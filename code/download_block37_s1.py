"""Resumable, authenticated and audited Block37 Sentinel-1 archive download."""
from __future__ import annotations
import argparse,hashlib,json,os,shutil,ssl,time,urllib.error,urllib.request,zipfile
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlencode,urljoin,urlsplit
from repository_paths import ROOT
from frf_client.transport import FetchError,NoRedirect,safe_url,save_json
from cdse_credentials import TokenProvider

BASE=ROOT/'duck_frf/Block37_s1_iw_spatial_trial'
TOKEN_HOST='identity.dataspace.copernicus.eu'


class DownloadAudit:
    """One persistent ledger for authentication and large-body HTTP attempts."""
    def __init__(self,path,timeout=120):
        self.path=Path(path);self.timeout=timeout;self.opener=urllib.request.build_opener(NoRedirect())
        self.state=json.loads(self.path.read_text()) if self.path.exists() else {
            'created_utc':datetime.now(timezone.utc).isoformat(),'http_transactions':0,'response_bytes':0,
            'download_stream_bytes':0,'events':[],'secrets_logged':False,'complete':False}
        self._save()
    def _save(self):save_json(self.path,self.state)
    def event(self,status,**values):
        self.state['events'].append({'utc':datetime.now(timezone.utc).isoformat(),'status':status,**values});self._save()
    def transaction(self,url,role):
        self.state['http_transactions']+=1;self.event('started',role=role,url=safe_url(url),number=self.state['http_transactions'])
    def post_form_secret(self,url,fields):
        if urlsplit(url).scheme!='https' or urlsplit(url).hostname!=TOKEN_HOST:raise FetchError('unsupported_auth_endpoint')
        body=urlencode(fields).encode();self.transaction(url,'authentication');response=None
        try:
            req=urllib.request.Request(url,data=body,headers={'Content-Type':'application/x-www-form-urlencoded','User-Agent':'thesis-block37/1.0'},method='POST')
            try:response=self.opener.open(req,timeout=self.timeout);code=response.status
            except urllib.error.HTTPError as exc:response=exc;code=exc.code
            if code in (301,302,303,307,308):raise FetchError('authentication_redirect_refused',code)
            limit=1024*1024;raw=response.read(limit+1)
            if len(raw)>limit:raise FetchError('authentication_response_too_large')
            self.state['response_bytes']+=len(raw);self.event('authentication_response',code=code,bytes=len(raw))
            if code!=200:raise FetchError('authentication_failed' if code in (400,401) else 'authentication_http_error',code)
            return raw
        except (urllib.error.URLError,TimeoutError,OSError):
            self.event('authentication_transport_error');raise FetchError('transport_error') from None
        finally:
            if response is not None:response.close()


def _validate_redirect(current,location):
    target=urljoin(current,location);parsed=urlsplit(target)
    if parsed.scheme!='https' or parsed.username or parsed.password:raise RuntimeError('Unsafe download redirect')
    host=(parsed.hostname or '').lower()
    if not (host=='dataspace.copernicus.eu' or host.endswith('.dataspace.copernicus.eu')):
        raise RuntimeError('Redirect left the verified CDSE domain: '+host)
    return target


def _hashes(path):
    md5=hashlib.md5();sha=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(16*1024*1024),b''):md5.update(chunk);sha.update(chunk)
    return md5.hexdigest(),sha.hexdigest()


def _open_stream(audit,url,token,start,total,timeout):
    redirects=0;refreshed=False;access=token.get()
    while True:
        headers={'Authorization':'Bearer '+access,'User-Agent':'thesis-block37/1.0','Accept':'application/zip,application/octet-stream'}
        if start:headers['Range']=f'bytes={start}-'
        audit.transaction(url,'archive_download');response=None
        try:
            try:response=audit.opener.open(urllib.request.Request(url,headers=headers),timeout=timeout);code=response.status
            except urllib.error.HTTPError as exc:response=exc;code=exc.code
            if code in (301,302,303,307,308):
                location=response.headers.get('Location');response.close()
                if not location or redirects>=5:raise RuntimeError('Missing/too many download redirects')
                url=_validate_redirect(url,location);redirects+=1;audit.event('redirect',url=safe_url(url),count=redirects);continue
            if code in (401,403) and not refreshed:
                response.close();access=token.get(force_refresh=True);refreshed=True;audit.event('bearer_refresh_after_auth_failure',code=code);continue
            expected_code=206 if start else 200
            if code!=expected_code:
                response.close()
                if start and code==200:raise RuntimeError('Server ignored Range; partial preserved and body not consumed')
                raise RuntimeError(f'Unexpected archive HTTP status {code}')
            ctype=(response.headers.get('Content-Type') or '').lower()
            if 'json' in ctype or 'html' in ctype or ctype.startswith('text/'):
                response.close();raise RuntimeError('Refused non-archive response Content-Type: '+ctype)
            length=response.headers.get('Content-Length')
            if length is None:response.close();raise RuntimeError('Archive response lacks Content-Length')
            length=int(length);expected=total-start
            if length!=expected:response.close();raise RuntimeError(f'Archive Content-Length mismatch {length} != {expected}')
            if start:
                value=response.headers.get('Content-Range','')
                if value!=f'bytes {start}-{total-1}/{total}':response.close();raise RuntimeError('Archive Content-Range mismatch')
            return response,url
        except Exception:
            if response is not None and not response.closed:response.close()
            raise


def download(config,audit):
    expected_name=config['archive_name'];total=config['catalogue_bytes'];vendor_md5=config['vendor_md5'].lower()
    directory=(ROOT/config['download_directory']).resolve()
    if not directory.is_relative_to(ROOT):raise RuntimeError('Download directory escapes repository')
    directory.mkdir(parents=True,exist_ok=True);target=directory/expected_name;partial=target.with_suffix(target.suffix+'.part')
    if target.exists():
        if target.stat().st_size!=total:raise RuntimeError('Existing final archive has wrong size')
        md5,sha=_hashes(target)
        if md5!=vendor_md5:raise RuntimeError('Existing final archive MD5 mismatch')
        audit.state.update(complete=True,path=target.relative_to(ROOT).as_posix(),bytes=total,md5=md5,sha256=sha);audit._save();return target
    start=partial.stat().st_size if partial.exists() else 0
    if start>total:raise RuntimeError('Partial archive exceeds expected size')
    if start and partial.open('rb').read(4)!=b'PK\x03\x04':raise RuntimeError('Partial file lacks ZIP magic')
    free=shutil.disk_usage(directory).free
    required=max(config['minimum_free_bytes_before_download'],total-start+2*1024**3)
    if free<required:raise RuntimeError(f'Insufficient free space: {free} < {required}')
    provider=TokenProvider(audit,ROOT/'.env',max_requests=3,expiry_skew_seconds=30)
    url=f"https://download.dataspace.copernicus.eu/odata/v1/Products({config['product_uuid']})/$value"
    attempts=0
    while (partial.stat().st_size if partial.exists() else 0) < total:
        start=partial.stat().st_size if partial.exists() else 0;attempts+=1
        if attempts>config['download_stream_attempts']:raise RuntimeError('Download stream attempt limit reached; partial preserved')
        response=None
        try:
            response,final_url=_open_stream(audit,url,provider,start,total,config['download_timeout_seconds'])
            mode='ab' if start else 'wb';next_report=start+512*1024**2
            with partial.open(mode) as output:
                while True:
                    chunk=response.read(config['download_chunk_bytes'])
                    if not chunk:break
                    output.write(chunk);audit.state['response_bytes']+=len(chunk);audit.state['download_stream_bytes']+=len(chunk)
                    current=output.tell()
                    if current>=next_report:
                        audit.state['partial_bytes']=current;audit._save();print(f'progress {current}/{total} bytes',flush=True);next_report=current+512*1024**2
            if partial.stat().st_size<total:
                audit.event('stream_ended_early',partial_bytes=partial.stat().st_size,attempt=attempts);continue
        except (urllib.error.URLError,TimeoutError,OSError) as exc:
            audit.event('stream_interrupted',partial_bytes=partial.stat().st_size if partial.exists() else 0,attempt=attempts,error=type(exc).__name__);continue
        finally:
            if response is not None:response.close()
    if partial.stat().st_size!=total:raise RuntimeError('Archive final size mismatch')
    if partial.open('rb').read(4)!=b'PK\x03\x04' or not zipfile.is_zipfile(partial):raise RuntimeError('Downloaded body is not a valid ZIP archive')
    md5,sha=_hashes(partial)
    if md5!=vendor_md5:raise RuntimeError('Vendor MD5 mismatch; partial preserved')
    partial.replace(target)
    audit.state.update(complete=True,path=target.relative_to(ROOT).as_posix(),bytes=total,md5=md5,sha256=sha,
        completed_utc=datetime.now(timezone.utc).isoformat());audit.event('download_verified',bytes=total,md5=md5,sha256=sha)
    return target


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',default=str(BASE/'CONFIG.json'));a=p.parse_args(argv)
    if Path.cwd().resolve()!=ROOT:p.error('Run from repository root')
    config=json.loads(Path(a.config).read_text());audit=DownloadAudit(BASE/'DOWNLOAD_AUDIT.json',config['download_timeout_seconds'])
    target=download(config,audit);print('VERIFIED_ARCHIVE',target)


if __name__=='__main__':raise SystemExit(main())
