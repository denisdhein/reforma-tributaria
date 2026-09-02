"""
Orquestra mensagens -> chamada -> verificação -> renderização. Três pontos
de entrada:

- `analisar(resultado)`: a explicação de uma tacada em POST /simular.
- `responder_pergunta(...)`: cada turno do chat em POST /chat.
- `responder_ajuda_cadastro(...)`: ajuda a preencher o formulário de
  empresa em POST /empresas/ajuda — SEM a verificação numérica das duas
  primeiras, porque não há `referencias` para ancorar (ainda não existe
  simulação calculada). A garantia ali é só o prompt (instruído a nunca
  citar número), não estrutural — ver ressalva no README.

Se qualquer etapa falhar, devolve um dict com status claro em vez de
propagar exceção — a simulação (o motor, que é o que importa de verdade)
não pode quebrar por causa da IA estar fora do ar, ter respondido mal, ou
o cliente ter mandado um contexto malformado (o chat recebe o contexto de
volta do navegador, não do banco — ver ressalva no README).
"""

from __future__ import annotations

import json

from app.ia.cliente import IAIndisponivel, gerar
from app.ia.prompt import (
    construir_mensagens_ajuda_cadastro, construir_mensagens_analise, construir_mensagens_chat,
)
from app.ia.renderizador import renderizar
from app.ia.verificacao import verificar

MAX_HISTORICO_TURNOS = 6
MAX_PERGUNTA_CHARS = 500


def _executar(
    mensagens: list[dict], referencias: dict, direcao: str, modo_relatorio: bool = True,
) -> dict:
    base = {
        "prompt_enviado": json.dumps(mensagens, ensure_ascii=False),
        "resposta_bruta": None,
        "tokens_entrada": None,
        "tokens_saida": None,
        "latencia_ms": None,
    }

    try:
        texto_bruto, tok_in, tok_out, latencia_ms = gerar(mensagens)
    except IAIndisponivel as exc:
        return {**base, "status": "indisponivel", "motivo": str(exc), "texto": None}

    base.update(
        resposta_bruta=texto_bruto, tokens_entrada=tok_in, tokens_saida=tok_out,
        latencia_ms=latencia_ms,
    )

    v = verificar(texto_bruto, referencias, direcao, modo_relatorio=modo_relatorio)
    if not v.aprovada:
        return {**base, "status": "reprovada", "motivo": "; ".join(v.motivos), "texto": None}

    try:
        texto = renderizar(texto_bruto, referencias)
    except Exception as exc:  # noqa: BLE001 — contexto malformado não pode virar 500
        return {**base, "status": "reprovada", "motivo": f"referência malformada: {exc}", "texto": None}

    return {**base, "status": "aprovada", "motivo": None, "texto": texto}


def analisar(resultado: dict) -> dict:
    mensagens = construir_mensagens_analise(resultado)
    return _executar(mensagens, resultado["referencias"], resultado["comparacao"]["direcao"])


def responder_pergunta(contexto: dict, historico: list[dict], pergunta: str) -> dict:
    historico = historico[-MAX_HISTORICO_TURNOS:]
    pergunta = pergunta.strip()[:MAX_PERGUNTA_CHARS]
    mensagens = construir_mensagens_chat(contexto, historico, pergunta)
    referencias = contexto.get("referencias") or {}
    direcao = contexto.get("direcao_da_variacao", "")
    return _executar(mensagens, referencias, direcao, modo_relatorio=False)


def responder_ajuda_cadastro(historico: list[dict], pergunta: str) -> dict:
    historico = historico[-MAX_HISTORICO_TURNOS:]
    pergunta = pergunta.strip()[:MAX_PERGUNTA_CHARS]
    mensagens = construir_mensagens_ajuda_cadastro(historico, pergunta)

    base = {
        "prompt_enviado": json.dumps(mensagens, ensure_ascii=False),
        "resposta_bruta": None, "tokens_entrada": None, "tokens_saida": None, "latencia_ms": None,
    }
    try:
        texto, tok_in, tok_out, latencia_ms = gerar(mensagens)
    except IAIndisponivel as exc:
        return {**base, "status": "indisponivel", "motivo": str(exc), "texto": None}

    return {
        **base, "status": "aprovada", "motivo": None, "texto": texto,
        "resposta_bruta": texto, "tokens_entrada": tok_in, "tokens_saida": tok_out,
        "latencia_ms": latencia_ms,
    }
