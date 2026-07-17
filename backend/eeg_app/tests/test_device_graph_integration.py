"""虚拟设备 → 计算图引擎 → WebSocket 全链路集成测试。

注意：
  GraphWorker 内部硬编码使用全局单例 get_device_manager()，
  因此无法使用测试专用的 Manager 实例 — 这些测试本质上是
  对 GraphExecutionManager API 的契约验证。

测试覆盖：
  1. 设备 → Manager 集成（虚拟设备发现/连接/采集/停止）
  2. GraphStore 运行时状态管理（run/stop/freeze 和校验）
  3. GraphEngine 数据流模拟（无设备时 SyntheticSourceProvider 降级）
  4. 事件队列数据格式验证
"""

import json
import threading
import time
from http.server import HTTPServer
from socketserver import ThreadingMixIn
from typing import Generator, Dict, Any, Set

import pytest

from eeg_app.virtual_device_server import VirtualDeviceHandler, _DEVICES
from eeg_app.drivers.manager import DeviceDriverManager
from eeg_app.drivers.simulator_eeg import SimulatorDriver
from eeg_app.drivers.base import DeviceStatus
from eeg_app.graph_store import set_graph, run_graph, stop_graph, get_graph, get_runtime_state, set_frozen
from eeg_app.graph_engine import GraphExecutionManager

TEST_PORT = 37777
TEST_BASE = f'http://127.0.0.1:{TEST_PORT}'


class _ThreadedTestServer(ThreadingMixIn, HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


@pytest.fixture(scope='module')
def vdev_server() -> Generator[None, None, None]:
    for d in _DEVICES.values():
        d.disconnect()
    server = _ThreadedTestServer(('127.0.0.1', TEST_PORT), VirtualDeviceHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.2)
    yield
    server.shutdown()


@pytest.fixture
def manager(vdev_server) -> Generator[DeviceDriverManager, None, None]:
    mgr = DeviceDriverManager()
    drv = SimulatorDriver(server_url=TEST_BASE)
    mgr.register_driver(drv)
    for dev in drv.discover():
        drv.disconnect(dev.device_id)
    yield mgr


# ═══════════════════════════════════════════════════════════════ #
#  设备 → Manager 集成
# ═══════════════════════════════════════════════════════════════ #

class TestDeviceManagerIntegration:
    def test_manager_discovers_virtual_devices(self, manager):
        devices = manager.discover_all()
        assert len(devices) == 5
        ids = [d.device_id for d in devices]
        assert 'sim_alpha' in ids and 'sim_multi' in ids

    def test_manager_connect_device(self, manager):
        assert manager.connect('sim_alpha') is True
        assert manager.get_status('sim_alpha') == DeviceStatus.CONNECTED

    def test_manager_start_and_read(self, manager):
        assert manager.start_streaming('sim_alpha') is True
        time.sleep(0.3)
        assert manager.is_streaming('sim_alpha') is True
        frames = manager.read_data('sim_alpha', count=10)
        assert len(frames) > 0
        assert len(frames[0].channels) == 8
        assert frames[0].device_id == 'sim_alpha'

    def test_manager_stop_streaming(self, manager):
        manager.start_streaming('sim_alpha')
        time.sleep(0.1)
        assert manager.stop_streaming('sim_alpha') is True
        assert manager.is_streaming('sim_alpha') is False

    def test_manager_multiple_devices(self, manager):
        assert manager.start_streaming('sim_alpha') is True
        assert manager.start_streaming('sim_beta') is True
        time.sleep(0.3)
        assert manager.is_streaming('sim_alpha') is True
        assert manager.is_streaming('sim_beta') is True
        alpha_frames = manager.read_data('sim_alpha', count=5)
        beta_frames = manager.read_data('sim_beta', count=5)
        assert len(alpha_frames) > 0 and len(beta_frames) > 0


# ═══════════════════════════════════════════════════════════════ #
#  GraphStore 运行时状态（不依赖虚拟设备服务器）
# ═══════════════════════════════════════════════════════════════ #

@pytest.fixture(autouse=True)
def reset_global_state():
    """每个测试前重置 graph_store 全局状态"""
    from eeg_app.graph_store import _RUNTIME_STATE
    _RUNTIME_STATE['running'] = False
    set_frozen(False)
    set_graph({'nodes': [], 'edges': [], 'frozen': False})
    yield


class TestRuntimeIntegration:
    """测试 graph_store 运行时状态管理（不依赖设备服务器）。"""

    def test_run_graph_makes_state_running(self):
        set_graph({'nodes': [], 'edges': [], 'frozen': True})
        set_frozen(True)
        result = run_graph('live')
        state = get_runtime_state()
        assert state['running'] is True
        assert state['mode'] == 'live'

    def test_stop_graph(self):
        set_graph({'nodes': [], 'edges': [], 'frozen': True})
        set_frozen(True)
        run_graph('live')
        result = stop_graph()
        assert result['status'] == 'stopped'

    def test_cannot_modify_graph_while_running(self):
        set_graph({'nodes': [], 'edges': [], 'frozen': True})
        set_frozen(True)
        run_graph('live')
        with pytest.raises(RuntimeError, match='Cannot modify graph'):
            set_graph({'nodes': [], 'edges': [], 'frozen': False})
        stop_graph()

    def test_cannot_freeze_while_running(self):
        set_graph({'nodes': [], 'edges': [], 'frozen': True})
        set_frozen(True)
        run_graph('live')
        with pytest.raises(RuntimeError, match='Cannot freeze'):
            set_frozen(False)
        stop_graph()

    def test_offline_mode_rejects_live_sources(self):
        set_graph({
            'nodes': [{'id': 'src-1', 'type': 'SOURCE', 'name': 'S', 'x': 0, 'y': 0, 'params': {}, 'deviceId': 'sim_alpha'}],
            'edges': [],
            'frozen': True,
        })
        result = run_graph('offline')
        assert result.get('status') == 'error'
        assert 'offline' in result.get('error', '').lower()


# ═══════════════════════════════════════════════════════════════ #
#  GraphEngine 数据流（SyntheticSourceProvider 降级）
# ═══════════════════════════════════════════════════════════════ #

class TestGraphEngineSyntheticFlow:
    """测试 GraphEngine 在无设备时的 SyntheticSourceProvider 降级路径。"""

    def test_synthetic_source_produces_events(self):
        engine = GraphExecutionManager()
        graph = {
            'nodes': [
                {'id': 'src-1', 'type': 'SOURCE', 'name': '合成源', 'x': 0, 'y': 0, 'params': {}, 'deviceId': None},
                {'id': 'out-1', 'type': 'OUTPUT', 'name': '输出', 'x': 200, 'y': 0, 'params': {}},
            ],
            'edges': [{'id': 'e1', 'source': 'src-1', 'target': 'out-1', 'sourcePort': 'out', 'targetPort': 'in'}],
            'frozen': True,
        }
        engine.update(graph, {'out-1'}, set())
        time.sleep(0.5)
        events = engine.poll_events(max_items_per_worker=100)
        engine.stop_all()
        assert len(events) > 0, 'Synthetic source should produce events'
        event = events[0]
        assert event['nodeId'] == 'out-1'
        assert event['nodeType'] == 'OUTPUT'
        assert 'channels' in event
        assert len(event['channels']) == 8

    def test_event_queue_fields(self):
        """验证事件队列中的字段与 graph_consumer_v2.py 期望一致"""
        engine = GraphExecutionManager()
        graph = {
            'nodes': [
                {'id': 'src-1', 'type': 'SOURCE', 'name': '合成源', 'x': 0, 'y': 0, 'params': {}, 'deviceId': None},
                {'id': 'out-1', 'type': 'OUTPUT', 'name': '输出', 'x': 200, 'y': 0, 'params': {}},
            ],
            'edges': [{'id': 'e1', 'source': 'src-1', 'target': 'out-1', 'sourcePort': 'out', 'targetPort': 'in'}],
            'frozen': True,
        }
        engine.update(graph, {'out-1'}, set())
        time.sleep(0.5)
        events = engine.poll_events(max_items_per_worker=50)
        engine.stop_all()
        assert len(events) > 0
        event = events[0]
        required_fields = {'nodeId', 'nodeType', 'channels', 'channelNames', 'sampleRate', 'utcFirstFrameMs'}
        missing = required_fields - set(event.keys())
        assert not missing, f'Missing required fields: {missing}'
        assert event['sampleRate'] > 0
        assert event['utcFirstFrameMs'] > 0
