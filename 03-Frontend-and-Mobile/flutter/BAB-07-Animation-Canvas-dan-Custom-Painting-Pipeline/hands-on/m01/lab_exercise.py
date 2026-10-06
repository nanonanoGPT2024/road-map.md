#!/usr/bin/env python3
"""
Flutter Animation & Custom Painting Pipeline Technical Simulator
================================================================
Materi: BAB-07-Animation-Canvas-dan-Custom-Painting-Pipeline

Skrip mandiri ini mensimulasikan arsitektur internal Flutter Engine:
  1. Vsync & Ticker Binding (Scheduler)
  2. AnimationController, Curves, & Tween Interpolation
  3. CustomPainter Contract & RecordingCanvas (DisplayList generation)
  4. RepaintBoundary & Dirty Layer Caching
  5. Rasterization Pipeline (Skia/Impeller abstraction ke ASCII Canvas)
"""

import math
import os
import sys
import time
from typing import Callable, List, Optional, Tuple

# ==============================================================================
# ANSI Color Palette & Terminal Utilities
# ==============================================================================
class Ansi:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"

    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    BG_DARK = "\033[40m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"


def clear_screen() -> None:
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


# ==============================================================================
# Model Geometri & Math (Flutter Size, Offset, Rect)
# ==============================================================================
class Offset:
    def __init__(self, dx: float, dy: float) -> None:
        self.dx = dx
        self.dy = dy

    def __add__(self, other: "Offset") -> "Offset":
        return Offset(self.dx + other.dx, self.dy + other.dy)

    def __repr__(self) -> str:
        return f"Offset({self.dx:.1f}, {self.dy:.1f})"


class Size:
    def __init__(self, width: float, height: float) -> None:
        self.width = width
        self.height = height

    def __repr__(self) -> str:
        return f"Size({self.width}x{self.height})"


# ==============================================================================
# Curves & Tween Engine
# ==============================================================================
class Curves:
    @staticmethod
    def linear(t: float) -> float:
        return max(0.0, min(1.0, t))

    @staticmethod
    def ease_in_out(t: float) -> float:
        t = max(0.0, min(1.0, t))
        return t * t * (3.0 - 2.0 * t)

    @staticmethod
    def bounce_out(t: float) -> float:
        t = max(0.0, min(1.0, t))
        if t < (1 / 2.75):
            return 7.5625 * t * t
        elif t < (2 / 2.75):
            t -= 1.5 / 2.75
            return 7.5625 * t * t + 0.75
        elif t < (2.5 / 2.75):
            t -= 2.25 / 2.75
            return 7.5625 * t * t + 0.9375
        else:
            t -= 2.625 / 2.75
            return 7.5625 * t * t + 0.984375

    @staticmethod
    def elastic_out(t: float) -> float:
        t = max(0.0, min(1.0, t))
        if t == 0.0 or t == 1.0:
            return t
        p = 0.3
        s = p / 4.0
        return math.pow(2, -10 * t) * math.sin((t - s) * (2 * math.pi) / p) + 1.0


class Tween:
    def __init__(self, begin: float, end: float) -> None:
        self.begin = begin
        self.end = end

    def transform(self, t: float) -> float:
        return self.begin + (self.end - self.begin) * t


# ==============================================================================
# Ticker & AnimationController
# ==============================================================================
class AnimationStatus:
    DISMISSED = "dismissed"
    FORWARD = "forward"
    REVERSE = "reverse"
    COMPLETED = "completed"


class AnimationController:
    def __init__(self, duration_sec: float = 1.5) -> None:
        self.duration_sec = duration_sec
        self.value = 0.0
        self.status = AnimationStatus.DISMISSED
        self._listeners: List[Callable[[], None]] = []

    def add_listener(self, fn: Callable[[], None]) -> None:
        self._listeners.append(fn)

    def _notify(self) -> None:
        for fn in self._listeners:
            fn()

    def tick(self, delta_time: float) -> None:
        if self.status == AnimationStatus.FORWARD:
            delta_val = delta_time / self.duration_sec
            self.value += delta_val
            if self.value >= 1.0:
                self.value = 1.0
                self.status = AnimationStatus.COMPLETED
            self._notify()
        elif self.status == AnimationStatus.REVERSE:
            delta_val = delta_time / self.duration_sec
            self.value -= delta_val
            if self.value <= 0.0:
                self.value = 0.0
                self.status = AnimationStatus.DISMISSED
            self._notify()

    def forward(self) -> None:
        self.status = AnimationStatus.FORWARD

    def reverse(self) -> None:
        self.status = AnimationStatus.REVERSE

    def reset(self) -> None:
        self.value = 0.0
        self.status = AnimationStatus.DISMISSED
        self._notify()


# ==============================================================================
# RecordingCanvas & DisplayList (Skia/Impeller Command Buffer)
# ==============================================================================
class DrawCommand:
    def __init__(self, cmd_type: str, details: str) -> None:
        self.cmd_type = cmd_type
        self.details = details

    def __repr__(self) -> str:
        return f"{Ansi.CYAN}{self.cmd_type}{Ansi.RESET} -> {self.details}"


class TerminalCanvas:
    """Simulasi Canvas Skia/Impeller berbasis Grid Karakter Terminal."""

    def __init__(self, width: int = 50, height: int = 16) -> None:
        self.width = width
        self.height = height
        self.grid: List[List[str]] = [[" " for _ in range(width)] for _ in range(height)]
        self.display_list: List[DrawCommand] = []

    def clear(self) -> None:
        self.grid = [[" " for _ in range(self.width)] for _ in range(self.height)]
        self.display_list.clear()

    def draw_line(self, x0: int, y0: int, x1: int, y1: int, char: str = "━", color: str = Ansi.WHITE) -> None:
        self.display_list.append(DrawCommand("drawLine", f"({x0},{y0}) to ({x1},{y1})"))
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        x, y = x0, y0
        while True:
            if 0 <= x < self.width and 0 <= y < self.height:
                self.grid[y][x] = f"{color}{char}{Ansi.RESET}"
            if x == x1 and y == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy

    def draw_rect(self, x: int, y: int, w: int, h: int, color: str = Ansi.BLUE, title: str = "") -> None:
        self.display_list.append(DrawCommand("drawRect", f"pos=({x},{y}) size={w}x{h}"))
        for col in range(x, min(x + w, self.width)):
            if 0 <= y < self.height:
                self.grid[y][col] = f"{color}━{Ansi.RESET}"
            if 0 <= y + h - 1 < self.height:
                self.grid[y + h - 1][col] = f"{color}━{Ansi.RESET}"
        for row in range(y, min(y + h, self.height)):
            if 0 <= x < self.width:
                self.grid[row][x] = f"{color}┃{Ansi.RESET}"
            if 0 <= x + w - 1 < self.width:
                self.grid[row][x + w - 1] = f"{color}┃{Ansi.RESET}"
        if 0 <= x < self.width and 0 <= y < self.height:
            self.grid[y][x] = f"{color}┏{Ansi.RESET}"
        if 0 <= x + w - 1 < self.width and 0 <= y < self.height:
            self.grid[y][x + w - 1] = f"{color}┓{Ansi.RESET}"
        if 0 <= x < self.width and 0 <= y + h - 1 < self.height:
            self.grid[y + h - 1][x] = f"{color}┗{Ansi.RESET}"
        if 0 <= x + w - 1 < self.width and 0 <= y + h - 1 < self.height:
            self.grid[y + h - 1][x + w - 1] = f"{color}┛{Ansi.RESET}"

        if title and 0 <= y < self.height:
            for idx, ch in enumerate(title[: max(0, w - 4)]):
                if x + 2 + idx < self.width:
                    self.grid[y][x + 2 + idx] = f"{Ansi.BOLD}{color}{ch}{Ansi.RESET}"

    def draw_circle(self, cx: int, cy: int, radius: int, color: str = Ansi.YELLOW, fill: bool = False) -> None:
        self.display_list.append(DrawCommand("drawCircle", f"center=({cx},{cy}) r={radius}"))
        aspect = 2.0  # Terminal font aspect ratio correction
        for row in range(max(0, cy - radius), min(self.height, cy + radius + 1)):
            for col in range(max(0, int(cx - radius * aspect)), min(self.width, int(cx + radius * aspect) + 1)):
                dx = (col - cx) / aspect
                dy = row - cy
                dist = math.sqrt(dx * dx + dy * dy)
                if fill and dist <= radius:
                    self.grid[row][col] = f"{color}●{Ansi.RESET}"
                elif not fill and abs(dist - radius) < 0.6:
                    self.grid[row][col] = f"{color}○{Ansi.RESET}"

    def render_to_string(self) -> str:
        lines = []
        top_border = "┌" + "─" * self.width + "┐"
        bot_border = "└" + "─" * self.width + "┘"
        lines.append(f"{Ansi.DIM}{top_border}{Ansi.RESET}")
        for row in self.grid:
            lines.append(f"{Ansi.DIM}│{Ansi.RESET}" + "".join(row) + f"{Ansi.DIM}│{Ansi.RESET}")
        lines.append(f"{Ansi.DIM}{bot_border}{Ansi.RESET}")
        return "\n".join(lines)


# ==============================================================================
# CustomPainter Contract & RepaintBoundary
# ==============================================================================
class CustomPainter:
    """Mirip class CustomPainter di package:flutter/rendering.dart."""

    def paint(self, canvas: TerminalCanvas, size: Size) -> None:
        raise NotImplementedError

    def should_repaint(self, old_delegate: Optional["CustomPainter"]) -> bool:
        raise NotImplementedError


class PulseWavePainter(CustomPainter):
    def __init__(self, progress: float, curve_name: str = "ease_in_out") -> None:
        self.progress = progress
        self.curve_name = curve_name

    def should_repaint(self, old_delegate: Optional["CustomPainter"]) -> bool:
        if not isinstance(old_delegate, PulseWavePainter):
            return True
        return abs(self.progress - old_delegate.progress) > 0.001 or self.curve_name != old_delegate.curve_name

    def paint(self, canvas: TerminalCanvas, size: Size) -> None:
        # Background guide box
        canvas.draw_rect(2, 1, int(size.width - 4), int(size.height - 2), color=Ansi.BLUE, title=" CustomPaint Viewport ")

        # Animated Radius & Pulse via Tween
        radius_tween = Tween(begin=2.0, end=6.0)
        curr_radius = int(radius_tween.transform(self.progress))

        center_x = int(size.width // 2)
        center_y = int(size.height // 2)

        # Pulse outer ring
        canvas.draw_circle(center_x, center_y, curr_radius, color=Ansi.MAGENTA, fill=False)
        # Core inner circle
        canvas.draw_circle(center_x, center_y, max(1, curr_radius // 2), color=Ansi.YELLOW, fill=True)

        # Dynamic trajectory line
        end_x = int(center_x + (curr_radius * 2.0) * math.cos(self.progress * 2 * math.pi))
        end_y = int(center_y + curr_radius * math.sin(self.progress * 2 * math.pi))
        canvas.draw_line(center_x, center_y, end_x, end_y, char="·", color=Ansi.CYAN)


class RepaintBoundary:
    """Simulasi RenderRepaintBoundary: isolasi raster cache saat tidak dirty."""

    def __init__(self) -> None:
        self.cached_raster: Optional[str] = None
        self.paint_count = 0
        self.cache_hits = 0

    def paint_with_cache(self, painter: CustomPainter, old_painter: Optional[CustomPainter], canvas: TerminalCanvas, size: Size) -> Tuple[str, bool]:
        is_dirty = painter.should_repaint(old_painter)
        if is_dirty or self.cached_raster is None:
            self.paint_count += 1
            canvas.clear()
            painter.paint(canvas, size)
            self.cached_raster = canvas.render_to_string()
            return self.cached_raster, True
        else:
            self.cache_hits += 1
            return self.cached_raster, False


# ==============================================================================
# Modul Lab Interactive Showcase
# ==============================================================================
def demo_live_animation() -> None:
    clear_screen()
    print(f"{Ansi.BOLD}{Ansi.GREEN}=== 1. FLUTTER LIVE ANIMATION & CUSTOM PAINT SIMULATOR ==={Ansi.RESET}\n")
    print(f"{Ansi.CYAN}Memilih kurva transfer function (Curves):{Ansi.RESET}")
    print("  [1] Curves.linear")
    print("  [2] Curves.easeInOut (Default)")
    print("  [3] Curves.bounceOut")
    print("  [4] Curves.elasticOut")

    choice = input(f"\n{Ansi.YELLOW}Pilih kurva (1-4, default 2): {Ansi.RESET}").strip()
    curve_map = {
        "1": (Curves.linear, "linear"),
        "2": (Curves.ease_in_out, "easeInOut"),
        "3": (Curves.bounce_out, "bounceOut"),
        "4": (Curves.elastic_out, "elasticOut"),
    }
    curve_fn, curve_name = curve_map.get(choice, (Curves.ease_in_out, "easeInOut"))

    canvas = TerminalCanvas(width=48, height=14)
    boundary = RepaintBoundary()
    controller = AnimationController(duration_sec=1.2)
    controller.forward()

    prev_painter: Optional[PulseWavePainter] = None
    fps = 20
    dt = 1.0 / fps
    total_frames = int(fps * controller.duration_sec)

    print(f"\n{Ansi.BOLD}Memulai Render Loop VSync (60Hz -> {fps} FPS terminal rate)...{Ansi.RESET}")
    time.sleep(0.8)

    for frame_idx in range(total_frames + 1):
        clear_screen()
        # Transform nilai controller melalui Curve
        curved_t = curve_fn(controller.value)
        painter = PulseWavePainter(progress=curved_t, curve_name=curve_name)

        # Repaint boundary logic
        rendered_screen, was_repainted = boundary.paint_with_cache(
            painter, prev_painter, canvas, Size(canvas.width, canvas.height)
        )
        prev_painter = painter

        # Terminal Visual Output
        print(f"{Ansi.BOLD}{Ansi.CYAN}[Flutter Rendering Pipeline - BAB 07]{Ansi.RESET}")
        print(f"Status: {Ansi.YELLOW}{controller.status.upper()}{Ansi.RESET} | Curve: {Ansi.GREEN}{curve_name}{Ansi.RESET}")
        print(f"Frame: {frame_idx + 1}/{total_frames + 1} | Controller.value: {controller.value:.3f} | CurvedValue: {curved_t:.3f}")
        print(f"RepaintBoundary stats -> Repaints: {boundary.paint_count} | Cache Hits: {boundary.cache_hits}\n")

        print(rendered_screen)

        # Tampilkan DisplayList Skia Ops terakhir
        print(f"\n{Ansi.BOLD}Skia/Impeller DisplayList ({len(canvas.display_list)} Commands):{Ansi.RESET}")
        for cmd in canvas.display_list[:4]:
            print(f"  ⚡ {cmd}")

        controller.tick(dt)
        time.sleep(dt)

    print(f"\n{Ansi.GREEN}{Ansi.BOLD}✓ Animasi selesai dirender sempurna tanpa jank!{Ansi.RESET}")
    input(f"\nTekan [ENTER] untuk kembali ke menu...")


def demo_pipeline_stages() -> None:
    clear_screen()
    print(f"{Ansi.BOLD}{Ansi.CYAN}=== 2. FLUTTER ENGINE RENDERING PIPELINE BREAKDOWN ==={Ansi.RESET}\n")

    stages = [
        ("1. VSYNC Pulse (SchedulerBinding)", "Hardware timer mengirim sinyal 60/120Hz ke Engine C++ (Shell)."),
        ("2. Animate Phase (Ticker & Controller)", "Tick callback dieksekusi, memperbarui AnimatedValue & notifyListeners()."),
        ("3. Build Phase (Element Tree)", "Widget tree memanggil build() hanya pada AnimatedBuilder/CustomPaint terkait."),
        ("4. Layout Phase (RenderObject Tree)", "Ukuran constraints dikalkulasi (BoxConstraints.tight / loose)."),
        ("5. Compositing Bits & RepaintBoundary", "Pengecekan flag isRepaintBoundary & dirty state layer sebelum melukis."),
        ("6. Paint Phase (RecordingCanvas)", "CustomPainter.paint() mencatat command ke Picture/DisplayList memory buffer."),
        ("7. Composition & Layer Tree", "Render tree menghasilkan SceneGraph dari Layer (Transform, Clip, Texture)."),
        ("8. Rasterization Phase (Skia / Impeller)", "Engine GPU mentransformasikan DisplayList ke Pixel/Vulkan/Metal pipeline.")
    ]

    for title, desc in stages:
        print(f"{Ansi.BOLD}{Ansi.YELLOW}▶ {title}{Ansi.RESET}")
        print(f"   {Ansi.WHITE}{desc}{Ansi.RESET}")
        time.sleep(0.3)

    print(f"\n{Ansi.MAGENTA}Key Takeaway:{Ansi.RESET}")
    print(f"  • CustomPaint menghemat Build Phase karena tidak membuat Sub-Widget tree baru.")
    print(f"  • shouldRepaint() adalah penjaga efisiensi Paint Phase.")
    print(f"  • RepaintBoundary mengisolasi repaint sehingga parent widget tidak ikut di-rekam ulang.")
    input(f"\nTekan [ENTER] untuk kembali ke menu...")


def demo_repaint_boundary_benchmark() -> None:
    clear_screen()
    print(f"{Ansi.BOLD}{Ansi.YELLOW}=== 3. BENCHMARK: REPAINT BOUNDARY DIRTY CHECKING ==={Ansi.RESET}\n")
    print("Mensimulasikan 100 frame rendering di mana sebagian state tidak berubah.\n")

    canvas = TerminalCanvas(30, 10)
    boundary = RepaintBoundary()
    painter_static = PulseWavePainter(progress=0.5, curve_name="linear")

    start_time = time.time()
    for frame in range(100):
        # Setiap 5 frame baru ada perubahan state
        if frame % 5 == 0:
            current_painter = PulseWavePainter(progress=0.5 + (frame * 0.002), curve_name="linear")
        else:
            current_painter = painter_static

        boundary.paint_with_cache(
            current_painter,
            painter_static if frame > 0 else None,
            canvas,
            Size(30, 10),
        )

    duration_ms = (time.time() - start_time) * 1000

    print(f"Total Frames Disimulasikan: {Ansi.BOLD}100{Ansi.RESET}")
    print(f"Kalkulasi Paint Baru (Dirty) : {Ansi.RED}{boundary.paint_count}{Ansi.RESET} kali")
    print(f"Raster Diambil dari Cache    : {Ansi.GREEN}{boundary.cache_hits}{Ansi.RESET} kali ({boundary.cache_hits}% raster reused!)")
    print(f"Durasi Komputasi Simulasi   : {Ansi.CYAN}{duration_ms:.2f} ms{Ansi.RESET}")
    print(f"\n{Ansi.BOLD}{Ansi.GREEN}Kesimpulan Arsitektur:{Ansi.RESET}")
    print("Dengan RepaintBoundary, penghematan resource CPU/GPU recording mencapai ~80% saat state statis.")
    input(f"\nTekan [ENTER] untuk kembali ke menu...")


def demo_curves_graph() -> None:
    clear_screen()
    print(f"{Ansi.BOLD}{Ansi.MAGENTA}=== 4. CURVE VISUALIZER (ASCII TRANSFER FUNCTION) ==={Ansi.RESET}\n")

    curve_list = [
        ("Linear", Curves.linear),
        ("EaseInOut", Curves.ease_in_out),
        ("BounceOut", Curves.bounce_out),
        ("ElasticOut", Curves.elastic_out),
    ]

    steps = 25
    height = 8

    for name, fn in curve_list:
        print(f"{Ansi.BOLD}{Ansi.CYAN}Curve: {name}{Ansi.RESET}")
        grid = [[" " for _ in range(steps)] for _ in range(height)]
        for col in range(steps):
            t = col / (steps - 1)
            val = fn(t)
            # Map 0.0 - 1.0 to row height-1 down to 0
            row = int((1.0 - max(0.0, min(1.0, val))) * (height - 1))
            row = max(0, min(height - 1, row))
            grid[row][col] = f"{Ansi.YELLOW}*{Ansi.RESET}"

        for r in range(height):
            prefix = "1.0 " if r == 0 else ("0.0 " if r == height - 1 else "    ")
            print(f"{Ansi.DIM}{prefix}│{Ansi.RESET}" + "".join(grid[r]))
        print(f"{Ansi.DIM}    └" + "─" * steps + f" {Ansi.WHITE}t -> 1.0{Ansi.RESET}\n")

    input(f"Tekan [ENTER] untuk kembali ke menu...")


# ==============================================================================
# Interactive Main Entry Point
# ==============================================================================
def main() -> None:
    while True:
        clear_screen()
        print(f"{Ansi.BOLD}{Ansi.CYAN}================================================================{Ansi.RESET}")
        print(f"{Ansi.BOLD}{Ansi.CYAN}   FLUTTER ANIMATION & CUSTOM PAINTING PIPELINE LAB (BAB 07)    {Ansi.RESET}")
        print(f"{Ansi.BOLD}{Ansi.CYAN}================================================================{Ansi.RESET}")
        print(f"{Ansi.WHITE}Simulasi Teknis Internal Engine: Ticker, Controller, Canvas & Raster{Ansi.RESET}\n")
        print("Pilih modul praktikum:")
        print(f"  {Ansi.GREEN}[1]{Ansi.RESET} Live Animation & CustomPainter Renderer (Terminal DisplayList)")
        print(f"  {Ansi.GREEN}[2]{Ansi.RESET} Pipeline Breakdown: VSYNC hingga Skia/Impeller Raster")
        print(f"  {Ansi.GREEN}[3]{Ansi.RESET} RepaintBoundary & Dirty Cache Benchmark")
        print(f"  {Ansi.GREEN}[4]{Ansi.RESET} Kurva Transfer & Tween Interpolation Visualizer")
        print(f"  {Ansi.RED}[0]{Ansi.RESET} Keluar (Exit)")

        choice = input(f"\n{Ansi.YELLOW}Masukkan pilihan (0-4): {Ansi.RESET}").strip()

        if choice == "1":
            demo_live_animation()
        elif choice == "2":
            demo_pipeline_stages()
        elif choice == "3":
            demo_repaint_boundary_benchmark()
        elif choice == "4":
            demo_curves_graph()
        elif choice == "0":
            clear_screen()
            print(f"{Ansi.GREEN}Terima kasih! Pemahaman arsitektur rendering Flutter Anda siap diuji.{Ansi.RESET}")
            sys.exit(0)
        else:
            print(f"{Ansi.RED}Pilihan tidak valid.{Ansi.RESET}")
            time.sleep(1)


if __name__ == "__main__":
    main()
