#!/usr/bin/env python3
"""
THE ICON — Massive MNQ live connection smoke test.

Infrastructure only. This file does NOT change or execute Option 2B strategy logic.
It authenticates to Massive's real-time Futures WebSocket, subscribes to MNQZ6
minute aggregates, and prints incoming events so we can verify the live feed first.
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

try:
    import websockets
except ImportError:
    print("Missing dependency: websockets")
    print("Run: pip install websockets")
    raise

WS_URL = "wss://socket.massive.com/futures"
SYMBOL = os.getenv("ICON_MNQ_SYMBOL", "MNQZ6")
ET = ZoneInfo("America/New_York")


def ts_et(ms):
    if ms is None:
        return ""
    try:
        return datetime.fromtimestamp(float(ms) / 1000, tz=ZoneInfo("UTC")).astimezone(ET).strftime("%Y-%m-%d %H:%M:%S ET")
    except Exception:
        return str(ms)


async def main():
    api_key = os.getenv("MASSIVE_API_KEY")
    if not api_key:
        sys.exit("MASSIVE_API_KEY is not set.")

    print("=" * 64)
    print("THE ICON — MASSIVE LIVE MNQ CONNECTION")
    print("=" * 64)
    print(f"Endpoint : {WS_URL}")
    print(f"Contract : {SYMBOL}")
    print("Mode     : DATA ONLY — NO ORDERS / NO OPTION 2B CHANGES")
    print()

    async with websockets.connect(
        WS_URL,
        ping_interval=20,
        ping_timeout=20,
        close_timeout=10,
        max_size=None,
    ) as ws:
        connected = json.loads(await ws.recv())
        print("SERVER   :", connected)

        await ws.send(json.dumps({"action": "auth", "params": api_key}))

        authenticated = False
        while not authenticated:
            payload = json.loads(await ws.recv())
            for event in payload if isinstance(payload, list) else [payload]:
                print("AUTH     :", event)
                if event.get("status") == "auth_success":
                    authenticated = True
                    break
                if event.get("status") in {"auth_failed", "not_authorized"}:
                    sys.exit(f"Massive authentication failed: {event}")

        # Massive futures minute aggregate channel = AM.<ticker>
        channel = f"AM.{SYMBOL}"
        await ws.send(json.dumps({"action": "subscribe", "params": channel}))
        print(f"SUBSCRIBED: {channel}")
        print("Waiting for LIVE futures messages... Ctrl+C to stop.\n")

        async for raw in ws:
            payload = json.loads(raw)
            events = payload if isinstance(payload, list) else [payload]
            for event in events:
                ev = event.get("ev")
                if ev == "AM":
                    symbol = event.get("sym", event.get("symbol", SYMBOL))
                    start = event.get("s", event.get("start"))
                    o = event.get("o", event.get("open"))
                    h = event.get("h", event.get("high"))
                    l = event.get("l", event.get("low"))
                    c = event.get("c", event.get("close"))
                    v = event.get("v", event.get("volume"))
                    print(
                        f"LIVE AM | {symbol} | {ts_et(start)} | "
                        f"O {o} H {h} L {l} C {c} V {v}",
                        flush=True,
                    )
                elif ev == "status":
                    print("STATUS   :", event, flush=True)
                else:
                    print("EVENT    :", event, flush=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
