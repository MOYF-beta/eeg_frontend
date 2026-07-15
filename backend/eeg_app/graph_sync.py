from __future__ import annotations

import time

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .graph_store import get_graph, get_graph_revision, get_persisted_revision, bump_control_revision


GRAPH_SYNC_GROUP = 'graph_sync'
CONTROL_GROUP = 'control'


def broadcast_graph_state(reason: str = 'updated') -> None:
    """向所有图同步客户端和控制客户端广播当前后端计算图。"""
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    # 控制修订号递增，通知数据 consumer 重新读取控制状态
    bump_control_revision()

    payload = {
        'type': 'graph.state',
        'graph': {
            **get_graph(),
            'revision': get_graph_revision(),
            'persistedRevision': get_persisted_revision(),
        },
        'reason': reason,
        'timestamp': int(time.time() * 1000),
    }
    async_to_sync(channel_layer.group_send)(GRAPH_SYNC_GROUP, payload)

    # 同时广播到控制组，触发 ControlConsumer 推送完整状态
    async_to_sync(channel_layer.group_send)(CONTROL_GROUP, {
        'type': 'control.broadcast',
        'reason': reason,
    })
