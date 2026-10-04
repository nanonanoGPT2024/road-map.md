#!/usr/bin/env python3
"""
Lab Exercise: Core Foundations - DevOps Software Delivery Lifecycle (SDLC) Pipeline Simulator
Topic: 01-Core-Foundations / Chapter 01 - Module 02 Deep Dive

Description:
This script simulates an automated CI/CD pipeline engine executing an end-to-end SDLC
flow. It implements technical verification stages: Static Code Analysis (Linting),
SAST (Security Scanning for hardcoded secrets), Automated Testing, Cryptographic Artifact
Packaging (SHA-256 immutable manifests), Progressive Multi-Environment Promotion
(Dev -> Staging -> Production), and Zero-Downtime Deployment with Automated Rollback.
"""

import sys
import time
import json
import hashlib
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Tuple

# Terminal ANSI Color Palette
class Color:
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


class PipelineStatus(Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"


@dataclass
class CodeCommit:
    """Represents an atomic Git commit pushed to the version control repository."""
    commit_id: str
    author: str
    branch: str
    files: Dict[str, str]  # Filename -> Source content
    timestamp: float = field(default_factory=time.time)


@dataclass
class Artifact:
    """Represents an immutable deployable software package."""
    artifact_id: str
    commit_id: str
    checksum_sha256: str
    manifest: Dict[str, any]
    created_at: float = field(default_factory=time.time)


@dataclass
class Environment:
    """Represents an isolated deployment environment target."""
    name: str
    current_artifact: Optional[Artifact] = None
    healthy: bool = True


class PipelineEngine:
    """Core CI/CD automation engine executing software delivery stages."""

    def __init__(self):
        self.environments = {
            "dev": Environment(name="Development"),
            "staging": Environment(name="Staging"),
            "production": Environment(name="Production")
        }

    @staticmethod
    def _print_stage_header(stage_name: str) -> None:
        print(f"\n{Color.CYAN}---> [STAGE] {stage_name}{Color.RESET}")

    @staticmethod
    def _log(status: str, message: str, color: str = Color.WHITE) -> None:
        timestamp = time.strftime("%H:%M:%S", time.localtime())
        print(f"{Color.DIM}[{timestamp}]{Color.RESET} {color}[{status}]{Color.RESET} {message}")

    def run_linter(self, commit: CodeCommit) -> bool:
        """Stage 1: Linting and Code Style Analysis."""
        self._print_stage_header("Static Analysis & Code Linting")
        self._log("EXEC", f"Analyzing {len(commit.files)} source file(s)...", Color.YELLOW)
        time.sleep(0.3)

        for filename, content in commit.files.items():
            lines = content.splitlines()
            for line_idx, line in enumerate(lines, start=1):
                if len(line) > 100:
                    self._log("FAIL", f"{filename}:{line_idx} Line exceeds 100 characters limit.", Color.RED)
                    return False
                if line.rstrip() != line:
                    self._log("FAIL", f"{filename}:{line_idx} Trailing whitespace detected.", Color.RED)
                    return False

        self._log("OK", "Static code analysis passed: clean formatting and syntax compliance.", Color.GREEN)
        return True

    def run_sast_scan(self, commit: CodeCommit) -> bool:
        """Stage 2: Static Application Security Testing (SAST)."""
        self._print_stage_header("Static Application Security Testing (SAST)")
        self._log("EXEC", "Scanning for hardcoded secrets and known vulnerabilities...", Color.YELLOW)
        time.sleep(0.3)

        secret_signatures = ["aws_secret_key", "password=", "BEGIN RSA PRIVATE KEY", "bearer "]

        for filename, content in commit.files.items():
            for sig in secret_signatures:
                if sig.lower() in content.lower():
                    self._log("ALERT", f"High-severity security violation in {filename}!", Color.RED)
                    self._log("ALERT", f"Detected credential signature pattern: '{sig}'", Color.RED)
                    return False

        self._log("OK", "SAST passed: No credentials or vulnerable dependencies detected.", Color.GREEN)
        return True

    def run_automated_tests(self, commit: CodeCommit) -> bool:
        """Stage 3: Automated Unit and Integration Test Runner."""
        self._print_stage_header("Automated Test Suite (Unit & Integration)")
        self._log("EXEC", "Spawning ephemeral test container...", Color.YELLOW)
        time.sleep(0.3)

        test_cases = [
            ("test_database_connection_pool", 0.05),
            ("test_http_router_dispatch", 0.08),
            ("test_user_auth_payload_validation", 0.12),
            ("test_concurrency_race_condition", 0.15),
        ]

        for test_name, duration in test_cases:
            time.sleep(duration)
            # Simulate explicit failure if bug flag exists in code
            if "FAIL_TEST" in commit.files.get("service.py", ""):
                self._log("FAIL", f"{test_name} failed: Assertion error in payload output.", Color.RED)
                return False
            self._log("PASS", f"{test_name} (took {duration:.2f}s)", Color.GREEN)

        self._log("OK", "All 4 test cases passed successfully (100% coverage requirement met).", Color.GREEN)
        return True

    def build_and_package(self, commit: CodeCommit) -> Optional[Artifact]:
        """Stage 4: Immutable Artifact Compilation and Packaging."""
        self._print_stage_header("Artifact Compilation & Packaging")
        self._log("EXEC", "Building containerized binary package...", Color.YELLOW)
        time.sleep(0.4)

        raw_payload = json.dumps(commit.files, sort_keys=True).encode("utf-8")
        sha256_hash = hashlib.sha256(raw_payload).hexdigest()
        artifact_id = f"pkg-{commit.commit_id[:8]}"

        artifact = Artifact(
            artifact_id=artifact_id,
            commit_id=commit.commit_id,
            checksum_sha256=sha256_hash,
            manifest={
                "build_env": "alpine-linux-3.18",
                "compiler": "python-cpython-3.10",
                "entrypoint": "main.py",
                "byte_size": len(raw_payload)
            }
        )

        self._log("OK", f"Artifact generated: {artifact.artifact_id}", Color.GREEN)
        self._log("INFO", f"Digest SHA-256: {artifact.checksum_sha256}", Color.MAGENTA)
        return artifact

    def deploy(self, env_key: str, artifact: Artifact) -> bool:
        """Stage 5: Deployment to Target Environment with Smoke Testing."""
        env = self.environments[env_key]
        self._print_stage_header(f"Deployment Target: {env.name.upper()}")
        self._log("INFO", f"Rolling out {artifact.artifact_id} to {env.name} cluster...", Color.YELLOW)
        time.sleep(0.4)

        prev_artifact = env.current_artifact
        env.current_artifact = artifact

        # Verification: Smoke test
        self._log("EXEC", "Conducting synthetic health check probes...", Color.YELLOW)
        time.sleep(0.3)

        # Trigger simulated anomaly if specific marker found
        smoke_test_failure = (
            env_key == "production" and 
            "TRIGGER_PROD_PANIC" in artifact.manifest.get("entrypoint", "")
        )

        if smoke_test_failure:
            self._log("CRIT", f"Smoke test failed on {env.name}: HTTP 500 /health probe timeout.", Color.RED)
            self._log("WARN", "Initiating automated self-healing rollback sequence...", Color.YELLOW)
            time.sleep(0.5)

            # Rollback
            env.current_artifact = prev_artifact
            rollback_version = prev_artifact.artifact_id if prev_artifact else "NONE"
            self._log("OK", f"Rollback completed. Restored active traffic to: {rollback_version}", Color.GREEN)
            return False

        self._log("OK", f"{env.name} deployment verification successful. Traffic routing 100%.", Color.GREEN)
        return True

    def execute_pipeline(self, commit: CodeCommit) -> PipelineStatus:
        """Coordinates the end-to-end software delivery lifecycle."""
        print(f"\n{Color.BOLD}{'='*70}")
        print(f" CI/CD PIPELINE TRIGGERED: Commit {commit.commit_id[:8]} on branch '{commit.branch}'")
        print(f" Author: {commit.author}")
        print(f"{'='*70}{Color.RESET}")

        # 1. Linting
        if not self.run_linter(commit):
            return PipelineStatus.FAILED

        # 2. SAST Scan
        if not self.run_sast_scan(commit):
            return PipelineStatus.FAILED

        # 3. Automated Unit/Integration Tests
        if not self.run_automated_tests(commit):
            return PipelineStatus.FAILED

        # 4. Artifact Build
        artifact = self.build_and_package(commit)
        if not artifact:
            return PipelineStatus.FAILED

        # 5. Continuous Deployment - Progressive Environments
        for target in ["dev", "staging", "production"]:
            deployed = self.deploy(target, artifact)
            if not deployed:
                if target == "production":
                    return PipelineStatus.ROLLED_BACK
                return PipelineStatus.FAILED

        return PipelineStatus.PASSED


def main() -> None:
    engine = PipelineEngine()

    # Pre-seed production environment with a stable baseline release
    baseline_commit = CodeCommit(
        commit_id="00000000a1b2c3d4",
        author="sre-team@corp.internal",
        branch="main",
        files={"service.py": "# Stable production baseline v1.0.0"}
    )
    engine.environments["production"].current_artifact = Artifact(
        artifact_id="pkg-baseline",
        commit_id=baseline_commit.commit_id,
        checksum_sha256="4cf90a6d0c4d4d1e2e1e3b6f8a8b8c8d8e8f808182838485868788898a8b8c8d",
        manifest={"entrypoint": "main.py"}
    )

    # -------------------------------------------------------------
    # Scenario 1: Unsafe Commit - Hardcoded AWS Secret (SAST Rejection)
    # -------------------------------------------------------------
    bad_secret_commit = CodeCommit(
        commit_id="8f921ab07e4d88ef",
        author="intern_dev@corp.internal",
        branch="feature/payment-gate",
        files={
            "service.py": "def process():\n    pass",
            "config.py": "AWS_SECRET_KEY = 'AKIAIOSFODNN7EXAMPLE_SECRET_LEAK'"
        }
    )
    status_1 = engine.execute_pipeline(bad_secret_commit)
    print(f"\nResult Scenario 1: {Color.RED}{status_1.value}{Color.RESET}")

    time.sleep(1.0)

    # -------------------------------------------------------------
    # Scenario 2: Unstable Commit - Production Smoke Check Fails (Rollback)
    # -------------------------------------------------------------
    unstable_commit = CodeCommit(
        commit_id="3bc94910cf9173aa",
        author="senior_dev@corp.internal",
        branch="release/v2.1.0",
        files={
            "service.py": "def handle_request():\n    return {'status': 200}",
            "main.py": "# Standard entrypoint\nTRIGGER_PROD_PANIC = True"
        }
    )
    status_2 = engine.execute_pipeline(unstable_commit)
    print(f"\nResult Scenario 2: {Color.YELLOW}{status_2.value}{Color.RESET}")

    time.sleep(1.0)

    # -------------------------------------------------------------
    # Scenario 3: Healthy Commit - End-to-End Promotion to Production
    # -------------------------------------------------------------
    clean_commit = CodeCommit(
        commit_id="d56a310bbfa91e23",
        author="lead_dev@corp.internal",
        branch="main",
        files={
            "service.py": "def compute():\n    return sum(range(100))",
            "main.py": "import service\nif __name__ == '__main__':\n    service.compute()"
        }
    )
    status_3 = engine.execute_pipeline(clean_commit)
    print(f"\nResult Scenario 3: {Color.GREEN}{status_3.value}{Color.RESET}")

    # Summary Report
    print(f"\n{Color.BOLD}{'='*70}")
    print(f" PIPELINE AUDIT SUMMARY")
    print(f"{'='*70}{Color.RESET}")
    for env_name, env_obj in engine.environments.items():
        current_pkg = env_obj.current_artifact.artifact_id if env_obj.current_artifact else "EMPTY"
        print(f" Environment [{env_name.upper():<10}] -> Active Package: {Color.CYAN}{current_pkg}{Color.RESET}")
    print(f"{Color.BOLD}{'='*70}{Color.RESET}\n")


if __name__ == "__main__":
    main()