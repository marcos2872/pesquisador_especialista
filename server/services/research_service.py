"""
Serviço de pesquisa — orquestra busca de fontes e geração de relatório.

Este é o módulo central da aplicação. O fluxo é:

  1. Coleta fontes reais via APIs acadêmicas (source_collector)
  2. Envia tópico + contexto de fontes para a IA (ai_service)
  3. Valida qualidade da resposta da IA
  4. Valida estrutura de seções obrigatórias
  5. Valida e sanitiza os links do relatório (report_service)
  6. Valida citações literais contra trechos extraídos (fetcher)
  7. Valida distribuição de fontes entre seções
  8. Se poucas fontes válidas, faz uma segunda tentativa (retry)
  9. Retorna o relatório final em Markdown

Cada serviço é recebido como argumento opcional (injeção de dependência
manual) para facilitar testes com mocks.
"""

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as _TimeoutError

from .ai_service import call_openai
from .report_service import sanitize_report_links
from .source_collector import _collect_real_sources
from .source_service import (
    count_unique_sources,
    validate_ai_response_quality,
    validate_report_sections,
    validate_report_sources,
    validate_section_min_sources,
)

MIN_UNIQUE_SOURCES = 3
PIPELINE_TIMEOUT_SECONDS = 300


def _validate_quoted_citations(
    report: str,
    snippets_map: dict[str, list[str]],
) -> str:
    """
    Verifica se as citações literais (entre aspas) existem nos snippets.

    Usa validate_quoted_citations do módulo fetcher para cruzar cada
    citação contra os trechos extraídos das fontes.

    Se mais de 50% das citações não forem verificadas, lança RuntimeError
    para forçar uma regeneração do relatório.

    Args:
        report: Relatório em Markdown
        snippets_map: dict mapping URL -> lista de trechos extraídos

    Returns:
        Relatório com citações não verificadas sanitizadas, ou o original
        se o módulo fetcher não estiver disponível.
    """
    if not snippets_map:
        return report
    try:
        from server.utils.fetcher import validate_quoted_citations

        sanitized, warnings = validate_quoted_citations(report, snippets_map)
        if warnings:
            total_quotes = report.count('"') // 2
            if total_quotes > 0 and len(warnings) > total_quotes * 0.5:
                raise RuntimeError(
                    "Mais de 50% das citações literais não foram verificadas "
                    "nos trechos extraídos das fontes."
                )
            return sanitized
    except RuntimeError:
        raise
    except Exception:
        pass
    return report


def _generate_report_impl(
    topic: str,
    ai_service=None,
    source_collector=None,
    sanitizer=None,
    prompt_template: str = "",
) -> str:
    """
    Executa o pipeline completo de geração de relatório.

    Etapas:
      1. Coleta fontes reais via source_collector
      2. Extrai URLs coletadas para validação posterior
      3. Chama AI para gerar o relatório (com retry se necessário)
      4. Valida qualidade, seções e fontes do relatório
      5. Sanitiza os links (remove links inválidos/irrelevantes)
      6. Valida citações literais contra snippets
      7. Se fontes < MIN_UNIQUE_SOURCES, tenta novamente com prompt mais rigoroso
      8. Se seções técnicas sem fontes, tenta novamente

    Args:
        topic: Tópico da pesquisa
        ai_service: Função para chamar a IA (default: call_openai)
        source_collector: Função para coletar fontes (default: _collect_real_sources)
        sanitizer: Função para sanitizar links (default: sanitize_report_links)
        prompt_template: Template de system prompt (opcional)

    Returns:
        Relatório final em Markdown com avisos de validação (se houver)
    """
    if ai_service is None:
        ai_service = call_openai
    if source_collector is None:
        source_collector = _collect_real_sources
    if sanitizer is None:
        sanitizer = sanitize_report_links

    sources_context, snippets_map = source_collector(topic)

    collected_urls: set[str] = set()
    for line in sources_context.splitlines():
        if line.strip().startswith("URL:") or line.strip().startswith("Link:"):
            url = line.split(":", 1)[1].strip()
            if url.startswith("http"):
                collected_urls.add(url)
        if line.strip().startswith("DOI:"):
            doi_value = line.split(":", 1)[1].strip()
            if doi_value.startswith("http"):
                collected_urls.add(doi_value)
            elif doi_value:
                collected_urls.add(f"https://doi.org/{doi_value}")

    def _try_generate(retry: bool = False) -> tuple[str, list[str], list[str]]:
        report = ai_service(
            topic,
            sources_context=sources_context,
            retry=retry,
            prompt_template=prompt_template,
        )

        validate_ai_response_quality(report)

        validate_report_sections(report)

        validate_report_sources(report)

        sanitized, removed = sanitizer(report, topic, collected_urls=collected_urls)

        if snippets_map:
            sanitized = _validate_quoted_citations(sanitized, snippets_map)

        return sanitized, removed, []

    sanitized_report, removed, _ = _try_generate(retry=False)

    has_real_sources = bool(sources_context.strip())
    if has_real_sources and count_unique_sources(sanitized_report) < MIN_UNIQUE_SOURCES:
        sanitized_report, removed, _ = _try_generate(retry=True)

    if has_real_sources and count_unique_sources(sanitized_report) < MIN_UNIQUE_SOURCES:
        raise RuntimeError(
            "A resposta trouxe poucas fontes que puderam ser verificadas como reais e relevantes. "
            f"Use pelo menos {MIN_UNIQUE_SOURCES} fontes distintas e confiáveis, "
            "ou integre uma ferramenta de busca real (ex.: Crossref, SerpAPI) para obter referências verificadas."
        )

    try:
        validate_section_min_sources(sanitized_report, min_per_section=1)
    except RuntimeError:
        if has_real_sources:
            sanitized_report, removed, _ = _try_generate(retry=True)

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


def generate_report(
    topic: str,
    ai_service=None,
    source_collector=None,
    sanitizer=None,
    prompt_template: str = "",
) -> str:
    """
    Gera relatório de pesquisa com timeout global no pipeline.

    Encapsula _generate_report_impl em uma ThreadPoolExecutor com
    timeout de PIPELINE_TIMEOUT_SECONDS segundos para evitar que
    chamadas externas (APIs de busca, OpenAI) pendurem o servidor.

    Args:
        topic: Tópico da pesquisa
        ai_service: Função para chamar a IA (default: call_openai)
        source_collector: Função para coletar fontes (default: _collect_real_sources)
        sanitizer: Função para sanitizar links (default: sanitize_report_links)
        prompt_template: Template de system prompt (opcional)

    Returns:
        Relatório final em Markdown

    Raises:
        RuntimeError: Se o tempo limite for excedido
    """
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(
        _generate_report_impl,
        topic,
        ai_service=ai_service,
        source_collector=source_collector,
        sanitizer=sanitizer,
        prompt_template=prompt_template,
    )
    try:
        return future.result(timeout=PIPELINE_TIMEOUT_SECONDS)
    except _TimeoutError:
        raise RuntimeError(
            f"Tempo limite de {PIPELINE_TIMEOUT_SECONDS}s excedido "
            "na geração do relatório."
        )
