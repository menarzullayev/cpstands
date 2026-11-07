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
            text = i18n.t(lang, key, **SAMPLE_ARGS)
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
    assert text.endswith(f"{count} {forms[count]}"), (expected, text)


def test_english_plural_forms() -> None:
    i18n = I18n()
    assert i18n.t("en", "track-list-header", count=1).endswith("1 handle")
    assert i18n.t("en", "track-list-header", count=2).endswith("2 handles")


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
    _edit(broken_locales, "uz", "Qo'shildi: { $handles }", "Qo'shildi: { $names }")
    problems = check_catalogs(broken_locales)
    assert any("uz: message 'track-added'" in p for p in problems)


def test_checker_catches_syntax_error(broken_locales: Path) -> None:
    _edit(
        broken_locales, "en", "track-removed = Removed: { $handles }", "track-removed = { $handles"
    )
    problems = check_catalogs(broken_locales)
    assert any(p.startswith("en: syntax error") for p in problems)


def test_checker_catches_empty_message(broken_locales: Path) -> None:
    _edit(
        broken_locales,
        "en",
        "rate-limited = Too many requests. Please wait a moment.",
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


_KEY_RE = re.compile(r"""\bt\(\s*[^,()]+,\s*["']([a-z0-9-]+)["']""")
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
    assert set(_message_ids("en")) - _code_keys() == set()


def test_key_scanner_finds_calls_and_ignores_noise() -> None:
    sample = (
        'x = deps.i18n.t(lang, "not-admin")\ny = t(None, \'track-usage\')\nz = "plain-string"\n'
    )
    assert keys_used_in(sample) == {"not-admin", "track-usage"}
