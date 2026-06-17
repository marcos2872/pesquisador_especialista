"""
Serviço de sanitização de relatórios gerados pela IA.

A IA pode inventar URLs, DOIs e números de patente (alucinação). Este
módulo valida cada link do relatório Markdown gerado, removendo ou
substituindo aqueles que não puderem ser verificados como fontes reais
e relevantes ao tema.

Estratégia:
  1. URLs vindas do contexto de fontes coletadas (collected_urls) são
     pré-aprovadas — já passaram pela verificação na busca acadêmica.
  2. URLs não coletadas são validadas em tempo real via Crossref (para
     DOIs) ou por download e análise de conteúdo.
  3. Links inválidos são substituídos por "[fonte não verificada]" e a
     seção de referências é reconstruída apenas com links válidos.
"""

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

    Args:
        report: Relatório Markdown gerado pela IA
        topic: Tópico da pesquisa (para validar relevância)
        url_validator: Função de validação (padrão: validate_url_relevance)
        collected_urls: URLs de fontes reais coletadas (pré-aprovadas)

    Returns:
        (relatório sanitizado, lista de URLs removidas)
    """
    if url_validator is None:
        url_validator = validate_url_relevance
    if collected_urls is None:
        collected_urls = set()

    # Remove marcações genéricas do sistema
    report = re.sub(r"\[sem validação externa\]", "", report, flags=re.IGNORECASE)

    links = list(dict.fromkeys(MARKDOWN_LINK_PATTERN.findall(report)))
    if not links:
        return report, []

    valid_urls: set = set()
    removed: list = []

    for text, url in links:
        # Filtra URLs de homepages/buscas (não são fontes primárias)
        if _is_search_or_home_url(url):
            removed.append(f"{url} (link de busca/homepage)")
            continue

        # URLs coletadas na busca são pré-aprovadas — já foram verificadas
        if url in collected_urls:
            valid_urls.add(url)
            continue

        # URLs não coletadas (possivelmente inventadas pela IA) são validadas agora
        is_valid, reason = url_validator(url, topic, timeout=15)
        if is_valid:
            valid_urls.add(url)
        else:
            removed.append(f"{url} ({reason})")

    if not removed:
        return report, []

    # Substitui links inválidos por '[fonte não verificada]' (mantém o texto visível)
    sanitized = report
    for text, url in links:
        if url not in valid_urls:
            sanitized = re.sub(
                rf"\[([^\]]+)\]\(\s*{re.escape(url)}\s*\)",
                r"[\1] [fonte não verificada]",
                sanitized,
            )

    # Reconstrói a seção 6 apenas com fontes válidas
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
