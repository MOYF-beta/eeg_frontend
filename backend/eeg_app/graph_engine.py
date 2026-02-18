from __future__ import annotations

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

    @property
    def node_ids(self) -> Set[str]:
        return set(self.nodes_by_id.keys())

    def _resolve_sample_rate(self) -> int:
        for node_id in self.source_node_ids:
            node = self.nodes_by_id.get(node_id) or {}
            params = node.get('params') or {}
            try:
                value = int(params.get('sampleRate', 1000))
            except Exception:
                value = 1000
            if value > 0:
                return value
        return 1000

    def _source_mode(self, node_id: str, node_type: str) -> str:
        if node_type == 'REPLAY':
            return 'replay'
        node = self.nodes_by_id.get(node_id) or {}
        params = node.get('params') or {}
        mode = str(params.get('sourceMode') or 'live').lower()
        return 'replay' if mode == 'replay' else 'live'

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
            order.extend(sorted(unresolved))
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
            # 防止阻塞，队列满时丢弃最旧的数据并重试一次
            try:
                _ = self.event_queue.get_nowait()
                self.event_queue.put_nowait(event)
            except Exception:
                pass

    def _generate_source_channels(self, node_id: str) -> Tuple[List[float], int]:
        node = self.nodes_by_id.get(node_id) or {}
        params = node.get('params') or {}
        channels_count = 8
        try:
            channels_count = max(1, int(params.get('channels', 8)))
        except Exception:
            channels_count = 8

        state = self.node_states[node_id]
        t = float(state.get('t', 0.0))
        dt = 1.0 / max(1, self.sample_rate)

        channels: List[float] = []
        for i in range(channels_count):
            # 清晰的方波信号，不同通道有不同频率
            freq = 5 + i * 0.5  # 5-8.5Hz，易于观察
            square = 1 if math.sin(2 * math.pi * freq * t) > 0 else -1
            square_signal = square * 100  # 增加方波幅度
            
            # 减少高频噪声，让方波更明显
            high_freq1 = 50 + i * 10
            high_freq2 = 120 + i * 5
            noise = math.sin(2 * math.pi * high_freq1 * t) * 5 + math.sin(2 * math.pi * high_freq2 * t) * 3  # 减少噪声幅度
            
            # 减少随机噪声
            random_noise = random.uniform(-2, 2)
            
            channels.append(square_signal + noise + random_noise)

        state['t'] = t + dt
        utc_ms = int(time.time() * 1000)
        return channels, utc_ms

    def _read_replay_channels(self, node_id: str) -> Tuple[List[float], Optional[int]]:
        from .data_replay import is_replaying, read_next_sample

        if not is_replaying(node_id):
            return [], None
        sample = read_next_sample(node_id)
        if not sample:
            return [], None
        return list(sample.get('channels', [])), int(sample.get('timestamp', time.time() * 1000))

    def _resolve_source_signal(self, node_id: str, node_type: str) -> Tuple[List[float], Optional[int]]:
        mode = self._source_mode(node_id, node_type)
        if mode == 'replay':
            return self._read_replay_channels(node_id)
        return self._generate_source_channels(node_id)

    def _pick_source_output(self, outputs: Dict[str, Dict[str, Any]], preferred_port: str) -> Dict[str, Any]:
        if preferred_port in outputs:
            return outputs[preferred_port]
        if outputs:
            return next(iter(outputs.values()))
        return {'channels': [], 'channelNames': [], 'utcFirstFrameMs': None}

    def _run(self) -> None:
        from .data_recorder import write_sample

        dt = 1.0 / max(1, self.sample_rate)
        max_samples_per_loop = max(1, int(self.sample_rate * 0.2))
        last_sample_time = time.perf_counter()
        sample_accumulator = 0.0

        while not self.stop_event.is_set():
            now = time.perf_counter()
            elapsed_samples = (now - last_sample_time) * self.sample_rate
            last_sample_time = now
            sample_accumulator += elapsed_samples

            samples_to_generate = int(sample_accumulator)
            if samples_to_generate <= 0:
                time.sleep(0.001)
                continue

            if samples_to_generate > max_samples_per_loop:
                samples_to_generate = max_samples_per_loop
                sample_accumulator = 0.0
            else:
                sample_accumulator -= samples_to_generate

            for _ in range(samples_to_generate):
                self.generated_sample_count += 1
                expected_wall_ms = self.started_wall_ms + int((self.generated_sample_count * 1000) / max(1, self.sample_rate))
                now_wall_ms = int(time.time() * 1000)
                processing_delay_ms = max(0, now_wall_ms - expected_wall_ms)
                node_outputs: Dict[str, Dict[str, Dict[str, Any]]] = {}

                for node_id in self.topo_order:
                    node = self.nodes_by_id.get(node_id)
                    if not node:
                        continue
                    node_type = str(node.get('type') or '').upper()
                    node_state = self.node_states[node_id]

                    if node_type in {'SOURCE', 'REPLAY'}:
                        generated_channels, generated_utc = self._resolve_source_signal(node_id, node_type)
                        node_state['generatedChannels'] = generated_channels
                        node_state['generatedUtcMs'] = generated_utc

                    inputs: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
                    for edge in self.incoming_by_target.get(node_id, []):
                        src = edge.get('source')
                        if src not in node_outputs:
                            continue
                        src_port = edge.get('sourcePort') or 'out'
                        tgt_port = edge.get('targetPort') or 'in'
                        src_sig = self._pick_source_output(node_outputs[src], src_port)
                        inputs[tgt_port].append(src_sig)

                    node_cls = get_node_class(node_type) or get_node_class('PASSTHROUGH')
                    processor = node_cls()
                    context = NodeExecutionContext(
                        node_state=node_state,
                        sample_rate=self.sample_rate,
                        wall_time_ms=int(time.time() * 1000),
                    )

                    try:
                        node_outputs[node_id] = processor.compute(node, inputs, context) or {}
                    except Exception as exc:
                        print(f'[GraphWorker] Node compute failed: {node_id}({node_type}) -> {exc}')
                        node_outputs[node_id] = {}

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
                            'processingDelayMs': processing_delay_ms,
                        }
                    )

            time.sleep(min(0.001, dt / 2))


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
