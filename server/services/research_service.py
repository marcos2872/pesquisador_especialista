"""
Serviço de pesquisa — orquestra busca de fontes e geração de relatório.

Este é o módulo central da aplicação. O fluxo é:

  1. Coleta fontes reais via APIs acadêmicas (source_collector)
  2. Envia tópico + contexto de fontes para a IA (ai_service)
  3. Valida e sanitiza os links do relatório (report_service)
  4. Se poucas fontes válidas, faz uma segunda tentativa (retry)
  5. Retorna o relatório final em Markdown

Cada serviço é recebido como argumento opcional (injeção de dependência
manual) para facilitar testes com mocks.
"""

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
        ai_service: Função que chama a OpenAI (call_openai)
        source_collector: Função que coleta fontes reais
        sanitizer: Função que sanitiza links do relatório
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

    # Passo 1: Coleta fontes reais de artigos e patentes
    sources_context, snippets_map = source_collector(topic)

    # Passo 1.5: Extrai URLs das fontes coletadas para usar como whitelist
    # na sanitização — URLs verificadas são pré-aprovadas.
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
        """Tenta uma geração: IA → validação → sanitização."""
        report = ai_service(
            topic,
            sources_context=sources_context,
            retry=retry,
            prompt_template=prompt_template,
        )
        validate_report_sources(report)
        sanitized, removed = sanitizer(report, topic, collected_urls=collected_urls)
        return sanitized, removed, []

    # Passo 2: Geração inicial
    sanitized_report, removed, _ = _try_generate(retry=False)

    # Passo 3: Se encontrou poucas fontes verificáveis, tenta com retry
    # O retry usa um prompt mais rigoroso instruindo o modelo a ser mais
    # conservador ao citar fontes.
    # Só reprova se havia fontes reais para citar — se o contexto estava
    # vazio, a IA não tinha fontes para usar e não faz sentido punir.
    has_real_sources = bool(sources_context.strip())
    if has_real_sources and count_unique_sources(sanitized_report) < MIN_UNIQUE_SOURCES:
        sanitized_report, removed, _ = _try_generate(retry=True)

    # Se mesmo com retry não atingiu o mínimo, levanta erro
    if has_real_sources and count_unique_sources(sanitized_report) < MIN_UNIQUE_SOURCES:
        raise RuntimeError(
            "A resposta trouxe poucas fontes que puderam ser verificadas como reais e relevantes. "
            f"Use pelo menos {MIN_UNIQUE_SOURCES} fontes distintas e confiáveis, "
            "ou integre uma ferramenta de busca real (ex.: Crossref, SerpAPI) para obter referências verificadas."
        )

    # Passo 4: Adiciona avisos no topo se links foram removidos
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
