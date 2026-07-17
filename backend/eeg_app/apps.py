import logging
logger = logging.getLogger(__name__)
from django.apps import AppConfig


class EegAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'eeg_app'
    
    def ready(self):
        """应用启动时加载设备驱动"""
        # 加载所有设备驱动
        from .drivers.manager import get_device_manager
        manager = get_device_manager()
        manager.load_all()
        manager.discover_all()
        logger.debug(f'[EegAppConfig] Loaded drivers: {manager.get_loaded_driver_types()}')
