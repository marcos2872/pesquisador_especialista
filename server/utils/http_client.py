#!/usr/bin/env python3
"""Cliente HTTP centralizado com retry inteligente, rate limiting e logging."""

import json
import logging
import time
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

logger = logging.getLogger("pesquisador.http")

MAX_RETRIES = 2
DEFAULT_BACKOFF = 0.5
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _should_retry(status_code: int | None, error: Exception | None) -> bool:
    if status_code is not None and status_code in RETRYABLE_STATUS_CODES:
        return True
    if isinstance(error, URLError):
        return True
    return False


def _make_request(
    req: Request,
    timeout: int,
    attempt: int,
) -> tuple[Optional[int], Optional[bytes]]:
    try:
        with urlopen(req, timeout=timeout) as response:
            return response.status, response.read()
    except HTTPError as e:
        return e.code, None
    except URLError:
        return None, None


def http_get_json(
    url: str,
    headers: dict | None = None,
    timeout: int = 30,
    max_retries: int = MAX_RETRIES,
) -> Optional[dict]:
    headers = headers or {}
    for attempt in range(max_retries + 1):
        req = Request(url, headers=headers, method="GET")
        status, content = _make_request(req, timeout, attempt)
        if status is not None and content is not None:
            try:
                return json.loads(content.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return None
        if status is not None and status not in RETRYABLE_STATUS_CODES:
            return None
        if attempt < max_retries:
            backoff = DEFAULT_BACKOFF * (attempt + 1)
            if status == 429:
                backoff = max(backoff, 2.0)
            logger.warning(
                "Retry %d/%d para %s (status=%s, error=%s). Aguardando %.1fs",
                attempt + 1,
                max_retries,
                url,
                status,
                "URLError" if status is None else "HTTPError",
                backoff,
            )
            time.sleep(backoff)
    return None


def http_get_text(
    url: str,
    headers: dict | None = None,
    timeout: int = 30,
    max_retries: int = MAX_RETRIES,
) -> Optional[str]:
    headers = headers or {}
    for attempt in range(max_retries + 1):
        req = Request(url, headers=headers, method="GET")
        status, content = _make_request(req, timeout, attempt)
        if status is not None and content is not None:
            try:
                return content.decode("utf-8", errors="ignore")
            except Exception:
                return None
        if status is not None and status not in RETRYABLE_STATUS_CODES:
            return None
        if attempt < max_retries:
            backoff = DEFAULT_BACKOFF * (attempt + 1)
            if status == 429:
                backoff = max(backoff, 2.0)
            logger.warning(
                "Retry %d/%d para %s (status=%s). Aguardando %.1fs",
                attempt + 1,
                max_retries,
                url,
                status,
                backoff,
            )
            time.sleep(backoff)
    return None


def http_post_json(
    url: str,
    headers: dict | None = None,
    payload: dict | None = None,
    timeout: int = 30,
    max_retries: int = MAX_RETRIES,
) -> Optional[dict]:
    headers = headers or {}
    data = json.dumps(payload).encode("utf-8") if payload else b""
    headers.setdefault("Content-Type", "application/json")
    for attempt in range(max_retries + 1):
        req = Request(url, data=data, headers=headers, method="POST")
        status, content = _make_request(req, timeout, attempt)
        if status is not None and content is not None:
            try:
                return json.loads(content.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return None
        if status is not None and status not in RETRYABLE_STATUS_CODES:
            return None
        if attempt < max_retries:
            backoff = DEFAULT_BACKOFF * (attempt + 1)
            if status == 429:
                backoff = max(backoff, 2.0)
            logger.warning(
                "Retry %d/%d POST para %s (status=%s). Aguardando %.1fs",
                attempt + 1,
                max_retries,
                url,
                status,
                backoff,
            )
            time.sleep(backoff)
    return None


def safe_query(text: str) -> str:
    """Sanitiza um texto para uso seguro em query strings de URL."""
    return quote_plus(text)
