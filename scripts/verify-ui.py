#!/usr/bin/env python3
"""Browser verification sweep for the Avira frontend.

Logs in with real credentials, visits every hash-routed page, and records:
  - console errors / page errors
  - failed API calls (status >= 400, excluding expected 404s for empty data)
  - blank page detection (main content empty)
  - a screenshot per page (docs/verification/screenshots/)

Usage:
  python3 scripts/verify-ui.py [--base http://localhost:30001]
                               [--user verify_u1] [--password Test1234!]
                               [--pages dashboard,finance,...]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

from playwright.sync_api import sync_playwright

PAGES = [
    'dashboard', 'today', 'radar', 'care', 'assistant', 'finance', 'health',
    'school', 'calendar', 'shopping', 'travel', 'grocery', 'nutrition',
    'family', 'portfolio', 'tasks', 'news', 'trading', 'market_intel',
    'forecast', 'day_trader', 'earnings_intel', 'action_center',
    'subscription', 'admin', 'notifications', 'maintenance', 'integrations',
    'ai_settings',
]

OUT_DIR = pathlib.Path(__file__).resolve().parents[1] / 'docs' / 'verification'


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default='http://localhost:30001')
    ap.add_argument('--user', default='verify_u1')
    ap.add_argument('--password', default='Test1234!')
    ap.add_argument('--pages', default=','.join(PAGES))
    ap.add_argument('--wait-ms', type=int, default=2500)
    args = ap.parse_args()

    pages = [p for p in args.pages.split(',') if p]
    shots = OUT_DIR / 'screenshots'
    shots.mkdir(parents=True, exist_ok=True)
    report: dict = {'base': args.base, 'user': args.user, 'pages': {}, 'login': {}}

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(viewport={'width': 1440, 'height': 900})
        page = ctx.new_page()

        console_errors: list[str] = []
        page_errors: list[str] = []
        bad_responses: list[dict] = []
        page.on('console', lambda m: console_errors.append(m.text) if m.type == 'error' else None)
        page.on('pageerror', lambda e: page_errors.append(str(e)))
        page.on('response', lambda r: bad_responses.append(
            {'url': r.url, 'status': r.status}) if r.status >= 400 else None)

        # ── Login ─────────────────────────────────────────────────────
        page.goto(args.base, wait_until='networkidle')
        report['login']['landing'] = page.title()
        try:
            page.fill('input[placeholder="Username"]', args.user, timeout=8000)
            page.fill('input[placeholder="Password"]', args.password)
            page.click('button[type="submit"]')
            page.wait_for_timeout(3000)
            token = page.evaluate("localStorage.getItem('auth_token')")
            report['login']['authenticated'] = bool(token)
        except Exception as e:
            report['login']['authenticated'] = False
            report['login']['error'] = str(e)[:300]
            page.screenshot(path=str(shots / 'login-failed.png'))

        if not report['login'].get('authenticated'):
            (OUT_DIR / 'ui-verify-report.json').write_text(json.dumps(report, indent=2))
            print('LOGIN FAILED — report at', OUT_DIR / 'ui-verify-report.json')
            return 1

        # ── Page sweep ────────────────────────────────────────────────
        for pid in pages:
            console_errors.clear()
            page_errors.clear()
            bad_responses.clear()
            t0 = time.time()
            try:
                page.goto(f'{args.base}/#{pid}', wait_until='networkidle')
                page.wait_for_timeout(args.wait_ms)
                # Is anything rendered? (main content area has text)
                text = page.evaluate(
                    "document.querySelector('main')?.innerText || document.body.innerText")
                entry = {
                    'rendered_chars': len(text.strip()),
                    'console_errors': list(console_errors),
                    'page_errors': list(page_errors),
                    'bad_api_calls': [r for r in bad_responses],
                    'elapsed_ms': int((time.time() - t0) * 1000),
                }
                entry['ok'] = len(text.strip()) > 50 and not page_errors
                page.screenshot(path=str(shots / f'{pid}.png'))
            except Exception as e:
                entry = {'ok': False, 'fatal': str(e)[:300]}
            report['pages'][pid] = entry
            status = 'OK' if entry.get('ok') else 'FAIL'
            print(f"{status:4} {pid:18} chars={entry.get('rendered_chars', 0):>6} "
                  f"console_err={len(entry.get('console_errors', []))} "
                  f"api_err={len(entry.get('bad_api_calls', []))}")

        browser.close()

    (OUT_DIR / 'ui-verify-report.json').write_text(json.dumps(report, indent=2))
    passed = sum(1 for v in report['pages'].values() if v.get('ok'))
    print(f"\n{passed}/{len(report['pages'])} pages rendered OK → {OUT_DIR / 'ui-verify-report.json'}")
    return 0 if passed == len(report['pages']) else 2


if __name__ == '__main__':
    sys.exit(main())
