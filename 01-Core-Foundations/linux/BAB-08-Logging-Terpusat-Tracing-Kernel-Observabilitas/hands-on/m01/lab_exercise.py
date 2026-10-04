#!/usr/bin/env python3
"""
Lab Exercise: Fondasi Inti Linux - Logging Terpusat, Tracing Kernel & Observabilitas
Bab 08: Modul 01 Hands-on Lab
Platform: Linux Kernel & System Observability Simulation
"""

import sys
import time
import random
from datetime import datetime

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
BG_BLUE = "\033[44m"
BG_DARK = "\033[40m"

FACILITIES = ["kern", "user", "daemon", "auth", "syslog"]
SEVERITIES = ["EMERG", "ALERT", "CRIT", "ERR", "WARNING", "NOTICE", "INFO", "DEBUG"]
SEV_COLORS = {
    "EMERG": RED + BOLD,
    "ALERT": RED,
    "CRIT": RED,
    "ERR": RED,
    "WARNING": YELLOW,
    "NOTICE": CYAN,
    "INFO": GREEN,
    "DEBUG": DIM + WHITE,
}

SYSCALLS = [
    ("sys_enter_openat", "vfs_open", "fs/open.c"),
    ("sys_enter_execve", "do_execveat_common", "fs/exec.c"),
    ("sys_enter_clone", "kernel_clone", "kernel/fork.c"),
    ("sys_enter_connect", "__sys_connect", "net/socket.c"),
    ("sys_enter_write", "ksys_write", "fs/read_write.c"),
]


def print_banner():
    print(f"{BLUE}{BOLD}" + "=" * 78 + f"{RESET}")
    print(f"{CYAN}{BOLD}  LINUX KERNEL OBSERVABILITY & DISTRIBUTED LOGGING SIMULATOR{RESET}")
    print(f"{DIM}  Bab 08 - Modul 01: dmesg, journald, rsyslog, ftrace & eBPF Probing{RESET}")
    print(f"{BLUE}{BOLD}" + "=" * 78 + f"{RESET}\n")


def simulate_kernel_ring_buffer():
    print(f"\n{YELLOW}{BOLD}[+] Simulasi Kernel Ring Buffer (/dev/kmsg & dmesg){RESET}")
    print(f"{DIM}Karakteristik: Circular buffer in-kernel, O(1) overwrite, non-blocking lockless ring.{RESET}\n")
    
    events = [
        ("0.000000", "Linux version 6.8.0-generic (buildd@linux) #42-SMP"),
        ("0.000102", "Command line: BOOT_IMAGE=/vmlinuz root=UUID=fa32 ro quiet splash"),
        ("0.004210", "x86/fpu: Supporting XSAVE feature 0x001: 'x87 floating point registers'"),
        ("1.205419", "systemd[1]: Detected architecture x86-64."),
        ("2.314050", "e1000e 0000:00:1f.6 eth0: Link is Up 1000Mbps Full Duplex"),
        ("3.541290", "audit: type=1400 audit(1728086400.123:4): apparmor=\"STATUS\" operation=\"profile_load\""),
        ("5.120934", "bpf_trace: eBPF program [kprobe_tcp_v4_connect] attached successfully (prog_id=142)"),
    ]
    
    for ts, msg in events:
        color = GREEN if "eBPF" in msg or "Link is Up" in msg else CYAN
        if "audit" in msg:
            color = MAGENTA
        print(f"{WHITE}[{float(ts):10.6f}]{RESET} {color}{msg}{RESET}")
        time.sleep(0.12)
    print(f"\n{GREEN}✔ Ring buffer snapshot loaded successfully.{RESET}")


def simulate_journald_and_rsyslog():
    print(f"\n{YELLOW}{BOLD}[+] Simulasi Pipeline Logging: journald -> rsyslog forwarder{RESET}")
    print(f"{DIM}Format: RFC 5424 structured syslog stream dengan fasilitas & severity.{RESET}\n")
    
    daemons = ["sshd", "systemd-networkd", "nginx", "auditd", "dockerd"]
    
    for i in range(8):
        facility = random.choice(FACILITIES)
        severity = random.choice(SEVERITIES[2:])
        daemon = random.choice(daemons)
        pid = random.randint(1000, 32768)
        now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        
        if severity in ["ERR", "CRIT"]:
            detail = f"Failed to authenticate connection from 192.168.1.{random.randint(10, 250)}: Max attempts exceeded"
        elif severity == "WARNING":
            detail = "High memory usage watermark breached in cgroup /system.slice"
        else:
            detail = f"Worker process {pid} successfully handled HTTP request 200 OK"
            
        sev_color = SEV_COLORS.get(severity, WHITE)
        print(f"{DIM}{now}{RESET} {BOLD}{daemon}[{pid}]{RESET}: <{facility}.{sev_color}{severity}{RESET}> {detail}")
        time.sleep(0.15)
        
    print(f"\n{GREEN}✔ Structured logs ingested & indexed to /var/log/journal.{RESET}")


def simulate_kernel_tracing():
    print(f"\n{YELLOW}{BOLD}[+] Simulasi Kernel Tracing (ftrace / kprobe / eBPF Tracing){RESET}")
    print(f"{DIM}Mekanisme: Tracefs ring_buffer (/sys/kernel/tracing/trace_pipe){RESET}\n")
    print(f"{WHITE}{BOLD}{'TASK-PID':<16} {'CPU#':<6} {'TIMESTAMP':<14} {'FUNCTION':<25} {'DURATION (us)'}{RESET}")
    print("-" * 75)
    
    tasks = [("kworker/0:1", 42), ("curl", 10842), ("node", 9921), ("python3", 11204)]
    base_time = 14205.100000
    
    for step in range(10):
        task, pid = random.choice(tasks)
        cpu = random.randint(0, 3)
        base_time += random.uniform(0.00010, 0.00250)
        sc, symbol, src = random.choice(SYSCALLS)
        latency = round(random.uniform(0.8, 45.2), 2)
        
        lat_color = RED if latency > 30 else (YELLOW if latency > 10 else GREEN)
        
        task_str = f"{task}-{pid}"
        print(f"{CYAN}{task_str:<16}{RESET} [{cpu:03d}] {WHITE}{base_time:12.6f}{RESET}: {MAGENTA}{sc:<25}{RESET} -> {lat_color}{latency} us{RESET} ({src})")
        time.sleep(0.12)
        
    print(f"\n{GREEN}✔ ftrace buffer drained without dropped frames.{RESET}")


def interactive_quiz():
    print(f"\n{MAGENTA}{BOLD}[?] Mini Challenge: Observabilitas & Tracing Linux{RESET}")
    questions = [
        {
            "q": "Di mana log biner systemd-journald disimpan secara persisten di disk?",
            "options": [
                "A. /sys/kernel/debug/tracing",
                "B. /var/log/journal/<machine-id>/",
                "C. /proc/sys/kernel/dmesg",
                "D. /etc/systemd/journald.conf",
            ],
            "ans": "B",
            "expl": "/var/log/journal/<machine-id>/ menyimpan file .journal biner yang tahan rotasi dan crash.",
        },
        {
            "q": "Framework tracing in-kernel modern yang aman dieksekusi di kernel space dengan bytecode JIT adalah?",
            "options": ["A. eBPF (Extended BPF)", "B. syslogd", "C. crontab", "D. udev"],
            "ans": "A",
            "expl": "eBPF diverifikasi oleh in-kernel verifier dan di-JIT untuk keamanan dan performa mendekati native.",
        },
    ]
    
    for idx, item in enumerate(questions, 1):
        print(f"\n{BOLD}{idx}. {item['q']}{RESET}")
        for opt in item["options"]:
            print(f"   {opt}")
        print(f"{YELLOW}Kunci Jawaban:{RESET} {BOLD}{item['ans']}{RESET} -> {item['expl']}")


def main():
    print_banner()
    while True:
        print(f"{WHITE}{BOLD}PILIHAN LAB OBSERVABILITAS:{RESET}")
        print(f"  {CYAN}1.{RESET} Simulasi Kernel Ring Buffer (dmesg & kmsg)")
        print(f"  {CYAN}2.{RESET} Simulasi Syslog & Journald Ingestion Pipeline")
        print(f"  {CYAN}3.{RESET} Simulasi Tracing Kernel (ftrace & kprobe)")
        print(f"  {CYAN}4.{RESET} Jalankan Seluruh Demonstrasi (Pipeline Lengkap)")
        print(f"  {CYAN}5.{RESET} Kuis Mandiri Cepat")
        print(f"  {RED}0.{RESET} Keluar")
        
        try:
            choice = input(f"\n{BOLD}Pilih opsi [0-5]: {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            break
            
        if choice == "1":
            simulate_kernel_ring_buffer()
        elif choice == "2":
            simulate_journald_and_rsyslog()
        elif choice == "3":
            simulate_kernel_tracing()
        elif choice == "4":
            simulate_kernel_ring_buffer()
            simulate_journald_and_rsyslog()
            simulate_kernel_tracing()
            interactive_quiz()
        elif choice == "5":
            interactive_quiz()
        elif choice == "0":
            print(f"{GREEN}Lab selesai. Selamat belajar observabilitas Linux!{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak valid, masukkan angka 0 sampai 5.{RESET}")
            
        print("\n" + "-" * 78 + "\n")


if __name__ == "__main__":
    main()
