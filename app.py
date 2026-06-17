#!/usr/bin/env python3
"""Servidor HTTP simples para a plataforma de pesquisa com IA.

Este módulo delega para server.app para manter compatibilidade com
imports diretos (ex.: testes, scripts).
"""

from server.app import main

if __name__ == "__main__":
    main()
