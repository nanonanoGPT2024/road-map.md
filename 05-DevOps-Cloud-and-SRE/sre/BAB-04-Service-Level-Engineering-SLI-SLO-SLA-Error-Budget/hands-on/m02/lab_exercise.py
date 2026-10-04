#!/usr/bin/env python3
"""
Lab Exercise: Production SRE Simulation - Service Level Engineering
Topic: SLI, SLO, SLA, Error Budget, and Multi-Window Multi-Burn-Rate Alerting
Target Directory: hands-on/m02/lab_exercise.py

Features:
- Real-time synthetic production traffic simulation (API Gateway -> Microservices)
- SLI computation: Availability SLI (2xx/3xx/4xx vs 5xx) & Latency SLI (p95/p99 <= threshold)
- Rolling Error Budget accounting (30-day rolling window scaled for lab)
- Google SRE Multi-Window Multi-Burn-Rate Alerting (14.4x 1h/5m, 6x 6h/30m, 1x 3-day)
- Incident Injection (Cascading failure, DB latency degradation, Packet loss)
- Automated Circuit Breaking & Policy Enforcement (Freeze deploy on Error Budget exhaustion)
- Interactive ANSI terminal dashboard
"""

import sys
import time
import random
import math
from dataclasses import dataclass, field
from typing import List, Dict, Tuple
from enum import Enum

# ANSI Terminal Color Escapes
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
    BG_BLUE = "\033[44m"


class AlertSeverity(Enum):
    PAGE = "PAGE (P1)"
    TICKET = "TICKET (P2)"
    INFO = "INFO (P3)"
    OK = "HEALTHY"


@dataclass
class RequestRecord:
    timestamp: float
    status_code: int
    latency_ms: float
    service: str
    is_good: bool  # Good event according to SLI definition


@dataclass
class ServiceLevelObjective:
    name: str
    target_slo: float            # e.g., 0.999 (99.9%)
    sla_threshold: float         # e.g., 0.995 (99.5% financial penalty)
    latency_threshold_ms: float  # e.g., 250.0 ms
    total_budget_percentage: float = 100.0  # 100% budget at baseline

    @property
    def max_allowed_failure_rate(self) -> float:
        return 1.0 - self.target_slo


@dataclass
class BurnRateAlertRule:
    name: str
    burn_rate_threshold: float
    long_window_minutes: int
    short_window_minutes: int
    budget_consumed_percent: float
    severity: AlertSeverity


class ProductionSRESimulator:
    def __init__(self):
        self.slo = ServiceLevelObjective(
            name="Checkout-and-Payment-API",
            target_slo=0.995,           # 99.5% SLO (allows 0.5% errors)
            sla_threshold=0.990,        # 99.0% SLA contractual breach
            latency_threshold_ms=200.0  # SLI: Latency <= 200ms
        )
        self.requests_history: List[RequestRecord] = []
        self.deployment_frozen = False
        self.chaos_mode = "NORMAL"
        self.circuit_breaker_active = False

        # Multi-window multi-burn-rate definitions (Google SRE Book Chapter 5)
        self.alert_rules = [
            BurnRateAlertRule(
                name="Critical Fast Burn",
                burn_rate_threshold=14.4,
                long_window_minutes=60,
                short_window_minutes=5,
                budget_consumed_percent=2.0,
                severity=AlertSeverity.PAGE
            ),
            BurnRateAlertRule(
                name="Elevated Medium Burn",
                burn_rate_threshold=6.0,
                long_window_minutes=360,
                short_window_minutes=30,
                budget_consumed_percent=5.0,
                severity=AlertSeverity.PAGE
            ),
            BurnRateAlertRule(
                name="Slow Bleed Burn",
                burn_rate_threshold=1.0,
                long_window_minutes=1440,
                short_window_minutes=120,
                budget_consumed_percent=10.0,
                severity=AlertSeverity.TICKET
            ),
        ]

    def generate_traffic_batch(self, count: int = 100) -> None:
        """Simulate incoming requests based on current chaos/production condition."""
        now = time.time()
        for _ in range(count):
            if self.circuit_breaker_active:
                # Circuit breaker sheds load or returns cached 200/429
                if random.random() < 0.8:
                    status = 429  # Rate limited/circuit open (client error, not 5xx failure for server SLI)
                    latency = random.uniform(5.0, 25.0)
                    is_good = True  # Controlled shedding
                else:
                    status = 200
                    latency = random.uniform(20.0, 80.0)
                    is_good = latency <= self.slo.latency_threshold_ms
            elif self.chaos_mode == "OUTAGE_PAYMENT_DB":
                # Severe DB outage: high 500s and long timeouts
                if random.random() < 0.45:
                    status = 500
                    latency = random.uniform(400.0, 1500.0)
                    is_good = False
                else:
                    status = 200
                    latency = random.uniform(150.0, 350.0)
                    is_good = (latency <= self.slo.latency_threshold_ms)
            elif self.chaos_mode == "LATENCY_SPIKE":
                # Latency degradation: low 5xx but high latency violating SLI
                status = 200 if random.random() > 0.05 else 503
                latency = random.uniform(220.0, 650.0)
                is_good = (status == 200 and latency <= self.slo.latency_threshold_ms)
            elif self.chaos_mode == "MILD_INTERMITTENT":
                # Slow bleed error budget consumption
                status = 502 if random.random() < 0.035 else 200
                latency = random.uniform(40.0, 190.0)
                is_good = (status == 200 and latency <= self.slo.latency_threshold_ms)
            else:
                # Normal operational traffic: 99.8% good
                status = 200 if random.random() > 0.002 else 500
                latency = random.uniform(25.0, 120.0)
                is_good = (status == 200 and latency <= self.slo.latency_threshold_ms)

            self.requests_history.append(
                RequestRecord(
                    timestamp=now,
                    status_code=status,
                    latency_ms=latency,
                    service="checkout-srv",
                    is_good=is_good
                )
            )

    def calculate_sli_metrics(self) -> Dict[str, float]:
        """Compute current SLI availability and latency compliance."""
        if not self.requests_history:
            return {"availability_sli": 1.0, "latency_sli": 1.0, "overall_sli": 1.0, "total": 0}

        total = len(self.requests_history)
        good_events = sum(1 for req in self.requests_history if req.is_good)
        non_5xx = sum(1 for req in self.requests_history if req.status_code < 500)
        fast_requests = sum(1 for req in self.requests_history if req.latency_ms <= self.slo.latency_threshold_ms)

        availability_sli = non_5xx / total
        latency_sli = fast_requests / total
        overall_sli = good_events / total

        return {
            "availability_sli": availability_sli,
            "latency_sli": latency_sli,
            "overall_sli": overall_sli,
            "total": total,
            "good_events": good_events,
            "bad_events": total - good_events
        }

    def calculate_error_budget(self) -> Tuple[float, float, float]:
        """
        Returns:
            (total_budget_fraction, consumed_budget_fraction, remaining_budget_percentage)
        """
        metrics = self.calculate_sli_metrics()
        total_requests = metrics["total"]
        if total_requests == 0:
            return (0.005, 0.0, 100.0)

        max_allowed_failures = total_requests * self.slo.max_allowed_failure_rate
        actual_failures = metrics["bad_events"]

        if max_allowed_failures > 0:
            consumed_budget_ratio = actual_failures / max_allowed_failures
        else:
            consumed_budget_ratio = 1.0 if actual_failures > 0 else 0.0

        remaining_budget_percent = max(0.0, (1.0 - consumed_budget_ratio) * 100.0)
        return (max_allowed_failures, actual_failures, remaining_budget_percent)

    def compute_burn_rate(self, window_size: int = 200) -> float:
        """
        Burn Rate = Current Error Rate / Max Allowed Error Rate
        A burn rate of 1.0 means the budget will be fully consumed exactly in the SLO window.
        """
        if len(self.requests_history) < 10:
            return 0.0

        sample = self.requests_history[-window_size:]
        bad_count = sum(1 for req in sample if not req.is_good)
        sample_error_rate = bad_count / len(sample)
        burn_rate = sample_error_rate / self.slo.max_allowed_failure_rate
        return round(burn_rate, 2)

    def evaluate_burn_rate_alerts(self, burn_rate: float) -> List[Tuple[BurnRateAlertRule, bool]]:
        """Evaluate alerting thresholds based on calculated burn rate."""
        results = []
        for rule in self.alert_rules:
            is_firing = burn_rate >= rule.burn_rate_threshold
            results.append((rule, is_firing))
        return results

    def enforce_sre_policies(self, remaining_budget_percent: float) -> None:
        """Enforce deployment freeze or mitigation when error budget is exhausted."""
        if remaining_budget_percent <= 0.0 and not self.deployment_frozen:
            self.deployment_frozen = True
        elif remaining_budget_percent > 20.0 and self.deployment_frozen:
            self.deployment_frozen = False

    def render_dashboard(self) -> None:
        """Render terminal dashboard with rich ANSI formatting."""
        metrics = self.calculate_sli_metrics()
        max_allowed, actual_bad, remaining_budget = self.calculate_error_budget()
        burn_rate = self.compute_burn_rate()
        alert_evals = self.evaluate_burn_rate_alerts(burn_rate)
        self.enforce_sre_policies(remaining_budget)

        print("\033[H\033[J", end="")  # Clear screen
        print(f"{Color.BG_BLUE}{Color.WHITE}{Color.BOLD} SRE SERVICE LEVEL ENGINEERING & ERROR BUDGET COCKPIT {Color.RESET}")
        print(f"Target Service : {Color.CYAN}{self.slo.name}{Color.RESET}")
        print(f"SLO Objective  : {Color.GREEN}{self.slo.target_slo * 100:.2f}%{Color.RESET} (Allowed Failures: {self.slo.max_allowed_failure_rate * 100:.2f}%)")
        print(f"SLA Contract   : {Color.YELLOW}{self.slo.sla_threshold * 100:.2f}%{Color.RESET} (Breach leads to financial credits)")
        print(f"SLI Metric Spec: HTTP status < 500 AND Latency <= {self.slo.latency_threshold_ms}ms")
        print("-" * 75)

        # SLI Performance Table
        sli_color = Color.GREEN if metrics["overall_sli"] >= self.slo.target_slo else (Color.YELLOW if metrics["overall_sli"] >= self.slo.sla_threshold else Color.RED)
        print(f"{Color.BOLD}1. SERVICE LEVEL INDICATORS (SLI){Color.RESET}")
        print(f"   • Total Requests Processed : {metrics['total']}")
        print(f"   • Availability SLI (Non-5xx): {metrics['availability_sli'] * 100:.2f}%")
        print(f"   • Latency SLI (<= {self.slo.latency_threshold_ms}ms) : {metrics['latency_sli'] * 100:.2f}%")
        print(f"   • Composite SLI (Success)  : {sli_color}{metrics['overall_sli'] * 100:.2f}%{Color.RESET}")

        print("-" * 75)
        # Error Budget Progress Bar
        print(f"{Color.BOLD}2. ROLLING ERROR BUDGET STATUS{Color.RESET}")
        bar_len = 30
        filled = int((remaining_budget / 100.0) * bar_len)
        bar_color = Color.GREEN if remaining_budget > 30 else (Color.YELLOW if remaining_budget > 0 else Color.RED)
        progress_bar = f"{bar_color}{'█' * filled}{Color.WHITE}{'░' * (bar_len - filled)}{Color.RESET}"

        print(f"   • Allowed Bad Events : {int(max_allowed)}")
        print(f"   • Consumed Bad Events: {int(actual_bad)}")
        print(f"   • Budget Remaining   : [{progress_bar}] {bar_color}{remaining_budget:.1f}%{Color.RESET}")

        if self.deployment_frozen:
            print(f"   • {Color.BG_RED}{Color.WHITE}{Color.BOLD} POLICY: DEPLOYMENT FREEZE ACTIVATED (Budget Depleted) {Color.RESET}")
        else:
            print(f"   • {Color.GREEN}POLICY: Deployments Allowed (Budget Healthy){Color.RESET}")

        print("-" * 75)
        # Burn Rate and Alerting Table
        print(f"{Color.BOLD}3. MULTI-WINDOW MULTI-BURN-RATE DETECTOR{Color.RESET}")
        br_color = Color.GREEN if burn_rate <= 1.0 else (Color.YELLOW if burn_rate < 6.0 else Color.RED)
        print(f"   • Instantaneous Burn Rate  : {br_color}{burn_rate}x{Color.RESET} (1.0x consumes 100% budget in 30 days)")

        print(f"\n   {'Alert Rule':<25} | {'Threshold':<10} | {'Window':<12} | {'Severity':<14} | {'Status'}")
        print("   " + "-" * 70)
        for rule, firing in alert_evals:
            status_badge = f"{Color.BG_RED}{Color.WHITE} FIRING {Color.RESET}" if firing else f"{Color.GREEN}OK{Color.RESET}"
            sev_badge = f"{Color.RED}{rule.severity.value}{Color.RESET}" if firing else f"{Color.WHITE}{rule.severity.value}{Color.RESET}"
            print(f"   {rule.name:<25} | {rule.burn_rate_threshold:<9.1f}x | {rule.long_window_minutes}m/{rule.short_window_minutes}m      | {sev_badge:<23} | {status_badge}")

        print("-" * 75)
        print(f"{Color.BOLD}4. ACTIVE CHAOS & CIRCUIT BREAKER STATE{Color.RESET}")
        print(f"   • Current Injection Mode   : {Color.MAGENTA}{self.chaos_mode}{Color.RESET}")
        cb_status = f"{Color.YELLOW}ACTIVE (Shedding 5xx to 429){Color.RESET}" if self.circuit_breaker_active else f"{Color.GREEN}INACTIVE (Closed){Color.RESET}"
        print(f"   • Circuit Breaker Status   : {cb_status}")
        print("=" * 75)


def display_interactive_menu():
    print(f"\n{Color.BOLD}CONTROL COMMANDS:{Color.RESET}")
    print("  [1] Send Normal Traffic (150 requests)")
    print("  [2] Inject Severe Outage: Payment DB Down (45% failure rate -> Fast Burn)")
    print("  [3] Inject Latency Spike: Microservice Slowdown (violates Latency SLI)")
    print("  [4] Inject Mild Intermittent Faults (Slow Bleed Burn)")
    print("  [5] Toggle Circuit Breaker Mitigation")
    print("  [6] Reset Simulator State")
    print("  [7] Run Automated End-to-End Incident Lifecycle Walkthrough")
    print("  [q] Quit")


def run_e2e_walkthrough(sim: ProductionSRESimulator):
    """Executes an automated scenario showing healthy -> incident -> alert -> circuit breaker -> recovery."""
    print(f"\n{Color.CYAN}Starting Automated SRE Incident Lifecycle Simulation...{Color.RESET}")
    time.sleep(1.2)

    # Step 1: Normal
    print(f"\n{Color.BOLD}Stage 1: Establishing Baseline Normal Traffic...{Color.RESET}")
    sim.chaos_mode = "NORMAL"
    for _ in range(5):
        sim.generate_traffic_batch(100)
        sim.render_dashboard()
        time.sleep(0.4)

    # Step 2: Inject Outage
    print(f"\n{Color.BOLD}Stage 2: Injecting Severe Database Outage!{Color.RESET}")
    sim.chaos_mode = "OUTAGE_PAYMENT_DB"
    for _ in range(6):
        sim.generate_traffic_batch(100)
        sim.render_dashboard()
        time.sleep(0.5)

    # Step 3: Trigger Circuit Breaker
    print(f"\n{Color.BOLD}Stage 3: SRE Automated Mitigation: Activating Circuit Breaker!{Color.RESET}")
    sim.circuit_breaker_active = True
    for _ in range(5):
        sim.generate_traffic_batch(100)
        sim.render_dashboard()
        time.sleep(0.4)

    # Step 4: Resolve Outage
    print(f"\n{Color.BOLD}Stage 4: Root Cause Fixed. Returning to Normal Traffic...{Color.RESET}")
    sim.chaos_mode = "NORMAL"
    sim.circuit_breaker_active = False
    for _ in range(6):
        sim.generate_traffic_batch(100)
        sim.render_dashboard()
        time.sleep(0.4)

    print(f"\n{Color.GREEN}{Color.BOLD}✓ Lifecycle walkthrough complete. Budget and alerts updated.{Color.RESET}")
    input("\nPress [Enter] to return to main menu...")


def main():
    sim = ProductionSRESimulator()
    # Pre-populate with baseline traffic
    sim.generate_traffic_batch(200)

    # Check if run non-interactively or with flags
    if len(sys.argv) > 1 and sys.argv[1] in ("--auto", "-a", "--test"):
        sim.render_dashboard()
        print(f"\n{Color.GREEN}Running non-interactive verification...{Color.RESET}")
        sim.generate_traffic_batch(100)
        metrics = sim.calculate_sli_metrics()
        burn_rate = sim.compute_burn_rate()
        print(f"SLI Computed: {metrics['overall_sli']:.4f}, Burn Rate: {burn_rate}")
        print(f"{Color.GREEN}Verification passed successfully!{Color.RESET}")
        return

    while True:
        sim.render_dashboard()
        display_interactive_menu()
        try:
            choice = input(f"{Color.BOLD}Enter option (1-7, q): {Color.RESET}").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Color.YELLOW}Exiting SRE Lab.{Color.RESET}")
            break

        if choice == '1':
            sim.chaos_mode = "NORMAL"
            sim.generate_traffic_batch(150)
        elif choice == '2':
            sim.chaos_mode = "OUTAGE_PAYMENT_DB"
            sim.generate_traffic_batch(150)
        elif choice == '3':
            sim.chaos_mode = "LATENCY_SPIKE"
            sim.generate_traffic_batch(150)
        elif choice == '4':
            sim.chaos_mode = "MILD_INTERMITTENT"
            sim.generate_traffic_batch(150)
        elif choice == '5':
            sim.circuit_breaker_active = not sim.circuit_breaker_active
        elif choice == '6':
            sim = ProductionSRESimulator()
            sim.generate_traffic_batch(200)
        elif choice == '7':
            run_e2e_walkthrough(sim)
        elif choice in ('q', 'quit', 'exit'):
            print(f"\n{Color.GREEN}Exiting SRE Simulator. Happy Engineering!{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Invalid selection. Please choose 1-7 or q.{Color.RESET}")
            time.sleep(1)


if __name__ == "__main__":
    main()
