"""模拟设备驱动（单文件）。

纯软件波形生成，不依赖 pyserial/pty。后端自动提供 5 个虚拟设备，
覆盖不同 EEG 节律频段，用于无硬件环境的开发与测试。
"""

from __future__ import annotations

import logging
import math
import random
import threading
import time
from collections import deque
from typing import Any, Dict, List, Optional

from .base import DeviceDriver, DeviceFrame, DeviceMeta, DeviceStatus

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------- #
#  5 个虚拟设备定义
# ---------------------------------------------------------------------- #
# 每个 entry: (device_id, name, channel_count, sample_rate, freqs)
# freqs: 每通道的基频列表（不足则循环），None 表示按通道索引自动递增
_DEVICES = [
    ('sim_alpha', 'Alpha 波模拟器 (10Hz)',  8, 250, [10.0]),
    ('sim_beta',  'Beta 波模拟器 (20Hz)',   8, 250, [20.0]),
    ('sim_theta', 'Theta 波模拟器 (6Hz)',   4, 200, [6.0]),
    ('sim_gamma', 'Gamma 波模拟器 (40Hz)',  8, 500, [40.0]),
    ('sim_multi', '多频混合模拟器',          8, 250, None),   # 每通道不同频率
]


# ---------------------------------------------------------------------- #
#  内部状态
# ---------------------------------------------------------------------- #
class _StreamState:
    """单个模拟设备的采集状态。"""
    def __init__(self):
        self.status: DeviceStatus = DeviceStatus.DISCONNECTED
        self.thread: Optional[threading.Thread] = None
        self.stop_event: threading.Event = threading.Event()
        self.data_queue: deque = deque(maxlen=2000)
        self.frame_seq: int = 0
        self.t: float = 0.0   # 累积时间（秒），用于波形相位


# ---------------------------------------------------------------------- #
#  驱动实现
# ---------------------------------------------------------------------- #
class SimulatorDriver(DeviceDriver):
    """模拟设备驱动 — 5 个虚拟 EEG 信号源。"""

    def __init__(self):
        self._states: Dict[str, _StreamState] = {dev[0]: _StreamState() for dev in _DEVICES}
        self._lock = threading.RLock()
        self._meta_cache: Dict[str, DeviceMeta] = {}
        for dev_id, name, ch, sr, _freqs in _DEVICES:
            self._meta_cache[dev_id] = DeviceMeta(
                driver_type=self.driver_type(),
                device_id=dev_id,
                name=name,
                address=dev_id,
                channel_count=ch,
                sample_rate=sr,
                is_available=True,
                extra={'waveform': 'sine+noise'},
            )

    # ------------------------------------------------------------------ #
    #  驱动元信息
    # ------------------------------------------------------------------ #
    @classmethod
    def driver_type(cls) -> str:
        return 'simulator'

    @classmethod
    def driver_name(cls) -> str:
        return '模拟设备驱动'

    @classmethod
    def driver_description(cls) -> str:
        return '纯软件波形生成，提供 5 个虚拟 EEG 设备（α/β/θ/γ/多频混合）'

    # ------------------------------------------------------------------ #
    #  设备发现
    # ------------------------------------------------------------------ #
    def discover(self) -> List[DeviceMeta]:
        return list(self._meta_cache.values())

    def get_device_meta(self, device_id: str) -> Optional[DeviceMeta]:
        return self._meta_cache.get(device_id)

    # ------------------------------------------------------------------ #
    #  连接管理
    # ------------------------------------------------------------------ #
    def connect(self, device_id: str, config: Optional[Dict[str, Any]] = None) -> bool:
        with self._lock:
            state = self._states.get(device_id)
            if not state:
                return False
            if state.status in (DeviceStatus.CONNECTED, DeviceStatus.ACQUIRING):
                return True
            state.status = DeviceStatus.CONNECTED
            logger.debug('[Simulator] Connected %s', device_id)
            return True

    def disconnect(self, device_id: str) -> bool:
        with self._lock:
            state = self._states.get(device_id)
            if not state:
                return False
            if state.status == DeviceStatus.ACQUIRING:
                self._stop_stream(device_id)
            state.status = DeviceStatus.DISCONNECTED
            logger.debug('[Simulator] Disconnected %s', device_id)
            return True

    def get_status(self, device_id: str) -> DeviceStatus:
        state = self._states.get(device_id)
        return state.status if state else DeviceStatus.DISCONNECTED

    # ------------------------------------------------------------------ #
    #  数据传输
    # ------------------------------------------------------------------ #
    def start_streaming(self, device_id: str) -> bool:
        with self._lock:
            state = self._states.get(device_id)
            if not state:
                return False
            if state.status == DeviceStatus.ACQUIRING:
                return True
            if state.status == DeviceStatus.DISCONNECTED:
                state.status = DeviceStatus.CONNECTED
            state.stop_event.clear()
            state.thread = threading.Thread(
                target=self._run_stream,
                args=(device_id, state),
                name=f'sim-stream-{device_id}',
                daemon=True,
            )
            state.thread.start()
            state.status = DeviceStatus.ACQUIRING
            logger.debug('[Simulator] Streaming started %s', device_id)
            return True

    def stop_streaming(self, device_id: str) -> bool:
        return self._stop_stream(device_id)

    def _stop_stream(self, device_id: str) -> bool:
        with self._lock:
            state = self._states.get(device_id)
            if not state:
                return False
            if state.status != DeviceStatus.ACQUIRING:
                return True
            state.stop_event.set()
            if state.thread and state.thread.is_alive():
                state.thread.join(timeout=2.0)
            state.status = DeviceStatus.CONNECTED
            logger.debug('[Simulator] Streaming stopped %s', device_id)
            return True

    def read_data(self, device_id: str, count: int = 1) -> List[DeviceFrame]:
        with self._lock:
            state = self._states.get(device_id)
            if not state:
                return []
            out: List[DeviceFrame] = []
            max_count = max(1, int(count))
            for _ in range(max_count):
                if not state.data_queue:
                    break
                raw = state.data_queue.popleft()
                out.append(DeviceFrame(
                    seq=raw['seq'],
                    timestamp=raw['timestamp'],
                    channels=raw['channels'],
                    device_id=device_id,
                ))
            return out

    def pending_count(self, device_id: str) -> int:
        state = self._states.get(device_id)
        return len(state.data_queue) if state else 0

    # ------------------------------------------------------------------ #
    #  波形生成线程
    # ------------------------------------------------------------------ #
    def _run_stream(self, device_id: str, state: _StreamState):
        meta = self._meta_cache[device_id]
        sr = meta.sample_rate
        ch = meta.channel_count
        freqs_def = next(d[4] for d in _DEVICES if d[0] == device_id)

        # 每通道频率列表
        if freqs_def is None:
            # sim_multi: 每通道不同频率 (5 + i*3 Hz)
            freqs = [5.0 + i * 3.0 for i in range(ch)]
        else:
            base = freqs_def[0]
            freqs = [base + i * 0.5 for i in range(ch)]

        dt = 1.0 / sr
        period = dt
        logger.debug('[Simulator] Stream thread started %s  sr=%d  ch=%d  freqs=%s',
                     device_id, sr, ch, freqs)

        # catch-up 循环（参考 serial_simulator.py），防止时间漂移
        next_t = time.perf_counter()
        while not state.stop_event.is_set():
            now = time.perf_counter()
            if now < next_t:
                time.sleep(min(0.001, next_t - now))
                continue

            # 生成一帧
            state.t += dt
            t = state.t
            channels: List[float] = []
            for i in range(ch):
                freq = freqs[i % len(freqs)]
                amp = 50.0 + (i % 3) * 10.0
                signal = amp * math.sin(2.0 * math.pi * freq * t + i * 0.5)
                noise = random.uniform(-amp * 0.05, amp * 0.05)
                channels.append(round(signal + noise, 3))

            state.frame_seq += 1
            state.data_queue.append({
                'seq': state.frame_seq,
                'timestamp': time.time(),
                'channels': channels,
            })

            next_t += period
