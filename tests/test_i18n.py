"""Catalog completeness (positive) and proof that the checker catches breakage (negative)."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest
from fluent.syntax import FluentParser, ast

from cpstands.i18n import LOCALES_DIR, SUPPORTED_LANGUAGES, I18n
from cpstands.i18n.check import check_catalogs

SAMPLE_ARGS: dict[str, str | int] = {
    "language": "English",
    "zone": "Asia/Tashkent",
    "time": "14:05",
    "query": "tash",
    "count": 3,
    "handles": "tourist, jiangly",
    "limit": 100,
    "mood": "playful",
    "phase": "finished",
    "first": 1,
    "last": 25,
    "total": 827,
    "from_problem": "A1",
    "to_problem": "D2",
    "id": "1970",
    "reminders": "on",
    "state": "on",
    "left": "day",
    "minutes": 10,
    "start": "21.11 19:35",
    "duration": "2:00",
    "view": "all",
    "level": 4,
    "cols": 16,
    "summary": "on",
    "medal": "🥇",
    "solved": 3,
    "body": "body",
    "rating": "1500",
    "max": "1600",
    "rank": "expert",
    "delta": "+10",
    "old": "1490",
    "new": "1500",
    "n": 16,
    "version": "0.1",
    "uptime": "1h",
    "sources": "codeforces",
    "overdue": 0,
    "scheduled": 1,
    "live": 0,
    "contests": 0,
    "chats": "active 1",
    "open": "-",
    "events": 1,
    "pending": 0,
    "failed": 0,
    "age": 200,
    "percent": 10,
    "source": "codeforces",
    "rule": "late",
    "alerts": "on",
    "v": 1,
    "handle": "tourist",
    "problem": "A1",
    "contest": "Round",
    "title": "Title",
    "name": "Round",
}


@pytest.fixture
def broken_locales(tmp_path: Path) -> Path:
    target = tmp_path / "locales"
    shutil.copytree(LOCALES_DIR, target)
    return target


def _edit(root: Path, lang: str, old: str, new: str) -> None:
    path = root / lang / "messages.ftl"
    text = path.read_text(encoding="utf-8")
    assert old in text, old
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def _message_ids(lang: str) -> list[str]:
    text = (LOCALES_DIR / lang / "messages.ftl").read_text(encoding="utf-8")
    body = FluentParser().parse(text).body
    return [entry.id.name for entry in body if isinstance(entry, ast.Message)]


def test_real_catalogs_are_consistent() -> None:
    assert check_catalogs() == []


def test_every_message_renders_in_every_language() -> None:
    i18n = I18n()
    for lang in SUPPORTED_LANGUAGES:
        for key in _message_ids(lang):
            text = i18n.t(lang, key, **SAMPLE_ARGS)  # type: ignore[arg-type]
            assert text != key, (lang, key)
            assert "{" not in text, (lang, key, text)
            assert "}" not in text, (lang, key, text)
            assert text.strip(), (lang, key)


@pytest.mark.parametrize(
    ("count", "expected"),
    [(1, "1 друг"), (2, "2 друга"), (5, "5 друзей"), (11, "11 друзей"), (21, "21 друг")],
)
def test_russian_plural_forms(count: int, expected: str) -> None:
    # The catalog uses "хендл"; the form pattern is what matters, so check the stem and suffix.
    text = I18n().t("ru", "track-list-header", count=count)
    forms = {1: "хендл", 2: "хендла", 5: "хендлов", 11: "хендлов", 21: "хендл"}
    assert f"{count} {forms[count]}</b>" in text, (expected, text)


def test_english_plural_forms() -> None:
    i18n = I18n()
    assert i18n.t("en", "track-list-header", count=1).endswith("1 handle</b>")
    assert i18n.t("en", "track-list-header", count=2).endswith("2 handles</b>")


def test_no_unicode_isolation_marks_in_output() -> None:
    text = I18n().t("en", "setup-done", language="English", zone="Asia/Tashkent")
    assert "⁨" not in text
    assert "⁩" not in text


def test_unknown_language_uses_default_and_missing_key_returns_key() -> None:
    i18n = I18n()
    assert i18n.t("xx", "not-admin") == i18n.t("uz", "not-admin")
    assert i18n.t(None, "not-admin") == i18n.t("uz", "not-admin")
    assert i18n.t("en", "no-such-key") == "no-such-key"


def test_missing_variable_falls_back_instead_of_raising() -> None:
    # A forgotten argument must not crash a handler; the English text (or key) is returned.
    text = I18n().t("ru", "timezone-set")
    assert isinstance(text, str)
    assert text


def test_checker_catches_missing_message(broken_locales: Path) -> None:
    _edit(broken_locales, "ru", "not-admin = ", "not-admin-renamed = ")
    problems = check_catalogs(broken_locales)
    assert any("ru: message 'not-admin' is missing" in p for p in problems)
    assert any("'not-admin-renamed' does not exist" in p for p in problems)


def test_checker_catches_variable_mismatch(broken_locales: Path) -> None:
    _edit(broken_locales, "uz", "Qo'shildi: <b>{ $handles }</b>", "Qo'shildi: <b>{ $names }</b>")
    problems = check_catalogs(broken_locales)
    assert any("uz: message 'track-added'" in p for p in problems)


def test_checker_catches_syntax_error(broken_locales: Path) -> None:
    _edit(
        broken_locales,
        "en",
        "track-removed = ✅ Removed: <b>{ $handles }</b>",
        "track-removed = { $handles",
    )
    problems = check_catalogs(broken_locales)
    assert any(p.startswith("en: syntax error") for p in problems)


def test_checker_catches_empty_message(broken_locales: Path) -> None:
    _edit(
        broken_locales,
        "en",
        "rate-limited = ⏰ Easy there, speedster! Give me a moment.",
        "rate-limited =",
    )
    problems = check_catalogs(broken_locales)
    assert any("en:" in p and "rate-limited" in p for p in problems)


def test_checker_catches_missing_russian_plural_form(broken_locales: Path) -> None:
    _edit(broken_locales, "ru", "        [many] { $count } хендлов\n", "")
    problems = check_catalogs(broken_locales)
    assert any("ru: message 'settings-summary' has plural keys" in p for p in problems)


def test_checker_catches_missing_catalog_file(broken_locales: Path) -> None:
    (broken_locales / "uz" / "messages.ftl").unlink()
    problems = check_catalogs(broken_locales)
    assert any("uz: catalog file is missing" in p for p in problems)


_KEY_RE = re.compile(
    r"""(?:\b(?:t|say|rich|tr)\(\s*(?:[^,()"']+,\s*)?|\b_?say\([^()]*\)\(\s*)["']([a-z0-9-]+)["']"""
)
SRC = Path(__file__).resolve().parents[1] / "src" / "cpstands"


def keys_used_in(source: str) -> set[str]:
    return set(_KEY_RE.findall(source))


def _code_keys() -> set[str]:
    keys: set[str] = set()
    for path in SRC.rglob("*.py"):
        keys |= keys_used_in(path.read_text(encoding="utf-8"))
    return keys


def test_every_key_used_in_code_exists_in_the_catalog() -> None:
    assert _code_keys() - set(_message_ids("en")) == set()


def test_every_catalog_key_is_used_in_code() -> None:
    used = _code_keys()
    unused = {
        key
        for key in set(_message_ids("en")) - used
        if not (key.endswith("-neutral") and key.removesuffix("-neutral") in used)
    }
    assert unused == set()


def test_key_scanner_finds_calls_and_ignores_noise() -> None:
    sample = 'x = deps.i18n.t(lang, "not-admin")\ny = say(\'track-usage\')\nz = "plain-string"\n'
    assert keys_used_in(sample) == {"not-admin", "track-usage"}


def test_user_text_is_html_escaped() -> None:
    text = I18n().t("en", "track-added", handles="<script>alert(1)</script> & co")
    assert "<script>" not in text
    assert "&lt;script&gt;" in text
    assert "&amp; co" in text


def test_neutral_tone_prefers_the_neutral_variant_and_falls_back_to_the_base() -> None:
    i18n = I18n()
    playful = i18n.t("en", "rate-limited", tone="playful")
    neutral = i18n.t("en", "rate-limited", tone="neutral")
    assert playful != neutral
    assert neutral == "Too many requests. Please wait a moment."
    assert i18n.t("en", "not-admin", tone="neutral") == i18n.t("en", "not-admin")
    assert i18n.bound("ru", "neutral")("error-generic") == i18n.t(
        "ru", "error-generic", tone="neutral"
    )


def test_custom_emoji_wraps_known_emoji_and_leaves_others() -> None:
    plain = I18n().t("en", "rate-limited")
    custom = I18n(custom_emoji=True).t("en", "rate-limited")
    assert "<tg-emoji" not in plain
    assert custom.startswith('<tg-emoji emoji-id="')
    assert custom.endswith("Give me a moment.")
    # Emoji without a custom twin are left exactly as they are.
    assert "⚙️" in I18n(custom_emoji=True).t(
        "en",
        "settings-summary",
        language="x",
        zone="y",
        mood="playful",
        reminders="on",
        level=4,
        cols=16,
        summary="on",
        count=1,
    )


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        ("<b>2/3 · Time zone</b>", "<b>2/3 · Time zone", "unclosed <b>"),
        ("<b>2/3 · Time zone</b>", "<div>2/3 · Time zone</div>", "tag <div> is not allowed"),
        ("<b>2/3 · Time zone</b>", "2/3 · Time zone</b>", "unbalanced </b>"),
        ("Pick your time zone below.", "Pick & choose your time zone below.", "bare '&'"),
        ("Pick your time zone below.", "Pick a < b time zone below.", "bare '<'"),
    ],
)
def test_checker_catches_broken_html(
    broken_locales: Path, old: str, new: str, expected: str
) -> None:
    _edit(broken_locales, "en", old, new)
    assert any(expected in p for p in check_catalogs(broken_locales))


def test_checker_catches_neutral_variant_problems(broken_locales: Path) -> None:
    _edit(
        broken_locales,
        "en",
        "rate-limited-neutral = Too many",
        "rate-limited-neutral = { $x } Too many",
    )
    assert any(
        "rate-limited-neutral" in p and "variables" in p for p in check_catalogs(broken_locales)
    )
    _edit(broken_locales, "en", "not-admin = ", "not-admin-gone = ")
    _edit(broken_locales, "en", "error-generic-neutral", "no-base-neutral")
    assert any("'no-base-neutral' has no base message" in p for p in check_catalogs(broken_locales))


@pytest.mark.parametrize(
    ("lang", "old", "new", "word"),
    [
        ("en", "It happens to the best!", "What a loser!", "loser"),
        ("en", "Chin up!", "Total Idiots.", "idiot"),
        ("ru", "Бывает и у лучших!", "Ты лох!", "лох"),
        ("ru", "Держимся!", "Неудачник!", "неудачник"),
        ("uz", "Eng yaxshilarda ham bo'ladi!", "Ahmoq!", "ahmoq"),
    ],
)
def test_content_guard_catches_insulting_alert_texts(
    broken_locales: Path, lang: str, old: str, new: str, word: str
) -> None:
    _edit(broken_locales, lang, old, new)
    problems = check_catalogs(broken_locales)
    assert any("alert-systest-fail" in p and word in p.lower() for p in problems)


def test_content_guard_ignores_harmless_words_that_contain_a_banned_stem() -> None:
    from cpstands.i18n.check import BANNED_WORDS

    assert not BANNED_WORDS["ru"].search("плохой день, но не страшно")  # contains "лох" inside
    assert not BANNED_WORDS["en"].search("a failure-free round".replace("failure", "fine"))
    assert BANNED_WORDS["en"].search("pure trash")


def test_the_guard_only_applies_to_alert_texts(broken_locales: Path) -> None:
    _edit(broken_locales, "en", "not-admin = 🔒 Only", "not-admin = 🔒 Stupid, only")
    assert not any("stupid" in p for p in check_catalogs(broken_locales))
