#!/usr/bin/env python3
"""
Lab Exercise: Enterprise Security, Resiliency & Disaster Recovery (Elasticsearch)
Bab 10: Enterprise Production Simulation (CCR, SLM, TLS/mTLS, RBAC/DLS/FLS, Multi-Region DR)
"""

import sys
import time
import json
import random
from typing import Dict, List, Any
from dataclasses import dataclass, field

# ANSI Escape Colors for Rich Terminal Display
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
BG_BLUE = "\033[44m"
BG_DARK = "\033[40m"


def header(title: str) -> None:
    print(f"\n{BOLD}{BG_BLUE}{WHITE}  === {title.upper()} ===  {RESET}\n")


def status_badge(ok: bool, text_ok="PASS / OPERATIONAL", text_fail="FAIL / DEGRADED") -> str:
    if ok:
        return f"{GREEN}[✔ {text_ok}]{RESET}"
    return f"{RED}[✘ {text_fail}]{RESET}"


@dataclass
class NodeTLSProfile:
    node_name: str
    transport_tls: bool = True
    http_tls: bool = True
    cipher_suite: str = "TLS_AES_256_GCM_SHA384"
    cert_expiry_days: int = 365
    mtls_enforced: bool = True


@dataclass
class RBACPrincipal:
    username: str
    roles: List[str]
    allowed_indices: List[str]
    dls_query: Dict[str, Any]
    fls_granted_fields: List[str]


@dataclass
class CCRPipeline:
    leader_cluster: str
    follower_cluster: str
    leader_index: str
    follower_index: str
    lag_operations: int = 0
    sync_status: str = "SYNCHRONIZED"


class EnterpriseClusterSimulator:
    def __init__(self):
        self.primary_region = "us-east-1 (Primary DC)"
        self.dr_region = "us-west-2 (Secondary DR)"
        self.active_region = self.primary_region
        self.nodes = [
            NodeTLSProfile("es-prod-master-01"),
            NodeTLSProfile("es-prod-master-02"),
            NodeTLSProfile("es-prod-master-03"),
            NodeTLSProfile("es-prod-data-01"),
            NodeTLSProfile("es-prod-data-02"),
        ]
        self.ccr = CCRPipeline(
            leader_cluster="cluster-primary",
            follower_cluster="cluster-dr",
            leader_index="fintech-transactions-2026",
            follower_index="fintech-transactions-2026-replica"
        )
        self.slm_policies = [
            {
                "name": "daily-s3-snapshot",
                "schedule": "0 30 1 * * ?",
                "repository": "s3-cold-backup",
                "retention_days": 90,
                "last_run": "2026-10-05T01:30:00Z",
                "last_status": "SUCCESS",
                "indices": ["fintech-*", "audit-logs-*"]
            }
        ]

    def print_banner(self) -> None:
        banner = f"""
{CYAN}╔═══════════════════════════════════════════════════════════════════════════╗
║   ELASTICSEARCH ENTERPRISE RESILIENCY & DISASTER RECOVERY LAB            ║
║   Architecture: Bab 10 - Security, SLM, CCR, RBAC & Multi-Region DR      ║
╚═══════════════════════════════════════════════════════════════════════════╝{RESET}
Active Region : {BOLD}{YELLOW}{self.active_region}{RESET}
Standby Region: {BOLD}{DIM}{self.dr_region}{RESET}
Cluster Health: {GREEN}GREEN (5 Nodes, Transport TLS mTLS Active){RESET}
"""
        print(banner)

    def test_mtls_transport(self) -> None:
        header("1. Transport Layer TLS & Mutual Authentication (mTLS)")
        print(f"{DIM}Memvalidasi handshake mTLS antar-node di internal transport layer (port 9300)...{RESET}")
        time.sleep(0.5)

        for node in self.nodes:
            status = status_badge(node.transport_tls and node.mtls_enforced, "mTLS VALID", "INSECURE")
            print(f" • Node: {BOLD}{node.node_name:<20}{RESET} Cipher: {CYAN}{node.cipher_suite}{RESET} -> {status}")
            print(f"   Cert Expiry: {node.cert_expiry_days} days remaining | HTTP TLS: {node.http_tls}")
        
        print(f"\n{GREEN}✔ Seluruh node master dan data mematuhi kebijakan Zero-Trust Transport Security.{RESET}")

    def test_rbac_dls_fls(self) -> None:
        header("2. Document-Level Security (DLS) & Field-Level Security (FLS)")
        user_auditor = RBACPrincipal(
            username="auditor_jkt",
            roles=["compliance_auditor"],
            allowed_indices=["fintech-transactions-*"],
            dls_query={"term": {"branch": "JKT-01"}},
            fls_granted_fields=["tx_id", "timestamp", "branch", "amount_masked", "currency"]
        )

        user_admin = RBACPrincipal(
            username="secops_admin",
            roles=["superuser"],
            allowed_indices=["*"],
            dls_query={"match_all": {}},
            fls_granted_fields=["*"]
        )

        print(f"Evaluasi Akses Pengguna: {BOLD}{user_auditor.username}{RESET}")
        print(f" - Roles          : {YELLOW}{user_auditor.roles}{RESET}")
        print(f" - DLS Filter     : {CYAN}{json.dumps(user_auditor.dls_query)}{RESET}")
        print(f" - FLS Masking    : {MAGENTA}{user_auditor.fls_granted_fields}{RESET}")
        print(f" - Protected Field: {RED}cc_number, pii_customer_ssn (STRIPPED){RESET}")

        sample_raw_doc = {
            "tx_id": "TX-9908124",
            "timestamp": "2026-10-06T05:15:00Z",
            "branch": "JKT-01",
            "amount_masked": "IDR 50.000.000",
            "currency": "IDR",
            "cc_number": "4111-2222-3333-4444",
            "pii_customer_ssn": "3171010190001"
        }

        print(f"\n{BOLD}Simulasi Query oleh '{user_auditor.username}' (Hasil Terfilter):{RESET}")
        filtered_doc = {k: v for k, v in sample_raw_doc.items() if k in user_auditor.fls_granted_fields}
        print(json.dumps(filtered_doc, indent=2))
        print(f"{GREEN}✔ DLS & FLS Policy aktif: Dokumen di luar cabang JKT-01 & data PII sensitif otomatis disembunyikan.{RESET}")

    def test_ccr_replication(self) -> None:
        header("3. Cross-Cluster Replication (CCR) Status")
        print(f"Leader Cluster   : {BOLD}{self.ccr.leader_cluster}{RESET} ({self.primary_region})")
        print(f"Follower Cluster : {BOLD}{self.ccr.follower_cluster}{RESET} ({self.dr_region})")
        print(f"Index Mapping    : {CYAN}{self.ccr.leader_index}{RESET} -> {MAGENTA}{self.ccr.follower_index}{RESET}")

        print("\nMenghitung replication lag dan seq_no checkpoint...")
        for i in range(1, 4):
            time.sleep(0.3)
            ops = random.randint(0, 5)
            self.ccr.lag_operations = ops
            print(f" [Tick {i}] Fetching shard stats... Lag: {YELLOW}{ops} operations{RESET} | Status: {GREEN}{self.ccr.sync_status}{RESET}")

        print(f"{GREEN}✔ CCR Pipeline sehat: RPO (Recovery Point Objective) < 2 detik.{RESET}")

    def test_slm_snapshot(self) -> None:
        header("4. Snapshot Lifecycle Management (SLM) & S3 Repository")
        policy = self.slm_policies[0]
        print(f"Policy Name    : {BOLD}{policy['name']}{RESET}")
        print(f"Repository     : {CYAN}{policy['repository']}{RESET} (Encrypted SSE-KMS)")
        print(f"Schedule Cron  : {YELLOW}{policy['schedule']}{RESET}")
        print(f"Target Indices : {policy['indices']}")
        print(f"Last Execution : {policy['last_run']} -> {GREEN}{policy['last_status']}{RESET}")

        print(f"\n{DIM}Memverifikasi Snapshot Integrity Checksum pada cold repository...{RESET}")
        time.sleep(0.4)
        print(f"{GREEN}✔ Checksum SHA-256 Valid: snapshot-2026-10-05-013000 terverifikasi immutable.{RESET}")

    def trigger_disaster_recovery_failover(self) -> None:
        header("5. EMERGENCY DRILL: Simulasi Failover Bencana Regional")
        print(f"{RED}{BOLD}[ALERT] Bencana terdeteksi di {self.primary_region}! Primary Data Center unreachable.{RESET}")
        print("Memulai prosedur Planned Disaster Recovery Failover...\n")

        steps = [
            ("Langkah 1: Pause & Unfollow CCR follower index", 0.6),
            ("Langkah 2: Promote follower index 'fintech-transactions-2026-replica' menjadi standalone read-write index", 0.8),
            ("Langkah 3: Reconfigure DNS Traffic Manager / Ingress Gateway ke Secondary DC", 0.7),
            ("Langkah 4: Update application connection strings to DR elasticsearch endpoint", 0.5),
            ("Langkah 5: Verifikasi write workload acceptance pada cluster us-west-2", 0.6)
        ]

        for step_desc, pause in steps:
            print(f" {YELLOW}⏳ {step_desc}...{RESET}")
            time.sleep(pause)
            print(f"    {GREEN}✔ OK{RESET}")

        self.active_region = self.dr_region
        print(f"\n{BOLD}{BG_BLUE}{WHITE}  FAILOVER SELESAI  {RESET}")
        print(f"Cluster aktif saat ini: {BOLD}{GREEN}{self.active_region}{RESET}")
        print(f"RTO tercapai: {BOLD}2.7 detik{RESET} (Jauh di bawah SLA enterprise 15 menit)")


def main():
    sim = EnterpriseClusterSimulator()
    sim.print_banner()

    while True:
        print(f"\n{BOLD}Menu Simulasi Lab Enterprise Security & DR:{RESET}")
        print(" [1] Uji Validasi Transport TLS & Node mTLS")
        print(" [2] Uji RBAC, Document-Level (DLS) & Field-Level Security (FLS)")
        print(" [3] Evaluasi Status Cross-Cluster Replication (CCR)")
        print(" [4] Audit Kebijakan Snapshot Lifecycle Management (SLM)")
        print(" [5] Jalankan Simulasi Failover Disaster Recovery (Multi-Region DR)")
        print(" [6] Jalankan Seluruh Skenario Produksi (End-to-End Test)")
        print(" [0] Keluar")

        try:
            choice = input(f"\n{CYAN}Pilih opsi [0-6]: {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nKeluar dari simulasi.")
            break

        if choice == "1":
            sim.test_mtls_transport()
        elif choice == "2":
            sim.test_rbac_dls_fls()
        elif choice == "3":
            sim.test_ccr_replication()
        elif choice == "4":
            sim.test_slm_snapshot()
        elif choice == "5":
            sim.trigger_disaster_recovery_failover()
        elif choice == "6":
            print(f"\n{BOLD}{MAGENTA}=== MENJALANKAN AUTOMATED FULL SUITE TEST ==={RESET}")
            sim.test_mtls_transport()
            sim.test_rbac_dls_fls()
            sim.test_ccr_replication()
            sim.test_slm_snapshot()
            sim.trigger_disaster_recovery_failover()
            print(f"\n{BOLD}{GREEN}Seluruh rangkaian uji enterprise keamanan & DR berhasil diselesaikan 100%.{RESET}\n")
        elif choice == "0":
            print("Selesai. Sampai jumpa di lab berikutnya!")
            break
        else:
            print(f"{RED}Pilihan tidak valid. Silakan masukkan angka 0-6.{RESET}")


if __name__ == "__main__":
    main()
