#!/usr/bin/env python3
"""
Lab Exercise: Design Systems Architecture & Design Token Engineering
BAB-06: Product Design Engineering Lab Simulation

Simulasi teknis arsitektur 3-tier design tokens:
1. Primitive Tokens (Global/Core)
2. Semantic Tokens (System/Alias/Contextual)
3. Component Tokens (Scoped)

Disertai:
- Multi-tier Token Resolution Engine
- Style Dictionary Exporter (CSS Variables & JSON)
- WCAG 2.1 Contrast Ratio Verification (Luminance check)
- ANSI Terminal Visual Previewer
"""

import sys
import json
import math
from typing import Dict, Any, Tuple, Optional

# --- ANSI Terminal Styling & Utilities ---
class TerminalColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    
    # Standard Foreground
    FG_RED = "\033[31m"
    FG_GREEN = "\033[32m"
    FG_YELLOW = "\033[33m"
    FG_BLUE = "\033[34m"
    FG_MAGENTA = "\033[35m"
    FG_CYAN = "\033[36m"
    FG_WHITE = "\033[37m"

    @staticmethod
    def hex_to_rgb(hex_code: str) -> Tuple[int, int, int]:
        clean_hex = hex_code.lstrip("#")
        if len(clean_hex) == 3:
            clean_hex = "".join([c * 2 for c in clean_hex])
        return (
            int(clean_hex[0:2], 16),
            int(clean_hex[2:4], 16),
            int(clean_hex[4:6], 16)
        )

    @classmethod
    def rgb_fg(cls, r: int, g: int, b: int) -> str:
        return f"\033[38;2;{r};{g};{b}m"

    @classmethod
    def rgb_bg(cls, r: int, g: int, b: int) -> str:
        return f"\033[48;2;{r};{g};{b}m"

    @classmethod
    def hex_badge(cls, text: str, fg_hex: str, bg_hex: str) -> str:
        fr, fg, fb = cls.hex_to_rgb(fg_hex)
        br, bg, bb = cls.hex_to_rgb(bg_hex)
        return f"{cls.rgb_bg(br, bg, bb)}{cls.rgb_fg(fr, fg, fb)} {text} {cls.RESET}"


# --- WCAG 2.1 Luminance & Contrast Calculator ---
class AccessibilityAuditor:
    @staticmethod
    def channel_luminance(c: float) -> float:
        c_norm = c / 255.0
        if c_norm <= 0.03928:
            return c_norm / 12.92
        return math.pow((c_norm + 0.055) / 1.055, 2.4)

    @classmethod
    def relative_luminance(cls, hex_color: str) -> float:
        r, g, b = TerminalColor.hex_to_rgb(hex_color)
        rl = cls.channel_luminance(r)
        gl = cls.channel_luminance(g)
        bl = cls.channel_luminance(b)
        return 0.2126 * rl + 0.7152 * gl + 0.0722 * bl

    @classmethod
    def contrast_ratio(cls, hex_fg: str, hex_bg: str) -> float:
        lum1 = cls.relative_luminance(hex_fg)
        lum2 = cls.relative_luminance(hex_bg)
        l_max = max(lum1, lum2)
        l_min = min(lum1, lum2)
        return (l_max + 0.05) / (l_min + 0.05)

    @classmethod
    def evaluate_compliance(cls, ratio: float) -> str:
        if ratio >= 7.0:
            return f"{TerminalColor.FG_GREEN}PASS AAA (>=7.0:1){TerminalColor.RESET}"
        elif ratio >= 4.5:
            return f"{TerminalColor.FG_CYAN}PASS AA (>=4.5:1){TerminalColor.RESET}"
        elif ratio >= 3.0:
            return f"{TerminalColor.FG_YELLOW}PASS Large-Text/UI only (>=3.0:1){TerminalColor.RESET}"
        else:
            return f"{TerminalColor.FG_RED}FAIL (<3.0:1){TerminalColor.RESET}"


# --- Token Definition Database (Multi-Tier) ---
PRIMITIVE_TOKENS: Dict[str, Any] = {
    # Color Palette Primitives
    "color.palette.neutral.0": "#FFFFFF",
    "color.palette.neutral.50": "#F9FAFB",
    "color.palette.neutral.100": "#F3F4F6",
    "color.palette.neutral.200": "#E5E7EB",
    "color.palette.neutral.700": "#374151",
    "color.palette.neutral.800": "#1F2937",
    "color.palette.neutral.900": "#111827",
    "color.palette.neutral.950": "#030712",
    "color.palette.blue.500": "#3B82F6",
    "color.palette.blue.600": "#2563EB",
    "color.palette.blue.700": "#1D4ED8",
    "color.palette.red.500": "#EF4444",
    "color.palette.red.600": "#DC2626",
    "color.palette.emerald.500": "#10B981",

    # Spacing Scale (4px base unit)
    "spacing.0": "0px",
    "spacing.1": "4px",
    "spacing.2": "8px",
    "spacing.3": "12px",
    "spacing.4": "16px",
    "spacing.6": "24px",
    "spacing.8": "32px",

    # Border Radii
    "radius.none": "0px",
    "radius.sm": "4px",
    "radius.md": "8px",
    "radius.lg": "12px",
    "radius.full": "9999px"
}

# Semantic Tier: references primitives via curly brackets
SEMANTIC_TOKENS_LIGHT: Dict[str, str] = {
    "color.surface.canvas": "{color.palette.neutral.50}",
    "color.surface.card": "{color.palette.neutral.0}",
    "color.surface.border": "{color.palette.neutral.200}",
    "color.text.primary": "{color.palette.neutral.900}",
    "color.text.secondary": "{color.palette.neutral.700}",
    "color.text.inverse": "{color.palette.neutral.0}",
    "color.action.primary.default": "{color.palette.blue.600}",
    "color.action.primary.hover": "{color.palette.blue.700}",
    "color.action.danger.default": "{color.palette.red.600}",
    "color.status.success": "{color.palette.emerald.500}",
    "spacing.layout.gutter": "{spacing.4}",
    "spacing.card.padding": "{spacing.6}",
    "radius.container": "{radius.md}"
}

SEMANTIC_TOKENS_DARK: Dict[str, str] = {
    "color.surface.canvas": "{color.palette.neutral.950}",
    "color.surface.card": "{color.palette.neutral.900}",
    "color.surface.border": "{color.palette.neutral.800}",
    "color.text.primary": "{color.palette.neutral.50}",
    "color.text.secondary": "{color.palette.neutral.200}",
    "color.text.inverse": "{color.palette.neutral.950}",
    "color.action.primary.default": "{color.palette.blue.500}",
    "color.action.primary.hover": "{color.palette.blue.600}",
    "color.action.danger.default": "{color.palette.red.500}",
    "color.status.success": "{color.palette.emerald.500}",
    "spacing.layout.gutter": "{spacing.4}",
    "spacing.card.padding": "{spacing.6}",
    "radius.container": "{radius.md}"
}

# Component Tier: scoped to concrete components
COMPONENT_TOKENS: Dict[str, str] = {
    "button.primary.background": "{color.action.primary.default}",
    "button.primary.background.hover": "{color.action.primary.hover}",
    "button.primary.text": "{color.text.inverse}",
    "button.primary.padding.x": "{spacing.4}",
    "button.primary.padding.y": "{spacing.2}",
    "button.primary.border-radius": "{radius.container}",
    
    "button.danger.background": "{color.action.danger.default}",
    "button.danger.text": "{color.text.inverse}",

    "card.background": "{color.surface.card}",
    "card.border.color": "{color.surface.border}",
    "card.padding": "{spacing.card.padding}",
    "card.text.title": "{color.text.primary}",
    "card.text.body": "{color.text.secondary}"
}


# --- Token Resolution Engine ---
class TokenEngine:
    def __init__(self, mode: str = "light"):
        self.mode = mode
        self.primitives = PRIMITIVE_TOKENS
        self.semantic = SEMANTIC_TOKENS_DARK if mode == "dark" else SEMANTIC_TOKENS_LIGHT
        self.components = COMPONENT_TOKENS

    def resolve_reference(self, ref_key: str, chain: Optional[list] = None) -> Tuple[str, list]:
        if chain is None:
            chain = []

        clean_key = ref_key.strip("{}")
        chain.append(clean_key)

        # 1. Search in Components
        if clean_key in self.components:
            val = self.components[clean_key]
            if val.startswith("{") and val.endswith("}"):
                return self.resolve_reference(val, chain)
            return val, chain

        # 2. Search in Semantics
        if clean_key in self.semantic:
            val = self.semantic[clean_key]
            if val.startswith("{") and val.endswith("}"):
                return self.resolve_reference(val, chain)
            return val, chain

        # 3. Search in Primitives
        if clean_key in self.primitives:
            val = self.primitives[clean_key]
            return val, chain

        return f"<UNRESOLVED: {clean_key}>", chain

    def get_resolved_dictionary(self) -> Dict[str, Any]:
        result = {}
        for comp_k in self.components.keys():
            val, chain = self.resolve_reference(comp_k)
            result[comp_k] = {
                "resolved_value": val,
                "resolution_chain": chain
            }
        return result

    def export_css_custom_properties(self) -> str:
        lines = [f":root[data-theme=\"{self.mode}\"] {{"]
        # Semantics
        for k, _ in self.semantic.items():
            css_var = "--" + k.replace(".", "-")
            val, _ = self.resolve_reference(k)
            lines.append(f"  {css_var}: {val};")
        # Components
        for k, _ in self.components.items():
            css_var = "--" + k.replace(".", "-")
            val, _ = self.resolve_reference(k)
            lines.append(f"  {css_var}: {val};")
        lines.append("}")
        return "\n".join(lines)


# --- Visual Terminal Components Renderer ---
class TerminalRenderer:
    @staticmethod
    def render_header(title: str):
        print(f"\n{TerminalColor.BOLD}{TerminalColor.FG_CYAN}=== {title} ==={TerminalColor.RESET}")

    @classmethod
    def render_button_preview(cls, engine: TokenEngine):
        btn_bg, _ = engine.resolve_reference("button.primary.background")
        btn_txt, _ = engine.resolve_reference("button.primary.text")
        danger_bg, _ = engine.resolve_reference("button.danger.background")
        danger_txt, _ = engine.resolve_reference("button.danger.text")
        
        card_bg, _ = engine.resolve_reference("card.background")
        card_title, _ = engine.resolve_reference("card.text.title")
        card_body, _ = engine.resolve_reference("card.text.body")
        card_border, _ = engine.resolve_reference("card.border.color")

        print(f"\n{TerminalColor.BOLD}[Mode: {engine.mode.upper()} THEME PREVIEW]{TerminalColor.RESET}")
        
        # Render Surface Card
        c_bg_r, c_bg_g, c_bg_b = TerminalColor.hex_to_rgb(card_bg)
        c_t_r, c_t_g, c_t_b = TerminalColor.hex_to_rgb(card_title)
        c_b_r, c_b_g, c_b_b = TerminalColor.hex_to_rgb(card_body)
        c_brd_r, c_brd_g, c_brd_b = TerminalColor.hex_to_rgb(card_border)

        bg_code = TerminalColor.rgb_bg(c_bg_r, c_bg_g, c_bg_b)
        title_code = TerminalColor.rgb_fg(c_t_r, c_t_g, c_t_b)
        body_code = TerminalColor.rgb_fg(c_b_r, c_b_g, c_b_b)
        border_code = TerminalColor.rgb_fg(c_brd_r, c_brd_g, c_brd_b)

        print(f"{border_code}+------------------------------------------------------+{TerminalColor.RESET}")
        print(f"{border_code}|{bg_code}  {title_code}{TerminalColor.BOLD}Card Component Header ({engine.mode.capitalize()} Mode){' ' * 20}{border_code}|{TerminalColor.RESET}")
        print(f"{border_code}|{bg_code}  {body_code}Design tokens automate styling across platforms seamlessly.{' ' * 0}{border_code}|{TerminalColor.RESET}")
        print(f"{border_code}|{bg_code}                                                        {border_code}|{TerminalColor.RESET}")
        
        # Primary & Danger Buttons inside card
        btn_prim_rendered = TerminalColor.hex_badge(" Confirm Action ", btn_txt, btn_bg)
        btn_dang_rendered = TerminalColor.hex_badge(" Delete Item ", danger_txt, danger_bg)
        
        print(f"{border_code}|{bg_code}  {btn_prim_rendered}  {btn_dang_rendered}                         {border_code}|{TerminalColor.RESET}")
        print(f"{border_code}+------------------------------------------------------+{TerminalColor.RESET}")


# --- Interactive CLI Demonstration ---
def run_lab():
    TerminalRenderer.render_header("BAB 06: DESIGN SYSTEM TOKEN ARCHITECTURE LAB")
    print(f"{TerminalColor.FG_YELLOW}Fokus Konsep: Tiered Token Resolution, Contrast Audit & Style Dictionary{TerminalColor.RESET}")

    current_mode = "light"
    engine = TokenEngine(mode=current_mode)

    while True:
        print(f"\n{TerminalColor.BOLD}Pilihan Menu Lab:{TerminalColor.RESET}")
        print("  1. Visualisasi Hierarchy / Dependency Chain Resolution")
        print("  2. Render Visual UI Component Preview (Terminal TrueColor ANSI)")
        print("  3. Beralih Tema (Toggle Light/Dark Theme)")
        print("  4. Audit Kontras Aksesibilitas WCAG 2.1 (Automated Check)")
        print("  5. Export Token Compiler ke Format CSS Custom Properties (:root)")
        print("  6. Export Token Compiler ke JSON AST Distribution")
        print("  0. Keluar dari Lab")

        choice = input(f"\n{TerminalColor.BOLD}{TerminalColor.FG_GREEN}Pilih opsi [0-6] (default=1): {TerminalColor.RESET}").strip()
        if not choice:
            choice = "1"

        if choice == "1":
            TerminalRenderer.render_header(f"Multi-Tier Resolution Trace ({engine.mode.upper()})")
            tokens_to_trace = [
                "button.primary.background",
                "button.primary.text",
                "card.background",
                "card.text.body"
            ]
            for t in tokens_to_trace:
                resolved, chain = engine.resolve_reference(t)
                arrow = f" {TerminalColor.FG_CYAN}->{TerminalColor.RESET} "
                formatted_chain = arrow.join([f"{TerminalColor.BOLD}{step}{TerminalColor.RESET}" for step in chain])
                print(f"Token: {TerminalColor.FG_YELLOW}{t}{TerminalColor.RESET}")
                print(f"  Path: {formatted_chain}")
                print(f"  Final Resolved Value: {TerminalColor.BOLD}{TerminalColor.FG_GREEN}{resolved}{TerminalColor.RESET}\n")

        elif choice == "2":
            TerminalRenderer.render_header("Interactive ANSI UI Canvas Preview")
            TerminalRenderer.render_button_preview(engine)

        elif choice == "3":
            current_mode = "dark" if current_mode == "light" else "light"
            engine = TokenEngine(mode=current_mode)
            print(f"\n{TerminalColor.FG_GREEN}[✓] Mode berhasil dialihkan ke: {TerminalColor.BOLD}{current_mode.upper()}{TerminalColor.RESET}")
            TerminalRenderer.render_button_preview(engine)

        elif choice == "4":
            TerminalRenderer.render_header(f"Automated WCAG 2.1 Contrast Audit ({engine.mode.upper()})")
            test_pairs = [
                ("Button Primary", "button.primary.text", "button.primary.background"),
                ("Button Danger", "button.danger.text", "button.danger.background"),
                ("Card Title on Card", "card.text.title", "card.background"),
                ("Card Body on Card", "card.text.body", "card.background"),
                ("Card Border on Canvas", "card.border.color", "color.surface.canvas")
            ]

            print(f"{'Elemen / Pasangan':<24} | {'FG Token':<10} | {'BG Token':<10} | {'Rasio':<8} | Status")
            print("-" * 75)
            for label, fg_key, bg_key in test_pairs:
                fg_val, _ = engine.resolve_reference(fg_key)
                bg_val, _ = engine.resolve_reference(bg_key)
                
                ratio = AccessibilityAuditor.contrast_ratio(fg_val, bg_val)
                status = AccessibilityAuditor.evaluate_compliance(ratio)
                badge = TerminalColor.hex_badge(" Aa ", fg_val, bg_val)
                print(f"{label:<24} | {fg_val:<10} | {bg_val:<10} | {ratio:>5.2f}:1 | {badge} {status}")

        elif choice == "5":
            TerminalRenderer.render_header("Style Dictionary Export: CSS Custom Properties")
            css_code = engine.export_css_custom_properties()
            print(f"{TerminalColor.FG_CYAN}{css_code}{TerminalColor.RESET}")

        elif choice == "6":
            TerminalRenderer.render_header("AST JSON Distribution Tree")
            ast_data = engine.get_resolved_dictionary()
            print(json.dumps(ast_data, indent=2))

        elif choice == "0":
            print(f"\n{TerminalColor.FG_YELLOW}Menutup sesi lab Design Systems Architecture. Selesai.{TerminalColor.RESET}\n")
            sys.exit(0)
        else:
            print(f"{TerminalColor.FG_RED}[!] Opsi tidak dikenali, silakan coba lagi.{TerminalColor.RESET}")


if __name__ == "__main__":
    try:
        run_lab()
    except (KeyboardInterrupt, EOFError):
        print(f"\n{TerminalColor.FG_YELLOW}Sesi lab dihentikan oleh user.{TerminalColor.RESET}")
        sys.exit(0)
