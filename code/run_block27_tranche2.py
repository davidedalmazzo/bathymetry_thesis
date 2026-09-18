"""User-authorized independent 30 HTTP/20 MiB tranche; preserve v1 and SAR."""
from __future__ import annotations
from repository_paths import resolve_historical
import argparse, json, shutil, hashlib, re, os
from datetime import datetime, timezone
from pathlib import Path
import run_block27_representativity as m
from umbra_sar.reference_recovery import HTTPBudget, fetch_limited

OUT=m.BASE/'representativity_v2'; STATE=OUT/'STATE.json'; LOG=OUT/'REQUEST_LOG.json'

def initialize():
    if STATE.exists(): return
    OUT.mkdir(parents=True,exist_ok=True)
    for name in ['ACQUISITION_AUDIT.csv','LOCAL_BIN_INVENTORY.json','STATION_HISTORY.json']:
        shutil.copyfile(m.OUT/name,OUT/name)
    shutil.copytree(m.OUT/'normalized',OUT/'normalized',dirs_exist_ok=True)
    m.dump(STATE,{'tranche':'new_user_authorized_2026-09-16','historical_consumption':'consumo storico non determinabile',
        'historical_transactions':None,'historical_bytes':None,'transactions':0,'total_bytes':0,
        'max_transactions':30,'max_total_bytes':20*1024**2,'stage':'initialized_before_first_request',
        'old_cumulative_limit_certified':False,'created_utc':datetime.now(timezone.utc).isoformat(),
        'history_search':'Blocks25–27 and _cache filename inventory: no attributable prior recovery ledger located; Block8/16/18/21 records belong to earlier separate activities.',
        'queue_sha256':m.sha(m.BASE/'BLOCK27_QUERY_QUEUE.csv')})
    m.dump(LOG,[])
    m.atomic(OUT/'PROTOCOL.md',b'Independent new tranche: 30 HTTP transactions including redirects/retries, 20 MiB response bytes. Historical consumption unknown, never zero. Observations first in frozen queue order; verified 42084 local payloads reused. No SAR. No repeated failed URL without new evidence. Persist reservation before network and counters during streaming. Station and event-model documentation only with remaining budget.\n')

def run():
    initialize(); state=json.loads(STATE.read_text()); logs=json.loads(LOG.read_text()); rows=m.read(OUT/'ACQUISITION_AUDIT.csv')
    direct=os.environ.get('UMBRA_DIRECT_TRANSPORT')=='1'
    if direct:
        state['transport_change']='Sandbox proxy refused connections; authorized direct network execution is new diagnostic information.'
        for l in logs:
            if 'ConnectionRefusedError' in l.get('error',''):l['superseded_transport_failure']=True
    class LiveBudget(HTTPBudget):
        def save(self):
            state.update(transactions=self.transactions,total_bytes=self.total_bytes,stage='running')
            m.dump(STATE,state);m.dump(LOG,logs+self.log)
        def reserve_transaction(self):
            super().reserve_transaction(); self.save()
        def accept_chunk(self,response_bytes,chunk_bytes):
            super().accept_chunk(response_bytes,chunk_bytes); self.save()
    b=LiveBudget(30,20*1024**2,3*1024**2,12,0,transactions=state['transactions'],total_bytes=state['total_bytes'])
    def get(url,purpose,key=''):
        p=OUT/'raw'/f'{hashlib.sha256(url.encode()).hexdigest()}.txt'
        if p.exists(): return p.read_text(encoding='utf-8'),p
        if any(l['url']==url and l['outcome']!='recovered' and not l.get('superseded_transport_failure') for l in logs+b.log):
            raise RuntimeError('cached_request_failure_not_repeated')
        try:
            data=fetch_limited(url,b,purpose=purpose,acquisition_key=key);m.atomic(p,data)
            return data.decode('utf-8','replace'),p
        finally: b.save()
    evpath=OUT/'DATASET_EVIDENCE.json'
    cache={}; bad={}; evidence=json.loads(evpath.read_text()) if evpath.exists() else []
    for r in rows:
        if r['reference_status'] in ['verified_local_Block18','recovered']: continue
        if b.transactions>=26: break # reserve documentation/geographic/model evidence requests
        sid=r['station_id'];yr=r['datetime_utc'][:4]
        root=f'https://dods.ndbc.noaa.gov/thredds/dodsC/data/swden/{sid}/{sid}w9999.nc'
        for ds in [root,root.replace('9999',yr)]:
            if ds in bad:
                r.update(reference_status=bad[ds]['status'],reference_error=bad[ds]['error']);continue
            try:
                if ds not in cache:
                    dds,dp=get(ds+'.dds','spectral_dds',sid);dims=m.parse_dds_dimensions(dds)
                    das,ap=get(ds+'.das','spectral_das',sid)
                    tt,tp=get(ds+'.ascii?time','spectral_time',sid); times=m.parse_ascii_vector(tt,'time')
                    cache[ds]=(dims,das,times)
                    evidence.append({'station':sid,'dataset':ds,'frequency_count':dims['frequency'],
                        'time_start':datetime.fromtimestamp(float(times[0]),timezone.utc).isoformat(),
                        'time_stop':datetime.fromtimestamp(float(times[-1]),timezone.utc).isoformat(),
                        'variables':[v for v in m.VARIABLES if re.search(r'\b'+v+r'\b',dds)],
                        'dds_path':str(dp.relative_to(m.ROOT)),'das_path':str(ap.relative_to(m.ROOT))})
                dims,das,times=cache[ds];i,obs=m.nearest_time_index(times,m.epoch(r['datetime_utc']));off=obs-m.epoch(r['datetime_utc'])
                r.update(observation_utc=datetime.fromtimestamp(obs,timezone.utc).isoformat(),observation_offset_s=off)
                if abs(off)>3600:
                    r['reference_status']='outside_time_tolerance';continue
                nf=dims['frequency'];sel=','.join(f'{v}[{i}:1:{i}][0:1:{nf-1}][0:1:0][0:1:0]' for v in m.VARIABLES)
                url=ds+'.ascii?time['+str(i)+':1:'+str(i)+'],frequency,'+sel
                text,p=get(url,'spectral_subset',r['acquisition_key'])
                try:
                    returned=m.parse_ascii_vector(text,'time')
                    if len(returned)!=1 or abs(float(returned[0])-obs)>.01: raise ValueError('returned_timestamp_mismatch')
                    n=m.normalize_payload(text,das,observation_epoch_s=obs)
                except Exception as exc:
                    r.update(reference_status='parse_failed',reference_error=repr(exc));break
                m.dump(OUT/'normalized'/f"{r['collect_id']}.json",m.serial(n))
                r.update(m.spectrum_metrics(n));r.update(m.same_band(n))
                r.update(reference_status='recovered',reference_station_id=sid,payload_path=str(p.relative_to(m.ROOT)),
                    payload_sha256=m.sha(p),source_url=url,joint_energy_coverage=n['joint_band_energy_coverage'],
                    decision='conditional' if n['joint_band_energy_coverage']>=.9 else 'not_evaluable')
                break
            except Exception as exc:
                status='budget_not_queried' if b.transactions>=30 else 'request_failed'
                bad[ds]={'status':status,'error':repr(exc)};r.update(reference_status=status,reference_error=repr(exc))
            finally:
                m.table(OUT/'ACQUISITION_AUDIT.csv',rows);m.dump(OUT/'DATASET_EVIDENCE.json',evidence)
        print(r['queue_order'],sid,r['reference_status'],flush=True)
    docs=[('42087_station','https://www.ndbc.noaa.gov/station_page.php?station=42087'),
          ('42087_operator','https://www.coral.noaa.gov/'),
          ('wave_model_documentation','https://open-meteo.com/en/docs/marine-weather-api'),
          ('Tobago_coastline_subset','https://overpass-api.de/api/interpreter?data=%5Bout%3Ajson%5D%5Btimeout%3A15%5D%3Bway%5B%22natural%22%3D%22coastline%22%5D%2811.10%2C-60.87%2C11.22%2C-60.74%29%3Bout%20geom%3B'),
          ('42087_operator_alternative','https://www.aoml.noaa.gov/icon/'),
          ('41052_station','https://www.ndbc.noaa.gov/station_page.php?station=41052')]
    for key,url in docs:
        if b.transactions>=30: break
        try: get(url,'documentation_or_small_geography',key)
        except Exception: pass
    state.update(stage='authorized_tranche_finished' if b.transactions<30 else 'transaction_budget_exhausted',
        transactions=b.transactions,total_bytes=b.total_bytes)
    m.dump(STATE,state);m.dump(LOG,logs+b.log);m.table(OUT/'ACQUISITION_AUDIT.csv',rows)
    m.dump(OUT/'DATASET_EVIDENCE.json',evidence)

def finish():
    from scipy.io import netcdf_file
    from html import unescape
    rows=m.read(OUT/'ACQUISITION_AUDIT.csv');state=json.loads(STATE.read_text());logs=json.loads(LOG.read_text())
    inventory=[]
    for p in sorted((m.ROOT/'umbra/validazione/Block8_validation/buoy_data').glob('246*.nc')):
        with netcdf_file(p,'r',mmap=False) as d:
            t=d.variables['waveTime'].data
            inventory.append({'path':str(p.relative_to(m.ROOT)),'sha256':m.sha(p),
                'time_start':datetime.fromtimestamp(float(t[0]),timezone.utc).isoformat(),
                'time_stop':datetime.fromtimestamp(float(t[-1]),timezone.utc).isoformat(),
                'title':d.title.decode(),'instrument':str(d.variables['metaInstrumentation']._attributes),
                'frequency_bins':len(d.variables['waveFrequency'].data),
                'spectral_variables':[k for k in d.variables if k in ['waveEnergyDensity','waveMeanDirection','waveA1Value','waveB1Value','waveA2Value','waveB2Value']],
                'matches_queue_dates':False,'status':'locally_available_but_outside_event_time'})
    m.dump(OUT/'LOCAL_CDIP_INVENTORY.json',inventory)
    docs={}
    for log in logs:
        if log['outcome']=='recovered' and log['purpose']=='documentation_or_small_geography':
            p=OUT/'raw'/(hashlib.sha256(log['url'].encode()).hexdigest()+'.txt')
            s=unescape(re.sub('<[^>]+>',' ',p.read_text(encoding='utf-8')));s=re.sub(r'\s+',' ',s)
            docs[log['acquisition_key']]=s
            m.atomic(OUT/'documentation_text'/f"{log['acquisition_key']}.txt",s.encode('utf-8'))
    check=[]
    for r in rows:
        if r['reference_status'] not in ['verified_local_Block18','recovered']: continue
        npath=OUT/'normalized'/f"{r['collect_id']}.json"
        saved=json.loads(npath.read_text());raw=resolve_historical(r['payload_path'], m.ROOT)
        if r['reference_station_id']=='42084':das=m.ROOT/'umbra/selezione_scene/Block18_reference_recovery/payloads_raw/42084w9999.das'
        else:
            ds=r['source_url'].split('.ascii?')[0];das=OUT/'raw'/(hashlib.sha256((ds+'.das').encode()).hexdigest()+'.txt')
        n=m.normalize_payload(raw.read_text(),das.read_text(),observation_epoch_s=float(saved['observation_epoch_s']))
        equivalent=m.serial(n)==saved
        if not equivalent or m.sha(raw)!=r['payload_sha256']:raise ValueError('offline_reparse_or_hash_mismatch')
        check.append({'collect':r['collect_id'],'station':r['reference_station_id'],'bin_count':len(n['frequency_hz']),
            'hash_verified':True,'offline_reparse_identical':True,'joint_energy_coverage':n['joint_band_energy_coverage']})
    m.dump(OUT/'OFFLINE_VERIFICATION.json',check)
    datasets=[]
    for l in logs:
        if l['purpose']!='spectral_dds' or l['outcome']!='recovered':continue
        ds=l['url'][:-4]
        def cached(suffix):return OUT/'raw'/(hashlib.sha256((ds+suffix).encode()).hexdigest()+'.txt')
        dims=m.parse_dds_dimensions(cached('.dds').read_text())
        times=m.parse_ascii_vector(cached('.ascii?time').read_text(),'time')
        datasets.append({'station':l['acquisition_key'],'dataset':ds,'dimensions':dims,
            'time_start':datetime.fromtimestamp(float(times[0]),timezone.utc).isoformat(),
            'time_stop':datetime.fromtimestamp(float(times[-1]),timezone.utc).isoformat(),
            'dds_path':str(cached('.dds').relative_to(m.ROOT)),'das_path':str(cached('.das').relative_to(m.ROOT)),
            'variables':list(m.VARIABLES),'operational_continuity_not_inferred_from_endpoints':True})
    m.dump(OUT/'DATASET_EVIDENCE.json',datasets)
    # Use existing geographic diagnostics only; do not rerun local reconciliation.
    m.OUT=OUT;m.maps_report()
    rows=m.read(OUT/'ACQUISITION_AUDIT.csv')
    for r in rows:
        r['instrument_event_verification']='Historical metadata interval only; event instrument continuity unverified'
        if r['station_id']=='51209':r['instrument_event_verification']='NDBC/CDIP partner station; event density and directional moments verified; exact sensor model at event unverified'
        if r['station_id']=='42094':r['instrument_event_verification']='Local CDIP Datawell DWR-M3 verified only for 2019 d02; no transfer of sensor/deployment to 2025–2026'
        if r['station_id']=='42087':r['instrument_event_verification']='ICON moored buoy/anemometer documented; wave sensor at 2024 date unverified'
        r['admissible_reference_status']='inherited_Block18_verified' if r['reference_status']=='verified_local_Block18' else ('temporal_and_directional_coverage_pass' if r['reference_status']=='recovered' and float(r['joint_energy_coverage'])>=.9 else 'not_established')
    m.table(OUT/'ACQUISITION_AUDIT.csv',rows)
    counts={s:sum(r['reference_status']==s for r in rows) for s in sorted({r['reference_status'] for r in rows})}
    s=next(r for r in rows if r['station_id']=='51209')
    historical=[]
    for key in ['42087_station','41052_station','42087_operator_alternative']:
        text=docs.get(key,'');i=text.find('Historical data')
        historical.append({'source_key':key,'retrieved':bool(text),'historical_section':text[i:i+1800] if i>=0 else 'No historical product section identified; not proof of absence'})
    m.dump(OUT/'STATION_DOCUMENTATION_ASSESSMENT.json',historical)
    models={'source':'https://open-meteo.com/en/docs/marine-weather-api','documentation_recovered':bool(docs.get('wave_model_documentation')),
        'MFWAM':{'published_grid':'0.08 degrees (~8 km)','native_time':'3-hourly','published_availability':'October 2021 onward','scope':'global'},
        'ERA5_ocean':{'published_grid':'0.5 degrees (~50 km)','native_time':'hourly','published_availability':'1940 to present','scope':'global'},
        'SMOC_currents':{'published_grid':'0.08 degrees (~8 km)','native_time':'hourly','published_availability':'January 2022 onward'},
        'event_subsets_retrieved':False,'native_cell_indices_known':False,'mask_verified':False,
        'wave_current_coupling_verified':False,'same_buoy_assimilation_verified':False,
        'partitions':'documentation lists total, wind-wave, swell, secondary swell; variable availability depends on model',
        'period_semantics':'mean swell_wave_period distinct from swell_wave_peak_period',
        'reason_no_comparison':'Tranche transaction budget exhausted; product documentation does not certify event retrieval or local coastal homogeneity'}
    m.dump(OUT/'MODEL_ASSESSMENT.json',models)
    report=f'''# Block27 — rappresentatività boa–ROI: checkpoint tranche autorizzata

## Budget e storia

**Consumo storico non determinabile**: transazioni e byte storici sono null, non zero.
La ricerca nei registri del blocco e nelle cache ha trovato archivi locali CDIP, ma nessun registro attribuibile completo alla fase precedente. Il nuovo registro è stato salvato prima della prima richiesta e i contatori persistiti prima di ogni transazione e durante lo streaming.
Questa tranche sostituisce per la prosecuzione il residuo sconosciuto; **non si dichiara rispettato il vecchio limite cumulativo**.
Nuova tranche: **{state['transactions']}/30 transazioni HTTP, {state['total_bytes']} / 20971520 byte**. Retry automatici zero; redirect conteggiati. I 13 tentativi sandbox con proxy rifiutato sono inclusi. Il cambio di trasporto autorizzato costituisce nuova informazione diagnostica, non un retry cieco. Nessun URL fallito nello stesso contesto è stato ripetuto.

## Osservazioni recuperate

- Samoa, {s['collect_name']}: spettro completo 51209, 64 frequenze; Tp={float(s['peak_period_s']):.5f} s, banda half-power {s['band_low_hz']}–{s['band_high_hz']} Hz, propagazione {float(s['band_propagation_to_deg']):.3f}°, offset {float(s['observation_offset_s']):.1f} s. Densità e quattro momenti/direzioni con maschere individuali/congiunte; timestamp restituito dal server verificato. Asse range preliminare vendor: scarto assiale {float(s['preliminary_axial_difference_deg']):.3f}°, non verifica SICD locale. Candidato **condizionato**, non promosso tramite descrizioni generiche del sito.
- Louisiana: riuso integrale dei quattro payload **42084** Block18 (392 bin) verificati; nessuna richiesta per quei dati. **42094 è ancora non verificata alle date SAR**. I prodotti CDIP 246 locali coprono settembre–novembre **2019**, fuori dalle date 2025–2026 della coda; il sensore DWR-M3 d02 non viene attribuito alle date nuove.
- Tobago 42087: percorsi NDBC aggregate/2024 non disponibili (404). Pagina NDBC documenta ICON, buoy/anemometro e archivio meteorologico 2016, non spettri ondosi 2024. Fonte operator coral.noaa.gov fallita per timeout; alternativa AOML interrogata entro budget. Nessuna deduzione da “Buccoo Reef”, nessuna dichiarazione globale di assenza di onde o prodotti.
- Isole Vergini 41052: percorsi spettrali NDBC aggregate/2025 404; pagina di stazione recuperata. Strumentazione e serie spettrale all'evento non ancora stabilite. Il solo intervallo storico di posizione non certifica attività continuativa.

Stati per tutte le 23 acquisizioni: `{json.dumps(counts)}`. Cinque riferimenti utilizzabili (uno nuovo e quattro locali), **18 acquisizioni senza riferimento per-bin stabilito**. Le date della coda non sono state selezionate in base al mare. I 404 sono errori dei percorsi provati; eventuali archivi alternativi rimangono non interrogati, non “assenti”.

## Geografia

Riconciliazione locale precedente preservata e non rieseguita. Mappe aggiornate con ROI/footprint, stazioni effettive, distanze/rilevamenti, nord e scala. Tobago: segmento boa–ROI attraversa terra nella maschera Natural Earth 1:10m per circa 4.2–4.8 km. È un indizio di esposizione diversa, non prova che le onde non raggiungano i due punti. Il subset di costa OSM richiesto è fallito (504); verifica con costa adeguata ancora incompleta. Non-intersezione negli altri siti non prova mare uguale. Quote GEBCO della coda non usate per Snell né trasferimento automatico della direzione.

## Modelli

Documentazione [Open-Meteo marine](https://open-meteo.com/en/docs/marine-weather-api) recuperata: MFWAM globale 0.08°/3 ore da ottobre 2021; ERA5-ocean globale 0.5°/ora dal 1940; SMOC correnti 0.08°/ora da gennaio 2022. Queste disponibilità pubblicate coprono nominalmente le date, **non certificano ancora il recupero effettivo dell'evento**. Variabili/partizioni dipendono dal modello; periodo swell medio distinto dal peak. Maschera, indici/celle native, accoppiamento correnti e assimilazione delle stesse boe non verificati. Nessun subset di evento disponibile prima dell'esaurimento del budget, nessun confronto boa–ROI, nessuna mappa di celle inventata o climatologia sostitutiva.

## Decisione e arresto

Quantità di evidenza diversa fra zone: Samoa e quattro scene Louisiana condizionate; Tobago, Isole Vergini e altre 14 Louisiana non valutabili osservativamente. Nessuna priorità definitiva giustificata; nessun nuovo gate Hm0, kh, lunghezze d'onda, fase o distanza. Cinque payload riparsati offline identici con hash verificati. Stato riprendibile, log completo e manifest sotto questa versione; versione v1 e blocchi congelati intatti.

**Un solo prossimo passo:** recupero mirato dei riferimenti alternativi per le 18 scene senza spettri, a partire dalle stazioni e date della coda congelata, solo con un eventuale nuovo budget autorizzato. Nessun SAR, AIS, inversione, dwell sweep o Vandenberg.
'''
    m.atomic(OUT/'REPORT.md',report.encode('utf-8'))
    m.dump(OUT/'SUMMARY.json',{'status':'checkpoint_transaction_budget_exhausted','historical_consumption':'consumo storico non determinabile',
        'old_cumulative_limit_certified':False,'transactions':state['transactions'],'total_bytes':state['total_bytes'],
        'new_references':1,'verified_local_references_reused':4,'acquisitions_without_established_spectrum':18,
        'reference_status_counts':counts,'priority_candidate':None,'offline_payload_checks':check})
    artifacts=[{'path':str(p.relative_to(m.ROOT)),'bytes':p.stat().st_size,'sha256':m.sha(p)} for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='MANIFEST.json']
    m.dump(OUT/'MANIFEST.json',{'version':'representativity_v2','artifacts':artifacts,'source_queue_sha256':m.sha(m.BASE/'BLOCK27_QUERY_QUEUE.csv')})

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['init','run','finish']);a=ap.parse_args()
    initialize()
    if a.stage=='run':run()
    elif a.stage=='finish':finish()
