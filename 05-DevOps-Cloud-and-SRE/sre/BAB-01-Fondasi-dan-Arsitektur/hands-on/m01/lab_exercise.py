#!/usr/bin/env python3
"""
Lab Exercise: Fondasi & Arsitektur SRE (Site Reliability Engineering)
Modul: BAB-01 Fondasi dan Arsitektur SRE

Simulasi interaktif konsep inti:
1. SLI (Service Level Indicator) & SLO (Service Level Objective)
2. Error Budget Tracking & Burn Rate
3. Four Golden Signals (Latency, Traffic, Errors, Saturation)
4. Toil Budgeting (50% Engineering vs 50% Toil Rule)
"""

import sys
import time
import random
from dataclasses import dataclass
from typing import List, Dict

# ANSI Color Codes untuk terminal interaktif
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
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"


@dataclass
class RequestMetric:
    timestamp: float
    status_code: int
    latency_ms: float
    is_error: bool


class SRESimulator:
    def __init__(self, target_slo: float = 99.5, total_window_requests: int = 1000):
        self.target_slo = target_slo  # misal 99.5%
        self.error_budget_percentage = 100.0 - target_slo  # misal 0.5%
        self.total_window_requests = total_window_requests
        self.allowed_failed_requests = int(total_window_requests * (self.error_budget_percentage / 100.0))
        self.consumed_budget = 0
        self.history: List[RequestMetric] = []

    def print_header(self, title: str):
        print(f"\n{Colors.BOLD}{Colors.CYAN}{'=' * 65}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.MAGENTA} >>> [SRE LAB] {title.upper()} <<<{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 65}{Colors.RESET}")

    def run_sli_slo_simulation(self):
        self.print_header("Simulasi SLI / SLO & Error Budget Burn")
        print(f"{Colors.WHITE}Target SLO Ketersediaan : {Colors.GREEN}{self.target_slo}%{Colors.RESET}")
        print(f"{Colors.WHITE}Total Request Baseline  : {Colors.YELLOW}{self.total_window_requests}{Colors.RESET}")
        print(f"{Colors.WHITE}Alokasi Error Budget    : {Colors.RED}{self.allowed_failed_requests} error requests{Colors.RESET}\n")

        print(f"{Colors.CYAN}Memulai streaming 100 request sintetis...{Colors.RESET}\n")
        time.sleep(0.5)

        total_sample = 100
        success_count = 0
        failure_count = 0

        for i in range(1, total_sample + 1):
            now = time.time()
            # Simulasi probabilistik: 96% success, 4% fault injection
            is_fault = random.random() < 0.04
            if is_fault:
                status = random.choice([500, 502, 503, 504])
                latency = round(random.uniform(500.0, 1500.0), 2)
                failure_count += 1
                self.consumed_budget += 1
            else:
                status = 200
                latency = round(random.uniform(20.0, 150.0), 2)
                success_count += 1

            self.history.append(RequestMetric(now, status, latency, is_fault))

            # Visual progress display
            status_color = Colors.GREEN if status == 200 else Colors.RED
            burn_pct = (self.consumed_budget / max(1, self.allowed_failed_requests)) * 100.0
            burn_color = Colors.GREEN if burn_pct < 80 else (Colors.YELLOW if burn_pct < 100 else Colors.RED)

            sys.stdout.write(
                f"\rReq #{i:03d} | Status: {status_color}{status}{Colors.RESET} | "
                f"Latency: {latency:6.1f}ms | Budget Burn: {burn_color}{burn_pct:5.1f}%{Colors.RESET}"
            )
            sys.stdout.flush()
            time.sleep(0.03)

        print("\n")
        current_sli = (success_count / total_sample) * 100.0
        sli_color = Colors.GREEN if current_sli >= self.target_slo else Colors.RED

        print(f"{Colors.BOLD}--- Evaluasi Service Level ---{Colors.RESET}")
        print(f"Total Sampel Request : {total_sample}")
        print(f"Request Sukses       : {Colors.GREEN}{success_count}{Colors.RESET}")
        print(f"Request Gagal        : {Colors.RED}{failure_count}{Colors.RESET}")
        print(f"Actual SLI           : {sli_color}{current_sli:.2f}%{Colors.RESET} (Target SLO: {self.target_slo}%)")

        if current_sli >= self.target_slo:
            print(f"{Colors.BG_GREEN}{Colors.WHITE}{Colors.BOLD} KEPUTUSAN SRE: SLO Terpenuhi. Deployment fitur baru diizinkan. {Colors.RESET}")
        else:
            print(f"{Colors.BG_RED}{Colors.WHITE}{Colors.BOLD} KEPUTUSAN SRE: SLO Terlanggar! Freeze deployment, prioritaskan reliabilitas. {Colors.RESET}")

    def run_golden_signals_demo(self):
        self.print_header("The Four Golden Signals of Monitoring")
        print(f"{Colors.WHITE}1. Latency    : Waktu eksekusi melayani permintaan (ms).")
        print(f"2. Traffic    : Tingkat beban sistem (RPS - Requests Per Second).")
        print(f"3. Errors     : Tingkat kegagalan permintaan (%).")
        print(f"4. Saturation : Pemanfaatan sumber daya bottleneck (CPU/Memory %).{Colors.RESET}\n")

        print(f"{Colors.YELLOW}Mengukur metrik instan 5 siklus tick cluster...{Colors.RESET}")
        print(f"{'-' * 65}")
        print(f"{'Siklus':<8}{'Latency (p99)':<16}{'Traffic (RPS)':<16}{'Error Rate':<14}{'Saturation':<12}")
        print(f"{'-' * 65}")

        for tick in range(1, 6):
            latency_p99 = random.uniform(45.0, 320.0)
            rps = random.randint(850, 4200)
            err_rate = random.uniform(0.01, 2.5)
            saturation = random.uniform(35.0, 95.0)

            lat_col = Colors.GREEN if latency_p99 < 150 else Colors.YELLOW
            err_col = Colors.GREEN if err_rate < 1.0 else Colors.RED
            sat_col = Colors.GREEN if saturation < 80 else Colors.RED

            print(
                f"Tick {tick:<3} "
                f"{lat_col}{latency_p99:6.1f} ms{Colors.RESET}         "
                f"{Colors.CYAN}{rps:<8} req/s{Colors.RESET} "
                f"{err_col}{err_rate:5.2f} %{Colors.RESET}        "
                f"{sat_col}{saturation:5.1f} %{Colors.RESET}"
            )
            time.sleep(0.4)

    def run_toil_calculator(self):
        self.print_header("Kalkulator Toil vs Engineering SRE (Rule 50%)")
        print(f"{Colors.WHITE}Berdasarkan prinsip SRE Google:")
        print(f"- Maksimal beban Toil (pekerjaan repetitif/manual): {Colors.YELLOW}50%{Colors.RESET}")
        print(f"- Minimal waktu Rekayasa Teknik / Otomasi        : {Colors.GREEN}50%{Colors.RESET}\n")

        try:
            print(f"{Colors.CYAN}Masukkan perkiraan pembagian jam kerja mingguan tim (Total 40 jam):{Colors.RESET}")
            manual_ops = float(input(" -> Jam untuk tiket manual / reboot / restart service : ") or "12")
            oncall = float(input(" -> Jam on-call interrupt & triage insiden             : ") or "10")
            engineering = float(input(" -> Jam pengembangan otomasi & arsitektur sistem       : ") or "18")
        except ValueError:
            print(f"{Colors.RED}Input tidak valid, menggunakan nilai default.{Colors.RESET}")
            manual_ops, oncall, engineering = 12.0, 10.0, 18.0

        total_hours = manual_ops + oncall + engineering
        toil_hours = manual_ops + oncall
        toil_percentage = (toil_hours / total_hours) * 100.0
        eng_percentage = (engineering / total_hours) * 100.0

        print(f"\n{Colors.BOLD}--- Hasil Audit Toil Tim ---{Colors.RESET}")
        print(f"Total Jam Terhitung   : {total_hours:.1f} jam")
        print(f"Jam Toil / Operasional: {Colors.YELLOW}{toil_hours:.1f} jam ({toil_percentage:.1f}%){Colors.RESET}")
        print(f"Jam Rekayasa/Otomasi  : {Colors.GREEN}{engineering:.1f} jam ({eng_percentage:.1f}%){Colors.RESET}")

        if toil_percentage > 50.0:
            print(f"\n{Colors.BG_RED}{Colors.WHITE}{Colors.BOLD} PERINGATAN: Toil melebihi batas 50%! SRE mengalami kelelahan operasional (burnout). {Colors.RESET}")
            print(f"{Colors.RED}Rekomendasi: Alihkan tiket manual ke form self-service atau bangun otomasi Terraform/Ansible.{Colors.RESET}")
        else:
            print(f"\n{Colors.BG_GREEN}{Colors.WHITE}{Colors.BOLD} STATUS SEHAT: Beban toil di bawah 50%. Tim memiliki kapasitas inovasi tinggi. {Colors.RESET}")


def interactive_menu():
    sim = SRESimulator()
    while True:
        print(f"\n{Colors.BOLD}{Colors.WHITE}====================================================={Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.BLUE}   LAB PRAKTIK SRE: BAB-01 FONDASI & ARSITEKTUR     {Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.WHITE}====================================================={Colors.RESET}")
        print(f"{Colors.CYAN}1.{Colors.RESET} Simulasi SLI/SLO & Error Budget Burn Rate")
        print(f"{Colors.CYAN}2.{Colors.RESET} Simulasi The Four Golden Signals")
        print(f"{Colors.CYAN}3.{Colors.RESET} Kalkulator & Audit Beban Toil (50% Cap)")
        print(f"{Colors.CYAN}4.{Colors.RESET} Jalankan Seluruh Simulasi Sekaligus")
        print(f"{Colors.RED}5.{Colors.RESET} Keluar (Exit)")
        print(f"{Colors.BOLD}{Colors.WHITE}-----------------------------------------------------{Colors.RESET}")

        choice = input(f"{Colors.BOLD}Pilih menu (1-5): {Colors.RESET}").strip()

        if choice == "1":
            sim.run_sli_slo_simulation()
        elif choice == "2":
            sim.run_golden_signals_demo()
        elif choice == "3":
            sim.run_toil_calculator()
        elif choice == "4":
            sim.run_sli_slo_simulation()
            sim.run_golden_signals_demo()
            sim.run_toil_calculator()
        elif choice == "5":
            print(f"\n{Colors.GREEN}Selesai. Terus pertahankan ketersediaan sistem dan kelola error budget!{Colors.RESET}\n")
            break
        else:
            print(f"{Colors.RED}Pilihan tidak dikenali. Silakan masukkan angka 1-5.{Colors.RESET}")


if __name__ == "__main__":
    interactive_menu()
