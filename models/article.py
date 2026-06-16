#!/usr/bin/env python3
"""Modelo de dados para artigos acadêmicos."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Article:
    title: str
    authors: list[str] = field(default_factory=list)
    year: Optional[int] = None
    venue: Optional[str] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    abstract: Optional[str] = None
    pdf_url: Optional[str] = None
    source_api: str = "unknown"

    def is_valid(self) -> bool:
        return bool(self.title and (self.doi or self.url))

    def short_citation(self) -> str:
        authors = (
            ", ".join(self.authors[:3]) if self.authors else "Autores não listados"
        )
        if len(self.authors) > 3:
            authors += " et al."
        venue = f" ({self.venue})" if self.venue else ""
        year = f", {self.year}" if self.year else ""
        link = self.url or (f"https://doi.org/{self.doi}" if self.doi else "sem link")
        return f"{authors}{year}{venue} — {self.title} — {link}"
