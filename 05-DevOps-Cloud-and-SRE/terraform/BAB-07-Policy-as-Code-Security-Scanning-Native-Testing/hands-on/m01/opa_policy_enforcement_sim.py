#!/usr/bin/env python3
"""
Simulasi Engine Policy-as-Code (OPA & Security Scanning) untuk Terraform Execution Plan.
Skrip ini mengurai file JSON representasi dari `terraform plan` dan mengevaluasi serangkaian
aturan tata kelola keamanan (Security & Compliance Guardrails) secara deterministik tanpa dependensi eksternal.

Penggunaan:
    python3 opa_policy_enforcement_sim.py --plan sample_plan.json
"""

import sys
import json
import re
import argparse
from typing import List, Dict, Any, Tuple

# ==============================================================================
# DEFINISI KEBIJAKAN & GUARDRAILS (SECURITY RULES)
# ==============================================================================

class PolicyViolation:
    def __init__(self, rule_id: str, severity: str, resource_address: str, message: str):
        self.rule_id = rule_id
        self.severity = severity  # CRITICAL, HIGH, MEDIUM, LOW
        self.resource_address = resource_address
        self.message = message

    def to_dict(self) -> Dict[str, str]:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "resource": self.resource_address,
            "message": self.message
        }

class TerraformPlanEvaluator:
    def __init__(self, plan_data: Dict[str, Any]):
        self.plan_data = plan_data
        self.resource_changes = plan_data.get("resource_changes", [])
        self.violations: List[PolicyViolation] = []

    def _get_active_resources(self, resource_type: str = None) -> List[Dict[str, Any]]:
        """Mengambil resource yang sedang dibuat (create) atau diupdate (update)."""
        filtered = []
        for res in self.resource_changes:
            actions = res.get("change", {}).get("actions", [])
            if "create" in actions or "update" in actions:
                if resource_type is None or res.get("type") == resource_type:
                    filtered.append(res)
        return filtered

    # --------------------------------------------------------------------------
    # RULE 1: S3 Bucket Public Access Block
    # --------------------------------------------------------------------------
    def evaluate_s3_public_access(self):
        rule_id = "SEC-001"
        severity = "CRITICAL"
        
        s3_pabs = self._get_active_resources("aws_s3_bucket_public_access_block")
        for pab in s3_pabs:
            after = pab.get("change", {}).get("after", {})
            block_public_acls = after.get("block_public_acls", False)
            block_public_policy = after.get("block_public_policy", False)
            
            if not (block_public_acls and block_public_policy):
                self.violations.append(PolicyViolation(
                    rule_id=rule_id,
                    severity=severity,
                    resource_address=pab.get("address", "unknown"),
                    message="S3 Public Access Block harus mengaktifkan 'block_public_acls' dan 'block_public_policy'."
                ))

    # --------------------------------------------------------------------------
    # RULE 2: Security Group Ingress 0.0.0.0/0 pada Port Administratif
    # --------------------------------------------------------------------------
    def evaluate_security_group_open_ports(self):
        rule_id = "SEC-002"
        severity = "CRITICAL"
        restricted_ports = [22, 3389, 21, 23, 1433, 3306, 5432]
        
        sgs = self._get_active_resources("aws_security_group")
        for sg in sgs:
            after = sg.get("change", {}).get("after", {})
            ingress_rules = after.get("ingress", []) or []
            
            for rule in ingress_rules:
                cidr_blocks = rule.get("cidr_blocks", [])
                from_port = rule.get("from_port", 0)
                to_port = rule.get("to_port", 0)
                
                if "0.0.0.0/0" in cidr_blocks:
                    for bad_port in restricted_ports:
                        if from_port <= bad_port <= to_port:
                            self.violations.append(PolicyViolation(
                                rule_id=rule_id,
                                severity=severity,
                                resource_address=sg.get("address", "unknown"),
                                message=f"Security Group membuka port administratif berbahaya ({bad_port}) ke publik (0.0.0.0/0)."
                            ))

    # --------------------------------------------------------------------------
    # RULE 3: Kepatuhan Tagging Korporat
    # --------------------------------------------------------------------------
    def evaluate_mandatory_tags(self):
        rule_id = "GOV-001"
        severity = "HIGH"
        required_tags = ["Environment", "OwnerEmail", "CostCenter"]
        email_regex = r"^[\w\.-]+@fintech-corp\.com$"
        cost_center_regex = r"^CC-\d{4}$"

        taggable_types = ["aws_s3_bucket", "aws_security_group", "aws_instance"]

        for res in self.resource_changes:
            if res.get("type") in taggable_types:
                after = res.get("change", {}).get("after", {})
                tags = after.get("tags") or {}
                address = res.get("address", "unknown")

                # Cek eksistensi tag
                for req in required_tags:
                    if req not in tags:
                        self.violations.append(PolicyViolation(
                            rule_id=rule_id,
                            severity=severity,
                            resource_address=address,
                            message=f"Resource kehilangan tag wajib: '{req}'."
                        ))

                # Validasi format OwnerEmail
                if "OwnerEmail" in tags and not re.match(email_regex, tags["OwnerEmail"]):
                    self.violations.append(PolicyViolation(
                        rule_id=rule_id,
                        severity="MEDIUM",
                        resource_address=address,
                        message=f"Tag OwnerEmail '{tags['OwnerEmail']}' tidak valid. Harus berdomain '@fintech-corp.com'."
                    ))

                # Validasi format CostCenter
                if "CostCenter" in tags and not re.match(cost_center_regex, tags["CostCenter"]):
                    self.violations.append(PolicyViolation(
                        rule_id=rule_id,
                        severity="MEDIUM",
                        resource_address=address,
                        message=f"Tag CostCenter '{tags['CostCenter']}' tidak valid. Format harus CC-XXXX (misal: CC-1024)."
                    ))

    # --------------------------------------------------------------------------
    # RULE 4: Enkripsi S3 Bucket
    # --------------------------------------------------------------------------
    def evaluate_s3_encryption(self):
        rule_id = "SEC-003"
        severity = "HIGH"
        
        # Cari semua aws_s3_bucket yang dibuat
        s3_buckets = self._get_active_resources("aws_s3_bucket")
        # Cari resource enkripsi terkait
        sse_configs = self._get_active_resources("aws_s3_bucket_server_side_encryption_configuration")
        
        # Ekstrak target bucket yang terenkripsi
        configured_buckets = set()
        for sse in sse_configs:
            after = sse.get("change", {}).get("after", {})
            bucket = after.get("bucket")
            if bucket:
                configured_buckets.add(bucket)

        for b in s3_buckets:
            bucket_name = b.get("name")
            address = b.get("address", "unknown")
            # Jika bucket tidak memiliki konfigurasi enkripsi di plan
            if not sse_configs:
                self.violations.append(PolicyViolation(
                    rule_id=rule_id,
                    severity=severity,
                    resource_address=address,
                    message="S3 Bucket dibuat tanpa konfigurasi Server-Side Encryption (SSE)."
                ))

    def run_all_checks(self) -> List[PolicyViolation]:
        self.evaluate_s3_public_access()
        self.evaluate_security_group_open_ports()
        self.evaluate_mandatory_tags()
        self.evaluate_s3_encryption()
        return self.violations

# ==============================================================================
# SAMPLE PLAN MOCK GENERATOR (JIKA TIDAK ADA INPUT FILE)
# ==============================================================================

def generate_mock_plan() -> Dict[str, Any]:
    """Menghasilkan representasi tfplan.json sintetis dengan beberapa celah keamanan."""
    return {
        "format_version": "1.2",
        "terraform_version": "1.7.0",
        "resource_changes": [
            {
                "address": "aws_s3_bucket.bad_bucket",
                "type": "aws_s3_bucket",
                "name": "bad_bucket",
                "change": {
                    "actions": ["create"],
                    "after": {
                        "bucket_prefix": "insecure-data-",
                        "tags": {
                            "Environment": "dev",
                            "OwnerEmail": "hacker@gmail.com",  # SALAH: Domain luar
                            "CostCenter": "CC-99"              # SALAH: Kurang dari 4 digit
                        }
                    }
                }
            },
            {
                "address": "aws_s3_bucket_public_access_block.bad_bucket_block",
                "type": "aws_s3_bucket_public_access_block",
                "name": "bad_bucket_block",
                "change": {
                    "actions": ["create"],
                    "after": {
                        "block_public_acls": False,           # SALAH: Celah keamanan publik
                        "block_public_policy": True
                    }
                }
            },
            {
                "address": "aws_security_group.insecure_sg",
                "type": "aws_security_group",
                "name": "insecure_sg",
                "change": {
                    "actions": ["create"],
                    "after": {
                        "name": "insecure_sg",
                        "tags": {
                            "Environment": "prod"
                            # SALAH: Missing OwnerEmail & CostCenter
                        },
                        "ingress": [
                            {
                                "from_port": 22,              # SALAH: SSH terbuka ke dunia
                                "to_port": 22,
                                "protocol": "tcp",
                                "cidr_blocks": ["0.0.0.0/0"]
                            },
                            {
                                "from_port": 443,
                                "to_port": 443,
                                "protocol": "tcp",
                                "cidr_blocks": ["0.0.0.0/0"]
                            }
                        ]
                    }
                }
            }
        ]
    }

# ==============================================================================
# MAIN CLI RUNNER
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="Terraform Plan Security & Compliance Policy Engine")
    parser.add_argument("--plan", type=str, help="Path ke file tfplan.json hasil export", required=False)
    args = parser.parse_args()

    if args.plan:
        try:
            with open(args.plan, "r") as f:
                plan_data = json.load(f)
            print(f"[INFO] Membaca plan dari file: {args.plan}")
        except Exception as e:
            print(f"[FATAL ERROR] Gagal membuka file plan: {e}")
            sys.exit(2)
    else:
        print("[INFO] Parameter --plan tidak disertakan. Menggunakan Mock Plan bawaan skrip...")
        plan_data = generate_mock_plan()

    evaluator = TerraformPlanEvaluator(plan_data)
    violations = evaluator.run_all_checks()

    # Cetak Hasil
    print("=" * 80)
    print("           LAPORAN EVALUASI KEBIJAKAN TERRAFORM (POLICY-AS-CODE)          ")
    print("=" * 80)

    if not violations:
        print("\n\033[92m[PASSED] Seluruh guardrails terpenuhi! Tidak ada pelanggaran kebijakan terdeteksi.\033[0m\n")
        sys.exit(0)

    print(f"\n\033[91m[FAILED] Terdeteksi {len(violations)} pelanggaran kebijakan keamanan!\033[0m\n")
    
    crit_count = 0
    high_count = 0
    med_count = 0

    for idx, v in enumerate(violations, start=1):
        color = "\033[91m" if v.severity in ["CRITICAL", "HIGH"] else "\033[93m"
        reset = "\033[0m"
        
        if v.severity == "CRITICAL":
            crit_count += 1
        elif v.severity == "HIGH":
            high_count += 1
        else:
            med_count += 1

        print(f"{idx}. {color}[{v.severity}] {v.rule_id}{reset} pada resource: {v.resource_address}")
        print(f"   Pesan: {v.message}")
        print("-" * 80)

    print("\nRingkasan Pelanggaran:")
    print(f" - CRITICAL : {crit_count}")
    print(f" - HIGH     : {high_count}")
    print(f" - MEDIUM   : {med_count}")
    print("=" * 80)

    # Gagalkan pipeline CI jika ada pelanggaran CRITICAL atau HIGH
    if crit_count > 0 or high_count > 0:
        print("\n\033[91m[EXIT 1] Eksekusi dihentikan: Pelanggaran CRITICAL/HIGH memblokir deployment.\033[0m\n")
        sys.exit(1)
    else:
        print("\n\033[93m[EXIT 0] Peringatan: Hanya pelanggaran MEDIUM yang ditemukan, deployment diizinkan dengan catatan.\033[0m\n")
        sys.exit(0)

if __name__ == "__main__":
    main()