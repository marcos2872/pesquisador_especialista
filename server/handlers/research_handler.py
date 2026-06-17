"""
Handler de requisições HTTP para a API de pesquisa.

Usamos BaseHTTPRequestHandler (stdlib) em vez de um framework web para
evitar dependências. O roteamento é feito manualmente no do_GET/do_POST/
do_DELETE comparando self.path com as rotas esperadas.

A aplicação também serve o frontend React estático (ui/dist/) e faz
proteção contra path traversal no serviço de assets.
"""

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from pathlib import Path

from server.services.db import (
    delete_research,
    get_research,
    list_researches,
    save_research,
)
from server.services.research_service import generate_report


class ResearchHandler(BaseHTTPRequestHandler):
    """
    Handler que mapeia requisições HTTP para as operações do sistema.

    Rotas:
      GET  /, /index.html        → frontend React (ui/dist/index.html)
      GET  /assets/*             → arquivos estáticos do frontend
      GET  /api/history          → lista pesquisas salvas
      GET  /api/history/{id}     → detalhes de uma pesquisa
      POST /api/research         → gera novo relatório
      DELETE /api/history/{id}   → remove pesquisa do histórico
    """

    def _write_json(self, payload: dict, status: int = HTTPStatus.OK) -> None:
        """Serializa o payload como JSON e envia a resposta HTTP."""
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            self.wfile.write(body)
        except BrokenPipeError:
            pass  # Cliente fechou a conexão antes de ler — não é erro nosso
        self.close_connection = True

    def _serve_index(self) -> None:
        """Serve o arquivo index.html do frontend React."""
        static_dir = Path(__file__).parent.parent.parent / "ui" / "dist"
        index_path = static_dir / "index.html"

        if not index_path.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "index.html não encontrado.")
            return

        content = index_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(content)
        self.close_connection = True

    def _resolve_asset_file(self, asset_path: str) -> Path | None:
        """
        Resolve o caminho do asset dentro de ui/dist/assets/ com proteção
        contra path traversal (ex.: /assets/../../../etc/passwd).

        A verificação resolved_asset.relative_to(resolved_static_dir) garante
        que o arquivo resolvido esteja DENTRO do diretório de assets.
        """
        from urllib.parse import unquote

        static_dir = Path(__file__).parent.parent.parent / "ui" / "dist" / "assets"
        resolved_static_dir = static_dir.resolve()
        raw_asset_path = unquote(asset_path)

        if raw_asset_path in {"/assets", "/assets/"}:
            return None

        if raw_asset_path.startswith("/assets/"):
            relative_path = raw_asset_path.removeprefix("/assets/").lstrip("/")
        elif raw_asset_path.startswith("assets/"):
            relative_path = raw_asset_path.removeprefix("assets/").lstrip("/")
        else:
            return None

        resolved_asset = (resolved_static_dir / relative_path).resolve()
        try:
            resolved_asset.relative_to(resolved_static_dir)
        except ValueError:
            return None  # Path traversal detectado
        return resolved_asset if resolved_asset.is_file() else None

    def _serve_asset(self, asset_path: str) -> None:
        """Serve arquivos de assets do frontend estático com content-type adequado."""
        from mimetypes import guess_type

        resolved_asset = self._resolve_asset_file(asset_path)
        if resolved_asset is None:
            self.send_error(HTTPStatus.NOT_FOUND, "Asset não encontrado.")
            return

        content = resolved_asset.read_bytes()
        content_type = guess_type(str(resolved_asset))[0] or "application/octet-stream"
        header_value = (
            f"{content_type}; charset=utf-8"
            if content_type.startswith("text/")
            else content_type
        )
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", header_value)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(content)
        self.close_connection = True

    def do_GET(self) -> None:
        """Roteia requisições GET: frontend, assets, ou API de histórico."""
        path = self.path.split("?", 1)[0]

        # Frontend estático
        if path in ("/", "/index.html"):
            self._serve_index()
            return
        if path == "/assets":
            self._serve_asset("")
            return
        if path.startswith("/assets/"):
            self._serve_asset(path)
            return

        # API: listar histórico
        if path == "/api/history":
            try:
                researches = list_researches()
            except Exception:
                self._write_json(
                    {"error": "Erro ao listar histórico."},
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                )
                return
            self._write_json({"researches": researches})
            return

        # API: detalhes de uma pesquisa
        if path.startswith("/api/history/"):
            try:
                research_id = int(path.split("/api/history/")[1].strip("/"))
            except (ValueError, IndexError):
                self._write_json(
                    {"error": "Id inválido."},
                    status=HTTPStatus.BAD_REQUEST,
                )
                return
            research = get_research(research_id)
            if research is None:
                self._write_json(
                    {"error": "Pesquisa não encontrada."},
                    status=HTTPStatus.NOT_FOUND,
                )
                return
            self._write_json(research)
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Rota não encontrada.")

    def do_POST(self) -> None:
        """
        Gera um novo relatório de pesquisa.

        Fluxo:
          1. Lê o JSON do corpo da requisição
          2. Extrai o tópico
          3. Chama generate_report (que orquestra busca de fontes + IA)
          4. Retorna o relatório ao cliente
          5. Tenta salvar no histórico (falha não quebra a resposta)
        """
        if self.path != "/api/research":
            self.send_error(HTTPStatus.NOT_FOUND, "Rota não encontrada.")
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            data = json.loads(body.decode("utf-8")) if body else {}
        except (ValueError, json.JSONDecodeError):
            self._write_json({"error": "JSON inválido."}, status=HTTPStatus.BAD_REQUEST)
            return

        topic = str(data.get("topic", "")).strip()
        if not topic:
            self._write_json(
                {"error": "Informe um tópico de pesquisa."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        try:
            report = generate_report(topic)
        except RuntimeError as err:
            self._write_json({"error": str(err)}, status=HTTPStatus.BAD_GATEWAY)
            return

        self._write_json({"topic": topic, "report": report})

        # Persistência do histórico é secundária — se falhar (ex.: permissão
        # de disco), o relatório já foi entregue ao cliente.
        try:
            save_research(topic, report)
        except Exception:
            pass

    def do_DELETE(self) -> None:
        """Remove uma pesquisa do histórico pelo ID."""
        path = self.path.split("?", 1)[0]

        if not path.startswith("/api/history/"):
            self.send_error(HTTPStatus.NOT_FOUND, "Rota não encontrada.")
            return

        try:
            research_id = int(path.split("/api/history/")[1].strip("/"))
        except (ValueError, IndexError):
            self._write_json(
                {"error": "Id inválido."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        deleted = delete_research(research_id)
        if not deleted:
            self._write_json(
                {"error": "Pesquisa não encontrada."},
                status=HTTPStatus.NOT_FOUND,
            )
            return

        self._write_json({"deleted": True})
