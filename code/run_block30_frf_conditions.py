#!/usr/bin/env python3
"""
Block 30 - Condizioni met-oceaniche FRF (Duck, NC) agli istanti delle 18
acquisizioni COSMO-SkyMed I generazione Spotlight-2 trovate in archivio.

Da eseguire in locale (il proxy della sessione cloud blocca chldata.erdc.dren.mil).
Ambiente: .venv-umbra-thesis. Solo lettura, nessun dato radar toccato.

Uso (dalla radice del repo):
  python code/run_block30_frf_conditions.py --smoke
  python code/run_block30_frf_conditions.py --months 202110 --gauges waverider-17m
  python code/run_block30_frf_conditions.py

Uscita in Block30_duck_csk_preflight/:
  BLOCK30_FRF_CONDITIONS.csv   una riga per scena x strumento
  BLOCK30_GATE.csv             gate combinato geometria + stato di mare

Non applica correzioni: riporta cio' che e' misurato, cio' che e' calcolato,
e lascia esplicito cio' che resta ipotesi.
"""
from __future__ import annotations
import csv, math, re, sys, time, urllib.request, urllib.error, hashlib, json
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://chldata.erdc.dren.mil/thredds/dodsC/frf/oceanography/waves"
GAUGES = ["waverider-17m", "awac-11m", "awac-8m", "8m-array", "waverider-26m"]
VARS = ["waveHs", "waveTp", "waveTm", "waveMeanDirection",
        "wavePeakDirectionPeakFrequency", "directionalPeakSpread"]

SCENES_CSV = Path("Block30_duck_csk_preflight/BLOCK30_CSK_DUCK_SCENES.csv")
OUTDIR     = Path("Block30_duck_csk_preflight")

G = 9.81
OFFSHORE_DEG = 70.0        # asse cross-shore FRF, STIMATO dalle posizioni boe: da confermare
MAX_REQUESTS = 120
MAX_BYTES    = 40 * 1024 * 1024

_budget = {"n": 0, "b": 0}
HTTP_CACHE = OUTDIR / "http_cache"


def fetch(url: str, timeout: int = 90) -> str:
    HTTP_CACHE.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(url.encode()).hexdigest()
    payload = HTTP_CACHE / (key + ".txt")
    if payload.exists():
        return payload.read_text(encoding="utf-8")
    if _budget["n"] >= MAX_REQUESTS:
        raise RuntimeError("budget richieste esaurito")
    req = urllib.request.Request(url, headers={"User-Agent": "polimi-thesis-block30"})
    _budget["n"] += 1
    with (HTTP_CACHE / "requests.jsonl").open("a", encoding="utf-8") as log:
        log.write(json.dumps({"url": url, "status": "started", "utc": datetime.now(timezone.utc).isoformat()}) + "\n")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read(MAX_BYTES - _budget["b"] + 1)
    except Exception as exc:
        with (HTTP_CACHE / "requests.jsonl").open("a", encoding="utf-8") as log:
            log.write(json.dumps({"url": url, "error": str(exc)}) + "\n")
        raise
    _budget["b"] += len(raw)
    if _budget["b"] > MAX_BYTES:
        raise RuntimeError("budget byte esaurito")
    text = raw.decode("utf-8", "replace")
    payload.write_text(text, encoding="utf-8")
    with (HTTP_CACHE / "requests.jsonl").open("a", encoding="utf-8") as log:
        log.write(json.dumps({"url": url, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}) + "\n")
    return text


def dap_url(gauge: str, yyyymm: str, suffix: str) -> str:
    return f"{BASE}/{gauge}/{yyyymm[:4]}/FRF-ocean_waves_{gauge}_{yyyymm}.nc{suffix}"


def parse_ascii_vector(text: str, name: str):
    """Estrae il vettore numerico di `name` da una risposta DAP .ascii.

    Formato atteso (THREDDS DAP2):
        Dataset { ... } nomefile;
        ---------------------------------------------
        time[1472]
        1.6330464E9, 1.6330482E9, ...
    """
    lines = text.splitlines()
    # salta l'intestazione fino alla riga di trattini
    start = 0
    for i, ln in enumerate(lines):
        if set(ln.strip()) == {"-"} and len(ln.strip()) > 10:
            start = i + 1
            break
    hdr = re.compile(r"^" + re.escape(name) + r"(\[[0-9]+\])*\s*$")
    any_hdr = re.compile(r"^[A-Za-z_]\w*(\[[0-9]+\])*\s*$")
    vals, capture = [], False
    for ln in lines[start:]:
        t = ln.strip()
        if not t:
            if capture:
                break
            continue
        if hdr.match(t):
            capture = True
            continue
        if any_hdr.match(t):
            if capture:
                break
            continue
        if capture:
            for tok in t.split(","):
                tok = tok.strip()
                if not tok:
                    continue
                try:
                    vals.append(float(tok))
                except ValueError:
                    pass
    if not vals:
        raise RuntimeError(f"nessun valore estratto per {name!r}")
    return vals


def time_units(gauge: str, yyyymm: str) -> str:
    das = fetch(dap_url(gauge, yyyymm, ".das"))
    m = re.search(r"time\s*\{[^}]*?units\s+\"([^\"]+)\"", das, re.S)
    if not m:
        raise RuntimeError(f"units di time non trovate per {gauge} {yyyymm}")
    return m.group(1)


def epoch_from_units(units: str) -> float:
    m = re.match(r"\s*seconds since\s+(.+)", units)
    if not m:
        raise RuntimeError(f"unita' di tempo non gestite: {units!r}")
    s = m.group(1).strip().replace("Z", "").replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:19], fmt).replace(tzinfo=timezone.utc).timestamp()
        except ValueError:
            continue
    raise RuntimeError(f"epoca non interpretabile: {s!r}")


def load_month(gauge: str, yyyymm: str):
    """Ritorna (times_epoch, {var: values}) oppure None se il file non esiste."""
    if gauge == "awac-8m":
        catalog = fetch("https://chldata.erdc.dren.mil/thredds/catalog/frf/oceanography/waves/awac-8m/catalog.xml")
        if f'{yyyymm[:4]}/catalog.xml' not in catalog:
            return None
    try:
        das = fetch(dap_url(gauge, yyyymm, ".das"))
        match = re.search(r'time\s*\{[^}]*?units\s+"([^"]+)"', das, re.S)
        if not match:
            raise RuntimeError("time units missing")
        units = match.group(1)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise
    ep = epoch_from_units(units)
    available = [v for v in VARS if re.search(r"\b" + v + r"\s*\{", das)]
    txt = fetch(dap_url(gauge, yyyymm, ".ascii?" + ",".join(["time"] + available)))
    t = [ep + v for v in parse_ascii_vector(txt, "time")]
    data = {}
    for v in VARS:
        try:
            if v not in available:
                data[v] = None
                continue
            vals = parse_ascii_vector(txt, v)
            block = re.search(r"\b" + v + r"\s*\{([^}]*)\}", das).group(1)
            fill = re.search(r"_FillValue\s+([^;]+);", block)
            fv = float(fill.group(1)) if fill else None
            vals = [x if math.isfinite(x) and x != fv and x > -900 else float("nan") for x in vals]
            data[v] = vals if len(vals) == len(t) else None
        except urllib.error.HTTPError:
            data[v] = None
    return t, data


def celerity(T: float, h: float) -> float:
    w = 2 * math.pi / T
    k = w * w / G
    for _ in range(200):
        f = G * k * math.tanh(k * h) - w * w
        df = G * math.tanh(k * h) + G * k * h / math.cosh(k * h) ** 2
        k -= f / df
    return w / k, k


def main(argv=None) -> int:
    global GAUGES, SCENES_CSV
    import argparse
    ap = argparse.ArgumentParser(description="Condizioni FRF agli istanti delle scene CSK")
    ap.add_argument("--months", nargs="*", default=None,
                    help="limita ai mesi YYYYMM indicati (default: tutti quelli delle scene)")
    ap.add_argument("--gauges", nargs="*", default=None,
                    help="limita agli strumenti indicati (default: %s)" % ",".join(GAUGES))
    ap.add_argument("--smoke", action="store_true",
                    help="prova rapida: solo waverider-17m sul primo mese, stampa e basta")
    ap.add_argument("scenes", nargs="?", default=str(SCENES_CSV),
                    help="CSV delle scene (default: %(default)s)")
    ap.add_argument("outdir", nargs="?", default=str(OUTDIR),
                    help="directory di uscita (default: %(default)s)")
    a = ap.parse_args(argv)

    if a.gauges:
        GAUGES = list(a.gauges)
    SCENES_CSV = Path(a.scenes)
    outdir = Path(a.outdir); outdir.mkdir(parents=True, exist_ok=True)
    out_cond = outdir / "BLOCK30_FRF_CONDITIONS.csv"
    out_gate = outdir / "BLOCK30_GATE.csv"

    if not SCENES_CSV.exists():
        print(f"manca {SCENES_CSV}", file=sys.stderr)
        return 1
    scenes = list(csv.DictReader(SCENES_CSV.open()))
    months = sorted({s["acq_utc"][:7].replace("-", "") for s in scenes})
    if a.months:
        months = [m for m in months if m in set(a.months)]
    if a.smoke:
        GAUGES = ["waverider-17m"]
        months = months[:1]
        print(f"SMOKE TEST: {GAUGES[0]} su {months[0]}")
        m = load_month(GAUGES[0], months[0])
        if not m:
            print("  file assente")
            return 2
        t, data = m
        print(f"  {len(t)} istanti, dal {datetime.fromtimestamp(t[0], timezone.utc)} "
              f"al {datetime.fromtimestamp(t[-1], timezone.utc)}")
        for v in VARS:
            vals = data.get(v)
            print(f"  {v:34s} {'n/d' if vals is None else f'{len(vals)} valori, primo={vals[0]}'}")
        print(f"richieste: {_budget['n']}, byte: {_budget['b']/1e6:.1f} MB")
        return 0
    print(f"{len(scenes)} scene, {len(months)} mesi: {months}")

    cache = {}
    for g in GAUGES:
        for ym in months:
            try:
                cache[(g, ym)] = load_month(g, ym)
                ok = cache[(g, ym)] is not None
                print(f"  {g} {ym}: {'ok' if ok else 'assente'}")
            except Exception as e:
                cache[(g, ym)] = None
                print(f"  {g} {ym}: errore {e}")
            time.sleep(0.5)

    cond_rows, gate_rows = [], []
    for s in scenes:
        t_acq = datetime.strptime(s["acq_utc"], "%Y-%m-%d %H:%M:%S") \
                        .replace(tzinfo=timezone.utc).timestamp()
        ym = s["acq_utc"][:7].replace("-", "")
        best = None
        for g in GAUGES:
            m = cache.get((g, ym))
            if not m:
                continue
            t, data = m
            if not t:
                continue
            i = min(range(len(t)), key=lambda j: abs(t[j] - t_acq))
            dt_min = (t[i] - t_acq) / 60.0
            row = {"acq_utc": s["acq_utc"], "product_id": s["product_id"], "gauge": g,
                   "dt_min": round(dt_min, 1)}
            for v in VARS:
                vals = data.get(v)
                row[v] = (None if vals is None or not (-1e30 < vals[i] < 1e30) else round(vals[i], 3))
            cond_rows.append(row)
            if g == "waverider-17m":
                best = row

        nearest = min((r for r in cond_rows if r["product_id"] == s["product_id"]),
                      key=lambda r: abs(r["dt_min"]), default=None)
        if best and best.get("waveTp") and best["waveTp"] > 0 and best.get("waveHs") is not None and best.get("waveMeanDirection") is not None:
            Tp = best["waveTp"]; Hs = best["waveHs"]
            mwd = best["waveMeanDirection"]          # direzione DA CUI viene, conv. FRF da verificare
            kdir = (mwd + 180.0) % 360.0             # direzione di propagazione
            rng = float(s["range_dir_deg"])
            phi = min(abs(((kdir - rng + 180) % 360) - 180),
                      180 - abs(((kdir - rng + 180) % 360) - 180))
            c17, k17 = celerity(Tp, 17.8)
            L = 2 * math.pi / k17
            L_az = L / max(math.sin(math.radians(phi)), 1e-3)
            beta = float(s["beta_s"])
            sig_u = 0.25 * Hs * (2 * math.pi / Tp) if Hs else None
            sig_ur = sig_u * math.cos(math.radians(float(s["inc_deg"]))) if sig_u else None
            lam_c = 2 * math.pi * beta * sig_ur if sig_ur else None
            w = 2 * math.pi / Tp
            dphi = math.degrees(w * float(s["T_base_s"]))
            gate_rows.append({
                "acq_utc": s["acq_utc"], "product_id": s["product_id"], "node": s["node"],
                "inc_deg": s["inc_deg"], "Hs_m": Hs, "Tp_s": Tp, "meanDir_deg": mwd,
                "gauge": best["gauge"], "dt_min": best["dt_min"],
                "over_60_min": abs(best["dt_min"]) > 60,
                "k_dir_deg": round(kdir, 1), "range_dir_deg": s["range_dir_deg"],
                "phi_k_range_deg": round(phi, 1),
                "L_17m_m": round(L, 1), "L_azimutale_apparente_m": round(L_az, 1),
                "lambda_cutoff_m": round(lam_c) if lam_c else None,
                "cutoff_margin": round(L_az / lam_c, 2) if lam_c else None,
                "T_base_s": s["T_base_s"], "dphi_deg": round(dphi),
                "dphi_in_45_180": 45 <= dphi <= 180,
                "offshore_extent_km": s["offshore_extent_km"],
                "wr17m_in_footprint": s["wr17m_in"],
            })
        else:
            gate_rows.append({"acq_utc": s["acq_utc"], "product_id": s["product_id"],
                              "node": s["node"], "status": "no_valid_wr17_observation",
                              "dt_min": best["dt_min"] if best else None,
                              "over_60_min": abs(best["dt_min"]) > 60 if best else None})
        gate_rows[-1].update({"nearest_gauge": nearest["gauge"] if nearest else None,
                             "nearest_dt_min": nearest["dt_min"] if nearest else None,
                             "nearest_over_60_min": abs(nearest["dt_min"]) > 60 if nearest else None})
        gate_rows[-1]["temporal_reference_usable"] = bool(best and abs(best["dt_min"]) <= 60)
        if best and abs(best["dt_min"]) > 60:
            gate_rows[-1]["status"] = "stale_wr17_reference_diagnostic_only"

    if cond_rows:
        with out_cond.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(cond_rows[0].keys()))
            w.writeheader(); w.writerows(cond_rows)
        print(f"scritto {out_cond} ({len(cond_rows)} righe)")
    if gate_rows:
        gate_rows.sort(key=lambda r: (not r["temporal_reference_usable"], -(r.get("cutoff_margin") or 0), -(r.get("dphi_deg") or 0)))
        with out_gate.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(dict.fromkeys(k for row in gate_rows for k in row)))
            w.writeheader(); w.writerows(gate_rows)
        print(f"scritto {out_gate} ({len(gate_rows)} righe)")
    print(f"richieste: {_budget['n']}, byte: {_budget['b']/1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
