"""Testes de integração do app com os módulos de busca."""

from unittest.mock import patch

import pytest

from server.config import build_user_prompt
from server.models.article import Article
from server.services.ai_service import extract_openai_text
from server.services.report_service import sanitize_report_links
from server.services.research_service import _collect_real_sources
from server.services.source_service import validate_report_sources


def test_collect_real_sources_returns_context_with_articles():
    a = Article(
        title="Test",
        doi="10.1/x",
        url="https://doi.org/10.1/x",
        authors=["A"],
        year=2020,
    )
    with (
        patch("server.services.source_collector.search_articles", return_value=[a]),
        patch("server.services.source_collector.search_patents", return_value=[]),
        patch(
            "server.utils.fetcher.download_source_texts",
            return_value=[
                {"title": "Test", "url": "https://doi.org/10.1/x", "snippets": []}
            ],
        ),
        patch("server.utils.fetcher.generate_query_variants", return_value=["test"]),
        patch.dict("os.environ", {"SEARCH_QUERY_DELAY_SECONDS": "0"}),
    ):
        ctx, snippets = _collect_real_sources("test")
    assert "ARTIGOS:" in ctx
    assert "Test" in ctx
    assert isinstance(snippets, dict)


def test_collect_real_sources_returns_empty_when_disabled():
    with patch.dict(
        "os.environ", {"ENABLE_REAL_SEARCH": "0", "SEARCH_QUERY_DELAY_SECONDS": "0"}
    ):
        with (
            patch("server.services.source_collector.search_articles") as sa,
            patch("server.services.source_collector.search_patents") as sp,
        ):
            ctx, snippets = _collect_real_sources("test")
    assert ctx == ""
    assert snippets == {}
    sa.assert_not_called()
    sp.assert_not_called()


def test_collect_real_sources_handles_exceptions_gracefully():
    with (
        patch(
            "server.services.source_collector.search_articles",
            side_effect=RuntimeError("boom"),
        ),
        patch(
            "server.services.source_collector.search_patents",
            side_effect=RuntimeError("boom"),
        ),
        patch("server.utils.fetcher.generate_query_variants", return_value=["test"]),
        patch.dict("os.environ", {"SEARCH_QUERY_DELAY_SECONDS": "0"}),
    ):
        ctx, snippets = _collect_real_sources("test")
    assert ctx == ""
    assert snippets == {}


def test_build_user_prompt_without_sources_omits_context_block():
    prompt = build_user_prompt("screw extruder")
    assert "CONTEXTO DE FONTES VERIFICADAS" not in prompt


def test_build_user_prompt_includes_sources_context():
    prompt = build_user_prompt("screw extruder", sources_context="ARTIGOS: ...")
    assert "CONTEXTO DE FONTES VERIFICADAS" in prompt
    assert "ARTIGOS: ..." in prompt


# ── extract_openai_text ──────────────────────────────────────────────


def test_extract_openai_text_from_output_text():
    data = {"output_text": "  Relatório gerado com sucesso.  "}
    assert extract_openai_text(data) == "Relatório gerado com sucesso."


def test_extract_openai_text_from_output_list():
    data = {
        "output": [
            {
                "content": [
                    {"type": "output_text", "text": "Primeiro parágrafo."},
                    {"type": "output_text", "text": "  "},
                    {"type": "output_text", "text": "Segundo parágrafo."},
                ]
            }
        ]
    }
    assert "Primeiro" in extract_openai_text(data)
    assert "Segundo" in extract_openai_text(data)


def test_extract_openai_text_from_choices_fallback():
    data = {
        "choices": [
            {
                "message": {"content": "Conteúdo via chat completions."},
            }
        ]
    }
    assert extract_openai_text(data) == "Conteúdo via chat completions."


def test_extract_openai_text_choices_with_list_content():
    data = {
        "choices": [
            {
                "message": {
                    "content": [
                        {"text": "Parte A."},
                        {"text": "Parte B."},
                    ]
                }
            }
        ]
    }
    result = extract_openai_text(data)
    assert "Parte A" in result
    assert "Parte B" in result


def test_extract_openai_text_handles_empty():
    assert extract_openai_text({}) == ""
    assert extract_openai_text({"output_text": "   "}) == ""


# ── validate_report_sources ──────────────────────────────────────────


def test_validate_report_sources_accepts_primary_sources():
    report = "Texto com [Fonte](https://doi.org/10.1234/test) e [Fonte](https://patents.google.com/patent/US123/en)."
    # Não deve lançar exceção
    validate_report_sources(report)


def test_validate_report_sources_rejects_missing_links():
    with pytest.raises(RuntimeError, match="não trouxe links"):
        validate_report_sources("Texto sem links.")


def test_validate_report_sources_rejects_search_links_only():
    with pytest.raises(RuntimeError, match="não trouxe links diretos"):
        validate_report_sources(
            "Texto com [Fonte](https://scholar.google.com/) e [Fonte](https://example.com/search?q=test)."
        )


# ── sanitize_report_links ────────────────────────────────────────────


def test_sanitize_report_links_keeps_valid_urls():
    with patch(
        "server.services.report_service.validate_url_relevance", return_value=(True, "")
    ):
        report = "Texto com [Fonte](https://doi.org/10.1234/test)."
        sanitized, removed = sanitize_report_links(report, "test topic")
    assert "https://doi.org/10.1234/test" in sanitized
    assert len(removed) == 0


def test_sanitize_report_links_removes_search_urls():
    report = "Texto com [Fonte](https://scholar.google.com/)."
    sanitized, removed = sanitize_report_links(report, "test topic")
    assert "fonte não verificada" in sanitized
    assert len(removed) == 1


def test_sanitize_report_links_removes_invalid_urls():
    with patch(
        "server.services.report_service.validate_url_relevance",
        return_value=(False, "timeout"),
    ):
        report = "Texto com [Fonte](https://example.com/article)."
        sanitized, removed = sanitize_report_links(report, "test topic")
    assert "fonte não verificada" in sanitized
    assert len(removed) == 1


def test_sanitize_report_links_rebuilds_reference_section():
    # A seção 6 só é reconstruída quando há URLs removidos.
    # Usamos um link de busca que será removido + um DOI válido.
    with patch(
        "server.services.report_service.validate_url_relevance", return_value=(True, "")
    ):
        report = (
            "Texto com [Fonte](https://scholar.google.com/) e "
            "[Fonte](https://doi.org/10.1/a).\n\n"
            "## 6. Referências antigas\n"
            "- https://doi.org/10.1/old\n"
        )
        sanitized, removed = sanitize_report_links(report, "test")
    # Link do Google Scholar deve ter sido removido
    assert len(removed) >= 1
    # Seção 6 reconstruída deve conter apenas o DOI válido
    assert "## 6. Referências utilizadas" in sanitized
    assert "10.1/a" in sanitized
    # A seção antiga deve ter sido removida
    assert "Referências antigas" not in sanitized


def test_sanitize_report_links_removes_no_validation_markers():
    report = "Texto [sem validação externa] com [Fonte](https://doi.org/10.1/x)."
    with patch(
        "server.services.report_service.validate_url_relevance", return_value=(True, "")
    ):
        sanitized, _ = sanitize_report_links(report, "test")
    assert "[sem validação externa]" not in sanitized
