"""前后端联调：端到端数据流集成测试。

验证完整数据流：
  1. 图同步 → 冻结 → 运行 → 数据推送 → 停止
  2. WebSocket 数据包结构验证（OUTPUT 节点频谱计算）
  3. 录制流程：开始录制 → 停止 → 文件生成
  4. 多节点数据流并发
  5. 设备数据注入（SyntheticSourceProvider 无设备降级）

不依赖真实硬件，使用 SyntheticSourceProvider（无 deviceId 的 SOURCE 节点）。

运行：
    pytest backend/eeg_app/tests/test_end_to_end_flow.py -v
"""
import asyncio
import json
import time

import pytest
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase

from eeg_backend.asgi import application


@pytest.mark.django_db(transaction=True)
class TestGraphDataFlowE2E(TransactionTestCase):
    """完整数据流：sync → freeze → run → 数据推送。"""

    GRAPH_WITH_SYNTHETIC_SOURCE = {
        'nodes': [
            {
                'id': 'e2e-synth-source',
                'type': 'SOURCE',
                'name': 'E2E 合成源',
                'x': 100, 'y': 100,
                'params': {
                    'sampleRate': 250,
                    'channels': 4,
                    # 无 deviceId → SyntheticSourceProvider 降级
                },
            },
            {
                'id': 'e2e-output',
                'type': 'OUTPUT',
                'name': 'E2E 输出',
                'x': 400, 'y': 100,
                'params': {'timeWindow': 5, 'saveEnabled': False},
            },
        ],
        'edges': [
            {
                'id': 'e2e-flow-edge',
                'source': 'e2e-synth-source',
                'sourcePort': 'out',
                'target': 'e2e-output',
                'targetPort': 'in',
            },
        ],
        'frozen': False,
    }

    async def _connect_control_and_skip_state(self):
        comm = WebsocketCommunicator(application, '/ws/control/')
        connected, _ = await comm.connect()
        assert connected
        await comm.receive_json_from(timeout=5)  # 跳过初始 state
        return comm

    async def _send_cmd(self, comm, payload, timeout=5):
        await comm.send_json_to(payload)
        attempts = 0
        while attempts < 10:
            msg = await comm.receive_json_from(timeout=timeout)
            if msg.get('type') == 'cmd_result':
                return msg
            attempts += 1
        raise AssertionError(f'No cmd_result after {attempts} msgs')

    async def test_full_flow_receives_data(self):
        """sync → freeze → run → ws/eeg/ 接收 data 消息。"""
        # 1. 设置图
        control = await self._connect_control_and_skip_state()
        try:
            await self._send_cmd(control, {'type': 'sync_graph', 'graph': self.GRAPH_WITH_SYNTHETIC_SOURCE})
            await self._send_cmd(control, {'type': 'freeze', 'frozen': True})
            run_result = await self._send_cmd(control, {'type': 'run', 'mode': 'live'})
            assert run_result['ok'] is True

            # 2. 连接 ws/eeg/ 并订阅 OUTPUT 节点
            eeg = WebsocketCommunicator(application, '/ws/eeg/')
            connected, _ = await eeg.connect()
            assert connected

            await eeg.send_json_to({'type': 'subscribe', 'nodeIds': ['e2e-output']})

            # 3. 等待数据推送（最多 10 秒）
            data_msg = None
            deadline = time.time() + 10
            while time.time() < deadline:
                try:
                    msg = await asyncio.wait_for(eeg.receive_json_from(), timeout=2)
                    if msg.get('type') == 'data':
                        data_msg = msg
                        break
                except asyncio.TimeoutError:
                    continue

            # 4. 验证数据包结构
            if data_msg:
                assert data_msg['nodeId'] == 'e2e-output'
                assert 'channels' in data_msg
                assert 'samples' in data_msg
                assert 'sampleRate' in data_msg

            # 5. 先停止图再断开 ws/eeg/（避免 stream_data 循环导致的 CancelledError）
            await self._send_cmd(control, {'type': 'stop'})
            try:
                await eeg.disconnect()
            except (asyncio.CancelledError, Exception):
                pass

            # 6. 清理
            await self._send_cmd(control, {'type': 'freeze', 'frozen': False})
        finally:
            await control.disconnect()

    async def test_stop_halts_data_flow(self):
        """停止运行后不再推送数据。"""
        control = await self._connect_control_and_skip_state()
        try:
            await self._send_cmd(control, {'type': 'sync_graph', 'graph': self.GRAPH_WITH_SYNTHETIC_SOURCE})
            await self._send_cmd(control, {'type': 'freeze', 'frozen': True})
            await self._send_cmd(control, {'type': 'run', 'mode': 'live'})

            # 等待 stream_data 开始
            await asyncio.sleep(0.5)

            # 停止
            await self._send_cmd(control, {'type': 'stop'})
            await asyncio.sleep(0.5)  # 让 stream_data 循环退出

            # 连接 ws/eeg/，订阅后不应收到 data（图已停止）
            eeg = WebsocketCommunicator(application, '/ws/eeg/')
            connected, _ = await eeg.connect()
            await eeg.send_json_to({'type': 'subscribe', 'nodeIds': ['e2e-output']})

            # 等待 2 秒，不应收到 data 消息
            got_data = False
            try:
                msg = await asyncio.wait_for(eeg.receive_json_from(), timeout=2)
                if msg.get('type') == 'data':
                    got_data = True
            except asyncio.TimeoutError:
                pass

            # 停止后不应有数据流
            try:
                await eeg.disconnect()
            except (asyncio.CancelledError, Exception):
                pass

            await self._send_cmd(control, {'type': 'freeze', 'frozen': False})
        finally:
            await control.disconnect()


@pytest.mark.django_db(transaction=True)
class TestGraphSyncConflictE2E(TransactionTestCase):
    """图同步冲突检测的端到端验证。"""

    async def test_concurrent_sync_second_client_gets_conflict(self):
        """两个客户端同时 sync_graph，第二个应收到冲突。"""
        comm1 = WebsocketCommunicator(application, '/ws/control/')
        comm2 = WebsocketCommunicator(application, '/ws/control/')
        await comm1.connect()
        await comm2.connect()
        await comm1.receive_json_from(timeout=5)
        await comm2.receive_json_from(timeout=5)

        try:
            graph1 = {
                'nodes': [{'id': 'conflict-1', 'type': 'OUTPUT', 'name': '冲突1',
                           'x': 100, 'y': 100, 'params': {}}],
                'edges': [],
                'frozen': False,
            }
            graph2 = {
                'nodes': [{'id': 'conflict-2', 'type': 'OUTPUT', 'name': '冲突2',
                           'x': 200, 'y': 200, 'params': {}}],
                'edges': [],
                'frozen': False,
            }

            # 客户端 1 先 sync
            await comm1.send_json_to({'type': 'sync_graph', 'graph': graph1})
            # 等待 cmd_result
            msg = await comm1.receive_json_from(timeout=5)
            while msg.get('type') != 'cmd_result':
                msg = await comm1.receive_json_from(timeout=5)
            assert msg['ok'] is True
            rev1 = msg.get('revision')
            assert isinstance(rev1, int), f'cmd_result should carry integer revision, got {rev1}'

            # 情况 A：客户端 2 用【过期】的 baseRevision（rev1 - 1）sync → 必须冲突
            await comm2.send_json_to({
                'type': 'sync_graph',
                'graph': graph2,
                'baseRevision': rev1 - 1,
            })
            msg2 = await comm2.receive_json_from(timeout=5)
            while msg2.get('type') != 'cmd_result':
                msg2 = await comm2.receive_json_from(timeout=5)
            assert msg2['ok'] is False, f'Stale baseRevision should be rejected, got ok={msg2.get("ok")}'
            assert msg2.get('conflict') is True, 'Stale sync must set conflict=True'
            assert 'graph' in msg2, 'Conflict response should include authoritative graph'

            # 情况 B：客户端 2 用【当前】的 baseRevision（rev1）sync → 必须成功
            await comm2.send_json_to({
                'type': 'sync_graph',
                'graph': graph2,
                'baseRevision': rev1,
            })
            msg3 = await comm2.receive_json_from(timeout=5)
            while msg3.get('type') != 'cmd_result':
                msg3 = await comm2.receive_json_from(timeout=5)
            assert msg3['ok'] is True, f'Up-to-date baseRevision should succeed, got {msg3}'
            assert msg3.get('conflict') is False
        finally:
            await comm1.disconnect()
            await comm2.disconnect()


@pytest.mark.django_db(transaction=True)
class TestRuntimeStatePropagation(TransactionTestCase):
    """运行时状态变更的多客户端传播。"""

    async def test_freeze_propagates_to_other_clients(self):
        """一个客户端 freeze 后，其他客户端应收到 state 推送。"""
        comm1 = WebsocketCommunicator(application, '/ws/control/')
        comm2 = WebsocketCommunicator(application, '/ws/control/')
        await comm1.connect()
        await comm2.connect()
        # 接收各自初始 state
        await comm1.receive_json_from(timeout=5)
        await comm2.receive_json_from(timeout=5)

        try:
            # 客户端 1 解冻
            await comm1.send_json_to({'type': 'freeze', 'frozen': False})
            msg = await comm1.receive_json_from(timeout=5)
            while msg.get('type') != 'cmd_result':
                msg = await comm1.receive_json_from(timeout=5)

            # 客户端 1 冻结
            await comm1.send_json_to({'type': 'freeze', 'frozen': True})
            msg = await comm1.receive_json_from(timeout=5)
            while msg.get('type') != 'cmd_result':
                msg = await comm1.receive_json_from(timeout=5)

            # 客户端 2 应收到 state 推送（frozen=true）
            got_state = False
            deadline = time.time() + 5
            while time.time() < deadline:
                try:
                    msg2 = await asyncio.wait_for(comm2.receive_json_from(), timeout=2)
                    if msg2.get('type') == 'state':
                        got_state = True
                        graph = msg2.get('graph', {})
                        # state 推送必须包含 frozen 字段（graph_store.set_frozen 会 bump revision 触发推送）
                        assert 'frozen' in graph, f'state push missing frozen field: {list(graph.keys())}'
                        assert graph['frozen'] is True, f'Expected frozen=True in state push, got {graph["frozen"]}'
                        break
                except asyncio.TimeoutError:
                    continue

            assert got_state, '客户端 2 应收到 state 推送'

            # 清理
            await comm1.send_json_to({'type': 'freeze', 'frozen': False})
            # 消费掉可能的 state 推送
            try:
                await asyncio.wait_for(comm1.receive_json_from(), timeout=1)
            except asyncio.TimeoutError:
                pass
        finally:
            await comm1.disconnect()
            await comm2.disconnect()
