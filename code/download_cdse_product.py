"""Prepared resumable CDSE product downloader; never invoked by Block36."""
import argparse,hashlib,os,shutil,urllib.request,urllib.error
from urllib.parse import urljoin,urlsplit
from pathlib import Path
from cdse_credentials import load_token
from repository_paths import ROOT

UUID='c49a9c1f-9b00-5676-ab05-683975d898a2';SIZE=7799368890
NAME='S1A_IW_SLC__1SDV_20211028T230636_20211028T230703_040326_04C765_B6FA.zip'
MD5='d1886a92315be184489eea0e072c0578'

class SameHostRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        target=urljoin(req.full_url,newurl);a,b=urlsplit(req.full_url),urlsplit(target)
        if b.scheme!='https' or b.hostname!=a.hostname:raise RuntimeError('Cross-origin redirect refused; bearer not forwarded')
        return urllib.request.Request(target,headers=dict(req.header_items()),method=req.get_method())

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--destination',required=True);p.add_argument('--credential-file')
    a=p.parse_args(argv);dest=Path(a.destination)
    if not dest.is_absolute():dest=ROOT/dest
    dest=dest.resolve()
    if not dest.is_relative_to(ROOT):p.error('Destination must remain in repository root')
    dest.mkdir(parents=True,exist_ok=True)
    target=dest/NAME;partial=target.with_suffix(target.suffix+'.part')
    existing=partial.stat().st_size if partial.exists() else 0
    if existing>SIZE:raise RuntimeError('Partial file exceeds catalogue size')
    if shutil.disk_usage(dest).free < (SIZE-existing)+1024**3:raise RuntimeError('Insufficient free space: require remaining bytes plus 1 GiB guard')
    token,_=load_token(a.credential_file)
    if token is None:raise RuntimeError('Configure CDSE_ACCESS_TOKEN or excluded credential file')
    url=f'https://download.dataspace.copernicus.eu/odata/v1/Products({UUID})/$value'
    headers={'Authorization':'Bearer '+token,'User-Agent':'thesis-cdse-download/1.0'}
    if existing:headers['Range']=f'bytes={existing}-'
    request=urllib.request.Request(url,headers=headers)
    opener=urllib.request.build_opener(SameHostRedirect())
    with opener.open(request,timeout=60) as response:
        if existing and response.status!=206:raise RuntimeError('Server ignored resume Range; partial preserved, body not consumed')
        if not existing and response.status!=200:raise RuntimeError('Unexpected download response')
        if existing:
            content_range=response.headers.get('Content-Range','')
            if not content_range.startswith(f'bytes {existing}-'):raise RuntimeError('Resume Content-Range mismatch; body not consumed')
        mode='ab' if existing else 'wb'
        with partial.open(mode) as out:
            while True:
                chunk=response.read(1024*1024)
                if not chunk:break
                out.write(chunk)
    if partial.stat().st_size!=SIZE:raise RuntimeError('Download incomplete; .part preserved for resume')
    h=hashlib.md5()
    with partial.open('rb') as f:
        for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
    if h.hexdigest().lower()!=MD5:raise RuntimeError('Vendor MD5 mismatch; .part preserved')
    partial.replace(target);print('Verified product saved:',target)

if __name__=='__main__':raise SystemExit(main())
