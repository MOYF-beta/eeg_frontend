from __future__ import annotations

from typing import Any, Dict, List

from .base import GraphNode, NodeExecutionContext, NodeInputs, NodeOutputs, default_channel_names, make_signal, merge_utc


def _collect_signals(inputs: NodeInputs, input_cfg: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """收集所有输入端口的信号，保持与 input_cfg 配置的权重对齐。"""
    raw_signals: List[Dict[str, Any]] = []
    sorted_items = sorted(inputs.items(), key=lambda item: item[0])
    for port_name, sigs in sorted_items:
        if not sigs:
            continue
        sig = sigs[0]
        channels = list(sig.get('channels', []))
        if not channels:
            continue
        cfg_idx = 0
        if port_name.startswith('in-'):
            try:
                cfg_idx = int(port_name.split('-', 1)[1]) - 1
            except Exception:
                cfg_idx = 0
        weight = 1.0
        if 0 <= cfg_idx < len(input_cfg) and isinstance(input_cfg[cfg_idx], dict):
            try:
                weight = float(input_cfg[cfg_idx].get('weight', 1.0))
            except Exception:
                weight = 1.0
        raw_signals.append({'channels': channels, 'weight': weight, 'sig': sig})
    return raw_signals


class SumNode(GraphNode):
    node_type = 'SUM'

    def compute(self, node: Dict[str, Any], inputs: NodeInputs, context: NodeExecutionContext) -> NodeOutputs:
        params = node.get('params') or {}
        input_cfg = params.get('inputs') if isinstance(params.get('inputs'), list) else []

        raw_signals = _collect_signals(inputs, input_cfg)

        if not raw_signals:
            return {'out': {'channels': [], 'channelNames': [], 'utcFirstFrameMs': None, 'sampleRate': None}}

        # 逐通道求和：所有输入信号按通道序号对齐后求和
        max_channels = max((len(s['channels']) for s in raw_signals), default=0)
        name = str(node.get('name') or 'SUM')
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
                else:
                    for i in range(min(len(out_names), len(src_names))):
                        if not out_names[i].startswith(f'{name}.'):
                            out_names[i] = f'{name}.{sn}' if i < len(src_names) else out_names[i]

        if not out_names:
            out_names = [f'{name}.{default_channel_names(max_channels)[i]}' for i in range(max_channels)]

        return {'out': make_signal(out_channels, out_names, merge_utc(used_signals))}
