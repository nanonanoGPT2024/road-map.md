#!/usr/bin/env python3
"""
Lab Exercise: Kubernetes Pod Lifecycle & Multi-Container Patterns Simulation
BAB-02: Pod Lifecycle, Probes, and Multi-Container Patterns (Sidecar, Ambassador, Adapter)
"""

import sys
import time
import threading
from typing import List, Dict, Optional

# ANSI Color Codes
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
    BG_RED = "\033[41m"

def print_header(title: str):
    width = 75
    print(f"\n{Color.CYAN}{'=' * width}{Color.RESET}")
    print(f"{Color.BOLD}{Color.WHITE}{title.center(width)}{Color.RESET}")
    print(f"{Color.CYAN}{'=' * width}{Color.RESET}\n")

def print_step(step_num: int, description: str):
    print(f"{Color.YELLOW}[STEP {step_num}]{Color.RESET} {Color.BOLD}{description}{Color.RESET}")

def log_event(source: str, msg: str, status: str = "INFO", color: str = Color.GREEN):
    timestamp = time.strftime("%H:%M:%S")
    status_badge = f"{color}[{status:^7}]{Color.RESET}"
    source_badge = f"{Color.MAGENTA}{source:<18}{Color.RESET}"
    print(f"{Color.DIM}{timestamp}{Color.RESET} {status_badge} {source_badge} : {msg}")

class Container:
    def __init__(self, name: str, role: str, is_init: bool = False):
        self.name = name
        self.role = role
        self.is_init = is_init
        self.state = "Waiting"
        self.ready = False
        self.restart_count = 0

    def start(self, duration: float = 1.0) -> bool:
        self.state = "Running"
        log_event(self.name, f"Memulai kontainer ({self.role})...", "START", Color.CYAN)
        time.sleep(duration)
        if self.is_init:
            self.state = "Completed"
            self.ready = True
            log_event(self.name, "Inisialisasi selesai dengan exit code 0.", "SUCCESS", Color.GREEN)
            return True
        return True

    def run_probe(self, probe_type: str, success: bool) -> bool:
        if success:
            log_event(self.name, f"{probe_type} probe: HTTP 200 OK (Healthy)", "PROBE", Color.GREEN)
            self.ready = True
            return True
        else:
            log_event(self.name, f"{probe_type} probe: Connection Refused / Timeout (Unhealthy)", "FAIL", Color.RED)
            self.ready = False
            return False

    def stop(self, grace_period: int = 5):
        self.state = "Terminating"
        log_event(self.name, f"Menerima sinyal SIGTERM. Menjalankan PreStop Hook...", "STOP", Color.YELLOW)
        for i in range(grace_period, 0, -1):
            log_event(self.name, f"Draining koneksi aktif ({i}s tersisa)...", "DRAIN", Color.YELLOW)
            time.sleep(0.4)
        self.state = "Terminated"
        self.ready = False
        log_event(self.name, "Kontainer berhenti dengan bersih (Graceful Exit 0).", "DOWN", Color.RED)

class PodSimulator:
    def __init__(self, name: str, namespace: str = "production"):
        self.name = name
        self.namespace = namespace
        self.phase = "Pending"
        self.shared_volume: Dict[str, str] = {}
        self.init_containers: List[Container] = []
        self.app_containers: List[Container] = []

    def run_full_lifecycle(self):
        print_header(f"SIMULASI SIKLUS HIDUP POD KUBERNETES: {self.name}")
        
        print_step(1, "Fase Penjadwalan & Init Containers (Sequential Execution)")
        self.phase = "Pending"
        log_event("Kube-Scheduler", f"Pod {self.name} dijadwalkan ke node 'worker-node-01'.", "SCHED", Color.BLUE)
        log_event("Kubelet", "Mempersiapkan network namespace & sandbox volume...", "INIT", Color.BLUE)
        time.sleep(0.5)

        # Setup Init Containers
        init1 = Container("init-wait-db", "Check DB Readiness", is_init=True)
        init2 = Container("init-fetch-config", "Fetch Vault Secret", is_init=True)
        self.init_containers = [init1, init2]

        for idx, init_c in enumerate(self.init_containers, 1):
            log_event("Kubelet", f"Menjalankan Init Container [{idx}/{len(self.init_containers)}]: {init_c.name}", "INIT", Color.CYAN)
            init_c.start(0.8)

        print_step(2, "Fase ContainerCreating & Startup Multi-Container")
        self.phase = "ContainerCreating"
        app = Container("web-service", "Main Application")
        sidecar = Container("fluentd-sidecar", "Log Forwarder (Sidecar)")
        self.app_containers = [app, sidecar]

        for c in self.app_containers:
            c.start(0.5)

        print_step(3, "Pemeriksaan Probes (Startup, Liveness, Readiness)")
        self.phase = "Running"
        log_event("Kubelet", "Menjalankan StartupProbe untuk web-service...", "PROBE", Color.CYAN)
        time.sleep(0.5)
        app.run_probe("Startup", True)

        log_event("Kubelet", "Menjalankan ReadinessProbe & LivenessProbe...", "PROBE", Color.CYAN)
        time.sleep(0.5)
        app.run_probe("Readiness", True)
        app.run_probe("Liveness", True)
        log_event("Kube-Proxy", f"Endpoint Pod {self.name} ditambahkan ke Service Target Pool.", "READY", Color.GREEN)

        print_step(4, "Fase Terminasi Anggun (PreStop Hook -> SIGTERM -> SIGKILL)")
        log_event("API-Server", f"Menerima perintah delete pod/{self.name} (Grace Period: 30s)", "DELETE", Color.YELLOW)
        self.phase = "Terminating"
        log_event("Kube-Proxy", f"Endpoint Pod {self.name} dicopot dari EndpointSlice (Traffic Stopped)", "REMOVE", Color.RED)

        threads = []
        for c in self.app_containers:
            t = threading.Thread(target=c.stop, args=(3,))
            threads.append(t)
            t.start()
        for t in threads:
            t.join()

        self.phase = "Succeeded"
        log_event("Kubelet", f"Semua container berhenti. Pod {self.name} masuk fase Succeeded.", "DONE", Color.GREEN)

    def simulate_sidecar_pattern(self):
        print_header("MULTI-CONTAINER PATTERN: SIDECAR (Shared Volume Logging)")
        print(f"{Color.BOLD}Skenario:{Color.RESET} Kontainer aplikasi utama menulis log ke shared emptyDir volume.")
        print(f"Kontainer Sidecar (Log Shipper) membaca dan mengirimkan log tersebut ke server terpusat.\n")

        self.shared_volume["app.log"] = ""
        log_entries = [
            "2026-10-06 00:01:05 [INFO] Request GET /api/v1/orders - 200 OK",
            "2026-10-06 00:01:06 [WARN] High latency on DB query: 320ms",
            "2026-10-06 00:01:08 [INFO] Request POST /api/v1/checkout - 201 Created"
        ]

        for entry in log_entries:
            time.sleep(0.7)
            log_event("app-backend", f"Menulis ke /var/log/app.log -> '{entry}'", "WRITE", Color.CYAN)
            self.shared_volume["app.log"] += entry + "\n"
            
            time.sleep(0.5)
            log_event("sidecar-shipper", f"Mendeteksi baris baru -> Meneruskan ke Elasticsearch / Loki", "FORWARD", Color.GREEN)

        print(f"\n{Color.GREEN}✔ Pola Sidecar Berhasil:{Color.RESET} Pemisahan tugas yang bersih antara core business logic dan log forwarding.")

    def simulate_ambassador_pattern(self):
        print_header("MULTI-CONTAINER PATTERN: AMBASSADOR (Local Proxy / Adapter)")
        print(f"{Color.BOLD}Skenario:{Color.RESET} Kontainer aplikasi hanya mengakses 'localhost:6379'.")
        print(f"Kontainer Ambassador menyembunyikan kompleksitas topologi Redis Cluster/Read-Write Splitting.\n")

        queries = [
            ("SET session:usr99 'active'", "WRITE"),
            ("GET session:usr99", "READ"),
            ("HGET customer:profile", "READ")
        ]

        for query, q_type in queries:
            time.sleep(0.6)
            log_event("app-frontend", f"Kirim query ke localhost:6379: '{query}'", "CLIENT", Color.CYAN)
            time.sleep(0.4)
            if q_type == "WRITE":
                log_event("ambassador-proxy", f"Mengarahkan {q_type} ke Redis Master Node (10.244.2.15:6379)", "ROUTING", Color.YELLOW)
            else:
                log_event("ambassador-proxy", f"Mengarahkan {q_type} ke Redis Read Replica Pool (10.244.3.88:6379)", "ROUTING", Color.GREEN)

        print(f"\n{Color.GREEN}✔ Pola Ambassador Berhasil:{Color.RESET} Aplikasi tidak perlu tahu konfigurasi redis cluster; cukup berbicara ke localhost.")

    def simulate_adapter_pattern(self):
        print_header("MULTI-CONTAINER PATTERN: ADAPTER (Metrics Standardizer)")
        print(f"{Color.BOLD}Skenario:{Color.RESET} Aplikasi legacy menghasilkan metrics dalam format custom key-value.")
        print(f"Kontainer Adapter menstandarkan format ke OpenMetrics / Prometheus Exposition format.\n")

        raw_metrics = [
            "memory_usage=782MB,disk_io=120io/s",
            "active_tasks=42,failed_tasks=1"
        ]

        for raw in raw_metrics:
            time.sleep(0.7)
            log_event("legacy-service", f"Generate raw internal metrics: '{raw}'", "RAW", Color.CYAN)
            time.sleep(0.5)
            transformed = "\n".join([f"# TYPE legacy_{k} gauge\nlegacy_{k} {v}" for k, v in [x.split('=') for x in raw.split(',')]])
            log_event("adapter-prometheus", f"Transformasi ke Prometheus metrics endpoint (/metrics):", "ADAPT", Color.MAGENTA)
            for line in transformed.split('\n'):
                print(f"       {Color.DIM}│ {line}{Color.RESET}")

        print(f"\n{Color.GREEN}✔ Pola Adapter Berhasil:{Color.RESET} Memodernisasi monitoring tanpa merombak source code aplikasi legacy.")

    def simulate_failure_loop(self):
        print_header("SIMULASI KEGAGALAN: CrashLoopBackOff & Liveness Failure")
        print(f"{Color.BOLD}Skenario:{Color.RESET} Aplikasi mengalami Out-Of-Memory (OOM) atau deadlock,")
        print(f"menyebabkan Liveness Probe gagal berulang kali dan memicu back-off restart.\n")

        app = Container("flaky-api", "Main API")
        app.start(0.4)
        
        for attempt in range(1, 4):
            time.sleep(0.6)
            print_step(attempt, f"Percobaan Siklus Deteksi Kegagalan Ke-{attempt}")
            log_event("flaky-api", "Memory leak terjadi! Aplikasi membeku (Deadlock)...", "WARN", Color.YELLOW)
            time.sleep(0.5)
            app.run_probe("Liveness", False)
            app.restart_count += 1
            backoff_delay = 2 ** attempt
            log_event("Kubelet", f"Liveness probe gagal 3x berturut-turut! Restarting container...", "RESTART", Color.RED)
            log_event("Kubelet", f"Fase: CrashLoopBackOff. Menunggu backoff {backoff_delay} detik sebelum restart ke-{app.restart_count}.", "BACKOFF", Color.MAGENTA)

        print(f"\n{Color.RED}✖ Diagnosa Kubelet:{Color.RESET} Pod berada di CrashLoopBackOff dengan {app.restart_count} restarts.")

def show_menu():
    print(f"\n{Color.BOLD}{Color.WHITE}=== LABORATORIUM INTERAKTIF POD LIFECYCLE & MULTI-CONTAINER ==={Color.RESET}")
    print(f"{Color.CYAN}1.{Color.RESET} Jalankan Siklus Penuh Pod (Init -> Ready -> Graceful Stop)")
    print(f"{Color.CYAN}2.{Color.RESET} Simulasi Pola Multi-Container: {Color.BOLD}Sidecar{Color.RESET} (Log Forwarding)")
    print(f"{Color.CYAN}3.{Color.RESET} Simulasi Pola Multi-Container: {Color.BOLD}Ambassador{Color.RESET} (Redis Proxy)")
    print(f"{Color.CYAN}4.{Color.RESET} Simulasi Pola Multi-Container: {Color.BOLD}Adapter{Color.RESET} (Prometheus Metric Standardizer)")
    print(f"{Color.CYAN}5.{Color.RESET} Simulasi Skenario Kegagalan: {Color.BOLD}CrashLoopBackOff{Color.RESET} & Liveness Failures")
    print(f"{Color.CYAN}6.{Color.RESET} Jalankan Seluruh Demonstrasi Otomatis")
    print(f"{Color.CYAN}0.{Color.RESET} Keluar")
    print(f"{Color.WHITE}Pilih opsi [0-6]: {Color.RESET}", end="", flush=True)

def main():
    sim = PodSimulator(name="ecommerce-checkout-pod-7df84", namespace="production")

    # If run with non-interactive argument or in piped mode without stdin
    if len(sys.argv) > 1 and sys.argv[1] in ["--demo", "--all", "-a"]:
        sim.run_full_lifecycle()
        sim.simulate_sidecar_pattern()
        sim.simulate_ambassador_pattern()
        sim.simulate_adapter_pattern()
        sim.simulate_failure_loop()
        print(f"\n{Color.GREEN}{Color.BOLD}Semua simulasi berhasil dijalankan!{Color.RESET}\n")
        return

    if not sys.stdin.isatty():
        # Running automated test or pipe
        print(f"{Color.YELLOW}Deteksi mode non-TTY: Menjalankan demo otomatis siklus penuh...{Color.RESET}")
        sim.run_full_lifecycle()
        sim.simulate_sidecar_pattern()
        sim.simulate_ambassador_pattern()
        sim.simulate_adapter_pattern()
        return

    while True:
        try:
            show_menu()
            choice = input().strip()
            if choice == "1":
                sim.run_full_lifecycle()
            elif choice == "2":
                sim.simulate_sidecar_pattern()
            elif choice == "3":
                sim.simulate_ambassador_pattern()
            elif choice == "4":
                sim.simulate_adapter_pattern()
            elif choice == "5":
                sim.simulate_failure_loop()
            elif choice == "6":
                sim.run_full_lifecycle()
                sim.simulate_sidecar_pattern()
                sim.simulate_ambassador_pattern()
                sim.simulate_adapter_pattern()
                sim.simulate_failure_loop()
            elif choice in ["0", "q", "exit"]:
                print(f"\n{Color.CYAN}Terima kasih telah menjalankan simulasi Kubernetes Pod Lifecycle!{Color.RESET}")
                break
            else:
                print(f"{Color.RED}Pilihan tidak valid. Silakan pilih 0-6.{Color.RESET}")
        except (KeyboardInterrupt, EOFError):
            print(f"\n\n{Color.YELLOW}Simulasi dihentikan oleh pengguna.{Color.RESET}")
            break

if __name__ == "__main__":
    main()
