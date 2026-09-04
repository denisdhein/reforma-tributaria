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
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
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
from app.formatacao import fracao_validada, moeda, numero, pctfmt
from app.ia.prompt import montar_contexto
from app.ia.servico import analisar, responder_pergunta
from app.models import (
    AnaliseIA, CenarioAliquota, Empresa, OpcaoSimplesIBSCBS, PapelUsuario, RegrasVersao,
    Simulacao, StatusVerificacao, TipoCenario, Usuario,
)
from app.motor import calcular
from app.motor.tipos import EntradaSimulacao
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


def _jsonavel(valor):
    """Converte Decimal (não serializável em JSON puro) para str, recursivamente
    — usado pra congelar o snapshot de entrada em Simulacao.dados_informados."""
    if isinstance(valor, Decimal):
        return str(valor)
    if isinstance(valor, dict):
        return {k: _jsonavel(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [_jsonavel(v) for v in valor]
    return valor


_STATUS_VERIFICACAO = {
    "aprovada": StatusVerificacao.APROVADA,
    "reprovada": StatusVerificacao.REPROVADA,
    "indisponivel": StatusVerificacao.NAO_EXECUTADA,
}


def _salvar_simulacao(
    db: Session, usuario: Usuario, empresa: Empresa, cenario: CenarioAliquota,
    regras: RegrasVersao, ano_base: int, opcao: str | None,
    entrada: EntradaSimulacao, resultado: dict, analise: dict,
) -> Simulacao:
    """
    RF08/RF11 — cada POST /simular bem sucedido vira uma linha aqui, sem
    passo extra de "salvar". Os campos *_snapshot congelam o que entrou no
    cálculo (ver docstring de Simulacao): editar o cenário ou os parâmetros
    depois não pode alterar retroativamente o que já foi salvo. Fecha
    também a lacuna do chat vindo de contexto de cliente — ver /chat abaixo.
    """
    c = resultado["comparacao"]
    simulacao = Simulacao(
        tenant_id=empresa.tenant_id,
        empresa_id=empresa.id,
        ano_base=ano_base,
        dados_informados=_jsonavel(asdict(entrada)),
        cenario_aliquota_snapshot=_jsonavel({
            "id": cenario.id, "nome": cenario.nome,
            "aliquota_ibs": cenario.aliquota_ibs, "aliquota_cbs": cenario.aliquota_cbs,
            "fonte": cenario.fonte, "tipo": cenario.tipo.value if cenario.tipo else None,
        }),
        regras_snapshot=regras.parametros,
        motor_versao=resultado["meta"]["motor_versao"],
        resultado=resultado,
        carga_atual_rs=Decimal(resultado["atual"]["carga_liquida_rs"]),
        carga_futura_rs=Decimal(resultado["futuro"]["carga_liquida_rs"]),
        diferenca_rs=Decimal(c["diferenca_rs"]),
        diferenca_pct=Decimal(c["diferenca_pct"]),
        margem_liquida_depois=(
            Decimal(c["margem_liquida_depois"]) if "margem_liquida_depois" in c else None
        ),
        opcao_simples=OpcaoSimplesIBSCBS(opcao) if opcao else None,
        cenario_aliquota_id=cenario.id,
        regras_versao_id=regras.id,
        criada_por_id=usuario.id,
    )
    db.add(simulacao)
    db.flush()

    # Só grava a análise se a IA de fato respondeu algo (aprovada ou
    # reprovada) — "indisponivel" não tem resposta_bruta pra satisfazer a
    # coluna NOT NULL, e não haveria o que auditar mesmo.
    if analise.get("resposta_bruta"):
        db.add(AnaliseIA(
            tenant_id=empresa.tenant_id,
            simulacao_id=simulacao.id,
            modelo=settings.OPENAI_MODEL,
            prompt_enviado=analise["prompt_enviado"],
            resposta_bruta=analise["resposta_bruta"],
            resposta_renderizada=analise.get("texto"),
            verificacao={"motivo": analise.get("motivo")},
            status_verificacao=_STATUS_VERIFICACAO.get(
                analise["status"], StatusVerificacao.NAO_EXECUTADA
            ),
            tokens_entrada=analise.get("tokens_entrada"),
            tokens_saida=analise.get("tokens_saida"),
            latencia_ms=analise.get("latencia_ms"),
        ))
    db.commit()
    return simulacao


def _selecionado_de_simulacao(db: Session, usuario: Usuario, simulacao_id: int) -> dict:
    """RF10 — pré-preenche o formulário a partir de uma simulação salva, pra
    "repetir com parâmetros alterados" não exigir digitar tudo de novo.
    Prioriza o cenário ao vivo se ele ainda existir/estiver ativo; senão
    reconstrói IBS/CBS do snapshot congelado (cenário pode ter sido
    desativado ou excluído depois — o snapshot nunca muda)."""
    simulacao = db.get(Simulacao, simulacao_id)
    if simulacao is None or (not eh_admin(usuario) and simulacao.tenant_id != usuario.tenant_id):
        return {}

    selecionado = {
        "empresa_id": simulacao.empresa_id,
        "ano_base": simulacao.ano_base,
        "opcao_simples": simulacao.opcao_simples.value if simulacao.opcao_simples else "",
    }
    cenario_vivo = (
        db.get(CenarioAliquota, simulacao.cenario_aliquota_id)
        if simulacao.cenario_aliquota_id else None
    )
    if cenario_vivo is not None and cenario_vivo.ativo:
        selecionado["cenario_id"] = cenario_vivo.id
    else:
        snap = simulacao.cenario_aliquota_snapshot or {}
        if "aliquota_ibs" in snap and "aliquota_cbs" in snap:
            selecionado["ibs_personalizado"] = numero(Decimal(snap["aliquota_ibs"]) * 100, 2)
            selecionado["cbs_personalizado"] = numero(Decimal(snap["aliquota_cbs"]) * 100, 2)
    return selecionado


@router.get("/", response_class=HTMLResponse)
def formulario(
    request: Request, repetir: int | None = None,
    db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_web),
) -> HTMLResponse:
    ctx = _contexto_base(db, usuario)
    selecionado = _selecionado_de_simulacao(db, usuario, repetir) if repetir is not None else {}
    ctx.update(
        request=request, resultado=None, empresa=None, erro=None, selecionado=selecionado,
        analise=None, simulacao_id=None, grafico_atual_futuro=None, grafico_simples=None,
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
    cenario_id: str = Form(""),
    ibs_personalizado: str = Form(""),
    cbs_personalizado: str = Form(""),
    opcao_simples: str = Form(""),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_web),
) -> HTMLResponse:
    ctx = _contexto_base(db, usuario)
    selecionado = {
        "empresa_id": empresa_id,
        "ano_base": ano_base,
        "cenario_id": cenario_id,
        "ibs_personalizado": ibs_personalizado,
        "cbs_personalizado": cbs_personalizado,
        "opcao_simples": opcao_simples,
    }
    ctx.update(
        request=request, resultado=None, empresa=None, erro=None,
        selecionado=selecionado, analise=None, simulacao_id=None,
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

    regras = _regras_ativa(db)

    # Digitar IBS/CBS direto no formulário vale mais que o cenário
    # escolhido no dropdown — evita o passo extra de ir em "Cenários"
    # criar um antes de poder simular com um número específico.
    cenario = None
    if ibs_personalizado.strip() and cbs_personalizado.strip():
        try:
            ibs = fracao_validada(ibs_personalizado, "IBS digitado")
            cbs = fracao_validada(cbs_personalizado, "CBS digitado")
        except ValueError as exc:
            ctx["erro"] = str(exc)
            return templates.TemplateResponse("index.html", ctx)
        cenario = db.scalar(
            select(CenarioAliquota).where(
                CenarioAliquota.tenant_id == usuario.tenant_id,
                CenarioAliquota.aliquota_ibs == ibs,
                CenarioAliquota.aliquota_cbs == cbs,
            )
        )
        if cenario is None:
            cenario = CenarioAliquota(
                tenant_id=usuario.tenant_id,
                nome=f"Personalizado (IBS {ibs_personalizado.strip()}% + CBS {cbs_personalizado.strip()}%)",
                aliquota_ibs=ibs, aliquota_cbs=cbs,
                fonte="Digitado direto na simulação", tipo=TipoCenario.USUARIO, ativo=True,
            )
            db.add(cenario)
            db.commit()
    elif cenario_id.strip():
        cenario = db.get(CenarioAliquota, int(cenario_id))

    if empresa is None or cenario is None or regras is None:
        ctx["erro"] = (
            "Empresa, cenário ou regras não encontrados. A seleção pode estar desatualizada, "
            "ou selecione um cenário / digite IBS e CBS."
        )
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
    except ValueError as exc:
        # ForaDoSimples (RBT12 fora da faixa, anexo sem tabela) é um
        # ValueError — mensagem do motor já é clara o bastante pra tela.
        ctx["erro"] = f"Não foi possível simular: {exc}"
        return templates.TemplateResponse("index.html", ctx)

    analise = analisar(resultado)
    simulacao = _salvar_simulacao(
        db, usuario, empresa, cenario, regras, ano_base, opcao, entrada, resultado, analise,
    )

    ctx["resultado"] = resultado
    ctx["empresa"] = empresa
    ctx["cenario"] = cenario
    ctx["analise"] = analise
    ctx["simulacao_id"] = simulacao.id
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
    simulacao_id: int
    historico: list[TurnoChat] = []
    pergunta: str


@router.post("/chat")
def chat(
    pedido: PedidoChat, db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_api),
) -> dict:
    """
    JSON, chamado por fetch() do próprio template (ver _resultado.html). O
    contexto vem de `Simulacao.resultado`, relido do banco por
    `simulacao_id` — não mais reenviado pelo navegador a cada pergunta.
    Fecha a lacuna que existia antes de RF08/RF11: um usuário autenticado
    não pode mais adulterar o contexto no devtools pra fazer a IA
    "confirmar" números fabricados, porque o servidor nunca confia no que
    o cliente diz que é o resultado — só no que está salvo.
    """
    pergunta = pedido.pergunta.strip()
    if not pergunta:
        return {"status": "erro", "motivo": "Pergunta vazia.", "texto": None}

    simulacao = db.get(Simulacao, pedido.simulacao_id)
    # Mesma régua de /simular e /historico: de outro tenant vira "não achei".
    if simulacao is not None and not eh_admin(usuario) and simulacao.tenant_id != usuario.tenant_id:
        simulacao = None
    if simulacao is None:
        return {"status": "erro", "motivo": "Simulação não encontrada.", "texto": None}

    contexto = montar_contexto(simulacao.resultado)
    historico = [{"pergunta": t.pergunta, "resposta": t.resposta} for t in pedido.historico]
    resultado = responder_pergunta(contexto, historico, pergunta)
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
