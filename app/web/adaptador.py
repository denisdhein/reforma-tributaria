"""
Ponte entre os modelos do banco e as dataclasses puras do motor.

Fica fora de app/motor de propósito: o motor não conhece ORM. Fica fora de
app/api porque não é JSON de API — é o que alimenta a tela HTML.
"""

from __future__ import annotations

from app.models import Empresa, ItemEmpresa
from app.motor import CustoEntrada, EntradaSimulacao, ItemEntrada
from app.motor.util import ZERO


def _aliq_item(item: ItemEmpresa, empresa: Empresa, campo: str) -> object:
    """
    Alíquota do item quando informada; senão, a da empresa (ver docstring de
    ItemEmpresa: "sobrepõe a da empresa quando informada"). Sem esse
    fallback, os itens do seed — cadastrados sem alíquota própria — dariam
    tributo zero no cálculo item a item.
    """
    valor_item = getattr(item, f"aliq_{campo}")
    if valor_item is not None:
        return valor_item
    return getattr(empresa, f"aliq_{campo}") or ZERO


def montar_entrada(empresa: Empresa) -> EntradaSimulacao:
    itens = [
        ItemEntrada(
            descricao=i.descricao,
            pct_faturamento=i.pct_faturamento,
            aliq_icms=_aliq_item(i, empresa, "icms"),
            aliq_iss=_aliq_item(i, empresa, "iss"),
            aliq_pis=_aliq_item(i, empresa, "pis"),
            aliq_cofins=_aliq_item(i, empresa, "cofins"),
            aliq_ipi=_aliq_item(i, empresa, "ipi"),
            regime_diferenciado=i.regime_diferenciado or "padrao",
            sujeito_imposto_seletivo=i.sujeito_imposto_seletivo,
        )
        for i in empresa.itens
    ]
    custos = [
        CustoEntrada(
            origem=c.origem.value,
            valor_anual=c.valor_anual,
            pct_fornecedor_simples=c.pct_fornecedor_simples,
            gera_credito_hoje=c.gera_credito_hoje,
            pct_imposto_embutido=c.pct_imposto_embutido,
        )
        for c in empresa.custos
    ]
    return EntradaSimulacao(
        razao_social=empresa.razao_social,
        regime=empresa.regime.value,
        faturamento_anual=empresa.faturamento_anual,
        itens=itens,
        custos=custos,
        simples_anexo=empresa.simples_anexo,
        rbt12=empresa.rbt12,
        aliq_icms=empresa.aliq_icms or ZERO,
        aliq_iss=empresa.aliq_iss or ZERO,
        aliq_pis=empresa.aliq_pis or ZERO,
        aliq_cofins=empresa.aliq_cofins or ZERO,
        aliq_ipi=empresa.aliq_ipi or ZERO,
        margem_bruta=empresa.margem_bruta,
        margem_liquida=empresa.margem_liquida,
        pct_compras_com_credito=empresa.pct_compras_com_credito,
        pct_imposto_embutido_custos=empresa.pct_imposto_embutido_custos,
    )
