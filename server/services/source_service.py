"""
Serviço de validação de fontes.

Contém heurísticas para:
  - Detectar URLs de busca/homepage (que não são fontes primárias)
  - Verificar se uma URL parece ser de artigo ou patente real
  - Validar que o relatório da IA contém links de fontes primárias
  - Contar fontes únicas citadas no relatório

Usamos análise de URL puramente textual (parsing de path e host) para
evitar fazer requisições HTTP em cada validação.
"""

import re
from urllib.parse import parse_qs, urlparse

MARKDOWN_LINK_PATTERN = re.compile(r"\[[^\]]+\]\((https?://[^)\s]+)\)")

# Parâmetros de query que indicam página de busca (não fonte direta)
SEARCH_QUERY_KEYS = {"q", "query", "search", "keyword", "keywords", "term"}


def _is_search_or_home_url(url: str) -> bool:
    """
    Verifica se URL é de página de busca/homepage (não fonte primária).

    Heurísticas:
      - Path vazio (raiz do site) → homepage
      - Path contendo /search, /scholar, /results → busca
      - scholar.google.com → sempre busca
      - Query string com parâmetros de busca sem path de documento → busca
    """
    parsed = urlparse(url)
    path = parsed.path or "/"
    normalized_path = path.rstrip("/")
    lower_path = normalized_path.lower()
    lower_host = parsed.netloc.lower()
    query_keys = {key.lower() for key in parse_qs(parsed.query).keys()}

    if normalized_path in ("",):
        return True
    if any(
        token in lower_path for token in ("/search", "/scholar", "/results", "/query")
    ):
        return True
    if lower_host == "scholar.google.com":
        return True
    if query_keys & SEARCH_QUERY_KEYS and not any(
        token in lower_path
        for token in (
            "/article",
            "/doi",
            "/patent",
            "/document",
            "/pdf",
        )
    ):
        return True
    return False


def _looks_like_primary_source(url: str) -> bool:
    """
    Verifica se URL parece ser de fonte primária (artigo/patente).

    Heurísticas:
      - Contém doi.org/ → é DOI, sempre fonte primária
      - Path contém /article, /doi, /abs, /full, /pdf, /patent, /document
      - Domínio de patente conhecido com path não vazio
    """
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    if "doi.org/" in url.lower():
        return True
    if any(
        token in path
        for token in (
            "/article",
            "/doi",
            "/abs",
            "/full",
            "/pdf",
            "/patent",
            "/document",
        )
    ):
        return True
    if host in {
        "patents.google.com",
        "worldwide.espacenet.com",
        "patentscope.wipo.int",
    } and path.strip("/"):
        return True
    return False


def validate_report_sources(report: str) -> None:
    """
    Valida se o relatório contém links de fontes primárias.

    Lança RuntimeError se:
      - Não houver links nenhum
      - Nenhum link for de fonte primária (ex.: só links de busca/homepage)
    """
    urls = MARKDOWN_LINK_PATTERN.findall(report)
    if not urls:
        raise RuntimeError(
            "A resposta não trouxe links de fontes. "
            "Exija links diretos de artigos/patentes citados."
        )

    if not any(_looks_like_primary_source(url) for url in urls):
        raise RuntimeError(
            "A resposta não trouxe links diretos de artigo/documento/patente. "
            "Inclua DOI ou URL do documento final."
        )


def count_unique_sources(report: str) -> int:
    """
    Conta quantidade de fontes únicas no relatório.

    Considera:
      - URLs únicas (case-insensitive) extraídas de links Markdown
      - Marcações "[fonte não verificada]" como fontes (são links que
        existiam mas foram removidos pela sanitização)
    """
    urls = MARKDOWN_LINK_PATTERN.findall(report)
    unique_urls = {url.lower() for url in urls}
    unverified_count = len(
        re.findall(r"\[fonte não verificada\]", report, re.IGNORECASE)
    )
    return len(unique_urls) + unverified_count
