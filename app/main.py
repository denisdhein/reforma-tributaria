from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.rotas import router as api_router
from app.auth.dependencias import NaoAutenticado
from app.web.cenarios import router as cenarios_router
from app.web.empresas import router as empresas_router
from app.web.historico import router as historico_router
from app.web.rotas import router as web_router
from app.web.usuarios import router as usuarios_router

app = FastAPI(
    title="Sistema de apoio à decisão · Reforma Tributária",
    description=(
        "Simulação de impacto da Reforma Tributária do Consumo "
        "(EC 132/2023, LC 214/2025, LC 227/2026). "
        "A IA explica; o motor determinístico calcula."
    ),
    version="0.1.0",
)


@app.exception_handler(NaoAutenticado)
def _redirecionar_para_login(request: Request, exc: NaoAutenticado) -> RedirectResponse:
    return RedirectResponse("/login", status_code=303)


app.include_router(web_router)
app.include_router(empresas_router)
app.include_router(cenarios_router)
app.include_router(historico_router)
app.include_router(usuarios_router)
app.include_router(api_router)

# Foto de perfil: nome de arquivo gerado (UUID), não há dado sensível
# exposto por servir sem autenticação — ver app/web/uploads.py.
app.mount(
    "/static", StaticFiles(directory=str(Path(__file__).parent / "web" / "static")), name="static",
)
