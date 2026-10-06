#!/usr/bin/env python3
"""
Lab Exercise: React Native High-Performance Animations & Gestures Simulator
BAB 06: Reanimated 3 Worklets, JSI Direct Execution, and Gesture State Machines
"""

import sys
import time
import math
import random
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional

# ANSI Color Palette for Rich Terminal Interface
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    RESET = "\033[0m"
    BG_DARK = "\033[40m"

@dataclass
class SpringConfig:
    mass: float = 1.0
    stiffness: float = 100.0
    damping: float = 10.0
    initial_velocity: float = 0.0

@dataclass
class GestureState:
    UNDETERMINED: int = 0
    BEGAN: int = 1
    ACTIVE: int = 2
    END: int = 3
    CANCELLED: int = 4

    @classmethod
    def name(cls, state_code: int) -> str:
        names = {
            0: "UNDETERMINED",
            1: "BEGAN",
            2: "ACTIVE",
            3: "END",
            4: "CANCELLED"
        }
        return names.get(state_code, "UNKNOWN")

class AnimationEngineSimulator:
    """Simulates React Native Animated Bridge vs Reanimated UI Thread (Worklet) Execution."""

    def __init__(self):
        self.target_fps_60 = 16.666  # ms per frame
        self.target_fps_120 = 8.333  # ms per frame

    def simulate_bridge_overhead(self, frames: int = 30, js_load_ms: float = 18.5) -> List[Dict]:
        """
        Legacy React Native Animated API:
        Each frame tick crosses the asynchronous serialization bridge.
        If JS thread is congested, bridge lag causes dropped frames (jank).
        """
        results = []
        accumulated_time = 0.0

        for frame in range(1, frames + 1):
            # Frame jitter due to JSON serialization and JS single-thread bottleneck
            bridge_jitter = random.uniform(2.0, 9.5)
            # Simulated heavy JS operation (e.g. state management, parsing JSON)
            js_delay = js_load_ms if (frame % 4 == 0) else random.uniform(1.0, 5.0)
            total_frame_time = self.target_fps_60 + bridge_jitter + js_delay

            is_dropped = total_frame_time > (self.target_fps_60 * 1.5)
            accumulated_time += total_frame_time

            results.append({
                "frame": frame,
                "duration_ms": total_frame_time,
                "dropped": is_dropped,
                "thread": "JS_BRIDGE",
                "timestamp_ms": accumulated_time
            })
        return results

    def simulate_worklet_ui_thread(self, frames: int = 30) -> List[Dict]:
        """
        Reanimated 3 Worklet Engine:
        Runs synchronously on UI thread via JSI (JavaScript Interface),
        completely isolated from JS thread microtasks and congestions.
        """
        results = []
        accumulated_time = 0.0

        for frame in range(1, frames + 1):
            # Native UI thread scheduler jitter (extremely small)
            ui_jitter = random.uniform(-0.4, 0.6)
            total_frame_time = max(8.0, self.target_fps_60 + ui_jitter)

            is_dropped = total_frame_time > (self.target_fps_60 * 1.3)
            accumulated_time += total_frame_time

            results.append({
                "frame": frame,
                "duration_ms": total_frame_time,
                "dropped": is_dropped,
                "thread": "UI_NATIVE_WORKLET",
                "timestamp_ms": accumulated_time
            })
        return results

class SpringPhysicsSolver:
    """Analytic and numerical solver for Reanimated withSpring physics."""

    def __init__(self, config: SpringConfig):
        self.config = config

    def solve(self, start: float, target: float, duration_steps: int = 40, dt: float = 0.016) -> List[Tuple[float, float]]:
        """
        Numerically steps damped harmonic oscillator:
        F = -k * (x - target) - c * v
        a = F / m
        v = v + a * dt
        x = x + v * dt
        """
        x = start
        v = self.config.initial_velocity
        k = self.config.stiffness
        c = self.config.damping
        m = self.config.mass

        trajectory = []
        for _ in range(duration_steps):
            f_spring = -k * (x - target)
            f_damping = -c * v
            force = f_spring + f_damping
            acc = force / m
            v += acc * dt
            x += v * dt
            trajectory.append((x, v))
        return trajectory

class PanGestureSimulator:
    """Simulates RNGH (react-native-gesture-handler) Pan gesture lifecycle and decay."""

    def __init__(self):
        self.current_state = GestureState.UNDETERMINED
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.velocity_x = 0.0
        self.velocity_y = 0.0

    def trigger_lifecycle(self) -> List[Tuple[str, str, float, float]]:
        events = []
        # Step 1: Touch down
        self.current_state = GestureState.BEGAN
        events.append((GestureState.name(self.current_state), "Finger contact recognized", self.offset_x, self.velocity_x))

        # Step 2: Dragging
        self.current_state = GestureState.ACTIVE
        for i in range(1, 6):
            delta = i * 24.5 + random.uniform(-2.0, 3.0)
            self.offset_x += delta
            self.velocity_x = delta / 0.016  # pixels/sec
            events.append((GestureState.name(self.current_state), f"Pan update translation={self.offset_x:.1f}px", self.offset_x, self.velocity_x))

        # Step 3: Release
        self.current_state = GestureState.END
        events.append((GestureState.name(self.current_state), f"Finger lifted with fling velocity={self.velocity_x:.1f}px/s", self.offset_x, self.velocity_x))
        return events

def render_ascii_graph(values: List[float], min_val: float, max_val: float, width: int = 40) -> None:
    """Renders a simple ASCII trajectory in terminal."""
    val_range = max_val - min_val if max_val != min_val else 1.0
    for idx, val in enumerate(values):
        norm = (val - min_val) / val_range
        pos = int(norm * (width - 1))
        pos = max(0, min(width - 1, pos))
        line = [" "] * width
        line[pos] = "█"
        bar = "".join(line)
        print(f"  {Colors.CYAN}{idx:02d}{Colors.RESET} | {Colors.YELLOW}{bar}{Colors.RESET} ({val:6.2f})")

def run_thread_benchmark_demo():
    print(f"\n{Colors.BOLD}{Colors.HEADER}=== DEMO 1: REACT NATIVE THREADING ARCHITECTURE BENCHMARK ==={Colors.RESET}")
    print(f"{Colors.DIM}Comparing Legacy Bridge vs Reanimated UI Worklet with heavy JS workload.{Colors.RESET}\n")

    engine = AnimationEngineSimulator()
    legacy_frames = engine.simulate_bridge_overhead(frames=24, js_load_ms=28.0)
    worklet_frames = engine.simulate_worklet_ui_thread(frames=24)

    legacy_dropped = sum(1 for f in legacy_frames if f["dropped"])
    worklet_dropped = sum(1 for f in worklet_frames if f["dropped"])

    print(f"{Colors.BOLD}[1] Legacy Animated Bridge (JS Thread Dependent):{Colors.RESET}")
    for f in legacy_frames[:8]:
        status_color = Colors.RED if f["dropped"] else Colors.GREEN
        status_lbl = "DROPPED (JANK)" if f["dropped"] else "SMOOTH"
        print(f"  Frame {f['frame']:02d}: {f['duration_ms']:5.1f}ms | Status: {status_color}{status_lbl}{Colors.RESET}")
    print(f"  ... [Total Dropped: {Colors.RED}{legacy_dropped}/{len(legacy_frames)} frames{Colors.RESET}]")

    print(f"\n{Colors.BOLD}[2] Reanimated 3 UI Worklet (Direct UI Thread via JSI):{Colors.RESET}")
    for f in worklet_frames[:8]:
        status_color = Colors.RED if f["dropped"] else Colors.GREEN
        status_lbl = "DROPPED (JANK)" if f["dropped"] else "SMOOTH"
        print(f"  Frame {f['frame']:02d}: {f['duration_ms']:5.1f}ms | Status: {status_color}{status_lbl}{Colors.RESET}")
    print(f"  ... [Total Dropped: {Colors.GREEN}{worklet_dropped}/{len(worklet_frames)} frames{Colors.RESET}]")

    print(f"\n{Colors.CYAN}Summary:{Colors.RESET} UI Worklets bypass JavaScript Event Loop blocking completely,")
    print(f"guaranteeing consistent 60fps/120fps even when JS thread is 100% occupied.\n")

def run_spring_physics_demo():
    print(f"\n{Colors.BOLD}{Colors.HEADER}=== DEMO 2: REANIMATED withSpring PHYSICS SIMULATION ==={Colors.RESET}")
    print(f"{Colors.DIM}Simulating 2nd order damped oscillator: m*x'' + c*x' + k*(x - target) = 0{Colors.RESET}\n")

    cfg = SpringConfig(mass=1.0, stiffness=120.0, damping=12.0, initial_velocity=0.0)
    solver = SpringPhysicsSolver(cfg)
    start_pos = 0.0
    target_pos = 100.0
    trajectory = solver.solve(start=start_pos, target=target_pos, duration_steps=25)

    positions = [pos for pos, _ in trajectory]
    velocities = [vel for _, vel in trajectory]
    overshoot = max(positions) - target_pos

    print(f"{Colors.BOLD}Spring Parameters:{Colors.RESET} Mass={cfg.mass}, Stiffness={cfg.stiffness}, Damping={cfg.damping}")
    print(f"{Colors.BOLD}Displacement Plot (0.0 -> {target_pos:.1f}):{Colors.RESET}")
    render_ascii_graph(positions, min(positions), max(positions), width=35)

    print(f"\n{Colors.GREEN}Max Overshoot:{Colors.RESET} {overshoot:.2f}px (Spring bounce effect)")
    print(f"{Colors.GREEN}Final Settled Value:{Colors.RESET} {positions[-1]:.2f}px\n")

def run_gesture_lifecycle_demo():
    print(f"\n{Colors.BOLD}{Colors.HEADER}=== DEMO 3: GESTURE HANDLER STATE MACHINE & DECAY ==={Colors.RESET}")
    print(f"{Colors.DIM}Gesture.Pan() state transitions and momentum fling calculation.{Colors.RESET}\n")

    pan = PanGestureSimulator()
    lifecycle = pan.trigger_lifecycle()

    for state, desc, trans_x, vel_x in lifecycle:
        color = Colors.BLUE if state == "BEGAN" else (Colors.YELLOW if state == "ACTIVE" else Colors.GREEN)
        print(f"  State: {color}{state:13s}{Colors.RESET} | {desc} (vx: {vel_x:7.1f} px/s)")

    print(f"\n{Colors.BOLD}Decay Fling Simulation (Reanimated withDecay):{Colors.RESET}")
    current_x = lifecycle[-1][2]
    decay_velocity = lifecycle[-1][3]
    deceleration = 0.992

    decay_steps = []
    for step in range(12):
        current_x += decay_velocity * 0.016
        decay_velocity *= deceleration
        decay_steps.append(current_x)
        print(f"  Decay Step {step+1:02d}: Position = {Colors.CYAN}{current_x:6.1f}px{Colors.RESET} | Residual Velocity = {decay_velocity:6.1f}px/s")

    print(f"\n{Colors.GREEN}Gesture & Decay completed natively on UI thread.{Colors.RESET}\n")

def print_welcome_banner():
    banner = f"""
{Colors.CYAN}╔═══════════════════════════════════════════════════════════════════════════════╗
║         REACT NATIVE HIGH-PERFORMANCE ANIMATIONS & GESTURES LAB               ║
║                  BAB 06: Worklets, JSI, Spring & Gesture Engine               ║
╚═══════════════════════════════════════════════════════════════════════════════╝{Colors.RESET}
    """
    print(banner)

def main():
    print_welcome_banner()

    demos = [
        ("Architecture Benchmark (Bridge vs Reanimated UI Worklet)", run_thread_benchmark_demo),
        ("Physics Engine (withSpring damped harmonic oscillator)", run_spring_physics_demo),
        ("Gesture Handler State Machine (Gesture.Pan & withDecay)", run_gesture_lifecycle_demo)
    ]

    # Non-interactive batch execution fallback if stdin is closed or piped
    if not sys.stdin.isatty():
        print(f"{Colors.YELLOW}[Notice] Non-interactive environment detected. Executing all simulation pipelines...{Colors.RESET}\n")
        for title, fn in demos:
            fn()
        print(f"{Colors.BOLD}{Colors.GREEN}All React Native animation simulations executed successfully.{Colors.RESET}")
        return

    while True:
        print(f"{Colors.BOLD}Select Simulation Module:{Colors.RESET}")
        for idx, (title, _) in enumerate(demos, 1):
            print(f"  {Colors.CYAN}[{idx}]{Colors.RESET} {title}")
        print(f"  {Colors.CYAN}[4]{Colors.RESET} Run All Modules Sequentially")
        print(f"  {Colors.CYAN}[0]{Colors.RESET} Exit")

        try:
            choice = input(f"\n{Colors.BOLD}Enter choice (0-4): {Colors.RESET}").strip()
            if choice == "0":
                print(f"{Colors.GREEN}Terminating simulator. Happy coding!{Colors.RESET}")
                break
            elif choice in ("1", "2", "3"):
                demos[int(choice) - 1][1]()
            elif choice == "4":
                for _, fn in demos:
                    fn()
            else:
                print(f"{Colors.RED}Invalid option selected. Please enter 0, 1, 2, 3, or 4.{Colors.RESET}\n")
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Colors.GREEN}Exiting simulator.{Colors.RESET}")
            break

if __name__ == "__main__":
    main()
