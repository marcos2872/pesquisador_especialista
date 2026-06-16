#!/usr/bin/env python3
"""Servidor HTTP simples para a plataforma de pesquisa com IA."""

import os
import sys
from http.server import ThreadingHTTPServer

from config import HOST, PORT
from handlers.research_handler import ResearchHandler


def main() -> None:
    """Inicializa o servidor HTTP."""
    server = ThreadingHTTPServer((HOST, PORT), ResearchHandler)
    print(f"Servidor ativo em http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
