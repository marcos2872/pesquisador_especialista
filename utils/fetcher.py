#!/usr/bin/env python3
"""
Módulo responsável por baixar e extrair texto de URLs (HTML e PDF).
"""

import json
import os
import re
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

# Palavras comuns em inglês/português que não ajudam na relevância
_STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "for", "in", "on", "at", "to", "from",
    "by", "with", "about", "as", "is", "are", "was", "were", "be", "been",
    "o", "a", "os", "as", "um", "uma", "de", "do", "da", "dos", "das", "em",
    "no", "na", "nos", "nas", "por", "para", "com", "sem", "sobre", "entre",
    "e", "ou", "que", "se", "como", "mas", "mais", "menos", "muito", "pouco",
}

# User-agent exigido/recomendado pela Crossref API
_CROSSREF_USER_AGENT = "PesquisadorEspecialista/1.0 (mailto:pesquisador@example.com)"

# Timeout padrão para requisições (segundos)
DEFAULT_TIMEOUT = int(os.getenv("OPENAI_TIMEOUT_SECONDS", "30"))

# User-agent para evitar bloqueio básico
USER_AGENT = "Mozilla/5.0 (compatible; PesquisadorEspecialista/1.0)"


def _make_request(url: str, timeout: int = DEFAULT_TIMEOUT) -> tuple[int, bytes]:
    """
    Faz uma requisição HTTP GET com timeout e retorna (status_code, content).
    """
    headers = {"User-Agent": USER_AGENT}
    req = Request(url, headers=headers, method="GET")
    try:
        with urlopen(req, timeout=timeout) as response:
            return response.status, response.read()
    except HTTPError as e:
        return e.code, b""
    except URLError:
        return 0, b""


def _extract_text_from_html(html: bytes) -> str:
    """
    Extrai texto de conteúdo HTML simples, removendo scripts, estilos e tags.
    """
    try:
        text = html.decode("utf-8", errors="ignore")
    except Exception:
        return ""

    # Remove blocos de script e style
    text = re.sub(
        r"<script[^>]*>.*?</script>", "", text, flags=re.IGNORECASE | re.DOTALL
    )
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.IGNORECASE | re.DOTALL)

    # Remove todas as tags HTML
    text = re.sub(r"<[^>]+>", " ", text)

    # Normaliza espaços e quebras de linha
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _extract_text_from_pdf(data: bytes) -> str:
    """
    Extrai texto de conteúdo PDF usando PyMuPDF (fitz), com fallback para texto bruto.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        # Fallback: tenta decodificar como texto bruto
        return data.decode("utf-8", errors="ignore")

    try:
        doc = fitz.open("pdf", data)
        texts = []
        for page in doc:
            texts.append(page.get_text("text"))
        return "\n".join(texts).strip()
    except Exception:
        return data.decode("utf-8", errors="ignore")


def fetch_url(url: str, timeout: int = DEFAULT_TIMEOUT) -> tuple[bool, str, str]:
    """
    Baixa o conteúdo de uma URL e extrai o texto principal.

    Retorna:
        tuple: (success, text, error_message)
            - success: True se conseguiu baixar e extrair texto.
            - text: Texto extraído (ou string vazia em caso de erro).
            - error_message: Mensagem de erro (ou string vazia em caso de sucesso).
    """
    status, content = _make_request(url, timeout=timeout)

    if status == 0:
        return False, "", "Falha de conexão (timeout ou DNS)"
    if status >= 400:
        return False, "", f"HTTP {status}"

    # Determina o tipo de conteúdo
    parsed = urlparse(url)
    path = parsed.path.lower()

    if path.endswith(".pdf"):
        text = _extract_text_from_pdf(content)
    else:
        text = _extract_text_from_html(content)

    # Remove marcas de [sem validação externa] que possam ter sido baixadas
    text = re.sub(r"\[sem validação externa\]", "", text, flags=re.IGNORECASE)

    return True, text[:50_000], ""  # Limita tamanho para não exceder tokens


def _extract_keywords(topic: str) -> set[str]:
    """
    Extrai palavras-chave significativas de um tópico de pesquisa.
    Remove stopwords, termos muito curtos e duplicatas.
    """
    # Mantém termos técnicos compostos separados por hífen/barra e quebra em tokens
    cleaned = re.sub(r"[^\w\s/\-]", " ", topic.lower())
    tokens = re.split(r"[\s/]+", cleaned)
    keywords = {
        token.strip("-\n")
        for token in tokens
        if len(token.strip("-\n")) >= 3 and token.strip("-\n") not in _STOPWORDS
    }
    return keywords


def _content_matches_topic(text: str, topic_keywords: set[str], min_matches: int = 2) -> bool:
    """
    Verifica se o texto baixado contém palavras-chave do tema.
    Exige pelo menos min_matches palavras distintas para considerar relevante.
    """
    if not text or not topic_keywords:
        return False
    text_lower = text.lower()
    matches = {kw for kw in topic_keywords if kw in text_lower}
    return len(matches) >= min(min_matches, len(topic_keywords))


def _extract_doi(url: str) -> Optional[str]:
    """Extrai o DOI de uma URL doi.org ou similar, se houver."""
    lower = url.lower()
    if "doi.org/" in lower:
        return url.split("doi.org/", 1)[1].split("?", 1)[0].strip("/")
    match = re.search(r"10\.\d{4,}/[^\s\)\"']+", url)
    return match.group(0) if match else None


def _validate_doi_via_crossref(doi: str, topic_keywords: set[str], timeout: int) -> tuple[bool, str]:
    """
    Valida um DOI usando a API Crossref e verifica relevância pelo título/resumo.
    """
    api_url = f"https://api.crossref.org/works/{doi}"
    headers = {"User-Agent": _CROSSREF_USER_AGENT, "Accept": "application/json"}
    req = Request(api_url, headers=headers, method="GET")
    try:
        with urlopen(req, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as err:
        if err.code == 404:
            return False, "DOI não encontrado na Crossref"
        return False, f"Erro na Crossref ({err.code})"
    except URLError:
        return False, "Falha de conexão com a Crossref"
    except json.JSONDecodeError:
        return False, "Resposta inválida da Crossref"

    work = data.get("message", {})
    title = " ".join(work.get("title", []))
    abstract = work.get("abstract", "")
    text = f"{title} {abstract}".lower()

    if not _content_matches_topic(text, topic_keywords, min_matches=2):
        return False, "DOI existe, mas o conteúdo não parece relacionado ao tema"

    return True, ""


def validate_url_relevance(
    url: str, topic: str, timeout: int = DEFAULT_TIMEOUT
) -> tuple[bool, str]:
    """
    Verifica se uma URL é acessível e se seu conteúdo é relevante ao tema.

    Retorna:
        tuple: (is_valid, reason)
            - is_valid: True se a URL responde e parece relevante ao tema.
            - reason: mensagem explicativa quando inválida (vazia quando válida).
    """
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return False, "URL malformada"

    topic_keywords = _extract_keywords(topic)

    # DOIs: validamos via Crossref (aberto e confiável), evitando bloqueios 403 de publishers.
    doi = _extract_doi(url)
    if doi:
        return _validate_doi_via_crossref(doi, topic_keywords, timeout)

    # URLs de patentes e demais links: fazemos requisição direta e verificamos relevância.
    status, content = _make_request(url, timeout=timeout)

    if status == 0:
        return False, "Falha de conexão (timeout ou DNS)"
    if status == 404:
        return False, "Link não encontrado (404)"
    if status >= 400:
        return False, f"Erro HTTP {status}"

    path = parsed.path.lower()
    is_pdf = path.endswith(".pdf")

    if is_pdf:
        text = _extract_text_from_pdf(content)
    else:
        text = _extract_text_from_html(content)

    if not _content_matches_topic(text, topic_keywords):
        return False, "Conteúdo da URL não parece relacionado ao tema"

    return True, ""
