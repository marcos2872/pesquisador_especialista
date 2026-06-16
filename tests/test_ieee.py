"""Testes para utils.search.ieee."""

from unittest.mock import patch

from utils.search.ieee import search_ieee


def test_search_ieee_returns_empty_without_api_key():
    with patch.dict("os.environ", {}, clear=True):
        assert search_ieee("test", 3, 5) == []


def test_search_ieee_parses_response():
    response = {
        "articles": [
            {
                "title": "IEEE Sample Article",
                "doi": "10.1109/example.2024.123",
                "article_number": "1234567",
                "publication_year": "2024",
                "publication_title": "IEEE Transactions on Example",
                "abstract": "Sample abstract for IEEE.",
                "authors": {
                    "authors": [
                        {"full_name": "Alice Engineer"},
                        {"full_name": "Bob Engineer"},
                    ]
                },
            }
        ]
    }
    with patch.dict("os.environ", {"IEEE_API_KEY": "fake-key"}), \
         patch("utils.search.ieee.http_get_json", return_value=response):
        articles = search_ieee("screw extruder", 3, 5)
    assert len(articles) == 1
    a = articles[0]
    assert a.title == "IEEE Sample Article"
    assert a.doi == "10.1109/example.2024.123"
    assert a.url == "https://doi.org/10.1109/example.2024.123"
    assert a.year == 2024
    assert a.venue == "IEEE Transactions on Example"
    assert a.source_api == "ieee"
    assert a.authors == ["Alice Engineer", "Bob Engineer"]


def test_search_ieee_falls_back_to_document_url_when_no_doi():
    response = {
        "articles": [
            {
                "title": "No DOI Paper",
                "article_number": "9999999",
                "authors": {"authors": []},
            }
        ]
    }
    with patch.dict("os.environ", {"IEEE_API_KEY": "fake-key"}), \
         patch("utils.search.ieee.http_get_json", return_value=response):
        articles = search_ieee("test", 3, 5)
    assert articles[0].url == "https://ieeexplore.ieee.org/document/9999999"
    assert articles[0].doi is None


def test_search_ieee_handles_empty_response():
    with patch.dict("os.environ", {"IEEE_API_KEY": "fake-key"}), \
         patch("utils.search.ieee.http_get_json", return_value={}):
        assert search_ieee("test", 3, 5) == []


def test_search_ieee_returns_empty_when_request_fails():
    with patch.dict("os.environ", {"IEEE_API_KEY": "fake-key"}), \
         patch("utils.search.ieee.http_get_json", return_value=None):
        assert search_ieee("test", 3, 5) == []
