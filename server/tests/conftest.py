"""
Fixtures e helpers compartilhados pelos testes.

PROJECT_ROOT é adicionado ao sys.path para que os imports absolutos
(server.models, server.services, etc.) funcionem nos testes sem
depender de instalação via pip.
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def mock_crossref_response():
    return {
        "status": "ok",
        "message": {
            "total-results": 2,
            "items": [
                {
                    "DOI": "10.1234/test.001",
                    "title": ["Test Article One"],
                    "author": [
                        {"given": "Alice", "family": "Smith"},
                        {"given": "Bob", "family": "Jones"},
                    ],
                    "container-title": ["Journal of Tests"],
                    "published-print": {"date-parts": [[2021]]},
                    "abstract": "Test abstract for article one.",
                },
                {
                    "DOI": "10.1234/test.002",
                    "title": ["Test Article Two"],
                    "author": [{"given": "Carol", "family": "White"}],
                    "container-title": ["Another Journal"],
                    "published-print": {"date-parts": [[2022]]},
                    "abstract": None,
                },
            ],
        },
    }


@pytest.fixture
def mock_openalex_response():
    return {
        "meta": {"count": 1},
        "results": [
            {
                "id": "https://openalex.org/W1",
                "doi": "https://doi.org/10.5678/openalex.001",
                "title": "OpenAlex Article",
                "display_name": "OpenAlex Article",
                "publication_year": 2023,
                "authorships": [
                    {"author": {"display_name": "Dave Black"}},
                ],
                "primary_location": {
                    "source": {"display_name": "OpenAlex Journal"},
                },
                "abstract_inverted_index": {
                    "This": [0],
                    "is": [1],
                    "an": [2],
                    "abstract": [3],
                },
            }
        ],
    }
