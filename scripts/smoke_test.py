"""Paper trading smoke test — runs against a live local stack.

Usage:
    python scripts/smoke_test.py [--base-url http://localhost:8000] [--api-key dev-key]

Checks:
  1. GET  /health               → status ok
  2. GET  /v1/watchlist         → empty list
  3. POST /v1/watchlist         → add 005930 (Samsung)
  4. GET  /v1/watchlist         → contains 005930
  5. GET  /v1/positions         → empty list (paper mode)
  6. GET  /v1/orders            → empty list
  7. POST /v1/orders            → paper LIMIT BUY (paper mode returns PAPER-* id)
  8. GET  /v1/orders            → 1 pending trade
  9. GET  /v1/risk/status       → not halted
 10. DELETE /v1/watchlist/005930 → 204

Exit code 0 = all passed, 1 = at least one failure.
"""
from __future__ import annotations

import argparse
import sys
from typing import Any

import httpx

TICKER = "005930"


def check(label: str, condition: bool, detail: str = "") -> bool:
    status = "PASS" if condition else "FAIL"
    suffix = f"  ({detail})" if detail else ""
    print(f"  [{status}] {label}{suffix}")
    return condition


def run(base_url: str, api_key: str) -> bool:
    headers = {"X-API-Key": api_key}
    all_pass = True

    with httpx.Client(base_url=base_url, headers=headers, timeout=10.0) as client:

        # 1. Health
        r = client.get("/health")
        ok = check("GET /health → 200", r.status_code == 200)
        all_pass = all_pass and ok
        if ok:
            body = r.json()
            check("  status == ok", body.get("status") == "ok", str(body.get("status")))

        # 2. Empty watchlist
        r = client.get("/v1/watchlist")
        ok = check("GET /v1/watchlist → 200", r.status_code == 200)
        all_pass = all_pass and ok

        # 3. Add to watchlist
        r = client.post("/v1/watchlist", json={"ticker": TICKER, "name": "삼성전자"})
        ok = check("POST /v1/watchlist → 201", r.status_code == 201)
        all_pass = all_pass and ok
        if ok:
            body = r.json()
            check(f"  ticker == {TICKER}", body.get("ticker") == TICKER, str(body.get("ticker")))

        # 4. Watchlist contains ticker
        r = client.get("/v1/watchlist")
        all_pass = all_pass and check("GET /v1/watchlist after add → has ticker",
                                      any(i["ticker"] == TICKER for i in r.json()))

        # 5. Positions empty (paper)
        r = client.get("/v1/positions")
        all_pass = all_pass and check("GET /v1/positions → 200", r.status_code == 200)

        # 6. Orders empty
        r = client.get("/v1/orders")
        all_pass = all_pass and check("GET /v1/orders → 200", r.status_code == 200)

        # 7. Manual BUY order (paper mode)
        payload = {"ticker": TICKER, "side": "BUY", "order_type": "LIMIT", "quantity": 5, "price": 75000.0}
        r = client.post("/v1/orders", json=payload)
        ok = check("POST /v1/orders (paper BUY) → 201", r.status_code == 201)
        all_pass = all_pass and ok
        if ok:
            body = r.json()
            ok2 = check("  order_id starts with PAPER-", str(body.get("order_id", "")).startswith("PAPER-"),
                        str(body.get("order_id")))
            all_pass = all_pass and ok2

        # 8. Orders list has 1 pending
        r = client.get("/v1/orders")
        orders = r.json()
        all_pass = all_pass and check("GET /v1/orders → 1 pending trade", len(orders) >= 1,
                                      f"count={len(orders)}")

        # 9. Risk status not halted
        r = client.get("/v1/risk/status")
        ok = check("GET /v1/risk/status → 200", r.status_code == 200)
        all_pass = all_pass and ok
        if ok:
            body = r.json()
            all_pass = all_pass and check("  trading_halted == False", not body.get("trading_halted"),
                                          str(body.get("trading_halted")))

        # 10. Remove from watchlist
        r = client.delete(f"/v1/watchlist/{TICKER}")
        all_pass = all_pass and check(f"DELETE /v1/watchlist/{TICKER} → 204", r.status_code == 204)

    return all_pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Paper trading smoke test")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--api-key", default="dev-key")
    args = parser.parse_args()

    print(f"\nSmoke test → {args.base_url}\n{'─' * 50}")
    passed = run(args.base_url, args.api_key)
    print(f"{'─' * 50}")
    print(f"Result: {'ALL PASSED ✓' if passed else 'FAILURES DETECTED ✗'}\n")
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
