"""Block15F: read PVP geometry and evaluate a limited look-dependent transfer.

Never accesses the CPHD signal block. New outputs refuse replacement.
"""
import argparse,csv,hashlib,json
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
from umbra_sar.backprojection import CphdChannel,build_ground_grid
from umbra_sar.look_transfer_geometry import unit,signed_angle,finite_depth_omega,transfer_terms,phase_slope

ROOT=Path(__file__).resolve().parents[1];V=ROOT/'Vandenberg';OUT=V/'results/analysis_block15';CFG=OUT/'BLOCK15F_CONFIG.json'
CPHD=V/'2025-02-16-18-55-44_UMBRA-10_CPHD.cphd';META=V/'metadata/CPHD_METADATA.json';MAN=V/'results/block12_backprojection/BLOCK12_SUBLOOK_MANIFEST.json'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(path,obj):
    with Path(path).open('x',encoding='utf8') as f:json.dump(obj,f,indent=2)
def bearing(v,east,north):return float(np.degrees(np.arctan2(v@east,v@north))%360)

def setup():
    d=json.loads(MAN.read_text());a=json.loads((OUT/'BLOCK15D_CONFIG.json').read_text());
    guards={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in [MAN,META,OUT/'BLOCK15D_CONFIG.json',OUT/'BLOCK15D_RESULTS.json',OUT/'BLOCK15E_CONFIG.json',OUT/'BLOCK15E_REPORT.md',ROOT/'code/umbra_sar/backprojection.py',ROOT/'code/umbra_sar/ocean_sar_forward.py',ROOT/'code/analyze_block10_ocean_sar_forward.py']}
    cfg=dict(created_utc=datetime.now(timezone.utc).isoformat(),scope='PVP-only geometry; limited linear intensity-coefficient transfer; no radar signal read',
      fixed_peak=dict(index=a['fixed_peak'],kx_rad_m=-.04799655442984407,ky_rad_m=0.,convention='FFT of linearly detrended BP12 intensity; first grid axis kx, second ky; selected representative not reselected'),
      surface_grid=d['grid'],look_edges_s=d['look_edges_tx_time_s'],representative_time='exact arithmetic mean TxTime of pulses assigned to look',
      transfer_scenarios=[dict(name='T13_depth5',period_s=13.33,depth_m=5.,tilt_scale=1.),dict(name='T13_depth10',period_s=13.33,depth_m=10.,tilt_scale=1.),dict(name='T13_depth20',period_s=13.33,depth_m=20.,tilt_scale=1.),dict(name='T17p902_depth10',period_s=17.902230457,depth_m=10.,tilt_scale=1.)],
      model='H=T_t+T_vb; T_h=0 because no locally verified X-band hydrodynamic/relaxation MTF. T_vb is density/Jacobian only, no separate displacement/shift MTF.',
      external_period_note='13.33 s is a diagnostic association hypothesis only; 17.902230457 s remains frozen SAR-only value, neither calibrates parameters.',guard_sha256=guards,
      source_sha256={p:sha(ROOT/p) for p in ['code/analyze_block15f_look_geometry.py','code/umbra_sar/look_transfer_geometry.py','tests/test_look_transfer_geometry.py']})
    save(CFG,cfg)

def geometry():
    cfg=json.loads(CFG.read_text());c=CphdChannel.open(CPHD,META);grid=cfg['surface_grid'];g=build_ground_grid(center_easting_m=grid['center_easting_northing_m'][0],center_northing_m=grid['center_easting_northing_m'][1],utm_zone=grid['utm_zone'],bearing_deg=grid['bearing_deg'],length_parallel_m=grid['length_parallel_m'],length_perpendicular_m=grid['length_perpendicular_m'],spacing_m=grid['spacing_m'],surface_hae_m=grid['surface_hae_m'])
    ni,nj=g.shape; target=g.ecf_m[(ni//2)*nj+nj//2]; axis0=unit(g.ecf_m[((ni//2+1)*nj+nj//2)]-target).reshape(3);axis1=unit(g.ecf_m[(ni//2)*nj+nj//2+1]-target).reshape(3);up=unit(np.cross(axis0,axis1)).reshape(3)
    # orient up outward
    if up@target<0:up=-up
    east=unit(np.cross(np.array([0.,0.,1.]),up)).reshape(3);north=unit(np.cross(up,east)).reshape(3)
    t=c.tx_time_s;p=c.tx_position_ecf_m;vel=np.gradient(p,t,axis=0);k=cfg['fixed_peak'];kv=k['kx_rad_m']*axis0+k['ky_rad_m']*axis1
    rows=[]; details=[]
    for j,(lo,hi) in enumerate(zip(cfg['look_edges_s'][:-1],cfg['look_edges_s'][1:])):
        ind=np.where((t>=lo)&((t<hi) if j<31 else (t<=hi)))[0];pos=p[ind];v=vel[ind];los=unit(pos-target);rng=np.linalg.norm(pos-target,axis=1);inc=np.arccos(np.clip(los@up,-1,1));lh=unit(los-(los@up)[:,None]*up);fh=unit(v-(v@up)[:,None]*up);speed=np.linalg.norm(v,axis=1);squint=np.array([signed_angle(f,ell,up) for f,ell in zip(fh,lh)])
        # geometry per pulse; representative evaluation at mean geometry is separately reported
        def interval(x):return (float(np.mean(x)),float(np.min(x)),float(np.max(x)),float(np.ptp(x)))
        rec=dict(look=j, pulses=len(ind),tx_time_mean_s=float(t[ind].mean()),tx_time_min_s=float(t[ind].min()),tx_time_max_s=float(t[ind].max()),
          slant_range_mean_m=interval(rng)[0],slant_range_min_m=interval(rng)[1],slant_range_max_m=interval(rng)[2],slant_range_ptp_m=interval(rng)[3],
          speed_mean_m_s=float(speed.mean()),speed_min_m_s=float(speed.min()),speed_max_m_s=float(speed.max()),speed_ptp_m_s=float(np.ptp(speed)),
          R_over_V_mean_s=float(np.mean(rng/speed)),R_over_V_ptp_s=float(np.ptp(rng/speed)),incidence_mean_deg=float(np.degrees(inc.mean())),incidence_min_deg=float(np.degrees(inc.min())),incidence_max_deg=float(np.degrees(inc.max())),incidence_ptp_deg=float(np.degrees(np.ptp(inc))),
          view_azimuth_mean_deg=bearing(unit(lh.mean(axis=0)).reshape(3),east,north),flight_azimuth_mean_deg=bearing(unit(fh.mean(axis=0)).reshape(3),east,north),squint_mean_deg=float(np.degrees(np.mean(squint))),squint_min_deg=float(np.degrees(np.min(squint))),squint_max_deg=float(np.degrees(np.max(squint))),squint_ptp_deg=float(np.degrees(np.ptp(squint))),
          k_los_mean_rad_m=float(np.mean(lh@kv)),k_flight_mean_rad_m=float(np.mean(fh@kv)),k_axis0_rad_m=float(k['kx_rad_m']),k_axis1_rad_m=float(k['ky_rad_m']))
        rows.append(rec);details.append(dict(indices=[int(ind[0]),int(ind[-1])],position_mean_ecf_m=pos.mean(0).tolist(),velocity_mean_ecf_m_s=v.mean(0).tolist(),representative_time_s=rec['tx_time_mean_s']))
    with (OUT/'BLOCK15F_LOOK_GEOMETRY.csv').open('x',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    save(OUT/'BLOCK15F_GEOMETRY.json',dict(target_ecf_m=target.tolist(),surface_hae_m=grid['surface_hae_m'],axis0_ecf=axis0.tolist(),axis1_ecf=axis1.tolist(),up_ecf=up.tolist(),east_ecf=east.tolist(),north_ecf=north.tolist(),k_vector_ecf_rad_m=kv.tolist(),k_magnitude_rad_m=float(np.linalg.norm(kv)),looks=details,rows=rows,pvp_signal_block_read=False))

def run():
    cfg=json.loads(CFG.read_text()); geo=json.loads((OUT/'BLOCK15F_GEOMETRY.json').read_text());rows=geo['rows'];looks=geo['looks'];kv=np.array(geo['k_vector_ecf_rad_m']);up=np.array(geo['up_ecf']);t=np.array([x['tx_time_mean_s'] for x in rows]);transfer=[]
    # reconstruct representative LOS/flight from stored vectors
    target=np.array(geo['target_ecf_m'])
    for scenario in cfg['transfer_scenarios']:
        omega=2*np.pi/scenario['period_s'];H=[];terms=[]
        for detail,row in zip(looks,rows):
            los=unit(np.array(detail['position_mean_ecf_m'])-target).reshape(3);lh=unit(los-(los@up)*up).reshape(3);v=np.array(detail['velocity_mean_ecf_m_s']);fh=unit(v-(v@up)*up).reshape(3)
            term=transfer_terms(k_vector=kv,los_horizontal=lh,flight_horizontal=fh,incidence_rad=np.deg2rad(row['incidence_mean_deg']),range_over_speed_s=row['R_over_V_mean_s'],omega_rad_s=omega,depth_m=scenario['depth_m'],tilt_scale=scenario['tilt_scale']);terms.append(term);H.append(term['H'])
        H=np.array(H); hphase=np.unwrap(np.angle(H));st,_=phase_slope(t,H); curvature=float(np.sqrt(np.mean((hphase-np.polyval(np.polyfit(t,hphase,1),t))**2)));rel=abs(H)/np.median(abs(H));cancellation=np.array([abs(x['H'])/(abs(x['T_t'])+abs(x['T_vb'])) for x in terms])
        # synthetic single coefficient, estimator A-equivalent unwrapped OLS
        sw=.4; recovered,_=phase_slope(t,H*np.exp(1j*sw*t));constant,_=phase_slope(t,np.full(32,H[16])*np.exp(1j*sw*t))
        for i,x in enumerate(terms):transfer.append(dict(scenario=scenario['name'],look=i,time_s=t[i],H_real=x['H'].real,H_imag=x['H'].imag,H_abs=abs(x['H']),H_phase_rad=float(np.angle(x['H'])),Tt_real=x['T_t'].real,Tt_imag=x['T_t'].imag,Tvb_real=x['T_vb'].real,Tvb_imag=x['T_vb'].imag,cancellation_ratio=float(cancellation[i]),relative_abs=float(rel[i]),transfer_slope_rad_s=st,phase_curvature_rms_rad=curvature,synthetic_imposed_s_wave=.4,synthetic_recovered_variable_s=recovered,synthetic_recovered_constant_s=constant))
    with (OUT/'BLOCK15F_TRANSFER_RESULTS.csv').open('x',newline='') as f:w=csv.DictWriter(f,fieldnames=list(transfer[0]));w.writeheader();w.writerows(transfer)
    save(OUT/'BLOCK15F_RESULTS.json',dict(transfer=transfer,convention='z_j=A H_j exp(i s_wave t_j); arg(z_j conj(z_r))=s_wave delta_t+arg(H_j conj(H_r)); conjugation reverses both slopes',not_a_frequency_correction=True))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['setup','geometry','run']);a=p.parse_args();globals()[a.mode]()
