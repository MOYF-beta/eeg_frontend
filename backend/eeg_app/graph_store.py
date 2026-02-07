from __future__ import annotations

import time
from typing import Dict, List, TypedDict


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


_GRAPH: GraphPayload = {
    'nodes': [],
    'edges': [],
    'frozen': False,
}


def get_graph() -> GraphPayload:
    return _GRAPH


def set_graph(payload: GraphPayload) -> None:
    _GRAPH['nodes'] = payload.get('nodes', [])
    _GRAPH['edges'] = payload.get('edges', [])
    _GRAPH['frozen'] = payload.get('frozen', False)


def set_frozen(value: bool) -> None:
    _GRAPH['frozen'] = value


def validate_graph(payload: GraphPayload) -> List[str]:
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
    return {
        'status': 'running',
        'startedAt': time.time(),
        'nodeCount': len(_GRAPH['nodes']),
        'edgeCount': len(_GRAPH['edges']),
    }