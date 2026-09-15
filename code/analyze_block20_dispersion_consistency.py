#!/usr/bin/env python3
"""Block 20 — test di consistenza dispersiva interno.

LA DOMANDA: le coppie (k, omega) misurate bin per bin dalla fase del
cross-spettro fra sotto-look giacciono su UNA shell di dispersione?

E' un test **interno**: nessuna boa, nessun DEM, nessun riferimento esterno
entra nel fit. Se la fase misurata e' cinematica ondosa reale, omega deve
crescere con k secondo sqrt(g k tanh(k h)) con una sola h per tutta la patch.
Se e' rumore, o un pattern statico, o una traslazione rigida dell'immagine,
la firma e' diversa e distinguibile.

E' il test che Romeiser & Graber non hanno mai pubblicato: in undici pagine
fra il 2018 e il 2021 adattano la shell come STIMATORE e non riportano mai un
residuo. Qui la shell e' usata come TEST e il residuo e' il risultato.

Ingresso: BLOCK15B_BINS.csv (artefatto congelato Block15b, per-bin
`k_rad_m` e `s_phi_A`). Nessun dato SAR riletto, nessuna nuova formazione.

Modelli confrontati (AIC, stessi bin):
  M0  omega = cost                        1 par   rumore / pattern statico
  M1  omega = k U                         1 par   traslazione rigida / advezione
  M2  omega = sqrt(g k tanh(k h))         1 par   dispersione, h libera
  M3  omega = sqrt(g k tanh(k h)) + k U   2 par   dispersione + corrente
  M4  omega = sqrt(g k tanh(k h0)) + k U  1 par   h fissata al vero, U libera
  M5  omega = sqrt(g k tanh(k h0))        0 par   predizione pura al vero h

Poi: che FORMA ha lo scarto residuo? moltiplicativo (scala su omega o
sull'asse tempi) oppure additivo in k (advezione)?
"""
from __future__ import annotations
import csv, json, math, sys
import numpy as np
from scipy.optimize import least_squares

G = 9.80665


def load_bins(path, r2_min=0.95, power_min=0.05):
    out = []
    for r in csv.DictReader(open(path)):
        if str(r.get("A_valid", "")).strip().lower() != "true":
            continue
        try:
            k = float(r["k_rad_m"]); w = float(r["s_phi_A"])
            r2 = float(r["A_R2"]); p = float(r["relative_power"])
        except (TypeError, ValueError, KeyError):
            continue
        if r2 < r2_min or p < power_min:
            continue
        # i lobi coniugati portano omega di segno opposto: si lavora sul modulo
        out.append((k, abs(w), r2, p))
    return out


def fit_all(k, w, h_true):
    n = len(k)
    aic = lambda ss, p: n * math.log(ss / n) + 2 * p
    res = {}

    ss = float(np.sum((w - w.mean()) ** 2))
    res["M0"] = dict(ss=ss, p=1, aic=aic(ss, 1), par=f"c={w.mean():.4f} rad/s")

    U = float(np.sum(k * w) / np.sum(k * k))
    ss = float(np.sum((w - k * U) ** 2))
    res["M1"] = dict(ss=ss, p=1, aic=aic(ss, 1), par=f"U={U:.3f} m/s")

    r = least_squares(lambda p: np.sqrt(G * k * np.tanh(k * abs(p[0]))) - w, [10.0])
    ss = float(np.sum(r.fun ** 2))
    res["M2"] = dict(ss=ss, p=1, aic=aic(ss, 1), par=f"h={abs(r.x[0]):.2f} m")

    r3 = least_squares(lambda p: np.sqrt(G * k * np.tanh(k * abs(p[0]))) + k * p[1] - w,
                       [10.0, 0.0])
    ss = float(np.sum(r3.fun ** 2))
    res["M3"] = dict(ss=ss, p=2, aic=aic(ss, 2),
                     par=f"h={abs(r3.x[0]):.2f} m, U={r3.x[1]:+.3f} m/s")

    base = np.sqrt(G * k * np.tanh(k * h_true))
    U4 = float(np.sum(k * (w - base)) / np.sum(k * k))
    ss = float(np.sum((w - base - k * U4) ** 2))
    res["M4"] = dict(ss=ss, p=1, aic=aic(ss, 1), par=f"U={U4:+.3f} m/s a h={h_true} m")

    ss = float(np.sum((w - base) ** 2))
    res["M5"] = dict(ss=ss, p=0, aic=aic(ss, 1e-9), par=f"h={h_true} m, U=0")
    return res


def bias_shape(k, w, depths):
    rows = []
    for h in depths:
        pred = np.sqrt(G * k * np.tanh(k * h))
        ratio = w / pred
        sl, ic = np.polyfit(k, ratio, 1)
        resid = ratio - (sl * k + ic)
        se = math.sqrt(np.sum(resid ** 2) / (len(k) - 2) / np.sum((k - k.mean()) ** 2))
        rows.append(dict(h_m=h, ratio_mean=float(ratio.mean()),
                         ratio_median=float(np.median(ratio)),
                         cv=float(ratio.std(ddof=1) / ratio.mean()),
                         slope_vs_k=float(sl), t_slope=float(sl / se)))
    return rows


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else "BLOCK15B_BINS.csv"
    h_true = float(sys.argv[2]) if len(sys.argv) > 2 else 16.4
    data = load_bins(path)
    k = np.array([d[0] for d in data]); w = np.array([d[1] for d in data])
    report = {"n_bins": len(k), "k_min": float(k.min()), "k_max": float(k.max()),
              "k_span_factor": float(k.max() / k.min()),
              "L_min_m": float(2 * math.pi / k.max()),
              "L_max_m": float(2 * math.pi / k.min()),
              "h_true_assumed_m": h_true}

    res = fit_all(k, w, h_true)
    best = min(res, key=lambda m: res[m]["aic"])
    for m in res:
        res[m]["dAIC"] = res[m]["aic"] - res[best]["aic"]
    report["models"] = res
    report["best"] = best
    report["rigid_translation_rejected_by_dAIC"] = res["M1"]["dAIC"] - res["M2"]["dAIC"]

    report["bias_shape"] = bias_shape(k, w, [10.1, 13.0, h_true, 20.0, 23.0, 30.0])
    pred = np.sqrt(G * k * np.tanh(k * h_true))
    ratio = w / pred
    mult_ss = float(np.sum((w - ratio.mean() * pred) ** 2))
    d = w - pred
    sl, ic = np.polyfit(k, d, 1)
    add_ss = float(np.sum((d - sl * k - ic) ** 2))
    n = len(k)
    report["bias_multiplicative_vs_additive"] = {
        "multiplicative_ss": mult_ss, "multiplicative_aic": n*math.log(mult_ss/n)+2,
        "additive_in_k_ss": add_ss, "additive_in_k_aic": n*math.log(add_ss/n)+4,
        "verdict": "multiplicative" if (n*math.log(mult_ss/n)+2) < (n*math.log(add_ss/n)+4)
                   else "additive",
    }

    print(json.dumps(report, indent=2))
    json.dump(report, open("BLOCK20_DISPERSION_CONSISTENCY.json", "w"), indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
