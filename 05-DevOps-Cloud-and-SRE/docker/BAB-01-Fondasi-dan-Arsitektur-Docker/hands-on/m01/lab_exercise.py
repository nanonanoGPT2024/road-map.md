#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Teknis Fondasi dan Arsitektur Docker (BAB-01)
Materi: Linux Namespaces, Cgroups, dan OverlayFS (Copy-on-Write) Simulation.
Standalone Python 3 script dengan output terminal berformat ANSI.
"""

import sys
import os
import time
import json
import uuid
from typing import Dict, List, Any


# --- ANSI Color Codes ---
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    MAGENTA = "\033[95m"
    BLUE = "\033[94m"
    GRAY = "\033[90m"


def header(title: str) -> None:
    print(f"\n{Color.BOLD}{Color.BLUE}{'=' * 65}{Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN} [LAB SIMULASI DOCKER] {title.upper()}{Color.RESET}")
    print(f"{Color.BOLD}{Color.BLUE}{'=' * 65}{Color.RESET}\n")


def status_msg(tag: str, msg: str, color: str = Color.GREEN) -> None:
    print(f"{color}[{tag}]{Color.RESET} {msg}")


# --- Komponen 1: Linux Namespaces Simulator ---
class NamespaceSimulator:
    """Simulasi isolasi Kernel Linux Namespaces (PID, Mount, Network, UTS)"""

    def __init__(self, hostname: str = "container-demo"):
        self.hostname = hostname
        self.host_pids = [1, 2, 89, 450, 1024, 1890, 2048]
        self.container_pids: Dict[int, int] = {}  # container_pid -> host_pid mapping

    def enter_namespaces(self) -> None:
        status_msg("UTS", f"Mengubah UTS Namespace: Node Host -> '{self.hostname}'", Color.CYAN)
        status_msg("NET", "Mengalokasikan veth pair: veth0 (Host) <-> eth0 (Container 172.17.0.2/16)", Color.CYAN)
        status_msg("MNT", "Pivot Root & Isolasi VFS: Chroot ke /var/lib/docker/overlay2/merged", Color.CYAN)
        status_msg("IPC", "Mengisolasi System V IPC Message Queue & Shared Memory segment", Color.CYAN)

    def isolate_pid(self) -> None:
        print(f"\n{Color.BOLD}--- Simulasi PID Namespace Virtualization ---{Color.RESET}")
        time.sleep(0.3)
        # Mengubah proses init container menjadi PID 1 di dalam namespace
        allocated_host_pid = 4128
        self.container_pids[1] = allocated_host_pid
        status_msg("PID", f"Host Process (PID {allocated_host_pid}) dimetakan ke Container (PID 1 /entrypoint.sh)", Color.YELLOW)
        
        # Sub-process container
        self.container_pids[2] = 4135
        status_msg("PID", "Host Process (PID 4135) dimetakan ke Container (PID 2 /app/server)", Color.YELLOW)

        print(f"\n{Color.GRAY}Tampilan dari dalam Container Namespace (ps aux):{Color.RESET}")
        print(f"{'PID':<8}{'COMMAND':<25}{'HOST_MAPPED_PID':<15}")
        print(f"{'-' * 48}")
        print(f"{'1':<8}{'/bin/sh /entrypoint.sh':<25}{self.container_pids[1]:<15}")
        print(f"{'2':<8}{'python3 app.py --port 8080':<25}{self.container_pids[2]:<15}")


# --- Komponen 2: Control Groups (cgroups v2) Simulator ---
class CgroupSimulator:
    """Simulasi pembatasan sumber daya komputasi melalui Linux cgroups"""

    def __init__(self, memory_limit_mb: int = 256, cpu_quota_pct: int = 50):
        self.memory_limit_mb = memory_limit_mb
        self.cpu_quota_pct = cpu_quota_pct

    def enforce_limits(self) -> None:
        print(f"\n{Color.BOLD}--- Simulasi Cgroups v2 Resource Allocation ---{Color.RESET}")
        cgroup_path = "/sys/fs/cgroup/docker/c7a19f80/"
        print(f"{Color.GRAY}Path kontrol kernel: {cgroup_path}{Color.RESET}")
        time.sleep(0.3)
        
        status_msg("CGROUP-MEM", f"Menulis memory.max = {self.memory_limit_mb * 1024 * 1024} bytes ({self.memory_limit_mb}MB)", Color.GREEN)
        status_msg("CGROUP-CPU", f"Menulis cpu.max = {self.cpu_quota_pct * 1000} 100000 (Quota: {self.cpu_quota_pct}% Core)", Color.GREEN)
        status_msg("CGROUP-OOM", "OOM Killer terpasang: Mematikan container jika melebihi batas RAM tanpa swap leak.", Color.YELLOW)


# --- Komponen 3: Storage Driver (OverlayFS & Copy-on-Write) Simulator ---
class OverlayFSSimulator:
    """Simulasi Layering Image Docker & CoW (LowerDir, UpperDir, WorkDir, MergedDir)"""

    def __init__(self):
        self.lower_dir = {
            "rootfs/bin/sh": "binary-sh-v1",
            "rootfs/etc/os-release": "NAME=Alpine Linux",
            "rootfs/lib/libc.so": "glibc-binary",
        }
        self.upper_dir: Dict[str, str] = {}
        self.deleted_in_upper: List[str] = []

    def inspect_layers(self) -> None:
        print(f"\n{Color.BOLD}--- Simulasi OverlayFS Driver & Layer Immutability ---{Color.RESET}")
        print(f"{Color.CYAN}[LowerDir - Read Only Layers]{Color.RESET}")
        for path, val in self.lower_dir.items():
            print(f"  └── (RO) {path} => {val}")

    def write_file(self, path: str, content: str) -> None:
        """CoW: Modifikasi file langsung disalin ke UpperDir (Read-Write Layer)"""
        status_msg("OVERLAY-COW", f"Copy-on-Write dipicu: File '{path}' diduplikasi ke UpperDir (R/W)", Color.MAGENTA)
        self.upper_dir[path] = content

    def remove_file(self, path: str) -> None:
        """Whiteout file marker pada OverlayFS"""
        if path in self.lower_dir or path in self.upper_dir:
            status_msg("OVERLAY-WH", f"Menulis Whiteout File (chr 0/0) untuk menyembunyikan '{path}'", Color.RED)
            self.deleted_in_upper.append(path)
            if path in self.upper_dir:
                del self.upper_dir[path]

    def render_merged(self) -> None:
        print(f"\n{Color.BOLD}[MergedDir - Unified View Terlihat oleh Container]{Color.RESET}")
        all_keys = set(self.lower_dir.keys()).union(set(self.upper_dir.keys()))
        for k in sorted(all_keys):
            if k in self.deleted_in_upper:
                continue
            origin = f"{Color.GREEN}(R/W UpperDir){Color.RESET}" if k in self.upper_dir else f"{Color.BLUE}(RO LowerDir){Color.RESET}"
            content = self.upper_dir[k] if k in self.upper_dir else self.lower_dir[k]
            print(f"  ├── {k:<30} {origin:<22} -> '{content}'")


# --- Orchestrator & CLI Runner ---
def run_interactive_simulation() -> None:
    container_id = uuid.uuid4().hex[:12]
    header(f"Inisialisasi Container Runtime ({container_id})")

    # 1. Namespaces
    ns = NamespaceSimulator(hostname=f"app-{container_id[:6]}")
    ns.enter_namespaces()
    ns.isolate_pid()

    # 2. Cgroups
    cg = CgroupSimulator(memory_limit_mb=512, cpu_quota_pct=80)
    cg.enforce_limits()

    # 3. Storage Layering
    storage = OverlayFSSimulator()
    storage.inspect_layers()

    print(f"\n{Color.BOLD}>>> Simulasi Eksekusi Operasi File I/O di Container...{Color.RESET}")
    time.sleep(0.4)
    storage.write_file("rootfs/app/config.json", '{"env": "production", "debug": false}')
    storage.write_file("rootfs/etc/os-release", "NAME=Alpine Linux (Patched Security Fix)")
    storage.remove_file("rootfs/lib/libc.so")

    storage.render_merged()

    print(f"\n{Color.BOLD}{Color.GREEN}{'=' * 65}{Color.RESET}")
    print(f"{Color.BOLD}{Color.GREEN}✔ Simulasi Fondasi Docker Sukses: Isolasi Kernel Terverifikasi!{Color.RESET}")
    print(f"{Color.BOLD}{Color.GREEN}{'=' * 65}{Color.RESET}\n")


if __name__ == "__main__":
    try:
        run_interactive_simulation()
    except KeyboardInterrupt:
        print(f"\n{Color.RED}Simulasi dibatalkan oleh user.{Color.RESET}")
        sys.exit(0)
