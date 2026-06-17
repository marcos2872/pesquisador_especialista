#!/usr/bin/env python3
"""
Modelo de dados para patentes.

Cada Patent representa um documento de patente encontrado em APIs como
Espacenet (EPO), USPTO, Lens.org, WIPO Patentscope ou Google Patents.

O campo jurisdiction indica o país/escritório (US, EP, WO, BR, etc.) e
o campo number armazena o número de publicação completo (ex.: US12345678A1).
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Patent:
    title: str
    number: str                 # Número de publicação (ex.: US12345678A1)
    url: str                    # Link direto para a patente
    year: Optional[int] = None
    inventors: list[str] = field(default_factory=list)
    assignee: Optional[str] = None   # Titular/depositante
    abstract: Optional[str] = None
    jurisdiction: str = "US"         # Código do escritório (US, EP, WO, etc.)
    source_api: str = "unknown"      # Provider que retornou o registro

    def is_valid(self) -> bool:
        """Patente válida precisa de título, número e URL — todos obrigatórios."""
        return bool(self.title and self.number and self.url)

    def short_citation(self) -> str:
        """Formata a patente para citação inline."""
        inventors = (
            ", ".join(self.inventors[:2])
            if self.inventors
            else "Inventores não listados"
        )
        if len(self.inventors) > 2:
            inventors += " et al."
        year = f" ({self.year})" if self.year else ""
        return f"{inventors}{year} — {self.title} — {self.number} — {self.url}"
