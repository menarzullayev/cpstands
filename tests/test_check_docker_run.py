"""The docker volume-leak guard (scripts/check_docker_run.py): its rules can fail, the repo passes."""

import importlib.util
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "check_docker_run", ROOT / "scripts" / "check_docker_run.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_builtin_rules_hold() -> None:
    assert _load().selftest() == 0


def test_repository_has_no_leaking_docker_command() -> None:
    assert _load().scan_repo(ROOT) == []


def test_a_postgres_run_without_rm_is_reported() -> None:
    found = _load().scan_text("```bash\ndocker run -d postgres:17-alpine\n```\n", "runbook.md")
    assert len(found) == 1
    assert "R2" in found[0]


def test_docker_rm_without_volumes_is_reported() -> None:
    found = _load().scan_text("```bash\ndocker rm -f restore-test\n```\n", "runbook.md")
    assert len(found) == 1
    assert "R3" in found[0]


def test_rm_flag_and_named_volume_pass() -> None:
    module = _load()
    assert module.scan_text("docker run -d --rm postgres:17-alpine\n", "a.sh") == []
    named = "docker run -d -v pgdata:/var/lib/postgresql/data postgres:17-alpine\n"
    assert module.scan_text(named, "a.sh") == []
