#!/usr/bin/env python3
"""
Lab Exercise: AWS Security Governance & Regulatory Compliance Architecture Simulation
BAB-08: Cloud Security, Governance, and Regulatory Compliance

This runnable interactive simulation models an enterprise multi-account AWS environment:
1. AWS Organizations & Service Control Policies (SCP) Guardrails
2. AWS Control Tower & Guardrails / Detective Controls
3. AWS Config Rule Evaluation & Auto-Remediation (Non-compliant S3 Bucket Public Access)
4. GuardDuty Threat Detection & Security Hub Centralized Event Routing
5. KMS Customer Managed Key (CMK) Envelope Encryption & Audit Trail Integrity
"""

import sys
import time
import json
import hashlib
import uuid
from typing import Dict, List, Any

# ANSI Terminal Colors
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
    BG_RED = "\033[41m"

def print_header(title: str):
    print(f"\n{Color.BG_BLUE}{Color.WHITE}{Color.BOLD} === [AWS GOVERNANCE LAB] {title.upper()} === {Color.RESET}\n")

def print_success(msg: str):
    print(f"{Color.GREEN}✔ [SUCCESS]{Color.RESET} {msg}")

def print_warning(msg: str):
    print(f"{Color.YELLOW}⚠ [WARNING]{Color.RESET} {msg}")

def print_alert(msg: str):
    print(f"{Color.RED}{Color.BOLD}✖ [SECURITY ALERT]{Color.RESET} {msg}")

def print_info(msg: str):
    print(f"{Color.CYAN}ℹ [INFO]{Color.RESET} {msg}")

def simulate_latency(duration_sec: float = 0.4):
    time.sleep(duration_sec)

# -----------------------------------------------------------------------------
# Module 1: Organizations SCP Engine Simulation
# -----------------------------------------------------------------------------
class OrganizationGovernanceEngine:
    def __init__(self):
        self.accounts = {
            "111122223333": {"name": "Management-Account", "ou": "Root"},
            "222233334444": {"name": "Security-Audit-Account", "ou": "Core-OU"},
            "333344445555": {"name": "Workload-Prod-Account", "ou": "Workloads-OU"},
            "444455556666": {"name": "Workload-Dev-Account", "ou": "Sandbox-OU"},
        }
        self.scps = [
            {
                "PolicyId": "p-deny-leave-org",
                "PolicyName": "DenyLeavingOrganization",
                "Effect": "Deny",
                "Actions": ["organizations:LeaveOrganization"],
                "Resources": ["*"],
                "TargetOU": "Root"
            },
            {
                "PolicyId": "p-protect-guardduty",
                "PolicyName": "DenyDisablingSecurityServices",
                "Effect": "Deny",
                "Actions": [
                    "guardduty:DeleteDetector",
                    "guardduty:DisassociateFromMasterAccount",
                    "securityhub:DisableSecurityHub",
                    "config:DeleteConfigRule"
                ],
                "Resources": ["*"],
                "TargetOU": "Workloads-OU"
            },
            {
                "PolicyId": "p-restrict-regions",
                "PolicyName": "DenyUnapprovedRegions",
                "Effect": "Deny",
                "Actions": ["ec2:*", "rds:*"],
                "Condition": {"StringNotEquals": {"aws:RequestedRegion": ["ap-southeast-1", "ap-southeast-3"]}},
                "TargetOU": "Workloads-OU"
            }
        ]

    def evaluate_request(self, account_id: str, action: str, region: str = "ap-southeast-3") -> bool:
        account = self.accounts.get(account_id)
        if not account:
            print_alert(f"Account ID {account_id} not registered in Organization hierarchy.")
            return False

        print_info(f"Evaluating action '{action}' on account {account['name']} ({account_id}) in region {region}...")
        simulate_latency(0.3)

        for scp in self.scps:
            # Check OU match
            if scp["TargetOU"] == "Root" or scp["TargetOU"] == account["ou"]:
                if action in scp.get("Actions", []):
                    print_alert(f"Action blocked by SCP: '{scp['PolicyName']}' (Target OU: {scp['TargetOU']})")
                    return False
                
                # Check condition on region restriction
                if "Condition" in scp and action in scp["Actions"]:
                    allowed_regions = scp["Condition"]["StringNotEquals"]["aws:RequestedRegion"]
                    if region not in allowed_regions:
                        print_alert(f"Action '{action}' blocked by SCP '{scp['PolicyName']}': Region '{region}' not in permitted whitelist {allowed_regions}!")
                        return False

        print_success(f"Action '{action}' evaluated through Organization SCPs: ALLOWED")
        return True

# -----------------------------------------------------------------------------
# Module 2: AWS Config & Automated Drift Remediation
# -----------------------------------------------------------------------------
class ConfigComplianceEngine:
    def __init__(self):
        self.resources = [
            {"id": "s3-corp-finance-raw", "type": "AWS::S3::Bucket", "public_access_block": True, "encrypted": True, "compliant": True},
            {"id": "s3-public-assets-unsecured", "type": "AWS::S3::Bucket", "public_access_block": False, "encrypted": False, "compliant": False},
            {"id": "ebs-vol-0a9b8c7d6e5f4", "type": "AWS::EC2::Volume", "encrypted": False, "compliant": False},
            {"id": "iam-role-devops-admin", "type": "AWS::IAM::Role", "has_permission_boundary": True, "compliant": True},
        ]

    def scan_environment(self):
        print_info("Executing AWS Config Managed Rules continuous evaluation against CIS AWS Foundations Benchmark v3.0...")
        simulate_latency(0.5)
        for res in self.resources:
            status_color = Color.GREEN if res["compliant"] else Color.RED
            status_text = "COMPLIANT" if res["compliant"] else "NON-COMPLIANT"
            print(f"  • Resource: {res['id']:<30} Type: {res['type']:<20} Status: {status_color}{status_text}{Color.RESET}")

    def remediate_drift(self):
        print_info("Triggering SSM Automation Document 'AWS-PublishSNSAndEnableS3BlockPublicAccess'...")
        for res in self.resources:
            if not res["compliant"] and res["type"] == "AWS::S3::Bucket":
                simulate_latency(0.4)
                print_warning(f"Remediating resource drift on {res['id']}...")
                res["public_access_block"] = True
                res["encrypted"] = True
                res["compliant"] = True
                print_success(f"S3 Public Access Block & SSE-KMS enforcement enabled on {res['id']}.")

# -----------------------------------------------------------------------------
# Module 3: KMS Envelope Encryption Simulation
# -----------------------------------------------------------------------------
class KMSEnvelopeEncryptionEngine:
    def __init__(self):
        self.cmk_arn = "arn:aws:kms:ap-southeast-3:222233334444:key/mrk-8a4b2c1d-90fe-4c12-b12a-331e92d8e411"
        self.master_key = b"EnterpriseSecurityKMSMasterKeySecret_2026!"

    def generate_data_key(self) -> Dict[str, str]:
        print_info(f"Calling kms:GenerateDataKey with CMK: {self.cmk_arn}")
        simulate_latency(0.3)
        raw_plaintext_key = uuid.uuid4().hex.encode('utf-8')
        
        # Envelope encryption: encrypt plaintext DEK with CMK
        cipher_dek = hashlib.sha256(self.master_key + raw_plaintext_key).hexdigest()
        return {
            "PlaintextDataKey": raw_plaintext_key.decode('utf-8'),
            "CiphertextBlob": f"kms-enc:{cipher_dek}"
        }

    def encrypt_payload(self, sensitive_data: str) -> Dict[str, str]:
        data_keys = self.generate_data_key()
        dek = data_keys["PlaintextDataKey"].encode('utf-8')
        
        # XOR/Hash simulation of data payload encryption with DEK
        encrypted_bytes = bytearray()
        for i, char in enumerate(sensitive_data.encode('utf-8')):
            encrypted_bytes.append(char ^ dek[i % len(dek)])
        
        payload_ciphertext = encrypted_bytes.hex()
        
        # Zeroize Plaintext DEK from RAM memory (Defense in Depth)
        print_info("Zeroizing Plaintext DEK from host memory buffer...")
        del data_keys["PlaintextDataKey"]
        
        return {
            "CiphertextBlob": data_keys["CiphertextBlob"],
            "PayloadCiphertext": payload_ciphertext,
            "KeyArn": self.cmk_arn
        }

# -----------------------------------------------------------------------------
# Module 4: CloudTrail Immutability & Audit Trail Verification
# -----------------------------------------------------------------------------
class CloudTrailAuditEngine:
    def __init__(self):
        self.log_chain = []
        self._seed_logs()

    def _seed_logs(self):
        events = [
            {"event": "ConsoleLogin", "user": "alice-admin", "src_ip": "203.0.113.15", "mfa": True},
            {"event": "CreateSecurityGroup", "user": "terraform-runner", "src_ip": "10.100.4.12", "mfa": True},
            {"event": "PutBucketPolicy", "user": "bob-developer", "src_ip": "198.51.100.89", "mfa": False},
        ]
        prev_digest = "0000000000000000000000000000000000000000000000000000000000000000"
        for evt in events:
            evt["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            evt_str = json.dumps(evt, sort_keys=True)
            current_digest = hashlib.sha256((prev_digest + evt_str).encode('utf-8')).hexdigest()
            self.log_chain.append({
                "record": evt,
                "previous_hash": prev_digest,
                "hash": current_digest
            })
            prev_digest = current_digest

    def verify_log_integrity(self) -> bool:
        print_info("Validating CloudTrail Digest Files against AWS KMS Signatures & Hash Trees...")
        simulate_latency(0.4)
        for i, entry in enumerate(self.log_chain):
            evt_str = json.dumps(entry["record"], sort_keys=True)
            recalculated = hashlib.sha256((entry["previous_hash"] + evt_str).encode('utf-8')).hexdigest()
            if recalculated != entry["hash"]:
                print_alert(f"Audit log tampering detected at index #{i}!")
                return False
            print_success(f"Log Record #{i+1} [{entry['record']['event']}] verified. Hash: {entry['hash'][:16]}...")
        return True

    def tamper_log(self, index: int = 1):
        if 0 <= index < len(self.log_chain):
            self.log_chain[index]["record"]["user"] = "attacker-compromised"
            print_warning(f"Simulated unauthorized modification injected into Log Entry #{index+1}.")

# -----------------------------------------------------------------------------
# Interactive CLI Workflow
# -----------------------------------------------------------------------------
def run_interactive_lab():
    org_engine = OrganizationGovernanceEngine()
    config_engine = ConfigComplianceEngine()
    kms_engine = KMSEnvelopeEncryptionEngine()
    audit_engine = CloudTrailAuditEngine()

    while True:
        print_header("Enterprise Security & Governance Simulation Hub")
        print(f"{Color.BOLD}PILIHAN LAB EXERCISE:{Color.RESET}")
        print("  1. Uji Evaluasi AWS Organizations & Service Control Policies (SCP)")
        print("  2. Audit Kepatuhan AWS Config & Auto-Remediation SSM Document")
        print("  3. Simulasi Envelope Encryption KMS Customer Managed Key (CMK)")
        print("  4. Verifikasi Integritas Audit Trail CloudTrail Log File Validation")
        print("  5. Jalankan Simulasi Komprehensif Otomatis (End-to-End Pipeline)")
        print("  0. Keluar")

        try:
            choice = input(f"\n{Color.YELLOW}Masukkan pilihan (0-5): {Color.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting lab...")
            break

        if choice == "1":
            print_header("Test SCP Guardrails")
            print("1. Coba hapus AWS GuardDuty dari Prod Workload Account")
            print("2. Coba deploy EC2 di region terlarang (us-east-1)")
            print("3. Coba deploy EC2 di region sah (ap-southeast-3)")
            sub = input("Pilih skenario (1-3): ").strip()
            if sub == "1":
                org_engine.evaluate_request("333344445555", "guardduty:DeleteDetector")
            elif sub == "2":
                org_engine.evaluate_request("333344445555", "ec2:RunInstances", region="us-east-1")
            elif sub == "3":
                org_engine.evaluate_request("333344445555", "ec2:RunInstances", region="ap-southeast-3")
            else:
                print_warning("Pilihan tidak valid.")

        elif choice == "2":
            print_header("AWS Config & Automated Remediation")
            config_engine.scan_environment()
            remedy = input(f"\nJalankan automated remediation untuk sumber daya non-compliant? (y/n): ").strip().lower()
            if remedy == "y":
                config_engine.remediate_drift()
                print("\nStatus pasca remediasi:")
                config_engine.scan_environment()

        elif choice == "3":
            print_header("KMS Envelope Encryption")
            secret = input("Masukkan data sensitif yang ingin dienkripsi (mis: 'CreditCard:4532-1234-5678-9010'): ").strip()
            if not secret:
                secret = "PatientMedicalRecord:CONFIDENTIAL-PCI-PHI-DATA-999"
            enc_result = kms_engine.encrypt_payload(secret)
            print_success("Payload berhasil dienkripsi!")
            print(f"  • Encrypted Data (Hex) : {enc_result['PayloadCiphertext'][:40]}... (Total {len(enc_result['PayloadCiphertext'])} chars)")
            print(f"  • Ciphertext DEK Blob  : {enc_result['CiphertextBlob']}")
            print(f"  • Target KMS CMK ARN   : {enc_result['KeyArn']}")

        elif choice == "4":
            print_header("CloudTrail Log Integrity")
            audit_engine.verify_log_integrity()
            tamper = input(f"\nSimulasikan serangan modifikasi log CloudTrail oleh adversary? (y/n): ").strip().lower()
            if tamper == "y":
                audit_engine.tamper_log(1)
                print_info("Menjalankan ulang validasi integritas...")
                if not audit_engine.verify_log_integrity():
                    print_alert("Integritas log GAGAL! Digest SHA-256 CloudTrail tidak cocok dengan catatan lokal.")

        elif choice == "5":
            print_header("Menjalankan Simulasi Komprehensif End-to-End")
            print_info("Step 1: Mengevaluasi Organization SCP Enforcement...")
            org_engine.evaluate_request("333344445555", "guardduty:DeleteDetector")
            org_engine.evaluate_request("333344445555", "ec2:RunInstances", region="ap-southeast-3")
            
            print_info("\nStep 2: Menjalankan AWS Config Rules Audit...")
            config_engine.scan_environment()
            config_engine.remediate_drift()
            
            print_info("\nStep 3: Memproses KMS Envelope Encryption...")
            kms_engine.encrypt_payload("EnterpriseFinancialLedger_Q3_CONFIDENTIAL")
            
            print_info("\nStep 4: Audit Trail Immutability Verification...")
            audit_engine.verify_log_integrity()
            print_success("Semua pemeriksaan pilar keamanan AWS telah berhasil dieksekusi.")

        elif choice == "0":
            print_info("Sesi lab selesai. Membersihkan resource session...")
            break
        else:
            print_warning("Pilihan tidak dikenal. Silakan masukkan angka yang tersedia.")

        input(f"\n{Color.DIM}Tekan [Enter] untuk melanjutkan ke menu utama...{Color.RESET}")

if __name__ == "__main__":
    run_interactive_lab()
