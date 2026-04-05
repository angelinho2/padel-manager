"""
services/ws_manager.py — Gestor de conexiones WebSocket

Mantiene un registro de todos los clientes conectados agrupados
por torneo. Cuando el admin marca un pago o añade un extra,
el servidor notifica a TODOS los clientes que están mirando
ese torneo al mismo tiempo (útil si uno abre la app en móvil
y otro en tablet para cobrar en dos pistas distintas).

Uso:
  from services.ws_manager import ws_manager

  # Conectar:
  await ws_manager.connect(torneo_id, websocket)

  # Desconectar:
  ws_manager.disconnect(torneo_id, websocket)

  # Broadcast a todos los del torneo:
  await ws_manager.broadcast(torneo_id, {"tipo": "pago", "datos": ...})
"""
import asyncio
import json
from collections import defaultdict

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        # { torneo_id: set of WebSocket connections }
        self._connections: dict[int, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, torneo_id: int, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self._connections[torneo_id].add(ws)

    async def disconnect(self, torneo_id: int, ws: WebSocket):
        async with self._lock:
            self._connections[torneo_id].discard(ws)
            if not self._connections[torneo_id]:
                del self._connections[torneo_id]

    async def broadcast(self, torneo_id: int, payload: dict):
        """
        Envía un mensaje JSON a todos los clientes conectados a este torneo.
        Si un cliente se desconectó a mitad, lo elimina sin lanzar excepción.
        """
        mensaje = json.dumps(payload, ensure_ascii=False, default=str)
        muertos = set()

        async with self._lock:
            clientes = set(self._connections.get(torneo_id, set()))

        for ws in clientes:
            try:
                await ws.send_text(mensaje)
            except Exception:
                muertos.add(ws)

        # Limpiar conexiones muertas
        if muertos:
            async with self._lock:
                self._connections[torneo_id] -= muertos

    def n_connected(self, torneo_id: int) -> int:
        """Número de clientes conectados a un torneo (para debug/UI)."""
        return len(self._connections.get(torneo_id, set()))


# Instancia global compartida por todos los routers
ws_manager = ConnectionManager()
