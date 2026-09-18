"""Operational cache-only planner and per-run summary; no scientific inference."""
import json
from pathlib import Path
from .transport import Transport,FetchError,save_json
from .temporal import event_windows,months_needed


class PlanningTransport(Transport):
    def __init__(self,*args,**kwargs):
        kwargs['offline']=True;super().__init__(*args,**kwargs);self.attempts=[]
    def get(self,url):
        try:
            raw=super().get(url);self.attempts.append({'url':url,'status':'verified_cache','bytes':len(raw)});return raw
        except FetchError as exc:
            self.attempts.append({'url':url,'status':exc.status,'bytes':None});raise


def plan(records,config,transport):
    unique={a['url']:a for a in transport.attempts}
    missing=[a for a in unique.values() if a['status']!='verified_cache']
    return {'actual_http_transactions':0,'requested_acquisitions':[r['acquisition_id'] for r in records],
            'verified_cache_inventory':[{k:e[k] for k in ('url','sha256','bytes')} for p in sorted(transport.directory.glob('*.json')) if (e:=json.loads(p.read_text())).get('status')=='ok'],
            'attempted_cache_reuse':list(unique.values()),'missing_requests_known':missing,
            'event_windows':{f:event_windows(records,config,f) for f in config['families'] if f!='bathymetry'},
            'calendar_months':{f:months_needed(records,config,f) for f in config['families'] if f!='bathymetry'},
            'cost_estimate':{'known_missing_transaction_lower_bound':len(missing),'estimated_new_bytes':None,'upper_bound_bytes':transport.state['max_bytes'],
                'uncertainty':'Request count is a lower bound: unknown metadata/catalog descendants, retry, redirects and payload sizes require live inspection. No annual observed arrays planned.'}}


def execution_summary(records,output,warnings,transport,before):
    lines=['# FRF execution summary','','Eligibility means implemented availability/QC/time checks only, NOT physical representativity.','',
           f"New HTTP transactions this run: {transport.state['transactions']-before['transactions']}; received bytes: {transport.state['bytes']-before['bytes']}",
           f"Tranche: {transport.state.get('tranche_name','unnamed offline/legacy cache state')}",'',
           'Inputs are catalogue/user timestamps, not verified aperture centers or physical dwell.','',
           'No ROI is invented. Catalogue footprints are not verified valid SAR support.','']
    import re
    for r in records:
        folder=re.sub(r'[^A-Za-z0-9_.-]','_',r['acquisition_id'])
        lines.append(f"- [{r['acquisition_id']}]({folder}/REPORT.md): {r['timestamp_utc']}")
    lines+=['','Input warnings: '+json.dumps(warnings),'','Missing data, incomplete searches and technical failures are preserved per dossier, not silently called a complete oceanographic state.']
    (output/'SUMMARY.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    save_json(output/'RUN_STATE.json',{'network_before':before,'network_after':transport.state,'input_warnings':warnings,
        'new_http_transactions':transport.state['transactions']-before['transactions'],'new_received_bytes':transport.state['bytes']-before['bytes'],'physical_representativity_verified':False})
