#!/usr/bin/env python
"""Download selected members of a Sentinel-1 SAFE from CDSE (OData Nodes API).

Only what processing needs for one polarisation: manifest.safe, the measurement
TIFF(s), their annotation, calibration and noise XML.  Each file is fetched into
<out>/<PRODUCT>.SAFE/<same relative path>, resumed with HTTP Range from a .part
file (the whole-product endpoint answers Range with 501), and verified against
the MD5 listed in manifest.safe before being renamed.  Credentials come from the
Git-ignored .env via cdse_credentials.TokenProvider and are never logged.

  python code/download_s1_safe_members.py 45382fde-3276-5c0b-b5e6-f7a733557815 --pol vv
"""
from __future__ import annotations
import argparse, hashlib, json, sys, time, urllib.error, urllib.request
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent))
from repository_paths import ROOT                                 # noqa: E402
import download_block37_s1 as dl                                   # noqa: E402
from cdse_credentials import TokenProvider                         # noqa: E402

CAT = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products({u})"
DL = "https://download.dataspace.copernicus.eu/odata/v1/Products({u})/Nodes({n})"


def node_url(base, rel):
    return base + "".join(f"/Nodes({p})" for p in rel.split("/")) + "/$value"


def fetch(opener, token, url, part, total, deadline, chunk=4 * 1024 ** 2):
    start = part.stat().st_size if part.exists() else 0
    if start >= total:
        return True
    headers = {"Authorization": "Bearer " + token.get(), "User-Agent": "thesis-s1-members/1.0"}
    if start:
        headers["Range"] = f"bytes={start}-"
    try:
        r = opener.open(urllib.request.Request(url, headers=headers), timeout=120); code = r.status
    except urllib.error.HTTPError as e:
        r = e; code = e.code
    try:
        if code != (206 if start else 200):
            raise RuntimeError(f"HTTP {code} for {url.rsplit('/Nodes(', 1)[-1]}")
        ctype = (r.headers.get("Content-Type") or "").lower()
        if "json" in ctype or "html" in ctype:
            raise RuntimeError("refused non-data response " + ctype)
        if start and r.headers.get("Content-Range") != f"bytes {start}-{total - 1}/{total}":
            raise RuntimeError("Content-Range mismatch")
        with part.open("ab" if start else "wb") as f:
            while time.time() < deadline:
                b = r.read(chunk)
                if not b:
                    break
                f.write(b)
    finally:
        r.close()
    return part.stat().st_size >= total


def md5(path):
    h = hashlib.md5()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(8 * 1024 ** 2), b""):
            h.update(b)
    return h.hexdigest()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("uuid"); ap.add_argument("--pol", default="vv"); ap.add_argument("--out", default="data_s1")
    ap.add_argument("--max-seconds", type=float, default=1e9, help="stop cleanly after this time (resume later)")
    a = ap.parse_args(argv); deadline = time.time() + a.max_seconds
    meta = json.loads(urllib.request.urlopen(CAT.format(u=a.uuid) + "?$select=Name", timeout=60).read())
    name = meta["Name"]; safe = ROOT / a.out / name; safe.mkdir(parents=True, exist_ok=True)
    audit = dl.DownloadAudit(ROOT / a.out / f"{name}.members_audit.json", 120)
    token = TokenProvider(audit, ROOT / ".env", max_requests=3)
    opener = urllib.request.build_opener(dl.NoRedirect())
    base = DL.format(u=a.uuid, n=name)
    man = safe / "manifest.safe"
    if not man.exists():
        req = urllib.request.Request(node_url(base, "manifest.safe"), headers={"Authorization": "Bearer " + token.get()})
        man.write_bytes(opener.open(req, timeout=120).read())
    ns = {"x": "urn:ccsds:schema:xfdu:1"}
    items = []
    for do in ET.parse(man).getroot().iter("dataObject"):
        loc = do.find(".//fileLocation"); cs = do.find(".//checksum"); bs = do.find(".//byteStream")
        rel = loc.get("href").lstrip("./"); low = rel.lower()
        if f"-{a.pol.lower()}-" in low and (low.startswith("measurement/") or low.startswith("annotation/")):
            items.append((rel, int(bs.get("size")), cs.text.strip().lower()))
    if not items:
        raise SystemExit("no members for polarisation " + a.pol)
    done = 0
    for rel, size, want in sorted(items, key=lambda t: t[1]):
        dst = safe / rel; dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists() and dst.stat().st_size == size:
            done += 1; continue
        part = dst.with_name(dst.name + ".part")
        if not fetch(opener, token, node_url(base, rel), part, size, deadline):
            print(f"PAUSED {rel} {part.stat().st_size}/{size}"); break
        got = md5(part)
        if got != want:
            raise RuntimeError(f"MD5 mismatch for {rel}; .part preserved")
        part.replace(dst); done += 1; audit.event("member_verified", path=rel, bytes=size, md5=got)
        print("VERIFIED", rel, size)
    print(f"{done}/{len(items)} members complete in {safe.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
