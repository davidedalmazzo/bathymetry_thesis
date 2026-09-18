"""Compact observational comparison: spectra diagnostics, not scene/SAR inference."""
import csv
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.signal import find_peaks
from .data import spectral_summary,mask_values,utc
from .geometry import polygon,inverse
from .output import table
from .transport import save_json


def spectrum_diagnostics(f,energy,valid,widths=None):
    s=spectral_summary(f,energy,valid,widths)
    f=np.asarray(f,float);e=np.asarray(energy,float);good=np.asarray(s['valid_mask'])
    maxima=[]
    # Invalid bands split the search; no zero-filled bridge or physical partition.
    indices=np.flatnonzero(good)
    runs=np.split(indices,np.flatnonzero(np.diff(indices)>1)+1)
    for run in runs:
        if len(run)<3:continue
        for p in find_peaks(e[run])[0]:
            j=int(run[p]);maxima.append({'bin':j,'frequency_hz':float(f[j]),'period_s':float(1/f[j]),'energy_density':float(e[j])})
    maxima.sort(key=lambda x:-x['energy_density'])
    m0=s['m0_m2']
    sigma=float(np.sqrt(max(s['m2']/m0-(s['m1']/m0)**2,0))) if m0 and m0>0 else None
    peak=s['peak_bin'];fwhm=None
    if peak is not None:
        lo=hi=peak
        while lo>0 and good[lo-1] and e[lo-1]>=e[peak]/2:lo-=1
        while hi+1<len(f) and good[hi+1] and e[hi+1]>=e[peak]/2:hi+=1
        fwhm={'first_bin':lo,'last_bin':hi,'width_hz_from_bin_widths':float(sum(s['widths_hz'][lo:hi+1])),
              'definition':'contiguous valid bins >= half maximum; includes reconstructed/provided widths, no sub-bin resolution claim'}
    return {**s,'local_maxima_no_smoothing':maxima,'frequency_standard_deviation_hz':sigma,
        'half_peak_contiguous_width':fwhm,'frequency_steps_hz':np.diff(f).tolist(),'frequency_bin_count':len(f),
        'maxima_caveat':'Numerical local maxima only, NOT independently identified physical wave systems'}


def compare(records,results,output):
    output.mkdir(parents=True,exist_ok=True)
    events=[];common={};curves=[];source_catalog={}
    parameters={'waveHs','waveTp','waveTm','waveTm1','waveTm2','waveMeanDirectionPeakFrequency','wavePeakDirectionPeakFrequency','directionalPeakSpread','windSpeed','windDirection','windGust','currentSpeed','currentEast','currentNorth','currentUp','waterLevel','predictedWaterLevel','residualWaterLevel','gapGauge'}
    for acquisition in records:
        base=results/acquisition['acquisition_id']
        observations=list(csv.DictReader((base/'OBSERVATIONS.csv').open(encoding='utf-8')))
        spatial={r['position_id']:r for r in csv.DictReader((base/'DISTANCES.csv').open(encoding='utf-8'))}
        tensors=json.loads((base/'TENSORS.json').read_text())
        for row in observations:
            if row['role']!='nearest_context' or row['variable'] not in parameters:continue
            pos=spatial[row['position_id']]
            events.append({k:row.get(k) for k in ('acquisition_id','instrument_id','family','variable','value','units','sensor_time_utc','offset_seconds','qc_flag','status','representative_eligible','tensor_pointer','sensor_vertical_context','observation_duration_seconds','interval_start_utc','interval_end_utc')}|
                {k:pos.get(k) for k in ('effective_sensor_id','lon_lat_json','position_status','position_uncertain','footprint_minimum_m','footprint_center_m','roi_minimum_m','roi_center_m','roi_status')})
            key=(row['product'],row['sensor_time_utc'],row['original_sample_index'],row['variable'])
            common.setdefault(key,[]).append(acquisition['acquisition_id'])
        for name,tensor in tensors.items():
            if not name.startswith('waves__'):continue
            v=tensor['variables']
            if 'waveEnergyDensity' not in v or 'waveFrequency' not in v:continue
            source_catalog[tensor['source']]=tensor
            row=next((r for r in observations if r['variable']=='waveEnergyDensity' and r['role']=='nearest_context' and r['product']==tensor['source']),None)
            if row is None:continue
            j=int(row['tensor_pointer'].split('/')[-1]);f=v['waveFrequency']['raw_values'];energy=v['waveEnergyDensity']['raw_values'][j];valid=v['waveEnergyDensity']['valid_mask'][j]
            qc=v.get('qcFlagE',{}).get('raw_values',[None]*len(v['time']['raw_values']))[j]
            diagnostics=spectrum_diagnostics(f,energy,valid,v.get('waveFrequencyBandwidth',{}).get('raw_values'))
            diagnostics.update(acquisition_id=acquisition['acquisition_id'],instrument_id=tensor['stable_identity'],product=tensor['source'],sensor_time_utc=row['sensor_time_utc'],qcFlagE=qc,
                published_Tp_s=v.get('waveTp',{}).get('raw_values',[None]*len(v['time']['raw_values']))[j],published_Tp_definition=v.get('waveTp',{}).get('attributes'),
                position=spatial[row['position_id']],published_peak_band={n:v[n]['raw_values'][j] for n in ('waveMeanDirectionPeakFrequency','wavePeakDirectionPeakFrequency','directionalPeakSpread') if n in v})
            curves.append({'diagnostics':diagnostics,'f':f,'energy':energy,'valid':valid})
    table(output/'EVENT_PARAMETERS.csv',events)
    shared=[{'product':k[0],'sensor_time_utc':k[1],'original_sample_index':int(k[2]),'variable':k[3],'acquisitions':ids,'independence':'same supplier observation, not independent'} for k,ids in common.items() if len(set(ids))>1]
    save_json(output/'COMMON_RECORDS.json',shared)
    save_json(output/'SPECTRAL_DIAGNOSTICS.json',[c['diagnostics'] for c in curves])
    fig,ax=plt.subplots(figsize=(9,5));plotted=set()
    for curve in curves:
        d=curve['diagnostics'];key=(d['product'],d['sensor_time_utc'])
        if key in plotted:continue
        plotted.add(key)
        ax.plot(curve['f'],np.where(curve['valid'],np.array(curve['energy'],float),np.nan),label=f"{d['instrument_id']} {d['sensor_time_utc']} QC E={d['qcFlagE']}")
    ax.set(xlabel='Frequency Hz (native bins)',ylabel='Density (original source units)',title='Unique observed spectra; no physical partitions/directional correction')
    if plotted:ax.legend(fontsize=7)
    fig.tight_layout();fig.savefig(output/'SPECTRA_OVERLAY.png',dpi=150);plt.close(fig)
    _map(records,events,output)
    _context(source_catalog,records,output)
    lines=['# October 2021: three-event observational comparison','','Catalogue footprints/timestamps only; no SAR valid support, phase, inversion or scene choice. ROI not supplied. Eligibility is implemented QC/time only, NOT physical representativity.','',
        '## Published versus native discrete spectral peak','',
        '| acquisition | instrument | UTC spectrum | QC E | Tp published s | Tp bin s | Hm0 derived m | sigma frequency Hz | numerical local maxima |',
        '|---|---|---|---:|---:|---:|---:|---:|---|']
    for curve in curves:
        d=curve['diagnostics'];lines.append(f"|{d['acquisition_id']}|{d['instrument_id']}|{d['sensor_time_utc']}|{d['qcFlagE']}|{d['published_Tp_s']}|{d['Tp_bin_s']}|{d['Hm0_m']}|{d['frequency_standard_deviation_hz']}|{[(p['frequency_hz'],p['energy_density']) for p in d['local_maxima_no_smoothing'][:5]]}|")
    lines+=['','## Interpretation limits','',
        'Published Tp can use a supplier parabolic fit while the diagnostic uses the maximum native bin. The two definitions are not interchangeable; the metadata definition is retained in SPECTRAL_DIAGNOSTICS.json. Native bin steps and half-peak contiguous widths quantify sampling/broadness, not extra resolution from plotting. Numerical adjacent maxima do NOT prove multiple independent wave systems.','',
        'Waverider ~9.55 s versus AWAC ~8.32 s is evaluated using their own spectra, QC, original nominal position/depth and time. Even the discrete-bin periods differ (~9.30 versus ~8.16 s); supplier peak fitting alone does not remove the difference. Direction mean/mode/spread at the published peak frequency are preserved separately in EVENT_PARAMETERS.csv and diagnostics, not replaced by whole-spectrum mean.','',
        'No automatic explanation by refraction, current, instrument bias or distinct systems. Nominal depths/positions and unverified burst anchors constrain interpretation; the recovered context does not bridge the long gap between TSX and later events. No sensor/current or wind-height conversion.','',
        f"Shared parameter references: {len(shared)} entries in COMMON_RECORDS.json; COSMO/TDX references can be identical and are never counted as separate spectra in the overlay.",'',
        'Wind height/elevation and averaging hints, current components/depth bins and tide datum remain original in EVENT_PARAMETERS.csv and per-event TENSORS/REPORT. Missing/technical/unsupported states and survey references remain in each dossier; no full surveyed seabed coverage is inferred.','',
        'Figures: map, unique spectra overlay and context series use supplier QC distinctions; context uses scatter to avoid connecting gaps.']
    (output/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


def _map(records,events,output):
    fig,ax=plt.subplots(figsize=(9,7))
    for r in records:
        geo=polygon(r['footprint']);x,y=geo.exterior.xy;ax.plot(x,y,label=r['acquisition_id']+' catalogue footprint')
    positions={}
    for r in events:
        position=json.loads(r['lon_lat_json'])
        if position:positions[(r['instrument_id'],tuple(position))]=position
    for (name,_),p in positions.items():ax.plot(*p,'o',label=name+' nominal sensor')
    unresolved=sorted({r['instrument_id'] for r in events if json.loads(r['lon_lat_json']) is None})
    if unresolved:ax.text(.02,.98,'Unresolved positions: '+', '.join(unresolved),transform=ax.transAxes,va='top',fontsize=8)
    x0,x1=ax.get_xlim();y0,y1=ax.get_ylim();ax.set_aspect(1/max(np.cos(np.deg2rad((y0+y1)/2)),.01))
    lon=x0+.05*(x1-x0);lat=y0+.05*(y1-y0);dl=(x1-x0)*.2;length=inverse(lon,lat,lon+dl,lat)[0]
    ax.plot([lon,lon+dl],[lat,lat],'k-',lw=3);ax.text(lon,lat,f'{length/1000:.2f} km',va='bottom')
    ax.annotate('N',xy=(.92,.93),xytext=(.92,.80),xycoords='axes fraction',arrowprops={'arrowstyle':'->'},ha='center')
    ax.set(xlabel='Longitude WGS84',ylabel='Latitude WGS84',title='Three catalogue footprints; valid SAR support NOT VERIFIED')
    ax.legend(fontsize=7);fig.tight_layout();fig.savefig(output/'FOOTPRINTS_INSTRUMENTS.png',dpi=150);plt.close(fig)


def _context(sources,records,output):
    from .data import cf_times
    fig,axs=plt.subplots(2,1,figsize=(10,7),sharex=True)
    origin=utc(records[0]['timestamp_utc']).timestamp()
    for source,tensor in sources.items():
        v=tensor['variables'];times=cf_times(v['time']['raw_values'],v['time']['attributes']['units']);qc=np.asarray(v.get('qcFlagE',{}).get('raw_values',[np.nan]*len(times)),float)
        for ax,name in zip(axs,['waveHs','waveTp']):
            if name not in v:continue
            values=np.asarray(v[name]['raw_values'],float);valid=np.asarray(v[name]['valid_mask']);x=(times-origin)/3600
            for mask,marker,label in [(valid&(qc==1),'o','QC1'),(valid&np.isfinite(qc)&(qc!=1),'x','QC failed'),(valid&~np.isfinite(qc),'s','QC unknown')]:
                if np.any(mask):ax.scatter(x[mask],values[mask],s=17,marker=marker,label=tensor['stable_identity']+' '+label)
    for ax,name in zip(axs,['Hs original m','Tp published s']):
        for r in records:ax.axvline((utc(r['timestamp_utc']).timestamp()-origin)/3600,alpha=.4,label=r['acquisition_id'])
        ax.set(ylabel=name);ax.legend(fontsize=6,ncol=2)
    axs[-1].set(xlabel='Hours after first catalogue event');fig.suptitle('Recovered context only; points, no interpolation across gaps')
    fig.tight_layout();fig.savefig(output/'WAVE_CONTEXT.png',dpi=150);plt.close(fig)
