#!/usr/bin/env python3
"""
Lab Exercise: Policy-as-Code, Security Scanning, and Native Testing Simulator
BAB-07: Policy-as-Code, Security Scanning, & Native Testing (Terraform)
"""

import sys
import time
import json
from dataclasses import dataclass
from typing import List, Dict, Any

# ANSI Terminal Color Codes
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
BG_RED = "\033[41m"
BG_GREEN = "\033[42m"
BG_BLUE = "\033[44m"


@dataclass
class PolicyFinding:
    rule_id: str
    resource: str
    severity: str
    description: str
    passed: bool


# Mock Terraform Plan JSON payload representing multi-tier cloud infrastructure
MOCK_TF_PLAN: Dict[str, Any] = {
    "format_version": "1.2",
    "terraform_version": "1.9.0",
    "resource_changes": [
        {
            "address": "aws_s3_bucket.data_lake",
            "type": "aws_s3_bucket",
            "name": "data_lake",
            "change": {
                "actions": ["create"],
                "after": {
                    "bucket": "prod-analytics-datalake-apac",
                    "tags": {"Environment": "production", "Owner": "DataPlatform"},
                },
            },
        },
        {
            "address": "aws_s3_bucket_server_side_encryption_configuration.data_lake",
            "type": "aws_s3_bucket_server_side_encryption_configuration",
            "name": "data_lake",
            "change": {
                "actions": ["create"],
                "after": {
                    "rule": [
                        {
                            "apply_server_side_encryption_by_default": {
                                "sse_algorithm": "aws:kms",
                                "kms_master_key_id": "arn:aws:kms:ap-southeast-1:123456789012:key/mrk-datalake",
                            }
                        }
                    ]
                },
            },
        },
        {
            "address": "aws_s3_bucket_public_access_block.data_lake",
            "type": "aws_s3_bucket_public_access_block",
            "name": "data_lake",
            "change": {
                "actions": ["create"],
                "after": {
                    "block_public_acls": True,
                    "block_public_policy": True,
                    "ignore_public_acls": True,
                    "restrict_public_buckets": True,
                },
            },
        },
        {
            "address": "aws_security_group.ingress_web",
            "type": "aws_security_group",
            "name": "ingress_web",
            "change": {
                "actions": ["create"],
                "after": {
                    "description": "Public web ingress",
                    "ingress": [
                        {
                            "cidr_blocks": ["0.0.0.0/0"],
                            "from_port": 443,
                            "to_port": 443,
                            "protocol": "tcp",
                        },
                        {
                            "cidr_blocks": ["0.0.0.0/0"],
                            "from_port": 22,
                            "to_port": 22,
                            "protocol": "tcp",
                        },
                    ],
                },
            },
        },
        {
            "address": "aws_db_instance.primary_rds",
            "type": "aws_db_instance",
            "name": "primary_rds",
            "change": {
                "actions": ["create"],
                "after": {
                    "allocated_storage": 100,
                    "engine": "postgres",
                    "engine_version": "16.1",
                    "instance_class": "db.m6g.xlarge",
                    "multi_az": True,
                    "publicly_accessible": False,
                    "storage_encrypted": True,
                    "deletion_protection": True,
                    "backup_retention_period": 14,
                },
            },
        },
    ],
}


def print_banner() -> None:
    print(f"\n{BOLD}{CYAN}========================================================================{RESET}")
    print(f"{BOLD}{CYAN}   TERRAFORM ENTERPRISE QUALITY & SECURITY GATEWAY (SIMULATOR)        {RESET}")
    print(f"{BOLD}{CYAN}   BAB-07: Policy-as-Code | Static Scanners | Native HCL Testing       {RESET}")
    print(f"{BOLD}{CYAN}========================================================================{RESET}\n")


def spinner_delay(label: str, duration: float = 1.0) -> None:
    chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    start = time.time()
    idx = 0
    while time.time() - start < duration:
        sys.stdout.write(f"\r{CYAN}{chars[idx % len(chars)]}{RESET} {label}...")
        sys.stdout.flush()
        time.sleep(0.08)
        idx += 1
    sys.stdout.write(f"\r{GREEN}✔{RESET} {label}... Done!\n")
    sys.stdout.flush()


def run_checkov_scanner(plan: Dict[str, Any]) -> List[PolicyFinding]:
    print(f"\n{BOLD}{MAGENTA}[1/3] EXECUTING STATIC SECURITY SCAN (Checkov / tfsec Engine){RESET}")
    spinner_delay("Evaluating CIS AWS Foundation Benchmarks & NIST 800-53", 1.2)
    findings: List[PolicyFinding] = []

    for rc in plan["resource_changes"]:
        addr = rc["address"]
        rtype = rc["type"]
        after = rc["change"].get("after", {})

        if rtype == "aws_security_group":
            ingress_list = after.get("ingress", [])
            ssh_open = any(
                ("0.0.0.0/0" in ing.get("cidr_blocks", []) and ing.get("from_port") <= 22 <= ing.get("to_port"))
                for ing in ingress_list
            )
            findings.append(
                PolicyFinding(
                    rule_id="CKV_AWS_24",
                    resource=addr,
                    severity="CRITICAL",
                    description="Ensure no security groups allow SSH from 0.0.0.0/0",
                    passed=not ssh_open,
                )
            )

        elif rtype == "aws_db_instance":
            encrypted = after.get("storage_encrypted", False)
            findings.append(
                PolicyFinding(
                    rule_id="CKV_AWS_16",
                    resource=addr,
                    severity="HIGH",
                    description="Ensure RDS storage is encrypted at rest",
                    passed=encrypted,
                )
            )
            del_prot = after.get("deletion_protection", False)
            findings.append(
                PolicyFinding(
                    rule_id="CKV_AWS_354",
                    resource=addr,
                    severity="MEDIUM",
                    description="Ensure RDS has deletion protection enabled",
                    passed=del_prot,
                )
            )

        elif rtype == "aws_s3_bucket":
            tags = after.get("tags", {})
            has_env = "Environment" in tags and tags["Environment"] in ["production", "staging"]
            findings.append(
                PolicyFinding(
                    rule_id="CKV_AWS_TAG_ENV",
                    resource=addr,
                    severity="LOW",
                    description="Ensure S3 bucket has standard Environment tag",
                    passed=has_env,
                )
            )

    for f in findings:
        status_tag = f"{GREEN}[PASSED]{RESET}" if f.passed else f"{RED}[FAILED]{RESET}"
        sev_color = RED if f.severity in ["CRITICAL", "HIGH"] else YELLOW
        print(f"  {status_tag} {BOLD}{f.rule_id}{RESET} ({sev_color}{f.severity}{RESET}) - {f.resource}")
        print(f"         {DIM}{f.description}{RESET}")

    return findings


def run_opa_rego_policies(plan: Dict[str, Any]) -> List[PolicyFinding]:
    print(f"\n{BOLD}{BLUE}[2/3] EVALUATING POLICY-AS-CODE RULES (Open Policy Agent / Rego){RESET}")
    spinner_delay("Evaluating organizational boundary constraints via OPA client", 1.0)
    findings: List[PolicyFinding] = []

    # Rule 1: Mandatory KMS Customer Managed Key enforcement on S3
    sse_resources = [rc for rc in plan["resource_changes"] if rc["type"] == "aws_s3_bucket_server_side_encryption_configuration"]
    kms_ok = False
    for sse in sse_resources:
        rules = sse["change"]["after"].get("rule", [])
        for r in rules:
            algo = r.get("apply_server_side_encryption_by_default", {}).get("sse_algorithm")
            key_id = r.get("apply_server_side_encryption_by_default", {}).get("kms_master_key_id", "")
            if algo == "aws:kms" and "arn:aws:kms" in key_id:
                kms_ok = True

    findings.append(
        PolicyFinding(
            rule_id="OPA-FINSERV-001",
            resource="aws_s3_bucket_server_side_encryption_configuration.*",
            severity="CRITICAL",
            description="All S3 storage must be encrypted using dedicated KMS CMK",
            passed=kms_ok,
        )
    )

    # Rule 2: Multi-AZ requirement for production relational databases
    rds_resources = [rc for rc in plan["resource_changes"] if rc["type"] == "aws_db_instance"]
    for rds in rds_resources:
        multi_az = rds["change"]["after"].get("multi_az", False)
        findings.append(
            PolicyFinding(
                rule_id="OPA-RELIABILITY-004",
                resource=rds["address"],
                severity="HIGH",
                description="Production database clusters must be provisioned across Multi-AZ",
                passed=multi_az,
            )
        )

    for f in findings:
        status_tag = f"{GREEN}[ALLOWED]{RESET}" if f.passed else f"{RED}[DENIED]{RESET}"
        sev_color = RED if f.severity == "CRITICAL" else YELLOW
        print(f"  {status_tag} {BOLD}{f.rule_id}{RESET} ({sev_color}{f.severity}{RESET}) - {f.resource}")
        print(f"         {DIM}{f.description}{RESET}")

    return findings


def run_terraform_native_tests() -> List[Dict[str, Any]]:
    print(f"\n{BOLD}{CYAN}[3/3] EXECUTING TERRAFORM NATIVE TEST FRAMEWORK (`terraform test`){RESET}")
    spinner_delay("Initializing mock providers and running tests/*.tftest.hcl", 1.4)

    test_runs = [
        {
            "file": "tests/unit_networking.tftest.hcl",
            "run": "verify_public_subnet_cidr_allocation",
            "mode": "plan",
            "passed": True,
            "duration": "0.14s",
        },
        {
            "file": "tests/unit_database.tftest.hcl",
            "run": "enforce_automated_backups_retention",
            "mode": "plan",
            "passed": True,
            "duration": "0.22s",
        },
        {
            "file": "tests/integration_s3.tftest.hcl",
            "run": "verify_bucket_ownership_controls_applied",
            "mode": "apply",
            "passed": True,
            "duration": "1.08s",
        },
    ]

    for t in test_runs:
        stat = f"{GREEN}PASS{RESET}" if t["passed"] else f"{RED}FAIL{RESET}"
        print(f"  {BOLD}run \"{t['run']}\"{RESET} in {DIM}{t['file']}{RESET} [{t['mode']}] ... {stat} ({t['duration']})")

    return test_runs


def remediate_vulnerabilities(plan: Dict[str, Any]) -> None:
    print(f"\n{YELLOW}{BOLD}⚡ AUTO-REMEDIATION / PATCHING DISCOVERED DRIFT & FLAWS{RESET}")
    spinner_delay("Patching Security Group ingress rules (restricting SSH to corporate bastion CIDR)", 0.8)

    for rc in plan["resource_changes"]:
        if rc["type"] == "aws_security_group":
            ingress = rc["change"]["after"].get("ingress", [])
            for ing in ingress:
                if 22 in [ing.get("from_port"), ing.get("to_port")]:
                    ing["cidr_blocks"] = ["10.200.5.0/24"]  # Corporate Bastion / VPN
    print(f"{GREEN}✔ Security Group updated: SSH restricted to internal Bastion 10.200.5.0/24.{RESET}\n")


def display_dashboard(checkov: List[PolicyFinding], opa: List[PolicyFinding], tests: List[Dict[str, Any]]) -> bool:
    all_findings = checkov + opa
    failed = [f for f in all_findings if not f.passed]

    print(f"\n{BOLD}════════════════════════════════════════════════════════════════════════{RESET}")
    print(f"{BOLD}                        PIPELINE AUDIT SUMMARY                         {RESET}")
    print(f"{BOLD}════════════════════════════════════════════════════════════════════════{RESET}")
    print(f" Total Static Security Checks   : {len(checkov)}")
    print(f" Total OPA/Rego Policy Rules    : {len(opa)}")
    print(f" Total Native HCL Test Suites   : {len(tests)}")
    print(f" Violations Detected            : {RED if failed else GREEN}{len(failed)}{RESET}")

    if failed:
        print(f"\n{BG_RED}{WHITE}{BOLD} ✖ DEPLOYMENT REJECTED: Pipeline halted due to critical policy violations. {RESET}\n")
        return False
    else:
        print(f"\n{BG_GREEN}{WHITE}{BOLD} ✔ DEPLOYMENT APPROVED: All compliance gates and unit tests cleared! {RESET}\n")
        return True


def interactive_menu():
    print_banner()
    plan = json.loads(json.dumps(MOCK_TF_PLAN))

    while True:
        print(f"{BOLD}Main Menu:{RESET}")
        print(" [1] Run Full CI/CD Gate Verification (Scan -> Policy -> Native Test)")
        print(" [2] Run Auto-Remediation on Security Group Ingress")
        print(" [3] Inspect Terraform Plan AST (JSON format)")
        print(" [4] Exit")

        choice = input(f"\n{BOLD}Select an option [1-4]: {RESET}").strip()

        if choice == "1":
            checkov_res = run_checkov_scanner(plan)
            opa_res = run_opa_rego_policies(plan)
            test_res = run_terraform_native_tests()
            display_dashboard(checkov_res, opa_res, test_res)
        elif choice == "2":
            remediate_vulnerabilities(plan)
        elif choice == "3":
            print(f"\n{DIM}{json.dumps(plan, indent=2)}{RESET}\n")
        elif choice == "4":
            print(f"{CYAN}Exiting simulator. Have a secure day!{RESET}\n")
            break
        else:
            print(f"{RED}Invalid option selected.{RESET}\n")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--non-interactive":
        print_banner()
        p = json.loads(json.dumps(MOCK_TF_PLAN))
        c = run_checkov_scanner(p)
        o = run_opa_rego_policies(p)
        t = run_terraform_native_tests()
        display_dashboard(c, o, t)
        remediate_vulnerabilities(p)
        c2 = run_checkov_scanner(p)
        display_dashboard(c2, o, t)
    else:
        interactive_menu()
