#!/usr/bin/env python3
"""Ponto de entrada para execução da aplicação."""

import subprocess
import sys


def run_app():
    """Executa a aplicação via app.py."""
    subprocess.run([sys.executable, "app.py"], check=True)


if __name__ == "__main__":
    run_app()
