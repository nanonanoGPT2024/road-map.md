#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Arsitektur Kernel, Bootstrapping, dan Init System Linux
BAB-01: Arsitektur Kernel, Bootstrapping, dan Init System
"""

import sys
import time
import argparse
from typing import Dict, List, Set

# ANSI Color Codes untuk Terminal Styling
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

def print_header(title: str) -> None:
    print(f"\n{BOLD}{CYAN}{'=' * 65}{RESET}")
    print(f"{BOLD}{WHITE}  {title.center(61)}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 65}{RESET}\n")

def print_status(component: str, status: str = "OK", delay: float = 0.05) -> None:
    time.sleep(delay)
    if status == "OK":
        badge = f"{BOLD}{GREEN}[  OK  ]{RESET}"
    elif status == "INFO":
        badge = f"{BOLD}{BLUE}[ INFO ]{RESET}"
    elif status == "WARN":
        badge = f"{BOLD}{YELLOW}[ WARN ]{RESET}"
    else:
        badge = f"{BOLD}{RED}[ FAIL ]{RESET}"
    print(f"{badge} {component}")

class LinuxBootSimulator:
    """Simulasi tahapan boot sequence dari POST hingga PID 1 Systemd."""

    def __init__(self, step_delay: float = 0.03):
        self.delay = step_delay

    def stage_firmware(self) -> None:
        print_header("TAHAP 1: FIRMWARE (UEFI / BIOS) & POST")
        print_status("Power-On Self-Test (POST) checking hardware registers...", "OK", self.delay)
        print_status("CPU Initialization: Bootstrap Processor (BSP) active", "OK", self.delay)
        print_status("Memory verification: 16384 MB detected & mapped", "OK", self.delay)
        print_status("NVMe/SATA controller probed: /dev/nvme0n1 detected", "OK", self.delay)
        print_status("Reading EFI System Partition (ESP) UUID: 4A12-9F01", "OK", self.delay)
        print_status("Executing UEFI Boot Manager: \\EFI\\systemd\\systemd-bootx64.efi", "INFO", self.delay)

    def stage_bootloader(self) -> None:
        print_header("TAHAP 2: BOOTLOADER (GRUB2 / SYSTEMD-BOOT)")
        print_status("Bootloader initialized into memory", "OK", self.delay)
        print_status("Parsing boot configuration (/boot/loader/entries/linux.conf)", "OK", self.delay)
        print(f"       {DIM}Cmdline: BOOT_IMAGE=/vmlinuz-6.8.0-generic root=UUID=b28c ro quiet splash{RESET}")
        print_status("Loading kernel image into RAM: /boot/vmlinuz-6.8.0-generic", "OK", self.delay)
        print_status("Loading Initial RAM Disk into RAM: /boot/initramfs-6.8.0.img", "OK", self.delay)
        print_status("Transferring CPU execution control to kernel entry (startup_64)", "INFO", self.delay)

    def stage_kernel_bootstrap(self) -> None:
        print_header("TAHAP 3: KERNEL DECOMPRESSION & INITIALIZATION")
        print_status("Kernel self-decompression complete (zImage/bzImage -> vmlinux)", "OK", self.delay)
        print_status("CPU switches to Long Mode (64-bit paging enabled)", "OK", self.delay)
        print_status("Initializing Kernel Memory Management: Buddy Allocator & SLUB", "OK", self.delay)
        print_status("Initializing Interrupt Descriptor Table (IDT) & Syscall handlers", "OK", self.delay)
        print_status("ACPI tables parsed: 8 logical cores brought online (SMP)", "OK", self.delay)
        print_status("Kernel device tree / sysfs drivers registered", "OK", self.delay)

    def stage_initramfs(self) -> None:
        print_header("TAHAP 4: EARLY USERSPACE (INITRAMFS) & PIVOT_ROOT")
        print_status("Extracting CPIO initramfs archive to rootfs (tmpfs)", "OK", self.delay)
        print_status("Executing /init script in early userspace", "OK", self.delay)
        print_status("Loading essential storage modules (nvme, ext4, dm_mod)", "OK", self.delay)
        print_status("Scanning LVM/LUKS storage volumes", "OK", self.delay)
        print_status("Root device located: /dev/nvme0n1p2 mounted read-only on /sysroot", "OK", self.delay)
        print_status("Executing pivot_root(): switching /sysroot to real root filesystem (/)", "OK", self.delay)
        print_status("Umounting early initramfs memory footprint", "OK", self.delay)

    def stage_pid1_init(self) -> None:
        print_header("TAHAP 5: SPAWNING PID 1 (SYSTEMD)")
        print_status("Executing /sbin/init -> /lib/systemd/systemd as PID 1", "INFO", self.delay)
        print_status("Mounted cgroup2 virtual hierarchy on /sys/fs/cgroup", "OK", self.delay)
        print_status("Loaded systemd unit dependency database", "OK", self.delay)
        print_status("Reached target: sysinit.target (System Initialization)", "OK", self.delay)
        print_status("Reached target: basic.target (Basic System)", "OK", self.delay)
        print_status("Started systemd-journald.service (Journal Service)", "OK", self.delay)
        print_status("Started systemd-udevd.service (Device Manager)", "OK", self.delay)
        print_status("Reached target: network.target (Network)", "OK", self.delay)
        print_status("Started sshd.service (OpenSSH Daemon)", "OK", self.delay)
        print_status("Reached target: multi-user.target (Multi-User System Ready)", "OK", self.delay)

    def run_full_boot(self) -> None:
        self.stage_firmware()
        self.stage_bootloader()
        self.stage_kernel_bootstrap()
        self.stage_initramfs()
        self.stage_pid1_init()
        print(f"\n{BOLD}{GREEN}[SUCCESS]{RESET} Sistem Linux berhasil boot ke multi-user mode!\n")


class KernelArchitectureExplorer:
    """Eksplorasi ring proteksi x86_64 dan transisi Syscall."""

    @staticmethod
    def show_rings() -> None:
        print_header("ARSITEKTUR PRIVILEGE RINGS (x86_64)")
        diagram = f"""
    {BOLD}{CYAN}+-----------------------------------------------------------+{RESET}
    {BOLD}{CYAN}|{RESET} {BOLD}{GREEN}Ring 3: User Space (Unprivileged Mode){RESET}                    {BOLD}{CYAN}|{RESET}
    {BOLD}{CYAN}|{RESET}  - User Applications: Bash, Python, Nginx, Browser        {BOLD}{CYAN}|{RESET}
    {BOLD}{CYAN}|{RESET}  - Standard C Library (glibc / musl)                       {BOLD}{CYAN}|{RESET}
    {BOLD}{CYAN}|{RESET}  - Ruang memori terisolasi (Virtual Memory Protection)     {BOLD}{CYAN}|{RESET}
    {BOLD}{CYAN}+-----------------------------+-----------------------------+{RESET}
                                  |
                   [ SYSCALL / SYSRET / INT 80h ]
                                  v
    {BOLD}{CYAN}+-----------------------------+-----------------------------+{RESET}
    {BOLD}{CYAN}|{RESET} {BOLD}{RED}Ring 0: Kernel Space (Supervisor Mode){RESET}                    {BOLD}{CYAN}|{RESET}
    {BOLD}{CYAN}|{RESET}  - Monolithic Kernel Core (Linux)                          {BOLD}{CYAN}|{RESET}
    {BOLD}{CYAN}|{RESET}  - Process Scheduler, Virtual File System (VFS)            {BOLD}{CYAN}|{RESET}
    {BOLD}{CYAN}|{RESET}  - Memory Management Unit (MMU Paging, Page Tables)        {BOLD}{CYAN}|{RESET}
    {BOLD}{CYAN}|{RESET}  - Network Stack, Device Drivers, Direct Hardware Access   {BOLD}{CYAN}|{RESET}
    {BOLD}{CYAN}+-----------------------------------------------------------+{RESET}
        """
        print(diagram)

    @staticmethod
    def trace_syscall(call_name: str = "write") -> None:
        print_header(f"TRACING SYSTEM CALL: {call_name.upper()}()")
        steps = [
            ("User Code (Ring 3)", "Memanggil write(1, 'Halo Linux\\n', 11) via glibc wrapper"),
            ("Register Prep", "Memuat opcode syscall ke RAX (1), argumen ke RDI, RSI, RDX"),
            ("CPU Privilege Switch", "Instruksi CPU 'syscall' dieksekusi: Ring 3 -> Ring 0"),
            ("Kernel Entry", "MSR_LSTAR melompat ke fungsi entry_SYSCALL_64"),
            ("Kernel VFS", "sys_write() memvalidasi pointer memori user & file descriptor"),
            ("Device Driver", "TTY driver kernel menulis buffer ke perangkat terminal"),
            ("CPU Return Switch", "Instruksi 'sysretq' dieksekusi: Ring 0 -> Ring 3"),
            ("User Return", "glibc mengembalikan byte count (11) ke program pemanggil"),
        ]
        for idx, (stage, desc) in enumerate(steps, start=1):
            time.sleep(0.04)
            print(f" {BOLD}{YELLOW}[Step {idx}]{RESET} {BOLD}{stage:<22}{RESET} -> {desc}")
        print(f"\n{BOLD}{GREEN}[DONE]{RESET} Siklus Syscall {call_name}() selesai dieksekusi tanpa fault.\n")


class SystemdDependencyEngine:
    """Engine simulasi dependensi unit Systemd (Topological Sort)."""

    def __init__(self):
        # Graph: Unit -> daftar unit yang dibutuhkannya (Requires / After)
        self.graph: Dict[str, List[str]] = {
            "graphical.target": ["multi-user.target", "display-manager.service"],
            "display-manager.service": ["multi-user.target"],
            "multi-user.target": ["basic.target", "sshd.service", "systemd-logind.service"],
            "sshd.service": ["network.target"],
            "systemd-logind.service": ["dbus.service"],
            "dbus.service": ["basic.target"],
            "network.target": ["basic.target", "systemd-networkd.service"],
            "systemd-networkd.service": ["basic.target"],
            "basic.target": ["sysinit.target", "sockets.target"],
            "sockets.target": ["sysinit.target"],
            "sysinit.target": ["systemd-udevd.service", "local-fs.target"],
            "systemd-udevd.service": [],
            "local-fs.target": [],
        }

    def resolve_order(self, target: str) -> List[str]:
        visited: Set[str] = set()
        order: List[str] = []

        def dfs(node: str) -> None:
            if node in visited:
                return
            visited.add(node)
            for neighbor in self.graph.get(node, []):
                dfs(neighbor)
            order.append(node)

        dfs(target)
        return order

    def simulate_activation(self, target: str = "multi-user.target") -> None:
        print_header(f"SYSTEMD BOOT RESOLVER: TARGET '{target}'")
        order = self.resolve_order(target)
        print(f"{BOLD}Urutan aktivasi unit berdasarkan Directed Acyclic Graph (DAG):{RESET}\n")
        for idx, unit in enumerate(order, start=1):
            time.sleep(0.03)
            unit_type = "TARGET" if unit.endswith(".target") else "SERVICE"
            color = MAGENTA if unit_type == "TARGET" else CYAN
            print(f" {idx:02d}. {color}[{unit_type:<7}]{RESET} Activating: {BOLD}{unit}{RESET}")
        print(f"\n{BOLD}{GREEN}[SUCCESS]{RESET} Seluruh {len(order)} unit berhasil diselesaikan secara topologis!\n")


class InteractiveQuiz:
    """Kuis evaluasi pemahaman arsitektur kernel & bootstrapping."""

    QUESTIONS = [
        {
            "q": "Komponen apa yang pertama kali dieksekusi CPU saat komputer dinyalakan?",
            "choices": ["GRUB2 Bootloader", "Firmware (BIOS / UEFI)", "Kernel vmlinuz", "Systemd PID 1"],
            "answer": 1,
            "explain": "Firmware (BIOS/UEFI) disimpan di chip non-volatile motherboard dan mengeksekusi POST pertama kali."
        },
        {
            "q": "Instruksi apa yang digunakan arsitektur x86_64 modern untuk transisi dari Ring 3 ke Ring 0?",
            "choices": ["CALL FAR", "JMP INTERRUPT", "SYSCALL", "SYSENTER32"],
            "answer": 2,
            "explain": "x86_64 menggunakan instruksi SYSCALL (dan SYSRET untuk kembali) untuk fast system calls."
        },
        {
            "q": "Apa peran utama initramfs dalam proses boot Linux modern?",
            "choices": [
                "Menjalankan GUI desktop environment",
                "Menyediakan driver dan script untuk menemukan serta me-mount root filesystem asli",
                "Mengkompilasi kernel Linux dari source code",
                "Menghapus log kernel lama"
            ],
            "answer": 1,
            "explain": "Initramfs adalah early userspace yang memuat driver storage/RAID/LUKS sebelum pivot_root ke disk asli."
        },
    ]

    @classmethod
    def run(cls) -> None:
        print_header("KUIS INTERAKTIF: LINUX BOOTSTRAPPING & KERNEL")
        score = 0
        for i, item in enumerate(cls.QUESTIONS, start=1):
            print(f"{BOLD}Pertanyaan {i}:{RESET} {item['q']}")
            for idx, ch in enumerate(item["choices"], start=1):
                print(f"  {idx}) {ch}")
            
            choice = 0
            while choice not in [1, 2, 3, 4]:
                try:
                    user_input = input(f"{BOLD}Pilihan Anda (1-4): {RESET}").strip()
                    choice = int(user_input)
                except (ValueError, EOFError):
                    choice = 1
                    break

            if choice - 1 == item["answer"]:
                print(f"{BOLD}{GREEN}✓ Benar!{RESET} {item['explain']}\n")
                score += 1
            else:
                correct_idx = item["answer"] + 1
                print(f"{BOLD}{RED}✗ Kurang tepat.{RESET} Jawaban benar: ({correct_idx}) {item['choices'][item['answer']]}")
                print(f"  {DIM}{item['explain']}{RESET}\n")

        print(f"{BOLD}{CYAN}Skor Akhir:{RESET} {score}/{len(cls.QUESTIONS)} pertanyaan benar.")


def interactive_menu() -> None:
    boot_sim = LinuxBootSimulator()
    dep_engine = SystemdDependencyEngine()

    while True:
        print_header("LAB SIMULATOR: BAB 01 LINUX CORE FOUNDATIONS")
        print(f" {BOLD}1.{RESET} Simulasi Lengkap Linux Boot Sequence (UEFI -> Systemd)")
        print(f" {BOLD}2.{RESET} Visualisasi x86_64 Privilege Rings (Ring 0 vs Ring 3)")
        print(f" {BOLD}3.{RESET} Tracing Siklus Eksekusi System Call (write)")
        print(f" {BOLD}4.{RESET} Analisis Systemd Unit DAG & Dependency Resolution")
        print(f" {BOLD}5.{RESET} Uji Pemahaman: Kuis Interaktif")
        print(f" {BOLD}6.{RESET} Keluar")
        print()

        try:
            choice = input(f"{BOLD}Pilih opsi [1-6]: {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar dari lab simulator.")
            break

        if choice == "1":
            boot_sim.run_full_boot()
        elif choice == "2":
            KernelArchitectureExplorer.show_rings()
        elif choice == "3":
            KernelArchitectureExplorer.trace_syscall("write")
        elif choice == "4":
            dep_engine.simulate_activation("multi-user.target")
        elif choice == "5":
            InteractiveQuiz.run()
        elif choice == "6":
            print(f"\n{BOLD}{GREEN}Terima kasih telah menjalankan Lab BAB 01!{RESET}\n")
            break
        else:
            print(f"{BOLD}{RED}Opsi tidak valid. Masukkan angka 1 sampai 6.{RESET}")

        input(f"{DIM}Tekan [Enter] untuk melanjutkan...{RESET}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulasi Arsitektur Kernel & Bootstrapping Linux")
    parser.add_argument("--auto-test", action="store_true", help="Jalankan semua modul secara otomatis tanpa prompt interaktif")
    args = parser.parse_args()

    if args.auto_test or not sys.stdin.isatty():
        # Non-interactive automated smoke test
        print(f"{BOLD}{YELLOW}[AUTO-TEST MODE ACTIVATED]{RESET}")
        sim = LinuxBootSimulator(step_delay=0.001)
        sim.run_full_boot()
        KernelArchitectureExplorer.show_rings()
        KernelArchitectureExplorer.trace_syscall("write")
        engine = SystemdDependencyEngine()
        engine.simulate_activation("multi-user.target")
        print(f"{BOLD}{GREEN}Auto-test selesai: Semua modul tervalidasi berjalan sukses.{RESET}")
    else:
        interactive_menu()


if __name__ == "__main__":
    main()
