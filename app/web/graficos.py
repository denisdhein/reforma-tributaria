"""
RF06: "exibir resultados em tabelas, cartões e gráficos simples" — só
faltava o gráfico. Sem lib nova: barras são `<div>` com altura em %,
coloridas via variável CSS (tema-aware de graça, sem duplicar cor por
tema). O template calcula a barra mais alta = 100%; nada aqui decide
número, só a proporção visual de valores que o motor já calculou.
"""

from __future__ import annotations

from decimal import Decimal

D = Decimal


def _montar_barras(itens: list[tuple[str, Decimal, str]]) -> list[dict]:
    maior = max((abs(v) for _, v, _ in itens), default=D("0"))
    barras = []
    for rotulo, valor, cor in itens:
        altura = (abs(valor) / maior * D("100")) if maior > 0 else D("0")
        altura = max(altura, D("4"))  # barra de valor pequeno não pode sumir
        barras.append({"rotulo": rotulo, "valor": str(valor), "altura_pct": float(altura), "cor": cor})
    return barras


def montar_grafico_atual_futuro(resultado: dict) -> list[dict]:
    atual = D(resultado["atual"]["carga_liquida_rs"])
    futuro = D(resultado["futuro"]["carga_liquida_rs"])
    direcao = resultado["comparacao"]["direcao"]
    cor_futuro = {
        "aumento": "var(--cor-perigo)", "reducao": "var(--cor-sucesso)", "neutro": "var(--cor-primaria)",
    }[direcao]
    ano = resultado["meta"]["ano_base"]
    return _montar_barras([
        ("Atual (plena carga)", atual, "var(--cor-texto-suave)"),
        (f"Simulado em {ano}", futuro, cor_futuro),
    ])


def montar_grafico_simples(resultado: dict) -> list[dict] | None:
    """None quando não há as duas opções calculadas para comparar (regime
    não é Simples, ou a simulação pediu só uma opção explicitamente)."""
    simples = resultado.get("simples")
    if not simples or "unico" not in simples or "hibrido" not in simples:
        return None

    unico = D(simples["unico"]["carga_liquida_rs"])
    hibrido = D(simples["hibrido"]["carga_liquida_rs"])
    cor_unico = "var(--cor-sucesso)" if unico <= hibrido else "var(--cor-texto-suave)"
    cor_hibrido = "var(--cor-sucesso)" if hibrido < unico else "var(--cor-texto-suave)"
    return _montar_barras([("Único", unico, cor_unico), ("Híbrido", hibrido, cor_hibrido)])
