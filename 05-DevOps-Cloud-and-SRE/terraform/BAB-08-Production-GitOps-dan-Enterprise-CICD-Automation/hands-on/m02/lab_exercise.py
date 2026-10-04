#!/usr/bin/env python3
"""
Lab Exercise M02: Simulasi Pipeline GitOps Enterprise & CI/CD Terraform Tingkat Lanjut
BAB-08: Production GitOps dan Enterprise CI/CD Automation

Skrip ini mereplikasi alur kerja production-grade Infrastructure as Code (IaC):
1. PR Automation & Static Analysis (TFLint, Trivy, Checkov)
2. Policy as Code Enforcement (Open Policy Agent / OPA Rego)
3. Cloud Cost Estimation (Infracost API Simulation)
4. GitOps Atlantis Pull Request Lock & Plan Generation
5. Manual Approver Gatekeeper & Multi-Environment Promotion
6. Terraform Apply dengan State Locking (DynamoDB & S3 Backend)
7. Automated Post-Apply Health Check & Drift Detection Trigger
"""

import sys
import time
import json
import random
from typing import Dict, Any, List

# ANSI Terminal Color Palette
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
    BG_BLUE = "\033[44m"
    BG_GREEN = "\033[42m"
    BG_RED = "\033[41m"

def print_banner():
    banner = f"""
{Color.CYAN}{Color.BOLD}================================================================================{Color.RESET}
{Color.MAGENTA}{Color.BOLD}   ENTERPRISE GITOPS & CI/CD PIPELINE SIMULATOR - TERRAFORM PRODUCTION (BAB 08)  {Color.RESET}
{Color.CYAN}{Color.BOLD}================================================================================{Color.RESET}
{Color.WHITE}Arsitektur: Git-driven Multi-Environment Promotion (Dev -> Staging -> Prod){Color.RESET}
{Color.WHITE}Komponen: GitHub Actions, Atlantis, OPA Conftest, Infracost, DynamoDB State Lock{Color.RESET}
--------------------------------------------------------------------------------
"""
    print(banner)

def log_step(step_num: int, title: str):
    print(f"\n{Color.BOLD}{Color.BLUE}[STAGE {step_num:02d}]{Color.RESET} {Color.BOLD}{Color.WHITE}{title}{Color.RESET}")
    print(f"{Color.DIM}{'-' * 60}{Color.RESET}")

def log_info(msg: str):
    print(f"  {Color.CYAN}[INFO]{Color.RESET} {msg}")

def log_success(msg: str):
    print(f"  {Color.GREEN}[PASS]{Color.RESET} {msg}")

def log_warn(msg: str):
    print(f"  {Color.YELLOW}[WARN]{Color.RESET} {msg}")

def log_fail(msg: str):
    print(f"  {Color.RED}[FAIL]{Color.RESET} {msg}")

def spinner(text: str, duration: float = 1.2):
    frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    end_time = time.time() + duration
    i = 0
    while time.time() < end_time:
        sys.stdout.write(f"\r  {Color.YELLOW}{frames[i % len(frames)]}{Color.RESET} {text}...")
        sys.stdout.flush()
        time.sleep(0.08)
        i += 1
    sys.stdout.write(f"\r  {Color.GREEN}✔{Color.RESET} {text}... Selesai.\n")
    sys.stdout.flush()

class GitOpsPipelineSimulator:
    def __init__(self, pr_id: int, author: str, target_env: str):
        self.pr_id = pr_id
        self.author = author
        self.target_env = target_env
        self.lock_id = f"lock-tfstate-{random.randint(100000, 999999)}"
        self.diff_resources = [
            {"action": "create", "type": "aws_eks_cluster", "name": "prod-core-eks", "cost": 73.00},
            {"action": "create", "type": "aws_eks_node_group", "name": "compute-spot-ng", "cost": 142.50},
            {"action": "update", "type": "aws_security_group_rule", "name": "ingress_k8s_api", "cost": 0.00},
            {"action": "create", "type": "aws_s3_bucket", "name": "finance-audit-vault-prod", "cost": 12.30},
        ]

    def stage_lint_and_security(self) -> bool:
        log_step(1, "Static Code Analysis, Linting & Security Gate")
        log_info(f"Targeting Pull Request #{self.pr_id} oleh @{self.author}")
        
        spinner("Menjalankan 'terraform fmt -check -recursive'")
        log_success("HCL canonical formatting sesuai konvensi standar.")

        spinner("Menjalankan 'tflint --module --config=.tflint.hcl'")
        log_success("Zero deprecation syntax, standard AWS naming convention valid.")

        spinner("Menjalankan Checkov Static Security Scanner")
        log_success("CKV_AWS_145: S3 Bucket default KMS encryption aktif.")
        log_success("CKV_AWS_18: S3 Bucket access logging enabled.")
        log_success("CKV_AWS_39: EKS cluster endpoint public access dibatasi oleh CIDR.")
        return True

    def stage_opa_policy(self) -> bool:
        log_step(2, "Policy as Code Enforcement (Open Policy Agent / Conftest)")
        log_info("Mengevaluasi Terraform Plan JSON terhadap Enterprise Rego Policies...")
        spinner("Evaluating OPA policies: 'data.terraform.deny[_]'")

        policies = [
            ("rule_mandatory_tags", "Tags [Environment, Owner, CostCenter, ManagedBy=Terraform] terpenuhi.", True),
            ("rule_disallow_wide_cidr", "Tidak ada Ingress Security Group 0.0.0.0/0 pada port 22/3389.", True),
            ("rule_approved_regions", "Region dibatasi ketat ke 'ap-southeast-1' & 'ap-southeast-3'.", True),
            ("rule_kms_customer_managed", "Storage enkripsi wajib CMK, bukan default AWS managed key.", True)
        ]

        all_passed = True
        for rule_id, desc, passed in policies:
            if passed:
                log_success(f"{rule_id}: {desc}")
            else:
                log_fail(f"{rule_id}: {desc}")
                all_passed = False

        print(f"  {Color.BOLD}{Color.GREEN}Policy Gate: 0 Violations, 0 Warnings.{Color.RESET}")
        return all_passed

    def stage_infracost(self) -> float:
        log_step(3, "FinOps Cloud Cost Estimation (Infracost CI/CD)")
        log_info("Menghitung baseline perubahan pengeluaran bulanan cloud...")
        spinner("Memanggil Infracost Cloud Pricing API")

        total_increase = sum(r["cost"] for r in self.diff_resources)
        print(f"""
  {Color.WHITE}{Color.BOLD}INFRACOST BREAKDOWN MATRIX (Currency: USD/Month):{Color.RESET}
  ┌──────────────────────────────┬──────────────────┬──────────────┐
  │ Resource Type                │ Action           │ Delta Cost   │
  ├──────────────────────────────┼──────────────────┼──────────────┤""")
        for item in self.diff_resources:
            action_colored = f"{Color.GREEN}+ CREATE{Color.RESET}" if item["action"] == "create" else f"{Color.YELLOW}~ UPDATE{Color.RESET}"
            print(f"  │ {item['type']:<28} │ {action_colored:<25} │ +${item['cost']:>9.2f} │")
        print(f"  └──────────────────────────────┴──────────────────┴──────────────┘")
        print(f"  {Color.BOLD}Monthly Cost Projection Difference: {Color.GREEN}+${total_increase:.2f}{Color.RESET}")
        
        if total_increase > 500.0:
            log_warn("Estimasi kenaikan biaya > $500/bulan! Memerlukan persetujuan FinOps Director.")
        else:
            log_success("Kenaikan biaya dalam threshold anggaran tim DevOps (< $500/bulan).")
        return total_increase

    def stage_atlantis_lock_plan(self):
        log_step(4, "GitOps Engine Lock & Plan (Atlantis Automation)")
        log_info(f"Mengamankan remote state lock DynamoDB: {self.lock_id}")
        spinner("Acquiring lock on S3 backend key: 'enterprise/production/terraform.tfstate'")
        log_success(f"Lock didapatkan: MD5-CheckSum=d41d8cd98f00b204e9800998ecf8427e")

        print(f"\n  {Color.CYAN}--- PULL REQUEST COMMENT GENERATED BY ATLANTIS BOT ---{Color.RESET}")
        print(f"  {Color.DIM}User @{self.author} run comment command: 'atlantis plan -d environments/{self.target_env}'{Color.RESET}")
        print(f"  {Color.BOLD}Plan: 3 to add, 1 to change, 0 to destroy.{Color.RESET}")
        print(f"  {Color.CYAN}-------------------------------------------------------{Color.RESET}\n")

    def stage_approval_gate(self) -> bool:
        log_step(5, "Enterprise Gatekeeper & Peer-Review Sign-off")
        print(f"  Target Environment: {Color.BOLD}{Color.RED if self.target_env == 'production' else Color.YELLOW}{self.target_env.upper()}{Color.RESET}")
        print(f"  Diperlukan minimal: {Color.BOLD}2 Senior Staff Approval{Color.RESET} untuk apply ke {self.target_env}.")

        try:
            user_input = input(f"\n  {Color.BOLD}{Color.WHITE}Ketik 'APPROVE' untuk mensimulasikan merge PR & trigger auto-apply (atau 'REJECT'): {Color.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            user_input = "APPROVE"
            print(f"\n  [Auto-Input fallback: {user_input}]")

        if user_input.upper() == "APPROVE":
            log_success("Approver 1: @tech-lead-sre (Signed off GPG Commit: 7fbc82a)")
            log_success("Approver 2: @secops-principal (Approved policy exceptions & KMS rules)")
            return True
        else:
            log_fail("Pipeline digagalkan oleh Gatekeeper Reviewer.")
            return False

    def stage_terraform_apply(self):
        log_step(6, f"Terraform Apply Execution ({self.target_env.upper()})")
        log_info("CI Runner mengalokasikan isolated ephemeral container...")
        spinner("Mengunduh providers (aws v5.45.0, kubernetes v2.28.0, helm v2.13.0)")

        for res in self.diff_resources:
            spinner(f"Applying {res['type']}.{res['name']}", duration=0.8)
            log_success(f"Provisioned {res['type']}.{res['name']} (ID: {random.randint(10000000, 99999999)})")

        spinner("Releasing DynamoDB State Lock Table 'tf-state-locks'")
        log_success(f"Lock {self.lock_id} berhasil dilepaskan. State updated secara atomik di S3.")

    def stage_post_apply_verification(self):
        log_step(7, "Post-Deployment Smoke Tests & Continuous Drift Detection")
        spinner("Kubeconfig auth ping ke cluster AWS EKS Endpoint")
        log_success("Cluster API Status: HTTP 200 OK - Control Plane Healthy.")

        spinner("Menjadwalkan AWS EventBridge Rule Cron (Drift Detection setiap 4 jam)")
        log_success("EventBridge Rule 'terraform-drift-detector-prod' aktif.")
        log_info("Webhook Slack terintegrasi: #devops-infra-alerts")

def main():
    print_banner()
    print(f"{Color.YELLOW}[*] Memulai interaktif skenario: Deployment Inkremental Arsitektur EKS & S3 Enterprise{Color.RESET}\n")

    sim = GitOpsPipelineSimulator(pr_id=1408, author="lead-sre-architect", target_env="production")
    
    # Execution Flow
    sim.stage_lint_and_security()
    time.sleep(0.5)

    if not sim.stage_opa_policy():
        print(f"\n{Color.BG_RED}{Color.WHITE} PIPELINE ABORTED: Policy Gate Failure {Color.RESET}")
        sys.exit(1)
    time.sleep(0.5)

    sim.stage_infracost()
    time.sleep(0.5)

    sim.stage_atlantis_lock_plan()
    time.sleep(0.5)

    approved = sim.stage_approval_gate()
    if not approved:
        print(f"\n{Color.BG_RED}{Color.WHITE} GITOPS ROLLOUT DIBATALKAN {Color.RESET}")
        sys.exit(0)

    sim.stage_terraform_apply()
    time.sleep(0.5)

    sim.stage_post_apply_verification()

    summary_card = f"""
{Color.BG_GREEN}{Color.WHITE}{Color.BOLD} PIPELINE SUKSES - INFRASTRUKTUR TELAH AKTIF DI PRODUCTION {Color.RESET}
{Color.GREEN}✔ GitOps Pull Request #{sim.pr_id} merged to branch 'main'
✔ Remote state atomik S3/DynamoDB konsisten tanpa race-condition
✔ Audit log tersimpan di AWS CloudTrail & GitHub Deployment Event Log{Color.RESET}
"""
    print(summary_card)

if __name__ == "__main__":
    main()
