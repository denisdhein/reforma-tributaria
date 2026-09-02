"""
Upload de foto de perfil — salva em disco local, nome de arquivo gerado
(nunca o nome original enviado, nunca escolhido pelo cliente) para não
colidir e não abrir brecha de path traversal. Sem redimensionamento ou
reprocessamento de imagem: escopo de protótipo acadêmico, não produto.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import UploadFile

DIRETORIO_UPLOADS = Path(__file__).parent / "static" / "uploads"
DIRETORIO_UPLOADS.mkdir(parents=True, exist_ok=True)

EXTENSOES_PERMITIDAS = {".jpg", ".jpeg", ".png", ".webp"}
TAMANHO_MAXIMO_BYTES = 2 * 1024 * 1024  # 2 MB


class UploadInvalido(Exception):
    pass


def salvar_foto(arquivo: UploadFile, prefixo: str) -> str:
    sufixo = Path(arquivo.filename or "").suffix.lower()
    if sufixo not in EXTENSOES_PERMITIDAS:
        raise UploadInvalido("Formato não aceito. Use JPG, PNG ou WEBP.")
    if not (arquivo.content_type or "").startswith("image/"):
        raise UploadInvalido("Arquivo não parece ser uma imagem.")

    conteudo = arquivo.file.read()
    if not conteudo:
        raise UploadInvalido("Arquivo vazio.")
    if len(conteudo) > TAMANHO_MAXIMO_BYTES:
        raise UploadInvalido("Imagem maior que 2 MB.")

    nome = f"{prefixo}_{uuid.uuid4().hex}{sufixo}"
    (DIRETORIO_UPLOADS / nome).write_bytes(conteudo)
    return nome


def remover_foto(nome: str | None) -> None:
    if not nome:
        return
    caminho = DIRETORIO_UPLOADS / nome
    if caminho.is_file():
        caminho.unlink()
