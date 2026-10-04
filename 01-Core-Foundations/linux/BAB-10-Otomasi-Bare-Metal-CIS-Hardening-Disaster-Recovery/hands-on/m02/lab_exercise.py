#!/usr/bin/env python3
"""
Lab Hands-on: Otomasi Bare-Metal, Hardening Standar CIS, dan Disaster Recovery (DR)
Modul 02 Deep Dive - Linux Core Foundations

Skrip ini mensimulasikan siklus hidup infrastruktur server Linux enterprise:
1. Bare-Metal Provisioning State Machine (PXE, Kickstart/Ignition, Kernel Bootstrapping).
2. CIS Benchmark Auditing & Automated Remediation Engine (Kernel Sysctl, Perms, SSHD).
3. Disaster Recovery (DR) Engine dengan verifikasi integritas kriptografis dan metrik RTO/RPO.
"""

import os
import sys
import time
import json
import hashlib
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum

# --- ANSI Formatting Helpers ---
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"

def log_header(title: str) -> None:
    print(f"\n{Color.BOLD}{Color.MAGENTA}{'='*70}{Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN} [STAGE] {title.upper()}{Color.RESET}")
    print(f"{Color.BOLD}{Color.MAGENTA}{'='*70}{Color.RESET}")

def log_step(action: str, target: str, status: str = "RUNNING") -> None:
    print(f"  {Color.BLUE}▸{Color.RESET} {action:<28} [{Color.BOLD}{target:<22}{Color.RESET}] -> {Color.YELLOW}{status}{Color.RESET}")

def log_success(message: str) -> None:
    print(f"    {Color.GREEN}✔ SUCCESS:{Color.RESET} {message}")

def log_warn(message: str) -> None:
    print(f"    {Color.YELLOW}⚠ WARNING:{Color.RESET} {message}")

def log_fail(message: str) -> None:
    print(f"    {Color.RED}✖ FAILED:{Color.RESET} {message}")


# ==============================================================================
# BAGIAN 1: BARE-METAL PROVISIONING ENGINE (PXE & IGNITION SIMULATION)
# ==============================================================================

class ProvisionState(Enum):
    DISCOVERED = "PXE_DHCP_DISCOVER"
    BOOTSTRAPPING = "TFTP_KERNEL_FETCH"
    PARTITIONING = "STORAGE_LAYOUT_SETUP"
    IGNITION_APPLIED = "POST_CONFIG_HOOKS"
    READY = "SYSTEM_ONLINE"

@dataclass
class BareMetalHost:
    mac_address: str
    ip_address: str
    hostname: str
    disk_layout: Dict[str, str] = field(default_factory=dict)
    state: ProvisionState = ProvisionState.DISCOVERED

class BareMetalProvisioner:
    """Mensimulasikan deployment OS bare-metal via network orchestration."""

    def __init__(self, host: BareMetalHost):
        self.host = host

    def run_pipeline(self) -> None:
        log_header(f"Provisioning Bare-Metal: {self.host.hostname} ({self.host.mac_address})")

        # 1. DHCP / PXE Handshake
        log_step("Acquiring IP via DHCP", self.host.mac_address)
        time.sleep(0.3)
        self.host.state = ProvisionState.BOOTSTRAPPING
        log_success(f"IP {self.host.ip_address} assigned via Option 66/67.")

        # 2. Kernel/Initramfs Fetch
        log_step("Loading Kernel & Initrd", "vmlinuz-linux-lts")
        time.sleep(0.4)
        self.host.state = ProvisionState.PARTITIONING
        log_success("Kernel unpacked in RAM. Initramfs running root pivot.")

        # 3. Partitioning & Filesystem Layout
        log_step("Partitioning NVMe", "/dev/nvme0n1")
        time.sleep(0.3)
        self.host.disk_layout = {
            "/dev/nvme0n1p1": "vfat (EFI, 512MB)",
            "/dev/nvme0n1p2": "ext4 (/boot, 1024MB)",
            "/dev/nvme0n1p3": "xfs (LVM-PV-system, Remainder)"
        }
        log_success(f"Partitions created: {list(self.host.disk_layout.keys())}")

        # 4. Ignition / Cloud-Init stage
        log_step("Injecting Configs", "Ignition/Post-Hooks")
        time.sleep(0.3)
        self.host.state = ProvisionState.IGNITION_APPLIED
        log_success("SSH authorized keys & base network profiles baked.")

        self.host.state = ProvisionState.READY
        print(f"  {Color.BOLD}{Color.GREEN}Node {self.host.hostname} successfully provisioned to state {self.host.state.value}.{Color.RESET}")


# ==============================================================================
# BAGIAN 2: CIS BENCHMARK AUDITING & AUTOMATED REMEDIATION ENGINE
# ==============================================================================

@dataclass
class CISRule:
    rule_id: str
    description: str
    target_param: str
    expected_value: Any
    current_value: Any
    remediable: bool = True

class CISHardeningEngine:
    """
    Engine untuk audit dan auto-remediasi berbasis CIS Linux Benchmark
    (Sysctl kernel hardening, filesystem attributes, dan secure SSH policies).
    """

    def __init__(self):
        # State tiruan kernel sysctl dan konfigurasi sistem
        self.system_state: Dict[str, Any] = {
            "net.ipv4.ip_forward": 1,                     # Insecure by default
            "net.ipv4.conf.all.accept_source_route": 1,    # Insecure
            "net.ipv4.tcp_syncookies": 0,                 # Insecure
            "fs.protected_hardlinks": 0,                  # Insecure
            "fs.protected_symlinks": 0,                   # Insecure
            "/etc/shadow:permissions": "0644",            # World readable! Critically insecure
            "sshd:PermitRootLogin": "yes",                # Insecure
            "sshd:MaxAuthTries": "10",                    # Non-compliant
        }

        self.benchmark_rules: List[CISRule] = [
            CISRule("CIS-3.1.1", "Disable IP Forwarding", "net.ipv4.ip_forward", 0),
            CISRule("CIS-3.2.1", "Disable Source Routed Packet Acceptance", "net.ipv4.conf.all.accept_source_route", 0),
            CISRule("CIS-3.2.8", "Enable TCP SYN Cookies", "net.ipv4.tcp_syncookies", 1),
            CISRule("CIS-4.1.1", "Ensure Protected Hardlinks Enabled", "fs.protected_hardlinks", 1),
            CISRule("CIS-4.1.2", "Ensure Protected Symlinks Enabled", "fs.protected_symlinks", 1),
            CISRule("CIS-6.1.3", "Verify /etc/shadow Permissions", "/etc/shadow:permissions", "0600"),
            CISRule("CIS-5.2.2", "SSH: PermitRootLogin Disabled", "sshd:PermitRootLogin", "no"),
            CISRule("CIS-5.2.5", "SSH: MaxAuthTries set to <= 4", "sshd:MaxAuthTries", "4"),
        ]

    def audit(self) -> Tuple[int, int]:
        """Melakukan audit kepatuhan terhadap baseline CIS."""
        log_header("Audit Kepatuhan Keamanan (CIS Linux Benchmark)")
        passed = 0
        failed = 0

        for rule in self.benchmark_rules:
            curr = self.system_state.get(rule.target_param)
            rule.current_value = curr
            if curr == rule.expected_value:
                log_step(rule.rule_id, rule.description, f"{Color.GREEN}PASS{Color.RESET}")
                passed += 1
            else:
                log_step(rule.rule_id, rule.description, f"{Color.RED}FAIL{Color.RESET}")
                log_warn(f"Value '{curr}' violates baseline (Expected: '{rule.expected_value}')")
                failed += 1

        total = passed + failed
        score = (passed / total) * 100
        print(f"\n  Skor Kepatuhan CIS: {Color.BOLD}{score:.1f}%{Color.RESET} (Pass: {passed}, Fail: {failed})")
        return passed, failed

    def remediate(self) -> None:
        """Menerapkan auto-remediasi konfigurasi yang melanggar standar."""
        log_header("Automated Remediation Engine (CIS Baseline Enforcement)")

        for rule in self.benchmark_rules:
            curr = self.system_state.get(rule.target_param)
            if curr != rule.expected_value:
                log_step("Applying Fix", rule.rule_id)
                time.sleep(0.1)
                self.system_state[rule.target_param] = rule.expected_value
                log_success(f"Mutated '{rule.target_param}': {curr} -> {rule.expected_value}")

        print(f"\n  {Color.BOLD}{Color.GREEN}Remediasi selesai. Kernel params & file permissions diperbarui.{Color.RESET}")


# ==============================================================================
# BAGIAN 3: DISASTER RECOVERY & CRYPTOGRAPHIC RESTORATION ENGINE
# ==============================================================================

@dataclass
class SnapshotBlock:
    block_id: str
    data_content: str
    sha256_hash: str

class DisasterRecoveryEngine:
    """
    Mensimulasikan pembuatan snapshot block-level, deteksi kerusakan data
    (bit-rot/ransomware), serta validasi SLA: RTO (Recovery Time Objective)
    dan RPO (Recovery Point Objective).
    """

    def __init__(self):
        self.primary_volume: Dict[str, str] = {}
        self.snapshot_vault: List[SnapshotBlock] = []
        self.recovery_point_timestamp: float = 0.0

    @staticmethod
    def _compute_hash(data: str) -> str:
        return hashlib.sha256(data.encode('utf-8')).hexdigest()

    def generate_live_data(self) -> None:
        """Mengisi data transaksi aktif ke partisi root."""
        self.primary_volume = {
            "blk_001": "SYSTEM_BOOT_SECTOR_INTEGRITY_DATA_UUID=4fa9",
            "blk_002": "CORE_SERVICES_DAEMON_CONFIG: postgresql, nginx, chronyd",
            "blk_003": "SECURE_CREDENTIALS_STORE: /etc/security/opensecret",
            "blk_004": "AUDIT_LOG_JOURNAL_SEGMENT_INDEX_000994",
        }

    def take_snapshot(self) -> None:
        """Snapshot point-in-time dengan integritas kriptografis per-block."""
        log_header("Disaster Recovery: Membuat Snapshot Point-In-Time")
        self.snapshot_vault.clear()
        self.recovery_point_timestamp = time.time()

        for blk_id, content in self.primary_volume.items():
            checksum = self._compute_hash(content)
            self.snapshot_vault.append(SnapshotBlock(blk_id, content, checksum))
            log_step("Snapshot Block", blk_id)
            log_success(f"Digest: {checksum[:16]}... (Immutable Lock Applied)")

        log_success(f"Snapshot Vault menyimpan {len(self.snapshot_vault)} block.")

    def simulate_disaster_event(self) -> None:
        """Mensimulasikan korupsi storage catastrophic."""
        log_header("Simulasi Bencana: Silent Bit-Rot & Disk Corruption")
        log_warn("Penyusupan terdeteksi: Partisi sistem mengalami korupsi block!")

        # Korup blk_001 dan hancurkan blk_003
        self.primary_volume["blk_001"] = "CORRUPTED_ZERO_BYTE_DATA_PAYLOAD_NULL"
        self.primary_volume["blk_003"] = "RANSOMWARE_ENCRYPTED_DATA_PAYLOAD_XX"
        del self.primary_volume["blk_004"]

        print(f"  {Color.RED}Volume primer rusak parah. Sistem crash.{Color.RESET}")

    def execute_recovery(self) -> None:
        """Pemulihan DR otomatis dengan kalkulasi RTO dan verifikasi RPO."""
        log_header("Prosedur Disaster Recovery: Failover & Validasi Integritas")
        start_recovery_time = time.time()

        corrupted_blocks = 0
        restored_blocks = 0

        # Verifikasi terhadap vault
        for snap_block in self.snapshot_vault:
            blk_id = snap_block.block_id
            curr_data = self.primary_volume.get(blk_id, "")
            curr_hash = self._compute_hash(curr_data)

            log_step("Verifying Integrity", blk_id)
            if curr_hash != snap_block.sha256_hash:
                log_fail(f"Hash mismatch! Live: {curr_hash[:8]} vs Snapshot: {snap_block.sha256_hash[:8]}")
                corrupted_blocks += 1

                # Restorasi
                log_step("Restoring Block", blk_id, f"{Color.CYAN}REBUILDING{Color.RESET}")
                time.sleep(0.15)
                self.primary_volume[blk_id] = snap_block.data_content
                restored_blocks += 1
                log_success(f"Block {blk_id} dipulihkan dari Vault.")
            else:
                log_success(f"Block {blk_id} utuh.")

        end_recovery_time = time.time()

        # Kalkulasi Metrik SLA
        actual_rto = end_recovery_time - start_recovery_time
        actual_rpo = start_recovery_time - self.recovery_point_timestamp

        print(f"\n{Color.BOLD}{Color.GREEN}--- METRIK EVALUASI DISASTER RECOVERY (DR) ---{Color.RESET}")
        print(f"  Total Block Bermasalah : {Color.RED}{corrupted_blocks}{Color.RESET}")
        print(f"  Total Block Dipulihkan : {Color.GREEN}{restored_blocks}{Color.RESET}")
        print(f"  Actual RTO (Waktu Pulih): {Color.CYAN}{actual_rto:.3f} detik{Color.RESET} (Target SLA: < 5.00s)")
        print(f"  Actual RPO (Lag Data)  : {Color.CYAN}{actual_rpo:.3f} detik{Color.RESET} (Target SLA: < 60.00s)")

        if actual_rto < 5.0 and corrupted_blocks == restored_blocks:
            print(f"  Status DR              : {Color.BOLD}{Color.GREEN}PASSED SLA CRITERIA{Color.RESET}\n")
        else:
            print(f"  Status DR              : {Color.BOLD}{Color.RED}FAILED SLA CRITERIA{Color.RESET}\n")


# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================

def main():
    print(f"{Color.BOLD}{Color.BLUE}")
    print("=" * 70)
    print("  ENTERPRISE LINUX INFRASTRUCTURE ORCHESTRATION BENCHMARK")
    print("  Automated Bare-Metal Provisioning, CIS Hardening & Disaster Recovery")
    print("=" * 70)
    print(f"{Color.RESET}")

    # Step 1: Bare-Metal Provisioning
    host = BareMetalHost(
        mac_address="52:54:00:a8:99:bf",
        ip_address="192.168.100.45",
        hostname="prod-k8s-worker-01"
    )
    provisioner = BareMetalProvisioner(host)
    provisioner.run_pipeline()

    # Step 2: CIS Hardening Engine
    cis_engine = CISHardeningEngine()
    passed, failed = cis_engine.audit()

    if failed > 0:
        cis_engine.remediate()
        print("\n  Melakukan Re-Audit pasca remediasi...")
        cis_engine.audit()

    # Step 3: Disaster Recovery Simulation
    dr_engine = DisasterRecoveryEngine()
    dr_engine.generate_live_data()
    dr_engine.take_snapshot()
    dr_engine.simulate_disaster_event()
    dr_engine.execute_recovery()

    print(f"{Color.BOLD}{Color.GREEN}Seluruh siklus validasi infrastruktur berhasil dituntaskan tanpa error.{Color.RESET}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Color.RED}Eksekusi lab dihentikan pengguna.{Color.RESET}")
        sys.exit(1)