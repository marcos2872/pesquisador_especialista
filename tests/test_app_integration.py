"""Testes de integração do app com os módulos de busca."""

from unittest.mock import patch

from app import _collect_real_sources, build_user_prompt
from utils.search.academic import Article


def test_collect_real_sources_returns_context_with_articles():
    a = Article(
        title="Test",
        doi="10.1/x",
        url="https://doi.org/10.1/x",
        authors=["A"],
        year=2020,
    )
    with patch("app.search_articles", return_value=[a]), \
         patch("app.search_patents", return_value=[]):
        ctx = _collect_real_sources("test")
    assert "ARTIGOS:" in ctx
    assert "Test" in ctx


def test_collect_real_sources_returns_empty_when_disabled():
    with patch.dict("os.environ", {"ENABLE_REAL_SEARCH": "0"}):
        with patch("app.search_articles") as sa, \
             patch("app.search_patents") as sp:
            ctx = _collect_real_sources("test")
    assert ctx == ""
    sa.assert_not_called()
    sp.assert_not_called()


def test_collect_real_sources_handles_exceptions_gracefully():
    with patch("app.search_articles", side_effect=RuntimeError("boom")), \
         patch("app.search_patents", side_effect=RuntimeError("boom")):
        ctx = _collect_real_sources("test")
    assert ctx == ""


def test_build_user_prompt_without_sources_omits_context_block():
    prompt = build_user_prompt("screw extruder")
    assert "CONTEXTO DE FONTES VERIFICADAS" not in prompt


def test_build_user_prompt_includes_sources_context():
    prompt = build_user_prompt("screw extruder", sources_context="ARTIGOS: ...")
    assert "CONTEXTO DE FONTES VERIFICADAS" in prompt
    assert "ARTIGOS: ..." in prompt
