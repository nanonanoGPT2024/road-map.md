#!/usr/bin/env python3
"""
Lab Hands-on: Containerization, Automated Testing, & Enterprise Rolling Deployment
Modul 02 Deep Dive - 01-Core-Foundations / Chapter 10

Script ini mensimulasikan arsitektur container orchestration tingkat enterprise:
1. Container Lifecycle & State Machine (PENDING -> RUNNING -> HEALTHY -> DRAINING -> TERMINATED).
2. Liveness & Readiness Probes (Kontrak pengujian internal microservice).
3. Zero-Downtime Rolling Deployment Engine (Blue/Green atau Canary Transition).
4. Smoke Testing Suite & Automated Rollback mechanism jika probe gagal.
"""

import sys
import time
import random
import threading
from enum import Enum
from typing import List, Dict, Optional
from dataclasses import dataclass, field

# --- Terminal Styling (ANSI Escape Codes) ---
CLR_RESET  = "\033[0m"
CLR_BOLD   = "\033[1m"
CLR_RED    = "\033[91m"
CLR_GREEN  = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE   = "\033[94m"
CLR_CYAN   = "\033[96m"

def log_info(msg: str) -> None:
    print(f"{CLR_CYAN}[INFO]{CLR_RESET} {msg}")

def log_success(msg: str) -> None:
    print(f"{CLR_GREEN}[PASS]{CLR_RESET} {msg}")

def log_warn(msg: str) -> None:
    print(f"{CLR_YELLOW}[WARN]{CLR_RESET} {msg}")

def log_err(msg: str) -> None:
    print(f"{CLR_RED}[FAIL]{CLR_RESET} {msg}")


class ContainerState(Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    HEALTHY = "HEALTHY"
    UNHEALTHY = "UNHEALTHY"
    DRAINING = "DRAINING"
    TERMINATED = "TERMINATED"


@dataclass
class ContainerInstance:
    """
    Representasi instance container isolated dengan metrik runtime internal.
    """
    id: str
    image_tag: str
    port: int
    state: ContainerState = ContainerState.PENDING
    handled_requests: int = 0
    failure_budget: float = 0.0  # Tingkat eror yang diinjeksikan untuk simulasi (0.0 - 1.0)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def boot(self) -> None:
        """Simulasi startup container & inisialisasi environment."""
        with self._lock:
            self.state = ContainerState.RUNNING

    def liveness_probe(self) -> bool:
        """
        Liveness check: Memastikan container runtime tidak mengalami deadlock.
        Jika gagal, orchestrator akan me-restart container.
        """
        with self._lock:
            if self.state in (ContainerState.TERMINATED, ContainerState.DRAINING):
                return False
            # Instance crash jika random float di bawah failure_budget
            return random.random() >= self.failure_budget

    def readiness_probe(self) -> bool:
        """
        Readiness check: Memastikan aplikasi siap melayani traffic (misal: koneksi DB valid).
        Traffic hanya diarahkan jika probe ini mengembalikan True.
        """
        with self._lock:
            if self.state != ContainerState.RUNNING and self.state != ContainerState.HEALTHY:
                return False
            is_ready = random.random() >= (self.failure_budget * 1.5)
            self.state = ContainerState.HEALTHY if is_ready else ContainerState.UNHEALTHY
            return is_ready

    def handle_request(self) -> bool:
        """Simulasi serving traffic API dari reverse proxy/load balancer."""
        with self._lock:
            if self.state != ContainerState.HEALTHY:
                return False
            self.handled_requests += 1
            return True

    def drain_and_terminate(self) -> None:
        """Graceful shutdown: Selesaikan request yang ada, tolak traffic baru (SIGTERM)."""
        with self._lock:
            self.state = ContainerState.DRAINING
        # Simulasi jeda graceful drain
        time.sleep(0.05)
        with self._lock:
            self.state = ContainerState.TERMINATED


class EnterpriseLoadBalancer:
    """
    Software-defined Load Balancer dengan algoritma Round-Robin
    yang hanya merutekan traffic ke instance berkondisi HEALTHY.
    """
    def __init__(self):
        self._index = 0
        self._lock = threading.Lock()

    def route_request(self, pool: List[ContainerInstance]) -> Optional[str]:
        with self._lock:
            healthy_pool = [c for c in pool if c.state == ContainerState.HEALTHY]
            if not healthy_pool:
                return None
            
            target = healthy_pool[self._index % len(healthy_pool)]
            self._index += 1
            success = target.handle_request()
            return target.id if success else None


class DeploymentOrchestrator:
    """
    Orchestration Controller yang mengelola zero-downtime rolling deployment,
    pengujian integrasi otomatis (readiness gates), dan rollback cerdas.
    """
    def __init__(self, desired_replicas: int = 4):
        self.desired_replicas = desired_replicas
        self.active_pool: List[ContainerInstance] = []
        self.lb = EnterpriseLoadBalancer()

    def bootstrap_cluster(self, image_tag: str) -> None:
        log_info(f"Bootstrapping cluster dengan {self.desired_replicas} replika. Image: {CLR_BOLD}{image_tag}{CLR_RESET}")
        for i in range(self.desired_replicas):
            instance = ContainerInstance(
                id=f"pod-{image_tag}-{i+1}",
                image_tag=image_tag,
                port=8080 + i
            )
            instance.boot()
            if instance.readiness_probe():
                self.active_pool.append(instance)
            else:
                log_err(f"Gagal inisialisasi pod: {instance.id}")
        self.print_pool_status()

    def print_pool_status(self) -> None:
        status_line = " | ".join(
            f"{c.id} [{CLR_GREEN if c.state == ContainerState.HEALTHY else CLR_RED}{c.state.value}{CLR_RESET}]"
            for c in self.active_pool
        )
        print(f"  Cluster Status: {status_line}")

    def execute_smoke_tests(self, instance: ContainerInstance) -> bool:
        """
        Pengujian otomatis pra-promosi (Smoke Test) untuk memvalidasi
        integritas rute kritis dan dependensi sebelum menerima traffic publik.
        """
        log_info(f"Menjalankan Synthetic Integration Smoke Tests pada {instance.id}...")
        tests = [
            ("Liveness Socket Probe", instance.liveness_probe),
            ("Readiness Endpoint Handshake", instance.readiness_probe),
            ("Mock DB Query Latency Test", lambda: random.random() > 0.05)
        ]
        
        for name, test_func in tests:
            time.sleep(0.04) # Simulasi latency I/O test
            if not test_func():
                log_err(f"Smoke Test Failed: {name} pada {instance.id}")
                return False
            log_success(f"Smoke Test Passed: {name}")
        return True

    def rolling_update(self, new_image_tag: str, inject_defect: bool = False) -> bool:
        """
        Eksekusi Rolling Deployment v1 -> v2 secara inkremental:
        1. Spawn instance baru.
        2. Jalankan health-check & test gates.
        3. Arahkan traffic ke instance baru.
        4. Drain & matikan instance lama.
        5. Jika ada kegagalan, jalankan Rollback otomatis!
        """
        print(f"\n{CLR_BOLD}=== MEMULAI ROLLING DEPLOYMENT KE: {new_image_tag} ==={CLR_RESET}")
        new_pool: List[ContainerInstance] = []
        old_pool = list(self.active_pool)

        for i, old_instance in enumerate(old_pool):
            new_id = f"pod-{new_image_tag}-{i+1}"
            log_info(f"Langkah {i+1}/{len(old_pool)}: Deploying {new_id}...")

            # Inisialisasi instance baru
            new_instance = ContainerInstance(
                id=new_id,
                image_tag=new_image_tag,
                port=9000 + i,
                failure_budget=0.95 if inject_defect else 0.0  # Defect injection
            )
            new_instance.boot()

            # Jalankan Automated Gate/Testing
            if not self.execute_smoke_tests(new_instance):
                log_err(f"Deployment ABORTED pada {new_id}! Memulai Prosedur Rollback Automatis...")
                new_instance.drain_and_terminate()
                self._rollback(new_pool)
                return False

            # Tambahkan ke active pool, gantikan old_instance secara bertahap
            self.active_pool.append(new_instance)
            new_pool.append(new_instance)

            log_info(f"Draining traffic dari instance lama: {old_instance.id}")
            old_instance.drain_and_terminate()
            self.active_pool.remove(old_instance)

            self.print_pool_status()
            time.sleep(0.1)

        log_success(f"Rolling Update ke {new_image_tag} BERHASIL 100% Zero-Downtime!")
        return True

    def _rollback(self, failed_new_instances: List[ContainerInstance]) -> None:
        """Membersihkan instance baru yang cacat dan memulihkan kestabilan."""
        log_warn("Mengeksekusi circuit breaker rollback: Membersihkan container baru...")
        for inst in failed_new_instances:
            inst.drain_and_terminate()
            if inst in self.active_pool:
                self.active_pool.remove(inst)
        log_info("Cluster kembali stabil ke status versi rilis stabil sebelumnya.")
        self.print_pool_status()

    def simulate_live_traffic(self, request_count: int = 50) -> None:
        """Simulasi beban traffic konkuren masuk ke cluster."""
        log_info(f"Mensimulasikan {request_count} HTTP requests melalui Load Balancer...")
        success_count = 0
        failed_count = 0

        for _ in range(request_count):
            routed_pod = self.lb.route_request(self.active_pool)
            if routed_pod:
                success_count += 1
            else:
                failed_count += 1
            time.sleep(0.002)

        availability = (success_count / request_count) * 100
        print(f"Traffic Result: {CLR_GREEN}{success_count} Berhasil{CLR_RESET}, "
              f"{CLR_RED}{failed_count} Gagal{CLR_RESET} | Availability: {availability:.2f}%")


def main() -> None:
    print(f"{CLR_BOLD}{CLR_BLUE}===================================================={CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_BLUE}   ENTERPRISE DEPLOYMENT & CONTAINER TEST ENGINE   {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_BLUE}===================================================={CLR_RESET}\n")

    # Inisialisasi orchestrator dengan 3 replika
    orchestrator = DeploymentOrchestrator(desired_replicas=3)

    # 1. Bootstrap State: Peluncuran App v1.0.0
    orchestrator.bootstrap_cluster(image_tag="v1.0.0")
    orchestrator.simulate_live_traffic(request_count=30)

    # 2. Skenario Sukses: Rolling Update ke App v1.1.0
    time.sleep(0.3)
    success = orchestrator.rolling_update(new_image_tag="v1.1.0", inject_defect=False)
    assert success, "Deployment v1.1.0 seharusnya sukses!"
    orchestrator.simulate_live_traffic(request_count=30)

    # 3. Skenario Gagal: Rolling Update ke App v1.2.0-broken (Memicu Rollback)
    time.sleep(0.3)
    success_bad = orchestrator.rolling_update(new_image_tag="v1.2.0-broken", inject_defect=True)
    assert not success_bad, "Deployment rusak seharusnya digagalkan oleh automated smoke test!"
    
    # 4. Validasi pasca-rollback: Cluster tetap melayani traffic tanpa downtime
    log_info("Memverifikasi Availability cluster setelah rollback...")
    orchestrator.simulate_live_traffic(request_count=30)

    print(f"\n{CLR_GREEN}{CLR_BOLD}✔ Lab Hands-on Eksekusi Sukses: Seluruh prinsip enterprise deployment tervalidasi.{CLR_RESET}\n")


if __name__ == "__main__":
    main()
