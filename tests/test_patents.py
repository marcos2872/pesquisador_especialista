"""Testes para utils.search.patents."""

from unittest.mock import patch

from utils.search.patents import (
    Patent,
    _dedup_patents,
    _get_epo_ops_token,
    _search_epo_ops,
    _search_lens,
    _search_patentsview,
    _search_uspto,
    search_patents,
)


def test_patent_is_valid_requires_title_number_url():
    p = Patent(title="X", number="US1", url="https://x")
    assert p.is_valid()
    assert not Patent(title="", number="", url="").is_valid()


def test_search_patentsview_parses_response():
    response = {
        "patents": [
            {
                "patent_number": "US10000000A1",
                "patent_title": "Twin Screw Element",
                "patent_date": "2018-09-04",
                "inventors": [
                    {"inventor_first_name": "Jane", "inventor_last_name": "Doe"},
                ],
                "assignees": [
                    {"assignee_organization": "Acme Extruders Inc"},
                ],
            }
        ]
    }
    with patch("utils.search.patents._http_get_json", return_value=response):
        patents = _search_patentsview("test", 5, 10)
    assert len(patents) == 1
    p = patents[0]
    assert p.number == "US10000000A1"
    assert p.title == "Twin Screw Element"
    assert p.year == 2018
    assert p.inventors == ["Jane Doe"]
    assert p.assignee == "Acme Extruders Inc"
    assert p.url == "https://patents.google.com/patent/US10000000A1/en"
    assert p.source_api == "patentsview"


def test_search_patentsview_returns_empty_when_request_fails():
    with patch("utils.search.patents._http_get_json", return_value=None):
        assert _search_patentsview("test", 5, 10) == []


def test_search_patentsview_skips_patents_without_number():
    response = {
        "patents": [
            {"patent_title": "Missing number", "patent_date": "2020-01-01"},
            {"patent_number": "US20000000B2", "patent_title": "Valid", "patent_date": "2019-06-15"},
        ]
    }
    with patch("utils.search.patents._http_get_json", return_value=response):
        patents = _search_patentsview("test", 5, 10)
    assert len(patents) == 1
    assert patents[0].number == "US20000000B2"


def test_get_epo_ops_token_returns_none_without_credentials():
    with patch.dict("os.environ", {}, clear=True):
        assert _get_epo_ops_token(5) is None


def test_search_epo_ops_returns_empty_without_token():
    with patch("utils.search.patents._get_epo_ops_token", return_value=None):
        assert _search_epo_ops("test", 3, 5) == []


def test_search_patents_falls_back_to_patentsview():
    fake_patent = Patent(
        title="X", number="US1", url="https://x", source_api="patentsview"
    )
    with patch("utils.search.patents._search_epo_ops", return_value=[]), \
         patch("utils.search.patents._search_patentsview", return_value=[fake_patent]):
        patents = search_patents("test", 3, 5)
    assert len(patents) == 1
    assert patents[0].source_api == "patentsview"


def test_search_patents_returns_empty_gracefully():
    with patch("utils.search.patents._search_epo_ops", return_value=[]), \
         patch("utils.search.patents._search_patentsview", return_value=[]), \
         patch("utils.search.patents._search_uspto", return_value=[]), \
         patch("utils.search.patents._search_lens", return_value=[]):
        assert search_patents("test", 3, 5) == []


def test_search_uspto_returns_empty_without_api_key():
    with patch.dict("os.environ", {}, clear=True):
        assert _search_uspto("test", 3, 5) == []


def test_search_uspto_parses_response():
    response = {
        "results": [
            {
                "patent_id": "US11000000B2",
                "patent_title": "USPTO Sample Patent",
                "patent_date": "2021-01-15",
                "inventors": [
                    {"inventor_name": "John Inventor"},
                    {"first_name": "Jane", "last_name": "Inventor"},
                ],
                "assignees": [{"assignee_name": "Acme Corp"}],
            }
        ]
    }
    with patch.dict("os.environ", {"USPTO_API_KEY": "fake-key"}), \
         patch("utils.search.patents._http_post_json", return_value=response):
        patents = _search_uspto("screw extruder", 3, 5)
    assert len(patents) == 1
    p = patents[0]
    assert p.number == "US11000000B2"
    assert p.title == "USPTO Sample Patent"
    assert p.year == 2021
    assert "John Inventor" in p.inventors
    assert "Jane Inventor" in p.inventors
    assert p.assignee == "Acme Corp"
    assert p.source_api == "uspto"


def test_search_uspto_handles_empty_results():
    with patch.dict("os.environ", {"USPTO_API_KEY": "fake-key"}), \
         patch("utils.search.patents._http_post_json", return_value={}):
        assert _search_uspto("test", 3, 5) == []


def test_search_lens_returns_empty_without_token():
    with patch.dict("os.environ", {}, clear=True):
        assert _search_lens("test", 3, 5) == []


def test_search_lens_parses_response():
    response = {
        "data": [
            {
                "lens_id": "012-345-678-901-234",
                "title": "Lens Sample Patent",
                "date_published": "2020-05-15",
                "inventors": [{"name": "Inventor Lens"}],
                "applicants": [{"name": "Lens Corp"}],
            }
        ]
    }
    with patch.dict("os.environ", {"LENS_API_TOKEN": "fake-token"}), \
         patch("utils.search.patents._http_post_json", return_value=response):
        patents = _search_lens("screw extruder", 3, 5)
    assert len(patents) == 1
    p = patents[0]
    assert p.number == "012-345-678-901-234"
    assert p.title == "Lens Sample Patent"
    assert p.year == 2020
    assert p.assignee == "Lens Corp"
    assert p.source_api == "lens"
    assert "lens.org" in p.url


def test_dedup_patents_merges_by_number():
    a = Patent(title="A", number="US1", url="https://x")
    b = Patent(title="A dup", number="us1", url="https://y")
    c = Patent(title="C", number="US2", url="https://z")
    result = _dedup_patents([a, b, c])
    assert len(result) == 2


def test_dedup_patents_merges_by_title_for_missing_numbers():
    a = Patent(title="Sample Title", number="X", url="https://x")
    b = Patent(title="Sample-Title!", number="Y", url="https://y")
    c = Patent(title="Different", number="Z", url="https://z")
    result = _dedup_patents([a, b, c])
    assert len(result) == 2


def test_search_patents_combines_multiple_providers():
    a = Patent(title="A", number="US1", url="https://x", source_api="epo_ops")
    b = Patent(title="B", number="US2", url="https://y", source_api="uspto")
    c = Patent(title="C", number="US3", url="https://z", source_api="lens")
    with patch("utils.search.patents._search_epo_ops", return_value=[a]), \
         patch("utils.search.patents._search_uspto", return_value=[b]), \
         patch("utils.search.patents._search_lens", return_value=[c]), \
         patch("utils.search.patents._search_patentsview", return_value=[]):
        patents = search_patents("test", max_results=5, timeout=10)
    sources = {p.source_api for p in patents}
    assert sources == {"epo_ops", "uspto", "lens"}
