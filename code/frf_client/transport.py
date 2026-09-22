"""Auditable HTTP with manual redirects, TLS, persistent limits and verified cache."""
from __future__ import annotations
import hashlib
import http.client
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode, urljoin, unquote


class FetchError(RuntimeError):
    def __init__(self, status, code=None):
        self.status, self.code = status, code
        super().__init__(status)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def save_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(obj, indent=2, allow_nan=False), encoding="utf-8")
    # Windows readers/antivirus may briefly deny atomic replacement. This is a
    # local persistence retry only; it never repeats an HTTP transaction.
    for attempt in range(6):
        try:
            temporary.replace(path)
            break
        except PermissionError:
            if attempt == 5:raise
            time.sleep(.05)


def safe_url(url):
    p = urlsplit(url)
    sensitive = ("token", "key", "credential", "signature", "password", "auth", "secret")
    query=[]
    for segment in p.query.split("&"):
        key=segment.split("=",1)[0]
        query.append(key+"=REDACTED" if any(x in unquote(key).lower() for x in sensitive) else segment)
    return urlunsplit((p.scheme, p.hostname or "", p.path, "&".join(query), ""))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Transport:
    def __init__(self, directory, *, offline=False, max_requests=40,
                 max_bytes=100*1024**2, max_response=8*1024**2, timeout=30,
                 rate_seconds=.25, retries=1, failure_ttl=3600,
                 hosts=("chldata.erdc.dren.mil",), opener=None,
                 tranche_directory=None,tranche_name=None,new_tranche=False):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.offline, self.max_response = offline, max_response
        self.timeout, self.rate_seconds, self.retries = timeout, rate_seconds, retries
        self.failure_ttl, self.hosts = failure_ttl, set(hosts)
        budget_directory=Path(tranche_directory) if tranche_directory is not None else self.directory
        self.state_path = budget_directory / "NETWORK_STATE.json"
        self.log_path = budget_directory / "requests.jsonl"
        if tranche_directory is not None:
            if not tranche_name or tranche_name in ('.','..') or not __import__('re').fullmatch(r'[A-Za-z0-9_.-]+',tranche_name):
                raise ValueError("Explicit safe tranche name required")
            if new_tranche and self.state_path.exists():raise ValueError("Named tranche already exists; resume without --new-tranche")
            if not new_tranche and not self.state_path.exists():raise ValueError("Unknown tranche: explicit --new-tranche required, no implicit reset")
        self.state = json.loads(self.state_path.read_text()) if self.state_path.exists() else {
            "transactions": 0, "bytes": 0, "max_transactions": max_requests,
            "max_bytes": max_bytes, "created_utc": datetime.now(timezone.utc).isoformat(),
            "historical_consumption": "not part of this tranche; not reconstructed"}
        if (self.state["max_transactions"], self.state["max_bytes"]) != (max_requests, max_bytes):
            raise ValueError("Persistent budget cannot be silently changed")
        if tranche_directory is not None:
            if self.state.get('tranche_name',tranche_name)!=tranche_name:raise ValueError("Tranche identity mismatch")
            if self.state.get('max_response',max_response)!=max_response:raise ValueError("Persistent response limit cannot be enlarged")
            self.state.update(tranche_name=tranche_name,max_response=max_response)
        save_json(self.state_path, self.state)  # exists BEFORE the first request
        self.opener = opener or urllib.request.build_opener(NoRedirect())
        self.last_request = 0.
        self._repair_url_provenance()

    def _repair_url_provenance(self):
        # Early development encoded bare DAP constraints with a spurious '='.
        # Repair only if the exact URL hash proves the original cache key.
        for path in self.directory.glob("*.json"):
            if path.name=="NETWORK_STATE.json":
                continue
            entry=json.loads(path.read_text())
            old=entry.get("url","")
            if ".ascii?" in old and old.endswith("=") and digest(old[:-1].encode())==path.stem:
                entry["url"]=old[:-1]
                if entry.get("final_url")==old:
                    entry["final_url"]=old[:-1]
                save_json(path,entry)
                self.log(status="cache_url_provenance_repaired",url=old[:-1],reason="URL hash matches original key; no new HTTP")

    def _paths(self, url):
        key = digest(url.encode())
        return self.directory / (key + ".payload"), self.directory / (key + ".json")

    def log(self, **entry):
        entry["utc"] = datetime.now(timezone.utc).isoformat()
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, allow_nan=False) + "\n")

    def _validate_url(self, url):
        p = urlsplit(url)
        if p.scheme != "https" or p.hostname not in self.hosts or p.username or p.password:
            raise FetchError("unsupported_or_unauthorized_endpoint")
        # Signed URLs/credentials are intentionally not supported by the anonymous adapter.
        if "REDACTED" in safe_url(url):
            raise FetchError("secret_url_not_supported")

    def import_legacy(self, directory):
        """Verify legacy payloads against successful Block30 request hashes, read-only."""
        directory = Path(directory)
        source = directory / "requests.jsonl"
        imported = []
        if not source.exists():
            return imported
        for line in source.read_text(encoding="utf-8").splitlines():
            entry = json.loads(line)
            if "sha256" not in entry:
                continue
            url = entry["url"]
            self._validate_url(url)
            old = directory / (digest(url.encode()) + ".txt")
            if not old.exists():
                continue
            raw = old.read_bytes()
            text = old.read_text(encoding="utf-8")
            candidates = [raw, text.encode(), text.replace("\n", "\r\n").encode()]
            verified = next((b for b in candidates if digest(b) == entry["sha256"]), None)
            if verified is None:
                imported.append({"url": safe_url(url), "status": "hash_mismatch_not_reused"})
                continue
            payload, metadata = self._paths(url)
            if not metadata.exists():
                payload.write_bytes(verified)
                save_json(metadata, {"url": safe_url(url), "sha256": digest(verified),
                                     "bytes": len(verified), "status": "ok",
                                     "legacy_source": str(old), "verified": True})
            imported.append({"url": safe_url(url), "status": "verified_legacy_reused"})
        return imported

    def import_verified(self,directory,predicate=None):
        """Copy verified payloads only; never import/reset another tranche's state."""
        imported=[]
        for path in sorted(Path(directory).glob('*.json')):
            entry=json.loads(path.read_text())
            if entry.get('status')!='ok' or not entry.get('url'):continue
            url=entry['url']
            if predicate is not None and not predicate(url):continue
            self._validate_url(url)
            payload=path.with_suffix('.payload')
            if not payload.exists():imported.append({'url':safe_url(url),'status':'source_payload_unavailable'});continue
            raw=payload.read_bytes()
            if digest(raw)!=entry['sha256']:imported.append({'url':safe_url(url),'status':'hash_mismatch_not_reused'});continue
            target,metadata=self._paths(url)
            if digest(url.encode())!=path.stem:imported.append({'url':safe_url(url),'status':'source_key_unresolved'});continue
            if not metadata.exists() or json.loads(metadata.read_text()).get('status')!='ok':
                target.write_bytes(raw);save_json(metadata,entry)
            imported.append({'url':safe_url(url),'sha256':entry['sha256'],'status':'verified_payload_reused_no_network'})
        return imported

    def cached(self, url):
        payload, meta = self._paths(url)
        if not meta.exists():
            raise FetchError("offline_cache_miss")
        metadata = json.loads(meta.read_text())
        if metadata["status"] != "ok":
            if time.time() < metadata["expires"]:
                raise FetchError(metadata["status"], metadata.get("code"))
            raise FetchError("offline_cache_miss")
        raw = payload.read_bytes()
        if digest(raw) != metadata["sha256"]:
            raise FetchError("cache_hash_mismatch")
        return raw

    def get(self, url, *, authorization_bearer=None):
        """GET with an optional in-memory bearer token that is never persisted.

        The URL remains the cache identity. Authentication material is accepted
        only as a syntactically safe bearer value and is absent from logs,
        metadata, exceptions and cache provenance.
        """
        self._validate_url(url)
        if authorization_bearer is not None:
            if not isinstance(authorization_bearer,str) or not authorization_bearer or any(c.isspace() for c in authorization_bearer):
                raise FetchError("invalid_bearer_token")
        try:
            return self.cached(url)
        except FetchError as exc:
            if exc.status != "offline_cache_miss":
                raise
        if self.offline:
            raise FetchError("offline_cache_miss")
        original_url, redirects, retry = url, 0, 0
        credential_host=urlsplit(url).hostname if authorization_bearer is not None else None
        while True:
            self._validate_url(url)
            if self.state["transactions"] >= self.state["max_transactions"] or self.state["bytes"] >= self.state["max_bytes"]:
                raise FetchError("incomplete_budget")
            delay = self.rate_seconds - (time.monotonic() - self.last_request)
            if delay > 0:
                time.sleep(delay)
            self.last_request = time.monotonic()
            self.state["transactions"] += 1
            starting_bytes=self.state["bytes"]
            save_json(self.state_path, self.state)
            self.log(url=safe_url(url), status="started", number=self.state["transactions"])
            response = None
            code, headers = None, {}
            try:
                try:
                    headers={"User-Agent": "FRF-thesis-client/0.1"}
                    if authorization_bearer is not None:
                        headers["Authorization"]="Bearer "+authorization_bearer
                    response = self.opener.open(urllib.request.Request(url, headers=headers), timeout=self.timeout)
                    code, headers = response.status, response.headers
                except urllib.error.HTTPError as exc:
                    response, code, headers = exc, exc.code, exc.headers
                allowance = min(self.max_response, self.state["max_bytes"] - self.state["bytes"])
                # urllib exposes encoded entity bytes, not decompressed content.
                # For chunked transfer Content-Length is not a comparable quantity.
                transfer_encoding = headers.get("Transfer-Encoding", "").lower()
                if transfer_encoding and transfer_encoding != "chunked":
                    raise FetchError("unsupported_transfer_encoding")
                length = None if transfer_encoding == "chunked" else headers.get("Content-Length")
                if length is not None:
                    try:
                        length = int(length)
                    except ValueError:
                        raise FetchError("invalid_content_length") from None
                    if length < 0:
                        raise FetchError("invalid_content_length")
                if length is not None and length > allowance:
                    raise FetchError("response_too_large")
                pieces, used = [], 0
                while used < allowance:
                    try:
                        chunk = response.read(min(65536, allowance-used))
                    except http.client.IncompleteRead as exc:
                        partial = exc.partial
                        self.state["bytes"] += len(partial)
                        save_json(self.state_path,self.state)
                        raise FetchError("truncated_response") from None
                    if not chunk:
                        break
                    pieces.append(chunk)
                    used += len(chunk)
                    self.state["bytes"] += len(chunk)
                    save_json(self.state_path, self.state)
                if used == allowance and (length is None or length > used):
                    raise FetchError("incomplete_budget_or_response_limit")
                if length is not None and used != length:
                    raise FetchError("truncated_response" if used < length else "content_length_mismatch")
                raw = b"".join(pieces)
                self.log(url=safe_url(url), status="response", code=code, bytes=used)
                if code in (301, 302, 303, 307, 308):
                    if redirects >= 4 or not headers.get("Location"):
                        raise FetchError("redirect_limit")
                    target=urljoin(url, headers["Location"])
                    if credential_host is not None and urlsplit(target).hostname!=credential_host:
                        raise FetchError("authenticated_cross_origin_redirect")
                    url = target
                    redirects += 1
                    continue
                if code in (429, 500, 502, 503, 504) and retry < self.retries:
                    retry += 1
                    after = headers.get("Retry-After", "1")
                    try:
                        wait = float(after)
                    except ValueError:
                        from email.utils import parsedate_to_datetime
                        wait = (parsedate_to_datetime(after) - datetime.now(timezone.utc)).total_seconds()
                    if wait > 30:
                        raise FetchError("retry_after_deferred", code)
                    time.sleep(max(0, wait))
                    continue
                if code != 200:
                    raise FetchError("authentication_required" if code in (401,403) else "path_not_found" if code == 404 else "http_error", code)
                payload, meta = self._paths(original_url)
                payload.write_bytes(raw)
                save_json(meta, {"url": safe_url(original_url), "final_url": safe_url(url),
                                 "status": "ok", "sha256": digest(raw), "bytes": len(raw),
                                 "content_length":length,"transfer_encoding":transfer_encoding or "identity",
                                 "content_encoding":headers.get("Content-Encoding","identity"),
                                 "length_comparison":"encoded_entity_bytes" if length is not None else "unknown_length_eof"})
                return raw
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                status = "timeout" if isinstance(exc, TimeoutError) or isinstance(getattr(exc,"reason",None), TimeoutError) else "transport_error"
                if status == "timeout" and retry < self.retries:
                    retry += 1
                    self.log(url=safe_url(url), status="timeout_retry_scheduled")
                    time.sleep(1)
                    continue
                self._failure(original_url, status, bytes_received=self.state["bytes"]-starting_bytes)
                raise FetchError(status) from None
            except FetchError as exc:
                if authorization_bearer is not None and exc.status=='authentication_required':
                    self.log(url=safe_url(original_url),status=exc.status,code=exc.code,
                             bytes_received=self.state['bytes']-starting_bytes,cache='not_persisted_for_token_refresh')
                else:
                    self._failure(original_url, exc.status, exc.code, bytes_received=self.state["bytes"]-starting_bytes)
                raise
            finally:
                if response is not None:
                    response.close()

    def post_form_secret(self,url,fields):
        """POST a secret form without caching or persisting body/response content.

        The transaction and encoded response bytes share this transport's
        persistent budget. Redirects and automatic retries are deliberately
        refused; callers bound any credential/MFA/refresh attempts.
        """
        self._validate_url(url)
        if not isinstance(fields,dict) or not fields or not all(isinstance(k,str) and isinstance(v,str) for k,v in fields.items()):
            raise FetchError('invalid_secret_form')
        if self.offline:raise FetchError('offline_cache_miss')
        if self.state['transactions']>=self.state['max_transactions'] or self.state['bytes']>=self.state['max_bytes']:
            raise FetchError('incomplete_budget')
        body=urlencode(fields).encode('utf-8');response=None
        self.state['transactions']+=1;save_json(self.state_path,self.state)
        self.log(url=safe_url(url),status='secret_post_started',number=self.state['transactions'])
        try:
            request=urllib.request.Request(url,data=body,headers={'Content-Type':'application/x-www-form-urlencoded','User-Agent':'thesis-cdse-auth/1.0'},method='POST')
            try:
                response=self.opener.open(request,timeout=self.timeout);code=response.status;headers=response.headers
            except urllib.error.HTTPError as exc:
                response=exc;code=exc.code;headers=exc.headers
            if code in (301,302,303,307,308):raise FetchError('authentication_redirect_refused',code)
            allowance=min(self.max_response,1024*1024,self.state['max_bytes']-self.state['bytes'])
            length=headers.get('Content-Length')
            if length is not None:
                try:length=int(length)
                except ValueError:raise FetchError('invalid_content_length') from None
                if length<0 or length>allowance:raise FetchError('response_too_large')
            chunks=[];used=0
            while used<allowance:
                chunk=response.read(min(65536,allowance-used))
                if not chunk:break
                chunks.append(chunk);used+=len(chunk);self.state['bytes']+=len(chunk);save_json(self.state_path,self.state)
            if used==allowance and (length is None or length>used):raise FetchError('incomplete_budget_or_response_limit')
            if length is not None and used!=length:raise FetchError('truncated_response')
            self.log(url=safe_url(url),status='secret_post_response',code=code,bytes=used)
            if code!=200:raise FetchError('authentication_failed' if code in (400,401) else 'authentication_http_error',code)
            return b''.join(chunks)
        except (urllib.error.URLError,TimeoutError,OSError):
            self.log(url=safe_url(url),status='authentication_transport_error')
            raise FetchError('transport_error') from None
        except FetchError as exc:
            self.log(url=safe_url(url),status=exc.status,code=exc.code)
            raise
        finally:
            if response is not None:response.close()

    def _failure(self, url, status, code=None, bytes_received=0):
        self.log(url=safe_url(url), status=status, code=code, bytes_received=bytes_received)
        _, meta = self._paths(url)
        save_json(meta, {"url": safe_url(url), "status": status, "code": code,
                         "bytes_received":bytes_received,
                         "expires": time.time() + self.failure_ttl})
