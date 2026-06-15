#!/usr/bin/env python3
"""
Formata fontes reais (artigos e patentes) em um trecho de contexto estruturado
para ser injetado no prompt do modelo. O objetivo e fornecer ao LLM referencias
verificaveis e reduzir a alucinacao de DOIs e numeros de patente.
"""

import os
from typing import Optional

from .academic import Article
from .patents import Patent

DEFAULT_MAX_ARTICLES = int(os.getenv("SOURCES_MAX_ARTICLES", "5"))
DEFAULT_MAX_PATENTS = int(os.getenv("SOURCES_MAX_PATENTS", "3"))
DEFAULT_MAX_ABSTRACT_CHARS = int(os.getenv("SOURCES_MAX_ABSTRACT_CHARS", "600"))


def _format_article(article: Article, max_abstract: int) -> str:
    lines = []
    title = article.title.strip() or "(sem título)"
    lines.append(f"- Título: {title}")
    if article.authors:
        authors = ", ".join(article.authors[:3])
        if len(article.authors) > 3:
            authors += " et al."
        lines.append(f"  Autores: {authors}")
    if article.year:
        lines.append(f"  Ano: {article.year}")
    if article.venue:
        lines.append(f"  Publicação: {article.venue}")
    if article.doi:
        lines.append(f"  DOI: https://doi.org/{article.doi}")
    if article.url and (not article.doi or article.url != f"https://doi.org/{article.doi}"):
        lines.append(f"  URL: {article.url}")
    if article.abstract:
        abstract = article.abstract.strip().replace("\n", " ")
        if len(abstract) > max_abstract:
            abstract = abstract[: max_abstract - 1].rstrip() + "…"
        lines.append(f"  Resumo: {abstract}")
    return "\n".join(lines)


def _format_patent(patent: Patent) -> str:
    lines = []
    title = patent.title.strip() or "(sem título)"
    lines.append(f"- Título: {title}")
    if patent.inventors:
        inventors = ", ".join(patent.inventors[:3])
        if len(patent.inventors) > 3:
            inventors += " et al."
        lines.append(f"  Inventores: {inventors}")
    if patent.assignee:
        lines.append(f"  Titular: {patent.assignee}")
    if patent.year:
        lines.append(f"  Ano: {patent.year}")
    lines.append(f"  Número: {patent.number}")
    lines.append(f"  Jurisdição: {patent.jurisdiction}")
    lines.append(f"  Link: {patent.url}")
    if patent.abstract:
        lines.append(f"  Resumo: {patent.abstract}")
    return "\n".join(lines)


def build_sources_context(
    articles: list[Article],
    patents: list[Patent],
    max_articles: int = DEFAULT_MAX_ARTICLES,
    max_patents: int = DEFAULT_MAX_PATENTS,
    max_abstract_chars: int = DEFAULT_MAX_ABSTRACT_CHARS,
) -> Optional[str]:
    """
    Constroi o bloco de contexto a partir de artigos e patentes reais.

    Retorna None se nao houver fonte alguma, ou string formatada com instrucoes
    para o modelo usar SOMENTE essas fontes.
    """
    articles = [a for a in articles if a.is_valid()][:max_articles]
    patents = [p for p in patents if p.is_valid()][:max_patents]

    if not articles and not patents:
        return None

    sections: list[str] = [
        "FONTS VERIFICADAS (use SOMENTE estas fontes para citar):",
        "Não invente, modifique ou adicione DOIs, números de patente ou URLs.",
        "Se uma afirmação não puder ser sustentada por estas fontes, omita a afirmação.",
    ]

    if articles:
        sections.append("\nARTIGOS:")
        for i, article in enumerate(articles, 1):
            sections.append(f"\n[{i}]")
            sections.append(_format_article(article, max_abstract_chars))

    if patents:
        sections.append("\n\nPATENTES:")
        for i, patent in enumerate(patents, 1):
            sections.append(f"\n[{i}]")
            sections.append(_format_patent(patent))

    return "\n".join(sections)
