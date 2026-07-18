"""Django HTTP 视图层单元测试。

覆盖 views.py 和 real_device_views.py 的所有 HTTP API 端点。
使用 Django TestClient + mock 设备管理器，不依赖真实硬件。

运行：
    pytest backend/eeg_app/tests/test_http_views.py -v
"""
import json
from unittest.mock import patch, MagicMock

import pytest
from django.test import Client

pytestmark = pytest.mark.django_db


@pytest.fixture
def client():
    return Client()


@pytest.fixture(autouse=True)
def _stop_runtime():
    """每个测试前后确保运行时停止（运行时禁止改图）。"""
    from eeg_app.graph_store import stop_graph, set_frozen
    stop_graph()
    set_frozen(False)
    yield
    stop_graph()
    set_frozen(False)


# ================================================================== //
#  基础端点
# ================================================================== //

class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        resp = client.get('/api/health/')
        assert resp.status_code == 200
        body = resp.json()
        assert body['status'] == 'ok'


class TestStatusEndpoint:
    def test_status_returns_runtime_and_perf(self, client):
        resp = client.get('/api/status/')
        assert resp.status_code == 200
        body = resp.json()
        assert body['ok'] is True
        assert 'runtime' in body
        assert 'running' in body['runtime']
        assert 'mode' in body['runtime']
        assert 'frozen' in body['runtime']

    def test_status_reflects_running_state(self, client):
        from eeg_app.graph_store import run_graph, stop_graph
        stop_graph()
        resp1 = client.get('/api/status/').json()
        assert resp1['runtime']['running'] is False

        # 设置一张最小图后运行
        from eeg_app.graph_store import set_graph
        set_graph({'nodes': [], 'edges': [], 'frozen': True})
        run_graph('live')
        resp2 = client.get('/api/status/').json()
        assert resp2['runtime']['running'] is True
        stop_graph()


# ================================================================== //
#  图 API
# ================================================================== //

class TestGraphEndpoint:
    def test_get_graph_returns_structure(self, client):
        resp = client.get('/api/graph/')
        assert resp.status_code == 200
        body = resp.json()
        assert 'nodes' in body
        assert 'edges' in body
        assert 'frozen' in body
        assert 'revision' in body
        assert 'persistedRevision' in body
        assert isinstance(body['nodes'], list)
        assert isinstance(body['edges'], list)

    def test_post_graph_rejected(self, client):
        """POST /api/graph/ 应返回 405（图修改走 WebSocket）。"""
        resp = client.post('/api/graph/', data=json.dumps({'nodes': []}), content_type='application/json')
        assert resp.status_code == 405


class TestGraphDebugEndpoint:
    def test_debug_post_returns_ok(self, client):
        resp = client.post(
            '/api/graph/debug/',
            data=json.dumps({'test': 'value'}),
            content_type='application/json',
        )
        assert resp.status_code == 200
        assert resp.json()['ok'] is True

    def test_debug_get_rejected(self, client):
        resp = client.get('/api/graph/debug/')
        assert resp.status_code == 405


class TestPythonPrototypeEndpoint:
    def test_prototype_post_returns_spec(self, client):
        resp = client.post(
            '/api/graph/python/prototype/',
            data=json.dumps({'inputCount': 2, 'outputCount': 1, 'functionName': 'test_fn'}),
            content_type='application/json',
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body['ok'] is True

    def test_prototype_get_rejected(self, client):
        resp = client.get('/api/graph/python/prototype/')
        assert resp.status_code == 405


class TestPythonLibraryEndpoint:
    def test_library_get_returns_code(self, client):
        resp = client.get('/api/graph/python/library/')
        assert resp.status_code == 200
        body = resp.json()
        assert body['ok'] is True
        assert 'library' in body


class TestSavedFilesEndpoint:
    def test_saved_files_returns_list(self, client):
        resp = client.get('/api/saved-files/')
        assert resp.status_code == 200
        body = resp.json()
        assert body['ok'] is True
        assert 'files' in body

    def test_saved_files_post_rejected(self, client):
        resp = client.post('/api/saved-files/')
        assert resp.status_code == 405


class TestReplayableFilesEndpoint:
    def test_replayable_files_returns_list(self, client):
        resp = client.get('/api/replayable-files/')
        assert resp.status_code == 200
        body = resp.json()
        assert body['ok'] is True
        assert 'files' in body


# ================================================================== //
#  录制 API
# ================================================================== //

class TestRecordEndpoint:
    def test_record_delete_stops_all(self, client):
        resp = client.delete('/api/graph/record/')
        assert resp.status_code == 200
        body = resp.json()
        assert body['ok'] is True
        assert body['recording'] is False


# ================================================================== //
#  设备管理 API（mock 设备管理器）
# ================================================================== //

class TestRealDevicesEndpoint:
    """GET /api/real-devices/ 列表端点。"""

    def test_real_devices_returns_list(self, client):
        resp = client.get('/api/real-devices/')
        assert resp.status_code == 200
        body = resp.json()
        # 响应结构：{ok, data: {devices: [...], count: N}} 或 {data: [...]}
        data = body.get('data', body)
        if isinstance(data, dict):
            assert 'devices' in data
            assert isinstance(data['devices'], list)
        else:
            assert isinstance(data, list)

    def test_devices_compat_delegates_to_real_devices(self, client):
        """/api/devices/ 向后兼容端点。"""
        resp = client.get('/api/devices/')
        assert resp.status_code == 200
        body = resp.json()
        assert 'data' in body


class TestScanPortsEndpoint:
    def test_scan_ports_returns_list(self, client):
        resp = client.get('/api/real-devices/scan-ports/')
        assert resp.status_code == 200
        body = resp.json()
        # 响应结构：{data: {ports: [...], count: N}}
        data = body.get('data', body)
        if isinstance(data, dict):
            assert 'ports' in data
            assert isinstance(data['ports'], list)
        else:
            assert isinstance(data, list)


class TestDeviceStatusEndpoint:
    def test_device_status_returns_dict(self, client):
        resp = client.get('/api/real-devices/status/')
        assert resp.status_code == 200
        body = resp.json()
        assert 'data' in body


class TestSimulatorStatusEndpoint:
    def test_simulator_status_returns_data(self, client):
        resp = client.get('/api/real-devices/simulator/status/')
        assert resp.status_code == 200
        body = resp.json()
        assert 'data' in body


class TestCreateDeviceEndpoint:
    def test_create_device_with_valid_payload(self, client):
        resp = client.post(
            '/api/real-devices/',
            data=json.dumps({
                'id': 'test-device-e2e',
                'name': '测试设备',
                'type': 'simulated',
                'config': {'sampleRate': 250, 'channels': 4},
            }),
            content_type='application/json',
        )
        # 创建可能成功或返回已有设备
        assert resp.status_code in (200, 201)

    def test_create_device_invalid_json(self, client):
        """无效 JSON 应返回 400。"""
        resp = client.post(
            '/api/real-devices/',
            data='not json',
            content_type='application/json',
        )
        assert resp.status_code == 400

    def test_create_device_returns_device_info(self, client):
        """创建设备后返回设备信息结构。"""
        resp = client.post(
            '/api/real-devices/',
            data=json.dumps({
                'name': '结构测试设备',
                'type': 'simulated',
                'sampling_rate': 500,
                'channel_count': 8,
            }),
            content_type='application/json',
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body['ok'] is True
        device = body['data']
        assert 'id' in device
        assert 'name' in device
        assert 'type' in device


class TestDebugOutputEndpoint:
    def test_debug_output_returns_structure(self, client):
        resp = client.get('/api/real-devices/debug-output/?count=10')
        assert resp.status_code == 200
        body = resp.json()
        assert 'data' in body

    def test_debug_output_port_entries_have_raw_fields(self, client):
        resp = client.get('/api/real-devices/debug-output/?count=5')
        body = resp.json()
        assert body['ok'] is True
        for port in body['data']['ports']:
            assert 'samples' in port
            assert 'count' in port
            assert 'raw_inputs' in port
            assert 'raw_input_count' in port
            assert isinstance(port['raw_inputs'], list)
            assert port['raw_input_count'] == len(port['raw_inputs'])


class TestListDriversEndpoint:
    def test_list_drivers_returns_structure(self, client):
        resp = client.get('/api/real-devices/drivers/')
        assert resp.status_code == 200
        body = resp.json()
        assert body['ok'] is True
        assert 'drivers' in body['data']
        assert 'count' in body['data']
        assert body['data']['count'] == len(body['data']['drivers'])

    def test_list_drivers_entries_have_required_fields(self, client):
        resp = client.get('/api/real-devices/drivers/')
        body = resp.json()
        for drv in body['data']['drivers']:
            for key in ('driver_type', 'driver_name', 'driver_description',
                        'device_count', 'module', 'class_name'):
                assert key in drv, f'missing key: {key}'

    def test_list_drivers_includes_builtin_drivers(self, client):
        resp = client.get('/api/real-devices/drivers/')
        body = resp.json()
        types = {d['driver_type'] for d in body['data']['drivers']}
        assert 'wearable_eeg' in types
        assert 'simulated' in types
