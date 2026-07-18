"""故障注入驱动 + 前后端故障反馈链路测试。

验证目标：
1. `FaultyDriver` 各故障注入设备行为正确（连接失败/抛异常/间歇数据流/状态错误）。
2. `DeviceDriverManager` 对驱动异常做兜底（不向上抛、状态=ERROR、记录 last_error）。
3. HTTP 视图把驱动故障反馈到前端（last_error 字段、500 + error 消息、设备列表状态）。

运行：
    pytest backend/eeg_app/tests/test_faulty_driver.py -v
"""

import json

import pytest
from django.test import Client

from eeg_app.drivers.base import DeviceStatus
from eeg_app.drivers.manager import DeviceDriverManager, get_device_manager
from eeg_app.drivers._faulty_driver import (
    FaultyDriver,
    DEVICE_OK,
    DEVICE_CONNECT_ERROR,
    DEVICE_THROW,
    DEVICE_MYSTERY,
    DEVICE_FLAKY,
    DEVICE_STATUS_ERROR,
)

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------- #
#  fixtures
# ---------------------------------------------------------------------- #

@pytest.fixture
def manager_with_faulty():
    """独立 manager（不污染全局单例），仅注册故障驱动。"""
    mgr = DeviceDriverManager()
    drv = FaultyDriver()
    mgr.register_driver(drv)
    # 建立 device_index（模拟 discover_all 的效果）
    mgr.discover_all()
    return mgr, drv


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def global_manager_with_faulty():
    """在全局单例中注册故障驱动（供 HTTP 视图测试），测试后移除。"""
    mgr = get_device_manager()
    drv = FaultyDriver()
    mgr.register_driver(drv)
    mgr.discover_all()
    yield mgr, drv
    # 清理：从单例中摘除故障驱动，避免污染其他测试
    with mgr._lock:
        mgr._drivers.pop(FaultyDriver.driver_type(), None)
        for dev_id in list(mgr._device_index.keys()):
            if dev_id.startswith('flt_'):
                mgr._device_index.pop(dev_id, None)


# ---------------------------------------------------------------------- #
#  1. FaultyDriver 单元行为
# ---------------------------------------------------------------------- #

class TestFaultyDriverBasics:
    def test_driver_metadata(self):
        assert FaultyDriver.driver_type() == 'faulty'
        assert FaultyDriver.driver_name()
        assert FaultyDriver.driver_description()
        assert FaultyDriver.driver_icon().startswith('mdi-')

    def test_discover_returns_all_fault_devices(self, manager_with_faulty):
        _, drv = manager_with_faulty
        metas = drv.discover()
        ids = {m.device_id for m in metas}
        assert {DEVICE_OK, DEVICE_CONNECT_ERROR, DEVICE_THROW,
                DEVICE_MYSTERY, DEVICE_FLAKY, DEVICE_STATUS_ERROR} <= ids
        for m in metas:
            assert m.driver_type == 'faulty'
            assert m.channel_count == 2

    def test_ok_device_full_lifecycle(self, manager_with_faulty):
        mgr, _ = manager_with_faulty
        assert mgr.connect(DEVICE_OK) is True
        assert mgr.get_status(DEVICE_OK) == DeviceStatus.CONNECTED
        assert mgr.start_streaming(DEVICE_OK) is True
        assert mgr.get_status(DEVICE_OK) == DeviceStatus.ACQUIRING
        assert mgr.pending_count(DEVICE_OK) == 5
        frames = mgr.read_data(DEVICE_OK, count=3)
        assert len(frames) == 3
        assert all(f.device_id == DEVICE_OK for f in frames)
        assert mgr.pending_count(DEVICE_OK) == 2
        assert mgr.stop_streaming(DEVICE_OK) is True
        assert mgr.get_status(DEVICE_OK) == DeviceStatus.CONNECTED
        assert mgr.disconnect(DEVICE_OK) is True
        assert mgr.get_status(DEVICE_OK) == DeviceStatus.DISCONNECTED

    def test_connect_error_device_returns_false_and_records_error(self, manager_with_faulty):
        mgr, drv = manager_with_faulty
        assert mgr.connect(DEVICE_CONNECT_ERROR) is False
        # 驱动内部记录了 last_error，视图层可通过 get_last_error 读取
        assert drv.get_last_error(DEVICE_CONNECT_ERROR) is not None
        assert '握手超时' in drv.get_last_error(DEVICE_CONNECT_ERROR)
        # manager 层也能读到（用于 HTTP 反馈）
        assert mgr.get_last_error(DEVICE_CONNECT_ERROR) is not None

    def test_status_error_device_connects_but_status_is_error(self, manager_with_faulty):
        mgr, drv = manager_with_faulty
        assert mgr.connect(DEVICE_STATUS_ERROR) is True
        # connect 返回 True，但 get_status 恒为 ERROR（设备自检失败场景）
        assert mgr.get_status(DEVICE_STATUS_ERROR) == DeviceStatus.ERROR
        # 即使 connect 成功清除了缓存错误，持续性自检故障仍可通过 get_last_error 查到
        assert drv.get_last_error(DEVICE_STATUS_ERROR) is not None
        assert '自检失败' in drv.get_last_error(DEVICE_STATUS_ERROR)
        # 启动采集失败
        assert mgr.start_streaming(DEVICE_STATUS_ERROR) is False

    def test_mystery_device_fails_silently(self, manager_with_faulty):
        mgr, drv = manager_with_faulty
        assert mgr.connect(DEVICE_MYSTERY) is False
        # 驱动没有记录任何错误（模拟低质量驱动）
        assert drv.get_last_error(DEVICE_MYSTERY) is None

    def test_flaky_device_drops_frames(self, manager_with_faulty):
        mgr, _ = manager_with_faulty
        mgr.connect(DEVICE_FLAKY)
        mgr.start_streaming(DEVICE_FLAKY)
        # 填充 5 帧，丢包后只剩一半（向上取整 → 3 帧）
        assert mgr.pending_count(DEVICE_FLAKY) == 3


# ---------------------------------------------------------------------- #
#  2. Manager 对驱动异常的兜底
# ---------------------------------------------------------------------- #

class TestManagerFaultTolerance:
    def test_throwing_connect_is_contained(self, manager_with_faulty):
        mgr, _ = manager_with_faulty
        # 驱动抛异常不应向上传播
        assert mgr.connect(DEVICE_THROW) is False
        # 异常通过 handle_error 记录到 last_error
        assert mgr.get_last_error(DEVICE_THROW) is not None
        assert 'connect' in mgr.get_last_error(DEVICE_THROW)

    def test_throwing_get_status_returns_error(self, manager_with_faulty):
        mgr, _ = manager_with_faulty
        assert mgr.get_status(DEVICE_THROW) == DeviceStatus.ERROR

    def test_throwing_streaming_and_read_are_contained(self, manager_with_faulty):
        mgr, _ = manager_with_faulty
        assert mgr.start_streaming(DEVICE_THROW) is False
        assert mgr.stop_streaming(DEVICE_THROW) is False
        assert mgr.read_data(DEVICE_THROW, 5) == []
        assert mgr.pending_count(DEVICE_THROW) == 0
        assert mgr.read_raw_inputs(DEVICE_THROW, 5) == []

    def test_connect_with_feedback_success(self, manager_with_faulty):
        mgr, _ = manager_with_faulty
        fb = mgr.connect_with_feedback(DEVICE_OK)
        assert fb['ok'] is True
        assert fb['error'] is None

    def test_connect_with_feedback_records_driver_error(self, manager_with_faulty):
        mgr, _ = manager_with_faulty
        fb = mgr.connect_with_feedback(DEVICE_CONNECT_ERROR)
        assert fb['ok'] is False
        assert fb['error'] is not None
        assert '握手超时' in fb['error']

    def test_connect_with_feedback_fallback_when_driver_silent(self, manager_with_faulty):
        mgr, _ = manager_with_faulty
        fb = mgr.connect_with_feedback(DEVICE_MYSTERY)
        assert fb['ok'] is False
        # 驱动没记录错误时给出兜底提示
        assert fb['error'] == '连接失败'

    def test_connect_with_feedback_no_driver(self, manager_with_faulty):
        mgr, _ = manager_with_faulty
        fb = mgr.connect_with_feedback('nonexistent_device_xyz')
        assert fb['ok'] is False
        assert '没有可用于设备' in fb['error']

    def test_successful_connect_clears_last_error(self, manager_with_faulty):
        mgr, _ = manager_with_faulty
        # 先制造一次失败（把 ok 设备手动塞一个错误进去）
        mgr._drivers['faulty']._last_errors[DEVICE_OK] = 'stale error'
        fb = mgr.connect_with_feedback(DEVICE_OK)
        assert fb['ok'] is True
        assert mgr.get_last_error(DEVICE_OK) is None


# ---------------------------------------------------------------------- #
#  3. HTTP 视图层故障反馈
# ---------------------------------------------------------------------- #

class TestFaultyDriverHttpViews:
    def test_device_list_contains_fault_devices_with_status(self, client, global_manager_with_faulty):
        resp = client.get('/api/real-devices/')
        assert resp.status_code == 200
        body = resp.json()
        assert body['ok'] is True
        devices = {d['device_id']: d for d in body['data']['devices']}
        assert DEVICE_OK in devices
        assert DEVICE_CONNECT_ERROR in devices
        # 故障设备也在列表中，状态为 offline（未连接）
        assert devices[DEVICE_CONNECT_ERROR]['connection_status']['status'] == 'disconnected'

    def test_device_status_endpoint_exposes_last_error(self, client, global_manager_with_faulty):
        mgr, _ = global_manager_with_faulty
        # 制造一次失败
        mgr.connect(DEVICE_CONNECT_ERROR)
        resp = client.get(f'/api/real-devices/{DEVICE_CONNECT_ERROR}/status/')
        assert resp.status_code == 200
        body = resp.json()
        assert body['ok'] is True
        assert body['data']['status'] == 'error'
        assert body['data']['last_error'] is not None
        assert '握手超时' in body['data']['last_error']

    def test_connect_endpoint_returns_error_message_on_failure(self, client, global_manager_with_faulty):
        resp = client.post(
            '/api/real-devices/connect/',
            data=json.dumps({'port': DEVICE_CONNECT_ERROR, 'config': {}}),
            content_type='application/json',
        )
        assert resp.status_code == 500
        body = resp.json()
        assert body['ok'] is False
        # 前端能拿到具体失败原因（非笼统的 "Failed to connect device"）
        assert '握手超时' in body['error']
        assert body['data']['last_error'] is not None

    def test_connect_endpoint_fallback_message_for_silent_driver(self, client, global_manager_with_faulty):
        resp = client.post(
            '/api/real-devices/connect/',
            data=json.dumps({'port': DEVICE_MYSTERY, 'config': {}}),
            content_type='application/json',
        )
        assert resp.status_code == 500
        body = resp.json()
        assert body['ok'] is False
        assert body['error'] == '连接失败'

    def test_connect_endpoint_for_throwing_driver(self, client, global_manager_with_faulty):
        resp = client.post(
            '/api/real-devices/connect/',
            data=json.dumps({'port': DEVICE_THROW, 'config': {}}),
            content_type='application/json',
        )
        assert resp.status_code == 500
        body = resp.json()
        assert body['ok'] is False
        assert 'connect' in body['error']

    def test_connect_endpoint_success_clears_error(self, client, global_manager_with_faulty):
        resp = client.post(
            '/api/real-devices/connect/',
            data=json.dumps({'port': DEVICE_OK, 'config': {}}),
            content_type='application/json',
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body['ok'] is True
        assert body['data']['last_error'] is None
        assert body['data']['status'] == 'connected'

    def test_status_all_devices_includes_last_error_field(self, client, global_manager_with_faulty):
        mgr, _ = global_manager_with_faulty
        mgr.connect(DEVICE_CONNECT_ERROR)
        resp = client.get('/api/real-devices/status/')
        assert resp.status_code == 200
        body = resp.json()
        assert body['ok'] is True
        devices = {d['device_id']: d for d in body['data']['devices']}
        assert 'last_error' in devices[DEVICE_CONNECT_ERROR]
        assert 'last_error' in devices[DEVICE_OK]

    def test_throwing_driver_does_not_crash_device_list(self, client, global_manager_with_faulty):
        # 把 throw 设备连上再查列表：get_status 抛异常 → manager 兜底为 ERROR
        mgr, _ = global_manager_with_faulty
        try:
            mgr.connect(DEVICE_THROW)
        except Exception:
            pass
        resp = client.get('/api/real-devices/')
        assert resp.status_code == 200
        body = resp.json()
        assert body['ok'] is True
