"""Testes para utils.search.academic."""

from unittest.mock import patch

from server.models.article import Article
from server.utils.search.academic import (
    _dedup_articles,
    _reconstruct_abstract,
    _search_arxiv,
    _search_core,
    _search_crossref,
    _search_openalex,
    _search_semantic_scholar,
    search_articles,
)


def test_reconstruct_abstract_from_inverted_index():
    inv = {"The": [0], "quick": [1], "brown": [2], "fox": [3]}
    assert _reconstruct_abstract(inv) == "The quick brown fox"


def test_reconstruct_abstract_handles_empty():
    assert _reconstruct_abstract(None) is None
    assert _reconstruct_abstract({}) is None


def test_article_is_valid_requires_title_and_link():
    a = Article(title="X")
    assert not a.is_valid()
    a = Article(title="X", doi="10.1/x")
    assert a.is_valid()
    a = Article(title="X", url="https://example.com/x")
    assert a.is_valid()


def test_search_crossref_parses_response(mock_crossref_response):
    with patch(
        "server.utils.search.academic.http_get_json",
        return_value=mock_crossref_response,
    ):
        articles = _search_crossref("test", 5, 10)
    assert len(articles) == 2
    assert articles[0].doi == "10.1234/test.001"
    assert articles[0].title == "Test Article One"
    assert articles[0].authors == ["Alice Smith", "Bob Jones"]
    assert articles[0].year == 2021
    assert articles[0].venue == "Journal of Tests"
    assert articles[1].abstract is None
    assert articles[1].source_api == "crossref"


def test_search_openalex_parses_response(mock_openalex_response):
    with patch(
        "server.utils.search.academic.http_get_json",
        return_value=mock_openalex_response,
    ):
        articles = _search_openalex("test", 5, 10)
    assert len(articles) == 1
    a = articles[0]
    assert a.doi == "10.5678/openalex.001"
    assert a.title == "OpenAlex Article"
    assert a.year == 2023
    assert a.abstract == "This is an abstract"
    assert a.source_api == "openalex"


def test_search_articles_prefers_crossref(
    mock_crossref_response, mock_openalex_response
):
    def _mock_json(url, headers=None, timeout=10):
        if "crossref" in url:
            return mock_crossref_response
        return None

    with (
        patch("server.utils.search.academic.http_get_json", side_effect=_mock_json),
        patch("server.utils.search.academic.http_get_text", return_value=None),
    ):
        articles = search_articles("test", max_results=3, timeout=10)
    assert len(articles) == 2
    assert all(a.source_api == "crossref" for a in articles)


def test_search_articles_falls_back_to_openalex(mock_openalex_response):
    def _mock_json(url, headers=None, timeout=10):
        if "openalex" in url:
            return mock_openalex_response
        return None

    with (
        patch("server.utils.search.academic.http_get_json", side_effect=_mock_json),
        patch("server.utils.search.academic.http_get_text", return_value=None),
    ):
        articles = search_articles("test", max_results=3, timeout=10)
    assert len(articles) == 1
    assert articles[0].source_api == "openalex"


def test_search_articles_returns_empty_when_all_fail():
    with (
        patch("server.utils.search.academic.http_get_json", return_value=None),
        patch("server.utils.search.academic.http_get_text", return_value=None),
    ):
        assert search_articles("test", max_results=3, timeout=10) == []


def test_search_articles_filters_invalid():
    bad_response = {
        "message": {
            "items": [
                {"title": ["No DOI"], "author": [], "container-title": ["X"]},
                {"DOI": "10.1/ok", "title": ["Valid"], "author": []},
            ]
        }
    }
    with (
        patch("server.utils.search.academic.http_get_json", return_value=bad_response),
        patch("server.utils.search.academic.http_get_text", return_value=None),
    ):
        articles = search_articles("test", max_results=3, timeout=10)
    assert len(articles) == 1
    assert articles[0].doi == "10.1/ok"


_ARXIV_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2306.04338v1</id>
    <title>Sample arXiv Paper</title>
    <summary>An interesting abstract about screw extruder elements.</summary>
    <published>2023-06-07T11:08:12Z</published>
    <arxiv:doi>10.1234/arxiv.001</arxiv:doi>
    <author><name>Alice Author</name></author>
    <author><name>Bob Author</name></author>
  </entry>
</feed>"""


def test_search_arxiv_parses_xml():
    with patch("server.utils.search.academic.http_get_text", return_value=_ARXIV_XML):
        articles = _search_arxiv("screw extruder", 3, 10)
    assert len(articles) == 1
    a = articles[0]
    assert a.title == "Sample arXiv Paper"
    assert "screw extruder" in (a.abstract or "")
    assert a.year == 2023
    assert a.doi == "10.1234/arxiv.001"
    assert a.url == "https://arxiv.org/abs/2306.04338v1"
    assert a.pdf_url == "https://arxiv.org/pdf/2306.04338v1"
    assert a.source_api == "arxiv"


def test_search_arxiv_handles_malformed_xml():
    with patch("server.utils.search.academic.http_get_text", return_value="<invalid"):
        assert _search_arxiv("test", 3, 10) == []


def test_search_arxiv_returns_empty_when_request_fails():
    with patch("server.utils.search.academic.http_get_text", return_value=None):
        assert _search_arxiv("test", 3, 10) == []


def test_search_core_parses_response():
    response = {
        "totalHits": 1,
        "results": [
            {
                "title": "CORE Sample",
                "doi": "10.1/core.001",
                "downloadUrl": "https://core.ac.uk/download/123",
                "yearPublished": 2020,
                "publisher": "Sample Press",
                "abstract": "Sample abstract.",
                "authors": [{"name": "Alice"}, {"name": "Bob"}],
            }
        ],
    }
    with patch("server.utils.search.academic.http_get_json", return_value=response):
        articles = _search_core("screw extruder", 3, 10)
    assert len(articles) == 1
    a = articles[0]
    assert a.title == "CORE Sample"
    assert a.doi == "10.1/core.001"
    assert a.url == "https://doi.org/10.1/core.001"
    assert a.year == 2020
    assert a.source_api == "core"
    assert a.authors == ["Alice", "Bob"]


def test_search_core_returns_empty_when_request_fails():
    with patch("server.utils.search.academic.http_get_json", return_value=None):
        assert _search_core("test", 3, 10) == []


def test_search_semantic_scholar_parses_response():
    response = {
        "total": 1,
        "data": [
            {
                "paperId": "abc123",
                "title": "Semantic Scholar Sample",
                "year": 2022,
                "venue": "Test Venue",
                "abstract": "SS abstract.",
                "externalIds": {"DOI": "10.1/ss.001"},
                "authors": [{"name": "Carol"}],
            }
        ],
    }
    with patch("server.utils.search.academic.http_get_json", return_value=response):
        articles = _search_semantic_scholar("test", 3, 10)
    assert len(articles) == 1
    a = articles[0]
    assert a.title == "Semantic Scholar Sample"
    assert a.doi == "10.1/ss.001"
    assert a.url == "https://doi.org/10.1/ss.001"
    assert a.source_api == "semantic_scholar"


def test_search_semantic_scholar_falls_back_to_paper_id_url():
    response = {
        "total": 1,
        "data": [
            {
                "paperId": "xyz789",
                "title": "No DOI Paper",
                "authors": [],
            }
        ],
    }
    with patch("server.utils.search.academic.http_get_json", return_value=response):
        articles = _search_semantic_scholar("test", 3, 10)
    assert articles[0].url == "https://www.semanticscholar.org/paper/xyz789"
    assert articles[0].doi is None


def test_dedup_articles_merges_duplicates_by_doi():
    a = Article(title="A", doi="10.1/x", url="https://u")
    b = Article(title="A variant", doi="10.1/X", url="https://other")
    c = Article(title="Unique", doi="10.1/y", url="https://u2")
    result = _dedup_articles([a, b, c])
    assert len(result) == 2
    assert result[0].title == "A"


def test_dedup_articles_merges_duplicates_by_title():
    a = Article(title="Screw Extruder Elements", doi=None, url="https://a")
    b = Article(title="screw-extruder-elements!", doi=None, url="https://b")
    c = Article(title="Different", doi=None, url="https://c")
    result = _dedup_articles([a, b, c])
    assert len(result) == 2


def test_search_articles_combines_multiple_providers():
    crossref_resp = {
        "message": {
            "items": [
                {
                    "DOI": "10.1/a",
                    "title": ["A"],
                    "author": [],
                    "container-title": ["X"],
                },
            ]
        }
    }
    openalex_resp = {
        "meta": {"count": 1},
        "results": [
            {
                "id": "https://openalex.org/W1",
                "doi": "https://doi.org/10.1/b",
                "title": "B",
                "display_name": "B",
                "publication_year": 2020,
                "authorships": [],
                "primary_location": {},
            }
        ],
    }
    arxiv_xml = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/1234</id>
    <title>C</title>
    <summary>abs</summary>
    <published>2021-01-01T00:00:00Z</published>
    <author><name>X</name></author>
  </entry>
</feed>"""

    def _mock_json(url, headers=None, timeout=10):
        if "crossref" in url:
            return crossref_resp
        elif "openalex" in url:
            return openalex_resp
        return None

    with (
        patch("server.utils.search.academic.http_get_json", side_effect=_mock_json),
        patch("server.utils.search.academic.http_get_text", return_value=arxiv_xml),
    ):
        articles = search_articles("test", max_results=5, timeout=10)
    sources = {a.source_api for a in articles}
    assert "crossref" in sources
    assert "openalex" in sources
    assert "arxiv" in sources
