#!/usr/bin/env python3
"""
Busca no Google Scholar via SerpAPI.

Requer cadastro em https://serpapi.com para obter SERPAPI_API_KEY.
Se a chave não estiver configurada, retorna lista vazia silenciosamente.

Os resultados incluem título, link, autores, ano, veículo e snippet.
Autores/ano/veículo são extraídos heuristicamente do campo
publication_info.summary (ex.: "Smith, J, 2023, Journal of X").
"""

import os
import re
from typing import Optional
from urllib.parse import urlencode

from server.models.article import Article
from server.utils.http_client import http_get_json

DEFAULT_TIMEOUT = int(os.getenv("SEARCH_TIMEOUT_SECONDS", "30"))
DEFAULT_MAX_RESULTS = 5
_SERPAPI_BASE = "https://serpapi.com/search"


def _build_url(engine: str, topic: str, max_results: int) -> str:
    """Monta URL de busca SerpAPI com engine, query e chave de API."""
    api_key = os.getenv("SERPAPI_API_KEY", "")
    params = {
        "engine": engine,
        "q": topic,
        "api_key": api_key,
        "num": str(max_results),
    }
    return f"{_SERPAPI_BASE}?{urlencode(params)}"


def search_google_scholar(
    topic: str,
    max_results: int = DEFAULT_MAX_RESULTS,
    timeout: int = DEFAULT_TIMEOUT,
) -> list[Article]:
    """
    Busca artigos no Google Scholar via SerpAPI.

    Extrai autores, ano e veículo do campo publication_info.summary usando
    heurísticas de formatação típica do Google Scholar.
    """
    api_key = os.getenv("SERPAPI_API_KEY", "")
    if not api_key:
        return []

    url = _build_url("google_scholar", topic, max_results)
    data = http_get_json(url, timeout=timeout)
    if not data:
        return []

    articles: list[Article] = []
    for item in data.get("organic_results", []):
        title = (item.get("title") or "").strip()
        if not title:
            continue

        link = item.get("link") or ""

        # Extrai autores, ano e veículo do summary (ex.: "Smith, J, 2023, Journal")
        pub_info = item.get("publication_info") or {}
        summary = pub_info.get("summary") or ""
        authors: list[str] = []
        year: Optional[int] = None
        venue: Optional[str] = None
        if summary:
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

        abstract = item.get("snippet") or ""

        articles.append(
            Article(
                title=title,
                authors=authors,
                year=year,
                venue=venue,
                url=link,
                abstract=abstract,
                source_api="google_scholar",
            )
        )
    return articles
