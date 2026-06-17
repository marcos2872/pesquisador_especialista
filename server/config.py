"""
Configurações da aplicação carregadas do ambiente.

Centralizamos todas as variáveis de ambiente aqui em vez de espalhá-las
pelos módulos. Isso facilita encontrar, documentar e testar cada config.

Usamos dotenv para carregar .env automaticamente (feito em app.py antes
de qualquer outro import).
"""

import os
from pathlib import Path

# ── Diretórios base do projeto ──────────────────────────────────────────
# BASE_DIR é a raiz do projeto (um nível acima de server/).
# STATIC_DIR aponta para ui/dist/ — o build de produção do frontend React.
# AGENT_DIR contém os templates de prompt (systemprompt.md, userprompt.md).
BASE_DIR = Path(__file__).parent.parent.resolve()
STATIC_DIR = BASE_DIR / "ui" / "dist"
AGENT_DIR = Path(__file__).parent.resolve() / "prompts"

# ── Caminhos dos prompts ────────────────────────────────────────────────
# Mantemos os prompts em arquivos .md separados para edição independente
# do código Python. Se os arquivos não existirem, usamos fallback hardcoded.
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
    """
    Constrói o prompt final do usuário.

    Se houver fontes reais coletadas, injeta o contexto estruturado entre
    marcadores --- para que o modelo entenda que deve usar SOMENTE aquelas
    fontes e não inventar referências.
    """
    base = load_user_prompt_template().replace("{topic}", topic)
    if sources_context:
        return (
            f"{base}\n\n--- CONTEXTO DE FONTES VERIFICADAS ---\n{sources_context}\n---\n"
            "Use SOMENTE as fontes do contexto acima para embasar o relatório. "
            "Não adicione fontes externas.\n"
        )
    return base


def build_retry_prompt(topic: str) -> str:
    """
    Constrói o prompt para a segunda tentativa (retry).

    Quando a validação de fontes falha na primeira tentativa (links
    inválidos ou irrelevantes), enviamos instruções mais rígidas para
    que o modelo seja mais conservador ao citar fontes.
    """
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


# ── Servidor HTTP ──────────────────────────────────────────────────────
# HOST e PORT definem onde o ThreadingHTTPServer escuta. Em produção,
# use 0.0.0.0:8000; em desenvolvimento local, 127.0.0.1:8000.
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))

# ── OpenAI / Azure OpenAI ───────────────────────────────────────────────
# OPENAI_BASE_URL pode apontar para Azure OpenAI (ex.: https://meu-recurso.openai.azure.com)
# ou para qualquer endpoint compatível com a API da OpenAI.
# OPENAI_MODEL: nome do deployment no Azure ou model ID na OpenAI.
# OPENAI_DEBUG=1 exibe o payload bruto retornado em caso de erro.
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
OPENAI_DEBUG = os.getenv("OPENAI_DEBUG", "1") == "1"
OPENAI_TIMEOUT_SECONDS = int(os.getenv("OPENAI_TIMEOUT_SECONDS", "240"))

# ── Busca de fontes reais ──────────────────────────────────────────────
# Quando ENABLE_REAL_SEARCH=0, o sistema pula a coleta de fontes via APIs
# (Crossref, arXiv, etc.) e manda o tópico diretamente para a IA. Útil
# para testes rápidos ou quando não há acesso à internet.
ENABLE_REAL_SEARCH = os.getenv("ENABLE_REAL_SEARCH", "1") == "1"
