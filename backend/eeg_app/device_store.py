"""设备配置存储和管理"""

import json
import os
import time
from typing import Dict, List, Optional, Any

# 设备数据文件路径
DEVICE_FILE = os.path.join(os.path.dirname(__file__), 'device_data.json')

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
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'sampling_rate': self.sampling_rate,
            'channel_count': self.channel_count,
            'config': self.config,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
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
    """设备存储管理器"""
    
    def __init__(self):
        self._devices: Dict[str, DeviceConfig] = {}
        self._load_from_file()
    
    def _load_from_file(self) -> None:
        """从JSON文件加载设备数据"""
        try:
            if os.path.exists(DEVICE_FILE):
                with open(DEVICE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for device_data in data.get('devices', []):
                        device = DeviceConfig.from_dict(device_data)
                        self._devices[device.id] = device
                print(f'[DeviceStore] Loaded {len(self._devices)} devices from {DEVICE_FILE}')
            else:
                # 文件不存在，创建默认模拟设备
                print(f'[DeviceStore] Device file not found, creating default devices')
                self._create_default_devices()
        except Exception as e:
            print(f'[DeviceStore] Failed to load from file: {e}')
            # 创建默认模拟设备
            self._create_default_devices()
    
    def _save_to_file(self) -> None:
        """保存设备数据到JSON文件"""
        try:
            data = {
                'devices': [device.to_dict() for device in self._devices.values()]
            }
            with open(DEVICE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f'[DeviceStore] Saved {len(self._devices)} devices to {DEVICE_FILE}')
        except Exception as e:
            print(f'[DeviceStore] Failed to save to file: {e}')
    
    def _create_default_devices(self) -> None:
        """创建默认模拟设备"""
        default_devices = [
            DeviceConfig(
                device_id='mock-1',
                name='模拟设备 1',
                device_type='simulated',
                sampling_rate=1000,
                channel_count=8,
                config={
                    'channels': [
                        {
                            'index': 0,
                            'wave_type': 'sine',
                            'frequency': 10,
                            'amplitude': 100,
                            'alias': 'CH1',
                            'noise_type': 'white',
                            'noise_amplitude': 5
                        },
                        {
                            'index': 1,
                            'wave_type': 'sine',
                            'frequency': 15,
                            'amplitude': 80,
                            'alias': 'CH2',
                            'noise_type': 'white',
                            'noise_amplitude': 5
                        },
                        {
                            'index': 2,
                            'wave_type': 'square',
                            'frequency': 5,
                            'amplitude': 120,
                            'alias': 'CH3',
                            'duty_cycle': 0.5,
                            'noise_type': 'white',
                            'noise_amplitude': 5
                        },
                        {
                            'index': 3,
                            'wave_type': 'triangle',
                            'frequency': 8,
                            'amplitude': 90,
                            'alias': 'CH4',
                            'noise_type': 'white',
                            'noise_amplitude': 5
                        },
                        {
                            'index': 4,
                            'wave_type': 'sine',
                            'frequency': 20,
                            'amplitude': 70,
                            'alias': 'CH5',
                            'noise_type': 'white',
                            'noise_amplitude': 5
                        },
                        {
                            'index': 5,
                            'wave_type': 'sine',
                            'frequency': 25,
                            'amplitude': 110,
                            'alias': 'CH6',
                            'noise_type': 'white',
                            'noise_amplitude': 5
                        },
                        {
                            'index': 6,
                            'wave_type': 'sine',
                            'frequency': 30,
                            'amplitude': 85,
                            'alias': 'CH7',
                            'noise_type': 'white',
                            'noise_amplitude': 5
                        },
                        {
                            'index': 7,
                            'wave_type': 'sine',
                            'frequency': 35,
                            'amplitude': 95,
                            'alias': 'CH8',
                            'noise_type': 'white',
                            'noise_amplitude': 5
                        }
                    ]
                }
            )
        ]
        
        for device in default_devices:
            self._devices[device.id] = device
        
        self._save_to_file()
    
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
        self._save_to_file()
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
        self._save_to_file()
        return device
    
    def delete_device(self, device_id: str) -> bool:
        """删除设备"""
        if device_id in self._devices:
            del self._devices[device_id]
            self._save_to_file()
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