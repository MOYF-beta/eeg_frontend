from __future__ import annotations

from typing import Any, Dict, List

from .base import GraphNode, NodeExecutionContext, NodeInputs, NodeOutputs, default_channel_names, make_signal, merge_utc


class MergeNode(GraphNode):
    node_type = 'MERGE'

    def compute(self, node: Dict[str, Any], inputs: NodeInputs, context: NodeExecutionContext) -> NodeOutputs:
        params = node.get('params') or {}
        input_cfg = params.get('inputs') if isinstance(params.get('inputs'), list) else []
        strategy = str(params.get('strategy') or 'concat').lower()

        collected: List[Dict[str, Any]] = []
        sorted_items = sorted(inputs.items(), key=lambda item: item[0])
        for port_name, sigs in sorted_items:
            if not sigs:
                continue
            sig = sigs[0]
            channels = list(sig.get('channels', []))
            if not channels:
                continue
            names = list(sig.get('channelNames', []))
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
            if gain != 1.0:
                channels = [v * gain for v in channels]
            collected.append({'channels': channels, 'names': names, 'sig': sig})

        if strategy == 'interleave':
            # 交错模式: CH1_in1, CH1_in2, CH2_in1, CH2_in2, ...
            max_len = max((len(c['channels']) for c in collected), default=0)
            out_channels: List[float] = []
            out_names: List[str] = []
            for i in range(max_len):
                for c in collected:
                    if i < len(c['channels']):
                        out_channels.append(c['channels'][i])
                        if i < len(c['names']):
                            out_names.append(c['names'][i])
                        else:
                            out_names.append(f'CH{i + 1}')
            used_signals = [c['sig'] for c in collected]
            return {'out': make_signal(out_channels, out_names, merge_utc(used_signals))}

        # concat 模式（默认）：拼接全部通道
        out_channels: List[float] = []
        out_names: List[str] = []
        used_signals: List[Dict[str, Any]] = []
        for c in collected:
            out_channels.extend(c['channels'])
            out_names.extend(c['names'] if c['names'] else default_channel_names(len(c['channels'])))
            used_signals.append(c['sig'])
        return {'out': make_signal(out_channels, out_names, merge_utc(used_signals))}
