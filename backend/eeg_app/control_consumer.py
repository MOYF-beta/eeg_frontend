"""统一控制 WebSocket Consumer (ws/control/)。

前端通过此通道发送所有控制命令（run/stop/freeze/sync_graph/save 等），
后端执行后通过同一通道推送 state_push（含运行时状态、设备状态、性能指标、图拓扑），
消除前端轮询。

ws/eeg/ 仅保留纯数据流（subscribe/unsubscribe + data payload）。
"""

from __future__ import annotations

import logging
logger = logging.getLogger(__name__)

import asyncio
import json
import time
from typing import Any, Dict, Optional, Set

from channels.generic.websocket import AsyncWebsocketConsumer

CONTROL_GROUP = 'control'


class ControlConsumer(AsyncWebsocketConsumer):
    """统一控制通道 — 命令收发 + 状态推送。"""

    async def connect(self):
        await self.channel_layer.group_add(CONTROL_GROUP, self.channel_name)
        await self.accept()
        self._heartbeat_task: Optional[asyncio.Task] = None
        # 连接后立即推送当前状态
        await self._push_state(reason='connected')
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.debug('[ControlWS] Client connected')

    async def disconnect(self, code):
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None
        try:
            await self.channel_layer.group_discard(CONTROL_GROUP, self.channel_name)
        except Exception:
            pass
        logger.debug('[ControlWS] Client disconnected: %s', code)

    # ------------------------------------------------------------------ #
    #  接收前端命令
    # ------------------------------------------------------------------ #
    async def receive(self, text_data):
        try:
            msg = json.loads(text_data)
            msg_type = msg.get('type')
            handler = self._COMMAND_MAP.get(msg_type)
            if handler:
                result = await handler(self, msg)
                # 先发命令结果给当前客户端
                if result:
                    await self.send(text_data=json.dumps(result))
                # 对影响全局状态的命令，广播给所有客户端
                if msg_type in ('run', 'stop', 'freeze'):
                    await self._broadcast_graph_change(reason=msg_type)
                elif msg.get('pushState', True):
                    await self._push_state(reason=msg_type)
            elif msg_type == 'ping':
                await self.send(text_data=json.dumps({'type': 'pong'}))
            elif msg_type == 'get_state':
                await self._push_state(reason='query')
            else:
                await self.send(text_data=json.dumps({
                    'type': 'error', 'error': f'Unknown command: {msg_type}',
                }))
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({'type': 'error', 'error': 'Invalid JSON'}))
        except Exception as exc:
            logger.warning('[ControlWS] Command error: %s', exc)
            await self.send(text_data=json.dumps({'type': 'error', 'error': str(exc)}))

    # ------------------------------------------------------------------ #
    #  命令处理器
    # ------------------------------------------------------------------ #
    async def cmd_run(self, msg) -> Dict:
        from .graph_store import run_graph
        mode = msg.get('mode', 'live')
        result = run_graph(mode=mode)
        if result.get('status') == 'error':
            return {'type': 'cmd_result', 'command': 'run', 'ok': False, 'error': result['error']}
        return {'type': 'cmd_result', 'command': 'run', 'ok': True, 'result': result}

    async def cmd_stop(self, msg) -> Dict:
        from .graph_store import stop_graph
        result = stop_graph()
        return {'type': 'cmd_result', 'command': 'stop', 'ok': True, 'result': result}

    async def cmd_freeze(self, msg) -> Dict:
        from .graph_store import set_frozen
        try:
            set_frozen(bool(msg.get('frozen', False)))
            return {'type': 'cmd_result', 'command': 'freeze', 'ok': True}
        except RuntimeError as exc:
            return {'type': 'cmd_result', 'command': 'freeze', 'ok': False, 'error': str(exc)}

    async def cmd_sync_graph(self, msg) -> Dict:
        """实时图同步 + 自动持久化（替代 HTTP POST /api/graph/sync/ + /api/graph/save/）。"""
        from .graph_store import apply_graph_sync
        payload = msg.get('graph') or {}
        base_rev = msg.get('baseRevision')
        result = apply_graph_sync(payload, base_revision=base_rev, persist=True)
        if result.get('conflict'):
            # 冲突时不广播，仅向当前客户端返回冲突详情 + 权威图
            return {'type': 'cmd_result', 'command': 'sync_graph', **result}
        # 成功时广播图变更给所有控制客户端
        await self._broadcast_graph_change(reason='synced')
        return {'type': 'cmd_result', 'command': 'sync_graph', **result}

    async def cmd_save_graph(self, msg) -> Dict:
        from .graph_store import persist_graph
        result = persist_graph()
        await self._broadcast_graph_change(reason='persisted')
        return {'type': 'cmd_result', 'command': 'save_graph', 'ok': True, **result}

    async def cmd_connect_device(self, msg) -> Dict:
        from .drivers.manager import get_device_manager
        manager = get_device_manager()
        device_id = msg.get('device_id') or msg.get('port', '')
        config = msg.get('config')
        ok = manager.connect(str(device_id), config)
        return {'type': 'cmd_result', 'command': 'connect_device', 'ok': ok}

    async def cmd_disconnect_device(self, msg) -> Dict:
        from .drivers.manager import get_device_manager
        manager = get_device_manager()
        device_id = msg.get('device_id') or msg.get('port', '')
        ok = manager.disconnect(str(device_id))
        return {'type': 'cmd_result', 'command': 'disconnect_device', 'ok': ok}

    async def cmd_start_streaming(self, msg) -> Dict:
        from .drivers.manager import get_device_manager
        manager = get_device_manager()
        device_id = msg.get('device_id') or msg.get('port', '')
        ok = manager.start_streaming(str(device_id))
        return {'type': 'cmd_result', 'command': 'start_streaming', 'ok': ok}

    async def cmd_stop_streaming(self, msg) -> Dict:
        from .drivers.manager import get_device_manager
        manager = get_device_manager()
        device_id = msg.get('device_id') or msg.get('port', '')
        ok = manager.stop_streaming(str(device_id))
        return {'type': 'cmd_result', 'command': 'stop_streaming', 'ok': ok}

    async def cmd_scan_ports(self, msg) -> Dict:
        from .drivers.manager import get_device_manager
        manager = get_device_manager()
        devices = manager.discover_all()
        ports = [
            {
                'port': m.device_id,
                'description': m.extra.get('description', ''),
                'driver_type': m.driver_type,
                'channel_count': m.channel_count,
                'sample_rate': m.sample_rate,
                'is_available': m.is_available,
            }
            for m in devices
        ]
        return {'type': 'cmd_result', 'command': 'scan_ports', 'ok': True, 'ports': ports}

    async def cmd_record(self, msg) -> Dict:
        from .data_recorder import stop_recording as stop_rec
        from .data_recorder import start_recording as start_rec
        from .graph_store import get_output_nodes_for_recording
        action = msg.get('action', 'start')
        output_nodes = get_output_nodes_for_recording()
        save_node_ids = [n.get('id') for n in output_nodes if n.get('id')]
        if action == 'stop':
            for nid in save_node_ids:
                try:
                    stop_rec(nid)
                except Exception:
                    pass
            return {'type': 'cmd_result', 'command': 'record', 'ok': True, 'action': 'stop'}
        else:
            for node in output_nodes:
                nid = node.get('id')
                if not nid:
                    continue
                params = node.get('params') or {}
                filename = params.get('filename') or params.get('filePath')
                fmt = str(params.get('format', 'CSV')).upper()
                start_rec(node_id=nid, filename=filename, format=fmt)
            return {'type': 'cmd_result', 'command': 'record', 'ok': True, 'action': 'start',
                    'nodes': save_node_ids}

    # ------------------------------------------------------------------ #
    #  状态推送
    # ------------------------------------------------------------------ #
    async def _push_state(self, reason: str = 'update'):
        """向当前客户端推送完整状态快照。"""
        from .graph_store import get_graph, get_runtime_state, get_graph_revision, get_persisted_revision
        from .drivers.manager import get_device_manager

        graph = get_graph()
        runtime = get_runtime_state()
        devices = []
        try:
            manager = get_device_manager()
            for meta in manager.discover_all():
                devices.append({
                    'device_id': meta.device_id,
                    'driver_type': meta.driver_type,
                    'name': meta.name,
                    'status': manager.get_status(meta.device_id).value,
                    'channel_count': meta.channel_count,
                    'sample_rate': meta.sample_rate,
                })
        except Exception:
            pass

        payload = {
            'type': 'state',
            'reason': reason,
            'timestamp': int(time.time() * 1000),
            'graph': {
                **graph,
                'revision': get_graph_revision(),
                'persistedRevision': get_persisted_revision(),
            },
            # 在 runtime 中冗余 frozen 字段，便于前端 graphRuntimeStore 直接读取
            'runtime': {**runtime, 'frozen': bool(graph.get('frozen', False))},
            'devices': devices,
        }
        try:
            await self.send(text_data=json.dumps(payload))
        except Exception as exc:
            logger.debug('[ControlWS] Push state failed: %s', exc)

    # 广播节流：100ms 窗口内合并多次变更
    _broadcast_throttle_ms = 100
    _broadcast_pending_reason: Optional[str] = None
    _broadcast_throttle_task: Optional[asyncio.Task] = None

    async def _broadcast_graph_change(self, reason: str):
        """通过 group_send 广播图变更给所有控制客户端（带节流）。

        高频调用（如拖拽节点时的 sync_graph）会在 100ms 窗口内合并。
        """
        self._broadcast_pending_reason = reason

        if self._broadcast_throttle_task and not self._broadcast_throttle_task.done():
            return  # 已有待处理的节流任务，更新 reason 后等待

        async def _throttled_broadcast():
            try:
                await asyncio.sleep(self._broadcast_throttle_ms / 1000.0)
                reason_to_send = self._broadcast_pending_reason or 'update'
                self._broadcast_pending_reason = None
                await self.channel_layer.group_send(CONTROL_GROUP, {
                    'type': 'control.broadcast',
                    'reason': reason_to_send,
                })
            except asyncio.CancelledError:
                pass

        self._broadcast_throttle_task = asyncio.create_task(_throttled_broadcast())

    # ------------------------------------------------------------------ #
    #  group_send handler — 其他 consumer/视图 触发的广播
    # ------------------------------------------------------------------ #
    async def control_broadcast(self, event):
        """group handler: type='control.broadcast' → 推送状态给此客户端。"""
        await self._push_state(reason=event.get('reason', 'broadcast'))

    # ------------------------------------------------------------------ #
    #  心跳
    # ------------------------------------------------------------------ #
    async def _heartbeat_loop(self):
        """每 30s 推送一次状态（含性能指标），替代前端 HTTP 轮询。"""
        while True:
            await asyncio.sleep(30)
            try:
                await self._push_state(reason='heartbeat')
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    #  命令路由表
    # ------------------------------------------------------------------ #
    _COMMAND_MAP: Dict[str, Any] = {}


# 填充命令映射（类定义后赋值，引用方法）
ControlConsumer._COMMAND_MAP = {
    'run': ControlConsumer.cmd_run,
    'stop': ControlConsumer.cmd_stop,
    'freeze': ControlConsumer.cmd_freeze,
    'sync_graph': ControlConsumer.cmd_sync_graph,
    'save_graph': ControlConsumer.cmd_save_graph,
    'connect_device': ControlConsumer.cmd_connect_device,
    'disconnect_device': ControlConsumer.cmd_disconnect_device,
    'start_streaming': ControlConsumer.cmd_start_streaming,
    'stop_streaming': ControlConsumer.cmd_stop_streaming,
    'scan_ports': ControlConsumer.cmd_scan_ports,
    'record': ControlConsumer.cmd_record,
}
