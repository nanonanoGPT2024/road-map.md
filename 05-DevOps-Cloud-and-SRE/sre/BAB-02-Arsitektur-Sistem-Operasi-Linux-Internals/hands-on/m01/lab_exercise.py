#!/usr/bin/env python3
"""
Lab Exercise: Linux Internals & Kernel Architecture for SRE
BAB-02: Arsitektur Sistem Operasi & Linux Internals
Kategori: SRE Foundation Series

Modul latihan interaktif mandiri untuk membedah:
1. User Space vs Kernel Space (Syscalls & Context Switches)
2. Siklus Hidup Proses Linux & Zombie Reaping
3. Linux Virtual Memory, Page Faults, dan OOM Killer Scoring
4. File Descriptor & Virtual File System (/proc exploration)
5. SRE Mini-Incident Simulator: Troubleshooting D-State Process
"""

import os
import sys
import time
import random
from typing import Dict, List, Optional

# ANSI Color codes for rich terminal UI
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
    BG_DARK = "\033[40m"


def print_banner():
    banner = f"""{Color.CYAN}{Color.BOLD}
========================================================================
  [SRE LAB] LINUX INTERNALS & KERNEL ARCHITECTURE INTERACTIVE WORKSHOP
  BAB-02: Arsitektur Sistem Operasi Linux untuk Site Reliability Eng.
========================================================================{Color.RESET}"""
    print(banner)


def clear_screen():
    print("\033[H\033[J", end="")


def read_proc_safe(path: str) -> Optional[str]:
    """Membaca file di /proc jika tersedia (Linux native)."""
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read().strip()
    except Exception:
        pass
    return None


def lab_syscall_simulation():
    """Simulasi transisi User Mode (Ring 3) ke Kernel Mode (Ring 0) via Syscall."""
    clear_screen()
    print(f"{Color.YELLOW}{Color.BOLD}--- [MODUL 1] SIMULASI SYSTEM CALL & CONTEXT SWITCH ---{Color.RESET}\n")
    print(f"{Color.WHITE}Dalam Linux, aplikasi berjalan di {Color.GREEN}User Space (Ring 3){Color.WHITE}.")
    print(f"Untuk mengakses hardware (disk, network, RAM), CPU harus switch ke {Color.RED}Kernel Space (Ring 0){Color.WHITE}")
    print(f"melalui instruksi traps / software interrupt (syscall).{Color.RESET}\n")

    operations = [
        {"call": "sys_openat()", "desc": "Membuka file konfigurasi service", "ring": "Ring 0", "cycles": 1200},
        {"call": "sys_read()", "desc": "Membaca 4096 byte buffer dari disk/pagecache", "ring": "Ring 0", "cycles": 3400},
        {"call": "sys_mmap()", "desc": "Memetakan virtual memory address space", "ring": "Ring 0", "cycles": 4800},
        {"call": "sys_write()", "desc": "Mengirimkan response socket network", "ring": "Ring 0", "cycles": 2900},
        {"call": "sys_close()", "desc": "Menutup file descriptor release socket", "ring": "Ring 0", "cycles": 900},
    ]

    print(f"{Color.BOLD}Memulai eksekusi tracing mikro-transisi CPU:{Color.RESET}")
    total_cycles = 0
    for idx, op in enumerate(operations, 1):
        print(f"\n{Color.CYAN}[Langkah {idx}]{Color.RESET} {Color.BOLD}{op['desc']}{Color.RESET}")
        print(f"  {Color.GREEN}[User Space] -> Trigger Trap: {op['call']}{Color.RESET}")
        time.sleep(0.3)
        print(f"  {Color.RED}[CPU Trap Handler] -> Switch ke {op['ring']} | Save Register Context{Color.RESET}")
        time.sleep(0.3)
        print(f"  {Color.MAGENTA}[Kernel VFS/Net] -> Eksekusi kernel code ({op['cycles']} CPU cycles){Color.RESET}")
        time.sleep(0.3)
        print(f"  {Color.GREEN}[Return to Ring 3] -> Restore CPU registers & deliver return code{Color.RESET}")
        total_cycles += op["cycles"]

    print(f"\n{Color.GREEN}{Color.BOLD}[ANALISIS SRE]{Color.RESET}")
    print(f"Total CPU Cycles yang dikonsumsi mode switch: {Color.YELLOW}{total_cycles} cycles{Color.RESET}")
    print(f"{Color.WHITE}Insight: Tingginya persentase CPU {Color.RED}%sy (system time){Color.WHITE} di htop/top")
    print(f"menandakan overhead syscall yang masif (misal: unbuffered I/O atau excessive epoll_wait).{Color.RESET}\n")
    input(f"{Color.DIM}Tekan [Enter] untuk kembali ke menu utama...{Color.RESET}")


def lab_process_states():
    """Simulasi & inspeksi status proses Linux (R, S, D, Z)."""
    clear_screen()
    print(f"{Color.YELLOW}{Color.BOLD}--- [MODUL 2] SIKLUS HIDUP PROSES & STATUS TASK LINUX ---{Color.RESET}\n")
    print("State dalam kernel Linux (sched.h):")
    print(f"  {Color.GREEN}TASK_RUNNING (R){Color.RESET}         : Aktif di CPU runqueue atau sedang dieksekusi CPU.")
    print(f"  {Color.CYAN}TASK_INTERRUPTIBLE (S){Color.RESET}   : Tidur menunggu event/I/O (bisa dihentikan signal SIGTERM).")
    print(f"  {Color.RED}TASK_UNINTERRUPTIBLE (D){Color.RESET} : Tidur menunggu disk/NFS I/O hardware (TIDAK BISA di-kill SIGKILL).")
    print(f"  {Color.MAGENTA}EXIT_ZOMBIE (Z){Color.RESET}          : Proses telah selesai namun parent belum memanggil waitpid().\n")

    # Ambil PID saat ini
    current_pid = os.getpid()
    proc_stat = read_proc_safe(f"/proc/{current_pid}/status")
    print(f"{Color.BOLD}Inspeksi Proses Lab Saat Ini (PID: {current_pid}):{Color.RESET}")
    if proc_stat:
        for line in proc_stat.splitlines():
            if any(line.startswith(prefix) for prefix in ["Name:", "State:", "VmSize:", "Threads:"]):
                print(f"  {Color.CYAN}{line}{Color.RESET}")
    else:
        print(f"  {Color.DIM}(/proc filesystem tidak tersedia, menggunakan fallback simulator){Color.RESET}")
        print(f"  Name: lab_exercise.py\n  State: R (running)\n  Threads: 1")

    print(f"\n{Color.YELLOW}{Color.BOLD}[Simulasi Zombie Reaping]{Color.RESET}")
    print("Membentuk proses child dummy yang mati...")
    time.sleep(0.5)
    print(f"  -> Child process [PID: 9941] keluar dengan exit code 0.")
    print(f"  -> State child sekarang: {Color.MAGENTA}Z (EXIT_ZOMBIE){Color.RESET}. Entry tersisa di process table!")
    print(f"  -> Parent process mengeksekusi syscall {Color.GREEN}waitpid(9941){Color.RESET}...")
    time.sleep(0.8)
    print(f"  -> {Color.GREEN}Zombie dibersihkan dari Kernel Task Struct! Process table slot dibebaskan.{Color.RESET}\n")

    print(f"{Color.WHITE}{Color.BOLD}Kuis SRE:{Color.RESET} Mengapa Zombie Process berbahaya jika dibiarkan akumulatif?")
    print(f"Jawaban: Zombie tidak mengonsumsi RAM/CPU, tapi menghabiskan {Color.RED}PID pool (kernel.pid_max){Color.WHITE}.")
    print(f"Ketika PID habis, OS tidak bisa melakukan fork() proses baru sama sekali!{Color.RESET}\n")
    input(f"{Color.DIM}Tekan [Enter] untuk kembali ke menu utama...{Color.RESET}")


def lab_memory_oom():
    """Simulasi Virtual Memory Subsystem, Page Faults, dan OOM Killer."""
    clear_screen()
    print(f"{Color.YELLOW}{Color.BOLD}--- [MODUL 3] VIRTUAL MEMORY, PAGE FAULTS & OOM KILLER ---{Color.RESET}\n")

    print("Membaca ringkasan memory sistem:")
    meminfo = read_proc_safe("/proc/meminfo")
    if meminfo:
        for line in meminfo.splitlines()[:5]:
            print(f"  {Color.CYAN}{line}{Color.RESET}")
    else:
        print(f"  {Color.CYAN}MemTotal:        16384210 kB\n  MemFree:          4210340 kB\n  MemAvailable:     8912300 kB{Color.RESET}")

    print(f"\n{Color.BOLD}1. Konsep Page Fault:{Color.RESET}")
    print(f"  - {Color.GREEN}Minor Page Fault{Color.RESET}: Alokasi memory baru di VMA yang belum terpetakan ke physical frame,")
    print("    atau halaman sudah ada di Page Cache RAM. Cepat (nanoseconds).")
    print(f"  - {Color.RED}Major Page Fault{Color.RESET}: Halaman data harus dibaca langsung dari Storage/Disk ke RAM.")
    print("    Sangat lambat (milliseconds) -> Penyebab utama latency spike pada database!\n")

    print(f"{Color.BOLD}2. Algoritma OOM (Out-Of-Memory) Score Calculation:{Color.RESET}")
    print("Ketika RAM dan Swap habis, OOM Killer menghitung oom_score untuk membunuh proses.")
    
    # Mock processes
    processes = [
        {"pid": 102, "name": "systemd", "rss_mb": 18, "oom_score_adj": -1000},
        {"pid": 1420, "name": "sshd", "rss_mb": 24, "oom_score_adj": -1000},
        {"pid": 3310, "name": "postgresql-main", "rss_mb": 4200, "oom_score_adj": -200},
        {"pid": 5891, "name": "java-spring-backend", "rss_mb": 7800, "oom_score_adj": 100},
        {"pid": 8011, "name": "worker-batch-leak", "rss_mb": 9200, "oom_score_adj": 0},
    ]

    print(f"\n{Color.BOLD}{'PID':<8}{'Process Name':<22}{'RSS (MB)':<12}{'oom_score_adj':<15}{'Calculated Score':<15}{Color.RESET}")
    print("-" * 72)
    
    highest_score = -9999
    victim = None

    for p in processes:
        base_score = int((p["rss_mb"] / 16000) * 1000)
        final_score = max(0, min(1000, base_score + p["oom_score_adj"]))
        if p["oom_score_adj"] == -1000:
            final_score = 0
        
        if final_score > highest_score:
            highest_score = final_score
            victim = p

        color_item = Color.RED if final_score > 500 else Color.WHITE
        print(f"{p['pid']:<8}{p['name']:<22}{p['rss_mb']:<12}{p['oom_score_adj']:<15}{color_item}{final_score:<15}{Color.RESET}")

    print(f"\n{Color.RED}{Color.BOLD}[OOM KILLER ACTIVATED]{Color.RESET}")
    if victim:
        print(f"Target yang dikorbankan kernel: {Color.RED}{victim['name']} (PID {victim['pid']}){Color.RESET} dengan score {highest_score}.")
        print(f"Action: Mengirim {Color.BOLD}SIGKILL (Signal 9){Color.RESET} seketika untuk membebaskan {victim['rss_mb']} MB RAM.\n")

    input(f"{Color.DIM}Tekan [Enter] untuk kembali ke menu utama...{Color.RESET}")


def lab_file_descriptors():
    """Inspeksi File Descriptors & Linux VFS Architecture."""
    clear_screen()
    print(f"{Color.YELLOW}{Color.BOLD}--- [MODUL 4] VIRTUAL FILE SYSTEM & FILE DESCRIPTORS (/proc/self/fd) ---{Color.RESET}\n")
    print(f"{Color.WHITE}Di Linux, 'Everything is a File'. Koneksi TCP socket, file disk, pipe,")
    print(f"dan device driver diakses melalui integer table yang disebut {Color.CYAN}File Descriptor (FD){Color.RESET}.\n")

    fd_dir = f"/proc/self/fd"
    if os.path.exists(fd_dir):
        print(f"{Color.GREEN}File Descriptor aktif pada proses Python saat ini ({fd_dir}):{Color.RESET}")
        try:
            for fd_name in os.listdir(fd_dir):
                fd_path = os.path.join(fd_dir, fd_name)
                try:
                    target = os.readlink(fd_path)
                    print(f"  FD {Color.BOLD}{fd_name}{Color.RESET} -> {Color.CYAN}{target}{Color.RESET}")
                except OSError:
                    print(f"  FD {fd_name} -> (inaccessible)")
        except Exception as e:
            print(f"  Error membaca FD: {e}")
    else:
        print("Tabel File Descriptor standar Linux:")
        print(f"  FD {Color.BOLD}0{Color.RESET} -> {Color.CYAN}/dev/stdin  (Standard Input){Color.RESET}")
        print(f"  FD {Color.BOLD}1{Color.RESET} -> {Color.CYAN}/dev/stdout (Standard Output){Color.RESET}")
        print(f"  FD {Color.BOLD}2{Color.RESET} -> {Color.CYAN}/dev/stderr (Standard Error){Color.RESET}")
        print(f"  FD {Color.BOLD}3{Color.RESET} -> {Color.CYAN}socket:[482910] (TCP Established 10.0.1.4:8080){Color.RESET}")

    print(f"\n{Color.YELLOW}{Color.BOLD}Limitasi Sistem yang Wajib Diwaspadai SRE:{Color.RESET}")
    print("1. Soft/Hard File Limit: Diatur via `ulimit -n` atau `/etc/security/limits.conf` (nofile).")
    print("2. System-wide File Limit: `/proc/sys/fs/file-max`")
    print(f"Gejala Crash SRE: Pesan error {Color.RED}'Too many open files' (EMFILE/ENFILE){Color.RESET} pada load tinggi.\n")
    input(f"{Color.DIM}Tekan [Enter] untuk kembali ke menu utama...{Color.RESET}")


def lab_sre_incident_troubleshooting():
    """Tantangan Interaktif SRE: Diagnosa Load Average Tinggi tapi CPU Rendah."""
    clear_screen()
    print(f"{Color.RED}{Color.BOLD}========================================================================{Color.RESET}")
    print(f"{Color.RED}{Color.BOLD}  [SRE SCENARIO] INSIDEN PROD: LOAD AVERAGE 128.00, CPU IDLE 95%!       {Color.RESET}")
    print(f"{Color.RED}{Color.BOLD}========================================================================{Color.RESET}\n")

    print(f"{Color.WHITE}Monitoring Alert berbunyi pada pukul 03:15 WIB:")
    print(f"  - Host: {Color.BOLD}api-gateway-node-04{Color.RESET}")
    print(f"  - Load Average (1m, 5m, 15m): {Color.RED}128.45, 115.20, 89.10{Color.RESET} (Cores: 8)")
    print(f"  - CPU Utilization: {Color.GREEN}user: 2%, sys: 3%, idle: 95%{Color.RESET}")
    print(f"  - Request Latency: P99 naik dari 15ms ke 12,000ms! Service timeout.{Color.RESET}\n")

    print(f"{Color.YELLOW}Sebagai SRE On-Call, apa langkah diagnosa pertama Anda?{Color.RESET}")
    print("1. Tambah core CPU via Cloud Autoscaler (Vertical scaling)")
    print("2. Cek status proses apakah banyak yang berada di State 'D' (Uninterruptible Sleep/Disk I/O Wait)")
    print("3. Restart service Nginx secara membabi-buta")
    print("4. Naikkan nilai kernel.pid_max")

    pilihan = input(f"\n{Color.BOLD}Pilih opsi (1-4): {Color.RESET}").strip()

    if pilihan == "2":
        print(f"\n{Color.GREEN}{Color.BOLD}[BENAR!] Root Cause Analysis Berhasil:{Color.RESET}")
        print(f"{Color.WHITE}Load Average di Linux menghitung proses dalam status {Color.BOLD}R (Running){Color.RESET}")
        print(f"DAN {Color.RED}{Color.BOLD}D (TASK_UNINTERRUPTIBLE){Color.RESET}!")
        print("Tingginya Load Average dengan CPU idle menandakan ada proses yang macet di kernel")
        print("menunggu hardware I/O (misalnya: NFS share freeze, SAN disk hang, atau NVMe lock).")
        print(f"Perintah mitigasi: {Color.CYAN}ps -eo state,pid,cmd | grep ^D{Color.RESET} lalu periksa kernel dmesg!\n")
    else:
        print(f"\n{Color.RED}{Color.BOLD}[KURANG TEPAT]{Color.RESET}")
        print("Jika CPU Idle 95%, menambah CPU tidak akan membantu karena bottleneck BUKAN di CPU.")
        print(f"Penyebab utamanya adalah proses stuck di state {Color.RED}D (TASK_UNINTERRUPTIBLE){Color.RESET},")
        print("yang umumnya disebabkan oleh I/O subsystem / Network File System yang macet.\n")

    input(f"{Color.DIM}Tekan [Enter] untuk kembali ke menu utama...{Color.RESET}")


def main():
    while True:
        clear_screen()
        print_banner()
        print(f"{Color.WHITE}Pilih modul latihan interaktif yang ingin dijalankan:{Color.RESET}\n")
        print(f"  {Color.GREEN}1.{Color.RESET} Simulasi System Call & Transisi Ring 3 <-> Ring 0")
        print(f"  {Color.GREEN}2.{Color.RESET} Inspeksi Process Lifecycle & Zombie Process Reaping")
        print(f"  {Color.GREEN}3.{Color.RESET} Linux Virtual Memory, Page Faults & OOM Score Calculation")
        print(f"  {Color.GREEN}4.{Color.RESET} File Descriptor Table & Virtual File System (/proc)")
        print(f"  {Color.GREEN}5.{Color.RESET} SRE Mini-Incident: Diagnosa Load Average Tinggi vs CPU Idle")
        print(f"  {Color.RED}6.{Color.RESET} Keluar (Exit)\n")

        pilihan = input(f"{Color.BOLD}Masukkan nomor pilihan (1-6): {Color.RESET}").strip()

        if pilihan == "1":
            lab_syscall_simulation()
        elif pilihan == "2":
            lab_process_states()
        elif pilihan == "3":
            lab_memory_oom()
        elif pilihan == "4":
            lab_file_descriptors()
        elif pilihan == "5":
            lab_sre_incident_troubleshooting()
        elif pilihan == "6" or pilihan.lower() in ["q", "exit"]:
            print(f"\n{Color.GREEN}Selesai. Terus eksplorasi Linux Kernel internals untuk SRE excellence!{Color.RESET}\n")
            sys.exit(0)
        else:
            print(f"{Color.RED}Pilihan tidak valid. Silakan pilih 1-6.{Color.RESET}")
            time.sleep(1)


if __name__ == "__main__":
    main()
