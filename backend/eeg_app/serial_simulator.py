"""Wearable EEG serial simulator for debug and regression tests.

Simulates the real device frame format:
- Frame header: 0xA5 0x5A 0x01
- Payload: 8 x int32 little-endian
- Frame tail: CRLF

The simulator listens for init commands (C005/C002) and starts streaming after
receiving them, mirroring the trusted wearable_eeg_utils script behavior.
"""

from __future__ import annotations

import math
import os
import pty
import random
import struct
import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class SimulatorStatus:
    port: str
    sample_rate: int
    channels: int
    running: bool
    streaming: bool
    frames_sent: int


class WearableSerialSimulator:
    def __init__(self, sample_rate: int = 1000, channels: int = 8):
        if channels <= 0:
            raise ValueError('channels must be > 0')
        self.sample_rate = max(1, int(sample_rate))
        self.channels = int(channels)

        self.master_fd: Optional[int] = None
        self.slave_fd: Optional[int] = None
        self.slave_name: Optional[str] = None

        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._streaming_enabled = False
        self._frames_sent = 0

        self._cmd_buffer = b''
        self._c005_count = 0
        self._c002_count = 0

    def start(self) -> str:
        if self._thread and self._thread.is_alive() and self.slave_name:
            return self.slave_name

        self.master_fd, self.slave_fd = pty.openpty()
        self.slave_name = os.ttyname(self.slave_fd)
        os.set_blocking(self.master_fd, False)

        self._stop.clear()
        self._streaming_enabled = False
        self._frames_sent = 0
        self._cmd_buffer = b''
        self._c005_count = 0
        self._c002_count = 0

        self._thread = threading.Thread(target=self._run, name='wearable-serial-sim', daemon=True)
        self._thread.start()
        return self.slave_name

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)

        for fd in (self.master_fd, self.slave_fd):
            if fd is not None:
                try:
                    os.close(fd)
                except Exception:
                    pass

        self.master_fd = None
        self.slave_fd = None
        self.slave_name = None

    def status(self) -> SimulatorStatus:
        return SimulatorStatus(
            port=self.slave_name or '',
            sample_rate=self.sample_rate,
            channels=self.channels,
            running=bool(self._thread and self._thread.is_alive()),
            streaming=self._streaming_enabled,
            frames_sent=self._frames_sent,
        )

    def _read_commands(self) -> None:
        if self.master_fd is None:
            return
        try:
            chunk = os.read(self.master_fd, 4096)
        except BlockingIOError:
            return
        except Exception:
            return

        if not chunk:
            return

        self._cmd_buffer += chunk
        while b'\r\n' in self._cmd_buffer:
            line, self._cmd_buffer = self._cmd_buffer.split(b'\r\n', 1)
            text = line.decode('ascii', errors='ignore').strip().upper()
            if text == 'C005':
                self._c005_count += 1
            elif text == 'C002':
                self._c002_count += 1

        # Match real init order loosely: multiple C005 then C002
        if self._c005_count >= 1 and self._c002_count >= 1:
            self._streaming_enabled = True

    def _build_channels(self, t: float):
        values = []
        for ch in range(self.channels):
            base_freq = 8.0 + ch * 0.7
            harmonic = 0.35 * math.sin(2 * math.pi * (base_freq * 2.0) * t + ch * 0.3)
            signal = math.sin(2 * math.pi * base_freq * t + ch * 0.2) + harmonic
            noise = random.uniform(-0.03, 0.03)
            uv = (signal + noise) * 120.0
            # Keep int32-scale values aligned with existing parsing path.
            values.append(int(uv * 1000.0))
        return values

    def _write_frame(self, channels) -> None:
        if self.master_fd is None:
            return
        values = list(channels[:8])
        if len(values) < 8:
            values.extend([0] * (8 - len(values)))
        payload = struct.pack('<8i', *values)
        frame = b'\xa5Z\x01' + payload + b'\r\n'
        try:
            os.write(self.master_fd, frame)
            self._frames_sent += 1
        except Exception:
            pass

    def _run(self) -> None:
        next_frame_ts = time.perf_counter()
        dt = 1.0 / float(self.sample_rate)
        t = 0.0

        while not self._stop.is_set():
            self._read_commands()

            if not self._streaming_enabled:
                time.sleep(0.002)
                continue

            now = time.perf_counter()
            if now < next_frame_ts:
                time.sleep(min(0.001, next_frame_ts - now))
                continue

            # Catch-up loop avoids drift under scheduler jitter.
            while now >= next_frame_ts and not self._stop.is_set():
                channels = self._build_channels(t)
                self._write_frame(channels)
                t += dt
                next_frame_ts += dt
                now = time.perf_counter()


_simulators: Dict[str, WearableSerialSimulator] = {}
_sim_lock = threading.RLock()


def start_wearable_serial_simulator(sample_rate: int = 1000, channels: int = 8) -> SimulatorStatus:
    with _sim_lock:
        sim = WearableSerialSimulator(sample_rate=sample_rate, channels=channels)
        port = sim.start()
        _simulators[port] = sim
        return sim.status()


def stop_wearable_serial_simulator(port: str) -> bool:
    with _sim_lock:
        sim = _simulators.pop(port, None)
        if not sim:
            return False
        sim.stop()
        return True


def list_wearable_serial_simulators() -> Dict[str, SimulatorStatus]:
    with _sim_lock:
        return {port: sim.status() for port, sim in _simulators.items()}
