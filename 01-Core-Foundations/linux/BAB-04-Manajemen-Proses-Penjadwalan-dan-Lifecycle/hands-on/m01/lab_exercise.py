#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Manajemen Proses, Lifecycle, dan Penjadwalan Linux
Modul: BAB-04-Manajemen-Proses-Penjadwalan-dan-Lifecycle (Modul 01)

Simulasi interaktif konsep fundamental kernel Linux:
1. State Machine Proses (TASK_RUNNING, TASK_INTERRUPTIBLE, TASK_STOPPED, TASK_ZOMBIE, TASK_DEAD)
2. Hierarchy Process, Fork, Exec, Zombie, dan Orphan Re-parenting ke PID 1 (systemd/init)
3. Completely Fair Scheduler (CFS) dengan bobot nice (-20 s/d +19) & virtual runtime (vruntime)
4. Pengiriman Signal Standar POSIX (SIGSTOP, SIGCONT, SIGTERM, SIGKILL)
"""

import sys
import time
import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# ANSI Color Codes
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_DIM = "\033[2m"
CLR_RED = "\033[31m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN = "\033[36m"
CLR_WHITE = "\033[37m"
CLR_BG_RED = "\033[41m"
CLR_BG_BLUE = "\033[44m"
CLR_BG_GREEN = "\033[42m"

# CFS Priority Weights table (Linux kernel sched/core.c sched_prio_to_weight)
SCHED_PRIO_TO_WEIGHT = {
    -20: 88761, -19: 71755, -18: 56483, -17: 46273, -16: 36291,
    -15: 29154, -14: 23254, -13: 18705, -12: 14949, -11: 11916,
    -10: 9548,  -9: 7620,   -8: 6100,   -7: 4904,   -6: 3906,
    -5: 3121,   -4: 2501,   -3: 1991,   -2: 1586,   -1: 1277,
     0: 1024,    1: 820,     2: 655,     3: 526,     4: 423,
     5: 335,     6: 272,     7: 215,     8: 172,     9: 137,
    10: 110,    11: 87,     12: 70,     13: 56,     14: 45,
    15: 36,     16: 29,     17: 23,     18: 18,     19: 15
}
NICE_0_LOAD = 1024


@dataclass
class ProcessPCB:
    pid: int
    ppid: int
    name: str
    state: str = "TASK_RUNNING"  # RUNNING, INTERRUPTIBLE, STOPPED, ZOMBIE, DEAD
    nice: int = 0
    weight: int = 1024
    vruntime_ms: float = 0.0
    cpu_time_ms: float = 0.0
    exit_code: Optional[int] = None
    children: List[int] = field(default_factory=list)

    def update_weight(self):
        self.nice = max(-20, min(19, self.nice))
        self.weight = SCHED_PRIO_TO_WEIGHT.get(self.nice, 1024)


class LinuxKernelSimulator:
    def __init__(self):
        self.processes: Dict[int, ProcessPCB] = {}
        self.next_pid = 1
        self.init_process_tree()

    def init_process_tree(self):
        """Inisialisasi PID 1 (systemd/init) sebagai akar pohon proses."""
        init_proc = ProcessPCB(
            pid=1,
            ppid=0,
            name="systemd",
            state="TASK_RUNNING",
            nice=0,
            vruntime_ms=0.0
        )
        init_proc.update_weight()
        self.processes[1] = init_proc
        self.next_pid = 2

    def alloc_pid(self) -> int:
        pid = self.next_pid
        self.next_pid += 1
        return pid

    def fork(self, parent_pid: int, child_name: str, nice: int = 0) -> Optional[int]:
        if parent_pid not in self.processes:
            print(f"{CLR_RED}[ERR] Parent PID {parent_pid} tidak ditemukan!{CLR_RESET}")
            return None

        parent = self.processes[parent_pid]
        child_pid = self.alloc_pid()

        # Min vruntime dari proses yang sedang aktif untuk fair start
        active_vruntimes = [p.vruntime_ms for p in self.processes.values() if p.state == "TASK_RUNNING"]
        initial_vruntime = min(active_vruntimes) if active_vruntimes else 0.0

        child = ProcessPCB(
            pid=child_pid,
            ppid=parent_pid,
            name=child_name,
            state="TASK_RUNNING",
            nice=nice,
            vruntime_ms=initial_vruntime
        )
        child.update_weight()
        self.processes[child_pid] = child
        parent.children.append(child_pid)
        return child_pid

    def terminate_process(self, pid: int, exit_code: int = 0):
        """Simulasi exit() proses -> beralih ke state ZOMBIE menunggu wait() parent."""
        if pid not in self.processes:
            print(f"{CLR_RED}[ERR] PID {pid} tidak ada.{CLR_RESET}")
            return

        proc = self.processes[pid]
        if proc.pid == 1:
            print(f"{CLR_RED}[ERR] Dilarang mematikan PID 1 (Kernel Panic)!{CLR_RESET}")
            return

        # Handle adopsi anak-anak jika proc yang mati memiliki anak (Reparenting ke PID 1)
        if proc.children:
            init_proc = self.processes[1]
            print(f"{CLR_YELLOW}[REPARENT] Anak-anak dari PID {pid} ({proc.children}) diadopsi oleh PID 1 (systemd){CLR_RESET}")
            for c_pid in proc.children:
                if c_pid in self.processes:
                    self.processes[c_pid].ppid = 1
                    init_proc.children.append(c_pid)
            proc.children.clear()

        proc.state = "TASK_ZOMBIE"
        proc.exit_code = exit_code
        print(f"{CLR_MAGENTA}[EXIT] Process PID {pid} [{proc.name}] exit dengan code {exit_code}. State: TASK_ZOMBIE (Menunggu wait() dari Parent PID {proc.ppid}){CLR_RESET}")

    def reap_zombie(self, parent_pid: int):
        """Simulasi syscall waitpid() oleh parent process untuk membersihkan zombie."""
        if parent_pid not in self.processes:
            print(f"{CLR_RED}[ERR] Parent PID {parent_pid} tidak ditemukan.{CLR_RESET}")
            return

        parent = self.processes[parent_pid]
        reaped = []
        for c_pid in list(parent.children):
            if c_pid in self.processes and self.processes[c_pid].state == "TASK_ZOMBIE":
                zombie = self.processes[c_pid]
                print(f"{CLR_GREEN}[WAITPID] Parent {parent_pid} mereap zombie PID {zombie.pid} [{zombie.name}] (Exit status: {zombie.exit_code}){CLR_RESET}")
                del self.processes[c_pid]
                parent.children.remove(c_pid)
                reaped.append(c_pid)

        if not reaped:
            print(f"{CLR_DIM}[WAITPID] Tidak ada child zombie untuk Parent PID {parent_pid}.{CLR_RESET}")

    def send_signal(self, pid: int, sig_name: str):
        """Simulasi pengiriman sinyal POSIX ke proses."""
        if pid not in self.processes:
            print(f"{CLR_RED}[ERR] Target PID {pid} tidak ada.{CLR_RESET}")
            return

        proc = self.processes[pid]
        sig_name = sig_name.upper()

        if sig_name == "SIGSTOP":
            if proc.state == "TASK_ZOMBIE":
                print(f"{CLR_YELLOW}[SIG] Tidak dapat menghentikan Zombie.{CLR_RESET}")
                return
            proc.state = "TASK_STOPPED"
            print(f"{CLR_YELLOW}[SIGNAL] SIGSTOP terkirim ke PID {pid}. State -> TASK_STOPPED (T/Paused){CLR_RESET}")

        elif sig_name == "SIGCONT":
            if proc.state == "TASK_STOPPED":
                proc.state = "TASK_RUNNING"
                print(f"{CLR_GREEN}[SIGNAL] SIGCONT terkirim ke PID {pid}. State -> TASK_RUNNING (R){CLR_RESET}")
            else:
                print(f"{CLR_DIM}[SIGNAL] PID {pid} tidak sedang di-pause.{CLR_RESET}")

        elif sig_name in ("SIGTERM", "SIGKILL"):
            print(f"{CLR_RED}[SIGNAL] {sig_name} dikirim ke PID {pid}. Proses dipaksa terminasi.{CLR_RESET}")
            self.terminate_process(pid, exit_code=137 if sig_name == "SIGKILL" else 143)

        else:
            print(f"{CLR_RED}[ERR] Sinyal tidak didukung dalam simulasi ringkas ini.{CLR_RESET}")

    def run_cfs_tick(self, timeslice_ms: float = 20.0):
        """
        Simulasi 1 siklus Completely Fair Scheduler (CFS).
        Memilih proses di TASK_RUNNING dengan vruntime terkecil (Red-Black tree leftmost).
        vruntime += delta_exec * (NICE_0_LOAD / weight)
        """
        runnable = [p for p in self.processes.values() if p.state == "TASK_RUNNING"]
        if not runnable:
            print(f"{CLR_DIM}[SCHED] Idle: tidak ada proses berstatus TASK_RUNNING.{CLR_RESET}")
            return

        # Pilih leftmost node (vruntime terendah)
        runnable.sort(key=lambda p: p.vruntime_ms)
        chosen = runnable[0]

        delta_exec = timeslice_ms
        # Rumus formal CFS vruntime update
        vruntime_delta = delta_exec * (NICE_0_LOAD / chosen.weight)
        chosen.vruntime_ms += vruntime_delta
        chosen.cpu_time_ms += delta_exec

        print(f"{CLR_CYAN}[CFS DISPATCH]{CLR_RESET} Executing PID {CLR_BOLD}{chosen.pid}{CLR_RESET} [{chosen.name}] "
              f"| Nice: {chosen.nice:+d} (Weight: {chosen.weight}) "
              f"| Exec: {delta_exec:.1f}ms -> delta_vruntime: {vruntime_delta:.2f}ms "
              f"| Total vruntime: {chosen.vruntime_ms:.2f}ms")

    def print_ps_tree(self):
        """Menampilkan daftar proses menyerupai command ps/top di Linux."""
        print(f"\n{CLR_BOLD}{CLR_WHITE}=== LINUX PROCESS TABLE & STATE VIEWER ==={CLR_RESET}")
        header = f"{'PID':<6} {'PPID':<6} {'STATE':<20} {'NICE':<6} {'WEIGHT':<8} {'VRUNTIME(ms)':<14} {'CPUTIME(ms)':<12} {'CMD'}"
        print(f"{CLR_DIM}{'-'*88}{CLR_RESET}")
        print(f"{CLR_BOLD}{header}{CLR_RESET}")
        print(f"{CLR_DIM}{'-'*88}{CLR_RESET}")

        state_color_map = {
            "TASK_RUNNING": CLR_GREEN,
            "TASK_STOPPED": CLR_YELLOW,
            "TASK_ZOMBIE": CLR_BG_RED + CLR_WHITE,
            "TASK_INTERRUPTIBLE": CLR_BLUE,
            "TASK_DEAD": CLR_RED
        }

        for pid in sorted(self.processes.keys()):
            p = self.processes[pid]
            st_color = state_color_map.get(p.state, CLR_WHITE)
            state_str = f"{st_color}{p.state:<19}{CLR_RESET}"
            nice_str = f"{p.nice:+d}"
            print(f"{p.pid:<6} {p.ppid:<6} {state_str} {nice_str:<6} {p.weight:<8} {p.vruntime_ms:<14.2f} {p.cpu_time_ms:<12.2f} {CLR_BOLD}{p.name}{CLR_RESET}")

        print(f"{CLR_DIM}{'-'*88}{CLR_RESET}\n")


def run_automated_demo(sim: LinuxKernelSimulator):
    """Menjalankan skenario otomatis demonstrasi lifecycle proses & CFS."""
    print(f"\n{CLR_BG_BLUE}{CLR_WHITE}{CLR_BOLD} [DEMO OTOMATIS: LIFECYCLE & CFS SCHEDULER] {CLR_RESET}\n")

    print(f"{CLR_BOLD}1. Membuat Proses Pekerja (Fork & Exec)...{CLR_RESET}")
    pid_nginx = sim.fork(parent_pid=1, child_name="nginx-master", nice=0)
    pid_worker1 = sim.fork(parent_pid=pid_nginx, child_name="nginx-worker-01", nice=-5) # High priority
    pid_worker2 = sim.fork(parent_pid=pid_nginx, child_name="nginx-worker-02", nice=10) # Low priority (Nice 10)
    pid_batch = sim.fork(parent_pid=1, child_name="backup-batch", nice=19)               # Lowest priority
    sim.print_ps_tree()

    print(f"{CLR_BOLD}2. Menjalankan Simulasi CFS Scheduling (5 Siklus)...{CLR_RESET}")
    print(f"{CLR_DIM}Perhatikan bagaimana proses bernilai Nice lebih rendah (-5) mendapat laju kenaikan vruntime lebih lambat (sehingga sering dijadwalkan).{CLR_RESET}")
    for i in range(5):
        sim.run_cfs_tick(timeslice_ms=20.0)
    sim.print_ps_tree()

    print(f"{CLR_BOLD}3. Simulasi Signal Management (SIGSTOP & SIGCONT)...{CLR_RESET}")
    sim.send_signal(pid_worker1, "SIGSTOP")
    sim.print_ps_tree()
    print(f"{CLR_DIM}CFS tick saat salah satu proses di-pause (SIGSTOP):{CLR_RESET}")
    sim.run_cfs_tick(timeslice_ms=20.0)
    sim.send_signal(pid_worker1, "SIGCONT")
    sim.print_ps_tree()

    print(f"{CLR_BOLD}4. Simulasi Zombie Process & Re-parenting Orphan...{CLR_RESET}")
    # Matikan worker 2 saat parent belum memanggil wait()
    sim.terminate_process(pid_worker2, exit_code=0)
    sim.print_ps_tree()

    # Matikan nginx-master mendadak, membuat child tersisa menjadi Orphan
    print(f"{CLR_BOLD}5. Parent (nginx-master) dimatikan mendadak -> Orphan reparenting ke PID 1:{CLR_RESET}")
    sim.terminate_process(pid_nginx, exit_code=1)
    sim.print_ps_tree()

    print(f"{CLR_BOLD}6. Parent PID 1 mereap Zombie proses yang tersisa:{CLR_RESET}")
    sim.reap_zombie(1)
    sim.print_ps_tree()
    print(f"{CLR_GREEN}{CLR_BOLD}Demo Selesai dengan sukses!{CLR_RESET}\n")


def interactive_cli():
    sim = LinuxKernelSimulator()

    # Cek apakah dijalankan non-interaktif
    if not sys.stdin.isatty() or "--demo" in sys.argv:
        run_automated_demo(sim)
        return

    banner = f"""
{CLR_CYAN}{CLR_BOLD}======================================================================
  LINUX PROCESS & SCHEDULER (CFS) INTERACTIVE LAB SIMULATOR
  Modul BAB-04: Process Management, Scheduling, and Lifecycle
======================================================================{CLR_RESET}
Perintah Tersedia:
  {CLR_GREEN}ps{CLR_RESET}                                 : Tampilkan daftar proses & tabel status
  {CLR_GREEN}fork <ppid> <name> [nice]{CLR_RESET}          : Buat proses baru (fork child)
  {CLR_GREEN}tick [n]{CLR_RESET}                             : Jalankan n tick penjadwalan CFS (default: 1)
  {CLR_GREEN}kill <pid> <SIGNAME>{CLR_RESET}                 : Kirim signal (SIGSTOP, SIGCONT, SIGTERM, SIGKILL)
  {CLR_GREEN}exit <pid> [code]{CLR_RESET}                    : Simulasi proses terminate (menjadi Zombie)
  {CLR_GREEN}wait <ppid>{CLR_RESET}                          : Parent mengeksekusi waitpid() membersihkan zombie
  {CLR_GREEN}demo{CLR_RESET}                                 : Jalankan demonstrasi otomatis lengkap
  {CLR_GREEN}help / q{CLR_RESET}                             : Panduan / Keluar
"""
    print(banner)
    sim.print_ps_tree()

    while True:
        try:
            line = input(f"{CLR_BOLD}linux-kernel-lab>{CLR_RESET} ").strip()
            if not line:
                continue

            parts = line.split()
            cmd = parts[0].lower()

            if cmd in ("q", "quit", "exit_sim"):
                print(f"{CLR_YELLOW}Menutup sesi lab Linux. Sampai jumpa!{CLR_RESET}")
                break

            elif cmd == "ps":
                sim.print_ps_tree()

            elif cmd == "demo":
                run_automated_demo(sim)

            elif cmd == "fork":
                if len(parts) < 3:
                    print(f"{CLR_RED}Penggunaan: fork <ppid> <name> [nice]{CLR_RESET}")
                    continue
                ppid = int(parts[1])
                name = parts[2]
                nice = int(parts[3]) if len(parts) > 3 else 0
                new_pid = sim.fork(ppid, name, nice)
                if new_pid:
                    print(f"{CLR_GREEN}[FORK SUCCESS] Created PID {new_pid} with nice {nice}{CLR_RESET}")

            elif cmd == "tick":
                count = int(parts[1]) if len(parts) > 1 else 1
                for _ in range(count):
                    sim.run_cfs_tick()

            elif cmd == "kill":
                if len(parts) < 3:
                    print(f"{CLR_RED}Penggunaan: kill <pid> <SIGNAME>{CLR_RESET}")
                    continue
                pid = int(parts[1])
                sig = parts[2]
                sim.send_signal(pid, sig)

            elif cmd == "exit":
                if len(parts) < 2:
                    print(f"{CLR_RED}Penggunaan: exit <pid> [code]{CLR_RESET}")
                    continue
                pid = int(parts[1])
                code = int(parts[2]) if len(parts) > 2 else 0
                sim.terminate_process(pid, code)

            elif cmd == "wait":
                if len(parts) < 2:
                    print(f"{CLR_RED}Penggunaan: wait <ppid>{CLR_RESET}")
                    continue
                ppid = int(parts[1])
                sim.reap_zombie(ppid)

            elif cmd == "help":
                print(banner)

            else:
                print(f"{CLR_RED}Perintah '{cmd}' tidak dikenali. Ketik 'help' untuk daftar opsi.{CLR_RESET}")

        except (EOFError, KeyboardInterrupt):
            print(f"\n{CLR_YELLOW}Keluar dari lab.{CLR_RESET}")
            break
        except Exception as e:
            print(f"{CLR_RED}[EXCEPTION] Error: {e}{CLR_RESET}")


if __name__ == "__main__":
    interactive_cli()
