"""
Cenário atual: PIS, COFINS, ICMS, ISS e IPI.

Premissa de modelagem — tributo por dentro
------------------------------------------
ICMS, ISS, PIS e COFINS integram a própria base de cálculo. O faturamento
informado já os contém, então a carga efetiva sobre o faturamento é a própria
alíquota. O IPI é por fora; aqui ele é tratado como incidente sobre o
faturamento, o que é simplificação declarada nas limitações.

Premissa de modelagem — créditos
--------------------------------
O crédito atual é limitado e depende da origem do custo. Modelo adotado:
  - PIS/COFINS: creditam nos custos marcados como geradores de crédito
  - ICMS: credita apenas em mercadorias, insumos, energia e frete
  - folha, aluguel e "outros": não creditam
Sobre isso aplica-se `pct_compras_com_credito` como amortecedor global
informado pela empresa. É simplificação: a legislação atual tem lista
taxativa de créditos que o MVP não reproduz.
"""

from __future__ import annotations

from decimal import Decimal

from app.motor.tipos import EntradaSimulacao, ItemEntrada
from app.motor.util import D, ZERO, dinheiro, pct

ORIGENS_COM_ICMS = {"mercadorias", "insumos", "energia", "frete"}

TRIBUTOS_ATUAIS = ("icms", "iss", "pis", "cofins", "ipi")


def _aliq_item(item: ItemEntrada, tributo: str) -> Decimal:
    return getattr(item, f"aliq_{tributo}", ZERO) or ZERO


def calcular_debitos(
    entrada: EntradaSimulacao,
    itens: list[ItemEntrada],
    fracoes_ano: dict | None = None,
) -> tuple[dict, list[dict]]:
    """
    Débitos por tributo e detalhamento item a item.

    `fracoes_ano=None` calcula a PLENA CARGA do sistema atual — é o baseline
    de comparação, fixo, independente do ano simulado. Com frações, calcula
    o resíduo dos tributos antigos vigente no ano de transição.
    """
    fracoes_ano = fracoes_ano or {}
    receita = D(entrada.faturamento_anual)
    por_tributo = {t: ZERO for t in TRIBUTOS_ATUAIS}
    detalhe: list[dict] = []

    for item in itens:
        receita_item = receita * D(item.pct_faturamento)
        tributos_item = {}
        for t in TRIBUTOS_ATUAIS:
            fracao_vigente = D(str(fracoes_ano.get(_chave_fracao(t), 1)))  # 1 = plena carga
            valor = receita_item * _aliq_item(item, t) * fracao_vigente
            tributos_item[t] = dinheiro(valor)
            por_tributo[t] += valor

        detalhe.append({
            "descricao": item.descricao,
            "pct_faturamento": str(item.pct_faturamento),
            "receita_rs": str(dinheiro(receita_item)),
            "tributos_rs": {t: str(v) for t, v in tributos_item.items()},
            "total_rs": str(dinheiro(sum(tributos_item.values()))),
        })

    return {t: dinheiro(v) for t, v in por_tributo.items()}, detalhe


def _chave_fracao(tributo: str) -> str:
    # PIS e COFINS compartilham a mesma fração de transição.
    return "pis_cofins" if tributo in ("pis", "cofins") else tributo


def calcular_creditos(
    entrada: EntradaSimulacao,
    itens: list[ItemEntrada],
    fracoes_ano: dict | None = None,
) -> Decimal:
    """Créditos aproveitados no sistema atual."""
    fracoes_ano = fracoes_ano or {}
    if entrada.regime == "simples":
        # No Simples não há apuração de crédito pelo próprio contribuinte.
        return ZERO

    # Alíquotas médias ponderadas pelos itens, para aplicar sobre as entradas.
    aliq_pis_cofins = sum(
        (_aliq_item(i, "pis") + _aliq_item(i, "cofins")) * D(i.pct_faturamento) for i in itens
    )
    aliq_icms = sum(_aliq_item(i, "icms") * D(i.pct_faturamento) for i in itens)

    f_pis = D(str(fracoes_ano.get("pis_cofins", 1)))
    f_icms = D(str(fracoes_ano.get("icms", 1)))

    amortecedor = (
        D(entrada.pct_compras_com_credito)
        if entrada.pct_compras_com_credito is not None
        else D("1")
    )

    total = ZERO
    for custo in entrada.custos:
        if not custo.gera_credito_hoje:
            continue
        base = D(custo.valor_anual)
        total += base * aliq_pis_cofins * f_pis
        if custo.origem in ORIGENS_COM_ICMS:
            total += base * aliq_icms * f_icms

    return dinheiro(total * amortecedor)


def calcular(
    entrada: EntradaSimulacao,
    itens: list[ItemEntrada],
    fracoes_ano: dict | None = None,
) -> dict:
    receita = D(entrada.faturamento_anual)
    debitos, detalhe = calcular_debitos(entrada, itens, fracoes_ano)
    creditos = calcular_creditos(entrada, itens, fracoes_ano)

    total_debitos = dinheiro(sum(debitos.values()))
    carga_liquida = dinheiro(total_debitos - creditos)

    return {
        "receita_bruta_rs": str(dinheiro(receita)),
        "tributos_rs": {t: str(v) for t, v in debitos.items()},
        "total_debitos_rs": str(total_debitos),
        "creditos_rs": str(creditos),
        "carga_liquida_rs": str(carga_liquida),
        "carga_pct_receita": str(pct(carga_liquida, receita)),
        # Base sem tributos: o que está embutido no preço é o DÉBITO.
        # O crédito é recuperado na aquisição, não compõe o preço de venda.
        "receita_liquida_rs": str(dinheiro(receita - total_debitos)),
        "itens": detalhe,
    }
