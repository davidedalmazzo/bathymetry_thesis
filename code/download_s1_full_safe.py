"""Scene-generic CDSE SAFE archive download and integrity-only verification.

The whole-product endpoint may reject Range.  This tool never concatenates
streams: each attempt starts at byte zero, retaining interrupted files only as
diagnostics.  Archive/SAFE paths must be beneath the repository's ignored data
directory.  No scene-specific JSON configuration is required.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import time
import urllib.error
import urllib.request
import zipfile
from xml.etree import ElementTree as ET

from cdse_credentials import TokenProvider
from download_block37_s1 import DownloadAudit, _open_stream
from repository_paths import ROOT
from frf_client.transport import save_json

CATALOGUE = 'https://catalogue.dataspace.copernicus.eu/odata/v1/Products({uuid})'
DOWNLOAD = 'https://download.dataspace.copernicus.eu/odata/v1/Products({uuid})/$value'


def catalogue_identity(opener, audit, uuid, name, size, md5, blake3=None):
    url = CATALOGUE.format(uuid=uuid)
    audit.transaction(url, 'public_catalogue')
    with opener.open(urllib.request.Request(url, headers={'Accept':'application/json'}),timeout=45) as response:
        body=response.read(128*1024+1)
        audit.state['response_bytes']+=len(body);audit._save()
        if len(body)>128*1024 or response.status!=200:raise RuntimeError('Invalid catalogue response')
    item=json.loads(body)
    checks={c['Algorithm'].upper():c['Value'].lower() for c in item.get('Checksum',[])}
    if (item.get('Id')!=uuid or item.get('Name')!=name or item.get('ContentLength')!=size
            or checks.get('MD5')!=md5.lower() or (blake3 and checks.get('BLAKE3')!=blake3.lower())):
        raise RuntimeError('Frozen product identity/length/checksum differs from public OData catalogue')
    audit.event('catalogue_verified',uuid=uuid,name=name,bytes=size,md5=checks['MD5'],blake3=checks.get('BLAKE3'))
    return checks


def validate_zip_members(archive, safe_name):
    rows=[]; names=set(); prefix=safe_name+'/'
    with zipfile.ZipFile(archive) as z:
        for item in z.infolist():
            name=item.filename; path=PurePosixPath(name)
            if (path.is_absolute() or '\\' in name or '..' in path.parts or not name.startswith(prefix)
                    or name in names or stat.S_ISLNK((item.external_attr>>16)&0xffff)):
                raise ValueError('Unsafe or duplicate SAFE member')
            names.add(name)
            rows.append({'path':name,'bytes':item.file_size,'compressed_bytes':item.compress_size,
                         'crc32':f'{item.CRC:08x}','directory':item.is_dir()})
    if prefix+'manifest.safe' not in names:raise ValueError('SAFE archive lacks manifest.safe')
    return rows


def manifest_objects(archive, safe_name, rows):
    with zipfile.ZipFile(archive) as z:
        root=ET.fromstring(z.read(safe_name+'/manifest.safe'))
    objects=[]
    names={r['path']:r for r in rows}
    for node in root.iter():
        if node.tag.rsplit('}',1)[-1]!='dataObject':continue
        loc=next((x for x in node.iter() if x.tag.rsplit('}',1)[-1]=='fileLocation'),None)
        bs=next((x for x in node.iter() if x.tag.rsplit('}',1)[-1]=='byteStream'),None)
        cs=next((x for x in node.iter() if x.tag.rsplit('}',1)[-1]=='checksum'),None)
        if loc is None or bs is None:raise ValueError('Manifest dataObject missing location or size')
        rel=loc.get('href','').removeprefix('./')
        archive_path=safe_name+'/'+rel
        if archive_path not in names or names[archive_path]['bytes']!=int(bs.get('size')):
            raise ValueError('Manifest/archive member or size mismatch: '+rel)
        objects.append({'relative_path':rel,'bytes':int(bs.get('size')),
                        'checksum_algorithm':cs.get('checksumName') if cs is not None else None,
                        'checksum':cs.text.strip().lower() if cs is not None and cs.text else None})
    return objects


def digest(path, algorithms=('md5','sha256')):
    hashes={a:hashlib.new(a) for a in algorithms}
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(8*1024*1024),b''):
            for h in hashes.values():h.update(chunk)
    return {k:h.hexdigest() for k,h in hashes.items()}


def download_stream(url, part, size, audit, provider, attempts=3, chunk_bytes=8*1024*1024):
    if part.exists():
        diag=part.with_name(part.name+'.prior_incomplete')
        if diag.exists():raise RuntimeError('Prior diagnostic partial already exists; no overwrite')
        part.rename(diag);audit.event('prior_partial_preserved',bytes=diag.stat().st_size,path=diag.name)
    for number in range(1,attempts+1):
        response=None;received=0
        try:
            # Whole-product Range=501: force a fresh 200 response at offset zero.
            if number>1:provider.get(force_refresh=True)
            response,_=_open_stream(audit,url,provider,0,size,120)
            with part.open('wb') as output:
                while True:
                    data=response.read(chunk_bytes)
                    if not data:break
                    if received==0 and not data.startswith(b'PK\x03\x04'):
                        raise RuntimeError('Non-ZIP archive body refused')
                    output.write(data);received+=len(data)
                    audit.state['response_bytes']+=len(data)
                    audit.state['download_stream_bytes']+=len(data)
                    if received>size:raise RuntimeError('Archive response exceeded catalogue size')
                    if received//(256*1024*1024)>(received-len(data))//(256*1024*1024):
                        audit.event('stream_progress',attempt=number,bytes=received)
            if received!=size:raise RuntimeError('Archive stream ended before catalogue length')
            audit.event('stream_complete',attempt=number,bytes=received)
            return number
        except Exception as exc:
            audit.event('stream_interrupted',attempt=number,bytes=received,error=type(exc).__name__)
            if part.exists():
                diag=part.with_name(part.name+f'.attempt{number}.incomplete')
                if diag.exists():raise RuntimeError('Diagnostic partial collision; refusing overwrite') from exc
                part.rename(diag)
            if number==attempts:raise
        finally:
            if response is not None:response.close()
    raise RuntimeError('Attempt limit exhausted')


def extract_separate(archive, rows, base, safe_name):
    dest=(base/'full'/safe_name).resolve()
    if not dest.is_relative_to(base.resolve()):raise RuntimeError('Extraction escaped data directory')
    required=sum(r['bytes'] for r in rows if not r['directory'])
    if shutil.disk_usage(base).free<required+2*1024**3:raise RuntimeError('Insufficient extraction space')
    dest.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        for item in rows:
            rel=PurePosixPath(item['path']).relative_to(safe_name)
            target=(dest/rel).resolve()
            if not target.is_relative_to(dest):raise ValueError('Unsafe extraction target')
            if item['directory']:target.mkdir(parents=True,exist_ok=True);continue
            target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists():
                if target.stat().st_size!=item['bytes']:raise RuntimeError('Existing full SAFE member differs')
                continue
            temp=target.with_name(target.name+'.part')
            with z.open(item['path']) as src,temp.open('wb') as dst:
                shutil.copyfileobj(src,dst,8*1024*1024)
            if temp.stat().st_size!=item['bytes']:raise RuntimeError('Extracted member length differs')
            temp.rename(target)
    return dest


def crosscheck_vv(full_safe, partial_safe, objects):
    rows=[]
    for obj in objects:
        rel=obj['relative_path']
        if '-vv-' not in rel.lower():continue
        old=partial_safe/rel;new=full_safe/rel
        if not old.exists():continue
        a=digest(old,('md5',))['md5'];b=digest(new,('md5',))['md5']
        rows.append({'path':rel,'nodes_md5':a,'full_safe_md5':b,'match':a==b,
                     'manifest_md5_match':obj['checksum_algorithm'].upper()=='MD5' and b==obj['checksum']})
    return rows


def one_raster_check(full_safe):
    import rasterio
    out=[]
    for pol in ('vv','vh'):
        files=list(full_safe.glob(f'measurement/*-{pol}-*.tiff'))
        if len(files)!=1:raise RuntimeError('Expected exactly one measurement '+pol)
        annotation=list(full_safe.glob(f'annotation/*-{pol}-*.xml'))
        if len(annotation)!=1:raise RuntimeError('Expected exactly one annotation '+pol)
        root=ET.parse(annotation[0]).getroot()
        def value(name):
            return next(int(x.text) for x in root.iter() if x.tag.rsplit('}',1)[-1]==name)
        with rasterio.open(files[0]) as ds:
            shape=[ds.height,ds.width]
            if shape!=[value('numberOfLines'),value('numberOfSamples')]:
                raise RuntimeError('TIFF/annotation dimensions mismatch: '+pol)
            out.append({'polarisation':pol,'measurement':str(files[0].relative_to(full_safe)).replace('\\','/'),
                        'dimensions_lines_samples':shape,'bands':ds.count,'dtype':ds.dtypes[0],
                        'annotation_dimensions_match':True})
    return out


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('uuid');p.add_argument('--out',default='data_s1')
    p.add_argument('--name',required=True);p.add_argument('--size',required=True,type=int)
    p.add_argument('--md5',required=True);p.add_argument('--blake3')
    a=p.parse_args(argv)
    base=(ROOT/a.out).resolve()
    if not base.is_relative_to(ROOT) or base==ROOT:raise RuntimeError('Destination must be inside repository')
    base.mkdir(parents=True,exist_ok=True)
    if not a.name.endswith('.SAFE') or '/' in a.name or '\\' in a.name:raise ValueError('Unsafe SAFE product name')
    zip_path=base/(a.name.removesuffix('.SAFE')+'.zip')
    audit=DownloadAudit(base/(zip_path.name+'.DOWNLOAD_AUDIT.json'))
    checks=catalogue_identity(audit.opener,audit,a.uuid,a.name,a.size,a.md5,a.blake3)
    if shutil.disk_usage(base).free<2*a.size+2*1024**3:
        raise RuntimeError('Insufficient free space for archive, extraction and 2 GiB margin')
    if zip_path.exists():
        if zip_path.stat().st_size!=a.size or digest(zip_path,('md5',))['md5']!=a.md5.lower():
            raise RuntimeError('Existing archive is not the frozen product')
        attempt=0
    else:
        provider=TokenProvider(audit,ROOT/'.env',max_requests=8)
        part=zip_path.with_name(zip_path.name+'.part')
        attempt=download_stream(DOWNLOAD.format(uuid=a.uuid),part,a.size,audit,provider)
        if not zipfile.is_zipfile(part):raise RuntimeError('Downloaded body is not ZIP')
        h=digest(part)
        if h['md5']!=a.md5.lower():raise RuntimeError('Downloaded archive MD5 mismatch; .part retained')
        part.rename(zip_path)
    h=digest(zip_path)
    if h['md5']!=a.md5.lower():raise RuntimeError('Archive MD5 mismatch')
    if a.blake3:
        try:
            import blake3
        except ImportError: pass
        else:
            hasher=blake3.blake3()
            with zip_path.open('rb') as stream:
                for data in iter(lambda:stream.read(8*1024*1024),b''):hasher.update(data)
            h['blake3']=hasher.hexdigest()
            if h['blake3']!=checks['BLAKE3']:raise RuntimeError('Archive BLAKE3 mismatch')
    rows=validate_zip_members(zip_path,a.name)
    objects=manifest_objects(zip_path,a.name,rows)
    full=extract_separate(zip_path,rows,base,a.name)
    cross=crosscheck_vv(full,base/a.name,objects)
    if not cross or any(not r['match'] or not r['manifest_md5_match'] for r in cross):
        raise RuntimeError('VV Nodes/full SAFE cross-check failed')
    rasters=one_raster_check(full)
    inventory={'uuid':a.uuid,'name':a.name,'archive_bytes':zip_path.stat().st_size,
               'archive_checksum':h,'member_count':len(rows),'manifest_data_object_count':len(objects),
               'members':rows,'data_objects':objects,'vv_crosscheck':cross,'raster_open_check':rasters,
               'full_safe_relative':full.relative_to(ROOT).as_posix()}
    save_json(base/(zip_path.name+'.SAFE_INVENTORY.json'),inventory)
    audit.state.update(complete=True,attempts_this_run=attempt,archive=zip_path.relative_to(ROOT).as_posix(),
                       archive_bytes=a.size,archive_checksums=h,member_count=len(rows),vv_crosscheck_count=len(cross),
                       completed_utc=datetime.now(timezone.utc).isoformat())
    audit._save()
    print(json.dumps({'complete':True,'attempts':attempt,'bytes':a.size,'checksums':h,
                      'members':len(rows),'data_objects':len(objects),'vv_crosscheck':len(cross),
                      'raster_check':rasters},indent=2))


if __name__=='__main__':main()
