#!/usr/bin/env python3
"""Massive Futures WebSocket vs REST 1-minute data parity test.

Diagnostic only. Does not import or modify Icon strategy logic and does not
send orders or PickMyTrade alerts.
"""

import asyncio
import json
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv

try:
    import websockets
except ImportError as exc:
    raise SystemExit("Missing dependency. Run: pip install websockets") from exc

load_dotenv(".env")

API_KEY = os.getenv("MASSIVE_API_KEY")
if not API_KEY:
    raise ValueError("MASSIVE_API_KEY was not found in .env")

SYMBOL = os.getenv("ICON_LIVE_SYMBOL", "MNQZ6")
WS_URL = os.getenv("MASSIVE_FUTURES_WS_URL", "wss://socket.massive.com/futures")
REST_URL = f"https://api.massive.com/futures/v1/aggs/{SYMBOL}"
TZ = ZoneInfo("America/New_York")
TARGET_BARS = int(os.getenv("ICON_PARITY_BARS", "5"))
REST_WAIT_SECONDS = float(os.getenv("ICON_PARITY_REST_WAIT_SECONDS", "8"))

FIELDS = {
    "open": ("o", "open"),
    "high": ("h", "high"),
    "low": ("l", "low"),
    "close": ("c", "close"),
    "volume": ("v", "volume"),
}


def to_utc_iso_from_ms(ms):
    return datetime.fromtimestamp(float(ms) / 1000.0, tz=timezone.utc).isoformat()


def to_et(ms):
    return datetime.fromtimestamp(float(ms) / 1000.0, tz=timezone.utc).astimezone(TZ)


def same_number(a, b, tol=1e-9):
    try:
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return a == b


def fetch_rest_bar(start_ms, end_ms):
    params = {
        "resolution": "1min",
        "window_start.gte": to_utc_iso_from_ms(start_ms),
        "window_start.lt": to_utc_iso_from_ms(end_ms),
        "limit": 10,
        "sort": "window_start.asc",
        "apiKey": API_KEY,
    }
    r = requests.get(REST_URL, params=params, timeout=30)
    r.raise_for_status()
    rows = r.json().get("results", [])
    if not rows:
        return None
    # Exact minute requested. Massive REST window_start is nanoseconds.
    wanted_ns = int(start_ms) * 1_000_000
    for row in rows:
        if int(row.get("window_start", -1)) == wanted_ns:
            return row
    return rows[0] if len(rows) == 1 else None


async def compare_bar(msg):
    start_ms = msg.get("s")
    end_ms = msg.get("e")
    if start_ms is None or end_ms is None:
        return False, ["missing WebSocket start/end timestamp"], None

    # Give REST a few seconds to publish the exact same completed minute.
    await asyncio.sleep(REST_WAIT_SECONDS)
    rest = await asyncio.to_thread(fetch_rest_bar, start_ms, end_ms)
    if rest is None:
        return False, ["REST bar not available for exact minute"], None

    mismatches = []
    for label, (ws_key, rest_key) in FIELDS.items():
        ws_val = msg.get(ws_key)
        rest_val = rest.get(rest_key)
        if not same_number(ws_val, rest_val):
            mismatches.append(f"{label}: WS={ws_val} REST={rest_val}")

    return len(mismatches) == 0, mismatches, rest


async def main():
    print("=" * 76)
    print("THE ICON — MASSIVE 1-MIN DATA PARITY TEST")
    print(f"Symbol: {SYMBOL} | Bars to compare: {TARGET_BARS}")
    print("WebSocket AM candle vs Massive REST candle for the exact same minute.")
    print("Diagnostic only — NO strategy imports and NO order execution.")
    print("=" * 76)

    passed = 0
    tested = 0

    async with websockets.connect(WS_URL, ping_interval=20, ping_timeout=20) as ws:
        print("Connected.")
        await ws.recv()
        await ws.send(json.dumps({"action": "auth", "params": API_KEY}))

        while True:
            raw = await ws.recv()
            messages = json.loads(raw)
            if not isinstance(messages, list):
                messages = [messages]
            if any(m.get("ev") == "status" and m.get("status") == "auth_success" for m in messages):
                await ws.send(json.dumps({"action": "subscribe", "params": f"AM.{SYMBOL}"}))
                print(f"Authenticated. Waiting for {TARGET_BARS} completed 1-minute candles...\n")
                break

        async for raw in ws:
            messages = json.loads(raw)
            if not isinstance(messages, list):
                messages = [messages]

            for msg in messages:
                if msg.get("ev") != "AM":
                    continue

                tested += 1
                start_ms = msg.get("s")
                stamp = to_et(start_ms).strftime("%Y-%m-%d %H:%M ET") if start_ms else "unknown"
                ok, mismatches, rest = await compare_bar(msg)

                if ok:
                    passed += 1
                    print(
                        f"PASS {tested}/{TARGET_BARS} | {stamp} | "
                        f"O={msg.get('o')} H={msg.get('h')} L={msg.get('l')} "
                        f"C={msg.get('c')} V={msg.get('v')}"
                    )
                else:
                    print(f"FAIL {tested}/{TARGET_BARS} | {stamp}")
                    for item in mismatches:
                        print("   ", item)

                if tested >= TARGET_BARS:
                    print("\n" + "=" * 76)
                    print(f"RESULT: {passed}/{tested} exact OHLCV matches")
                    print("DATA PARITY:", "PASS" if passed == tested else "FAIL")
                    print("=" * 76)
                    return


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
