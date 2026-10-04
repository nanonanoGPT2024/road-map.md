#!/usr/bin/env python3
"""
Lab Exercise: Terraform State Architecture & Concurrency Control Simulation
Bab 03: State Architecture dan Concurrency Control (Remote State, S3+DynamoDB Locking, Drift, & Force-Unlock)

Fitur Simulasi:
1. S3 Remote Backend: Versioning, Server-Side Encryption (SSE-KMS), State Lineage & Serial tracking.
2. DynamoDB Concurrency Control: Distributed LockID, Lease metadata, & ConditionalCheckFailedException.
3. Race Condition Scenarios: Multi-actor concurrent apply conflict (CI/CD vs SRE).
4. State Drift Detection: Out-of-band resource tampering vs recorded terraform state refresh.
5. Disaster Recovery: State Lock Poisoning & `terraform force-unlock <LOCK-ID>`.
"""

import sys
import time
import json
import uuid
import hashlib
from typing import Dict, Any, Optional
from datetime import datetime

# ANSI Color Codes for terminal formatting
class TermColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    BG_DARK = "\033[40m"

def print_header(title: str) -> None:
    print(f"\n{TermColor.BOLD}{TermColor.CYAN}{'=' * 75}{TermColor.RESET}")
    print(f"{TermColor.BOLD}{TermColor.CYAN} [LAB] {title.upper()}{TermColor.RESET}")
    print(f"{TermColor.BOLD}{TermColor.CYAN}{'=' * 75}{TermColor.RESET}")

def print_tf_log(level: str, msg: str) -> None:
    timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    color = TermColor.GREEN if level == "INFO" else TermColor.YELLOW if level == "WARN" else TermColor.RED
    print(f"{TermColor.DIM}[{timestamp}]{TermColor.RESET} {color}{TermColor.BOLD}[{level}]{TermColor.RESET} {msg}")

class DynamoDBLockTable:
    """Simulasi tabel DynamoDB untuk Distributed Locking (e.g., terraform-locks)."""
    def __init__(self, table_name: str = "terraform-lock-table"):
        self.table_name = table_name
        self.locks: Dict[str, Dict[str, Any]] = {}

    def acquire_lock(self, lock_key: str, lock_info: Dict[str, Any]) -> bool:
        if lock_key in self.locks:
            return False  # ConditionalCheckFailedException in DynamoDB PutItem
        self.locks[lock_key] = lock_info
        return True

    def release_lock(self, lock_key: str, lock_id: str) -> bool:
        if lock_key in self.locks:
            if self.locks[lock_key].get("ID") == lock_id:
                del self.locks[lock_key]
                return True
        return False

    def force_unlock(self, lock_key: str, target_id: str) -> bool:
        if lock_key in self.locks and self.locks[lock_key].get("ID") == target_id:
            del self.locks[lock_key]
            return True
        return False

    def get_lock_info(self, lock_key: str) -> Optional[Dict[str, Any]]:
        return self.locks.get(lock_key)

class S3StateBackend:
    """Simulasi S3 Object Storage untuk state file dengan versioning dan SSE."""
    def __init__(self, bucket_name: str = "prod-terraform-state-bucket"):
        self.bucket_name = bucket_name
        self.versions: Dict[str, list] = {}
        self.kms_key_id = "arn:aws:kms:ap-southeast-1:112233445566:key/tf-state-cmk"

    def put_state(self, key: str, state_content: Dict[str, Any]) -> str:
        version_id = f"v{int(time.time() * 1000)}"
        state_json = json.dumps(state_content, indent=2)
        md5_hash = hashlib.md5(state_json.encode('utf-8')).hexdigest()
        
        record = {
            "version_id": version_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "content": state_content,
            "md5": md5_hash,
            "kms_encrypted": True
        }
        
        if key not in self.versions:
            self.versions[key] = []
        self.versions[key].append(record)
        return version_id

    def get_latest_state(self, key: str) -> Optional[Dict[str, Any]]:
        if key in self.versions and self.versions[key]:
            return self.versions[key][-1]["content"]
        return None

    def get_history(self, key: str) -> list:
        return self.versions.get(key, [])

class TerraformEngine:
    """Simulasi Core Terraform Engine: State Refresh, Lock Acquisition, Apply, Release."""
    def __init__(self, s3: S3StateBackend, ddb: DynamoDBLockTable, state_path: str):
        self.s3 = s3
        self.ddb = ddb
        self.state_path = state_path
        self.lock_key = f"{s3.bucket_name}/{state_path}-md5"

    def create_initial_state(self) -> None:
        initial_state = {
            "version": 4,
            "terraform_version": "1.8.5",
            "serial": 1,
            "lineage": str(uuid.uuid4()),
            "resources": [
                {
                    "mode": "managed",
                    "type": "aws_vpc",
                    "name": "primary",
                    "instances": [{
                        "attributes": {
                            "id": "vpc-0a1b2c3d4e5f",
                            "cidr_block": "10.0.0.0/16",
                            "enable_dns_hostnames": True,
                            "tags": {"Environment": "Production", "Owner": "Platform-Team"}
                        }
                    }]
                }
            ]
        }
        v_id = self.s3.put_state(self.state_path, initial_state)
        print_tf_log("INFO", f"State awal disimpan di S3://{self.s3.bucket_name}/{self.state_path} (VersionId: {v_id})")

    def run_apply(self, actor_name: str, op_desc: str, changes: Dict[str, Any], lock_hold_seconds: float = 2.0) -> bool:
        lock_id = str(uuid.uuid4())
        lock_info = {
            "ID": lock_id,
            "Operation": op_desc,
            "Who": actor_name,
            "Version": "1.8.5",
            "Created": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "Path": f"{self.s3.bucket_name}/{self.state_path}"
        }

        print_tf_log("INFO", f"[{actor_name}] Menginisiasi 'terraform apply'...")
        print_tf_log("INFO", f"[{actor_name}] Mencoba mengakuisisi state lock di DynamoDB...")
        
        # Concurrency check
        acquired = self.ddb.acquire_lock(self.lock_key, lock_info)
        if not acquired:
            existing = self.ddb.get_lock_info(self.lock_key) or {}
            print(f"\n{TermColor.BOLD}{TermColor.RED}Error: Error acquiring the state lock{TermColor.RESET}")
            print(f"{TermColor.RED}Error message: ConditionalCheckFailedException: The conditional request failed.{TermColor.RESET}")
            print(f"{TermColor.YELLOW}Lock Info:{TermColor.RESET}")
            print(f"  ID:        {existing.get('ID')}")
            print(f"  Path:      {existing.get('Path')}")
            print(f"  Operation: {existing.get('Operation')}")
            print(f"  Who:       {existing.get('Who')}")
            print(f"  Created:   {existing.get('Created')}\n")
            print_tf_log("WARN", f"[{actor_name}] Apply DIBATALKAN untuk mencegah state race-condition/corruption.")
            return False

        print(f"{TermColor.GREEN}[{actor_name}] State lock BERHASIL diakuisisi! (Lock ID: {lock_id}){TermColor.RESET}")
        
        try:
            current_state = self.s3.get_latest_state(self.state_path)
            new_serial = current_state["serial"] + 1 if current_state else 1
            print_tf_log("INFO", f"[{actor_name}] Mengunduh remote state (Serial: {current_state['serial']})...")
            print_tf_log("INFO", f"[{actor_name}] Melakukan eksekusi infrastruktur ({op_desc})...")
            time.sleep(lock_hold_seconds)

            # Apply state mutation
            updated_state = json.loads(json.dumps(current_state))
            updated_state["serial"] = new_serial
            for res in updated_state["resources"]:
                if res["type"] == "aws_vpc":
                    res["instances"][0]["attributes"]["tags"].update(changes)

            v_id = self.s3.put_state(self.state_path, updated_state)
            print(f"{TermColor.GREEN}[{actor_name}] State baru berhasil disimpan ke S3! Serial: {new_serial} (VersionId: {v_id}){TermColor.RESET}")
            return True
        finally:
            print_tf_log("INFO", f"[{actor_name}] Melepaskan state lock di DynamoDB...")
            self.ddb.release_lock(self.lock_key, lock_id)
            print(f"{TermColor.CYAN}[{actor_name}] Lock {lock_id} telah dirilis secara aman.{TermColor.RESET}")

def run_concurrency_simulation(engine: TerraformEngine) -> None:
    print_header("Skenario 1: Concurrency Conflict (CI/CD vs SRE Apply Bersamaan)")
    print(f"{TermColor.BOLD}Simulasi:{TermColor.RESET} Pipeline CI/CD menjalankan apply panjang, sementara SRE menjalankan hotfix apply lokal.\n")

    # Lock intentionally held by Actor 1
    actor1_lock_id = str(uuid.uuid4())
    lock_data = {
        "ID": actor1_lock_id,
        "Operation": "OperationTypeApply",
        "Who": "gitlab-runner-prod-01@runner.internal",
        "Version": "1.8.5",
        "Created": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "Path": engine.lock_key
    }
    engine.ddb.acquire_lock(engine.lock_key, lock_data)
    print_tf_log("INFO", "[CI/CD Pipeline] Telah mengakuisisi lock untuk provisioning 12 RDS replica...")

    # Actor 2 attempts apply
    engine.run_apply(
        actor_name="SRE-Lokal (Budi)",
        op_desc="Quick Security Group Patch",
        changes={"Hotfix": "SecGroup-Patch"},
        lock_hold_seconds=0.5
    )

    # Actor 1 completes
    engine.ddb.release_lock(engine.lock_key, actor1_lock_id)
    print_tf_log("INFO", "[CI/CD Pipeline] Selesai menerapkan perubahan dan melepaskan lock.")

def run_drift_simulation(engine: TerraformEngine) -> None:
    print_header("Skenario 2: State Drift Detection & Reconciliation")
    current_state = engine.s3.get_latest_state(engine.state_path)
    recorded_tags = current_state["resources"][0]["instances"][0]["attributes"]["tags"]
    
    print(f"State S3 Tersimpan Saat Ini (Serial: {current_state['serial']}):")
    print(f"  VPC Tags: {json.dumps(recorded_tags)}")

    # Simulasi Out-Of-Band modification via AWS Console
    real_world_tags = dict(recorded_tags)
    real_world_tags["Environment"] = "Staging-Modified-Via-Console"
    real_world_tags["UnmanagedTag"] = "ManualBypass"

    print(f"\n{TermColor.BOLD}{TermColor.YELLOW}[AWS Cloud Real World]{TermColor.RESET} Seseorang mengubah tag langsung di AWS Console:")
    print(f"  Real AWS VPC Tags: {json.dumps(real_world_tags)}")

    print(f"\n{TermColor.BOLD}{TermColor.CYAN}Menjalankan: 'terraform plan -refresh-only'{TermColor.RESET}")
    print(f"~ update in-place (Drift Detected!)")
    print(f"  ~ tags = {{")
    print(f"    {TermColor.RED}- Environment  = \"Production\"{TermColor.RESET}")
    print(f"    {TermColor.GREEN}+ Environment  = \"Staging-Modified-Via-Console\"{TermColor.RESET}")
    print(f"    {TermColor.GREEN}+ UnmanagedTag = \"ManualBypass\"{TermColor.RESET}")
    print(f"  }}")
    print_tf_log("WARN", "Drift terdeteksi antara physical cloud reality dan recorded remote state.")

def run_force_unlock_simulation(engine: TerraformEngine) -> None:
    print_header("Skenario 3: Zombie Lock Recovery (Force-Unlock)")
    poisoned_lock_id = "deadbeef-c001-49b8-a721-0123456789ab"
    engine.ddb.acquire_lock(engine.lock_key, {
        "ID": poisoned_lock_id,
        "Operation": "OperationTypeApply (Orphaned / CI Job OOMKilled)",
        "Who": "jenkins-agent-node-04 (TERMINATED)",
        "Version": "1.8.5",
        "Created": "2026-10-05T01:15:00Z",
        "Path": engine.lock_key
    })

    print_tf_log("WARN", f"DynamoDB terkunci oleh job yang mati (Zombie Lock ID: {poisoned_lock_id})")
    print("Mencoba eksekusi normal:")
    engine.run_apply("Lead-SRE", "Deploy Service", {}, lock_hold_seconds=0.1)

    print(f"\n{TermColor.BOLD}{TermColor.MAGENTA}Solusi Operasional:{TermColor.RESET}")
    print(f"$ terraform force-unlock {poisoned_lock_id}")
    time.sleep(0.5)
    
    success = engine.ddb.force_unlock(engine.lock_key, poisoned_lock_id)
    if success:
        print(f"{TermColor.BOLD}{TermColor.GREEN}Local and remote state locks successfully released.{TermColor.RESET}")
        print_tf_log("INFO", "Kunci berhasil dibongkar paksa. Sistem kembali dapat menerima apply.")
    else:
        print(f"{TermColor.RED}Gagal melakukan force-unlock.{TermColor.RESET}")

def display_interactive_menu() -> None:
    s3 = S3StateBackend()
    ddb = DynamoDBLockTable()
    engine = TerraformEngine(s3, ddb, "env/production/terraform.tfstate")
    engine.create_initial_state()

    # If running non-interactively or in automated test, run all demos
    if not sys.stdin.isatty():
        print(f"\n{TermColor.YELLOW}Deteksi mode non-interaktif. Menjalankan seluruh sekuens lab otomatis...{TermColor.RESET}")
        run_concurrency_simulation(engine)
        run_drift_simulation(engine)
        run_force_unlock_simulation(engine)
        print_header("Simulasi Selesai dengan Sukses")
        return

    while True:
        print(f"\n{TermColor.BOLD}{TermColor.BLUE}=== LAB MENU: TERRAFORM STATE ARCHITECTURE ==={TermColor.RESET}")
        print("1. Simulasi Concurrency Conflict (Multi-actor Lock Contention)")
        print("2. Simulasi State Drift Detection & Refresh Plan")
        print("3. Simulasi Zombie Lock & 'terraform force-unlock'")
        print("4. Jalankan Semua Skenario Sekaligus")
        print("5. Keluar")
        
        try:
            choice = input(f"\n{TermColor.BOLD}Pilih opsi [1-5]: {TermColor.RESET}").strip()
            if choice == "1":
                run_concurrency_simulation(engine)
            elif choice == "2":
                run_drift_simulation(engine)
            elif choice == "3":
                run_force_unlock_simulation(engine)
            elif choice == "4":
                run_concurrency_simulation(engine)
                run_drift_simulation(engine)
                run_force_unlock_simulation(engine)
            elif choice == "5":
                print(f"{TermColor.GREEN}Terima kasih telah menjalankan Lab State Architecture!{TermColor.RESET}")
                break
            else:
                print(f"{TermColor.RED}Pilihan tidak valid. Silakan pilih 1-5.{TermColor.RESET}")
        except (KeyboardInterrupt, EOFError):
            print("\nKeluar dari simulasi.")
            break

if __name__ == "__main__":
    display_interactive_menu()
