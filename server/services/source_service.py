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


REQUIRED_SECTION_HEADINGS = [
    "## 1. Estado da arte",
    "## 2. Pesquisa de anterioridade",
    "## 3. Tabela comparativa",
    "## 4. Lacunas e oportunidades",
    "## 5. Conclusão",
    "## 6. Referências",
]


def validate_report_sections(report: str) -> None:
    """
    Verifica se o relatório contém todas as 6 seções obrigatórias.

    As seções esperadas são definidas em REQUIRED_SECTION_HEADINGS:
      1. Estado da arte
      2. Pesquisa de anterioridade
      3. Tabela comparativa
      4. Lacunas e oportunidades
      5. Conclusão
      6. Referências

    Lança RuntimeError se alguma seção estiver ausente.
    """
    missing = [s for s in REQUIRED_SECTION_HEADINGS if s not in report]
    if missing:
        raise RuntimeError(
            "Relatório não contém as seções obrigatórias: "
            + ", ".join(missing)
        )


def count_sources_per_section(report: str) -> dict[str, int]:
    """
    Conta quantas fontes (links) existem em cada seção do relatório.

    Divide o relatório pelos headings ## N. e extrai os links Markdown
    de cada bloco usando MARKDOWN_LINK_PATTERN.

    Returns:
        dict com heading como chave e contagem de links como valor.
    """
    sections = re.split(r'\n(?=## \d+\.)', report)
    counts: dict[str, int] = {}
    for section in sections:
        header_match = re.match(r'## (\d+\..+)', section.strip())
        if not header_match:
            continue
        header = header_match.group(1).strip()
        urls = MARKDOWN_LINK_PATTERN.findall(section)
        counts[header] = len(urls)
    return counts


def validate_section_min_sources(report: str, min_per_section: int = 1) -> None:
    """
    Verifica se cada seção técnica tem pelo menos min_per_section fontes.

    Seção "Referências" não entra na validação, pois links ali são opcionais.

    Lança RuntimeError se 2 ou mais seções técnicas estiverem abaixo do mínimo.
    """
    counts = count_sources_per_section(report)
    empty_sections = [
        header
        for header, count in counts.items()
        if count < min_per_section and "Referências" not in header
    ]
    if len(empty_sections) >= 2:
        raise RuntimeError(
            f"Seções sem fontes suficientes: {', '.join(empty_sections)}. "
            "Cada seção técnica deve ter pelo menos 1 fonte citada."
        )


def validate_ai_response_quality(report: str) -> None:
    """
    Valida qualidade básica da resposta da IA antes de prosseguir.

    Verificações:
      - Tamanho mínimo de 200 caracteres
      - Pelo menos 3 headings Markdown (##)
      - Ausência da marcação "[sem validação externa]" (proibida)
      - Parágrafos não-repetitivos (similaridade < 60% entre trechos)

    Lança RuntimeError na primeira violação encontrada.
    """
    if len(report) < 200:
        raise RuntimeError(
            "Relatório gerado é muito curto (menos de 200 caracteres)."
        )

    heading_count = report.count("## ")
    if heading_count < 3:
        raise RuntimeError(
            "Relatório não possui estrutura markdown mínima "
            f"(apenas {heading_count} headings encontrados)."
        )

    if "[sem validação externa]" in report:
        raise RuntimeError(
            "Relatório contém marcação '[sem validação externa]', "
            "que é proibida. A IA deve omitir afirmações sem fonte."
        )

    paragraphs = [p for p in report.split("\n\n") if p.strip()]
    if len(paragraphs) >= 4:
        unique_paras = set(p[:100] for p in paragraphs)
        if len(unique_paras) < len(paragraphs) * 0.4:
            raise RuntimeError(
                "Relatório contém conteúdo repetitivo "
                "(parágrafos muito similares entre si)."
            )
