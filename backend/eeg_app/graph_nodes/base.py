from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


Signal = Dict[str, Any]
NodeInputs = Dict[str, List[Signal]]
NodeOutputs = Dict[str, Signal]


def default_channel_names(count: int) -> List[str]:
    return [f"CH{i + 1}" for i in range(max(0, int(count)))]


def clone_signal(signal: Optional[Signal]) -> Signal:
    if not signal:
        return {'channels': [], 'channelNames': [], 'utcFirstFrameMs': None, 'sampleRate': None}
    return {
        'channels': list(signal.get('channels', [])),
        'channelNames': list(signal.get('channelNames', [])),
        'utcFirstFrameMs': signal.get('utcFirstFrameMs'),
        'sampleRate': signal.get('sampleRate'),
    }


def make_signal(
    channels: List[float],
    channel_names: Optional[List[str]] = None,
    utc_first_frame_ms: Optional[int] = None,
    sample_rate: Optional[float] = None,
) -> Signal:
    names = list(channel_names or [])
    if len(names) < len(channels):
        names.extend(default_channel_names(len(channels) - len(names)))
    return {
        'channels': list(channels),
        'channelNames': names[: len(channels)],
        'utcFirstFrameMs': utc_first_frame_ms,
        'sampleRate': sample_rate,
    }


def parse_channel_indices(raw: object) -> List[int]:
    if not isinstance(raw, str):
        return []
    values: List[int] = []
    normalized = raw.replace('，', ',')
    for part in normalized.split(','):
        token = part.strip()
        if not token:
            continue
        try:
            idx = int(token)
        except Exception:
            continue
        if idx >= 0:
            values.append(idx)
    return values


def pick_signal_by_port(inputs: NodeInputs, port: str, fallback_port: str = 'in') -> Signal:
    if port in inputs and inputs[port]:
        return clone_signal(inputs[port][0])
    if fallback_port in inputs and inputs[fallback_port]:
        return clone_signal(inputs[fallback_port][0])
    for sigs in inputs.values():
        if sigs:
            return clone_signal(sigs[0])
    return {'channels': [], 'channelNames': [], 'utcFirstFrameMs': None, 'sampleRate': None}


def merge_utc(signals: List[Signal]) -> Optional[int]:
    utc_values = [sig.get('utcFirstFrameMs') for sig in signals if sig and sig.get('utcFirstFrameMs') is not None]
    if not utc_values:
        return None
    return int(min(utc_values))


@dataclass
class NodeExecutionContext:
    node_state: Dict[str, Any]
    sample_rate: int
    wall_time_ms: int


class GraphNode:
    node_type = 'BASE'

    def compute(self, node: Dict[str, Any], inputs: NodeInputs, context: NodeExecutionContext) -> NodeOutputs:
        raise NotImplementedError
