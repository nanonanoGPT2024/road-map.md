#!/usr/bin/env python3
"""
Lab Hands-on: Otomasi Dasar CI/CD Menggunakan GitHub Actions (Deep Dive)
Bab 10: Simulasi Engine Eksekusi Workflow GitHub Actions

Script ini memodelkan runtime engine GitHub Actions secara mandiri menggunakan
Python Standard Library. Fitur yang disimulasikan meliputi:
- Parsing workflow definition (Jobs, Steps, Dependencies 'needs', Matrix Strategy).
- Resolusi Directed Acyclic Graph (DAG) untuk penentuan urutan eksekusi job.
- Evaluasi ekspresi konteks (${{ env.* }}, ${{ matrix.* }}).
- Simulasi cache action (simulasi cache key, hit/miss, store/restore).
- Runner eksekutor bertingkat dengan logging ANSI berformat GitHub Actions.
"""

import sys
import time
import json
import hashlib
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from collections import defaultdict, deque

# ANSI Color Codes untuk standard terminal styling
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[31m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN = "\033[36m"
CLR_GRAY = "\033[90m"


@dataclass
class Step:
    name: str
    run: Optional[str] = None
    uses: Optional[str] = None
    env: Dict[str, str] = field(default_factory=dict)
    with_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Job:
    id: str
    name: str
    runs_on: str
    steps: List[Step]
    needs: List[str] = field(default_factory=list)
    strategy: Dict[str, Any] = field(default_factory=dict)
    env: Dict[str, str] = field(default_factory=dict)


class CacheBackend:
    """Simulasi storage remote caching GitHub Actions (actions/cache@v3)."""
    def __init__(self):
        self._storage: Dict[str, bytes] = {}

    def get(self, key: str) -> Optional[bytes]:
        return self._storage.get(key)

    def set(self, key: str, data: bytes) -> None:
        self._storage[key] = data


class WorkflowEngine:
    """
    Core Engine yang memproses DAG jobs, resolusi matrix, interpolasi env/matrix,
    dan mengeksekusi step layaknya runner virtual GitHub Actions.
    """
    def __init__(self, workflow_config: Dict[str, Any]):
        self.name = workflow_config.get("name", "Simulated-Workflow")
        self.raw_jobs = workflow_config.get("jobs", {})
        self.cache_backend = CacheBackend()
        self.artifacts: Dict[str, Any] = {}

    def _interpolate(self, text: str, context: Dict[str, Any]) -> str:
        """Menggantikan ekspresi format GitHub Actions: ${{ context.variable }}."""
        result = text
        for ctx_key, ctx_val in context.items():
            if isinstance(ctx_val, dict):
                for k, v in ctx_val.items():
                    placeholder = f"${{{{ {ctx_key}.{k} }}}}"
                    result = result.replace(placeholder, str(v))
        return result

    def _topological_sort_jobs(self) -> List[List[str]]:
        """
        Menyusun urutan eksekusi job berdasarkan array 'needs' (DAG Resolution).
        Mengembalikan list layer batch yang dapat dieksekusi secara paralel.
        """
        in_degree = {job_id: 0 for job_id in self.raw_jobs}
        graph = defaultdict(list)

        for job_id, job_data in self.raw_jobs.items():
            needs = job_data.get("needs", [])
            if isinstance(needs, str):
                needs = [needs]
            for prerequisite in needs:
                if prerequisite not in self.raw_jobs:
                    raise ValueError(f"Job '{job_id}' membutuhkan job tidak dikenal: '{prerequisite}'")
                graph[prerequisite].append(job_id)
                in_degree[job_id] += 1

        queue = deque([job_id for job_id, deg in in_degree.items() if deg == 0])
        ordered_batches = []

        while queue:
            current_layer = []
            layer_size = len(queue)
            for _ in range(layer_size):
                curr = queue.popleft()
                current_layer.append(curr)
                for neighbor in graph[curr]:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        queue.append(neighbor)
            ordered_batches.append(current_layer)

        flattened = [j for batch in ordered_batches for j in batch]
        if len(flattened) != len(self.raw_jobs):
            raise RuntimeError("Ditemukan Circular Dependency (siklus) pada dependency DAG job!")

        return ordered_batches

    def _expand_matrix(self, job_id: str, job_data: Dict[str, Any]) -> List[Job]:
        """Memecah definisi 1 job dengan strategy matrix menjadi multiple instans job terpisah."""
        strategy = job_data.get("strategy", {})
        matrix = strategy.get("matrix", {})
        steps_raw = job_data.get("steps", [])

        steps = [
            Step(
                name=s.get("name", "Unnamed Step"),
                run=s.get("run"),
                uses=s.get("uses"),
                env=s.get("env", {}),
                with_params=s.get("with", {})
            )
            for s in steps_raw
        ]

        if not matrix:
            return [Job(
                id=job_id,
                name=job_data.get("name", job_id),
                runs_on=job_data.get("runs-on", "ubuntu-latest"),
                steps=steps,
                needs=job_data.get("needs", []) if isinstance(job_data.get("needs", []), list) else [job_data.get("needs")],
                strategy={},
                env=job_data.get("env", {})
            )]

        # Hitung kombinasi Cartesian sederhana untuk matrix
        keys = list(matrix.keys())
        combinations = [{}]
        for k in keys:
            combinations = [
                {**existing, k: val}
                for existing in combinations
                for val in matrix[k]
            ]

        expanded_jobs = []
        for combo in combinations:
            combo_suffix = ", ".join(f"{k}:{v}" for k, v in combo.items())
            interpolated_job_id = f"{job_id} ({combo_suffix})"
            expanded_jobs.append(Job(
                id=interpolated_job_id,
                name=f"{job_data.get('name', job_id)} ({combo_suffix})",
                runs_on=job_data.get("runs-on", "ubuntu-latest"),
                steps=steps,
                needs=job_data.get("needs", []) if isinstance(job_data.get("needs", []), list) else [job_data.get("needs")],
                strategy=combo,
                env=job_data.get("env", {})
            ))

        return expanded_jobs

    def _execute_step(self, step: Step, context: Dict[str, Any]) -> bool:
        """Simulasi eksekusi instruksi action individual."""
        step_name = self._interpolate(step.name, context)
        print(f"  {CLR_CYAN}▸ [STEP]{CLR_RESET} {step_name}")
        t0 = time.perf_counter()

        # Simulasi Action 'actions/cache'
        if step.uses and "actions/cache" in step.uses:
            key_raw = step.with_params.get("key", "default-key")
            cache_key = self._interpolate(key_raw, context)
            cached_data = self.cache_backend.get(cache_key)
            if cached_data:
                print(f"    {CLR_GREEN}✓ Cache Hit!{CLR_RESET} Mengambil asset untuk key: '{cache_key}'")
            else:
                print(f"    {CLR_YELLOW}! Cache Miss.{CLR_RESET} Key '{cache_key}' belum ada. Menyiapkan cold build.")
                self.cache_backend.set(cache_key, b"precompiled_deps_manifest")
            context["steps"] = context.get("steps", {})
            context["steps"]["cache"] = {"outputs": {"cache-hit": str(cached_data is not None).lower()}}
            time.sleep(0.04)
            return True

        # Simulasi CLI Shell Run
        if step.run:
            command = self._interpolate(step.run, context).strip()
            print(f"    {CLR_GRAY}$ {command}{CLR_RESET}")
            time.sleep(0.05)  # Simulasi overhead kompilasi / IO

            # Logic mock kegagalan bila ditemukan simulasi error eksplisit
            if "exit 1" in command or "fail" in command.lower():
                print(f"    {CLR_RED}✗ Perintah gagal dieksekusi dengan kode keluar non-zero.{CLR_RESET}")
                return False

            print(f"    {CLR_GREEN}✓ Selesai ({time.perf_counter() - t0:.3f}s){CLR_RESET}")
            return True

        return True

    def run(self, event_context: Dict[str, Any]) -> bool:
        """Entrypoint eksekusi seluruh workflow berdasarkan payload event Git."""
        print(f"{CLR_BOLD}{CLR_BLUE}======================================================{CLR_RESET}")
        print(f"{CLR_BOLD}GITHUB ACTIONS RUNNER ENGINE SIMULATOR{CLR_RESET}")
        print(f"Workflow: {CLR_MAGENTA}{self.name}{CLR_RESET}")
        print(f"Event:    {CLR_YELLOW}{event_context.get('event_name')} "
              f"({event_context.get('ref')}) oleh {event_context.get('actor')}{CLR_RESET}")
        print(f"{CLR_BOLD}{CLR_BLUE}======================================================{CLR_RESET}\n")

        batches = self._topological_sort_jobs()
        global_success = True

        for batch_index, batch in enumerate(batches, 1):
            print(f"{CLR_BOLD}::group::Pipeline Phase #{batch_index} (Parallel Batches: {batch}){CLR_RESET}")
            for raw_job_id in batch:
                job_template = self.raw_jobs[raw_job_id]
                expanded_subjobs = self._expand_matrix(raw_job_id, job_template)

                for job in expanded_subjobs:
                    print(f"\n{CLR_BOLD}► Running Job: {CLR_YELLOW}{job.id}{CLR_RESET} on {CLR_CYAN}{job.runs_on}{CLR_RESET}")
                    job_context = {
                        "env": {**job.env},
                        "matrix": job.strategy,
                        "github": event_context
                    }

                    job_success = True
                    for step in job.steps:
                        status = self._execute_step(step, job_context)
                        if not status:
                            job_success = False
                            global_success = False
                            print(f"{CLR_RED}Job '{job.id}' dihentikan karena kegagalan step.{CLR_RESET}")
                            break

                    if job_success:
                        print(f"  {CLR_GREEN}Job Status: SUCCESS{CLR_RESET}")
                    else:
                        print(f"  {CLR_RED}Job Status: FAILED{CLR_RESET}")
            print(f"{CLR_BOLD}::endgroup::{CLR_RESET}\n")

        print(f"{CLR_BOLD}{CLR_BLUE}------------------------------------------------------{CLR_RESET}")
        if global_success:
            print(f"{CLR_BOLD}{CLR_GREEN}STATUS WORKFLOW: BERHASIL DIEKSEKUSI (0 Error){CLR_RESET}")
        else:
            print(f"{CLR_BOLD}{CLR_RED}STATUS WORKFLOW: GAGAL DIEKSEKUSI{CLR_RESET}")
        print(f"{CLR_BOLD}{CLR_BLUE}------------------------------------------------------{CLR_RESET}")

        return global_success


def main():
    # Model Definisi Konfigurasi YAML GitHub Actions (.github/workflows/ci.yml)
    workflow_yaml_mock = {
        "name": "Production Continuous Integration & Quality Gate",
        "on": ["push"],
        "jobs": {
            "lint-and-validate": {
                "name": "Lint Source Code",
                "runs-on": "ubuntu-latest",
                "steps": [
                    {"name": "Checkout source code", "uses": "actions/checkout@v3"},
                    {
                        "name": "Check python syntax & linting",
                        "run": "python3 -m py_compile **/*.py && flake8 . --max-line-length=120"
                    }
                ]
            },
            "unit-tests": {
                "name": "Run Test Suite",
                "needs": ["lint-and-validate"],
                "runs-on": "ubuntu-latest",
                "strategy": {
                    "matrix": {
                        "python-version": ["3.10", "3.11"],
                        "os-target": ["ubuntu-latest", "macos-latest"]
                    }
                },
                "steps": [
                    {"name": "Checkout repo", "uses": "actions/checkout@v3"},
                    {
                        "name": "Cache Pip Dependencies",
                        "uses": "actions/cache@v3",
                        "with": {
                            "path": "~/.cache/pip",
                            "key": "deps-${{ matrix.os-target }}-py${{ matrix.python-version }}"
                        }
                    },
                    {
                        "name": "Execute pytest on ${{ matrix.os-target }} (Python ${{ matrix.python-version }})",
                        "run": "pytest -q --disable-warnings"
                    }
                ]
            },
            "build-and-deploy": {
                "name": "Build Container Image",
                "needs": ["unit-tests"],
                "runs-on": "ubuntu-latest",
                "steps": [
                    {
                        "name": "Compile Binary Artifact",
                        "run": "echo 'Building production binary payload...' && tar -czf release.tar.gz ."
                    },
                    {
                        "name": "Publish to Container Registry",
                        "run": "echo 'Pushing Docker image tag v1.0.0-rc ...' && exit 0"
                    }
                ]
            }
        }
    }

    # Payload event mock dari trigger Git Push
    commit_sha = hashlib.sha1(b"simulated_commit_data_v1").hexdigest()[:8]
    event_payload = {
        "event_name": "push",
        "ref": "refs/heads/main",
        "actor": "octocat",
        "sha": commit_sha
    }

    # Inisialisasi dan jalankan engine workflow
    engine = WorkflowEngine(workflow_yaml_mock)
    success = engine.run(event_payload)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()