from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Index, Integer,
    Numeric, String, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    Base, JSONType, OpcaoSimplesIBSCBS, OrigemCusto, RegimeTributario,
)


class Empresa(Base):
    __tablename__ = "empresa"
    __table_args__ = (
        Index("ix_empresa_tenant_cnpj", "tenant_id", "cnpj"),
        CheckConstraint("faturamento_anual >= 0", name="ck_empresa_faturamento"),
        CheckConstraint(
            "simples_anexo is null or simples_anexo between 1 and 5",
            name="ck_empresa_simples_anexo",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant.id"), index=True)

    razao_social: Mapped[str] = mapped_column(String(255))
    cnpj: Mapped[str | None] = mapped_column(String(14))
    uf: Mapped[str] = mapped_column(String(2))
    municipio: Mapped[str] = mapped_column(String(120))
    cnae_principal: Mapped[str | None] = mapped_column(String(7))
    ramo: Mapped[str | None] = mapped_column(String(120))

    regime: Mapped[RegimeTributario] = mapped_column(
        Enum(RegimeTributario, native_enum=False, length=20)
    )

    # Simples Nacional — anexo I a V. Nulo nos demais regimes.
    simples_anexo: Mapped[int | None] = mapped_column(Integer)
    # Opção pretendida para IBS/CBS a partir de 2027 (art. 41, §3º LC 214/2025).
    # Serve de padrão; a análise comparativa roda os dois cenários de qualquer forma.
    simples_opcao_ibs_cbs: Mapped[OpcaoSimplesIBSCBS | None] = mapped_column(
        Enum(OpcaoSimplesIBSCBS, native_enum=False, length=20)
    )

    faturamento_anual: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    # RBT12 pode divergir do faturamento informado. Se nulo, o motor usa o faturamento.
    rbt12: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))

    # Composição do faturamento (frações)
    pct_interno: Mapped[Decimal] = mapped_column(Numeric(9, 6), default=0)
    pct_interestadual: Mapped[Decimal] = mapped_column(Numeric(9, 6), default=0)
    pct_exportacao: Mapped[Decimal] = mapped_column(Numeric(9, 6), default=0)
    pct_consumidor_final: Mapped[Decimal] = mapped_column(Numeric(9, 6), default=0)

    margem_bruta: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    margem_liquida: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))

    # Alíquotas efetivas praticadas hoje (regimes tradicionais)
    aliq_icms: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    aliq_iss: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    aliq_pis: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    aliq_cofins: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    aliq_ipi: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))

    # Fração das compras que gera crédito no sistema atual
    pct_compras_com_credito: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))

    # Fração média do custo que já é imposto antigo embutido no preço do
    # fornecedor (ICMS/PIS/COFINS por dentro) — usada só no crédito do
    # sistema NOVO (IBS/CBS), pra não creditar imposto novo em cima de
    # imposto antigo que ainda está no preço. Nula/zero = assume que o
    # custo informado já é líquido (comportamento anterior a esta coluna).
    # Padrão da empresa — vale só pras linhas de CustoEmpresa que não
    # informam o próprio pct_imposto_embutido (calibração 2, opção A do
    # motor, ver README): antes era o único jeito de informar isso, agora
    # é o "senão" de um valor mais preciso por linha.
    pct_imposto_embutido_custos: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))

    beneficios_fiscais: Mapped[dict | None] = mapped_column(JSONType)
    observacoes: Mapped[str | None] = mapped_column(Text)

    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizada_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    tenant: Mapped["Tenant"] = relationship(back_populates="empresas")  # noqa: F821
    custos: Mapped[list["CustoEmpresa"]] = relationship(
        back_populates="empresa", cascade="all, delete-orphan"
    )
    itens: Mapped[list["ItemEmpresa"]] = relationship(
        back_populates="empresa", cascade="all, delete-orphan"
    )


class CustoEmpresa(Base):
    """Custos e despesas por origem — insumo do cálculo de crédito."""

    __tablename__ = "custo_empresa"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant.id"), index=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id"), index=True)

    origem: Mapped[OrigemCusto] = mapped_column(Enum(OrigemCusto, native_enum=False, length=30))
    valor_anual: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    # Fração adquirida de fornecedor optante pelo Simples em regime único.
    # Limita o crédito aproveitável pelo adquirente no cenário pós-reforma.
    pct_fornecedor_simples: Mapped[Decimal] = mapped_column(Numeric(9, 6), default=0)
    gera_credito_hoje: Mapped[bool] = mapped_column(Boolean, default=False)

    # Fração deste custo específico que já é imposto atual embutido no
    # preço do fornecedor — sobrepõe Empresa.pct_imposto_embutido_custos
    # quando informado (mesma regra de override que ItemEmpresa já usa
    # pras alíquotas). Nulo = usa o padrão da empresa. Calibração 2, opção
    # A do motor: crédito por linha de custo, mais preciso que uma média
    # única — ver README "Calibrações do motor".
    pct_imposto_embutido: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))

    empresa: Mapped[Empresa] = relationship(back_populates="custos")


class ItemEmpresa(Base):
    """Produto ou serviço, para o detalhamento item a item."""

    __tablename__ = "item_empresa"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant.id"), index=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id"), index=True)

    descricao: Mapped[str] = mapped_column(String(255))
    ncm: Mapped[str | None] = mapped_column(String(8))
    codigo_servico: Mapped[str | None] = mapped_column(String(20))

    pct_faturamento: Mapped[Decimal] = mapped_column(Numeric(9, 6))

    # Tributação atual do item (sobrepõe a da empresa quando informada)
    aliq_icms: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    aliq_iss: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    aliq_pis: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    aliq_cofins: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    aliq_ipi: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))

    # Enquadramento futuro
    cst_ibs_cbs: Mapped[str | None] = mapped_column(String(3))
    c_class_trib: Mapped[str | None] = mapped_column(String(6))
    # Chave em RegrasVersao.parametros["regimes_diferenciados"]
    regime_diferenciado: Mapped[str | None] = mapped_column(String(60))
    sujeito_imposto_seletivo: Mapped[bool] = mapped_column(Boolean, default=False)

    empresa: Mapped[Empresa] = relationship(back_populates="itens")
