from __future__ import annotations

from typing import Any, Dict

from .base import GraphNode, NodeExecutionContext, NodeInputs, NodeOutputs, default_channel_names, make_signal


class SourceNode(GraphNode):
    node_type = 'SOURCE'

    def compute(self, node: Dict[str, Any], inputs: NodeInputs, context: NodeExecutionContext) -> NodeOutputs:
        channels = list(context.node_state.get('generatedChannels', []))
        params = node.get('params') or {}
        names = params.get('channelNames') if isinstance(params.get('channelNames'), list) else None
        if not names:
            names = default_channel_names(len(channels))
        signal = make_signal(
            channels,
            [str(v) for v in names],
            context.node_state.get('generatedUtcMs'),
            sample_rate=float(context.sample_rate),
        )
        return {'out': signal}
