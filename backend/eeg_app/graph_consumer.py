import asyncio
import json
import time
from collections import deque

import numpy as np
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
        self._spectrum_buffers = [deque(maxlen=2048) for _ in range(8)]
        
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

    @staticmethod
    def _extract_fft_size(nodes):
        """从 SPECTRUM 节点参数中提取 FFT 点数，缺省 512"""
        valid_sizes = {256, 512, 1024, 2048}
        for node in nodes:
            if node.get('type') != 'SPECTRUM':
                continue
            params = node.get('params', {}) or {}
            raw = params.get('fftSize', params.get('fft_size', 512))
            try:
                size = int(raw)
            except Exception:
                continue
            if size in valid_sizes:
                return size
        return 512

    def _compute_spectrum_bundle(self, sample_rate: int, fft_size: int):
        """计算后端频谱数据（每通道频谱 + 平均频谱 + 时频谱行）"""
        if fft_size < 8:
            return None

        min_len = min((len(ch) for ch in self._spectrum_buffers), default=0)
        if min_len < fft_size:
            return None

        channel_frames = []
        for ch in self._spectrum_buffers:
            arr = np.array(list(ch)[-fft_size:], dtype=np.float64)
            channel_frames.append(arr)

        data = np.stack(channel_frames, axis=0)  # [C, N]
        window = np.hamming(fft_size)
        data = data * window

        fft = np.fft.rfft(data, axis=1)
        mags = np.abs(fft) / fft_size  # [C, K]
        avg = np.mean(mags, axis=0)    # [K]

        db = 20.0 * np.log10(np.maximum(avg, 1e-12))
        db_min = float(np.min(db))
        db_max = float(np.max(db))
        span = max(1e-6, db_max - db_min)
        norm_row = np.clip((db - db_min) / span, 0.0, 1.0)

        return {
            'fftSize': fft_size,
            'freqResolution': float(sample_rate / fft_size),
            'spectra': mags.tolist(),
            'spectrum': avg.tolist(),
            'spectrogramRow': norm_row.tolist(),
            'spectrogramDbMin': db_min,
            'spectrogramDbMax': db_max,
        }
    
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

        # 采样节拍控制（基于实际耗时追赶采样率）
        last_sample_time = time.perf_counter()
        sample_accumulator = 0.0
        max_samples_per_loop = int(sample_rate * 0.2)  # 最多补偿200ms
        
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
            
            # 计算应生成的样本数
            now = time.perf_counter()
            elapsed_samples = (now - last_sample_time) * sample_rate
            last_sample_time = now
            sample_accumulator += elapsed_samples
            samples_to_generate = int(sample_accumulator)

            if samples_to_generate <= 0:
                await asyncio.sleep(0.001)
                continue

            if samples_to_generate > max_samples_per_loop:
                samples_to_generate = max_samples_per_loop
                sample_accumulator = 0.0
            else:
                sample_accumulator -= samples_to_generate

            # 获取计算图节点并缓冲数据
            nodes = graph.get('nodes', [])
            osc_nodes = [node for node in nodes if node.get('type') == 'OSC' and node.get('id') in self.subscribed_nodes]
            spectrum_nodes = [node for node in nodes if node.get('type') == 'SPECTRUM' and node.get('id') in self.subscribed_nodes]
            output_nodes = osc_nodes + spectrum_nodes

            fft_size = self._extract_fft_size(nodes)

            for _ in range(samples_to_generate):
                # 获取数据源（每个样本一次，支持REPLAY）
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
                    self._spectrum_buffers[i].append(filtered_values[i])

                # 保存数据到文件（如果有SAVE节点）
                if self._save_nodes:
                    self._save_channels(channels)

                for node in output_nodes:
                    node_id = node['id']
                    if node_id not in sample_buffer:
                        sample_buffer[node_id] = []
                    sample_buffer[node_id].append(channels[:])

                t += dt
            
            # 检查是否到达发送时间（30fps）
            current_time = time.time()
            elapsed = current_time - last_send_time
            
            if elapsed >= FRAME_INTERVAL:
                last_send_time = current_time
                node_type_map = {node.get('id'): node.get('type') for node in nodes}
                spectrum_bundle = self._compute_spectrum_bundle(sample_rate, fft_size)
                
                # 发送缓冲的数据
                for node_id, samples in list(sample_buffer.items()):
                    if samples:
                        # 使用最新的样本作为兼容字段，同时发送批量样本
                        latest_channels = samples[-1]

                        # 发送数据包（批量样本）
                        payload = {
                            'type': 'data',
                            'timestamp': int(time.time() * 1000),
                            'nodeId': node_id,
                            'nodeType': node_type_map.get(node_id),
                            'channels': latest_channels,
                            'samples': samples,
                            'sampleRate': sample_rate,
                        }

                        # 频谱数据由后端统一计算，供频谱/时频谱前端直接消费
                        if spectrum_bundle is not None:
                            payload.update(spectrum_bundle)

                        try:
                            await self.send(text_data=json.dumps(payload))
                        except Exception as e:
                            print(f"[WebSocket] Send error: {e}")
                            self.running = False
                            break
                
                # 清空缓冲区
                sample_buffer.clear()
            await asyncio.sleep(0.001)
