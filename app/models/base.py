"""
Base declarativa, enums e tipos portáveis.

Convenções:
- Valores monetários: Numeric(18, 2)
- Percentuais e alíquotas: Numeric(9, 6), guardados como fração (0.088 = 8,8%)
- Nunca float. Erro de arredondamento em cálculo tributário é indefensável.
"""

from __future__ import annotations

import enum

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase

# JSONB no Postgres, JSON em qualquer outro dialeto (testes locais em SQLite).
JSONType = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


class TipoTenant(str, enum.Enum):
    ESCRITORIO = "escritorio"
    EMPRESA = "empresa"


class PapelUsuario(str, enum.Enum):
    ADMIN = "admin"          # superusuário, atravessa tenants
    GESTOR = "gestor"        # administra o próprio tenant
    OPERADOR = "operador"    # cria e consulta simulações


class RegimeTributario(str, enum.Enum):
    SIMPLES = "simples"
    PRESUMIDO = "presumido"
    REAL = "real"


class OpcaoSimplesIBSCBS(str, enum.Enum):
    """Art. 41, §3º da LC 214/2025."""

    UNICO = "unico"          # IBS/CBS dentro do DAS
    HIBRIDO = "hibrido"      # IBS/CBS apurados pelo regime regular


class TipoCenario(str, enum.Enum):
    OFICIAL = "oficial"
    TRAVA_LEGAL = "trava_legal"
    USUARIO = "usuario"


class OrigemCusto(str, enum.Enum):
    MERCADORIAS = "mercadorias"
    INSUMOS = "insumos"
    SERVICOS_TOMADOS = "servicos_tomados"
    ENERGIA = "energia"
    FRETE = "frete"
    ALUGUEL = "aluguel"
    FOLHA = "folha"
    OUTROS = "outros"


class StatusVerificacao(str, enum.Enum):
    APROVADA = "aprovada"
    REPROVADA = "reprovada"
    NAO_EXECUTADA = "nao_executada"
