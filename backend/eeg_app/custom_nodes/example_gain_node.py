from __future__ import annotations

from typing import Any, Dict

from eeg_app.graph_nodes.base import GraphNode, NodeExecutionContext, NodeInputs, NodeOutputs, pick_signal_by_port


class GainNode(GraphNode):
    node_type = 'CUSTOM_GAIN'

    def compute(self, node: Dict[str, Any], inputs: NodeInputs, context: NodeExecutionContext) -> NodeOutputs:
        sig = pick_signal_by_port(inputs, 'in')
        gain = 1.0
        try:
            gain = float((node.get('params') or {}).get('gain', 1.0))
        except Exception:
            gain = 1.0
        sig['channels'] = [v * gain for v in sig.get('channels', [])]
        return {'out': sig}
