"""Testes para utils.search.wipo."""

from unittest.mock import patch

from server.utils.search.wipo import search_wipo


def test_search_wipo_returns_empty_without_api_key():
    with patch.dict("os.environ", {}, clear=True):
        assert search_wipo("test", 3, 5) == []


def test_search_wipo_parses_response():
    response = {
        "resultList": [
            {
                "publicationNumber": "WO2024/123456A1",
                "title": "WIPO Sample Patent",
                "publicationDate": "2024-05-15",
                "inventors": [
                    {"name": "Inventor One"},
                    {"name": "Inventor Two"},
                ],
            }
        ]
    }
    with (
        patch.dict("os.environ", {"WIPO_API_KEY": "fake-key"}),
        patch("server.utils.search.wipo.http_post_json", return_value=response),
    ):
        patents = search_wipo("screw extruder", 3, 5)
    assert len(patents) == 1
    p = patents[0]
    assert p.number == "WO2024/123456A1"
    assert p.title == "WIPO Sample Patent"
    assert p.year == 2024
    assert p.inventors == ["Inventor One", "Inventor Two"]
    assert p.source_api == "wipo"
    assert p.jurisdiction == "WO"
    assert "patentscope.wipo.int" in p.url


def test_search_wipo_handles_alternative_field_names():
    response = {
        "data": [
            {
                "id": "WO2024/999999A1",
                "inventionTitle": "Alt Field Patent",
                "datePublished": "2024-03-10",
                "inventors": ["Inventor Three"],
            }
        ]
    }
    with (
        patch.dict("os.environ", {"WIPO_API_KEY": "fake-key"}),
        patch("server.utils.search.wipo.http_post_json", return_value=response),
    ):
        patents = search_wipo("test", 3, 5)
    assert patents[0].title == "Alt Field Patent"
    assert patents[0].number == "WO2024/999999A1"
    assert patents[0].inventors == ["Inventor Three"]


def test_search_wipo_skips_patents_without_number():
    response = {
        "resultList": [
            {"title": "Missing number", "publicationDate": "2024-01-01"},
            {
                "publicationNumber": "WO2024/000001A1",
                "title": "Valid",
                "publicationDate": "2024-01-01",
            },
        ]
    }
    with (
        patch.dict("os.environ", {"WIPO_API_KEY": "fake-key"}),
        patch("server.utils.search.wipo.http_post_json", return_value=response),
    ):
        patents = search_wipo("test", 3, 5)
    assert len(patents) == 1
    assert patents[0].number == "WO2024/000001A1"


def test_search_wipo_returns_empty_when_request_fails():
    with (
        patch.dict("os.environ", {"WIPO_API_KEY": "fake-key"}),
        patch("server.utils.search.wipo.http_post_json", return_value=None),
    ):
        assert search_wipo("test", 3, 5) == []
