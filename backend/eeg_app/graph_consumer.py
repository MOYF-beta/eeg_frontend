import asyncio
import json
import math
import random
import time
from collections import deque
from typing import Dict, List, Set, Optional

import numpy as np
from channels.generic.websocket import AsyncWebsocketConsumer

from .device_store import get_device
from .graph_store import get_runtime_state


def generate_signal_from_config(channel_config: Dict, t: float, sample_rate: float = 1000.0) -> float:
    """根据通道配置生成信号值
    
    Args:
        channel_config: 通道配置字典
        t: 时间（秒）
        sample_rate: 采样率（Hz）
    
    Returns:
        信号值
    """
    if not channel_config.get('enabled', True):
        return 0.0
    
    wave_type = channel_config.get('wave_type', 'sine')
    frequency = float(channel_config.get('frequency', 10.0))
    amplitude = float(channel_config.get('amplitude', 100.0))
    phase = float(channel_config.get('phase', 0.0)) * math.pi / 180.0  # 转换为弧度
    
    # 基础信号
    base_signal = 0.0
    
    if wave_type == 'sine':
        # 正弦波
        base_signal = amplitude * math.sin(2 * math.pi * frequency * t + phase)
    
    elif wave_type == 'square':
        # 方波
        duty_cycle = float(channel_config.get('duty_cycle', 0.5))
        phase_rad = 2 * math.pi * frequency * t + phase
        phase_mod = phase_rad % (2 * math.pi)
        if phase_mod < 2 * math.pi * duty_cycle:
            base_signal = amplitude
        else:
            base_signal = -amplitude
    
    elif wave_type == 'triangle':
        # 三角波
        phase_rad = 2 * math.pi * frequency * t + phase
        phase_mod = phase_rad % (2 * math.pi)
        if phase_mod < math.pi:
            base_signal = amplitude * (2 * phase_mod / math.pi - 1)
        else:
            base_signal = amplitude * (3 - 2 * phase_mod / math.pi)
    
    elif wave_type == 'pulse':
        # 脉冲
        pulse_width = float(channel_config.get('pulse_width', 0.01))
        duty_cycle = float(channel_config.get('duty_cycle', 0.1))
        period = 1.0 / frequency
        pulse_time = t % period
        
        if pulse_time < pulse_width:
            base_signal = amplitude
        else:
            base_signal = 0.0
    
    elif wave_type == 'multi_sine':
        # 多个正弦波叠加
        sine_components = channel_config.get('sine_components', [])
        if not sine_components:
            # 如果没有分量，使用默认正弦波
            base_signal = amplitude * math.sin(2 * math.pi * frequency * t + phase)
        else:
            base_signal = 0.0
            for comp in sine_components:
                comp_freq = float(comp.get('frequency', frequency))
                comp_amp = float(comp.get('amplitude', amplitude))
                comp_phase = float(comp.get('phase', 0.0)) * math.pi / 180.0
                base_signal += comp_amp * math.sin(2 * math.pi * comp_freq * t + comp_phase)
    
    else:
        # 默认正弦波
        base_signal = amplitude * math.sin(2 * math.pi * frequency * t + phase)
    
    # 添加通道噪声
    noise_type = channel_config.get('noise_type', 'none')
    noise_amplitude = float(channel_config.get('noise_amplitude', 0.0))
    
    if noise_type == 'white' and noise_amplitude > 0:
        # 白噪声
        base_signal += random.uniform(-noise_amplitude, noise_amplitude)
    elif noise_type == 'gaussian' and noise_amplitude > 0:
        # 高斯噪声
        base_signal += random.gauss(0, noise_amplitude / 3.0)  # 3σ原则
    
    return base_signal


def get_device_channels(device_id: str, t: float, sample_rate: float = 1000.0) -> Optional[List[float]]:
    """根据设备配置生成所有通道的信号
    
    Args:
        device_id: 设备ID
        t: 时间（秒）
        sample_rate: 采样率（Hz）
    
    Returns:
        通道信号列表，如果设备不存在则返回None
    """
    from .device_store import get_device
    from .real_device_manager import get_real_device_manager
    
    device = get_device(device_id)
    if not device:
        return None
    
    device_type = device.get('type', 'simulated')
    device_config = device.get('config', {}) or {}
    
    if device_type == 'wearable_eeg':
        # 真实设备：从设备管理器获取数据
        port = device_config.get('port')
        if not port:
            return None
        
        manager = get_real_device_manager()
        latest_data = manager.get_latest_data(port, count=1)
        
        if not latest_data:
            # 如果没有实时数据，返回模拟数据作为后备
            return _generate_fallback_channels(device_config, t, sample_rate)
        
        # 获取最新的数据
        data = latest_data[-1]
        raw_channels = data.get('channels', [])
        
        # 转换为浮点数（原始数据是整数），并归一化到伏特量级
        channels = [float(ch) / 1_000_000.0 for ch in raw_channels]
        
        # 确保有8个通道
        if len(channels) < 8:
            channels.extend([0.0] * (8 - len(channels)))
        elif len(channels) > 8:
            channels = channels[:8]
            
        return channels
    
    else:
        # 模拟设备：使用原有的信号生成逻辑
        channels_config = device_config.get('channels', [])
        if not channels_config:
            return None
        
        # 按索引排序通道配置
        sorted_channels = sorted(channels_config, key=lambda x: x.get('index', 0))
        
        # 生成每个通道的信号
        channels = []
        for channel_config in sorted_channels:
            signal_value = generate_signal_from_config(channel_config, t, sample_rate)
            channels.append(signal_value)
        
        return channels


def _generate_fallback_channels(device_config: Dict, t: float, sample_rate: float) -> List[float]:
    """生成后备通道数据（当真实设备没有数据时使用）
    
    Args:
        device_config: 设备配置
        t: 时间（秒）
        sample_rate: 采样率（Hz）
    
    Returns:
        后备通道数据
    """
    # 生成简单的正弦波作为后备数据
    channels = []
    for i in range(8):  # 默认8个通道
        frequency = 10.0 + i * 2.0
        amplitude = 100.0
        phase = i * 0.3
        value = amplitude * math.sin(2 * math.pi * frequency * t + phase)
        channels.append(value)
    
    return channels


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
        self._stream_task = None  # 数据流任务
        
        # 从 graph_store 获取计算图状态
        from .graph_store import get_graph
        graph = get_graph()
        self.graph_frozen = graph.get('frozen', False)
        
        print(f"[WebSocket] Client connected, graph frozen: {self.graph_frozen}")
        
        # 初始化SAVE和REPLAY节点
        self._init_save_replay_nodes(graph)
        
        # 如果计算图已冻结，开始发送数据
        if self.graph_frozen:
            self._stream_task = asyncio.create_task(self.stream_data())
            print(f"[WebSocket] Started stream data task: {self._stream_task}")
    
    async def disconnect(self, code):
        print(f"[WebSocket] Client disconnecting, code: {code}")
        self.running = False
        
        # 取消数据流任务
        if self._stream_task and not self._stream_task.done():
            print(f"[WebSocket] Cancelling stream data task: {self._stream_task}")
            self._stream_task.cancel()
            try:
                await self._stream_task
            except asyncio.CancelledError:
                print("[WebSocket] Stream task cancelled successfully")
            except Exception as e:
                print(f"[WebSocket] Error cancelling stream task: {e}")
        
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
                if not self.running:
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

    @staticmethod
    def _default_channel_names(count: int) -> List[str]:
        return [f'CH{i + 1}' for i in range(max(0, count))]

    @staticmethod
    def _parse_channel_indices(raw: object) -> List[int]:
        if not isinstance(raw, str):
            return []
        result: List[int] = []
        for part in raw.split(','):
            item = part.strip()
            if not item:
                continue
            try:
                idx = int(item)
            except Exception:
                continue
            if idx >= 0:
                result.append(idx)
        return result

    @staticmethod
    def _clone_signal(signal: Dict) -> Dict:
        return {
            'channels': list(signal.get('channels', [])),
            'channelNames': list(signal.get('channelNames', [])),
        }

    def _compute_node_outputs(
        self,
        node_id: str,
        nodes_by_id: Dict[str, Dict],
        incoming_by_target: Dict[str, List[Dict]],
        default_source_signal: Dict,
        memo: Dict[str, Dict[str, Dict]],
        visiting: Set[str],
    ) -> Dict[str, Dict]:
        if node_id in memo:
            return memo[node_id]

        if node_id in visiting:
            memo[node_id] = {}
            return memo[node_id]

        node = nodes_by_id.get(node_id)
        if not node:
            memo[node_id] = {}
            return memo[node_id]

        visiting.add(node_id)

        node_type = node.get('type')
        params = node.get('params') or {}
        incoming_edges = sorted(
            incoming_by_target.get(node_id, []),
            key=lambda e: str(e.get('targetPort') or ''),
        )

        def get_edge_signal(edge: Dict) -> Dict:
            source_id = edge.get('source')
            if not source_id:
                return {'channels': [], 'channelNames': []}
            source_outputs = self._compute_node_outputs(
                source_id,
                nodes_by_id,
                incoming_by_target,
                default_source_signal,
                memo,
                visiting,
            )
            source_port = edge.get('sourcePort') or 'out'
            if source_port in source_outputs:
                return self._clone_signal(source_outputs[source_port])
            if source_outputs:
                first = next(iter(source_outputs.values()))
                return self._clone_signal(first)
            return {'channels': [], 'channelNames': []}

        def get_first_input_signal() -> Dict:
            for edge in incoming_edges:
                sig = get_edge_signal(edge)
                if sig.get('channels'):
                    return sig
            return {'channels': [], 'channelNames': []}

        outputs: Dict[str, Dict] = {}

        if node_type in {'SOURCE', 'REPLAY'}:
            channels = list(default_source_signal.get('channels', []))
            names = params.get('channelNames')
            if isinstance(names, list) and names:
                channel_names = [str(v) for v in names]
            else:
                channel_names = self._default_channel_names(len(channels))
            outputs['out'] = {'channels': channels, 'channelNames': channel_names}

        elif node_type == 'FILTER':
            in_sig = get_first_input_signal()
            outputs['out'] = in_sig

        elif node_type == 'SUM':
            input_cfg = params.get('inputs')
            if not isinstance(input_cfg, list):
                input_cfg = []

            total = 0.0
            has_value = False
            if input_cfg:
                for idx, cfg in enumerate(input_cfg):
                    target_port = f'in-{idx + 1}'
                    edge = next((e for e in incoming_edges if (e.get('targetPort') or 'in') == target_port), None)
                    if not edge:
                        continue
                    sig = get_edge_signal(edge)
                    channels = sig.get('channels', [])
                    if not channels:
                        continue
                    weight = 1.0
                    if isinstance(cfg, dict):
                        try:
                            weight = float(cfg.get('weight', 1.0))
                        except Exception:
                            weight = 1.0
                    total += channels[0] * weight
                    has_value = True
            else:
                for edge in incoming_edges:
                    sig = get_edge_signal(edge)
                    channels = sig.get('channels', [])
                    if not channels:
                        continue
                    total += channels[0]
                    has_value = True

            out_channels = [total] if has_value else []
            outputs['out'] = {
                'channels': out_channels,
                'channelNames': [str(node.get('name') or 'SUM')] if out_channels else [],
            }

        elif node_type == 'SPLIT':
            in_sig = get_first_input_signal()
            in_channels = list(in_sig.get('channels', []))
            in_names = list(in_sig.get('channelNames', []))
            outputs_cfg = params.get('outputs')
            if not isinstance(outputs_cfg, list) or len(outputs_cfg) == 0:
                outputs_cfg = [{'label': '输出1', 'channelIndices': ','.join(str(i) for i in range(len(in_channels)))}]

            for idx, cfg in enumerate(outputs_cfg):
                port = f'out-{idx + 1}'
                label = f'输出{idx + 1}'
                channel_indices_raw = ''
                if isinstance(cfg, dict):
                    label = str(cfg.get('label') or label)
                    channel_indices_raw = str(cfg.get('channelIndices') or '')

                indices = self._parse_channel_indices(channel_indices_raw)
                if indices:
                    out_channels = [in_channels[i] for i in indices if 0 <= i < len(in_channels)]
                    out_names = [in_names[i] if i < len(in_names) else f'CH{i + 1}' for i in indices if 0 <= i < len(in_channels)]
                else:
                    out_channels = list(in_channels)
                    out_names = list(in_names)

                if not out_names and out_channels:
                    out_names = self._default_channel_names(len(out_channels))

                if len(out_names) == 1 and label:
                    out_names = [label]

                outputs[port] = {
                    'channels': out_channels,
                    'channelNames': out_names,
                }

        elif node_type == 'MERGE':
            input_cfg = params.get('inputs')
            if not isinstance(input_cfg, list):
                input_cfg = []

            out_channels: List[float] = []
            out_names: List[str] = []

            for idx, edge in enumerate(incoming_edges):
                sig = get_edge_signal(edge)
                channels = list(sig.get('channels', []))
                names = list(sig.get('channelNames', []))
                gain = 1.0
                if idx < len(input_cfg) and isinstance(input_cfg[idx], dict):
                    try:
                        gain = float(input_cfg[idx].get('gain', 1.0))
                    except Exception:
                        gain = 1.0
                out_channels.extend([v * gain for v in channels])
                if names:
                    out_names.extend(names)
                else:
                    out_names.extend(self._default_channel_names(len(channels)))

            outputs['out'] = {'channels': out_channels, 'channelNames': out_names}

        elif node_type in {'OSC', 'SPECTRUM', 'SAVE'}:
            outputs['in'] = get_first_input_signal()

        else:
            outputs['out'] = get_first_input_signal()

        memo[node_id] = outputs
        visiting.remove(node_id)
        return outputs
    
    def _save_channels(self, channels, node_ids=None):
        """保存通道数据到指定或全部 SAVE 节点"""
        from .data_recorder import write_sample
        
        timestamp = time.time() * 1000
        target_nodes = node_ids if node_ids is not None else self._save_nodes
        for node_id in target_nodes:
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
        sample_channel_names: Dict[str, List[str]] = {}
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
            try:
                # 刷新计算图状态
                graph = get_graph()
                self.graph_frozen = graph.get('frozen', False)
                
                # 检查计算图是否正在运行
                runtime_state = get_runtime_state()
                is_graph_running = runtime_state.get('running', False)
                
                if not is_graph_running:
                    # 计算图未运行，停止发送
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
                edges = graph.get('edges', [])
                nodes_by_id = {node.get('id'): node for node in nodes if node.get('id')}
                incoming_by_target: Dict[str, List[Dict]] = {}
                for edge in edges:
                    target = edge.get('target')
                    if not target:
                        continue
                    incoming_by_target.setdefault(target, []).append(edge)

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
                        # 获取SOURCE节点绑定的设备配置
                        source_nodes = [node for node in nodes if node.get('type') == 'SOURCE']
                        device_channels = None
                        
                        if source_nodes:
                            # 使用第一个SOURCE节点的设备配置
                            source_node = source_nodes[0]
                            device_id = source_node.get('params', {}).get('deviceId')
                            if device_id:
                                # 根据设备配置生成信号
                                device_channels = get_device_channels(device_id, t, float(sample_rate))
                        
                        if device_channels is not None:
                            # 使用设备配置生成的信号
                            raw_channels = device_channels
                        else:
                            # 如果没有设备配置，使用默认模拟数据（方波 + 噪声，25Hz方波用于测试）
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

                    base_signal = {
                        'channels': channels,
                        'channelNames': self._default_channel_names(len(channels)),
                    }
                    memo: Dict[str, Dict[str, Dict]] = {}

                    # 保存节点：写入其输入通道
                    for save_node_id in self._save_nodes:
                        save_out = self._compute_node_outputs(
                            save_node_id,
                            nodes_by_id,
                            incoming_by_target,
                            base_signal,
                            memo,
                            set(),
                        )
                        in_sig = save_out.get('in') or {}
                        save_channels = in_sig.get('channels') or []
                        if save_channels:
                            self._save_channels(save_channels, [save_node_id])

                    for node in output_nodes:
                        node_id = node['id']
                        node_outputs = self._compute_node_outputs(
                            node_id,
                            nodes_by_id,
                            incoming_by_target,
                            base_signal,
                            memo,
                            set(),
                        )
                        in_sig = node_outputs.get('in') or node_outputs.get('out') or {}
                        node_channels = list(in_sig.get('channels') or [])
                        node_names = [str(v) for v in (in_sig.get('channelNames') or [])]

                        if node_id not in sample_buffer:
                            sample_buffer[node_id] = []
                        sample_buffer[node_id].append(node_channels)
                        sample_channel_names[node_id] = node_names

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
                                'channelNames': sample_channel_names.get(node_id, []),
                                'sampleRate': sample_rate,
                            }

                            # 频谱数据由后端统一计算，供频谱/时频谱前端直接消费
                            if spectrum_bundle is not None:
                                payload.update(spectrum_bundle)

                            try:
                                await self.send(text_data=json.dumps(payload))
                            except Exception as e:
                                print(f"[WebSocket] Send error: {e}")
                                # 发送错误，可能是连接已断开
                                self.running = False
                                break
                    
                    # 清空缓冲区
                    sample_buffer.clear()
                    sample_channel_names.clear()
                    await asyncio.sleep(0.001)
        
            except asyncio.CancelledError:
                print("[WebSocket] Stream data task cancelled")
                break
            except Exception as e:
                print(f"[WebSocket] Error in stream_data: {e}")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(0.1)  # 避免快速循环
    
    print("[WebSocket] Stream data task ended")
