"""
Dependências de autenticação para rotas FastAPI.

Duas variantes porque a falha se comporta diferente conforme o consumidor:
tela HTML redireciona para /login; rota JSON devolve 401. O núcleo —
ler cookie, decodificar token, carregar usuário — é o mesmo.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.auth.seguranca import NOME_COOKIE, usuario_id_do_token
from app.db import get_db
from app.models import PapelUsuario, Usuario


class NaoAutenticado(Exception):
    """Sinaliza para o handler em app.main redirecionar para /login."""


def _carregar_usuario(request: Request, db: Session) -> Usuario | None:
    token = request.cookies.get(NOME_COOKIE)
    if not token:
        return None
    usuario_id = usuario_id_do_token(token)
    if usuario_id is None:
        return None
    usuario = db.get(Usuario, usuario_id)
    if usuario is None or not usuario.ativo:
        return None
    return usuario


def usuario_web(request: Request, db: Session = Depends(get_db)) -> Usuario:
    usuario = _carregar_usuario(request, db)
    if usuario is None:
        raise NaoAutenticado()
    return usuario


def usuario_api(request: Request, db: Session = Depends(get_db)) -> Usuario:
    usuario = _carregar_usuario(request, db)
    if usuario is None:
        raise HTTPException(status_code=401, detail="Não autenticado.")
    return usuario


def eh_admin(usuario: Usuario) -> bool:
    return usuario.papel == PapelUsuario.ADMIN
