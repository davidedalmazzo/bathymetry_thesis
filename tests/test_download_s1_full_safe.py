from __future__ import annotations

import io
import json
import zipfile
import hashlib
from pathlib import Path

import pytest

from download_s1_full_safe import catalogue_identity, download_stream, validate_zip_members, digest


class Audit:
    def __init__(self): self.state={'response_bytes':0,'download_stream_bytes':0};self.events=[]
    def event(self,status,**kw): self.events.append((status,kw))
    def _save(self): pass
    def transaction(self,url,role): self.events.append(('transaction',{'role':role}))


class Response(io.BytesIO):
    status=200
    def __enter__(self): return self
    def __exit__(self,*_): self.close()


class Opener:
    def __init__(self,body): self.body=body
    def open(self,*_,**__): return Response(self.body)


def test_catalogue_identity_rejects_wrong_content_length():
    item={'Id':'u','Name':'n.SAFE','ContentLength':11,
          'Checksum':[{'Algorithm':'MD5','Value':'a'*32}]}
    with pytest.raises(RuntimeError,match='differs'):
        catalogue_identity(Opener(json.dumps(item).encode()),Audit(),'u','n.SAFE',12,'a'*32)


def test_nonzip_body_rejected_without_promotion(monkeypatch,tmp_path):
    body=b'<html>error</html>'
    def open_stream(*_): return Response(body),'https://download.dataspace.copernicus.eu/'
    monkeypatch.setattr('download_s1_full_safe._open_stream',open_stream)
    class Token:
        def get(self,force_refresh=False): return 'opaque'
    part=tmp_path/'x.zip.part'
    with pytest.raises(RuntimeError,match='Non-ZIP'):
        download_stream('https://download.dataspace.copernicus.eu/',part,len(body),Audit(),Token(),attempts=1)
    assert not part.exists() and (tmp_path/'x.zip.part.attempt1.incomplete').exists()


def test_range_501_forces_fresh_stream_without_concatenation(monkeypatch,tmp_path):
    valid=b'PK\x03\x04' + b'fresh-data'
    calls=[]
    def open_stream(audit,url,token,start,total,timeout):
        calls.append(start)
        if len(calls)==1: raise RuntimeError('HTTP 501 Range unsupported')
        return Response(valid),'https://download.dataspace.copernicus.eu/'
    monkeypatch.setattr('download_s1_full_safe._open_stream',open_stream)
    class Token:
        def get(self,force_refresh=False): return 'opaque'
    part=tmp_path/'x.zip.part';part.write_bytes(b'PK\x03\x04old')
    result=download_stream('https://download.dataspace.copernicus.eu/',part,len(valid),Audit(),Token(),attempts=2)
    assert result==2 and calls==[0,0] and part.read_bytes()==valid
    assert (tmp_path/'x.zip.part.prior_incomplete').read_bytes()==b'PK\x03\x04old'


def test_md5_matches_exact_file_bytes(tmp_path):
    path=tmp_path/'x';path.write_bytes(b'contents')
    assert digest(path)['md5']==hashlib.md5(b'contents').hexdigest()


def test_zip_path_traversal_rejected(tmp_path):
    archive=tmp_path/'a.zip'
    with zipfile.ZipFile(archive,'w') as z:
        z.writestr('n.SAFE/manifest.safe','ok')
        z.writestr('n.SAFE/../outside','bad')
    with pytest.raises(ValueError,match='Unsafe'):
        validate_zip_members(archive,'n.SAFE')
