#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Interaktif Fondasi & Arsitektur C++
BAB-01: Fondasi dan Arsitektur (C++ Engine Simulation)

Topik yang disimulasikan:
1. Tahapan Kompilasi C++ (Preprocessor -> Compiler -> Assembler -> Linker)
2. Memory Layout Process Space (Text, Data, BSS, Heap, Stack)
3. Semantik Pointer & Reference serta Resolusi Alamat
4. Mekanisme RAII (Resource Acquisition Is Initialization) & Destruksi Terbalik
"""

import sys
import time
from typing import Dict, List, Any, Optional

# Kode ANSI untuk pewarnaan terminal
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    
    # Warna Foreground
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    
    # Warna Background
    BG_BLUE = "\033[44m"
    BG_DARK = "\033[40m"


def print_banner(title: str) -> None:
    line = "=" * 64
    print(f"\n{Style.CYAN}{line}{Style.RESET}")
    print(f"{Style.BOLD}{Style.YELLOW}  {title.upper()}{Style.RESET}")
    print(f"{Style.CYAN}{line}{Style.RESET}\n")


def simulate_compilation_pipeline() -> None:
    """Simulasi 4 fase kompilasi C++ modern."""
    print_banner("1. Simulasi Pipeline Kompilasi C++ (Source -> Binary)")
    
    stages = [
        (
            "Pre-processor (cpp)",
            "Memproses direktif '#include', '#define', '#ifdef'. Menghilangkan komentar.",
            "main.cpp -> main.i (Expanded Source Code)",
            Style.BLUE
        ),
        (
            "Compiler Frontend & Backend (g++/clang++)",
            "Parsing sintaks, AST, optimasi SSA (Single Static Assignment), translasi ke Assembly.",
            "main.i -> main.s (Assembly code - x86_64 / ARM)",
            Style.MAGENTA
        ),
        (
            "Assembler (as)",
            "Menerjemahkan instruksi bahasa rakitan menjadi machine code (Relocatable Object File).",
            "main.s -> main.o / main.obj (ELF / Mach-O binary format)",
            Style.YELLOW
        ),
        (
            "Linker (ld / lld)",
            "Menyelesaikan symbol external (libstdc++, glibc, static libs), resolusi alamat referensi.",
            "main.o + libc.a -> app (Executable Binary)",
            Style.GREEN
        )
    ]
    
    for idx, (name, desc, artifact, color) in enumerate(stages, 1):
        print(f"{color}[Tahap {idx}/4] {Style.BOLD}{name}{Style.RESET}")
        print(f"  {Style.DIM}Fungsi:{Style.RESET}   {desc}")
        print(f"  {Style.GREEN}Output:{Style.RESET}   {artifact}")
        time.sleep(0.3)
        print()


def simulate_memory_layout() -> None:
    """Simulasi struktur memori virtual proses C++."""
    print_banner("2. Arsitektur Memori Virtual Proses C++ (Memory Map)")
    
    segments = [
        ("0xFFFFFFFFFFFF", "Kernel Space", "Akses istimewa (Ring 0), proteksi OS", Style.RED),
        ("0x7FFFFFFE0000", "Stack (Grows Downwards)", "Alokasi otomatis (lokal variabel, frame pointer, RAII)", Style.CYAN),
        ("      |       ", "      ↓        ", "Batas pemisah dinamis (Guard Page)", Style.DIM),
        ("      ↑       ", "      ↑        ", "Ruang ekspansi bebas antara heap dan stack", Style.DIM),
        ("0x000055556000", "Heap (Grows Upwards)", "Alokasi dinamis (malloc/free, new/delete, smart pointers)", Style.GREEN),
        ("0x000055555000", "BSS Segment", "Variabel global & static yang belum diinisialisasi (zero-init)", Style.YELLOW),
        ("0x000055554000", "Data Segment", "Variabel global & static yang sudah diinisialisasi nilai awal", Style.MAGENTA),
        ("0x000055550000", "Text / Code Segment", "Instruksi binary machine code (Read-Only & Executable)", Style.BLUE),
    ]
    
    print(f"{Style.BOLD}{'Alamat Virtual':<18} | {'Segmen Memori':<26} | {'Karakteristik'}{Style.RESET}")
    print("-" * 75)
    for addr, seg, desc, color in segments:
        print(f"{Style.DIM}{addr:<18}{Style.RESET} | {color}{seg:<26}{Style.RESET} | {desc}")
        time.sleep(0.15)
    print()


def simulate_pointers_and_references() -> None:
    """Simulasi teknis perbedaan Pointer dan Reference dalam C++."""
    print_banner("3. Semantik Pointer vs Reference pada Level Hardware")
    
    val = 42
    addr_val = "0x7ffd98b0"
    ptr_addr = "0x7ffd98b8"
    
    print(f"{Style.BOLD}Deklarasi Variabel Asli:{Style.RESET}")
    print(f"  int x = 42;                 -> [Alamat: {addr_val}] [Nilai: {val}]")
    print()
    
    print(f"{Style.BOLD}A. Pointer Semantics (int* ptr = &x):{Style.RESET}")
    print(f"  - Pointer adalah entitas variabel mandiri di memori.")
    print(f"  - Memiliki alamat sendiri: {Style.YELLOW}{ptr_addr}{Style.RESET}")
    print(f"  - Menyimpan nilai berupa alamat memori target: {Style.GREEN}{addr_val}{Style.RESET}")
    print(f"  - Dereferensi (*ptr): Membaca isi alamat {addr_val} -> {Style.CYAN}{val}{Style.RESET}")
    print(f"  - Dapat direassign (re-pointed) atau bernilai {Style.RED}nullptr{Style.RESET}.")
    print()
    
    print(f"{Style.BOLD}B. Reference Semantics (int& ref = x):{Style.RESET}")
    print(f"  - Reference adalah alias sintaksis (compile-time alias) untuk 'x'.")
    print(f"  - Berbagi alamat identik dengan x: {Style.GREEN}{addr_val}{Style.RESET}")
    print(f"  - Tidak memiliki alamat mandiri dalam model konseptual C++.")
    print(f"  - Wajib diinisialisasi saat deklarasi & {Style.RED}TIDAK DAPAT{Style.RESET} dipindahkan (immutable binding).")
    print()


class ScopedResource:
    """Helper untuk mensimulasikan siklus hidup RAII object."""
    def __init__(self, name: str, resource_type: str):
        self.name = name
        self.resource_type = resource_type
        print(f"  {Style.GREEN}[+] Constructor: '{self.name}' dialokasikan ({self.resource_type}){Style.RESET}")
        
    def release(self) -> None:
        print(f"  {Style.RED}[-] Destructor : '{self.name}' dibebaskan secara deterministik{Style.RESET}")


def simulate_raii_lifecycle() -> None:
    """Simulasi mekanisme RAII & Unwinding Scope."""
    print_banner("4. Simulasi RAII & Deterministic Destruction Order")
    print("Memasuki Scope Blok { ... } :\n")
    
    stack: List[ScopedResource] = []
    
    # Alokasi bertahap pada scope stack
    stack.append(ScopedResource("DatabaseConnectionPool", "TCP Socket FD 12"))
    time.sleep(0.2)
    stack.append(ScopedResource("FileHandle", "File Descriptor: log.txt"))
    time.sleep(0.2)
    stack.append(ScopedResource("MutexLockGuard", "Kernel Mutex 0xDEADBEEF"))
    time.sleep(0.2)
    
    print(f"\n{Style.YELLOW}Operasi bisnis selesai atau terjadi error/return dari scope...{Style.RESET}")
    print("Meninggalkan Scope } (LIFO Order / Stack Unwinding):\n")
    
    # Destruksi dengan prinsip LIFO (Last-In-First-Out)
    while stack:
        item = stack.pop()
        item.release()
        time.sleep(0.2)
    print()


def show_menu() -> None:
    """Menampilkan menu interaktif."""
    print(f"{Style.BOLD}PILIHAN MODUL LAB (BAB 01 - C++):{Style.RESET}")
    print("  [1] Simulasi Pipeline Kompilasi C++")
    print("  [2] Simulasi Arsitektur Memori Virtual")
    print("  [3] Simulasi Pointer vs Reference")
    print("  [4] Simulasi Siklus Hidup RAII")
    print("  [5] Jalankan Seluruh Simulasi (Full Suite)")
    print("  [0] Keluar")
    print()


def run_interactive() -> None:
    """Loop eksekusi utama."""
    print(f"{Style.BG_BLUE}{Style.WHITE}{Style.BOLD} --- LAB PRAKTIKUM INTERAKTIF: FONDASI C++ & ARSITEKTUR --- {Style.RESET}")
    
    # Jika dijalankan non-interaktif (pipe/CI), jalankan full suite lalu exit
    if not sys.stdin.isatty():
        print(f"{Style.DIM}Mode Non-Interactive terdeteksi. Menjalankan full suite...{Style.RESET}\n")
        simulate_compilation_pipeline()
        simulate_memory_layout()
        simulate_pointers_and_references()
        simulate_raii_lifecycle()
        print(f"{Style.GREEN}{Style.BOLD}✓ Seluruh modul lab sukses dijalankan.{Style.RESET}")
        return

    while True:
        show_menu()
        try:
            choice = input(f"{Style.BOLD}Pilih nomor modul [0-5]: {Style.RESET}").strip()
            if choice == "1":
                simulate_compilation_pipeline()
            elif choice == "2":
                simulate_memory_layout()
            elif choice == "3":
                simulate_pointers_and_references()
            elif choice == "4":
                simulate_raii_lifecycle()
            elif choice == "5":
                simulate_compilation_pipeline()
                simulate_memory_layout()
                simulate_pointers_and_references()
                simulate_raii_lifecycle()
            elif choice == "0":
                print(f"\n{Style.CYAN}Lab selesai. Selamat belajar C++!{Style.RESET}\n")
                break
            else:
                print(f"{Style.RED}Pilihan tidak valid. Silakan masukkan angka 0-5.{Style.RESET}\n")
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Style.YELLOW}Sesi lab dihentikan oleh pengguna.{Style.RESET}")
            break


if __name__ == "__main__":
    run_interactive()
