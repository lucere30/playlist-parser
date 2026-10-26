"""Small HTTP helpers on top of urllib (no third-party HTTP dependency)."""
from __future__ import annotations

import gzip
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)
PLAIN_UA = "Mozilla/5.0"

_last_call: dict[str, float] = {}
_lock = threading.Lock()


class FetchError(RuntimeError):
    pass


def _throttle(host: str, min_interval: float) -> None:
    if min_interval <= 0:
        return
    with _lock:
        now = time.monotonic()
        wait = _last_call.get(host, 0) + min_interval - now
        if wait > 0:
            time.sleep(wait)
        _last_call[host] = time.monotonic()


def _decode(resp) -> bytes:
    raw = resp.read()
    enc = (resp.headers.get("Content-Encoding") or "").lower()
    if enc == "gzip":
        raw = gzip.decompress(raw)
    elif enc == "deflate":
        raw = zlib.decompress(raw)
    return raw


def request(
    url: str,
    *,
    data: bytes | str | dict | None = None,
    headers: dict | None = None,
    timeout: float = 25,
    retries: int = 2,
    min_interval: float = 0.0,
) -> tuple[bytes, str]:
    """Return (body, final_url). Follows redirects. Retries on 429/5xx/network errors."""
    host = urllib.parse.urlsplit(url).netloc
    hdrs = {"User-Agent": BROWSER_UA, "Accept-Encoding": "gzip, deflate"}
    if headers:
        hdrs.update(headers)
    if isinstance(data, dict):
        data = urllib.parse.urlencode(data)
    if isinstance(data, str):
        data = data.encode("utf-8")
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        _throttle(host, min_interval)
        req = urllib.request.Request(url, data=data, headers=hdrs)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return _decode(resp), resp.geturl()
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(2 * (attempt + 1))
                continue
            raise FetchError(f"HTTP {e.code} for {url}") from e
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last_err = e
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
    raise FetchError(f"Network error for {url}: {last_err}")


def get_text(url: str, **kw) -> str:
    body, _ = request(url, **kw)
    return body.decode("utf-8", errors="replace")


def get_json(url: str, **kw):
    body, _ = request(url, **kw)
    return json.loads(body.decode("utf-8", errors="replace"))


def redirect_chain(url: str, headers: dict | None = None, timeout: float = 20) -> tuple[list[str], str]:
    """Follow redirects by hand. Returns (every URL visited, body of the last page or "").

    Short links sometimes redirect to a page that itself errors (e.g. 404 on desktop),
    but the playlist id is already in one of the redirect targets, so keep them all.
    """
    class _NoFollow(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None

    opener = urllib.request.build_opener(_NoFollow)
    hdrs = {"User-Agent": PLAIN_UA}
    if headers:
        hdrs.update(headers)
    chain, current, body = [url], url, ""
    for _ in range(8):
        try:
            with opener.open(urllib.request.Request(current, headers=hdrs), timeout=timeout) as resp:
                body = _decode(resp).decode("utf-8", errors="replace")
                break
        except urllib.error.HTTPError as e:
            loc = e.headers.get("Location") if e.code in (301, 302, 303, 307, 308) else None
            if not loc:
                break
            current = urllib.parse.urljoin(current, loc)
            chain.append(current)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if len(chain) == 1:
                raise FetchError(f"Network error for {url}: {e}") from e
            break
    return chain, body
