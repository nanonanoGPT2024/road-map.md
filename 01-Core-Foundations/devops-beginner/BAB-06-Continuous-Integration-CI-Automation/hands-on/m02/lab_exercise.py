#!/usr/bin/env python3
"""
Lab Hands-on: Bab 06 - Continuous Integration (CI) Praktis (Modul 02 Deep Dive)
Topik: In-Memory Multi-Stage CI Pipeline Engine dengan Dependency Resolution,
       Concurrent Job Execution, dan Incremental Artifact Caching.

Deskripsi:
Program ini mengimplementasikan engine runner CI skala kecil yang mensimulasikan
alur kerja GitHub Actions / GitLab CI:
1. Validasi DAG (Directed Acyclic Graph) dependensi antar job.
2. Eksekusi paralel antar job yang independen menggunakan Thread Pool.
3. Simulasi langkah nyata: Static Code Analysis, Unit Testing, SAST Scanner, dan Packaging.
4. Hash-based Cache Mechanism untuk mempercepat build (Incremental Build Simulation).
"""

import sys
import time
import hashlib
import threading
from enum import Enum
from typing import List, Dict, Set, Callable, Optional
from dataclasses import dataclass, field
from queue import Queue

# --- ANSI Formatting Configuration ---
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    GRAY = "\033[90m"

class JobStatus(Enum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    CACHED = "CACHED"

@dataclass
class JobResult:
    status: JobStatus
    duration: float
    output: str
    artifact_hash: Optional[str] = None

@dataclass
class CIJob:
    name: str
    action: Callable[[], JobResult]
    needs: List[str] = field(default_factory=list)
    status: JobStatus = JobStatus.PENDING
    result: Optional[JobResult] = None
    started_at: float = 0.0
    finished_at: float = 0.0

# --- Global Artifact & Cache Storage ---
BUILD_CACHE: Dict[str, str] = {
    # Pre-calculated cache hash simulasi commit sebelumnya
    "static-analysis": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
}
log_lock = threading.Lock()

def safe_log(prefix: str, msg: str, color: str = Color.RESET):
    """Mencegah data race pada stdout saat thread concurrent melakukan print."""
    with log_lock:
        timestamp = time.strftime("%H:%M:%S")
        print(f"{Color.GRAY}[{timestamp}]{Color.RESET} {color}[{prefix}]{Color.RESET} {msg}")

# --- Simulasi Pipeline Steps ---

def run_linting() -> JobResult:
    """Simulasi linting (Flake8 / ESLint) dengan validasi checksum source code."""
    time.sleep(0.3)
    mock_source = "def main(): return 42"
    source_hash = hashlib.sha256(mock_source.encode()).hexdigest()
    
    # Deteksi cache hit
    if BUILD_CACHE.get("static-analysis") == source_hash:
        return JobResult(
            status=JobStatus.CACHED,
            duration=0.05,
            output="Cache hit: Source files unchanged. Linting skipped.",
            artifact_hash=source_hash
        )
    return JobResult(
        status=JobStatus.PASSED,
        duration=0.3,
        output="Lint passed. Code styling clean with zero violations.",
        artifact_hash=source_hash
    )

def run_unit_tests() -> JobResult:
    """Simulasi eksekusi unit test suite."""
    time.sleep(0.6)
    tests_run = 48
    failures = 0
    return JobResult(
        status=JobStatus.PASSED,
        duration=0.6,
        output=f"Executed {tests_run} test cases. Failures: {failures}. Coverage: 92.4%."
    )

def run_security_sast() -> JobResult:
    """Simulasi scan kerentanan dependensi (SAST / CVE Audit)."""
    time.sleep(0.5)
    dependencies_scanned = 112
    cves_found = 0
    return JobResult(
        status=JobStatus.PASSED,
        duration=0.5,
        output=f"Scanned {dependencies_scanned} packages. High/Crit vulnerabilities: {cves_found}."
    )

def run_docker_build() -> JobResult:
    """Simulasi packaging image OCI / Docker dan perhitungan SHA digest."""
    time.sleep(0.8)
    image_layers = ["layer-1-base-os", "layer-2-python-runtime", "layer-3-app-code"]
    combined_layers = "".join(image_layers)
    image_digest = hashlib.sha256(combined_layers.encode()).hexdigest()[:16]
    return JobResult(
        status=JobStatus.PASSED,
        duration=0.8,
        output=f"Image built successfully: app/microservice:sha-{image_digest}",
        artifact_hash=image_digest
    )

# --- CI Execution Engine ---

class CIPipelineEngine:
    def __init__(self, workers: int = 2):
        self.jobs: Dict[str, CIJob] = {}
        self.workers = workers
        self.queue: Queue[str] = Queue()
        self.completed_jobs: Set[str] = set()
        self.pipeline_failed = False
        self.lock = threading.Lock()

    def add_job(self, name: str, action: Callable[[], JobResult], needs: List[str] = None):
        """Mendaftarkan task ke dalam DAG pipeline."""
        needs = needs or []
        self.jobs[name] = CIJob(name=name, action=action, needs=needs)

    def validate_dag(self):
        """Memvalidasi tidak ada circular dependency atau undefined task."""
        for name, job in self.jobs.items():
            for dep in job.needs:
                if dep not in self.jobs:
                    raise ValueError(f"Dependency '{dep}' dari job '{name}' tidak terdaftar!")
        
        # Deteksi siklus sederhana menggunakan DFS
        visited = set()
        rec_stack = set()

        def dfs(node: str):
            visited.add(node)
            rec_stack.add(node)
            for neighbor in self.jobs[node].needs:
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            rec_stack.remove(node)
            return False

        for job_name in self.jobs:
            if job_name not in visited:
                if dfs(job_name):
                    raise RuntimeError("Terdeteksi Cyclic Dependency pada pipeline DAG!")

    def _worker(self):
        """Worker thread untuk mengambil task dari antrian dan mengeksekusinya."""
        while True:
            job_name = self.queue.get()
            if job_name is None:
                self.queue.task_done()
                break

            job = self.jobs[job_name]
            
            # Cek apakah ada dependencies yang gagal
            with self.lock:
                failed_deps = [dep for dep in job.needs if self.jobs[dep].status == JobStatus.FAILED]
                if failed_deps or self.pipeline_failed:
                    job.status = JobStatus.SKIPPED
                    safe_log(job_name, f"Skipped due to upstream failure: {failed_deps}", Color.YELLOW)
                    self.completed_jobs.add(job_name)
                    self.queue.task_done()
                    self._check_and_enqueue_dependents()
                    continue
                job.status = JobStatus.RUNNING

            safe_log(job_name, "Memulai eksekusi task...", Color.BLUE)
            start_time = time.time()
            
            try:
                res = job.action()
            except Exception as e:
                res = JobResult(status=JobStatus.FAILED, duration=time.time() - start_time, output=str(e))

            job.finished_at = time.time()
            job.result = res
            job.status = res.status

            color = Color.GREEN if res.status in (JobStatus.PASSED, JobStatus.CACHED) else Color.RED
            status_text = res.status.value
            safe_log(job_name, f"Selesai [{status_text}] ({res.duration:.2f}s) -> {res.output}", color)

            with self.lock:
                if res.status == JobStatus.FAILED:
                    self.pipeline_failed = True
                self.completed_jobs.add(job_name)

            self.queue.task_done()
            self._check_and_enqueue_dependents()

    def _check_and_enqueue_dependents(self):
        """Mengecek job mana yang dependensinya sudah terpenuhi untuk dimasukkan antrian."""
        with self.lock:
            for name, job in self.jobs.items():
                if job.status == JobStatus.PENDING:
                    # Periksa apakah seluruh upstream job sudah selesai
                    if all(dep in self.completed_jobs for dep in job.needs):
                        job.status = JobStatus.QUEUED
                        self.queue.put(name)

    def run(self):
        """Menjalankan seluruh alur orkestrasi pipeline CI."""
        self.validate_dag()
        safe_log("ENGINE", f"Memulai Pipeline Runner dengan {self.workers} concurrency worker.", Color.MAGENTA)
        
        start_pipeline = time.time()
        threads = []
        for _ in range(self.workers):
            t = threading.Thread(target=self._worker)
            t.daemon = True
            t.start()
            threads.append(t)

        # Trigger job level pertama (yang tidak memiliki dependensi)
        self._check_and_enqueue_dependents()

        # Tunggu hingga semua job masuk dan selesai diproses di antrian
        self.queue.join()

        # Berhenti workers
        for _ in range(self.workers):
            self.queue.put(None)
        for t in threads:
            t.join()

        total_duration = time.time() - start_pipeline
        self._print_summary(total_duration)

    def _print_summary(self, total_duration: float):
        """Menampilkan laporan eksekusi Pipeline CI secara visual."""
        print("\n" + "=" * 65)
        print(f"{Color.BOLD}CI PIPELINE EXECUTION SUMMARY{Color.RESET}")
        print("=" * 65)
        print(f"{'JOB NAME':<20} | {'STATUS':<10} | {'DURATION':<10} | {'ARTIFACT'}")
        print("-" * 65)

        all_passed = True
        for name, job in self.jobs.items():
            res = job.result
            dur_str = f"{res.duration:.2f}s" if res else "0.00s"
            art_str = (res.artifact_hash[:8] + "...") if (res and res.artifact_hash) else "-"
            
            if job.status in (JobStatus.PASSED, JobStatus.CACHED):
                status_colored = f"{Color.GREEN}{job.status.value:<10}{Color.RESET}"
            elif job.status == JobStatus.SKIPPED:
                status_colored = f"{Color.YELLOW}{job.status.value:<10}{Color.RESET}"
                all_passed = False
            else:
                status_colored = f"{Color.RED}{job.status.value:<10}{Color.RESET}"
                all_passed = False

            print(f"{name:<20} | {status_colored} | {dur_str:<10} | {art_str}")

        print("-" * 65)
        outcome = f"{Color.GREEN}SUCCESS (BUILD STABLE){Color.RESET}" if all_passed else f"{Color.RED}FAILURE (BUILD BROKEN){Color.RESET}"
        print(f"Final Outcome : {outcome}")
        print(f"Total Wall Time: {total_duration:.2f}s")
        print("=" * 65)

def main():
    print(f"{Color.CYAN}{Color.BOLD}=== CI Engine Orchestrator Simulation ==={Color.RESET}\n")

    # Inisialisasi engine dengan pool worker concurrent
    engine = CIPipelineEngine(workers=2)

    # Membangun skenario Dependency Graph:
    # [Lint] ---------\
    #                  +---> [Build Package]
    # [Unit Test] ----+
    # [SAST Scan] ----/
    
    engine.add_job("static-analysis", run_linting, needs=[])
    engine.add_job("unit-tests", run_unit_tests, needs=[])
    engine.add_job("security-audit", run_security_sast, needs=[])
    engine.add_job("build-artifact", run_docker_build, needs=["static-analysis", "unit-tests", "security-audit"])

    # Jalankan pipeline engine
    engine.run()

if __name__ == "__main__":
    main()