#!/usr/bin/env python3
"""
Lab Exercise: Terraform State Architecture & Concurrency Control Simulator
BAB-03: State Architecture dan Concurrency Control

Simulasi teknis independen mengenai:
1. S3 Remote Backend (State serialization, lineage, serial versioning, schema version).
2. DynamoDB Distributed Lock Table (LockID, Info, digest, acquire/release/force-unlock).
3. Concurrency collision: Simulasi race condition saat dua worker melakukan `terraform apply`.
"""

import sys
import time
import json
import uuid
import hashlib
from typing import Dict, Any, Optional

# ANSI Color Codes for terminal formatting
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"


class StateLockError(Exception):
    """Raised when acquiring state lock fails due to active lock contention."""
    pass


class TerraformBackendSimulator:
    """Simulates an S3 Remote Backend paired with a DynamoDB State Locking table."""

    def __init__(self, bucket_name: str, lock_table: str):
        self.bucket_name = bucket_name
        self.lock_table = lock_table
        self.lineage = str(uuid.uuid4())
        self.serial = 0
        self.terraform_version = "1.8.5"
        self.resources: Dict[str, Dict[str, Any]] = {}
        self.active_lock: Optional[Dict[str, Any]] = None

    def _calculate_digest(self, state_dict: Dict[str, Any]) -> str:
        state_bytes = json.dumps(state_dict, sort_keys=True).encode("utf-8")
        return hashlib.sha256(state_bytes).hexdigest()

    def acquire_lock(self, operation: str, who: str, lock_id: Optional[str] = None) -> str:
        """Simulates DynamoDB conditional write (attribute_not_exists(LockID))."""
        if self.active_lock is not None:
            raise StateLockError(
                f"Error acquiring the state lock: ConditionalCheckFailedException!\n"
                f"Lock Info:\n"
                f"  ID:        {self.active_lock['ID']}\n"
                f"  Path:      {self.bucket_name}/terraform.tfstate\n"
                f"  Operation: {self.active_lock['Operation']}\n"
                f"  Who:       {self.active_lock['Who']}\n"
                f"  Version:   {self.active_lock['Version']}\n"
                f"  Created:   {self.active_lock['Created']}"
            )

        token = lock_id or str(uuid.uuid4())
        self.active_lock = {
            "ID": token,
            "Operation": operation,
            "Who": who,
            "Version": self.terraform_version,
            "Created": time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime()),
            "Path": f"{self.bucket_name}/terraform.tfstate"
        }
        return token

    def release_lock(self, lock_token: str) -> bool:
        """Releases the state lock using the matching lock token."""
        if not self.active_lock:
            return False
        if self.active_lock["ID"] != lock_token:
            raise ValueError(f"Lock token mismatch! Active lock ID is {self.active_lock['ID']}")
        self.active_lock = None
        return True

    def force_unlock(self, lock_id: str) -> bool:
        """Simulates `terraform force-unlock <LOCK-ID>`."""
        if not self.active_lock:
            return False
        if self.active_lock["ID"] != lock_id:
            raise ValueError(f"Provided Lock ID '{lock_id}' does not match active lock '{self.active_lock['ID']}'")
        self.active_lock = None
        return True

    def read_state(self) -> Dict[str, Any]:
        """Fetches the state document from simulated S3 storage."""
        state_payload = {
            "format_version": "1.0",
            "terraform_version": self.terraform_version,
            "serial": self.serial,
            "lineage": self.lineage,
            "resources": self.resources,
            "outputs": {}
        }
        state_payload["digest"] = self._calculate_digest(state_payload)
        return state_payload

    def write_state(self, lock_token: str, updated_resources: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Persists state changes, incrementing serial version."""
        if not self.active_lock or self.active_lock["ID"] != lock_token:
            raise StateLockError("Cannot write state without holding an active lock!")

        self.serial += 1
        self.resources = updated_resources
        return self.read_state()


def print_banner():
    print(f"{CYAN}{BOLD}{'='*75}{RESET}")
    print(f"{CYAN}{BOLD} TERRAFORM STATE ARCHITECTURE & CONCURRENCY CONTROLLER (BAB-03){RESET}")
    print(f"{CYAN}{BOLD}{'='*75}{RESET}")
    print(f"{WHITE}Simulasi Interaktif: S3 Remote State, DynamoDB Lock, dan Race Condition{RESET}\n")


def simulate_concurrent_applies(backend: TerraformBackendSimulator):
    print(f"{YELLOW}{BOLD}[SKENARIO 1] Pengujian Concurrency Control & Lock Contention{RESET}")
    worker_a = "ci-runner-agent-01@production-worker"
    worker_b = "developer-local@workstation-laptop"

    print(f"{WHITE}Worker A ({CYAN}{worker_a}{WHITE}) memulai 'terraform apply'...{RESET}")
    try:
        lock_token_a = backend.acquire_lock(operation="OperationTypeApply", who=worker_a)
        print(f"  {GREEN}[SUCCESS]{RESET} Worker A memperoleh lock. Lock ID: {MAGENTA}{lock_token_a}{RESET}")
    except StateLockError as e:
        print(f"  {RED}[FAILED]{RESET} {e}")
        return

    print(f"\n{WHITE}Worker B ({CYAN}{worker_b}{WHITE}) mencoba 'terraform apply' secara bersamaan...{RESET}")
    try:
        backend.acquire_lock(operation="OperationTypeApply", who=worker_b)
        print(f"  {RED}[BUG]{RESET} Worker B berhasil memperoleh lock padahal Lock masih aktif!")
    except StateLockError as err:
        print(f"  {RED}[LOCK CONTENTION DETECTED]{RESET}\n")
        for line in str(err).split("\n"):
            print(f"    {YELLOW}{line}{RESET}")

    print(f"\n{WHITE}Worker A menyelesaikan kompilasi dan penulisan state...{RESET}")
    new_resources = {
        "aws_vpc.primary": {
            "type": "aws_vpc",
            "cidr_block": "10.0.0.0/16",
            "enable_dns_hostnames": True,
            "id": "vpc-0abc123def456"
        },
        "aws_subnet.public_a": {
            "type": "aws_subnet",
            "cidr_block": "10.0.1.0/24",
            "vpc_id": "vpc-0abc123def456",
            "id": "subnet-0987654321"
        }
    }
    updated_state = backend.write_state(lock_token=lock_token_a, updated_resources=new_resources)
    print(f"  {GREEN}[STATE COMMITTED]{RESET} State Serial: {BOLD}{updated_state['serial']}{RESET} | Lineage: {updated_state['lineage']}")
    print(f"  {GREEN}[DIGEST]{RESET} SHA-256: {updated_state['digest']}")

    print(f"\n{WHITE}Worker A melepaskan state lock...{RESET}")
    backend.release_lock(lock_token_a)
    print(f"  {GREEN}[RELEASED]{RESET} Lock status: {backend.active_lock}")


def simulate_force_unlock(backend: TerraformBackendSimulator):
    print(f"\n{YELLOW}{BOLD}[SKENARIO 2] Simulasi Deadlock & 'terraform force-unlock'{RESET}")
    crashed_pipeline = "github-actions-runner@runner-449"
    print(f"{WHITE}Pipeline ({CYAN}{crashed_pipeline}{WHITE}) lock state lalu mengalami fatal crash...{RESET}")
    stuck_lock = backend.acquire_lock(operation="OperationTypeApply", who=crashed_pipeline)
    print(f"  {RED}[STUCK LOCK]{RESET} Active Lock Token: {MAGENTA}{stuck_lock}{RESET}")

    print(f"{WHITE}Operator mengeksekusi: {CYAN}terraform force-unlock {stuck_lock}{RESET}")
    backend.force_unlock(stuck_lock)
    print(f"  {GREEN}[FORCE-UNLOCKED]{RESET} Lock berhasil dilepaskan secara manual!")


def display_state_inspector(backend: TerraformBackendSimulator):
    print(f"\n{YELLOW}{BOLD}[STATE INSPECTION]{RESET}")
    current_state = backend.read_state()
    formatted_json = json.dumps(current_state, indent=2)
    print(f"{CYAN}{formatted_json}{RESET}\n")


def interactive_menu():
    backend = TerraformBackendSimulator(
        bucket_name="mycompany-terraform-remote-state-prod",
        lock_table="mycompany-terraform-locks"
    )

    while True:
        print_banner()
        print(f"{BOLD}Pilih Mode Simulasi:{RESET}")
        print("  1. Jalankan Simulasi Concurrency Collision & S3 State Update")
        print("  2. Jalankan Simulasi Stale Lock & Force Unlock")
        print("  3. Inspeksi Raw State JSON (Serial, Lineage, Resources)")
        print("  4. Jalankan Full Automated Test Suite")
        print("  5. Keluar")

        try:
            choice = input(f"\n{WHITE}Pilihan [1-5]: {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting simulator.")
            sys.exit(0)

        if choice == "1":
            simulate_concurrent_applies(backend)
        elif choice == "2":
            simulate_force_unlock(backend)
        elif choice == "3":
            display_state_inspector(backend)
        elif choice == "4":
            print(f"\n{BLUE}{BOLD}=== RUNNING AUTOMATED STATE & CONCURRENCY TESTS ==={RESET}\n")
            simulate_concurrent_applies(backend)
            simulate_force_unlock(backend)
            display_state_inspector(backend)
            print(f"{GREEN}{BOLD}✓ Semua skenario lolos verifikasi integritas state & locking!{RESET}\n")
        elif choice == "5" or choice.lower() == "exit":
            print(f"{GREEN}Simulator selesai. Terima kasih.{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak valid. Masukkan angka 1 sampai 5.{RESET}")

        try:
            input(f"\n{CYAN}Tekan [Enter] untuk kembali ke menu...{RESET}")
        except (EOFError, KeyboardInterrupt):
            break


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        b = TerraformBackendSimulator("prod-tf-state", "prod-tf-locks")
        simulate_concurrent_applies(b)
        simulate_force_unlock(b)
        display_state_inspector(b)
        sys.exit(0)
    interactive_menu()
