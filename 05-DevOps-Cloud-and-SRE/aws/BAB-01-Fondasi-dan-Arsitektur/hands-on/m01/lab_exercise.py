#!/usr/bin/env python3
"""
Hands-On Lab M01: Simulasi Fondasi dan Arsitektur AWS (BAB-01)
--------------------------------------------------------------
Materi:
1. AWS Global Infrastructure (Regions, Availability Zones, Edge Locations)
2. AWS Shared Responsibility Model (IaaS, PaaS, SaaS)
3. AWS Well-Architected Framework (6 Pilar Arsitektur)
4. Disaster Recovery (DR) Strategy & RTO/RPO Trade-off Simulator

Script ini bersifat runnable mandiri tanpa dependensi eksternal (pure standard library).
"""

import sys
import time
import random
from typing import Dict, List, Tuple

# ANSI Terminal Color Codes
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"
RESET = "\033[0m"


def print_banner():
    banner = f"""
{CYAN}{BOLD}======================================================================
     AWS FOUNDATION & CLOUD ARCHITECTURE INTERACTIVE SIMULATOR
           BAB 01: Fondasi & Arsitektur Global Cloud AWS
======================================================================{RESET}
{DIM}Mode: Hands-on Lab M01 | Standard Library Python 3 | Pure Interactive{RESET}
"""
    print(banner)


def simulate_latency(region_name: str, base_ms: int, variance: int) -> float:
    time.sleep(0.15)
    return round(base_ms + random.uniform(-variance, variance), 2)


# =====================================================================
# MODUL 1: AWS Global Infrastructure Simulator
# =====================================================================
def run_global_infra_sim():
    print(f"\n{YELLOW}{BOLD}[MODUL 1] Simulasi AWS Global Infrastructure & Routing Latency{RESET}")
    print(f"{DIM}Memeriksa replikasi data antar Availability Zone (AZ) dan Edge Locations...{RESET}\n")

    regions = {
        "ap-southeast-3": {
            "name": "Jakarta",
            "azs": ["ap-southeast-3a", "ap-southeast-3b", "ap-southeast-3c"],
            "base_latency": 4.5,
        },
        "ap-southeast-1": {
            "name": "Singapore",
            "azs": ["ap-southeast-1a", "ap-southeast-1b", "ap-southeast-1c"],
            "base_latency": 15.2,
        },
        "us-east-1": {
            "name": "N. Virginia",
            "azs": ["us-east-1a", "us-east-1b", "us-east-1c", "us-east-1d"],
            "base_latency": 185.0,
        },
    }

    print(f"{BOLD}{'Region ID':<18} {'Lokasi':<15} {'AZs Aktif':<35} {'Ping (ms)':<10}{RESET}")
    print("-" * 80)
    for reg_id, data in regions.items():
        lat = simulate_latency(reg_id, int(data["base_latency"]), 2)
        az_str = ", ".join(data["azs"][:2]) + f" (+{len(data['azs'])-2} AZ)"
        color = GREEN if lat < 20 else (YELLOW if lat < 100 else RED)
        print(f"{CYAN}{reg_id:<18}{RESET} {data['name']:<15} {az_str:<35} {color}{lat:<10.2f}{RESET}")

    print(f"\n{BOLD}Simulasi Skenario Multi-AZ Failover (High Availability):{RESET}")
    print(f"[*] Primari RDS Instance berjalan di {CYAN}ap-southeast-3a{RESET}")
    print(f"[*] Sinkronisasi replika standby di {CYAN}ap-southeast-3b{RESET} via fiber optic berlatensi rendah (<2ms)")
    time.sleep(0.3)
    print(f"{RED}[! ALARM !] Degradasi daya terdeteksi pada DC di ap-southeast-3a!{RESET}")
    print(f"[*] AWS Route 53 & RDS Multi-AZ mendeteksi healthcheck failure (30 detik)...")
    time.sleep(0.3)
    print(f"{GREEN}[✓ SUKSES] Otomatis mempromosikan ap-southeast-3b sebagai Master! Zero data loss (RPO = 0).{RESET}")


# =====================================================================
# MODUL 2: Shared Responsibility Model Matrix
# =====================================================================
def run_shared_responsibility_sim():
    print(f"\n{YELLOW}{BOLD}[MODUL 2] Audit AWS Shared Responsibility Model{RESET}")
    print(f"{DIM}Menentukan pembagian batas tanggung jawab antara AWS (Security OF the Cloud){RESET}")
    print(f"{DIM}dan Pelanggan (Security IN the Cloud) untuk berbagai model layanan.{RESET}\n")

    items = [
        ("Fisik Data Center & Server Hardware", "IaaS / PaaS / SaaS", "AWS", "Security OF the Cloud"),
        ("Hypervisor & Host Virtualization", "IaaS (EC2)", "AWS", "Security OF the Cloud"),
        ("Guest OS, Patching & Firewall OS", "IaaS (EC2)", "Customer", "Security IN the Cloud"),
        ("Database Engine Patching", "PaaS (Amazon RDS)", "AWS", "Security OF the Cloud"),
        ("Aplikasi, Skema & Akses Data DB", "PaaS (Amazon RDS)", "Customer", "Security IN the Cloud"),
        ("Serverless Execution Runtime", "FaaS (AWS Lambda)", "AWS", "Security OF the Cloud"),
        ("Fungsi Kode & IAM Permission Lambda", "FaaS (AWS Lambda)", "Customer", "Security IN the Cloud"),
        ("Enkripsi Data (At-Rest & In-Transit)", "Semua Model", "Customer", "Security IN the Cloud"),
    ]

    print(f"{BOLD}{'Komponen Arsitektur':<36} {'Model Layanan':<18} {'Penanggung Jawab':<18} {'Klasifikasi':<20}{RESET}")
    print("-" * 94)

    for comp, svc, owner, classification in items:
        badge_color = GREEN if owner == "Customer" else MAGENTA
        print(f"{WHITE}{comp:<36}{RESET} {CYAN}{svc:<18}{RESET} {badge_color}{owner:<18}{RESET} {DIM}{classification}{RESET}")

    print(f"\n{BOLD}Kunci Pemahaman:{RESET}")
    print(f" -> {MAGENTA}AWS{RESET} bertanggung jawab atas infrastruktur dasar, fasilitas fisik, dan layer hardware.")
    print(f" -> {GREEN}Customer{RESET} selalu bertanggung jawab penuh atas data mereka, identitas/IAM, dan konfigurasi keamanan.")


# =====================================================================
# MODUL 3: AWS Well-Architected Framework Review
# =====================================================================
def run_well_architected_evaluator():
    print(f"\n{YELLOW}{BOLD}[MODUL 3] Evaluasi 6 Pilar AWS Well-Architected Framework{RESET}")
    print(f"{DIM}Mengevaluasi kesiapan arsitektur aplikasi e-commerce microservices...{RESET}\n")

    pillars = {
        "1. Operational Excellence": {
            "checks": [("Infrastructure as Code (Terraform/CloudFormation)", True), ("Automated CI/CD Pipeline", True), ("Runbook terintegrasi", False)],
            "weight": 20,
        },
        "2. Security": {
            "checks": [("Principle of Least Privilege (IAM)", True), ("Enkripsi KMS At-Rest & TLS In-Transit", True), ("MFA diaktifkan untuk akun Root", True)],
            "weight": 20,
        },
        "3. Reliability": {
            "checks": [("Multi-AZ Deployment untuk Web & Database", True), ("Auto Scaling Group teruji", True), ("Chaos Engineering / DR drill berkala", False)],
            "weight": 20,
        },
        "4. Performance Efficiency": {
            "checks": [("CloudFront CDN Caching diaktifkan", True), ("ElastiCache Redis untuk sesi", True), ("Instance Type disesuaikan (Graviton)", True)],
            "weight": 15,
        },
        "5. Cost Optimization": {
            "checks": [("AWS Savings Plans / Reserved Instances", True), ("S3 Lifecycle Policies ke Glacier", True), ("Alokasi Tagging Biaya FinOps", False)],
            "weight": 15,
        },
        "6. Sustainability": {
            "checks": [("Serverless / Autoscaling Scale-to-Zero", True), ("Pemanfaatan prosesor efisien (AWS Graviton)", True)],
            "weight": 10,
        },
    }

    total_score = 0
    max_score = 100

    for pillar_name, pdata in pillars.items():
        print(f"{BOLD}{pillar_name}:{RESET}")
        passed_checks = 0
        for item, status in pdata["checks"]:
            mark = f"{GREEN}PASS{RESET}" if status else f"{RED}FAIL{RESET}"
            icon = "✓" if status else "✗"
            print(f"  [{icon}] {item:<52} [{mark}]")
            if status:
                passed_checks += 1
        
        ratio = passed_checks / len(pdata["checks"])
        pillar_score = ratio * pdata["weight"]
        total_score += pillar_score
        print(f"  {DIM}Skor Pilar: {pillar_score:.1f}/{pdata['weight']} poin{RESET}\n")

    print("-" * 60)
    score_color = GREEN if total_score >= 80 else (YELLOW if total_score >= 60 else RED)
    print(f"{BOLD}Total Indeks Arsitektur Well-Architected: {score_color}{total_score:.1f} / {max_score}{RESET}")
    if total_score >= 80:
        print(f"{GREEN}[STATUS: ENTERPRISE READY] Arsitektur memenuhi standar keandalan tinggi.{RESET}")
    else:
        print(f"{YELLOW}[STATUS: REMEDIATION NEEDED] Perbaiki item yang bertanda FAIL sebelum go-live.{RESET}")


# =====================================================================
# MODUL 4: Disaster Recovery (DR) Strategy & Cost/RTO Simulator
# =====================================================================
def run_dr_strategy_simulator():
    print(f"\n{YELLOW}{BOLD}[MODUL 4] Simulator Strategi Disaster Recovery (DR) AWS{RESET}")
    print(f"{DIM}Menganalisis Trade-off RTO (Recovery Time Objective), RPO (Recovery Point Objective), dan Biaya.{RESET}\n")

    strategies = [
        {
            "name": "Backup & Restore",
            "rpo": "Jam - Hari",
            "rto": "24+ Jam",
            "cost_index": "$",
            "desc": "Simpan snapshot ke S3/Glacier di region lain. Pulihkan server manual saat bencana.",
        },
        {
            "name": "Pilot Light",
            "rpo": "Menit",
            "rto": "1 - 2 Jam",
            "cost_index": "$$",
            "desc": "Database aktif replikasi core di secondary region; compute (EC2) distart saat bencana.",
        },
        {
            "name": "Warm Standby",
            "rpo": "Detik - Menit",
            "rto": "Menit",
            "cost_index": "$$$",
            "desc": "Versi scaled-down aplikasi berjalan 24/7 di secondary region, siap scale up seketika.",
        },
        {
            "name": "Multi-Region Active-Active",
            "rpo": "Near Zero",
            "rto": "Near Zero",
            "cost_index": "$$$$$",
            "desc": "Traffic terbagi aktif ke 2+ region (Route 53 latency routing + DynamoDB Global Tables).",
        },
    ]

    print(f"{BOLD}{'Strategi DR':<26} {'RPO':<16} {'RTO':<14} {'Biaya':<8} {'Penjelasan Ringkas'}{RESET}")
    print("-" * 94)
    for s in strategies:
        print(f"{CYAN}{s['name']:<26}{RESET} {YELLOW}{s['rpo']:<16}{RESET} {GREEN}{s['rto']:<14}{RESET} {MAGENTA}{s['cost_index']:<8}{RESET} {s['desc']}")

    print(f"\n{BOLD}Rekomendasi Arsitektur:{RESET}")
    print(f"- Aplikasi Finansial / Payment Gateway -> {CYAN}Warm Standby{RESET} atau {CYAN}Multi-Region Active-Active{RESET}")
    print(f"- Portal Internal / Dev Environment   -> {CYAN}Backup & Restore{RESET}")


# =====================================================================
# Main Interactive Controller
# =====================================================================
def main():
    print_banner()

    menu = """
Pilih Modul Hands-On:
  1. Simulasi AWS Global Infrastructure & Multi-AZ Failover
  2. Audit AWS Shared Responsibility Model (IaaS, PaaS, SaaS)
  3. Evaluasi 6 Pilar AWS Well-Architected Framework
  4. Analisis Strategi Disaster Recovery (RTO/RPO Trade-off)
  5. Jalankan Seluruh Modul Berurutan (Full Comprehensive Lab)
  0. Keluar
"""

    # Jika berjalan dalam mode non-interaktif (piped/CI/test), jalankan semua modul
    if not sys.stdin.isatty():
        print(f"{DIM}[Auto-Run Mode detected: Executing all modules sequentially]{RESET}")
        run_global_infra_sim()
        run_shared_responsibility_sim()
        run_well_architected_evaluator()
        run_dr_strategy_simulator()
        print(f"\n{GREEN}{BOLD}[✓] Seluruh simulasi BAB 01 selesai dijalankan dengan sukses.{RESET}\n")
        return

    while True:
        print(menu)
        try:
            choice = input(f"{BOLD}Masukkan pilihan [0-5]: {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar dari lab.")
            break

        if choice == "1":
            run_global_infra_sim()
        elif choice == "2":
            run_shared_responsibility_sim()
        elif choice == "3":
            run_well_architected_evaluator()
        elif choice == "4":
            run_dr_strategy_simulator()
        elif choice == "5":
            run_global_infra_sim()
            run_shared_responsibility_sim()
            run_well_architected_evaluator()
            run_dr_strategy_simulator()
            print(f"\n{GREEN}{BOLD}[✓] Selesai menjalankan seluruh modul.{RESET}")
        elif choice == "0":
            print(f"{GREEN}Lab selesai. Selamat belajar arsitektur AWS!{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak valid. Silakan pilih 0-5.{RESET}")


if __name__ == "__main__":
    main()
