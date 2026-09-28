#!/usr/bin/env python3
"""Massive real-time Futures WebSocket latency probe.

Diagnostic only. Does not import or modify Icon strategy logic and does not
send orders or PickMyTrade alerts.
"""

import asyncio
import json
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

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
TZ = ZoneInfo("America/New_York")


def iso_et_from_ms(value):
    if value is None:
        return ""
    return datetime.fromtimestamp(float(value) / 1000.0, tz=timezone.utc).astimezone(TZ).isoformat()


def latency_seconds(value):
    if value is None:
        return None
    event_dt = datetime.fromtimestamp(float(value) / 1000.0, tz=timezone.utc)
    return (datetime.now(timezone.utc) - event_dt).total_seconds()


async def main():
    print("=" * 72)
    print("THE ICON — MASSIVE REAL-TIME FUTURES WEBSOCKET PROBE")
    print(f"Symbol: {SYMBOL}")
    print(f"Endpoint: {WS_URL}")
    print("Diagnostic only — no strategy changes, no PickMyTrade orders.")
    print("=" * 72)

    async with websockets.connect(WS_URL, ping_interval=20, ping_timeout=20) as ws:
        first = json.loads(await ws.recv())
        print("CONNECT:", first)

        await ws.send(json.dumps({"action": "auth", "params": API_KEY}))

        while True:
            raw = await ws.recv()
            messages = json.loads(raw)
            if not isinstance(messages, list):
                messages = [messages]

            authenticated = False
            for msg in messages:
                if msg.get("ev") == "status":
                    print("STATUS:", msg)
                    if msg.get("status") == "auth_success":
                        authenticated = True

            if authenticated:
                # T = individual trades; AM = per-minute aggregates.
                # Trades prove raw feed latency; AM proves minute-bar availability.
                params = f"T.{SYMBOL},AM.{SYMBOL}"
                await ws.send(json.dumps({"action": "subscribe", "params": params}))
                print("SUBSCRIBED:", params)
                break

        last_trade_print_second = None
        async for raw in ws:
            received_et = datetime.now(TZ)
            messages = json.loads(raw)
            if not isinstance(messages, list):
                messages = [messages]

            for msg in messages:
                ev = msg.get("ev")
                if ev == "status":
                    print("STATUS:", msg)
                    continue

                if ev == "T":
                    event_ms = msg.get("t")
                    lag = latency_seconds(event_ms)
                    # Avoid flooding terminal: print at most one trade sample/second.
                    sec = received_et.replace(microsecond=0)
                    if sec != last_trade_print_second:
                        last_trade_print_second = sec
                        print(
                            "TRADE | "
                            f"received={received_et.isoformat()} | "
                            f"event={iso_et_from_ms(event_ms)} | "
                            f"lag={lag:.3f}s | price={msg.get('p')}"
                            if lag is not None else
                            f"TRADE | received={received_et.isoformat()} | {msg}"
                        )

                elif ev == "AM":
                    # Futures AM uses the aggregate end timestamp when supplied.
                    event_ms = msg.get("e") or msg.get("s")
                    lag = latency_seconds(event_ms)
                    print(
                        "MINUTE | "
                        f"received={received_et.isoformat()} | "
                        f"bar_start={iso_et_from_ms(msg.get('s'))} | "
                        f"bar_end={iso_et_from_ms(msg.get('e'))} | "
                        f"lag_vs_end={lag:.3f}s | "
                        f"O={msg.get('o')} H={msg.get('h')} "
                        f"L={msg.get('l')} C={msg.get('c')} V={msg.get('v')}"
                        if lag is not None else
                        f"MINUTE | received={received_et.isoformat()} | {msg}"
                    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
