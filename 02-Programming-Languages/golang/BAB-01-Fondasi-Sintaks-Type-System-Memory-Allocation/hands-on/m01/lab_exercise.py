#!/usr/bin/env python3
"""
Interactive Golang Fundamentals Simulation Lab (BAB 01)
Simulates:
  - Zero Value & Strict Static Type System
  - Memory Layout: Array vs Slice Header (Data Pointer, Len, Cap)
  - Value vs Pointer Semantics (Copy vs Mutation)
  - Escape Analysis (Stack Allocation vs Heap Escape)

Author: Go Curriculum Hands-on Engine
Language: Python 3 (Standalone, Zero External Dependencies)
"""

import sys
import time
from dataclasses import dataclass
from typing import List, Optional, Any

# ANSI Terminal Color Palette
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
ITALIC = "\033[3m"
UNDERLINE = "\033[4m"

RED = "\033[38;5;196m"
GREEN = "\033[38;5;46m"
YELLOW = "\033[38;5;220m"
BLUE = "\033[38;5;39m"
MAGENTA = "\033[38;5;201m"
CYAN = "\033[38;5;51m"
WHITE = "\033[38;5;231m"
GRAY = "\033[38;5;244m"
BG_BLUE = "\033[48;5;24m"
BG_DARK = "\033[48;5;234m"

def print_banner() -> None:
    print(f"{CYAN}{BOLD}" + "=" * 76 + f"{RESET}")
    print(f"{BLUE}{BOLD}   GOLANG CORE ENGINE: INTERACTIVE MEMORY & TYPE SYSTEM SIMULATOR{RESET}")
    print(f"{GRAY}   BAB 01 - Fondasi Sintaks, Type System, Memory Layout & Escape Analysis{RESET}")
    print(f"{CYAN}{BOLD}" + "=" * 76 + f"{RESET}\n")

def pause_step(message: str = "Tekan [Enter] untuk melanjutkan...") -> None:
    if sys.stdin.isatty():
        try:
            input(f"\n{YELLOW}{ITALIC}>>> {message}{RESET}")
        except (KeyboardInterrupt, EOFError):
            print()
            sys.exit(0)
    else:
        time.sleep(0.3)
        print()

# -----------------------------------------------------------------------------
# 1. SIMULASI ZERO VALUES & STATIC TYPE SYSTEM
# -----------------------------------------------------------------------------
@dataclass
class GoField:
    name: str
    go_type: str
    zero_repr: str
    byte_size: int

def simulate_zero_values() -> None:
    print(f"{MAGENTA}{BOLD}[MODUL 1] Zero Value Specification & Memory Footprint{RESET}")
    print(f"{GRAY}Dalam Golang, tidak ada konsep 'uninitialized memory' atau 'garbage memory'.")
    print(f"Setiap alokasi variabel otomatis dinolkan (Zero-initialized) sesuai tipe data.{RESET}\n")

    fields = [
        GoField("isActive", "bool", "false", 1),
        GoField("counter", "int64", "0", 8),
        GoField("ratio", "float64", "0.0", 8),
        GoField("label", "string", '"" (ptr: nil, len: 0)', 16),
        GoField("items", "[]int", "nil (slice header: 0, 0, nil)", 24),
        GoField("metadata", "map[string]int", "nil (hmap pointer = 0x0)", 8),
        GoField("worker", "*Worker", "nil (pointer address = 0x0)", 8),
        GoField("notifier", "io.Reader", "nil (iface: tab=nil, data=nil)", 16),
    ]

    print(f"{BOLD}{'Nama Field':<15} {'Go Type':<16} {'Size (Byte)':<12} {'Zero Value Representation':<30}{RESET}")
    print(f"{GRAY}{'-'*15} {'-'*16} {'-'*12} {'-'*30}{RESET}")
    total_size = 0
    for f in fields:
        total_size += f.byte_size
        print(f"{WHITE}{f.name:<15}{RESET} {CYAN}{f.go_type:<16}{RESET} {YELLOW}{f.byte_size:<12}{RESET} {GREEN}{f.zero_repr:<30}{RESET}")

    print(f"{GRAY}{'-'*75}{RESET}")
    print(f"{BOLD}Total Zero-State Struct Footprint: {YELLOW}{total_size} Bytes{RESET}\n")

    print(f"{BLUE}{BOLD}Aturan Type System & Keamanan Kompilasi:{RESET}")
    print(f" {GREEN}✔{RESET} Tidak ada 'implicit narrowing/widening conversion' (e.g., int32 != int).")
    print(f" {GREEN}✔{RESET} Untyped constants (`const X = 42`) memiliki presisi arbitrary sampai dievaluasi.")
    print(f" {GREEN}✔{RESET} Zero value selalu deterministik dan aman dari segmentasi memori kotor.")

# -----------------------------------------------------------------------------
# 2. SIMULASI SLICE HEADER & MEMORY ALLOCATION / CAPACITY GROWTH
# -----------------------------------------------------------------------------
@dataclass
class SliceHeader:
    data_ptr: int
    len: int
    cap: int

class SliceEngine:
    def __init__(self, initial_cap: int = 2):
        self._backing_array: List[Optional[int]] = [None] * initial_cap
        self._base_address: int = 0x140000a2000
        self.header = SliceHeader(data_ptr=self._base_address, len=0, cap=initial_cap)

    def append(self, val: int) -> dict:
        event = {"old_cap": self.header.cap, "reallocated": False, "old_ptr": self.header.data_ptr}
        if self.header.len == self.header.cap:
            # Go 1.18+ growth formula: double until 256, then (cap + 3*256)/4
            new_cap = self.header.cap * 2 if self.header.cap < 256 else int((self.header.cap + 768) / 4)
            self._base_address += 0x1000  # Pindah blok memori heap baru
            new_array: List[Optional[int]] = [None] * new_cap
            for i in range(self.header.len):
                new_array[i] = self._backing_array[i]
            self._backing_array = new_array
            self.header.cap = new_cap
            self.header.data_ptr = self._base_address
            event["reallocated"] = True
            event["new_cap"] = new_cap
            event["new_ptr"] = self.header.data_ptr

        self._backing_array[self.header.len] = val
        self.header.len += 1
        return event

    def render_memory(self) -> None:
        print(f"  {BOLD}Slice Header (24 Bytes di Stack):{RESET}")
        print(f"    [ Data Pointer: {CYAN}{hex(self.header.data_ptr)}{RESET} | Len: {YELLOW}{self.header.len}{RESET} | Cap: {MAGENTA}{self.header.cap}{RESET} ]")
        print(f"  {BOLD}Backing Array di Memory Block ({hex(self.header.data_ptr)}):{RESET}")

        cells = []
        for i in range(self.header.cap):
            if i < self.header.len:
                cells.append(f"{GREEN}[ {self._backing_array[i]} ]{RESET}")
            else:
                cells.append(f"{GRAY}[ _ ]{RESET}")
        print("    " + " ".join(cells))
        print(f"    {DIM}Slot Terisi (Len): {self.header.len} | Slot Reserved (Cap): {self.header.cap}{RESET}\n")

def simulate_slice_lifecycle() -> None:
    print(f"\n{MAGENTA}{BOLD}[MODUL 2] Anatomi Slice Header & Dynamic Backing Array Growth{RESET}")
    print(f"{GRAY}Slice bukan array langsung, melainkan struct kecil 3 kata mesin (24 byte di arsitektur 64-bit).{RESET}\n")

    engine = SliceEngine(initial_cap=2)
    print(f"{BOLD}Inisialisasi `s := make([]int, 0, 2)`:{RESET}")
    engine.render_memory()

    elements = [10, 20, 30, 40, 50]
    for idx, num in enumerate(elements, 1):
        print(f"{YELLOW}>>> Operasi: `s = append(s, {num})`{RESET}")
        evt = engine.append(num)
        if evt["reallocated"]:
            print(f"  {RED}{BOLD}⚡ REALLOCATION TRIGGERED! Cap overflowed from {evt['old_cap']} to {evt['new_cap']}.{RESET}")
            print(f"  {RED}  Data pointer berpindah: {hex(evt['old_ptr'])} -> {hex(evt['new_ptr'])}{RESET}")
        engine.render_memory()

# -----------------------------------------------------------------------------
# 3. VALUE SEMANTICS VS POINTER SEMANTICS (MUTASI & COPY OVERHEAD)
# -----------------------------------------------------------------------------
@dataclass
class UserState:
    id: int
    name: str
    balance: float
    address_mem: str

def simulate_semantics() -> None:
    print(f"\n{MAGENTA}{BOLD}[MODUL 3] Value Semantics (Copy) vs Pointer Semantics (Sharing){RESET}")
    print(f"{GRAY}Golang adalah bahasa 'Pass by Value'. Mengoper pointer berarti meng-copy address pointer tersebut.{RESET}\n")

    original = UserState(id=101, name="Gopher Indonesia", balance=500000.0, address_mem="0xc0000100a0")
    print(f"{BOLD}Variabel Asli `u1` pada Memory Address {CYAN}{original.address_mem}{RESET}:")
    print(f"  Data: ID={original.id}, Name={original.name}, Saldo=Rp{original.balance:,.2f}\n")

    # Value receiver simulation
    print(f"{BLUE}[A] Value Receiver: `func UpdateBalanceValue(u User, newBalance float64)`{RESET}")
    copy_address = "0xc000010120"
    print(f"  -> Seluruh struct disalin (shallow copy) ke stack frame baru di {YELLOW}{copy_address}{RESET}.")
    u_copy = UserState(id=original.id, name=original.name, balance=750000.0, address_mem=copy_address)
    print(f"  -> Mutasi saldo pada copy: Rp{u_copy.balance:,.2f}")
    print(f"  -> State `u1` asli setelah pemanggilan: {GREEN}Rp{original.balance:,.2f}{RESET} (TIDAK BERUBAH - Isolation Terjaga)")

    # Pointer receiver simulation
    print(f"\n{BLUE}[B] Pointer Receiver: `func UpdateBalancePointer(u *User, newBalance float64)`{RESET}")
    ptr_address = "0xc0000101f8"
    print(f"  -> Parameter adalah pointer 8-byte di {YELLOW}{ptr_address}{RESET}, mereferensikan address {CYAN}{original.address_mem}{RESET}.")
    original.balance = 990000.0
    print(f"  -> Dereferensikan pointer (*u).balance = 990000")
    print(f"  -> State `u1` asli sekarang: {RED}{BOLD}Rp{original.balance:,.2f}{RESET} (MUTASI LANGSUNG PADA HEAP/STACK INDUK)")

# -----------------------------------------------------------------------------
# 4. SIMULASI ESCAPE ANALYSIS (STACK VS HEAP ESCAPE)
# -----------------------------------------------------------------------------
@dataclass
class EscapeScenario:
    code_snippet: str
    allocation_target: str
    compiler_reason: str
    diagnostic_flag: str

def simulate_escape_analysis() -> None:
    print(f"\n{MAGENTA}{BOLD}[MODUL 4] Compiler Escape Analysis Simulator (`go build -gcflags='-m'`){RESET}")
    print(f"{GRAY}Compiler Go menentukan apakah variabel aman dialokasikan di Stack atau harus 'escape to heap'.{RESET}\n")

    scenarios = [
        EscapeScenario(
            code_snippet="func NewUser(name string) User {\n    u := User{Name: name}\n    return u // return by value\n}",
            allocation_target="STACK ALLOCATION",
            compiler_reason="Nilai struct disalin langsung ke caller stack frame. Lifetime objek tidak melebihi fungsi.",
            diagnostic_flag="does not escape"
        ),
        EscapeScenario(
            code_snippet="func NewUserPtr(name string) *User {\n    u := User{Name: name}\n    return &u // return reference\n}",
            allocation_target="HEAP ESCAPE",
            compiler_reason="Alamat memori &u dikembalikan keluar scope fungsi. Jika ditaruh di stack, alamat akan tertimpa (dangling).",
            diagnostic_flag="&u escapes to heap"
        ),
        EscapeScenario(
            code_snippet="var a any = 42\nfmt.Println(a)",
            allocation_target="HEAP ESCAPE",
            compiler_reason="Variabel dimasukkan ke interface{} / any (reflection & boxing type header runtime).",
            diagnostic_flag="a escapes to heap"
        ),
        EscapeScenario(
            code_snippet="size := 1024\nbuf := make([]byte, size)",
            allocation_target="HEAP ESCAPE",
            compiler_reason="Ukuran alokasi ditentukan secara dinamis pada runtime (non-constant size).",
            diagnostic_flag="make([]byte, size) escapes to heap"
        ),
    ]

    for idx, sc in enumerate(scenarios, 1):
        color = GREEN if "STACK" in sc.allocation_target else RED
        print(f"{BOLD}Kasus #{idx}:{RESET}")
        print(f"{WHITE}{sc.code_snippet}{RESET}")
        print(f"  Status Kompilasi: {color}{BOLD}{sc.allocation_target}{RESET}")
        print(f"  Compiler Diagnostic Output: {CYAN}`{sc.diagnostic_flag}`{RESET}")
        print(f"  Analisis Mekanisme: {GRAY}{sc.compiler_reason}{RESET}\n")

# -----------------------------------------------------------------------------
# 5. INTERACTIVE KNOWLEDGE CHECK / SELF TEST
# -----------------------------------------------------------------------------
def run_interactive_quiz() -> None:
    print(f"\n{MAGENTA}{BOLD}[MODUL 5] Uji Pemahaman Mandiri (Self-Assessment Checklist){RESET}")
    questions = [
        {
            "q": "Berapa ukuran memory header dari sebuah slice pada arsitektur 64-bit?",
            "options": ["A. 8 bytes", "B. 16 bytes", "C. 24 bytes", "D. Dinamis sesuai len"],
            "ans": "C",
            "explain": "Slice header terdiri dari Data Pointer (8B), Len (8B), dan Cap (8B) = 24 bytes total."
        },
        {
            "q": "Apa zero value dari sebuah tipe data interface atau pointer?",
            "options": ["A. 0", "B. undefined", "C. empty struct", "D. nil"],
            "ans": "D",
            "explain": "Tipe referensi dan interface memiliki zero value `nil` (0x0)."
        },
        {
            "q": "Mengapa mengembalikan pointer `&localStruct` dalam fungsi Go aman dari bug dangling pointer (seperti di C)?",
            "options": [
                "A. Go melarang pengembalian pointer",
                "B. Escape analysis compiler otomatis memindahkan alokasi ke Heap",
                "C. Stack frame Go tidak pernah dibersihkan",
                "D. Pointer di-copy otomatis menjadi array"
            ],
            "ans": "B",
            "explain": "Go compiler melakukan escape analysis statis dan mengalokasikan memori di heap runtime jika referensi keluar stack frame."
        }
    ]

    score = 0
    is_tty = sys.stdin.isatty()
    for idx, item in enumerate(questions, 1):
        print(f"{BOLD}Pertanyaan {idx}/{len(questions)}:{RESET} {WHITE}{item['q']}{RESET}")
        for opt in item["options"]:
            print(f"  {opt}")
        user_choice = ""
        if is_tty:
            try:
                user_choice = input(f"{YELLOW}Jawaban Anda (A/B/C/D): {RESET}").strip().upper()
            except (KeyboardInterrupt, EOFError):
                break
        else:
            user_choice = item["ans"]
            print(f"{YELLOW}Jawaban Otomatis (Demo/Non-TTY): {user_choice}{RESET}")

        if user_choice == item["ans"]:
            print(f"{GREEN}{BOLD}✔ BENAR!{RESET} {item['explain']}\n")
            score += 1
        else:
            print(f"{RED}{BOLD}✘ KURANG TEPAT.{RESET} Jawaban yang benar adalah {item['ans']}. {item['explain']}\n")

    print(f"{CYAN}{BOLD}Hasil Evaluasi: {score}/{len(questions)} Konsep Terpenuhi.{RESET}\n")

# -----------------------------------------------------------------------------
# MAIN ENTRYPOINT
# -----------------------------------------------------------------------------
def main() -> None:
    print_banner()

    steps = [
        ("Simulasi Zero Value & Static Typing", simulate_zero_values),
        ("Simulasi Anatomi Slice Header & Heap Reallocation", simulate_slice_lifecycle),
        ("Simulasi Value vs Pointer Semantics", simulate_semantics),
        ("Simulasi Escape Analysis Engine", simulate_escape_analysis),
        ("Uji Pemahaman Mandiri", run_interactive_quiz),
    ]

    for title, action in steps:
        action()
        pause_step(f"Lanjut ke langkah berikutnya: {title}...")

    print(f"{GREEN}{BOLD}════════════════════════════════════════════════════════════════════════════{RESET}")
    print(f"{GREEN}{BOLD}✔ SIMULASI SELESAI: Seluruh konsep inti BAB 01 Golang tervalidasi sukses.{RESET}")
    print(f"{GREEN}{BOLD}════════════════════════════════════════════════════════════════════════════{RESET}\n")

if __name__ == "__main__":
    main()
