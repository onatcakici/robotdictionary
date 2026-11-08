"""Discover robot candidates from Wikidata and English Wikipedia and fetch their facts.
Runs on GitHub Actions (open network). Writes raw/*.json."""
import json, os, re, sys, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

UA = "RobotDictionaryBot/1.0 (https://robotdictionary.com; contact@robotdictionary.com)"
OUT = sys.argv[1] if len(sys.argv) > 1 else "raw"
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "log.txt"), "w")
def log(*a):
    s = " ".join(str(x) for x in a)
    print(s); LOG.write(s + "\n"); LOG.flush()

def get(url, data=None, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r)
        except Exception as e:
            log("retry", i, url[:120], repr(e)[:200]); time.sleep(3 * (i + 1))
    return None

def sparql(q):
    d = get("https://query.wikidata.org/sparql", urllib.parse.urlencode({"query": q, "format": "json"}).encode())
    if not d: return []
    return [{k: v["value"] for k, v in b.items()} for b in d["results"]["bindings"]]

def qid(uri): return uri.rsplit("/", 1)[-1]

cands = {}  # qid -> set(origins)
def add(q, origin):
    cands.setdefault(q, set()).add(origin)

# 1. instances under robot
for r in sparql("SELECT DISTINCT ?item WHERE { ?item wdt:P31/wdt:P279* wd:Q11012 . }"):
    add(qid(r["item"]), "wd:instance")
log("after instances", len(cands))
# 2. product models: subclasses of robot with maker or developer
for r in sparql("SELECT DISTINCT ?item WHERE { ?item wdt:P279+ wd:Q11012 . ?item wdt:P176|wdt:P178 ?m . }"):
    add(qid(r["item"]), "wd:model")
log("after models", len(cands))
# 3. rovers and other robot like classes not under robot
for label in ["Mars rover", "lunar rover", "rover", "planetary rover", "space rover", "robotic arm",
              "unmanned ground vehicle", "autonomous underwater vehicle", "remotely operated underwater vehicle",
              "robotic lawn mower", "exoskeleton", "powered exoskeleton", "surgical robot", "telepresence robot",
              "robotic vacuum cleaner", "quadruped robot", "educational robot", "robot kit", "humanoid robot"]:
    q = f"""SELECT DISTINCT ?item WHERE {{ ?cls rdfs:label "{label}"@en . ?item wdt:P31/wdt:P279* ?cls . }} LIMIT 3000"""
    rows = sparql(q)
    for r in rows: add(qid(r["item"]), "wd:class:" + label)
    log("class", label, len(rows)); time.sleep(1)
log("after classes", len(cands))

# 4. English Wikipedia category crawl
API = "https://en.wikipedia.org/w/api.php"
SEEDS = ["Robots", "Humanoid robots", "Mars rovers", "Lunar rovers", "Rovers", "Industrial robots",
         "Medical robots", "Surgical robots", "Robotic surgery", "Unmanned ground vehicles",
         "Autonomous underwater vehicles", "Remotely operated underwater vehicles", "Military robots",
         "Robotic vacuum cleaners", "Robot kits", "Educational robots", "Social robots", "Entertainment robots",
         "Robotic animals", "Robotic dogs", "Legged robots", "Bipedal robots", "Quadrupedal robots",
         "Delivery robots", "Agricultural robots", "Space robots", "Telepresence robots", "Robotic arms",
         "Robotic manipulators", "Mobile robots", "Domestic robots", "Personal robots", "Service robots",
         "Robotic lawn mowers", "Toy robots", "Robotic toys", "1950s robots", "1960s robots", "1970s robots",
         "1980s robots", "1990s robots", "2000s robots", "2010s robots", "2020s robots", "Robots of Japan",
         "Robots of the United States", "Robots of China", "Robots of South Korea", "Robots of Germany",
         "Robots of the United Kingdom", "Robots of France", "Robots of Italy", "Robots of Switzerland",
         "Robots of Canada", "Robots of Russia", "Robots of India", "Robots of Spain", "Robots by country",
         "Robots by decade", "Animatronic robots", "Androids", "Gynoids", "Swarm robots", "Snake robots",
         "Underwater robots", "Rescue robots", "Bomb disposal robots", "Robotic exoskeletons", "Exoskeletons",
         "Robotic hands", "Self-driving delivery robots", "Lunar sample return robots", "Robot vacuum cleaners"]
BAD = re.compile(r"fiction|film|television|tv series|video game|comic|character|novel|book|competition|event|"
                 r"compan|manufacturer|people|roboticist|engineer|scientist|researcher|organi[sz]ation|laborator|"
                 r"software|programming|in popular culture|media|music|song|album|band|award|conference|journal|"
                 r"standard|ethic|law|concept|theor|algorithm|stub|template|list|museum|festival|series|anime|manga|"
                 r"toyline|transformers|gundam|star wars|doctor who|mecha|game|sport|league|team|school|"
                 r"universit|institute|history of|portal|wikipedia|image|photo|logo|people", re.I)
seen_cats, pages = set(), {}
def crawl(cat, depth, path):
    if cat in seen_cats or depth > 3: return
    seen_cats.add(cat)
    cont = {}
    while True:
        params = {"action": "query", "list": "categorymembers", "cmtitle": "Category:" + cat, "cmtype": "page|subcat",
                  "cmlimit": "500", "format": "json", "formatversion": "2", **cont}
        d = get(API + "?" + urllib.parse.urlencode(params))
        if not d: return
        for m in d.get("query", {}).get("categorymembers", []):
            t = m["title"]
            if m["ns"] == 14:
                sub = t.split(":", 1)[1]
                if not BAD.search(sub): crawl(sub, depth + 1, path + [sub])
            elif m["ns"] == 0:
                pages.setdefault(t, set()).add("/".join(path))
        if "continue" in d: cont = d["continue"]
        else: break
for s in SEEDS:
    crawl(s, 0, [s])
log("categories", len(seen_cats), "pages", len(pages))

# map pages -> qid (+ shortdesc)
titles = sorted(pages)
page_qid = {}
for i in range(0, len(titles), 50):
    chunk = titles[i:i + 50]
    d = get(API + "?" + urllib.parse.urlencode({"action": "query", "prop": "pageprops", "titles": "|".join(chunk),
                                                 "redirects": "1", "format": "json", "formatversion": "2"}))
    if not d: continue
    norm = {}
    for n in d["query"].get("normalized", []) + d["query"].get("redirects", []): norm[n["to"]] = n["from"]
    for p in d["query"].get("pages", []):
        q = p.get("pageprops", {}).get("wikibase_item")
        if q:
            src = norm.get(p["title"], p["title"])
            page_qid[p["title"]] = q
            add(q, "wp:" + "|".join(sorted(pages.get(src, pages.get(p["title"], {"?"})))))
log("after wikipedia", len(cands))

# 5. entity details
PROPS = ["P31", "P279", "P176", "P178", "P170", "P495", "P17", "P571", "P577", "P580", "P582", "P576", "P2048", "P2067",
         "P2043", "P2049", "P18", "P856", "P1813", "P361", "P127", "P1416", "P366", "P155", "P156", "P144", "P2283",
         "P4908", "P5006", "P973", "P1324", "P2670", "P527", "P1056", "P2052", "P2109", "P1424", "P61", "P138"]
ents = {}
ids = sorted(cands)
def fetch_ents(chunk):
    d = get("https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode({
        "action": "wbgetentities", "ids": "|".join(chunk), "props": "labels|descriptions|aliases|claims|sitelinks",
        "languages": "en", "sitefilter": "enwiki", "format": "json"}))
    return d.get("entities", {}) if d else {}
def slim(e):
    out = {"id": e.get("id"), "label": e.get("labels", {}).get("en", {}).get("value"),
           "desc": e.get("descriptions", {}).get("en", {}).get("value"),
           "aliases": [a["value"] for a in e.get("aliases", {}).get("en", [])],
           "enwiki": e.get("sitelinks", {}).get("enwiki", {}).get("title"), "claims": {}}
    for p in PROPS:
        vals = []
        for c in e.get("claims", {}).get(p, []):
            if c.get("rank") == "deprecated": continue
            dv = c.get("mainsnak", {}).get("datavalue")
            if not dv: continue
            v = dv["value"]
            if isinstance(v, dict) and "id" in v: v = {"id": v["id"]}
            elif isinstance(v, dict) and "time" in v: v = {"time": v["time"], "precision": v.get("precision")}
            elif isinstance(v, dict) and "amount" in v: v = {"amount": v["amount"], "unit": v.get("unit", "").rsplit("/", 1)[-1]}
            refs = []
            for ref in c.get("references", [])[:3]:
                for rp in ("P854", "P248"):
                    for sn in ref.get("snaks", {}).get(rp, []):
                        rv = sn.get("datavalue", {}).get("value")
                        if rv: refs.append({rp: rv if isinstance(rv, str) else rv.get("id")})
            vals.append({"v": v, "rank": c.get("rank"), "refs": refs})
        if vals: out["claims"][p] = vals
    return out
with ThreadPoolExecutor(4) as ex:
    for res in ex.map(fetch_ents, [ids[i:i + 50] for i in range(0, len(ids), 50)]):
        for k, e in res.items():
            if "missing" not in e: ents[k] = slim(e)
log("entities", len(ents))
# labels for referenced items
ref_ids = set()
for e in ents.values():
    for p, vals in e["claims"].items():
        for v in vals:
            if isinstance(v["v"], dict) and "id" in v["v"]: ref_ids.add(v["v"]["id"])
            for r in v["refs"]:
                if "P248" in r and isinstance(r["P248"], str): ref_ids.add(r["P248"])
for u in ("Q11573", "Q174728", "Q11570", "Q174789", "Q218593", "Q100995"):
    ref_ids.add(u)
labels = {}
def fetch_labels(chunk):
    d = get("https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode({
        "action": "wbgetentities", "ids": "|".join(chunk), "props": "labels|descriptions|claims|sitelinks", "languages": "en",
        "sitefilter": "enwiki", "format": "json"}))
    out = {}
    for k, e in (d or {}).get("entities", {}).items():
        cl = e.get("claims", {})
        def first_id(p):
            for c in cl.get(p, []):
                dv = c.get("mainsnak", {}).get("datavalue")
                if dv and isinstance(dv["value"], dict) and "id" in dv["value"]: return dv["value"]["id"]
        def first_str(p):
            for c in cl.get(p, []):
                dv = c.get("mainsnak", {}).get("datavalue")
                if dv and isinstance(dv["value"], str): return dv["value"]
        out[k] = {"label": e.get("labels", {}).get("en", {}).get("value"), "desc": e.get("descriptions", {}).get("en", {}).get("value"),
                  "country": first_id("P17") or first_id("P495"), "hq": first_id("P159"), "website": first_str("P856"),
                  "enwiki": e.get("sitelinks", {}).get("enwiki", {}).get("title"),
                  "p31": [c["mainsnak"]["datavalue"]["value"]["id"] for c in cl.get("P31", []) if c.get("mainsnak", {}).get("datavalue")]}
    return out
rl = sorted(ref_ids)
with ThreadPoolExecutor(4) as ex:
    for res in ex.map(fetch_labels, [rl[i:i + 50] for i in range(0, len(rl), 50)]):
        labels.update(res)
# second hop for maker countries
more = {v["country"] for v in labels.values() if v.get("country") and v["country"] not in labels}
more |= {v["hq"] for v in labels.values() if v.get("hq") and v["hq"] not in labels}
ml = sorted(more)
with ThreadPoolExecutor(4) as ex:
    for res in ex.map(fetch_labels, [ml[i:i + 50] for i in range(0, len(ml), 50)]):
        labels.update(res)
log("labels", len(labels))

# 6. Wikipedia summaries (extract is CC BY-SA 4.0; stored for attribution-required excerpts and fact checking)
def summary(title):
    d = get("https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(title.replace(" ", "_"), safe=""))
    time.sleep(0.15)
    if not d: return title, None
    return title, {"extract": d.get("extract"), "description": d.get("description"), "type": d.get("type"),
                   "thumb": (d.get("thumbnail") or {}).get("source"), "url": d.get("content_urls", {}).get("desktop", {}).get("page"),
                   "timestamp": d.get("timestamp")}
wtitles = sorted({e["enwiki"] for e in ents.values() if e.get("enwiki")})
sums = {}
with ThreadPoolExecutor(4) as ex:
    for t, s in ex.map(summary, wtitles):
        if s: sums[t] = s
log("summaries", len(sums))

json.dump({k: sorted(v) for k, v in cands.items()}, open(os.path.join(OUT, "candidates.json"), "w"), indent=0)
json.dump(ents, open(os.path.join(OUT, "entities.json"), "w"))
json.dump(labels, open(os.path.join(OUT, "labels.json"), "w"))
json.dump(sums, open(os.path.join(OUT, "summaries.json"), "w"))
json.dump({k: sorted(v) for k, v in pages.items()}, open(os.path.join(OUT, "wp_pages.json"), "w"), indent=0)
json.dump(sorted(seen_cats), open(os.path.join(OUT, "wp_categories.json"), "w"), indent=0)
log("done")
