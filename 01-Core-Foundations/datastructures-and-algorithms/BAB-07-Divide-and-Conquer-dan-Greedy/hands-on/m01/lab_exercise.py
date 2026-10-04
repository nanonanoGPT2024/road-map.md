#!/usr/bin/env python3
"""
Hands-on Lab Exercise: Divide and Conquer vs. Greedy Algorithms
Modul 01: Algoritma D&C (Merge Sort, Karatsuba) & Greedy (Fractional Knapsack, Huffman Coding)
Simulasi Interaktif & Demonstrasi dengan Visualisasi Terminal ANSI
"""

import sys
import time
import heapq
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Any, Optional

# ANSI Color Codes
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
BLUE = "\033[94m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def print_header(title: str) -> None:
    print(f"\n{BOLD}{CYAN}{'=' * 65}{RESET}")
    print(f"{BOLD}{CYAN}>>> {title.center(57)} <<<{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 65}{RESET}\n")


def print_step(step: int, text: str, color: str = YELLOW) -> None:
    print(f" {BOLD}{color}[Langkah {step:02d}]{RESET} {text}")


# =====================================================================
# 1. DIVIDE AND CONQUER: Merge Sort dengan Visualisasi Pohon Rekursi
# =====================================================================
def merge_sort_visualized(arr: List[int], depth: int = 0) -> List[int]:
    indent = "    " * depth
    if len(arr) <= 1:
        print(f"{indent}{DIM}↳ Basis: {arr} (sudah terurut){RESET}")
        return arr

    mid = len(arr) // 2
    left_part = arr[:mid]
    right_part = arr[mid:]

    print(f"{indent}{BOLD}{BLUE}[DIVIDE depth={depth}]{RESET} Potong {arr} -> L: {left_part} | R: {right_part}")

    left_sorted = merge_sort_visualized(left_part, depth + 1)
    right_sorted = merge_sort_visualized(right_part, depth + 1)

    print(f"{indent}{BOLD}{GREEN}[CONQUER/COMBINE]{RESET} Menggabungkan L: {left_sorted} dan R: {right_sorted}")
    merged = []
    i = j = 0

    while i < len(left_sorted) and j < len(right_sorted):
        if left_sorted[i] <= right_sorted[j]:
            merged.append(left_sorted[i])
            i += 1
        else:
            merged.append(right_sorted[j])
            j += 1

    merged.extend(left_sorted[i:])
    merged.extend(right_sorted[j:])

    print(f"{indent}{BOLD}{MAGENTA}↳ Hasil Gabungan:{RESET} {merged}")
    return merged


# =====================================================================
# 2. DIVIDE AND CONQUER: Karatsuba Fast Multiplication
# =====================================================================
def karatsuba_multiply(x: int, y: int, depth: int = 0) -> int:
    indent = "  " * depth
    # Base case jika angka cukup kecil
    if x < 10 or y < 10:
        res = x * y
        print(f"{indent}{DIM}↳ Basis Rekursi: {x} * {y} = {res}{RESET}")
        return res

    n = max(len(str(x)), len(str(y)))
    m = n // 2

    # Pisahkan x dan y menjadi x1, x0 dan y1, y0
    power = 10 ** m
    x1, x0 = divmod(x, power)
    y1, y0 = divmod(y, power)

    print(f"{indent}{BOLD}{CYAN}[Karatsuba depth={depth}]{RESET} x={x}, y={y} (m={m})")
    print(f"{indent}  Submasalah: x1={x1}, x0={x0} | y1={y1}, y0={y0}")

    z2 = karatsuba_multiply(x1, y1, depth + 1)
    z0 = karatsuba_multiply(x0, y0, depth + 1)
    z1 = karatsuba_multiply(x1 + x0, y1 + y0, depth + 1)

    # Formula Karatsuba: z2 * 10^(2m) + (z1 - z2 - z0) * 10^m + z0
    middle = z1 - z2 - z0
    result = (z2 * (10 ** (2 * m))) + (middle * power) + z0

    print(f"{indent}  {BOLD}Kombinasi:{RESET} z2={z2}, z0={z0}, middle={middle} -> {BOLD}{GREEN}{result}{RESET}")
    return result


# =====================================================================
# 3. GREEDY: Fractional Knapsack Problem
# =====================================================================
@dataclass
class Item:
    name: str
    weight: float
    value: float

    @property
    def density(self) -> float:
        return self.value / self.weight if self.weight > 0 else 0.0


def fractional_knapsack(items: List[Item], capacity: float) -> Tuple[float, List[Dict[str, Any]]]:
    print(f"{BOLD}{YELLOW}Daftar Barang Sebelum Sorting (Nilai vs Bobot):{RESET}")
    for item in items:
        print(f"  - {item.name:10s} | Bobot: {item.weight:5.1f} kg | Nilai: ${item.value:6.1f} | Densitas: ${item.density:6.2f}/kg")

    # Prinsip Greedy: Urutkan secara descending berdasarkan density (value/weight)
    sorted_items = sorted(items, key=lambda it: it.density, reverse=True)

    print(f"\n{BOLD}{GREEN}Urutan Seleksi Greedy (Sorted by Value/Weight Ratio):{RESET}")
    for i, it in enumerate(sorted_items, 1):
        print(f"  {i}. {it.name:10s} | Densitas: ${it.density:6.2f}/kg")

    remaining_cap = capacity
    total_val = 0.0
    selections = []

    print(f"\n{BOLD}{CYAN}Proses Pengisian Ransel (Kapasitas: {capacity:.1f} kg):{RESET}")
    for it in sorted_items:
        if remaining_cap <= 0:
            break

        if it.weight <= remaining_cap:
            # Ambil seluruh barang
            taken_wt = it.weight
            fraction = 1.0
            taken_val = it.value
            remaining_cap -= taken_wt
            total_val += taken_val
            selections.append({"name": it.name, "fraction": fraction, "taken_weight": taken_wt, "value": taken_val})
            print(f"  {GREEN}[100% DIAMBIL]{RESET} {it.name:10s} (+{taken_wt:5.1f} kg, +${taken_val:6.1f}) | Sisa Kapasitas: {remaining_cap:5.1f} kg")
        else:
            # Ambil pecahan (fractional)
            fraction = remaining_cap / it.weight
            taken_wt = remaining_cap
            taken_val = it.value * fraction
            total_val += taken_val
            remaining_cap = 0
            selections.append({"name": it.name, "fraction": fraction, "taken_weight": taken_wt, "value": taken_val})
            print(f"  {MAGENTA}[{fraction * 100:5.1f}% DIAMBIL]{RESET} {it.name:10s} (+{taken_wt:5.1f} kg, +${taken_val:6.1f}) | Sisa Kapasitas: 0.0 kg")
            break

    return total_val, selections


# =====================================================================
# 4. GREEDY: Huffman Coding Simulation
# =====================================================================
@dataclass(order=True)
class HuffmanNode:
    freq: int
    char: Optional[str] = field(compare=False, default=None)
    left: Optional["HuffmanNode"] = field(compare=False, default=None)
    right: Optional["HuffmanNode"] = field(compare=False, default=None)


def build_huffman_tree(text: str) -> Optional[HuffmanNode]:
    if not text:
        return None

    # 1. Hitung frekuensi karakter
    freq_map: Dict[str, int] = {}
    for ch in text:
        freq_map[ch] = freq_map.get(ch, 0) + 1

    print(f"{BOLD}{YELLOW}Tabel Frekuensi Karakter:{RESET}")
    for ch, freq in sorted(freq_map.items(), key=lambda x: x[1], reverse=True):
        repr_char = "\\s" if ch == " " else ch
        print(f"  '{repr_char}': {freq} kali")

    # 2. Inisialisasi Min-Heap Priority Queue
    priority_queue: List[HuffmanNode] = [HuffmanNode(freq=f, char=c) for c, f in freq_map.items()]
    heapq.heapify(priority_queue)

    step = 1
    print(f"\n{BOLD}{CYAN}Konstruksi Pohon Huffman (Greedy Merge 2 Frekuensi Terkecil):{RESET}")

    # Khusus jika teks hanya memiliki 1 variasi karakter
    if len(priority_queue) == 1:
        root = priority_queue[0]
        dummy = HuffmanNode(freq=root.freq, left=root)
        return dummy

    # 3. Greedy Loop: Satukan 2 simpul berfrekuensi terendah
    while len(priority_queue) > 1:
        node1 = heapq.heappop(priority_queue)
        node2 = heapq.heappop(priority_queue)

        name1 = f"'{node1.char}'({node1.freq})" if node1.char else f"Sub({node1.freq})"
        name2 = f"'{node2.char}'({node2.freq})" if node2.char else f"Sub({node2.freq})"

        merged = HuffmanNode(freq=node1.freq + node2.freq, left=node1, right=node2)
        heapq.heappush(priority_queue, merged)

        print_step(step, f"Gabung {name1} + {name2} -> Parent({merged.freq})", GREEN)
        step += 1

    return priority_queue[0]


def generate_codes(root: Optional[HuffmanNode], current_code: str = "", code_book: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    if code_book is None:
        code_book = {}
    if root is None:
        return code_book

    if root.char is not None:
        code_book[root.char] = current_code or "0"
        return code_book

    if root.left:
        generate_codes(root.left, current_code + "0", code_book)
    if root.right:
        generate_codes(root.right, current_code + "1", code_book)

    return code_book


# =====================================================================
# INTERACTIVE CLI RUNNER & DEMONSTRATION
# =====================================================================
def run_merge_sort_demo():
    print_header("SIMULASI DIVIDE AND CONQUER: MERGE SORT")
    print(f"{DIM}Memecah array menjadi 2 sub-bagian, mengurutkan secara rekursif, lalu menggabungkannya.{RESET}\n")
    sample_data = [38, 27, 43, 3, 9, 82, 10]
    print(f"{BOLD}Array Awal:{RESET} {sample_data}\n")
    start_t = time.perf_counter()
    result = merge_sort_visualized(sample_data)
    dur = (time.perf_counter() - start_t) * 1000
    print(f"\n{BOLD}{GREEN}✓ Array Terurut Sempurna:{RESET} {result}")
    print(f"{DIM}Waktu eksekusi visual: {dur:.3f} ms{RESET}")


def run_karatsuba_demo():
    print_header("SIMULASI DIVIDE AND CONQUER: KARATSUBA MULTIPLICATION")
    x, y = 1234, 5678
    print(f"{DIM}Mengalikan bilangan besar dengan kompleksitas O(n^1.585) vs standard O(n^2).{RESET}")
    print(f"{BOLD}Perhitungan: {x} x {y}{RESET}\n")
    start_t = time.perf_counter()
    ans = karatsuba_multiply(x, y)
    dur = (time.perf_counter() - start_t) * 1000
    print(f"\n{BOLD}{GREEN}✓ Hasil Akhir Karatsuba:{RESET} {ans}")
    print(f"{BOLD}Verifikasi Python Native:{RESET} {x * y} (Cocok: {ans == x * y})")
    print(f"{DIM}Waktu eksekusi visual: {dur:.3f} ms{RESET}")


def run_fractional_knapsack_demo():
    print_header("SIMULASI GREEDY: FRACTIONAL KNAPSACK")
    items = [
        Item("Emas Murni", weight=10.0, value=600.0),
        Item("Perak Batangan", weight=20.0, value=1000.0),
        Item("Berlian Kasar", weight=30.0, value=1200.0),
        Item("Tembaga Halus", weight=15.0, value=150.0)
    ]
    max_cap = 50.0
    total_val, history = fractional_knapsack(items, max_cap)
    print(f"\n{BOLD}{GREEN}✓ Total Keuntungan Maksimum Didapat:{RESET} ${total_val:,.2f}")


def run_huffman_demo():
    print_header("SIMULASI GREEDY: HUFFMAN COMPRESSION CODING")
    sample_text = "STRUKTUR DATA DAN ALGORITMA GREEDY DIVIDE CONQUER"
    print(f"{BOLD}Teks Input ({len(sample_text)} karakter):{RESET} \"{sample_text}\"\n")

    root = build_huffman_tree(sample_text)
    codes = generate_codes(root)

    print(f"\n{BOLD}{GREEN}Kode Biner Huffman (Karakter Sering = Kode Pendek):{RESET}")
    for char, code in sorted(codes.items(), key=lambda it: len(it[1])):
        display_ch = "<SPASI>" if char == " " else char
        print(f"  {BOLD}{display_ch:8s}{RESET} -> {BOLD}{CYAN}{code:10s}{RESET} ({len(code)} bit)")

    encoded = "".join(codes[c] for c in sample_text)
    orig_bits = len(sample_text) * 8
    comp_bits = len(encoded)
    savings = (1 - (comp_bits / orig_bits)) * 100

    print(f"\n{BOLD}{YELLOW}Statistik Kompresi:{RESET}")
    print(f"  Ukuran Asli (8-bit ASCII) : {orig_bits} bit ({len(sample_text)} byte)")
    print(f"  Ukuran Huffman Encoded    : {comp_bits} bit (~{comp_bits // 8 + (1 if comp_bits % 8 else 0)} byte)")
    print(f"  Efisiensi / Penghematan   : {BOLD}{GREEN}{savings:.2f}%{RESET}")


def run_full_suite():
    run_merge_sort_demo()
    run_karatsuba_demo()
    run_fractional_knapsack_demo()
    run_huffman_demo()
    print_header("SEMUA SIMULASI BERHASIL DIEKSEKUSI")


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("--demo", "--all", "-a"):
        run_full_suite()
        return

    while True:
        print_header("LAB EXERCISE: DIVIDE & CONQUER vs GREEDY")
        print(f" {BOLD}Pilih simulasi interaktif yang ingin dijalankan:{RESET}")
        print(f"   {CYAN}[1]{RESET} Divide & Conquer : Visualisasi Merge Sort")
        print(f"   {CYAN}[2]{RESET} Divide & Conquer : Multiplikasi Cepat Karatsuba")
        print(f"   {CYAN}[3]{RESET} Greedy Algorithm : Fractional Knapsack Problem")
        print(f"   {CYAN}[4]{RESET} Greedy Algorithm : Kompresi Data Huffman Coding")
        print(f"   {CYAN}[5]{RESET} {BOLD}Jalankan Seluruh Suite Demo Sekaligus{RESET}")
        print(f"   {RED}[0]{RESET} Keluar")
        print(f"{DIM}{'-' * 65}{RESET}")

        try:
            choice = input(f"{BOLD}Masukkan nomor pilihan [0-5]: {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nKeluar...")
            break

        if choice == "1":
            run_merge_sort_demo()
        elif choice == "2":
            run_karatsuba_demo()
        elif choice == "3":
            run_fractional_knapsack_demo()
        elif choice == "4":
            run_huffman_demo()
        elif choice == "5":
            run_full_suite()
        elif choice == "0":
            print(f"\n{GREEN}Terima kasih telah menjalankan hands-on lab exercise.{RESET}\n")
            break
        else:
            print(f"{RED}Pilihan '{choice}' tidak valid. Silakan coba lagi.{RESET}")

        try:
            input(f"\n{DIM}Tekan [Enter] untuk kembali ke menu...{RESET}")
        except (KeyboardInterrupt, EOFError):
            break


if __name__ == "__main__":
    main()
