#!/usr/bin/env python3
"""FRF inventory/fetch/offline CLI. No radar reading or mission-specific retrieval."""
import argparse
import json
from pathlib import Path
from frf_client.transport import Transport, save_json
from frf_client.catalog import ROOT, catalog
from frf_client.inputs import adapt_cleos, adapt_eoweb


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mode", choices=["inventory","fetch","offline"], default="offline")
    ap.add_argument("--config", default="examples/frf/client.json")
    ap.add_argument("--input")
    ap.add_argument("--output", default="outputs/frf_client")
    ap.add_argument("--cache", default="_cache/frf_client")
    ap.add_argument("--inspect-catalog")
    ap.add_argument("--prepare-regressions", action="store_true")
    ap.add_argument("--audit-frozen", action="store_true")
    ap.add_argument("--acquisition-id")
    ap.add_argument("--timestamp-utc")
    ap.add_argument("--footprint", help="GeoJSON geometry file")
    ap.add_argument("--roi", help="GeoJSON geometry file")
    ap.add_argument('--roi-outside',choices=['reject','allow'],default='reject')
    ap.add_argument('--tranche',help='Explicit persistent network tranche name')
    ap.add_argument('--new-tranche',action='store_true')
    ap.add_argument('--budget-config',help='Separate authorized budget JSON')
    ap.add_argument('--tranche-root',default='_cache/frf_tranches')
    ap.add_argument('--reuse-cache',action='append',default=[])
    ap.add_argument('--dry-run',action='store_true',help='Cache-only planning; never HTTP')
    args = ap.parse_args(argv)
    repository=Path(__file__).resolve().parents[1]
    if Path.cwd().resolve() != repository:
        ap.error("Run only from repository root")
    for frozen in ('Block32_frf_client','Block33_frf_offline_correction'):
        if Path(args.output).resolve().is_relative_to(repository/frozen):ap.error("Frozen artifacts: select new output directory")
        if Path(args.cache).resolve().is_relative_to(repository/frozen):ap.error("Frozen cache: use a separate verified payload cache")
    for name in ("config","input","output","cache","footprint","roi","budget_config","tranche_root"):
        value=getattr(args,name)
        if value and not Path(value).resolve().is_relative_to(repository):
            ap.error("All input/output/cache/config paths must be inside repository root")
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    if not Path(config.get("legacy_cache",'_cache/no_legacy')).resolve().is_relative_to(repository):
        ap.error("Legacy cache must be inside repository")
    if any(word in key.lower() for key in config for word in ("secret","password","token","credential")):
        ap.error("Anonymous FRF adapter does not accept credential configuration")
    from frf_client.inputs import read_acquisitions,validate,validate_batch
    records=[];input_warnings=[]
    if not (args.audit_frozen or args.prepare_regressions or args.inspect_catalog):
        try:
            if args.input:records=read_acquisitions(args.input)
            else:
                if not args.acquisition_id or not args.timestamp_utc:ap.error('--input or acquisition-id + timestamp-utc required')
                def geometry(path):
                    if not path:return None
                    obj=json.loads(Path(path).read_text(encoding='utf-8-sig'))
                    return obj.get('geometry') if obj.get('type')=='Feature' else obj
                records=[validate({'acquisition_id':args.acquisition_id,'timestamp_utc':args.timestamp_utc,'footprint':geometry(args.footprint),'roi':geometry(args.roi)})]
            records,input_warnings=validate_batch(records,args.roi_outside)
        except (ValueError,KeyError) as exc:ap.error(str(exc))
    for path in args.reuse_cache:
        if not Path(path).resolve().is_relative_to(repository):ap.error('Reuse cache must be within root')
    if args.new_tranche and not args.tranche:ap.error('--new-tranche requires --tranche')
    if args.mode!='offline' and not args.dry_run and not args.tranche:ap.error('Live inventory/fetch requires explicit named --tranche')
    budget=json.loads(Path(args.budget_config).read_text()) if args.budget_config else {k:config.get(k,d) for k,d in [('max_requests',40),('max_bytes',104857600),('max_response',8388608)]}
    if any(not isinstance(budget[k],int) or budget[k]<=0 for k in ('max_requests','max_bytes','max_response')):ap.error('Budget limits must be positive integers')
    if args.new_tranche and not args.budget_config:ap.error('New tranche requires explicit --budget-config authorization')
    named={}
    if args.tranche:
        import re
        if args.tranche in ('.','..') or not re.fullmatch(r'[A-Za-z0-9_.-]+',args.tranche):ap.error('Invalid tranche name')
        if not (Path(args.tranche_root)/args.tranche).resolve().is_relative_to(repository):ap.error('Tranche state must remain inside repository')
        named=dict(tranche_directory=Path(args.tranche_root)/args.tranche,tranche_name=args.tranche,new_tranche=args.new_tranche)
    from frf_client.operational import PlanningTransport
    cls=PlanningTransport if args.dry_run else Transport
    transport = cls(args.cache, offline=args.mode=="offline" or args.dry_run,
                          max_requests=budget["max_requests"], max_bytes=budget["max_bytes"],
                          max_response=budget["max_response"], timeout=config["timeout_seconds"],
                          rate_seconds=config["rate_seconds"], retries=config["retries"],
                          failure_ttl=config["failure_ttl_seconds"],**named)
    imports=[]
    for cache in args.reuse_cache:imports.extend(transport.import_verified(cache))
    if config.get('legacy_cache'):imports.extend(transport.import_legacy(config["legacy_cache"]))
    save_json(Path(args.output)/"LEGACY_CACHE_AUDIT.json", imports)
    if args.audit_frozen:
        from frf_client.provenance import audit
        path = Path("Block32_frf_client/FROZEN_INPUT_HASHES.json")
        if not path.exists():
            save_json(Path(args.output)/"FROZEN_AUDIT.json",{"status":"manifest_unavailable"})
            return 1
        hashes=json.loads(path.read_text())
        rows=audit(hashes,repository,{"D:/Dati Tesi/Umbra":"."})
        save_json(Path(args.output)/"FROZEN_AUDIT.json",{"entries":rows,"absolute_path_remapping":{"D:/Dati Tesi/Umbra":"."}})
        print(json.dumps({state:sum(r["status"]==state for r in rows) for state in ("hash_verified","mismatch","file_unavailable","unresolved_path")}))
        return int(any(r["status"]!="hash_verified" for r in rows))
    if args.prepare_regressions:
        if not Path("Block30_duck_csk_preflight/cleos_export/results_COSMO-SkyMed_20190911_20260916.json").is_file() or not Path("Block31_tsx_duck_query/eoweb_export/resultTableExport_1789663304925.csv").is_file():
            ap.error("Historical original exports unavailable; use tracked Block32 REGRESSION_ACQUISITIONS.json. No inputs fabricated.")
        records = adapt_cleos("Block30_duck_csk_preflight/cleos_export/results_COSMO-SkyMed_20190911_20260916.json", ["2098202","1941935","1942455"])
        records += adapt_eoweb("Block31_tsx_duck_query/eoweb_export/resultTableExport_1789663304925.csv", [11])
        for record in records:
            if record["acquisition_id"] == "COSMO_2098202":
                record["timestamp_utc"]="2021-10-13T22:45:03+00:00"
                record["timestamp_semantics"]="requested_catalogue_timestamp_at_second_precision_not_verified_aperture_center"
        records.sort(key=lambda r:r["timestamp_utc"],reverse=True)
        save_json(Path(args.output)/"REGRESSION_ACQUISITIONS.json", {"acquisitions": records})
        print("Prepared 4 strict regression inputs; no network")
        return 0
    if args.inspect_catalog:
        obj = catalog(transport, args.inspect_catalog)
        save_json(Path(args.output)/"DISCOVERY_LAST.json", obj)
        print(json.dumps(obj, indent=2))
        return 0
    from frf_client.client import Client
    client = Client(transport, config)
    before=transport.state.copy()
    client.run(records, Path(args.output), mode='offline' if args.dry_run else args.mode)
    from frf_client.operational import execution_summary,plan
    execution_summary(records,Path(args.output),input_warnings,transport,before)
    if args.dry_run:save_json(Path(args.output)/'RECOVERY_PLAN.json',plan(records,config,transport))
    print(json.dumps(transport.state, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
