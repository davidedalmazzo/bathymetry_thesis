import numpy as np
import pytest

from umbra_sar.reference_recovery import (
    HTTPBudget, nearest_time_index, normalize_payload, parse_dds_dimensions, spectrum_metrics,
    validity_mask, variable_attributes,
)

DDS="""Dataset { Float64 time[time = 12]; Float32 frequency[frequency = 3]; Float32 spectral_wave_density[time = 12][frequency = 3][latitude = 1][longitude = 1]; } x;"""
DAS="""Attributes {
 spectral_wave_density { String units "m2 Hz-1"; Float32 _FillValue -999.0; }
 mean_wave_dir { String units "degree_true"; Float32 _FillValue 999.0; }
 principal_wave_dir { Float32 missing_value 999.0; }
 wave_spectrum_r1 { Float32 _FillValue 9.99; }
 wave_spectrum_r2 { Float32 _FillValue 9.99; }
}"""
ASCII="""frequency[3]
0.05, 0.07, 0.10

spectral_wave_density.spectral_wave_density[1][3][1][1]
[0][0][0][0], 1
[0][1][0][0], 2
[0][2][0][0], 1

mean_wave_dir.mean_wave_dir[1][3][1][1]
[0][0][0][0], 99
[0][1][0][0], 100
[0][2][0][0], 101

principal_wave_dir.principal_wave_dir[1][3][1][1]
[0][0][0][0], 90
[0][1][0][0], 91
[0][2][0][0], 92

wave_spectrum_r1.wave_spectrum_r1[1][3][1][1]
[0][0][0][0], .8
[0][1][0][0], .7
[0][2][0][0], .6

wave_spectrum_r2.wave_spectrum_r2[1][3][1][1]
[0][0][0][0], .6
[0][1][0][0], .5
[0][2][0][0], .4
"""


def test_dynamic_dimensions_not_fixed_98():
    assert parse_dds_dimensions(DDS)=={"time":12,"frequency":3,"latitude":1,"longitude":1}


def test_variable_specific_missing_keeps_valid_99_degree_direction():
    attrs=variable_attributes(DAS,"mean_wave_dir")
    m=validity_mask([99,999],variable="mean_wave_dir",attrs=attrs)
    assert m.tolist()==[True,False]


def test_normalization_joint_mask_and_bin_sum_reproducible_offline():
    a=normalize_payload(ASCII,DAS,observation_epoch_s=1)
    b=normalize_payload(ASCII,DAS,observation_epoch_s=1)
    assert np.array_equal(a["joint_mask"],b["joint_mask"])
    assert a["joint_band_energy_coverage"]==1
    assert spectrum_metrics(a)==spectrum_metrics(b)


def test_duplicate_frequency_rejected():
    with pytest.raises(ValueError,match="duplicate"):
        normalize_payload(ASCII.replace("0.05, 0.07, 0.10","0.05, 0.07, 0.07"),DAS,observation_epoch_s=1)


def test_budget_enforced_during_chunks():
    b=HTTPBudget(2,10,6,1,0,4); b.reserve_transaction(); b.accept_chunk(0,4)
    with pytest.raises(RuntimeError,match="response"):
        b.accept_chunk(4,4)


def test_timestamp_is_selected_from_coordinate_not_stale_index():
    index,epoch=nearest_time_index([100,200,300,400],305)
    assert (index,epoch)==(2,300)


def test_actual_recovered_payloads_parse_offline_with_dynamic_shape():
    from pathlib import Path
    das=Path("Block18_reference_recovery/payloads_raw/42084w9999.das").read_text()
    files=sorted(Path("Block18_reference_recovery/payloads_raw").glob("*_spectrum.ascii"))
    assert len(files)==4
    for path in files:
        n=normalize_payload(path.read_text(),das,observation_epoch_s=0)
        assert len(n["frequency_hz"])==98 and n["joint_band_energy_coverage"]==1


def test_metric_uses_band_width_sum_not_gap_bridging():
    missing=ASCII.replace("[0][1][0][0], 2","[0][1][0][0], -999")
    n=normalize_payload(missing,DAS,observation_epoch_s=1)
    # endpoint widths are 0.02 and 0.03; missing middle contributes nothing
    assert np.isclose(spectrum_metrics(n)["m0_m2"],.05)
