#!/usr/bin/env python3
"""
Lab Exercise M02: Simulasi Siklus Hidup Arsitektur Produksi Terraform (IaC)
Modul: BAB-05-Infrastructure-as-Code-Terraform
Fokus: Remote State (S3 + DynamoDB State Locking), Dependency Graph, Drift Detection, dan Canary Rollout.
"""

import sys
import time
import json
import random
import hashlib
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional
from enum import Enum

# ANSI Color Codes untuk output visual terminal
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BG_BLUE = "\033[44m"
    BG_GREEN = "\033[42m"
    BG_RED = "\033[41m"

class ResourceStatus(Enum):
    PLANNED = "PLANNED"
    CREATING = "CREATING"
    CREATED = "CREATED"
    MODIFIED = "MODIFIED"
    DESTROYED = "DESTROYED"
    DRIFTED = "DRIFTED"

@dataclass
class TerraformResource:
    address: str
    resource_type: str
    name: str
    attributes: Dict[str, str]
    dependencies: List[str] = field(default_factory=list)
    status: ResourceStatus = ResourceStatus.PLANNED

class StateLockManager:
    """Simulasi DynamoDB State Locking untuk mencegah concurrent apply."""
    def __init__(self):
        self.lock_id: Optional[str] = None
        self.locked_by: Optional[str] = None
        self.created_at: Optional[str] = None

    def acquire_lock(self, who: str) -> bool:
        if self.lock_id is not None:
            return False
        self.lock_id = hashlib.md5(f"{who}-{time.time()}".encode()).hexdigest()[:12]
        self.locked_by = who
        self.created_at = time.strftime("%Y-%m-%d %H:%M:%S")
        return True

    def release_lock(self, who: str) -> bool:
        if self.locked_by == who or who == "FORCE_UNLOCK":
            self.lock_id = None
            self.locked_by = None
            self.created_at = None
            return True
        return False

class TerraformEngine:
    """Mesin simulasi workflow Terraform enterprise tingkat lanjut."""
    def __init__(self):
        self.lock_manager = StateLockManager()
        self.state_version = 1
        self.serial = 0
        self.state_store: Dict[str, TerraformResource] = {}
        self.desired_spec: Dict[str, TerraformResource] = {}
        self._init_desired_state()

    def _init_desired_state(self):
        # Desired state mendefinisikan arsitektur VPC + EKS + RDS Multi-AZ + IAM
        self.desired_spec = {
            "module.vpc.aws_vpc.primary": TerraformResource(
                address="module.vpc.aws_vpc.primary",
                resource_type="aws_vpc",
                name="prod_vpc",
                attributes={"cidr_block": "10.0.0.0/16", "enable_dns_hostnames": "true"},
                dependencies=[]
            ),
            "module.vpc.aws_subnet.private_1a": TerraformResource(
                address="module.vpc.aws_subnet.private_1a",
                resource_type="aws_subnet",
                name="private_1a",
                attributes={"cidr_block": "10.0.1.0/24", "az": "us-east-1a"},
                dependencies=["module.vpc.aws_vpc.primary"]
            ),
            "module.vpc.aws_subnet.private_1b": TerraformResource(
                address="module.vpc.aws_subnet.private_1b",
                resource_type="aws_subnet",
                name="private_1b",
                attributes={"cidr_block": "10.0.2.0/24", "az": "us-east-1b"},
                dependencies=["module.vpc.aws_vpc.primary"]
            ),
            "module.eks.aws_eks_cluster.main": TerraformResource(
                address="module.eks.aws_eks_cluster.main",
                resource_type="aws_eks_cluster",
                name="production_eks",
                attributes={"version": "1.30", "endpoint_private_access": "true"},
                dependencies=["module.vpc.aws_subnet.private_1a", "module.vpc.aws_subnet.private_1b"]
            ),
            "module.database.aws_db_instance.postgres": TerraformResource(
                address="module.database.aws_db_instance.postgres",
                resource_type="aws_db_instance",
                name="primary_rds",
                attributes={"instance_class": "db.m6g.xlarge", "multi_az": "true", "storage_encrypted": "true"},
                dependencies=["module.vpc.aws_subnet.private_1a", "module.vpc.aws_subnet.private_1b"]
            )
        }

    def print_banner(self):
        print(f"\n{Color.BG_BLUE}{Color.WHITE}{Color.BOLD} TERRAFORM PRODUCTION INFRASTRUCTURE EMULATOR {Color.RESET}")
        print(f"{Color.CYAN}Modul Lanjutan: Remote Backend (S3) | Distributed Locking (DynamoDB) | Drift Detector{Color.RESET}\n")

    def run_init(self):
        print(f"{Color.BOLD}1. Menjalankan 'terraform init' ...{Color.RESET}")
        time.sleep(0.3)
        print(f"  {Color.GREEN}✓{Color.RESET} Inisialisasi S3 Backend: s3://tf-state-enterprise-prod/ap-southeast-1/terraform.tfstate")
        print(f"  {Color.GREEN}✓{Color.RESET} Inisialisasi DynamoDB Table Lock: arn:aws:dynamodb:ap-southeast-1:112233445566:table/tf-locks")
        print(f"  {Color.GREEN}✓{Color.RESET} Plugin provider 'hashicorp/aws' v5.45.0 telah berhasil diverifikasi via SHA-256 lockfile.")
        print(f"{Color.GREEN}Sukses: Direktori kerja Terraform siap digunakan!{Color.RESET}\n")

    def run_plan(self) -> List[str]:
        print(f"{Color.BOLD}2. Menjalankan 'terraform plan' (DAG Dependency Resolution) ...{Color.RESET}")
        actions = []
        for addr, spec in self.desired_spec.items():
            if addr not in self.state_store:
                actions.append(f"{Color.GREEN}+ create {addr}{Color.RESET}")
            else:
                current = self.state_store[addr]
                if current.attributes != spec.attributes:
                    actions.append(f"{Color.YELLOW}~ update in-place {addr}{Color.RESET}")
        
        if not actions:
            print(f"  {Color.CYAN}No changes. Your infrastructure matches the configuration.{Color.RESET}\n")
            return []

        print(f"  Terraform will perform the following actions:\n")
        for act in actions:
            print(f"    {act}")
        
        to_add = len([a for a in actions if "+ create" in a])
        to_mod = len([a for a in actions if "~ update" in a])
        print(f"\n{Color.BOLD}Plan:{Color.RESET} {Color.GREEN}{to_add} to add{Color.RESET}, {Color.YELLOW}{to_mod} to change{Color.RESET}, {Color.RED}0 to destroy{Color.RESET}.\n")
        return actions

    def run_apply(self, operator: str = "devops-engineer"):
        print(f"{Color.BOLD}3. Menjalankan 'terraform apply' ...{Color.RESET}")
        
        # Step: Acquire Lock
        print(f"  Acquiring state lock from DynamoDB Table...")
        if not self.lock_manager.acquire_lock(operator):
            print(f"  {Color.RED}Error: State lock failed! Locked by: {self.lock_manager.locked_by} (ID: {self.lock_manager.lock_id}){Color.RESET}")
            return
        
        print(f"  {Color.GREEN}Lock acquired! Lock ID: {self.lock_manager.lock_id}{Color.RESET}")
        time.sleep(0.4)

        try:
            # Selesaikan dependency graph sederhana
            resolved_order = [
                "module.vpc.aws_vpc.primary",
                "module.vpc.aws_subnet.private_1a",
                "module.vpc.aws_subnet.private_1b",
                "module.eks.aws_eks_cluster.main",
                "module.database.aws_db_instance.postgres"
            ]

            for addr in resolved_order:
                target = self.desired_spec[addr]
                current = self.state_store.get(addr)
                if not current:
                    print(f"  {Color.CYAN}{addr}:{Color.RESET} Creating...")
                    time.sleep(0.2)
                    target.status = ResourceStatus.CREATED
                    self.state_store[addr] = TerraformResource(
                        address=target.address,
                        resource_type=target.resource_type,
                        name=target.name,
                        attributes=dict(target.attributes),
                        dependencies=list(target.dependencies),
                        status=ResourceStatus.CREATED
                    )
                    print(f"  {Color.GREEN}{addr}: Creation complete after 2s [id={target.name}_id_aws]{Color.RESET}")
                elif current.attributes != target.attributes:
                    print(f"  {Color.YELLOW}{addr}:{Color.RESET} Modifying attributes in-place...")
                    time.sleep(0.2)
                    current.attributes = dict(target.attributes)
                    current.status = ResourceStatus.CREATED
                    print(f"  {Color.GREEN}{addr}: Modifications complete [id={target.name}_id_aws]{Color.RESET}")
            
            self.serial += 1
            print(f"\n{Color.BG_GREEN}{Color.WHITE}{Color.BOLD} Apply complete! Resources: {len(self.state_store)} added/aligned. {Color.RESET}")
            print(f"State remote updated to serial {self.serial} di s3://tf-state-enterprise-prod/terraform.tfstate.\n")
        finally:
            self.lock_manager.release_lock(operator)
            print(f"  {Color.CYAN}Releasing state lock ({operator})... Done.{Color.RESET}\n")

    def simulate_drift(self):
        """Simulasi out-of-band change (perubahan langsung via AWS Console)."""
        print(f"{Color.BOLD}4. [Simulasi Masalah] Seorang engineer mengubah konfigurasi langsung di AWS Console (Drift)...{Color.RESET}")
        target_res = "module.database.aws_db_instance.postgres"
        if target_res in self.state_store:
            # Mengubah instance class secara ilegal di live state
            self.state_store[target_res].attributes["instance_class"] = "db.t3.medium"
            self.state_store[target_res].status = ResourceStatus.DRIFTED
            print(f"  {Color.RED}Drift terjadi pada '{target_res}':{Color.RESET}")
            print(f"    - Desired Spec (Code): db.m6g.xlarge")
            print(f"    - Live Infrastructure : db.t3.medium (Diubah langsung via console!)\n")
        else:
            print(f"  {Color.YELLOW}Peringatan: Terapkan 'apply' terlebih dahulu sebelum simulasi drift.{Color.RESET}\n")

    def run_drift_detection(self):
        """Mendeteksi perbedaan antara live state dan code."""
        print(f"{Color.BOLD}5. Menjalankan Drift Detection (terraform refresh & plan)...{Color.RESET}")
        time.sleep(0.3)
        drift_found = False
        for addr, current in self.state_store.items():
            desired = self.desired_spec.get(addr)
            if desired and current.attributes != desired.attributes:
                drift_found = True
                print(f"  {Color.RED}! ALERT DRIFT TERDETEKSI:{Color.RESET} {addr}")
                for k, v in desired.attributes.items():
                    curr_val = current.attributes.get(k)
                    if curr_val != v:
                        print(f"    Attribute '{k}': Live={Color.RED}{curr_val}{Color.RESET} != Code={Color.GREEN}{v}{Color.RESET}")
        
        if drift_found:
            print(f"\n  {Color.YELLOW}Rekomendasi Remediasi:{Color.RESET} Jalankan 'terraform apply' untuk memaksa Live State kembali patuh pada Code.")
        else:
            print(f"  {Color.GREEN}✓ Infrastruktur sinkron 100% dengan State & Code (Zero Drift).{Color.RESET}")
        print()

    def show_state(self):
        print(f"{Color.BOLD}State File Viewer (Remote State Dump):{Color.RESET}")
        state_export = {
            "version": 4,
            "terraform_version": "1.8.5",
            "serial": self.serial,
            "lineage": "e2c34a2e-4b68-45a7-9f44-123456789abc",
            "resources": [
                {
                    "address": res.address,
                    "type": res.resource_type,
                    "name": res.name,
                    "status": res.status.value,
                    "attributes": res.attributes
                }
                for res in self.state_store.values()
            ]
        }
        print(json.dumps(state_export, indent=2))
        print()

def interactive_loop():
    engine = TerraformEngine()
    engine.print_banner()

    menu = (
        f"{Color.BOLD}PILIH TINDAKAN SIMULASI:{Color.RESET}\n"
        f"  {Color.CYAN}[1]{Color.RESET} terraform init (Inisialisasi Backend S3 + DynamoDB Lock)\n"
        f"  {Color.CYAN}[2]{Color.RESET} terraform plan (Hitung DAG & Perubahan Arsitektur)\n"
        f"  {Color.CYAN}[3]{Color.RESET} terraform apply (Akuisisi State Lock & Rollout Infrastruktur)\n"
        f"  {Color.CYAN}[4]{Color.RESET} Simulasi Out-of-band Configuration Drift (Console Modification)\n"
        f"  {Color.CYAN}[5]{Color.RESET} Jalankan Audit Drift Detection & Remediasi\n"
        f"  {Color.CYAN}[6]{Color.RESET} Inspeksi remote state (terraform show / state pull)\n"
        f"  {Color.CYAN}[7]{Color.RESET} Jalankan Seluruh Skenario Otomatis (Canary / Full Cycle)\n"
        f"  {Color.RED}[0] Keluar (Exit){Color.RESET}\n"
    )

    # Cek jika dijalankan non-interaktif
    if not sys.stdin.isatty():
        print(f"{Color.YELLOW}Mode Non-Interaktif Terdeteksi. Menjalankan siklus pengujian penuh otomatis...{Color.RESET}\n")
        engine.run_init()
        engine.run_plan()
        engine.run_apply()
        engine.simulate_drift()
        engine.run_drift_detection()
        engine.run_apply() # Remediasi
        engine.run_drift_detection()
        engine.show_state()
        print(f"{Color.BG_GREEN}{Color.WHITE}{Color.BOLD} Semua pengujian arsitektur produksi IaC sukses! {Color.RESET}")
        return

    while True:
        print(menu)
        try:
            choice = input(f"{Color.BOLD}tf-cli > {Color.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            break

        if choice == "1":
            engine.run_init()
        elif choice == "2":
            engine.run_plan()
        elif choice == "3":
            engine.run_apply()
        elif choice == "4":
            engine.simulate_drift()
        elif choice == "5":
            engine.run_drift_detection()
        elif choice == "6":
            engine.show_state()
        elif choice == "7":
            print(f"\n{Color.MAGENTA}=== MENJALANKAN FULL PIPELINE IA-C PRODUCTION ==={Color.RESET}")
            engine.run_init()
            engine.run_plan()
            engine.run_apply()
            engine.simulate_drift()
            engine.run_drift_detection()
            print(f"{Color.CYAN}Memulihkan Drift dengan 'terraform apply'...{Color.RESET}")
            engine.run_apply()
            engine.run_drift_detection()
            print(f"{Color.GREEN}Siklus CI/CD Terraform selesai dengan sempurna.{Color.RESET}\n")
        elif choice == "0":
            print(f"{Color.GREEN}Terima kasih telah menggunakan Terraform Production Emulator.{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid. Silakan coba lagi.{Color.RESET}\n")

if __name__ == "__main__":
    interactive_loop()
