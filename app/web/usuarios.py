"""
Gestão de usuários — tela só para admin. Ver todos os usuários cadastrados
(atravessa tenants, mesma regra usada no resto do app para o papel admin),
cadastrar um novo, editar nome/e-mail/papel/status/senha de qualquer um, e
excluir.

Usuário comum editar o próprio nome/e-mail/senha é coisa diferente — mora
em app/web/rotas.py, tela /perfil (autoatendimento, exige a senha atual
pra trocar a senha). Aqui é só a visão de administrador sobre os outros.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, selectinload

from app.auth.dependencias import eh_admin, usuario_web
from app.auth.seguranca import hash_senha
from app.db import get_db
from app.formatacao import email_valido, texto_validado
from app.models import LogAuditoria, PapelUsuario, RegrasVersao, Simulacao, Tenant, TipoTenant, Usuario
from app.web.rotas import templates
from app.web.uploads import remover_foto

router = APIRouter(include_in_schema=False)


class ErroValidacao(Exception):
    pass


def _garante_admin_sobrando(db: Session, *, excluindo_id: int, fica_admin_ativo: bool) -> None:
    """Levanta ErroValidacao se a mudança (editar pra outro papel/inativo,
    ou excluir) deixaria o sistema sem nenhum admin ativo. Compartilhada
    entre editar e excluir — mesma trava, dois lugares que podem causar o
    mesmo problema."""
    if fica_admin_ativo:
        return
    outros_admins_ativos = db.scalar(
        select(func.count(Usuario.id)).where(
            Usuario.papel == PapelUsuario.ADMIN,
            Usuario.ativo.is_(True),
            Usuario.id != excluindo_id,
        )
    )
    if not outros_admins_ativos:
        raise ErroValidacao(
            "Precisa sobrar pelo menos um administrador ativo no sistema — "
            "promova ou ative outro admin antes de mudar este."
        )


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
    if len(nome) > 200:
        raise ErroValidacao(f"Nome tem {len(nome)} caracteres — o máximo é 200.")
    if not email or not email_valido(email):
        raise ErroValidacao(f'E-mail inválido: "{email}".')
    if len(email) > 255:
        raise ErroValidacao(f"E-mail tem {len(email)} caracteres — o máximo é 255.")

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
    _garante_admin_sobrando(
        db, excluindo_id=alvo.id, fica_admin_ativo=(papel == PapelUsuario.ADMIN and ativo),
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


def _criar_usuario(
    db: Session, *, nome: str, email: str, papel_bruto: str, senha: str, confirmar_senha: str,
    tenant_modo: str, tenant_id_bruto: str, tenant_nome: str, tenant_tipo_bruto: str,
) -> Usuario:
    nome = texto_validado(nome, "Nome", 200)
    email = email.strip().lower()
    if not nome:
        raise ErroValidacao("Nome não pode ficar em branco.")
    if not email or not email_valido(email):
        raise ErroValidacao(f'E-mail inválido: "{email}".')
    if len(email) > 255:
        raise ErroValidacao(f"E-mail tem {len(email)} caracteres — o máximo é 255.")
    if db.scalar(select(Usuario).where(Usuario.email == email)):
        raise ErroValidacao(f'Já existe um usuário com o e-mail "{email}".')

    try:
        papel = PapelUsuario(papel_bruto)
    except ValueError:
        raise ErroValidacao("Papel de acesso inválido.") from None

    senha = senha.strip()
    if len(senha) < 8:
        raise ErroValidacao("A senha precisa ter pelo menos 8 caracteres.")
    if senha != confirmar_senha.strip():
        raise ErroValidacao("A confirmação não bate com a senha.")

    if tenant_modo == "existente":
        tenant_id = int(tenant_id_bruto) if tenant_id_bruto.strip().isdigit() else None
        tenant = db.get(Tenant, tenant_id) if tenant_id else None
        if tenant is None:
            raise ErroValidacao("Selecione um escritório/empresa existente.")
    else:
        tenant_nome_val = texto_validado(tenant_nome, "Nome do escritório/empresa", 200)
        if not tenant_nome_val:
            raise ErroValidacao("Nome do novo escritório/empresa não pode ficar em branco.")
        try:
            tenant_tipo = TipoTenant(tenant_tipo_bruto)
        except ValueError:
            raise ErroValidacao("Tipo de conta inválido.") from None
        tenant = Tenant(nome=tenant_nome_val, tipo=tenant_tipo, ativo=True)
        db.add(tenant)
        db.flush()  # gera tenant.id sem precisar de um commit à parte

    return Usuario(
        tenant_id=tenant.id, email=email, senha_hash=hash_senha(senha), nome=nome,
        papel=papel, ativo=True,
    )


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


@router.get("/usuarios/novo", response_class=HTMLResponse)
def form_novo_usuario(
    request: Request, db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_web),
) -> HTMLResponse:
    if not eh_admin(usuario):
        return RedirectResponse("/", status_code=303)

    tenants = db.scalars(select(Tenant).order_by(Tenant.nome)).all()
    return templates.TemplateResponse("usuario_novo.html", {
        "request": request, "usuario": usuario, "pagina_ativa": "usuarios",
        "papeis": list(PapelUsuario), "tenants": tenants, "tipos_tenant": list(TipoTenant),
        "erro": None, "valores": {},
    })


@router.post("/usuarios/novo", response_class=HTMLResponse)
def criar_usuario_web(
    request: Request,
    nome: str = Form(...), email: str = Form(...), papel: str = Form(...),
    senha: str = Form(...), confirmar_senha: str = Form(...),
    tenant_modo: str = Form("existente"), tenant_id: str = Form(""),
    tenant_nome: str = Form(""), tenant_tipo: str = Form(""),
    db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_web),
) -> HTMLResponse:
    if not eh_admin(usuario):
        return RedirectResponse("/", status_code=303)

    valores = dict(nome=nome, email=email, papel=papel, tenant_modo=tenant_modo,
                    tenant_id=tenant_id, tenant_nome=tenant_nome, tenant_tipo=tenant_tipo)
    try:
        novo = _criar_usuario(
            db, nome=nome, email=email, papel_bruto=papel, senha=senha,
            confirmar_senha=confirmar_senha, tenant_modo=tenant_modo,
            tenant_id_bruto=tenant_id, tenant_nome=tenant_nome, tenant_tipo_bruto=tenant_tipo,
        )
    except ErroValidacao as exc:
        tenants = db.scalars(select(Tenant).order_by(Tenant.nome)).all()
        return templates.TemplateResponse("usuario_novo.html", {
            "request": request, "usuario": usuario, "pagina_ativa": "usuarios",
            "papeis": list(PapelUsuario), "tenants": tenants, "tipos_tenant": list(TipoTenant),
            "erro": str(exc), "valores": valores,
        })

    db.add(novo)
    db.commit()
    return RedirectResponse("/usuarios?criado=1", status_code=303)


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


@router.post("/usuarios/{usuario_id}/excluir")
def excluir_usuario(
    usuario_id: int, db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_web),
) -> RedirectResponse:
    """
    Exclui a conta. Nunca a própria (deslogaria no meio da própria ação, e
    não há necessidade real de suportar isso) e nunca o último admin ativo
    — mesma trava de _garante_admin_sobrando usada em editar.

    Simulacao.criada_por_id, RegrasVersao.criada_por_id e
    LogAuditoria.usuario_id são FKs opcionais (só rastreabilidade, não
    dado que precisa sobreviver ligado a ESTE usuário) — zeradas antes de
    excluir. Sem isso, excluir um usuário que já criou alguma simulação
    ou versão de regras violaria a FK no Postgres, a mesma classe de bug
    já corrigida em excluir empresa e excluir histórico.
    """
    if not eh_admin(usuario) or usuario_id == usuario.id:
        return RedirectResponse("/usuarios", status_code=303)

    alvo = db.get(Usuario, usuario_id)
    if alvo is None:
        return RedirectResponse("/usuarios", status_code=303)

    try:
        _garante_admin_sobrando(db, excluindo_id=alvo.id, fica_admin_ativo=False)
    except ErroValidacao:
        return RedirectResponse("/usuarios?erro=admin", status_code=303)

    db.execute(update(Simulacao).where(Simulacao.criada_por_id == alvo.id).values(criada_por_id=None))
    db.execute(
        update(RegrasVersao).where(RegrasVersao.criada_por_id == alvo.id)
        .values(criada_por_id=None)
    )
    db.execute(update(LogAuditoria).where(LogAuditoria.usuario_id == alvo.id).values(usuario_id=None))

    if alvo.foto_nome:
        remover_foto(alvo.foto_nome)

    db.delete(alvo)
    db.commit()
    return RedirectResponse("/usuarios?excluido=1", status_code=303)
