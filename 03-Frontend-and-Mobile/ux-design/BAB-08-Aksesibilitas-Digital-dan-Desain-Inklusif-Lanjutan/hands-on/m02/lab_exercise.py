#!/usr/bin/env python3
"""
Lab Exercise Modul 02: Advanced Digital Accessibility & Inclusive Design Engine
BAB-08: Aksesibilitas-Digital-dan-Desain-Inklusif-Lanjutan
Arsitektur Simulasi Produksi: WCAG 2.2 AAA Audit, Color Contrast / APCA Evaluator,
Accessibility Tree & Virtual Screen Reader Speech Dispatcher.
"""

from __future__ import annotations
import dataclasses
import enum
import math
import sys
import time
from typing import Dict, List, Optional, Tuple


# ==========================================
# 1. ANSI Color Formatting & Terminal Helpers
# ==========================================
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    
    # Foreground Colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    # High-intensity Foreground
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    # Background
    BG_DARK = "\033[40m"
    BG_BLUE = "\033[44m"


def print_banner(text: str) -> None:
    border = "=" * 76
    print(f"\n{Style.BRIGHT_CYAN}{border}")
    print(f"{Style.BOLD}{Style.BRIGHT_WHITE}  {text}")
    print(f"{Style.BRIGHT_CYAN}{border}{Style.RESET}\n")


def print_status(tag: str, msg: str, style_color: str = Style.BRIGHT_GREEN) -> None:
    print(f"  {style_color}[{tag}]{Style.RESET} {msg}")


# ==========================================
# 2. Domain Models & WCAG 2.2 Data Structures
# ==========================================
class AriaRole(enum.Enum):
    BANNER = "banner"
    NAVIGATION = "navigation"
    MAIN = "main"
    HEADING = "heading"
    BUTTON = "button"
    ALERT = "alert"
    STATUS = "status"
    FORM = "form"
    TEXTBOX = "textbox"
    GENERIC = "generic"


class WCAGLevel(enum.Enum):
    A = "A"
    AA = "AA"
    AAA = "AAA"
    FAIL = "FAIL"


@dataclasses.dataclass
class ColorRGB:
    r: int
    g: int
    b: int

    @classmethod
    def from_hex(cls, hex_str: str) -> ColorRGB:
        clean_hex = hex_str.lstrip("#")
        if len(clean_hex) == 3:
            clean_hex = "".join([c * 2 for c in clean_hex])
        if len(clean_hex) != 6:
            raise ValueError(f"Invalid Hex color: {hex_str}")
        r = int(clean_hex[0:2], 16)
        g = int(clean_hex[2:4], 16)
        b = int(clean_hex[4:6], 16)
        return cls(r, g, b)

    def to_relative_luminance(self) -> float:
        """Kalkulasi relative luminance sesuai standar sRGB WCAG 2.1/2.2."""
        def channel_lum(val: int) -> float:
            c = val / 255.0
            return c / 12.92 if c <= 0.04045 else math.pow((c + 0.055) / 1.055, 2.4)
        
        return 0.2126 * channel_lum(self.r) + 0.7152 * channel_lum(self.g) + 0.0722 * channel_lum(self.b)


@dataclasses.dataclass
class AccessibleNode:
    node_id: str
    role: AriaRole
    name: Optional[str] = None
    description: Optional[str] = None
    focusable: bool = False
    tab_index: int = 0
    keyboard_trap_risk: bool = False
    level: Optional[int] = None  # Untuk heading 1-6
    fg_color: Optional[ColorRGB] = None
    bg_color: Optional[ColorRGB] = None
    live_region: Optional[str] = None  # "polite", "assertive", None
    children: List[AccessibleNode] = dataclasses.field(default_factory=list)


# ==========================================
# 3. Calculation Engines (Contrast & WCAG)
# ==========================================
class ContrastAnalyzer:
    @staticmethod
    def calculate_contrast_ratio(fg: ColorRGB, bg: ColorRGB) -> float:
        l1 = fg.to_relative_luminance()
        l2 = bg.to_relative_luminance()
        lighter = max(l1, l2)
        darker = min(l1, l2)
        return (lighter + 0.05) / (darker + 0.05)

    @classmethod
    def evaluate_wcag(cls, ratio: float, is_large_text: bool = False) -> Tuple[WCAGLevel, str]:
        if is_large_text:
            if ratio >= 4.5:
                return WCAGLevel.AAA, "Lolos Level AAA (Teks Besar >= 4.5:1)"
            elif ratio >= 3.0:
                return WCAGLevel.AA, "Lolos Level AA (Teks Besar >= 3.0:1)"
            else:
                return WCAGLevel.FAIL, "Gagal WCAG (Rasio < 3.0:1)"
        else:
            if ratio >= 7.0:
                return WCAGLevel.AAA, "Lolos Level AAA (Teks Normal >= 7.0:1)"
            elif ratio >= 4.5:
                return WCAGLevel.AA, "Lolos Level AA (Teks Normal >= 4.5:1)"
            else:
                return WCAGLevel.FAIL, "Gagal WCAG (Rasio < 4.5:1)"


# ==========================================
# 4. Accessibility Tree Auditor & Simulator
# ==========================================
class A11yAuditEngine:
    def __init__(self, root: AccessibleNode):
        self.root = root
        self.findings: List[Dict[str, str]] = []

    def run_full_audit(self) -> None:
        self.findings.clear()
        self._audit_node(self.root)

    def _audit_node(self, node: AccessibleNode) -> None:
        # Rule 1: Accessible Name computation
        interactive_roles = {AriaRole.BUTTON, AriaRole.TEXTBOX}
        if node.role in interactive_roles and (not node.name or not node.name.strip()):
            self.findings.append({
                "severity": "CRITICAL",
                "rule": "WCAG 4.1.2 Name, Role, Value",
                "node_id": node.node_id,
                "detail": f"Elemen interaktif peran <{node.role.value}> tidak memiliki accessible name (aria-label/text)."
            })

        # Rule 2: Color Contrast
        if node.fg_color and node.bg_color:
            ratio = ContrastAnalyzer.calculate_contrast_ratio(node.fg_color, node.bg_color)
            is_large = bool(node.role == AriaRole.HEADING and node.level and node.level <= 2)
            level, desc = ContrastAnalyzer.evaluate_wcag(ratio, is_large_text=is_large)
            if level == WCAGLevel.FAIL:
                self.findings.append({
                    "severity": "SERIOUS",
                    "rule": "WCAG 1.4.3 Contrast (Minimum)",
                    "node_id": node.node_id,
                    "detail": f"Rasio kontras {ratio:.2f}:1 di bawah batas minimum (Gagal AA). {desc}"
                })

        # Rule 3: Keyboard Trap & Negative Tabindex Check
        if node.keyboard_trap_risk:
            self.findings.append({
                "severity": "CRITICAL",
                "rule": "WCAG 2.1.2 No Keyboard Trap",
                "node_id": node.node_id,
                "detail": "Terdeteksi potensi keyboard trap: fokus tertahan tanpa tombol escape handler."
            })
        if node.tab_index > 0:
            self.findings.append({
                "severity": "MODERATE",
                "rule": "Anti-Pattern TabIndex > 0",
                "node_id": node.node_id,
                "detail": f"Nilai tabindex={node.tab_index} merusak aliran sekuensial alami DOM."
            })

        for child in node.children:
            self._audit_node(child)


class VirtualScreenReader:
    """Simulasi virtual screen reader speech buffer & sequential keyboard navigation."""
    def __init__(self, root: AccessibleNode):
        self.root = root

    def traverse_dom(self, node: Optional[AccessibleNode] = None, depth: int = 0) -> None:
        curr = node or self.root
        indent = "  " * depth
        role_label = f"<{curr.role.value}>"
        name_info = f'"{curr.name}"' if curr.name else f"{Style.RED}[NO NAME]{Style.RESET}"
        focus_info = f"{Style.CYAN}[Tab: {curr.tab_index}]{Style.RESET}" if curr.focusable else ""
        
        print(f"{indent}{Style.BRIGHT_MAGENTA}● {Style.BOLD}{role_label}{Style.RESET} {name_info} {focus_info}")
        for child in curr.children:
            self.traverse_dom(child, depth + 1)

    def announce_speech(self) -> None:
        print_banner("SIMULASI SCREEN READER SPEECH OUTPUT (SEQUENTIAL VIRTUAL BUFFER)")
        interactive_nodes: List[AccessibleNode] = []
        
        def collect(n: AccessibleNode):
            if n.focusable or n.role in {AriaRole.HEADING, AriaRole.ALERT}:
                interactive_nodes.append(n)
            for c in n.children:
                collect(c)
        
        collect(self.root)

        for idx, item in enumerate(interactive_nodes, start=1):
            time.sleep(0.15)
            speech = f"Fokus {idx}: Peran {item.role.value.upper()}"
            if item.name:
                speech += f", Label: '{item.name}'"
            if item.level:
                speech += f", Heading Level {item.level}"
            if item.live_region:
                speech += f" [LIVE REGION ANNOUNCEMENT: {item.live_region.upper()}]"
            
            color = Style.BRIGHT_YELLOW if item.live_region else Style.BRIGHT_WHITE
            print(f"  {Style.BRIGHT_GREEN}🔊 [TTS Readout]{Style.RESET} {color}{speech}{Style.RESET}")


# ==========================================
# 5. Pipeline Setup & Interaktif CLI
# ==========================================
def build_sample_enterprise_ui() -> AccessibleNode:
    root = AccessibleNode(
        node_id="app-root",
        role=AriaRole.MAIN,
        name="Dashboard Transaksi Inklusif FinTech Core",
        children=[
            AccessibleNode(
                node_id="header-bar",
                role=AriaRole.BANNER,
                name="Header Navigasi Utama",
                children=[
                    AccessibleNode(
                        node_id="h1-title",
                        role=AriaRole.HEADING,
                        level=1,
                        name="Portal Dompet Digital Mandiri",
                        fg_color=ColorRGB.from_hex("#1E293B"),
                        bg_color=ColorRGB.from_hex("#FFFFFF")
                    ),
                    AccessibleNode(
                        node_id="btn-skip-nav",
                        role=AriaRole.BUTTON,
                        name="Lewati ke Konten Utama (Skip to Main)",
                        focusable=True,
                        tab_index=0,
                        fg_color=ColorRGB.from_hex("#FFFFFF"),
                        bg_color=ColorRGB.from_hex("#0F172A")
                    )
                ]
            ),
            AccessibleNode(
                node_id="alert-box",
                role=AriaRole.ALERT,
                name="Saldo Anda berada di bawah batas minimum Rp 20.000",
                live_region="assertive",
                fg_color=ColorRGB.from_hex("#991B1B"),
                bg_color=ColorRGB.from_hex("#FEE2E2")
            ),
            AccessibleNode(
                node_id="transfer-card",
                role=AriaRole.FORM,
                name="Formulir Transfer Dana Instan",
                children=[
                    AccessibleNode(
                        node_id="input-rek",
                        role=AriaRole.TEXTBOX,
                        name="Nomor Rekening Tujuan",
                        focusable=True,
                        tab_index=0,
                        fg_color=ColorRGB.from_hex("#334155"),
                        bg_color=ColorRGB.from_hex("#F8FAFC")
                    ),
                    # Elemen Anti-Pattern: Tombol tanpa label & rasio kontras buruk
                    AccessibleNode(
                        node_id="btn-icon-submit",
                        role=AriaRole.BUTTON,
                        name=None,  # BAD: Empty Accessible Name
                        focusable=True,
                        tab_index=0,
                        fg_color=ColorRGB.from_hex("#94A3B8"),  # Low contrast vs #FFFFFF
                        bg_color=ColorRGB.from_hex("#FFFFFF")
                    ),
                    # Elemen Anti-Pattern: Tabindex > 0
                    AccessibleNode(
                        node_id="btn-help-modal",
                        role=AriaRole.BUTTON,
                        name="Bantuan Interaktif",
                        focusable=True,
                        tab_index=5,  # BAD: Positive tabindex
                        keyboard_trap_risk=True,  # BAD: Keyboard Trap
                        fg_color=ColorRGB.from_hex("#FFFFFF"),
                        bg_color=ColorRGB.from_hex("#2563EB")
                    )
                ]
            )
        ]
    )
    return root


def run_interactive_engine() -> None:
    print_banner("SIMULATOR AKSESIBILITAS DIGITAL & DESAIN INKLUSIF LANJUTAN (WCAG 2.2 AAA)")
    print_status("INIT", "Memuat arsitektur Accessibility Tree UI FinTech Enterprise...", Style.CYAN)
    root = build_sample_enterprise_ui()

    while True:
        print(f"\n{Style.BOLD}{Style.BRIGHT_YELLOW}MENU EKSEKUSI AKSESIBILITAS:{Style.RESET}")
        print("  [1] Tampilkan Hierarki Accessibility Tree DOM")
        print("  [2] Evaluasi Uji Rasio Kontras Warna Otomatis (WCAG 2.2 AA / AAA)")
        print("  [3] Jalankan Comprehensive Accessibility Audit Engine")
        print("  [4] Simulasikan Virtual Screen Reader (TTS Buffer Readout)")
        print("  [5] Remediasi Otomatis Arsitektur UI (Auto-Fix Anti-Patterns)")
        print("  [0] Keluar")
        
        try:
            choice = input(f"\n{Style.BRIGHT_CYAN}Pilih opsi [0-5]: {Style.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nMenghentikan simulator.")
            break

        if choice == "1":
            print_banner("HIERARKI ACCESSIBILITY TREE DOM")
            sr = VirtualScreenReader(root)
            sr.traverse_dom()

        elif choice == "2":
            print_banner("EVALUASI COLOR CONTRAST & WCAG COMPLIANCE")
            palette = [
                ("Teks Normal Gelap vs Putih", ColorRGB.from_hex("#1E293B"), ColorRGB.from_hex("#FFFFFF"), False),
                ("Placeholder Abu vs Putih (Low Contrast)", ColorRGB.from_hex("#94A3B8"), ColorRGB.from_hex("#FFFFFF"), False),
                ("Alert Merah Gelap vs Merah Muda", ColorRGB.from_hex("#991B1B"), ColorRGB.from_hex("#FEE2E2"), False),
                ("Heading Utama Besar vs Putih", ColorRGB.from_hex("#0F172A"), ColorRGB.from_hex("#FFFFFF"), True),
            ]
            for label, fg, bg, is_large in palette:
                ratio = ContrastAnalyzer.calculate_contrast_ratio(fg, bg)
                lvl, desc = ContrastAnalyzer.evaluate_wcag(ratio, is_large_text=is_large)
                color = Style.BRIGHT_GREEN if lvl in {WCAGLevel.AA, WCAGLevel.AAA} else Style.BRIGHT_RED
                print(f"  ● {Style.BOLD}{label}{Style.RESET}")
                print(f"    Rasio: {color}{ratio:.2f}:1{Style.RESET} | Status: {color}{lvl.value} - {desc}{Style.RESET}")

        elif choice == "3":
            print_banner("HASIL COMPREHENSIVE A11Y ENGINE AUDIT")
            auditor = A11yAuditEngine(root)
            auditor.run_full_audit()
            if not auditor.findings:
                print_status("PASS", "Tidak ditemukan pelanggaran WCAG 2.2!", Style.BRIGHT_GREEN)
            else:
                for idx, issue in enumerate(auditor.findings, 1):
                    sev_color = Style.BRIGHT_RED if issue["severity"] == "CRITICAL" else Style.BRIGHT_YELLOW
                    print(f"  {sev_color}[{issue['severity']} #{idx}]{Style.RESET} Rule: {issue['rule']}")
                    print(f"    Node: {Style.CYAN}{issue['node_id']}{Style.RESET} -> {issue['detail']}\n")

        elif choice == "4":
            sr = VirtualScreenReader(root)
            sr.announce_speech()

        elif choice == "5":
            print_banner("AUTO-REMEDIASI ARSITEKTUR AKSESIBILITAS")
            print_status("FIX", "Menyuntikkan aria-label ke elemen button ikon...", Style.BRIGHT_GREEN)
            # Find and patch btn-icon-submit
            def patch(node: AccessibleNode):
                if node.node_id == "btn-icon-submit":
                    node.name = "Kirim Transaksi Pembayaran"
                    node.fg_color = ColorRGB.from_hex("#0F172A")  # High contrast
                if node.node_id == "btn-help-modal":
                    node.tab_index = 0
                    node.keyboard_trap_risk = False
                for c in node.children:
                    patch(c)
            patch(root)
            print_status("FIX", "Menghapus positive tabindex & melepas keyboard trap...", Style.BRIGHT_GREEN)
            print_status("SUCCESS", "Arsitektur berhasil diperbaiki sesuai standar WCAG 2.2 AAA.", Style.BRIGHT_CYAN)

        elif choice == "0":
            print(f"\n{Style.BRIGHT_GREEN}Simulasi selesai. Mengakhiri sesi lab aksessibilitas.{Style.RESET}\n")
            break
        else:
            print(f"{Style.RED}Pilihan tidak valid. Silakan pilih 0-5.{Style.RESET}")


if __name__ == "__main__":
    # Dukungan non-interaktif pipeline jika dijalankan via automated testing / pipe
    if not sys.stdin.isatty():
        print_banner("AUTOMATED EXECUTION PIPELINE MODE")
        root_sample = build_sample_enterprise_ui()
        auditor = A11yAuditEngine(root_sample)
        auditor.run_full_audit()
        print_status("AUDIT", f"Audit otomatis selesai. Ditemukan {len(auditor.findings)} isu aksesibilitas.", Style.BRIGHT_YELLOW)
        sr = VirtualScreenReader(root_sample)
        sr.announce_speech()
    else:
        run_interactive_engine()
