#!/usr/bin/env python3
"""
Lab Exercise M01: Simulasi Continuous Delivery & Deployment Strategies
BAB 07: Continuous Delivery dan Automated Deployment (DevOps Beginner)

Simulasi interaktif pipeline CD:
1. Artifact Verification & Checksum
2. Staging Deployment & Automated Acceptance Tests
3. Deployment Strategy Selector:
   - Rolling Update
   - Blue-Green Deployment
   - Canary Release (dengan Traffic Shifting & Auto-Rollback)
"""

import sys
import time
import random
import hashlib

# ANSI Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
BLUE = "\033[34m"
YELLOW = "\033[33m"
RED = "\033[31m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"

def print_header(title: str):
    print(f"\n{BOLD}{CYAN}{'=' * 65}{RESET}")
    print(f"{BOLD}{CYAN} [CD LAB] {title.center(53)} {RESET}")
    print(f"{BOLD}{CYAN}{'=' * 65}{RESET}\n")

def log_step(stage: str, message: str, status: str = "INFO"):
    colors = {
        "INFO": BLUE,
        "SUCCESS": GREEN,
        "WARN": YELLOW,
        "FAIL": RED,
        "ACTION": MAGENTA
    }
    col = colors.get(status, BLUE)
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] {col}[{status.ljust(7)}]{RESET} {BOLD}{stage}:{RESET} {message}")

def simulate_progress(action_text: str, duration: float = 1.0, steps: int = 15):
    print(f"{YELLOW}* {action_text}...{RESET} ", end="", flush=True)
    step_duration = duration / steps
    for _ in range(steps):
        time.sleep(step_duration)
        print(f"{GREEN}█{RESET}", end="", flush=True)
    print(f" {GREEN}[SELESAI]{RESET}")

def verify_artifact(version: str, artifact_payload: str) -> bool:
    log_step("ARTIFACT", f"Memverifikasi paket rilis v{version}...", "INFO")
    simulate_progress("Menghitung SHA-256 Checksum", 0.6)
    checksum = hashlib.sha256(artifact_payload.encode()).hexdigest()
    log_step("ARTIFACT", f"Checksum valid: {checksum[:16]}... OK", "SUCCESS")
    return True

def run_staging_tests() -> bool:
    log_step("STAGING", "Deploying ke Staging Environment...", "ACTION")
    simulate_progress("Provisioning container staging", 0.7)
    simulate_progress("Menjalankan Smoke & Integration Tests", 0.8)
    
    # 95% pass rate
    passed = random.random() < 0.95
    if passed:
        log_step("STAGING", "Semua test suite Staging (42/42 tests) lolos!", "SUCCESS")
        return True
    else:
        log_step("STAGING", "Smoke test gagal: HTTP 502 pada /healthz", "FAIL")
        return False

def deploy_rolling_update(num_instances: int = 4):
    print_header("STRATEGI: ROLLING UPDATE")
    print(f"{BOLD}Total instance yang diupdate secara bertahap:{RESET} {num_instances} pods\n")
    
    for i in range(1, num_instances + 1):
        print(f"{YELLOW}--- Mengganti Pod-{i} (v1.0 -> v2.0) ---{RESET}")
        log_step("ROLLING", f"Mencabut Pod-{i} dari load balancer target group", "INFO")
        simulate_progress(f"Terminating v1 Pod-{i}", 0.4)
        simulate_progress(f"Launching v2 Pod-{i}", 0.6)
        log_step("ROLLING", f"Health-check probe Pod-{i}: 200 OK", "SUCCESS")
        log_step("ROLLING", f"Memasukkan Pod-{i} kembali ke traffic pool", "SUCCESS")
        time.sleep(0.3)
    
    print(f"\n{BOLD}{GREEN}✓ Rolling Update selesai! 100% armada berjalan di v2.0 tanpa downtime.{RESET}\n")

def deploy_blue_green():
    print_header("STRATEGI: BLUE-GREEN DEPLOYMENT")
    print(f"{BLUE}[Active Router]{RESET} ---> {BOLD}{BLUE}[Environment BLUE: v1.0 (Live)]{RESET}")
    print(f"{MAGENTA}[Idle Stack]{RESET}   ---> {BOLD}{GREEN}[Environment GREEN: v2.0 (Deploying)]{RESET}\n")
    
    log_step("GREEN", "Provisioning full replica environment GREEN...", "ACTION")
    simulate_progress("Deploying v2.0 ke Green environment", 0.8)
    simulate_progress("Running synthetic transaction checks on Green", 0.7)
    log_step("GREEN", "Green Environment dinyatakan HEALTHY & Siap melayani traffic", "SUCCESS")
    
    print(f"\n{YELLOW}Menunggu keputusan switch router cutover...{RESET}")
    simulate_progress("Memindahkan Router DNS / Ingress dari BLUE ke GREEN", 1.0)
    
    print(f"\n{GREEN}[Active Router]{RESET} ---> {BOLD}{GREEN}[Environment GREEN: v2.0 (LIVE)]{RESET}")
    print(f"{YELLOW}[Standby]{RESET}        ---> {BOLD}{BLUE}[Environment BLUE: v1.0 (Standby/Rollback ready)]{RESET}\n")
    log_step("CUTOVER", "Traffic 100% beralih ke GREEN. Zero downtime tercapai.", "SUCCESS")

def deploy_canary():
    print_header("STRATEGI: CANARY DEPLOYMENT")
    print(f"Deploying Canary instance dengan bertahap routing traffic:\n")
    
    log_step("CANARY", "Deploying 1 Canary Instance (v2.0)...", "ACTION")
    simulate_progress("Bootstrapping Canary node", 0.6)
    
    stages = [
        {"traffic": "10%", "duration": 0.6, "fail_prob": 0.0},
        {"traffic": "25%", "duration": 0.7, "fail_prob": 0.0},
        {"traffic": "50%", "duration": 0.8, "fail_prob": 0.15},
        {"traffic": "100%", "duration": 0.9, "fail_prob": 0.0}
    ]
    
    for idx, stage in enumerate(stages, 1):
        traffic = stage["traffic"]
        log_step("CANARY", f"Mengarahkan {traffic} user traffic ke Canary...", "ACTION")
        simulate_progress(f"Memonitor metric error rate & latency ({traffic})", stage["duration"])
        
        # Simulasi deteksi anomali
        if random.random() < stage["fail_prob"]:
            print(f"\n{BOLD}{RED}[ALERT] SLI breach terdeteksi! Error rate melonjak > 3.5%!{RESET}")
            log_step("MONITOR", "Automated Rollback terpicu!", "FAIL")
            simulate_progress("Mengembalikan traffic 100% ke Baseline (v1.0)", 0.6)
            simulate_progress("Terminating broken canary instance", 0.5)
            print(f"\n{BOLD}{RED}✘ Canary Release digagalkan & di-rollback otomatis secara aman.{RESET}\n")
            return
        
        log_step("METRICS", f"Latency p99: 42ms | Error Rate: 0.01% [NORMAL]", "SUCCESS")
        time.sleep(0.3)
        
    print(f"\n{BOLD}{GREEN}✓ Canary dinyatakan stabil! Full roll-out 100% selesai sukses.{RESET}\n")

def interactive_menu():
    print_header("SIMULASI CD & DEPLOYMENT AUTOMATION")
    print("Selamat datang di Lab Interaktif Continuous Delivery (BAB 07).")
    print("Lab ini mendemonstrasikan pipeline rilis otomatis dari artifact hingga production.\n")
    
    app_version = "2.4.0-rc.1"
    raw_payload = f"app-binary-payload-data-{app_version}-{time.time()}"
    
    # Tahap 1: Verifikasi Artifak
    if not verify_artifact(app_version, raw_payload):
        sys.exit(1)
        
    # Tahap 2: Staging Gate
    print()
    if not run_staging_tests():
        print(f"\n{RED}Pipeline dihentikan: Staging gate gagal.{RESET}")
        sys.exit(1)
        
    print(f"\n{BOLD}{GREEN}Pipeline Gate: Staging disetujui. Siap rilis ke Production!{RESET}\n")
    
    while True:
        print(f"{BOLD}Pilih Strategi Automated Deployment yang ingin disimulasikan:{RESET}")
        print("  1) Rolling Update (Zero Downtime, Incremental Replacement)")
        print("  2) Blue-Green Deployment (Instant Switchover & Instant Rollback)")
        print("  3) Canary Deployment (Progressive Traffic Shift & Auto-Rollback)")
        print("  4) Jalankan Semua Strategi Secara Berurutan")
        print("  5) Keluar")
        
        try:
            choice = input(f"\n{BOLD}{CYAN}Masukkan pilihan (1-5): {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nKeluar dari simulasi.")
            break
            
        if choice == "1":
            deploy_rolling_update()
        elif choice == "2":
            deploy_blue_green()
        elif choice == "3":
            deploy_canary()
        elif choice == "4":
            deploy_rolling_update()
            deploy_blue_green()
            deploy_canary()
        elif choice == "5":
            print(f"\n{GREEN}Lab selesai. Terima kasih telah mempraktikkan konsep CD!{RESET}\n")
            break
        else:
            print(f"{RED}Pilihan tidak valid. Silakan pilih 1-5.{RESET}\n")

if __name__ == "__main__":
    interactive_menu()
