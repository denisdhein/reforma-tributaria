from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

D = Decimal
ZERO = D("0")

CENTAVO = D("0.01")
FRACAO = D("0.000001")


def dinheiro(v: Decimal) -> Decimal:
    """Arredonda para centavo. ROUND_HALF_UP é a convenção fiscal brasileira."""
    return D(v).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def fracao(v: Decimal) -> Decimal:
    return D(v).quantize(FRACAO, rounding=ROUND_HALF_UP)


def pct(parte: Decimal, todo: Decimal) -> Decimal:
    if not todo:
        return ZERO
    return fracao(D(parte) / D(todo))


def s(v: Decimal | None) -> str | None:
    """Serializa Decimal para JSON sem perder precisão."""
    return None if v is None else str(v)
