"""SimulatorDriver — 模拟设备驱动集成测试。

测试 SimulatorDriver 通过 HTTP 与虚拟设备服务器 (7777端口) 通信的正确性。
使用一个隔离的测试服务器实例。

运行：
    pytest backend/eeg_app/tests/test_simulator_driver.py -v
"""

import json
import threading
import time
from http.server import HTTPServer
from socketserver import ThreadingMixIn
from typing import Generator, Dict, Any, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError

import pytest

from eeg_app.drivers.simulator_eeg import SimulatorDriver, _STATUS_MAP
from eeg_app.drivers.base import DeviceStatus, DeviceFrame
from eeg_app.virtual_device_server import VirtualDeviceHandler, _DEVICES, _DEVICES_SPEC

TEST_PORT = 27777
TEST_BASE = f'http://127.0.0.1:{TEST_PORT}'


class _ThreadedTestServer(ThreadingMixIn, HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def _http(method: str, path: str, body: Any = None) -> Dict[str, Any]:
    url = f'{TEST_BASE}/{path.lstrip("/")}'
    data = json.dumps(body).encode('utf-8') if body else None
    req = Request(url, data=data, method=method)
    if data:
        req.add_header('Content-Type', 'application/json')
    try:
        with urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except URLError as e:
        if hasattr(e, 'read'):
            return json.loads(e.read().decode('utf-8'))
        raise


@pytest.fixture(scope='module')
def vdev_test_server() -> Generator[_ThreadedTestServer, None, None]:
    """启动测试用虚拟设备服务器。"""
    for d in _DEVICES.values():
        d.disconnect()
    server = _ThreadedTestServer(('127.0.0.1', TEST_PORT), VirtualDeviceHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.2)
    yield server
    server.shutdown()


@pytest.fixture
def driver(vdev_test_server) -> Generator[SimulatorDriver, None, None]:
    """创建指向测试服务器的 SimulatorDriver 实例。"""
    drv = SimulatorDriver(server_url=TEST_BASE)
    # 确保设备都断开
    for dev_id in ['sim_alpha', 'sim_beta', 'sim_theta', 'sim_gamma', 'sim_multi']:
        try:
            _http('POST', f'/devices/{dev_id}/disconnect')
        except Exception:
            pass
    yield drv


# ------------------------------------------------------------------ #
#  驱动元信息测试
# ------------------------------------------------------------------ #

class TestDriverMetadata:
    def test_driver_type(self):
        assert SimulatorDriver.driver_type() == 'simulated'

    def test_driver_name(self):
        assert SimulatorDriver.driver_name() == '虚拟设备驱动'

    def test_driver_description(self):
        desc = SimulatorDriver.driver_description()
        assert '7777' in desc
        assert 'EEG' in desc or '虚拟' in desc


# ------------------------------------------------------------------ #
#  设备发现测试
# ------------------------------------------------------------------ #

class TestDiscovery:
    def test_discover_returns_5_devices(self, driver):
        devices = driver.discover()
        assert len(devices) == 5
        ids = [d.device_id for d in devices]
        assert 'sim_alpha' in ids
        assert 'sim_multi' in ids

    def test_discover_meta_structure(self, driver):
        devices = driver.discover()
        for meta in devices:
            assert meta.driver_type == 'simulated'
            assert meta.device_id
            assert meta.name
            assert meta.channel_count > 0
            assert meta.sample_rate > 0
            assert meta.is_available is True

    def test_get_device_meta_alpha(self, driver):
        meta = driver.get_device_meta('sim_alpha')
        assert meta is not None
        assert meta.device_id == 'sim_alpha'
        assert meta.channel_count == 8
        assert meta.sample_rate == 250

    def test_get_device_meta_theta_4ch(self, driver):
        meta = driver.get_device_meta('sim_theta')
        assert meta is not None
        assert meta.channel_count == 4
        assert meta.sample_rate == 200

    def test_get_device_meta_nonexistent(self, driver):
        meta = driver.get_device_meta('nonexistent')
        assert meta is None


# ------------------------------------------------------------------ #
#  连接管理测试
# ------------------------------------------------------------------ #

class TestConnectionManagement:
    def test_connect(self, driver):
        assert driver.connect('sim_alpha') is True
        assert driver.get_status('sim_alpha') == DeviceStatus.CONNECTED

    def test_connect_idempotent(self, driver):
        assert driver.connect('sim_alpha') is True
        assert driver.connect('sim_alpha') is True
        assert driver.get_status('sim_alpha') == DeviceStatus.CONNECTED

    def test_disconnect(self, driver):
        driver.connect('sim_alpha')
        assert driver.disconnect('sim_alpha') is True
        assert driver.get_status('sim_alpha') == DeviceStatus.DISCONNECTED

    def test_disconnect_without_connect(self, driver):
        """未连接的设备断开也应正确响应"""
        assert driver.disconnect('sim_beta') is True
        assert driver.get_status('sim_beta') == DeviceStatus.DISCONNECTED

    def test_get_status_disconnected(self, driver):
        assert driver.get_status('sim_alpha') == DeviceStatus.DISCONNECTED

    def test_connect_nonexistent_device(self, driver):
        assert driver.connect('nonexistent') is False


# ------------------------------------------------------------------ #
#  数据采集测试
# ------------------------------------------------------------------ #

class TestDataAcquisition:
    def test_start_streaming(self, driver):
        driver.connect('sim_alpha')
        assert driver.start_streaming('sim_alpha') is True
        assert driver.get_status('sim_alpha') == DeviceStatus.ACQUIRING

    def test_start_without_connect(self, driver):
        """start_streaming 应自动完成连接"""
        assert driver.start_streaming('sim_alpha') is True
        assert driver.get_status('sim_alpha') == DeviceStatus.ACQUIRING

    def test_stop_streaming(self, driver):
        driver.start_streaming('sim_alpha')
        time.sleep(0.1)
        assert driver.stop_streaming('sim_alpha') is True
        assert driver.get_status('sim_alpha') == DeviceStatus.CONNECTED

    def test_read_data_after_start(self, driver):
        driver.start_streaming('sim_alpha')
        time.sleep(0.3)
        frames = driver.read_data('sim_alpha', count=10)
        assert len(frames) >= 1
        frame = frames[0]
        assert isinstance(frame, DeviceFrame)
        assert frame.device_id == 'sim_alpha'
        assert len(frame.channels) == 8
        assert frame.seq > 0
        assert frame.timestamp > 0

    def test_read_data_returns_requested_count(self, driver):
        driver.start_streaming('sim_multi')
        time.sleep(0.5)
        frames = driver.read_data('sim_multi', count=20)
        assert len(frames) <= 20  # 可能少于20，但不能多于20

    def test_read_data_no_stream(self, driver):
        """未开始采集时读取数据应返回空列表"""
        # 确保已停止采集
        driver.stop_streaming('sim_alpha')
        driver.disconnect('sim_alpha')
        # 使用一个未被其他测试启动的设备
        frames = driver.read_data('sim_gamma', count=10)
        assert frames == []

    def test_pending_count(self, driver):
        driver.start_streaming('sim_alpha')
        time.sleep(0.3)
        count = driver.pending_count('sim_alpha')
        assert count > 0


# ------------------------------------------------------------------ #
#  全设备测试
# ------------------------------------------------------------------ #

class TestAllDevices:
    def test_all_devices_discoverable(self, driver):
        devices = driver.discover()
        assert len(devices) == 5

    def test_all_devices_connectable(self, driver):
        for meta in driver.discover():
            assert driver.connect(meta.device_id) is True

    def test_all_devices_can_stream(self, driver):
        for meta in driver.discover():
            assert driver.start_streaming(meta.device_id) is True

        time.sleep(0.3)

        for meta in driver.discover():
            status = driver.get_status(meta.device_id)
            assert status == DeviceStatus.ACQUIRING, f'{meta.device_id} not acquiring'
            frames = driver.read_data(meta.device_id, count=5)
            assert len(frames) > 0, f'{meta.device_id} has no data'
            frame = frames[0]
            assert len(frame.channels) == meta.channel_count, \
                f'{meta.device_id}: expected {meta.channel_count} ch, got {len(frame.channels)}'
            # 每个帧的 channel 数量应设备特有
            assert frame.device_id == meta.device_id

    def test_all_devices_can_stop(self, driver):
        for meta in driver.discover():
            driver.start_streaming(meta.device_id)
        time.sleep(0.2)
        for meta in driver.discover():
            assert driver.stop_streaming(meta.device_id) is True
            assert driver.get_status(meta.device_id) == DeviceStatus.CONNECTED

    def test_all_devices_can_disconnect(self, driver):
        for meta in driver.discover():
            driver.connect(meta.device_id)
            assert driver.disconnect(meta.device_id) is True
            assert driver.get_status(meta.device_id) == DeviceStatus.DISCONNECTED


# ------------------------------------------------------------------ #
#  错误处理测试
# ------------------------------------------------------------------ #

class TestErrorHandling:
    def test_server_unavailable_discover(self):
        """服务器不可用时 discover 应返回空列表"""
        drv = SimulatorDriver(server_url='http://127.0.0.1:19999')
        devices = drv.discover()
        assert devices == []

    def test_server_unavailable_connect(self):
        drv = SimulatorDriver(server_url='http://127.0.0.1:19999')
        assert drv.connect('sim_alpha') is False

    def test_server_unavailable_read_data(self):
        drv = SimulatorDriver(server_url='http://127.0.0.1:19999')
        frames = drv.read_data('sim_alpha', count=10)
        assert frames == []

    def test_server_unavailable_get_status(self):
        drv = SimulatorDriver(server_url='http://127.0.0.1:19999')
        assert drv.get_status('sim_alpha') == DeviceStatus.DISCONNECTED

    def test_server_unavailable_pending_count(self):
        drv = SimulatorDriver(server_url='http://127.0.0.1:19999')
        assert drv.pending_count('sim_alpha') == 0
