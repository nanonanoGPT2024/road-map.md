#!/usr/bin/env python3
"""
Lab Exercise: SRE & Disaster Recovery Engine Simulation
Bab 10: Security Reliability Engineering & Disaster Recovery
Interactive Technical Simulation: SLI/SLO, Error Budget Burn Rate, RPO/RTO & DR Failover
"""

import sys
import time
import random
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict

# ANSI Terminal Color Palette
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    BG_DARK = "\033[40m"

class CircuitState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

@dataclass
class SLOMetric:
    name: str
    target_percentage: float
    total_requests: int = 0
    failed_requests: int = 0

    @property
    def current_sli(self) -> float:
        if self.total_requests == 0:
            return 100.0
        return ((self.total_requests - self.failed_requests) / self.total_requests) * 100.0

    @property
    def error_budget_allowed(self) -> float:
        return (100.0 - self.target_percentage) / 100.0 * self.total_requests

    @property
    def error_budget_consumed_pct(self) -> float:
        allowed = self.error_budget_allowed
        if allowed <= 0:
            return 100.0 if self.failed_requests > 0 else 0.0
        return min((self.failed_requests / allowed) * 100.0, 100.0)

    @property
    def burn_rate_1h(self) -> float:
        # Standard 30-day window burn rate relative to 1 hour consumption
        allowed_fraction = (100.0 - self.target_percentage) / 100.0
        if allowed_fraction <= 0 or self.total_requests == 0:
            return 0.0
        actual_error_rate = self.failed_requests / self.total_requests
        return actual_error_rate / allowed_fraction

class DisasterRecoverySimulator:
    def __init__(self):
        self.primary_region = "ap-southeast-1 (Jakarta)"
        self.standby_region = "ap-southeast-3 (Singapore)"
        self.rpo_target_sec = 5.0
        self.rto_target_sec = 30.0
        self.replication_lag_sec = 1.2
        self.primary_healthy = True

    def simulate_failover(self):
        print(f"\n{Color.CYAN}{'='*60}")
        print(f" SIMULASI DISASTER RECOVERY & REGIONAL FAILOVER")
        print(f"{'='*60}{Color.RESET}")
        print(f"Primary Region  : {Color.BOLD}{self.primary_region}{Color.RESET}")
        print(f"Standby Region  : {Color.BOLD}{self.standby_region}{Color.RESET}")
        print(f"Target RPO      : {self.rpo_target_sec} detik (Max Data Loss Window)")
        print(f"Target RTO      : {self.rto_target_sec} detik (Max Downtime Window)\n")

        print(f"[{Color.YELLOW}STAGE 1{Color.RESET}] Menginjeksikan pemadaman total (Outage) pada Primary Region...")
        time.sleep(0.6)
        self.primary_healthy = False
        print(f"[{Color.RED}CRITICAL{Color.RESET}] Health check failed 3/3 pada {self.primary_region}!")

        print(f"\n[{Color.YELLOW}STAGE 2{Color.RESET}] Mengukur Replication Lag & Potensi Kehilangan Data (RPO)...")
        time.sleep(0.5)
        observed_rpo = self.replication_lag_sec + random.uniform(0.1, 0.8)
        rpo_status = f"{Color.GREEN}MEMENUHI TARGET (<= {self.rpo_target_sec}s){Color.RESET}" if observed_rpo <= self.rpo_target_sec else f"{Color.RED}VIOLASI RPO{Color.RESET}"
        print(f"-> Observed Data Lag (RPO): {observed_rpo:.2f} detik -> {rpo_status}")

        print(f"\n[{Color.YELLOW}STAGE 3{Color.RESET}] Mengeksekusi Automated DNS / Global Load Balancer Failover...")
        start_rto = time.time()
        for step in ["Promote Standby Database to Read/Write", "Update Anycast Route & Global DNS TTL", "Warm-up Cache Pools di Secondary Region"]:
            time.sleep(0.4)
            print(f"   [OK] {step}")

        simulated_downtime = random.uniform(12.0, 22.0)
        rto_status = f"{Color.GREEN}MEMENUHI TARGET (<= {self.rto_target_sec}s){Color.RESET}" if simulated_downtime <= self.rto_target_sec else f"{Color.RED}VIOLASI RTO{Color.RESET}"
        print(f"\n-> Total Recovery Time (RTO): {simulated_downtime:.1f} detik -> {rto_status}")
        print(f"[{Color.GREEN}SUCCESS{Color.RESET}] Trafik dialihkan 100% ke {self.standby_region}.\n")

class CircuitBreakerSimulator:
    def __init__(self, failure_threshold: int = 3, recovery_time: float = 2.0):
        self.state = CircuitState.CLOSED
        self.failure_threshold = failure_threshold
        self.recovery_time = recovery_time
        self.failure_count = 0
        self.last_failure_time = 0.0

    def call_service(self, simulate_upstream_fail: bool) -> bool:
        current_time = time.time()

        if self.state == CircuitState.OPEN:
            if current_time - self.last_failure_time > self.recovery_time:
                self.state = CircuitState.HALF_OPEN
                print(f"   {Color.YELLOW}[CIRCUIT BREAKER: HALF_OPEN]{Color.RESET} Menguji probe request ke upstream...")
            else:
                print(f"   {Color.RED}[CIRCUIT BREAKER: OPEN]{Color.RESET} Fast-fail! Permintaan diblokir demi melindungi sistem.")
                return False

        if simulate_upstream_fail:
            self.failure_count += 1
            self.last_failure_time = current_time
            print(f"   {Color.RED}[UPSTREAM ERROR]{Color.RESET} Kegagalan ke-{self.failure_count}/{self.failure_threshold}")
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                print(f"   {Color.RED}{Color.BOLD}>>> TRIP TRIGGERED! State berpindah ke OPEN <<<{Color.RESET}")
            return False
        else:
            if self.state == CircuitState.HALF_OPEN:
                print(f"   {Color.GREEN}[CIRCUIT BREAKER: CLOSED]{Color.RESET} Upstream pulih, sirkuit ditutup kembali.")
                self.state = CircuitState.CLOSED
                self.failure_count = 0
            return True

def simulate_slo_engine():
    print(f"\n{Color.CYAN}{'='*60}")
    print(f" SRE ENGINE: SLI, SLO & ERROR BUDGET BURN RATE MONITOR")
    print(f"{'='*60}{Color.RESET}")

    slo = SLOMetric(name="Checkout Service Availability", target_percentage=99.9, total_requests=10000, failed_requests=6)
    
    print(f"Service Target  : {Color.BOLD}{slo.name}{Color.RESET}")
    print(f"SLO Objective   : {Color.BOLD}{slo.target_percentage}%{Color.RESET} ketersediaan sukses")
    print(f"Total Traffic   : {slo.total_requests:,} permintaan")
    print(f"Failed Traffic  : {slo.failed_requests} error (5xx)")
    print(f"Current SLI     : {Color.GREEN if slo.current_sli >= slo.target_percentage else Color.RED}{slo.current_sli:.4f}%{Color.RESET}")
    print(f"Budget Max Err  : {slo.error_budget_allowed:.1f} error diizinkan")
    print(f"Budget Terpakai : {slo.error_budget_consumed_pct:.1f}%")

    burn_rate = slo.burn_rate_1h
    print(f"1-Hour Burn Rate: {Color.BOLD}{burn_rate:.2f}x{Color.RESET}")

    if burn_rate >= 14.4:
        print(f"[{Color.RED}{Color.BOLD}PAGER ALERT - P1{Color.RESET}] Burn Rate > 14.4x (2% budget habis dalam 1 jam). Hubungi SRE on-call!")
    elif burn_rate >= 6.0:
        print(f"[{Color.YELLOW}TICKET ALERT - P2{Color.RESET}] Burn Rate > 6.0x (5% budget habis dalam 6 jam). Kirim alert ke Slack SRE.")
    else:
        print(f"[{Color.GREEN}STABLE{Color.RESET}] Tingkat konsumsi error budget normal dan terkendali.")

def run_resilience_circuit_test():
    print(f"\n{Color.CYAN}{'='*60}")
    print(f" SIMULASI CIRCUIT BREAKER & CHAOS FAULT INJECTION")
    print(f"{'='*60}{Color.RESET}")
    cb = CircuitBreakerSimulator(failure_threshold=3, recovery_time=1.5)

    print("Skenario 1: Menembakkan 4 kegagalan beruntun...")
    for i in range(1, 5):
        print(f"Request #{i}:")
        cb.call_service(simulate_upstream_fail=True)
        time.sleep(0.3)

    print("\nSkenario 2: Permintaan datang saat sirkuit masih OPEN...")
    cb.call_service(simulate_upstream_fail=False)

    print(f"\nSkenario 3: Menunggu recovery timeout ({cb.recovery_time} detik)...")
    time.sleep(cb.recovery_time + 0.1)

    print("Mengirim request sehat untuk memulihkan sirkuit...")
    cb.call_service(simulate_upstream_fail=False)

def main_interactive_menu():
    while True:
        print(f"\n{Color.BOLD}{Color.BLUE}===================================================={Color.RESET}")
        print(f"{Color.BOLD}{Color.MAGENTA}  SRE & DISASTER RECOVERY LAB SIMULATOR (BAB 10)  {Color.RESET}")
        print(f"{Color.BOLD}{Color.BLUE}===================================================={Color.RESET}")
        print(f"1. Kalkulasi SLI, SLO & Alerting Error Budget Burn Rate")
        print(f"2. Simulasi Disaster Recovery & Multi-Region Failover (RPO/RTO)")
        print(f"3. Simulasi Fault Injection & Circuit Breaker Pattern")
        print(f"4. Jalankan Semua Uji Ketahanan Otomatis (Audit Resilience)")
        print(f"5. Keluar")
        print(f"{Color.BLUE}----------------------------------------------------{Color.RESET}")

        try:
            choice = input(f"{Color.BOLD}Pilih opsi simulasi [1-5]: {Color.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting lab simulator.")
            sys.exit(0)

        if choice == "1":
            simulate_slo_engine()
        elif choice == "2":
            dr = DisasterRecoverySimulator()
            dr.simulate_failover()
        elif choice == "3":
            run_resilience_circuit_test()
        elif choice == "4":
            print(f"\n{Color.GREEN}>>> MEMULAI AUDIT KETAHANAN SRE OTOMATIS <<<{Color.RESET}")
            simulate_slo_engine()
            dr = DisasterRecoverySimulator()
            dr.simulate_failover()
            run_resilience_circuit_test()
            print(f"\n{Color.GREEN}[PASSED] Seluruh modul simulasi fondasi SRE selesai dieksekusi.{Color.RESET}")
        elif choice == "5":
            print(f"{Color.GREEN}Terima kasih telah menyelesaikan modul lab SRE & DR.{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid. Silakan masukkan angka 1-5.{Color.RESET}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--non-interactive":
        simulate_slo_engine()
        dr = DisasterRecoverySimulator()
        dr.simulate_failover()
        run_resilience_circuit_test()
    else:
        main_interactive_menu()
