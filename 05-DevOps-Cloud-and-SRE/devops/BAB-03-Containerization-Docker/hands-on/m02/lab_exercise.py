#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Arsitektur Produksi Lanjut Docker & Containerization
Topik: BAB-03-Containerization-Docker (DevOps Cloud & SRE)

Simulasi interaktif tingkat lanjut yang memodelkan komponen internal Docker:
- Kernel Namespaces & cgroups v2 (CPU Quota, Memory Limit & OOM Killer)
- Multi-Stage Build & Layer Caching Engine
- Custom Bridge Network Isolation & DNS Service Discovery
- Container Healthcheck, Self-Healing Daemon & Zero-Downtime Rolling Update
"""

import sys
import time
import random
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

# ==============================================================================
# ANSI Color Codes & Formatting
# ==============================================================================
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

def cprint(text: str, color: str = Color.WHITE, bold: bool = False, end: str = "\n"):
    prefix = Color.BOLD if bold else ""
    print(f"{prefix}{color}{text}{Color.RESET}", end=end)

def render_progress(label: str, total_steps: int = 15, delay: float = 0.04):
    sys.stdout.write(f"{Color.CYAN}{label.ljust(35)}{Color.RESET} [")
    for _ in range(total_steps):
        time.sleep(delay)
        sys.stdout.write(f"{Color.GREEN}#{Color.RESET}")
        sys.stdout.flush()
    sys.stdout.write(f"] {Color.BOLD}{Color.GREEN}DONE{Color.RESET}\n")

# ==============================================================================
# Model Domain Docker & Container Engine
# ==============================================================================
class ContainerState(Enum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    HEALTHY = "HEALTHY"
    UNHEALTHY = "UNHEALTHY"
    OOM_KILLED = "OOM_KILLED"
    STOPPED = "STOPPED"

@dataclass
class CgroupLimits:
    cpu_limit_cores: float = 1.0
    memory_limit_mb: int = 256
    current_memory_mb: int = 64

@dataclass
class Container:
    container_id: str
    name: str
    image: str
    network: str
    ip_address: str
    cgroups: CgroupLimits
    state: ContainerState = ContainerState.CREATED
    pid_ns: int = field(default_factory=lambda: random.randint(1000, 9999))
    restart_count: int = 0
    logs: List[str] = field(default_factory=list)

    def log(self, message: str):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        self.logs.append(f"[{timestamp}] {message}")

class DockerDaemonSimulation:
    def __init__(self):
        self.containers: Dict[str, Container] = {}
        self.networks = {
            "bridge-frontend": "172.20.0.0/16",
            "bridge-backend": "172.21.0.0/16"
        }
        self.image_cache = {"alpine:3.19": 7.4, "golang:1.22-alpine": 280.0}

    def print_banner(self):
        print(f"{Color.CYAN}{'='*75}{Color.RESET}")
        cprint("   DOCKER ENGINE & PRODUCTION CONTAINERIZATION SIMULATOR", Color.CYAN, bold=True)
        cprint("   BAB 03: DevOps / SRE Enterprise Architecture Hands-On Lab", Color.WHITE)
        print(f"{Color.CYAN}{'='*75}{Color.RESET}\n")

    def simulate_multi_stage_build(self):
        cprint("\n[LAB 1] Simulasi Multi-Stage Build & Image Optimization", Color.YELLOW, bold=True)
        cprint("Memeriksa instruksi Dockerfile dengan target: microservice-gateway:v2.1", Color.WHITE)
        time.sleep(0.3)

        stages = [
            ("Stage 1 (Builder): FROM golang:1.22-alpine AS build", "Fetch base SDK layer", False),
            ("Stage 1 (Builder): COPY go.mod go.sum ./ && RUN go mod download", "Dependency caching", True),
            ("Stage 1 (Builder): COPY . . && RUN CGO_ENABLED=0 go build -ldflags='-s -w'", "Binary compilation", False),
            ("Stage 2 (Runtime): FROM alpine:3.19", "Minimal runtime base", True),
            ("Stage 2 (Runtime): RUN addgroup -S app && adduser -S app -G app", "Non-root security context", False),
            ("Stage 2 (Runtime): COPY --from=build /app/server /bin/server", "Zero-tooling binary extraction", False),
            ("Stage 2 (Runtime): USER app:app && EXPOSE 8080", "Principle of Least Privilege", False),
        ]

        for step, desc, cached in stages:
            cache_flag = f"{Color.MAGENTA}[CACHE HIT]{Color.RESET}" if cached else f"{Color.BLUE}[RUN/BUILD]{Color.RESET}"
            render_progress(f"{cache_flag} {step[:30]}...", total_steps=8, delay=0.03)

        cprint("\nPerbandingan Ukuran Image Akhir:", Color.GREEN, bold=True)
        print(f"  • Single-stage (golang:1.22-alpine + source): {Color.RED}412.8 MB{Color.RESET} (High CVE surface)")
        print(f"  • Multi-stage (alpine:3.19 distroless-like):    {Color.GREEN}14.2 MB{Color.RESET} (Reduced 96.5%)")

    def provision_cluster(self):
        cprint("\n[LAB 2] Provisioning Cluster Container & Cgroups Enforcers", Color.YELLOW, bold=True)
        configs = [
            ("c1a", "api-gateway-v1", "microservice-gateway:v2.0", "bridge-frontend", "172.20.0.11", 512, 1.5),
            ("c1b", "api-gateway-v2", "microservice-gateway:v2.1", "bridge-frontend", "172.20.0.12", 512, 1.5),
            ("c2a", "auth-service-01", "auth-svc:v1.4", "bridge-backend", "172.21.0.21", 256, 1.0),
            ("c3a", "payment-worker", "payment-engine:v3.0", "bridge-backend", "172.21.0.31", 128, 0.5),
        ]

        for cid, name, img, net, ip, mem, cpu in configs:
            container = Container(
                container_id=cid,
                name=name,
                image=img,
                network=net,
                ip_address=ip,
                cgroups=CgroupLimits(cpu_limit_cores=cpu, memory_limit_mb=mem, current_memory_mb=int(mem * 0.4)),
                state=ContainerState.RUNNING
            )
            container.log(f"Container created with namespaces: PID({container.pid_ns}), NET({net})")
            container.log(f"cgroups v2 enforced: memory.max={mem}MB, cpu.max={cpu} cores")
            self.containers[cid] = container
            render_progress(f"Starting {name} ({ip})", total_steps=6, delay=0.02)

        self.display_table()

    def display_table(self):
        print(f"\n{Color.BOLD}{'ID':<6} {'NAME':<18} {'IP ADDRESS':<15} {'NET':<17} {'MEM USAGE':<14} {'STATE':<12}{Color.RESET}")
        print("-" * 88)
        for c in self.containers.values():
            status_color = Color.GREEN if c.state in [ContainerState.RUNNING, ContainerState.HEALTHY] else Color.RED
            if c.state == ContainerState.OOM_KILLED:
                status_color = Color.MAGENTA
            mem_str = f"{c.cgroups.current_memory_mb}/{c.cgroups.memory_limit_mb} MB"
            print(f"{c.container_id:<6} {c.name:<18} {c.ip_address:<15} {c.network:<17} {mem_str:<14} {status_color}{c.state.value:<12}{Color.RESET}")

    def simulate_oom_killer(self):
        cprint("\n[LAB 3] Simulasi Beban Cgroups Memory Limit & Kernel OOM Killer", Color.YELLOW, bold=True)
        target = self.containers.get("c3a")
        if not target:
            return

        cprint(f"Menyuntikkan memory leak simulasi pada container '{target.name}'...", Color.WHITE)
        time.sleep(0.4)

        for burst in [60, 95, 120, 135]:
            target.cgroups.current_memory_mb = burst
            pct = (burst / target.cgroups.memory_limit_mb) * 100
            bar_color = Color.GREEN if pct < 80 else (Color.YELLOW if pct < 100 else Color.RED)
            cprint(f"  [cg-monitor] Memory usage: {burst}MB / {target.cgroups.memory_limit_mb}MB ({pct:.1f}%)", bar_color)
            time.sleep(0.3)

        cprint(f"\n[KERNEL ALERT] Invoked oom-killer: gfp_mask=0x1100cca(GFP_HIGHUSER_MOVABLE)", Color.RED, bold=True)
        cprint(f"Out of memory: Killed process {target.pid_ns} ({target.name}) total-vm:{burst}MB", Color.RED)
        target.state = ContainerState.OOM_KILLED
        target.log("Process terminated by host kernel OOM killer (cgroups memory limit exceeded). Exit code 137.")
        self.display_table()

        cprint("\n[Self-Healing] Docker Restart Policy (restart: on-failure:3) memicu pemulihan...", Color.CYAN)
        time.sleep(0.5)
        target.state = ContainerState.RUNNING
        target.restart_count += 1
        target.cgroups.current_memory_mb = 45
        target.pid_ns = random.randint(1000, 9999)
        target.log(f"Container auto-healed. New PID NS: {target.pid_ns}, Restart Counter: {target.restart_count}")
        render_progress(f"Restarting {target.name} (pid {target.pid_ns})", total_steps=10, delay=0.03)
        self.display_table()

    def simulate_rolling_update(self):
        cprint("\n[LAB 4] Zero-Downtime Rolling Update & Active Healthcheck", Color.YELLOW, bold=True)
        cprint("Strategi: Rolling replacement dari v2.0 ke v2.1 di balik ingress load-balancer", Color.WHITE)
        time.sleep(0.3)

        c1a = self.containers.get("c1a")
        c1b = self.containers.get("c1b")

        if not c1a or not c1b:
            return

        print(f"1. Ingress mengalirkan traffic 50/50 ke {c1a.name} dan {c1b.name}")
        for attempt in range(1, 4):
            time.sleep(0.2)
            cprint(f"   HTTP GET /healthz via {c1b.name} ({c1b.ip_address}): 200 OK (Probe {attempt}/3)", Color.GREEN)

        c1b.state = ContainerState.HEALTHY
        cprint(f"\n2. Container {c1b.name} dinyatakan HEALTHY. Memindahkan seluruh traffic ke {c1b.name}.", Color.CYAN)
        time.sleep(0.4)

        cprint(f"3. Mengirimkan SIGTERM ke {c1a.name} (Graceful shutdown period: 15s)...", Color.YELLOW)
        c1a.log("Received SIGTERM signal. Draining in-flight TCP connections...")
        render_progress(f"Draining {c1a.name}", total_steps=8, delay=0.03)

        c1a.state = ContainerState.STOPPED
        c1a.log("Worker exited with status code 0.")
        cprint(f"4. {c1a.name} berhasil dimatikan tanpa kegagalan koneksi aktif.", Color.GREEN, bold=True)
        self.display_table()

    def inspect_container_namespaces(self):
        cprint("\n[LAB 5] Deep-Dive Linux Kernel Namespaces Inspection", Color.YELLOW, bold=True)
        c = self.containers.get("c1b")
        if not c:
            return

        metadata = {
            "Id": c.container_id,
            "Name": f"/{c.name}",
            "Image": c.image,
            "State": {
                "Status": c.state.value,
                "Pid": c.pid_ns,
                "Health": "healthy"
            },
            "HostConfig": {
                "NetworkMode": c.network,
                "Memory": c.cgroups.memory_limit_mb * 1024 * 1024,
                "NanoCpus": int(c.cgroups.cpu_limit_cores * 1_000_000_000),
                "RestartPolicy": {"Name": "unless-stopped", "MaximumRetryCount": 5}
            },
            "NetworkSettings": {
                "IPAddress": c.ip_address,
                "Gateway": "172.20.0.1",
                "MacAddress": "02:42:ac:14:00:0c"
            }
        }
        print(f"{Color.CYAN}Simulasi output: docker inspect {c.name}{Color.RESET}")
        print(f"{Color.WHITE}{json.dumps(metadata, indent=2)}{Color.RESET}")

    def run_interactive(self):
        self.print_banner()
        self.simulate_multi_stage_build()
        self.provision_cluster()
        self.simulate_oom_killer()
        self.simulate_rolling_update()
        self.inspect_container_namespaces()

        print(f"\n{Color.GREEN}{'='*75}{Color.RESET}")
        cprint("   SELURUH RANGKAIAN LAB ARSITEKTUR CONTAINER SELESAI!", Color.GREEN, bold=True)
        cprint("   Prinsip DevOps Tercakup: Multi-stage, Cgroups, Healthcheck, Zero-Downtime.", Color.WHITE)
        print(f"{Color.GREEN}{'='*75}{Color.RESET}\n")

if __name__ == "__main__":
    app = DockerDaemonSimulation()
    app.run_interactive()
