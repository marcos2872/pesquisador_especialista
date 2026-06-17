#!/usr/bin/env python3
"""
Módulo de fetch e extração de conteúdo de URLs.

Responsabilidades:
  1. Baixar HTML e PDF de URLs
  2. Extrair texto limpo (removendo scripts, styles, tags)
  3. Validar relevância de URLs contra um tópico (via Crossref ou
     análise de conteúdo)
  4. Extrair trechos literais (snippets) ao redor de keywords para
     citações com aspas no relatório
  5. Gerar variantes de query (PT→EN, com conectores)

Usamos urllib padrão (sem requests) para evitar dependências.
Para PDFs, tentamos usar PyMuPDF (fitz) se disponível; caso contrário,
fazemos fallback para extração de texto bruto.
"""

import json
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

logger = logging.getLogger("pesquisador.fetcher")

# Stopwords en/pt — palavras comuns que não agregam relevância
_STOPWORDS = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "of",
    "for",
    "in",
    "on",
    "at",
    "to",
    "from",
    "by",
    "with",
    "about",
    "as",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "o",
    "a",
    "os",
    "as",
    "um",
    "uma",
    "de",
    "do",
    "da",
    "dos",
    "das",
    "em",
    "no",
    "na",
    "nos",
    "nas",
    "por",
    "para",
    "com",
    "sem",
    "sobre",
    "entre",
    "e",
    "ou",
    "que",
    "se",
    "como",
    "mas",
    "mais",
    "menos",
    "muito",
    "pouco",
}

_CROSSREF_USER_AGENT = "PesquisadorEspecialista/1.0 (mailto:pesquisador@example.com)"
DEFAULT_TIMEOUT = int(os.getenv("SEARCH_TIMEOUT_SECONDS", "30"))
USER_AGENT = "Mozilla/5.0 (compatible; PesquisadorEspecialista/1.0)"


def _make_request(url: str, timeout: int = DEFAULT_TIMEOUT) -> tuple[int, bytes]:
    """Faz requisição HTTP GET e retorna (status_code, body)."""
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
    """Remove tags HTML/script/style e retorna texto limpo."""
    try:
        text = html.decode("utf-8", errors="ignore")
    except Exception:
        return ""
    # Remove scripts e styles primeiro (conteúdo entre tags)
    text = re.sub(
        r"<script[^>]*>.*?</script>", "", text, flags=re.IGNORECASE | re.DOTALL
    )
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.IGNORECASE | re.DOTALL)
    # Remove tags HTML restantes
    text = re.sub(r"<[^>]+>", " ", text)
    # Normaliza espaços em branco
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _extract_text_from_pdf(data: bytes) -> str:
    """Extrai texto de PDF usando PyMuPDF (fitz) se disponível."""
    try:
        import fitz
    except ImportError:
        # Fallback: decodifica como texto bruto (pouca qualidade)
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
    Baixa o conteúdo de uma URL (HTML ou PDF) e retorna o texto extraído.

    Returns:
        (sucesso, texto, mensagem_de_erro)
    """
    status, content = _make_request(url, timeout=timeout)
    if status == 0:
        return False, "", "Falha de conexão (timeout ou DNS)"
    if status >= 400:
        return False, "", f"HTTP {status}"
    parsed = urlparse(url)
    path = parsed.path.lower()
    if path.endswith(".pdf"):
        text = _extract_text_from_pdf(content)
    else:
        text = _extract_text_from_html(content)
    text = re.sub(r"\[sem validação externa\]", "", text, flags=re.IGNORECASE)
    return True, text[:50_000], ""


def _extract_keywords(topic: str) -> set[str]:
    """Extrai palavras-chave relevantes do tópico (remove stopwords e tokens curtos)."""
    cleaned = re.sub(r"[^\w\s/\-]", " ", topic.lower())
    tokens = re.split(r"[\s/]+", cleaned)
    keywords = {
        token.strip("-\n")
        for token in tokens
        if len(token.strip("-\n")) >= 3 and token.strip("-\n") not in _STOPWORDS
    }
    return keywords


def _content_matches_topic(
    text: str, topic_keywords: set[str], min_matches: int = 2
) -> bool:
    """
    Verifica se o texto contém keywords do tópico.

    Usamos um mínimo de matches proporcional ao número de keywords
    para evitar falsos positivos com textos muito curtos.
    """
    if not text or not topic_keywords:
        return False
    text_lower = text.lower()
    matches = {kw for kw in topic_keywords if kw in text_lower}
    return len(matches) >= min(min_matches, len(topic_keywords))


def _extract_doi(url: str) -> Optional[str]:
    """Extrai DOI de uma URL ou string, se presente."""
    lower = url.lower()
    if "doi.org/" in lower:
        return url.split("doi.org/", 1)[1].split("?", 1)[0].strip("/")
    # Tenta encontrar padrão DOI (10.xxxx/xxxxx) diretamente no texto
    match = re.search(r"10\.\d{4,}/[^\s\)\"']+", url)
    return match.group(0) if match else None


def _validate_doi_via_crossref(
    doi: str, topic_keywords: set[str], timeout: int
) -> tuple[bool, str]:
    """
    Valida um DOI consultando a API da Crossref.

    Verifica:
      1. Se o DOI existe na Crossref
      2. Se o título/abstract do trabalho contém keywords do tópico
         (relevância temática)
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
    Valida se uma URL é acessível e relevante ao tópico.

    Estratégia:
      1. Se a URL contém DOI → valida via Crossref (rápido e confiável)
      2. Senão → baixa o conteúdo e verifica se contém keywords do tópico

    Returns:
        (é_válida, motivo_da_rejeição)
    """
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return False, "URL malformada"
    topic_keywords = _extract_keywords(topic)
    doi = _extract_doi(url)
    if doi:
        return _validate_doi_via_crossref(doi, topic_keywords, timeout)
    # Para URLs não-DOI, baixa e analisa o conteúdo
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


_MAX_SNIPPET_CHARS = 1200
_MAX_SNIPPETS_PER_SOURCE = 5
_CONTEXT_WINDOW = 80


def _extract_snippets_around_keywords(
    text: str,
    keywords: set[str],
    max_snippets: int = _MAX_SNIPPETS_PER_SOURCE,
    context_window: int = _CONTEXT_WINDOW,
) -> list[str]:
    """
    Extrai trechos literais ao redor de keywords no texto.

    Cada snippet contém a keyword com ~80 caracteres de contexto de cada
    lado. Os snippets são usados para citações literais no relatório,
    permitindo que o modelo cite trechos exatos com aspas.

    Evita snippets duplicados controlando spans já vistos.
    """
    if not text or not keywords:
        return []
    text_lower = text.lower()
    snippets: list[str] = []
    seen_spans: set[tuple[int, int]] = set()
    for kw in keywords:
        start = 0
        while len(snippets) < max_snippets:
            idx = text_lower.find(kw, start)
            if idx == -1:
                break
            snippet_start = max(0, idx - context_window)
            snippet_end = min(len(text), idx + len(kw) + context_window)
            span = (snippet_start, snippet_end)
            if span not in seen_spans:
                seen_spans.add(span)
                snippet = text[snippet_start:snippet_end].strip()
                # Adiciona marcadores de truncamento
                if snippet_start > 0:
                    snippet = "…" + snippet
                if snippet_end < len(text):
                    snippet = snippet + "…"
                if len(snippet) >= 40:
                    snippets.append(snippet)
            start = idx + len(kw)
    return snippets


def _deduplicate_snippets(snippets: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for s in snippets:
        key = s[50:150] if len(s) > 50 else s
        if key not in seen:
            seen.add(key)
            result.append(s)
    return result


def _build_expanded_queries(topic: str) -> list[str]:
    """
    Gera múltiplas variantes de query a partir do tópico.

    Inclui:
      - Query original em PT
      - Tradução para EN (via dicionário de termos técnicos)
      - Combinações com conectores ("review", "recent advances", etc.)

    O dicionário de tradução cobre termos comuns de materiais, engenharia
    e ciência para melhorar a cobertura em APIs internacionais.
    """
    translations = {
        "ligas": "alloys",
        "alumínio": "aluminum",
        "aluminio": "aluminum",
        "grafeno": "graphene",
        "compósitos": "composites",
        "compositos": "composites",
        "polímero": "polymer",
        "polimero": "polymer",
        "nanocompósitos": "nanocomposites",
        "nanocompositos": "nanocomposites",
        "baterias": "batteries",
        "revestimento": "coating",
        "extrusora": "extruder",
        "manufatura": "manufacturing",
        "aditiva": "additive",
        "impressão": "printing",
        "3d": "3d",
        "biomateriais": "biomaterials",
        "células": "cells",
        "aço": "steel",
        "aco": "steel",
        "cerâmica": "ceramic",
        "ceramica": "ceramic",
        "soldagem": "welding",
        "corrosão": "corrosion",
        "corrosao": "corrosion",
        "térmico": "thermal",
        "termico": "thermal",
        "mecânico": "mechanical",
        "mecanico": "mechanical",
        "elétrico": "electrical",
        "eletrico": "electrical",
        "superfície": "surface",
        "superficie": "surface",
        "tratamento": "treatment",
        "simulação": "simulation",
        "simulacao": "simulation",
        "modelagem": "modeling",
        "otimização": "optimization",
        "otimizacao": "optimization",
        "sensores": "sensors",
        "catálise": "catalysis",
        "catalise": "catalysis",
        "fotovoltaico": "photovoltaic",
        "hidrogênio": "hydrogen",
        "hidrogenio": "hydrogen",
        "biomedicina": "biomedical",
        "fármaco": "drug",
        "farmaco": "drug",
        "entrega": "delivery",
        "tecido": "tissue",
        "ósseo": "bone",
        "osseo": "bone",
        "regeneração": "regeneration",
        "regeneracao": "regeneration",
        "membrana": "membrane",
        "filtração": "filtration",
        "filtracao": "filtration",
        "adsorção": "adsorption",
        "adsorcao": "adsorption",
        "catodo": "cathode",
        "anodo": "anode",
        "eletrólito": "electrolyte",
        "eletrolito": "electrolyte",
        "robótica": "robotics",
        "robotica": "robotics",
        "inteligência": "intelligence",
        "inteligencia": "intelligence",
        "artificial": "artificial",
        "aprendizado": "learning",
        "máquina": "machine",
        "maquina": "machine",
        "profundo": "deep",
        "rede": "network",
        "neural": "neural",
        "processamento": "processing",
        "linguagem": "language",
        "natural": "natural",
        "visão": "vision",
        "visao": "vision",
        "computacional": "computational",
    }
    english_tokens: list[str] = []
    for word in re.split(r"[\s/]+", topic.lower().strip()):
        english_tokens.append(translations.get(word, word))
    english_topic = " ".join(english_tokens)
    queries = [topic.strip(), english_topic]
    for connector in (
        "paper",
        "review",
        "systematic review",
        "literature review",
        "standard approach",
        "overview",
        "recent advances",
        "state of the art",
        "properties",
        "applications",
        "synthesis",
        "characterization",
    ):
        queries.append(f"{english_topic} {connector}")
    # Remove duplicatas mantendo ordem
    seen: set[str] = set()
    unique: list[str] = []
    for q in queries:
        q_clean = q.strip()
        if q_clean and q_clean.lower() not in seen:
            seen.add(q_clean.lower())
            unique.append(q_clean)
    return unique[:10]


def generate_query_variants(topic: str) -> list[str]:
    return _build_expanded_queries(topic)


def download_source_texts(
    sources: list[dict],
    topic: str,
    timeout: int = DEFAULT_TIMEOUT,
    max_workers: int = 3,
) -> list[dict]:
    if not sources:
        return sources
    keywords = _extract_keywords(topic)
    if not keywords:
        return sources

    def _fetch_one(source: dict) -> dict:
        result = dict(source)
        result.setdefault("snippets", [])
        urls_to_try = []
        for key in ("pdf_url", "url"):
            val = source.get(key)
            if val and isinstance(val, str) and val.startswith("http"):
                urls_to_try.append(val)
        for url in urls_to_try:
            if result["snippets"]:
                break
            success, text, _ = fetch_url(url, timeout=timeout)
            if not success or not text:
                continue
            raw_snippets = _extract_snippets_around_keywords(text, keywords)
            result["snippets"] = _deduplicate_snippets(raw_snippets)
            if result["snippets"]:
                logger.debug(
                    "%d snippets extraídos de %s",
                    len(result["snippets"]),
                    source.get("title", url)[:80],
                )
        return result

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_fetch_one, s): i for i, s in enumerate(sources)}
        enriched = [dict(s) for s in sources]
        for future in as_completed(futures):
            idx = futures[future]
            try:
                enriched[idx] = future.result()
            except Exception as exc:
                logger.warning(
                    "Falha ao baixar fonte %s: %s",
                    sources[idx].get("title", "?")[:80],
                    exc,
                )
    return enriched


def validate_quoted_citations(
    report: str,
    source_snippets: dict[str, list[str]],
) -> tuple[str, list[str]]:
    quote_pattern = re.compile(r'"([^"]{30,})"')
    all_snippets: list[str] = []
    for snippets in source_snippets.values():
        all_snippets.extend(snippets)
    if not all_snippets:
        return report, []
    warnings: list[str] = []
    sanitized = report
    for match in quote_pattern.finditer(report):
        quote = match.group(1)
        found = False
        search_key = quote[:60].lower() if len(quote) > 60 else quote.lower()
        for snippet in all_snippets:
            if search_key in snippet.lower():
                found = True
                break
        if not found:
            warnings.append(
                f'Citação não verificada: "{quote[:80]}{"..." if len(quote) > 80 else ""}"'
            )
            sanitized = sanitized.replace(
                f'"{quote}"', f'"{quote}" [citação não verificada na fonte]'
            )
    return sanitized, warnings
