"""Pick real building locations from OpenStreetMap for the rd_fusion.html twin, so every dot sits on a real building.

For each sub-area (Cork, Inis Mor, Inis Meain, Inis Oirr, Athlone, Dublin, Sligo, Donegal) it asks the
Overpass API (one query per sub-area, 8 in total) for residential buildings and commercial places (shops,
schools, offices, pubs, hotels ...), keeps a spread-out random sample (fixed seed, at least MIN_GAP m apart)
and writes them into rd_fusion.html (replacing the SITES placeholder) and to sites.json.

The energy data stays synthetic: the page states that positions are real OSM buildings picked at random and
the values do not come from them. No addresses or names are kept, only coordinates and a coarse kind.

Usage (anywhere with internet, e.g. the EC2 instance):
    python3 fetch_osm_sites.py --html rd_fusion.html --out sites.json
Needs only the Python standard library. Data (c) OpenStreetMap contributors, ODbL.
"""
from __future__ import annotations
import argparse, json, math, random, re, sys, time, urllib.parse, urllib.request

OVERPASS = ["https://overpass-api.de/api/interpreter", "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
            "https://overpass.private.coffee/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]
# sub-area id: (lat, lon, radius m, residential needed, commercial needed). Counts are a generous upper bound.
SUBS = {
    "CRK":     (51.8985, -8.4756, 2000, 60, 15),
    "ARN-MOR": (53.1100, -9.6900, 5000, 40, 10),
    "ARN-MEA": (53.0890, -9.5900, 2500, 15, 6),
    "ARN-OIR": (53.0640, -9.5200, 2000, 15, 6),
    "MID":     (53.4239, -7.9407, 2500, 60, 15),
    "DUB":     (53.3498, -6.2603, 1800, 60, 15),
    "NTH-SLI": (54.2697, -8.4694, 2000, 35, 10),
    "NTH-DON": (54.6538, -8.1096, 1500, 35, 10),
}
MIN_GAP = 45   # metres between chosen sites
RES = {"house", "detached", "semidetached_house", "terrace", "residential", "bungalow", "apartments", "farm", "cabin", "semi"}
COM_B = {"commercial", "retail", "office", "supermarket", "school", "college", "hotel", "industrial", "warehouse", "public", "kindergarten", "civic", "university", "hospital"}
COM_A = {"school", "college", "library", "community_centre", "townhall", "pub", "restaurant", "cafe", "pharmacy", "clinic", "doctors",
         "post_office", "fire_station", "police", "bank", "fast_food", "bar", "kindergarten", "dentist", "veterinary", "fuel"}


def query(lat, lon, r):
    q = f"""[out:json][timeout:60][maxsize:67108864];
way["building"~"^(house|detached|semidetached_house|terrace|residential|bungalow|apartments|farm|cabin|semi|yes)$"](around:{r},{lat},{lon})->.r;
.r out center tags 2500;
(
  nwr["shop"](around:{r},{lat},{lon});
  nwr["amenity"~"^({'|'.join(sorted(COM_A))})$"](around:{r},{lat},{lon});
  nwr["office"](around:{r},{lat},{lon});
  nwr["tourism"~"^(hotel|guest_house|hostel)$"](around:{r},{lat},{lon});
  way["building"~"^({'|'.join(sorted(COM_B))})$"](around:{r},{lat},{lon});
)->.c;
.c out center tags 800;"""
    data = urllib.parse.urlencode({"data": q}).encode()
    for attempt in range(8):
        url = OVERPASS[attempt % len(OVERPASS)]
        try:
            req = urllib.request.Request(url, data=data, headers={"User-Agent": "rd-fusion-twin/0.1 (UCC Tyndall EIG research)"})
            with urllib.request.urlopen(req, timeout=120) as f:
                return json.load(f)["elements"]
        except Exception as e:
            print(f"  {url}: {e}; retrying", file=sys.stderr); time.sleep(8)
    sys.exit("Overpass not reachable")


def classify(el):
    t = el.get("tags", {})
    b = t.get("building", "")
    if t.get("shop") or t.get("office") or t.get("amenity") in COM_A or t.get("tourism") or b in COM_B:
        return "C", (t.get("amenity") or ("shop" if t.get("shop") else None) or ("office" if t.get("office") else None) or t.get("tourism") or b)
    if b in RES:
        return "R", b
    if b == "yes":
        return "Y", "building"
    return None, None


def metres(a, b):
    dy = (a[0] - b[0]) * 111200; dx = (a[1] - b[1]) * 111320 * math.cos(math.radians(a[0]))
    return math.hypot(dx, dy)


def pick(points, n, rng):
    rng.shuffle(points); out = []
    for p in points:
        if all(metres(p, q) >= MIN_GAP for q in out):
            out.append(p)
            if len(out) >= n: break
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", help="rd_fusion.html to patch in place")
    ap.add_argument("--out", default="sites.json")
    ap.add_argument("--seed", type=int, default=20260716)
    ap.add_argument("--sites", help="reuse an existing sites.json instead of querying OpenStreetMap")
    a = ap.parse_args()
    rng = random.Random(a.seed)
    sites = {"source": "OpenStreetMap contributors (ODbL), via Overpass API", "created": time.strftime("%Y-%m-%d"),
             "note": "Real building positions picked at random; RD-Fusion values shown at them are synthetic.", "subs": {}}
    if a.sites:
        sites = json.load(open(a.sites)); print(f"using {a.sites}")
    for sid, (lat, lon, r, nr, nc) in ({} if a.sites else SUBS).items():
        els = query(lat, lon, r)
        pools = {"R": [], "C": [], "Y": []}
        for el in els:
            c = el.get("center") or ({"lat": el["lat"], "lon": el["lon"]} if "lat" in el else None)
            k, kind = classify(el)
            if c and k: pools[k].append([round(c["lat"], 6), round(c["lon"], 6), kind])
        res = pick(pools["R"], nr, rng)
        if len(res) < nr: res += pick([p for p in pools["Y"] if all(metres(p, q) >= MIN_GAP for q in res)], nr - len(res), rng)
        com = pick(pools["C"], nc, rng)
        sites["subs"][sid] = {"R": res, "C": com}
        print(f"{sid}: {len(els)} OSM objects -> {len(res)} residential, {len(com)} commercial", flush=True)
        time.sleep(3)
    if not a.sites:
      with open(a.out, "w") as f: json.dump(sites, f, separators=(",", ":"))
    if a.html:
        s = open(a.html, encoding="utf-8").read()
        new, n = re.subn(r"const SITES = .*?; /\*@@SITES@@\*/", lambda m: "const SITES = " + json.dumps(sites, separators=(",", ":")) + "; /*@@SITES@@*/", s, count=1, flags=re.S)
        if not n: sys.exit("SITES placeholder not found in html")
        open(a.html, "w", encoding="utf-8").write(new)
        print(f"patched {a.html}")
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
