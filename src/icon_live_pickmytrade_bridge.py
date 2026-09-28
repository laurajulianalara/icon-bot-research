#!/usr/bin/env python3
"""
THE ICON — live PickMyTrade alert parity bridge.

Purpose:
- Run the existing frozen current-month reporter unchanged.
- Detect only NEW FINAL trades written by that reporter.
- Send exactly one PickMyTrade alert for each new live trade.
- Use an intentionally non-executable account id during transport testing.

This file does NOT contain or modify strategy selection logic.
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from dotenv import load_dotenv

TZ = ZoneInfo("America/New_York")
REPORTER = Path("src/icon_month_live_report.py")
STATE_PATH = Path("data/reports/pickmytrade_alert_state.json")
ALERT_LOG_PATH = Path("data/reports/pickmytrade_alerts_sent.csv")
TIMING_LOG_PATH = Path("data/reports/pickmytrade_timing_diagnostic.csv")

load_dotenv(".env")

WEBHOOK_URL = os.getenv("PICKMYTRADE_WEBHOOK_URL")
TOKEN = os.getenv("PICKMYTRADE_TOKEN")
# Deliberately invalid by default. Never put a funded account id in source code.
ACCOUNT_ID = "ICON_ALERT_TEST_INVALID"
POLL_SECONDS = float(os.getenv("PICKMYTRADE_POLL_SECONDS", "1"))

if not WEBHOOK_URL:
    raise ValueError("PICKMYTRADE_WEBHOOK_URL was not found in .env")
if not TOKEN:
    raise ValueError("PICKMYTRADE_TOKEN was not found in .env")

STATE_PATH.parent.mkdir(parents=True, exist_ok=True)


def trade_key(row):
    return "|".join([
        str(row["entry_time"]),
        str(row["direction"]),
        f'{float(row["entry"]):.8f}',
        f'{float(row["stop"]):.8f}',
    ])


def load_state():
    if not STATE_PATH.exists():
        return {"seen": []}
    try:
        return json.loads(STATE_PATH.read_text())
    except Exception:
        return {"seen": []}


def save_state(seen):
    STATE_PATH.write_text(json.dumps({"seen": sorted(seen)}, indent=2))


def pickmytrade_payload(row):
    direction = str(row["direction"]).upper()
    if direction == "LONG":
        action = "buy"
    elif direction == "SHORT":
        action = "sell"
    else:
        raise ValueError(f"Unknown direction: {direction}")

    # Preserve PickMyTrade's generated JSON structure.
    return {
        "symbol": "MNQZ6",
        "strategy_name": "Test",
        "date": pd.Timestamp(row["entry_time"]).isoformat(),
        "data": action,
        "quantity": 1,
        "risk_percentage": 0,
        "price": float(row["entry"]),
        "tp": 0,
        "percentage_tp": 0,
        "dollar_tp": 0,
        "sl": 0,
        "dollar_sl": 0,
        "percentage_sl": 0,
        "trail": 0,
        "trail_stop": 0,
        "trail_trigger": 0,
        "trail_freq": 0,
        "update_tp": False,
        "update_sl": False,
        "breakeven": 0,
        "breakeven_offset": 0,
        "token": TOKEN,
        "pyramid": False,
        "same_direction_ignore": False,
        "reverse_order_close": False,
        "multiple_accounts": [
            {
                "token": TOKEN,
                "account_id": ACCOUNT_ID,
                "risk_percentage": 0,
                "quantity_multiplier": 1,
            }
        ],
    }


def append_alert_log(row, key, status_code, response_text):
    record = pd.DataFrame([{
        "sent_at_et": datetime.now(TZ).isoformat(),
        "trade_key": key,
        "entry_time": row["entry_time"],
        "direction": row["direction"],
        "entry": row["entry"],
        "stop": row["stop"],
        "http_status": status_code,
        "response": response_text[:1000],
    }])
    record.to_csv(
        ALERT_LOG_PATH,
        mode="a",
        header=not ALERT_LOG_PATH.exists(),
        index=False,
    )


def run_reporter():
    reporter_started_at = datetime.now(TZ)
    monotonic_start = time.monotonic()
    result = subprocess.run([sys.executable, str(REPORTER)])
    reporter_finished_at = datetime.now(TZ)
    reporter_runtime_seconds = time.monotonic() - monotonic_start
    if result.returncode != 0:
        raise RuntimeError(f"Reporter exited with code {result.returncode}")
    print(
        f"TIMING | reporter {reporter_started_at.isoformat()} -> "
        f"{reporter_finished_at.isoformat()} | {reporter_runtime_seconds:.3f}s"
    )
    return {
        "reporter_started_at_et": reporter_started_at,
        "reporter_finished_at_et": reporter_finished_at,
        "reporter_runtime_seconds": reporter_runtime_seconds,
    }


def process_new_live_trades(reporter_timing=None):
    now = datetime.now(TZ)
    report_path = Path(f"data/reports/{now:%Y-%m}_trades.csv")
    if not report_path.exists():
        return 0

    trades = pd.read_csv(report_path)
    if trades.empty:
        return 0

    trades["entry_time"] = pd.to_datetime(trades["entry_time"], errors="coerce")
    trades = trades[trades["entry_time"].notna()].copy()

    # LIVE ONLY: never replay historical/backtest trades into PickMyTrade.
    today = now.date()
    trades = trades[trades["entry_time"].dt.date == today].copy()
    trades = trades.sort_values("entry_time")

    state = load_state()
    seen = set(state.get("seen", []))
    sent = 0

    for _, row in trades.iterrows():
        key = trade_key(row)
        if key in seen:
            continue

        payload = pickmytrade_payload(row)
        detected_at = datetime.now(TZ)
        entry_ts = pd.Timestamp(row["entry_time"])
        if entry_ts.tzinfo is None:
            entry_ts = entry_ts.tz_localize(TZ)
        else:
            entry_ts = entry_ts.tz_convert(TZ)
        entry_to_detect_seconds = (detected_at - entry_ts.to_pydatetime()).total_seconds()

        print(
            f"NEW LIVE FINAL TRADE -> PickMyTrade | "
            f"{row['entry_time']} | {row['direction']} | entry {row['entry']}"
        )
        print(
            f"TIMING | entry -> bridge detect: {entry_to_detect_seconds:.3f}s | "
            f"detected {detected_at.isoformat()}"
        )

        webhook_started_at = datetime.now(TZ)
        webhook_monotonic_start = time.monotonic()
        try:
            response = requests.post(WEBHOOK_URL, json=payload, timeout=20)
            webhook_response_at = datetime.now(TZ)
            webhook_roundtrip_seconds = time.monotonic() - webhook_monotonic_start
            response_text = response.text
            append_alert_log(row, key, response.status_code, response_text)

            timing_record = pd.DataFrame([{
                "trade_key": key,
                "entry_time": entry_ts.isoformat(),
                "reporter_started_at_et": (
                    reporter_timing["reporter_started_at_et"].isoformat()
                    if reporter_timing else ""
                ),
                "reporter_finished_at_et": (
                    reporter_timing["reporter_finished_at_et"].isoformat()
                    if reporter_timing else ""
                ),
                "reporter_runtime_seconds": (
                    reporter_timing["reporter_runtime_seconds"]
                    if reporter_timing else ""
                ),
                "bridge_detected_at_et": detected_at.isoformat(),
                "entry_to_bridge_detect_seconds": entry_to_detect_seconds,
                "webhook_started_at_et": webhook_started_at.isoformat(),
                "webhook_response_at_et": webhook_response_at.isoformat(),
                "webhook_roundtrip_seconds": webhook_roundtrip_seconds,
                "http_status": response.status_code,
            }])
            timing_record.to_csv(
                TIMING_LOG_PATH,
                mode="a",
                header=not TIMING_LOG_PATH.exists(),
                index=False,
            )
            print(
                f"TIMING | webhook round trip: {webhook_roundtrip_seconds:.3f}s | "
                f"response {webhook_response_at.isoformat()}"
            )

            # Mark received requests as seen after PickMyTrade responds.
            # 4xx is still a completed transport attempt and is expected
            # with the intentionally invalid test account.
            if response.status_code < 500:
                seen.add(key)
                save_state(seen)
                sent += 1
                print(
                    f"PickMyTrade responded HTTP {response.status_code}. "
                    "Check PickMyTrade Alerts Log."
                )
            else:
                print(f"Server error HTTP {response.status_code}; will retry.")

        except requests.RequestException as exc:
            append_alert_log(row, key, "REQUEST_ERROR", str(exc))
            print("Webhook request failed; will retry:", exc)

    return sent


def baseline_existing_today():
    """Mark trades already present at startup as seen so they are never replayed."""
    run_reporter()

    now = datetime.now(TZ)
    report_path = Path(f"data/reports/{now:%Y-%m}_trades.csv")
    if not report_path.exists():
        return 0

    trades = pd.read_csv(report_path)
    if trades.empty or "entry_time" not in trades.columns:
        return 0

    trades["entry_time"] = pd.to_datetime(trades["entry_time"], errors="coerce")
    trades = trades[trades["entry_time"].notna()].copy()
    trades = trades[trades["entry_time"].dt.date == now.date()].copy()

    state = load_state()
    seen = set(state.get("seen", []))
    before = len(seen)

    for _, row in trades.iterrows():
        seen.add(trade_key(row))

    save_state(seen)
    return len(seen) - before


def main():
    print("=" * 68)
    print("THE ICON — LIVE PICKMYTRADE ALERT PARITY")
    print("Source: frozen Python reporter")
    print("Mode: LIVE trades only")
    print("Destination account: intentionally non-executable test id")
    print("=" * 68)
    print(f"Polling every {POLL_SECONDS:g}s. Ctrl+C to stop.")
    baseline_count = baseline_existing_today()
    print(f"Startup baseline: {baseline_count} existing trade(s) ignored.")

    while True:
        try:
            reporter_timing = run_reporter()
            process_new_live_trades(reporter_timing)
        except KeyboardInterrupt:
            print("\nStopped.")
            break
        except Exception as exc:
            print("Cycle error:", exc)

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
