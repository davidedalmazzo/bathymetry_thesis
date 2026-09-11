from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path

import numpy as np
import pytest
from scipy import fft as scipy_fft
from sarpy.io.complex.sicd_elements.SICD import SICDType
from sarpy.processing.sicd.fft_base import fft_sicd

from umbra_sar.cross_spectrum import (
    CROSS_SPECTRUM_CONVENTION,
    intensity,
    spatial_cross_spectrum,
    wrapped_phase_error,
)
from umbra_sar.subaperture import (
    AxisConvention,
    MetadataError,
    ProcessedSupport,
    SicdSubapertureContext,
    SubapertureBand,
    image_to_shifted_spectrum,
    make_window,
    masked_spectrum,
    plan_centered_band,
    plan_tiled_bands,
    rectangular_partition,
    shifted_spectrum_to_image,
    sublook_from_spectrum,
    sublook_metadata,
)


ROOT = Path(__file__).resolve().parents[1]
SICD_XML = ROOT / "Vandenberg" / "metadata" / "SICD_METADATA.xml"
CPHD_DWELL_S = 22.540812513364376
SICD_PROCESSED_APERTURE_S = 18.068061721230308


def actual_context() -> SicdSubapertureContext:
    sicd = SICDType.from_xml_string(SICD_XML.read_bytes())
    return SicdSubapertureContext.from_sicd(
        sicd, cphd_slow_time_dwell_s=CPHD_DWELL_S
    )


def relative_error(actual: np.ndarray, expected: np.ndarray) -> float:
    return float(np.linalg.norm(actual - expected) / np.linalg.norm(expected))


def exact_band(start: int, stop: int, total: int) -> SubapertureBand:
    fraction = (stop - start) / total
    center_fraction = (start + stop) / (2 * total)
    return SubapertureBand(
        start=start,
        stop=stop,
        support_start=0,
        support_stop=total,
        requested_nominal_duration_s=fraction,
        requested_bandwidth_fraction=fraction,
        realized_bandwidth_fraction=fraction,
        realized_nominal_duration_s=fraction,
        center_fraction_in_support=center_fraction,
        nominal_center_time_from_collect_start_s=center_fraction,
    )


class Test01FftIfftRoundTripAndSign:
    @pytest.mark.parametrize("shape,axis", [((61, 128), 0), ((61, 128), 1)])
    @pytest.mark.parametrize("sgn", [-1, 1])
    def test_round_trip_near_floating_point(self, shape, axis, sgn):
        rng = np.random.default_rng(20260829 + axis + sgn)
        image = rng.normal(size=shape) + 1j * rng.normal(size=shape)
        spectrum = image_to_shifted_spectrum(image, axis=axis, sgn=sgn)
        reconstructed = shifted_spectrum_to_image(spectrum, axis=axis, sgn=sgn)
        assert relative_error(reconstructed, image) < 8e-15

    def test_col_sgn_minus_one_selects_fft_not_ifft(self):
        n = 256
        positive_bin = 29
        samples = np.arange(n)
        positive_tone = np.exp(2j * np.pi * positive_bin * samples / n)

        correct = image_to_shifted_spectrum(
            positive_tone[None, :], axis=1, sgn=-1
        )[0]
        explicitly_fft = scipy_fft.fftshift(scipy_fft.fft(positive_tone))
        explicitly_wrong_ifft = scipy_fft.fftshift(scipy_fft.ifft(positive_tone))

        assert np.argmax(np.abs(correct)) == n // 2 + positive_bin
        assert np.argmax(np.abs(explicitly_fft)) == n // 2 + positive_bin
        assert np.argmax(np.abs(explicitly_wrong_ifft)) == n // 2 - positive_bin
        assert relative_error(correct, explicitly_fft) < 1e-15
        assert relative_error(correct, explicitly_wrong_ifft) > 0.99

    def test_implementation_matches_sarpy_fft_sicd_for_actual_col_sgn(self):
        sicd = SICDType.from_xml_string(SICD_XML.read_bytes())
        rng = np.random.default_rng(314159)
        image = rng.normal(size=(17, 128)) + 1j * rng.normal(size=(17, 128))
        ours = image_to_shifted_spectrum(image, axis=1, sgn=int(sicd.Grid.Col.Sgn))
        sarpy_result = scipy_fft.fftshift(fft_sicd(image, 1, sicd), axes=1)
        assert int(sicd.Grid.Col.Sgn) == -1
        assert relative_error(ours, sarpy_result) < 2e-15


class Test02SplitRecombineAndWindows:
    def test_rectangular_partition_recombines_exactly(self):
        context = actual_context()
        n_rows, n_cols = 37, 256
        support = ProcessedSupport.from_axis_metadata(n_cols, context.axis)
        rng = np.random.default_rng(7)
        source_spectrum = np.zeros((n_rows, n_cols), dtype=np.complex128)
        source_spectrum[:, support.start : support.stop] = (
            rng.normal(size=(n_rows, support.size))
            + 1j * rng.normal(size=(n_rows, support.size))
        )
        image = shifted_spectrum_to_image(
            source_spectrum,
            axis=context.axis.azimuth_axis,
            sgn=context.axis.azimuth_sgn,
        )
        recovered_spectrum = image_to_shifted_spectrum(
            image,
            axis=context.axis.azimuth_axis,
            sgn=context.axis.azimuth_sgn,
        )
        edges = np.linspace(support.start, support.stop, 5, dtype=int).tolist()
        bands = rectangular_partition(support, edges, context=context)
        looks = []
        for band in bands:
            window, _ = make_window(band.size, "rect", normalization="none")
            looks.append(
                sublook_from_spectrum(
                    recovered_spectrum,
                    band,
                    axis=context.axis.azimuth_axis,
                    sgn=context.axis.azimuth_sgn,
                    window=window,
                )
            )
        reconstructed = np.sum(looks, axis=0)
        assert relative_error(reconstructed, image) < 8e-15

    def test_rectangular_and_tukey_metrics_and_energy_normalization(self):
        n = 1024
        rect, rect_metrics = make_window(n, "rect", normalization="energy")
        smooth, smooth_metrics = make_window(
            n, "tukey", tukey_alpha=0.25, normalization="energy"
        )
        assert np.all(rect == 1)
        assert rect_metrics.enbw_bins == pytest.approx(1.0, abs=1e-15)
        assert rect_metrics.energy_sum == pytest.approx(n, rel=2e-15)
        assert smooth_metrics.energy_sum == pytest.approx(n, rel=2e-15)
        assert smooth_metrics.rms_gain == pytest.approx(1.0, rel=2e-15)
        assert smooth_metrics.enbw_bins > 1.0
        assert smooth[0] == pytest.approx(0.0)
        assert smooth[-1] == pytest.approx(0.0)

    def test_sublook_metadata_records_native_sva_without_blocking(self):
        context = actual_context()
        support = ProcessedSupport.from_axis_metadata(107800, context.axis)
        band = plan_centered_band(context, support, 6.0)
        _, metrics = make_window(
            band.size, "tukey", tukey_alpha=0.25, normalization="energy"
        )
        metadata = sublook_metadata(context, support, band, metrics)
        assert metadata["native_weight"]["name"] == "SVA"
        assert metadata["native_weight"]["samples_present"] is False
        assert "exact deweighting is unavailable" in metadata["native_weight"]["warning"]
        assert metadata["complex_phase_preserved"] is True


class Test03AxisSelection:
    def test_actual_rgaizim_metadata_resolves_row_range_col_azimuth(self):
        context = actual_context()
        assert context.axis.grid_type == "RGAZIM"
        assert context.axis.range_axis == 0
        assert context.axis.azimuth_axis == 1
        assert context.axis.azimuth_sgn == -1
        assert context.axis.forward_transform_name == "fft"

    def test_known_modulation_is_selected_only_on_azimuth_axis(self):
        context = actual_context()
        rows, cols = 32, 256
        tone_bin = 41
        samples = np.arange(cols)
        image = np.repeat(
            np.exp(2j * np.pi * tone_bin * samples / cols)[None, :],
            rows,
            axis=0,
        )
        spectrum_col = image_to_shifted_spectrum(image, axis=1, sgn=-1)
        spectrum_row = image_to_shifted_spectrum(image, axis=0, sgn=-1)

        assert np.argmax(np.abs(spectrum_col[0])) == cols // 2 + tone_bin
        assert np.all(np.argmax(np.abs(spectrum_row), axis=0) == rows // 2)

        positive_band = exact_band(cols // 2 + 1, cols, cols)
        negative_band = exact_band(0, cols // 2, cols)
        positive_window, _ = make_window(
            positive_band.size, "rect", normalization="none"
        )
        negative_window, _ = make_window(
            negative_band.size, "rect", normalization="none"
        )
        retained = masked_spectrum(
            spectrum_col, positive_band, axis=1, window=positive_window
        )
        rejected = masked_spectrum(
            spectrum_col, negative_band, axis=1, window=negative_window
        )
        assert np.linalg.norm(retained) == pytest.approx(
            np.linalg.norm(spectrum_col), rel=2e-15
        )
        assert np.linalg.norm(rejected) / np.linalg.norm(spectrum_col) < 1e-14

    def test_non_rgazim_metadata_is_rejected(self):
        fake_col = SimpleNamespace(
            Sgn=-1,
            SS=1.0,
            DeltaK1=-0.4,
            DeltaK2=0.4,
            DeltaKCOAPoly=np.array([[0.0]]),
            WgtType=None,
            WgtFunct=None,
        )
        fake = SimpleNamespace(Grid=SimpleNamespace(Type="PLANE", Col=fake_col))
        with pytest.raises(MetadataError, match="not inferred"):
            AxisConvention.from_sicd(fake)


class Test04BandLocationAndDurationSeparation:
    @pytest.mark.parametrize("tone_bin", [-47, 47])
    def test_known_tone_reaches_expected_shifted_doppler_band(self, tone_bin):
        n = 256
        samples = np.arange(n)
        tone = np.exp(2j * np.pi * tone_bin * samples / n)
        spectrum = image_to_shifted_spectrum(tone[None, :], axis=1, sgn=-1)[0]
        peak = int(np.argmax(np.abs(spectrum)))
        assert peak == n // 2 + tone_bin
        if tone_bin < 0:
            assert peak < n // 2
        else:
            assert peak > n // 2

    def test_wrong_ifft_reverses_positive_negative_band_order(self):
        n = 256
        tone_bin = 47
        samples = np.arange(n)
        tone = np.exp(2j * np.pi * tone_bin * samples / n)
        correct = image_to_shifted_spectrum(tone, axis=0, sgn=-1)
        wrong = scipy_fft.fftshift(scipy_fft.ifft(tone))
        assert np.argmax(np.abs(correct)) == n // 2 + tone_bin
        assert np.argmax(np.abs(wrong)) == n // 2 - tone_bin

    def test_actual_sicd_support_six_second_plan_and_distinct_durations(self):
        context = actual_context()
        assert context.durations.processed_aperture_duration_s == pytest.approx(
            SICD_PROCESSED_APERTURE_S, abs=2e-13
        )
        assert context.durations.cphd_slow_time_dwell_s == pytest.approx(
            CPHD_DWELL_S, abs=2e-13
        )
        assert context.durations.sicd_timeline_collect_duration_s == pytest.approx(
            22.547940446666665, abs=2e-13
        )
        support = ProcessedSupport.from_axis_metadata(107800, context.axis)
        assert (support.start, support.stop, support.size) == (10780, 97020, 86240)
        centered = plan_centered_band(context, support, 6.0)
        assert centered.size == 28638
        assert centered.requested_bandwidth_fraction == pytest.approx(
            6.0 / SICD_PROCESSED_APERTURE_S, rel=2e-15
        )
        bands = plan_tiled_bands(context, support, 6.0, overlap_fraction=0.0)
        assert len(bands) == 3
        assert all(a.stop <= b.start for a, b in zip(bands[:-1], bands[1:]))
        realized_step_s = bands[0].realized_nominal_duration_s
        processed_center_s = (
            context.t_start_proc_from_collect_start_s
            + context.durations.processed_aperture_duration_s / 2
        )
        assert [band.nominal_center_time_from_collect_start_s for band in bands] == pytest.approx(
            [
                processed_center_s - realized_step_s,
                processed_center_s,
                processed_center_s + realized_step_s,
            ],
            abs=1e-12,
        )
        assert realized_step_s == pytest.approx(5.99992058873601, abs=1e-12)
        with pytest.raises(ValueError, match="CPHD dwell cannot be substituted"):
            context.durations.sicd_bandwidth_fraction(20.0)

    def test_explicit_overlap_produces_ordered_overlapping_bands(self):
        context = actual_context()
        support = ProcessedSupport.from_axis_metadata(107800, context.axis)
        bands = plan_tiled_bands(context, support, 6.0, overlap_fraction=0.5)
        assert len(bands) == 5
        assert all(a.start < b.start for a, b in zip(bands[:-1], bands[1:]))
        assert all(a.stop > b.start for a, b in zip(bands[:-1], bands[1:]))


class Test05CrossSpectrumPhaseSign:
    def test_known_intensity_wave_phase_is_positive_at_positive_peak(self):
        rows, cols = 48, 128
        row_bin, col_bin = 5, 13
        imposed_phase = 0.63
        rr = np.arange(rows)[:, None]
        cc = np.arange(cols)[None, :]
        argument = 2 * np.pi * (row_bin * rr / rows + col_bin * cc / cols)
        reference = 4.0 + 0.7 * np.cos(argument)
        secondary = 4.0 + 0.7 * np.cos(argument + imposed_phase)
        cross = spatial_cross_spectrum(reference, secondary)
        positive = (rows // 2 + row_bin, cols // 2 + col_bin)
        negative = (rows // 2 - row_bin, cols // 2 - col_bin)
        assert wrapped_phase_error(np.angle(cross[positive]), imposed_phase) < 2e-13
        assert abs(wrapped_phase_error(np.angle(cross[negative]), -imposed_phase)) < 2e-13
        swapped = spatial_cross_spectrum(secondary, reference)
        assert abs(wrapped_phase_error(np.angle(swapped[positive]), -imposed_phase)) < 2e-13
        assert "F_secondary" in CROSS_SPECTRUM_CONVENTION

    def test_col_sgn_minus_one_end_to_end_band_order_and_cross_phase(self):
        rows, cols = 24, 256
        center = cols // 2
        low_carrier = -52
        high_carrier = 31
        wave_bin = 7
        imposed_phase = 0.71

        shifted = np.zeros((rows, cols), dtype=np.complex128)
        shifted[:, center + low_carrier] = 1.0
        shifted[:, center + low_carrier + wave_bin] = 0.65
        shifted[:, center + high_carrier] = 1.0
        shifted[:, center + high_carrier + wave_bin] = 0.65 * np.exp(1j * imposed_phase)

        full_image = shifted_spectrum_to_image(shifted, axis=1, sgn=-1)
        recovered = image_to_shifted_spectrum(full_image, axis=1, sgn=-1)
        wrong = scipy_fft.fftshift(scipy_fft.ifft(full_image, axis=1), axes=1)

        expected_peaks = {
            center + low_carrier,
            center + low_carrier + wave_bin,
            center + high_carrier,
            center + high_carrier + wave_bin,
        }
        recovered_peaks = set(np.argsort(np.abs(recovered[0]))[-4:].tolist())
        wrong_peaks = set(np.argsort(np.abs(wrong[0]))[-4:].tolist())
        assert recovered_peaks == expected_peaks
        assert all(index < center for index in sorted(expected_peaks)[:2])
        assert all(index > center for index in sorted(expected_peaks)[2:])
        assert wrong_peaks != expected_peaks

        low_band = exact_band(center - 70, center - 30, cols)
        high_band = exact_band(center + 20, center + 60, cols)
        low_window, _ = make_window(low_band.size, "rect", normalization="none")
        high_window, _ = make_window(high_band.size, "rect", normalization="none")
        low_look = sublook_from_spectrum(
            recovered, low_band, axis=1, sgn=-1, window=low_window
        )
        high_look = sublook_from_spectrum(
            recovered, high_band, axis=1, sgn=-1, window=high_window
        )
        cross = spatial_cross_spectrum(intensity(low_look), intensity(high_look))
        positive_wave_peak = (rows // 2, cols // 2 + wave_bin)
        measured = float(np.angle(cross[positive_wave_peak]))
        assert abs(wrapped_phase_error(measured, imposed_phase)) < 3e-13
