from __future__ import annotations

from typing import Any, Dict

from .base import GraphNode, NodeExecutionContext, NodeInputs, NodeOutputs, make_signal, pick_signal_by_port


class UpsampleNode(GraphNode):
    node_type = 'UPSAMPLE'

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
            out_rate = in_rate * factor
        else:
            try:
                out_rate = max(1.0, float(params.get('targetRate', in_rate)))
            except Exception:
                out_rate = in_rate

        state = context.node_state
        if channels:
            state['lastChannels'] = channels
            state['lastNames'] = names
            state['lastUtc'] = utc_ms
            return {'out': make_signal(channels, names, utc_ms, sample_rate=out_rate)}

        last_channels = state.get('lastChannels') or []
        if not last_channels:
            return {'out': make_signal([], names, utc_ms, sample_rate=out_rate)}

        last_names = state.get('lastNames') or names
        last_utc = state.get('lastUtc') if state.get('lastUtc') is not None else utc_ms
        return {'out': make_signal(list(last_channels), list(last_names), last_utc, sample_rate=out_rate)}
