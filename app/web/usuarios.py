"""
Gestão de usuários — tela só para admin. Ver todos os usuários cadastrados
(atravessa tenants, mesma regra usada no resto do app para o papel admin)
e editar nome, e-mail, papel, status e senha de qualquer um deles.

Usuário comum editar o próprio nome/e-mail/senha é coisa diferente — mora
em app/web/rotas.py, tela /perfil (autoatendimento, exige a senha atual
pra trocar a senha). Aqui é só a visão de administrador sobre os outros.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.auth.dependencias import eh_admin, usuario_web
from app.auth.seguranca import hash_senha
from app.db import get_db
from app.formatacao import email_valido
from app.models import PapelUsuario, Usuario
from app.web.rotas import templates

router = APIRouter(include_in_schema=False)


class ErroValidacao(Exception):
    pass


def _validar_e_aplicar(
    db: Session, alvo: Usuario, *, nome: str, email: str, papel_bruto: str,
    ativo: bool, nova_senha: str, confirmar_senha: str,
) -> None:
    nome = nome.strip()
    email = email.strip().lower()
    nova_senha = nova_senha.strip()
    confirmar_senha = confirmar_senha.strip()

    if not nome:
        raise ErroValidacao("Nome não pode ficar em branco.")
    if not email or not email_valido(email):
        raise ErroValidacao(f'E-mail inválido: "{email}".')

    outro_com_mesmo_email = db.scalar(
        select(Usuario).where(Usuario.email == email, Usuario.id != alvo.id)
    )
    if outro_com_mesmo_email:
        raise ErroValidacao(f'Já existe outro usuário com o e-mail "{email}".')

    try:
        papel = PapelUsuario(papel_bruto)
    except ValueError:
        raise ErroValidacao("Papel de acesso inválido.") from None

    # Trava de segurança: nunca deixar o sistema sem nenhum admin ativo —
    # sem isso, um clique errado (rebaixar ou desativar o único admin)
    # tranca todo mundo fora da administração, sem um jeito fácil de voltar.
    fica_admin_ativo = papel == PapelUsuario.ADMIN and ativo
    if not fica_admin_ativo:
        outros_admins_ativos = db.scalar(
            select(func.count(Usuario.id)).where(
                Usuario.papel == PapelUsuario.ADMIN,
                Usuario.ativo.is_(True),
                Usuario.id != alvo.id,
            )
        )
        if not outros_admins_ativos:
            raise ErroValidacao(
                "Precisa sobrar pelo menos um administrador ativo no sistema — "
                "promova ou ative outro admin antes de mudar este."
            )

    if nova_senha or confirmar_senha:
        if len(nova_senha) < 8:
            raise ErroValidacao("A nova senha precisa ter pelo menos 8 caracteres.")
        if nova_senha != confirmar_senha:
            raise ErroValidacao("A confirmação não bate com a nova senha.")

    alvo.nome = nome
    alvo.email = email
    alvo.papel = papel
    alvo.ativo = ativo
    if nova_senha:
        alvo.senha_hash = hash_senha(nova_senha)


@router.get("/usuarios", response_class=HTMLResponse)
def listar_usuarios(
    request: Request, db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_web),
) -> HTMLResponse:
    if not eh_admin(usuario):
        return RedirectResponse("/", status_code=303)

    usuarios = db.scalars(
        select(Usuario).options(selectinload(Usuario.tenant)).order_by(Usuario.nome)
    ).all()
    return templates.TemplateResponse("usuarios_lista.html", {
        "request": request, "usuario": usuario, "pagina_ativa": "usuarios", "usuarios": usuarios,
    })


@router.get("/usuarios/{usuario_id}/editar", response_class=HTMLResponse)
def form_editar_usuario(
    usuario_id: int, request: Request,
    db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_web),
) -> HTMLResponse:
    if not eh_admin(usuario):
        return RedirectResponse("/", status_code=303)

    alvo = db.get(Usuario, usuario_id, options=[selectinload(Usuario.tenant)])
    if alvo is None:
        return RedirectResponse("/usuarios", status_code=303)

    return templates.TemplateResponse("usuario_editar.html", {
        "request": request, "usuario": usuario, "pagina_ativa": "usuarios",
        "alvo": alvo, "papeis": list(PapelUsuario), "erro": None,
    })


@router.post("/usuarios/{usuario_id}/editar", response_class=HTMLResponse)
def editar_usuario(
    usuario_id: int, request: Request,
    nome: str = Form(...), email: str = Form(...), papel: str = Form(...),
    ativo: str = Form(""), nova_senha: str = Form(""), confirmar_senha: str = Form(""),
    db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_web),
) -> HTMLResponse:
    if not eh_admin(usuario):
        return RedirectResponse("/", status_code=303)

    alvo = db.get(Usuario, usuario_id, options=[selectinload(Usuario.tenant)])
    if alvo is None:
        return RedirectResponse("/usuarios", status_code=303)

    try:
        _validar_e_aplicar(
            db, alvo, nome=nome, email=email, papel_bruto=papel, ativo=(ativo == "1"),
            nova_senha=nova_senha, confirmar_senha=confirmar_senha,
        )
    except ErroValidacao as exc:
        return templates.TemplateResponse("usuario_editar.html", {
            "request": request, "usuario": usuario, "pagina_ativa": "usuarios",
            "alvo": alvo, "papeis": list(PapelUsuario), "erro": str(exc),
        })

    db.commit()
    return RedirectResponse("/usuarios?atualizado=1", status_code=303)
