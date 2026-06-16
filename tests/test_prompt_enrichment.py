"""Testes para utils.search.prompt_enrichment."""

from models.article import Article
from models.patent import Patent
from utils.search.prompt_enrichment import build_sources_context


def make_article(**kwargs) -> Article:
    defaults = {
        "title": "Sample Article",
        "doi": "10.1234/sample",
        "url": "https://doi.org/10.1234/sample",
        "authors": ["Jane Doe", "John Smith"],
        "year": 2022,
        "venue": "Sample Journal",
        "abstract": "Short abstract.",
    }
    defaults.update(kwargs)
    return Article(**defaults)


def make_patent(**kwargs) -> Patent:
    defaults = {
        "title": "Sample Patent",
        "number": "US12345678A1",
        "url": "https://patents.google.com/patent/US12345678A1/en",
        "inventors": ["Inventor One"],
        "year": 2020,
        "assignee": "Acme Corp",
        "jurisdiction": "US",
    }
    defaults.update(kwargs)
    return Patent(**defaults)


def test_returns_none_when_no_sources():
    assert build_sources_context([], []) is None


def test_includes_only_articles_when_no_patents():
    a = make_article()
    result = build_sources_context([a], [])
    assert "ARTIGOS:" in result
    assert "PATENTES:" not in result
    assert "Sample Article" in result
    assert "10.1234/sample" in result


def test_includes_only_patents_when_no_articles():
    p = make_patent()
    result = build_sources_context([], [p])
    assert "PATENTES:" in result
    assert "ARTIGOS:" not in result
    assert "US12345678A1" in result


def test_includes_both_when_provided():
    a = make_article()
    p = make_patent()
    result = build_sources_context([a], [p])
    assert "ARTIGOS:" in result
    assert "PATENTES:" in result


def test_truncates_long_abstracts():
    long_abstract = "word " * 500
    a = make_article(abstract=long_abstract.strip())
    result = build_sources_context([a], [], max_abstract_chars=100)
    assert "…" in result


def test_limits_number_of_articles():
    articles = [make_article(doi=f"10.1234/{i}", title=f"Article {i}") for i in range(10)]
    result = build_sources_context(articles, [], max_articles=3)
    assert result.count("Título:") == 3


def test_limits_number_of_patents():
    patents = [make_patent(number=f"US{1000 + i}A1", title=f"Patent {i}") for i in range(10)]
    result = build_sources_context([], patents, max_patents=2)
    assert result.count("Título:") == 2


def test_filters_invalid_articles():
    invalid = Article(title="No link", doi=None, url=None)
    valid = make_article()
    result = build_sources_context([invalid, valid], [])
    assert "No link" not in result
    assert "Sample Article" in result


def test_filters_invalid_patents():
    invalid = Patent(title="", number="", url="")
    valid = make_patent()
    result = build_sources_context([], [invalid, valid])
    assert result.count("Título:") == 1
