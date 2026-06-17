#!/usr/bin/env python3
"""
Busca de patentes em multiplas APIs gratuitas:
  - Espacenet OPS / EPO (gratis com cadastro; opcional)
  - USPTO Open Data API (gratis com cadastro; opcional)
  - Lens.org (gratis com cadastro academico; opcional)
  - PatentsView (gratis, sem cadastro, atualmente descontinuada com WAF)
  - WIPO Patentscope (gratis com cadastro; opcional)
  - Google Patents via SerpAPI (gratis com cadastro; opcional)

A funcao search_patents() combina resultados de todos os providers ativos
em paralelo, remove duplicatas e respeita max_results.
"""

import base64
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Optional
from urllib.parse import urlencode

from server.models.patent import Patent
from server.utils.http_client import http_get_json, http_get_text, http_post_json
from server.utils.search.serpapi_patents import enrich_patent_with_details

logger = logging.getLogger("pesquisador.patents")

DEFAULT_TIMEOUT = int(os.getenv("SEARCH_TIMEOUT_SECONDS", "30"))
DEFAULT_MAX_RESULTS = 5  # Patentes finais retornadas por search_patents() após dedup
PROVIDER_MULTIPLIER = (
    2  # Cada provider busca max_results * PROVIDER_MULTIPLIER para garantir variedade
)

_EPO_OPS_BASE = "https://ops.epo.org/3.2/rest-services"
_EPO_OPS_TOKEN_URL = "https://ops.epo.org/3.2/auth/accesstoken"
_USPTO_BASE = "https://api.uspto.gov/patents/search"
_LENS_PATENT_BASE = "https://api.lens.org/patent/search"
_LENS_SCHOLARLY_BASE = "https://api.lens.org/scholarly/search"
_PATENTSVIEW_BASE = "https://api.patentsview.org/patents/query"


def _get_epo_ops_token(timeout: int) -> Optional[str]:
    """
    Obtém token de acesso para a API Espacenet OPS (EPO).

    Usa client credentials OAuth2 com as credenciais EPO_OPS_CONSUMER_KEY
    e EPO_OPS_CONSUMER_SECRET.
    """
    consumer_key = os.getenv("EPO_OPS_CONSUMER_KEY")
    consumer_secret = os.getenv("EPO_OPS_CONSUMER_SECRET")
    if not consumer_key or not consumer_secret:
        return None

    credentials = base64.b64encode(
        f"{consumer_key}:{consumer_secret}".encode("utf-8")
    ).decode("ascii")
    headers = {
        "Authorization": f"Basic {credentials}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    payload = http_post_json(
        _EPO_OPS_TOKEN_URL,
        headers=headers,
        payload=None,
        timeout=timeout,
    )
    if not isinstance(payload, dict):
        return None
    return payload.get("access_token")


def _search_epo_ops(topic: str, max_results: int, timeout: int) -> list[Patent]:
    """
    Busca patentes na API Espacenet OPS (EPO).

    Requer EPO_OPS_CONSUMER_KEY e EPO_OPS_CONSUMER_SECRET.
    Usa busca textual no título e abstract.
    """
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
    raw = http_get_text(url, headers, timeout)
    if not raw:
        return []

    try:
        import json

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
    """Busca patentes na API USPTO Open Data. Requer USPTO_API_KEY."""
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
    data = http_post_json(
        f"{_USPTO_BASE}", headers=headers, payload=payload, timeout=timeout
    )
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
    """Busca patentes na API Lens.org. Requer LENS_API_TOKEN."""
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
    data = http_post_json(
        _LENS_PATENT_BASE, headers=headers, payload=payload, timeout=timeout
    )
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
    """
    PatentsView (gratuito, sem cadastro).

    ATENÇÃO: API descontinuada em 2024 com WAF (Web Application Firewall).
    Mantido como fallback histórico — pode não funcionar consistentemente.
    """
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
            "q": __import__("json").dumps(query_payload["q"]),
            "f": __import__("json").dumps(query_payload["f"]),
            "o": __import__("json").dumps(query_payload["o"]),
        }
    )
    url = f"{_PATENTSVIEW_BASE}?{params}"
    headers = {"Accept": "application/json"}
    data = http_get_json(url, headers, timeout)
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
    """
    Remove patentes duplicadas por número ou título normalizado.

    Preserva a primeira ocorrência. Ignora títulos placeholders
    ("(sem título)", "(título a confirmar)") para não bloquear
    registros com título pendente.
    """
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
    Busca patentes reais para o tópico combinando APIs gratuitas em paralelo.

    Providers ativos (todos gratuitos, alguns com chave opcional):
      1. Espacenet OPS (EPO_OPS_CONSUMER_KEY/SECRET)
      2. USPTO (USPTO_API_KEY)
      3. Lens.org (LENS_API_TOKEN)
      4. WIPO Patentscope (WIPO_API_KEY)
      5. Google Patents via SerpAPI (SERPAPI_API_KEY)
      6. PatentsView (sem cadastro, atualmente descontinuado)

    Se houver SERPAPI_API_KEY, as patentes são enriquecidas com detalhes
    (classificação CPC, número de reivindicações, forward references).
    """
    from .serpapi_patents import search_google_patents as _search_google_patents
    from .wipo import search_wipo as _search_wipo_provider

    per_provider = max(3, max_results * PROVIDER_MULTIPLIER)
    providers: list[tuple[str, Any]] = []
    if os.getenv("EPO_OPS_CONSUMER_KEY", "").strip():
        providers.append(("epo_ops", _search_epo_ops))
    if os.getenv("USPTO_API_KEY", "").strip():
        providers.append(("uspto", _search_uspto))
    if os.getenv("LENS_API_TOKEN", "").strip():
        providers.append(("lens", _search_lens))
    if os.getenv("WIPO_API_KEY", "").strip():
        providers.append(("wipo", _search_wipo_provider))
    if os.getenv("SERPAPI_API_KEY", "").strip():
        providers.append(("google_patents", _search_google_patents))
    providers.append(("patentsview", _search_patentsview))

    collected: list[Patent] = []

    with ThreadPoolExecutor(max_workers=len(providers)) as executor:
        future_to_name = {
            executor.submit(fn, topic, per_provider, timeout): name
            for name, fn in providers
        }
        for future in as_completed(future_to_name):
            name = future_to_name[future]
            try:
                results = future.result()
                logger.info("Provider %s: %d resultados", name, len(results))
                collected.extend(results)
            except Exception as exc:
                logger.warning("Provider %s falhou: %s", name, exc)

    if not collected:
        return []

    deduped = _dedup_patents(collected)
    valid = [p for p in deduped if p.is_valid()]

    # Enrich top patents with Google Patents details when SerpAPI key is available
    if os.getenv("SERPAPI_API_KEY", "").strip() and valid:
        enriched = []
        for patent in valid[:max_results]:
            try:
                enriched.append(enrich_patent_with_details(patent, timeout=timeout))
            except Exception as exc:
                logger.warning("Falha ao enriquecer patente %s: %s", patent.number, exc)
                enriched.append(patent)
        valid = enriched

    return valid[:max_results]
