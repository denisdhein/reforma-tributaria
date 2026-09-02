"""
Substitui {{chave}} pelo valor formatado — só roda depois que a verificação
já aprovou que toda chave citada existe em `referencias` (ver servico.py).
Formata pela convenção de nome que o motor já usa: sufixo _rs é dinheiro,
"aliquota_efetiva"/"margem_liquida"/sufixo _pct são fração a exibir em
percentual, variacao_margem_pp já vem em pontos percentuais (não é fração).
"""

from __future__ import annotations

from app.formatacao import moeda, numero, pctfmt
from app.ia.verificacao import PADRAO_REFERENCIA

_DIRECOES = {"aumento": "aumento", "reducao": "redução", "neutro": "estável"}


def _formatar(chave: str, valor: str) -> str:
    if chave == "comparacao.direcao":
        return _DIRECOES.get(valor, valor)
    if chave.endswith("variacao_margem_pp"):
        return numero(valor) + " p.p."
    if chave.endswith("_rs"):
        return moeda(valor)
    # Substring, não endswith: chaves como "atual.carga_pct_receita" têm
    # "_pct" no meio, não no fim — endswith deixava passar cru (achado
    # rodando a análise de verdade: "0.201800" aparecendo sem formatar).
    if "_pct" in chave or "aliquota_efetiva" in chave or "margem_liquida" in chave:
        return pctfmt(valor)
    return valor


def renderizar(texto: str, referencias: dict) -> str:
    def _sub(m) -> str:
        chave = m.group(1)
        valor = referencias.get(chave)
        return _formatar(chave, valor) if valor is not None else m.group(0)

    return PADRAO_REFERENCIA.sub(_sub, texto)
