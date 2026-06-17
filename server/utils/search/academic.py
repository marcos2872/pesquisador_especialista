#!/usr/bin/env python3
"""
Busca de artigos acadêmicos em múltiplas APIs gratuitas.

Provedores disponíveis (todos gratuitos):
  - Crossref: sem cadastro, primário, alta cobertura
  - OpenAlex: sem cadastro, bom para artigos recentes
  - arXiv: sem cadastro, foco em preprint (física, cs, matemática)
  - Core.ac.uk: sem cadastro, agrega repositórios institucionais
  - Semantic Scholar: gratuito com chave opcional
  - Unpaywall: enriquece com link de PDF (requer email)
  - IEEE Xplore: gratuito com chave (IEEE_API_KEY)
  - Google Scholar via SerpAPI: gratuito com chave (SERPAPI_API_KEY)

A função search_articles() roda todos os providers ativos em paralelo
(ThreadPoolExecutor), remove duplicatas por DOI/título e respeita o
limite max_results.
"""

import logging
import os
import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Optional
from urllib.parse import urlencode

from server.models.article import Article
from server.utils.http_client import http_get_json, http_get_text

logger = logging.getLogger("pesquisador.academic")

DEFAULT_TIMEOUT = int(os.getenv("SEARCH_TIMEOUT_SECONDS", "30"))
DEFAULT_MAX_RESULTS = 5
DEFAULT_OPENALEX_EMAIL = os.getenv("OPENALEX_USER_AGENT", "pesquisador@example.com")
DEFAULT_UNPAYWALL_EMAIL = os.getenv("UNPAYWALL_EMAIL", "")
_SEMANTIC_SCHOLAR_API_KEY = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "").strip()
_CORE_API_KEY = os.getenv("CORE_API_KEY", "").strip()

# URLs base das APIs
_OPENALEX_BASE = "https://api.openalex.org"
_CROSSREF_BASE = "https://api.crossref.org"
_ARXIV_BASE = "http://export.arxiv.org/api/query"
_CORE_BASE = "https://api.core.ac.uk/v3"
_SEMANTIC_SCHOLAR_BASE = "https://api.semanticscholar.org/graph/v1"
_UNPAYWALL_BASE = "https://api.unpaywall.org/v2"
# Namespace XML do arXiv para parsing
_ARXIV_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


def _reconstruct_abstract(inverted_index: Optional[dict]) -> Optional[str]:
    if not inverted_index:
        return None
    positions: list[tuple[int, str]] = []
    for word, indices in inverted_index.items():
        for idx in indices:
            positions.append((idx, word))
    if not positions:
        return None
    positions.sort(key=lambda x: x[0])
    return " ".join(word for _, word in positions)


def _search_crossref(topic: str, max_results: int, timeout: int) -> list[Article]:
    """Busca artigos na API Crossref (gratuita, sem cadastro)."""
    params = urlencode(
        {
            "query.bibliographic": topic,
            "rows": str(max_results),
            "sort": "relevance",
        }
    )
    url = f"{_CROSSREF_BASE}/works?{params}"
    headers = {
        "User-Agent": f"pesquisador_especialista/1.0 (mailto:{DEFAULT_OPENALEX_EMAIL})",
        "Accept": "application/json",
    }
    data = http_get_json(url, headers, timeout)
    if not data:
        return []

    articles: list[Article] = []
    for item in data.get("message", {}).get("items", []):
        doi = item.get("DOI")
        url = f"https://doi.org/{doi}" if doi else None
        authors = [
            f"{a.get('given', '')} {a.get('family', '')}".strip()
            for a in item.get("author", [])
        ]
        venue = (item.get("container-title") or [None])[0]
        year = (item.get("published-print") or item.get("published-online") or {}).get(
            "date-parts", [[None]]
        )[0][0]
        abstract = item.get("abstract")
        if abstract:
            abstract = re.sub(r"<[^>]+>", "", abstract).strip()
        articles.append(
            Article(
                title=(item.get("title") or ["(sem título)"])[0],
                authors=[a for a in authors if a],
                year=year,
                venue=venue,
                doi=doi,
                url=url,
                abstract=abstract,
                source_api="crossref",
            )
        )
    return articles


def _search_openalex(topic: str, max_results: int, timeout: int) -> list[Article]:
    """
    Busca artigos na API OpenAlex (gratuita, sem cadastro).

    Tenta duas estratégias: filtro por título (mais preciso) e busca
    textual (mais abrangente). Usa a que retornar resultados primeiro.
    """
    for extra in (
        {"filter": f"title.search:{topic}"},
        {"search": topic},
    ):
        params = urlencode(
            {
                **extra,
                "per_page": str(max_results),
                "sort": "cited_by_count:desc",
            }
        )
        url = f"{_OPENALEX_BASE}/works?{params}"
        headers = {
            "User-Agent": f"pesquisador_especialista/1.0 (mailto:{DEFAULT_OPENALEX_EMAIL})",
            "Accept": "application/json",
        }
        data = http_get_json(url, headers, timeout)
        if not data:
            continue

        results = data.get("results", [])
        if not results:
            continue

        articles: list[Article] = []
        for item in results:
            doi = item.get("doi")
            if doi and doi.startswith("https://doi.org/"):
                doi = doi.replace("https://doi.org/", "")
            landing = item.get("primary_location", {}).get("landing_page_url")
            url = item.get("doi") or landing
            authors = [
                a.get("author", {}).get("display_name")
                for a in item.get("authorships", [])
                if a.get("author", {}).get("display_name")
            ]
            venue = (item.get("primary_location", {}).get("source") or {}).get(
                "display_name"
            )
            articles.append(
                Article(
                    title=item.get("title")
                    or item.get("display_name")
                    or "(sem título)",
                    authors=authors,
                    year=item.get("publication_year"),
                    venue=venue,
                    doi=doi,
                    url=url,
                    abstract=_reconstruct_abstract(item.get("abstract_inverted_index")),
                    source_api="openalex",
                )
            )
        if articles:
            return articles
    return []


def _search_arxiv(topic: str, max_results: int, timeout: int) -> list[Article]:
    """Busca preprints na API arXiv (gratuita, sem cadastro, retorna XML)."""
    params = urlencode(
        {"search_query": f"all:{topic}", "max_results": str(max_results)}
    )
    url = f"{_ARXIV_BASE}?{params}"
    headers = {
        "User-Agent": "pesquisador_especialista/1.0",
        "Accept": "application/atom+xml",
    }
    raw = http_get_text(url, headers, timeout)
    if not raw:
        return []

    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return []

    articles: list[Article] = []
    for entry in root.findall("atom:entry", _ARXIV_NS):
        title_el = entry.find("atom:title", _ARXIV_NS)
        title = (
            (title_el.text or "").strip().replace("\n", " ")
            if title_el is not None
            else ""
        )
        summary_el = entry.find("atom:summary", _ARXIV_NS)
        summary = (
            (summary_el.text or "").strip().replace("\n", " ")
            if summary_el is not None
            else None
        )
        published_el = entry.find("atom:published", _ARXIV_NS)
        year = None
        if published_el is not None and published_el.text:
            match = re.match(r"(\d{4})", published_el.text)
            if match:
                year = int(match.group(1))
        id_el = entry.find("atom:id", _ARXIV_NS)
        arxiv_id = (id_el.text or "").strip() if id_el is not None else ""
        if not arxiv_id:
            continue
        arxiv_id = arxiv_id.replace("http://arxiv.org/abs/", "").replace(
            "https://arxiv.org/abs/", ""
        )
        authors = []
        for a in entry.findall("atom:author", _ARXIV_NS):
            name_el = a.find("atom:name", _ARXIV_NS)
            if name_el is not None and name_el.text:
                authors.append(name_el.text.strip())
        doi_el = entry.find("arxiv:doi", _ARXIV_NS)
        doi = (doi_el.text or "").strip() if doi_el is not None else None
        doi = doi or None
        articles.append(
            Article(
                title=title or "(sem título)",
                authors=authors,
                year=year,
                venue="arXiv",
                doi=doi,
                url=f"https://arxiv.org/abs/{arxiv_id}",
                abstract=summary,
                pdf_url=f"https://arxiv.org/pdf/{arxiv_id}",
                source_api="arxiv",
            )
        )
    return articles


def _search_core(topic: str, max_results: int, timeout: int) -> list[Article]:
    """Busca artigos na API CORE (requer CORE_API_KEY)."""
    params = urlencode({"q": topic, "limit": str(max_results)})
    url = f"{_CORE_BASE}/search/works?{params}"
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    }
    if _CORE_API_KEY:
        headers["Authorization"] = f"Bearer {_CORE_API_KEY}"
    data = http_get_json(url, headers, timeout)
    if not data:
        return []

    articles: list[Article] = []
    for item in data.get("results", []):
        title = (item.get("title") or "").strip() or "(sem título)"
        doi = item.get("doi")
        if doi and not str(doi).startswith("http"):
            url = f"https://doi.org/{doi}"
        else:
            url = doi or item.get("downloadUrl") or item.get("link")
        authors = []
        for a in item.get("authors", []):
            name = a.get("name") or ""
            if name:
                authors.append(name)
        year = item.get("yearPublished")
        abstract = item.get("abstract")
        articles.append(
            Article(
                title=title,
                authors=authors,
                year=year,
                venue=item.get("publisher") or "CORE",
                doi=doi if doi and not str(doi).startswith("http") else None,
                url=url,
                abstract=abstract,
                source_api="core",
            )
        )
    return articles


def _search_semantic_scholar(
    topic: str, max_results: int, timeout: int
) -> list[Article]:
    """
    Busca artigos na API Semantic Scholar.

    Requer SEMANTIC_SCHOLAR_API_KEY (opcional). Sem a chave, ainda funciona
    mas com limite de taxa mais restritivo.
    """
    fields = "title,authors,year,venue,abstract,externalIds"
    params = urlencode({"query": topic, "limit": str(max_results), "fields": fields})
    url = f"{_SEMANTIC_SCHOLAR_BASE}/paper/search?{params}"
    headers = {"Accept": "application/json"}
    if _SEMANTIC_SCHOLAR_API_KEY:
        headers["x-api-key"] = _SEMANTIC_SCHOLAR_API_KEY
    data = http_get_json(url, headers, timeout)
    if not data:
        return []

    articles: list[Article] = []
    for item in data.get("data", []):
        title = (item.get("title") or "").strip() or "(sem título)"
        authors = [a.get("name", "") for a in item.get("authors", []) if a.get("name")]
        year = item.get("year")
        venue = item.get("venue")
        abstract = item.get("abstract")
        external = item.get("externalIds") or {}
        doi = external.get("DOI")
        url = f"https://doi.org/{doi}" if doi else None
        if not url and item.get("paperId"):
            url = f"https://www.semanticscholar.org/paper/{item['paperId']}"
        articles.append(
            Article(
                title=title,
                authors=authors,
                year=year,
                venue=venue,
                doi=doi,
                url=url,
                abstract=abstract,
                source_api="semantic_scholar",
            )
        )
    return articles


def _enrich_with_unpaywall(articles: list[Article], timeout: int) -> list[Article]:
    """
    Enriquece artigos com link de PDF gratuito via Unpaywall.

    Requer UNPAYWALL_EMAIL configurado. O Unpaywall consulta repositórios
    de acesso aberto para encontrar versões gratuitas dos artigos.
    """
    if not DEFAULT_UNPAYWALL_EMAIL or "@" not in DEFAULT_UNPAYWALL_EMAIL:
        return articles

    def _fetch_one(article: Article) -> None:
        if not article.doi or article.pdf_url:
            return
        url = f"{_UNPAYWALL_BASE}/{article.doi}?email={DEFAULT_UNPAYWALL_EMAIL}"
        headers = {"Accept": "application/json"}
        data = http_get_json(url, headers, timeout)
        if not data:
            return
        best = data.get("best_oa_location") or {}
        pdf_url = best.get("url_for_pdf") or best.get("url")
        if pdf_url:
            article.pdf_url = pdf_url

    with ThreadPoolExecutor(max_workers=4) as executor:
        executor.map(_fetch_one, articles)

    return articles


def _dedup_articles(articles: list[Article]) -> list[Article]:
    """
    Remove duplicatas por DOI ou título normalizado.

    A normalização remove caracteres não-alfanuméricos para comparar
    títulos de forma flexível (ex.: "Screw-Extruder" == "Screw Extruder").
    Preserva a primeira ocorrência de cada artigo.
    """
    seen_doi: set[str] = set()
    seen_titles: set[str] = set()
    result: list[Article] = []
    for a in articles:
        if a.doi:
            doi_key = a.doi.lower()
            if doi_key in seen_doi:
                continue
            seen_doi.add(doi_key)
        if a.title:
            title_key = re.sub(r"\W+", "", a.title.lower())
            if title_key and title_key in seen_titles:
                continue
            if title_key:
                seen_titles.add(title_key)
        result.append(a)
    return result


def search_articles(
    topic: str,
    max_results: int = DEFAULT_MAX_RESULTS,
    timeout: int = DEFAULT_TIMEOUT,
) -> list[Article]:
    """
    Busca artigos reais para o tópico combinando múltiplas APIs gratuitas.

    Roda todos os providers ativos em paralelo, mescla resultados,
    remove duplicatas (DOI/título) e retorna até max_results artigos
    válidos (com título E link).

    Providers ativos: Crossref, OpenAlex, arXiv, Core.ac.uk (se CORE_API_KEY setada),
    Semantic Scholar, IEEE Xplore, Google Scholar.
    """
    from .ieee import search_ieee as _search_ieee_provider
    from .serpapi import search_google_scholar as _search_google_scholar

    per_provider = max(3, max_results * 2)
    providers: list[tuple[str, Any]] = [
        ("crossref", _search_crossref),
        ("openalex", _search_openalex),
        ("arxiv", _search_arxiv),
    ]
    if _CORE_API_KEY:
        providers.append(("core", _search_core))
    if os.getenv("SEMANTIC_SCHOLAR_API_KEY", "").strip():
        providers.append(("semantic_scholar", _search_semantic_scholar))
    if os.getenv("IEEE_API_KEY", "").strip():
        providers.append(("ieee", _search_ieee_provider))
    if os.getenv("SERPAPI_API_KEY", "").strip():
        providers.append(("google_scholar", _search_google_scholar))

    collected: list[Article] = []

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

    deduped = _dedup_articles(collected)
    deduped = _enrich_with_unpaywall(deduped, timeout)
    valid = [a for a in deduped if a.is_valid()]
    return valid[:max_results]
