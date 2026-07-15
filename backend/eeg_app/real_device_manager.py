import logging
logger = logging.getLogger(__name__)
"""真实可穿戴EEG设备管理器 - 集成驱动脚本的异步逻辑"""

import asyncio
import json
import os
import platform
import subprocess
import struct
import time
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, Any, Callable
import threading
from datetime import datetime
import numpy as np

# pyserial 依赖 termios（Unix-only），在 Windows 上需优雅降级
try:
    import serial
    import serial.tools.list_ports
    import serial_asyncio
    SERIAL_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    serial = None  # type: ignore
    serial_asyncio = None  # type: ignore
    SERIAL_AVAILABLE = False

# 设备状态枚举
class DeviceStatus(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ACQUIRING = "acquiring"
    ERROR = "error"

# 设备连接信息
@dataclass
class DeviceConnection:
    port: str
    baudrate: int = 460800
    status: DeviceStatus = DeviceStatus.DISCONNECTED
    last_error: Optional[str] = None
    connected_at: Optional[float] = None
    data_count: int = 0
    serial_conn: Optional[Any] = None
    async_transport: Optional[Any] = None
    async_protocol: Optional[Any] = None
    data_buffer: bytes = b''
    data_queue: deque = None
    raw_input_queue: deque = None
    thread: Optional[threading.Thread] = None
    stop_event: threading.Event = None
    data_listeners: Set[Callable] = None
    acquisition_task: Optional[asyncio.Task] = None
    frame_seq: int = 0

    def __post_init__(self):
        self.data_queue = deque(maxlen=1000)
        self.raw_input_queue = deque(maxlen=2000)
        self.stop_event = threading.Event()
        self.data_listeners = set()


class BCIAsyncProtocol(asyncio.Protocol):
    """异步BCI数据协议（从驱动脚本移植）"""
    
    def __init__(self, device_connection: DeviceConnection):
        self.conn = device_connection
        self.buffer = b''
        self.data_received_count = 0
        self.valid_frame_count = 0
        self.transport = None
        self._raw_dump_count = 0  # 记录已转储的原始数据块数
        self._raw_first_bytes = b''  # 记录串口最先收到的原始字节
        self._total_a5_seen = 0  # 累计看到过多少个 \xa5 字节（诊断用）
        
    def connection_made(self, transport):
        self.transport = transport
        serial_port = transport.serial  # serial_asyncio 提供的底层 pyserial 对象
        logger.debug(f"[BCIAsyncProtocol] Connection made to {self.conn.port}")
        logger.debug(f"[BCIAsyncProtocol] Serial details: baudrate={serial_port.baudrate}, "
              f"bytesize={serial_port.bytesize}, parity={serial_port.parity}, "
              f"stopbits={serial_port.stopbits}")
        logger.debug(f"[BCIAsyncProtocol] DTR={serial_port.dtr}, RTS={serial_port.rts}")
        logger.debug(f"[BCIAsyncProtocol] Timeout={serial_port.timeout}, write_timeout={serial_port.write_timeout}")
        # 确保 DTR/RTS 为高电平（某些设备需要这些信号才能正常工作）
        if not serial_port.dtr:
            serial_port.dtr = True
            logger.debug(f"[BCIAsyncProtocol] Set DTR=True")
        if not serial_port.rts:
            serial_port.rts = True
            logger.debug(f"[BCIAsyncProtocol] Set RTS=True")
        
    def data_received(self, data):
        self.data_received_count += 1
        
        # 统计 \xa5 字节出现次数（诊断：设备是否曾发送过二进制帧头）
        a5_count = data.count(0xa5)
        if a5_count > 0:
            self._total_a5_seen += a5_count
            if self.valid_frame_count == 0 and self._total_a5_seen <= 10:
                logger.debug(f"[BCIAsyncProtocol] Found 0xa5 byte! total_a5={self._total_a5_seen}, "
                      f"this chunk has {a5_count}, data hex={data[:40].hex()}")
        
        # 保留最先收到的原始字节用于调试
        if self._raw_dump_count < 5:
            self._raw_first_bytes += data
            self._raw_dump_count += 1
            logger.debug(f"[BCIAsyncProtocol] RAW DUMP #{self._raw_dump_count}: "
                  f"{len(data)} bytes, hex={data[:60].hex()}")
            if len(data) <= 60:
                try:
                    logger.debug(f"[BCIAsyncProtocol] RAW DUMP #{self._raw_dump_count} ascii: "
                          f"{data.decode('ascii', errors='replace')!r}")
                except Exception:
                    pass
        
        self.buffer += data
        
        # 解析完整的数据帧
        while b'\r\n' in self.buffer:
            line, self.buffer = self.buffer.split(b'\r\n', 1)
            
            # 检查是否是有效数据帧（驱动脚本中是\xa5Z\x01）
            if line.startswith(b'\xa5Z\x01') and len(line) == 35:
                self.valid_frame_count += 1
                data_bytes = line[3:]  # 跳过帧头
                
                if len(data_bytes) == 32:  # 8个int，每个4字节
                    try:
                        # 解析8个通道的数据
                        channel_data = struct.unpack('<8i', data_bytes)
                        self.conn.data_count += 1
                        self.conn.frame_seq += 1
                        
                        # 将数据放入队列
                        self.conn.data_queue.append({
                            'seq': self.conn.frame_seq,
                            'timestamp': time.time(),
                            'channels': list(channel_data),
                            'port': self.conn.port,
                            'raw_hex': line.hex()
                        })
                        
                        # 通知监听器
                        if hasattr(self.conn, 'data_listeners'):
                            for listener in self.conn.data_listeners:
                                try:
                                    listener(self.conn.port, channel_data)
                                except Exception as e:
                                    logger.debug(f"[BCIAsyncProtocol] Error in data listener: {e}")
                        
                    except struct.error as e:
                        logger.debug(f"[BCIAsyncProtocol] Error unpacking data: {e}")
            else:
                # 设备在未初始化时会发送 ASCII 文本消息
                if self.valid_frame_count == 0 and self.data_received_count <= 30:
                    try:
                        ascii_text = line.decode('ascii', errors='replace')
                        logger.debug(f"[BCIAsyncProtocol] Non-data frame #{self.data_received_count}: "
                              f"len={len(line)}, first3={line[:3].hex()}, text={ascii_text[:80]!r}")
                    except Exception:
                        logger.debug(f"[BCIAsyncProtocol] Non-data frame #{self.data_received_count}: "
                              f"hex={line[:20].hex()}, len={len(line)}")
    
    def connection_lost(self, exc):
        logger.debug(f"[BCIAsyncProtocol] Connection lost to {self.conn.port}: {exc}")
        self.conn.status = DeviceStatus.DISCONNECTED
        
    def pause_writing(self):
        logger.debug(f"[BCIAsyncProtocol] Pause writing to {self.conn.port}")
        
    def resume_writing(self):
        logger.debug(f"[BCIAsyncProtocol] Resume writing to {self.conn.port}")


class RealDeviceManager:
    """真实设备管理器"""
    
    def __init__(self):
        self._connections: Dict[str, DeviceConnection] = {}
        self._lock = threading.RLock()
        self._data_listeners: Set[callable] = set()
        self._async_loop: Optional[asyncio.AbstractEventLoop] = None
        self._async_thread: Optional[threading.Thread] = None
        self._async_loop_ready = threading.Event()

    def _ensure_async_loop(self) -> asyncio.AbstractEventLoop:
        """确保存在长期运行的后台事件循环，避免串口连接绑定到一次性 asyncio.run。"""
        with self._lock:
            if self._async_loop and self._async_loop.is_running() and self._async_thread and self._async_thread.is_alive():
                return self._async_loop

            self._async_loop_ready.clear()

            def _loop_runner():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                self._async_loop = loop
                self._async_loop_ready.set()
                loop.run_forever()

            self._async_thread = threading.Thread(target=_loop_runner, name='real-device-async-loop', daemon=True)
            self._async_thread.start()

        self._async_loop_ready.wait(timeout=3.0)
        if not self._async_loop or not self._async_loop.is_running():
            raise RuntimeError('Failed to start background async loop for real device manager')
        return self._async_loop

    def _run_coro_on_async_loop(self, coro):
        """将协程提交到长期运行的后台事件循环并阻塞等待结果。"""
        loop = self._ensure_async_loop()
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result(timeout=15.0)

    @staticmethod
    def _run_async_blocking(coro):
        """在同步上下文中阻塞执行协程。

        - 无运行中的事件循环：直接 asyncio.run
        - 有运行中的事件循环：在新线程中创建私有事件循环执行
        """
        try:
            running_loop = asyncio.get_running_loop()
            if running_loop and running_loop.is_running():
                result_holder = {'result': None, 'error': None}

                def _thread_runner():
                    try:
                        result_holder['result'] = asyncio.run(coro)
                    except Exception as ex:
                        result_holder['error'] = ex

                t = threading.Thread(target=_thread_runner, daemon=True)
                t.start()
                t.join()

                if result_holder['error'] is not None:
                    raise result_holder['error']
                return result_holder['result']
        except RuntimeError:
            pass

        return asyncio.run(coro)

    @staticmethod
    def get_ch340_ports() -> List[str]:
        """获取CH340/CH341串口设备列表（从驱动脚本移植）
        
        Returns:
            可用的CH340/CH341设备端口列表
        """
        ch340_ports = []
        ports = serial.tools.list_ports.comports()
        
        current_system = platform.system()
        logger.debug(f"[RealDeviceManager] Scanning for CH340 devices on {current_system}...")
        
        for port in ports:
            # 获取设备信息
            device_name = port.device
            description = (port.description or '').upper()
            manufacturer = (port.manufacturer or '').upper()
            product = (port.product or '').upper()
            hwid = (port.hwid or '').upper()
            
            # 获取VID/PID（如果可用）
            vid = getattr(port, 'vid', None)
            pid = getattr(port, 'pid', None)
            
            # CH340/CH341检测逻辑（从驱动脚本移植）
            is_ch340 = False
            detection_method = ""
            
            # 方法1: 检查描述中的CH340/CH341（最直接）
            if 'CH340' in description or 'CH341' in description:
                is_ch340 = True
                detection_method = "Description contains CH340/CH341"
            
            # 方法2: 检查VID/PID (CH340的VID通常是0x1A86)
            elif vid == 0x1A86:  # QinHeng Electronics (CH340制造商)
                is_ch340 = True
                detection_method = f"VID matches CH340 (0x1A86)"
            
            # 方法3: 检查HWID中的1A86 (Linux常见)
            elif '1A86' in hwid:
                is_ch340 = True
                detection_method = "HWID contains 1A86 (CH340 VID)"
            
            # 方法4: 平台特定的检测
            elif current_system == 'Linux':
                # Linux下的CH340设备通常显示为"USB SERIAL"或"USB Serial"
                device_lower = device_name.lower()
                
                # 检查是否是USB串口设备
                if device_lower.startswith('/dev/ttyusb') or device_lower.startswith('/dev/ttyacm'):
                    # 检查描述是否包含USB串口相关关键词
                    usb_keywords = ['USB SERIAL', 'USB_SERIAL', 'USB Serial', 'USB-Serial']
                    if any(keyword in description for keyword in usb_keywords):
                        is_ch340 = True
                        detection_method = "Linux USB serial device with USB SERIAL description"
                    # 如果没有明确描述，但设备名是ttyUSB且HWID包含USB，也认为是CH340
                    elif device_lower.startswith('/dev/ttyusb') and 'USB' in hwid:
                        is_ch340 = True
                        detection_method = "Linux ttyUSB device with USB in HWID"
            
            elif current_system == 'Windows':
                # Windows下的检测
                if device_name.upper().startswith('COM'):
                    # Windows下COM端口且描述包含USB
                    if 'USB' in description and ('SERIAL' in description or 'CH340' in hwid):
                        is_ch340 = True
                        detection_method = "Windows COM port with USB serial description"
            
            if is_ch340:
                ch340_ports.append(device_name)
                logger.debug(f"[RealDeviceManager] Found CH340 device: {device_name}")
                logger.debug(f"  Detection method: {detection_method}")
                logger.debug(f"  Description: {description}")
                logger.debug(f"  Manufacturer: {manufacturer}")
                logger.debug(f"  Product: {product}")
                logger.debug(f"  HWID: {hwid}")
                logger.debug(f"  VID: {hex(vid) if vid else 'N/A'}")
                logger.debug(f"  PID: {hex(pid) if pid else 'N/A'}")
        
        logger.debug(f"[RealDeviceManager] Found {len(ch340_ports)} CH340 device(s) on {current_system}")
        return ch340_ports
    
    @staticmethod
    def _is_usb_serial_port(port_info) -> bool:
        """判断是否为USB串口设备（跨平台）"""
        device = (getattr(port_info, 'device', '') or '').lower()
        description = (getattr(port_info, 'description', '') or '').upper()
        manufacturer = (getattr(port_info, 'manufacturer', '') or '').upper()
        product = (getattr(port_info, 'product', '') or '').upper()
        hwid = (getattr(port_info, 'hwid', '') or '').upper()
        
        # 获取VID/PID
        vid = getattr(port_info, 'vid', None)
        pid = getattr(port_info, 'pid', None)

        # 方法1: pyserial 能识别到 USB VID/PID 时最可靠
        if vid is not None and pid is not None:
            return True

        # 方法2: Linux / macOS 常见 USB 串口设备名
        usb_device_prefixes = ('/dev/ttyusb', '/dev/ttyacm', '/dev/cu.usbserial', '/dev/cu.usbmodem')
        if device.startswith(usb_device_prefixes):
            return True

        # 方法3: 检查是否为CH340/CH341设备
        # CH340的VID通常是0x1A86 (QinHeng Electronics)
        if vid == 0x1A86:
            return True
        
        # 检查描述或HWID中的CH340/CH341
        if 'CH340' in description or 'CH341' in description:
            return True
        
        # 检查HWID中的1A86 (Linux常见)
        if '1A86' in hwid:
            return True

        # 方法4: 兜底文本判断（Windows/Linux）
        text_blob = f"{description} {manufacturer} {product} {hwid}"
        return 'USB' in text_blob

    @staticmethod
    def _open_serial(port: str, baudrate: int) -> serial.Serial:
        """打开串口连接"""
        return serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=1.0,
            write_timeout=1.0
        )

    @staticmethod
    def _try_fix_linux_serial_permission(port: str) -> Tuple[bool, str]:
        """尝试通过 sudo -A 修复 Linux 串口权限"""
        askpass = os.environ.get('SUDO_ASKPASS') or os.environ.get('SSH_ASKPASS')
        if not askpass:
            return False, 'SUDO_ASKPASS/SSH_ASKPASS 未配置'

        try:
            result = subprocess.run(
                ['sudo', '-A', 'chmod', 'a+rw', port],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return True, ''
            err = (result.stderr or result.stdout or '').strip()
            return False, err or f'sudo 返回码 {result.returncode}'
        except Exception as e:
            return False, str(e)
        
    def scan_ports(self) -> List[Dict[str, Any]]:
        """扫描可用的串口设备
        
        Returns:
            可用串口设备列表，每个设备包含端口、描述等信息
        """
        ports = []

        def _to_hex_or_na(value: Any) -> str:
            """将VID/PID安全转换为16进制字符串"""
            if value is None:
                return 'N/A'
            try:
                return hex(int(value))
            except Exception:
                return str(value)
        
        try:
            # 使用新的CH340检测方法
            ch340_ports = self.get_ch340_ports()
            available_ports = serial.tools.list_ports.comports()

            logger.debug(f"[RealDeviceManager] scan_ports: total system ports={len(available_ports)}, ch340_ports={ch340_ports}")
            
            for port_info in available_ports:
                device_name = port_info.device
                
                # 检查是否是CH340设备
                is_ch340 = device_name in ch340_ports
                
                # 如果不是CH340，检查是否为其他USB串口设备
                if not is_ch340 and not self._is_usb_serial_port(port_info):
                    continue
                
                port_data = {
                    'port': device_name,
                    'description': port_info.description or '',
                    'manufacturer': port_info.manufacturer or '',
                    'product': port_info.product or '',
                    'hwid': port_info.hwid or '',
                    'is_ch340': is_ch340,
                    'is_available': True,
                    'vid': _to_hex_or_na(getattr(port_info, 'vid', None)),
                    'pid': _to_hex_or_na(getattr(port_info, 'pid', None))
                }
                ports.append(port_data)
                logger.debug(
                    f"[RealDeviceManager] scan_ports include: {device_name}, "
                    f"is_ch340={is_ch340}, vid={port_data['vid']}, pid={port_data['pid']}, "
                    f"desc={port_data['description']}"
                )

            logger.debug(f"[RealDeviceManager] scan_ports result count={len(ports)}")
            if not ports:
                logger.debug("[RealDeviceManager] scan_ports result is empty after filtering")
                
        except Exception as e:
            logger.debug(f"[RealDeviceManager] Error scanning ports: {e}")
            import traceback
            traceback.print_exc()
                
        return ports
    
    def connect_device(self, port: str, baudrate: int = 460800, use_async: bool = True) -> bool:
        """连接设备
        
        Args:
            port: 串口端口
            baudrate: 波特率
            use_async: 是否使用异步连接（推荐）
            
        Returns:
            连接是否成功
        """
        with self._lock:
            if port in self._connections:
                conn = self._connections[port]
                if conn.status in [DeviceStatus.CONNECTED, DeviceStatus.ACQUIRING]:
                    logger.debug(f"[RealDeviceManager] Device already connected on {port}")
                    return True
                elif conn.status == DeviceStatus.CONNECTING:
                    logger.debug(f"[RealDeviceManager] Device already connecting on {port}")
                    return False
            
            logger.debug(f"[RealDeviceManager] Connecting to device on {port} at {baudrate} baud (async={use_async})")
            
            # 创建连接对象
            conn = DeviceConnection(port=port, baudrate=baudrate, status=DeviceStatus.CONNECTING)
            self._connections[port] = conn
            
            try:
                if use_async:
                    # 异步连接
                    ok = self._run_coro_on_async_loop(self._connect_device_async(conn))
                    logger.debug(f"[RealDeviceManager] Async connect completed for {port}: success={ok}, status={conn.status.value}")
                    return bool(ok)
                else:
                    # 同步连接（向后兼容）
                    return self._connect_device_sync(conn)
            except Exception as e:
                conn.status = DeviceStatus.ERROR
                conn.last_error = str(e)
                logger.debug(f"[RealDeviceManager] Unexpected error when connecting to {port}: {e}")
                return False
    
    def _connect_device_sync(self, conn: DeviceConnection) -> bool:
        """同步连接设备（向后兼容）"""
        try:
            # 尝试连接串口
            serial_conn = self._open_serial(conn.port, conn.baudrate)
            
            if serial_conn.is_open:
                conn.serial_conn = serial_conn
                conn.status = DeviceStatus.CONNECTED
                conn.connected_at = time.time()
                conn.last_error = None
                
                logger.debug(f"[RealDeviceManager] Successfully connected to device on {conn.port}")
                
                # 初始化设备
                self._initialize_device(conn)
                
                return True
            else:
                conn.status = DeviceStatus.ERROR
                conn.last_error = "Failed to open serial port"
                logger.debug(f"[RealDeviceManager] Failed to open serial port {conn.port}")
                return False
                
        except serial.SerialException as e:
            error_msg = str(e)
            is_permission_error = ('Permission denied' in error_msg) or ('Access is denied' in error_msg)

            if is_permission_error and platform.system() == 'Linux':
                fixed, fix_reason = self._try_fix_linux_serial_permission(conn.port)
                if fixed:
                    try:
                        serial_conn = self._open_serial(conn.port, conn.baudrate)
                        if serial_conn.is_open:
                            conn.serial_conn = serial_conn
                            conn.status = DeviceStatus.CONNECTED
                            conn.connected_at = time.time()
                            conn.last_error = None
                            logger.debug(f"[RealDeviceManager] Connected after sudo askpass permission fix: {conn.port}")
                            self._initialize_device(conn)
                            return True
                    except Exception as retry_e:
                        error_msg = f"{error_msg}; retry failed: {retry_e}"
                else:
                    error_msg = (
                        f"{error_msg}; 权限修复失败: {fix_reason}. "
                        "请配置 SUDO_ASKPASS 后重试，或将当前用户加入 dialout/uucp 组。"
                    )

            elif is_permission_error and platform.system() == 'Windows':
                error_msg = (
                    f"{error_msg}; 请以管理员身份运行后端服务或终端后重试。"
                )

            conn.status = DeviceStatus.ERROR
            conn.last_error = error_msg
            logger.debug(f"[RealDeviceManager] SerialException when connecting to {conn.port}: {error_msg}")
            return False
        except Exception as e:
            conn.status = DeviceStatus.ERROR
            conn.last_error = str(e)
            logger.debug(f"[RealDeviceManager] Unexpected error when connecting to {conn.port}: {e}")
            return False
    
    async def _connect_device_async(self, conn: DeviceConnection) -> bool:
        """异步连接设备（使用serial_asyncio）"""
        try:
            loop = asyncio.get_running_loop()
            
            logger.debug(f"[RealDeviceManager] Creating async serial connection for {conn.port}...")
            transport, protocol = await serial_asyncio.create_serial_connection(
                loop, 
                lambda: BCIAsyncProtocol(conn), 
                conn.port, 
                baudrate=conn.baudrate
            )
            
            conn.async_transport = transport
            conn.async_protocol = protocol
            conn.status = DeviceStatus.CONNECTED
            conn.connected_at = time.time()
            conn.last_error = None
            
            logger.debug(f"[RealDeviceManager] Successfully connected to device on {conn.port} (async)")
            
            # ===== 关键调试：验证 transport.write 实际写入了数据 =====
            serial_port = transport.serial
            logger.debug(f"[RealDeviceManager] Transport type: {type(transport).__name__}")
            logger.debug(f"[RealDeviceManager] Serial port is_open: {serial_port.is_open}")
            
            # 与驱动脚本完全一致：连接后立即发送初始化命令
            # 驱动脚本 main() 中 create_serial_connection 后立即 create_task(init_eeg_acquiring)
            logger.debug(f"[RealDeviceManager] Sending init commands immediately...")
            for i in range(3):
                cmd = b"C005\r\n"
                written = transport.write(cmd)
                logger.debug(f"[RealDeviceManager] C005 #{i+1}: write returned {written}, cmd={cmd!r}")
                await asyncio.sleep(0.05)
            
            for i in range(2):
                cmd = b"C002\r\n"
                written = transport.write(cmd)
                logger.debug(f"[RealDeviceManager] C002 #{i+1}: write returned {written}, cmd={cmd!r}")
                await asyncio.sleep(0.01)
            
            logger.debug(f"[RealDeviceManager] Init commands sent to {conn.port}")
            
            # 等待设备响应
            for check in range(30):  # 最多等 3 秒
                await asyncio.sleep(0.1)
                if protocol.valid_frame_count > 0:
                    logger.debug(f"[RealDeviceManager] ✓ Got valid frames after init on {conn.port} "
                          f"(after {(check+1)*0.1:.1f}s)")
                    break
                # 每 0.5s 汇报一次状态
                if (check + 1) % 5 == 0:
                    # 扫描 buffer 中是否有 \xa5 字节
                    has_a5 = b'\xa5' in protocol.buffer
                    logger.debug(f"[RealDeviceManager] Waiting... received={protocol.data_received_count}, "
                          f"valid={protocol.valid_frame_count}, "
                          f"buffer_len={len(protocol.buffer)}, has_0xa5_in_buffer={has_a5}")
            
            if protocol.valid_frame_count == 0:
                # 最终诊断
                logger.debug(f"[RealDeviceManager] ⚠ NO valid frames on {conn.port}")
                logger.debug(f"[RealDeviceManager]   Total received callbacks: {protocol.data_received_count}")
                logger.debug(f"[RealDeviceManager]   Valid frames: {protocol.valid_frame_count}")
                logger.debug(f"[RealDeviceManager]   Total 0xa5 bytes seen: {protocol._total_a5_seen}")
                logger.debug(f"[RealDeviceManager]   Raw first bytes (hex): {protocol._raw_first_bytes[:100].hex()}")
                logger.debug(f"[RealDeviceManager]   Buffer remaining: {len(protocol.buffer)} bytes")
                if protocol.buffer:
                    logger.debug(f"[RealDeviceManager]   Buffer tail (hex): {protocol.buffer[-50:].hex()}")
            
            return True
            
        except Exception as e:
            error_msg = str(e)
            is_permission_error = ('Permission denied' in error_msg) or ('Access is denied' in error_msg)

            if is_permission_error and platform.system() == 'Linux':
                fixed, fix_reason = self._try_fix_linux_serial_permission(conn.port)
                if fixed:
                    try:
                        loop = asyncio.get_running_loop()
                        transport, protocol = await serial_asyncio.create_serial_connection(
                            loop, 
                            lambda: BCIAsyncProtocol(conn), 
                            conn.port, 
                            baudrate=conn.baudrate
                        )
                        
                        conn.async_transport = transport
                        conn.async_protocol = protocol
                        conn.status = DeviceStatus.CONNECTED
                        conn.connected_at = time.time()
                        conn.last_error = None
                        logger.debug(f"[RealDeviceManager] Connected after sudo askpass permission fix: {conn.port}")
                        for i in range(3):
                            transport.write(b"C005\r\n")
                            await asyncio.sleep(0.05)
                        for i in range(2):
                            transport.write(b"C002\r\n")
                            await asyncio.sleep(0.01)
                        logger.debug(f"[RealDeviceManager] Init commands sent after permission fix on {conn.port}")
                        return True
                    except Exception as retry_e:
                        error_msg = f"{error_msg}; retry failed: {retry_e}"
                else:
                    error_msg = (
                        f"{error_msg}; 权限修复失败: {fix_reason}. "
                        "请配置 SUDO_ASKPASS 后重试，或将当前用户加入 dialout/uucp 组。"
                    )

            elif is_permission_error and platform.system() == 'Windows':
                error_msg = (
                    f"{error_msg}; 请以管理员身份运行后端服务或终端后重试。"
                )

            conn.status = DeviceStatus.ERROR
            conn.last_error = error_msg
            logger.debug(f"[RealDeviceManager] Error when connecting to {conn.port}: {error_msg}")
            return False
    
    def _initialize_device(self, conn: DeviceConnection):
        """同步初始化设备（发送初始化命令）"""
        try:
            if not conn.serial_conn:
                return
                
            # 发送初始化命令序列
            init_commands = [
                b'C005\r\n',  # 初始化命令1
                b'C005\r\n',
                b'C005\r\n',
                b'C002\r\n',  # 初始化命令2
                b'C002\r\n',
            ]
            
            for cmd in init_commands:
                conn.serial_conn.write(cmd)
                time.sleep(0.05)
                
            logger.debug(f"[RealDeviceManager] Device initialization commands sent to {conn.port}")
            
        except Exception as e:
            logger.debug(f"[RealDeviceManager] Error initializing device on {conn.port}: {e}")
            conn.last_error = f"Initialization error: {e}"
    
    def start_acquisition(self, port: str, use_async: bool = True) -> bool:
        """开始数据采集
        
        Args:
            port: 串口端口
            use_async: 是否使用异步采集（推荐）
            
        Returns:
            是否成功启动采集
        """
        with self._lock:
            if port not in self._connections:
                logger.debug(f"[RealDeviceManager] Device not connected on {port}")
                return False
                
            conn = self._connections[port]
            
            if conn.status != DeviceStatus.CONNECTED:
                logger.debug(f"[RealDeviceManager] Device not in connected state on {port}")
                return False
                
            if conn.thread and conn.thread.is_alive():
                logger.debug(f"[RealDeviceManager] Acquisition already running on {port}")
                return True
                
            if use_async and conn.async_transport:
                logger.debug(f"[RealDeviceManager] Starting async data acquisition on {port}")
                # 异步采集不需要单独的线程，协议会自动处理
                conn.status = DeviceStatus.ACQUIRING
                return True
            else:
                logger.debug(f"[RealDeviceManager] Starting sync data acquisition on {port}")
                
                # 创建数据采集线程
                conn.stop_event.clear()
                conn.thread = threading.Thread(
                    target=self._acquisition_thread,
                    args=(conn,),
                    name=f"device-acq-{port}",
                    daemon=True
                )
                conn.thread.start()
                
                conn.status = DeviceStatus.ACQUIRING
                return True
    
    def _acquisition_thread(self, conn: DeviceConnection):
        """数据采集线程"""
        logger.debug(f"[RealDeviceManager] Acquisition thread started for {conn.port}")
        
        try:
            while not conn.stop_event.is_set() and conn.serial_conn and conn.serial_conn.is_open:
                try:
                    # 读取数据
                    if conn.serial_conn.in_waiting > 0:
                        data = conn.serial_conn.read(conn.serial_conn.in_waiting)
                        if data:
                            conn.raw_input_queue.append({
                                'timestamp': time.time(),
                                'raw_hex': data.hex(),
                                'raw_text': data.decode('latin-1', errors='replace')
                            })
                        conn.data_buffer += data
                        
                        # 解析完整的数据帧
                        while b'\r\n' in conn.data_buffer:
                            line, conn.data_buffer = conn.data_buffer.split(b'\r\n', 1)
                            
                            # 检查是否是有效数据帧
                            if line.startswith(b'\xa5Z\x01') and len(line) == 35:
                                # 提取数据部分（跳过帧头）
                                data_bytes = line[3:]  # 跳过3字节的帧头
                                
                                if len(data_bytes) == 32:  # 8个int，每个4字节
                                    # 解析8个通道的数据
                                    try:
                                        channel_data = struct.unpack('<8i', data_bytes)
                                        conn.data_count += 1
                                        conn.frame_seq += 1
                                        
                                        # 将数据放入队列
                                        conn.data_queue.append({
                                            'seq': conn.frame_seq,
                                            'timestamp': time.time(),
                                            'channels': list(channel_data),
                                            'port': conn.port,
                                            'raw_hex': line.hex()
                                        })
                                        
                                        # 通知监听器
                                        self._notify_data_listeners(conn.port, channel_data)
                                        
                                    except struct.error as e:
                                        logger.debug(f"[RealDeviceManager] Error unpacking data from {conn.port}: {e}")
                
                except serial.SerialException as e:
                    logger.debug(f"[RealDeviceManager] Serial error on {conn.port}: {e}")
                    conn.last_error = str(e)
                    conn.status = DeviceStatus.ERROR
                    break
                except Exception as e:
                    logger.debug(f"[RealDeviceManager] Error in acquisition thread for {conn.port}: {e}")
                    # 继续运行，不中断线程
                
                # 短暂休眠以避免CPU占用过高
                time.sleep(0.001)
                
        except Exception as e:
            logger.debug(f"[RealDeviceManager] Acquisition thread crashed for {conn.port}: {e}")
            conn.status = DeviceStatus.ERROR
            conn.last_error = str(e)
        finally:
            logger.debug(f"[RealDeviceManager] Acquisition thread stopped for {conn.port}")
    
    def stop_acquisition(self, port: str) -> bool:
        """停止数据采集
        
        Args:
            port: 串口端口
            
        Returns:
            是否成功停止采集
        """
        with self._lock:
            if port not in self._connections:
                return False
                
            conn = self._connections[port]
            
            if conn.status != DeviceStatus.ACQUIRING:
                return True
                
            logger.debug(f"[RealDeviceManager] Stopping data acquisition on {port}")
            
            # 停止采集线程
            if conn.stop_event:
                conn.stop_event.set()
                
            if conn.thread and conn.thread.is_alive():
                conn.thread.join(timeout=2.0)
                
            conn.status = DeviceStatus.CONNECTED
            return True
    
    def disconnect_device(self, port: str) -> bool:
        """断开设备连接
        
        Args:
            port: 串口端口
            
        Returns:
            是否成功断开连接
        """
        with self._lock:
            if port not in self._connections:
                return False
                
            conn = self._connections[port]
            
            # 先停止采集
            if conn.status == DeviceStatus.ACQUIRING:
                self.stop_acquisition(port)
            
            logger.debug(f"[RealDeviceManager] Disconnecting device on {port}")
            
            # 关闭串口连接
            if conn.serial_conn and conn.serial_conn.is_open:
                try:
                    conn.serial_conn.close()
                except Exception as e:
                    logger.debug(f"[RealDeviceManager] Error closing serial connection on {port}: {e}")

            # 关闭异步连接
            if conn.async_transport:
                try:
                    if self._async_loop and self._async_loop.is_running():
                        self._async_loop.call_soon_threadsafe(conn.async_transport.close)
                    else:
                        conn.async_transport.close()
                except Exception as e:
                    logger.debug(f"[RealDeviceManager] Error closing async transport on {port}: {e}")
            
            # 清理连接对象
            del self._connections[port]
            
            return True
    
    def get_device_status(self, port: str) -> Optional[Dict[str, Any]]:
        """获取设备状态
        
        Args:
            port: 串口端口
            
        Returns:
            设备状态信息字典
        """
        with self._lock:
            if port not in self._connections:
                return None
                
            conn = self._connections[port]
            
            return {
                'port': conn.port,
                'status': conn.status.value,
                'baudrate': conn.baudrate,
                'last_error': conn.last_error,
                'connected_at': conn.connected_at,
                'data_count': conn.data_count,
                'queue_size': len(conn.data_queue) if conn.data_queue else 0
            }
    
    def get_latest_data(self, port: str, count: int = 1) -> List[Dict[str, Any]]:
        """获取最新的数据
        
        Args:
            port: 串口端口
            count: 要获取的数据数量
            
        Returns:
            最新的数据列表
        """
        with self._lock:
            if port not in self._connections:
                return []
                
            conn = self._connections[port]
            
            if not conn.data_queue:
                return []
                
            # 从队列中获取最新的数据
            data_list = list(conn.data_queue)
            return data_list[-count:] if data_list else []

    def drain_data(self, port: str, count: int = 200) -> List[Dict[str, Any]]:
        """从设备队列按时间顺序出队数据，供实时图引擎消费。"""
        with self._lock:
            if port not in self._connections:
                return []

            conn = self._connections[port]
            if not conn.data_queue:
                return []

            out: List[Dict[str, Any]] = []
            max_count = max(1, int(count))
            for _ in range(max_count):
                if not conn.data_queue:
                    break
                out.append(conn.data_queue.popleft())
            return out

    def get_latest_raw_input(self, port: str, count: int = 100) -> List[Dict[str, Any]]:
        """获取串口原始输入（按读取块）"""
        with self._lock:
            if port not in self._connections:
                return []

            conn = self._connections[port]
            if not conn.raw_input_queue:
                return []

            raw_list = list(conn.raw_input_queue)
            return raw_list[-count:] if raw_list else []
    
    def get_all_connected_devices(self) -> List[Dict[str, Any]]:
        """获取所有已连接的设备
        
        Returns:
            已连接设备列表
        """
        with self._lock:
            devices = []
            for port, conn in self._connections.items():
                devices.append(self.get_device_status(port))
            return [d for d in devices if d is not None]
    
    def add_data_listener(self, listener: callable):
        """添加数据监听器
        
        Args:
            listener: 监听器函数，接收 (port, channel_data) 参数
        """
        with self._lock:
            self._data_listeners.add(listener)
    
    def remove_data_listener(self, listener: callable):
        """移除数据监听器
        
        Args:
            listener: 要移除的监听器函数
        """
        with self._lock:
            self._data_listeners.discard(listener)
    
    def _notify_data_listeners(self, port: str, channel_data: Tuple):
        """通知所有数据监听器
        
        Args:
            port: 数据来源端口
            channel_data: 通道数据
        """
        for listener in list(self._data_listeners):
            try:
                listener(port, channel_data)
            except Exception as e:
                logger.debug(f"[RealDeviceManager] Error in data listener: {e}")


# 全局设备管理器实例
_real_device_manager = None  # 延迟初始化，避免 Windows 上导入即报错


def _ensure_serial_available():
    """检查串口支持是否可用，不可用则抛出 ImportError"""
    if not SERIAL_AVAILABLE:
        raise ImportError(
            "pyserial/serial_asyncio is not available on this platform (Windows). "
            "Real device management is only supported on Linux/macOS."
        )


def get_real_device_manager() -> RealDeviceManager:
    """获取真实设备管理器实例"""
    global _real_device_manager
    if _real_device_manager is None:
        _real_device_manager = RealDeviceManager()
    return _real_device_manager


def scan_serial_ports() -> List[Dict[str, Any]]:
    """扫描串口端口（API接口）"""
    _ensure_serial_available()
    return get_real_device_manager().scan_ports()


def connect_real_device(port: str, baudrate: int = 460800) -> Dict[str, Any]:
    """连接真实设备（API接口）"""
    _ensure_serial_available()
    manager = get_real_device_manager()
    success = manager.connect_device(port, baudrate)
    
    if success:
        status = manager.get_device_status(port)
        return {
            'success': True,
            'device': status
        }
    else:
        status = manager.get_device_status(port)
        detailed_error = status.get('last_error') if status else None
        return {
            'success': False,
            'error': detailed_error or f"Failed to connect to device on {port}"
        }


def start_device_acquisition(port: str) -> Dict[str, Any]:
    """开始设备数据采集（API接口）"""
    _ensure_serial_available()
    manager = get_real_device_manager()
    success = manager.start_acquisition(port)
    
    if success:
        return {
            'success': True,
            'message': f"Data acquisition started on {port}"
        }
    else:
        return {
            'success': False,
            'error': f"Failed to start acquisition on {port}"
        }


def stop_device_acquisition(port: str) -> Dict[str, Any]:
    """停止设备数据采集（API接口）"""
    _ensure_serial_available()
    manager = get_real_device_manager()
    success = manager.stop_acquisition(port)
    
    if success:
        return {
            'success': True,
            'message': f"Data acquisition stopped on {port}"
        }
    else:
        return {
            'success': False,
            'error': f"Failed to stop acquisition on {port}"
        }


def disconnect_real_device(port: str) -> Dict[str, Any]:
    """断开真实设备连接（API接口）"""
    _ensure_serial_available()
    manager = get_real_device_manager()
    success = manager.disconnect_device(port)
    
    if success:
        return {
            'success': True,
            'message': f"Device disconnected on {port}"
        }
    else:
        return {
            'success': False,
            'error': f"Failed to disconnect device on {port}"
        }


def get_device_status(port: str) -> Dict[str, Any]:
    """获取设备状态（API接口）"""
    manager = get_real_device_manager()
    status = manager.get_device_status(port)
    
    if status:
        return {
            'success': True,
            'device': status
        }
    else:
        return {
            'success': False,
            'error': f"Device not found on {port}"
        }


def get_all_connected_devices() -> Dict[str, Any]:
    """获取所有已连接的设备（API接口）"""
    manager = get_real_device_manager()
    devices = manager.get_all_connected_devices()
    
    return {
        'success': True,
        'devices': devices
    }


def get_debug_output(port: Optional[str] = None, count: int = 100) -> Dict[str, Any]:
    """获取串口调试输出（最近解析帧）"""
    manager = get_real_device_manager()

    if port:
        samples = manager.get_latest_data(port, count=count)
        raw_inputs = manager.get_latest_raw_input(port, count=count)
        return {
            'success': True,
            'ports': [{
                'port': port,
                'samples': samples,
                'count': len(samples),
                'raw_inputs': raw_inputs,
                'raw_input_count': len(raw_inputs)
            }],
            'total_samples': len(samples)
        }

    devices = manager.get_all_connected_devices()
    result_ports = []
    total = 0
    for dev in devices:
        dev_port = dev.get('port')
        if not dev_port:
            continue
        samples = manager.get_latest_data(dev_port, count=count)
        raw_inputs = manager.get_latest_raw_input(dev_port, count=count)
        total += len(samples)
        result_ports.append({
            'port': dev_port,
            'samples': samples,
            'count': len(samples),
            'raw_inputs': raw_inputs,
            'raw_input_count': len(raw_inputs)
        })

    return {
        'success': True,
        'ports': result_ports,
        'total_samples': total
    }