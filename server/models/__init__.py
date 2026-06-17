"""
Modelos de dados da plataforma.

Usamos dataclasses (stdlib) em vez de Pydantic/Ormar para manter zero
dependências de framework. Cada modelo representa uma entidade do domínio
(Artigo acadêmico, Patente) com métodos auxiliares para validação e
formatação de citação.
"""

from server.models.article import Article
from server.models.patent import Patent

__all__ = ["Article", "Patent"]
