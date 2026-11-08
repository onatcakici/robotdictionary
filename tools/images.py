#!/usr/bin/env python3
"""Fetch small, freely licensed pictures for entries from Wikimedia Commons.

Pictures come from the image linked on an entry's Wikidata item, or the lead image of its
English Wikipedia article when that file is hosted on Commons. Each picture is saved twice,
as a plate (fits 480x360) and a thumbnail (fits 160x120), both WebP. Licence and author are
kept in data/images.json so pages can credit them.
"""
import datetime as dt, html, io, json, os, re, sys, time, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENT = os.path.join(ROOT, "data", "entries")
IMG = os.path.join(ROOT, "img")
META = os.path.join(ROOT, "data", "images.json")
TRIED = os.path.join(ROOT, "data", "state", "image_attempts.json")
UA = "RobotDictionaryBot/1.0 (https://robotdictionary.com; contact@robotdictionary.com)"
TODAY = os.environ.get("BUILD_DATE") or dt.datetime.now(dt.timezone.utc).date().isoformat()
MAX = int(os.environ.get("MAX_IMAGES", "120"))
PLATE, THUMB = (480, 360), (160, 120)

# Androids built as likenesses of real people are left without pictures.
EXCLUDE = {"geminoid-hi-1", "bina48", "albert-hubo", "nadine", "philip-k-dick-android", "geminoid-f", "geminoid-dk", "han-robot"}
PEOPLE = re.compile(r"\b(with|meets|meeting|visit|visits|visited|president|minister|prime|ceo|founder|professor|prof|dr|mayor|governor|senator|"
                    r"king|queen|prince|princess|pope|elon|musk|obama|trump|putin|modi|merkel|macron|jinping|abe|biden|clinton|bezos|zuckerberg|"
                    r"astronauts?|cosmonauts?|spacewalk|eva|crew|team|students?|children|kids|visitors?|operators?|technicians?|engineers?|"
                    r"scientists?|people|man|woman|men|women|boy|girl|portrait|selfie|STS-\d+|holding|riding)\b", re.I)
NOTPHOTO = re.compile(r"logo|diagram|schematic|drawing|patch|emblem|icon|insignia|\bmap\b|chart|graph|blueprint|sketch|render|cad\b|poster|stamp", re.I)
FREE = re.compile(r"^(cc0|cc[ -]by|public domain|pd|no restrictions|attribution|fal|free art)", re.I)

def log(*a): print(*a, flush=True)

def get(url, binary=False, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            return data if binary else json.loads(data)
        except Exception as e:
            log("retry", i, url[:90], repr(e)[:120]); time.sleep(3 * (i + 1))
    return None

def load(p, d):
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else d

def save(p, o):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f: json.dump(o, f, indent=1, ensure_ascii=False); f.write("\n")

def plain(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip()

def p18(qids):
    out = {}
    for i in range(0, len(qids), 50):
        d = get("https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode({"action": "wbgetentities", "ids": "|".join(qids[i:i + 50]),
                                                                               "props": "claims", "format": "json"}))
        for q, e in ((d or {}).get("entities") or {}).items():
            for c in e.get("claims", {}).get("P18", []):
                v = (c.get("mainsnak", {}).get("datavalue") or {}).get("value")
                if isinstance(v, str) and c.get("rank") != "deprecated": out[q] = v; break
        time.sleep(0.5)
    return out

def page_images(titles):
    out = {}
    for i in range(0, len(titles), 40):
        d = get("https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode({"action": "query", "prop": "pageimages", "piprop": "name",
                                                                              "titles": "|".join(titles[i:i + 40]), "redirects": "1", "format": "json"}))
        q = (d or {}).get("query", {})
        back = {}
        for n in q.get("normalized", []) + q.get("redirects", []): back[n["to"]] = back.get(n["from"], n["from"])
        for p in q.get("pages", {}).values():
            if p.get("pageimage"): out[back.get(p["title"], p["title"])] = p["pageimage"]
        time.sleep(0.5)
    return out

def commons_info(files):
    out = {}
    for i in range(0, len(files), 40):
        chunk = ["File:" + f for f in files[i:i + 40]]
        d = get("https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode({"action": "query", "titles": "|".join(chunk), "prop": "imageinfo",
                                                                                    "iiprop": "url|size|mime|extmetadata", "iiurlwidth": "960", "format": "json"}))
        q = (d or {}).get("query", {})
        back = {n["to"]: n["from"] for n in q.get("normalized", [])}
        for p in q.get("pages", {}).values():
            ii = (p.get("imageinfo") or [None])[0]
            if not ii or p.get("missing") is not None: continue
            name = back.get(p["title"], p["title"])[5:]
            out[name] = ii
        time.sleep(0.5)
    return out

def acceptable(name, ii):
    md = ii.get("extmetadata") or {}
    lic = plain((md.get("LicenseShortName") or {}).get("value"))
    if not FREE.match(lic or ""): return False, "licence " + (lic or "unknown")
    if "personality" in plain((md.get("Restrictions") or {}).get("value")).lower(): return False, "personality rights"
    if (ii.get("mime") or "") not in ("image/jpeg", "image/png", "image/webp", "image/tiff"): return False, "type " + str(ii.get("mime"))
    text = name + " " + plain((md.get("ImageDescription") or {}).get("value"))[:300]
    if NOTPHOTO.search(name): return False, "not a photograph"
    if PEOPLE.search(text): return False, "may show people"
    if (ii.get("width") or 0) < 300: return False, "too small"
    return True, ""

def fit(im, box):
    im = im.copy(); im.thumbnail(box, resample=3)
    return im

def to_rgb(im):
    from PIL import Image
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA"); bg = Image.new("RGB", im.size, (255, 255, 255)); bg.paste(im, mask=im.split()[-1]); return bg
    return im.convert("RGB")

def main():
    from PIL import Image
    entries = {}
    for fn in os.listdir(ENT):
        if fn.endswith(".json"): entries[fn[:-5]] = json.load(open(os.path.join(ENT, fn), encoding="utf-8"))
    meta = load(META, {}); tried = load(TRIED, {})
    blocked = set(load(os.path.join(ROOT, "data", "state", "image_blocklist.json"), []))
    for b0 in blocked:
        meta.pop(b0, None)
        for suffix in (".webp", ".t.webp"):
            pth = os.path.join(IMG, b0 + suffix)
            if os.path.exists(pth): os.remove(pth)
    cutoff = (dt.date.fromisoformat(TODAY) - dt.timedelta(days=30)).isoformat()
    todo = [eid for eid in sorted(entries) if eid not in meta and eid not in EXCLUDE and eid not in blocked and tried.get(eid, "") < cutoff]
    log("entries without pictures to try", len(todo))
    qmap = {entries[e]["ids"]["wikidata"]: e for e in todo if (entries[e].get("ids") or {}).get("wikidata")}
    files = {}
    for q, f in p18(sorted(qmap)).items(): files[qmap[q]] = f
    wtitle = {}
    for e in todo:
        if e in files: continue
        for r in entries[e].get("refs") or []:
            if r.get("kind") == "wikipedia":
                wtitle[urllib.parse.unquote(r["url"].rsplit("/wiki/", 1)[-1]).replace("_", " ")] = e
    for t, f in page_images(sorted(wtitle)).items():
        if t in wtitle: files.setdefault(wtitle[t], f.replace("_", " "))
    log("candidate files", len(files))
    info = commons_info(sorted(set(files.values())))
    os.makedirs(IMG, exist_ok=True)
    done = 0
    for eid in todo:
        if done >= MAX: break
        tried[eid] = TODAY
        f = files.get(eid)
        ii = info.get(f) if f else None
        if not ii: continue
        ok, why = acceptable(f, ii)
        if not ok: log("skip", eid, why); continue
        data = get(ii.get("thumburl") or ii["url"], binary=True)
        if not data: continue
        try:
            im = to_rgb(Image.open(io.BytesIO(data)))
        except Exception as ex:
            log("bad image", eid, ex); continue
        p = fit(im, PLATE); t = fit(im, THUMB)
        p.save(os.path.join(IMG, f"{eid}.webp"), "WEBP", quality=72, method=6)
        t.save(os.path.join(IMG, f"{eid}.t.webp"), "WEBP", quality=70, method=6)
        md = ii.get("extmetadata") or {}
        meta[eid] = {"file": f, "page": ii.get("descriptionurl"), "author": plain((md.get("Artist") or {}).get("value"))[:90] or "Unknown author",
                     "license": plain((md.get("LicenseShortName") or {}).get("value")), "license_url": plain((md.get("LicenseUrl") or {}).get("value")),
                     "w": p.size[0], "h": p.size[1], "tw": t.size[0], "th": t.size[1], "added": TODAY}
        done += 1
        if done % 25 == 0: log("pictures", done); save(META, meta); save(TRIED, tried)
        time.sleep(0.4)
    save(META, meta); save(TRIED, tried)
    log("new pictures", done, "total", len(meta))

if __name__ == "__main__":
    main()
