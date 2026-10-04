#!/usr/bin/env python3
"""
Flutter Deep Dive: Animation, Canvas, & Custom Painting Pipeline Simulation
===========================================================================
Simulates the Flutter rendering engine pipeline:
  Ticker/VSync -> AnimationController (Curves & Lerp) ->
  RenderCustomPaint (shouldRepaint check) -> PictureRecorder & Canvas (DisplayList) ->
  Compositor & Layer Tree -> Rasterizer (Virtual FrameBuffer).
"""

import math
import sys
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, List, Optional, Tuple


# ============================================================================
# ANSI Terminal Styling Utilities
# ============================================================================
class ANSI:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    MAGENTA = "\033[35m"
    BLUE = "\033[34m"
    BG_DARK = "\033[48;5;234m"
    CLEAR_LINE = "\033[2K"


# ============================================================================
# Math, Geometry & Curves Pipeline
# ============================================================================
@dataclass(frozen=True)
class Offset:
    dx: float
    dy: float

    def __add__(self, other: "Offset") -> "Offset":
        return Offset(self.dx + other.dx, self.dy + other.dy)


@dataclass(frozen=True)
class Size:
    width: float
    height: float


@dataclass(frozen=True)
class Rect:
    left: float
    top: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.left + self.width

    @property
    def bottom(self) -> float:
        return self.top + self.height

    def contains(self, offset: Offset) -> bool:
        return (self.left <= offset.dx < self.right) and (self.top <= offset.dy < self.bottom)


def lerp_double(a: float, b: float, t: float) -> float:
    """Linear interpolation between a and b at progress t."""
    return a + (b - a) * t


class Curves:
    """Mathematical easing curves matching Flutter's animation specifications."""
    @staticmethod
    def linear(t: float) -> float:
        return t

    @staticmethod
    def ease_in_out(t: float) -> float:
        return -0.5 * (math.cos(math.pi * t) - 1.0)

    @staticmethod
    def bounce_out(t: float) -> float:
        if t < (1.0 / 2.75):
            return 7.5625 * t * t
        elif t < (2.0 / 2.75):
            t -= 1.5 / 2.75
            return 7.5625 * t * t + 0.75
        elif t < (2.5 / 2.75):
            t -= 2.25 / 2.75
            return 7.5625 * t * t + 0.9375
        else:
            t -= 2.625 / 2.75
            return 7.5625 * t * t + 0.984375


# ============================================================================
# Canvas & DisplayList Command Recording (Skia / Impeller Mock)
# ============================================================================
class DrawOpType(Enum):
    DRAW_RECT = "DrawRect"
    DRAW_CIRCLE = "DrawCircle"
    DRAW_LINE = "DrawLine"
    CLIP_RECT = "ClipRect"


@dataclass
class DrawCommand:
    op_type: DrawOpType
    params: dict
    paint_char: str


class PictureRecorder:
    """Records graphics operations into an immutable DisplayList."""
    def __init__(self):
        self.commands: List[DrawCommand] = []

    def record(self, cmd: DrawCommand):
        self.commands.append(cmd)

    def end_recording(self) -> List[DrawCommand]:
        display_list = list(self.commands)
        self.commands.clear()
        return display_list


class Canvas:
    """Flutter-like drawing canvas recording draw operations."""
    def __init__(self, recorder: PictureRecorder):
        self._recorder = recorder

    def draw_rect(self, rect: Rect, glyph: str = "█"):
        self._recorder.record(DrawCommand(
            op_type=DrawOpType.DRAW_RECT,
            params={"rect": rect},
            paint_char=glyph
        ))

    def draw_circle(self, center: Offset, radius: float, glyph: str = "●"):
        self._recorder.record(DrawCommand(
            op_type=DrawOpType.DRAW_CIRCLE,
            params={"center": center, "radius": radius},
            paint_char=glyph
        ))

    def draw_line(self, p1: Offset, p2: Offset, glyph: str = "─"):
        self._recorder.record(DrawCommand(
            op_type=DrawOpType.DRAW_LINE,
            params={"p1": p1, "p2": p2},
            paint_char=glyph
        ))


# ============================================================================
# CustomPainter Abstraction
# ============================================================================
class CustomPainter:
    """Base interface mirror to Flutter's CustomPainter."""
    def paint(self, canvas: Canvas, size: Size):
        raise NotImplementedError

    def should_repaint(self, old_delegate: "CustomPainter") -> bool:
        raise NotImplementedError


class RadarScannerPainter(CustomPainter):
    """
    Concrete CustomPainter simulating a radar sweep, orbiting target,
    and bounding boundaries.
    """
    def __init__(self, progress: float, sweep_angle: float):
        self.progress = progress
        self.sweep_angle = sweep_angle

    def paint(self, canvas: Canvas, size: Size):
        center = Offset(size.width / 2.0, size.height / 2.0)
        radius = min(size.width, size.height) * 0.42

        # 1. Background boundary box
        canvas.draw_rect(Rect(0, 0, size.width, size.height), glyph="·")

        # 2. Outer Radar Horizon (Circle Approximation)
        canvas.draw_circle(center, radius, glyph="○")

        # 3. Scanning Ray
        ray_x = center.dx + (radius * 0.9) * math.cos(self.sweep_angle)
        ray_y = center.dy + (radius * 0.9) * math.sin(self.sweep_angle)
        canvas.draw_line(center, Offset(ray_x, ray_y), glyph="*")

        # 4. Moving Target (interpolated trajectory)
        target_dist = radius * (0.3 + 0.5 * math.sin(self.progress * math.pi))
        target_ang = self.sweep_angle - 0.7
        target_pos = Offset(
            center.dx + target_dist * math.cos(target_ang),
            center.dy + target_dist * math.sin(target_ang)
        )
        canvas.draw_circle(target_pos, radius=1.2, glyph="▲")

    def should_repaint(self, old_delegate: "CustomPainter") -> bool:
        if not isinstance(old_delegate, RadarScannerPainter):
            return True
        return (abs(self.progress - old_delegate.progress) > 1e-4 or
                abs(self.sweep_angle - old_delegate.sweep_angle) > 1e-4)


# ============================================================================
# Rasterizer & Virtual Compositing Engine
# ============================================================================
class VirtualRasterizer:
    """Rasterizes Skia-style DisplayLists to an ASCII FrameBuffer."""
    def __init__(self, size: Size):
        self.size = size
        self.cols = int(size.width)
        self.rows = int(size.height)

    def rasterize(self, display_list: List[DrawCommand]) -> List[str]:
        # Initialize empty frame buffer grid
        grid = [[" " for _ in range(self.cols)] for _ in range(self.rows)]

        for cmd in display_list:
            if cmd.op_type == DrawOpType.DRAW_RECT:
                rect: Rect = cmd.params["rect"]
                r_left = max(0, int(rect.left))
                r_top = max(0, int(rect.top))
                r_right = min(self.cols, int(rect.right))
                r_bottom = min(self.rows, int(rect.bottom))

                for y in range(r_top, r_bottom):
                    for x in range(r_left, r_right):
                        if y == r_top or y == r_bottom - 1 or x == r_left or x == r_right - 1:
                            grid[y][x] = cmd.paint_char

            elif cmd.op_type == DrawOpType.DRAW_CIRCLE:
                center: Offset = cmd.params["center"]
                rad = cmd.params["radius"]
                y_scale = 2.0  # Terminal font aspect ratio correction (height > width)

                for y in range(self.rows):
                    for x in range(self.cols):
                        dx = (x - center.dx)
                        dy = (y - center.dy) * y_scale
                        dist = math.sqrt(dx * dx + dy * dy)
                        if abs(dist - rad) < 0.8:
                            grid[y][x] = cmd.paint_char
                        elif rad <= 1.5 and dist <= rad:
                            grid[y][x] = cmd.paint_char

            elif cmd.op_type == DrawOpType.DRAW_LINE:
                p1: Offset = cmd.params["p1"]
                p2: Offset = cmd.params["p2"]
                # Bresenham-like linear sample
                steps = max(int(abs(p2.dx - p1.dx) + abs(p2.dy - p1.dy) * 2), 1)
                for step in range(steps + 1):
                    t = step / float(steps)
                    lx = int(lerp_double(p1.dx, p2.dx, t))
                    ly = int(lerp_double(p1.dy, p2.dy, t))
                    if 0 <= lx < self.cols and 0 <= ly < self.rows:
                        grid[ly][lx] = cmd.paint_char

        return ["".join(row) for row in grid]


# ============================================================================
# Engine Pipeline Execution & Driver Loop
# ============================================================================
class FlutterPipelineSimulator:
    def __init__(self, viewport_size: Size):
        self.size = viewport_size
        self.recorder = PictureRecorder()
        self.canvas = Canvas(self.recorder)
        self.rasterizer = VirtualRasterizer(viewport_size)
        self.cached_display_list: Optional[List[DrawCommand]] = None
        self.last_painter: Optional[CustomPainter] = None

    def render_frame(self, painter: CustomPainter) -> Tuple[List[str], dict]:
        """
        Executes Flutter's paint & compositing pipeline stages.
        Measures exact microsecond breakdown for performance diagnostics.
        """
        metrics = {"skipped_paint": False, "t_record_us": 0.0, "t_raster_us": 0.0}

        # Check RepaintBoundary / shouldRepaint optimization
        t0 = time.perf_counter()
        if self.last_painter is not None and not painter.should_repaint(self.last_painter):
            metrics["skipped_paint"] = True
            display_list = self.cached_display_list or []
        else:
            painter.paint(self.canvas, self.size)
            display_list = self.recorder.end_recording()
            self.cached_display_list = display_list
            self.last_painter = painter
        t1 = time.perf_counter()

        # Rasterize stage
        frame_buffer = self.rasterizer.rasterize(display_list)
        t2 = time.perf_counter()

        metrics["t_record_us"] = (t1 - t0) * 1_000_000.0
        metrics["t_raster_us"] = (t2 - t1) * 1_000_000.0
        metrics["display_list_size"] = len(display_list)
        return frame_buffer, metrics


def main():
    print(f"{ANSI.BOLD}{ANSI.CYAN}======================================================================{ANSI.RESET}")
    print(f"{ANSI.BOLD}{ANSI.CYAN} FLUTTER RENDERING PIPELINE: Canvas, Animation & CustomPaint Deep Dive{ANSI.RESET}")
    print(f"{ANSI.BOLD}{ANSI.CYAN}======================================================================{ANSI.RESET}\n")

    viewport = Size(width=48.0, height=18.0)
    pipeline = FlutterPipelineSimulator(viewport)

    total_ticks = 12
    fps_budget_ms = 16.666  # Standard 60 FPS Target (16.67ms frame budget)

    print(f"{ANSI.YELLOW}Simulating VSYNC ticks driving AnimationController with Curves.bounce_out...{ANSI.RESET}\n")

    for tick in range(total_ticks):
        # 1. Animation Timing & Controller Tick
        raw_t = tick / float(total_ticks - 1)
        curved_t = Curves.bounce_out(raw_t)
        sweep_angle = lerp_double(0.0, 2.0 * math.pi, raw_t)

        painter = RadarScannerPainter(progress=curved_t, sweep_angle=sweep_angle)

        # 2. Run Pipeline
        frame_lines, metrics = pipeline.render_frame(painter)
        frame_ms = (metrics["t_record_us"] + metrics["t_raster_us"]) / 1000.0
        budget_pct = (frame_ms / fps_budget_ms) * 100.0

        # 3. Output Telemetry Header
        status_color = ANSI.GREEN if frame_ms < fps_budget_ms else ANSI.RED
        print(f"{ANSI.BOLD}Frame {tick+1:02d}/{total_ticks:02d}{ANSI.RESET} | "
              f"Progress: {ANSI.CYAN}{curved_t:.3f}{ANSI.RESET} | "
              f"Ops: {ANSI.MAGENTA}{metrics['display_list_size']}{ANSI.RESET} | "
              f"Record: {metrics['t_record_us']:.1f}µs | "
              f"Raster: {metrics['t_raster_us']:.1f}µs | "
              f"Total: {status_color}{frame_ms:.3f}ms ({budget_pct:.1f}% budget){ANSI.RESET}")

        # 4. Print Ascii FrameBuffer with Boundary Border
        sys.stdout.write(f"{ANSI.BG_DARK}")
        for row in frame_lines:
            print(f"  │{row}│")
        sys.stdout.write(f"{ANSI.RESET}")
        print(f"  └{'─' * int(viewport.width)}┘\n")

    # Pipeline Repaint Check Demonstration (shouldRepaint = False scenario)
    print(f"{ANSI.BOLD}{ANSI.YELLOW}--- Repaint Boundary / shouldRepaint Isolation Test ---{ANSI.RESET}")
    static_painter = RadarScannerPainter(progress=1.0, sweep_angle=math.pi)
    _, m1 = pipeline.render_frame(static_painter)
    _, m2 = pipeline.render_frame(static_painter)  # Identical state

    print(f"First Pass  : Record: {m1['t_record_us']:.1f}µs, Skipped: {m1['skipped_paint']}")
    print(f"Second Pass : Record: {m2['t_record_us']:.1f}µs, Skipped: {ANSI.GREEN}{m2['skipped_paint']}{ANSI.RESET} "
          f"(Re-used DisplayList without re-recording)")

    print(f"\n{ANSI.BOLD}{ANSI.GREEN}✓ Custom painting pipeline test completed successfully.{ANSI.RESET}")


if __name__ == "__main__":
    main()