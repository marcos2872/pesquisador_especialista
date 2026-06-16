"""Serviço de pesquisa - orquestra busca de fontes e geração de relatório."""

from .ai_service import call_openai
from .report_service import sanitize_report_links
from .source_collector import _collect_real_sources
from .source_service import count_unique_sources, validate_report_sources

MIN_UNIQUE_SOURCES = 3


def generate_report(
    topic: str,
    ai_service=None,
    source_collector=None,
    sanitizer=None,
    prompt_template: str = "",
) -> str:
    """
    Gera relatório de pesquisa orquestrando os serviços de IA e fontes.

    Args:
        topic: Tópico da pesquisa
        ai_service: Serviço de IA (call_openai)
        source_collector: Coletor de fontes (_collect_real_sources)
        sanitizer: Sanitizador de links (sanitize_report_links)
        prompt_template: Template do prompt de sistema

    Returns:
        Relatório sanitizado em Markdown
    """
    if ai_service is None:
        ai_service = call_openai
    if source_collector is None:
        source_collector = _collect_real_sources
    if sanitizer is None:
        sanitizer = sanitize_report_links

    # Coleta fontes reais
    sources_context, snippets_map = source_collector(topic)

    def _try_generate(retry: bool = False) -> tuple[str, list[str], list[str]]:
        report = ai_service(
            topic,
            sources_context=sources_context,
            retry=retry,
            prompt_template=prompt_template,
        )
        validate_report_sources(report)
        sanitized, removed = sanitizer(report, topic)
        return sanitized, removed, []

    sanitized_report, removed, _ = _try_generate(retry=False)

    if count_unique_sources(sanitized_report) < MIN_UNIQUE_SOURCES:
        sanitized_report, removed, _ = _try_generate(retry=True)

    if count_unique_sources(sanitized_report) < MIN_UNIQUE_SOURCES:
        raise RuntimeError(
            "A resposta trouxe poucas fontes que puderam ser verificadas como reais e relevantes. "
            f"Use pelo menos {MIN_UNIQUE_SOURCES} fontes distintas e confiáveis, "
            "ou integre uma ferramenta de busca real (ex.: Crossref, SerpAPI) para obter referências verificadas."
        )

    # Monta avisos
    warnings: list = []
    if removed:
        warnings.append(
            "> **Aviso de validação de fontes:** alguns links gerados pelo modelo "
            "não foram confirmados como válidos ou relevantes ao tema e foram "
            "substituídos por `[fonte não verificada]`. "
            "Recomenda-se revisão manual das referências."
        )

    if warnings:
        sanitized_report = "\n\n".join(warnings) + "\n\n" + sanitized_report

    return sanitized_report
