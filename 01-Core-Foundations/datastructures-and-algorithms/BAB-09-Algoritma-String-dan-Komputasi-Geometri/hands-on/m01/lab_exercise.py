#!/usr/bin/env python3
"""
Hands-on Lab Exercise M01: Algoritma String & Komputasi Geometri
BAB-09: Algoritma String dan Komputasi Geometri

Simulasi Interaktif:
1. String Matching: Knuth-Morris-Pratt (KMP) & Visualisasi Prefix Table (LPS)
2. String Matching: Rabin-Karp dengan Rolling Hash
3. Komputasi Geometri: Uji Orientasi Titik (Cross Product / Turn Test)
4. Komputasi Geometri: Convex Hull (Monotone Chain / Graham Scan)
"""

import sys
import time
from typing import List, Tuple

# ANSI Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"
BG_BLUE = "\033[44m"
BG_GREEN = "\033[42m"


# ==========================================
# 1. ALGORITMA STRING: KMP (KNUTH-MORRIS-PRATT)
# ==========================================

def compute_lps(pattern: str) -> List[int]:
    """Menghitung Longest Prefix Suffix (LPS) array untuk KMP."""
    m = len(pattern)
    lps = [0] * m
    length = 0
    i = 1

    while i < m:
        if pattern[i] == pattern[length]:
            length += 1
            lps[i] = length
            i += 1
        else:
            if length != 0:
                length = lps[length - 1]
            else:
                lps[i] = 0
                i += 1
    return lps


def kmp_search(text: str, pattern: str) -> List[int]:
    """Pencarian substring KMP dengan visualisasi pergeseran index."""
    n = len(text)
    m = len(pattern)
    if m == 0 or n == 0 or m > n:
        return []

    lps = compute_lps(pattern)
    matches = []

    print(f"\n{BOLD}{CYAN}=== KMP STRING MATCHING ENGINE ==={RESET}")
    print(f"Text   : {YELLOW}{text}{RESET} (panjang: {n})")
    print(f"Pattern: {MAGENTA}{pattern}{RESET} (panjang: {m})")
    print(f"LPS Array: {lps}\n")

    i = 0  # index text
    j = 0  # index pattern
    step = 1

    while i < n:
        # Visualisasi perbandingan karakter
        status = "MATCH" if text[i] == pattern[j] else "MISMATCH"
        color = GREEN if text[i] == pattern[j] else RED
        print(f"Step {step:02d} | T[{i}]='{text[i]}' vs P[{j}]='{pattern[j]}' -> {color}{status}{RESET}")
        step += 1

        if pattern[j] == text[i]:
            i += 1
            j += 1

        if j == m:
            matches.append(i - j)
            print(f"  {BG_GREEN}{WHITE} FOUND MATCH AT INDEX {i - j} {RESET}")
            j = lps[j - 1]
        elif i < n and pattern[j] != text[i]:
            if j != 0:
                print(f"  {BLUE}-> Fallback j dari {j} ke lps[{j-1}]={lps[j-1]}{RESET}")
                j = lps[j - 1]
            else:
                i += 1

    return matches


# ==========================================
# 2. ALGORITMA STRING: RABIN-KARP ROLLING HASH
# ==========================================

def rabin_karp_search(text: str, pattern: str, prime: int = 101, base: int = 256) -> List[int]:
    """Pencarian string dengan Rolling Hash Rabin-Karp."""
    n = len(text)
    m = len(pattern)
    matches = []

    if m == 0 or n == 0 or m > n:
        return []

    h = pow(base, m - 1, prime)
    p_hash = 0
    t_hash = 0

    for i in range(m):
        p_hash = (base * p_hash + ord(pattern[i])) % prime
        t_hash = (base * t_hash + ord(text[i])) % prime

    print(f"\n{BOLD}{CYAN}=== RABIN-KARP ROLLING HASH ENGINE ==={RESET}")
    print(f"Target Pattern Hash: {MAGENTA}{p_hash}{RESET} (Prime: {prime}, Base: {base})")

    for i in range(n - m + 1):
        if p_hash == t_hash:
            # Hash collision check (spurious hit prevention)
            if text[i:i + m] == pattern:
                matches.append(i)
                print(f"Window [{i}:{i+m}] Hash={GREEN}{t_hash}{RESET} -> {BOLD}{GREEN}VERIFIED MATCH!{RESET}")
            else:
                print(f"Window [{i}:{i+m}] Hash={YELLOW}{t_hash}{RESET} -> {YELLOW}SPURIOUS HIT (Collision){RESET}")
        else:
            print(f"Window [{i}:{i+m}] Hash={WHITE}{t_hash}{RESET} != {p_hash}")

        # Hitung rolling hash untuk jendela berikutnya
        if i < n - m:
            t_hash = (base * (t_hash - ord(text[i]) * h) + ord(text[i + m])) % prime
            if t_hash < 0:
                t_hash += prime

    return matches


# ==========================================
# 3. KOMPUTASI GEOMETRI: TITIK & CROSS PRODUCT
# ==========================================

Point = Tuple[float, float]

def cross_product(o: Point, a: Point, b: Point) -> float:
    """
    Menghitung 2D Cross Product dari vektor OA dan OB.
    Return:
      > 0: Counter-Clockwise (Belok Kiri)
      < 0: Clockwise (Belok Kanan)
      = 0: Kolinier (Segaris lurus)
    """
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def analyze_orientation(p1: Point, p2: Point, p3: Point) -> None:
    """Menganalisis arah belokan dari p1 -> p2 -> p3."""
    val = cross_product(p1, p2, p3)
    print(f"\n{BOLD}{CYAN}=== UJI ORIENTASI TITIK (TURN TEST) ==={RESET}")
    print(f"P1 = {p1}, P2 = {p2}, P3 = {p3}")
    print(f"Cross Product OA x OB = {val:.4f}")

    if abs(val) < 1e-9:
        print(f"Hasil: {BOLD}{YELLOW}KOLINIER (Garis Lurus / Co-linear){RESET}")
    elif val > 0:
        print(f"Hasil: {BOLD}{GREEN}COUNTER-CLOCKWISE (Belok Kiri / CCW){RESET}")
    else:
        print(f"Hasil: {BOLD}{RED}CLOCKWISE (Belok Kanan / CW){RESET}")


# ==========================================
# 4. KOMPUTASI GEOMETRI: CONVEX HULL
# ==========================================

def convex_hull_monotone(points: List[Point]) -> List[Point]:
    """
    Algoritma Monotone Chain (Andrew's Algorithm) untuk Convex Hull.
    Kompleksitas: O(n log n)
    """
    pts = sorted(set(points))
    if len(pts) <= 1:
        return pts

    # Lower hull
    lower = []
    for p in pts:
        while len(lower) >= 2 and cross_product(lower[-2], lower[-1], p) <= 0:
            popped = lower.pop()
            print(f"  {RED}[Pop Lower]{RESET} Hapus {popped} karena belok kanan ke {p}")
        lower.append(p)
        print(f"  {GREEN}[Add Lower]{RESET} Tambah {p}")

    # Upper hull
    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross_product(upper[-2], upper[-1], p) <= 0:
            popped = upper.pop()
            print(f"  {RED}[Pop Upper]{RESET} Hapus {popped} karena belok kanan ke {p}")
        upper.append(p)
        print(f"  {GREEN}[Add Upper]{RESET} Tambah {p}")

    # Gabung lower dan upper (buang titik duplikat di ujung)
    hull = lower[:-1] + upper[:-1]
    return hull


# ==========================================
# CLI INTERAKTIF MENU
# ==========================================

def banner():
    print(f"{BOLD}{BG_BLUE}{WHITE}")
    print("=" * 64)
    print("  LAB EXERCISE M01: STRING & COMPUTATIONAL GEOMETRY SIMULATOR  ")
    print("=" * 64 + f"{RESET}")


def menu():
    print(f"\n{BOLD}Menu Pilihan Simulasi:{RESET}")
    print(f" {CYAN}1.{RESET} KMP String Matching & Visualisasi LPS")
    print(f" {CYAN}2.{RESET} Rabin-Karp Rolling Hash Matching")
    print(f" {CYAN}3.{RESET} Geometry Orientation Test (Cross Product)")
    print(f" {CYAN}4.{RESET} Convex Hull (Andrew's Monotone Chain)")
    print(f" {CYAN}5.{RESET} Jalankan Seluruh Demo Lengkap")
    print(f" {RED}0.{RESET} Keluar")


def run_full_demo():
    print(f"\n{BOLD}{MAGENTA}>>> MEMULAI AUTOMATED FULL SUITE DEMO <<<{RESET}")
    time.sleep(0.5)

    # Demo KMP
    text_sample = "ABABDABACDABABCABAB"
    pat_sample = "ABABCABAB"
    kmp_matches = kmp_search(text_sample, pat_sample)
    print(f"Hasil Pencocokan KMP Index: {GREEN}{kmp_matches}{RESET}")

    time.sleep(0.5)

    # Demo Rabin-Karp
    text_rk = "GEEKS FOR GEEKS"
    pat_rk = "GEEK"
    rk_matches = rabin_karp_search(text_rk, pat_rk)
    print(f"Hasil Pencocokan Rabin-Karp Index: {GREEN}{rk_matches}{RESET}")

    time.sleep(0.5)

    # Demo Orientation
    analyze_orientation((0, 0), (4, 4), (1, 2))
    analyze_orientation((0, 0), (4, 4), (4, 0))
    analyze_orientation((0, 0), (2, 2), (4, 4))

    time.sleep(0.5)

    # Demo Convex Hull
    points_sample = [
        (0, 3), (2, 2), (1, 1), (2, 1),
        (3, 0), (0, 0), (3, 3), (1, 2)
    ]
    print(f"\n{BOLD}{CYAN}=== CONVEX HULL (MONOTONE CHAIN) ==={RESET}")
    print(f"Titik Masukan ({len(points_sample)} titik): {points_sample}")
    hull = convex_hull_monotone(points_sample)
    print(f"\n{BOLD}{GREEN}Titik Pembentuk Perimeter Convex Hull ({len(hull)} titik):{RESET}")
    for idx, pt in enumerate(hull):
        print(f"  Peringkat {idx+1}: {YELLOW}{pt}{RESET}")


def interactive_loop():
    while True:
        menu()
        choice = input(f"\n{YELLOW}Pilih opsi [0-5]: {RESET}").strip()

        if choice == "1":
            t = input(f"Masukkan Text [{WHITE}ABABDABACDABABCABAB{RESET}]: ").strip() or "ABABDABACDABABCABAB"
            p = input(f"Masukkan Pattern [{WHITE}ABABCABAB{RESET}]: ").strip() or "ABABCABAB"
            res = kmp_search(t, p)
            print(f"\nIndex Kecocokan: {GREEN}{res}{RESET}")
        elif choice == "2":
            t = input(f"Masukkan Text [{WHITE}AABAACAADAABAABA{RESET}]: ").strip() or "AABAACAADAABAABA"
            p = input(f"Masukkan Pattern [{WHITE}AABA{RESET}]: ").strip() or "AABA"
            res = rabin_karp_search(t, p)
            print(f"\nIndex Kecocokan: {GREEN}{res}{RESET}")
        elif choice == "3":
            try:
                p1_raw = input("P1 (x y) [default: 0 0]: ").strip() or "0 0"
                p2_raw = input("P2 (x y) [default: 2 2]: ").strip() or "2 2"
                p3_raw = input("P3 (x y) [default: 1 3]: ").strip() or "1 3"
                p1 = tuple(map(float, p1_raw.split()))
                p2 = tuple(map(float, p2_raw.split()))
                p3 = tuple(map(float, p3_raw.split()))
                analyze_orientation(p1, p2, p3)  # type: ignore
            except Exception as e:
                print(f"{RED}Input koordinat tidak valid: {e}{RESET}")
        elif choice == "4":
            sample = [(0, 0), (1, 4), (3, 1), (3, 3), (5, 2), (5, 5), (9, 0), (4, 4), (7, 3)]
            print(f"Menggunakan 9 titik uji geometris: {sample}")
            hull = convex_hull_monotone(sample)
            print(f"\n{BOLD}{GREEN}Convex Hull Points:{RESET} {hull}")
        elif choice == "5":
            run_full_demo()
        elif choice == "0":
            print(f"\n{GREEN}Terima kasih! Sesi lab exercise selesai.{RESET}\n")
            break
        else:
            print(f"{RED}Pilihan tidak valid. Silakan coba lagi.{RESET}")


if __name__ == "__main__":
    banner()
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        run_full_demo()
    else:
        # Jika non-interaktif atau diarahkan ke pipe, otomatis jalankan demo
        if not sys.stdin.isatty():
            run_full_demo()
        else:
            interactive_loop()
