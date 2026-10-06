#!/usr/bin/env python3
"""
Interactive Terminal Simulator: Flutter Multi-Platform Adaptive & Responsive Architecture
Simulates Flutter's MediaQuery, LayoutBuilder, BoxConstraints, TargetPlatform adaptation,
and Breakpoint-driven responsive layouts in Python 3.
"""

import sys
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Dict, Tuple


# ANSI Color Codes for Rich Terminal Output
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    
    # Colors
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    MAGENTA = "\033[95m"
    WHITE = "\033[97m"
    BG_BLUE = "\033[44m"
    BG_CYAN = "\033[46m"
    BG_DARK = "\033[40m"


class TargetPlatform(Enum):
    ANDROID = "android"
    IOS = "ios"
    MACOS = "macos"
    WINDOWS = "windows"
    LINUX = "linux"
    WEB = "web"


class DeviceScreenType(Enum):
    COMPACT = "Compact (< 600dp) [Mobile Phone]"
    MEDIUM = "Medium (600dp - 839dp) [Tablet / Foldable]"
    EXPANDED = "Expanded (>= 840dp) [Desktop / Web Wide]"


@dataclass
class BoxConstraints:
    min_width: float
    max_width: float
    min_height: float
    max_height: float

    @property
    def is_tight(self) -> bool:
        return self.min_width >= self.max_width and self.min_height >= self.max_height

    @property
    def has_bounded_width(self) -> bool:
        return self.max_width < float('inf')

    def constrain_width(self, width: float) -> float:
        return max(self.min_width, min(width, self.max_width))


@dataclass
class MediaQueryData:
    size_width: float
    size_height: float
    device_pixel_ratio: float
    text_scale_factor: float
    padding_top: float  # Notch / Status Bar
    padding_bottom: float  # Navigation bar / Home indicator

    @property
    def screen_type(self) -> DeviceScreenType:
        if self.size_width < 600.0:
            return DeviceScreenType.COMPACT
        elif self.size_width < 840.0:
            return DeviceScreenType.MEDIUM
        else:
            return DeviceScreenType.EXPANDED


class FlutterLayoutEngineSimulator:
    """Simulates how Flutter widgets evaluate constraints and adapt to platform conventions."""

    def __init__(self):
        self.platform = TargetPlatform.ANDROID
        self.media_query = MediaQueryData(
            size_width=390.0,
            size_height=844.0,
            device_pixel_ratio=3.0,
            text_scale_factor=1.0,
            padding_top=47.0,
            padding_bottom=34.0,
        )

    def print_banner(self):
        print(f"\n{Style.BG_BLUE}{Style.WHITE}{Style.BOLD} === FLUTTER RESPONSIVE & ADAPTIVE ARCHITECTURE SIMULATOR === {Style.RESET}")
        print(f"{Style.DIM}Simulation of MediaQuery, LayoutBuilder, Adaptive Widgets & Platform Channels{Style.RESET}\n")

    def inspect_current_context(self):
        st = self.media_query.screen_type
        print(f"{Style.BOLD}{Style.CYAN}--- 1. CURRENT SIMULATION CONTEXT ---{Style.RESET}")
        print(f"  • Target Platform    : {Style.YELLOW}{self.platform.value.upper()}{Style.RESET}")
        print(f"  • Screen Resolution  : {self.media_query.size_width:.1f}dp x {self.media_query.size_height:.1f}dp")
        print(f"  • Pixel Ratio (DPR)  : {self.media_query.device_pixel_ratio:.1f}x")
        print(f"  • Safe Area Insets   : Top {self.media_query.padding_top}dp | Bottom {self.media_query.padding_bottom}dp")
        print(f"  • Screen Breakpoint  : {Style.GREEN}{st.value}{Style.RESET}")

    def simulate_adaptive_component(self):
        """Demonstrates adaptive behavior (Cupertino vs Material vs Desktop pointer)."""
        print(f"\n{Style.BOLD}{Style.CYAN}--- 2. ADAPTIVE WIDGET TREE EVALUATION ---{Style.RESET}")
        if self.platform == TargetPlatform.IOS or self.platform == TargetPlatform.MACOS:
            print(f"  {Style.MAGENTA}[Adaptive Switch]{Style.RESET} Rendering {Style.BOLD}CupertinoSwitch{Style.RESET}")
            print(f"    └─ Physics: BouncingScrollPhysics (iOS standard)")
            print(f"    └─ Dialog: CupertinoAlertDialog with SF Pro typography")
            print(f"    └─ Transitions: CupertinoPageTransition (Slide from Right with drag-to-pop)")
        elif self.platform in (TargetPlatform.WINDOWS, TargetPlatform.LINUX, TargetPlatform.MACOS, TargetPlatform.WEB):
            print(f"  {Style.BLUE}[Adaptive UI]{Style.RESET} Rendering {Style.BOLD}Desktop / Web DesktopScaffold{Style.RESET}")
            print(f"    └─ Interaction: MouseRegion hover detection, ContextMenu on right click")
            print(f"    └─ Navigation: NavigationRail / Custom App Sidebar with keyboard shortcuts")
            print(f"    └─ Scroll: Smooth MouseWheelScrollBehavior with visible scrollbars")
        else:
            print(f"  {Style.GREEN}[Adaptive Switch]{Style.RESET} Rendering {Style.BOLD}Switch.adaptive (Material 3){Style.RESET}")
            print(f"    └─ Physics: ClampingScrollPhysics with Material stretch overscroll glow")
            print(f"    └─ Dialog: AlertDialog with MD3 ColorScheme and tonal elevation")
            print(f"    └─ Transitions: MaterialPageRoute (Predictive Back Gesture ready)")

    def simulate_responsive_layout(self):
        """Demonstrates Breakpoint-driven layout layout switching."""
        print(f"\n{Style.BOLD}{Style.CYAN}--- 3. RESPONSIVE LAYOUT ENGINE (LayoutBuilder Simulation) ---{Style.RESET}")
        st = self.media_query.screen_type
        width = self.media_query.size_width
        
        # Simulating Root LayoutBuilder
        parent_constraints = BoxConstraints(
            min_width=0.0,
            max_width=width,
            min_height=0.0,
            max_height=self.media_query.size_height
        )

        print(f"  Incoming BoxConstraints: minW={parent_constraints.min_width}, maxW={parent_constraints.max_width}")

        if st == DeviceScreenType.COMPACT:
            print(f"\n  {Style.YELLOW}>> Active Layout: Single-Column Master-Detail (Push Navigation){Style.RESET}")
            print("  ┌────────────────────────┐")
            print("  │ [App Bar / Search]     │")
            print("  │ ---------------------- │")
            print("  │ Item 1 >               │")
            print("  │ Item 2 > (Tap to push) │")
            print("  │ Item 3 >               │")
            print("  │ ---------------------- │")
            print("  │ [BottomNavigationBar]  │")
            print("  └────────────────────────┘")
        elif st == DeviceScreenType.MEDIUM:
            print(f"\n  {Style.YELLOW}>> Active Layout: NavigationRail + Responsive Grid{Style.RESET}")
            print("  ┌──┬──────────────────────┐")
            print("  │  │ [Dashboard Grid]     │")
            print("  │R │ ┌───────┐ ┌────────┐ │")
            print("  │A │ │Card A │ │Card B  │ │")
            print("  │I │ └───────┘ └────────┘ │")
            print("  │L │ ┌───────┐ ┌────────┐ │")
            print("  │  │ │Card C │ │Card D  │ │")
            print("  └──┴─┴───────┴─┴────────┴─┘")
        else:
            print(f"\n  {Style.YELLOW}>> Active Layout: Master-Detail Side-by-Side (Split View){Style.RESET}")
            print("  ┌──────┬──────────────┬───────────────────────────┐")
            print("  │ Nav  │ List (320dp) │ Detail Workspace (Flex: 2)│")
            print("  │ Rail │ ───────────  │ ───────────────────────── │")
            print("  │      │ - Project A  │ Project A Deep Insights   │")
            print("  │ ⚙️    │ - Project B  │ Real-time stats & graphs  │")
            print("  └──────┴──────────────┴───────────────────────────┘")

    def run_benchmark_preset(self, preset_name: str, width: float, height: float, platform: TargetPlatform):
        print(f"\n{Style.BOLD}Applying Preset: {Style.MAGENTA}{preset_name}{Style.RESET}")
        self.platform = platform
        self.media_query.size_width = width
        self.media_query.size_height = height
        self.inspect_current_context()
        self.simulate_adaptive_component()
        self.simulate_responsive_layout()
        print(f"{Style.DIM}------------------------------------------------------------{Style.RESET}")


def interactive_loop():
    engine = FlutterLayoutEngineSimulator()
    engine.print_banner()

    presets = [
        ("iPhone 15 Pro", 393.0, 852.0, TargetPlatform.IOS),
        ("Pixel 8 (Android)", 412.0, 915.0, TargetPlatform.ANDROID),
        ("iPad Pro 11-inch (Portrait)", 834.0, 1194.0, TargetPlatform.IOS),
        ("Samsung Galaxy Z Fold 5 (Expanded)", 904.0, 2316.0, TargetPlatform.ANDROID),
        ("Desktop 1080p Browser Window", 1280.0, 800.0, TargetPlatform.WEB),
        ("macOS Retina UltraWide Window", 1920.0, 1080.0, TargetPlatform.MACOS),
    ]

    while True:
        print(f"\n{Style.BOLD}PILIH MENU SIMULASI TEKNIS:{Style.RESET}")
        print(" [1] Jalankan Preset Device Profile (Mobile/Tablet/Desktop/Web)")
        print(" [2] Atur Custom Dimensions (Uji Breakpoint 600dp & 840dp)")
        print(" [3] Ubah TargetPlatform (Lihat adaptasi Cupertino vs Material)")
        print(" [4] Jalankan Auto Benchmark Semua Preset")
        print(" [0] Keluar")

        try:
            choice = input(f"\n{Style.BOLD}{Style.GREEN}Pilihan Anda (0-4): {Style.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting simulator.")
            break

        if choice == "0":
            print(f"{Style.YELLOW}Sesi simulasi ditutup. Selamat belajar Flutter Adaptive Architecture!{Style.RESET}")
            break
        elif choice == "1":
            print("\nPreset Tersedia:")
            for idx, (name, w, h, p) in enumerate(presets, 1):
                print(f"  [{idx}] {name} ({w}x{h}dp - {p.value})")
            p_idx = input(f"Pilih preset (1-{len(presets)}): ").strip()
            if p_idx.isdigit() and 1 <= int(p_idx) <= len(presets):
                name, w, h, p = presets[int(p_idx) - 1]
                engine.run_benchmark_preset(name, w, h, p)
            else:
                print(f"{Style.RED}Input tidak valid.{Style.RESET}")
        elif choice == "2":
            try:
                w_str = input("Masukkan width dalam logical pixels (dp) [misal 400, 720, 1024]: ").strip()
                h_str = input("Masukkan height dalam logical pixels (dp) [misal 800]: ").strip()
                w = float(w_str)
                h = float(h_str)
                engine.media_query.size_width = w
                engine.media_query.size_height = h
                engine.inspect_current_context()
                engine.simulate_responsive_layout()
            except ValueError:
                print(f"{Style.RED}Format angka tidak valid.{Style.RESET}")
        elif choice == "3":
            print("\nPlatform Target Tersedia:")
            for idx, p in enumerate(TargetPlatform, 1):
                print(f"  [{idx}] {p.value}")
            p_sel = input("Pilih target platform: ").strip()
            if p_sel.isdigit() and 1 <= int(p_sel) <= len(TargetPlatform):
                engine.platform = list(TargetPlatform)[int(p_sel) - 1]
                engine.inspect_current_context()
                engine.simulate_adaptive_component()
            else:
                print(f"{Style.RED}Input tidak valid.{Style.RESET}")
        elif choice == "4":
            print(f"\n{Style.CYAN}Memulai running auto benchmark semua preset...{Style.RESET}")
            for name, w, h, p in presets:
                time.sleep(0.3)
                engine.run_benchmark_preset(name, w, h, p)
        else:
            print(f"{Style.RED}Opsi tidak dikenali.{Style.RESET}")


if __name__ == "__main__":
    interactive_loop()
