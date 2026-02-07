import asyncio
import json
import math
import random
import time
from channels.generic.websocket import AsyncWebsocketConsumer


class EegStreamConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        self.running = True
        asyncio.create_task(self.stream_data())

    async def disconnect(self, code):
        self.running = False

    async def stream_data(self):
        t = 0.0
        while self.running:
            channels = [
                math.sin(t + i * 0.3)
                + math.cos(t * 0.5 + i) * 0.2
                + random.uniform(-0.15, 0.15)
                for i in range(8)
            ]
            payload = {
                't': time.time(),
                'channels': channels,
            }
            await self.send(text_data=json.dumps(payload))
            t += 0.1
            await asyncio.sleep(0.05)
