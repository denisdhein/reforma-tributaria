from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, PapelUsuario, TipoTenant


class Tenant(Base):
    __tablename__ = "tenant"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(200))
    tipo: Mapped[TipoTenant] = mapped_column(Enum(TipoTenant, native_enum=False, length=20))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    usuarios: Mapped[list["Usuario"]] = relationship(back_populates="tenant")
    empresas: Mapped[list["Empresa"]] = relationship(back_populates="tenant")  # noqa: F821


class Usuario(Base):
    __tablename__ = "usuario"
    __table_args__ = (UniqueConstraint("email", name="uq_usuario_email"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant.id"), index=True)

    email: Mapped[str] = mapped_column(String(255))
    senha_hash: Mapped[str] = mapped_column(String(255))
    nome: Mapped[str] = mapped_column(String(200))
    papel: Mapped[PapelUsuario] = mapped_column(Enum(PapelUsuario, native_enum=False, length=20))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    # Nome do arquivo em app/web/static/uploads/ — nunca o path completo,
    # nunca o nome original enviado (evita path traversal e colisão).
    foto_nome: Mapped[str | None] = mapped_column(String(255))
    ultimo_acesso: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tenant: Mapped[Tenant] = relationship(back_populates="usuarios")
