#!/usr/bin/env python3
"""
Lab Exercise M01: Enterprise Scale Monorepos & Large Assets Simulation
BAB-10: Git & GitHub Enterprise Workflows

Simulates:
1. Git LFS Clean/Smudge Filters & Pointer System
2. Partial Clones (Blobless vs Treeless vs Shallow)
3. Sparse-Checkout Cone Mode Directory Projection
4. Monorepo Affected Target Calculation (Graph Traversal)
"""

import sys
import hashlib
import time
from typing import Dict, List, Set

# ANSI Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"
BG_BLUE = "\033[44m\033[37m"

def print_header(title: str) -> None:
    print(f"\n{BG_BLUE} === {title} === {RESET}\n")

def print_step(step: str) -> None:
    print(f"{BOLD}{CYAN}>>> [STEP]{RESET} {step}")

def print_success(msg: str) -> None:
    print(f"{GREEN}✓ {msg}{RESET}")

def print_info(label: str, val: str) -> None:
    print(f"  {YELLOW}{label:24}:{RESET} {val}")

# ----------------------------------------------------------------------
# 1. Git LFS Simulation (Clean & Smudge Filters)
# ----------------------------------------------------------------------
def simulate_git_lfs() -> None:
    print_header("SIMULASI 1: Git LFS (Clean / Smudge Filters & Pointer File)")
    print_step("Membuat simulasi file asset biner berukuran besar (models/weights.bin)...")

    dummy_content = b"SIMULATED_LARGE_WEIGHT_MATRIX_TENSOR_WEIGHTS" * 250000  # ~11 MB
    actual_size = len(dummy_content)
    sha256_hash = hashlib.sha256(dummy_content).hexdigest()

    print_info("File Path", "models/weights.bin")
    print_info("Raw Binary Size", f"{actual_size / (1024 * 1024):.2f} MB ({actual_size:,} bytes)")
    print_info("SHA-256 Digest", sha256_hash)

    print("\n" + BOLD + "[Filter Clean Execution: Git Add]" + RESET)
    print("Git mendeteksi pola .gitattributes: '*.bin filter=lfs diff=lfs merge=lfs -text'")
    print(f"{MAGENTA}Payload asli dialihkan ke LFS Remote Storage Object Store (.git/lfs/objects/)...{RESET}")

    lfs_pointer = (
        f"version https://git-lfs.github.com/spec/v1\n"
        f"oid sha256:{sha256_hash}\n"
        f"size {actual_size}\n"
    )
    pointer_size = len(lfs_pointer.encode('utf-8'))

    print_success("LFS Pointer file terbentuk untuk dimasukkan ke Git Object Tree standard:")
    print("-" * 50)
    for line in lfs_pointer.strip().split("\n"):
        print(f"  {CYAN}{line}{RESET}")
    print("-" * 50)
    print_info("Git Tree Size Incurred", f"{pointer_size} bytes (Hemat {(actual_size - pointer_size):,} bytes pada Git database!)")

    print("\n" + BOLD + "[Filter Smudge Execution: Git Checkout]" + RESET)
    print(f"Git Checkout membaca LFS Pointer file dan mengunduh blob asli berdasarkan hash OID...")
    time.sleep(0.3)
    print_success(f"File models/weights.bin berhasil dihidrasi ke working directory ({actual_size / (1024*1024):.2f} MB).")

# ----------------------------------------------------------------------
# 2. Partial Clones & Shallow Clones
# ----------------------------------------------------------------------
def simulate_partial_clones() -> None:
    print_header("SIMULASI 2: Clone Strategies untuk Skala Enterprise Monorepo")
    strategies = [
        {
            "name": "Full Clone (`git clone <url>`)",
            "commits": "100%",
            "trees": "100%",
            "blobs": "100%",
            "download_mb": 4850.0,
            "desc": "Mengunduh seluruh riwayat commit, tree struktur folder, dan seluruh isi file dari hari pertama."
        },
        {
            "name": "Shallow Clone (`--depth=1`)",
            "commits": "Hanya commit HEAD",
            "trees": "Hanya tree HEAD",
            "blobs": "Hanya blob HEAD",
            "download_mb": 310.0,
            "desc": "Memotong history commit. Cepat untuk CI/CD, namun membatasi git log / bisect / rebase."
        },
        {
            "name": "Blobless Clone (`--filter=blob:none`)",
            "commits": "100%",
            "trees": "100%",
            "blobs": "On-demand (lazy fetched)",
            "download_mb": 420.0,
            "desc": "Riwayat commit & log lengkap tanpa mendownload konten file lama. Blob diunduh saat checkout/diff."
        },
        {
            "name": "Treeless Clone (`--filter=tree:0`)",
            "commits": "100%",
            "trees": "On-demand",
            "blobs": "On-demand",
            "download_mb": 65.0,
            "desc": "Paling minimal untuk developer worktree. Mengunduh tree dan blob hanya untuk commit aktif."
        }
    ]

    for s in strategies:
        print(f"{BOLD}{BLUE}[{s['name']}]{RESET}")
        print_info("Commit History", s["commits"])
        print_info("Tree Structures", s["trees"])
        print_info("File Blobs", s["blobs"])
        print_info("Estimasi Data Ditransfer", f"{s['download_mb']} MB")
        print(f"  {YELLOW}Deskripsi{RESET} : {s['desc']}\n")

# ----------------------------------------------------------------------
# 3. Sparse-Checkout Cone Mode Simulation
# ----------------------------------------------------------------------
def simulate_sparse_checkout() -> None:
    print_header("SIMULASI 3: Git Sparse-Checkout (Cone Mode)")
    print_step("Memproyeksikan arsitektur monorepo berukuran 120.000 file...")

    monorepo_structure = [
        "apps/web-dashboard/src/App.tsx",
        "apps/web-dashboard/package.json",
        "apps/mobile-ios/Sources/App.swift",
        "apps/mobile-android/src/MainActivity.kt",
        "services/payment-gateway/src/main.go",
        "services/user-auth/src/server.ts",
        "services/order-processing/src/app.py",
        "packages/ui-components/src/Button.tsx",
        "packages/shared-models/src/types.ts",
        "packages/database-client/src/client.ts"
    ]

    print(f"Total file terdaftar di Git Tree remote: {len(monorepo_structure)} modul percontohan.")
    print("Developer hanya mengerjakan modul backend payment: `services/payment-gateway`")

    active_cone = ["services/payment-gateway", "packages/shared-models"]
    print(f"\n{BOLD}Perintah yang dieksekusi:{RESET}")
    print(f"  {CYAN}$ git sparse-checkout init --cone{RESET}")
    print(f"  {CYAN}$ git sparse-checkout set services/payment-gateway packages/shared-models{RESET}\n")

    print_step("Evaluasi file yang diproyeksikan ke disk lokal:")
    for path in monorepo_structure:
        included = any(path.startswith(cone) for cone in active_cone)
        status = f"{GREEN}[TERPROYEKSI]{RESET}" if included else f"{RED}[DIABAIKAN - VIRTUAL]{RESET}"
        print(f"  {status:32} -> {path}")

    print_success("Penghematan I/O Disk & File Watcher (IDE) tercapai via Cone Mode!")

# ----------------------------------------------------------------------
# 4. Monorepo Affected Target Graph Analysis
# ----------------------------------------------------------------------
def simulate_monorepo_affected() -> None:
    print_header("SIMULASI 4: Monorepo Affected Target Detection (Nx / Turborepo Logic)")

    dependency_graph: Dict[str, List[str]] = {
        "packages/shared-models": [],
        "packages/database-client": ["packages/shared-models"],
        "packages/ui-components": ["packages/shared-models"],
        "services/user-auth": ["packages/database-client", "packages/shared-models"],
        "services/payment-gateway": ["packages/database-client"],
        "apps/web-dashboard": ["packages/ui-components", "packages/shared-models"],
        "apps/mobile-ios": ["packages/shared-models"],
    }

    print_step("Graf Ketergantungan Paket (Dependency Graph):")
    for pkg, deps in dependency_graph.items():
        deps_str = ", ".join(deps) if deps else "(Tidak ada dependensi internal)"
        print(f"  {CYAN}{pkg}{RESET} depends on: {deps_str}")

    changed_file = "packages/database-client/src/client.ts"
    print(f"\n{BOLD}{YELLOW}Deteksi Git Diff (HEAD~1 vs HEAD):{RESET} {changed_file}")
    changed_package = "packages/database-client"

    # Reverse graph traversal to find affected packages
    affected: Set[str] = {changed_package}
    queue = [changed_package]

    while queue:
        current = queue.pop(0)
        for consumer, deps in dependency_graph.items():
            if current in deps and consumer not in affected:
                affected.add(consumer)
                queue.append(consumer)

    print(f"\n{BOLD}Hasil Analisis Dampak (Affected Packages):{RESET}")
    for pkg in dependency_graph:
        if pkg in affected:
            mark = f"{RED}[REBUILD & TEST]{RESET}"
            reason = "Langsung diubah" if pkg == changed_package else f"Terdampak dependensi transitif"
            print(f"  {mark:26} {pkg:30} ({reason})")
        else:
            print(f"  {GREEN}[CACHE REPLAY]{RESET}    {pkg:30} (Skip build - Cache Hit)")

    print_success(f"CI Monorepo hanya perlu membangun {len(affected)} dari {len(dependency_graph)} paket total.")

# ----------------------------------------------------------------------
# Interactive CLI Runner
# ----------------------------------------------------------------------
def main() -> None:
    print(f"{BOLD}{MAGENTA}")
    print("=" * 70)
    print("  BAB-10: ENTERPRISE MONOREPO & LARGE ASSET MANAGEMENT LAB")
    print("  Interactive Hands-on Simulation Engine")
    print("=" * 70 + f"{RESET}")

    simulations = [
        ("Git LFS (Clean/Smudge Filter & Object Pointer)", simulate_git_lfs),
        ("Enterprise Clone Strategies (Blobless, Treeless, Shallow)", simulate_partial_clones),
        ("Sparse-Checkout Cone Mode Projection", simulate_sparse_checkout),
        ("Monorepo Affected Build Engine (Graph Traversal)", simulate_monorepo_affected),
    ]

    while True:
        print(f"\n{BOLD}Menu Simulasi Lab:{RESET}")
        for idx, (label, _) in enumerate(simulations, 1):
            print(f"  {CYAN}{idx}.{RESET} {label}")
        print(f"  {CYAN}5.{RESET} Jalankan Seluruh Simulasi Sekaligus")
        print(f"  {CYAN}0.{RESET} Keluar")

        try:
            choice = input(f"\n{YELLOW}Pilih opsi [0-5]: {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar dari simulasi.")
            sys.exit(0)

        if choice == "0":
            print("Selesai. Selamat belajar Git Enterprise!")
            break
        elif choice in ["1", "2", "3", "4"]:
            simulations[int(choice) - 1][1]()
        elif choice == "5":
            for _, func in simulations:
                func()
        else:
            print(f"{RED}Pilihan tidak valid. Silakan masukkan angka 0-5.{RESET}")

if __name__ == "__main__":
    main()
