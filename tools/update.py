#!/usr/bin/env python3
"""Daily revision of the Robot Dictionary. Runs on GitHub Actions.

1. Refresh entries linked to Wikidata: fill missing maker, country, year and sources, note new end dates.
2. Link entries that have no Wikidata item yet, when the match is unambiguous.
3. Add a small number of newly documented robots from Wikidata and Wikipedia.
4. Refresh Y Combinator company status for YC entries and queue new YC robotics companies for review.
Writes data/entries/*.json, data/state/*.json. The build step renders the site afterwards.
"""
import datetime as dt, json, os, re, sys, time, unicodedata, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENT = os.path.join(ROOT, "data", "entries")
STATE = os.path.join(ROOT, "data", "state")
UA = "RobotDictionaryBot/1.0 (https://robotdictionary.com; contact@robotdictionary.com)"
TODAY = (os.environ.get("BUILD_DATE") or dt.datetime.now(dt.timezone.utc).date().isoformat())
MAX_NEW = int(os.environ.get("MAX_NEW", "8"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from robot_filter import is_robot, section_for, kind_for, COUNTRY

def log(*a): print(*a, flush=True)

def get(url, data=None, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r)
        except Exception as e:
            log("retry", i, url[:100], repr(e)[:160]); time.sleep(4 * (i + 1))
    return None

def sparql(q):
    d = get("https://query.wikidata.org/sparql", urllib.parse.urlencode({"query": q, "format": "json"}).encode())
    return [{k: v["value"] for k, v in b.items()} for b in d["results"]["bindings"]] if d else []

def wb(ids, props="labels|descriptions|aliases|claims|sitelinks"):
    out = {}
    def one(chunk):
        d = get("https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode({"action": "wbgetentities", "ids": "|".join(chunk), "props": props,
                                                                               "languages": "en", "sitefilter": "enwiki", "format": "json"}))
        time.sleep(0.3)
        return (d or {}).get("entities", {})
    chunks = [ids[i:i + 50] for i in range(0, len(ids), 50)]
    with ThreadPoolExecutor(2) as ex:
        for res in ex.map(one, chunks): out.update({k: v for k, v in res.items() if "missing" not in v})
    return out

def slugify(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")

def load_json(p, default):
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else default

def save_json(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f: json.dump(obj, f, indent=1, ensure_ascii=False); f.write("\n")

def label(e): return (e.get("labels", {}).get("en") or {}).get("value")
def desc(e): return (e.get("descriptions", {}).get("en") or {}).get("value") or ""
def enwiki(e): return (e.get("sitelinks", {}).get("enwiki") or {}).get("title")
def ids_of(e, p):
    out = []
    for c in e.get("claims", {}).get(p, []):
        if c.get("rank") == "deprecated": continue
        v = (c.get("mainsnak", {}).get("datavalue") or {}).get("value")
        if isinstance(v, dict) and "id" in v: out.append(v["id"])
    return out
def years_of(e, p):
    out = []
    for c in e.get("claims", {}).get(p, []):
        v = (c.get("mainsnak", {}).get("datavalue") or {}).get("value")
        m = re.match(r"\+(\d{4})", (v or {}).get("time", "") if isinstance(v, dict) else "")
        if m: out.append(int(m.group(1)))
    return out
YEAR_PROPS = ("P571", "P577", "P5204", "P729", "P606", "P619", "P1619", "P580", "P575", "P2031")
def first_year(w):
    """Year an item was made or first shown: inception or publication first, then the later milestones."""
    now = dt.date.fromisoformat(TODAY).year + 1
    ys = [y for y in years_of(w, "P571") + years_of(w, "P577") if 1700 <= y <= now]
    if ys: return min(ys)
    for p in YEAR_PROPS[2:]:
        ys = [y for y in years_of(w, p) if 1700 <= y <= now]
        if ys: return min(ys)
    return None

def str_of(e, p):
    for c in e.get("claims", {}).get(p, []):
        v = (c.get("mainsnak", {}).get("datavalue") or {}).get("value")
        if isinstance(v, str): return v

def wp_url(t): return "https://en.wikipedia.org/wiki/" + urllib.parse.quote(t.replace(" ", "_"), safe="():,'!")
def add_ref(entry, ref):
    if any(r["url"] == ref["url"] for r in entry.setdefault("refs", [])): return False
    entry["refs"].append(ref); return True

def main():
    entries = {}
    for fn in os.listdir(ENT):
        if fn.endswith(".json"): entries[fn[:-5]] = load_json(os.path.join(ENT, fn), {})
    changes = load_json(os.path.join(STATE, "changes.json"), [])
    block = set(load_json(os.path.join(STATE, "blocklist.json"), []))
    touched = {}
    def note(eid, kind, text=""):
        if eid in touched: return
        touched[eid] = 1
        changes.append({"date": TODAY, "id": eid, "type": kind, "note": text})

    # ---- 1. refresh linked entries
    linked = {e["ids"]["wikidata"]: eid for eid, e in entries.items() if (e.get("ids") or {}).get("wikidata")}
    known_q = set(linked) | block
    ents = wb(sorted(linked)) if linked else {}
    need_labels = set()
    for q, w in ents.items():
        for p in ("P176", "P178", "P170", "P495", "P17"): need_labels.update(ids_of(w, p)[:2])
    labs = wb(sorted(need_labels), "labels|claims") if need_labels else {}
    def lab(q): return label(labs.get(q, {})) or ""
    for q, w in ents.items():
        eid = linked[q]; e = entries[eid]; changed = []
        t = enwiki(w)
        if t and add_ref(e, {"label": "Wikipedia, " + t, "url": wp_url(t), "kind": "wikipedia"}): changed.append("source")
        if not e.get("maker"):
            mk = [lab(x) for x in (ids_of(w, "P176") or ids_of(w, "P178"))[:2] if lab(x)]
            if mk: e["maker"] = " and ".join(mk); changed.append("maker")
        if not e.get("country"):
            c = (ids_of(w, "P495") or ids_of(w, "P17"))[:1]
            if c and lab(c[0]) and "relations" not in lab(c[0]).lower(): e["country"] = COUNTRY.get(lab(c[0]), lab(c[0])); changed.append("country")
        if not e.get("year"):
            y = first_year(w)
            if y: e["year"] = str(y); changed.append("year")
        end = years_of(w, "P576") + years_of(w, "P582")
        if end and e.get("status") in ("production", "service", "pilot") and not e.get("status_locked"):
            e["status"] = "retired" if e.get("section") != "rovers" else "completed"; changed.append("status")
        if changed:
            e["revised"] = TODAY; note(eid, "revised", ", ".join(sorted(set(changed))) + " from Wikidata")

    if os.environ.get("ONLY_REFRESH"):
        for eid, e in entries.items(): save_json(os.path.join(ENT, eid + ".json"), e)
        save_json(os.path.join(STATE, "changes.json"), changes[-5000:])
        log("refreshed only", sum(1 for c in changes if c["date"] == TODAY)); return

    # ---- 2. link unlinked entries when unambiguous
    unl = [eid for eid, e in entries.items() if not (e.get("ids") or {}).get("wikidata") and not e.get("no_wikidata")]
    tried = load_json(os.path.join(STATE, "link_attempts.json"), {})
    unl = [eid for eid in unl if tried.get(eid, "") < (dt.date.fromisoformat(TODAY) - dt.timedelta(days=30)).isoformat()][:60]
    for eid in unl:
        e = entries[eid]; tried[eid] = TODAY
        d = get("https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode({"action": "wbsearchentities", "search": e["name"], "language": "en",
                                                                               "type": "item", "limit": "7", "format": "json"}))
        hits = []
        mk = (e.get("maker") or "").lower().split(" ")[0]
        for h in (d or {}).get("search", []):
            ds = (h.get("description") or "").lower()
            if not re.search(r"robot|rover|android|humanoid|exoskeleton|underwater vehicle", ds): continue
            if h["id"] in linked: continue
            score = (2 if mk and len(mk) > 2 and mk in ds else 0) + (1 if (h.get("label") or "").lower() == e["name"].lower() else 0)
            if score >= 2: hits.append(h["id"])
        if len(hits) == 1:
            q = hits[0]; w = wb([q]).get(q)
            if not w: continue
            e.setdefault("ids", {})["wikidata"] = q; linked[q] = eid; known_q.add(q)
            add_ref(e, {"label": f"Wikidata, {label(w) or e['name']} ({q})", "url": "https://www.wikidata.org/wiki/" + q, "kind": "wikidata"})
            t = enwiki(w)
            if t: add_ref(e, {"label": "Wikipedia, " + t, "url": wp_url(t), "kind": "wikipedia"})
            e["revised"] = TODAY; note(eid, "revised", "sources added")
        time.sleep(0.3)
    save_json(os.path.join(STATE, "link_attempts.json"), tried)

    # ---- 3. new robots from Wikidata, a few a day
    rows = sparql("""SELECT DISTINCT ?item WHERE {
      { ?item wdt:P31/wdt:P279* wd:Q11012 . }
      UNION { VALUES ?l { "lunar rover"@en "Mars rover"@en "rover"@en "autonomous underwater vehicle"@en "remotely operated underwater vehicle"@en
                          "powered exoskeleton"@en }
              ?cls rdfs:label ?l . ?item wdt:P31 ?cls . }
      ?art schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> . }""")
    cand = [r["item"].rsplit("/", 1)[-1] for r in rows]
    cand = [q for q in cand if q not in known_q]
    log("new candidates", len(cand))
    deferred = 0
    added = 0
    if cand:
        cents = wb(cand[:600])
        cl_ids = set()
        for w in cents.values():
            cl_ids.update(ids_of(w, "P31")[:6]); cl_ids.update(ids_of(w, "P279")[:4])
            for p in ("P176", "P178", "P495", "P17"): cl_ids.update(ids_of(w, p)[:2])
        labs2 = wb(sorted(cl_ids), "labels|claims") if cl_ids else {}
        lab2 = lambda q: label(labs2.get(q, {})) or ""
        queue = []
        names = {}
        for eid0, e0 in entries.items():
            for n0 in [e0.get("name", "")] + list(e0.get("aka") or []):
                if n0: names.setdefault(slugify(n0), eid0)
        deferred = 0
        for q, w in cents.items():
            cids = ids_of(w, "P31")[:6] + ids_of(w, "P279")[:4]
            if any(x not in labs2 for x in cids):
                deferred += 1; continue          # labels did not load; look again tomorrow rather than judge blind
            classes = [lab2(x) for x in cids]
            ok, why = is_robot(classes, desc(w))
            if not ok: block.add(q); continue
            same = names.get(slugify(re.sub(r"\s*\((robot|rover|robotics)\)$", "", label(w) or "")))
            if same:
                e0 = entries[same]
                if not (e0.get("ids") or {}).get("wikidata"):
                    e0.setdefault("ids", {})["wikidata"] = q
                    add_ref(e0, {"label": f"Wikidata, {label(w)} ({q})", "url": "https://www.wikidata.org/wiki/" + q, "kind": "wikidata"})
                    if enwiki(w): add_ref(e0, {"label": "Wikipedia, " + enwiki(w), "url": wp_url(enwiki(w)), "kind": "wikipedia"})
                    e0["revised"] = TODAY; note(same, "revised", "linked to Wikidata")
                known_q.add(q); continue

            if not enwiki(w) or len(desc(w)) < 18: continue
            queue.append((q, w, classes))
        queue.sort(key=lambda t: -len(t[1].get("sitelinks", {})))
        # keep the dictionary above a thousand entries; otherwise a few new robots a day
        room = max(MAX_NEW, min(60, 1010 - len(entries)))
        for q, w, classes in queue[:room]:
            t = enwiki(w)
            s = get("https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(t.replace(" ", "_"), safe=""))
            name = re.sub(r"\s*\((robot|rover|robotics)\)$", "", label(w) or t)
            eid = slugify(name)
            if not eid or eid in entries: eid = f"{eid}-{q.lower()}"
            mk = [lab2(x) for x in (ids_of(w, "P176") or ids_of(w, "P178"))[:2] if lab2(x)]
            c = (ids_of(w, "P495") or ids_of(w, "P17"))[:1]
            y0 = first_year(w)
            d0 = desc(w).strip().rstrip(".")
            definition = d0[:1].upper() + d0[1:] + "."
            refs = [{"label": "Wikipedia, " + t, "url": wp_url(t), "kind": "wikipedia"},
                    {"label": f"Wikidata, {label(w) or name} ({q})", "url": "https://www.wikidata.org/wiki/" + q, "kind": "wikidata"}]
            site = str_of(w, "P856")
            if site: refs.insert(0, {"label": "Official website", "url": site, "kind": "official"})
            e = {"id": eid, "name": name, "aka": [], "section": section_for(classes, desc(w)), "kind": kind_for(classes, desc(w)),
                 "maker": " and ".join(mk), "country": COUNTRY.get(lab2(c[0]), lab2(c[0])) if c else "", "year": str(y0) if y0 else "",
                 "status": "", "def": definition, "body": [], "facts": [], "specs": [], "see": [], "refs": refs, "ids": {"wikidata": q},
                 "origin": "auto", "added": TODAY, "revised": TODAY, "old": []}
            ex = (s or {}).get("extract") or ""
            if ex:
                sent = re.split(r"(?<=[.!?])\s+", ex)
                text = " ".join(sent[:2])[:420]
                e["excerpt"] = {"text": text, "title": t, "url": wp_url(t)}
            entries[eid] = e; known_q.add(q); added += 1
            note(eid, "added", "from Wikidata and Wikipedia")
    log("added", added, "deferred", deferred)

    # ---- 4. Y Combinator
    yc_queue = load_json(os.path.join(STATE, "yc_queue.json"), [])
    tags = ["robotics", "medical-robotics", "robotic-surgery", "food-service-robots-and-machines", "swarm-robotics"]
    seen_slugs = {(e.get("ids") or {}).get("yc") for e in entries.values()} | {x["slug"] for x in yc_queue} | set(load_json(os.path.join(STATE, "yc_ignore.json"), []))
    allc = {}
    for t in tags:
        for c in get(f"https://yc-oss.github.io/api/tags/{t}.json") or []: allc[c["slug"]] = c
    for eid, e in entries.items():
        y = e.get("yc")
        if y and (e.get("ids") or {}).get("yc") in allc:
            c = allc[e["ids"]["yc"]]
            if c.get("status") and c["status"] != y.get("status"):
                y["status"] = c["status"]; e["revised"] = TODAY; note(eid, "revised", "company status from the YC directory")
    for slug, c in allc.items():
        if slug in seen_slugs: continue
        txt = ((c.get("one_liner") or "") + " " + (c.get("long_description") or "")).lower()
        if re.search(r"\b(robots? (that|for|to|which)|humanoids?|exoskeletons?|robotic (arms?|hands?|system|platform|kitchen)|(we )?build(s|ing)? (\w+ )?robots)\b", txt):
            yc_queue.append({"slug": slug, "name": c["name"], "batch": c.get("batch"), "one_liner": c.get("one_liner"), "url": c.get("url"), "found": TODAY})
    save_json(os.path.join(STATE, "yc_queue.json"), yc_queue[-300:])

    for eid, e in entries.items():
        save_json(os.path.join(ENT, eid + ".json"), e)
    save_json(os.path.join(STATE, "changes.json"), changes[-5000:])
    save_json(os.path.join(STATE, "blocklist.json"), sorted(block))
    log("revised", sum(1 for c in changes if c["date"] == TODAY))

if __name__ == "__main__":
    main()
