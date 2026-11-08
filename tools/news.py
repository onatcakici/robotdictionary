#!/usr/bin/env python3
"""Collect robotics headlines from publishers' feeds and link them to dictionary entries.

Only the headline, link, publisher and date are kept. Articles stay on the publishers' sites.
Writes data/news.json.
"""
import datetime as dt, email.utils, html, json, os, re, time, unicodedata, urllib.request
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENT = os.path.join(ROOT, "data", "entries")
OUT = os.path.join(ROOT, "data", "news.json")
UA = "RobotDictionaryBot/1.0 (https://robotdictionary.com; contact@robotdictionary.com)"
NOW = dt.datetime.now(dt.timezone.utc)
KEEP_DAYS = 45
FEEDS = [
    ("IEEE Spectrum", "https://spectrum.ieee.org/feeds/topic/robotics.rss", False),
    ("The Robot Report", "https://www.therobotreport.com/feed/", False),
    ("TechCrunch", "https://techcrunch.com/category/robotics/feed/", False),
    ("Robohub", "https://robohub.org/feed/", False),
    ("New Atlas", "https://newatlas.com/robotics/index.rss", False),
    ("MIT News", "https://news.mit.edu/topic/mitrobotics-rss.xml", False),
    ("Interesting Engineering", "https://interestingengineering.com/feed", True),
    ("The Verge", "https://www.theverge.com/rss/index.xml", True),
    ("Electrek", "https://electrek.co/feed/", True),
]
ROBOTY = re.compile(r"\brobot|\brover\b|humanoid|android|exoskeleton|quadruped", re.I)
STOP_NAMES = {"robot", "rover", "the", "one", "max", "pro", "go", "dot", "eve", "neo", "iron", "alex", "grace", "rhino", "hound", "flex", "relay",
              "beam", "cue", "dash", "root", "ultra", "eden", "nori", "odin", "grip", "boost", "pave", "darwin", "manifold", "mobot", "tally",
              "chuck", "spirit", "opportunity", "curiosity", "perseverance", "freight", "fetch", "scout", "sherpa", "hero", "atom", "toro",
              "phoenix", "sophia", "apollo", "atlas", "spot", "digit", "pepper", "astro", "vector", "optimus", "figure", "stretch", "proteus"}

def log(*a): print(*a, flush=True)

def fetch(url):
    for i in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml"})
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read()
        except Exception as e:
            log("retry", i, url, repr(e)[:120]); time.sleep(3)
    return None

def text(el):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", "".join(el.itertext()) if el is not None else ""))).strip()

def parse_date(s):
    if not s: return None
    try:
        d = email.utils.parsedate_to_datetime(s)
    except Exception:
        try: d = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception: return None
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)

def items_of(raw):
    out = []
    try: root = ET.fromstring(raw)
    except Exception as e:
        log("bad feed", repr(e)[:80]); return out
    ns = {"a": "http://www.w3.org/2005/Atom"}
    for it in root.iter("item"):
        out.append({"title": text(it.find("title")), "url": (it.findtext("link") or "").strip(), "date": parse_date(it.findtext("pubDate")),
                    "summary": text(it.find("description"))[:600]})
    for it in root.iter("{http://www.w3.org/2005/Atom}entry"):
        link = it.find("a:link[@rel='alternate']", ns)
        if link is None: link = it.find("a:link", ns)
        out.append({"title": text(it.find("a:title", ns)), "url": link.get("href") if link is not None else "",
                    "date": parse_date(it.findtext("a:published", namespaces=ns) or it.findtext("a:updated", namespaces=ns)),
                    "summary": text(it.find("a:summary", ns))[:600]})
    return out

def norm(s):
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()

def main():
    entries = {}
    for fn in os.listdir(ENT):
        if fn.endswith(".json"): entries[fn[:-5]] = json.load(open(os.path.join(ENT, fn), encoding="utf-8"))
    pats = []
    for eid, e in entries.items():
        names = [e["name"]] + [a for a in e.get("aka", []) if len(a) > 3]
        maker = norm(e.get("maker") or "")
        mk = [w for w in re.split(r"\s+and\s+|,", maker) if w.strip()]
        mk_pat = re.compile("|".join(re.escape(m.strip()) for m in mk if len(m.strip()) > 2)) if mk else None
        for n in names:
            n0 = re.sub(r"\s*\(.*?\)", "", norm(n)).strip()
            if len(n0) < 3: continue
            safe = bool(re.search(r"\d", n0) or re.search(r"[a-z][A-Z]", n0) or len(n0.split()) > 1) and n0.lower() not in STOP_NAMES
            own = mk_pat if (mk_pat is not None and not any(m.strip().lower() in n0.lower() or n0.lower() in m.strip().lower() for m in mk)) else None
            pats.append((eid, re.compile(r"(?<![\w-])" + re.escape(n0) + r"(?![\w-])"), safe, own, n0.lower(), e.get("status")))
    old = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else []
    seen = {o["url"] for o in old}
    fresh = []
    for source, url, needs_robot in FEEDS:
        raw = fetch(url)
        if not raw: log("feed failed", source); continue
        its = items_of(raw)
        log(source, len(its))
        for it in its:
            if not it["title"] or not it["url"].startswith("http") or it["url"] in seen: continue
            d = it["date"] or NOW
            if (NOW - d).days > KEEP_DAYS or d > NOW + dt.timedelta(days=1): continue
            blob = norm(it["title"] + " " + it["summary"])
            hits = []
            for eid, pat, safe, mk_pat, key, status in pats:
                if pat.search(blob) and (safe or (mk_pat is not None and mk_pat.search(blob))):
                    if eid not in [h[0] for h in hits]: hits.append((eid, key, status))
            ids = []
            for eid, key, status in hits:
                same = [h for h in hits if h[1] == key]
                if len(same) > 1 and status in ("retired", "discontinued", "completed", "lost") and any(h[2] not in ("retired", "discontinued", "completed", "lost") for h in same):
                    continue
                ids.append(eid)
            if needs_robot and not ids and not ROBOTY.search(it["title"]): continue
            fresh.append({"title": it["title"][:220], "url": it["url"], "source": source, "date": d.date().isoformat(), "ids": ids[:4]})
            seen.add(it["url"])
    allitems = [o for o in old + fresh if (NOW.date() - dt.date.fromisoformat(o["date"])).days <= KEEP_DAYS]
    allitems.sort(key=lambda o: (o["date"], bool(o["ids"])), reverse=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(allitems[:500], f, indent=1, ensure_ascii=False); f.write("\n")
    log("new headlines", len(fresh), "linked", sum(1 for o in fresh if o["ids"]), "kept", len(allitems[:500]))

if __name__ == "__main__":
    main()
