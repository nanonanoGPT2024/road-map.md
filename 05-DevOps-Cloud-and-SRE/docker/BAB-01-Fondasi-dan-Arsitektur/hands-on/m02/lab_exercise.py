#!/usr/bin/env python3
"""
Lab Exercise: Docker Bab 01 Modul 02
Deep Dive Arsitektur Container, Linux Kernel Primitives & OCI Runtime Simulator
-------------------------------------------------------------------------------
Simulasi teknis independen (Python 3 native) yang merefleksikan:
1. OCI Execution Flow (Docker CLI -> dockerd -> containerd -> shim-v2 -> runc)
2. Linux Kernel Namespaces isolation (PID, NET, MNT, IPC, UTS, USER, CGROUP)
3. Cgroups v2 Hierarchy & Out-of-Memory (OOM) Killer Simulation
4. OverlayFS Copy-on-Write (CoW) Engine & Copy-Up Overhead
5. Security Hardening (Capabilities Drop & PID 1 Zombie Reaping)
"""

import sys
import os
import time
import random
from dataclasses import dataclass, field
from typing import List, Dict, Optional

# ==============================================================================
# ANSI Color Palette & Terminal Styling
# ==============================================================================
class Color:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RED     = "\033[31m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    BLUE    = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN    = "\033[36m"
    WHITE   = "\033[37m"
    BG_BLUE = "\033[44m"
    BG_RED  = "\033[41m"

def badge(text: str, color: str = Color.CYAN) -> str:
    return f"{color}[{text}]{Color.RESET}"

def log_info(msg: str) -> None:
    print(f" {badge('INFO', Color.BLUE)} {msg}")

def log_success(msg: str) -> None:
    print(f" {badge('PASS', Color.GREEN)} {Color.GREEN}{msg}{Color.RESET}")

def log_warn(msg: str) -> None:
    print(f" {badge('WARN', Color.YELLOW)} {Color.YELLOW}{msg}{Color.RESET}")

def log_error(msg: str) -> None:
    print(f" {badge('FAIL', Color.RED)} {Color.RED}{msg}{Color.RESET}")

def log_step(step_num: int, title: str) -> None:
    print(f"\n{Color.BOLD}{Color.MAGENTA}=== Tahap {step_num}: {title} ==={Color.RESET}")

# ==============================================================================
# Model & Domain Objects
# ==============================================================================
@dataclass
class NamespaceState:
    ns_type: str
    host_id: int
    container_id: int
    status: str = "Active"

@dataclass
class OverlayFile:
    filename: str
    size_kb: int
    layer: str  # 'lower' or 'upper'
    modified: bool = False

# ==============================================================================
# 1. OCI Execution Pipeline Simulation
# ==============================================================================
class OCIRuntimePipeline:
    """Mensimulasikan transisi kontrol dari Docker CLI hingga Kernel Syscall."""
    
    PIPELINE_STAGES = [
        ("Docker CLI", "Translasi argumen CLI & parsing flags isolasi", "unix:///var/run/docker.sock"),
        ("dockerd (Daemon)", "Generasi OCI bundle specification (config.json) & auth check", "gRPC /run/containerd/containerd.sock"),
        ("containerd", "Supervisi container lifecycle & distribusi image snapshot", "Internal API"),
        ("containerd-shim-v2", "Detasemen stdio, penanganan PID 1 exit status & headless daemon", "FIFO / PTY stream"),
        ("runc (OCI Runtime)", "Eksekusi libcontainer syscalls: clone(), setns(), pivot_root()", "Linux Kernel Syscall")
    ]

    def execute(self, container_name: str) -> bool:
        log_step(1, f"OCI Execution Chain untuk Container: {container_name}")
        for idx, (actor, desc, iface) in enumerate(self.PIPELINE_STAGES, start=1):
            time.sleep(0.08)
            print(f"  {Color.CYAN}--> [{idx}/5] {Color.BOLD}{actor:<20}{Color.RESET} | {Color.DIM}Interface: {iface:<36}{Color.RESET}")
            print(f"      {Color.WHITE}Tugas: {desc}{Color.RESET}")
        log_success("Runc berhasil mengeksekusi container process payload.")
        return True

# ==============================================================================
# 2. Linux Kernel Namespaces Isolation
# ==============================================================================
class NamespaceEngine:
    """Mensimulasikan isolasi virtualisasi 7 subsistem Linux Kernel Namespaces."""
    
    NAMESPACES = {
        "pid":     ("CLONE_NEWPID", 4026531836, 1, "Proses container terisolasi, melihat PID dirinya sebagai PID 1"),
        "net":     ("CLONE_NEWNET", 4026531992, 1001, "Loopback & veth-pair terpisah dari host network stack"),
        "mnt":     ("CLONE_NEWNS",  4026531840, 2001, "Mount table terisolasi via pivot_root() dari rootfs host"),
        "ipc":     ("CLONE_NEWIPC", 4026531839, 3001, "System V IPC and POSIX message queue segment terisolasi"),
        "uts":     ("CLONE_NEWUTS", 4026531838, 4001, "Hostname dan NIS domain name independen"),
        "user":    ("CLONE_NEWUSER",4026531837, 5001, "UID 0 container dipetakan ke UID 10001 di rootless host"),
        "cgroup":  ("CLONE_NEWCGROUP",4026531835, 6001, "Virtual root cgroups view dari perspektif container")
    }

    def inspect_namespaces(self) -> None:
        log_step(2, "Verifikasi Primitif Linux Kernel Namespaces")
        print(f"  {Color.BOLD}{'Subsystem':<10} {'Kernel Flag':<16} {'Host Inode':<14} {'Cnt Inode':<14} {'Status':<10}{Color.RESET}")
        print("  " + "-" * 68)
        for ns, (flag, h_inode, c_inode, detail) in self.NAMESPACES.items():
            print(f"  {Color.YELLOW}{ns:<10}{Color.RESET} {flag:<16} {h_inode:<14} {c_inode:<14} {Color.GREEN}ISOLATED{Color.RESET}")
            print(f"  {Color.DIM}      `-> {detail}{Color.RESET}")
            time.sleep(0.04)
        log_success("Seluruh namespace boundary berhasil diinisialisasi secara deterministik.")

# ==============================================================================
# 3. Cgroups v2 & Out-of-Memory (OOM) Killer Simulation
# ==============================================================================
class CgroupV2MemoryController:
    """Mensimulasikan hierarki cgroups v2 resource metering dan OOM Killer."""

    def __init__(self, cgroup_path: str, memory_max_mb: int, memory_high_mb: int):
        self.path = cgroup_path
        self.memory_max = memory_max_mb
        self.memory_high = memory_high_mb
        self.current_usage = 0

    def simulate_workload(self, allocation_steps_mb: List[int]) -> None:
        log_step(3, f"Cgroups v2 Resource Limiter & OOM Killer ({self.path})")
        log_info(f"Konfigurasi batas: memory.max={self.memory_max}MB | memory.high={self.memory_high}MB")

        for step, alloc in enumerate(allocation_steps_mb, start=1):
            self.current_usage += alloc
            bar_len = 24
            pct = min(1.0, self.current_usage / self.memory_max)
            filled = int(bar_len * pct)
            bar = "#" * filled + "-" * (bar_len - filled)

            color = Color.GREEN if pct < 0.8 else (Color.YELLOW if pct <= 1.0 else Color.RED)
            print(f"  [Step {step}] Alokasi +{alloc}MB -> Total: {self.current_usage:3d}MB / {self.memory_max}MB [{color}{bar}{Color.RESET}]", end="")

            if self.current_usage > self.memory_max:
                print(f" {Color.BG_RED}{Color.WHITE} OOM KILLED {Color.RESET}")
                log_error(f"Kernel OOM-Killer terpicu! Invocation detail:")
                print(f"      {Color.RED}kernel: [cgroup-oom] Task in {self.path} killed as result of limit reached.{Color.RESET}")
                print(f"      {Color.RED}kernel: Memory cgroup out of memory: Kill process (victim PID 4821 [worker]){Color.RESET}")
                log_warn("Container keluar dengan Exit Code 137 (128 + SIGKILL 9).")
                return
            elif self.current_usage >= self.memory_high:
                print(f" {Color.YELLOW}[THROTTLED - memory.high]{Color.RESET}")
                log_warn("Kernel melakukan synchronous memory reclaim throttling.")
            else:
                print(f" {Color.GREEN}[OK]{Color.RESET}")
            time.sleep(0.06)

        log_success("Workload selesai tanpa melanggar batasan memory.max.")

# ==============================================================================
# 4. Storage Engine: OverlayFS Copy-on-Write (CoW) Simulation
# ==============================================================================
class OverlayFSEngine:
    """Mensimulasikan arsitektur lowerdir, upperdir, workdir, merged dan copy-up."""

    def __init__(self):
        # Lowerdir (Read-Only Image Layers)
        self.lowerdir: Dict[str, OverlayFile] = {
            "etc/nginx.conf": OverlayFile("etc/nginx.conf", 4, "lower"),
            "usr/bin/nginx":  OverlayFile("usr/bin/nginx", 1250, "lower"),
            "var/log/app.log": OverlayFile("var/log/app.log", 15, "lower"),
            "var/data/big.db": OverlayFile("var/data/big.db", 51200, "lower")  # 50MB
        }
        # Upperdir (Read-Write Container Layer)
        self.upperdir: Dict[str, OverlayFile] = {}

    def read_file(self, path: str) -> None:
        if path in self.upperdir:
            f = self.upperdir[path]
            print(f"  [VFS READ]  {path:<20} -> Ditemukan di {Color.CYAN}upperdir (RW){Color.RESET} [Size: {f.size_kb}KB]")
        elif path in self.lowerdir:
            f = self.lowerdir[path]
            print(f"  [VFS READ]  {path:<20} -> Ditemukan di {Color.BLUE}lowerdir (RO){Color.RESET} [Size: {f.size_kb}KB, Fast Hit]")
        else:
            log_error(f"File {path} tidak ditemukan di sistem berkas OverlayFS.")

    def write_file(self, path: str, extra_kb: int) -> None:
        print(f"  [VFS WRITE] Modifikasi file: {Color.BOLD}{path}{Color.RESET}")
        if path in self.upperdir:
            self.upperdir[path].size_kb += extra_kb
            self.upperdir[path].modified = True
            print(f"      {Color.GREEN}`-> Target sudah ada di upperdir. Menulis langsung tanpa latency copy-up.{Color.RESET}")
        elif path in self.lowerdir:
            # Copy-Up Triggered!
            origin = self.lowerdir[path]
            print(f"      {Color.YELLOW}`-> CoW Trigger: File berada di lowerdir (RO). Memulai kernel copy-up...{Color.RESET}")
            # Simulasi latensi copy-up sebanding dengan ukuran file
            latency_ms = max(1.0, origin.size_kb / 1024.0 * 2.5)
            time.sleep(min(0.15, latency_ms / 1000.0))
            self.upperdir[path] = OverlayFile(
                filename=path,
                size_kb=origin.size_kb + extra_kb,
                layer="upper",
                modified=True
            )
            print(f"      {Color.MAGENTA}`-> Copy-up selesai: {origin.size_kb}KB disalin dari lower -> upper ({latency_ms:.2f}ms latency penalty){Color.RESET}")
        else:
            # Create brand new file in upperdir
            self.upperdir[path] = OverlayFile(filename=path, size_kb=extra_kb, layer="upper", modified=False)
            print(f"      {Color.CYAN}`-> File baru dibuat langsung pada upperdir.{Color.RESET}")

    def simulate(self) -> None:
        log_step(4, "Driver Penyimpanan OverlayFS & Copy-on-Write (CoW)")
        log_info("Struktur Layer: lowerdir=/var/lib/docker/overlay2/<id>/diff (RO) | upperdir=rw (RW)")
        self.read_file("usr/bin/nginx")
        self.write_file("etc/nginx.conf", extra_kb=1)      # File kecil
        self.write_file("var/data/big.db", extra_kb=1024)   # File besar (50MB) -> Menimbulkan I/O stall
        self.read_file("etc/nginx.conf")
        log_success("Mekanisme Copy-up dan masking dentry OverlayFS terverifikasi.")

# ==============================================================================
# 5. Enterprise Hardening & Zombie Reaping
# ==============================================================================
class HardeningSimulator:
    """Mensimulasikan Linux Capabilities Auditing dan Mitigasi Zombie Process (PID 1)."""

    CAPABILITIES_BASELINE = [
        ("CAP_CHOWN", False, "Ubah kepemilikan file (DIDROP)"),
        ("CAP_NET_RAW", False, "Bypass packet filtering / ICMP raw sockets (DIDROP)"),
        ("CAP_SYS_ADMIN", False, "Superuser kernel capabilities / mount (DIDROP)"),
        ("CAP_NET_BIND_SERVICE", True, "Bind socket ke port istimewa < 1024 (DIIZINKAN)"),
        ("CAP_SETUID", False, "Ubah UID sembarang (DIDROP)")
    ]

    def audit_capabilities(self) -> None:
        log_step(5, "Audit Hardening: Linux Capabilities (`--cap-drop=ALL`)")
        print(f"  {Color.BOLD}{'Capability':<24} {'Status':<12} {'Keterangan':<40}{Color.RESET}")
        print("  " + "-" * 70)
        for cap, allowed, desc in self.CAPABILITIES_BASELINE:
            status_str = f"{Color.GREEN}ALLOWED{Color.RESET}" if allowed else f"{Color.RED}DROPPED{Color.RESET}"
            print(f"  {Color.YELLOW}{cap:<24}{Color.RESET} {status_str:<21} {Color.DIM}{desc}{Color.RESET}")
            time.sleep(0.03)

    def simulate_pid1_zombie_reaping(self) -> None:
        print(f"\n  {Color.BOLD}Simulasi PID 1 Reaping (Mitigasi Zombie Processes):{Color.RESET}")
        print(f"  {Color.CYAN}[tini/dumb-init as PID 1]{Color.RESET} Spawn child process worker (PID 14)")
        time.sleep(0.04)
        print(f"  {Color.CYAN}[Worker PID 14]{Color.RESET} Spawn ephemeral task (PID 15)")
        time.sleep(0.04)
        print(f"  {Color.RED}[Worker PID 14]{Color.RESET} Terminated mendadak tanpa memanggil waitpid() pada PID 15!")
        print(f"  {Color.YELLOW}[Kernel]{Color.RESET} Orphan process PID 15 diadopsi oleh PID 1 (Init System).")
        print(f"  {Color.GREEN}[PID 1 (tini)]{Color.RESET} Menangkap sinyal SIGCHLD, mengeksekusi reap sys_wait4(), mencegah PID exhaustion.")
        log_success("Tini/Init berhasil membersihkan zombie process dan meneruskan POSIX signals.")

# ==============================================================================
# Main Orchestrator
# ==============================================================================
def run_full_lab() -> None:
    print(f"{Color.BOLD}{Color.CYAN}=================================================================={Color.RESET}")
    print(f"{Color.BOLD}{Color.WHITE}   DOCKER BAB 01 MODUL 02: DEEP DIVE ARSITEKTUR & PRIMITIF KERNEL   {Color.RESET}")
    print(f"{Color.DIM}   Simulasi Komprehensif OCI, Namespaces, Cgroups v2 & Storage      {Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}=================================================================={Color.RESET}")

    # 1. OCI Execution Pipeline
    oci = OCIRuntimePipeline()
    oci.execute(container_name="prod-gateway-service")

    # 2. Linux Namespaces
    ns = NamespaceEngine()
    ns.inspect_namespaces()

    # 3. Cgroups v2 & OOM Killer
    cgroups = CgroupV2MemoryController(
        cgroup_path="/sys/fs/cgroup/docker/prod-gateway-service",
        memory_max_mb=256,
        memory_high_mb=200
    )
    # Workload yang melebihi batas 256MB untuk memicu OOM Killer
    cgroups.simulate_workload([64, 64, 64, 32, 64])

    # 4. Storage Engine: OverlayFS
    storage = OverlayFSEngine()
    storage.simulate()

    # 5. Hardening & Zombie Reaping
    hardening = HardeningSimulator()
    hardening.audit_capabilities()
    hardening.simulate_pid1_zombie_reaping()

    # Final Summary
    print(f"\n{Color.BOLD}{Color.GREEN}=================================================================={Color.RESET}")
    print(f"{Color.BOLD}{Color.GREEN}    HASIL AUDIT SIMULASI LAB MODUL 02: SEMUA TAHAP SUKSES          {Color.RESET}")
    print(f"{Color.DIM}    Seluruh primitif isolasi kernel dan runtime OCI tervalidasi. {Color.RESET}")
    print(f"{Color.BOLD}{Color.GREEN}=================================================================={Color.RESET}\n")

if __name__ == "__main__":
    run_full_lab()
