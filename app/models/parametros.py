from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean, DateTime, Enum, ForeignKey, Numeric, String, Text,
    UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, JSONType, TipoCenario


class CenarioAliquota(Base):
    """Alíquotas de referência de IBS e CBS. Nunca constantes no código."""

    __tablename__ = "cenario_aliquota"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Nulo = cenário global (mantido pelo admin). Preenchido = criado por um tenant.
    tenant_id: Mapped[int | None] = mapped_column(ForeignKey("tenant.id"), index=True)

    nome: Mapped[str] = mapped_column(String(160))
    aliquota_ibs: Mapped[Decimal] = mapped_column(Numeric(9, 6))
    aliquota_cbs: Mapped[Decimal] = mapped_column(Numeric(9, 6))

    fonte: Mapped[str | None] = mapped_column(String(255))
    data_publicacao: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    base_legal: Mapped[str | None] = mapped_column(String(255))

    tipo: Mapped[TipoCenario] = mapped_column(Enum(TipoCenario, native_enum=False, length=20))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    substituido_por_id: Mapped[int | None] = mapped_column(ForeignKey("cenario_aliquota.id"))

    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @property
    def total(self) -> Decimal:
        return self.aliquota_ibs + self.aliquota_cbs

    def snapshot(self) -> dict:
        """Congela o cenário para gravação na simulação."""
        return {
            "id": self.id,
            "nome": self.nome,
            "aliquota_ibs": str(self.aliquota_ibs),
            "aliquota_cbs": str(self.aliquota_cbs),
            "total": str(self.total),
            "fonte": self.fonte,
            "data_publicacao": self.data_publicacao.isoformat() if self.data_publicacao else None,
            "base_legal": self.base_legal,
            "tipo": self.tipo.value,
        }


class RegrasVersao(Base):
    """
    Conjunto versionado de regras de transição. Imutável após criação:
    alterar significa criar uma nova versão.

    É o que permite representar 2026 a 2033 sem hardcode e sobreviver a
    mudança legislativa durante a pesquisa. Ver app/seeds/regras_iniciais.py
    para o formato de `parametros`.
    """

    __tablename__ = "regras_versao"
    __table_args__ = (UniqueConstraint("versao", name="uq_regras_versao"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    versao: Mapped[str] = mapped_column(String(40))       # "2026.08.1"
    descricao: Mapped[str | None] = mapped_column(Text)
    parametros: Mapped[dict] = mapped_column(JSONType)

    vigencia_inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    vigencia_fim: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)

    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    criada_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))

    def snapshot(self) -> dict:
        return {"id": self.id, "versao": self.versao, "parametros": self.parametros}
