#!/usr/bin/env python3
"""
Lab: Deep Dive - POSIX Job Control, Process Lifecycle, & Asynchronous Concurrency
Category: 01-Core-Foundations / Bab: 07 (shell-bash)

Simulates the internal execution architecture of a POSIX Unix Shell (e.g., Bash):
- Process State Transitions: RUNNING, STOPPED, DONE, TERMINATED
- Process Group IDs (PGID) and TTY ownership arbitration
- Foreground vs. Background execution & Pipeline concurrency
- Job Table management (+ / - current job markers, %job_id notation)
- Signal Trapping & Propagation: SIGINT, SIGTSTP, SIGCONT, SIGCHLD
- Asynchronous Fan-out and 'wait' barrier synchronization
"""

import enum
import os
import random
import sys
import threading
import time
from typing import Dict, List, Optional, Tuple

# ANSI Terminal Formatting
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_DIM = "\033[2m"
CLR_CYAN = "\033[36m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_RED = "\033[31m"
CLR_MAGENTA = "\033[35m"
CLR_BLUE = "\033[34m"


class ProcessState(enum.Enum):
    RUNNING = "Running"
    STOPPED = "Stopped"
    DONE = "Done"
    TERMINATED = "Terminated"


class Signal(enum.Enum):
    SIGINT = 2     # Interrupt from keyboard (Ctrl+C)
    SIGKILL = 9    # Kill signal (Uncatchable)
    SIGTERM = 15   # Termination signal
    SIGTSTP = 20   # Stop typed at terminal (Ctrl+Z)
    SIGCONT = 18   # Continue if stopped
    SIGCHLD = 17   # Child status changed


class ProcessDescriptor:
    """
    Represents an individual process within a shell pipeline or subshell.
    Maintains CPU state, execution progress, and signal disposition.
    """
    def __init__(self, pid: int, pgid: int, command: str, total_ticks: int):
        self.pid = pid
        self.pgid = pgid
        self.command = command
        self.total_ticks = total_ticks
        self.elapsed_ticks = 0
        self.state = ProcessState.RUNNING
        self.exit_code: Optional[int] = None
        self._pause_event = threading.Event()
        self._pause_event.set()  # Set means NOT paused (running)
        self._terminate_event = threading.Event()

    def tick(self) -> bool:
        """Executes one quantum of simulated CPU/IO work."""
        if self._terminate_event.is_set():
            return False

        self._pause_event.wait()  # Block if SIGTSTP was received

        if self.elapsed_ticks < self.total_ticks:
            self.elapsed_ticks += 1
            if self.elapsed_ticks >= self.total_ticks:
                self.state = ProcessState.DONE
                self.exit_code = 0
                return False
            return True
        return False

    def signal(self, sig: Signal):
        """Dispatches POSIX signals to this specific process."""
        if sig == Signal.SIGTSTP:
            self.state = ProcessState.STOPPED
            self._pause_event.clear()
        elif sig == Signal.SIGCONT:
            self.state = ProcessState.RUNNING
            self._pause_event.set()
        elif sig in (Signal.SIGINT, Signal.SIGTERM, Signal.SIGKILL):
            self.state = ProcessState.TERMINATED
            self.exit_code = 128 + sig.value
            self._terminate_event.set()
            self._pause_event.set()  # Unblock thread if paused so it can exit


class Job:
    """
    Represents a Shell Job: a collection of one or more cooperating processes
    sharing a Process Group ID (PGID).
    """
    def __init__(self, job_id: int, pgid: int, command: str, processes: List[ProcessDescriptor]):
        self.job_id = job_id
        self.pgid = pgid
        self.command = command
        self.processes = processes
        self.notified = False
        self.is_foreground = False

    @property
    def state(self) -> ProcessState:
        """Derives composite job state from its underlying processes."""
        if any(p.state == ProcessState.RUNNING for p in self.processes):
            return ProcessState.RUNNING
        if any(p.state == ProcessState.STOPPED for p in self.processes):
            return ProcessState.STOPPED
        if any(p.state == ProcessState.TERMINATED for p in self.processes):
            return ProcessState.TERMINATED
        return ProcessState.DONE

    def signal_group(self, sig: Signal):
        """Simulates kill(-pgid, sig) broadcasting to entire process group."""
        for p in self.processes:
            p.signal(sig)


class ShellJobEngine:
    """
    Simulates the POSIX Shell's Job Control subsystem, process management table,
    and Asynchronous Concurrency runtime.
    """
    def __init__(self):
        self.jobs: Dict[int, Job] = {}
        self.next_job_id = 1
        self.next_pid = 1000
        self.current_job: Optional[int] = None   # Matches the '+' job marker
        self.previous_job: Optional[int] = None  # Matches the '-' job marker
        self._lock = threading.RLock()
        self._scheduler_running = True
        self._scheduler_thread = threading.Thread(target=self._kernel_scheduler, daemon=True)
        self._scheduler_thread.start()

    def _kernel_scheduler(self):
        """Mock Kernel CPU scheduler ticking running processes asynchronously."""
        while self._scheduler_running:
            with self._lock:
                for job in list(self.jobs.values()):
                    if job.state == ProcessState.RUNNING:
                        for proc in job.processes:
                            if proc.state == ProcessState.RUNNING:
                                proc.tick()
            time.sleep(0.08)

    def spawn(self, command: str, total_ticks: int = 20, background: bool = False) -> Job:
        """
        Emulates fork() + execvp() and process group assignment.
        Creates a new process group to segregate signal domains.
        """
        with self._lock:
            job_id = self.next_job_id
            self.next_job_id += 1
            pgid = self.next_pid
            self.next_pid += 1

            proc = ProcessDescriptor(pid=pgid, pgid=pgid, command=command, total_ticks=total_ticks)
            job = Job(job_id=job_id, pgid=pgid, command=command, processes=[proc])
            job.is_foreground = not background

            self.jobs[job_id] = job
            self._update_job_markers(job_id)

            if background:
                print(f"[{job.job_id}] {job.pgid}")
            return job

    def _update_job_markers(self, active_id: int):
        """Maintains the '+' and '-' shell indicators for current/previous jobs."""
        if self.current_job != active_id:
            self.previous_job = self.current_job
            self.current_job = active_id

    def list_jobs(self, show_pids: bool = True):
        """Replicates the POSIX 'jobs -l' command display."""
        with self._lock:
            if not self.jobs:
                print(f"{CLR_DIM}[No active or suspended jobs]{CLR_RESET}")
                return

            print(f"{CLR_BOLD}{'JID':<5} {'PGID/PID':<10} {'Marker':<8} {'State':<14} {'Command'}{CLR_RESET}")
            print(f"{CLR_DIM}{'-'*60}{CLR_RESET}")

            for jid, job in sorted(self.jobs.items()):
                marker = " "
                if jid == self.current_job:
                    marker = "+"
                elif jid == self.previous_job:
                    marker = "-"

                state_color = {
                    ProcessState.RUNNING: CLR_GREEN,
                    ProcessState.STOPPED: CLR_YELLOW,
                    ProcessState.DONE: CLR_CYAN,
                    ProcessState.TERMINATED: CLR_RED
                }.get(job.state, CLR_RESET)

                state_str = f"{state_color}{job.state.value}{CLR_RESET}"
                pid_info = f"{job.pgid:<10}" if show_pids else ""
                print(f"[{jid}]   {pid_info}{marker:<8} {state_str:<23} {CLR_BOLD}{job.command}{CLR_RESET}")

    def bring_to_foreground(self, job_id: int):
        """Simulates 'fg %job_id': grants terminal control, sends SIGCONT, blocks shell."""
        with self._lock:
            job = self.jobs.get(job_id)
            if not job:
                print(f"bash: fg: %{job_id}: no such job")
                return

            print(f"{CLR_CYAN}{job.command}{CLR_RESET}")
            job.is_foreground = True
            job.signal_group(Signal.SIGCONT)
            self._update_job_markers(job.job_id)

        # Foreground wait loop
        while True:
            with self._lock:
                if job.state != ProcessState.RUNNING:
                    break
            time.sleep(0.05)

        with self._lock:
            job.is_foreground = False
            if job.state == ProcessState.DONE:
                print(f"[{job.job_id}]+  Done                    {job.command}")
                del self.jobs[job.job_id]
                self._recalculate_markers()

    def send_to_background(self, job_id: Optional[int] = None):
        """Simulates 'bg %job_id': sends SIGCONT and leaves process in background."""
        with self._lock:
            target_id = job_id or self.current_job
            if not target_id or target_id not in self.jobs:
                print(f"bash: bg: {f'%{job_id}' if job_id else 'current'}: no such job")
                return

            job = self.jobs[target_id]
            job.is_foreground = False
            job.signal_group(Signal.SIGCONT)
            print(f"[{job.job_id}]+ {job.command} &")
            self._update_job_markers(job.job_id)

    def wait_all(self):
        """Simulates bash 'wait' without arguments: blocks until all background jobs exit."""
        print(f"{CLR_YELLOW}[SHELL] Executing 'wait' barrier across all background jobs...{CLR_RESET}")
        while True:
            with self._lock:
                pending = [j for j in self.jobs.values() if j.state in (ProcessState.RUNNING, ProcessState.STOPPED)]
                if not pending:
                    break
            time.sleep(0.05)
        print(f"{CLR_GREEN}[SHELL] All background tasks completed. Terminal synchronized.{CLR_RESET}")

    def send_signal(self, job_id: int, sig: Signal):
        """Sends an arbitrary signal to a job's process group."""
        with self._lock:
            job = self.jobs.get(job_id)
            if job:
                job.signal_group(sig)

    def reap_zombies(self):
        """Simulates the asynchronous SIGCHLD handler reclaiming terminated processes."""
        with self._lock:
            finished = [jid for jid, job in self.jobs.items() if job.state in (ProcessState.DONE, ProcessState.TERMINATED)]
            for jid in finished:
                job = self.jobs[jid]
                status_msg = "Done" if job.state == ProcessState.DONE else f"Terminated: {job.processes[0].exit_code}"
                print(f"{CLR_DIM}[SIGCHLD Handler] Reaped JID [{jid}] ({job.command}): {status_msg}{CLR_RESET}")
                del self.jobs[jid]
            if finished:
                self._recalculate_markers()

    def _recalculate_markers(self):
        """Recalculates the + and - job designations when jobs exit."""
        active = sorted(self.jobs.keys())
        self.current_job = active[-1] if active else None
        self.previous_job = active[-2] if len(active) > 1 else None

    def shutdown(self):
        self._scheduler_running = False
        self._scheduler_thread.join()


def print_banner(step_num: int, title: str):
    print(f"\n{CLR_BLUE}{'='*70}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_MAGENTA}SCENARIO #{step_num:02d}: {title}{CLR_RESET}")
    print(f"{CLR_BLUE}{'='*70}{CLR_RESET}")


def main():
    engine = ShellJobEngine()
    print(f"{CLR_BOLD}{CLR_GREEN}=== POSIX JOB CONTROL & PROCESS LIFECYCLE SIMULATOR ==={CLR_RESET}")
    print(f"Simulating PID namespace root: {os.getpid()} | Subshell Engine Ready\n")

    try:
        # -------------------------------------------------------------
        # Step 1: Background Job Spawning (cmd &)
        # -------------------------------------------------------------
        print_banner(1, "Asynchronous Background Dispatch (cmd &)")
        print(f"$ ./compile_kernel.sh -j8 > /dev/null &")
        j1 = engine.spawn("./compile_kernel.sh -j8", total_ticks=25, background=True)

        print(f"$ find /var/log -type f -name '*.gz' -exec zgrep 'ERR' {{}} + &")
        j2 = engine.spawn("find /var/log -name '*.gz'", total_ticks=15, background=True)

        time.sleep(0.3)
        print("\n$ jobs -l")
        engine.list_jobs()

        # -------------------------------------------------------------
        # Step 2: Foreground Process, Interactive Suspension (Ctrl+Z / SIGTSTP)
        # -------------------------------------------------------------
        print_banner(2, "Interactive Foreground Execution & Suspension (Ctrl+Z)")
        print(f"$ openssl speed rsa4096 (Running in Foreground)")
        j3 = engine.spawn("openssl speed rsa4096", total_ticks=30, background=False)

        # Simulate user letting it run for a brief moment then pressing Ctrl+Z
        time.sleep(0.4)
        print(f"\n{CLR_YELLOW}^Z{CLR_RESET}")
        print(f"[Terminal Driver] Emitted SIGTSTP to PGID {j3.pgid}")
        engine.send_signal(j3.job_id, Signal.SIGTSTP)
        print(f"[{j3.job_id}]+  Stopped                 {j3.command}")

        time.sleep(0.2)
        print("\n$ jobs -l")
        engine.list_jobs()

        # -------------------------------------------------------------
        # Step 3: Resuming Suspended Job into Background (bg %n)
        # -------------------------------------------------------------
        print_banner(3, "Resuming Suspended Process to Background (bg %3)")
        print(f"$ bg %{j3.job_id}")
        engine.send_to_background(j3.job_id)

        time.sleep(0.3)
        print("\n$ jobs -l")
        engine.list_jobs()

        # -------------------------------------------------------------
        # Step 4: Interprocess Signals (SIGINT / Ctrl+C)
        # -------------------------------------------------------------
        print_banner(4, "Signal Routing: Killing a Rogue Job via SIGINT")
        print(f"$ kill -SIGINT %{j2.job_id}")
        engine.send_signal(j2.job_id, Signal.SIGINT)

        time.sleep(0.2)
        print("\n$ jobs -l")
        engine.list_jobs()

        print("\n[Shell Event Loop] Simulating asynchronous SIGCHLD receipt...")
        engine.reap_zombies()

        # -------------------------------------------------------------
        # Step 5: Foreground Reclamation (fg %n)
        # -------------------------------------------------------------
        print_banner(5, "Foreground Takeover & Completion (fg %1)")
        print(f"$ fg %{j1.job_id}")
        # Bring j1 back to foreground; blocks until done
        engine.bring_to_foreground(j1.job_id)

        print("\n$ jobs -l")
        engine.list_jobs()

        # -------------------------------------------------------------
        # Step 6: Subshell Concurrency Fan-out & Synchronization Barrier (wait)
        # -------------------------------------------------------------
        print_banner(6, "Subshell Fan-Out Pattern & Synchronization Barrier (wait)")
        print("Script execution: Fan-out 4 worker subshells concurrently and await barrier:")
        print(f"{CLR_CYAN}for i in {{1..4}}; do (worker_task $i) & done; wait{CLR_RESET}\n")

        subshell_tasks = [
            f"(subshell_worker_{idx}.sh) &" for idx in range(1, 5)
        ]
        for cmd in subshell_tasks:
            duration = random.randint(8, 14)
            engine.spawn(cmd, total_ticks=duration, background=True)

        time.sleep(0.2)
        print("\n$ jobs -l")
        engine.list_jobs()

        print("\nIssuing blocking wait barrier...")
        engine.wait_all()

        print("\nPost-barrier state inspection:")
        engine.reap_zombies()
        engine.list_jobs()

        print(f"\n{CLR_BOLD}{CLR_GREEN}[SUCCESS] Lab completed. POSIX Job Control lifecycle fully verified.{CLR_RESET}")

    finally:
        engine.shutdown()


if __name__ == "__main__":
    main()
