#!/usr/bin/env python3
"""
Lab Exercise M02: Simulasi GitOps Reconciliation Loop & IaC Drift Detection Engine
Modul: BAB-08-Otomasi-Infrastructure-as-Code-GitOps-Engineering
Tingkat: SRE Production Architecture

Script ini merefleksikan arsitektur GitOps controller (mirip ArgoCD/Flux)
dan IaC state management (mirip Terraform state & OPA Guardrails) dalam
lingkungan multi-tier production SRE.
"""

import sys
import time
import json
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

# --- ANSI Color Codes untuk Terminal Output ---
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
    BG_DARK = "\033[40m"


class HealthState(Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    DRIFTED = "DRIFTED"
    SYNCING = "SYNCING"


class SyncStatus(Enum):
    SYNCED = "SYNCED"
    OUT_OF_SYNC = "OUT_OF_SYNC"
    POLICY_VIOLATION = "POLICY_VIOLATION"


@dataclass
class IaCResource:
    name: str
    kind: str
    desired_spec: Dict[str, any]
    live_spec: Dict[str, any]
    state_lock: bool = False
    drift: bool = False

    def check_drift(self) -> bool:
        self.drift = self.desired_spec != self.live_spec
        return self.drift


@dataclass
class GitOpsApplication:
    name: str
    target_revision: str
    synced_revision: str
    health: HealthState = HealthState.HEALTHY
    sync_status: SyncStatus = SyncStatus.SYNCED
    resources: List[IaCResource] = field(default_factory=list)
    canary_weight: int = 100


class GitOpsSREEngine:
    def __init__(self):
        self.app = GitOpsApplication(
            name="checkout-payment-svc",
            target_revision="git-commit-e9f1a20",
            synced_revision="git-commit-e9f1a20",
            resources=[
                IaCResource(
                    name="db-postgres-primary",
                    kind="RDSCluster",
                    desired_spec={"instance_type": "db.r6g.2xlarge", "multi_az": True, "storage_encrypted": True},
                    live_spec={"instance_type": "db.r6g.2xlarge", "multi_az": True, "storage_encrypted": True}
                ),
                IaCResource(
                    name="app-k8s-deployment",
                    kind="KubernetesDeployment",
                    desired_spec={"replicas": 12, "cpu_limit": "2000m", "image_tag": "v2.14.0"},
                    live_spec={"replicas": 12, "cpu_limit": "2000m", "image_tag": "v2.14.0"}
                ),
                IaCResource(
                    name="ingress-security-policy",
                    kind="NetworkPolicy",
                    desired_spec={"allow_cidrs": ["10.0.0.0/8"], "tls_enforced": True},
                    live_spec={"allow_cidrs": ["10.0.0.0/8"], "tls_enforced": True}
                )
            ]
        )
        self.reconciliation_interval = 3
        self.opa_policy_strict = True

    def banner(self):
        print(f"{Color.CYAN}{Color.BOLD}")
        print("==========================================================================")
        print("   SRE ARCHITECTURE LAB: GITOPS & IAC RECONCILIATION ENGINE SIMULATOR   ")
        print("   Bab 08: Otomasi Infrastructure-as-Code & GitOps Production Systems   ")
        print("==========================================================================")
        print(f"{Color.RESET}")

    def display_status(self):
        print(f"\n{Color.BOLD}{Color.BLUE}--- [SYSTEM LIVE TOPOLOGY & CONTROLLER STATUS] ---{Color.RESET}")
        print(f"Application Target      : {Color.BOLD}{self.app.name}{Color.RESET}")
        print(f"Desired Git Revision    : {Color.YELLOW}{self.app.target_revision}{Color.RESET}")
        print(f"Active Live Revision    : {Color.GREEN if self.app.target_revision == self.app.synced_revision else Color.RED}{self.app.synced_revision}{Color.RESET}")
        
        status_color = Color.GREEN if self.app.sync_status == SyncStatus.SYNCED else Color.RED
        health_color = Color.GREEN if self.app.health == HealthState.HEALTHY else Color.YELLOW
        print(f"Sync Status             : {status_color}{self.app.sync_status.value}{Color.RESET}")
        print(f"Cluster Health          : {health_color}{self.app.health.value}{Color.RESET}")
        print(f"Canary Traffic Weight   : {Color.CYAN}{self.app.canary_weight}% Production{Color.RESET}")

        print(f"\n{Color.BOLD}Live Resources Managed by Controller:{Color.RESET}")
        for r in self.app.resources:
            drift_label = f"{Color.RED}[DRIFT DETECTED]{Color.RESET}" if r.drift else f"{Color.GREEN}[IN SYNC]{Color.RESET}"
            lock_label = f"{Color.MAGENTA}[STATE LOCKED]{Color.RESET}" if r.state_lock else f"{Color.GRAY}[UNLOCKED]{Color.RESET}"
            print(f"  • {Color.BOLD}{r.kind}{Color.RESET}/{r.name} -> {drift_label} {lock_label}")
            if r.drift:
                print(f"    {Color.GRAY}Desired: {json.dumps(r.desired_spec)}{Color.RESET}")
                print(f"    {Color.RED}Live   : {json.dumps(r.live_spec)}{Color.RESET}")

    def evaluate_opa_policy(self, spec: Dict[str, any]) -> bool:
        """Simulasi OPA (Open Policy Agent) Guardrail"""
        print(f"{Color.GRAY}[OPA Gatekeeper] Memeriksa kepatuhan policy keamanan infrastruktur...{Color.RESET}")
        time.sleep(0.6)
        if "allow_cidrs" in spec:
            if "0.0.0.0/0" in spec["allow_cidrs"]:
                print(f"{Color.RED}[VIOLATION] OPA Rule CVE-SRE-08: Insecure CIDR 0.0.0.0/0 ditolak!{Color.RESET}")
                return False
        if "storage_encrypted" in spec and not spec["storage_encrypted"]:
            print(f"{Color.RED}[VIOLATION] OPA Rule ENCR-01: Penyimpanan database wajib terenkripsi!{Color.RESET}")
            return False
        print(f"{Color.GREEN}[OPA Gatekeeper] Security & Governance Validated: PASS{Color.RESET}")
        return True

    def trigger_git_commit(self):
        new_commit = f"git-commit-{hex(random.randint(0x100000, 0xFFFFFF))[2:]}"
        print(f"\n{Color.CYAN}--> [GIT WEBHOOK] Deteksi commit baru di repo manifest: {new_commit}{Color.RESET}")
        self.app.target_revision = new_commit
        
        # Simulasi perubahan deklaratif di manifest Git
        k8s_res = next(r for r in self.app.resources if r.kind == "KubernetesDeployment")
        k8s_res.desired_spec["replicas"] = 20
        k8s_res.desired_spec["image_tag"] = "v2.15.0-rc1"
        k8s_res.check_drift()
        
        self.app.sync_status = SyncStatus.OUT_OF_SYNC
        self.app.health = HealthState.DEGRADED
        print(f"{Color.YELLOW}[GitOps Engine] Target state termutasi! Sistem berada pada kondisi OUT_OF_SYNC.{Color.RESET}")

    def reconcile_loop(self, auto_heal: bool = True):
        print(f"\n{Color.MAGENTA}=== MEMULAI RECONCILIATION & IAC DEPLOYMENT LOOP ==={Color.RESET}")
        time.sleep(0.5)
        
        # 1. Acquire State Lock
        print(f"{Color.YELLOW}[IaC Backend] Mengunci DynamoDB/Consul Distributed State Lock...{Color.RESET}")
        for r in self.app.resources:
            r.state_lock = True
        time.sleep(0.7)

        # 2. Policy-as-Code Validation
        passed = True
        for r in self.app.resources:
            if not self.evaluate_opa_policy(r.desired_spec):
                passed = False
                break
        
        if not passed:
            print(f"{Color.RED}[SRE ALERT] Deployment diblokir oleh Policy Guardrails. Rollback otomatis!{Color.RESET}")
            self.app.sync_status = SyncStatus.POLICY_VIOLATION
            self._release_locks()
            return

        # 3. Progressive Rollout (Canary)
        print(f"{Color.BLUE}[Progressive Delivery] Melakukan Canary Promotion bertahap...{Color.RESET}")
        steps = [20, 50, 100]
        for step in steps:
            time.sleep(0.6)
            self.app.canary_weight = step
            error_rate = round(random.uniform(0.01, 0.05), 3)
            print(f"  -> Canary Weight: {step}% | P99 Latency: 42ms | Error Rate: {error_rate}% {Color.GREEN}[SLO OK]{Color.RESET}")

        # 4. Synchronize Live State to Desired State
        print(f"{Color.CYAN}[Reconciler] Menerapkan patch deklaratif ke live cluster...{Color.RESET}")
        for r in self.app.resources:
            r.live_spec = json.loads(json.dumps(r.desired_spec))
            r.drift = False

        self.app.synced_revision = self.app.target_revision
        self.app.sync_status = SyncStatus.SYNCED
        self.app.health = HealthState.HEALTHY
        self._release_locks()
        
        print(f"{Color.GREEN}{Color.BOLD}[SUCCESS] Rekonsiliasi selesai. Live State == Desired State!{Color.RESET}")

    def _release_locks(self):
        for r in self.app.resources:
            r.state_lock = False
        print(f"{Color.GRAY}[IaC Backend] State Lock dilepaskan.{Color.RESET}")

    def inject_manual_drift(self):
        print(f"\n{Color.RED}--> [CHAOS INJECTION] Insinyur melakukan perubahan manual via Cloud Console!{Color.RESET}")
        rds_res = next(r for r in self.app.resources if r.kind == "RDSCluster")
        rds_res.live_spec["storage_encrypted"] = False
        rds_res.live_spec["instance_type"] = "db.t4g.micro" # Downsize ilegal
        rds_res.check_drift()
        
        k8s_res = next(r for r in self.app.resources if r.kind == "KubernetesDeployment")
        k8s_res.live_spec["replicas"] = 2 # Mengakibatkan downtime
        k8s_res.check_drift()

        self.app.health = HealthState.DRIFTED
        self.app.sync_status = SyncStatus.OUT_OF_SYNC
        print(f"{Color.RED}[ALERT] Drift terdeteksi antara State File dan Actual Cloud Resources!{Color.RESET}")

    def test_insecure_policy(self):
        print(f"\n{Color.YELLOW}--> [TEST] Percobaan pengiriman PR dengan konfigurasi berbahaya (CIDR 0.0.0.0/0)...{Color.RESET}")
        net_res = next(r for r in self.app.resources if r.kind == "NetworkPolicy")
        original_cidr = net_res.desired_spec["allow_cidrs"]
        net_res.desired_spec["allow_cidrs"] = ["0.0.0.0/0"]
        self.app.target_revision = "git-pr-bad-actor-99"
        self.reconcile_loop()
        # Restore desired spec jika gagal
        net_res.desired_spec["allow_cidrs"] = original_cidr

    def run_interactive(self):
        self.banner()
        while True:
            self.display_status()
            print(f"\n{Color.BOLD}Pilihan Aksi SRE / GitOps Engineer:{Color.RESET}")
            print(f"  {Color.GREEN}1{Color.RESET}. Kirim Commit Manifest Git Baru (Trigger Automated Sync)")
            print(f"  {Color.RED}2{Color.RESET}. Injeksi Unmanaged Manual Drift (Simulasi Mutasi Manual)")
            print(f"  {Color.MAGENTA}3{Color.RESET}. Eksekusi GitOps Auto-Healing & Reconciliation Engine")
            print(f"  {Color.YELLOW}4{Color.RESET}. Uji Policy Guardrails OPA (Penolakan Insecure Config)")
            print(f"  {Color.GRAY}5{Color.RESET}. Refresh / Cek Status Metric Live")
            print(f"  {Color.BOLD}0{Color.RESET}. Keluar dari Simulasi")
            
            try:
                choice = input(f"\n{Color.BOLD}Pilih opsi [0-5]: {Color.RESET}").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nSelesai.")
                break

            if choice == "1":
                self.trigger_git_commit()
            elif choice == "2":
                self.inject_manual_drift()
            elif choice == "3":
                self.reconcile_loop()
            elif choice == "4":
                self.test_insecure_policy()
            elif choice == "5":
                continue
            elif choice == "0":
                print(f"{Color.CYAN}Menutup simulasi SRE GitOps Engine.{Color.RESET}")
                break
            else:
                print(f"{Color.RED}Pilihan tidak valid.{Color.RESET}")
            
            time.sleep(1)


if __name__ == "__main__":
    engine = GitOpsSREEngine()
    # Jika dijalankan tanpa terminal interaktif (CI mode), jalankan 1 siklus audit lengkap
    if not sys.stdin.isatty():
        engine.banner()
        engine.display_status()
        engine.inject_manual_drift()
        engine.display_status()
        engine.reconcile_loop()
        engine.display_status()
    else:
        engine.run_interactive()
