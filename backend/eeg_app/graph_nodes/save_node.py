from __future__ import annotations

from typing import Any, Dict

from .base import GraphNode, NodeExecutionContext, NodeInputs, NodeOutputs, pick_signal_by_port


class SaveNode(GraphNode):
    node_type = 'SAVE'

    def compute(self, node: Dict[str, Any], inputs: NodeInputs, context: NodeExecutionContext) -> NodeOutputs:
        return {'in': pick_signal_by_port(inputs, 'in')}
