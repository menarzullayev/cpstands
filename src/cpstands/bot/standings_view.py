"""The standings table as a Rich Message: HTML table, paged by rows and by problem columns.

Telegram allows at most 20 table columns, so four are fixed (rank, who, score, penalty) and the
problems are shown 16 at a time; a contest with more problems gets a column switcher.
"""

from __future__ import annotations

import html
from datetime import datetime

from aiogram.types import InlineKeyboardMarkup

from cpstands.bot.keyboards import button
from cpstands.domain.contest import (
    ContestPhase,
    FullStandings,
    ProblemResult,
    ProblemStatus,
    StandingRow,
)
from cpstands.i18n import Translator
from cpstands.services import timezone as tzs

ROWS_PER_PAGE = 25
PROBLEM_COLUMNS = 16
NAME_MAX = 18
CALLBACK_PREFIX = "st:"
NOOP = "st:noop"


def row_pages(total_rows: int) -> int:
    return max(1, -(-total_rows // ROWS_PER_PAGE))


def column_ranges(problem_count: int) -> list[tuple[int, int]]:
    """Half-open ``(start, end)`` ranges of problem indexes, one per column page."""
    if problem_count <= PROBLEM_COLUMNS:
        return [(0, problem_count)]
    return [
        (start, min(start + PROBLEM_COLUMNS, problem_count))
        for start in range(0, problem_count, PROBLEM_COLUMNS)
    ]


def _clip(name: str) -> str:
    return name if len(name) <= NAME_MAX else name[: NAME_MAX - 1] + "…"


def _hm(seconds: int | None) -> str:
    if seconds is None:
        return ""
    return f"{seconds // 3600}:{seconds % 3600 // 60:02d}"


def _number(value: float) -> str:
    return f"{value:g}" if value != int(value) else str(int(value))


def cell(result: ProblemResult, *, icpc: bool) -> str:
    """One problem cell: ``+2 3:02`` solved after 2 wrong tries, ``-3`` unsolved, blank untried."""
    if result.status in {ProblemStatus.ACCEPTED, ProblemStatus.PROVISIONAL}:
        mark = "+" if icpc else _number(result.points)
        wrong = str(result.rejected_attempts) if icpc and result.rejected_attempts else ""
        text = f"{mark}{wrong}"
        if icpc and result.time_s is not None:
            text += f" {_hm(result.time_s)}"
        return text + ("*" if result.status is ProblemStatus.PROVISIONAL else "")
    if result.status is ProblemStatus.REJECTED:
        return f"-{result.rejected_attempts}"
    return ""


def _phase_key(phase: ContestPhase) -> str:
    if phase.is_active:
        return "running"
    return "before" if phase is ContestPhase.BEFORE else "finished"


def _row_html(row: StandingRow, columns: range, *, icpc: bool) -> str:
    cells = [
        str(row.rank),
        html.escape(_clip(row.who), quote=False),
        _number(row.points),
        str(row.penalty),
        *(cell(row.problems[i], icpc=icpc) if i < len(row.problems) else "" for i in columns),
    ]
    return "<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"


def render(
    standings: FullStandings,
    row_page: int,
    col_page: int,
    say: Translator,
    *,
    time_zone: str | None,
) -> str:
    """Build the HTML of one page; page numbers are 0-based and clamped to the valid range."""
    total = len(standings.rows)
    row_page = min(max(row_page, 0), row_pages(total) - 1)
    ranges = column_ranges(len(standings.problems))
    start, end = ranges[min(max(col_page, 0), len(ranges) - 1)]
    first = row_page * ROWS_PER_PAGE
    rows = standings.rows[first : first + ROWS_PER_PAGE]
    icpc = standings.contest.kind == "ICPC"

    head = ["#", "Who", "=", "Pen", *(p.index for p in standings.problems[start:end])]
    header = "<tr>" + "".join(f"<th>{html.escape(h, quote=False)}</th>" for h in head) + "</tr>"
    body = "".join(_row_html(r, range(start, end), icpc=icpc) for r in rows)
    zone = time_zone if time_zone and tzs.is_valid_zone(time_zone) else "UTC"
    status = say.rich(
        "standings-status",
        phase=_phase_key(standings.contest.phase),
        count=total,
        time=_clock(standings.fetched_at, zone),
    )
    footer = say.rich(
        "standings-footer",
        first=first + 1 if rows else 0,
        last=first + len(rows),
        total=total,
        from_problem=standings.problems[start].index if standings.problems else "-",
        to_problem=standings.problems[end - 1].index if standings.problems else "-",
    )
    name = html.escape(standings.contest.name, quote=False)
    table = f"<table>{header}{body}</table>" if rows else ""
    empty = f"<p>{say.rich('standings-empty')}</p>" if not rows else ""
    return f"<h1>{name}</h1><p>{status}</p>{table}{empty}<blockquote>{footer}</blockquote>"


def _clock(moment: datetime, zone: str) -> str:
    return tzs.local_time_text(zone, moment)


def callback(contest_id: int, row_page: int, col_page: int, *, refresh: bool = False) -> str:
    return f"{CALLBACK_PREFIX}{contest_id}:{row_page}:{col_page}" + (":r" if refresh else "")


def keyboard(
    standings: FullStandings,
    row_page: int,
    col_page: int,
    say: Translator,
    *,
    icons: bool,
) -> InlineKeyboardMarkup:
    cid = standings.contest.external_id
    pages = row_pages(len(standings.rows))
    row_page = min(max(row_page, 0), pages - 1)
    ranges = column_ranges(len(standings.problems))
    col_page = min(max(col_page, 0), len(ranges) - 1)
    rows: list[list[object]] = []
    if pages > 1:
        rows.append(
            [
                button("⏮", callback(cid, 0, col_page)),
                button("◀", callback(cid, max(row_page - 1, 0), col_page)),
                button(f"{row_page + 1} / {pages}", NOOP),
                button("▶", callback(cid, min(row_page + 1, pages - 1), col_page)),
                button("⏭", callback(cid, pages - 1, col_page)),
            ]
        )
    if len(ranges) > 1:
        rows.append(
            [
                button(
                    f"{standings.problems[a].index}–{standings.problems[b - 1].index}",  # noqa: RUF001
                    callback(cid, row_page, i),
                    style="primary" if i == col_page else None,
                )
                for i, (a, b) in enumerate(ranges)
            ]
        )
    rows.append(
        [
            button(
                say("button-refresh"),
                callback(cid, row_page, col_page, refresh=True),
                emoji="🔁",
                icons=icons,
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)  # type: ignore[arg-type]
