#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Fondasi Inti Containerization & Docker
Topik: Namespaces, cgroups v2, OverlayFS (UnionFS), dan Container Lifecycle
Bahasa: Python 3 (Standard Library Only)
"""

import sys
import time
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# ANSI Color Codes
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

def print_header(title: str):
    print(f"\n{BOLD}{CYAN}{'=' * 65}{RESET}")
    print(f"{BOLD}{WHITE}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 65}{RESET}")

def print_step(step: str, desc: str):
    print(f"\n{BOLD}{YELLOW}[STEP]{RESET} {BOLD}{step}{RESET}: {desc}")

def print_success(msg: str):
    print(f"{GREEN}[OK]{RESET} {msg}")

def print_info(msg: str):
    print(f"{BLUE}[INFO]{RESET} {msg}")

def print_warn(msg: str):
    print(f"{YELLOW}[WARN]{RESET} {msg}")

def print_alert(msg: str):
    print(f"{RED}[ALERT]{RESET} {msg}")

# -------------------------------------------------------------
# 1. SIMULASI NAMESPACES (UTS, PID, NET, MNT)
# -------------------------------------------------------------
@dataclass
class SimulatedProcess:
    global_pid: int
    namespace_pid: int
    command: str
    user: str

class NamespaceSimulator:
    def __init__(self, hostname: str, ip_address: str):
        self.hostname = hostname
        self.ip_address = ip_address
        self.isolated_processes: List[SimulatedProcess] = []
        self.mount_points: Dict[str, str] = {
            "/": "rootfs (overlayfs)",
            "/proc": "procfs (isolated PID view)",
            "/sys": "sysfs (cgroup tree)",
            "/dev": "devtmpfs (minimal devices)"
        }

    def add_process(self, global_pid: int, command: str, user: str = "root"):
        ns_pid = len(self.isolated_processes) + 1
        proc = SimulatedProcess(global_pid=global_pid, namespace_pid=ns_pid, command=command, user=user)
        self.isolated_processes.append(proc)
        return proc

    def render_view(self):
        print(f"\n  {BOLD}{MAGENTA}--- Virtual Namespace Isolation View ---{RESET}")
        print(f"  {BOLD}UTS Namespace (Hostname):{RESET} {GREEN}{self.hostname}{RESET}")
        print(f"  {BOLD}NET Namespace (IP Address):{RESET} {GREEN}{self.ip_address}{RESET}")
        print(f"  {BOLD}MNT Namespace (Mount Points):{RESET}")
        for target, src in self.mount_points.items():
            print(f"    - {CYAN}{target:<10}{RESET} -> {src}")
        print(f"  {BOLD}PID Namespace Translation Table:{RESET}")
        print(f"    {'NS PID':<10} {'GLOBAL PID':<12} {'USER':<10} {'COMMAND'}")
        print(f"    {'-'*10} {'-'*12} {'-'*10} {'-'*20}")
        for p in self.isolated_processes:
            print(f"    {GREEN}{p.namespace_pid:<10}{RESET} {YELLOW}{p.global_pid:<12}{RESET} {p.user:<10} {p.command}")

# -------------------------------------------------------------
# 2. SIMULASI CGROUPS V2 (Resource Limits & Accounting)
# -------------------------------------------------------------
class CGroupV2Controller:
    def __init__(self, name: str, memory_limit_mb: int, cpu_quota_pct: int):
        self.name = name
        self.memory_limit_mb = memory_limit_mb
        self.cpu_quota_pct = cpu_quota_pct
        self.current_memory_mb = 12
        self.current_cpu_pct = 5

    def allocate_memory(self, mb: int) -> bool:
        new_total = self.current_memory_mb + mb
        print_info(f"Mengajukan alokasi memory: {mb}MB (Aktif: {self.current_memory_mb}MB / Limit: {self.memory_limit_mb}MB)")
        time.sleep(0.3)
        if new_total > self.memory_limit_mb:
            print_alert(f"OOM Killer Invoked! Batas memory {self.memory_limit_mb}MB terlampaui (butuh {new_total}MB).")
            print_alert("Kernel mengirim sinyal SIGKILL (Exit Code 137).")
            return False
        self.current_memory_mb = new_total
        print_success(f"Alokasi memory sukses. Penggunaan terkini: {self.current_memory_mb}MB")
        return True

    def stress_cpu(self, requested_pct: int):
        print_info(f"Proses meminta {requested_pct}% CPU...")
        time.sleep(0.3)
        if requested_pct > self.cpu_quota_pct:
            throttled = requested_pct - self.cpu_quota_pct
            print_warn(f"cgroups v2 throttling aktif! Quota: {self.cpu_quota_pct}%. Dipangkas (throttled): {throttled}%.")
            self.current_cpu_pct = self.cpu_quota_pct
        else:
            self.current_cpu_pct = requested_pct
        print_success(f"CPU efektif yang didapat container: {self.current_cpu_pct}%")

# -------------------------------------------------------------
# 3. SIMULASI OVERLAYFS (Lower, Upper, Work, Merged Layers)
# -------------------------------------------------------------
class OverlayFSSimulator:
    def __init__(self):
        # Read-only image layers (LowerDir)
        self.lower_layers: List[Dict[str, str]] = [
            {"/bin/sh": "binary-sh-v1", "/lib/libc.so": "libc-2.31"},     # Base OS
            {"/usr/local/bin/python": "python-3.11", "/etc/issue": "Alpine"} # Runtime
        ]
        # Read-write container layer (UpperDir)
        self.upper_layer: Dict[str, str] = {}
        # Whiteout deletion marker: .wh.<filename>
        self.whiteouts: set = set()

    def get_merged_files(self) -> Dict[str, str]:
        merged = {}
        # 1. Baca dari lower layer (bawah ke atas)
        for layer in self.lower_layers:
            for path, content in layer.items():
                merged[path] = f"{content} {DIM}(ro-image-layer){RESET}"
        # 2. Timpa dengan upper layer (Copy-on-Write)
        for path, content in self.upper_layer.items():
            merged[path] = f"{content} {GREEN}(rw-container-layer){RESET}"
        # 3. Hilangkan whiteout file
        for deleted in self.whiteouts:
            if deleted in merged:
                del merged[deleted]
        return merged

    def write_file(self, path: str, content: str):
        is_cow = any(path in layer for layer in self.lower_layers)
        if is_cow:
            print_info(f"Copy-on-Write (CoW) dipicu: Menduplikasi '{path}' dari LowerDir ke UpperDir...")
        else:
            print_info(f"Menulis file baru di UpperDir: '{path}'...")
        time.sleep(0.2)
        self.upper_layer[path] = content
        self.whiteouts.discard(path)
        print_success(f"File '{path}' berhasil disimpan di UpperDir.")

    def delete_file(self, path: str):
        is_lower = any(path in layer for layer in self.lower_layers)
        if is_lower:
            print_info(f"Membuat whiteout marker '.wh.{os.path.basename(path)}' di UpperDir untuk menyembunyikan file image.")
            self.whiteouts.add(path)
        if path in self.upper_layer:
            del self.upper_layer[path]
        print_success(f"File '{path}' dihapus dari pandangan MergedDir.")

    def render_layers(self):
        print(f"\n  {BOLD}{MAGENTA}--- OverlayFS Architecture Map ---{RESET}")
        print(f"  {BOLD}UpperDir (Read/Write Container Layer):{RESET}")
        if not self.upper_layer and not self.whiteouts:
            print(f"    {DIM}(Kosong - belum ada mutasi disk){RESET}")
        for p, c in self.upper_layer.items():
            print(f"    {GREEN}+ {p:<25}{RESET} -> {c}")
        for w in self.whiteouts:
            print(f"    {RED}x {w:<25} (whiteout marker){RESET}")

        print(f"  {BOLD}LowerDir (Read-Only Base Image Layers):{RESET}")
        for idx, layer in enumerate(self.lower_layers, 1):
            print(f"    Layer {idx}: {list(layer.keys())}")

        print(f"  {BOLD}MergedDir (Unified View / Container RootFS):{RESET}")
        merged = self.get_merged_files()
        for p, desc in merged.items():
            print(f"    * {CYAN}{p:<25}{RESET} : {desc}")

# -------------------------------------------------------------
# 4. SIMULASI CONTAINER LIFECYCLE
# -------------------------------------------------------------
class ContainerState:
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"
    DEAD = "DEAD"

class MiniContainer:
    def __init__(self, name: str, image: str):
        self.name = name
        self.image = image
        self.state = ContainerState.CREATED
        self.ns = NamespaceSimulator(hostname=f"cnt-{name[:6]}", ip_address="172.17.0.2")
        self.cgroups = CGroupV2Controller(name=name, memory_limit_mb=64, cpu_quota_pct=50)
        self.storage = OverlayFSSimulator()

    def run(self):
        print_step("RUN", f"Transisi state: {self.state} -> {ContainerState.RUNNING}")
        self.state = ContainerState.RUNNING
        # Init process inside container (PID 1)
        self.ns.add_process(global_pid=28491, command="entrypoint.sh", user="root")
        self.ns.add_process(global_pid=28510, command="python app.py", user="appuser")
        print_success("Namespaces diisolasi, init PID 1 aktif.")

    def pause(self):
        if self.state != ContainerState.RUNNING:
            print_warn("Hanya container RUNNING yang dapat di-pause.")
            return
        print_step("PAUSE", f"Membekukan proses menggunakan cgroup freezer subsystem...")
        time.sleep(0.3)
        self.state = ContainerState.PAUSED
        print_success(f"Container '{self.name}' dalam status PAUSED.")

    def unpause(self):
        if self.state != ContainerState.PAUSED:
            print_warn("Container tidak dalam status PAUSED.")
            return
        print_step("UNPAUSE", f"Melanjutkan proses dari freeze...")
        self.state = ContainerState.RUNNING
        print_success(f"Container '{self.name}' kembali RUNNING.")

    def stop(self):
        print_step("STOP", f"Mengirim SIGTERM (grace period 10s), kemudian SIGKILL...")
        time.sleep(0.4)
        self.state = ContainerState.STOPPED
        print_success(f"Container '{self.name}' telah dihentikan (Exit Code 0).")

# -------------------------------------------------------------
# RUNNABLE INTERACTIVE LAB PIPELINE
# -------------------------------------------------------------
def run_interactive_lab():
    print_header("LAB SIMULASI TEKNIS: BAB-03 CONTAINERIZATION DOCKER")
    print(f"{WHITE}Membedah abstraksi container: Linux Namespaces, cgroups v2, dan OverlayFS.{RESET}")

    cnt = MiniContainer(name="docker-core-demo", image="alpine-python:3.11")

    # Step 1: Inisialisasi & Lifecycle
    cnt.run()
    cnt.ns.render_view()

    # Step 2: OverlayFS Mutasi & CoW
    print_header("SIMULASI OVERLAYFS (COPY-ON-WRITE & WHITEOUT)")
    cnt.storage.render_layers()
    
    print_step("OverlayFS CoW", "Aplikasi memodifikasi file bawaan image (/etc/issue)...")
    cnt.storage.write_file("/etc/issue", "Alpine Custom Patch v2")
    
    print_step("OverlayFS New File", "Aplikasi menulis log baru (/var/log/app.log)...")
    cnt.storage.write_file("/var/log/app.log", "[INFO] Application started successfully")
    
    print_step("OverlayFS Delete", "Aplikasi menghapus file lower layer (/bin/sh)...")
    cnt.storage.delete_file("/bin/sh")
    
    cnt.storage.render_layers()

    # Step 3: cgroups v2 Enforcement
    print_header("SIMULASI CONTROL GROUPS V2 (RESOURCE CONSTRAINTS)")
    print(f"Konfigurasi Limit -> Memory: {cnt.cgroups.memory_limit_mb}MB | CPU Quota: {cnt.cgroups.cpu_quota_pct}%")

    cnt.cgroups.stress_cpu(85)
    cnt.cgroups.allocate_memory(24)
    cnt.cgroups.allocate_memory(40)  # Ini akan memicu OOM Killer

    # Step 4: Lifecycle Cleanup
    print_header("SIMULASI DAUR HIDUP AKHIR (LIFECYCLE TEARDOWN)")
    cnt.pause()
    cnt.unpause()
    cnt.stop()

    print_header("RINGKASAN TEKNIS LAB")
    print(f"""{GREEN}Semua pilar fondasi container telah diverifikasi:{RESET}
  1. {BOLD}Namespaces{RESET}: Menyekat visibilitas sistem (UTS, PID, NET, MNT).
  2. {BOLD}cgroups v2{RESET}: Mengatur dan membatasi alokasi resource (CPU throttling & OOM).
  3. {BOLD}OverlayFS{RESET}: Menggabungkan layer read-only image dengan writable container layer.
  4. {BOLD}Lifecycle{RESET}: Mengendalikan transisi proses container dari create hingga stop.
""")

if __name__ == "__main__":
    try:
        run_interactive_lab()
    except KeyboardInterrupt:
        print(f"\n{RED}[INTERRUPT] Simulasi dihentikan oleh pengguna.{RESET}")
        sys.exit(0)
