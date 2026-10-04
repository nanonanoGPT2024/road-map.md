#!/usr/bin/env python3
"""
Enterprise GitOps & CI/CD Pipeline Simulator for Terraform
Standard Kurikulum GEMINI.md - Bab 08: Production GitOps & CI/CD Automation

Deskripsi:
Skrip mandiri ini mensimulasikan fungsionalitas PR-driven GitOps (seperti Atlantis/Spacelift),
termasuk Speculative Plans, Concurrency Locking, Role-Based Approval Gates, dan Drift Detection.
"""

import sys
import json
import time
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# ANSI Escape Colors for Enterprise Terminal Output
CLR_RESET = "\033[0m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_CYAN = "\033[96m"
CLR_BOLD = "\033[1m"

def log_info(msg: str):
    print(f"{CLR_BLUE}[INFO]{CLR_RESET} {msg}")

def log_success(msg: str):
    print(f"{CLR_GREEN}[SUCCESS]{CLR_RESET} {msg}")

def log_warn(msg: str):
    print(f"{CLR_YELLOW}[WARN]{CLR_RESET} {msg}")

def log_error(msg: str):
    print(f"{CLR_RED}[ERROR]{CLR_RESET} {msg}")

def log_pipeline(step: str, msg: str):
    print(f"{CLR_CYAN}[PIPELINE :: {step.upper()}]{CLR_RESET} {msg}")


@dataclass
class LockMetadata:
    pr_number: int
    environment: str
    locked_by: str
    timestamp: float


class GitOpsEngine:
    def __init__(self):
        # In-memory storage simulating external state & locks
        self.locks: Dict[str, LockMetadata] = {}
        
        # Simulating Cloud Infrastructure Live State vs Remote State
        self.simulated_remote_state = {
            "staging": {
                "aws_vpc.main": {"cidr": "10.0.0.0/16", "enable_dns": True},
                "aws_security_group.web": {"ingress_port": 443, "cidr": "0.0.0.0/0"}
            },
            "production": {
                "aws_vpc.prod": {"cidr": "172.16.0.0/16", "enable_dns": True},
                "aws_rds_cluster.aurora": {"instance_class": "db.r6g.xlarge", "multi_az": True}
            }
        }
        
        # Live infrastructure (can drift out-of-band)
        self.simulated_live_cloud = {
            "staging": {
                "aws_vpc.main": {"cidr": "10.0.0.0/16", "enable_dns": True},
                "aws_security_group.web": {"ingress_port": 443, "cidr": "0.0.0.0/0"}
            },
            "production": {
                "aws_vpc.prod": {"cidr": "172.16.0.0/16", "enable_dns": True},
                # DRIFT: Someone manually modified the RDS instance in AWS Console!
                "aws_rds_cluster.aurora": {"instance_class": "db.t4g.medium", "multi_az": False}
            }
        }

        # RBAC Matrix configuration
        self.user_roles = {
            "alice_dev": "Junior-Developer",
            "bob_sre": "Lead-SRE",
            "charlie_audit": "Security-Auditor"
        }

    # ==========================================
    # 1. CONCURRENCY & LOCK MANAGEMENT
    # ==========================================
    def acquire_lock(self, env: str, pr_number: int, user: str) -> bool:
        if env in self.locks:
            current_lock = self.locks[env]
            if current_lock.pr_number == pr_number:
                log_info(f"Workspace [{env}] already locked by this PR #{pr_number}. Re-using lock.")
                return True
            else:
                log_error(f"LOCK REJECTED: Environment [{env}] sedang terkunci oleh PR #{current_lock.pr_number} "
                          f"oleh user '{current_lock.locked_by}'!")
                return False
        
        self.locks[env] = LockMetadata(
            pr_number=pr_number,
            environment=env,
            locked_by=user,
            timestamp=time.time()
        )
        log_success(f"Workspace Lock ACQUIRED untuk environment [{env}] oleh PR #{pr_number} ({user}).")
        return True

    def release_lock(self, env: str, pr_number: int) -> bool:
        if env in self.locks:
            if self.locks[env].pr_number == pr_number:
                del self.locks[env]
                log_info(f"Workspace Lock RELEASED untuk environment [{env}].")
                return True
            else:
                log_warn(f"PR #{pr_number} tidak dapat melepaskan lock milik PR #{self.locks[env].pr_number}!")
                return False
        return True

    # ==========================================
    # 2. SPECULATIVE PLAN EXECUTION
    # ==========================================
    def run_speculative_plan(self, pr_number: int, env: str, user: str, proposed_changes: dict):
        log_pipeline("PLAN", f"Memulai Speculative Plan pada PR #{pr_number} (Target: {env}) oleh {user}...")
        
        if not self.acquire_lock(env, pr_number, user):
            log_error("Pipeline dibatalkan karena kegagalan akuisisi lock.")
            return None

        time.sleep(1) # Simulasi kalkulasi diff
        print("\n" + "="*60)
        print(f"TERRAFORM SPECULATIVE PLAN RESULT - PR #{pr_number} [ENV: {env.upper()}]")
        print("="*60)
        
        adds = proposed_changes.get("add", 0)
        changes = proposed_changes.get("change", 0)
        destroys = proposed_changes.get("destroy", 0)

        for item in proposed_changes.get("details", []):
            print(f"  {item}")

        print("-"*60)
        print(f"Plan: {CLR_GREEN}{adds} to add{CLR_RESET}, "
              f"{CLR_YELLOW}{changes} to change{CLR_RESET}, "
              f"{CLR_RED}{destroys} to destroy{CLR_RESET}.")
        print("="*60 + "\n")

        # Guardrail Check
        if env == "production" and destroys > 0:
            log_warn("GUARDRAIL ALERT: Terdeteksi operasi DESTROY pada Production!")
            log_warn("Kebijakan mensyaratkan approval eksplisit dari role 'Lead-SRE' sebelum apply.")

        # Buat dummy plan artifact file
        plan_artifact = f"/tmp/tfplan-{env}-pr{pr_number}.bin"
        with open(plan_artifact, "w") as f:
            f.write(json.dumps(proposed_changes))
        log_success(f"Speculative plan binary berhasil di-archive ke temporary storage: {plan_artifact}")
        return plan_artifact

    # ==========================================
    # 3. ROLE-BASED APPROVAL GATE & REAL APPLY
    # ==========================================
    def run_real_apply(self, pr_number: int, env: str, user: str, plan_artifact: str):
        log_pipeline("APPLY", f"Mengevaluasi izin Real Apply untuk PR #{pr_number} pada [{env}]...")

        if not os.path.exists(plan_artifact):
            log_error(f"Plan artifact {plan_artifact} tidak ditemukan! Real Apply dibatalkan.")
            return False

        with open(plan_artifact, "r") as f:
            changes = json.load(f)

        destroys = changes.get("destroy", 0)
        user_role = self.user_roles.get(user, "Unknown")

        # Enterprise Approval Gate Logic
        log_info(f"Otentikasi Actor: '{user}' | Role: '{user_role}'")
        
        if env == "production":
            if user_role != "Lead-SRE":
                log_error(f"PERMISSION DENIED: Role '{user_role}' TIDAK diizinkan melakukan apply ke PRODUCTION!")
                log_error("Apply ditolak. Diperlukan review dan eksekusi dari role 'Lead-SRE'.")
                return False
            if destroys > 0 and user_role != "Lead-SRE":
                log_error("DESTRUCTION BLOCKED: Hanya Lead-SRE yang dapat menghapus resource produksi!")
                return False
        
        log_pipeline("APPLY", "Verifikasi OIDC Credentials Token berhasil. Menjalankan 'terraform apply'...")
        time.sleep(1.5)

        # Update simulated state
        log_success(f"Infrastruktur [{env}] BERHASIL dimutasi secara deterministik.")
        log_info(f"Remote State file di cloud backend telah diperbarui.")

        # Bersihkan plan artifact & lock
        os.remove(plan_artifact)
        self.release_lock(env, pr_number)
        return True

    # ==========================================
    # 4. DRIFT DETECTION ENGINE
    # ==========================================
    def run_drift_cron(self, env: str) -> int:
        log_pipeline("DRIFT-SCAN", f"Menjalankan scheduled drift cron untuk environment [{env}]...")
        time.sleep(1)

        remote_state = self.simulated_remote_state.get(env, {})
        live_cloud = self.simulated_live_cloud.get(env, {})

        drift_detected = False
        drift_details = []

        for resource, attributes in remote_state.items():
            if resource not in live_cloud:
                drift_detected = True
                drift_details.append(f"Resource {resource} hilang di live cloud provider!")
            else:
                live_attrs = live_cloud[resource]
                for k, v in attributes.items():
                    if live_attrs.get(k) != v:
                        drift_detected = True
                        drift_details.append(
                            f"Resource [{resource}] Atribut '{k}' DRIFTED: "
                            f"Expected='{v}', Actual='{live_attrs.get(k)}'"
                        )

        if drift_detected:
            log_error(f"DRIFT ALERT: Deviasi infrastruktur terdeteksi pada [{env}]!")
            for diff in drift_details:
                print(f"  {CLR_RED}! {diff}{CLR_RESET}")
            print(f"{CLR_BOLD}Detailed Exit Code: 2 (Changes Present){CLR_RESET}\n")
            return 2
        else:
            log_success(f"Environment [{env}] SEHAT: State 100% sinkron dengan cloud riil.")
            print(f"{CLR_BOLD}Detailed Exit Code: 0 (No Changes){CLR_RESET}\n")
            return 0


# ==========================================
# SIMULATION WORKFLOW EXECUTION
# ==========================================
def main():
    print(f"{CLR_BOLD}{CLR_CYAN}=== ENTERPRISE GITOPS & CI/CD AUTOMATION SIMULATOR ==={CLR_RESET}\n")
    engine = GitOpsEngine()

    # Skenario 1: Developer biasa membuka PR dan meminta Speculative Plan
    print(f"\n{CLR_BOLD}--- SKENARIO 1: Pull Request Speculative Plan (Staging) ---{CLR_RESET}")
    staging_changes = {
        "add": 1,
        "change": 1,
        "destroy": 0,
        "details": [
            "+ resource 'aws_security_group_rule' 'allow_http' { port = 80 }",
            "~ resource 'aws_security_group' 'web' { ingress_port: 443 -> 443, 80 }"
        ]
    }
    plan_stg = engine.run_speculative_plan(
        pr_number=101,
        env="staging",
        user="alice_dev",
        proposed_changes=staging_changes
    )

    # Skenario 2: Konkurensi - Developer lain mencoba plan pada workspace yang sama
    print(f"\n{CLR_BOLD}--- SKENARIO 2: Concurrency Collision Lock Test ---{CLR_RESET}")
    engine.run_speculative_plan(
        pr_number=102,
        env="staging",
        user="bob_sre",
        proposed_changes={"add": 2, "change": 0, "destroy": 0, "details": []}
    )

    # Skenario 3: Developer menerapkan (Apply) ke Staging
    print(f"\n{CLR_BOLD}--- SKENARIO 3: Real Apply pada Staging ---{CLR_RESET}")
    if plan_stg:
        engine.run_real_apply(
            pr_number=101,
            env="staging",
            user="alice_dev",
            plan_artifact=plan_stg
        )

    # Skenario 4: Role-Based Approval Gate Violation di Production
    print(f"\n{CLR_BOLD}--- SKENARIO 4: RBAC Violation di Production ---{CLR_RESET}")
    prod_changes = {
        "add": 0,
        "change": 1,
        "destroy": 1,
        "details": [
            "- resource 'aws_rds_cluster.aurora' { destroy old instance }",
            "+ resource 'aws_rds_cluster.aurora' { create replacement }"
        ]
    }
    plan_prod = engine.run_speculative_plan(
        pr_number=105,
        env="production",
        user="alice_dev",
        proposed_changes=prod_changes
    )

    if plan_prod:
        # Developer biasa mencoba apply ke production (harus ditolak)
        engine.run_real_apply(
            pr_number=105,
            env="production",
            user="alice_dev",
            plan_artifact=plan_prod
        )

        # Sekarang Lead-SRE menyetujui dan mengeksekusi apply
        print(f"\n{CLR_BOLD}--- SKENARIO 5: SRE Approved Real Apply di Production ---{CLR_RESET}")
        engine.run_real_apply(
            pr_number=105,
            env="production",
            user="bob_sre",
            plan_artifact=plan_prod
        )

    # Skenario 6: Drift Detection Cron
    print(f"\n{CLR_BOLD}--- SKENARIO 6: Scheduled Drift Detection Pipeline (Cron) ---{CLR_RESET}")
    code_staging = engine.run_drift_cron("staging")
    code_prod = engine.run_drift_cron("production")

    print(f"\n{CLR_BOLD}Hasil Simulasi Exit Code:{CLR_RESET}")
    print(f"Staging Exit Code   : {code_staging} (Clean)")
    print(f"Production Exit Code: {code_prod} (Drift Detected!)")
    
    if code_prod == 2:
        log_warn("Tindakan Otomatis: Membuat GitHub Issue alert & mengirim payload ke Slack Webhook SRE!")

if __name__ == "__main__":
    main()