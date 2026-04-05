"""
services/algoritmo_pistas.py — Algoritmo de asignación de pistas

Lógica:
  1. Ordenar los 24 confirmados por nivel (1=mejor, 6=peor)
  2. Dividir en 6 grupos de 4: top 4 → pista 1, ..., bottom 4 → pista 6
  3. Ajuste por acompañantes: si dos jugadores quieren empezar juntos
     pero caen en pistas distintas, se hace un intercambio mínimo
     con el jugador adyacente de menor diferencia de nivel.

El resultado es un dict {pista: [jugador_id, ...]} que el admin puede
revisar y ajustar manualmente antes de publicar.
"""
from typing import Optional
from sqlmodel import Session, select

from models.models import Inscripcion, Jugador, EstadoInscripcion

MAX_CONFIRMADOS = 24
PISTAS = 6
JUGADORES_POR_PISTA = MAX_CONFIRMADOS // PISTAS  # = 4


def generar_asignacion(
    torneo_id: int,
    session: Session,
) -> dict[int, list[dict]]:
    """
    Genera la asignación inicial de pistas para un torneo.

    Devuelve un dict con la estructura:
    {
      1: [{"jugador_id": X, "nombre": "...", "nivel": N}, ...],
      2: [...],
      ...
      6: [...]
    }
    """
    # Obtener los 24 confirmados con sus datos de jugador en un solo query
    filas = session.exec(
        select(Inscripcion, Jugador)
        .join(Jugador, Inscripcion.jugador_id == Jugador.id)
        .where(
            Inscripcion.torneo_id == torneo_id,
            Inscripcion.estado == EstadoInscripcion.confirmado,
        )
    ).all()

    if len(filas) != MAX_CONFIRMADOS:
        raise ValueError(
            f"El torneo tiene {len(filas)} confirmados, se necesitan exactamente {MAX_CONFIRMADOS}"
        )

    # Construir lista de jugadores con sus datos relevantes
    jugadores = [
        {
            "inscripcion_id": insc.id,
            "jugador_id": jugador.id,
            "nombre": jugador.nombre,
            "nivel": jugador.nivel,
            "acompanante_id": insc.acompanante_id,
        }
        for insc, jugador in filas
    ]

    # ── Paso 1: ordenar por nivel (1=mejor va primero) ────────────
    jugadores.sort(key=lambda j: j["nivel"])

    # ── Paso 2: asignación inicial en grupos de 4 ─────────────────
    pistas: dict[int, list[dict]] = {}
    for pista_num in range(1, PISTAS + 1):
        start = (pista_num - 1) * JUGADORES_POR_PISTA
        end = pista_num * JUGADORES_POR_PISTA
        for j in jugadores[start:end]:
            j["pista_asignada"] = pista_num
        pistas[pista_num] = jugadores[start:end]

    # ── Paso 3: ajuste por acompañantes ───────────────────────────
    # Mapa: jugador_id → pista asignada
    asignacion_map = {j["jugador_id"]: j["pista_asignada"] for p in pistas.values() for j in p}

    for pista_num, grupo in pistas.items():
        for jugador in grupo:
            acomp_id = jugador.get("acompanante_id")
            if not acomp_id:
                continue

            # Buscar si el acompañante está en una pista diferente
            pista_acomp = asignacion_map.get(acomp_id)
            if pista_acomp is None or pista_acomp == pista_num:
                continue  # Mismo grupo, no hay que hacer nada

            # Encontrar el jugador acompañante
            acomp = next(
                (j for j in pistas[pista_acomp] if j["jugador_id"] == acomp_id),
                None,
            )
            if not acomp:
                continue

            # Buscar el mejor candidato para intercambiar en el grupo del jugador
            # (el que tenga menor diferencia de nivel con el acompañante)
            candidatos = [j for j in grupo if j["jugador_id"] != jugador["jugador_id"]]
            if not candidatos:
                continue

            mejor_candidato = min(
                candidatos,
                key=lambda c: abs(c["nivel"] - acomp["nivel"]),
            )

            # Intercambio: el candidato va a la pista del acompañante,
            # el acompañante viene a esta pista
            pistas[pista_num].remove(mejor_candidato)
            pistas[pista_num].append(acomp)
            pistas[pista_acomp].remove(acomp)
            pistas[pista_acomp].append(mejor_candidato)

            # Actualizar mapa
            mejor_candidato["pista_asignada"] = pista_acomp
            acomp["pista_asignada"] = pista_num
            asignacion_map[mejor_candidato["jugador_id"]] = pista_acomp
            asignacion_map[acomp["jugador_id"]] = pista_num

            # Un jugador solo se procesa una vez por acompañante
            break

    return pistas


def guardar_asignacion(
    torneo_id: int,
    asignacion: dict[int, list[int]],  # {pista: [jugador_id, ...]}
    session: Session,
) -> None:
    """
    Persiste en la BD la asignación de pistas (generada o ajustada manualmente).

    asignacion: {1: [id1, id2, id3, id4], 2: [...], ...}
    """
    # Validación básica
    todos_ids = [jid for ids in asignacion.values() for jid in ids]
    if len(todos_ids) != MAX_CONFIRMADOS:
        raise ValueError(f"La asignación debe tener {MAX_CONFIRMADOS} jugadores en total")

    for pista_num, jugador_ids in asignacion.items():
        if len(jugador_ids) != JUGADORES_POR_PISTA:
            raise ValueError(f"La pista {pista_num} debe tener exactamente {JUGADORES_POR_PISTA} jugadores")

    # Actualizar pista_asignada en cada inscripción
    for pista_num, jugador_ids in asignacion.items():
        for jugador_id in jugador_ids:
            inscripcion = session.exec(
                select(Inscripcion).where(
                    Inscripcion.torneo_id == torneo_id,
                    Inscripcion.jugador_id == jugador_id,
                    Inscripcion.estado == EstadoInscripcion.confirmado,
                )
            ).first()
            if inscripcion:
                inscripcion.pista_asignada = pista_num
                session.add(inscripcion)

    session.commit()
