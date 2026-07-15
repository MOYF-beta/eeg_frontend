"""设备驱动抽象基类与数据类型定义。

所有第三方设备驱动只需实现 DeviceDriver 抽象类，
将 .py 文件放入 drivers/ 目录即可被 loader 自动发现加载。
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DeviceStatus(Enum):
    """设备连接状态。"""
    DISCONNECTED = 'disconnected'
    CONNECTING = 'connecting'
    CONNECTED = 'connected'
    ACQUIRING = 'acquiring'
    ERROR = 'error'


@dataclass
class DeviceMeta:
    """设备元信息 — discover() 返回单元。"""
    driver_type: str                       # 驱动类型标识（如 'wearable_eeg'）
    device_id: str                         # 驱动内全局唯一 ID（端口号 / 'sim_alpha' 等）
    name: str                              # 人类可读名称
    channel_count: int                     # 通道数
    sample_rate: int                       # 标称采样率 (Hz)
    address: str = ''                      # 连接地址（与 device_id 可同）
    channel_names: List[str] = field(default_factory=list)
    is_available: bool = True              # 当前是否可连接
    extra: Dict[str, Any] = field(default_factory=dict)   # 驱动特定字段


@dataclass
class DeviceFrame:
    """统一数据帧。"""
    seq: int                               # 帧序号
    timestamp: float                       # 秒级时间戳（time.time() 尺度）
    channels: List[float]                  # 通道数据
    device_id: str = ''
    extra: Dict[str, Any] = field(default_factory=dict)


class DeviceDriver(ABC):
    """设备驱动抽象基类。

    子类必须实现所有 @abstractmethod 方法。
    将含此基类子类的 .py 文件放入 drivers/ 目录即自动注册。
    """

    # ------------------------------------------------------------------ #
    #  驱动级元信息
    # ------------------------------------------------------------------ #

    @classmethod
    @abstractmethod
    def driver_type(cls) -> str:
        """返回驱动类型标识，全局唯一（如 'wearable_eeg'）。"""

    @classmethod
    def driver_name(cls) -> str:
        """人类可读驱动名称，默认 = driver_type()。"""
        return cls.driver_type()

    @classmethod
    def driver_description(cls) -> str:
        """驱动描述文本。"""
        return ''

    # ------------------------------------------------------------------ #
    #  设备发现与元信息
    # ------------------------------------------------------------------ #

    @abstractmethod
    def discover(self) -> List[DeviceMeta]:
        """发现可用设备列表，不建立持久连接。"""

    def get_device_meta(self, device_id: str) -> Optional[DeviceMeta]:
        """查询单个设备元信息，默认遍历 discover()。"""
        for meta in self.discover():
            if meta.device_id == device_id:
                return meta
        return None

    # ------------------------------------------------------------------ #
    #  连接管理
    # ------------------------------------------------------------------ #

    @abstractmethod
    def connect(self, device_id: str, config: Optional[Dict[str, Any]] = None) -> bool:
        """建立设备连接（幂等）。"""

    @abstractmethod
    def disconnect(self, device_id: str) -> bool:
        """断开设备连接（幂等）。"""

    @abstractmethod
    def get_status(self, device_id: str) -> DeviceStatus:
        """获取设备当前状态。"""

    # ------------------------------------------------------------------ #
    #  数据传输
    # ------------------------------------------------------------------ #

    @abstractmethod
    def start_streaming(self, device_id: str) -> bool:
        """启动数据传输，持续采集到内部缓冲。"""

    @abstractmethod
    def stop_streaming(self, device_id: str) -> bool:
        """停止数据传输（连接保持，幂等）。"""

    @abstractmethod
    def read_data(self, device_id: str, count: int = 1) -> List[DeviceFrame]:
        """从缓冲区 drain 最多 count 帧数据。"""

    @abstractmethod
    def pending_count(self, device_id: str) -> int:
        """缓冲区待读帧数。"""

    # ------------------------------------------------------------------ #
    #  异常处理
    # ------------------------------------------------------------------ #

    def handle_error(self, device_id: str, error: Exception) -> None:
        """异常处理钩子，默认记录日志，子类可覆写。"""
        logger.error('[%s] Device %s error: %s', self.driver_type(), device_id, error)
