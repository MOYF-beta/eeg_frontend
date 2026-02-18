from __future__ import annotations
# pyright: reportMissingImports=false

from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from eeg_app.graph_nodes.base import GraphNode, NodeExecutionContext, NodeInputs, NodeOutputs, make_signal
from eeg_app.python_node_templates import extract_editable_code, generate_python_prototype_spec


def _safe_count(value: object, default: int = 1) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = default
    return max(1, parsed)


def _safe_identifier(value: object, fallback: str) -> str:
    text = str(value or '').strip()
    if not text:
        return fallback
    text = ''.join(ch if (ch.isalnum() or ch == '_') else '_' for ch in text)
    if not text:
        return fallback
    if text[0].isdigit():
        text = f'_{text}'
    return text


def _normalize_names(raw: object, count: int, prefix: str) -> List[str]:
    if isinstance(raw, str):
        items = [token.strip() for token in raw.split(',') if token.strip()]
    elif isinstance(raw, list):
        items = [str(token).strip() for token in raw if str(token).strip()]
    else:
        items = []
    names = [_safe_identifier(item, f'{prefix}_{idx + 1}') for idx, item in enumerate(items)]
    while len(names) < count:
        names.append(f'{prefix}_{len(names) + 1}')
    return names[:count]


def _window_size_points(params: Dict[str, Any], sample_rate: int) -> int:
    mode = str(params.get('windowMode') or 'seconds').lower()
    if mode == 'points':
        return min(60000, _safe_count(params.get('windowPoints'), 256))
    seconds = float(params.get('windowSeconds') or 1.0)
    if seconds <= 0:
        seconds = 1.0
    return min(60000, max(1, int(round(seconds * max(1, sample_rate)))))


def _hop_size_points(params: Dict[str, Any], sample_rate: int) -> int:
    mode = str(params.get('hopMode') or 'points').lower()
    if mode == 'milliseconds':
        hop_ms = float(params.get('hopMs') or 0)
        if hop_ms <= 0:
            return 1
        return max(1, int(round((hop_ms * max(1, sample_rate)) / 1000.0)))
    if mode == 'targetrate':
        try:
            target_rate = float(params.get('outputSampleRate') or sample_rate)
        except Exception:
            target_rate = float(sample_rate)
        target_rate = max(1.0, target_rate)
        return max(1, int(round(max(1.0, float(sample_rate)) / target_rate)))
    return max(1, _safe_count(params.get('hopPoints'), 1))


def _pick_signal(inputs: NodeInputs, port: str) -> Dict[str, Any]:
    if port in inputs and inputs[port]:
        return dict(inputs[port][0])
    if port == 'in-1' and inputs.get('in'):
        return dict(inputs['in'][0])
    if port == 'in' and inputs.get('in-1'):
        return dict(inputs['in-1'][0])
    for sigs in inputs.values():
        if sigs:
            return dict(sigs[0])
    return {'channels': [], 'channelNames': [], 'utcFirstFrameMs': None}


def _vector_from_signal(sig: Dict[str, Any]) -> np.ndarray:
    arr = np.asarray(sig.get('channels', []), dtype=float).reshape(-1)
    return arr


def _build_window(buffer_rows: List[np.ndarray], expected_channels: int) -> np.ndarray:
    if not buffer_rows:
        if expected_channels > 0:
            return np.zeros((0, expected_channels), dtype=float)
        return np.zeros((0, 0), dtype=float)

    width = expected_channels
    if width <= 0:
        width = max((int(row.size) for row in buffer_rows), default=0)
    if width <= 0:
        return np.zeros((len(buffer_rows), 0), dtype=float)

    out = np.zeros((len(buffer_rows), width), dtype=float)
    for idx, row in enumerate(buffer_rows):
        row = np.asarray(row, dtype=float).reshape(-1)
        n = min(width, int(row.size))
        if n > 0:
            out[idx, :n] = row[:n]
    return out


def _to_output_vector(value: Any, expected_channels: int) -> np.ndarray:
    arr = np.asarray(value, dtype=float)
    if arr.size == 0:
        return np.array([], dtype=float)
    if arr.ndim == 0:
        vec = np.array([float(arr)], dtype=float)
    elif arr.ndim == 1:
        vec = arr.reshape(-1)
    else:
        vec = np.asarray(arr[-1], dtype=float).reshape(-1)

    if expected_channels > 0:
        if vec.size != expected_channels:
            raise AssertionError(f'output channel mismatch: expected {expected_channels}, got {vec.size}')
    return vec


class CustomPyFuncNode(GraphNode):
    node_type = 'CUSTOM_PYFUNC'

    def compute(self, node: Dict[str, Any], inputs: NodeInputs, context: NodeExecutionContext) -> NodeOutputs:
        params = node.get('params') or {}
        mode = str(params.get('portMode') or 'fixed').lower()
        input_count = _safe_count(params.get('inputCount'), 1)
        output_count = _safe_count(params.get('outputCount'), 1)

        # 端口顺序：固定模式由数量决定；自适应模式按连接输入端口排序
        if mode == 'adaptive':
            ordered_input_ports = sorted(inputs.keys()) if inputs else ['in']
            if not ordered_input_ports:
                ordered_input_ports = ['in']
            ordered_output_ports = [f'out-{idx + 1}' for idx in range(max(1, len(ordered_input_ports)))]
        else:
            ordered_input_ports = [f'in-{i + 1}' for i in range(input_count)]
            ordered_output_ports = [f'out-{i + 1}' for i in range(output_count)]

        input_names = _normalize_names(params.get('inputNames'), len(ordered_input_ports), 'input')
        output_names = _normalize_names(params.get('outputNames'), len(ordered_output_ports), 'output')
        function_name = _safe_identifier(params.get('functionName'), 'process_generated')

        editable_code = str(params.get('pythonEditableCode') or '').strip()
        if not editable_code:
            editable_code = extract_editable_code(str(params.get('pythonCode') or ''))

        window_points = _window_size_points(params, context.sample_rate)
        hop_points = _hop_size_points(params, context.sample_rate)
        derived_output_rate = max(1.0, float(context.sample_rate) / float(hop_points))
        buffers: Dict[str, List[np.ndarray]] = context.node_state.setdefault('windowBuffers', {})

        current_inputs: List[np.ndarray] = []
        input_windows: List[np.ndarray] = []
        input_signals: List[Dict[str, Any]] = []
        utc_candidates: List[int] = []
        channel_names: List[str] = []
        expected_channels = 0

        for port in ordered_input_ports:
            sig = _pick_signal(inputs, port)
            input_signals.append(sig)
            vec = _vector_from_signal(sig)
            current_inputs.append(vec)

            if expected_channels == 0 and vec.size > 0:
                expected_channels = int(vec.size)
                names = sig.get('channelNames') if isinstance(sig.get('channelNames'), list) else []
                channel_names = [str(n) for n in names][:expected_channels]

            if sig.get('utcFirstFrameMs') is not None:
                try:
                    utc_candidates.append(int(sig.get('utcFirstFrameMs')))
                except Exception:
                    pass

            rows = buffers.get(port, [])
            rows.append(vec)
            if len(rows) > window_points:
                rows = rows[-window_points:]
            buffers[port] = rows
            input_windows.append(_build_window(rows, expected_channels if expected_channels > 0 else int(vec.size)))

        if not channel_names and expected_channels > 0:
            channel_names = [f'CH{i + 1}' for i in range(expected_channels)]
        utc_ms: Optional[int] = min(utc_candidates) if utc_candidates else None

        hop_counter = int(context.node_state.get('hopCounter', 0)) + 1
        context.node_state['hopCounter'] = hop_counter
        should_execute = (hop_counter % hop_points) == 0
        if not should_execute:
            outputs: NodeOutputs = {}
            for port in ordered_output_ports:
                outputs[port] = make_signal([], channel_names, utc_ms, sample_rate=derived_output_rate)
            if mode == 'adaptive' and outputs and 'out' not in outputs:
                outputs['out'] = outputs[ordered_output_ports[0]]
            return outputs

        prototype = generate_python_prototype_spec(
            input_count=len(ordered_input_ports),
            output_count=len(ordered_output_ports),
            function_name=function_name,
            input_names=input_names,
            output_names=output_names,
            editable_code=editable_code,
        )
        full_code = str(prototype.get('code', ''))
        fn_name = str(prototype.get('functionName', function_name))

        compile_key = '|'.join(
            [
                fn_name,
                ','.join(input_names),
                ','.join(output_names),
                editable_code,
                str(len(ordered_input_ports)),
                str(len(ordered_output_ports)),
            ]
        )

        fn = context.node_state.get('compiledFn')
        if context.node_state.get('compiledKey') != compile_key or not callable(fn):
            safe_globals: Dict[str, Any] = {
                'np': np,
                '__builtins__': {'print': print, 'len': len, 'range': range, 'min': min, 'max': max, 'abs': abs, 'sum': sum},
            }
            local_ns: Dict[str, Any] = {}
            try:
                exec(full_code, safe_globals, local_ns)
                fn = local_ns.get(fn_name) or safe_globals.get(fn_name)
                if not callable(fn):
                    raise RuntimeError(f'generated function {fn_name} is not callable')
                context.node_state['compiledFn'] = fn
                context.node_state['compiledKey'] = compile_key
            except Exception as exc:
                print(f'[CustomPyFuncNode] compile failed: {exc}')
                fn = None

        output_vectors: List[np.ndarray] = []
        if callable(fn):
            try:
                returned = fn(*input_windows, params)
                if len(ordered_output_ports) == 1:
                    returned_values: Tuple[Any, ...] = (returned,)
                elif isinstance(returned, tuple):
                    returned_values = returned
                elif isinstance(returned, list):
                    returned_values = tuple(returned)
                else:
                    returned_values = (returned,)

                for idx in range(len(ordered_output_ports)):
                    raw_value = returned_values[idx] if idx < len(returned_values) else np.array([], dtype=float)
                    output_vectors.append(_to_output_vector(raw_value, expected_channels))
            except Exception as exc:
                print(f'[CustomPyFuncNode] execute failed: {exc}')

        if not output_vectors:
            # 回退：复制首输入当前帧
            fallback = current_inputs[0] if current_inputs else np.array([], dtype=float)
            output_vectors = [fallback.copy() for _ in ordered_output_ports]

        outputs: NodeOutputs = {}
        for idx, port in enumerate(ordered_output_ports):
            vec = output_vectors[idx] if idx < len(output_vectors) else np.array([], dtype=float)
            outputs[port] = make_signal(
                vec.tolist(),
                channel_names[: len(vec)] if channel_names else None,
                utc_ms,
                sample_rate=derived_output_rate,
            )

        if mode == 'adaptive' and outputs:
            # 兼容自适应端口单输出
            first_key = ordered_output_ports[0]
            if first_key != 'out':
                outputs['out'] = outputs[first_key]

        return outputs
