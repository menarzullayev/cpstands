"""The friends' rating table as a Rich Message, paged by rows."""

from __future__ import annotations

import html

from aiogram.types import InlineKeyboardMarkup

from cpstands.bot.keyboards import button
from cpstands.i18n import Translator
from cpstands.services import timezone as tzs
from cpstands.services.ratings import RatingTable

ROWS_PER_PAGE = 25
NAME_MAX = 20
PREFIX = "rk:"
NOOP = "rk:noop"


def pages(total: int) -> int:
    return max(1, -(-total // ROWS_PER_PAGE))


def _clip(name: str) -> str:
    return name if len(name) <= NAME_MAX else name[: NAME_MAX - 1] + "…"


def _cell(value: object) -> str:
    return "-" if value is None else html.escape(str(value), quote=False)


def render(table: RatingTable, page: int, say: Translator, *, time_zone: str | None) -> str:
    """HTML of one page (0-based, clamped); the unknown handles are listed under the table."""
    total = len(table.rows)
    page = min(max(page, 0), pages(total) - 1)
    first = page * ROWS_PER_PAGE
    rows = table.rows[first : first + ROWS_PER_PAGE]
    zone = time_zone if time_zone and tzs.is_valid_zone(time_zone) else "UTC"
    head = "".join(f"<th>{h}</th>" for h in ("#", "Handle", "Rating", "Max", "Rank"))
    body = "".join(
        "<tr>"
        + "".join(
            f"<td>{c}</td>"
            for c in (
                first + i + 1,
                html.escape(_clip(r.handle), quote=False),
                _cell(r.rating),
                _cell(r.max_rating),
                _cell(r.rank),
            )
        )
        + "</tr>"
        for i, r in enumerate(rows)
    )
    status = say.rich("rank-status", count=total, time=tzs.local_time_text(zone, table.fetched_at))
    footer = say.rich(
        "rank-footer", first=first + 1 if rows else 0, last=first + len(rows), total=total
    )
    note = ""
    if table.unknown:
        names = ", ".join(table.unknown)  # escaped once, by the translator
        note = f"<p>{say.rich('rank-unknown', handles=names)}</p>"
    table_html = f"<table><tr>{head}</tr>{body}</table>" if rows else ""
    title = say.rich("rank-title")
    return f"<h1>{title}</h1><p>{status}</p>{table_html}{note}<blockquote>{footer}</blockquote>"


def callback(page: int, *, refresh: bool = False) -> str:
    return f"{PREFIX}{page}" + (":r" if refresh else "")


def keyboard(total: int, page: int, say: Translator, *, icons: bool) -> InlineKeyboardMarkup:
    count = pages(total)
    page = min(max(page, 0), count - 1)
    rows = []
    if count > 1:
        rows.append(
            [
                button("⏮", callback(0)),
                button("◀", callback(max(page - 1, 0))),
                button(f"{page + 1} / {count}", NOOP),
                button("▶", callback(min(page + 1, count - 1))),
                button("⏭", callback(count - 1)),
            ]
        )
    rows.append(
        [button(say("button-refresh"), callback(page, refresh=True), emoji="🔁", icons=icons)]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)
