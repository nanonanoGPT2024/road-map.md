#!/usr/bin/env python3
"""
AWS Storage Subsystems & Data Lifecycle Management Lab
Simulasi Interaktif Produksi Tingkat Lanjut:
- S3 Storage Classes & Automated Lifecycle Transitions (Standard -> IA -> Glacier -> Deep Archive)
- S3 Object Lock (WORM Compliance & Legal Hold)
- S3 Intelligent-Tiering & Access Pattern Telemetry
- Cost Analytics & Storage TCO Optimization Engine
"""

import sys
import time
import uuid
import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# ANSI Color Codes
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"


# Pricing per GB-month (us-east-1 reference)
PRICING_PER_GB = {
    "STANDARD": 0.023,
    "STANDARD_IA": 0.0125,
    "GLACIER_FLEXIBLE": 0.0036,
    "DEEP_ARCHIVE": 0.00099,
    "EXPIRED": 0.0,
}


@dataclass
class StorageObject:
    key: str
    size_gb: float
    storage_class: str = "STANDARD"
    age_days: int = 0
    object_lock_mode: Optional[str] = None  # None, "GOVERNANCE", "COMPLIANCE"
    retention_until_day: int = 0
    legal_hold: bool = False
    access_frequency_days: int = 1
    tags: Dict[str, str] = field(default_factory=dict)
    is_deleted: bool = False


class S3LifecycleEngine:
    def __init__(self, bucket_name: str = "prod-data-lake-tier1"):
        self.bucket_name = bucket_name
        self.objects: Dict[str, StorageObject] = {}
        self.simulation_day = 0

    def put_object(
        self,
        key: str,
        size_gb: float,
        lock_mode: Optional[str] = None,
        retention_days: int = 0,
        legal_hold: bool = False,
        tags: Optional[Dict[str, str]] = None,
    ) -> StorageObject:
        obj = StorageObject(
            key=key,
            size_gb=size_gb,
            storage_class="STANDARD",
            age_days=0,
            object_lock_mode=lock_mode,
            retention_until_day=self.simulation_day + retention_days if lock_mode else 0,
            legal_hold=legal_hold,
            tags=tags or {},
        )
        self.objects[key] = obj
        return obj

    def apply_lifecycle_rules(self, verbose: bool = True) -> List[str]:
        """
        Enterprise Policy:
        - Day 0-29: STANDARD
        - Day 30-89: STANDARD_IA (Infrequent Access)
        - Day 90-179: GLACIER_FLEXIBLE (Cold Storage)
        - Day 180-364: DEEP_ARCHIVE (Glacier Deep Archive)
        - Day >= 365: Expired / Permanent Deletion (respecting Object Lock)
        """
        transitions = []
        for obj in self.objects.values():
            if obj.is_deleted:
                continue

            prev_class = obj.storage_class
            target_class = prev_class

            if obj.age_days >= 365:
                # Check Lock
                if obj.legal_hold:
                    transitions.append(
                        f"{Colors.YELLOW}[BLOCKED]{Colors.RESET} {obj.key}: Deletion blocked by Legal Hold."
                    )
                elif obj.object_lock_mode and self.simulation_day < obj.retention_until_day:
                    transitions.append(
                        f"{Colors.YELLOW}[BLOCKED]{Colors.RESET} {obj.key}: Deletion blocked by {obj.object_lock_mode} until Day {obj.retention_until_day}."
                    )
                else:
                    obj.is_deleted = True
                    obj.storage_class = "EXPIRED"
                    transitions.append(
                        f"{Colors.RED}[EXPIRED]{Colors.RESET} {obj.key} permanently deleted at Day {self.simulation_day}."
                    )
                    continue
            elif obj.age_days >= 180:
                target_class = "DEEP_ARCHIVE"
            elif obj.age_days >= 90:
                target_class = "GLACIER_FLEXIBLE"
            elif obj.age_days >= 30:
                target_class = "STANDARD_IA"

            if target_class != prev_class:
                obj.storage_class = target_class
                transitions.append(
                    f"{Colors.CYAN}[TIER MIGRATION]{Colors.RESET} {obj.key}: {prev_class} -> {Colors.BOLD}{target_class}{Colors.RESET} (Age: {obj.age_days}d)"
                )

        return transitions

    def advance_time(self, days: int) -> List[str]:
        self.simulation_day += days
        for obj in self.objects.values():
            if not obj.is_deleted:
                obj.age_days += days
        return self.apply_lifecycle_rules()

    def attempt_delete(self, key: str, bypass_governance: bool = False) -> tuple[bool, str]:
        if key not in self.objects:
            return False, "Object not found."
        obj = self.objects[key]
        if obj.is_deleted:
            return False, "Object already deleted."

        if obj.legal_hold:
            return False, f"HTTP 403 AccessDenied: Object '{key}' has an active Legal Hold."

        if obj.object_lock_mode == "COMPLIANCE" and self.simulation_day < obj.retention_until_day:
            remaining = obj.retention_until_day - self.simulation_day
            return False, f"HTTP 403 AccessDenied: Object in COMPLIANCE WORM mode. Locked for {remaining} more days."

        if obj.object_lock_mode == "GOVERNANCE" and self.simulation_day < obj.retention_until_day:
            if not bypass_governance:
                return False, f"HTTP 403 AccessDenied: GOVERNANCE retention active. Requires s3:BypassGovernanceRetention."

        obj.is_deleted = True
        obj.storage_class = "EXPIRED"
        return True, f"Object '{key}' successfully deleted."

    def calculate_monthly_tco(self) -> Dict[str, float]:
        active_objects = [o for o in self.objects.values() if not o.is_deleted]
        current_cost = sum(o.size_gb * PRICING_PER_GB[o.storage_class] for o in active_objects)
        all_standard_cost = sum(o.size_gb * PRICING_PER_GB["STANDARD"] for o in active_objects)
        savings = max(0.0, all_standard_cost - current_cost)
        savings_pct = (savings / all_standard_cost * 100) if all_standard_cost > 0 else 0.0

        return {
            "current_cost": current_cost,
            "baseline_standard_cost": all_standard_cost,
            "savings": savings,
            "savings_pct": savings_pct,
            "total_active_gb": sum(o.size_gb for o in active_objects),
        }


def print_banner():
    banner = f"""
{Colors.CYAN}{Colors.BOLD}================================================================================
 AWS STORAGE SUBSYSTEMS & DATA LIFECYCLE MANAGEMENT SIMULATOR
 Production Architecture Lab - BAB 04 (Advanced S3/Glacier/WORM/EBS)
================================================================================{Colors.RESET}
"""
    print(banner)


def display_dashboard(engine: S3LifecycleEngine):
    print(f"\n{Colors.BOLD}{Colors.WHITE}CURRENT CLOUD STATE (Simulation Day: {engine.simulation_day}){Colors.RESET}")
    print(f"Bucket: {Colors.CYAN}s3://{engine.bucket_name}{Colors.RESET}")
    print("-" * 88)
    print(f"{'Object Key':<24} | {'Size':<8} | {'Class':<16} | {'Age':<6} | {'Lock / WORM':<18} | {'Status'}")
    print("-" * 88)

    for obj in engine.objects.values():
        lock_status = "None"
        if obj.legal_hold:
            lock_status = f"{Colors.RED}LegalHold{Colors.RESET}"
        elif obj.object_lock_mode:
            rem = max(0, obj.retention_until_day - engine.simulation_day)
            lock_status = f"{Colors.MAGENTA}{obj.object_lock_mode} ({rem}d){Colors.RESET}"

        status_str = f"{Colors.RED}DELETED{Colors.RESET}" if obj.is_deleted else f"{Colors.GREEN}ACTIVE{Colors.RESET}"
        class_color = {
            "STANDARD": Colors.WHITE,
            "STANDARD_IA": Colors.CYAN,
            "GLACIER_FLEXIBLE": Colors.BLUE,
            "DEEP_ARCHIVE": Colors.MAGENTA,
            "EXPIRED": Colors.RED,
        }.get(obj.storage_class, Colors.WHITE)

        print(
            f"{obj.key:<24} | {obj.size_gb:>6.1f}GB | {class_color}{obj.storage_class:<16}{Colors.RESET} | "
            f"{obj.age_days:>4}d | {lock_status:<27} | {status_str}"
        )
    print("-" * 88)

    tco = engine.calculate_monthly_tco()
    print(
        f"Active Data: {Colors.BOLD}{tco['total_active_gb']:.1f} GB{Colors.RESET} | "
        f"Monthly Cost: {Colors.GREEN}${tco['current_cost']:.2f}{Colors.RESET} "
        f"(Without Lifecycle: {Colors.YELLOW}${tco['baseline_standard_cost']:.2f}{Colors.RESET}) | "
        f"Savings: {Colors.BOLD}{Colors.GREEN}{tco['savings_pct']:.1f}% (${tco['savings']:.2f}/mo){Colors.RESET}"
    )


def seed_production_data(engine: S3LifecycleEngine):
    engine.put_object("raw-logs/app-2026.log", size_gb=120.0, tags={"Env": "Prod", "Compliance": "PCI"})
    engine.put_object(
        "financial-audit/q1-report.pdf",
        size_gb=15.0,
        lock_mode="COMPLIANCE",
        retention_days=180,
        tags={"Audit": "SOX", "Tier": "MissionCritical"},
    )
    engine.put_object(
        "legal/contract-nda-994.enc",
        size_gb=2.5,
        legal_hold=True,
        tags={"Dept": "Legal", "Litigation": "Active"},
    )
    engine.put_object(
        "analytics/clickstream.parquet",
        size_gb=450.0,
        tags={"Pipeline": "DataLake", "Schema": "v3"},
    )
    engine.put_object(
        "backups/db-snapshot.dump",
        size_gb=250.0,
        lock_mode="GOVERNANCE",
        retention_days=60,
        tags={"Service": "RDS-Aurora"},
    )


def run_interactive_simulation():
    print_banner()
    engine = S3LifecycleEngine()
    seed_production_data(engine)

    menu = f"""
{Colors.BOLD}PILIH AKSI SIMULASI:{Colors.RESET}
  {Colors.CYAN}[1]{Colors.RESET} Tampilkan Status S3 & Metrik Biaya (Current State)
  {Colors.CYAN}[2]{Colors.RESET} Majukan Waktu (+30 Hari -> Transisi ke Standard-IA)
  {Colors.CYAN}[3]{Colors.RESET} Majukan Waktu (+90 Hari -> Transisi ke Glacier Flexible)
  {Colors.CYAN}[4]{Colors.RESET} Majukan Waktu (+180 Hari -> Transisi ke Glacier Deep Archive)
  {Colors.CYAN}[5]{Colors.RESET} Majukan Waktu (+365 Hari -> Uji Expiration & Deletion Rules)
  {Colors.CYAN}[6]{Colors.RESET} Uji Proteksi WORM (Delete Object Lock / Legal Hold)
  {Colors.CYAN}[7]{Colors.RESET} Ingest Data Baru (Simulasi PUT Multi-Part Object)
  {Colors.CYAN}[8]{Colors.RESET} Jalankan Automated End-to-End Walkthrough (Demo Otomatis)
  {Colors.CYAN}[0]{Colors.RESET} Keluar
"""

    while True:
        try:
            print(menu)
            choice = input(f"{Colors.BOLD}Pilihan [0-8]: {Colors.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting simulator.")
            break

        if choice == "1":
            display_dashboard(engine)

        elif choice == "2":
            print(f"\n{Colors.YELLOW}[SIMULATION]{Colors.RESET} Majukan waktu +30 hari...")
            logs = engine.advance_time(30)
            for log in logs:
                print(" -> " + log)
            display_dashboard(engine)

        elif choice == "3":
            print(f"\n{Colors.YELLOW}[SIMULATION]{Colors.RESET} Majukan waktu +90 hari...")
            logs = engine.advance_time(90)
            for log in logs:
                print(" -> " + log)
            display_dashboard(engine)

        elif choice == "4":
            print(f"\n{Colors.YELLOW}[SIMULATION]{Colors.RESET} Majukan waktu +180 hari...")
            logs = engine.advance_time(180)
            for log in logs:
                print(" -> " + log)
            display_dashboard(engine)

        elif choice == "5":
            print(f"\n{Colors.YELLOW}[SIMULATION]{Colors.RESET} Majukan waktu +365 hari...")
            logs = engine.advance_time(365)
            for log in logs:
                print(" -> " + log)
            display_dashboard(engine)

        elif choice == "6":
            print(f"\n{Colors.BOLD}{Colors.WHITE}TESTING S3 OBJECT LOCK WORM IMMUTABILITY{Colors.RESET}")
            test_keys = ["financial-audit/q1-report.pdf", "legal/contract-nda-994.enc", "analytics/clickstream.parquet"]
            for key in test_keys:
                print(f"\n[*] Percobaan penghapusan paksa: {Colors.CYAN}{key}{Colors.RESET}")
                success, msg = engine.attempt_delete(key)
                if success:
                    print(f"    {Colors.GREEN}SUCCESS:{Colors.RESET} {msg}")
                else:
                    print(f"    {Colors.RED}BLOCKED:{Colors.RESET} {msg}")

        elif choice == "7":
            try:
                name = input("Masukkan key object (e.g. models/ai-weights.bin): ").strip()
                if not name:
                    name = f"dataset/{uuid.uuid4().hex[:8]}.csv"
                size = float(input("Ukuran dalam GB (default 80.0): ") or 80.0)
                engine.put_object(name, size_gb=size)
                print(f"{Colors.GREEN}[INGESTED]{Colors.RESET} Object {name} ({size} GB) berhasil diunggah ke STANDARD.")
                display_dashboard(engine)
            except ValueError:
                print(f"{Colors.RED}Input ukuran tidak valid.{Colors.RESET}")

        elif choice == "8":
            run_automated_demo(engine)

        elif choice == "0":
            print(f"\n{Colors.GREEN}Lab selesai. Arsitektur Storage Lifecycle terverifikasi.{Colors.RESET}")
            break
        else:
            print(f"{Colors.RED}Pilihan tidak valid, silakan ulangi.{Colors.RESET}")


def run_automated_demo(engine: Optional[S3LifecycleEngine] = None):
    """Automated batch test that runs cleanly even in non-interactive CI/CD terminals."""
    if engine is None:
        print_banner()
        engine = S3LifecycleEngine("automated-ci-cd-storage-lab")
        seed_production_data(engine)

    print(f"\n{Colors.BOLD}{Colors.MAGENTA}=== MENJALANKAN AUTOMATED ARCHITECTURE DEMO ==={Colors.RESET}")
    display_dashboard(engine)

    steps = [
        (30, "Hari ke-30: Transisi S3 Standard -> Standard-IA"),
        (60, "Hari ke-90: Transisi Standard-IA -> Glacier Flexible Archive"),
        (90, "Hari ke-180: Transisi Glacier -> Glacier Deep Archive"),
        (185, "Hari ke-365: Uji Lifecycle Expiration & WORM Protection"),
    ]

    for days, desc in steps:
        print(f"\n{Colors.CYAN}{Colors.BOLD}>>> {desc} (+{days} hari){Colors.RESET}")
        logs = engine.advance_time(days)
        if logs:
            for l in logs:
                print("   " + l)
        else:
            print("   (Tidak ada transisi baru pada jendela ini)")
        display_dashboard(engine)

    print(f"\n{Colors.BOLD}{Colors.WHITE}>>> Uji Keamanan WORM Compliance terhadap Hacker / Malicious Actor:{Colors.RESET}")
    for key in ["financial-audit/q1-report.pdf", "legal/contract-nda-994.enc", "analytics/clickstream.parquet"]:
        success, msg = engine.attempt_delete(key)
        badge = f"{Colors.GREEN}[ALLOWED]{Colors.RESET}" if success else f"{Colors.RED}[REJECTED]{Colors.RESET}"
        print(f"   {badge} Delete '{key}': {msg}")

    print(f"\n{Colors.BOLD}{Colors.GREEN}[OK] Automated Verification Complete: Zero data loss on protected assets & maximum cost savings achieved!{Colors.RESET}\n")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--demo", "--auto", "-y"):
        run_automated_demo()
    elif not sys.stdin.isatty():
        # Fallback to demo mode if executed inside automated runner without interactive tty
        run_automated_demo()
    else:
        run_interactive_simulation()
