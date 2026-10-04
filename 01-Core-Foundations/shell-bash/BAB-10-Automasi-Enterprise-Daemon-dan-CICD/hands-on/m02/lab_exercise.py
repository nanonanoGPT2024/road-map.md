#!/usr/bin/env python3
"""
Lab Exercise: Modul 02 Deep Dive - Enterprise Automation, System Admin & CI/CD
Topik: shell-bash (01-Core-Foundations)

Deskripsi:
Program ini memodelkan Enterprise CI/CD Pipeline & System Automation Engine.
Mengimplementasikan manajemen lockfile berbasis PID (mencegah overlapping execution),
orchestrasi stage modular berbasis POSIX Bash, streaming log real-time,
penangkapan exit code/sinyal Linux, verifikasi integritas kriptografis (SHA-256),
dan pembuatan audit report operasional enterprise.
"""

import os
import sys
import time
import subprocess
import hashlib
import tempfile
import pathlib
from dataclasses import dataclass, field
from typing import List, Dict, Optional

# ANSI Color Codes untuk terminal styling enterprise
CLR_RESET   = "\033[0m"
CLR_BOLD    = "\033[1m"
CLR_RED     = "\033[31m"
CLR_GREEN   = "\033[32m"
CLR_YELLOW  = "\033[33m"
CLR_BLUE    = "\033[34m"
CLR_CYAN    = "\033[36m"
CLR_GRAY    = "\033[90m"

@dataclass
class StageResult:
    """Menyimpan telemetry dan metrik eksekusi tiap tahapan pipeline bash."""
    name: str
    exit_code: int
    duration_sec: float
    stdout: str
    stderr: str
    is_success: bool


@dataclass
class PipelineStage:
    """Definisi stage otomatisasi yang dieksekusi melalui sub-shell Bash."""
    name: str
    bash_script: str
    allow_failure: bool = False
    custom_env: Dict[str, str] = field(default_factory=dict)


class EnterpriseAutomationEngine:
    """
    Core Engine yang mengatur pipeline CI/CD, lockfile management, 
    dan eksekusi shell script dengan kontrol error strict (set -euo pipefail).
    """

    def __init__(self, pipeline_name: str, lock_dir: Optional[str] = None):
        self.pipeline_name = pipeline_name
        self.lock_dir = pathlib.Path(lock_dir or tempfile.gettempdir())
        self.lock_file = self.lock_dir / f"{self.pipeline_name}.lock"
        self.stages: List[PipelineStage] = []
        self.results: List[StageResult] = []

    def acquire_lock(self) -> bool:
        """
        Menerapkan enterprise concurrency control: Mutex lockfile berbasis PID.
        Mencegah multiple cron jobs atau worker bertabrakan di host yang sama.
        """
        if self.lock_file.exists():
            try:
                locked_pid = int(self.lock_file.read_text().strip())
                # Verifikasi jika process dengan PID tersebut masih aktif (Signal 0 check)
                os.kill(locked_pid, 0)
                print(f"{CLR_RED}[LOCK ERROR]{CLR_RESET} Pipeline sedang berjalan pada PID {locked_pid}. Aborting.")
                return False
            except (OSError, ValueError):
                # Stale lock: PID tidak ada atau corrupted, timpa file lock
                print(f"{CLR_YELLOW}[WARN]{CLR_RESET} Stale lockfile terdeteksi. Mengambil alih lock...")

        current_pid = os.getpid()
        self.lock_file.write_text(str(current_pid))
        return True

    def release_lock(self):
        """Menghapus lockfile saat pipeline selesai atau terminasi crash."""
        if self.lock_file.exists():
            try:
                self.lock_file.unlink()
            except OSError:
                pass

    def add_stage(self, stage: PipelineStage):
        """Mendaftarkan stage eksekusi baru ke dalam pipeline sequence."""
        self.stages.append(stage)

    def _execute_bash_subshell(self, stage: PipelineStage) -> StageResult:
        """
        Mengeksekusi skrip Bash di subshell terisolasi dengan defensive bash flags:
        -e: Keluar jika perintah mengembalikan non-zero status
        -u: Treat unset variables as errors
        -o pipefail: Mencegah error tertutup saat menggunakan pipelining (|)
        """
        # Standar enterprise defensif wrapper
        wrapped_script = f"set -euo pipefail\n{stage.bash_script}"
        
        env = os.environ.copy()
        env.update(stage.custom_env)
        env["PIPELINE_EXEC_TIMESTAMP"] = str(int(time.time()))

        start_time = time.perf_counter()
        
        # Eksekusi POSIX Bash
        proc = subprocess.Popen(
            ["/bin/bash", "-c", wrapped_script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env
        )

        stdout, stderr = proc.communicate()
        duration = time.perf_counter() - start_time
        is_success = (proc.returncode == 0)

        return StageResult(
            name=stage.name,
            exit_code=proc.returncode,
            duration_sec=duration,
            stdout=stdout.strip(),
            stderr=stderr.strip(),
            is_success=is_success
        )

    def run(self) -> bool:
        """
        Menjalankan seluruh sequence stage secara berurutan dan menghentikan 
        pipeline jika terjadi failure pada critical stage.
        """
        print(f"\n{CLR_BOLD}{CLR_BLUE}=== Memulai CI/CD Pipeline: {self.pipeline_name} ==={CLR_RESET}")
        
        if not self.acquire_lock():
            return False

        pipeline_passed = True
        try:
            for idx, stage in enumerate(self.stages, 1):
                print(f"\n{CLR_CYAN}[{idx}/{len(self.stages)}] Menjalankan Stage: {CLR_BOLD}{stage.name}{CLR_RESET}")
                result = self._execute_bash_subshell(stage)
                self.results.append(result)

                if result.is_success:
                    print(f"  {CLR_GREEN}✓ Status:{CLR_RESET} SUCCESS (Exit Code: 0, Durasi: {result.duration_sec:.2f}s)")
                    if result.stdout:
                        for line in result.stdout.splitlines():
                            print(f"    {CLR_GRAY}│{CLR_RESET} {line}")
                else:
                    print(f"  {CLR_RED}✗ Status:{CLR_RESET} FAILED (Exit Code: {result.exit_code}, Durasi: {result.duration_sec:.2f}s)")
                    if result.stderr:
                        for line in result.stderr.splitlines():
                            print(f"    {CLR_RED}│ [STDERR]{CLR_RESET} {line}")
                    if result.stdout:
                        for line in result.stdout.splitlines():
                            print(f"    {CLR_GRAY}│ [STDOUT]{CLR_RESET} {line}")

                    if not stage.allow_failure:
                        print(f"\n{CLR_RED}[CRITICAL]{CLR_RESET} Pipeline dihentikan paksa karena stage '{stage.name}' gagal.")
                        pipeline_passed = False
                        break
                    else:
                        print(f"  {CLR_YELLOW}! Notice:{CLR_RESET} Failure diabaikan (allow_failure=True).")

        finally:
            self.release_lock()

        self._print_summary(pipeline_passed)
        return pipeline_passed

    def _print_summary(self, passed: bool):
        """Mencetak metrik performa eksekusi dan tabel audit enterprise."""
        print(f"\n{CLR_BOLD}{CLR_BLUE}=== Pipeline Audit Report ==={CLR_RESET}")
        total_time = sum(r.duration_sec for r in self.results)
        
        for r in self.results:
            status = f"{CLR_GREEN}PASS{CLR_RESET}" if r.is_success else f"{CLR_RED}FAIL{CLR_RESET}"
            print(f"  [{status}] {r.name:<35} | Exit: {r.exit_code:<3} | {r.duration_sec:.3f}s")

        status_text = f"{CLR_GREEN}SUCCEEDED{CLR_RESET}" if passed else f"{CLR_RED}FAILED{CLR_RESET}"
        print(f"\nHasil Akhir: {CLR_BOLD}{status_text}{CLR_RESET}")
        print(f"Total Waktu Eksekusi: {CLR_BOLD}{total_time:.3f}s{CLR_RESET}\n")


def build_artifact_verifier(workspace_dir: str) -> str:
    """Helper untuk memverifikasi integritas checksum SHA-256 dari rilis."""
    target = pathlib.Path(workspace_dir) / "release.tar.gz"
    if target.exists():
        hasher = hashlib.sha256()
        with open(target, "rb") as f:
            while chunk := f.read(4096):
                hasher.update(chunk)
        return hasher.hexdigest()
    return "NONE"


def main():
    # Direktori kerja sandbox untuk simulasi build CI/CD
    workspace = tempfile.mkdtemp(prefix="lab_enterprise_pipeline_")
    engine = EnterpriseAutomationEngine(pipeline_name="production-deploy-job")

    # STAGE 1: Audit Lingkungan Host
    engine.add_stage(PipelineStage(
        name="1. Infrastructure & OS Audit",
        bash_script="""
            echo "Host: $(uname -s -m)"
            echo "Current User ID: $(id -u)"
            echo "Bash Version: ${BASH_VERSION}"
            echo "Memori Tersedia: $(free -m 2>/dev/null | awk '/Mem:/ {print $7 " MB"}' || echo 'N/A')"
        """
    ))

    # STAGE 2: Sanitasi Workspace & Pengujian Dependensi
    engine.add_stage(PipelineStage(
        name="2. Workspace Sanitization & Linting",
        bash_script=f"""
            WORK_DIR="{workspace}"
            mkdir -p "$WORK_DIR/src" "$WORK_DIR/dist"
            
            # Simulasi generate modul kode
            cat << 'EOF' > "$WORK_DIR/src/app_service.sh"
#!/usr/bin/env bash
run_daemon() {{
    echo "[DAEMON] Core transaction service aktif."
}}
EOF
            chmod +x "$WORK_DIR/src/app_service.sh"
            echo "Files generated di: $WORK_DIR/src"
            ls -la "$WORK_DIR/src" | awk 'NR>1 {{print $1, $9}}'
        """
    ))

    # STAGE 3: Build & Automated Unit/Integration Testing
    engine.add_stage(PipelineStage(
        name="3. Test Execution & Assertion",
        bash_script=f"""
            WORK_DIR="{workspace}"
            source "$WORK_DIR/src/app_service.sh"
            
            # Unit test assertion: verifikasi output fungsi
            TEST_OUT=$(run_daemon)
            EXPECTED="[DAEMON] Core transaction service aktif."
            
            if [ "$TEST_OUT" != "$EXPECTED" ]; then
                echo "Assertion failed! Diperoleh: '$TEST_OUT'" >&2
                exit 1
            fi
            echo "Assertion passed: Service daemon mengembalikan output yang valid."
        """
    ))

    # STAGE 4: Enterprise Packaging & Cryptographic Checksum
    engine.add_stage(PipelineStage(
        name="4. Artifact Packaging & Checksumming",
        bash_script=f"""
            WORK_DIR="{workspace}"
            cd "$WORK_DIR"
            tar -czf "$WORK_DIR/dist/release.tar.gz" -C "$WORK_DIR/src" .
            
            # Hitung SHA-256 langsung via utilitas coreutils
            sha256sum "$WORK_DIR/dist/release.tar.gz" | awk '{{print "Generated Checksum: " $1}}'
            echo "Artifact Size: $(wc -c < "$WORK_DIR/dist/release.tar.gz") bytes"
        """
    ))

    # STAGE 5: Simulasi Deployment & Idempotency Health-Check
    engine.add_stage(PipelineStage(
        name="5. Simulated Blue/Green Deployment",
        bash_script=f"""
            WORK_DIR="{workspace}"
            DEPLOY_TARGET="$WORK_DIR/deploy_active"
            mkdir -p "$DEPLOY_TARGET"
            
            # Ekstraksi release payload
            tar -xzf "$WORK_DIR/dist/release.tar.gz" -C "$DEPLOY_TARGET"
            
            # Health check simulasi
            if [ -f "$DEPLOY_TARGET/app_service.sh" ]; then
                echo "Health-check OK: Service binary terpasang dan executable."
            else
                echo "Health-check Failed: Binary rilis tidak ditemukan!" >&2
                exit 2
            fi
        """
    ))

    # Eksekusi pipeline
    success = engine.run()

    # Post-run cleanup and verification
    artifact_hash = build_artifact_verifier(f"{workspace}/dist")
    print(f"{CLR_BOLD}[VERIFIKASI INTEGRITAS RUNTIME]{CLR_RESET}")
    print(f"Workspace Path  : {workspace}")
    print(f"Artifact SHA-256: {artifact_hash}")

    # Cleanup temporary workspace
    subprocess.run(["rm", "-rf", workspace], check=False)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()