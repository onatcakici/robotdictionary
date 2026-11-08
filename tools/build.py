#!/usr/bin/env python3
"""Build robotdictionary.com from data/entries/*.json into static pages at the repository root."""
import csv, datetime as dt, hashlib, html, io, json, os, re, shutil, sys, unicodedata
from collections import defaultdict, Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://robotdictionary.com"
REPO = "https://github.com/onatcakici/robotdictionary"
CONTACT = "contact@robotdictionary.com"
TODAY = dt.date.fromisoformat(os.environ.get("BUILD_DATE") or dt.datetime.now(dt.timezone.utc).date().isoformat())

SECTIONS = [
    ("humanoids", "Humanoids", "Machines built in the human form, from research bipeds to factory workers.", "humanoid robot"),
    ("quadrupeds", "Quadrupeds", "Four legged walkers and the other legged machines.", "quadruped robot"),
    ("wheeled", "Wheeled machines", "Delivery robots, cleaners, mowers, warehouse movers and tracked vehicles.", "wheeled robot"),
    ("arms", "Arms and workcells", "Industrial and collaborative arms, hands, laboratory automation and robotic kitchens.", "robot arm"),
    ("rovers", "Rovers", "Robots built to drive on the Moon, Mars and other worlds, with their test vehicles and field rovers.", "rover"),
    ("medical", "Medical and surgical", "Surgical systems, rehabilitation robots and exoskeletons for patients.", "medical robot"),
    ("marine", "Underwater and marine", "Autonomous submarines, remotely operated vehicles and robotic vessels.", "underwater robot"),
    ("other", "Other forms", "Snakes, climbers, companions, spheres and machines that fit no other shelf.", "robot"),
]
SEC = {s[0]: s for s in SECTIONS}
ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]
SAMPLES = {"humanoids": ["asimo", "atlas", "optimus"], "quadrupeds": ["spot", "anymal", "aibo"], "wheeled": ["roomba", "starship-delivery-robot", "stretch"],
           "arms": ["unimate", "ur5", "abb-yumi"], "rovers": ["lunokhod-1", "sojourner", "perseverance"], "medical": ["da-vinci-surgical-system", "mako", "versius"],
           "marine": [], "other": ["lego-mindstorms-ev3", "jibo"]}
STATUS = {"production": "In production", "service": "In service", "pilot": "In pilot deployments", "research": "Research platform",
          "prototype": "Prototype", "concept": "Announced, not yet in service", "development": "In development",
          "retired": "Retired", "discontinued": "Discontinued", "lost": "Lost", "completed": "Mission completed"}
RESERVED = {s[0] for s in SECTIONS} | {"assets", "data", "tools", "makers", "countries", "timeline", "yc", "a-z", "about",
            "legal", "recent", "search", "img", "feed.xml", "sitemap.xml", "robots.txt", "404.html", "index.html", "CNAME"}
GENERATED_LIST = os.path.join(ROOT, "tools", "generated.txt")

esc = lambda s: html.escape(str(s or ""), quote=True)

def slugify(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "x"

def nice_date(d):
    if isinstance(d, str): d = dt.date.fromisoformat(d[:10])
    return f"{d.day} {d.strftime('%B')} {d.year}"

def long_date(d):
    return f"{d.strftime('%A')} {d.day} {d.strftime('%B')} {d.year}"

def first_letter(name):
    c = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()[:1].upper()
    return c if c.isalpha() else "#"

def sort_key(name):
    return unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()

def domain(url):
    m = re.match(r"https?://(?:www\.)?([^/]+)", url or "")
    return m.group(1) if m else url

# ---------- load ----------
def load_entries():
    d = os.path.join(ROOT, "data", "entries")
    out = {}
    for fn in sorted(os.listdir(d)):
        if fn.endswith(".json"):
            e = json.load(open(os.path.join(d, fn), encoding="utf-8"))
            if e.get("hidden"): continue
            out[e["id"]] = e
    return out

def load_state(name, default):
    p = os.path.join(ROOT, "data", "state", name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else default

def save_state(name, obj):
    p = os.path.join(ROOT, "data", "state", name)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False); f.write("\n")

# ---------- page shell ----------
FONTS = ('<link rel="preload" href="/assets/fonts/source-serif-4-latin-400-normal.woff2" as="font" type="font/woff2" crossorigin>'
         '<link rel="preload" href="/assets/fonts/young-serif-latin-400-normal.woff2" as="font" type="font/woff2" crossorigin>')

def thumbs(current=None):
    out = []
    for key, title, *_ in SECTIONS:
        short = {"wheeled": "Wheeled", "arms": "Arms", "medical": "Medical", "marine": "Marine", "other": "Other"}.get(key, title)
        cur = ' class="cur"' if key == current else ""
        out.append(f'<a href="/{key}/" style="background:var(--{key})"{cur} title="{esc(title)}">{esc(short)}</a>')
    return '<nav class="thumbs" aria-label="Sections">' + "".join(out) + "</nav>"

def header():
    return ('<header class="top"><div class="wrap">'
            '<a class="wordmark" href="/">Robot Dictionary<i>.</i></a>'
            '<nav class="nav" aria-label="Site"><a href="/a-z/">A to Z</a><a href="/makers/">Makers</a><a href="/timeline/">Timeline</a>'
            '<a href="/yc/">YC robots</a><a href="/recent/">Recent</a><a href="/about/">About</a></nav>'
            '<div class="find" data-find><input type="search" placeholder="Find a robot or maker" aria-label="Find a robot or maker" autocomplete="off">'
            '<ul class="hits" hidden></ul></div></div></header>')

def footer(stats):
    return ('<footer class="colophon"><div class="wrap"><div>'
            '<b>Robot Dictionary</b>'
            '<p>A reference of the world\'s robots in eight sections, revised daily. Every entry lists its sources.</p>'
            f'<p>Corrections and additions to <a class="u" href="mailto:{CONTACT}">{CONTACT}</a>.</p></div>'
            '<nav aria-label="More"><a href="/about/">About the dictionary</a><a href="/legal/">Legal notice</a><a href="/recent/">Recently added</a>'
            '<a href="/countries/">Countries</a><a href="/data/robots.json">Open data</a><a href="/feed.xml">RSS feed</a>'
            f'<a href="{REPO}">GitHub</a></nav></div></footer>')

def page(path, title, desc, body, stats, section=None, jsonld=None, og_type="website", noindex=False, body_class=""):
    canon = SITE + path
    ld = f'<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>' if jsonld else ""
    robots = '<meta name="robots" content="noindex">' if noindex else ""
    return ("<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">\n"
            f"<title>{esc(title)}</title>\n<meta name=\"description\" content=\"{esc(desc)}\">\n{robots}"
            f"<link rel=\"canonical\" href=\"{canon}\">\n"
            f"<meta property=\"og:type\" content=\"{og_type}\"><meta property=\"og:site_name\" content=\"Robot Dictionary\">"
            f"<meta property=\"og:title\" content=\"{esc(title)}\"><meta property=\"og:description\" content=\"{esc(desc)}\">"
            f"<meta property=\"og:url\" content=\"{canon}\"><meta property=\"og:image\" content=\"{SITE}/assets/card.png\">"
            "<meta name=\"twitter:card\" content=\"summary_large_image\"><meta name=\"twitter:site\" content=\"@robotdictionary\">\n"
            "<link rel=\"icon\" href=\"/assets/icon-32.png\" sizes=\"32x32\" type=\"image/png\"><link rel=\"apple-touch-icon\" href=\"/assets/icon-180.png\">"
            "<link rel=\"alternate\" type=\"application/rss+xml\" title=\"Robot Dictionary, new entries\" href=\"/feed.xml\">\n"
            f"{FONTS}\n<link rel=\"stylesheet\" href=\"/assets/site.css?v={stats['v']}\">\n{ld}\n</head>\n<body{(' class=\"' + body_class + '\"') if body_class else ''}>\n"
            f"{header()}\n{thumbs(section)}\n{body}\n{footer(stats)}\n"
            f"<script src=\"/assets/search.js?v={stats['v']}\" defer></script>\n</body>\n</html>\n")

# ---------- fragments ----------
def maker_link(e, makers_with_pages):
    m = e.get("maker") or ""
    if not m: return ""
    s = slugify(m)
    return f'<a href="/makers/{s}/">{esc(m)}</a>' if s in makers_with_pages else esc(m)

def country_link(e, countries_with_pages):
    c = e.get("country") or ""
    if not c: return ""
    s = slugify(c)
    return f'<a href="/countries/{s}/">{esc(c)}</a>' if s in countries_with_pages else esc(c)

def origin_line(e, mk=None, ct=None, links=True):
    parts = []
    if e.get("maker"): parts.append(maker_link(e, mk) if links else esc(e["maker"]))
    if e.get("country"): parts.append(country_link(e, ct) if links else esc(e["country"]))
    if e.get("year"): parts.append(esc(e["year"]))
    return (", ".join(parts) + ".") if parts else ""

def pos_label(e):
    s, k = e.get("section"), (e.get("kind") or "").lower()
    if s == "humanoids": return "android" if "android" in k else "humanoid"
    if s == "quadrupeds": return "quadruped" if ("quadruped" in k or "dog" in k or not re.search(r"legged|hexapod|walker|limbed|wheel", k)) else "legged robot"
    if s == "wheeled": return "wheeled machine" if "track" not in k else "tracked machine"
    if s == "arms": return "robot hand" if re.search(r"\bhands?\b", k) else ("robot arm" if re.search(r"\barms?\b|cobot|delta", k) else "workcell")
    if s == "rovers": return "rover"
    if s == "medical": return "exoskeleton" if "exoskeleton" in k else "medical robot"
    if s == "marine": return "underwater robot" if re.search(r"underwater|remotely operated|glider|submersible", k) else "marine robot"
    return "robot"

def status_text(e):
    t = e.get("status_text") or STATUS.get(e.get("status") or "", "")
    return (t.rstrip(".") + ".") if t else ""

def plate(e, big=False):
    img = e.get("image")
    inner = f'<img src="{esc(img)}" alt="{esc(e["name"])}" loading="lazy">' if img else ""
    return f'<span class="plate" aria-hidden="{"false" if img else "true"}">{inner}</span>'

def dict_entry(e, mk, ct):
    st = status_text(e)
    return (f'<p class="dent"><a class="hw" href="/{e["id"]}/">{esc(e["name"])}</a> <span class="pos">n., {esc(pos_label(e))}.</span> '
            f'<span class="org">{origin_line(e, mk, ct, links=False)}</span> {esc(e.get("def"))} '
            + (f'<span class="st">{esc(st)}</span>' if st else "") + "</p>")

# ---------- builders ----------
class Out:
    def __init__(self): self.files = {}
    def put(self, rel, content): self.files[rel] = content

def build():
    E = load_entries()
    ids = sorted(E, key=lambda i: sort_key(E[i]["name"]))
    for i in ids:
        if i in RESERVED: sys.exit(f"entry id collides with a reserved path: {i}")
    by_sec = defaultdict(list)
    for i in ids: by_sec[E[i]["section"]].append(E[i])
    makers = defaultdict(list); countries = defaultdict(list)
    for i in ids:
        e = E[i]
        if e.get("maker"): makers[slugify(e["maker"])].append(e)
        if e.get("country"): countries[slugify(e["country"])].append(e)
    mk_pages = {k for k, v in makers.items() if len(v) >= 2}
    ct_pages = {k for k, v in countries.items() if len(v) >= 1}
    css = open(os.path.join(ROOT, "tools", "static", "site.css"), encoding="utf-8").read()
    js = open(os.path.join(ROOT, "tools", "static", "search.js"), encoding="utf-8").read()
    v = hashlib.sha1((css + js).encode()).hexdigest()[:8]
    stats = {"n": len(ids), "v": v}
    out = Out()

    # robot of the day
    featured = load_state("featured.json", [])
    eligible = [i for i in ids if E[i].get("origin") == "edited" and (E[i].get("body") or E[i].get("facts")) and E[i].get("def")]
    todays = [f for f in featured if f["date"] == TODAY.isoformat() and f["id"] in E]
    if todays:
        rod = E[todays[0]["id"]]
    else:
        recent = {f["id"] for f in featured[-120:]}
        pool = [i for i in eligible if i not in recent] or eligible
        h = int(hashlib.sha256(TODAY.isoformat().encode()).hexdigest(), 16)
        rod = E[pool[h % len(pool)]]
        featured = [f for f in featured if f["date"] != TODAY.isoformat()] + [{"date": TODAY.isoformat(), "id": rod["id"]}]
        save_state("featured.json", featured[-400:])
    changes = load_state("changes.json", [])

    # ---- entry pages
    for sec_key, title, blurb, _ in SECTIONS:
        group = by_sec.get(sec_key, [])
        for n, e in enumerate(group):
            prev_e = group[n - 1] if n > 0 else None
            next_e = group[n + 1] if n + 1 < len(group) else None
            out.put(f'{e["id"]}/index.html', entry_page(e, E, sec_key, title, group, n, prev_e, next_e, mk_pages, ct_pages, stats))

    # ---- sections
    for k, (sec_key, title, blurb, _) in enumerate(SECTIONS):
        group = by_sec.get(sec_key, [])
        letters = defaultdict(list)
        for e in group: letters[first_letter(e["name"])].append(e)
        lets = sorted(letters)
        body = [f'<section class="cover" style="--c:var(--{sec_key})"><div class="wrap"><p class="vol">Section {ROMAN[k]}</p><h1>{esc(title)}</h1>'
                f'<p>{esc(blurb)} <span class="cnt">{len(group):,} entries.</span></p></div></section>',
                '<main class="wrap"><nav class="letters" aria-label="Letters">' + "".join(f'<a href="#{l if l != "#" else "num"}">{l}</a>' for l in lets) + "</nav>",
                f'<div class="dict" style="--c:var(--{sec_key})">']
        for l in lets:
            body.append(f'<h2 id="{l if l != "#" else "num"}">{l}</h2>')
            body += [dict_entry(e, mk_pages, ct_pages) for e in letters[l]]
        body.append("</div></main>")
        desc = f"{title}: {len(group)} entries in the Robot Dictionary. {blurb}"
        ld = {"@context": "https://schema.org", "@type": "CollectionPage", "name": f"{title} | Robot Dictionary", "url": f"{SITE}/{sec_key}/",
              "description": desc, "isPartOf": {"@type": "WebSite", "name": "Robot Dictionary", "url": SITE + "/"}}
        out.put(f"{sec_key}/index.html", page(f"/{sec_key}/", f"{title}, every entry | Robot Dictionary", desc, "\n".join(body), stats, sec_key, ld))

    # ---- home
    out.put("index.html", home_page(E, ids, by_sec, rod, featured, changes, mk_pages, ct_pages, stats, makers, countries))

    # ---- A to Z
    letters = defaultdict(list)
    for i in ids: letters[first_letter(E[i]["name"])].append(E[i])
    body = ['<main class="wrap"><div class="page-h"><h1>A to Z</h1>'
            f'<p>All {len(ids):,} entries in alphabetical order. Each name opens its full entry with measures and sources.</p></div>',
            '<nav class="letters" aria-label="Letters">' + "".join(f'<a href="#{l if l != "#" else "num"}">{l}</a>' for l in sorted(letters)) + "</nav>",
            '<div class="cols">']
    for l in sorted(letters):
        body.append(f'<h2 id="{l if l != "#" else "num"}">{l}</h2><ul>' + "".join(
            f'<li><a href="/{e["id"]}/">{esc(e["name"])}</a> <span class="m">{esc(e.get("maker") or "")}</span></li>' for e in letters[l]) + "</ul>")
    body.append("</div></main>")
    out.put("a-z/index.html", page("/a-z/", "A to Z of robots | Robot Dictionary", f"Alphabetical index of all {len(ids):,} robots in the Robot Dictionary.", "\n".join(body), stats))

    # ---- makers
    mk_sorted = sorted(makers.items(), key=lambda kv: sort_key(kv[1][0]["maker"]))
    ml = defaultdict(list)
    for s, es in mk_sorted: ml[first_letter(es[0]["maker"])].append((s, es))
    body = ['<main class="wrap"><div class="page-h"><h1>Makers</h1>'
            f'<p>{len(makers):,} companies, laboratories and agencies that have built the robots in this dictionary.</p></div><div class="cols">']
    for l in sorted(ml):
        items = []
        for s, es in ml[l]:
            href = f"/makers/{s}/" if s in mk_pages else f"/{es[0]['id']}/"
            items.append(f'<li><a href="{href}">{esc(es[0]["maker"])}</a> <span class="m">{len(es)}</span></li>')
        body.append(f"<h2>{l}</h2><ul>" + "".join(items) + "</ul>")
    body.append("</div></main>")
    out.put("makers/index.html", page("/makers/", "Robot makers | Robot Dictionary", f"Index of {len(makers)} robot makers with their entries in the Robot Dictionary.", "\n".join(body), stats))
    for s in mk_pages:
        es = makers[s]; name = es[0]["maker"]
        cs = Counter(e.get("country") for e in es if e.get("country")).most_common(1)
        lead = f"{len(es)} entries" + (f", {cs[0][0]}" if cs else "")
        body = [f'<main class="wrap"><div class="page-h"><h1>{esc(name)}</h1><p>Robots by {esc(name)} recorded in the dictionary: {esc(lead)}.</p></div>',
                '<div class="dict">'] + [dict_entry(e, mk_pages, ct_pages) for e in sorted(es, key=lambda e: (e.get("year") or "9999", sort_key(e["name"])))] + ["</div></main>"]
        out.put(f"makers/{s}/index.html", page(f"/makers/{s}/", f"{name} robots | Robot Dictionary", f"All {len(es)} {name} robots in the Robot Dictionary, with dates, status and sources.", "\n".join(body), stats))

    # ---- countries
    cs_sorted = sorted(countries.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    body = ['<main class="wrap"><div class="page-h"><h1>Countries</h1><p>Where the robots in this dictionary were built, by number of entries.</p></div><div class="cols"><ul>']
    body += [f'<li><a href="/countries/{s}/">{esc(es[0]["country"])}</a> <span class="m">{len(es)}</span></li>' for s, es in cs_sorted]
    body.append("</ul></div></main>")
    out.put("countries/index.html", page("/countries/", "Robots by country | Robot Dictionary", "Robots in the Robot Dictionary grouped by country of origin.", "\n".join(body), stats))
    for s, es in countries.items():
        name = es[0]["country"]
        groups = defaultdict(list)
        for e in es: groups[e["section"]].append(e)
        body = [f'<main class="wrap"><div class="page-h"><h1>Robots of {esc(name)}</h1><p>{len(es)} entries built in {esc(name)}, grouped by section.</p></div>']
        for sec_key, title, *_ in SECTIONS:
            if groups.get(sec_key):
                body.append(f'<div class="dict" style="--c:var(--{sec_key})"><h2>{esc(title)}</h2>' + "".join(dict_entry(e, mk_pages, ct_pages) for e in sorted(groups[sec_key], key=lambda e: sort_key(e["name"]))) + "</div>")
        body.append("</main>")
        out.put(f"countries/{s}/index.html", page(f"/countries/{s}/", f"Robots of {name} | Robot Dictionary", f"{len(es)} robots built in {name}: humanoids, quadrupeds, rovers and more, with sources.", "\n".join(body), stats))

    # ---- timeline
    years = defaultdict(list)
    for i in ids:
        y = re.match(r"(\d{4})", E[i].get("year") or "")
        if y: years[int(y.group(1))].append(E[i])
    body = ['<main class="wrap"><div class="page-h"><h1>Timeline</h1><p>Every dated entry by the year it was first shown, from the earliest automata of the electric age to this year\'s machines.</p></div>']
    last_dec = None
    for y in sorted(years):
        dec = y // 10 * 10
        if dec != last_dec:
            body.append(f'<h2 class="decade" id="d{dec}">{dec}s</h2>'); last_dec = dec
        body.append(f'<div class="year" id="y{y}"><span class="y">{y}</span><ul>' + "".join(
            f'<li><a href="/{e["id"]}/">{esc(e["name"])}</a> <span class="org">{esc(e.get("maker") or "")}</span></li>'
            for e in sorted(years[y], key=lambda e: sort_key(e["name"]))) + "</ul></div>")
    body.append("</main>")
    out.put("timeline/index.html", page("/timeline/", "Timeline of robots | Robot Dictionary", "Robots by year first shown, from the 1940s to today.", "\n".join(body), stats))

    # ---- YC
    yc = [E[i] for i in ids if E[i].get("yc")]
    def bkey(b):
        m = re.match(r"(Winter|Spring|Summer|Fall)\s+(\d{4})", b or "")
        return (int(m.group(2)), ["Winter", "Spring", "Summer", "Fall"].index(m.group(1))) if m else (0, 0)
    batches = defaultdict(list)
    for e in yc: batches[e["yc"]["batch"]].append(e)
    body = ['<main class="wrap"><div class="page-h"><h1>Robots from Y Combinator companies</h1>'
            f'<p>{len(yc)} robots built by companies that went through Y Combinator, newest batch first. Company facts come from the public YC company directory; '
            'Robot Dictionary is not affiliated with Y Combinator.</p></div>']
    for b in sorted(batches, key=bkey, reverse=True):
        body.append(f'<section class="batch"><h2>{esc(b)}</h2><div class="dict">' + "".join(
            dict_entry(e, mk_pages, ct_pages) for e in sorted(batches[b], key=lambda e: sort_key(e["name"]))) + "</div></section>")
    queue = [q for q in load_state("yc_queue.json", []) if q.get("slug") not in {(e.get("ids") or {}).get("yc") for e in yc}]
    if queue:
        body.append('<section class="batch"><h2>Newly listed robotics companies</h2><p class="more" style="color:var(--soft);font-size:16px">'
                    'Robotics companies that recently appeared in the YC directory, checked each morning.</p><ul class="list">'
                    + "".join(f'<li><a href="{esc(q["url"])}" rel="noopener">{esc(q["name"])}</a> <span class="m">{esc(q.get("batch") or "")}</span></li>'
                              for q in sorted(queue, key=lambda q: q.get("found") or "", reverse=True)[:60]) + "</ul></section>")
    body.append("</main>")
    out.put("yc/index.html", page("/yc/", "Y Combinator robotics startups and their robots | Robot Dictionary",
                                  f"{len(yc)} robots built by Y Combinator companies, by batch, with status and sources.", "\n".join(body), stats))

    # ---- recent
    by_date = defaultdict(list)
    for c in changes:
        if c["id"] in E: by_date[c["date"]].append(c)
    for i in ids:
        if not any(c["id"] == i for c in changes) and E[i].get("added"):
            pass
    body = ['<main class="wrap"><div class="page-h"><h1>Recently added and revised</h1>'
            '<p>The dictionary is revised every day. New entries and corrected facts appear here first.</p></div>']
    for d in sorted(by_date, reverse=True)[:60]:
        items = by_date[d]
        body.append(f'<section class="batch"><h2>{nice_date(d)}</h2><ul class="list">' + "".join(
            f'<li><a href="/{c["id"]}/">{esc(E[c["id"]]["name"])}</a> <span class="m">{"added" if c["type"] == "added" else "revised"}'
            + (f', {esc(c["note"])}' if c.get("note") else "") + "</span></li>" for c in items[:1500]) + "</ul></section>")
    body.append("</main>")
    out.put("recent/index.html", page("/recent/", "Recently added robots | Robot Dictionary", "New and revised entries in the Robot Dictionary, by date.", "\n".join(body), stats))

    # ---- about, legal, 404
    out.put("about/index.html", page("/about/", "About the Robot Dictionary", "How the Robot Dictionary is compiled, sourced and revised every day.", about_body(stats, len(makers), len(countries)), stats))
    out.put("legal/index.html", page("/legal/", "Legal notice | Robot Dictionary", "Disclaimer, sources and licences, trademarks, corrections and privacy for robotdictionary.com.", legal_body(), stats))
    out.put("404.html", page("/404.html", "No such entry | Robot Dictionary", "This page is not in the dictionary.",
                             '<main class="wrap"><div class="page-h"><h1>No such entry</h1><p>Nothing in the present edition answers to this address. '
                             'Try the search above, or browse the <a class="u" href="/a-z/">A to Z</a>.</p></div></main>', stats, noindex=True))

    # ---- redirects for old addresses
    for i in ids:
        for o in E[i].get("old") or []:
            if o in E or o in RESERVED or o in out.files: continue
            if f"{o}/index.html" in out.files: continue
            out.put(f"{o}/index.html", redirect_page(f"/{i}/", E[i]["name"]))

    # ---- feeds, data, sitemap
    out.put("feed.xml", feed(E, changes))
    search = [[e["id"], e["name"], " ".join(e.get("aka") or []), e.get("maker") or "", e.get("country") or "", e.get("year") or ""] for e in (E[i] for i in ids)]
    out.put("assets/search.json", json.dumps(search, ensure_ascii=False, separators=(",", ":")))
    out.put("assets/site.css", css); out.put("assets/search.js", js)
    sdir = os.path.join(ROOT, "tools", "static")
    for sub in ("fonts", "img"):
        d = os.path.join(sdir, sub)
        if os.path.isdir(d):
            for fn in sorted(os.listdir(d)):
                if fn.endswith((".woff2", ".png", ".svg", ".ico", ".txt")):
                    out.put(f"assets/{sub + '/' if sub == 'fonts' else ''}{fn}", open(os.path.join(d, fn), "rb").read())
    out.put("data/robots.json", json.dumps(open_data(E, ids), ensure_ascii=False, indent=1) + "\n")
    out.put("data/robots.csv", open_csv(E, ids))
    urls = ["/", "/a-z/", "/makers/", "/countries/", "/timeline/", "/yc/", "/recent/", "/about/", "/legal/"] + [f"/{s[0]}/" for s in SECTIONS]
    urls += [f"/{i}/" for i in ids] + [f"/makers/{s}/" for s in sorted(mk_pages)] + [f"/countries/{s}/" for s in sorted(countries)]
    lastmod = {f"/{i}/": E[i].get("revised") or E[i].get("added") for i in ids}
    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        lm = lastmod.get(u) or TODAY.isoformat()
        sm.append(f"<url><loc>{SITE}{u}</loc><lastmod>{lm}</lastmod></url>")
    sm.append("</urlset>")
    out.put("sitemap.xml", "\n".join(sm) + "\n")
    out.put("robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n")
    out.put("CNAME", "robotdictionary.com\n")
    out.put(".nojekyll", "")
    write(out)
    print(f"built {len(out.files)} files, {len(ids)} entries, robot of the day: {rod['name']}")

def home_page(E, ids, by_sec, rod, featured, changes, mk, ct, stats, makers, countries):
    recent_added = []
    seen = set()
    def notable(i):
        e = E[i]
        return (300 if any(r.get("kind") == "wikipedia" for r in e.get("refs") or []) else 0) + 50 * len(e.get("facts") or []) + len(" ".join(e.get("body") or []))
    ordered = sorted([c for c in changes if c["id"] in E], key=lambda c: (c["date"], notable(c["id"]),
                     hashlib.md5((c["date"] + c["id"]).encode()).hexdigest()), reverse=True)
    for c in ordered:
        if c["type"] == "added" and c["id"] not in seen:
            recent_added.append(c); seen.add(c["id"])
        if len(recent_added) >= 12: break
    rod_sec = SEC[rod["section"]]
    body = rod.get("body") or []
    excerpt = body[0] if body else ("; ".join(rod.get("facts") or [])[:300])
    past = [f for f in featured if f["date"] != TODAY.isoformat() and f["id"] in E][-6:][::-1]
    h = ['<main class="wrap">',
         '<header class="mast"><h1>Robot Dictionary<i>.</i></h1>',
         '<p class="tag">A reference of the world\'s robots, with makers, measures, history and sources.</p>',
         f'<p class="date">Revised daily. This edition: {long_date(TODAY)}, {stats["n"]:,} entries.</p>',
         '<div class="bigfind" data-find><input type="search" placeholder="Find a robot, maker or country" aria-label="Find a robot, maker or country" autocomplete="off"><ul class="hits" hidden></ul>'
         '<p>Try Atlas, Unitree, Opportunity or Japan. Press / to search from any page.</p></div></header>',
         '<hr class="double">',
         '<div class="spread"><section><h2 class="label">Robot of the day</h2>'
         + (f'<article class="today"><a href="/{rod["id"]}/" aria-label="{esc(rod["name"])}">{plate(rod)}</a><div>' if rod.get("image") else '<article class="today noimg"><div>')
         + f'<h2><a href="/{rod["id"]}/">{esc(rod["name"])}</a></h2>'
         f'<p class="pos"><i>n., {esc(pos_label(rod))}.</i> <span class="org">{origin_line(rod, mk, ct)}</span> <span class="st">{esc(status_text(rod))}</span></p>'
         f'<p class="def">{esc(rod.get("def"))}</p>'
         + (f'<p class="more">{esc(excerpt)}</p>' if excerpt else "")
         + f'<p class="more"><a class="u" href="/{rod["id"]}/">Read the full entry</a> in <a class="u" href="/{rod["section"]}/">{esc(rod_sec[1])}</a>.</p></div></article>'
         + ("<p class=\"more\" style=\"margin-top:22px;font-size:15.5px;color:var(--soft)\">Earlier this week: " + ", ".join(
             f'<a class="u" href="/{f["id"]}/">{esc(E[f["id"]]["name"])}</a>' for f in past) + ".</p>" if past else "")
         + '</section><aside><h2 class="label">Recently added</h2><ul class="list">'
         + "".join(f'<li class="row"><span><a href="/{c["id"]}/">{esc(E[c["id"]]["name"])}</a>'
                   + (f' <span class="m">{esc(E[c["id"]]["maker"])}</span>' if E[c["id"]].get("maker") and E[c["id"]]["maker"].lower() not in E[c["id"]]["name"].lower() else "")
                   + f'</span><span class="d">{dt.date.fromisoformat(c["date"]).strftime("%-d %b")}</span></li>' for c in recent_added)
         + '</ul><p class="more" style="font-size:15.5px;margin-top:10px"><a class="u" href="/recent/">All recent changes</a></p></aside></div>',
         '<section class="contents"><h2>Contents</h2><ol class="toc">']
    for k, (key, title, blurb, _) in enumerate(SECTIONS):
        group = by_sec.get(key, [])
        pref = [E[i] for i in SAMPLES.get(key, []) if i in E and E[i]["section"] == key]
        rest = sorted([e for e in group if e not in pref], key=lambda e: -(len(" ".join(e.get("body") or [])) + 60 * len(e.get("facts") or [])
                                                                       + (300 if any(r.get("kind") == "wikipedia" for r in e.get("refs") or []) else 0)))
        sample = (pref + rest)[:3]
        h.append(f'<li style="--c:var(--{key})"><span class="num">{ROMAN[k]}</span><div><span class="t"><a href="/{key}/">{esc(title)}</a></span>'
                 f'<span class="x">{esc(blurb)} <em>Including ' + ", ".join(f'<a href="/{e["id"]}/">{esc(e["name"])}</a>' for e in sample) + '.</em></span></div>'
                 f'<span class="n">{len(group):,} entries</span></li>')
    h.append('</ol><nav class="more-ways" aria-label="Other ways in">'
             f'<a href="/a-z/">A to Z, all {len(ids):,} entries</a><a href="/makers/">{len(makers):,} makers</a><a href="/countries/">{len(countries)} countries</a>'
             f'<a href="/timeline/">Timeline</a><a href="/yc/">Robots from Y Combinator companies</a></nav></section></main>')
    ld = {"@context": "https://schema.org", "@type": "WebSite", "name": "Robot Dictionary", "url": SITE + "/",
          "description": "A reference of the world's robots, revised daily.",
          }
    return page("/", "Robot Dictionary: a reference of the world's robots, revised daily",
                f"Robot Dictionary records {len(ids):,} robots, from ASIMO and Atlas to Mars rovers and new startup machines, each with maker, measures, status and sources.",
                "\n".join(h), stats, None, ld, body_class="home")

def entry_page(e, E, sec_key, sec_title, group, n, prev_e, next_e, mk, ct, stats):
    st = status_text(e)
    rows = []
    if e.get("maker"): rows.append(("Maker", maker_link(e, mk)))
    if e.get("country"): rows.append(("Country", country_link(e, ct)))
    if e.get("year"): rows.append(("First shown", esc(e["year"])))
    if st: rows.append(("Status", esc(st.rstrip("."))))
    if e.get("yc"):
        rows.append(("Y Combinator", f'<a href="/yc/">{esc(e["yc"]["batch"])}</a>' + (f', company {esc(e["yc"]["status"].lower())}' if e["yc"].get("status") and e["yc"]["status"] != "Active" else "")))
    for k, val in e.get("specs") or []:
        rows.append((esc(k), esc(val)))
    refs = e.get("refs") or []
    see = [E[s] for s in (e.get("see") or []) if s in E]
    sibs = group[max(0, n - 5): n + 6]
    aka = e.get("aka") or []
    revised = e.get("revised") or e.get("added")
    cite_id = "cite"
    title = f'{e["name"]}, {e.get("kind") or "robot"}' + (f' by {e["maker"]}' if e.get("maker") else "") + " | Robot Dictionary"
    desc = (e.get("def") or "")
    if len(desc) > 158: desc = desc[:155].rsplit(" ", 1)[0] + "..."
    body = [f'<main class="wrap" style="--c:var(--{sec_key})">',
            f'<p class="crumb"><span class="sw"></span><a href="/{sec_key}/">{esc(sec_title)}</a></p>',
            '<div class="entry"><article>',
            f'<h1>{esc(e["name"])}</h1>']
    if aka: body.append(f'<p class="aka">Also known as {esc(", ".join(aka))}</p>')
    body.append(f'<p class="posline"><span class="pos">n., {esc(pos_label(e))}.</span> <span class="org">{origin_line(e, mk, ct)}</span> '
                + (f'<span class="st">{esc(st)}</span>' if st else "") + "</p>")
    body.append(f'<p class="lead">{esc(e.get("def"))}</p>')
    body.append('<table class="measures"><caption>Measures and facts</caption><tbody>' + "".join(
        f'<tr><th scope="row">{k}</th><td>{v}</td></tr>' for k, v in rows) + "</tbody></table>")
    if e.get("body"):
        body.append('<div class="prose">' + "".join(f"<p>{esc(p)}</p>" for p in e["body"]) + "</div>")
    if e.get("excerpt"):
        x = e["excerpt"]
        body.append(f'<div class="excerpt"><p>{esc(x["text"])}</p><p>From the Wikipedia article <a href="{esc(x["url"])}">{esc(x["title"])}</a>, '
                    'available under <a href="https://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA 4.0</a>.</p></div>')
    if e.get("facts"):
        body.append('<h3>Of note</h3><ul class="facts">' + "".join(f"<li>{esc(f)}</li>" for f in e["facts"]) + "</ul>")
    if refs:
        body.append('<h3>Sources</h3><ol class="refs">' + "".join(
            f'<li><a href="{esc(r["url"])}" rel="noopener">{esc(r["label"])}</a>, {esc(domain(r["url"]))}</li>' for r in refs) + "</ol>")
    if see:
        body.append('<h3>See also</h3><p class="see">' + ", ".join(f'<a href="/{s["id"]}/">{esc(s["name"])}</a>' for s in see) + ".</p>")
    body.append(f'<h3>Cite this entry</h3><p class="cite" id="{cite_id}">&ldquo;{esc(e["name"])}.&rdquo; <i>Robot Dictionary</i>, robotdictionary.com/{e["id"]}/. Revised {nice_date(revised)}.</p>'
                f'<p class="stamp"><button type="button" data-copy="{cite_id}" style="font:inherit;font-size:14.5px;background:none;border:0;padding:0;color:var(--soft);text-decoration:underline;text-decoration-color:var(--rule);text-underline-offset:3px;cursor:pointer">Copy</button></p>')
    body.append(f'<p class="stamp">Entry added {nice_date(e.get("added") or revised)}, revised {nice_date(revised)}. '
                f'<a href="mailto:{CONTACT}?subject={esc("Correction: " + e["name"])}">Suggest a correction</a> or '
                f'<a href="{REPO}/edit/main/data/entries/{e["id"]}.json">edit this entry</a>.</p>')
    pager = '<nav class="pager">' + (f'<a href="/{prev_e["id"]}/">{esc(prev_e["name"])}</a>' if prev_e else "<span></span>") + \
            (f'<a href="/{next_e["id"]}/">{esc(next_e["name"])}</a>' if next_e else "<span></span>") + "</nav>"
    body.append(pager)
    body.append(f'</article><aside>{plate(e, True)}'
                + f'<h3>Nearby in {esc(sec_title)}</h3><ul class="sibs">' + "".join(
        (f'<li class="cur">{esc(s["name"])}</li>' if s is e else f'<li><a href="/{s["id"]}/">{esc(s["name"])}</a></li>') for s in sibs) + "</ul></aside></div></main>")
    about = {"@type": "Product", "name": e["name"], "category": e.get("kind") or "robot", "description": e.get("def") or ""}
    if e.get("maker"): about["manufacturer"] = {"@type": "Organization", "name": e["maker"]}
    if e.get("country"): about["countryOfOrigin"] = e["country"]
    same = [r["url"] for r in refs if r.get("kind") in ("wikidata", "wikipedia")]
    if same: about["sameAs"] = same
    ld = {"@context": "https://schema.org", "@type": "WebPage", "name": title, "url": f"{SITE}/{e['id']}/", "description": desc,
          "dateModified": revised, "about": about,
          "breadcrumb": {"@type": "BreadcrumbList", "itemListElement": [
              {"@type": "ListItem", "position": 1, "name": "Robot Dictionary", "item": SITE + "/"},
              {"@type": "ListItem", "position": 2, "name": sec_title, "item": f"{SITE}/{sec_key}/"},
              {"@type": "ListItem", "position": 3, "name": e["name"], "item": f"{SITE}/{e['id']}/"}]}}
    return page(f"/{e['id']}/", title, desc, "\n".join(body), stats, sec_key, ld, "article")

def redirect_page(target, name):
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            f"<title>{esc(name)} | Robot Dictionary</title><link rel=\"canonical\" href=\"{SITE}{target}\">"
            f"<meta http-equiv=\"refresh\" content=\"0; url={target}\"><meta name=\"robots\" content=\"noindex\">"
            f"<script>location.replace({json.dumps(target)})</script></head><body><p>This entry has moved to <a href=\"{target}\">{esc(name)}</a>.</p></body></html>\n")

def feed(E, changes):
    items = []
    seen = set()
    for c in sorted(changes, key=lambda c: c["date"], reverse=True):
        if c["type"] != "added" or c["id"] not in E or c["id"] in seen: continue
        seen.add(c["id"]); e = E[c["id"]]
        d = dt.datetime.fromisoformat(c["date"] + "T06:00:00")
        items.append(f'<item><title>{esc(e["name"])}</title><link>{SITE}/{e["id"]}/</link><guid>{SITE}/{e["id"]}/</guid>'
                     f'<pubDate>{d.strftime("%a, %d %b %Y %H:%M:%S +0000")}</pubDate><description>{esc(e.get("def"))}</description></item>')
        if len(items) >= 50: break
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel><title>Robot Dictionary, new entries</title>'
            f'<link>{SITE}/</link><description>New robots added to the Robot Dictionary.</description><language>en</language>'
            f'<lastBuildDate>{dt.datetime.combine(TODAY, dt.time(6)).strftime("%a, %d %b %Y %H:%M:%S +0000")}</lastBuildDate>'
            + "".join(items) + "</channel></rss>\n")

OPEN_FIELDS = ["id", "name", "aka", "section", "kind", "maker", "country", "year", "status", "def", "specs", "facts", "see", "refs", "ids", "yc", "added", "revised"]
def open_data(E, ids):
    return {"name": "Robot Dictionary", "url": SITE + "/", "licence": "CC BY 4.0, attribution: Robot Dictionary (robotdictionary.com)",
            "generated": TODAY.isoformat(), "count": len(ids),
            "entries": [{k: E[i][k] for k in OPEN_FIELDS if E[i].get(k) not in (None, "", [], {})} for i in ids]}

def open_csv(E, ids):
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(["id", "name", "section", "kind", "maker", "country", "year", "status", "definition", "url", "wikidata", "yc_batch"])
    for i in ids:
        e = E[i]
        w.writerow([e["id"], e["name"], e["section"], e.get("kind", ""), e.get("maker", ""), e.get("country", ""), e.get("year", ""),
                    e.get("status", ""), e.get("def", ""), f"{SITE}/{e['id']}/", (e.get("ids") or {}).get("wikidata", ""), (e.get("yc") or {}).get("batch", "")])
    return buf.getvalue()

def about_body(stats, n_makers, n_countries):
    return f'''<main class="wrap"><div class="page-h"><h1>About the dictionary</h1>
<p>Robot Dictionary is a reference of the world's robots: one entry per machine, written to be read in a minute and checked in two.</p></div>
<div class="doc">
<h2>What is in it</h2>
<p>The present edition holds {stats["n"]:,} entries from {n_makers:,} makers in {n_countries} countries, arranged in eight sections: humanoids, quadrupeds, wheeled machines, arms and workcells, rovers, medical and surgical robots, underwater and marine robots, and other forms. A robot earns an entry when it was built and shown in public, or announced with enough published detail to describe it.</p>
<h2>How an entry is made</h2>
<p>Each entry gives the robot's maker, country, the year it was first shown, its present status, a short definition and, where they are published, its measures. Longer entries add a history and notes. Every entry lists its sources at the foot of the page: makers' own publications, Wikidata, Wikipedia, the Y Combinator company directory, and press or research papers where those are the best record.</p>
<p>Figures are copied as published and rounded only where the source gives a range. Where sources disagree, the maker's own figure is preferred and the disagreement is noted. Nothing in an entry is guessed; when a fact is unknown it is left out.</p>
<h2>Revised every day</h2>
<p>A revision runs every morning. It refreshes facts drawn from Wikidata, picks up robots that have newly appeared in the public record, checks the Y Combinator directory for new robotics companies, selects the robot of the day and rebuilds every page. The changes of each day are listed under <a href="/recent/">Recently added</a> and in the <a href="/feed.xml">RSS feed</a>.</p>
<h2>Corrections and additions</h2>
<p>Write to <a href="mailto:{CONTACT}">{CONTACT}</a> with the entry and a source, or edit the entry directly on <a href="{REPO}">GitHub</a>, where every entry is a small text file. Makers are welcome to send official figures and photographs.</p>
<h2>Open data</h2>
<p>The whole dictionary can be downloaded as <a href="/data/robots.json">JSON</a> or <a href="/data/robots.csv">CSV</a> and reused under CC BY 4.0 with credit to Robot Dictionary. Text quoted from Wikipedia is marked on the page and keeps its own CC BY-SA 4.0 licence.</p>
<h2>Plates</h2>
<p>Each entry has a reserved plate for a photograph of the robot on a plain white ground. Plates are added as cleared images arrive; an empty frame means the picture is still to come.</p>
</div></main>'''

def legal_body():
    return f'''<main class="wrap"><div class="page-h"><h1>Legal notice</h1><p>Please read this before relying on anything in the Robot Dictionary.</p></div>
<div class="doc">
<h2>Information only</h2>
<p>Robot Dictionary is a general reference. Entries are compiled from published sources and are provided as is, without any warranty that they are complete, current or free of error. Specifications, prices, dates and statuses change and are sometimes reported differently by different sources. Do not rely on this site for purchasing, safety, engineering, legal, medical or investment decisions; confirm details with the maker or an authoritative source first.</p>
<h2>No affiliation</h2>
<p>Robot Dictionary is independent. It is not affiliated with, sponsored or endorsed by any manufacturer, laboratory, agency, investor or company named on this site, including Y Combinator. Inclusion of a robot or company is not a recommendation.</p>
<h2>Trademarks</h2>
<p>Robot names, company names and logos are trademarks or registered trademarks of their respective owners. They are used here only to identify the products described.</p>
<h2>Sources and licences</h2>
<ul>
<li>Every entry lists its sources. Facts are drawn from makers' publications, research papers, reputable press, the Y Combinator public company directory, Wikidata and Wikipedia.</li>
<li>Structured data from Wikidata is used under its CC0 public domain dedication.</li>
<li>Any text taken from Wikipedia is marked as such on the page, linked to the article, and available under the Creative Commons Attribution ShareAlike 4.0 licence.</li>
<li>Company descriptions from the Y Combinator directory are summarised in our own words and linked to the company profile.</li>
<li>The definitions, notes and arrangement of the dictionary are original work. The compiled dataset is offered under CC BY 4.0 with attribution to Robot Dictionary.</li>
</ul>
<h2>Images</h2>
<p>Plates are published only when the image is our own, supplied by the maker for this purpose, or released under a licence that allows it, with credit given in the sources of the entry. If you hold rights in an image shown here and did not agree to its use, write to us and it will be taken down.</p>
<h2>Corrections and removal requests</h2>
<p>To correct an entry, report an error, or ask for content to be removed, write to <a href="mailto:{CONTACT}">{CONTACT}</a> with the address of the page and the reason. Every request is reviewed and the outcome recorded in the next daily revision.</p>
<h2>Privacy</h2>
<p>This site has no accounts, no advertising, no analytics and sets no cookies. Pages and fonts are served from GitHub Pages, which may keep standard server logs; see the <a href="https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement">GitHub privacy statement</a>. The search box works entirely in your browser.</p>
<h2>Copyright</h2>
<p>Text and design copyright {TODAY.year} Robot Dictionary, except where another licence is stated above.</p>
</div></main>'''

def write(out):
    old = set()
    if os.path.exists(GENERATED_LIST):
        old = {l.strip() for l in open(GENERATED_LIST, encoding="utf-8") if l.strip()}
    for rel, content in out.files.items():
        p = os.path.join(ROOT, rel)
        os.makedirs(os.path.dirname(p) or ROOT, exist_ok=True)
        data = content.encode("utf-8") if isinstance(content, str) else content
        if os.path.exists(p) and open(p, "rb").read() == data: continue
        with open(p, "wb") as f: f.write(data)
    stale = old - set(out.files)
    for rel in sorted(stale):
        p = os.path.join(ROOT, rel)
        if os.path.exists(p): os.remove(p)
        d = os.path.dirname(p)
        while d != ROOT and os.path.isdir(d) and not os.listdir(d):
            os.rmdir(d); d = os.path.dirname(d)
    with open(GENERATED_LIST, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(out.files)) + "\n")

if __name__ == "__main__":
    build()
