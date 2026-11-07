"""Create anonymized, trimmed test fixtures from raw Codeforces responses.

Raw responses live in the git-ignored ``fixtures/raw/`` directory (recorded with ``scripts/record_fixtures.py``).
Handles are replaced by deterministic pseudonyms (``user_00001`` ...), team and room details are dropped, and the
rows are cut to a few hundred so the committed files stay small. Nothing personal reaches the repository.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "fixtures" / "raw"
OUT = ROOT / "tests" / "fixtures"

# (raw file, output name, rows to keep)
STANDINGS = [
    ("st_2249.json", "standings_small.json", 120),
    ("st_2250.json", "standings_medium.json", 300),
    ("st_2260.json", "standings_shape.json", 40),
]


def anonymize_standings(document: dict, keep: int) -> dict:
    rows = document["result"]["rows"][:keep]
    mapping: dict[str, str] = {}
    for row in rows:
        party = row["party"]
        for member in party["members"]:
            real = member["handle"]
            mapping.setdefault(real, f"user_{len(mapping) + 1:05d}")
            member["handle"] = mapping[real]
        party.pop("teamName", None)
        party.pop("teamId", None)
        party.pop("room", None)
        party["participantId"] = 0
    document["result"]["rows"] = rows
    return document


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for raw_name, out_name, keep in STANDINGS:
        source = RAW / raw_name
        if not source.exists():
            raise SystemExit(f"missing raw file {source}; run scripts/record_fixtures.py first")
        document = anonymize_standings(json.loads(source.read_text(encoding="utf-8")), keep)
        (OUT / out_name).write_text(json.dumps(document, separators=(",", ":")), encoding="utf-8")
        print(f"{out_name}: {len(document['result']['rows'])} rows")
    listing = json.loads((RAW / "contest_list.json").read_text(encoding="utf-8"))
    before = [c for c in listing["result"] if c["phase"] == "BEFORE"][:4]
    finished = [c for c in listing["result"] if c["phase"] == "FINISHED"][:8]
    listing["result"] = before + finished
    (OUT / "contest_list.json").write_text(
        json.dumps(listing, separators=(",", ":")), encoding="utf-8"
    )
    print(f"contest_list.json: {len(listing['result'])} contests")


if __name__ == "__main__":
    main()
