"""
Histórico de simulações — RF08 (persistência) e RF11 (histórico) do TCC I.

Puramente leitura: quem grava é POST /simular, em app/web/rotas.py
(_salvar_simulacao), no instante em que a simulação roda — cada rodada bem
sucedida vira uma linha aqui, sem passo extra de "salvar". Reusa
`templates` importado de rotas.py, mesmo padrão de app/web/cenarios.py.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth.dependencias import eh_admin, usuario_web
from app.db import get_db
from app.models import Simulacao, StatusVerificacao, Usuario
from app.web.graficos import montar_grafico_atual_futuro, montar_grafico_simples
from app.web.rotas import templates

router = APIRouter(include_in_schema=False)

_STATUS_TEXTO = {
    StatusVerificacao.APROVADA: "aprovada",
    StatusVerificacao.REPROVADA: "reprovada",
    StatusVerificacao.NAO_EXECUTADA: "indisponivel",
}


def _analise_para_template(simulacao: Simulacao) -> dict:
    """Reconstrói o formato que _resultado.html espera (mesmo shape que
    app/ia/servico.py:analisar() devolve na hora), a partir da AnaliseIA
    salva — ou de um placeholder quando a IA não respondeu naquela rodada."""
    a = simulacao.analise
    if a is None:
        return {
            "status": "indisponivel",
            "motivo": "IA não respondeu nesta simulação.",
            "texto": None,
            "latencia_ms": None,
        }
    return {
        "status": _STATUS_TEXTO.get(a.status_verificacao, "indisponivel"),
        "motivo": (a.verificacao or {}).get("motivo"),
        "texto": a.resposta_renderizada,
        "latencia_ms": a.latencia_ms,
    }


@router.get("/historico", response_class=HTMLResponse)
def listar_historico(
    request: Request, db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_web),
) -> HTMLResponse:
    q = (
        select(Simulacao)
        .options(selectinload(Simulacao.empresa))
        .order_by(Simulacao.criada_em.desc())
    )
    if not eh_admin(usuario):
        q = q.where(Simulacao.tenant_id == usuario.tenant_id)
    simulacoes = db.scalars(q).all()
    return templates.TemplateResponse("historico_lista.html", {
        "request": request, "usuario": usuario, "pagina_ativa": "historico",
        "simulacoes": simulacoes, "erro": None,
    })


@router.get("/historico/{simulacao_id}", response_class=HTMLResponse)
def ver_historico(
    simulacao_id: int, request: Request,
    db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_web),
) -> HTMLResponse:
    simulacao = db.get(
        Simulacao, simulacao_id,
        options=[selectinload(Simulacao.empresa), selectinload(Simulacao.analise)],
    )
    # De outro tenant: tratada como inexistente, mesma régua de /simular.
    if simulacao is not None and not eh_admin(usuario) and simulacao.tenant_id != usuario.tenant_id:
        simulacao = None
    if simulacao is None:
        return templates.TemplateResponse("historico_lista.html", {
            "request": request, "usuario": usuario, "pagina_ativa": "historico",
            "simulacoes": [], "erro": "Simulação não encontrada.",
        })

    resultado = simulacao.resultado
    return templates.TemplateResponse("historico_detalhe.html", {
        "request": request, "usuario": usuario, "pagina_ativa": "historico",
        "simulacao": simulacao,
        "resultado": resultado,
        "empresa": simulacao.empresa,
        "cenario": simulacao.cenario_aliquota_snapshot,
        "analise": _analise_para_template(simulacao),
        "grafico_atual_futuro": montar_grafico_atual_futuro(resultado),
        "grafico_simples": montar_grafico_simples(resultado),
        "selecionado": {
            "opcao_simples": simulacao.opcao_simples.value if simulacao.opcao_simples else "",
        },
        "simulacao_id": simulacao.id,
    })
