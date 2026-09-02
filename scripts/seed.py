"""
Popula o banco com parâmetros iniciais e perfis sintéticos de empresa.

Uso:  python -m scripts.seed
Idempotente: rodar de novo não duplica.
"""

from __future__ import annotations

import os
import secrets
import sys
from decimal import Decimal

from sqlalchemy import select

from app.auth.seguranca import hash_senha
from app.db import SessionLocal
from app.models import (
    CenarioAliquota, CustoEmpresa, Empresa, ItemEmpresa, OpcaoSimplesIBSCBS,
    OrigemCusto, PapelUsuario, RegimeTributario, RegrasVersao, Tenant,
    TipoCenario, TipoTenant, Usuario,
)
from app.seeds.regras_iniciais import CENARIOS_INICIAIS, VERSAO_INICIAL

D = Decimal


def seed_regras(db) -> RegrasVersao:
    existente = db.scalar(
        select(RegrasVersao).where(RegrasVersao.versao == VERSAO_INICIAL["versao"])
    )
    if existente:
        return existente
    rv = RegrasVersao(**VERSAO_INICIAL, ativa=True)
    db.add(rv)
    db.flush()
    return rv


def seed_cenarios(db) -> list[CenarioAliquota]:
    criados = []
    for c in CENARIOS_INICIAIS:
        if db.scalar(select(CenarioAliquota).where(CenarioAliquota.nome == c["nome"])):
            continue
        cen = CenarioAliquota(
            nome=c["nome"],
            aliquota_ibs=D(str(c["aliquota_ibs"])),
            aliquota_cbs=D(str(c["aliquota_cbs"])),
            fonte=c["fonte"],
            base_legal=c["base_legal"],
            data_publicacao=c["data_publicacao"],
            tipo=TipoCenario(c["tipo"]),
            ativo=True,
        )
        db.add(cen)
        criados.append(cen)
    db.flush()
    return criados


def seed_tenant(db, nome: str, tipo: TipoTenant) -> Tenant:
    t = db.scalar(select(Tenant).where(Tenant.nome == nome))
    if t:
        return t
    t = Tenant(nome=nome, tipo=tipo, ativo=True)
    db.add(t)
    db.flush()
    return t


def seed_usuario(db, tenant: Tenant, email: str, nome: str, papel: PapelUsuario, senha: str) -> tuple[Usuario, bool]:
    """Devolve (usuario, criado_agora). Idempotente: usuário existente não é tocado."""
    u = db.scalar(select(Usuario).where(Usuario.email == email))
    if u:
        return u, False
    u = Usuario(
        tenant_id=tenant.id, email=email, senha_hash=hash_senha(senha),
        nome=nome, papel=papel, ativo=True,
    )
    db.add(u)
    db.flush()
    return u, True


def seed_admin(db) -> Tenant:
    """
    Conta do administrador (Denis) — acesso irrestrito, atravessa tenants.
    E-mail e senha vêm de env var quando definidos; senão, usa um e-mail
    padrão e GERA uma senha aleatória, impressa uma única vez neste seed.
    """
    tenant = seed_tenant(db, "Administração", TipoTenant.ESCRITORIO)
    email = os.environ.get("ADMIN_EMAIL", "denisdhein@gmail.com").strip().lower()
    senha = os.environ.get("ADMIN_SENHA") or secrets.token_urlsafe(9)
    usuario, criado = seed_usuario(db, tenant, email, "Denis Dhein", PapelUsuario.ADMIN, senha)
    if criado and not os.environ.get("ADMIN_SENHA"):
        print(f"admin senha  : {senha}  <- gerada agora, anote — não é recuperável depois")
    return tenant


CAMPOS_DECIMAIS = {
    "faturamento_anual", "rbt12",
    "pct_interno", "pct_interestadual", "pct_exportacao", "pct_consumidor_final",
    "margem_bruta", "margem_liquida",
    "aliq_icms", "aliq_iss", "aliq_pis", "aliq_cofins", "aliq_ipi",
    "pct_compras_com_credito",
}

# Perfis sintéticos. Dados fictícios, para desenvolvimento e demonstração.
# tenant_chave amarra cada empresa ao tenant certo em seed_empresas: as duas
# primeiras são clientes de um mesmo escritório contábil (um tenant, duas
# empresas — o caso "contador"); a terceira é uma empresa direta, dona da
# própria conta (um tenant, uma empresa — o caso "empresa"). Existir os dois
# casos no seed é o que deixa o isolamento por tenant demonstrável no login.
PERFIS = [
    {
        "tenant_chave": "escritorio",
        "razao_social": "Distribuidora Oeste Ltda (fictícia)",
        "uf": "SC", "municipio": "Chapecó", "ramo": "Comércio atacadista",
        "regime": RegimeTributario.SIMPLES, "simples_anexo": 1,
        "simples_opcao_ibs_cbs": OpcaoSimplesIBSCBS.UNICO,
        "faturamento_anual": "3200000.00",
        "pct_interno": "0.70", "pct_interestadual": "0.30",
        "pct_consumidor_final": "0.05",
        "margem_bruta": "0.22", "margem_liquida": "0.07",
        "custos": [
            (OrigemCusto.MERCADORIAS, "2100000.00", "0.35", True),
            (OrigemCusto.FRETE, "160000.00", "0.50", False),
            (OrigemCusto.FOLHA, "290000.00", "0.00", False),
        ],
        "itens": [("Alimentos secos", "0.60"), ("Bebidas", "0.40")],
    },
    {
        "tenant_chave": "escritorio",
        "razao_social": "Metalúrgica Serra Alta S.A. (fictícia)",
        "uf": "SC", "municipio": "Chapecó", "ramo": "Indústria metalúrgica",
        "regime": RegimeTributario.REAL, "faturamento_anual": "28000000.00",
        "pct_interno": "0.45", "pct_interestadual": "0.40", "pct_exportacao": "0.15",
        "margem_bruta": "0.31", "margem_liquida": "0.11",
        "aliq_icms": "0.170", "aliq_pis": "0.0165", "aliq_cofins": "0.076",
        "aliq_ipi": "0.05", "pct_compras_com_credito": "0.72",
        "custos": [
            (OrigemCusto.INSUMOS, "14500000.00", "0.08", True),
            (OrigemCusto.ENERGIA, "1900000.00", "0.00", True),
            (OrigemCusto.SERVICOS_TOMADOS, "2400000.00", "0.30", False),
            (OrigemCusto.FOLHA, "4100000.00", "0.00", False),
        ],
        "itens": [("Perfis laminados", "0.55"), ("Peças usinadas", "0.45")],
    },
    {
        "tenant_chave": "empresa_direta",
        "razao_social": "Consultoria Aurora ME (fictícia)",
        "uf": "SC", "municipio": "Chapecó", "ramo": "Serviços profissionais",
        "regime": RegimeTributario.PRESUMIDO, "faturamento_anual": "1450000.00",
        "pct_interno": "0.90", "pct_consumidor_final": "0.15",
        "margem_bruta": "0.55", "margem_liquida": "0.19",
        "aliq_iss": "0.05", "aliq_pis": "0.0065", "aliq_cofins": "0.03",
        "pct_compras_com_credito": "0.10",
        "custos": [
            (OrigemCusto.SERVICOS_TOMADOS, "380000.00", "0.60", False),
            (OrigemCusto.ALUGUEL, "96000.00", "0.20", False),
            (OrigemCusto.FOLHA, "520000.00", "0.00", False),
        ],
        "itens": [("Consultoria tributária", "1.00")],
    },
]


def seed_empresas(db, tenants: dict[str, Tenant]) -> int:
    n = 0
    for p in PERFIS:
        if db.scalar(select(Empresa).where(Empresa.razao_social == p["razao_social"])):
            continue
        tenant = tenants[p.pop("tenant_chave")]
        custos = p.pop("custos", [])
        itens = p.pop("itens", [])
        # Explícito de propósito: os enums herdam de str, então detectar
        # "o que é decimal" por isinstance converteria enum em Decimal.
        campos = {
            k: (D(v) if k in CAMPOS_DECIMAIS else v)
            for k, v in p.items()
        }
        emp = Empresa(tenant_id=tenant.id, **campos)
        db.add(emp)
        db.flush()
        for origem, valor, pct_simples, credito in custos:
            db.add(CustoEmpresa(
                tenant_id=tenant.id, empresa_id=emp.id, origem=origem,
                valor_anual=D(valor), pct_fornecedor_simples=D(pct_simples),
                gera_credito_hoje=credito,
            ))
        for descricao, pct in itens:
            db.add(ItemEmpresa(
                tenant_id=tenant.id, empresa_id=emp.id,
                descricao=descricao, pct_faturamento=D(pct),
                regime_diferenciado="padrao",
            ))
        n += 1
    db.flush()
    return n


# Senha fixa de demonstração — os dois tenants abaixo só têm empresas
# fictícias, não há nada a proteger. Facilita testar isolamento por tenant
# sem precisar caçar senha gerada em log.
SENHA_DEMO = "demo12345"


def main() -> int:
    with SessionLocal() as db:
        rv = seed_regras(db)
        cenarios = seed_cenarios(db)

        tenant_admin = seed_admin(db)
        tenant_escritorio = seed_tenant(db, "Escritório Demonstração", TipoTenant.ESCRITORIO)
        tenant_empresa = seed_tenant(db, "Consultoria Aurora ME", TipoTenant.EMPRESA)

        n_emp = seed_empresas(db, {
            "escritorio": tenant_escritorio,
            "empresa_direta": tenant_empresa,
        })

        _, contador_criado = seed_usuario(
            db, tenant_escritorio, "contador@escritoriodemo.local", "Contador Demonstração",
            PapelUsuario.GESTOR, SENHA_DEMO,
        )
        _, empresa_criado = seed_usuario(
            db, tenant_empresa, "financeiro@consultoriaaurora.local", "Financeiro Consultoria Aurora",
            PapelUsuario.GESTOR, SENHA_DEMO,
        )
        db.commit()

        print(f"regras       : {rv.versao} (id={rv.id})")
        print(f"cenarios     : +{len(cenarios)} novos")
        print(f"tenant admin : {tenant_admin.nome} (id={tenant_admin.id})")
        print(f"tenant demo  : {tenant_escritorio.nome} (id={tenant_escritorio.id}), "
              f"{tenant_empresa.nome} (id={tenant_empresa.id})")
        print(f"empresas     : +{n_emp} novas")
        if contador_criado or empresa_criado:
            print(f"login demo   : contador@escritoriodemo.local / "
                  f"financeiro@consultoriaaurora.local — senha \"{SENHA_DEMO}\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
