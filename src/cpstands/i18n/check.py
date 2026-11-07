"""Static checks for the Fluent catalogs: same messages, same variables, valid plurals."""

from __future__ import annotations

import sys
from pathlib import Path

from fluent.syntax import FluentParser, ast
from fluent.syntax.visitor import Visitor

from cpstands.i18n import FALLBACK_LANGUAGE, LOCALES_DIR, SUPPORTED_LANGUAGES

# CLDR plural categories that must be written out for each language.
PLURAL_CATEGORIES: dict[str, frozenset[str]] = {
    "uz": frozenset({"one", "other"}),
    "en": frozenset({"one", "other"}),
    "ru": frozenset({"one", "few", "many", "other"}),
}


class _Collector(Visitor):
    """Collects the variables of a message and the plural keys of each selector."""

    def __init__(self) -> None:
        super().__init__()
        self.variables: set[str] = set()
        self.plural_sets: list[frozenset[str]] = []

    def visit_VariableReference(self, node: ast.VariableReference) -> None:  # noqa: N802
        self.variables.add(node.id.name)

    def visit_SelectExpression(self, node: ast.SelectExpression) -> None:  # noqa: N802
        keys = frozenset(v.key.name for v in node.variants if isinstance(v.key, ast.Identifier))
        if keys:
            self.plural_sets.append(keys)
        self.generic_visit(node)


class _Catalog:
    def __init__(self) -> None:
        self.messages: dict[str, _Collector] = {}
        self.problems: list[str] = []


def _load(path: Path, label: str) -> _Catalog:
    catalog = _Catalog()
    if not path.is_file():
        catalog.problems.append(f"{label}: catalog file is missing ({path})")
        return catalog
    resource = FluentParser().parse(path.read_text(encoding="utf-8"))
    for entry in resource.body:
        if isinstance(entry, ast.Junk):
            lines = (entry.content or "").strip().splitlines()
            snippet = lines[0] if lines else ""
            catalog.problems.append(f"{label}: syntax error near '{snippet}'")
        elif isinstance(entry, ast.Message):
            if entry.value is None or not entry.value.elements:
                catalog.problems.append(f"{label}: message '{entry.id.name}' is empty")
                continue
            collector = _Collector()
            collector.visit(entry.value)
            catalog.messages[entry.id.name] = collector
    return catalog


def check_catalogs(locales_dir: Path = LOCALES_DIR) -> list[str]:
    """Return a list of human-readable problems; an empty list means the catalogs agree."""
    catalogs = {
        lang: _load(locales_dir / lang / "messages.ftl", lang) for lang in SUPPORTED_LANGUAGES
    }
    problems: list[str] = []
    for catalog in catalogs.values():
        problems.extend(catalog.problems)

    reference = catalogs[FALLBACK_LANGUAGE].messages
    for lang, catalog in catalogs.items():
        if lang == FALLBACK_LANGUAGE:
            continue
        for key in sorted(reference.keys() - catalog.messages.keys()):
            problems.append(f"{lang}: message '{key}' is missing")
        for key in sorted(catalog.messages.keys() - reference.keys()):
            problems.append(f"{lang}: message '{key}' does not exist in {FALLBACK_LANGUAGE}")
        for key in sorted(reference.keys() & catalog.messages.keys()):
            expected = reference[key].variables
            actual = catalog.messages[key].variables
            if expected != actual:
                problems.append(
                    f"{lang}: message '{key}' uses variables {sorted(actual)}, "
                    f"expected {sorted(expected)}"
                )
    for lang, catalog in catalogs.items():
        required = PLURAL_CATEGORIES[lang]
        for key, collector in sorted(catalog.messages.items()):
            for keys in collector.plural_sets:
                if keys != required:
                    problems.append(
                        f"{lang}: message '{key}' has plural keys {sorted(keys)}, "
                        f"expected {sorted(required)}"
                    )
    return problems


def main() -> int:
    problems = check_catalogs()
    for problem in problems:
        print(problem, file=sys.stderr)  # noqa: T201
    if not problems:
        print("i18n catalogs are consistent")  # noqa: T201
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
