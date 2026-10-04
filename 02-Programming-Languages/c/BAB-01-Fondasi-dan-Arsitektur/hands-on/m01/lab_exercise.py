#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Fondasi dan Arsitektur Bahasa C
BAB-01: Fondasi dan Arsitektur C

Modul simulasi interaktif mandiri untuk memvisualisasikan:
1. Tahapan Kompilasi C (Preprocessing, Compilation, Assembly, Linking)
2. Layout Memori Proses C (Text, Data, BSS, Heap, Stack)
3. Model Pointer dan Representasi Byte Memori (Endianness)
"""

import sys
import time
import struct

# ANSI Color Codes untuk output visual terminal
class Color:
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
    BG_DARK = "\033[100m"

def print_header(title: str):
    width = 65
    print(f"\n{Color.CYAN}{'=' * width}{Color.RESET}")
    print(f"{Color.BOLD}{Color.WHITE} {title.center(width - 2)} {Color.RESET}")
    print(f"{Color.CYAN}{'=' * width}{Color.RESET}\n")

def simulate_compilation_pipeline():
    """Simulasi 4 fase kompilasi C modern (GCC / Clang)."""
    print_header("Fase Kompilasi Program C (GCC / Clang Toolchain)")

    source_code = (
        "#include <stdio.h>\n"
        "#define PI 3.14159\n\n"
        "int main(void) {\n"
        "    double r = 7.0;\n"
        "    double luas = PI * r * r;\n"
        "    printf(\"Luas: %f\\n\", luas);\n"
        "    return 0;\n"
        "}"
    )

    print(f"{Color.YELLOW}[File Asal: main.c]{Color.RESET}")
    print(f"{Color.WHITE}{source_code}{Color.RESET}\n")

    stages = [
        (
            "1. Preprocessing (cpp main.c -> main.i)",
            Color.GREEN,
            "Ekspansi macro (#define PI -> 3.14159), resolusi header (<stdio.h>), penghapusan komentar.",
            "Output: File teks ASCII (.i) berukuran jauh lebih besar (~ ribuan baris kode prototipe)."
        ),
        (
            "2. Compilation (cc1 main.i -> main.s)",
            Color.CYAN,
            "Parsing sintaks, analisa semantik, AST (Abstract Syntax Tree), dan optimasi perakitan.",
            "Output: Kode Assembly human-readable spesifik arsitektur target (x86_64 / ARM64)."
        ),
        (
            "3. Assembly (as main.s -> main.o)",
            Color.MAGENTA,
            "Penerjemahan instruksi assembly menjadi binary machine code (opcode biner).",
            "Output: Relocatable Object File (ELF di Linux / Mach-O di macOS / PE di Windows)."
        ),
        (
            "4. Linking (ld main.o + libc.a/so -> a.out)",
            Color.BLUE,
            "Resolusi simbol eksternal (printf), pengaturan relocation address, integrasi runtime CRT.",
            "Output: Executable Binary siap dimuat OS Loader ke Virtual Memory."
        )
    ]

    for stage_name, color, desc, artifact in stages:
        print(f"{color}{Color.BOLD}>>> {stage_name}{Color.RESET}")
        print(f"    {Color.WHITE}Proses   :{Color.RESET} {desc}")
        print(f"    {Color.WHITE}Artefak  :{Color.RESET} {artifact}\n")
        time.sleep(0.3)

def simulate_memory_layout():
    """Simulasi struktur alamat memori virtual proses C (32/64-bit)."""
    print_header("Simulasi Layout Memori Virtual Proses C (Virtual Address Space)")

    print(f"{Color.YELLOW}Peta Memori Virtual (High Address -> Low Address):{Color.RESET}\n")

    layout = [
        ("0xFFFFFFFFFFFF", "Kernel Space", "Dipetakan untuk kernel OS, tidak dapat diakses user space secara langsung.", Color.RED),
        ("0x7FFFFFFF0000", "[STACK SEGMENT]", "Variabel lokal, stack frame fungsi (grows DOWNWARDS).", Color.GREEN),
        ("     | v |     ", "     v     ", "Arah pertumbuhan stack menuju alamat lebih rendah.", Color.GREEN),
        ("     | ^ |     ", "     ^     ", "Arah pertumbuhan heap menuju alamat lebih tinggi.", Color.MAGENTA),
        ("0x000002000000", "[HEAP SEGMENT]", "Alokasi memori dinamis (malloc/calloc/free).", Color.MAGENTA),
        ("0x000000602000", "[BSS SEGMENT]", "Variabel global/static yang TIDAK diinisialisasi (zero-initialized).", Color.CYAN),
        ("0x000000601000", "[DATA SEGMENT]", "Variabel global/static yang DIINISIALISASI nilai eksplisit.", Color.BLUE),
        ("0x000000400000", "[TEXT / CODE]", "Instruksi mesin biner yang read-only (mencegah modifikasi kode).", Color.WHITE),
        ("0x000000000000", "NULL Pointer", "Halaman dilindungi (trap segmentation fault jika di-dereference).", Color.RED),
    ]

    for addr, name, desc, color in layout:
        if "v" in name or "^" in name:
            print(f"                 {color}{name.center(22)}{Color.RESET}  {Color.WHITE}{desc}{Color.RESET}")
        else:
            print(f"{Color.BOLD}{addr}{Color.RESET}  {color}{name:<18}{Color.RESET} : {Color.WHITE}{desc}{Color.RESET}")

    print("\n" + "=" * 65)

def simulate_pointers_and_bytes():
    """Simulasi konsep pointer, byte-addressable memory, dan endianness."""
    print_header("Simulasi Pointer & Penyimpanan Byte di Memori (Endianness)")

    sample_val = 0x12345678
    packed_little = struct.pack("<I", sample_val)
    packed_big = struct.pack(">I", sample_val)

    print(f"Nilai Integer (32-bit uint32_t): {Color.BOLD}{hex(sample_val)}{Color.RESET} ({sample_val} desimal)")
    print(f"Ukuran tipe data di arsitektur C: {Color.GREEN}sizeof(uint32_t) = 4 bytes{Color.RESET}\n")

    base_addr = 0x7FFF0010
    print(f"{Color.CYAN}Alamat Basis Array Byte (&val): {hex(base_addr)}{Color.RESET}\n")

    print(f"{Color.BOLD}1. Representasi Little-Endian (x86_64, ARM default):{Color.RESET}")
    print(f"   Least Significant Byte (LSB) disimpan pada alamat memori terkecil.")
    print("   +-------------------+------------+------------+")
    print("   | Alamat Memori     | Byte (Hex) | Deskripsi  |")
    print("   +-------------------+------------+------------+")
    for i, b in enumerate(packed_little):
        curr_addr = hex(base_addr + i)
        note = "LSB (0x78)" if i == 0 else ("MSB (0x12)" if i == 3 else f"Byte {i}")
        print(f"   | {Color.YELLOW}{curr_addr:<17}{Color.RESET} | {Color.GREEN}0x{b:02X}{Color.RESET}       | {note:<10} |")
    print("   +-------------------+------------+------------+\n")

    print(f"{Color.BOLD}2. Representasi Big-Endian (Network Byte Order, SPARC):{Color.RESET}")
    print(f"   Most Significant Byte (MSB) disimpan pada alamat memori terkecil.")
    print("   +-------------------+------------+------------+")
    print("   | Alamat Memori     | Byte (Hex) | Deskripsi  |")
    print("   +-------------------+------------+------------+")
    for i, b in enumerate(packed_big):
        curr_addr = hex(base_addr + i)
        note = "MSB (0x12)" if i == 0 else ("LSB (0x78)" if i == 3 else f"Byte {i}")
        print(f"   | {Color.YELLOW}{curr_addr:<17}{Color.RESET} | {Color.MAGENTA}0x{b:02X}{Color.RESET}       | {note:<10} |")
    print("   +-------------------+------------+------------+\n")

    print(f"{Color.WHITE}Analogi Pointer C:{Color.RESET}")
    print(f"   uint32_t x = 0x12345678;")
    print(f"   uint8_t *ptr = (uint8_t *)&x;")
    print(f"   Dereference byte pertama (*ptr) pada Little-Endian menghasilkan: {Color.GREEN}0x{packed_little[0]:02X}{Color.RESET}")

def run_interactive_quiz():
    """Kuis interaktif singkat untuk menguji pemahaman arsitektur C."""
    print_header("Kuis Interaktif: Uji Pemahaman Arsitektur & Fondasi C")

    questions = [
        {
            "q": "Pada tahapan kompilasi apa directive #include dan #define diekspansi?",
            "options": ["A. Assembler", "B. Linker", "C. Preprocessor", "D. Compiler"],
            "ans": "C",
            "expl": "Preprocessor bertanggung jawab menangani semua directive berawalan tanda '#' sebelum masuk ke compiler."
        },
        {
            "q": "Di segmen memori manakah variabel lokal non-static dialokasikan saat runtime?",
            "options": ["A. Stack", "B. Heap", "C. BSS Segment", "D. Data Segment"],
            "ans": "A",
            "expl": "Stack menyimpan stack frame fungsi, variabel lokal, dan return address pemanggilan fungsi."
        },
        {
            "q": "Apa yang terjadi jika variabel bernilai 0xABCD disimpan pada sistem Little-Endian?",
            "options": [
                "A. Byte 0xAB disimpan di alamat memori terendah",
                "B. Byte 0xCD disimpan di alamat memori terendah",
                "C. Kedua byte disimpan terbalik dalam urutan bit",
                "D. Memori akan corrupt"
            ],
            "ans": "B",
            "expl": "Little-endian menyimpan LSB (Least Significant Byte, yaitu 0xCD) pada alamat memori terkecil."
        }
    ]

    score = 0
    for idx, item in enumerate(questions, 1):
        print(f"{Color.BOLD}Soal {idx}: {item['q']}{Color.RESET}")
        for opt in item["options"]:
            print(f"   {opt}")
        user_ans = input(f"\n{Color.YELLOW}Pilihan Anda (A/B/C/D) [default: {item['ans']}]: {Color.RESET}").strip().upper()
        if not user_ans:
            user_ans = item["ans"]

        if user_ans == item["ans"]:
            print(f"{Color.GREEN}✓ Benar!{Color.RESET} {item['expl']}\n")
            score += 1
        else:
            print(f"{Color.RED}✗ Salah.{Color.RESET} Jawaban yang benar adalah {item['ans']}. {item['expl']}\n")

    print(f"{Color.BOLD}Skor Akhir: {score}/{len(questions)}{Color.RESET}")

def main():
    """Fungsi utama lab exercise."""
    print(f"\n{Color.BG_BLUE}{Color.BOLD}{Color.WHITE} LAB EXERCISE: FONDASI DAN ARSITEKTUR BAHASA C {Color.RESET}\n")

    while True:
        print(f"{Color.CYAN}--- Menu Pilihan Simulasi ---{Color.RESET}")
        print("1. Jalankan Simulasi 4 Tahap Kompilasi C")
        print("2. Tampilkan Visualisasi Virtual Memory Layout")
        print("3. Jalankan Simulasi Pointer, Memori & Endianness")
        print("4. Jalankan Kuis Evaluasi Mandiri")
        print("5. Jalankan Seluruh Materi (Auto Tour)")
        print("0. Keluar")

        try:
            choice = input(f"\n{Color.YELLOW}Pilih menu (0-5) [default: 5]: {Color.RESET}").strip()
            if not choice:
                choice = "5"

            if choice == "1":
                simulate_compilation_pipeline()
            elif choice == "2":
                simulate_memory_layout()
            elif choice == "3":
                simulate_pointers_and_bytes()
            elif choice == "4":
                run_interactive_quiz()
            elif choice == "5":
                simulate_compilation_pipeline()
                simulate_memory_layout()
                simulate_pointers_and_bytes()
                run_interactive_quiz()
                print(f"\n{Color.GREEN}Seluruh demonstrasi modul fondasi C berhasil dijalankan!{Color.RESET}")
                break
            elif choice == "0":
                print(f"\n{Color.WHITE}Selesai. Terima kasih telah menjelajahi fondasi C.{Color.RESET}\n")
                break
            else:
                print(f"{Color.RED}Pilihan tidak valid, silakan ulangi.{Color.RESET}\n")
        except (KeyboardInterrupt, EOFError):
            print(f"\n\n{Color.WHITE}Eksekusi dibatalkan pengguna.{Color.RESET}\n")
            break

if __name__ == "__main__":
    main()
