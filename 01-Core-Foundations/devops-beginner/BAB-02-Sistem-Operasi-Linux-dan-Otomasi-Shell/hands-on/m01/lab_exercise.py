#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Fondasi Sistem Operasi Linux & Otomasi Shell
BAB-02: Sistem Operasi Linux dan Otomasi Shell (DevOps Beginner)

Modul Hands-on interaktif yang mensimulasikan:
1. File System Hierarchy Standard (FHS) & Path Resolution
2. Linux Permissions (rwx, octal notation, chown/chmod logic)
3. Standard Streams & Pipeline Emulation (stdin, stdout, stderr, pipe |)
4. Process Lifecycle & POSIX Signal Handling (PID, fork/exec concept, SIGTERM, SIGKILL)
5. Shell Automation & Job Scheduling (Cron syntax parsing & environment variables)
"""

import sys
import time
import os
import random

# ANSI Color Codes
class Colors:
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
    BG_BLACK = "\033[40m"

def print_header(title: str):
    width = 70
    print("\n" + Colors.CYAN + "=" * width + Colors.RESET)
    print(f"{Colors.BOLD}{Colors.WHITE}{Colors.BG_BLUE}  {title.center(width - 4)}  {Colors.RESET}")
    print(Colors.CYAN + "=" * width + Colors.RESET + "\n")

def print_step(step_num: int, title: str, desc: str):
    print(f"{Colors.BOLD}{Colors.YELLOW}[MODUL {step_num:02d}]{Colors.RESET} {Colors.BOLD}{title}{Colors.RESET}")
    print(f"{Colors.DIM}{desc}{Colors.RESET}")
    print(Colors.DIM + "-" * 60 + Colors.RESET)

def sim_fhs_explorer():
    print_step(1, "Filesystem Hierarchy Standard (FHS) & VFS Tree", 
               "Eksplorasi struktur direktori standar Linux dan kegunaan sistematisnya.")
    
    fhs_map = {
        "/bin": ("Essential user command binaries (ls, bash, cp, ping)", "Mounted on root, critical for single-user mode"),
        "/etc": ("Host-specific system configurations (nginx.conf, passwd, hosts)", "Static configuration files, no binaries"),
        "/var/log": ("Variable data, persistent logs (syslog, auth.log, journal)", "Continuously growing files"),
        "/proc": ("Virtual pseudo-filesystem documenting kernel & process state", "0 bytes on disk, memory-backed"),
        "/dev": ("Device nodes (sda, urandom, null, stdout)", "Hardware interfaces managed by udev"),
        "/sys": ("Kernel sysfs exporting kernel objects, devices, and drivers", "Direct kernel tuning & hardware knobs")
    }

    for path, (purpose, note) in fhs_map.items():
        print(f" {Colors.GREEN}●{Colors.RESET} {Colors.BOLD}{Colors.CYAN}{path:<10}{Colors.RESET} -> {purpose}")
        print(f"   {Colors.DIM}Detail: {note}{Colors.RESET}")
        time.sleep(0.15)
    print()

def sim_permission_calculator():
    print_step(2, "Linux Permissions & Octal Calculation Engine", 
               "Simulasi perhitungan bit permission POSIX (User, Group, Others).")

    samples = [
        ("chmod 755 app.sh", 0o755, "rwxr-xr-x", "Eksekusi web server / script binari publik"),
        ("chmod 600 id_ed25519", 0o600, "rw-------", "Private key SSH (strict security requirement)"),
        ("chmod 644 config.yaml", 0o644, "rw-r--r--", "File konfigurasi read-only untuk non-owner"),
        ("chmod 700 deploy.pem", 0o700, "rwx------", "Direktori ~/.ssh atau file private eksekutabel")
    ]

    for cmd, octal_val, symb, use_case in samples:
        u = (octal_val >> 6) & 0o7
        g = (octal_val >> 3) & 0o7
        o = octal_val & 0o7
        
        print(f"Perintah: {Colors.BOLD}{Colors.YELLOW}{cmd}{Colors.RESET}")
        print(f"  Octal : {Colors.MAGENTA}{oct(octal_val)[2:]}{Colors.RESET} (User: {u}, Group: {g}, Other: {o})")
        print(f"  Simbol: {Colors.GREEN}{symb}{Colors.RESET} [{symb[0:3]}|{symb[3:6]}|{symb[6:9]}]")
        print(f"  Konteks: {Colors.WHITE}{use_case}{Colors.RESET}\n")
        time.sleep(0.15)

def sim_pipe_and_streams():
    print_step(3, "Standard Streams (stdin=0, stdout=1, stderr=2) & Pipelines", 
               "Mensimulasikan redirect stream dan alur pipeline filter: cat | grep | sort | wc -l.")

    dummy_logs = [
        "2026-10-05 02:00:11 [INFO] Worker node-1 registered",
        "2026-10-05 02:00:15 [ERROR] Connection timeout to database 10.0.4.15:5432",
        "2026-10-05 02:00:18 [WARN] Memory utilization exceeded 80%",
        "2026-10-05 02:00:22 [ERROR] Health check failed for ingress-controller",
        "2026-10-05 02:00:25 [INFO] Batch job execution finished successfully",
        "2026-10-05 02:00:30 [ERROR] Connection timeout to database 10.0.4.15:5432"
    ]

    print(f"{Colors.BOLD}Pipeline:{Colors.RESET} {Colors.CYAN}app.log | grep '[ERROR]' | sort -u{Colors.RESET}")
    print(f"{Colors.DIM}Mengalirkan stream data baris per baris melalui buffer inter-process communication...{Colors.RESET}\n")

    error_lines = [line for line in dummy_logs if "[ERROR]" in line]
    unique_errors = sorted(list(set(error_lines)))

    print(f"{Colors.GREEN}[Stream Output stdout (FD 1)]{Colors.RESET}:")
    for err in unique_errors:
        print(f"  {Colors.RED}✖{Colors.RESET} {err}")
    print(f"\n{Colors.BLUE}Jumlah unik incident error:{Colors.RESET} {len(unique_errors)}")
    print(f"{Colors.YELLOW}[Stderr FD 2 Simulator]{Colors.RESET}: 0 bytes written (Exit Code: 0/SUCCESS)\n")

def sim_process_lifecycle():
    print_step(4, "Process Lifecycle, PID & Signal Handling (POSIX)", 
               "Simulasi daemon, status proses (R, S, Z), dan sinyal kontrol (SIGTERM/SIGKILL).")

    processes = [
        {"pid": 1042, "name": "nginx-master", "state": "S (Sleeping/Listening)", "mem": "14.2 MB"},
        {"pid": 1043, "name": "nginx-worker", "state": "R (Running/Active)", "mem": "28.5 MB"},
        {"pid": 1210, "name": "gunicorn-app", "state": "R (Running/Active)", "mem": "112.4 MB"},
        {"pid": 1399, "name": "defunct-zombie", "state": "Z (Zombie/Unreaped)", "mem": "0.0 MB"}
    ]

    print(f"{Colors.BOLD}{'PID':<8}{'PROCESS NAME':<18}{'STATE':<26}{'MEMORY'}{Colors.RESET}")
    print("-" * 65)
    for p in processes:
        state_color = Colors.GREEN if "R" in p["state"] else (Colors.RED if "Z" in p["state"] else Colors.YELLOW)
        print(f"{p['pid']:<8}{p['name']:<18}{state_color}{p['state']:<26}{Colors.RESET}{p['mem']}")
    print()

    target_pid = 1210
    print(f"{Colors.BOLD}Mengirim Sinyal Graceful Shutdown:{Colors.RESET}")
    print(f"  # kill -15 {target_pid}  {Colors.DIM}(SIGTERM: Meminta aplikasi menyelesaikan koneksi & close socket){Colors.RESET}")
    time.sleep(0.2)
    print(f"  -> PID {target_pid} menangkap SIGTERM... Flushing memory buffer... [OK]")
    print(f"  -> Process {target_pid} terminated cleanly with exit status 0.\n")

def sim_cron_automation():
    print_step(5, "Shell Automation & Cron Job Expression Parser", 
               "Simulasi evaluasi waktu eksekusi cron tab format: * * * * * (min hour dom mon dow).")

    cron_rules = [
        ("0 2 * * *", "/opt/scripts/backup-db.sh >> /var/log/backup.log 2>&1", "Setiap hari pukul 02:00 AM UTC"),
        ("*/15 * * * *", "/usr/local/bin/healthcheck.sh", "Setiap interval 15 menit"),
        ("0 0 1 * *", "/usr/bin/certbot renew --quiet", "Tiap awal bulan tanggal 1 pukul 00:00"),
        ("30 23 * * 5", "/usr/bin/clean-cache.sh", "Tiap hari Jumat pukul 23:30 malam")
    ]

    for expr, cmd, meaning in cron_rules:
        print(f"Cron Expression : {Colors.BOLD}{Colors.GREEN}{expr:<15}{Colors.RESET}")
        print(f"Jadwal          : {Colors.WHITE}{meaning}{Colors.RESET}")
        print(f"Perintah Shell  : {Colors.CYAN}{cmd}{Colors.RESET}\n")
        time.sleep(0.1)

def run_interactive_quiz():
    print_step(6, "Self-Assessment Challenge: Linux Sysadmin & Automation", 
               "Uji pemahaman langsung terhadap materi fondasi Linux.")

    questions = [
        {
            "q": "Direktori manakah dalam FHS Linux yang menyimpan konfigurasi host (misal hosts, fstab)?",
            "opts": ["A. /var", "B. /etc", "C. /usr", "D. /opt"],
            "ans": "B",
            "exp": "/etc berisi seluruh konfigurasi statis spesifik untuk sistem host."
        },
        {
            "q": "Berapakah representasi numerik oktal untuk permission file 'rwxr-xr--'?",
            "opts": ["A. 754", "B. 644", "C. 755", "D. 774"],
            "ans": "A",
            "exp": "rwx = 4+2+1=7 (User), r-x = 4+0+1=5 (Group), r-- = 4+0+0=4 (Other) -> 754."
        },
        {
            "q": "Simbol pengalihan manakah yang mengarahkan standard error (stderr) ke file log?",
            "opts": ["A. 1> log.txt", "B. > log.txt", "C. 2> log.txt", "D. < log.txt"],
            "ans": "C",
            "exp": "File descriptor 2 merepresentasikan stderr, sehingga '2>' adalah redirect stderr."
        }
    ]

    score = 0
    print(f"{Colors.BOLD}{Colors.MAGENTA}--- Mode Evaluasi Interaktif Otomatis ---{Colors.RESET}")
    for idx, item in enumerate(questions, 1):
        print(f"\n{Colors.BOLD}Soal {idx}: {item['q']}{Colors.RESET}")
        for opt in item["opts"]:
            print(f"   {opt}")
        
        # In non-interactive or batch mode, simulate correct answer selection
        selected = item["ans"]
        print(f"{Colors.CYAN}Pilihan Siswa [Simulasi Interaktif]: {selected}{Colors.RESET}")
        if selected == item["ans"]:
            print(f"{Colors.GREEN}✔ BENAR!{Colors.RESET} {Colors.DIM}{item['exp']}{Colors.RESET}")
            score += 1
        else:
            print(f"{Colors.RED}✘ SALAH.{Colors.RESET} {item['exp']}")
        time.sleep(0.15)

    print(f"\n{Colors.BOLD}{Colors.BG_BLUE} Skor Akhir Evaluasi: {score}/{len(questions)} ({int(score/len(questions)*100)}%) {Colors.RESET}\n")

def main():
    print_header("SIMULATOR FONDASI LINUX & OTOMASI SHELL (BAB-02)")
    print(f"{Colors.DIM}Memulai sesi simulasi praktikum DevOps Engineer...{Colors.RESET}")
    time.sleep(0.3)

    sim_fhs_explorer()
    sim_permission_calculator()
    sim_pipe_and_streams()
    sim_process_lifecycle()
    sim_cron_automation()
    run_interactive_quiz()

    print(f"{Colors.BOLD}{Colors.GREEN}=== Seluruh Modul Simulasi Hands-on Berhasil Dijalankan ==={Colors.RESET}\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Colors.RED}Simulasi dihentikan oleh pengguna.{Colors.RESET}")
        sys.exit(1)
