"""
Chamada ao provedor de IA generativa, isolada num módulo próprio — é a
"camada de integração" da arquitetura descrita no TCC I (seção 2.3.3):
trocar de provedor significa mexer só aqui, nada no motor nem nas rotas.
Trocado de Gemini para OpenAI em 31/08/2026: o modelo disponível na chave
Gemini testada (gemini-3.6-flash) respondeu com timeout/sobrecarga em
sequência — ver histórico no README.
"""

from __future__ import annotations

import time

from app.config import settings

TIMEOUT_S = 30
MAX_TOKENS_SAIDA = 500
TEMPERATURA = 0.3


class IAIndisponivel(Exception):
    pass


def gerar(mensagens: list[dict]) -> tuple[str, int | None, int | None, int]:
    """Devolve (texto, tokens_entrada, tokens_saida, latencia_ms).

    `mensagens` é a lista completa no formato da API de chat (system, user,
    assistant, ...) — tanto a análise de uma tacada quanto o chat de
    perguntas passam por aqui, só muda o que constroem em app/ia/prompt.py.
    """
    if not settings.OPENAI_API_KEY:
        raise IAIndisponivel("OPENAI_API_KEY não configurada (ver .env).")

    from openai import OpenAI

    inicio = time.monotonic()
    try:
        client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=TIMEOUT_S)
        resposta = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=mensagens,
            temperature=TEMPERATURA,
            max_completion_tokens=MAX_TOKENS_SAIDA,
        )
    except Exception as exc:  # noqa: BLE001 — qualquer falha do provedor vira "indisponível"
        raise IAIndisponivel(f"Falha ao chamar a OpenAI: {exc}") from exc

    latencia_ms = int((time.monotonic() - inicio) * 1000)
    texto = (resposta.choices[0].message.content or "").strip()
    if not texto:
        raise IAIndisponivel("Resposta vazia do modelo.")

    uso = resposta.usage
    tokens_entrada = uso.prompt_tokens if uso else None
    tokens_saida = uso.completion_tokens if uso else None
    return texto, tokens_entrada, tokens_saida, latencia_ms
