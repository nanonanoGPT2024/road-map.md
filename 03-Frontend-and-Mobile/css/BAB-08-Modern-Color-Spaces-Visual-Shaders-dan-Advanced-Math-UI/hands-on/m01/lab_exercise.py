#!/usr/bin/env python3
"""
Lab Exercise: Modern Color Spaces, Visual Shaders, and Advanced Math in CSS
BAB-08: Modern Color Spaces, Visual Shaders, dan Advanced Math UI

Simulates:
1. Color space transformations: sRGB <-> Linear sRGB <-> CIE XYZ <-> Oklab <-> Oklch
2. Gamut clipping & out-of-gamut detection for Display P3 / Rec.2020 vs sRGB
3. Perceptual gradient interpolation: CSS color-mix(in oklch, ...) vs color-mix(in srgb, ...)
4. CSS Advanced Math: clamp(), min(), max(), and trigonometric fluid layouts (sin/cos/atan2)
5. Procedural 2D shader simulation rendered via ANSI 24-bit TrueColor in terminal
"""

import math
import sys
import time
from typing import Tuple, List, Optional

# ANSI TrueColor formatting helpers
def ansi_fg(r: int, g: int, b: int, text: str) -> str:
    return f"\033[38;2;{r};{g};{b}m{text}\033[0m"

def ansi_bg(r: int, g: int, b: int, text: str = " ") -> str:
    return f"\033[48;2;{r};{g};{b}m{text}\033[0m"

def ansi_bold(text: str) -> str:
    return f"\033[1m{text}\033[0m"

# -----------------------------------------------------------------------------
# 1. COLOR SPACE MATH (sRGB, XYZ, Oklab, Oklch)
# -----------------------------------------------------------------------------

def srgb_to_linear(c: float) -> float:
    """Decodes gamma-corrected sRGB channel [0..1] into linear light."""
    if c <= 0.04045:
        return c / 12.92
    return math.pow((c + 0.055) / 1.055, 2.4)

def linear_to_srgb(c: float) -> float:
    """Encodes linear channel to sRGB [0..1] with gamma curve."""
    if c <= 0.0031308:
        return 12.92 * c
    return 1.055 * math.pow(max(0.0, c), 1.0 / 2.4) - 0.055

def srgb_to_oklab(r: float, g: float, b: float) -> Tuple[float, float, float]:
    """Converts standard sRGB [0..1] to Oklab (L, a, b)."""
    lr = srgb_to_linear(r)
    lg = srgb_to_linear(g)
    lb = srgb_to_linear(b)

    # Approximate LMS transform for Oklab
    l_cone = 0.4122214708 * lr + 0.5363325363 * lg + 0.0514459929 * lb
    m_cone = 0.2119034982 * lr + 0.6806995451 * lg + 0.1073969566 * lb
    s_cone = 0.0883024619 * lr + 0.2817188376 * lg + 0.6299787005 * lb

    l_ = math.pow(max(0.0, l_cone), 1.0 / 3.0)
    m_ = math.pow(max(0.0, m_cone), 1.0 / 3.0)
    s_ = math.pow(max(0.0, s_cone), 1.0 / 3.0)

    L = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    b_val = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
    return (L, a, b_val)

def oklab_to_srgb(L: float, a: float, b: float) -> Tuple[float, float, float, bool]:
    """Converts Oklab to sRGB [0..1]. Returns (r, g, b, in_gamut)."""
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b

    l_cone = l_ ** 3
    m_cone = m_ ** 3
    s_cone = s_ ** 3

    lr = +4.0767416621 * l_cone - 3.3077115913 * m_cone + 0.2309699292 * s_cone
    lg = -1.2684380046 * l_cone + 2.6097574011 * m_cone - 0.3413193965 * s_cone
    lb = -0.0041960863 * l_cone - 0.7034186147 * m_cone + 1.7076147010 * s_cone

    r = linear_to_srgb(lr)
    g = linear_to_srgb(lg)
    b_val = linear_to_srgb(lb)

    in_gamut = (0.0 <= r <= 1.0) and (0.0 <= g <= 1.0) and (0.0 <= b_val <= 1.0)
    # Gamut clip for display
    r_clipped = min(max(r, 0.0), 1.0)
    g_clipped = min(max(g, 0.0), 1.0)
    b_clipped = min(max(b_val, 0.0), 1.0)
    return (r_clipped, g_clipped, b_clipped, in_gamut)

def oklab_to_oklch(L: float, a: float, b: float) -> Tuple[float, float, float]:
    """Converts Oklab to Oklch (Lightness [0..1], Chroma [0..0.4+], Hue [0..360])."""
    C = math.sqrt(a * a + b * b)
    h_rad = math.atan2(b, a)
    h_deg = math.degrees(h_rad)
    if h_deg < 0:
        h_deg += 360.0
    return (L, C, h_deg)

def oklch_to_oklab(L: float, C: float, h_deg: float) -> Tuple[float, float, float]:
    """Converts Oklch to Oklab."""
    h_rad = math.radians(h_deg)
    a = C * math.cos(h_rad)
    b = C * math.sin(h_rad)
    return (L, a, b)

# -----------------------------------------------------------------------------
# 2. GRADIENT INTERPOLATION (color-mix in sRGB vs OKLCH)
# -----------------------------------------------------------------------------

def interpolate_srgb(c1: Tuple[float, float, float], c2: Tuple[float, float, float], t: float) -> Tuple[int, int, int]:
    """Naive sRGB linear interpolation (causes grey-dead-zones in gradients)."""
    r = (1 - t) * c1[0] + t * c2[0]
    g = (1 - t) * c1[1] + t * c2[1]
    b = (1 - t) * c1[2] + t * c2[2]
    return (int(r * 255), int(g * 255), int(b * 255))

def interpolate_oklch(c1: Tuple[float, float, float], c2: Tuple[float, float, float], t: float) -> Tuple[int, int, int]:
    """CSS color-mix(in oklch, ...) perceptual interpolation."""
    lab1 = srgb_to_oklab(c1[0], c1[1], c1[2])
    lab2 = srgb_to_oklab(c2[0], c2[1], c2[2])
    lch1 = oklab_to_oklch(*lab1)
    lch2 = oklab_to_oklch(*lab2)

    # Lightness and Chroma blend linearly
    L = (1 - t) * lch1[0] + t * lch2[0]
    C = (1 - t) * lch1[1] + t * lch2[1]

    # Hue interpolation: shortest angular path
    h1 = lch1[2]
    h2 = lch2[2]
    diff = (h2 - h1 + 180.0) % 360.0 - 180.0
    H = (h1 + diff * t) % 360.0

    lab_interp = oklch_to_oklab(L, C, H)
    r, g, b, _ = oklab_to_srgb(*lab_interp)
    return (int(r * 255), int(g * 255), int(b * 255))

# -----------------------------------------------------------------------------
# 3. ADVANCED MATH IN CSS: clamp(), min(), max(), trig UI
# -----------------------------------------------------------------------------

def css_clamp(min_val: float, val: float, max_val: float) -> float:
    """Simulates CSS clamp(MIN, VAL, MAX)."""
    return max(min_val, min(val, max_val))

def calculate_fluid_typography(viewport_width_px: float, min_vw: float = 320, max_vw: float = 1200,
                               min_font_rem: float = 1.0, max_font_rem: float = 2.5) -> dict:
    """
    Simulates CSS:
    font-size: clamp(1rem, 1rem + (2.5 - 1) * ((100vw - 320px) / (1200 - 320)), 2.5rem);
    """
    slope = (max_font_rem - min_font_rem) / (max_vw - min_vw)
    y_intercept = min_font_rem - slope * min_vw
    preferred_rem = y_intercept + slope * viewport_width_px
    clamped_rem = css_clamp(min_font_rem, preferred_rem, max_font_rem)
    return {
        "viewport_px": viewport_width_px,
        "raw_rem": round(preferred_rem, 3),
        "clamped_rem": round(clamped_rem, 3),
        "computed_px": round(clamped_rem * 16.0, 1)
    }

def circular_dial_coords(center_x: float, center_y: float, radius: float, angle_deg: float) -> Tuple[float, float]:
    """
    CSS Trigonometric functions (sin, cos) in polar layouts:
    transform: translate(calc(cos(var(--a)) * 100px), calc(sin(var(--a)) * 100px));
    """
    rad = math.radians(angle_deg)
    x = center_x + radius * math.cos(rad)
    y = center_y + radius * math.sin(rad)
    return (round(x, 2), round(y, 2))

# -----------------------------------------------------------------------------
# 4. VISUAL SHADER / PROCEDURAL SINE-WAVE SIMULATION (ANSI TrueColor)
# -----------------------------------------------------------------------------

def render_css_shader_preview(width: int = 50, height: int = 14, time_offset: float = 0.0) -> None:
    """
    Simulates a visual CSS fragment shader / noise mesh in terminal.
    Generates a swirling procedural plasma using trigonometric equations and Oklch coloring.
    """
    print(ansi_bold("\n=== Visual Shader Simulation (CSS Fragment Shader on Terminal Canvas) ==="))
    print("Shader Formula: z = sin(3*x + t) + cos(2*y - t) + sin((x+y)*2 + t)")
    
    for y in range(height):
        row_str = ""
        ny = (y / float(height)) * 2.0 - 1.0  # normalize [-1..1]
        for x in range(width):
            nx = (x / float(width)) * 2.0 - 1.0  # normalize [-1..1]
            
            # Procedural wave field
            v1 = math.sin(nx * 3.0 + time_offset)
            v2 = math.cos(ny * 2.5 - time_offset * 0.8)
            v3 = math.sin((nx + ny) * 2.0 + time_offset * 1.2)
            wave = (v1 + v2 + v3) / 3.0  # [-1..1]
            
            # Map wave to OKLCH:
            # Lightness: 0.4 to 0.85
            # Chroma: 0.15 to 0.28
            # Hue: 180 to 360 (Cyan to Magenta spectrum)
            L = 0.55 + 0.3 * wave
            C = 0.18 + 0.08 * math.cos(wave * math.pi)
            H = (200.0 + 160.0 * ((wave + 1.0) / 2.0) + time_offset * 20.0) % 360.0
            
            lab = oklch_to_oklab(L, C, H)
            r, g, b, in_gamut = oklab_to_srgb(*lab)
            ir, ig, ib = int(r * 255), int(g * 255), int(b * 255)
            
            # Render dual-pixel or single space block
            row_str += ansi_bg(ir, ig, ib, " ")
        print(row_str)
    print(ansi_fg(160, 160, 160, f"Rendered {width}x{height} TrueColor pixels. Time offset: {time_offset:.2f}s\n"))

# -----------------------------------------------------------------------------
# 5. DEMONSTRATION SUITES
# -----------------------------------------------------------------------------

def demo_color_spaces() -> None:
    print(ansi_bold("\n[1] Modern Color Spaces: sRGB vs Oklab vs Oklch"))
    print("CSS Color Module Level 4 introduces perceptual color spaces.")
    test_colors = [
        ("Vibrant Cyan", (0.0, 1.0, 1.0)),
        ("Hot Pink", (1.0, 0.08, 0.58)),
        ("Electric Indigo", (0.29, 0.0, 0.51)),
        ("Pure Yellow", (1.0, 1.0, 0.0)),
    ]

    for name, (r, g, b) in test_colors:
        L, a, b_val = srgb_to_oklab(r, g, b)
        L_ch, C, H = oklab_to_oklch(L, a, b_val)
        
        rgb_int = (int(r * 255), int(g * 255), int(b * 255))
        swatch = ansi_bg(rgb_int[0], rgb_int[1], rgb_int[2], "    ")
        
        print(f"{swatch} {ansi_bold(name)}:")
        print(f"   • sRGB: rgb({rgb_int[0]}, {rgb_int[1]}, {rgb_int[2]})")
        print(f"   • Oklab: oklab({L:.3f} {a:.3f} {b_val:.3f})")
        print(f"   • Oklch: oklch({L_ch:.1%} {C:.3f} {H:.1f}deg)")

def demo_gradient_interpolation() -> None:
    print(ansi_bold("\n[2] Gradient Interpolation: color-mix(in srgb) vs color-mix(in oklch)"))
    print("Demonstrating the notorious 'grey dead zone' when blending Blue and Yellow:")
    
    blue = (0.0, 0.0, 1.0)
    yellow = (1.0, 1.0, 0.0)
    steps = 40

    # sRGB Gradient
    srgb_bar = ""
    for i in range(steps):
        t = i / float(steps - 1)
        r, g, b = interpolate_srgb(blue, yellow, t)
        srgb_bar += ansi_bg(r, g, b, " ")
    
    # Oklch Gradient
    oklch_bar = ""
    for i in range(steps):
        t = i / float(steps - 1)
        r, g, b = interpolate_oklch(blue, yellow, t)
        oklch_bar += ansi_bg(r, g, b, " ")

    print("\n   [sRGB Gradient (Notice muddy grey/brownish center)]:")
    print(f"   {srgb_bar}")
    print("\n   [OKLCH Gradient (Perceptually smooth transition through vibrant greens)]:")
    print(f"   {oklch_bar}\n")

def demo_advanced_math() -> None:
    print(ansi_bold("\n[3] Advanced Math UI: CSS clamp(), min(), max(), and Trigonometry"))
    print("Fluid Typography test across multiple viewport sizes:")
    test_viewports = [280, 320, 600, 768, 1024, 1200, 1600]
    
    for vp in test_viewports:
        data = calculate_fluid_typography(vp)
        print(f"   • Viewport {vp:4d}px -> clamp(1rem, ..., 2.5rem) = {data['clamped_rem']}rem ({data['computed_px']}px)")
    
    print("\nTrigonometric Circular Radial Menu positioning (CSS sin() & cos()):")
    menu_items = ["Home", "Profile", "Settings", "Notifications", "Help", "Logout"]
    total = len(menu_items)
    for idx, label in enumerate(menu_items):
        deg = (360.0 / total) * idx
        x, y = circular_dial_coords(center_x=0.0, center_y=0.0, radius=120.0, angle_deg=deg)
        print(f"   • {label:<14} (Angle: {deg:5.1f}deg) -> transform: translate({x:6.1f}px, {y:6.1f}px);")

# -----------------------------------------------------------------------------
# 6. INTERACTIVE CLI RUNNER
# -----------------------------------------------------------------------------

def interactive_loop() -> None:
    banner = f"""
{ansi_bold('========================================================================')}
{ansi_fg(100, 200, 255, ansi_bold('   CSS FOUNDATION: BAB-08 LAB EXERCISE'))}
{ansi_fg(200, 200, 200, '   Modern Color Spaces, Visual Shaders & Advanced Math in CSS')}
{ansi_bold('========================================================================')}
Options:
  1. Inspect Modern Color Spaces (sRGB, Oklab, Oklch)
  2. Compare Gradient Interpolation (sRGB vs OKLCH color-mix)
  3. Simulate CSS clamp() Fluid Typography & Trigonometry UI
  4. Render CSS Fragment Shader Animation (ANSI TrueColor)
  5. Run Full Automated Benchmark Suite
  6. Exit
"""
    print(banner)

    # Check if run non-interactively or with flags
    if not sys.stdin.isatty() or len(sys.argv) > 1:
        print("[Non-interactive mode detected. Running full demonstration suite...]")
        demo_color_spaces()
        demo_gradient_interpolation()
        demo_advanced_math()
        render_css_shader_preview(width=60, height=12, time_offset=1.5)
        print(ansi_bold("Lab verification complete. All technical concepts executed successfully."))
        return

    while True:
        try:
            choice = input(ansi_bold("\nSelect an option [1-6]: ")).strip()
            if choice == "1":
                demo_color_spaces()
            elif choice == "2":
                demo_gradient_interpolation()
            elif choice == "3":
                demo_advanced_math()
            elif choice == "4":
                print("\nRendering animated shader frames (press Ctrl+C to stop)...")
                try:
                    for frame in range(12):
                        # Clear screen or print newline
                        render_css_shader_preview(width=54, height=12, time_offset=frame * 0.3)
                        time.sleep(0.1)
                except KeyboardInterrupt:
                    print("\nAnimation paused.")
            elif choice == "5":
                demo_color_spaces()
                demo_gradient_interpolation()
                demo_advanced_math()
                render_css_shader_preview(width=60, height=12, time_offset=2.0)
            elif choice in ("6", "q", "exit"):
                print("Exiting Lab Exercise. Happy CSS Coding!")
                break
            else:
                print("Invalid option. Please choose between 1 and 6.")
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            break

if __name__ == "__main__":
    interactive_loop()
