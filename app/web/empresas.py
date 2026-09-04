"""
Cadastro de empresa pela própria conta — RF01. Sem escolher tenant no
formulário: a empresa nasce presa ao tenant do usuário logado, sempre
(evita criar empresa em tenant alheio digitando um id). Item a item é
opcional — zero itens cadastrados cai no modo "agregado" do motor, já
testado; a alíquota do item, quando não preenchida, herda a da empresa
(mesma regra de app/web/adaptador.py).
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth.dependencias import eh_admin, usuario_api, usuario_web
from app.db import get_db
from app.ia.servico import responder_ajuda_cadastro
from app.models import (
    CustoEmpresa, Empresa, ItemEmpresa, OpcaoSimplesIBSCBS, OrigemCusto,
    PapelUsuario, RegimeTributario, RegrasVersao, Usuario,
)
from app.web.rotas import TurnoChat, templates

router = APIRouter(include_in_schema=False)

D = Decimal

UFS = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG",
    "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
]

ROTULOS_REGIME = {
    RegimeTributario.SIMPLES: "Simples Nacional",
    RegimeTributario.PRESUMIDO: "Lucro Presumido",
    RegimeTributario.REAL: "Lucro Real",
}

ROTULOS_ORIGEM = {
    OrigemCusto.MERCADORIAS: "Mercadorias",
    OrigemCusto.INSUMOS: "Insumos",
    OrigemCusto.SERVICOS_TOMADOS: "Serviços tomados",
    OrigemCusto.ENERGIA: "Energia",
    OrigemCusto.FRETE: "Frete",
    OrigemCusto.ALUGUEL: "Aluguel",
    OrigemCusto.FOLHA: "Folha",
    OrigemCusto.OUTROS: "Outros",
}


class ErroValidacao(Exception):
    pass


def _decimal(bruto: str, campo: str) -> Decimal | None:
    bruto = (bruto or "").strip().replace(",", ".")
    if not bruto:
        return None
    try:
        return D(bruto)
    except InvalidOperation:
        raise ErroValidacao(f"Valor inválido em \"{campo}\": \"{bruto}\".") from None


def _fracao(bruto: str, campo: str) -> Decimal | None:
    """Campo digitado em percentual (17,5) vira fração (0.175)."""
    valor = _decimal(bruto, campo)
    return None if valor is None else valor / D("100")


def _regimes_diferenciados(db: Session) -> dict:
    regras = db.scalar(
        select(RegrasVersao).where(RegrasVersao.ativa.is_(True)).order_by(RegrasVersao.id.desc())
    )
    if regras is None:
        return {"padrao": 1.0}
    return regras.parametros.get("regimes_diferenciados", {"padrao": 1.0})


def _contexto_formulario(db: Session, usuario: Usuario, **extra) -> dict:
    return {
        "usuario": usuario,
        "pagina_ativa": "empresas",
        "ufs": UFS,
        "regimes": list(RegimeTributario),
        "rotulos_regime": ROTULOS_REGIME,
        "origens_custo": list(OrigemCusto),
        "rotulos_origem": ROTULOS_ORIGEM,
        "regimes_diferenciados": sorted(_regimes_diferenciados(db).keys()),
        "erro": None,
        "modo": "novo",
        "empresa_id": None,
        **extra,
    }


def _pct_str(fracao: Decimal | None) -> str:
    """Inverso de _fracao: fração guardada (0.175) vira texto em percentual
    (17.5) pra reaparecer preenchido no formulário de edição."""
    if fracao is None:
        return ""
    texto = format(fracao * D("100"), "f")
    if "." in texto:
        texto = texto.rstrip("0").rstrip(".")
    return texto


def _validar_e_montar(
    usuario: Usuario, *, razao_social: str, cnpj: str, uf: str, municipio: str, ramo: str,
    regime: str, simples_anexo: str, simples_opcao_ibs_cbs: str, faturamento_anual: str,
    rbt12: str, pct_interno: str, pct_interestadual: str, pct_exportacao: str,
    pct_consumidor_final: str, margem_bruta: str, margem_liquida: str, aliq_icms: str,
    aliq_iss: str, aliq_pis: str, aliq_cofins: str, aliq_ipi: str,
    pct_compras_com_credito: str, pct_imposto_embutido_custos: str, observacoes: str,
    custos: list[tuple[str, str, str, str, str]], itens: list[tuple[str, str, str, str]],
) -> tuple[dict, list[dict], list[dict]]:
    """Levanta ErroValidacao/ValueError com mensagem pronta pra tela se algo
    não bater; devolve (campos_da_empresa, linhas_custo, linhas_item) prontos
    pra virar Empresa/CustoEmpresa/ItemEmpresa. Usado por criar e editar —
    a validação de uma empresa não muda por já existir ou não."""
    try:
        regime_enum = RegimeTributario(regime)
    except ValueError:
        raise ErroValidacao("Regime tributário inválido.") from None

    if regime_enum == RegimeTributario.SIMPLES and not simples_anexo:
        raise ErroValidacao("Empresa do Simples precisa informar o anexo.")

    faturamento = _decimal(faturamento_anual, "Faturamento anual")
    if faturamento is None or faturamento <= 0:
        raise ErroValidacao("Faturamento anual precisa ser maior que zero.")

    campos = dict(
        tenant_id=usuario.tenant_id,
        razao_social=razao_social.strip(),
        cnpj=(cnpj.strip() or None),
        uf=uf.strip().upper(),
        municipio=municipio.strip(),
        ramo=(ramo.strip() or None),
        regime=regime_enum,
        simples_anexo=int(simples_anexo) if simples_anexo else None,
        simples_opcao_ibs_cbs=(
            OpcaoSimplesIBSCBS(simples_opcao_ibs_cbs) if simples_opcao_ibs_cbs else None
        ),
        faturamento_anual=faturamento,
        rbt12=_decimal(rbt12, "RBT12"),
        pct_interno=(_fracao(pct_interno, "% interno") or D("0")),
        pct_interestadual=(_fracao(pct_interestadual, "% interestadual") or D("0")),
        pct_exportacao=(_fracao(pct_exportacao, "% exportação") or D("0")),
        pct_consumidor_final=(_fracao(pct_consumidor_final, "% consumidor final") or D("0")),
        margem_bruta=_fracao(margem_bruta, "Margem bruta"),
        margem_liquida=_fracao(margem_liquida, "Margem líquida"),
        aliq_icms=_fracao(aliq_icms, "Alíquota ICMS"),
        aliq_iss=_fracao(aliq_iss, "Alíquota ISS"),
        aliq_pis=_fracao(aliq_pis, "Alíquota PIS"),
        aliq_cofins=_fracao(aliq_cofins, "Alíquota COFINS"),
        aliq_ipi=_fracao(aliq_ipi, "Alíquota IPI"),
        pct_compras_com_credito=_fracao(pct_compras_com_credito, "% compras com crédito"),
        pct_imposto_embutido_custos=_fracao(
            pct_imposto_embutido_custos, "% de imposto já embutido nos custos",
        ),
        observacoes=(observacoes.strip() or None),
    )

    linhas_custo = []
    for origem, valor, pct_simples, credito, pct_embutido in custos:
        if not valor.strip():
            continue
        valor_dec = _decimal(valor, "Valor do custo")
        if valor_dec is None or valor_dec < 0:
            raise ErroValidacao("Valor de custo inválido — não pode ser negativo.")
        linhas_custo.append(dict(
            origem=OrigemCusto(origem),
            valor_anual=valor_dec,
            pct_fornecedor_simples=(_fracao(pct_simples, "% fornecedor Simples") or D("0")),
            gera_credito_hoje=(credito == "sim"),
            pct_imposto_embutido=_fracao(pct_embutido, "% de imposto já embutido (linha de custo)"),
        ))

    linhas_item = []
    soma_pct = D("0")
    for descricao, pct, regime_dif, seletivo in itens:
        if not descricao.strip():
            continue
        pct_dec = _fracao(pct, "% do faturamento do item")
        if pct_dec is None or pct_dec <= 0:
            raise ErroValidacao(f'Item "{descricao}" precisa de um % de faturamento maior que zero.')
        soma_pct += pct_dec
        linhas_item.append(dict(
            descricao=descricao.strip(),
            pct_faturamento=pct_dec,
            regime_diferenciado=(regime_dif or "padrao"),
            sujeito_imposto_seletivo=(seletivo == "sim"),
        ))

    if linhas_item and abs(soma_pct - D("1")) > D("0.01"):
        raise ErroValidacao(f"Os itens somam {soma_pct * 100:.2f}% do faturamento — precisa somar 100%.")

    return campos, linhas_custo, linhas_item


@router.get("/empresas", response_class=HTMLResponse)
def listar_empresas(
    request: Request, db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_web),
) -> HTMLResponse:
    q = select(Empresa).order_by(Empresa.razao_social)
    if not eh_admin(usuario):
        q = q.where(Empresa.tenant_id == usuario.tenant_id)
    empresas = db.scalars(q).all()
    return templates.TemplateResponse("empresas_lista.html", {
        "request": request, "usuario": usuario, "pagina_ativa": "empresas", "empresas": empresas,
    })


@router.post("/empresas/{empresa_id}/excluir")
def excluir_empresa(
    empresa_id: int, db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_web),
) -> RedirectResponse:
    """
    Apaga a empresa e, em cascata (relationship com cascade="all,
    delete-orphan" no modelo), seus custos e itens. Não existe Simulacao
    persistida ainda, então não há histórico órfão a se preocupar por
    enquanto — quando existir, isso vai precisar de mais cuidado.
    """
    empresa = db.get(Empresa, empresa_id)
    pode_excluir = (
        empresa is not None
        and (eh_admin(usuario) or empresa.tenant_id == usuario.tenant_id)
        and usuario.papel != PapelUsuario.OPERADOR
    )
    if not pode_excluir:
        return RedirectResponse("/empresas", status_code=303)

    db.delete(empresa)
    db.commit()
    return RedirectResponse("/empresas?excluida=1", status_code=303)


@router.get("/empresas/nova", response_class=HTMLResponse)
def form_nova_empresa(
    request: Request, db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_web),
) -> HTMLResponse:
    ctx = _contexto_formulario(db, usuario, request=request, valores={}, custos=[], itens=[])
    return templates.TemplateResponse("empresa_nova.html", ctx)


@router.post("/empresas/nova", response_class=HTMLResponse)
def criar_empresa(
    request: Request,
    razao_social: str = Form(...),
    cnpj: str = Form(""),
    uf: str = Form(...),
    municipio: str = Form(...),
    ramo: str = Form(""),
    regime: str = Form(...),
    simples_anexo: str = Form(""),
    simples_opcao_ibs_cbs: str = Form(""),
    faturamento_anual: str = Form(...),
    rbt12: str = Form(""),
    pct_interno: str = Form(""),
    pct_interestadual: str = Form(""),
    pct_exportacao: str = Form(""),
    pct_consumidor_final: str = Form(""),
    margem_bruta: str = Form(""),
    margem_liquida: str = Form(""),
    aliq_icms: str = Form(""),
    aliq_iss: str = Form(""),
    aliq_pis: str = Form(""),
    aliq_cofins: str = Form(""),
    aliq_ipi: str = Form(""),
    pct_compras_com_credito: str = Form(""),
    pct_imposto_embutido_custos: str = Form(""),
    observacoes: str = Form(""),
    custo_origem: list[str] = Form([]),
    custo_valor_anual: list[str] = Form([]),
    custo_pct_fornecedor_simples: list[str] = Form([]),
    custo_gera_credito: list[str] = Form([]),
    custo_pct_imposto_embutido: list[str] = Form([]),
    item_descricao: list[str] = Form([]),
    item_pct_faturamento: list[str] = Form([]),
    item_regime_diferenciado: list[str] = Form([]),
    item_sujeito_seletivo: list[str] = Form([]),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_web),
) -> HTMLResponse:
    valores = dict(
        razao_social=razao_social, cnpj=cnpj, uf=uf, municipio=municipio, ramo=ramo,
        regime=regime, simples_anexo=simples_anexo, simples_opcao_ibs_cbs=simples_opcao_ibs_cbs,
        faturamento_anual=faturamento_anual, rbt12=rbt12,
        pct_interno=pct_interno, pct_interestadual=pct_interestadual,
        pct_exportacao=pct_exportacao, pct_consumidor_final=pct_consumidor_final,
        margem_bruta=margem_bruta, margem_liquida=margem_liquida,
        aliq_icms=aliq_icms, aliq_iss=aliq_iss, aliq_pis=aliq_pis,
        aliq_cofins=aliq_cofins, aliq_ipi=aliq_ipi,
        pct_compras_com_credito=pct_compras_com_credito,
        pct_imposto_embutido_custos=pct_imposto_embutido_custos, observacoes=observacoes,
    )
    custos = list(zip(
        custo_origem, custo_valor_anual, custo_pct_fornecedor_simples, custo_gera_credito,
        custo_pct_imposto_embutido,
    ))
    itens = list(zip(item_descricao, item_pct_faturamento, item_regime_diferenciado, item_sujeito_seletivo))

    try:
        campos, linhas_custo, linhas_item = _validar_e_montar(
            usuario, razao_social=razao_social, cnpj=cnpj, uf=uf, municipio=municipio, ramo=ramo,
            regime=regime, simples_anexo=simples_anexo,
            simples_opcao_ibs_cbs=simples_opcao_ibs_cbs, faturamento_anual=faturamento_anual,
            rbt12=rbt12, pct_interno=pct_interno, pct_interestadual=pct_interestadual,
            pct_exportacao=pct_exportacao, pct_consumidor_final=pct_consumidor_final,
            margem_bruta=margem_bruta, margem_liquida=margem_liquida, aliq_icms=aliq_icms,
            aliq_iss=aliq_iss, aliq_pis=aliq_pis, aliq_cofins=aliq_cofins, aliq_ipi=aliq_ipi,
            pct_compras_com_credito=pct_compras_com_credito,
        pct_imposto_embutido_custos=pct_imposto_embutido_custos, observacoes=observacoes,
            custos=custos, itens=itens,
        )
    except (ErroValidacao, ValueError) as exc:
        # ValueError também cobre enum inválido (OrigemCusto, OpcaoSimplesIBSCBS) —
        # só acontece adulterando o POST fora do formulário, mas não pode virar 500.
        ctx = _contexto_formulario(
            db, usuario, request=request, valores=valores, custos=custos, itens=itens,
            erro=str(exc),
        )
        return templates.TemplateResponse("empresa_nova.html", ctx)

    empresa = Empresa(**campos)
    db.add(empresa)
    db.flush()

    for linha in linhas_custo:
        db.add(CustoEmpresa(tenant_id=usuario.tenant_id, empresa_id=empresa.id, **linha))
    for linha in linhas_item:
        db.add(ItemEmpresa(tenant_id=usuario.tenant_id, empresa_id=empresa.id, **linha))

    db.commit()
    return RedirectResponse(f"/empresas?criada={empresa.id}", status_code=303)


@router.get("/empresas/{empresa_id}/editar", response_class=HTMLResponse)
def form_editar_empresa(
    empresa_id: int, request: Request, db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_web),
) -> HTMLResponse:
    empresa = db.get(
        Empresa, empresa_id, options=[selectinload(Empresa.custos), selectinload(Empresa.itens)],
    )
    if empresa is None or (not eh_admin(usuario) and empresa.tenant_id != usuario.tenant_id):
        return RedirectResponse("/empresas", status_code=303)

    valores = dict(
        razao_social=empresa.razao_social, cnpj=empresa.cnpj or "", uf=empresa.uf,
        municipio=empresa.municipio, ramo=empresa.ramo or "",
        regime=empresa.regime.value,
        simples_anexo=(str(empresa.simples_anexo) if empresa.simples_anexo else ""),
        simples_opcao_ibs_cbs=(
            empresa.simples_opcao_ibs_cbs.value if empresa.simples_opcao_ibs_cbs else ""
        ),
        faturamento_anual=format(empresa.faturamento_anual, "f"),
        rbt12=(format(empresa.rbt12, "f") if empresa.rbt12 is not None else ""),
        pct_interno=_pct_str(empresa.pct_interno),
        pct_interestadual=_pct_str(empresa.pct_interestadual),
        pct_exportacao=_pct_str(empresa.pct_exportacao),
        pct_consumidor_final=_pct_str(empresa.pct_consumidor_final),
        margem_bruta=_pct_str(empresa.margem_bruta),
        margem_liquida=_pct_str(empresa.margem_liquida),
        aliq_icms=_pct_str(empresa.aliq_icms),
        aliq_iss=_pct_str(empresa.aliq_iss),
        aliq_pis=_pct_str(empresa.aliq_pis),
        aliq_cofins=_pct_str(empresa.aliq_cofins),
        aliq_ipi=_pct_str(empresa.aliq_ipi),
        pct_compras_com_credito=_pct_str(empresa.pct_compras_com_credito),
        pct_imposto_embutido_custos=_pct_str(empresa.pct_imposto_embutido_custos),
        observacoes=empresa.observacoes or "",
    )
    custos = [
        (c.origem.value, format(c.valor_anual, "f"), _pct_str(c.pct_fornecedor_simples),
         "sim" if c.gera_credito_hoje else "nao", _pct_str(c.pct_imposto_embutido))
        for c in empresa.custos
    ]
    itens = [
        (i.descricao, _pct_str(i.pct_faturamento), i.regime_diferenciado or "padrao",
         "sim" if i.sujeito_imposto_seletivo else "nao")
        for i in empresa.itens
    ]

    ctx = _contexto_formulario(
        db, usuario, request=request, valores=valores, custos=custos, itens=itens,
        modo="editar", empresa_id=empresa.id,
    )
    return templates.TemplateResponse("empresa_nova.html", ctx)


@router.post("/empresas/{empresa_id}/editar", response_class=HTMLResponse)
def editar_empresa(
    empresa_id: int,
    request: Request,
    razao_social: str = Form(...),
    cnpj: str = Form(""),
    uf: str = Form(...),
    municipio: str = Form(...),
    ramo: str = Form(""),
    regime: str = Form(...),
    simples_anexo: str = Form(""),
    simples_opcao_ibs_cbs: str = Form(""),
    faturamento_anual: str = Form(...),
    rbt12: str = Form(""),
    pct_interno: str = Form(""),
    pct_interestadual: str = Form(""),
    pct_exportacao: str = Form(""),
    pct_consumidor_final: str = Form(""),
    margem_bruta: str = Form(""),
    margem_liquida: str = Form(""),
    aliq_icms: str = Form(""),
    aliq_iss: str = Form(""),
    aliq_pis: str = Form(""),
    aliq_cofins: str = Form(""),
    aliq_ipi: str = Form(""),
    pct_compras_com_credito: str = Form(""),
    pct_imposto_embutido_custos: str = Form(""),
    observacoes: str = Form(""),
    custo_origem: list[str] = Form([]),
    custo_valor_anual: list[str] = Form([]),
    custo_pct_fornecedor_simples: list[str] = Form([]),
    custo_gera_credito: list[str] = Form([]),
    custo_pct_imposto_embutido: list[str] = Form([]),
    item_descricao: list[str] = Form([]),
    item_pct_faturamento: list[str] = Form([]),
    item_regime_diferenciado: list[str] = Form([]),
    item_sujeito_seletivo: list[str] = Form([]),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_web),
) -> HTMLResponse:
    empresa = db.get(
        Empresa, empresa_id, options=[selectinload(Empresa.custos), selectinload(Empresa.itens)],
    )
    if empresa is None or (not eh_admin(usuario) and empresa.tenant_id != usuario.tenant_id):
        return RedirectResponse("/empresas", status_code=303)

    valores = dict(
        razao_social=razao_social, cnpj=cnpj, uf=uf, municipio=municipio, ramo=ramo,
        regime=regime, simples_anexo=simples_anexo, simples_opcao_ibs_cbs=simples_opcao_ibs_cbs,
        faturamento_anual=faturamento_anual, rbt12=rbt12,
        pct_interno=pct_interno, pct_interestadual=pct_interestadual,
        pct_exportacao=pct_exportacao, pct_consumidor_final=pct_consumidor_final,
        margem_bruta=margem_bruta, margem_liquida=margem_liquida,
        aliq_icms=aliq_icms, aliq_iss=aliq_iss, aliq_pis=aliq_pis,
        aliq_cofins=aliq_cofins, aliq_ipi=aliq_ipi,
        pct_compras_com_credito=pct_compras_com_credito,
        pct_imposto_embutido_custos=pct_imposto_embutido_custos, observacoes=observacoes,
    )
    custos = list(zip(
        custo_origem, custo_valor_anual, custo_pct_fornecedor_simples, custo_gera_credito,
        custo_pct_imposto_embutido,
    ))
    itens = list(zip(item_descricao, item_pct_faturamento, item_regime_diferenciado, item_sujeito_seletivo))

    try:
        campos, linhas_custo, linhas_item = _validar_e_montar(
            usuario, razao_social=razao_social, cnpj=cnpj, uf=uf, municipio=municipio, ramo=ramo,
            regime=regime, simples_anexo=simples_anexo,
            simples_opcao_ibs_cbs=simples_opcao_ibs_cbs, faturamento_anual=faturamento_anual,
            rbt12=rbt12, pct_interno=pct_interno, pct_interestadual=pct_interestadual,
            pct_exportacao=pct_exportacao, pct_consumidor_final=pct_consumidor_final,
            margem_bruta=margem_bruta, margem_liquida=margem_liquida, aliq_icms=aliq_icms,
            aliq_iss=aliq_iss, aliq_pis=aliq_pis, aliq_cofins=aliq_cofins, aliq_ipi=aliq_ipi,
            pct_compras_com_credito=pct_compras_com_credito,
        pct_imposto_embutido_custos=pct_imposto_embutido_custos, observacoes=observacoes,
            custos=custos, itens=itens,
        )
    except (ErroValidacao, ValueError) as exc:
        ctx = _contexto_formulario(
            db, usuario, request=request, valores=valores, custos=custos, itens=itens,
            erro=str(exc), modo="editar", empresa_id=empresa_id,
        )
        return templates.TemplateResponse("empresa_nova.html", ctx)

    campos.pop("tenant_id", None)  # nunca muda o dono da empresa numa edição
    for campo, valor in campos.items():
        setattr(empresa, campo, valor)

    for custo_existente in list(empresa.custos):
        db.delete(custo_existente)
    for item_existente in list(empresa.itens):
        db.delete(item_existente)
    db.flush()

    for linha in linhas_custo:
        db.add(CustoEmpresa(tenant_id=empresa.tenant_id, empresa_id=empresa.id, **linha))
    for linha in linhas_item:
        db.add(ItemEmpresa(tenant_id=empresa.tenant_id, empresa_id=empresa.id, **linha))

    db.commit()
    return RedirectResponse(f"/empresas?editada={empresa.id}", status_code=303)


# --------------------------------------------------------------------------
# Ajuda da IA durante o cadastro
# --------------------------------------------------------------------------

class PedidoAjuda(BaseModel):
    historico: list[TurnoChat] = []
    pergunta: str


@router.post("/empresas/ajuda")
def ajuda_cadastro(pedido: PedidoAjuda, usuario: Usuario = Depends(usuario_api)) -> dict:
    pergunta = pedido.pergunta.strip()
    if not pergunta:
        return {"status": "erro", "motivo": "Pergunta vazia.", "texto": None}
    historico = [{"pergunta": t.pergunta, "resposta": t.resposta} for t in pedido.historico]
    resultado = responder_ajuda_cadastro(historico, pergunta)
    return {
        "status": resultado["status"], "motivo": resultado["motivo"], "texto": resultado["texto"],
    }
