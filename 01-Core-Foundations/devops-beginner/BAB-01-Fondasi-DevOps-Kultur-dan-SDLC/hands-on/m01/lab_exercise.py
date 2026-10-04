#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Fondasi DevOps, Kultur, dan SDLC
Topik: BAB 01 - Fondasi DevOps, Kultur, dan SDLC
Framework: CALMS, Tiga Cara (The Three Ways), dan Metrik DORA Dasar
"""

import sys
import time
import random

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

def print_header(title: str):
    line = "=" * 65
    print(f"\n{CYAN}{BOLD}{line}{RESET}")
    print(f"{CYAN}{BOLD}  {title}{RESET}")
    print(f"{CYAN}{BOLD}{line}{RESET}\n")

def print_step(step_num: int, description: str):
    print(f"{YELLOW}[Langkah {step_num}]{RESET} {WHITE}{description}{RESET}")

def simulate_delay(seconds: float = 0.5):
    time.sleep(seconds)

def explain_calms():
    print_header("1. FRAMEWORK CALMS DALAM DEVOPS")
    pillars = [
        ("C - Culture", "Mengikis silo antara Dev dan Ops, menumbuhkan shared responsibility.", GREEN),
        ("A - Automation", "Otomatisasi pengujian, build, dan deployment untuk konsistensi.", CYAN),
        ("L - Lean", "Mengurangi pemborosan (waste), membatasi WIP, batch size kecil.", YELLOW),
        ("M - Measurement", "Mengukur metrik objektif seperti DORA (Lead Time, MTTR, dll).", MAGENTA),
        ("S - Sharing", "Transparansi pengetahuan, blameless post-mortem, dan kolaborasi.", BLUE),
    ]
    for pillar, desc, color in pillars:
        print(f"  {color}{BOLD}▸ {pillar:<16}{RESET} : {desc}")
        simulate_delay(0.2)
    print()

def simulate_three_ways():
    print_header("2. TIGA CARA (THE THREE WAYS)")
    ways = [
        ("Prinsip Pertama", "Flow (Aliran Sistem)", "Mempercepat aliran nilai dari Dev ke Ops ke Pelanggan."),
        ("Prinsip Kedua", "Fast Feedback", "Memperpendek dan memperkuat loop umpan balik (deteksi bug dini)."),
        ("Prinsip Ketiga", "Continuous Learning", "Menciptakan kultur eksperimen, risiko terkendali, dan pembelajaran.")
    ]
    for name, title, detail in ways:
        print(f"  {MAGENTA}{BOLD}[{name}]{RESET} {BOLD}{title}{RESET}")
        print(f"    └─ {detail}")
        simulate_delay(0.2)
    print()

def run_pipeline_simulation(mode: str):
    print_header(f"SIMULASI PIPELINE PENGIRIMAN: {mode.upper()}")
    
    if mode == "silo":
        print(f"{RED}{BOLD}! Skenario Tradisional (Wall of Confusion): Dev melempar kode ke Ops.{RESET}\n")
        steps = [
            ("Penyusunan Kode (Dev)", 1.2, True),
            ("Serah Terima Dokumen Rilis manual", 1.5, True),
            ("Persetujuan Komite CAB (Menunggu Hari)", 1.8, True),
            ("Deploy Manual ke Server Staging", 1.5, random.choice([True, False])),
            ("Inspeksi Manual & Integrasi Ops", 1.2, True),
            ("Deploy Manual ke Production", 1.8, False)
        ]
        
        lead_time_days = random.randint(14, 30)
        mttr_hours = random.randint(12, 48)
        
        for idx, (name, dur, success) in enumerate(steps, start=1):
            print_step(idx, f"Menjalankan: {name}...")
            simulate_delay(dur * 0.3)
            if not success:
                print(f"    {RED}✘ GAGAL: Terjadi konfigurasi lingkungan yang mismatch!{RESET}")
                print(f"    {RED}✘ Blame Game: Dev menyalahkan Ops, Ops menyalahkan Dev.{RESET}")
                print(f"\n{RED}{BOLD}Hasil Rilis Gagal (Deployment Rollback Diperlukan){RESET}")
                print(f"  - Lead Time for Changes : {lead_time_days} Hari")
                print(f"  - Mean Time to Recover  : {mttr_hours} Jam")
                print(f"  - Change Failure Rate   : 75%")
                return
            else:
                print(f"    {GREEN}✔ Selesai (Manual){RESET}")

    elif mode == "devops":
        print(f"{GREEN}{BOLD}✔ Skenario DevOps Modern: CI/CD Terotomatisasi & Shared Ownership.{RESET}\n")
        steps = [
            ("Commit & Push ke Version Control", 0.5, True),
            ("CI Lint & Static Code Analysis", 0.6, True),
            ("Automated Unit & Integration Tests", 0.8, True),
            ("Automated Container Build & Scan", 0.7, True),
            ("Automated Canary Deployment ke Production", 0.9, True),
            ("Automated Health Check & Telemetry", 0.5, True)
        ]
        
        lead_time_mins = random.randint(15, 45)
        mttr_mins = random.randint(5, 15)
        
        for idx, (name, dur, success) in enumerate(steps, start=1):
            print_step(idx, f"Pipeline Step: {name}...")
            simulate_delay(dur * 0.3)
            print(f"    {GREEN}✔ Lolos verifikasi otomatis{RESET}")

        print(f"\n{GREEN}{BOLD}Hasil Rilis Sukses (Deployment Berhasil Secara Kontinu){RESET}")
        print(f"  - Lead Time for Changes : {lead_time_mins} Menit")
        print(f"  - Deployment Frequency  : Beberapa rilis per hari")
        print(f"  - Mean Time to Recover  : {mttr_mins} Menit")
        print(f"  - Change Failure Rate   : < 5%")

def interactive_menu():
    while True:
        print_header("LAB INTERAKTIF: FONDASI DEVOPS & SDLC")
        print(f"  {BOLD}1.{RESET} Pelajari Framework CALMS")
        print(f"  {BOLD}2.{RESET} Pelajari Prinsip Tiga Cara (The Three Ways)")
        print(f"  {BOLD}3.{RESET} Jalankan Simulasi Rilis: Model Silo Tradisional")
        print(f"  {BOLD}4.{RESET} Jalankan Simulasi Rilis: Model DevOps Terintegrasi")
        print(f"  {BOLD}5.{RESET} Komparasi Metrik DORA (Silo vs DevOps)")
        print(f"  {BOLD}0.{RESET} Keluar")
        print()
        
        try:
            choice = input(f"{YELLOW}Pilih menu [0-5]: {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSelesai.")
            break
            
        if choice == "1":
            explain_calms()
        elif choice == "2":
            simulate_three_ways()
        elif choice == "3":
            run_pipeline_simulation("silo")
        elif choice == "4":
            run_pipeline_simulation("devops")
        elif choice == "5":
            print_header("KOMPARASI METRIK DORA")
            print(f"{'Metrik':<28} | {'Silo Tradisional':<20} | {'DevOps Modern':<20}")
            print("-" * 74)
            print(f"{'Deployment Frequency':<28} | {'1x per kuartal/bulan':<20} | {'On-demand (banyak/hari)':<20}")
            print(f"{'Lead Time for Changes':<28} | {'1 - 6 Bulan':<20} | {'< 1 Jam':<20}")
            print(f"{'Mean Time to Recover (MTTR)':<28} | {'Hari hingga Minggu':<20} | {'< 1 Jam':<20}")
            print(f"{'Change Failure Rate':<28} | {'40% - 60%':<20} | {'0% - 15%':<20}")
            print("-" * 74)
        elif choice == "0":
            print(f"\n{GREEN}Terima kasih telah menjalankan Lab Fondasi DevOps!{RESET}\n")
            break
        else:
            print(f"\n{RED}Pilihan tidak valid. Silakan coba lagi.{RESET}")
        
        try:
            input(f"\n{CYAN}Tekan [Enter] untuk kembali ke menu...{RESET}")
        except (EOFError, KeyboardInterrupt):
            break

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        explain_calms()
        simulate_three_ways()
        run_pipeline_simulation("silo")
        run_pipeline_simulation("devops")
    else:
        interactive_menu()

if __name__ == "__main__":
    main()
