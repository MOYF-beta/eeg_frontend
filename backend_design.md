# 后端数据处理架构设计

本文档定义后端数据处理的核心架构，重点区分实时滑动窗口处理和离线批处理两种模式的实现策略。

---

## 1. 架构总览

### 1.1 处理模式对比

| 特性 | 实时模式（Realtime） | 离线模式（Batch） |
|------|---------------------|------------------|
| 数据来源 | 设备实时流 | 录制文件 |
| 处理方式 | 滑动窗口增量处理 | 全量数据加载后处理 |
| 输出方式 | WebSocket实时推送 | 一次性写入文件 |
| 内存占用 | 固定窗口大小 | 取决于文件大小 |
| 处理延迟 | 实时输出 | 不要求 |
| 状态保持 | 滤波器状态、窗口缓冲 | 无状态 |
| 典型应用 | 实时监控、在线分析 | 数据导出、批量预处理 |

### 1.2 模块划分

```
backend/
├── apps/
│   ├── devices/          # 设备管理
│   ├── streaming/        # 实时数据流
│   ├── processing/       # 数据处理引擎
│   │   ├── realtime/     # 实时处理
│   │   └── batch/        # 离线处理
│   ├── storage/          # 文件存储
│   └── api/              # REST API
├── core/
│   ├── nodes/            # 计算图节点定义
│   ├── graph/            # 计算图执行引擎
│   └── utils/            # 通用工具
└── config/
```

---

## 2. 实时滑动窗口处理

### 2.1 核心概念

**滑动窗口**：维护固定时长的数据缓冲区，每次新数据到达时：
1. 追加新数据到窗口末尾
2. 丢弃窗口开头的旧数据
3. 在窗口上执行计算
4. 输出结果

**特点**：
- 内存占用恒定
- 需维护滤波器状态

### 2.2 数据流架构

```
设备 → 采集线程 → 原始数据队列 → 处理线程 → 输出队列 → WebSocket
                      ↓
                   录制线程 → 磁盘文件
```

### 2.3 实时处理引擎设计

#### 2.3.1 核心类：RealtimeProcessor

```python
# processing/realtime/processor.py
import numpy as np
import pandas as pd
from collections import deque
from threading import Thread, Lock
import time

class RealtimeProcessor:
    """实时数据处理引擎"""
    
    def __init__(self, graph_config, sampling_rate, window_duration=2.0):
        """
        Args:
            graph_config: 计算图配置
            sampling_rate: 采样率（Hz）
            window_duration: 窗口时长（秒）
        """
        self.graph = graph_config
        self.sampling_rate = sampling_rate
        self.window_duration = window_duration
        self.window_samples = int(sampling_rate * window_duration)
        
        # 数据窗口（每个节点一个）
        self.buffers = {}  # {node_id: deque}
        
        # 节点实例
        self.nodes = {}
        
        # 节点执行顺序（拓扑排序）
        self.execution_order = []
        
        # 线程控制
        self.running = False
        self.lock = Lock()
        
        # 输入/输出队列
        self.input_queue = deque(maxlen=100)
        self.output_queues = {}  # {node_id: deque}
        
        self._build()
    
    def _build(self):
        """构建计算图"""
        # 拓扑排序
        self.execution_order = self._topological_sort()
        
        # 初始化节点
        for node_id in self.execution_order:
            node_config = self.graph['nodes'][node_id]
            self.nodes[node_id] = self._create_node(node_config)
            
            # 为输出节点创建输出队列
            if node_config['type'] in ['scope', 'spectrum', 'save']:
                self.output_queues[node_id] = deque(maxlen=50)
            
            # 初始化缓冲区
            self.buffers[node_id] = deque(maxlen=self.window_samples)
    
    def start(self):
        """启动处理线程"""
        self.running = True
        self.thread = Thread(target=self._process_loop, daemon=True)
        self.thread.start()
    
    def stop(self):
        """停止处理"""
        self.running = False
        if hasattr(self, 'thread'):
            self.thread.join(timeout=2.0)
    
    def push_data(self, timestamp, data):
        """
        推送新数据
        
        Args:
            timestamp: 时间戳
            data: numpy数组，shape=(channels, samples)
        """
        with self.lock:
            self.input_queue.append({
                'timestamp': timestamp,
                'data': data
            })
    
    def _process_loop(self):
        """处理循环（在独立线程中运行）"""
        while self.running:
            # 获取输入数据
            if not self.input_queue:
                time.sleep(0.001)  # 1ms
                continue
            
            with self.lock:
                chunk = self.input_queue.popleft()
            
            # 处理数据
            try:
                self._process_chunk(chunk)
            except Exception as e:
                print(f"Processing error: {e}")
                import traceback
                traceback.print_exc()
    
    def _process_chunk(self, chunk):
        """
        处理一个数据块
        
        Args:
            chunk: {'timestamp': float, 'data': np.ndarray}
        """
        timestamp = chunk['timestamp']
        data = chunk['data']  # shape: (channels, samples)
        
        # 转换为DataFrame
        df = pd.DataFrame(
            data.T,  # 转置为 (samples, channels)
            columns=[f'CH{i}' for i in range(data.shape[0])]
        )
        df.insert(0, 'timestamp', 
                  timestamp + np.arange(data.shape[1]) / self.sampling_rate)
        
        # 执行计算图
        results = {}
        
        for node_id in self.execution_order:
            node = self.nodes[node_id]
            node_config = self.graph['nodes'][node_id]
            
            # 获取输入数据
            if node_config['type'] == 'source':
                # 数据源节点直接使用输入
                input_df = df
            else:
                # 从前置节点获取数据
                input_df = self._get_node_input(node_id, results, df)
            
            # 执行节点处理
            output_df = node.process(input_df)
            results[node_id] = output_df
            
            # 更新缓冲区（用于窗口统计）
            self._update_buffer(node_id, output_df)
            
            # 如果是输出节点，推送到输出队列
            if node_config['type'] in ['scope', 'spectrum', 'save']:
                self.output_queues[node_id].append({
                    'timestamp': timestamp,
                    'data': output_df
                })
    
    def _update_buffer(self, node_id, df):
        """更新节点的滑动窗口缓冲区"""
        buffer = self.buffers[node_id]
        
        # 追加新数据（按行）
        for _, row in df.iterrows():
            buffer.append(row.to_dict())
        
        # deque的maxlen会自动丢弃旧数据
    
    def get_window_data(self, node_id):
        """
        获取节点的窗口数据
        
        Returns:
            pd.DataFrame
        """
        with self.lock:
            if node_id not in self.buffers:
                return pd.DataFrame()
            
            buffer = self.buffers[node_id]
            if not buffer:
                return pd.DataFrame()
            
            return pd.DataFrame(list(buffer))
    
    def get_latest_output(self, node_id):
        """获取节点的最新输出"""
        with self.lock:
            if node_id not in self.output_queues:
                return None
            
            queue = self.output_queues[node_id]
            if not queue:
                return None
            
            return queue[-1]
```

#### 2.3.2 有状态节点示例：高通滤波器

```python
# core/nodes/filters.py
from scipy import signal
import pandas as pd
import numpy as np

class HighpassFilterNode:
    """高通滤波器节点（有状态）"""
    
    def __init__(self, cutoff, order, sampling_rate):
        self.cutoff = cutoff
        self.order = order
        self.sampling_rate = sampling_rate
        
        # 设计滤波器
        self.sos = signal.butter(
            order, cutoff, 'high',
            fs=sampling_rate, output='sos'
        )
        
        # 滤波器状态（每个通道一个）
        self.zi = {}  # {channel: state_vector}
    
    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        处理输入数据
        
        Args:
            df: 包含timestamp列和数据列的DataFrame
        
        Returns:
            处理后的DataFrame（列名会添加后缀）
        """
        output_df = df[['timestamp']].copy()
        
        for col in df.columns:
            if col == 'timestamp':
                continue
            
            # 初始化滤波器状态
            if col not in self.zi:
                self.zi[col] = signal.sosfilt_zi(self.sos) * df[col].iloc[0]
            
            # 应用滤波器
            filtered, self.zi[col] = signal.sosfilt(
                self.sos,
                df[col].values,
                zi=self.zi[col]
            )
            
            # 生成新列名
            new_col = f"{col}-HP{self.cutoff}Hz"
            output_df[new_col] = filtered
        
        return output_df
    
    def reset(self):
        """重置滤波器状态"""
        self.zi.clear()
```

#### 2.3.3 无状态节点示例：通道分离器

```python
# core/nodes/utils.py

class ChannelSplitterNode:
    """通道分离器节点（无状态）"""
    
    def __init__(self, groups):
        """
        Args:
            groups: 分组配置，如 "0,1-2,3" 表示 [0], [1,2], [3]
        """
        self.groups = self._parse_groups(groups)
    
    def _parse_groups(self, groups_str):
        """解析分组字符串"""
        groups = []
        for part in groups_str.split(','):
            part = part.strip()
            if '-' in part:
                start, end = map(int, part.split('-'))
                groups.append(list(range(start, end + 1)))
            else:
                groups.append([int(part)])
        return groups
    
    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        处理输入数据
        
        Args:
            df: 包含所有通道的DataFrame
        
        Returns:
            仅包含指定组通道的DataFrame
        """
        # 获取所有数据列（除timestamp）
        data_cols = [col for col in df.columns if col != 'timestamp']
        
        # 选择目标通道
        selected_cols = ['timestamp']
        for group in self.groups:
            for idx in group:
                if idx < len(data_cols):
                    selected_cols.append(data_cols[idx])
        
        return df[selected_cols].copy()
```

### 2.4 WebSocket推送机制

```python
# streaming/consumers.py
from channels.generic.websocket import AsyncWebsocketConsumer
import asyncio
import struct

class RealtimeGraphConsumer(AsyncWebsocketConsumer):
    """实时计算图执行的WebSocket消费者"""
    
    async def connect(self):
        self.execution_id = self.scope['url_route']['kwargs']['execution_id']
        self.processor = None
        
        await self.accept()
        
        # 获取执行实例
        execution = await self.get_execution(self.execution_id)
        
        # 创建处理器
        self.processor = RealtimeProcessor(
            graph_config=execution.graph.graph,
            sampling_rate=execution.config['sampling_rate'],
            window_duration=execution.config.get('window_duration', 2.0)
        )
        
        # 启动处理器
        self.processor.start()
        
        # 发送元信息
        await self.send_meta()
        
        # 启动数据推送任务
        asyncio.create_task(self.push_loop())
    
    async def disconnect(self, close_code):
        if self.processor:
            self.processor.stop()
    
    async def push_loop(self):
        """定期推送数据"""
        while True:
            try:
                await asyncio.sleep(0.04)  # 25 fps
                
                # 获取所有输出节点的最新数据
                for node_id, queue in self.processor.output_queues.items():
                    if not queue:
                        continue
                    
                    latest = queue[-1]
                    
                    # 根据节点类型发送不同格式
                    node_type = self._get_node_type(node_id)
                    
                    if node_type == 'scope':
                        await self.send_wave_frame(node_id, latest)
                    elif node_type == 'spectrum':
                        await self.send_spectrum_frame(node_id, latest)
            
            except Exception as e:
                print(f"Push error: {e}")
                break
    
    async def send_wave_frame(self, node_id, data):
        """发送波形数据帧（二进制）"""
        timestamp = data['timestamp']
        df = data['data']
        
        # 构建帧头
        sample_count = len(df)
        header = struct.pack(
            '<4sBBHHHId',
            b'EEGW',  # magic
            1,        # version
            0x01,     # frameType
            24,       # headerLen
            0,        # reserved
            sample_count,  # sampleCount
            hash(node_id) & 0xFFFFFFFF,  # nodeId作为deviceId
            float(timestamp)
        )
        
        # 构建载荷
        data_cols = [col for col in df.columns if col != 'timestamp']
        payload = b''
        
        for _, row in df.iterrows():
            for col in data_cols:
                payload += struct.pack('<f', row[col])
        
        # 发送
        await self.send(bytes_data=header + payload)
    
    async def send_spectrum_frame(self, node_id, data):
        """发送频谱数据帧（二进制）"""
        # 类似wave_frame，但magic为EEGS
        pass
```

### 2.5 实时录制

```python
# storage/recorder.py
import os
import json
import struct
import threading
from collections import deque

class RealtimeRecorder:
    """实时录制器"""
    
    def __init__(self, filepath, device_id, channels, sampling_rate, metadata=None):
        self.filepath = filepath
        self.device_id = device_id
        self.channels = channels
        self.sampling_rate = sampling_rate
        self.metadata = metadata or {}
        
        self.file = None
        self.buffer = deque(maxlen=250)  # 缓冲1秒数据
        self.lock = threading.Lock()
        self.running = False
        
        self.total_samples = 0
        self.start_timestamp = None
    
    def start(self):
        """开始录制"""
        self.file = open(self.filepath, 'wb')
        
        # 写入文件头
        header = self._make_file_header()
        self.file.write(header)
        
        # 写入元信息区
        self._write_metadata()
        
        self.running = True
        self.thread = threading.Thread(target=self._write_loop, daemon=True)
        self.thread.start()
    
    def stop(self):
        """停止录制"""
        self.running = False
        if hasattr(self, 'thread'):
            self.thread.join(timeout=2.0)
        
        # 刷新缓冲区
        self._flush_buffer()
        
        # 更新文件头（写入总样本数）
        self._update_file_header()
        
        if self.file:
            self.file.close()
    
    def push_data(self, timestamp, data):
        """
        推送数据
        
        Args:
            timestamp: 时间戳
            data: numpy数组，shape=(channels, samples)
        """
        if not self.running:
            return
        
        if self.start_timestamp is None:
            self.start_timestamp = timestamp
        
        with self.lock:
            self.buffer.append({
                'timestamp': timestamp,
                'data': data
            })
    
    def _write_loop(self):
        """写入循环"""
        while self.running:
            # 每100ms写入一次
            threading.Event().wait(0.1)
            self._flush_buffer()
    
    def _flush_buffer(self):
        """刷新缓冲区到磁盘"""
        if not self.buffer:
            return
        
        with self.lock:
            chunks = list(self.buffer)
            self.buffer.clear()
        
        for chunk in chunks:
            self._write_chunk(chunk)
    
    def _write_chunk(self, chunk):
        """写入一个数据块"""
        timestamp = chunk['timestamp']
        data = chunk['data']  # shape: (channels, samples)
        
        # 写入数据（按样本交错存储）
        samples = data.shape[1]

        # 构建数据帧（无deviceId，包含sampleCount）
        frame = struct.pack(
            '<4sBBHHHd',
            b'EEGW',
            1,
            0x01,
            20,  # 帧头20字节（无deviceId）
            0,
            samples,
            float(timestamp)
        )
        for i in range(samples):
            for ch in range(data.shape[0]):
                frame += struct.pack('<f', data[ch, i])
        
        self.file.write(frame)
        self.total_samples += samples
    
    def _make_file_header(self):
        """生成文件头"""
        return struct.pack(
            '<8sHHIIfQ64s28s',
            b'EEGFILE\0',
            1,  # version
            128,  # header_len
            len(self.channels),
            self.sampling_rate,
            self.start_timestamp or 0.0,
            0,  # total_samples（稍后更新）
            self.device_id.encode('utf-8').ljust(64, b'\0'),
            b'\0' * 28  # reserved
        )

    def _write_metadata(self):
        """写入元信息区（JSON）"""
        meta_json = json.dumps(self.metadata, ensure_ascii=False).encode('utf-8')
        self.file.write(struct.pack('<I', len(meta_json)))
        self.file.write(meta_json)
    
    def _update_file_header(self):
        """更新文件头中的总样本数"""
        self.file.seek(28)  # total_samples的位置
        self.file.write(struct.pack('<Q', self.total_samples))
```

---

## 3. 离线批处理

### 3.1 核心概念

**批处理**：一次性加载全部数据到内存，执行完整的处理流程，输出结果文件。

**特点**：
- 可并行处理
- 无需维护状态
- 适合大规模数据

### 3.2 批处理架构

```
录制文件 → 文件读取器 → 全量数据加载 → 批处理引擎 → 结果写入 → 输出文件
                              ↓
                          进度回调 → WebSocket通知前端
```

### 3.3 批处理引擎设计

#### 3.3.1 核心类：BatchProcessor

```python
# processing/batch/processor.py
import numpy as np
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
import os

class BatchProcessor:
    """离线批处理引擎"""
    
    def __init__(self, graph_config, sampling_rate):
        self.graph = graph_config
        self.sampling_rate = sampling_rate
        
        self.nodes = {}
        self.execution_order = []
        
        self._build()
    
    def _build(self):
        """构建计算图"""
        self.execution_order = self._topological_sort()
        
        # 初始化节点（无状态版本）
        for node_id in self.execution_order:
            node_config = self.graph['nodes'][node_id]
            self.nodes[node_id] = self._create_stateless_node(node_config)
    
    def process_file(self, input_file, output_dir, progress_callback=None):
        """
        处理文件
        
        Args:
            input_file: 输入文件路径
            output_dir: 输出目录
            progress_callback: 进度回调函数 callback(progress: float)
        
        Returns:
            dict: 处理结果 {node_id: output_path}
        """
        # 1. 加载数据
        if progress_callback:
            progress_callback(0.1)
        
        df = self._load_file(input_file)
        
        if progress_callback:
            progress_callback(0.2)
        
        # 2. 执行计算图
        results = {}
        total_nodes = len(self.execution_order)
        
        for i, node_id in enumerate(self.execution_order):
            node = self.nodes[node_id]
            node_config = self.graph['nodes'][node_id]
            
            # 获取输入
            if node_config['type'] == 'source':
                input_df = df
            else:
                input_df = self._get_node_input(node_id, results, df)
            
            # 执行处理
            output_df = node.process(input_df)
            results[node_id] = output_df
            
            # 更新进度
            if progress_callback:
                progress = 0.2 + 0.7 * (i + 1) / total_nodes
                progress_callback(progress)
        
        # 3. 保存输出
        if progress_callback:
            progress_callback(0.9)
        
        output_files = self._save_outputs(results, output_dir)
        
        if progress_callback:
            progress_callback(1.0)
        
        return output_files
    
    def _load_file(self, filepath):
        """
        加载文件
        
        Returns:
            pd.DataFrame
        """
        ext = os.path.splitext(filepath)[1].lower()
        
        if ext == '.bin':
            return self._load_bin_file(filepath)
        elif ext == '.csv':
            return pd.read_csv(filepath)
        else:
            raise ValueError(f"Unsupported file format: {ext}")
    
    def _load_bin_file(self, filepath):
        """加载.bin二进制文件"""
        with open(filepath, 'rb') as f:
            # 读取文件头
            header = f.read(128)
            magic, version, header_len, channel_count, sampling_rate, \
                start_time, total_samples, device_id, _ = struct.unpack(
                    '<8sHHIIfQ64s28s', header
                )
            
            # 验证
            if magic != b'EEGFILE\0':
                raise ValueError("Invalid EEG file")

            # 读取元信息区
            meta_len_bytes = f.read(4)
            if len(meta_len_bytes) == 4:
                meta_len = struct.unpack('<I', meta_len_bytes)[0]
                if meta_len > 0:
                    _ = f.read(meta_len)
            
            # 读取所有数据块
            all_data = []
            timestamps = []
            
            while True:
                # 读取数据帧头
                frame_header = f.read(20)
                if len(frame_header) < 20:
                    break
                
                magic, ver, frame_type, frame_header_len, reserved, sample_count, timestamp = \
                    struct.unpack('<4sBBHHHd', frame_header)
                
                if magic != b'EEGW':
                    break
                
                # 读取剩余帧数据
                samples_per_frame = sample_count
                
                frame_data = np.zeros((channel_count, samples_per_frame))
                for s in range(samples_per_frame):
                    for ch in range(channel_count):
                        value_bytes = f.read(4)
                        if len(value_bytes) < 4:
                            break
                        frame_data[ch, s] = struct.unpack('<f', value_bytes)[0]
                    
                    # 计算时间戳
                    ts = timestamp + s / sampling_rate
                    timestamps.append(ts)
                
                all_data.append(frame_data)
            
            # 合并所有帧
            data_array = np.concatenate(all_data, axis=1)  # (channels, total_samples)
            
            # 转换为DataFrame
            df = pd.DataFrame(
                data_array.T,
                columns=[f'CH{i}' for i in range(channel_count)]
            )
            df.insert(0, 'timestamp', timestamps)
            
            return df
    
    def _save_outputs(self, results, output_dir):
        """保存输出节点的结果"""
        os.makedirs(output_dir, exist_ok=True)
        
        output_files = {}
        
        for node_id, df in results.items():
            node_config = self.graph['nodes'][node_id]
            
            if node_config['type'] == 'save':
                # 获取保存配置
                filename = node_config['config'].get('filename', node_id)
                format = node_config['config'].get('format', 'csv')
                
                filepath = os.path.join(output_dir, f"{filename}.{format}")
                
                if format == 'csv':
                    df.to_csv(filepath, index=False)
                
                output_files[node_id] = filepath
        
        return output_files
    
    def _create_stateless_node(self, node_config):
        """
        创建无状态节点（批处理专用）
        
        批处理中的滤波器不需要维护状态，直接对全量数据应用
        """
        node_type = node_config['type']
        
        if node_type == 'highpass':
            return BatchHighpassFilterNode(
                cutoff=node_config['config']['cutoff'],
                order=node_config['config'].get('order', 4),
                sampling_rate=self.sampling_rate
            )
        # ... 其他节点
```

#### 3.3.2 批处理专用滤波器节点

```python
# core/nodes/batch_filters.py
from scipy import signal
import pandas as pd

class BatchHighpassFilterNode:
    """批处理高通滤波器（无状态）"""
    
    def __init__(self, cutoff, order, sampling_rate):
        self.cutoff = cutoff
        self.order = order
        self.sampling_rate = sampling_rate
        
        # 设计滤波器
        self.sos = signal.butter(
            order, cutoff, 'high',
            fs=sampling_rate, output='sos'
        )
    
    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        处理全量数据
        
        批处理模式下，直接对整列数据应用滤波，无需维护状态
        """
        output_df = df[['timestamp']].copy()
        
        for col in df.columns:
            if col == 'timestamp':
                continue
            
            # 一次性滤波全部数据
            filtered = signal.sosfiltfilt(
                self.sos,
                df[col].values
            )
            
            new_col = f"{col}-HP{self.cutoff}Hz"
            output_df[new_col] = filtered
        
        return output_df
```

**注意**：
- 实时模式使用 `sosfilt`（有状态，逐块处理）
- 批处理模式使用 `sosfiltfilt`（零相位，全量处理）

### 3.4 批处理任务管理

```python
# processing/batch/task_manager.py
from celery import Celery
import os

app = Celery('batch_tasks', broker='redis://localhost:6379/0')

@app.task(bind=True)
def process_batch_task(self, graph_id, input_file, output_dir):
    """
    批处理任务（Celery异步任务）
    
    Args:
        graph_id: 计算图ID
        input_file: 输入文件路径
        output_dir: 输出目录
    """
    # 加载计算图
    graph = ComputeGraph.objects.get(id=graph_id)
    
    # 创建处理器
    processor = BatchProcessor(
        graph_config=graph.graph,
        sampling_rate=250  # 从文件读取
    )
    
    # 进度回调
    def progress_callback(progress):
        self.update_state(
            state='PROCESSING',
            meta={'progress': progress}
        )
    
    # 执行处理
    try:
        output_files = processor.process_file(
            input_file,
            output_dir,
            progress_callback
        )
        
        return {
            'status': 'completed',
            'output_files': output_files
        }
    
    except Exception as e:
        return {
            'status': 'error',
            'message': str(e)
        }
```

### 3.5 分块处理（大文件优化）

```python
# processing/batch/chunked_processor.py

class ChunkedBatchProcessor(BatchProcessor):
    """分块批处理器（处理超大文件）"""
    
    def __init__(self, graph_config, sampling_rate, chunk_size=10000):
        """
        Args:
            chunk_size: 每次处理的样本数
        """
        super().__init__(graph_config, sampling_rate)
        self.chunk_size = chunk_size
    
    def process_file(self, input_file, output_dir, progress_callback=None):
        """分块处理文件"""
        # 1. 获取文件总大小
        total_samples = self._get_file_size(input_file)
        
        # 2. 初始化输出文件
        output_files = self._init_output_files(output_dir)
        
        # 3. 分块读取和处理
        chunks_count = (total_samples + self.chunk_size - 1) // self.chunk_size
        
        for i, chunk_df in enumerate(self._read_chunks(input_file)):
            # 执行计算图
            results = self._process_chunk_through_graph(chunk_df)
            
            # 追加到输出文件
            self._append_results(results, output_files)
            
            # 更新进度
            if progress_callback:
                progress = (i + 1) / chunks_count
                progress_callback(progress)
        
        return output_files
    
    def _read_chunks(self, filepath):
        """生成器：逐块读取文件"""
        if filepath.endswith('.csv'):
            # CSV分块读取
            for chunk in pd.read_csv(filepath, chunksize=self.chunk_size):
                yield chunk
        
        elif filepath.endswith('.bin'):
            # 二进制文件分块读取
            # 实现类似_load_eeg_file，但用生成器
            pass
```

---

## 4. 模式选择与切换

### 4.1 执行控制器

```python
# processing/controller.py

class ExecutionController:
    """执行控制器：统一管理实时和批处理"""
    
    def __init__(self, execution_id):
        self.execution_id = execution_id
        self.execution = GraphExecution.objects.get(id=execution_id)
        self.processor = None
    
    def start(self):
        """启动执行"""
        if self.execution.mode == 'realtime':
            self._start_realtime()
        elif self.execution.mode == 'batch':
            self._start_batch()
    
    def stop(self):
        """停止执行"""
        if self.processor:
            if isinstance(self.processor, RealtimeProcessor):
                self.processor.stop()
            # 批处理任务通过Celery revoke
    
    def _start_realtime(self):
        """启动实时处理"""
        config = self.execution.config
        
        # 创建处理器
        self.processor = RealtimeProcessor(
            graph_config=self.execution.graph.graph,
            sampling_rate=config['sampling_rate'],
            window_duration=config.get('window_duration', 2.0)
        )
        
        # 启动
        self.processor.start()
        
        # 连接数据源
        device_id = config['data_source']['id']
        self._connect_device(device_id)
    
    def _start_batch(self):
        """启动批处理"""
        config = self.execution.config
        
        # 提交Celery任务
        task = process_batch_task.apply_async(
            args=[
                self.execution.graph.id,
                config['input_file'],
                config['output_dir']
            ]
        )
        
        # 保存任务ID
        self.execution.task_id = task.id
        self.execution.save()
    
    def _connect_device(self, device_id):
        """连接设备，将数据推送到处理器"""
        device = Device.objects.get(id=device_id)
        
        # 注册数据回调
        def on_data(timestamp, data):
            self.processor.push_data(timestamp, data)
        
        device_manager.register_callback(device_id, on_data)
```

---

## 7. 错误处理与容错

### 7.1 实时模式容错

```python
class RealtimeProcessor:
    def _process_chunk(self, chunk):
        try:
            # 正常处理
            return self._process_chunk_impl(chunk)
        
        except Exception as e:
            # 记录错误
            logger.error(f"Chunk processing error: {e}")
            
            # 尝试恢复
            if self._is_recoverable(e):
                self._reset_node_states()
                return self._process_chunk_impl(chunk)
            else:
                # 通知前端
                self._send_error_notification(e)
                raise
    
    def _reset_node_states(self):
        """重置所有节点状态"""
        for node in self.nodes.values():
            if hasattr(node, 'reset'):
                node.reset()
```

### 7.2 批处理模式容错

```python
class BatchProcessor:
    def process_file(self, input_file, output_dir, progress_callback=None):
        try:
            return self._process_file_impl(
                input_file, output_dir, progress_callback
            )
        
        except Exception as e:
            # 保存中间结果
            self._save_partial_results(output_dir)
            
            # 记录错误信息
            error_log = os.path.join(output_dir, 'error.log')
            with open(error_log, 'w') as f:
                f.write(f"Error: {e}\n")
                f.write(traceback.format_exc())
            
            raise
```

---

## 9. 部署建议

### 9.1 实时模式部署

```yaml
# docker-compose.yml
services:
  django:
    image: eeg-backend:latest
    environment:
      - MODE=realtime
      - MAX_DEVICES=20
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
```

### 9.2 批处理模式部署

```yaml
services:
  celery-worker:
    image: eeg-backend:latest
    command: celery -A backend worker -Q batch_processing
    environment:
      - MODE=batch
    deploy:
      replicas: 4
      resources:
        limits:
          cpus: '4'
          memory: 4G
  
  redis:
    image: redis:alpine
```

---

## 10. 总结对照表

| 维度 | 实时模式 | 批处理模式 |
|------|---------|-----------|
| **数据流** | 流式处理 | 全量加载 |
| **状态管理** | 有状态（滤波器zi） | 无状态 |
| **内存模式** | 固定窗口 | 可变大小 |
| **滤波方式** | sosfilt（有状态） | sosfiltfilt（零相位） |
| **并发模型** | 线程+队列 | 进程池+任务队列 |
| **输出方式** | WebSocket推送 | 文件写入 |
| **错误恢复** | 重置状态继续 | 保存中间结果 |
| **扩展方式** | 水平扩展（多设备） | 垂直扩展（多核） |

---

本文档提供了实时和离线两种处理模式的完整实现指导，包括核心代码框架。