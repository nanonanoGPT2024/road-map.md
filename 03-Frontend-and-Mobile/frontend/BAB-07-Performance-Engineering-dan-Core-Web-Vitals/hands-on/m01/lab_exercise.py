#!/usr/bin/env python3
"""
Lab Exercise M01: Performance Engineering & Core Web Vitals Simulator
BAB-07: Performance Engineering dan Core Web Vitals

Simulasi teknis interaktif berbasis ANSI Terminal:
- Largest Contentful Paint (LCP)
- Interaction to Next Paint (INP)
- Cumulative Layout Shift (CLS)
- Total Blocking Time (TBT) & Time to First Byte (TTFB)
"""

import sys
import time
import math
import random
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

# ==============================================================================
# ANSI Color Codes & Formatting
# ==============================================================================
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BG_DARK = "\033[48;5;235m"

def c_print(text: str, color: str = Color.WHITE, bold: bool = False, end: str = "\n"):
    prefix = Color.BOLD if bold else ""
    print(f"{prefix}{color}{text}{Color.RESET}", end=end)

def print_banner():
    banner = f"""
{Color.CYAN}{Color.BOLD}================================================================================
  CORE WEB VITALS & WEB PERFORMANCE BENCHMARK SIMULATOR (BAB-07)
  Chrome UX Report (CrUX) & Lighthouse 10+ Alignment Engine
================================================================================{Color.RESET}"""
    print(banner)

# ==============================================================================
# Domain Models & CWV Specifications
# ==============================================================================
@dataclass
class CWVThreshold:
    good: float
    needs_improvement: float
    unit: str

THRESHOLDS = {
    "LCP": CWVThreshold(good=2500.0, needs_improvement=4000.0, unit="ms"),
    "INP": CWVThreshold(good=200.0, needs_improvement=500.0, unit="ms"),
    "CLS": CWVThreshold(good=0.10, needs_improvement=0.25, unit="score"),
    "TTFB": CWVThreshold(good=800.0, needs_improvement=1800.0, unit="ms"),
    "TBT": CWVThreshold(good=200.0, needs_improvement=600.0, unit="ms"),
}

def grade_metric(metric: str, value: float) -> Tuple[str, str]:
    t = THRESHOLDS[metric]
    if value <= t.good:
        return "GOOD", Color.GREEN
    elif value <= t.needs_improvement:
        return "NEEDS IMPROVEMENT", Color.YELLOW
    else:
        return "POOR", Color.RED

@dataclass
class NetworkRequest:
    name: str
    size_kb: float
    ttfb_ms: float
    download_ms: float
    is_render_blocking: bool
    is_lcp_candidate: bool = False

@dataclass
class LayoutShiftEvent:
    element: str
    impact_fraction: float
    distance_fraction: float
    had_recent_input: bool = False

    @property
    def shift_score(self) -> float:
        if self.had_recent_input:
            return 0.0
        return round(self.impact_fraction * self.distance_fraction, 4)

@dataclass
class InteractionEvent:
    event_type: str
    input_delay_ms: float
    processing_duration_ms: float
    presentation_delay_ms: float

    @property
    def total_duration_ms(self) -> float:
        return round(self.input_delay_ms + self.processing_duration_ms + self.presentation_delay_ms, 2)

@dataclass
class PerformanceProfile:
    name: str
    requests: List[NetworkRequest] = field(default_factory=list)
    layout_shifts: List[LayoutShiftEvent] = field(default_factory=list)
    interactions: List[InteractionEvent] = field(default_factory=list)

# ==============================================================================
# Simulation Engine
# ==============================================================================
class CWVSimulator:
    def __init__(self, profile: PerformanceProfile):
        self.profile = profile

    def calculate_lcp(self) -> Tuple[float, Optional[NetworkRequest]]:
        total_time = 0.0
        lcp_req = None
        blocking_js_css = 0.0

        for req in self.profile.requests:
            req_time = req.ttfb_ms + req.download_ms
            if req.is_render_blocking:
                blocking_js_css += req_time
            if req.is_lcp_candidate:
                lcp_req = req

        if lcp_req:
            # LCP = Network start + TTFB + Download + Render Blocking Latency
            lcp_time = lcp_req.ttfb_ms + lcp_req.download_ms + (blocking_js_css * 0.65)
        else:
            lcp_time = blocking_js_css + 350.0

        return round(lcp_time, 2), lcp_req

    def calculate_cls(self) -> float:
        total_cls = sum(event.shift_score for event in self.profile.layout_shifts)
        return round(total_cls, 4)

    def calculate_inp(self) -> Tuple[float, Optional[InteractionEvent]]:
        if not self.profile.interactions:
            return 0.0, None

        # INP is typically the 98th percentile interaction or worst for small session
        sorted_interactions = sorted(self.profile.interactions, key=lambda x: x.total_duration_ms, reverse=True)
        worst_interaction = sorted_interactions[0]
        return worst_interaction.total_duration_ms, worst_interaction

    def calculate_tbt(self) -> float:
        # Sum of blocking portions (> 50ms) for main thread tasks
        tbt = 0.0
        for interaction in self.profile.interactions:
            task_time = interaction.processing_duration_ms
            if task_time > 50.0:
                tbt += (task_time - 50.0)
        return round(tbt, 2)

    def calculate_ttfb(self) -> float:
        if not self.profile.requests:
            return 0.0
        return round(self.profile.requests[0].ttfb_ms, 2)

# ==============================================================================
# Preset Profiles (Unoptimized vs Production Optimized)
# ==============================================================================
def create_unoptimized_profile() -> PerformanceProfile:
    profile = PerformanceProfile(name="Legacy Unoptimized Architecture (SPA Fat Bundle)")
    
    # Network Requests (Heavy bundles, non-CDN, uncompressed hero banner)
    profile.requests = [
        NetworkRequest("document (HTML)", size_kb=45.0, ttfb_ms=850.0, download_ms=120.0, is_render_blocking=True),
        NetworkRequest("app.bundle.js", size_kb=3200.0, ttfb_ms=150.0, download_ms=1600.0, is_render_blocking=True),
        NetworkRequest("vendor.styles.css", size_kb=650.0, ttfb_ms=120.0, download_ms=450.0, is_render_blocking=True),
        NetworkRequest("hero-banner-uncompressed.png", size_kb=4200.0, ttfb_ms=220.0, download_ms=2100.0, is_render_blocking=False, is_lcp_candidate=True),
        NetworkRequest("tracker-analytics.js", size_kb=350.0, ttfb_ms=300.0, download_ms=400.0, is_render_blocking=True),
    ]

    # Layout Shifts (Images without dimensions, late ads injection)
    profile.layout_shifts = [
        LayoutShiftEvent("<img> Hero Banner (No width/height reserved)", impact_fraction=0.60, distance_fraction=0.25),
        LayoutShiftEvent("<div id='top-ad-banner'> Late Hydration", impact_fraction=0.45, distance_fraction=0.15),
        LayoutShiftEvent("<div class='cookie-consent'> DOM Injection", impact_fraction=0.20, distance_fraction=0.10),
    ]

    # Interactions (Heavy hydration, un-debounced filter, synchronous JSON parsing)
    profile.interactions = [
        InteractionEvent("Search Filter Keypress", input_delay_ms=180.0, processing_duration_ms=420.0, presentation_delay_ms=65.0),
        InteractionEvent("Mobile Nav Drawer Toggle", input_delay_ms=90.0, processing_duration_ms=150.0, presentation_delay_ms=40.0),
        InteractionEvent("Add to Cart Button Click", input_delay_ms=210.0, processing_duration_ms=510.0, presentation_delay_ms=80.0),
    ]

    return profile

def create_optimized_profile() -> PerformanceProfile:
    profile = PerformanceProfile(name="Modern Edge-Optimized Architecture (Islands + Priority Hints)")

    # Network Requests (Edge SSR, code splitting, WebP/AVIF hero with fetchpriority="high")
    profile.requests = [
        NetworkRequest("document (Edge SSR HTML)", size_kb=18.0, ttfb_ms=110.0, download_ms=25.0, is_render_blocking=True),
        NetworkRequest("critical.css (Inlined)", size_kb=12.0, ttfb_ms=0.0, download_ms=5.0, is_render_blocking=True),
        NetworkRequest("island-main.js (ESM Chunk)", size_kb=85.0, ttfb_ms=40.0, download_ms=60.0, is_render_blocking=False),
        NetworkRequest("hero-banner.avif (fetchpriority=high)", size_kb=140.0, ttfb_ms=50.0, download_ms=95.0, is_render_blocking=False, is_lcp_candidate=True),
        NetworkRequest("analytics.js (Worker / defer)", size_kb=25.0, ttfb_ms=80.0, download_ms=40.0, is_render_blocking=False),
    ]

    # Layout Shifts (Explicit aspect-ratio, CSS containment, reserved ad slots)
    profile.layout_shifts = [
        LayoutShiftEvent("<img> Hero Banner with aspect-ratio: 16/9", impact_fraction=0.0, distance_fraction=0.0),
        LayoutShiftEvent("<div id='top-ad-banner'> min-height slot reserved", impact_fraction=0.02, distance_fraction=0.01),
    ]

    # Interactions (yield to main thread with scheduler.yield(), Web Worker compute)
    profile.interactions = [
        InteractionEvent("Search Filter Keypress (scheduler.yield)", input_delay_ms=8.0, processing_duration_ms=32.0, presentation_delay_ms=12.0),
        InteractionEvent("Mobile Nav Drawer Toggle (CSS Transform)", input_delay_ms=4.0, processing_duration_ms=14.0, presentation_delay_ms=6.0),
        InteractionEvent("Add to Cart Button Click (Optimistic UI)", input_delay_ms=12.0, processing_duration_ms=45.0, presentation_delay_ms=15.0),
    ]

    return profile

# ==============================================================================
# UI Report Presenter
# ==============================================================================
def render_metrics_table(profile: PerformanceProfile):
    sim = CWVSimulator(profile)
    lcp, lcp_req = sim.calculate_lcp()
    cls_score = sim.calculate_cls()
    inp, worst_int = sim.calculate_inp()
    tbt = sim.calculate_tbt()
    ttfb = sim.calculate_ttfb()

    print(f"\n{Color.BOLD}{Color.MAGENTA}=== Vitals Audit: {profile.name} ==={Color.RESET}")
    print(f"{'Metric':<8} | {'Value':<14} | {'Target (Good)':<14} | {'Status':<18} | {'Impact / Bottleneck'}")
    print("-" * 88)

    metrics_data = [
        ("TTFB", ttfb, f"{ttfb:.1f} ms", "<= 800 ms", "Server & Network Routing"),
        ("LCP", lcp, f"{lcp:.1f} ms", "<= 2500 ms", f"Resource: {lcp_req.name if lcp_req else 'DOM Content'}"),
        ("INP", inp, f"{inp:.1f} ms", "<= 200 ms", f"Event: {worst_int.event_type if worst_int else 'None'}"),
        ("CLS", cls_score, f"{cls_score:.4f}", "<= 0.1000", f"{len(profile.layout_shifts)} layout shifts recorded"),
        ("TBT", tbt, f"{tbt:.1f} ms", "<= 200 ms", "Total Main Thread Long Tasks"),
    ]

    for code, raw_val, formatted_val, target, impact in metrics_data:
        status, color = grade_metric(code, raw_val)
        status_str = f"{color}{status:<18}{Color.RESET}"
        print(f"{Color.BOLD}{code:<8}{Color.RESET} | {formatted_val:<14} | {target:<14} | {status_str} | {Color.DIM}{impact}{Color.RESET}")
    print("-" * 88)

def render_waterfall(profile: PerformanceProfile):
    print(f"\n{Color.BOLD}{Color.CYAN}--- Network & Critical Rendering Path Waterfall ---{Color.RESET}")
    current_offset = 0.0
    
    for req in profile.requests:
        ttfb_bars = max(1, int(req.ttfb_ms / 50.0))
        download_bars = max(1, int(req.download_ms / 50.0))
        
        tag = f"[{'BLOCKING' if req.is_render_blocking else 'ASYNC'}]"
        tag_color = Color.RED if req.is_render_blocking else Color.GREEN
        candidate_tag = f" {Color.YELLOW}*LCP*{Color.RESET}" if req.is_lcp_candidate else ""

        print(f"\n{req.name:<34} ({req.size_kb:6.1f} KB) {tag_color}{tag:<10}{Color.RESET}{candidate_tag}")
        
        offset_space = " " * int(current_offset / 50.0)
        ttfb_vis = f"{Color.BLUE}{'░' * ttfb_bars}{Color.RESET}"
        down_vis = f"{Color.CYAN}{'█' * download_bars}{Color.RESET}"
        
        print(f"  Timeline: {offset_space}{ttfb_vis}{down_vis} ({req.ttfb_ms + req.download_ms:.0f} ms total)")
        
        if req.is_render_blocking:
            current_offset += (req.ttfb_ms + req.download_ms) * 0.45
        else:
            current_offset += 20.0

def render_inp_breakdown(profile: PerformanceProfile):
    sim = CWVSimulator(profile)
    _, worst_int = sim.calculate_inp()
    if not worst_int:
        print("No interactions recorded.")
        return

    print(f"\n{Color.BOLD}{Color.YELLOW}--- Interaction to Next Paint (INP) Deep Dive ---{Color.RESET}")
    print(f"Worst Interaction: {Color.BOLD}{worst_int.event_type}{Color.RESET}")
    print(f"Total Duration   : {worst_int.total_duration_ms:.1f} ms\n")

    total = worst_int.total_duration_ms
    p1 = (worst_int.input_delay_ms / total) * 100
    p2 = (worst_int.processing_duration_ms / total) * 100
    p3 = (worst_int.presentation_delay_ms / total) * 100

    print("Phase Breakdown:")
    print(f"  1. Input Delay         : {worst_int.input_delay_ms:6.1f} ms ({p1:4.1f}%) {Color.RED}{'█' * int(p1 / 4)}{Color.RESET}")
    print(f"  2. Processing Duration : {worst_int.processing_duration_ms:6.1f} ms ({p2:4.1f}%) {Color.YELLOW}{'█' * int(p2 / 4)}{Color.RESET}")
    print(f"  3. Presentation Delay  : {worst_int.presentation_delay_ms:6.1f} ms ({p3:4.1f}%) {Color.BLUE}{'█' * int(p3 / 4)}{Color.RESET}")
    
    print(f"\n{Color.DIM}Root Cause Engineering Notes:{Color.RESET}")
    if worst_int.input_delay_ms > 50.0:
        c_print("  [!] Input Delay is High: Main thread was locked by prior long tasks before event fired.", Color.RED)
    if worst_int.processing_duration_ms > 100.0:
        c_print("  [!] Processing Duration is High: Heavy event listener loop. Break down via scheduler.yield().", Color.YELLOW)
    if worst_int.presentation_delay_ms > 50.0:
        c_print("  [!] Presentation Delay is High: Layout thrashing or massive DOM tree recalculation.", Color.RED)

def render_cls_breakdown(profile: PerformanceProfile):
    print(f"\n{Color.BOLD}{Color.MAGENTA}--- Cumulative Layout Shift (CLS) Mathematical Attribution ---{Color.RESET}")
    print(f"Formula: Shift Score = Impact Fraction × Distance Fraction\n")

    for i, shift in enumerate(profile.layout_shifts, 1):
        score = shift.shift_score
        color = Color.GREEN if score < 0.05 else (Color.YELLOW if score < 0.1 else Color.RED)
        print(f"Shift #{i}: {shift.element}")
        print(f"   Impact Fraction  : {shift.impact_fraction:.3f}")
        print(f"   Distance Fraction: {shift.distance_fraction:.3f}")
        print(f"   Calculated Score : {color}{score:.4f}{Color.RESET}")
        print()

# ==============================================================================
# Interactive Engineering Sandbox
# ==============================================================================
def interactive_tuning_sandbox():
    c_print("\n=== INTERACTIVE PARAMETER TUNING SANDBOX ===", Color.CYAN, bold=True)
    c_print("Simulasikan perbaikan arsitektur dan lihat dampaknya secara real-time.\n", Color.DIM)

    # Base profile to tweak
    p = create_unoptimized_profile()

    while True:
        sim = CWVSimulator(p)
        lcp, _ = sim.calculate_lcp()
        cls_val = sim.calculate_cls()
        inp, _ = sim.calculate_inp()

        print("-" * 60)
        c_print("Current Core Web Vitals Status:", Color.BOLD)
        for name, val in [("LCP", lcp), ("INP", inp), ("CLS", cls_val)]:
            status, col = grade_metric(name, val)
            print(f"  • {name:<5}: {val:8.2f} [{col}{status}{Color.RESET}]")
        print("-" * 60)

        print("\nPilih Optimasi Teknis yang ingin diterapkan:")
        print(" [1] Pasang explicit width/height & CSS aspect-ratio pada gambar (Fix CLS)")
        print(" [2] Aktifkan Code-Splitting & Defer Non-Critical JavaScript (Fix LCP & INP)")
        print(" [3] Convert Hero Image ke AVIF + pasang fetchpriority='high' (Fix LCP)")
        print(" [4] Ganti Sync Loop dengan scheduler.yield() / Web Worker (Fix INP)")
        print(" [5] Reset ke Kondisi Awal")
        print(" [0] Kembali ke Menu Utama")

        choice = input(f"\n{Color.YELLOW}Pilihan Anda [0-5]: {Color.RESET}").strip()

        if choice == "1":
            for shift in p.layout_shifts:
                shift.impact_fraction *= 0.1
                shift.distance_fraction *= 0.1
            c_print("\n[V] Berhasil! Slot gambar telah dipesan sebelum network download selesai.", Color.GREEN)
        elif choice == "2":
            for req in p.requests:
                if "bundle.js" in req.name or "tracker" in req.name:
                    req.is_render_blocking = False
                    req.download_ms *= 0.4
                    req.size_kb *= 0.3
            c_print("\n[V] Bundle di-split! Render blocking latency berkurang drastis.", Color.GREEN)
        elif choice == "3":
            for req in p.requests:
                if req.is_lcp_candidate:
                    req.name = "hero-banner-optimized.avif"
                    req.size_kb = 120.0
                    req.download_ms = 85.0
                    req.ttfb_ms = 60.0
            c_print("\n[V] Hero banner di-convert ke AVIF dan diprioritaskan di preload scanner.", Color.GREEN)
        elif choice == "4":
            for interaction in p.interactions:
                interaction.input_delay_ms = max(5.0, interaction.input_delay_ms * 0.15)
                interaction.processing_duration_ms = max(18.0, interaction.processing_duration_ms * 0.2)
                interaction.presentation_delay_ms = max(8.0, interaction.presentation_delay_ms * 0.25)
            c_print("\n[V] Task dipecah di bawah 50ms threshold via scheduler.yield().", Color.GREEN)
        elif choice == "5":
            p = create_unoptimized_profile()
            c_print("\n[R] Profil di-reset ke kondisi legacy unoptimized.", Color.MAGENTA)
        elif choice == "0":
            break
        else:
            c_print("Pilihan tidak valid.", Color.RED)
        time.sleep(0.6)

# ==============================================================================
# Main Interactive CLI Loop
# ==============================================================================
def main():
    print_banner()

    unopt = create_unoptimized_profile()
    opt = create_optimized_profile()

    while True:
        print(f"\n{Color.BOLD}{Color.WHITE}MAIN SELECTION MENU:{Color.RESET}")
        print(f" {Color.CYAN}[1]{Color.RESET} Bandingkan Audit Lengkap (Unoptimized vs Production Optimized)")
        print(f" {Color.CYAN}[2]{Color.RESET} Visualisasi Waterfall & Critical Rendering Path (CRP)")
        print(f" {Color.CYAN}[3]{Color.RESET} Deep Dive: Interaction to Next Paint (INP) Long Tasks")
        print(f" {Color.CYAN}[4]{Color.RESET} Deep Dive: Cumulative Layout Shift (CLS) Calculation")
        print(f" {Color.CYAN}[5]{Color.RESET} Interactive Performance Engineering Tuning Sandbox")
        print(f" {Color.CYAN}[0]{Color.RESET} Keluar / Exit")

        user_input = input(f"\n{Color.BOLD}Masukkan nomor pilihan [0-5]: {Color.RESET}").strip()

        if user_input == "1":
            render_metrics_table(unopt)
            render_metrics_table(opt)
        elif user_input == "2":
            render_waterfall(unopt)
            render_waterfall(opt)
        elif user_input == "3":
            render_inp_breakdown(unopt)
            render_inp_breakdown(opt)
        elif user_input == "4":
            render_cls_breakdown(unopt)
            render_cls_breakdown(opt)
        elif user_input == "5":
            interactive_tuning_sandbox()
        elif user_input in ("0", "q", "exit"):
            c_print("\nSelesai. Terus pantau CrUX dan Web Vitals di production pipeline Anda!\n", Color.GREEN, bold=True)
            sys.exit(0)
        else:
            c_print("Input tidak dikenali. Silakan pilih 0 - 5.", Color.RED)

if __name__ == "__main__":
    main()
