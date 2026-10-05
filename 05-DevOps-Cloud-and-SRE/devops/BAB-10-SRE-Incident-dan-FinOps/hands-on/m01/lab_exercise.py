#!/usr/bin/env python3
"""
Lab Exercise: SRE Reliability, Incident Response & FinOps Engine
BAB-10: SRE, Incident Management, dan FinOps Cloud Optimization
Simulasi teknis interaktif fondasi DevOps/SRE.
"""

import sys
import time
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional

# ==============================================================================
# Terminal ANSI Color Palette
# ==============================================================================
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
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_BLUE = "\033[44m"


def header(text: str) -> None:
    border = "=" * 76
    print(f"\n{Color.CYAN}{Color.BOLD}{border}")
    print(f"  {text}")
    print(f"{border}{Color.RESET}")


def subheader(text: str) -> None:
    print(f"\n{Color.MAGENTA}{Color.BOLD}>>> {text}{Color.RESET}")


def status_badge(status: str) -> str:
    if status in ("OK", "HEALTHY", "RESOLVED", "OPTIMAL"):
        return f"{Color.GREEN}{Color.BOLD}[✓ {status}]{Color.RESET}"
    elif status in ("WARN", "DEGRADED", "INVESTIGATING", "BURNING"):
        return f"{Color.YELLOW}{Color.BOLD}[⚠ {status}]{Color.RESET}"
    else:
        return f"{Color.RED}{Color.BOLD}[✗ {status}]{Color.RESET}"


def progress_bar(percentage: float, width: int = 30) -> str:
    filled = int(width * (min(100.0, max(0.0, percentage)) / 100.0))
    bar = "█" * filled + "░" * (width - filled)
    if percentage >= 80.0:
        col = Color.GREEN
    elif percentage >= 40.0:
        col = Color.YELLOW
    else:
        col = Color.RED
    return f"{col}[{bar}] {percentage:5.1f}%{Color.RESET}"


# ==============================================================================
# SRE Module: SLI, SLO & Error Budget Tracker
# ==============================================================================
@dataclass
class SLOTracker:
    target_slo: float = 99.90  # 99.9% Three Nines
    rolling_window_days: int = 30
    total_events: int = 1_000_000
    good_events: int = 999_250

    @property
    def bad_events(self) -> int:
        return self.total_events - self.good_events

    @property
    def current_sli(self) -> float:
        if self.total_events == 0:
            return 100.0
        return (self.good_events / self.total_events) * 100.0

    @property
    def total_error_budget_events(self) -> int:
        allowed_failure_ratio = (100.0 - self.target_slo) / 100.0
        return int(self.total_events * allowed_failure_ratio)

    @property
    def remaining_budget_events(self) -> int:
        return max(0, self.total_error_budget_events - self.bad_events)

    @property
    def error_budget_percent(self) -> float:
        if self.total_error_budget_events == 0:
            return 0.0
        return (self.remaining_budget_events / self.total_error_budget_events) * 100.0

    def calculate_burn_rate(self, window_hours: float, window_bad_events: int) -> float:
        """
        Burn Rate 1.0 berarti menghabiskan 100% budget tepat dalam 30 hari (720 jam).
        Burn Rate 14.4 menghabiskan 100% budget dalam 2 hari (5% dalam 1 jam -> Pager Alert SEV-1).
        """
        total_hours = self.rolling_window_days * 24
        expected_bad_per_hour = self.total_error_budget_events / total_hours
        actual_bad_per_hour = window_bad_events / max(window_hours, 0.001)
        if expected_bad_per_hour == 0:
            return 0.0
        return actual_bad_per_hour / expected_bad_per_hour

    def run_simulation(self) -> None:
        header("1. SRE CORE: SLI / SLO & ERROR BUDGET CALCULATION ENGINE")
        print(f"Target SLO Availability   : {Color.BOLD}{self.target_slo:.2f}%{Color.RESET} (Rolling {self.rolling_window_days} Days)")
        print(f"Total Window Request      : {self.total_events:,} events")
        print(f"Total Allowed Failures    : {self.total_error_budget_events:,} errors")
        print(f"Actual Good Requests      : {self.good_events:,}")
        print(f"Actual Failure Requests   : {self.bad_events:,}")

        sli_val = self.current_sli
        badge = status_badge("HEALTHY" if sli_val >= self.target_slo else "DEGRADED")
        print(f"Calculated SLI            : {Color.BOLD}{sli_val:.4f}%{Color.RESET} {badge}")
        
        rem_pct = self.error_budget_percent
        print(f"Error Budget Sisa         : {progress_bar(rem_pct)} ({self.remaining_budget_events:,} errors left)")

        subheader("Multi-Window Multi-Burn-Rate Alert Evaluation")
        test_windows = [
            ("1 Hour Window", 1.0, 75, 14.4),   # Severe spike
            ("6 Hour Window", 6.0, 120, 6.0),    # Steady erosion
            ("24 Hour Window", 24.0, 50, 1.0),   # Nominal traffic
        ]
        
        print(f"{'Time Window':<16} | {'Bad Events':<10} | {'Burn Rate':<10} | {'Threshold':<10} | {'Alert Severity'}")
        print("-" * 72)
        for name, hrs, bads, thresh in test_windows:
            rate = self.calculate_burn_rate(hrs, bads)
            if rate >= 14.4:
                alert = f"{Color.RED}{Color.BOLD}CRITICAL (Page SRE On-Call){Color.RESET}"
            elif rate >= 6.0:
                alert = f"{Color.YELLOW}{Color.BOLD}WARNING (Slack Ticket){Color.RESET}"
            else:
                alert = f"{Color.GREEN}NORMAL (No Page){Color.RESET}"
            print(f"{name:<16} | {bads:<10} | {rate:8.2f}x  | {thresh:8.2f}x  | {alert}")


# ==============================================================================
# Incident Management Module
# ==============================================================================
class Severity(Enum):
    SEV1 = "SEV-1 (Critical Outage, Revenue/Customer Blocking)"
    SEV2 = "SEV-2 (High Impact, Core Feature Degraded, Workaround Exists)"
    SEV3 = "SEV-3 (Moderate Impact, Non-Critical Service Down)"


@dataclass
class Incident:
    id: str
    title: str
    severity: Severity
    mttd_minutes: float  # Mean Time to Detect
    mttr_minutes: float  # Mean Time to Resolve
    root_cause: str
    action_item: str


class IncidentSimulation:
    def __init__(self):
        self.incidents: List[Incident] = [
            Incident(
                id="INC-4091",
                title="Payment Gateway Timeout (504 Gateway Timeout)",
                severity=Severity.SEV1,
                mttd_minutes=2.4,
                mttr_minutes=18.5,
                root_cause="Database Connection Pool Exhaustion akibat unindexed query",
                action_item="Implement circuit breaker & query timeout limit 2000ms"
            ),
            Incident(
                id="INC-4092",
                title="Image Processing Worker Queue Latency Spike",
                severity=Severity.SEV2,
                mttd_minutes=8.0,
                mttr_minutes=42.0,
                root_cause="Redis memory limit eviction policy OOM Kill",
                action_item="Scale Redis cluster shard & tuning maxmemory-policy to volatile-lru"
            ),
            Incident(
                id="INC-4093",
                title="Staging Cluster Ingress SSL Certificate Expired",
                severity=Severity.SEV3,
                mttd_minutes=15.0,
                mttr_minutes=25.0,
                root_cause="Cert-manager ACME HTTP-01 challenge ingress path blocked",
                action_item="Automate Prometheus cert_exporter expiry alert at 14 days"
            ),
        ]

    def run_simulation(self) -> None:
        header("2. INCIDENT MANAGEMENT & MTTR / MTTD LIFECYCLE SIMULATOR")
        print(f"Total Recorded Incidents  : {len(self.incidents)}")
        avg_mttd = sum(i.mttd_minutes for i in self.incidents) / len(self.incidents)
        avg_mttr = sum(i.mttr_minutes for i in self.incidents) / len(self.incidents)

        print(f"Average MTTD (Detection)  : {Color.BOLD}{Color.CYAN}{avg_mttd:.2f} Minutes{Color.RESET}")
        print(f"Average MTTR (Recovery)   : {Color.BOLD}{Color.YELLOW}{avg_mttr:.2f} Minutes{Color.RESET}")

        subheader("Incident Post-Mortem & Timeline Log")
        for inc in self.incidents:
            col = Color.RED if inc.severity == Severity.SEV1 else Color.YELLOW if inc.severity == Severity.SEV2 else Color.WHITE
            print(f"\n{col}{Color.BOLD}• [{inc.id}] {inc.title}{Color.RESET}")
            print(f"  Severity    : {inc.severity.value}")
            print(f"  Detection   : MTTD = {inc.mttd_minutes} min | Recovery: MTTR = {inc.mttr_minutes} min")
            print(f"  Root Cause  : {Color.WHITE}{inc.root_cause}{Color.RESET}")
            print(f"  Remediation : {Color.GREEN}{inc.action_item}{Color.RESET}")

        subheader("Simulasi Triage Live Incident Drill")
        print(f"Menjalankan simulasi alert trigger... [PAGERDUTY DISPATCH]")
        time.sleep(0.3)
        print(f"  [T+0m] High Error Rate Alert on API Gateway (5xx > 5%)")
        print(f"  [T+2m] Incident Commander (IC) declared SEV-1. War Room opened.")
        print(f"  [T+5m] Ops Lead executing automated rollback via ArgoCD sync.")
        print(f"  [T+8m] Traffic normalized. Error rate dropped to 0.02%.")
        print(f"  {status_badge('RESOLVED')} Status page updated: Incident mitigated in 8 minutes.")


# ==============================================================================
# FinOps Module: Cloud Cost & Waste Optimization
# ==============================================================================
@dataclass
class CloudResource:
    name: str
    resource_type: str
    monthly_cost_usd: float
    cpu_utilization_avg: float
    is_idle: bool
    recommended_action: str
    potential_savings_usd: float


class FinOpsEngine:
    def __init__(self):
        self.resources: List[CloudResource] = [
            CloudResource(
                name="k8s-prod-worker-large-c5.4xlarge",
                resource_type="EC2 Instance",
                monthly_cost_usd=510.0,
                cpu_utilization_avg=6.5,
                is_idle=False,
                recommended_action="Downsize to c5.xlarge + Enable Karpenter Auto-scaling",
                potential_savings_usd=382.50
            ),
            CloudResource(
                name="dev-analytics-db-snapshot-unattached",
                resource_type="EBS Volume / Snapshot",
                monthly_cost_usd=140.0,
                cpu_utilization_avg=0.0,
                is_idle=True,
                recommended_action="Purge unattached EBS volume older than 30 days",
                potential_savings_usd=140.00
            ),
            CloudResource(
                name="qa-staging-aurora-cluster",
                resource_type="RDS PostgreSQL",
                monthly_cost_usd=420.0,
                cpu_utilization_avg=2.0,
                is_idle=True,
                recommended_action="Migrate to Aurora Serverless v2 with auto-pause",
                potential_savings_usd=294.00
            ),
            CloudResource(
                name="nat-gateway-us-east-1a",
                resource_type="VPC NAT Gateway",
                monthly_cost_usd=230.0,
                cpu_utilization_avg=12.0,
                is_idle=False,
                recommended_action="Configure S3/DynamoDB Gateway Endpoints (Bypass NAT)",
                potential_savings_usd=165.00
            )
        ]

    def run_simulation(self) -> None:
        header("3. FINOPS ENGINE: CLOUD UNIT ECONOMICS & WASTE PRUNING")
        total_spend = sum(r.monthly_cost_usd for r in self.resources)
        total_savings = sum(r.potential_savings_usd for r in self.resources)
        optimized_spend = total_spend - total_savings
        savings_ratio = (total_savings / total_spend) * 100.0

        print(f"Current Monthly Cloud Spend  : {Color.RED}{Color.BOLD}${total_spend:,.2f} USD{Color.RESET}")
        print(f"Identified Waste & Bloat     : {Color.YELLOW}${total_savings:,.2f} USD{Color.RESET}")
        print(f"Target Optimized Monthly Run : {Color.GREEN}{Color.BOLD}${optimized_spend:,.2f} USD{Color.RESET}")
        print(f"Potential FinOps Efficiency  : {Color.CYAN}{savings_ratio:.1f}% Savings{Color.RESET}")

        subheader("Audit Temuan Sumber Pemborosan Infrastruktur")
        print(f"{'Resource Name':<34} | {'Type':<15} | {'Cost':<9} | {'CPU%':<5} | {'Status'}")
        print("-" * 76)
        for r in self.resources:
            stat = status_badge("IDLE" if r.is_idle else "BURNING")
            print(f"{r.name[:34]:<34} | {r.resource_type:<15} | ${r.monthly_cost_usd:>6.1f} | {r.cpu_utilization_avg:>4.1f}% | {stat}")

        subheader("Rekomendasi Aksi Efisiensi FinOps")
        for idx, r in enumerate(self.resources, 1):
            print(f"{idx}. {Color.BOLD}{r.name}{Color.RESET} ({r.resource_type})")
            print(f"   Aksi      : {Color.WHITE}{r.recommended_action}{Color.RESET}")
            print(f"   Penghematan: {Color.GREEN}{Color.BOLD}+${r.potential_savings_usd:.2f}/bulan{Color.RESET}")


# ==============================================================================
# Interactive CLI Menu & Dispatcher
# ==============================================================================
def display_banner():
    banner = f"""
{Color.CYAN}{Color.BOLD}╔════════════════════════════════════════════════════════════════════════════╗
║    ENTERPRISE SRE, INCIDENT RESPONSE & FINOPS CLOUD SIMULATOR              ║
║    BAB-10 DevOps Technical Lab Platform (Python 3 Engine)                 ║
╚════════════════════════════════════════════════════════════════════════════╝{Color.RESET}
    """
    print(banner)


def run_full_suite():
    slo = SLOTracker()
    slo.run_simulation()

    inc = IncidentSimulation()
    inc.run_simulation()

    finops = FinOpsEngine()
    finops.run_simulation()

    header("SIMULASI SELESAI: KESIAPAN INTEGRASI OPERASIONAL 100%")
    print(f"{Color.GREEN}{Color.BOLD}Semua metrik SRE, protokol insiden, dan kalkulasi FinOps terverifikasi stabil.{Color.RESET}\n")


def interactive_menu():
    slo = SLOTracker()
    inc = IncidentSimulation()
    finops = FinOpsEngine()

    while True:
        display_banner()
        print(f"{Color.BOLD}Menu Simulasi Interaktif:{Color.RESET}")
        print("  1. Hitung SLI/SLO & Error Budget Burn Rate")
        print("  2. Jalankan Simulasi Siklus Insiden (MTTD / MTTR)")
        print("  3. Analisis Pemborosan Cloud FinOps & Rightsizing")
        print("  4. Eksekusi Seluruh Rangkaian Simulasi (End-to-End)")
        print("  5. Keluar")

        try:
            choice = input(f"\n{Color.YELLOW}{Color.BOLD}Pilih opsi [1-5]: {Color.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{Color.CYAN}Simulasi dihentikan.{Color.RESET}")
            break

        if choice == "1":
            slo.run_simulation()
        elif choice == "2":
            inc.run_simulation()
        elif choice == "3":
            finops.run_simulation()
        elif choice == "4":
            run_full_suite()
        elif choice == "5" or choice.lower() in ("q", "quit", "exit"):
            print(f"\n{Color.GREEN}Terima kasih telah menjalankan modul BAB-10 DevOps Lab.{Color.RESET}")
            break
        else:
            print(f"\n{Color.RED}Opsi tidak valid. Silakan pilih 1 - 5.{Color.RESET}")

        try:
            input(f"\n{Color.DIM}Tekan [Enter] untuk kembali ke menu...{Color.RESET}")
        except (EOFError, KeyboardInterrupt):
            break


def main():
    # Jika dijalankan di environment non-TTY atau menerima argument non-interaktif
    if not sys.stdin.isatty() or "--demo" in sys.argv:
        display_banner()
        run_full_suite()
    else:
        interactive_menu()


if __name__ == "__main__":
    main()
