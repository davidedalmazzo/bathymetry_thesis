#!/usr/bin/env python3
"""Block 25 — gate finale sullo stato di mare per la coda Block25.

I tre gate offline sono gia' applicati e hanno prodotto BLOCK25_QUERY_QUEUE.csv:
  G1  prodotto complesso PUBBLICO  (sicd_size_bytes o cphd_size_bytes non nulli,
      non il flag has_* che viene dalla dichiarazione STAC — vedi Block23/24)
  G2  stazione entro 10 km e ROI >= 1000 m
  G3  finestra congiunta: il periodo risolvibile dalla ROI (>=10 lunghezze
      d'onda, cioe' dL/L <= 0.1) da' ancora una rotazione di fase utilizzabile
      sulla base temporale 0.65*dwell

Restano due gate che richiedono la boa, ed e' quello che fa questo script:
  G4  Hm0 >= HM0_MIN                 energia del mare (Block24: il gate mancante)
  G5  |differenza assiale| <= 35 deg  allineamento onda-range

Soglie DESCRITTIVE, non calibrate. HM0_MIN = 1.5 m e' ancorato al fatto che
Vandenberg, con Hm0 = 1.99 m, era gia' marginale (Block15K Livello 2).

Riusa `umbra_sar.reference_recovery` del Block17/18: stessa politica di
completezza direzionale congiunta, stessa gestione dei missing per variabile,
stesso budget HTTP. Una sola lettura del vettore `time` per stazione.

NON scarica alcun prodotto SAR e non raccomanda download.

Uso:
  python run_block25_reference_gate.py BLOCK25_QUERY_QUEUE.csv <outdir>
"""
from __future__ import annotations
import csv, json, math, sys, time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from umbra_sar.reference_recovery import (          # noqa: E402
    HTTPBudget, fetch_limited, parse_dds_dimensions, parse_ascii_vector,
    variable_attributes, nearest_time_index, normalize_payload, spectrum_metrics,
    VARIABLES,
)

G = 9.80665
F_BASE = 0.65
HM0_MIN_M = 1.5           # descrittiva, non calibrata
AXIAL_MAX_DEG = 35.0
MAX_TIME_OFFSET_S = 3600.0
BASE = "https://dods.ndbc.noaa.gov/thredds/dodsC/data/swden"


def axial_difference_deg(a: float, b: float) -> float:
    return abs(((a - b + 90.0) % 180.0) - 90.0)


def deep_wavelength(T: float) -> float:
    return G * T * T / (2.0 * math.pi)


def epoch_of(iso: str) -> float:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).replace(
        tzinfo=timezone.utc).timestamp()


def station_index(station: str, budget: HTTPBudget, cache: dict):
    """Una sola lettura di dds/das/time per stazione."""
    if station in cache:
        return cache[station]
    root = f"{BASE}/{station}/{station}w9999.nc"
    dds = fetch_limited(root + ".dds", budget, purpose="dds").decode("utf-8", "replace")
    das = fetch_limited(root + ".das", budget, purpose="das").decode("utf-8", "replace")
    tv = fetch_limited(root + ".ascii?time", budget, purpose="time").decode("utf-8", "replace")
    dims = parse_dds_dimensions(dds)
    epochs = parse_ascii_vector(tv, "time")
    cache[station] = (root, dims, das, epochs)
    return cache[station]


def query_scene(row, budget: HTTPBudget, cache: dict) -> dict:
    st = row["station_id"]
    out = {"collect_name": row["collect_name"], "station_id": st,
           "station_km": float(row["station_km"])}
    try:
        root, dims, das, epochs = station_index(st, budget, cache)
    except Exception as exc:                                    # noqa: BLE001
        out["status"] = f"station_index_failed: {exc}"
        return out

    target = epoch_of(row["datetime_utc"])
    i = nearest_time_index(epochs, target)
    offset = float(epochs[i] - target)
    out["observation_offset_s"] = offset
    if abs(offset) > MAX_TIME_OFFSET_S:
        out["status"] = "outside_time_tolerance"
        return out

    nf = dims.get("frequency") or dims.get("spectral_wave_density_frequency")
    if not nf:
        out["status"] = "unknown_frequency_dimension"
        return out
    sel = ",".join(f"{v}[{i}:1:{i}][0:1:{nf-1}][0:1:0][0:1:0]" for v in VARIABLES)
    url = f"{root}.ascii?frequency,{sel}"
    try:
        payload = fetch_limited(url, budget, purpose="spectrum",
                                acquisition_key=row["acquisition_key"]).decode("utf-8", "replace")
    except Exception as exc:                                    # noqa: BLE001
        out["status"] = f"spectrum_fetch_failed: {exc}"
        return out

    norm = normalize_payload(payload, das, observation_epoch_s=float(epochs[i]))
    met = spectrum_metrics(norm)
    out.update({k: met.get(k) for k in met})
    out["source_url"] = url
    out["status"] = "ok"
    return out


def apply_gates(row, ref) -> dict:
    d = dict(row)
    d.update({f"ref_{k}": v for k, v in ref.items() if k not in ("collect_name",)})
    if ref.get("status") != "ok":
        d["verdict"] = "NO_REFERENCE"
        return d

    Hm0 = ref.get("Hm0_m") or ref.get("hm0_m")
    Tp = ref.get("peak_period_s") or ref.get("Tp_s")
    prop = ref.get("propagation_to_deg") or ref.get("peak_propagation_to_deg")
    if None in (Hm0, Tp, prop):
        d["verdict"] = "INCOMPLETE_METRICS"
        return d

    L = deep_wavelength(float(Tp))
    roi = float(row["roi_m"])
    dwell = float(row["duration_s"])
    d["L_deep_m"] = L
    d["wavelengths_in_roi"] = roi / L
    d["dL_over_L"] = L / roi
    d["phase_rotation_deg"] = math.degrees((2 * math.pi / float(Tp)) * F_BASE * dwell)
    rax = float(row["local_range_axis_deg"])
    d["axial_difference_deg"] = axial_difference_deg(rax, float(prop))
    d["steepness_H_over_L"] = float(Hm0) / L

    fails = []
    if float(Hm0) < HM0_MIN_M:
        fails.append(f"Hm0={float(Hm0):.2f}<{HM0_MIN_M}")
    if d["dL_over_L"] > 0.10:
        fails.append(f"dL/L={d['dL_over_L']:.3f}>0.10")
    if d["axial_difference_deg"] > AXIAL_MAX_DEG:
        fails.append(f"axial={d['axial_difference_deg']:.1f}>{AXIAL_MAX_DEG}")
    if not (45.0 <= d["phase_rotation_deg"] <= 720.0):
        fails.append(f"dphi={d['phase_rotation_deg']:.0f}")
    d["gate_failures"] = ";".join(fails)
    d["verdict"] = "CANDIDATE" if not fails else "REJECTED"
    return d


def main() -> int:
    queue = Path(sys.argv[1]); outdir = Path(sys.argv[2] if len(sys.argv) > 2 else ".")
    outdir.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader(open(queue)))
    budget = HTTPBudget(maximum_transactions=250, maximum_total_bytes=150 * 1024 * 1024,
                        maximum_response_bytes=10 * 1024 * 1024)
    cache: dict = {}
    results = []
    for n, row in enumerate(rows, 1):
        ref = query_scene(row, budget, cache)
        results.append(apply_gates(row, ref))
        print(f"[{n}/{len(rows)}] {row['collect_name']:32s} {results[-1]['verdict']}"
              f"  {results[-1].get('gate_failures','')}")
        time.sleep(0.3)

    keys = sorted({k for r in results for k in r})
    with open(outdir / "BLOCK25_REFERENCE_GATE.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys); w.writeheader()
        for r in results:
            w.writerow(r)
    cands = [r for r in results if r.get("verdict") == "CANDIDATE"]
    cands.sort(key=lambda r: (r.get("axial_difference_deg", 99), r.get("min_complex_GB", 99)))
    json.dump({"n_queue": len(rows), "n_candidates": len(cands),
               "hm0_min_m": HM0_MIN_M, "axial_max_deg": AXIAL_MAX_DEG,
               "thresholds_are_descriptive_not_calibrated": True,
               "candidates": cands[:20]},
              open(outdir / "BLOCK25_SUMMARY.json", "w"), indent=2, default=str)
    print(f"\ncandidati: {len(cands)} / {len(rows)}")
    for c in cands[:10]:
        print(f"  {c['collect_name']:32s} Hm0={c['ref_Hm0_m']} "
              f"axial={c['axial_difference_deg']:.1f} dL/L={c['dL_over_L']:.3f} "
              f"{c['min_complex_GB']} GB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
