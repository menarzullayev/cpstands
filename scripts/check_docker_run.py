#!/usr/bin/env python3
"""Fail when a tracked script, workflow or README starts a container that leaks Docker volumes.

Images such as postgres, redis (older tags), mysql, mongo, minio and prometheus declare VOLUME
paths. Started with `docker run` and no `--rm`, every run leaves an anonymous volume behind that
nothing owns and nothing cleans up. A bare file name used as a volume source
(`-v inner_py.sh:/tmp/x`) silently creates a NAMED volume instead of a bind mount.

Rules (the same ones the local Claude Code hook enforces on interactive commands):
  R1  `-v NAME.ext:/path` where NAME.ext is a file name, not a volume name or a path.
  R2  no `--rm`, and the image declares VOLUME paths that no `-v`/`--mount`/`--tmpfs` covers;
      also `-v /path` without a source (anonymous volume).
  R3  `docker rm` without `-v`: the container goes, its anonymous volumes stay.
`--rm` is enough on its own: Docker removes anonymous volumes together with the container.
A service that must keep data uses an explicit named volume (`-v name:/path`) or `--tmpfs`.

A deliberate exception takes a reason on the same line or the line above:
    # docker-run-guard: ignore -- <why this container may leave a volume>

Usage:
    python3 check_docker_run.py              # scan the git repository that holds the cwd
    python3 check_docker_run.py --root DIR   # scan another repository
    python3 check_docker_run.py --selftest   # prove the rules with positive and negative cases
Standard library only. Exit 0 = clean, 1 = violations, 2 = self-test failure.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

VALUE_FLAGS = {
    "--add-host",
    "--annotation",
    "--attach",
    "--blkio-weight",
    "--cap-add",
    "--cap-drop",
    "--cgroup-parent",
    "--cgroupns",
    "--cidfile",
    "--cpu-period",
    "--cpu-quota",
    "--cpu-shares",
    "--cpus",
    "--cpuset-cpus",
    "--cpuset-mems",
    "--detach-keys",
    "--device",
    "--dns",
    "--dns-option",
    "--dns-search",
    "--domainname",
    "--entrypoint",
    "--env",
    "--env-file",
    "--expose",
    "--gpus",
    "--group-add",
    "--health-cmd",
    "--health-interval",
    "--health-retries",
    "--health-start-period",
    "--health-timeout",
    "--hostname",
    "--ip",
    "--ip6",
    "--ipc",
    "--isolation",
    "--label",
    "--label-file",
    "--link",
    "--log-driver",
    "--log-opt",
    "--mac-address",
    "--memory",
    "--memory-reservation",
    "--memory-swap",
    "--mount",
    "--name",
    "--network",
    "--network-alias",
    "--pid",
    "--platform",
    "--publish",
    "--pull",
    "--restart",
    "--runtime",
    "--security-opt",
    "--shm-size",
    "--stop-signal",
    "--stop-timeout",
    "--storage-opt",
    "--sysctl",
    "--tmpfs",
    "--ulimit",
    "--user",
    "--userns",
    "--uts",
    "--volume",
    "--volume-driver",
    "--volumes-from",
    "--workdir",
}
SHORT_VALUE = {"-a", "-c", "-e", "-h", "-l", "-m", "-p", "-u", "-v", "-w"}

# Image (last path segment, no tag) -> VOLUME paths it declares.
STATIC_VOLUMES: dict[str, list[str]] = {
    "postgres": ["/var/lib/postgresql/data", "/var/lib/postgresql"],
    "redis": ["/data"],
    "valkey": ["/data"],
    "mysql": ["/var/lib/mysql"],
    "mariadb": ["/var/lib/mysql"],
    "mongo": ["/data/db", "/data/configdb"],
    "rabbitmq": ["/var/lib/rabbitmq"],
    "minio": ["/data"],
    "clickhouse": ["/var/lib/clickhouse"],
    "prometheus": ["/prometheus"],
    "grafana": ["/var/lib/grafana"],
}

PATHLIKE = re.compile(r"^(/|\.|~|\$|%|[A-Za-z]:[\\/])")
FILENAME = re.compile(r"^[A-Za-z0-9_-]+\.[A-Za-z0-9]{1,6}$")
TOKEN = re.compile(r"\"[^\"]*\"|'[^']*'|\S+")
DOCKER_RUN = re.compile(r"\bdocker(?:\.exe)?\s+(?:container\s+)?(?:run|create)\b")
DOCKER_RM = re.compile(r"\bdocker(?:\.exe)?\s+(?:container\s+)?rm\b")
IGNORE = re.compile(r"docker-run-guard:\s*ignore")
NOT_A_COMMAND = re.compile(r"^\s*(#|(-\s+)?name:)")
SCAN_SUFFIXES = {".sh", ".bash", ".ps1", ".psm1", ".yml", ".yaml", ".mk", ".md"}
SCAN_NAMES = {"Makefile", "makefile", "package.json", "Justfile"}
SKIP_PARTS = ("node_modules/", "/vendor/", "/.git/", "graphify-out/")


def cut_at_operator(text: str) -> str:
    """Return text up to the first shell operator that is not inside quotes."""
    quote = ""
    i = 0
    while i < len(text):
        c = text[i]
        if quote:
            if c == quote:
                quote = ""
        elif c in "\"'":
            quote = c
        elif text.startswith(("&&", "||"), i) or c in ";|":
            return text[:i]
        i += 1
    return text


def tokenize(segment: str) -> list[str]:
    out = []
    for t in TOKEN.findall(segment):
        if len(t) >= 2 and t[0] == t[-1] and t[0] in "\"'":
            t = t[1:-1]
        out.append(t)
    return out


def parse_run(tokens: list[str]) -> dict[str, Any] | None:
    n = len(tokens)
    for i, tok in enumerate(tokens):
        if os.path.basename(tok.replace("\\", "/")).lower() not in ("docker", "docker.exe"):
            continue
        j = i + 1
        if j < n and tokens[j] == "container":
            j += 1
        if j >= n or tokens[j] not in ("run", "create"):
            continue
        j += 1
        info: dict[str, Any] = {"rm": False, "image": None, "vols": [], "mounts": [], "tmpfs": []}
        while j < n:
            t = tokens[j]
            if t == "--":
                j += 1
                break
            if t.startswith("--"):
                name, eq, val = t.partition("=")
                if name == "--rm":
                    info["rm"] = val.lower() != "false"
                    j += 1
                    continue
                if not eq and name in VALUE_FLAGS:
                    val = tokens[j + 1] if j + 1 < n else ""
                    j += 2
                else:
                    j += 1
                if name == "--volume":
                    info["vols"].append(val)
                elif name == "--mount":
                    info["mounts"].append(val)
                elif name == "--tmpfs":
                    info["tmpfs"].append(val.split(":")[0])
                continue
            if t.startswith("-") and len(t) > 1:
                if t in SHORT_VALUE:
                    val = tokens[j + 1] if j + 1 < n else ""
                    j += 2
                    if t == "-v":
                        info["vols"].append(val)
                    continue
                if t[:2] == "-v" and len(t) > 2:
                    info["vols"].append(t[2:])
                j += 1
                continue
            break
        if j < n:
            info["image"] = tokens[j]
        return info
    return None


def declared_volumes(image: str) -> list[str]:
    ref = image.split("@")[0]
    last = ref.rsplit("/", 1)[-1]
    name = last.rsplit(":", 1)[0].lower() if ":" in last else last.lower()
    if ref.lower().startswith(("bitnami/", "bitnamilegacy/")):
        return ["/bitnami"]
    return list(STATIC_VOLUMES.get(name, []))


def mount_dests(info: dict[str, Any]) -> list[str]:
    dests: list[str] = []
    for v in info["vols"]:
        parts = v.split(":")
        if len(parts) >= 2 and len(parts[0]) == 1 and parts[1][:1] in ("\\", "/"):
            parts = [parts[0] + ":" + parts[1], *parts[2:]]
        dests.append(parts[0] if len(parts) == 1 else parts[1])
    for m in info["mounts"]:
        for kv in m.split(","):
            k, _, val = kv.partition("=")
            if k.strip() in ("dst", "destination", "target"):
                dests.append(val)
    dests.extend(info["tmpfs"])
    return [d.rstrip("/") or "/" for d in dests]


def covered(path: str, dests: list[str]) -> bool:
    path = path.rstrip("/") or "/"
    return any(d == path or path.startswith(d + "/") or d.startswith(path + "/") for d in dests)


def rm_without_volumes(tokens: list[str]) -> bool:
    """True for `docker [container] rm ...` that does not pass -v/--volumes."""
    n = len(tokens)
    for i, tok in enumerate(tokens):
        if os.path.basename(tok.replace("\\", "/")).lower() not in ("docker", "docker.exe"):
            continue
        j = i + 1
        if j < n and tokens[j] == "container":
            j += 1
        if j >= n or tokens[j] != "rm":
            continue
        for t in tokens[j + 1 :]:
            if not t.startswith("-"):
                break
            if t.startswith("--"):
                if t.partition("=")[0] == "--volumes" and t.partition("=")[2].lower() != "false":
                    return False
            elif "v" in t[1:]:
                return False
        return True
    return False


def check_command(command: str) -> list[str]:
    """Violations for one logical line (may hold several docker invocations)."""
    problems: list[str] = []
    for m in DOCKER_RM.finditer(command):
        if rm_without_volumes(tokenize(cut_at_operator(command[m.start() :]))):
            problems.append(
                "R3: `docker rm` without -v leaves the container's anonymous volumes behind; "
                "use `docker rm -v` (named volumes are never touched by -v)"
            )
    for m in DOCKER_RUN.finditer(command):
        info = parse_run(tokenize(cut_at_operator(command[m.start() :])))
        if not info:
            continue
        for v in info["vols"]:
            src = v.split(":")[0]
            if len(src) > 1 and FILENAME.match(src) and not PATHLIKE.match(src):
                problems.append(
                    f"R1: '-v {src}:...' uses a file name as the source and creates a NAMED "
                    f"VOLUME '{src}'; write ./{src} for a bind mount"
                )
        if info["rm"]:
            continue
        for v in info["vols"]:
            if ":" not in v and v.startswith("/"):
                problems.append(f"R2: '-v {v}' has no source (anonymous volume); add --rm")
        if info["image"]:
            dests = mount_dests(info)
            missing = [p for p in declared_volumes(info["image"]) if not covered(p, dests)]
            if missing:
                problems.append(
                    f"R2: image '{info['image']}' declares VOLUME {', '.join(missing)} and "
                    "the run has no --rm: every run leaves an anonymous volume; use --rm, "
                    "--tmpfs <path> or -v <name>:<path>"
                )
    return problems


def logical_lines(text: str, path: str) -> list[tuple[int, str, str]]:
    """(first line number, logical line, previous physical line) with continuations joined."""
    cont = "`" if path.endswith((".ps1", ".psm1")) else "\\"
    out: list[tuple[int, str, str]] = []
    buf: list[str] = []
    start = 0
    prev = ""
    prev_at_start = ""
    in_fence = False
    md = path.endswith(".md")
    for no, raw in enumerate(text.splitlines(), 1):
        if md:
            if raw.lstrip().startswith("```"):
                in_fence = not in_fence
                prev = raw
                continue
            if not in_fence:
                prev = raw
                continue
        line = raw.rstrip()
        if not buf:
            start = no
            prev_at_start = prev
        if line.endswith(cont):
            buf.append(line[:-1])
        else:
            buf.append(line)
            joined = " ".join(s.strip() for s in buf)
            if path.endswith("package.json"):
                joined = joined.replace('\\"', '"')
            out.append((start, joined, prev_at_start))
            buf = []
        if not buf:
            prev = raw
    return out


def scan_text(text: str, path: str) -> list[str]:
    found: list[str] = []
    for no, line, prev in logical_lines(text, path):
        if "docker" not in line:
            continue
        # A comment, or a YAML `name:` label, describes a command; it does not run one.
        if NOT_A_COMMAND.match(line):
            continue
        probs = check_command(line)
        if probs and not (IGNORE.search(line) or IGNORE.search(prev)):
            found.extend(f"{path}:{no}: {p}" for p in probs)
    return found


def tracked_files(root: Path) -> list[str]:
    git = shutil.which("git") or "git"
    res = subprocess.run(  # noqa: S603 - fixed argument list, no shell
        [git, "-C", str(root), "ls-files", "-z"], capture_output=True, check=True
    )
    files = [f for f in res.stdout.decode("utf-8", "replace").split("\0") if f]
    return [
        f
        for f in files
        if (Path(f).suffix in SCAN_SUFFIXES or Path(f).name in SCAN_NAMES)
        and not any(s in "/" + f for s in SKIP_PARTS)
    ]


def scan_repo(root: Path) -> list[str]:
    found: list[str] = []
    for f in tracked_files(root):
        p = root / f
        if not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        found.extend(scan_text(text, f))
    return found


# ---- self-test: positive (must be flagged) and negative (must pass) cases ----------------------
DENY = [
    "docker run -d postgres:16",
    "docker run postgres:15 psql --version",
    "docker run -d --name r redis",
    "docker run -d mirror.gcr.io/library/postgres:18-alpine",
    "docker container run -d postgres",
    "docker create mysql:8",
    "docker run --rm -v inner_py.sh:/tmp/inner_py.sh alpine sh /tmp/inner_py.sh",
    "docker run -d -v /data busybox sleep 1",
    "MSYS_NO_PATHCONV=1 docker run -d postgres:16",
    "echo hi && docker run -d mongo:7",
    "docker run -d -v ./cfg:/etc/cfg postgres:16",
    "docker run -d bitnamilegacy/minio:2025.4.22",
    "docker run -d prom/prometheus:v3.5.0",
    "docker run -d postgres:16 | tee out.txt",
    "docker rm -f restore-test",
    "docker container rm x",
    "docker rm x y",
]
ALLOW = [
    "docker run --rm postgres:16 psql --version",
    "docker run -d --rm redis:8",
    "docker run -d -v pgdata:/var/lib/postgresql/data postgres:16",
    "docker run -d -v pg18:/var/lib/postgresql postgres:18",
    "docker run -d --tmpfs /var/lib/postgresql/data postgres:16",
    "docker run -d --mount type=volume,src=r,dst=/data redis:8",
    "docker run -d --name web nginx:alpine",
    "docker run --rm -v ./inner_py.sh:/tmp/x alpine sh /tmp/x",
    'docker run --rm -v "$PWD/tests:/e2e:ro" alpine ls',
    "docker run --rm -v C:\\Users\\x:/in:ro alpine ls",
    'docker run --rm -v "${project}_miniodata:/data:ro" alpine ls',
    "docker ps -a",
    "docker compose run --rm api",
    "docker exec db psql -U x",
    "echo 'docker run -d postgres'",
    'docker run --rm "$GITLEAKS" git /repo',
    "docker run --rm postgres:16 pg_dump | gzip > out.sql.gz",
    "docker rm -fv restore-test",
    "docker rm -v x",
    "docker rm --volumes --force x",
    "docker rm -f -v x",
    "docker container rm -v x",
    "docker rmi alpine",
    "docker compose rm -f",
    "docker stop restore-test",
]


def selftest() -> int:
    bad = [c for c in DENY if not check_command(c)] + [c for c in ALLOW if check_command(c)]
    # logical-line handling in files
    cases = {
        "a.sh": ("docker run -d \\\n  --name db \\\n  postgres:16\n", True),
        "a.ps1": ("& docker run -d `\n  redis:7\n", True),
        "package.json": ('{"s": "docker run -v \\"%cd%\\":/w alpine ls"}\n', False),
        "ci.yml": ("steps:\n  - run: docker run -d postgres:16\n", True),
        "ok.sh": ("docker run --rm \\\n  postgres:16 psql\n", False),
        "r.md": (
            "text docker run -d postgres:16 outside a fence\n"
            "```bash\ndocker run --rm postgres:16\n```\n",
            False,
        ),
        "r2.md": ("```bash\ndocker run -d postgres:16\n```\n", True),
        "ign.sh": (
            "# docker-run-guard: ignore -- long-lived fixture\ndocker run -d postgres:16\n",
            False,
        ),
        "ign2.sh": ("docker run -d postgres:16  # docker-run-guard: ignore -- fixture\n", False),
        "noign.sh": ("# docker-run-guard: ignore\n\ndocker run -d postgres:16\n", True),
        "comment.sh": ("# docker run -d postgres:16 would leak\n# docker rm -f x\n", False),
        "label.yml": ("- name: Docker leaks (docker run -d postgres, docker rm -f x)\n", False),
        "label2.yml": ("    name: docker rm without -v\n", False),
        "after_comment.yml": ("# note\n- run: docker rm -f x\n", True),
    }
    for name, (text, should_flag) in cases.items():
        if bool(scan_text(text, name)) != should_flag:
            bad.append(f"file case {name}")
    if bad:
        print("self-test FAILED:", *bad, sep="\n  ", file=sys.stderr)
        return 2
    print(f"self-test ok: {len(DENY)} denied, {len(ALLOW)} allowed, {len(cases)} file cases")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=".", help="repository to scan (default: cwd)")
    ap.add_argument("--selftest", action="store_true", help="run the built-in rule tests and exit")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    root = Path(args.root).resolve()
    found = scan_repo(root)
    if found:
        print(
            "docker run would leak volumes (see rules in this file's docstring):", file=sys.stderr
        )
        for f in found:
            print("  " + f, file=sys.stderr)
        return 1
    print("docker run guard: no leaking `docker run` found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
