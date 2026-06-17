#!/usr/bin/env python3
"""Modelo de dados para patentes."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Patent:
    title: str
    number: str
    url: str
    year: Optional[int] = None
    inventors: list[str] = field(default_factory=list)
    assignee: Optional[str] = None
    abstract: Optional[str] = None
    jurisdiction: str = "US"
    source_api: str = "unknown"

    def is_valid(self) -> bool:
        return bool(self.title and self.number and self.url)

    def short_citation(self) -> str:
        inventors = (
            ", ".join(self.inventors[:2])
            if self.inventors
            else "Inventores não listados"
        )
        if len(self.inventors) > 2:
            inventors += " et al."
        year = f" ({self.year})" if self.year else ""
        return f"{inventors}{year} — {self.title} — {self.number} — {self.url}"
