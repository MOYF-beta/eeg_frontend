"""设备驱动注册表。"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Type

from .base import DeviceDriver

logger = logging.getLogger(__name__)

_DRIVER_REGISTRY: Dict[str, Type[DeviceDriver]] = {}


def register_driver(cls: Type[DeviceDriver]) -> None:
    """注册驱动类。按 driver_type() 去重。"""
    try:
        dtype = cls.driver_type()
    except Exception as exc:
        logger.warning('[DriverRegistry] %s driver_type() failed: %s — skipped', cls.__name__, exc)
        return

    if dtype in _DRIVER_REGISTRY:
        logger.warning('[DriverRegistry] driver_type=%r already registered by %s, overwriting with %s',
                       dtype, _DRIVER_REGISTRY[dtype].__name__, cls.__name__)
    _DRIVER_REGISTRY[dtype] = cls
    logger.debug('[DriverRegistry] Registered driver %s (type=%s)', cls.__name__, dtype)


def get_driver_class(driver_type: str) -> Optional[Type[DeviceDriver]]:
    return _DRIVER_REGISTRY.get(driver_type)


def get_registered_driver_types() -> List[str]:
    return list(_DRIVER_REGISTRY.keys())
