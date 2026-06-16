#!/usr/bin/env python3
"""
Busca no Google Scholar e Google Patents via SerpAPI.
Requer cadastro em https://serpapi.com para obter a chave de API.
"""

import os
import re
from typing import Optional
from urllib.parse import urlencode

from models.article import Article
from models.patent import Patent
from utils.http_client import http_get_json

DEFAULT_TIMEOUT = int(os.getenv("SEARCH_TIMEOUT_SECONDS", "30"))
DEFAULT_MAX_RESULTS = 5
_SERPAPI_BASE = "https://serpapi.com/search"


def _build_url(engine: str, topic: str, max_results: int) -> str:
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


def search_google_patents(
    topic: str,
    max_results: int = DEFAULT_MAX_RESULTS,
    timeout: int = DEFAULT_TIMEOUT,
) -> list[Patent]:
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
        year = None
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
    return patents
