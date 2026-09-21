"""
Cenários de alíquota criados pelo próprio usuário — o modelo já previa
isso (`TipoCenario.USUARIO`, `CenarioAliquota.tenant_id`), só faltava a
tela. Existe porque a reforma ainda está em transição: ninguém sabe se a
alíquota de referência vai ficar como está, mudar, ou se a reforma some
no meio do caminho. Em vez de esperar o Senado fixar um número, o usuário
testa a própria hipótese — inclusive "e se não mudar nada" (0% e 0%).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.auth.dependencias import usuario_web
from app.db import get_db
from app.formatacao import fracao_validada, texto_validado
from app.models import CenarioAliquota, TipoCenario, Usuario
from app.web.rotas import _cenarios_visiveis, templates

router = APIRouter(include_in_schema=False)


@router.get("/cenarios", response_class=HTMLResponse)
def listar_cenarios(
    request: Request, db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_web),
) -> HTMLResponse:
    cenarios = _cenarios_visiveis(db, usuario)
    return templates.TemplateResponse("cenarios_lista.html", {
        "request": request, "usuario": usuario, "pagina_ativa": "cenarios", "cenarios": cenarios,
    })


@router.get("/cenarios/novo", response_class=HTMLResponse)
def form_novo_cenario(
    request: Request, usuario: Usuario = Depends(usuario_web),
) -> HTMLResponse:
    return templates.TemplateResponse("cenario_novo.html", {
        "request": request, "usuario": usuario, "pagina_ativa": "cenarios",
        "erro": None, "valores": {},
    })


@router.post("/cenarios/novo", response_class=HTMLResponse)
def criar_cenario(
    request: Request,
    nome: str = Form(...),
    aliquota_ibs: str = Form(...),
    aliquota_cbs: str = Form(...),
    fonte: str = Form(""),
    base_legal: str = Form(""),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_web),
) -> HTMLResponse:
    valores = dict(
        nome=nome, aliquota_ibs=aliquota_ibs, aliquota_cbs=aliquota_cbs,
        fonte=fonte, base_legal=base_legal,
    )
    nome = nome.strip()
    if not nome:
        return templates.TemplateResponse("cenario_novo.html", {
            "request": request, "usuario": usuario, "pagina_ativa": "cenarios",
            "erro": "Dê um nome ao cenário — ajuda a lembrar depois qual hipótese era essa.",
            "valores": valores,
        })

    try:
        ibs = fracao_validada(aliquota_ibs, "Alíquota do IBS")
        cbs = fracao_validada(aliquota_cbs, "Alíquota da CBS")
        # Mesma classe do bug do CNPJ pontuado: texto além do limite da
        # coluna passa liso no SQLite, só estoura contra Postgres.
        nome = texto_validado(nome, "Nome do cenário", 160)
        fonte_val = texto_validado(fonte, "Fonte", 255)
        base_legal_val = texto_validado(base_legal, "Base legal", 255)
    except ValueError as exc:
        return templates.TemplateResponse("cenario_novo.html", {
            "request": request, "usuario": usuario, "pagina_ativa": "cenarios",
            "erro": str(exc), "valores": valores,
        })

    cenario = CenarioAliquota(
        tenant_id=usuario.tenant_id,
        nome=nome,
        aliquota_ibs=ibs,
        aliquota_cbs=cbs,
        fonte=(fonte_val or None),
        base_legal=(base_legal_val or None),
        tipo=TipoCenario.USUARIO,
        ativo=True,
    )
    db.add(cenario)
    db.commit()
    return RedirectResponse("/cenarios?criado=1", status_code=303)
