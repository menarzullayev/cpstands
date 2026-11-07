"""Apply config/bot_profile.json to the bot through the Bot API.

Reads TELEGRAM_BOT_TOKEN from .env and never prints it. Standard library only.
Usage: python scripts/apply_bot_profile.py [--check]
  --check  only read back the current values (getMyName, ...) and compare.
"""
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
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


# profile key -> (setter, getter, setter param, getter result key)
FIELDS = {
    "name": ("setMyName", "getMyName", "name", "name"),
    "description": ("setMyDescription", "getMyDescription", "description", "description"),
    "short_description": ("setMyShortDescription", "getMyShortDescription", "short_description", "short_description"),
}


def main(check_only: bool) -> int:
    profile = json.loads((ROOT / "config" / "bot_profile.json").read_text(encoding="utf-8"))
    bad = 0
    for key, (setter, getter, param, rkey) in FIELDS.items():
        for lang, value in profile.get(key, {}).items():
            if not check_only:
                res = call(setter, **{param: value}, language_code=lang)
                if not res.get("ok"):
                    print(f"FAIL set {key}[{lang or 'default'}]: {res.get('description')}")
                    bad += 1
                    continue
            got = call(getter, language_code=lang)
            actual = got.get("result", {}).get(rkey)
            status = "ok" if actual == value else "MISMATCH"
            if status != "ok":
                bad += 1
            print(f"{status}: {key}[{lang or 'default'}] = {actual!r}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main("--check" in sys.argv))
