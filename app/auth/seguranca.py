"""
Hash de senha e token de sessão.

Argon2 para senha (argon2-cffi já era dependência do projeto). JWT assinado
em cookie HttpOnly para sessão — sem tabela de sessão, sem Redis; o próprio
token carrega usuario_id e expiração. `python-jose` também já era
dependência. Nada disso adiciona peça nova ao projeto.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from jose import JWTError, jwt

from app.config import settings

_hasher = PasswordHasher()

ALGORITMO = "HS256"
NOME_COOKIE = "sessao"
EXPIRA_HORAS = 12


def hash_senha(senha: str) -> str:
    return _hasher.hash(senha)


def verificar_senha(senha: str, hash_: str) -> bool:
    try:
        return _hasher.verify(hash_, senha)
    except VerifyMismatchError:
        return False
    except Exception:
        # Hash inválido/corrompido não deve derrubar o login — só nega.
        return False


def criar_token(usuario_id: int) -> str:
    expira = datetime.now(timezone.utc) + timedelta(hours=EXPIRA_HORAS)
    payload = {"sub": str(usuario_id), "exp": expira}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITMO)


def usuario_id_do_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITMO])
    except JWTError:
        return None
    sub = payload.get("sub")
    return int(sub) if sub is not None else None
