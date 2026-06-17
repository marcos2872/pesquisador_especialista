#!/usr/bin/env python3
"""Servidor HTTP simples para a plataforma de pesquisa com IA."""

import os
import sys
from http.server import ThreadingHTTPServer
from pathlib import Path

from dotenv import load_dotenv

# Carrega .env automaticamente (procura no diretório do projeto)
_env_file = Path(__file__).parent.parent / ".env"
if _env_file.exists():
    load_dotenv(_env_file)

from .config import HOST, PORT
from .handlers.research_handler import ResearchHandler


def main() -> None:
    """Inicializa o servidor HTTP."""
    server = ThreadingHTTPServer((HOST, PORT), ResearchHandler)
    print(f"Servidor ativo em http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
