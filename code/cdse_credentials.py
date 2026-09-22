"""Secret-safe CDSE credentials and in-memory OAuth token lifecycle.

Official flow: https://documentation.dataspace.copernicus.eu/APIs/Token.html
"""
from __future__ import annotations
import base64,getpass,json,os,re,time
from pathlib import Path
from repository_paths import ROOT
from frf_client.transport import FetchError

DEFAULT_FILE=ROOT/'.env'
TOKEN_URL='https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token'
CLIENT_ID='cdse-public'
ALLOWED_KEYS={'CDSE_USERNAME','CDSE_PASSWORD','CDSE_ACCESS_TOKEN'}


class CredentialError(RuntimeError):
    pass


def _validate_token(token):
    if not token or token=='REPLACE_WITH_TEMPORARY_BEARER_TOKEN' or any(c.isspace() for c in token):
        raise CredentialError('CDSE_ACCESS_TOKEN is missing, placeholder or contains whitespace')
    return token


def _credential_path(path=None,environ=None):
    env=os.environ if environ is None else environ
    candidate=Path(path or env.get('CDSE_TOKEN_FILE') or DEFAULT_FILE)
    if not candidate.is_absolute():candidate=ROOT/candidate
    candidate=candidate.resolve()
    if not candidate.is_relative_to(ROOT):raise CredentialError('Credential file must remain inside repository root')
    return candidate


def _parse_env(path):
    values={}
    if not path.exists():return values
    for raw in path.read_text(encoding='utf-8').splitlines():
        line=raw.strip()
        if not line or line.startswith('#'):continue
        if line.lower().startswith('export '):line=line[7:].lstrip()
        if '=' not in line:raise CredentialError('Malformed local credential line')
        key,value=line.split('=',1);key=key.strip();value=value.strip()
        if key not in ALLOWED_KEYS or key in values:raise CredentialError('Unexpected or duplicate credential key')
        if len(value)>=2 and value[0]==value[-1] and value[0] in ('"',"'"):value=value[1:-1]
        values[key]=value
    return values


def load_settings(path=None,environ=None):
    """Load credentials without network access; environment overrides local file."""
    env=os.environ if environ is None else environ
    candidate=_credential_path(path,environ)
    values=_parse_env(candidate)
    for key in ALLOWED_KEYS:
        if env.get(key):values[key]=env[key]
    token=values.get('CDSE_ACCESS_TOKEN') or None
    if token:token=_validate_token(token)
    username=values.get('CDSE_USERNAME') or None;password=values.get('CDSE_PASSWORD') or None
    if not token and bool(username)!=bool(password):raise CredentialError('CDSE_USERNAME and CDSE_PASSWORD must both be configured')
    if token:username=password=None
    if username and ('\x00' in username or '\x00' in password):raise CredentialError('NUL is not allowed in credentials')
    source='access_token' if token else 'username_password' if username else 'not_configured'
    return {'access_token':token,'username':username,'password':password,'source':source,'path':candidate}


def load_token(path=None,environ=None):
    """Backward-compatible direct-token loader; password login needs TokenProvider."""
    settings=load_settings(path,environ)
    return settings['access_token'],('environment_or_local_file' if settings['access_token'] else settings['source'])


def status(path=None,environ=None):
    """Return only non-sensitive availability, never credential values."""
    try:settings=load_settings(path,environ)
    except CredentialError as exc:return {'configured':False,'source':'invalid_local_configuration','error':str(exc)}
    return {'configured':settings['source']!='not_configured','source':settings['source'],'error':None,
            'mfa':'prompted_locally_only_if_server_rejects_initial_password_grant'}


def _jwt_exp(token):
    try:
        part=token.split('.')[1];part+='='*(-len(part)%4)
        value=json.loads(base64.urlsafe_b64decode(part.encode()))
        return float(value['exp'])
    except (IndexError,KeyError,ValueError,TypeError,json.JSONDecodeError):return None


class TokenProvider:
    """Hold access/refresh tokens in memory and bound all authentication attempts."""
    def __init__(self,transport,path=None,environ=None,*,max_requests=3,expiry_skew_seconds=30,clock=time.time,prompt=None):
        self.transport=transport;self.settings=load_settings(path,environ);self.max_requests=max_requests
        self.expiry_skew_seconds=expiry_skew_seconds;self.clock=clock;self._default_prompt=prompt is None
        self.prompt=prompt or (lambda:getpass.getpass('CDSE MFA/TOTP code: '))
        self.auth_requests=0;self.access_token=self.settings['access_token'];self.refresh_token=None
        self.expires_at=_jwt_exp(self.access_token) if self.access_token else None

    def _post(self,fields):
        if self.auth_requests>=self.max_requests:raise CredentialError('CDSE authentication attempt limit reached')
        self.auth_requests+=1
        raw=self.transport.post_form_secret(TOKEN_URL,fields)
        try:data=json.loads(raw)
        except (UnicodeDecodeError,json.JSONDecodeError) as exc:raise CredentialError('CDSE authentication returned invalid JSON') from exc
        token=data.get('access_token')
        if not isinstance(token,str):raise CredentialError('CDSE authentication response lacks access token')
        self.access_token=_validate_token(token)
        refresh=data.get('refresh_token');self.refresh_token=refresh if isinstance(refresh,str) and refresh else None
        expires=data.get('expires_in')
        self.expires_at=self.clock()+float(expires) if isinstance(expires,(int,float)) and float(expires)>0 else _jwt_exp(token)
        return self.access_token

    def _password_grant(self):
        if not self.settings['username']:raise CredentialError('Configure CDSE_USERNAME and CDSE_PASSWORD in .env, or CDSE_ACCESS_TOKEN')
        fields={'client_id':CLIENT_ID,'grant_type':'password','username':self.settings['username'],'password':self.settings['password']}
        try:return self._post(fields)
        except FetchError as exc:
            if exc.status!='authentication_failed':raise CredentialError('CDSE authentication transport failed: '+exc.status) from None
        if self._default_prompt and not os.isatty(0):
            raise CredentialError('CDSE login rejected; MFA may be required and needs an interactive terminal')
        totp=self.prompt().strip()
        if not re.fullmatch(r'\d{6,8}',totp):raise CredentialError('MFA/TOTP code was absent or invalid')
        fields['totp']=totp
        try:return self._post(fields)
        except FetchError as exc:raise CredentialError('CDSE authentication failed after MFA: '+exc.status) from None

    def get(self,force_refresh=False):
        if self.access_token and not force_refresh and (self.expires_at is None or self.clock()<self.expires_at-self.expiry_skew_seconds):
            return self.access_token
        if self.refresh_token:
            try:return self._post({'client_id':CLIENT_ID,'grant_type':'refresh_token','refresh_token':self.refresh_token})
            except FetchError:self.refresh_token=None
        return self._password_grant()
