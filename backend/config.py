"""
config.py — Configuración global de la aplicación

Pydantic-Settings lee las variables de entorno o del archivo .env
automáticamente. Si una variable no está definida, usa el valor por defecto.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Base de datos ──────────────────────────────────────────────
    DATABASE_URL: str = "sqlite:////app/data/padel.db"

    # ── JWT (autenticación) ────────────────────────────────────────
    SECRET_KEY: str = "cambia-esto-por-una-clave-segura"
    ALGORITHM: str = "HS256"
    # El token dura 7 días (cómodo para uso en móvil)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7

    # ── Credenciales del admin ─────────────────────────────────────
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "changeme"

    # ── Desarrollo ─────────────────────────────────────────────────
    DEBUG: bool = False  # Si True, imprime todas las queries SQL en los logs

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Instancia global — se importa en el resto de módulos con:
#   from config import settings
settings = Settings()
