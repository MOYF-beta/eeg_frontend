import logging
logger = logging.getLogger(__name__)
from django.apps import AppConfig


class EegAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'eeg_app'
    
    def ready(self):
        """应用启动时加载设备驱动并初始化设备存储"""
        # 加载所有设备驱动
        from .drivers.manager import get_device_manager
        manager = get_device_manager()
        manager.load_all()
        manager.discover_all()
        logger.debug(f'[EegAppConfig] Loaded drivers: {manager.get_loaded_driver_types()}')

        # 初始化设备存储（基于已发现的设备）
        from .device_store import get_device_store
        device_store = get_device_store()
        logger.debug(f'[EegAppConfig] Device store initialized with {len(device_store.get_all_devices())} devices')
