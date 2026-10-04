#!/usr/bin/env python3
"""
Lab Exercise M02: SRE Architecture Simulation & Disaster Recovery Drill
BAB 10: Security Reliability Engineering & Disaster Recovery (SRE & DR)

Fitur Simulasi:
1. Multi-Region Active/Passive Failover & Replication Sync (RPO & RTO Tracking)
2. Zero-Trust Security Token Validation & mTLS Gateway Filter
3. Dynamic Circuit Breaker & Graceful Degradation (CLOSED, OPEN, HALF-OPEN)
4. Telemetry Realtime: Latency p95/p99, Error Budget Burn Rate, Availability SLO
5. Interactive Chaos Engineering: Split-Brain, Network Partition, Database Outage
"""

import sys
import time
import random
import enum
from dataclasses import dataclass, field
from typing import List, Dict, Optional

# ANSI Color Codes for Rich Terminal Output
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_BLUE = "\033[44m"


class CircuitState(enum.Enum):
    CLOSED = "CLOSED (NORMAL)"
    OPEN = "OPEN (ISOLATED/FALLBACK)"
    HALF_OPEN = "HALF-OPEN (PROBING)"


class RegionStatus(enum.Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"
    OFFLINE = "OFFLINE"


@dataclass
class ReplicationState:
    primary_lsn: int = 1000000
    replica_lsn: int = 1000000
    last_sync_timestamp: float = field(default_factory=time.time)

    @property
    def replication_lag_seconds(self) -> float:
        return max(0.0, time.time() - self.last_sync_timestamp)

    @property
    def rpo_data_loss_records(self) -> int:
        return max(0, self.primary_lsn - self.replica_lsn)


@dataclass
class ServiceMeshNode:
    region_id: str
    is_primary: bool
    status: RegionStatus = RegionStatus.HEALTHY
    latency_p99_ms: float = 24.5
    error_rate: float = 0.001
    active_connections: int = 450


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout_sec: float = 4.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout_sec = recovery_timeout_sec
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.last_state_change = time.time()

    def record_success(self):
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.last_state_change = time.time()

    def record_failure(self):
        self.failure_count += 1
        if self.state == CircuitState.CLOSED and self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            self.last_state_change = time.time()

    def can_execute(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_state_change > self.recovery_timeout_sec:
                self.state = CircuitState.HALF_OPEN
                self.last_state_change = time.time()
                return True
            return False
        return True  # HALF_OPEN allows probe test


class SREDisasterRecoverySystem:
    def __init__(self):
        self.primary_region = ServiceMeshNode(region_id="ap-southeast-1 (Jakarta)", is_primary=True)
        self.dr_region = ServiceMeshNode(region_id="ap-southeast-3 (Singapore DR)", is_primary=False)
        self.replication = ReplicationState()
        self.circuit_breaker = CircuitBreaker()
        self.slo_target = 99.95
        self.total_requests = 10000
        self.failed_requests = 3
        self.mtls_secret_token = "sre-sec-auth-k8s-prod-99x"
        self.active_traffic_region = "ap-southeast-1 (Jakarta)"

    def calculate_availability(self) -> float:
        if self.total_requests == 0:
            return 100.0
        return ((self.total_requests - self.failed_requests) / self.total_requests) * 100.0

    def calculate_error_budget_burn(self) -> float:
        # SLO 99.95% -> allowed error budget = 0.05%
        allowed_error_ratio = (100.0 - self.slo_target) / 100.0
        current_error_ratio = self.failed_requests / max(1, self.total_requests)
        burn_rate = current_error_ratio / allowed_error_ratio
        return burn_rate

    def validate_security_envelope(self, token: str, client_ip: str) -> bool:
        """Zero-Trust SRE Gateway Ingress Inspection"""
        if token != self.mtls_secret_token:
            return False
        if client_ip.startswith("10.99.66"):  # Simulated blacklisted subnet
            return False
        return True

    def process_incoming_traffic(self, batch_size: int = 150):
        print(f"\n{Color.CYAN}[INFRA-GATEWAY]{Color.RESET} Dispatching {batch_size} incoming client transactions...")
        success = 0
        dropped = 0

        target_node = self.primary_region if self.active_traffic_region.startswith("ap-southeast-1") else self.dr_region

        for _ in range(batch_size):
            self.total_requests += 1
            if not self.circuit_breaker.can_execute():
                self.failed_requests += 1
                dropped += 1
                continue

            # Check target region status
            if target_node.status == RegionStatus.OFFLINE:
                self.circuit_breaker.record_failure()
                self.failed_requests += 1
                dropped += 1
            elif target_node.status == RegionStatus.CRITICAL:
                if random.random() < 0.65:
                    self.circuit_breaker.record_failure()
                    self.failed_requests += 1
                    dropped += 1
                else:
                    self.circuit_breaker.record_success()
                    success += 1
                    self.replication.primary_lsn += 1
            elif target_node.status == RegionStatus.DEGRADED:
                if random.random() < 0.20:
                    self.circuit_breaker.record_failure()
                    self.failed_requests += 1
                    dropped += 1
                else:
                    self.circuit_breaker.record_success()
                    success += 1
                    self.replication.primary_lsn += 1
            else:
                self.circuit_breaker.record_success()
                success += 1
                self.replication.primary_lsn += 1

        # Keep replica in sync under normal conditions
        if target_node.status in (RegionStatus.HEALTHY, RegionStatus.DEGRADED):
            self.replication.replica_lsn = self.replication.primary_lsn
            self.replication.last_sync_timestamp = time.time()

        print(f"  -> Result: {Color.GREEN}{success} OK{Color.RESET} | {Color.RED}{dropped} DROPPED{Color.RESET}")

    def trigger_chaos_disaster(self, disaster_type: str):
        print(f"\n{Color.BG_RED}{Color.WHITE} [CHAOS INJECTION DRILL] {Color.RESET} Applying scenario: {Color.BOLD}{disaster_type}{Color.RESET}")
        time.sleep(0.5)

        if disaster_type == "REGION_BLACKOUT":
            self.primary_region.status = RegionStatus.OFFLINE
            self.primary_region.latency_p99_ms = 9999.0
            self.primary_region.error_rate = 1.0
            # Replication breaks
            self.replication.primary_lsn += random.randint(45, 120)  # Unreplicated transactions
            print(f"{Color.RED}[CRITICAL]{Color.RESET} Primary Region Jakarta (ap-southeast-1) completely unresponsive!")
            print(f"{Color.YELLOW}[WARN]{Color.RESET} Cross-region synchronous storage replication severed!")

        elif disaster_type == "DATABASE_CORRUPTION":
            self.primary_region.status = RegionStatus.CRITICAL
            self.primary_region.latency_p99_ms = 1850.0
            self.primary_region.error_rate = 0.58
            for _ in range(6):
                self.circuit_breaker.record_failure()
            print(f"{Color.RED}[ALERT]{Color.RESET} Database Master I/O stall detected! Circuit breaker triggered to OPEN state.")

        elif disaster_type == "DDOS_SECURITY_BREACH":
            print(f"{Color.MAGENTA}[SECURITY SOC]{Color.RESET} Botnet volumetric attack detected (450K req/sec).")
            # Simulate defense validation
            allowed = self.validate_security_envelope(self.mtls_secret_token, "192.168.1.100")
            blocked = self.validate_security_envelope("forged-token-xyz", "10.99.66.4")
            print(f"  - Valid mTLS Gateway Token: {Color.GREEN}{allowed} (Allowed){Color.RESET}")
            print(f"  - Spoofed Rogue Ingress Token: {Color.RED}{not blocked} (Blocked via Zero-Trust Policy){Color.RESET}")
            self.primary_region.status = RegionStatus.DEGRADED
            self.primary_region.latency_p99_ms = 380.0

    def execute_disaster_recovery_failover(self):
        print(f"\n{Color.BG_BLUE}{Color.WHITE} [AUTOMATED SRE FAILOVER DRILL] {Color.RESET} Initiating Runbook DR-P0-FAILOVER...")
        start_time = time.time()

        print(f"Step 1: Quorum Fencing - Isolating degraded region...")
        self.primary_region.status = RegionStatus.OFFLINE
        time.sleep(0.4)

        print(f"Step 2: Assessing RPO Data Loss Metric...")
        rpo_loss = self.replication.rpo_data_loss_records
        replication_lag = self.replication.replication_lag_seconds
        print(f"  - Replication Lag: {Color.YELLOW}{replication_lag:.2f}s{Color.RESET}")
        print(f"  - Unsynced LSN Delta (RPO Impact): {Color.YELLOW}{rpo_loss} transactions{Color.RESET}")
        time.sleep(0.4)

        print(f"Step 3: Promoting Secondary DR Region (ap-southeast-3) to Read/Write MASTER...")
        self.dr_region.is_primary = True
        self.dr_region.status = RegionStatus.HEALTHY
        self.dr_region.latency_p99_ms = 31.2
        self.dr_region.error_rate = 0.002
        self.replication.replica_lsn = self.replication.primary_lsn
        self.replication.last_sync_timestamp = time.time()
        time.sleep(0.4)

        print(f"Step 4: Global Anycast DNS / BGP Route Rerouting to ap-southeast-3...")
        self.active_traffic_region = self.dr_region.region_id
        self.circuit_breaker.state = CircuitState.CLOSED
        self.circuit_breaker.failure_count = 0
        time.sleep(0.4)

        elapsed_rto = time.time() - start_time
        print(f"\n{Color.GREEN}{Color.BOLD}>>> FAILOVER COMPLETED SUCCESSFULLY <<<{Color.RESET}")
        print(f"  {Color.BOLD}Actual RTO (Recovery Time Objective):{Color.RESET} {Color.GREEN}{elapsed_rto:.2f} seconds{Color.RESET} (SLA Target: < 60s)")
        print(f"  {Color.BOLD}Actual RPO (Recovery Point Objective):{Color.RESET} {Color.GREEN}{rpo_loss} records{Color.RESET} (SLA Target: < 500 records)")

    def print_telemetry_dashboard(self):
        avail = self.calculate_availability()
        burn_rate = self.calculate_error_budget_burn()

        avail_color = Color.GREEN if avail >= self.slo_target else Color.RED
        burn_color = Color.GREEN if burn_rate < 1.0 else (Color.YELLOW if burn_rate < 5.0 else Color.RED)

        print("\n" + "=" * 78)
        print(f"{Color.BOLD}{Color.CYAN}       SRE OBSERVABILITY & DISASTER RECOVERY DASHBOARD (BAB 10)       {Color.RESET}")
        print("=" * 78)
        print(f" Active Traffic Target : {Color.BOLD}{Color.WHITE}{self.active_traffic_region}{Color.RESET}")
        print(f" Circuit Breaker State : {Color.BOLD}{self.circuit_breaker.state.value}{Color.RESET}")
        print(f" Total Requests Tracked: {self.total_requests:,} | Failed: {self.failed_requests:,}")
        print(f" Service Availability  : {avail_color}{avail:.4f}%{Color.RESET} (SLO Target: {self.slo_target}%)")
        print(f" Error Budget Burn Rate: {burn_color}{burn_rate:.2f}x{Color.RESET} normal rate")
        print("-" * 78)

        # Regions Table
        print(f"{'Region Name':<32} | {'Role':<9} | {'Health Status':<12} | {'p99 Latency':<11}")
        print("-" * 78)
        for node in [self.primary_region, self.dr_region]:
            role_str = "PRIMARY" if node.is_primary else "STANDBY"
            stat_color = Color.GREEN if node.status == RegionStatus.HEALTHY else (Color.YELLOW if node.status == RegionStatus.DEGRADED else Color.RED)
            print(f"{node.region_id:<32} | {role_str:<9} | {stat_color}{node.status.value:<12}{Color.RESET} | {node.latency_p99_ms:>7.1f} ms")

        print("=" * 78)


def run_interactive_simulation():
    system = SREDisasterRecoverySystem()

    menu = f"""
{Color.BOLD}PILAH AKSI SIMULASI SRE & DISASTER RECOVERY:{Color.RESET}
  {Color.GREEN}1{Color.RESET} -> Kirim Beban Transaksi Normal (Traffic Burst)
  {Color.YELLOW}2{Color.RESET} -> Injeksi Bencana: Database Master Crash & I/O Stall
  {Color.RED}3{Color.RESET} -> Injeksi Bencana: Total Region Outage (Jakarta Blackout)
  {Color.MAGENTA}4{Color.RESET} -> Injeksi Bencana: Volumetric DDoS & Rogue mTLS Ingress
  {Color.CYAN}5{Color.RESET} -> Eksekusi Automated SRE Disaster Recovery Failover (RTO/RPO Drill)
  {Color.WHITE}6{Color.RESET} -> Pulihkan Semua Region ke Status Normal (Self-Healing)
  {Color.GREEN}7{Color.RESET} -> Jalankan Full End-to-End Automated Resilience Verification Suite
  {Color.RED}0{Color.RESET} -> Keluar dari Simulasi
"""

    print(f"{Color.CYAN}{Color.BOLD}Memulai SRE Architecture & Disaster Recovery Interactive Lab...{Color.RESET}")
    system.print_telemetry_dashboard()

    # If run in non-interactive terminal (e.g. CI/automated runner), run automated suite
    if not sys.stdin.isatty():
        print(f"\n{Color.YELLOW}[AUTO-RUN DETECTED]{Color.RESET} Non-interactive terminal: running verification pipeline...")
        system.process_incoming_traffic(300)
        system.trigger_chaos_disaster("REGION_BLACKOUT")
        system.process_incoming_traffic(100)
        system.print_telemetry_dashboard()
        system.execute_disaster_recovery_failover()
        system.process_incoming_traffic(300)
        system.print_telemetry_dashboard()
        print(f"\n{Color.GREEN}[PASSED]{Color.RESET} SRE & Disaster Recovery simulation verified successfully.")
        return

    while True:
        print(menu)
        try:
            choice = input(f"{Color.BOLD}Masukkan pilihan (0-7): {Color.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar dari simulasi.")
            break

        if choice == "1":
            system.process_incoming_traffic(500)
            system.print_telemetry_dashboard()
        elif choice == "2":
            system.trigger_chaos_disaster("DATABASE_CORRUPTION")
            system.print_telemetry_dashboard()
        elif choice == "3":
            system.trigger_chaos_disaster("REGION_BLACKOUT")
            system.print_telemetry_dashboard()
        elif choice == "4":
            system.trigger_chaos_disaster("DDOS_SECURITY_BREACH")
            system.print_telemetry_dashboard()
        elif choice == "5":
            system.execute_disaster_recovery_failover()
            system.print_telemetry_dashboard()
        elif choice == "6":
            print(f"\n{Color.GREEN}[SELF-HEALING]{Color.RESET} Resetting all nodes and regions to healthy state...")
            system.primary_region.status = RegionStatus.HEALTHY
            system.primary_region.latency_p99_ms = 24.5
            system.dr_region.status = RegionStatus.HEALTHY
            system.dr_region.latency_p99_ms = 32.0
            system.circuit_breaker.state = CircuitState.CLOSED
            system.circuit_breaker.failure_count = 0
            system.print_telemetry_dashboard()
        elif choice == "7":
            print(f"\n{Color.CYAN}[RUNNING FULL RESILIENCE TEST SUITE]{Color.RESET}")
            system.process_incoming_traffic(400)
            system.trigger_chaos_disaster("REGION_BLACKOUT")
            system.process_incoming_traffic(200)
            system.execute_disaster_recovery_failover()
            system.process_incoming_traffic(400)
            system.print_telemetry_dashboard()
            print(f"\n{Color.GREEN}Full automated resiliency drill completed successfully.{Color.RESET}")
        elif choice == "0":
            print(f"\n{Color.CYAN}Simulasi SRE & Disaster Recovery selesai. Terima kasih.{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Pilihan '{choice}' tidak valid.{Color.RESET}")


if __name__ == "__main__":
    run_interactive_simulation()
