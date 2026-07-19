from __future__ import annotations
# pyright: reportMissingImports=false

import logging
logger = logging.getLogger(__name__)

import asyncio
import json
import time
from collections import deque
from typing import Dict, List, Optional, Set

import numpy as np
from channels.generic.websocket import AsyncWebsocketConsumer

from .graph_engine import GraphExecutionManager


class EegGraphConsumerV2(AsyncWebsocketConsumer):
    """Path-threaded graph consumer with UTC-ms packet timestamp support."""

    # 缓存 FFT 窗口，避免每次计算都重新生成
    _fft_window_cache: Dict[int, np.ndarray] = {}

    async def connect(self):
        await self.accept()
        self.subscribed_nodes: Set[str] = set()
        self.running = True
        self.graph_frozen = False

        self._save_nodes: List[str] = []
        self._replay_nodes: List[str] = []
        self._save_replay_signature: Optional[str] = None

        self._engine = GraphExecutionManager()
        self._sample_buffer: Dict[str, List[List[float]]] = {}
        self._sample_channel_names: Dict[str, List[str]] = {}
        self._sample_rates: Dict[str, int] = {}
        self._batch_first_utc: Dict[str, int] = {}

        self._spectrum_buffers_by_node: Dict[str, List[deque]] = {}

        # 追踪 stream_data task 以在 disconnect 时正确取消
        self._stream_task: Optional[asyncio.Task] = None

        from .graph_store import get_graph, get_runtime_state

        graph = get_graph()
        self.graph_frozen = bool(graph.get('frozen', False))

        self._sync_save_replay_nodes(graph)
        # 冻结已退出 UI：数据流由 running 驱动。只要图已运行即启动数据流任务，
        # 不再要求先 frozen（修复原“connect 时未 frozen 则永不启动数据流”的缺陷）。
        if get_runtime_state().get('running'):
            self._stream_task = asyncio.create_task(self.stream_data())

        logger.debug(f"[WebSocket] Client connected, graph running: {get_runtime_state().get('running')}")

    async def disconnect(self, code):
        self.running = False
        if self._stream_task and not self._stream_task.done():
            self._stream_task.cancel()
            try:
                await self._stream_task
            except asyncio.CancelledError:
                pass
            self._stream_task = None
        self._engine.stop_all()
        self._stop_all_save_replay()
        logger.debug(f"[WebSocket] Client disconnected, code: {code}")

    @staticmethod
    def _extract_fft_size(nodes):
        valid_sizes = {256, 512, 1024, 2048}
        for node in nodes:
            if str(node.get('type')).upper() != 'OUTPUT':
                continue
            params = node.get('params', {}) or {}
            raw = params.get('fftSize', params.get('fft_size', 512))
            try:
                size = int(raw)
            except Exception:
                continue
            if size in valid_sizes:
                return size
        return 512

    def _ensure_spectrum_buffers(self, node_id: str, channel_count: int, maxlen: int = 4096) -> None:
        channel_count = max(1, int(channel_count))
        existing = self._spectrum_buffers_by_node.get(node_id) or []
        if len(existing) != channel_count:
            existing = [deque(maxlen=maxlen) for _ in range(channel_count)]
            self._spectrum_buffers_by_node[node_id] = existing

    def _compute_spectrum_bundle(self, node_id: str, sample_rate: int, fft_size: int):
        if fft_size < 8:
            return None

        buffers = self._spectrum_buffers_by_node.get(node_id) or []
        if not buffers:
            return None

        min_len = min((len(ch) for ch in buffers), default=0)
        if min_len < fft_size:
            return None

        channel_frames = []
        for ch in buffers:
            arr = np.array(list(ch)[-fft_size:], dtype=np.float64)
            channel_frames.append(arr)

        data = np.stack(channel_frames, axis=0)
        if fft_size not in self._fft_window_cache:
            self._fft_window_cache[fft_size] = np.hamming(fft_size)
        window = self._fft_window_cache[fft_size]
        data = data * window

        fft = np.fft.rfft(data, axis=1)
        mags = np.abs(fft) / fft_size
        avg = np.mean(mags, axis=0)

        db = 20.0 * np.log10(np.maximum(avg, 1e-12))
        db_min = float(np.min(db))
        db_max = float(np.max(db))
        span = max(1e-6, db_max - db_min)
        norm_row = np.clip((db - db_min) / span, 0.0, 1.0)

        return {
            'fftSize': fft_size,
            'freqResolution': float(sample_rate / fft_size),
            'spectra': mags.tolist(),
            'spectrum': avg.tolist(),
            'spectrogramRow': norm_row.tolist(),
            'spectrogramDbMin': db_min,
            'spectrogramDbMax': db_max,
        }

    def _build_save_replay_signature(self, graph: Dict) -> str:
        nodes = graph.get('nodes', []) or []
        filtered = [
            {
                'id': n.get('id'),
                'type': n.get('type'),
                'params': n.get('params', {}),
            }
            for n in nodes
            if (
                str(n.get('type')).upper() in {'REPLAY'}
                or (
                    str(n.get('type')).upper() == 'OUTPUT'
                    and bool((n.get('params') or {}).get('saveEnabled', False))
                )
            )
        ]
        return json.dumps(filtered, ensure_ascii=False, sort_keys=True)

    def _sync_save_replay_nodes(self, graph: Dict) -> None:
        signature = self._build_save_replay_signature(graph)
        if signature == self._save_replay_signature:
            return

        self._stop_all_save_replay()
        self._save_replay_signature = signature

        from .data_recorder import start_recording
        from .data_replay import start_replay

        self._save_nodes = []
        self._replay_nodes = []

        nodes = graph.get('nodes', []) or []
        for node in nodes:
            node_type = str(node.get('type') or '').upper()
            params = node.get('params', {}) or {}
            node_id = node.get('id')
            if not node_id:
                continue

            if node_type == 'OUTPUT' and bool(params.get('saveEnabled', False)):
                filename = params.get('filename') or params.get('filePath')
                format_type = str(params.get('format', 'CSV')).upper()
                result = start_recording(node_id=node_id, filename=filename, format=format_type)
                if result.get('ok'):
                    self._save_nodes.append(node_id)
                    logger.debug(f"[WebSocket] SAVE node initialized: {node_id} -> {result.get('filepath')}")
                else:
                    logger.debug(f"[WebSocket] SAVE node failed: {node_id} - {result.get('error')}")

            is_replay_source = node_type == 'REPLAY'
            if is_replay_source:
                filename = params.get('file') or params.get('filePath')
                if isinstance(filename, list) and filename:
                    filename = filename[0]
                loop = bool(params.get('loop', False))
                if not filename:
                    continue
                result = start_replay(node_id=node_id, filename=filename, loop=loop)
                if result.get('ok'):
                    self._replay_nodes.append(node_id)
                    logger.debug(f"[WebSocket] REPLAY node initialized: {node_id} -> {result.get('filename')}")
                else:
                    logger.debug(f"[WebSocket] REPLAY node failed: {node_id} - {result.get('error')}")

    def _stop_all_save_replay(self):
        from .data_recorder import stop_recording
        from .data_replay import stop_replay

        for node_id in self._save_nodes:
            try:
                stop_recording(node_id)
            except Exception:
                pass

        for node_id in self._replay_nodes:
            try:
                stop_replay(node_id)
            except Exception:
                pass

        self._save_nodes = []
        self._replay_nodes = []

    async def receive(self, text_data):
        try:
            message = json.loads(text_data)
            msg_type = message.get('type')

            if msg_type == 'subscribe':
                node_ids = message.get('nodeIds', [])
                self.subscribed_nodes.update(str(node_id) for node_id in node_ids)
                logger.debug(f"[WebSocket] Subscribed to nodes: {node_ids}")
                # 兜底：客户端先连接、后 run 时（connect 未启动 task），subscribe 时补启动数据流
                if self._stream_task is None or self._stream_task.done():
                    from .graph_store import get_runtime_state
                    if get_runtime_state().get('running'):
                        self._stream_task = asyncio.create_task(self.stream_data())
                        logger.debug("[WebSocket] stream_data started on subscribe (running)")

            elif msg_type == 'unsubscribe':
                node_ids = message.get('nodeIds', [])
                if node_ids:
                    for nid in node_ids:
                        self.subscribed_nodes.discard(str(nid))
                    logger.debug(f"[WebSocket] Unsubscribed from nodes: {node_ids}, remaining: {list(self.subscribed_nodes)}")
                else:
                    self.subscribed_nodes.clear()
                    logger.debug("[WebSocket] Unsubscribed from all nodes")

            elif msg_type == 'ping':
                await self.send(text_data=json.dumps({'type': 'pong'}))

            elif msg_type == 'get_recordings':
                from .data_recorder import get_active_recordings

                await self.send(text_data=json.dumps({'type': 'recordings', 'recordings': get_active_recordings()}))

            elif msg_type == 'get_saved_files':
                from .data_recorder import list_saved_files

                await self.send(text_data=json.dumps({'type': 'saved_files', 'files': list_saved_files()}))

        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({'type': 'error', 'error': 'Invalid JSON'}))
        except Exception as e:
            await self.send(text_data=json.dumps({'type': 'error', 'error': str(e)}))

    async def stream_data(self):
        from .graph_store import (
            get_graph, get_runtime_state, set_runtime_metrics,
            get_control_revision,
        )
        from .data_replay import get_replay_status

        # 订阅消息与 stream_data 并发执行，首个 tick 延迟 100ms 确保 subscribe 已处理。
        await asyncio.sleep(0.1)

        # 缓存的控制状态 — 仅在 control_revision 变化时重读
        last_control_rev = -1
        cached_graph: Dict = {}
        cached_frozen = False
        cached_running = False
        cached_runtime_mode = 'live'
        cached_node_type_map: Dict[str, str] = {}
        cached_fft_size = 512
        while self.running:
            # --- 控制状态检查：仅比较修订号，O(1) ---
            control_rev = get_control_revision()
            if control_rev != last_control_rev:
                last_control_rev = control_rev
                cached_graph = get_graph()
                cached_frozen = bool(cached_graph.get('frozen', False))
                self.graph_frozen = cached_frozen
                self._sync_save_replay_nodes(cached_graph)
                rt = get_runtime_state()
                cached_running = bool(rt.get('running', False))
                cached_runtime_mode = str(rt.get('mode') or 'live').lower()
                nodes = cached_graph.get('nodes', []) or []
                cached_node_type_map = {
                    str(n.get('id')): str(n.get('type') or '').upper()
                    for n in nodes if n.get('id')
                }
                cached_fft_size = self._extract_fft_size(nodes)

            # --- 流转条件：仅由 running 驱动（frozen 已退出 UI，不再作为流转前提） ---
            if not cached_running:
                self._engine.stop_all()
                self._sample_buffer.clear()
                self._sample_channel_names.clear()
                self._sample_rates.clear()
                self._batch_first_utc.clear()
                await asyncio.sleep(0.1)
                continue

            nodes = cached_graph.get('nodes', []) or []
            node_type_map = cached_node_type_map

            subscribed_output_nodes = {
                node_id
                for node_id in self.subscribed_nodes
                if node_type_map.get(node_id) == 'OUTPUT'
            }
            save_nodes = set(self._save_nodes)

            self._engine.update(cached_graph, subscribed_output_nodes, save_nodes)

            events = self._engine.poll_events(max_items_per_worker=1000)
            max_processing_delay_ms = 0
            now_ms_for_events = int(time.time() * 1000)
            for event in events:
                node_id = str(event.get('nodeId') or '')
                if not node_id:
                    continue
                channels = list(event.get('channels', []))
                if not channels:
                    continue
                names = [str(v) for v in event.get('channelNames', [])]
                sample_rate = int(event.get('sampleRate') or 1000)
                utc_ms = int(event.get('utcFirstFrameMs') or now_ms_for_events)
                # 真实管道延迟：从数据到达串口/生成到当前处理时刻
                real_delay_ms = max(0, now_ms_for_events - utc_ms)
                if real_delay_ms > max_processing_delay_ms:
                    max_processing_delay_ms = real_delay_ms

                self._sample_buffer.setdefault(node_id, []).append(channels)
                self._sample_channel_names[node_id] = names
                self._sample_rates[node_id] = sample_rate
                self._batch_first_utc.setdefault(node_id, utc_ms)

                if node_type_map.get(node_id) == 'OUTPUT':
                    self._ensure_spectrum_buffers(node_id, len(channels))
                    for ch_idx, val in enumerate(channels):
                        self._spectrum_buffers_by_node[node_id][ch_idx].append(float(val))

            t_send_start = time.perf_counter_ns()
            fft_size = cached_fft_size

            for node_id, samples in list(self._sample_buffer.items()):
                if not samples:
                    continue
                latest_channels = samples[-1]
                node_type = node_type_map.get(node_id)
                # 按节点计算真实管道延迟
                node_utc = int(self._batch_first_utc.get(node_id, int(time.time() * 1000)))
                node_delay_ms = max(0, int(time.time() * 1000) - node_utc)

                payload = {
                    'type': 'data',
                    'timestamp': int(time.time() * 1000),
                    'utcFirstFrameMs': node_utc,
                    'nodeId': node_id,
                    'nodeType': node_type,
                    'channels': latest_channels,
                    'samples': samples,
                    'channelNames': self._sample_channel_names.get(node_id, []),
                    'sampleRate': int(self._sample_rates.get(node_id, 1000)),
                    'processingDelayMs': int(node_delay_ms),
                    'runtimeMode': cached_runtime_mode,
                    'nonRealtime': bool(node_delay_ms > 10000),
                    'performanceWarning': '非实时：处理延迟持续升高' if node_delay_ms > 10000 else None,
                }
                if len(samples) <= 2:
                    logger.debug(f"[WebSocket] SEND nodeId={node_id} channels={len(latest_channels)} names={self._sample_channel_names.get(node_id, [])[:3]} samples={len(samples)}")

                if node_type == 'OUTPUT':
                    bundle = self._compute_spectrum_bundle(node_id=node_id, sample_rate=int(self._sample_rates.get(node_id, 1000)), fft_size=fft_size)
                    if bundle is not None:
                        payload.update(bundle)

                try:
                    await self.send(text_data=json.dumps(payload))
                except Exception as exc:
                    logger.warning("[WebSocket] Send error for node %s: %s", node_id, exc)
                    self.running = False
                    break

            ws_send_us = int((time.perf_counter_ns() - t_send_start) // 1000)

            from .perf_monitor import get_perf_monitor, PipelineMetrics
            perf = get_perf_monitor()
            perf.record_pipeline(PipelineMetrics(
                ws_send_us=ws_send_us,
                total_pipeline_us=ws_send_us,
            ))

            self._sample_buffer.clear()
            self._sample_channel_names.clear()
            self._sample_rates.clear()
            self._batch_first_utc.clear()

            progress = None
            if cached_runtime_mode == 'offline' and self._replay_nodes:
                progresses = []
                for replay_node_id in self._replay_nodes:
                    status = get_replay_status(replay_node_id)
                    if not status:
                        continue
                    try:
                        progresses.append(float(status.get('progress', 0)))
                    except Exception:
                        pass
                if progresses:
                    progress = sum(progresses) / len(progresses)
                else:
                    progress = 100.0

            set_runtime_metrics(
                processing_delay_ms=max_processing_delay_ms,
                progress=progress,
                non_realtime=max_processing_delay_ms > 10000,
                warning='非实时：处理延迟持续升高' if max_processing_delay_ms > 10000 else None,
            )

            await asyncio.sleep(0.005)
