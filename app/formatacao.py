"""
Formatação pt-BR de moeda e percentual. Compartilhado entre os filtros
Jinja da interface web e o renderizador da camada de IA — a mesma regra que
formata um valor na tela formata o mesmo valor quando a IA o referencia.
"""

from __future__ import annotations

from decimal import Decimal


def moeda(v: str | Decimal) -> str:
    d = Decimal(str(v))
    negativo = d < 0
    inteiro_str = f"{abs(d):,.2f}"
    inteiro_str = inteiro_str.replace(",", "_").replace(".", ",").replace("_", ".")
    return ("-R$ " if negativo else "R$ ") + inteiro_str


def pctfmt(v: str | Decimal, casas: int = 2) -> str:
    d = Decimal(str(v)) * 100
    return f"{d:.{casas}f}".replace(".", ",") + "%"


def numero(v: str | Decimal, casas: int = 2) -> str:
    d = Decimal(str(v))
    return f"{d:.{casas}f}".replace(".", ",")
