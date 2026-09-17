"""Auditable HTTP with manual redirects, TLS, persistent limits and verified cache."""
from __future__ import annotations
import hashlib
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
    temporary.replace(path)


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
                 hosts=("chldata.erdc.dren.mil",), opener=None):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.offline, self.max_response = offline, max_response
        self.timeout, self.rate_seconds, self.retries = timeout, rate_seconds, retries
        self.failure_ttl, self.hosts = failure_ttl, set(hosts)
        self.state_path = self.directory / "NETWORK_STATE.json"
        self.log_path = self.directory / "requests.jsonl"
        self.state = json.loads(self.state_path.read_text()) if self.state_path.exists() else {
            "transactions": 0, "bytes": 0, "max_transactions": max_requests,
            "max_bytes": max_bytes, "created_utc": datetime.now(timezone.utc).isoformat(),
            "historical_consumption": "not part of this tranche; not reconstructed"}
        if (self.state["max_transactions"], self.state["max_bytes"]) != (max_requests, max_bytes):
            raise ValueError("Persistent budget cannot be silently changed")
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

    def get(self, url):
        self._validate_url(url)
        try:
            return self.cached(url)
        except FetchError as exc:
            if exc.status != "offline_cache_miss":
                raise
        if self.offline:
            raise FetchError("offline_cache_miss")
        original_url, redirects, retry = url, 0, 0
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
                    response = self.opener.open(urllib.request.Request(url, headers={"User-Agent": "FRF-thesis-client/0.1"}), timeout=self.timeout)
                    code, headers = response.status, response.headers
                except urllib.error.HTTPError as exc:
                    response, code, headers = exc, exc.code, exc.headers
                allowance = min(self.max_response, self.state["max_bytes"] - self.state["bytes"])
                length = headers.get("Content-Length")
                if length and int(length) > allowance:
                    raise FetchError("response_too_large")
                pieces, used = [], 0
                while used < allowance:
                    chunk = response.read(min(65536, allowance-used))
                    if not chunk:
                        break
                    pieces.append(chunk)
                    used += len(chunk)
                    self.state["bytes"] += len(chunk)
                    save_json(self.state_path, self.state)
                if used == allowance and (not length or int(length) > used):
                    raise FetchError("incomplete_budget_or_response_limit")
                raw = b"".join(pieces)
                self.log(url=safe_url(url), status="response", code=code, bytes=used)
                if code in (301, 302, 303, 307, 308):
                    if redirects >= 4 or not headers.get("Location"):
                        raise FetchError("redirect_limit")
                    url = urljoin(url, headers["Location"])
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
                                 "status": "ok", "sha256": digest(raw), "bytes": len(raw)})
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
                self._failure(original_url, exc.status, exc.code, bytes_received=self.state["bytes"]-starting_bytes)
                raise
            finally:
                if response is not None:
                    response.close()

    def _failure(self, url, status, code=None, bytes_received=0):
        self.log(url=safe_url(url), status=status, code=code, bytes_received=bytes_received)
        _, meta = self._paths(url)
        save_json(meta, {"url": safe_url(url), "status": status, "code": code,
                         "bytes_received":bytes_received,
                         "expires": time.time() + self.failure_ttl})
