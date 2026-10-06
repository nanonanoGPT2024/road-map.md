#!/usr/bin/env python3
"""
Lab Exercise: Enterprise Security, Resiliency & Disaster Recovery in Elasticsearch
Module: hands-on/m01/lab_exercise.py
Topics:
  - RBAC & Document/Field-Level Security (DLS & FLS)
  - TLS/SSL Transport & REST Encryption Verification
  - Snapshot Lifecycle Management (SLM) & Disaster Recovery
  - Cross-Cluster Replication (CCR) & Failover Simulation
"""

import sys
import time
import json
import hashlib
from typing import Dict, List, Any, Optional

# ANSI Color Palette
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[92m"
BLUE = "\033[94m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
DIM = "\033[2m"

def print_header(title: str):
    width = 75
    print(f"\n{BLUE}{BOLD}{'=' * width}{RESET}")
    print(f"{CYAN}{BOLD} [LAB] {title.center(width - 8)} {RESET}")
    print(f"{BLUE}{BOLD}{'=' * width}{RESET}\n")

def print_step(step_num: int, title: str):
    print(f"\n{YELLOW}{BOLD}>>> Step {step_num}: {title}{RESET}")

def print_success(msg: str):
    print(f"  {GREEN}[✓] SUCCESS:{RESET} {msg}")

def print_info(msg: str):
    print(f"  {BLUE}[i] INFO:{RESET} {msg}")

def print_warning(msg: str):
    print(f"  {YELLOW}[!] WARNING:{RESET} {msg}")

def print_denied(msg: str):
    print(f"  {RED}[✗] ACCESS DENIED:{RESET} {msg}")


class SecurityRealmSimulator:
    """Simulates Elasticsearch RBAC, DLS (Document-Level Security), and FLS (Field-Level Security)."""

    def __init__(self):
        # Sample enterprise dataset: financial audit logs
        self.raw_data = [
            {"id": "DOC-101", "department": "finance", "user": "alice", "salary": 95000, "status": "CONFIDENTIAL", "audit_notes": "Q1 bonus approval"},
            {"id": "DOC-102", "department": "engineering", "user": "bob", "salary": 85000, "status": "INTERNAL", "audit_notes": "Infra budget request"},
            {"id": "DOC-103", "department": "finance", "user": "carol", "salary": 110000, "status": "RESTRICTED", "audit_notes": "Executive payroll review"},
            {"id": "DOC-104", "department": "marketing", "user": "dave", "salary": 72000, "status": "PUBLIC", "audit_notes": "Campaign costs"},
        ]
        
        # Role definitions with DLS query filters and allowed FLS fields
        self.roles = {
            "superuser": {
                "dls_filter": lambda doc: True,
                "fls_allowed_fields": ["id", "department", "user", "salary", "status", "audit_notes"]
            },
            "finance_auditor": {
                "dls_filter": lambda doc: doc["department"] == "finance",
                "fls_allowed_fields": ["id", "department", "user", "salary", "status"]  # 'audit_notes' masked
            },
            "general_analyst": {
                "dls_filter": lambda doc: doc["status"] in ["INTERNAL", "PUBLIC"],
                "fls_allowed_fields": ["id", "department", "user", "status"]  # 'salary' and 'audit_notes' stripped
            }
        }

    def execute_secured_query(self, username: str, role_name: str) -> List[Dict[str, Any]]:
        print_info(f"Authenticating user '{BOLD}{username}{RESET}' with role '{CYAN}{role_name}{RESET}'...")
        if role_name not in self.roles:
            print_denied(f"Role '{role_name}' does not exist.")
            return []

        role = self.roles[role_name]
        dls_filter = role["dls_filter"]
        allowed_fields = role["fls_allowed_fields"]

        results = []
        for doc in self.raw_data:
            # 1. Document-Level Security (DLS) Evaluation
            if not dls_filter(doc):
                continue

            # 2. Field-Level Security (FLS) Masking/Filtering
            filtered_doc = {k: v for k, v in doc.items() if k in allowed_fields}
            results.append(filtered_doc)

        return results


class TLSTransportSimulator:
    """Simulates mutual TLS (mTLS) certificate validation between Elasticsearch cluster nodes."""

    @staticmethod
    def simulate_node_handshake(node_name: str, cert_dn: str, trusted_ca_dn: str) -> bool:
        print_info(f"Initiating TLS v1.3 transport handshake with node: {BOLD}{node_name}{RESET}")
        print_info(f"Subject DN: {DIM}{cert_dn}{RESET}")
        
        # Simulated certificate authority verification
        if "CN=Elastic-Internal-CA" in trusted_ca_dn:
            time.sleep(0.15)
            fingerprint = hashlib.sha256(cert_dn.encode()).hexdigest()[:16]
            print_success(f"Certificate chain verified. SHA-256 fingerprint: {fingerprint}")
            print_success(f"Cipher suite negotiated: TLS_AES_256_GCM_SHA384 (Transport Layer Secured)")
            return True
        else:
            print_denied(f"Untrusted Root CA in certificate chain: {trusted_ca_dn}")
            return False


class DisasterRecoverySimulator:
    """Simulates Snapshot Lifecycle Management (SLM) and Cross-Cluster Replication (CCR) failover."""

    def __init__(self):
        self.primary_cluster = "cluster-prod-dc1"
        self.dr_cluster = "cluster-dr-dc2"
        self.snapshots = []
        self.replicated_indices = {"orders_v1": {"follower_status": "PAUSED", "docs": 1500}}

    def create_slm_snapshot(self, repo_name: str, snapshot_name: str, doc_count: int) -> Dict[str, Any]:
        print_info(f"SLM Policy triggered on [{self.primary_cluster}]: Snapshotting to repository '{repo_name}'...")
        time.sleep(0.2)
        snapshot = {
            "snapshot": snapshot_name,
            "repository": repo_name,
            "state": "SUCCESS",
            "indices": ["orders_v1", "audit_logs_v1"],
            "total_docs": doc_count,
            "checksum": hashlib.md5(f"{snapshot_name}_{doc_count}".encode()).hexdigest()
        }
        self.snapshots.append(snapshot)
        print_success(f"Snapshot '{snapshot_name}' created successfully. Checksum: {snapshot['checksum']}")
        return snapshot

    def simulate_ccr_replication(self):
        print_info(f"Establishing Cross-Cluster Replication (CCR): {self.primary_cluster} -> {self.dr_cluster}")
        time.sleep(0.15)
        self.replicated_indices["orders_v1"]["follower_status"] = "ACTIVE_FOLLOWING"
        self.replicated_indices["orders_v1"]["docs"] = 2850
        print_success(f"Leader index 'orders_v1' replicated to Follower index 'orders_v1' with sync latency < 12ms.")

    def execute_disaster_recovery_failover(self):
        print_warning(f"CRITICAL ALERT: Primary Data Center [{self.primary_cluster}] UNREACHABLE!")
        print_info(f"Initiating automated Disaster Recovery (DR) runbook...")
        
        # Step A: Unfollow / Promote Follower Index
        time.sleep(0.2)
        print_step("DR-1", f"Decoupling follower index on {self.dr_cluster}")
        self.replicated_indices["orders_v1"]["follower_status"] = "UNFOLLOWED_LEADER_PROMOTED"
        print_success(f"Index 'orders_v1' promoted to standalone read-write index on {self.dr_cluster}.")

        # Step B: Point-In-Time Snapshot Restore for auxiliary indices
        print_step("DR-2", "Restoring auxiliary indices from S3 SLM Cold Snapshot")
        if self.snapshots:
            latest = self.snapshots[-1]
            print_success(f"Restored {latest['indices']} from snapshot '{latest['snapshot']}' (Docs: {latest['total_docs']}).")
        else:
            print_warning("No automated snapshot found. Generating emergency warm recovery.")

        print_success(f"DR Cluster [{self.dr_cluster}] is now serving 100% of production traffic! RTO: 35s | RPO: 0s.")


def run_interactive_simulation():
    print_header("Elasticsearch Enterprise Security, Resiliency & DR Simulator")

    sec_sim = SecurityRealmSimulator()
    tls_sim = TLSTransportSimulator()
    dr_sim = DisasterRecoverySimulator()

    while True:
        print(f"\n{BOLD}Select Lab Scenario:{RESET}")
        print(f"  {CYAN}1.{RESET} Verify Node-to-Node Transport TLS/mTLS Handshake")
        print(f"  {CYAN}2.{RESET} Test RBAC with Document & Field-Level Security (DLS/FLS)")
        print(f"  {CYAN}3.{RESET} Run Snapshot Lifecycle Management (SLM) Backup")
        print(f"  {CYAN}4.{RESET} Configure Cross-Cluster Replication (CCR)")
        print(f"  {CYAN}5.{RESET} Simulate Full DC Disaster & DR Failover (RPO/RTO)")
        print(f"  {CYAN}6.{RESET} Run Complete Security & Resiliency Benchmark")
        print(f"  {RED}0.{RESET} Exit")

        choice = input(f"\n{YELLOW}Enter option (0-6): {RESET}").strip()

        if choice == "0":
            print(f"\n{GREEN}Exiting lab. Keep clusters secure and resilient!{RESET}")
            break
        elif choice == "1":
            print_step(1, "Simulating mTLS Transport Verification")
            tls_sim.simulate_node_handshake(
                node_name="es-node-01.prod.internal",
                cert_dn="CN=es-node-01.prod.internal,OU=Search,O=Enterprise,C=ID",
                trusted_ca_dn="CN=Elastic-Internal-CA,O=Enterprise,C=ID"
            )
        elif choice == "2":
            print_step(2, "RBAC, DLS & FLS Evaluation")
            for user, role in [("bob", "general_analyst"), ("carol", "finance_auditor"), ("admin", "superuser")]:
                print(f"\n--- Testing Query as [{user}] (Role: {role}) ---")
                results = sec_sim.execute_secured_query(user, role)
                print(f"Returned {len(results)} document(s):")
                print(json.dumps(results, indent=2))
        elif choice == "3":
            print_step(3, "Snapshot Lifecycle Management (SLM)")
            dr_sim.create_slm_snapshot("s3-secure-backup-repo", "snap-daily-2026-10-06", 142500)
        elif choice == "4":
            print_step(4, "Cross-Cluster Replication (CCR)")
            dr_sim.simulate_ccr_replication()
        elif choice == "5":
            print_step(5, "Disaster Recovery Failover Simulation")
            dr_sim.execute_disaster_recovery_failover()
        elif choice == "6":
            run_automated_benchmark()
        else:
            print_warning("Invalid choice! Please select an option between 0 and 6.")


def run_automated_benchmark():
    """Runs a non-interactive end-to-end verification of all security & resiliency pillars."""
    print_header("Running Automated Enterprise Audit & Verification")

    # 1. TLS Check
    print_step(1, "Transport Layer Security (TLS/mTLS) Audit")
    tls_ok = TLSTransportSimulator.simulate_node_handshake(
        "es-node-02.internal",
        "CN=es-node-02.internal,OU=DataNodes,O=Enterprise",
        "CN=Elastic-Internal-CA,O=Enterprise"
    )
    assert tls_ok, "TLS handshake failed"

    # 2. DLS / FLS Check
    print_step(2, "RBAC, DLS, and FLS Compliance Audit")
    sec = SecurityRealmSimulator()
    analyst_docs = sec.execute_secured_query("analyst_user", "general_analyst")
    for doc in analyst_docs:
        assert "salary" not in doc, "Security Violation: Analyst saw salary field!"
        assert doc["status"] in ["INTERNAL", "PUBLIC"], "Security Violation: DLS breach on document status!"
    print_success("DLS & FLS policy enforcement 100% compliant.")

    # 3. SLM & DR Failover Check
    print_step(3, "SLM & Cross-Cluster Failover Validation")
    dr = DisasterRecoverySimulator()
    dr.create_slm_snapshot("glacier-repo", "snap-benchmark-01", 50000)
    dr.simulate_ccr_replication()
    dr.execute_disaster_recovery_failover()
    print_success("Automated DR test completed without data loss.\n")


if __name__ == "__main__":
    # If passed '--run-all', execute benchmark non-interactively
    if len(sys.argv) > 1 and sys.argv[1] == "--run-all":
        run_automated_benchmark()
    else:
        run_interactive_simulation()
