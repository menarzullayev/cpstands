"""Message catalogs (Fluent) and the translator used by every handler."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import structlog
from fluent.runtime import FluentBundle, FluentResource

SUPPORTED_LANGUAGES: tuple[str, ...] = ("uz", "ru", "en")
DEFAULT_LANGUAGE = "uz"
FALLBACK_LANGUAGE = "en"
LOCALES_DIR = Path(__file__).parent / "locales"

# Names shown on language buttons and in confirmations; never translated.
LANGUAGE_NAMES: Mapping[str, str] = {"uz": "O'zbekcha", "ru": "Русский", "en": "English"}

log = structlog.get_logger(__name__)

type FluentValue = str | int | float


class I18n:
    """Loads every catalog once and renders messages with a safe fallback.

    A missing key or a formatting error never raises: the user gets the English
    text (or the bare key as a last resort) and the problem is logged.
    """

    def __init__(self, locales_dir: Path = LOCALES_DIR) -> None:
        self._bundles: dict[str, FluentBundle] = {}
        for lang in SUPPORTED_LANGUAGES:
            text = (locales_dir / lang / "messages.ftl").read_text(encoding="utf-8")
            # Isolation marks would end up inside Telegram messages, so they are off.
            bundle = FluentBundle([lang], use_isolating=False)
            bundle.add_resource(FluentResource(text))
            self._bundles[lang] = bundle

    def t(self, lang: str | None, key: str, **args: FluentValue) -> str:
        """Render ``key`` in ``lang``; unknown languages use the default language."""
        language = lang if lang in self._bundles else DEFAULT_LANGUAGE
        text = self._render(language, key, args)
        if text is None and language != FALLBACK_LANGUAGE:
            text = self._render(FALLBACK_LANGUAGE, key, args)
        if text is None:
            log.error("i18n_missing_key", key=key, lang=language)
            return key
        return text

    def _render(self, lang: str, key: str, args: Mapping[str, FluentValue]) -> str | None:
        bundle = self._bundles[lang]
        try:
            message = bundle.get_message(key)
        except KeyError:
            return None
        if message.value is None:
            return None
        text, errors = bundle.format_pattern(message.value, dict(args))
        if errors:
            log.error("i18n_format_error", key=key, lang=lang, errors=[repr(e) for e in errors])
            return None
        return str(text)
