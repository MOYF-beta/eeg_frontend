"""设备配置存储和管理"""

import json
import os
import time
import serial.tools.list_ports
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
        
        # 真实设备特定字段
        if device_type == 'wearable_eeg':
            self.port = config.get('port', '')
            self.baudrate = config.get('baudrate', 460800)
            self.connected = False
            self.acquiring = False
    
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
        
        # 添加真实设备特定字段
        if self.type == 'wearable_eeg':
            result['port'] = getattr(self, 'port', '')
            result['baudrate'] = getattr(self, 'baudrate', 460800)
            result['connected'] = getattr(self, 'connected', False)
            result['acquiring'] = getattr(self, 'acquiring', False)
            
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
        
        # 设置真实设备特定字段
        if data['type'] == 'wearable_eeg':
            device.port = data.get('port', '')
            device.baudrate = data.get('baudrate', 460800)
            device.connected = data.get('connected', False)
            device.acquiring = data.get('acquiring', False)
            
        return device


class DeviceStore:
    """设备存储管理器 - 内存存储，后端启动时自动扫描设备"""
    
    def __init__(self):
        self._devices: Dict[str, DeviceConfig] = {}
        self._initialize_devices()
    
    def _initialize_devices(self) -> None:
        """初始化设备：扫描真实设备并创建模拟设备"""
        print('[DeviceStore] Initializing devices...')
        
        # 1. 扫描真实设备
        self._scan_real_devices()
        
        # 2. 创建默认模拟设备
        self._create_default_devices()
        
        print(f'[DeviceStore] Initialized {len(self._devices)} devices')
    
    def _scan_real_devices(self) -> None:
        """扫描真实设备（CH340和其他USB串口设备）"""
        try:
            # 获取所有串口设备
            available_ports = serial.tools.list_ports.comports()
            print(f'[DeviceStore] Found {len(available_ports)} serial ports')
            
            for port_info in available_ports:
                device_name = port_info.device
                
                # 检查是否是USB串口设备
                if not self._is_usb_serial_port(port_info):
                    continue
                
                # 检查是否是CH340设备
                is_ch340 = self._is_ch340_port(port_info)
                
                # 创建设备ID（使用端口名和设备信息）
                device_id = f'real-{device_name.replace("/", "-")}'
                
                # 创建设备配置
                device = DeviceConfig(
                    device_id=device_id,
                    name=f'真实设备 {device_name}',
                    device_type='wearable_eeg',
                    sampling_rate=250,  # 默认采样率
                    channel_count=8,    # 默认通道数
                    config={
                        'port': device_name,
                        'baudrate': 460800,
                        'description': port_info.description or '',
                        'manufacturer': port_info.manufacturer or '',
                        'product': port_info.product or '',
                        'hwid': port_info.hwid or '',
                        'is_ch340': is_ch340,
                        'vid': getattr(port_info, 'vid', None),
                        'pid': getattr(port_info, 'pid', None)
                    }
                )
                
                self._devices[device_id] = device
                print(f'[DeviceStore] Added real device: {device_name} (CH340: {is_ch340})')
                
        except Exception as e:
            print(f'[DeviceStore] Error scanning real devices: {e}')
            import traceback
            traceback.print_exc()
    
    def _is_usb_serial_port(self, port_info) -> bool:
        """检查是否是USB串口设备"""
        try:
            # 检查是否有VID/PID（USB设备）
            vid = getattr(port_info, 'vid', None)
            pid = getattr(port_info, 'pid', None)
            
            # 检查描述中是否包含USB或串口关键词
            description = (port_info.description or '').lower()
            manufacturer = (port_info.manufacturer or '').lower()
            product = (port_info.product or '').lower()
            
            # USB设备通常有VID/PID
            if vid is not None and pid is not None:
                return True
            
            # 检查常见关键词
            usb_keywords = ['usb', 'serial', 'com', 'uart', 'ch340', 'ftdi', 'cp210']
            for keyword in usb_keywords:
                if (keyword in description or 
                    keyword in manufacturer or 
                    keyword in product):
                    return True
                    
            return False
        except Exception:
            return False
    
    def _is_ch340_port(self, port_info) -> bool:
        """检查是否是CH340设备"""
        try:
            vid = getattr(port_info, 'vid', None)
            pid = getattr(port_info, 'pid', None)
            
            # CH340的VID通常是0x1A86
            if vid == 0x1A86:
                return True
            
            # 检查描述中是否包含CH340
            description = (port_info.description or '').lower()
            manufacturer = (port_info.manufacturer or '').lower()
            product = (port_info.product or '').lower()
            
            ch340_keywords = ['ch340', 'ch341', '1a86']
            for keyword in ch340_keywords:
                if (keyword in description or 
                    keyword in manufacturer or 
                    keyword in product):
                    return True
                    
            return False
        except Exception:
            return False
    
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
            print(f'[DeviceStore] Added simulated device: {device.name}')
    
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
        print(f'[DeviceStore] Created device: {device.name} (ID: {device_id})')
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
        print(f'[DeviceStore] Updated device: {device.name} (ID: {device_id})')
        return device
    
    def delete_device(self, device_id: str) -> bool:
        """删除设备"""
        if device_id in self._devices:
            device_name = self._devices[device_id].name
            del self._devices[device_id]
            print(f'[DeviceStore] Deleted device: {device_name} (ID: {device_id})')
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