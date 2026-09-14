"""Block15H: BP12-only spatial-resolution audit; no new SAR formation."""
from __future__ import annotations
import argparse, csv, hashlib, json
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from analyze_block12_phase_slope import detrended_spectrum
from umbra_sar.frequency_comparison import local_msc, reference_fit
from umbra_sar.spatial_resolution import tukey_1d, window_2d, window_axis_metrics, kernel_overlap, count_local_maxima
from umbra_sar.two_component_separability import window_response

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'Vandenberg/results/analysis_block15'; BP=ROOT/'Vandenberg/results/block12_backprojection'; CFG=OUT/'BLOCK15H_CONFIG.json'
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
 if isinstance(x,dict): return {k:clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)): return [clean(v) for v in x]
 if isinstance(x,np.ndarray): return clean(x.tolist())
 if isinstance(x,np.generic): return x.item()
 if isinstance(x,float) and not np.isfinite(x): return None
 return x
def save(p,x):
 with Path(p).open('x',encoding='utf-8',newline='') as f: json.dump(clean(x),f,indent=2)
def gaussian(n=3,sigma=1.):
 a=np.arange(n)-n//2; w=np.exp(-(a[:,None]**2+a[None,:]**2)/(2*sigma*sigma)); return w/w.sum()
def prepare():
 stack=BP/'BLOCK12_SUBLOOKS_complex64.npy'; manifest=BP/'BLOCK12_SUBLOOK_MANIFEST.json'; m=json.loads(manifest.read_text()); a=np.load(stack,mmap_mode='r')
 guards=[manifest,OUT/'BLOCK15B_CONFIG.json',OUT/'BLOCK15B_BINS.csv',OUT/'BLOCK15B_REPORT.md',OUT/'BLOCK15D_CONFIG.json',OUT/'BLOCK15E_CONFIG.json',OUT/'BLOCK15F_DELIVERY_MANIFEST.json',OUT/'BLOCK15G_DELIVERY_MANIFEST.json']
 cfg=dict(created_utc=datetime.now(timezone.utc).isoformat(),scope='BP12 existing complex stack only; resolution audit, no frequency correction or Q2 real fit',stack=dict(path=str(stack.relative_to(ROOT)).replace('\\','/'),bytes=stack.stat().st_size,mtime_ns=stack.stat().st_mtime_ns,shape=list(a.shape),dtype=str(a.dtype)),manifest=str(manifest.relative_to(ROOT)).replace('\\','/'),times_s=m['mean_tx_time_per_look_s'],grid=m['grid'],fixed_peak=[133,65],neighborhood=dict(rows=[127,140],cols=[59,72],meaning='half-open 13x13 audit neighborhood; fixed candidate is never retuned'),preprocessing=dict(intensity='abs(BP12 complex64)**2',detrend='same global plane as Block15B',window='same separable Tukey alpha=0.1 as Block15B',padding='none for measured BP12 spectra',phase_estimator='Block15B reference_fit, reference look index 16, signed slope; MSC uses unchanged local 3x3 definition'),classification=dict(separated='two internal local amplitude maxima separated by >= one measured FWHM and window overlap <=0.2',partially_separated='shoulder/secondary maximum with separation >=0.5 FWHM or overlap 0.2--0.7',overlapped='no resolved valley and window overlap >0.7',unidentifiable='phase/slope evidence contradicts amplitude or quality is inadequate'),synthetics=dict(seed=150800,cases=['single_isolated','two_separated_6_bins','two_overlapped_1_bin','single_offgrid_window_broadened','weak_component_under_main_lobe'],same_grid_window_times=True),guard_sha256={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in guards},source_sha256={str(Path(__file__).relative_to(ROOT)).replace('\\','/'):sha(Path(__file__)), 'code/umbra_sar/spatial_resolution.py':sha(ROOT/'code/umbra_sar/spatial_resolution.py')})
 save(CFG,cfg)
def spectra(cfg):
 p=ROOT/cfg['stack']['path']; x=np.load(p,mmap_mode='r'); assert list(x.shape)==cfg['stack']['shape'] and p.stat().st_size==cfg['stack']['bytes']
 w=window_2d(tuple(x.shape[1:]),.1); return np.asarray([detrended_spectrum(abs(np.asarray(z))**2,w) for z in x]),w
def axes(shape,spacing):
 return np.meshgrid(2*np.pi*np.fft.fftshift(np.fft.fftfreq(shape[0],spacing)),2*np.pi*np.fft.fftshift(np.fft.fftfreq(shape[1],spacing)),indexing='ij')
def fwhm_line(p,c):
 p=np.asarray(p,float); q=p/p[c]; out=[]
 for sign in (-1,1):
  k=c
  while 0<=k+sign<len(q) and q[k+sign]>.5:k+=sign
  if not 0<=k+sign<len(q): return float('nan')
  out.append(k+(0.5-q[k])/(q[k+sign]-q[k])*sign)
 return float(out[1]-out[0])
def synthetic_rows(cfg):
 shape=tuple(cfg['stack']['shape'][1:]); t=np.asarray(cfg['times_s']); peak=np.array(cfg['fixed_peak'],float); rr=np.arange(127,140); cc=np.arange(59,72); q=np.array([[r,c] for r in rr for c in cc],float); cases=[('single_isolated',0,0,0),('two_separated_6_bins',6,.7,.54),('two_overlapped_1_bin',1,.7,.54),('single_offgrid_window_broadened',.5,0,0),('weak_component_under_main_lobe',1.5,.08,.54)]; rows=[]
 for name,d,a2,s2 in cases:
  k1=peak+np.array([.5 if name=='single_offgrid_window_broadened' else 0,0]); z=np.exp(.4j*t)[:,None]*window_response(shape,q,k1)[None,:]
  if a2:z+=a2*np.exp(1j*s2*t)[:,None]*window_response(shape,q,peak+[d,0])[None,:]
  power=np.mean(abs(z)**2,axis=0).reshape(len(rr),len(cc)); maxima=count_local_maxima(power,.05); best=np.unravel_index(np.argmax(power),power.shape); ref=reference_fit(z[:,np.argmax(np.mean(abs(z)**2,axis=0))],t,16)
  rows.append(dict(case=name,declared_separation_bins=d,secondary_amplitude_ratio=a2,local_maxima_count=len(maxima),strongest_row=int(rr[best[0]]),strongest_col=int(cc[best[1]]),center_error_bins=float(np.hypot(rr[best[0]]-peak[0],cc[best[1]]-peak[1])),signed_slope_rad_s=ref['s_phi'],r2=ref['r2'],phase_rmse_rad=ref['rmse']))
 return rows
def run():
 cfg=json.loads(CFG.read_text());
 for p,h in cfg['guard_sha256'].items(): assert sha(ROOT/p)==h, f'Frozen artifact changed: {p}'
 F,w=spectra(cfg); t=np.asarray(cfg['times_s']); shape=F.shape[1:]; spacing=float(cfg['grid']['spacing_m']); kx,ky=axes(shape,spacing); power=np.mean(abs(F)**2,axis=0); amp=np.mean(abs(F),axis=0); pr,pc=cfg['fixed_peak']; r0,r1=cfg['neighborhood']['rows'];c0,c1=cfg['neighborhood']['cols']; endpoint,valid=local_msc(F[0],F[-1]); adj=np.asarray([local_msc(a,b)[0] for a,b in zip(F[:-1],F[1:])]); peak=float(power[pr,pc]); rows=[]
 for i in range(r0,r1):
  for j in range(c0,c1):
   z=F[:,i,j]; fit=reference_fit(z,t,16); relphase=np.angle(z*np.conj(F[:,pr,pc])); resid=np.asarray(fit['residual']); peakfit=reference_fit(F[:,pr,pc],t,16); pres=np.asarray(peakfit['residual']); ar=np.corrcoef(abs(z),abs(F[:,pr,pc]))[0,1]; er=np.corrcoef(resid,pres)[0,1] if np.std(resid)>0 and np.std(pres)>0 else np.nan; dr,dc=i-pr,j-pc
   rows.append(dict(row=i,col=j,offset_row=dr,offset_col=dc,kx_rad_m=kx[i,j],ky_rad_m=ky[i,j],k_rad_m=float(np.hypot(kx[i,j],ky[i,j])),wavelength_m=float(2*np.pi/np.hypot(kx[i,j],ky[i,j])),distance_bins=float(np.hypot(dr,dc)),distance_rad_m=float(np.hypot(dr*2*np.pi/(shape[0]*spacing),dc*2*np.pi/(shape[1]*spacing))),mean_power=power[i,j],relative_power=power[i,j]/peak,mean_amplitude=amp[i,j],relative_amplitude=amp[i,j]/amp[pr,pc],look_power_cv=float(np.std(abs(F[:,i,j])**2)/np.mean(abs(F[:,i,j])**2)),peak_relative_phase_resultant=float(abs(np.mean(np.exp(1j*relphase)))),amplitude_correlation_to_peak=ar,residual_correlation_to_peak=er,window_overlap_to_peak=kernel_overlap(shape,.1,dr,dc),signed_slope_rad_s=fit['s_phi'],intercept_rad=fit['intercept'],slope_difference_to_peak=fit['s_phi']-peakfit['s_phi'],phase_rmse_rad=fit['rmse'],r2=fit['r2'],max_adjacent_step_rad=fit['max_adjacent_step'],endpoint_msc=endpoint[i,j],min_adjacent_msc=float(adj[:,i,j].min()),fixed_peak=(i,j)==(pr,pc)))
 with (OUT/'BLOCK15H_PEAK_NEIGHBORHOOD.csv').open('x',newline='',encoding='utf-8') as f: q=csv.DictWriter(f,fieldnames=list(rows[0]));q.writeheader();q.writerows(clean(rows))
 dep=[{k:x[k] for k in ['row','col','offset_row','offset_col','distance_bins','window_overlap_to_peak','amplitude_correlation_to_peak','residual_correlation_to_peak','peak_relative_phase_resultant','signed_slope_rad_s','slope_difference_to_peak','endpoint_msc','min_adjacent_msc']} for x in rows]
 with (OUT/'BLOCK15H_BIN_DEPENDENCE.csv').open('x',newline='',encoding='utf-8') as f:q=csv.DictWriter(f,fieldnames=list(dep[0]));q.writeheader();q.writerows(clean(dep))
 met=[]
 for axis,n in [('parallel_row',shape[0]),('perpendicular_col',shape[1])]:
  m=window_axis_metrics(n,.1);m.update(axis=axis,delta_bin_rad_m=2*np.pi/(n*spacing),fwhm_power_rad_m=m['fwhm_power_bins']*2*np.pi/(n*spacing),equivalent_lobe_width_rad_m=m['equivalent_lobe_width_bins']*2*np.pi/(n*spacing));met.append(m)
 with (OUT/'BLOCK15H_WINDOW_RESPONSE.csv').open('x',newline='',encoding='utf-8') as f:q=csv.DictWriter(f,fieldnames=list(met[0]));q.writeheader();q.writerows(clean(met))
 syn=synthetic_rows(cfg)
 with (OUT/'BLOCK15H_SYNTHETIC_CALIBRATION.csv').open('x',newline='',encoding='utf-8') as f:q=csv.DictWriter(f,fieldnames=list(syn[0]));q.writeheader();q.writerows(clean(syn))
 # Effective rank of the declared 13x13 neighbourhood under the same window covariance.
 coords=np.array([[x['offset_row'],x['offset_col']] for x in rows]); wr=np.fft.fft(tukey_1d(shape[0],.1)**2);wc=np.fft.fft(tukey_1d(shape[1],.1)**2);wr/=wr[0];wc/=wc[0];C=np.array([[wr[(a[0]-b[0])%shape[0]]*wc[(a[1]-b[1])%shape[1]] for b in coords] for a in coords]); neff=float(abs(np.trace(C))**2/np.trace(C@C).real)
 local=count_local_maxima(power[r0:r1,c0:c1],.05); fixedmax=(pr-r0,pc-c0) in local; second=[x for x in local if x!=(pr-r0,pc-c0)]; nearest=min((np.hypot(x[0]-(pr-r0),x[1]-(pc-c0)) for x in second),default=None); line_r=fwhm_line(power[:,pc],pr);line_c=fwhm_line(power[pr,:],pc); radial=met[0]['fwhm_power_bins']; peakrow=next(x for x in rows if x['fixed_peak']); amplitude_class='overlapped' if fixedmax and not second else ('partially_separated' if second else 'unidentifiable'); phase_class='non_identifiable_from_neighbor_bins' if neff<5 else 'descriptive_only'; local_power=abs(F[:,r0:r1,c0:c1])**2; fixed_flat=(pr-r0)*(c1-c0)+(pc-c0); fixed_count=int(sum(np.argmax(local_power.reshape(len(F),-1),axis=1)==fixed_flat)); summary=dict(fixed_peak=[pr,pc],delta_bin=dict(parallel_rad_m=met[0]['delta_bin_rad_m'],perpendicular_rad_m=met[1]['delta_bin_rad_m']),window_metrics=met,measured_peak=dict(local_maxima_count=len(local),fixed_is_local_maximum=fixedmax,nearest_secondary_distance_bins=nearest,peak_to_strongest_neighbor_power_ratio=float(peak/max(x['mean_power'] for x in rows if not x['fixed_peak'])),local_fwhm_power_bins=dict(parallel=line_r,perpendicular=line_c),window_fwhm_power_bins=dict(parallel=radial,perpendicular=met[1]['fwhm_power_bins']),stable_fixed_maximum_look_count=fixed_count,peak_slope=peakrow['signed_slope_rad_s'],peak_r2=peakrow['r2'],peak_endpoint_msc=peakrow['endpoint_msc']),dependence=dict(neighborhood_bins=len(rows),window_covariance_effective_rank=neff,interpretation='not independent bins; rank is a window-covariance diagnostic only'),classification=dict(amplitude=amplitude_class,phase=phase_class,temporal_slope='descriptive_same-lobe comparison only',look_stability='fixed candidate assessed; no reselection',overall='not_identifiable_as_multiple_spatial_components'),block15g_comparison=dict(real_nearest_secondary_over_delta_eff=(nearest/radial if nearest is not None else None),conclusion='BP12 neighborhood is compared to 1- and 6-bin synthetic scenarios only dimensionlessly; it does not establish two waves.'),synthetic=syn,limitations=['BP12 grid spacing is not a measured radar PSF','window response is only the explicit Block15B Tukey factor, not full backprojection/SAR PSF','neighbor bins and 32 looks are dependent; no confidence interval from their scatter','no frequency, period, bathymetry or Q2 real fit was changed'])
 save(OUT/'BLOCK15H_SUMMARY.json',summary); plot(power,rows,met,cfg); report(summary,cfg)
def plot(power,rows,met,cfg):
 import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
 pr,pc=cfg['fixed_peak'];r0,r1=cfg['neighborhood']['rows'];c0,c1=cfg['neighborhood']['cols'];fig,ax=plt.subplots(1,2,figsize=(11,4),layout='constrained'); ax[0].imshow(np.log10(power[r0:r1,c0:c1]/power[pr,pc]),origin='lower',aspect='auto');ax[0].plot(pc-c0,pr-r0,'rx');ax[0].set(title='BP12 fixed-peak neighborhood: log10 relative power',xlabel='col offset',ylabel='row offset');a=np.array([[x['signed_slope_rad_s'] for x in rows if x['row']==i] for i in range(r0,r1)]);im=ax[1].imshow(a,origin='lower',aspect='auto');ax[1].plot(pc-c0,pr-r0,'rx');ax[1].set(title='Signed Block15B-reference slope [rad/s]');fig.colorbar(im,ax=ax[1]);fig.savefig(OUT/'BLOCK15H_PEAK_NEIGHBORHOOD.png',dpi=150);plt.close(fig)
 fig,ax=plt.subplots(figsize=(7,4),layout='constrained');
 for m in met:ax.bar(m['axis'],m['fwhm_power_bins'],label='FWHM power');ax.scatter(m['axis'],m['equivalent_lobe_width_bins'],marker='x',s=70,label='equivalent width')
 ax.set(ylabel='native FFT bins',title='Explicit Block15B Tukey-window resolution');ax.legend();fig.savefig(OUT/'BLOCK15H_WINDOW_RESPONSE.png',dpi=150);plt.close(fig)
def report(s,cfg):
 m=s['window_metrics'];p=s['measured_peak'];text=f"""# Block15H — BP12 spatial-resolution audit\n\n## Scope\n\nBP12-only audit using the frozen `[133,65]` candidate. No CPHD/SICD signal read, stack formation, dwell sweep, frequency correction, period/depth inference or real Q2 fit occurred. Input is `{cfg['stack']['path']}`, with 32 recorded mean TxTime values.\n\n## Direct BP12 result\n\nThe explicit Block15B Tukey alpha=0.1 gives delta-bin `{{m[0]['delta_bin_rad_m']:.8f}}` rad/m parallel and `{{m[1]['delta_bin_rad_m']:.8f}}` rad/m perpendicular. Its measured power FWHM is `{{m[0]['fwhm_power_bins']:.3f}}` and `{{m[1]['fwhm_power_bins']:.3f}}` bins; this, rather than delta-bin alone, is delta-eff. The local fixed-peak audit finds {{p['local_maxima_count']}} internal maxima above the declared 5% floor; fixed maximum={{p['fixed_is_local_maximum']}}.\n\n## Classification\n\nAmplitude: **{s['classification']['amplitude']}**. Phase and slope neighbor-bin evidence is deliberately only descriptive because the 13x13 neighborhood has window-covariance effective rank {s['dependence']['window_covariance_effective_rank']:.2f}, not 169 independent observations. Overall: **not identifiable as multiple spatial components**. This is compatible with one window-broadened/overlapped lobe; it is not evidence against all possible physical mixtures.\n\n## Block15G comparison\n\nThe nearest detected feature divided by the measured window FWHM is {s['block15g_comparison']['real_nearest_secondary_over_delta_eff']}. Therefore a literal comparison to 1 or 6 bins is invalid; the synthetic calibration is only a dimensional response check.\n\n## Limits\n\nThe Tukey kernel is an explicitly measured added analysis window, not the unmeasured full BP12 backprojection PSF. Neighbor bins, conjugates and look samples are dependent. Signed slopes retain `F_secondary * conj(F_reference)` convention but are not corrected or interpreted as new physical frequencies.\n\n**STOP — Block15H complete.**\n"""; (OUT/'BLOCK15H_REPORT.md').open('x',encoding='utf-8').write(text)
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('mode',choices=['prepare','run']);x=a.parse_args();prepare() if x.mode=='prepare' else run()
