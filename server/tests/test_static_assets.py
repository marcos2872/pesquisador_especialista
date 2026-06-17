"""Testes para rotas de assets estáticos."""

from pathlib import Path

from server.handlers.research_handler import ResearchHandler

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ASSETS_DIR = PROJECT_ROOT / "ui" / "dist" / "assets"


def test_resolve_asset_file_maps_public_asset_route():
    handler = ResearchHandler.__new__(ResearchHandler)

    resolved = handler._resolve_asset_file("/assets/senai-brand.svg")

    assert resolved == ASSETS_DIR / "senai-brand.svg"


def test_resolve_asset_file_maps_asset_route_with_dot_segment():
    handler = ResearchHandler.__new__(ResearchHandler)

    resolved = handler._resolve_asset_file("/assets/./senai-brand.svg")

    assert resolved == ASSETS_DIR / "senai-brand.svg"


def test_resolve_asset_file_blocks_path_traversal():
    handler = ResearchHandler.__new__(ResearchHandler)

    assert handler._resolve_asset_file("/assets/../config.py") is None
    assert handler._resolve_asset_file("/assets/../../config.py") is None
    assert handler._resolve_asset_file("/assets/..%2Fconfig.py") is None
    assert (
        handler._resolve_asset_file("/assets//senai-brand.svg")
        == ASSETS_DIR / "senai-brand.svg"
    )
