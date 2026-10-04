#!/usr/bin/env python3
"""
Lab Hands-on: Compositor-Driven Animations, Motion Systems, dan View Transitions
Kategori: 03-Frontend-and-Mobile | Bab: 07 - Modul 02 Deep Dive

Skrip ini memodelkan arsitektur rendering engine browser modern (Blink/Chromium Compositor - 'cc'):
1. Pipeline Rendering: DOM Mutation -> Recalculate Style -> Layout (Reflow) -> Paint -> Composite.
2. Main-Thread Jank Simulation: Animasi non-composited (e.g., 'top', 'margin') vs Off-thread Composited ('transform').
3. Motion Physics System: Damped harmonic oscillator (Spring Physics) vs Cubic-Bezier curve parser.
4. View Transition Engine: State capture (old/new snapshot), layer-tree diffing, pseudo-element mapping.
"""

import sys
import time
import math
import random
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional

# --- ANSI Color Palette ---
CLR_RESET   = "\033[0m"
CLR_BOLD    = "\033[1m"
CLR_DIM     = "\033[2m"
CLR_RED     = "\033[31m"
CLR_GREEN   = "\033[32m"
CLR_YELLOW  = "\033[33m"
CLR_BLUE    = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN    = "\033[36m"
CLR_BG_RED  = "\033[41m"
CLR_BG_BLUE = "\033[44m"

FRAME_BUDGET_MS = 16.667  # 60 FPS Target (1000ms / 60)


@dataclass
class RenderFrame:
    frame_index: int
    style_recalc_ms: float
    layout_ms: float
    paint_ms: float
    composite_ms: float
    main_thread_blocked_ms: float
    is_compositor_thread: bool

    @property
    def total_main_time(self) -> float:
        return self.style_recalc_ms + self.layout_ms + self.paint_ms + self.main_thread_blocked_ms

    @property
    def total_frame_time(self) -> float:
        if self.is_compositor_thread:
            # Compositor thread hanya menjalankan commit & composite di GPU
            return self.composite_ms
        return self.total_main_time + self.composite_ms

    @property
    def dropped(self) -> bool:
        return self.total_frame_time > FRAME_BUDGET_MS


class SpringPhysics:
    """
    Simulasi Motion System: Damped Harmonic Oscillator.
    Formula: F = -k * (x - target) - c * v
    Digunakan oleh motion design systems (e.g., Framer Motion, UIKit, modern CSS linear() generation).
    """
    def __init__(self, mass: float = 1.0, stiffness: float = 180.0, damping: float = 12.0):
        self.mass = mass
        self.stiffness = stiffness
        self.damping = damping

    def evaluate(self, duration_s: float = 1.0, steps: int = 60) -> List[Tuple[float, float]]:
        dt = duration_s / steps
        target = 1.0
        pos = 0.0
        vel = 0.0
        trajectory = []

        for step in range(steps):
            t = step * dt
            # Hukum Newton II: a = F / m
            spring_force = -self.stiffness * (pos - target)
            damping_force = -self.damping * vel
            acc = (spring_force + damping_force) / self.mass

            vel += acc * dt
            pos += vel * dt
            trajectory.append((round(t, 3), round(pos, 4)))
            if abs(pos - target) < 0.001 and abs(vel) < 0.001:
                break
        return trajectory


class CubicBezier:
    """
    Pengevaluasi kurva cubic-bezier CSS standar (B1(t), B2(t), B3(t), B4(t))
    Memetakan t (progress waktu) ke nilai posisi menggunakan de Casteljau / Newton-Raphson approximation.
    """
    def __init__(self, p1x: float, p1y: float, p2x: float, p2y: float):
        self.p1x, self.p1y = p1x, p1y
        self.p2x, self.p2y = p2x, p2y

    def sample_x(self, t: float) -> float:
        return 3 * (1 - t)**2 * t * self.p1x + 3 * (1 - t) * t**2 * self.p2x + t**3

    def sample_y(self, t: float) -> float:
        return 3 * (1 - t)**2 * t * self.p1y + 3 * (1 - t) * t**2 * self.p2y + t**3

    def solve(self, x: float, epsilon: float = 1e-4) -> float:
        # Newton-Raphson iteration untuk menemukan nilai parameter t dari waktu x
        t = x
        for _ in range(8):
            current_x = self.sample_x(t)
            if abs(current_x - x) < epsilon:
                return self.sample_y(t)
            # Derivative approximation
            dx = (self.sample_x(t + 1e-5) - current_x) / 1e-5
            if abs(dx) < 1e-6:
                break
            t -= (current_x - x) / dx
        return self.sample_y(min(max(t, 0.0), 1.0))


class ChromiumCompositorSimulator:
    """
    Mensimulasikan Chrome/Blink Layer Tree dan Thread Architecture:
    - Main Thread: JS Event Loop, Style, Layout, Pre-Paint, Tile Worker.
    - Compositor Thread: Handle user input, scroll, transform/opacity animations, GPU draw calls.
    """
    def __init__(self):
        self.frames_main_bound: List[RenderFrame] = []
        self.frames_composited: List[RenderFrame] = []

    def simulate_animation_run(self, total_frames: int = 40):
        # Skenario 1: Animasi Main-Thread ('top' / 'left' / 'margin')
        # Skenario 2: Animasi Compositor-Thread ('transform: translate3d(...)')
        
        # Injeksi lag thread utama pada frame 15 sampai 25 (e.g. Garbage Collection / Heavy JS JSON parse)
        lag_window = range(15, 26)

        for i in range(total_frames):
            js_block = 0.0
            if i in lag_window:
                js_block = random.uniform(25.0, 48.0) # Main thread tersendat (jank)

            # 1. Main-Thread Driven Properties:
            # Perubahan pada geometri memicu: Recalc Style -> Layout -> Paint -> Composite
            style_ms = random.uniform(2.1, 4.2)
            layout_ms = random.uniform(6.0, 9.5)
            paint_ms = random.uniform(3.5, 7.0)
            comp_ms = random.uniform(0.8, 1.5)

            frame_main = RenderFrame(
                frame_index=i,
                style_recalc_ms=style_ms,
                layout_ms=layout_ms,
                paint_ms=paint_ms,
                composite_ms=comp_ms,
                main_thread_blocked_ms=js_block,
                is_compositor_thread=False
            )
            self.frames_main_bound.append(frame_main)

            # 2. Compositor-Driven Properties:
            # Menggunakan GPU Compositing Layer terpisah (Blink Paint Artifact Compositor).
            # Main thread bebas macet, Compositor Thread melakukan komputasi matriks 4x4 off-thread.
            frame_comp = RenderFrame(
                frame_index=i,
                style_recalc_ms=0.0,
                layout_ms=0.0,
                paint_ms=0.0,
                composite_ms=random.uniform(1.2, 3.8),
                main_thread_blocked_ms=js_block,
                is_compositor_thread=True
            )
            self.frames_composited.append(frame_comp)


class ViewTransitionSimulator:
    """
    Mensimulasikan mekanika W3C View Transitions API:
    ::view-transition
       └─ ::view-transition-group(name)
          └─ ::view-transition-image-pair(name)
             ├─ ::view-transition-old(name) -> Snapshot Old State
             └─ ::view-transition-new(name) -> Snapshot Live DOM State
    """
    def __init__(self, element_id: str):
        self.element_id = element_id

    def execute_transition(self, old_box: Dict[str, float], new_box: Dict[str, float]):
        # Hitung transform delta (FLIP: First, Last, Invert, Play)
        delta_x = old_box['x'] - new_box['x']
        delta_y = old_box['y'] - new_box['y']
        scale_x = old_box['width'] / new_box['width']
        scale_y = old_box['height'] / new_box['height']

        return {
            "pseudo_root": "::view-transition",
            "group": f"::view-transition-group({self.element_id})",
            "old_view": {
                "transform": f"translate({delta_x}px, {delta_y}px) scale({scale_x:.2f}, {scale_y:.2f})",
                "opacity_animation": "1.0 -> 0.0"
            },
            "new_view": {
                "transform": "translate(0px, 0px) scale(1.0, 1.0)",
                "opacity_animation": "0.0 -> 1.0"
            },
            "interpolated_matrix": [
                [scale_x, 0.0, delta_x],
                [0.0, scale_y, delta_y],
                [0.0, 0.0, 1.0]
            ]
        }


def print_header(title: str):
    print(f"\n{CLR_BOLD}{CLR_BLUE}================================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}  {title}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_BLUE}================================================================================{CLR_RESET}")


def run_compositor_benchmark():
    print_header("LAB BENCHMARK 1: PIPELINE RENDERING ENGINE & JANK ANALYSIS")
    print(f"{CLR_DIM}Target Budget: {FRAME_BUDGET_MS:.2f} ms/frame (60 FPS baseline). Simulasi blokade JS pada frame 15-25.{CLR_RESET}\n")

    sim = ChromiumCompositorSimulator()
    sim.simulate_animation_run(total_frames=35)

    print(f"{CLR_BOLD}{'FRAME':<6} | {'PIPELINE: NON-COMPOSITED (top/margin)':<38} | {'COMPOSITED (transform/GPU)':<26}{CLR_RESET}")
    print("-" * 80)

    dropped_main = 0
    dropped_comp = 0

    for idx in range(len(sim.frames_main_bound)):
        fm = sim.frames_main_bound[idx]
        fc = sim.frames_composited[idx]

        # Formatting Output Non-Composited
        status_m = f"{CLR_RED}DROP (Jank){CLR_RESET}" if fm.dropped else f"{CLR_GREEN}PASS (60fps){CLR_RESET}"
        if fm.dropped:
            dropped_main += 1

        # Formatting Output Composited
        status_c = f"{CLR_RED}DROP{CLR_RESET}" if fc.dropped else f"{CLR_GREEN}PASS (60fps){CLR_RESET}"
        if fc.dropped:
            dropped_comp += 1

        main_info = f"{fm.total_frame_time:5.1f}ms [{status_m}] (JS-Wait: {fm.main_thread_blocked_ms:4.1f}ms)"
        comp_info = f"{fc.total_frame_time:4.1f}ms [{status_c}]"

        # Highlight frame yang mengalami spike
        marker = f"{CLR_YELLOW}⚡{CLR_RESET}" if fm.main_thread_blocked_ms > 0 else " "
        print(f"#{fm.frame_index:<4} {marker} | {main_info:<48} | {comp_info}")

    print("-" * 80)
    print(f"{CLR_BOLD}Benchmark Summary:{CLR_RESET}")
    print(f"Non-Composited Frames Dropped : {CLR_RED}{dropped_main}/35 frames ({(dropped_main/35)*100:.1f}% JANK){CLR_RESET}")
    print(f"Composited Frames Dropped     : {CLR_GREEN}{dropped_comp}/35 frames ({(dropped_comp/35)*100:.1f}% JANK){CLR_RESET}")
    print(f"{CLR_CYAN}Kesimpulan Arsitektur: Compositor Thread berjalan independen dari Script/Style/Layout lifecycle.{CLR_RESET}")


def run_motion_system_lab():
    print_header("LAB SIMULATOR 2: MOTION SYSTEMS - HARMONIC SPRING VS CUBIC-BEZIER")

    # Inisialisasi model fisika
    spring = SpringPhysics(mass=1.0, stiffness=120.0, damping=10.0)
    spring_trajectory = spring.evaluate(duration_s=0.6, steps=15)

    # Inisialisasi Cubic Bezier (e.g., standard CSS ease-out: cubic-bezier(0.0, 0.0, 0.58, 1.0))
    bezier = CubicBezier(0.0, 0.0, 0.58, 1.0)

    print(f"{CLR_BOLD}{'TIME (s)':<10} | {'SPRING DYNAMICS (pos)':<25} | {'CUBIC-BEZIER EASE-OUT':<25} | {'VISUAL DELTA'}{CLR_RESET}")
    print("-" * 80)

    for t, pos_spring in spring_trajectory:
        pos_bezier = bezier.solve(t / 0.6)
        
        # Representasi visual bar kecil di terminal
        bar_len_s = int(max(0.0, min(pos_spring, 1.5)) * 15)
        bar_len_b = int(max(0.0, min(pos_bezier, 1.5)) * 15)
        
        diff = abs(pos_spring - pos_bezier)
        diff_str = f"{CLR_MAGENTA}Δ={diff:.3f}{CLR_RESET}"

        print(f"{t:<10.3f} | {pos_spring:<7.3f} {'[' + '='*bar_len_s + '>':<16} | {pos_bezier:<7.3f} {'[' + '#'*bar_len_b + '>':<16} | {diff_str}")

    print("-" * 80)
    print(f"{CLR_GREEN}✓ Spring physics menyediakan dynamic overshoot natural tanpa hard-coded deceleration curve.{CLR_RESET}")


def run_view_transitions_lab():
    print_header("LAB SIMULATOR 3: W3C VIEW TRANSITIONS PSEUDO-TREE & RECT DIFF")

    # State A: Thumbnail dalam katalog (misal grid card)
    state_a_rect = {"x": 45.0, "y": 120.0, "width": 80.0, "height": 80.0}
    # State B: Fullscreen modal dialog
    state_b_rect = {"x": 10.0, "y": 40.0, "width": 360.0, "height": 480.0}

    vt_engine = ViewTransitionSimulator(element_id="hero-banner")
    result = vt_engine.execute_transition(state_a_rect, state_b_rect)

    print(f"{CLR_BOLD}Elemen Target ID:{CLR_RESET} hero-banner")
    print(f"{CLR_BOLD}Struktur Pseudo-Element Tree Browser:{CLR_RESET}")
    print(f"  {CLR_CYAN}{result['pseudo_root']}{CLR_RESET}")
    print(f"   └── {CLR_YELLOW}{result['group']}{CLR_RESET}")
    print(f"        └── ::view-transition-image-pair(hero-banner)")
    print(f"             ├── ::view-transition-old(hero-banner) -> Transisi keluar")
    print(f"             └── ::view-transition-new(hero-banner) -> Transisi masuk")
    print()
    print(f"{CLR_BOLD}Kalkulasi Geometri Inversi FLIP (Off-Thread Compositor Transform):{CLR_RESET}")
    print(f"  • Matriks Snapshot Lama: {result['old_view']['transform']}")
    print(f"  • Animasi Opacity Snapshot: {result['old_view']['opacity_animation']}")
    print(f"  • Matriks Target Akhir : {result['new_view']['transform']}")
    print(f"  • Representasi Transform Matrix 3x3:")
    for row in result['interpolated_matrix']:
        print(f"      [ {row[0]:8.3f}, {row[1]:8.3f}, {row[2]:8.3f} ]")
    print()
    print(f"{CLR_GREEN}✓ Zero Main-Thread Relayout: Transisi halus di-render langsung oleh GPU Layer Compositor.{CLR_RESET}")


def main():
    start_time = time.time()
    print(f"{CLR_BG_BLUE}{CLR_BOLD} COMPOSITOR, MOTION SYSTEMS & VIEW TRANSITIONS DEEP DIVE {CLR_RESET}")
    
    run_compositor_benchmark()
    run_motion_system_lab()
    run_view_transitions_lab()

    elapsed = (time.time() - start_time) * 1000
    print(f"\n{CLR_BOLD}{CLR_GREEN}Semua simulasi pipeline rendering selesai dieksekusi dalam {elapsed:.2f} ms.{CLR_RESET}\n")


if __name__ == "__main__":
    main()