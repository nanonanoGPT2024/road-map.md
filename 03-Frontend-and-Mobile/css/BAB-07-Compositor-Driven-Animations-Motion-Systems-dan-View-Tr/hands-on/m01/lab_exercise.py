#!/usr/bin/env python3
"""
Lab Exercise M01: Compositor-Driven Animations, Motion Systems & View Transitions
Simulasi teknis interaktif pipeline rendering browser, off-main-thread composite,
budget frame 60fps/120fps, dan transisi View Transitions API.
"""

import math
import os
import sys
import time
from dataclasses import dataclass
from enum import Enum
from typing import List, Tuple

# ANSI Escape Colors for Rich Terminal Output
class Color:
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
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    GRAY = "\033[90m"


class PipelineStage(Enum):
    JS_STYLE = "JavaScript / Recalc Style"
    LAYOUT = "Layout (Reflow)"
    PAINT = "Paint (Rasterization)"
    COMPOSITE = "Composite (GPU Thread)"


@dataclass
class CSSPropertyProfile:
    name: str
    css_syntax: str
    triggers_layout: bool
    triggers_paint: bool
    is_compositor_thread: bool
    typical_cost_ms: float
    description: str


PROPERTIES_DB = [
    CSSPropertyProfile(
        name="left / top",
        css_syntax="left: 120px;",
        triggers_layout=True,
        triggers_paint=True,
        is_compositor_thread=False,
        typical_cost_ms=18.4,
        description="Memicu reflow layout geometri DOM hierarkis dan repainting seluruh layer."
    ),
    CSSPropertyProfile(
        name="width / height",
        css_syntax="width: 350px;",
        triggers_layout=True,
        triggers_paint=True,
        is_compositor_thread=False,
        typical_cost_ms=22.1,
        description="Merubah dimensi elemen dan memicu layout cascades ke child dan sibling elements."
    ),
    CSSPropertyProfile(
        name="background-color",
        css_syntax="background-color: #3b82f6;",
        triggers_layout=False,
        triggers_paint=True,
        is_compositor_thread=False,
        typical_cost_ms=8.2,
        description="Melewati layout tetapi memicu repainting raster bitmaps pada main thread."
    ),
    CSSPropertyProfile(
        name="transform",
        css_syntax="transform: translate3d(120px, 0, 0);",
        triggers_layout=False,
        triggers_paint=False,
        is_compositor_thread=True,
        typical_cost_ms=1.1,
        description="Compositor-only! Dijalankan langsung pada GPU compositor thread tanpa jank."
    ),
    CSSPropertyProfile(
        name="opacity",
        css_syntax="opacity: 0.85;",
        triggers_layout=False,
        triggers_paint=False,
        is_compositor_thread=True,
        typical_cost_ms=0.9,
        description="Compositor-only! Alpha blending dioperasikan di level quad texture GPU."
    ),
]


def print_header(title: str) -> None:
    line = "═" * 70
    print(f"\n{Color.BOLD}{Color.CYAN}{line}{Color.RESET}")
    print(f"{Color.BOLD}{Color.WHITE}  {title.center(66)}{Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}{line}{Color.RESET}\n")


def simulate_rendering_pipeline():
    print_header("SIMULASI 1: BROWSER RENDERING PIPELINE & FRAME JANK")
    print(f"{Color.WHITE}Perbandingan eksekusi animasi per frame (Budget 60 FPS = {Color.BOLD}16.67ms{Color.RESET}{Color.WHITE}):{Color.RESET}\n")

    for prop in PROPERTIES_DB:
        print(f"{Color.BOLD}{Color.YELLOW}● Properti:{Color.RESET} {Color.WHITE}{prop.name:<18}{Color.RESET} [{Color.DIM}{prop.css_syntax}{Color.RESET}]")
        stages = []
        stages.append(f"{Color.GREEN}Style{Color.RESET}")
        if prop.triggers_layout:
            stages.append(f"{Color.RED}Layout [Reflow]{Color.RESET}")
        if prop.triggers_paint:
            stages.append(f"{Color.MAGENTA}Paint [Raster]{Color.RESET}")
        stages.append(f"{Color.CYAN}Composite [GPU]{Color.RESET}")

        pipeline_str = " -> ".join(stages)
        print(f"  {Color.GRAY}Pipeline :{Color.RESET} {pipeline_str}")
        
        # Frame budget check
        budget = 16.67
        jank = prop.typical_cost_ms > budget
        status_tag = f"{Color.BG_RED}{Color.WHITE} JANK / FRAME DROP {Color.RESET}" if jank else f"{Color.BG_GREEN}{Color.WHITE} 60-120 FPS SMOOTH {Color.RESET}"
        
        bar_len = min(40, int((prop.typical_cost_ms / 30.0) * 40))
        bar_color = Color.RED if jank else Color.GREEN
        meter = f"{bar_color}{'█' * bar_len}{Color.GRAY}{'░' * (40 - bar_len)}{Color.RESET}"

        print(f"  {Color.GRAY}Duration :{Color.RESET} {prop.typical_cost_ms:>5.1f} ms |{meter}| {status_tag}")
        print(f"  {Color.GRAY}Detail   :{Color.RESET} {prop.description}\n")


def simulate_motion_spring_physics():
    print_header("SIMULASI 2: MOTION SYSTEM - DAMPED SPRING PHYSICS ENGINE")
    print(f"{Color.WHITE}Visualisasi kurva pegas (Stiffness: 180, Damping: 14, Mass: 1.0){Color.RESET}")
    print(f"{Color.GRAY}Animasi responsif modern menghindari linear timing functions.{Color.RESET}\n")

    # Damped harmonic oscillator simulation
    target = 100.0
    position = 0.0
    velocity = 0.0
    stiffness = 180.0
    damping = 14.0
    mass = 1.0
    dt = 0.016  # 60 FPS tick (16ms)

    ticks: List[Tuple[float, float]] = []
    current_time = 0.0

    while current_time <= 1.2:
        spring_force = -stiffness * (position - target)
        damping_force = -damping * velocity
        acceleration = (spring_force + damping_force) / mass
        velocity += acceleration * dt
        position += velocity * dt
        ticks.append((current_time, position))
        current_time += dt

    # ASCII Plot
    width = 50
    print(f"{Color.BOLD}Time(s) | Displacement Curve (0% -> 100% with Overshoot):{Color.RESET}")
    print(f"{Color.GRAY}{'─' * 70}{Color.RESET}")

    for t, pos in ticks[::2]:  # Sample every 2 ticks
        normalized = max(0.0, min(140.0, pos))
        bar_index = int((normalized / 140.0) * width)
        line = [" "] * (width + 1)
        
        # Target mark
        target_idx = int((100.0 / 140.0) * width)
        line[target_idx] = f"{Color.GRAY}┆{Color.RESET}"
        
        # Spring Head
        if bar_index <= width:
            c = Color.CYAN if pos < 100.0 else (Color.YELLOW if pos <= 105.0 else Color.MAGENTA)
            line[bar_index] = f"{c}●{Color.RESET}"

        curve_str = "".join(line)
        print(f"{t:>6.2f}s | {curve_str} {Color.WHITE}{pos:>5.1f}%{Color.RESET}")

    print(f"{Color.GRAY}{'─' * 70}{Color.RESET}")
    print(f"{Color.CYAN}●{Color.RESET} Acceleration phase  |  {Color.MAGENTA}●{Color.RESET} Damped Overshoot  |  {Color.GRAY}┆{Color.RESET} Target Anchor (100%)\n")


def simulate_view_transitions_lifecycle():
    print_header("SIMULASI 3: VIEW TRANSITIONS API (DOCUMENT TRANSITIONS)")
    print(f"{Color.WHITE}Membedah lifecycle internal `document.startViewTransition(updateCallback)`:{Color.RESET}\n")

    steps = [
        ("Step 1: Snapshot Old State", "::view-transition-old(root)", "Browser meng-capture bitmap texture dari DOM lama dan membekukan visual rendering."),
        ("Step 2: DOM Mutation Callback", "updateDOMCallback()", "State aplikasi diubah (misal: navigasi route, swap kartu, atau reordering list)."),
        ("Step 3: Snapshot New State", "::view-transition-new(root)", "Browser me-render DOM baru secara off-screen dan menangkap bitmap texture baru."),
        ("Step 4: Pseudo-element Tree Assembly", "::view-transition-group", "Browser mengaitkan layer lama dan baru dalam GPU transition container."),
        ("Step 5: GPU Morph Cross-fade", "transform & opacity blend", "Animasi simultan: Old fade out + scale down, New fade in + scale up tanpa reflow!")
    ]

    for title, pseudo, desc in steps:
        print(f"{Color.BOLD}{Color.GREEN}▶ {title}{Color.RESET}")
        print(f"  {Color.MAGENTA}CSS Target :{Color.RESET} {Color.BOLD}{pseudo}{Color.RESET}")
        print(f"  {Color.GRAY}Aktivitas  :{Color.RESET} {desc}\n")
        time.sleep(0.1)

    print(f"{Color.BOLD}{Color.YELLOW}Hierarki Pseudo-Element Tree View Transitions:{Color.RESET}")
    print(f"""{Color.CYAN}::view-transition
 └─ ::view-transition-group(card-item)
     ├─ ::view-transition-image-pair(card-item)
     │   ├─ ::view-transition-old(card-item) {Color.RED}[GPU Texture: Outgoing]{Color.CYAN}
     │   └─ ::view-transition-new(card-item) {Color.GREEN}[GPU Texture: Incoming]{Color.CYAN}
{Color.RESET}""")


def simulate_layer_promotion_memory_tradeoff():
    print_header("SIMULASI 4: LAYER PROMOTION & GPU VRAM FOOTPRINT")
    print(f"{Color.WHITE}Analisis dampak over-promotion dengan `will-change: transform`:{Color.RESET}\n")

    element_counts = [10, 50, 200, 1000]
    element_w, element_h = 300, 200  # pixels
    bytes_per_pixel = 4  # RGBA 32-bit texture

    print(f"{Color.BOLD}{'Elements Promoted':<20} | {'VRAM Consumed':<18} | {'Compositor Health':<25}{Color.RESET}")
    print(f"{Color.GRAY}{'─' * 70}{Color.RESET}")

    for count in element_counts:
        vram_bytes = count * element_w * element_h * bytes_per_pixel
        vram_mb = vram_bytes / (1024 * 1024)

        if vram_mb < 15:
            health = f"{Color.GREEN}Optimal (High FPS){Color.RESET}"
        elif vram_mb < 70:
            health = f"{Color.YELLOW}Caution (Mobile Warning){Color.RESET}"
        else:
            health = f"{Color.RED}Severe VRAM Thrashing!{Color.RESET}"

        print(f"{count:<20} | {vram_mb:>8.2f} MB        | {health}")

    print(f"{Color.GRAY}{'─' * 70}{Color.RESET}")
    print(f"{Color.YELLOW}Rule of Thumb:{Color.RESET} Gunakan `will-change` hanya saat interaksi aktif, hapus setelah transisi usai!\n")


def run_interactive_menu():
    while True:
        print_header("BAB-07: COMPOSITOR-DRIVEN ANIMATIONS & MOTION LAB")
        print(f"{Color.WHITE}Pilih simulasi teknis untuk dieksekusi:{Color.RESET}")
        print(f"  {Color.CYAN}1.{Color.RESET} Pipeline Rendering Browser & Frame Budget (Layout vs Composite)")
        print(f"  {Color.CYAN}2.{Color.RESET} Motion System: Damped Harmonic Spring Physics")
        print(f"  {Color.CYAN}3.{Color.RESET} View Transitions API: Lifecycle & Pseudo-Tree Inspector")
        print(f"  {Color.CYAN}4.{Color.RESET} GPU Layer Promotion & VRAM Memory Trade-off")
        print(f"  {Color.CYAN}5.{Color.RESET} Jalankan Semua Simulasi Sekaligus")
        print(f"  {Color.CYAN}0.{Color.RESET} Keluar / Exit")
        print(f"{Color.GRAY}{'─' * 70}{Color.RESET}")

        try:
            choice = input(f"{Color.BOLD}Masukkan opsi [0-5]: {Color.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting lab...")
            break

        if choice == "1":
            simulate_rendering_pipeline()
        elif choice == "2":
            simulate_motion_spring_physics()
        elif choice == "3":
            simulate_view_transitions_lifecycle()
        elif choice == "4":
            simulate_layer_promotion_memory_tradeoff()
        elif choice == "5":
            simulate_rendering_pipeline()
            simulate_motion_spring_physics()
            simulate_view_transitions_lifecycle()
            simulate_layer_promotion_memory_tradeoff()
        elif choice == "0":
            print(f"\n{Color.GREEN}Lab selesai. Selamat belajar performa animasi CSS modern!{Color.RESET}\n")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid. Silakan coba lagi.{Color.RESET}")


def main():
    # Jika dipanggil tanpa TTY interaktif (misal via CI / runner), jalankan mode otomatis
    if not sys.stdin.isatty() or "--all" in sys.argv:
        simulate_rendering_pipeline()
        simulate_motion_spring_physics()
        simulate_view_transitions_lifecycle()
        simulate_layer_promotion_memory_tradeoff()
    else:
        run_interactive_menu()


if __name__ == "__main__":
    main()
