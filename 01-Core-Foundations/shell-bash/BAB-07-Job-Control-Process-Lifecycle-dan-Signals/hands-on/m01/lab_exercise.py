#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Job Control, Process Lifecycle, dan Signals pada Shell/Bash
BAB-07: Job Control, Process Lifecycle, dan Signals

Skrip simulasi interaktif mandiri untuk memvisualisasikan bagaimana shell mengelola:
1. Process Lifecycle: Created -> Running -> Stopped (Suspended) -> Terminated / Zombie
2. Job Table: Job ID vs PID, State Tracking (+/- current/previous job marker)
3. Signal Handling: SIGINT (Ctrl+C), SIGTSTP (Ctrl+Z), SIGCONT, SIGTERM, SIGKILL
4. Foreground & Background Execution (fg, bg, &)
"""

import sys
import time
import threading
import queue
import enum
from typing import Dict, List, Optional


class AnsiColor:
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


class ProcessState(enum.Enum):
    READY = "READY"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    TERMINATED = "TERMINATED"


class Signal(enum.Enum):
    SIGHUP = 1
    SIGINT = 2     # Ctrl+C
    SIGKILL = 9    # Uncatchable termination
    SIGTERM = 15   # Cooperative termination
    SIGCONT = 18   # Continue if stopped
    SIGSTOP = 19   # Uncatchable stop
    SIGTSTP = 20   # Ctrl+Z (terminal stop)


class SimulatedProcess:
    _pid_counter = 1000

    def __init__(self, command: str, duration: int = 20):
        SimulatedProcess._pid_counter += 1
        self.pid: int = SimulatedProcess._pid_counter
        self.command: str = command
        self.duration: int = duration
        self.elapsed: int = 0
        self.state: ProcessState = ProcessState.READY
        self.exit_code: Optional[int] = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # Not paused initially
        self.thread: Optional[threading.Thread] = None

    def start(self):
        self.state = ProcessState.RUNNING
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        while self.elapsed < self.duration and not self._stop_event.is_set():
            self._pause_event.wait()
            if self._stop_event.is_set():
                break
            time.sleep(0.5)
            self.elapsed += 1

        if not self._stop_event.is_set():
            self.state = ProcessState.TERMINATED
            self.exit_code = 0

    def send_signal(self, sig: Signal) -> str:
        if self.state == ProcessState.TERMINATED:
            return f"Process {self.pid} sudah berstatus TERMINATED."

        if sig in (Signal.SIGINT, Signal.SIGTERM, Signal.SIGKILL):
            self.state = ProcessState.TERMINATED
            self.exit_code = 128 + sig.value
            self._stop_event.set()
            self._pause_event.set()  # Unblock if waiting
            return f"Process {self.pid} menerima {sig.name} -> TERMINATED (Exit: {self.exit_code})"

        elif sig in (Signal.SIGTSTP, Signal.SIGSTOP):
            if self.state == ProcessState.RUNNING:
                self.state = ProcessState.STOPPED
                self._pause_event.clear()
                return f"Process {self.pid} menerima {sig.name} -> STOPPED (Suspended)"
            return f"Process {self.pid} bukan dalam state RUNNING."

        elif sig == Signal.SIGCONT:
            if self.state == ProcessState.STOPPED:
                self.state = ProcessState.RUNNING
                self._pause_event.set()
                return f"Process {self.pid} menerima SIGCONT -> RUNNING (Resumed)"
            return f"Process {self.pid} sudah dalam status {self.state.value}."

        return f"Signal {sig.name} diabaikan."


class Job:
    def __init__(self, job_id: int, process: SimulatedProcess, is_foreground: bool = False):
        self.job_id: int = job_id
        self.process: SimulatedProcess = process
        self.is_foreground: bool = is_foreground

    @property
    def status_str(self) -> str:
        return self.process.state.value


class BashJobManager:
    def __init__(self):
        self.jobs: Dict[int, Job] = {}
        self.job_counter: int = 1
        self.foreground_job_id: Optional[int] = None

    def add_job(self, command: str, duration: int = 25, foreground: bool = False) -> Job:
        proc = SimulatedProcess(command=command, duration=duration)
        job_id = self.job_counter
        self.job_counter += 1
        job = Job(job_id=job_id, process=proc, is_foreground=foreground)
        self.jobs[job_id] = job
        proc.start()

        if foreground:
            self.foreground_job_id = job_id
        return job

    def clean_terminated(self):
        to_del = []
        for jid, job in self.jobs.items():
            if job.process.state == ProcessState.TERMINATED:
                to_del.append(jid)
        for jid in to_del:
            if self.foreground_job_id == jid:
                self.foreground_job_id = None

    def list_jobs(self) -> List[Job]:
        return list(self.jobs.values())

    def get_job(self, job_id: int) -> Optional[Job]:
        return self.jobs.get(job_id)

    def get_job_by_pid(self, pid: int) -> Optional[Job]:
        for job in self.jobs.values():
            if job.process.pid == pid:
                return job
        return None

    def send_signal_to_job(self, job_id: int, sig: Signal) -> str:
        job = self.get_job(job_id)
        if not job:
            return f"{AnsiColor.RED}Error: Job %{job_id} tidak ditemukan.{AnsiColor.RESET}"
        res = job.process.send_signal(sig)
        if sig in (Signal.SIGINT, Signal.SIGTERM, Signal.SIGKILL):
            if self.foreground_job_id == job_id:
                self.foreground_job_id = None
        elif sig == Signal.SIGTSTP:
            if self.foreground_job_id == job_id:
                job.is_foreground = False
                self.foreground_job_id = None
        return f"{AnsiColor.YELLOW}[Signal]{AnsiColor.RESET} {res}"


def print_banner():
    banner = f"""{AnsiColor.CYAN}{AnsiColor.BOLD}
========================================================================
   SIMULATOR JOB CONTROL, PROCESS LIFECYCLE & SIGNALS (BASH / SHELL)
========================================================================{AnsiColor.RESET}
Konsep yang disimulasikan:
 - {AnsiColor.GREEN}Foreground & Background (&){AnsiColor.RESET}: Alokasi kendali terminal stdin/stdout
 - {AnsiColor.YELLOW}Job Table (+/-){AnsiColor.RESET}: Pemetaan ID job bash terhadap PID kernel
 - {AnsiColor.RED}Signals{AnsiColor.RESET}: SIGINT (2), SIGKILL (9), SIGTERM (15), SIGCONT (18), SIGTSTP (20)
 - {AnsiColor.MAGENTA}Builtins{AnsiColor.RESET}: jobs, fg, bg, kill, ps, run
Type '{AnsiColor.BOLD}help{AnsiColor.RESET}' untuk melihat daftar perintah simulasi, atau '{AnsiColor.BOLD}demo{AnsiColor.RESET}' untuk mode otomatis.
"""
    print(banner)


def print_help():
    help_text = f"""
{AnsiColor.BOLD}DAFTAR PERINTAH SIMULATOR:{AnsiColor.RESET}
  {AnsiColor.GREEN}run <cmd> [durasi] [&]{AnsiColor.RESET}   : Jalankan proses baru. Tambahkan '&' untuk background.
                             Contoh: run worker_task 30 &
                             Contoh: run backup_db 15
  {AnsiColor.GREEN}jobs{AnsiColor.RESET}                   : Tampilkan tabel jobs aktif dengan status dan PID.
  {AnsiColor.GREEN}ps{AnsiColor.RESET}                     : Tampilkan process table (PID, State, Duration, Elapsed).
  {AnsiColor.GREEN}fg <%jid>{AnsiColor.RESET}                : Pindahkan job ke foreground dan kirim SIGCONT jika stopped.
  {AnsiColor.GREEN}bg <%jid>{AnsiColor.RESET}                : Lanjutkan job yang berstatus STOPPED di background (&).
  {AnsiColor.GREEN}kill -<SIG> <%jid|PID>{AnsiColor.RESET}   : Kirim sinyal ke process/job (e.g. kill -STOP %1, kill -9 1001).
  {AnsiColor.GREEN}ctrl-c{AnsiColor.RESET}                 : Simulasikan penekanan Ctrl+C (SIGINT) ke foreground job.
  {AnsiColor.GREEN}ctrl-z{AnsiColor.RESET}                 : Simulasikan penekanan Ctrl+Z (SIGTSTP) ke foreground job.
  {AnsiColor.GREEN}demo{AnsiColor.RESET}                   : Jalankan skenario simulasi otomatis bertahap.
  {AnsiColor.GREEN}clear{AnsiColor.RESET}                  : Bersihkan layar terminal simulasi.
  {AnsiColor.GREEN}exit{AnsiColor.RESET}                   : Keluar dari simulator.
"""
    print(help_text)


def display_jobs_table(manager: BashJobManager):
    jobs = manager.list_jobs()
    if not jobs:
        print(f"{AnsiColor.DIM}(Tabel jobs kosong - tidak ada proses aktif){AnsiColor.RESET}")
        return

    print(f"\n{AnsiColor.BOLD}{'JID':<6} {'STATUS':<14} {'PID':<8} {'MODE':<12} {'COMMAND'}{AnsiColor.RESET}")
    print("-" * 65)

    for job in sorted(jobs, key=lambda x: x.job_id):
        state = job.process.state
        if state == ProcessState.RUNNING:
            color = AnsiColor.GREEN
        elif state == ProcessState.STOPPED:
            color = AnsiColor.YELLOW
        elif state == ProcessState.TERMINATED:
            color = AnsiColor.RED
        else:
            color = AnsiColor.WHITE

        mode_str = f"{AnsiColor.CYAN}Foreground{AnsiColor.RESET}" if job.is_foreground else f"{AnsiColor.DIM}Background &{AnsiColor.RESET}"
        status_styled = f"{color}{state.value:<14}{AnsiColor.RESET}"
        print(f"[{job.job_id}]   {status_styled} {job.process.pid:<8} {mode_str:<21} {job.process.command} (t={job.process.elapsed}/{job.process.duration}s)")
    print()


def display_ps_table(manager: BashJobManager):
    print(f"\n{AnsiColor.BOLD}{'PID':<8} {'STATE':<14} {'ELAPSED':<10} {'EXIT_CODE':<10} {'COMMAND'}{AnsiColor.RESET}")
    print("-" * 65)
    for job in sorted(manager.list_jobs(), key=lambda x: x.process.pid):
        p = job.process
        color = AnsiColor.GREEN if p.state == ProcessState.RUNNING else (AnsiColor.YELLOW if p.state == ProcessState.STOPPED else AnsiColor.RED)
        exit_val = str(p.exit_code) if p.exit_code is not None else "-"
        print(f"{p.pid:<8} {color}{p.state.value:<14}{AnsiColor.RESET} {f'{p.elapsed}s':<10} {exit_val:<10} {p.command}")
    print()


def run_automated_demo(manager: BashJobManager):
    print(f"\n{AnsiColor.CYAN}{AnsiColor.BOLD}>>> MEMULAI SKENARIO DEMO OTOMATIS PROSES & SIGNAL <<<{AnsiColor.RESET}\n")
    time.sleep(1)

    print(f"{AnsiColor.WHITE}Step 1: Meluncurkan Job 1 (long_batch_job) di background (&)...{AnsiColor.RESET}")
    job1 = manager.add_job("long_batch_job.sh", duration=30, foreground=False)
    print(f"{AnsiColor.GREEN}[1] {job1.process.pid} (diluncurkan di background){AnsiColor.RESET}")
    display_jobs_table(manager)
    time.sleep(2)

    print(f"{AnsiColor.WHITE}Step 2: Meluncurkan Job 2 (interactive_compile) di foreground...{AnsiColor.RESET}")
    job2 = manager.add_job("interactive_compile.sh", duration=25, foreground=True)
    print(f"{AnsiColor.GREEN}[2] {job2.process.pid} (sedang memegang kendali foreground){AnsiColor.RESET}")
    display_jobs_table(manager)
    time.sleep(2)

    print(f"{AnsiColor.YELLOW}Step 3: Mengirim Ctrl+Z (SIGTSTP) ke foreground job [2]...{AnsiColor.RESET}")
    res = manager.send_signal_to_job(job2.job_id, Signal.SIGTSTP)
    print(res)
    display_jobs_table(manager)
    time.sleep(2)

    print(f"{AnsiColor.WHITE}Step 4: Melanjutkan Job [2] di background menggunakan perintah 'bg %2'...{AnsiColor.RESET}")
    manager.send_signal_to_job(job2.job_id, Signal.SIGCONT)
    job2.is_foreground = False
    print(f"{AnsiColor.GREEN}[2]+ interactive_compile.sh &  (Status kembali RUNNING){AnsiColor.RESET}")
    display_jobs_table(manager)
    time.sleep(2)

    print(f"{AnsiColor.RED}Step 5: Mengirim SIGTERM (kill -15) ke Job 1 ({job1.process.pid})...{AnsiColor.RESET}")
    res = manager.send_signal_to_job(job1.job_id, Signal.SIGTERM)
    print(res)
    display_jobs_table(manager)
    time.sleep(2)

    print(f"{AnsiColor.MAGENTA}Step 6: Membawa Job [2] kembali ke foreground dengan 'fg %2'...{AnsiColor.RESET}")
    job2.is_foreground = True
    manager.foreground_job_id = job2.job_id
    print(f"{AnsiColor.MAGENTA}Job [2] kini di foreground. Mengirim SIGINT (Ctrl+C)...{AnsiColor.RESET}")
    res = manager.send_signal_to_job(job2.job_id, Signal.SIGINT)
    print(res)
    display_jobs_table(manager)

    print(f"{AnsiColor.CYAN}{AnsiColor.BOLD}>>> DEMO SELESAI: Semua konsep transisi status berhasil disimulasikan. <<<{AnsiColor.RESET}\n")


def parse_signal(sig_name: str) -> Optional[Signal]:
    clean = sig_name.upper().lstrip("-")
    if clean.startswith("SIG"):
        clean = clean[3:]
    mapping = {
        "HUP": Signal.SIGHUP,
        "1": Signal.SIGHUP,
        "INT": Signal.SIGINT,
        "2": Signal.SIGINT,
        "KILL": Signal.SIGKILL,
        "9": Signal.SIGKILL,
        "TERM": Signal.SIGTERM,
        "15": Signal.SIGTERM,
        "CONT": Signal.SIGCONT,
        "18": Signal.SIGCONT,
        "STOP": Signal.SIGSTOP,
        "19": Signal.SIGSTOP,
        "TSTP": Signal.SIGTSTP,
        "20": Signal.SIGTSTP,
    }
    return mapping.get(clean)


def main():
    manager = BashJobManager()
    print_banner()

    # Jika terminal dijalankan non-interaktif atau dengan argumen --demo
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        run_automated_demo(manager)
        return

    while True:
        try:
            fg_info = f" {AnsiColor.CYAN}[fg:%{manager.foreground_job_id}]{AnsiColor.RESET}" if manager.foreground_job_id else ""
            prompt = f"{AnsiColor.BOLD}bash-simulator{fg_info}> {AnsiColor.RESET}"
            user_input = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{AnsiColor.YELLOW}Sesi simulator ditutup.{AnsiColor.RESET}")
            break

        if not user_input:
            continue

        parts = user_input.split()
        cmd = parts[0].lower()
        args = parts[1:]

        if cmd in ("exit", "quit"):
            print(f"{AnsiColor.GREEN}Terminating simulator. Bye!{AnsiColor.RESET}")
            break

        elif cmd == "help":
            print_help()

        elif cmd == "clear":
            print("\033[2J\033[H", end="")

        elif cmd == "demo":
            run_automated_demo(manager)

        elif cmd == "jobs":
            display_jobs_table(manager)

        elif cmd == "ps":
            display_ps_table(manager)

        elif cmd == "run":
            if not args:
                print(f"{AnsiColor.RED}Usage: run <command_name> [duration_seconds] [&]{AnsiColor.RESET}")
                continue

            is_bg = False
            if args[-1] == "&":
                is_bg = True
                args = args[:-1]

            duration = 20
            command_name = args[0]
            if len(args) > 1 and args[1].isdigit():
                duration = int(args[1])

            if not is_bg and manager.foreground_job_id is not None:
                print(f"{AnsiColor.YELLOW}Peringatan: Foreground sedang ditempati job %{manager.foreground_job_id}. Memaksa job baru ke background.{AnsiColor.RESET}")
                is_bg = True

            job = manager.add_job(command=command_name, duration=duration, foreground=not is_bg)
            if is_bg:
                print(f"[{job.job_id}] {job.process.pid}  (Dimulai di background)")
            else:
                print(f"[{job.job_id}] {job.process.pid}  (Berjalan di foreground. Tekan 'ctrl-c' atau 'ctrl-z' untuk sinyal)")

        elif cmd == "ctrl-c":
            if manager.foreground_job_id:
                res = manager.send_signal_to_job(manager.foreground_job_id, Signal.SIGINT)
                print(res)
            else:
                print(f"{AnsiColor.DIM}(Tidak ada foreground job yang aktif untuk menerima SIGINT){AnsiColor.RESET}")

        elif cmd == "ctrl-z":
            if manager.foreground_job_id:
                res = manager.send_signal_to_job(manager.foreground_job_id, Signal.SIGTSTP)
                print(res)
            else:
                print(f"{AnsiColor.DIM}(Tidak ada foreground job yang aktif untuk menerima SIGTSTP){AnsiColor.RESET}")

        elif cmd == "fg":
            if not args:
                # Default ke job stopped terakhir atau job background apapun
                jobs = [j for j in manager.list_jobs() if j.process.state != ProcessState.TERMINATED]
                if not jobs:
                    print(f"{AnsiColor.RED}bash: fg: current: no such job{AnsiColor.RESET}")
                    continue
                target_job = jobs[-1]
            else:
                target_arg = args[0].lstrip("%")
                if not target_arg.isdigit() or int(target_arg) not in manager.jobs:
                    print(f"{AnsiColor.RED}bash: fg: %{args[0]}: no such job{AnsiColor.RESET}")
                    continue
                target_job = manager.jobs[int(target_arg)]

            if target_job.process.state == ProcessState.STOPPED:
                manager.send_signal_to_job(target_job.job_id, Signal.SIGCONT)

            target_job.is_foreground = True
            manager.foreground_job_id = target_job.job_id
            print(f"{AnsiColor.CYAN}{target_job.process.command}{AnsiColor.RESET} dipindahkan ke Foreground.")

        elif cmd == "bg":
            if not args:
                stopped_jobs = [j for j in manager.list_jobs() if j.process.state == ProcessState.STOPPED]
                if not stopped_jobs:
                    print(f"{AnsiColor.RED}bash: bg: current: no such job{AnsiColor.RESET}")
                    continue
                target_job = stopped_jobs[-1]
            else:
                target_arg = args[0].lstrip("%")
                if not target_arg.isdigit() or int(target_arg) not in manager.jobs:
                    print(f"{AnsiColor.RED}bash: bg: %{args[0]}: no such job{AnsiColor.RESET}")
                    continue
                target_job = manager.jobs[int(target_arg)]

            target_job.is_foreground = False
            if manager.foreground_job_id == target_job.job_id:
                manager.foreground_job_id = None
            manager.send_signal_to_job(target_job.job_id, Signal.SIGCONT)
            print(f"[{target_job.job_id}]+ {target_job.process.command} &")

        elif cmd == "kill":
            if not args:
                print(f"{AnsiColor.RED}Usage: kill -<SIGNAL> <%job_id | PID>{AnsiColor.RESET}")
                continue

            sig = Signal.SIGTERM
            target_str = args[0]
            if target_str.startswith("-") and len(args) > 1:
                parsed = parse_signal(target_str)
                if not parsed:
                    print(f"{AnsiColor.RED}Signal '{target_str}' tidak valid.{AnsiColor.RESET}")
                    continue
                sig = parsed
                target_str = args[1]

            if target_str.startswith("%"):
                jid_str = target_str[1:]
                if not jid_str.isdigit():
                    print(f"{AnsiColor.RED}JID tidak valid: {target_str}{AnsiColor.RESET}")
                    continue
                res = manager.send_signal_to_job(int(jid_str), sig)
                print(res)
            elif target_str.isdigit():
                pid = int(target_str)
                job = manager.get_job_by_pid(pid)
                if job:
                    res = manager.send_signal_to_job(job.job_id, sig)
                    print(res)
                else:
                    print(f"{AnsiColor.RED}bash: kill: ({pid}) - No such process{AnsiColor.RESET}")
            else:
                print(f"{AnsiColor.RED}Target identifier tidak valid: {target_str}{AnsiColor.RESET}")

        else:
            print(f"{AnsiColor.RED}bash: {cmd}: command not found. Ketik 'help' untuk panduan.{AnsiColor.RESET}")


if __name__ == "__main__":
    main()
