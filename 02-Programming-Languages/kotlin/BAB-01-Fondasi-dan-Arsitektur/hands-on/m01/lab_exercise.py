#!/usr/bin/env python3
"""
Lab Exercise: Kotlin Core Foundations & Architecture Simulator (BAB-01)
Interaktif demonstrasi arsitektur Kotlin, Type System, Null Safety, dan Kompilasi JVM.
"""

import sys
import time

# ANSI Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
BLUE = "\033[34m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"


def print_banner():
    print(f"{CYAN}{BOLD}" + "=" * 65)
    print("   KOTLIN ARCHITECTURE & FOUNDATIONS SIMULATOR (BAB 01)")
    print("   Interaktif: Type System, Null Safety & JVM Target")
    print("=" * 65 + f"{RESET}\n")


def demo_architecture_pipeline():
    print(f"{BOLD}{MAGENTA}[1] Kotlin Compilation & Architecture Pipeline{RESET}")
    print("Memahami bagaimana kode Kotlin (.kt) dikompilasi ke bytecode JVM:\n")

    steps = [
        ("Source Code (.kt)", "User menulis kode dengan sintaks ekspresif & Null Safety."),
        ("kotlinc (Frontend - PSI/FIR)", "Lexer, Parser, Resolution, Type Checking, Smart Casting."),
        ("IR (Intermediate Representation)", "Representasi pohon sintaks universal Kotlin 1.5+ (Kotlin IR)."),
        ("Backend Target (JVM / JS / Native)", "Lowering IR menjadi Java Bytecode (.class) dengan JVM Target 8/17/21."),
        ("Runtime & JVM Execution", "Eksekusi bytecode di JVM bersama kotlin-stdlib (~1.8 MB runtime overhead).")
    ]

    for idx, (stage, desc) in enumerate(steps, start=1):
        print(f"  {BLUE}{BOLD}[Langkah {idx}]{RESET} {YELLOW}{stage}{RESET}")
        print(f"       -> {desc}")
        time.sleep(0.1)

    print(f"\n{GREEN}✔ Kotlin 100% interoperable dengan Java melalui standard JVM Bytecode!{RESET}\n")


def demo_val_vs_var():
    print(f"{BOLD}{MAGENTA}[2] Immutability: Val vs Var Simulation{RESET}")
    print("Simulasi alokasi memori dan 'read-only' constraint pada Kotlin:\n")

    val_name = "Kotlin 2.0"
    print(f"  Deklarasi: {CYAN}val framework: String = \"{val_name}\"{RESET}")
    print(f"  Status: {GREEN}Immutable Reference (Final field pada Java Bytecode){RESET}")

    try:
        print(f"  Mencoba reassign: {YELLOW}framework = \"Java 21\"{RESET}")
        raise TypeError("Val cannot be reassigned (Kotlin Compiler Error: Val cannot be reassigned)")
    except TypeError as e:
        print(f"  {RED}✖ Compiler Error:{RESET} {e}")

    var_counter = 10
    print(f"\n  Deklarasi: {CYAN}var counter: Int = {var_counter}{RESET}")
    print(f"  Status: {GREEN}Mutable Variable (Non-final field){RESET}")
    var_counter += 5
    print(f"  Reassign counter: {YELLOW}counter += 5{RESET} -> {GREEN}Nilai baru: {var_counter}{RESET}\n")


def demo_null_safety():
    print(f"{BOLD}{MAGENTA}[3] Type System & Null Safety Simulation{RESET}")
    print("Mencegah The Billion Dollar Mistake (NullPointerException) saat compile time:\n")

    # Non-nullable vs Nullable
    print(f"  1. Non-nullable Type: {CYAN}var title: String = \"Architect\"{RESET}")
    print(f"     Assign null ke title -> {RED}Compilation Error: Null can not be a value of a non-null type String{RESET}\n")

    print(f"  2. Nullable Type: {CYAN}var subtitle: String? = null{RESET}")
    print(f"     Direct access: subtitle.length -> {RED}Error: Only safe (?.) or non-null asserted (!!.) calls are allowed{RESET}\n")

    # Safe call and Elvis operator
    sample_values = ["Kotlin Multiplatform", None]
    for val in sample_values:
        print(f"  --- Menguji input: {YELLOW}{repr(val)}{RESET} ---")
        # Safe call (?.)
        length = len(val) if val is not None else None
        print(f"    Safe Call (val?.length)            : {CYAN}{length}{RESET}")

        # Elvis Operator (?:)
        fallback = length if length is not None else 0
        print(f"    Elvis Operator (val?.length ?: 0)  : {GREEN}{fallback}{RESET}")

        # Smart Cast check
        if val is not None:
            print(f"    Smart Cast (if val != null)        : {GREEN}Type dipromosikan otomatis ke Non-null String{RESET}")
        else:
            print(f"    Smart Cast (if val == null)        : {YELLOW}Cabang null terdeteksi secara aman{RESET}")
        print()


def interactive_quiz():
    print(f"{BOLD}{MAGENTA}[4] Uji Pemahaman Fondasi Kotlin{RESET}")
    questions = [
        {
            "q": "Apa komponen backend compiler Kotlin yang menghasilkan file .class?",
            "opts": ["A. Kotlin/Native LLVM", "B. Kotlin/JVM Backend", "C. Kotlin/Wasm Engine", "D. D8 Dexer"],
            "ans": "B"
        },
        {
            "q": "Operator apa yang digunakan untuk Elvis Operator di Kotlin?",
            "opts": ["A. ??", "B. ||", "C. ?:", "D. ?."],
            "ans": "C"
        },
        {
            "q": "Apa sifat default dari properti bertipe 'val' di Kotlin?",
            "opts": ["A. Mutable", "B. Read-only / Immutable reference", "C. Thread-unsafe", "D. Dynamic"],
            "ans": "B"
        }
    ]

    score = 0
    for idx, item in enumerate(questions, start=1):
        print(f"{BOLD}{YELLOW}Pertanyaan {idx}:{RESET} {item['q']}")
        for opt in item["opts"]:
            print(f"   {opt}")
        choice = input(f"{CYAN}Pilih jawaban (A/B/C/D) atau tekan Enter untuk skip: {RESET}").strip().upper()
        if choice == item["ans"]:
            print(f"{GREEN}✔ Benar!{RESET}\n")
            score += 1
        elif choice == "":
            print(f"{YELLOW}Dilewati. Kunci jawaban: {item['ans']}{RESET}\n")
        else:
            print(f"{RED}✖ Salah. Kunci jawaban: {item['ans']}{RESET}\n")

    print(f"{BOLD}{CYAN}Skor Kuis Anda: {score}/{len(questions)}{RESET}\n")


def main():
    print_banner()
    while True:
        print(f"{BOLD}Pilih Modul Simulasi:{RESET}")
        print("  1. Arsitektur Kompilasi Kotlin (Source -> IR -> JVM Bytecode)")
        print("  2. Immutability: 'val' vs 'var' & Memory Mechanics")
        print("  3. Kotlin Null Safety, Safe Call & Elvis Operator")
        print("  4. Interactive Knowledge Quiz")
        print("  5. Jalankan Semua Simulasi")
        print("  0. Keluar")

        choice = input(f"\n{CYAN}Masukkan pilihan [0-5]: {RESET}").strip()
        print("-" * 65)

        if choice == "1":
            demo_architecture_pipeline()
        elif choice == "2":
            demo_val_vs_var()
        elif choice == "3":
            demo_null_safety()
        elif choice == "4":
            interactive_quiz()
        elif choice == "5":
            demo_architecture_pipeline()
            demo_val_vs_var()
            demo_null_safety()
            interactive_quiz()
        elif choice == "0":
            print(f"{GREEN}Terima kasih telah mempelajari Fondasi & Arsitektur Kotlin!{RESET}")
            sys.exit(0)
        else:
            print(f"{RED}Pilihan tidak valid, silakan coba lagi.{RESET}\n")


if __name__ == "__main__":
    main()
