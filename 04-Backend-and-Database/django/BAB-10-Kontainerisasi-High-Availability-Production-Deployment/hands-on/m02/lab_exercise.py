#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Arsitektur Produksi High-Availability Django
BAB 10 - Kontainerisasi, High Availability, dan Production Deployment

Simulasi interaktif standalone:
- Nginx Reverse Proxy / Load Balancer (Round-Robin & Health Check)
- Cluster Kontainer Django WSGI/ASGI (Gunicorn/Uvicorn)
- PostgreSQL High Availability (Primary Read-Write + Replica Read-Only + PgBouncer)
- Redis Cache & Task Broker Cluster
- Zero-Downtime Rolling Deployment & Automatic Failover Engine
"""

import sys
import time
import random
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict

# ANSI Color Codes
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BG_BLUE = "\033[44m"
    BG_DARK = "\033[100m"

class NodeStatus(Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    DRAINING = "DRAINING"
    DOWN = "DOWN"

@dataclass
class DjangoWorkerNode:
    node_id: str
    container_ip: str
    version: str
    port: int
    active_connections: int = 0
    status: NodeStatus = NodeStatus.HEALTHY
    total_served: int = 0

@dataclass
class DatabaseNode:
    role: str  # Primary or Replica
    host: str
    port: int
    connections: int
    max_connections: int
    status: NodeStatus = NodeStatus.HEALTHY
    replication_lag_ms: float = 0.0

class ProductionClusterSimulator:
    def __init__(self):
        self.app_version = "1.0.0"
        self.workers: List[DjangoWorkerNode] = [
            DjangoWorkerNode(node_id="django-app-01", container_ip="172.28.0.11", version=self.app_version, port=8000),
            DjangoWorkerNode(node_id="django-app-02", container_ip="172.28.0.12", version=self.app_version, port=8000),
            DjangoWorkerNode(node_id="django-app-03", container_ip="172.28.0.13", version=self.app_version, port=8000),
        ]
        self.rr_index = 0
        self.db_primary = DatabaseNode(role="PRIMARY (R/W)", host="pg-primary.prod.internal", port=6432, connections=14, max_connections=100)
        self.db_replica = DatabaseNode(role="REPLICA (RO)", host="pg-replica.prod.internal", port=6432, connections=8, max_connections=100, replication_lag_ms=1.2)
        self.redis_nodes = ["redis-sentinel-01:26379", "redis-sentinel-02:26379", "redis-master:6379"]

    def log(self, prefix: str, message: str, color: str = Color.WHITE):
        timestamp = time.strftime("%H:%M:%S")
        print(f"{Color.DIM}[{timestamp}]{Color.RESET} {color}{prefix}{Color.RESET} {message}")

    def render_header(self, title: str):
        print(f"\n{Color.BG_BLUE}{Color.WHITE}{Color.BOLD} === {title} === {Color.RESET}\n")

    def display_cluster_status(self):
        self.render_header("TOPOLOGI INFRASTRUKTUR HIGH-AVAILABILITY CLUSTER")
        
        # Load Balancer & Edge
        print(f"{Color.BOLD}1. INGRESS & EDGE PROXY (Nginx + Cloudflare SSL Termination){Color.RESET}")
        print(f"   [Gateway VIP]    : {Color.CYAN}203.0.113.80:443 (TLS v1.3 | HTTP/2){Color.RESET}")
        print(f"   [Algorithm]      : Least Connections with Health Checking")
        print(f"   [KeepAlive Pool] : 64 connections\n")

        # Django WSGI/ASGI Containers
        print(f"{Color.BOLD}2. DJANGO APP SERVERS (Docker Swarm / Kubernetes Pods){Color.RESET}")
        for w in self.workers:
            color = Color.GREEN if w.status == NodeStatus.HEALTHY else (Color.YELLOW if w.status == NodeStatus.DRAINING else Color.RED)
            print(f"   • {w.node_id:<15} [{w.container_ip}:{w.port}] | Ver: {w.version:<6} | Status: {color}{w.status.value:<9}{Color.RESET} | Active Conn: {w.active_connections:<2} | Total Req: {w.total_served}")
        print()

        # Database Cluster
        print(f"{Color.BOLD}3. DATABASE CLUSTER (PostgreSQL 16 HA via PgBouncer Pooler){Color.RESET}")
        p_col = Color.GREEN if self.db_primary.status == NodeStatus.HEALTHY else Color.RED
        r_col = Color.GREEN if self.db_replica.status == NodeStatus.HEALTHY else Color.RED
        print(f"   • {self.db_primary.role:<16} : {self.db_primary.host}:{self.db_primary.port} | Pool: {self.db_primary.connections}/{self.db_primary.max_connections} | Status: {p_col}{self.db_primary.status.value}{Color.RESET}")
        print(f"   • {self.db_replica.role:<16} : {self.db_replica.host}:{self.db_replica.port} | Lag: {self.db_replica.replication_lag_ms}ms | Pool: {self.db_replica.connections}/{self.db_replica.max_connections} | Status: {r_col}{self.db_replica.status.value}{Color.RESET}\n")

        # Cache & Queue
        print(f"{Color.BOLD}4. CACHE & TASK BROKER (Redis Sentinel Cluster){Color.RESET}")
        for r in self.redis_nodes:
            print(f"   • {Color.MAGENTA}{r:<28}{Color.RESET} [OK - PING/PONG < 0.4ms]")
        print("-" * 75)

    def run_health_checks(self):
        self.render_header("AUDIT AUDIENCE PROBE & HEALTH CHECKS")
        self.log("[K8S/CONSUL]", "Memeriksa probe liveness (/healthz/live/) dan readiness (/healthz/ready/)...", Color.CYAN)
        time.sleep(0.3)
        for worker in self.workers:
            if worker.status in [NodeStatus.HEALTHY, NodeStatus.DRAINING]:
                latency = round(random.uniform(2.1, 8.5), 2)
                self.log(f"[{worker.node_id}]", f"HTTP 200 OK - DB:CONNECTED, REDIS:OK (Latency: {latency}ms)", Color.GREEN)
            else:
                self.log(f"[{worker.node_id}]", "HTTP 503 SERVICE UNAVAILABLE - Container Unreachable", Color.RED)
            time.sleep(0.15)

    def simulate_traffic(self, request_count: int = 15):
        self.render_header(f"SIMULASI LOAD TRAFFIC INCOMING ({request_count} REQUESTS)")
        healthy_workers = [w for w in self.workers if w.status == NodeStatus.HEALTHY]
        if not healthy_workers:
            self.log("[NGINX]", "502 Bad Gateway! Semua node Django tidak aktif!", Color.RED)
            return

        for i in range(1, request_count + 1):
            worker = healthy_workers[self.rr_index % len(healthy_workers)]
            self.rr_index += 1

            # Tipe request simulasi
            req_type = random.choice(["GET /api/v1/catalog/", "POST /api/v1/orders/checkout/", "GET /healthz/live/", "GET /static/app.css"])
            latency = round(random.uniform(4.0, 35.0), 1)

            if "static" in req_type:
                self.log("[NGINX-EDGE]", f"Req #{i:02d} -> {req_type} dilayani langsung oleh Nginx (Cache HIT - 0.8ms)", Color.CYAN)
            elif "GET" in req_type:
                worker.total_served += 1
                self.log(f"[{worker.node_id}]", f"Req #{i:02d} -> {req_type} routed ke PgBouncer Replica (200 OK, {latency}ms)", Color.GREEN)
            else:
                worker.total_served += 1
                self.log(f"[{worker.node_id}]", f"Req #{i:02d} -> {req_type} transaksi ACID ke PgBouncer Primary (201 Created, {latency + 12}ms)", Color.YELLOW)
            time.sleep(0.1)

    def simulate_database_failover(self):
        self.render_header("SIMULASI AUTOMATIC FAILOVER POSTGRESQL (Patroni / Sentinel)")
        self.log("[FAILURE INJECT]", "Kernel panic pada PostgreSQL Primary Instance (Host Unreachable)...", Color.RED)
        self.db_primary.status = NodeStatus.DOWN
        time.sleep(0.5)

        self.log("[PATRONI-ETCD]", "DCS Heartbeat lost on pg-primary.prod.internal!", Color.RED)
        self.log("[PATRONI-ETCD]", "Memulai proses pemungutan suara (Quorum Consensus Leader Election)...", Color.YELLOW)
        time.sleep(0.6)

        self.log("[PATRONI-ETCD]", "Mempromosikan pg-replica.prod.internal menjadi PRIMARY baru...", Color.YELLOW)
        time.sleep(0.4)
        
        # Promote Replica
        self.db_replica.role = "PRIMARY (R/W - Promoted)"
        self.db_replica.replication_lag_ms = 0.0
        self.log("[PGBOUNCER]", "Routing reload: Mengarahkan semua query Write ke VIP baru.", Color.GREEN)
        self.log("[CLUSTER]", "Database High-Availability failover sukses diselesaikan dalam <1.5s!", Color.GREEN)

    def simulate_rolling_deployment(self):
        new_version = "1.1.0"
        self.render_header(f"SIMULASI ZERO-DOWNTIME ROLLING DEPLOYMENT (v{self.app_version} -> v{new_version})")
        self.log("[DEPLOYER]", f"Menjalankan migrasi skema database Django (python manage.py migrate)...", Color.CYAN)
        time.sleep(0.4)
        self.log("[DJANGO-MIGRATE]", "Operations to perform: Apply unapplied migrations: shop.0004_auto_add_index... OK", Color.GREEN)

        for i, worker in enumerate(self.workers):
            print()
            self.log(f"[{worker.node_id}]", "Langkah 1: Menandai node ke mode DRAIN (Menghabiskan in-flight requests)...", Color.YELLOW)
            worker.status = NodeStatus.DRAINING
            time.sleep(0.4)

            self.log(f"[{worker.node_id}]", f"Langkah 2: Pulling image baru & restart container (tag: v{new_version})...", Color.CYAN)
            time.sleep(0.5)
            worker.version = new_version

            self.log(f"[{worker.node_id}]", "Langkah 3: Menjalankan warm-up health check probe...", Color.CYAN)
            time.sleep(0.3)
            worker.status = NodeStatus.HEALTHY
            self.log(f"[{worker.node_id}]", f"Langkah 4: Node kembali online melayani traffic (v{new_version})!", Color.GREEN)

        self.app_version = new_version
        print()
        self.log("[DEPLOYER]", f"Deployment sukses 100%! Semua {len(self.workers)} pods berhasil diupgrade ke v{new_version} tanpa downtime!", Color.GREEN)

def print_menu():
    print(f"\n{Color.BOLD}{Color.CYAN}--- PILIHAN OPERASIONAL PRODUKSI DJANGO HA ---{Color.RESET}")
    print(f"{Color.WHITE}1.{Color.RESET} Tampilkan Status Topologi Klaster")
    print(f"{Color.WHITE}2.{Color.RESET} Jalankan Liveness & Readiness Health Checks")
    print(f"{Color.WHITE}3.{Color.RESET} Simulasi Distribusi Traffic Nginx Load Balancer")
    print(f"{Color.WHITE}4.{Color.RESET} Simulasi Zero-Downtime Rolling Update (v1.0 -> v1.1)")
    print(f"{Color.WHITE}5.{Color.RESET} Uji Ketahanan Failover Database Otomatis")
    print(f"{Color.WHITE}6.{Color.RESET} Jalankan Skenario Lengkap (Semua Pengujian)")
    print(f"{Color.WHITE}0.{Color.RESET} Keluar")

def main():
    sim = ProductionClusterSimulator()
    print(f"{Color.BOLD}{Color.GREEN}=== SIMULATOR ARSITEKTUR PRODUKSI HIGH-AVAILABILITY DJANGO ==={Color.RESET}")
    print(f"Modul Praktikum BAB-10: Nginx, Gunicorn Cluster, PostgreSQL HA & Zero Downtime\n")

    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        sim.display_cluster_status()
        sim.run_health_checks()
        sim.simulate_traffic(8)
        sim.simulate_rolling_deployment()
        sim.simulate_database_failover()
        sim.display_cluster_status()
        return

    while True:
        print_menu()
        try:
            choice = input(f"\n{Color.BOLD}Pilih opsi [0-6]: {Color.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nSelesai.")
            break

        if choice == "1":
            sim.display_cluster_status()
        elif choice == "2":
            sim.run_health_checks()
        elif choice == "3":
            sim.simulate_traffic(15)
        elif choice == "4":
            sim.simulate_rolling_deployment()
        elif choice == "5":
            sim.simulate_database_failover()
        elif choice == "6":
            sim.display_cluster_status()
            sim.run_health_checks()
            sim.simulate_traffic(10)
            sim.simulate_rolling_deployment()
            sim.simulate_database_failover()
            sim.display_cluster_status()
        elif choice == "0":
            print(f"{Color.GREEN}Terima kasih! Sesi simulasi selesai.{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid, silakan coba lagi.{Color.RESET}")

if __name__ == "__main__":
    main()
