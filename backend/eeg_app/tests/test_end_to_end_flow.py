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
import csv
import json
import time

import pytest
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase
from asgiref.sync import sync_to_async

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

            # 4. 验证数据包结构（收不到 data 必须 fail，不允许静默通过）
            assert data_msg is not None, '10s 内未收到任何 data 消息（图已 frozen+run）'
            assert data_msg['nodeId'] == 'e2e-output'
            assert data_msg['nodeType'] == 'OUTPUT'
            assert data_msg['sampleRate'] == 250
            assert len(data_msg['channels']) == 4, f'期望 4 通道，实际 {len(data_msg["channels"])}'
            assert len(data_msg['samples']) > 0, 'samples 不能为空'
            # 数值合理性：合成源是方波+噪声，不允许全零或 NaN
            flat = [v for frame in data_msg['samples'] for v in frame]
            assert all(isinstance(v, (int, float)) and v == v for v in flat), '样本含非数值/NaN'
            assert any(abs(v) > 1e-9 for v in flat), '样本全零，合成源未产生有效信号'

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

            # 停止，并核验最终运行时状态
            stop_result = await self._send_cmd(control, {'type': 'stop'})
            assert stop_result['ok'] is True

            from eeg_app.graph_store import get_runtime_state
            state = await sync_to_async(get_runtime_state)()
            assert state['running'] is False, f'stop 后 running 应为 False，实际 {state["running"]}'

            await asyncio.sleep(0.5)  # 让 stream_data 循环退出

            # 连接 ws/eeg/，订阅后不应收到 data（图已停止）
            eeg = WebsocketCommunicator(application, '/ws/eeg/')
            connected, _ = await eeg.connect()
            assert connected
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
            assert got_data is False, 'stop 后仍收到 data 消息'

            try:
                await eeg.disconnect()
            except (asyncio.CancelledError, Exception):
                pass

            await self._send_cmd(control, {'type': 'freeze', 'frozen': False})
        finally:
            await control.disconnect()


@pytest.mark.django_db(transaction=True)
class TestRecordingE2E(TransactionTestCase):
    """录制流程端到端：record start → run → stop → 验证 CSV 产物。"""

    GRAPH_WITH_SAVE = {
        'nodes': [
            {
                'id': 'e2e-rec-source',
                'type': 'SOURCE',
                'name': '录制源',
                'x': 100, 'y': 100,
                'params': {'sampleRate': 250, 'channels': 4},
            },
            {
                'id': 'e2e-rec-output',
                'type': 'OUTPUT',
                'name': '录制输出',
                'x': 400, 'y': 100,
                'params': {
                    'timeWindow': 5,
                    'saveEnabled': True,
                    'filename': 'e2e_rec_cmd_verify.csv',
                },
            },
        ],
        'edges': [
            {
                'id': 'e2e-rec-edge',
                'source': 'e2e-rec-source',
                'sourcePort': 'out',
                'target': 'e2e-rec-output',
                'targetPort': 'in',
            },
        ],
        'frozen': False,
    }

    async def test_record_command_produces_csv(self):
        """ws/control record 命令端到端：录制产物 CSV 必须存在且内容合法。"""
        import os
        from eeg_app.data_recorder import get_data_dir, is_recording

        csv_path = get_data_dir() / 'e2e_rec_cmd_verify.csv'
        if csv_path.exists():
            os.remove(csv_path)

        control = WebsocketCommunicator(application, '/ws/control/')
        connected, _ = await control.connect()
        assert connected
        await control.receive_json_from(timeout=5)  # 初始 state

        eeg = None
        try:
            async def send_cmd(payload):
                await control.send_json_to(payload)
                for _ in range(10):
                    msg = await control.receive_json_from(timeout=5)
                    if msg.get('type') == 'cmd_result':
                        return msg
                raise AssertionError('No cmd_result')

            await send_cmd({'type': 'sync_graph', 'graph': self.GRAPH_WITH_SAVE})
            await send_cmd({'type': 'freeze', 'frozen': True})

            # record start：OUTPUT 节点 saveEnabled=true，应返回节点列表
            rec_start = await send_cmd({'type': 'record', 'action': 'start'})
            assert rec_start['ok'] is True
            assert rec_start.get('action') == 'start'
            assert 'e2e-rec-output' in rec_start.get('nodes', []), (
                f'record start 应包含 e2e-rec-output，实际 {rec_start.get("nodes")}'
            )
            assert await sync_to_async(is_recording)('e2e-rec-output') is True

            run_result = await send_cmd({'type': 'run', 'mode': 'live'})
            assert run_result['ok'] is True

            # 连 ws/eeg/ 驱动 stream_data → _save_nodes 同步 → worker write_sample
            eeg = WebsocketCommunicator(application, '/ws/eeg/')
            connected, _ = await eeg.connect()
            assert connected
            await eeg.send_json_to({'type': 'subscribe', 'nodeIds': ['e2e-rec-output']})

            # 等待收到首帧 data（确认 worker 在写样本），再录制 ~2 秒
            got_data = False
            deadline = time.time() + 10
            while time.time() < deadline:
                try:
                    msg = await asyncio.wait_for(eeg.receive_json_from(), timeout=2)
                    if msg.get('type') == 'data':
                        got_data = True
                        break
                except asyncio.TimeoutError:
                    continue
            assert got_data, '运行后未收到 data，录制链路未驱动'
            await asyncio.sleep(2.0)

            # record stop：录制器应停止
            rec_stop = await send_cmd({'type': 'record', 'action': 'stop'})
            assert rec_stop['ok'] is True
            assert rec_stop.get('action') == 'stop'
            assert await sync_to_async(is_recording)('e2e-rec-output') is False

            await send_cmd({'type': 'stop'})
            await send_cmd({'type': 'freeze', 'frozen': False})

            # ── 产物验收 ──
            assert csv_path.exists(), f'录制 CSV 未生成: {csv_path}'
            assert csv_path.stat().st_size > 0, '录制 CSV 为空文件'

            def _read_csv():
                with open(csv_path, newline='', encoding='utf-8') as f:
                    return list(csv.reader(f))

            rows = await sync_to_async(_read_csv)()
            header, data_rows = rows[0], rows[1:]
            assert header == ['timestamp', 'sample_idx', 'ch1', 'ch2', 'ch3', 'ch4'], (
                f'CSV 表头不符: {header}'
            )
            assert len(data_rows) > 50, f'2s 录制应 >50 行，实际 {len(data_rows)}'

            # 列数一致 + 无 NaN/空值
            for row in data_rows:
                assert len(row) == 6, f'行列数异常: {row}'
                for v in row[2:]:
                    fv = float(v)
                    assert fv == fv, f'样本含 NaN: {row}'

            # sample_idx 从 0 连续递增
            idxs = [int(r[1]) for r in data_rows]
            assert idxs[0] == 0
            assert idxs == list(range(len(idxs))), 'sample_idx 不连续'

            # 时间戳单调不减
            ts = [int(r[0]) for r in data_rows]
            assert all(b >= a for a, b in zip(ts, ts[1:])), '时间戳非单调'
        finally:
            if eeg is not None:
                try:
                    await eeg.disconnect()
                except (asyncio.CancelledError, Exception):
                    pass
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
