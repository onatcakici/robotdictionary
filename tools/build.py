#!/usr/bin/env python3
"""Build robotdictionary.com from data/entries/*.json into static pages at the repository root."""
import base64, csv, datetime as dt, hashlib, html, io, json, os, re, shutil, sys, unicodedata
from collections import defaultdict, Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://robotdictionary.com"
REPO = "https://github.com/onatcakici/robotdictionary"
CONTACT = "contact@robotdictionary.com"
TODAY = dt.date.fromisoformat(os.environ.get("BUILD_DATE") or dt.datetime.now(dt.timezone.utc).date().isoformat())

SECTIONS = [
    ("humanoids", "Humanoids", "Machines built in the human form, from research bipeds to factory workers.", "humanoid robot"),
    ("quadrupeds", "Quadrupeds", "Four legged walkers and the other legged machines.", "quadruped robot"),
    ("wheeled", "Wheeled machines", "Delivery robots, cleaners, mowers, warehouse movers and inspection crawlers.", "wheeled robot"),
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
RESERVED = {s[0] for s in SECTIONS} | {"assets", "data", "tools", "makers", "countries", "timeline", "yc", "a-z", "about", "news", "credits",
            "legal", "recent", "search", "img", "feed.xml", "sitemap.xml", "robots.txt", "404.html", "index.html", "CNAME", "play", "evolution"}
SHORT = {"humanoids": "Humanoid", "quadrupeds": "Legged", "wheeled": "Wheeled", "arms": "Arm", "rovers": "Rover",
         "medical": "Medical", "marine": "Marine", "other": "Other"}
LEGEND = {"humanoids": "Humanoids", "quadrupeds": "Quadrupeds", "wheeled": "Wheeled", "arms": "Arms", "rovers": "Rovers",
          "medical": "Medical", "marine": "Marine", "other": "Other"}
STATUS_GROUP = {"production": 1, "service": 1, "pilot": 1, "research": 2, "prototype": 2, "development": 2, "concept": 2,
                "retired": 3, "discontinued": 3, "lost": 3, "completed": 3}
REGIONS = ["", "the Americas", "Europe", "East Asia", "South and Southeast Asia", "the Middle East", "Oceania", "Africa"]
REGION_OF = {}
for _r, _cs in ((1, "United States|Canada|Brazil|Mexico|Argentina|Chile|Colombia"),
                (2, "Germany|Switzerland|United Kingdom|France|Denmark|Spain|Netherlands|Sweden|Italy|Russia|Soviet Union|Norway|Poland|"
                    "Luxembourg|Austria|Estonia|Hungary|Ukraine|Latvia|Czechia|Ireland|Portugal|Serbia|Europe|Belgium|Finland|Greece|Slovenia|Croatia"),
                (3, "China|Japan|South Korea|Hong Kong|Taiwan"), (4, "India|Vietnam|Bangladesh|Singapore|Thailand|Malaysia|Indonesia|Pakistan|Sri Lanka"),
                (5, "Israel|Turkey|Iran|United Arab Emirates|Yemen|Saudi Arabia|Qatar"), (6, "Australia|New Zealand"), (7, "South Africa|Egypt|Nigeria|Kenya")):
    for _c in _cs.split("|"): REGION_OF[_c] = _r
# Robots lined up on the front page, oldest first.
MARCH = ["digesting-duck", "silver-swan", "george", "shakey", "lunokhod-1", "sojourner", "aibo-ers-110", "asimo", "roomba",
         "bigdog", "nao", "curiosity", "atlas-hydraulic", "pepper", "spot", "ameca", "unitree-g1"]
# Landmarks on the evolution chart, each with one line.
MARKS = [("digesting-duck", "Appeared to digest grain. It did not."),
         ("silver-swan", "Preens, then swallows a silver fish."),
         ("el-ajedrecista", "Mates a lone king, every time."),
         ("elektro", "Smoked cigarettes at the 1939 World's Fair."),
         ("unimate", "The first robot arm on a factory line."),
         ("shakey", "First robot to reason about its own moves."),
         ("lunokhod-1", "First rover on another world."),
         ("wabot-1", "The first full scale humanoid robot."),
         ("sojourner", "First rover on Mars, at a centimetre a second."),
         ("aibo-ers-110", "A dog that needs charging, not walking."),
         ("asimo", "Walked, ran and climbed stairs."),
         ("roomba", "Put a robot in millions of homes."),
         ("bigdog", "Famous for staying up when kicked."),
         ("nao", "Played football at RoboCup for years."),
         ("curiosity", "Car sized; lowered onto Mars by a sky crane."),
         ("atlas-hydraulic", "Did backflips before it retired."),
         ("pepper", "Built to read faces and greet shoppers."),
         ("spot", "The robot dog that went on sale."),
         ("ameca", "Its facial expressions went viral."),
         ("unitree-g1", "A humanoid announced at $16,000.")]
ROBODLE_START = dt.date(2026, 11, 8)
ROBODLE_FIRST = ["asimo", "spot", "roomba", "curiosity", "pepper", "aibo-ers-110", "sojourner", "nao", "bigdog", "lunokhod-1",
                 "atlas-hydraulic", "shakey", "ameca", "unitree-g1", "digesting-duck", "da-vinci-surgical-system", "lego-mindstorms-ev3",
                 "cozmo", "valkyrie", "icub", "robosapien", "spirit", "mechanical-turk", "kismet", "qrio", "yutu-2", "wakamaru",
                 "lunar-roving-vehicle", "hitchbot", "robonaut-2", "silver-swan", "zhurong", "poo-chi", "el-ajedrecista", "baxter",
                 "astrobee", "reem-c", "george", "puma", "dextre", "genibo", "i-cybie", "rhex", "surena-iv", "roboraptor", "hexbug", "turtlebot"]
ROBODLE_GUESSES = 8
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

def load_json_file(p, default):
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else default

def year_int(e):
    m = re.match(r"(\d{4})", e.get("year") or "")
    return int(m.group(1)) if m else 0

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
            '<nav class="nav" aria-label="Site"><a class="hot" href="/play/">Robodle</a><a href="/evolution/">Evolution</a><a href="/news/">News</a>'
            '<a href="/a-z/">A to Z</a><a href="/makers/">Makers</a><a href="/yc/">YC robots</a><a href="/about/">About</a></nav>'
            '<div class="find" data-find><input type="search" placeholder="Find a robot or maker" aria-label="Find a robot or maker" autocomplete="off">'
            '<ul class="hits" hidden></ul></div></div></header>')

def footer(stats):
    return ('<footer class="colophon"><div class="wrap"><div>'
            '<b>Robot Dictionary</b>'
            '<p>A reference of the world\'s robots in eight sections, revised daily. Every entry lists its sources.</p>'
            f'<p>Corrections and additions to <a class="u" href="mailto:{CONTACT}">{CONTACT}</a>.</p>'
            '<p class="colo">Set in Young Serif and Source Serif 4. Pictures from Wikimedia Commons.</p></div>'
            '<nav aria-label="More"><a href="/about/">About the dictionary</a><a href="/legal/">Legal notice</a><a href="/recent/">Recently added</a>'
            '<a href="/countries/">Countries</a><a href="/timeline/">Timeline</a><a href="/credits/">Picture credits</a><a href="/data/robots.json">Open data</a><a href="/feed.xml">RSS feed</a>'
            f'<a href="{REPO}">GitHub</a></nav></div></footer>')

def page(path, title, desc, body, stats, section=None, jsonld=None, og_type="website", noindex=False, body_class="", scripts=(), image=None):
    canon = SITE + path
    ld = f'<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>' if jsonld else ""
    robots = '<meta name="robots" content="noindex">' if noindex else ""
    extra = "".join(f'<script src="/assets/{s}?v={stats["v"]}" defer></script>\n' for s in scripts)
    return ("<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">\n"
            f"<title>{esc(title)}</title>\n<meta name=\"description\" content=\"{esc(desc)}\">\n{robots}"
            f"<link rel=\"canonical\" href=\"{canon}\">\n"
            f"<meta property=\"og:type\" content=\"{og_type}\"><meta property=\"og:site_name\" content=\"Robot Dictionary\">"
            f"<meta property=\"og:title\" content=\"{esc(title)}\"><meta property=\"og:description\" content=\"{esc(desc)}\">"
            f"<meta property=\"og:url\" content=\"{canon}\"><meta property=\"og:image\" content=\"{SITE}/assets/{image or 'card.png'}\">"
            "<meta name=\"twitter:card\" content=\"summary_large_image\"><meta name=\"twitter:site\" content=\"@robotdictionary\">\n"
            "<link rel=\"icon\" href=\"/assets/icon-32.png\" sizes=\"32x32\" type=\"image/png\"><link rel=\"apple-touch-icon\" href=\"/assets/icon-180.png\">"
            "<link rel=\"alternate\" type=\"application/rss+xml\" title=\"Robot Dictionary, new entries\" href=\"/feed.xml\">\n"
            f"{FONTS}\n<link rel=\"stylesheet\" href=\"/assets/site.css?v={stats['v']}\">\n{ld}\n</head>\n<body{(' class=\"' + body_class + '\"') if body_class else ''}>\n"
            f"{header()}\n{thumbs(section)}\n{body}\n{footer(stats)}\n"
            f"<script src=\"/assets/search.js?v={stats['v']}\" defer></script>\n{extra}</body>\n</html>\n")

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
    if "automaton" in k: return "automaton"
    if "animatronic" in k: return "animatronic figure"
    if "snake" in k or "serpentine" in k: return "snake robot"
    if "toy" in k: return "toy robot"
    if "kit" in k: return "robot kit"
    return "robot"

def status_text(e):
    t = e.get("status_text") or STATUS.get(e.get("status") or "", "")
    return (t.rstrip(".") + ".") if t else ""

def plate(e, eager=False):
    c = e.get("cut")
    if c:
        return (f'<span class="fig"><img src="/img/{e["id"]}.c.webp" width="{c["w"]}" height="{c["h"]}" alt="{esc(e["name"])}"'
                + ('' if eager else ' loading="lazy"') + ' decoding="async"></span>')
    p = e.get("pic")
    if not p: return ""
    return (f'<span class="plate"><img src="/img/{e["id"]}.webp" width="{p["w"]}" height="{p["h"]}" alt="{esc(e["name"])}"'
            + ('' if eager else ' loading="lazy"') + ' decoding="async"></span>')

def cut_img(e, h, cls="", eager=False):
    c = e["cut"]; w = round(c["w"] * h / c["h"])
    src = f'/img/{e["id"]}.ct.webp' if h <= 120 and c.get("th", 0) >= h else f'/img/{e["id"]}.c.webp'
    return (f'<img{(" class=" + chr(34) + cls + chr(34)) if cls else ""} src="{src}" width="{w}" height="{h}" alt="{esc(e["name"])}"'
            + ('' if eager else ' loading="lazy"') + ' decoding="async">')

def fame(e):
    return (300 if any(r.get("kind") == "wikipedia" for r in e.get("refs") or []) else 0) + 60 * len(e.get("facts") or []) + len(" ".join(e.get("body") or [])) + (200 if e.get("pic") else 0)

def shelf_img(e, h=120):
    p = e["pic"]; w = round(p["w"] * h / p["h"])
    return f'<a href="/{e["id"]}/" title="{esc(e["name"])}"><img src="/img/{e["id"]}.webp" width="{w}" height="{h}" alt="{esc(e["name"])}" loading="lazy" decoding="async"></a>'

def thumb(e):
    c = e.get("cut")
    if c:
        return (f'<a class="th cut" href="/{e["id"]}/" tabindex="-1" aria-hidden="true"><img src="/img/{e["id"]}.ct.webp" width="{c["tw"]}" height="{c["th"]}"'
                ' alt="" loading="lazy" decoding="async"></a>')
    p = e.get("pic")
    if not p: return ""
    return (f'<a class="th" href="/{e["id"]}/" tabindex="-1" aria-hidden="true"><img src="/img/{e["id"]}.t.webp" width="{p["tw"]}" height="{p["th"]}"'
            ' alt="" loading="lazy" decoding="async"></a>')

def pic_credit(e):
    p = e.get("pic")
    if not p: return ""
    title = re.sub(r"\.(jpe?g|png|tiff?|webp)$", "", p["file"], flags=re.I)
    lic = f'<a href="{esc(p["license_url"])}" rel="noopener">{esc(p["license"])}</a>' if p.get("license_url") else esc(p["license"])
    lead = "Picture, background removed" if e.get("cut") else "Picture"
    return f'{lead}: <a href="{esc(p["page"])}" rel="noopener">{esc(title)}</a> by {esc(p["author"])}, {lic}, via Wikimedia Commons'

def dict_entry(e, mk, ct):
    st = status_text(e)
    return (f'<p class="dent">{thumb(e)}<a class="hw" href="/{e["id"]}/">{esc(e["name"])}</a> <span class="pos">n., {esc(pos_label(e))}.</span> '
            f'<span class="org">{origin_line(e, mk, ct, links=False)}</span> {esc(e.get("def"))} '
            + (f'<span class="st">{esc(st)}</span>' if st else "") + "</p>")

# ---------- builders ----------
class Out:
    def __init__(self): self.files = {}
    def put(self, rel, content): self.files[rel] = content

def build():
    E = load_entries()
    pics = json.load(open(os.path.join(ROOT, "data", "images.json"), encoding="utf-8")) if os.path.exists(os.path.join(ROOT, "data", "images.json")) else {}
    blocked = set(load_state("image_blocklist.json", []))
    for i, p in pics.items():
        if i in E and i not in blocked and os.path.exists(os.path.join(ROOT, "img", f"{i}.webp")): E[i]["pic"] = p
    cuts = json.load(open(os.path.join(ROOT, "data", "cutouts.json"), encoding="utf-8")) if os.path.exists(os.path.join(ROOT, "data", "cutouts.json")) else {}
    cut_block, cut_allow = set(load_state("cutout_blocklist.json", [])), set(load_state("cutout_allow.json", []))
    for i, c in cuts.items():
        if (i in E and E[i].get("pic") and i not in cut_block and (c.get("ok") or i in cut_allow) and c.get("w")
                and os.path.exists(os.path.join(ROOT, "img", f"{i}.c.webp"))):
            E[i]["cut"] = c
    news = json.load(open(os.path.join(ROOT, "data", "news.json"), encoding="utf-8")) if os.path.exists(os.path.join(ROOT, "data", "news.json")) else []
    news = [n for n in news if n.get("title") and n.get("url")]
    news_by = defaultdict(list)
    for n in news:
        for i in n.get("ids") or []:
            if i in E: news_by[i].append(n)
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
    js_extra = {n: open(os.path.join(ROOT, "tools", "static", n), encoding="utf-8").read() for n in ("play.js", "evolution.js")}
    v = hashlib.sha1((css + js + "".join(js_extra.values())).encode()).hexdigest()[:8]
    stats = {"n": len(ids), "v": v}
    out = Out()

    # robot of the day
    featured = load_state("featured.json", [])
    eligible = [i for i in ids if E[i].get("origin") == "edited" and (E[i].get("body") or E[i].get("facts")) and E[i].get("def")]
    with_pic = [i for i in eligible if E[i].get("pic")]
    if len(with_pic) >= 30: eligible = with_pic
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
            out.put(f'{e["id"]}/index.html', entry_page(e, E, sec_key, title, group, n, prev_e, next_e, mk_pages, ct_pages, stats, news_by.get(e["id"], [])))

    # ---- sections
    for k, (sec_key, title, blurb, _) in enumerate(SECTIONS):
        group = by_sec.get(sec_key, [])
        letters = defaultdict(list)
        for e in group: letters[first_letter(e["name"])].append(e)
        lets = sorted(letters)
        gal = sorted([e for e in group if e.get("cut")], key=lambda e: -fame(e))[:5]
        gal_html = "".join(f'<a href="/{e["id"]}/" tabindex="-1">{cut_img(e, 150)}</a>' for e in gal) if len(gal) >= 3 else ""
        if not gal_html:
            gal = sorted([e for e in group if e.get("pic")], key=lambda e: -fame(e))[:5]
            gal_html = "".join(shelf_img(e, 112) for e in gal)
        body = [f'<section class="cover" style="--c:var(--{sec_key})"><div class="wrap"><div><p class="vol">Section {ROMAN[k]}</p><h1>{esc(title)}</h1>'
                f'<p>{esc(blurb)} <span class="cnt">{len(group):,} entries.</span></p></div>'
                + (f'<div class="gallery{" cuts" if len([e for e in gal if e.get("cut")]) >= 3 else ""}" aria-hidden="true">' + gal_html + '</div>' if gal_html else "")
                + '</div></section>',
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

    # ---- robodle, the daily game, and the evolution chart
    robodle = robodle_build(E, ids)
    out.put("assets/robots.json", json.dumps(robot_rows(E, ids), ensure_ascii=False, separators=(",", ":")))
    out.put("assets/robodle.json", json.dumps(robodle["data"], ensure_ascii=False, separators=(",", ":")))
    lineage = [p for p in load_json_file(os.path.join(ROOT, "data", "lineage.json"), []) if p[0] in E and p[1] in E]
    out.put("assets/lineage.json", json.dumps(lineage, separators=(",", ":")))
    for n, src in js_extra.items(): out.put(f"assets/{n}", src)
    out.put("play/index.html", play_page(stats, robodle))
    out.put("evolution/index.html", evolution_page(E, ids, stats))

    # ---- home
    out.put("index.html", home_page(E, ids, by_sec, rod, featured, changes, mk_pages, ct_pages, stats, makers, countries, news, robodle))

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

    # ---- news
    by_day = defaultdict(list)
    for x in news: by_day[x["date"]].append(x)
    body = ['<main class="wrap"><div class="page-h"><h1>Robotics headlines</h1>'
            '<p>Collected each morning from robotics publishers and linked to the robots they mention. Every headline opens on the publisher\'s own site.</p></div>']
    for d in sorted(by_day, reverse=True)[:45]:
        body.append(f'<section class="batch"><h2>{nice_date(d)}</h2><ul class="news">' + "".join(news_item(x, E) for x in by_day[d]) + "</ul></section>")
    if not news: body.append('<p class="more">The first headlines arrive with the next morning revision.</p>')
    body.append("</main>")
    out.put("news/index.html", page("/news/", "Robotics headlines, linked to the robots | Robot Dictionary",
                                    "Daily robotics headlines from publishers, linked to the Robot Dictionary entries for the robots they mention.", "\n".join(body), stats))

    # ---- picture credits
    pe = sorted([E[i] for i in ids if E[i].get("pic")], key=lambda e: sort_key(e["name"]))
    body = ['<main class="wrap"><div class="page-h"><h1>Picture credits</h1>'
            f'<p>The {len(pe)} pictures in the dictionary come from Wikimedia Commons under free licences. They are shown in reduced size; follow each link for the original and its full licence.</p></div>',
            '<div class="doc" style="max-width:none"><ol class="refs" style="columns:2;column-gap:40px">']
    body += [f'<li style="break-inside:avoid"><a href="/{e["id"]}/">{esc(e["name"])}</a>. {pic_credit(e)}</li>' for e in pe]
    body.append("</ol></div></main>")
    out.put("credits/index.html", page("/credits/", "Picture credits | Robot Dictionary", "Authors and licences of the pictures used in the Robot Dictionary.", "\n".join(body), stats))

    # ---- about, legal, 404
    out.put("about/index.html", page("/about/", "About the Robot Dictionary", "How the Robot Dictionary is compiled, sourced and revised every day.", about_body(stats, len(makers), len(countries)), stats))
    out.put("legal/index.html", page("/legal/", "Legal notice | Robot Dictionary", "Disclaimer, sources and licences, trademarks, corrections and privacy for robotdictionary.com.", legal_body(), stats))
    out.put("404.html", page("/404.html", "No such entry | Robot Dictionary", "This page is not in the dictionary.",
                             '<main class="wrap"><div class="page-h"><h1>No such entry</h1><p>Nothing in the present edition answers to this address. Perhaps it has not been built yet. '
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
                if fn.endswith((".woff2", ".png", ".jpg", ".svg", ".ico", ".txt")):
                    out.put(f"assets/{sub + '/' if sub == 'fonts' else ''}{fn}", open(os.path.join(d, fn), "rb").read())
    out.put("data/robots.json", json.dumps(open_data(E, ids), ensure_ascii=False, indent=1) + "\n")
    out.put("data/robots.csv", open_csv(E, ids))
    urls = ["/", "/play/", "/evolution/", "/news/", "/a-z/", "/makers/", "/countries/", "/timeline/", "/yc/", "/recent/", "/about/", "/legal/", "/credits/"] + [f"/{s[0]}/" for s in SECTIONS]
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

def home_page(E, ids, by_sec, rod, featured, changes, mk, ct, stats, makers, countries, news=(), robodle=None):
    rod_sec = SEC[rod["section"]]
    dated = sum(1 for i in ids if year_int(E[i]))
    body = rod.get("body") or []
    excerpt = body[0] if body else ("; ".join(rod.get("facts") or [])[:300])
    today = (robodle or {}).get("today")
    sil = E[today["id"]]["cut"]["s"] if today and today["id"] in E and E[today["id"]].get("cut") else ""
    h = ['<main class="home-main">',
         '<section class="hero"><div class="wrap"><h1>Every robot worth knowing, from 1739 to this morning.</h1>'
         f'<p class="deck">A reference of {stats["n"]:,} robots with their makers, dates, measures and sources. Revised every day.</p></div>',
         march_html(E),
         '<div class="wrap"><div class="bigfind" data-find><input type="search" placeholder="Find a robot, maker or country" aria-label="Find a robot, maker or country" autocomplete="off"><ul class="hits" hidden></ul>'
         '<p>Try Atlas, Unitree, Opportunity or Japan. Press / to search from any page.</p></div></div></section>',
         '<section class="ways wrap">'
         + (f'<a class="way play-way" href="/play/"><span class="sil"><img src="/img/s/{sil}.webp" alt="" width="200" height="200" loading="lazy"></span>'
            f'<span class="wt"><em>Robodle No. {today["n"]}</em><b>Who is that robot?</b><span>Name today\'s robot from its shadow in eight guesses. A new one every midnight.</span><span class="go">Play</span></span></a>' if sil else "")
         + f'<a class="way evo-way" href="/evolution/">{mini_skyline(E, ids)}<span class="wt"><em>The chart</em><b>The evolution of robots</b>'
           f'<span>All {dated:,} dated robots on one chart, from a clockwork duck to this year\'s humanoids.</span><span class="go">Open the chart</span></span></a>'
         + '</section>',
         '<div class="wrap"><hr class="double"><div class="spread"><section><h2 class="label">Robot of the day</h2>'
         + (f'<article class="today"><a href="/{rod["id"]}/" aria-label="{esc(rod["name"])}">{plate(rod, True)}</a><div>' if rod.get("pic") else '<article class="today noimg"><div>')
         + f'<h2><a href="/{rod["id"]}/">{esc(rod["name"])}</a></h2>'
         f'<p class="pos"><i>n., {esc(pos_label(rod))}.</i> <span class="org">{origin_line(rod, mk, ct)}</span> <span class="st">{esc(status_text(rod))}</span></p>'
         f'<p class="def">{esc(rod.get("def"))}</p>'
         + (f'<p class="more">{esc(excerpt)}</p>' if excerpt else "")
         + f'<p class="more"><a class="u" href="/{rod["id"]}/">Read the full entry</a> in <a class="u" href="/{rod["section"]}/">{esc(rod_sec[1])}</a>.</p></div></article>'
         + '</section><aside><h2 class="label">In the news</h2>'
         + ('<ul class="news">' + "".join(news_item(x, E) for x in news[:7]) + '</ul><p class="more" style="font-size:15.5px;margin-top:10px"><a class="u" href="/news/">All robotics headlines</a></p>'
            if news else '<p class="more">Headlines from robotics publishers appear here each morning.</p>')
         + '</aside></div>',
         '<section class="contents"><h2>Contents</h2><ol class="toc">']
    for k, (key, title, blurb, _) in enumerate(SECTIONS):
        group = by_sec.get(key, [])
        pref = [E[i] for i in SAMPLES.get(key, []) if i in E and E[i]["section"] == key]
        rest = sorted([e for e in group if e not in pref], key=lambda e: -fame(e))
        sample = (pref + rest)[:3]
        tp = next((e for e in sorted(group, key=lambda e: -fame(e)) if e.get("cut")), None) or next((e for e in sorted(group, key=lambda e: -fame(e)) if e.get("pic")), None)
        tpi = ""
        if tp and tp.get("cut"):
            tpi = f'<a class="tp cut" href="/{tp["id"]}/" tabindex="-1" aria-hidden="true">{cut_img(tp, 60)}</a>'
        elif tp:
            tpi = f'<a class="tp" href="/{tp["id"]}/" tabindex="-1" aria-hidden="true"><img src="/img/{tp["id"]}.t.webp" width="{tp["pic"]["tw"]}" height="{tp["pic"]["th"]}" alt="" loading="lazy"></a>'
        h.append(f'<li style="--c:var(--{key})"><span class="num">{ROMAN[k]}</span><div><span class="t"><a href="/{key}/">{esc(title)}</a></span>'
                 f'<span class="x">{esc(blurb)} <em>Including ' + ", ".join(f'<a href="/{e["id"]}/">{esc(e["name"])}</a>' for e in sample) + '.</em></span></div>'
                 + (tpi or '<span></span>') + f'<span class="n">{len(group):,} entries</span></li>')
    h.append('</ol><nav class="more-ways" aria-label="Other ways in">'
             f'<a href="/a-z/">A to Z, all {len(ids):,} entries</a><a href="/makers/">{len(makers):,} makers</a><a href="/countries/">{len(countries)} countries</a>'
             f'<a href="/timeline/">Timeline</a><a href="/yc/">Robots from Y Combinator companies</a><a href="/recent/">Recently added</a></nav></section></div></main>')
    ld = {"@context": "https://schema.org", "@type": "WebSite", "name": "Robot Dictionary", "url": SITE + "/",
          "description": "A reference of the world's robots, revised daily."}
    return page("/", "Robot Dictionary: every robot worth knowing, revised daily",
                f"Robot Dictionary records {len(ids):,} robots, from ASIMO and Atlas to Mars rovers and new startup machines, each with maker, measures, status and sources. "
                "Play Robodle, the daily robot guessing game.",
                "\n".join(h), stats, None, ld, body_class="home")

def march_html(E):
    row = [E[i] for i in MARCH if i in E and E[i].get("cut") and year_int(E[i])]
    if len(row) < 6: return ""
    items = []
    for e in sorted(row, key=year_int):
        items.append(f'<a class="m" href="/{e["id"]}/">{cut_img(e, 200, eager=True)}<span class="my">{year_int(e)}</span>'
                     f'<span class="mn">{esc(e["name"])}</span></a>')
    return ('<div class="march" data-march aria-label="Robots in order of their first showing">'
            '<div class="mtrack">' + "".join(items) + '</div></div>')

def mini_skyline(E, ids, w=320, h=120):
    y0, y1 = 1950, TODAY.year
    cols = defaultdict(Counter)
    for i in ids:
        y = year_int(E[i])
        if y0 <= y <= y1: cols[y][E[i]["section"]] += 1
    top = max((sum(c.values()) for c in cols.values()), default=1)
    n = y1 - y0 + 1; bw = w / n; u = (h - 4) / top
    rects = []
    for k, y in enumerate(range(y0, y1 + 1)):
        acc = 0
        for key, *_ in SECTIONS:
            c = cols[y].get(key, 0)
            if not c: continue
            rects.append(f'<rect x="{k * bw:.1f}" y="{h - (acc + c) * u:.1f}" width="{max(1, bw - 1):.1f}" height="{c * u:.1f}" style="fill:var(--{key})"/>')
            acc += c
    return (f'<svg class="mini" viewBox="0 0 {w} {h}" width="{w}" height="{h}" aria-hidden="true" focusable="false">' + "".join(rects)
            + f'<line x1="0" x2="{w}" y1="{h - .5}" y2="{h - .5}" class="base"/></svg>')

def robot_rows(E, ids):
    sec_ix = {s[0]: k for k, s in enumerate(SECTIONS)}
    rows = []
    for i in ids:
        e = E[i]
        d = e.get("def") or ""
        if len(d) > 170: d = d[:167].rsplit(" ", 1)[0] + "..."
        c = e.get("country") or ""
        reg = REGION_OF.get(c) or REGION_OF.get(re.split(r",| and ", c)[0].strip(), 0)
        rows.append([i, e["name"], " ".join(e.get("aka") or []), sec_ix[e["section"]], c, reg, e.get("maker") or "", year_int(e),
                     STATUS_GROUP.get(e.get("status") or "", 0), 2 if e.get("cut") else (1 if e.get("pic") else 0), d])
    return rows

def robodle_obf(s, key):
    kb = key.encode()
    return base64.b64encode(bytes(c ^ kb[k % len(kb)] for k, c in enumerate(s.encode()))).decode()

def robodle_pool(E):
    return {i for i, e in E.items() if e.get("cut") and year_int(e) and e.get("maker")
            and (any(r.get("kind") == "wikipedia" for r in e.get("refs") or []) or fame(e) >= 1000)}

def robodle_build(E, ids):
    import random
    pool = robodle_pool(E)
    today_n = (TODAY - ROBODLE_START).days + 1
    sched = []
    for d in load_state("robodle.json", []):
        if d["n"] <= today_n or d["id"] in pool: sched.append(d)
        else: break
    rest = sorted(pool - set(ROBODLE_FIRST)); random.Random("robodle").shuffle(rest)
    order = [i for i in ROBODLE_FIRST if i in pool] + rest
    while order and (not sched or sched[-1]["n"] < today_n + 40):
        n = sched[-1]["n"] + 1 if sched else 1
        recent = {d["id"] for d in sched[-365:]}
        pick = next((i for i in order if i not in recent), None)
        if pick is None:
            last = {d["id"]: d["n"] for d in sched}
            pick = min(order, key=lambda i: last.get(i, 0))
        sched.append({"n": n, "date": (ROBODLE_START + dt.timedelta(days=n - 1)).isoformat(), "id": pick})
    if sched: save_state("robodle.json", sched)
    days = [[d["n"], d["date"], robodle_obf(d["id"], "robodle:" + d["date"]), E[d["id"]]["cut"]["s"]]
            for d in sched if today_n - 60 <= d["n"] <= today_n + 2 and d["id"] in E and E[d["id"]].get("cut")]
    soon = {d["id"] for d in sched if d["n"] >= today_n}
    practice = [[robodle_obf(i, "practice"), E[i]["cut"]["s"]] for i in sorted(pool - soon)]
    today = next((dict(d, s=E[d["id"]]["cut"]["s"]) for d in sched if d["n"] == today_n and d["id"] in E and E[d["id"]].get("cut")), None)
    return {"data": {"start": ROBODLE_START.isoformat(), "max": ROBODLE_GUESSES, "days": days, "practice": practice}, "today": today, "n": today_n}

def play_page(stats, robodle):
    today = robodle.get("today")
    secs = json.dumps([[s[0], SHORT[s[0]]] for s in SECTIONS])
    regs = json.dumps(REGIONS)
    if not today:
        main = ('<main class="wrap"><div class="page-h"><h1>Robodle</h1><p>The daily robot guessing game opens with the next morning revision. '
                'Come back tomorrow.</p></div></main>')
    else:
        main = f"""<main class="wrap play" id="robodle" data-sections='{esc(secs)}' data-regions='{esc(regs)}' data-max="{ROBODLE_GUESSES}">
<header class="play-h"><h1>Robodle</h1><p class="play-no"><span data-no>No. {today["n"]}</span> <span data-date></span></p>
<p class="play-deck">Name today's robot from its shadow. You have eight guesses, and each one tells you how close you came.</p></header>
<div class="play-grid">
<figure class="shadow"><img data-sil src="/img/s/{esc(today["s"])}.webp" alt="Today's robot, in silhouette"><img data-reveal alt="" hidden></figure>
<div class="play-side">
<div class="guess" data-guess><input type="text" placeholder="Type a robot's name" aria-label="Your guess" autocomplete="off" autocapitalize="off" spellcheck="false"><ul class="hits" hidden></ul></div>
<p class="left" data-left></p>
<div class="rows" data-rows aria-live="polite"><div class="row head" aria-hidden="true"><span class="nmh">Your guess</span><span>Section</span><span>Country</span><span>Maker</span><span>Year</span><span>Status</span></div></div>
<p class="hint" data-hint hidden></p>
<section class="done" data-done hidden></section>
</div></div>
<details class="how"><summary>How to play</summary>
<p>Every day there is one robot from the dictionary to find. Type a name and pick it from the list. Each guess is compared with the answer.</p>
<ul><li><b class="sw hit"></b>Green means the same.</li>
<li><b class="sw near"></b>Yellow means close: a country in the same part of the world, a year within five, or a maker that shares a name.</li>
<li><b class="sw miss"></b>Plain means not it.</li></ul>
<p>Arrows on the year point toward the answer. After five misses you are told the first letter. A new robot arrives at midnight, your time. Your results stay in this browser.</p></details>
</main>"""
    ld = {"@context": "https://schema.org", "@type": "VideoGame", "name": "Robodle", "url": SITE + "/play/", "genre": "Puzzle",
          "description": "Guess the robot from its silhouette in eight tries. A new robot every day.", "gamePlatform": "Web browser",
          "publisher": {"@type": "Organization", "name": "Robot Dictionary", "url": SITE + "/"}}
    return page("/play/", "Robodle: guess the robot from its shadow | Robot Dictionary",
                "Robodle is a daily robot guessing game. Name the robot from its silhouette in eight guesses. A new robot every day.",
                main, stats, None, ld, scripts=("play.js",), image="robodle-card.png", body_class="playpage")

def evolution_page(E, ids, stats):
    dated = [E[i] for i in ids if year_int(E[i])]
    years = sorted(year_int(e) for e in dated)
    n = len(dated)
    median = years[n // 2] if years else 0
    cnt = Counter(years)
    busiest, bn = max(cnt.items(), key=lambda kv: (kv[1], kv[0])) if cnt else (0, 0)
    first = min(dated, key=lambda e: (year_int(e), e["name"]))
    before = sum(1 for y in years if y < 1950)
    marks = [[i, note] for i, note in MARKS if i in E and year_int(E[i])]
    secs = json.dumps([[s[0], s[1]] for s in SECTIONS])
    legend = "".join(f'<button type="button" data-s="{k}" style="--c:var(--{s[0]})" aria-pressed="false" title="Show only {esc(s[1].lower())}">{esc(LEGEND[s[0]])}</button>' for k, s in enumerate(SECTIONS))
    body = f"""<main class="evo-page">
<div class="wrap"><header class="page-h evo-h"><h1>The evolution of robots</h1>
<p>All {n:,} dated robots in the dictionary, one dot each, stacked by the year they were first shown. Point at a dot to see the robot and its family.</p></header>
</div>
<div id="evo" class="evo" data-sections='{esc(secs)}' data-marks='{esc(json.dumps(marks, ensure_ascii=False))}'>
<div class="evo-bar wrap"><div class="evo-legend" role="group" aria-label="Show one section">{legend}</div>
<div class="evo-find"><input type="search" placeholder="Find a robot on the chart" aria-label="Find a robot on the chart" autocomplete="off"><ul hidden></ul></div></div>
<div class="evo-stage" tabindex="0" aria-label="Chart of robots by year, scroll sideways"><div class="evo-tip" hidden></div></div>
<noscript><p class="wrap">The chart needs JavaScript. The same robots are listed by year on the <a href="/timeline/">timeline</a>.</p></noscript>
</div>
<div class="wrap evo-foot"><dl class="figures">
<div><dt>{year_int(first)}</dt><dd>The oldest entry, <a href="/{first['id']}/">{esc(first['name'])}</a>.</dd></div>
<div><dt>{before}</dt><dd>Robots here first shown before 1950.</dd></div>
<div><dt>{median}</dt><dd>Half of them were first shown in {median} or later.</dd></div>
<div><dt>{busiest}</dt><dd>The busiest year so far, with {bn} new robots.</dd></div>
</dl><p>Red curves join a robot to the machines it came from and the ones that followed, where the record is clear. {len(ids) - n:,} entries without a known year are left off the chart; every robot is listed by year on the <a class="u" href="/timeline/">timeline</a>. Years before 1950 are drawn closer together, and each year from 1990 has two columns.</p></div>
</main>"""
    ld = {"@context": "https://schema.org", "@type": "Dataset", "name": "The evolution of robots", "url": SITE + "/evolution/",
          "description": f"{n} robots by the year they were first shown, from {year_int(first)} to {TODAY.year}.", "creator": {"@type": "Organization", "name": "Robot Dictionary"},
          "license": "https://creativecommons.org/licenses/by/4.0/"}
    return page("/evolution/", "The evolution of robots, 1739 to today, on one chart | Robot Dictionary",
                f"Every robot in the Robot Dictionary on one chart: {n:,} machines from {year_int(first)} to {TODAY.year}, by year and kind, with their family lines.",
                body, stats, None, ld, scripts=("evolution.js",), image="evolution-card.jpg", body_class="evopage")

def news_item(n, E, show_ids=True):
    d = dt.date.fromisoformat(n["date"])
    robots = [E[i] for i in (n.get("ids") or []) if i in E] if show_ids else []
    return (f'<li><a class="nh" href="{esc(n["url"])}" rel="noopener nofollow">{esc(n["title"])}</a>'
            f'<span class="ns">{esc(n["source"])}, {d.day} {d.strftime("%b")}'
            + ("".join(f' <a class="nr" href="/{r["id"]}/">{esc(r["name"])}</a>' for r in robots) if robots else "") + "</span></li>")

def entry_page(e, E, sec_key, sec_title, group, n, prev_e, next_e, mk, ct, stats, news_for=()):
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
    if e.get("pic"): body.append(f'<div class="mplate">{plate(e)}</div>')
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
    if news_for:
        body.append('<h3>In the news</h3><ul class="news">' + "".join(news_item(x, E, False) for x in news_for[:6]) + "</ul>")
    if refs or e.get("pic"):
        body.append('<h3>Sources</h3><ol class="refs">' + "".join(
            f'<li><a href="{esc(r["url"])}" rel="noopener">{esc(r["label"])}</a>, {esc(domain(r["url"]))}</li>' for r in refs)
            + (f'<li>{pic_credit(e)}</li>' if e.get("pic") else "") + "</ol>")
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
    if e.get("pic"): about["image"] = f"{SITE}/img/{e['id']}.webp"
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
<h2>Pictures</h2>
<p>Pictures come from Wikimedia Commons under free licences and are shown in reduced size to keep pages fast. Each one is credited in the sources of its entry and on the <a href="/credits/">picture credits</a> page. Entries without a suitable free picture are shown without one.</p>
<h2>News</h2>
<p>Each morning the dictionary also collects robotics headlines from publishers and links them to the robots they mention. They appear on the front page, on the robots' own entries and under <a href="/news/">News</a>.</p>
<h2>Robodle and the chart</h2>
<p><a href="/play/">Robodle</a> is a daily game drawn from the dictionary: one robot a day, shown only as a shadow, to be named in eight guesses. <a href="/evolution/">The evolution of robots</a> puts every dated entry on a single chart, so the whole history can be seen at once. Both are rebuilt every morning with the rest of the site.</p>
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
<h2>Pictures</h2>
<p>Pictures come from Wikimedia Commons under free licences such as Creative Commons Attribution, Attribution ShareAlike, CC0 or the public domain, and are shown in reduced size. Each picture is credited with its author and licence in the sources of its entry and on the <a href="/credits/">picture credits</a> page. Photographs that show identifiable people are left out. Many pictures are shown with their background removed so the robot stands on the page; these adapted versions keep the licence of the original and are marked as such in the credits. If you hold rights in a picture shown here and did not agree to its use, write to us and it will be taken down.</p>
<h2>News headlines</h2>
<p>The news column lists headlines from robotics publishers with a link to the original article and the publisher's name. Articles are not copied or hosted here. Publishers who do not want their headlines listed can write to us.</p>
<h2>Corrections and removal requests</h2>
<p>To correct an entry, report an error, or ask for content to be removed, write to <a href="mailto:{CONTACT}">{CONTACT}</a> with the address of the page and the reason. Every request is reviewed and the outcome recorded in the next daily revision.</p>
<h2>Privacy</h2>
<p>This site has no accounts, no advertising, no analytics and sets no cookies. Pages and fonts are served from GitHub Pages, which may keep standard server logs; see the <a href="https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement">GitHub privacy statement</a>. The search box works entirely in your browser. Robodle keeps your results in your own browser's storage; they are never sent to us.</p>
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
