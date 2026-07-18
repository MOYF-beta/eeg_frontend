"""虚拟设备服务器 (7777端口) 端到端测试。

测试策略：
1. 启动一个隔离的虚拟设备服务器实例（测试端口）
2. 直接向其 HTTP API 发送请求验证每个端点
3. 验证波形数据生成的质量

使用方法：
    pytest backend/eeg_app/tests/test_virtual_device_server.py -v
"""

import json
import threading
import time
from http.server import HTTPServer
from socketserver import ThreadingMixIn
from typing import Generator, Any, Dict
from urllib.request import Request, urlopen
from urllib.error import URLError

import pytest

# 导入被测模块
from eeg_app.virtual_device_server import (
    VirtualDeviceHandler,
    DeviceState,
    _DEVICES,
    _DEVICES_SPEC,
)

# ------------------------------------------------------------------ #
#  测试用 HTTP 客户端
# ------------------------------------------------------------------ #

TEST_PORT = 17777
TEST_BASE = f'http://127.0.0.1:{TEST_PORT}'


def _http(method: str, path: str, body: Any = None) -> Dict[str, Any]:
    """发送 HTTP 请求到测试服务器。"""
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


# ------------------------------------------------------------------ #
#  Fixture: 启动隔离的测试服务器
# ------------------------------------------------------------------ #

class _ThreadedTestServer(ThreadingMixIn, HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


@pytest.fixture(scope='module')
def vdev_server() -> Generator[None, None, None]:
    """启动虚拟设备测试服务器，测试完成后关闭。"""
    # 重置设备状态
    from eeg_app.virtual_device_server import _DEVICES as devs
    for d in devs.values():
        d.disconnect()

    server = _ThreadedTestServer(('127.0.0.1', TEST_PORT), VirtualDeviceHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.2)  # 等待服务器启动

    yield

    server.shutdown()


# ------------------------------------------------------------------ #
#  测试用例
# ------------------------------------------------------------------ #

class TestVirtualDeviceHealthAPI:
    """测试健康检查端点。"""

    def test_health_returns_running(self, vdev_server):
        resp = _http('GET', '/health')
        assert resp['ok'] is True
        assert resp['data']['status'] == 'running'
        assert resp['data']['device_count'] == 5
        assert 'sim_alpha' in resp['data']['devices']
        assert 'sim_multi' in resp['data']['devices']


class TestVirtualDeviceDiscoveryAPI:
    """测试设备发现端点。"""

    def test_list_devices(self, vdev_server):
        resp = _http('GET', '/devices')
        assert resp['ok'] is True
        assert resp['data']['count'] == 5
        device_ids = [d['device_id'] for d in resp['data']['devices']]
        assert 'sim_alpha' in device_ids
        assert 'sim_beta' in device_ids
        assert 'sim_theta' in device_ids
        assert 'sim_gamma' in device_ids
        assert 'sim_multi' in device_ids

    def test_device_meta_structure(self, vdev_server):
        resp = _http('GET', '/devices/sim_alpha')
        assert resp['ok'] is True
        data = resp['data']
        assert data['device_id'] == 'sim_alpha'
        assert data['driver_type'] == 'simulated'
        assert data['channel_count'] == 8
        assert data['sample_rate'] == 250
        assert data['is_available'] is True
        assert 'Alpha' in data['name']

    def test_device_meta_sim_multi(self, vdev_server):
        """sim_multi: 多频混合的特殊配置"""
        resp = _http('GET', '/devices/sim_multi')
        assert resp['ok'] is True
        data = resp['data']
        assert data['device_id'] == 'sim_multi'
        assert data['channel_count'] == 8
        assert data['sample_rate'] == 250
        # sim_multi 的 freqs 为 None，每通道频率不同
        assert data['extra']['freqs'] is None

    def test_device_meta_sim_theta_4ch(self, vdev_server):
        """sim_theta 只有4通道"""
        resp = _http('GET', '/devices/sim_theta')
        assert resp['ok'] is True
        assert resp['data']['channel_count'] == 4
        assert resp['data']['sample_rate'] == 200

    def test_device_not_found(self, vdev_server):
        resp = _http('GET', '/devices/nonexistent')
        assert resp['ok'] is False


class TestVirtualDeviceConnectionLifecycle:
    """测试设备连接生命周期：connect → start → stop → disconnect。"""

    def test_connect_device(self, vdev_server):
        """连接设备：CONNECTED 状态"""
        resp = _http('POST', '/devices/sim_alpha/connect')
        assert resp['ok'] is True
        assert resp['data']['device_id'] == 'sim_alpha'
        assert resp['data']['status'] == 'connected'

    def test_connect_idempotent(self, vdev_server):
        """重复连接应幂等"""
        _http('POST', '/devices/sim_beta/connect')
        resp = _http('POST', '/devices/sim_beta/connect')
        assert resp['ok'] is True
        assert resp['data']['status'] == 'connected'

    def test_status_after_connect(self, vdev_server):
        """连接后状态应为 connected"""
        _http('POST', '/devices/sim_gamma/connect')
        resp = _http('GET', '/devices/sim_gamma/status')
        assert resp['ok'] is True
        assert resp['data']['status'] == 'connected'

    def test_start_streaming(self, vdev_server):
        """开始采集后状态应为 acquiring"""
        _http('POST', '/devices/sim_alpha/connect')
        resp = _http('POST', '/devices/sim_alpha/start')
        assert resp['ok'] is True
        assert resp['data']['status'] == 'acquiring'

    def test_streaming_generates_data(self, vdev_server):
        """采集后应有数据生成"""
        _http('POST', '/devices/sim_alpha/connect')
        _http('POST', '/devices/sim_alpha/start')
        time.sleep(0.3)  # 等待数据积累
        resp = _http('GET', '/devices/sim_alpha/status')
        assert resp['data']['pending_count'] > 0

    def test_read_data_returns_frames(self, vdev_server):
        """读取数据应返回帧"""
        _http('POST', '/devices/sim_alpha/connect')
        _http('POST', '/devices/sim_alpha/start')
        time.sleep(0.5)
        resp = _http('GET', '/devices/sim_alpha/data?count=10')
        assert resp['ok'] is True
        frames = resp['data']['frames']
        assert len(frames) >= 1
        frame = frames[0]
        # 验证帧结构
        assert 'seq' in frame
        assert 'timestamp' in frame
        assert 'channels' in frame
        assert 'device_id' in frame
        assert frame['device_id'] == 'sim_alpha'
        assert len(frame['channels']) == 8  # sim_alpha 是 8 通道

    def test_stop_streaming(self, vdev_server):
        """停止采集后状态应为 connected"""
        _http('POST', '/devices/sim_alpha/connect')
        _http('POST', '/devices/sim_alpha/start')
        time.sleep(0.1)
        resp = _http('POST', '/devices/sim_alpha/stop')
        assert resp['ok'] is True
        assert resp['data']['status'] == 'connected'
        # pending_count 应重置或正在消耗
        status = _http('GET', '/devices/sim_alpha/status')
        assert status['data']['status'] == 'connected'

    def test_disconnect_device(self, vdev_server):
        """断开后状态应为 disconnected"""
        _http('POST', '/devices/sim_alpha/connect')
        resp = _http('POST', '/devices/sim_alpha/disconnect')
        assert resp['ok'] is True
        assert resp['data']['status'] == 'disconnected'
        status = _http('GET', '/devices/sim_alpha/status')
        assert status['data']['status'] == 'disconnected'

    def test_full_lifecycle(self, vdev_server):
        """全生命周期：disconnected → connected → acquiring → connected → disconnected"""
        # 先断开确保初始状态为 disconnected
        _http('POST', '/devices/sim_beta/disconnect')
        time.sleep(0.05)

        # 初始状态
        status = _http('GET', '/devices/sim_beta/status')
        assert status['data']['status'] == 'disconnected', f'Expected disconnected, got {status["data"]["status"]}'

        # connect
        _http('POST', '/devices/sim_beta/connect')
        status = _http('GET', '/devices/sim_beta/status')
        assert status['data']['status'] == 'connected'

        # start
        _http('POST', '/devices/sim_beta/start')
        status = _http('GET', '/devices/sim_beta/status')
        assert status['data']['status'] == 'acquiring'

        # stop
        _http('POST', '/devices/sim_beta/stop')
        status = _http('GET', '/devices/sim_beta/status')
        assert status['data']['status'] == 'connected'

        # disconnect
        _http('POST', '/devices/sim_beta/disconnect')
        status = _http('GET', '/devices/sim_beta/status')
        assert status['data']['status'] == 'disconnected'


class TestVirtualDeviceDataQuality:
    """测试波形数据质量。"""

    def test_waveform_amplitude_range(self, vdev_server):
        """波形幅度应在合理范围内（正弦波 + 噪声，峰峰值在 50-150 uV）"""
        _http('POST', '/devices/sim_alpha/connect')
        _http('POST', '/devices/sim_alpha/start')
        time.sleep(0.5)
        resp = _http('GET', '/devices/sim_alpha/data?count=50')
        frames = resp['data']['frames']
        all_values = [abs(ch) for f in frames for ch in f['channels']]
        avg_abs = sum(all_values) / len(all_values)
        # Alpha 模拟器各通道幅度 50/60/70 µV，叠加噪声后绝对值均值应在20-70范围
        assert 15 < avg_abs < 75, f'Average absolute amplitude {avg_abs} outside expected range'

    def test_waveform_not_constant(self, vdev_server):
        """波形应随时间变化（不是常量）"""
        _http('POST', '/devices/sim_alpha/connect')
        _http('POST', '/devices/sim_alpha/start')
        time.sleep(0.5)
        resp = _http('GET', '/devices/sim_alpha/data?count=50')
        frames = resp['data']['frames']
        # 同一通道在不同帧的值应不同
        ch0_values = [f['channels'][0] for f in frames]
        assert len(set(ch0_values)) > 1, 'Waveform is constant - values do not change'

    def test_waveform_frame_order(self, vdev_server):
        """帧序号应严格递增"""
        _http('POST', '/devices/sim_alpha/connect')
        _http('POST', '/devices/sim_alpha/start')
        time.sleep(0.5)
        resp = _http('GET', '/devices/sim_alpha/data?count=50')
        frames = resp['data']['frames']
        seqs = [f['seq'] for f in frames]
        assert all(seqs[i] < seqs[i + 1] for i in range(len(seqs) - 1)), \
            'Frame seq numbers are not monotonically increasing'

    def test_channel_count_consistency(self, vdev_server):
        """每帧通道数应一致"""
        _http('POST', '/devices/sim_multi/connect')
        _http('POST', '/devices/sim_multi/start')
        time.sleep(0.5)
        resp = _http('GET', '/devices/sim_multi/data?count=30')
        frames = resp['data']['frames']
        ch_counts = [len(f['channels']) for f in frames]
        assert all(c == 8 for c in ch_counts), f'Inconsistent channel counts: {set(ch_counts)}'

    def test_sample_rate_accuracy(self, vdev_server):
        """采样率应准确（250Hz 设备在 1.2 秒内应生成约 300 帧）。"""
        _http('POST', '/devices/sim_alpha/connect')
        _http('POST', '/devices/sim_alpha/start')
        time.sleep(1.2)
        resp = _http('GET', '/devices/sim_alpha/data?count=500')
        frames = resp['data']['frames']
        # 250Hz × 1.2s = 300 帧预期。catch-up 循环可防止漂移，
        # 但启动瞬间线程调度抖动可能损失少量帧，放宽到 ≥150（-50% 容差）。
        # 此前断言 >= 50（-83% 偏差）形同虚设，无法发现采样率错误。
        assert len(frames) >= 150, (
            f'250Hz in 1.2s should yield ~300 frames, got {len(frames)} (<50% suggests sample-rate bug)'
        )

    def test_data_deque_maxlen(self, vdev_server):
        """数据队列不应无限增长（maxlen=4000）"""
        _http('POST', '/devices/sim_alpha/connect')
        _http('POST', '/devices/sim_alpha/start')
        time.sleep(5)  # 长时间运行
        resp = _http('GET', '/devices/sim_alpha/data?count=5000')
        assert resp['ok'] is True
        # 即使请求5000帧，也应只返回队列中现有的数据
        frames = resp['data']['frames']
        assert len(frames) <= 4500, f'Queue exceeded maxlen: {len(frames)}'


class TestVirtualDeviceConcurrency:
    """测试并发场景。"""

    def test_multiple_devices_simultaneously(self, vdev_server):
        """5 个设备同时采集"""
        for dev_id in ['sim_alpha', 'sim_beta', 'sim_theta', 'sim_gamma', 'sim_multi']:
            _http('POST', f'/devices/{dev_id}/connect')
            _http('POST', f'/devices/{dev_id}/start')

        time.sleep(0.5)

        for dev_id in ['sim_alpha', 'sim_beta', 'sim_theta', 'sim_gamma', 'sim_multi']:
            resp = _http('GET', f'/devices/{dev_id}/status')
            assert resp['data']['status'] == 'acquiring', f'{dev_id} not acquiring'
            assert resp['data']['pending_count'] > 0, f'{dev_id} has no data'

    def test_connect_already_acquiring(self, vdev_server):
        """在采集状态下 connect 不应改变状态"""
        _http('POST', '/devices/sim_alpha/connect')
        _http('POST', '/devices/sim_alpha/start')
        resp = _http('POST', '/devices/sim_alpha/connect')
        assert resp['ok'] is True
        # 应保持 acquiring
        status = _http('GET', '/devices/sim_alpha/status')
        assert status['data']['status'] == 'acquiring'


class TestVirtualDeviceCrossOriginAndCORS:
    """测试 CORS 头。"""

    def test_cors_headers_on_get(self, vdev_server):
        from urllib.request import Request, urlopen
        req = Request(f'{TEST_BASE}/health')
        with urlopen(req, timeout=5) as resp:
            assert resp.headers.get('Access-Control-Allow-Origin') == '*'

    def test_cors_headers_on_options(self, vdev_server):
        from urllib.request import Request, urlopen
        req = Request(f'{TEST_BASE}/devices', method='OPTIONS')
        # 服务器实现了 do_OPTIONS（virtual_device_server.py L261）返回 204 + CORS 头
        with urlopen(req, timeout=5) as resp:
            assert resp.status == 204, f'OPTIONS should return 204, got {resp.status}'
            assert resp.headers.get('Access-Control-Allow-Origin') == '*'
            assert 'GET' in resp.headers.get('Access-Control-Allow-Methods', '')


class TestRealDeviceViewsSimulatorEndpoints:
    """通过 Django real_device_views 测试模拟设备集成（需要Django运行）。"""

    def test_device_manager_routes_to_simulator(self, vdev_server):
        """DeviceDriverManager 应将 sim_alpha 路由到 SimulatorDriver"""
        from eeg_app.drivers.manager import get_device_manager
        manager = get_device_manager()
        manager.load_all()
        devices = manager.discover_all()
        sim_meta = [d for d in devices if d.device_id == 'sim_alpha']
        assert len(sim_meta) > 0, 'sim_alpha not discovered'
        assert sim_meta[0].driver_type == 'simulated'
