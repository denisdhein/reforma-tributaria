"""
Telas HTML do protótipo: login, formulário de simulação e resultado.

Server-rendered com Jinja2. Sem SPA, sem build step — o próprio backend
monta a página. Toda rota abaixo de /login exige sessão (cookie JWT, ver
app/auth) e é filtrada pelo tenant do usuário logado — admin atravessa
todos os tenants, os demais só veem o próprio. Cadastro de empresa vive em
app/web/empresas.py; contas de usuário são provisionadas via
`python -m scripts.criar_usuario`.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from markupsafe import Markup
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth.dependencias import eh_admin, usuario_api, usuario_web
from app.auth.seguranca import EXPIRA_HORAS, NOME_COOKIE, criar_token, verificar_senha
from app.config import settings
from app.db import get_db
from app.formatacao import moeda, pctfmt
from app.ia.prompt import montar_contexto
from app.ia.servico import analisar, responder_pergunta
from app.models import (
    CenarioAliquota, Empresa, OpcaoSimplesIBSCBS, PapelUsuario, RegrasVersao, Usuario,
)
from app.motor.simples import ForaDoSimples
from app.motor import calcular
from app.web.adaptador import montar_entrada
from app.web.graficos import montar_grafico_atual_futuro, montar_grafico_simples
from app.web.uploads import UploadInvalido, remover_foto, salvar_foto

router = APIRouter(include_in_schema=False)

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.filters["moeda"] = moeda
templates.env.filters["pctfmt"] = pctfmt
templates.env.filters["tojson"] = lambda v: Markup(json.dumps(v, ensure_ascii=False).replace("</", "<\\/"))

_PALETA_AVATAR = ["#1d4ed8", "#15803d", "#b45309", "#7c3aed", "#be123c", "#0e7490"]
templates.env.filters["cor_avatar"] = lambda id_: _PALETA_AVATAR[id_ % len(_PALETA_AVATAR)]

ANOS = list(range(2026, 2034))

_COOKIE_SEGURO = settings.AMBIENTE == "prod"


# --------------------------------------------------------------------------
# Login / logout
# --------------------------------------------------------------------------

@router.get("/login", response_class=HTMLResponse)
def tela_login(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("login.html", {"request": request, "erro": None})


@router.post("/login", response_class=HTMLResponse)
def autenticar(
    request: Request,
    email: str = Form(...),
    senha: str = Form(...),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    usuario = db.scalar(select(Usuario).where(Usuario.email == email.strip().lower()))
    # Mensagem genérica de propósito: não revela se o e-mail existe.
    invalido = usuario is None or not usuario.ativo or not verificar_senha(senha, usuario.senha_hash)
    if invalido:
        return templates.TemplateResponse(
            "login.html", {"request": request, "erro": "E-mail ou senha inválidos."}
        )

    usuario.ultimo_acesso = datetime.now(timezone.utc)
    db.commit()

    resposta = RedirectResponse("/", status_code=303)
    resposta.set_cookie(
        NOME_COOKIE, criar_token(usuario.id),
        max_age=EXPIRA_HORAS * 3600, httponly=True, samesite="lax", secure=_COOKIE_SEGURO,
    )
    return resposta


@router.post("/logout")
def logout() -> RedirectResponse:
    resposta = RedirectResponse("/login", status_code=303)
    resposta.delete_cookie(NOME_COOKIE)
    return resposta


# --------------------------------------------------------------------------
# Simulação
# --------------------------------------------------------------------------

def _regras_ativa(db: Session) -> RegrasVersao | None:
    return db.scalar(
        select(RegrasVersao).where(RegrasVersao.ativa.is_(True)).order_by(RegrasVersao.id.desc())
    )


def _empresas_visiveis(db: Session, usuario: Usuario):
    q = select(Empresa).order_by(Empresa.razao_social)
    if not eh_admin(usuario):
        q = q.where(Empresa.tenant_id == usuario.tenant_id)
    return db.scalars(q).all()


def _cenarios_visiveis(db: Session, usuario: Usuario):
    q = select(CenarioAliquota).where(CenarioAliquota.ativo.is_(True))
    if not eh_admin(usuario):
        q = q.where(
            (CenarioAliquota.tenant_id.is_(None)) | (CenarioAliquota.tenant_id == usuario.tenant_id)
        )
    return db.scalars(q.order_by(CenarioAliquota.id)).all()


def _contexto_base(db: Session, usuario: Usuario) -> dict:
    return {
        "empresas": _empresas_visiveis(db, usuario),
        "cenarios": _cenarios_visiveis(db, usuario),
        "anos": ANOS,
        "usuario": usuario,
        "pagina_ativa": "simular",
    }


@router.get("/", response_class=HTMLResponse)
def formulario(
    request: Request, db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_web),
) -> HTMLResponse:
    ctx = _contexto_base(db, usuario)
    ctx.update(
        request=request, resultado=None, empresa=None, erro=None, selecionado={},
        analise=None, contexto_ia=None, grafico_atual_futuro=None, grafico_simples=None,
    )

    if _regras_ativa(db) is None:
        ctx["erro"] = "Nenhuma versão de regras ativa. Rode: python -m scripts.seed"
    elif not ctx["empresas"]:
        ctx["erro"] = "Nenhuma empresa visível para esta conta."

    return templates.TemplateResponse("index.html", ctx)


@router.post("/simular", response_class=HTMLResponse)
def simular(
    request: Request,
    empresa_id: int = Form(...),
    ano_base: int = Form(...),
    cenario_id: int = Form(...),
    opcao_simples: str = Form(""),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_web),
) -> HTMLResponse:
    ctx = _contexto_base(db, usuario)
    selecionado = {
        "empresa_id": empresa_id,
        "ano_base": ano_base,
        "cenario_id": cenario_id,
        "opcao_simples": opcao_simples,
    }
    ctx.update(
        request=request, resultado=None, empresa=None, erro=None,
        selecionado=selecionado, analise=None, contexto_ia=None,
        grafico_atual_futuro=None, grafico_simples=None,
    )

    empresa = db.get(
        Empresa, empresa_id,
        options=[selectinload(Empresa.itens), selectinload(Empresa.custos)],
    )
    # Empresa de outro tenant: tratada como inexistente, sem entregar posição
    # (não revela se o id existe fora do escopo do usuário).
    if empresa is not None and not eh_admin(usuario) and empresa.tenant_id != usuario.tenant_id:
        empresa = None

    cenario = db.get(CenarioAliquota, cenario_id)
    regras = _regras_ativa(db)

    if empresa is None or cenario is None or regras is None:
        ctx["erro"] = "Empresa, cenário ou regras não encontrados. A seleção pode estar desatualizada."
        return templates.TemplateResponse("index.html", ctx)

    entrada = montar_entrada(empresa)
    opcao = opcao_simples or None
    if opcao and opcao not in (OpcaoSimplesIBSCBS.UNICO.value, OpcaoSimplesIBSCBS.HIBRIDO.value):
        opcao = None

    try:
        resultado = calcular(
            entrada, ano_base, cenario.aliquota_ibs, cenario.aliquota_cbs,
            regras.parametros, opcao_simples=opcao,
        )
    except ForaDoSimples:
        # Mensagem própria: "Anexo não parametrizado nesta versão de
        # regras" (erro cru do motor) confundiu um usuário de verdade —
        # só os anexos I e III têm tabela de faixas cadastrada hoje.
        ctx["erro"] = (
            f"Não foi possível simular: o Anexo {entrada.simples_anexo} do Simples ainda não "
            "tem tabela de alíquotas cadastrada neste sistema — só os Anexos I e III têm hoje. "
            "Recadastre a empresa com um desses dois anexos, ou peça para o administrador "
            "completar os demais."
        )
        return templates.TemplateResponse("index.html", ctx)
    except ValueError as exc:
        ctx["erro"] = f"Não foi possível simular: {exc}"
        return templates.TemplateResponse("index.html", ctx)

    ctx["resultado"] = resultado
    ctx["empresa"] = empresa
    ctx["cenario"] = cenario
    ctx["analise"] = analisar(resultado)
    ctx["contexto_ia"] = montar_contexto(resultado)
    ctx["grafico_atual_futuro"] = montar_grafico_atual_futuro(resultado)
    ctx["grafico_simples"] = montar_grafico_simples(resultado)
    return templates.TemplateResponse("index.html", ctx)


# --------------------------------------------------------------------------
# Chat sobre o resultado
# --------------------------------------------------------------------------

class TurnoChat(BaseModel):
    pergunta: str
    resposta: str


class PedidoChat(BaseModel):
    contexto: dict
    historico: list[TurnoChat] = []
    pergunta: str


@router.post("/chat")
def chat(pedido: PedidoChat, usuario: Usuario = Depends(usuario_api)) -> dict:
    """
    JSON, chamado por fetch() do próprio template (ver index.html). O
    contexto vem de volta do navegador, não é relido do banco — a tela já
    tinha esses números na hora que a simulação rodou. Isso significa que
    um usuário autenticado pode adulterar seu próprio `contexto` no
    devtools e fazer a IA "confirmar" números fabricados na própria tela
    dele; não expõe dado de outro tenant nem quebra a aplicação (renderizar
    valida a chave contra o texto gerado, não o contrário). Fechar essa
    lacuna de vez pede persistir a simulação no banco (Simulacao) e o chat
    ler o contexto por id, não por payload — fica para quando RF08/RF11
    entrarem em pauta.
    """
    pergunta = pedido.pergunta.strip()
    if not pergunta:
        return {"status": "erro", "motivo": "Pergunta vazia.", "texto": None}
    if not isinstance(pedido.contexto.get("referencias"), dict):
        return {"status": "erro", "motivo": "Contexto inválido.", "texto": None}

    historico = [{"pergunta": t.pergunta, "resposta": t.resposta} for t in pedido.historico]
    resultado = responder_pergunta(pedido.contexto, historico, pergunta)
    return {
        "status": resultado["status"], "motivo": resultado["motivo"], "texto": resultado["texto"],
    }


# --------------------------------------------------------------------------
# Perfil
# --------------------------------------------------------------------------

@router.get("/perfil", response_class=HTMLResponse)
def perfil(request: Request, usuario: Usuario = Depends(usuario_web)) -> HTMLResponse:
    return templates.TemplateResponse("perfil.html", {
        "request": request, "usuario": usuario, "pagina_ativa": "perfil",
        "erro": None, "sucesso": None,
    })


@router.post("/perfil", response_class=HTMLResponse)
def atualizar_perfil(
    request: Request,
    nome: str = Form(...),
    nome_tenant: str = Form(...),
    foto: UploadFile | None = File(None),
    remover_foto_atual: str = Form(""),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_web),
) -> HTMLResponse:
    nome = nome.strip()
    nome_tenant = nome_tenant.strip()
    # Operador administra o que é dele (simulações); renomear a conta toda
    # fica para gestor/admin — a mesma distinção de papel que já existe no
    # modelo (PapelUsuario), só nunca tinha uma tela que a usasse.
    pode_renomear_conta = usuario.papel != PapelUsuario.OPERADOR

    erro = None
    if not nome:
        erro = "Nome não pode ficar em branco."
    elif pode_renomear_conta and not nome_tenant:
        erro = "Nome da empresa/escritório não pode ficar em branco."

    if erro is None and foto is not None and foto.filename:
        try:
            nome_arquivo = salvar_foto(foto, f"usuario{usuario.id}")
        except UploadInvalido as exc:
            erro = str(exc)
        else:
            foto_antiga = usuario.foto_nome
            usuario.foto_nome = nome_arquivo
            remover_foto(foto_antiga)
    elif erro is None and remover_foto_atual == "1" and usuario.foto_nome:
        remover_foto(usuario.foto_nome)
        usuario.foto_nome = None

    if erro:
        return templates.TemplateResponse("perfil.html", {
            "request": request, "usuario": usuario, "pagina_ativa": "perfil",
            "erro": erro, "sucesso": None,
        })

    usuario.nome = nome
    if pode_renomear_conta:
        usuario.tenant.nome = nome_tenant
    db.commit()

    return templates.TemplateResponse("perfil.html", {
        "request": request, "usuario": usuario, "pagina_ativa": "perfil",
        "erro": None, "sucesso": "Perfil atualizado.",
    })
