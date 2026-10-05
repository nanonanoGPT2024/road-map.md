#!/usr/bin/env python3
"""
Lab Exercise: SRE Incident Management & FinOps Cloud Cost Architecture Simulator
Module: BAB-10-SRE-Incident-dan-FinOps (Modul 02)
Topic: Advanced Production Reliability, Multi-Window Alerting, Incident Response, & Cloud Economics
"""

import sys
import time
import random
from dataclasses import dataclass, field
from typing import List, Dict

# ANSI Terminal Colors
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"


@dataclass
class ServiceSLO:
    name: str
    target_availability: float  # e.g., 99.9% -> 0.999
    window_days: int = 30
    total_budget_minutes: float = field(init=False)
    consumed_budget_minutes: float = 0.0

    def __post_init__(self):
        # 30 days = 43,200 minutes
        total_period_minutes = self.window_days * 24 * 60
        allowed_downtime_ratio = 1.0 - self.target_availability
        self.total_budget_minutes = total_period_minutes * allowed_downtime_ratio

    @property
    def remaining_budget_pct(self) -> float:
        if self.total_budget_minutes <= 0:
            return 0.0
        rem = (self.total_budget_minutes - self.consumed_budget_minutes) / self.total_budget_minutes
        return max(0.0, rem * 100.0)

    @property
    def current_sli(self) -> float:
        total_window_minutes = self.window_days * 24 * 60
        actual_uptime = total_window_minutes - self.consumed_budget_minutes
        return (actual_uptime / total_window_minutes) * 100.0


@dataclass
class CloudResource:
    name: str
    resource_type: str
    hourly_cost_usd: float
    cpu_utilization_pct: float
    is_wasteful: bool = False

    def check_rightsizing(self) -> str:
        if self.cpu_utilization_pct < 10.0:
            self.is_wasteful = True
            return f"Underutilized ({self.cpu_utilization_pct:.1f}% CPU) -> Recommendation: Downscale/Terminate"
        elif self.cpu_utilization_pct > 80.0:
            return f"High Load ({self.cpu_utilization_pct:.1f}% CPU) -> Recommendation: Scale Out/Up"
        return f"Optimal ({self.cpu_utilization_pct:.1f}% CPU) -> Kept as is"


class SREFinOpsSimulator:
    def __init__(self):
        self.payment_slo = ServiceSLO(name="payment-gateway", target_availability=0.999)
        self.api_slo = ServiceSLO(name="core-api-gateway", target_availability=0.9995)
        self.resources: List[CloudResource] = [
            CloudResource("k8s-worker-pool-spot", "EKS Spot Instance", hourly_cost_usd=0.08, cpu_utilization_pct=65.0),
            CloudResource("k8s-worker-pool-onprem", "EKS On-Demand r5.4xlarge", hourly_cost_usd=1.008, cpu_utilization_pct=6.5),
            CloudResource("rds-aurora-primary", "Aurora PostgreSQL db.r6g.2xl", hourly_cost_usd=0.86, cpu_utilization_pct=42.0),
            CloudResource("elasticache-redis-cluster", "Redis Cache Node r6g.xlarge", hourly_cost_usd=0.34, cpu_utilization_pct=8.0),
            CloudResource("unattached-ebs-vol-091a", "gp3 Unattached 500GB EBS", hourly_cost_usd=0.06, cpu_utilization_pct=0.0, is_wasteful=True),
        ]
        self.incident_history: List[str] = []

    def print_banner(self):
        print(f"\n{Color.BOLD}{Color.CYAN}{'='*75}")
        print("  SRE INCIDENT RESPONSE & FINOPS CLOUD ARCHITECTURE SIMULATOR (BAB-10)")
        print(f"{'='*75}{Color.RESET}\n")

    def display_slo_status(self):
        print(f"\n{Color.BOLD}{Color.YELLOW}[SLO & Error Budget Dashboard - 30 Day Rolling Window]{Color.RESET}")
        print(f"{'-'*75}")
        print(f"{'Service Name':<22} | {'Target SLO':<12} | {'Current SLI':<13} | {'Remaining Budget':<18}")
        print(f"{'-'*75}")

        for slo in [self.payment_slo, self.api_slo]:
            rem = slo.remaining_budget_pct
            color = Color.GREEN if rem > 50 else (Color.YELLOW if rem > 20 else Color.RED)
            print(f"{slo.name:<22} | {slo.target_availability * 100:>10.3f}% | {slo.current_sli:>11.4f}% | {color}{rem:>15.2f}%{Color.RESET}")

        print(f"{'-'*75}")
        print(f"Policy: If Error Budget < 0%, P0 Freeze feature releases to focus on reliability!")

    def simulate_burn_rate_alert(self):
        print(f"\n{Color.BOLD}{Color.CYAN}[Multi-Window Multi-Burn-Rate Alert Evaluation]{Color.RESET}")
        print("Evaluating 1-hour window (14.4x burn rate) & 6-hour window (6x burn rate)...")
        time.sleep(0.5)

        # Simulate dynamic error rate spike
        simulated_error_rate = random.uniform(0.015, 0.055)  # 1.5% to 5.5% errors
        burn_rate = simulated_error_rate / (1.0 - self.payment_slo.target_availability)

        print(f"\nSimulated Telemetry Metrics:")
        print(f" - Traffic Volume: 25,000 req/min")
        print(f" - Error Rate (HTTP 5xx): {Color.RED}{simulated_error_rate * 100:.2f}%{Color.RESET}")
        print(f" - Calculated Burn Rate: {Color.BOLD}{burn_rate:.1f}x{Color.RESET}")

        downtime_spent = random.uniform(8.0, 18.0)
        self.payment_slo.consumed_budget_minutes += downtime_spent

        if burn_rate >= 14.4:
            print(f"\n{Color.BG_RED}{Color.WHITE} [CRITICAL ALERT - PAGING P1 ON-CALL] {Color.RESET}")
            print(f"{Color.RED}Alert: 14.4x Burn Rate exceeded in 1h window! (Consumes 2% budget in 1 hour){Color.RESET}")
            print("Action: PagerDuty triggered -> Incident Commander, Comms Lead, Ops Lead paged.")
            self.incident_history.append(f"P1 Incident: {burn_rate:.1f}x Burn Rate on {self.payment_slo.name}")
        elif burn_rate >= 6.0:
            print(f"\n{Color.BG_YELLOW}{Color.WHITE} [WARNING ALERT - TICKET P2] {Color.RESET}")
            print(f"{Color.YELLOW}Alert: 6x Burn Rate detected in 6h window! (Consumes 5% budget in 6 hours){Color.RESET}")
            print("Action: Slack alert sent to #eng-reliability channel for proactive triage.")
            self.incident_history.append(f"P2 Warning: {burn_rate:.1f}x Burn Rate on {self.payment_slo.name}")
        else:
            print(f"\n{Color.GREEN}[STABLE] Burn rate is within acceptable noise threshold.{Color.RESET}")

    def run_incident_response_drill(self):
        print(f"\n{Color.BOLD}{Color.RED}[Production Incident Response Drill & Mitigation]{Color.RESET}")
        print("Scenario: Cascading timeout in Database Connection Pool during flash sale.")
        steps = [
            ("Detection & Triage", "Grafana synthetic probes detect TTFB > 2500ms on /checkout"),
            ("Command & Declare", "Incident Commander assigned. Dedicated bridge created: #inc-2026-prod-01"),
            ("Automated Mitigation", "Deploying Envoy circuit-breaker + Load Shedding non-critical queries"),
            ("Traffic Drain & Canary", "Rolling back candidate v2.4.1 to v2.4.0 via ArgoCD Canary Rollback"),
            ("Recovery Verification", "SLI HTTP 5xx returns to < 0.01%, Error budget consumption halts"),
            ("Blameless Post-Mortem", "Action items recorded into Jira: add db connection pooling limits")
        ]

        for idx, (phase, detail) in enumerate(steps, start=1):
            time.sleep(0.3)
            print(f"  Step {idx}/6: {Color.BOLD}{phase:<25}{Color.RESET} -> {Color.CYAN}{detail}{Color.RESET}")

        self.incident_history.append("Drill Executed: Cascading Timeout Mitigated via Circuit Breaker")
        print(f"\n{Color.GREEN}Incident Drill Successfully Resolved with Zero Customer Data Loss!{Color.RESET}")

    def finops_cost_analysis(self):
        print(f"\n{Color.BOLD}{Color.MAGENTA}[FinOps Cloud Economics & Unit Cost Analysis]{Color.RESET}")
        print(f"{'-'*80}")
        print(f"{'Resource Identifier':<26} | {'Type':<22} | {'Monthly Cost':<12} | {'Status'}")
        print(f"{'-'*80}")

        total_monthly_spend = 0.0
        potential_savings = 0.0

        for res in self.resources:
            monthly_cost = res.hourly_cost_usd * 24 * 30
            total_monthly_spend += monthly_cost
            audit_note = res.check_rightsizing()

            status_color = Color.RED if res.is_wasteful else Color.GREEN
            print(f"{res.name:<26} | {res.resource_type:<22} | ${monthly_cost:>10.2f} | {status_color}{audit_note}{Color.RESET}")

            if res.is_wasteful:
                # Estimate 70% savings if rightsized or terminated
                potential_savings += monthly_cost * 0.75

        unit_orders = 1_500_000
        cost_per_order = total_monthly_spend / unit_orders

        print(f"{'-'*80}")
        print(f"{Color.BOLD}FinOps KPI Summary:{Color.RESET}")
        print(f" - Total Projected Monthly Spend : {Color.YELLOW}${total_monthly_spend:,.2f}{Color.RESET}")
        print(f" - Identified Waste / Optimizable: {Color.RED}${potential_savings:,.2f}{Color.RESET}")
        print(f" - Unit Economics (Cost / Order) : {Color.GREEN}${cost_per_order:.4f} USD{Color.RESET}")
        print(f" - FinOps Maturity Phase        : {Color.CYAN}Operate & Optimize (Continuous Rightsizing){Color.RESET}")

    def finops_auto_remediate(self):
        print(f"\n{Color.BOLD}{Color.GREEN}[FinOps Automated Waste Remediation]{Color.RESET}")
        remediated_count = 0
        for res in self.resources:
            if res.is_wasteful:
                print(f" -> Deleting orphan resource / Rightsizing instance: {Color.YELLOW}{res.name}{Color.RESET}")
                res.is_wasteful = False
                res.hourly_cost_usd *= 0.25  # Downscale cost
                res.cpu_utilization_pct = 55.0
                remediated_count += 1
                time.sleep(0.3)

        if remediated_count > 0:
            print(f"{Color.GREEN}Successfully remediated {remediated_count} resources. Cloud bill optimized!{Color.RESET}")
        else:
            print(f"{Color.CYAN}No wasteful resources detected. Infrastructure is lean.{Color.RESET}")

    def show_incident_timeline(self):
        print(f"\n{Color.BOLD}{Color.WHITE}[Incident History & Audit Log]{Color.RESET}")
        if not self.incident_history:
            print("No incidents recorded in this session.")
            return
        for idx, event in enumerate(self.incident_history, 1):
            print(f" [{idx}] {Color.CYAN}{event}{Color.RESET}")


def interactive_menu():
    sim = SREFinOpsSimulator()
    sim.print_banner()

    menu = (
        f"\n{Color.BOLD}PILIH MENU SIMULASI INTERAKTIF:{Color.RESET}\n"
        f"  {Color.CYAN}1.{Color.RESET} Tampilkan SLI / SLO & Sisa Error Budget\n"
        f"  {Color.CYAN}2.{Color.RESET} Simulasi Traffic Spike & Multi-Window Burn Rate Alert\n"
        f"  {Color.CYAN}3.{Color.RESET} Eksekusi SRE Incident Response Drill (P1 Outage Mitigation)\n"
        f"  {Color.CYAN}4.{Color.RESET} Audit FinOps (Cloud Spend, Waste, & Unit Economics)\n"
        f"  {Color.CYAN}5.{Color.RESET} Eksekusi FinOps Auto-Remediation (Rightsizing & Cleanup)\n"
        f"  {Color.CYAN}6.{Color.RESET} Tampilkan Audit Log Insiden\n"
        f"  {Color.CYAN}7.{Color.RESET} Jalankan Automated End-to-End Walkthrough (Demo Mode)\n"
        f"  {Color.CYAN}0.{Color.RESET} Keluar (Exit)\n"
    )

    # Check non-interactive or automated environment
    if not sys.stdin.isatty():
        print("[Non-interactive environment detected. Running full automated walkthrough...]")
        sim.display_slo_status()
        sim.simulate_burn_rate_alert()
        sim.run_incident_response_drill()
        sim.finops_cost_analysis()
        sim.finops_auto_remediate()
        sim.show_incident_timeline()
        print(f"\n{Color.BOLD}{Color.GREEN}Automated Verification Complete. All SRE & FinOps checks passed!{Color.RESET}")
        return

    while True:
        print(menu)
        try:
            choice = input(f"{Color.BOLD}Masukkan pilihan [0-7]: {Color.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting simulator.")
            break

        if choice == "1":
            sim.display_slo_status()
        elif choice == "2":
            sim.simulate_burn_rate_alert()
        elif choice == "3":
            sim.run_incident_response_drill()
        elif choice == "4":
            sim.finops_cost_analysis()
        elif choice == "5":
            sim.finops_auto_remediate()
        elif choice == "6":
            sim.show_incident_timeline()
        elif choice == "7":
            print(f"\n{Color.BOLD}Executing complete end-to-end simulation cycle...{Color.RESET}")
            sim.display_slo_status()
            sim.simulate_burn_rate_alert()
            sim.run_incident_response_drill()
            sim.finops_cost_analysis()
            sim.finops_auto_remediate()
            sim.show_incident_timeline()
        elif choice == "0":
            print(f"\n{Color.GREEN}Terima kasih telah menggunakan SRE & FinOps Simulator. Sampai jumpa!{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid, silakan coba lagi.{Color.RESET}")


if __name__ == "__main__":
    interactive_menu()
