import logging
logger = logging.getLogger(__name__)
"""设备配置存储和管理"""

import json
import os
import sys
import time
from typing import Dict, List, Optional, Any

# 设备配置结构
class DeviceConfig:
    def __init__(self, device_id: str, name: str, device_type: str, 
                 sampling_rate: int, channel_count: int, config: Optional[Dict] = None):
        self.id = device_id
        self.name = name
        self.type = device_type
        self.sampling_rate = sampling_rate
        self.channel_count = channel_count
        self.config = config or {}
        self.created_at = time.time()
        self.updated_at = time.time()
    
    def to_dict(self) -> Dict:
        result = {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'sampling_rate': self.sampling_rate,
            'channel_count': self.channel_count,
            'config': self.config,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
        return result
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'DeviceConfig':
        device = cls(
            device_id=data['id'],
            name=data['name'],
            device_type=data['type'],
            sampling_rate=data['sampling_rate'],
            channel_count=data['channel_count'],
            config=data.get('config', {})
        )
        device.created_at = data.get('created_at', time.time())
        device.updated_at = data.get('updated_at', time.time())
        return device


class DeviceStore:
    """设备存储管理器 - 内存存储，后端启动时自动扫描设备"""
    
    def __init__(self):
        self._devices: Dict[str, DeviceConfig] = {}
        self._initialize_devices()
    
    def _initialize_devices(self) -> None:
        """初始化设备：扫描真实设备并自动连接。"""
        logger.debug('[DeviceStore] Initializing devices...')

        # 扫描并自动连接真实设备
        self._scan_real_devices()

        logger.debug(f'[DeviceStore] Initialized {len(self._devices)} devices')
    
    def _scan_real_devices(self) -> None:
        """通过 DeviceDriverManager 发现所有设备并注册。"""
        try:
            from .drivers.manager import get_device_manager

            manager = get_device_manager()
            devices = manager.discover_all()

            for meta in devices:
                # 用 driver_type + device_id 生成唯一存储 ID
                store_id = f'{meta.driver_type}:{meta.device_id}'
                if store_id in self._devices:
                    continue

                device = DeviceConfig(
                    device_id=store_id,
                    name=meta.name,
                    device_type=meta.driver_type,
                    sampling_rate=meta.sample_rate,
                    channel_count=meta.channel_count,
                    config={
                        'device_id': meta.device_id,
                        'address': meta.address,
                        'extra': meta.extra,
                    },
                )
                self._devices[store_id] = device
                logger.debug(f'[DeviceStore] Added device: {store_id} ({meta.name})')

        except Exception as e:
            logger.debug(f'[DeviceStore] Error discovering devices: {e}')
            import traceback
            traceback.print_exc()
    
    def get_device(self, device_id: str) -> Optional[DeviceConfig]:
        """获取设备配置"""
        return self._devices.get(device_id)
    
    def get_all_devices(self) -> List[DeviceConfig]:
        """获取所有设备"""
        return list(self._devices.values())
    
    def create_device(self, device_data: Dict) -> DeviceConfig:
        """创建设备"""
        import time
        device_id = f'dev-{int(time.time() * 1000)}'
        
        device = DeviceConfig(
            device_id=device_id,
            name=device_data.get('name', f'设备 {len(self._devices) + 1}'),
            device_type=device_data.get('type', 'simulated'),
            sampling_rate=device_data.get('sampling_rate', 250),
            channel_count=device_data.get('channel_count', 8),
            config=device_data.get('config', {})
        )
        
        self._devices[device_id] = device
        logger.debug(f'[DeviceStore] Created device: {device.name} (ID: {device_id})')
        return device
    
    def update_device(self, device_id: str, updates: Dict) -> Optional[DeviceConfig]:
        """更新设备"""
        device = self._devices.get(device_id)
        if not device:
            return None
        
        # 检查是否尝试修改通道数量 - 禁止修改
        if 'channel_count' in updates and updates['channel_count'] != device.channel_count:
            raise ValueError("设备创建后通道数量不可修改")
        
        # 更新可修改的字段
        updatable_fields = ['name', 'sampling_rate', 'config']
        for field in updatable_fields:
            if field in updates:
                setattr(device, field, updates[field])
        
        device.updated_at = time.time()
        logger.debug(f'[DeviceStore] Updated device: {device.name} (ID: {device_id})')
        return device
    
    def delete_device(self, device_id: str) -> bool:
        """删除设备"""
        if device_id in self._devices:
            device_name = self._devices[device_id].name
            del self._devices[device_id]
            logger.debug(f'[DeviceStore] Deleted device: {device_name} (ID: {device_id})')
            return True
        return False


# 全局设备存储实例
_device_store = DeviceStore()


def get_device_store() -> DeviceStore:
    """获取设备存储实例"""
    return _device_store


def get_device_config(device_id: str) -> Optional[Dict]:
    """获取设备配置"""
    device = _device_store.get_device(device_id)
    return device.config if device else None


def get_device(device_id: str) -> Optional[Dict]:
    """获取完整设备信息"""
    device = _device_store.get_device(device_id)
    return device.to_dict() if device else None


def get_all_devices() -> List[Dict]:
    """获取所有设备"""
    return [device.to_dict() for device in _device_store.get_all_devices()]


def create_device(device_data: Dict) -> Dict:
    """创建设备"""
    device = _device_store.create_device(device_data)
    return device.to_dict()


def update_device(device_id: str, updates: Dict) -> Optional[Dict]:
    """更新设备"""
    device = _device_store.update_device(device_id, updates)
    return device.to_dict() if device else None


def delete_device(device_id: str) -> bool:
    """删除设备"""
    return _device_store.delete_device(device_id)