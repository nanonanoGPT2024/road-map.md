#!/usr/bin/env python3
"""
SwiftUI Core Lab Exercise: Graphics, Metal Shaders & Advanced Animations
Bab 06: Graphics, Metal Shaders, & Advanced Animations (SwiftUI Engine Simulation)

Simulasi interaktif Python 3 tanpa dependensi eksternal yang memodelkan pipeline
grafis deklaratif SwiftUI, integrasi Metal Shaders (MSL distortion/color effect),
serta kalkulasi fisika Spring & Keyframe Timeline.
"""

import math
import sys
import time
from dataclasses import dataclass, field
from typing import Callable, List, Tuple


class ANSI:
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
    BG_DARK = "\033[48;5;234m"
    CLEAR = "\033[2J\033[H"


@dataclass
class Vector2:
    x: float
    y: float

    def __add__(self, other: "Vector2") -> "Vector2":
        return Vector2(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "Vector2") -> "Vector2":
        return Vector2(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: float) -> "Vector2":
        return Vector2(self.x * scalar, self.y * scalar)


@dataclass
class SpringConfig:
    mass: float = 1.0
    stiffness: float = 100.0
    damping: float = 10.0
    initial_velocity: float = 0.0

    @property
    def damping_ratio(self) -> float:
        critical_damping = 2.0 * math.sqrt(self.mass * self.stiffness)
        return self.damping / critical_damping if critical_damping > 0 else 0.0

    @property
    def natural_frequency(self) -> float:
        return math.sqrt(self.stiffness / self.mass)


class SpringSimulation:
    """Simulasi analitis kurva SwiftUI .spring() / .snappy() / .bouncy()"""

    def __init__(self, config: SpringConfig, target: float = 1.0):
        self.config = config
        self.target = target

    def evaluate(self, t: float) -> Tuple[float, float]:
        """Menghitung posisi x(t) dan kecepatan v(t) pada detik t."""
        zeta = self.config.damping_ratio
        omega_n = self.config.natural_frequency
        x0 = -self.target
        v0 = self.config.initial_velocity

        if zeta < 1.0:
            # Underdamped (bouncy)
            omega_d = omega_n * math.sqrt(1.0 - zeta * zeta)
            decay = math.exp(-zeta * omega_n * t)
            a = x0
            b = (v0 + zeta * omega_n * x0) / omega_d
            pos = self.target + decay * (a * math.cos(omega_d * t) + b * math.sin(omega_d * t))
            vel = decay * (
                (-zeta * omega_n * (a * math.cos(omega_d * t) + b * math.sin(omega_d * t)))
                + (-a * omega_d * math.sin(omega_d * t) + b * omega_d * math.cos(omega_d * t))
            )
            return pos, vel
        elif math.isclose(zeta, 1.0, rel_tol=1e-4):
            # Critically damped
            decay = math.exp(-omega_n * t)
            c1 = x0
            c2 = v0 + omega_n * x0
            pos = self.target + decay * (c1 + c2 * t)
            vel = decay * (c2 - omega_n * (c1 + c2 * t))
            return pos, vel
        else:
            # Overdamped
            gamma1 = -omega_n * (zeta - math.sqrt(zeta * zeta - 1.0))
            gamma2 = -omega_n * (zeta + math.sqrt(zeta * zeta - 1.0))
            c2 = (v0 - gamma1 * x0) / (gamma2 - gamma1)
            c1 = x0 - c2
            pos = self.target + c1 * math.exp(gamma1 * t) + c2 * math.exp(gamma2 * t)
            vel = c1 * gamma1 * math.exp(gamma1 * t) + c2 * gamma2 * math.exp(gamma2 * t)
            return pos, vel


@dataclass
class Keyframe:
    time: float
    value: float
    curve: str = "linear"


class KeyframeAnimator:
    """Emulasi SwiftUI KeyframeAnimator & TimelineView interpolation."""

    def __init__(self, keyframes: List[Keyframe]):
        self.keyframes = sorted(keyframes, key=lambda k: k.time)

    def sample(self, t: float) -> float:
        if not self.keyframes:
            return 0.0
        if t <= self.keyframes[0].time:
            return self.keyframes[0].value
        if t >= self.keyframes[-1].time:
            return self.keyframes[-1].value

        for i in range(len(self.keyframes) - 1):
            k1 = self.keyframes[i]
            k2 = self.keyframes[i + 1]
            if k1.time <= t <= k2.time:
                span = k2.time - k1.time
                progress = (t - k1.time) / span if span > 0 else 0.0

                if k2.curve == "cubic":
                    # Smooth cubic hermite curve (3t^2 - 2t^3)
                    factor = progress * progress * (3.0 - 2.0 * progress)
                elif k2.curve == "ease_in":
                    factor = progress * progress
                elif k2.curve == "ease_out":
                    factor = 1.0 - (1.0 - progress) * (1.0 - progress)
                else:
                    factor = progress
                return k1.value + (k2.value - k1.value) * factor
        return self.keyframes[-1].value


class MetalShaderSimulator:
    """
    Simulasi MSL (Metal Shading Language) fragment function untuk SwiftUI:
    [[stitchable]] half4 rippleDistortion(float2 position, half4 color, float2 origin, float time)
    """

    @staticmethod
    def ripple_shader(x: float, y: float, origin_x: float, origin_y: float, time_val: float) -> Tuple[float, float, float]:
        dx = x - origin_x
        dy = y - origin_y
        dist = math.sqrt(dx * dx + dy * dy)
        frequency = 12.0
        wave_speed = 4.0
        attenuation = math.exp(-dist * 1.8)

        ripple = math.sin(dist * frequency - time_val * wave_speed) * attenuation
        norm_r = min(1.0, max(0.0, 0.2 + ripple * 0.8))
        norm_g = min(1.0, max(0.0, 0.4 + ripple * 0.6 + math.cos(time_val) * 0.2))
        norm_b = min(1.0, max(0.0, 0.8 + ripple * 0.5))
        return norm_r, norm_g, norm_b

    @staticmethod
    def render_canvas(width: int = 40, height: int = 15, time_val: float = 0.0) -> List[str]:
        lines = []
        center_x = 0.5
        center_y = 0.5
        chars = " .:-=+*#%@"

        for row in range(height):
            line_parts = []
            for col in range(width):
                u = col / float(width - 1)
                v = row / float(height - 1)
                r, g, b = MetalShaderSimulator.ripple_shader(u, v, center_x, center_y, time_val)
                intensity = (r * 0.299 + g * 0.587 + b * 0.114)
                char_idx = int(intensity * (len(chars) - 1))
                char_idx = max(0, min(len(chars) - 1, char_idx))
                symbol = chars[char_idx]

                # Convert to ANSI RGB color
                ir = int(r * 255)
                ig = int(g * 255)
                ib = int(b * 255)
                colored_char = f"\033[38;2;{ir};{ig};{ib}m{symbol}\033[0m"
                line_parts.append(colored_char)
            lines.append("".join(line_parts))
        return lines


@dataclass
class Particle:
    position: Vector2
    velocity: Vector2
    lifetime: float
    age: float = 0.0
    color_ansi: str = ANSI.CYAN

    @property
    def is_alive(self) -> bool:
        return self.age < self.lifetime

    @property
    def normalized_life(self) -> float:
        return min(1.0, self.age / self.lifetime) if self.lifetime > 0 else 1.0


class SwiftUIEmitterView:
    """Emulasi Particle System berbasis SwiftUI Canvas Context."""

    def __init__(self, width: int = 40, height: int = 12):
        self.width = width
        self.height = height
        self.particles: List[Particle] = []

    def spawn(self, origin: Vector2, count: int = 6):
        for i in range(count):
            angle = (math.pi * 2.0 / count) * i
            speed = 3.5 + 1.2 * math.cos(i * 1.5)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed * 0.5
            colors = [ANSI.RED, ANSI.YELLOW, ANSI.GREEN, ANSI.CYAN, ANSI.MAGENTA]
            p = Particle(
                position=Vector2(origin.x, origin.y),
                velocity=Vector2(vx, vy),
                lifetime=1.5,
                color_ansi=colors[i % len(colors)],
            )
            self.particles.append(p)

    def update(self, dt: float):
        gravity = Vector2(0.0, 1.8)
        alive = []
        for p in self.particles:
            p.age += dt
            if p.is_alive:
                p.velocity = p.velocity + gravity * dt
                p.position = p.position + p.velocity * dt
                alive.append(p)
        self.particles = alive

    def render(self) -> List[str]:
        grid = [[" " for _ in range(self.width)] for _ in range(self.height)]
        for p in self.particles:
            gx = int(p.position.x)
            gy = int(p.position.y)
            if 0 <= gx < self.width and 0 <= gy < self.height:
                alpha_char = "*" if p.normalized_life < 0.5 else "."
                grid[gy][gx] = f"{p.color_ansi}{alpha_char}{ANSI.RESET}"

        return ["".join(row) for row in grid]


def run_unit_tests() -> bool:
    """Verifikasi matematis deterministik dari model grafis dan fisika."""
    print(f"{ANSI.YELLOW}[TEST]{ANSI.RESET} Menjalankan Suite Verifikasi SwiftUI Engine...")

    # Test 1: Underdamped Spring Conservation & Overshoot
    cfg = SpringConfig(mass=1.0, stiffness=100.0, damping=4.0)
    spring = SpringSimulation(cfg, target=1.0)
    pos_0, _ = spring.evaluate(0.0)
    assert math.isclose(pos_0, 0.0, abs_tol=1e-5), f"T=0 pos should be 0, got {pos_0}"

    overshoot_found = False
    for step in range(1, 100):
        t = step * 0.02
        pos, _ = spring.evaluate(t)
        if pos > 1.05:
            overshoot_found = True
            break
    assert overshoot_found, "Spring underdamped harus memiliki efek overshoot (> 1.0)!"
    print(f"  {ANSI.GREEN}✓{ANSI.RESET} Spring Physics (underdamped overshoot) terverifikasi.")

    # Test 2: Keyframe Track Hermite Interpolation
    animator = KeyframeAnimator([
        Keyframe(time=0.0, value=0.0, curve="linear"),
        Keyframe(time=1.0, value=100.0, curve="cubic"),
        Keyframe(time=2.0, value=20.0, curve="linear"),
    ])
    assert math.isclose(animator.sample(0.0), 0.0)
    assert math.isclose(animator.sample(1.0), 100.0)
    assert math.isclose(animator.sample(2.0), 20.0)
    mid_val = animator.sample(0.5)
    assert math.isclose(mid_val, 50.0, abs_tol=1e-4), f"Cubic mid should be 50.0, got {mid_val}"
    print(f"  {ANSI.GREEN}✓{ANSI.RESET} Keyframe Interpolation (Hermite Cubic) terverifikasi.")

    # Test 3: Metal Shader Shader Bound Check
    for u in [0.0, 0.5, 1.0]:
        for v in [0.0, 0.5, 1.0]:
            r, g, b = MetalShaderSimulator.ripple_shader(u, v, 0.5, 0.5, 1.2)
            assert 0.0 <= r <= 1.0 and 0.0 <= g <= 1.0 and 0.0 <= b <= 1.0
    print(f"  {ANSI.GREEN}✓{ANSI.RESET} Metal Shader MSL Bound & Color Clamping terverifikasi.")

    # Test 4: Particle Emitter Lifecycle
    emitter = SwiftUIEmitterView(width=20, height=10)
    emitter.spawn(Vector2(10.0, 5.0), count=4)
    assert len(emitter.particles) == 4
    emitter.update(2.0)  # Exceeds lifetime 1.5s
    assert len(emitter.particles) == 0
    print(f"  {ANSI.GREEN}✓{ANSI.RESET} SwiftUI Canvas Particle Lifecycle terverifikasi.")
    print(f"{ANSI.GREEN}[PASS]{ANSI.RESET} Semua 4 pengujian fisika grafis berhasil 100%!\n")
    return True


def demo_spring_physics():
    print(f"\n{ANSI.BOLD}{ANSI.CYAN}--- DEMO 1: SwiftUI .spring() vs .bouncy() Trajectory ---{ANSI.RESET}")
    print("Membandingkan trajectory target 0.0 -> 1.0 pada terminal chart:")

    bouncy_cfg = SpringConfig(mass=1.0, stiffness=80.0, damping=5.0)  # zeta < 1.0
    smooth_cfg = SpringConfig(mass=1.0, stiffness=80.0, damping=18.0)  # critically damped approx

    sim_bouncy = SpringSimulation(bouncy_cfg, target=1.0)
    sim_smooth = SpringSimulation(smooth_cfg, target=1.0)

    print(f"{'Time':<6} | {'Bouncy (.bouncy)':<28} | {'Smooth (.smooth)':<28}")
    print("-" * 68)

    for i in range(25):
        t = i * 0.08
        pos_b, _ = sim_bouncy.evaluate(t)
        pos_s, _ = sim_smooth.evaluate(t)

        def make_bar(val: float, color: str) -> str:
            width = int(max(0.0, min(1.4, val)) * 18)
            bar = "█" * width
            return f"{color}{bar:<18}{ANSI.RESET} ({val:4.2f})"

        print(f"{t:4.2f}s | {make_bar(pos_b, ANSI.MAGENTA)} | {make_bar(pos_s, ANSI.CYAN)}")


def demo_metal_shader():
    print(f"\n{ANSI.BOLD}{ANSI.CYAN}--- DEMO 2: SwiftUI .distortionEffect / Metal Shader Emulation ---{ANSI.RESET}")
    print("Merender fragment shader ripple real-time (5 frame sampling):")

    for frame in range(5):
        sim_time = frame * 0.4
        print(f"\n{ANSI.YELLOW}[Frame {frame + 1}/5 | Time = {sim_time:.2f}s | MSL stitchable]{ANSI.RESET}")
        canvas_lines = MetalShaderSimulator.render_canvas(width=42, height=9, time_val=sim_time)
        border = f"{ANSI.DIM}+{'-' * 42}+{ANSI.RESET}"
        print(border)
        for line in canvas_lines:
            print(f"{ANSI.DIM}|{ANSI.RESET}{line}{ANSI.DIM}|{ANSI.RESET}")
        print(border)


def demo_particle_emitter():
    print(f"\n{ANSI.BOLD}{ANSI.CYAN}--- DEMO 3: SwiftUI Canvas Particle System ---{ANSI.RESET}")
    print("Menembakkan partikel dari pusat (20, 3) selama 6 ticks gravitasi:")

    emitter = SwiftUIEmitterView(width=42, height=8)
    emitter.spawn(Vector2(21.0, 2.0), count=10)

    for step in range(6):
        dt = 0.15
        emitter.update(dt)
        rendered_lines = emitter.render()
        print(f"{ANSI.DIM}Tick {step + 1} (Alive Particles: {len(emitter.particles)}):{ANSI.RESET}")
        for row in rendered_lines:
            print(f"|{row}|")


def print_banner():
    banner = f"""{ANSI.CYAN}{ANSI.BOLD}
========================================================================
   SWIFTUI CORE LAB: BAB 06 GRAPHICS, METAL & ADVANCED ANIMATIONS
========================================================================{ANSI.RESET}
{ANSI.WHITE}Model simulasi pipeline rendering SwiftUI deklaratif, Metal Shading
Language (stitchable functions), dan kalkulus fisika diferensial.{ANSI.RESET}
"""
    print(banner)


def main():
    print_banner()

    # Jalankan pengujian mandiri terlebih dahulu
    run_unit_tests()

    # Menu interaktif / eksekusi demonstrasi
    if len(sys.argv) > 1 and sys.argv[1] == "--test-only":
        sys.exit(0)

    demo_spring_physics()
    demo_metal_shader()
    demo_particle_emitter()

    print(f"\n{ANSI.GREEN}{ANSI.BOLD}[SUKSES] Seluruh simulasi Bab 06 Graphics & Metal selesai dieksekusi.{ANSI.RESET}\n")


if __name__ == "__main__":
    main()
