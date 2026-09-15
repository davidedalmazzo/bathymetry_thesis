#!/usr/bin/env python3
"""Block 19 (ESPLORATIVO) — screen di fattibilita' fisica congiunta.

Non e' un gate e non promuove nessuna scena. Ordina.

Il Block16A-18 valuta i proxy uno alla volta e **non usa mai la profondita'**.
Questo script aggiunge la batimetria e valuta i requisiti IN CONGIUNZIONE.

  G1  l'onda deve sentire il fondo        kh <= 1.5      A = 1 + sinh(2kh)/(2kh)
  G2  deve battere il cut-off azimutale   L/sin(phi) >= lambda_c = 2 pi beta sigma_ur
      dove phi e' l'angolo fra il vettore d'onda e l'asse range.  Il cut-off
      agisce sulla componente AZIMUTALE di k, non su |k|: un'onda che viaggia in
      range non ne e' mai tagliata.  phi_max e' la liberta' geometrica residua.
  G3  il dwell deve coprire un ciclo      T_dwell / T >= ~1
  G4  il fondale deve essere dolce        il termine spaziale scala come sqrt(grad h)

`dh/h` e' riportato come INDICATORE sotto le ipotesi dichiarate in
docs/NOTE_accuracy_envelope_open.md — la covarianza k-omega non e' ancora
trattata e 2*pi/W e' una risoluzione, non l'errore di uno stimatore.
Non e' una soglia.

Batimetria: GEBCO2020 via opentopodata, stencil a 5 punti.
Periodi: climatologici per costa, non dello scene.
"""
from __future__ import annotations
import json, math, sys

G = 9.80665
BETA_DEFAULT = 79.75          # R/V [s], valore Umbra misurato a Vandenberg


def k_of(T: float, h: float) -> float:
    w = 2 * math.pi / T
    k = w * w / G
    for _ in range(400):
        k = w * w / (G * math.tanh(k * h))
    return k


def amplification(kh: float):
    A = 1.0 + math.sinh(2 * kh) / (2 * kh)
    return A, 2.0 * (A - 1.0)


def lambda_cutoff(Hs: float, T: float, beta: float = BETA_DEFAULT,
                  incidence_deg: float = 33.0) -> float:
    """Stima del cut-off azimutale. sigma_ur dal solo picco: e' un limite
    INFERIORE, la coda spettrale lo allarga. Conservativo nel verso giusto."""
    sigma_u = (Hs / 4.0) * (2 * math.pi / T)
    return 2 * math.pi * beta * sigma_u * math.sin(math.radians(incidence_deg))


def phi_max_deg(L: float, Hs: float, T: float, **kw) -> float:
    """Massimo angolo onda-range che batte ancora il cut-off."""
    s = L / lambda_cutoff(Hs, T, **kw)
    return 90.0 if s >= 1.0 else math.degrees(math.asin(s))


def spatial_indicator(kh: float, grad: float) -> float:
    """Termine spaziale al W autoconsistente (nota aperta, non validato)."""
    A, _ = amplification(kh)
    n = 0.5 * (1.0 + 2 * kh / math.sinh(2 * kh))
    return A * math.sqrt(2 * math.pi * grad / (n * math.sinh(2 * kh)))


def evaluate(name, h, grad, Hs, Tp, dwell=None, beta=BETA_DEFAULT, inc=33.0):
    k = k_of(Tp, h)
    kh = k * h
    L = 2 * math.pi / k
    A, B = amplification(kh)
    lc = lambda_cutoff(Hs, Tp, beta, inc)
    pm = phi_max_deg(L, Hs, Tp, beta=beta, incidence_deg=inc)
    return {
        "site": name, "h_m": h, "grad": grad, "Hs_m": Hs, "Tp_s": Tp,
        "k_rad_m": k, "kh": kh, "L_m": L, "A": A, "B": B,
        "lambda_c_m": lc, "phi_max_deg": pm,
        "cycles": (dwell / Tp) if dwell else None,
        "G1_feels_bottom": kh <= 1.5,
        "G2_cutoff_geometry_needed_deg": pm,
        "G3_cycles_ok": (dwell / Tp >= 1.0) if dwell else None,
        "dh_over_h_indicator": spatial_indicator(kh, grad),
    }


def min_period_for_kh(h, kh_target=1.5):
    lo, hi = 3.0, 40.0
    for _ in range(300):
        m = 0.5 * (lo + hi)
        if k_of(m, h) * h > kh_target:
            lo = m
        else:
            hi = m
    return 0.5 * (lo + hi)


SITES = [
    # --- candidati del catalogo Umbra (GEBCO al punto rappresentativo) -----
    ("catalog", "Vandenberg CA (congelato)", 30.0, 8.4e-3, 2.0, 13.0, 22.5),
    ("catalog", "Santa Barbara CA",          22.0, 1.1e-2, 2.0, 14.0, 13.0),
    ("catalog", "Ventura / Oxnard CA",       13.0, 7.5e-3, 2.0, 14.0, 12.0),
    ("catalog", "Cape Canaveral FL",          2.0, 1.2e-3, 1.5, 11.0, 11.0),
    ("catalog", "Charleston SC",             15.0, 6.0e-3, 1.5, 11.0, 12.0),
    ("catalog", "Fukushima JP",              14.0, 1.4e-2, 2.0, 12.0, 12.0),
    ("catalog", "Lord Howe Is. (Tasman)",    39.0, 1.5e-3, 2.5, 13.0, 12.0),
    ("catalog", "Golfo del Messico 29N90W",  20.0, 1.0e-3, 1.0,  4.26, 17.2),
    # --- Italia (non presenti nel catalogo con dwell utile) ---------------
    ("italy", "Alto Adriatico / Venezia",    23.0, 4.1e-4, 4.0,  8.9, 22.0),
    ("italy", "Alto Adriatico / Venezia",    23.0, 4.1e-4, 5.0,  9.6, 22.0),
    ("italy", "Ravenna / Rimini",            13.0, 4.5e-4, 3.0,  8.0, 22.0),
    ("italy", "Ravenna / Rimini",            13.0, 4.5e-4, 5.0,  9.6, 22.0),
    ("italy", "W Sardegna / Oristano 41 m",  41.0, 2.3e-3, 6.7, 12.1, 22.0),
    ("italy", "W Sardegna / Oristano 20 m",  20.0, 2.3e-3, 4.0, 11.0, 22.0),
    ("italy", "W Sardegna, decadimento",     20.0, 2.3e-3, 2.5, 11.0, 22.0),
]


def main() -> int:
    out = []
    for grp, name, h, grad, Hs, Tp, dw in SITES:
        r = evaluate(name, h, grad, Hs, Tp, dw)
        r["group"] = grp
        r["T_min_for_kh_1p5_s"] = min_period_for_kh(h)
        out.append(r)

    hdr = (f"{'site':28s} {'h':>5} {'grad':>9} {'Hs':>4} {'Tp':>5} {'kh':>5} "
           f"{'A':>6} {'L':>6} {'lam_c':>6} {'phi_max':>7} {'cyc':>5} {'dh/h~':>6}")
    for grp, title in (("catalog", "CATALOGO UMBRA"), ("italy", "ITALIA")):
        print("=" * len(hdr)); print(title); print("=" * len(hdr)); print(hdr)
        for r in out:
            if r["group"] != grp:
                continue
            ok = "  <= usabile" if (r["G1_feels_bottom"] and r["phi_max_deg"] >= 15
                                    and (r["cycles"] or 0) >= 1) else ""
            print(f"{r['site']:28s} {r['h_m']:5.1f} {r['grad']:9.1e} {r['Hs_m']:4.1f} "
                  f"{r['Tp_s']:5.1f} {r['kh']:5.2f} {r['A']:6.1f} {r['L_m']:6.1f} "
                  f"{r['lambda_c_m']:6.1f} {r['phi_max_deg']:6.1f}d "
                  f"{(r['cycles'] or 0):5.2f} "
                  f"{100*min(r['dh_over_h_indicator'],9.99):5.1f}%{ok}")
        print()

    json.dump(out, open(sys.argv[1] if len(sys.argv) > 1
                        else "BLOCK19_SCREEN.json", "w"), indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
