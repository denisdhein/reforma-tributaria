"""
Estruturas de entrada e saída do motor.

O motor é puro: não conhece banco, não conhece FastAPI, não conhece IA.
Recebe dataclasses, devolve dicionário. Isso é o que torna ele testável
e o que permite reproduzir uma simulação antiga a partir do snapshot.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

D = Decimal
ZERO = D("0")


@dataclass(frozen=True)
class ItemEntrada:
    """Produto ou serviço. O cálculo roda item a item e agrega depois."""

    descricao: str
    pct_faturamento: Decimal
    aliq_icms: Decimal = ZERO
    aliq_iss: Decimal = ZERO
    aliq_pis: Decimal = ZERO
    aliq_cofins: Decimal = ZERO
    aliq_ipi: Decimal = ZERO
    regime_diferenciado: str = "padrao"
    sujeito_imposto_seletivo: bool = False


@dataclass(frozen=True)
class CustoEntrada:
    origem: str
    valor_anual: Decimal
    pct_fornecedor_simples: Decimal = ZERO
    gera_credito_hoje: bool = False
    # Fração deste custo já composta de imposto ATUAL embutido no preço do
    # fornecedor. Nulo = usa EntradaSimulacao.pct_imposto_embutido_custos
    # (padrão da empresa) — calibração 2, opção A: crédito por linha.
    pct_imposto_embutido: Decimal | None = None


@dataclass(frozen=True)
class EntradaSimulacao:
    razao_social: str
    regime: str                      # simples | presumido | real
    faturamento_anual: Decimal

    itens: list[ItemEntrada] = field(default_factory=list)
    custos: list[CustoEntrada] = field(default_factory=list)

    # Simples Nacional
    simples_anexo: int | None = None
    rbt12: Decimal | None = None

    # Alíquotas da empresa — usadas quando não há itens cadastrados
    aliq_icms: Decimal = ZERO
    aliq_iss: Decimal = ZERO
    aliq_pis: Decimal = ZERO
    aliq_cofins: Decimal = ZERO
    aliq_ipi: Decimal = ZERO

    margem_bruta: Decimal | None = None
    margem_liquida: Decimal | None = None
    pct_compras_com_credito: Decimal | None = None

    # Fração média do custo já composta de imposto ATUAL embutido no preço
    # do fornecedor — desconta antes de creditar IBS/CBS sobre a compra, pra
    # não creditar imposto novo em cima de imposto antigo. Nulo = 0 (assume
    # todo custo informado já líquido; calibração 2 do motor, ver README).
    pct_imposto_embutido_custos: Decimal | None = None

    def itens_efetivos(self) -> tuple[list[ItemEntrada], str]:
        """
        Item a item quando há itens cadastrados; agregado quando não há.

        No modo agregado, sintetiza um item único de 100% do faturamento com
        as alíquotas da empresa. O modo usado é declarado no resultado e nas
        premissas — nunca fica implícito.
        """
        if self.itens:
            return list(self.itens), "item_a_item"

        sintetico = ItemEntrada(
            descricao="Faturamento agregado (sem itens cadastrados)",
            pct_faturamento=D("1"),
            aliq_icms=self.aliq_icms,
            aliq_iss=self.aliq_iss,
            aliq_pis=self.aliq_pis,
            aliq_cofins=self.aliq_cofins,
            aliq_ipi=self.aliq_ipi,
        )
        return [sintetico], "agregado"
