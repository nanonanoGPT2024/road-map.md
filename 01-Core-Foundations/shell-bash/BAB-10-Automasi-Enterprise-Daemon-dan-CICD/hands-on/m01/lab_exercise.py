#!/usr/bin/env python3
"""
Lab Exercise M01: Simulasi Automasi Enterprise, Daemon Management, dan CI/CD Pipeline
Kurikulum: Shell & Bash Enterprise Foundations (BAB-10)

Deskripsi:
Program interaktif ini mensimulasikan fondasi arsitektur enterprise:
1. Daemon Process Lifecycle (PID Locking, Graceful Shutdown, Signal Handling)
2. Lockfile Mutex & Stale PID Auto-recovery
3. Enterprise CI/CD Pipeline Simulator (Lint, Test, Artifact Build, Deploy, Rollback)
4. Watchdog & Self-Healing Health Check Loop
"""

import sys
import os
import time
import signal
import tempfile
import random

# ANSI Color Codes untuk visualisasi terminal
class Colors:
    HEADER    = '\033[95m'
    BLUE      = '\033[94m'
    CYAN      = '\033[96m'
    GREEN     = '\033[92m'
    YELLOW    = '\033[93m'
    RED       = '\033[91m'
    BOLD      = '\033[1m'
    UNDERLINE = '\033[4m'
    RESET     = '\033[0m'

def log_info(msg):
    print(f"{Colors.BLUE}[INFO]{Colors.RESET} {msg}")

def log_success(msg):
    print(f"{Colors.GREEN}[SUCCESS]{Colors.RESET} {msg}")

def log_warn(msg):
    print(f"{Colors.YELLOW}[WARN]{Colors.RESET} {msg}")

def log_error(msg):
    print(f"{Colors.RED}[ERROR]{Colors.RESET} {msg}")

def log_step(step_name, detail=""):
    print(f"\n{Colors.BOLD}{Colors.CYAN}==> [{step_name}]{Colors.RESET} {detail}")

class EnterpriseLockManager:
    """Simulasi manajemen PID lockfile enterprise dengan safe mutex & stale lock detection."""
    def __init__(self, service_name="enterprise-worker"):
        self.lock_dir = tempfile.gettempdir()
        self.lock_file = os.path.join(self.lock_dir, f"{service_name}.pid")

    def acquire_lock(self):
        log_step("MUTEX_LOCK", f"Mencoba acquire lock file: {self.lock_file}")
        if os.path.exists(self.lock_file):
            with open(self.lock_file, "r") as f:
                content = f.read().strip()
            try:
                existing_pid = int(content)
                log_warn(f"Lockfile ditemukan dengan PID: {existing_pid}")
                # Cek apakah proses aktif di OS
                try:
                    os.kill(existing_pid, 0)
                    log_error(f"Service sudah berjalan aktif di PID {existing_pid}. Abort.")
                    return False
                except OSError:
                    log_warn(f"Stale lockfile terdeteksi! PID {existing_pid} tidak aktif di sistem.")
                    log_info("Membersihkan stale lockfile secara otomatis...")
                    os.remove(self.lock_file)
            except ValueError:
                log_warn("Format lockfile korup. Menimpa lockfile lama...")
                os.remove(self.lock_file)

        my_pid = os.getpid()
        with open(self.lock_file, "w") as f:
            f.write(str(my_pid))
        log_success(f"Lock berhasil diakuisisi oleh PID {my_pid} -> {self.lock_file}")
        return True

    def release_lock(self):
        if os.path.exists(self.lock_file):
            try:
                os.remove(self.lock_file)
                log_info(f"Lockfile dilepas dan dihapus: {self.lock_file}")
            except Exception as e:
                log_error(f"Gagal menghapus lockfile: {e}")

class EnterpriseDaemonSimulator:
    """Simulasi worker daemon berstandar systemd dengan signal trap & watchdog."""
    def __init__(self):
        self.running = True
        self.lock_mgr = EnterpriseLockManager("daemon-agent")

    def _signal_handler(self, signum, frame):
        sig_name = "SIGTERM" if signum == signal.SIGTERM else "SIGINT"
        print(f"\n{Colors.YELLOW}[SIGNAL INTERCEPTED]{Colors.RESET} Menerima {sig_name} ({signum})")
        log_info("Memulai graceful shutdown sequence...")
        log_info("1. Menghentikan penerimaan batch task baru...")
        time.sleep(0.5)
        log_info("2. Menyelesaikan flush buffer & koneksi database...")
        time.sleep(0.5)
        self.lock_mgr.release_lock()
        self.running = False
        log_success("Daemon berhenti dengan aman (Clean exit code 0).")

    def run(self, cycles=5):
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        if not self.lock_mgr.acquire_lock():
            return False

        log_step("DAEMON_ACTIVE", "Daemon memasuki main loop worker (Tekan Ctrl+C untuk test graceful shutdown)...")
        iteration = 0
        try:
            while self.running and iteration < cycles:
                iteration += 1
                health_status = "HEALTHY" if random.random() > 0.15 else "DEGRADED"
                load_metric = round(random.uniform(0.12, 1.85), 2)
                color = Colors.GREEN if health_status == "HEALTHY" else Colors.YELLOW
                print(f"  [{time.strftime('%H:%M:%S')}] Pulse #{iteration:02d} | Status: {color}{health_status}{Colors.RESET} | SysLoad: {load_metric} | ActiveQueue: {random.randint(0, 8)}")
                time.sleep(1)
        finally:
            if self.running:
                self.lock_mgr.release_lock()
        return True

class EnterpriseCICDPipeline:
    """Simulasi orchestrator CI/CD Enterprise: Lint, Test, Artifact Build, Blue-Green Deploy, Rollback."""
    def __init__(self, commit_hash="a1c49f8", branch="main"):
        self.commit = commit_hash
        self.branch = branch

    def stage_lint(self):
        log_step("STAGE 1: SHELLCHECK & LINTING", "Memeriksa kepatuhan kode dan POSIX compatibility...")
        time.sleep(0.6)
        log_info("Running: shellcheck --severity=style scripts/*.sh")
        log_success("0 syntax errors, 0 warnings. Formatting compliant.")
        return True

    def stage_unit_test(self, force_fail=False):
        log_step("STAGE 2: AUTOMATED TESTING", "Menjalankan bats-core unit & integration test suite...")
        tests = [
            ("test_pid_isolation_boundary", 0.05),
            ("test_signal_sigterm_graceful_exit", 0.12),
            ("test_log_rotation_permission_mask", 0.08),
            ("test_idempotent_directory_scaffolding", 0.04)
        ]
        for name, duration in tests:
            time.sleep(0.3)
            print(f"  ✓ {name:<45} [{duration:.2f}s] {Colors.GREEN}PASSED{Colors.RESET}")

        if force_fail:
            time.sleep(0.3)
            print(f"  ✗ {'test_canary_smoke_database_handshake':<45} [0.42s] {Colors.RED}FAILED{Colors.RESET}")
            log_error("AssertionError: Target endpoint unreachable (503 Service Unavailable)")
            return False

        log_success("Semua 4 test suites passed tanpa kegagalan (100% test coverage).")
        return True

    def stage_build(self):
        log_step("STAGE 3: ARTIFACT PACKAGING", "Mengemas release artifact immutable...")
        time.sleep(0.5)
        tar_name = f"release-{self.commit}.tar.gz"
        sha256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        log_info(f"Generated package: {tar_name}")
        log_info(f"SHA-256 Checksum: {sha256}")
        log_success("Artifact siap dipublikasikan ke production repository.")
        return True

    def stage_deploy(self, trigger_failure=False):
        log_step("STAGE 4: BLUE-GREEN DEPLOYMENT", "Menjalankan zero-downtime cutover...")
        time.sleep(0.4)
        log_info("Deploying artifact ke Target Cluster: GREEN environment...")
        time.sleep(0.5)
        log_info("Running pre-flight canary smoke test...")
        if trigger_failure:
            log_error("Canary test gagal: Memory footprint melonjak 95%!")
            log_step("STAGE 5: AUTOMATED ROLLBACK", "Memicu self-healing rollback...")
            time.sleep(0.6)
            log_warn("Mengarahkan NGINX reverse-proxy kembali ke Cluster: BLUE...")
            log_success("Rollback berhasil! Cluster BLUE tetap stabil melayani trafik.")
            return False

        log_info("Switching virtual IP / NGINX upstream ke Cluster: GREEN...")
        time.sleep(0.4)
        log_success(f"Deployment sukses untuk branch '{self.branch}' pada commit [{self.commit}].")
        return True

def print_banner():
    banner = f"""{Colors.CYAN}{Colors.BOLD}
========================================================================
   ENTERPRISE AUTOMATION, DAEMON & CI/CD SIMULATOR (BAB 10)
   Hands-on Interactive Lab - Core Foundations Shell/Bash
========================================================================{Colors.RESET}"""
    print(banner)

def main_menu():
    print_banner()
    while True:
        print(f"\n{Colors.BOLD}PILIHAN LAB EXERCISE INTERAKTIF:{Colors.RESET}")
        print("  1. Uji Akuisisi & Stale PID Lockfile (Mutex Safety)")
        print("  2. Jalankan Daemon Worker Simulation (Graceful SIGTERM Trap)")
        print("  3. Eksekusi CI/CD Pipeline Lengkap (Happy Path / Sukses)")
        print("  4. Uji CI/CD Pipeline Kegagalan & Auto-Rollback Recovery")
        print("  5. Jalankan Semua Simulasi Otomatis (Comprehensive Audit)")
        print("  6. Keluar dari Lab")

        choice = input(f"\n{Colors.BOLD}Masukkan pilihan Anda [1-6]: {Colors.RESET}").strip()

        if choice == "1":
            log_step("LAB 1", "Tes Mekanisme Locking File & Auto Recovery")
            mgr = EnterpriseLockManager("test-lock")
            mgr.acquire_lock()
            # Uji coba lock kedua
            mgr2 = EnterpriseLockManager("test-lock")
            mgr2.acquire_lock()
            mgr.release_lock()
            log_success("Uji Lockfile Selesai.")

        elif choice == "2":
            log_step("LAB 2", "Menjalankan Daemon Interaktif")
            daemon = EnterpriseDaemonSimulator()
            daemon.run(cycles=4)

        elif choice == "3":
            log_step("LAB 3", "Simulasi Happy Path CI/CD Enterprise")
            pipeline = EnterpriseCICDPipeline()
            if pipeline.stage_lint():
                if pipeline.stage_unit_test():
                    if pipeline.stage_build():
                        pipeline.stage_deploy(trigger_failure=False)

        elif choice == "4":
            log_step("LAB 4", "Simulasi Failure & Auto-Rollback Pipeline")
            pipeline = EnterpriseCICDPipeline(commit_hash="bad981c")
            pipeline.stage_lint()
            pipeline.stage_unit_test(force_fail=False)
            pipeline.stage_build()
            pipeline.stage_deploy(trigger_failure=True)

        elif choice == "5":
            log_step("LAB 5", "Automated Full Run Audit Suite")
            print(f"{Colors.HEADER}--- SESI 1: MUTEX LOCK CHECK ---{Colors.RESET}")
            mgr = EnterpriseLockManager("audit-worker")
            mgr.acquire_lock()
            mgr.release_lock()

            print(f"\n{Colors.HEADER}--- SESI 2: DAEMON HEARTBEAT PULSE ---{Colors.RESET}")
            daemon = EnterpriseDaemonSimulator()
            daemon.run(cycles=3)

            print(f"\n{Colors.HEADER}--- SESI 3: ENTERPRISE CI/CD TEST ---{Colors.RESET}")
            pipeline = EnterpriseCICDPipeline(commit_hash="f09a12c")
            pipeline.stage_lint()
            pipeline.stage_unit_test()
            pipeline.stage_build()
            pipeline.stage_deploy(trigger_failure=False)
            log_success("\nSeluruh skenario fondasi enterprise berhasil diverifikasi.")

        elif choice == "6" or choice.lower() in ("q", "quit", "exit"):
            print(f"\n{Colors.GREEN}Terima kasih telah menyelesaikan Lab Exercise BAB 10!{Colors.RESET}\n")
            break
        else:
            log_error("Pilihan tidak valid. Silakan pilih nomor 1 sampai 6.")

if __name__ == "__main__":
    main_menu()
