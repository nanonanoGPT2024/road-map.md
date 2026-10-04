#!/usr/bin/env python3
"""
Lab Hands-on: Sistem Operasi Linux & Otomasi Shell Scripting
Modul 02: Deep Dive - Kernel Process Management, File Descriptors, & Pipeline Engine

Deskripsi:
Script ini memodelkan subsistem kernel Linux inti secara independen:
1. Process Control Block (PCB) & Lifecycle Management (Fork, Exec, Wait, Terminate).
2. Inter-Process Communication (IPC) via POSIX Pipe Buffers (FIFO with EOF propagation).
3. Unix Shell Pipeline Engine (e.g., cat /var/log/syslog | grep ERROR | cut | wc -l).
4. Signal Dispatching (SIGTERM, SIGKILL) dan Zombie Process Reaping.
"""

import sys
import time
import queue
import threading
from enum import Enum
from typing import List, Dict, Optional, Any

# ANSI Color Codes untuk visualisasi terminal
CLR_RESET  = "\033[0m"
CLR_BOLD   = "\033[1m"
CLR_RED    = "\033[91m"
CLR_GREEN  = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE   = "\033[94m"
CLR_CYAN   = "\033[96m"
CLR_GRAY   = "\033[90m"

class ProcessState(Enum):
    READY = "READY"
    RUNNING = "RUNNING"
    SLEEPING = "SLEEPING"
    ZOMBIE = "ZOMBIE"
    TERMINATED = "TERMINATED"

class Signal(Enum):
    SIGTERM = 15
    SIGKILL = 9

class ProcessControlBlock:
    """
    Representasi Process Control Block (PCB) di kernel Linux.
    Menyimpan metadata proses, tabel file descriptor, dan state eksekusi.
    """
    def __init__(self, pid: int, ppid: int, name: str):
        self.pid: int = pid
        self.ppid: int = ppid
        self.name: str = name
        self.state: ProcessState = ProcessState.READY
        self.exit_code: Optional[int] = None
        # File Descriptor Table standar: 0=stdin, 1=stdout, 2=stderr
        self.fd_table: Dict[int, Any] = {0: None, 1: None, 2: None}
        self.thread: Optional[threading.Thread] = None

    def __repr__(self) -> str:
        return f"PCB(PID={self.pid}, PPID={self.ppid}, Name='{self.name}', State={self.state.value})"

class UnixKernelSimulator:
    """
    Simulasi Micro-Kernel Linux untuk manajemen PID, sinyal, dan tabel proses.
    """
    def __init__(self):
        self._next_pid = 1000
        self.process_table: Dict[int, ProcessControlBlock] = {}
        self._lock = threading.Lock()

    def fork_exec(self, ppid: int, name: str, target_func, args=()) -> ProcessControlBlock:
        """
        Mengemulasi fork() dan execve(): Membuat PCB baru dan mengeksekusi fungsi di thread worker.
        """
        with self._lock:
            pid = self._next_pid
            self._next_pid += 1
            pcb = ProcessControlBlock(pid=pid, ppid=ppid, name=name)
            self.process_table[pid] = pcb

        def runner():
            pcb.state = ProcessState.RUNNING
            try:
                exit_code = target_func(pcb, *args)
                pcb.exit_code = 0 if exit_code is None else exit_code
            except Exception as ex:
                pcb.exit_code = 1
                if pcb.fd_table.get(2):
                    pcb.fd_table[2].put(f"STDERR [{pcb.name}]: {str(ex)}")
            finally:
                # Transisi ke ZOMBIE hingga parent melakukan wait/reap
                pcb.state = ProcessState.ZOMBIE
                # Tutup write descriptors untuk mengirim EOF ke pipeline hilir
                if isinstance(pcb.fd_table.get(1), queue.Queue):
                    pcb.fd_table[1].put(None)

        pcb.thread = threading.Thread(target=runner, name=f"PID-{pid}-{name}", daemon=True)
        pcb.thread.start()
        return pcb

    def send_signal(self, pid: int, sig: Signal) -> bool:
        """
        Mengirim sinyal asinkron ke proses berdasarkan PID.
        """
        with self._lock:
            pcb = self.process_table.get(pid)
            if not pcb or pcb.state in (ProcessState.TERMINATED, ProcessState.ZOMBIE):
                return False

            if sig == Signal.SIGKILL or sig == Signal.SIGTERM:
                pcb.state = ProcessState.TERMINATED
                pcb.exit_code = 128 + sig.value
                return True
        return False

    def waitpid(self, pid: int) -> int:
        """
        Mengemulasi syscall waitpid(): Memanen exit code dari Zombie process.
        """
        pcb = self.process_table.get(pid)
        if not pcb:
            return -1

        if pcb.thread and pcb.thread.is_alive():
            pcb.thread.join()

        with self._lock:
            exit_code = pcb.exit_code if pcb.exit_code is not None else 0
            pcb.state = ProcessState.TERMINATED
            return exit_code

    def print_process_table(self):
        """Menampilkan output visual snapshot Process Table (/proc format snapshot)."""
        print(f"\n{CLR_BOLD}{CLR_CYAN}=== KERNEL PROCESS TABLE [/proc snapshot] ==={CLR_RESET}")
        print(f"{'PID':<8}{'PPID':<8}{'STATE':<12}{'EXIT':<8}{'COMMAND'}")
        print(f"{CLR_GRAY}{'-'*50}{CLR_RESET}")
        with self._lock:
            for pid, pcb in self.process_table.items():
                state_clr = CLR_GREEN if pcb.state == ProcessState.RUNNING else \
                            CLR_YELLOW if pcb.state == ProcessState.ZOMBIE else \
                            CLR_RED if pcb.state == ProcessState.TERMINATED else CLR_RESET
                exit_str = str(pcb.exit_code) if pcb.exit_code is not None else "-"
                print(f"{pid:<8}{pcb.ppid:<8}{state_clr}{pcb.state.value:<12}{CLR_RESET}{exit_str:<8}{pcb.name}")
        print(f"{CLR_GRAY}{'-'*50}{CLR_RESET}\n")

# ==============================================================================
# Built-in Unix Utilities Emulation (Pure Stream Operators via Pipe)
# ==============================================================================

def util_cat(pcb: ProcessControlBlock, lines: List[str]):
    """Mengalirkan input data mentah ke stdout (FD 1)."""
    out_pipe: queue.Queue = pcb.fd_table[1]
    for line in lines:
        out_pipe.put(line)
        time.sleep(0.01)  # Simulasi latency I/O kernel

def util_grep(pcb: ProcessControlBlock, pattern: str):
    """Menyaring baris dari stdin (FD 0) berdasarkan substring pattern."""
    in_pipe: queue.Queue = pcb.fd_table[0]
    out_pipe: queue.Queue = pcb.fd_table[1]
    while True:
        line = in_pipe.get()
        if line is None:  # EOF detected
            break
        if pattern in line:
            out_pipe.put(line)

def util_cut(pcb: ProcessControlBlock, delimiter: str, field_idx: int):
    """Memotong kolom teks dari stream stdin (FD 0) berbasis delimiter."""
    in_pipe: queue.Queue = pcb.fd_table[0]
    out_pipe: queue.Queue = pcb.fd_table[1]
    while True:
        line = in_pipe.get()
        if line is None:  # EOF
            break
        parts = line.split(delimiter)
        if len(parts) > field_idx:
            out_pipe.put(parts[field_idx])

def util_wc_l(pcb: ProcessControlBlock):
    """Menghitung total baris stream hingga EOF diterima."""
    in_pipe: queue.Queue = pcb.fd_table[0]
    out_pipe: queue.Queue = pcb.fd_table[1]
    count = 0
    while True:
        line = in_pipe.get()
        if line is None:
            break
        count += 1
    out_pipe.put(str(count))

# ==============================================================================
# Main Shell Automation & Pipeline Execution Engine
# ==============================================================================

def execute_pipeline_demo(kernel: UnixKernelSimulator):
    print(f"{CLR_BOLD}{CLR_BLUE}[+] Menjalankan Simulasi Pipeline Shell Unix:{CLR_RESET}")
    print(f"    Command: {CLR_YELLOW}syslog_stream | grep 'ERROR' | cut -d ':' -f 2 | wc -l{CLR_RESET}\n")

    # Raw Log Dataset (Simulasi /var/log/syslog)
    raw_logs = [
        "10:45:01:INFO:User session established [UID=1000]",
        "10:45:02:ERROR:Database connection timeout [Code=ETIMEDOUT]",
        "10:45:03:DEBUG:Buffer allocated in slab pool",
        "10:45:04:ERROR:Filesystem full on /dev/sda1 [Code=ENOSPC]",
        "10:45:05:WARN:High memory consumption detected: 89%",
        "10:45:06:ERROR:SSL handshake failed [Code=EPROTO]",
        "10:45:07:INFO:Worker thread spawned successfully",
    ]

    # Alokasi POSIX Pipes (FIFO dengan bounded capacity 16 elemen)
    pipe_cat_grep = queue.Queue(maxsize=16)
    pipe_grep_cut = queue.Queue(maxsize=16)
    pipe_cut_wc   = queue.Queue(maxsize=16)
    stdout_sink   = queue.Queue(maxsize=16)

    shell_pid = 100

    # 1. Fork & Wire Process: cat
    p_cat = kernel.fork_exec(shell_pid, "cat /var/log/syslog", util_cat, args=(raw_logs,))
    p_cat.fd_table[1] = pipe_cat_grep

    # 2. Fork & Wire Process: grep ERROR
    p_grep = kernel.fork_exec(shell_pid, "grep ERROR", util_grep, args=("ERROR",))
    p_grep.fd_table[0] = pipe_cat_grep
    p_grep.fd_table[1] = pipe_grep_cut

    # 3. Fork & Wire Process: cut -d ':' -f 2
    p_cut = kernel.fork_exec(shell_pid, "cut -d ':' -f 2", util_cut, args=(":", 2))
    p_cut.fd_table[0] = pipe_grep_cut
    p_cut.fd_table[1] = pipe_cut_wc

    # 4. Fork & Wire Process: wc -l
    p_wc = kernel.fork_exec(shell_pid, "wc -l", util_wc_l)
    p_wc.fd_table[0] = pipe_cut_wc
    p_wc.fd_table[1] = stdout_sink

    # Capture output pipeline dari end-sink
    result = stdout_sink.get()

    # Kernel reaping: Wait for all child processes (Reap zombies)
    for p in [p_cat, p_grep, p_cut, p_wc]:
        kernel.waitpid(p.pid)

    print(f"{CLR_GREEN}✔ Pipeline Selesai Dieksekusi!{CLR_RESET}")
    print(f"  {CLR_BOLD}Total Log Berstatus ERROR:{CLR_RESET} {CLR_RED}{result}{CLR_RESET}\n")

def execute_signal_demo(kernel: UnixKernelSimulator):
    print(f"{CLR_BOLD}{CLR_BLUE}[+] Menjalankan Simulasi Signals & Zombie Process Reaping:{CLR_RESET}")

    def long_running_worker(pcb: ProcessControlBlock):
        while pcb.state != ProcessState.TERMINATED:
            time.sleep(0.05)

    # Spawn daemon dummy
    p_daemon = kernel.fork_exec(ppid=1, name="dummy_daemon", target_func=long_running_worker)
    print(f"  -> Spawned Process: PID={p_daemon.pid}, State={p_daemon.state.value}")
    time.sleep(0.1)

    # Send SIGKILL
    print(f"  -> Mengirimkan sinyal SIGKILL (9) ke PID {p_daemon.pid}...")
    kernel.send_signal(p_daemon.pid, Signal.SIGKILL)

    # State inspection sebelum di-reap
    print(f"  -> Status Proses sebelum waitpid: {p_daemon.state.value} (Exit Code: {p_daemon.exit_code})")

    # Parent melakukan waitpid() untuk membersihkan tabel
    exit_code = kernel.waitpid(p_daemon.pid)
    print(f"  -> Parent memanen PID {p_daemon.pid} dengan exit code: {exit_code}")

def main():
    print(f"{CLR_BOLD}{CLR_CYAN}============================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}  LINUX OS INTERNALS & PROCESS AUTOMATION LAB (MODUL 02)     {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}============================================================{CLR_RESET}\n")

    kernel = UnixKernelSimulator()

    # 1. Jalankan Eksekusi Pipeline Shell Berantai
    execute_pipeline_demo(kernel)

    # 2. Jalankan Lifecycle Sinyal & Handling Zombie
    execute_signal_demo(kernel)

    # 3. Tampilkan Tabel Proses Akhir
    kernel.print_process_table()

    print(f"{CLR_GREEN}{CLR_BOLD}[✔] Lab Eksekusi Sistem Operasi & Automasi Sukses Terverifikasi.{CLR_RESET}")

if __name__ == "__main__":
    main()