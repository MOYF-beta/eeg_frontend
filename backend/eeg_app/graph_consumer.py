import asyncio
import json
import time
from channels.generic.websocket import AsyncWebsocketConsumer


class EegGraphConsumer(AsyncWebsocketConsumer):
    """计算图数据流 WebSocket Consumer
    
    消息格式:
    客户端 -> 服务器:
        {"type": "subscribe", "nodeIds": ["osc-1", "osc-2"]}
        {"type": "unsubscribe"}
        {"type": "ping"}
    
    服务器 -> 客户端:
        {"type": "data", "timestamp": 1234567890, "nodeId": "osc-1", "channels": [...], "sampleRate": 1000}
        {"type": "pong"}
        {"type": "error", "error": "..."}
    """
    
    async def connect(self):
        await self.accept()
        self.subscribed_nodes = set()
        self.running = True
        self.graph_frozen = False
        
        # 从 graph_store 获取计算图状态
        from .graph_store import get_graph
        graph = get_graph()
        self.graph_frozen = graph.get('frozen', False)
        
        print(f"[WebSocket] Client connected, graph frozen: {self.graph_frozen}")
        
        # 如果计算图已冻结，开始发送数据
        if self.graph_frozen:
            asyncio.create_task(self.stream_data())
    
    async def disconnect(self, code):
        self.running = False
        print(f"[WebSocket] Client disconnected, code: {code}")
    
    async def receive(self, text_data):
        """处理客户端消息"""
        try:
            message = json.loads(text_data)
            msg_type = message.get('type')
            
            if msg_type == 'subscribe':
                node_ids = message.get('nodeIds', [])
                self.subscribed_nodes.update(node_ids)
                print(f"[WebSocket] Subscribed to nodes: {node_ids}")
                
                # 如果没有在运行，启动数据流
                if self.graph_frozen and not self.running:
                    self.running = True
                    asyncio.create_task(self.stream_data())
                    
            elif msg_type == 'unsubscribe':
                self.subscribed_nodes.clear()
                print("[WebSocket] Unsubscribed from all nodes")
                
            elif msg_type == 'ping':
                await self.send(text_data=json.dumps({'type': 'pong'}))
                
            elif msg_type == 'command':
                command = message.get('command')
                print(f"[WebSocket] Received command: {command}")
                # TODO: 处理控制命令
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'error': 'Invalid JSON'
            }))
        except Exception as e:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'error': str(e)
            }))
    
    async def stream_data(self):
        """发送计算图处理后的数据"""
        import math
        import random
        
        from .graph_store import get_graph
        
        t = 0.0
        sample_rate = 1000  # Hz
        dt = 1.0 / sample_rate
        
        while self.running:
            # 刷新计算图状态
            graph = get_graph()
            self.graph_frozen = graph.get('frozen', False)
            
            if not self.graph_frozen:
                # 计算图未冻结，停止发送
                await asyncio.sleep(0.1)
                continue
            
            if not self.subscribed_nodes:
                # 没有订阅的节点，等待
                await asyncio.sleep(0.1)
                continue
            
            # 获取计算图节点
            nodes = graph.get('nodes', [])
            
            # 为每个订阅的OSC节点生成数据
            for node in nodes:
                if node['type'] != 'OSC':
                    continue
                if node['id'] not in self.subscribed_nodes:
                    continue
                
                # 获取节点参数
                params = node.get('params', {})
                time_window = params.get('timeWindow', 5)
                
                # 生成模拟数据（方波 + 噪声，与前端测试信号一致）
                channels = []
                for i in range(8):
                    # 方波信号
                    freq = 5 + i * 0.5
                    square = 1 if math.sin(2 * math.pi * freq * t) > 0 else -1
                    square_signal = square * 30
                    
                    # 高频噪声
                    high_freq1 = 50 + i * 10
                    high_freq2 = 120 + i * 5
                    noise = math.sin(2 * math.pi * high_freq1 * t) * 20 + \
                            math.sin(2 * math.pi * high_freq2 * t) * 15
                    
                    # 随机噪声
                    random_noise = random.uniform(-5, 5)
                    
                    channels.append(square_signal + noise + random_noise)
                
                # 发送数据包
                payload = {
                    'type': 'data',
                    'timestamp': int(time.time() * 1000),
                    'nodeId': node['id'],
                    'channels': channels,
                    'sampleRate': sample_rate,
                }
                
                try:
                    await self.send(text_data=json.dumps(payload))
                except Exception as e:
                    print(f"[WebSocket] Send error: {e}")
                    self.running = False
                    break
            
            t += dt
            await asyncio.sleep(dt)
