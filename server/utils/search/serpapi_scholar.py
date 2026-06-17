#!/usr/bin/env python3
"""
Busca de citações e publicações de autores no Google Scholar via SerpAPI.
Requer cadastro em https://serpapi.com para obter a chave de API.
"""

import logging
import os
import re
from typing import Optional
from urllib.parse import urlencode

from server.models.article import Article
from server.utils.http_client import http_get_json

logger = logging.getLogger("pesquisador.search.serpapi_scholar")

DEFAULT_TIMEOUT = int(os.getenv("SEARCH_TIMEOUT_SECONDS", "30"))
DEFAULT_MAX_RESULTS = 10
_SERPAPI_BASE = "https://serpapi.com/search"


def _build_url(params: dict) -> str:
    """Monta a URL de consulta SerpAPI a partir de um dicionário de parâmetros."""
    return f"{_SERPAPI_BASE}?{urlencode(params)}"


def _parse_publication_summary(
    summary: str,
) -> tuple[list[str], Optional[int], Optional[str]]:
    """Extrai authors, year e venue de uma string de publication_info.summary."""
    authors: list[str] = []
    year: Optional[int] = None
    venue: Optional[str] = None

    if not summary:
        return authors, year, venue

    year_match = re.search(r"\b(19\d{2}|20\d{2})\b", summary)
    if year_match:
        year = int(year_match.group(1))

    parts = [p.strip() for p in summary.split(",")]
    if parts and parts[0]:
        authors = [parts[0]]

    if len(parts) >= 2 and year is None:
        y = parts[1]
        if y.isdigit() and len(y) == 4:
            year = int(y)

    if len(parts) >= 3 and year is not None:
        venue_parts = [p.strip() for p in parts[1:] if p.strip() != str(year)]
        if venue_parts:
            venue = venue_parts[0]

    return authors, year, venue


def search_google_scholar_citations(
    article_id: str,
    max_results: int = DEFAULT_MAX_RESULTS,
    timeout: int = DEFAULT_TIMEOUT,
) -> list[Article]:
    """Busca artigos que citam um artigo específico no Google Scholar via SerpAPI."""
    api_key = os.getenv("SERPAPI_API_KEY", "")
    if not api_key:
        logger.warning("SERPAPI_API_KEY não configurada; retornando lista vazia.")
        return []

    params = {
        "engine": "google_scholar_cite",
        "cites": article_id,
        "api_key": api_key,
        "num": str(max_results),
    }
    url = _build_url(params)
    data = http_get_json(url, timeout=timeout)
    if not data:
        return []

    results: list[Article] = []
    for item in data.get("organic_results", []):
        title = (item.get("title") or "").strip()
        if not title:
            continue

        link = item.get("link") or ""
        abstract = item.get("snippet") or ""

        pub_info = item.get("publication_info") or {}
        summary = pub_info.get("summary") or ""
        authors, year, venue = _parse_publication_summary(summary)

        results.append(
            Article(
                title=title,
                authors=authors,
                year=year,
                venue=venue,
                url=link,
                abstract=abstract,
                source_api="google_scholar_citations",
            )
        )

    logger.info("Provider google_scholar_citations: %d resultados", len(results))
    return results


def search_google_scholar_author(
    author_id: str,
    max_results: int = DEFAULT_MAX_RESULTS,
    timeout: int = DEFAULT_TIMEOUT,
) -> list[Article]:
    """Busca publicações de um autor no Google Scholar via SerpAPI."""
    api_key = os.getenv("SERPAPI_API_KEY", "")
    if not api_key:
        logger.warning("SERPAPI_API_KEY não configurada; retornando lista vazia.")
        return []

    params = {
        "engine": "google_scholar_author",
        "mauthors": author_id,
        "api_key": api_key,
        "num": str(max_results),
    }
    url = _build_url(params)
    data = http_get_json(url, timeout=timeout)
    if not data:
        return []

    results: list[Article] = []
    for item in data.get("articles", []):
        title = (item.get("title") or "").strip()
        if not title:
            continue

        link = item.get("link") or ""
        authors_raw = item.get("authors") or []
        authors = [str(a).strip() for a in authors_raw if str(a).strip()]

        year: Optional[int] = None
        year_raw = item.get("year")
        if year_raw is not None:
            try:
                year = int(year_raw)
            except (ValueError, TypeError):
                year = None

        venue = item.get("journal") or None
        abstract = item.get("snippet") or item.get("abstract") or ""

        results.append(
            Article(
                title=title,
                authors=authors,
                year=year,
                venue=venue,
                url=link,
                abstract=abstract,
                source_api="google_scholar_author",
            )
        )

    logger.info("Provider google_scholar_author: %d resultados", len(results))
    return results
