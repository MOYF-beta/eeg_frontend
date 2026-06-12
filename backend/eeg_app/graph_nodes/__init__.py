from __future__ import annotations

from .average_node import AverageNode
from .filter_node import FilterNode
from .downsample_node import DownsampleNode
from .loader import DEFAULT_CUSTOM_NODE_PATH, load_custom_nodes
from .merge_node import MergeNode
from .osc_node import OscNode
from .passthrough_node import PassthroughNode
from .registry import get_node_class, get_registered_node_types, register_node
from .replay_node import ReplayNode
from .save_node import SaveNode
from .source_node import SourceNode
from .spectrum_node import SpectrumNode
from .split_node import SplitNode
from .sum_node import SumNode
from .upsample_node import UpsampleNode


def _register_builtin_nodes() -> None:
    for cls in (
        SourceNode,
        ReplayNode,
        FilterNode,
        DownsampleNode,
        UpsampleNode,
        SumNode,
        AverageNode,
        SplitNode,
        MergeNode,
        OscNode,
        SpectrumNode,
        SaveNode,
        PassthroughNode,
    ):
        register_node(cls)


_register_builtin_nodes()
LOADED_CUSTOM_NODE_PATH = load_custom_nodes()


__all__ = [
    'get_node_class',
    'get_registered_node_types',
    'register_node',
    'load_custom_nodes',
    'DEFAULT_CUSTOM_NODE_PATH',
    'LOADED_CUSTOM_NODE_PATH',
]
