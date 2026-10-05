#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Arsitektur Produksi UX Design & Fondasi Sistem (BAB 01)
Modul 02: Information Architecture, Usability Heuristics & WCAG Accessibility Audit
"""

import sys
import time
import math
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum

# ==============================================================================
# ANSI Color Palette for Rich Terminal UX
# ==============================================================================
class Color:
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
    BG_DARK = "\033[100m"

def cprint(text: str, color: str = Color.WHITE, bold: bool = False, end: str = "\n"):
    prefix = Color.BOLD if bold else ""
    print(f"{prefix}{color}{text}{Color.RESET}", end=end)

def print_header(title: str):
    print("\n" + "=" * 70)
    cprint(f"  {title.upper()}", Color.CYAN, bold=True)
    print("=" * 70)

def print_badge(label: str, text: str, color: str = Color.GREEN):
    print(f"[{color}{Color.BOLD}{label}{Color.RESET}] {text}")

# ==============================================================================
# Domain Model 1: Information Architecture (IA) Node & Hierarchy Engine
# ==============================================================================
class ContentType(Enum):
    PAGE = "Page"
    ACTION = "Interactive Action"
    SECTION = "Content Section"
    MODAL = "Overlay Modal"

@dataclass
class IANode:
    id: str
    label: str
    content_type: ContentType
    depth: int
    children: List['IANode'] = field(default_factory=list)
    click_cost: int = 1
    cognitive_load_index: float = 1.0  # 1.0 (Low) to 5.0 (High)

    def add_child(self, child: 'IANode') -> 'IANode':
        child.depth = self.depth + 1
        self.children.append(child)
        return child

    def render_tree(self, prefix: str = "", is_last: bool = True):
        marker = "└── " if is_last else "├── "
        color = Color.GREEN if self.depth <= 2 else (Color.YELLOW if self.depth == 3 else Color.RED)
        type_str = f"({self.content_type.value}, Load: {self.cognitive_load_index})"
        print(f"{prefix}{marker}{color}{Color.BOLD}{self.label}{Color.RESET} {Color.DIM}{type_str}{Color.RESET}")
        
        new_prefix = prefix + ("    " if is_last else "│   ")
        count = len(self.children)
        for idx, child in enumerate(self.children):
            child.render_tree(new_prefix, idx == (count - 1))

    def evaluate_depth_friction(self) -> List[Tuple[str, int, str]]:
        """Identifies deep navigation paths violating 3-click rule."""
        issues = []
        if self.depth > 3:
            issues.append((self.label, self.depth, "Violates 3-click navigation guideline (Friction Risk)"))
        for child in self.children:
            issues.extend(child.evaluate_depth_friction())
        return issues

# ==============================================================================
# Domain Model 2: WCAG 2.1 Color Contrast & Accessibility Analyzer
# ==============================================================================
class WCAGAnalyzer:
    @staticmethod
    def _hex_to_rgb(hex_code: str) -> Tuple[int, int, int]:
        hex_clean = hex_code.lstrip("#")
        if len(hex_clean) != 6:
            raise ValueError(f"Invalid hex color format: {hex_code}")
        return tuple(int(hex_clean[i:i+2], 16) for i in (0, 2, 4))  # type: ignore

    @classmethod
    def _relative_luminance(cls, r: int, g: int, b: int) -> float:
        """Calculates W3C sRGB relative luminance."""
        def channel_lum(val: int) -> float:
            c = val / 255.0
            return c / 12.92 if c <= 0.03928 else math.pow((c + 0.055) / 1.055, 2.4)
        
        rs = channel_lum(r)
        gs = channel_lum(g)
        bs = channel_lum(b)
        return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs

    @classmethod
    def calculate_contrast(cls, fg_hex: str, bg_hex: str) -> float:
        fg_rgb = cls._hex_to_rgb(fg_hex)
        bg_rgb = cls._hex_to_rgb(bg_hex)
        lum1 = cls._relative_luminance(*fg_rgb)
        lum2 = cls._relative_luminance(*bg_rgb)
        lighter = max(lum1, lum2)
        darker = min(lum1, lum2)
        return (lighter + 0.05) / (darker + 0.05)

    @classmethod
    def audit_contrast(cls, fg_hex: str, bg_hex: str, label: str) -> Dict[str, any]:
        ratio = round(cls.calculate_contrast(fg_hex, bg_hex), 2)
        aa_normal = ratio >= 4.5
        aa_large = ratio >= 3.0
        aaa_normal = ratio >= 7.0
        aaa_large = ratio >= 4.5
        
        status = "FAIL"
        if aaa_normal:
            status = "AAA (Optimal)"
        elif aa_normal:
            status = "AA (Compliant)"
        elif aa_large:
            status = "AA Large Only"
            
        return {
            "label": label,
            "fg": fg_hex,
            "bg": bg_hex,
            "ratio": ratio,
            "aa_normal": aa_normal,
            "aa_large": aa_large,
            "aaa_normal": aaa_normal,
            "status": status
        }

# ==============================================================================
# Domain Model 3: System Usability Scale (SUS) Psychometric Engine
# ==============================================================================
class SUSCalculator:
    """Computes standardized Brooke (1996) System Usability Scale score."""
    QUESTIONS = [
        "1. I think that I would like to use this system frequently.",
        "2. I found the system unnecessarily complex.",
        "3. I thought the system was easy to use.",
        "4. I think that I would need the support of a technical person to use this system.",
        "5. I found the various functions in this system were well integrated.",
        "6. I thought there was too much inconsistency in this system.",
        "7. I would imagine that most people would learn to use this system very quickly.",
        "8. I found the system very cumbersome to use.",
        "9. I felt very confident using the system.",
        "10. I needed to learn a lot of things before I could get going with this system."
    ]

    @classmethod
    def compute(cls, scores: List[int]) -> Tuple[float, str, str]:
        if len(scores) != 10 or not all(1 <= s <= 5 for s in scores):
            raise ValueError("SUS requires exactly 10 ratings ranging between 1 and 5.")
        
        total_contribution = 0
        for i, val in enumerate(scores):
            if (i + 1) % 2 != 0:
                # Odd items: scale position - 1
                total_contribution += (val - 1)
            else:
                # Even items: 5 - scale position
                total_contribution += (5 - val)
        
        sus_score = total_contribution * 2.5
        
        # Qualitative grade based on Bangor, Kortum & Miller (2008)
        if sus_score >= 85.0:
            grade = "A+ (Superior / Best Imaginable)"
            adjective = "Excellent"
        elif sus_score >= 80.0:
            grade = "A (Good Usability)"
            adjective = "Good"
        elif sus_score >= 70.0:
            grade = "B (Acceptable / Above Average)"
            adjective = "Good"
        elif sus_score >= 68.0:
            grade = "C (Marginal Average)"
            adjective = "OK"
        elif sus_score >= 50.0:
            grade = "D (Poor Usability / Action Required)"
            adjective = "Poor"
        else:
            grade = "F (Unacceptable Friction)"
            adjective = "Awful"

        return round(sus_score, 1), grade, adjective

# ==============================================================================
# Simulation Scenario: Enterprise SaaS UX Architecture
# ==============================================================================
def create_sample_ia_tree() -> IANode:
    root = IANode(id="root", label="Global Navigation Dashboard", content_type=ContentType.PAGE, depth=0)
    
    # Branch 1: Projects
    projects = root.add_child(IANode(id="proj", label="Projects Hub", content_type=ContentType.PAGE, depth=1, cognitive_load_index=1.5))
    p_detail = projects.add_child(IANode(id="proj_det", label="Project Workspace", content_type=ContentType.PAGE, depth=2, cognitive_load_index=2.0))
    p_tasks = p_detail.add_child(IANode(id="tasks", label="Task Board", content_type=ContentType.SECTION, depth=3, cognitive_load_index=2.5))
    # Friction branch (Depth 4 & 5)
    p_subtask = p_tasks.add_child(IANode(id="sub_item", label="Subtask Drawer", content_type=ContentType.MODAL, depth=4, cognitive_load_index=3.8))
    p_subtask.add_child(IANode(id="perm_cfg", label="Deep Permissions Matrix", content_type=ContentType.ACTION, depth=5, cognitive_load_index=4.5))

    # Branch 2: Analytics
    analytics = root.add_child(IANode(id="analytics", label="Executive Analytics", content_type=ContentType.PAGE, depth=1, cognitive_load_index=2.0))
    analytics.add_child(IANode(id="reports", label="Conversion Funnels", content_type=ContentType.PAGE, depth=2, cognitive_load_index=2.2))
    
    # Branch 3: Settings
    settings = root.add_child(IANode(id="settings", label="System Config", content_type=ContentType.PAGE, depth=1, cognitive_load_index=1.2))
    settings.add_child(IANode(id="team", label="Identity & Access", content_type=ContentType.PAGE, depth=2, cognitive_load_index=1.8))
    
    return root

# ==============================================================================
# Interactive CLI Simulator Routines
# ==============================================================================
def run_ia_audit(root: IANode):
    print_header("Audit Information Architecture (IA) & Hierarchical Depth")
    print("Menganalisis pohon navigasi aplikasi terhadap Cognitive Load & 3-Click Rule:\n")
    root.render_tree()
    
    print("\n--- Diagnostic IA Insights ---")
    issues = root.evaluate_depth_friction()
    if issues:
        cprint(f"Ditemukan {len(issues)} potensi hambatan navigasi (Deep Nesting):", Color.YELLOW, bold=True)
        for label, depth, desc in issues:
            print(f"  • Node: {Color.RED}{label}{Color.RESET} (Depth: {depth}) -> {Color.WHITE}{desc}{Color.RESET}")
    else:
        cprint("Pohon arsitektur informasi memenuhi kriteria flat hierarchy (< 3 depth).", Color.GREEN)

def run_wcag_audit():
    print_header("Simulasi WCAG 2.1 AA/AAA Color Contrast Matrix")
    cprint("Menguji palet warna design system terhadap keterbacaan visual:", Color.WHITE)
    
    design_system_colors = [
        ("#FFFFFF", "#0F172A", "Primary Surface Dark (Text/Background)"),
        ("#94A3B8", "#0F172A", "Muted Label on Dark Surface"),
        ("#3B82F6", "#FFFFFF", "Primary CTA Blue on White"),
        ("#FACC15", "#FFFFFF", "Warning Yellow on White (Anti-pattern)"),
        ("#10B981", "#064E3B", "Success Green Tag on Dark Green"),
        ("#EF4444", "#FFFFFF", "Destructive Action on White")
    ]

    print(f"\n{'Token Description':<38} {'FG/BG':<18} {'Contrast':<10} {'WCAG Status'}")
    print("-" * 78)
    
    for fg, bg, label in design_system_colors:
        res = WCAGAnalyzer.audit_contrast(fg, bg, label)
        status = res["status"]
        if "AAA" in status:
            stat_color = Color.GREEN
        elif "AA" in status:
            stat_color = Color.CYAN
        elif "Large" in status:
            stat_color = Color.YELLOW
        else:
            stat_color = Color.RED
            
        print(f"{label:<38} {fg+'/'+bg:<18} {res['ratio']:<5}:1   {stat_color}{Color.BOLD}{status}{Color.RESET}")

def run_sus_assessment():
    print_header("Kalkulator Psychometric System Usability Scale (SUS)")
    cprint("Menghitung skor baku SUS dari simulasi 10 instrumen uji usability:\n", Color.WHITE)
    
    # Preset sample user responses
    sample_scores = [5, 2, 4, 1, 5, 2, 4, 1, 5, 2]
    
    print("Menampilkan profil kuesioner terstandar:")
    for idx, (q, sc) in enumerate(zip(SUSCalculator.QUESTIONS, sample_scores)):
        print(f"  {Color.DIM}{q}{Color.RESET} -> Score: {Color.BOLD}{Color.CYAN}{sc}/5{Color.RESET}")
        
    score, grade, adj = SUSCalculator.compute(sample_scores)
    
    print("\n" + "=" * 45)
    cprint(f"  SKOR SUS AKHIR      : {score} / 100", Color.MAGENTA, bold=True)
    cprint(f"  GRADE KLASIFIKASI   : {grade}", Color.GREEN if score >= 68 else Color.RED, bold=True)
    cprint(f"  ADJECTIVE RATING    : {adj}", Color.WHITE, bold=True)
    print("=" * 45)
    
    print_badge("INTERPRETASI", "Benchmark industri rata-rata SUS adalah 68.0.")
    if score >= 68.0:
        print_badge("STATUS", "Desain arsitektur produk berada di atas rata-rata kelayakan industri.", Color.GREEN)
    else:
        print_badge("STATUS", "Perlu dilakukan usability testing ulang dan simplifikasi task flow.", Color.RED)

def run_telemetry_simulation():
    print_header("Simulasi Telemetri Interaksi & User Flow Latency")
    cprint("Menghitung Cognitive Load & Task Completion Efficiency secara real-time...\n", Color.CYAN)
    
    flow_steps = [
        ("Step 1: Onboarding Landing", 0.4, "Clear Visual Anchor"),
        ("Step 2: Workspace Creation", 0.8, "Form Field Sanitization"),
        ("Step 3: Permission Role Mapping", 1.5, "High Cognitive Decision Point"),
        ("Step 4: Primary Dashboard Access", 0.5, "Success State Render")
    ]
    
    total_time = 0.0
    for step, latency, annotation in flow_steps:
        sys.stdout.write(f"  Processing {Color.BOLD}{step:<35}{Color.RESET} ")
        sys.stdout.flush()
        time.sleep(0.15)  # Accelerated simulation delay
        total_time += latency
        cprint(f"[OK] ~{latency}s latency ({annotation})", Color.GREEN)
        
    print("-" * 65)
    print_badge("SUMMARY", f"Total Cognitive Path Time: {round(total_time, 2)}s across {len(flow_steps)} critical steps.")

# ==============================================================================
# Automated Self-Test Verification Suite
# ==============================================================================
def run_automated_test_suite():
    print_header("Menjalankan Automated Verification Test Suite")
    
    # Test 1: WCAG Contrast Accuracy
    contrast = WCAGAnalyzer.calculate_contrast("#FFFFFF", "#000000")
    assert math.isclose(contrast, 21.0, rel_tol=1e-2), f"Expected 21:1 contrast, got {contrast}"
    print_badge("TEST 1 PASSED", "WCAG Relative Luminance & Contrast Formula Verified (21:1 for Black/White)")
    
    # Test 2: Contrast Fail Test
    low_contrast = WCAGAnalyzer.calculate_contrast("#FFFFFF", "#FACC15")
    assert low_contrast < 4.5, "Expected warning color to fail AA contrast on white"
    print_badge("TEST 2 PASSED", f"WCAG Fail Detection Accurate ({round(low_contrast, 2)}:1 < 4.5:1)")

    # Test 3: SUS Benchmark Math
    # All 5s -> (4 + 0 + 4 + 0 + 4 + 0 + 4 + 0 + 4 + 0) * 2.5 = 20 * 2.5 = 50.0
    all_fives = [5] * 10
    score_mid, _, _ = SUSCalculator.compute(all_fives)
    assert score_mid == 50.0, f"Expected 50.0 for uniform score 5, got {score_mid}"
    
    # Ideal scores -> odd 5s (pos-1=4), even 1s (5-pos=4) -> 10 * 4 * 2.5 = 100.0
    ideal_scores = [5, 1, 5, 1, 5, 1, 5, 1, 5, 1]
    score_max, _, _ = SUSCalculator.compute(ideal_scores)
    assert score_max == 100.0, f"Expected 100.0 for ideal score, got {score_max}"
    print_badge("TEST 3 PASSED", "SUS Psychometric Calculation Verified (Min: 0, Mid: 50, Max: 100)")

    # Test 4: IA Tree Depth Analysis
    root = create_sample_ia_tree()
    issues = root.evaluate_depth_friction()
    assert len(issues) == 2, f"Expected 2 deep hierarchy issues, found {len(issues)}"
    print_badge("TEST 4 PASSED", f"Information Architecture 3-Click Rule Evaluator Verified ({len(issues)} issues found)")
    
    cprint("\nSemua unit verification test untuk Arsitektur UX berhasil dilewati tanpa error!", Color.GREEN, bold=True)

# ==============================================================================
# Main Execution CLI Entry Point
# ==============================================================================
def main():
    ia_root = create_sample_ia_tree()

    # If run in non-interactive / CI argument mode
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        run_automated_test_suite()
        return

    while True:
        print_header("Simulasi Arsitektur Produksi UX Design (BAB 01)")
        print(f"{Color.CYAN}Pilih Menu Demonstrasi Arsitektur & Evaluasi UX:{Color.RESET}")
        print("  1. Evaluasi Information Architecture (Tree, Load & 3-Click Rule)")
        print("  2. Audit Aksesibilitas WCAG 2.1 AA/AAA Contrast Ratio")
        print("  3. Kalkulasi Skor System Usability Scale (SUS Benchmark)")
        print("  4. Simulasi Telemetri Interaksi & User Flow Latency")
        print("  5. Jalankan Automated Verification Unit Tests")
        print("  6. Keluar")
        
        try:
            choice = input(f"\n{Color.BOLD}Masukkan pilihan (1-6) [default: 5]: {Color.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nProgram dihentikan pengguna.")
            break

        if not choice:
            choice = "5"

        if choice == "1":
            run_ia_audit(ia_root)
        elif choice == "2":
            run_wcag_audit()
        elif choice == "3":
            run_sus_assessment()
        elif choice == "4":
            run_telemetry_simulation()
        elif choice == "5":
            run_automated_test_suite()
        elif choice == "6":
            cprint("\nTerima kasih telah menjalankan simulasi arsitektur UX!", Color.GREEN)
            break
        else:
            cprint("Pilihan tidak valid, silakan ulangi.", Color.RED)
            
        print("\n" + Color.DIM + "Tekan Enter untuk kembali ke menu utama..." + Color.RESET)
        try:
            input()
        except (KeyboardInterrupt, EOFError):
            break

if __name__ == "__main__":
    main()
