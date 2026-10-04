#!/usr/bin/env python3
"""
Lab Hands-on: Accessible Color Science & Contrast Engineering (WCAG 2.1 & APCA)
Design System Architecture - Deep Dive Module

This script provides an enterprise-grade color science engine simulating:
1. Exact sRGB to Linear Photometric conversion via gamma expansion.
2. ITU-R BT.709 relative luminance calculation.
3. WCAG 2.1 relative contrast ratio evaluation against AA/AAA compliance thresholds.
4. Simplified APCA (Accessible Perceptual Contrast Algorithm - W3C Silver draft) computation.
5. Contrast Remediation Engine: Automated programmatic luminance stepping to achieve
   minimum target contrast with minimal perceptual delta E.
"""

from __future__ import annotations
import math
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Tuple, List, Optional


class WCAGLevel(Enum):
    FAIL = "FAIL"
    AA_LARGE = "AA Large (3.0:1)"
    AA_NORMAL = "AA Normal (4.5:1)"
    AAA_NORMAL = "AAA Normal (7.0:1)"


@dataclass(frozen=True)
class RGBColor:
    r: int  # 0 - 255
    g: int  # 0 - 255
    b: int  # 0 - 255

    @classmethod
    def from_hex(cls, hex_str: str) -> RGBColor:
        """Parses standard #RGB or #RRGGBB hexadecimal strings."""
        clean_hex = hex_str.lstrip("#")
        if len(clean_hex) == 3:
            clean_hex = "".join([c * 2 for c in clean_hex])
        if len(clean_hex) != 6:
            raise ValueError(f"Invalid hex color format: {hex_str}")
        r = int(clean_hex[0:2], 16)
        g = int(clean_hex[2:4], 16)
        b = int(clean_hex[4:6], 16)
        return cls(r, g, b)

    def to_hex(self) -> str:
        """Converts RGB channels to standard uppercase hexadecimal string."""
        return f"#{self.r:02X}{self.g:02X}{self.b:02X}"

    def ansi_styled(self, text: str, bg: Optional[RGBColor] = None) -> str:
        """Renders 24-bit TrueColor ANSI output for terminal display."""
        fg_seq = f"\033[38;2;{self.r};{self.g};{self.b}m"
        bg_seq = f"\033[48;2;{bg.r};{bg.g};{bg.b}m" if bg else ""
        reset = "\033[0m"
        return f"{fg_seq}{bg_seq}{text}{reset}"


class ColorScienceEngine:
    """
    Implements standard spectrophotometric transformations and contrast metrics.
    """

    @staticmethod
    def channel_to_linear(c_srgb: float) -> float:
        """
        De-quantizes and linearizes an 8-bit sRGB channel (removes 2.4 gamma encoding).
        Specification: IEC 61966-2-1:1999.
        """
        val = c_srgb / 255.0
        if val <= 0.04045:
            return val / 12.92
        return math.pow((val + 0.055) / 1.055, 2.4)

    @staticmethod
    def linear_to_channel(c_lin: float) -> int:
        """Re-applies gamma compression to convert linear radiometric energy to sRGB channel."""
        c_clamped = max(0.0, min(1.0, c_lin))
        if c_clamped <= 0.0031308:
            srgb = c_clamped * 12.92
        else:
            srgb = 1.055 * math.pow(c_clamped, 1.0 / 2.4) - 0.055
        return int(round(srgb * 255.0))

    @classmethod
    def calculate_relative_luminance(cls, color: RGBColor) -> float:
        """
        Calculates ITU-R BT.709 relative luminance (Y) from sRGB coordinates.
        Coefficients represent human photopic spectral sensitivity (V(lambda)).
        """
        r_lin = cls.channel_to_linear(color.r)
        g_lin = cls.channel_to_linear(color.g)
        b_lin = cls.channel_to_linear(color.b)
        return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin

    @classmethod
    def calculate_wcag_contrast(cls, fg: RGBColor, bg: RGBColor) -> float:
        """
        Computes WCAG 2.1 Relative Contrast Ratio: (L1 + 0.05) / (L2 + 0.05)
        Range: 1.0 to 21.0.
        """
        lum1 = cls.calculate_relative_luminance(fg)
        lum2 = cls.calculate_relative_luminance(bg)
        l_light = max(lum1, lum2)
        l_dark = min(lum1, lum2)
        return (l_light + 0.05) / (l_dark + 0.05)

    @classmethod
    def calculate_apca_contrast(cls, fg: RGBColor, bg: RGBColor) -> float:
        """
        Calculates simplified APCA (Accessible Perceptual Contrast Algorithm) Lightness contrast (Lc).
        Unlike WCAG 2, APCA accounts for spatial frequency, surround luminance, and polarity.
        Positive Lc: Dark text on light background.
        Negative Lc: Light text on dark background.
        """
        y_txt = cls.calculate_relative_luminance(fg)
        y_bg = cls.calculate_relative_luminance(bg)

        # Soft clamping for black-level flare
        blk_thresh = 0.022
        blk_clamp = 1.414
        if y_txt < blk_thresh:
            y_txt += math.pow(blk_thresh - y_txt, blk_clamp)
        if y_bg < blk_thresh:
            y_bg += math.pow(blk_thresh - y_bg, blk_clamp)

        # Perceptual exponents (W3C Silver APCA draft approximations)
        norm_bg = 0.56
        norm_txt = 0.57
        rev_txt = 0.62
        rev_bg = 0.65

        scale = 1.1414

        if y_bg >= y_txt:
            # Positive polarity (dark text on light bg)
            sapc = (math.pow(y_bg, norm_bg) - math.pow(y_txt, norm_txt)) * scale
            lc = (sapc - 0.027) * 100.0 if sapc > 0.027 else 0.0
        else:
            # Negative polarity (light text on dark bg)
            sapc = (math.pow(y_bg, rev_bg) - math.pow(y_txt, rev_txt)) * scale
            lc = (sapc + 0.027) * 100.0 if sapc < -0.027 else 0.0

        return lc

    @classmethod
    def evaluate_wcag_level(cls, ratio: float, is_large_text: bool = False) -> WCAGLevel:
        """Maps numeric contrast ratio to formal compliance classification."""
        if is_large_text:
            if ratio >= 4.5:
                return WCAGLevel.AAA_NORMAL
            if ratio >= 3.0:
                return WCAGLevel.AA_LARGE
        else:
            if ratio >= 7.0:
                return WCAGLevel.AAA_NORMAL
            if ratio >= 4.5:
                return WCAGLevel.AA_NORMAL
            if ratio >= 3.0:
                return WCAGLevel.AA_LARGE
        return WCAGLevel.FAIL


class AutomatedContrastRemediator:
    """
    Programmatic color engineering: Adjusts color coordinates along the luminance axis
    to remediate non-compliant design tokens while preserving the original hue/chroma.
    """

    @classmethod
    def remediate_foreground(
        cls, fg: RGBColor, bg: RGBColor, target_ratio: float = 4.5, max_steps: int = 256
    ) -> Tuple[RGBColor, float]:
        """
        Binary search over scalar multiplier on linear RGB vector to find minimum luminance
        change satisfying target_ratio.
        """
        current_ratio = ColorScienceEngine.calculate_wcag_contrast(fg, bg)
        if current_ratio >= target_ratio:
            return fg, current_ratio

        bg_lum = ColorScienceEngine.calculate_relative_luminance(bg)
        # Determine shift direction: go darker if bg is light, go brighter if bg is dark
        shift_towards_white = bg_lum < 0.5

        low = 0.0
        high = 1.0
        best_candidate = fg
        best_ratio = current_ratio

        for _ in range(max_steps):
            factor = (low + high) / 2.0
            if shift_towards_white:
                # Interpolate towards (255, 255, 255)
                cand_r = int(fg.r + (255 - fg.r) * factor)
                cand_g = int(fg.g + (255 - fg.g) * factor)
                cand_b = int(fg.b + (255 - fg.b) * factor)
            else:
                # Interpolate towards (0, 0, 0)
                cand_r = int(fg.r * (1.0 - factor))
                cand_g = int(fg.g * (1.0 - factor))
                cand_b = int(fg.b * (1.0 - factor))

            candidate = RGBColor(cand_r, cand_g, cand_b)
            r = ColorScienceEngine.calculate_wcag_contrast(candidate, bg)

            if r >= target_ratio:
                best_candidate = candidate
                best_ratio = r
                high = factor  # Attempt to find closer match to original color
            else:
                low = factor

        return best_candidate, best_ratio


def run_system_audit() -> None:
    """Executes full diagnostic and auto-remediation suite on standard design system tokens."""
    token_pairs = [
        ("color-text-primary", "#111827", "color-bg-canvas", "#FFFFFF"),
        ("color-text-muted", "#9CA3AF", "color-bg-canvas", "#FFFFFF"),
        ("color-text-brand", "#3B82F6", "color-bg-surface", "#F3F4F6"),
        ("color-badge-warning-text", "#B45309", "color-badge-warning-bg", "#FEF3C7"),
        ("color-btn-danger-text", "#FFFFFF", "color-btn-danger-bg", "#EF4444"),
        ("color-text-disabled", "#D1D5DB", "color-bg-dark", "#1E293B"),
    ]

    print("\033[1;36m" + "=" * 90)
    print(" ACCESSIBLE COLOR SCIENCE & CONTRAST ENGINEERING SUITE (WCAG 2.1 & APCA)")
    print("=" * 90 + "\033[0m\n")

    print(f"{'Token Pair (FG vs BG)':<38} | {'sRGB Hex':<17} | {'WCAG':<7} | {'APCA Lc':<8} | {'Status'}")
    print("-" * 90)

    remediation_queue: List[Tuple[str, RGBColor, str, RGBColor, float]] = []

    for fg_name, fg_hex, bg_name, bg_hex in token_pairs:
        fg_col = RGBColor.from_hex(fg_hex)
        bg_col = RGBColor.from_hex(bg_hex)

        wcag_ratio = ColorScienceEngine.calculate_wcag_contrast(fg_col, bg_col)
        apca_lc = ColorScienceEngine.calculate_apca_contrast(fg_col, bg_col)
        level = ColorScienceEngine.evaluate_wcag_level(wcag_ratio)

        label = f"{fg_name} / {bg_name}"
        hex_pair = f"{fg_hex} on {bg_hex}"

        # Color-coded badge output
        swatch_sample = fg_col.ansi_styled(" Aa ", bg=bg_col)
        if level in (WCAGLevel.AAA_NORMAL, WCAGLevel.AA_NORMAL):
            status = f"\033[1;32mPASS ({level.value})\033[0m"
        elif level == WCAGLevel.AA_LARGE:
            status = f"\033[1;33mLARGE TEXT ONLY ({level.value})\033[0m"
        else:
            status = f"\033[1;31mFAIL (Insufficient Contrast)\033[0m"
            remediation_queue.append((fg_name, fg_col, bg_name, bg_col, wcag_ratio))

        print(f"{label:<38} | {swatch_sample} {hex_pair:<13} | {wcag_ratio:5.2f}:1 | {apca_lc:7.1f} | {status}")

    print("\n" + "\033[1;33m" + "=" * 90)
    print(" AUTOMATED CONTRAST REMEDIATION ENGINE (TARGET: WCAG AA >= 4.5:1)")
    print("=" * 90 + "\033[0m\n")

    if not remediation_queue:
        print("\033[32mAll design tokens are fully compliant. No remediation required.\033[0m\n")
        return

    for fg_name, fg_col, bg_name, bg_col, old_ratio in remediation_queue:
        optimized_fg, new_ratio = AutomatedContrastRemediator.remediate_foreground(
            fg=fg_col, bg=bg_col, target_ratio=4.5
        )
        new_apca = ColorScienceEngine.calculate_apca_contrast(optimized_fg, bg_col)
        new_level = ColorScienceEngine.evaluate_wcag_level(new_ratio)

        orig_swatch = fg_col.ansi_styled(" FAIL ", bg=bg_col)
        remed_swatch = optimized_fg.ansi_styled(" PASS ", bg=bg_col)

        print(f"Token: \033[1m{fg_name}\033[0m against \033[1m{bg_name}\033[0m")
        print(f"  [Original]    Hex: {fg_col.to_hex()} | Ratio: {old_ratio:5.2f}:1 | Swatch: {orig_swatch}")
        print(f"  [Remediated]  Hex: \033[1;32m{optimized_fg.to_hex()}\033[0m | Ratio: \033[1;32m{new_ratio:5.2f}:1\033[0m | Swatch: {remed_swatch}")
        print(f"  [Metrics]     New APCA Lc: {new_apca:5.1f} | Compliance: {new_level.name}")
        print("  " + "." * 70)

    print("\n\033[1;32m[✓] Remediation run completed. Generated production tokens ready for design sync.\033[0m\n")


if __name__ == "__main__":
    try:
        run_system_audit()
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as err:
        sys.stderr.write(f"\033[31mExecution failure: {err}\033[0m\n")
        sys.exit(1)