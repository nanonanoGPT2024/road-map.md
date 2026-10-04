#!/usr/bin/env python3
"""
Lab Hands-on: Flutter Multi-Platform Adaptive & Responsive Architecture
Bab: 03 - Multi-Platform Adaptive & Responsive Architecture (Modul 02 Deep Dive)

Deskripsi:
Skrip ini mensimulasikan Flutter Layout Pipeline, Breakpoint Classification,
BoxConstraints solver, serta Adaptive Widget Engine (Material 3 vs Cupertino)
tanpa dependensi eksternal. Mensimulasikan resize loop, device orientation,
dan transisi navigasi adaptif (BottomNav -> NavigationRail -> NavigationDrawer).
"""

import sys
import time
from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Dict, Optional, Tuple

# ==============================================================================
# ANSI Color Codes untuk Visualisasi Terminal
# ==============================================================================
class TerminalColor:
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
    BG_DARK = "\033[48;5;236m"


# ==============================================================================
# Domain Models: TargetPlatform & Breakpoints (Spesifikasi Material Design 3)
# ==============================================================================
class TargetPlatform(Enum):
    ANDROID = "android"
    IOS = "iOS"
    MACOS = "macOS"
    WINDOWS = "windows"
    LINUX = "linux"
    WEB = "web"

    @property
    def is_desktop(self) -> bool:
        return self in (TargetPlatform.MACOS, TargetPlatform.WINDOWS, TargetPlatform.LINUX)

    @property
    def is_apple(self) -> bool:
        return self in (TargetPlatform.IOS, TargetPlatform.MACOS)


class WindowWidthClass(Enum):
    COMPACT = auto()   # < 600dp: Phone portrait
    MEDIUM = auto()    # 600dp - 839dp: Tablets portrait, Foldables unfolded
    EXPANDED = auto()  # >= 840dp: Tablet landscape, Desktop, Web


@dataclass(frozen=True)
class Size:
    width: float
    height: float

    @property
    def aspect_ratio(self) -> float:
        return self.width / (self.height if self.height != 0 else 1.0)

    @property
    def is_landscape(self) -> bool:
        return self.width > self.height


# ==============================================================================
# Flutter BoxConstraints Core Engine Simulation
# "Constraints go down. Sizes go up. Parent sets position."
# ==============================================================================
@dataclass(frozen=True)
class BoxConstraints:
    min_width: float = 0.0
    max_width: float = float("inf")
    min_height: float = 0.0
    max_height: float = float("inf")

    def constrain_width(self, width: float) -> float:
        return max(self.min_width, min(width, self.max_width))

    def constrain_height(self, height: float) -> float:
        return max(self.min_height, min(height, self.max_height))

    def constrain(self, size: Size) -> Size:
        return Size(self.constrain_width(size.width), self.constrain_height(size.height))

    @property
    def is_tight(self) -> bool:
        return self.min_width >= self.max_width and self.min_height >= self.max_height

    @classmethod
    def tight(cls, size: Size) -> "BoxConstraints":
        return cls(size.width, size.width, size.height, size.height)

    @classmethod
    def loose(cls, size: Size) -> "BoxConstraints":
        return cls(0.0, size.width, 0.0, size.height)


@dataclass
class MediaQueryData:
    size: Size
    device_pixel_ratio: float
    platform: TargetPlatform
    text_scale_factor: float = 1.0

    @property
    def window_class(self) -> WindowWidthClass:
        """Kategorisasi breakpoint lebar layar standar Material 3."""
        if self.size.width < 600:
            return WindowWidthClass.COMPACT
        elif self.size.width < 840:
            return WindowWidthClass.MEDIUM
        return WindowWidthClass.EXPANDED


# ==============================================================================
# Virtual Widget Architecture & Adaptive Components
# ==============================================================================
class VirtualWidget:
    """Basis representasi Widget dalam hirarki pohon UI."""
    def render(self, context: MediaQueryData, constraints: BoxConstraints) -> Dict[str, any]:
        raise NotImplementedError


class AdaptiveScaffold(VirtualWidget):
    """
    Scaffold adaptif: Memilih Navigasi yang paling tepat berdasarkan
    Screen Size Breakpoint dan Platform Target.
    """
    def __init__(self, title: str, items_count: int):
        self.title = title
        self.items_count = items_count

    def render(self, context: MediaQueryData, constraints: BoxConstraints) -> Dict[str, any]:
        win_class = context.window_class
        platform = context.platform

        # 1. Resolusi Navigasi Berdasarkan Window Class
        if win_class == WindowWidthClass.COMPACT:
            nav_strategy = "BottomNavigationBar (Mobile Ergonomics)"
            nav_footprint = Size(constraints.max_width, 56.0)
            content_width = constraints.max_width
        elif win_class == WindowWidthClass.MEDIUM:
            nav_strategy = "NavigationRail (Compact Tablet/Foldable)"
            nav_footprint = Size(72.0, constraints.max_height)
            content_width = constraints.max_width - 72.0
        else:
            nav_strategy = "NavigationDrawer/PermanentSidebar (Large Desktop/Web)"
            nav_footprint = Size(256.0, constraints.max_height)
            content_width = constraints.max_width - 256.0

        # 2. Resolusi Styling: Cupertino (iOS/macOS) vs Material 3 (Android/Win/Linux/Web)
        ui_family = "Cupertino (Human Interface Guidelines)" if platform.is_apple else "Material 3 (Dynamic Color)"
        touch_target_min = 44.0 if platform.is_apple else 48.0
        input_modality = "Mouse/Keyboard (Hover State Enabled)" if platform.is_desktop else "Touch First (Haptic Feedback)"

        # 3. Dynamic Multi-column Layout Calculation
        column_count = 1
        if content_width >= 1200:
            column_count = 4
        elif content_width >= 800:
            column_count = 3
        elif content_width >= 600:
            column_count = 2

        col_gutter = 16.0
        total_gutter = col_gutter * (column_count - 1)
        card_width = (content_width - (col_gutter * 2) - total_gutter) / column_count

        return {
            "title": self.title,
            "window_class": win_class.name,
            "ui_family": ui_family,
            "touch_target_dp": touch_target_min,
            "input_modality": input_modality,
            "navigation_type": nav_strategy,
            "nav_footprint": nav_footprint,
            "content_width": content_width,
            "grid_columns": column_count,
            "card_width_calculated": round(card_width, 2)
        }


# ==============================================================================
# Pipeline Layout & Test Runner
# ==============================================================================
class FlutterAdaptiveLayoutTester:
    def __init__(self):
        self.test_scenarios = [
            ("Google Pixel 7 (Portrait)", Size(412, 915), 2.625, TargetPlatform.ANDROID),
            ("Google Pixel 7 (Landscape)", Size(915, 412), 2.625, TargetPlatform.ANDROID),
            ("Apple iPad Pro 11\" (Portrait)", Size(834, 1194), 2.0, TargetPlatform.IOS),
            ("Apple MacBook Pro 16\" (Windowed)", Size(1280, 800), 2.0, TargetPlatform.MACOS),
            ("Windows 11 Ultra-Wide Monitor", Size(2560, 1080), 1.0, TargetPlatform.WINDOWS),
        ]

    def run_tests(self):
        print(f"{TerminalColor.BOLD}{TerminalColor.CYAN}====================================================================")
        print("  FLUTTER ADAPTIVE & RESPONSIVE ARCHITECTURE LAB - ENGINE SIMULATION")
        print(f"===================================================================={TerminalColor.RESET}\n")

        for idx, (dev_name, size, dpr, platform) in enumerate(self.test_scenarios, 1):
            media_query = MediaQueryData(
                size=size,
                device_pixel_ratio=dpr,
                platform=platform
            )
            screen_constraints = BoxConstraints.tight(size)
            
            scaffold = AdaptiveScaffold(title="Catalog Dashboard", items_count=24)
            start_time = time.perf_counter()
            render_tree = scaffold.render(media_query, screen_constraints)
            duration_us = (time.perf_counter() - start_time) * 1_000_000

            self._print_scenario_result(idx, dev_name, media_query, render_tree, duration_us)
            time.sleep(0.05)

        self._print_architecture_summary()

    def _print_scenario_result(self, idx: int, dev_name: str, mq: MediaQueryData, res: Dict[str, any], duration: float):
        print(f"{TerminalColor.BOLD}{TerminalColor.YELLOW}[FRAME PIPELINE #{idx}] {dev_name}{TerminalColor.RESET}")
        print(f"  • Screen Physical: {int(mq.size.width * mq.device_pixel_ratio)}x{int(mq.size.height * mq.device_pixel_ratio)}px | "
              f"Logical DP: {mq.size.width}x{mq.size.height}dp (DPR: {mq.device_pixel_ratio})")
        print(f"  • Orientation: {'LANDSCAPE' if mq.size.is_landscape else 'PORTRAIT'} | "
              f"Material Breakpoint: {TerminalColor.MAGENTA}{res['window_class']}{TerminalColor.RESET}")
        print(f"  • Platform Target: {TerminalColor.CYAN}{mq.platform.value}{TerminalColor.RESET} -> Theme: {res['ui_family']}")
        print(f"  • Target Metric: Min Hit-Test DP: {res['touch_target_dp']}dp | Modality: {res['input_modality']}")
        print(f"  • Layout Resolution:")
        print(f"    - Navigation Engine : {TerminalColor.GREEN}{res['navigation_type']}{TerminalColor.RESET}")
        print(f"    - Main Viewport Dims: {res['content_width']}dp width available")
        print(f"    - Responsive Grid   : {res['grid_columns']} Columns (Calculated Card Width: {res['card_width_calculated']}dp)")
        print(f"  • Pipeline Latency : {TerminalColor.DIM}{duration:.2f} µs{TerminalColor.RESET}\n")

    def _print_architecture_summary(self):
        print(f"{TerminalColor.BOLD}{TerminalColor.CYAN}--- TECHNICAL ARCHITECTURAL SUMMARY ---{TerminalColor.RESET}")
        summary_text = (
            "1. Responsive vs Adaptive:\n"
            "   - Responsive adapts to screen real-estate changes (Geometry: Columns, Size, Overflow).\n"
            "   - Adaptive adapts to platform ecosystem expectations (Interaction: Touch/Mouse, HIG/Material).\n"
            "2. Layout Principle:\n"
            "   - Flutter passes un-negotiable tight constraints from the view root down to widgets.\n"
            "   - LayoutBuilder & MediaQuery determine canonical layouts without hardcoding device models.\n"
            "3. Structural Shift Thresholds:\n"
            "   - < 600dp (Compact): Bottom Bar avoids thumb reach stretch.\n"
            "   - 600-839dp (Medium): Rail saves vertical room on landscape tablets.\n"
            "   - >= 840dp (Expanded): Persistent Drawer utilizes expansive lateral space."
        )
        print(f"{TerminalColor.WHITE}{summary_text}{TerminalColor.RESET}")
        print(f"{TerminalColor.GREEN}{TerminalColor.BOLD}\n[SUCCESS] Engine simulation completed without layout exceptions.{TerminalColor.RESET}")


# ==============================================================================
# Entry Point
# ==============================================================================
if __name__ == "__main__":
    tester = FlutterAdaptiveLayoutTester()
    tester.run_tests()
    sys.exit(0)