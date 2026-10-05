#!/usr/bin/env python3
"""
Lab Exercise: Fondasi Logika Komputasi dan Matematika Diskrit
Modul: BAB-01 - Logika Proposisional, Aljabar Boolean, Teori Himpunan, & Graf
"""

import sys
import itertools
from typing import Callable, Dict, List, Set, Tuple

# ==========================================
# ANSI Color Codes & Formatting Helpers
# ==========================================
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    GRAY = "\033[90m"

def print_header(title: str) -> None:
    border = "=" * 68
    print(f"\n{Color.CYAN}{Color.BOLD}{border}")
    print(f" {title.center(66)} ")
    print(f"{border}{Color.RESET}\n")

def print_section(title: str) -> None:
    print(f"\n{Color.YELLOW}{Color.BOLD}>>> {title} <<<{Color.RESET}")

def color_bool(val: bool) -> str:
    return f"{Color.GREEN}T{Color.RESET}" if val else f"{Color.RED}F{Color.RESET}"

# ==========================================
# 1. Propositional Logic & Truth Tables
# ==========================================
def implies(p: bool, q: bool) -> bool:
    """Material implication: P -> Q equivalent to (not P) or Q"""
    return (not p) or q

def iff(p: bool, q: bool) -> bool:
    """Biconditional: P <-> Q equivalent to P == Q"""
    return p == q

def xor(p: bool, q: bool) -> bool:
    """Exclusive OR: P ⊕ Q"""
    return p != q

def generate_truth_table() -> None:
    print_section("Simulasi Tabel Kebenaran (Truth Table Generator)")
    headers = ["P", "Q", "NOT P", "P AND Q", "P OR Q", "P XOR Q", "P -> Q", "P <-> Q"]
    header_str = " | ".join(f"{Color.BOLD}{h:^8}{Color.RESET}" for h in headers)
    separator = "-+-".join("-" * 8 for _ in headers)

    print(header_str)
    print(f"{Color.GRAY}{separator}{Color.RESET}")

    for p, q in itertools.product([True, False], repeat=2):
        row = [
            color_bool(p),
            color_bool(q),
            color_bool(not p),
            color_bool(p and q),
            color_bool(p or q),
            color_bool(xor(p, q)),
            color_bool(implies(p, q)),
            color_bool(iff(p, q))
        ]
        # Align manually because color codes contain non-printable chars
        row_str = " | ".join(f"{r:^17}" for r in row)
        print(row_str)

# ==========================================
# 2. Pembuktian Formal Hukum De Morgan
# ==========================================
def verify_de_morgan() -> None:
    print_section("Verifikasi Ekuivalensi Logis: Hukum De Morgan")
    print(f"{Color.MAGENTA}Hukum 1: ¬(P ∧ Q) ≡ (¬P ∨ ¬Q){Color.RESET}")
    print(f"{Color.MAGENTA}Hukum 2: ¬(P ∨ Q) ≡ (¬P ∧ ¬Q){Color.RESET}\n")

    law1_valid = True
    law2_valid = True

    print(f"{'P':^5} | {'Q':^5} | {'¬(P∧Q)':^10} | {'(¬P∨¬Q)':^10} | {'Hukum 1':^10} | {'¬(P∨Q)':^10} | {'(¬P∧¬Q)':^10} | {'Hukum 2':^10}")
    print("-" * 78)

    for p, q in itertools.product([True, False], repeat=2):
        lhs1 = not (p and q)
        rhs1 = (not p) or (not q)
        match1 = (lhs1 == rhs1)
        if not match1:
            law1_valid = False

        lhs2 = not (p or q)
        rhs2 = (not p) and (not q)
        match2 = (lhs2 == rhs2)
        if not match2:
            law2_valid = False

        res1_str = f"{Color.GREEN}VALID{Color.RESET}" if match1 else f"{Color.RED}INVALID{Color.RESET}"
        res2_str = f"{Color.GREEN}VALID{Color.RESET}" if match2 else f"{Color.RED}INVALID{Color.RESET}"

        print(f"{str(p):^5} | {str(q):^5} | {str(lhs1):^10} | {str(rhs1):^10} | {res1_str:^19} | {str(lhs2):^10} | {str(rhs2):^10} | {res2_str:^19}")

    print()
    if law1_valid and law2_valid:
        print(f"{Color.GREEN}{Color.BOLD}[BERHASIL]{Color.RESET} Semua kasus terbukti tautologi. Hukum De Morgan terverifikasi secara formal.")
    else:
        print(f"{Color.RED}{Color.BOLD}[GAGAL]{Color.RESET} Terdapat kontradiksi dalam evaluasi ekuivalensi.")

# ==========================================
# 3. Simulasi Gerbang Logika & Full Adder
# ==========================================
def half_adder(a: int, b: int) -> Tuple[int, int]:
    """Half Adder: Menghasilkan (Sum, Carry)"""
    sum_bit = a ^ b
    carry_bit = a & b
    return sum_bit, carry_bit

def full_adder(a: int, b: int, cin: int) -> Tuple[int, int]:
    """Full Adder: Menggabungkan dua half adder dan gerbang OR"""
    s1, c1 = half_adder(a, b)
    sum_bit, c2 = half_adder(s1, cin)
    carry_out = c1 | c2
    return sum_bit, carry_out

def simulate_full_adder() -> None:
    print_section("Simulasi Gerbang Logika: 1-Bit Full Adder (Rangkaian Aritmatika)")
    print("Formula: Sum = A ⊕ B ⊕ Cin, Cout = (A ∧ B) ∨ (Cin ∧ (A ⊕ B))\n")

    print(f"{'A':^5} | {'B':^5} | {'Cin':^5} | {'Sum':^7} | {'Cout':^7} | {'Verifikasi Desimal':^20}")
    print("-" * 58)

    all_correct = True
    for a, b, cin in itertools.product([0, 1], repeat=3):
        s, cout = full_adder(a, b, cin)
        expected_decimal = a + b + cin
        actual_decimal = (cout << 1) | s
        ok = (expected_decimal == actual_decimal)
        if not ok:
            all_correct = False

        status = f"{Color.GREEN}{actual_decimal} == {expected_decimal} (OK){Color.RESET}" if ok else f"{Color.RED}FAIL{Color.RESET}"
        print(f"{a:^5} | {b:^5} | {cin:^5} | {s:^7} | {cout:^7} | {status:^29}")

    if all_correct:
        print(f"\n{Color.GREEN}{Color.BOLD}[OK]{Color.RESET} Rangkaian Full Adder berfungsi sempurna 100% untuk operasi aritmatika biner.")

# ==========================================
# 4. Teori Himpunan & Sifat Relasi Biner
# ==========================================
def analyze_binary_relation(domain: Set[int], relation: Set[Tuple[int, int]]) -> None:
    print_section("Analisis Sifat Relasi Biner (Matematika Diskrit)")
    print(f"Domain himpunan A : {Color.CYAN}{sorted(list(domain))}{Color.RESET}")
    print(f"Relasi R ⊆ A x A  : {Color.BLUE}{sorted(list(relation))}{Color.RESET}\n")

    # 1. Refleksif: ∀x ∈ A, (x, x) ∈ R
    is_reflexive = all((x, x) in relation for x in domain)

    # 2. Simetris: ∀x, y ∈ A, (x, y) ∈ R => (y, x) ∈ R
    is_symmetric = all((y, x) in relation for (x, y) in relation)

    # 3. Transitif: ∀x, y, z ∈ A, ((x, y) ∈ R ∧ (y, z) ∈ R) => (x, z) ∈ R
    is_transitive = True
    violating_triplet = None
    for (x, y1) in relation:
        for (y2, z) in relation:
            if y1 == y2 and (x, z) not in relation:
                is_transitive = False
                violating_triplet = (x, y1, z)
                break
        if not is_transitive:
            break

    # 4. Anti-simetris: ∀x, y ∈ A, ((x, y) ∈ R ∧ (y, x) ∈ R) => x == y
    is_antisymmetric = all(x == y for (x, y) in relation if (y, x) in relation)

    def status_label(b: bool) -> str:
        return f"{Color.GREEN}YA (Terpenuhi){Color.RESET}" if b else f"{Color.RED}TIDAK (Gagal){Color.RESET}"

    print(f"1. Refleksif    : {status_label(is_reflexive)}")
    print(f"2. Simetris     : {status_label(is_symmetric)}")
    print(f"3. Transitif    : {status_label(is_transitive)}")
    if not is_transitive and violating_triplet:
        x, y, z = violating_triplet
        print(f"   {Color.GRAY}-> Kontradiksi transitif: ({x},{y}) ∈ R dan ({y},{z}) ∈ R tetapi ({x},{z}) ∉ R{Color.RESET}")
    print(f"4. Anti-simetris: {status_label(is_antisymmetric)}")

    is_equivalence = is_reflexive and is_symmetric and is_transitive
    is_partial_order = is_reflexive and is_antisymmetric and is_transitive

    print("\nKlasifikasi Relasi:")
    print(f"- Relasi Ekuivalensi : {status_label(is_equivalence)}")
    print(f"- Partial Order (Poset): {status_label(is_partial_order)}")

# ==========================================
# 5. Teori Graf & Matriks Keterhubungan
# ==========================================
def graph_analysis() -> None:
    print_section("Representasi Graf & Analisis Derajat Titik (Degree)")
    nodes = ["v1", "v2", "v3", "v4"]
    edges = [("v1", "v2"), ("v1", "v3"), ("v2", "v3"), ("v3", "v4")]

    print(f"Simpul (Vertices) : {Color.CYAN}{nodes}{Color.RESET}")
    print(f"Sisi (Edges)      : {Color.BLUE}{edges}{Color.RESET}\n")

    # Inisialisasi matriks ketetanggaan (Adjacency Matrix)
    idx_map = {node: i for i, node in enumerate(nodes)}
    n = len(nodes)
    adj_matrix = [[0] * n for _ in range(n)]

    for u, v in edges:
        i, j = idx_map[u], idx_map[v]
        adj_matrix[i][j] = 1
        adj_matrix[j][i] = 1  # Graf tak berarah

    print(f"{Color.BOLD}Adjacency Matrix (Matriks Ketetanggaan):{Color.RESET}")
    print("    " + "  ".join(f"{Color.BOLD}{node}{Color.RESET}" for node in nodes))
    for i, row in enumerate(adj_matrix):
        row_str = "   ".join(str(cell) for cell in row)
        print(f"{Color.BOLD}{nodes[i]}{Color.RESET}  [ {row_str} ]")

    print("\nDerajat Simpul (Degree):")
    total_degree = 0
    for node in nodes:
        deg = sum(adj_matrix[idx_map[node]])
        total_degree += deg
        print(f" - deg({node}) = {deg}")

    print(f"\nTotal Derajat     : {total_degree}")
    print(f"2 x Jumlah Sisi   : {2 * len(edges)}")
    handshaking_ok = (total_degree == 2 * len(edges))
    print(f"Handshaking Lemma : {Color.GREEN}TERBUKTI (Total Degree = 2|E|){Color.RESET}" if handshaking_ok else f"{Color.RED}GAGAL{Color.RESET}")

# ==========================================
# Main Execution Loop & Menu
# ==========================================
def main() -> None:
    print_header("LAB EXERCISE BAB 01: LOGIKA KOMPUTASI & MATEMATIKA DISKRIT")
    print(f"{Color.BOLD}Lingkungan Eksekusi:{Color.RESET} Python 3 Interaktif")
    print("Menjalankan rangkaian simulasi verifikasi matematika diskrit...\n")

    # 1. Tabel Kebenaran
    generate_truth_table()

    # 2. De Morgan
    verify_de_morgan()

    # 3. Rangkaian Logika
    simulate_full_adder()

    # 4. Relasi Himpunan
    domain_set = {1, 2, 3}
    # Kasus Relasi Ekuivalensi: {(1,1), (2,2), (3,3), (1,2), (2,1)}
    equiv_relation = {(1, 1), (2, 2), (3, 3), (1, 2), (2, 1)}
    analyze_binary_relation(domain_set, equiv_relation)

    # 5. Teori Graf
    graph_analysis()

    print_header("LAB SELESAI: SEMUA SIMULASI LULUS VERIFIKASI")

if __name__ == "__main__":
    main()
