"""
routers/torneos.py — Endpoints para gestión de torneos

Endpoints:
  GET    /torneos                — Listar todos los torneos
  POST   /torneos                — Crear un nuevo torneo
  GET    /torneos/{id}           — Detalle del torneo con resumen de inscripciones
  PATCH  /torneos/{id}/estado    — Cambiar el estado del torneo
  DELETE /torneos/{id}           — Eliminar torneo (y todas sus inscripciones)
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select, func

from auth.jwt_auth import get_current_user
from database import get_session
from models.models import EstadoInscripcion, EstadoTorneo, Extra, Inscripcion, Jugador, Torneo

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────

class TorneoCreate(BaseModel):
    """Datos para crear un torneo."""
    fecha: date                    # Formato: "2025-04-05"
    precio_base: float = 10.0


class TorneoEstadoUpdate(BaseModel):
    """Para cambiar el estado del torneo."""
    estado: EstadoTorneo


# ── Endpoints ─────────────────────────────────────────────────

@router.get("/", response_model=list[Torneo])
async def listar_torneos(
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    """Lista todos los torneos ordenados por fecha descendente (más reciente primero)."""
    return session.exec(select(Torneo).order_by(Torneo.fecha.desc())).all()


@router.post("/", response_model=Torneo, status_code=201)
async def crear_torneo(
    datos: TorneoCreate,
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    """Crea un nuevo torneo con fecha de sábado. El estado inicial es 'abierto'."""
    torneo = Torneo(**datos.model_dump())
    session.add(torneo)
    session.commit()
    session.refresh(torneo)
    return torneo


@router.get("/{torneo_id}")
async def obtener_torneo(
    torneo_id: int,
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    """
    Detalle completo de un torneo.

    Incluye:
      - Datos del torneo
      - Número de confirmados y pagados
      - Lista completa: confirmados, espera y bajas (con datos del jugador)
    """
    torneo = session.get(Torneo, torneo_id)
    if not torneo:
        raise HTTPException(status_code=404, detail="Torneo no encontrado")

    # JOIN en un solo query para evitar N+1
    inscritos = session.exec(
        select(Inscripcion, Jugador)
        .join(Jugador, Inscripcion.jugador_id == Jugador.id)
        .where(Inscripcion.torneo_id == torneo_id)
        .order_by(Inscripcion.estado, Inscripcion.posicion_espera, Inscripcion.created_at)
    ).all()

    # Separamos en listas según el estado
    confirmados = []
    espera = []
    bajas = []

    for inscripcion, jugador in inscritos:
        item = {
            "inscripcion_id": inscripcion.id,
            "jugador": jugador,
            "pista_asignada": inscripcion.pista_asignada,
            "posicion_espera": inscripcion.posicion_espera,
            "pagado": inscripcion.pagado,
            "fecha_pago": inscripcion.fecha_pago,
            "acompanante_id": inscripcion.acompanante_id,
        }
        if inscripcion.estado == EstadoInscripcion.confirmado:
            confirmados.append(item)
        elif inscripcion.estado == EstadoInscripcion.espera:
            espera.append(item)
        else:
            bajas.append(item)

    n_pagados = sum(1 for i, _ in inscritos
                    if i.pagado and i.estado == EstadoInscripcion.confirmado)

    return {
        "torneo": torneo,
        "resumen": {
            "confirmados": len(confirmados),
            "en_espera": len(espera),
            "pagados": n_pagados,
            "pendientes_pago": len(confirmados) - n_pagados,
        },
        "confirmados": confirmados,
        "espera": espera,
        "bajas": bajas,
    }


@router.patch("/{torneo_id}/estado", response_model=Torneo)
async def cambiar_estado_torneo(
    torneo_id: int,
    datos: TorneoEstadoUpdate,
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    """
    Cambia el estado del torneo.

    Flujo esperado: abierto → cerrado → en_curso → finalizado

    No se valida el orden de transición para darte flexibilidad,
    pero el flujo recomendado está en el análisis de requisitos.
    """
    torneo = session.get(Torneo, torneo_id)
    if not torneo:
        raise HTTPException(status_code=404, detail="Torneo no encontrado")

    torneo.estado = datos.estado
    session.add(torneo)
    session.commit()
    session.refresh(torneo)
    return torneo


@router.delete("/{torneo_id}", status_code=204)
async def eliminar_torneo(
    torneo_id: int,
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    """
    Elimina un torneo y en cascada todas sus inscripciones y extras.
    Operación irreversible — el frontend pide confirmación antes de llamar.
    """
    torneo = session.get(Torneo, torneo_id)
    if not torneo:
        raise HTTPException(status_code=404, detail="Torneo no encontrado")

    # Borrar extras → inscripciones → torneo (orden por FKs)
    inscripciones = session.exec(
        select(Inscripcion).where(Inscripcion.torneo_id == torneo_id)
    ).all()
    for insc in inscripciones:
        extras = session.exec(
            select(Extra).where(Extra.inscripcion_id == insc.id)
        ).all()
        for extra in extras:
            session.delete(extra)
        session.delete(insc)

    session.delete(torneo)
    session.commit()
    # 204 No Content — no devuelve cuerpo
