# 接口设计详细规范

## 1. REST API 设计

### 1.1 设备管理 API

#### 1.1.1 获取设备列表
```http
GET /api/devices/
```

**响应示例：**
```json
{
  "code": 0,
  "message": "success",
  "data": [
    {
      "id": "device-001",
      "name": "实验设备1",
      "alias": "Fp设备",
      "address": "COM3",
      "type": "physical",
      "status": "connected",
      "battery": 85,
      "sampling_rate": 250,
      "channel_count": 8,
      "channels": [
        {
          "index": 0,
          "alias": "Fp1",
          "unit": "uV",
          "impedance": 12.3,
          "impedance_status": "good"
        }
      ],
      "created_at": "2026-02-07T10:30:00Z",
      "updated_at": "2026-02-07T12:45:00Z"
    }
  ]
}
```

#### 1.1.2 创建设备
```http
POST /api/devices/
Content-Type: application/json
```

**请求体：**
```json
{
  "type": "simulated",
  "name": "测试信号源",
  "alias": "Test-1",
  "address": "SIM-001",
  "sampling_rate": 250,
  "channel_count": 8,
  "config": {
    "channels": [
      {
        "index": 0,
        "wave_type": "sine",
        "frequency": 10,
        "amplitude": 100,
        "alias": "CH1"
      },
      {
        "index": 1,
        "wave_type": "square",
        "frequency": 5,
        "amplitude": 50,
        "alias": "CH2"
      }
    ]
  }
}
```

**响应：**
```json
{
  "code": 0,
  "message": "Device created successfully",
  "data": {
    "id": "device-002",
    "name": "测试信号源",
    "status": "ready"
  }
}
```

#### 1.1.3 更新设备配置
```http
PATCH /api/devices/{device_id}/
Content-Type: application/json
```

**请求体：**
```json
{
  "alias": "新设备名",
  "channels": [
    {
      "index": 0,
      "alias": "Fp1-Left"
    }
  ]
}
```

#### 1.1.4 删除设备
```http
DELETE /api/devices/{device_id}/
```

**响应：**
```json
{
  "code": 0,
  "message": "Device deleted successfully"
}
```

#### 1.1.5 获取设备阻抗
```http
GET /api/devices/{device_id}/impedance/
```

**响应：**
```json
{
  "code": 0,
  "data": {
    "device_id": "device-001",
    "timestamp": "2026-02-07T12:45:30Z",
    "impedances": [
      {"channel": 0, "value": 12.3, "status": "good"},
      {"channel": 1, "value": 45.6, "status": "warning"},
      {"channel": 2, "value": 120.5, "status": "bad"}
    ]
  }
}
```

**阻抗状态标准：**
- `good`: < 20 kΩ
- `warning`: 20-50 kΩ
- `bad`: > 50 kΩ

---

### 1.2 录制管理 API

#### 1.2.1 开始录制
```http
POST /api/recording/start/
Content-Type: application/json
```

**请求体：**
```json
{
  "device_id": "device-001",
  "filename": "experiment_2026_02_07",
  "channels": [0, 1, 2, 3],  // 可选，默认全部通道
  "metadata": {
    "subject_id": "S001",
    "session": "baseline",
    "notes": "测试录制"
  }
}
```

**响应：**
```json
{
  "code": 0,
  "message": "Recording started",
  "data": {
    "recording_id": "rec-20260207-001",
    "device_id": "device-001",
    "start_time": "2026-02-07T12:50:00Z",
    "file_path": "/data/recordings/experiment_2026_02_07.bin"
  }
}
```

#### 1.2.2 停止录制
```http
POST /api/recording/stop/
Content-Type: application/json
```

**请求体：**
```json
{
  "recording_id": "rec-20260207-001"
}
```

**响应：**
```json
{
  "code": 0,
  "message": "Recording stopped",
  "data": {
    "recording_id": "rec-20260207-001",
    "duration": 120.5,
    "samples": 30125,
    "file_size": 964000,
    "file_path": "/data/recordings/experiment_2026_02_07.bin"
  }
}
```

#### 1.2.3 获取录制列表
```http
GET /api/recordings/?device_id={device_id}&limit=20&offset=0
```

**响应：**
```json
{
  "code": 0,
  "data": {
    "total": 45,
    "recordings": [
      {
        "id": "rec-20260207-001",
        "device_id": "device-001",
        "filename": "experiment_2026_02_07",
        "start_time": "2026-02-07T12:50:00Z",
        "duration": 120.5,
        "file_size": 964000,
        "metadata": {
          "subject_id": "S001",
          "session": "baseline"
        }
      }
    ]
  }
}
```

#### 1.2.4 导出录制数据
```http
POST /api/recordings/{recording_id}/export/
Content-Type: application/json
```

**请求体：**
```json
{
  "format": "csv",  // csv | mat | edf
  "channels": [0, 1, 2],  // 可选
  "time_range": {  // 可选
    "start": 10.0,
    "end": 60.0
  }
}
```

**响应：**
```json
{
  "code": 0,
  "message": "Export task created",
  "data": {
    "task_id": "export-001",
    "status": "processing",
    "download_url": null
  }
}
```

#### 1.2.5 查询导出任务状态
```http
GET /api/recordings/export/{task_id}/
```

**响应：**
```json
{
  "code": 0,
  "data": {
    "task_id": "export-001",
    "status": "completed",
    "progress": 100,
    "download_url": "/downloads/experiment_2026_02_07.csv",
    "file_size": 524288,
    "expires_at": "2026-02-08T12:50:00Z"
  }
}
```

---

### 1.3 计算图 API

#### 1.3.1 保存计算图
```http
POST /api/graphs/
Content-Type: application/json
```

**请求体：**
```json
{
  "name": "高通滤波流程",
  "description": "0.5Hz高通滤波后显示",
  "graph": {
    "nodes": [
      {
        "id": "source-1",
        "type": "source",
        "position": {"x": 100, "y": 100},
        "config": {
          "source_type": "device",
          "device_id": "device-001",
          "channels": [0, 1, 2, 3]
        }
      },
      {
        "id": "filter-1",
        "type": "highpass",
        "position": {"x": 300, "y": 100},
        "config": {
          "cutoff": 0.5,
          "order": 4
        }
      },
      {
        "id": "scope-1",
        "type": "scope",
        "position": {"x": 500, "y": 100},
        "config": {
          "window_size": 10.0
        }
      }
    ],
    "edges": [
      {
        "id": "edge-1",
        "source": "source-1",
        "target": "filter-1"
      },
      {
        "id": "edge-2",
        "source": "filter-1",
        "target": "scope-1"
      }
    ]
  }
}
```

**响应：**
```json
{
  "code": 0,
  "message": "Graph saved",
  "data": {
    "graph_id": "graph-001",
    "name": "高通滤波流程",
    "version": 1,
    "created_at": "2026-02-07T13:00:00Z"
  }
}
```

#### 1.3.2 获取计算图列表
```http
GET /api/graphs/
```

#### 1.3.3 加载计算图
```http
GET /api/graphs/{graph_id}/
```

#### 1.3.4 执行计算图
```http
POST /api/graphs/{graph_id}/execute/
Content-Type: application/json
```

**请求体：**
```json
{
  "mode": "realtime",  // realtime | batch
  "config": {
    "data_source": {
      "type": "device",  // realtime模式必填
      "id": "device-001"
    }
  }
}
```

**批处理模式请求体：**
```json
{
  "mode": "batch",
  "config": {
    "input_file": "/data/recordings/experiment_2026_02_07.bin",
    "output_dir": "/data/exports",
    "time_range": {
      "start": 0.0,
      "end": 120.0
    }
  }
}
```

**响应：**
```json
{
  "code": 0,
  "message": "Graph execution started",
  "data": {
    "execution_id": "exec-001",
    "graph_id": "graph-001",
    "mode": "realtime",
    "status": "running",
    "websocket_url": "ws://localhost:8000/ws/graph/exec-001/"
  }
}
```

#### 1.3.5 停止计算图执行
```http
POST /api/graphs/executions/{execution_id}/stop/
```

#### 1.3.6 获取节点数据
```http
GET /api/graphs/executions/{execution_id}/nodes/{node_id}/data/
```

**查询参数：**
- `time_range`: 时间范围，格式 `start,end`
- `format`: 返回格式 `json | csv`

**响应：**
```json
{
  "code": 0,
  "data": {
    "node_id": "filter-1",
    "columns": ["timestamp", "COM3-Fp1-filter-1", "COM3-Fp2-filter-1"],
    "data": [
      [1700000000.000, 1.23, 2.34],
      [1700000000.004, 1.45, 2.56]
    ],
    "metadata": {
      "sampling_rate": 250,
      "unit": "uV"
    }
  }
}
```

---

## 2. WebSocket 协议设计

### 2.1 连接建立

#### 2.1.1 实时数据流连接
```
ws://localhost:8000/ws/device/{device_id}/
```

**URL参数：**
- `device_id`: 设备ID

#### 2.1.2 计算图执行连接
```
ws://localhost:8000/ws/graph/{execution_id}/
```

**URL参数：**
- `execution_id`: 执行ID

### 2.2 消息格式

所有WebSocket消息使用以下格式封装：

```json
{
  "type": "message_type",
  "timestamp": 1700000000.123,
  "data": {}
}
```

### 2.3 元信息包（Meta Message）

**连接建立后后端首先发送（字段统一使用 snake_case）：**

```json
{
  "type": "meta",
  "timestamp": 1700000000.000,
  "data": {
    "device_id": "device-001",
    "sampling_rate": 250,
    "channel_count": 8,
    "channels": [
      {
        "index": 0,
        "name": "COM3-Fp1",
        "unit": "uV",
        "scale": 1.0
      }
    ],
    "binary_config": {
      "wave_magic": "EEGW",
      "spectrum_magic": "EEGS",
      "wave_header_len": 24,
      "wave_sample_count": 25,
      "spectrum_header_len": 24,
      "spectrum_bin_count": 129
    }
  }
}
```

### 2.4 二进制数据帧设计

#### 2.4.1 时域数据帧（Wave Frame）

**帧结构：**

| 字段 | 类型 | 字节数 | 说明 |
|------|------|--------|------|
| magic | char[4] | 4 | 'EEGW' (0x45454757) |
| version | uint8 | 1 | 版本号，当前为1 |
| frameType | uint8 | 1 | 0x01=wave |
| headerLen | uint16 | 2 | 帧头长度=24 |
| reserved | uint16 | 2 | 保留字段 |
| sampleCount | uint16 | 2 | 本帧样本数 |
| deviceId | uint32 | 4 | 设备ID（数值型） |
| timestamp | float64 | 8 | 时间戳（秒） |
| payload | float32[] | N×C×4 | N个样本×C个通道 |

**总长度：** 24 + (样本数 × 通道数 × 4) 字节

**前端解析示例（JavaScript）：**

```javascript
function parseWaveFrame(buffer) {
  const view = new DataView(buffer);
  let offset = 0;
  
  // 解析帧头
  const magic = String.fromCharCode(
    view.getUint8(offset++),
    view.getUint8(offset++),
    view.getUint8(offset++),
    view.getUint8(offset++)
  );
  
  if (magic !== 'EEGW') {
    throw new Error('Invalid wave frame magic');
  }
  
  const version = view.getUint8(offset++);
  const frameType = view.getUint8(offset++);
  const headerLen = view.getUint16(offset, true); offset += 2;
  const reserved = view.getUint16(offset, true); offset += 2;
  const sampleCount = view.getUint16(offset, true); offset += 2;
  const deviceId = view.getUint32(offset, true); offset += 4;
  const timestamp = view.getFloat64(offset, true); offset += 8;
  
  // 解析数据
  const payloadLength = buffer.byteLength - headerLen;
  if (payloadLength !== sampleCount * channelCount * 4) {
    throw new Error('Invalid payload length');
  }
  
  const data = new Array(channelCount);
  for (let ch = 0; ch < channelCount; ch++) {
    data[ch] = new Float32Array(sampleCount);
  }
  
  for (let i = 0; i < sampleCount; i++) {
    for (let ch = 0; ch < channelCount; ch++) {
      data[ch][i] = view.getFloat32(offset, true);
      offset += 4;
    }
  }
  
  return {
    deviceId,
    timestamp,
    sampleCount,
    data
  };
}
```

#### 2.4.2 频域数据帧（Spectrum Frame）

**帧结构：**

| 字段 | 类型 | 字节数 | 说明 |
|------|------|--------|------|
| magic | char[4] | 4 | 'EEGS' (0x45454753) |
| version | uint8 | 1 | 版本号，当前为1 |
| frameType | uint8 | 1 | 0x02=spectrum |
| headerLen | uint16 | 2 | 帧头长度=24 |
| reserved | uint16 | 2 | 保留字段 |
| binCount | uint16 | 2 | 频点数量 |
| deviceId | uint32 | 4 | 设备ID |
| timestamp | float64 | 8 | 时间戳 |
| payload | float32[] | M×C×4 | M个频点×C个通道 |

**频率计算：**
```javascript
const freqs = Array.from(
  {length: binCount},
  (_, i) => i * samplingRate / (2 * binCount)
);
```

### 2.5 控制消息（JSON）

#### 2.5.1 前端→后端：订阅通道

```json
{
  "type": "subscribe",
  "data": {
    "channels": [0, 1, 2],
    "data_types": ["wave", "spectrum"]
  }
}
```

#### 2.5.2 前端→后端：录制控制

```json
{
  "type": "record",
  "data": {
    "action": "start",
    "filename": "test_recording",
    "channels": [0, 1, 2, 3]
  }
}
```

```json
{
  "type": "record",
  "data": {
    "action": "stop"
  }
}
```

#### 2.5.3 后端→前端：录制状态

```json
{
  "type": "record_status",
  "timestamp": 1700000000.000,
  "data": {
    "recording": true,
    "duration": 45.2,
    "samples": 11300,
    "file_size": 361600
  }
}
```

#### 2.5.4 后端→前端：错误消息

```json
{
  "type": "error",
  "timestamp": 1700000000.000,
  "data": {
    "code": "DEVICE_DISCONNECTED",
    "message": "设备连接丢失",
    "severity": "error"
  }
}
```

#### 2.5.5 心跳检测

**前端→后端：**
```json
{
  "type": "ping",
  "timestamp": 1700000000.000
}
```

**后端→前端：**
```json
{
  "type": "pong",
  "timestamp": 1700000000.000
}
```

**策略：**
- 前端每30秒发送ping
- 后端60秒未收到任何消息则断开连接
- 前端60秒未收到任何消息则重连

---

## 3. 数据模型设计

### 3.1 后端数据库模型（Django ORM）

#### 3.1.1 Device Model

```python
from django.db import models
from django.contrib.postgres.fields import JSONField

class Device(models.Model):
    TYPE_CHOICES = [
        ('physical', 'Physical Device'),
        ('simulated', 'Simulated Device'),
    ]
    
    STATUS_CHOICES = [
        ('disconnected', 'Disconnected'),
        ('connected', 'Connected'),
        ('error', 'Error'),
    ]
    
    id = models.CharField(max_length=64, primary_key=True)
    name = models.CharField(max_length=255)
    alias = models.CharField(max_length=255, blank=True)
    address = models.CharField(max_length=255)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    battery = models.IntegerField(default=100)
    sampling_rate = models.IntegerField(default=250)
    channel_count = models.IntegerField(default=8)
    config = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'devices'
        ordering = ['-created_at']

class Channel(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='channels')
    index = models.IntegerField()
    alias = models.CharField(max_length=64)
    unit = models.CharField(max_length=16, default='uV')
    impedance = models.FloatField(null=True, blank=True)
    config = models.JSONField(default=dict)
    
    class Meta:
        db_table = 'channels'
        unique_together = ['device', 'index']
        ordering = ['index']
```

#### 3.1.2 Recording Model

```python
class Recording(models.Model):
    id = models.CharField(max_length=64, primary_key=True)
    device = models.ForeignKey(Device, on_delete=models.CASCADE)
    filename = models.CharField(max_length=255)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    duration = models.FloatField(null=True, blank=True)
    samples = models.BigIntegerField(default=0)
    file_path = models.CharField(max_length=512)
    file_size = models.BigIntegerField(default=0)
    metadata = models.JSONField(default=dict)
    
    class Meta:
        db_table = 'recordings'
        ordering = ['-start_time']
```

#### 3.1.3 ComputeGraph Model

```python
class ComputeGraph(models.Model):
    id = models.CharField(max_length=64, primary_key=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    graph = models.JSONField()
    version = models.IntegerField(default=1)
    is_frozen = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'compute_graphs'
        ordering = ['-created_at']

class GraphExecution(models.Model):
    MODE_CHOICES = [
        ('realtime', 'Real-time'),
        ('batch', 'Batch Processing'),
    ]
    
    STATUS_CHOICES = [
        ('running', 'Running'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
        ('error', 'Error'),
    ]
    
    id = models.CharField(max_length=64, primary_key=True)
    graph = models.ForeignKey(ComputeGraph, on_delete=models.CASCADE)
    mode = models.CharField(max_length=20, choices=MODE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    config = models.JSONField()
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'graph_executions'
```

### 3.2 前端状态管理（Pinia Store）

#### 3.2.1 Device Store

```typescript
// stores/device.ts
import { defineStore } from 'pinia'

export interface Channel {
  index: number
  alias: string
  unit: string
  impedance: number | null
  impedanceStatus: 'good' | 'warning' | 'bad'
}

export interface Device {
  id: string
  name: string
  alias: string
  address: string
  type: 'physical' | 'simulated'
  status: 'connected' | 'disconnected' | 'error'
  battery: number
  samplingRate: number
  channelCount: number
  channels: Channel[]
  createdAt: string
  updatedAt: string
}

export const useDeviceStore = defineStore('device', {
  state: () => ({
    devices: [] as Device[],
    selectedDeviceId: null as string | null,
    loading: false,
    error: null as string | null
  }),
  
  getters: {
    selectedDevice: (state) => 
      state.devices.find(d => d.id === state.selectedDeviceId),
    
    connectedDevices: (state) =>
      state.devices.filter(d => d.status === 'connected')
  },
  
  actions: {
    async fetchDevices() {
      this.loading = true
      try {
        const response = await fetch('/api/devices/')
        const result = await response.json()
        this.devices = result.data
      } catch (error) {
        this.error = error.message
      } finally {
        this.loading = false
      }
    },
    
    async createDevice(deviceData: Partial<Device>) {
      const response = await fetch('/api/devices/', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(deviceData)
      })
      const result = await response.json()
      await this.fetchDevices()
      return result.data
    },
    
    updateChannelImpedance(deviceId: string, channelIndex: number, impedance: number) {
      const device = this.devices.find(d => d.id === deviceId)
      if (device) {
        const channel = device.channels.find(c => c.index === channelIndex)
        if (channel) {
          channel.impedance = impedance
          channel.impedanceStatus = impedance < 20 ? 'good' : 
                                    impedance < 50 ? 'warning' : 'bad'
        }
      }
    }
  }
})
```

#### 3.2.2 Recording Store

```typescript
// stores/recording.ts
export interface Recording {
  id: string
  deviceId: string
  filename: string
  startTime: string
  duration: number | null
  samples: number
  fileSize: number
  metadata: Record<string, any>
}

export const useRecordingStore = defineStore('recording', {
  state: () => ({
    recordings: [] as Recording[],
    currentRecording: null as Recording | null,
    isRecording: false
  }),
  
  actions: {
    async startRecording(deviceId: string, filename: string, metadata?: any) {
      const response = await fetch('/api/recording/start/', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({device_id: deviceId, filename, metadata})
      })
      const result = await response.json()
      this.currentRecording = result.data
      this.isRecording = true
      return result.data
    },
    
    async stopRecording() {
      if (!this.currentRecording) return
      
      const response = await fetch('/api/recording/stop/', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({recording_id: this.currentRecording.id})
      })
      const result = await response.json()
      this.isRecording = false
      this.currentRecording = null
      await this.fetchRecordings()
      return result.data
    }
  }
})
```

#### 3.2.3 Graph Store

```typescript
// stores/graph.ts
export interface GraphNode {
  id: string
  type: string
  position: {x: number, y: number}
  config: Record<string, any>
}

export interface GraphEdge {
  id: string
  source: string
  target: string
}

export interface ComputeGraph {
  id?: string
  name: string
  description?: string
  graph: {
    nodes: GraphNode[]
    edges: GraphEdge[]
  }
  isFrozen: boolean
}

export const useGraphStore = defineStore('graph', {
  state: () => ({
    graphs: [] as ComputeGraph[],
    currentGraph: null as ComputeGraph | null,
    currentExecution: null as any
  }),
  
  actions: {
    async saveGraph(graph: ComputeGraph) {
      const response = await fetch('/api/graphs/', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(graph)
      })
      return await response.json()
    },
    
    async executeGraph(graphId: string, mode: 'realtime' | 'batch', config: any) {
      const response = await fetch(`/api/graphs/${graphId}/execute/`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({mode, config})
      })
      const result = await response.json()
      this.currentExecution = result.data
      return result.data
    }
  }
})
```

---

## 4. 数据处理流程设计

### 4.1 后端数据处理管道

```python
# processing/pipeline.py
import pandas as pd
import numpy as np
from scipy import signal

class DataPipeline:
    def __init__(self, graph_config, sampling_rate):
        self.graph = graph_config
        self.sampling_rate = sampling_rate
        self.nodes = {}
        self.buffers = {}
        
    def build(self):
        """构建计算图执行顺序"""
        # 拓扑排序
        sorted_nodes = self._topological_sort()
        
        for node_id in sorted_nodes:
            node = self.graph['nodes'][node_id]
            self.nodes[node_id] = self._create_node(node)
            
    def process_chunk(self, data_chunk: pd.DataFrame):
        """处理一个数据块"""
        results = {}
        
        for node_id, node in self.nodes.items():
            # 获取输入数据
            inputs = self._get_node_inputs(node_id, results, data_chunk)
            
            # 执行节点
            output = node.process(inputs)
            results[node_id] = output
            
            # 更新输出buffer
            if node.is_output_node():
                self.buffers[node_id] = output
                
        return results
        
    def _create_node(self, node_config):
        node_type = node_config['type']
        
        if node_type == 'highpass':
            return HighpassNode(
                cutoff=node_config['config']['cutoff'],
                order=node_config['config'].get('order', 4),
                sampling_rate=self.sampling_rate
            )
        elif node_type == 'lowpass':
            return LowpassNode(...)
        # ... 其他节点类型
        
class HighpassNode:
    def __init__(self, cutoff, order, sampling_rate):
        self.cutoff = cutoff
        self.order = order
        self.sampling_rate = sampling_rate
        self.sos = signal.butter(
            order, cutoff, 'high', 
            fs=sampling_rate, output='sos'
        )
        self.zi = None
        
    def process(self, input_df: pd.DataFrame) -> pd.DataFrame:
        """处理输入数据"""
        output_df = input_df.copy()
        
        for col in input_df.columns:
            if col == 'timestamp':
                continue
                
            if self.zi is None:
                # 初始化滤波器状态
                self.zi = signal.sosfilt_zi(self.sos) * input_df[col].iloc[0]
                
            # 应用滤波器
            filtered, self.zi = signal.sosfilt(
                self.sos, input_df[col].values, zi=self.zi
            )
            
            # 更新列名
            new_col_name = f"{col}-highpass-{self.cutoff}Hz"
            output_df.rename(columns={col: new_col_name}, inplace=True)
            output_df[new_col_name] = filtered
            
        return output_df
```

### 4.2 前端数据流管理

```typescript
// composables/useDataStream.ts
import { ref, onMounted, onUnmounted } from 'vue'

export function useDataStream(deviceId: string) {
  const ws = ref<WebSocket | null>(null)
  const connected = ref(false)
  const metadata = ref<any>(null)
  const dataBuffer = ref<Float32Array[]>([])
  
  const connect = () => {
    ws.value = new WebSocket(`ws://localhost:8000/ws/device/${deviceId}/`)
    
    ws.value.onopen = () => {
      connected.value = true
      console.log('WebSocket connected')
    }
    
    ws.value.onmessage = (event) => {
      if (typeof event.data === 'string') {
        // JSON消息
        const message = JSON.parse(event.data)
        handleJsonMessage(message)
      } else {
        // 二进制消息
        handleBinaryMessage(event.data)
      }
    }
    
    ws.value.onerror = (error) => {
      console.error('WebSocket error:', error)
    }
    
    ws.value.onclose = () => {
      connected.value = false
      console.log('WebSocket disconnected')
      // 自动重连
      setTimeout(connect, 3000)
    }
  }
  
  const handleJsonMessage = (message: any) => {
    if (message.type === 'meta') {
      metadata.value = message.data
      // 初始化数据缓冲区
      const channelCount = message.data.channel_count
      dataBuffer.value = Array.from(
        {length: channelCount},
        () => new Float32Array(0)
      )
    }
  }
  
  const handleBinaryMessage = (data: ArrayBuffer) => {
    const frame = parseWaveFrame(data, metadata.value.channel_count)
    
    // 追加到缓冲区
    for (let ch = 0; ch < frame.data.length; ch++) {
      const oldBuffer = dataBuffer.value[ch]
      const newBuffer = new Float32Array(
        oldBuffer.length + frame.data[ch].length
      )
      newBuffer.set(oldBuffer)
      newBuffer.set(frame.data[ch], oldBuffer.length)
      dataBuffer.value[ch] = newBuffer
    }
    
    // 触发更新
    onDataUpdate(frame)
  }
  
  const subscribe = (channels: number[], dataTypes: string[]) => {
    if (ws.value && connected.value) {
      ws.value.send(JSON.stringify({
        type: 'subscribe',
        data: {channels, data_types: dataTypes}
      }))
    }
  }
  
  onMounted(() => {
    connect()
  })
  
  onUnmounted(() => {
    if (ws.value) {
      ws.value.close()
    }
  })
  
  return {
    connected,
    metadata,
    dataBuffer,
    subscribe
  }
}
```

---

## 5. 文件格式规范

### 5.1 二进制录制文件格式

**文件扩展名：** `.bin`

**文件结构：**

```
[文件头]
[数据块1]
[数据块2]
...
[数据块N]
```

**文件头（128字节）：**

| 偏移 | 类型 | 字节 | 说明 |
|------|------|------|------|
| 0 | char[8] | 8 | 魔数 'EEGFILE\0' |
| 8 | uint16 | 2 | 版本号 |
| 10 | uint16 | 2 | 头部长度 |
| 12 | uint32 | 4 | 通道数 |
| 16 | uint32 | 4 | 采样率 |
| 20 | float64 | 8 | 开始时间戳 |
| 28 | uint64 | 8 | 总样本数 |
| 36 | char[64] | 64 | 设备ID |
| 100 | char[28] | 28 | 保留 |

**元信息区（可选，可变长）：**

紧随文件头之后追加元信息块，用于保存录制上下文。

| 字段 | 类型 | 字节 | 说明 |
|------|------|------|------|
| metaLen | uint32 | 4 | 元信息JSON字节长度 |
| metaJson | bytes | metaLen | UTF-8 JSON字符串 |

**建议元信息字段：**
- `recording_id`
- `device_id`
- `device_name`
- `sampling_rate`
- `channel_count`
- `channels`（包含index/alias/unit）
- `start_time`
- `notes`

**数据块（变长）：**

数据块帧头字段：

| 字段 | 类型 | 字节 | 说明 |
|------|------|------|------|
| magic | char[4] | 4 | 'EEGW' |
| version | uint8 | 1 | 版本号 |
| frameType | uint8 | 1 | 0x01=wave |
| headerLen | uint16 | 2 | 帧头长度=20 |
| reserved | uint16 | 2 | 保留字段 |
| sampleCount | uint16 | 2 | 本帧样本数 |
| timestamp | float64 | 8 | 时间戳 |

载荷为 float32[]，按样本交错存储（样本数 × 通道数）。

### 5.2 CSV导出格式

**文件头：**
```csv
# EEG Recording Export
# Device: device-001 (实验设备1)
# Start Time: 2026-02-07T12:50:00Z
# Sampling Rate: 250 Hz
# Channels: 8
timestamp,COM3-Fp1,COM3-Fp2,COM3-F3,COM3-F4,COM3-C3,COM3-C4,COM3-P3,COM3-P4
1700000000.000,1.23,2.34,3.45,4.56,5.67,6.78,7.89,8.90
1700000000.004,1.25,2.36,3.47,4.58,5.69,6.80,7.91,8.92
```

---

## 6. 错误处理与状态码

### 6.1 HTTP状态码

- `200 OK`: 成功
- `201 Created`: 资源创建成功
- `400 Bad Request`: 请求参数错误
- `404 Not Found`: 资源不存在
- `409 Conflict`: 资源冲突（如设备已存在）
- `500 Internal Server Error`: 服务器错误

### 6.2 业务错误码

```json
{
  "code": 1001,
  "message": "设备未连接",
  "data": null
}
```

**错误码定义：**

| 错误码 | 说明 |
|--------|------|
| 0 | 成功 |
| 1001 | 设备未连接 |
| 1002 | 设备已存在 |
| 1003 | 通道配置错误 |
| 2001 | 录制已在进行 |
| 2002 | 录制未开始 |
| 2003 | 文件写入失败 |
| 3001 | 计算图格式错误 |
| 3002 | 计算图未冻结 |
| 3003 | 节点配置错误 |
| 3004 | 循环依赖 |
| 9999 | 未知错误 |

---

## 7. 性能优化建议

### 7.1 前端优化

1. **虚拟滚动**：设备列表使用虚拟滚动
2. **数据抽样**：示波器窗口过大时进行数据抽样显示
3. **Web Worker**：数据解析和统计计算在Worker中进行
4. **Canvas优化**：ECharts使用Canvas渲染器

### 7.2 后端优化

1. **批量发送**：累积25个样本（0.1秒@250Hz）后发送一次
2. **缓冲池**：使用对象池减少内存分配
3. **异步I/O**：文件写入使用异步I/O
4. **连接池**：数据库连接池配置

## 8. 安全性考虑

### 8.1 认证与授权
- WebSocket连接需要token验证
- API请求需要CSRF token

### 8.2 数据验证
- 所有输入参数进行类型和范围检查
- 二进制帧验证magic number和checksum

### 8.3 资源限制
- WebSocket最大连接数：100
- 单次录制最大时长：24小时
- 文件上传最大大小：100MB

---

## 附录A：完整示例

### A.1 前端创建模拟设备并订阅数据

```typescript
// 1. 创建设备
const deviceStore = useDeviceStore()
const device = await deviceStore.createDevice({
  type: 'simulated',
  name: '测试信号源',
  alias: 'Test-1',
  address: 'SIM-001',
  sampling_rate: 250,
  channel_count: 8,
  config: {
    channels: [
      {index: 0, wave_type: 'sine', frequency: 10, amplitude: 100}
    ]
  }
})

// 2. 建立WebSocket连接
const {connected, metadata, dataBuffer, subscribe} = useDataStream(device.id)

// 3. 订阅数据
watch(connected, (isConnected) => {
  if (isConnected) {
    subscribe([0, 1, 2, 3], ['wave', 'spectrum'])
  }
})
```

### A.2 后端处理数据并广播

```python
# consumers.py
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
import json
import struct

class DeviceConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.device_id = self.scope['url_route']['kwargs']['device_id']
        await self.channel_layer.group_add(
            f'device_{self.device_id}',
            self.channel_name
        )
        await self.accept()
        
        # 发送元信息
        device = await self.get_device(self.device_id)
        await self.send(text_data=json.dumps({
            'type': 'meta',
            'timestamp': time.time(),
            'data': {
                'device_id': device.id,
                'sampling_rate': device.sampling_rate,
                'channel_count': device.channel_count,
                'channels': [
                    {
                        'index': ch.index,
                        'name': f"{device.address}-{ch.alias}",
                        'unit': ch.unit
                    }
                    for ch in device.channels.all()
                ]
            }
        }))
        
    async def device_data(self, event):
        # 发送二进制数据帧
        await self.send(bytes_data=event['data'])
```