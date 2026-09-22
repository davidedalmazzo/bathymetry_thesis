import io,json,math,urllib.parse
from pathlib import Path
import pytest
from shapely.geometry import Polygon,mapping,shape
from s1_iw_annotation import parse_annotation,roi_support,local_geometry,transform_k,axial_difference,validate_xml_payload,validate_manifest,burst_support_geojson
from run_block36_s1_iw_preflight import _validate_annotation_identity
from cdse_credentials import load_token,load_settings,status,TokenProvider,CredentialError
from frf_client.transport import Transport,FetchError


def annotation_xml(first0='1 1',last0='8 8'):
    geo=''.join(f'''<geolocationGridPoint><azimuthTime>2021-10-28T23:06:{36+line:02d}Z</azimuthTime><slantRangeTime>0.005</slantRangeTime><line>{line}</line><pixel>{pix}</pixel><latitude>{36+line*.001}</latitude><longitude>{-75+pix*.001}</longitude><height>0</height><incidenceAngle>{30+pix*.1}</incidenceAngle><elevationAngle>60</elevationAngle></geolocationGridPoint>''' for line in (0,2,4) for pix in (0,5,10))
    bursts=f'''<burst><azimuthTime>2021-10-28T23:06:36Z</azimuthTime><sensingTime>2021-10-28T23:06:36Z</sensingTime><byteOffset>0</byteOffset><firstValidSample>{first0}</firstValidSample><lastValidSample>{last0}</lastValidSample></burst><burst><azimuthTime>2021-10-28T23:06:38Z</azimuthTime><sensingTime>2021-10-28T23:06:38Z</sensingTime><byteOffset>100</byteOffset><firstValidSample>1 1</firstValidSample><lastValidSample>8 8</lastValidSample></burst>'''
    return f'''<?xml version="1.0"?><product><adsHeader><missionId>S1A</missionId><productType>SLC</productType><polarisation>VV</polarisation><mode>IW</mode><swath>IW2</swath><startTime>2021-10-28T23:06:36Z</startTime><stopTime>2021-10-28T23:06:40Z</stopTime><absoluteOrbitNumber>40326</absoluteOrbitNumber><missionDataTakeId>04C765</missionDataTakeId></adsHeader><imageAnnotation><imageInformation><rangePixelSpacing>2</rangePixelSpacing><azimuthPixelSpacing>4</azimuthPixelSpacing><azimuthTimeInterval>1</azimuthTimeInterval><numberOfSamples>10</numberOfSamples><numberOfLines>4</numberOfLines><slantRangeTime>0.005</slantRangeTime></imageInformation></imageAnnotation><swathTiming><linesPerBurst>2</linesPerBurst><samplesPerBurst>10</samplesPerBurst><burstList count="2">{bursts}</burstList></swathTiming><geolocationGrid><geolocationGridPointList>{geo}</geolocationGridPointList></geolocationGrid></product>'''.encode()


def geo_roi(sample0,sample1,line0,line1):
    return mapping(Polygon([(-75+sample0*.001,36+line0*.001),(-75+sample1*.001,36+line0*.001),(-75+sample1*.001,36+line1*.001),(-75+sample0*.001,36+line1*.001)]))


def test_annotation_parser_identity_dimensions_and_times():
    a=parse_annotation(annotation_xml(),expected_swath='IW2')
    assert a['axis_order']==['azimuth_line','slant_range_sample']
    assert (a['number_of_lines'],a['number_of_samples'])==(4,10)
    assert a['bursts'][0]['valid_line_count']==2 and a['bursts'][1]['line_start']==2
    assert a['start_time'].endswith('+00:00') and len(a['geolocation_grid'])==9
    with pytest.raises(ValueError,match='Subswath'):parse_annotation(annotation_xml(),expected_swath='IW3')


def test_safe_naive_timestamp_is_interpreted_as_declared_utc():
    raw=annotation_xml().replace(b'Z</',b'</')
    a=parse_annotation(raw,expected_swath='IW2')
    assert a['start_time'].endswith('+00:00') and a['bursts'][0]['azimuth_time'].endswith('+00:00')


def test_invalid_samples_excluded_and_partial_burst():
    a=parse_annotation(annotation_xml('-1 1','-1 8'))
    assert a['bursts'][0]['valid_line_count']==1
    r=roi_support(a,geo_roi(2,4,.1,1.9))
    assert 0<r['valid_fraction']<1 and not r['fully_valid']


def test_single_burst_and_join_are_distinct():
    a=parse_annotation(annotation_xml())
    single=roi_support(a,geo_roi(2,4,.1,1.4));seam=roi_support(a,geo_roi(2,4,1.4,2.4))
    assert single['fully_valid'] and single['single_valid_burst'] and not single['crosses_burst_join']
    assert seam['fully_valid'] and seam['crosses_burst_join'] and not seam['single_valid_burst']
    assert 'do not duplicate overlap' in seam['join_treatment']
    projected=shape(burst_support_geojson(a,0));assert projected.is_valid and not projected.is_empty


def test_local_geometry_and_known_k_transform():
    a=parse_annotation(annotation_xml());g=local_geometry(a,geo_roi(2,4,.2,1.4),delta=.5)
    assert g['range_sample_bearing_deg']==pytest.approx(90,abs=.2)
    assert g['azimuth_line_bearing_deg']==pytest.approx(0,abs=.2)
    result=transform_k(2,8,[[2,0],[0,4]])
    assert result['k_east_rad_m']==pytest.approx(1) and result['k_north_rad_m']==pytest.approx(2)
    assert result['bearing_toward_deg']==pytest.approx(math.degrees(math.atan2(1,2)))


@pytest.mark.parametrize('a,b,d',[(10,190,0),(80,90,10),(350,10,20)])
def test_axial_direction_convention(a,b,d):assert axial_difference(a,b)==pytest.approx(d)


def test_reject_unexpected_oversized_malformed_content():
    raw=annotation_xml()
    with pytest.raises(ValueError,match='oversized'):parse_annotation(raw,max_bytes=10)
    with pytest.raises(ValueError,match='Polarisation'):parse_annotation(raw,expected_polarisation='VH')
    with pytest.raises(ValueError,match='length'):validate_xml_payload(raw,'x.xml',len(raw)+1)
    with pytest.raises(ValueError,match='Only'):validate_xml_payload(raw,'measurement.tiff',len(raw))
    with pytest.raises(ValueError,match='non-XML'):validate_xml_payload(b'not xml','x.xml',7)


def test_valid_vector_length_and_interval_rejected():
    with pytest.raises(ValueError,match='length'):parse_annotation(annotation_xml('1','8'))
    with pytest.raises(ValueError,match='Invalid'):parse_annotation(annotation_xml('8 8','1 8'))


def test_credentials_environment_file_and_path_protection(tmp_path):
    token,source=load_token(environ={'CDSE_ACCESS_TOKEN':'abc.def.ghi'});assert source=='environment_or_local_file' and token.startswith('abc')
    local=Path.cwd()/'_tmp'/'block36_test_token.env';local.parent.mkdir(exist_ok=True);local.write_text('CDSE_ACCESS_TOKEN=secret-token')
    try:assert load_token(local,environ={})==('secret-token','environment_or_local_file')
    finally:local.unlink()
    missing=Path.cwd()/'_tmp'/'does_not_exist.env';assert not status(missing,environ={})['configured']
    with pytest.raises(CredentialError,match='inside'):load_token(Path('C:/outside-block36.env'),environ={})
    with pytest.raises(CredentialError):load_token(environ={'CDSE_ACCESS_TOKEN':'bad token'})


def test_username_password_env_pair_and_precedence(tmp_path):
    local=Path.cwd()/'_tmp'/'block36_test_credentials.env';local.write_text('CDSE_USERNAME=local-user\nCDSE_PASSWORD="local=p&ss"\n')
    try:
        settings=load_settings(local,environ={});assert settings['source']=='username_password' and settings['password']=='local=p&ss'
        overridden=load_settings(local,environ={'CDSE_ACCESS_TOKEN':'direct.token'});assert overridden['source']=='access_token'
    finally:local.unlink()
    with pytest.raises(CredentialError,match='both'):
        load_settings(local,environ={'CDSE_USERNAME':'only-user'})


class Response(io.BytesIO):
    status=200
    def __init__(self,body=b'<x/>'):super().__init__(body);self.headers={'Content-Length':str(len(body))}
class Opener:
    def __init__(self):self.authorization=None
    def open(self,request,timeout=None):self.authorization=request.get_header('Authorization');return Response()


class RedirectResponse(Response):
    status=302
    def __init__(self):
        super().__init__(b'');self.headers={'Content-Length':'0','Location':'https://second.test/meta.xml'}


class RedirectOpener:
    def open(self,request,timeout=None):return RedirectResponse()


class AuthOpener:
    def __init__(self,responses):self.responses=list(responses);self.forms=[]
    def open(self,request,timeout=None):
        self.forms.append(urllib.parse.parse_qs(request.data.decode()))
        code,body=self.responses.pop(0);response=Response(json.dumps(body).encode());response.status=code;return response


def test_bearer_secret_not_logged_and_transaction_counted(tmp_path):
    opener=Opener();t=Transport(tmp_path/'cache',tranche_directory=tmp_path/'net',tranche_name='auth',new_tranche=True,
        hosts=('example.test',),max_requests=2,max_bytes=100,max_response=50,retries=0,rate_seconds=0,opener=opener)
    secret='very-secret-token';assert t.get('https://example.test/meta.xml',authorization_bearer=secret)==b'<x/>'
    assert opener.authorization=='Bearer '+secret and t.state['transactions']==1 and t.state['bytes']==4
    persisted=''.join(p.read_text(errors='ignore') for p in (tmp_path/'net').glob('*') if p.is_file())
    persisted+=''.join(p.read_text(errors='ignore') for p in (tmp_path/'cache').glob('*.json'))
    assert secret not in persisted and 'Authorization' not in persisted
    with pytest.raises(FetchError,match='invalid_bearer'):t.get('https://example.test/new',authorization_bearer='bad token')


def test_bearer_is_not_forwarded_across_allowed_hosts(tmp_path):
    t=Transport(tmp_path/'cache',tranche_directory=tmp_path/'net',tranche_name='redirect',new_tranche=True,
        hosts=('example.test','second.test'),max_requests=2,max_bytes=100,max_response=50,retries=0,rate_seconds=0,opener=RedirectOpener())
    with pytest.raises(FetchError,match='authenticated_cross_origin_redirect'):
        t.get('https://example.test/meta.xml',authorization_bearer='secret')
    assert t.state['transactions']==1


def test_password_login_mfa_refresh_and_secrets_never_persisted(tmp_path):
    responses=[(400,{'error':'invalid_grant'}),(200,{'access_token':'first.token','refresh_token':'refresh-secret','expires_in':1}),
               (200,{'access_token':'second.token','refresh_token':'refresh-2','expires_in':60})]
    opener=AuthOpener(responses);t=Transport(tmp_path/'cache',tranche_directory=tmp_path/'net',tranche_name='oauth',new_tranche=True,
        hosts=('identity.dataspace.copernicus.eu',),max_requests=4,max_bytes=10000,max_response=5000,retries=0,rate_seconds=0,opener=opener)
    now=[100.];provider=TokenProvider(t,environ={'CDSE_USERNAME':'user@example.test','CDSE_PASSWORD':'p&=word'},
        max_requests=3,expiry_skew_seconds=0,clock=lambda:now[0],prompt=lambda:'123456')
    assert provider.get()=='first.token';now[0]=102.;assert provider.get()=='second.token'
    assert [x['grant_type'][0] for x in opener.forms]==['password','password','refresh_token']
    assert opener.forms[1]['totp']==['123456'] and t.state['transactions']==3
    with pytest.raises(CredentialError,match='limit'):provider.get(force_refresh=True)
    assert t.state['transactions']==3
    persisted=''.join(p.read_text(errors='ignore') for p in (tmp_path/'net').glob('*') if p.is_file())
    for secret in ('p&=word','first.token','second.token','refresh-secret','123456','user@example.test'):
        assert secret not in persisted


def test_manifest_requires_exact_annotation_references():
    raw=b'<xfdu:XFDU xmlns:xfdu="urn:test"><dataObject><byteStream><fileLocation href="./annotation/a.xml"/></byteStream></dataObject></xfdu:XFDU>'
    assert validate_manifest(raw,['a.xml'])['expected_annotations_present']
    with pytest.raises(ValueError,match='does not reference'):validate_manifest(raw,['b.xml'])


def test_block36_annotation_identity_is_bound_to_selected_product():
    annotation=parse_annotation(annotation_xml(),expected_swath='IW2')
    assert _validate_annotation_identity(annotation,'IW2')
    annotation['absolute_orbit_number']=40327
    with pytest.raises(ValueError,match='orbit'):
        _validate_annotation_identity(annotation,'IW2')
