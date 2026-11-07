"""Experiments for the standings data path (milestone M1, ADR-004, REQ-N01, NFR-001, NFR-002).

Subcommands
-----------
parse      parse benchmark on synthetic bodies in separate processes (time and real peak memory)
cadence    simulate how old displayed data gets under the platform's 60 s cache for several polling strategies
live       measure real fetches (wire and decoded size, duration, cache headers) with the governed client
expiry     poll one contest right after each cache expiry and print how the headers evolve

Run from the repository root:  uv run python scripts/experiment_standings.py parse
"""

from __future__ import annotations

import argparse
import asyncio
import gzip
import json
import random
import statistics
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))


# ---------------------------------------------------------------------------------------------
# parse
# ---------------------------------------------------------------------------------------------
def peak_rss_mb() -> float:
    """Peak resident memory of this process in MB (Windows via ctypes, Unix via resource)."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = Counters()
        counters.cb = ctypes.sizeof(Counters)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        kernel32.K32GetProcessMemoryInfo.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        kernel32.K32GetProcessMemoryInfo.restype = wintypes.BOOL
        ok = kernel32.K32GetProcessMemoryInfo(
            kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb
        )
        if not ok:
            raise OSError(ctypes.get_last_error(), "K32GetProcessMemoryInfo failed")
        return counters.PeakWorkingSetSize / 1e6
    import resource

    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def parse_one(body_file: str, watched_count: int, repeats: int) -> dict[str, float]:
    """Run in a fresh process: the body is only read from disk, so the RSS increase is the parser's."""
    from tests.support.synth import handle_for

    from cpstands.sources.codeforces.parser import parse_standings

    body = Path(body_file).read_bytes()
    watched = frozenset(handle_for(i) for i in range(1, watched_count + 1))
    baseline = peak_rss_mb()
    timings = []
    for _ in range(repeats):
        started = time.perf_counter()
        snapshot = parse_standings(body, watched)
        timings.append(time.perf_counter() - started)
    return {
        "rows": snapshot.rows_scanned,
        "watched": len(snapshot.results),
        "decoded_mb": round(len(body) / 1e6, 2),
        "gzip_kb": round(len(gzip.compress(body, 6)) / 1e3, 1),
        "median_ms": round(statistics.median(timings) * 1000, 1),
        "max_ms": round(max(timings) * 1000, 1),
        "rss_before_mb": round(baseline, 1),
        "peak_rss_mb": round(peak_rss_mb(), 1),
    }


def cmd_parse(args: argparse.Namespace) -> None:
    import tempfile

    from tests.support.synth import synthesize_standings

    print(
        "rows  watched  decoded_MB  gzip_KB  median_ms  max_ms  rss_loaded_MB  peak_rss_MB  parser_adds_MB"
    )
    with tempfile.TemporaryDirectory() as tmp:
        for rows in (670, 3000, 9743, 20000):
            body_file = Path(tmp) / f"body_{rows}.json"
            body_file.write_bytes(synthesize_standings(rows))
            for watched in (20, 200, 2000):
                if watched > rows:
                    continue
                out = subprocess.run(  # noqa: S603
                    [
                        sys.executable,
                        __file__,
                        "parse-one",
                        "--body-file",
                        str(body_file),
                        "--watched",
                        str(watched),
                        "--repeats",
                        str(args.repeats),
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                    cwd=ROOT,
                )
                r = json.loads(out.stdout)
                print(
                    f"{r['rows']:5d} {r['watched']:8d} {r['decoded_mb']:10.2f} {r['gzip_kb']:8.1f} "
                    f"{r['median_ms']:10.1f} {r['max_ms']:7.1f} {r['rss_before_mb']:14.1f} "
                    f"{r['peak_rss_mb']:12.1f} {r['peak_rss_mb'] - r['rss_before_mb']:15.1f}"
                )


# ---------------------------------------------------------------------------------------------
# cadence
# ---------------------------------------------------------------------------------------------
TTL = 60.0


def simulate(
    strategy: str,
    interval: float,
    *,
    demand: str,
    rng: random.Random,
    horizon: float = 6 * 3600.0,
    processing: float = 3.0,
) -> list[float]:
    """Return sampled ages (seconds) of the data shown to users at random instants.

    Model: the platform proxy keeps one generation of the standings for TTL seconds. A new generation is
    created by the first request after the previous one expired. With ``demand='shared'`` other clients keep
    requesting, so generations start exactly every TTL seconds; with ``demand='ours'`` only our requests
    refresh the cache, so a generation starts at our first request after expiry.
    ``processing`` is the delay from fetch to the edited message (parse, queue, Telegram call).
    """
    offset = rng.uniform(0, TTL)  # unknown phase of the platform's refresh clock
    gen_start = offset
    shown_generation = None  # start time of the generation currently displayed
    shown_at = 0.0
    events: list[
        tuple[float, float]
    ] = []  # (time the user-visible message changes, generation start)
    t = rng.uniform(0, interval)
    next_expiry_known = None
    while t < horizon:
        # find the generation valid at time t
        if demand == "shared":
            gen = offset + TTL * ((t - offset) // TTL)
        else:
            while t >= gen_start + TTL:
                gen_start = t  # our request refreshes the expired cache
            gen = gen_start
        if shown_generation is None or gen > shown_generation:
            events.append((t + processing, gen))
            shown_generation = gen
        # schedule the next poll
        if strategy == "fixed":
            t += interval
        else:  # expiry-aligned: next poll just after the generation we just saw expires
            next_expiry_known = gen + TTL
            t = max(t + 1.0, next_expiry_known + 0.5)
    ages = []
    for _ in range(20000):
        user_time = rng.uniform(300.0, horizon - 300.0)
        shown = [g for (when, g) in events if when <= user_time]
        if shown:
            ages.append(user_time - shown[-1])
    _ = (shown_at, next_expiry_known)
    return ages


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(q * len(ordered)))]


def cmd_cadence(_args: argparse.Namespace) -> None:
    rng = random.Random(20261108)  # noqa: S311
    print(
        "Data age (s) of the displayed standings; processing delay 3 s; platform cache TTL 60 s\n"
    )
    print(
        f"{'demand':8} {'strategy':16} {'requests/min':>12} {'p50':>6} {'p95':>6} {'p99':>6} {'max':>6}"
    )
    for demand in ("shared", "ours"):
        for strategy, interval in (
            ("fixed", 15.0),
            ("fixed", 20.0),
            ("fixed", 30.0),
            ("fixed", 60.0),
            ("fixed", 90.0),
            ("expiry-aligned", 0.0),
        ):
            ages = simulate(strategy, interval, demand=demand, rng=rng)
            per_min = 60.0 / interval if strategy == "fixed" else 1.0
            label = f"{strategy} {int(interval)}s" if strategy == "fixed" else strategy
            print(
                f"{demand:8} {label:16} {per_min:12.1f} {percentile(ages, 0.5):6.1f} "
                f"{percentile(ages, 0.95):6.1f} {percentile(ages, 0.99):6.1f} {max(ages):6.1f}"
            )


# ---------------------------------------------------------------------------------------------
# live
# ---------------------------------------------------------------------------------------------
def _client():
    from cpstands.sources.codeforces.client import ClientConfig, CodeforcesClient

    return CodeforcesClient(
        ClientConfig(
            user_agent="cpstands-experiment/0.1 (+https://github.com/menarzullayev/cpstands)"
        )
    )


async def live(contests: list[int]) -> None:
    from cpstands.sources.codeforces.parser import parse_contest_list, parse_standings

    client = _client()
    try:
        raw = await client.fetch("contest.list", {"gym": "false"})
        contests_list, skipped = parse_contest_list(raw.body)
        active = [c for c in contests_list if c.phase.is_active]
        print(
            f"contest.list: wire={raw.meta.wire_bytes} B decoded={raw.meta.decoded_bytes} B "
            f"time={raw.meta.duration_s:.2f}s contests={len(contests_list)} skipped={skipped} "
            f"active_now={[c.external_id for c in active]} cache={raw.meta.cache_status}"
        )
        for contest_id in contests:
            raw = await client.fetch("contest.standings", {"contestId": str(contest_id)})
            started = time.perf_counter()
            snapshot = parse_standings(raw.body, frozenset({"nobody"}))
            parse_ms = (time.perf_counter() - started) * 1000
            m = raw.meta
            ratio = m.decoded_bytes / max(1, m.wire_bytes)
            print(
                f"standings {contest_id}: rows={snapshot.rows_scanned} wire={m.wire_bytes / 1e3:.0f} KB "
                f"decoded={m.decoded_bytes / 1e6:.2f} MB ratio={ratio:.0f}x fetch={m.duration_s:.2f}s "
                f"parse={parse_ms:.0f}ms cache={m.cache_status} expires={m.expires_at}"
            )
    finally:
        await client.aclose()


def cmd_live(args: argparse.Namespace) -> None:
    asyncio.run(live([int(x) for x in args.contests.split(",")]))


async def expiry(contest_id: int, cycles: int) -> None:
    client = _client()
    try:
        for cycle in range(cycles):
            raw = await client.fetch("contest.standings", {"contestId": str(contest_id)})
            m = raw.meta
            now = datetime.now(UTC)
            remaining = (m.expires_at - now).total_seconds() if m.expires_at else None
            print(
                f"cycle {cycle}: at {now:%H:%M:%S} cache={m.cache_status} expires={m.expires_at:%H:%M:%S} "
                f"remaining={remaining:.1f}s wire={m.wire_bytes / 1e3:.0f} KB"
                if m.expires_at
                else f"cycle {cycle}: no Expires header cache={m.cache_status}",
                flush=True,
            )
            if m.expires_at is None or cycle == cycles - 1:
                continue
            wait = max(0.0, (m.expires_at - datetime.now(UTC)).total_seconds()) + 1.0
            await asyncio.sleep(wait)
    finally:
        await client.aclose()


def cmd_expiry(args: argparse.Namespace) -> None:
    asyncio.run(expiry(args.contest, args.cycles))


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("parse")
    p.add_argument("--repeats", type=int, default=5)
    p.set_defaults(func=cmd_parse)
    p1 = sub.add_parser("parse-one")
    p1.add_argument("--body-file", required=True)
    p1.add_argument("--watched", type=int, required=True)
    p1.add_argument("--repeats", type=int, default=5)
    p1.set_defaults(func=lambda a: print(json.dumps(parse_one(a.body_file, a.watched, a.repeats))))
    sub.add_parser("cadence").set_defaults(func=cmd_cadence)
    lv = sub.add_parser("live")
    lv.add_argument("--contests", default="2249,2250,2260")
    lv.set_defaults(func=cmd_live)
    ex = sub.add_parser("expiry")
    ex.add_argument("--contest", type=int, default=2249)
    ex.add_argument("--cycles", type=int, default=4)
    ex.set_defaults(func=cmd_expiry)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
