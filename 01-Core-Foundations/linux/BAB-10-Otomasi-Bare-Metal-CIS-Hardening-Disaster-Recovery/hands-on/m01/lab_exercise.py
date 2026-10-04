#!/usr/bin/env python3
"""
Lab Exercise M01: Otomasi Bare Metal, CIS Hardening, & Disaster Recovery Simulation
BAB 10 - Core Linux Engineering Lab
==================================================================================
Simulasi interaktif tingkat lanjut yang mencakup:
1. Bare-metal provisioning pipeline (iPXE, DHCP, Cloud-init / Kickstart).
2. CIS Linux Benchmark Level 1 & 2 Security Auditor & Auto-Remediation Engine.
3. Disaster Recovery (DR) & Backup Orchestration (RPO/RTO & Bare-Metal Restore).
"""

import sys
import time
import os
import hashlib
import json
from typing import Dict, List, Tuple

# ANSI Terminal Color Palette
class Color:
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
    BG_DARK = "\033[40m"


def print_banner():
    banner = f"""{Color.CYAN}{Color.BOLD}
================================================================================
   _     ___ _   _ _   ___  __   ___  ____    _  _____ ___ ___  _   _ 
  | |   |_ _| \ | | | | \ \/ /  / _ \|  _ \  / \|_   _|_ _/ _ \| \ | |
  | |    | ||  \| | | | |\  /  | | | | |_) |/ _ \ | |  | | | | |  \| |
  | |___ | || |\  | |_| |/  \  | |_| |  __/ ___ \| |  | | |_| | |\  |
  |_____|___|_| \_|\___//_/\_\  \___/|_| /_/   \_\_| |___\___/|_| \_|
                                                                      
  BAB 10: Bare-Metal Provisioning, CIS Hardening & Disaster Recovery
================================================================================{Color.RESET}"""
    print(banner)


def progress_step(description: str, duration: float = 0.3):
    print(f"  {Color.YELLOW}[RUNNING]{Color.RESET} {description}...", end="", flush=True)
    time.sleep(duration)
    print(f"\r  {Color.GREEN}[  OK  ]{Color.RESET} {description}                ")


# -----------------------------------------------------------------------------
# 1. BARE-METAL AUTOMATION & PROVISIONING (PXE / iPXE / Cloud-Init)
# -----------------------------------------------------------------------------
class BareMetalProvisioner:
    def __init__(self, mac_address: str = "52:54:00:fa:9b:11", hostname: str = "node01.infra.internal"):
        self.mac = mac_address
        self.hostname = hostname
        self.ip_assigned = "192.168.100.50"

    def run_provisioning_pipeline(self):
        print(f"\n{Color.BOLD}{Color.MAGENTA}=== [TAHAP 1: BARE-METAL PXE & PROVISIONING PIPELINE] ==={Color.RESET}")
        print(f"Target Server MAC : {Color.WHITE}{self.mac}{Color.RESET}")
        print(f"Target Hostname   : {Color.WHITE}{self.hostname}{Color.RESET}\n")

        progress_step("Mengirim DHCP Discover paket broadcast melalui NIC")
        progress_step(f"DHCP Offer diterima -> Next-Server: 192.168.100.1, Assigned IP: {self.ip_assigned}")
        progress_step("Mengunduh stage-1 iPXE chainloader via TFTP (undionly.kpxe)")
        progress_step("Eksekusi iPXE boot script via HTTPS dari Provisioning Server")
        progress_step("Transfer Linux Kernel (vmlinuz-6.8.0) dan initrd.img ke RAM")
        progress_step("Memuat Cloud-Init user-data & Kickstart automation config")

        cloud_init_spec = {
            "hostname": self.hostname,
            "timezone": "Asia/Jakarta",
            "users": [
                {
                    "name": "devops-admin",
                    "sudo": "ALL=(ALL) NOPASSWD:ALL",
                    "ssh_authorized_keys": ["ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI... automation-key"]
                }
            ],
            "storage": {
                "layout": "lvm",
                "vg": "vg_system",
                "partitions": [
                    {"mount": "/boot", "size": "1G", "fstype": "ext4"},
                    {"mount": "/", "size": "30G", "fstype": "ext4"},
                    {"mount": "/var", "size": "50G", "fstype": "ext4"},
                    {"mount": "/var/log", "size": "20G", "fstype": "ext4"},
                    {"mount": "/var/log/audit", "size": "10G", "fstype": "ext4"}
                ]
            }
        }

        print(f"\n{Color.CYAN}--- [Generated Cloud-Init / Storage Profile (LVM CIS Layout)] ---{Color.RESET}")
        print(json.dumps(cloud_init_spec, indent=2))
        print(f"{Color.GREEN}{Color.BOLD}✓ Bare-Metal node berhasil ter-install dan boot ke OS primer.{Color.RESET}\n")


# -----------------------------------------------------------------------------
# 2. CIS LINUX BENCHMARK AUDITOR & AUTO-REMEDIATION ENGINE
# -----------------------------------------------------------------------------
class CISBenchmarkAuditor:
    def __init__(self):
        self.rules = [
            {
                "id": "CIS-1.1.1.1",
                "title": "Ensure mounting of cramfs filesystems is disabled",
                "status": "FAIL",
                "remediation": "echo 'install cramfs /bin/true' > /etc/modprobe.d/cramfs.conf"
            },
            {
                "id": "CIS-1.1.2.1",
                "title": "Ensure /tmp is mounted with separate partition & noexec,nodev,nosuid",
                "status": "FAIL",
                "remediation": "mount -o remount,noexec,nodev,nosuid /tmp"
            },
            {
                "id": "CIS-3.2.1",
                "title": "Ensure IP forwarding is disabled (net.ipv4.ip_forward = 0)",
                "status": "FAIL",
                "remediation": "sysctl -w net.ipv4.ip_forward=0 && echo 'net.ipv4.ip_forward=0' >> /etc/sysctl.d/99-cis.conf"
            },
            {
                "id": "CIS-5.2.1",
                "title": "Ensure SSH Root Login is disabled (PermitRootLogin no)",
                "status": "FAIL",
                "remediation": "sed -i 's/^PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config"
            },
            {
                "id": "CIS-5.2.10",
                "title": "Ensure SSH PasswordAuthentication is disabled (Key-based only)",
                "status": "FAIL",
                "remediation": "sed -i 's/^PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config"
            },
            {
                "id": "CIS-6.1.2",
                "title": "Ensure permissions on /etc/shadow are 0000 or 0640 (root:shadow)",
                "status": "PASS",
                "remediation": "chmod 0640 /etc/shadow && chown root:shadow /etc/shadow"
            }
        ]

    def audit_system(self):
        print(f"\n{Color.BOLD}{Color.MAGENTA}=== [TAHAP 2: CIS LINUX BENCHMARK COMPLIANCE AUDIT] ==={Color.RESET}")
        print(f"{'ID':<12} | {'STATUS':<8} | {'BENCHMARK TITLE'}")
        print("-" * 75)
        for r in self.rules:
            status_color = Color.GREEN if r["status"] == "PASS" else Color.RED
            print(f"{r['id']:<12} | {status_color}{r['status']:<8}{Color.RESET} | {r['title']}")
            time.sleep(0.1)

        fail_count = sum(1 for r in self.rules if r["status"] == "FAIL")
        total = len(self.rules)
        score = int(((total - fail_count) / total) * 100)
        print("-" * 75)
        print(f"Compliance Score: {Color.YELLOW}{score}%{Color.RESET} ({fail_count} Pelanggaran Keamanan Kritis)\n")

    def remediate_all(self):
        print(f"{Color.BOLD}{Color.CYAN}--- [EKSEKUSI AUTO-REMEDIASI CIS HARDENING] ---{Color.RESET}")
        for r in self.rules:
            if r["status"] == "FAIL":
                progress_step(f"Menerapkan Remediasi {r['id']}")
                r["status"] = "PASS"
                print(f"    {Color.DIM}-> Exec: {r['remediation']}{Color.RESET}")
        print(f"\n{Color.GREEN}{Color.BOLD}✓ Semua CIS hardening policies sukses diterapkan. Compliance 100%.{Color.RESET}\n")


# -----------------------------------------------------------------------------
# 3. DISASTER RECOVERY (DR) & BACKUP ORCHESTRATION
# -----------------------------------------------------------------------------
class DisasterRecoveryEngine:
    def __init__(self):
        self.snapshots = []
        self.rpo_target_minutes = 15
        self.rto_target_minutes = 30

    def create_bare_metal_backup(self, label: str = "GOLD_MASTER_STATE"):
        print(f"\n{Color.BOLD}{Color.MAGENTA}=== [TAHAP 3: BARE-METAL BACKUP & DR SNAPSHOT] ==={Color.RESET}")
        progress_step("Membekukan filesystem konsisten (LVM snapshot freeze / fsfreeze)")
        progress_step("Streaming block level backup (/dev/vg_system/root) dengan Zstandard kompresi")
        
        raw_data = f"SYS_STATE_DUMP_{label}_{time.time()}".encode("utf-8")
        checksum = hashlib.sha256(raw_data).hexdigest()
        
        snapshot_meta = {
            "snapshot_id": f"snap-{int(time.time())}",
            "label": label,
            "sha256": checksum,
            "size_compressed": "4.2 GB",
            "dedup_ratio": "2.4x",
            "target": "s3://dr-vault-region-b/bare-metal/"
        }
        self.snapshots.append(snapshot_meta)
        progress_step("Mengunggah metadata dan payload snapshot ke Secondary Offsite DR Vault")
        
        print(f"\n{Color.CYAN}--- Snapshot Ledger Berhasil Dibuat ---{Color.RESET}")
        print(json.dumps(snapshot_meta, indent=2))
        print(f"{Color.GREEN}RPO Status: Compliant (Interval saat ini: 0 menit <= Target: {self.rpo_target_minutes} menit){Color.RESET}\n")

    def simulate_catastrophic_failure_and_dr(self):
        print(f"\n{Color.RED}{Color.BOLD}!!! [SIMULASI BENCANA: CATASTROPHIC DISK & SYSTEM FAILURE] !!!{Color.RESET}")
        print(f"{Color.RED}Node utama mengalami hardware kernel panic & filesystem corruption.{Color.RESET}")
        time.sleep(0.5)

        print(f"\n{Color.YELLOW}Memulai Prosedur Bare-Metal Disaster Recovery (Bare-Metal Restore)...{Color.RESET}")
        start_time = time.time()
        
        progress_step("PXE booting Rescue OS (Live Memory RAM Environment) pada spare node")
        progress_step("Mengunduh snapshot master terbaru dari remote vault")
        if self.snapshots:
            target_snap = self.snapshots[-1]
            print(f"  {Color.DIM}Verifikasi integritas SHA256: {target_snap['sha256'][:16]}... OK{Color.RESET}")
        progress_step("Partisi ulang NVMe drive dengan skema LVM & restore block stream")
        progress_step("Re-install GRUB bootloader & regenerate initramfs")
        progress_step("Sinkronisasi IP Failover / Virtual IP (Keepalived / BGP Anycast)")

        elapsed_sim_minutes = 12.4
        print(f"\n{Color.GREEN}{Color.BOLD}=== HASIL RECOVERY DRILL ==={Color.RESET}")
        print(f"RTO Aktual  : {Color.BOLD}{elapsed_sim_minutes} Menit{Color.RESET} (Batas Target: {self.rto_target_minutes} Menit) -> {Color.GREEN}MEETS SLA{Color.RESET}")
        print(f"Data Loss   : {Color.BOLD}0 blocks{Color.RESET} (Integritas Bit-Level 100% Cocok)")
        print(f"{Color.GREEN}✓ Node pengganti sukses pulih dan berstatus Healthy di Cluster.{Color.RESET}\n")


# -----------------------------------------------------------------------------
# MAIN INTERACTIVE WORKFLOW LOOP
# -----------------------------------------------------------------------------
def run_interactive_lab():
    print_banner()
    provisioner = BareMetalProvisioner()
    auditor = CISBenchmarkAuditor()
    dr = DisasterRecoveryEngine()

    menu = f"""{Color.BOLD}{Color.WHITE}PILIH MODUL PRAKTIKUM LINUX CORE ENGINEERING:{Color.RESET}
  {Color.CYAN}1.{Color.RESET} Jalankan Otomasi Bare-Metal Provisioning (PXE, DHCP, Cloud-Init)
  {Color.CYAN}2.{Color.RESET} Jalankan Audit Keamanan CIS Benchmark Level 1 & 2
  {Color.CYAN}3.{Color.RESET} Terapkan Auto-Remediasi CIS Hardening Policy
  {Color.CYAN}4.{Color.RESET} Buat Snapshot Backup Bare-Metal ke Disaster Recovery Vault
  {Color.CYAN}5.{Color.RESET} Jalankan Uji Simulasi Bencana & Failover Recovery Drill (RPO/RTO)
  {Color.CYAN}6.{Color.RESET} Eksekusi Seluruh Pipeline Secara Sekuensial (Full Automated Run)
  {Color.RED}0.{Color.RESET} Keluar dari Lab

"""

    # If executed with non-interactive flag (e.g. CI/grading)
    if "--non-interactive" in sys.argv or "--auto" in sys.argv:
        print(f"{Color.YELLOW}[Mode Non-Interaktif Aktif: Menjalankan Full Pipeline Sekuensial]{Color.RESET}")
        provisioner.run_provisioning_pipeline()
        auditor.audit_system()
        auditor.remediate_all()
        dr.create_bare_metal_backup()
        dr.simulate_catastrophic_failure_and_dr()
        print(f"{Color.GREEN}{Color.BOLD}Semua tes lab berhasil diselesaikan dengan sempurna!{Color.RESET}")
        return

    while True:
        try:
            choice = input(menu + f"{Color.BOLD}Pilihan Anda [0-6]: {Color.RESET}").strip()
            if choice == "1":
                provisioner.run_provisioning_pipeline()
            elif choice == "2":
                auditor.audit_system()
            elif choice == "3":
                auditor.remediate_all()
            elif choice == "4":
                dr.create_bare_metal_backup()
            elif choice == "5":
                dr.simulate_catastrophic_failure_and_dr()
            elif choice == "6":
                print(f"\n{Color.YELLOW}Memulai eksekusi end-to-end simulasi BAB 10...{Color.RESET}")
                provisioner.run_provisioning_pipeline()
                auditor.audit_system()
                auditor.remediate_all()
                dr.create_bare_metal_backup()
                dr.simulate_catastrophic_failure_and_dr()
            elif choice in ("0", "exit", "quit"):
                print(f"\n{Color.CYAN}Selesai. Keluar dari laboratorium.{Color.RESET}")
                break
            else:
                print(f"{Color.RED}Pilihan tidak valid. Silakan pilih 0 hingga 6.{Color.RESET}\n")
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Color.YELLOW}Lab dihentikan oleh pengguna.{Color.RESET}")
            break


if __name__ == "__main__":
    run_interactive_lab()
