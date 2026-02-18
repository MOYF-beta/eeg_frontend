from __future__ import annotations

import json
import os
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
    'SPLIT',
    'MERGE',
    'OSC',
    'SPECTRUM',
    'SAVE',
}

_NO_INPUT_NODE_TYPES = {'SOURCE', 'REPLAY'}
_NO_OUTPUT_NODE_TYPES = {'OSC', 'SPECTRUM', 'SAVE'}


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

    if node_type in {'SUM', 'MERGE'}:
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

    return ['in']


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

    return ['out']

# 默认空图
_DEFAULT_GRAPH: GraphPayload = {
    'nodes': [],
    'edges': [],
    'frozen': False,
}

# 内存中的图数据
_GRAPH: GraphPayload = {
    'nodes': [],
    'edges': [],
    'frozen': False,
}

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
        source_mode = str(params.get('sourceMode') or 'live').lower()
        return source_mode != 'replay'
    return False


def _has_offline_input_node(node: Dict) -> bool:
    node_type = str(node.get('type') or '').upper()
    params = node.get('params') or {}
    if node_type == 'REPLAY':
        return True
    if node_type == 'SOURCE':
        source_mode = str(params.get('sourceMode') or 'live').lower()
        return source_mode == 'replay'
    return False


def _load_from_file() -> GraphPayload:
    """从JSON文件加载图数据"""
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 验证数据结构
                if 'nodes' in data and 'edges' in data and 'frozen' in data:
                    print(f'[GraphStore] Loaded graph from {DATA_FILE}: {len(data["nodes"])} nodes, {len(data["edges"])} edges')
                    return {
                        'nodes': data.get('nodes', []),
                        'edges': data.get('edges', []),
                        'frozen': data.get('frozen', False),
                    }
    except Exception as e:
        print(f'[GraphStore] Failed to load from file: {e}')
    return _DEFAULT_GRAPH.copy()


def _save_to_file(payload: GraphPayload) -> None:
    """保存图数据到JSON文件"""
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f'[GraphStore] Saved graph to {DATA_FILE}')
    except Exception as e:
        print(f'[GraphStore] Failed to save to file: {e}')


def get_graph() -> GraphPayload:
    """获取当前图数据"""
    return _GRAPH


def set_graph(payload: GraphPayload) -> None:
    """设置图数据并保存到文件"""
    # 检查计算图是否正在运行
    if _RUNTIME_STATE['running']:
        raise RuntimeError('Cannot modify graph while it is running')
    
    _GRAPH['nodes'] = payload.get('nodes', [])
    _GRAPH['edges'] = payload.get('edges', [])
    _GRAPH['frozen'] = payload.get('frozen', False)
    _save_to_file(_GRAPH)


def set_frozen(value: bool) -> None:
    """设置冻结状态并保存"""
    # 检查计算图是否正在运行
    if _RUNTIME_STATE['running']:
        raise RuntimeError('Cannot freeze/unfreeze graph while it is running')
    
    _GRAPH['frozen'] = value
    _save_to_file(_GRAPH)


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


def run_graph(mode: str = 'live') -> Dict:
    """运行计算图"""
    global _RUNTIME_STATE

    normalized_mode = str(mode or 'live').lower()
    if normalized_mode not in {'live', 'offline'}:
        normalized_mode = 'live'

    nodes = _GRAPH.get('nodes', []) or []
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
    return {
        'status': 'running',
        'mode': normalized_mode,
        'startedAt': _RUNTIME_STATE['startedAt'],
        'nodeCount': len(_GRAPH['nodes']),
        'edgeCount': len(_GRAPH['edges']),
    }


def stop_graph() -> Dict:
    """停止计算图"""
    global _RUNTIME_STATE
    _RUNTIME_STATE['running'] = False
    _RUNTIME_STATE['stoppedAt'] = time.time()
    return {
        'status': 'stopped',
        'mode': _RUNTIME_STATE['mode'],
        'startedAt': _RUNTIME_STATE['startedAt'],
        'stoppedAt': _RUNTIME_STATE['stoppedAt'],
    }


def set_runtime_metrics(
    processing_delay_ms: float | int | None = None,
    progress: float | None = None,
    non_realtime: bool | None = None,
    warning: str | None = None,
) -> None:
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
    """获取运行时状态"""
    return {
        'running': _RUNTIME_STATE['running'],
        'mode': _RUNTIME_STATE['mode'],
        'startedAt': _RUNTIME_STATE['startedAt'],
        'stoppedAt': _RUNTIME_STATE['stoppedAt'],
        'progress': _RUNTIME_STATE['progress'],
        'processingDelayMs': _RUNTIME_STATE['processingDelayMs'],
        'nonRealtime': _RUNTIME_STATE['nonRealtime'],
        'warning': _RUNTIME_STATE['warning'],
    }


# 初始化时从文件加载数据
_GRAPH = _load_from_file()
