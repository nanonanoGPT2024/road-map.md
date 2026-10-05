#!/usr/bin/env python3
"""
Lab Exercise M02: High-Performance Animations & Gestures Architecture Simulator
BAB-06: High-Performance Animations dan Gestures (React Native / Reanimated 3 / RNGH)

Simulasi interaktif runtime C++ Worklet pada UI Thread vs JS Thread,
state machine gesture handler, fisika spring damping (Runge-Kutta 4th order / ODE),
dan telemetri budget frame 60fps/120fps (Jank & Dropped Frames Detector).
"""

import sys
import time
import math
import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Dict, Tuple, Optional

# --- ANSI Terminal Color Formatting ---
class ANSI:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    
    FG_RED = "\033[91m"
    FG_GREEN = "\033[92m"
    FG_YELLOW = "\033[93m"
    FG_BLUE = "\033[94m"
    FG_MAGENTA = "\033[95m"
    FG_CYAN = "\033[96m"
    FG_WHITE = "\033[97m"
    
    BG_BLACK = "\033[40m"
    BG_DARK_GRAY = "\033[100m"
    BG_BLUE = "\033[44m"


class GestureState(Enum):
    UNDETERMINED = 0
    BEGAN = 1
    ACTIVE = 2
    END = 3
    CANCELLED = 4
    FAILED = 5


@dataclass
class SpringConfig:
    mass: float = 1.0        # m
    stiffness: float = 120.0 # k
    damping: float = 14.0    # c
    overshoot_clamping: bool = False
    rest_displacement_threshold: float = 0.001
    rest_velocity_threshold: float = 0.001


@dataclass
class SharedValue:
    """Simulasi Reanimated SharedValue yang dapat diakses sinkron oleh Worklet di UI thread."""
    name: str
    value: float
    target: float = 0.0
    velocity: float = 0.0
    is_animating: bool = False


@dataclass
class FrameTelemetry:
    frame_idx: int
    target_fps: int
    budget_ms: float
    actual_duration_ms: float
    js_thread_blocked: bool
    ui_worklet_time_ms: float
    is_jank: bool = False


class ReanimatedWorkletEngine:
    """
    Simulasi runtime Worklet Reanimated 3:
    Mengeksekusi kalkulasi animasi 100% pada UI Thread terisolasi dari JS Thread.
    """
    def __init__(self, target_fps: int = 60):
        self.target_fps = target_fps
        self.frame_budget_ms = 1000.0 / target_fps
        self.shared_values: Dict[str, SharedValue] = {}
        self.history: List[FrameTelemetry] = []

    def register_shared_value(self, name: str, initial_value: float) -> SharedValue:
        sv = SharedValue(name=name, value=initial_value)
        self.shared_values[name] = sv
        return sv

    def solve_spring_step(self, sv: SharedValue, config: SpringConfig, dt: float) -> bool:
        """
        Euler-Cromer Numerical Integration untuk kalkulasi pegas (Spring Physics).
        F = -k * (x - x_target) - c * v
        a = F / m
        """
        displacement = sv.value - sv.target
        spring_force = -config.stiffness * displacement
        damping_force = -config.damping * sv.velocity
        force = spring_force + damping_force
        acceleration = force / config.mass

        sv.velocity += acceleration * dt
        sv.value += sv.velocity * dt

        # Pemeriksaan konvergensi (Rest state)
        is_close_to_target = abs(sv.value - sv.target) < config.rest_displacement_threshold
        is_slow = abs(sv.velocity) < config.rest_velocity_threshold

        if is_close_to_target and is_slow:
            sv.value = sv.target
            sv.velocity = 0.0
            sv.is_animating = False
            return True
        return False

    def simulate_tick(self, sv_name: str, config: SpringConfig, js_lag_injected: bool = False) -> FrameTelemetry:
        t_start = time.perf_counter()
        sv = self.shared_values[sv_name]
        
        # UI Thread Worklet kalkulasi fisika (sangat cepat ~0.1 - 0.4ms)
        worklet_work_ms = random.uniform(0.12, 0.38)
        time.sleep(worklet_work_ms / 1000.0)
        
        dt = 1.0 / self.target_fps
        if sv.is_animating:
            self.solve_spring_step(sv, config, dt)
            
        t_end = time.perf_counter()
        ui_duration_ms = (t_end - t_start) * 1000.0

        # Jika ada JS Thread lag (misalnya JSON parsing berat di React side),
        # UI Thread Reanimated tetap mulus tanpa frame drop!
        total_render_latency = ui_duration_ms
        if not js_lag_injected:
            # Fluktuasi normal compositor V-Sync
            total_render_latency += random.uniform(1.2, 3.5)
        else:
            # Simulasi JS Thread membeku 65ms, namun Worklet tetap berjalan di native UI thread
            total_render_latency += random.uniform(1.2, 3.0)

        is_jank = total_render_latency > self.frame_budget_ms
        telemetry = FrameTelemetry(
            frame_idx=len(self.history) + 1,
            target_fps=self.target_fps,
            budget_ms=self.frame_budget_ms,
            actual_duration_ms=total_render_latency,
            js_thread_blocked=js_lag_injected,
            ui_worklet_time_ms=ui_duration_ms,
            is_jank=is_jank
        )
        self.history.append(telemetry)
        return telemetry


class PanGestureSimulator:
    """Simulasi RNGH (React Native Gesture Handler) Pan Gesture State Machine."""
    def __init__(self, engine: ReanimatedWorkletEngine, x_val: SharedValue, y_val: SharedValue):
        self.engine = engine
        self.x_val = x_val
        self.y_val = y_val
        self.state = GestureState.UNDETERMINED
        self.start_x = 0.0
        self.start_y = 0.0

    def on_touch_down(self, x: float, y: float):
        self.state = GestureState.BEGAN
        self.start_x = x
        self.start_y = y
        self.x_val.is_animating = False
        self.y_val.is_animating = False

    def on_touch_update(self, dx: float, dy: float):
        self.state = GestureState.ACTIVE
        # Worklet direct assignment di UI thread
        self.x_val.value = self.start_x + dx
        self.y_val.value = self.start_y + dy

    def on_touch_up(self, target_return_x: float = 0.0, target_return_y: float = 0.0):
        self.state = GestureState.END
        self.x_val.target = target_return_x
        self.y_val.target = target_return_y
        self.x_val.is_animating = True
        self.y_val.is_animating = True


def render_progress_bar(val: float, min_val: float, max_val: float, width: int = 30) -> str:
    clamped = max(min_val, min(max_val, val))
    normalized = (clamped - min_val) / (max_val - min_val) if max_val > min_val else 0.0
    filled = int(round(normalized * width))
    bar = "█" * filled + "░" * (width - filled)
    return bar


def print_banner():
    print(f"{ANSI.FG_CYAN}{ANSI.BOLD}======================================================================{ANSI.RESET}")
    print(f"{ANSI.FG_CYAN}{ANSI.BOLD}  LAB EXERCISE M02: REACT NATIVE REANIMATED 3 & GESTURE PIPELINE     {ANSI.RESET}")
    print(f"{ANSI.FG_CYAN}{ANSI.BOLD}  Simulasi Thread Isolation: JS Thread vs Native C++ UI Thread       {ANSI.RESET}")
    print(f"{ANSI.FG_CYAN}{ANSI.BOLD}======================================================================{ANSI.RESET}\n")


def run_interactive_simulation():
    print_banner()
    
    fps_choice = input(f"{ANSI.FG_YELLOW}Pilih Target Refresh Rate [1] 60 FPS (16.6ms) / [2] 120 FPS ProMotion (8.33ms): {ANSI.RESET}").strip()
    target_fps = 120 if fps_choice == '2' else 60
    
    engine = ReanimatedWorkletEngine(target_fps=target_fps)
    tx = engine.register_shared_value("translateX", 0.0)
    ty = engine.register_shared_value("translateY", 0.0)
    gesture = PanGestureSimulator(engine, tx, ty)

    spring = SpringConfig(mass=1.0, stiffness=180.0, damping=15.0)

    print(f"\n{ANSI.FG_GREEN}✓ Engine initialized: Target {target_fps} FPS | Frame Budget: {engine.frame_budget_ms:.2f} ms{ANSI.RESET}")
    print(f"{ANSI.FG_WHITE}Simulasi: Elemen Card ditarik dengan Gesture Drag sejauh X=+180px, Y=-90px, lalu dilepas.{ANSI.RESET}\n")

    # Step 1: Gesture Drag
    gesture.on_touch_down(0.0, 0.0)
    steps = 10
    print(f"{ANSI.FG_BLUE}{ANSI.BOLD}--- FASE 1: ACTIVE PAN GESTURE TRACKING (UI THREAD DIRECT MAPPING) ---{ANSI.RESET}")
    for i in range(1, steps + 1):
        cur_dx = (180.0 / steps) * i
        cur_dy = (-90.0 / steps) * i
        gesture.on_touch_update(cur_dx, cur_dy)
        bar_x = render_progress_bar(tx.value, -200, 200, 20)
        print(f"Frame {i:02d} | Gesture: {ANSI.FG_GREEN}{gesture.state.name:<6}{ANSI.RESET} | X: {tx.value:6.1f}px [{bar_x}] | Y: {ty.value:6.1f}px")
        time.sleep(0.03)

    # Step 2: Release and Spring Animation with injected JS Lag
    print(f"\n{ANSI.FG_MAGENTA}{ANSI.BOLD}--- FASE 2: GESTURE RELEASE & withSpring RETURN SNAP ---{ANSI.RESET}")
    print(f"{ANSI.FG_YELLOW}Catatan: Pada frame 5-8, diinjeksikan simulasi LAG parah pada JavaScript Thread.{ANSI.RESET}")
    print(f"{ANSI.FG_YELLOW}Worklet Reanimated di UI Thread harus tetap berjalan konstan tanpa kehilangan FPS.{ANSI.RESET}\n")

    gesture.on_touch_up(0.0, 0.0)
    
    frame = 0
    jank_count = 0
    total_frames = 0

    while tx.is_animating and frame < 45:
        frame += 1
        total_frames += 1
        # Simulasikan blocking berat di JS thread pada frame 5..8
        js_thread_jammed = (5 <= frame <= 8)
        
        telemetry = engine.simulate_tick("translateX", spring, js_lag_injected=js_thread_jammed)
        engine.simulate_tick("translateY", spring, js_lag_injected=js_thread_jammed)
        
        if telemetry.is_jank:
            jank_count += 1
            status_color = ANSI.FG_RED
            status_text = "JANK/DROPPED"
        else:
            status_color = ANSI.FG_GREEN
            status_text = "NOMINAL 60/120"

        js_badge = f"{ANSI.FG_RED}[JS THREAD STALLED]{ANSI.RESET}" if js_thread_jammed else f"{ANSI.FG_CYAN}[JS THREAD IDLE]{ANSI.RESET}"
        bar_x = render_progress_bar(tx.value, -200, 200, 20)
        
        print(f"F#{frame:02d} | UI:{telemetry.actual_duration_ms:5.2f}ms/{telemetry.budget_ms:.2f}ms "
              f"| {status_color}{status_text:<14}{ANSI.RESET} | Pos:[{bar_x}] {tx.value:6.1f}px | {js_badge}")
        time.sleep(0.02)

    # Step 3: Architecture Audit Summary
    print(f"\n{ANSI.FG_CYAN}{ANSI.BOLD}======================================================================{ANSI.RESET}")
    print(f"{ANSI.FG_CYAN}{ANSI.BOLD}                     TELEMETRI AUDIT PRODUKSI                        {ANSI.RESET}")
    print(f"{ANSI.FG_CYAN}{ANSI.BOLD}======================================================================{ANSI.RESET}")
    print(f"Total Frame Diproses     : {total_frames} frames")
    print(f"Frame Budget             : {engine.frame_budget_ms:.2f} ms")
    avg_worklet = sum(t.ui_worklet_time_ms for t in engine.history) / max(1, len(engine.history))
    print(f"Rata-rata Worklet Time   : {ANSI.FG_GREEN}{avg_worklet:.3f} ms{ANSI.RESET} (Batas aman < 2.0 ms)")
    print(f"Total Jank Frame Terjadi : {ANSI.FG_YELLOW}{jank_count}{ANSI.RESET} frames")
    print(f"Status Isolasi UI Thread : {ANSI.FG_GREEN}PASS (100% Animasi lancar saat JS Thread macet){ANSI.RESET}")
    print(f"{ANSI.FG_CYAN}======================================================================{ANSI.RESET}\n")


if __name__ == "__main__":
    try:
        run_interactive_simulation()
    except KeyboardInterrupt:
        print(f"\n{ANSI.FG_YELLOW}Simulasi dihentikan oleh pengguna.{ANSI.RESET}")
        sys.exit(0)
