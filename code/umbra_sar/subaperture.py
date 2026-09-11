"""Metadata-aware Doppler sub-aperture primitives.

The module deliberately keeps two time quantities separate:

* ``processed_aperture_duration_s`` is the SICD ImageFormation interval and is
  the only duration used to turn a nominal SICD sub-aperture duration into a
  Doppler bandwidth fraction.
* ``cphd_slow_time_dwell_s`` is CPHD slow-time availability.  It is provenance
  for later focusing and time mapping, never a denominator for an already
  focused SICD.

Timing produced by a linear bandwidth fraction is always labelled nominal.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal, Sequence

import numpy as np
from scipy import fft as scipy_fft
from scipy.signal.windows import tukey


WindowKind = Literal["rect", "tukey"]
WindowNormalization = Literal["none", "energy", "coherent"]


class MetadataError(ValueError):
    """Raised when metadata cannot support a physically explicit operation."""


def _to_array(value: Any, dtype: str = "float64") -> np.ndarray | None:
    if value is None:
        return None
    if hasattr(value, "get_array"):
        return np.asarray(value.get_array(dtype=dtype), dtype=dtype)
    return np.asarray(value, dtype=dtype)


def _constant_polynomial(value: Any, name: str) -> float:
    array = _to_array(value)
    if array is None:
        raise MetadataError(f"{name} is missing")
    if array.size == 0:
        raise MetadataError(f"{name} is empty")
    flat = array.ravel()
    if flat.size > 1 and np.any(flat[1:] != 0):
        raise MetadataError(
            f"{name} varies spatially; a single global Doppler support is not valid"
        )
    return float(flat[0])


def _metadata_parameter(parameters: Any, name: str) -> str | None:
    if parameters is None:
        return None
    if isinstance(parameters, dict):
        value = parameters.get(name)
        return None if value is None else str(value)
    try:
        return str(parameters[name])
    except Exception:
        return None


@dataclass(frozen=True)
class AxisConvention:
    """SICD array axis and Fourier-sign information for azimuth splitting."""

    grid_type: str
    range_axis: int
    azimuth_axis: int
    azimuth_sgn: int
    azimuth_sample_spacing_m: float
    delta_k1_per_m: float
    delta_k2_per_m: float
    delta_kcoa_constant_per_m: float
    native_weight_name: str | None
    native_weight_samples_present: bool

    @classmethod
    def from_sicd(cls, sicd: Any) -> "AxisConvention":
        grid = getattr(sicd, "Grid", None)
        grid_type = str(getattr(grid, "Type", "") or "").upper()
        if grid_type != "RGAZIM":
            raise MetadataError(
                f"Grid.Type={grid_type!r}; range/azimuth axes are not inferred"
            )
        col = getattr(grid, "Col", None)
        if col is None:
            raise MetadataError("Grid.Col is missing")
        sgn = int(getattr(col, "Sgn", 0))
        if sgn not in (-1, 1):
            raise MetadataError(f"Grid.Col.Sgn must be -1 or +1, got {sgn}")
        ss = float(getattr(col, "SS"))
        delta_k1 = float(getattr(col, "DeltaK1"))
        delta_k2 = float(getattr(col, "DeltaK2"))
        if not (ss > 0 and delta_k2 > delta_k1):
            raise MetadataError("Invalid Col sample spacing or DeltaK support")
        delta_kcoa = _constant_polynomial(
            getattr(col, "DeltaKCOAPoly", None), "Grid.Col.DeltaKCOAPoly"
        )
        weight_type = getattr(col, "WgtType", None)
        weight_name = getattr(weight_type, "WindowName", None)
        weight_samples = getattr(col, "WgtFunct", None)
        return cls(
            grid_type=grid_type,
            range_axis=0,
            azimuth_axis=1,
            azimuth_sgn=sgn,
            azimuth_sample_spacing_m=ss,
            delta_k1_per_m=delta_k1,
            delta_k2_per_m=delta_k2,
            delta_kcoa_constant_per_m=delta_kcoa,
            native_weight_name=None if weight_name is None else str(weight_name),
            native_weight_samples_present=weight_samples is not None,
        )

    @property
    def forward_transform_name(self) -> str:
        return "fft" if self.azimuth_sgn < 0 else "ifft"

    @property
    def inverse_transform_name(self) -> str:
        return "ifft" if self.azimuth_sgn < 0 else "fft"

    @property
    def native_weight_warning(self) -> str | None:
        if (
            self.native_weight_name
            and self.native_weight_name.upper() not in {"UNIFORM", "UNKNOWN"}
            and not self.native_weight_samples_present
        ):
            return (
                f"Native {self.native_weight_name} weighting is declared without "
                "WgtFunct samples; exact deweighting is unavailable"
            )
        return None


@dataclass(frozen=True)
class ApertureDurations:
    """Explicitly distinct SICD processing and CPHD slow-time durations."""

    processed_aperture_duration_s: float
    sicd_timeline_collect_duration_s: float | None = None
    cphd_slow_time_dwell_s: float | None = None

    def __post_init__(self) -> None:
        if self.processed_aperture_duration_s <= 0:
            raise MetadataError("processed aperture duration must be positive")
        if (
            self.sicd_timeline_collect_duration_s is not None
            and self.sicd_timeline_collect_duration_s <= 0
        ):
            raise MetadataError("SICD Timeline.CollectDuration must be positive")
        if self.cphd_slow_time_dwell_s is not None and self.cphd_slow_time_dwell_s <= 0:
            raise MetadataError("CPHD dwell must be positive")

    def sicd_bandwidth_fraction(self, nominal_duration_s: float) -> float:
        """Return a nominal SICD bandwidth fraction using only processed time."""

        duration = float(nominal_duration_s)
        if duration <= 0:
            raise ValueError("nominal duration must be positive")
        tolerance = 32 * np.finfo(float).eps * self.processed_aperture_duration_s
        if duration > self.processed_aperture_duration_s + tolerance:
            raise ValueError(
                f"nominal SICD duration {duration:.12g} s exceeds processed aperture "
                f"duration {self.processed_aperture_duration_s:.12g} s; CPHD dwell "
                "cannot be substituted"
            )
        return min(1.0, duration / self.processed_aperture_duration_s)


@dataclass(frozen=True)
class SicdSubapertureContext:
    """Metadata needed to define reproducible SICD sub-apertures."""

    original_sicd_identifier: str
    collect_id: str | None
    axis: AxisConvention
    durations: ApertureDurations
    t_start_proc_from_collect_start_s: float

    @classmethod
    def from_sicd(
        cls,
        sicd: Any,
        *,
        cphd_slow_time_dwell_s: float | None = None,
    ) -> "SicdSubapertureContext":
        formation = getattr(sicd, "ImageFormation", None)
        timeline = getattr(sicd, "Timeline", None)
        if formation is None:
            raise MetadataError("ImageFormation is missing")
        start = float(getattr(formation, "TStartProc"))
        end = float(getattr(formation, "TEndProc"))
        if end <= start:
            raise MetadataError("ImageFormation TEndProc must exceed TStartProc")
        collect_duration = getattr(timeline, "CollectDuration", None)
        collection = getattr(sicd, "CollectionInfo", None)
        identifier = str(getattr(collection, "CoreName", "") or "UNKNOWN_SICD")
        collect_id = _metadata_parameter(getattr(collection, "Parameters", None), "collect_id")
        return cls(
            original_sicd_identifier=identifier,
            collect_id=collect_id,
            axis=AxisConvention.from_sicd(sicd),
            durations=ApertureDurations(
                processed_aperture_duration_s=end - start,
                sicd_timeline_collect_duration_s=(
                    None if collect_duration is None else float(collect_duration)
                ),
                cphd_slow_time_dwell_s=cphd_slow_time_dwell_s,
            ),
            t_start_proc_from_collect_start_s=start,
        )


@dataclass(frozen=True)
class ProcessedSupport:
    """Half-open bin support in an fftshifted spectrum."""

    start: int
    stop: int
    fft_size: int
    bin_spacing_per_m: float
    requested_lower_per_m: float
    requested_upper_per_m: float
    realized_lower_per_m: float
    realized_upper_per_m: float

    def __post_init__(self) -> None:
        if not (0 <= self.start < self.stop <= self.fft_size):
            raise ValueError("invalid processed-support bounds")

    @property
    def size(self) -> int:
        return self.stop - self.start

    @property
    def fraction_of_fft(self) -> float:
        return self.size / self.fft_size

    @classmethod
    def from_axis_metadata(cls, fft_size: int, axis: AxisConvention) -> "ProcessedSupport":
        n = int(fft_size)
        if n < 2:
            raise ValueError("fft_size must be at least 2")
        spacing = 1.0 / (n * axis.azimuth_sample_spacing_m)
        lower = axis.delta_kcoa_constant_per_m + axis.delta_k1_per_m
        upper = axis.delta_kcoa_constant_per_m + axis.delta_k2_per_m
        bins = int(round((upper - lower) / spacing))
        if not (1 <= bins <= n):
            raise MetadataError(
                f"metadata support implies {bins} bins for an FFT of size {n}"
            )
        center_frequency = 0.5 * (lower + upper)
        shifted_zero_index = n // 2
        center_index = shifted_zero_index + center_frequency / spacing
        start = int(round(center_index - bins / 2.0))
        stop = start + bins
        if start < 0 or stop > n:
            raise MetadataError("metadata support lies outside sampled FFT frequencies")
        realized_lower = (start - shifted_zero_index) * spacing
        realized_upper = realized_lower + bins * spacing
        return cls(
            start=start,
            stop=stop,
            fft_size=n,
            bin_spacing_per_m=spacing,
            requested_lower_per_m=lower,
            requested_upper_per_m=upper,
            realized_lower_per_m=realized_lower,
            realized_upper_per_m=realized_upper,
        )


@dataclass(frozen=True)
class SubapertureBand:
    """One half-open Doppler band and its explicitly nominal timing labels."""

    start: int
    stop: int
    support_start: int
    support_stop: int
    requested_nominal_duration_s: float
    requested_bandwidth_fraction: float
    realized_bandwidth_fraction: float
    realized_nominal_duration_s: float
    center_fraction_in_support: float
    nominal_center_time_from_collect_start_s: float
    timing_model: str = "nominal_linear_bandwidth_to_processed_time"

    def __post_init__(self) -> None:
        if not (self.support_start <= self.start < self.stop <= self.support_stop):
            raise ValueError("sub-aperture band is outside processed support")

    @property
    def size(self) -> int:
        return self.stop - self.start

    @property
    def center_bin(self) -> float:
        return 0.5 * (self.start + self.stop)


def plan_band(
    context: SicdSubapertureContext,
    support: ProcessedSupport,
    nominal_duration_s: float,
    *,
    center_fraction_in_support: float,
) -> SubapertureBand:
    """Plan a band at a normalized center within the processed support.

    Center fraction 0 is the lower support edge and 1 is the upper edge.  A band
    is accepted only when its complete half-open support lies inside the
    processed support.
    """

    fraction = context.durations.sicd_bandwidth_fraction(nominal_duration_s)
    bins = max(1, int(round(support.size * fraction)))
    bins = min(bins, support.size)
    center_fraction = float(center_fraction_in_support)
    if not 0 <= center_fraction <= 1:
        raise ValueError("center fraction must lie in [0, 1]")
    center = support.start + center_fraction * support.size
    start = int(round(center - bins / 2.0))
    stop = start + bins
    if start < support.start or stop > support.stop:
        raise ValueError("requested band extends beyond processed support")
    realized_fraction = bins / support.size
    realized_center_fraction = (0.5 * (start + stop) - support.start) / support.size
    processed_duration = context.durations.processed_aperture_duration_s
    return SubapertureBand(
        start=start,
        stop=stop,
        support_start=support.start,
        support_stop=support.stop,
        requested_nominal_duration_s=float(nominal_duration_s),
        requested_bandwidth_fraction=fraction,
        realized_bandwidth_fraction=realized_fraction,
        realized_nominal_duration_s=realized_fraction * processed_duration,
        center_fraction_in_support=realized_center_fraction,
        nominal_center_time_from_collect_start_s=(
            context.t_start_proc_from_collect_start_s
            + realized_center_fraction * processed_duration
        ),
    )


def plan_centered_band(
    context: SicdSubapertureContext,
    support: ProcessedSupport,
    nominal_duration_s: float,
) -> SubapertureBand:
    return plan_band(
        context,
        support,
        nominal_duration_s,
        center_fraction_in_support=0.5,
    )


def plan_tiled_bands(
    context: SicdSubapertureContext,
    support: ProcessedSupport,
    nominal_duration_s: float,
    *,
    overlap_fraction: float = 0.0,
) -> list[SubapertureBand]:
    """Plan a centered series of equally sized bands with explicit overlap."""

    if not 0 <= overlap_fraction < 1:
        raise ValueError("overlap_fraction must lie in [0, 1)")
    fraction = context.durations.sicd_bandwidth_fraction(nominal_duration_s)
    width = max(1, min(support.size, int(round(support.size * fraction))))
    step = max(1, int(round(width * (1.0 - overlap_fraction))))
    count = 1 + (support.size - width) // step
    span = width + (count - 1) * step
    first_start = support.start + (support.size - span) // 2
    bands: list[SubapertureBand] = []
    for index in range(count):
        start = first_start + index * step
        center_fraction = (start + width / 2.0 - support.start) / support.size
        bands.append(
            plan_band(
                context,
                support,
                nominal_duration_s,
                center_fraction_in_support=center_fraction,
            )
        )
    return bands


@dataclass(frozen=True)
class WindowMetrics:
    kind: str
    length: int
    tukey_alpha: float | None
    normalization: str
    applied_scale: float
    coherent_gain: float
    rms_gain: float
    energy_sum: float
    enbw_bins: float


def make_window(
    length: int,
    kind: WindowKind,
    *,
    tukey_alpha: float = 0.25,
    normalization: WindowNormalization = "energy",
) -> tuple[np.ndarray, WindowMetrics]:
    """Create a Doppler window and report its applied normalization.

    ``energy`` scales the window so that ``sum(abs(w)**2) == length``.  This
    matches the total energy of a rectangular window and is the default for
    comparable sub-look energy.  ENBW is scale invariant.
    """

    n = int(length)
    if n < 1:
        raise ValueError("window length must be positive")
    if kind == "rect":
        raw = np.ones(n, dtype=np.float64)
        alpha: float | None = None
    elif kind == "tukey":
        if not 0 <= tukey_alpha <= 1:
            raise ValueError("Tukey alpha must lie in [0, 1]")
        raw = tukey(n, alpha=float(tukey_alpha), sym=True).astype(np.float64)
        alpha = float(tukey_alpha)
    else:
        raise ValueError(f"unsupported window kind {kind!r}")

    if normalization == "none":
        scale = 1.0
    elif normalization == "energy":
        scale = float(np.sqrt(n / np.sum(np.abs(raw) ** 2)))
    elif normalization == "coherent":
        total = float(np.sum(raw))
        if total == 0:
            raise ValueError("window coherent gain is zero")
        scale = n / total
    else:
        raise ValueError(f"unsupported normalization {normalization!r}")
    window = raw * scale
    energy = float(np.sum(np.abs(window) ** 2))
    coherent_gain = float(np.sum(window) / n)
    rms_gain = float(np.sqrt(energy / n))
    enbw_bins = float(n * np.sum(np.abs(window) ** 2) / abs(np.sum(window)) ** 2)
    metrics = WindowMetrics(
        kind=kind,
        length=n,
        tukey_alpha=alpha,
        normalization=normalization,
        applied_scale=scale,
        coherent_gain=coherent_gain,
        rms_gain=rms_gain,
        energy_sum=energy,
        enbw_bins=enbw_bins,
    )
    return window, metrics


def _validated_axis(array: np.ndarray, axis: int) -> int:
    resolved = int(axis)
    if resolved < 0:
        resolved += array.ndim
    if not 0 <= resolved < array.ndim:
        raise ValueError(f"axis {axis} is invalid for shape {array.shape}")
    return resolved


def image_to_shifted_spectrum(
    image: np.ndarray,
    *,
    axis: int,
    sgn: int,
    workers: int | None = None,
) -> np.ndarray:
    """Transform a focused image to shifted spectrum using SICD Sgn.

    This matches SarPy ``fft_sicd``: Sgn=-1 selects FFT; Sgn=+1 selects IFFT.
    """

    data = np.asarray(image)
    resolved_axis = _validated_axis(data, axis)
    if sgn == -1:
        spectrum = scipy_fft.fft(data, axis=resolved_axis, workers=workers)
    elif sgn == 1:
        spectrum = scipy_fft.ifft(data, axis=resolved_axis, workers=workers)
    else:
        raise ValueError("SICD Sgn must be -1 or +1")
    return scipy_fft.fftshift(spectrum, axes=resolved_axis)


def shifted_spectrum_to_image(
    spectrum: np.ndarray,
    *,
    axis: int,
    sgn: int,
    workers: int | None = None,
) -> np.ndarray:
    """Inverse of :func:`image_to_shifted_spectrum`."""

    data = np.asarray(spectrum)
    resolved_axis = _validated_axis(data, axis)
    unshifted = scipy_fft.ifftshift(data, axes=resolved_axis)
    if sgn == -1:
        return scipy_fft.ifft(unshifted, axis=resolved_axis, workers=workers)
    if sgn == 1:
        return scipy_fft.fft(unshifted, axis=resolved_axis, workers=workers)
    raise ValueError("SICD Sgn must be -1 or +1")


def masked_spectrum(
    shifted_spectrum: np.ndarray,
    band: SubapertureBand,
    *,
    axis: int,
    window: np.ndarray,
) -> np.ndarray:
    """Return a full-sized spectrum containing only one windowed band."""

    spectrum = np.asarray(shifted_spectrum)
    resolved_axis = _validated_axis(spectrum, axis)
    weights = np.asarray(window)
    if weights.ndim != 1 or weights.size != band.size:
        raise ValueError("window length must equal band size")
    output = np.zeros_like(spectrum)
    selection = [slice(None)] * spectrum.ndim
    selection[resolved_axis] = slice(band.start, band.stop)
    reshape = [1] * spectrum.ndim
    reshape[resolved_axis] = weights.size
    output[tuple(selection)] = spectrum[tuple(selection)] * weights.reshape(reshape)
    return output


def sublook_from_spectrum(
    shifted_spectrum: np.ndarray,
    band: SubapertureBand,
    *,
    axis: int,
    sgn: int,
    window: np.ndarray,
    workers: int | None = None,
) -> np.ndarray:
    filtered = masked_spectrum(shifted_spectrum, band, axis=axis, window=window)
    return shifted_spectrum_to_image(filtered, axis=axis, sgn=sgn, workers=workers)


def sublook_metadata(
    context: SicdSubapertureContext,
    support: ProcessedSupport,
    band: SubapertureBand,
    window_metrics: WindowMetrics,
) -> dict[str, Any]:
    """Create JSON-ready provenance for a complex sub-look."""

    return {
        "original_sicd_identifier": context.original_sicd_identifier,
        "collect_id": context.collect_id,
        "grid_type": context.axis.grid_type,
        "range_axis": context.axis.range_axis,
        "fft_axis": context.axis.azimuth_axis,
        "sicd_col_sgn": context.axis.azimuth_sgn,
        "image_to_spectrum_transform": context.axis.forward_transform_name,
        "spectrum_to_image_transform": context.axis.inverse_transform_name,
        "durations": asdict(context.durations),
        "duration_usage_rule": (
            "SICD bandwidth fractions use processed_aperture_duration_s only; "
            "CPHD dwell is provenance for later slow-time mapping"
        ),
        "processed_support": asdict(support),
        "band": asdict(band),
        "window": asdict(window_metrics),
        "native_weight": {
            "name": context.axis.native_weight_name,
            "samples_present": context.axis.native_weight_samples_present,
            "warning": context.axis.native_weight_warning,
        },
        "complex_phase_preserved": True,
    }


def rectangular_partition(
    support: ProcessedSupport,
    edges: Sequence[int],
    *,
    context: SicdSubapertureContext,
) -> list[SubapertureBand]:
    """Build exact adjacent bands for numerical split/recombine tests."""

    values = [int(value) for value in edges]
    if values[0] != support.start or values[-1] != support.stop:
        raise ValueError("partition edges must cover the complete support")
    if any(a >= b for a, b in zip(values[:-1], values[1:])):
        raise ValueError("partition edges must be strictly increasing")
    duration = context.durations.processed_aperture_duration_s
    bands: list[SubapertureBand] = []
    for start, stop in zip(values[:-1], values[1:]):
        fraction = (stop - start) / support.size
        center_fraction = (0.5 * (start + stop) - support.start) / support.size
        bands.append(
            SubapertureBand(
                start=start,
                stop=stop,
                support_start=support.start,
                support_stop=support.stop,
                requested_nominal_duration_s=fraction * duration,
                requested_bandwidth_fraction=fraction,
                realized_bandwidth_fraction=fraction,
                realized_nominal_duration_s=fraction * duration,
                center_fraction_in_support=center_fraction,
                nominal_center_time_from_collect_start_s=(
                    context.t_start_proc_from_collect_start_s + center_fraction * duration
                ),
            )
        )
    return bands

