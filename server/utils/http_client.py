#!/usr/bin/env python3
"""
Cliente HTTP centralizado com retry inteligente e rate limiting.

Usamos urllib padrão em vez de requests para evitar dependências.
Todas as chamadas HTTP externas (APIs de busca, Crossref, etc.) passam
por este módulo, que oferece:

  - Retry automático em códigos 429 (rate limit) e 5xx (erro servidor)
  - Backoff progressivo entre tentativas
  - Suporte a GET, POST e retorno JSON ou texto
  - Logging de todas as tentativas

A função safe_query() sanitiza parâmetros para URL encoding.
"""

import json
import logging
import time
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

logger = logging.getLogger("pesquisador.http")

# Número máximo de tentativas e backoff base
MAX_RETRIES = 2
DEFAULT_BACKOFF = 0.5
# Códigos HTTP que indicam erro transiente — vale tentar novamente
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _should_retry(status_code: int | None, error: Exception | None) -> bool:
    """Decide se a requisição deve ser repetida com base no status/erro."""
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
    """Executa uma requisição HTTP e retorna (status_code, body)."""
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
    """
    Faz GET HTTP e retorna o JSON parseado como dict.

    Retorna None em caso de erro (status não retryable, timeout, JSON inválido).
    """
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
                backoff = max(backoff, 2.0)  # Backoff maior para rate limit
            logger.warning(
                "Retry %d/%d para %s (status=%s). Aguardando %.1fs",
                attempt + 1,
                max_retries,
                url,
                status or "URLError",
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
    """
    Faz GET HTTP e retorna o corpo como texto (string).

    Útil para APIs que retornam XML (ex.: arXiv) ou HTML.
    """
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
                status or "?",
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
    """
    Faz POST HTTP com payload JSON e retorna a resposta parseada.

    Usado por APIs que exigem POST para busca (ex.: USPTO, Lens.org).
    """
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
                status or "?",
                backoff,
            )
            time.sleep(backoff)
    return None


def safe_query(text: str) -> str:
    """Sanitiza um texto para uso seguro em query strings de URL (URL encoding)."""
    return quote_plus(text)
