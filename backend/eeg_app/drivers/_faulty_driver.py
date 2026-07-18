"""故障注入测试驱动 — 仅供测试/E2E 使用。

文件名以 `_` 开头，drivers/loader.py 扫描时会跳过，**不会**在生产环境自动注册。
测试中通过 `manager.register_driver(FaultyDriver())` 手动注入。

提供 5 个固定设备，覆盖驱动开发中最常见的故障模式：
- `flt_ok`        — 完全正常，可连接可采集（对照组）
- `flt_conn_err`  — connect() 永远失败（模拟握手失败 / 权限拒绝）
- `flt_throw`     — 所有操作抛异常（模拟驱动代码 bug，测试 manager 兜底）
- `flt_mystery`   — connect() 返回 False 但不记录错误（测试视图的兜底提示）
- `flt_flaky`     — 间歇性数据流（读缓冲周期清空，模拟接触不良丢包）
- `flt_status_err`— get_status() 返回 DeviceStatus.ERROR（模拟设备自检失败）

该驱动同时验证 `get_last_error` 钩子：故障设备的错误消息可通过
`GET /api/real-devices/{id}/status/` 的 `last_error` 字段读取。
"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional

from .base import DeviceDriver, DeviceFrame, DeviceMeta, DeviceStatus

DEVICE_OK = 'flt_ok'
DEVICE_CONNECT_ERROR = 'flt_conn_err'
DEVICE_THROW = 'flt_throw'
DEVICE_MYSTERY = 'flt_mystery'
DEVICE_FLAKY = 'flt_flaky'
DEVICE_STATUS_ERROR = 'flt_status_err'

_ALL_DEVICES = [
    DEVICE_OK, DEVICE_CONNECT_ERROR, DEVICE_THROW,
    DEVICE_MYSTERY, DEVICE_FLAKY, DEVICE_STATUS_ERROR,
]

_ERR_MSGS = {
    DEVICE_CONNECT_ERROR: '模拟连接失败：握手超时（设备未响应 C005 初始化命令）',
    DEVICE_STATUS_ERROR: '模拟设备自检失败：传感器校准超时',
}


class FaultyDriver(DeviceDriver):
    """故障注入驱动，用于测试前后端对驱动故障的处理。"""

    @classmethod
    def driver_type(cls) -> str:
        return 'faulty'

    @classmethod
    def driver_name(cls) -> str:
        return '故障注入测试驱动'

    @classmethod
    def driver_description(cls) -> str:
        return '仅供测试：提供连接失败/异常/间歇数据流等故障注入设备'

    @classmethod
    def driver_icon(cls) -> str:
        return 'mdi-flask-empty-outline'

    def __init__(self) -> None:
        super().__init__()
        self._lock = threading.RLock()
        # device_id → 状态容器
        self._state: Dict[str, Dict[str, Any]] = {
            d: {'status': DeviceStatus.DISCONNECTED, 'seq': 0, 'buffer': []}
            for d in _ALL_DEVICES
        }

    # ------------------------------------------------------------------ #
    #  设备发现
    # ------------------------------------------------------------------ #
    def discover(self) -> List[DeviceMeta]:
        metas: List[DeviceMeta] = []
        for dev_id in _ALL_DEVICES:
            metas.append(DeviceMeta(
                driver_type=self.driver_type(),
                device_id=dev_id,
                name=f'故障注入·{dev_id}',
                channel_count=2,
                sample_rate=250,
                address=dev_id,
                extra={'fault_injection': True},
            ))
        return metas

    def get_device_meta(self, device_id: str) -> Optional[DeviceMeta]:
        if device_id not in self._state:
            return None
        for m in self.discover():
            if m.device_id == device_id:
                return m
        return None

    # ------------------------------------------------------------------ #
    #  连接管理
    # ------------------------------------------------------------------ #
    def connect(self, device_id: str, config: Optional[Dict[str, Any]] = None) -> bool:
        if device_id not in self._state:
            return False
        if device_id == DEVICE_THROW:
            raise RuntimeError('模拟驱动内部错误：connect 抛出未捕获异常')
        if device_id == DEVICE_CONNECT_ERROR:
            # 模拟驱动内部记录了具体失败原因（如 CH340 的 conn.last_error）
            self._state[device_id]['status'] = DeviceStatus.ERROR
            self._last_errors[device_id] = _ERR_MSGS[DEVICE_CONNECT_ERROR]
            return False
        if device_id == DEVICE_MYSTERY:
            # 返回 False 但什么都不记录 —— 测试视图兜底提示
            return False
        if device_id == DEVICE_STATUS_ERROR:
            # 连接成功，但 get_status 恒为 ERROR
            self._state[device_id]['status'] = DeviceStatus.ERROR
            self._last_errors[device_id] = _ERR_MSGS[DEVICE_STATUS_ERROR]
            return True

        self._state[device_id]['status'] = DeviceStatus.CONNECTED
        return True

    def disconnect(self, device_id: str) -> bool:
        if device_id == DEVICE_THROW:
            raise RuntimeError('模拟驱动内部错误：disconnect 抛出异常')
        if device_id not in self._state:
            return False
        self._state[device_id]['status'] = DeviceStatus.DISCONNECTED
        self._state[device_id]['buffer'] = []
        return True

    def get_status(self, device_id: str) -> DeviceStatus:
        if device_id == DEVICE_THROW:
            raise RuntimeError('模拟驱动内部错误：get_status 抛出异常')
        if device_id not in self._state:
            return DeviceStatus.DISCONNECTED
        if device_id == DEVICE_STATUS_ERROR:
            return DeviceStatus.ERROR
        return self._state[device_id]['status']

    # ------------------------------------------------------------------ #
    #  数据传输
    # ------------------------------------------------------------------ #
    def start_streaming(self, device_id: str) -> bool:
        if device_id == DEVICE_THROW:
            raise RuntimeError('模拟驱动内部错误：start_streaming 抛出异常')
        if device_id not in self._state:
            return False
        if device_id in (DEVICE_STATUS_ERROR,):
            return False
        st = self._state[device_id]
        if st['status'] != DeviceStatus.CONNECTED:
            return False
        st['status'] = DeviceStatus.ACQUIRING
        # 预填充若干帧，flaky 设备填充后立刻丢一半
        now = time.time()
        for i in range(5):
            st['seq'] += 1
            st['buffer'].append(DeviceFrame(
                seq=st['seq'], timestamp=now + i * 0.004,
                channels=[1.0 * st['seq'], -1.0 * st['seq']],
                device_id=device_id,
            ))
        if device_id == DEVICE_FLAKY:
            st['buffer'] = st['buffer'][::2]  # 模拟丢包：只剩一半帧
        return True

    def stop_streaming(self, device_id: str) -> bool:
        if device_id == DEVICE_THROW:
            raise RuntimeError('模拟驱动内部错误：stop_streaming 抛出异常')
        if device_id not in self._state:
            return False
        if self._state[device_id]['status'] == DeviceStatus.ACQUIRING:
            self._state[device_id]['status'] = DeviceStatus.CONNECTED
        return True

    def read_data(self, device_id: str, count: int = 1) -> List[DeviceFrame]:
        if device_id == DEVICE_THROW:
            raise RuntimeError('模拟驱动内部错误：read_data 抛出异常')
        if device_id not in self._state:
            return []
        buf = self._state[device_id]['buffer']
        out = buf[:max(1, int(count))]
        self._state[device_id]['buffer'] = buf[len(out):]
        return out

    def pending_count(self, device_id: str) -> int:
        if device_id == DEVICE_THROW:
            raise RuntimeError('模拟驱动内部错误：pending_count 抛出异常')
        if device_id not in self._state:
            return 0
        return len(self._state[device_id]['buffer'])

    # ------------------------------------------------------------------ #
    #  错误反馈
    # ------------------------------------------------------------------ #
    def get_last_error(self, device_id: str) -> Optional[str]:
        if device_id == DEVICE_THROW:
            return self._last_errors.get(device_id) or '模拟驱动内部错误'
        if device_id == DEVICE_STATUS_ERROR:
            # 持续性硬件故障：即使 connect 清除了缓存，自检错误依然存在
            return _ERR_MSGS[DEVICE_STATUS_ERROR]
        return super().get_last_error(device_id)
