"""Testes para utils.search.serpapi."""

from unittest.mock import patch

from server.utils.search.serpapi import search_google_scholar


def test_google_scholar_returns_empty_without_api_key():
    with patch.dict("os.environ", {}, clear=True):
        assert search_google_scholar("test", 3, 5) == []


def test_google_scholar_parses_response():
    response = {
        "organic_results": [
            {
                "title": "Sample Scholar Article",
                "link": "https://example.com/article",
                "publication_info": {"summary": "A Autores, 2024, Journal of Research"},
                "snippet": "This is a sample abstract.",
            }
        ]
    }
    with (
        patch.dict("os.environ", {"SERPAPI_API_KEY": "fake-key"}),
        patch("server.utils.search.serpapi.http_get_json", return_value=response),
    ):
        articles = search_google_scholar("machine learning", 3, 5)
    assert len(articles) == 1
    a = articles[0]
    assert a.title == "Sample Scholar Article"
    assert a.url == "https://example.com/article"
    assert a.year == 2024
    assert a.authors == ["A Autores"]
    assert a.venue == "Journal of Research"
    assert a.abstract == "This is a sample abstract."
    assert a.source_api == "google_scholar"


def test_google_scholar_handles_minimal_summary():
    response = {
        "organic_results": [
            {
                "title": "Minimal Article",
                "link": "https://example.com/minimal",
                "publication_info": {"summary": "B Autor, 2023"},
                "snippet": "",
            }
        ]
    }
    with (
        patch.dict("os.environ", {"SERPAPI_API_KEY": "fake-key"}),
        patch("server.utils.search.serpapi.http_get_json", return_value=response),
    ):
        articles = search_google_scholar("test", 3, 5)
    assert articles[0].title == "Minimal Article"
    assert articles[0].year == 2023
    assert articles[0].authors == ["B Autor"]
    assert articles[0].venue is None


def test_google_scholar_handles_missing_title():
    response = {
        "organic_results": [
            {"link": "https://example.com/no-title", "publication_info": {}}
        ]
    }
    with (
        patch.dict("os.environ", {"SERPAPI_API_KEY": "fake-key"}),
        patch("server.utils.search.serpapi.http_get_json", return_value=response),
    ):
        assert search_google_scholar("test", 3, 5) == []


def test_google_scholar_returns_empty_when_request_fails():
    with (
        patch.dict("os.environ", {"SERPAPI_API_KEY": "fake-key"}),
        patch("server.utils.search.serpapi.http_get_json", return_value=None),
    ):
        assert search_google_scholar("test", 3, 5) == []
