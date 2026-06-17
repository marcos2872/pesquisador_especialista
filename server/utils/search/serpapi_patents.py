#!/usr/bin/env python3
"""
Busca de patentes no Google Patents via SerpAPI com enriquecimento de detalhes.

Fornece:
  - search_google_patents: busca lista de patentes por topico (mantem assinatura original).
  - search_google_patents_details: busca detalhes de uma patente via engine google_patents_details.
  - enrich_patent_with_details: enriquece um objeto Patent com dados detalhados.

Requer cadastro em https://serpapi.com para obter a chave de API (SERPAPI_API_KEY).
"""

import logging
import os
import re
from copy import deepcopy
from typing import Optional
from urllib.parse import urlencode

from server.models.patent import Patent
from server.utils.http_client import http_get_json

logger = logging.getLogger("pesquisador.patents")

DEFAULT_TIMEOUT = int(os.getenv("SEARCH_TIMEOUT_SECONDS", "30"))
DEFAULT_MAX_RESULTS = 5
_SERPAPI_BASE = "https://serpapi.com/search"


def _build_url(engine: str, query: str, num: int) -> str:
    """Constroi URL de busca SerpAPI com engine, query e limite de resultados."""
    api_key = os.getenv("SERPAPI_API_KEY", "")
    params = {
        "engine": engine,
        "q": query,
        "api_key": api_key,
        "num": str(num),
    }
    return f"{_SERPAPI_BASE}?{urlencode(params)}"


def _build_details_url(patent_id: str) -> str:
    """Constroi URL de detalhes de patente no SerpAPI (engine=google_patents_details)."""
    api_key = os.getenv("SERPAPI_API_KEY", "")
    params = {
        "engine": "google_patents_details",
        "patent_id": patent_id,
        "api_key": api_key,
    }
    return f"{_SERPAPI_BASE}?{urlencode(params)}"


def search_google_patents(
    topic: str,
    max_results: int = DEFAULT_MAX_RESULTS,
    timeout: int = DEFAULT_TIMEOUT,
) -> list[Patent]:
    """Busca patentes no Google Patents via SerpAPI e retorna lista de Patent."""
    api_key = os.getenv("SERPAPI_API_KEY", "")
    if not api_key:
        return []

    url = _build_url("google_patents", topic, max_results)
    data = http_get_json(url, timeout=timeout)
    if not data:
        return []

    patents: list[Patent] = []
    for item in data.get("organic_results", []):
        title = (item.get("title") or "").strip()
        patent_id = item.get("patent_id") or ""
        link = item.get("link") or ""
        if not title or not patent_id:
            continue

        date = item.get("publication_date") or ""
        year: Optional[int] = None
        if date:
            match = re.match(r"(\d{4})", str(date))
            if match:
                year = int(match.group(1))

        inventors_raw = item.get("inventor") or item.get("inventors") or []
        inventors = [str(i).strip() for i in inventors_raw if str(i).strip()]

        assignee_raw = item.get("assignee")
        assignee: Optional[str] = None
        if isinstance(assignee_raw, str):
            assignee = assignee_raw.strip() or None
        elif isinstance(assignee_raw, list):
            assignee = str(assignee_raw[0]).strip() if assignee_raw else None

        abstract = item.get("summary") or item.get("snippet") or ""

        patents.append(
            Patent(
                title=title,
                number=patent_id,
                url=link or f"https://patents.google.com/patent/{patent_id}/en",
                year=year,
                inventors=inventors,
                assignee=assignee,
                abstract=abstract,
                source_api="google_patents",
            )
        )

    logger.info("Provider google_patents: %d resultados", len(patents))
    return patents


def search_google_patents_details(
    patent_id: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> Optional[dict]:
    """Busca detalhes de uma patente via SerpAPI (engine=google_patents_details)."""
    api_key = os.getenv("SERPAPI_API_KEY", "")
    if not api_key:
        logger.warning("SERPAPI_API_KEY nao configurada; detalhes ignorados.")
        return None

    url = _build_details_url(patent_id)
    data = http_get_json(url, timeout=timeout)
    if not data:
        logger.warning("Sem resposta de detalhes para patente %s", patent_id)
        return None

    title = (data.get("title") or "").strip()

    description = data.get("description") or ""
    summary = (
        description.strip()
        if isinstance(description, str)
        else str(description).strip()
    )

    classification = data.get("classification")
    if isinstance(classification, list):
        classification = [str(c).strip() for c in classification if str(c).strip()]
    else:
        classification = []

    claims_raw = data.get("claims")
    claims_count: Optional[int] = None
    if isinstance(claims_raw, list):
        claims_count = len(claims_raw)
    elif isinstance(claims_raw, dict):
        claims_count = len(claims_raw.get("claims", claims_raw.get("items", [])))
    elif isinstance(claims_raw, (int, str)):
        try:
            claims_count = int(claims_raw)
        except (ValueError, TypeError):
            claims_count = None

    forward_references = data.get("forward_references") or data.get(
        "forward_references_count"
    )
    forward_references_count: Optional[int] = None
    if isinstance(forward_references, list):
        forward_references_count = len(forward_references)
    elif isinstance(forward_references, (int, str)):
        try:
            forward_references_count = int(forward_references)
        except (ValueError, TypeError):
            forward_references_count = None

    result = {
        "title": title,
        "summary": summary,
        "classification": classification,
        "claims_count": claims_count,
        "forward_references_count": forward_references_count,
    }

    logger.info("Detalhes obtidos para patente %s", patent_id)
    return result


def enrich_patent_with_details(
    patent: Patent,
    timeout: int = DEFAULT_TIMEOUT,
) -> Patent:
    """Enriquece um Patent com dados detalhados do Google Patents via SerpAPI."""
    if not patent.number:
        return patent

    details = search_google_patents_details(patent.number, timeout=timeout)
    if not details:
        return patent

    enriched = deepcopy(patent)

    summary = details.get("summary") or ""
    classification = details.get("classification") or []

    if summary and not enriched.abstract:
        enriched.abstract = summary

    if classification:
        cpc_text = ", ".join(classification)
        if enriched.abstract:
            enriched.abstract = f"{enriched.abstract}\n\nClassificacao CPC: {cpc_text}"
        else:
            enriched.abstract = f"Classificacao CPC: {cpc_text}"

    claims_count = details.get("claims_count")
    if claims_count is not None and enriched.abstract:
        enriched.abstract += f"\nReivindicacoes: {claims_count}"

    forward_refs = details.get("forward_references_count")
    if forward_refs is not None and enriched.abstract:
        enriched.abstract += f" | Citada por {forward_refs} patentes"

    return enriched
