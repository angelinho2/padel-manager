"""
routers/inscripciones.py — Endpoints de inscripciones, cobros y extras

Endpoints:
  POST   /torneos/{id}/inscripciones     — Apuntar jugador (auto-espera si >24)
  GET    /torneos/{id}/inscripciones     — Ver confirmados + espera
  PATCH  /inscripciones/{id}/baja        — Dar de baja (promueve sustituto)
  PATCH  /inscripciones/{id}/pago        — Marcar pagado/no pagado (toggle)
  POST   /inscripciones/{id}/extras      — Añadir un extra (bebida, snack...)
  DELETE /extras/{id}                    — Eliminar un extra
  GET    /inscripciones/{id}/extras      — Ver extras de una inscripción
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select
from typing import Optional

from auth.jwt_auth import get_current_user
from database import get_session
from models.models import EstadoInscripcion, Extra, Inscripcion, Jugador, MetodoPago, Torneo
from services.lista_espera import dar_de_baja, inscribir_jugador
from services.ws_manager import ws_manager

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────

class InscripcionCreate(BaseModel):
    """Datos para apuntar a un jugador en un torneo."""
    jugador_id: int
    acompanante_id: Optional[int] = None  # Jugador con el que quiere empezar (opcional)


class ExtraCreate(BaseModel):
    """Un consumo adicional."""
    concepto: str   # "Bebida", "Snack", "Camiseta"...
    precio: float


# ── Endpoints de inscripción ───────────────────────────────────

@router.post("/torneos/{torneo_id}/inscripciones", status_code=201)
async def apuntar_jugador(
    torneo_id: int,
    datos: InscripcionCreate,
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    """
    Apunta a un jugador en el torneo.

    El sistema decide automáticamente si entra como:
      - confirmado (si hay menos de 24 confirmados)
      - espera     (si ya hay 24 confirmados)

    La respuesta incluye el estado asignado y, si está en espera, su posición.
    """
    # Verificaciones previas
    torneo = session.get(Torneo, torneo_id)
    if not torneo:
        raise HTTPException(status_code=404, detail="Torneo no encontrado")

    jugador = session.get(Jugador, datos.jugador_id)
    if not jugador:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")

    # Verificar que el jugador no esté ya inscrito en este torneo
    ya_inscrito = session.exec(
        select(Inscripcion).where(
            Inscripcion.torneo_id == torneo_id,
            Inscripcion.jugador_id == datos.jugador_id,
            Inscripcion.estado != EstadoInscripcion.baja,  # Las bajas sí pueden volver a apuntarse
        )
    ).first()
    if ya_inscrito:
        raise HTTPException(
            status_code=409,
            detail=f"El jugador ya está inscrito en este torneo (estado: {ya_inscrito.estado})",
        )

    inscripcion = await inscribir_jugador(
        torneo_id=torneo_id,
        jugador_id=datos.jugador_id,
        acompanante_id=datos.acompanante_id,
        session=session,
    )

    mensaje = (
        f"¡Confirmado! Jugador en pista (plaza {inscripcion.id})"
        if inscripcion.estado == EstadoInscripcion.confirmado
        else f"Jugador en lista de espera, posición {inscripcion.posicion_espera}"
    )

    return {
        "mensaje": mensaje,
        "inscripcion": inscripcion,
    }


@router.get("/torneos/{torneo_id}/inscripciones")
async def ver_inscripciones(
    torneo_id: int,
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    """
    Devuelve todos los inscritos de un torneo separados por estado.
    Útil para la pantalla de cobros y la vista de gestión del torneo.
    """
    torneo = session.get(Torneo, torneo_id)
    if not torneo:
        raise HTTPException(status_code=404, detail="Torneo no encontrado")

    inscritos = session.exec(
        select(Inscripcion, Jugador)
        .join(Jugador, Inscripcion.jugador_id == Jugador.id)
        .where(Inscripcion.torneo_id == torneo_id)
        .order_by(Inscripcion.posicion_espera, Inscripcion.created_at)
    ).all()

    confirmados = []
    espera = []
    bajas = []

    for inscripcion, jugador in inscritos:
        item = {"inscripcion": inscripcion, "jugador": jugador}
        if inscripcion.estado == EstadoInscripcion.confirmado:
            confirmados.append(item)
        elif inscripcion.estado == EstadoInscripcion.espera:
            espera.append(item)
        else:
            bajas.append(item)

    n_pagados = sum(1 for i, _ in inscritos
                    if i.pagado and i.estado == EstadoInscripcion.confirmado)

    return {
        "torneo_id": torneo_id,
        "resumen": {
            "confirmados": len(confirmados),
            "pagados": n_pagados,
            "en_espera": len(espera),
        },
        "confirmados": confirmados,
        "espera": espera,
        "bajas": bajas,
    }


# ── Endpoints de gestión de inscripción ───────────────────────

@router.patch("/inscripciones/{inscripcion_id}/baja")
async def dar_de_baja_jugador(
    inscripcion_id: int,
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    """
    Da de baja a un jugador confirmado.

    Automáticamente:
      1. Marca la inscripción como 'baja'
      2. Promueve al primero de la lista de espera (si hay alguno)
      3. Reordena la cola de espera

    La respuesta indica quién fue promovido (o null si la espera estaba vacía).
    """
    inscripcion = session.get(Inscripcion, inscripcion_id)
    if not inscripcion:
        raise HTTPException(status_code=404, detail="Inscripción no encontrada")

    if inscripcion.estado != EstadoInscripcion.confirmado:
        raise HTTPException(
            status_code=400,
            detail=f"Solo se pueden dar de baja jugadores confirmados (estado actual: {inscripcion.estado})",
        )

    sustituto = await dar_de_baja(inscripcion, session)

    if sustituto:
        jugador_sustituto = session.get(Jugador, sustituto.jugador_id)
        return {
            "mensaje": f"Jugador dado de baja. {jugador_sustituto.nombre} promovido desde espera.",
            "sustituto": {"inscripcion": sustituto, "jugador": jugador_sustituto},
        }
    else:
        return {
            "mensaje": "Jugador dado de baja. La lista de espera estaba vacía.",
            "sustituto": None,
        }


class PagoUpdate(BaseModel):
    """Body opcional para el endpoint de pago."""
    metodo: Optional[MetodoPago] = None   # tarjeta | efectivo | None (desmarcar)


@router.patch("/inscripciones/{inscripcion_id}/pago")
async def toggle_pago(
    inscripcion_id: int,
    datos: PagoUpdate = PagoUpdate(),
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    """
    Marca o desmarca el pago de un jugador.

    Si se envía metodo=tarjeta o metodo=efectivo → marca como pagado con ese método.
    Si ya estaba pagado con el mismo método → desmarca (toggle).
    """
    inscripcion = session.get(Inscripcion, inscripcion_id)
    if not inscripcion:
        raise HTTPException(status_code=404, detail="Inscripción no encontrada")

    # Toggle: si ya estaba pagado con el mismo método → desmarcar
    if inscripcion.pagado and inscripcion.metodo_pago == datos.metodo:
        inscripcion.pagado = False
        inscripcion.fecha_pago = None
        inscripcion.metodo_pago = None
    else:
        inscripcion.pagado = True
        inscripcion.fecha_pago = datetime.utcnow()
        inscripcion.metodo_pago = datos.metodo

    session.add(inscripcion)
    session.commit()
    session.refresh(inscripcion)

    # Notificar a todos los clientes WS del torneo
    from routers.cobros import _build_cobros_snapshot
    snapshot = _build_cobros_snapshot(inscripcion.torneo_id, session)
    import asyncio
    asyncio.create_task(ws_manager.broadcast(inscripcion.torneo_id, snapshot))

    return inscripcion


# ── Endpoints de extras ───────────────────────────────────────

@router.get("/inscripciones/{inscripcion_id}/extras", response_model=list[Extra])
async def ver_extras(
    inscripcion_id: int,
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    """Lista todos los extras de una inscripción con el total."""
    inscripcion = session.get(Inscripcion, inscripcion_id)
    if not inscripcion:
        raise HTTPException(status_code=404, detail="Inscripción no encontrada")

    extras = session.exec(
        select(Extra).where(Extra.inscripcion_id == inscripcion_id)
    ).all()

    return extras


@router.post("/inscripciones/{inscripcion_id}/extras", status_code=201, response_model=Extra)
async def anadir_extra(
    inscripcion_id: int,
    datos: ExtraCreate,
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    """
    Añade un extra (bebida, snack, etc.) a la inscripción de un jugador.

    Ejemplo: POST /inscripciones/7/extras
    Body: {"concepto": "Bebida", "precio": 1.5}
    """
    inscripcion = session.get(Inscripcion, inscripcion_id)
    if not inscripcion:
        raise HTTPException(status_code=404, detail="Inscripción no encontrada")

    extra = Extra(inscripcion_id=inscripcion_id, **datos.model_dump())
    session.add(extra)
    session.commit()
    session.refresh(extra)

    # Notificar a todos los clientes WS del torneo
    from routers.cobros import _build_cobros_snapshot
    snapshot = _build_cobros_snapshot(inscripcion.torneo_id, session)
    import asyncio
    asyncio.create_task(ws_manager.broadcast(inscripcion.torneo_id, snapshot))

    return extra


@router.delete("/extras/{extra_id}", status_code=204)
async def eliminar_extra(
    extra_id: int,
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    """Elimina un extra. Status 204 = éxito sin cuerpo de respuesta."""
    extra = session.get(Extra, extra_id)
    if not extra:
        raise HTTPException(status_code=404, detail="Extra no encontrado")

    torneo_id = session.get(Inscripcion, extra.inscripcion_id).torneo_id
    session.delete(extra)
    session.commit()

    # Notificar a todos los clientes WS del torneo
    from routers.cobros import _build_cobros_snapshot
    snapshot = _build_cobros_snapshot(torneo_id, session)
    import asyncio
    asyncio.create_task(ws_manager.broadcast(torneo_id, snapshot))
