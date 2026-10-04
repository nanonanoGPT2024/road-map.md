#!/usr/bin/env python3
"""
Lab Exercise Modul 02: SRE Deep Dive - Multi-Window Multi-Burn-Rate Alerting (MWMRA)
dan Resilience Pattern (Circuit Breaker & Adaptive Load Shedding) Simulation.

Simulasi mandiri evaluasi SLI/SLO, konsumsi Error Budget, deteksi lonjakan Burn Rate,
dan kebijakan rilis Canary (Deployment Gate).
"""

import sys
import time
import random
from dataclasses import dataclass, field
from typing import List, Dict

# ANSI Escape Sequences untuk formatting terminal output
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
BG_YELLOW = "\033[43m"


@dataclass
class SLOConfig:
    target_slo: float = 0.995          # 99.5% availability target
    window_total_budget_events: int = 10_000
    allowed_bad_events: int = field(init=False)

    def __post_init__(self):
        self.allowed_bad_events = int(self.window_total_budget_events * (1.0 - self.target_slo))


class CircuitBreaker:
    STATE_CLOSED = "CLOSED"
    STATE_OPEN = "OPEN"
    STATE_HALF_OPEN = "HALF_OPEN"

    def __init__(self, failure_threshold: float = 0.35, recovery_time_ticks: int = 3):
        self.failure_threshold = failure_threshold
        self.recovery_time_ticks = recovery_time_ticks
        self.state = self.STATE_CLOSED
        self.tripped_tick = 0

    def evaluate(self, current_tick: int, recent_error_rate: float) -> str:
        if self.state == self.STATE_CLOSED:
            if recent_error_rate >= self.failure_threshold:
                self.state = self.STATE_OPEN
                self.tripped_tick = current_tick
        elif self.state == self.STATE_OPEN:
            if (current_tick - self.tripped_tick) >= self.recovery_time_ticks:
                self.state = self.STATE_HALF_OPEN
        elif self.state == self.STATE_HALF_OPEN:
            if recent_error_rate < (self.failure_threshold / 2):
                self.state = self.STATE_CLOSED
            else:
                self.state = self.STATE_OPEN
                self.tripped_tick = current_tick
        return self.state


class MultiWindowBurnRateMonitor:
    """
    Mengimplementasikan Google SRE MWMRA (Multi-Window Multi-Burn-Rate Alerting).
    - Fast Burn (14.4x burn rate): Mengonsumsi 2% budget dalam 1 jam (window pendek)
    - Medium Burn (6.0x burn rate): Mengonsumsi 5% budget dalam 6 jam
    - Slow Burn (1.0x burn rate): Habis tepat dalam 30 hari
    """
    def __init__(self, slo: SLOConfig):
        self.slo = slo
        self.short_window: List[bool] = []
        self.long_window: List[bool] = []
        self.short_len = 5
        self.long_len = 15

    def record_events(self, good_count: int, bad_count: int):
        events = [True] * good_count + [False] * bad_count
        random.shuffle(events)
        for ev in events:
            self.short_window.append(ev)
            self.long_window.append(ev)
            if len(self.short_window) > self.short_len * 50:
                self.short_window.pop(0)
            if len(self.long_window) > self.long_len * 50:
                self.long_window.pop(0)

    def calculate_burn_rate(self) -> float:
        if not self.short_window:
            return 0.0
        bad_events = self.short_window.count(False)
        total = len(self.short_window)
        current_error_rate = bad_events / total
        expected_error_rate = 1.0 - self.slo.target_slo
        if expected_error_rate == 0:
            return 0.0
        return current_error_rate / expected_error_rate

    def get_alert_status(self, burn_rate: float) -> str:
        if burn_rate >= 14.4:
            return f"{BG_RED}{WHITE}{BOLD} [CRITICAL ALERT: 14.4x FAST BURN] {RESET}"
        elif burn_rate >= 6.0:
            return f"{BG_YELLOW}{WHITE}{BOLD} [PAGE ALERT: 6.0x MED BURN] {RESET}"
        elif burn_rate >= 2.0:
            return f"{YELLOW}{BOLD} [WARNING: 2.0x SLOW BURN] {RESET}"
        return f"{GREEN}[HEALTHY]{RESET}"


def render_progress_bar(consumed_pct: float, width: int = 24) -> str:
    filled = int(consumed_pct * width)
    filled = max(0, min(width, filled))
    empty = width - filled
    if consumed_pct < 0.6:
        color = GREEN
    elif consumed_pct < 0.9:
        color = YELLOW
    else:
        color = RED
    bar = f"{color}{'█' * filled}{DIM}{'░' * empty}{RESET}"
    return f"[{bar}] {consumed_pct*100:5.1f}%"


def run_simulation():
    print(f"\n{BOLD}{CYAN}{'='*80}{RESET}")
    print(f"{BOLD}{CYAN} SRE LAB 02: MULTI-WINDOW MULTI-BURN-RATE & RESILIENCE SIMULATION {RESET}")
    print(f"{BOLD}{CYAN}{'='*80}{RESET}\n")

    slo = SLOConfig(target_slo=0.995, window_total_budget_events=10_000)
    monitor = MultiWindowBurnRateMonitor(slo)
    breaker = CircuitBreaker(failure_threshold=0.30, recovery_time_ticks=3)

    total_good_events = 0
    total_bad_events = 0
    total_shed_events = 0

    print(f"{WHITE}SLO Target     :{RESET} {BOLD}{slo.target_slo * 100:.2f}%{RESET}")
    print(f"{WHITE}Total Budget   :{RESET} {BOLD}{slo.allowed_bad_events}{RESET} bad events allowable (out of {slo.window_total_budget_events:,})")
    print(f"{WHITE}Architecture   :{RESET} Edge API Gateway -> Adaptive Circuit Breaker -> Downstream RPC")
    print(f"{WHITE}{'-'*80}{RESET}\n")

    print(f"{BOLD}{'Tick':<6} {'Phase':<20} {'State':<12} {'Req/s':<8} {'Err%':<8} {'BurnRate':<10} {'Budget Consumed':<22} {'Alert Status'}{RESET}")
    print(f"{DIM}{'-'*98}{RESET}")

    phases = [
        ("Normal Traffic", 6, 200, 0.002),
        ("Injected Cascading Fail", 5, 450, 0.420),
        ("Shedding & Backoff", 4, 300, 0.150),
        ("Recovery Steady-state", 5, 220, 0.003),
    ]

    tick = 1
    for phase_name, iterations, req_volume, base_error_ratio in phases:
        for _ in range(iterations):
            # Evaluate Circuit Breaker status
            current_recent_err = base_error_ratio if breaker.state != BreakerStateOpen else 0.05
            cb_state = breaker.evaluate(tick, base_error_ratio)

            # Load shedding if Circuit Breaker is OPEN or HALF_OPEN
            if cb_state == CircuitBreaker.STATE_OPEN:
                effective_reqs = int(req_volume * 0.1) # shed 90%
                shed_count = req_volume - effective_reqs
                actual_bad = int(effective_reqs * 0.10)
                actual_good = effective_reqs - actual_bad
            elif cb_state == CircuitBreaker.STATE_HALF_OPEN:
                effective_reqs = int(req_volume * 0.5) # shed 50%
                shed_count = req_volume - effective_reqs
                actual_bad = int(effective_reqs * 0.05)
                actual_good = effective_reqs - actual_bad
            else:
                shed_count = 0
                actual_bad = int(req_volume * base_error_ratio)
                actual_good = req_volume - actual_bad

            total_good_events += actual_good
            total_bad_events += actual_bad
            total_shed_events += shed_count

            monitor.record_events(actual_good, actual_bad)
            burn_rate = monitor.calculate_burn_rate()
            alert_str = monitor.get_alert_status(burn_rate)

            # State styling
            if cb_state == CircuitBreaker.STATE_CLOSED:
                state_fmt = f"{GREEN}{cb_state:<12}{RESET}"
            elif cb_state == CircuitBreaker.STATE_HALF_OPEN:
                state_fmt = f"{YELLOW}{cb_state:<12}{RESET}"
            else:
                state_fmt = f"{RED}{cb_state:<12}{RESET}"

            consumed_ratio = min(1.0, total_bad_events / slo.allowed_bad_events)
            budget_bar = render_progress_bar(consumed_ratio, width=12)

            measured_err_pct = (actual_bad / max(1, (actual_good + actual_bad))) * 100

            print(f"{tick:<6} {phase_name:<20} {state_fmt} {req_volume:<8} {measured_err_pct:5.1f}%  {burn_rate:6.2f}x   {budget_bar:<20} {alert_str}")
            time.sleep(0.08)
            tick += 1

    # Final Executive Summary & Canary Deployment Decision
    total_processed = total_good_events + total_bad_events
    final_sli = (total_good_events / total_processed) * 100 if total_processed else 0
    budget_exhausted = total_bad_events >= slo.allowed_bad_events

    print(f"\n{BOLD}{CYAN}{'='*80}{RESET}")
    print(f"{BOLD}{WHITE} SRE POST-MORTEM & ERROR BUDGET GOVERNANCE REPORT {RESET}")
    print(f"{BOLD}{CYAN}{'='*80}{RESET}")
    print(f"Total Requests Processed : {BOLD}{total_processed:,}{RESET}")
    print(f"Total Good Events        : {GREEN}{BOLD}{total_good_events:,}{RESET}")
    print(f"Total Bad Events         : {RED}{BOLD}{total_bad_events:,}{RESET}")
    print(f"Total Shedded (Protected): {YELLOW}{BOLD}{total_shed_events:,}{RESET}")
    print(f"Observed SLI             : {BOLD}{final_sli:.3f}%{RESET} (Target: {slo.target_slo*100:.2f}%)")
    print(f"Budget Remaining         : {max(0, slo.allowed_bad_events - total_bad_events)} / {slo.allowed_bad_events} events")

    print(f"\n{BOLD}{MAGENTA}CANARY RELEASE GATE DECISION:{RESET}")
    if budget_exhausted:
        print(f"{BG_RED}{WHITE}{BOLD} [BLOCKED] {RESET} {RED}Error Budget terlampaui! Policy: Freeze feature deployments, alokasikan sprint ke engineering reliability.{RESET}\n")
    elif total_bad_events > (slo.allowed_bad_events * 0.75):
        print(f"{BG_YELLOW}{WHITE}{BOLD} [RESTRICTED] {RESET} {YELLOW}Budget < 25% tersisa. Hanya patch kritis/P0 yang diizinkan untuk rilis.{RESET}\n")
    else:
        print(f"{BG_GREEN}{WHITE}{BOLD} [APPROVED] {RESET} {GREEN}Error budget aman ({100 - (total_bad_events/slo.allowed_bad_events)*100:.1f}% tersisa). Pipeline deployment canary diizinkan berjalan.{RESET}\n")


if __name__ == "__main__":
    BreakerStateOpen = CircuitBreaker.STATE_OPEN
    run_simulation()
