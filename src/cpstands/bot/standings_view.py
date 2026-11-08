"""The standings table as a Rich Message: HTML table, paged by rows and by problem columns.

Telegram allows at most 20 table columns, so four are fixed (rank, who, score, penalty) and the
problems are shown ``cols`` (8, 12 or 16) at a time; a contest with more problems gets a column
switcher. A chat that follows handles can switch between the friends view (only the followed
handles, with their real ranks) and the full table.
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import datetime

from aiogram.types import InlineKeyboardMarkup

from cpstands.bot.keyboards import app_button, button
from cpstands.domain.contest import (
    ContestPhase,
    FullStandings,
    ProblemResult,
    ProblemStatus,
    StandingRow,
    handle_key,
)
from cpstands.i18n import Translator
from cpstands.services import timezone as tzs

ROWS_PER_PAGE = 25
PROBLEM_COLUMNS = 16
NAME_MAX = 18
CALLBACK_PREFIX = "st:"
NOOP = "st:noop"
VIEW_TOKEN = {"friends": "f", "all": "a"}
TOKEN_VIEW = {"f": "friends", "a": "all"}


@dataclass(frozen=True, slots=True)
class ViewContext:
    """How one chat wants to see a table: which rows, how many problem columns."""

    view: str = "all"  # "friends" or "all"
    friends: frozenset[str] = frozenset()
    cols: int = PROBLEM_COLUMNS

    @property
    def has_friends(self) -> bool:
        return bool(self.friends)


def resolve_view(preferred: str | None, friends: frozenset[str]) -> str:
    """``auto`` (or a missing choice) means friends when the chat has any, else everyone."""
    if preferred in {"friends", "all"}:
        return "all" if preferred == "friends" and not friends else str(preferred)
    return "friends" if friends else "all"


def visible_rows(standings: FullStandings, ctx: ViewContext) -> tuple[StandingRow, ...]:
    if ctx.view != "friends":
        return standings.rows
    return tuple(
        row for row in standings.rows if any(handle_key(h) in ctx.friends for h in row.handles)
    )


def row_pages(total_rows: int) -> int:
    return max(1, -(-total_rows // ROWS_PER_PAGE))


def column_ranges(problem_count: int, cols: int = PROBLEM_COLUMNS) -> list[tuple[int, int]]:
    """Half-open ``(start, end)`` ranges of problem indexes, one per column page."""
    if problem_count <= cols:
        return [(0, problem_count)]
    return [(start, min(start + cols, problem_count)) for start in range(0, problem_count, cols)]


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
    ctx: ViewContext | None = None,
) -> str:
    """Build the HTML of one page; page numbers are 0-based and clamped to the valid range."""
    ctx = ctx or ViewContext()
    all_rows = visible_rows(standings, ctx)
    total = len(all_rows)
    row_page = min(max(row_page, 0), row_pages(total) - 1)
    ranges = column_ranges(len(standings.problems), ctx.cols)
    start, end = ranges[min(max(col_page, 0), len(ranges) - 1)]
    first = row_page * ROWS_PER_PAGE
    rows = all_rows[first : first + ROWS_PER_PAGE]
    icpc = standings.contest.kind == "ICPC"

    head = ["#", "Who", "=", "Pen", *(p.index for p in standings.problems[start:end])]
    header = "<tr>" + "".join(f"<th>{html.escape(h, quote=False)}</th>" for h in head) + "</tr>"
    body = "".join(_row_html(r, range(start, end), icpc=icpc) for r in rows)
    zone = time_zone if time_zone and tzs.is_valid_zone(time_zone) else "UTC"
    status = say.rich(
        "standings-status",
        phase=_phase_key(standings.contest.phase),
        count=total,
        view=ctx.view,
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
    empty = ""
    if not rows:
        if ctx.view == "friends":
            empty = f"<p>{say.rich('standings-no-friends')}</p>"
        else:
            empty = f"<p>{say.rich('standings-empty')}</p>"
    return f"<h1>{name}</h1><p>{status}</p>{table}{empty}<blockquote>{footer}</blockquote>"


def _clock(moment: datetime, zone: str) -> str:
    return tzs.local_time_text(zone, moment)


def callback(
    contest_id: int, row_page: int, col_page: int, view: str = "all", *, refresh: bool = False
) -> str:
    token = VIEW_TOKEN.get(view, "a")
    return f"{CALLBACK_PREFIX}{contest_id}:{row_page}:{col_page}:{token}" + (
        ":r" if refresh else ""
    )


def keyboard(
    standings: FullStandings,
    row_page: int,
    col_page: int,
    say: Translator,
    *,
    icons: bool,
    ctx: ViewContext | None = None,
) -> InlineKeyboardMarkup:
    ctx = ctx or ViewContext()
    cid = standings.contest.external_id
    view = ctx.view
    pages = row_pages(len(visible_rows(standings, ctx)))
    row_page = min(max(row_page, 0), pages - 1)
    ranges = column_ranges(len(standings.problems), ctx.cols)
    col_page = min(max(col_page, 0), len(ranges) - 1)
    rows: list[list[object]] = []
    if ctx.has_friends:
        rows.append(
            [
                button(
                    say("button-view-friends"),
                    callback(cid, 0, col_page, "friends"),
                    emoji="👥",
                    style="primary" if view == "friends" else None,
                    icons=icons,
                ),
                button(
                    say("button-view-all"),
                    callback(cid, 0, col_page, "all"),
                    emoji="🌍",
                    style="primary" if view == "all" else None,
                    icons=icons,
                ),
            ]
        )
    if pages > 1:
        rows.append(
            [
                button("1", callback(cid, 0, col_page, view), emoji="⏮", icons=icons),
                button(
                    str(max(row_page, 1)),
                    callback(cid, max(row_page - 1, 0), col_page, view),
                    emoji="◀",
                    icons=icons,
                ),
                button(f"{row_page + 1} / {pages}", NOOP),
                button(
                    str(min(row_page + 2, pages)),
                    callback(cid, min(row_page + 1, pages - 1), col_page, view),
                    emoji="▶",
                    icons=icons,
                ),
                button(
                    str(pages), callback(cid, pages - 1, col_page, view), emoji="⏭", icons=icons
                ),
            ]
        )
    if len(ranges) > 1:
        rows.append(
            [
                button(
                    f"{standings.problems[a].index}–{standings.problems[b - 1].index}",  # noqa: RUF001
                    callback(cid, row_page, i, view),
                    style="primary" if i == col_page else None,
                )
                for i, (a, b) in enumerate(ranges)
            ]
        )
    rows.append(
        [
            button(
                say("button-refresh"),
                callback(cid, row_page, col_page, view, refresh=True),
                emoji="🔁",
                icons=icons,
            ),
            app_button(say, f"standings_{cid}", icons=icons),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)  # type: ignore[arg-type]
