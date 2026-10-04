#!/usr/bin/env python3
"""
SRE Lab Exercise: Incident Lifecycle, On-Call Response, and Blameless Post-Mortem
Modul 02: Advanced Production Incident Response Simulator
"""

import sys
import time
import random
from datetime import datetime

# ANSI Color Codes
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


class ServiceState:
    def __init__(self):
        self.gateway_status = "HEALTHY"
        self.payment_api_status = "DEGRADED"
        self.db_pool_utilization = 98.4  # percentage
        self.error_rate = 14.8          # percentage (SLO threshold: < 0.5%)
        self.p99_latency_ms = 2450       # ms (SLO threshold: < 250ms)
        self.circuit_breaker_active = False
        self.db_failover_executed = False
        self.canary_rolled_back = False
        self.traffic_shedding_rate = 0


class IncidentSimulator:
    def __init__(self):
        self.state = ServiceState()
        self.incident_id = f"INC-{random.randint(1000, 9999)}"
        self.timeline = []
        self.start_time = datetime.now()
        self.ic_name = "Primary On-Call"

    def log_event(self, description: str, severity: str = "INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.timeline.append({"time": timestamp, "desc": description, "severity": severity})

    def print_banner(self):
        print(f"\n{BOLD}{BG_RED}{WHITE} [SRE SIMULATION ENGINE] SEV-1 INCIDENT RESPONSE {RESET}")
        print(f"{CYAN}Module: BAB-06 Incident Lifecycle, On-Call, & Blameless Post-Mortem{RESET}\n")

    def print_alert(self):
        self.log_event("PagerDuty Alert Triggered: Multi-Window Multi-Burn-Rate Alert (14.4x burn)", "ALERT")
        print(f"{RED}{BOLD}🚨 [PAGERDUTY HIGH-SEVERITY ALERT] 🚨{RESET}")
        print(f"Incident ID   : {BOLD}{self.incident_id}{RESET}")
        print(f"Service Target: {YELLOW}checkout-payment-pipeline:v2.4.1{RESET}")
        print(f"Condition     : {RED}Burn Rate 14.4x (Consuming 10% budget in 1 hour){RESET}")
        print(f"P99 Latency   : {RED}{self.state.p99_latency_ms} ms (SLO: <250 ms){RESET}")
        print(f"Error Rate    : {RED}{self.state.error_rate}% (SLO: <0.5%){RESET}")
        print(f"DB Conn Pool  : {RED}{self.state.db_pool_utilization}% (Exhaustion Risk){RESET}\n")

    def print_dashboard(self):
        print(f"{BOLD}=== REAL-TIME TELEMETRY & SYSTEM HEALTH ==={RESET}")
        status_color = RED if self.state.error_rate > 1.0 else GREEN
        cb_color = YELLOW if self.state.circuit_breaker_active else WHITE
        db_color = RED if self.state.db_pool_utilization > 85.0 else GREEN

        print(f"API Gateway Latency (P99) : {status_color}{self.state.p99_latency_ms:.1f} ms{RESET}")
        print(f"Global HTTP 5xx Rate      : {status_color}{self.state.error_rate:.2f}%{RESET}")
        print(f"DB Connection Saturation  : {db_color}{self.state.db_pool_utilization:.1f}%{RESET}")
        print(f"Circuit Breaker Status    : {cb_color}{'TRIPPED (SHEDDING 40%)' if self.state.circuit_breaker_active else 'CLOSED (NORMAL)'}{RESET}")
        print(f"Database Topology         : {GREEN if self.state.db_failover_executed else YELLOW}{'FAILOVER -> REPLICA-AZ2 (PRIMARY)' if self.state.db_failover_executed else 'ACTIVE-AZ1 (SATURATED)'}{RESET}")
        print(f"Deployment Canary State   : {GREEN if self.state.canary_rolled_back else RED}{'ROLLED BACK TO v2.4.0' if self.state.canary_rolled_back else 'ACTIVE v2.4.1 (FAULTY POOLING)'}{RESET}")
        print("-" * 55)

    def action_circuit_breaker(self):
        print(f"\n{YELLOW}[EXECUTING] Engaging ingress circuit breaker & load-shedding...{RESET}")
        time.sleep(0.8)
        self.state.circuit_breaker_active = True
        self.state.p99_latency_ms *= 0.65
        self.state.error_rate = max(1.5, self.state.error_rate * 0.45)
        self.state.db_pool_utilization = max(40.0, self.state.db_pool_utilization - 25.0)
        self.log_event("Incident Commander enabled aggressive circuit breaker and traffic shedding", "ACTION")
        print(f"{GREEN}✓ Circuit breaker tripped. Degraded non-essential calls. Latency decreasing.{RESET}")

    def action_rollback_canary(self):
        print(f"\n{YELLOW}[EXECUTING] Initiating automated gitops rollback of v2.4.1 -> v2.4.0...{RESET}")
        time.sleep(1.0)
        self.state.canary_rolled_back = True
        self.state.error_rate = min(self.state.error_rate, 0.8)
        self.state.p99_latency_ms = min(self.state.p99_latency_ms, 380)
        self.state.db_pool_utilization = max(35.0, self.state.db_pool_utilization - 35.0)
        self.log_event("Deployment reverted to v2.4.0 (purged unclosed DB connection bug)", "ACTION")
        print(f"{GREEN}✓ Canary rollback deployed. Connection pool leaks ceased.{RESET}")

    def action_db_failover(self):
        print(f"\n{YELLOW}[EXECUTING] Orchestrating RDS/PostgreSQL cluster failover to replica in AZ-b...{RESET}")
        time.sleep(1.0)
        self.state.db_failover_executed = True
        self.state.db_pool_utilization = 22.5
        self.state.p99_latency_ms = 185
        self.state.error_rate = 0.05
        self.log_event("Database failover executed cleanly. Clean thread pool restored on new primary", "ACTION")
        print(f"{GREEN}✓ Failover completed. DB connection pool utilization reset to nominal.{RESET}")

    def evaluate_resolution(self) -> bool:
        return (
            self.state.error_rate < 0.5
            and self.state.p99_latency_ms < 250
            and self.state.db_pool_utilization < 70.0
        )

    def interactive_triage_loop(self):
        step = 1
        while not self.evaluate_resolution() and step <= 6:
            print(f"\n{BOLD}[TRIAGE STEP {step}] Available Incident Mitigation Strategies:{RESET}")
            print("1. Trip Circuit Breaker (Isolate non-critical microservice traffic)")
            print("2. Rollback Canary Deployment (Roll back v2.4.1 pool leak)")
            print("3. Execute DB Aurora/PostgreSQL Failover to fresh warm replica")
            print("4. Broadcast Statuspage Announcement (Stakeholder Communication)")
            print("5. Run Diagnostics / Refresh Telemetry Dashboard")
            print("6. Conclude Triage & Force Post-Mortem Generation")

            choice = ""
            try:
                choice = input(f"{BOLD}{CYAN}Select SRE Mitigation Action [1-6]: {RESET}").strip()
            except (EOFError, KeyboardInterrupt):
                choice = "2"
                print("\nAutomated on-call fallback selected: 2")

            if choice == "1":
                self.action_circuit_breaker()
            elif choice == "2":
                self.action_rollback_canary()
            elif choice == "3":
                self.action_db_failover()
            elif choice == "4":
                print(f"\n{BLUE}📢 Statuspage updated: 'Investigating degraded performance in Payment Checkout.'{RESET}")
                self.log_event("Published public incident notice on statuspage", "COMM")
            elif choice == "5":
                print(f"\n{WHITE}Gathering fresh telemetry data from Prometheus...{RESET}")
            elif choice == "6":
                print(f"\n{YELLOW}Terminating live mitigation phase.{RESET}")
                break
            else:
                print(f"{RED}Invalid input. Please choose 1-6.{RESET}")

            print()
            self.print_dashboard()
            step += 1

        if self.evaluate_resolution():
            print(f"\n{BG_GREEN}{WHITE}{BOLD} ✔ INCIDENT MITIGATED & RESOLVED! ALL SLOs WITHIN NOMINAL TARGETS {RESET}\n")
            self.log_event("Incident marked RESOLVED by Incident Commander", "RESOLVE")
        else:
            print(f"\n{YELLOW}Mitigation phase ended. Proceeding to post-incident review.{RESET}\n")

    def generate_blameless_post_mortem(self):
        duration_min = round((datetime.now() - self.start_time).total_seconds() / 60, 2)
        print(f"\n{BOLD}{BG_GREEN}{WHITE} [AUTOMATED BLAMELESS POST-MORTEM ARTIFACT] {RESET}")
        print("=" * 70)
        print(f"{BOLD}Title          :{RESET} Incident {self.incident_id} - Payment API Latency & Connection Pool Depletion")
        print(f"{BOLD}Date & Time    :{RESET} {self.start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"{BOLD}Severity       :{RESET} SEV-1 (Customer-Facing Checkout Impact)")
        print(f"{BOLD}Incident Comm. :{RESET} {self.ic_name}")
        print(f"{BOLD}Time to Mitigate:{RESET} ~{duration_min} minutes (Simulated)")
        print(f"{BOLD}User Impact    :{RESET} ~14.8% of checkout transactions encountered HTTP 504 timeouts.")
        print("-" * 70)

        print(f"\n{BOLD}1. INCIDENT TIMELINE (UTC):{RESET}")
        for item in self.timeline:
            color = RED if item['severity'] == "ALERT" else (GREEN if item['severity'] == "RESOLVE" else CYAN)
            print(f"  • [{color}{item['time']}{RESET}] [{item['severity']:<7}] {item['desc']}")

        print(f"\n{BOLD}2. ROOT CAUSE ANALYSIS (5-WHYS / SYSTEMIC):{RESET}")
        print("  • Release v2.4.1 contained a bug in the database connection retry loop.")
        print("  • Unhandled context cancellation leaked connections without returning to pool.")
        print("  • Max pool cap (200 connections) reached within 12 minutes of traffic ramp-up.")
        print("  • Backend threads blocked on pool acquisition, causing cascade timeout to Envoy gateway.")

        print(f"\n{BOLD}3. BLAMELESS CULTURE REFLECTION:{RESET}")
        print(f"  {WHITE}Focus: How do our testing gates, observability, and circuit breaking fail to catch this?")
        print("  People do not cause failures; complex distributed systems fail. We harden the platform.")

        print(f"\n{BOLD}4. CORRECTIVE & PREVENTATIVE ACTION ITEMS (SMART):{RESET}")
        print("  [P0] Add integration tests verifying connection return on client cancellation timeout (Owner: Payment Team).")
        print("  [P1] Configure automatic DB connection pool leak alerts at 80% saturation in Datadog (Owner: SRE).")
        print("  [P1] Implement automated Canary Analysis (Kayenta/Argo Rollouts) to halt rollout if P99 > 300ms (Owner: SRE).")
        print("  [P2] Audit runbooks for Aurora PostgreSQL failover under active load (Owner: Database Guild).")
        print("=" * 70 + "\n")


def main():
    sim = IncidentSimulator()
    sim.print_banner()
    sim.print_alert()
    sim.print_dashboard()
    sim.interactive_triage_loop()
    sim.generate_blameless_post_mortem()


if __name__ == "__main__":
    main()
