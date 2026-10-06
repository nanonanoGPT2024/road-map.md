#!/usr/bin/env python3
"""
Simulasi Interaktif: Ruby on Rails Containerization, Kamal Deployment & SRE Operations
BAB 10: Containerization, Kamal Deployment, & SRE

Skrip ini mendemonstrasikan simulasi teknis siklus hidup:
1. Docker Multi-Stage Build untuk Rails (Asset Precompilation, Jemalloc, Minimal Image Size)
2. Kamal Deployment Flow (Lock acquisition, Docker build/push, Traefik routing, Zero-downtime swap)
3. SRE Health Checking & Automated Rollback
4. Container Signal Trapping (SIGTERM vs SIGQUIT) & Graceful Puma/Sidekiq Drain
"""

import sys
import time
import random
from dataclasses import dataclass
from typing import List, Dict, Optional

# ANSI Color Codes untuk Terminal Styling
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BG_DARK = "\033[40m"


def print_banner():
    banner = f"""
{Color.CYAN}{Color.BOLD}======================================================================
  RAILS PRODUCTION SRE: CONTAINERIZATION & KAMAL DEPLOYMENT SIMULATOR
  Bab 10: Docker Multi-Stage, Kamal 2 Traefik Coordination, & Resilience
======================================================================{Color.RESET}
"""
    print(banner)


def status_badge(text: str, success: bool) -> str:
    if success:
        return f"{Color.GREEN}[PASS: {text}]{Color.RESET}"
    return f"{Color.RED}[FAIL: {text}]{Color.RESET}"


class DockerBuildSimulator:
    """Simulasi Multi-Stage Dockerfile untuk Rails 7.2+ dengan Jemalloc"""
    def __init__(self, app_name: str = "rails-fintech-core"):
        self.app_name = app_name
        self.stages = [
            ("Stage 1: Base Runtime", "Instalasi jemalloc, libvips, timezone data"),
            ("Stage 2: Build Dependencies", "Instalasi compiler, libpq-dev, nodejs, bun"),
            ("Stage 3: Gem & Asset Compilation", "bundle install --deployment & assets:precompile"),
            ("Stage 4: Final Image Assembly", "Copy build artifacts, non-root user, strip cache"),
        ]

    def run_build(self):
        print(f"\n{Color.BOLD}{Color.BLUE}>>> 1. MULTI-STAGE DOCKER BUILD SIMULATION ({self.app_name}){Color.RESET}")
        time.sleep(0.3)
        total_size_mb = 1250

        for idx, (stage_name, desc) in enumerate(self.stages, 1):
            print(f"  {Color.YELLOW}[{idx}/4] {stage_name}...{Color.RESET}")
            print(f"       -> Detail: {desc}")
            time.sleep(0.4)
            if idx == 3:
                print(f"       -> {Color.MAGENTA}SECRET_KEY_BASE_DUMMY=1 bin/rails assets:precompile{Color.RESET}")
                time.sleep(0.3)

        final_size = 184
        saved = total_size_mb - final_size
        print(f"\n  {status_badge('DOCKER IMAGE READY', True)}")
        print(f"  Single-stage raw size: {total_size_mb} MB | Multi-stage slim size: {Color.GREEN}{Color.BOLD}{final_size} MB{Color.RESET}")
        print(f"  Image optimization efficiency: {Color.CYAN}{(saved / total_size_mb) * 100:.1f}% reduction{Color.RESET}\n")


@dataclass
class ContainerInstance:
    cid: str
    version: str
    port: int
    healthy: bool
    traffic_weight: int


class KamalDeployerSimulator:
    """Simulasi Orkestrasi Kamal: Lock -> Build -> Boot Old/New -> Healthcheck -> Traefik Swap -> Prune"""
    def __init__(self, current_version: str = "v1.2.0"):
        self.current_version = current_version
        self.running_containers: List[ContainerInstance] = [
            ContainerInstance(cid="c_a1b2c3d4", version=current_version, port=3000, healthy=True, traffic_weight=100)
        ]

    def deploy_new_version(self, target_version: str, induce_failure: bool = False):
        print(f"{Color.BOLD}{Color.MAGENTA}>>> 2. KAMAL DEPLOYMENT ORCHESTRATION ({self.current_version} -> {target_version}){Color.RESET}")
        time.sleep(0.3)

        print(f"  [1/6] {Color.CYAN}Kamal Lock:{Color.RESET} Menyiapkan distributed deploy lock di host...")
        time.sleep(0.3)
        print(f"        Lock didapatkan oleh host operator (PID {random.randint(1000, 9999)})")

        new_cid = f"c_{random.randint(100000, 999999):x}"
        new_port = 3001
        print(f"  [2/6] {Color.CYAN}Boot Container Baru:{Color.RESET} Menjalankan {target_version} pada port {new_port} ({new_cid})...")
        time.sleep(0.4)

        print(f"  [3/6] {Color.CYAN}Kamal Healthcheck:{Color.RESET} Polling GET /up (Rails 7.2 health endpoint)...")
        time.sleep(0.5)

        is_healthy = not induce_failure
        if is_healthy:
            print(f"        Health check response: {Color.GREEN}200 OK (DB connected, Redis connected, Disk OK){Color.RESET}")
            new_container = ContainerInstance(cid=new_cid, version=target_version, port=new_port, healthy=True, traffic_weight=0)
            
            print(f"  [4/6] {Color.CYAN}Traefik Dynamic Routing Switch:{Color.RESET}")
            print(f"        Routing 100% request traffic to {target_version} ({new_cid})...")
            time.sleep(0.4)
            self.running_containers[0].traffic_weight = 0
            new_container.traffic_weight = 100
            self.running_containers.append(new_container)
            
            print(f"  [5/6] {Color.CYAN}Graceful Drain (SIGTERM):{Color.RESET} Menunggu in-flight requests {self.current_version} selesai...")
            time.sleep(0.4)
            
            print(f"  [6/6] {Color.CYAN}Container Stop & Prune:{Color.RESET} Menghentikan versi lama {self.current_version}...")
            time.sleep(0.3)
            self.running_containers.pop(0)
            self.current_version = target_version
            print(f"  {status_badge('DEPLOYMENT ZERO-DOWNTIME SUCCESSFUL', True)}\n")
        else:
            print(f"        Health check response: {Color.RED}500 Internal Server Error (Database migration pending!){Color.RESET}")
            print(f"  {Color.RED}{Color.BOLD}>>> SRE ALERT: Kamal automated rollback sequence triggered!{Color.RESET}")
            time.sleep(0.4)
            print(f"  [Rollback 1/2] Traefik routing tetap terkunci pada versi stabil {self.current_version}...")
            print(f"  [Rollback 2/2] Menghentikan dan menghapus container cacat {new_cid}...")
            time.sleep(0.3)
            print(f"  {status_badge('ROLLBACK COMPLETED - ZERO DOWNTIME MAINTAINED', True)}\n")


class SignalDrainSimulator:
    """Simulasi Penanganan UNIX Signals (SIGTERM vs SIGQUIT) pada Puma / Sidekiq"""
    def run_drain_test(self):
        print(f"{Color.BOLD}{Color.YELLOW}>>> 3. SRE RESILIENCE: CONTAINER SIGNAL HANDLING & GRACEFUL DRAIN{Color.RESET}")
        time.sleep(0.3)

        jobs = [
            {"id": "job_01", "name": "SendReceiptEmail", "runtime_left": 1.5},
            {"id": "job_02", "name": "ProcessStripeWebhook", "runtime_left": 2.2},
            {"id": "job_03", "name": "GenerateMonthlyReport", "runtime_left": 8.0},
        ]

        print("  State saat ini: Puma Web Server (4 workers) + Sidekiq Worker (3 active jobs)")
        print(f"  Mengirimkan sinyal: {Color.RED}{Color.BOLD}SIGTERM (Kamal timeout budget: 5.0s){Color.RESET}")
        time.sleep(0.4)

        print("  [Sidekiq] Menerima SIGTERM: Menyetop fetching job baru dari Redis.")
        print("  [Sidekiq] Mengosongkan in-flight jobs:")

        timeout_budget = 5.0
        elapsed = 0.0
        for job in jobs:
            if job["runtime_left"] <= timeout_budget:
                time.sleep(0.3)
                print(f"    - {job['id']} ({job['name']}): {Color.GREEN}Selesai dalam {job['runtime_left']}s. Clean exit.{Color.RESET}")
                elapsed = max(elapsed, job["runtime_left"])
            else:
                time.sleep(0.3)
                print(f"    - {job['id']} ({job['name']}): {Color.YELLOW}Membutuhkan {job['runtime_left']}s (> {timeout_budget}s).{Color.RESET}")
                print(f"      -> Re-enqueued back to Redis queue (At-Least-Once Delivery).")

        print(f"  [Puma] HTTP Keep-Alive connection terminated cleanly.")
        print(f"  {status_badge('GRACEFUL DRAIN FINISHED WITHIN BUDGET', True)}\n")


def interactive_menu():
    print_banner()
    builder = DockerBuildSimulator()
    deployer = KamalDeployerSimulator(current_version="v2.4.0")
    drainer = SignalDrainSimulator()

    while True:
        print(f"{Color.BOLD}PILIHAN LAB INTERAKTIF:{Color.RESET}")
        print("  [1] Jalankan Simulasi Docker Multi-Stage Build")
        print("  [2] Jalankan Simulasi Kamal Deploy Normal (Zero-Downtime)")
        print("  [3] Jalankan Simulasi Kamal Deploy Gagal (Automated Healthcheck Rollback)")
        print("  [4] Jalankan Simulasi SRE Signal Handling (SIGTERM & Job Re-enqueuing)")
        print("  [5] Jalankan SEMUA Modul Simulasi Sekaligus")
        print("  [0] Keluar")

        try:
            choice = input(f"\n{Color.CYAN}Masukkan nomor modul [0-5]: {Color.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Color.YELLOW}Keluar dari lab.{Color.RESET}")
            sys.exit(0)

        if choice == "1":
            builder.run_build()
        elif choice == "2":
            deployer.deploy_new_version("v2.5.0", induce_failure=False)
        elif choice == "3":
            deployer.deploy_new_version("v2.5.1-broken", induce_failure=True)
        elif choice == "4":
            drainer.run_drain_test()
        elif choice == "5":
            builder.run_build()
            deployer.deploy_new_version("v2.5.0", induce_failure=False)
            deployer.deploy_new_version("v2.5.1-broken", induce_failure=True)
            drainer.run_drain_test()
            print(f"{Color.GREEN}{Color.BOLD}>>> SELURUH SIMULASI SRE SELESAI DIEKSEKUSI! <<<{Color.RESET}\n")
        elif choice == "0":
            print(f"{Color.GREEN}Terima kasih telah menjalankan lab BAB 10!{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid. Silakan pilih 0-5.{Color.RESET}\n")


if __name__ == "__main__":
    interactive_menu()
