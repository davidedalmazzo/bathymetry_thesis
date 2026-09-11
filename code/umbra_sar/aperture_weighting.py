"""Effective slow time of a Doppler sub-look from the measured azimuth spectrum.

Blocks 3/4 assign to every sub-look the *geometric* centre of its Doppler band,
mapped to slow time through the CPHD PVP inversion.  That is the correct label
only if the azimuth spectral density is flat across the processed support.  It
is not: the SICD declares ``Grid.Col.WgtType.WindowName = SVA`` without
``WgtFunct`` samples, the two-way antenna pattern tapers the illumination, and
Block 4 applies its own Tukey(0.25) inside each band.

The slow-time instant a sub-look actually represents is the *power weighted*
centroid of its band,

    t_eff,i = integral t(k) |S_i(k)|^2 dk / integral |S_i(k)|^2 dk ,

which for any weighting peaked at the centre of the aperture is pulled inward
relative to the geometric centre.  The lever arm of a phase-versus-time
regression therefore shrinks, and an angular frequency recovered from that
slope is biased *low* by exactly that shrink factor.  The bias is a rescaling
of the time axis, hence multiplicative and independent of the wave number.

This module measures the weighting from the data instead of assuming it.  It
depends only on numpy so it runs both inside the project venv and on a bare
interpreter; SICD scalars are read from the frozen SICD_METADATA.json rather
than through sarpy.

Caveat kept explicit throughout: |S_i(k)|^2 measured on an image crop estimates
(scene azimuth spectrum) x (aperture weighting).  Speckle makes the scene
factor white in expectation, so the measured profile is an estimator of the
weighting.  For the phase of a long wave the relevant weight is the same one,
because the wave modulation rides multiplicatively on the reflectivity.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Sequence

import numpy as np


# --------------------------------------------------------------------------
# metadata access without sarpy
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class SicdScalars:
    col_ss_m: float
    num_cols: int
    col_delta_k1_per_m: float
    col_delta_k2_per_m: float
    col_sgn: int
    col_uvect_ecf: tuple[float, float, float]
    row_uvect_ecf: tuple[float, float, float]
    scp_ecf: tuple[float, float, float]
    scp_time_s: float
    t_start_proc_s: float
    t_end_proc_s: float
    tx_frequency_proc_min_hz: float
    tx_frequency_proc_max_hz: float
    col_weight_name: str | None
    col_weight_samples_present: bool

    @property
    def processed_aperture_duration_s(self) -> float:
        return self.t_end_proc_s - self.t_start_proc_s

    @property
    def processed_center_frequency_hz(self) -> float:
        return 0.5 * (self.tx_frequency_proc_min_hz + self.tx_frequency_proc_max_hz)

    @classmethod
    def from_json(cls, path: Path | str) -> "SicdScalars":
        document = json.loads(Path(path).read_text(encoding="utf-8"))
        # The frozen SICD_METADATA.json keeps the verbatim SICD tree under
        # "sicd_selected_metadata"; a raw SICD dump has it at the root.
        raw = document.get("sicd_selected_metadata", document)
        grid = raw["Grid"]
        col = grid["Col"]
        row = grid["Row"]
        formation = raw["ImageFormation"]
        image_data = raw["ImageData"]
        weight_type = col.get("WgtType") or {}
        return cls(
            col_ss_m=float(col["SS"]),
            num_cols=int(image_data["NumCols"]),
            col_delta_k1_per_m=float(col["DeltaK1"]),
            col_delta_k2_per_m=float(col["DeltaK2"]),
            col_sgn=int(col["Sgn"]),
            col_uvect_ecf=_xyz(col["UVectECF"]),
            row_uvect_ecf=_xyz(row["UVectECF"]),
            scp_ecf=_xyz(raw["GeoData"]["SCP"]["ECF"]),
            scp_time_s=float(raw["SCPCOA"]["SCPTime"]),
            t_start_proc_s=float(formation["TStartProc"]),
            t_end_proc_s=float(formation["TEndProc"]),
            tx_frequency_proc_min_hz=float(formation["TxFrequencyProc"]["MinProc"]),
            tx_frequency_proc_max_hz=float(formation["TxFrequencyProc"]["MaxProc"]),
            col_weight_name=(
                None if weight_type.get("WindowName") is None
                else str(weight_type["WindowName"])
            ),
            col_weight_samples_present=col.get("WgtFunct") is not None,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _xyz(node: dict) -> tuple[float, float, float]:
    return (float(node["X"]), float(node["Y"]), float(node["Z"]))


# --------------------------------------------------------------------------
# CPHD PVP -> monotone k_col(t)
# --------------------------------------------------------------------------


SPEED_OF_LIGHT_M_PER_S = 299792458.0


@dataclass(frozen=True)
class KColTimeTable:
    """Strictly decreasing k_col sampled on strictly increasing TxTime."""

    tx_time_s: np.ndarray
    k_col_per_m: np.ndarray
    k_row_per_m: np.ndarray
    source_cphd: str

    def time_for_k(self, targets: np.ndarray | float) -> np.ndarray:
        values = np.atleast_1d(np.asarray(targets, dtype=np.float64))
        lo, hi = self.k_col_per_m[-1], self.k_col_per_m[0]
        if np.any(values < lo) or np.any(values > hi):
            raise ValueError(
                f"k_col target outside CPHD coverage [{lo:.6f}, {hi:.6f}] per m"
            )
        return np.interp(values, self.k_col_per_m[::-1], self.tx_time_s[::-1])

    def validate_against_sicd(self, sicd: SicdScalars) -> dict[str, float]:
        k_row_at_scp = float(np.interp(sicd.scp_time_s, self.tx_time_s, self.k_row_per_m))
        k_col_at_scp = float(np.interp(sicd.scp_time_s, self.tx_time_s, self.k_col_per_m))
        return {
            "interpolated_k_row_at_scp_time_per_m": k_row_at_scp,
            "interpolated_k_col_at_scp_time_per_m": k_col_at_scp,
        }


def load_kcol_time_table(
    cphd_path: Path | str,
    cphd_metadata_json: Path | str,
    sicd: SicdScalars,
) -> KColTimeTable:
    """Rebuild k_col(t) from the CPHD PVP block only; the signal block is never read."""

    meta = json.loads(Path(cphd_metadata_json).read_text(encoding="utf-8"))
    header = meta["file"]["header"]
    definitions = meta["pvp_fields"]
    num_vectors = int(meta["data"]["num_vectors"])
    record_words = int(meta["data"]["num_bytes_pvp"]) // 8
    records = np.memmap(
        Path(cphd_path),
        dtype=">f8",
        mode="r",
        offset=int(header["PVP_BLOCK_BYTE_OFFSET"]),
        shape=(num_vectors, record_words),
    )

    def field(name: str) -> np.ndarray:
        item = definitions[name]
        start = int(item["offset_words"])
        stop = start + int(item["size_words"])
        return np.asarray(records[:, start:stop], dtype=np.float64)

    tx_time = field("TxTime")[:, 0]
    tx_pos = field("TxPos")
    srp_pos = field("SRPPos")
    line_of_sight = srp_pos - tx_pos
    line_of_sight /= np.linalg.norm(line_of_sight, axis=1)[:, None]
    wave_vector = (
        2.0 * sicd.processed_center_frequency_hz / SPEED_OF_LIGHT_M_PER_S
    ) * line_of_sight
    k_col = wave_vector @ np.asarray(sicd.col_uvect_ecf)
    k_row = wave_vector @ np.asarray(sicd.row_uvect_ecf)

    if not np.all(np.diff(tx_time) > 0):
        raise ValueError("CPHD TxTime is not strictly increasing")
    if not np.all(np.diff(k_col) < 0):
        raise ValueError("CPHD-derived k_col is not strictly decreasing")
    return KColTimeTable(
        tx_time_s=tx_time,
        k_col_per_m=k_col,
        k_row_per_m=k_row,
        source_cphd=str(cphd_path),
    )


# --------------------------------------------------------------------------
# windows (numpy only; mirrors umbra_sar.subaperture.make_window)
# --------------------------------------------------------------------------


def tukey_window(length: int, alpha: float) -> np.ndarray:
    n = int(length)
    if n < 1:
        raise ValueError("window length must be positive")
    if not 0.0 <= alpha <= 1.0:
        raise ValueError("Tukey alpha must lie in [0, 1]")
    if alpha == 0.0:
        return np.ones(n, dtype=np.float64)
    if n == 1:
        return np.ones(1, dtype=np.float64)
    x = np.linspace(0.0, 1.0, n, dtype=np.float64)
    w = np.ones(n, dtype=np.float64)
    taper = alpha / 2.0
    left = x < taper
    right = x > 1.0 - taper
    w[left] = 0.5 * (1.0 + np.cos(np.pi * (2.0 * x[left] / alpha - 1.0)))
    w[right] = 0.5 * (
        1.0 + np.cos(np.pi * (2.0 * x[right] / alpha - 2.0 / alpha + 1.0))
    )
    return w


def energy_normalized(window: np.ndarray) -> np.ndarray:
    w = np.asarray(window, dtype=np.float64)
    return w * float(np.sqrt(w.size / np.sum(np.abs(w) ** 2)))


# --------------------------------------------------------------------------
# azimuth power profile of a stored complex sub-look
# --------------------------------------------------------------------------


def azimuth_power_profile(
    complex_image: np.ndarray,
    *,
    col_ss_m: float,
    col_sgn: int,
    row_block: int = 128,
) -> tuple[np.ndarray, np.ndarray]:
    """Mean |spectrum|^2 along azimuth of a focused crop, on absolute k_col.

    Returns ``(k_col_per_m, mean_power)`` with the spectrum fftshifted.  The
    azimuth spatial-frequency axis is absolute, so an azimuth crop does not
    move it: only its bin spacing coarsens.  Sgn=-1 selects the forward FFT,
    matching ``umbra_sar.subaperture.image_to_shifted_spectrum``.
    """

    data = np.asarray(complex_image)
    if data.ndim != 2:
        raise ValueError("expected a 2-D (range, azimuth) crop")
    rows, cols = data.shape
    k = np.fft.fftshift(np.fft.fftfreq(cols, d=float(col_ss_m)))
    accumulator = np.zeros(cols, dtype=np.float64)
    for start in range(0, rows, int(row_block)):
        block = np.asarray(data[start : start + int(row_block)], dtype=np.complex128)
        if col_sgn == -1:
            spectrum = np.fft.fft(block, axis=1)
        elif col_sgn == 1:
            spectrum = np.fft.ifft(block, axis=1)
        else:
            raise ValueError("SICD Col.Sgn must be -1 or +1")
        spectrum = np.fft.fftshift(spectrum, axes=1)
        accumulator += np.sum(np.abs(spectrum) ** 2, axis=0)
    return k, accumulator / rows


@dataclass(frozen=True)
class BandCentroid:
    look_index: int
    band_start_bin: int
    band_stop_bin: int
    k_low_per_m: float
    k_high_per_m: float
    k_geometric_center_per_m: float
    k_energy_centroid_per_m: float
    t_geometric_center_s: float
    t_energy_centroid_s: float
    in_band_samples: int
    band_power_fraction_outside: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def band_energy_centroid(
    k_axis: np.ndarray,
    power: np.ndarray,
    *,
    k_low_per_m: float,
    k_high_per_m: float,
) -> tuple[float, int, float]:
    """Power-weighted k centroid inside a band, plus leakage diagnostics."""

    lo, hi = sorted((float(k_low_per_m), float(k_high_per_m)))
    inside = (k_axis >= lo) & (k_axis <= hi)
    if int(np.count_nonzero(inside)) < 8:
        raise ValueError("band contains too few spectral samples for a centroid")
    weight = power[inside]
    total = float(np.sum(power))
    in_band = float(np.sum(weight))
    centroid = float(np.sum(k_axis[inside] * weight) / in_band)
    leakage = 0.0 if total <= 0 else 1.0 - in_band / total
    return centroid, int(np.count_nonzero(inside)), leakage


def deweighted_band_profile(
    k_axis: np.ndarray,
    power: np.ndarray,
    *,
    k_low_per_m: float,
    k_high_per_m: float,
    band_window: np.ndarray,
    min_window_power: float = 0.2,
) -> tuple[np.ndarray, np.ndarray]:
    """Divide out the in-band analysis window to expose the aperture weighting.

    Only samples where the window power exceeds ``min_window_power`` are kept,
    so the Tukey skirts never appear as a division by a near-zero number.
    """

    lo, hi = sorted((float(k_low_per_m), float(k_high_per_m)))
    inside = (k_axis >= lo) & (k_axis <= hi)
    u = (k_axis[inside] - lo) / (hi - lo)
    w = np.interp(u, np.linspace(0.0, 1.0, band_window.size), band_window)
    w2 = w**2
    keep = w2 > float(min_window_power)
    return k_axis[inside][keep], power[inside][keep] / w2[keep]


def shrink_factor(t_geometric: Sequence[float], t_energy: Sequence[float]) -> dict[str, float]:
    """OLS slope of the energy-centroid times against the geometric times.

    A least-squares phase ramp fitted against ``t_geometric`` when the physical
    times are ``t_energy`` returns ``omega_true * shrink``.
    """

    g = np.asarray(t_geometric, dtype=np.float64)
    e = np.asarray(t_energy, dtype=np.float64)
    if g.shape != e.shape or g.size < 3:
        raise ValueError("need matching arrays with at least 3 looks")
    gc = g - g.mean()
    ec = e - e.mean()
    slope = float(np.sum(gc * ec) / np.sum(gc**2))
    intercept = float(e.mean() - slope * g.mean())
    residual = e - (intercept + slope * g)
    return {
        "shrink": slope,
        "intercept_s": intercept,
        "residual_rms_s": float(np.sqrt(np.mean(residual**2))),
        "residual_max_abs_s": float(np.max(np.abs(residual))),
        "geometric_span_s": float(g.max() - g.min()),
        "energy_span_s": float(e.max() - e.min()),
        "span_ratio": float((e.max() - e.min()) / (g.max() - g.min())),
    }
