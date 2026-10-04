#!/usr/bin/env python3
"""
Terraform Enterprise Module Architecture & Reusability Lab Simulator
BAB-05: Enterprise Module Architecture dan Reusability (Modul 02)
Topic: Advanced Multi-Tier Module Composition, SemVer Governance, & Automated Validation
"""

import sys
import time
import json
import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

# ANSI Color Codes for terminal UI
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    RED = "\033[31m"
    BG_BLUE = "\033[44m"
    WHITE = "\033[97m"

def print_header(title: str):
    print(f"\n{Color.BOLD}{Color.CYAN}{'='*72}{Color.RESET}")
    print(f"{Color.BOLD}{Color.WHITE} 🚀 {title.upper()}{Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}{'='*72}{Color.RESET}")

def print_step(step_num: int, title: str):
    print(f"\n{Color.BOLD}{Color.YELLOW}[STEP {step_num}] {Color.WHITE}{title}{Color.RESET}")
    print(f"{Color.DIM}{'-'*60}{Color.RESET}")

def print_success(msg: str):
    print(f"  {Color.GREEN}✔ [PASS]{Color.RESET} {msg}")

def print_warning(msg: str):
    print(f"  {Color.YELLOW}⚠ [WARN]{Color.RESET} {msg}")

def print_error(msg: str):
    print(f"  {Color.RED}✖ [FAIL]{Color.RESET} {msg}")

def print_info(label: str, value: str):
    print(f"  {Color.CYAN}➤ {label:24}:{Color.RESET} {Color.BOLD}{value}{Color.RESET}")

@dataclass
class ModuleContract:
    name: str
    version: str
    source: str
    inputs: Dict[str, Any]
    required_outputs: List[str]
    compliance_tags: Dict[str, str]

@dataclass
class EnterpriseModuleRegistry:
    modules: Dict[str, List[str]] = field(default_factory=lambda: {
        "terraform-aws-modules/vpc/aws": ["3.14.0", "4.0.0", "5.1.2", "5.8.0"],
        "enterprise-registry.internal.net/modules/security-group": ["1.0.0", "1.2.1", "2.0.0-rc1"],
        "enterprise-registry.internal.net/modules/eks-cluster": ["2.4.0", "2.5.0", "3.0.0"],
        "enterprise-registry.internal.net/modules/rds-aurora": ["1.8.0", "2.1.0", "2.2.0"]
    })

    def resolve_version(self, source: str, constraint: str) -> Optional[str]:
        if source not in self.modules:
            return None
        available = self.modules[source]
        # Simplified SemVer matching simulation (~> or >=)
        if constraint.startswith("~>"):
            base = constraint.replace("~>", "").strip()
            parts = base.split(".")
            prefix = ".".join(parts[:2])
            matching = [v for v in available if v.startswith(prefix)]
            return matching[-1] if matching else None
        elif constraint.startswith(">="):
            min_ver = constraint.replace(">=", "").strip()
            matching = [v for v in available if v >= min_ver]
            return matching[-1] if matching else None
        elif constraint in available:
            return constraint
        return available[-1] if available else None

class EnterprisePipelineSimulator:
    def __init__(self):
        self.registry = EnterpriseModuleRegistry()
        self.composition_stack: List[ModuleContract] = []

    def simulate_contract_validation(self, contract: ModuleContract) -> bool:
        print_info("Module Name", contract.name)
        print_info("Declared Source", contract.source)
        print_info("Version Pinning", contract.version)

        # 1. SemVer enforcement check
        semver_regex = r"^(\~>|\>\=|\=)?\s*\d+\.\d+(\.\d+)?(-[a-zA-Z0-9.]+)?$"
        if not re.match(semver_regex, contract.version.strip()):
            print_error(f"Invalid Semantic Version constraint '{contract.version}' - violates Enterprise Golden Rules.")
            return False
        print_success("Semantic Versioning syntax adheres to SemVer 2.0 specifications.")

        # 2. Private registry resolution check
        resolved = self.registry.resolve_version(contract.source, contract.version)
        if not resolved:
            print_error(f"Cannot resolve module '{contract.source}' with constraint '{contract.version}' in private registry.")
            return False
        print_success(f"Private Registry Lock resolved artifact version: {Color.BOLD}{resolved}{Color.RESET}")

        # 3. Mandatory Tags & Governance Policy Check
        required_tags = {"Environment", "CostCenter", "Owner", "ManagedBy"}
        provided_tags = set(contract.compliance_tags.keys())
        missing_tags = required_tags - provided_tags
        if missing_tags:
            print_error(f"Enterprise Governance Policy Violated: Missing mandatory tags {missing_tags}")
            return False
        print_success(f"Mandatory Enterprise metadata tags validated: {list(provided_tags)}")

        # 4. Interface signature check
        for req_out in contract.required_outputs:
            print_success(f"Export contract satisfied: Output attribute '{req_out}' registered.")

        return True

    def build_enterprise_topology(self):
        # 1. Core Network Layer
        self.composition_stack.append(ModuleContract(
            name="vpc_core",
            version="~> 5.1.0",
            source="terraform-aws-modules/vpc/aws",
            inputs={"cidr": "10.100.0.0/16", "azs": ["ap-southeast-1a", "ap-southeast-1b", "ap-southeast-1c"]},
            required_outputs=["vpc_id", "private_subnets", "database_subnets"],
            compliance_tags={"Environment": "production", "CostCenter": "CC-9021", "Owner": "platform-eng", "ManagedBy": "terraform"}
        ))

        # 2. Security & Zero Trust Layer
        self.composition_stack.append(ModuleContract(
            name="security_perimeter",
            version="~> 1.2.0",
            source="enterprise-registry.internal.net/modules/security-group",
            inputs={"vpc_id": "${module.vpc_core.vpc_id}", "enable_egress_filter": True},
            required_outputs=["ingress_sg_id", "egress_sg_id"],
            compliance_tags={"Environment": "production", "CostCenter": "CC-9021", "Owner": "infosec-team", "ManagedBy": "terraform"}
        ))

        # 3. Compute Tier (Kubernetes EKS)
        self.composition_stack.append(ModuleContract(
            name="k8s_platform",
            version=">= 2.5.0",
            source="enterprise-registry.internal.net/modules/eks-cluster",
            inputs={
                "vpc_id": "${module.vpc_core.vpc_id}",
                "subnet_ids": "${module.vpc_core.private_subnets}",
                "security_group_id": "${module.security_perimeter.ingress_sg_id}",
                "cluster_version": "1.30"
            },
            required_outputs=["cluster_endpoint", "oidc_provider_arn"],
            compliance_tags={"Environment": "production", "CostCenter": "CC-9021", "Owner": "platform-eng", "ManagedBy": "terraform"}
        ))

        # 4. Data Layer (Aurora PostgreSQL HA)
        self.composition_stack.append(ModuleContract(
            name="db_persistence",
            version="~> 2.1.0",
            source="enterprise-registry.internal.net/modules/rds-aurora",
            inputs={
                "vpc_id": "${module.vpc_core.vpc_id}",
                "database_subnets": "${module.vpc_core.database_subnets}",
                "database_name": "app_production",
                "engine": "aurora-postgresql"
            },
            required_outputs=["writer_endpoint", "reader_endpoint", "cluster_arn"],
            compliance_tags={"Environment": "production", "CostCenter": "CC-9021", "Owner": "dba-ops", "ManagedBy": "terraform"}
        ))

    def run_preflight_checks(self):
        print_step(1, "Module Contract & Static Interface Governance Verification")
        all_passed = True
        for idx, mod in enumerate(self.composition_stack, 1):
            print(f"\n{Color.MAGENTA}--- Auditing Sub-Module #{idx}: {mod.name} ---{Color.RESET}")
            time.sleep(0.15)
            if not self.simulate_contract_validation(mod):
                all_passed = False
        return all_passed

    def run_graph_synthesis(self):
        print_step(2, "Generating Multi-Tier Module Dependency DAG (Directed Acyclic Graph)")
        time.sleep(0.2)
        dependencies = {
            "module.vpc_core": [],
            "module.security_perimeter": ["module.vpc_core"],
            "module.k8s_platform": ["module.vpc_core", "module.security_perimeter"],
            "module.db_persistence": ["module.vpc_core"]
        }

        for node, deps in dependencies.items():
            dep_str = ", ".join(deps) if deps else "[ROOT LEVEL (Independent)]"
            print(f"  {Color.CYAN}⬢ Node:{Color.RESET} {Color.BOLD}{node:<30}{Color.RESET} ↳ Depends On: {Color.GREEN}{dep_str}{Color.RESET}")
        print_success("Dependency graph has 0 cyclic loops. Graph resolution order: Tier 1 (VPC) ➔ Tier 2 (Sec/DB) ➔ Tier 3 (EKS)")

    def run_terratest_simulation(self):
        print_step(3, "Automated Contract Testing Simulation (Terratest / Go Harness)")
        tests = [
            ("TestVpcSubnetCidrAllocation", "PASS", "0.32s"),
            ("TestSecurityGroupStrictEgressRule", "PASS", "0.19s"),
            ("TestEksClusterOidcProviderSignature", "PASS", "0.85s"),
            ("TestAuroraClusterStorageEncryptionAtRest", "PASS", "0.41s")
        ]
        for test_name, status, duration in tests:
            time.sleep(0.12)
            print(f"  {Color.BLUE}=== RUN   {Color.WHITE}{test_name}{Color.RESET}")
            print(f"  {Color.GREEN}--- PASS: {Color.BOLD}{test_name} ({duration}){Color.RESET}")
        print_success("All Terratest integration and contract assertions passed successfully!")

    def execute_live_run(self):
        print_header("Enterprise Terraform Module Reusability & Architecture Lab")
        print(f"{Color.DIM}Repository standard: BAB-05 Enterprise Architecture & Component Reuse{Color.RESET}")
        print(f"{Color.DIM}Target Environment: AWS Multi-AZ Production Architecture{Color.RESET}")

        self.build_enterprise_topology()
        success = self.run_preflight_checks()
        if not success:
            print_error("Pipeline halted due to architectural contract violations.")
            sys.exit(1)

        self.run_graph_synthesis()
        self.run_terratest_simulation()

        print_step(4, "Enterprise Production Release Summary")
        print(f"\n  {Color.BG_BLUE}{Color.WHITE}{Color.BOLD} STATUS: ARCHITECTURE PASSED ENTERPRISE SPECIFICATION {Color.RESET}")
        print(f"  Total Reusable Modules Orchestrated : {Color.BOLD}{len(self.composition_stack)}{Color.RESET}")
        print(f"  Semantic Pinning Compliance         : {Color.GREEN}100% Validated{Color.RESET}")
        print(f"  Tagging & Security Standard         : {Color.GREEN}100% Policy-As-Code Compliant{Color.RESET}")
        print(f"  Artifact Promotion State            : {Color.CYAN}Ready for 'terraform apply -auto-approve'{Color.RESET}\n")

def main():
    simulator = EnterprisePipelineSimulator()
    simulator.execute_live_run()

if __name__ == "__main__":
    main()
