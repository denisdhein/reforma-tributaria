"""
Orquestrador do motor.

Contrato: recebe dataclasses puras, devolve dicionário serializável.
Não conhece banco, FastAPI nem IA.

O dicionário de saída inclui `referencias`: um mapa plano de identificador
estável para valor. É ele que a camada de IA recebe. A IA não digita números
— ela referencia chaves deste mapa, e o sistema substitui na renderização.
Isso torna invenção numérica estruturalmente impossível.
"""

from __future__ import annotations

from decimal import Decimal

from app.motor import atual, futuro, simples
from app.motor.tipos import EntradaSimulacao
from app.motor.util import D, ZERO, dinheiro, fracao, pct

MOTOR_VERSAO = "0.1.0"


def _baseline_simples(entrada: EntradaSimulacao, parametros: dict) -> dict:
    """
    Baseline do Simples: o DAS de hoje, a plena carga, sem separar IBS/CBS.
    Sem isso a comparação parte de zero e o resultado fica sem sentido.
    """
    cfg = parametros["simples"]
    anexo = cfg["anexos"].get(str(entrada.simples_anexo), [])
    rbt12 = D(entrada.rbt12 or entrada.faturamento_anual)
    receita = D(entrada.faturamento_anual)

    efetiva, faixa = simples.aliquota_efetiva(rbt12, anexo)
    das = dinheiro(receita * efetiva)

    return {
        "receita_bruta_rs": str(dinheiro(receita)),
        "tributos_rs": {"das": str(das)},
        "total_debitos_rs": str(das),
        "creditos_rs": "0.00",
        "carga_liquida_rs": str(das),
        "carga_pct_receita": str(pct(das, receita)),
        "receita_liquida_rs": str(dinheiro(receita - das)),
        "aliquota_efetiva_das": str(efetiva),
        "faixa": faixa["faixa"],
        "itens": [],
    }


def _fracoes(parametros: dict, ano_base: int) -> dict:
    anos = parametros.get("anos", {})
    chave = str(ano_base)
    if chave not in anos:
        raise ValueError(f"Ano {ano_base} não parametrizado nesta versão de regras.")
    return anos[chave]


def _direcao(diferenca: Decimal) -> str:
    if diferenca > 0:
        return "aumento"
    if diferenca < 0:
        return "reducao"
    return "neutro"


def _limitacoes(parametros: dict, modo: str, entrada: EntradaSimulacao) -> list[str]:
    lim = [
        "O cenário atual é o sistema vigente a plena carga, usado como "
        "referência fixa. O cenário do ano simulado soma o resíduo dos "
        "tributos antigos ao IBS/CBS já vigentes naquele ano.",
        "Comparação feita com receita líquida de tributos constante. "
        "A alternativa de preço final ao consumidor constante não está implementada.",
        "IPI tratado como incidente sobre o faturamento, sem apuração por etapa.",
        "Créditos do sistema atual modelados por origem de custo, sem a lista "
        "taxativa da legislação vigente.",
        "Alíquotas de referência de IBS e CBS não estão fixadas por Resolução do "
        "Senado. O resultado é projeção sobre o cenário escolhido, não apuração.",
    ]
    if modo == "agregado":
        lim.append(
            "Empresa sem itens cadastrados: cálculo feito sobre o faturamento "
            "agregado, com as alíquotas médias da empresa. O detalhamento por "
            "produto não está disponível nesta simulação."
        )
    if entrada.regime == "simples":
        nao_impl = parametros.get("simples", {}).get("nao_implementado", [])
        if nao_impl:
            lim.append(
                "Simples Nacional: não implementados " + ", ".join(nao_impl) + "."
            )
    if not parametros.get("imposto_seletivo", {}).get("habilitado"):
        lim.append(
            "Imposto Seletivo desabilitado: alíquotas dependem de lei ainda não "
            "aprovada."
        )
    lim.append(_limitacao_imposto_embutido(entrada))
    return lim


def _limitacao_imposto_embutido(entrada: EntradaSimulacao) -> str:
    """
    Calibração 2 (opção A): cada CustoEntrada pode informar o próprio
    `pct_imposto_embutido`, sobrepondo o padrão da empresa
    (`pct_imposto_embutido_custos`) — mesma regra de override que
    ItemEntrada já usa pras alíquotas. A limitação relata o que foi
    efetivamente usado: por linha, por padrão da empresa, misto, ou
    nenhum desconto (comportamento anterior a esse parâmetro existir).
    """
    padrao = D(entrada.pct_imposto_embutido_custos or 0)
    creditaveis = [c for c in entrada.custos if c.origem != "folha"]
    com_valor_proprio = sum(1 for c in creditaveis if c.pct_imposto_embutido is not None)

    if not creditaveis:
        return (
            "Crédito de IBS/CBS calculado sobre o valor cheio dos custos informados, sem "
            "descontar imposto atual eventualmente já embutido no preço do fornecedor."
        )
    if com_valor_proprio == len(creditaveis):
        return (
            "Crédito de IBS/CBS sobre custos descontado individualmente por linha de custo "
            "(cada uma informa quanto do próprio valor já é imposto atual embutido no preço "
            "do fornecedor)."
        )
    if com_valor_proprio:
        padrao_txt = f"{padrao * D('100'):.2f}%" if padrao else "sem desconto"
        return (
            f"Crédito de IBS/CBS sobre custos descontado de forma mista: "
            f"{com_valor_proprio} de {len(creditaveis)} linha(s) com valor próprio; as "
            f"demais usam o padrão da empresa ({padrao_txt})."
        )
    if padrao:
        return (
            f"Crédito de IBS/CBS sobre custos descontado em {padrao * D('100'):.2f}% "
            "(padrão informado no cadastro da empresa, nenhuma linha de custo tem valor "
            "próprio)."
        )
    return (
        "Crédito de IBS/CBS calculado sobre o valor cheio dos custos informados, sem "
        "descontar imposto atual eventualmente já embutido no preço do fornecedor — pode "
        "superestimar o crédito. Informe o \"% de imposto já embutido\" por linha de custo "
        "ou um padrão no cadastro da empresa para corrigir."
    )


def _referencias(resultado: dict) -> dict:
    """Mapa plano de identificador estável -> valor, consumido pela IA."""
    r: dict[str, str] = {}
    a, f, c = resultado["atual"], resultado["futuro"], resultado["comparacao"]

    r["atual.receita_bruta_rs"] = a["receita_bruta_rs"]
    r["atual.total_debitos_rs"] = a["total_debitos_rs"]
    r["atual.creditos_rs"] = a["creditos_rs"]
    r["atual.carga_liquida_rs"] = a["carga_liquida_rs"]
    r["atual.carga_pct_receita"] = a["carga_pct_receita"]
    for t, v in a["tributos_rs"].items():
        r[f"atual.tributo.{t}_rs"] = v

    r["futuro.receita_bruta_rs"] = f["receita_bruta_rs"]
    r["futuro.carga_liquida_rs"] = f["carga_liquida_rs"]
    r["futuro.carga_pct_receita"] = f["carga_pct_receita"]
    r["futuro.creditos_rs"] = f.get("creditos_rs", "0.00")
    for t, v in f.get("tributos_rs", {}).items():
        r[f"futuro.tributo.{t}_rs"] = v

    r["comparacao.diferenca_rs"] = c["diferenca_rs"]
    r["comparacao.diferenca_pct"] = c["diferenca_pct"]
    r["comparacao.direcao"] = c["direcao"]
    if c.get("margem_liquida_antes") is not None:
        r["comparacao.margem_liquida_antes"] = c["margem_liquida_antes"]
        r["comparacao.margem_liquida_depois"] = c["margem_liquida_depois"]
        r["comparacao.variacao_margem_pp"] = c["variacao_margem_pp"]

    if resultado.get("simples"):
        for opcao, dados in resultado["simples"].items():
            for campo in (
                "carga_liquida_rs", "das_rs", "aliquota_efetiva",
                "credito_transferido_ao_cliente_rs",
            ):
                r[f"simples.{opcao}.{campo}"] = dados[campo]

    return r


def calcular(
    entrada: EntradaSimulacao,
    ano_base: int,
    aliq_ibs: Decimal,
    aliq_cbs: Decimal,
    parametros: dict,
    opcao_simples: str | None = None,
) -> dict:
    fracoes = _fracoes(parametros, ano_base)
    itens, modo = entrada.itens_efetivos()

    # Baseline: sistema atual a PLENA CARGA. Fixo, não depende do ano simulado.
    if entrada.regime == "simples":
        res_atual = _baseline_simples(entrada, parametros)
    else:
        res_atual = atual.calcular(entrada, itens, fracoes_ano=None)
    receita_liquida = D(res_atual["receita_liquida_rs"])

    # Resíduo dos tributos antigos ainda vigente no ano simulado.
    residuo, _ = atual.calcular_debitos(entrada, itens, fracoes)
    creditos_residuais = atual.calcular_creditos(entrada, itens, fracoes)

    res_simples = None
    if entrada.regime == "simples":
        opcoes = [opcao_simples] if opcao_simples else ["unico", "hibrido"]
        res_simples = {
            o: simples.calcular(entrada, o, parametros, aliq_ibs, aliq_cbs, fracoes)
            for o in opcoes
        }
        escolhida = opcao_simples or "unico"
        base = res_simples[escolhida]
        res_futuro = {
            "receita_bruta_rs": base["receita_bruta_rs"],
            "receita_liquida_rs": str(receita_liquida),
            "tributos_rs": {
                "das": base["das_rs"],
                "ibs_cbs_por_fora": base["ibs_cbs_por_fora_rs"],
            },
            "total_debitos_rs": str(
                dinheiro(D(base["das_rs"]) + D(base["ibs_cbs_por_fora_rs"]))
            ),
            "creditos_rs": base["creditos_rs"],
            "carga_liquida_rs": base["carga_liquida_rs"],
            "carga_pct_receita": str(
                pct(D(base["carga_liquida_rs"]), D(entrada.faturamento_anual))
            ),
            "opcao_simples": escolhida,
            "itens": [],
        }
    else:
        res_futuro = futuro.calcular(
            entrada, itens, receita_liquida, aliq_ibs, aliq_cbs, fracoes, parametros,
            residuo_antigos=residuo, creditos_antigos=creditos_residuais,
        )

    carga_antes = D(res_atual["carga_liquida_rs"])
    carga_depois = D(res_futuro["carga_liquida_rs"])
    diferenca = dinheiro(carga_depois - carga_antes)

    comparacao = {
        "diferenca_rs": str(diferenca),
        "diferenca_pct": str(pct(diferenca, carga_antes) if carga_antes else ZERO),
        "direcao": _direcao(diferenca),
    }

    if entrada.margem_liquida is not None:
        receita = D(entrada.faturamento_anual)
        antes = D(entrada.margem_liquida)
        # A variação da carga desloca a margem na mesma proporção da receita.
        depois = fracao(antes - (diferenca / receita)) if receita else antes
        comparacao["margem_liquida_antes"] = str(fracao(antes))
        comparacao["margem_liquida_depois"] = str(depois)
        comparacao["variacao_margem_pp"] = str(fracao((depois - antes) * D("100")))

    resultado = {
        "meta": {
            "motor_versao": MOTOR_VERSAO,
            "ano_base": ano_base,
            "modo_calculo": modo,
            "regime": entrada.regime,
            "razao_social": entrada.razao_social,
            "premissas": {
                "comparacao": "receita_liquida_constante",
                "baseline": "sistema_atual_a_plena_carga",
                "aliquota_ibs": str(aliq_ibs),
                "aliquota_cbs": str(aliq_cbs),
                "aliquota_total": str(aliq_ibs + aliq_cbs),
                "fracoes_do_ano": fracoes,
            },
        },
        "atual": res_atual,
        "futuro": res_futuro,
        "comparacao": comparacao,
        "simples": res_simples,
        "limitacoes": _limitacoes(parametros, modo, entrada),
    }
    resultado["referencias"] = _referencias(resultado)
    return resultado
