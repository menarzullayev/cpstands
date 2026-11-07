"""Apply config/bot_profile.json to the bot through the Bot API.

Reads TELEGRAM_BOT_TOKEN from .env and never prints it. Standard library only.
Usage: python scripts/apply_bot_profile.py [--check] [--photo]
  --photo  re-upload the profile photo even if one is already set
  --check  only read back the current values (getMyName, ...) and compare.
"""
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8")


def load_token() -> str:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("TELEGRAM_BOT_TOKEN="):
            token = line.split("=", 1)[1].strip()
            if token:
                return token
    sys.exit("TELEGRAM_BOT_TOKEN is empty in .env")


TOKEN = load_token()


def call(method: str, **params):
    data = urllib.parse.urlencode(
        {k: v if isinstance(v, str) else json.dumps(v) for k, v in params.items()}
    ).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{TOKEN}/{method}", data=data)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return json.load(e)


CRLF = "\r\n"


def call_multipart(method: str, fields: dict, file_field: str, path: Path):
    boundary = "----cpstands" + uuid.uuid4().hex
    body = b""
    for k, v in fields.items():
        body += f'--{boundary}{CRLF}Content-Disposition: form-data; name="{k}"{CRLF}{CRLF}{v}{CRLF}'.encode()
    body += (
        f'--{boundary}{CRLF}Content-Disposition: form-data; name="{file_field}"; filename="{path.name}"{CRLF}'
        f"Content-Type: image/jpeg{CRLF}{CRLF}"
    ).encode()
    body += path.read_bytes() + CRLF.encode() + f"--{boundary}--{CRLF}".encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TOKEN}/{method}",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return json.load(e)


def apply_photo(rel_path: str, force: bool, check_only: bool) -> int:
    me = call("getMe")["result"]
    count = call("getUserProfilePhotos", user_id=me["id"], limit=1)["result"]["total_count"]
    if not check_only and (force or count == 0):
        res = call_multipart(
            "setMyProfilePhoto",
            {"photo": json.dumps({"type": "static", "photo": "attach://avatar"})},
            "avatar",
            ROOT / rel_path,
        )
        if not res.get("ok"):
            print(f"FAIL set profile photo: {res.get('description')}")
            return 1
        count = call("getUserProfilePhotos", user_id=me["id"], limit=1)["result"]["total_count"]
    print(f"{'ok' if count >= 1 else 'MISSING'}: profile_photo count = {count}")
    return 0 if count >= 1 else 1


# profile key -> (setter, getter, setter param, getter result key)
FIELDS = {
    "name": ("setMyName", "getMyName", "name", "name"),
    "description": ("setMyDescription", "getMyDescription", "description", "description"),
    "short_description": ("setMyShortDescription", "getMyShortDescription", "short_description", "short_description"),
}


SCOPES = {
    "default": {"type": "default"},
    "private": {"type": "all_private_chats"},
    "group": {"type": "all_group_chats"},
    "admins": {"type": "all_chat_administrators"},
}
LANGS = ["", "en", "ru", "uz"]  # "" = fallback for every other language (English text)


def build_menu(spec: dict, menu: str, lang: str):
    out = []
    for cid in spec["menus"][menu]:
        d = spec["defs"][cid]
        item = {"command": d["command"], "description": d["desc"][lang or "en"]}
        if d.get("is_ephemeral"):
            item["is_ephemeral"] = True
        out.append(item)
    return out


def _same_commands(got, want) -> bool:
    key = lambda c: (c["command"], c["description"], bool(c.get("is_ephemeral")))
    return [key(g) for g in got] == [key(w) for w in want]


def apply_commands(spec: dict, check_only: bool) -> int:
    bad = 0
    for menu, scope in SCOPES.items():
        for lang in LANGS:
            want = build_menu(spec, menu, lang)
            got = call("getMyCommands", scope=scope, language_code=lang).get("result", [])
            if not check_only and not _same_commands(got, want):
                res = call("setMyCommands", commands=want, scope=scope, language_code=lang)
                if not res.get("ok"):
                    print(f"FAIL set commands[{menu}/{lang or 'default'}]: {res.get('description')}")
                    bad += 1
                    continue
                got = call("getMyCommands", scope=scope, language_code=lang).get("result", [])
            same = _same_commands(got, want)
            if not same:
                bad += 1
            print(f"{'ok' if same else 'MISMATCH'}: commands[{menu}/{lang or 'default'}] = {[g['command'] for g in got]}")
    return bad


def main(check_only: bool) -> int:
    profile = json.loads((ROOT / "config" / "bot_profile.json").read_text(encoding="utf-8"))
    bad = 0
    for key, (setter, getter, param, rkey) in FIELDS.items():
        for lang, value in profile.get(key, {}).items():
            actual = call(getter, language_code=lang).get("result", {}).get(rkey)
            # Only write when different: Telegram rate-limits setMyName (about 24 h of "retry after").
            if not check_only and actual != value:
                res = call(setter, **{param: value}, language_code=lang)
                if not res.get("ok"):
                    print(f"FAIL set {key}[{lang or 'default'}]: {res.get('description')}")
                    bad += 1
                    continue
                actual = call(getter, language_code=lang).get("result", {}).get(rkey)
            status = "ok" if actual == value else "MISMATCH"
            if status != "ok":
                bad += 1
            print(f"{status}: {key}[{lang or 'default'}] = {actual!r}")
    if "commands" in profile:
        bad += apply_commands(profile["commands"], check_only)
    if "profile_photo" in profile:
        bad += apply_photo(profile["profile_photo"], "--photo" in sys.argv, check_only)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main("--check" in sys.argv))
