#!/usr/bin/env python3
"""
Busca de artigos no IEEE Xplore via API oficial.
Requer cadastro gratuito em https://developer.ieee.org/ para obter a chave.
"""

import os
from typing import Optional
from urllib.parse import urlencode

from models.article import Article
from utils.http_client import http_get_json

DEFAULT_TIMEOUT = int(os.getenv("SEARCH_TIMEOUT_SECONDS", "30"))
DEFAULT_MAX_RESULTS = 5
_IEEE_BASE = "https://ieeexploreapi.ieee.org/api/v1/search/articles"


def search_ieee(
    topic: str,
    max_results: int = DEFAULT_MAX_RESULTS,
    timeout: int = DEFAULT_TIMEOUT,
) -> list[Article]:
    """
    Busca artigos no IEEE Xplore. Requer a variavel de ambiente IEEE_API_KEY.
    Se a chave nao estiver configurada, retorna lista vazia sem erro.
    """
    api_key = os.getenv("IEEE_API_KEY")
    if not api_key:
        return []

    params = urlencode({
        "querytext": topic,
        "apikey": api_key,
        "max_records": str(max_results),
        "sort_field": "publication_year",
        "sort_order": "desc",
    })
    url = f"{_IEEE_BASE}?{params}"
    data = http_get_json(url, timeout=timeout)
    if not data:
        return []

    raw_articles = data.get("articles") or []
    articles: list[Article] = []
    for item in raw_articles:
        title = (item.get("title") or "").strip() or "(sem título)"
        doi = item.get("doi")
        url = f"https://doi.org/{doi}" if doi else None
        if not url:
            article_number = item.get("article_number")
            if article_number:
                url = f"https://ieeexplore.ieee.org/document/{article_number}"
        authors: list[str] = []
        for a in item.get("authors", {}).get("authors", []):
            name = (a.get("full_name") or "").strip()
            if name:
                authors.append(name)
        year_str = item.get("publication_year")
        try:
            year = int(year_str) if year_str else None
        except (TypeError, ValueError):
            year = None
        venue = item.get("publication_title")
        abstract = item.get("abstract")
        articles.append(
            Article(
                title=title,
                authors=authors,
                year=year,
                venue=venue,
                doi=doi,
                url=url,
                abstract=abstract,
                source_api="ieee",
            )
        )
    return articles
