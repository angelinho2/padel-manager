"""
routers/jugadores.py — Endpoints CRUD para gestión de jugadores

Endpoints:
  GET    /jugadores               — Listar jugadores (filtros: activo, buscar por nombre)
  POST   /jugadores               — Crear nuevo jugador
  GET    /jugadores/{id}          — Detalle de un jugador
  PATCH  /jugadores/{id}          — Editar jugador (parcial)
  DELETE /jugadores/{id}          — Marcar jugador como inactivo (soft delete)
  GET    /jugadores/{id}/historial — Historial completo del jugador

Todos los endpoints requieren autenticación JWT (get_current_user).
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from auth.jwt_auth import get_current_user
from database import get_session
from models.models import Inscripcion, Jugador, Torneo

router = APIRouter()


# ── Schemas de request (lo que recibe el endpoint) ────────────
# Usamos Pydantic BaseModel (no SQLModel) para los datos de entrada,
# así separamos la validación HTTP del modelo de base de datos.

class JugadorCreate(BaseModel):
    """Datos necesarios para crear un jugador."""
    nombre: str
    nivel: int = Field(ge=1, le=6, description="Nivel del jugador: 1=mejor, 6=peor")
    telefono: Optional[str] = None


class JugadorUpdate(BaseModel):
    """
    Datos para actualizar un jugador. Todos son opcionales:
    solo se actualizan los campos que se envíen.
    """
    nombre: Optional[str] = None
    nivel: Optional[int] = Field(default=None, ge=1, le=6)
    telefono: Optional[str] = None
    activo: Optional[bool] = None


# ── Endpoints ─────────────────────────────────────────────────

@router.get("/", response_model=list[Jugador])
async def listar_jugadores(
    activo: Optional[bool] = Query(default=None, description="Filtrar por activo/inactivo"),
    buscar: Optional[str] = Query(default=None, description="Buscar por nombre (parcial)"),
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),  # _ porque no usamos el valor, solo verificamos
):
    """
    Lista todos los jugadores con filtros opcionales.

    Ejemplos:
      GET /jugadores?activo=true          → solo activos
      GET /jugadores?buscar=garcia        → jugadores con "garcia" en el nombre
      GET /jugadores?activo=true&buscar=p → combinado
    """
    query = select(Jugador)

    if activo is not None:
        query = query.where(Jugador.activo == activo)

    if buscar:
        # contains() genera un LIKE '%buscar%' en SQL (insensible a mayúsculas en SQLite)
        query = query.where(Jugador.nombre.contains(buscar))

    return session.exec(query.order_by(Jugador.nombre)).all()


@router.post("/", response_model=Jugador, status_code=201)
async def crear_jugador(
    datos: JugadorCreate,
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    """Crea un nuevo jugador en la base de datos."""
    jugador = Jugador(**datos.model_dump())
    session.add(jugador)
    session.commit()
    session.refresh(jugador)  # Recarga desde BD para obtener el id asignado
    return jugador


@router.get("/{jugador_id}", response_model=Jugador)
async def obtener_jugador(
    jugador_id: int,
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    """Obtiene los datos de un jugador por su ID."""
    jugador = session.get(Jugador, jugador_id)
    if not jugador:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")
    return jugador


@router.patch("/{jugador_id}", response_model=Jugador)
async def actualizar_jugador(
    jugador_id: int,
    datos: JugadorUpdate,
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    """
    Actualiza parcialmente un jugador.
    Solo se modifican los campos incluidos en la petición.

    Ejemplo — solo subir el nivel:
      PATCH /jugadores/5  →  {"nivel": 3}
    """
    jugador = session.get(Jugador, jugador_id)
    if not jugador:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")

    # model_dump(exclude_unset=True) devuelve solo los campos enviados en la petición
    datos_dict = datos.model_dump(exclude_unset=True)
    for campo, valor in datos_dict.items():
        setattr(jugador, campo, valor)

    session.add(jugador)
    session.commit()
    session.refresh(jugador)
    return jugador


@router.delete("/{jugador_id}", status_code=204)
async def eliminar_jugador(
    jugador_id: int,
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    """
    Marca al jugador como inactivo (soft delete).
    No se borran sus datos para preservar el historial de inscripciones.
    """
    jugador = session.get(Jugador, jugador_id)
    if not jugador:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")

    jugador.activo = False
    session.add(jugador)
    session.commit()


@router.get("/{jugador_id}/historial")
async def historial_jugador(
    jugador_id: int,
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    """
    Devuelve el historial completo de un jugador:
    todos los torneos en los que ha participado, con su estado de pago y pista.
    """
    jugador = session.get(Jugador, jugador_id)
    if not jugador:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")

    # JOIN entre Inscripcion y Torneo para obtener los datos del torneo
    # en el mismo query, sin N+1 queries
    inscripciones = session.exec(
        select(Inscripcion, Torneo)
        .join(Torneo, Inscripcion.torneo_id == Torneo.id)
        .where(Inscripcion.jugador_id == jugador_id)
        .order_by(Torneo.fecha.desc())  # Más reciente primero
    ).all()

    return {
        "jugador": jugador,
        "total_participaciones": len([i for i, _ in inscripciones if i.estado == "confirmado"]),
        "historial": [
            {
                "torneo": torneo,
                "estado": inscripcion.estado,
                "pista_asignada": inscripcion.pista_asignada,
                "pagado": inscripcion.pagado,
                "fecha_pago": inscripcion.fecha_pago,
            }
            for inscripcion, torneo in inscripciones
        ],
    }
