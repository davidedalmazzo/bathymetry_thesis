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
    ap.add_argument("--config", default="Block32_frf_client/CONFIG.json")
    ap.add_argument("--input")
    ap.add_argument("--output", default="Block32_frf_client/results")
    ap.add_argument("--cache", default="Block32_frf_client/cache")
    ap.add_argument("--inspect-catalog")
    ap.add_argument("--prepare-regressions", action="store_true")
    ap.add_argument("--audit-frozen", action="store_true")
    ap.add_argument("--acquisition-id")
    ap.add_argument("--timestamp-utc")
    ap.add_argument("--footprint", help="GeoJSON geometry file")
    ap.add_argument("--roi", help="GeoJSON geometry file")
    args = ap.parse_args(argv)
    repository=Path(__file__).resolve().parents[1]
    if Path.cwd().resolve() != repository:
        ap.error("Run only from repository root")
    for name in ("config","input","output","cache","footprint","roi"):
        value=getattr(args,name)
        if value and not Path(value).resolve().is_relative_to(repository):
            ap.error("All input/output/cache/config paths must be inside repository root")
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    if config["max_requests"]>40 or config["max_bytes"]>100*1024**2:
        ap.error("This authorized tranche cannot exceed 40 HTTP transactions / 100 MiB")
    if not Path(config["legacy_cache"]).resolve().is_relative_to(repository):
        ap.error("Legacy cache must be inside repository")
    if any(word in key.lower() for key in config for word in ("secret","password","token","credential")):
        ap.error("Anonymous FRF adapter does not accept credential configuration")
    transport = Transport(args.cache, offline=args.mode=="offline",
                          max_requests=config["max_requests"], max_bytes=config["max_bytes"],
                          max_response=config["max_response"], timeout=config["timeout_seconds"],
                          rate_seconds=config["rate_seconds"], retries=config["retries"],
                          failure_ttl=config["failure_ttl_seconds"])
    imports = transport.import_legacy(config["legacy_cache"])
    save_json(Path(args.output)/"LEGACY_CACHE_AUDIT.json", imports)
    if args.audit_frozen:
        from frf_client.transport import digest
        path = Path("Block32_frf_client/FROZEN_INPUT_HASHES.json")
        if not path.exists():
            files = [p for root in [Path("Block30_duck_csk_preflight"),Path("Block31_tsx_duck_query")] for p in root.rglob("*") if p.is_file()]
            files += [Path("code/run_block30_frf_conditions.py"),Path("tests/test_block30_frf_conditions.py")]
            for old in [Path("Block29_Samoa_mapping_trial/MANIFEST.json"),Path("Block28_Samoa_metadata_preflight/DELIVERY_MANIFEST.json")]:
                files.append(old)
                obj=json.loads(old.read_text())
                files += [Path(e["path"]) for e in obj["artifacts"]]
            save_json(path,[{"path":str(p),"bytes":p.stat().st_size,"sha256":digest(p.read_bytes())} for p in sorted(set(files))])
        hashes=json.loads(path.read_text())
        bad=[e["path"] for e in hashes if digest(Path(e["path"]).read_bytes()) != e["sha256"]]
        save_json("Block32_frf_client/FROZEN_AUDIT.json",{"checked":len(hashes),"mismatches":bad})
        print(f"Frozen files: {len(hashes)} checked, {len(bad)} mismatches")
        return 1 if bad else 0
    if args.prepare_regressions:
        records = adapt_cleos("Block30_duck_csk_preflight/cleos_export/results_COSMO-SkyMed_20190911_20260916.json", ["2098202","1941935","1942455"])
        records += adapt_eoweb("Block31_tsx_duck_query/eoweb_export/resultTableExport_1789663304925.csv", [11])
        for record in records:
            if record["acquisition_id"] == "COSMO_2098202":
                record["timestamp_utc"]="2021-10-13T22:45:03+00:00"
                record["timestamp_semantics"]="requested_catalogue_timestamp_at_second_precision_not_verified_aperture_center"
        records.sort(key=lambda r:r["timestamp_utc"],reverse=True)
        save_json("Block32_frf_client/REGRESSION_ACQUISITIONS.json", {"acquisitions": records})
        print("Prepared 4 strict regression inputs; no network")
        return 0
    if args.inspect_catalog:
        obj = catalog(transport, args.inspect_catalog)
        save_json(Path(args.output)/"DISCOVERY_LAST.json", obj)
        print(json.dumps(obj, indent=2))
        return 0
    from frf_client.client import Client
    from frf_client.inputs import read_acquisitions, validate
    if args.input:
        records = read_acquisitions(args.input)
    else:
        if not args.acquisition_id or not args.timestamp_utc:
            ap.error("--input or both --acquisition-id and --timestamp-utc required")
        records = [validate({"acquisition_id":args.acquisition_id, "timestamp_utc":args.timestamp_utc,
                             "footprint":json.loads(Path(args.footprint).read_text()) if args.footprint else None,
                             "roi":json.loads(Path(args.roi).read_text()) if args.roi else None})]
    client = Client(transport, config)
    client.run(records, Path(args.output), mode=args.mode)
    print(json.dumps(transport.state, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
