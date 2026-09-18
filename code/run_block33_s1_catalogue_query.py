#!/usr/bin/env python3
"""Block 33a - query dell'archivio Sentinel-1 IW SLC su Duck (FRF, NC).

Solo metadati di catalogo. Nessun download di prodotti.

## Obiettivo, che NON e' quello dei blocchi 30-32

Qui Sentinel-1 non e' un candidato per misurare omega: con 0.165 s di dwell per
bersaglio in TOPS la rotazione di fase vale ~4 gradi a T = 10 s, e il valore non
si tira fuori. Serve a **validare la parte spaziale** della catena: stimare il
numero d'onda k localmente dallo spettro d'immagine, prendere omega dalla boa
FRF invece che dalla fase, invertire omega^2 = g k tanh(kh) e confrontare la
profondita' con i rilievi FRF.

Conseguenza sui criteri: **il gate sulla fase sparisce**. Non contano dwell,
Delta phi, avvolgimento. Contano la visibilita' dell'onda nell'immagine, il
cut-off azimutale, la risoluzione spettrale su k e la banda di profondita'.

## Il catalogo

Copernicus Data Space Ecosystem, aperto e senza autenticazione per la RICERCA
(il download richiede credenziali). Due API equivalenti:

  OData      https://catalogue.dataspace.copernicus.eu/odata/v1/Products
  OpenSearch https://catalogue.dataspace.copernicus.eu/resto/api/collections/Sentinel1/search.json

Dal container di sessione entrambe sono bloccate dal proxy: lo script e'
scritto per girare in locale e **non e' stato eseguito contro il servizio
reale**. Per questo il primo passo e' `--probe`, che stampa i nomi dei campi
osservati invece di assumerli: e' la lezione dei metadati EOWEB, dove
`sensorResolution` non era quello che sembrava.

Uso:
  python code/run_block33_s1_catalogue_query.py --probe
  python code/run_block33_s1_catalogue_query.py --search
  python code/run_block33_s1_catalogue_query.py --search --from 2020-09-01 --to 2020-09-15
"""
from __future__ import annotations
import argparse, collections, csv, json, math, re, urllib.error, urllib.parse, urllib.request
from datetime import datetime
from pathlib import Path

ODATA = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
RESTO = "https://catalogue.dataspace.copernicus.eu/resto/api/collections/Sentinel1/search.json"
OUTDIR = Path("Block33_s1_duck_query")

PIER = (36.1836, -75.7461)
SHORE = (36.1836, -75.7497)
OFFSHORE_DEG = 70.0                 # ASSUNTO: asse cross-shore FRF
WR_17M = (36.200, -75.714)
WR_26M = (36.257, -75.593)
R_EARTH_M = 6371008.8

# Sentinel-1: incidenze nominali per sotto-banda IW. ASSUNTE, servono solo a
# stimare beta = R/V per il cut-off; l'incidenza vera va letta nell'annotazione.
IW_INCIDENCE = {"IW1": (29.1, 36.0), "IW2": (34.8, 41.1), "IW3": (40.0, 46.0)}
S1_ALT_KM = 693.0
RE_KM = 6371.0
V_SAT_KMS = 7.512

_spent = {"n": 0, "b": 0}
MAX_REQ, MAX_BYTES = 60, 40 * 1024 * 1024


def get(url: str):
    if _spent["n"] >= MAX_REQ:
        raise RuntimeError("budget richieste esaurito")
    req = urllib.request.Request(url, headers={
        "Accept": "application/json", "User-Agent": "polimi-thesis-block33"})
    with urllib.request.urlopen(req, timeout=120) as r:
        raw = r.read(MAX_BYTES - _spent["b"] + 1)
    _spent["n"] += 1
    _spent["b"] += len(raw)
    if _spent["b"] > MAX_BYTES:
        raise RuntimeError("budget byte esaurito")
    return json.loads(raw.decode("utf-8", "replace"))


def odata_url(t0: str, t1: str, top: int = 200, skip: int = 0) -> str:
    f = (f"Collection/Name eq 'SENTINEL-1' and contains(Name,'IW_SLC') "
         f"and OData.CSC.Intersects(area=geography'SRID=4326;"
         f"POINT({PIER[1]} {PIER[0]})') "
         f"and ContentDate/Start gt {t0}T00:00:00.000Z "
         f"and ContentDate/Start lt {t1}T00:00:00.000Z")
    q = {"$filter": f, "$expand": "Attributes", "$top": str(top),
         "$skip": str(skip), "$orderby": "ContentDate/Start asc"}
    return ODATA + "?" + urllib.parse.urlencode(q)


def resto_url(t0: str, t1: str, n: int = 200) -> str:
    q = {"productType": "IW_SLC", "startDate": f"{t0}T00:00:00Z",
         "completionDate": f"{t1}T00:00:00Z", "lon": str(PIER[1]),
         "lat": str(PIER[0]), "maxRecords": str(n), "sortParam": "startDate"}
    return RESTO + "?" + urllib.parse.urlencode(q)


def ll2xy(lat, lon, lat0, lon0):
    return (math.radians(lon - lon0) * R_EARTH_M * math.cos(math.radians(lat0)),
            math.radians(lat - lat0) * R_EARTH_M)


def bearing(dx, dy):
    return math.degrees(math.atan2(dx, dy)) % 360.0


def d180(a, b):
    return min(abs((a - b) % 180.0), 180.0 - abs((a - b) % 180.0))


def in_polygon(pt, poly):
    x, y = pt; n = len(poly); inside = False; j = n - 1
    for i in range(n):
        xi, yi = poly[i]; xj, yj = poly[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def slant_range_km(inc_deg):
    th = math.radians(inc_deg)
    look = math.asin(RE_KM / (RE_KM + S1_ALT_KM) * math.sin(th))
    return RE_KM * math.sin(th - look) / math.sin(look)


def parse_wkt_polygon(wkt: str):
    m = re.search(r"\(\(([^)]*)\)\)", wkt or "")
    if not m:
        return []
    pts = []
    for tok in m.group(1).split(","):
        p = tok.split()
        if len(p) >= 2:
            pts.append((float(p[1]), float(p[0])))   # (lat, lon)
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    return pts


def attrs_of(entry: dict) -> dict:
    out = {}
    for a in entry.get("Attributes", []) or []:
        if "Name" in a:
            out[a["Name"]] = a.get("Value")
    return out


def derive(name, t_start, ring, node, rel_orbit, pol, pid):
    lat0 = sum(a for a, _ in ring) / len(ring)
    lon0 = sum(b for _, b in ring) / len(ring)
    xy = [ll2xy(a, b, lat0, lon0) for a, b in ring]
    edges = []
    for i in range(len(xy)):
        x1, y1 = xy[i]; x2, y2 = xy[(i + 1) % len(xy)]
        edges.append((math.hypot(x2 - x1, y2 - y1), bearing(x2 - x1, y2 - y1)))
    nominal = 193.0 if (node or "").upper().startswith("DESC") else 347.0
    head = min(edges, key=lambda e: d180(e[1], nominal))[1]
    if abs(((head - nominal + 180) % 360) - 180) >= 90:
        head = (head + 180.0) % 360.0
    rng = (head + 90.0) % 360.0

    poly_lonlat = [(b, a) for a, b in ring]
    cs = []
    for a, b in ring:
        x, y = ll2xy(a, b, *SHORE)
        cs.append((x * math.sin(math.radians(OFFSHORE_DEG))
                   + y * math.cos(math.radians(OFFSHORE_DEG))) / 1000.0)
    # incidenza a Duck: interpolata sulla posizione cross-track nell'impronta.
    # APPROSSIMATA: l'incidenza vera va letta nell'annotazione del prodotto.
    inc = 38.0
    r_km = slant_range_km(inc)
    row = {
        "acq_utc": t_start[:19].replace("T", " "),
        "product_id": pid, "product_name": name,
        "node": (node or "").upper(), "rel_orbit": rel_orbit, "pol": pol,
        "inc_deg_APPROSSIMATA": inc,
        "slant_km": round(r_km, 1),
        "beta_s": round(r_km * 1e3 / (V_SAT_KMS * 1e3), 1),
        "heading_deg": round(head, 1), "range_dir_deg": round(rng, 1),
        "offshore_extent_km": round(max(cs), 2),
        "onshore_extent_km": round(min(cs), 2),
        "pier_in": in_polygon((PIER[1], PIER[0]), poly_lonlat),
        "wr17m_in": in_polygon((WR_17M[1], WR_17M[0]), poly_lonlat),
        "wr26m_in": in_polygon((WR_26M[1], WR_26M[0]), poly_lonlat),
        "centre_lat": round(lat0, 5), "centre_lon": round(lon0, 5),
    }
    return row


def cmd_probe(t0, t1):
    print(f"probe OData su {t0} .. {t1}\n")
    try:
        d = get(odata_url(t0, t1, top=3))
    except urllib.error.HTTPError as e:
        print(f"OData HTTP {e.code}: {e.read()[:400]!r}")
        d = None
    except urllib.error.URLError as e:
        print(f"OData non raggiungibile: {e.reason}")
        d = None
    if d:
        vals = d.get("value", [])
        print(f"{len(vals)} elementi. Campi di primo livello del primo:")
        if vals:
            for k, v in vals[0].items():
                if k == "Attributes":
                    continue
                print(f"  {k:28s} {str(v)[:90]}")
            print("\n  Attributes:")
            for k, v in attrs_of(vals[0]).items():
                print(f"    {k:26s} {str(v)[:70]}")
    print("\nprobe OpenSearch/resto")
    try:
        d2 = get(resto_url(t0, t1, n=3))
        feats = d2.get("features", [])
        print(f"{len(feats)} elementi. Proprieta' del primo:")
        if feats:
            for k, v in (feats[0].get("properties") or {}).items():
                print(f"  {k:28s} {str(v)[:80]}")
    except Exception as e:
        print(f"  non riuscito: {e}")
    print(f"\nrichieste {_spent['n']}, byte {_spent['b']/1e6:.2f} MB")
    print("\nControlla qui sopra i nomi VERI dei campi di nodo d'orbita,")
    print("orbita relativa e polarizzazione, poi adegua estrarre() se serve.")
    return 0


def cmd_search(t0, t1, api):
    OUTDIR.mkdir(parents=True, exist_ok=True)
    rows, raw = [], []
    if api == "odata":
        skip = 0
        while True:
            d = get(odata_url(t0, t1, top=200, skip=skip))
            vals = d.get("value", [])
            raw.extend(vals)
            if len(vals) < 200:
                break
            skip += 200
        for e in raw:
            a = attrs_of(e)
            ring = parse_wkt_polygon(e.get("Footprint", ""))
            if not ring:
                continue
            rows.append(derive(e.get("Name", ""),
                               (e.get("ContentDate") or {}).get("Start", ""),
                               ring, a.get("orbitDirection"),
                               a.get("relativeOrbitNumber"), a.get("polarisationChannels"),
                               e.get("Id", "")))
    else:
        d = get(resto_url(t0, t1, n=500))
        raw = d.get("features", [])
        for f in raw:
            p = f.get("properties") or {}
            g = f.get("geometry") or {}
            coords = (g.get("coordinates") or [[]])[0]
            ring = [(c[1], c[0]) for c in coords]
            if len(ring) > 1 and ring[0] == ring[-1]:
                ring = ring[:-1]
            if not ring:
                continue
            rows.append(derive(p.get("title", ""), p.get("startDate", ""), ring,
                               p.get("orbitDirection"), p.get("relativeOrbitNumber"),
                               p.get("polarisation"), f.get("id", "")))

    (OUTDIR / "BLOCK33_S1_RAW.json").write_text(json.dumps(raw, indent=1), encoding="utf-8")
    rows.sort(key=lambda r: r["acq_utc"])
    out = OUTDIR / "BLOCK33_S1_DUCK_SCENES.csv"
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print(f"{len(rows)} scene -> {out}")
    c = collections.Counter(r["node"] for r in rows)
    print(f"  nodi: {dict(c)}")
    print(f"  orbite relative: {sorted({r['rel_orbit'] for r in rows})}")
    print(f"  direzione di range: {sorted({r['range_dir_deg'] for r in rows})}")
    print(f"  con molo nell'impronta: {sum(r['pier_in'] for r in rows)}")
    print(f"richieste {_spent['n']}, byte {_spent['b']/1e6:.1f} MB")
    print("\nProssimo passo: run_block30_frf_conditions.py su questo CSV,")
    print("poi run_block33_spatial_gate.py per la classifica.")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--search", action="store_true")
    ap.add_argument("--api", choices=("odata", "resto"), default="odata")
    ap.add_argument("--from", dest="t0", default="2016-01-01")
    ap.add_argument("--to", dest="t1", default=datetime.utcnow().strftime("%Y-%m-%d"))
    a = ap.parse_args(argv)
    if a.probe:
        return cmd_probe(a.t0, a.t1)
    if a.search:
        return cmd_search(a.t0, a.t1, a.api)
    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
