#!/usr/bin/env python3
"""Cut robots out of their pictures so they can stand on the page.

For every entry with a picture, a larger copy of the same Wikimedia Commons file is fetched,
the background is removed with rembg, and the robot is saved on a transparent ground as
img/<id>.c.webp (fits 720x720) and img/<id>.ct.webp (fits 240x240). A silhouette for the
daily game is made from the same mask. Measurements of each cut are kept in data/cutouts.json
and cuts that fail them are not used. The licence of the original picture applies to the cut.
"""
import datetime as dt, hashlib, io, json, os, sys, time, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, "img")
PICS = os.path.join(ROOT, "data", "images.json")
META = os.environ.get("CUTOUT_META") or os.path.join(ROOT, "data", "cutouts.json")
BLOCK = os.path.join(ROOT, "data", "state", "cutout_blocklist.json")
UA = "RobotDictionaryBot/1.0 (https://robotdictionary.com; contact@robotdictionary.com)"
TODAY = os.environ.get("BUILD_DATE") or dt.datetime.now(dt.timezone.utc).date().isoformat()
MODEL = os.environ.get("CUTOUT_MODEL", "birefnet-general")
MAX = int(os.environ.get("MAX_CUTOUTS", "20"))
SHARD = os.environ.get("CUTOUT_SHARD", "")          # "k/n" splits the work between runners
RAW = os.environ.get("KEEP_RAW", "")                # keep sources and masks here for review
BIG, SMALL = (720, 720), (240, 240)

def log(*a): print(*a, flush=True)

def load(p, d):
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else d

def save(p, o):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f: json.dump(o, f, indent=1, ensure_ascii=False, sort_keys=True); f.write("\n")

def get(url, binary=False, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60) as r:
                data = r.read()
            return data if binary else json.loads(data)
        except Exception as e:
            log("retry", i, url[:90], repr(e)[:120]); time.sleep(3 * (i + 1))
    return None

def source(file):
    d = get("https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode({
        "action": "query", "titles": "File:" + file, "prop": "imageinfo", "iiprop": "url|size", "iiurlwidth": "1280", "format": "json"}))
    for p in ((d or {}).get("query", {}).get("pages") or {}).values():
        ii = (p.get("imageinfo") or [None])[0]
        if ii: return get(ii.get("thumburl") or ii["url"], binary=True)
    return None

def silhouette_name(eid):
    return hashlib.sha1(("silhouette:" + eid).encode()).hexdigest()[:16]

def finish(rgb, mask):
    """Clean the mask, measure it, and return the cropped RGBA cut with its measurements."""
    import numpy as np
    from PIL import Image
    from scipy import ndimage
    a = np.asarray(mask.convert("L"), dtype=np.float32)
    H, W = a.shape
    solid = a > 127
    total = int(solid.sum())
    if total < 0.01 * H * W:
        return None, {"ok": False, "why": "nothing found"}
    lab, n = ndimage.label(solid)
    sizes = ndimage.sum(solid, lab, index=np.arange(1, n + 1))
    big = float(sizes.max())
    keep = np.isin(lab, np.nonzero(sizes >= max(0.03 * big, 0.002 * H * W))[0] + 1)
    near = ndimage.binary_dilation(keep, iterations=max(2, round(0.006 * max(H, W))))
    a = np.where(near, a, 0)
    kept = keep.sum()
    m = {"cov": round(total / (H * W), 3), "main": round(big / max(1, kept), 3), "parts": int(len(np.unique(lab[keep]))),
         "top": round(float(solid[0].mean()), 3), "bottom": round(float(solid[-1].mean()), 3),
         "left": round(float(solid[:, 0].mean()), 3), "right": round(float(solid[:, -1].mean()), 3),
         "soft": round(float(((a > 20) & (a < 235)).sum()) / max(1, total), 3)}
    why = []
    if m["cov"] > 0.85: why.append("kept the background")
    if max(m["top"], m["left"], m["right"]) > 0.25: why.append("cut at the edge")
    if m["bottom"] > 0.55: why.append("cut at the bottom")
    if m["soft"] > 0.35: why.append("unsure edges")
    if m["main"] < 0.6: why.append("in pieces")
    m["ok"] = not why
    if why: m["why"] = ", ".join(why)
    ys, xs = np.nonzero(a > 10)
    y0, y1, x0, x1 = int(ys.min()), int(ys.max()) + 1, int(xs.min()), int(xs.max()) + 1
    pad = round(0.02 * max(y1 - y0, x1 - x0))
    y0, x0, y1, x1 = max(0, y0 - pad), max(0, x0 - pad), min(H, y1 + pad), min(W, x1 + pad)
    rgba = np.dstack([np.asarray(rgb.convert("RGB")), a.astype(np.uint8)])[y0:y1, x0:x1]
    return Image.fromarray(rgba, "RGBA"), m

def write_cut(eid, cut, meta_row):
    from PIL import Image
    big = cut.copy(); big.thumbnail(BIG, resample=Image.LANCZOS)
    small = cut.copy(); small.thumbnail(SMALL, resample=Image.LANCZOS)
    big.save(os.path.join(IMG, f"{eid}.c.webp"), "WEBP", quality=80, method=6, exact=False)
    small.save(os.path.join(IMG, f"{eid}.ct.webp"), "WEBP", quality=78, method=6)
    # silhouette for the game: one flat colour, named so the file does not give the answer away
    sil = Image.new("RGBA", big.size, (28, 27, 24, 255)); sil.putalpha(big.getchannel("A"))
    os.makedirs(os.path.join(IMG, "s"), exist_ok=True)
    sil.save(os.path.join(IMG, "s", silhouette_name(eid) + ".webp"), "WEBP", lossless=True, method=6)
    meta_row.update({"w": big.size[0], "h": big.size[1], "tw": small.size[0], "th": small.size[1], "s": silhouette_name(eid)})

def main():
    from PIL import Image
    from rembg import new_session, remove
    pics = load(PICS, {}); meta = load(META, {}); blocked = set(load(BLOCK, []))
    only = [x for x in os.environ.get("CUTOUT_IDS", "").split(",") if x]
    todo = only or [i for i in sorted(pics) if i not in meta and i not in blocked and os.path.exists(os.path.join(IMG, f"{i}.webp"))]
    if SHARD:
        k, n = (int(x) for x in SHARD.split("/")); todo = todo[k::n]
    todo = todo[:MAX]
    log("to cut", len(todo), "with", MODEL)
    if not todo: return
    session = new_session(MODEL)
    for n_done, eid in enumerate(todo, 1):
        p = pics.get(eid) or {}
        data = source(p["file"]) if p.get("file") else None
        try:
            rgb = Image.open(io.BytesIO(data)).convert("RGB") if data else Image.open(os.path.join(IMG, f"{eid}.webp")).convert("RGB")
        except Exception as ex:
            log("bad source", eid, ex); continue
        rgb.thumbnail((1280, 1280))
        t = time.time()
        mask = remove(rgb, session=session, only_mask=True)
        if mask.size != rgb.size: mask = mask.resize(rgb.size)
        cut, m = finish(rgb, mask)
        m.update({"model": MODEL, "added": TODAY, "src": "commons" if data else "plate"})
        if RAW:
            os.makedirs(RAW, exist_ok=True)
            rgb.save(os.path.join(RAW, f"{eid}.jpg"), quality=90); mask.save(os.path.join(RAW, f"{eid}.png"))
        if cut is not None: write_cut(eid, cut, m)
        meta[eid] = m
        log(n_done, eid, round(time.time() - t, 1), "ok" if m.get("ok") else m.get("why"))
        if n_done % 10 == 0: save(META, meta)
        time.sleep(0.2)
    save(META, meta)

if __name__ == "__main__":
    main()
