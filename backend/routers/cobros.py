"""
routers/cobros.py — Pantalla de cobros en tiempo real

Endpoints:
  GET  /torneos/{id}/cobros   — Estado completo de cobros (REST inicial)
  WS   /ws/torneos/{id}       — WebSocket: actualizaciones en tiempo real

Flujo:
  1. El cliente carga la pantalla → GET /torneos/{id}/cobros (snapshot inicial)
  2. El cliente abre WS /ws/torneos/{id} → queda escuchando
  3. Cualquier acción (PATCH /inscripciones/{id}/pago, extras) llama
     ws_manager.broadcast() → todos los clientes del torneo se actualizan

El mensaje WS es siempre el estado COMPLETO del torneo para que el cliente
no necesite hacer merge de deltas (más simple y menos bugs).
"""
import json
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlmodel import Session, select

from auth.jwt_auth import get_current_user, verify_token_ws
from database import get_session, engine
from models.models import EstadoInscripcion, Extra, Inscripcion, Jugador, Torneo
from services.ws_manager import ws_manager
from sqlmodel import Session as SQLSession

router = APIRouter()


# ── Helper: construir el snapshot de cobros ────────────────────

def _build_cobros_snapshot(torneo_id: int, session: Session) -> dict:
    """
    Construye el estado completo de cobros para un torneo.
    Se usa tanto en el endpoint REST como en el broadcast WS.
    """
    torneo = session.get(Torneo, torneo_id)
    if not torneo:
        return {"error": "Torneo no encontrado"}

    # Todos los confirmados con sus jugadores
    filas = session.exec(
        select(Inscripcion, Jugador)
        .join(Jugador, Inscripcion.jugador_id == Jugador.id)
        .where(
            Inscripcion.torneo_id == torneo_id,
            Inscripcion.estado == EstadoInscripcion.confirmado,
        )
        .order_by(Inscripcion.pista_asignada, Jugador.nombre)
    ).all()

    jugadores = []
    total_recaudado = 0.0
    total_esperado  = 0.0

    for insc, jug in filas:
        # Extras de este jugador
        extras = session.exec(
            select(Extra).where(Extra.inscripcion_id == insc.id)
        ).all()

        total_extras = sum(e.precio for e in extras)
        precio_final = torneo.precio_base + total_extras
        total_esperado += precio_final
        if insc.pagado:
            total_recaudado += precio_final

        jugadores.append({
            "inscripcion_id": insc.id,
            "jugador_id":     jug.id,
            "nombre":         jug.nombre,
            "nivel":          jug.nivel,
            "telefono":       jug.telefono,
            "pista_asignada": insc.pista_asignada,
            "pagado":         insc.pagado,
            "metodo_pago":    insc.metodo_pago,
            "fecha_pago":     insc.fecha_pago.isoformat() if insc.fecha_pago else None,
            "precio_base":    torneo.precio_base,
            "total_extras":   total_extras,
            "precio_total":   precio_final,
            "extras": [
                {"id": e.id, "concepto": e.concepto, "precio": e.precio}
                for e in extras
            ],
        })

    n_pagados = sum(1 for j in jugadores if j["pagado"])
    recaudado_tarjeta  = sum(j["precio_total"] for j in jugadores if j["pagado"] and j["metodo_pago"] == "tarjeta")
    recaudado_efectivo = sum(j["precio_total"] for j in jugadores if j["pagado"] and j["metodo_pago"] == "efectivo")

    return {
        "tipo":                "snapshot",
        "torneo_id":           torneo_id,
        "precio_base":         torneo.precio_base,
        "n_confirmados":       len(jugadores),
        "n_pagados":           n_pagados,
        "n_pendientes":        len(jugadores) - n_pagados,
        "total_recaudado":     round(total_recaudado, 2),
        "total_esperado":      round(total_esperado, 2),
        "recaudado_tarjeta":   round(recaudado_tarjeta, 2),
        "recaudado_efectivo":  round(recaudado_efectivo, 2),
        "jugadores":           jugadores,
    }


# ── REST: snapshot inicial ─────────────────────────────────────

@router.get("/torneos/{torneo_id}/cobros")
async def get_cobros(
    torneo_id: int,
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    """
    Devuelve el estado completo de cobros del torneo.
    El cliente lo usa para poblar la UI nada más entrar.
    """
    torneo = session.get(Torneo, torneo_id)
    if not torneo:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Torneo no encontrado")

    return _build_cobros_snapshot(torneo_id, session)


# ── WebSocket: actualizaciones en tiempo real ──────────────────

@router.websocket("/ws/torneos/{torneo_id}")
async def cobros_ws(
    torneo_id: int,
    websocket: WebSocket,
    token: str = "",          # el frontend envía ?token=xxx
):
    """
    WebSocket de cobros para un torneo.

    El cliente:
      1. Se conecta: ws://host/ws/torneos/{id}?token=<jwt>
      2. Recibe inmediatamente el snapshot completo
      3. Permanece escuchando — cada vez que alguien marca un pago
         o añade un extra, recibe el snapshot actualizado
      4. Puede enviar "ping" para verificar la conexión

    La autenticación se hace vía query param ?token=<jwt>
    (los WebSockets del navegador no soportan cabeceras Authorization).
    """
    # Verificar token JWT
    if not token or not verify_token_ws(token):
        await websocket.close(code=4001, reason="No autorizado")
        return

    await ws_manager.connect(torneo_id, websocket)

    try:
        # Enviar snapshot inicial
        with SQLSession(engine) as session:
            snapshot = _build_cobros_snapshot(torneo_id, session)
        await websocket.send_text(json.dumps(snapshot, default=str))

        # Mantener la conexión viva
        while True:
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text('{"tipo":"pong"}')

    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect(torneo_id, websocket)
