from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint, DateTime, Enum, ForeignKey, Index, Integer,
    Numeric, String, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, JSONType, OpcaoSimplesIBSCBS, StatusVerificacao


class Simulacao(Base):
    """
    Snapshot imutável. Os campos *_snapshot congelam tudo que entrou no cálculo.
    As FKs de rastreabilidade não participam da releitura do resultado — editar
    um cenário no painel admin não pode alterar retroativamente o que já foi salvo.
    """

    __tablename__ = "simulacao"
    __table_args__ = (
        Index("ix_simulacao_tenant_criada", "tenant_id", "criada_em"),
        Index("ix_simulacao_empresa", "empresa_id"),
        CheckConstraint("ano_base between 2026 and 2033", name="ck_simulacao_ano"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant.id"), index=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id"))
    empresa: Mapped["Empresa"] = relationship()  # noqa: F821

    titulo: Mapped[str | None] = mapped_column(String(200))
    ano_base: Mapped[int] = mapped_column(Integer)

    # ---- snapshot congelado ----
    dados_informados: Mapped[dict] = mapped_column(JSONType)
    cenario_aliquota_snapshot: Mapped[dict] = mapped_column(JSONType)
    regras_snapshot: Mapped[dict] = mapped_column(JSONType)
    motor_versao: Mapped[str] = mapped_column(String(40))
    resultado: Mapped[dict] = mapped_column(JSONType)

    # ---- desnormalizado para filtro e ordenação ----
    carga_atual_rs: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    carga_futura_rs: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    diferenca_rs: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    diferenca_pct: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    margem_liquida_depois: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))

    # Simples: qual opção este resultado representa. Nulo nos demais regimes.
    opcao_simples: Mapped[OpcaoSimplesIBSCBS | None] = mapped_column(
        Enum(OpcaoSimplesIBSCBS, native_enum=False, length=20)
    )
    # Amarra as duas rodadas (único e híbrido) de uma mesma análise.
    grupo_comparacao: Mapped[str | None] = mapped_column(String(36), index=True)

    # ---- rastreabilidade, sem efeito no cálculo ----
    cenario_aliquota_id: Mapped[int | None] = mapped_column(ForeignKey("cenario_aliquota.id"))
    regras_versao_id: Mapped[int | None] = mapped_column(ForeignKey("regras_versao.id"))

    criada_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    criada_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))

    analise: Mapped["AnaliseIA | None"] = relationship(
        back_populates="simulacao", uselist=False, cascade="all, delete-orphan"
    )


class AnaliseIA(Base):
    """Rastro da chamada ao modelo e da verificação determinística."""

    __tablename__ = "analise_ia"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant.id"), index=True)
    simulacao_id: Mapped[int] = mapped_column(ForeignKey("simulacao.id"), unique=True)

    modelo: Mapped[str] = mapped_column(String(80))
    prompt_enviado: Mapped[str] = mapped_column(Text)
    resposta_bruta: Mapped[str] = mapped_column(Text)
    # Após substituir as referências numéricas pelos valores do motor
    resposta_renderizada: Mapped[str | None] = mapped_column(Text)

    # Detalhe de cada checagem: aderência numérica, coerência de direção,
    # menção às limitações, menção ao cenário, afirmação normativa sem citação.
    verificacao: Mapped[dict] = mapped_column(JSONType)
    status_verificacao: Mapped[StatusVerificacao] = mapped_column(
        Enum(StatusVerificacao, native_enum=False, length=20)
    )

    tokens_entrada: Mapped[int | None] = mapped_column(Integer)
    tokens_saida: Mapped[int | None] = mapped_column(Integer)
    custo_estimado: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    latencia_ms: Mapped[int | None] = mapped_column(Integer)

    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    simulacao: Mapped[Simulacao] = relationship(back_populates="analise")


class LogAuditoria(Base):
    __tablename__ = "log_auditoria"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int | None] = mapped_column(ForeignKey("tenant.id"), index=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))

    acao: Mapped[str] = mapped_column(String(80))    # "cenario.editar", "tenant.impersonar"
    entidade: Mapped[str | None] = mapped_column(String(80))
    entidade_id: Mapped[int | None] = mapped_column(Integer)
    detalhe: Mapped[dict | None] = mapped_column(JSONType)

    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
