#!/usr/bin/env python3
"""Block 31 - interrogazione via API del catalogo TerraSAR-X su Duck (FRF, NC).

Solo metadati di catalogo. Nessun download di prodotti SAR.

## Quale endpoint, e perche' NON EO-CAT

EO-CAT (`eocat.esa.int`) espone una STAC API pubblica, ma il TCP connect va in
timeout sia dalla rete dell'utente sia da una rete indipendente: da entrambe,
`WinError 10060` / ConnectTimeout. Non e' un problema di certificati o di
proxy, e' che l'host non accetta la connessione. **Scartato per irraggiungibilita'.**

**FedEO** (`fedeo.ceos.org`, clearinghouse CEOS/ESA, OGC API Features) risponde
e non richiede autenticazione in lettura. E' l'endpoint usato qui.

## Il vantaggio decisivo di FedEO per noi

FedEO indicizza l'archivio DLR EOWEB con **una collezione separata per ciascun
modo spotlight**. Non serve indovinare il nome di un campo `productType` ne' i
suoi valori: si interroga direttamente la collezione del modo giusto.

  Staring Spotlight (ST, 0.24 m)  bb9fdc41-1a19-4793-aca1-a6f5f28d592d
  High Res Spotlight (HS, 1.0 m)  aae157df-5b91-4a49-b00b-d81729a566d7
  Spotlight (SL, 2.0 m)           fa8dc12c-b6c5-4ff4-9781-a39c8775d4fa
  StripMap                        53554204-282b-457e-b36d-a168679a0c1f
  archivio completo ESA TPM       TerraSAR-X_TanDEM-X.full.archive.and.tasking

Solo lo **Staring Spotlight** ha dwell sufficiente (~5-6 s, Delta phi 117-140 deg
a T = 10 s). HS sta a 28-34 deg, SL a 14-17 deg: sotto la soglia di progetto.

## Avvertenze da non dimenticare

- Al 2026-09-17 l'endpoint `/items` della collezione Staring Spotlight
  restituisce **HTTP 500**. La collezione esiste e il suo descrittore si legge,
  ma la ricerca degli elementi e' rotta lato server. **Un esito vuoto o un 500
  NON dimostrano che non esistano acquisizioni**: vanno verificati su EOWEB.
- L'intervallo temporale degli elementi (1.1-1.5 s per SL e HS) **non e'
  interpretabile ne' come dwell per bersaglio ne' come data take senza
  l'annotazione del prodotto**: SL a 2 m ha intervallo piu' lungo di HS a 1 m,
  cioe' l'opposto di quanto ci si aspetterebbe da un dwell. Il dwell va
  ricavato dalla risoluzione azimutale del modo, non da questo campo.
- Gli identificativi terminano in `TSX-1.SAR.L0`: e' il livello **grezzo** a
  essere catalogato. E' la notizia migliore, perche' col grezzo la partizione
  in sotto-aperture la controlliamo noi.

Uso:
  python code/run_block31_tsx_catalogue_query.py --duck
  python code/run_block31_tsx_catalogue_query.py --collections TerraSAR-X
  python code/run_block31_tsx_catalogue_query.py --items <ID> [--bbox ...] [--datetime ...]
"""
from __future__ import annotations
import argparse, collections, json, urllib.error, urllib.parse, urllib.request
from pathlib import Path

BASE = "https://fedeo.ceos.org"
OUTDIR = Path('duck_frf/Block31_tsx_duck_query')
BBOX = "-75.90,36.08,-75.55,36.30"     # molo FRF 36.1836 N, 75.7461 W
DATETIME = None                         # tutto l'archivio

TSX_MODES = [
    ("StaringSpotlight",       "bb9fdc41-1a19-4793-aca1-a6f5f28d592d", 0.24),
    ("HighResolutionSpotlight", "aae157df-5b91-4a49-b00b-d81729a566d7", 1.00),
    ("Spotlight",              "fa8dc12c-b6c5-4ff4-9781-a39c8775d4fa", 2.00),
    ("StripMap",               "53554204-282b-457e-b36d-a168679a0c1f", 3.00),
]

_spent = {"n": 0, "b": 0}
MAX_REQ, MAX_BYTES, MAX_PAGES = 80, 40 * 1024 * 1024, 20


def get(url: str, accept: str = "application/json"):
    if _spent["n"] >= MAX_REQ:
        raise RuntimeError("budget richieste esaurito")
    req = urllib.request.Request(url, headers={
        "Accept": accept, "User-Agent": "polimi-thesis-block31"})
    with urllib.request.urlopen(req, timeout=120) as r:
        raw = r.read(MAX_BYTES - _spent["b"] + 1)
    _spent["n"] += 1
    _spent["b"] += len(raw)
    if _spent["b"] > MAX_BYTES:
        raise RuntimeError("budget byte esaurito")
    return json.loads(raw.decode("utf-8", "replace"))


def items_url(coll: str, bbox: str | None, dt: str | None, limit: int = 50) -> str:
    q = [f"limit={limit}", "httpAccept=" + urllib.parse.quote("application/geo+json")]
    if bbox:
        q.append("bbox=" + bbox)
    if dt:
        q.append("datetime=" + urllib.parse.quote(dt))
    return f"{BASE}/collections/{urllib.parse.quote(coll)}/items?" + "&".join(q)


def fetch_items(coll: str, bbox: str | None, dt: str | None):
    """Ritorna (features, nota). nota != None quando la ricerca non e' andata."""
    url, feats, page = items_url(coll, bbox, dt), [], 0
    while url and page < MAX_PAGES:
        try:
            data = get(url, accept="application/geo+json")
        except urllib.error.HTTPError as e:
            return feats, f"HTTP {e.code} dall'endpoint /items"
        except urllib.error.URLError as e:
            return feats, f"rete non raggiungibile: {e.reason}"
        feats.extend(data.get("features", []))
        matched = data.get("numberMatched")
        url = next((l["href"] for l in data.get("links", [])
                    if l.get("rel") == "next"), None)
        page += 1
        if matched is not None and len(feats) >= matched:
            break
    return feats, None


def summarise(feats):
    counts: dict[str, collections.Counter] = {}
    for f in feats:
        for k, v in (f.get("properties") or {}).items():
            if isinstance(v, (str, int, float, bool)) or v is None:
                counts.setdefault(k, collections.Counter())[str(v)] += 1
    return counts


def cmd_duck(bbox, dt):
    OUTDIR.mkdir(parents=True, exist_ok=True)
    print(f"FedEO {BASE}\nbbox {bbox}  datetime {dt or 'tutto l archivio'}\n")
    summary = []
    for name, coll, d_az in TSX_MODES:
        feats, note = fetch_items(coll, bbox, dt)
        out = OUTDIR / f"BLOCK31_TSX_{name}_duck.geojson"
        out.write_text(json.dumps(
            {"type": "FeatureCollection", "features": feats}, indent=1), encoding="utf-8")
        state = note or f"{len(feats)} elementi"
        print(f"{name:26s} delta_az={d_az:4.2f} m   {state}   -> {out.name}")
        for f in feats:
            p = f.get("properties") or {}
            when = p.get("datetime") or p.get("date") or p.get("start_datetime") or "?"
            print(f"    {when}   {f.get('id')}")
        summary.append({"mode": name, "collection": coll, "delta_az_m": d_az,
                        "n_items": len(feats), "note": note})
    (OUTDIR / "BLOCK31_SUMMARY.json").write_text(
        json.dumps({"base": BASE, "bbox": bbox, "datetime": dt,
                    "modes": summary}, indent=1), encoding="utf-8")
    print(f"\nrichieste {_spent['n']}, byte {_spent['b']/1e6:.1f} MB")
    print("\nATTENZIONE: un conteggio zero o un HTTP 500 NON dimostrano assenza")
    print("di acquisizioni. L'archivio autoritativo e' EOWEB (eoweb.dlr.de/egp).")
    return 0


def cmd_collections(q: str):
    data = get(f"{BASE}/collections?q={urllib.parse.quote(q)}&limit=50")
    cols = data.get("collections", [])
    print(f"{data.get('numberMatched', len(cols))} collezioni per q={q!r}\n")
    for c in cols:
        print(f"  {c.get('id')}\n      {c.get('title')}")
    return 0


def cmd_items(coll, bbox, dt):
    OUTDIR.mkdir(parents=True, exist_ok=True)
    feats, note = fetch_items(coll, bbox, dt)
    if note:
        print(f"ricerca non riuscita: {note}")
    out = OUTDIR / f"BLOCK31_{coll.replace('/', '_')[:60]}_duck.geojson"
    out.write_text(json.dumps(
        {"type": "FeatureCollection", "features": feats}, indent=1), encoding="utf-8")
    print(f"{len(feats)} elementi -> {out}")
    if feats:
        print("\nproprieta' osservate (distinti, 6 piu' frequenti):\n")
        for k, c in sorted(summarise(feats).items()):
            print(f"  {k:34s} {len(c):4d}   " +
                  ", ".join(f"{v}x{n}" for v, n in c.most_common(6)))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--duck", action="store_true",
                    help="interroga tutti i modi TSX sull'area di Duck")
    ap.add_argument("--collections", metavar="TESTO")
    ap.add_argument("--items", metavar="ID_COLLEZIONE")
    ap.add_argument("--bbox", default=BBOX)
    ap.add_argument("--datetime", default=DATETIME)
    a = ap.parse_args(argv)
    if a.duck:
        return cmd_duck(a.bbox, a.datetime)
    if a.collections:
        return cmd_collections(a.collections)
    if a.items:
        return cmd_items(a.items, a.bbox, a.datetime)
    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
