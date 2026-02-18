from django.apps import AppConfig


class EegAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'eeg_app'
    
    def ready(self):
        """应用启动时初始化设备存储"""
        # 导入设备存储模块，触发设备存储初始化
        from .device_store import get_device_store
        device_store = get_device_store()
        print(f'[EegAppConfig] Device store initialized with {len(device_store.get_all_devices())} devices')
