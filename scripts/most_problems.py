"""Find the Codeforces contests with the most problems (one problemset.problems request)."""

import collections
import json
import urllib.request

req = urllib.request.Request(
    "https://codeforces.com/api/problemset.problems",
    headers={"User-Agent": "cpstands/0.1 (+https://github.com/menarzullayev/cpstands)"},
)
data = json.load(urllib.request.urlopen(req, timeout=60))["result"]["problems"]
count: collections.Counter[int] = collections.Counter(p["contestId"] for p in data)
names = {}
req2 = urllib.request.Request(
    "https://codeforces.com/api/contest.list?gym=false",
    headers={"User-Agent": "cpstands/0.1"},
)
for c in json.load(urllib.request.urlopen(req2, timeout=60))["result"]:
    names[c["id"]] = (c["name"], c["type"], c["phase"])
for cid, n in count.most_common(8):
    print(n, cid, names.get(cid))
