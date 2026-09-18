import importlib.util
from pathlib import Path
import math

spec = importlib.util.spec_from_file_location("block30", Path(__file__).parents[1] / "code/run_block30_frf_conditions.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def test_ascii_multiple_vectors():
    text = "Dataset {} file;\n--------------------\ntime[3]\n1, 2, 3\n\nwaveHs[3]\n1.1, -999, NaN\n"
    assert m.parse_ascii_vector(text, "time") == [1, 2, 3]
    hs = m.parse_ascii_vector(text, "waveHs")
    assert hs[:2] == [1.1, -999]
    assert math.isnan(hs[2])


def test_epoch_and_filename():
    assert m.epoch_from_units("seconds since 1970-01-01 00:00:00") == 0
    assert m.dap_url("waverider-17m", "202110", ".das").endswith("/2021/FRF-ocean_waves_waverider-17m_202110.nc.das")


def test_dispersion_diagnostic():
    c, k = m.celerity(9.547, 17.8)
    assert 100 < 2 * math.pi / k < 120
    assert abs(m.G * k * math.tanh(k * 17.8) - (2 * math.pi / 9.547)**2) < 1e-10
