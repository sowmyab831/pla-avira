"""Provider-hosted subscriptions. Keys and prices remain on the server."""
import hashlib
import hmac
import json
import os
import time
from urllib.parse import urlparse
import httpx

PROVIDERS = {"US": "stripe", "IN": "razorpay"}
CURRENCIES = {"US": "USD", "IN": "INR"}
PRICES = {"US": {"premium": 999, "enterprise": 1999}, "IN": {"premium": 49900, "enterprise": 99900}}


class BillingUnavailable(ValueError):
    pass


def plan_id(country, tier):
    if country not in PROVIDERS or tier not in PRICES[country]:
        raise ValueError("Unsupported country or tier")
    prefix = "STRIPE_PRICE" if country == "US" else "RAZORPAY_PLAN"
    return os.getenv(f"{prefix}_{country}_{tier.upper()}", "")


def readiness(country, tier):
    provider = PROVIDERS[country]
    names = (["STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET"] if provider == "stripe" else
             ["RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET", "RAZORPAY_WEBHOOK_SECRET"])
    enabled = os.getenv("AVIRA_PAYMENTS_ENABLED", "false").lower() == "true"
    return enabled and all(os.getenv(n) for n in names) and bool(plan_id(country, tier)) and bool(os.getenv("AVIRA_PUBLIC_URL"))


def checkout_url_allowed(url, provider):
    p = urlparse(url or "")
    allowed = {"stripe": {"checkout.stripe.com"}, "razorpay": {"rzp.io"}}
    return p.scheme == "https" and p.hostname in allowed[provider] and not p.username and not p.password


async def request(provider, method, path, *, data=None, key=None):
    if provider == "stripe":
        base = "https://api.stripe.com/v1"
        auth = (os.environ["STRIPE_SECRET_KEY"], "")
        headers = {"Idempotency-Key": key} if key else {}
        kwargs = {"data": data} if data is not None else {}
    else:
        base = "https://api.razorpay.com/v1"
        auth = (os.environ["RAZORPAY_KEY_ID"], os.environ["RAZORPAY_KEY_SECRET"])
        headers = {}
        kwargs = {"json": data} if data is not None else {}
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.request(method, base + path, auth=auth, headers=headers, **kwargs)
        response.raise_for_status()
        return response.json()


async def create_checkout(account):
    country, tier, provider = account.country, account.tier, account.provider
    if not readiness(country, tier):
        raise BillingUnavailable("Payments for this country and plan are not enabled yet.")
    public = os.environ["AVIRA_PUBLIC_URL"].rstrip("/")
    if urlparse(public).scheme != "https":
        raise BillingUnavailable("Configure an HTTPS public application URL before enabling payments.")
    configured_plan = plan_id(country, tier)
    expected = PRICES[country][tier]
    if provider == "stripe":
        price = await request(provider, "GET", f"/prices/{configured_plan}")
        if (price.get("currency") != "usd" or price.get("unit_amount") != expected
                or price.get("recurring", {}).get("interval") != "month"
                or price.get("recurring", {}).get("interval_count") != 1 or not price.get("active")):
            raise BillingUnavailable("The configured Stripe price does not match the displayed monthly plan.")
        obj = await request(provider, "POST", "/checkout/sessions", key=account.id, data={
            "mode": "subscription", "client_reference_id": account.id,
            "line_items[0][price]": configured_plan, "line_items[0][quantity]": "1",
            "subscription_data[metadata][avira_billing_id]": account.id,
            "success_url": public + "/#subscription", "cancel_url": public + "/#subscription"})
        return obj["id"], None, obj["url"]
    plan = await request(provider, "GET", f"/plans/{configured_plan}")
    if (plan.get("item", {}).get("currency") != "INR" or plan.get("item", {}).get("amount") != expected
            or plan.get("period") != "monthly" or plan.get("interval") != 1):
        raise BillingUnavailable("The configured Razorpay plan does not match the displayed monthly plan.")
    obj = await request(provider, "POST", "/subscriptions", data={"plan_id": configured_plan,
        "total_count": 120, "quantity": 1, "customer_notify": False, "notes": {"avira_billing_id": account.id}})
    return obj["id"], obj["id"], obj["short_url"]


def verify_webhook(provider, body, signature, now=None):
    secret = os.getenv(f"{provider.upper()}_WEBHOOK_SECRET")
    if not secret:
        raise BillingUnavailable("Webhook verification is not configured")
    if provider == "stripe":
        pieces = [x.split("=", 1) for x in (signature or "").split(",") if "=" in x]
        stamps = [v for k, v in pieces if k == "t"]
        signatures = [v for k, v in pieces if k == "v1"]
        if len(stamps) != 1:
            raise ValueError("Invalid signature")
        try:
            timestamp = int(stamps[0])
        except ValueError:
            raise ValueError("Invalid timestamp")
        if abs((time.time() if now is None else now) - timestamp) > 300:
            raise ValueError("Expired signature")
        expected = hmac.new(secret.encode(), str(timestamp).encode() + b"." + body, hashlib.sha256).hexdigest()
        if not any(hmac.compare_digest(expected, s) for s in signatures):
            raise ValueError("Invalid signature")
    else:
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature or ""):
            raise ValueError("Invalid signature")
    event = json.loads(body)
    if not isinstance(event, dict):
        raise ValueError("Invalid event")
    return event


async def subscription_snapshot(account, subscription_id=None):
    identifier = subscription_id or account.provider_id
    if not identifier or not identifier.startswith("sub_") or not all(c.isalnum() or c == '_' for c in identifier):
        raise ValueError("Invalid provider subscription")
    obj = await request(account.provider, "GET", f"/subscriptions/{identifier}")
    metadata = obj.get("metadata" if account.provider == "stripe" else "notes") or {}
    if metadata.get("avira_billing_id") != account.id:
        raise ValueError("Subscription does not belong to this billing record")
    if account.provider == "stripe":
        items = obj.get("items", {}).get("data", [])
        if len(items) != 1 or items[0].get("price", {}).get("id") != plan_id(account.country, account.tier) or items[0].get("quantity") != 1:
            raise ValueError("Unexpected subscription plan")
    elif obj.get("plan_id") != plan_id(account.country, account.tier) or obj.get("quantity") != 1:
        raise ValueError("Unexpected subscription plan")
    return obj
