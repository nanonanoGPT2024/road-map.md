#!/usr/bin/env python3
"""
Visual System, Typography, dan Color Science Sandbox
Script ini mensimulasikan logika komputasi di balik pembuatan 
skala tipografi (Modular Scale) dan palet warna (Color Generator) 
yang umum digunakan dalam Design System (misal: Tailwind atau Material UI).
"""

import sys
import math
import json
import time

# --- ANSI Escape Codes untuk pewarnaan terminal ---
RESET = "\033[0m"
BOLD = "\033[1m"
UNDERLINE = "\033[4m"

def print_header(title):
    print(f"\n{BOLD}{'=' * 50}{RESET}")
    print(f"{BOLD} {title} {RESET}")
    print(f"{BOLD}{'=' * 50}{RESET}")

def print_step(message):
    print(f"\n[\033[94mINFO\033[0m] {message}")
    time.sleep(0.5)

# --- 1. Typography Scale Generator ---
class TypographyScaleGenerator:
    def __init__(self, base_size_px=16, ratio=1.250):
        self.base_size = base_size_px
        self.ratio = ratio
        self.levels = ["xs", "sm", "base", "lg", "xl", "2xl", "3xl", "4xl", "5xl"]
        # Posisi index untuk base font size (base adalah index 2)
        self.base_index = 2

    def generate(self):
        scale = {}
        for i, level in enumerate(self.levels):
            # Hitung eksponen berdasarkan jarak dari index base
            exponent = i - self.base_index
            size = self.base_size * (self.ratio ** exponent)
            
            # Hitung ideal line-height: semakin besar teks, semakin rapat line height-nya
            line_height = self._calculate_line_height(size)
            
            scale[level] = {
                "font_size_px": round(size, 2),
                "font_size_rem": round(size / 16.0, 3),
                "line_height": round(line_height, 2)
            }
        return scale
        
    def _calculate_line_height(self, font_size):
        # Logika sederhana: Base size punya line-height ~1.5
        # Heading besar punya line-height ~1.1 atau 1.2
        if font_size <= 16:
            return 1.5
        elif font_size <= 24:
            return 1.4
        elif font_size <= 36:
            return 1.2
        else:
            return 1.1

# --- 2. Color System Utilities (Hex, RGB, HSL) ---
def hex_to_rgb(hex_code):
    hex_code = hex_code.lstrip('#')
    return tuple(int(hex_code[i:i+2], 16) for i in (0, 2, 4))

def rgb_to_hsl(r, g, b):
    # R, G, B dalam range 0-255
    r /= 255.0
    g /= 255.0
    b /= 255.0
    
    max_val = max(r, g, b)
    min_val = min(r, g, b)
    l = (max_val + min_val) / 2.0
    
    if max_val == min_val:
        h = s = 0.0 # Achromatic
    else:
        d = max_val - min_val
        s = d / (2.0 - max_val - min_val) if l > 0.5 else d / (max_val + min_val)
        if max_val == r:
            h = (g - b) / d + (6.0 if g < b else 0.0)
        elif max_val == g:
            h = (b - r) / d + 2.0
        else:
            h = (r - g) / d + 4.0
        h /= 6.0
        
    return (h * 360, s, l)

def hsl_to_rgb(h, s, l):
    h /= 360.0
    if s == 0:
        r = g = b = l # Achromatic
    else:
        def hue_to_rgb(p, q, t):
            if t < 0: t += 1
            if t > 1: t -= 1
            if t < 1/6.0: return p + (q - p) * 6 * t
            if t < 1/2.0: return q
            if t < 2/3.0: return p + (q - p) * (2/3.0 - t) * 6
            return p
            
        q = l * (1 + s) if l < 0.5 else l + s - l * s
        p = 2 * l - q
        r = hue_to_rgb(p, q, h + 1/3.0)
        g = hue_to_rgb(p, q, h)
        b = hue_to_rgb(p, q, h - 1/3.0)
        
    return (int(r * 255), int(g * 255), int(b * 255))

def rgb_to_hex(r, g, b):
    return f"#{r:02x}{g:02x}{b:02x}".upper()

def get_ansi_bg_color(r, g, b):
    """Mengembalikan escape sequence ANSI 24-bit untuk warna background."""
    return f"\033[48;2;{r};{g};{b}m"

# --- 3. Palette Generator ---
class PaletteGenerator:
    def __init__(self, base_hex):
        self.base_hex = base_hex
        self.stops = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950]

    def generate(self):
        r, g, b = hex_to_rgb(self.base_hex)
        h, s, l = rgb_to_hsl(r, g, b)
        
        palette = {}
        for stop in self.stops:
            # Simulasi pergeseran Lightness (Semakin kecil stop, semakin terang)
            # Stop 50 -> lightness ~0.95
            # Stop 500 -> lightness asli base color
            # Stop 950 -> lightness ~0.10
            
            # Interpolasi linear sederhana untuk simulasi
            if stop == 500:
                new_l = l
            elif stop < 500:
                # Dari L sampai 0.95
                ratio = (500 - stop) / 450.0
                new_l = l + (0.95 - l) * ratio
            else:
                # Dari L sampai 0.10
                ratio = (stop - 500) / 450.0
                new_l = l - (l - 0.10) * ratio
                
            # Sedikit manipulasi saturation agar ujung tidak pucat
            new_s = min(1.0, s * (1.0 if stop == 500 else 0.9))
            
            nr, ng, nb = hsl_to_rgb(h, new_s, new_l)
            palette[stop] = {
                "hex": rgb_to_hex(nr, ng, nb),
                "rgb": (nr, ng, nb)
            }
            
        return palette

# --- Main Execution ---
def main():
    print_header("Design System Simulator: Typography & Color Science")
    
    # === SIMULASI TYPOGRAPHY ===
    base_size = 16
    ratio_name = "Major Third"
    ratio_val = 1.250
    print_step(f"Men-generate Typography Scale berbasis rasio {ratio_name} ({ratio_val})")
    
    typo_gen = TypographyScaleGenerator(base_size_px=base_size, ratio=ratio_val)
    typography_tokens = typo_gen.generate()
    
    print("\n\tTingkat\t| Ukuran (px)\t| Ukuran (rem)\t| Ideal Line-Height")
    print("\t" + "-" * 60)
    for level, data in typography_tokens.items():
        print(f"\ttext-{level:4}\t| {data['font_size_px']:7.2f} px\t| {data['font_size_rem']:5.3f} rem\t| {data['line_height']}")
        time.sleep(0.05)

    # === SIMULASI WARNA ===
    base_color_hex = "#3B82F6" # Warna biru khas Tailwind
    print_step(f"Men-generate Color Palette Monochromatic dari base color {base_color_hex} (biru)")
    
    color_gen = PaletteGenerator(base_color_hex)
    color_palette = color_gen.generate()
    
    print("\n\tShade\t| Hex Code\t| Visual Preview")
    print("\t" + "-" * 50)
    for stop, data in color_palette.items():
        h = data["hex"]
        r, g, b = data["rgb"]
        # ANSI preview block
        bg_ansi = get_ansi_bg_color(r, g, b)
        text_color = "\033[30m" if stop <= 400 else "\033[97m" # Text hitam di warna terang, putih di warna gelap
        preview_block = f"{bg_ansi}{text_color}     {h}     {RESET}"
        
        print(f"\tblu-{stop:<4}\t| {h}\t| {preview_block}")
        time.sleep(0.05)

    print_step("Mem-parsing hasil ke dalam Design Token JSON (Simulasi untuk export Frontend)...")
    
    # Output simulasi JSON
    design_tokens = {
        "typography": typography_tokens,
        "colors": {
            "blue": {str(k): v["hex"] for k, v in color_palette.items()}
        }
    }
    
    print("\n" + json.dumps(design_tokens, indent=2))
    
    print_header("Selesai! Script simulasi berhasil dijalankan.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nDihentikan oleh user.")
        sys.exit(1)
