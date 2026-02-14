from __future__ import annotations

import json
import os
import time
from typing import Dict, List, TypedDict

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


class GraphPayload(TypedDict):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    frozen: bool


NODE_TYPES = {
    'SOURCE',
    'REPLAY',
    'FILTER',
    'SUM',
    'SPLIT',
    'MERGE',
    'OSC',
    'SPECTRUM',
    'SAVE',
}

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
    'startedAt': None,
    'stoppedAt': None,
}


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
    _GRAPH['nodes'] = payload.get('nodes', [])
    _GRAPH['edges'] = payload.get('edges', [])
    _GRAPH['frozen'] = payload.get('frozen', False)
    _save_to_file(_GRAPH)


def set_frozen(value: bool) -> None:
    """设置冻结状态并保存"""
    _GRAPH['frozen'] = value
    _save_to_file(_GRAPH)


def validate_graph(payload: GraphPayload) -> List[str]:
    """验证图数据"""
    errors: List[str] = []
    node_ids = set()
    for node in payload.get('nodes', []):
        node_id = node.get('id')
        node_type = node.get('type')
        if not node_id:
            errors.append('node.id is required')
        if node_type not in NODE_TYPES:
            errors.append(f"invalid node type: {node_type}")
        if node_id in node_ids:
            errors.append(f"duplicate node id: {node_id}")
        node_ids.add(node_id)

    for edge in payload.get('edges', []):
        source = edge.get('source')
        target = edge.get('target')
        if not source or not target:
            errors.append('edge.source and edge.target are required')
            continue
        if source not in node_ids or target not in node_ids:
            errors.append('edge source/target must exist in nodes')

    return errors


def run_graph() -> Dict:
    """运行计算图"""
    global _RUNTIME_STATE
    _RUNTIME_STATE['running'] = True
    _RUNTIME_STATE['startedAt'] = time.time()
    _RUNTIME_STATE['stoppedAt'] = None
    return {
        'status': 'running',
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
        'startedAt': _RUNTIME_STATE['startedAt'],
        'stoppedAt': _RUNTIME_STATE['stoppedAt'],
    }


def get_runtime_state() -> Dict:
    """获取运行时状态"""
    return {
        'running': _RUNTIME_STATE['running'],
        'startedAt': _RUNTIME_STATE['startedAt'],
        'stoppedAt': _RUNTIME_STATE['stoppedAt'],
    }


# 初始化时从文件加载数据
_GRAPH = _load_from_file()
