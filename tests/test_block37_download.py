import hashlib,io,json,zipfile
from pathlib import Path
import pytest
import download_block37_s1 as module
from prepare_block37_safe import validate_members


def zip_bytes():
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w') as z:z.writestr('PRODUCT.SAFE/manifest.safe','<XFDU/>')
    return out.getvalue()


class Audit:
    def __init__(self):self.state={'response_bytes':0,'download_stream_bytes':0};self.events=[]
    def event(self,*args,**kwargs):self.events.append((args,kwargs))
    def _save(self):pass


class Response(io.BytesIO):
    def __init__(self,data):super().__init__(data);self.closed_flag=False
    def close(self):self.closed_flag=True;super().close()


class Interrupted(Response):
    def __init__(self,data):super().__init__(data);self.calls=0
    def read(self,n=-1):
        self.calls+=1
        if self.calls==1:return super().read(10)
        raise OSError('synthetic interruption')


def config(raw):
    return {'archive_name':'PRODUCT.zip','catalogue_bytes':len(raw),'vendor_md5':hashlib.md5(raw).hexdigest(),
        'download_directory':'data','minimum_free_bytes_before_download':1,'product_uuid':'uuid',
        'download_stream_attempts':3,'download_timeout_seconds':1,'download_chunk_bytes':64}


def test_interrupted_download_resumes_without_concatenation(monkeypatch,tmp_path):
    raw=zip_bytes();audit=Audit();starts=[]
    monkeypatch.setattr(module,'ROOT',tmp_path);monkeypatch.setattr(module,'TokenProvider',lambda *a,**k:object())
    def opening(audit,url,provider,start,total,timeout):
        starts.append(start)
        return (Interrupted(raw) if start==0 else Response(raw[start:])),url
    monkeypatch.setattr(module,'_open_stream',opening)
    target=module.download(config(raw),audit)
    assert target.read_bytes()==raw and starts==[0,10]
    assert not target.with_suffix('.zip.part').exists()


def test_non_zip_response_is_rejected_and_part_preserved(monkeypatch,tmp_path):
    raw=b'not-a-sar-product';audit=Audit();monkeypatch.setattr(module,'ROOT',tmp_path)
    monkeypatch.setattr(module,'TokenProvider',lambda *a,**k:object())
    monkeypatch.setattr(module,'_open_stream',lambda *args:(Response(raw),args[1]))
    with pytest.raises(RuntimeError,match='ZIP'):module.download(config(raw),audit)
    assert (tmp_path/'data/PRODUCT.zip.part').read_bytes()==raw


def test_config_identity_is_frozen():
    cfg=json.loads((Path(module.__file__).parents[1]/'duck_frf/Block37_s1_iw_spatial_trial/CONFIG.json').read_text())
    assert cfg['product_uuid']=='c49a9c1f-9b00-5676-ab05-683975d898a2'
    assert cfg['catalogue_bytes']==7799368890 and cfg['subswath']=='IW3' and cfg['burst_index']==0


def test_safe_inventory_identity_and_traversal_rejection(tmp_path):
    good=tmp_path/'good.zip';root='PRODUCT.SAFE'
    with zipfile.ZipFile(good,'w') as z:
        for name in ('manifest.safe','measurement/s1a-iw3-slc-vv-20211028t230637-20211028t230702-040326-04c765-006.tiff',
                     'annotation/s1a-iw3-slc-vv-20211028t230637-20211028t230702-040326-04c765-006.xml',
                     'annotation/calibration/calibration-s1a-iw3-slc-vv-20211028t230637-20211028t230702-040326-04c765-006.xml',
                     'annotation/calibration/noise-s1a-iw3-slc-vv-20211028t230637-20211028t230702-040326-04c765-006.xml'):
            z.writestr(root+'/'+name,b'x')
    rows,required=validate_members(good,root);assert len(rows)==5 and required['manifest'].endswith('manifest.safe')
    bad=tmp_path/'bad.zip'
    with zipfile.ZipFile(bad,'w') as z:z.writestr('../escape','x')
    with pytest.raises(ValueError,match='Unsafe'):validate_members(bad,root)
