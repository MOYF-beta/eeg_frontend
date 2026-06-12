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
        for port_name, sigs in sorted_items:
            if not sigs:
                continue
            sig = sigs[0]
            channels = list(sig.get('channels', []))
            if not channels:
                continue
            names = list(sig.get('channelNames', []))
            # 从端口名 'in-<N>' 提取序号以匹配 input_cfg 配置
            cfg_idx = 0
            if port_name.startswith('in-'):
                try:
                    cfg_idx = int(port_name.split('-', 1)[1]) - 1
                except Exception:
                    cfg_idx = 0
            gain = 1.0
            if 0 <= cfg_idx < len(input_cfg) and isinstance(input_cfg[cfg_idx], dict):
                try:
                    gain = float(input_cfg[cfg_idx].get('gain', 1.0))
                except Exception:
                    gain = 1.0
            out_channels.extend([v * gain for v in channels])
            out_names.extend(names if names else default_channel_names(len(channels)))
            used_signals.append(sig)

        return {'out': make_signal(out_channels, out_names, merge_utc(used_signals))}
