"""Block29 phase A; phase B is forbidden unless the frozen gate passes."""
from __future__ import annotations
import argparse,json,hashlib,sys,subprocess,os
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
from sarpy.io.complex.sicd_elements.SICD import SICDType
from sarpy.io.phase_history.cphd1_elements.CPHD import CPHDType
from sarpy.geometry.geocoords import geodetic_to_ecf
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'code'))
import run_block28_samoa_preflight as b28
from run_block22_geographic_preflight import dump,atomic,table
from run_block27_representativity import serial
from umbra_sar.pfa_time_mapping import *
BASE=ROOT/'Block29_Samoa_mapping_trial';B28=b28.BASE

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def init():
    if (BASE/'CONFIG.json').exists():return
    BASE.mkdir(parents=True,exist_ok=True)
    commit=subprocess.check_output(['git','-c','safe.directory=D:/Dati Tesi/Umbra','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    status=subprocess.check_output(['git','-c','safe.directory=D:/Dati Tesi/Umbra','status','--short'],cwd=ROOT,text=True)
    dump(BASE/'INITIAL_STATE.json',{'commit':commit,'preexisting_worktree':status,'cwd':str(ROOT),'python':sys.executable,
        'TEMP':os.environ.get('TEMP'),'TMP':os.environ.get('TMP'),'started_utc':datetime.now(timezone.utc).isoformat()})
    cfg={'collect_id':b28.ID,'criteria_frozen_before_pvp':True,
        'maximum_center_sensitivity_s':.05,'maximum_baseline_fractional_sensitivity':.05,
        'maximum_duration_fractional_sensitivity':.10,'maximum_poly_geometry_equivalent_time_error_s':.01,
        'maximum_temporal_gap_median_ratio':1.5,'maximum_endpoint_clock_discrepancy_s':.005,
        'primary_look_plan':'three_nonoverlap','control_look_plan':'two_nonoverlap',
        'points':'SCP, frozen ROI centre and four corners; fixed declared PFA plane/basis',
        'radial_samples':'PFA Krg1, middle, Krg2; inherited rectangular Col bands',
        'weight_cases':['uniform output-k','uniform time'],
        'budget_A':{'transactions':60,'total_bytes':100*1024**2,'response_bytes':10*1024**2,'automatic_retries':0},
        'budget_B':{'sole_sicd_bytes':2551099862,'traffic_bytes':3*1024**3,'intermediates_bytes':5*1024**3},
        'support_primary':'full azimuth, preserve oblique validity; no small pre-FFT crop',
        'support_control':'single explicit taper sensitivity, no optimization',
        'gate_policy':'all timing/geometry checks must pass; CONDITIONAL disables SICD download',
        'tolerance_rationale':'A 0.05 s unmodelled center shift introduces 0.05 rad at a diagnostic unit angular frequency 1 rad/s; 5% differential baseline error directly gives ~5% slope scale error. Duration variation limited to 10% to prevent comparing unlike temporal averaging. These are technical tolerances, not buoy period gates.'}
    dump(BASE/'CONFIG.json',cfg);atomic(BASE/'CONFIG.sha256',(sha(BASE/'CONFIG.json')+'\n').encode())
    atomic(BASE/'PROTOCOL.md',('''# Block29 — frozen phase A protocol

Same Samoa acquisition, no frozen artifact changes. Reuse Block28 identity,
SICD/PFA XML, CPHD header/XML, full ROI and verified buoy payload. Retrieve
only the compact complete PVP block (8,165,216 bytes), after a relevant HEAD
probe and size/ETag verification. No support/signal array. Structured dtype
from official SarPy CPHD XML, big-endian and integer SIGNAL/PulseNumber.

Reconstruct bistatic phase-gradient vectors, project along focus-plane normal
onto the declared PFA image plane, retain both Row and Col (cycles/metre),
compare angle against metadata PolarAngPoly and the independent SICD ARP.
Invert angle = atan2(k_col,k_row) separately at three Row carrier frequencies
and ROI representative points. Scene-interaction time from Tx/Rcv paths;
record clock conventions and TxTime/RcvTime differences. Rectangular output-k
and uniform-time centers are geometry-only weight cases, not exact vendor
illumination kernels. Unknown interpolation/antenna/pulse weights remain a
limitation and cannot be fitted to buoy agreement.

Thresholds in CONFIG are frozen before new PVP processing. Differential
baseline and duration sensitivity, absolute center variation, monotonicity,
gaps, geometry/poly equivalent timing and frequency support must pass. Reject
or mark conditional if spatial/radial coupling exceeds these limits. PASS
alone authorizes one resumable SICD download; otherwise record the impediment
and stop, without alternate formation. No q/bathymetry/boa optimization.

Numerical tests: structured offsets, units, inverse-transpose wavevector,
FFT sign/conjugate intensity lobes/cross convention, mask-domain synthetic
static/dynamic diagnostics (not a raw SAR simulator), byte-range guard and
frozen provenance. Full project-local pytest suite required.
''').encode())
    dump(BASE/'PHASE_A_STATE.json',{'transactions':0,'total_bytes':0,'stage':'initialized_before_network'})
    dump(BASE/'PHASE_A_REQUEST_LOG.json',[])
    sources=[B28/'DELIVERY_MANIFEST.json',B28/'raw/sicd.xml',B28/'raw/cphd.xml',B28/'CPHD_METADATA.json',B28/'LOCAL_INPUTS.json',B28/'SUBAPERTURE_METADATA_AND_PLANS.json']
    dump(BASE/'INPUT_PROVENANCE.json',[{'path':str(p.relative_to(ROOT)),'sha256':sha(p),'bytes':p.stat().st_size} for p in sources])

class Client(b28.Client):
    def __init__(self):
        self.state=json.loads((BASE/'PHASE_A_STATE.json').read_text());self.log=json.loads((BASE/'PHASE_A_REQUEST_LOG.json').read_text())
    def save(self):dump(BASE/'PHASE_A_STATE.json',self.state);dump(BASE/'PHASE_A_REQUEST_LOG.json',self.log)
    def reserve(self,url,purpose,method,span,kind='request'):
        from urllib.parse import urlparse
        if self.state['transactions']>=60:raise RuntimeError('phase_A_transaction_budget')
        if urlparse(url).hostname!=urlparse(b28.ENDPOINT).hostname:raise RuntimeError('redirect_outside_public_host')
        self.state['transactions']+=1;e={'timestamp_utc':datetime.now(timezone.utc).isoformat(),'url':url,'purpose':purpose,'method':method,'range':span,'kind':kind,'outcome':'pending','bytes':0};self.log.append(e);self.save();return e
    def request(self,url,purpose,method='GET',span=None):
        # b28's 5MiB/20MiB limits are conservative, but entire PVP needs 10MiB.
        # Separate streaming implementation retains its before-body range guard.
        from urllib.request import build_opener,Request,HTTPRedirectHandler
        from umbra_sar.geographic_preflight import validate_partial_response
        e=self.reserve(url,purpose,method,span);client=self
        class Redirect(HTTPRedirectHandler):
            def redirect_request(self,req,fp,code,msg,headers,newurl):
                x=client.reserve(newurl,purpose,method,span,'redirect');x.update(outcome='redirect',http_status=code);client.save()
                return super().redirect_request(req,fp,code,msg,headers,newurl)
        headers={'User-Agent':'UmbraThesis-Samoa-PVP/1.0'}
        if span:headers['Range']=f'bytes={span[0]}-{span[1]}'
        try:
            with build_opener(Redirect()).open(Request(url,headers=headers,method=method),timeout=30) as r:
                cl=r.headers.get('Content-Length');cr=r.headers.get('Content-Range');e.update(http_status=r.status,content_length=cl,content_range=cr,etag=r.headers.get('ETag'))
                if span:validate_partial_response(r.status,cr,*span,span[1]-span[0]+1)
                if method!='HEAD' and cl and int(cl)>10*1024**2:raise RuntimeError('response_limit')
                data=[];remaining=0 if method=='HEAD' else (span[1]-span[0]+1 if span else int(cl or 10*1024**2))
                while remaining:
                    n=min(65536,remaining,100*1024**2-self.state['total_bytes'])
                    if n<=0:raise RuntimeError('total_budget')
                    piece=r.read(n)
                    if not piece:break
                    remaining-=len(piece);data.append(piece);e['bytes']+=len(piece);self.state['total_bytes']+=len(piece);self.save()
                result=b''.join(data)
                if span:validate_partial_response(r.status,cr,*span,len(result))
            e.update(outcome='recovered',sha256=hashlib.sha256(result).hexdigest());self.save();return result,e
        except Exception as exc:e.update(outcome='failed',error=repr(exc));self.save();raise

def fetch():
    meta=json.loads((B28/'CPHD_METADATA.json').read_text());c=Client();p=BASE/'raw/pvp_block.bin'
    if p.exists():return
    # First pertinent probe; exception aborts before other endpoints.
    _,head=c.request(meta['url'],'CPHD_identity_connectivity_HEAD',method='HEAD')
    if int(head['content_length'])!=meta['size_bytes']:raise RuntimeError('CPHD_version_size_changed')
    kv=meta['header_fields'];start=int(kv['PVP_BLOCK_BYTE_OFFSET']);size=int(kv['PVP_BLOCK_SIZE']);end=start+size-1
    if end>=int(kv['SIGNAL_BLOCK_BYTE_OFFSET']):raise RuntimeError('PVP_range_overlaps_signal')
    data,_=c.request(meta['url'],'complete_compact_PVP_only',span=(start,end));atomic(p,data)
    c.state['stage']='full_PVP_recovered';c.save()

def analyze():
    cfg=json.loads((BASE/'CONFIG.json').read_text());assert sha(BASE/'CONFIG.json')==(BASE/'CONFIG.sha256').read_text().strip()
    s=SICDType.from_xml_file(str(B28/'raw/sicd.xml'));cp=CPHDType.from_xml_file(str(B28/'raw/cphd.xml'))
    rec=parse_pvp_bytes((BASE/'raw/pvp_block.bin').read_bytes(),cp)
    fpn=s.PFA.FPN.get_array();ipn=s.PFA.IPN.get_array();row=s.Grid.Row.UVectECF.get_array();col=s.Grid.Col.UVectECF.get_array()
    point=s.GeoData.SCP.ECF.get_array();time,closure=scatter_time(rec,point)
    coeff=pfa_phase_vectors(rec['TxPos'],rec['RcvPos'],point,fpn,ipn,row,col);theta=np.arctan2(coeff[:,1],coeff[:,0])
    sf_geometry=.5*C*np.linalg.norm(coeff,axis=1);sf_poly=s.PFA.SpatialFreqSFPoly(theta)
    poly=s.PFA.PolarAngPoly(time);ang_rate=np.gradient(theta,time)
    time_equiv=(theta-poly)/ang_rate
    dt=np.diff(rec['TxTime']);pvpstats={'vectors':len(rec),'dtype':str(rec.dtype),'record_bytes':rec.dtype.itemsize,
        'TxTime_monotone':bool(np.all(dt>0)),'RcvTime_monotone':bool(np.all(np.diff(rec['RcvTime'])>0)),
        'scatter_time_monotone':bool(np.all(np.diff(time)>0)),
        'dt_min_s':float(dt.min()),'dt_median_s':float(np.median(dt)),'dt_max_s':float(dt.max()),
        'gap_max_to_median_ratio':float(dt.max()/np.median(dt)),
        'PulseNumber_monotone':bool(np.all(np.diff(rec['PulseNumber'].astype(float))>0)),
        'SIGNAL_values':np.unique(rec['SIGNAL']).tolist(),'Tx_Rcv_scatter_closure_max_s':float(np.max(abs(closure))),
        'TxTime_span_s':float(rec['TxTime'][-1]-rec['TxTime'][0]),'all_time_continuity_verified':True,
        'PVP_sha256':sha(BASE/'raw/pvp_block.bin'),'CPHD_SGN':cp.Global.SGN,
        'units':'Tx/RcvTime seconds since CollectionStart; positions metres ECF; velocities m/s; FX Hz; derived PFA k cycles/m',
        'poly_geometry_equivalent_time_error_max_s':float(np.max(abs(time_equiv)))}
    pvpstats.update({'PFA_scale_geometry_vs_polynomial_max_absolute_residual':float(np.max(abs(sf_geometry-sf_poly))),
        'required_fields_finite':bool(all(np.all(np.isfinite(rec[k])) for k in ['TxTime','RcvTime','TxPos','TxVel','RcvPos','RcvVel','SRPPos','FX1','FX2'])),
        'declared_format_and_offsets_source':'SarPy CPHDType.PVP.get_vector_dtype from original XML, not an all-double reinterpretation'})
    head=next(e for e in json.loads((BASE/'PHASE_A_REQUEST_LOG.json').read_text()) if e['purpose']=='CPHD_identity_connectivity_HEAD' and e['outcome']=='recovered')
    public=json.loads((B28/'PUBLIC_LISTING_INVENTORY.json').read_text())['assets'];expected=next(x['etag'] for x in public if x['key'].endswith('_CPHD.cphd'))
    pvpstats['CPHD_ETag_matches_frozen_public_listing']=head.get('etag','').strip('"')==expected.strip('"')
    dump(BASE/'PVP_AUDIT.json',pvpstats)
    # Independent ARP/metadata comparison: no PVP geometry used in ARP curve.
    ga,gsf=s.PFA.pfa_polar_coords(s.Position,point,time)
    pvpstats['ARP_vs_PVP_angle_equivalent_time_error_max_s']=float(np.max(abs((ga-theta)/ang_rate)))
    dump(BASE/'PVP_AUDIT.json',pvpstats)
    b28inputs=json.loads((B28/'LOCAL_INPUTS.json').read_text());from shapely.geometry import shape
    roi=shape(json.loads(b28inputs['reference_and_roi']['roi_polygon_json']));hae=float(s.GeoData.SCP.LLH.HAE)
    locations=[('SCP',point),('ROI_centre',geodetic_to_ecf([roi.centroid.y,roi.centroid.x,hae]))]
    locations +=[(f'ROI_corner_{i}',geodetic_to_ecf([lat,lon,hae])) for i,(lon,lat) in enumerate(list(roi.exterior.coords)[:-1])]
    plans=json.loads((B28/'SUBAPERTURE_METADATA_AND_PLANS.json').read_text())['plans'];rows=[];kernels=[]
    krowvalues=[s.PFA.Krg1,.5*(s.PFA.Krg1+s.PFA.Krg2),s.PFA.Krg2]
    fft=np.fft.fftshift(np.fft.fftfreq(s.ImageData.NumCols,d=s.Grid.Col.SS))
    for label,pt in locations:
        tt,cl=scatter_time(rec,pt);cc=pfa_phase_vectors(rec['TxPos'],rec['RcvPos'],pt,fpn,ipn,row,col);aa=np.arctan2(cc[:,1],cc[:,0])
        for plan in plans:
            if plan['label'] not in [cfg['primary_look_plan'],cfg['control_look_plan']]:continue
            for ix,band in enumerate(plan['bands']):
                low=fft[band['start']];high=fft[band['stop']]
                for kr in krowvalues:
                    try:kernel=band_kernel(aa,tt,kr,low,high)
                    except ValueError as exc:
                        q={'point':label,'plan':plan['label'],'look_index':ix,'k_row_cycles_per_m':kr,
                            'k_col_low_cycles_per_m':float(low),'k_col_high_cycles_per_m':float(high),
                            'kernel_status':'not_identifiable_outside_geometry_support','error':str(exc),
                            'requested_angle_low_rad':float(np.arctan2(low,kr)),'requested_angle_high_rad':float(np.arctan2(high,kr)),
                            'available_angle_low_rad':float(aa.min()),'available_angle_high_rad':float(aa.max()),
                            'frequency_supported':False,'within_processing_time_guard':False}
                        rows.append(q);kernels.append(q);continue
                    frequencies=np.interp(kernel['sampled_times_s'],tt,cc[:,0]);freq_required=kr/frequencies
                    fx1=np.interp(kernel['sampled_times_s'],tt,rec['FX1']);fx2=np.interp(kernel['sampled_times_s'],tt,rec['FX2'])
                    q={k:v for k,v in kernel.items() if not isinstance(v,np.ndarray)}
                    q.update(point=label,plan=plan['label'],look_index=ix,k_row_cycles_per_m=kr,k_col_low_cycles_per_m=float(low),k_col_high_cycles_per_m=float(high))
                    q.update({'frequency_supported':bool(np.all(freq_required>=fx1-1) and np.all(freq_required<=fx2+1)),
                        'declared_processed_frequency_supported':bool(np.all(freq_required>=s.ImageFormation.TxFrequencyProc.MinProc-1) and np.all(freq_required<=s.ImageFormation.TxFrequencyProc.MaxProc+1)),
                        'required_frequency_min_hz':float(freq_required.min()),'required_frequency_max_hz':float(freq_required.max()),
                        'within_processing_time_guard':bool(q['time_start_s']>=s.ImageFormation.TStartProc-cfg['maximum_endpoint_clock_discrepancy_s'] and q['time_stop_s']<=s.ImageFormation.TEndProc+cfg['maximum_endpoint_clock_discrepancy_s'])})
                    q['kernel_status']='geometry_identified_not_vendor_exact'
                    rows.append(q);kernels.append({**q,'sampled_times_s':kernel['sampled_times_s'].tolist(),'sampled_k_col':kernel['sampled_k_col'].tolist()})
    table(BASE/'BAND_TIMES.csv',rows);dump(BASE/'GEOMETRIC_KERNELS.json',kernels)
    nominal=[r for r in rows if r['point']=='SCP' and r['k_row_cycles_per_m']==krowvalues[1]]
    errors=[];baseline=[];durations=[];radial=[];spatial=[];weight=[]
    for r in rows:
        if 'centre_uniform_output_k_s' not in r:continue
        ref=next(x for x in nominal if x['plan']==r['plan'] and x['look_index']==r['look_index'])
        errors.extend([abs(r['centre_uniform_output_k_s']-ref['centre_uniform_output_k_s']),abs(r['centre_uniform_time_s']-r['centre_uniform_output_k_s'])])
        weight.append(abs(r['centre_uniform_time_s']-r['centre_uniform_output_k_s']))
        if r['point']=='SCP':radial.append(abs(r['centre_uniform_output_k_s']-ref['centre_uniform_output_k_s']))
        if r['k_row_cycles_per_m']==krowvalues[1]:spatial.append(abs(r['centre_uniform_output_k_s']-ref['centre_uniform_output_k_s']))
        durations.append(abs(r['support_duration_s']/ref['support_duration_s']-1))
    for plan in [cfg['primary_look_plan'],cfg['control_look_plan']]:
        for label,_ in locations:
            for kr in krowvalues:
                local=sorted([r for r in rows if r['point']==label and r['plan']==plan and r['k_row_cycles_per_m']==kr],key=lambda x:x['look_index'])
                ref=sorted([r for r in nominal if r['plan']==plan],key=lambda x:x['look_index'])
                for i in range(1,len(local)):
                    if any('centre_uniform_output_k_s' not in x for x in [local[i],local[i-1],ref[i],ref[i-1]]):continue
                    b=local[i]['centre_uniform_output_k_s']-local[i-1]['centre_uniform_output_k_s'];br=ref[i]['centre_uniform_output_k_s']-ref[i-1]['centre_uniform_output_k_s']
                    baseline.append(abs(b/br-1))
    checks={'temporal_continuity':pvpstats['TxTime_monotone'] and pvpstats['RcvTime_monotone'] and pvpstats['gap_max_to_median_ratio']<=cfg['maximum_temporal_gap_median_ratio'],
        'PFA_angle_monotone':bool(np.all(np.diff(theta)<0) or np.all(np.diff(theta)>0)),
        'poly_geometry_timing':pvpstats['poly_geometry_equivalent_time_error_max_s']<=cfg['maximum_poly_geometry_equivalent_time_error_s'],
        'ARP_geometry_timing':pvpstats['ARP_vs_PVP_angle_equivalent_time_error_max_s']<=cfg['maximum_poly_geometry_equivalent_time_error_s'],
        'center_sensitivity':max(errors)<=cfg['maximum_center_sensitivity_s'],
        'baseline_sensitivity':max(baseline)<=cfg['maximum_baseline_fractional_sensitivity'],
        'duration_sensitivity':max(durations)<=cfg['maximum_duration_fractional_sensitivity'],
        'frequency_support':all(r['frequency_supported'] for r in rows),'processed_support':all(r['within_processing_time_guard'] for r in rows),
        'all_candidate_kernels_identifiable':all('centre_uniform_output_k_s' in r for r in rows)}
    gate={'result':'PASS' if all(checks.values()) else 'CONDITIONAL','checks':checks,
        'maximum_center_sensitivity_s':max(errors),'maximum_baseline_fractional_sensitivity':max(baseline),
        'maximum_duration_fractional_sensitivity':max(durations),'config_sha256':sha(BASE/'CONFIG.json'),
        'one_dimensional_Col_adequacy':'geometry-only bands depend on Row frequency and ROI point; see measured sensitivities',
        'unknown_kernel_weights':['supplier polar interpolation details','illumination pulse weights not proven by UNIFORM output weighting'],
        'kernel_exact':False,'SICD_download_authorized_by_gate':all(checks.values())}
    gate['interpretation_caveat']='Global PFA output coordinates are shared across the image. ROI-point phase-gradient projections are local stationary-phase diagnostics, NOT a verified re-indexing of that shared output grid. Large local offsets may be deterministic focus-phase/carrier effects; this block does not prove their full magnitude is physical timing bias. Correct local/global kernel transport is unresolved, so the gate is conditional rather than a declaration of scene failure.'
    gate['kernels_not_identifiable_count']=sum('centre_uniform_output_k_s' not in r for r in rows)
    gate['candidate_kernel_count']=len(rows)
    gate.update({'SCP_radial_only_max_center_sensitivity_s':max(radial),
        'ROI_local_gradient_only_max_center_offset_s':max(spatial),'uniform_k_vs_time_max_center_difference_s':max(weight)})
    dump(BASE/'GATE_A.json',gate)
    np.savez_compressed(BASE/'PFA_MAPPING.npz',scatter_time_s=time,TxTime_s=rec['TxTime'],theta_rad=theta,
        polynomial_theta_rad=poly,coeff_row_cycles_per_m_per_hz=coeff[:,0],coeff_col_cycles_per_m_per_hz=coeff[:,1])
    center,_,_=s.project_ground_to_image_geo([roi.centroid.y,roi.centroid.x,hae]);J=geometry_jacobian(s,center,hae)
    dump(BASE/'WAVEVECTOR_TRANSFORM.json',{'J_ground_EN_m_per_image_RowCol_m':J.tolist(),
        'mapping':'k_ground_rad_per_m = inverse(J).T @ k_image_rad_per_m','condition_number':float(np.linalg.cond(J)),
        'LOS_vs_Grid_vs_pushforward_source':'Block28 GEOMETRY.json retained unchanged'})
    dump(BASE/'PHASE_B_DOWNLOAD_STATE.json',{'status':'not_started_gate_'+gate['result'],'transactions':0,'transferred_bytes':0,
        'SICD_downloaded':False,'CPHD_signal_read':False})
    print(json.dumps(gate,indent=2),flush=True)

def synthetic_support(s,omega=0.):
    """Small image-domain carrier multiplex test, NOT a SAR phase-history model."""
    from shapely.geometry import Polygon,Point
    from scipy.ndimage import distance_transform_edt
    nr,nc=192,512;rr,cc=np.mgrid[:nr,:nc];phase=2*np.pi*(2*rr/nr+3*cc/nc)+.3
    time=np.array([0.,1.,2.]);carriers=[-150,0,150]
    full=sum(np.sqrt(1+.15*np.cos(phase-omega*t))*np.exp(2j*np.pi*carrier*cc/nc) for t,carrier in zip(time,carriers))
    valid=Polygon([(v.Col/(s.ImageData.NumCols-1)*(nc-1),v.Row/(s.ImageData.NumRows-1)*(nr-1)) for v in s.ImageData.ValidData])
    mask=np.array([[valid.covers(Point(c,r)) for c in range(nc)] for r in range(nr)])
    taper=np.clip(distance_transform_edt(mask)/8,0,1);taper=.5-.5*np.cos(np.pi*taper)
    roi_a=json.loads((B28/'ROI_VALID_SUPPORT.json').read_text())['projections'][1]
    roi=Polygon([(p[1]/(s.ImageData.NumCols-1)*(nc-1),p[0]/(s.ImageData.NumRows-1)*(nr-1)) for p in roi_a['boundary_pixels_row_col']])
    roi_mask=np.array([[roi.covers(Point(c,r)) for c in range(nc)] for r in range(nr)])
    basis=np.column_stack([np.ones(roi_mask.sum()),np.cos(phase[roi_mask]),np.sin(phase[roi_mask])]);results={}
    for label,window in [('no_mask_reference',np.ones_like(mask,float)),('primary_explicit_hard_valid_mask',mask),('single_8pixel_edge_taper',taper)]:
        spectrum=np.fft.fftshift(np.fft.fft(full*window,axis=1),axes=1);coefficients=[]
        for carrier in carriers:
            out=np.zeros_like(spectrum);ix=nc//2+carrier;out[:,ix-40:ix+41]=spectrum[:,ix-40:ix+41]
            image=np.fft.ifft(np.fft.ifftshift(out,axes=1),axis=1);power=abs(image)**2
            beta=np.linalg.lstsq(basis,power[roi_mask],rcond=None)[0]
            coefficients.append(complex(beta[1],-beta[2]))
        z=np.asarray(coefficients);relative=z*np.conj(z[0]);wrapped=np.angle(relative);unwrapped=np.unwrap(wrapped)
        fit=np.polyfit(time,unwrapped,1)
        results[label]={'coefficients_real_imag':np.column_stack([z.real,z.imag]).tolist(),
            'relative_phase_wrapped_rad':wrapped.tolist(),'relative_phase_unwrapped_rad':unwrapped.tolist(),
            'fitted_image_domain_slope_rad_s':float(fit[0]),'known_image_domain_slope_rad_s':-omega,
            'residual_rad':(unwrapped-np.polyval(fit,time)).tolist()}
    return {'model':'carrier-multiplexed synthetic complex IMAGE; not raw physical SAR',
        'time_s':time.tolist(),'omega_truth_rad_s':omega,'valid_mask_fraction':float(mask.mean()),
        'mask_vertices_scaled_from_actual_sicd':list(valid.exterior.coords),'ROI_pixel_count':int(roi_mask.sum()),
        'cases':results,'masked_invalid_values_explicitly_zero_not_claimed_valid_data':True,
        'diagnostic_only_not_phase_C_real_data':True}

def finish():
    os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'_cache/matplotlib'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    gate=json.loads((BASE/'GATE_A.json').read_text());audit=json.loads((BASE/'PVP_AUDIT.json').read_text())
    state=json.loads((BASE/'PHASE_A_STATE.json').read_text());cfg=json.loads((BASE/'CONFIG.json').read_text())
    s=SICDType.from_xml_file(str(B28/'raw/sicd.xml'));syn={label:synthetic_support(s,w) for label,w in [('static',0.),('known_dynamic',.7)]}
    dump(BASE/'SYNTHETIC_SUPPORT_DIAGNOSTIC.json',syn)
    (BASE/'figures').mkdir(exist_ok=True)
    mapping=np.load(BASE/'PFA_MAPPING.npz');fig,axes=plt.subplots(2,1,figsize=(8,6),sharex=True)
    axes[0].plot(mapping['scatter_time_s'],mapping['theta_rad'],label='bistatic PVP + PFA focus-plane projection')
    axes[0].plot(mapping['scatter_time_s'],mapping['polynomial_theta_rad'],'--',label='declared PolarAngPoly');axes[0].legend(fontsize=8);axes[0].set_ylabel('PFA angle [rad]')
    axes[1].plot(mapping['scatter_time_s'],mapping['theta_rad']-mapping['polynomial_theta_rad']);axes[1].set_ylabel('angle residual [rad]');axes[1].set_xlabel('scene-interaction time since CollectStart [s]')
    fig.tight_layout();fig.savefig(BASE/'figures/pfa_mapping.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    for ax,label in zip(axes,['static','known_dynamic']):
        for case,r in syn[label]['cases'].items():ax.plot(syn[label]['time_s'],r['relative_phase_unwrapped_rad'],'o-',label=case)
        ax.set_title(label+' — image-domain only');ax.set_xlabel('synthetic time [s]');ax.set_ylabel('relative phase [rad]')
    axes[0].legend(fontsize=6);fig.tight_layout();fig.savefig(BASE/'figures/synthetic_mask_phase.png',dpi=150);plt.close(fig)
    bands=b28.read(BASE/'BAND_TIMES.csv');central=[r for r in bands if r['point']=='SCP' and r['k_row_cycles_per_m']==str(.5*(s.PFA.Krg1+s.PFA.Krg2))]
    report=f'''# CHECKPOINT_29 — Samoa: mapping gate e arresto tecnico

**Gate A: {gate['result']}. SICD non scaricato.**
Non si è ottenuta un'associazione globale/locale sufficientemente verificata per assegnare tempi fisici unici alle sotto-bande della prova sulla ROI. Non viene avviato un diverso percorso di formazione. Non è una dichiarazione che la scena o il metodo siano fisicamente inutilizzabili.

## 1. Mapping verificato e limiti

Intero blocco PVP: **{audit['vectors']} vettori**, **{audit['record_bytes']} byte/vettore**, layout XML SarPy big-endian con interi SIGNAL/PulseNumber distinti dai float. TxTime/RcvTime e scena-interaction time monotoni. dt mediano {audit['dt_median_s']:.12f} s, massimo/mediana {audit['gap_max_to_median_ratio']:.6f}; SIGNAL={{1}}, nessun campionamento parziale della continuità.

TxTime span **{audit['TxTime_span_s']:.9f} s**, distinto dall'apertura SICD processata **{float(s.ImageFormation.TEndProc-s.ImageFormation.TStartProc):.9f} s** e catalogo 3,6 s. Scene time è la media di TxTime+R_tx/c e RcvTime−R_rx/c; chiusura massima dei due cammini {audit['Tx_Rcv_scatter_closure_max_s']:.3e} s. La differenza Tx/scene time (~2 ms) non è confusa con durata processata.

Geometria primaria: somma dei versori bistatici sensore→punto, divisa per c, proiettata lungo FPN sul piano IPN. k [cycles/m]=f[Hz]×coefficiente. Questa proiezione di focus-plane è diversa dalla semplice LOS·Grid.Col usata in uno sviluppo precedente; quest'ultima non viene trasferita a Samoa senza verifica PFA. Angolo atan2(k_col,k_row), non frazione bandwidth=frazione tempo. Residuo equivalente temporale massimo PVP vs PolarAngPoly **{audit['poly_geometry_equivalent_time_error_max_s']:.3e} s**, ARP SICD vs PVP **{audit['ARP_vs_PVP_angle_equivalent_time_error_max_s']:.3e} s**.

Il mapping geometrico **allo SCP è coerente**. Per il kernel di una banda Col, però, theta=atan2(k_col,k_row): si integra sull'intera banda Row, non esiste automaticamente un solo tempo per Col. Uniform-output-k e uniform-time sono due pesi geometrici dichiarati. UNIFORM SICD non dimostra pesi di illuminazione originali uniformi; interpolazione e pulse weighting del fornitore non sono integralmente ricostruiti. Nessun kernel detto esatto.

## 2. Gate prefissato

CONFIG salvata prima di recuperare i PVP, SHA256 `{sha(BASE/'CONFIG.json')}`. Limiti: centro 0,05 s; sensibilità baseline 5%; durata 10%; coerenza geometria/polinomi 0,01 s. Il limite baseline controlla direttamente l'errore di scala della pendenza. Non sono derivati dal Tp della boa né rilassati dopo i risultati.

Massima variazione dei centri nei controlli **{gate['maximum_center_sensitivity_s']:.6f} s**; baseline **{100*gate['maximum_baseline_fractional_sensitivity']:.3f}%**; durata **{100*gate['maximum_duration_fractional_sensitivity']:.3f}%**. Kernel non identificabili nel controllo locale **{gate['kernels_not_identifiable_count']}/{gate['candidate_kernel_count']}**. Esito dei check: `{json.dumps(gate['checks'])}`.

Separazione dei contributi: sola dipendenza Row allo SCP **{gate['SCP_radial_only_max_center_sensitivity_s']:.6f} s**; offset del solo gradiente locale ROI al carrier centrale **{gate['ROI_local_gradient_only_max_center_offset_s']:.6f} s**; uniforme-k contro uniforme-tempo **{gate['uniform_k_vs_time_max_center_difference_s']:.6f} s**. Lo scale factor PFA ricostruito dalla geometria concorda con SpatialFreqSFPoly entro **{audit['PFA_scale_geometry_vs_polynomial_max_absolute_residual']:.3e}**. ETag CPHD multipart concordante con listing congelato; non interpretato come MD5.

**Cautela importante:** le coordinate di output PFA sono globali e comuni all'immagine. Riproiettare il gradiente locale a un punto ROI non equivale a reindicizzare automaticamente quel reticolo. Lo shift locale di 0,392 s può contenere termini deterministici di focalizzazione/carrier che andrebbero trasportati correttamente prima di chiamarlo bias temporale fisico. Questo blocco identifica un impedimento di modellazione, non prova un bias oceanico di tale ampiezza. Per la stessa ragione i casi locali fuori supporto non dimostrano pixel SICD invalidi. Non si estrapolano kernel o si cambiano bande per far passare il gate.

I tempi geometrici SCP per i piani candidati sono conservati in BAND_TIMES.csv; le dipendenze Row/posizione e i casi non identificabili sono espliciti. La primaria a tre bande e il controllo a due bande sono quelli prefissati da Block28; non sono stati formati look reali. Nessuna linearità da una sola coppia, nessuna falsa indipendenza dei look.

Al carrier Row centrale i tre centri geometrici SCP sono circa 3,126629 / 2,216655 / 1,302203 s dall'inizio collezione per indici banda 0/1/2: **ordine temporale inverso rispetto alla frequenza Col crescente**. Durate del supporto circa 0,907747 / 0,912207 / 0,916702 s, non automaticamente i 0,95 s nominali. Il test di cronologia e quelli FFT/coniugati verificano numericamente i segni, senza inferirli solo da Col.Sgn.

## 3. Geometria e supporto

LOS fisica, proiezione orizzontale Grid.Row e push-forward delle coordinate a terra restano distinti come in Block28. Jacobiano completo [m EN/m RowCol immagine] in WAVEVECTOR_TRANSFORM.json; k_ground[rad/m]=J^(-T)k_image[rad/m]. Nessuna rotazione semplice. ROI congelata e ValidData obliquo invariati; contenimento metadata non sostituisce controllo dei pixel reali.

Piccolo sintetico complex **nel dominio immagine**, maschera con vertici del SICD scalati, carrier separati e intensità con fase nota: caso statico e dinamico a −0,7 rad/s di verità sintetica arbitraria, non spettro boa. Un trattamento hard-mask esplicito e una sola variante taper a 8 pixel; full Col prima della FFT. Coefficienti, fasi/residui e differenze salvati; non viene chiamato simulatore fisico SAR o controllo della leakage del dato reale. Nessuna sottrazione di pendenza sintetica al mare.

Nel sintetico statico le pendenze sono numericamente zero (~10^-16 rad/s); nel caso dinamico, riferimento −0,7 rad/s, hard-mask −0,7003363 e unica variante taper −0,6999604 rad/s. Questi scostamenti sono diagnostici del piccolo modello imposto, non intervalli di confidenza né una certificazione del supporto reale. Non determinano il gate temporale e non compensano il mancato controllo globale/locale.

## 4. Prova reale non eseguita

Integrità SICD completa e SHA256: **non valutabili, download non iniziato**. Identità/dimensioni metadata restano quelle verificate Block28 (SICD 2.551.099.862 byte, CPHD 25.234.138.880 byte, HH). Struttura ondosa e controllo terrestre: **non osservati**. Leakage reale, fase reale e stabilità di pendenze: **non misurate**. Non vengono inferite dalle simulazioni. Interpretazione fisica e batimetrica non dimostrate; nessun q, confronto ottimizzato alla boa, dwell sweep o Vandenberg.

## 5. Budget, hash e riproducibilità

Fase A: **{state['transactions']}/60 transazioni HTTP, {state['total_bytes']}/104857600 byte**; massimo 10 MiB/risposta. Primo probe sandbox rifiutato, diagnosticato; solo rete pubblica tramite esecuzione autorizzata. Range intero PVP verificato prima della lettura; fine blocco precedente al signal array. Retry automatici zero. SHA256 PVP `{audit['PVP_sha256']}`. Registri fase A/B separati; fase B zero traffico e intermedi entro budget. Hash degli input congelati verificati senza riscriverli. Suite completa riportata nel TEST_REPORT, non dedotta da suite storiche.

**Un solo prossimo passo:** chiarire il trasporto dei kernel fra reticolo PFA globale e gradiente locale ROI, includendo la dipendenza Row, prima di autorizzare attraverso un nuovo gate la prova SICD. Nessun percorso alternativo di formazione viene avviato automaticamente.
'''
    atomic(BASE/'REPORT.md',report.encode('utf-8'))
    dump(BASE/'SUMMARY.json',{'status':'CHECKPOINT_29','gate_A':gate,'PVP_audit':audit,'phase_A_transactions':state['transactions'],'phase_A_bytes':state['total_bytes'],
        'SICD_downloaded':False,'real_wave_structure_observed':False,'real_phase_measured':False,
        'phase_B_status':'not_started_gate_CONDITIONAL','physical_interpretation_demonstrated':False,
        'automatic_alternate_formation':False,'synthetic_diagnostic_domain':'image only'})
    dump(BASE/'REAL_TRIAL_NOT_RUN.json',{'reason':'Gate A CONDITIONAL','overview':'not_run',
        'SICD_integrity_and_SHA256':'not_evaluable_no_download','real_support_pixel_values':'not_read',
        'real_sublooks':'not_formed','real_wave_peaks':'not_selected','real_phase':'not_measured',
        'buoy_comparison':'not_performed','land_control':'not_observed',
        'synthetic_support_diagnostic':'image_domain_only_not_substitute_for_real_trial'})
    state['stage']='CHECKPOINT_29_GATE_'+gate['result'];dump(BASE/'PHASE_A_STATE.json',state)
    manifest()

def manifest():
    artifacts=[{'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(BASE.rglob('*')) if p.is_file() and p.name!='MANIFEST.json']
    sources=[ROOT/'code/run_block29_samoa_mapping.py',ROOT/'code/umbra_sar/pfa_time_mapping.py',ROOT/'tests/test_block29_samoa_mapping.py']
    dump(BASE/'MANIFEST.json',{'block':29,'artifacts':artifacts,'code_sources':[{'path':str(p.relative_to(ROOT)),'sha256':sha(p)} for p in sources]})

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['init','fetch','analyze','finish','manifest']);a=ap.parse_args();init()
    if a.stage=='fetch':fetch()
    elif a.stage=='analyze':analyze()
    elif a.stage=='finish':finish()
    elif a.stage=='manifest':manifest()
