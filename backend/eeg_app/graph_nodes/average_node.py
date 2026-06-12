from __future__ import annotations

from typing import Any, Dict, List

from .base import GraphNode, NodeExecutionContext, NodeInputs, NodeOutputs, default_channel_names, make_signal, merge_utc
from .sum_node import _collect_signals


class AverageNode(GraphNode):
    node_type = 'AVERAGE'

    def compute(self, node: Dict[str, Any], inputs: NodeInputs, context: NodeExecutionContext) -> NodeOutputs:
        params = node.get('params') or {}
        input_cfg = params.get('inputs') if isinstance(params.get('inputs'), list) else []

        raw_signals = _collect_signals(inputs, input_cfg)

        if not raw_signals:
            return {'out': {'channels': [], 'channelNames': [], 'utcFirstFrameMs': None, 'sampleRate': None}}

        count = len(raw_signals)
        max_channels = max((len(s['channels']) for s in raw_signals), default=0)
        name = str(node.get('name') or 'AVG')
        out_channels = [0.0] * max_channels
        out_names: List[str] = []
        used_signals: List[Dict[str, Any]] = []

        for src in raw_signals:
            ch = src['channels']
            w = src['weight']
            for i in range(max_channels):
                val = ch[i] if i < len(ch) else 0.0
                out_channels[i] += val * w
            used_signals.append(src['sig'])
            src_names = list(src['sig'].get('channelNames', []))
            if src_names:
                if not out_names:
                    out_names = [f'{name}.{sn}' for sn in src_names[:max_channels]]

        # 除以输入数量得到平均值
        if count > 1:
            for i in range(max_channels):
                out_channels[i] /= count

        if not out_names:
            out_names = [f'{name}.{default_channel_names(max_channels)[i]}' for i in range(max_channels)]

        return {'out': make_signal(out_channels, out_names, merge_utc(used_signals))}
