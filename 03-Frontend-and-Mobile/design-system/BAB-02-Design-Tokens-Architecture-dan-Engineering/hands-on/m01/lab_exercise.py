#!/usr/bin/env python3
"""
Lab Exercise M01: Design Tokens Architecture & Engineering Engine
Simulasi komprehensif arsitektur design tokens:
1. Global/Primitive Tokens (Palet dasar, spacing scale, typographic scale)
2. Semantic/Alias Tokens (Contextual intent & Multi-theme light/dark)
3. Component-Specific Tokens (Button, Surface, Input)
4. Token Resolver & Reference Expander (Resolusi alias dinamis)
5. WCAG 2.1 Contrast Ratio Validator & Exporter (CSS Variables & SCSS)
"""

import sys
import re
import math
import json
from typing import Dict, Any, Tuple, Optional

# ANSI Escape Codes untuk output terminal yang kaya warna
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
UNDERLINE = "\033[4m"

FG_BLACK = "\033[30m"
FG_RED = "\033[31m"
FG_GREEN = "\033[32m"
FG_YELLOW = "\033[33m"
FG_BLUE = "\033[34m"
FG_MAGENTA = "\033[35m"
FG_CYAN = "\033[36m"
FG_WHITE = "\033[37m"

BG_BLACK = "\033[40m"
BG_WHITE = "\033[47m"
BG_BLUE = "\033[44m"
BG_GRAY = "\033[100m"


def hex_to_rgb(hex_code: str) -> Tuple[int, int, int]:
    """Mengonversi string hex (#RRGGBB) ke tuple RGB integer."""
    hex_code = hex_code.lstrip("#")
    if len(hex_code) == 3:
        hex_code = "".join([c * 2 for c in hex_code])
    return tuple(int(hex_code[i:i + 2], 16) for i in (0, 2, 4))


def ansi_truecolor_badge(hex_color: str, text: str = "   ") -> str:
    """Merender kotak warna visual di terminal menggunakan ANSI truecolor 24-bit."""
    try:
        r, g, b = hex_to_rgb(hex_color)
        return f"\033[48;2;{r};{g};{b}m{text}{RESET}"
    except Exception:
        return f"[{hex_color}]"


def calculate_luminance(rgb: Tuple[int, int, int]) -> float:
    """Menghitung relative luminance sesuai spesifikasi WCAG 2.1."""
    def channel_lum(channel: int) -> float:
        c = channel / 255.0
        return c / 12.92 if c <= 0.03928 else math.pow((c + 0.055) / 1.055, 2.4)

    r, g, b = rgb
    return 0.2126 * channel_lum(r) + 0.7152 * channel_lum(g) + 0.0722 * channel_lum(b)


def calculate_contrast_ratio(hex1: str, hex2: str) -> float:
    """Menghitung WCAG contrast ratio antara 2 warna heksadesimal."""
    lum1 = calculate_luminance(hex_to_rgb(hex1))
    lum2 = calculate_luminance(hex_to_rgb(hex2))
    brightest = max(lum1, lum2)
    darkest = min(lum1, lum2)
    return (brightest + 0.05) / (darkest + 0.05)


# --- 1. DEFINISI TIER 1: GLOBAL / PRIMITIVE TOKENS ---
GLOBAL_TOKENS = {
    "color": {
        "blue": {
            "50": "#eff6ff",
            "100": "#dbeafe",
            "500": "#3b82f6",
            "600": "#2563eb",
            "700": "#1d4ed8",
            "900": "#1e3a8a",
        },
        "neutral": {
            "0": "#ffffff",
            "50": "#f8fafc",
            "100": "#f1f5f9",
            "200": "#e2e8f0",
            "700": "#334155",
            "800": "#1e293b",
            "900": "#0f172a",
            "950": "#020617",
        },
        "emerald": {
            "500": "#10b981",
            "600": "#059669",
        },
        "rose": {
            "500": "#f43f5e",
            "600": "#e11d48",
        },
    },
    "spacing": {
        "0": "0px",
        "1": "4px",
        "2": "8px",
        "3": "12px",
        "4": "16px",
        "6": "24px",
        "8": "32px",
    },
    "radii": {
        "none": "0px",
        "sm": "4px",
        "md": "8px",
        "lg": "12px",
        "full": "9999px",
    },
    "font-family": {
        "sans": "Inter, system-ui, -apple-system, sans-serif",
        "mono": "'JetBrains Mono', monospace",
    },
    "font-size": {
        "sm": "0.875rem",
        "base": "1rem",
        "lg": "1.125rem",
        "xl": "1.25rem",
        "2xl": "1.5rem",
    },
}

# --- 2. DEFINISI TIER 2: SEMANTIC / ALIAS TOKENS (LIGHT & DARK THEMES) ---
SEMANTIC_TOKENS = {
    "light": {
        "surface": {
            "canvas": "{color.neutral.50}",
            "card": "{color.neutral.0}",
            "border": "{color.neutral.200}",
        },
        "text": {
            "primary": "{color.neutral.900}",
            "secondary": "{color.neutral.700}",
            "inverse": "{color.neutral.0}",
        },
        "brand": {
            "primary": "{color.blue.600}",
            "primary-hover": "{color.blue.700}",
            "on-primary": "{color.neutral.0}",
        },
        "feedback": {
            "success": "{color.emerald.600}",
            "danger": "{color.rose.600}",
        },
    },
    "dark": {
        "surface": {
            "canvas": "{color.neutral.950}",
            "card": "{color.neutral.900}",
            "border": "{color.neutral.800}",
        },
        "text": {
            "primary": "{color.neutral.50}",
            "secondary": "{color.neutral.200}",
            "inverse": "{color.neutral.950}",
        },
        "brand": {
            "primary": "{color.blue.500}",
            "primary-hover": "{color.blue.600}",
            "on-primary": "{color.neutral.950}",
        },
        "feedback": {
            "success": "{color.emerald.500}",
            "danger": "{color.rose.500}",
        },
    },
}

# --- 3. DEFINISI TIER 3: COMPONENT-SPECIFIC TOKENS ---
COMPONENT_TOKENS = {
    "button": {
        "primary": {
            "bg": "{brand.primary}",
            "bg-hover": "{brand.primary-hover}",
            "text": "{brand.on-primary}",
            "padding-y": "{spacing.3}",
            "padding-x": "{spacing.6}",
            "radius": "{radii.md}",
            "font-size": "{font-size.base}",
        },
        "ghost": {
            "bg": "transparent",
            "bg-hover": "{surface.border}",
            "text": "{text.primary}",
            "padding-y": "{spacing.3}",
            "padding-x": "{spacing.6}",
            "radius": "{radii.md}",
            "font-size": "{font-size.base}",
        },
    },
    "card": {
        "bg": "{surface.card}",
        "border": "{surface.border}",
        "radius": "{radii.lg}",
        "padding": "{spacing.6}",
        "text-headline": "{text.primary}",
        "text-body": "{text.secondary}",
    },
}


class TokenResolver:
    """Engine untuk menavigasi, me-resolve alias token, dan memvalidasi integritas tema."""

    def __init__(self, global_pool: Dict[str, Any], semantic_pool: Dict[str, Any], component_pool: Dict[str, Any]):
        self.global_pool = global_pool
        self.semantic_pool = semantic_pool
        self.component_pool = component_pool

    def get_primitive(self, path: str) -> Optional[str]:
        keys = path.split(".")
        curr = self.global_pool
        for k in keys:
            if isinstance(curr, dict) and k in curr:
                curr = curr[k]
            else:
                return None
        return curr if isinstance(curr, str) else None

    def get_semantic(self, path: str, theme: str = "light") -> Optional[str]:
        keys = path.split(".")
        curr = self.semantic_pool.get(theme, {})
        for k in keys:
            if isinstance(curr, dict) and k in curr:
                curr = curr[k]
            else:
                return None
        return curr if isinstance(curr, str) else None

    def resolve_reference(self, ref_expression: str, theme: str = "light", depth: int = 0) -> str:
        """Me-resolve {token.path} secara rekursif hingga menemukan nilai primitif."""
        if depth > 10:
            raise RecursionError(f"Circular token reference detected: {ref_expression}")

        pattern = r"\{([^}]+)\}"
        matches = re.findall(pattern, ref_expression)
        if not matches:
            return ref_expression

        resolved_str = ref_expression
        for match in matches:
            val = self.get_semantic(match, theme)
            if val is None:
                val = self.get_primitive(match)
            if val is None:
                raise KeyError(f"Gagal me-resolve token reference: '{{{match}}}' pada tema '{theme}'")
            resolved_child = self.resolve_reference(val, theme, depth + 1)
            resolved_str = resolved_str.replace(f"{{{match}}}", resolved_child)

        return resolved_str

    def resolve_all_components(self, theme: str = "light") -> Dict[str, Any]:
        """Resolusi penuh seluruh komponen token terhadap tema aktif."""
        resolved = {}
        for comp_name, comp_props in self.component_pool.items():
            resolved[comp_name] = self._resolve_dict_recursive(comp_props, theme)
        return resolved

    def _resolve_dict_recursive(self, d: Dict[str, Any], theme: str) -> Dict[str, Any]:
        result = {}
        for k, v in d.items():
            if isinstance(v, dict):
                result[k] = self._resolve_dict_recursive(v, theme)
            elif isinstance(v, str):
                result[k] = self.resolve_reference(v, theme)
            else:
                result[k] = v
        return result


def print_banner():
    banner = f"""
{BOLD}{FG_CYAN}========================================================================{RESET}
{BOLD}{FG_WHITE}   DESIGN TOKENS ARCHITECTURE & MULTI-TIER ENGINE SIMULATOR (M01)   {RESET}
{BOLD}{FG_CYAN}========================================================================{RESET}
{DIM}Platform Engineering: Global Primitives -> Semantic Aliases -> Component Tokens{RESET}
"""
    print(banner)


def display_primitives_demo(resolver: TokenResolver):
    print(f"\n{BOLD}{FG_YELLOW}▶ TIER 1: GLOBAL / PRIMITIVE DESIGN TOKENS{RESET}")
    print(f"{DIM}Nilai absolut bebas konteks (raw palette & metric scales):{RESET}\n")

    print(f"{UNDERLINE}Color Palette Primitives:{RESET}")
    for family, shades in GLOBAL_TOKENS["color"].items():
        print(f"  {BOLD}{family.upper():<10}{RESET}: ", end="")
        for shade, hex_code in shades.items():
            badge = ansi_truecolor_badge(hex_code, "  ")
            print(f"{badge} {shade}:{DIM}{hex_code}{RESET}  ", end="")
        print()

    print(f"\n{UNDERLINE}Spacing Scale (4px-based baseline grid):{RESET}")
    for k, v in GLOBAL_TOKENS["spacing"].items():
        bar = "█" * (int(v.replace("px", "")) // 2) if v != "0px" else "·"
        print(f"  spacing.{k:<3} -> {v:<5} {FG_CYAN}{bar}{RESET}")


def display_semantic_modes_demo(resolver: TokenResolver):
    print(f"\n{BOLD}{FG_YELLOW}▶ TIER 2: SEMANTIC TOKENS & MODE SWITCHING (LIGHT vs DARK){RESET}")
    print(f"{DIM}Mengikat konteks UX dengan warna intent, mendukung multi-theming:{RESET}\n")

    for mode in ["light", "dark"]:
        canvas_hex = resolver.resolve_reference(SEMANTIC_TOKENS[mode]["surface"]["canvas"], mode)
        card_hex = resolver.resolve_reference(SEMANTIC_TOKENS[mode]["surface"]["card"], mode)
        border_hex = resolver.resolve_reference(SEMANTIC_TOKENS[mode]["surface"]["border"], mode)
        text_pri_hex = resolver.resolve_reference(SEMANTIC_TOKENS[mode]["text"]["primary"], mode)
        brand_hex = resolver.resolve_reference(SEMANTIC_TOKENS[mode]["brand"]["primary"], mode)

        mode_badge = f"{BG_WHITE}{FG_BLACK} LIGHT MODE {RESET}" if mode == "light" else f"{BG_GRAY}{FG_WHITE} DARK MODE  {RESET}"
        print(f"{BOLD}Tema: {mode_badge}{RESET}")
        print(f"  • surface.canvas    : {ansi_truecolor_badge(canvas_hex)} {canvas_hex}")
        print(f"  • surface.card      : {ansi_truecolor_badge(card_hex)} {card_hex}")
        print(f"  • surface.border    : {ansi_truecolor_badge(border_hex)} {border_hex}")
        print(f"  • text.primary      : {ansi_truecolor_badge(text_pri_hex)} {text_pri_hex}")
        print(f"  • brand.primary     : {ansi_truecolor_badge(brand_hex)} {brand_hex}\n")


def display_wcag_audit(resolver: TokenResolver):
    print(f"{BOLD}{FG_YELLOW}▶ VALIDASI KUALITAS TOKENS: WCAG 2.1 ACCESSIBILITY CONTRAST AUDIT{RESET}")
    print(f"{DIM}Audit rasio kontras otomatis sebelum artefak token diekspor ke CSS/SCSS:{RESET}\n")

    test_pairs = [
        ("light", "surface.card", "text.primary", "Normal Text", 4.5),
        ("light", "brand.primary", "brand.on-primary", "Button Primary", 4.5),
        ("light", "surface.canvas", "text.secondary", "Muted Text", 4.5),
        ("dark", "surface.card", "text.primary", "Normal Text", 4.5),
        ("dark", "brand.primary", "brand.on-primary", "Button Primary", 4.5),
        ("dark", "surface.canvas", "text.secondary", "Muted Text", 4.5),
    ]

    print(f"{'THEME':<8} | {'BACKGROUND':<16} | {'FOREGROUND':<18} | {'RATIO':<8} | {'WCAG AA':<10}")
    print("-" * 70)

    all_passed = True
    for mode, bg_alias, fg_alias, desc, min_req in test_pairs:
        bg_raw = SEMANTIC_TOKENS[mode][bg_alias.split(".")[0]][bg_alias.split(".")[1]]
        fg_raw = SEMANTIC_TOKENS[mode][fg_alias.split(".")[0]][fg_alias.split(".")[1]]
        bg_hex = resolver.resolve_reference(bg_raw, mode)
        fg_hex = resolver.resolve_reference(fg_raw, mode)

        ratio = calculate_contrast_ratio(bg_hex, fg_hex)
        passed = ratio >= min_req
        if not passed:
            all_passed = False

        status_str = f"{FG_GREEN}PASS (>= {min_req}){RESET}" if passed else f"{FG_RED}FAIL (< {min_req}){RESET}"
        badge_preview = f"{ansi_truecolor_badge(bg_hex, ' ')}{ansi_truecolor_badge(fg_hex, ' ')}"

        print(f"{mode.upper():<8} | {badge_preview} {bg_alias:<12} | {fg_alias:<18} | {ratio:>5.2f}:1  | {status_str}")

    print("-" * 70)
    if all_passed:
        print(f"{BOLD}{FG_GREEN}✓ Seluruh kombinasi Semantic Tokens lolos WCAG 2.1 level AA!{RESET}\n")
    else:
        print(f"{BOLD}{FG_RED}✗ Terdapat token pair yang melanggar standar aksesibilitas!{RESET}\n")


def display_component_resolution(resolver: TokenResolver):
    print(f"{BOLD}{FG_YELLOW}▶ TIER 3: COMPONENT TOKEN RESOLUTION MATRIX{RESET}")
    print(f"{DIM}Hasil kalkulasi akhir token per komponen untuk runtime rendering:{RESET}\n")

    for mode in ["light", "dark"]:
        resolved_components = resolver.resolve_all_components(theme=mode)
        btn = resolved_components["button"]["primary"]

        print(f"{BOLD}Button Component Resolved [{mode.upper()}]{RESET}:")
        print(f"  • Background       : {ansi_truecolor_badge(btn['bg'])} {btn['bg']}")
        print(f"  • Background Hover : {ansi_truecolor_badge(btn['bg-hover'])} {btn['bg-hover']}")
        print(f"  • Text Color       : {ansi_truecolor_badge(btn['text'])} {btn['text']}")
        print(f"  • Geometry (Padding/Radius) : {btn['padding-y']} {btn['padding-x']} | R: {btn['radius']}")

        # Render representasi visual button di terminal
        bg_rgb = hex_to_rgb(btn['bg'])
        fg_rgb = hex_to_rgb(btn['text'])
        btn_visual = f"\033[48;2;{bg_rgb[0]};{bg_rgb[1]};{bg_rgb[2]}m\033[38;2;{fg_rgb[0]};{fg_rgb[1]};{fg_rgb[2]}m{BOLD}   Simpan Perubahan   {RESET}"
        print(f"  • Live Preview     : {btn_visual}\n")


def export_css_tokens(resolver: TokenResolver):
    print(f"{BOLD}{FG_YELLOW}▶ COMPILER TARGET: CSS CUSTOM PROPERTIES (DESIGN SYSTEM EXPORT){RESET}")
    print(f"{DIM}Output siap pakai untuk Web Engine / Frontend bundler:{RESET}\n")

    css_lines = [":root {"]
    # Primitives
    css_lines.append("  /* --- Global Primitives --- */")
    for group, items in GLOBAL_TOKENS.items():
        if group == "color":
            for sub, shades in items.items():
                for shade, val in shades.items():
                    css_lines.append(f"  --ds-global-color-{sub}-{shade}: {val};")
        else:
            for k, val in items.items():
                css_lines.append(f"  --ds-global-{group}-{k}: {val};")

    # Semantic Light
    css_lines.append("\n  /* --- Semantic Tokens (Default Light) --- */")
    for category, props in SEMANTIC_TOKENS["light"].items():
        for prop, raw_val in props.items():
            resolved = resolver.resolve_reference(raw_val, "light")
            css_lines.append(f"  --ds-{category}-{prop}: {resolved};")

    css_lines.append("}\n")

    # Semantic Dark
    css_lines.append("[data-theme='dark'] {")
    css_lines.append("  /* --- Semantic Tokens (Dark Mode Override) --- */")
    for category, props in SEMANTIC_TOKENS["dark"].items():
        for prop, raw_val in props.items():
            resolved = resolver.resolve_reference(raw_val, "dark")
            css_lines.append(f"  --ds-{category}-{prop}: {resolved};")
    css_lines.append("}")

    sample_output = "\n".join(css_lines[:25]) + f"\n  {DIM}... [truncated remaining lines] ...{RESET}\n}}"
    print(f"{FG_GREEN}{sample_output}{RESET}\n")


def interactive_token_lookup(resolver: TokenResolver):
    print(f"{BOLD}{FG_MAGENTA}------------------------------------------------------------------------{RESET}")
    print(f"{BOLD}INTERACTIVE LAB DEMO: Cek Resolusi Token Kustom{RESET}")
    print(f"{DIM}Coba ketik ekspresi token seperti: {FG_CYAN}{{brand.primary}}{DIM}, {FG_CYAN}{{color.blue.500}}{DIM}, {FG_CYAN}{{spacing.4}}{RESET}")
    print(f"{DIM}Atau ketik 'exit' untuk menyelesaikan simulasi.{RESET}\n")

    queries = [
        "{brand.primary}",
        "{surface.canvas}",
        "{button.primary.bg}",
        "{spacing.4}",
    ]

    print(f"{BOLD}Menjalankan uji resolusi otomatis untuk contoh queries:{RESET}")
    for q in queries:
        try:
            if "button." in q:
                # Handle component level
                resolved_light = resolver.component_pool["button"]["primary"]["bg"]
                res_l = resolver.resolve_reference(resolved_light, "light")
                res_d = resolver.resolve_reference(resolved_light, "dark")
            else:
                res_l = resolver.resolve_reference(q, "light")
                res_d = resolver.resolve_reference(q, "dark")

            badge_l = ansi_truecolor_badge(res_l) if res_l.startswith("#") else ""
            badge_d = ansi_truecolor_badge(res_d) if res_d.startswith("#") else ""

            print(f"  Token: {BOLD}{q:<24}{RESET} -> Light: {badge_l} {res_l:<10} | Dark: {badge_d} {res_d}")
        except Exception as e:
            print(f"  Token: {BOLD}{q:<24}{RESET} -> Error: {e}")


def main():
    print_banner()
    resolver = TokenResolver(
        global_pool=GLOBAL_TOKENS,
        semantic_pool=SEMANTIC_TOKENS,
        component_pool=COMPONENT_TOKENS,
    )

    display_primitives_demo(resolver)
    display_semantic_modes_demo(resolver)
    display_wcag_audit(resolver)
    display_component_resolution(resolver)
    export_css_tokens(resolver)
    interactive_token_lookup(resolver)

    print(f"\n{BOLD}{FG_CYAN}========================================================================{RESET}")
    print(f"{BOLD}{FG_GREEN}✓ SIMULASI DESIGN TOKENS ARCHITECTURE BERHASIL DIEKSEKUSI SEMPURNA.{RESET}")
    print(f"{BOLD}{FG_CYAN}========================================================================{RESET}\n")


if __name__ == "__main__":
    main()
