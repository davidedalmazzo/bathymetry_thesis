#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sicd_subaperture.py

Decomposizione in sub-aperture Doppler di un'immagine SAR complessa SICD.
Pensato per Umbra Spotlight e per l'esperimento di tesi sul dwell.

Dipendenze:
    pip install numpy matplotlib sarpy

Esempi:
    python sicd_subaperture.py FILE_SICD.nitf --inspect
    python sicd_subaperture.py FILE_SICD.nitf --self-test

    # Primo test: ROI 1 km attorno allo SCP, 6 s, tre sub-look non sovrapposti
    python sicd_subaperture.py FILE_SICD.nitf --mode tiled --dwell 6 --roi-size-m 1000

    # Curva di degradazione del dwell: una sub-apertura centrale per durata
    python sicd_subaperture.py FILE_SICD.nitf --mode centered \
        --dwells 20,16,12,10,8,6,5 --roi-size-m 1000

NOTE IMPORTANTI
---------------
1) Per Grid.Type == RGAZIM, SICD definisce Row=range e Col=Doppler/azimuth.
   In quel caso lo split viene fatto lungo le colonne (axis=1).
2) Per griglie diverse, il programma NON indovina: richiede --axis 0/1.
3) La corrispondenza dwell <-> larghezza della banda Doppler e' assunta lineare.
   E' adeguata per il primo esperimento controllato; per la stima temporale finale
   useremo il CPHD/PVP per associare ogni sub-apertura ai tempi reali.
4) I file .npy sono complex64, quindi preservano la fase. Le PNG sono solo quicklook.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
from pathlib import Path
from typing import Optional, Sequence, Tuple

import numpy as np

try:
    from sarpy.io.complex.converter import open_complex
except Exception as exc:  # pragma: no cover
    open_complex = None
    SARPY_IMPORT_ERROR = exc
else:
    SARPY_IMPORT_ERROR = None


def _float_or_none(v):
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def _arr(v):
    if v is None:
        return None
    try:
        if hasattr(v, "get_array"):
            return np.asarray(v.get_array(dtype="float64"), dtype=float)
        return np.asarray(v, dtype=float)
    except Exception:
        return None


def _sicd_meta(reader):
    metas = reader.get_sicds_as_tuple()
    if not metas:
        raise RuntimeError("Nessun metadata SICD trovato")
    if len(metas) > 1:
        print(f"[nota] Il reader contiene {len(metas)} immagini; uso indice 0.")
    return metas[0]


def infer_full_dwell(meta) -> Tuple[float, str]:
    """Restituisce durata processata preferendo ImageFormation TStart/TEnd."""
    try:
        a = _float_or_none(meta.ImageFormation.TStartProc)
        b = _float_or_none(meta.ImageFormation.TEndProc)
        if a is not None and b is not None and b > a:
            return b - a, "ImageFormation.TEndProc-TStartProc"
    except Exception:
        pass
    try:
        d = _float_or_none(meta.Timeline.CollectDuration)
        if d is not None and d > 0:
            return d, "Timeline.CollectDuration"
    except Exception:
        pass
    raise RuntimeError("Impossibile ricavare il dwell dal SICD; passa --full-dwell")


def infer_axis(meta, forced: Optional[int]) -> int:
    if forced is not None:
        if forced not in (0, 1):
            raise ValueError("--axis deve essere 0 oppure 1")
        return forced
    gtype = str(getattr(meta.Grid, "Type", "") or "").upper()
    if gtype == "RGAZIM":
        return 1  # Row=range, Col=Doppler/azimuth
    raise RuntimeError(
        f"Grid.Type={gtype!r}: non assumo quale asse sia azimut. "
        "Rilancia con --axis 0 oppure --axis 1 dopo avere verificato il metadata."
    )


def image_shape(reader) -> Tuple[int, int]:
    sizes = reader.get_data_size_as_tuple()
    if isinstance(sizes, tuple) and len(sizes) == 2 and all(isinstance(x, (int, np.integer)) for x in sizes):
        return int(sizes[0]), int(sizes[1])
    if isinstance(sizes, (tuple, list)) and len(sizes) >= 1:
        s = sizes[0]
        return int(s[0]), int(s[1])
    raise RuntimeError(f"Formato dimensioni inatteso: {sizes!r}")


def scp_pixel(meta, shape: Tuple[int, int]) -> Tuple[int, int]:
    try:
        r = int(round(float(meta.ImageData.SCPPixel.Row) - float(meta.ImageData.FirstRow)))
        c = int(round(float(meta.ImageData.SCPPixel.Col) - float(meta.ImageData.FirstCol)))
        return max(0, min(shape[0]-1, r)), max(0, min(shape[1]-1, c))
    except Exception:
        return shape[0] // 2, shape[1] // 2


def pixel_spacing(meta) -> Tuple[Optional[float], Optional[float]]:
    try:
        return _float_or_none(meta.Grid.Row.SS), _float_or_none(meta.Grid.Col.SS)
    except Exception:
        return None, None


def support_bins(meta, axis: int, n: int) -> Tuple[int, str]:
    """Numero di bin del supporto spettrale processato lungo l'asse scelto."""
    dim = meta.Grid.Row if axis == 0 else meta.Grid.Col
    ss = _float_or_none(getattr(dim, "SS", None))
    dk1 = _float_or_none(getattr(dim, "DeltaK1", None))
    dk2 = _float_or_none(getattr(dim, "DeltaK2", None))
    if ss and dk1 is not None and dk2 is not None and dk2 > dk1:
        nb = int(round((dk2 - dk1) * n * ss))
        if 8 <= nb <= n:
            return nb, "Grid.DeltaK2-DeltaK1"
    bw = _float_or_none(getattr(dim, "ImpRespBW", None))
    if ss and bw and bw > 0:
        nb = int(round(bw * n * ss))
        if 8 <= nb <= n:
            return nb, "Grid.ImpRespBW"
    return n, "full FFT (fallback)"


def crop_bounds(center: int, count: int, total: int) -> Tuple[int, int]:
    count = max(8, min(int(count), total))
    start = int(round(center - count / 2))
    start = max(0, min(total - count, start))
    return start, start + count


def parse_dwells(s: Optional[str], one: Optional[float]) -> Sequence[float]:
    vals = []
    if s:
        for x in s.split(","):
            x = x.strip()
            if x:
                vals.append(float(x))
    if one is not None:
        vals.append(float(one))
    if not vals:
        vals = [6.0]
    vals = sorted(set(vals), reverse=True)
    if any(v <= 0 for v in vals):
        raise ValueError("I dwell devono essere > 0")
    return vals


def make_window(n: int, kind: str) -> np.ndarray:
    if kind == "rect":
        return np.ones(n, dtype=np.float32)
    if kind == "hann":
        return np.hanning(n).astype(np.float32)
    raise ValueError(kind)


def to_spectrum(chip: np.ndarray, axis: int) -> np.ndarray:
    # Stessa convenzione usata dal modulo CSI di SarPy: image -> phase-history-like
    return np.fft.fftshift(np.fft.ifft(chip, axis=axis), axes=axis)


def from_spectrum(spec: np.ndarray, axis: int) -> np.ndarray:
    return np.fft.fft(np.fft.ifftshift(spec, axes=axis), axis=axis)


def quicklook(a: np.ndarray, fn: Path, title: str = "") -> None:
    import matplotlib.pyplot as plt
    mag = np.abs(a).astype(np.float32)
    lo, hi = np.percentile(mag[np.isfinite(mag)], [2, 99.7]) if np.isfinite(mag).any() else (0, 1)
    img = np.clip((mag - lo) / max(hi - lo, 1e-12), 0, 1)
    img = np.sqrt(img)
    fig = plt.figure(figsize=(7, 7))
    ax = fig.add_subplot(111)
    ax.imshow(img, cmap="gray", origin="upper")
    ax.set_title(title)
    ax.set_xlabel("col")
    ax.set_ylabel("row")
    fig.tight_layout()
    fig.savefig(fn, dpi=150)
    plt.close(fig)


def inspect_file(path: str) -> None:
    if open_complex is None:
        raise RuntimeError(f"sarpy non importabile: {SARPY_IMPORT_ERROR}")
    reader = open_complex(path)
    meta = _sicd_meta(reader)
    nr, nc = image_shape(reader)
    ssr, ssc = pixel_spacing(meta)
    sr, sc = scp_pixel(meta, (nr, nc))
    try:
        dwell, dwell_src = infer_full_dwell(meta)
    except Exception:
        dwell, dwell_src = None, "non disponibile"

    def g(path_tuple):
        x = meta
        try:
            for p in path_tuple:
                x = getattr(x, p)
            return x
        except Exception:
            return None

    print("\n=== SICD INSPECT ===")
    print(f"file              : {path}")
    print(f"shape             : {nr} x {nc}")
    print(f"PixelType         : {g(('ImageData','PixelType'))}")
    print(f"Grid.Type         : {g(('Grid','Type'))}")
    print(f"Grid.ImagePlane   : {g(('Grid','ImagePlane'))}")
    print(f"ImageFormAlgo     : {g(('ImageFormation','ImageFormAlgo'))}")
    print(f"Row.SS            : {ssr} m")
    print(f"Col.SS            : {ssc} m")
    print(f"Row.ImpRespBW     : {g(('Grid','Row','ImpRespBW'))}")
    print(f"Col.ImpRespBW     : {g(('Grid','Col','ImpRespBW'))}")
    print(f"Row DeltaK1/2     : {g(('Grid','Row','DeltaK1'))} / {g(('Grid','Row','DeltaK2'))}")
    print(f"Col DeltaK1/2     : {g(('Grid','Col','DeltaK1'))} / {g(('Grid','Col','DeltaK2'))}")
    print(f"SCP pixel locale  : row={sr}, col={sc}")
    print(f"CollectDuration   : {g(('Timeline','CollectDuration'))} s")
    print(f"TStartProc/End    : {g(('ImageFormation','TStartProc'))} / {g(('ImageFormation','TEndProc'))} s")
    print(f"dwell usato       : {dwell} s ({dwell_src})")
    print(f"AzimAng           : {g(('SCPCOA','AzimAng'))} deg")
    print(f"GrazeAng          : {g(('SCPCOA','GrazeAng'))} deg")
    print(f"SideOfTrack       : {g(('SCPCOA','SideOfTrack'))}")
    try:
        axis = infer_axis(meta, None)
        print(f"asse sub-aperture : {axis} ({'rows' if axis == 0 else 'cols'}), da Grid.Type")
        n = nr if axis == 0 else nc
        nb, src = support_bins(meta, axis, n)
        print(f"supporto Doppler  : {nb}/{n} bin ({100*nb/n:.1f}%), da {src}")
    except Exception as e:
        print(f"asse sub-aperture : NON determinato ({e})")
    print("====================\n")


def self_test() -> None:
    rng = np.random.default_rng(0)
    n0, n1 = 128, 256
    # Costruisce uno spettro azimutale limitato al centro e un'immagine complessa.
    ph = np.zeros((n0, n1), dtype=np.complex128)
    lo, hi = 64, 192
    ph[:, lo:hi] = rng.normal(size=(n0, hi-lo)) + 1j*rng.normal(size=(n0, hi-lo))
    x = from_spectrum(ph, axis=1)
    ph2 = to_spectrum(x, axis=1)
    err_round = np.linalg.norm(ph2 - ph) / np.linalg.norm(ph)

    # Tre bande non sovrapposte la cui somma deve ricostruire il supporto scelto.
    ys = []
    edges = np.linspace(lo, hi, 4, dtype=int)
    for a, b in zip(edges[:-1], edges[1:]):
        p = np.zeros_like(ph2)
        p[:, a:b] = ph2[:, a:b]
        ys.append(from_spectrum(p, axis=1))
    recon = sum(ys)
    err_split = np.linalg.norm(recon - x) / np.linalg.norm(x)
    print(f"self-test round-trip relative error : {err_round:.3e}")
    print(f"self-test tiled-sum relative error  : {err_split:.3e}")
    if err_round > 1e-10 or err_split > 1e-10:
        raise SystemExit("SELF-TEST FALLITO")
    print("SELF-TEST OK")


def process(args) -> None:
    if open_complex is None:
        raise RuntimeError(
            f"sarpy non importabile ({SARPY_IMPORT_ERROR}). Installa con: pip install sarpy"
        )
    reader = open_complex(args.sicd)
    meta = _sicd_meta(reader)
    shape = image_shape(reader)
    axis = infer_axis(meta, args.axis)
    full_dwell, dwell_src = infer_full_dwell(meta) if args.full_dwell is None else (args.full_dwell, "--full-dwell")
    dwells = parse_dwells(args.dwells, args.dwell)
    if max(dwells) > full_dwell * 1.001:
        raise ValueError(f"Dwell richiesto {max(dwells)} s > dwell completo {full_dwell:.3f} s")

    ssr, ssc = pixel_spacing(meta)
    sr, sc = scp_pixel(meta, shape)
    cr = args.center_row if args.center_row is not None else sr
    cc = args.center_col if args.center_col is not None else sc

    if args.roi_size_m is not None:
        if not ssr or not ssc:
            raise RuntimeError("Pixel spacing mancante: usa --roi-rows e --roi-cols")
        nrr = int(round(args.roi_size_m / ssr))
        ncc = int(round(args.roi_size_m / ssc))
    else:
        nrr = args.roi_rows
        ncc = args.roi_cols

    r0, r1 = crop_bounds(cr, nrr, shape[0])
    c0, c1 = crop_bounds(cc, ncc, shape[1])
    print(f"Apro ROI: rows {r0}:{r1}, cols {c0}:{c1} -> {(r1-r0)} x {(c1-c0)} pixel")
    chip = reader[r0:r1, c0:c1, 0]
    chip = np.asarray(chip, dtype=np.complex64)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    np.save(outdir / "roi_full.npy", chip)
    quicklook(chip, outdir / "roi_full.png", f"Full aperture ~ {full_dwell:.2f} s")

    n_axis = chip.shape[axis]
    n_support, support_src = support_bins(meta, axis, n_axis)
    supp0 = (n_axis - n_support) // 2
    supp1 = supp0 + n_support
    print(f"Dwell completo: {full_dwell:.3f} s ({dwell_src})")
    print(f"Asse split: {axis}; supporto: {n_support}/{n_axis} bin ({support_src})")

    spec = to_spectrum(chip, axis=axis)
    # Lavoriamo su una sola copia dello spettro; ogni sub-look viene creato e liberato.
    records = []

    def make_one(dwell: float, b0: int, b1: int, seg: int, nseg: int, center_norm: float):
        w = make_window(b1-b0, args.window)
        shp = [1, 1]
        shp[axis] = b1-b0
        filt = np.zeros_like(spec)
        sl = [slice(None), slice(None)]
        sl[axis] = slice(b0, b1)
        filt[tuple(sl)] = spec[tuple(sl)] * w.reshape(shp)
        y = from_spectrum(filt, axis=axis).astype(np.complex64)
        del filt

        stem = f"sub_{dwell:g}s_{args.mode}_{seg:02d}of{nseg:02d}"
        np.save(outdir / f"{stem}.npy", y)
        quicklook(y, outdir / f"{stem}.png", f"{dwell:g} s | {args.mode} | {seg}/{nseg}")

        # Etichetta temporale SOLO lineare/approssimata. center_norm: -0.5..+0.5 nel supporto.
        t_approx = full_dwell * (0.5 + center_norm)
        records.append({
            "dwell_s": dwell,
            "mode": args.mode,
            "segment": seg,
            "n_segments": nseg,
            "band_bin_start": b0,
            "band_bin_stop": b1,
            "band_bins": b1-b0,
            "band_center_norm": center_norm,
            "approx_center_time_from_start_s": t_approx,
            "npy": f"{stem}.npy",
        })
        print(f"  scritto {stem}: bins {b0}:{b1}, centro norm={center_norm:+.3f}")
        del y

    for dwell in dwells:
        frac = min(1.0, dwell / full_dwell)
        nsub = max(8, int(round(n_support * frac)))
        nsub = min(nsub, n_support)

        if args.mode == "centered":
            b0 = supp0 + (n_support - nsub)//2
            b1 = b0 + nsub
            center_norm = ((0.5*(b0+b1) - (supp0 + n_support/2)) / n_support)
            make_one(dwell, b0, b1, 1, 1, center_norm)

        elif args.mode == "tiled":
            nseg = max(1, int(math.floor(full_dwell / dwell + 1e-9)))
            # limita a segmenti realmente non sovrapposti dentro il supporto
            nseg = min(nseg, max(1, n_support // nsub))
            block = nseg * nsub
            start = supp0 + (n_support - block)//2
            for j in range(nseg):
                b0 = start + j*nsub
                b1 = b0 + nsub
                center_norm = ((0.5*(b0+b1) - (supp0 + n_support/2)) / n_support)
                make_one(dwell, b0, b1, j+1, nseg, center_norm)
        else:
            raise ValueError(args.mode)

    with open(outdir / "subapertures.csv", "w", newline="", encoding="utf-8") as f:
        fields = list(records[0].keys()) if records else []
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(records)

    meta_out = {
        "sicd": str(Path(args.sicd).resolve()),
        "shape_full": shape,
        "roi": {"r0": r0, "r1": r1, "c0": c0, "c1": c1, "shape": list(chip.shape)},
        "scp_pixel_local": [sr, sc],
        "split_axis": axis,
        "grid_type": str(getattr(meta.Grid, "Type", None)),
        "full_dwell_s": full_dwell,
        "full_dwell_source": dwell_src,
        "support_bins": n_support,
        "support_source": support_src,
        "window": args.window,
        "warning": "approx_center_time_from_start_s usa mapping lineare banda-tempo; usare CPHD/PVP per timing finale",
    }
    with open(outdir / "run_metadata.json", "w", encoding="utf-8") as f:
        json.dump(meta_out, f, indent=2)

    print(f"\nFatto. Output: {outdir.resolve()}")
    print("Per il cross-spettro usa i .npy complex64, NON le PNG.")
    print("I tempi in subapertures.csv sono approssimati: per la tesi finale li mapperemo col CPHD/PVP.")


def build_parser():
    p = argparse.ArgumentParser(description="Sub-aperture Doppler splitter per SICD")
    p.add_argument("sicd", nargs="?", help="file SICD .nitf")
    p.add_argument("--inspect", action="store_true", help="stampa metadata e non processa")
    p.add_argument("--self-test", action="store_true", help="test numerico FFT/split senza dati")
    p.add_argument("--axis", type=int, choices=[0,1], default=None,
                   help="forza asse sub-aperture; per RGAZIM viene scelto automaticamente")
    p.add_argument("--full-dwell", type=float, default=None,
                   help="dwell completo in s; default da SICD metadata")
    p.add_argument("--mode", choices=["centered","tiled"], default="tiled")
    p.add_argument("--dwell", type=float, default=None, help="singolo dwell in s")
    p.add_argument("--dwells", default=None, help="lista, es. 20,16,12,10,8,6,5")
    p.add_argument("--window", choices=["rect","hann"], default="rect")
    p.add_argument("--center-row", type=int, default=None)
    p.add_argument("--center-col", type=int, default=None)
    p.add_argument("--roi-size-m", type=float, default=1000.0,
                   help="ROI quadrata in metri; default 1000")
    p.add_argument("--roi-rows", type=int, default=2048,
                   help="usato solo se --roi-size-m non e' specificato")
    p.add_argument("--roi-cols", type=int, default=2048,
                   help="usato solo se --roi-size-m non e' specificato")
    p.add_argument("--outdir", default="sicd_subapertures")
    return p


def main():
    p = build_parser()
    a = p.parse_args()
    if a.self_test:
        self_test()
        if not a.sicd:
            return
    if not a.sicd:
        p.error("specifica il file SICD, oppure usa solo --self-test")
    if a.inspect:
        inspect_file(a.sicd)
        return
    process(a)


if __name__ == "__main__":
    main()
