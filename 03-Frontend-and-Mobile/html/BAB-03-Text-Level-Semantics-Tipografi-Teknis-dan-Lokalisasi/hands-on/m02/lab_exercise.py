#!/usr/bin/env python3
"""
Lab Hands-on: HTML Text-Level Semantics, Tipografi Teknis, dan Lokalisasi
Bab 03 - Modul 02 Deep Dive

Script ini memodelkan dan mensimulasikan mesin parsing serta layouting tipografi
tingkat teks (text-level semantics) yang mencakup:
1. Ruby Annotation Layouting (<ruby>, <rt>, <rp>) dengan kompensasi East-Asian Width.
2. Bi-directional (BiDi) Isolation (<bdi>, <bdo>) dan eliminasi Directional Bleeding.
3. Machine-Readable Semantic Extractor (<time>, <data>) berbasis ISO-8601.
4. Line Breaking Layout Engine dengan kalkulasi boundary break (<wbr>, &shy;).
"""

import sys
import re
import unicodedata
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict

# ANSI Terminal Color Sequences
CLR_RESET   = "\033[0m"
CLR_BOLD    = "\033[1m"
CLR_DIM     = "\033[2m"
CLR_RED     = "\033[31m"
CLR_GREEN   = "\033[32m"
CLR_YELLOW  = "\033[33m"
CLR_BLUE    = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN    = "\033[36m"
CLR_WHITE   = "\033[37m"
CLR_BG_DARK = "\033[48;5;236m"

def get_char_width(char: str) -> int:
    """
    Menghitung visual display width karakter berdasarkan Unicode East Asian Width.
    Karakter Wide ('W') dan Fullwidth ('F') berbobot 2 kolom, lainnya 1 kolom.
    """
    ea = unicodedata.east_asian_width(char)
    return 2 if ea in ('W', 'F') else 1

def get_string_width(text: str) -> int:
    """Menghitung total visual width sebuah string di terminal."""
    return sum(get_char_width(c) for c in text)


# ==============================================================================
# 1. RUBY ANNOTATION TYPESETTER (<ruby>, <rt>, <rp>)
# ==============================================================================

@dataclass
class RubyPair:
    base: str
    annotation: str

class RubyTypesetter:
    """
    Mensimulasikan layout engine perender teks fonetik Asia Timur (<ruby>).
    Menangani visual column alignment antara base character (kanji/hanzi)
    dan phonetic guide (furigana/zhuyin).
    """

    @staticmethod
    def render_terminal_ruby(pairs: List[RubyPair]) -> str:
        """
        Merender pasangan base dan ruby ke dalam representasi teks dua baris:
        Baris 1: Anotasi fonetik (<rt>) dengan padding sentral.
        Baris 2: Teks dasar (base) dengan lebar kolom yang seimbang.
        """
        top_line = []
        bottom_line = []

        for pair in pairs:
            base_w = get_string_width(pair.base)
            rt_w = get_string_width(pair.annotation)
            col_width = max(base_w, rt_w)

            # Padding kalkulasi untuk RT (Centering)
            pad_rt_total = col_width - rt_w
            pad_rt_l = pad_rt_total // 2
            pad_rt_r = pad_rt_total - pad_rt_l
            rt_segment = (" " * pad_rt_l) + pair.annotation + (" " * pad_rt_r)

            # Padding kalkulasi untuk Base (Centering)
            pad_base_total = col_width - base_w
            pad_base_l = pad_base_total // 2
            pad_base_r = pad_base_total - pad_base_l
            base_segment = (" " * pad_base_l) + pair.base + (" " * pad_base_r)

            top_line.append(f"{CLR_YELLOW}{rt_segment}{CLR_RESET}")
            bottom_line.append(f"{CLR_CYAN}{CLR_BOLD}{base_segment}{CLR_RESET}")

        return (
            "  " + "".join(top_line) + "\n" +
            "  " + "".join(bottom_line)
        )

    @staticmethod
    def linearize_fallback(pairs: List[RubyPair]) -> str:
        """
        Simulasi rendering fallback untuk browser/klien tanpa engine tipografi (<rp>).
        Format: Base(Annotation)
        """
        out = []
        for pair in pairs:
            out.append(f"{pair.base}<rp>(</rp><rt>{pair.annotation}</rt><rp>)</rp>")
        return "".join(out)


# ==============================================================================
# 2. BIDIRECTIONAL TEXT & ISOLATION SIMULATOR (<bdi>, <bdo>)
# ==============================================================================

class BiDiSimulator:
    """
    Mensimulasikan integrasi teks RTL (Right-to-Left) dan LTR (Left-to-Right).
    Mendemonstrasikan efek 'Directional Bleeding' saat inline teks RTL tidak
    diisolasi, dan bagaimana elemen HTML5 <bdi> serta <bdo> mengatasi masalah ini.
    """

    RTL_RANGES = [
        (0x0590, 0x05FF),  # Hebrew
        (0x0600, 0x06FF),  # Arabic
        (0x0750, 0x077F),  # Arabic Supplement
        (0x08A0, 0x08FF),  # Arabic Extended-A
    ]

    @classmethod
    def is_rtl(cls, text: str) -> bool:
        """Heuristik deteksi arah teks berdasarkan kode blok Unicode RTL."""
        for char in text:
            cp = ord(char)
            for start, end in cls.RTL_RANGES:
                if start <= cp <= end:
                    return True
        return False

    @staticmethod
    def simulate_bidi_resolution(raw_username: str, score: int, use_bdi: bool) -> str:
        """
        Mensimulasikan visual pipeline:
        Tanpa <bdi>: Karakter numerik/netral LTR setelah string RTL akan terserap
        ke dalam orientasi konteks RTL (menyebabkan layout bug).
        Dengan <bdi>: Menggunakan Unicode Directional Isolation (U+2068 & U+2069).
        """
        FSI = "\u2068"  # First Strong Isolate (<bdi>)
        PDI = "\u2069"  # Pop Directional Isolate
        
        if use_bdi:
            # Mengisolasi konteks teks pengguna secara terpisah
            return f"User {FSI}{raw_username}{PDI} achieved score: {score} pts"
        else:
            # Mengalir mentah: Karakter RTL mengancam boundary teks berikutnya
            return f"User {raw_username} achieved score: {score} pts"

    @staticmethod
    def simulate_bdo_override(text: str, direction: str) -> str:
        """
        Mensimulasikan elemen <bdo dir="rtl|ltr"> yang memaksa directional override
        menggunakan Unicode Formatting Controls (U+202E / U+202D).
        """
        RLO = "\u202E"  # Right-to-Left Override
        LRO = "\u202D"  # Left-to-Right Override
        PDF = "\u202C"  # Pop Directional Formatting

        override_char = RLO if direction.lower() == "rtl" else LRO
        return f"{override_char}{text}{PDF}"


# ==============================================================================
# 3. MACHINE-READABLE SEMANTICS VALIDATOR (<time>, <data>)
# ==============================================================================

class SemanticDataParser:
    """
    Parser dan validator spesifikasi teknis HTML5 untuk elemen <time datetime="...">
    dan <data value="...">.
    """

    ISO_DATETIME_REGEX = re.compile(
        r'^\d{4}-\d{2}-\d{2}'                          # YYYY-MM-DD
        r'(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?'    # THH:MM:SS
        r'(?:Z|[+-]\d{2}:?\d{2})?)?$'                  # Timezone offset
    )

    ISO_DURATION_REGEX = re.compile(
        r'^P(?:(\d+)Y)?(?:(\d+)M)?(?:(\d+)D)?'
        r'(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?)?$'
    )

    @classmethod
    def parse_time_element(cls, datetime_attr: str, visible_text: str) -> Dict[str, str]:
        """Validasi dan parsing mesin terhadap atribut datetime HTML5."""
        result = {
            "visible": visible_text,
            "raw_attribute": datetime_attr,
            "semantic_type": "UNKNOWN",
            "parsed_info": "",
            "valid": False
        }

        # 1. Cek Durasi ISO 8601 (HTML5 valid duration string)
        dur_match = cls.ISO_DURATION_REGEX.match(datetime_attr)
        if dur_match and any(dur_match.groups()):
            result["semantic_type"] = "DURATION"
            result["valid"] = True
            y, m, d, h, mn, s = dur_match.groups()
            parts = []
            if y: parts.append(f"{y} Tahun")
            if m: parts.append(f"{m} Bulan")
            if d: parts.append(f"{d} Hari")
            if h: parts.append(f"{h} Jam")
            if mn: parts.append(f"{mn} Menit")
            if s: parts.append(f"{s} Detik")
            result["parsed_info"] = ", ".join(parts)
            return result

        # 2. Cek Tanggal / Waktu ISO 8601
        if cls.ISO_DATETIME_REGEX.match(datetime_attr):
            result["valid"] = True
            try:
                # Normalisasi string untuk ISO parse Python
                iso_clean = datetime_attr.replace(" ", "T").replace("Z", "+00:00")
                parsed_dt = datetime.fromisoformat(iso_clean)
                result["semantic_type"] = "TIMESTAMP"
                result["parsed_info"] = parsed_dt.strftime("%d %B %Y, %H:%M:%S UTC%z")
            except ValueError:
                result["semantic_type"] = "DATE_ONLY"
                result["parsed_info"] = f"Valid Date Pattern ({datetime_attr})"
            return result

        return result


# ==============================================================================
# 4. OPPORTUNISTIC BREAKING & SOFT WRAP SIMULATOR (<wbr>, &shy;)
# ==============================================================================

class LineBreakEngine:
    """
    Mensimulasikan reflow teks berbasis kolom dengan parsing elemen pembagi kata:
    - <wbr>: Word Break Opportunity (pecah baris tanpa menambahkan tanda hubung)
    - &shy;: Soft Hyphen (pecah baris dengan menambahkan tanda '-')
    """

    @staticmethod
    def wrap_text(tokens: List[Tuple[str, str]], max_width: int) -> List[str]:
        """
        Menerima daftar token (text, break_type) di mana break_type:
        'NONE', 'WBR', 'SHY'
        """
        lines = []
        current_line = ""
        current_width = 0

        for text, break_type in tokens:
            seg_width = get_string_width(text)
            
            # Jika segmen muat di baris ini
            if current_width + seg_width <= max_width:
                current_line += text
                current_width += seg_width
            else:
                # Periksa apakah ada titik potong
                if current_width > 0:
                    lines.append(current_line)
                    current_line = text
                    current_width = seg_width
                else:
                    # Segmen tunggal melebihi kapasitas kolom, paksa break
                    current_line = text[:max_width]
                    lines.append(current_line)
                    remainder = text[max_width:]
                    current_line = remainder
                    current_width = get_string_width(remainder)

            # Evaluasi Break Opportunity
            if break_type == "WBR" and current_width >= (max_width * 0.75):
                lines.append(current_line)
                current_line = ""
                current_width = 0
            elif break_type == "SHY" and current_width >= (max_width * 0.75):
                lines.append(current_line + "-")
                current_line = ""
                current_width = 0

        if current_line:
            lines.append(current_line)

        return lines


# ==============================================================================
# MAIN EXECUTION ROUTINE
# ==============================================================================

def main():
    print(f"\n{CLR_BOLD}{CLR_BG_DARK}=== LAB: TEXT-LEVEL SEMANTICS, TIPOGRAFI, DAN LOKALISASI ==={CLR_RESET}\n")

    # --------------------------------------------------------------------------
    # DEMO 1: Ruby Typography Layouting
    # --------------------------------------------------------------------------
    print(f"{CLR_BOLD}{CLR_BLUE}[1] ANALISIS ELEMEN TIPOGRAFI TIMUR: <ruby>, <rt>, <rp>{CLR_RESET}")
    print(f"{CLR_DIM}Mensimulasikan perataan teks fonetik di atas hierarki kanji dan fallback mode:{CLR_RESET}\n")

    kanji_sample = [
        RubyPair(base="東", annotation="とう"),
        RubyPair(base="京", annotation="きょう"),
        RubyPair(base="特", annotation="とく"),
        RubyPair(base="許", annotation="きょ"),
        RubyPair(base="許", annotation="きょ"),
        RubyPair(base="可", annotation="か"),
        RubyPair(base="局", annotation="きょく"),
    ]

    rendered_ruby = RubyTypesetter.render_terminal_ruby(kanji_sample)
    fallback_text = RubyTypesetter.linearize_fallback(kanji_sample)

    print("--- [Visual Rendering (Browser Display Simulation)] ---")
    print(rendered_ruby)
    print("\n--- [Semantic Fallback Markup (<rp> linear mode)] ---")
    print(f"  {CLR_GREEN}{fallback_text}{CLR_RESET}\n")

    # --------------------------------------------------------------------------
    # DEMO 2: Bi-directional Text Isolation & Directional Bleeding
    # --------------------------------------------------------------------------
    print(f"{CLR_BOLD}{CLR_BLUE}[2] ISOLASI ARAH TEKS INTERNASIONAL: <bdi> vs <bdo>{CLR_RESET}")
    print(f"{CLR_DIM}Mencegah Directional Bleeding dari entri RTL ke dalam UI LTR:{CLR_RESET}\n")

    user_arabic = "سارة"  # Sarah (RTL)
    user_english = "JohnDoe" # LTR
    score = 42

    unisolated = BiDiSimulator.simulate_bidi_resolution(user_arabic, score, use_bdi=False)
    isolated = BiDiSimulator.simulate_bidi_resolution(user_arabic, score, use_bdi=True)
    overridden = BiDiSimulator.simulate_bdo_override("SYSTEM_OVERRIDE_RTL", direction="rtl")

    print(f"  [RAW / Tanpa <bdi>] : {CLR_RED}{unisolated}{CLR_RESET}")
    print(f"    * Catatan: Tanda titik dua dan angka berisiko tertukar urutan bacanya.")
    print(f"  [DENGAN <bdi>]     : {CLR_GREEN}{isolated}{CLR_RESET}")
    print(f"    * Isolasi terisolir via First-Strong Isolate (U+2068..U+2069).")
    print(f"  [DENGAN <bdo>]     : {CLR_MAGENTA}{overridden}{CLR_RESET}")
    print(f"    * Memaksa override arah teks secara mutlak (LTR ke RTL force layout).\n")

    # --------------------------------------------------------------------------
    # DEMO 3: Machine-Readable Semantics (<time>, <data>)
    # --------------------------------------------------------------------------
    print(f"{CLR_BOLD}{CLR_BLUE}[3] PARSER METADATA MESIN: <time> & <data>{CLR_RESET}")
    print(f"{CLR_DIM}Validasi format standar ISO-8601 untuk web spiders dan assistive tech:{CLR_RESET}\n")

    semantic_inputs = [
        ("2026-03-29T14:30:00Z", "Hari Minggu jam setengah tiga sore"),
        ("PT2H45M", "Durasi film: 2 jam 45 menit"),
        ("2026-12", "Edisi Desember 2026"),
        ("INVALID_STAMP_99", "Bukan format ISO"),
    ]

    for raw_attr, label in semantic_inputs:
        res = SemanticDataParser.parse_time_element(raw_attr, label)
        status_color = CLR_GREEN if res["valid"] else CLR_RED
        status_lbl = "VALID" if res["valid"] else "INVALID"

        print(f"  Markup: <time datetime=\"{CLR_BOLD}{raw_attr}{CLR_RESET}\">{label}</time>")
        print(f"  Status: {status_color}[{status_lbl}]{CLR_RESET} | Tipe: {res['semantic_type']}")
        print(f"  Parsed: {CLR_CYAN}{res['parsed_info']}{CLR_RESET}")
        print("  " + "-" * 50)
    print()

    # --------------------------------------------------------------------------
    # DEMO 4: Opportunistic Line Breaking Engine (<wbr>, &shy;)
    # --------------------------------------------------------------------------
    print(f"{CLR_BOLD}{CLR_BLUE}[4] LINE BREAK OPPORTUNITIES: <wbr> & &shy; SIMULATION{CLR_RESET}")
    print(f"{CLR_DIM}Mencegah overflow layout pada layar sempit/responsif:{CLR_RESET}\n")

    # String teknis panjang: Supercalifragilisticexpialidocious
    # Representasi: Super<wbr>cali<shy>fragilistic<wbr>expiali<shy>docious
    tokens = [
        ("Super", "WBR"),
        ("cali", "SHY"),
        ("fragilistic", "WBR"),
        ("expiali", "SHY"),
        ("docious", "NONE"),
        (" merupakan kata yang sangat panjang.", "NONE")
    ]

    container_width = 16
    print(f"  Simulasi Kontainer Lebar Tetap: {CLR_BOLD}{container_width} Kolom{CLR_RESET}")
    print(f"  {CLR_DIM}Boundary: |{'=' * container_width}|{CLR_RESET}")

    lines = LineBreakEngine.wrap_text(tokens, container_width)
    for idx, l in enumerate(lines, 1):
        pad = " " * (container_width - get_string_width(l))
        print(f"  Baris {idx:02d}: |{CLR_YELLOW}{l}{CLR_RESET}{pad}|")
    print(f"  {CLR_DIM}Boundary: |{'=' * container_width}|{CLR_RESET}\n")

    print(f"{CLR_BOLD}{CLR_GREEN}[✔] LAB BERHASIL DIEKSEKUSI SECARA INTEGRATIF TANPA EROR.{CLR_RESET}\n")

if __name__ == "__main__":
    main()