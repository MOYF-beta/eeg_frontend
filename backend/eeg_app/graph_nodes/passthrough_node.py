from __future__ import annotations

from typing import Any, Dict

from .base import GraphNode, NodeExecutionContext, NodeInputs, NodeOutputs, pick_signal_by_port


class PassthroughNode(GraphNode):
    node_type = 'PASSTHROUGH'

    def compute(self, node: Dict[str, Any], inputs: NodeInputs, context: NodeExecutionContext) -> NodeOutputs:
        return {'out': pick_signal_by_port(inputs, 'in')}
