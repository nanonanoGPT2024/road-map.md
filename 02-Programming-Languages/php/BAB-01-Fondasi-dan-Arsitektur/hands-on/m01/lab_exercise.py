#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Fondasi & Arsitektur Runtime PHP (Zend Engine)
BAB-01: Fondasi dan Arsitektur PHP
Materi: Lexing, Parsing (AST), Opcode Compilation, Zend VM, & Request Lifecycle
"""

import sys
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

# ANSI Color Codes untuk visualisasi terminal
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BG_BLUE = "\033[44m"
    BG_DARK = "\033[40m"

@dataclass
class Token:
    name: str
    value: str
    line: int

@dataclass
class Opcode:
    op_number: int
    instruction: str
    op1: Optional[str] = None
    op2: Optional[str] = None
    result: Optional[str] = None

@dataclass
class Zval:
    type_name: str
    value: Any
    refcount: int = 1
    is_ref: bool = False

def print_header(title: str):
    print(f"\n{Color.BG_BLUE}{Color.WHITE}{Color.BOLD} === {title} === {Color.RESET}\n")

def print_step(step_name: str, desc: str):
    print(f"{Color.CYAN}▶ [{step_name}]{Color.RESET} {Color.BOLD}{desc}{Color.RESET}")

def simulate_zend_pipeline():
    sample_php = """<?php
$a = 10;
$b = 25;
$c = $a + $b;
echo "Hasil: " . $c;
"""
    print_header("SIMULASI PIPELINE ZEND ENGINE (Kompilasi & Eksekusi)")
    print(f"{Color.YELLOW}Kode Sumber PHP:{Color.RESET}")
    print(f"{Color.DIM}{sample_php}{Color.RESET}")
    time.sleep(0.6)

    # 1. Lexical Analysis (Lexing / Scanning)
    print_step("FASE 1: LEXING (Scanning)", "Mengubah source code string menjadi stream token (re2c)")
    tokens = [
        Token("T_OPEN_TAG", "<?php\\n", 1),
        Token("T_VARIABLE", "$a", 2),
        Token("=", "=", 2),
        Token("T_LNUMBER", "10", 2),
        Token(";", ";", 2),
        Token("T_VARIABLE", "$b", 3),
        Token("=", "=", 3),
        Token("T_LNUMBER", "25", 3),
        Token(";", ";", 3),
        Token("T_VARIABLE", "$c", 4),
        Token("=", "=", 4),
        Token("T_VARIABLE", "$a", 4),
        Token("+", "+", 4),
        Token("T_VARIABLE", "$b", 4),
        Token(";", ";", 4),
        Token("T_ECHO", "echo", 5),
        Token("T_CONSTANT_ENCAPSED_STRING", '"Hasil: "', 5),
        Token(".", ".", 5),
        Token("T_VARIABLE", "$c", 5),
        Token(";", ";", 5),
    ]

    for tok in tokens[:8]:
        print(f"  {Color.GREEN}Token:{Color.RESET} {tok.name:<25} | Nilai: {tok.value:<10} (Baris {tok.line})")
    print(f"  {Color.DIM}... [total {len(tokens)} token terurai secara deterministik] ...{Color.RESET}\n")
    time.sleep(0.8)

    # 2. Parsing (AST Construction)
    print_step("FASE 2: PARSING (Bison Grammar)", "Membangun Abstract Syntax Tree (AST) dari token stream")
    ast_representation = """  └── ZEND_AST_STMT_LIST
      ├── ZEND_AST_ASSIGN ($a, 10)
      ├── ZEND_AST_ASSIGN ($b, 25)
      ├── ZEND_AST_ASSIGN ($c, ZEND_AST_BINARY_OP[ADD] ($a, $b))
      └── ZEND_AST_ECHO (ZEND_AST_BINARY_OP[CONCAT] ("Hasil: ", $c))"""
    print(f"{Color.MAGENTA}{ast_representation}{Color.RESET}\n")
    time.sleep(0.8)

    # 3. Compilation into Zend Opcodes
    print_step("FASE 3: COMPILATION", "Mengubah AST menjadi Opcodes (Zend Op Array) siap dieksekusi")
    opcodes = [
        Opcode(0, "ASSIGN", "$a", "10", None),
        Opcode(1, "ASSIGN", "$b", "25", None),
        Opcode(2, "ADD", "$a", "$b", "~0"),
        Opcode(3, "ASSIGN", "$c", "~0", None),
        Opcode(4, "CONCAT", '"Hasil: "', "$c", "~1"),
        Opcode(5, "ECHO", "~1", None, None),
        Opcode(6, "RETURN", "1", None, None),
    ]

    print(f"  {'Line':<5} | {'Instruction':<12} | {'Op1':<12} | {'Op2':<12} | {'Result':<10}")
    print("  " + "-" * 58)
    for op in opcodes:
        op1_str = op.op1 if op.op1 else "-"
        op2_str = op.op2 if op.op2 else "-"
        res_str = op.result if op.result else "-"
        print(f"  {op.op_number:<5} | {Color.YELLOW}{op.instruction:<12}{Color.RESET} | {op1_str:<12} | {op2_str:<12} | {Color.CYAN}{res_str:<10}{Color.RESET}")
    print()
    time.sleep(0.8)

    # 4. Zend Virtual Machine Execution
    print_step("FASE 4: ZEND VM EXECUTION", "Zend Executor memproses instruction pointer (zend_execute_data)")
    variables: Dict[str, Zval] = {}
    output_buffer: List[str] = []

    for op in opcodes:
        if op.instruction == "ASSIGN":
            val = int(op.op2) if op.op2.isdigit() else variables[op.op2].value
            variables[op.op1] = Zval(type_name="IS_LONG", value=val)
            print(f"  {Color.DIM}VM Exec:{Color.RESET} Set {op.op1} = {val} [zval allocated]")
        elif op.instruction == "ADD":
            res = variables[op.op1].value + variables[op.op2].value
            variables[op.result] = Zval(type_name="IS_LONG", value=res)
            print(f"  {Color.DIM}VM Exec:{Color.RESET} Calc {op.op1} + {op.op2} -> {op.result} = {res}")
        elif op.instruction == "CONCAT":
            str_val = op.op1.strip('"') + str(variables[op.op2].value)
            variables[op.result] = Zval(type_name="IS_STRING", value=str_val)
            print(f"  {Color.DIM}VM Exec:{Color.RESET} Concat strings -> {op.result} = '{str_val}'")
        elif op.instruction == "ECHO":
            output_buffer.append(variables[op.op1].value)
            print(f"  {Color.GREEN}VM Output:{Color.RESET} Menulis ke stdout buffer")
        time.sleep(0.2)

    print(f"\n{Color.BOLD}{Color.GREEN}Output Akhir Script PHP:{Color.RESET} {''.join(output_buffer)}\n")

def simulate_lifecycle():
    print_header("SIMULASI SIKLUS HIDUP REQUEST PHP (Shared-Nothing Architecture)")
    phases = [
        ("1. Module Initialization (MINIT)", "Dipanggil saat PHP engine pertama kali start (e.g. php-fpm master process booted). Inisialisasi ekstensi bawaan & PDO."),
        ("2. Request Initialization (RINIT)", "Dipanggil per HTTP request baru. Setup superglobals ($_GET, $_POST, $_SERVER), alokasi Zend Memory Manager (ZMM)."),
        ("3. Script Execution", "Zend VM mengeksekusi opcodes. Shared-nothing context aktif: memori terisolasi penuh dari request lain."),
        ("4. Request Shutdown (RSHUTDOWN)", "Request selesai. ZMM membersihkan SEMUA alokasi memori request, menghancurkan variabel lokal, menutup buffer output."),
        ("5. Module Shutdown (MSHUTDOWN)", "Dipanggil hanya ketika web server/PHP-FPM dimatikan total. Cleanup static resource ekstensi.")
    ]

    for title, desc in phases:
        print(f"{Color.YELLOW}● {title}{Color.RESET}")
        print(f"  {Color.WHITE}{desc}{Color.RESET}\n")
        time.sleep(0.5)

    print(f"{Color.CYAN}Kesimpulan Shared-Nothing:{Color.RESET} Kebocoran memori (memory leak) di satu request tidak akan meracuni request berikutnya!")

def simulate_zval_refcounting():
    print_header("SIMULASI STRUKTUR DATA ZVAL & REFCOUNTING")
    print("Melihat bagaimana PHP mengelola memori dengan Copy-On-Write (COW):\n")

    print(f"{Color.BOLD}Langkah 1: $x = 'Hello Dunia'{Color.RESET}")
    val_x = Zval(type_name="IS_STRING", value="Hello Dunia", refcount=1)
    print(f"  zval(x) -> type: {val_x.type_name}, value: '{val_x.value}', refcount: {Color.GREEN}{val_x.refcount}{Color.RESET}")

    print(f"\n{Color.BOLD}Langkah 2: $y = $x (Penugasan variabel tanpa modifikasi){Color.RESET}")
    val_x.refcount += 1
    val_y = val_x
    print(f"  [Copy-On-Write]: Memori TIDAK diduplikasi!")
    print(f"  zval(x & y) -> value: '{val_x.value}', refcount: {Color.YELLOW}{val_x.refcount}{Color.RESET}")

    print(f"\n{Color.BOLD}Langkah 3: $y .= ' Modifikasi' (Trigger Copy-On-Write){Color.RESET}")
    val_x.refcount -= 1
    val_y = Zval(type_name="IS_STRING", value="Hello Dunia Modifikasi", refcount=1)
    print(f"  [COW Triggered]: Terjadi alokasi memori baru untuk $y!")
    print(f"  zval(x) -> value: '{val_x.value}', refcount: {Color.GREEN}{val_x.refcount}{Color.RESET}")
    print(f"  zval(y) -> value: '{val_y.value}', refcount: {Color.GREEN}{val_y.refcount}{Color.RESET}\n")

def interactive_menu():
    while True:
        print(f"\n{Color.BOLD}===================================================={Color.RESET}")
        print(f"{Color.CYAN}{Color.BOLD}  LAB INTERAKTIF: FONDASI & ARSITEKTUR PHP (BAB-01) {Color.RESET}")
        print(f"{Color.BOLD}===================================================={Color.RESET}")
        print(" [1] Simulasi Pipeline Kompilasi Zend Engine (Lexer -> AST -> Opcode -> VM)")
        print(" [2] Simulasi Siklus Hidup Request (MINIT -> RINIT -> RSHUTDOWN -> MSHUTDOWN)")
        print(" [3] Simulasi Mekanisme zval & Copy-On-Write (COW)")
        print(" [4] Jalankan Semua Simulasi Berurutan")
        print(" [0] Keluar")
        print("----------------------------------------------------")
        
        try:
            choice = input(f"{Color.YELLOW}Pilih opsi (0-4): {Color.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nKeluar dari lab.")
            break

        if choice == "1":
            simulate_zend_pipeline()
        elif choice == "2":
            simulate_lifecycle()
        elif choice == "3":
            simulate_zval_refcounting()
        elif choice == "4":
            simulate_zend_pipeline()
            simulate_lifecycle()
            simulate_zval_refcounting()
        elif choice == "0":
            print(f"\n{Color.GREEN}Terima kasih telah menjalankan hands-on lab fondasi PHP!{Color.RESET}\n")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid. Silakan pilih 0-4.{Color.RESET}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        # Non-interactive automated execution mode
        simulate_zend_pipeline()
        simulate_lifecycle()
        simulate_zval_refcounting()
    else:
        interactive_menu()
