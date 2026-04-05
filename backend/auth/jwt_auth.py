"""
jwt_auth.py — Sistema de autenticación JWT

¿Cómo funciona?
  1. El admin hace POST /auth/login con su usuario y contraseña
  2. El servidor verifica las credenciales y devuelve un JWT (token)
  3. El frontend guarda ese token y lo incluye en cada petición:
       Authorization: Bearer <token>
  4. Cada endpoint protegido llama a get_current_user() que verifica el token

El JWT contiene:
  - sub: el username del admin
  - exp: fecha de expiración (7 días por defecto)
  - Está firmado con SECRET_KEY, por eso no se puede falsificar
"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel

from config import settings

router = APIRouter()

# OAuth2PasswordBearer le dice a FastAPI dónde buscar el token.
# tokenUrl es la URL del endpoint de login (para que Swagger lo muestre bien).
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ── Schemas de respuesta ──────────────────────────────────────

class Token(BaseModel):
    """Lo que devuelve el endpoint /auth/login."""
    access_token: str
    token_type: str  # Siempre "bearer"


class TokenData(BaseModel):
    """Datos que extraemos del JWT decodificado."""
    username: Optional[str] = None


# ── Funciones de utilidad ─────────────────────────────────────

def verify_password(plain_password: str) -> bool:
    """
    Compara la contraseña recibida con la del .env.
    Por simplicidad, comparación directa (sin hash).
    En producción con múltiples usuarios usaríamos bcrypt.
    """
    return plain_password == settings.ADMIN_PASSWORD


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Crea un JWT firmado con SECRET_KEY.

    data: dict con los datos a incluir (normalmente {"sub": username})
    expires_delta: tiempo de vida del token (por defecto 7 días)
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    # jwt.encode firma el payload con la clave secreta y devuelve el token como string
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


# ── Dependency de FastAPI ────────────────────────────────────

async def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    """
    Dependency que verifica el JWT en cada petición protegida.

    FastAPI la llama automáticamente cuando un endpoint declara:
        _: str = Depends(get_current_user)

    Si el token es inválido o ha expirado, devuelve 401 Unauthorized.
    Si es válido, devuelve el username del admin.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido o expirado. Vuelve a iniciar sesión.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # Decodifica y verifica la firma del token
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # Comprobación extra: solo el admin configurado en .env puede acceder
    if username != settings.ADMIN_USERNAME:
        raise credentials_exception

    return username


def verify_token_ws(token: str) -> bool:
    """
    Verifica un token JWT para conexiones WebSocket.

    Los WebSockets del navegador NO soportan cabeceras Authorization,
    así que el token llega como query param (?token=xxx).
    Devuelve True si es válido, False si no.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        return username == settings.ADMIN_USERNAME
    except JWTError:
        return False


# ── Endpoints ────────────────────────────────────────────────

@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Endpoint de login.

    Recibe usuario y contraseña (como form data, estándar OAuth2).
    Devuelve un JWT válido por 7 días.

    En el frontend, el token se guarda en localStorage y se incluye
    en cada petición al backend.
    """
    if form_data.username != settings.ADMIN_USERNAME:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuario o contraseña incorrectos",
        )
    if not verify_password(form_data.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuario o contraseña incorrectos",
        )

    access_token = create_access_token(data={"sub": form_data.username})
    return Token(access_token=access_token, token_type="bearer")


@router.get("/me")
async def get_me(current_user: str = Depends(get_current_user)):
    """Devuelve el usuario actual. Útil para que el frontend verifique si el token sigue válido."""
    return {"username": current_user}
