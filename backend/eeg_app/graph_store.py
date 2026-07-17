from __future__ import annotations

import logging
logger = logging.getLogger(__name__)

import copy
import json
import os
import threading
import time
from typing import Dict, List, TypedDict

from .graph_nodes import get_registered_node_types

# 数据文件路径
DATA_FILE = os.path.join(os.path.dirname(__file__), 'graph_data.json')


class GraphNode(TypedDict):
    id: str
    type: str
    name: str
    x: float
    y: float
    params: Dict
    deviceId: str | None  # SOURCE/REPLAY节点绑定的设备ID


class GraphEdge(TypedDict):
    id: str
    source: str
    target: str
    sourcePort: str
    targetPort: str


class GraphPayload(TypedDict):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    frozen: bool


BUILTIN_NODE_TYPES = {
    'SOURCE',
    'REPLAY',
    'FILTER',
    'DOWNSAMPLE',
    'UPSAMPLE',
    'SUM',
    'AVERAGE',
    'SPLIT',
    'MERGE',
    'OUTPUT',
}

_NO_INPUT_NODE_TYPES = {'SOURCE', 'REPLAY'}
_NO_OUTPUT_NODE_TYPES = {'OUTPUT'}


def _safe_positive_int(raw: object, default: int = 1) -> int:
    try:
        value = int(raw)
    except Exception:
        value = default
    return max(1, value)


def _node_input_ports(node: Dict) -> List[str]:
    node_type = node.get('type')
    params = node.get('params') or {}

    if node_type in _NO_INPUT_NODE_TYPES:
        return []

    if node_type in {'SUM', 'MERGE', 'AVERAGE'}:
        inputs = params.get('inputs')
        count = len(inputs) if isinstance(inputs, list) else 1
        count = max(1, count)
        return [f'in-{i + 1}' for i in range(count)]

    port_mode = str(params.get('portMode') or 'fixed').lower()
    if port_mode == 'adaptive':
        return ['in']

    count = _safe_positive_int(params.get('inputCount'), 1)
    if count == 1:
        return ['in']
    return [f'in-{i + 1}' for i in range(count)]


def _node_output_ports(node: Dict) -> List[str]:
    node_type = node.get('type')
    params = node.get('params') or {}

    if node_type in _NO_OUTPUT_NODE_TYPES:
        return []

    if node_type == 'SPLIT':
        outputs = params.get('outputs')
        count = len(outputs) if isinstance(outputs, list) else 1
        count = max(1, count)
        return [f'out-{i + 1}' for i in range(count)]

    port_mode = str(params.get('portMode') or 'fixed').lower()
    if port_mode == 'adaptive':
        return ['out']

    count = _safe_positive_int(params.get('outputCount'), 1)
    if count == 1:
        return ['out']
    return [f'out-{i + 1}' for i in range(count)]

# 默认空图
_DEFAULT_GRAPH: GraphPayload = {
    'nodes': [],
    'edges': [],
    'frozen': False,
}

# 线程锁 — 保护所有全局可变状态
_graph_lock = threading.RLock()

# 内存中的图数据
_GRAPH: GraphPayload = {
    'nodes': [],
    'edges': [],
    'frozen': False,
}

_GRAPH_REVISION = 0
_PERSISTED_REVISION = 0

# 控制修订号：每次 frozen/running/graph 变更时递增。
# 数据 consumer 通过比较此值判断是否需要重新读取控制状态，
# 避免每 tick 全量重读 graph + 重算签名。
_CONTROL_REVISION = 0

# 运行时状态
_RUNTIME_STATE = {
    'running': False,
    'mode': 'live',
    'startedAt': None,
    'stoppedAt': None,
    'progress': None,
    'processingDelayMs': 0,
    'nonRealtime': False,
    'warning': None,
}


def _is_live_input_node(node: Dict) -> bool:
    node_type = str(node.get('type') or '').upper()
    params = node.get('params') or {}
    if node_type == 'REPLAY':
        return False
    if node_type == 'SOURCE':
        return True  # SOURCE 始终为实时采集
    return False


def _has_offline_input_node(node: Dict) -> bool:
    node_type = str(node.get('type') or '').upper()
    if node_type == 'REPLAY':
        return True
    return False


def _load_from_file() -> GraphPayload:
    """从JSON文件加载图数据"""
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 验证数据结构
                if 'nodes' in data and 'edges' in data and 'frozen' in data:
                    logger.debug(f'[GraphStore] Loaded graph from {DATA_FILE}: {len(data["nodes"])} nodes, {len(data["edges"])} edges')
                    
                    # 确保每个节点都有deviceId字段
                    nodes = data.get('nodes', [])
                    for node in nodes:
                        if 'deviceId' not in node:
                            node['deviceId'] = None
                    
                    return {
                        'nodes': nodes,
                        'edges': data.get('edges', []),
                        'frozen': data.get('frozen', False),
                    }
    except Exception as e:
        logger.debug(f'[GraphStore] Failed to load from file: {e}')
    return _DEFAULT_GRAPH.copy()


def _save_to_file(payload: GraphPayload) -> None:
    """保存图数据到JSON文件"""
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        logger.debug(f'[GraphStore] Saved graph to {DATA_FILE}')
    except Exception as e:
        logger.debug(f'[GraphStore] Failed to save to file: {e}')


def get_graph() -> GraphPayload:
    """获取当前图数据的深拷贝（线程安全）"""
    with _graph_lock:
        return copy.deepcopy(_GRAPH)


def set_graph(payload: GraphPayload, persist: bool = False) -> None:
    """设置图数据，persist=True 时同时落盘。"""
    global _GRAPH_REVISION, _PERSISTED_REVISION
    with _graph_lock:
        # 检查计算图是否正在运行
        if _RUNTIME_STATE['running']:
            raise RuntimeError('Cannot modify graph while it is running')
        
        _GRAPH['nodes'] = list(payload.get('nodes', []))
        _GRAPH['edges'] = list(payload.get('edges', []))
        _GRAPH['frozen'] = bool(payload.get('frozen', False))
        _GRAPH_REVISION += 1
        bump_control_revision()
    if persist:
        _save_to_file(get_graph())
        with _graph_lock:
            _PERSISTED_REVISION = _GRAPH_REVISION


def apply_graph_sync(payload: GraphPayload, base_revision: int | None = None, persist: bool = False) -> Dict:
    """应用前端实时同步，支持基于 revision 的冲突检测。

    persist=True 时同时落盘（自动保存模式）。
    """
    with _graph_lock:
        current_revision = int(_GRAPH_REVISION)
        if base_revision is not None and int(base_revision) != current_revision:
            return {
                'ok': False,
                'conflict': True,
                'revision': current_revision,
                'persistedRevision': int(_PERSISTED_REVISION),
                'graph': dict(_GRAPH),
                'error': 'revision conflict',
            }

    set_graph(payload, persist=persist)
    with _graph_lock:
        return {
            'ok': True,
            'conflict': False,
            'revision': int(_GRAPH_REVISION),
            'persistedRevision': int(_PERSISTED_REVISION),
        }


def persist_graph() -> Dict:
    """将当前内存图持久化到文件。"""
    global _PERSISTED_REVISION
    with _graph_lock:
        graph_copy = dict(_GRAPH)
        rev = int(_GRAPH_REVISION)
    _save_to_file(graph_copy)
    with _graph_lock:
        _PERSISTED_REVISION = rev
        persisted_rev = int(_PERSISTED_REVISION)
    return {
        'revision': rev,
        'persistedRevision': persisted_rev,
    }


def get_graph_revision() -> int:
    with _graph_lock:
        return int(_GRAPH_REVISION)


def get_persisted_revision() -> int:
    with _graph_lock:
        return int(_PERSISTED_REVISION)


def bump_control_revision() -> int:
    """递增控制修订号，通知数据 consumer 控制状态已变更。"""
    global _CONTROL_REVISION
    with _graph_lock:
        _CONTROL_REVISION += 1
        return int(_CONTROL_REVISION)


def get_control_revision() -> int:
    with _graph_lock:
        return int(_CONTROL_REVISION)


def set_frozen(value: bool) -> None:
    """设置冻结状态（不落盘，持久化由 sync_graph 负责）。"""
    with _graph_lock:
        # 检查计算图是否正在运行
        if _RUNTIME_STATE['running']:
            raise RuntimeError('Cannot freeze/unfreeze graph while it is running')
        _GRAPH['frozen'] = value
        bump_control_revision()


def validate_graph(payload: GraphPayload) -> List[str]:
    """验证图数据"""
    errors: List[str] = []
    valid_node_types = set(BUILTIN_NODE_TYPES) | set(get_registered_node_types())
    node_ids = set()
    nodes_by_id = {}
    for node in payload.get('nodes', []):
        node_id = node.get('id')
        node_type = node.get('type')
        if not node_id:
            errors.append('node.id is required')
        if node_type not in valid_node_types:
            errors.append(f"invalid node type: {node_type}")
        if node_id in node_ids:
            errors.append(f"duplicate node id: {node_id}")
        node_ids.add(node_id)
        nodes_by_id[node_id] = node

    for edge in payload.get('edges', []):
        source = edge.get('source')
        target = edge.get('target')
        source_port = edge.get('sourcePort')
        target_port = edge.get('targetPort')
        if not source or not target:
            errors.append('edge.source and edge.target are required')
            continue
        if source not in node_ids or target not in node_ids:
            errors.append('edge source/target must exist in nodes')
            continue

        source_node = nodes_by_id.get(source, {})
        target_node = nodes_by_id.get(target, {})

        valid_source_ports = _node_output_ports(source_node)
        valid_target_ports = _node_input_ports(target_node)

        if valid_source_ports and source_port and source_port not in valid_source_ports:
            errors.append(f"invalid source port: {source}.{source_port}")
        if valid_target_ports and target_port and target_port not in valid_target_ports:
            errors.append(f"invalid target port: {target}.{target_port}")

        if valid_source_ports and not source_port:
            errors.append(f"edge.sourcePort is required for node {source}")
        if valid_target_ports and not target_port:
            errors.append(f"edge.targetPort is required for node {target}")

        if not valid_source_ports:
            errors.append(f"node {source} cannot be edge source")
        if not valid_target_ports:
            errors.append(f"node {target} cannot be edge target")

    return errors


def get_output_nodes_for_recording(graph: GraphPayload | None = None) -> List[Dict]:
    """获取计算图中需要录制的 OUTPUT 节点列表。
    
    用于统一 control_consumer.cmd_record 和 views.graph_record 中的录制逻辑。
    """
    if graph is None:
        graph = get_graph()
    nodes = graph.get('nodes', []) or []
    result = []
    for node in nodes:
        nt = str(node.get('type') or '').upper()
        params = node.get('params') or {}
        if nt == 'OUTPUT' and bool(params.get('saveEnabled', False)):
            result.append(node)
    return result


def run_graph(mode: str = 'live') -> Dict:
    """运行计算图"""
    global _RUNTIME_STATE

    normalized_mode = str(mode or 'live').lower()
    if normalized_mode not in {'live', 'offline'}:
        normalized_mode = 'live'

    with _graph_lock:
        nodes = list(_GRAPH.get('nodes', []) or [])
        if normalized_mode == 'offline':
            has_live = any(_is_live_input_node(node) for node in nodes)
            has_offline = any(_has_offline_input_node(node) for node in nodes)
            if has_live:
                return {
                    'status': 'error',
                    'error': 'offline mode does not allow realtime source nodes',
                }
            if not has_offline:
                return {
                    'status': 'error',
                    'error': 'offline mode requires at least one replay source',
                }

        _RUNTIME_STATE['running'] = True
        _RUNTIME_STATE['mode'] = normalized_mode
        _RUNTIME_STATE['startedAt'] = time.time()
        _RUNTIME_STATE['stoppedAt'] = None
        _RUNTIME_STATE['progress'] = 0 if normalized_mode == 'offline' else None
        _RUNTIME_STATE['processingDelayMs'] = 0
        _RUNTIME_STATE['nonRealtime'] = False
        _RUNTIME_STATE['warning'] = None
        bump_control_revision()
        started_at = _RUNTIME_STATE['startedAt']
        node_count = len(_GRAPH['nodes'])
        edge_count = len(_GRAPH['edges'])

    return {
        'status': 'running',
        'mode': normalized_mode,
        'startedAt': started_at,
        'nodeCount': node_count,
        'edgeCount': edge_count,
    }


def stop_graph() -> Dict:
    """停止计算图"""
    global _RUNTIME_STATE
    with _graph_lock:
        _RUNTIME_STATE['running'] = False
        _RUNTIME_STATE['stoppedAt'] = time.time()
        bump_control_revision()
        mode = _RUNTIME_STATE['mode']
        started_at = _RUNTIME_STATE['startedAt']
        stopped_at = _RUNTIME_STATE['stoppedAt']

    return {
        'status': 'stopped',
        'mode': mode,
        'startedAt': started_at,
        'stoppedAt': stopped_at,
    }


def set_runtime_metrics(
    processing_delay_ms: float | int | None = None,
    progress: float | None = None,
    non_realtime: bool | None = None,
    warning: str | None = None,
) -> None:
    with _graph_lock:
        if processing_delay_ms is not None:
            try:
                _RUNTIME_STATE['processingDelayMs'] = max(0, int(float(processing_delay_ms)))
            except Exception:
                pass
        if progress is not None:
            try:
                _RUNTIME_STATE['progress'] = max(0.0, min(100.0, float(progress)))
            except Exception:
                pass
        if non_realtime is not None:
            _RUNTIME_STATE['nonRealtime'] = bool(non_realtime)
        if warning is not None:
            _RUNTIME_STATE['warning'] = warning


def get_runtime_state() -> Dict:
    """获取运行时状态（返回拷贝，线程安全）"""
    with _graph_lock:
        return {
            'running': _RUNTIME_STATE['running'],
            'mode': _RUNTIME_STATE['mode'],
            'startedAt': _RUNTIME_STATE['startedAt'],
            'stoppedAt': _RUNTIME_STATE['stoppedAt'],
            'progress': _RUNTIME_STATE['progress'],
            'processingDelayMs': _RUNTIME_STATE['processingDelayMs'],
            'nonRealtime': _RUNTIME_STATE['nonRealtime'],
            'warning': _RUNTIME_STATE['warning'],
            'frozen': _GRAPH['frozen'],
        }


# 初始化时从文件加载数据（线程安全）
_init_graph = _load_from_file()
with _graph_lock:
    _GRAPH['nodes'] = _init_graph.get('nodes', [])
    _GRAPH['edges'] = _init_graph.get('edges', [])
    _GRAPH['frozen'] = _init_graph.get('frozen', False)
_GRAPH_REVISION = 1
_PERSISTED_REVISION = 1
