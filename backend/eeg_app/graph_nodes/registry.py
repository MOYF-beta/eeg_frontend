from __future__ import annotations

from typing import Dict, Iterable, Type

from .base import GraphNode


_NODE_REGISTRY: Dict[str, Type[GraphNode]] = {}


def register_node(node_cls: Type[GraphNode]) -> None:
    node_type = str(getattr(node_cls, 'node_type', '') or '').strip().upper()
    if not node_type:
        raise ValueError('node_type is required')
    _NODE_REGISTRY[node_type] = node_cls


def get_node_class(node_type: str):
    return _NODE_REGISTRY.get(str(node_type or '').upper())


def get_registered_node_types() -> Iterable[str]:
    return tuple(sorted(_NODE_REGISTRY.keys()))
