#!/usr/bin/env python3
"""
Busca de patentes no WIPO Patentscope via API.
Requer cadastro em https://patentscope.wipo.int/ para obter a chave de API.
"""

import os
import re
from typing import Optional

from models.patent import Patent
from utils.http_client import http_post_json

DEFAULT_TIMEOUT = int(os.getenv("SEARCH_TIMEOUT_SECONDS", "30"))
DEFAULT_MAX_RESULTS = 3
_WIPO_BASE = "https://patentscope.wipo.int/search/rest/patents"


def search_wipo(
    topic: str,
    max_results: int = DEFAULT_MAX_RESULTS,
    timeout: int = DEFAULT_TIMEOUT,
) -> list[Patent]:
    """
    Busca patentes no WIPO Patentscope. Requer a variavel de ambiente
    WIPO_API_KEY. Se nao estiver configurada, retorna lista vazia.
    """
    api_key = os.getenv("WIPO_API_KEY")
    if not api_key:
        return []

    payload = {
        "searchQuery": f'ti = "{topic}" OR ab = "{topic}"',
        "resultCount": max_results,
    }
    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    data = http_post_json(_WIPO_BASE, headers=headers, payload=payload, timeout=timeout)
    if not data:
        return []

    patents: list[Patent] = []
    items = data.get("resultList") or data.get("results") or data.get("data") or []
    for item in items:
        if not isinstance(item, dict):
            continue
        number = (
            item.get("publicationNumber")
            or item.get("id")
            or item.get("docId")
            or ""
        ).strip()
        if not number:
            continue
        title = (item.get("title") or item.get("inventionTitle") or "").strip() or "(sem título)"
        date = item.get("publicationDate") or item.get("datePublished") or ""
        year = None
        if date:
            match = re.match(r"(\d{4})", str(date))
            if match:
                year = int(match.group(1))
        inventors = []
        for inv in item.get("inventors", []):
            name = inv.get("name") if isinstance(inv, dict) else str(inv)
            if name:
                inventors.append(str(name).strip())
        url = f"https://patentscope.wipo.int/search/pt/detail.html?docId={number}"
        patents.append(
            Patent(
                title=title,
                number=number,
                url=url,
                year=year,
                inventors=inventors,
                jurisdiction="WO",
                source_api="wipo",
            )
        )
    return patents
