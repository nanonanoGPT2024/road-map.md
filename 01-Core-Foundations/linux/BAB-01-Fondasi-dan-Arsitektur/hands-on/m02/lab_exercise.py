#!/usr/bin/env python3
"""
Lab Hands-on: Arsitektur Kernel, Bootstrapping, dan Inisialisasi Sistem Linux
Modul: 01-Core-Foundations / Bab 01 - Deep Dive

Deskripsi:
Script ini memodelkan alur booting arsitektur Linux x86_64 secara low-level:
1. Peralihan Mode CPU (Real Mode -> Protected Mode -> Long Mode 64-bit).
2. Setup MMU 4-Level Paging (PML4 -> PDPT -> PD -> PT) dan translasi Virtual-ke-Fisikal.
3. Dekompresi dan validasi integritas Initramfs (CPIO mock archive).
4. Mekanisme VFS mount, switch_root (pivot_root), dan isolasi mount namespace.
5. Transisi Kernel Process (PID 0 / swapper) ke PID 1 (systemd/init).
6. Dependency Graph Engine untuk systemd target resolution (Topological Sort).
"""

import sys
import time
import hashlib
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple

# --- ANSI Formatting Configuration ---
class Color:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    RED     = "\033[31m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    BLUE    = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN    = "\033[36m"
    WHITE   = "\033[37m"
    DIM     = "\033[2m"

def klog(timestamp: float, facility: str, message: str, level: str = "INFO") -> None:
    """Simulasi printk kernel dmesg logger dengan formatting terstruktur."""
    color_map = {
        "INFO": Color.GREEN,
        "WARN": Color.YELLOW,
        "CRIT": Color.RED,
        "DEBUG": Color.DIM + Color.WHITE
    }
    lvl_color = color_map.get(level, Color.WHITE)
    print(f"{Color.DIM}[{timestamp:10.6f}]{Color.RESET} "
          f"{Color.BOLD}{Color.CYAN}[{facility:<10}]{Color.RESET} "
          f"{lvl_color}{level:<5}{Color.RESET}: {message}")


# --- Bagian 1: Model Hardware & MMU 4-Level Paging (x86_64) ---
class CPUMode(Enum):
    REAL_MODE_16BIT = auto()
    PROTECTED_MODE_32BIT = auto()
    LONG_MODE_64BIT = auto()

@dataclass
class PageTableEntry:
    present: bool = True
    writable: bool = True
    user_accessible: bool = False
    physical_frame: int = 0

class MemoryManagementUnit:
    """
    Simulasi MMU x86_64 4-Level Paging (CR3 -> PML4 -> PDPT -> PD -> PT).
    Memetakan canonical virtual addresses ke physical memory frames.
    """
    PAGE_SIZE = 4096  # 4 KiB
    
    def __init__(self):
        # Tabel halaman berbasis kamus bertingkat: pml4[idx] -> pdpt[idx] -> pd[idx] -> pt[idx] -> Frame
        self.pml4: Dict[int, Dict[int, Dict[int, Dict[int, PageTableEntry]]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(dict))
        )
        self.cr3_base: int = 0x100000  # Physical address root PML4

    def map_page(self, v_addr: int, p_addr: int, writable: bool = True) -> None:
        """Memetakan virtual address ke physical address menggunakan skema 9-9-9-9-12 bit."""
        pml4_idx = (v_addr >> 39) & 0x1FF
        pdpt_idx = (v_addr >> 30) & 0x1FF
        pd_idx   = (v_addr >> 21) & 0x1FF
        pt_idx   = (v_addr >> 12) & 0x1FF

        frame = p_addr & ~0xFFF
        entry = PageTableEntry(present=True, writable=writable, physical_frame=frame)
        self.pml4[pml4_idx][pdpt_idx][pd_idx][pt_idx] = entry

    def translate(self, v_addr: int) -> Tuple[Optional[int], str]:
        """Translasi virtual address runtime dengan traversing tabel halaman."""
        pml4_idx = (v_addr >> 39) & 0x1FF
        pdpt_idx = (v_addr >> 30) & 0x1FF
        pd_idx   = (v_addr >> 21) & 0x1FF
        pt_idx   = (v_addr >> 12) & 0x1FF
        offset   = v_addr & 0xFFF

        try:
            entry = self.pml4[pml4_idx][pdpt_idx][pd_idx][pt_idx]
            if not entry.present:
                return None, "#PF (Page Fault: Entry Not Present)"
            return entry.physical_frame | offset, "OK"
        except KeyError:
            return None, "#PF (Page Fault: Unmapped Level)"


# --- Bagian 2: Initramfs Simulator & VFS Root Migration ---
@dataclass
class CPIOFile:
    filename: str
    content: bytes
    permissions: int
    checksum: str

class InitramfsArchive:
    """Simulasi in-memory early userspace archive (CPIO image)."""
    def __init__(self):
        self.files: Dict[str, CPIOFile] = {}

    def add_file(self, filename: str, content: bytes, permissions: int = 0o755) -> None:
        chk = hashlib.sha256(content).hexdigest()
        self.files[filename] = CPIOFile(filename, content, permissions, chk)

    def extract_to_vfs(self, target_vfs: Dict[str, bytes]) -> bool:
        """Ekstraksi payload initramfs ke VFS root temporer (rootfs/ramfs)."""
        for fname, cpio_entry in self.files.items():
            calc_chk = hashlib.sha256(cpio_entry.content).hexdigest()
            if calc_chk != cpio_entry.checksum:
                return False
            target_vfs[fname] = cpio_entry.content
        return True


# --- Bagian 3: Systemd Unit Dependency Engine ---
class UnitType(Enum):
    TARGET = "target"
    SERVICE = "service"
    SOCKET = "socket"

@dataclass
class SystemdUnit:
    name: str
    unit_type: UnitType
    requires: List[str] = field(default_factory=list)
    after: List[str] = field(default_factory=list)
    executed: bool = False

class SystemdInitEngine:
    """Engine parsing dan eksekusi dependency graph untuk System Initialization."""
    def __init__(self):
        self.units: Dict[str, SystemdUnit] = {}

    def register_unit(self, unit: SystemdUnit) -> None:
        self.units[unit.name] = unit

    def resolve_boot_order(self, target: str) -> List[str]:
        """
        Menyelesaikan urutan aktivasi unit menggunakan Topological Sort (Kahn's Algorithm).
        Memastikan dependensi 'after' dan 'requires' diproses dalam urutan deterministik.
        """
        in_degree = defaultdict(int)
        graph = defaultdict(list)
        all_relevant_units = set()

        # Eksplorasi sub-graph yang dibutuhkan oleh target
        def collect_deps(u_name: str):
            if u_name in all_relevant_units or u_name not in self.units:
                return
            all_relevant_units.add(u_name)
            for req in self.units[u_name].requires:
                collect_deps(req)

        collect_deps(target)

        # Bangun dependency graph
        for u_name in all_relevant_units:
            unit = self.units[u_name]
            for dep in unit.after:
                if dep in all_relevant_units:
                    graph[dep].append(u_name)
                    in_degree[u_name] += 1

        queue = deque([u for u in all_relevant_units if in_degree[u] == 0])
        resolved_order = []

        while queue:
            curr = queue.popleft()
            resolved_order.append(curr)
            for neighbor in graph[curr]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(resolved_order) != len(all_relevant_units):
            raise RuntimeError("Dependency loop terdeteksi pada systemd unit graph!")

        return resolved_order


# --- Bagian 4: Kernel Bootstrapping Orchestrator ---
class LinuxKernelBootSimulator:
    """Simulator orkestrasi bootstrap kernel Linux dari early assembly hingga userland."""
    
    def __init__(self):
        self.clock = 0.000000
        self.cpu_mode = CPUMode.REAL_MODE_16BIT
        self.mmu = MemoryManagementUnit()
        self.vfs_root: Dict[str, bytes] = {}
        self.initramfs = InitramfsArchive()
        self.init_engine = SystemdInitEngine()
        self.pid_table: Dict[int, str] = {}

    def tick(self, delta: float) -> float:
        self.clock += delta
        return self.clock

    def stage_cpu_modes(self) -> None:
        klog(self.tick(0.000010), "CPU", "CPU diinisialisasi pada Real Mode (16-bit reset vector 0xFFFF0)", "INFO")
        time.sleep(0.05)
        
        # Transisi ke 32-bit Protected Mode
        self.cpu_mode = CPUMode.PROTECTED_MODE_32BIT
        klog(self.tick(0.000120), "CPU", "Global Descriptor Table (GDT) dimuat. Transisi ke Protected Mode (32-bit)", "INFO")
        time.sleep(0.05)

        # Mengaktifkan PAE & Long Mode (EFER.LME = 1)
        self.cpu_mode = CPUMode.LONG_MODE_64BIT
        klog(self.tick(0.000350), "CPU", "Control Register CR4.PAE diset. IA32_EFER.LME diset. Transisi ke Long Mode (64-bit)", "INFO")

    def stage_early_memory(self) -> None:
        klog(self.tick(0.001200), "MMU", "Inisialisasi 4-Level Paging (PML4 base at CR3: 0x100000)", "INFO")
        
        # Identity Mapping untuk Kernel Text Segment (0x1000000 -> 0x1000000)
        kernel_text_v = 0xFFFFFFFF81000000
        kernel_text_p = 0x0000000001000000
        self.mmu.map_page(kernel_text_v, kernel_text_p, writable=False)
        
        # Test MMU address translation
        phys_out, status = self.mmu.translate(kernel_text_v + 0x01A)
        klog(self.tick(0.000500), "MMU", 
             f"Translasi Virtual: 0x{kernel_text_v:X} -> Fisikal: 0x{phys_out:X} (Status: {status})", "DEBUG")

    def stage_initramfs_and_pivot(self) -> None:
        klog(self.tick(0.015000), "INITRAMFS", "Memeriksa archive CPIO terkompresi di memori...", "INFO")
        
        # Injeksi modul kernel mock ke dalam initramfs
        self.initramfs.add_file("/init", b"#!/bin/sh\nexec /sbin/init", 0o755)
        self.initramfs.add_file("/lib/modules/ahci.ko", b"[BINARY_DRIVER_AHCI_SATA]", 0o644)
        self.initramfs.add_file("/etc/fstab", b"UUID=c49a-e11 / ext4 defaults 0 1", 0o644)

        success = self.initramfs.extract_to_vfs(self.vfs_root)
        if not success:
            klog(self.tick(0.001000), "INITRAMFS", "Kerusakan hash digest pada CPIO initramfs!", "CRIT")
            sys.exit(1)
        
        klog(self.tick(0.021000), "VFS", f"Initramfs diekstrak ke rootfs temporer (files: {len(self.vfs_root)})", "INFO")
        
        # Simulasi pivot_root: Mengganti mount rootfs temporer ke disk root sesungguhnya
        klog(self.tick(0.045000), "VFS", "Memuat block driver 'ahci.ko' untuk mendeteksi Root Device...", "INFO")
        klog(self.tick(0.012000), "VFS", "Target root device UUID=c49a-e11 terdeteksi (ext4).", "INFO")
        klog(self.tick(0.008000), "VFS", "pivot_root: Mengalihkan rootfs dari ramfs ke /dev/sda2 (Real Root)", "INFO")

    def stage_spawn_pid1(self) -> None:
        # Kernel idle loop = PID 0 (swapper_process)
        self.pid_table[0] = "swapper/0"
        klog(self.tick(0.010000), "KERNEL", "PID 0 (swapper/0) berjalan pada core utama", "INFO")
        
        # Kernel memanggil sys_fork() & sys_execve() untuk memicu userspace
        self.pid_table[1] = "/sbin/init"
        klog(self.tick(0.035000), "KERNEL", "Kernel mengeksekusi init binary: /sbin/init -> Spawning PID 1", "INFO")

    def stage_userspace_systemd(self) -> None:
        klog(self.tick(0.012000), "SYSTEMD", "Systemd 252.5-1 running in system mode (+PAM +AUDIT +SELINUX)", "INFO")
        
        # Konfigurasi dependensi Systemd Units
        self.init_engine.register_unit(SystemdUnit("system.slice", UnitType.TARGET))
        self.init_engine.register_unit(SystemdUnit("syslog.socket", UnitType.SOCKET, after=["system.slice"]))
        self.init_engine.register_unit(SystemdUnit("systemd-journald.service", UnitType.SERVICE, 
                                                   requires=["syslog.socket"], after=["syslog.socket"]))
        self.init_engine.register_unit(SystemdUnit("networking.service", UnitType.SERVICE, 
                                                   requires=["systemd-journald.service"], after=["systemd-journald.service"]))
        self.init_engine.register_unit(SystemdUnit("multi-user.target", UnitType.TARGET, 
                                                   requires=["networking.service"], after=["networking.service"]))

        order = self.init_engine.resolve_boot_order("multi-user.target")
        
        klog(self.tick(0.005000), "SYSTEMD", "Graf Dependensi Unit berhasil dihitung. Menjalankan Target Order...", "INFO")
        for unit_name in order:
            unit = self.init_engine.units[unit_name]
            unit.executed = True
            time.sleep(0.03)
            klog(self.tick(0.015000), "SYSTEMD", f"Reached target/unit: {Color.BOLD}{unit.name}{Color.RESET}", "INFO")

    def run_simulation(self) -> None:
        """Menjalankan full-cycle pipeline bootstrap sistem."""
        print(f"\n{Color.BOLD}{Color.MAGENTA}=== MEMULAI SIMULATOR BOOTSTRAP KERNEL LINUX x86_64 ==={Color.RESET}\n")
        
        self.stage_cpu_modes()
        self.stage_early_memory()
        self.stage_initramfs_and_pivot()
        self.stage_spawn_pid1()
        self.stage_userspace_systemd()
        
        total_time = self.clock
        print(f"\n{Color.BOLD}{Color.GREEN}=== BOOT SELESAI: Multi-User Target Tercapai ==={Color.RESET}")
        print(f"{Color.CYAN}Total Kernel Boot Time: {Color.BOLD}{total_time:.6f} detik{Color.RESET}")
        print(f"{Color.CYAN}Active Process Table  : {Color.BOLD}{dict(self.pid_table)}{Color.RESET}\n")


if __name__ == "__main__":
    simulator = LinuxKernelBootSimulator()
    simulator.run_simulation()