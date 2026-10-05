#!/usr/bin/env python3
"""
AWS Storage Subsystems & Data Lifecycle Management Lab
BAB-04: S3, EBS, and EFS Storage Tiering and Lifecycle Policy Simulator.
Standard library only, interactive CLI with ANSI color formatting.
"""

import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional

# ANSI Color Codes
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    GRAY = "\033[90m"


class S3StorageClass(Enum):
    STANDARD = ("S3 Standard", 0.023, 0, "Millisecond")
    INTELLIGENT = ("S3 Intelligent-Tiering", 0.023, 0, "Millisecond")
    STANDARD_IA = ("S3 Standard-IA", 0.0125, 30, "Millisecond")
    ONEZONE_IA = ("S3 One Zone-IA", 0.010, 30, "Millisecond")
    GLACIER_IR = ("S3 Glacier Instant Retrieval", 0.004, 90, "Millisecond")
    GLACIER_FLEX = ("S3 Glacier Flexible Retrieval", 0.0036, 90, "Minutes to Hours")
    GLACIER_DEEP = ("S3 Glacier Deep Archive", 0.00099, 180, "12 to 48 Hours")

    def __init__(self, display_name: str, cost_per_gb: float, min_days: int, retrieval_latency: str):
        self.display_name = display_name
        self.cost_per_gb = cost_per_gb
        self.min_days = min_days
        self.retrieval_latency = retrieval_latency


@dataclass
class S3ObjectMetadata:
    key: str
    size_gb: float
    age_days: int
    current_tier: S3StorageClass
    history: List[str] = field(default_factory=list)


@dataclass
class LifecycleRule:
    prefix: str
    transition_ia_days: int = 30
    transition_glacier_days: int = 90
    transition_deep_archive_days: int = 180
    expiration_days: int = 365


class S3LifecycleEngine:
    def __init__(self, rule: LifecycleRule):
        self.rule = rule

    def evaluate_transition(self, obj: S3ObjectMetadata) -> Optional[S3StorageClass]:
        if not obj.key.startswith(self.rule.prefix):
            return None

        if obj.age_days >= self.rule.expiration_days:
            return None  # Marked for deletion

        if obj.age_days >= self.rule.transition_deep_archive_days:
            return S3StorageClass.GLACIER_DEEP
        elif obj.age_days >= self.rule.transition_glacier_days:
            return S3StorageClass.GLACIER_FLEX
        elif obj.age_days >= self.rule.transition_ia_days:
            return S3StorageClass.STANDARD_IA
        return S3StorageClass.STANDARD


def print_banner():
    banner = f"""
{Color.CYAN}{Color.BOLD}========================================================================
   AWS STORAGE SUBSYSTEMS & DATA LIFECYCLE MANAGEMENT SIMULATOR
   BAB-04: S3 Tiering, EBS IOPS, and EFS Cost Optimization
========================================================================{Color.RESET}
"""
    print(banner)


def display_tier_matrix():
    print(f"\n{Color.BOLD}{Color.YELLOW}[*] AWS S3 Storage Tier Specification Matrix:{Color.RESET}\n")
    header = f"{'Storage Class':<30} | {'Cost/GB/Mo':<12} | {'Min Retention':<14} | {'Retrieval Latency'}"
    print(f"{Color.BOLD}{header}{Color.RESET}")
    print("-" * 75)
    for tier in S3StorageClass:
        line = f"{tier.display_name:<30} | ${tier.cost_per_gb:<11.5f} | {tier.min_days:>3} days       | {tier.retrieval_latency}"
        print(f"{Color.GREEN if 'Standard' in tier.name else Color.CYAN}{line}{Color.RESET}")
    print("-" * 75)


def run_lifecycle_simulation(dataset_size_gb: float = 5000.0):
    print(f"\n{Color.BOLD}{Color.MAGENTA}[*] Running 365-Day Lifecycle Policy Simulation for {dataset_size_gb:,.0f} GB Dataset...{Color.RESET}\n")
    rule = LifecycleRule(
        prefix="logs/",
        transition_ia_days=30,
        transition_glacier_days=90,
        transition_deep_archive_days=180,
        expiration_days=365
    )
    engine = S3LifecycleEngine(rule)

    obj = S3ObjectMetadata(
        key="logs/app-access-2026.parquet",
        size_gb=dataset_size_gb,
        age_days=0,
        current_tier=S3StorageClass.STANDARD
    )

    milestones = [0, 30, 60, 90, 180, 270, 365]
    total_cost_standard_only = 0.0
    total_cost_with_lifecycle = 0.0

    print(f"{'Day':<6} | {'Simulated Event':<35} | {'Active Tier':<28} | {'Monthly Cost':<12}")
    print("-" * 90)

    for day in range(366):
        obj.age_days = day
        # Calculate daily fraction cost
        daily_rate_standard = (obj.size_gb * S3StorageClass.STANDARD.cost_per_gb) / 30.0
        total_cost_standard_only += daily_rate_standard

        target_tier = engine.evaluate_transition(obj)
        if target_tier and target_tier != obj.current_tier:
            event_desc = f"TRANSITION -> {target_tier.display_name}"
            obj.current_tier = target_tier
            obj.history.append(f"Day {day}: Moved to {target_tier.name}")
            monthly_equiv = obj.size_gb * obj.current_tier.cost_per_gb
            print(f"{Color.YELLOW}{day:<6} | {event_desc:<35} | {obj.current_tier.display_name:<28} | ${monthly_equiv:<11.2f}{Color.RESET}")
        elif day == 365:
            print(f"{Color.RED}{day:<6} | {'EXPIRED & PURGED (Deleted)':<35} | {'None (Deleted)':<28} | $0.00       {Color.RESET}")

        if day < 365:
            daily_rate_lifecycle = (obj.size_gb * obj.current_tier.cost_per_gb) / 30.0
            total_cost_with_lifecycle += daily_rate_lifecycle

    savings = total_cost_standard_only - total_cost_with_lifecycle
    savings_pct = (savings / total_cost_standard_only) * 100 if total_cost_standard_only > 0 else 0

    print("-" * 90)
    print(f"\n{Color.BOLD}{Color.CYAN}[*] 1-Year Financial Impact Analysis:{Color.RESET}")
    print(f"  - Total Cost (S3 Standard Unmanaged) : {Color.RED}${total_cost_standard_only:,.2f}{Color.RESET}")
    print(f"  - Total Cost (With Lifecycle Policy) : {Color.GREEN}${total_cost_with_lifecycle:,.2f}{Color.RESET}")
    print(f"  - Net Operational Savings           : {Color.BOLD}{Color.GREEN}${savings:,.2f} ({savings_pct:.1f}%){Color.RESET}\n")


def simulate_ebs_workload():
    print(f"\n{Color.BOLD}{Color.YELLOW}[*] Simulating EBS Volume Subsystems (Throughput & IOPS):{Color.RESET}\n")
    ebs_types = {
        "gp3 (General Purpose)": {"base_iops": 3000, "burst_iops": 16000, "base_mb_s": 125, "cost_gb": 0.08},
        "io2 Block Express": {"base_iops": 64000, "burst_iops": 256000, "base_mb_s": 4000, "cost_gb": 0.125},
        "st1 (Throughput Optimized)": {"base_iops": 500, "burst_iops": 500, "base_mb_s": 500, "cost_gb": 0.045}
    }

    for name, specs in ebs_types.items():
        print(f"  {Color.BOLD}{name}{Color.RESET}:")
        print(f"    IOPS: {specs['base_iops']:,} - {specs['burst_iops']:,} IOPS | Max Bandwidth: {specs['base_mb_s']} MB/s | Storage: ${specs['cost_gb']}/GB-Mo")
    print()


def interactive_menu():
    print_banner()
    while True:
        print(f"{Color.BOLD}Select an AWS Storage Lab Demonstration:{Color.RESET}")
        print("  1. View S3 Storage Class & Retrieval Characteristics Matrix")
        print("  2. Run 365-Day S3 Lifecycle Tiering & Financial Simulator")
        print("  3. Benchmark EBS Volume Subsystems (gp3 vs io2 vs st1)")
        print("  4. Execute Full Automated Laboratory Suite")
        print("  5. Exit")
        
        try:
            choice = input(f"\n{Color.BOLD}{Color.CYAN}Enter choice [1-5]: {Color.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting lab...")
            break

        if choice == "1":
            display_tier_matrix()
        elif choice == "2":
            run_lifecycle_simulation(dataset_size_gb=10000.0)
        elif choice == "3":
            simulate_ebs_workload()
        elif choice == "4":
            display_tier_matrix()
            run_lifecycle_simulation(dataset_size_gb=10000.0)
            simulate_ebs_workload()
            print(f"{Color.GREEN}{Color.BOLD}[+] All simulations executed successfully.{Color.RESET}\n")
            break
        elif choice == "5":
            print(f"{Color.GREEN}Lab completed successfully.{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Invalid selection. Please choose 1-5.{Color.RESET}\n")


def main():
    # If stdin is not a TTY or running in non-interactive batch mode
    if not sys.stdin.isatty() or "--non-interactive" in sys.argv:
        print_banner()
        display_tier_matrix()
        run_lifecycle_simulation(dataset_size_gb=10000.0)
        simulate_ebs_workload()
        print(f"{Color.GREEN}{Color.BOLD}[+] Non-interactive batch execution finished.{Color.RESET}")
    else:
        interactive_menu()


if __name__ == "__main__":
    main()
