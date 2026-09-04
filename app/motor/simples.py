"""
Simples Nacional — regime único vs. regime híbrido (art. 41, §3º LC 214/2025).

Alíquota efetiva
----------------
    efetiva = (RBT12 * aliquota_nominal - parcela_a_deduzir) / RBT12

Uma fórmula, alimentada por tabela parametrizada de anexos e faixas.

Regime único
------------
IBS e CBS permanecem dentro do DAS. O crédito transferível ao adquirente PJ
fica limitado à fração de IBS/CBS embutida no DAS — bem menor que a alíquota
cheia. A própria empresa não se credita das aquisições.

Regime híbrido
--------------
IBS e CBS saem do DAS e são apurados pelo regime regular, com não
cumulatividade plena e crédito integral ao adquirente. O DAS é reduzido pela
parcela correspondente.

O crédito transferido ao cliente é calculado e devolvido porque é ele, e não
apenas a carga própria, que decide a escolha entre os dois regimes.

Não implementado no MVP (ver limitações): Fator R, sublimites estaduais,
segregação de receitas, substituição tributária, monofásicos e MEI.
"""

from __future__ import annotations

from decimal import Decimal

from app.motor.tipos import EntradaSimulacao
from app.motor.util import D, ZERO, dinheiro, fracao


class ForaDoSimples(ValueError):
    pass


def aliquota_efetiva(rbt12: Decimal, anexo: list[dict]) -> tuple[Decimal, dict]:
    """Devolve a alíquota efetiva e a faixa aplicada."""
    if not anexo:
        raise ForaDoSimples("Anexo não parametrizado nesta versão de regras.")
    if rbt12 <= 0:
        raise ForaDoSimples("RBT12 deve ser maior que zero.")

    faixa = next((f for f in anexo if rbt12 <= D(str(f["ate"]))), None)
    if faixa is None:
        raise ForaDoSimples("RBT12 acima do limite do Simples Nacional.")

    nominal = D(str(faixa["aliquota"]))
    deduzir = D(str(faixa["deduzir"]))
    efetiva = (rbt12 * nominal - deduzir) / rbt12
    return fracao(efetiva), faixa


def calcular(
    entrada: EntradaSimulacao,
    opcao: str,
    parametros: dict,
    aliq_ibs: Decimal,
    aliq_cbs: Decimal,
    fracoes_ano: dict,
) -> dict:
    cfg = parametros["simples"]
    anexo_id = str(entrada.simples_anexo)
    anexo = cfg["anexos"].get(anexo_id, [])
    rbt12 = D(entrada.rbt12 or entrada.faturamento_anual)
    receita = D(entrada.faturamento_anual)

    efetiva, faixa = aliquota_efetiva(rbt12, anexo)
    das_cheio = dinheiro(receita * efetiva)

    pct_ibs_cbs = D(str(cfg["pct_ibs_cbs_no_das"].get(anexo_id, 0)))
    parcela_ibs_cbs = dinheiro(das_cheio * pct_ibs_cbs)

    f_ibs = D(str(fracoes_ano.get("ibs", 0)))
    f_cbs = D(str(fracoes_ano.get("cbs", 0)))

    if opcao == "unico":
        das = das_cheio
        ibs_cbs_por_fora = ZERO
        creditos = dinheiro(ZERO)
        # Teto do crédito transferível ao cliente PJ.
        credito_ao_cliente = parcela_ibs_cbs
    elif opcao == "hibrido":
        das = dinheiro(das_cheio - parcela_ibs_cbs)
        # Receita líquida do que ainda fica embutido no preço (o DAS
        # reduzido) — mesma convenção "por fora" do resto do motor.
        # Achado testando com dados reais: usar a receita bruta aqui
        # inflava o IBS/CBS do híbrido e distorcia a comparação com o
        # único, que é o resultado principal desta parte do motor.
        receita_liquida = dinheiro(receita - das)
        aliq_total = aliq_ibs * f_ibs + aliq_cbs * f_cbs
        ibs_cbs_por_fora = dinheiro(receita_liquida * aliq_total)
        # Mesmo desconto de imposto atual embutido usado em futuro.py — por
        # linha de custo quando informado (calibração 2, opção A), senão o
        # padrão da empresa. Sem isso credita IBS/CBS em cima de um custo
        # que ainda carrega ICMS/PIS/COFINS antigo (ver README).
        padrao_empresa = D(entrada.pct_imposto_embutido_custos or 0)
        creditos = dinheiro(
            sum(
                D(c.valor_anual)
                * (D("1") - (D(c.pct_imposto_embutido) if c.pct_imposto_embutido is not None else padrao_empresa))
                * aliq_total
                for c in entrada.custos
                if c.origem != "folha"
            )
        )
        credito_ao_cliente = ibs_cbs_por_fora
    else:
        raise ValueError(f"Opção inválida: {opcao}")

    carga_liquida = dinheiro(das + ibs_cbs_por_fora - creditos)

    return {
        "opcao": opcao,
        "anexo": entrada.simples_anexo,
        "rbt12_rs": str(dinheiro(rbt12)),
        "faixa": faixa["faixa"],
        "aliquota_efetiva": str(efetiva),
        "das_rs": str(das),
        "ibs_cbs_por_fora_rs": str(ibs_cbs_por_fora),
        "creditos_rs": str(creditos),
        "carga_liquida_rs": str(carga_liquida),
        "credito_transferido_ao_cliente_rs": str(dinheiro(credito_ao_cliente)),
        "receita_bruta_rs": str(dinheiro(receita)),
    }
