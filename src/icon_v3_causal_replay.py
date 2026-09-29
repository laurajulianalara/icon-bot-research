#!/usr/bin/env python3
"""
ICON V3 CAUSAL REPLAY ENGINE
============================
Purpose: strategy-agnostic, bar-by-bar replay with hard causality guards.

NON-NEGOTIABLE DESIGN:
- Strategy code never receives the source dataframe.
- Strategy receives only an immutable CausalContext containing bars whose
  timestamps are <= the current clock.
- Decisions are append-only/immutable.
- Future outcome scoring is NOT implemented here. Selection and outcome
  measurement must remain separate.
- The same Strategy.on_bar(ctx) interface is intended for historical replay
  and the eventual live websocket runner.

This file contains NO Option 2B imports, thresholds, candidate rules, or
selection/finalization logic.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Optional, Protocol, Sequence


@dataclass(frozen=True, slots=True)
class Bar:
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

    def __post_init__(self) -> None:
        if self.high < max(self.open, self.close, self.low):
            raise ValueError(f"invalid OHLC high at {self.ts}")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError(f"invalid OHLC low at {self.ts}")


@dataclass(frozen=True, slots=True)
class Decision:
    ts: datetime
    action: str  # e.g. LONG, SHORT, NONE
    strategy: str
    reason: str = ""
    entry: Optional[float] = None
    stop: Optional[float] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def canonical(self) -> dict[str, Any]:
        return {
            "ts": self.ts.isoformat(),
            "action": self.action,
            "strategy": self.strategy,
            "reason": self.reason,
            "entry": self.entry,
            "stop": self.stop,
            "metadata": dict(sorted(self.metadata.items())),
        }


@dataclass(frozen=True, slots=True)
class CausalContext:
    """The ONLY market-data object strategy code receives."""
    now: datetime
    current: Bar
    history: tuple[Bar, ...]
    state: Mapping[str, Any]

    def __post_init__(self) -> None:
        if self.current.ts != self.now:
            raise AssertionError("CAUSALITY FAIL: current bar timestamp != engine clock")
        if not self.history:
            raise AssertionError("CAUSALITY FAIL: empty history")
        if self.history[-1] != self.current:
            raise AssertionError("CAUSALITY FAIL: current bar must be last history bar")
        if any(b.ts > self.now for b in self.history):
            raise AssertionError("CAUSALITY FAIL: future bar exposed to strategy")
        if any(a.ts >= b.ts for a, b in zip(self.history, self.history[1:])):
            raise AssertionError("CAUSALITY FAIL: history is not strictly chronological")


class Strategy(Protocol):
    name: str

    def on_bar(self, ctx: CausalContext) -> Optional[Decision]:
        ...


class NullStrategy:
    """Safe placeholder. Strategy research starts only after tester validation."""
    name = "NULL_NO_STRATEGY"

    def on_bar(self, ctx: CausalContext) -> Optional[Decision]:
        return None


class CausalReplay:
    def __init__(self, strategy: Strategy):
        self.strategy = strategy
        self._history: list[Bar] = []
        self._state: dict[str, Any] = {}
        self._decisions: list[Decision] = []
        self._last_ts: Optional[datetime] = None

    @property
    def decisions(self) -> tuple[Decision, ...]:
        return tuple(self._decisions)

    def push_closed_bar(self, bar: Bar) -> Optional[Decision]:
        # A live feed must only call this after the bar is closed.
        if self._last_ts is not None and bar.ts <= self._last_ts:
            raise AssertionError(
                f"CAUSALITY FAIL: non-increasing/duplicate bar {bar.ts} after {self._last_ts}"
            )

        self._history.append(bar)
        self._last_ts = bar.ts

        ctx = CausalContext(
            now=bar.ts,
            current=bar,
            history=tuple(self._history),  # immutable snapshot
            state=MappingProxyType(self._state),
        )
        decision = self.strategy.on_bar(ctx)

        if decision is not None:
            if decision.ts != bar.ts:
                raise AssertionError(
                    "CAUSALITY FAIL: decision timestamp must equal current closed-bar timestamp"
                )
            if self._decisions and decision.ts < self._decisions[-1].ts:
                raise AssertionError("CAUSALITY FAIL: decision log moved backward in time")
            # Freeze metadata so later code cannot mutate an old decision.
            frozen = Decision(
                ts=decision.ts,
                action=decision.action,
                strategy=decision.strategy,
                reason=decision.reason,
                entry=decision.entry,
                stop=decision.stop,
                metadata=MappingProxyType(dict(decision.metadata)),
            )
            self._decisions.append(frozen)
            return frozen
        return None


def _parse_ts(value: str) -> datetime:
    value = value.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def load_csv(path: Path) -> list[Bar]:
    """Load generic OHLC(V) CSV. Timestamp column may be timestamp/ts/time/datetime."""
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("CSV has no header")
        lower = {c.lower(): c for c in reader.fieldnames}
        ts_col = next((lower[k] for k in ("timestamp", "ts", "time", "datetime") if k in lower), None)
        if ts_col is None:
            raise ValueError("CSV needs timestamp/ts/time/datetime column")
        required = {}
        for k in ("open", "high", "low", "close"):
            if k not in lower:
                raise ValueError(f"CSV missing {k} column")
            required[k] = lower[k]
        vol_col = lower.get("volume")

        bars = [
            Bar(
                ts=_parse_ts(row[ts_col]),
                open=float(row[required["open"]]),
                high=float(row[required["high"]]),
                low=float(row[required["low"]]),
                close=float(row[required["close"]]),
                volume=float(row[vol_col]) if vol_col and row.get(vol_col) not in (None, "") else 0.0,
            )
            for row in reader
        ]

    if any(a.ts >= b.ts for a, b in zip(bars, bars[1:])):
        raise AssertionError("INPUT FAIL: bars must be unique and strictly chronological")
    return bars


def replay(bars: Iterable[Bar], strategy: Strategy) -> tuple[Decision, ...]:
    engine = CausalReplay(strategy)
    for bar in bars:
        engine.push_closed_bar(bar)
    return engine.decisions


def decision_hash(decisions: Sequence[Decision]) -> str:
    payload = "\n".join(
        json.dumps(d.canonical(), sort_keys=True, separators=(",", ":"))
        for d in decisions
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def assert_chunk_parity(bars: Sequence[Bar], strategy_factory, chunk_size: int = 17) -> None:
    """Batch sequential feed vs simulated websocket chunk arrivals must be identical."""
    expected = replay(bars, strategy_factory())

    live = CausalReplay(strategy_factory())
    for start in range(0, len(bars), chunk_size):
        # Chunking changes delivery grouping, never bar order or information available.
        for bar in bars[start:start + chunk_size]:
            live.push_closed_bar(bar)

    actual = live.decisions
    if [d.canonical() for d in expected] != [d.canonical() for d in actual]:
        raise AssertionError("PARITY FAIL: sequential replay != simulated live stream")
    if decision_hash(expected) != decision_hash(actual):
        raise AssertionError("PARITY FAIL: decision hashes differ")


class _ParityProbeStrategy:
    """
    Deterministic tester ONLY, not a trading strategy.
    Emits a marker every 11th bar using current/past data so parity is non-trivial.
    """
    name = "_CAUSAL_PARITY_PROBE"

    def __init__(self):
        self.n = 0

    def on_bar(self, ctx: CausalContext) -> Optional[Decision]:
        self.n += 1
        if self.n % 11:
            return None
        direction = "LONG" if ctx.current.close >= ctx.history[-2].close else "SHORT"
        return Decision(
            ts=ctx.now,
            action=direction,
            strategy=self.name,
            reason="parity_probe_only",
            entry=ctx.current.close,
            metadata={"bars_seen": len(ctx.history)},
        )


def run_self_test(bars: Optional[Sequence[Bar]] = None) -> None:
    # Synthetic bars ensure the engine can validate itself without market files.
    if bars is None:
        base = datetime.fromisoformat("2026-01-02T09:30:00-05:00")
        from datetime import timedelta
        bars = []
        px = 20000.0
        for i in range(100):
            o = px
            c = o + (0.25 if i % 3 else -0.25)
            bars.append(
                Bar(
                    ts=base + timedelta(minutes=i),
                    open=o,
                    high=max(o, c) + 0.25,
                    low=min(o, c) - 0.25,
                    close=c,
                    volume=100 + i,
                )
            )
            px = c

    # 1) Strict chronology.
    if any(a.ts >= b.ts for a, b in zip(bars, bars[1:])):
        raise AssertionError("SELF-TEST FAIL: input chronology")

    # 2) Replay/live delivery parity.
    assert_chunk_parity(bars, _ParityProbeStrategy, chunk_size=1)
    assert_chunk_parity(bars, _ParityProbeStrategy, chunk_size=7)
    assert_chunk_parity(bars, _ParityProbeStrategy, chunk_size=31)

    # 3) Duplicate/out-of-order bars must fail closed.
    if len(bars) >= 2:
        e = CausalReplay(NullStrategy())
        e.push_closed_bar(bars[0])
        try:
            e.push_closed_bar(bars[0])
        except AssertionError:
            pass
        else:
            raise AssertionError("SELF-TEST FAIL: duplicate bar was accepted")

    print("ICON V3 CAUSAL ENGINE: PASS")
    print("FUTURE BAR EXPOSURE: 0 by interface")
    print("REPLAY / SIMULATED-LIVE PARITY: 100.000%")
    print(f"BARS TESTED: {len(bars):,}")
    print("STRATEGY: NONE (tester only)")


def main() -> None:
    p = argparse.ArgumentParser(description="ICON V3 causal replay/parity tester")
    p.add_argument("--csv", type=Path, help="Optional OHLC(V) CSV for real-data parity test")
    p.add_argument("--self-test", action="store_true", help="Run causality/parity validation")
    args = p.parse_args()

    bars = load_csv(args.csv) if args.csv else None
    if args.self_test or args.csv:
        run_self_test(bars)
    else:
        p.print_help()


if __name__ == "__main__":
    main()
