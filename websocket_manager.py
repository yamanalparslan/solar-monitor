"""
Solar Monitor - WebSocket Bağlantı Yöneticisi
===============================================
Canlı veri yayını için WebSocket bağlantılarını yönetir.

Kullanım:
    from websocket_manager import manager
    await manager.broadcast(data)
"""

import json
import logging
from typing import Dict, Any
from fastapi import WebSocket

logger = logging.getLogger("websocket")


class ConnectionManager:
    """WebSocket istemci bağlantılarını yönetir."""

    def __init__(self):
        self._active: list[WebSocket] = []

    @property
    def client_count(self) -> int:
        return len(self._active)

    async def connect(self, ws: WebSocket):
        """Yeni istemci bağlantısını kabul eder."""
        await ws.accept()
        self._active.append(ws)
        logger.info("WS istemci bağlandı (%d aktif)", self.client_count)

    def disconnect(self, ws: WebSocket):
        """İstemci bağlantısını kaldırır."""
        if ws in self._active:
            self._active.remove(ws)
        logger.info("WS istemci ayrıldı (%d aktif)", self.client_count)

    async def broadcast(self, data: Dict[str, Any]):
        """Tüm bağlı istemcilere JSON veri yayınlar."""
        if not self._active:
            return

        message = json.dumps(data, ensure_ascii=False, default=str)
        dead = []

        for ws in self._active:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)

        # Kopmuş bağlantıları temizle
        for ws in dead:
            self.disconnect(ws)

    async def send_personal(self, ws: WebSocket, data: Dict[str, Any]):
        """Tek bir istemciye mesaj gönderir."""
        try:
            await ws.send_text(json.dumps(data, ensure_ascii=False, default=str))
        except Exception:
            self.disconnect(ws)


# Singleton instance
manager = ConnectionManager()
