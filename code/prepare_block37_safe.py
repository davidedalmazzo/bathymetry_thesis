"""Validate and safely extract the frozen Block37 Sentinel-1 SAFE archive."""
from __future__ import annotations
import argparse,json,os,shutil,stat,zipfile
from datetime import datetime,timezone
from pathlib import Path,PurePosixPath
from repository_paths import ROOT
from frf_client.transport import save_json

BASE=ROOT/'duck_frf/Block37_s1_iw_spatial_trial'


def validate_members(archive,product_name):
    root=product_name.rstrip('/')
    rows=[]
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            name=info.filename;path=PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts or '\\' in name or not path.parts or path.parts[0]!=root:
                raise ValueError('Unsafe or unexpected SAFE member path: '+name)
            mode=(info.external_attr>>16)&0xFFFF
            if stat.S_ISLNK(mode):raise ValueError('SAFE archive contains a symbolic link')
            rows.append({'path':name,'bytes':info.file_size,'compressed_bytes':info.compress_size,
                'crc32':f'{info.CRC:08x}','directory':info.is_dir()})
    names={x['path'] for x in rows};prefix=root+'/'
    required={'manifest':prefix+'manifest.safe',
        'measurement_vv_iw3':prefix+'measurement/s1a-iw3-slc-vv-20211028t230637-20211028t230702-040326-04c765-006.tiff',
        'annotation_vv_iw3':prefix+'annotation/s1a-iw3-slc-vv-20211028t230637-20211028t230702-040326-04c765-006.xml',
        'calibration_vv_iw3':prefix+'annotation/calibration/calibration-s1a-iw3-slc-vv-20211028t230637-20211028t230702-040326-04c765-006.xml',
        'noise_vv_iw3':prefix+'annotation/calibration/noise-s1a-iw3-slc-vv-20211028t230637-20211028t230702-040326-04c765-006.xml'}
    missing={k:v for k,v in required.items() if v not in names}
    if missing:raise ValueError('SAFE required-member mismatch: '+repr(missing))
    return rows,required


def extract(archive,destination,rows):
    destination=Path(destination).resolve();destination.mkdir(parents=True,exist_ok=True)
    total=sum(x['bytes'] for x in rows if not x['directory']);free=shutil.disk_usage(destination).free
    if free<total+8*1024**3:raise RuntimeError('Insufficient extraction space including 8 GiB guard')
    with zipfile.ZipFile(archive) as z:
        for row in rows:
            target=(destination/PurePosixPath(row['path'])).resolve()
            if not target.is_relative_to(destination):raise ValueError('Extraction target escaped destination')
            if row['directory']:target.mkdir(parents=True,exist_ok=True);continue
            target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists():
                if target.stat().st_size!=row['bytes']:raise RuntimeError('Existing extracted member has wrong size: '+str(target))
                continue
            partial=target.with_suffix(target.suffix+'.part')
            if partial.exists() and partial.stat().st_size>row['bytes']:raise RuntimeError('Oversized extraction partial: '+str(partial))
            # Zip streams are not safely seek-resumable: restart this member only,
            # preserving all already verified members and the source archive.
            with z.open(row['path']) as source,partial.open('wb') as output:
                shutil.copyfileobj(source,output,16*1024*1024)
            if partial.stat().st_size!=row['bytes']:raise RuntimeError('Extracted member length mismatch')
            partial.replace(target)
    return total


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--inventory-only',action='store_true');a=p.parse_args(argv)
    if Path.cwd().resolve()!=ROOT:p.error('Run from repository root')
    config=json.loads((BASE/'CONFIG.json').read_text());archive=ROOT/config['download_directory']/config['archive_name']
    if not archive.is_file() or archive.stat().st_size!=config['catalogue_bytes']:raise RuntimeError('Verified archive unavailable or wrong size')
    rows,required=validate_members(archive,config['product_name'])
    extracted_bytes=None
    if not a.inventory_only:extracted_bytes=extract(archive,ROOT/config['extraction_directory'],rows)
    audit=json.loads((BASE/'DOWNLOAD_AUDIT.json').read_text())
    save_json(BASE/'SAFE_INVENTORY.json',{'product_uuid':config['product_uuid'],'product_name':config['product_name'],
        'archive':archive.relative_to(ROOT).as_posix(),'archive_bytes':archive.stat().st_size,'archive_md5':audit.get('md5'),
        'archive_sha256':audit.get('sha256'),'member_count':len(rows),'uncompressed_file_bytes':sum(x['bytes'] for x in rows if not x['directory']),
        'extracted':not a.inventory_only,'extracted_bytes':extracted_bytes,'required_members':required,'members':rows,
        'validated_utc':datetime.now(timezone.utc).isoformat(),'unsafe_members':[]})
    print('SAFE_MEMBERS',len(rows),'UNCOMPRESSED_BYTES',sum(x['bytes'] for x in rows if not x['directory']))


if __name__=='__main__':raise SystemExit(main())
