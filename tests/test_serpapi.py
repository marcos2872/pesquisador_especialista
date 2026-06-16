"""Testes para utils.search.serpapi."""

from unittest.mock import patch

from utils.search.serpapi import search_google_scholar, search_google_patents


def test_google_scholar_returns_empty_without_api_key():
    with patch.dict("os.environ", {}, clear=True):
        assert search_google_scholar("test", 3, 5) == []


def test_google_scholar_parses_response():
    response = {
        "organic_results": [
            {
                "title": "Sample Scholar Article",
                "link": "https://example.com/article",
                "publication_info": {
                    "summary": "A Autores, 2024, Journal of Research"
                },
                "snippet": "This is a sample abstract.",
            }
        ]
    }
    with patch.dict("os.environ", {"SERPAPI_API_KEY": "fake-key"}), \
         patch("utils.search.serpapi._http_get_json", return_value=response):
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
                "publication_info": {
                    "summary": "B Autor, 2023"
                },
                "snippet": "",
            }
        ]
    }
    with patch.dict("os.environ", {"SERPAPI_API_KEY": "fake-key"}), \
         patch("utils.search.serpapi._http_get_json", return_value=response):
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
    with patch.dict("os.environ", {"SERPAPI_API_KEY": "fake-key"}), \
         patch("utils.search.serpapi._http_get_json", return_value=response):
        assert search_google_scholar("test", 3, 5) == []


def test_google_scholar_returns_empty_when_request_fails():
    with patch.dict("os.environ", {"SERPAPI_API_KEY": "fake-key"}), \
         patch("utils.search.serpapi._http_get_json", return_value=None):
        assert search_google_scholar("test", 3, 5) == []


def test_google_patents_returns_empty_without_api_key():
    with patch.dict("os.environ", {}, clear=True):
        assert search_google_patents("test", 3, 5) == []


def test_google_patents_parses_response():
    response = {
        "organic_results": [
            {
                "title": "Sample Patent Title",
                "patent_id": "US20240000001A1",
                "link": "https://patents.google.com/patent/US20240000001A1/en",
                "publication_date": "2024-03-15",
                "inventor": ["Alice Inventor", "Bob Inventor"],
                "assignee": "Sample Company",
                "summary": "A novel method for machine learning.",
            }
        ]
    }
    with patch.dict("os.environ", {"SERPAPI_API_KEY": "fake-key"}), \
         patch("utils.search.serpapi._http_get_json", return_value=response):
        patents = search_google_patents("machine learning", 3, 5)
    assert len(patents) == 1
    p = patents[0]
    assert p.title == "Sample Patent Title"
    assert p.number == "US20240000001A1"
    assert "patents.google.com" in p.url
    assert p.year == 2024
    assert p.inventors == ["Alice Inventor", "Bob Inventor"]
    assert p.assignee == "Sample Company"
    assert p.abstract == "A novel method for machine learning."
    assert p.source_api == "google_patents"


def test_google_patents_uses_inventors_field_fallback():
    response = {
        "organic_results": [
            {
                "title": "Patent With Inventors Field",
                "patent_id": "US20240000002A1",
                "link": "https://patents.google.com/patent/US20240000002A1/en",
                "publication_date": "2024-06-01",
                "inventors": ["Charlie Inventor"],
                "assignee": "Another Company",
                "summary": "Abstract here.",
            }
        ]
    }
    with patch.dict("os.environ", {"SERPAPI_API_KEY": "fake-key"}), \
         patch("utils.search.serpapi._http_get_json", return_value=response):
        patents = search_google_patents("test", 3, 5)
    assert patents[0].inventors == ["Charlie Inventor"]


def test_google_patents_skips_entry_without_patent_id():
    response = {
        "organic_results": [
            {"title": "No ID", "link": "https://example.com/patent"},
            {
                "title": "Valid Patent",
                "patent_id": "US20240000003A1",
                "link": "https://patents.google.com/patent/US20240000003A1/en",
            },
        ]
    }
    with patch.dict("os.environ", {"SERPAPI_API_KEY": "fake-key"}), \
         patch("utils.search.serpapi._http_get_json", return_value=response):
        patents = search_google_patents("test", 3, 5)
    assert len(patents) == 1
    assert patents[0].number == "US20240000003A1"


def test_google_patents_returns_empty_when_request_fails():
    with patch.dict("os.environ", {"SERPAPI_API_KEY": "fake-key"}), \
         patch("utils.search.serpapi._http_get_json", return_value=None):
        assert search_google_patents("test", 3, 5) == []
