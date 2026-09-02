"""
Cenário pós-reforma: CBS, IBS e Imposto Seletivo.

Premissa de comparação — receita líquida constante
--------------------------------------------------
IBS e CBS são calculados por fora: incidem sobre o valor da operação sem
os próprios tributos. Comparar a alíquota nominal do novo sistema com a do
atual induz a erro grosseiro.

O motor mantém constante a RECEITA LÍQUIDA de tributos. A base de IBS/CBS é
a receita líquida apurada no cenário atual, e o preço bruto passa a ser
liquido × (1 + alíquota). Essa é a premissa declarada; a alternativa
(preço final ao consumidor constante) não está implementada no MVP e consta
nas limitações.

Premissa — crédito de fornecedor do Simples
-------------------------------------------
Compra de optante pelo Simples em regime único gera crédito limitado ao
IBS/CBS embutido no DAS, bem menor que a alíquota cheia. O motor aplica
`fator_credito_fornecedor_simples`, parâmetro de RegrasVersao.
"""

from __future__ import annotations

from decimal import Decimal

from app.motor.tipos import EntradaSimulacao, ItemEntrada
from app.motor.util import D, ZERO, dinheiro, pct

SEM_CREDITO = {"folha"}


def _multiplicador_regime(regimes: dict, chave: str | None) -> Decimal:
    if not chave:
        return D("1")
    return D(str(regimes.get(chave, 1)))


def calcular_debitos(
    receita_liquida_base: Decimal,
    itens: list[ItemEntrada],
    aliq_ibs: Decimal,
    aliq_cbs: Decimal,
    fracoes_ano: dict,
    regimes: dict,
    seletivo: dict,
) -> tuple[dict, list[dict]]:
    f_ibs = D(str(fracoes_ano.get("ibs", 0)))
    f_cbs = D(str(fracoes_ano.get("cbs", 0)))

    total = {"ibs": ZERO, "cbs": ZERO, "is": ZERO}
    detalhe: list[dict] = []

    for item in itens:
        base = receita_liquida_base * D(item.pct_faturamento)
        mult = _multiplicador_regime(regimes, item.regime_diferenciado)

        ibs = base * aliq_ibs * mult * f_ibs
        cbs = base * aliq_cbs * mult * f_cbs

        imposto_seletivo = ZERO
        if seletivo.get("habilitado") and item.sujeito_imposto_seletivo:
            aliq_is = D(str(seletivo.get("aliquotas", {}).get(item.descricao, 0)))
            imposto_seletivo = base * aliq_is

        total["ibs"] += ibs
        total["cbs"] += cbs
        total["is"] += imposto_seletivo

        detalhe.append({
            "descricao": item.descricao,
            "pct_faturamento": str(item.pct_faturamento),
            "base_rs": str(dinheiro(base)),
            "regime_diferenciado": item.regime_diferenciado,
            "multiplicador_regime": str(mult),
            "tributos_rs": {
                "ibs": str(dinheiro(ibs)),
                "cbs": str(dinheiro(cbs)),
                "is": str(dinheiro(imposto_seletivo)),
            },
            "total_rs": str(dinheiro(ibs + cbs + imposto_seletivo)),
        })

    return {k: dinheiro(v) for k, v in total.items()}, detalhe


def calcular_creditos(
    entrada: EntradaSimulacao,
    aliq_ibs: Decimal,
    aliq_cbs: Decimal,
    fracoes_ano: dict,
    fator_simples: Decimal,
) -> tuple[Decimal, list[dict]]:
    """
    Não cumulatividade ampla: crédito sobre praticamente toda aquisição.
    Folha não gera crédito. Fornecedor do Simples em regime único gera
    crédito reduzido.

    `pct_imposto_embutido_custos` desconta do custo a fração que já é
    imposto ATUAL embutido no preço do fornecedor, antes de aplicar a
    alíquota NOVA — sem isso, credita-se IBS/CBS em cima de um valor que
    ainda carrega ICMS/PIS/COFINS antigo, superestimando o crédito
    (calibração 2 do motor, ver README). Zero/não informado preserva o
    comportamento anterior a este parâmetro.
    """
    f_ibs = D(str(fracoes_ano.get("ibs", 0)))
    f_cbs = D(str(fracoes_ano.get("cbs", 0)))
    aliq_total = aliq_ibs * f_ibs + aliq_cbs * f_cbs
    fator_liquido = D("1") - D(entrada.pct_imposto_embutido_custos or 0)

    total = ZERO
    detalhe: list[dict] = []

    for custo in entrada.custos:
        if custo.origem in SEM_CREDITO:
            detalhe.append({
                "origem": custo.origem,
                "valor_rs": str(dinheiro(D(custo.valor_anual))),
                "credito_rs": "0.00",
                "motivo": "folha não gera crédito",
            })
            continue

        base = D(custo.valor_anual) * fator_liquido
        p_simples = D(custo.pct_fornecedor_simples or 0)

        credito_regular = base * (D("1") - p_simples) * aliq_total
        credito_simples = base * p_simples * aliq_total * fator_simples
        credito = credito_regular + credito_simples

        total += credito
        detalhe.append({
            "origem": custo.origem,
            "valor_rs": str(dinheiro(D(custo.valor_anual))),
            "pct_fornecedor_simples": str(p_simples),
            "credito_rs": str(dinheiro(credito)),
        })

    return dinheiro(total), detalhe


def calcular(
    entrada: EntradaSimulacao,
    itens: list[ItemEntrada],
    receita_liquida_base: Decimal,
    aliq_ibs: Decimal,
    aliq_cbs: Decimal,
    fracoes_ano: dict,
    parametros: dict,
    residuo_antigos: dict | None = None,
    creditos_antigos: Decimal = ZERO,
) -> dict:
    """
    Cenário do ano simulado.

    Durante a transição a empresa paga os dois sistemas ao mesmo tempo: o
    resíduo dos tributos antigos na fração vigente do ano, mais IBS/CBS na
    fração deles. `residuo_antigos` vem do módulo `atual`, calculado com as
    frações do ano.
    """
    residuo_antigos = residuo_antigos or {}
    regimes = parametros.get("regimes_diferenciados", {})
    seletivo = parametros.get("imposto_seletivo", {})
    fator_simples = D(str(parametros.get("fator_credito_fornecedor_simples", "0.25")))

    debitos, detalhe_itens = calcular_debitos(
        receita_liquida_base, itens, aliq_ibs, aliq_cbs, fracoes_ano, regimes, seletivo
    )
    creditos, detalhe_creditos = calcular_creditos(
        entrada, aliq_ibs, aliq_cbs, fracoes_ano, fator_simples
    )

    debitos_novos = dinheiro(sum(debitos.values()))
    debitos_antigos = dinheiro(sum(D(v) for v in residuo_antigos.values()))
    total_debitos = dinheiro(debitos_novos + debitos_antigos)

    creditos_totais = dinheiro(creditos + creditos_antigos)
    carga_liquida = dinheiro(total_debitos - creditos_totais)
    # Os tributos antigos são por dentro (já no preço); os novos, por fora.
    receita_bruta = dinheiro(receita_liquida_base + debitos_antigos + debitos_novos)

    todos = {k: str(v) for k, v in debitos.items()}
    todos.update({k: str(v) for k, v in residuo_antigos.items() if D(v) != 0})

    return {
        "receita_bruta_rs": str(receita_bruta),
        "receita_liquida_rs": str(dinheiro(receita_liquida_base)),
        "tributos_rs": todos,
        "debitos_novos_rs": str(debitos_novos),
        "debitos_antigos_residuais_rs": str(debitos_antigos),
        "total_debitos_rs": str(total_debitos),
        "creditos_rs": str(creditos_totais),
        "carga_liquida_rs": str(carga_liquida),
        "carga_pct_receita": str(pct(carga_liquida, D(entrada.faturamento_anual))),
        "itens": detalhe_itens,
        "detalhe_creditos": detalhe_creditos,
    }
