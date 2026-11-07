"""Record raw Codeforces responses into the git-ignored ``fixtures/raw/`` directory.

Uses the same rate-governed client as the application (one request per two seconds). Afterwards run
``python scripts/make_fixtures.py`` to produce the anonymized, trimmed fixtures that are committed.

Usage:  uv run python scripts/record_fixtures.py [--contests 2249,2250,2260]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from cpstands.sources.codeforces.client import ClientConfig, CodeforcesClient  # noqa: E402

RAW = ROOT / "fixtures" / "raw"


async def record(contests: list[int]) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    client = CodeforcesClient(
        ClientConfig(user_agent="cpstands-fixture-recorder/0.1 (+https://github.com/menarzullayev/cpstands)")
    )
    try:
        listing = await client.fetch("contest.list", {"gym": "false"})
        (RAW / "contest_list.json").write_bytes(listing.body)
        print(f"contest_list.json: {listing.meta.decoded_bytes} bytes")
        for contest_id in contests:
            raw = await client.fetch("contest.standings", {"contestId": str(contest_id)})
            (RAW / f"st_{contest_id}.json").write_bytes(raw.body)
            print(
                f"st_{contest_id}.json: {raw.meta.decoded_bytes} bytes "
                f"(wire {raw.meta.wire_bytes}, cache {raw.meta.cache_status})"
            )
    finally:
        await client.aclose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contests", default="2249,2250,2260")
    args = parser.parse_args()
    asyncio.run(record([int(x) for x in args.contests.split(",")]))


if __name__ == "__main__":
    main()
