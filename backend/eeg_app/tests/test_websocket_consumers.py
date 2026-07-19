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

    async def _get_state(self, communicator):
        """发送 get_state 并等待 type=state 消息。"""
        await communicator.send_json_to({'type': 'get_state'})
        attempts = 0
        while attempts < 10:
            msg = await communicator.receive_json_from(timeout=5)
            if msg.get('type') == 'state':
                return msg
            attempts += 1
        raise AssertionError(f'No state message received after {attempts} messages')

    async def test_freeze_command(self):
        comm = await self._connect_and_skip_state()
        try:
            # 先解冻确保干净状态
            await self._send_cmd_and_get_result(comm, {'type': 'freeze', 'frozen': False})

            result = await self._send_cmd_and_get_result(comm, {'type': 'freeze', 'frozen': True})
            assert result['command'] == 'freeze'
            assert result['ok'] is True

            # 核验最终状态：get_state 中 graph.frozen 必须为 True
            state = await self._get_state(comm)
            assert state['graph']['frozen'] is True, (
                f'freeze 后 graph.frozen 应为 True，实际 {state["graph"].get("frozen")}'
            )
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

            # 核验图真的落库：get_state 应返回 2 节点 1 边，id 集合一致
            state = await self._get_state(comm)
            nodes = state['graph']['nodes']
            edges = state['graph']['edges']
            assert len(nodes) == 2, f'期望 2 节点，实际 {len(nodes)}'
            assert {n['id'] for n in nodes} == {'ws-test-src', 'ws-test-out'}
            assert len(edges) == 1, f'期望 1 边，实际 {len(edges)}'
            assert edges[0]['source'] == 'ws-test-src'
            assert edges[0]['target'] == 'ws-test-out'
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

            # 核验运行状态：runtime.running 必须为 True 且 mode=live
            state = await self._get_state(comm)
            assert state['runtime']['running'] is True, (
                f'run 后 running 应为 True，实际 {state["runtime"].get("running")}'
            )
            assert state['runtime']['mode'] == 'live'

            # 停止
            stop_result = await self._send_cmd_and_get_result(comm, {'type': 'stop'})
            assert stop_result['ok'] is True

            # 核验停止状态：runtime.running 必须为 False
            state = await self._get_state(comm)
            assert state['runtime']['running'] is False, (
                f'stop 后 running 应为 False，实际 {state["runtime"].get("running")}'
            )

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
                # 错误消息必须指出未知命令名
                assert 'Unknown command' in msg['error'], f'错误消息应含 Unknown command: {msg["error"]}'
                assert 'nonexistent_command' in msg['error']
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

        # subscribe/unsubscribe 无 ack，用 ping→pong 验证 consumer 处理完上述消息后仍存活
        await communicator.send_json_to({'type': 'ping'})
        msg = await communicator.receive_json_from(timeout=5)
        attempts = 0
        while msg.get('type') != 'pong' and attempts < 10:
            msg = await communicator.receive_json_from(timeout=2)
            attempts += 1
        assert msg.get('type') == 'pong', 'subscribe/unsubscribe 后 consumer 不再响应'

        await communicator.disconnect()

    async def test_ping_pong(self):
        communicator = WebsocketCommunicator(application, '/ws/eeg/')
        connected, _ = await communicator.connect()
        assert connected

        await communicator.send_json_to({'type': 'ping'})
        # ws/eeg consumer 收到 ping 必须回 pong（graph_consumer_v2.py L241-242），
        # 期间可能夹杂 data 推送（若图在运行），需跳过。
        msg = await communicator.receive_json_from(timeout=5)
        attempts = 0
        while msg.get('type') != 'pong' and attempts < 10:
            try:
                msg = await communicator.receive_json_from(timeout=2)
            except Exception:
                break
            attempts += 1
        assert msg.get('type') == 'pong', (
            f'Expected pong after ping, got {msg.get("type")} after {attempts} retries'
        )

        await communicator.disconnect()
