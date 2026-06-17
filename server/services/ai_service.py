"""Serviço de IA - Integração com OpenAI/Azure."""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from server.config import build_retry_prompt, build_user_prompt, load_prompt_template


def extract_openai_text(data: dict) -> str:
    """Extrai texto de diferentes formatos de payload da OpenAI."""
    output_text = data.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    output = data.get("output")
    if isinstance(output, list):
        chunks = []
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if not isinstance(part, dict):
                    continue
                if part.get("type") == "output_text" and isinstance(
                    part.get("text"), str
                ):
                    text = part["text"].strip()
                    if text:
                        chunks.append(text)
        if chunks:
            return "\n\n".join(chunks)

    # Fallback para chat completions
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
        if isinstance(content, list):
            chunks = []
            for part in content:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    text = part["text"].strip()
                    if text:
                        chunks.append(text)
            if chunks:
                return "\n\n".join(chunks)

    return ""


def call_openai(
    topic: str,
    sources_context: str = "",
    retry: bool = False,
    prompt_template: str = "",
) -> str:
    """Faz chamada à API OpenAI/Azure e retorna o texto gerado."""
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")

    if not api_key:
        raise RuntimeError("OPENAI_API_KEY não configurada.")

    # Usa os builders do config
    if retry:
        user_content = build_retry_prompt(topic)
    else:
        user_content = build_user_prompt(topic, sources_context)

    # Usa o template do config
    if not prompt_template:
        prompt_template = load_prompt_template()

    payload = {
        "model": model,
        "input": [
            {"role": "system", "content": prompt_template},
            {"role": "user", "content": user_content},
        ],
    }

    is_azure = ".openai.azure.com" in base_url
    headers = {"Content-Type": "application/json"}
    if is_azure:
        headers["api-key"] = api_key
    else:
        headers["Authorization"] = f"Bearer {api_key}"

    req = Request(
        f"{base_url}/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    request_timeout = int(os.getenv("OPENAI_TIMEOUT_SECONDS", "240"))
    try:
        with urlopen(req, timeout=request_timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as err:
        body = err.read().decode("utf-8", errors="ignore")
        if err.code == 404:
            raise RuntimeError(
                f"Modelo '{model}' não encontrado no endpoint '{base_url}'. "
                "Verifique OPENAI_MODEL e OPENAI_BASE_URL."
            ) from err
        raise RuntimeError(f"Falha OpenAI ({err.code}): {body}") from err
    except URLError as err:
        raise RuntimeError(f"Falha de conexão OpenAI: {err.reason}") from err

    text = extract_openai_text(data)
    if text:
        return text

    if os.getenv("OPENAI_DEBUG") == "1":
        raw = json.dumps(data, ensure_ascii=False)[:2500]
        raise RuntimeError(
            "Resposta da OpenAI sem texto utilizável. "
            f"Chaves: {list(data.keys())}. Raw (truncado): {raw}"
        )
    raise RuntimeError(
        "Resposta da OpenAI sem texto utilizável. "
        "Defina OPENAI_DEBUG=1 para ver o payload retornado."
    )
