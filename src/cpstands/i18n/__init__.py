"""Message catalogs (Fluent) and the translator used by every handler.

Catalog texts are Telegram HTML. String arguments are escaped here, so a handle or a city
typed by a user can never inject markup into a message.
"""

from __future__ import annotations

import html
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import structlog
from fluent.runtime import FluentBundle, FluentResource

from cpstands.ui.emoji import decorate

SUPPORTED_LANGUAGES: tuple[str, ...] = ("uz", "ru", "en")
DEFAULT_LANGUAGE = "uz"
FALLBACK_LANGUAGE = "en"
TONES: tuple[str, ...] = ("playful", "neutral")
DEFAULT_TONE = "playful"
NEUTRAL_SUFFIX = "-neutral"
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

    def __init__(self, locales_dir: Path = LOCALES_DIR, *, custom_emoji: bool = False) -> None:
        self._custom_emoji = custom_emoji
        self._bundles: dict[str, FluentBundle] = {}
        for lang in SUPPORTED_LANGUAGES:
            text = (locales_dir / lang / "messages.ftl").read_text(encoding="utf-8")
            # Isolation marks would end up inside Telegram messages, so they are off.
            bundle = FluentBundle([lang], use_isolating=False)
            bundle.add_resource(FluentResource(text))
            self._bundles[lang] = bundle

    def t(
        self, lang: str | None, key: str, *, tone: str = DEFAULT_TONE, **args: FluentValue
    ) -> str:
        """Render ``key`` in ``lang``; unknown languages use the default language.

        With the neutral tone, ``<key>-neutral`` is preferred when the catalog has it.
        """
        language = lang if lang in self._bundles else DEFAULT_LANGUAGE
        safe = {
            k: html.escape(v, quote=False) if isinstance(v, str) else v for k, v in args.items()
        }
        keys = [key + NEUTRAL_SUFFIX, key] if tone == "neutral" else [key]
        text: str | None = None
        for candidate in keys:
            text = self._render(language, candidate, safe)
            if text is None and language != FALLBACK_LANGUAGE:
                text = self._render(FALLBACK_LANGUAGE, candidate, safe)
            if text is not None:
                break
        if text is None:
            log.error("i18n_missing_key", key=key, lang=language)
            return html.escape(key, quote=False)
        return decorate(text) if self._custom_emoji else text

    def bound(self, lang: str | None, tone: str = DEFAULT_TONE) -> Translator:
        return Translator(self, lang, tone)

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


@dataclass(frozen=True, slots=True)
class Translator:
    """A translator bound to one chat's language and tone: ``say("not-admin")``."""

    i18n: I18n
    lang: str | None
    tone: str = DEFAULT_TONE

    def __call__(self, key: str, **args: FluentValue) -> str:
        return self.i18n.t(self.lang, key, tone=self.tone, **args)
