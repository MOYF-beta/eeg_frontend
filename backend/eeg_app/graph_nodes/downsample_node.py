from __future__ import annotations

from typing import Any, Dict

from .base import GraphNode, NodeExecutionContext, NodeInputs, NodeOutputs, make_signal, pick_signal_by_port


class DownsampleNode(GraphNode):
    node_type = 'DOWNSAMPLE'

    def compute(self, node: Dict[str, Any], inputs: NodeInputs, context: NodeExecutionContext) -> NodeOutputs:
        sig = pick_signal_by_port(inputs, 'in')
        channels = list(sig.get('channels', []))
        names = list(sig.get('channelNames', []))
        utc_ms = sig.get('utcFirstFrameMs')

        in_rate = float(sig.get('sampleRate') or context.sample_rate)
        params = node.get('params') or {}
        mode = str(params.get('mode') or 'targetRate').lower()

        if mode == 'factor':
            try:
                factor = max(1, int(params.get('factor', 2)))
            except Exception:
                factor = 2
            out_rate = max(1.0, in_rate / factor)
        else:
            try:
                target = float(params.get('targetRate', max(1.0, in_rate / 2.0)))
            except Exception:
                target = max(1.0, in_rate / 2.0)
            target = max(1.0, min(target, in_rate))
            factor = max(1, int(round(in_rate / target)))
            out_rate = max(1.0, in_rate / factor)

        state = context.node_state
        counter = int(state.get('counter', 0)) + 1
        state['counter'] = counter

        emit_this_tick = (counter % factor) == 0
        if not emit_this_tick or not channels:
            return {'out': make_signal([], names, utc_ms, sample_rate=out_rate)}

        return {'out': make_signal(channels, names, utc_ms, sample_rate=out_rate)}
