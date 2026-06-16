"""Testes para utils.fetcher — extração de snippets, queries e validação."""

from unittest.mock import patch

from services.source_service import _is_search_or_home_url, _looks_like_primary_source
from utils.fetcher import (
    _deduplicate_snippets,
    _extract_keywords,
    _extract_snippets_around_keywords,
    download_source_texts,
    generate_query_variants,
    validate_quoted_citations,
    validate_url_relevance,
)

# ── _extract_keywords ────────────────────────────────────────────────


def test_extract_keywords_removes_stopwords():
    keywords = _extract_keywords("o estudo de ligas de alumínio com grafeno")
    assert "o" not in keywords
    assert "de" not in keywords
    assert "com" not in keywords
    assert "ligas" in keywords
    assert "alumínio" in keywords or "aluminio" in keywords
    assert "grafeno" in keywords


def test_extract_keywords_minimum_length():
    keywords = _extract_keywords("AI em CPU com ML")
    assert "cpu" in keywords
    # Palavras com menos de 3 caracteres são ignoradas
    for kw in keywords:
        assert len(kw.strip("-\n")) >= 3


def test_extract_keywords_handles_empty():
    assert _extract_keywords("") == set()
    assert _extract_keywords("a e o de") == set()


# ── _extract_snippets_around_keywords ─────────────────────────────────


def test_extract_snippets_around_keywords_basic():
    text = (
        "The tensile strength of graphene aluminum alloys increased by "
        "42 percent with 0.5 weight percent graphene loading. "
        "This represents a significant improvement over pure aluminum."
    )
    keywords = {"graphene", "aluminum", "tensile"}
    snippets = _extract_snippets_around_keywords(text, keywords, max_snippets=3)
    assert len(snippets) > 0
    assert any("graphene" in s.lower() for s in snippets)


def test_extract_snippets_around_keywords_returns_empty_for_no_match():
    snippets = _extract_snippets_around_keywords(
        "lorem ipsum dolor sit amet", {"graphene", "titanium"}
    )
    assert snippets == []


def test_extract_snippets_around_keywords_returns_empty_for_empty_text():
    assert _extract_snippets_around_keywords("", {"test"}) == []
    assert _extract_snippets_around_keywords("text", set()) == []


def test_extract_snippets_truncates_short():
    """Snippets menores que 40 caracteres são filtrados."""
    snippets = _extract_snippets_around_keywords(
        "short text with kw", {"kw"}, max_snippets=5, context_window=5
    )
    # O snippet " with kw" teria ~12 chars, deve ser filtrado
    assert all(len(s) >= 40 for s in snippets)


# ── _deduplicate_snippets ────────────────────────────────────────────


def test_deduplicate_snippets_removes_overlap():
    # A deduplicação usa o trecho s[50:150] como chave. Para que dois snippets
    # colidam, precisam ter overlap idêntico na região [50:150].
    shared = "x" * 200  # Suficiente para cobrir posições 50-150 totalmente com x's
    snippets = [
        f"prefix one {shared} suffix one",
        f"prefix two {shared} suffix two",
        "completely different text about other things " + ("y" * 60),
    ]
    result = _deduplicate_snippets(snippets)
    assert len(result) == 2  # Os dois primeiros têm overlap na chave


def test_deduplicate_snippets_handles_empty():
    assert _deduplicate_snippets([]) == []


# ── generate_query_variants / _build_expanded_queries ─────────────────


def test_generate_query_variants_returns_portuguese_and_english():
    queries = generate_query_variants("ligas de alumínio com grafeno")
    assert any("aluminum" in q.lower() for q in queries)
    assert any("grafeno" in q.lower() or "graphene" in q.lower() for q in queries)
    assert len(queries) >= 2  # Pelo menos PT e EN


def test_generate_query_variants_includes_connectors():
    queries = generate_query_variants("baterias de lítio")
    assert any("review" in q.lower() for q in queries)
    assert len(queries) <= 6  # Limite máximo


def test_generate_query_variants_deduplicates():
    queries = generate_query_variants("the the test test")
    assert len(queries) == len(set(q.lower() for q in queries))


# ── validate_quoted_citations ────────────────────────────────────────


def test_validate_quoted_citations_passes_when_snippet_matches():
    report = 'O estudo afirma que "tensile strength increased by 42 percent" [Fonte](https://doi.org/10.1/x).'
    snippets_map = {
        "https://doi.org/10.1/x": [
            "…tensile strength increased by 42 percent with graphene loading…",
        ]
    }
    sanitized, warnings = validate_quoted_citations(report, snippets_map)
    assert "[citação não verificada na fonte]" not in sanitized
    assert len(warnings) == 0


def test_validate_quoted_citations_flags_unverified():
    report = 'O estudo afirma que "this fabricated claim does not exist anywhere" [Fonte](https://doi.org/10.1/x).'
    snippets_map = {
        "https://doi.org/10.1/x": ["…real text about aluminum alloys…"],
    }
    sanitized, warnings = validate_quoted_citations(report, snippets_map)
    assert "[citação não verificada na fonte]" in sanitized
    assert len(warnings) == 1
    assert "fabricated claim" in warnings[0]


def test_validate_quoted_citations_ignores_short_quotes():
    """Citações com menos de 30 caracteres são ignoradas."""
    report = 'Isso é "curto" demais.'
    _, warnings = validate_quoted_citations(report, {})
    assert len(warnings) == 0


def test_validate_quoted_citations_returns_unchanged_without_snippets():
    report = 'O texto diz "alguma coisa importante aqui que precisa ser verificada".'
    sanitized, warnings = validate_quoted_citations(report, {})
    assert sanitized == report
    assert warnings == []


# ── validate_url_relevance ───────────────────────────────────────────


def test_validate_url_relevance_rejects_malformed():
    is_valid, reason = validate_url_relevance("not-a-url", "test")
    assert not is_valid
    assert "malformada" in reason.lower()


def test_validate_url_relevance_validates_doi_via_crossref():
    # Usa tópico em inglês para que as keywords (graphene, aluminum, alloys)
    # casem com o título/abstract do mock.
    with patch("utils.fetcher.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value.read.return_value = (
            b'{"message": {"title": ["Graphene Aluminum Alloys"], '
            b'"abstract": "Study of graphene reinforced aluminum matrix composites"}}'
        )
        mock_urlopen.return_value.__enter__.return_value.status = 200
        is_valid, reason = validate_url_relevance(
            "https://doi.org/10.1234/graphene.al.001",
            "graphene aluminum alloys composites",
        )
    assert is_valid
    assert reason == ""


def test_validate_url_relevance_rejects_doi_not_found():
    from urllib.error import HTTPError

    with patch(
        "utils.fetcher.urlopen",
        side_effect=HTTPError(
            "https://api.crossref.org/works/10.1234/fake", 404, "Not Found", {}, None
        ),
    ):
        is_valid, reason = validate_url_relevance(
            "https://doi.org/10.1234/fake", "test topic"
        )
    assert not is_valid
    assert "não encontrado" in reason.lower()


# ── download_source_texts ────────────────────────────────────────────


def test_download_source_texts_enriches_sources():
    sources = [
        {
            "title": "Test Article",
            "url": "https://example.com/article",
            "pdf_url": None,
        }
    ]
    with patch("utils.fetcher.fetch_url") as mock_fetch:
        mock_fetch.return_value = (
            True,
            "This paper studies graphene aluminum alloys. "
            + "The tensile strength increased by 42 percent with 0.5 wt% graphene. "
            + "These results demonstrate significant improvement over pure aluminum.",
            "",
        )
        enriched = download_source_texts(sources, "graphene aluminum alloys")
    assert len(enriched) == 1
    assert len(enriched[0].get("snippets", [])) > 0
    assert any("42 percent" in s for s in enriched[0]["snippets"])


def test_download_source_texts_handles_fetch_failure():
    sources = [{"title": "Broken", "url": "https://example.com/broken"}]
    with patch("utils.fetcher.fetch_url", return_value=(False, "", "timeout")):
        enriched = download_source_texts(sources, "test")
    assert enriched[0].get("snippets", []) == []


def test_download_source_texts_returns_empty_for_no_sources():
    assert download_source_texts([], "test") == []


# ── URL classification helpers (imported from app.py for coverage) ───


def test_is_search_or_home_url_identifies_search_pages():
    assert _is_search_or_home_url("https://scholar.google.com/") is True
    assert _is_search_or_home_url("https://example.com/search?q=test") is True
    assert _is_search_or_home_url("https://doi.org/10.1234/test") is False


def test_looks_like_primary_source_identifies_documents():
    assert _looks_like_primary_source("https://doi.org/10.1234/test") is True
    assert _looks_like_primary_source("https://example.com/article/123") is True
    assert (
        _looks_like_primary_source("https://patents.google.com/patent/US123/en") is True
    )
    assert _looks_like_primary_source("https://example.com/search") is False
