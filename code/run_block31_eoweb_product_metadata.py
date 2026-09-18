#!/usr/bin/env python3
"""Block 31 - metadati di prodotto EOWEB delle acquisizioni TerraSAR-X su Duck.

Legge le pagine "product detail" di EOWEB incollate in file di testo e produce
una tabella con i campi osservati piu' le grandezze derivate. Nessun download
di prodotti SAR.

## ATTENZIONE: `sensorResolution` NON e' la risoluzione azimutale

I valori osservati su venti prodotti sono:

    SL  ->  1.7 m        HS  ->  1.1 m        ST  ->  1.1 m

Se fosse la risoluzione azimutale, lo Staring Spotlight (0.24 m nominali) non
potrebbe valere quanto l'High Resolution Spotlight. **E' la risoluzione in
range obliquo**, fissata dalla banda del chirp:

    delta_r = 1.18 * c / (2*B)   con finestra di pesatura
    B = 100 MHz -> 1.77 m   (modo SL)
    B = 150 MHz -> 1.18 m   (modi HS e ST)

Torna entro il 7% su entrambi i valori. Le due bande di chirp del TerraSAR-X
sono appunto 100 e 150 MHz.

**Conseguenza operativa**: `sensorResolution` non dice nulla sul dwell. Il
`T_dwell` qui si calcola dalla risoluzione AZIMUTALE NOMINALE del modo, non da
questo campo, e resta da confermare sull'annotazione del prodotto ordinato.
Il campo e' comunque riportato in tabella come `slant_range_res_m`, perche'
fissa il campionamento in range: a 1.1 m un'onda di 84 m in range e' campionata
con 76 punti per lunghezza d'onda.

## Cosa e' osservato e cosa e' calcolato

OSSERVATO dai metadati:
  tempi, modo, fascio, nodo, orbita, incidenze, polarizzazione,
  `sensorResolution`, `processingLevel`, `dopplerFrequency`, poligono,
  qualita' e disponibilita'.

CALCOLATO qui:
  slant range dall'incidenza e dalla quota orbitale;
  beta = R/V, che entra nel cut-off azimutale;
  T_dwell dalla risoluzione azimutale DI PRODOTTO;
  T_base = 0.65*T_dwell, limite aggressivo della separazione fra sub-look;
  dphi = omega*T_base per periodi d'onda di riferimento;
  estensione azimutale della scena = (stopTime - startTime) * velocita' al suolo
    -- convenzione EOWEB verificata su tre modi contro le specifiche nominali;
  heading dal poligono, direzione di range = heading + 90 (right-looking);
  estensioni cross-shore, appartenenza di molo e boe all'impronta.

ASSUNTO, da confermare:
  asse cross-shore FRF a 70 degT, stimato dai bearing molo->boe.
  Quota orbitale 514.8 km per TSX-1 e TDX-1.

NON applicato: il fattore di allargamento della finestra di pesatura. Se la
risoluzione dichiarata e' la larghezza a -3 dB con finestra, il dwell reale e'
maggiore e i dphi qui sono un LIMITE INFERIORE.

Uso:
  python code/run_block31_eoweb_product_metadata.py \
      Block31_tsx_duck_query/eoweb_products/*.txt Block31_tsx_duck_query
"""
from __future__ import annotations
import csv, math, re, sys
from datetime import datetime
from pathlib import Path

R_EARTH_M = 6371008.8
RE_KM = 6371.0
TSX_ALT_KM = 514.8              # TSX-1 e TDX-1
TSX_LAMBDA_M = 3e8 / 9.65e9     # banda X, 9.65 GHz
V_SAT_KMS = 7.6
V_GROUND_KMS = V_SAT_KMS * RE_KM / (RE_KM + TSX_ALT_KM)
LOOK_FRACTION = 0.65
REF_PERIODS_S = (8.0, 10.0, 12.0)

# Risoluzione AZIMUTALE nominale per modo. NON viene da `sensorResolution`,
# che e' la risoluzione in range obliquo (vedi docstring).
DELTA_AZ_NOMINAL_M = {"ST": 0.24, "HS": 1.10, "SL": 2.00}

PIER = (36.1836, -75.7461)
SHORE = (36.1836, -75.7497)
OFFSHORE_DEG = 70.0             # ASSUNTO
WR_17M = (36.200, -75.714)      # NDBC 44056
WR_26M = (36.257, -75.593)      # NDBC 44100 / CDIP 430

KEYS = [
    "startTime", "stopTime", "status", "orbitDuration", "processorName",
    "dopplerFrequency", "acquisitionType", "acquisitionStation", "acquisitionDate",
    "orbitNumber", "orbitDirection", "incidenceAngle", "processingLevel",
    "antennaLookDirection", "maximumIncidenceAngle", "minimumIncidenceAngle",
    "polarisationChannels", "polarisationMode", "archivingDate", "sensorResolution",
    "instrumentShortName", "platformSerialIdentifier", "sensorOperationalMode",
    "swathIdentifier", "DatatakeFileNumber", "AntennaReceiveConfiguration",
    "UniqueDataTakeID", "OrbitPhase", "OrbitCycle", "OrbitsRepeatCycle",
    "IOP", "GOP", "Availability", "Revision", "Quality", "CreationSite", "RelOrbit",
]
ID_RE = re.compile(r"^TSX-1\.SAR\.L1b-\S*:/dims_")


def parse_records(text: str):
    lines = [ln.rstrip() for ln in text.splitlines()]
    starts = [i for i, ln in enumerate(lines) if ID_RE.match(ln.strip())]
    for n, i0 in enumerate(starts):
        i1 = starts[n + 1] if n + 1 < len(starts) else len(lines)
        block = lines[i0:i1]
        rec = {"eoweb_id": block[0].strip()}
        j = 1
        while j < len(block):
            key = block[j].strip()
            if key == "Polygon" and j + 1 < len(block):
                rec["polygon"] = block[j + 1].strip()
                j += 2
                continue
            if key in KEYS and j + 1 < len(block):
                rec[key] = block[j + 1].strip()
                j += 2
                continue
            j += 1
        yield rec


def polygon_points(s: str):
    pts = re.findall(r"\(\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*\)", s)
    ll = [(float(a), float(b)) for a, b in pts]
    if len(ll) > 1 and ll[0] == ll[-1]:
        ll = ll[:-1]
    return ll


def ll2xy(lat, lon, lat0, lon0):
    return (math.radians(lon - lon0) * R_EARTH_M * math.cos(math.radians(lat0)),
            math.radians(lat - lat0) * R_EARTH_M)


def bearing(dx, dy):
    return math.degrees(math.atan2(dx, dy)) % 360.0


def d180(a, b):
    return min(abs((a - b) % 180.0), 180.0 - abs((a - b) % 180.0))


def in_polygon(pt, poly):
    x, y = pt
    n = len(poly); inside = False; j = n - 1
    for i in range(n):
        xi, yi = poly[i]; xj, yj = poly[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def slant_range_km(incidence_deg):
    th = math.radians(incidence_deg)
    look = math.asin(RE_KM / (RE_KM + TSX_ALT_KM) * math.sin(th))
    return RE_KM * math.sin(th - look) / math.sin(look)


def parse_time(s):
    return datetime.strptime(s.replace("Z", "")[:23], "%Y-%m-%dT%H:%M:%S.%f")


def derive(rec):
    out = dict(rec)
    inc = float(rec["incidenceAngle"])
    mode = rec.get("sensorOperationalMode", "")
    if mode not in DELTA_AZ_NOMINAL_M:
        raise RuntimeError(f"modo {mode!r} senza risoluzione azimutale nominale nota")
    d_az = DELTA_AZ_NOMINAL_M[mode]
    r_km = slant_range_km(inc)
    t_dwell = TSX_LAMBDA_M * r_km * 1e3 / (2.0 * d_az * V_SAT_KMS * 1e3)
    t_base = LOOK_FRACTION * t_dwell
    span = (parse_time(rec["stopTime"]) - parse_time(rec["startTime"])).total_seconds()

    ring = polygon_points(rec["polygon"])
    lat0 = sum(a for a, _ in ring) / len(ring)
    lon0 = sum(b for _, b in ring) / len(ring)
    xy = [ll2xy(a, b, lat0, lon0) for a, b in ring]
    edges = []
    for i in range(len(xy)):
        x1, y1 = xy[i]; x2, y2 = xy[(i + 1) % len(xy)]
        edges.append((math.hypot(x2 - x1, y2 - y1), bearing(x2 - x1, y2 - y1)))
    nominal = 190.0 if rec["orbitDirection"] == "DESCENDING" else 350.0
    head = min(edges, key=lambda e: d180(e[1], nominal))[1]
    if abs(((head - nominal + 180) % 360) - 180) >= 90:
        head = (head + 180.0) % 360.0
    poly_lonlat = [(b, a) for a, b in ring]
    cs = []
    for a, b in ring:
        x, y = ll2xy(a, b, *SHORE)
        cs.append((x * math.sin(math.radians(OFFSHORE_DEG))
                   + y * math.cos(math.radians(OFFSHORE_DEG))) / 1000.0)

    m = re.search(r"dims_\w+_dfd_(\w+)/", rec["eoweb_id"])
    out.update({
        "product_id": m.group(1) if m else "",
        "acq_utc": rec["startTime"][:19].replace("T", " "),
        "mode": mode,
        "delta_az_m": d_az,
        "delta_az_source": "nominale del modo (NON sensorResolution)",
        "slant_range_res_m": float(rec["sensorResolution"]),
        "chirp_bw_MHz_inferita": round(1.18 * 3e8 / (2 * float(rec["sensorResolution"])) / 1e6),
        "slant_km": round(r_km, 1),
        "beta_s": round(r_km * 1e3 / (V_SAT_KMS * 1e3), 1),
        "eoweb_span_s": round(span, 3),
        "scene_azimuth_km": round(span * V_GROUND_KMS, 2),
        "T_dwell_s": round(t_dwell, 3),
        "T_base_s": round(t_base, 3),
        "heading_deg": round(head, 1),
        "range_dir_deg": round((head + 90.0) % 360.0, 1),
        "offshore_extent_km": round(max(cs), 2),
        "onshore_extent_km": round(min(cs), 2),
        "footprint_long_km": round(max(e[0] for e in edges) / 1000, 2),
        "footprint_short_km": round(min(e[0] for e in edges) / 1000, 2),
        "sea_area_km2": round(max(max(cs), 0.0) * min(e[0] for e in edges) / 1000, 1),
        "pier_in": in_polygon((PIER[1], PIER[0]), poly_lonlat),
        "wr17m_in": in_polygon((WR_17M[1], WR_17M[0]), poly_lonlat),
        "wr26m_in": in_polygon((WR_26M[1], WR_26M[0]), poly_lonlat),
        "centre_lat": round(lat0, 5),
        "centre_lon": round(lon0, 5),
    })
    for tw in REF_PERIODS_S:
        out[f"dphi_{int(tw)}s_deg"] = round(math.degrees(2 * math.pi / tw * t_base))
    return out


COLS = ["acq_utc", "mode", "product_id", "platformSerialIdentifier", "orbitDirection",
        "swathIdentifier", "polarisationChannels", "polarisationMode",
        "delta_az_m", "delta_az_source", "slant_range_res_m",
        "chirp_bw_MHz_inferita", "sensorResolution", "incidenceAngle", "minimumIncidenceAngle",
        "maximumIncidenceAngle", "slant_km", "beta_s", "T_dwell_s", "T_base_s",
        "dphi_8s_deg", "dphi_10s_deg", "dphi_12s_deg", "eoweb_span_s",
        "scene_azimuth_km", "heading_deg", "range_dir_deg", "offshore_extent_km",
        "onshore_extent_km", "footprint_long_km", "footprint_short_km",
        "sea_area_km2", "pier_in", "wr17m_in", "wr26m_in", "centre_lat", "centre_lon",
        "processingLevel", "dopplerFrequency", "Quality", "Availability", "Revision",
        "orbitNumber", "RelOrbit", "OrbitCycle", "OrbitPhase", "OrbitsRepeatCycle",
        "DatatakeFileNumber", "UniqueDataTakeID", "AntennaReceiveConfiguration",
        "IOP", "GOP", "acquisitionStation", "acquisitionDate", "archivingDate",
        "startTime", "stopTime", "status", "processorName", "acquisitionType",
        "antennaLookDirection", "CreationSite", "eoweb_id", "polygon"]

MODE_ORDER = {"ST": 0, "HS": 1, "SL": 2}


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    outdir = Path(argv[-1]); outdir.mkdir(parents=True, exist_ok=True)
    recs = []
    for p in argv[1:-1]:
        for f in sorted(Path().glob(p)) or [Path(p)]:
            if not f.is_file():
                continue
            recs.extend(parse_records(f.read_text(encoding="utf-8", errors="replace")))
    if not recs:
        print("nessun record trovato", file=sys.stderr)
        return 1
    rows = [derive(r) for r in recs]
    rows.sort(key=lambda r: (MODE_ORDER.get(r["mode"], 9), r["acq_utc"]))
    out = outdir / "BLOCK31_TSX_PRODUCT_METADATA.csv"
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS, extrasaction="ignore")
        w.writeheader(); w.writerows(rows)
    print(f"{len(rows)} prodotti -> {out}")
    seen = {}
    for r in rows:
        seen.setdefault(r["mode"], []).append(r)
    for mode, g in seen.items():
        print(f"  {mode}: {len(g)} scene, delta_az={sorted({x['delta_az_m'] for x in g})}, "
              f"T_dwell {min(x['T_dwell_s'] for x in g):.2f}-{max(x['T_dwell_s'] for x in g):.2f} s, "
              f"dphi@10s {min(x['dphi_10s_deg'] for x in g)}-{max(x['dphi_10s_deg'] for x in g)} deg, "
              f"pol={sorted({x['polarisationChannels'] for x in g})}")
    lv = sorted({r["processingLevel"] for r in rows})
    dc = sorted({r["dopplerFrequency"] for r in rows})
    print(f"  processingLevel: {lv}   dopplerFrequency: {dc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
