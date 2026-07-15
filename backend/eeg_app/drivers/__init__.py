"""设备驱动包公共 API。

新增驱动：在 drivers/ 目录下放入一个 .py 文件，
文件中定义 DeviceDriver 子类即可被自动发现加载。
"""

from .base import DeviceDriver, DeviceFrame, DeviceMeta, DeviceStatus
from .manager import DeviceDriverManager, get_device_manager
from .registry import get_driver_class, get_registered_driver_types, register_driver

__all__ = [
    'DeviceDriver',
    'DeviceMeta',
    'DeviceFrame',
    'DeviceStatus',
    'DeviceDriverManager',
    'get_device_manager',
    'register_driver',
    'get_driver_class',
    'get_registered_driver_types',
]
