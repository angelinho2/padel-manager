"""
lista_espera.py — Lógica de negocio para inscripciones y lista de espera

Este módulo contiene las dos operaciones más críticas del sistema:
  1. inscribir_jugador: apunta a un jugador, decidiendo si entra como
     confirmado (si hay plaza) o en espera (si ya hay 24 confirmados).
  2. dar_de_baja: da de baja a un confirmado y promueve automáticamente
     al primero de la lista de espera.

Por qué en services/ y no en el router:
  La lógica de negocio vive aquí separada de la capa HTTP (routers/).
  Así es más fácil de testear y de reutilizar.
"""
from typing import Optional

from sqlmodel import Session, select, func

from models.models import Inscripcion, EstadoInscripcion

# Constante: número máximo de confirmados por torneo
MAX_CONFIRMADOS = 24


async def inscribir_jugador(
    torneo_id: int,
    jugador_id: int,
    acompanante_id: Optional[int],
    session: Session,
) -> Inscripcion:
    """
    Inscribe a un jugador en un torneo.

    Lógica:
      - Si hay menos de 24 confirmados → estado = confirmado
      - Si ya hay 24 confirmados → estado = espera, con posición al final de la cola

    Retorna la Inscripcion creada (con su estado y posición asignados).
    """
    # Contamos cuántos confirmados tiene ya este torneo
    # func.count() es la función SQL COUNT()
    n_confirmados = session.exec(
        select(func.count(Inscripcion.id)).where(
            Inscripcion.torneo_id == torneo_id,
            Inscripcion.estado == EstadoInscripcion.confirmado,
        )
    ).one()

    if n_confirmados < MAX_CONFIRMADOS:
        # ✅ Hay plaza libre
        estado = EstadoInscripcion.confirmado
        posicion_espera = None
    else:
        # 🔴 Sin plaza, va a espera
        estado = EstadoInscripcion.espera

        # Busca la posición más alta actual en la cola de espera
        # para poner al nuevo al final
        max_posicion = session.exec(
            select(func.max(Inscripcion.posicion_espera)).where(
                Inscripcion.torneo_id == torneo_id,
                Inscripcion.estado == EstadoInscripcion.espera,
            )
        ).one()

        # Si no hay nadie en espera todavía, empieza en posición 1
        posicion_espera = (max_posicion or 0) + 1

    inscripcion = Inscripcion(
        torneo_id=torneo_id,
        jugador_id=jugador_id,
        estado=estado,
        posicion_espera=posicion_espera,
        acompanante_id=acompanante_id,
    )
    session.add(inscripcion)
    session.commit()
    session.refresh(inscripcion)
    return inscripcion


async def dar_de_baja(
    inscripcion: Inscripcion,
    session: Session,
) -> Optional[Inscripcion]:
    """
    Da de baja a un jugador confirmado.

    Efecto en cascada automático:
      1. Marca la inscripción como 'baja'
      2. Busca el primero de la lista de espera (posicion_espera = 1)
      3. Lo promueve a 'confirmado'
      4. Reordena el resto de la cola (todos suben una posición)

    Retorna el sustituto promovido (o None si la lista de espera estaba vacía).
    """
    # ── Paso 1: Marcar como baja ──────────────────────────────────
    inscripcion.estado = EstadoInscripcion.baja
    session.add(inscripcion)

    # ── Paso 2: Buscar el primero en espera ───────────────────────
    primero = session.exec(
        select(Inscripcion)
        .where(
            Inscripcion.torneo_id == inscripcion.torneo_id,
            Inscripcion.estado == EstadoInscripcion.espera,
        )
        .order_by(Inscripcion.posicion_espera)  # El de posición más baja es el primero
    ).first()

    if primero:
        # ── Paso 3: Promover al sustituto ─────────────────────────
        primero.estado = EstadoInscripcion.confirmado
        primero.posicion_espera = None
        session.add(primero)

        # ── Paso 4: Reordenar el resto de la cola ─────────────────
        # Todos los que quedan en espera suben una posición
        restantes = session.exec(
            select(Inscripcion)
            .where(
                Inscripcion.torneo_id == inscripcion.torneo_id,
                Inscripcion.estado == EstadoInscripcion.espera,
            )
            .order_by(Inscripcion.posicion_espera)
        ).all()

        for nueva_posicion, insc in enumerate(restantes, start=1):
            insc.posicion_espera = nueva_posicion
            session.add(insc)

    # Guardamos todo de una vez (más eficiente que varios commits)
    session.commit()

    if primero:
        session.refresh(primero)

    return primero
