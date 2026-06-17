"""
Serviço de banco de dados SQLite para histórico de pesquisas.

Usamos SQLite diretamente (sem ORM) para manter zero dependências.
O banco fica em ~/.pesquisador/history.db — um arquivo local por usuário.

A connection factory _get_connection() garante que o diretório e a
tabela existam antes de qualquer operação, eliminando a necessidade
de um script de migração separado.
"""

import sqlite3
from pathlib import Path

# Banco localizado no home do usuário para persistência entre execuções
DB_PATH = Path.home() / ".pesquisador" / "history.db"

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS researches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT NOT NULL,
    report TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""


def _get_connection() -> sqlite3.Connection:
    """
    Retorna conexão com o banco, criando diretório e tabela se necessário.

    Usamos row_factory=sqlite3.Row para acessar colunas por nome (ex.:
    row["topic"]) em vez de índice numérico, melhorando a legibilidade.
    O bloco try/except no CREATE TABLE lida com race conditions em
    ambientes concorrentes.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(_CREATE_TABLE_SQL)
        conn.commit()
    except sqlite3.OperationalError:
        conn.execute(_CREATE_TABLE_SQL)
        conn.commit()
    return conn


def save_research(topic: str, report: str) -> int:
    """
    Salva uma pesquisa no banco e retorna seu id.

    Args:
        topic: Tópico da pesquisa
        report: Relatório gerado em Markdown

    Returns:
        Id do registro inserido
    """
    conn = _get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO researches (topic, report) VALUES (?, ?)",
            (topic, report),
        )
        conn.commit()
        return cursor.lastrowid or 0
    finally:
        conn.close()


def list_researches(limit: int = 50) -> list[dict]:
    """
    Lista pesquisas ordenadas pela data de criação (mais recentes primeiro).

    Args:
        limit: Número máximo de registros retornados

    Returns:
        Lista de dicionários com chaves id, topic e created_at
    """
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT id, topic, created_at FROM researches ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            {
                "id": row["id"],
                "topic": row["topic"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]
    finally:
        conn.close()


def get_research(research_id: int) -> dict | None:
    """
    Retorna uma pesquisa específica pelo id.

    Args:
        research_id: Id da pesquisa

    Returns:
        Dicionário com chaves id, topic, report e created_at, ou None se não encontrado
    """
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT id, topic, report, created_at FROM researches WHERE id = ?",
            (research_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "topic": row["topic"],
            "report": row["report"],
            "created_at": row["created_at"],
        }
    finally:
        conn.close()


def delete_research(research_id: int) -> bool:
    """
    Deleta uma pesquisa pelo id.

    Args:
        research_id: Id da pesquisa a ser removida

    Returns:
        True se um registro foi removido, False se o id não existia
    """
    conn = _get_connection()
    try:
        cursor = conn.execute(
            "DELETE FROM researches WHERE id = ?", (research_id,)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()
