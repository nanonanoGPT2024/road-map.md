#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Teknis Multi-Container dengan Docker Compose
BAB-06 Multi-Container dengan Docker Compose
"""

import time
import sys
from typing import Dict, List, Set

# ANSI Color Codes
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


class Service:
    def __init__(self, name: str, image: str, ports: List[str], depends_on: Dict[str, str], healthcheck_cmd: str):
        self.name = name
        self.image = image
        self.ports = ports
        self.depends_on = depends_on
        self.healthcheck_cmd = healthcheck_cmd
        self.status = "stopped"
        self.health = "unknown"
        self.ip_address = ""

    def __repr__(self):
        return f"<Service {self.name} [{self.status}|{self.health}]>"


class DockerComposeSimulator:
    def __init__(self):
        self.network_name = "app_tier_network"
        self.subnet = "172.28.0.0/16"
        self.named_volumes = {"pgdata": "/var/lib/postgresql/data", "redis_data": "/data"}
        self.services: Dict[str, Service] = {
            "postgres": Service(
                name="postgres",
                image="postgres:15-alpine",
                ports=["5432:5432"],
                depends_on={},
                healthcheck_cmd="pg_isready -U postgres"
            ),
            "redis": Service(
                name="redis",
                image="redis:7-alpine",
                ports=["6379:6379"],
                depends_on={},
                healthcheck_cmd="redis-cli ping"
            ),
            "api_gateway": Service(
                name="api_gateway",
                image="fastapi-core:v1.2",
                ports=["8000:8000"],
                depends_on={"postgres": "service_healthy", "redis": "service_started"},
                healthcheck_cmd="curl -f http://localhost:8000/healthz"
            ),
            "worker": Service(
                name="worker",
                image="celery-worker:v1.2",
                ports=[],
                depends_on={"redis": "service_started", "postgres": "service_healthy"},
                healthcheck_cmd="celery inspect ping"
            )
        }

    def print_banner(self):
        print(f"{CYAN}{BOLD}======================================================================{RESET}")
        print(f"{CYAN}{BOLD}   LAB MULTI-CONTAINER SIMULATOR: DOCKER COMPOSE ENGINE LIFECYCLE     {RESET}")
        print(f"{CYAN}{BOLD}======================================================================{RESET}")
        print(f"{DIM}Project Namespace: bab06_multi_container | Drivers: bridge, local volume{RESET}\n")

    def display_compose_manifest(self):
        print(f"{YELLOW}{BOLD}[+] Manifest: docker-compose.yml Architecture{RESET}")
        manifest = f"""
services:
  postgres:
    image: postgres:15-alpine
    volumes: [pgdata:/var/lib/postgresql/data]
    networks: [{self.network_name}]
    healthcheck: test: ["CMD-SHELL", "pg_isready"]

  redis:
    image: redis:7-alpine
    volumes: [redis_data:/data]
    networks: [{self.network_name}]

  api_gateway:
    image: fastapi-core:v1.2
    ports: ["8000:8000"]
    depends_on:
      postgres: {{ condition: service_healthy }}
      redis: {{ condition: service_started }}
    networks: [{self.network_name}]

  worker:
    image: celery-worker:v1.2
    depends_on:
      redis: {{ condition: service_started }}
      postgres: {{ condition: service_healthy }}
    networks: [{self.network_name}]

networks:
  {self.network_name}:
    driver: bridge
"""
        print(f"{DIM}{manifest}{RESET}")

    def resolve_dag_order(self) -> List[str]:
        """Kalkulasi Directed Acyclic Graph (DAG) dependencies untuk urutan bootstrap."""
        order = []
        visited = set()
        temp_marked = set()

        def visit(node: str):
            if node in temp_marked:
                raise ValueError(f"Siklus dependency terdeteksi pada node {node}!")
            if node not in visited:
                temp_marked.add(node)
                for dep in self.services[node].depends_on.keys():
                    visit(dep)
                temp_marked.remove(node)
                visited.add(node)
                order.append(node)

        for svc_name in self.services.keys():
            if svc_name not in visited:
                visit(svc_name)
        return order

    def simulate_up(self):
        print(f"\n{BOLD}{CYAN}>>> Mengeksekusi 'docker compose up -d' <<<{RESET}")
        print(f"[*] Membuat bridge network: {GREEN}{self.network_name}{RESET} ({self.subnet})")
        time.sleep(0.3)
        for vol in self.named_volumes.keys():
            print(f"[*] Memastikan isolated volume: {GREEN}{vol}{RESET} terpasang")
            time.sleep(0.2)

        ordered_services = self.resolve_dag_order()
        print(f"[*] Resolved Topology Order via DAG: {YELLOW}{' -> '.join(ordered_services)}{RESET}\n")

        ip_counter = 10
        for svc_name in ordered_services:
            svc = self.services[svc_name]
            ip_counter += 1
            svc.ip_address = f"172.28.0.{ip_counter}"

            # Validasi dependency requirements
            for dep_name, condition in svc.depends_on.items():
                dep_svc = self.services[dep_name]
                print(f"[{svc.name}] Menunggu syarat {dep_name} -> {condition}...")
                if condition == "service_healthy" and dep_svc.health != "healthy":
                    print(f"[{svc.name}] {RED}ERROR: Dependency {dep_name} belum healthy!{RESET}")
                    return

            print(f"[{svc.name}] {CYAN}Creating container...{RESET} ({svc.image})")
            time.sleep(0.4)
            svc.status = "running"
            print(f"[{svc.name}] {GREEN}Container started{RESET} [IP: {svc.ip_address}]")

            # Simulasi healthcheck probe
            if "healthy" in [cond for cond in svc.depends_on.values()] or svc.name in ["postgres", "api_gateway"]:
                print(f"[{svc.name}] Menjalankan healthcheck: '{svc.healthcheck_cmd}'")
                for attempt in range(1, 4):
                    time.sleep(0.3)
                    print(f"    - Attempt {attempt}/3: probing socket...")
                svc.health = "healthy"
                print(f"[{svc.name}] Status health: {GREEN}HEALTHY (status code 0){RESET}")
            else:
                svc.health = "none"

            time.sleep(0.2)

        print(f"\n{GREEN}{BOLD}[+] Semua service berhasil beroperasi dalam mode detached (-d)!{RESET}")

    def simulate_dns_discovery(self):
        print(f"\n{BOLD}{YELLOW}>>> Simulasi Docker Embedded DNS (127.0.0.11) Resolution <<<{RESET}")
        running = [s for s in self.services.values() if s.status == "running"]
        if not running:
            print(f"{RED}Container belum berjalan. Jalankan simulasi 'up' terlebih dahulu!{RESET}")
            return

        print(f"Container '{CYAN}api_gateway{RESET}' mencoba komunikasi intra-network:")
        for target in ["postgres", "redis"]:
            target_svc = self.services[target]
            print(f" -> Resolving DNS '{target}' via 127.0.0.11...")
            time.sleep(0.3)
            print(f"    {GREEN}A Record match:{RESET} {target}.{self.network_name} -> {target_svc.ip_address}")
            print(f"    Ping latency to {target_svc.ip_address}: {CYAN}0.24 ms (Bridge Virtual Interface){RESET}")

    def display_ps(self):
        print(f"\n{BOLD}NAME             IMAGE                 STATUS     HEALTH     PORTS{RESET}")
        print("-" * 70)
        for s in self.services.values():
            ports_str = ", ".join(s.ports) if s.ports else "-"
            status_color = GREEN if s.status == "running" else RED
            health_color = GREEN if s.health == "healthy" else (YELLOW if s.health == "none" else DIM)
            print(f"{s.name:<16} {s.image:<21} {status_color}{s.status:<10}{RESET} {health_color}{s.health:<10}{RESET} {ports_str}")

    def simulate_down(self):
        print(f"\n{BOLD}{RED}>>> Mengeksekusi 'docker compose down -v' <<<{RESET}")
        ordered_services = list(reversed(self.resolve_dag_order()))
        for svc_name in ordered_services:
            svc = self.services[svc_name]
            if svc.status == "running":
                print(f"[*] Stopping container {CYAN}{svc.name}{RESET} (SIGTERM)...")
                time.sleep(0.2)
                svc.status = "stopped"
                svc.health = "unknown"
                svc.ip_address = ""
                print(f"[*] Removing container {svc.name}... {GREEN}done{RESET}")
        print(f"[*] Removing bridge network '{self.network_name}'... {GREEN}done{RESET}")
        print(f"[*] Purging volumes: {list(self.named_volumes.keys())}... {GREEN}done{RESET}")


def interactive_menu():
    sim = DockerComposeSimulator()
    sim.print_banner()

    menu = """
Pilih Simulasi Tindakan:
1. Tampilkan Manifest docker-compose.yml
2. Jalankan 'docker compose up -d' (DAG + Healthcheck)
3. Cek Status Container ('docker compose ps')
4. Uji Service Discovery (Docker Embedded DNS Lookup)
5. Hentikan & Bersihkan ('docker compose down -v')
6. Keluar dari Lab
"""

    while True:
        print(menu)
        choice = input(f"{BOLD}Pilih opsi (1-6): {RESET}").strip()
        if choice == "1":
            sim.display_compose_manifest()
        elif choice == "2":
            sim.simulate_up()
        elif choice == "3":
            sim.display_ps()
        elif choice == "4":
            sim.simulate_dns_discovery()
        elif choice == "5":
            sim.simulate_down()
        elif choice == "6":
            print(f"{CYAN}Sesi Lab Multi-Container selesai.{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak valid, masukkan angka 1-6.{RESET}")


if __name__ == "__main__":
    interactive_menu()
