#!/usr/bin/env python3
"""
Busca de patentes em multiplas APIs gratuitas:
  - Espacenet OPS / EPO (gratis com cadastro; opcional)
  - USPTO Open Data API (gratis com cadastro; opcional)
  - Lens.org (gratis com cadastro academico; opcional)
  - PatentsView (gratis, sem cadastro, atualmente descontinuada com WAF)

A funcao search_patents() combina resultados de todos os providers ativos.
"""

import base64
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

logger = logging.getLogger("pesquisador.patents")

DEFAULT_TIMEOUT = int(os.getenv("SEARCH_TIMEOUT_SECONDS", "30"))
DEFAULT_MAX_RESULTS = 3

_EPO_OPS_BASE = "https://ops.epo.org/3.2/rest-services"
_EPO_OPS_TOKEN_URL = "https://ops.epo.org/3.2/auth/accesstoken"
_USPTO_BASE = "https://api.uspto.gov/patents/search"
_LENS_PATENT_BASE = "https://api.lens.org/patent/search"
_LENS_SCHOLARLY_BASE = "https://api.lens.org/scholarly/search"
_PATENTSVIEW_BASE = "https://api.patentsview.org/patents/query"
_MAX_RETRIES = 2


@dataclass
class Patent:
    title: str
    number: str
    url: str
    year: Optional[int] = None
    inventors: list[str] = field(default_factory=list)
    assignee: Optional[str] = None
    abstract: Optional[str] = None
    jurisdiction: str = "US"
    source_api: str = "unknown"

    def is_valid(self) -> bool:
        return bool(self.title and self.number and self.url)

    def short_citation(self) -> str:
        inventors = (
            ", ".join(self.inventors[:2])
            if self.inventors
            else "Inventores não listados"
        )
        if len(self.inventors) > 2:
            inventors += " et al."
        year = f" ({self.year})" if self.year else ""
        return f"{inventors}{year} — {self.title} — {self.number} — {self.url}"


def _http_get_json(url: str, headers: dict, timeout: int) -> Optional[dict]:
    for attempt in range(_MAX_RETRIES + 1):
        req = Request(url, headers=headers, method="GET")
        try:
            with urlopen(req, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, json.JSONDecodeError):
            return None
        except URLError:
            if attempt < _MAX_RETRIES:
                time.sleep(0.5 * (attempt + 1))
                continue
            return None
    return None


def _http_get_text(url: str, headers: dict, timeout: int) -> Optional[str]:
    for attempt in range(_MAX_RETRIES + 1):
        req = Request(url, headers=headers, method="GET")
        try:
            with urlopen(req, timeout=timeout) as response:
                return response.read().decode("utf-8", errors="ignore")
        except HTTPError:
            return None
        except URLError:
            if attempt < _MAX_RETRIES:
                time.sleep(0.5 * (attempt + 1))
                continue
            return None
    return None


def _http_post_json(
    url: str, headers: dict, payload: dict, timeout: int
) -> Optional[dict]:
    for attempt in range(_MAX_RETRIES + 1):
        req = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(req, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, json.JSONDecodeError):
            return None
        except URLError:
            if attempt < _MAX_RETRIES:
                time.sleep(0.5 * (attempt + 1))
                continue
            return None
    return None


def _get_epo_ops_token(timeout: int) -> Optional[str]:
    consumer_key = os.getenv("EPO_OPS_CONSUMER_KEY")
    consumer_secret = os.getenv("EPO_OPS_CONSUMER_SECRET")
    if not consumer_key or not consumer_secret:
        return None

    credentials = base64.b64encode(
        f"{consumer_key}:{consumer_secret}".encode("utf-8")
    ).decode("ascii")
    data = urlencode({"grant_type": "client_credentials"}).encode("utf-8")
    req = Request(
        _EPO_OPS_TOKEN_URL,
        data=data,
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return payload.get("access_token")
    except (HTTPError, URLError, json.JSONDecodeError):
        return None


def _search_epo_ops(topic: str, max_results: int, timeout: int) -> list[Patent]:
    token = _get_epo_ops_token(timeout)
    if not token:
        return []

    query = f'ti="{topic}" OR ta="{topic}"'
    params = urlencode({"q": query, "range": f"1-{max_results}"})
    url = f"{_EPO_OPS_BASE}/published-data/search/biblio?{params}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    raw = _http_get_text(url, headers, timeout)
    if not raw:
        return []

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []

    patents: list[Patent] = []
    docs = (
        data.get("ops:world-patent-data", {})
        .get("ops:biblio-search", {})
        .get("ops:search-result", {})
        .get("ops:publication-reference", [])
    )
    for doc in docs:
        number = (doc.get("document-id", {}).get("doc-number") or "").strip()
        if not number:
            continue
        country = doc.get("document-id", {}).get("country", "US")
        kind = doc.get("document-id", {}).get("kind", "")
        full_number = f"{country}{number}{kind}"
        patents.append(
            Patent(
                title="(título a confirmar)",
                number=full_number,
                url=f"https://patents.google.com/patent/{full_number}/en",
                jurisdiction=country,
                source_api="epo_ops",
            )
        )
    return patents


def _search_uspto(topic: str, max_results: int, timeout: int) -> list[Patent]:
    api_key = os.getenv("USPTO_API_KEY")
    if not api_key:
        return []

    payload = {
        "q": topic,
        "rows": max_results,
        "fields": [
            "patent_id",
            "patent_title",
            "patent_date",
            "inventors",
            "assignees",
        ],
    }
    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    data = _http_post_json(f"{_USPTO_BASE}", headers, payload, timeout)
    if not data:
        return []

    patents: list[Patent] = []
    items = data.get("results") or data.get("patents") or data.get("data") or []
    for item in items:
        number = (item.get("patent_id") or item.get("patent_number") or "").strip()
        if not number:
            continue
        title = (item.get("patent_title") or "").strip() or "(sem título)"
        date = item.get("patent_date") or ""
        year = None
        if date and len(date) >= 4:
            match = re.match(r"(\d{4})", date)
            if match:
                year = int(match.group(1))
        inventors = []
        for inv in item.get("inventors", []):
            name = (
                inv.get("inventor_name")
                or f"{inv.get('first_name', '')} {inv.get('last_name', '')}".strip()
            )
            if name:
                inventors.append(name)
        assignees = [
            a.get("assignee_name") or a.get("organization", "")
            for a in item.get("assignees", [])
        ]
        assignees = [a for a in assignees if a]
        patents.append(
            Patent(
                title=title,
                number=number,
                url=f"https://patents.google.com/patent/{number}/en",
                year=year,
                inventors=inventors,
                assignee=assignees[0] if assignees else None,
                jurisdiction="US",
                source_api="uspto",
            )
        )
    return patents


def _search_lens(topic: str, max_results: int, timeout: int) -> list[Patent]:
    token = os.getenv("LENS_API_TOKEN")
    if not token:
        return []

    payload = {
        "query": {"match": {"title": topic}},
        "size": max_results,
        "include": ["lens_id", "title", "date_published", "inventors", "applicants"],
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    data = _http_post_json(_LENS_PATENT_BASE, headers, payload, timeout)
    if not data:
        return []

    patents: list[Patent] = []
    for item in data.get("data", []):
        lens_id = item.get("lens_id")
        title = (item.get("title") or "").strip() or "(sem título)"
        if not lens_id:
            continue
        date = item.get("date_published") or ""
        year = None
        if date and len(date) >= 4:
            match = re.match(r"(\d{4})", date)
            if match:
                year = int(match.group(1))
        inventors = [
            i.get("name", "").strip()
            for i in item.get("inventors", [])
            if i.get("name")
        ]
        applicants = [
            a.get("name", "").strip()
            for a in item.get("applicants", [])
            if a.get("name")
        ]
        patents.append(
            Patent(
                title=title,
                number=lens_id,
                url=f"https://www.lens.org/lens/patent/{lens_id}",
                year=year,
                inventors=inventors,
                assignee=applicants[0] if applicants else None,
                jurisdiction="WO",
                source_api="lens",
            )
        )
    return patents


def _search_patentsview(topic: str, max_results: int, timeout: int) -> list[Patent]:
    """PatentsView legado (descontinuado em 2024 com WAF, mantido como fallback)."""
    query_payload = {
        "q": {"_and": [{"_text_all": {"patent_title": topic}}]},
        "f": [
            "patent_number",
            "patent_title",
            "patent_date",
            "inventor_first_name",
            "inventor_last_name",
            "assignee_organization",
        ],
        "o": {"per_page": max_results},
    }
    params = urlencode(
        {
            "q": json.dumps(query_payload["q"]),
            "f": json.dumps(query_payload["f"]),
            "o": json.dumps(query_payload["o"]),
        }
    )
    url = f"{_PATENTSVIEW_BASE}?{params}"
    headers = {"Accept": "application/json"}
    data = _http_get_json(url, headers, timeout)
    if not data or not isinstance(data.get("patents"), list):
        return []

    patents: list[Patent] = []
    for p in data.get("patents", []):
        number = (p.get("patent_number") or "").strip()
        if not number:
            continue
        title = (p.get("patent_title") or "(sem título)").strip()
        inventors = [
            f"{i.get('inventor_first_name', '')} {i.get('inventor_last_name', '')}".strip()
            for i in p.get("inventors", [])
        ]
        assignees = [
            a.get("assignee_organization", "")
            for a in p.get("assignees", [])
            if a.get("assignee_organization")
        ]
        year = None
        date = p.get("patent_date")
        if date and len(date) >= 4:
            try:
                year = int(date[:4])
            except ValueError:
                year = None
        patents.append(
            Patent(
                title=title,
                number=number,
                url=f"https://patents.google.com/patent/{number}/en",
                year=year,
                inventors=[i for i in inventors if i],
                assignee=assignees[0] if assignees else None,
                jurisdiction="US",
                source_api="patentsview",
            )
        )
    return patents


def _dedup_patents(patents: list[Patent]) -> list[Patent]:
    seen_numbers: set[str] = set()
    seen_titles: set[str] = set()
    result: list[Patent] = []
    for p in patents:
        number_key = p.number.lower()
        if number_key in seen_numbers:
            continue
        seen_numbers.add(number_key)
        if p.title and p.title != "(sem título)" and p.title != "(título a confirmar)":
            title_key = re.sub(r"\W+", "", p.title.lower())
            if title_key and title_key in seen_titles:
                continue
            if title_key:
                seen_titles.add(title_key)
        result.append(p)
    return result


def search_patents(
    topic: str,
    max_results: int = DEFAULT_MAX_RESULTS,
    timeout: int = DEFAULT_TIMEOUT,
) -> list[Patent]:
    """
    Busca patentes reais para o topico combinando varias APIs gratuitas.
    Retorna ate max_results patentes validas.

    Providers ativos (em ordem de prioridade):
      1. Espacenet OPS (gratis com EPO_OPS_CONSUMER_KEY/SECRET)
      2. USPTO (gratis com USPTO_API_KEY)
      3. Lens.org (gratis com LENS_API_TOKEN)
      4. WIPO Patentscope (gratis com WIPO_API_KEY)
      5. Google Patents via SerpAPI (gratis com chave opcional SERPAPI_API_KEY)
      6. PatentsView (gratis, sem cadastro; atualmente descontinuado)
    """
    from .serpapi import search_google_patents as _search_google_patents
    from .wipo import search_wipo as _search_wipo_provider

    collected: list[Patent] = []
    per_provider = max(3, max_results * 2)

    for provider in (
        _search_epo_ops,
        _search_uspto,
        _search_lens,
        _search_wipo_provider,
        _search_google_patents,
        _search_patentsview,
    ):
        try:
            results = provider(topic, per_provider, timeout)
        except Exception as exc:
            logger.warning("Provider %s falhou: %s", provider.__name__, exc)
            results = []
        collected.extend(results)

    if not collected:
        return []

    deduped = _dedup_patents(collected)
    valid = [p for p in deduped if p.is_valid()]
    return valid
