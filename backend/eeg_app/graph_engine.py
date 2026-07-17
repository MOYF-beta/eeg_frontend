from __future__ import annotations

import logging
logger = logging.getLogger(__name__)

import json
import math
import queue
import random
import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from .graph_nodes import get_node_class
from .graph_nodes.base import NodeExecutionContext, default_channel_names


# ---------------------------------------------------------------------- #
#  Source Providers — 替代旧的 _generate_source_channels / _drain_real_devices_sync
# ---------------------------------------------------------------------- #

class _SourceProvider:
    """基类：为 SOURCE/REPLAY 节点提供逐帧数据。

    每个 provider 实例绑定一个 source 节点，负责在每 tick 产出一帧
    (channels, utc_ms)。provider 自己管理缓冲、时间步进和采样率，
    GraphWorker 只负责按拓扑序调用 compute()。
    """

    def __init__(self, node_id: str, sample_rate: int):
        self.node_id = node_id
        self.sample_rate = max(1, sample_rate)

    def available_samples(self) -> int:
        """当前缓冲区中可消费的帧数（用于设备同步窗口计算）。"""
        return 1  # 默认：合成/回放随时可产

    def next_sample(self) -> Tuple[List[float], Optional[int]]:
        """返回下一帧 (channels, utc_ms)，无数据时返回 ([], None)。"""
        raise NotImplementedError


class _DeviceSourceProvider(_SourceProvider):
    """从 DeviceDriverManager 读取设备数据的 provider。"""

    # 每次从 manager 拉取的最大帧数
    _MAX_BATCH = 1024

    def __init__(self, node_id: str, sample_rate: int, device_id: str, channel_count: int):
        super().__init__(node_id, sample_rate)
        self._device_id = device_id
        self._channel_count = channel_count
        self._pending: List[Tuple[List[float], int]] = []  # [(channels, utc_ms)]

    def available_samples(self) -> int:
        if not self._pending:
            self._refill()
        return len(self._pending)

    def next_sample(self) -> Tuple[List[float], Optional[int]]:
        if not self._pending:
            self._refill()
        if not self._pending:
            return [], None
        channels, utc_ms = self._pending.pop(0)
        # 对齐通道数
        if len(channels) < self._channel_count:
            channels = channels + [0.0] * (self._channel_count - len(channels))
        elif len(channels) > self._channel_count:
            channels = channels[:self._channel_count]
        return channels, utc_ms

    def _refill(self) -> None:
        """从 manager 批量拉取数据到内部缓冲。"""
        from .drivers.manager import get_device_manager
        manager = get_device_manager()
        count = max(8, min(self._MAX_BATCH, int(self.sample_rate * 0.2)))
        try:
            frames = manager.read_data(self._device_id, count=count)
        except Exception as exc:
            logger.debug(f'[DeviceSource] read_data failed for {self._device_id}: {exc}')
            return
        for frame in frames:
            channels = [float(ch) for ch in frame.channels]
            utc_ms = int(frame.timestamp * 1000)
            self._pending.append((channels, utc_ms))


class _ReplaySourceProvider(_SourceProvider):
    """从 CSV 回放读取数据的 provider。"""

    def __init__(self, node_id: str, sample_rate: int):
        super().__init__(node_id, sample_rate)

    def available_samples(self) -> int:
        return 1  # 回放每 tick 读一行

    def next_sample(self) -> Tuple[List[float], Optional[int]]:
        from .data_replay import is_replaying, read_next_sample
        if not is_replaying(self.node_id):
            return [], None
        sample = read_next_sample(self.node_id)
        if not sample:
            return [], None
        return list(sample.get('channels', [])), int(sample.get('timestamp', time.time() * 1000))


class _SyntheticSourceProvider(_SourceProvider):
    """无设备绑定时生成方波+噪声的兜底 provider。"""

    def __init__(self, node_id: str, sample_rate: int, channel_count: int = 8):
        super().__init__(node_id, sample_rate)
        self._channel_count = channel_count
        self._t: float = 0.0

    def available_samples(self) -> int:
        return 1

    def next_sample(self) -> Tuple[List[float], Optional[int]]:
        dt = 1.0 / self.sample_rate
        self._t += dt
        t = self._t
        channels: List[float] = []
        for i in range(self._channel_count):
            freq = 5 + i * 0.5
            square = 1 if math.sin(2 * math.pi * freq * t) > 0 else -1
            signal = square * 100
            noise = math.sin(2 * math.pi * (50 + i * 10) * t) * 5 + math.sin(2 * math.pi * (120 + i * 5) * t) * 3
            channels.append(signal + noise + random.uniform(-2, 2))
        return channels, int(time.time() * 1000)


@dataclass
class WorkerSpec:
    worker_id: str
    node_ids: Set[str]
    edges: List[Dict[str, Any]]
    subscribed_sink_ids: Set[str]
    save_node_ids: Set[str]


class GraphWorker:
    def __init__(self, spec: WorkerSpec, nodes_by_id: Dict[str, Dict[str, Any]]):
        self.spec = spec
        self.nodes_by_id = {nid: nodes_by_id[nid] for nid in spec.node_ids if nid in nodes_by_id}
        self.event_queue: "queue.Queue[Dict[str, Any]]" = queue.Queue(maxsize=20000)
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, name=f"graph-worker-{spec.worker_id}", daemon=True)

        self.node_states: Dict[str, Dict[str, Any]] = defaultdict(dict)
        self.topo_order: List[str] = self._build_topological_order()
        self.incoming_by_target: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for edge in self.spec.edges:
            target = edge.get('target')
            if target in self.node_ids:
                self.incoming_by_target[target].append(edge)
        for target in self.incoming_by_target:
            self.incoming_by_target[target].sort(key=lambda e: str(e.get('targetPort') or ''))

        self.source_node_ids = [
            node_id
            for node_id, node in self.nodes_by_id.items()
            if str(node.get('type')).upper() in {'SOURCE', 'REPLAY'}
        ]
        self.sample_rate = self._resolve_sample_rate()
        self.started_wall_ms = int(time.time() * 1000)
        self.generated_sample_count = 0

        # 为每个 source 节点构建 provider
        self.source_providers: Dict[str, _SourceProvider] = {}
        self._build_source_providers()

        # 缓存节点 processor 实例，避免每个 tick 创建新对象
        self._processor_cache: Dict[str, Any] = {}

    def _build_source_providers(self) -> None:
        """根据节点配置为每个 SOURCE/REPLAY 节点创建对应的 provider。"""
        from .drivers.manager import get_device_manager

        manager = get_device_manager()
        for node_id in self.source_node_ids:
            node = self.nodes_by_id.get(node_id) or {}
            node_type = str(node.get('type') or '').upper()
            params = node.get('params') or {}

            # REPLAY 节点 — 文件回放
            if node_type == 'REPLAY':
                self.source_providers[node_id] = _ReplaySourceProvider(node_id, self.sample_rate)
                continue

            # SOURCE 节点 — 实时设备采集
            device_id = self._resolve_source_device_id(node)
            if device_id:
                meta = manager.get_device_meta(device_id)
                ch_count = meta.channel_count if meta else int(params.get('channels') or 8)
                self.source_providers[node_id] = _DeviceSourceProvider(
                    node_id, self.sample_rate, device_id, max(1, ch_count),
                )
            else:
                # 无设备绑定：合成信号兜底
                ch_count = max(1, int(params.get('channels') or 8))
                self.source_providers[node_id] = _SyntheticSourceProvider(
                    node_id, self.sample_rate, ch_count,
                )

    @property
    def node_ids(self) -> Set[str]:
        return set(self.nodes_by_id.keys())

    def _resolve_sample_rate(self) -> int:
        from .drivers.manager import get_device_manager
        manager = get_device_manager()
        for node_id in self.source_node_ids:
            node = self.nodes_by_id.get(node_id) or {}
            params = node.get('params') or {}
            device_id = node.get('deviceId') or params.get('deviceId')
            if device_id:
                try:
                    meta = manager.get_device_meta(str(device_id))
                    if meta:
                        value = int(meta.sample_rate or params.get('sampleRate') or 1000)
                        if value > 0:
                            return value
                except Exception:
                    pass
            try:
                value = int(params.get('sampleRate', 1000))
            except Exception:
                value = 1000
            if value > 0:
                return value
        return 1000

    def _resolve_source_device_id(self, node: Dict[str, Any]) -> Optional[str]:
        params = node.get('params') or {}
        raw = node.get('deviceId') or params.get('deviceId')
        if raw is None:
            return None
        text = str(raw).strip()
        return text or None

    def _build_topological_order(self) -> List[str]:
        indegree: Dict[str, int] = {nid: 0 for nid in self.node_ids}
        outgoing: Dict[str, List[str]] = defaultdict(list)
        for edge in self.spec.edges:
            src = edge.get('source')
            tgt = edge.get('target')
            if src in indegree and tgt in indegree:
                indegree[tgt] += 1
                outgoing[src].append(tgt)

        ready = sorted([nid for nid, deg in indegree.items() if deg == 0])
        order: List[str] = []
        while ready:
            current = ready.pop(0)
            order.append(current)
            for nxt in outgoing.get(current, []):
                indegree[nxt] -= 1
                if indegree[nxt] == 0:
                    ready.append(nxt)
            ready.sort()

        if len(order) < len(indegree):
            unresolved = [nid for nid in indegree if nid not in order]
            logger.error(
                '[GraphWorker] Cycle detected in graph component %s! '
                'Unresolved node ids: %s. Stopping worker.',
                self.spec.worker_id, sorted(unresolved),
            )
            self.stop_event.set()
            return []
        return order

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread.is_alive():
            self.thread.join(timeout=1.0)

    def drain_events(self, max_items: int = 2000) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for _ in range(max_items):
            try:
                items.append(self.event_queue.get_nowait())
            except queue.Empty:
                break
        return items

    def _put_event(self, event: Dict[str, Any]) -> None:
        try:
            self.event_queue.put_nowait(event)
        except queue.Full:
            # 队列满时丢弃最旧的数据并记录警告
            logger.warning(
                '[GraphWorker] Event queue full for worker %s (size=%d). '
                'Dropping oldest frame. Consider increasing maxsize or reducing sample rate.',
                self.spec.worker_id, self.event_queue.maxsize,
            )
            try:
                _ = self.event_queue.get_nowait()
                self.event_queue.put_nowait(event)
            except Exception:
                pass

    def _pick_output(self, outputs: Dict[str, Dict[str, Any]], preferred_port: str) -> Dict[str, Any]:
        if preferred_port in outputs:
            return outputs[preferred_port]
        if outputs:
            # 回退匹配：去掉端口名末尾数字（如 'out0' → 'out'，'in0' → 'in'）
            import re
            base = re.sub(r'\d+$', '', preferred_port)
            if base and base in outputs:
                return outputs[base]
            # 最后回退：返回任意第一个可用端口
            first_key = next(iter(outputs))
            return outputs[first_key]
        return {'channels': [], 'channelNames': [], 'utcFirstFrameMs': None}

    def _has_device_provider(self) -> bool:
        """检查是否存在设备型 provider（决定同步/定时模式）。"""
        return any(isinstance(p, _DeviceSourceProvider) for p in self.source_providers.values())

    def _device_available_samples(self) -> int:
        """所有设备 provider 的最小可用帧数（同步窗口）。"""
        counts = [
            p.available_samples()
            for p in self.source_providers.values()
            if isinstance(p, _DeviceSourceProvider)
        ]
        if not counts:
            return 0
        SYNC_WINDOW = 4
        return min(min(counts), SYNC_WINDOW)

    def _run(self) -> None:
        from .data_recorder import write_sample
        from .perf_monitor import get_perf_monitor, PipelineMetrics

        max_samples_per_loop = max(1, int(self.sample_rate * 0.2))
        last_sample_time = time.perf_counter()
        sample_accumulator = 0.0
        perf = get_perf_monitor()

        tick = 0
        while not self.stop_event.is_set():
            tick += 1
            # 决定本 tick 要生成多少帧
            if self._has_device_provider():
                samples_to_generate = self._device_available_samples()
                if samples_to_generate <= 0:
                    self.stop_event.wait(0.002)
                    continue
            else:
                now = time.perf_counter()
                elapsed_samples = (now - last_sample_time) * self.sample_rate
                last_sample_time = now
                sample_accumulator += elapsed_samples

                samples_to_generate = int(sample_accumulator)
                if samples_to_generate <= 0:
                    self.stop_event.wait(0.001)
                    continue

                if samples_to_generate > max_samples_per_loop:
                    sample_accumulator -= float(max_samples_per_loop)
                    samples_to_generate = max_samples_per_loop
                else:
                    sample_accumulator -= samples_to_generate

            loop_start = time.perf_counter_ns()
            source_gen_total_ns = 0
            node_compute_total_ns = 0
            event_samples = 0

            for _ in range(samples_to_generate):
                self.generated_sample_count += 1
                node_outputs: Dict[str, Dict[str, Dict[str, Any]]] = {}

                for node_id in self.topo_order:
                    node = self.nodes_by_id.get(node_id)
                    if not node:
                        continue
                    node_type = str(node.get('type') or '').upper()
                    node_state = self.node_states[node_id]

                    # SOURCE/REPLAY 节点：从 provider 取数据
                    t0 = time.perf_counter_ns()
                    if node_type in {'SOURCE', 'REPLAY'}:
                        provider = self.source_providers.get(node_id)
                        if provider:
                            channels, utc_ms = provider.next_sample()
                        else:
                            channels, utc_ms = [], None
                        node_state['generatedChannels'] = channels
                        node_state['generatedUtcMs'] = utc_ms
                    source_gen_total_ns += time.perf_counter_ns() - t0

                    # 组装入边
                    inputs: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
                    for edge in self.incoming_by_target.get(node_id, []):
                        src = edge.get('source')
                        if src not in node_outputs:
                            continue
                        src_port = edge.get('sourcePort') or 'out'
                        tgt_port = edge.get('targetPort') or 'in'
                        src_sig = self._pick_output(node_outputs[src], src_port)
                        inputs[tgt_port].append(src_sig)

                    # 执行节点计算（使用缓存 processor 实例）
                    t1 = time.perf_counter_ns()
                    if node_id not in self._processor_cache:
                        node_cls = get_node_class(node_type) or get_node_class('PASSTHROUGH')
                        self._processor_cache[node_id] = node_cls()
                    processor = self._processor_cache[node_id]
                    context = NodeExecutionContext(
                        node_state=node_state,
                        sample_rate=self.sample_rate,
                        wall_time_ms=int(time.time() * 1000),
                    )

                    try:
                        node_outputs[node_id] = processor.compute(node, inputs, context) or {}
                    except Exception as exc:
                        logger.error('[GraphWorker] Node compute failed: %s(%s) -> %s', node_id, node_type, exc)
                        node_outputs[node_id] = {}
                    node_compute_total_ns += time.perf_counter_ns() - t1

                # SAVE 写入
                for save_node_id in self.spec.save_node_ids:
                    outputs = node_outputs.get(save_node_id, {})
                    sig = outputs.get('in') or outputs.get('out')
                    if not sig:
                        continue
                    channels = list(sig.get('channels', []))
                    if not channels:
                        continue
                    utc_ms = sig.get('utcFirstFrameMs')
                    if utc_ms is None:
                        utc_ms = int(time.time() * 1000)
                    write_sample(save_node_id, float(utc_ms), channels)

                # 输出节点事件
                for sink_id in self.spec.subscribed_sink_ids:
                    node = self.nodes_by_id.get(sink_id) or {}
                    node_type = str(node.get('type') or '').upper()
                    outputs = node_outputs.get(sink_id, {})
                    sig = outputs.get('in') or outputs.get('out')
                    if not sig:
                        continue
                    channels = list(sig.get('channels', []))
                    if not channels:
                        continue
                    names = list(sig.get('channelNames', []))
                    if not names:
                        names = default_channel_names(len(channels))
                    utc_ms = sig.get('utcFirstFrameMs')
                    if utc_ms is None:
                        utc_ms = int(time.time() * 1000)

                    self._put_event(
                        {
                            'nodeId': sink_id,
                            'nodeType': node_type,
                            'channels': channels,
                            'channelNames': names,
                            'sampleRate': self.sample_rate,
                            'utcFirstFrameMs': int(utc_ms),
                        }
                    )
                    event_samples += 1

            loop_total_us = int((time.perf_counter_ns() - loop_start) // 1000)
            perf.record_pipeline(PipelineMetrics(
                source_gen_us=int(source_gen_total_ns // 1000),
                node_compute_us=int(node_compute_total_ns // 1000),
                event_put_us=loop_total_us,
                total_pipeline_us=loop_total_us,
                samples_per_second=float(self.sample_rate),
            ))
            perf.add_samples(event_samples)


class GraphExecutionManager:
    def __init__(self) -> None:
        self.workers: Dict[str, GraphWorker] = {}
        self.signature: Optional[str] = None

    def stop_all(self) -> None:
        for worker in list(self.workers.values()):
            worker.stop()
        self.workers.clear()
        self.signature = None

    @staticmethod
    def _build_signature(graph: Dict[str, Any], subscribed_nodes: Set[str], save_nodes: Set[str]) -> str:
        key = {
            'nodes': graph.get('nodes', []),
            'edges': graph.get('edges', []),
            'subscribed': sorted(subscribed_nodes),
            'saveNodes': sorted(save_nodes),
        }
        return json.dumps(key, ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _required_nodes_for_sinks(edges: List[Dict[str, Any]], sink_ids: Set[str]) -> Set[str]:
        incoming: Dict[str, List[str]] = defaultdict(list)
        for edge in edges:
            src = edge.get('source')
            tgt = edge.get('target')
            if src and tgt:
                incoming[tgt].append(src)

        required = set(sink_ids)
        stack = list(sink_ids)
        while stack:
            node_id = stack.pop()
            for src in incoming.get(node_id, []):
                if src in required:
                    continue
                required.add(src)
                stack.append(src)
        return required

    @staticmethod
    def _build_components(node_ids: Set[str], edges: List[Dict[str, Any]]) -> List[Set[str]]:
        adjacency: Dict[str, Set[str]] = defaultdict(set)
        for edge in edges:
            src = edge.get('source')
            tgt = edge.get('target')
            if src in node_ids and tgt in node_ids:
                adjacency[src].add(tgt)
                adjacency[tgt].add(src)

        components: List[Set[str]] = []
        unvisited = set(node_ids)
        while unvisited:
            start = next(iter(unvisited))
            queue_nodes = [start]
            comp: Set[str] = set()
            while queue_nodes:
                cur = queue_nodes.pop(0)
                if cur in comp:
                    continue
                comp.add(cur)
                for nxt in adjacency.get(cur, set()):
                    if nxt not in comp:
                        queue_nodes.append(nxt)
            components.append(comp)
            unvisited -= comp
        return components

    def update(self, graph: Dict[str, Any], subscribed_nodes: Set[str], save_nodes: Set[str]) -> None:
        new_signature = self._build_signature(graph, subscribed_nodes, save_nodes)
        if new_signature == self.signature:
            return

        self.stop_all()

        nodes = graph.get('nodes', []) or []
        edges = graph.get('edges', []) or []
        nodes_by_id = {node.get('id'): node for node in nodes if node.get('id')}

        sink_ids = set(subscribed_nodes) | set(save_nodes)
        sink_ids = {sid for sid in sink_ids if sid in nodes_by_id}
        if not sink_ids:
            self.signature = new_signature
            return

        required_nodes = self._required_nodes_for_sinks(edges, sink_ids)
        required_nodes = {nid for nid in required_nodes if nid in nodes_by_id}
        if not required_nodes:
            self.signature = new_signature
            return

        relevant_edges = [
            edge
            for edge in edges
            if edge.get('source') in required_nodes and edge.get('target') in required_nodes
        ]

        components = self._build_components(required_nodes, relevant_edges)

        for idx, comp in enumerate(components):
            comp_edges = [
                edge
                for edge in relevant_edges
                if edge.get('source') in comp and edge.get('target') in comp
            ]
            comp_subscribed = {sid for sid in subscribed_nodes if sid in comp}
            comp_save = {sid for sid in save_nodes if sid in comp}
            if not comp_subscribed and not comp_save:
                continue
            spec = WorkerSpec(
                worker_id=f'component-{idx + 1}',
                node_ids=comp,
                edges=comp_edges,
                subscribed_sink_ids=comp_subscribed,
                save_node_ids=comp_save,
            )
            worker = GraphWorker(spec=spec, nodes_by_id=nodes_by_id)
            worker.start()
            self.workers[spec.worker_id] = worker

        self.signature = new_signature

    def poll_events(self, max_items_per_worker: int = 2000) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        for worker in self.workers.values():
            events.extend(worker.drain_events(max_items=max_items_per_worker))
        return events
