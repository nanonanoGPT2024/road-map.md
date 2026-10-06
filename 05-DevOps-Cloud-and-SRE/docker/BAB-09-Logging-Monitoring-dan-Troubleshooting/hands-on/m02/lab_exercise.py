#!/usr/bin/env python3
"""
Laboratorium Simulasi Interaktif: Docker Observability, Monitoring & Troubleshooting
Topik: BAB-09 Logging, Monitoring, dan Troubleshooting Docker Tingkat Lanjut
Standard Library Python 3 - Mandiri dan Runnable Tanpa Dependensi Eksternal
"""

import sys
import time
import random
import json
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional

# --- ANSI Terminal Color Palette ---
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"


class LogDriver(Enum):
    JSON_FILE = "json-file"
    FLUENTD = "fluentd"
    JOURNALD = "journald"
    LOKI = "loki"


@dataclass
class ContainerSpec:
    id: str
    name: str
    image: str
    mem_limit_mb: int
    cpu_shares: int
    log_driver: LogDriver
    log_max_size_mb: int = 10
    log_max_files: int = 3
    current_mem_mb: float = 30.0
    current_cpu_pct: float = 2.5
    status: str = "running"
    exit_code: int = 0
    health_status: str = "healthy"
    logs_generated: int = 0
    disk_usage_mb: float = 45.0


class ProductionClusterSimulation:
    def __init__(self):
        self.containers: Dict[str, ContainerSpec] = {}
        self.log_buffers: Dict[str, List[Dict[str, str]]] = {}
        self.prometheus_metrics_store: List[Dict[str, float]] = []
        self._bootstrap_cluster()

    def _bootstrap_cluster(self):
        presets = [
            ContainerSpec(
                id="c0a1b2c3d4e5",
                name="gateway-envoy",
                image="envoyproxy/envoy:v1.28-alpine",
                mem_limit_mb=256,
                cpu_shares=512,
                log_driver=LogDriver.JSON_FILE,
                log_max_size_mb=20,
                log_max_files=5,
                current_mem_mb=85.4,
                current_cpu_pct=14.2,
            ),
            ContainerSpec(
                id="f6e5d4c3b2a1",
                name="order-service-api",
                image="order-backend:2.4.1",
                mem_limit_mb=512,
                cpu_shares=1024,
                log_driver=LogDriver.LOKI,
                current_mem_mb=490.0,  # Near threshold (leak alert)
                current_cpu_pct=78.6,
            ),
            ContainerSpec(
                id="a9b8c7d6e5f4",
                name="cadvisor-agent",
                image="gcr.io/cadvisor/cadvisor:v0.47.2",
                mem_limit_mb=128,
                cpu_shares=256,
                log_driver=LogDriver.JOURNALD,
                current_mem_mb=62.0,
                current_cpu_pct=4.1,
            ),
            ContainerSpec(
                id="112233445566",
                name="redis-cache-tier",
                image="redis:7.2-alpine",
                mem_limit_mb=512,
                cpu_shares=512,
                log_driver=LogDriver.FLUENTD,
                current_mem_mb=140.2,
                current_cpu_pct=6.8,
            ),
        ]
        for c in presets:
            self.containers[c.id] = c
            self.log_buffers[c.id] = []

    def print_banner(self):
        print(f"{Color.CYAN}{Color.BOLD}{'=' * 78}{Color.RESET}")
        print(f"{Color.CYAN}{Color.BOLD}   DOCKER OBSERVABILITY, MONITORING & TROUBLESHOOTING SIMULATOR (PROD){Color.RESET}")
        print(f"{Color.DIM}   Bab 09: Production Log Drivers, cAdvisor Metrics, Health & Root-Cause Triage{Color.RESET}")
        print(f"{Color.CYAN}{Color.BOLD}{'=' * 78}{Color.RESET}\n")

    def display_docker_stats(self):
        """Simulate real-time `docker stats --no-stream` format with cAdvisor engine."""
        print(f"{Color.BOLD}{Color.WHITE}CONTAINER OBSERVABILITY METRICS (cAdvisor Engine):{Color.RESET}")
        header = f"{'CONTAINER ID':<14} {'NAME':<20} {'CPU %':<10} {'MEM USAGE / LIMIT':<24} {'MEM %':<10} {'STATUS':<12}"
        print(f"{Color.BLUE}{header}{Color.RESET}")
        print(f"{Color.DIM}{'-' * 92}{Color.RESET}")

        for cid, c in self.containers.items():
            mem_pct = (c.current_mem_mb / c.mem_limit_mb) * 100.0 if c.status == "running" else 0.0
            cpu_str = f"{c.current_cpu_pct:.1f}%" if c.status == "running" else "0.0%"
            mem_str = f"{c.current_mem_mb:.1f}MiB / {c.mem_limit_mb}MiB" if c.status == "running" else "0B / 0B"

            # Dynamic color alert based on utilization
            if mem_pct >= 90.0:
                mem_pct_styled = f"{Color.RED}{Color.BOLD}{mem_pct:.1f}% [WARN]{Color.RESET}"
            elif mem_pct >= 75.0:
                mem_pct_styled = f"{Color.YELLOW}{mem_pct:.1f}%{Color.RESET}"
            else:
                mem_pct_styled = f"{Color.GREEN}{mem_pct:.1f}%{Color.RESET}"

            status_styled = (
                f"{Color.GREEN}Up (health: {c.health_status}){Color.RESET}"
                if c.status == "running"
                else f"{Color.RED}Exited ({c.exit_code}){Color.RESET}"
            )

            print(f"{cid[:12]:<14} {c.name:<20} {cpu_str:<10} {mem_str:<24} {mem_pct_styled:<20} {status_styled}")
        print(f"{Color.DIM}{'-' * 92}{Color.RESET}\n")

    def simulate_logging_pipeline(self):
        """Simulate Docker Daemon Log Drivers: json-file rotation and forwarders."""
        print(f"{Color.BOLD}{Color.MAGENTA}--- SIMULASI ENGINE LOGGING & LOG ROTATION ---{Color.RESET}")
        target = self.containers["c0a1b2c3d4e5"]
        print(f"Mengaudit kontainer: {Color.CYAN}{target.name}{Color.RESET} (ID: {target.id[:12]})")
        print(f"Log Driver Aktif: {Color.YELLOW}{target.log_driver.value}{Color.RESET} | Max-Size: {target.log_max_size_mb}MB | Max-Files: {target.log_max_files}")

        print(f"\n{Color.DIM}[Daemon] Menghasilkan 5 event log akses berkecepatan tinggi...{Color.RESET}")
        log_sample = [
            {"level": "info", "msg": "GET /api/v1/health HTTP/1.1 200 OK", "upstream_time": "0.002s"},
            {"level": "info", "msg": "POST /api/v1/orders HTTP/1.1 201 Created", "upstream_time": "0.045s"},
            {"level": "warn", "msg": "High upstream latency detected in downstream order-service", "upstream_time": "1.420s"},
            {"level": "info", "msg": "GET /metrics Prometheus scrape completed", "upstream_time": "0.001s"},
            {"level": "error", "msg": "Connection reset by peer on socket 10.0.4.15:8080", "upstream_time": "5.002s"},
        ]

        for item in log_sample:
            raw_entry = {
                "log": f"[{item['level'].upper()}] {item['msg']} (latency={item['upstream_time']})\n",
                "stream": "stderr" if item["level"] in ("error", "warn") else "stdout",
                "time": datetime.now(timezone.utc).isoformat(),
            }
            self.log_buffers[target.id].append(raw_entry)
            target.logs_generated += 1
            time.sleep(0.1)

            # JSON-file rotation check
            if target.logs_generated > 3 and target.log_driver == LogDriver.JSON_FILE:
                rot_msg = f"{Color.BLUE}[Log Rotation Triggered]{Color.RESET} File {target.id}-json.log mencapai batas rotasi. Rolled into {target.id}-json.log.1"
                print(f"  {rot_msg}")

            stream_color = Color.YELLOW if raw_entry["stream"] == "stderr" else Color.GREEN
            print(f"  [{stream_color}{raw_entry['stream']}{Color.RESET}] {raw_entry['time']} -> {json.dumps(raw_entry)}")

        print(f"\n{Color.GREEN}✓ Pipeline log docker tersimpan dengan aman tanpa membebani disk root host.{Color.RESET}\n")

    def run_troubleshooting_scenario_oom(self):
        """Simulate Linux Kernel OOM Killer termination (Exit Code 137)."""
        print(f"{Color.BOLD}{Color.RED}--- SKENARIO ROOT-CAUSE 1: OOMKILLED (EXIT CODE 137) ---{Color.RESET}")
        target = self.containers["f6e5d4c3b2a1"]
        print(f"Menganalisis anomali pada kontainer: {Color.YELLOW}{target.name}{Color.RESET}")
        print(f"Spesifikasi Batas Kernel Cgroup: Memory Limit = {target.mem_limit_mb}MiB")

        print(f"{Color.DIM}[Simulator] Injeksi memory leak heap allocation...{Color.RESET}")
        for leak_step in range(1, 4):
            target.current_mem_mb += 15.0
            print(f"  Waktu t+{leak_step}s: Memory Usage = {target.current_mem_mb:.1f}MiB / {target.mem_limit_mb}MiB")
            time.sleep(0.2)

        # Trigger OOM
        print(f"\n{Color.BG_RED}{Color.WHITE} [KERNEL ALERT: dmesg] {Color.RESET} {Color.RED}oom-killer invoked: task={target.name}, pid=28491, oom_score_adj=998{Color.RESET}")
        print(f"{Color.RED}[KERNEL] Memory cgroup out of memory: Kill process 28491 ({target.name}) score 1012 or sacrifice child{Color.RESET}")

        target.status = "exited"
        target.exit_code = 137
        target.health_status = "unhealthy"
        target.current_mem_mb = 0.0
        target.current_cpu_pct = 0.0

        print(f"\n{Color.BOLD}Hasil Investigasi `docker inspect {target.id[:12]}`:{Color.RESET}")
        diagnostic_info = {
            "State": {
                "Status": target.status,
                "Running": False,
                "Paused": False,
                "OOMKilled": True,
                "Dead": False,
                "Pid": 0,
                "ExitCode": target.exit_code,
                "Error": "fatal error: runtime: out of memory",
                "FinishedAt": datetime.now(timezone.utc).isoformat(),
            },
            "HostConfig": {
                "Memory": target.mem_limit_mb * 1024 * 1024,
                "MemoryReservation": (target.mem_limit_mb // 2) * 1024 * 1024,
                "OomKillDisable": False,
            }
        }
        print(f"{Color.CYAN}{json.dumps(diagnostic_info, indent=2)}{Color.RESET}")
        print(f"\n{Color.GREEN}[Rekomendasi Arsitektur SRE]:")
        print("  1. Analisis dump profiling heap pprof / JVM heap analyzer.")
        print("  2. Sesuaikan limit cgroup: `docker update --memory 1024m --memory-swap 1024m`.")
        print(f"  3. Pasang alert rule Prometheus: `container_memory_usage_bytes / container_spec_memory_limit_bytes > 0.85`{Color.RESET}\n")

    def run_troubleshooting_scenario_disk_pressure(self):
        """Simulate /var/lib/docker storage driver pressure and prune remediation."""
        print(f"{Color.BOLD}{Color.YELLOW}--- SKENARIO ROOT-CAUSE 2: DOCKER STORAGE LEAK & PRUNE ---{Color.RESET}")
        print("Mendeteksi status partisi host: /var/lib/docker/overlay2 mencapai 94% kapasitas.")

        storage_analysis = [
            {"Type": "Images (Dangling)", "Total": 14, "Active": 3, "Size": "4.82GB", "Reclaimable": "3.11GB (64%)"},
            {"Type": "Containers (Stopped)", "Total": 8, "Active": 3, "Size": "820MB", "Reclaimable": "610MB (74%)"},
            {"Type": "Local Volumes (Orphan)", "Total": 6, "Active": 2, "Size": "12.4GB", "Reclaimable": "9.2GB (74%)"},
            {"Type": "Build Cache", "Total": 42, "Active": 0, "Size": "6.5GB", "Reclaimable": "6.5GB (100%)"},
        ]

        print(f"\n{Color.BOLD}{'TYPE':<25} {'TOTAL':<10} {'ACTIVE':<10} {'SIZE':<12} {'RECLAIMABLE':<20}{Color.RESET}")
        print(f"{Color.DIM}{'-' * 80}{Color.RESET}")
        for row in storage_analysis:
            print(f"{row['Type']:<25} {row['Total']:<10} {row['Active']:<10} {row['Size']:<12} {Color.YELLOW}{row['Reclaimable']:<20}{Color.RESET}")
        print(f"{Color.DIM}{'-' * 80}{Color.RESET}")

        print(f"\n{Color.CYAN}[Remediasi Otomatis] Menjalankan: docker system prune --volumes -f ...{Color.RESET}")
        time.sleep(0.3)
        print(f"  Deleted Containers: 5 stopped containers purged.")
        print(f"  Deleted Volumes: 4 unreferenced persistent volumes purged.")
        print(f"  Deleted Images: 11 untagged/dangling overlay layers purged.")
        print(f"  Deleted Build Cache: 42 stage cache entries evicted.")
        print(f"{Color.GREEN}{Color.BOLD}✓ Total Ruang Disk Berhasil Direklamasi: 19.42GB. Partisi kembali stabil pada 48% pemakaian.{Color.RESET}\n")

    def run_healthcheck_audit(self):
        """Demonstrate Container Healthcheck state machine (HEALTHCHECK instruction)."""
        print(f"{Color.BOLD}{Color.GREEN}--- SIMULASI DOCKER HEALTHCHECK STATE MACHINE ---{Color.RESET}")
        print("Audit konfigurasi HEALTHCHECK pada gateway-envoy:")
        print(f"  Interval: 5s | Timeout: 2s | Retries: 3 | Start-Period: 2s")
        print(f"  CMD: curl -f http://localhost:8001/ready || exit 1\n")

        states = [
            ("healthy", 200, "HTTP 200 OK - Upstream pool ready"),
            ("healthy", 200, "HTTP 200 OK - Latency 4ms"),
            ("unhealthy-candidate", 503, "HTTP 503 Service Unavailable (Attempt 1/3)"),
            ("unhealthy-candidate", 503, "HTTP 503 Service Unavailable (Attempt 2/3)"),
            ("unhealthy", 500, "HTTP 500 Gateway Error (Attempt 3/3 - MARKED UNHEALTHY)"),
        ]

        for idx, (h_state, code, msg) in enumerate(states, 1):
            time.sleep(0.15)
            badge = f"{Color.GREEN}[PASS]{Color.RESET}" if code == 200 else f"{Color.RED}[FAIL]{Color.RESET}"
            print(f"  Probe #{idx}: {badge} Code={code} Status={h_state.upper()} -> {msg}")

        print(f"\n{Color.YELLOW}[Docker Swarm / Orchestrator Action]: Trafik dialihkan otomatis dari kontainer yang berstatus 'unhealthy'.{Color.RESET}\n")


def interactive_menu():
    sim = ProductionClusterSimulation()
    sim.print_banner()

    menu = (
        f"{Color.BOLD}PILIH MENU PRAKTIK OBSERVABILITY & DIAGNOSTIK:{Color.RESET}\n"
        f"  1. Tampilkan Real-time Metrics Cluster (`docker stats` cAdvisor)\n"
        f"  2. Simulasi Log Driver & Buffer Rotation (`json-file`, `loki`)\n"
        f"  3. Simulasi Root-Cause Failure: OOMKilled Container (Exit Code 137)\n"
        f"  4. Simulasi Root-Cause Failure: Storage Leak & Docker System Prune\n"
        f"  5. Simulasi State Machine Healthcheck (`HEALTHCHECK` probes)\n"
        f"  6. Jalankan Semua Skenario Pengujian Sekaligus (Automated Full Audit)\n"
        f"  0. Keluar dari Laboratorium\n"
    )

    # In automated/headless runs without tty stdin, run all scenarios
    if not sys.stdin.isatty():
        print(f"{Color.DIM}[Non-Interactive Shell Detected] Mengeksekusi Automated Full Audit...{Color.RESET}\n")
        sim.display_docker_stats()
        sim.simulate_logging_pipeline()
        sim.run_troubleshooting_scenario_oom()
        sim.display_docker_stats()
        sim.run_troubleshooting_scenario_disk_pressure()
        sim.run_healthcheck_audit()
        print(f"{Color.GREEN}{Color.BOLD}Seluruh simulasi dan skenario pemecahan masalah selesai dijalankan 100% sukses.{Color.RESET}")
        return

    while True:
        print(menu)
        try:
            choice = input(f"{Color.BOLD}{Color.WHITE}Pilih opsi (0-6): {Color.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar dari simulator.")
            break

        if choice == "1":
            sim.display_docker_stats()
        elif choice == "2":
            sim.simulate_logging_pipeline()
        elif choice == "3":
            sim.run_troubleshooting_scenario_oom()
        elif choice == "4":
            sim.run_troubleshooting_scenario_disk_pressure()
        elif choice == "5":
            sim.run_healthcheck_audit()
        elif choice == "6":
            sim.display_docker_stats()
            sim.simulate_logging_pipeline()
            sim.run_troubleshooting_scenario_oom()
            sim.display_docker_stats()
            sim.run_troubleshooting_scenario_disk_pressure()
            sim.run_healthcheck_audit()
        elif choice == "0":
            print(f"{Color.CYAN}Sesi lab troubleshooting ditutup. Selamat belajar!{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid. Silakan pilih 0-6.{Color.RESET}\n")


if __name__ == "__main__":
    interactive_menu()
