"""DeviceDriverManager — 全局设备管理单例。

聚合所有已加载驱动的设备，对外暴露统一 API。
device_id 由驱动实现保证全局唯一（串口设备=端口号，模拟器='sim_alpha' 等）。
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Optional

from .base import DeviceDriver, DeviceFrame, DeviceMeta, DeviceStatus
from .loader import load_drivers
from .registry import get_driver_class, get_registered_driver_types

logger = logging.getLogger(__name__)


class DeviceDriverManager:
    """设备驱动管理器单例。"""

    def __init__(self):
        self._drivers: Dict[str, DeviceDriver] = {}         # driver_type → 实例
        self._device_index: Dict[str, str] = {}             # device_id → driver_type
        self._lock = threading.RLock()
        self._loaded = False

    # ------------------------------------------------------------------ #
    #  加载与注册
    # ------------------------------------------------------------------ #

    def load_all(self, driver_path: Optional[str] = None) -> None:
        """加载所有驱动（扫描目录 + 实例化）。幂等。"""
        with self._lock:
            if self._loaded:
                return
            self._loaded = True

        # 触发 loader 扫描，将驱动类注册到 registry
        loaded_classes = load_drivers(driver_path)

        with self._lock:
            for cls in loaded_classes:
                try:
                    dtype = cls.driver_type()
                    if dtype in self._drivers:
                        continue
                    instance = cls()
                    self._drivers[dtype] = instance
                    logger.info('[DriverManager] Instantiated driver: %s (%s)',
                                cls.__name__, dtype)
                except Exception as exc:
                    logger.error('[DriverManager] Failed to instantiate %s: %s', cls.__name__, exc)

        logger.info('[DriverManager] Loaded %d driver(s): %s',
                    len(self._drivers), list(self._drivers.keys()))

    def register_driver(self, driver: DeviceDriver) -> None:
        """手动注册驱动实例。"""
        with self._lock:
            dtype = driver.driver_type()
            self._drivers[dtype] = driver

    # ------------------------------------------------------------------ #
    #  设备发现
    # ------------------------------------------------------------------ #

    def discover_all(self) -> List[DeviceMeta]:
        """聚合所有驱动的 discover()，更新 device_index。"""
        all_devices: List[DeviceMeta] = []
        with self._lock:
            drivers = list(self._drivers.values())

        for driver in drivers:
            try:
                devices = driver.discover()
                for meta in devices:
                    with self._lock:
                        self._device_index[meta.device_id] = driver.driver_type()
                    all_devices.append(meta)
            except Exception as exc:
                logger.warning('[DriverManager] discover() failed for %s: %s',
                               driver.driver_type(), exc)

        logger.info('[DriverManager] Discovered %d device(s)', len(all_devices))
        return all_devices

    def get_all_devices(self) -> List[DeviceMeta]:
        """返回最近一次 discover_all 的结果（重新扫描）。"""
        return self.discover_all()

    def get_device_meta(self, device_id: str) -> Optional[DeviceMeta]:
        """查询设备元信息。"""
        driver = self._route(device_id)
        if driver:
            return driver.get_device_meta(device_id)
        return None

    # ------------------------------------------------------------------ #
    #  路由
    # ------------------------------------------------------------------ #

    def _route(self, device_id: str) -> Optional[DeviceDriver]:
        """根据 device_id 路由到对应驱动实例。"""
        with self._lock:
            # 优先查索引
            dtype = self._device_index.get(device_id)
            if dtype and dtype in self._drivers:
                return self._drivers[dtype]

            # 索引未命中：遍历所有驱动尝试
            for driver in self._drivers.values():
                if driver.get_device_meta(device_id):
                    self._device_index[device_id] = driver.driver_type()
                    return driver
        return None

    # ------------------------------------------------------------------ #
    #  设备操作（统一 API）
    # ------------------------------------------------------------------ #

    def connect(self, device_id: str, config: Optional[Dict[str, Any]] = None) -> bool:
        driver = self._route(device_id)
        if not driver:
            logger.warning('[DriverManager] No driver for device %s', device_id)
            return False
        try:
            return driver.connect(device_id, config)
        except Exception as exc:
            driver.handle_error(device_id, exc)
            return False

    def disconnect(self, device_id: str) -> bool:
        driver = self._route(device_id)
        if not driver:
            return False
        try:
            return driver.disconnect(device_id)
        except Exception as exc:
            driver.handle_error(device_id, exc)
            return False

    def start_streaming(self, device_id: str) -> bool:
        driver = self._route(device_id)
        if not driver:
            return False
        try:
            return driver.start_streaming(device_id)
        except Exception as exc:
            driver.handle_error(device_id, exc)
            return False

    def stop_streaming(self, device_id: str) -> bool:
        driver = self._route(device_id)
        if not driver:
            return False
        try:
            return driver.stop_streaming(device_id)
        except Exception as exc:
            driver.handle_error(device_id, exc)
            return False

    def read_data(self, device_id: str, count: int = 1) -> List[DeviceFrame]:
        driver = self._route(device_id)
        if not driver:
            return []
        try:
            return driver.read_data(device_id, count)
        except Exception as exc:
            driver.handle_error(device_id, exc)
            return []

    def get_status(self, device_id: str) -> DeviceStatus:
        driver = self._route(device_id)
        if not driver:
            return DeviceStatus.DISCONNECTED
        try:
            return driver.get_status(device_id)
        except Exception as exc:
            driver.handle_error(device_id, exc)
            return DeviceStatus.ERROR

    def pending_count(self, device_id: str) -> int:
        driver = self._route(device_id)
        if not driver:
            return 0
        try:
            return driver.pending_count(device_id)
        except Exception:
            return 0

    def is_streaming(self, device_id: str) -> bool:
        return self.get_status(device_id) == DeviceStatus.ACQUIRING

    # ------------------------------------------------------------------ #
    #  调试
    # ------------------------------------------------------------------ #

    def get_loaded_driver_types(self) -> List[str]:
        with self._lock:
            return list(self._drivers.keys())


# ---------------------------------------------------------------------- #
#  单例
# ---------------------------------------------------------------------- #

_manager: Optional[DeviceDriverManager] = None
_manager_lock = threading.Lock()


def get_device_manager() -> DeviceDriverManager:
    """获取全局 DeviceDriverManager 单例。"""
    global _manager
    if _manager is None:
        with _manager_lock:
            if _manager is None:
                _manager = DeviceDriverManager()
    return _manager
