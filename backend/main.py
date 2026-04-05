"""
main.py — Punto de entrada de la aplicación FastAPI

Este es el archivo que arranca el servidor. Define:
  - El ciclo de vida de la app (crear tablas al arrancar)
  - Los middlewares (CORS para que el frontend pueda llamar al backend)
  - El registro de todos los routers (grupos de endpoints)
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel

from database import engine
from routers import inscripciones, jugadores, torneos, pistas, cobros
from auth.jwt_auth import router as auth_router

# Importar los modelos para que SQLModel los registre antes de crear las tablas
# (aunque no los usemos explícitamente aquí, el import es necesario)
from models.models import (  # noqa: F401
    Jugador, Torneo, Inscripcion, Extra, Partido, SolicitudCambioPista
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Código que se ejecuta al arrancar y al apagar el servidor.
    
    Al arrancar: crea las tablas en la BD si no existen.
    En producción con migraciones (Alembic), este create_all se puede quitar.
    """
    # ── Arranque ──────────────────────────────────────────────
    print("🎾 Padel Manager arrancando...")
    SQLModel.metadata.create_all(engine)
    print("✅ Base de datos lista")
    yield
    # ── Apagado ───────────────────────────────────────────────
    print("👋 Padel Manager apagándose")


app = FastAPI(
    title="Padel Manager API",
    description=(
        "API para gestión de maratón de pádel semanal.\n\n"
        "**Autenticación**: Usa el endpoint `/auth/login` para obtener un JWT, "
        "luego haz clic en el botón 🔒 Authorize en la esquina superior derecha "
        "e introduce el token."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# ── CORS ──────────────────────────────────────────────────────
# CORS (Cross-Origin Resource Sharing) permite que el frontend
# (corriendo en un puerto o dominio diferente) pueda llamar al backend.
# En producción, limita allow_origins a tu dominio real en lugar de "*".
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],           # TODO: cambiar a ["https://tudominio.com"] en producción
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routers ───────────────────────────────────────────────────
# Cada router agrupa los endpoints de una entidad.
# El prefix define la URL base de ese grupo.

app.include_router(auth_router, prefix="/auth", tags=["🔐 autenticación"])
app.include_router(jugadores.router, prefix="/jugadores", tags=["👤 jugadores"])
app.include_router(torneos.router, prefix="/torneos", tags=["🏆 torneos"])
app.include_router(inscripciones.router, tags=["📋 inscripciones"])
app.include_router(pistas.router, tags=["🎾 pistas"])
app.include_router(cobros.router, tags=["💰 cobros"])


# ── Endpoint raíz ─────────────────────────────────────────────
@app.get("/", tags=["info"])
async def root():
    """Página de bienvenida. Útil para verificar que el servidor está vivo."""
    return {
        "app": "Padel Manager API",
        "version": "1.0.0",
        "documentacion": "/docs",       # Swagger UI interactivo
        "documentacion_alt": "/redoc",  # ReDoc (alternativa más legible)
        "estado": "funcionando 🎾",
    }
