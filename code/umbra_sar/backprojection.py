"""Time-domain backprojection of the CPHD phase history onto a ground grid.

Why not reuse the vendor SICD.  The delivered product is focused with PFA and
declares ``SVA`` weighting on both Grid.Row and Grid.Col without ``WgtFunct``
samples.  Spatially Variant Apodization is a *nonlinear, pixel-dependent*
sidelobe suppression: it does not commute with a Doppler sub-band split, so a
sub-look extracted by masking the azimuth spectrum of an SVA image is not the
image that band of the aperture would have formed.  Autofocus is declared off
(``azimuth_autofocus = NO``, ``range_autofocus = NO``) and ``TimeCOAPoly`` is
constant, so those are not suspects, but SVA cannot be undone without the
weighting samples.

Forming sub-looks directly from phase history removes that class of doubt and
improves the measurement at the same time:

* the slow time of a sub-look is *exactly* the mean TxTime of the pulses summed
  into it, not a band centre mapped through an inversion;
* the full 22.541 s CPHD dwell is available instead of the 18.068 s the SICD
  processed, a 25 percent longer phase-ramp baseline;
* sub-looks are strictly disjoint in slow time by construction;
* the aperture weighting is uniform and chosen by us;
* the image is built directly on a ground grid at the sea-surface height, so
  there is no slant-plane Jacobian and no HAE mislocation.

Geometry notes.  The collection is monostatic with TxPos == RcvPos and a
constant SRPPos, and the FX-domain signal is already referenced to the SRP: a
range-compressed pulse peaks tens of metres from zero delay, not at the 610 km
slant range.  So the backprojection kernel is

    I(p) = sum_m g_m(tau_m(p)) exp(+i 2 pi SC0 tau_m(p)),
    tau_m(p) = 2 (|TxPos_m - p| - |TxPos_m - SRP|) / c ,

with g_m the zero-padded inverse DFT of the pulse over its uniform frequency
grid f_n = SC0 + n SCSS.  The envelope is interpolated with a four-point
Catmull-Rom kernel; at the padding used here it is oversampled about 2.5 times
per resolution cell, where cubic interpolation costs about -45 dB and linear
would cost about -26 dB.

Pulses are never decimated.  The scene is a coastline and the illuminated
spotlight footprint is far wider than the analysis patch, so a lower effective
PRF would fold bright land returns onto the water.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterator

import numpy as np

SPEED_OF_LIGHT_M_PER_S = 299792458.0
WGS84_A = 6378137.0
WGS84_F = 1.0 / 298.257223563


# --------------------------------------------------------------------------
# geodesy (pure numpy; no pyproj dependency)
# --------------------------------------------------------------------------


def utm_to_geodetic(
    easting: np.ndarray, northing: np.ndarray, zone: int, northern: bool = True
) -> tuple[np.ndarray, np.ndarray]:
    """Inverse UTM (Krueger series, order 6). Returns degrees (lat, lon)."""

    a, f = WGS84_A, WGS84_F
    n = f / (2.0 - f)
    n2, n3, n4, n5 = n**2, n**3, n**4, n**5
    A = a / (1.0 + n) * (1.0 + n2 / 4.0 + n4 / 64.0)
    k0, e0, n0 = 0.9996, 500000.0, (0.0 if northern else 10000000.0)
    xi = (np.asarray(northing, dtype=np.float64) - n0) / (k0 * A)
    eta = (np.asarray(easting, dtype=np.float64) - e0) / (k0 * A)

    beta = (
        n / 2.0 - 2.0 / 3.0 * n2 + 37.0 / 96.0 * n3 - 1.0 / 360.0 * n4 - 81.0 / 512.0 * n5,
        1.0 / 48.0 * n2 + 1.0 / 15.0 * n3 - 437.0 / 1440.0 * n4 + 46.0 / 105.0 * n5,
        17.0 / 480.0 * n3 - 37.0 / 840.0 * n4 - 209.0 / 4480.0 * n5,
        4397.0 / 161280.0 * n4 + 11.0 / 504.0 * n5,
        4583.0 / 161280.0 * n5,
    )
    delta = (
        2.0 * n - 2.0 / 3.0 * n2 - 2.0 * n3 + 116.0 / 45.0 * n4 + 26.0 / 45.0 * n5,
        7.0 / 3.0 * n2 - 8.0 / 5.0 * n3 - 227.0 / 45.0 * n4 + 2704.0 / 315.0 * n5,
        56.0 / 15.0 * n3 - 136.0 / 35.0 * n4 - 1262.0 / 105.0 * n5,
        4279.0 / 630.0 * n4 - 332.0 / 35.0 * n5,
        4174.0 / 315.0 * n5,
    )
    xi_p, eta_p = xi.copy(), eta.copy()
    for j, b in enumerate(beta, start=1):
        xi_p -= b * np.sin(2.0 * j * xi) * np.cosh(2.0 * j * eta)
        eta_p -= b * np.cos(2.0 * j * xi) * np.sinh(2.0 * j * eta)
    chi = np.arcsin(np.sin(xi_p) / np.cosh(eta_p))
    latitude = chi.copy()
    for j, d in enumerate(delta, start=1):
        latitude += d * np.sin(2.0 * j * chi)
    longitude = np.deg2rad(zone * 6.0 - 183.0) + np.arctan2(
        np.sinh(eta_p), np.cos(xi_p)
    )
    return np.rad2deg(latitude), np.rad2deg(longitude)


def geodetic_to_ecf(
    latitude_deg: np.ndarray, longitude_deg: np.ndarray, height_m: np.ndarray | float
) -> np.ndarray:
    lat = np.deg2rad(np.asarray(latitude_deg, dtype=np.float64))
    lon = np.deg2rad(np.asarray(longitude_deg, dtype=np.float64))
    height = np.asarray(height_m, dtype=np.float64) * np.ones_like(lat)
    e2 = WGS84_F * (2.0 - WGS84_F)
    nu = WGS84_A / np.sqrt(1.0 - e2 * np.sin(lat) ** 2)
    return np.stack(
        (
            (nu + height) * np.cos(lat) * np.cos(lon),
            (nu + height) * np.cos(lat) * np.sin(lon),
            (nu * (1.0 - e2) + height) * np.sin(lat),
        ),
        axis=-1,
    )


# --------------------------------------------------------------------------
# grid
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class GroundGrid:
    """Rotated ground rectangle on a constant-HAE surface, in ECF."""

    ecf_m: np.ndarray
    shape: tuple[int, int]
    spacing_m: float
    length_parallel_m: float
    length_perpendicular_m: float
    bearing_deg: float
    center_easting_northing_m: tuple[float, float]
    utm_zone: int
    surface_hae_m: float

    def metadata(self) -> dict[str, Any]:
        item = {k: v for k, v in asdict(self).items() if k != "ecf_m"}
        item["pixel_count"] = int(self.shape[0] * self.shape[1])
        return item


def build_ground_grid(
    *,
    center_easting_m: float,
    center_northing_m: float,
    utm_zone: int,
    bearing_deg: float,
    length_parallel_m: float,
    length_perpendicular_m: float,
    spacing_m: float,
    surface_hae_m: float,
) -> GroundGrid:
    """Grid whose first axis runs along ``bearing_deg`` clockwise from north."""

    n_parallel = int(round(length_parallel_m / spacing_m))
    n_perpendicular = int(round(length_perpendicular_m / spacing_m))
    u = (np.arange(n_parallel) - 0.5 * (n_parallel - 1)) * spacing_m
    v = (np.arange(n_perpendicular) - 0.5 * (n_perpendicular - 1)) * spacing_m
    grid_u, grid_v = np.meshgrid(u, v, indexing="ij")
    theta = np.deg2rad(bearing_deg)
    # bearing is clockwise from north: north component cos, east component sin
    easting = center_easting_m + grid_u * np.sin(theta) + grid_v * np.cos(theta)
    northing = center_northing_m + grid_u * np.cos(theta) - grid_v * np.sin(theta)
    latitude, longitude = utm_to_geodetic(easting.ravel(), northing.ravel(), utm_zone)
    ecf = geodetic_to_ecf(latitude, longitude, surface_hae_m)
    return GroundGrid(
        ecf_m=np.ascontiguousarray(ecf, dtype=np.float64),
        shape=(n_parallel, n_perpendicular),
        spacing_m=float(spacing_m),
        length_parallel_m=float(length_parallel_m),
        length_perpendicular_m=float(length_perpendicular_m),
        bearing_deg=float(bearing_deg),
        center_easting_northing_m=(float(center_easting_m), float(center_northing_m)),
        utm_zone=int(utm_zone),
        surface_hae_m=float(surface_hae_m),
    )


# --------------------------------------------------------------------------
# CPHD access
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class CphdChannel:
    path: Path
    num_vectors: int
    num_samples: int
    signal_offset: int
    pvp_offset: int
    pvp_words: int
    sc0_hz: float
    scss_hz: float
    tx_time_s: np.ndarray
    tx_position_ecf_m: np.ndarray
    srp_position_ecf_m: np.ndarray
    global_sgn: int

    @classmethod
    def open(cls, cphd_path: Path | str, metadata_json: Path | str) -> "CphdChannel":
        meta = json.loads(Path(metadata_json).read_text(encoding="utf-8"))
        header = meta["file"]["header"]
        definitions = meta["pvp_fields"]
        num_vectors = int(meta["data"]["num_vectors"])
        num_samples = int(meta["data"]["num_samples"])
        words = int(meta["data"]["num_bytes_pvp"]) // 8
        pvp = np.memmap(
            Path(cphd_path), dtype=">f8", mode="r",
            offset=int(header["PVP_BLOCK_BYTE_OFFSET"]), shape=(num_vectors, words),
        )

        def field(name: str) -> np.ndarray:
            item = definitions[name]
            start = int(item["offset_words"])
            return np.asarray(pvp[:, start : start + int(item["size_words"])],
                              dtype=np.float64)

        sc0 = field("SC0")[:, 0]
        scss = field("SCSS")[:, 0]
        if not (np.allclose(sc0, sc0[0]) and np.allclose(scss, scss[0])):
            raise ValueError("SC0/SCSS vary per vector; a common frequency grid is "
                             "assumed by this implementation")
        tx_position = field("TxPos")
        if not np.allclose(tx_position, field("RcvPos")):
            raise ValueError("TxPos != RcvPos; this implementation is monostatic")
        srp = field("SRPPos")
        if not np.allclose(srp, srp[0]):
            raise ValueError("SRPPos varies per vector; not handled")
        return cls(
            path=Path(cphd_path),
            num_vectors=num_vectors,
            num_samples=num_samples,
            signal_offset=int(header["SIGNAL_BLOCK_BYTE_OFFSET"]),
            pvp_offset=int(header["PVP_BLOCK_BYTE_OFFSET"]),
            pvp_words=words,
            sc0_hz=float(sc0[0]),
            scss_hz=float(scss[0]),
            tx_time_s=field("TxTime")[:, 0],
            tx_position_ecf_m=tx_position,
            srp_position_ecf_m=srp,
            global_sgn=int(meta["global"]["sgn"]),
        )

    def signal(self) -> np.memmap:
        return np.memmap(self.path, dtype=">c8", mode="r",
                         offset=self.signal_offset,
                         shape=(self.num_vectors, self.num_samples))


# --------------------------------------------------------------------------
# kernel
# --------------------------------------------------------------------------


def catmull_rom(envelope: np.ndarray, position: np.ndarray) -> np.ndarray:
    """Four-point cubic interpolation of a complex envelope at fractional bins."""

    base = np.floor(position).astype(np.int64)
    t = (position - base).astype(np.float32)
    size = envelope.shape[-1]
    i0 = np.clip(base - 1, 0, size - 1)
    i1 = np.clip(base, 0, size - 1)
    i2 = np.clip(base + 1, 0, size - 1)
    i3 = np.clip(base + 2, 0, size - 1)
    t2 = t * t
    t3 = t2 * t
    w0 = 0.5 * (-t3 + 2.0 * t2 - t)
    w1 = 0.5 * (3.0 * t3 - 5.0 * t2 + 2.0)
    w2 = 0.5 * (-3.0 * t3 + 4.0 * t2 + t)
    w3 = 0.5 * (t3 - t2)
    return (envelope[i0] * w0 + envelope[i1] * w1
            + envelope[i2] * w2 + envelope[i3] * w3)


def backproject(
    channel: CphdChannel,
    grid: GroundGrid,
    look_of_pulse: np.ndarray,
    *,
    look_count: int,
    fft_size: int = 1 << 18,
    delay_window_m: float = 900.0,
    pulse_block: int = 256,
    carrier_sign: int = +1,
    pulse_indices: np.ndarray | None = None,
    progress: Any = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Accumulate one complex image per look. ``look_of_pulse`` selects the look."""

    signal = channel.signal()
    pixels = grid.ecf_m
    n_pixels = pixels.shape[0]
    images = np.zeros((look_count, n_pixels), dtype=np.complex128)
    contributions = np.zeros(look_count, dtype=np.int64)
    time_sum = np.zeros(look_count, dtype=np.float64)

    bin_metres = SPEED_OF_LIGHT_M_PER_S / (2.0 * fft_size * channel.scss_hz)
    half_window = int(round(delay_window_m / bin_metres))
    centre = fft_size // 2
    lo, hi = centre - half_window, centre + half_window
    carrier = carrier_sign * 2.0 * np.pi * channel.sc0_hz * 2.0 / SPEED_OF_LIGHT_M_PER_S

    indices = (np.arange(channel.num_vectors) if pulse_indices is None
               else np.asarray(pulse_indices, dtype=np.int64))

    srp = channel.srp_position_ecf_m[0]

    for start in range(0, indices.size, pulse_block):
        block = indices[start : start + pulse_block]
        raw = np.asarray(signal[block[0] : block[-1] + 1], dtype=np.complex64)
        if block.size != block[-1] - block[0] + 1:
            raw = raw[block - block[0]]
        envelope = np.fft.fftshift(
            np.fft.ifft(raw, n=fft_size, axis=1), axes=1
        )[:, lo:hi].astype(np.complex64)
        for offset, pulse in enumerate(block):
            look = int(look_of_pulse[pulse])
            if look < 0:
                continue
            antenna = channel.tx_position_ecf_m[pulse]
            delta = pixels - antenna
            ranges = np.sqrt(np.einsum("ij,ij->i", delta, delta))
            differential = ranges - float(np.linalg.norm(srp - antenna))
            position = differential / bin_metres + half_window
            sampled = catmull_rom(envelope[offset], position)
            images[look] += sampled * np.exp(1j * carrier * differential)
            contributions[look] += 1
            time_sum[look] += channel.tx_time_s[pulse]
        if progress is not None:
            progress(start + block.size, indices.size)

    diagnostics = {
        "fft_size": int(fft_size),
        "range_bin_m": float(bin_metres),
        "oversampling_vs_native_resolution": float(
            fft_size / channel.num_samples
        ),
        "delay_window_m": float(delay_window_m),
        "carrier_sign": int(carrier_sign),
        "pulses_used": int(indices.size),
        "pulses_per_look": contributions.tolist(),
        "mean_tx_time_per_look_s": (
            time_sum / np.maximum(contributions, 1)
        ).tolist(),
    }
    return images.astype(np.complex64), diagnostics


def disjoint_look_assignment(
    tx_time_s: np.ndarray, look_count: int,
    *, start_s: float | None = None, stop_s: float | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Assign each pulse to one of ``look_count`` equal, disjoint time slices."""

    t = np.asarray(tx_time_s, dtype=np.float64)
    lo = float(t.min() if start_s is None else start_s)
    hi = float(t.max() if stop_s is None else stop_s)
    edges = np.linspace(lo, hi, look_count + 1)
    look = np.digitize(t, edges[1:-1])
    look = np.where((t < lo) | (t > hi), -1, look)
    return look.astype(np.int32), edges
