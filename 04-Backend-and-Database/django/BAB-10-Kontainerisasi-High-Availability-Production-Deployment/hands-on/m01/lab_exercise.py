#!/usr/bin/env python3
"""
Lab Exercise M01: Django Production, High Availability & Containerization Simulation
BAB 10: Kontainerisasi, High Availability, dan Production Deployment

Simulasi interaktif mandiri yang mengemulasi:
1. WSGI/ASGI Worker Topology (Gunicorn / Uvicorn master-worker model)
2. Reverse Proxy Load Balancing & Upstream Health Probes (Liveness & Readiness)
3. Zero-Downtime Blue-Green Deployment & Traffic Shift
4. Database Connection Pool & Circuit Breaker under Stress
"""

import sys
import time
import random
from dataclasses import dataclass, field
from typing import List, Dict, Optional

# ANSI Color Codes for terminal formatting
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"
DIM = "\033[2m"


@dataclass
class WorkerProcess:
    worker_id: int
    pid: int
    worker_type: str  # 'gunicorn-sync' or 'uvicorn-worker'
    status: str = "ALIVE"  # ALIVE, BUSY, CRASHED
    memory_mb: float = 45.0
    requests_served: int = 0
    heartbeat_time: float = field(default_factory=time.time)

    def is_healthy(self) -> bool:
        return self.status != "CRASHED" and (time.time() - self.heartbeat_time < 5.0)


@dataclass
class ContainerInstance:
    name: str
    version: str
    ip_address: str
    status: str = "RUNNING"  # STARTING, RUNNING, DRAINING, STOPPED
    is_ready: bool = False
    active_connections: int = 0
    workers: List[WorkerProcess] = field(default_factory=list)

    def readiness_check(self) -> bool:
        """Simulates Django /healthz/readiness probe (DB ping + Cache ping)."""
        return self.status == "RUNNING" and self.is_ready

    def liveness_check(self) -> bool:
        """Simulates Django /healthz/liveness probe (Process alive)."""
        return self.status in ("RUNNING", "DRAINING")


class ProductionClusterSimulator:
    def __init__(self):
        self.blue_cluster: List[ContainerInstance] = [
            ContainerInstance("django-app-blue-1", "v1.2.0", "10.0.1.11", is_ready=True),
            ContainerInstance("django-app-blue-2", "v1.2.0", "10.0.1.12", is_ready=True),
        ]
        self.green_cluster: List[ContainerInstance] = []
        self.active_color = "BLUE"
        self.db_pool_capacity = 20
        self.db_active_conns = 4
        self._init_workers()

    def _init_workers(self):
        for node in self.blue_cluster:
            node.workers = [
                WorkerProcess(worker_id=1, pid=1010 + random.randint(1, 900), worker_type="uvicorn.workers.UvicornWorker"),
                WorkerProcess(worker_id=2, pid=2010 + random.randint(1, 900), worker_type="uvicorn.workers.UvicornWorker"),
            ]

    def display_topology(self):
        print(f"\n{BOLD}{CYAN}=== INFRASTRUCTURE CLUSTER TOPOLOGY ==={RESET}")
        print(f"Active Production Routing : {BOLD}{GREEN if self.active_color == 'BLUE' else MAGENTA}{self.active_color}{RESET}")
        print(f"PostgreSQL Pool Usage     : {self.db_active_conns}/{self.db_pool_capacity} active connections\n")

        print(f"{BOLD}[BLUE POOL (Active Target)]{RESET}")
        for c in self.blue_cluster:
            r_tag = f"{GREEN}READY{RESET}" if c.readiness_check() else f"{RED}NOT READY{RESET}"
            l_tag = f"{GREEN}LIVE{RESET}" if c.liveness_check() else f"{RED}DEAD{RESET}"
            print(f"  * Node: {c.name:20} IP: {c.ip_address:12} Ver: {c.version} Status: {c.status:8} [R: {r_tag}, L: {l_tag}]")
            for w in c.workers:
                w_status = f"{GREEN}{w.status}{RESET}" if w.status == "ALIVE" else f"{RED}{w.status}{RESET}"
                print(f"      |- Worker #{w.worker_id} (PID: {w.pid}) Type: {w.worker_type} Mem: {w.memory_mb:.1f}MB Status: {w_status} Served: {w.requests_served}")

        if self.green_cluster:
            print(f"\n{BOLD}[GREEN POOL (Staging / Next Target)]{RESET}")
            for c in self.green_cluster:
                r_tag = f"{GREEN}READY{RESET}" if c.readiness_check() else f"{YELLOW}WARMING UP{RESET}"
                l_tag = f"{GREEN}LIVE{RESET}" if c.liveness_check() else f"{RED}DEAD{RESET}"
                print(f"  * Node: {c.name:20} IP: {c.ip_address:12} Ver: {c.version} Status: {c.status:8} [R: {r_tag}, L: {l_tag}]")
                for w in c.workers:
                    w_status = f"{GREEN}{w.status}{RESET}" if w.status == "ALIVE" else f"{RED}{w.status}{RESET}"
                    print(f"      |- Worker #{w.worker_id} (PID: {w.pid}) Status: {w_status} Mem: {w.memory_mb:.1f}MB")
        else:
            print(f"\n{DIM}[GREEN POOL: Standby / Offline]{RESET}")

    def simulate_traffic_and_worker_failure(self):
        print(f"\n{BOLD}{YELLOW}>> Menjalankan Simulasi Stress Traffic & OOM-Killer pada Worker...{RESET}")
        time.sleep(0.5)
        target_nodes = self.blue_cluster if self.active_color == "BLUE" else self.green_cluster
        if not target_nodes:
            print(f"{RED}Error: Tidak ada node aktif!{RESET}")
            return

        total_reqs = 50
        print(f"Mengirim {total_reqs} request konkurensi melalui Nginx upstream proxy...")

        crashed_worker: Optional[WorkerProcess] = None
        for i in range(1, total_reqs + 1):
            node = random.choice(target_nodes)
            worker = random.choice(node.workers)
            worker.requests_served += 1
            worker.memory_mb += random.uniform(0.8, 2.5)

            # Simulasi memory leak threshold
            if worker.memory_mb > 65.0 and worker.status == "ALIVE" and not crashed_worker:
                worker.status = "CRASHED"
                crashed_worker = worker
                print(f"{RED}[ALERT] Worker PID {worker.pid} di {node.name} melebihi limit memori! OOM Killed (SIGKILL).{RESET}")

        print(f"{GREEN}Traffic selesai diproses.{RESET}")
        if crashed_worker:
            print(f"\n{BOLD}{CYAN}[GUNICORN MASTER PROCESS SUPERVISOR]{RESET}")
            print(f"Master mendeteksi worker PID {crashed_worker.pid} silent / crash.")
            time.sleep(0.6)
            new_pid = crashed_worker.pid + 100
            crashed_worker.pid = new_pid
            crashed_worker.status = "ALIVE"
            crashed_worker.memory_mb = 42.0
            crashed_worker.heartbeat_time = time.time()
            print(f"{GREEN}[RECOVERY] Master me-respawn worker baru PID {new_pid} [Status: ALIVE]. Zero HTTP 502 dropped.{RESET}")

    def run_zero_downtime_blue_green(self):
        print(f"\n{BOLD}{MAGENTA}=== MEMULAI ZERO-DOWNTIME BLUE-GREEN DEPLOYMENT (v1.2.0 -> v1.3.0) ==={RESET}")
        time.sleep(0.5)

        # Step 1: Deploy Green
        print(f"\n1. {BOLD}Provisioning Green Environment (Docker Container v1.3.0)...{RESET}")
        self.green_cluster = [
            ContainerInstance("django-app-green-1", "v1.3.0", "10.0.2.21", status="STARTING", is_ready=False),
            ContainerInstance("django-app-green-2", "v1.3.0", "10.0.2.22", status="STARTING", is_ready=False),
        ]
        for node in self.green_cluster:
            node.workers = [
                WorkerProcess(1, 3010 + random.randint(1, 900), "uvicorn.workers.UvicornWorker"),
                WorkerProcess(2, 4010 + random.randint(1, 900), "uvicorn.workers.UvicornWorker"),
            ]
        print(f"   Node Green berhasil dibuat: status STARTING.")
        time.sleep(0.6)

        # Step 2: Database Migration Check
        print(f"\n2. {BOLD}Checking Database Backward Compatibility & Migration Contract...{RESET}")
        print(f"   {GREEN}[OK]{RESET} Skema database aditif (backward-compatible dengan v1.2.0).")
        print(f"   Menjalankan: 'python manage.py migrate --noinput'...")
        time.sleep(0.4)
        print(f"   {GREEN}[OK]{RESET} Migrasi skema selesai tanpa lock tabel eksklusif.")

        # Step 3: Readiness Probe & Warm-up
        print(f"\n3. {BOLD}Executing Kubernetes / Load-Balancer Readiness Probes on Green...{RESET}")
        for node in self.green_cluster:
            print(f"   Probing GET http://{node.ip_address}:8000/healthz/ready ...", end=" ")
            time.sleep(0.3)
            node.status = "RUNNING"
            node.is_ready = True
            print(f"{GREEN}HTTP 200 OK (DB pool ready, Cache warmed){RESET}")

        # Step 4: Traffic Cutover at Nginx / Ingress
        print(f"\n4. {BOLD}Switching Upstream Traffic in Nginx Configuration (Blue -> Green)...{RESET}")
        print(f"   Reloading Nginx with zero dropped packets (`nginx -s reload`)...")
        time.sleep(0.5)
        self.active_color = "GREEN"
        print(f"   {GREEN}{BOLD}Traffic sukses dialihkan 100% ke GREEN CLUSTER (v1.3.0)!{RESET}")

        # Step 5: Graceful Draining of Blue
        print(f"\n5. {BOLD}Graceful Shutdown & Connection Draining on Blue Cluster...{RESET}")
        for node in self.blue_cluster:
            node.status = "DRAINING"
            print(f"   Node {node.name}: Mengirim SIGTERM ke Gunicorn master. Menunggu koneksi aktif selesai...")
            time.sleep(0.3)
            node.status = "STOPPED"
            node.is_ready = False
            for w in node.workers:
                w.status = "STOPPED"
        print(f"   {GREEN}[SUCCESS] Semua container Blue selesai drain dan safe dihentikan.{RESET}")

    def simulate_circuit_breaker(self):
        print(f"\n{BOLD}{RED}=== SIMULASI CHAOS: DATABASE CONNECTION EXHAUSTION & CIRCUIT BREAKER ==={RESET}")
        print(f"Kapasitas Connection Pool PostgreSQL: {self.db_pool_capacity}")
        print("Menerima lonjakan traffic tak terduga (Thundering Herd)...")
        time.sleep(0.4)

        self.db_active_conns = self.db_pool_capacity
        print(f"{YELLOW}[WARN] Connection pool jenuh ({self.db_active_conns}/{self.db_pool_capacity})!{RESET}")
        time.sleep(0.4)

        print(f"{RED}[CIRCUIT BREAKER: TRIPPED -> OPEN]{RESET}")
        print(f"1. Django Healthz endpoint merespon: {YELLOW}503 Service Unavailable{RESET}")
        print(f"2. Nginx menghentikan pengiriman request ke worker yang overload.")
        print(f"3. Fallback cache diaktifkan (Read-only static stale data disajikan ke user).")
        time.sleep(0.6)

        print(f"\n{BOLD}{GREEN}Pemulihan Pool (PgBouncer Auto-reap idle connections)...{RESET}")
        self.db_active_conns = 5
        print(f"Koneksi aktif kembali normal ({self.db_active_conns}/{self.db_pool_capacity}).")
        print(f"{GREEN}[CIRCUIT BREAKER: CLOSED] Sistem kembali melayani write request normal.{RESET}")


def main():
    cluster = ProductionClusterSimulator()

    # Non-interactive automated smoke test when run in CI/headless mode
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        print(f"{BOLD}{GREEN}Running automated verification suite...{RESET}")
        cluster.display_topology()
        cluster.simulate_traffic_and_worker_failure()
        cluster.run_zero_downtime_blue_green()
        cluster.simulate_circuit_breaker()
        print(f"\n{BOLD}{GREEN}[VERIFIKASI BERHASIL] Seluruh skenario produksi berjalan sempurna.{RESET}")
        sys.exit(0)

    while True:
        print(f"\n{BOLD}{BLUE}===================================================================={RESET}")
        print(f"{BOLD}{CYAN}   LAB M01: DJANGO HIGH-AVAILABILITY & PRODUCTION SIMULATOR{RESET}")
        print(f"{BOLD}{BLUE}===================================================================={RESET}")
        print(" [1] Lihat Topologi Cluster & Status Worker (Gunicorn/Uvicorn)")
        print(" [2] Simulasi High-Traffic & OOM Worker Recovery (Gunicorn Supervisor)")
        print(" [3] Simulasi Zero-Downtime Blue-Green Deployment")
        print(" [4] Simulasi Chaos: DB Pool Exhaustion & Circuit Breaker")
        print(" [5] Jalankan Seluruh Skenario Otomatis (Full Verification)")
        print(" [0] Keluar (Exit)")
        print(f"{DIM}--------------------------------------------------------------------{RESET}")

        try:
            choice = input(f"{BOLD}Pilih menu [0-5]: {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{YELLOW}Sesi diakhiri.{RESET}")
            break

        if choice == "1":
            cluster.display_topology()
        elif choice == "2":
            cluster.simulate_traffic_and_worker_failure()
        elif choice == "3":
            cluster.run_zero_downtime_blue_green()
        elif choice == "4":
            cluster.simulate_circuit_breaker()
        elif choice == "5":
            cluster.display_topology()
            cluster.simulate_traffic_and_worker_failure()
            cluster.run_zero_downtime_blue_green()
            cluster.simulate_circuit_breaker()
            print(f"\n{BOLD}{GREEN}Semua skenario pengujian berhasil disimulasikan!{RESET}")
        elif choice == "0":
            print(f"{GREEN}Terima kasih telah menjalankan simulasi Django High Availability!{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak valid. Silakan pilih 0-5.{RESET}")


if __name__ == "__main__":
    main()
