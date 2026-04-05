"""
routers/pistas.py — Endpoints de asignación y gestión de pistas

Endpoints:
  POST   /torneos/{id}/generar-pistas   — Ejecutar algoritmo automático
  GET    /torneos/{id}/pistas           — Ver asignación actual
  PATCH  /torneos/{id}/pistas           — Guardar reordenación manual (drag & drop)
  PATCH  /torneos/{id}/publicar-pistas  — Publicar (visible para jugadores)
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from auth.jwt_auth import get_current_user
from database import get_session
from models.models import EstadoInscripcion, Inscripcion, Jugador, Torneo
from services.algoritmo_pistas import generar_asignacion, guardar_asignacion

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────

class AsignacionManual(BaseModel):
    """
    Estructura para guardar la reordenación manual del admin (drag & drop).
    El frontend envía el estado final de todas las pistas.

    Ejemplo:
    {
      "pistas": {
        "1": [3, 7, 12, 18],
        "2": [1, 5, 9, 22],
        ...
      }
    }
    """
    pistas: dict[int, list[int]]  # {pista_num: [jugador_id, ...]}


# ── Endpoints ─────────────────────────────────────────────────

@router.post("/torneos/{torneo_id}/generar-pistas")
async def generar_pistas(
    torneo_id: int,
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    """
    Ejecuta el algoritmo automático de asignación de pistas.

    Requisitos:
      - El torneo debe estar en estado 'cerrado' o 'abierto'
      - Debe haber exactamente 24 confirmados

    La asignación se guarda en BD pero NO se publica hasta que el admin
    la revise y llame a /publicar-pistas.
    """
    torneo = session.get(Torneo, torneo_id)
    if not torneo:
        raise HTTPException(status_code=404, detail="Torneo no encontrado")

    # Contar confirmados
    n_confirmados = session.exec(
        select(Inscripcion).where(
            Inscripcion.torneo_id == torneo_id,
            Inscripcion.estado == EstadoInscripcion.confirmado,
        )
    ).all()

    if len(n_confirmados) != 24:
        raise HTTPException(
            status_code=400,
            detail=f"Se necesitan exactamente 24 jugadores confirmados. Hay {len(n_confirmados)}.",
        )

    # Generar asignación
    try:
        pistas = generar_asignacion(torneo_id, session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Guardar en BD
    asignacion_ids = {
        pista_num: [j["jugador_id"] for j in grupo]
        for pista_num, grupo in pistas.items()
    }
    guardar_asignacion(torneo_id, asignacion_ids, session)

    return {
        "mensaje": "Pistas generadas correctamente. Revisa y ajusta antes de publicar.",
        "publicadas": False,
        "pistas": pistas,
    }


@router.get("/torneos/{torneo_id}/pistas")
async def ver_pistas(
    torneo_id: int,
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    """
    Devuelve la asignación de pistas actual del torneo.
    Incluye el nombre y nivel de cada jugador para mostrar en la UI.
    """
    torneo = session.get(Torneo, torneo_id)
    if not torneo:
        raise HTTPException(status_code=404, detail="Torneo no encontrado")

    inscritos = session.exec(
        select(Inscripcion, Jugador)
        .join(Jugador, Inscripcion.jugador_id == Jugador.id)
        .where(
            Inscripcion.torneo_id == torneo_id,
            Inscripcion.estado == EstadoInscripcion.confirmado,
            Inscripcion.pista_asignada.is_not(None),
        )
        .order_by(Inscripcion.pista_asignada)
    ).all()

    if not inscritos:
        return {"publicadas": torneo.pistas_publicadas, "pistas": {}}

    # Agrupar por pista
    pistas: dict[int, list[dict]] = {}
    for insc, jugador in inscritos:
        pista_num = insc.pista_asignada
        if pista_num not in pistas:
            pistas[pista_num] = []
        pistas[pista_num].append({
            "inscripcion_id": insc.id,
            "jugador_id": jugador.id,
            "nombre": jugador.nombre,
            "nivel": jugador.nivel,
            "acompanante_id": insc.acompanante_id,
        })

    return {
        "torneo_id": torneo_id,
        "publicadas": torneo.pistas_publicadas,
        "pistas": pistas,
    }


@router.patch("/torneos/{torneo_id}/pistas")
async def guardar_pistas_manual(
    torneo_id: int,
    datos: AsignacionManual,
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    """
    Guarda la reordenación manual del admin (resultado del drag & drop).

    El frontend envía el estado completo de todas las pistas tras el drag.
    El backend valida que sigan siendo 6 pistas × 4 jugadores y lo persiste.
    """
    torneo = session.get(Torneo, torneo_id)
    if not torneo:
        raise HTTPException(status_code=404, detail="Torneo no encontrado")

    try:
        guardar_asignacion(torneo_id, datos.pistas, session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"mensaje": "Asignación guardada correctamente.", "publicadas": torneo.pistas_publicadas}


@router.patch("/torneos/{torneo_id}/publicar-pistas")
async def publicar_pistas(
    torneo_id: int,
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    """
    Publica la asignación de pistas.
    Tras publicar, los jugadores con acceso pueden ver su pista asignada.
    """
    torneo = session.get(Torneo, torneo_id)
    if not torneo:
        raise HTTPException(status_code=404, detail="Torneo no encontrado")

    # Verificar que hay asignación guardada
    con_pista = session.exec(
        select(Inscripcion).where(
            Inscripcion.torneo_id == torneo_id,
            Inscripcion.estado == EstadoInscripcion.confirmado,
            Inscripcion.pista_asignada.is_not(None),
        )
    ).all()

    if len(con_pista) != 24:
        raise HTTPException(
            status_code=400,
            detail="Genera las pistas primero antes de publicar.",
        )

    torneo.pistas_publicadas = True
    session.add(torneo)
    session.commit()

    return {"mensaje": "¡Pistas publicadas! Los jugadores ya pueden ver su asignación."}
