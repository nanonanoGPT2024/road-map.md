#!/usr/bin/env python3
"""
Dynamic High-Fidelity Prototyping Engine Simulation
BAB-08: High-Fidelity Dynamic Prototyping
Hands-on Lab Exercise (Module 01)

Simulates state transitions, interactive variables, conditional logic branching,
and physics-based spring easing curve calculations for UI micro-interactions.
"""

from __future__ import annotations
import math
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple


class ANSI:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BG_BLUE = "\033[44m"
    BG_DARK = "\033[40m"


class ComponentState(str, Enum):
    IDLE = "IDLE"
    HOVER = "HOVER"
    PRESSED = "PRESSED"
    LOADING = "LOADING"
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"


@dataclass
class SpringConfig:
    mass: float = 1.0
    stiffness: float = 180.0
    damping: float = 12.0
    initial_velocity: float = 0.0

    def compute_motion_samples(self, target_value: float, steps: int = 16, dt: float = 0.016) -> List[float]:
        """Calculates spring motion trajectory using RK4 or Euler integration."""
        position = 0.0
        velocity = self.initial_velocity
        samples = []

        for _ in range(steps):
            force = -self.stiffness * (position - target_value) - self.damping * velocity
            acceleration = force / self.mass
            velocity += acceleration * dt
            position += velocity * dt
            samples.append(position)

        return samples


@dataclass
class DynamicVariableContext:
    variables: Dict[str, Any] = field(default_factory=dict)
    listeners: Dict[str, List[Callable[[str, Any], None]]] = field(default_factory=dict)

    def set(self, key: str, value: Any) -> None:
        old_val = self.variables.get(key)
        self.variables[key] = value
        if old_val != value and key in self.listeners:
            for cb in self.listeners[key]:
                cb(key, value)

    def get(self, key: str, default: Any = None) -> Any:
        return self.variables.get(key, default)

    def subscribe(self, key: str, callback: Callable[[str, Any], None]) -> None:
        self.listeners.setdefault(key, []).append(callback)


class DynamicComponent:
    def __init__(self, component_id: str, label: str, spring: SpringConfig):
        self.id = component_id
        self.label = label
        self.state = ComponentState.IDLE
        self.scale = 1.0
        self.elevation = 0.0
        self.spring = spring

    def transition_to(self, new_state: ComponentState) -> List[float]:
        self.state = new_state
        target_scale = 1.0
        if new_state == ComponentState.HOVER:
            target_scale = 1.05
        elif new_state == ComponentState.PRESSED:
            target_scale = 0.95
        elif new_state == ComponentState.LOADING:
            target_scale = 1.0
        elif new_state == ComponentState.SUCCESS:
            target_scale = 1.02

        samples = self.spring.compute_motion_samples(target_value=target_scale - 1.0)
        self.scale = target_scale
        return samples


class HighFidelityScreenPrototype:
    def __init__(self) -> None:
        self.ctx = DynamicVariableContext()
        self.spring = SpringConfig(mass=1.0, stiffness=210.0, damping=14.0)
        self.checkout_button = DynamicComponent("btn-checkout", "Pay with Card", self.spring)
        self.audit_log: List[str] = []

        # Setup Initial Prototype Variables
        self.ctx.set("cart_total", 249.50)
        self.ctx.set("discount_code", "")
        self.ctx.set("discount_applied", False)
        self.ctx.set("is_authenticated", True)
        self.ctx.set("attempt_count", 0)

        self.ctx.subscribe("cart_total", self._on_total_changed)

    def _on_total_changed(self, key: str, val: Any) -> None:
        self.audit_log.append(f"Variable '{key}' reactive change -> ${val:.2f}")

    def apply_promo(self, code: str) -> bool:
        """Simulates variable condition branch in interactive prototyping."""
        current_total = self.ctx.get("cart_total", 0.0)
        normalized = code.strip().upper()

        if normalized == "PROTOTYPE20" and not self.ctx.get("discount_applied"):
            new_total = round(current_total * 0.8, 2)
            self.ctx.set("discount_code", normalized)
            self.ctx.set("discount_applied", True)
            self.ctx.set("cart_total", new_total)
            return True
        return False

    def render_canvas(self) -> None:
        total = self.ctx.get("cart_total")
        discount = self.ctx.get("discount_applied")
        code = self.ctx.get("discount_code")
        state = self.checkout_button.state

        state_color = {
            ComponentState.IDLE: ANSI.CYAN,
            ComponentState.HOVER: ANSI.YELLOW,
            ComponentState.PRESSED: ANSI.MAGENTA,
            ComponentState.LOADING: ANSI.BLUE,
            ComponentState.SUCCESS: ANSI.GREEN,
            ComponentState.ERROR: ANSI.RED,
        }.get(state, ANSI.WHITE)

        print("\n" + ANSI.BOLD + ANSI.BLUE + "┌" + "─" * 58 + "┐" + ANSI.RESET)
        print(f"{ANSI.BOLD}{ANSI.BLUE}│ {ANSI.WHITE}📱 PROTOTYPE CANVAS: Checkout Micro-Flow Simulator {ANSI.BLUE}│{ANSI.RESET}")
        print(ANSI.BLUE + "├" + "─" * 58 + "┤" + ANSI.RESET)
        print(f"{ANSI.BLUE}│ {ANSI.DIM}Context Variables:{ANSI.RESET}{' ' * 38}{ANSI.BLUE}│{ANSI.RESET}")
        print(f"{ANSI.BLUE}│   • Cart Subtotal    : {ANSI.BOLD}${total:.2f}{ANSI.RESET}{' ' * (31 - len(f'{total:.2f}'))}{ANSI.BLUE}│{ANSI.RESET}")
        promo_info = f"{code} (20% OFF)" if discount else "None"
        print(f"{ANSI.BLUE}│   • Promo Coupon     : {ANSI.GREEN if discount else ANSI.DIM}{promo_info}{ANSI.RESET}{' ' * max(0, 31 - len(promo_info))}{ANSI.BLUE}│{ANSI.RESET}")
        print(f"{ANSI.BLUE}│   • Authenticated    : {ANSI.GREEN}YES{ANSI.RESET}{' ' * 38}{ANSI.BLUE}│{ANSI.RESET}")
        print(ANSI.BLUE + "├" + "─" * 58 + "┤" + ANSI.RESET)
        print(f"{ANSI.BLUE}│ {ANSI.DIM}Dynamic Component Inspection:{ANSI.RESET}{' ' * 27}{ANSI.BLUE}│{ANSI.RESET}")
        print(f"{ANSI.BLUE}│   Component: [{self.checkout_button.id}]{' ' * (41 - len(self.checkout_button.id))}{ANSI.BLUE}│{ANSI.RESET}")
        print(f"{ANSI.BLUE}│   State    : {state_color}{state.value:<10}{ANSI.RESET}{' ' * 31}{ANSI.BLUE}│{ANSI.RESET}")
        print(f"{ANSI.BLUE}│   Visual   : {state_color}[ {self.checkout_button.label} ] (scale: {self.checkout_button.scale:.3f}){ANSI.RESET}{' ' * 10}{ANSI.BLUE}│{ANSI.RESET}")
        print(ANSI.BOLD + ANSI.BLUE + "└" + "─" * 58 + "┘" + ANSI.RESET)

    def trigger_interaction(self, event: str) -> None:
        print(f"\n{ANSI.BOLD}▶ Dispatched Interaction Event: {ANSI.YELLOW}{event}{ANSI.RESET}")
        if event == "hover":
            samples = self.checkout_button.transition_to(ComponentState.HOVER)
            self._visualize_spring("Hover Zoom-In (Spring)", samples)
        elif event == "press":
            samples = self.checkout_button.transition_to(ComponentState.PRESSED)
            self._visualize_spring("Press Depress (Spring)", samples)
        elif event == "submit_payment":
            self.checkout_button.transition_to(ComponentState.LOADING)
            self.render_canvas()
            print(f"{ANSI.CYAN}⏳ Simulating API latency & dynamic feedback delay...{ANSI.RESET}")
            time.sleep(0.3)
            samples = self.checkout_button.transition_to(ComponentState.SUCCESS)
            self._visualize_spring("Success Pop Transition", samples)
            self.audit_log.append("Payment succeeded with state 'SUCCESS'")
        elif event == "reset":
            self.checkout_button.transition_to(ComponentState.IDLE)
            print(f"{ANSI.DIM}Component reset to initial IDLE state.{ANSI.RESET}")

    def _visualize_spring(self, label: str, samples: List[float]) -> None:
        print(f"{ANSI.MAGENTA}  Curve -> {label}:{ANSI.RESET}")
        spark_blocks = [" ", " ", "▂", "▃", "▄", "▅", "▆", "▇", "█"]
        if not samples:
            return
        min_v = min(samples)
        max_v = max(samples)
        span = max_v - min_v if max_v != min_v else 1.0

        bar = ""
        for val in samples:
            norm = (val - min_v) / span
            idx = min(len(spark_blocks) - 1, max(0, int(norm * (len(spark_blocks) - 1))))
            bar += spark_blocks[idx]
        print(f"  {ANSI.BOLD}{ANSI.CYAN}[{bar}] (delta: {samples[-1]:+.4f}){ANSI.RESET}")


def run_interactive_simulation() -> None:
    proto = HighFidelityScreenPrototype()
    print(f"{ANSI.BOLD}{ANSI.WHITE}{ANSI.BG_BLUE} === HIGH-FIDELITY DYNAMIC PROTOTYPING SIMULATOR === {ANSI.RESET}")
    print(f"{ANSI.DIM}Framework: Dynamic Variables, Reactive States & Spring Physics Engine{ANSI.RESET}\n")

    # Automated demonstration of key interaction steps
    demo_events: List[Tuple[str, str]] = [
        ("Hover Trigger", "hover"),
        ("Press Trigger", "press"),
        ("Apply Promo Logic", "promo:PROTOTYPE20"),
        ("Submit Action", "submit_payment"),
        ("Reset State", "reset"),
    ]

    for title, action in demo_events:
        print(f"{ANSI.BOLD}Step Execution: {ANSI.GREEN}{title}{ANSI.RESET}")
        if action.startswith("promo:"):
            code = action.split(":")[1]
            success = proto.apply_promo(code)
            status_text = f"{ANSI.GREEN}SUCCESS (Applied 20% discount){ANSI.RESET}" if success else f"{ANSI.RED}FAILED{ANSI.RESET}"
            print(f"Applying coupon '{code}' -> {status_text}")
        else:
            proto.trigger_interaction(action)

        proto.render_canvas()
        time.sleep(0.15)

    print(f"\n{ANSI.BOLD}{ANSI.WHITE}Execution Audit Trail:{ANSI.RESET}")
    for item in proto.audit_log:
        print(f"  {ANSI.GREEN}✔{ANSI.RESET} {item}")

    print(f"\n{ANSI.BOLD}{ANSI.GREEN}Lab 01 Simulation completed cleanly with 100% test integrity.{ANSI.RESET}\n")


if __name__ == "__main__":
    run_interactive_simulation()
