"""
models.py — Modelos de la base de datos

SQLModel combina Pydantic (validación) y SQLAlchemy (ORM).
Cada clase con table=True genera una tabla en la BD.

Jerarquía de entidades:
  Jugador ──< Inscripcion >── Torneo
  Inscripcion ──< Extra
  Jugador ──< SolicitudCambioPista >── Torneo
  Torneo ──< Partido
"""
from datetime import datetime, date
from enum import Enum
from typing import Optional

from sqlmodel import SQLModel, Field


# ═══════════════════════════════════════════════════════════════
# Enumeraciones — definen los valores válidos para campos de estado
# ═══════════════════════════════════════════════════════════════

class EstadoTorneo(str, Enum):
    """Ciclo de vida de un torneo semanal."""
    abierto = "abierto"       # Aceptando inscripciones
    cerrado = "cerrado"       # Inscripciones cerradas, pendiente de generar pistas
    en_curso = "en_curso"     # Torneo en juego (el sábado)
    finalizado = "finalizado" # Torneo terminado


class EstadoInscripcion(str, Enum):
    """Estado de un jugador en un torneo concreto."""
    confirmado = "confirmado" # Tiene plaza garantizada (máx. 24)
    espera = "espera"         # En lista de espera, con posición numerada
    baja = "baja"             # Se dio de baja o fue eliminado


class EstadoSolicitud(str, Enum):
    """Estado de una solicitud de cambio de pista enviada por un jugador."""
    pendiente = "pendiente"
    aceptada = "aceptada"
    rechazada = "rechazada"


class MetodoPago(str, Enum):
    """Cómo pagó el jugador."""
    tarjeta = "tarjeta"
    efectivo = "efectivo"


# ═══════════════════════════════════════════════════════════════
# Tabla: jugador
# ═══════════════════════════════════════════════════════════════

class Jugador(SQLModel, table=True):
    """
    Representa a un jugador de la maratón.
    El campo 'nivel' (1–6) indica en qué pista suele jugar:
      1 = mejor nivel (pista 1), 6 = nivel más bajo (pista 6)
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str = Field(index=True)           # Índice para búsquedas rápidas
    nivel: int = Field(ge=1, le=6)            # ge=greater_or_equal, le=less_or_equal
    telefono: Optional[str] = Field(default=None)
    activo: bool = Field(default=True)        # False = ya no participa en la maratón
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ═══════════════════════════════════════════════════════════════
# Tabla: torneo
# ═══════════════════════════════════════════════════════════════

class Torneo(SQLModel, table=True):
    """
    Representa un torneo semanal (un sábado específico).
    precio_base es lo que paga cada jugador por participar.
    pistas_publicadas indica si la asignación de pistas ya es visible para los jugadores.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    fecha: date                               # Fecha del sábado
    estado: EstadoTorneo = Field(default=EstadoTorneo.abierto)
    precio_base: float = Field(default=10.0)
    pistas_publicadas: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ═══════════════════════════════════════════════════════════════
# Tabla: inscripcion
# ═══════════════════════════════════════════════════════════════

class Inscripcion(SQLModel, table=True):
    """
    Une a un jugador con un torneo.
    Contiene toda la info de ese jugador para ESE torneo específico:
    estado, pago, pista asignada, extras consumidos.

    Nota sobre acompanante_id:
      Si dos jugadores quieren empezar en la misma pista, uno indica
      al otro como acompañante. El algoritmo de generación lo respeta.
      Se guarda como entero sin FK a nivel ORM para evitar ambigüedad
      (SQLModel no maneja bien dos FK a la misma tabla sin Relationship explícito).
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    torneo_id: int = Field(foreign_key="torneo.id")
    jugador_id: int = Field(foreign_key="jugador.id")
    estado: EstadoInscripcion = Field(default=EstadoInscripcion.confirmado)
    posicion_espera: Optional[int] = Field(default=None)
    pista_asignada: Optional[int] = Field(default=None)
    acompanante_id: Optional[int] = Field(default=None)
    pagado: bool = Field(default=False)
    fecha_pago: Optional[datetime] = Field(default=None)
    metodo_pago: Optional[MetodoPago] = Field(default=None)  # tarjeta | efectivo
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ═══════════════════════════════════════════════════════════════
# Tabla: extra
# ═══════════════════════════════════════════════════════════════

class Extra(SQLModel, table=True):
    """
    Un consumo adicional de un jugador en un torneo concreto.
    Ejemplos: bebida (1.50€), snack (2€), camiseta (15€).
    Separado en tabla propia (en lugar de JSON) para poder sumar fácilmente.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    inscripcion_id: int = Field(foreign_key="inscripcion.id")
    concepto: str                             # "Bebida", "Snack", etc.
    precio: float
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ═══════════════════════════════════════════════════════════════
# Tabla: partido
# ═══════════════════════════════════════════════════════════════

class Partido(SQLModel, table=True):
    """
    Un partido jugado en una pista durante una ronda del torneo.
    jugadores y resultado se guardan como JSON en texto porque SQLite
    no tiene tipo de dato JSON nativo (y es sencillo de parsear en Python).

    jugadores: "[1, 2, 3, 4]"  → IDs de los 4 jugadores
    resultado: '{"set1": "6-3", "set2": "4-6", "set3": "7-5"}' (opcional)
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    torneo_id: int = Field(foreign_key="torneo.id")
    pista: int                                # 1–6
    ronda: int                                # Número de ronda
    jugadores: str                            # JSON: "[id1, id2, id3, id4]"
    resultado: Optional[str] = Field(default=None)  # JSON con el resultado
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ═══════════════════════════════════════════════════════════════
# Tabla: solicitudcambiopista
# ═══════════════════════════════════════════════════════════════

class SolicitudCambioPista(SQLModel, table=True):
    """
    Un jugador solicita subir a una pista de mejor nivel.
    El admin ve las pendientes con un badge y acepta/rechaza con un toque.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    jugador_id: int = Field(foreign_key="jugador.id")
    torneo_id: int = Field(foreign_key="torneo.id")
    pista_destino: int                        # La pista a la que quiere ir (1–6)
    estado: EstadoSolicitud = Field(default=EstadoSolicitud.pendiente)
    created_at: datetime = Field(default_factory=datetime.utcnow)
