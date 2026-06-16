"""Handler de requisições HTTP para a API de pesquisa."""

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler

from services.research_service import generate_report

from services.report_service import sanitize_report_links
from services.source_service import validate_report_sources


class ResearchHandler(BaseHTTPRequestHandler):
    """Handler para rotas da aplicação."""

    def _write_json(self, payload: dict, status: int = HTTPStatus.OK) -> None:
        """Envia resposta JSON."""
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def _serve_index(self) -> None:
        """Serve o arquivo index.html estático."""
        import os
        from pathlib import Path

        static_dir = Path(__file__).parent.parent / "static"
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

    def do_GET(self) -> None:
        """Processa requisições GET."""
        if self.path in ("/", "/index.html"):
            self._serve_index()
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Rota não encontrada.")

    def do_POST(self) -> None:
        """Processa requisições POST para /api/research."""
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
