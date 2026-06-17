"""Serviço de geração e sanitização de relatórios."""

import re

from server.services.source_service import _is_search_or_home_url
from server.utils.fetcher import validate_quoted_citations, validate_url_relevance

MIN_UNIQUE_SOURCES = 3

# Padrão para extrair links Markdown: [texto](url)  → retorna (texto, url)
MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def sanitize_report_links(
    report: str, topic: str, url_validator=None, collected_urls: set[str] | None = None
) -> tuple[str, list[str]]:
    """
    Sanitiza links do relatório, removendo/substituindo URLs inválidas ou irrelevantes.

    URLs que vieram do contexto de fontes coletadas (collected_urls) são pré-aprovadas
    — já foram verificadas durante a busca acadêmica.

    Returns:
        (sanitized_report, removed_urls)
    """
    if url_validator is None:
        url_validator = validate_url_relevance
    if collected_urls is None:
        collected_urls = set()

    report = re.sub(r"\[sem validação externa\]", "", report, flags=re.IGNORECASE)

    links = list(dict.fromkeys(MARKDOWN_LINK_PATTERN.findall(report)))
    if not links:
        return report, []

    valid_urls: set = set()
    removed: list = []

    for text, url in links:
        if _is_search_or_home_url(url):
            removed.append(f"{url} (link de busca/homepage)")
            continue

        # URLs coletadas na busca são pré-aprovadas — já foram verificadas
        if url in collected_urls:
            valid_urls.add(url)
            continue

        # Para URLs não coletadas (possivelmente inventadas pela IA), faz validação completa
        is_valid, reason = url_validator(url, topic, timeout=15)
        if is_valid:
            valid_urls.add(url)
        else:
            removed.append(f"{url} ({reason})")

    if not removed:
        return report, []

    # Substitui links inválidos por '[fonte não verificada]'
    sanitized = report
    for text, url in links:
        if url not in valid_urls:
            sanitized = re.sub(
                rf"\[([^\]]+)\]\(\s*{re.escape(url)}\s*\)",
                r"[\1] [fonte não verificada]",
                sanitized,
            )

    # Remove seção 6 de referências anterior
    reference_header_pattern = re.compile(
        r"\n##\s+6\.\s+Referências.*$", re.IGNORECASE | re.DOTALL
    )
    sanitized = reference_header_pattern.sub("", sanitized)
    sanitized = sanitized.rstrip()

    if valid_urls:
        sanitized += "\n\n## 6. Referências utilizadas (links verificados)\n\n"
        sanitized += "\n".join(f"- {url}" for url in sorted(valid_urls))
    else:
        sanitized += (
            "\n\n## 6. Referências utilizadas\n\n"
            "_Nenhuma das fontes citadas pôde ser verificada automaticamente. "
            "Recomenda-se busca manual em bases confiáveis._"
        )

    return sanitized, removed
