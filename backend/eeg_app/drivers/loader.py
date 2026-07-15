"""设备驱动动态加载器。

扁平单文件约定：每个驱动 = drivers/ 目录下的一个 .py 文件。
loader 扫描 *.py，凡含 DeviceDriver 子类的文件即视为驱动，
自动实例化并注册到 registry。
"""

from __future__ import annotations

import importlib.util
import inspect
import logging
import os
from pathlib import Path
from types import ModuleType
from typing import List, Optional, Type

from .base import DeviceDriver
from .registry import register_driver

logger = logging.getLogger(__name__)

# 本目录即默认驱动扫描路径（排除框架文件）
DEFAULT_DRIVER_PATH = Path(__file__).resolve().parent

# 框架自身文件，不作为驱动加载
_FRAMEWORK_FILES = {
    '__init__', 'base', 'registry', 'loader', 'manager',
}


def _load_module(path: Path) -> Optional[ModuleType]:
    import sys
    try:
        module_name = f'eeg_app.drivers.{path.stem}'
        spec = importlib.util.spec_from_file_location(module_name, str(path))
        if not spec or not spec.loader:
            return None
        module = importlib.util.module_from_spec(spec)
        # Register in sys.modules before exec — required by @dataclass on Python 3.12+
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module
    except Exception as exc:
        logger.warning('[DriverLoader] Failed to load %s: %s', path.name, exc)
        return None


def load_drivers(driver_path: Optional[str] = None) -> List[Type[DeviceDriver]]:
    """扫描目录，加载所有含 DeviceDriver 子类的 .py 文件。

    Args:
        driver_path: 自定义扫描目录；None 时用 DEFAULT_DRIVER_PATH 或 EEG_DRIVER_PATH 环境变量。

    Returns:
        成功加载并注册的驱动类列表。
    """
    path = Path(driver_path or os.getenv('EEG_DRIVER_PATH') or DEFAULT_DRIVER_PATH)
    path.mkdir(parents=True, exist_ok=True)

    loaded: List[Type[DeviceDriver]] = []

    for file in sorted(path.glob('*.py')):
        if file.name.startswith('_'):
            continue
        if file.stem in _FRAMEWORK_FILES:
            continue

        module = _load_module(file)
        if not module:
            continue

        # 自动发现 DeviceDriver 子类
        for _, member in inspect.getmembers(module, inspect.isclass):
            if not issubclass(member, DeviceDriver) or member is DeviceDriver:
                continue
            try:
                register_driver(member)
                loaded.append(member)
                logger.info('[DriverLoader] Loaded driver %s from %s', member.__name__, file.name)
            except Exception as exc:
                logger.warning('[DriverLoader] Failed to register %s from %s: %s',
                               member.__name__, file.name, exc)

    return loaded
