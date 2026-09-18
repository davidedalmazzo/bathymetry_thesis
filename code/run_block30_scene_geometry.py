#!/usr/bin/env python3
"""Block 30 - geometria delle acquisizioni COSMO-SkyMed su Duck (FRF, NC).

Legge l'export CLEOS (GeoJSON) e produce la tabella geometrica delle scene.
Nessun download SAR, nessuna inversione, nessuna correzione di q.

Cosa calcola, e con quale stato epistemico:

  OSSERVATO (dai metadati)
    piattaforma, modo, fascio, nodo d'orbita, polarizzazione, angoli di
    incidenza, durata del data take, poligono dell'impronta.

  CALCOLATO (da leggi note e dai metadati)
    range di slant dall'incidenza e dalla quota CSK;
    beta = R/V (per il cut-off azimutale);
    T_dwell = lambda*R / (2*delta_az*V), cioe' il tempo di illuminazione del
    SINGOLO bersaglio. **Non e' la durata del data take**: quella copre lo
    scorrimento del fascio sull'intera scena in azimut ed e' ~5x piu' lunga.
    Confondere le due cose sovrastima il dwell di un fattore 5.
    T_base = 0.65*T_dwell (limite aggressivo della separazione fra sub-look:
    due look ai bordi della banda Doppler con frazione 0.35 ciascuno).
    dphi = omega*T_base per periodi d'onda di riferimento.
    heading dal poligono, direzione di range = heading + 90 (right-looking).

  ASSUNTO (da confermare, non da usare come verita')
    OFFSHORE_DEG = 70: asse cross-shore del FRF, stimato dai bearing
    molo->44056 (57.7 deg) e molo->44100 (59.2 deg). Da confermare sui
    metadati FRF.
    Direzione di propagazione dell'onda = OFFSHORE_DEG + 180. E' una
    climatologia di comodo: il gate vero usa la direzione MISURATA alla boa,
    che arriva da run_block30_frf_conditions.py.

Il fattore di allargamento della finestra di pesatura non e' applicato: se la
risoluzione dichiarata e' la larghezza a -3 dB con finestra (tipicamente
~1.25x), il dwell reale e' maggiore e i dphi qui sono un LIMITE INFERIORE.

Uso:
  python code/run_block30_scene_geometry.py \
      Block30_duck_csk_preflight/cleos_export/results_COSMO-SkyMed_*.json \
      Block30_duck_csk_preflight
"""
from __future__ import annotations
import csv, json, math, sys
from datetime import datetime
from pathlib import Path

R_EARTH_M = 6371008.8
RE_KM = 6371.0
CSK_ALT_KM = 619.0          # quota nominale COSMO-SkyMed I generazione
CSK_LAMBDA_M = 3e8 / 9.6e9  # banda X, 9.6 GHz
V_SAT_KMS = 7.6
DELTA_AZ_M = 1.0            # risoluzione azimutale nominale classe VHR1b
LOOK_FRACTION = 0.65        # separazione fra centroidi dei due sub-look

PIER = (36.1836, -75.7461)      # testata molo FRF
SHORE = (36.1836, -75.7497)     # linea di riva al molo (approssimata)
OFFSHORE_DEG = 70.0             # ASSUNTO, vedi docstring
WR_17M = (36.200, -75.714)      # NDBC 44056 / waverider-17m
WR_26M = (36.257, -75.593)      # NDBC 44100 / CDIP 430 / waverider-26m
REF_PERIODS_S = (8.0, 10.0, 12.0)


def ll2xy(lat, lon, lat0, lon0):
    x = math.radians(lon - lon0) * R_EARTH_M * math.cos(math.radians(lat0))
    y = math.radians(lat - lat0) * R_EARTH_M
    return x, y


def bearing(dx, dy):
    return math.degrees(math.atan2(dx, dy)) % 360.0


def d180(a, b):
    return min(abs((a - b) % 180.0), 180.0 - abs((a - b) % 180.0))


def in_polygon(pt, poly):
    x, y = pt
    n = len(poly)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def parse_time(s):
    return datetime.strptime(s.replace("Z", "")[:26], "%Y-%m-%dT%H:%M:%S.%f")


def slant_range_km(incidence_deg):
    """Range di slant da angolo di incidenza al suolo e quota orbitale."""
    th = math.radians(incidence_deg)
    look = math.asin(RE_KM / (RE_KM + CSK_ALT_KM) * math.sin(th))
    return RE_KM * math.sin(th - look) / math.sin(look)


def main(argv):
    if len(argv) != 3:
        print(__doc__)
        return 2
    src, outdir = Path(argv[1]), Path(argv[2])
    outdir.mkdir(parents=True, exist_ok=True)
    features = json.loads(src.read_text(encoding="utf-8"))["features"]

    rows = []
    for feat in features:
        p = feat["properties"]
        ring = [(c[1], c[0]) for c in feat["geometry"]["coordinates"][0]]
        if ring[0] == ring[-1]:
            ring = ring[:-1]
        lat0 = sum(a for a, _ in ring) / len(ring)
        lon0 = sum(b for _, b in ring) / len(ring)
        xy = [ll2xy(a, b, lat0, lon0) for a, b in ring]

        edges = []
        for i in range(len(xy)):
            x1, y1 = xy[i]
            x2, y2 = xy[(i + 1) % len(xy)]
            edges.append((math.hypot(x2 - x1, y2 - y1), bearing(x2 - x1, y2 - y1)))

        nominal_head = 190.0 if p["orbit_direction"] == "DESCENDING" else 350.0
        az_edge = min(edges, key=lambda e: d180(e[1], nominal_head))
        head = az_edge[1]
        if abs(((head - nominal_head + 180) % 360) - 180) >= 90:
            head = (head + 180.0) % 360.0
        range_dir = (head + 90.0) % 360.0          # right-looking
        k_dir_assumed = (OFFSHORE_DEG + 180.0) % 360.0
        phi = d180(k_dir_assumed, range_dir)

        cross_shore_km = []
        for a, b in ring:
            x, y = ll2xy(a, b, *SHORE)
            cross_shore_km.append(
                (x * math.sin(math.radians(OFFSHORE_DEG))
                 + y * math.cos(math.radians(OFFSHORE_DEG))) / 1000.0)

        inc = (p["minimum_incidence_angle"] + p["maximum_incidence_angle"]) / 2.0
        r_km = slant_range_km(inc)
        t_dwell = CSK_LAMBDA_M * r_km * 1e3 / (2.0 * DELTA_AZ_M * V_SAT_KMS * 1e3)
        t_base = LOOK_FRACTION * t_dwell
        poly_lonlat = [(b, a) for a, b in ring]

        row = {
            "acq_utc": p["start_datetime"][:19].replace("T", " "),
            "platform": p["platform"],
            "mission": p["mission"],
            "acquisition_mode": p["acquisition_mode"],
            "node": p["orbit_direction"],
            "beam": p["beam"],
            "polarization": p["polarization"],
            "product_id": p["product_identifier"],
            "inc_deg": round(inc, 2),
            "slant_km": round(r_km, 1),
            "beta_s": round(r_km * 1e3 / (V_SAT_KMS * 1e3), 1),
            "datatake_s": round((parse_time(p["end_datetime"])
                                 - parse_time(p["start_datetime"])).total_seconds(), 2),
            "T_dwell_s": round(t_dwell, 2),
            "T_base_s": round(t_base, 2),
            "heading_deg": round(head, 1),
            "range_dir_deg": round(range_dir, 1),
            "phi_k_range_deg_ASSUNTO": round(phi, 1),
            "offshore_extent_km": round(max(cross_shore_km), 2),
            "onshore_extent_km": round(min(cross_shore_km), 2),
            "pier_in": in_polygon((PIER[1], PIER[0]), poly_lonlat),
            "wr17m_in": in_polygon((WR_17M[1], WR_17M[0]), poly_lonlat),
            "wr26m_in": in_polygon((WR_26M[1], WR_26M[0]), poly_lonlat),
            "centre_lat": round(lat0, 5),
            "centre_lon": round(lon0, 5),
        }
        for tw in REF_PERIODS_S:
            row[f"dphi_{int(tw)}s_deg"] = round(math.degrees(2 * math.pi / tw * t_base))
        rows.append(row)

    rows.sort(key=lambda r: r["acq_utc"])
    out = outdir / "BLOCK30_CSK_DUCK_SCENES.csv"
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} scene -> {out}")
    print(f"  con waverider-17m nell'impronta: {sum(r['wr17m_in'] for r in rows)}")
    print(f"  dphi @T=10 s: {min(r['dphi_10s_deg'] for r in rows)}"
          f" - {max(r['dphi_10s_deg'] for r in rows)} deg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
