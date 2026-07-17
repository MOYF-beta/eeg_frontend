"""虚拟设备服务器 — 独立运行的 HTTP 服务，模拟外部 EEG 设备硬件。

手动启动：
    python manage.py runserver 8000          # Django 后端
    python virtual_device_server.py           # 虚拟设备服务器（端口 7777）

架构：
    ┌─────────────────┐         HTTP          ┌──────────────────┐
    │  Django 后端     │  ←──────────────────→  │  虚拟设备服务器    │
    │  (simulator_eeg │   localhost:7777       │  5 个虚拟 EEG 设备  │
    │   驱动 = 客户端)  │                       │  (波形生成引擎)     │
    └─────────────────┘                       └──────────────────┘

提供 RESTful API：
    GET    /devices                      — 发现所有设备
    GET    /devices/{device_id}          — 查询单个设备元信息
    POST   /devices/{device_id}/connect  — 建立连接
    POST   /devices/{device_id}/disconnect — 断开连接
    GET    /devices/{device_id}/status   — 查询状态
    POST   /devices/{device_id}/start    — 开始采集
    POST   /devices/{device_id}/stop     — 停止采集
    GET    /devices/{device_id}/data?count=N — 拉取 N 帧数据
    GET    /health                       — 健康检查
"""

from __future__ import annotations

import json
import math
import random
import threading
import time
from collections import deque
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse, parse_qs

HOST = '0.0.0.0'
PORT = 7777

# ---------------------------------------------------------------------- #
#  5 个虚拟设备定义
# ---------------------------------------------------------------------- #
# (device_id, name, channel_count, sample_rate, freqs)
# freqs: 每通道的基频列表（不足则循环），None 表示按通道索引自动递增
_DEVICES_SPEC: List[Tuple[str, str, int, int, Optional[List[float]]]] = [
    ('sim_alpha', 'Alpha 波模拟器 (10Hz)',  8, 250, [10.0]),
    ('sim_beta',  'Beta 波模拟器 (20Hz)',   8, 250, [20.0]),
    ('sim_theta', 'Theta 波模拟器 (6Hz)',   4, 200, [6.0]),
    ('sim_gamma', 'Gamma 波模拟器 (40Hz)',  8, 500, [40.0]),
    ('sim_multi', '多频混合模拟器',          8, 250, None),
]


# ---------------------------------------------------------------------- #
#  单设备状态机
# ---------------------------------------------------------------------- #
class DeviceState:
    """单个虚拟设备的运行时状态。"""

    DISCONNECTED = 'disconnected'
    CONNECTING = 'connecting'
    CONNECTED = 'connected'
    ACQUIRING = 'acquiring'

    def __init__(self, spec: Tuple[str, str, int, int, Optional[List[float]]]):
        self.device_id: str = spec[0]
        self.name: str = spec[1]
        self.channel_count: int = spec[2]
        self.sample_rate: int = spec[3]
        self.freqs_def: Optional[List[float]] = spec[4]

        self.status: str = self.DISCONNECTED
        self._lock = threading.Lock()
        self._stream_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._data_queue: deque = deque(maxlen=4000)
        self._frame_seq: int = 0
        self._t: float = 0.0
        self._connected_at: Optional[float] = None
        self._acquiring_started_at: Optional[float] = None

    # --- 元信息 ---
    def meta(self) -> Dict[str, Any]:
        return {
            'driver_type': 'simulated',
            'device_id': self.device_id,
            'name': self.name,
            'address': self.device_id,
            'channel_count': self.channel_count,
            'sample_rate': self.sample_rate,
            'is_available': True,
            'extra': {
                'waveform': 'sine+noise',
                'freqs': self.freqs_def,
            },
        }

    # --- 连接管理 ---
    def connect(self) -> bool:
        with self._lock:
            if self.status in (self.CONNECTED, self.ACQUIRING):
                return True
            self.status = self.CONNECTED
            self._connected_at = time.time()
            return True

    def disconnect(self) -> bool:
        with self._lock:
            if self.status == self.ACQUIRING:
                self._stop_stream()
            self.status = self.DISCONNECTED
            self._connected_at = None
            return True

    # --- 采集控制 ---
    def start_streaming(self) -> bool:
        with self._lock:
            if self.status == self.ACQUIRING:
                return True
            if self.status == self.DISCONNECTED:
                self.status = self.CONNECTED
                self._connected_at = time.time()
            self._stop_event.clear()
            self._stream_thread = threading.Thread(
                target=self._run_stream,
                name=f'vdev-stream-{self.device_id}',
                daemon=True,
            )
            self._stream_thread.start()
            self.status = self.ACQUIRING
            self._acquiring_started_at = time.time()
            return True

    def stop_streaming(self) -> bool:
        with self._lock:
            return self._stop_stream()

    def _stop_stream(self) -> bool:
        """调用者需持锁。"""
        if self.status != self.ACQUIRING:
            return True
        self._stop_event.set()
        thread = self._stream_thread
        if thread and thread.is_alive():
            # 释放锁后 join，避免死锁
            pass  # 线程是 daemon，会在 stop_event 触发后自行退出
        self.status = self.CONNECTED
        self._acquiring_started_at = None
        return True

    # --- 数据读取 ---
    def read_data(self, count: int = 1) -> List[Dict[str, Any]]:
        with self._lock:
            out: List[Dict[str, Any]] = []
            max_count = max(1, int(count))
            for _ in range(max_count):
                if not self._data_queue:
                    break
                out.append(self._data_queue.popleft())
            return out

    def pending_count(self) -> int:
        with self._lock:
            return len(self._data_queue)

    # --- 波形生成线程 ---
    def _run_stream(self):
        sr = self.sample_rate
        ch = self.channel_count

        if self.freqs_def is None:
            # sim_multi: 每通道不同频率 (5 + i*3 Hz)
            freqs = [5.0 + i * 3.0 for i in range(ch)]
        else:
            base = self.freqs_def[0]
            freqs = [base + i * 0.5 for i in range(ch)]

        dt = 1.0 / sr
        period = dt

        # catch-up 循环，防止时间漂移
        next_t = time.perf_counter()
        while not self._stop_event.is_set():
            now = time.perf_counter()
            if now < next_t:
                time.sleep(min(0.001, next_t - now))
                continue

            # 生成一帧
            self._t += dt
            t = self._t
            channels: List[float] = []
            for i in range(ch):
                freq = freqs[i % len(freqs)]
                amp = 50.0 + (i % 3) * 10.0
                signal = amp * math.sin(2.0 * math.pi * freq * t + i * 0.5)
                noise = random.uniform(-amp * 0.05, amp * 0.05)
                channels.append(round(signal + noise, 3))

            self._frame_seq += 1
            with self._lock:
                self._data_queue.append({
                    'seq': self._frame_seq,
                    'timestamp': time.time(),
                    'channels': channels,
                    'device_id': self.device_id,
                })

            next_t += period


# ---------------------------------------------------------------------- #
#  服务器全局状态
# ---------------------------------------------------------------------- #
_DEVICES: Dict[str, DeviceState] = {
    spec[0]: DeviceState(spec) for spec in _DEVICES_SPEC
}


def get_device(device_id: str) -> Optional[DeviceState]:
    return _DEVICES.get(device_id)


# ---------------------------------------------------------------------- #
#  HTTP 请求处理器
# ---------------------------------------------------------------------- #
class VirtualDeviceHandler(BaseHTTPRequestHandler):
    """处理虚拟设备 API 请求。"""

    def log_message(self, format, *args):
        # 简化日志，带时间戳
        print(f'[{time.strftime("%H:%M:%S")}] {self.address_string()} - {format % args}')

    # --- 辅助方法 ---
    def _send_json(self, data: Any, status: int = 200):
        body = json.dumps(data).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, message: str, status: int = 400):
        self._send_json({'ok': False, 'error': message}, status)

    def _read_body(self) -> Dict[str, Any]:
        length = int(self.headers.get('Content-Length', 0))
        if length == 0:
            return {}
        try:
            raw = self.rfile.read(length)
            return json.loads(raw) if raw else {}
        except (json.JSONDecodeError, ValueError):
            return {}

    def do_OPTIONS(self):
        """CORS 预检。"""
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    # --- GET 路由 ---
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.strip('/')
        parts = [p for p in path.split('/') if p]

        # GET /health
        if parts == ['health']:
            self._send_json({
                'ok': True,
                'data': {
                    'status': 'running',
                    'device_count': len(_DEVICES),
                    'devices': list(_DEVICES.keys()),
                    'uptime': time.time() - _SERVER_START_TIME,
                }
            })
            return

        # GET /devices
        if parts == ['devices']:
            devices = [d.meta() for d in _DEVICES.values()]
            self._send_json({'ok': True, 'data': {'devices': devices, 'count': len(devices)}})
            return

        # GET /devices/{id}
        if len(parts) == 2 and parts[0] == 'devices':
            dev = get_device(parts[1])
            if not dev:
                self._send_error(f'Device not found: {parts[1]}', 404)
                return
            self._send_json({'ok': True, 'data': dev.meta()})
            return

        # GET /devices/{id}/status
        if len(parts) == 3 and parts[0] == 'devices' and parts[2] == 'status':
            dev = get_device(parts[1])
            if not dev:
                self._send_error(f'Device not found: {parts[1]}', 404)
                return
            self._send_json({
                'ok': True,
                'data': {
                    'device_id': dev.device_id,
                    'status': dev.status,
                    'pending_count': dev.pending_count(),
                    'connected_at': dev._connected_at,
                    'acquiring_started_at': dev._acquiring_started_at,
                }
            })
            return

        # GET /devices/{id}/data?count=N
        if len(parts) == 3 and parts[0] == 'devices' and parts[2] == 'data':
            dev = get_device(parts[1])
            if not dev:
                self._send_error(f'Device not found: {parts[1]}', 404)
                return
            qs = parse_qs(parsed.query)
            count = int(qs.get('count', ['1'])[0])
            count = max(1, min(2000, count))
            frames = dev.read_data(count=count)
            self._send_json({
                'ok': True,
                'data': {
                    'device_id': dev.device_id,
                    'frames': frames,
                    'count': len(frames),
                    'pending': dev.pending_count(),
                }
            })
            return

        self._send_error(f'Unknown path: GET {self.path}', 404)

    # --- POST 路由 ---
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.strip('/')
        parts = [p for p in path.split('/') if p]

        # POST /devices/{id}/connect
        if len(parts) == 3 and parts[0] == 'devices' and parts[2] == 'connect':
            dev = get_device(parts[1])
            if not dev:
                self._send_error(f'Device not found: {parts[1]}', 404)
                return
            ok = dev.connect()
            self._send_json({
                'ok': ok,
                'data': {'device_id': dev.device_id, 'status': dev.status},
            })
            return

        # POST /devices/{id}/disconnect
        if len(parts) == 3 and parts[0] == 'devices' and parts[2] == 'disconnect':
            dev = get_device(parts[1])
            if not dev:
                self._send_error(f'Device not found: {parts[1]}', 404)
                return
            ok = dev.disconnect()
            self._send_json({
                'ok': ok,
                'data': {'device_id': dev.device_id, 'status': dev.status},
            })
            return

        # POST /devices/{id}/start
        if len(parts) == 3 and parts[0] == 'devices' and parts[2] == 'start':
            dev = get_device(parts[1])
            if not dev:
                self._send_error(f'Device not found: {parts[1]}', 404)
                return
            ok = dev.start_streaming()
            self._send_json({
                'ok': ok,
                'data': {'device_id': dev.device_id, 'status': dev.status},
            })
            return

        # POST /devices/{id}/stop
        if len(parts) == 3 and parts[0] == 'devices' and parts[2] == 'stop':
            dev = get_device(parts[1])
            if not dev:
                self._send_error(f'Device not found: {parts[1]}', 404)
                return
            ok = dev.stop_streaming()
            self._send_json({
                'ok': ok,
                'data': {'device_id': dev.device_id, 'status': dev.status},
            })
            return

        self._send_error(f'Unknown path: POST {self.path}', 404)


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """多线程 HTTP 服务器，每个请求在独立线程处理。"""
    daemon_threads = True


_SERVER_START_TIME = time.time()


def create_server(host: str = HOST, port: int = PORT) -> ThreadingHTTPServer:
    """创建虚拟设备服务器实例。"""
    server = ThreadingHTTPServer((host, port), VirtualDeviceHandler)
    return server


def run_server(host: str = HOST, port: int = PORT):
    """启动虚拟设备服务器（阻塞）。"""
    server = create_server(host, port)
    print(f'[VirtualDeviceServer] Listening on http://{host}:{port}')
    print(f'[VirtualDeviceServer] {len(_DEVICES)} virtual devices:')
    for dev_id, dev in _DEVICES.items():
        print(f'    • {dev_id:12s}  {dev.name:30s}  ch={dev.channel_count}  sr={dev.sample_rate}')
    print(f'[VirtualDeviceServer] Endpoints:')
    print(f'    GET  /health')
    print(f'    GET  /devices')
    print(f'    GET  /devices/{{id}}')
    print(f'    GET  /devices/{{id}}/status')
    print(f'    GET  /devices/{{id}}/data?count=N')
    print(f'    POST /devices/{{id}}/connect')
    print(f'    POST /devices/{{id}}/disconnect')
    print(f'    POST /devices/{{id}}/start')
    print(f'    POST /devices/{{id}}/stop')
    print()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n[VirtualDeviceServer] Shutting down...')
        server.shutdown()


if __name__ == '__main__':
    run_server()
