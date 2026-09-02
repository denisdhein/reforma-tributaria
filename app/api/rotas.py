"""
Rotas mínimas do esqueleto. Existem para provar a fiação ponta a ponta:
aplicação sobe, fala com o banco e devolve os parâmetros carregados.

O motor de cálculo, autenticação e simulação ainda não existem.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencias import eh_admin, usuario_api
from app.config import settings
from app.db import get_db
from app.models import CenarioAliquota, Empresa, RegrasVersao, Usuario

router = APIRouter()


@router.get("/saude", tags=["infra"])
def saude(db: Session = Depends(get_db)) -> dict:
    db.execute(select(1))
    return {
        "status": "ok",
        "ambiente": settings.AMBIENTE,
        "motor_versao": settings.MOTOR_VERSAO,
    }


@router.get("/api/cenarios", tags=["parâmetros"])
def listar_cenarios(db: Session = Depends(get_db)) -> list[dict]:
    cenarios = db.scalars(
        select(CenarioAliquota)
        .where(CenarioAliquota.ativo.is_(True))
        .order_by(CenarioAliquota.id)
    ).all()
    return [c.snapshot() for c in cenarios]


@router.get("/api/regras", tags=["parâmetros"])
def regras_ativa(db: Session = Depends(get_db)) -> dict:
    rv = db.scalar(
        select(RegrasVersao)
        .where(RegrasVersao.ativa.is_(True))
        .order_by(RegrasVersao.id.desc())
    )
    if rv is None:
        raise HTTPException(404, "Nenhuma versão de regras ativa. Rode: python -m scripts.seed")

    p = rv.parametros
    return {
        "versao": rv.versao,
        "descricao": rv.descricao,
        "anos_cobertos": sorted(p["anos"].keys()),
        "regimes_diferenciados": sorted(p["regimes_diferenciados"].keys()),
        "simples_anexos_preenchidos": sorted(
            k for k, v in p["simples"]["anexos"].items() if v
        ),
        "simples_nao_implementado": p["simples"]["nao_implementado"],
        "imposto_seletivo_habilitado": p["imposto_seletivo"]["habilitado"],
    }


@router.get("/api/empresas", tags=["empresas"])
def listar_empresas(
    db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_api),
) -> list[dict]:
    q = select(Empresa).order_by(Empresa.id)
    if not eh_admin(usuario):
        q = q.where(Empresa.tenant_id == usuario.tenant_id)
    empresas = db.scalars(q).all()
    return [
        {
            "id": e.id,
            "razao_social": e.razao_social,
            "regime": e.regime.value,
            "simples_anexo": e.simples_anexo,
            "uf": e.uf,
            "municipio": e.municipio,
            "faturamento_anual": str(e.faturamento_anual),
            "qtd_custos": len(e.custos),
            "qtd_itens": len(e.itens),
        }
        for e in empresas
    ]
