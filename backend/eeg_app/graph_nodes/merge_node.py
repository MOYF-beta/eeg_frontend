from __future__ import annotations

from typing import Any, Dict, List

from .base import GraphNode, NodeExecutionContext, NodeInputs, NodeOutputs, default_channel_names, make_signal, merge_utc


class MergeNode(GraphNode):
    node_type = 'MERGE'

    def compute(self, node: Dict[str, Any], inputs: NodeInputs, context: NodeExecutionContext) -> NodeOutputs:
        params = node.get('params') or {}
        input_cfg = params.get('inputs') if isinstance(params.get('inputs'), list) else []

        out_channels: List[float] = []
        out_names: List[str] = []
        used_signals: List[Dict[str, Any]] = []

        sorted_items = sorted(inputs.items(), key=lambda item: item[0])
        for idx, (_, sigs) in enumerate(sorted_items):
            if not sigs:
                continue
            sig = sigs[0]
            channels = list(sig.get('channels', []))
            if not channels:
                continue
            names = list(sig.get('channelNames', []))
            gain = 1.0
            if idx < len(input_cfg) and isinstance(input_cfg[idx], dict):
                try:
                    gain = float(input_cfg[idx].get('gain', 1.0))
                except Exception:
                    gain = 1.0
            out_channels.extend([v * gain for v in channels])
            out_names.extend(names if names else default_channel_names(len(channels)))
            used_signals.append(sig)

        return {'out': make_signal(out_channels, out_names, merge_utc(used_signals))}
