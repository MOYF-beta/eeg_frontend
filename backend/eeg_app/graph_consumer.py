import asyncio
import json
import time
from channels.generic.websocket import AsyncWebsocketConsumer


class EegGraphConsumer(AsyncWebsocketConsumer):
    """计算图数据流 WebSocket Consumer (支持SAVE/REPLAY)
    
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
        self._save_nodes = []  # SAVE节点列表
        self._replay_nodes = []  # REPLAY节点列表
        
        # 从 graph_store 获取计算图状态
        from .graph_store import get_graph
        graph = get_graph()
        self.graph_frozen = graph.get('frozen', False)
        
        print(f"[WebSocket] Client connected, graph frozen: {self.graph_frozen}")
        
        # 初始化SAVE和REPLAY节点
        self._init_save_replay_nodes(graph)
        
        # 如果计算图已冻结，开始发送数据
        if self.graph_frozen:
            asyncio.create_task(self.stream_data())
    
    async def disconnect(self, code):
        self.running = False
        # 停止所有录制和回放
        self._stop_all_save_replay()
        print(f"[WebSocket] Client disconnected, code: {code}")
    
    def _init_save_replay_nodes(self, graph):
        """初始化SAVE和REPLAY节点"""
        from .data_recorder import start_recording
        from .data_replay import start_replay
        
        nodes = graph.get('nodes', [])
        
        # 收集SAVE节点
        self._save_nodes = []
        for node in nodes:
            if node.get('type') == 'SAVE':
                params = node.get('params', {})
                filename = params.get('filename')
                format_type = params.get('format', 'CSV')
                
                result = start_recording(
                    node_id=node['id'],
                    filename=filename,
                    format=format_type
                )
                if result.get('ok'):
                    self._save_nodes.append(node['id'])
                    print(f"[WebSocket] SAVE node initialized: {node['id']} -> {result.get('filepath')}")
                else:
                    print(f"[WebSocket] SAVE node failed: {node['id']} - {result.get('error')}")
        
        # 收集REPLAY节点
        self._replay_nodes = []
        for node in nodes:
            if node.get('type') == 'REPLAY':
                params = node.get('params', {})
                filename = params.get('file')
                if isinstance(filename, list) and filename:
                    filename = filename[0]  # v-file-input returns array
                loop = params.get('loop', False)
                
                if filename:
                    result = start_replay(
                        node_id=node['id'],
                        filename=filename,
                        loop=loop
                    )
                    if result.get('ok'):
                        self._replay_nodes.append(node['id'])
                        print(f"[WebSocket] REPLAY node initialized: {node['id']} -> {result.get('filename')}")
                    else:
                        print(f"[WebSocket] REPLAY node failed: {node['id']} - {result.get('error')}")
    
    def _stop_all_save_replay(self):
        """停止所有录制和回放"""
        from .data_recorder import stop_recording
        from .data_replay import stop_replay
        
        for node_id in self._save_nodes:
            result = stop_recording(node_id)
            print(f"[WebSocket] SAVE stopped: {node_id} - {result}")
        
        for node_id in self._replay_nodes:
            result = stop_replay(node_id)
            print(f"[WebSocket] REPLAY stopped: {node_id} - {result}")
        
        self._save_nodes = []
        self._replay_nodes = []
    
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
                
            elif msg_type == 'get_recordings':
                # 返回活跃录制列表
                from .data_recorder import get_active_recordings
                recordings = get_active_recordings()
                await self.send(text_data=json.dumps({
                    'type': 'recordings',
                    'recordings': recordings
                }))
                
            elif msg_type == 'get_saved_files':
                # 返回已保存文件列表
                from .data_recorder import list_saved_files
                files = list_saved_files()
                await self.send(text_data=json.dumps({
                    'type': 'saved_files',
                    'files': files
                }))
                
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
    
    def _get_source_channels(self):
        """获取数据源通道数据（支持REPLAY节点）"""
        from .data_replay import read_next_sample, is_replaying
        
        # 优先使用REPLAY节点作为数据源
        for node_id in self._replay_nodes:
            if is_replaying(node_id):
                sample = read_next_sample(node_id)
                if sample:
                    return sample['channels']
        
        # 没有REPLAY节点或回放结束，返回None
        return None
    
    def _save_channels(self, channels):
        """保存通道数据到所有SAVE节点"""
        from .data_recorder import write_sample
        
        timestamp = time.time() * 1000
        for node_id in self._save_nodes:
            write_sample(node_id, timestamp, channels)
    
    async def stream_data(self):
        """发送计算图处理后的数据 (30fps 批次发送)"""
        import math
        import random
        
        from .graph_store import get_graph
        
        t = 0.0
        sample_rate = 1000  # Hz
        dt = 1.0 / sample_rate
        
        # 30fps 发送配置
        TARGET_FPS = 30
        FRAME_INTERVAL = 1.0 / TARGET_FPS  # ~33.33ms
        
        # 数据缓冲区
        sample_buffer = {}
        last_send_time = time.time()
        
        # 50Hz 低通滤波器（一阶RC滤波器）
        FILTER_CUTOFF = 50  # Hz
        RC = 1.0 / (2 * math.pi * FILTER_CUTOFF)
        alpha = dt / (RC + dt)
        
        # 每通道的滤波器状态
        filtered_values = [0.0] * 8
        first_sample = [True] * 8
        
        # 检查是否有REPLAY节点
        
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
            
            # 获取数据源
            replay_channels = self._get_source_channels()
            
            if replay_channels is not None:
                # 使用回放数据
                raw_channels = replay_channels
            else:
                # 生成模拟数据（方波 + 噪声，25Hz方波用于测试）
                raw_channels = []
                for i in range(8):
                    # 方波信号 - 25Hz
                    freq = 25
                    square = 1 if math.sin(2 * math.pi * freq * t) > 0 else -1
                    square_signal = square * 30
                    
                    # 高频噪声
                    high_freq1 = 50 + i * 10
                    high_freq2 = 120 + i * 5
                    noise = math.sin(2 * math.pi * high_freq1 * t) * 20 + \
                            math.sin(2 * math.pi * high_freq2 * t) * 15
                    
                    # 随机噪声
                    random_noise = random.uniform(-5, 5)
                    
                    raw_channels.append(square_signal + noise + random_noise)
            
            # 应用50Hz低通滤波器
            channels = []
            for i in range(8):
                if first_sample[i]:
                    filtered_values[i] = raw_channels[i]
                    first_sample[i] = False
                else:
                    # 一阶低通滤波器
                    filtered_values[i] = alpha * raw_channels[i] + (1 - alpha) * filtered_values[i]
                channels.append(filtered_values[i])
            
            # 保存数据到文件（如果有SAVE节点）
            if self._save_nodes:
                self._save_channels(channels)
            
            # 获取计算图节点并缓冲数据
            nodes = graph.get('nodes', [])
            
            for node in nodes:
                if node['type'] != 'OSC':
                    continue
                if node['id'] not in self.subscribed_nodes:
                    continue
                
                # 初始化缓冲区
                if node['id'] not in sample_buffer:
                    sample_buffer[node['id']] = []
                
                # 添加样本到缓冲区
                sample_buffer[node['id']].append(channels[:])  # 复制列表
            
            # 检查是否到达发送时间（30fps）
            current_time = time.time()
            elapsed = current_time - last_send_time
            
            if elapsed >= FRAME_INTERVAL:
                last_send_time = current_time
                
                # 发送缓冲的数据
                for node_id, samples in list(sample_buffer.items()):
                    if samples:
                        # 使用最新的样本
                        latest_channels = samples[-1]
                        
                        # 发送数据包
                        payload = {
                            'type': 'data',
                            'timestamp': int(time.time() * 1000),
                            'nodeId': node_id,
                            'channels': latest_channels,
                            'sampleRate': sample_rate,
                        }
                        
                        try:
                            await self.send(text_data=json.dumps(payload))
                        except Exception as e:
                            print(f"[WebSocket] Send error: {e}")
                            self.running = False
                            break
                
                # 清空缓冲区
                sample_buffer.clear()
            await asyncio.sleep(dt)
