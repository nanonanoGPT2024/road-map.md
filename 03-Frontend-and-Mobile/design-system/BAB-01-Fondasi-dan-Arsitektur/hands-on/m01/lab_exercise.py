#!/usr/bin/env python3
"""
Lab Exercise: Fondasi & Arsitektur Design System (BAB-01)
Simulasi Interaktif: Token 3-Tier Architecture, Theme Resolver, & Accessibility Check.

Materi Lab:
1. Tier 1: Core / Global Primitive Tokens
2. Tier 2: Semantic Tokens (Light & Dark Theme Mapping)
3. Tier 3: Component-Scoped Tokens
4. Token Resolution Engine (Alias Pointer dereferencing)
5. WCAG AA Contrast Ratio Validator & ANSI Component Terminal Renderer
"""

import sys
import re
import math
from typing import Dict, Any, Tuple, Optional

# --- ANSI Terminal Styling Helper ---
class Terminal:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"

    # Standard Colors
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    @staticmethod
    def rgb_fg(r: int, g: int, b: int) -> str:
        return f"\033[38;2;{r};{g};{b}m"

    @staticmethod
    def rgb_bg(r: int, g: int, b: int) -> str:
        return f"\033[48;2;{r};{g};{b}m"

    @staticmethod
    def hex_to_rgb(hex_code: str) -> Tuple[int, int, int]:
        clean_hex = hex_code.lstrip('#')
        if len(clean_hex) == 3:
            clean_hex = "".join([c*2 for c in clean_hex])
        return tuple(int(clean_hex[i:i+2], 16) for i in (0, 2, 4))


# --- 1. Tier 1: Global Primitive Tokens ---
GLOBAL_PRIMITIVES: Dict[str, Any] = {
    # Color Palette (Primitives)
    "color.blue.50": "#EFF6FF",
    "color.blue.500": "#3B82F6",
    "color.blue.600": "#2563EB",
    "color.blue.900": "#1E3A8A",

    "color.neutral.0": "#FFFFFF",
    "color.neutral.100": "#F3F4F6",
    "color.neutral.200": "#E5E7EB",
    "color.neutral.700": "#374151",
    "color.neutral.800": "#1F2937",
    "color.neutral.900": "#111827",

    "color.emerald.500": "#10B981",
    "color.rose.500": "#F43F5E",

    # Spacing Units (8pt Grid System)
    "spacing.0": "0px",
    "spacing.1": "4px",
    "spacing.2": "8px",
    "spacing.3": "12px",
    "spacing.4": "16px",
    "spacing.6": "24px",

    # Border Radius
    "radius.sm": "4px",
    "radius.md": "8px",
    "radius.full": "9999px",
}


# --- 2. Tier 2: Semantic Tokens per Theme ---
SEMANTIC_TOKENS: Dict[str, Dict[str, str]] = {
    "light": {
        "color.bg.canvas": "{color.neutral.100}",
        "color.bg.surface": "{color.neutral.0}",
        "color.text.primary": "{color.neutral.900}",
        "color.text.secondary": "{color.neutral.700}",
        "color.text.inverse": "{color.neutral.0}",
        "color.border.subtle": "{color.neutral.200}",
        "color.interactive.brand": "{color.blue.600}",
        "color.interactive.brand-hover": "{color.blue.900}",
        "color.status.success": "{color.emerald.500}",
        "color.status.error": "{color.rose.500}",
    },
    "dark": {
        "color.bg.canvas": "{color.neutral.900}",
        "color.bg.surface": "{color.neutral.800}",
        "color.text.primary": "{color.neutral.100}",
        "color.text.secondary": "{color.neutral.200}",
        "color.text.inverse": "{color.neutral.900}",
        "color.border.subtle": "{color.neutral.700}",
        "color.interactive.brand": "{color.blue.500}",
        "color.interactive.brand-hover": "{color.blue.600}",
        "color.status.success": "{color.emerald.500}",
        "color.status.error": "{color.rose.500}",
    }
}


# --- 3. Tier 3: Component-Scoped Tokens ---
COMPONENT_TOKENS: Dict[str, Dict[str, str]] = {
    "button.primary": {
        "bg": "{color.interactive.brand}",
        "bg-hover": "{color.interactive.brand-hover}",
        "text": "{color.text.inverse}",
        "border": "transparent",
        "padding-x": "{spacing.4}",
        "padding-y": "{spacing.2}",
        "radius": "{radius.md}",
    },
    "card.standard": {
        "bg": "{color.bg.surface}",
        "text": "{color.text.primary}",
        "border": "{color.border.subtle}",
        "padding": "{spacing.6}",
        "radius": "{radius.md}",
    }
}


# --- Token Resolution Engine ---
class DesignTokenEngine:
    def __init__(self, theme: str = "light"):
        self.theme = theme
        self.max_depth = 5

    def set_theme(self, theme: str) -> None:
        if theme not in SEMANTIC_TOKENS:
            raise ValueError(f"Tema '{theme}' tidak tersedia. Pilih 'light' atau 'dark'.")
        self.theme = theme

    def resolve(self, token_expr: str, depth: int = 0) -> str:
        if depth > self.max_depth:
            raise RecursionError(f"Terdeteksi circular dependency pada token: {token_expr}")

        # Identifikasi pola alias `{token.name}`
        match = re.match(r"^\{([\w\.\-]+)\}$", token_expr.strip())
        if not match:
            return token_expr  # Nilai literal (misal: hex string, px, transparent)

        token_key = match.group(1)

        # Cek Tier 2 Semantic Token sesuai tema aktif
        current_semantics = SEMANTIC_TOKENS.get(self.theme, {})
        if token_key in current_semantics:
            return self.resolve(current_semantics[token_key], depth + 1)

        # Cek Tier 1 Global Primitives
        if token_key in GLOBAL_PRIMITIVES:
            return self.resolve(GLOBAL_PRIMITIVES[token_key], depth + 1)

        raise KeyError(f"Token '{token_key}' tidak ditemukan di catalog Tier-1 maupun Tier-2.")

    def resolve_component(self, component_name: str) -> Dict[str, str]:
        if component_name not in COMPONENT_TOKENS:
            raise KeyError(f"Komponen '{component_name}' belum didefinisikan.")
        
        raw_defs = COMPONENT_TOKENS[component_name]
        resolved = {}
        for prop, val in raw_defs.items():
            resolved[prop] = self.resolve(val)
        return resolved


# --- WCAG 2.1 Contrast Ratio Calculator ---
class AccessibilityAuditor:
    @staticmethod
    def _srgb_channel_to_luminance(c: float) -> float:
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else math.pow((c + 0.055) / 1.055, 2.4)

    @classmethod
    def calculate_relative_luminance(cls, hex_color: str) -> float:
        r, g, b = Terminal.hex_to_rgb(hex_color)
        r_lum = cls._srgb_channel_to_luminance(r)
        g_lum = cls._srgb_channel_to_luminance(g)
        b_lum = cls._srgb_channel_to_luminance(b)
        return 0.2126 * r_lum + 0.7152 * g_lum + 0.0722 * b_lum

    @classmethod
    def contrast_ratio(cls, hex1: str, hex2: str) -> float:
        lum1 = cls.calculate_relative_luminance(hex1)
        lum2 = cls.calculate_relative_luminance(hex2)
        lighter = max(lum1, lum2)
        darker = min(lum1, lum2)
        return (lighter + 0.05) / (darker + 0.05)

    @classmethod
    def evaluate_compliance(cls, ratio: float) -> Tuple[bool, bool, str]:
        aa_normal = ratio >= 4.5
        aaa_normal = ratio >= 7.0
        status = "AAA Pass" if aaa_normal else ("AA Pass" if aa_normal else "Fail")
        return aa_normal, aaa_normal, status


# --- Terminal UI Renderer ---
def render_header(title: str) -> None:
    print(f"\n{Terminal.CYAN}{Terminal.BOLD}===================================================================={Terminal.RESET}")
    print(f"{Terminal.CYAN}{Terminal.BOLD}  {title}{Terminal.RESET}")
    print(f"{Terminal.CYAN}{Terminal.BOLD}===================================================================={Terminal.RESET}\n")


def display_token_trace(engine: DesignTokenEngine, component_key: str, property_key: str) -> None:
    raw_val = COMPONENT_TOKENS[component_key][property_key]
    match = re.match(r"^\{([\w\.\-]+)\}$", raw_val.strip())
    
    print(f"{Terminal.BOLD}Resolusi Hirarki Token [{component_key}.{property_key}]:{Terminal.RESET}")
    print(f"  [Tier 3 Component] : {Terminal.MAGENTA}{raw_val}{Terminal.RESET}")
    
    if match:
        sem_key = match.group(1)
        sem_val = SEMANTIC_TOKENS[engine.theme].get(sem_key, "N/A")
        print(f"  [Tier 2 Semantic ] : {Terminal.YELLOW}{sem_key}{Terminal.RESET} -> {Terminal.YELLOW}{sem_val}{Terminal.RESET} (Theme: {engine.theme})")
        
        sem_match = re.match(r"^\{([\w\.\-]+)\}$", sem_val.strip())
        if sem_match:
            prim_key = sem_match.group(1)
            prim_val = GLOBAL_PRIMITIVES.get(prim_key, "N/A")
            print(f"  [Tier 1 Primitive] : {Terminal.GREEN}{prim_key}{Terminal.RESET} -> {Terminal.GREEN}{prim_val}{Terminal.RESET}")
            resolved_hex = engine.resolve(raw_val)
            print(f"  [Calculated Value] : {Terminal.BOLD}{resolved_hex}{Terminal.RESET}")


def render_preview_box(engine: DesignTokenEngine) -> None:
    btn = engine.resolve_component("button.primary")
    card = engine.resolve_component("card.standard")
    
    bg_card_rgb = Terminal.hex_to_rgb(card["bg"])
    text_card_rgb = Terminal.hex_to_rgb(card["text"])
    btn_bg_rgb = Terminal.hex_to_rgb(btn["bg"])
    btn_text_rgb = Terminal.hex_to_rgb(btn["text"])

    card_bg_ansi = Terminal.rgb_bg(*bg_card_rgb)
    card_text_ansi = Terminal.rgb_fg(*text_card_rgb)
    btn_bg_ansi = Terminal.rgb_bg(*btn_bg_rgb)
    btn_text_ansi = Terminal.rgb_fg(*btn_text_rgb)

    print(f"\n{Terminal.BOLD}Visual Preview Rendering (Virtual Terminal Canvas):{Terminal.RESET}")
    print(f"{card_bg_ansi}{card_text_ansi}┌────────────────────────────────────────────────────────────┐{Terminal.RESET}")
    print(f"{card_bg_ansi}{card_text_ansi}│  Card Container [{card['radius']}] (Theme: {engine.theme.upper():<6})                     │{Terminal.RESET}")
    print(f"{card_bg_ansi}{card_text_ansi}│  Semantic Surface: {card['bg']:<7} | Text: {card['text']:<7}            │{Terminal.RESET}")
    print(f"{card_bg_ansi}{card_text_ansi}│                                                            │{Terminal.RESET}")
    
    # Tombol di dalam card
    btn_label = " [ Confirm Action ] "
    print(f"{card_bg_ansi}{card_text_ansi}│    Action: {btn_bg_ansi}{btn_text_ansi}{Terminal.BOLD}{btn_label}{Terminal.RESET}{card_bg_ansi}{card_text_ansi}                                │{Terminal.RESET}")
    print(f"{card_bg_ansi}{card_text_ansi}│    (Button Bg: {btn['bg']}, Text: {btn['text']}, Pad: {btn['padding-x']})       │{Terminal.RESET}")
    print(f"{card_bg_ansi}{card_text_ansi}└────────────────────────────────────────────────────────────┘{Terminal.RESET}\n")


def run_accessibility_audit(engine: DesignTokenEngine) -> None:
    btn = engine.resolve_component("button.primary")
    card = engine.resolve_component("card.standard")
    
    print(f"{Terminal.BOLD}Audit Aksesibilitas (WCAG 2.1 Contrast Ratio):{Terminal.RESET}")
    
    tests = [
        ("Button Primary (Text vs BG)", btn["text"], btn["bg"]),
        ("Card Surface (Text vs BG)", card["text"], card["bg"]),
    ]

    for label, fg, bg in tests:
        ratio = AccessibilityAuditor.contrast_ratio(fg, bg)
        aa, aaa, status = AccessibilityAuditor.evaluate_compliance(ratio)
        badge_color = Terminal.GREEN if aa else Terminal.RED
        print(f"  • {label:<32} : {fg} on {bg}")
        print(f"    Ratio: {ratio:.2f}:1 -> {badge_color}{Terminal.BOLD}[{status}]{Terminal.RESET}")


def interactive_simulation():
    engine = DesignTokenEngine(theme="light")
    render_header("Design System Studio: BAB-01 Fondasi & Arsitektur")

    print(f"{Terminal.BOLD}Menu Simulasi Interaktif:{Terminal.RESET}")
    print("1. Tampilkan Token Architecture (Tier 1 -> Tier 2 -> Tier 3)")
    print("2. Simulasi Resolusi & Audit Tema Light")
    print("3. Simulasi Switch ke Tema Dark (Hot Reload)")
    print("4. Jalankan Self-Verification Test Suite")
    print("5. Keluar")

    while True:
        try:
            choice = input(f"\n{Terminal.CYAN}Pilih opsi (1-5, atau Enter untuk rotasi tema otomatis): {Terminal.RESET}").strip()
            if not choice or choice == "auto":
                # Otomatis peragakan kedua tema
                print(f"\n{Terminal.YELLOW}>>> Menjalankan demonstrasi komparasi tema (Light vs Dark) <<<{Terminal.RESET}")
                for theme in ["light", "dark"]:
                    engine.set_theme(theme)
                    render_header(f"Mode Desain Aktif: {theme.upper()} THEME")
                    display_token_trace(engine, "button.primary", "bg")
                    display_token_trace(engine, "button.primary", "text")
                    render_preview_box(engine)
                    run_accessibility_audit(engine)
                break
            elif choice == "1":
                display_token_trace(engine, "button.primary", "bg")
                display_token_trace(engine, "card.standard", "bg")
            elif choice == "2":
                engine.set_theme("light")
                render_header("Tema Aktif: LIGHT")
                render_preview_box(engine)
                run_accessibility_audit(engine)
            elif choice == "3":
                engine.set_theme("dark")
                render_header("Tema Aktif: DARK")
                render_preview_box(engine)
                run_accessibility_audit(engine)
            elif choice == "4":
                run_test_suite()
            elif choice == "5" or choice.lower() == "exit":
                print(f"{Terminal.GREEN}Simulasi selesai. Fondasi arsitektur terverifikasi.{Terminal.RESET}")
                break
            else:
                print(f"{Terminal.RED}Pilihan tidak valid. Silakan pilih 1-5.{Terminal.RESET}")
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Terminal.YELLOW}Simulasi dihentikan.{Terminal.RESET}")
            break


def run_test_suite():
    print(f"\n{Terminal.BOLD}--- Menjalankan Unit & Architecture Tests ---{Terminal.RESET}")
    engine = DesignTokenEngine()
    
    # Test 1: Resolution Tier 1
    t1_val = engine.resolve("{color.blue.500}")
    assert t1_val == "#3B82F6", f"Expected #3B82F6, got {t1_val}"
    print(f"  {Terminal.GREEN}✔ Test 1 passed:{Terminal.RESET} Tier-1 primitive resolution")

    # Test 2: Multi-hop resolution (Component -> Semantic -> Primitive)
    engine.set_theme("light")
    btn_bg = engine.resolve(COMPONENT_TOKENS["button.primary"]["bg"])
    assert btn_bg == "#2563EB", f"Expected #2563EB for light button.bg, got {btn_bg}"
    print(f"  {Terminal.GREEN}✔ Test 2 passed:{Terminal.RESET} 3-Tier Multi-hop pointer dereferencing (Light)")

    # Test 3: Theme switching updates resolved value
    engine.set_theme("dark")
    btn_bg_dark = engine.resolve(COMPONENT_TOKENS["button.primary"]["bg"])
    assert btn_bg_dark == "#3B82F6", f"Expected #3B82F6 for dark button.bg, got {btn_bg_dark}"
    print(f"  {Terminal.GREEN}✔ Test 3 passed:{Terminal.RESET} Theme switching updates semantic resolution (Dark)")

    # Test 4: Contrast Ratio Math
    ratio = AccessibilityAuditor.contrast_ratio("#FFFFFF", "#000000")
    assert math.isclose(ratio, 21.0, rel_tol=1e-2), f"Expected 21:1 contrast, got {ratio}"
    print(f"  {Terminal.GREEN}✔ Test 4 passed:{Terminal.RESET} WCAG Luminance and Contrast calculation")

    print(f"{Terminal.GREEN}{Terminal.BOLD}Semua 4/4 test lolos verifikasi arsitektur!{Terminal.RESET}\n")


if __name__ == "__main__":
    if "--test" in sys.argv:
        run_test_suite()
    else:
        # Menjalankan rotasi otomatis atau interaktif
        if len(sys.argv) > 1 and sys.argv[1] == "--auto":
            engine = DesignTokenEngine("light")
            for t in ["light", "dark"]:
                engine.set_theme(t)
                render_header(f"DEMO ARSITEKTUR DESIGN SYSTEM: {t.upper()} MODE")
                display_token_trace(engine, "button.primary", "bg")
                render_preview_box(engine)
                run_accessibility_audit(engine)
            run_test_suite()
        else:
            interactive_simulation()
