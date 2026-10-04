#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Terragrunt Monorepo Architecture & FinOps Policy Guardrails
Modul: BAB-09-Skalabilitas-Terragrunt-Monorepo-FinOps (M02 Hands-on Lab)

Fitur Simulasi:
1. Terragrunt Dependency DAG & Concurrent Stack Resolution (terragrunt run-all plan)
2. Infracost FinOps Shift-Left Simulation & Automated Cost Diff Calculation
3. FinOps Budget Guardrail Policy Engine (OPEX Budget Threshold vs Projected Cost)
4. Resource Mandatory Tagging Compliance Checker (FinOps Cost Allocation Tags)
5. Interactive CLI Menu dengan visualisasi terminal ANSI Color
"""

import sys
import time
import json
import dataclasses
from typing import Dict, List, Optional

# --- ANSI Color Codes ---
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
WHITE = "\033[97m"

@dataclasses.dataclass
class TerragruntModule:
    name: str
    path: str
    dependencies: List[str]
    monthly_baseline_cost: float
    monthly_new_cost: float
    tags: Dict[str, str]

class TerragruntFinOpsSimulator:
    def __init__(self, monthly_budget_limit: float = 3500.0):
        self.budget_limit = monthly_budget_limit
        self.modules: Dict[str, TerragruntModule] = {
            "vpc-network": TerragruntModule(
                name="vpc-network",
                path="live/prod/ap-southeast-3/vpc",
                dependencies=[],
                monthly_baseline_cost=120.0,
                monthly_new_cost=145.0,
                tags={"Environment": "production", "CostCenter": "CC-INFRA-01", "ManagedBy": "Terragrunt", "Owner": "sre-core"}
            ),
            "rds-aurora-cluster": TerragruntModule(
                name="rds-aurora-cluster",
                path="live/prod/ap-southeast-3/rds",
                dependencies=["vpc-network"],
                monthly_baseline_cost=780.0,
                monthly_new_cost=1120.0,
                tags={"Environment": "production", "CostCenter": "CC-FINTECH-02", "ManagedBy": "Terragrunt"}
            ),
            "eks-workload-cluster": TerragruntModule(
                name="eks-workload-cluster",
                path="live/prod/ap-southeast-3/eks",
                dependencies=["vpc-network"],
                monthly_baseline_cost=1450.0,
                monthly_new_cost=1980.0,
                tags={"Environment": "production", "CostCenter": "CC-APP-03", "ManagedBy": "Terragrunt", "Owner": "platform-eng"}
            ),
            "elasticache-redis": TerragruntModule(
                name="elasticache-redis",
                path="live/prod/ap-southeast-3/redis",
                dependencies=["vpc-network", "eks-workload-cluster"],
                monthly_baseline_cost=210.0,
                monthly_new_cost=295.0,
                tags={"Environment": "production", "CostCenter": "CC-APP-03"}
            ),
            "observability-stack": TerragruntModule(
                name="observability-stack",
                path="live/prod/ap-southeast-3/monitoring",
                dependencies=["eks-workload-cluster"],
                monthly_baseline_cost=320.0,
                monthly_new_cost=360.0,
                tags={"Environment": "production", "ManagedBy": "Terragrunt", "Owner": "sre-core"}
            )
        }

    def print_banner(self):
        print(f"\n{BOLD}{CYAN}========================================================================{RESET}")
        print(f"{BOLD}{WHITE}   TERRAGRUNT MONOREPO & FINOPS GUARDRAILS INTERACTIVE LAB SIMULATOR  {RESET}")
        print(f"{BOLD}{CYAN}========================================================================{RESET}")
        print(f"{DIM}Arsitektur Produksi Skalabilitas Tinggi: Multi-Stack DAG & Infracost Gate{RESET}\n")

    def show_dependency_tree(self):
        print(f"{BOLD}{YELLOW}[+] Resolving Terragrunt Multi-Module Dependency Graph (DAG)...{RESET}")
        time.sleep(0.4)
        for mod_name, mod in self.modules.items():
            deps_str = f"{CYAN}{', '.join(mod.dependencies)}{RESET}" if mod.dependencies else f"{DIM}(root - no dependencies){RESET}"
            print(f"  {GREEN}▶{RESET} {BOLD}{mod.name:<22}{RESET} [{DIM}{mod.path}{RESET}]")
            print(f"     └── Dependencies: {deps_str}")
        print(f"\n{BOLD}{GREEN}[✔] Terragrunt execution order successfully planned with topo-sort.{RESET}")

    def run_terragrunt_run_all(self):
        print(f"\n{BOLD}{MAGENTA}[*] Executing: `terragrunt run-all plan -out=tfplan.binary`{RESET}")
        print(f"{DIM}Running plan across 5 isolated state stacks with remote state S3 & DynamoDB locks...{RESET}\n")
        
        # Level 1
        print(f"{YELLOW}▶ Stage 1 (Concurrency 1):{RESET} Initializing and planning root stack [vpc-network]")
        time.sleep(0.5)
        print(f"  {GREEN}✓ vpc-network planned successfully (0 errors, 4 resources to add){RESET}")
        
        # Level 2
        print(f"{YELLOW}▶ Stage 2 (Concurrency 2):{RESET} Parallel execution of [rds-aurora-cluster, eks-workload-cluster]")
        time.sleep(0.7)
        print(f"  {GREEN}✓ rds-aurora-cluster planned successfully (Scale-up db.r6g.xlarge){RESET}")
        print(f"  {GREEN}✓ eks-workload-cluster planned successfully (NodeGroup autoscaling 3 -> 6){RESET}")

        # Level 3
        print(f"{YELLOW}▶ Stage 3 (Concurrency 2):{RESET} Parallel execution of [elasticache-redis, observability-stack]")
        time.sleep(0.6)
        print(f"  {GREEN}✓ elasticache-redis planned successfully{RESET}")
        print(f"  {GREEN}✓ observability-stack planned successfully{RESET}")
        print(f"\n{BOLD}{GREEN}[SUCCESS] Terragrunt run-all finished without lock contention!{RESET}\n")

    def run_infracost_breakdown(self):
        print(f"\n{BOLD}{BLUE}[+] Running Infracost Shift-Left Financial Analysis...{RESET}")
        print(f"{DIM}Parsing Terraform HCL AST and matching against Cloud Provider Pricing API...{RESET}\n")
        time.sleep(0.5)

        total_baseline = 0.0
        total_projected = 0.0

        header = f"{'MODULE NAME':<24} {'BASELINE ($/mo)':<18} {'PROJECTED ($/mo)':<18} {'DELTA ($/mo)':<16} {'% CHANGE'}"
        print(f"{BOLD}{WHITE}{header}{RESET}")
        print("-" * len(header))

        for mod in self.modules.values():
            delta = mod.monthly_new_cost - mod.monthly_baseline_cost
            pct = (delta / mod.monthly_baseline_cost) * 100 if mod.monthly_baseline_cost > 0 else 0.0
            total_baseline += mod.monthly_baseline_cost
            total_projected += mod.monthly_new_cost

            color = RED if delta > 200 else (YELLOW if delta > 0 else GREEN)
            delta_str = f"{'+' if delta >= 0 else ''}${delta:,.2f}"
            pct_str = f"{'+' if pct >= 0 else ''}{pct:.1f}%"

            print(f"{mod.name:<24} ${mod.monthly_baseline_cost:<17,.2f} ${mod.monthly_new_cost:<17,.2f} {color}{delta_str:<16} {pct_str}{RESET}")

        total_delta = total_projected - total_baseline
        total_pct = (total_delta / total_baseline) * 100
        print("-" * len(header))
        print(f"{BOLD}{WHITE}{'TOTAL INFRA COST':<24} ${total_baseline:<17,.2f} ${total_projected:<17,.2f} {RED if total_delta > 0 else GREEN}+{total_delta:<15,.2f} +{total_pct:.1f}%{RESET}\n")

        return total_projected

    def evaluate_finops_guardrails(self, projected_cost: float):
        print(f"{BOLD}{YELLOW}[+] Evaluating FinOps OPA Policy & Cost Guardrails...{RESET}")
        time.sleep(0.4)
        print(f"  • Monthly Hard Budget Limit : {BOLD}${self.budget_limit:,.2f}{RESET}")
        print(f"  • Projected Post-Apply Cost : {BOLD}${projected_cost:,.2f}{RESET}")

        cost_overrun = projected_cost - self.budget_limit
        if cost_overrun > 0:
            print(f"\n{BOLD}{RED}[VIOLATION] FINOPS POLICY FAILED: Budget Threshold Exceeded!{RESET}")
            print(f"  {RED}✖ Cost overrun of +${cost_overrun:,.2f} ({((projected_cost/self.budget_limit)-1)*100:.1f}% over limit){RESET}")
            print(f"  {YELLOW}⚠ FinOps Action:{RESET} Pull Request requires explicit Finance Director & Head of Infra approval token.")
            print(f"  {YELLOW}⚠ Recommendation:{RESET} Rightsizing EKS Spot instances and configuring Aurora auto-pause during non-peak.")
            return False
        else:
            print(f"\n{BOLD}{GREEN}[PASS] FinOps Policy Check Succeeded: Spending within allowable budget.{RESET}")
            return True

    def audit_finops_tags(self):
        print(f"\n{BOLD}{CYAN}[+] Auditing Mandatory Cost-Allocation Tags (FinOps Tag Governance)...{RESET}")
        mandatory_tags = ["Environment", "CostCenter", "ManagedBy", "Owner"]
        time.sleep(0.4)

        has_missing = False
        for mod in self.modules.values():
            missing = [t for t in mandatory_tags if t not in mod.tags]
            if missing:
                has_missing = True
                print(f"  {RED}✖ [NON-COMPLIANT]{RESET} {BOLD}{mod.name}{RESET}")
                print(f"      Missing mandatory tags: {RED}{', '.join(missing)}{RESET}")
            else:
                print(f"  {GREEN}✔ [COMPLIANT]{RESET} {mod.name} (All 4 tags present)")

        if has_missing:
            print(f"\n{YELLOW}[WARN] CI/CD Linting: PR blocked by Tagging Policy until tags are completed.{RESET}")
        else:
            print(f"\n{GREEN}[SUCCESS] 100% Tagging Compliance Achieved across all Terragrunt stacks.{RESET}")

    def interactive_menu(self):
        while True:
            self.print_banner()
            print(f"{BOLD}Pilih Skenario / Aksi Simulasi:{RESET}")
            print(f"  {CYAN}1.{RESET} Visualisasi Terragrunt Monorepo DAG & Stacks")
            print(f"  {CYAN}2.{RESET} Jalankan `terragrunt run-all plan` Multi-Stack Concurrent")
            print(f"  {CYAN}3.{RESET} Jalankan FinOps Infracost Breakdown & Delta Analysis")
            print(f"  {CYAN}4.{RESET} Evaluasi FinOps Budget Guardrail Gate")
            print(f"  {CYAN}5.{RESET} Audit Kepatuhan Tagging FinOps (Cost Allocation)")
            print(f"  {CYAN}6.{RESET} Jalankan Seluruh Pipeline CI/CD Lengkap (Full Test)")
            print(f"  {RED}0.{RESET} Keluar (Exit)")

            try:
                choice = input(f"\n{BOLD}{WHITE}Masukkan nomor pilihan [0-6]: {RESET}").strip()
            except (EOFError, KeyboardInterrupt):
                print(f"\n{YELLOW}Exiting simulator...{RESET}")
                break

            if choice == "1":
                self.show_dependency_tree()
            elif choice == "2":
                self.run_terragrunt_run_all()
            elif choice == "3":
                self.run_infracost_breakdown()
            elif choice == "4":
                proj = sum(m.monthly_new_cost for m in self.modules.values())
                self.evaluate_finops_guardrails(proj)
            elif choice == "5":
                self.audit_finops_tags()
            elif choice == "6":
                print(f"\n{BOLD}{WHITE}=== RUNNING AUTOMATED FULL FINOPS & TERRAGRUNT CI/CD PIPELINE ==={RESET}")
                self.show_dependency_tree()
                self.run_terragrunt_run_all()
                proj = self.run_infracost_breakdown()
                self.evaluate_finops_guardrails(proj)
                self.audit_finops_tags()
                print(f"\n{BOLD}{GREEN}=== PIPELINE SIMULATION COMPLETED ==={RESET}\n")
            elif choice == "0":
                print(f"{GREEN}Lab exercise simulator selesai. Sampai jumpa!{RESET}")
                break
            else:
                print(f"{RED}[!] Pilihan tidak valid, silakan ulangi.{RESET}")

            input(f"\n{DIM}Tekan [Enter] untuk kembali ke menu utama...{RESET}")

def main():
    simulator = TerragruntFinOpsSimulator(monthly_budget_limit=3500.0)
    # Jika dipanggil dengan argumen --non-interactive (misalnya untuk automated test)
    if len(sys.argv) > 1 and sys.argv[1] in ("--auto", "--test", "--non-interactive"):
        simulator.print_banner()
        simulator.show_dependency_tree()
        simulator.run_terragrunt_run_all()
        proj = simulator.run_infracost_breakdown()
        simulator.evaluate_finops_guardrails(proj)
        simulator.audit_finops_tags()
    else:
        simulator.interactive_menu()

if __name__ == "__main__":
    main()
