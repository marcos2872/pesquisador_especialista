"""Configurações da aplicação carregadas do ambiente."""

import os
from pathlib import Path

# Diretórios base
BASE_DIR = Path(__file__).parent.resolve()
STATIC_DIR = BASE_DIR / "static"
AGENT_DIR = BASE_DIR / "agent"

# Prompts
PROMPT_TEMPLATE_PATH = AGENT_DIR / "systemprompt.md"
USER_PROMPT_PATH = AGENT_DIR / "userprompt.md"


def load_prompt_template() -> str:
    """Carrega o template do prompt de sistema."""
    if PROMPT_TEMPLATE_PATH.exists():
        return PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8").strip()
    return (
        "Você é um pesquisador especialista em revisão técnica, pesquisa de anterioridade, "
        "patentes e análise de lacunas de P&D."
    )


def load_user_prompt_template() -> str:
    """Carrega o template do prompt do usuário."""
    if USER_PROMPT_PATH.exists():
        return USER_PROMPT_PATH.read_text(encoding="utf-8").strip()
    return "Tema da pesquisa: {topic}"


def build_user_prompt(topic: str, sources_context: str = "") -> str:
    """Constrói o prompt do usuário com o tópico e contexto de fontes."""
    base = load_user_prompt_template().replace("{topic}", topic)
    if sources_context:
        return (
            f"{base}\n\n--- CONTEXTO DE FONTES VERIFICADAS ---\n{sources_context}\n---\n"
            "Use SOMENTE as fontes do contexto acima para embasar o relatório. "
            "Não adicione fontes externas.\n"
        )
    return base


def build_retry_prompt(topic: str) -> str:
    """Constrói o prompt de retry quando a validação de fontes falha."""
    return (
        f"Tema da pesquisa: {topic}\n\n"
        "A tentativa anterior falhou porque os links fornecidos não puderam ser "
        "verificados como fontes reais e relevantes ao tema.\n\n"
        "Execute a pesquisa novamente, mas desta vez:\n"
        "- Cite APENAS fontes que você conhece com certeza e consegue referenciar com precisão.\n"
        "- NÃO invente DOIs, números de patente, títulos, autores ou URLs.\n"
        "- NÃO use links de homepages de bases de dados (ex.: https://worldwide.espacenet.com sem número de patente).\n"
        "- Use SOMENTE links diretos: https://doi.org/10.xxxx/xxxxx ou https://patents.google.com/patent/NUMERO/en.\n"
        "- Prefira DOIs de artigos consolidados e patentes de jurisdições principais (US/EP/WO) que você saiba que existem.\n"
        "- Se não souber uma fonte específica, reduza o escopo do parágrafo ou omita a afirmação.\n"
        "- Entregue exatamente a mesma estrutura de 6 seções.\n"
        "- Use obrigatoriamente links diretos no formato [Fonte](URL/DOI/patente).\n"
        "- Seção 6 deve listar somente as fontes realmente citadas no texto."
    )


# Configurações de servidor
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))

# Configurações OpenAI
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
OPENAI_DEBUG = os.getenv("OPENAI_DEBUG", "0") == "1"
OPENAI_TIMEOUT_SECONDS = int(os.getenv("OPENAI_TIMEOUT_SECONDS", "240"))

# Configurações de busca
ENABLE_REAL_SEARCH = os.getenv("ENABLE_REAL_SEARCH", "1") == "1"
