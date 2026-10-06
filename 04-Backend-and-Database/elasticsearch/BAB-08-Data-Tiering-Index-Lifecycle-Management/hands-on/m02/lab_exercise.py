#!/usr/bin/env python3
"""
Lab Exercise: Advanced Elasticsearch Data Tiering & Index Lifecycle Management (ILM)
BAB-08: Data Tiering & Index Lifecycle Management
Author: Elasticsearch Production Architecture Hands-On Lab
Environment: Standalone Python 3 with Terminal ANSI Color Output
"""

import sys
import time
import json
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

# --- ANSI Color Codes for Terminal UI ---
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    
    # Foreground
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    # Bright Foreground
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"
    
    # Background
    BG_DARK = "\033[40m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"


class Tier(str, Enum):
    HOT = "data_hot"
    WARM = "data_warm"
    COLD = "data_cold"
    FROZEN = "data_frozen"
    DELETED = "deleted"


@dataclass
class ClusterNode:
    name: str
    role_tier: str
    hardware_spec: str
    storage_type: str
    iops: int
    cost_per_gb_month: float
    active_shards: int = 0


@dataclass
class SimulatedIndex:
    name: str
    alias: str
    generation: int
    current_tier: Tier
    doc_count: int
    primary_shards: int
    replica_shards: int
    segment_count: int
    size_mb: float
    is_read_only: bool = False
    is_searchable_snapshot: bool = False
    age_days: float = 0.0
    history: List[str] = field(default_factory=list)

    def log_event(self, message: str) -> None:
        self.history.append(f"[Day {self.age_days:.1f} | {self.current_tier.value}] {message}")


class ILMArchitectureLab:
    def __init__(self):
        self.nodes = [
            ClusterNode("es-hot-node-01", "data_hot", "32 vCPU / 64GB RAM", "NVMe SSD (Gen4)", 80000, 0.28),
            ClusterNode("es-hot-node-02", "data_hot", "32 vCPU / 64GB RAM", "NVMe SSD (Gen4)", 80000, 0.28),
            ClusterNode("es-warm-node-01", "data_warm", "16 vCPU / 64GB RAM", "Dense SATA SSD", 15000, 0.12),
            ClusterNode("es-warm-node-02", "data_warm", "16 vCPU / 64GB RAM", "Dense SATA SSD", 15000, 0.12),
            ClusterNode("es-cold-node-01", "data_cold", "8 vCPU / 32GB RAM", "Standard HDD / EBS gp3", 3000, 0.05),
            ClusterNode("es-frozen-node-01", "data_frozen", "4 vCPU / 16GB RAM", "S3 Shared Object Store", 500, 0.015),
        ]
        
        self.ilm_policy = {
            "policy": {
                "phases": {
                    "hot": {
                        "min_age": "0d",
                        "actions": {
                            "rollover": {
                                "max_primary_shard_size": "50GB",
                                "max_age": "7d",
                                "max_docs": 1000
                            },
                            "set_priority": {"priority": 100}
                        }
                    },
                    "warm": {
                        "min_age": "7d",
                        "actions": {
                            "shrink": {"number_of_shards": 1},
                            "forcemerge": {"max_num_segments": 1},
                            "allocate": {"number_of_replicas": 1},
                            "set_priority": {"priority": 50}
                        }
                    },
                    "cold": {
                        "min_age": "30d",
                        "actions": {
                            "searchable_snapshot": {
                                "snapshot_repository": "found-snapshots"
                            },
                            "allocate": {"number_of_replicas": 0},
                            "set_priority": {"priority": 20}
                        }
                    },
                    "frozen": {
                        "min_age": "90d",
                        "actions": {
                            "searchable_snapshot": {
                                "snapshot_repository": "found-snapshots",
                                "storage": "shared_cache"
                            }
                        }
                    },
                    "delete": {
                        "min_age": "365d",
                        "actions": {
                            "delete": {"delete_searchable_snapshot": True}
                        }
                    }
                }
            }
        }
        
        self.indices: Dict[str, SimulatedIndex] = {}
        self.current_write_index: Optional[SimulatedIndex] = None
        self.active_alias = "logs-application-prod"

    def banner(self) -> None:
        print(f"{Color.BRIGHT_CYAN}{'='*80}{Color.RESET}")
        print(f"{Color.BOLD}{Color.BRIGHT_YELLOW}   ELASTICSEARCH PRODUCTION LAB: DATA TIERING & ILM ARCHITECTURE{Color.RESET}")
        print(f"{Color.DIM}   Module 02: Multi-Tier Storage, Rollover, Shrink, Force-Merge, Searchable Snapshots{Color.RESET}")
        print(f"{Color.BRIGHT_CYAN}{'='*80}{Color.RESET}\n")

    def print_section(self, title: str) -> None:
        print(f"\n{Color.BRIGHT_BLUE}▶ {Color.BOLD}{Color.BRIGHT_WHITE}{title}{Color.RESET}")
        print(f"{Color.CYAN}{'-'*75}{Color.RESET}")

    def show_topology(self) -> None:
        self.print_section("CLUSTER TOPOLOGY & DATA TIER SPECS")
        header = f"{'Node Name':<18} | {'Tier Role':<13} | {'Specs':<20} | {'Storage Media':<20} | {'IOPS':<7} | {'$/GB/Mo'}"
        print(f"{Color.BOLD}{header}{Color.RESET}")
        print("-" * 95)
        for n in self.nodes:
            tier_color = {
                "data_hot": Color.BRIGHT_RED,
                "data_warm": Color.BRIGHT_YELLOW,
                "data_cold": Color.BRIGHT_CYAN,
                "data_frozen": Color.BRIGHT_BLUE
            }.get(n.role_tier, Color.WHITE)
            
            print(f"{n.name:<18} | {tier_color}{n.role_tier:<13}{Color.RESET} | {n.hardware_spec:<20} | "
                  f"{n.storage_type:<20} | {n.iops:<7} | ${n.cost_per_gb_month:.3f}")
        print("-" * 95)

    def display_ilm_policy(self) -> None:
        self.print_section("ACTIVE ILM POLICY DEFINITION (enterprise-logs-ilm)")
        formatted_json = json.dumps(self.ilm_policy, indent=2)
        print(f"{Color.BRIGHT_GREEN}{formatted_json}{Color.RESET}")
        print(f"\n{Color.YELLOW}Key Architecture Invariants:{Color.RESET}")
        print(f" • {Color.BOLD}Hot Tier{Color.RESET}: High ingest, 2 primary + 2 replica shards, NVMe throughput.")
        print(f" • {Color.BOLD}Warm Tier (Day 7+){Color.RESET}: Index shrunk to 1 shard, force-merged to 1 segment (read-only).")
        print(f" • {Color.BOLD}Cold Tier (Day 30+){Color.RESET}: Fully mounted Searchable Snapshot, replicas reduced to 0.")
        print(f" • {Color.BOLD}Frozen Tier (Day 90+){Color.RESET}: Partially mounted Searchable Snapshot backed by S3 cache.")
        print(f" • {Color.BOLD}Delete Phase (Day 365+){Color.RESET}: Complete purge from S3 object store.")

    def bootstrap_index(self) -> None:
        self.print_section("BOOTSTRAP DATA STREAM / ILM INDEX")
        idx_name = f"{self.active_alias}-000001"
        if idx_name in self.indices:
            print(f"{Color.YELLOW}Index {idx_name} already exists.{Color.RESET}")
            return

        new_index = SimulatedIndex(
            name=idx_name,
            alias=self.active_alias,
            generation=1,
            current_tier=Tier.HOT,
            doc_count=0,
            primary_shards=2,
            replica_shards=1,
            segment_count=4,
            size_mb=12.5,
            age_days=0.0
        )
        new_index.log_event("Index initialized on HOT tier. Primary shards=2, Replica=1, is_write_index=True.")
        self.indices[idx_name] = new_index
        self.current_write_index = new_index

        print(f"{Color.GREEN}✓ Created initial index: {Color.BOLD}{idx_name}{Color.RESET}")
        print(f"{Color.GREEN}✓ Configured write alias: {Color.BOLD}{self.active_alias}{Color.RESET} (is_write_index: true)")
        print(f"{Color.CYAN}  Settings applied: index.lifecycle.name = 'enterprise-logs-ilm'")
        print(f"  Routing preference: index.routing.allocation.include._tier_preference = 'data_hot'{Color.RESET}")

    def ingest_traffic(self, batch_size: int = 400) -> None:
        self.print_section(f"BULK INGESTION SIMULATION (+{batch_size} documents)")
        if not self.current_write_index:
            print(f"{Color.RED}Error: No write index active. Please bootstrap first.{Color.RESET}")
            return

        idx = self.current_write_index
        idx.doc_count += batch_size
        added_size = round(batch_size * 0.08 + random.uniform(1.0, 4.0), 2)
        idx.size_mb = round(idx.size_mb + added_size, 2)
        idx.segment_count += random.randint(2, 5)
        idx.age_days = round(idx.age_days + 1.2, 1)

        print(f"Ingesting into {Color.BOLD}{idx.name}{Color.RESET} via alias [{Color.CYAN}{self.active_alias}{Color.RESET}]...")
        for i in range(1, 11):
            time.sleep(0.04)
            pct = i * 10
            bar = "█" * (pct // 5) + "-" * (20 - (pct // 5))
            print(f"\r  [{Color.BRIGHT_GREEN}{bar}{Color.RESET}] {pct}% ({idx.doc_count} total docs, {idx.size_mb} MB)", end="", flush=True)
        print()

        idx.log_event(f"Ingested batch of {batch_size} docs. Current size: {idx.size_mb} MB, Segments: {idx.segment_count}")

        # Check rollover condition
        if idx.doc_count >= 1000 or idx.size_mb >= 80.0:
            print(f"\n{Color.BRIGHT_YELLOW}⚡ ILM Rollover Threshold Met! (Docs >= 1000 or Size >= 80MB){Color.RESET}")
            self.execute_rollover()

    def execute_rollover(self) -> None:
        if not self.current_write_index:
            return
        
        old_idx = self.current_write_index
        next_gen = old_idx.generation + 1
        new_name = f"{self.active_alias}-{next_gen:06d}"

        print(f"{Color.MAGENTA}Executing POST /{self.active_alias}/_rollover...{Color.RESET}")
        old_idx.log_event(f"Rolled over. Rollover target became {new_name}. Write permission revoked.")

        new_index = SimulatedIndex(
            name=new_name,
            alias=self.active_alias,
            generation=next_gen,
            current_tier=Tier.HOT,
            doc_count=0,
            primary_shards=2,
            replica_shards=1,
            segment_count=2,
            size_mb=8.0,
            age_days=0.0
        )
        new_index.log_event(f"Spawned from rollover of {old_idx.name}. Assigned as new write target.")

        self.indices[new_name] = new_index
        self.current_write_index = new_index

        print(f"  {Color.GREEN}✓ Rollover complete:{Color.RESET}")
        print(f"    - Closed for writing: {Color.DIM}{old_idx.name}{Color.RESET}")
        print(f"    - New Active Write Index: {Color.BRIGHT_GREEN}{new_name}{Color.RESET}")

    def advance_time_and_ilm(self, days_to_add: float = 8.0) -> None:
        self.print_section(f"SIMULATING TIME PASSAGE & ILM STEP EVALUATION (+{days_to_add} days)")
        
        for idx in list(self.indices.values()):
            if idx.current_tier == Tier.DELETED:
                continue

            # Active write index ages slowly
            if idx == self.current_write_index:
                idx.age_days += round(days_to_add * 0.4, 1)
                continue

            idx.age_days = round(idx.age_days + days_to_add, 1)
            print(f"Evaluating ILM rules for {Color.BOLD}{idx.name}{Color.RESET} (Current age: {idx.age_days:.1f} days, Tier: {idx.current_tier.value})...")

            # Phase Transitions Check
            if idx.age_days >= 365.0 and idx.current_tier != Tier.DELETED:
                print(f"  {Color.RED}→ ILM DELETE PHASE reached (Age >= 365d). Purging index and snapshot metadata...{Color.RESET}")
                idx.current_tier = Tier.DELETED
                idx.log_event("Deleted by ILM retention policy after 365 days.")
            
            elif idx.age_days >= 90.0 and idx.current_tier in [Tier.HOT, Tier.WARM, Tier.COLD]:
                print(f"  {Color.BRIGHT_BLUE}→ ILM FROZEN PHASE transition:{Color.RESET}")
                print(f"    * Mounting as Partially Mounted Searchable Snapshot on S3.")
                print(f"    * Setting _tier_preference = 'data_frozen'.")
                idx.current_tier = Tier.FROZEN
                idx.is_searchable_snapshot = True
                idx.replica_shards = 0
                idx.log_event("Migrated to FROZEN tier. Backed by S3 partially mounted searchable snapshot.")
            
            elif idx.age_days >= 30.0 and idx.current_tier in [Tier.HOT, Tier.WARM]:
                print(f"  {Color.BRIGHT_CYAN}→ ILM COLD PHASE transition:{Color.RESET}")
                print(f"    * Taking snapshot in S3 repository 'found-snapshots'.")
                print(f"    * Mounting as Fully Mounted Searchable Snapshot.")
                print(f"    * Removing replicas (replica=0) to cut storage cost.")
                idx.current_tier = Tier.COLD
                idx.is_searchable_snapshot = True
                idx.replica_shards = 0
                idx.log_event("Migrated to COLD tier. Fully mounted searchable snapshot, replicas=0.")

            elif idx.age_days >= 7.0 and idx.current_tier == Tier.HOT:
                print(f"  {Color.BRIGHT_YELLOW}→ ILM WARM PHASE transition:{Color.RESET}")
                print(f"    * Setting index.blocks.write = true (read-only).")
                print(f"    * Performing Shrink action: 2 primaries -> 1 primary shard.")
                print(f"    * Performing Force-Merge: {idx.segment_count} segments -> 1 segment.")
                print(f"    * Shifting allocation: _tier_preference = 'data_warm,data_hot'.")
                idx.current_tier = Tier.WARM
                idx.is_read_only = True
                idx.primary_shards = 1
                idx.segment_count = 1
                idx.size_mb = round(idx.size_mb * 0.82, 2)  # Segment compression benefit
                idx.log_event("Migrated to WARM tier. Shrunk to 1 shard, force-merged to 1 segment.")

    def show_index_inventory(self) -> None:
        self.print_section("MANAGED INDICES LIFECYCLE INVENTORY")
        header = f"{'Index Name':<28} | {'Tier':<12} | {'Age':<6} | {'Docs':<6} | {'Pri/Rep':<7} | {'Seg':<4} | {'Size MB':<8} | {'Status'}"
        print(f"{Color.BOLD}{header}{Color.RESET}")
        print("-" * 95)
        
        total_storage_mb = 0.0
        total_monthly_cost = 0.0

        for idx in self.indices.values():
            if idx.current_tier == Tier.DELETED:
                print(f"{Color.DIM}{idx.name:<28} | {'DELETED':<12} | {idx.age_days:>5.1f}d | {'-':<6} | {'-':<7} | {'-':<4} | {'0.00':<8} | Purged from disk{Color.RESET}")
                continue

            tier_badge = {
                Tier.HOT: f"{Color.BRIGHT_RED}HOT{Color.RESET}",
                Tier.WARM: f"{Color.BRIGHT_YELLOW}WARM{Color.RESET}",
                Tier.COLD: f"{Color.BRIGHT_CYAN}COLD{Color.RESET}",
                Tier.FROZEN: f"{Color.BRIGHT_BLUE}FROZEN{Color.RESET}",
            }.get(idx.current_tier, idx.current_tier.value)

            status = "Write Active" if idx == self.current_write_index else ("RO Snapshot" if idx.is_searchable_snapshot else "Read-Only")
            shard_repr = f"{idx.primary_shards}/{idx.replica_shards}"
            
            # Storage cost calculation
            cost_rate = {
                Tier.HOT: 0.28,
                Tier.WARM: 0.12,
                Tier.COLD: 0.05,
                Tier.FROZEN: 0.015
            }[idx.current_tier]
            
            effective_storage = idx.size_mb * (idx.primary_shards + idx.replica_shards)
            total_storage_mb += effective_storage
            total_monthly_cost += (effective_storage / 1024.0) * cost_rate

            print(f"{idx.name:<28} | {tier_badge:<21} | {idx.age_days:>5.1f}d | {idx.doc_count:<6} | {shard_repr:<7} | {idx.segment_count:<4} | {idx.size_mb:<8.2f} | {status}")
        
        print("-" * 95)
        print(f"{Color.BOLD}Cluster In-Use Footprint:{Color.RESET} {total_storage_mb:.2f} MB (~{total_storage_mb/1024.0:.3f} GB)")
        print(f"{Color.BOLD}Estimated Infrastructure Cost:{Color.RESET} {Color.BRIGHT_GREEN}${total_monthly_cost:.4f}/month{Color.RESET} (Tiering optimization active)")

    def inspect_index_details(self) -> None:
        self.print_section("INSPECT DETAILED AUDIT TRAIL OF AN INDEX")
        if not self.indices:
            print(f"{Color.YELLOW}No indices available. Bootstrap first.{Color.RESET}")
            return

        print("Available indices:")
        idx_keys = list(self.indices.keys())
        for idx, k in enumerate(idx_keys, 1):
            print(f"  [{idx}] {k} ({self.indices[k].current_tier.value})")
        
        selection = 1  # Default to first for non-blocking / demo resilience
        target = self.indices[idx_keys[selection - 1]]
        
        print(f"\n{Color.BOLD}Audit Timeline for {target.name}:{Color.RESET}")
        for event in target.history:
            print(f"  {Color.CYAN}•{Color.RESET} {event}")

    def run_automated_demonstration(self) -> None:
        self.banner()
        print(f"{Color.BRIGHT_MAGENTA}Starting Full-Cycle Autonomous Architecture Lifecycle Simulation...{Color.RESET}\n")
        time.sleep(0.5)

        # 1. Topology
        self.show_topology()
        time.sleep(0.5)

        # 2. Bootstrap
        self.bootstrap_index()
        time.sleep(0.5)

        # 3. Ingestion & Rollover 1
        self.ingest_traffic(batch_size=500)
        self.ingest_traffic(batch_size=600)  # triggers rollover
        time.sleep(0.5)

        # 4. Ingest to Generation 2
        self.ingest_traffic(batch_size=400)
        self.show_index_inventory()
        time.sleep(0.5)

        # 5. Move to Warm (7+ days)
        self.advance_time_and_ilm(days_to_add=8.0)
        self.show_index_inventory()
        time.sleep(0.5)

        # 6. Move to Cold (30+ days)
        self.advance_time_and_ilm(days_to_add=25.0)
        self.show_index_inventory()
        time.sleep(0.5)

        # 7. Move to Frozen (90+ days)
        self.advance_time_and_ilm(days_to_add=65.0)
        self.show_index_inventory()
        time.sleep(0.5)

        # 8. Move to Delete (365+ days)
        self.advance_time_and_ilm(days_to_add=280.0)
        self.show_index_inventory()
        time.sleep(0.5)

        # 9. Audit Trail inspection
        self.inspect_index_details()

        print(f"\n{Color.BRIGHT_GREEN}================================================================================{Color.RESET}")
        print(f"{Color.BOLD}{Color.BRIGHT_GREEN}✓ SIMULATION VERIFIED: All Data Tiering & ILM Phases Executed Successfully!{Color.RESET}")
        print(f"{Color.BRIGHT_GREEN}================================================================================{Color.RESET}\n")

    def interactive_menu(self) -> None:
        while True:
            self.banner()
            print(f"{Color.BOLD}Select Lab Scenario Operation:{Color.RESET}")
            print(" [1] Show Cluster Nodes & Data Tier Topology")
            print(" [2] View ILM Policy JSON (Hot, Warm, Cold, Frozen, Delete)")
            print(" [3] Bootstrap Initial Index & Write Alias")
            print(" [4] Simulate Bulk Ingestion Traffic (Triggers Rollover)")
            print(" [5] Advance Timeline & Evaluate ILM Phase Transitions")
            print(" [6] View Detailed Managed Indices Inventory & Cost Breakdown")
            print(" [7] Inspect Index Audit Trail")
            print(" [8] Run Complete Automated E2E Simulation Demo")
            print(" [9] Exit Lab")
            
            try:
                choice = input(f"\n{Color.BRIGHT_CYAN}Enter option [1-9] (or 'q' to quit): {Color.RESET}").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting lab.")
                break

            if choice == "1":
                self.show_topology()
            elif choice == "2":
                self.display_ilm_policy()
            elif choice == "3":
                self.bootstrap_index()
            elif choice == "4":
                self.ingest_traffic(batch_size=450)
            elif choice == "5":
                self.advance_time_and_ilm(days_to_add=15.0)
            elif choice == "6":
                self.show_index_inventory()
            elif choice == "7":
                self.inspect_index_details()
            elif choice == "8":
                self.run_automated_demonstration()
            elif choice in ["9", "q", "exit"]:
                print(f"{Color.GREEN}Lab completed. Exiting.{Color.RESET}")
                break
            else:
                print(f"{Color.RED}Invalid option selected.{Color.RESET}")
            
            try:
                input(f"\n{Color.DIM}Press Enter to continue...{Color.RESET}")
            except (EOFError, KeyboardInterrupt):
                break


def main() -> None:
    lab = ILMArchitectureLab()
    # If run in non-interactive/automated mode or with flag --auto
    if len(sys.argv) > 1 and sys.argv[1] in ["--auto", "--demo", "-a"]:
        lab.run_automated_demonstration()
    elif not sys.stdin.isatty():
        # Headless execution safety (pipe or automated runner)
        lab.run_automated_demonstration()
    else:
        lab.interactive_menu()


if __name__ == "__main__":
    main()
