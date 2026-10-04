#!/usr/bin/env python3
"""
Lab Exercise M01: Simulasi Fondasi dan Arsitektur Scala
BAB-01: Fondasi dan Arsitektur Scala (Scala 2 vs Scala 3 / Dotty, JVM Runtime, TASTy)

Skrip interaktif mandiri Python 3 untuk memvisualisasikan:
1. Unified Type System Scala (Any, AnyVal, AnyRef, Null, Nothing)
2. Pipeline Kompilasi Scala (Source -> AST -> TASTy -> JVM Bytecode)
3. Paradigma Expression-Oriented & Evaluasi Nilai (val vs var vs lazy val)
4. Case Class & Pattern Matching Engine
"""

import sys
import time
from dataclasses import dataclass
from typing import Any, List, Optional, Tuple

# ANSI Escape Sequences untuk Styling Terminal
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
RED = "\033[91m"
BG_BLUE = "\033[44m\033[97m"


def print_banner():
    print(f"{CYAN}{BOLD}" + "=" * 70 + f"{RESET}")
    print(f"{BG_BLUE}  LAB EXERCISE M01: SIMULATOR FONDASI & ARSITEKTUR SCALA (JVM/DOTTY)  {RESET}")
    print(f"{CYAN}" + "=" * 70 + f"{RESET}")
    print(f"{DIM}Memvisualisasikan prinsip inti komputasi dan type system bahasa Scala.{RESET}\n")


def simulate_type_hierarchy():
    print(f"\n{BOLD}{YELLOW}=== 1. SIMULASI SCALA UNIFIED TYPE HIERARCHY ==={RESET}")
    print("Scala menyatukan Primitive Type (Java) dan Object Reference dalam satu hierarki.")
    print(f"{CYAN}Root Class: {BOLD}scala.Any{RESET}")
    print("      ├── scala.AnyVal (Value Types: Int, Double, Boolean, Unit, Char)")
    print("      └── scala.AnyRef (Reference Types: String, List, User Classes / java.lang.Object)")
    print(f"Bottom Types: {MAGENTA}scala.Null{RESET} (subtipe AnyRef) dan {RED}scala.Nothing{RESET} (subtipe SEMUA tipe)\n")

    samples: List[Tuple[str, Any, str, str]] = [
        ("42", 42, "scala.Int", "AnyVal"),
        ("3.14159", 3.14159, "scala.Double", "AnyVal"),
        ("true", True, "scala.Boolean", "AnyVal"),
        ("() [Unit]", None, "scala.Unit", "AnyVal"),
        ('"Halo Scala"', "Halo Scala", "java.lang.String", "AnyRef"),
        ("List(1, 2, 3)", [1, 2, 3], "scala.collection.immutable.List", "AnyRef"),
    ]

    print(f"{BOLD}{'Ekspresi':<20} | {'Tipe Inferensi':<32} | {'Kategori Induk':<10}{RESET}")
    print("-" * 68)
    for expr, val, scala_type, parent in samples:
        time.sleep(0.08)
        color = GREEN if parent == "AnyVal" else BLUE
        print(f"{expr:<20} | {color}{scala_type:<32}{RESET} | {BOLD}{parent:<10}{RESET}")

    print(f"\n{DIM}Bottom Type Demonstration:{RESET}")
    print(f"- {MAGENTA}Null{RESET}: Merepresentasikan ketiadaan nilai referensi (val s: String = null).")
    print(f"- {RED}Nothing{RESET}: Sinyal terminasi abnormal atau ekspresi yang tidak pernah return (e.g., throw new Exception()).")


def simulate_compilation_pipeline():
    print(f"\n{BOLD}{YELLOW}=== 2. SIMULASI PIPELINE KOMPILASI SCALA 3 (DOTTY / TASTy) ==={RESET}")
    stages = [
        ("Source Code (.scala)", "Parsing kode teks berbasis ekspresi dan sintaks Scala 3"),
        ("Parser & AST Generation", "Membentuk Abstract Syntax Tree dan memeriksa struktur leksikal"),
        ("Typer & Semantic Analysis", "Resolusi tipe data, implicits/givens, macro expansion"),
        ("TASTy Serialization", "Menyimpan Typed Abstract Syntax Trees (.tasty) untuk cross-version compatibility"),
        ("Erasure & JVM Transformation", "Menghapus type parameters, unboxing value class ke JVM primitive jika memungkinkan"),
        ("JVM Bytecode (.class)", "Menghasilkan format instruksi JVM standar yang siap dieksekusi di runtime JVM"),
    ]

    for idx, (stage, desc) in enumerate(stages, 1):
        time.sleep(0.12)
        print(f" {CYAN}[Tahap {idx}/6]{RESET} {BOLD}{stage:<30}{RESET} -> {DIM}{desc}{RESET}")
    print(f"\n{GREEN}✔ Bytecode siap dieksekusi di HotSpot JVM atau diadopsi via forward/backward TASTy!{RESET}")


@dataclass(frozen=True)
class PersonCaseClass:
    name: str
    role: str
    experience_years: int


def simulate_pattern_matching():
    print(f"\n{BOLD}{YELLOW}=== 3. SIMULASI CASE CLASS & PATTERN MATCHING ENGINE ==={RESET}")
    print("Di Scala, Case Class mengaktifkan dekonstruksi struktural (unapply) dan immutability bawaan.")

    team = [
        PersonCaseClass("Budi", "Data Engineer", 5),
        PersonCaseClass("Siti", "Distributed Systems Architect", 8),
        PersonCaseClass("Andi", "Junior Scala Developer", 1),
        PersonCaseClass("Dewi", "Tech Lead", 10),
    ]

    print(f"\nMengevaluasi daftar personil melalui Pattern Matching Engine:\n")
    for member in team:
        time.sleep(0.1)
        # Simulasi ekspresi pattern matching Scala
        # member match { ... }
        if member.experience_years >= 8:
            verdict = f"{MAGENTA}Senior Principal/Lead Tier{RESET} (Years >= 8)"
        elif member.role == "Data Engineer":
            verdict = f"{BLUE}Spesialis Apache Spark/Flink Pipeline{RESET}"
        elif member.experience_years < 2:
            verdict = f"{YELLOW}Mentee / Onboarding Track{RESET}"
        else:
            verdict = f"{GREEN}Core Production Contributor{RESET}"

        print(f"  • {BOLD}{member.name}{RESET} [{member.role}, {member.experience_years} thn]")
        print(f"    └── Match Result: {verdict}")


def simulate_expression_oriented():
    print(f"\n{BOLD}{YELLOW}=== 4. SIMULASI PARADIGMA EXPRESSION-ORIENTED & EVALUASI ==={RESET}")
    print("Di Scala, kontrol alur (if-else, try-catch, match, blok {}) menghasilkan nilai (expression), bukan statement.")

    scores = [45, 78, 92]
    print(f"\n{BOLD}Evaluasi ekspresi 'val grade = if (score >= 80) ...'{RESET}")
    for s in scores:
        time.sleep(0.08)
        # Di Scala: val grade = if (score >= 85) "A" else if (score >= 70) "B" else "C"
        grade = "A (Distinction)" if s >= 85 else ("B (Satisfactory)" if s >= 70 else "C (Need Improvement)")
        print(f"  Score: {s:<3} => Hasil Ekspresi: {GREEN}{BOLD}{grade}{RESET}")

    print(f"\n{BOLD}Perbedaan Konsep Evaluasi Pengikatan:{RESET}")
    print(f"  - {CYAN}val{RESET}      : Immutable reference, dievaluasi satu kali saat deklarasi (eager).")
    print(f"  - {YELLOW}var{RESET}      : Mutable reference, dilarang dalam pure FP idioamtik kecuali performa kritis.")
    print(f"  - {MAGENTA}lazy val{RESET} : Dievaluasi hanya saat pertama kali diakses (deferred/cached memoization).")
    print(f"  - {BLUE}def{RESET}      : Evaluasi ulang setiap kali dipanggil (by-name evaluation model).")


def interactive_menu():
    print_banner()
    while True:
        print(f"\n{BOLD}Pilih Modul Simulasi:{RESET}")
        print(f"  {CYAN}1.{RESET} Unified Type Hierarchy (Any, AnyVal, AnyRef, Nothing)")
        print(f"  {CYAN}2.{RESET} Pipeline Kompilasi Scala 3 & JVM TASTy Architecture")
        print(f"  {CYAN}3.{RESET} Case Class & Pattern Matching Engine")
        print(f"  {CYAN}4.{RESET} Expression-Oriented & Binding Semantics (val, var, lazy)")
        print(f"  {CYAN}5.{RESET} Jalankan Seluruh Demonstrasi (Batch Mode)")
        print(f"  {RED}0.{RESET} Keluar")

        try:
            choice = input(f"\n{BOLD}Masukkan pilihan [0-5]: {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{DIM}Selesai.{RESET}")
            break

        if choice == "1":
            simulate_type_hierarchy()
        elif choice == "2":
            simulate_compilation_pipeline()
        elif choice == "3":
            simulate_pattern_matching()
        elif choice == "4":
            simulate_expression_oriented()
        elif choice == "5":
            simulate_type_hierarchy()
            simulate_compilation_pipeline()
            simulate_pattern_matching()
            simulate_expression_oriented()
            print(f"\n{GREEN}{BOLD}Semua simulasi fondasi Scala BAB-01 selesai dieksekusi dengan sukses!{RESET}\n")
        elif choice == "0":
            print(f"{CYAN}Keluar dari Lab Exercise. Selamat mendalami ekosistem Scala!{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak valid. Silakan masukkan angka 0 sampai 5.{RESET}")


if __name__ == "__main__":
    # Jika dijalankan secara non-interaktif atau dilempar argumen batch/test, jalankan semua lalu keluar
    if len(sys.argv) > 1 and sys.argv[1] in ("--batch", "-b", "--all", "test"):
        print_banner()
        simulate_type_hierarchy()
        simulate_compilation_pipeline()
        simulate_pattern_matching()
        simulate_expression_oriented()
        print(f"\n{GREEN}{BOLD}Batch execution test passed.{RESET}")
    else:
        interactive_menu()
