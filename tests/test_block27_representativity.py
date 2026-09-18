"""Offline regression for resumed Block27 provenance and same-band direction."""
from repository_paths import resolve_historical
import importlib.util
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('block27_repr',ROOT/'code/run_block27_representativity.py')
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

def test_direction_uses_same_peak_band_and_circular_mean():
    n={'frequency_hz':np.array([.05,.06,.07,.08]),
       'band_width_hz':np.full(4,.01),
       'arrays':{'spectral_wave_density':np.array([1.,4.,4.,1.]),
                 'mean_wave_dir':np.array([90.,359.,1.,90.]),
                 'wave_spectrum_r1':np.ones(4)},
       'masks':{'spectral_wave_density':np.ones(4,bool),
                'mean_wave_dir':np.ones(4,bool),'wave_spectrum_r1':np.ones(4,bool)}}
    r=mod.same_band(n)
    assert r['band_low_hz']==.06 and r['band_high_hz']==.07
    assert abs(r['band_propagation_to_deg']-180)<1e-10

def test_bearing_true_north_clockwise():
    assert abs(mod.bearing(mod.Point(0,0),mod.Point(0,1)))<1e-12
    assert abs(mod.bearing(mod.Point(0,0),mod.Point(1,0))-90)<1e-12

def test_offline_reused_reference_distinct_from_nearest_station():
    rr=mod.read(ROOT/'umbra/selezione_scene/Block27_frequency_query/representativity_v1/ACQUISITION_AUDIT.csv')
    reused=[r for r in rr if r['reference_status']=='verified_local_Block18']
    assert len(reused)==4
    assert all(r['reference_station_id']=='42084' for r in reused)
    assert all(r['station_id']=='42094' for r in reused)
    # The nearest station of any instrument type is GRBL1, not the wave buoy.
    assert all(r['nearest_historical_station']=='GRBL1' for r in reused)
    assert all(mod.sha(resolve_historical(r['payload_path'], ROOT))==r['payload_sha256'] for r in reused)
