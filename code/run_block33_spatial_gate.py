#!/usr/bin/env python3
"""Block 33b - classifica delle scene Sentinel-1 per la VALIDAZIONE SPAZIALE.

Obiettivo: stimare k localmente dallo spettro d'immagine SAR, prendere omega
dalla boa FRF invece che dalla fase del cross-spettro, invertire
omega^2 = g k tanh(kh) e confrontare h con i rilievi FRF.

**Il gate sulla fase non c'e'.** Dwell, Delta phi e avvolgimento sono
irrilevanti qui: omega arriva dall'esterno. Cio' che conta e' se l'onda e'
visibile nell'immagine, se sopravvive al cut-off, se k e' misurabile con la
precisione che serve, e se la profondita' cade dove l'inversione e' sensibile.

## I criteri, e perche'

S1  ANGOLO k-RANGE, dalla direzione MISURATA alla boa (non assunta).
    Governa tutto il resto: il cut-off agisce sulla componente azimutale.

S2  CUT-OFF AZIMUTALE.  L/sin(phi) >= lambda_c, con lambda_c = 2 pi beta sigma_ur.
    Per Sentinel-1 beta = R/V ~ 113 s contro gli ~86 s del TerraSAR-X: a parita'
    di mare il cut-off e' ~30% peggiore. E' il gate piu' severo.

S3  RIPIDITA' H/L.  La modulazione di tilt scala con la pendenza dell'onda, non
    con Hs. Uno swell da 0.8 m e 15 s ha H/L = 0.002 ed e' quasi invisibile.

S4  VENTO.  Finestra a due lati, mai usata nei blocchi precedenti:
      troppo poco  -> niente rugosita' di Bragg, NRCS sotto il rumore
      troppo       -> mare di vento a banda larga che seppellisce il picco di swell
    Soglie descrittive 3-10 m/s. Dal gauge FRF meteorology/wind/derived.

S5  PULIZIA SPETTRALE.  directionalPeakSpread basso e picco coerente fra
    strumenti del transetto: serve un lobo isolabile, non una miscela.

S6  BANDA DI PROFONDITA'.  kh nella fascia sensibile. Fuori da kh ~ [0.6, 2.0]
    l'inversione perde sensibilita' o esce dal lineare.

S7  RISOLUZIONE SPETTRALE NECESSARIA.  L'errore su k si amplifica su h:
        delta_h/h = G(kh) * delta_k/k     con  G(kh) = n sinh(2kh)/(kh)
    e delta_k/k ~ L/W per una finestra di lato W. Quindi
        W_richiesta = G(kh) * L / (delta_h/h)_obiettivo
    Si confronta con il pavimento analitico di Block 17, che limita comunque
    l'accuratezza a causa del gradiente del fondale: non ha senso chiedere una
    finestra piu' grande di quella che il pavimento rende utile.

Tutte le soglie sono DESCRITTIVE, non calibrate.

Uso (dalla radice del repo):
  python code/run_block33_spatial_gate.py \
      Block33_s1_duck_query/BLOCK33_S1_DUCK_SCENES.csv \
      Block33_s1_duck_query/BLOCK30_FRF_CONDITIONS.csv \
      Block33_s1_duck_query
"""
from __future__ import annotations
import csv, math, re, sys, time, urllib.error, urllib.request
from datetime import datetime, timezone
from pathlib import Path

G = 9.81
H_REF = 17.8                  # profondita' della boa di riferimento
DEPTH_BAND = (8.0, 20.0)      # fascia d'acqua utile nell'impronta a Duck
GRAD_OFFSHORE = 5.0e-4        # gradiente del fondale oltre 2.5 km
TARGET_DH_REL = 0.10          # obiettivo descrittivo sull'accuratezza in h
WIND_WINDOW = (3.0, 10.0)     # m/s, descrittivo
STEEPNESS_MIN = 0.008
CUTOFF_MARGIN_MIN = 2.0
KH_BAND = (0.6, 2.0)

WIND_BASE = "https://chldata.erdc.dren.mil/thredds/dodsC/frf/meteorology/wind/derived"
_spent = {"n": 0, "b": 0}


def fetch(url, timeout=90):
    if _spent["n"] >= 60:
        raise RuntimeError("budget richieste esaurito")
    req = urllib.request.Request(url, headers={"User-Agent": "polimi-thesis-block33"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read(20 * 1024 * 1024)
    _spent["n"] += 1; _spent["b"] += len(raw)
    return raw.decode("utf-8", "replace")


def parse_ascii_vector(text: str, name: str):
    lines = text.splitlines()
    start = 0
    for i, ln in enumerate(lines):
        if set(ln.strip()) == {"-"} and len(ln.strip()) > 10:
            start = i + 1; break
    hdr = re.compile(r"^" + re.escape(name) + r"(\[[0-9]+\])*\s*$")
    any_hdr = re.compile(r"^[A-Za-z_]\w*(\[[0-9]+\])*\s*$")
    vals, cap = [], False
    for ln in lines[start:]:
        t = ln.strip()
        if not t:
            if cap: break
            continue
        if hdr.match(t): cap = True; continue
        if any_hdr.match(t):
            if cap: break
            continue
        if cap:
            for tok in t.split(","):
                tok = tok.strip()
                if tok:
                    try: vals.append(float(tok))
                    except ValueError: pass
    return vals


def load_wind_month(yyyymm: str):
    base = f"{WIND_BASE}/{yyyymm[:4]}/FRF-met_wind_derived_{yyyymm}.nc"
    try:
        t = [v for v in parse_ascii_vector(fetch(base + ".ascii?time"), "time")]
        ws = parse_ascii_vector(fetch(base + ".ascii?windSpeed"), "windSpeed")
        wd = parse_ascii_vector(fetch(base + ".ascii?windDirection"), "windDirection")
    except urllib.error.HTTPError:
        return None
    if not t or len(ws) != len(t):
        return None
    return t, ws, (wd if len(wd) == len(t) else None)


def kof(T, h):
    w = 2 * math.pi / T; k = w * w / G
    for _ in range(200):
        k -= (G * k * math.tanh(k * h) - w * w) / (
            G * math.tanh(k * h) + G * k * h / math.cosh(k * h) ** 2)
    return k


def amplif(kh):
    n = 0.5 * (1 + 2 * kh / math.sinh(2 * kh))
    return n * math.sinh(2 * kh) / kh, n


def block17_floor(kh, grad):
    n = 0.5 * (1 + 2 * kh / math.sinh(2 * kh))
    A = 1 + math.sinh(2 * kh) / (2 * kh)
    return A * math.sqrt(2 * math.pi * grad / (n * math.sinh(2 * kh)))


def d180(a, b):
    return min(abs((a - b) % 180.0), 180.0 - abs((a - b) % 180.0))


def main(argv):
    if len(argv) != 4:
        print(__doc__); return 2
    scenes = list(csv.DictReader(Path(argv[1]).open()))
    conds = list(csv.DictReader(Path(argv[2]).open()))
    outdir = Path(argv[3]); outdir.mkdir(parents=True, exist_ok=True)

    by_t = {}
    for c in conds:
        if c.get("gauge") == "waverider-17m" and abs(float(c["dt_min"])) <= 60:
            by_t[c["acq_utc"]] = c

    months = sorted({s["acq_utc"][:7].replace("-", "") for s in scenes})
    wind = {}
    for m in months:
        try:
            wind[m] = load_wind_month(m)
            print(f"  vento {m}: {'ok' if wind[m] else 'assente'}")
        except Exception as e:
            wind[m] = None; print(f"  vento {m}: errore {e}")
        time.sleep(0.4)

    rows = []
    for s in scenes:
        c = by_t.get(s["acq_utc"])
        if not c or not c.get("waveTp") or c.get("waveMeanDirection") in (None, ""):
            continue
        Tp = float(c["waveTp"]); Hs = float(c["waveHs"])
        mwd = float(c["waveMeanDirection"])
        spread = float(c["directionalPeakSpread"]) if c.get("directionalPeakSpread") else None

        k = kof(Tp, H_REF); L = 2 * math.pi / k; kh = k * H_REF
        kdir = (mwd + 180.0) % 360.0
        phi = d180(kdir, float(s["range_dir_deg"]))
        L_az = L / max(math.sin(math.radians(phi)), 1e-3)
        beta = float(s["beta_s"])
        w = 2 * math.pi / Tp
        sig_ur = 0.25 * Hs * w * math.cos(math.radians(float(s["inc_deg_APPROSSIMATA"])))
        lam_c = 2 * math.pi * beta * sig_ur
        Gk, n = amplif(kh)
        W_req = Gk * L / TARGET_DH_REL
        floor = block17_floor(kh, GRAD_OFFSHORE)
        kh_shallow = kof(Tp, DEPTH_BAND[0]) * DEPTH_BAND[0]
        kh_deep = kof(Tp, DEPTH_BAND[1]) * DEPTH_BAND[1]

        t_acq = datetime.strptime(s["acq_utc"], "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=timezone.utc).timestamp()
        m = s["acq_utc"][:7].replace("-", "")
        ws = wd = dt_w = None
        if wind.get(m):
            tt, sp, dd = wind[m]
            i = min(range(len(tt)), key=lambda j: abs(tt[j] - t_acq))
            if abs(tt[i] - t_acq) <= 3600 and -1e30 < sp[i] < 1e30:
                ws = round(sp[i], 2); dt_w = round((tt[i] - t_acq) / 60, 1)
                if dd and -1e30 < dd[i] < 1e30:
                    wd = round(dd[i], 1)

        g = {
            "S2_cutoff": (L_az / lam_c) >= CUTOFF_MARGIN_MIN if lam_c else False,
            "S3_ripidita": (Hs / L) >= STEEPNESS_MIN,
            "S4_vento": ws is not None and WIND_WINDOW[0] <= ws <= WIND_WINDOW[1],
            "S6_banda_kh": KH_BAND[0] <= kh_deep and kh_shallow <= KH_BAND[1],
        }
        rows.append({
            "acq_utc": s["acq_utc"], "product_id": s["product_id"],
            "node": s["node"], "rel_orbit": s["rel_orbit"],
            "Hs_m": Hs, "Tp_s": Tp, "meanDir_deg": mwd,
            "directionalPeakSpread": spread,
            "wind_ms": ws, "wind_dir_deg": wd, "wind_dt_min": dt_w,
            "k_dir_deg": round(kdir, 1), "range_dir_deg": s["range_dir_deg"],
            "S1_phi_k_range_deg": round(phi, 1),
            "L_17m_m": round(L, 1), "kh_17m": round(kh, 2),
            "kh_a_8m": round(kh_shallow, 2), "kh_a_20m": round(kh_deep, 2),
            "L_azimutale_m": round(L_az), "lambda_cutoff_m": round(lam_c),
            "S2_cutoff_margin": round(L_az / lam_c, 2) if lam_c else None,
            "S3_steepness_HL": round(Hs / L, 4),
            "amplificazione_G": round(Gk, 2),
            "W_richiesta_km": round(W_req / 1000, 2),
            "pavimento_block17_dh_rel": round(floor, 3),
            "pavimento_block17_dh_m": round(floor * H_REF, 2),
            "offshore_extent_km": s["offshore_extent_km"],
            "wr17m_in": s["wr17m_in"],
            **{f"gate_{kk}": vv for kk, vv in g.items()},
            "passa_tutti": all(g.values()),
            "n_gate_passati": sum(g.values()),
        })

    rows.sort(key=lambda r: (-r["n_gate_passati"], -(r["S2_cutoff_margin"] or 0)))
    out = outdir / "BLOCK33_SPATIAL_GATE.csv"
    with out.open("w", newline="", encoding="utf-8") as fh:
        w_ = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w_.writeheader(); w_.writerows(rows)
    print(f"\n{len(rows)} scene valutate -> {out}")
    print(f"  passano tutti i gate: {sum(r['passa_tutti'] for r in rows)}")
    for r in rows[:10]:
        print("  %-19s Hs=%4.2f Tp=%5.2f phi=%5.1f marg=%6.2f H/L=%.4f vento=%s W_req=%.1f km %s"
              % (r["acq_utc"], r["Hs_m"], r["Tp_s"], r["S1_phi_k_range_deg"],
                 r["S2_cutoff_margin"] or 0, r["S3_steepness_HL"],
                 r["wind_ms"], r["W_richiesta_km"],
                 "OK" if r["passa_tutti"] else f"{r['n_gate_passati']}/4"))
    print(f"richieste {_spent['n']}, byte {_spent['b']/1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
