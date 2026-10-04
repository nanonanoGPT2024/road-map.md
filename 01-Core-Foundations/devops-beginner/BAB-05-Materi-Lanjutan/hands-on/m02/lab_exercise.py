#!/usr/bin/env python3
"""
Deep Dive: Engine Kontainerisasi & Abstraksi Container Runtime
Lab Hands-on: Arsitektur Docker, Layered FileSystem (OverlayFS/CoW),
Namespaces, dan Cgroups Resource Limiter.

Standar library Python murni tanpa dependensi eksternal.
"""

import hashlib
import json
import time
import os
import sys
from typing import Dict, List, Optional, Any

# ANSI Color Codes untuk Visualisasi Terminal
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[31m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN = "\033[36m"


class ImageLayer:
    """
    Merepresentasikan Image Layer yang Immutable (Read-Only)
    Berbasis Content-Addressable Storage (CAS) menggunakan SHA-256.
    """
    def __init__(self, layer_name: str, files: Dict[str, str]):
        self.layer_name = layer_name
        self.files = files
        # Menghitung SHA256 digest dari konten layer
        payload = json.dumps(files, sort_keys=True).encode("utf-8")
        self.digest = hashlib.sha256(payload).hexdigest()[:12]

    def __repr__(self):
        return f"<Layer {self.layer_name} (sha256:{self.digest})>"


class OverlayFileSystem:
    """
    Simulasi UnionFS / OverlayFS dengan mekanisme Copy-on-Write (CoW).
    - Lower Layers: Kumpulan layer read-only.
    - Upper Layer: Layer read-write tempat kontainer melakukan mutasi file.
    """
    def __init__(self, lower_layers: List[ImageLayer]):
        self.lower_layers = lower_layers
        self.upper_layer: Dict[str, str] = {}  # Writable layer
        self.whiteout_markers: set = set()     # Menandai file yang dihapus (.wh.*)

    def read_file(self, filepath: str) -> Optional[str]:
        """Membaca file dengan resolusi traversal dari upper ke lower layer."""
        if filepath in self.whiteout_markers:
            return None
        # Cek writable upper layer terlebih dahulu
        if filepath in self.upper_layer:
            return self.upper_layer[filepath]
        # Traversal lower layer dari yang paling atas ke paling dasar
        for layer in reversed(self.lower_layers):
            if filepath in layer.files:
                return layer.files[filepath]
        return None

    def write_file(self, filepath: str, content: str) -> None:
        """
        Implementasi Copy-on-Write: Modifikasi file hanya ditulis
        pada upper layer tanpa mengubah layer read-only di bawahnya.
        """
        if filepath in self.whiteout_markers:
            self.whiteout_markers.remove(filepath)
        self.upper_layer[filepath] = content

    def delete_file(self, filepath: str) -> bool:
        """Menghapus file menggunakan Whiteout marker jika file ada di lower layers."""
        file_exists = self.read_file(filepath) is not None
        if not file_exists:
            return False
        if filepath in self.upper_layer:
            del self.upper_layer[filepath]
        self.whiteout_markers.add(filepath)
        return True


class CGroupController:
    """
    Simulasi Linux Control Groups (cgroups v2).
    Membatasi konsumsi Memory dan CPU Quota.
    """
    def __init__(self, memory_limit_mb: int, cpu_quota_pct: int):
        self.memory_limit_mb = memory_limit_mb
        self.cpu_quota_pct = cpu_quota_pct
        self.memory_usage_mb = 0

    def allocate_memory(self, mb: int) -> bool:
        """Alokasi memori dengan penegakan limit OOM (Out-of-Memory)."""
        if self.memory_usage_mb + mb > self.memory_limit_mb:
            return False  # OOM Triggered
        self.memory_usage_mb += mb
        return True

    def release_memory(self, mb: int) -> None:
        self.memory_usage_mb = max(0, self.memory_usage_mb - mb)


class NamespaceIsolator:
    """
    Simulasi Linux Namespaces (PID, NET, UTS, MNT).
    Menyediakan isolasi identitas proses dan jaringan.
    """
    def __init__(self, container_id: str, hostname: str, ip_address: str):
        self.container_id = container_id
        self.hostname = hostname
        self.ip_address = ip_address
        self.pid_map: Dict[int, int] = {}  # Map Host PID -> Container PID
        self.next_container_pid = 1

    def spawn_process(self, host_pid: int, command: str) -> int:
        """Membuat proses baru di dalam namespace PID terisolasi."""
        c_pid = self.next_container_pid
        self.pid_map[host_pid] = c_pid
        self.next_container_pid += 1
        return c_pid


class Container:
    """
    Representasi instance Container utuh yang menggabungkan:
    OverlayFS + Cgroups + Namespaces.
    """
    def __init__(self, container_id: str, image_name: str, rootfs: OverlayFileSystem,
                 cgroups: CGroupController, namespaces: NamespaceIsolator):
        self.id = container_id
        self.image_name = image_name
        self.rootfs = rootfs
        self.cgroups = cgroups
        self.namespaces = namespaces
        self.status = "Created"
        self.process_table: List[Dict[str, Any]] = []

    def start(self):
        self.status = "Running"
        # Inisialisasi proses PID 1 (Init system / Entrypoint kontainer)
        c_pid = self.namespaces.spawn_process(host_pid=10450, command="python3 app.py")
        self.process_table.append({"c_pid": c_pid, "host_pid": 10450, "cmd": "python3 app.py"})

    def execute_command(self, host_pid: int, cmd: str, mem_cost_mb: int = 10) -> bool:
        """Simulasi eksekusi instruksi di dalam kontainer dengan audit cgroup."""
        if self.status != "Running":
            print(f"{CLR_RED}[FAIL] Kontainer tidak dalam status running.{CLR_RESET}")
            return False

        if not self.cgroups.allocate_memory(mem_cost_mb):
            print(f"{CLR_RED}[OOM-KILLED] Host PID {host_pid} memicu Out-Of-Memory! "
                  f"Limit: {self.cgroups.memory_limit_mb}MB, Butuh: +{mem_cost_mb}MB "
                  f"(Terpakai: {self.cgroups.memory_usage_mb}MB){CLR_RESET}")
            return False

        c_pid = self.namespaces.spawn_process(host_pid=host_pid, command=cmd)
        self.process_table.append({"c_pid": c_pid, "host_pid": host_pid, "cmd": cmd})
        return True


def print_section(title: str):
    """Cetak header seksi dengan pemformatan visual."""
    print(f"\n{CLR_BOLD}{CLR_CYAN}{'=' * 65}")
    print(f" {title.upper()}")
    print(f"{'=' * 65}{CLR_RESET}")


def run_container_deep_dive_lab():
    """Eksekusi lab utama yang mendemonstrasikan internal kontainer."""
    print_section("Fase 1: Image Composition & Content-Addressable Storage")

    # 1. Definisi Layer Image Immutable
    layer_base = ImageLayer("alpine:3.18-base", {
        "/bin/sh": "binary_content_sh",
        "/etc/os-release": "NAME=Alpine Linux\nVERSION_ID=3.18",
        "/etc/hosts": "127.0.0.1 localhost"
    })

    layer_runtime = ImageLayer("python:3.11-runtime", {
        "/usr/bin/python3": "binary_content_python3",
        "/usr/lib/python3.11": "lib_files"
    })

    layer_app = ImageLayer("app:microservice", {
        "/app/app.py": "import os\nprint('Microservice running')",
        "/app/config.json": '{"env": "production", "debug": false}'
    })

    layers = [layer_base, layer_runtime, layer_app]
    for idx, lyr in enumerate(layers):
        print(f"{CLR_YELLOW}[Layer {idx}]{CLR_RESET} SHA256: {CLR_GREEN}{lyr.digest}{CLR_RESET} "
              f"| Tag: {CLR_BOLD}{lyr.layer_name}{CLR_RESET}")
        for file in lyr.files:
            print(f"   └── {file}")

    print_section("Fase 2: OverlayFS & Mekanisme Copy-on-Write (CoW)")
    rootfs = OverlayFileSystem(lower_layers=layers)

    print(f"{CLR_BLUE}[READ lower]{CLR_RESET} Membaca file original /app/config.json:")
    print(f"   Konten: {CLR_MAGENTA}{rootfs.read_file('/app/config.json')}{CLR_RESET}")

    print(f"\n{CLR_BLUE}[CoW Triggered]{CLR_RESET} Mengubah /app/config.json di kontainer (Upper Layer)...")
    rootfs.write_file("/app/config.json", '{"env": "production", "debug": true, "worker": 4}')

    print(f"{CLR_GREEN}[READ upper]{CLR_RESET} Konten aktif di kontainer sekarang:")
    print(f"   Konten: {CLR_BOLD}{rootfs.read_file('/app/config.json')}{CLR_RESET}")

    print(f"{CLR_YELLOW}[AUDIT]{CLR_RESET} Memverifikasi integritas layer Read-Only dasar:")
    print(f"   Layer App Asli: {CLR_GREEN}{layer_app.files['/app/config.json']}{CLR_RESET} (Tidak termutasi!)")
    print(f"   Upper Layer Delta: {CLR_MAGENTA}{rootfs.upper_layer['/app/config.json']}{CLR_RESET}")

    print_section("Fase 3: Isolasi Namespaces & Batasan Control Groups (Cgroups)")
    cgroup = CGroupController(memory_limit_mb=64, cpu_quota_pct=50)
    ns = NamespaceIsolator(container_id="ctr-prod-01", hostname="microservice-pod", ip_address="172.17.0.2")
    container = Container("ctr-prod-01", "python-microservice:v1", rootfs, cgroup, ns)

    container.start()
    print(f"{CLR_GREEN}✓ Kontainer Berjalan.{CLR_RESET} Status: {container.status}")
    print(f"  Container Hostname : {CLR_BOLD}{container.namespaces.hostname}{CLR_RESET}")
    print(f"  Container Virtual IP : {CLR_BOLD}{container.namespaces.ip_address}{CLR_RESET}")
    print(f"  Cgroups Memory Limit : {CLR_BOLD}{cgroup.memory_limit_mb} MB{CLR_RESET}")

    print("\nSimulasi Alokasi Proses:")
    # Task 1: Operasi normal
    print("-> Menjalankan Worker Thread (Memori: 30MB)...")
    container.execute_command(host_pid=23941, cmd="worker_thread_1", mem_cost_mb=30)
    print(f"   Penggunaan Memori Cgroup: {CLR_YELLOW}{cgroup.memory_usage_mb}/{cgroup.memory_limit_mb} MB{CLR_RESET}")

    # Task 2: Operasi yang melebihi batas memori (OOM Trigger)
    print("-> Menjalankan Heavy In-Memory Buffer (Memori: 40MB)...")
    container.execute_command(host_pid=23955, cmd="data_aggregator", mem_cost_mb=40)

    print_section("Fase 4: Audit Pemetaan PID (Namespace Isolation View)")
    print(f"{'HOST PID':<12} | {'CONTAINER PID':<15} | {'COMMAND':<25}")
    print("-" * 58)
    for p in container.process_table:
        print(f"{CLR_BLUE}{p['host_pid']:<12}{CLR_RESET} | "
              f"{CLR_GREEN}{p['c_pid']:<15}{CLR_RESET} | "
              f"{p['cmd']:<25}")

    print(f"\n{CLR_GREEN}{CLR_BOLD}Audit Selesai:{CLR_RESET} Prinsip isolasi kontainer dan proteksi cgroups tervalidasi.")


if __name__ == "__main__":
    run_container_deep_dive_lab()