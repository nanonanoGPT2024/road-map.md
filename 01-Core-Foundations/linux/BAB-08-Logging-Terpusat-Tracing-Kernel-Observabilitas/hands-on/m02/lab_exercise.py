#!/usr/bin/env python3
"""
Lab Hands-on: Observabilitas Kernel, Tracing (eBPF), dan Logging Terpusat
Kategori: 01-Core-Foundations | Bab 08: Modul 02 Deep Dive

Deskripsi:
Script ini memodelkan arsitektur observabilitas modern berbasis eBPF:
1. In-Kernel Virtual Machine & Bytecode Verifier (Simulasi).
2. BPF Maps (BPF_MAP_TYPE_HASH & BPF_MAP_TYPE_RINGBUF) untuk transfer data kernel-to-userspace.
3. Kprobe/Tracepoint hooks yang mencegat syscall (`sys_enter_openat`, `sys_enter_connect`, `sys_enter_execve`).
4. Userspace Daemon / Centralized Log Collector yang melakukan poller loop,
   agregasi metrik latensi, dan ekspor log terstruktur (JSON).
"""

import sys
import time
import json
import random
import threading
from collections import deque, defaultdict
from dataclasses import dataclass, asdict
from typing import Dict, List, Any, Optional

# --- ANSI Formatting Constants ---
CLR_RST = "\033[0m"
CLR_BLD = "\033[1m"
CLR_RED = "\033[31m"
CLR_GRN = "\033[32m"
CLR_YLW = "\033[33m"
CLR_BLU = "\033[34m"
CLR_CYN = "\033[36m"
CLR_MAG = "\033[35m"
CLR_GRY = "\033[90m"


@dataclass
class SyscallEvent:
    """Representasi payload raw context dari kernel kprobe/tracepoint."""
    timestamp_ns: int
    pid: int
    tgid: int
    comm: str
    syscall_id: int
    syscall_name: str
    args: Dict[str, Any]
    duration_ns: int
    ret_code: int


class BPFMap:
    """
    Simulasi BPF Map:
    - BPF_MAP_TYPE_HASH: Key-value storage di kernel space.
    - BPF_MAP_TYPE_RINGBUF: Lockless circular ring buffer untuk high-throughput telemetry.
    """
    def __init__(self, map_name: str, map_type: str, max_entries: int = 1024):
        self.name = map_name
        self.map_type = map_type
        self.max_entries = max_entries
        self._lock = threading.Lock()
        self._storage: Dict[Any, Any] = {}
        self._ringbuffer: deque = deque(maxlen=max_entries)

    def update_hash(self, key: Any, value: Any) -> bool:
        """Atomic update untuk BPF_MAP_TYPE_HASH."""
        with self._lock:
            if len(self._storage) >= self.max_entries and key not in self._storage:
                return False  # -ENOSPC
            self._storage[key] = value
            return True

    def lookup_hash(self, key: Any) -> Optional[Any]:
        with self._lock:
            return self._storage.get(key, None)

    def dump_hash(self) -> Dict[Any, Any]:
        with self._lock:
            return dict(self._storage)

    def submit_ringbuf(self, event: SyscallEvent) -> bool:
        """Kirim event ke userspace via BPF_MAP_TYPE_RINGBUF."""
        with self._lock:
            if len(self._ringbuffer) >= self.max_entries:
                return False  # Buffer full / dropped
            self._ringbuffer.append(event)
            return True

    def poll_ringbuf(self) -> Optional[SyscallEvent]:
        with self._lock:
            if self._ringbuffer:
                return self._ringbuffer.popleft()
            return None


class BPFVerifier:
    """
    Simulasi eBPF Bytecode Verifier:
    Memeriksa safety guarantee (no unbounded loops, valid memory dereference, bounded instructions).
    """
    @staticmethod
    def verify(instructions_count: int, has_infinite_loop: bool, writes_outside_stack: bool) -> bool:
        print(f"{CLR_GRY}[KERNEL:VERIFIER] Melakukan static analysis bytecode...{CLR_RST}")
        time.sleep(0.1)
        if has_infinite_loop:
            print(f"{CLR_RED}[KERNEL:VERIFIER] REJECTED: Program memiliki unbounded loop!{CLR_RST}")
            return False
        if writes_outside_stack:
            print(f"{CLR_RED}[KERNEL:VERIFIER] REJECTED: Upaya memory access di luar R10 (BFP stack pointer)!{CLR_RST}")
            return False
        if instructions_count > 4096:
            print(f"{CLR_RED}[KERNEL:VERIFIER] REJECTED: Instruction limit exceeded ({instructions_count} > 4096)!{CLR_RST}")
            return False
        print(f"{CLR_GRN}[KERNEL:VERIFIER] PASSED: JIT compilation successful. Program loaded.{CLR_RST}")
        return True


class KernelTraceHookEngine:
    """
    Simulasi Kernel Space:
    Memicu system calls, mengeksekusi program eBPF in-kernel,
    dan memfilter tracing data.
    """
    def __init__(self, ringbuf: BPFMap, stats_map: BPFMap):
        self.ringbuf = ringbuf
        self.stats_map = stats_map
        self.running = False
        self._thread: Optional[threading.Thread] = None

    def _ebpf_filter_prog(self, event: SyscallEvent) -> bool:
        """
        Simulasi eBPF C Hook:
        filter() {
            // Hanya tangkap proses non-idle, dan syscall dengan durasi > 10us atau execve/connect
            if (event->pid == 0) return 0;
            return 1;
        }
        """
        if event.pid == 0:
            return False
        return True

    def _ebpf_collector_prog(self, event: SyscallEvent):
        """In-kernel logic: update hash map metric dan submit ke ringbuffer."""
        # 1. Update latency metrics di BPF Map
        current = self.stats_map.lookup_hash(event.syscall_name) or {"count": 0, "total_ns": 0}
        current["count"] += 1
        current["total_ns"] += event.duration_ns
        self.stats_map.update_hash(event.syscall_name, current)

        # 2. Forward ke Ring Buffer jika lolos filter
        self.ringbuf.submit_ringbuf(event)

    def _kernel_worker(self):
        sample_procs = ["nginx", "dockerd", "python3", "postgres", "redis-server", "curl"]
        syscalls = [
            (1, "sys_enter_write", lambda: {"fd": 1, "bytes": random.randint(32, 4096)}),
            (2, "sys_enter_openat", lambda: {"path": "/etc/ssl/certs/ca.pem", "flags": 0}),
            (42, "sys_enter_connect", lambda: {"ip": f"10.0.0.{random.randint(1, 254)}", "port": 443}),
            (59, "sys_enter_execve", lambda: {"binary": "/usr/bin/bash", "argc": 2}),
        ]

        while self.running:
            pid = random.randint(1000, 9999)
            tgid = pid
            comm = random.choice(sample_procs)
            sc_id, sc_name, args_gen = random.choice(syscalls)
            duration = random.randint(5_000, 2_500_000)  # 5us s.d 2.5ms
            ret = 0 if random.random() > 0.05 else -13  # -EACCES

            event = SyscallEvent(
                timestamp_ns=time.time_ns(),
                pid=pid,
                tgid=tgid,
                comm=comm,
                syscall_id=sc_id,
                syscall_name=sc_name,
                args=args_gen(),
                duration_ns=duration,
                ret_code=ret
            )

            # Invoke in-kernel eBPF handler
            if self._ebpf_filter_prog(event):
                self._ebpf_collector_prog(event)

            time.sleep(random.uniform(0.02, 0.08))

    def start(self):
        self.running = True
        self._thread = threading.Thread(target=self._kernel_worker, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False
        if self._thread:
            self._thread.join()


class CentralizedLogAggregator:
    """
    Userspace Daemon:
    1. Polling data dari BPF RingBuffer (libbpf-style consumer).
    2. Format ingestion pipeline: Enrichment, filtering, dan structured JSON logging.
    """
    def __init__(self, ringbuf: BPFMap, stats_map: BPFMap):
        self.ringbuf = ringbuf
        self.stats_map = stats_map
        self.collected_logs: List[str] = []

    def consume_stream(self, max_records: int = 15):
        print(f"\n{CLR_BLD}{CLR_CYN}=== REAL-TIME TRACE DUMP (RING BUFFER EVENT STREAM) ==={CLR_RST}")
        print(f"{CLR_BLD}{'TIME':<12} | {'PID':<6} | {'COMM':<14} | {'SYSCALL':<18} | {'LATENCY (us)':<12} | {'RET'}{CLR_RST}")
        print("-" * 75)

        processed = 0
        while processed < max_records:
            event = self.ringbuf.poll_ringbuf()
            if not event:
                time.sleep(0.05)
                continue

            processed += 1
            lat_us = f"{event.duration_ns / 1_000:.2f}"
            ret_color = CLR_GRN if event.ret_code == 0 else CLR_RED
            ts_sec = time.strftime("%H:%M:%S", time.localtime(event.timestamp_ns / 1e9))

            print(f"{ts_sec:<12} | {event.pid:<6} | {event.comm:<14} | {CLR_BLU}{event.syscall_name:<18}{CLR_RST} | {lat_us:<12} | {ret_color}{event.ret_code}{CLR_RST}")

            # Structured Log Aggregation (Centralized logging format / Fluentd / Logstash)
            structured_payload = {
                "source": "ebpf_kernel_tracer",
                "ts": event.timestamp_ns,
                "process": {"pid": event.pid, "comm": event.comm},
                "audit": {
                    "syscall": event.syscall_name,
                    "args": event.args,
                    "duration_us": event.duration_ns / 1000,
                    "status": "SUCCESS" if event.ret_code == 0 else "FAIL"
                }
            }
            self.collected_logs.append(json.dumps(structured_payload))

    def display_kernel_map_metrics(self):
        """Membaca isi BPF_MAP_TYPE_HASH langsung dari kernel telemetry."""
        print(f"\n{CLR_BLD}{CLR_YLW}=== BPF HASH MAP AGGREGATE SUMMARY (In-Kernel Accumulator) ==={CLR_RST}")
        stats = self.stats_map.dump_hash()
        print(f"{'SYSCALL':<22} | {'TOTAL CALLS':<14} | {'AVG LATENCY (us)':<16}")
        print("-" * 56)
        for syscall_name, data in stats.items():
            avg_us = (data["total_ns"] / data["count"]) / 1_000 if data["count"] > 0 else 0
            print(f"{syscall_name:<22} | {data['count']:<14} | {avg_us:<16.2f}")


def main():
    print(f"{CLR_BLD}{CLR_MAG}======================================================================{CLR_RST}")
    print(f"{CLR_BLD}{CLR_MAG} LAB: eBPF Kernel Tracing Engine & Centralized Logging Pipeline       {CLR_RST}")
    print(f"{CLR_BLD}{CLR_MAG} Modul 02: Kernel Probes, Ring Buffers, and Telemetry Aggregation    {CLR_RST}")
    print(f"{CLR_BLD}{CLR_MAG}======================================================================{CLR_RST}\n")

    # Step 1: Bytecode Verification
    print(f"{CLR_BLD}[STEP 1] Validasi eBPF Bytecode via In-Kernel Verifier{CLR_RST}")
    is_safe = BPFVerifier.verify(instructions_count=214, has_infinite_loop=False, writes_outside_stack=False)
    if not is_safe:
        sys.exit(1)

    # Step 2: Initialize BPF Maps
    print(f"\n{CLR_BLD}[STEP 2] Inisialisasi BPF Maps (Storage & Circular Buffer){CLR_RST}")
    ringbuf_map = BPFMap(map_name="events_ringbuf", map_type="BPF_MAP_TYPE_RINGBUF", max_entries=256)
    stats_map = BPFMap(map_name="syscall_stats", map_type="BPF_MAP_TYPE_HASH", max_entries=64)
    print(f"{CLR_GRN}[INFO] Allocating 'events_ringbuf' (type: RINGBUF, entries: 256) -> OK{CLR_RST}")
    print(f"{CLR_GRN}[INFO] Allocating 'syscall_stats' (type: HASH, entries: 64) -> OK{CLR_RST}")

    # Step 3: Attach hooks & Start Kernel Tracer
    print(f"\n{CLR_BLD}[STEP 3] Memasang Tracepoints & Mengaktifkan Kernel Tracing{CLR_RST}")
    engine = KernelTraceHookEngine(ringbuf=ringbuf_map, stats_map=stats_map)
    engine.start()
    print(f"{CLR_CYN}[INFO] Hooks terpasang pada tracepoints: sys_enter_openat, sys_enter_connect, sys_enter_execve{CLR_RST}")
    print(f"{CLR_CYN}[INFO] Kernel thread mulai memproses event ke ring buffer...{CLR_RST}")

    # Step 4: Userspace Daemon consumes telemetry
    aggregator = CentralizedLogAggregator(ringbuf=ringbuf_map, stats_map=stats_map)
    aggregator.consume_stream(max_records=12)

    # Step 5: Read In-Kernel Map Counters
    aggregator.display_kernel_map_metrics()

    # Step 6: Shutdown & Centralized Log Export Sample
    engine.stop()
    print(f"\n{CLR_BLD}[STEP 4] Contoh Format Log JSON Terpusat (SIEM/Elasticsearch Payload):{CLR_RST}")
    if aggregator.collected_logs:
        sample = json.loads(aggregator.collected_logs[0])
        print(f"{CLR_GRY}{json.dumps(sample, indent=2)}{CLR_RST}")

    print(f"\n{CLR_BLD}{CLR_GRN}[+] Lab Observabilitas & eBPF Tracing Selesai dengan Sukses.{CLR_RST}")


if __name__ == "__main__":
    main()