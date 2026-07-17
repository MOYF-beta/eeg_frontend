from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple, Union

from .base import GraphNode, NodeExecutionContext, NodeInputs, NodeOutputs, clone_signal, pick_signal_by_port


def _butterworth_sos(
    order: int, filter_type: str, cutoff: float, sample_rate: float
) -> List[Union[Tuple[float, float, float, float, float], Tuple[str, float]]]:
    """计算 Butterworth 滤波器的二阶节系数列表。

    返回 sos_list，每个元素为 (b0, b1, b2, a1, a2) 或 ('first_order_lp'/'first_order_hp', alpha)。
    """
    if order < 1:
        order = 1

    nyq = sample_rate / 2.0
    wn = max(0.001, min(0.999, cutoff / nyq))
    w0 = 2.0 * math.pi * wn

    cos_w0 = math.cos(w0)
    sin_w0 = math.sin(w0)

    sections = order // 2
    sos_list: list = []

    for k in range(sections):
        angle = math.pi * (2 * k + 1) / (2 * order)
        cos_angle = math.cos(angle)
        q = 1.0 / (2.0 * cos_angle) if abs(cos_angle) > 1e-10 else 0.7071
        alpha = sin_w0 / (2.0 * q)

        if filter_type == 'highpass':
            b0 = (1 + cos_w0) / 2
            b1 = -(1 + cos_w0)
            b2 = (1 + cos_w0) / 2
        elif filter_type == 'bandpass':
            b0 = alpha
            b1 = 0.0
            b2 = -alpha
        elif filter_type == 'notch':
            b0 = 1.0
            b1 = -2 * cos_w0
            b2 = 1.0
        else:  # lowpass
            b0 = (1 - cos_w0) / 2
            b1 = 1 - cos_w0
            b2 = (1 - cos_w0) / 2

        a0 = 1 + alpha
        a1 = -2 * cos_w0
        a2 = 1 - alpha
        sos_list.append((b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0))

    if order % 2 == 1:
        dt = 1.0 / sample_rate
        rc = 1.0 / (2 * math.pi * cutoff)
        alpha1 = dt / (rc + dt)
        tag = 'first_order_hp' if filter_type == 'highpass' else 'first_order_lp'
        sos_list.append((tag, alpha1))

    return sos_list


class FilterNode(GraphNode):
    node_type = 'FILTER'

    def compute(self, node: Dict[str, Any], inputs: NodeInputs, context: NodeExecutionContext) -> NodeOutputs:
        in_sig = pick_signal_by_port(inputs, 'in')
        channels = list(in_sig.get('channels', []))

        params = node.get('params') or {}
        filter_type = str(params.get('type') or 'lowpass').lower()
        cutoff = float(params.get('cutoff') or 50)
        cutoff = max(0.1, cutoff)
        order = max(1, int(params.get('order') or 1))

        sample_rate = float(context.sample_rate)
        state = context.node_state

        coeff_key = f'coeffs_{order}_{filter_type}_{cutoff:.4f}_{sample_rate:.1f}'
        if state.get('_coeff_key') != coeff_key:
            state['_coeff_key'] = coeff_key
            state['_sos'] = _butterworth_sos(order, filter_type, cutoff, sample_rate)
            state['_num_sections'] = len(state['_sos'])
            for i in range(state['_num_sections']):
                state[f'z1_{i}'] = []
                state[f'z2_{i}'] = []

        sos_list = state.get('_sos') or []
        num_sections = len(sos_list)

        if not channels:
            return {'out': in_sig}

        num_ch = len(channels)

        # 确保各节状态数组够长
        for idx in range(num_sections):
            z1 = list(state.get(f'z1_{idx}') or [])
            z2 = list(state.get(f'z2_{idx}') or [])
            while len(z1) < num_ch:
                z1.append(0.0)
            while len(z2) < num_ch:
                z2.append(0.0)
            state[f'z1_{idx}'] = z1
            state[f'z2_{idx}'] = z2

        out = list(channels)

        for idx in range(num_sections):
            sos = sos_list[idx]
            z1 = state[f'z1_{idx}']
            z2 = state[f'z2_{idx}']

            if isinstance(sos[0], str):
                # 一阶 fallback
                mode_str = sos[0]
                alpha1 = sos[1]
                for i in range(num_ch):
                    x = out[i]
                    lp = alpha1 * x + (1.0 - alpha1) * z1[i]
                    z1[i] = lp
                    out[i] = x - lp if mode_str == 'first_order_hp' else lp
            else:
                b0, b1, b2, a1, a2 = sos
                for i in range(num_ch):
                    x = out[i]
                    y = b0 * x + z1[i]
                    z1[i] = b1 * x - a1 * y + z2[i]
                    z2[i] = b2 * x - a2 * y
                    out[i] = y

        in_sig['channels'] = out
        if not in_sig.get('channelNames'):
            in_sig['channelNames'] = [f'CH{i + 1}' for i in range(len(out))]
        return {'out': in_sig}
