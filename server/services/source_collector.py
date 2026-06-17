"""Serviço de coleta de fontes reais via APIs acadêmicas."""

import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

# Importa os módulos de busca (assumindo que existem em utils.search)
# Se não existirem, esta função retornará empty context
try:
    from server.utils.fetcher import download_source_texts, generate_query_variants
    from server.utils.search.academic import search_articles
    from server.utils.search.patents import search_patents
    from server.utils.search.prompt_enrichment import build_sources_context

    HAS_SEARCH_MODULES = True
except ImportError:
    HAS_SEARCH_MODULES = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=__import__("sys").stderr,
)
logger = logging.getLogger("pesquisador")


def _collect_real_sources(topic: str) -> tuple[str, dict[str, list[str]]]:
    """
    Coleta fontes reais via APIs gratuitas, baixa textos e extrai snippets.

    Returns:
        (sources_context, snippets_map): contexto formatado e mapa url->snippets.
    """
    if os.getenv("ENABLE_REAL_SEARCH", "1") == "0":
        return "", {}

    # Se os módulos de busca não existirem, retorna contexto vazio
    if not HAS_SEARCH_MODULES:
        logger.info(
            "Módulos de busca não encontrados. Retornando contexto vazio para o tópico '%s'",
            topic,
        )
        return "", {}

    # Expande o tópico em múltiplas queries (EN + PT + variantes)
    queries = generate_query_variants(topic)
    logger.info("Buscando com %d queries: %s", len(queries), queries[:5])

    all_articles: list = []
    all_patents: list = []

    query_delay = float(os.getenv("SEARCH_QUERY_DELAY_SECONDS", "1.0"))
    for i, query in enumerate(queries[:5]):  # Usa até 5 queries para melhor cobertura
        if i > 0 and query_delay > 0:
            time.sleep(query_delay)  # Delay entre queries para evitar rate limits
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_art = executor.submit(
                search_articles, query, max_results=5, timeout=15
            )
            future_pat = executor.submit(
                search_patents, query, max_results=3, timeout=15
            )

            try:
                all_articles.extend(future_art.result())
            except Exception as exc:
                logger.warning("Falha na busca de artigos para '%s': %s", query, exc)

            try:
                all_patents.extend(future_pat.result())
            except Exception as exc:
                logger.warning("Falha na busca de patentes para '%s': %s", query, exc)

    if not all_articles and not all_patents:
        logger.info("Nenhuma fonte real encontrada para o tópico '%s'", topic)
        return "", {}

    # Baixa PDFs e extrai snippets das fontes encontradas
    sources_for_download: list[dict] = []
    for a in all_articles:
        entry = {
            "title": a.title,
            "url": a.url,
            "pdf_url": getattr(a, "pdf_url", None),
            "doi": getattr(a, "doi", None),
        }
        sources_for_download.append(entry)
    for p in all_patents:
        entry = {
            "title": p.title,
            "url": p.url,
            "pdf_url": None,
            "doi": None,
        }
        sources_for_download.append(entry)

    logger.info(
        "Baixando PDFs e extraindo snippets de %d fontes...", len(sources_for_download)
    )
    enriched = download_source_texts(
        sources_for_download, topic, timeout=20, max_workers=3
    )

    # Constrói o mapa de snippets: url -> lista de trechos
    snippets_map: dict[str, list[str]] = {}
    for src in enriched:
        url = src.get("url") or ""
        if url and src.get("snippets"):
            snippets_map[url] = src["snippets"]

    total_snippets = sum(len(v) for v in snippets_map.values())
    logger.info(
        "%d fontes encontradas, %d trechos extraídos para citação literal",
        len(enriched),
        total_snippets,
    )

    context = (
        build_sources_context(all_articles, all_patents, snippets_map=snippets_map)
        or ""
    )
    return context, snippets_map
