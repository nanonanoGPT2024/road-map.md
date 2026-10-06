#!/usr/bin/env python3
"""
Interactive Micro-Interactions & Motion Physics Simulator
BAB 07: Advanced Interaction Design, Micro-interactions, and Motion

Demonstrating:
1. Dan Saffer's 4-Part Micro-Interaction Model (Trigger, Rules, Feedback, Loops/Modes)
2. Easing Curves Visualization (Linear, Ease-In, Ease-Out, Ease-In-Out via Bezier)
3. Spring Physics Engine (Damped Harmonic Oscillator: Mass, Tension, Friction)
4. Motion Choreography & Staggered Feedback Orchestration
"""

import sys
import time
import math
from typing import Callable, List, Tuple

# ANSI Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"
BG_DARK = "\033[48;5;236m"


def print_banner(title: str, subtitle: str = "") -> None:
    print(f"\n{BOLD}{CYAN}{'=' * 68}{RESET}")
    print(f"{BOLD}{CYAN}  {title.center(64)}{RESET}")
    if subtitle:
        print(f"{DIM}  {subtitle.center(64)}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 68}{RESET}\n")


def draw_progress_bar(progress: float, width: int = 40, char: str = "█", color: str = GREEN) -> str:
    clamped = max(0.0, min(1.0, progress))
    filled = int(clamped * width)
    empty = width - filled
    pct = int(clamped * 100)
    return f"{color}{char * filled}{DIM}{'░' * empty}{RESET} {BOLD}{pct:3d}%{RESET}"


# --- 1. Easing Functions ---
def ease_linear(t: float) -> float:
    return t


def ease_in_quad(t: float) -> float:
    return t * t


def ease_out_quad(t: float) -> float:
    return t * (2 - t)


def ease_in_out_cubic(t: float) -> float:
    if t < 0.5:
        return 4 * t * t * t
    p = 2 * t - 2
    return 0.5 * p * p * p + 1


def cubic_bezier_approx(t: float, p1: float, p2: float) -> float:
    # 1D slice approximation for bezier curve (p0=0, p3=1)
    cx = 3.0 * p1
    bx = 3.0 * (p2 - p1) - cx
    ax = 1.0 - cx - bx
    return ((ax * t + bx) * t + cx) * t


def simulate_easing_curves() -> None:
    print_banner("1. TIMING & EASING CURVE COMPARISON", "Observing velocity profiles across 1000ms duration")
    curves: List[Tuple[str, Callable[[float], float], str]] = [
        ("Linear (Robotic / Raw)", ease_linear, RED),
        ("Ease-In (Gravity Acceleration)", ease_in_quad, YELLOW),
        ("Ease-Out (Natural Deceleration)", ease_out_quad, GREEN),
        ("Ease-In-Out (Smooth Organic)", ease_in_out_cubic, CYAN),
    ]

    steps = 25
    canvas_width = 45

    print(f"{BOLD}{'Curve':<32} | {'Trajectory (0.0 -> 1.0)':<{canvas_width}} | {'Final Value':<10}{RESET}")
    print("-" * 90)

    for name, func, col in curves:
        row = ["·"] * canvas_width
        for step in range(steps + 1):
            t = step / steps
            val = max(0.0, min(1.0, func(t)))
            pos = min(canvas_width - 1, int(val * (canvas_width - 1)))
            row[pos] = f"{col}●{RESET}"
        track = "".join(row)
        print(f"{col}{name:<32}{RESET} | {track} | {BOLD}{func(1.0):.2f}{RESET}")

    print(f"\n{DIM}Insight: Micro-interactions favor Ease-Out for incoming UI elements (feels instant){RESET}")
    print(f"{DIM}and Ease-In for exits (accelerating out of view).{RESET}\n")


# --- 2. Spring Physics Simulation ---
def simulate_spring_physics(mass: float = 1.0, stiffness: float = 120.0, damping: float = 14.0) -> None:
    print_banner(
        "2. SPRING DYNAMICS SIMULATION",
        f"Harmonic Oscillator (Mass: {mass}, Tension/k: {stiffness}, Friction/c: {damping})"
    )
    target = 1.0
    x = 0.0      # Current position
    v = 0.0      # Velocity
    dt = 0.02    # Time slice (20ms step, ~50 FPS)
    duration = 1.6
    total_steps = int(duration / dt)

    print(f"{BOLD}{'Time(s)':<8} | {'Displacement (x)':<18} | {'Visual Spring Gauge'}{RESET}")
    print("-" * 75)

    chart_width = 40
    for step in range(total_steps):
        # Force: F = -k * (x - target) - c * v
        force = -stiffness * (x - target) - damping * v
        a = force / mass
        v += a * dt
        x += v * dt
        elapsed = step * dt

        # Render spring position on a scale from 0.0 to 1.5
        pos_idx = int((x / 1.5) * chart_width)
        bar = [" "] * (chart_width + 5)
        target_idx = int((target / 1.5) * chart_width)
        bar[target_idx] = f"{DIM}│{RESET}"  # Target mark

        if 0 <= pos_idx < len(bar):
            bar[pos_idx] = f"{MAGENTA}◆{RESET}"

        gauge = "".join(bar)
        status = f"{GREEN}Overshoot!{RESET}" if x > target + 0.02 else (
            f"{YELLOW}Settle{RESET}" if abs(v) < 0.05 and abs(x - target) < 0.02 else f"{CYAN}Moving{RESET}"
        )
        if step % 2 == 0:  # Print sampled frames
            print(f"{elapsed:6.2f}s  | x: {x:+6.3f} (v: {v:+6.2f}) | [{gauge}] {status}")

    print(f"\n{GREEN}✔ Spring reached equilibrium at x ≈ {x:.3f} without abrupt snap cuts.{RESET}\n")


# --- 3. Dan Saffer's 4-Part Micro-Interaction Model ---
class MicroInteractionButton:
    """
    Simulates a Micro-interaction Lifecycle:
    1. Trigger: User Click / Touch Event
    2. Rules: Debounce limit, authentication state, rate limiting
    3. Feedback: Haptic pulse, visual state transitions, color morph
    4. Loops & Modes: Persistent toggled state, cooldown cycle
    """

    def __init__(self, label: str):
        self.label = label
        self.is_active = False
        self.click_count = 0
        self.cooldown_until = 0.0

    def trigger(self, trigger_type: str = "CLICK") -> None:
        print(f"\n{BOLD}{YELLOW}>> [1. TRIGGER]{RESET} Event: '{trigger_type}' triggered on '{self.label}'")
        now = time.time()

        # Rule evaluation
        print(f"{BOLD}{BLUE}>> [2. RULES]{RESET} Evaluating state machine preconditions...")
        if now < self.cooldown_until:
            print(f"   {RED}Rule Blocked:{RESET} Action on cooldown. Rate-limit active!")
            return

        self.click_count += 1
        self.is_active = not self.is_active
        self.cooldown_until = now + 0.8

        # Feedback generation
        print(f"{BOLD}{GREEN}>> [3. FEEDBACK]{RESET} Dispatching multi-modal response:")
        print(f"   • Haptic Pulse: {BOLD}{'Medium Impact (15ms)' if self.is_active else 'Light Notch (8ms)'}{RESET}")
        print(f"   • Sound Effect: {CYAN}{'pop_on.wav' if self.is_active else 'pop_off.wav'}{RESET}")
        print(f"   • Visual Morph: Transitioning to '{'ACTIVE / ON' if self.is_active else 'INACTIVE / OFF'}'")

        # Loops & Modes
        print(f"{BOLD}{MAGENTA}>> [4. LOOPS & MODES]{RESET} Long-term interaction loop state:")
        print(f"   • Mode: {'ACTIVE_STATE' if self.is_active else 'DEFAULT_STATE'}")
        print(f"   • Interaction Counter: {self.click_count}")
        print(f"   • Cooldown Window: 800ms protection active\n")


def simulate_micro_interaction_lifecycle() -> None:
    print_banner(
        "3. DAN SAFFER MICRO-INTERACTION LIFECYCLE",
        "Trigger -> Rules -> Feedback -> Loops & Modes"
    )
    btn = MicroInteractionButton("Bookmark / Favorite Toggle")
    btn.trigger("TAP_GESTURE")
    time.sleep(0.1)
    btn.trigger("RAPID_RE_TAP")  # Should demonstrate rule blocking
    time.sleep(0.9)
    btn.trigger("DELIBERATE_TAP")


# --- 4. Choreography & Staggered Transitions ---
def simulate_motion_choreography() -> None:
    print_banner(
        "4. MOTION CHOREOGRAPHY & STAGGERED REVEAL",
        "Orchestrating UI Card Entry with 80ms Stagger Delay"
    )
    cards = [
        "Card 1: User Profile Header",
        "Card 2: Analytics Summary KPI",
        "Card 3: Recent Transactions",
        "Card 4: Security Status Alert",
    ]
    stagger_delay = 0.08  # 80ms
    transition_frames = 12

    print(f"{BOLD}Choreographing entrance of {len(cards)} UI components:{RESET}\n")

    for idx, card in enumerate(cards):
        delay = idx * stagger_delay
        print(f"{BOLD}[T+{delay:4.2f}s]{RESET} {CYAN}{card}{RESET} starting spring entry...")
        for frame in range(1, transition_frames + 1):
            p = frame / transition_frames
            eased = ease_out_quad(p)
            bar = draw_progress_bar(eased, width=28, color=CYAN if idx % 2 == 0 else GREEN)
            sys.stdout.write(f"\r  └─ Animation: {bar}")
            sys.stdout.flush()
            time.sleep(0.015)
        print("  " + GREEN + "✓ Mounted (100% Opacity, Scale 1.0, Y-offset 0px)" + RESET)

    print(f"\n{GREEN}✔ Choreography finished: Hierarchy preserved without visual clutter.{RESET}\n")


def run_interactive_suite() -> None:
    print_banner(
        "ADVANCED INTERACTION DESIGN & MOTION LAB",
        "Hands-On Technical Demonstration for Module 01"
    )
    print(f"{BOLD}Available Demonstration Modules:{RESET}")
    print("  1. Easing Curves Trajectory (Linear vs Quad vs Cubic)")
    print("  2. Spring Physics Mechanics (Harmonic Oscillator)")
    print("  3. Dan Saffer 4-Part Micro-Interaction Model")
    print("  4. Motion Choreography & Stagger Staging")
    print("  5. Run Complete Demonstration Suite (All in sequence)")
    print("-" * 68)

    # In automated environments, run complete suite directly
    choice = "5"
    if sys.stdin.isatty():
        try:
            val = input(f"{BOLD}Enter selection [1-5] (default: 5): {RESET}").strip()
            if val in {"1", "2", "3", "4", "5"}:
                choice = val
        except (EOFError, KeyboardInterrupt):
            choice = "5"

    print(f"\n{BOLD}Executing Module Selection: {choice}...{RESET}\n")

    if choice == "1":
        simulate_easing_curves()
    elif choice == "2":
        simulate_spring_physics()
    elif choice == "3":
        simulate_micro_interaction_lifecycle()
    elif choice == "4":
        simulate_motion_choreography()
    else:
        simulate_easing_curves()
        simulate_spring_physics()
        simulate_micro_interaction_lifecycle()
        simulate_motion_choreography()

    print_banner("LAB EXECUTION COMPLETE", "Ready for advanced interaction prototyping")


if __name__ == "__main__":
    run_interactive_suite()
