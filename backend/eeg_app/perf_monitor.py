"""性能监控模块 — 追踪数据管道各阶段耗时和系统资源"""

import os
import time
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional

try:
    import psutil

    _PSUTIL_AVAILABLE = True
except ImportError:
    _PSUTIL_AVAILABLE = False


@dataclass
class PipelineMetrics:
    """单次数据管道的耗时快照"""
    source_gen_us: int = 0
    node_compute_us: int = 0
    event_put_us: int = 0
    ws_send_us: int = 0
    total_pipeline_us: int = 0
    samples_per_second: float = 0.0


class PerfMonitor:
    """全局性能监控器（线程安全）"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pipeline_history: deque = deque(maxlen=100)
        self._latest: Optional[PipelineMetrics] = None
        self._total_samples: int = 0
        self._start_time: float = time.time()

    def record_pipeline(self, metrics: PipelineMetrics) -> None:
        with self._lock:
            self._latest = metrics
            self._pipeline_history.append(metrics)
            self._total_samples += 1

    def add_samples(self, count: int) -> None:
        with self._lock:
            self._total_samples += count

    def snapshot(self) -> Dict:
        with self._lock:
            latest = self._latest
            elapsed = max(time.time() - self._start_time, 0.001)

            avg_source = 0
            avg_node = 0
            avg_ws = 0
            avg_total = 0
            if self._pipeline_history:
                count = len(self._pipeline_history)
                avg_source = sum(m.source_gen_us for m in self._pipeline_history) // count
                avg_node = sum(m.node_compute_us for m in self._pipeline_history) // count
                avg_ws = sum(m.ws_send_us for m in self._pipeline_history) // count
                avg_total = sum(m.total_pipeline_us for m in self._pipeline_history) // count

            system = _collect_system_metrics()

            return {
                'pipeline': {
                    'latest': {
                        'sourceGenUs': latest.source_gen_us if latest else 0,
                        'nodeComputeUs': latest.node_compute_us if latest else 0,
                        'wsSendUs': latest.ws_send_us if latest else 0,
                        'totalUs': latest.total_pipeline_us if latest else 0,
                    },
                    'average': {
                        'sourceGenUs': avg_source,
                        'nodeComputeUs': avg_node,
                        'wsSendUs': avg_ws,
                        'totalUs': avg_total,
                    },
                    'samplesPerSecond': round(self._total_samples / elapsed, 1),
                    'totalSamples': self._total_samples,
                },
                'system': system,
            }


_monitor: Optional[PerfMonitor] = None
_monitor_lock = threading.Lock()


def get_perf_monitor() -> PerfMonitor:
    global _monitor
    with _monitor_lock:
        if _monitor is None:
            _monitor = PerfMonitor()
        return _monitor


def _collect_system_metrics() -> Dict:
    result: Dict = {}

    # CPU / memory via psutil
    if _PSUTIL_AVAILABLE:
        try:
            result['cpuPercent'] = round(psutil.cpu_percent(interval=0), 1)
            mem = psutil.virtual_memory()
            result['memoryUsedMb'] = round(mem.used / (1024 * 1024), 1)
            result['memoryTotalMb'] = round(mem.total / (1024 * 1024), 1)
            result['memoryPercent'] = mem.percent
            disk = psutil.disk_usage('/')
            result['diskUsedGb'] = round(disk.used / (1024 * 1024 * 1024), 1)
            result['diskTotalGb'] = round(disk.total / (1024 * 1024 * 1024), 1)
            result['diskPercent'] = disk.percent
            result['processMemoryMb'] = round(
                psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024), 1
            )
            result['threadCount'] = psutil.Process(os.getpid()).num_threads()
        except Exception:
            pass

    # 磁盘 IO 统计（Linux）
    if not result.get('diskUsedGb'):
        try:
            stat = os.statvfs('/')
            total = (stat.f_frsize * stat.f_blocks) / (1024 * 1024 * 1024)
            free = (stat.f_frsize * stat.f_bavail) / (1024 * 1024 * 1024)
            used = total - free
            result['diskUsedGb'] = round(used, 1)
            result['diskTotalGb'] = round(total, 1)
            result['diskPercent'] = round(used / max(total, 0.001) * 100, 1)
        except Exception:
            pass

    return result
