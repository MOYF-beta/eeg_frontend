from __future__ import annotations

import math
from typing import Any, Dict, List

from .base import GraphNode, NodeExecutionContext, NodeInputs, NodeOutputs, clone_signal, pick_signal_by_port


class FilterNode(GraphNode):
    node_type = 'FILTER'

    def compute(self, node: Dict[str, Any], inputs: NodeInputs, context: NodeExecutionContext) -> NodeOutputs:
        in_sig = pick_signal_by_port(inputs, 'in')
        channels = list(in_sig.get('channels', []))

        params = node.get('params') or {}
        filter_type = str(params.get('type') or 'lowpass').lower()
        cutoff = float(params.get('cutoff') or 50)
        cutoff = max(0.1, cutoff)

        dt = 1.0 / max(1, context.sample_rate)
        rc = 1.0 / (2 * math.pi * cutoff)
        alpha = dt / (rc + dt)

        state = context.node_state
        low_state: List[float] = list(state.get('lowState') or [])
        high_state: List[float] = list(state.get('highState') or [])

        if not channels:
            # 输入为空时衰减滤波器状态以趋近于零，避免虚假信号延续
            decay = max(0.0, 1.0 - alpha * 0.1)
            for i in range(len(low_state)):
                low_state[i] *= decay
            for i in range(len(high_state)):
                high_state[i] *= decay
            state['lowState'] = low_state
            state['highState'] = high_state
            return {'out': in_sig}

        if len(low_state) < len(channels):
            low_state.extend([channels[0] if channels else 0.0] * (len(channels) - len(low_state)))
        if len(high_state) < len(channels):
            high_state.extend([0.0] * (len(channels) - len(high_state)))

        out = [0.0] * len(channels)
        for i, x in enumerate(channels):
            low_state[i] = alpha * x + (1.0 - alpha) * low_state[i]
            high_state[i] = x - low_state[i]
            if filter_type == 'highpass':
                out[i] = high_state[i]
            elif filter_type == 'bandpass':
                out[i] = high_state[i] * 0.6
            elif filter_type == 'notch':
                out[i] = x - (high_state[i] * 0.2)
            else:
                out[i] = low_state[i]

        state['lowState'] = low_state
        state['highState'] = high_state

        in_sig['channels'] = out
        if not in_sig.get('channelNames'):
            in_sig['channelNames'] = [f'CH{i + 1}' for i in range(len(out))]
        return {'out': in_sig}
