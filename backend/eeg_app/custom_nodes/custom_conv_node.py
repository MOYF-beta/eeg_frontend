from __future__ import annotations
# pyright: reportMissingImports=false

from typing import Any, Dict, List

import numpy as np

from eeg_app.graph_nodes.base import GraphNode, NodeExecutionContext, NodeInputs, NodeOutputs, make_signal


class ConvolutionNode(GraphNode):
    node_type = 'CUSTOM_CONV'

    def compute(self, node: Dict[str, Any], inputs: NodeInputs, context: NodeExecutionContext) -> NodeOutputs:
        params = node.get('params') or {}
        kernel = np.asarray(params.get('kernel', [0.25, 0.5, 0.25]), dtype=float)
        if kernel.size == 0:
            kernel = np.array([1.0], dtype=float)
        kernel_sum = float(kernel.sum())
        if abs(kernel_sum) < 1e-9:
            kernel = np.array([1.0], dtype=float)
        else:
            kernel = kernel / kernel_sum

        in_signal = (inputs.get('in') or inputs.get('in-1') or [{}])[0]
        channels = np.asarray(in_signal.get('channels', []), dtype=float).reshape(-1)
        utc_ms = in_signal.get('utcFirstFrameMs')
        channel_names = in_signal.get('channelNames') if isinstance(in_signal.get('channelNames'), list) else []
        sample_rate = in_signal.get('sampleRate')

        if channels.size == 0:
            return {'out': make_signal([], utc_first_frame_ms=utc_ms, sample_rate=sample_rate)}

        state = context.node_state
        history: List[np.ndarray] = state.get('history') or []
        history.append(channels)
        max_len = int(max(1, kernel.size))
        if len(history) > max_len:
            history = history[-max_len:]
        state['history'] = history

        window = np.asarray(history, dtype=float)
        if window.ndim == 1:
            window = window.reshape(1, -1)

        k = kernel[::-1]
        used = min(window.shape[0], k.size)
        weights = k[:used].reshape(-1, 1)
        filtered = np.sum(window[-used:, :] * weights, axis=0)

        return {'out': make_signal(filtered.tolist(), channel_names, utc_ms, sample_rate=sample_rate)}
