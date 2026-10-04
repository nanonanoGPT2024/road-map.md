#!/usr/bin/env python3
"""
Lab Hands-on: Arsitektur Eksekusi GitHub Actions CI/CD & DAG Workflow Engine
Kategori: 01-Core-Foundations / Bab 08 - Modul 02 Deep Dive

Skrip ini memodelkan runtime internal GitHub Actions Runner:
1. Directed Acyclic Graph (DAG) Job Dependency Solver (penyelesaian 'needs').
2. Matrix Strategy Expansion (Cartesian Product dari dimensi matrix).
3. Context & State Store ($GITHUB_ENV, $GITHUB_OUTPUT, runner context).
4. Content-Addressable Cache Layer (simulasi actions/cache dengan hashing file).
5. Artifact Store Pipeline (simulasi upload-artifact & download-artifact).
"""

import hashlib
import itertools
import os
import sys
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

# ==============================================================================
# ANSI Styling Helpers
# ==============================================================================
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    RED = "\033[31m"


# ==============================================================================
# Model Entitas GitHub Actions
# ==============================================================================
@dataclass
class Step:
    name: str
    id: Optional[str] = None
    run: Optional[Callable[["ExecutionContext"], int]] = None
    uses: Optional[str] = None
    with_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Job:
    name: str
    needs: List[str] = field(default_factory=list)
    strategy_matrix: Optional[Dict[str, List[Any]]] = None
    steps: List[Step] = field(default_factory=list)
    runs_on: str = "ubuntu-latest"


# ==============================================================================
# Runtime Execution Context & Storage
# ==============================================================================
class ExecutionContext:
    """Menyimpan environment, step outputs, runner cache, dan storage artifact."""

    def __init__(self, job_name: str, matrix_vars: Dict[str, Any]):
        self.job_name = job_name
        self.matrix = matrix_vars
        self.env: Dict[str, str] = {
            "CI": "true",
            "GITHUB_ACTION": "run",
            "GITHUB_JOB": job_name,
            "GITHUB_RUN_ID": "89421045",
            "GITHUB_SHA": "e4f8b2d1c67a99f0e345b1287c88b0a1a5b23d91",
        }
        self.step_outputs: Dict[str, Dict[str, str]] = defaultdict(dict)
        self.active_step_id: Optional[str] = None

    def set_output(self, key: str, value: str):
        """Simulasi: echo 'key=value' >> $GITHUB_OUTPUT"""
        if self.active_step_id:
            self.step_outputs[self.active_step_id][key] = value

    def set_env(self, key: str, value: str):
        """Simulasi: echo 'KEY=VALUE' >> $GITHUB_ENV"""
        self.env[key] = value


class ArtifactStore:
    """Penyimpanan blob terpusat (GitHub Artifact Storage backend)."""

    def __init__(self):
        self._store: Dict[str, bytes] = {}

    def upload(self, name: str, data: bytes):
        self._store[name] = data

    def download(self, name: str) -> Optional[bytes]:
        return self._store.get(name)


class ActionCacheStore:
    """Simulasi Content-Addressable Cache (actions/cache)."""

    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}

    def compute_hash(self, payload: str) -> str:
        """Menghasilkan cache key derivatif seperti hashFiles('**/requirements.lock')."""
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        return self._cache.get(key)

    def put(self, key: str, data: Dict[str, Any]):
        self._cache[key] = data


# ==============================================================================
# DAG Engine & Runner
# ==============================================================================
class WorkflowRunner:
    def __init__(self, name: str):
        self.workflow_name = name
        self.jobs: Dict[str, Job] = {}
        self.artifacts = ArtifactStore()
        self.cache = ActionCacheStore()

    def add_job(self, job_id: str, job: Job):
        self.jobs[job_id] = job

    def _resolve_dag_execution_order(self) -> List[List[str]]:
        """
        Menyelesaikan graph dependensi 'needs' menggunakan Topological Sort (Kahn's Algorithm).
        Mengembalikan daftar tahap (stage) yang dapat dieksekusi secara paralel.
        """
        in_degree: Dict[str, int] = {jid: 0 for jid in self.jobs}
        dependents: Dict[str, List[str]] = defaultdict(list)

        for jid, job in self.jobs.items():
            for prereq in job.needs:
                if prereq not in self.jobs:
                    raise ValueError(f"Job '{jid}' merujuk dependensi yang tidak valid: '{prereq}'")
                dependents[prereq].append(jid)
                in_degree[jid] += 1

        queue = deque([jid for jid, deg in in_degree.items() if deg == 0])
        stages: List[List[str]] = []

        visited_count = 0
        while queue:
            current_stage = []
            for _ in range(len(queue)):
                curr = queue.popleft()
                current_stage.append(curr)
                visited_count += 1
                for dep in dependents[curr]:
                    in_degree[dep] -= 1
                    if in_degree[dep] == 0:
                        queue.append(dep)
            stages.append(current_stage)

        if visited_count != len(self.jobs):
            raise RuntimeError("Siklus sirkular terdeteksi pada definisi 'needs' workflow!")

        return stages

    def _expand_matrix(self, job: Job) -> List[Dict[str, Any]]:
        """Melakukan perkalian Cartesian Product dari strategy.matrix."""
        if not job.strategy_matrix:
            return [{}]

        keys = list(job.strategy_matrix.keys())
        values = list(job.strategy_matrix.values())
        combinations = list(itertools.product(*values))

        matrix_instances = []
        for combo in combinations:
            matrix_instances.append(dict(zip(keys, combo)))
        return matrix_instances

    def _execute_step(self, step: Step, ctx: ExecutionContext) -> bool:
        ctx.active_step_id = step.id
        print(f"      {Style.CYAN}▸ Run Step:{Style.RESET} {step.name}")

        start_time = time.perf_counter()
        exit_code = 0

        try:
            if step.run:
                exit_code = step.run(ctx)
            elif step.uses:
                exit_code = self._handle_builtin_action(step, ctx)
            else:
                print(f"        {Style.YELLOW}! Step kosong dilewati{Style.RESET}")
        except Exception as ex:
            print(f"        {Style.RED}✗ Step Exception: {ex}{Style.RESET}")
            exit_code = 1

        elapsed = (time.perf_counter() - start_time) * 1000

        if exit_code == 0:
            print(f"        {Style.GREEN}✓ Berhasil{Style.RESET} {Style.DIM}({elapsed:.2f}ms){Style.RESET}")
            return True
        else:
            print(f"        {Style.RED}✗ Gagal dengan exit code {exit_code}{Style.RESET}")
            return False

    def _handle_builtin_action(self, step: Step, ctx: ExecutionContext) -> int:
        """Handler emulasi untuk Action komunitas umum."""
        action_name = step.uses
        params = step.with_params

        if action_name == "actions/cache@v3":
            key = params.get("key", "default-key")
            hit = self.cache.get(key)
            if hit:
                print(f"        {Style.MAGENTA}[Cache Hit]{Style.RESET} Kunci ditemukan: {key}")
                ctx.set_output("cache-hit", "true")
            else:
                print(f"        {Style.YELLOW}[Cache Miss]{Style.RESET} Tidak ada cache untuk: {key}")
                ctx.set_output("cache-hit", "false")
                # Pre-populate dummy cache untuk simulasi save pada akhir job
                self.cache.put(key, {"cached_at": time.time(), "data": "compiled_wheels"})
            return 0

        elif action_name == "actions/upload-artifact@v3":
            artifact_name = params.get("name", "artifact")
            content = params.get("content", b"").encode("utf-8") if isinstance(params.get("content"), str) else params.get("content", b"")
            self.artifacts.upload(artifact_name, content)
            print(f"        {Style.BLUE}[Artifact]{Style.RESET} Mengunggah '{artifact_name}' ({len(content)} bytes)")
            return 0

        elif action_name == "actions/download-artifact@v3":
            artifact_name = params.get("name", "artifact")
            data = self.artifacts.download(artifact_name)
            if data is not None:
                print(f"        {Style.BLUE}[Artifact]{Style.RESET} Mengunduh '{artifact_name}' ({len(data)} bytes)")
                ctx.set_output("download-path", f"/workspace/{artifact_name}")
                return 0
            print(f"        {Style.RED}[Artifact]{Style.RESET} Artifact '{artifact_name}' tidak ditemukan!")
            return 1

        print(f"        {Style.RED}Unknown action: {action_name}{Style.RESET}")
        return 1

    def run(self):
        """Menjalankan seluruh workflow lifecycle."""
        print(f"\n{Style.BOLD}=== Memulai Workflow: {self.workflow_name} ==={Style.RESET}")
        stages = self._resolve_dag_execution_order()

        for stage_idx, stage_jobs in enumerate(stages, start=1):
            print(f"\n{Style.BOLD}{Style.BLUE}--- Stage {stage_idx} (Jobs Paralel: {', '.join(stage_jobs)}) ---{Style.RESET}")
            for job_id in stage_jobs:
                job_def = self.jobs[job_id]
                matrices = self._expand_matrix(job_def)

                for matrix_instance in matrices:
                    matrix_label = f" ({matrix_instance})" if matrix_instance else ""
                    print(f"\n  {Style.BOLD}▶ Mulai Job: {job_id}{matrix_label} on [{job_def.runs_on}]{Style.RESET}")

                    ctx = ExecutionContext(job_id, matrix_instance)

                    # Simulasikan setting environment bawaan matrix
                    for k, v in matrix_instance.items():
                        ctx.set_env(f"MATRIX_{k.upper()}", str(v))

                    job_success = True
                    for step in job_def.steps:
                        success = self._execute_step(step, ctx)
                        if not success:
                            job_success = False
                            print(f"\n  {Style.RED}Job '{job_id}' dihentikan karena langkah gagal.{Style.RESET}")
                            return False

        print(f"\n{Style.BOLD}{Style.GREEN}✔ Workflow '{self.workflow_name}' SELESAI DENGAN SUKSES!{Style.RESET}\n")
        return True


# ==============================================================================
# Deklarasi Skenario Lab
# ==============================================================================
def create_lab_workflow() -> WorkflowRunner:
    runner = WorkflowRunner("CI/CD Enterprise Pipeline")

    # Mock isi file kunci lock dependencies
    mock_lock_content = "urllib3==2.0.7\nrequests==2.31.0\npytest==7.4.3"
    lock_hash = runner.cache.compute_hash(mock_lock_content)
    cache_key = f"python-deps-hash-{lock_hash}"

    # 1. Job Linter & Static Analysis (Tanpa dependensi)
    lint_job = Job(
        name="Lint & Static Analysis",
        runs_on="ubuntu-latest",
        steps=[
            Step(
                name="Checkout repository",
                run=lambda ctx: 0
            ),
            Step(
                name="Execute Flake8 & Mypy",
                id="typecheck",
                run=lambda ctx: (
                    ctx.set_output("violations_count", "0"),
                    print(f"        {Style.DIM}[Stdout] 0 violations found. Strict type pass.{Style.RESET}")
                ) and 0
            )
        ]
    )

    # 2. Job Matrix Testing (Bergantung pada lint_job)
    test_job = Job(
        name="Unit & Integration Tests",
        needs=["lint"],
        strategy_matrix={
            "python-version": ["3.10", "3.11"],
            "os-target": ["ubuntu-latest", "macos-latest"]
        },
        steps=[
            Step(
                name="Restore pip dependency cache",
                id="pip-cache",
                uses="actions/cache@v3",
                with_params={"key": cache_key}
            ),
            Step(
                name="Install dependencies (conditional)",
                run=lambda ctx: (
                    print(f"        {Style.DIM}[Stdout] Menggunakan dependencies ter-cache.{Style.RESET}")
                    if ctx.step_outputs.get("pip-cache", {}).get("cache-hit") == "true"
                    else print(f"        {Style.DIM}[Stdout] Cache miss: Mengunduh packages...{Style.RESET}")
                ) or 0
            ),
            Step(
                name="Run Pytest Suite",
                run=lambda ctx: (
                    print(f"        {Style.DIM}[Stdout] Menjalankan test suite pada {ctx.matrix}... 48 passed.{Style.RESET}")
                ) or 0
            )
        ]
    )

    # 3. Job Build Package & Binary (Bergantung pada test_job)
    build_job = Job(
        name="Build Distribution Package",
        needs=["test"],
        runs_on="ubuntu-latest",
        steps=[
            Step(
                name="Compile Wheel package",
                id="builder",
                run=lambda ctx: (
                    ctx.set_output("wheel_file", "app_core-1.0.0-py3-none-any.whl"),
                    print(f"        {Style.DIM}[Stdout] Building wheel: dist/app_core-1.0.0-py3-none-any.whl{Style.RESET}")
                ) or 0
            ),
            Step(
                name="Upload Wheel Artifact",
                uses="actions/upload-artifact@v3",
                with_params={
                    "name": "release-package",
                    "content": "PK\x03\x04...[MOCK COMPILED ZIP BINARY]...PK\x05\x06"
                }
            )
        ]
    )

    # 4. Job Deployment (Bergantung pada build_job)
    deploy_job = Job(
        name="Deploy to Production Staging",
        needs=["build"],
        runs_on="ubuntu-latest",
        steps=[
            Step(
                name="Download Application Artifact",
                uses="actions/download-artifact@v3",
                with_params={"name": "release-package"}
            ),
            Step(
                name="Execute Deployment Blue/Green Script",
                run=lambda ctx: (
                    print(f"        {Style.DIM}[Stdout] Rolling out to cluster: us-east-1. Verification healthy.{Style.RESET}")
                ) or 0
            )
        ]
    )

    runner.add_job("lint", lint_job)
    runner.add_job("test", test_job)
    runner.add_job("build", build_job)
    runner.add_job("deploy", deploy_job)

    return runner


# ==============================================================================
# Titik Masuk Utama
# ==============================================================================
if __name__ == "__main__":
    runner = create_lab_workflow()

    print(f"{Style.BOLD}{Style.MAGENTA}SIMULASI RUN 1: Cache Cold (Cache Miss pada run pertama){Style.RESET}")
    success_run_1 = runner.run()

    if success_run_1:
        print(f"\n{Style.BOLD}{Style.MAGENTA}SIMULASI RUN 2: Cache Warm (Membuktikan Cache Hit pada run berikutnya){Style.RESET}")
        # Jalankan ulang runner yang sama untuk menguji retensi cache state
        runner.run()