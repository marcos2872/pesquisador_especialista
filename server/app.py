#!/usr/bin/env python3
"""
Ponto de entrada do servidor HTTP.

Usamos http.server.ThreadigHTTPServer (stdlib) em vez de Flask/FastAPI
para manter zero dependências de framework web. Cada requisição roda em
uma thread separada, o que é suficiente para uma API de uso interno com
baixa concorrência.

O .env é carregado antes de qualquer outro import para que as variáveis
de ambiente (OPENAI_API_KEY, etc.) estejam disponíveis desde o início.
"""

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
    """Inicializa o servidor HTTP na porta/config especificada."""
    server = ThreadingHTTPServer((HOST, PORT), ResearchHandler)
    print(f"Servidor ativo em http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
