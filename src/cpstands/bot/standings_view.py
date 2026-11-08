"""The standings table as a Rich Message: HTML table, paged by rows and by problem columns.

Telegram allows at most 20 table columns, so four are fixed (rank, who, score, penalty) and the
problems are shown ``cols`` (8, 12 or 16) at a time; a contest with more problems gets a column
switcher. A chat that follows handles can switch between the friends view (only the followed
handles, with their real ranks) and the full table.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import datetime

from aiogram.types import InlineKeyboardMarkup

from cpstands import platforms
from cpstands.bot.keyboards import app_button, button, link
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
from cpstands.ui.emoji import custom_emoji_id

ROWS_PER_PAGE = 25
PROBLEM_COLUMNS = 16
NAME_MAX = 18
CALLBACK_PREFIX = "st:"
NOOP = "st:noop"
VIEW_TOKEN = {"friends": "f", "all": "a"}
TOKEN_VIEW = {"f": "friends", "a": "all"}
STYLES = ("emoji", "classic")  # owner decision 2026-11-08: emoji by default
# Telegram keeps only the first 100 custom emoji of a message and shows the rest as plain
# emoji (measured 2026-11-08: 201 sent, 100 kept). So solved and failed cells use plain 🟢 🔴,
# and only the few special marks (medals, ⚡ first solves) are custom.
MAX_CUSTOM_EMOJI = 100
PLAIN_CELL_EMOJI = frozenset({"🟢", "🔴"})  # plain on purpose, see above
_TAG_RE = re.compile(r'<tg-emoji emoji-id="\d+">(.*?)</tg-emoji>')
MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}


@dataclass(frozen=True, slots=True)
class ViewContext:
    """How one chat wants to see a table: which rows, how many problem columns."""

    view: str = "all"  # "friends" or "all"
    friends: frozenset[str] = frozenset()
    cols: int = PROBLEM_COLUMNS
    style: str = "emoji"  # "emoji" or "classic"

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


def _hm(seconds: int | None, *, padded: bool = False) -> str:
    if seconds is None:
        return ""
    hours = f"{seconds // 3600:02d}" if padded else str(seconds // 3600)
    return f"{hours}:{seconds % 3600 // 60:02d}"


def _number(value: float) -> str:
    return f"{value:g}" if value != int(value) else str(int(value))


def _emoji(emoji: str) -> str:
    found = custom_emoji_id(emoji)
    return f'<tg-emoji emoji-id="{found}">{emoji}</tg-emoji>' if found else emoji


_SOLVED = {ProblemStatus.ACCEPTED, ProblemStatus.PROVISIONAL}


def first_solves(standings: FullStandings) -> list[int | None]:
    """The earliest solve time of each problem over the whole table (not just one page)."""
    best: list[int | None] = [None] * len(standings.problems)
    for row in standings.rows:
        for i, result in enumerate(row.problems[: len(best)]):
            if result.status in _SOLVED and result.time_s is not None:
                current = best[i]
                if current is None or result.time_s < current:
                    best[i] = result.time_s
    return best


def styled_cell(result: ProblemResult, *, icpc: bool, padded: bool, style: str, first: bool) -> str:
    """A cell in the ``emoji`` style (🟢 solved, ⚡ first solve, 🔴 tried) or ``classic`` one
    (attempts raised, the first solve marked)."""
    if style not in STYLES:
        return cell(result, icpc=icpc, padded=padded)
    if result.status in _SOLVED:
        tries = f"<sup>{result.rejected_attempts}</sup>" if result.rejected_attempts else ""
        star = "*" if result.status is ProblemStatus.PROVISIONAL else ""
        value = _hm(result.time_s, padded=padded) if icpc else _number(result.points)
        if not icpc:
            tries = ""
        if style == "emoji":
            if first:
                return f"{_emoji('⚡')}{tries} <b>{value}</b>{star}"
            return f"{'🟢'}{tries} {value}{star}"
        text = f"+{tries} {value}{star}" if icpc else f"{value}{star}"
        return f"<mark>{text}</mark>" if first else text
    if result.status is ProblemStatus.REJECTED:
        if style == "emoji":
            return f"{'🔴'}<sup>{result.rejected_attempts}</sup>"
        return f"-{result.rejected_attempts}"
    return ""


def cell(result: ProblemResult, *, icpc: bool, padded: bool = False) -> str:
    """One problem cell: ``+2 3:02`` solved after 2 wrong tries, ``-3`` unsolved, blank untried."""
    if result.status in {ProblemStatus.ACCEPTED, ProblemStatus.PROVISIONAL}:
        mark = "+" if icpc else _number(result.points)
        wrong = str(result.rejected_attempts) if icpc and result.rejected_attempts else ""
        text = f"{mark}{wrong}"
        if icpc and result.time_s is not None:
            text += f" {_hm(result.time_s, padded=padded)}"
        return text + ("*" if result.status is ProblemStatus.PROVISIONAL else "")
    if result.status is ProblemStatus.REJECTED:
        return f"-{result.rejected_attempts}"
    return ""


def _phase_key(phase: ContestPhase) -> str:
    if phase.is_active:
        return "running"
    return "before" if phase is ContestPhase.BEFORE else "finished"


def _row_html(
    row: StandingRow,
    columns: range,
    *,
    icpc: bool,
    padded: bool = False,
    ctx: ViewContext | None = None,
    firsts: list[int | None] | None = None,
    flagged: bool = False,
) -> str:
    ctx = ctx or ViewContext()
    firsts = firsts or []
    who = html.escape(_clip(row.who), quote=False)
    if ctx.view != "friends" and any(handle_key(h) in ctx.friends for h in row.handles):
        who = f"<mark><b>{who}</b></mark>"  # a followed handle stands out in the full table

    def problem(i: int) -> str:
        if i >= len(row.problems):
            return ""
        result = row.problems[i]
        if flagged:  # the platform names the first solver (kep.uz: one per problem)
            first = result.first
        else:  # the earliest time; ties at the same second all count
            first = i < len(firsts) and firsts[i] is not None and result.time_s == firsts[i]
        return styled_cell(result, icpc=icpc, padded=padded, style=ctx.style, first=first)

    cells = [
        _emoji(MEDALS[row.rank]) if row.rank in MEDALS else str(row.rank),
        who,
        f"<b>{_number(row.points)}</b>",
        str(row.penalty),
        *(problem(i) for i in columns),
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
    # kep.uz writes solve times as 01:23, Codeforces as 1:23; each table follows its site.
    padded = standings.contest.platform == platforms.KEP
    firsts = first_solves(standings)
    flagged = any(p.first for r in standings.rows for p in r.problems)
    body = "".join(
        _row_html(
            r, range(start, end), icpc=icpc, padded=padded, ctx=ctx, firsts=firsts, flagged=flagged
        )
        for r in rows
    )
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
    attrs = "bordered striped" if ctx.style == "classic" else "bordered compact"
    table = f"<table {attrs}>{header}{body}</table>" if rows else ""
    empty = ""
    if not rows:
        if ctx.view == "friends":
            empty = f"<p>{say.rich('standings-no-friends')}</p>"
        else:
            empty = f"<p>{say.rich('standings-empty')}</p>"
    page = f"<h1>{name}</h1><p>{status}</p>{table}{empty}<blockquote>{footer}</blockquote>"
    return cap_custom_emoji(page)


def cap_custom_emoji(html_text: str, limit: int = MAX_CUSTOM_EMOJI) -> str:
    """Keep at most ``limit`` custom emoji; later ones become their plain emoji.

    Telegram would do the same silently, but from the 101st on, so the look would change in the
    middle of the table. Doing it here keeps the decision visible and testable.
    """
    seen = 0

    def keep(match: re.Match[str]) -> str:
        nonlocal seen
        seen += 1
        return match.group(0) if seen <= limit else match.group(1)

    return _TAG_RE.sub(keep, html_text)


def _clock(moment: datetime, zone: str) -> str:
    return tzs.local_time_text(zone, moment)


def callback(
    contest_id: int,
    row_page: int,
    col_page: int,
    view: str = "all",
    *,
    refresh: bool = False,
    platform: str = platforms.CODEFORCES,
) -> str:
    """``st:<contest>:<row>:<col>:<view>[:r]``; a kep.uz contest is written ``kep504``."""
    token = VIEW_TOKEN.get(view, "a")
    target = platforms.get(platform).slug(contest_id)
    return f"{CALLBACK_PREFIX}{target}:{row_page}:{col_page}:{token}" + (":r" if refresh else "")


_callback = callback  # the keyboard shadows the name with its own


def parse_target(text: str) -> tuple[platforms.Platform, int] | None:
    """``1970`` -> Codeforces 1970; ``kep504`` -> kep.uz 504."""
    for site in platforms.PLATFORMS.values():
        tag = site.prefix.rstrip(":")
        if tag and text.startswith(tag):
            rest = text[len(tag) :]
            return (site, int(rest)) if rest.isascii() and rest.isdigit() else None
    return (platforms.DEFAULT, int(text)) if text.isascii() and text.isdigit() else None


def keyboard(
    standings: FullStandings,
    row_page: int,
    col_page: int,
    say: Translator,
    *,
    icons: bool,
    ctx: ViewContext | None = None,
    chat_id: int | None = None,
) -> InlineKeyboardMarkup:
    ctx = ctx or ViewContext()
    cid = standings.contest.external_id
    site = platforms.get(standings.contest.platform)
    view = ctx.view

    def callback(
        contest_id: int, row: int, col: int, view: str = "all", *, refresh: bool = False
    ) -> str:
        return _callback(contest_id, row, col, view, refresh=refresh, platform=site.name)

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
            app_button(say, f"standings_{site.slug(cid)}", icons=icons, chat_id=chat_id),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)  # type: ignore[arg-type]


def link_keyboard(
    standings: FullStandings, say: Translator, *, icons: bool
) -> InlineKeyboardMarkup:
    """The site's standings page and the Mini App: links only, no callbacks."""
    site = platforms.get(standings.contest.platform)
    cid = standings.contest.external_id
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                link(say("button-results"), site.standings_url(cid), emoji="🏆", icons=icons),
                app_button(say, f"standings_{site.slug(cid)}", icons=icons),
            ]
        ]
    )
