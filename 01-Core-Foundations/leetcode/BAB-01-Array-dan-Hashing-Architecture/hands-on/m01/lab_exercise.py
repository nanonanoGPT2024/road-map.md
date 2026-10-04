#!/usr/bin/env python3
"""
BAB-01: Array & Hashing Architecture - Interactive Lab Exercise
Topik: Dynamic Array Growth, Custom Hash Table with Collision Handling,
       dan Visualisasi Pola LeetCode (Two Sum & Group Anagrams).

Dijalankan secara mandiri dengan Python 3 (Standard Library Only).
"""

import sys
import time
from typing import Any, List, Optional, Tuple

# ANSI Terminal Colors
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"
BG_BLUE = "\033[44m"
BG_GREEN = "\033[42m"


def header(title: str) -> None:
    line = "=" * 68
    print(f"\n{CYAN}{BOLD}{line}{RESET}")
    print(f"{CYAN}{BOLD}  >>> {title.upper()} <<<{RESET}")
    print(f"{CYAN}{BOLD}{line}{RESET}\n")


def subheader(title: str) -> None:
    print(f"\n{YELLOW}{BOLD}--- [ {title} ] ---{RESET}")


class DynamicArraySimulator:
    """Simulasi alokasi memori fisik dan resizing geometris array dinamis."""

    def __init__(self, initial_capacity: int = 2):
        self.capacity = initial_capacity
        self.size = 0
        self.buffer: List[Optional[Any]] = [None] * initial_capacity
        self.resize_events: List[Tuple[int, int, int]] = []

    def append(self, value: Any) -> None:
        if self.size == self.capacity:
            old_cap = self.capacity
            new_cap = self.capacity * 2
            print(f"  {RED}[RESIZE EVENT]{RESET} Buffer penuh ({self.size}/{old_cap}). "
                  f"Alokasi memori baru: {BOLD}{new_cap} slots{RESET} & migrasi elemen.")
            new_buffer: List[Optional[Any]] = [None] * new_cap
            for i in range(self.size):
                new_buffer[i] = self.buffer[i]
            self.buffer = new_buffer
            self.capacity = new_cap
            self.resize_events.append((self.size, old_cap, new_cap))

        self.buffer[self.size] = value
        self.size += 1

    def display(self) -> None:
        slots = []
        for i in range(self.capacity):
            if i < self.size:
                slots.append(f"{GREEN}[{self.buffer[i]}]{RESET}")
            else:
                slots.append(f"{DIM}[_]{RESET}")
        ratio = (self.size / self.capacity) * 100
        print(f"  Memory Layout : {' '.join(slots)}")
        print(f"  Length: {BOLD}{self.size}{RESET} | Capacity: {BOLD}{self.capacity}{RESET} | Load: {CYAN}{ratio:.1f}%{RESET}")


class SimpleHashTable:
    """Implementasi Hash Table mandiri dengan Chaining & rehash saat load > 0.7."""

    def __init__(self, initial_buckets: int = 5):
        self.num_buckets = initial_buckets
        self.buckets: List[List[Tuple[str, Any]]] = [[] for _ in range(initial_buckets)]
        self.total_keys = 0

    def _hash(self, key: str) -> int:
        h = 0
        for char in key:
            h = (h * 31 + ord(char)) % self.num_buckets
        return h

    def set(self, key: str, value: Any) -> None:
        load_factor = (self.total_keys + 1) / self.num_buckets
        if load_factor > 0.7:
            print(f"  {MAGENTA}[REHASH TRIGGERED]{RESET} Load factor: {load_factor:.2f} > 0.7. Doubling buckets.")
            self._rehash()

        idx = self._hash(key)
        for i, (k, _) in enumerate(self.buckets[idx]):
            if k == key:
                self.buckets[idx][i] = (key, value)
                return

        self.buckets[idx].append((key, value))
        self.total_keys += 1

    def get(self, key: str) -> Optional[Any]:
        idx = self._hash(key)
        for k, v in self.buckets[idx]:
            if k == key:
                return v
        return None

    def _rehash(self) -> None:
        old_buckets = self.buckets
        self.num_buckets *= 2
        self.buckets = [[] for _ in range(self.num_buckets)]
        self.total_keys = 0
        for chain in old_buckets:
            for k, v in chain:
                self.set(k, v)

    def display(self) -> None:
        print(f"  {BOLD}Bucket Slots (Total Keys: {self.total_keys}, Capacity: {self.num_buckets}){RESET}")
        for i, chain in enumerate(self.buckets):
            if chain:
                items = " -> ".join([f"{CYAN}{k}{RESET}:{GREEN}{v}{RESET}" for k, v in chain])
                print(f"    Bucket [{i:2d}]: {items}")
            else:
                print(f"    Bucket [{i:2d}]: {DIM}(empty){RESET}")


def demo_dynamic_array() -> None:
    subheader("Modul 1: Dynamic Array Memory Allocation & Growth Simulator")
    print(f"{DIM}Mengamati bagaimana amortized O(1) bekerja saat append memicu doubling reallocation.{RESET}\n")

    arr = DynamicArraySimulator(initial_capacity=2)
    sample_data = [10, 20, 30, 40, 50, 60, 70]

    for item in sample_data:
        print(f"{BOLD}-> Append({item}){RESET}")
        arr.append(item)
        arr.display()
        print()


def demo_hash_table() -> None:
    subheader("Modul 2: Custom Hash Table Architecture & Chaining Visualizer")
    print(f"{DIM}Simulasi polynomial rolling hash, collision resolution via chaining, dan auto-rehashing.{RESET}\n")

    ht = SimpleHashTable(initial_buckets=4)
    pairs = [("apple", 15), ("banana", 24), ("cherry", 42), ("date", 99), ("elderberry", 7), ("fig", 88)]

    for k, v in pairs:
        print(f"{BOLD}-> Insert key='{k}', val={v}{RESET}")
        ht.set(k, v)
        ht.display()
        print()

    print(f"{BOLD}Pencarian Elemen:{RESET}")
    for target in ["banana", "grape"]:
        res = ht.get(target)
        if res is not None:
            print(f"  Lookup '{target}': {GREEN}FOUND -> {res}{RESET}")
        else:
            print(f"  Lookup '{target}': {RED}NOT FOUND{RESET}")


def demo_two_sum_visualizer() -> None:
    subheader("Modul 3: LeetCode Pattern - Two Sum (Hash Map O(N) Step Tracer)")
    nums = [2, 11, 7, 15]
    target = 9
    print(f"  Input Array  : {nums}")
    print(f"  Target Sum   : {BOLD}{target}{RESET}\n")

    lookup = {}
    found = False

    for idx, num in enumerate(nums):
        complement = target - num
        print(f"  Langkah {idx+1}: Memeriksa index={idx}, num={BOLD}{num}{RESET}")
        print(f"    Dibutuhkan complement = {target} - {num} = {CYAN}{complement}{RESET}")

        if complement in lookup:
            prev_idx = lookup[complement]
            print(f"    {GREEN}{BOLD}KORESPONDENSI DITEMUKAN!{RESET}")
            print(f"    Nilai {complement} ada di hash map pada index {prev_idx}.")
            print(f"    Output Result: {BG_GREEN}{BOLD} [{prev_idx}, {idx}] {RESET} (Values: {nums[prev_idx]} + {nums[idx]} = {target})")
            found = True
            break
        else:
            print(f"    {complement} belum ada di hash map.")
            lookup[num] = idx
            print(f"    Simpan state: map[{num}] = {idx}")
            print(f"    State Map saat ini: {YELLOW}{lookup}{RESET}\n")

    if not found:
        print(f"  {RED}Tidak ada pasangan angka yang menghasilkan target {target}.{RESET}")


def demo_group_anagrams() -> None:
    subheader("Modul 4: LeetCode Pattern - Group Anagrams (Character Frequency Key)")
    words = ["eat", "tea", "tan", "ate", "nat", "bat"]
    print(f"  Input Words: {words}\n")

    groups = {}
    for word in words:
        count = [0] * 26
        for ch in word:
            count[ord(ch) - ord('a')] += 1
        key = tuple(count)

        if key not in groups:
            groups[key] = []
        groups[key].append(word)

        non_zero = [(chr(i + ord('a')), count[i]) for i in range(26) if count[i] > 0]
        sig_str = ", ".join([f"'{c}':{cnt}" for c, cnt in non_zero])
        print(f"  Word: {CYAN}{word:<4}{RESET} -> Fingerprint Key: {{{sig_str}}}")

    print(f"\n{BOLD}Hasil Pengelompokan (Grouped Anagrams):{RESET}")
    for i, cluster in enumerate(groups.values(), 1):
        print(f"  Kelompok {i}: {GREEN}{cluster}{RESET}")


def interactive_menu() -> None:
    while True:
        header("LeetCode Bab 01: Array & Hashing Architecture Lab")
        print("Pilih simulasi yang ingin dijalankan:")
        print(f"  {BOLD}1{RESET}. Dynamic Array Allocation & Resizing Simulator")
        print(f"  {BOLD}2{RESET}. Custom Hash Table with Collision Chaining & Rehashing")
        print(f"  {BOLD}3{RESET}. Two Sum Hash Map Step-by-Step Tracer")
        print(f"  {BOLD}4{RESET}. Group Anagrams Character Count Fingerprint Simulator")
        print(f"  {BOLD}5{RESET}. Jalankan Semua Modul (Full Automation)")
        print(f"  {BOLD}0{RESET}. Keluar")
        print()

        try:
            choice = input(f"{YELLOW}Masukkan pilihan (0-5): {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nProgram dihentikan.")
            break

        if choice == "1":
            demo_dynamic_array()
        elif choice == "2":
            demo_hash_table()
        elif choice == "3":
            demo_two_sum_visualizer()
        elif choice == "4":
            demo_group_anagrams()
        elif choice == "5":
            demo_dynamic_array()
            demo_hash_table()
            demo_two_sum_visualizer()
            demo_group_anagrams()
        elif choice == "0":
            print(f"\n{GREEN}Lab exercise selesai. Selamat belajar!{RESET}\n")
            break
        else:
            print(f"{RED}Pilihan tidak valid. Silakan coba lagi.{RESET}")

        input(f"\n{DIM}[Tekan Enter untuk kembali ke menu]{RESET}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--all", "-a", "--run"):
        header("Automated Test Mode - Bab 01 Array & Hashing Architecture")
        demo_dynamic_array()
        demo_hash_table()
        demo_two_sum_visualizer()
        demo_group_anagrams()
    else:
        interactive_menu()
