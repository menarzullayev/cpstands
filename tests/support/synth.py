"""Helpers that build Codeforces-shaped payloads for tests and experiments."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def load_fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def handle_for(index: int) -> str:
    return f"user_{index:05d}"


def synthesize_standings(
    rows: int, *, template: str = "standings_shape.json", teams: int = 0
) -> bytes:
    """Build a standings body with ``rows`` rows by cycling the rows of a recorded fixture.

    Handles are ``user_00001`` ... so tests know exactly which handles exist. The first ``teams`` rows
    become two-member team rows.
    """
    document: dict[str, Any] = json.loads(load_fixture(template))
    templates = document["result"]["rows"]
    built: list[dict[str, Any]] = []
    for index in range(rows):
        row = copy.deepcopy(templates[index % len(templates)])
        row["rank"] = index + 1
        row["party"]["members"] = [{"handle": handle_for(index + 1)}]
        if index < teams:
            row["party"]["members"].append({"handle": f"teammate_{index:05d}"})
        built.append(row)
    document["result"]["rows"] = built
    return json.dumps(document, separators=(",", ":")).encode()
