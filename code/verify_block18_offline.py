"""Reparse saved Block18 payloads and compare every normalized value offline."""
import csv, json
from pathlib import Path
import numpy as np
from umbra_sar.reference_recovery import normalize_payload, spectrum_metrics

def datetime_epoch(value):
 from datetime import datetime
 return datetime.fromisoformat(value).timestamp()

root=Path(__file__).resolve().parents[1]; out=root/"Block18_reference_recovery"
cfg=json.loads((out/"BLOCK18_CONFIG.json").read_text()); das=(out/"payloads_raw/42084w9999.das").read_text(errors="replace")
saved=list(csv.DictReader((out/"BLOCK18_NORMALIZED_BINS.csv").open()))
by={}
for row in saved: by.setdefault(row["acquisition_key"],[]).append(row)
verified=[]
for a in cfg["acquisitions"]:
 key=a["acquisition_key"]; stem=key.split(":",1)[1]
 meta=json.loads((out/"normalized"/f"{stem}_metadata.json").read_text())
 text=(out/"payloads_raw"/f"{stem}_spectrum.ascii").read_text(errors="replace")
 n=normalize_payload(text,das,observation_epoch_s=datetime_epoch(meta["observation_utc"]),joint_band=tuple(cfg["validity"]["joint_band_hz"]))
 rows=by[key]
 assert len(rows)==len(n["frequency_hz"])
 maxerr=0.0
 for i,row in enumerate(rows):
  maxerr=max(maxerr,abs(float(row["frequency_hz"])-n["frequency_hz"][i]),abs(float(row["band_width_hz"])-n["band_width_hz"][i]))
  for v in n["arrays"]: maxerr=max(maxerr,abs(float(row[v])-n["arrays"][v][i]))
 assert maxerr==0
 assert spectrum_metrics(n)==json.loads((out/"normalized"/f"{stem}_metrics.json").read_text())
 verified.append({"acquisition_key":key,"bins":len(rows),"maximum_numeric_difference":maxerr})
print(json.dumps({"offline_reproduction":"exact","acquisitions":verified},indent=2))
