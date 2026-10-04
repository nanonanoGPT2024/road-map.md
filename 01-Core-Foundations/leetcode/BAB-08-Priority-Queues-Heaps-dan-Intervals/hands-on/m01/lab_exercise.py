#!/usr/bin/env python3
"""
=============================================================================
LAB EXERCISE M01: PRIORITY QUEUES, HEAPS & INTERVALS SIMULATOR
LeetCode Foundation: BAB-08 Priority Queues, Heaps & Intervals
=============================================================================
Simulasi interaktif algoritma Min-Heap, Max-Heap, Top-K Filtering,
dan Interval Merging dengan visualisasi ASCII/ANSI Terminal.
"""

import sys
import heapq
import time
from typing import List, Tuple, Optional

# --- ANSI Color Palette ---
class Color:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN    = "\033[96m"
    BG_BLUE = "\033[44m"
    BG_DARK = "\033[40m"


def print_banner(title: str) -> None:
    width = 68
    print(f"\n{Color.CYAN}{'═' * width}{Color.RESET}")
    print(f"{Color.BOLD}{Color.MAGENTA}  ▶ {title.upper()}{Color.RESET}")
    print(f"{Color.CYAN}{'═' * width}{Color.RESET}")


def print_step(step_num: int, description: str) -> None:
    print(f"\n{Color.YELLOW}[Langkah {step_num}]{Color.RESET} {Color.BOLD}{description}{Color.RESET}")


# --- MODUL 1: Min-Heap Interactive Visualizer ---
class VisualMinHeap:
    def __init__(self):
        self.heap: List[int] = []

    def push(self, val: int) -> None:
        print(f"  {Color.GREEN}+ Menambahkan nilai {val} ke heap...{Color.RESET}")
        heapq.heappush(self.heap, val)
        self.render()

    def pop(self) -> Optional[int]:
        if not self.heap:
            print(f"  {Color.RED}! Heap kosong, tidak bisa pop.{Color.RESET}")
            return None
        val = heapq.heappop(self.heap)
        print(f"  {Color.RED}- Mengambil elemen root terkecil: {val}{Color.RESET}")
        self.render()
        return val

    def peek(self) -> Optional[int]:
        return self.heap[0] if self.heap else None

    def render(self) -> None:
        print(f"    {Color.DIM}Array internal: {Color.RESET}{Color.BOLD}{self.heap}{Color.RESET}")
        if not self.heap:
            print(f"    {Color.DIM}(Heap kosong){Color.RESET}")
            return

        # Simple tree visualizer for up to 7 elements (depth 3)
        h = self.heap
        n = len(h)
        print(f"    {Color.CYAN}Struktur Hirarki Pohon Biner:{Color.RESET}")
        print(f"            [{Color.GREEN}{h[0]}{Color.RESET}]")
        if n > 1:
            left1 = f"[{h[1]}]"
            right1 = f"[{h[2]}]" if n > 2 else "   "
            print(f"           /      \\")
            print(f"       {Color.YELLOW}{left1:^6}{Color.RESET}   {Color.YELLOW}{right1:^6}{Color.RESET}")
        if n > 3:
            l2_1 = f"[{h[3]}]"
            l2_2 = f"[{h[4]}]" if n > 4 else ""
            l2_3 = f"[{h[5]}]" if n > 5 else ""
            l2_4 = f"[{h[6]}]" if n > 6 else ""
            print(f"       /   \\      /   \\")
            print(f"     {l2_1:4}{l2_2:4}  {l2_3:4}{l2_4:4}")


# --- MODUL 2: Top-K Pattern (Kth Largest Element) ---
def simulate_top_k_stream(numbers: List[int], k: int) -> None:
    print_banner(f"Simulasi Top-{k} Elemen Terbesar (Bounded Min-Heap)")
    print(f"Stream Data: {Color.BOLD}{numbers}{Color.RESET}")
    print(f"Kapasitas Heap dibatasi tepat {Color.BOLD}k = {k}{Color.RESET}\n")

    min_heap: List[int] = []

    for i, num in enumerate(numbers, 1):
        print(f"{Color.CYAN}Item #{i:02d}:{Color.RESET} Datang nilai {Color.BOLD}{num}{Color.RESET}")
        if len(min_heap) < k:
            heapq.heappush(min_heap, num)
            print(f"  Heap belum penuh ({len(min_heap)}/{k}). Push {num} -> {min_heap}")
        else:
            if num > min_heap[0]:
                evicted = heapq.heappop(min_heap)
                heapq.heappush(min_heap, num)
                print(f"  {Color.GREEN}{num} > root ({evicted}){Color.RESET} -> Gantikan root terkecil. Heap: {min_heap}")
            else:
                print(f"  {Color.DIM}{num} <= root ({min_heap[0]}) -> Abaikan {num}. Heap tetap: {min_heap}{Color.RESET}")

    print(f"\n{Color.BOLD}{Color.GREEN}Hasil Akhir Top-{k} Elemen:{Color.RESET} {sorted(min_heap, reverse=True)}")
    print(f"{Color.BOLD}Elemen ke-{k} terbesar adalah:{Color.RESET} {Color.YELLOW}{min_heap[0]}{Color.RESET}")


# --- MODUL 3: Interval Merging Engine ---
def simulate_merge_intervals(intervals: List[List[int]]) -> List[List[int]]:
    print_banner("Simulasi Interval Merging (Sweep-line / Sorting)")
    print(f"Interval Mentah : {Color.BOLD}{intervals}{Color.RESET}")

    # 1. Sorting berdasarkan start time
    sorted_intervals = sorted(intervals, key=lambda x: x[0])
    print(f"Sorted Interval : {Color.CYAN}{sorted_intervals}{Color.RESET}\n")

    merged: List[List[int]] = []

    for current in sorted_intervals:
        if not merged:
            merged.append(current)
            print(f"  Initial buffer -> masukkan {Color.GREEN}{current}{Color.RESET}")
            continue

        prev = merged[-1]
        print(f"  Memeriksa pasangan: Prev {Color.YELLOW}{prev}{Color.RESET} vs Curr {Color.CYAN}{current}{Color.RESET}")

        # Cek kondisi overlap: curr.start <= prev.end
        if current[0] <= prev[1]:
            old_end = prev[1]
            prev[1] = max(prev[1], current[1])
            print(f"    {Color.RED}⚠ Overlap Terdeteksi!{Color.RESET} {current[0]} <= {old_end}")
            print(f"    -> Leburkan interval menjadi: {Color.BOLD}{Color.MAGENTA}{prev}{Color.RESET}")
        else:
            print(f"    {Color.BLUE}✓ Bebas Overlap.{Color.RESET} Tambahkan interval baru {current}")
            merged.append(current)

    print(f"\n{Color.BOLD}{Color.GREEN}Hasil Penggabungan Interval (Merged):{Color.RESET} {merged}")
    return merged


# --- MODUL 4: Meeting Rooms II (Minimum Ruangan via Min-Heap) ---
def simulate_min_meeting_rooms(intervals: List[List[int]]) -> int:
    print_banner("Simulasi Meeting Rooms II (Alokasi Resource via Min-Heap)")
    print(f"Daftar Jadwal Rapat: {intervals}")

    if not intervals:
        return 0

    sorted_meetings = sorted(intervals, key=lambda x: x[0])
    end_times_heap: List[int] = []

    print(f"Jadwal diurutkan berdasarkan waktu mulai:")
    for m in sorted_meetings:
        print(f"  Rapat: {m[0]:02d}:00 - {m[1]:02d}:00")

    print("\nProses Alokasi Ruangan:")
    for idx, meeting in enumerate(sorted_meetings, 1):
        start, end = meeting
        print(f"\n{Color.BOLD}[Rapat #{idx}]{Color.RESET} Jam {start:02d}:00 - {end:02d}:00")

        if end_times_heap and end_times_heap[0] <= start:
            freed_room_end = heapq.heappop(end_times_heap)
            print(f"  {Color.GREEN}✓ Ruangan bebas!{Color.RESET} Rapat sebelumnya selesai jam {freed_room_end:02d}:00.")
            print(f"    Gunakan kembali ruangan tersebut sampai jam {end:02d}:00.")
        else:
            print(f"  {Color.RED}+ Semua ruangan terpakai!{Color.RESET} Butuh penambahan ruangan baru.")

        heapq.heappush(end_times_heap, end)
        print(f"  Status waktu selesai ruangan aktif: {Color.CYAN}{end_times_heap}{Color.RESET}")
        print(f"  Jumlah ruangan terpakai saat ini: {Color.YELLOW}{len(end_times_heap)}{Color.RESET}")

    total_rooms = len(end_times_heap)
    print(f"\n{Color.BOLD}{Color.GREEN}Total Ruangan Minimum yang Dibutuhkan:{Color.RESET} {Color.MAGENTA}{total_rooms} Ruangan{Color.RESET}")
    return total_rooms


# --- CLI Interactive Controller ---
def interactive_menu():
    while True:
        print_banner("LEETCODE BAB-08: Priority Queues, Heaps & Intervals")
        print(f"{Color.BOLD}PILIH MENU SIMULASI:{Color.RESET}")
        print(f"  {Color.CYAN}[1]{Color.RESET} Visualizer Min-Heap Dasar (Push/Pop Step-by-Step)")
        print(f"  {Color.CYAN}[2]{Color.RESET} Top-K Elemen Terbesar (Stream Processing)")
        print(f"  {Color.CYAN}[3]{Color.RESET} Interval Merging Engine (LeetCode #56)")
        print(f"  {Color.CYAN}[4]{Color.RESET} Meeting Rooms II Allocation (LeetCode #253)")
        print(f"  {Color.CYAN}[5]{Color.RESET} Jalankan Seluruh Test Suite Otomatis")
        print(f"  {Color.RED}[0] Keluar{Color.RESET}")

        try:
            choice = input(f"\n{Color.BOLD}Masukkan pilihan (0-5): {Color.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nSampai jumpa!")
            break

        if choice == "1":
            print_banner("Interactive Min-Heap Demo")
            heap_sim = VisualMinHeap()
            sample_data = [15, 10, 20, 8, 12, 25, 6]
            print(f"Memasukkan elemen sample: {sample_data}")
            for v in sample_data:
                heap_sim.push(v)
            print("\nMelakukan 3x operasi Pop (Root Extraction):")
            for _ in range(3):
                heap_sim.pop()

        elif choice == "2":
            stream = [3, 10, 4, 1, 20, 15, 8, 30, 2, 50]
            k = 3
            simulate_top_k_stream(stream, k)

        elif choice == "3":
            raw_intervals = [[1, 3], [2, 6], [8, 10], [15, 18], [9, 12]]
            simulate_merge_intervals(raw_intervals)

        elif choice == "4":
            meetings = [[0, 30], [5, 10], [15, 20], [9, 17], [18, 25]]
            simulate_min_meeting_rooms(meetings)

        elif choice == "5":
            print_banner("Menjalankan Otomatisasi Seluruh Modul")
            # 1. Min-Heap
            h = VisualMinHeap()
            for v in [9, 4, 7, 1, 3]:
                h.push(v)
            h.pop()
            # 2. Top-K
            simulate_top_k_stream([7, 10, 4, 3, 20, 15], 3)
            # 3. Intervals
            simulate_merge_intervals([[1, 4], [4, 5], [6, 8], [7, 9]])
            # 4. Meeting rooms
            simulate_min_meeting_rooms([[1, 5], [8, 9], [2, 6], [10, 12]])
            print(f"\n{Color.GREEN}✓ Seluruh modul berhasil diuji!{Color.RESET}")

        elif choice == "0":
            print(f"\n{Color.GREEN}Selesai. Terima kasih telah menggunakan simulator!{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid. Silakan pilih 0-5.{Color.RESET}")


if __name__ == "__main__":
    # Jika dijalankan tanpa terminal interaktif, jalankan automated suite
    if not sys.stdin.isatty():
        print(f"{Color.YELLOW}Mode Non-Interaktif Terdeteksi: Menjalankan Suite Penuh...{Color.RESET}")
        h = VisualMinHeap()
        for v in [14, 8, 22, 5, 11]:
            h.push(v)
        h.pop()
        simulate_top_k_stream([12, 3, 5, 7, 19, 26, 1], 3)
        simulate_merge_intervals([[1, 3], [2, 6], [8, 10], [15, 18]])
        simulate_min_meeting_rooms([[0, 30], [5, 10], [15, 20]])
    else:
        interactive_menu()
