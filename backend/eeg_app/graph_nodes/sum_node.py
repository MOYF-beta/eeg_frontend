from __future__ import annotations

from typing import Any, Dict, List

from .base import GraphNode, NodeExecutionContext, NodeInputs, NodeOutputs, make_signal, merge_utc


class SumNode(GraphNode):
    node_type = 'SUM'

    def compute(self, node: Dict[str, Any], inputs: NodeInputs, context: NodeExecutionContext) -> NodeOutputs:
        params = node.get('params') or {}
        input_cfg = params.get('inputs') if isinstance(params.get('inputs'), list) else []

        value = 0.0
        has_value = False
        used_signals = []

        if input_cfg:
            for idx, cfg in enumerate(input_cfg):
                port = f'in-{idx + 1}'
                sigs = inputs.get(port) or []
                if not sigs:
                    continue
                sig = sigs[0]
                channels = list(sig.get('channels', []))
                if not channels:
                    continue
                weight = 1.0
                if isinstance(cfg, dict):
                    try:
                        weight = float(cfg.get('weight', 1.0))
                    except Exception:
                        weight = 1.0
                value += channels[0] * weight
                has_value = True
                used_signals.append(sig)
        else:
            for sigs in inputs.values():
                if not sigs:
                    continue
                sig = sigs[0]
                channels = list(sig.get('channels', []))
                if not channels:
                    continue
                value += channels[0]
                has_value = True
                used_signals.append(sig)

        out_channels = [value] if has_value else []
        name = str(node.get('name') or 'SUM')
        out = make_signal(out_channels, [name] if out_channels else [], merge_utc(used_signals))
        return {'out': out}
