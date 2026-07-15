"""CH340 EEG 设备驱动（单文件）。

实现 DeviceDriver 抽象类，管理 CH340/CH341 USB 串口 EEG 设备的发现、连接、数据采集。

帧协议：
  帧头 0xA5 0x5A 0x01 (3B) + 载荷 8×int32-LE (32B) + 帧尾 CRLF (2B) = 35B/帧
"""

from __future__ import annotations

import asyncio
import logging
import os
import platform
import struct
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .base import DeviceDriver, DeviceFrame, DeviceMeta, DeviceStatus

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------- #
#  协议常量
# ---------------------------------------------------------------------- #
FRAME_HEADER = b'\xa5Z\x01'
FRAME_TAIL = b'\r\n'
FRAME_TOTAL_LEN = 35          # 3 头 + 32 数据 + 2 尾
FRAME_PAYLOAD_FMT = '<8i'     # 8×int32 little-endian
FRAME_PAYLOAD_LEN = 32
CHANNEL_COUNT = 8
DEFAULT_BAUDRATE = 460800
DEFAULT_SAMPLE_RATE = 250

# pyserial 依赖 termios（Unix-only），Windows 上优雅降级
try:
    import serial
    import serial.tools.list_ports
    import serial_asyncio
    SERIAL_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    serial = None       # type: ignore
    serial_asyncio = None  # type: ignore
    SERIAL_AVAILABLE = False


# ---------------------------------------------------------------------- #
#  内部数据结构
# ---------------------------------------------------------------------- #
@dataclass
class _Connection:
    """驱动内部连接状态容器。"""
    port: str
    baudrate: int = DEFAULT_BAUDRATE
    status: DeviceStatus = DeviceStatus.DISCONNECTED
    last_error: Optional[str] = None
    connected_at: Optional[float] = None
    data_count: int = 0
    frame_seq: int = 0
    serial_conn: Optional[Any] = None
    async_transport: Optional[Any] = None
    async_protocol: Optional[Any] = None
    data_buffer: bytes = b''
    data_queue: deque = field(default_factory=lambda: deque(maxlen=1000))
    raw_input_queue: deque = field(default_factory=lambda: deque(maxlen=2000))
    thread: Optional[threading.Thread] = None
    stop_event: threading.Event = field(default_factory=threading.Event)
    data_listeners: Set[Callable] = field(default_factory=set)


# ---------------------------------------------------------------------- #
#  异步帧解析协议
# ---------------------------------------------------------------------- #
class _BCIAsyncProtocol(asyncio.Protocol):
    """异步 BCI 数据帧解析协议（从驱动脚本移植）。"""

    def __init__(self, conn: _Connection):
        self.conn = conn
        self.buffer = b''
        self.data_received_count = 0
        self.valid_frame_count = 0
        self.transport = None
        self._raw_dump_count = 0
        self._raw_first_bytes = b''
        self._total_a5_seen = 0

    def connection_made(self, transport):
        self.transport = transport
        sp = transport.serial
        logger.debug('[BCI] Connected %s  baud=%d  dtr=%s  rts=%s',
                     self.conn.port, sp.baudrate, sp.dtr, sp.rts)
        if not sp.dtr:
            sp.dtr = True
        if not sp.rts:
            sp.rts = True

    def data_received(self, data: bytes):
        self.data_received_count += 1

        a5_count = data.count(0xA5)
        if a5_count > 0:
            self._total_a5_seen += a5_count

        if self._raw_dump_count < 5:
            self._raw_first_bytes += data
            self._raw_dump_count += 1
            logger.debug('[BCI] RAW #%d  %d bytes  hex=%s', self._raw_dump_count, len(data), data[:60].hex())

        self.buffer += data
        while FRAME_TAIL in self.buffer:
            line, self.buffer = self.buffer.split(FRAME_TAIL, 1)

            if line.startswith(FRAME_HEADER) and len(line) == FRAME_TOTAL_LEN - len(FRAME_TAIL):
                self._parse_frame(line)
            elif self.valid_frame_count == 0 and self.data_received_count <= 30:
                logger.debug('[BCI] Non-data frame #%d  len=%d  text=%r',
                             self.data_received_count, len(line), line[:80])

    def _parse_frame(self, line: bytes):
        data_bytes = line[len(FRAME_HEADER):]
        if len(data_bytes) != FRAME_PAYLOAD_LEN:
            return
        try:
            channels = list(struct.unpack(FRAME_PAYLOAD_FMT, data_bytes))
        except struct.error as exc:
            logger.debug('[BCI] Unpack error: %s', exc)
            return

        self.valid_frame_count += 1
        self.conn.data_count += 1
        self.conn.frame_seq += 1
        self.conn.data_queue.append({
            'seq': self.conn.frame_seq,
            'timestamp': time.time(),
            'channels': channels,
            'port': self.conn.port,
            'raw_hex': line.hex(),
        })
        for listener in list(self.conn.data_listeners):
            try:
                listener(self.conn.port, channels)
            except Exception as exc:
                logger.debug('[BCI] Listener error: %s', exc)

    def connection_lost(self, exc):
        logger.debug('[BCI] Connection lost %s: %s', self.conn.port, exc)
        self.conn.status = DeviceStatus.DISCONNECTED


# ---------------------------------------------------------------------- #
#  驱动实现
# ---------------------------------------------------------------------- #
class Ch340EegDriver(DeviceDriver):
    """CH340 EEG 串口设备驱动。"""

    def __init__(self):
        self._connections: Dict[str, _Connection] = {}
        self._lock = threading.RLock()
        self._async_loop: Optional[asyncio.AbstractEventLoop] = None
        self._async_thread: Optional[threading.Thread] = None
        self._async_loop_ready = threading.Event()

    # ------------------------------------------------------------------ #
    #  驱动元信息
    # ------------------------------------------------------------------ #
    @classmethod
    def driver_type(cls) -> str:
        return 'wearable_eeg'

    @classmethod
    def driver_name(cls) -> str:
        return 'CH340 EEG 串口设备'

    # ------------------------------------------------------------------ #
    #  设备发现
    # ------------------------------------------------------------------ #
    def discover(self) -> List[DeviceMeta]:
        if not SERIAL_AVAILABLE:
            logger.debug('[Ch340] pyserial not available, returning empty list')
            return []

        result: List[DeviceMeta] = []
        try:
            for port_info in serial.tools.list_ports.comports():
                if not self._is_usb_serial_port(port_info):
                    continue
                is_ch340 = self._is_ch340_port(port_info)
                port_name = port_info.device
                vid = getattr(port_info, 'vid', None)
                pid = getattr(port_info, 'pid', None)
                result.append(DeviceMeta(
                    driver_type=self.driver_type(),
                    device_id=port_name,
                    name=f'{port_info.description or "USB 串口"} ({port_name})',
                    address=port_name,
                    channel_count=CHANNEL_COUNT,
                    sample_rate=DEFAULT_SAMPLE_RATE,
                    is_available=True,
                    extra={
                        'baudrate': DEFAULT_BAUDRATE,
                        'is_ch340': is_ch340,
                        'description': port_info.description or '',
                        'manufacturer': port_info.manufacturer or '',
                        'product': port_info.product or '',
                        'hwid': port_info.hwid or '',
                        'vid': vid,
                        'pid': pid,
                    },
                ))
        except Exception as exc:
            logger.warning('[Ch340] discover error: %s', exc)

        logger.debug('[Ch340] Discovered %d port(s)', len(result))
        return result

    def get_device_meta(self, device_id: str) -> Optional[DeviceMeta]:
        for meta in self.discover():
            if meta.device_id == device_id:
                return meta
        return None

    # ------------------------------------------------------------------ #
    #  连接管理
    # ------------------------------------------------------------------ #
    def connect(self, device_id: str, config: Optional[Dict[str, Any]] = None) -> bool:
        if not SERIAL_AVAILABLE:
            return False
        config = config or {}
        baudrate = int(config.get('baudrate', DEFAULT_BAUDRATE))
        port = device_id

        with self._lock:
            conn = self._connections.get(port)
            if conn and conn.status in (DeviceStatus.CONNECTED, DeviceStatus.ACQUIRING):
                return True
            if conn and conn.status == DeviceStatus.CONNECTING:
                return False

            conn = _Connection(port=port, baudrate=baudrate, status=DeviceStatus.CONNECTING)
            self._connections[port] = conn

        try:
            return bool(self._run_coro_on_async_loop(self._connect_async(conn)))
        except Exception as exc:
            conn.status = DeviceStatus.ERROR
            conn.last_error = str(exc)
            logger.debug('[Ch340] Connect failed %s: %s', port, exc)
            return False

    def disconnect(self, device_id: str) -> bool:
        port = device_id
        with self._lock:
            conn = self._connections.get(port)
            if not conn:
                return False
            if conn.status == DeviceStatus.ACQUIRING:
                self._stop_streaming_impl(conn)
            logger.debug('[Ch340] Disconnecting %s', port)
            if conn.serial_conn and conn.serial_conn.is_open:
                try:
                    conn.serial_conn.close()
                except Exception:
                    pass
            if conn.async_transport:
                try:
                    loop = self._async_loop
                    if loop and loop.is_running():
                        loop.call_soon_threadsafe(conn.async_transport.close)
                    else:
                        conn.async_transport.close()
                except Exception:
                    pass
            del self._connections[port]
            return True

    def get_status(self, device_id: str) -> DeviceStatus:
        with self._lock:
            conn = self._connections.get(device_id)
            return conn.status if conn else DeviceStatus.DISCONNECTED

    # ------------------------------------------------------------------ #
    #  数据传输
    # ------------------------------------------------------------------ #
    def start_streaming(self, device_id: str) -> bool:
        with self._lock:
            conn = self._connections.get(device_id)
            if not conn:
                return False
            if conn.status not in (DeviceStatus.CONNECTED, DeviceStatus.ACQUIRING):
                return False
            if conn.async_transport:
                # 异步路径：协议自动解析，仅需切换状态
                conn.status = DeviceStatus.ACQUIRING
                return True
            # 同步路径：启动采集线程
            conn.stop_event.clear()
            conn.thread = threading.Thread(
                target=self._acq_thread, args=(conn,),
                name=f'ch340-acq-{device_id}', daemon=True,
            )
            conn.thread.start()
            conn.status = DeviceStatus.ACQUIRING
            return True

    def stop_streaming(self, device_id: str) -> bool:
        with self._lock:
            conn = self._connections.get(device_id)
            if not conn:
                return False
            return self._stop_streaming_impl(conn)

    def _stop_streaming_impl(self, conn: _Connection) -> bool:
        if conn.status != DeviceStatus.ACQUIRING:
            return True
        conn.stop_event.set()
        if conn.thread and conn.thread.is_alive():
            conn.thread.join(timeout=2.0)
        conn.status = DeviceStatus.CONNECTED
        return True

    def read_data(self, device_id: str, count: int = 1) -> List[DeviceFrame]:
        with self._lock:
            conn = self._connections.get(device_id)
            if not conn or not conn.data_queue:
                return []
            out: List[DeviceFrame] = []
            max_count = max(1, int(count))
            for _ in range(max_count):
                if not conn.data_queue:
                    break
                raw = conn.data_queue.popleft()
                out.append(DeviceFrame(
                    seq=int(raw.get('seq', 0)),
                    timestamp=float(raw.get('timestamp', time.time())),
                    channels=[float(ch) for ch in raw.get('channels', [])],
                    device_id=device_id,
                    extra={'port': device_id, 'raw_hex': raw.get('raw_hex', '')},
                ))
            return out

    def pending_count(self, device_id: str) -> int:
        with self._lock:
            conn = self._connections.get(device_id)
            return len(conn.data_queue) if conn else 0

    # ------------------------------------------------------------------ #
    #  异常处理
    # ------------------------------------------------------------------ #
    def handle_error(self, device_id: str, error: Exception) -> None:
        logger.error('[Ch340] %s error: %s', device_id, error)
        with self._lock:
            conn = self._connections.get(device_id)
            if conn:
                conn.last_error = str(error)

    # ================================================================== #
    #  内部实现
    # ================================================================== #

    @staticmethod
    def _is_usb_serial_port(port_info) -> bool:
        device = (getattr(port_info, 'device', '') or '').lower()
        description = (getattr(port_info, 'description', '') or '').upper()
        hwid = (getattr(port_info, 'hwid', '') or '').upper()
        vid = getattr(port_info, 'vid', None)
        pid = getattr(port_info, 'pid', None)

        if vid is not None and pid is not None:
            return True
        usb_device_prefixes = ('/dev/ttyusb', '/dev/ttyacm', '/dev/cu.usbserial', '/dev/cu.usbmodem')
        if device.startswith(usb_device_prefixes):
            return True
        if vid == 0x1A86:
            return True
        if 'CH340' in description or 'CH341' in description:
            return True
        if '1A86' in hwid:
            return True
        text_blob = f'{description} {(getattr(port_info, "manufacturer", "") or "").upper()} {(getattr(port_info, "product", "") or "").upper()} {hwid}'
        return 'USB' in text_blob

    @staticmethod
    def _is_ch340_port(port_info) -> bool:
        vid = getattr(port_info, 'vid', None)
        if vid == 0x1A86:
            return True
        description = (getattr(port_info, 'description', '') or '').upper()
        hwid = (getattr(port_info, 'hwid', '') or '').upper()
        for kw in ('CH340', 'CH341', '1A86'):
            if kw in description or kw in hwid:
                return True
        return False

    @staticmethod
    def _try_fix_linux_serial_permission(port: str) -> Tuple[bool, str]:
        askpass = os.environ.get('SUDO_ASKPASS') or os.environ.get('SSH_ASKPASS')
        if not askpass:
            return False, 'SUDO_ASKPASS/SSH_ASKPASS 未配置'
        try:
            result = subprocess.run(
                ['sudo', '-A', 'chmod', 'a+rw', port],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                return True, ''
            return False, (result.stderr or result.stdout or '').strip() or f'sudo rc={result.returncode}'
        except Exception as exc:
            return False, str(exc)

    # --- async loop management --- #

    def _ensure_async_loop(self) -> asyncio.AbstractEventLoop:
        with self._lock:
            if (self._async_loop and self._async_loop.is_running()
                    and self._async_thread and self._async_thread.is_alive()):
                return self._async_loop
            self._async_loop_ready.clear()

            def _runner():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                self._async_loop = loop
                self._async_loop_ready.set()
                loop.run_forever()

            self._async_thread = threading.Thread(target=_runner, name='ch340-async-loop', daemon=True)
            self._async_thread.start()

        self._async_loop_ready.wait(timeout=3.0)
        if not self._async_loop or not self._async_loop.is_running():
            raise RuntimeError('Failed to start background async loop for Ch340 driver')
        return self._async_loop

    def _run_coro_on_async_loop(self, coro):
        loop = self._ensure_async_loop()
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result(timeout=15.0)

    # --- async connect --- #

    async def _connect_async(self, conn: _Connection) -> bool:
        try:
            loop = asyncio.get_running_loop()
            transport, protocol = await serial_asyncio.create_serial_connection(
                loop, lambda: _BCIAsyncProtocol(conn), conn.port, baudrate=conn.baudrate,
            )
            conn.async_transport = transport
            conn.async_protocol = protocol
            conn.status = DeviceStatus.CONNECTED
            conn.connected_at = time.time()
            conn.last_error = None

            # 发送初始化命令
            for i in range(3):
                transport.write(b'C005\r\n')
                await asyncio.sleep(0.05)
            for i in range(2):
                transport.write(b'C002\r\n')
                await asyncio.sleep(0.01)

            # 等待设备响应（最多 3s）
            for check in range(30):
                await asyncio.sleep(0.1)
                if protocol.valid_frame_count > 0:
                    break

            logger.debug('[Ch340] Connected %s  valid_frames=%d', conn.port, protocol.valid_frame_count)
            return True

        except Exception as exc:
            error_msg = str(exc)
            is_perm_error = 'Permission denied' in error_msg or 'Access is denied' in error_msg

            if is_perm_error and platform.system() == 'Linux':
                fixed, reason = self._try_fix_linux_serial_permission(conn.port)
                if fixed:
                    try:
                        loop = asyncio.get_running_loop()
                        transport, protocol = await serial_asyncio.create_serial_connection(
                            loop, lambda: _BCIAsyncProtocol(conn), conn.port, baudrate=conn.baudrate,
                        )
                        conn.async_transport = transport
                        conn.async_protocol = protocol
                        conn.status = DeviceStatus.CONNECTED
                        conn.connected_at = time.time()
                        conn.last_error = None
                        for _ in range(3):
                            transport.write(b'C005\r\n')
                            await asyncio.sleep(0.05)
                        for _ in range(2):
                            transport.write(b'C002\r\n')
                            await asyncio.sleep(0.01)
                        logger.debug('[Ch340] Connected %s after permission fix', conn.port)
                        return True
                    except Exception as retry_exc:
                        error_msg = f'{error_msg}; retry failed: {retry_exc}'
                else:
                    error_msg = (f'{error_msg}; 权限修复失败: {reason}. '
                                 '请配置 SUDO_ASKPASS 后重试，或将当前用户加入 dialout/uucp 组。')
            elif is_perm_error and platform.system() == 'Windows':
                error_msg = f'{error_msg}; 请以管理员身份运行后端服务或终端后重试。'

            conn.status = DeviceStatus.ERROR
            conn.last_error = error_msg
            logger.debug('[Ch340] Connect error %s: %s', conn.port, error_msg)
            return False

    # --- sync acquisition thread (fallback path) --- #

    def _acq_thread(self, conn: _Connection):
        logger.debug('[Ch340] Acq thread started %s', conn.port)
        try:
            while not conn.stop_event.is_set() and conn.serial_conn and conn.serial_conn.is_open:
                try:
                    if conn.serial_conn.in_waiting > 0:
                        data = conn.serial_conn.read(conn.serial_conn.in_waiting)
                        if data:
                            conn.raw_input_queue.append({
                                'timestamp': time.time(),
                                'raw_hex': data.hex(),
                                'raw_text': data.decode('latin-1', errors='replace'),
                            })
                        conn.data_buffer += data
                        while FRAME_TAIL in conn.data_buffer:
                            line, conn.data_buffer = conn.data_buffer.split(FRAME_TAIL, 1)
                            if line.startswith(FRAME_HEADER) and len(line) == FRAME_TOTAL_LEN - len(FRAME_TAIL):
                                payload = line[len(FRAME_HEADER):]
                                if len(payload) == FRAME_PAYLOAD_LEN:
                                    try:
                                        channels = list(struct.unpack(FRAME_PAYLOAD_FMT, payload))
                                        conn.data_count += 1
                                        conn.frame_seq += 1
                                        conn.data_queue.append({
                                            'seq': conn.frame_seq,
                                            'timestamp': time.time(),
                                            'channels': channels,
                                            'port': conn.port,
                                            'raw_hex': line.hex(),
                                        })
                                    except struct.error:
                                        pass
                except Exception as exc:
                    logger.debug('[Ch340] Acq error %s: %s', conn.port, exc)
                    conn.last_error = str(exc)
                    conn.status = DeviceStatus.ERROR
                    break
                time.sleep(0.001)
        except Exception as exc:
            conn.status = DeviceStatus.ERROR
            conn.last_error = str(exc)
