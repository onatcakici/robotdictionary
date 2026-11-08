import json, os, re, time, urllib.parse, urllib.request
UA = "RobotDictionaryBot/1.0 (https://robotdictionary.com; contact@robotdictionary.com)"
def get(url):
    for i in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=40) as r: return json.load(r)
        except Exception as e:
            print("retry", url[:80], repr(e)[:80]); time.sleep(2)
out = {}
for fn in sorted(os.listdir("data/entries")):
    e = json.load(open(os.path.join("data/entries", fn), encoding="utf-8"))
    if re.match(r"\d{4}", e.get("year") or ""): continue
    t = next((urllib.parse.unquote(r["url"].rsplit("/wiki/", 1)[-1]) for r in e.get("refs") or [] if r.get("kind") == "wikipedia"), None)
    if not t: continue
    d = get("https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(t, safe=""))
    if d and d.get("extract"): out[e["id"]] = {"title": t, "extract": d["extract"][:1200]}
    time.sleep(0.15)
json.dump(out, open("data/leads.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print("leads", len(out))
