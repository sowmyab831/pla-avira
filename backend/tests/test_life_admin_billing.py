"""Offline regressions: real SQLite records, mocked payment/network adapters."""
import asyncio
import hashlib
import hmac
import json
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.database import Base, get_session, UserDB
from app.models.life_admin import CommitmentDB, BillingAccountDB, BillingEventDB
from app.routes import life_admin, billing as billing_routes
from app.routes.auth import get_current_user
from app.services import billing, nexus_bus, notification_service, smart_shopping


class AsyncSessionAdapter:
    """Exercise actual SQL ownership filters without touching deployment DB."""
    def __init__(self, session): self.session = session
    async def execute(self, query): return self.session.execute(query)
    async def get(self, model, key): return self.session.get(model, key)
    def add(self, row): self.session.add(row)
    async def flush(self): self.session.flush()
    async def commit(self): self.session.commit()
    async def refresh(self, row): self.session.refresh(row)


@pytest.fixture
def harness():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[CommitmentDB.__table__, BillingAccountDB.__table__, BillingEventDB.__table__, UserDB.__table__])
    session = Session(engine, expire_on_commit=False)
    db = AsyncSessionAdapter(session)
    identity = {'id': 'owner-a'}
    for identifier in ['owner-a', 'owner-b']:
        session.add(UserDB(user_id=identifier, username=identifier, email=f'{identifier}@example.test', password_hash='test-only', role='user', subscription_tier='free'))
    session.commit()
    app = FastAPI(); app.include_router(life_admin.router); app.include_router(billing_routes.router)
    app.dependency_overrides[get_current_user] = lambda: session.get(UserDB, identity['id'])
    app.dependency_overrides[get_session] = lambda: db
    with TestClient(app) as client:
        yield client, identity, session, db
    session.close(); engine.dispose()


def payload(**changes):
    return dict(title='Electricity', kind='bill', country='IN', currency='INR', amount_minor=125050,
                due_date='2026-01-31', timezone='Asia/Kolkata', recurrence='monthly', **changes)


def test_commitment_isolation_recurrence_and_duplicate_completion(harness):
    client, identity, session, _ = harness
    created = client.post('/api/life-admin/commitments', json=payload())
    assert created.status_code == 201, created.text
    row = created.json(); identifier = row['id']
    identity['id'] = 'owner-b'
    assert client.get('/api/life-admin/commitments').json()['items'] == []
    assert client.post(f'/api/life-admin/commitments/{identifier}/complete', json={'version': 1}).status_code == 404
    identity['id'] = 'owner-a'
    done = client.post(f'/api/life-admin/commitments/{identifier}/complete', json={'version': 1})
    assert done.json()['due_date'] == '2026-02-28'
    assert client.post(f'/api/life-admin/commitments/{identifier}/complete', json={'version': 1}).status_code == 409
    done = client.post(f'/api/life-admin/commitments/{identifier}/complete', json={'version': 2})
    assert done.json()['due_date'] == '2026-03-31'
    assert session.get(CommitmentDB, identifier).amount_minor == 125050
    assert len(done.json()['history']) == 2


@pytest.mark.parametrize('changes', [dict(amount_minor=-1),dict(amount_minor=12.5),dict(currency='USD'),dict(title=' '),dict(timezone='invalid'),dict(reference_url='javascript:alert(1)'),dict(reference_url='https://user:pass@example.test')])
def test_commitment_validation(changes):
    value = payload(); value.update(changes)
    with pytest.raises(ValidationError): life_admin.CommitmentIn(**value)


def test_timezone_and_leap_year():
    assert life_admin.next_due(date(2024,2,29),'yearly',29) == date(2025,2,28)
    assert life_admin.next_due(date(2026,12,31),'monthly',31) == date(2027,1,31)


def test_edit_conflict_and_separate_currency_totals(harness):
    client, _, _, _ = harness
    p = payload(); p['due_date'] = date.today().isoformat()
    row = client.post('/api/life-admin/commitments', json=p).json()
    p['title'] = 'Edited bill'
    assert client.put(f"/api/life-admin/commitments/{row['id']}?version=1",json=p).status_code == 200
    assert client.put(f"/api/life-admin/commitments/{row['id']}?version=1",json=p).status_code == 409
    totals = client.get('/api/life-admin/commitments').json()['due_within_30_days_minor']
    assert totals == {'USD':0,'INR':125050}


def test_checkout_disabled_no_record(harness, monkeypatch):
    client, _, session, _ = harness
    monkeypatch.setenv('AVIRA_PAYMENTS_ENABLED','false')
    r = client.post('/api/billing/checkout', json={'country':'IN','tier':'premium'})
    assert r.status_code == 503
    assert session.query(BillingAccountDB).count() == 0
    assert not client.get('/api/billing/catalog').json()['markets']['IN']['plans'][0]['enabled']


@pytest.mark.parametrize('provider', ['stripe','razorpay'])
def test_signature_tamper_and_replay(provider, monkeypatch):
    monkeypatch.setenv(f'{provider.upper()}_WEBHOOK_SECRET','fixture-secret')
    body = b'{"id":"evt_fixture"}'
    raw = b'1000.' + body if provider == 'stripe' else body
    digest = hmac.new(b'fixture-secret',raw,hashlib.sha256).hexdigest()
    sig = 't=1000,v1=' + digest if provider == 'stripe' else digest
    assert billing.verify_webhook(provider, body, sig, now=1001)['id'] == 'evt_fixture'
    with pytest.raises(ValueError): billing.verify_webhook(provider, body+b' ',sig,now=1001)
    if provider == 'stripe':
        with pytest.raises(ValueError): billing.verify_webhook(provider,body,sig,now=1400)


def test_checkout_reuses_pending_session(harness, monkeypatch):
    client, _, session, _ = harness
    monkeypatch.setattr(billing,'readiness',lambda *args: True)
    create = AsyncMock(return_value=('cs_fixture', None, 'https://checkout.stripe.com/c/pay/fixture'))
    monkeypatch.setattr(billing,'create_checkout',create)
    for _ in range(2):
        assert client.post('/api/billing/checkout',json={'country':'US','tier':'premium'}).status_code == 200
    assert create.await_count == 1
    assert session.get(UserDB,'owner-a').subscription_tier == 'free'


def test_webhook_verification_and_idempotency(harness, monkeypatch):
    client, _, session, _ = harness
    account = BillingAccountDB(id='billing-fixture', user_id='owner-a', provider='stripe',country='US',tier='premium',provider_id='sub_fixture',status='checkout_pending')
    session.add(account);session.commit()
    monkeypatch.setenv('STRIPE_WEBHOOK_SECRET','fixture-secret')
    import time
    def signed(event_id):
        data=json.dumps({'id':event_id,'type':'customer.subscription.updated','data':{'object':{'id':'sub_fixture','metadata':{'avira_billing_id':'billing-fixture'}}}}).encode()
        stamp=str(int(time.time()))
        sig=hmac.new(b'fixture-secret',stamp.encode()+b'.'+data,hashlib.sha256).hexdigest()
        return data,{'stripe-signature':f't={stamp},v1={sig}'}
    snapshot=AsyncMock(return_value={'id':'sub_fixture','status':'active'})
    monkeypatch.setattr(billing,'subscription_snapshot',snapshot)
    data,headers=signed('event1')
    assert client.post('/api/billing/webhook/stripe',content=data,headers={'stripe-signature':'bad'}).status_code == 400
    assert session.get(UserDB,'owner-a').subscription_tier == 'free'
    assert client.post('/api/billing/webhook/stripe',content=data,headers=headers).status_code == 200
    assert session.get(UserDB,'owner-a').subscription_tier == 'premium'
    assert client.post('/api/billing/webhook/stripe',content=data,headers=headers).json()['duplicate']
    assert snapshot.await_count == 1
    snapshot.return_value={'id':'sub_fixture','status':'canceled'}
    data,headers=signed('event2')
    assert client.post('/api/billing/webhook/stripe',content=data,headers=headers).status_code == 200
    assert session.get(UserDB,'owner-a').subscription_tier == 'free'


@pytest.mark.parametrize('url', ['https://evil.test','http://checkout.stripe.com','https://checkout.stripe.com.evil.test','https://user:pass@checkout.stripe.com'])
def test_checkout_redirect_allowlist(url):
    assert not billing.checkout_url_allowed(url,'stripe')


def test_selective_action_and_failure_state(monkeypatch):
    called=[]
    async def apply(db,user,params): called.append(params['name']); return {}
    monkeypatch.setattr(nexus_bus,'_APPLY',{'test.run':apply})
    monkeypatch.setattr(nexus_bus,'flag_modified',lambda *a:None)
    event=SimpleNamespace(actions=[{'domain':'test','action':'run','status':'pending','params':{'name':'chosen'}},
                                    {'domain':'test','action':'run','status':'skipped','params':{'name':'skipped'}}])
    asyncio.run(nexus_bus._apply_actions(None,'owner-a',event))
    assert called == ['chosen']; assert event.status == 'applied'
    async def fail(*a): raise ValueError('fixture failure')
    monkeypatch.setattr(nexus_bus,'_APPLY',{'test.run':fail})
    event.actions=[{'domain':'test','action':'run','status':'pending','params':{}}]
    asyncio.run(nexus_bus._apply_actions(None,'owner-a',event))
    assert event.status == 'failed'; assert event.applied_at is None


def test_notification_other_owner_cannot_send(monkeypatch):
    pending={'fixture':{'user_id':'owner-a','status':'pending_approval','channels':['email']}}
    monkeypatch.setattr(notification_service,'_PENDING_APPROVALS',pending)
    assert not asyncio.run(notification_service.approve_and_send('fixture','owner-b'))['success']
    assert not notification_service.reject_notification('fixture','owner-b')['success']
    assert pending['fixture']['status'] == 'pending_approval'


def test_notification_unsupported_channel_is_not_sent(monkeypatch):
    pending={'fixture':{'user_id':'owner-a','status':'pending_approval','channels':['push']}}
    monkeypatch.setattr(notification_service,'_PENDING_APPROVALS',pending)
    monkeypatch.setattr(notification_service,'get_notification_prefs',lambda _: {})
    assert not asyncio.run(notification_service.approve_and_send('fixture','owner-a'))['success']
    assert pending['fixture']['status'] == 'failed'


def test_shopping_no_fake_offers(monkeypatch):
    service=smart_shopping.SmartShoppingService()
    for method in ['_scrape_slickdeals','_scrape_google_shopping','_scrape_amazon','_scrape_walmart']:
        monkeypatch.setattr(service,method,AsyncMock(return_value=[]))
    assert asyncio.run(service._search_retailer_prices('headphones')) == []


def test_shopping_conditional_rewards_not_subtracted():
    service=smart_shopping.SmartShoppingService()
    product={'id':'p1','price':200,'shipping':0,'retailer':'Store'}
    unverified=[{'retailer':'Store','description':'20% off'}]
    result=service._calculate_true_costs([product],unverified,{'cashback':[{'retailer':'Store','rate':'Up to 6%'}]})[0]
    assert result['true_cost']==200 and result['cashback_savings']==0 and result['price_complete'] is False
    coupon={'product_id':'p1','verified':True,'eligible':True,'type':'fixed','value':10}
    assert service._calculate_true_costs([product],[coupon],{})[0]['true_cost']==190


@pytest.mark.parametrize('country,provider,plan', [('US','stripe','price_fixture'),('IN','razorpay','plan_fixture')])
def test_provider_checkout_validates_configured_price(country,provider,plan,monkeypatch):
    monkeypatch.setattr(billing,'readiness',lambda *a: True)
    monkeypatch.setattr(billing,'plan_id',lambda *a: plan)
    monkeypatch.setenv('AVIRA_PUBLIC_URL','https://avira.example.test')
    account=SimpleNamespace(id='billing1',country=country,tier='premium',provider=provider)
    expected=billing.PRICES[country]['premium']
    price={'currency':'usd','unit_amount':expected,'active':True,'recurring':{'interval':'month','interval_count':1}} if provider=='stripe' else {'item':{'currency':'INR','amount':expected},'period':'monthly','interval':1}
    response={'id':'cs_fixture','url':'https://checkout.stripe.com/c/pay/test'} if provider=='stripe' else {'id':'sub_fixture','short_url':'https://rzp.io/test'}
    adapter=AsyncMock(side_effect=[price,response]);monkeypatch.setattr(billing,'request',adapter)
    checkout_id,sub_id,url=asyncio.run(billing.create_checkout(account))
    assert checkout_id and billing.checkout_url_allowed(url,provider)
    assert adapter.await_count==2
    if provider=='stripe':price['unit_amount']=1
    else:price['item']['amount']=1
    adapter.side_effect=[price]
    with pytest.raises(billing.BillingUnavailable):asyncio.run(billing.create_checkout(account))


def test_snapshot_rejects_other_billing_owner(monkeypatch):
    account=SimpleNamespace(provider='stripe',provider_id='sub_fixture',id='owner_a')
    monkeypatch.setattr(billing,'request',AsyncMock(return_value={'metadata':{'avira_billing_id':'owner_b'}}))
    with pytest.raises(ValueError):asyncio.run(billing.subscription_snapshot(account))


def test_private_member_partitions_verify_ownership():
    from app.services.private_scope import resolve_private_scope
    from fastapi import HTTPException
    user=SimpleNamespace(user_id='owner_a')
    db=SimpleNamespace(get=AsyncMock(return_value=SimpleNamespace(user_id='owner_a')))
    assert asyncio.run(resolve_private_scope('default',user,db))=='owner_a'
    assert asyncio.run(resolve_private_scope('member_123',user,db))=='member_123'
    db.get.return_value=SimpleNamespace(user_id='owner_b')
    with pytest.raises(HTTPException) as denied:asyncio.run(resolve_private_scope('member_123',user,db))
    assert denied.value.status_code==403
    with pytest.raises(HTTPException):asyncio.run(resolve_private_scope('default',None,db))


def test_wishlist_owned_database_routes(harness):
    from app.routes import shopping
    from app.models.life_admin import OwnedWishlistDB
    client,identity,session,db=harness
    OwnedWishlistDB.__table__.create(session.bind)
    client.app.include_router(shopping.router)
    row=client.post('/api/shopping/wishlist',json={'name':'Laptop','target_price':50000,'currency':'INR'}).json()['item']
    identity['id']='owner-b'
    assert client.get('/api/shopping/wishlist').json()['items']==[]
    assert client.get(f"/api/shopping/wishlist/{row['id']}/analysis").status_code==404
    identity['id']='owner-a'
    item=client.get('/api/shopping/wishlist').json()['items'][0]
    assert item['target_price']==50000 and item['currency']=='INR' and item['analysis'] is None


def test_regional_product_intent_and_units():
    from app.services.query_classifier import QueryClassifier
    from app.services.intent_engine import _items
    from app.services.imap_radar import classify
    from datetime import datetime
    for query in ['Buy USB C headphones under ₹5000','Find a TV under INR 25000']:
        assert QueryClassifier.classify_query(query)['category']=='shopping'
    assert _items('2 kg rice and 500 g dal')[0]['unit']=='kg'
    assert _items('2 kg rice and 500 g dal')[1]['unit']=='g'
    assert classify('Your electricity bill is ready: $1399.98 due Sep 25','','',datetime(2026,9,21))['amount']==1399.98
    assert classify('Electric dryer $1399.98 + Free Shipping','','',datetime(2026,9,21))['category']=='promo'


def test_llm_over_budget_is_not_sent(monkeypatch):
    from app.services import llm_client
    monkeypatch.setattr(llm_client,'_MAX_INPUT_CHARS',10)
    assert asyncio.run(llm_client.generate('x'*11))==''


def test_refund_tracking_preserves_currency_and_removes_completed_total(harness):
    client,_,_,_=harness
    value=payload();value.update(kind='refund',recurrence='none')
    row=client.post('/api/life-admin/commitments',json=value).json()
    before=client.get('/api/life-admin/commitments').json()
    assert before['pending_recovery_minor']=={'USD':0,'INR':125050}
    assert before['due_within_30_days_minor']=={'USD':0,'INR':0}
    assert client.post(f"/api/life-admin/commitments/{row['id']}/complete",json={'version':1}).json()['status']=='completed'
    assert client.get('/api/life-admin/commitments').json()['pending_recovery_minor']=={'USD':0,'INR':0}


def test_search_model_is_lazy(monkeypatch):
    from app import search
    monkeypatch.setattr(search,'_embedding_model',SimpleNamespace(encode=lambda text: SimpleNamespace(tolist=lambda: [1.0,2.0])))
    assert search._encode('fixture')==[1.0,2.0]
