#!/usr/bin/env python3
"""Block 26 — query per la SOLA misura della frequenza assoluta.

Obiettivo cambiato: si misura `omega` dalla fase del cross-spettro fra
sotto-aperture e la si confronta con la boa. **Batimetria e lunghezza d'onda
non interessano.**

Perche' questo semplifica davvero: `omega` e' l'invariante cinematico, e
**e' anche la stessa grandezza che misurano entrambi gli strumenti**.

Una boa ormeggiata campiona l'elevazione in un punto FISSO nel riferimento
terrestre: misura la frequenza assoluta `omega = sigma + k.U`. La fase del
cross-spettro fra sotto-look segue l'evoluzione del pattern nello STESSO
riferimento terrestre, quindi restituisce la stessa `omega`. **Una corrente
sposta le due misure in modo identico e si cancella nel confronto.** Inoltre
`omega` assoluta si conserva lungo un raggio in un mezzo stazionario, quindi
nemmeno un campo di corrente disomogeneo rompe il trasferimento boa->scena.

La corrente tornerebbe a contare solo per ricavare `sigma` e invertire la
dispersione — cioe' per la batimetria, che qui non interessa.

Cio' che conta davvero e' la PULIZIA del campo d'onda: pennacchi fluviali,
scie di navi, infrastrutture, e gradienti di corrente cosi' forti da rendere
diverso il mare alla boa e nella ROI. Le scie di navi in particolare sono
esattamente i «non-ocean-wave contributions at the same wavenumbers» che il
poster AGU 2020 di Romeiser indica come causa del bias di frequenza.
Per questo la coda e' ordinata per **pulizia**, poi vicinanza della boa,
poi dwell.

GATE OFFLINE gia' applicati in BLOCK27_QUERY_QUEUE.csv:
  O1  prodotto complesso pubblico (`*_size_bytes` non nullo, non il flag STAC)
  O2  **mare aperto**: `ocean_fraction >= 0.99` oppure nessuna costa
      nell'impronta
  O3  una stazione con spettro direzionale entro 50 km

GATE CHE RICHIEDONO LA BOA, applicati qui:
  B1  **allineamento onda-range** |differenza assiale| <= AXIAL_MAX_DEG
      (criterio primario: e' quello che minimizza cut-off e velocity bunching)
  B2  **ripidita'** H/L >= STEEPNESS_MIN
      La modulazione di tilt scala con la pendenza dell'onda, non con Hs. Uno
      swell da 0.8 m e 15 s ha H/L = 0.002; un mare di vento da 1.0 m e 4.3 s
      ha 0.036, cioe' 16 volte tanto. Per l'imaging conta la seconda.
  B3  **lobo isolabile**: almeno MIN_WAVELENGTHS_IN_ROI lunghezze d'onda nella
      ROI. Serve solo a separare il lobo dal DC, non a misurare `k` con
      precisione: per questo 3 e non 10.
  B4  **rotazione di fase** utilizzabile sulla base temporale 0.65*dwell.

Soglie DESCRITTIVE, non calibrate.

Riusa `umbra_sar.reference_recovery` (Block17/18). Non scarica prodotti SAR.

Uso:  python run_block27_frequency_query.py BLOCK27_QUERY_QUEUE.csv <outdir>
"""
from __future__ import annotations
import csv, json, math, sys, time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from umbra_sar.reference_recovery import (          # noqa: E402
    HTTPBudget, fetch_limited, parse_dds_dimensions, parse_ascii_vector,
    nearest_time_index, normalize_payload, spectrum_metrics, VARIABLES,
)

G = 9.80665
F_BASE = 0.65
AXIAL_MAX_DEG = 35.0
STEEPNESS_MIN = 0.010
MIN_WAVELENGTHS_IN_ROI = 3.0
PHASE_MIN_DEG, PHASE_MAX_DEG = 45.0, 1080.0
MAX_TIME_OFFSET_S = 3600.0
BASE = "https://dods.ndbc.noaa.gov/thredds/dodsC/data/swden"


def axial_difference_deg(a, b):
    return abs(((a - b + 90.0) % 180.0) - 90.0)


def wavenumber(T, h):
    w = 2.0 * math.pi / T
    k = w * w / G
    for _ in range(300):
        k = w * w / (G * math.tanh(k * h))
    return k


def celerity(T, h):
    return (2.0 * math.pi / T) / wavenumber(T, h)


def refract_direction(prop_deg, T, h_buoy, h_roi, contour_normal_deg):
    """Snell su isobate rettilinee: sin(theta)/c = cost.

    `theta` e' l'angolo fra la direzione di propagazione e la normale alle
    isobate. Serve perche' il gate di allineamento vuole la direzione NELLA
    ROI, non alla boa: su 7-9 km fra quote diverse la rifrazione cambia la
    direzione di gradi, mentre `omega` resta invariata (si conserva lungo il
    raggio) e non ha bisogno di correzione.

    `contour_normal_deg` e' una **assunzione dichiarata** sull'orientamento
    locale delle isobate. Se non e' nota si restituisce la direzione non
    corretta e si segnala.
    """
    if contour_normal_deg is None or h_buoy is None or h_roi is None:
        return prop_deg, None, "no_contour_normal_assumed"
    th_b = ((prop_deg - contour_normal_deg + 180.0) % 360.0) - 180.0
    s = math.sin(math.radians(th_b)) * celerity(T, h_roi) / celerity(T, h_buoy)
    if abs(s) > 1.0:
        return prop_deg, None, "total_reflection_snell_invalid"
    th_r = math.degrees(math.asin(s))
    return (contour_normal_deg + th_r) % 360.0, (th_r - th_b), "refracted"


def epoch_of(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).replace(
        tzinfo=timezone.utc).timestamp()


def station_index(station, budget, cache):
    if station in cache:
        return cache[station]
    root = f"{BASE}/{station}/{station}w9999.nc"
    dds = fetch_limited(root + ".dds", budget, purpose="dds").decode("utf-8", "replace")
    das = fetch_limited(root + ".das", budget, purpose="das").decode("utf-8", "replace")
    tv = fetch_limited(root + ".ascii?time", budget, purpose="time").decode("utf-8", "replace")
    cache[station] = (root, parse_dds_dimensions(dds), das, parse_ascii_vector(tv, "time"))
    return cache[station]


def query(row, budget, cache):
    out = {"status": "?"}
    try:
        root, dims, das, epochs = station_index(row["station_id"], budget, cache)
    except Exception as exc:                                   # noqa: BLE001
        out["status"] = f"station_index_failed: {exc}"; return out
    i = nearest_time_index(epochs, epoch_of(row["datetime_utc"]))
    off = float(epochs[i] - epoch_of(row["datetime_utc"]))
    out["observation_offset_s"] = off
    if abs(off) > MAX_TIME_OFFSET_S:
        out["status"] = "outside_time_tolerance"; return out
    nf = dims.get("frequency")
    if not nf:
        out["status"] = "unknown_frequency_dimension"; return out
    sel = ",".join(f"{v}[{i}:1:{i}][0:1:{nf-1}][0:1:0][0:1:0]" for v in VARIABLES)
    url = f"{root}.ascii?frequency,{sel}"
    try:
        txt = fetch_limited(url, budget, purpose="spectrum",
                            acquisition_key=row["acquisition_key"]).decode("utf-8", "replace")
    except Exception as exc:                                   # noqa: BLE001
        out["status"] = f"spectrum_fetch_failed: {exc}"; return out
    out.update(spectrum_metrics(normalize_payload(txt, das,
                                                  observation_epoch_s=float(epochs[i]))))
    out["source_url"] = url; out["status"] = "ok"
    return out


def gates(row, ref):
    d = dict(row)
    d.update({f"ref_{k}": v for k, v in ref.items()})
    if ref.get("status") != "ok":
        d["verdict"] = "NO_REFERENCE"; return d
    Hm0 = ref.get("Hm0_m") or ref.get("hm0_m")
    Tp = ref.get("peak_period_s") or ref.get("Tp_s")
    prop = ref.get("propagation_to_deg") or ref.get("peak_propagation_to_deg")
    if None in (Hm0, Tp, prop):
        d["verdict"] = "INCOMPLETE_METRICS"; return d

    Tp = float(Tp); Hm0 = float(Hm0)
    L = G * Tp * Tp / (2.0 * math.pi)
    roi = float(row["roi_m"]); dwell = float(row["duration_s"])
    d["L_deep_m"] = L
    d["wavelengths_in_roi"] = roi / L
    d["steepness_H_over_L"] = Hm0 / L
    d["omega_buoy_rad_s"] = 2.0 * math.pi / Tp
    d["phase_rotation_deg"] = math.degrees((2 * math.pi / Tp) * F_BASE * dwell)
    # la direzione va portata alla quota della ROI prima del gate
    hb = row.get("buoy_depth_m"); hr = row.get("gebco_depth_m")
    cn = row.get("contour_normal_deg")
    prop_roi, dtheta, how = refract_direction(
        float(prop), Tp,
        float(hb) if hb not in (None, "") else None,
        abs(float(hr)) if hr not in (None, "") else None,
        float(cn) if cn not in (None, "") else None)
    d["propagation_at_buoy_deg"] = float(prop)
    d["propagation_at_roi_deg"] = prop_roi
    d["refraction_delta_deg"] = dtheta
    d["refraction_status"] = how
    d["axial_difference_deg"] = axial_difference_deg(
        float(row["local_range_axis_deg"]), prop_roi)
    d["axial_difference_unrefracted_deg"] = axial_difference_deg(
        float(row["local_range_axis_deg"]), float(prop))

    fails = []
    if d["axial_difference_deg"] > AXIAL_MAX_DEG:
        fails.append(f"axial={d['axial_difference_deg']:.1f}")
    if d["steepness_H_over_L"] < STEEPNESS_MIN:
        fails.append(f"steep={d['steepness_H_over_L']:.4f}")
    if d["wavelengths_in_roi"] < MIN_WAVELENGTHS_IN_ROI:
        fails.append(f"lambda_in_roi={d['wavelengths_in_roi']:.1f}")
    if not (PHASE_MIN_DEG <= d["phase_rotation_deg"] <= PHASE_MAX_DEG):
        fails.append(f"dphi={d['phase_rotation_deg']:.0f}")
    d["gate_failures"] = ";".join(fails)
    d["verdict"] = "CANDIDATE" if not fails else "REJECTED"
    return d


def main():
    q = Path(sys.argv[1]); outdir = Path(sys.argv[2] if len(sys.argv) > 2 else ".")
    outdir.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader(open(q)))
    budget = HTTPBudget(maximum_transactions=150, maximum_total_bytes=100 * 1024 * 1024,
                        maximum_response_bytes=10 * 1024 * 1024)
    cache, res = {}, []
    for n, row in enumerate(rows, 1):
        r = gates(row, query(row, budget, cache))
        res.append(r)
        print(f"[{n}/{len(rows)}] {row['collect_name']:32s} {r['verdict']:12s} "
              f"{r.get('gate_failures','')}")
        time.sleep(0.3)
    keys = sorted({k for r in res for k in r})
    with open(outdir / "BLOCK27_FREQUENCY_GATE.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys); w.writeheader()
        for r in res:
            w.writerow(r)
    cands = [r for r in res if r["verdict"] == "CANDIDATE"]
    cands.sort(key=lambda r: (int(r.get("cleanliness_rank", 9)),
                              r["axial_difference_deg"], -r["steepness_H_over_L"]))
    json.dump({"n_queue": len(rows), "n_candidates": len(cands),
               "axial_max_deg": AXIAL_MAX_DEG, "steepness_min": STEEPNESS_MIN,
               "min_wavelengths_in_roi": MIN_WAVELENGTHS_IN_ROI,
               "thresholds_are_descriptive_not_calibrated": True,
               "candidates": cands},
              open(outdir / "BLOCK27_SUMMARY.json", "w"), indent=2, default=str)
    print(f"\ncandidati: {len(cands)} / {len(rows)}")
    for c in cands[:12]:
        print(f"  {c['collect_name']:32s} axial={c['axial_difference_deg']:5.1f} "
              f"steep={c['steepness_H_over_L']:.4f} T={c['ref_peak_period_s']} "
              f"lam/ROI={c['wavelengths_in_roi']:.1f} {c['min_complex_GB']} GB "
              f"[{c.get('site','?')}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
