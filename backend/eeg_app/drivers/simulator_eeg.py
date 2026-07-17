"""模拟设备驱动 — 通过 HTTP 与 7777 端口虚拟设备服务器通信。

这是一个 **客户端驱动**：不直接生成波形，而是与独立运行的
`virtual_device_server.py`（端口 7777）通信，实现 `DeviceDriver` 抽象类的
所有方法。这样更好地模拟真实外部设备的行为。

启动顺序：
    1. python virtual_device_server.py        # 先启动虚拟设备服务器
    2. python manage.py runserver             # 再启动 Django 后端

如果服务器未运行，discover() 返回空列表，设备列表中不会出现虚拟设备。
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from .base import DeviceDriver, DeviceFrame, DeviceMeta, DeviceStatus

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------- #
#  配置
# ---------------------------------------------------------------------- #
DEFAULT_SERVER_URL = 'http://127.0.0.1:7777'
REQUEST_TIMEOUT = 3.0  # 秒

# 状态字符串 → DeviceStatus 映射
_STATUS_MAP = {
    'disconnected': DeviceStatus.DISCONNECTED,
    'connecting': DeviceStatus.CONNECTING,
    'connected': DeviceStatus.CONNECTED,
    'acquiring': DeviceStatus.ACQUIRING,
    'error': DeviceStatus.ERROR,
}


def _http_request(method: str, path: str, base_url: str = DEFAULT_SERVER_URL,
                  body: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
    """发送 HTTP 请求到虚拟设备服务器。

    Returns:
        解析后的 JSON 响应 dict，出错返回 None。
    """
    url = f'{base_url.rstrip("/")}/{path.lstrip("/")}'
    data = json.dumps(body).encode('utf-8') if body else None
    req = urllib.request.Request(url, data=data, method=method)
    if data:
        req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.URLError as exc:
        logger.debug('[SimulatorDriver] Server unreachable (%s %s): %s', method, url, exc)
        return None
    except Exception as exc:
        logger.warning('[SimulatorDriver] Request failed (%s %s): %s', method, url, exc)
        return None


class SimulatorDriver(DeviceDriver):
    """模拟设备驱动 — 通过 HTTP 与 7777 端口服务器通信。

    本驱动不包含任何波形生成逻辑，所有数据由虚拟设备服务器产生。
    """

    def __init__(self, server_url: str = DEFAULT_SERVER_URL):
        self._server_url = server_url
        self._meta_cache: Dict[str, DeviceMeta] = {}
        self._available: bool = False

    # ------------------------------------------------------------------ #
    #  驱动元信息
    # ------------------------------------------------------------------ #
    @classmethod
    def driver_type(cls) -> str:
        return 'simulated'

    @classmethod
    def driver_name(cls) -> str:
        return '虚拟设备驱动'

    @classmethod
    def driver_description(cls) -> str:
        return '通过 HTTP 与 7777 端口虚拟设备服务器通信，提供 5 个虚拟 EEG 设备（α/β/θ/γ/多频混合）'

    # ------------------------------------------------------------------ #
    #  内部辅助
    # ------------------------------------------------------------------ #
    def _refresh_meta_cache(self) -> bool:
        """从服务器拉取设备列表，更新本地缓存。"""
        result = _http_request('GET', '/devices', self._server_url)
        if result is None or not result.get('ok'):
            self._available = False
            self._meta_cache.clear()
            return False

        self._available = True
        self._meta_cache.clear()
        for item in result.get('data', {}).get('devices', []):
            meta = DeviceMeta(
                driver_type=item.get('driver_type', self.driver_type()),
                device_id=item['device_id'],
                name=item.get('name', item['device_id']),
                address=item.get('address', item['device_id']),
                channel_count=item.get('channel_count', 8),
                sample_rate=item.get('sample_rate', 250),
                is_available=item.get('is_available', True),
                extra=item.get('extra', {}),
            )
            self._meta_cache[meta.device_id] = meta
        return True

    # ------------------------------------------------------------------ #
    #  设备发现
    # ------------------------------------------------------------------ #
    def discover(self) -> List[DeviceMeta]:
        self._refresh_meta_cache()
        return list(self._meta_cache.values())

    def get_device_meta(self, device_id: str) -> Optional[DeviceMeta]:
        if not self._meta_cache:
            self._refresh_meta_cache()
        return self._meta_cache.get(device_id)

    # ------------------------------------------------------------------ #
    #  连接管理
    # ------------------------------------------------------------------ #
    def connect(self, device_id: str, config: Optional[Dict[str, Any]] = None) -> bool:
        result = _http_request('POST', f'/devices/{device_id}/connect', self._server_url)
        if result is None:
            return False
        return result.get('ok', False)

    def disconnect(self, device_id: str) -> bool:
        result = _http_request('POST', f'/devices/{device_id}/disconnect', self._server_url)
        if result is None:
            return False
        return result.get('ok', False)

    def get_status(self, device_id: str) -> DeviceStatus:
        result = _http_request('GET', f'/devices/{device_id}/status', self._server_url)
        if result is None or not result.get('ok'):
            return DeviceStatus.DISCONNECTED
        status_str = result.get('data', {}).get('status', 'disconnected')
        return _STATUS_MAP.get(status_str, DeviceStatus.DISCONNECTED)

    # ------------------------------------------------------------------ #
    #  数据传输
    # ------------------------------------------------------------------ #
    def start_streaming(self, device_id: str) -> bool:
        result = _http_request('POST', f'/devices/{device_id}/start', self._server_url)
        if result is None:
            return False
        return result.get('ok', False)

    def stop_streaming(self, device_id: str) -> bool:
        result = _http_request('POST', f'/devices/{device_id}/stop', self._server_url)
        if result is None:
            return False
        return result.get('ok', False)

    def read_data(self, device_id: str, count: int = 1) -> List[DeviceFrame]:
        result = _http_request(
            'GET', f'/devices/{device_id}/data?count={count}', self._server_url
        )
        if result is None or not result.get('ok'):
            return []
        frames: List[DeviceFrame] = []
        for item in result.get('data', {}).get('frames', []):
            frames.append(DeviceFrame(
                seq=item.get('seq', 0),
                timestamp=item.get('timestamp', 0.0),
                channels=item.get('channels', []),
                device_id=device_id,
            ))
        return frames

    def pending_count(self, device_id: str) -> int:
        result = _http_request('GET', f'/devices/{device_id}/status', self._server_url)
        if result is None or not result.get('ok'):
            return 0
        return result.get('data', {}).get('pending_count', 0)
