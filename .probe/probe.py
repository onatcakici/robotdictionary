import json, urllib.request, urllib.parse, time, os, sys
UA = "RobotDictionaryBot/1.0 (https://robotdictionary.com; contact@robotdictionary.com)"
EP = "https://query.wikidata.org/sparql"
def sparql(q):
    data = urllib.parse.urlencode({"query": q, "format": "json"}).encode()
    req = urllib.request.Request(EP, data=data, headers={"User-Agent": UA, "Accept": "application/sparql-results+json"})
    t = time.time()
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            out = json.load(r)
        return {"ok": True, "secs": round(time.time()-t,1), "rows": [{k: v["value"] for k, v in b.items()} for b in out["results"]["bindings"]]}
    except Exception as e:
        return {"ok": False, "secs": round(time.time()-t,1), "error": repr(e)[:500]}
Q = {}
Q["total_instances"] = "SELECT (COUNT(DISTINCT ?item) AS ?n) WHERE { ?item wdt:P31/wdt:P279* wd:Q11012 . }"
Q["fictional_instances"] = "SELECT (COUNT(DISTINCT ?item) AS ?n) WHERE { ?item wdt:P31/wdt:P279* wd:Q11012 . ?item wdt:P31/wdt:P279* wd:Q14897293 . }"
Q["enwiki_instances"] = "SELECT (COUNT(DISTINCT ?item) AS ?n) WHERE { ?item wdt:P31/wdt:P279* wd:Q11012 . ?a schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> . }"
Q["subclass_with_maker"] = "SELECT (COUNT(DISTINCT ?item) AS ?n) WHERE { ?item wdt:P279+ wd:Q11012 . ?item wdt:P176|wdt:P178 ?m . }"
Q["subclass_with_maker_enwiki"] = "SELECT (COUNT(DISTINCT ?item) AS ?n) WHERE { ?item wdt:P279+ wd:Q11012 . ?item wdt:P176|wdt:P178 ?m . ?a schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> . }"
Q["classes"] = """SELECT ?cls ?clsLabel (COUNT(DISTINCT ?item) AS ?n) WHERE {
  ?item wdt:P31 ?cls . ?cls wdt:P279* wd:Q11012 .
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
} GROUP BY ?cls ?clsLabel ORDER BY DESC(?n) LIMIT 400"""
Q["known"] = """SELECT ?item ?itemLabel ?itemDescription ?p31 ?p31Label ?under WHERE {
  VALUES ?name { "ASIMO"@en "Spot"@en "Curiosity"@en "Roomba"@en "Atlas"@en "Pepper"@en "Optimus"@en "da Vinci Surgical System"@en "Canadarm2"@en "Unimate"@en "KUKA LBR iiwa"@en "Sojourner"@en "Digit"@en "Ameca"@en "Sophia"@en "BigDog"@en "Shakey the robot"@en "Kiva Systems"@en "Starship Technologies"@en "Perseverance"@en "Unitree Go2"@en "Unitree G1"@en "Nao"@en "Aibo"@en "Cassie"@en "Baxter"@en "Valkyrie"@en "Robonaut"@en "Yutu"@en "Lunokhod 1"@en "Zhurong"@en }
  ?item rdfs:label ?name .
  OPTIONAL { ?item wdt:P31 ?p31 }
  BIND(EXISTS { ?item (wdt:P31|wdt:P279)/wdt:P279* wd:Q11012 } AS ?under)
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}"""
res = {}
for k, q in Q.items():
    res[k] = sparql(q); time.sleep(2)
    print(k, res[k]["ok"], res[k]["secs"], len(res[k].get("rows", [])), file=sys.stderr)
# yc-oss reachability
for u in ["https://yc-oss.github.io/api/meta.json", "https://yc-oss.github.io/api/tags/robotics.json", "https://en.wikipedia.org/api/rest_v1/page/summary/ASIMO"]:
    try:
        req = urllib.request.Request(u, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as r:
            body = r.read()
        res[u] = {"ok": True, "bytes": len(body), "head": body[:400].decode("utf-8", "replace")}
    except Exception as e:
        res[u] = {"ok": False, "error": repr(e)[:300]}
os.makedirs("probe-out", exist_ok=True)
json.dump(res, open("probe-out/result.json", "w"), indent=1)
