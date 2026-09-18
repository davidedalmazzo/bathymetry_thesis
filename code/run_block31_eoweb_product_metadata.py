#!/usr/bin/env python3
"""Block 31 - inventario delle acquisizioni candidate su Duck (FRF, NC).

Legge due sorgenti diverse e le fonde in una tabella sola:

  EOWEB (DLR)    pagine "product detail" incollate in .txt  -> TerraSAR-X / TanDEM-X
  CLEOS (e-GEOS) export KML o GeoJSON                       -> COSMO-SkyMed

Nessun download di prodotti SAR.

## Le due sorgenti NON hanno lo stesso livello di metadati

La colonna `metadata_level` lo dichiara riga per riga, e non e' una distinzione
formale:

  `product`    EOWEB. Ha `processingLevel`, `sensorResolution`,
               `dopplerFrequency`, qualita', disponibilita': campi letti dal
               prodotto.
  `catalogue`  CLEOS. Solo metadati di catalogo. **Manca il livello di prodotto**
               (SCS? L0?), **manca la risoluzione azimutale reale** — c'e' solo
               `resolution_class: VHR1b`, che e' un'etichetta di classe — e
               mancano banda di chirp e centroide Doppler.

Per le righe `catalogue` il dwell e' calcolato dalla risoluzione azimutale
NOMINALE del modo. E' esattamente il campo su cui ci si e' gia' sbagliati con
TerraSAR-X, dove `sensorResolution` si e' rivelato la risoluzione in range
obliquo e non quella azimutale. **I dphi delle righe COSMO restano provvisori
finche' non si leggono i metadati di prodotto dei singoli elementi.**

## Perche' `sensorResolution` non risolve il problema (lezione TerraSAR-X)

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

Uso (l'ultimo argomento e' la directory di uscita):
  python code/run_block31_eoweb_product_metadata.py \
      "Block31_tsx_duck_query/eoweb_products/*.txt" \
      "Block31_tsx_duck_query/cleos_export/*.kml" \
      Block31_tsx_duck_query

I .txt sono letti come pagine EOWEB, i .kml e .geojson/.json come export CLEOS.
"""
from __future__ import annotations
import csv, math, re, sys
import json
import xml.etree.ElementTree as ET
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
DELTA_AZ_NOMINAL_M = {"ST": 0.24, "HS": 1.10, "SL": 2.00,
                      # COSMO-SkyMed I gen, Enhanced Spotlight.
                      # 0.91 m = risoluzione azimutale a Livello 1A dichiarata
                      # nel documento ASI-CSM-PMG-NT-001 (Mission and Products
                      # Description, rev.3). NON e' un campo del catalogo, che
                      # riporta solo `resolution_class: VHR1b`. Se e' la
                      # larghezza a -3 dB con finestra di pesatura, l'apertura
                      # reale e' ~20-30% maggiore e i dphi qui sono un limite
                      # inferiore, come verificato su TerraSAR-X.
                      "Spotlight-2": 0.91}

SENSOR_CONST = {   # lambda, quota orbitale, velocita'
    "TSX": {"lambda_m": 3e8 / 9.65e9, "alt_km": 514.8, "v_kms": 7.6},
    # quota 619.6 km da ASI-CSM-PMG-NT-001; v = velocita' orbitale a quella quota
    "CSK": {"lambda_m": 3e8 / 9.60e9, "alt_km": 619.6, "v_kms": 7.551},
}

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


def slant_range_km(incidence_deg, alt_km=TSX_ALT_KM):
    th = math.radians(incidence_deg)
    look = math.asin(RE_KM / (RE_KM + alt_km) * math.sin(th))
    return RE_KM * math.sin(th - look) / math.sin(look)


def parse_time(s):
    return datetime.strptime(s.replace("Z", "")[:23], "%Y-%m-%dT%H:%M:%S.%f")




# ---------------------------------------------------------------- CLEOS ----
def parse_cleos(path: Path):
    """Export CLEOS: KML (Placemark/ExtendedData) o GeoJSON. Metadati di CATALOGO."""
    txt = path.read_text(encoding="utf-8", errors="replace")
    recs = []
    if path.suffix.lower() in (".json", ".geojson"):
        for f in json.loads(txt).get("features", []):
            pr = dict(f.get("properties") or {})
            ring = [(c[1], c[0]) for c in (f.get("geometry", {})
                                           .get("coordinates") or [[]])[0]]
            if len(ring) > 1 and ring[0] == ring[-1]:
                ring = ring[:-1]
            pr["_ring"] = ring
            recs.append(pr)
        return recs
    ns = {"k": "http://www.opengis.net/kml/2.2"}
    root = ET.fromstring(txt)
    for pm in root.findall(".//k:Placemark", ns):
        pr = {}
        for data in pm.findall(".//k:Data", ns):
            dn = data.find("k:displayName", ns); v = data.find("k:value", ns)
            if dn is not None and dn.text:
                pr[dn.text] = v.text if v is not None else None
        co = pm.find(".//k:coordinates", ns)
        ring = []
        if co is not None and co.text:
            for tok in co.text.split():
                c = tok.split(",")
                if len(c) >= 2:
                    ring.append((float(c[1]), float(c[0])))
        if len(ring) > 1 and ring[0] == ring[-1]:
            ring = ring[:-1]
        pr["_ring"] = ring
        recs.append(pr)
    return recs


# ------------------------------------------------------------- geometria ---
def geometry(ring, node, nominal_desc=190.0, nominal_asc=350.0):
    lat0 = sum(a for a, _ in ring) / len(ring)
    lon0 = sum(b for _, b in ring) / len(ring)
    xy = [ll2xy(a, b, lat0, lon0) for a, b in ring]
    edges = []
    for i in range(len(xy)):
        x1, y1 = xy[i]; x2, y2 = xy[(i + 1) % len(xy)]
        edges.append((math.hypot(x2 - x1, y2 - y1), bearing(x2 - x1, y2 - y1)))
    nominal = nominal_desc if str(node).upper().startswith("DESC") else nominal_asc
    head = min(edges, key=lambda e: d180(e[1], nominal))[1]
    if abs(((head - nominal + 180) % 360) - 180) >= 90:
        head = (head + 180.0) % 360.0
    poly = [(b, a) for a, b in ring]
    cs = []
    for a, b in ring:
        x, y = ll2xy(a, b, *SHORE)
        cs.append((x * math.sin(math.radians(OFFSHORE_DEG))
                   + y * math.cos(math.radians(OFFSHORE_DEG))) / 1000.0)
    return {
        "heading_deg": round(head, 1),
        "range_dir_deg": round((head + 90.0) % 360.0, 1),
        "offshore_extent_km": round(max(cs), 2),
        "onshore_extent_km": round(min(cs), 2),
        "footprint_long_km": round(max(e[0] for e in edges) / 1000, 2),
        "footprint_short_km": round(min(e[0] for e in edges) / 1000, 2),
        "sea_area_km2": round(max(max(cs), 0.0) * min(e[0] for e in edges) / 1000, 1),
        "pier_in": in_polygon((PIER[1], PIER[0]), poly),
        "wr17m_in": in_polygon((WR_17M[1], WR_17M[0]), poly),
        "wr26m_in": in_polygon((WR_26M[1], WR_26M[0]), poly),
        "centre_lat": round(lat0, 5), "centre_lon": round(lon0, 5),
    }


def kinematics(mode, inc, sensor):
    c = SENSOR_CONST[sensor]
    d_az = DELTA_AZ_NOMINAL_M[mode]
    r_km = slant_range_km(inc, c["alt_km"])
    t_dwell = c["lambda_m"] * r_km * 1e3 / (2.0 * d_az * c["v_kms"] * 1e3)
    t_base = LOOK_FRACTION * t_dwell
    out = {"delta_az_m": d_az,
           "delta_az_source": "nominale del modo (NON misurata sul prodotto)",
           "slant_km": round(r_km, 1),
           "beta_s": round(r_km * 1e3 / (c["v_kms"] * 1e3), 1),
           "T_dwell_s": round(t_dwell, 3), "T_base_s": round(t_base, 3)}
    for tw in REF_PERIODS_S:
        out[f"dphi_{int(tw)}s_deg"] = round(math.degrees(2 * math.pi / tw * t_base))
    return out


def derive_eoweb(rec):
    out = dict(rec)
    mode = rec.get("sensorOperationalMode", "")
    if mode not in DELTA_AZ_NOMINAL_M:
        raise RuntimeError(f"modo {mode!r} senza risoluzione azimutale nominale nota")
    inc = float(rec["incidenceAngle"])
    ring = polygon_points(rec["polygon"])
    span = (parse_time(rec["stopTime"]) - parse_time(rec["startTime"])).total_seconds()
    m = re.search(r"dims_\w+_dfd_(\w+)/", rec["eoweb_id"])
    out.update(kinematics(mode, inc, "TSX"))
    out.update(geometry(ring, rec.get("orbitDirection")))
    out.update({
        "sensore": "TerraSAR-X/TanDEM-X", "metadata_level": "product",
        "sorgente": "EOWEB product detail",
        "product_id": m.group(1) if m else "",
        "acq_utc": rec["startTime"][:19].replace("T", " "),
        "mode": mode,
        "slant_range_res_m": float(rec["sensorResolution"]),
        "chirp_bw_MHz_inferita": round(1.18 * 3e8 / (2 * float(rec["sensorResolution"])) / 1e6),
        "eoweb_span_s": round(span, 3),
        "scene_azimuth_km": round(span * V_GROUND_KMS, 2),
    })
    return out


def derive_cleos(pr):
    ring = pr.get("_ring") or []
    if not ring:
        return None
    mode = pr.get("acquisition_mode", "")
    if mode not in DELTA_AZ_NOMINAL_M:
        raise RuntimeError(f"modo {mode!r} senza risoluzione azimutale nominale nota")
    inc = (float(pr["minimum_incidence_angle"]) + float(pr["maximum_incidence_angle"])) / 2.0
    t0, t1 = pr.get("start_datetime", ""), pr.get("end_datetime", "")
    span = None
    if t0 and t1:
        span = (parse_time(t1) - parse_time(t0)).total_seconds()
    out = {}
    out.update(kinematics(mode, inc, "CSK"))
    out.update(geometry(ring, pr.get("orbit_direction")))
    out.update({
        "sensore": "COSMO-SkyMed I gen", "metadata_level": "catalogue",
        "sorgente": "CLEOS export",
        "acq_utc": t0[:19].replace("T", " "),
        "mode": mode,
        "product_id": pr.get("product_identifier", ""),
        "product_name": pr.get("product_identifier", ""),
        "platformSerialIdentifier": pr.get("platform"),
        "orbitDirection": pr.get("orbit_direction"),
        "swathIdentifier": pr.get("beam"),
        "polarisationChannels": pr.get("polarization"),
        "incidenceAngle": round(inc, 3),
        "minimumIncidenceAngle": pr.get("minimum_incidence_angle"),
        "maximumIncidenceAngle": pr.get("maximum_incidence_angle"),
        "orbitNumber": pr.get("orbit_number"),
        "antennaLookDirection": pr.get("lookside"),
        "Availability": pr.get("acquisition_status"),
        "startTime": t0, "stopTime": t1,
        "cleos_datatake_s": round(span, 3) if span is not None else None,
        "resolution_class": pr.get("resolution_class"),
        "off_nadir_angle": pr.get("off_nadir_angle"),
        "aoi_coverage_percentage": pr.get("aoi_coverage_percentage"),
        "processingLevel": "",      # NON fornito dal catalogo
        "dopplerFrequency": "",     # NON fornito dal catalogo
        "slant_range_res_m": "",    # NON fornito dal catalogo
    })
    return out


COLS = ["acq_utc", "sensore", "mode", "metadata_level", "product_id",
        "platformSerialIdentifier", "orbitDirection", "swathIdentifier",
        "polarisationChannels", "polarisationMode",
        "delta_az_m", "delta_az_source", "slant_range_res_m",
        "chirp_bw_MHz_inferita", "sensorResolution", "resolution_class",
        "incidenceAngle", "minimumIncidenceAngle", "maximumIncidenceAngle",
        "off_nadir_angle", "slant_km", "beta_s", "T_dwell_s", "T_base_s",
        "dphi_8s_deg", "dphi_10s_deg", "dphi_12s_deg",
        "eoweb_span_s", "cleos_datatake_s", "scene_azimuth_km",
        "heading_deg", "range_dir_deg", "offshore_extent_km",
        "onshore_extent_km", "footprint_long_km", "footprint_short_km",
        "sea_area_km2", "pier_in", "wr17m_in", "wr26m_in",
        "centre_lat", "centre_lon", "processingLevel", "dopplerFrequency",
        "Quality", "Availability", "Revision", "aoi_coverage_percentage",
        "orbitNumber", "RelOrbit", "OrbitCycle", "OrbitPhase", "OrbitsRepeatCycle",
        "DatatakeFileNumber", "UniqueDataTakeID", "AntennaReceiveConfiguration",
        "IOP", "GOP", "acquisitionStation", "acquisitionDate", "archivingDate",
        "startTime", "stopTime", "status", "processorName", "acquisitionType",
        "antennaLookDirection", "CreationSite", "sorgente", "eoweb_id", "polygon"]

SENSOR_ORDER = {"TerraSAR-X/TanDEM-X": 0, "COSMO-SkyMed I gen": 1}
MODE_ORDER = {"ST": 0, "HS": 1, "SL": 2, "Spotlight-2": 3}


def main(argv):
    if len(argv) < 3:
        print(__doc__); return 2
    outdir = Path(argv[-1]); outdir.mkdir(parents=True, exist_ok=True)
    rows = []
    for pat in argv[1:-1]:
        files = sorted(Path().glob(pat)) or ([Path(pat)] if Path(pat).is_file() else [])
        for f in files:
            if not f.is_file():
                continue
            if f.suffix.lower() == ".txt":
                n = 0
                for rec in parse_records(f.read_text(encoding="utf-8", errors="replace")):
                    rows.append(derive_eoweb(rec)); n += 1
                print(f"  EOWEB  {f.name}: {n} prodotti")
            elif f.suffix.lower() in (".kml", ".json", ".geojson"):
                n = 0
                for pr in parse_cleos(f):
                    r = derive_cleos(pr)
                    if r: rows.append(r); n += 1
                print(f"  CLEOS  {f.name}: {n} acquisizioni")
    if not rows:
        print("nessun record trovato", file=sys.stderr); return 1
    rows.sort(key=lambda r: (SENSOR_ORDER.get(r["sensore"], 9),
                             MODE_ORDER.get(r["mode"], 9), r["acq_utc"]))
    out = outdir / "BLOCK31_ACQUISITION_METADATA.csv"
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS, extrasaction="ignore")
        w.writeheader(); w.writerows(rows)
    print(f"\n{len(rows)} acquisizioni -> {out}")
    seen = {}
    for r in rows:
        seen.setdefault((r["sensore"], r["mode"]), []).append(r)
    for (sens, mode), g in seen.items():
        print(f"  {sens:22s} {mode:12s} {len(g):2d} scene  "
              f"d_az={g[0]['delta_az_m']}  T_dwell {min(x['T_dwell_s'] for x in g):.2f}"
              f"-{max(x['T_dwell_s'] for x in g):.2f} s  "
              f"dphi@10s {min(x['dphi_10s_deg'] for x in g)}-{max(x['dphi_10s_deg'] for x in g)} deg  "
              f"[{g[0]['metadata_level']}]")
    lv = sorted({r.get("processingLevel", "") for r in rows})
    print(f"  processingLevel presenti: {lv}")
    print("\n  ATTENZIONE: le righe 'catalogue' non hanno livello di prodotto ne'")
    print("  risoluzione azimutale misurata. I loro dphi sono provvisori.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
