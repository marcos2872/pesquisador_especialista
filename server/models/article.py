#!/usr/bin/env python3
"""
Modelo de dados para artigos acadêmicos.

Cada Article representa um artigo real encontrado durante a busca em APIs
como Crossref, OpenAlex, arXiv, etc. O campo source_api guarda qual
provedor originou o registro, útil para auditoria e debug.

is_valid() garante que só artigos com título E pelo menos um link (DOI/URL)
sejam considerados válidos — isso filtra registros incompletos das APIs.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Article:
    title: str
    authors: list[str] = field(default_factory=list)
    year: Optional[int] = None
    venue: Optional[str] = None          # Periódico ou conferência
    doi: Optional[str] = None            # DOI sem o prefixo https://doi.org/
    url: Optional[str] = None            # Landing page do artigo
    abstract: Optional[str] = None
    pdf_url: Optional[str] = None        # Link direto para PDF (via Unpaywall, arXiv)
    source_api: str = "unknown"           # Nome do provider que retornou o dado

    def is_valid(self) -> bool:
        """Um artigo é válido se tem título e ao menos um identificador (DOI ou URL)."""
        return bool(self.title and (self.doi or self.url))

    def short_citation(self) -> str:
        """Formata o artigo como uma citação curta no padrão ABNT simplificado."""
        authors = (
            ", ".join(self.authors[:3]) if self.authors else "Autores não listados"
        )
        if len(self.authors) > 3:
            authors += " et al."
        venue = f" ({self.venue})" if self.venue else ""
        year = f", {self.year}" if self.year else ""
        link = self.url or (f"https://doi.org/{self.doi}" if self.doi else "sem link")
        return f"{authors}{year}{venue} — {self.title} — {link}"
