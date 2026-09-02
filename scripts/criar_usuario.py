"""
Provisiona uma conta (usuário + tenant, se necessário). Uso do admin — não
há cadastro público na aplicação.

Criar um tenant novo (empresa direta ou escritório) com seu primeiro usuário:

    python -m scripts.criar_usuario --email joao@escritorio.com --nome "João" \
        --tenant-nome "Escritório João Contábil" --tenant-tipo escritorio

Criar mais um usuário num tenant já existente (ex.: outro operador no mesmo
escritório):

    python -m scripts.criar_usuario --email maria@escritorio.com --nome "Maria" \
        --tenant-id 2 --papel operador

Sem --senha, uma senha é gerada e impressa uma única vez — anote-a, ela não
fica recuperável depois (só o hash é gravado).
"""

from __future__ import annotations

import argparse
import secrets
import sys

from sqlalchemy import select

from app.auth.seguranca import hash_senha
from app.db import SessionLocal
from app.models import PapelUsuario, Tenant, TipoTenant, Usuario


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--email", required=True)
    ap.add_argument("--nome", required=True)
    ap.add_argument("--senha", help="Se omitido, uma senha aleatória é gerada e impressa.")
    ap.add_argument(
        "--papel", choices=[p.value for p in PapelUsuario], default=PapelUsuario.GESTOR.value,
    )
    ap.add_argument("--tenant-id", type=int, help="Tenant existente para receber o usuário.")
    ap.add_argument("--tenant-nome", help="Cria um tenant novo com este nome.")
    ap.add_argument(
        "--tenant-tipo", choices=[t.value for t in TipoTenant],
        help="Tipo do tenant novo (obrigatório com --tenant-nome).",
    )
    args = ap.parse_args()

    if not args.tenant_id and not args.tenant_nome:
        ap.error("informe --tenant-id (tenant existente) ou --tenant-nome (+ --tenant-tipo, cria um novo).")
    if args.tenant_nome and not args.tenant_tipo:
        ap.error("--tenant-nome exige --tenant-tipo (escritorio | empresa).")

    email = args.email.strip().lower()
    senha = args.senha or secrets.token_urlsafe(9)

    with SessionLocal() as db:
        if db.scalar(select(Usuario).where(Usuario.email == email)):
            print(f"Já existe usuário com o e-mail {email}.", file=sys.stderr)
            return 1

        if args.tenant_id:
            tenant = db.get(Tenant, args.tenant_id)
            if tenant is None:
                print(f"Tenant {args.tenant_id} não encontrado.", file=sys.stderr)
                return 1
        else:
            tenant = Tenant(nome=args.tenant_nome, tipo=TipoTenant(args.tenant_tipo), ativo=True)
            db.add(tenant)
            db.flush()

        usuario = Usuario(
            tenant_id=tenant.id,
            email=email,
            senha_hash=hash_senha(senha),
            nome=args.nome,
            papel=PapelUsuario(args.papel),
            ativo=True,
        )
        db.add(usuario)
        db.commit()

        print(f"tenant  : {tenant.nome} (id={tenant.id}, tipo={tenant.tipo.value})")
        print(f"usuario : {usuario.nome} <{usuario.email}> (id={usuario.id}, papel={usuario.papel.value})")
        if not args.senha:
            print(f"senha   : {senha}  <- anote agora, não é recuperável depois")
    return 0


if __name__ == "__main__":
    sys.exit(main())
