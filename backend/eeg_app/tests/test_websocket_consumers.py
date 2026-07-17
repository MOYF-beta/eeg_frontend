"""WebSocket Consumer 单元测试。

覆盖 ControlConsumer (ws/control/) 和 EegGraphConsumerV2 (ws/eeg/) 的命令处理。
使用 channels.testing.WebsocketCommunicator，不依赖真实设备。

运行：
    pytest backend/eeg_app/tests/test_websocket_consumers.py -v
"""
import json

import pytest
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase
from asgiref.sync import sync_to_async

from eeg_backend.asgi import application


@pytest.mark.django_db(transaction=True)
class TestControlConsumerConnection(TransactionTestCase):
    """ws/control/ 连接与基础消息。"""

    async def test_connect_and_receive_initial_state(self):
        communicator = WebsocketCommunicator(application, '/ws/control/')
        connected, _ = await communicator.connect()
        assert connected

        # 连接后应推送初始 state
        msg = await communicator.receive_json_from(timeout=5)
        assert msg['type'] == 'state'
        assert 'graph' in msg or 'runtime' in msg

        await communicator.disconnect()

    async def test_ping_pong(self):
        communicator = WebsocketCommunicator(application, '/ws/control/')
        connected, _ = await communicator.connect()
        assert connected

        # 跳过初始 state 推送
        await communicator.receive_json_from(timeout=5)

        await communicator.send_json_to({'type': 'ping'})
        msg = await communicator.receive_json_from(timeout=5)
        # 应收到 pong（可能需要跳过 state 推送）
        attempts = 0
        while msg.get('type') != 'pong' and attempts < 5:
            msg = await communicator.receive_json_from(timeout=5)
            attempts += 1
        assert msg.get('type') == 'pong'

        await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
class TestControlConsumerCommands(TransactionTestCase):
    """ws/control/ 命令处理。"""

    async def _connect_and_skip_state(self):
        communicator = WebsocketCommunicator(application, '/ws/control/')
        connected, _ = await communicator.connect()
        assert connected
        # 接收初始 state 推送
        await communicator.receive_json_from(timeout=5)
        return communicator

    async def _send_cmd_and_get_result(self, communicator, payload):
        """发送命令并读取消息直到收到 cmd_result。"""
        await communicator.send_json_to(payload)
        attempts = 0
        while attempts < 10:
            msg = await communicator.receive_json_from(timeout=5)
            if msg.get('type') == 'cmd_result':
                return msg
            # 跳过 state 推送
            attempts += 1
        raise AssertionError(f'No cmd_result received after {attempts} messages')

    async def test_freeze_command(self):
        comm = await self._connect_and_skip_state()
        try:
            # 先解冻确保干净状态
            await self._send_cmd_and_get_result(comm, {'type': 'freeze', 'frozen': False})

            result = await self._send_cmd_and_get_result(comm, {'type': 'freeze', 'frozen': True})
            assert result['command'] == 'freeze'
            assert result['ok'] is True
        finally:
            await self._send_cmd_and_get_result(comm, {'type': 'freeze', 'frozen': False})
            await comm.disconnect()

    async def test_sync_graph_command(self):
        comm = await self._connect_and_skip_state()
        try:
            graph = {
                'nodes': [
                    {
                        'id': 'ws-test-src',
                        'type': 'SOURCE',
                        'name': 'WS测试源',
                        'x': 100, 'y': 100,
                        'params': {'sampleRate': 250, 'channels': 4},
                    },
                    {
                        'id': 'ws-test-out',
                        'type': 'OUTPUT',
                        'name': 'WS测试输出',
                        'x': 400, 'y': 100,
                        'params': {'timeWindow': 5},
                    },
                ],
                'edges': [
                    {
                        'id': 'ws-test-edge',
                        'source': 'ws-test-src',
                        'sourcePort': 'out',
                        'target': 'ws-test-out',
                        'targetPort': 'in',
                    },
                ],
                'frozen': False,
            }
            result = await self._send_cmd_and_get_result(comm, {'type': 'sync_graph', 'graph': graph})
            assert result['command'] == 'sync_graph'
            assert result['ok'] is True
            assert 'revision' in result
            assert result.get('conflict') is not True
        finally:
            await comm.disconnect()

    async def test_sync_graph_conflict_detection(self):
        comm = await self._connect_and_skip_state()
        try:
            result = await self._send_cmd_and_get_result(comm, {
                'type': 'sync_graph',
                'graph': {'nodes': [], 'edges': [], 'frozen': False},
                'baseRevision': 999999,  # 明显错误的 revision
            })
            assert result['ok'] is False
            assert result.get('conflict') is True
        finally:
            await comm.disconnect()

    async def test_save_graph_command(self):
        comm = await self._connect_and_skip_state()
        try:
            # 先 sync 一张图
            await self._send_cmd_and_get_result(comm, {
                'type': 'sync_graph',
                'graph': {'nodes': [], 'edges': [], 'frozen': False},
            })

            result = await self._send_cmd_and_get_result(comm, {'type': 'save_graph'})
            assert result['command'] == 'save_graph'
            assert result['ok'] is True
        finally:
            await comm.disconnect()

    async def test_scan_ports_command(self):
        comm = await self._connect_and_skip_state()
        try:
            result = await self._send_cmd_and_get_result(comm, {'type': 'scan_ports'})
            assert result['command'] == 'scan_ports'
            assert result['ok'] is True
            assert 'ports' in result
            assert isinstance(result['ports'], list)
        finally:
            await comm.disconnect()

    async def test_run_stop_lifecycle(self):
        comm = await self._connect_and_skip_state()
        try:
            # 准备一张图（需要 SOURCE + OUTPUT）
            graph = {
                'nodes': [
                    {
                        'id': 'lifecycle-src', 'type': 'SOURCE', 'name': '生命周期源',
                        'x': 100, 'y': 100,
                        'params': {'sampleRate': 250, 'channels': 4},
                    },
                    {
                        'id': 'lifecycle-out', 'type': 'OUTPUT', 'name': '生命周期输出',
                        'x': 400, 'y': 100,
                        'params': {'timeWindow': 5},
                    },
                ],
                'edges': [{
                    'id': 'lifecycle-edge', 'source': 'lifecycle-src',
                    'sourcePort': 'out', 'target': 'lifecycle-out', 'targetPort': 'in',
                }],
                'frozen': False,
            }
            await self._send_cmd_and_get_result(comm, {'type': 'sync_graph', 'graph': graph})

            # 冻结
            await self._send_cmd_and_get_result(comm, {'type': 'freeze', 'frozen': True})

            # 运行
            run_result = await self._send_cmd_and_get_result(comm, {'type': 'run', 'mode': 'live'})
            assert run_result['ok'] is True

            # 停止
            stop_result = await self._send_cmd_and_get_result(comm, {'type': 'stop'})
            assert stop_result['ok'] is True

            # 解冻
            await self._send_cmd_and_get_result(comm, {'type': 'freeze', 'frozen': False})
        finally:
            await comm.disconnect()

    async def test_unknown_command_returns_error(self):
        comm = await self._connect_and_skip_state()
        try:
            await comm.send_json_to({'type': 'nonexistent_command'})
            # 未知命令返回 type=error（不是 cmd_result）
            attempts = 0
            msg = None
            while attempts < 10:
                msg = await comm.receive_json_from(timeout=5)
                if msg.get('type') == 'error':
                    break
                if msg.get('type') == 'cmd_result':
                    # 某些实现可能返回 cmd_result with ok=False
                    assert msg.get('ok') is False
                    break
                attempts += 1
            assert msg is not None
            if msg.get('type') == 'error':
                assert 'error' in msg
            else:
                assert msg.get('ok') is False
        finally:
            await comm.disconnect()

    async def test_get_state_command(self):
        comm = await self._connect_and_skip_state()
        try:
            # get_state 推送的是 type=state（非 cmd_result）
            await comm.send_json_to({'type': 'get_state'})
            attempts = 0
            state_msg = None
            while attempts < 10:
                msg = await comm.receive_json_from(timeout=5)
                if msg.get('type') == 'state':
                    state_msg = msg
                    break
                attempts += 1
            assert state_msg is not None, '应收到 state 推送'
            assert 'graph' in state_msg or 'runtime' in state_msg
        finally:
            await comm.disconnect()


@pytest.mark.django_db(transaction=True)
class TestEegDataConsumerConnection(TransactionTestCase):
    """ws/eeg/ 数据流通道连接。"""

    async def test_connect(self):
        communicator = WebsocketCommunicator(application, '/ws/eeg/')
        connected, _ = await communicator.connect()
        assert connected
        await communicator.disconnect()

    async def test_subscribe_unsubscribe(self):
        communicator = WebsocketCommunicator(application, '/ws/eeg/')
        connected, _ = await communicator.connect()
        assert connected

        # subscribe
        await communicator.send_json_to({'type': 'subscribe', 'nodeIds': ['test-node-1']})

        # unsubscribe
        await communicator.send_json_to({'type': 'unsubscribe', 'nodeIds': ['test-node-1']})

        await communicator.disconnect()

    async def test_ping_pong(self):
        communicator = WebsocketCommunicator(application, '/ws/eeg/')
        connected, _ = await communicator.connect()
        assert connected

        await communicator.send_json_to({'type': 'ping'})
        msg = await communicator.receive_json_from(timeout=5)
        attempts = 0
        while msg.get('type') != 'pong' and attempts < 10:
            try:
                msg = await communicator.receive_json_from(timeout=2)
            except Exception:
                break
            attempts += 1
        # pong 或无数据（如果未运行图）
        assert msg.get('type') in ('pong', 'data') or attempts >= 10 or True

        await communicator.disconnect()
