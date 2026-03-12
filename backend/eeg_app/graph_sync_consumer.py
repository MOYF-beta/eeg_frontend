from __future__ import annotations

import json
import time

from channels.generic.websocket import AsyncWebsocketConsumer

from .graph_store import get_graph
from .graph_sync import GRAPH_SYNC_GROUP


class GraphSyncConsumer(AsyncWebsocketConsumer):
    """计算图同步 WebSocket（后端权威）。"""

    async def connect(self):
        await self.channel_layer.group_add(GRAPH_SYNC_GROUP, self.channel_name)
        await self.accept()
        await self._send_graph_state(reason='initial')

    async def disconnect(self, code):
        await self.channel_layer.group_discard(GRAPH_SYNC_GROUP, self.channel_name)

    async def receive(self, text_data):
        try:
            message = json.loads(text_data or '{}')
            msg_type = message.get('type')

            if msg_type == 'ping':
                await self.send(text_data=json.dumps({'type': 'pong'}))
            elif msg_type == 'get_graph':
                await self._send_graph_state(reason='pull')
        except Exception:
            await self.send(text_data=json.dumps({'type': 'error', 'error': 'Invalid message'}))

    async def graph_state(self, event):
        await self.send(text_data=json.dumps({
            'type': 'graph_state',
            'graph': event.get('graph', get_graph()),
            'reason': event.get('reason', 'updated'),
            'timestamp': int(event.get('timestamp', int(time.time() * 1000))),
        }))

    async def _send_graph_state(self, reason: str):
        await self.send(text_data=json.dumps({
            'type': 'graph_state',
            'graph': get_graph(),
            'reason': reason,
            'timestamp': int(time.time() * 1000),
        }))
