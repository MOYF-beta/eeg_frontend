from __future__ import annotations

from typing import Any, Dict, List

from .base import GraphNode, NodeExecutionContext, NodeInputs, NodeOutputs, make_signal, parse_channel_indices, pick_signal_by_port


class SplitNode(GraphNode):
    node_type = 'SPLIT'

    def compute(self, node: Dict[str, Any], inputs: NodeInputs, context: NodeExecutionContext) -> NodeOutputs:
        in_sig = pick_signal_by_port(inputs, 'in')
        in_channels = list(in_sig.get('channels', []))
        in_names = list(in_sig.get('channelNames', []))
        utc_ms = in_sig.get('utcFirstFrameMs')

        params = node.get('params') or {}
        outputs_cfg = params.get('outputs') if isinstance(params.get('outputs'), list) else []
        if not outputs_cfg:
            outputs_cfg = [{'label': '输出1', 'channelIndices': ','.join(str(i) for i in range(len(in_channels)))}]

        outputs: NodeOutputs = {}
        for idx, cfg in enumerate(outputs_cfg):
            port = f'out-{idx + 1}'
            label = f'输出{idx + 1}'
            raw_indices = ''
            if isinstance(cfg, dict):
                label = str(cfg.get('label') or label)
                raw_indices = str(cfg.get('channelIndices') or '')
            indices = parse_channel_indices(raw_indices)
            if indices:
                channels = [in_channels[i] for i in indices if 0 <= i < len(in_channels)]
                names = [in_names[i] if i < len(in_names) else f'CH{i + 1}' for i in indices if 0 <= i < len(in_channels)]
                if not channels:
                    # 所有索引越界时跳过此端口，不产生空信号
                    continue
            else:
                channels = list(in_channels)
                names = list(in_names)

            if label:
                if len(channels) == 1:
                    names = [label]
                else:
                    names = [f'{label}.{n}' for n in names]
            outputs[port] = make_signal(channels, names, utc_ms)

        return outputs
