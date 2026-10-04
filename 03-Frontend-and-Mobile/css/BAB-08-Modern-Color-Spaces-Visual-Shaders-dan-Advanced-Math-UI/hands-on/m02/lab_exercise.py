#!/usr/bin/env python3
"""
Lab Hands-on: Modern Color Spaces, Visual Shaders, dan Advanced Math UI
Bab 08 - Modul 02 Deep Dive

Skrip ini memodelkan:
1. Konversi matematis eksak antara standard sRGB, Linear sRGB, Oklab, dan Oklch (CSS Color Module Level 4).
2. Perbandingan interpolasi warna CSS `color-mix()`: Oklch vs sRGB (menganalisis fenomena dead-zone / gray-zone).
3. Evaluasi Signed Distance Field (SDF) dan visual shader 2D menggunakan CSS Math UI functions (sin, cos, smoothstep).
4. Terminal Truecolor Engine (24-bit ANSI) untuk merender gradient bar dan UI card shader secara live.
"""

import math
import sys
import time
from typing import Tuple, List

# --- Konfigurasi Terminal ANSI Truecolor ---
ANSI_RESET = "\x1b[0m"
ANSI_BOLD = "\x1b[1m"
ANSI_DIM = "\x1b[2m"
ANSI_CYAN = "\x1b[36m"
ANSI_GREEN = "\x1b[32m"
ANSI_YELLOW = "\x1b[33m"

def truecolor_fg(r: int, g: int, b: int) -> str:
    return f"\x1b[38;2;{r};{g};{b}m"

def truecolor_bg(r: int, g: int, b: int) -> str:
    return f"\x1b[48;2;{r};{g};{b}m"


# ============================================================================
# 1. MODUL COLOR SPACE: sRGB <-> Linear sRGB <-> Oklab <-> Oklch
# ============================================================================

def srgb_to_linear(c: float) -> float:
    """Mengubah sRGB terkompresi gamma menjadi Linear sRGB."""
    if c <= 0.04045:
        return c / 12.92
    return math.pow((c + 0.055) / 1.055, 2.4)

def linear_to_srgb(c: float) -> float:
    """Mengubah Linear sRGB kembali ke gamma sRGB dengan clamping [0, 1]."""
    c = max(0.0, min(1.0, c))
    if c <= 0.0031308:
        return 12.92 * c
    return 1.055 * math.pow(c, 1.0 / 2.4) - 0.055

def cbrt(v: float) -> float:
    """Cube root dengan penanganan angka negatif secara aman."""
    return math.copysign(abs(v) ** (1.0 / 3.0), v)

def rgb_to_oklab(r: float, g: float, b: float) -> Tuple[float, float, float]:
    """
    Konversi RGB [0..1] ke ruang Oklab (Björn Ottosson, standar CSS Color 4).
    L: Lightness [0..1], a: green-red axis, b: blue-yellow axis.
    """
    lr = srgb_to_linear(r)
    lg = srgb_to_linear(g)
    lb = srgb_to_linear(b)

    # Transfer linear RGB ke LMS cone space
    l = 0.4122214708 * lr + 0.5363325363 * lg + 0.0514459929 * lb
    m = 0.2119034982 * lr + 0.6806995451 * lg + 0.1073969566 * lb
    s = 0.0883024619 * lr + 0.2817188376 * lg + 0.6299787005 * lb

    l_ = cbrt(l)
    m_ = cbrt(m)
    s_ = cbrt(s)

    L = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    b_ok = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_

    return L, a, b_ok

def oklab_to_rgb(L: float, a: float, b: float) -> Tuple[float, float, float]:
    """Konversi Oklab kembali ke sRGB [0..1]."""
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b

    l = l_ * l_ * l_
    m = m_ * m_ * m_
    s = s_ * s_ * s_

    lr = +4.0767439362 * l - 3.3077115913 * m + 0.2309699290 * s
    lg = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    lb = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s

    return linear_to_srgb(lr), linear_to_srgb(lg), linear_to_srgb(lb)

def oklab_to_oklch(L: float, a: float, b: float) -> Tuple[float, float, float]:
    """Konversi Cartesian Oklab ke Polar Oklch (Lightness, Chroma, Hue [0..360])."""
    C = math.sqrt(a * a + b * b)
    h_rad = math.atan2(b, a)
    h_deg = math.degrees(h_rad)
    if h_deg < 0:
        h_deg += 360.0
    return L, C, h_deg

def oklch_to_oklab(L: float, C: float, h_deg: float) -> Tuple[float, float, float]:
    """Konversi Polar Oklch ke Cartesian Oklab."""
    h_rad = math.radians(h_deg)
    a = C * math.cos(h_rad)
    b = C * math.sin(h_rad)
    return L, a, b

def rgb_to_oklch(r: float, g: float, b: float) -> Tuple[float, float, float]:
    L, a, b_val = rgb_to_oklab(r, g, b)
    return oklab_to_oklch(L, a, b_val)

def oklch_to_rgb(L: float, C: float, h: float) -> Tuple[float, float, float]:
    L_ok, a, b = oklch_to_oklab(L, C, h)
    return oklab_to_rgb(L_ok, a, b)


# ============================================================================
# 2. SIMULASI CSS COLOR INTERPOLATION (color-mix())
# ============================================================================

def interpolate_srgb(rgb1: Tuple[float, float, float], rgb2: Tuple[float, float, float], t: float) -> Tuple[float, float, float]:
    """Interpolasi naive klasik standar CSS di sRGB."""
    return (
        rgb1[0] + (rgb2[0] - rgb1[0]) * t,
        rgb1[1] + (rgb2[1] - rgb1[1]) * t,
        rgb1[2] + (rgb2[2] - rgb1[2]) * t
    )

def interpolate_oklch(oklch1: Tuple[float, float, float], oklch2: Tuple[float, float, float], t: float) -> Tuple[float, float, float]:
    """
    Interpolasi Oklch modern dengan penanganan shortest hue path
    setara dengan CSS `color-mix(in oklch, c1, c2)`.
    """
    L1, C1, h1 = oklch1
    L2, C2, h2 = oklch2

    # Shortest hue path delta
    dh = (h2 - h1 + 180.0) % 360.0 - 180.0
    h_interp = (h1 + dh * t) % 360.0

    L_interp = L1 + (L2 - L1) * t
    C_interp = C1 + (C2 - C1) * t
    return L_interp, C_interp, h_interp


# ============================================================================
# 3. ADVANCED MATH UI & SHADER ENGINE (SDF + CSS Math functions)
# ============================================================================

def clamp(x: float, min_val: float, max_val: float) -> float:
    return max(min_val, min(max_val, x))

def smoothstep(edge0: float, edge1: float, x: float) -> float:
    """Implementasi fungsi smoothstep GLSL/CSS math untuk visual anti-aliasing."""
    t = clamp((x - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)

def sdf_rounded_box(px: float, py: float, bx: float, by: float, r: float) -> float:
    """
    Signed Distance Field untuk Rounded Rectangle UI Box.
    Mensimulasikan perhitungan modern CSS border-radius & box-shadow di fragment shader.
    """
    qx = abs(px) - bx + r
    qy = abs(py) - by + r
    outside_dist = math.hypot(max(qx, 0.0), max(qy, 0.0))
    inside_dist = min(max(qx, qy), 0.0)
    return outside_dist + inside_dist - r


# ============================================================================
# 4. BENCHMARK & RENDERING HARNESS
# ============================================================================

def render_gradient_strip(name: str, colors: List[Tuple[int, int, int]]):
    """Mencetak bar gradien visual 24-bit truecolor langsung di terminal."""
    sys.stdout.write(f"{ANSI_BOLD}{name:<22}{ANSI_RESET} |")
    for r, g, b in colors:
        sys.stdout.write(f"{truecolor_bg(r, g, b)} {ANSI_RESET}")
    sys.stdout.write("|\n")

def run_color_space_demo():
    print(f"\n{ANSI_CYAN}{ANSI_BOLD}=== [LAB STEP 1] MODERN COLOR SPACE CONVERSION & COLOR-MIX ENGINE ==={ANSI_RESET}")
    print(f"{ANSI_DIM}Menguji Oklab/Oklch perceptual uniformity dan perbandingan gradien Blue -> Yellow.{ANSI_RESET}\n")

    # Uji Konversi Blue & Yellow
    blue_rgb = (0.0, 0.0, 1.0)
    yellow_rgb = (1.0, 1.0, 0.0)

    blue_oklch = rgb_to_oklch(*blue_rgb)
    yellow_oklch = rgb_to_oklch(*yellow_rgb)

    print(f"Blue   RGB: (0.00, 0.00, 1.00) -> Oklch: L={blue_oklch[0]:.3f}, C={blue_oklch[1]:.3f}, h={blue_oklch[2]:.1f}°")
    print(f"Yellow RGB: (1.00, 1.00, 0.00) -> Oklch: L={yellow_oklch[0]:.3f}, C={yellow_oklch[1]:.3f}, h={yellow_oklch[2]:.1f}°\n")

    steps = 40
    srgb_samples = []
    oklch_samples = []

    for i in range(steps):
        t = i / (steps - 1)

        # Naive sRGB Interpolation
        r1, g1, b1 = interpolate_srgb(blue_rgb, yellow_rgb, t)
        srgb_samples.append((int(r1 * 255), int(g1 * 255), int(b1 * 255)))

        # CSS Color 4 Oklch Interpolation
        oklch_interp = interpolate_oklch(blue_oklch, yellow_oklch, t)
        r2, g2, b2 = oklch_to_rgb(*oklch_interp)
        oklch_samples.append((int(r2 * 255), int(g2 * 255), int(b2 * 255)))

    # Render Visual Gradients
    render_gradient_strip("sRGB Naive Gradient", srgb_samples)
    render_gradient_strip("Oklch CSS-4 Gradient", oklch_samples)

    # Analisis Midpoint (Dead-zone detection)
    mid_srgb = srgb_samples[steps // 2]
    mid_oklch = oklch_samples[steps // 2]
    print(f"\n{ANSI_YELLOW}Analisis Titik Tengah (t=0.5):{ANSI_RESET}")
    print(f" - sRGB Midpoint : RGB{mid_srgb} (Desaturated grayish mud)")
    print(f" - Oklch Midpoint: RGB{mid_oklch} (Vibrant natural green, mempertahankan perceptual chroma)")


def run_ui_shader_demo():
    print(f"\n{ANSI_CYAN}{ANSI_BOLD}=== [LAB STEP 2] CSS MATH UI SHADER & PROCEDURAL SURFACE (SDF) ==={ANSI_RESET}")
    print(f"{ANSI_DIM}Merender UI Card dengan Border Glow & Radial Shader menggunakan terminal ANSI.{ANSI_RESET}\n")

    width, height = 50, 18
    aspect = width / (height * 2.0)  # Koreksi font terminal aspect ratio

    t_start = time.perf_counter()
    pixel_count = 0

    for y in range(height):
        row_str = ""
        # Normalisasi UV coords ke rentang [-1.0, 1.0]
        uv_y = (y / (height - 1.0)) * 2.0 - 1.0

        for x in range(width):
            uv_x = ((x / (width - 1.0)) * 2.0 - 1.0) * aspect

            # Evaluasi SDF Box (Card dimensi: w=0.55, h=0.65, radius=0.20)
            d = sdf_rounded_box(uv_x, uv_y, 0.55, 0.65, 0.20)

            # Mathematical Surface (Simulasi CSS sin(), cos() background pattern)
            wave = math.sin(uv_x * 8.0) * math.cos(uv_y * 8.0)

            # Shading logic: Card Inner vs Border Glow vs Background
            if d < 0.0:
                # Inside Card: Gradien radial Oklch
                dist_center = math.hypot(uv_x, uv_y)
                lightness = clamp(0.75 - dist_center * 0.45 + wave * 0.05, 0.1, 0.95)
                chroma = 0.14
                hue = (210.0 + dist_center * 80.0) % 360.0
                r, g, b = oklch_to_rgb(lightness, chroma, hue)
                char = " "
            elif d < 0.08:
                # Border Glow Edge (Anti-aliased glow)
                glow = smoothstep(0.08, 0.0, d)
                r, g, b = oklch_to_rgb(0.85 * glow, 0.22, 140.0)
                char = "░" if glow < 0.6 else "▓"
            else:
                # Canvas Background: Gelap bertingkat
                bg_l = clamp(0.12 - d * 0.04, 0.02, 0.15)
                r, g, b = oklch_to_rgb(bg_l, 0.03, 260.0)
                char = "."

            ir, ig, ib = int(r * 255), int(g * 255), int(b * 255)
            row_str += f"{truecolor_bg(ir, ig, ib)}{truecolor_fg(255, 255, 255)}{char}{ANSI_RESET}"
            pixel_count += 1

        print(row_str)

    elapsed = (time.perf_counter() - t_start) * 1000.0
    print(f"\n{ANSI_GREEN}Shader Render Complete:{ANSI_RESET} {pixel_count} fragment SDF dievaluasi dalam {elapsed:.2f} ms.")


def main():
    print(f"{ANSI_BOLD}----------------------------------------------------------------------{ANSI_RESET}")
    print(f"{ANSI_BOLD}  LAB ADVANCED CSS: MODERN COLOR SPACES & PROCEDURAL UI SHADERS       {ANSI_RESET}")
    print(f"{ANSI_BOLD}----------------------------------------------------------------------{ANSI_RESET}")

    run_color_space_demo()
    run_ui_shader_demo()

    print(f"\n{ANSI_GREEN}{ANSI_BOLD}✔ SELURUH SUITE SIMULASI MATEMATIKA CSS BERHASIL DIEKSEKUSI.{ANSI_RESET}\n")

if __name__ == "__main__":
    main()