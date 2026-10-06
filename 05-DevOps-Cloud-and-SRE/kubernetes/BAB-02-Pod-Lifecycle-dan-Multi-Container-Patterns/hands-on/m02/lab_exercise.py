#!/usr/bin/env python3
"""
Kubernetes Pod Lifecycle & Multi-Container Patterns Simulator
Modul 02: Hands-on Lab Exercise
Author: DevOps & Cloud Architecture Team

Topik yang disimulasikan:
1. Pod Lifecycle Phases: Pending -> ContainerCreating -> Running -> Terminating
2. Init Containers (Sequential execution & exit code gating)
3. Container Probes (Startup, Liveness, Readiness)
4. Multi-Container Patterns:
   - Sidecar (Log shipping daemon)
   - Ambassador (Smart database proxy)
   - Adapter (Custom metrics transformer for Prometheus)
5. Lifecycle Hooks & Graceful Shutdown:
   - postStart hook
   - preStop hook (Connection draining & state cleanup)
   - SIGTERM -> TerminationGracePeriodSeconds -> SIGKILL
"""

import sys
import time
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional


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
    BG_BLUE = "\033[44m"
    BG_GREEN = "\033[42m"
    BG_MAGENTA = "\033[45m"


class PodPhase(Enum):
    PENDING = "Pending"
    INITIALIZING = "Init:0/2"
    RUNNING = "Running"
    TERMINATING = "Terminating"
    SUCCEEDED = "Succeeded"
    FAILED = "Failed"


class ProbeStatus(Enum):
    SUCCESS = f"{Color.GREEN}200 OK{Color.RESET}"
    FAILURE = f"{Color.RED}503 Service Unavailable{Color.RESET}"
    PENDING = f"{Color.YELLOW}Checking...{Color.RESET}"


@dataclass
class Container:
    name: str
    image: str
    role: str
    is_ready: bool = False
    is_alive: bool = True
    logs: List[str] = field(default_factory=list)

    def log(self, message: str, color: str = Color.WHITE) -> None:
        timestamp = time.strftime("%H:%M:%S")
        entry = f"{Color.DIM}[{timestamp}]{Color.RESET} {color}[{self.name}]{Color.RESET} {message}"
        self.logs.append(entry)
        print(entry)


class PodSimulator:
    def __init__(self, name: str, namespace: str = "production"):
        self.name = name
        self.namespace = namespace
        self.phase = PodPhase.PENDING
        self.grace_period_seconds = 5
        self.active_connections = 12

        # Inisialisasi Kontainer
        self.init_containers = [
            Container("init-schema-migration", "flyway/flyway:9.0", "Init Container (DB Migration)"),
            Container("init-vault-secrets", "hashicorp/vault:1.14", "Init Container (Secret Injection)"),
        ]

        self.app_container = Container(
            "order-service-api", "corp/order-api:v2.4.0", "Main Application"
        )

        self.multi_containers = {
            "sidecar": Container("log-shipper-fluentbit", "fluent/fluent-bit:2.1", "Sidecar Pattern (Log Forwarder)"),
            "ambassador": Container("redis-cluster-ambassador", "envoyproxy/envoy:v1.28", "Ambassador Pattern (Circuit Breaker & Routing)"),
            "adapter": Container("metrics-adapter", "prom/statsd-exporter:v0.24", "Adapter Pattern (Format Standardizer)"),
        }

    def print_banner(self) -> None:
        banner = f"""
{Color.CYAN}{Color.BOLD}================================================================================
          KUBERNETES POD LIFECYCLE & MULTI-CONTAINER SIMULATOR
   BAB-02: Advanced Production Pod Internals & Container Collaboration
================================================================================{Color.RESET}
Pod Name      : {Color.BOLD}{self.name}{Color.RESET}
Namespace     : {Color.GREEN}{self.namespace}{Color.RESET}
Architecture  : Multi-Container (Init + Main + Sidecar + Ambassador + Adapter)
"""
        print(banner)

    def print_section(self, title: str) -> None:
        print(f"\n{Color.BG_BLUE}{Color.WHITE}{Color.BOLD} [STAGE] {title} {Color.RESET}\n")

    def run_init_phase(self) -> bool:
        self.print_section("FASE 1: Eksekusi Init Containers (Serial & Blocking)")
        self.phase = PodPhase.INITIALIZING

        for idx, container in enumerate(self.init_containers, 1):
            container.log(f"Memulai container ({idx}/{len(self.init_containers)}) - Role: {container.role}", Color.YELLOW)
            time.sleep(0.6)

            if container.name == "init-schema-migration":
                container.log("Memverifikasi koneksi PostgreSQL db-primary.internal...", Color.CYAN)
                time.sleep(0.5)
                container.log("Menerapkan migrasi V1.0__init_order_table.sql [SUCCESS]", Color.GREEN)
            elif container.name == "init-vault-secrets":
                container.log("Mengautentikasi ke Vault via Kubernetes ServiceAccount Token...", Color.CYAN)
                time.sleep(0.5)
                container.log("Menulis secret ke shared in-memory volume /vault/secrets/db-creds [SUCCESS]", Color.GREEN)

            container.log("Kontainer selesai dengan Exit Code 0 (Completed)\n", Color.GREEN)
            time.sleep(0.4)

        print(f"{Color.GREEN}{Color.BOLD}>>> Seluruh Init Container Berhasil. Pod memasuki status PodInitializing -> Running.{Color.RESET}")
        return True

    def run_multi_container_startup(self) -> None:
        self.print_section("FASE 2: Startup Multi-Container & PostStart Hook")
        self.phase = PodPhase.RUNNING

        print(f"{Color.BOLD}Mengaktifkan Main Container bersamaan dengan Co-located Containers (Shared IPC/Net):{Color.RESET}")
        time.sleep(0.4)

        # 1. Main App
        self.app_container.log("Entrypoint exec /app/server --config=/vault/secrets/db-creds", Color.MAGENTA)
        
        # PostStart hook
        self.app_container.log("Menjalankan lifecycle.postStart: /bin/sh -c 'curl -X POST audit.internal/pod-up'", Color.YELLOW)
        time.sleep(0.4)
        self.app_container.log("Lifecycle postStart hook selesai secara asynchronous.", Color.GREEN)

        # 2. Sidecar (Logging)
        self.multi_containers["sidecar"].log("Mounting volume shared /var/log/orders...", Color.CYAN)
        self.multi_containers["sidecar"].log("Streaming JSON log dari app ke central Elasticsearch cluster.", Color.CYAN)
        time.sleep(0.3)

        # 3. Ambassador (Proxy)
        self.multi_containers["ambassador"].log("Binding localhost:6379 -> routing read/write splitting ke Redis Sentinel pool.", Color.BLUE)
        time.sleep(0.3)

        # 4. Adapter (Metrics)
        self.multi_containers["adapter"].log("Membaca custom metrics (order_throughput_raw) pada socket lokal.", Color.YELLOW)
        self.multi_containers["adapter"].log("Mengekspos Prometheus endpoint /metrics pada port 9102 [Ready]", Color.YELLOW)
        time.sleep(0.5)

    def run_probes_lifecycle(self) -> bool:
        self.print_section("FASE 3: Probes Validation (Startup -> Liveness -> Readiness)")
        
        # 1. Startup Probe
        print(f"{Color.BOLD}1. Memeriksa Startup Probe (Perlindungan slow-starting container)...{Color.RESET}")
        time.sleep(0.5)
        print(f"   Probe: http-get :8080/health/startup | Result: {ProbeStatus.SUCCESS.value}")
        print(f"   {Color.GREEN}Startup probe berhasil! Liveness probe kini mulai aktif.{Color.RESET}\n")

        # 2. Liveness Probe
        print(f"{Color.BOLD}2. Memeriksa Liveness Probe (Deteksi Deadlock & Zombie Process)...{Color.RESET}")
        time.sleep(0.5)
        print(f"   Probe: http-get :8080/health/live | Result: {ProbeStatus.SUCCESS.value}")
        self.app_container.is_alive = True
        print(f"   {Color.GREEN}Container dinilai sehat oleh kubelet, tidak perlu restart container.{Color.RESET}\n")

        # 3. Readiness Probe
        print(f"{Color.BOLD}3. Memeriksa Readiness Probe (Gating Endpoint Service / Trafik End-User)...{Color.RESET}")
        time.sleep(0.5)
        print(f"   Attempt 1: http-get :8080/health/ready | Result: {ProbeStatus.FAILURE.value} (Warming caches)")
        time.sleep(0.7)
        print(f"   Attempt 2: http-get :8080/health/ready | Result: {ProbeStatus.SUCCESS.value} (Cache loaded)")
        
        self.app_container.is_ready = True
        for c in self.multi_containers.values():
            c.is_ready = True

        print(f"\n{Color.BG_GREEN}{Color.WHITE}{Color.BOLD} POD STATUS: RUNNING & READY (Endpoints ditambahkan ke Kube-Proxy/EndpointsSlice) {Color.RESET}\n")
        return True

    def simulate_active_traffic(self) -> None:
        self.print_section("FASE 4: Simulasi Trafik Produksi & Interaksi Multi-Container")
        for req_id in range(101, 104):
            time.sleep(0.4)
            print(f"{Color.BOLD}--> Request ID #{req_id} [POST /api/v1/orders] Masuk via Service ClusterIP{Color.RESET}")
            self.app_container.log(f"Menerima order #{req_id}. Query state via Ambassador...", Color.MAGENTA)
            self.multi_containers["ambassador"].log("Routing query read ke Redis replica [10.244.2.14:6379]", Color.BLUE)
            self.app_container.log(f"Order #{req_id} berhasil diproses. Logging audit...", Color.MAGENTA)
            self.multi_containers["sidecar"].log(f"Parsed & enriched order #{req_id} log -> pushed to Elastic.", Color.CYAN)
            self.multi_containers["adapter"].log("Transform metric: order_count{status='success'} += 1", Color.YELLOW)
            print()

    def run_graceful_shutdown(self) -> None:
        self.print_section("FASE 5: Graceful Termination Lifecycle (Zero-Downtime Drainage)")
        self.phase = PodPhase.TERMINATING

        print(f"{Color.RED}{Color.BOLD}[API Server] Pod ditandai TERMINATING (Event: kubectl delete pod / RollingUpdate){Color.RESET}")
        print(f"{Color.YELLOW}Langkah 1: Endpoint controller mencabut Pod IP dari Service Endpoints.{Color.RESET}")
        print(f"{Color.YELLOW}Langkah 2: Kubelet memicu 'lifecycle.preStop' hook pada Main Container secara serentak.{Color.RESET}\n")
        time.sleep(0.8)

        # PreStop Hook Execution
        self.app_container.log(f"PRE-STOP TRIGGERED: Menutup penerimaan request baru. Active connections: {self.active_connections}", Color.YELLOW)
        for remaining in range(self.active_connections, 0, -4):
            time.sleep(0.5)
            self.app_container.log(f"Draining sockets... {remaining} koneksi tersisa.", Color.YELLOW)
        
        self.app_container.log("Seluruh in-flight requests selesai. PreStop hook tuntas.", Color.GREEN)
        time.sleep(0.6)

        # SIGTERM Signal
        print(f"\n{Color.BOLD}Langkah 3: Kubelet mengirim sinyal SIGTERM ke seluruh container PID 1.{Color.RESET}")
        self.app_container.log("Menerima SIGTERM: Menutup koneksi database pool & unregistering.", Color.MAGENTA)
        self.multi_containers["sidecar"].log("Menerima SIGTERM: Flushing pending logs buffer ke disk.", Color.CYAN)
        self.multi_containers["ambassador"].log("Menerima SIGTERM: Menutup TCP listening sockets.", Color.BLUE)
        self.multi_containers["adapter"].log("Menerima SIGTERM: Scraping final internal metrics.", Color.YELLOW)
        time.sleep(0.8)

        print(f"\n{Color.BOLD}Langkah 4: Semua proses berhenti dengan bersih dalam batas terminationGracePeriod ({self.grace_period_seconds}s).{Color.RESET}")
        print(f"{Color.GREEN}Tidak ada pengiriman paksa SIGKILL. Data aman tanpa korupsi.{Color.RESET}")
        self.phase = PodPhase.SUCCEEDED
        print(f"\n{Color.BG_MAGENTA}{Color.WHITE}{Color.BOLD} POD BERHASIL DITERMINASI DENGAN GRACEFUL (Exit Code: 0) {Color.RESET}\n")

    def run_full_simulation(self) -> None:
        self.print_banner()
        self.run_init_phase()
        self.run_multi_container_startup()
        self.run_probes_lifecycle()
        self.simulate_active_traffic()
        self.run_graceful_shutdown()


def display_interactive_menu() -> None:
    simulator = PodSimulator("order-api-deployment-78db64c9d-x94zq")
    
    while True:
        print(f"\n{Color.BOLD}{Color.CYAN}=== KUBERNETES POD LIFECYCLE INTERACTIVE LAB ==={Color.RESET}")
        print("1. Jalankan Simulasi Siklus Hidup Penuh (Full Lifecycle & Patterns)")
        print("2. Demo Khusus: Init Containers Dependency & Fail-Safe")
        print("3. Demo Khusus: Multi-Container Patterns (Sidecar, Ambassador, Adapter)")
        print("4. Demo Khusus: PreStop Hook & Graceful Termination")
        print("5. Keluar (Exit)")
        
        try:
            choice = input(f"\n{Color.BOLD}Pilih opsi [1-5]: {Color.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting lab simulator. Goodbye!")
            sys.exit(0)

        if choice == "1":
            simulator.run_full_simulation()
        elif choice == "2":
            simulator.print_banner()
            simulator.run_init_phase()
        elif choice == "3":
            simulator.print_banner()
            simulator.run_multi_container_startup()
            simulator.simulate_active_traffic()
        elif choice == "4":
            simulator.print_banner()
            simulator.run_graceful_shutdown()
        elif choice == "5":
            print(f"\n{Color.GREEN}Terima kasih telah mempelajari Kubernetes Pod Internals! Selesai.{Color.RESET}")
            sys.exit(0)
        else:
            print(f"{Color.RED}Pilihan tidak valid. Silakan pilih 1 - 5.{Color.RESET}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        sim = PodSimulator("order-api-deployment-78db64c9d-x94zq")
        sim.run_full_simulation()
    else:
        # Default run langsung atau interaktif
        if not sys.stdin.isatty():
            sim = PodSimulator("order-api-deployment-78db64c9d-x94zq")
            sim.run_full_simulation()
        else:
            display_interactive_menu()
