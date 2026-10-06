#!/usr/bin/env python3
"""
Lab Exercise: Docker Logging, Monitoring, dan Troubleshooting Simulator
Modul 01 - BAB 09: Logging, Monitoring, dan Troubleshooting

Deskripsi:
Simulasi interaktif teknis berbasis CLI untuk memahami:
1. Docker Logging Drivers & Log Rotation (json-file, local, syslog)
2. Container Metrics Monitoring (CPU %, Memory, Network I/O, Block I/O)
3. Healthcheck Mechanism & State Transitions
4. Diagnostik Troubleshooting & Analisis Exit Code (0, 1, 137 OOMKilled, 139)
"""

import sys
import time
import json
import random
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import List, Dict, Optional

# ANSI Color Codes
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_MAGENTA = "\033[95m"
CLR_CYAN = "\033[96m"
CLR_BG_DARK = "\033[100m"


def header(title: str):
    print(f"\n{CLR_BOLD}{CLR_BLUE}{'=' * 65}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}  [LAB] {title.upper()}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_BLUE}{'=' * 65}{CLR_RESET}\n")


def log_step(msg: str):
    print(f"{CLR_BOLD}{CLR_GREEN}[+] {msg}{CLR_RESET}")


def log_warn(msg: str):
    print(f"{CLR_BOLD}{CLR_YELLOW}[!] {msg}{CLR_RESET}")


def log_err(msg: str):
    print(f"{CLR_BOLD}{CLR_RED}[X] {msg}{CLR_RESET}")


def log_info(msg: str):
    print(f"{CLR_BLUE}[*] {msg}{CLR_RESET}")


# ----------------------------------------------------------------------
# 1. SIMULASI LOGGING DRIVER & LOG ROTATION
# ----------------------------------------------------------------------
@dataclass
class LogEntry:
    timestamp: str
    stream: str
    log: str


class DockerLoggingSimulator:
    """Mensimulasikan mekanisme logging driver json-file dan rotasi file."""

    def __init__(self, container_id: str, max_size_bytes: int = 1500, max_files: int = 3):
        self.container_id = container_id
        self.max_size_bytes = max_size_bytes
        self.max_files = max_files
        self.files: List[List[Dict]] = [[]]
        self.current_file_size = 0

    def emit_log(self, message: str, stream: str = "stdout"):
        ts = datetime.now(timezone.utc).isoformat() + "Z"
        record = {"log": message + "\n", "stream": stream, "time": ts}
        record_bytes = len(json.dumps(record).encode("utf-8"))

        if self.current_file_size + record_bytes > self.max_size_bytes:
            log_warn(f"Rotasi Terpicu! File ke-{len(self.files)} melebihi batas {self.max_size_bytes}B")
            if len(self.files) >= self.max_files:
                oldest = self.files.pop(0)
                log_warn(f"Menghapus log chunk tertua ({len(oldest)} entri) sesuai max-file={self.max_files}")
            self.files.append([])
            self.current_file_size = 0

        self.files[-1].append(record)
        self.current_file_size += record_bytes

    def display_logs(self, tail: int = 5):
        all_logs = [item for f in self.files for item in f]
        print(f"\n{CLR_BOLD}--- Output 'docker logs --tail {tail} --timestamps' ---{CLR_RESET}")
        for entry in all_logs[-tail:]:
            color = CLR_GREEN if entry["stream"] == "stdout" else CLR_RED
            print(f"{CLR_MAGENTA}{entry['time']}{CLR_RESET} {color}[{entry['stream']}]{CLR_RESET} {entry['log'].strip()}")

    def display_disk_layout(self):
        print(f"\n{CLR_BOLD}--- Status File Log di Disk (/var/lib/docker/containers/{self.container_id}/) ---{CLR_RESET}")
        for idx, f in enumerate(self.files):
            size = sum(len(json.dumps(r).encode("utf-8")) for r in f)
            fname = f"{self.container_id}-json.log" if idx == len(self.files) - 1 else f"{self.container_id}-json.log.{len(self.files) - 1 - idx}"
            print(f"  -> File: {CLR_CYAN}{fname:<35}{CLR_RESET} Entri: {len(f):<3} Ukuran: {size}/{self.max_size_bytes} bytes")


# ----------------------------------------------------------------------
# 2. SIMULASI MONITORING & STATS
# ----------------------------------------------------------------------
@dataclass
class ContainerStats:
    container_id: str
    name: str
    cpu_percent: float = 0.0
    mem_usage_mib: float = 0.0
    mem_limit_mib: float = 512.0
    net_in_kib: float = 0.0
    net_out_kib: float = 0.0
    block_in_mib: float = 0.0
    block_out_mib: float = 0.0

    def tick_workload(self, stress_cpu: bool = False, leak_mem: bool = False):
        if stress_cpu:
            self.cpu_percent = min(100.0, self.cpu_percent + random.uniform(25.0, 45.0))
        else:
            self.cpu_percent = max(1.2, self.cpu_percent - random.uniform(5.0, 15.0) + random.uniform(0.5, 3.0))

        if leak_mem:
            self.mem_usage_mib = min(self.mem_limit_mib + 50.0, self.mem_usage_mib + random.uniform(30.0, 70.0))
        else:
            self.mem_usage_mib = max(35.0, self.mem_usage_mib + random.uniform(-5.0, 5.0))

        self.net_in_kib += random.uniform(5.0, 80.0)
        self.net_out_kib += random.uniform(10.0, 120.0)
        self.block_in_mib += random.uniform(0.1, 0.8)
        self.block_out_mib += random.uniform(0.05, 0.4)


def render_stats_table(containers: List[ContainerStats]):
    print(f"\n{CLR_BOLD}{CLR_BG_DARK} CONTAINER ID   NAME           CPU %      MEM USAGE / LIMIT     MEM %     NET I/O          BLOCK I/O    {CLR_RESET}")
    for c in containers:
        mem_pct = (c.mem_usage_mib / c.mem_limit_mib) * 100.0
        cpu_color = CLR_RED if c.cpu_percent > 80.0 else (CLR_YELLOW if c.cpu_percent > 40.0 else CLR_GREEN)
        mem_color = CLR_RED if mem_pct > 90.0 else (CLR_YELLOW if mem_pct > 70.0 else CLR_GREEN)

        print(
            f" {c.container_id[:12]:<14} "
            f"{c.name:<14} "
            f"{cpu_color}{c.cpu_percent:>6.2f}%{CLR_RESET}    "
            f"{c.mem_usage_mib:>6.1f}MiB / {c.mem_limit_mib:.0f}MiB   "
            f"{mem_color}{mem_pct:>6.2f}%{CLR_RESET}   "
            f"{c.net_in_kib:>5.1f}kB / {c.net_out_kib:>5.1f}kB   "
            f"{c.block_in_mib:>4.1f}MB / {c.block_out_mib:>4.1f}MB"
        )


# ----------------------------------------------------------------------
# 3. SIMULASI HEALTHCHECK & LIFECYCLE STATE
# ----------------------------------------------------------------------
class HealthcheckSimulator:
    """Mensimulasikan interval, timeout, retries, dan transisi healthy -> unhealthy."""

    def __init__(self, interval_sec: int = 2, retries: int = 3):
        self.interval = interval_sec
        self.retries = retries
        self.failing_streak = 0
        self.status = "starting"  # starting, healthy, unhealthy

    def probe(self, endpoint_healthy: bool) -> str:
        if endpoint_healthy:
            self.failing_streak = 0
            self.status = "healthy"
            log_step(f"Health check PROBE SUKSES (HTTP 200) -> Status: {CLR_GREEN}{self.status}{CLR_RESET}")
        else:
            self.failing_streak += 1
            log_warn(f"Health check GAGAL (Streak {self.failing_streak}/{self.retries})")
            if self.failing_streak >= self.retries:
                self.status = "unhealthy"
                log_err(f"Batas retry tercapai! Transisi status menjadi: {CLR_RED}{self.status}{CLR_RESET}")
            else:
                self.status = "starting" if self.status == "starting" else "healthy (degrading)"
        return self.status


# ----------------------------------------------------------------------
# 4. SIMULASI DIAGNOSTIK TROUBLESHOOTING & EXIT CODES
# ----------------------------------------------------------------------
EXIT_CODE_KNOWLEDGE = {
    0: ("Normal Exit / Completed", "Proses container selesai menjalankan tugasnya dengan sukses."),
    1: ("Application Error / Exception", "Error aplikasi umum (misal: unhandled exception, syntax error code)."),
    125: ("Docker Daemon Error", "Perintah docker run gagal dieksekusi oleh daemon itu sendiri."),
    126: ("Command Cannot Be Invoked", "Executable file ditemukan tetapi tidak memiliki permission execute."),
    127: ("Container Command Not Found", "Executable / binary tidak ditemukan di dalam PATH container."),
    137: ("SIGKILL (OOMKilled / Force Kill)", "Container di-kill oleh host kernel Linux karena kehabisan alokasi Memory (OOM) atau 'docker kill'."),
    139: ("SIGSEGV (Segmentation Fault)", "Aplikasi mengakses segmen memory ilegal (memory corruption)."),
    143: ("SIGTERM (Graceful Stop)", "Container dihentikan secara wajar via 'docker stop' tetapi tidak keluar mandiri tepat waktu."),
}


def diagnose_exit_code(code: int, oom_killed: bool = False):
    print(f"\n{CLR_BOLD}=== HASIL ANALISIS DOCKER INSPECT PADA EXIT CODE: {code} ==={CLR_RESET}")
    desc, remedy = EXIT_CODE_KNOWLEDGE.get(code, ("Unknown Exit Code", "Periksa log rinci aplikasi."))

    if code == 137:
        if oom_killed:
            print(f"Status State: {CLR_RED}Dead / OOMKilled=True{CLR_RESET}")
            print(f"Deskripsi   : {desc}")
            print(f"{CLR_YELLOW}Root Cause  : Batas --memory atau --memory-swap terlampaui cgroup host.{CLR_RESET}")
            print(f"{CLR_CYAN}Solusi      : Naikkan limit memory pada Compose/Run atau optimasi memory leak.{CLR_RESET}")
        else:
            print(f"Status State: {CLR_YELLOW}Stopped by SIGKILL{CLR_RESET}")
            print(f"Root Cause  : Perintah paksa 'docker kill' atau orchestrator timeout.")
    elif code == 127:
        print(f"Status State: {CLR_RED}Entrypoint / CMD Missing{CLR_RESET}")
        print(f"Deskripsi   : {desc}")
        print(f"{CLR_CYAN}Solusi      : Periksa PATH, binary name, atau shebang (#!/bin/sh vs #!/bin/bash).{CLR_RESET}")
    elif code == 0:
        print(f"Status State: {CLR_GREEN}Finished Successfully{CLR_RESET}")
        print(f"Deskripsi   : {desc}")
    else:
        print(f"Status State: {CLR_RED}Failed{CLR_RESET}")
        print(f"Deskripsi   : {desc}")
        print(f"Analisis    : {remedy}")


# ----------------------------------------------------------------------
# WORKFLOW DEMO INTERAKTIF
# ----------------------------------------------------------------------
def demo_logging():
    header("Demo 1: Docker Logging Driver & Log Rotation (json-file)")
    sim = DockerLoggingSimulator(container_id="c1a49f8b3401", max_size_bytes=450, max_files=3)

    log_info("Konfigurasi: max-size=450 bytes, max-file=3")
    sample_logs = [
        ("Nginx worker process initialized", "stdout"),
        ("Listening on 0.0.0.0:80", "stdout"),
        ("GET /api/v1/health HTTP/1.1 200 OK", "stdout"),
        ("GET /static/bundle.js HTTP/1.1 304 Not Modified", "stdout"),
        ("DB Connection timed out after 3000ms", "stderr"),
        ("Retrying connection to postgres:5432", "stderr"),
        ("Connection re-established", "stdout"),
        ("POST /api/v1/orders HTTP/1.1 201 Created", "stdout"),
        ("Warning: high disk write latency detected", "stderr"),
    ]

    for msg, stream in sample_logs:
        sim.emit_log(msg, stream)
        time.sleep(0.05)

    sim.display_disk_layout()
    sim.display_logs(tail=4)


def demo_monitoring():
    header("Demo 2: Container Metrics Live-Monitor (docker stats)")
    containers = [
        ContainerStats("9f3b118a24c1", "api-gateway", cpu_percent=8.5, mem_usage_mib=110.0, mem_limit_mib=512.0),
        ContainerStats("a81c4e92d004", "order-service", cpu_percent=14.2, mem_usage_mib=240.0, mem_limit_mib=512.0),
        ContainerStats("fe4581290bb3", "cache-redis", cpu_percent=2.1, mem_usage_mib=45.0, mem_limit_mib=256.0),
    ]

    log_info("Mensimulasikan sampling metrik selama 4 siklus cgroup ticks...")
    for tick in range(1, 5):
        print(f"\n{CLR_BOLD}[Tick {tick}/4 - Waktu: {datetime.now().strftime('%H:%M:%S')}]{CLR_RESET}")
        stress = tick >= 3
        leak = tick >= 2
        containers[1].tick_workload(stress_cpu=stress, leak_mem=leak)
        containers[0].tick_workload()
        containers[2].tick_workload()
        render_stats_table(containers)
        time.sleep(0.3)


def demo_healthcheck():
    header("Demo 3: HEALTHCHECK Lifecycle & State Transition")
    hc = HealthcheckSimulator(interval_sec=2, retries=3)
    log_info("Rule: HEALTHCHECK --interval=2s --timeout=1s --retries=3 CMD curl -f /health")

    steps = [
        (True, "Aplikasi baru start up, probe awal OK"),
        (False, "Koneksi database terputus, endpoint /health merespon HTTP 500"),
        (False, "Probe kedua masih gagal HTTP 500"),
        (False, "Probe ketiga berturut-turut gagal!"),
        (True, "Setelah recovery, probe kembali HTTP 200"),
    ]

    for healthy, note in steps:
        print(f"\nSkenario: {CLR_BOLD}{note}{CLR_RESET}")
        hc.probe(endpoint_healthy=healthy)
        time.sleep(0.1)


def demo_troubleshooting():
    header("Demo 4: Diagnostik Crash & Exit Code Triage")
    scenarios = [
        (0, False, "Batch processing job selesai memproses data"),
        (1, False, "Python throw ValueError: unhandled payload format"),
        (127, False, "CMD salah ketik di Dockerfile: 'gunicorn-start' tidak ditemukan"),
        (137, True, "NodeJS heap memory melonjak melampaui limit 256MB -> OOMKilled"),
        (139, False, "C++ Extension segmentation fault (memory address violation)"),
    ]

    for code, oom, ctx in scenarios:
        print(f"\nKonteks Kasus: {CLR_BOLD}{ctx}{CLR_RESET}")
        diagnose_exit_code(code, oom_killed=oom)


def main():
    print(f"{CLR_BOLD}{CLR_MAGENTA}")
    print("╔═════════════════════════════════════════════════════════════════╗")
    print("║   DOCKER LAB: LOGGING, MONITORING, AND TROUBLESHOOTING SIM      ║")
    print("║   BAB 09 - Modul 01: Core Observability & Debugging Practice    ║")
    print("╚═════════════════════════════════════════════════════════════════╝")
    print(f"{CLR_RESET}")

    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        demo_logging()
        demo_monitoring()
        demo_healthcheck()
        demo_troubleshooting()
        log_step("Semua simulasi berhasil dijalankan secara otomatis.")
        return

    menu = """
Pilih Simulasi:
  [1] Docker Logging Drivers & Log Rotation (json-file)
  [2] Container Metrics Monitoring (docker stats simulation)
  [3] HEALTHCHECK Mechanism & State Transitions
  [4] Exit Code Triage & Troubleshooting Matrix (OOMKilled, 137, 127, etc)
  [5] Jalankan Semua Demo (Full Comprehensive Run)
  [0] Keluar
"""
    while True:
        print(menu)
        choice = input(f"{CLR_BOLD}Pilihan Anda (0-5): {CLR_RESET}").strip()
        if choice == "1":
            demo_logging()
        elif choice == "2":
            demo_monitoring()
        elif choice == "3":
            demo_healthcheck()
        elif choice == "4":
            demo_troubleshooting()
        elif choice == "5":
            demo_logging()
            demo_monitoring()
            demo_healthcheck()
            demo_troubleshooting()
        elif choice == "0":
            print(f"\n{CLR_GREEN}Lab selesai. Terima kasih.{CLR_RESET}\n")
            break
        else:
            log_warn("Pilihan tidak valid, silakan ulangi.")


if __name__ == "__main__":
    main()
