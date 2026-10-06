#!/usr/bin/env python3
"""
Lab Exercise: Dockerfile Engineering & Image Optimization Simulator
BAB-03 Dockerfile Engineering dan Image Optimization

Simulasi teknis konsep fondasi inti:
1. Docker Build Layer Caching & Cache Invalidation
2. Single-Stage vs Multi-Stage Build Image Sizing
3. .dockerignore Security & Context Pruning
4. Exec Form vs Shell Form Signal Propagation (PID 1)
"""

import sys
import time
import hashlib
from typing import List, Dict, Tuple

# ANSI Terminal Colors
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"
BG_BLUE = "\033[44m"


def print_banner() -> None:
    print(f"{CYAN}{BOLD}======================================================================{RESET}")
    print(f"{BG_BLUE}{WHITE}{BOLD}   DOCKERFILE ENGINEERING & IMAGE OPTIMIZATION SIMULATOR (BAB-03)   {RESET}")
    print(f"{CYAN}{BOLD}======================================================================{RESET}\n")


def simulate_layer_caching() -> None:
    print(f"{MAGENTA}{BOLD}[MODUL 1: LAYER CACHING & ORDER OF EXECUTION]{RESET}")
    print(f"{DIM}Mengamati dampak perubahan file terhadap Docker Build Cache.{RESET}\n")

    steps: List[Tuple[str, str, bool, int]] = [
        ("Step 1/6 : FROM node:20-alpine", "FROM node:20-alpine", False, 175),
        ("Step 2/6 : WORKDIR /app", "WORKDIR /app", False, 0),
        ("Step 3/6 : COPY package*.json ./", "COPY package.json", False, 1),
        ("Step 4/6 : RUN npm ci --only=production", "RUN npm ci", False, 65),
        ("Step 5/6 : COPY src/ ./src", "COPY src/", True, 5),  # Source file changed!
        ("Step 6/6 : CMD [\"node\", \"src/server.js\"]", "CMD exec form", False, 0),
    ]

    cache_invalidated = False
    total_time = 0.0

    for step_title, instruction, file_changed, size_mb in steps:
        time.sleep(0.3)
        if file_changed:
            cache_invalidated = True

        if not cache_invalidated:
            status = f"{GREEN}---> Using cache{RESET}"
            duration = 0.02
        else:
            status = f"{YELLOW}---> Running in 9b2d8e4f1a... [CACHE MISS]{RESET}"
            duration = 0.6 if size_mb > 10 else 0.2

        total_time += duration
        print(f"{BOLD}{step_title}{RESET}")
        print(f"       {status}")
        print(f"       {DIM}Layer Size: ~{size_mb} MB | Delta Time: {duration:.2f}s{RESET}")

    print(f"\n{GREEN}{BOLD}✓ Image build selesai dalam {total_time:.2f}s!{RESET}")
    print(f"{CYAN}Insight:{RESET} Meletakkan `COPY package*.json` sebelum `COPY src/`")
    print(f"menjaga layer dependency `{GREEN}USING CACHE{RESET}` saat kode aplikasi diperbarui.\n")


def simulate_multistage_comparison() -> None:
    print(f"{MAGENTA}{BOLD}[MODUL 2: SINGLE-STAGE VS MULTI-STAGE BUILD OPTIMIZATION]{RESET}")
    print(f"{DIM}Komparasi ukuran artifak runtime antara Single-Stage vs Multi-Stage.{RESET}\n")

    single_stage_layers: Dict[str, float] = {
        "Base OS (golang:1.22-bookworm)": 302.0,
        "Go Compiler & Toolchain": 540.0,
        "Source Code & Git History": 45.0,
        "Compiled Binary (app)": 28.5,
        "Build Artifacts & Cache (/root/.cache)": 185.0,
    }

    multistage_layers: Dict[str, float] = {
        "Base OS (gcr.io/distroless/static-debian12)": 2.4,
        "Non-root User & SSL Root CA Certificates": 1.2,
        "Compiled Binary (app - stripped)": 18.2,
    }

    total_single = sum(single_stage_layers.values())
    total_multi = sum(multistage_layers.values())

    print(f"{RED}{BOLD}1. Single-Stage Dockerfile (Dev-in-Prod Anti-Pattern):{RESET}")
    for layer, size in single_stage_layers.items():
        print(f"   - {layer:<45} : {YELLOW}{size:>6.1f} MB{RESET}")
    print(f"   {RED}Total Single-Stage Size: {total_single:.1f} MB{RESET}\n")

    print(f"{GREEN}{BOLD}2. Multi-Stage Dockerfile (Distroless Target):{RESET}")
    for layer, size in multistage_layers.items():
        print(f"   - {layer:<45} : {GREEN}{size:>6.1f} MB{RESET}")
    print(f"   {GREEN}Total Multi-Stage Size : {total_multi:.1f} MB{RESET}\n")

    reduction = ((total_single - total_multi) / total_single) * 100
    print(f"{CYAN}{BOLD}Hasil Optimasi:{RESET}")
    print(f"Efisiensi Penyimpanan : {GREEN}{BOLD}-{reduction:.1f}%{RESET}")
    print(f"Attack Surface        : {GREEN}Toolchain, compiler, package manager berhasil dipangkas!{RESET}\n")


def simulate_dockerignore_audit() -> None:
    print(f"{MAGENTA}{BOLD}[MODUL 3: .DOCKERIGNORE & BUILD CONTEXT SANITIZATION]{RESET}")
    print(f"{DIM}Verifikasi pencegahan kebocoran secret dan bloatware context.{RESET}\n")

    files_in_workspace = [
        ("src/index.js", 12 * 1024, False),
        ("src/utils.js", 8 * 1024, False),
        ("package.json", 2 * 1024, False),
        (".git/objects/pack/bigpack.pack", 84 * 1024 * 1024, True),
        (".env.production", 512, True),
        ("node_modules/@aws-sdk/client-s3/index.js", 120 * 1024 * 1024, True),
        ("tests/e2e/cypress.videos.mp4", 45 * 1024 * 1024, True),
    ]

    print(f"{WHITE}{BOLD}{'File / Path':<45} | {'Ukuran':<12} | {'Status Filter'}{RESET}")
    print("-" * 75)

    leaked_secrets = []
    total_ignored_mb = 0.0

    for path, size_bytes, should_ignore in files_in_workspace:
        size_str = f"{size_bytes / (1024*1024):.2f} MB" if size_bytes > 1024 * 1024 else f"{size_bytes / 1024:.1f} KB"
        if should_ignore:
            status = f"{GREEN}[BLOCKED by .dockerignore]{RESET}"
            total_ignored_mb += size_bytes / (1024 * 1024)
            if ".env" in path:
                leaked_secrets.append(path)
        else:
            status = f"{CYAN}[INCLUDED in Context]{RESET}"

        print(f"{path:<45} | {size_str:<12} | {status}")

    print(f"\n{GREEN}{BOLD}✓ Ringkasan Sanitasi:{RESET}")
    print(f"- Menghemat Context Transfer ke Daemon : {YELLOW}{total_ignored_mb:.2f} MB{RESET}")
    print(f"- Proteksi Secret Teruji              : {GREEN}Sukses memblokir {len(leaked_secrets)} file sensitif (.env){RESET}\n")


def simulate_pid1_signal_handling() -> None:
    print(f"{MAGENTA}{BOLD}[MODUL 4: EXEC FORM VS SHELL FORM & SIGNAL FORWARDING]{RESET}")
    print(f"{DIM}Mengapa CMD [\"node\", \"app.js\"] vs CMD node app.js mempengaruhi Graceful Shutdown.{RESET}\n")

    print(f"{RED}{BOLD}A. Shell Form: `CMD node app.js`{RESET}")
    print(f"   Hierarchy : {YELLOW}PID 1 [/bin/sh] -> PID 2 [node app.js]{RESET}")
    print(f"   Event     : `docker stop` mengirim SIGTERM ke PID 1 (/bin/sh)")
    print(f"   Masalah   : /bin/sh {RED}TIDAK{RESET} meneruskan SIGTERM ke PID 2!")
    print(f"   Dampak    : Timeout 10 detik lalu dimatikan paksa via {RED}{BOLD}SIGKILL{RESET} (Unclean exit).\n")

    print(f"{GREEN}{BOLD}B. Exec Form: `CMD [\"node\", \"app.js\"]`{RESET}")
    print(f"   Hierarchy : {GREEN}PID 1 [node app.js]{RESET}")
    print(f"   Event     : `docker stop` mengirim SIGTERM langsung ke Node runtime")
    print(f"   Hasil     : Aplikasi menangkap event `{GREEN}process.on('SIGTERM'){RESET}`,")
    print(f"               menutup koneksi database, drain HTTP pool, exit code 0 ({GREEN}Graceful{RESET}).\n")


def main() -> None:
    print_banner()
    simulate_layer_caching()
    simulate_multistage_comparison()
    simulate_dockerignore_audit()
    simulate_pid1_signal_handling()

    print(f"{CYAN}{BOLD}======================================================================{RESET}")
    print(f"{GREEN}{BOLD}Lab Exercise Simulator BAB-03 Berhasil Dijalankan Secara Penuh!{RESET}")
    print(f"{CYAN}{BOLD}======================================================================{RESET}")


if __name__ == "__main__":
    main()
