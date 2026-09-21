"""
Formatação pt-BR de moeda e percentual. Compartilhado entre os filtros
Jinja da interface web e o renderizador da camada de IA — a mesma regra que
formata um valor na tela formata o mesmo valor quando a IA o referencia.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def email_valido(email: str) -> bool:
    """Checagem propositalmente simples (formato, não existência) —
    compartilhada entre /perfil (autoatendimento) e /usuarios (admin)."""
    return bool(_EMAIL_RE.match(email))


def texto_validado(bruto: str, campo: str, maximo: int) -> str:
    """Corta espaço nas pontas e barra texto maior que a coluna do banco
    aceita, ANTES do insert/update. Sem isso, um texto digitado além do
    `String(n)` da coluna passa liso no SQLite (sem VARCHAR real) e só
    estoura em produção (Postgres, que reforça o limite de verdade) —
    mesma classe do bug do CNPJ pontuado, só que pra qualquer campo de
    texto livre (nome de empresa, de cenário, de usuário...), não só um.
    Levanta ValueError com mensagem pronta pra tela, igual fracao_validada."""
    texto = (bruto or "").strip()
    if len(texto) > maximo:
        raise ValueError(
            f'"{campo}" tem {len(texto)} caracteres — o máximo é {maximo}. '
            f'Digitado: "{texto[:maximo]}…"'
        )
    return texto


def fracao_validada(bruto: str, campo: str, minimo: str = "0", maximo: str = "100") -> Decimal:
    """Percentual digitado (17,5) vira fração (0.175), validado entre
    `minimo` e `maximo` (em %). Levanta ValueError com mensagem pronta
    pra tela — mesma checagem usada em cenários e no cadastro de empresa,
    centralizada aqui pra não duplicar (e pra rotas.py poder usar sem
    criar import circular com cenarios.py)."""
    bruto = (bruto or "").strip().replace(",", ".")
    try:
        valor = Decimal(bruto)
    except InvalidOperation:
        raise ValueError(f'"{campo}" precisa ser um número — recebi "{bruto}".') from None
    if valor < Decimal(minimo) or valor > Decimal(maximo):
        raise ValueError(f'"{campo}" precisa estar entre {minimo} e {maximo}.')
    return valor / Decimal("100")


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
