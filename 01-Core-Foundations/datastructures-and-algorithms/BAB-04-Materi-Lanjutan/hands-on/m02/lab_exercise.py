#!/usr/bin/env python3
"""
Lab Hands-on: Advanced Data Structures & Algorithms
Modul: 04.02 - Self-Balancing AVL Tree Engine vs Degenerate BST Benchmark
Deskripsi:
    Implementasi mandiri struktur data AVL Tree (Adelson-Velsky and Landis)
    dengan penyeimbangan otomatis (Rotasi LL, RR, LR, RL), visualisasi ASCII,
    serta komparasi performa O(log N) vs O(N) terhadap Unbalanced BST pada skenario
    worst-case (sequential insertion).
"""

import sys
import time
from typing import Optional, Tuple, List

# ANSI Color Codes untuk format terminal
CLR_CYAN = "\033[96m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_RED = "\033[91m"
CLR_BOLD = "\033[1m"
CLR_RESET = "\033[0m"


class AVLNode:
    """Node penyusun AVL Tree dengan pelacakan tinggi pohon."""
    def __init__(self, key: int, value: str):
        self.key = key
        self.value = value
        self.height = 1
        self.left: Optional['AVLNode'] = None
        self.right: Optional['AVLNode'] = None


class AVLTree:
    """Implementasi lengkap Self-Balancing AVL Tree dengan invariant height <= 1."""

    def __init__(self):
        self.root: Optional[AVLNode] = None
        self.rotations_count = 0

    def get_height(self, node: Optional[AVLNode]) -> int:
        """Mengembalikan tinggi sub-tree (0 jika node kosong)."""
        return node.height if node else 0

    def get_balance_factor(self, node: Optional[AVLNode]) -> int:
        """Menghitung selisih tinggi sub-tree kiri dan kanan."""
        if not node:
            return 0
        return self.get_height(node.left) - self.get_height(node.right)

    def _update_height(self, node: AVLNode) -> None:
        """Memperbarui tinggi node berdasarkan anak-anaknya."""
        node.height = 1 + max(self.get_height(node.left), self.get_height(node.right))

    def _rotate_right(self, y: AVLNode) -> AVLNode:
        """
        Rotasi Kanan (Right Rotation):
            y             x
           / \           / \
          x   T3  -->   T1  y
         / \               / \
        T1  T2            T2  T3
        """
        x = y.left
        assert x is not None
        t2 = x.right

        # Re-link pointer
        x.right = y
        y.left = t2

        # Update tinggi (y dulu karena sekarang menjadi anak dari x)
        self._update_height(y)
        self._update_height(x)

        self.rotations_count += 1
        return x

    def _rotate_left(self, x: AVLNode) -> AVLNode:
        """
        Rotasi Kiri (Left Rotation):
          x                 y
         / \               / \
        T1  y     -->     x   T3
           / \           / \
          T2  T3        T1  T2
        """
        y = x.right
        assert y is not None
        t2 = y.left

        # Re-link pointer
        y.left = x
        x.right = t2

        # Update tinggi (x dulu karena sekarang menjadi anak dari y)
        self._update_height(x)
        self._update_height(y)

        self.rotations_count += 1
        return y

    def insert(self, key: int, value: str) -> None:
        """Public API untuk menyisipkan node baru."""
        self.root = self._insert_recursive(self.root, key, value)

    def _insert_recursive(self, node: Optional[AVLNode], key: int, value: str) -> AVLNode:
        """Penyisipan rekursif dengan auto-balancing cascade."""
        if not node:
            return AVLNode(key, value)

        if key < node.key:
            node.left = self._insert_recursive(node.left, key, value)
        elif key > node.key:
            node.right = self._insert_recursive(node.right, key, value)
        else:
            node.value = value  # Update nilai jika key duplikat
            return node

        self._update_height(node)
        balance = self.get_balance_factor(node)

        # Kasus 1: Left-Left (LL) Heavy -> Rotasi Kanan
        if balance > 1 and node.left and key < node.left.key:
            return self._rotate_right(node)

        # Kasus 2: Right-Right (RR) Heavy -> Rotasi Kiri
        if balance < -1 and node.right and key > node.right.key:
            return self._rotate_left(node)

        # Kasus 3: Left-Right (LR) Heavy -> Rotasi Kiri pada anak, Kanan pada root
        if balance > 1 and node.left and key > node.left.key:
            node.left = self._rotate_left(node.left)
            return self._rotate_right(node)

        # Kasus 4: Right-Left (RL) Heavy -> Rotasi Kanan pada anak, Kiri pada root
        if balance < -1 and node.right and key < node.right.key:
            node.right = self._rotate_right(node.right)
            return self._rotate_left(node)

        return node

    def search(self, key: int) -> Tuple[Optional[str], int]:
        """Pencarian kunci O(log N) dengan instrumen penghitung langkah (hops)."""
        curr = self.root
        hops = 0
        while curr:
            hops += 1
            if key == curr.key:
                return curr.value, hops
            elif key < curr.key:
                curr = curr.left
            else:
                curr = curr.right
        return None, hops

    def display_tree(self, node: Optional[AVLNode], prefix: str = "", is_left: bool = True) -> None:
        """Visualisasi struktur pohon dalam representasi terminal berbasis ASCII."""
        if not node:
            return
        if node.right:
            self.display_tree(node.right, prefix + ("│   " if is_left else "    "), False)
        print(f"{prefix}{'└── ' if is_left else '┌── '}{CLR_CYAN}[{node.key}:{node.value}]{CLR_RESET} (h={node.height})")
        if node.left:
            self.display_tree(node.left, prefix + ("    " if is_left else "│   "), True)


class DegenerateBSTNode:
    """Node standar tanpa mekanika balancing untuk perbandingan."""
    def __init__(self, key: int, value: str):
        self.key = key
        self.value = value
        self.left: Optional['DegenerateBSTNode'] = None
        self.right: Optional['DegenerateBSTNode'] = None


class DegenerateBST:
    """Pohon BST Iteratif murni untuk menghindari batas kedalaman rekursi Python."""
    def __init__(self):
        self.root: Optional[DegenerateBSTNode] = None

    def insert(self, key: int, value: str) -> None:
        """Penyisipan iteratif tanpa penyeimbangan."""
        new_node = DegenerateBSTNode(key, value)
        if not self.root:
            self.root = new_node
            return

        curr = self.root
        while True:
            if key < curr.key:
                if not curr.left:
                    curr.left = new_node
                    break
                curr = curr.left
            elif key > curr.key:
                if not curr.right:
                    curr.right = new_node
                    break
                curr = curr.right
            else:
                curr.value = value
                break

    def search(self, key: int) -> Tuple[Optional[str], int]:
        """Pencarian sekuensial iteratif (Worst case O(N))."""
        curr = self.root
        hops = 0
        while curr:
            hops += 1
            if key == curr.key:
                return curr.value, hops
            elif key < curr.key:
                curr = curr.left
            else:
                curr = curr.right
        return None, hops


def run_demo():
    print(f"\n{CLR_BOLD}======================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}LAB WORKSHOP: AVL TREE BALANCING ENGINE & PERFORMANCE TELEMETRY{CLR_RESET}")
    print(f"{CLR_BOLD}======================================================================{CLR_RESET}\n")

    avl = AVLTree()

    # Fase 1: Demonstrasi Rotasi AVL secara bertahap
    print(f"{CLR_YELLOW}=== [TAHAP 1: Demonstrasi Auto-Balancing via Rotasi] ==={CLR_RESET}")
    elements = [
        (10, "Cluster-A"), (20, "Cluster-B"), (30, "Cluster-C"),
        (40, "Cluster-D"), (50, "Cluster-E"), (25, "Cluster-X")
    ]
    print(f"Menyisipkan entri secara berurutan: {[k for k, _ in elements]}")
    for k, v in elements:
        avl.insert(k, v)

    print(f"\nStruktur Akhir Pohon AVL setelah Re-balancing:")
    avl.display_tree(avl.root)
    print(f"Total Operasi Rotasi Internal: {CLR_GREEN}{avl.rotations_count}{CLR_RESET}")
    print(f"Tinggi Subtree Akar: {CLR_GREEN}{avl.get_height(avl.root)}{CLR_RESET} (Maksimum teoritis terikat O(log N))\n")

    # Fase 2: Benchmark Skala Besar - Skema Worst-Case (Sequential Skewed Input)
    print(f"{CLR_YELLOW}=== [TAHAP 2: Benchmark Worst-Case: AVL vs Degenerate BST] ==={CLR_RESET}")
    SAMPLE_SIZE = 3000
    print(f"Mensimulasikan beban kerja: {SAMPLE_SIZE} kunci terurut (1 .. {SAMPLE_SIZE})")

    avl_bench = AVLTree()
    bst_bench = DegenerateBST()

    # 1. Benchmark Penyisipan
    t0 = time.perf_counter()
    for i in range(1, SAMPLE_SIZE + 1):
        avl_bench.insert(i, f"payload_{i}")
    t_avl_insert = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    for i in range(1, SAMPLE_SIZE + 1):
        bst_bench.insert(i, f"payload_{i}")
    t_bst_insert = (time.perf_counter() - t0) * 1000

    # 2. Benchmark Pencarian (Worst-Case Target: elemen terakhir)
    target_key = SAMPLE_SIZE
    t0 = time.perf_counter()
    _, avl_hops = avl_bench.search(target_key)
    t_avl_search = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    _, bst_hops = bst_bench.search(target_key)
    t_bst_search = (time.perf_counter() - t0) * 1000

    # Laporan Telemetri
    print(f"\n{CLR_BOLD}{'METRIK EVALUASI':<28} | {'AVL TREE (BALANCED)':<20} | {'NAIVE BST (SKEWED)':<20}{CLR_RESET}")
    print("-" * 75)
    print(f"{'Tinggi Pohon (Height)':<28} | {CLR_GREEN}{avl_bench.get_height(avl_bench.root):<20}{CLR_RESET} | {CLR_RED}{SAMPLE_SIZE:<20}{CLR_RESET}")
    print(f"{'Waktu Ingest/Insert':<28} | {t_avl_insert:>16.2f} ms | {t_bst_insert:>16.2f} ms")
    print(f"{'Langkah Pointer (Worst Hops)':<28} | {CLR_GREEN}{avl_hops:<20}{CLR_RESET} | {CLR_RED}{bst_hops:<20}{CLR_RESET}")
    print(f"{'Latensi Search Worst-Case':<28} | {CLR_GREEN}{t_avl_search:>16.4f} ms{CLR_RESET} | {CLR_RED}{t_bst_search:>16.4f} ms{CLR_RESET}")
    print("-" * 75)

    speedup = bst_hops / avl_hops if avl_hops else 0
    print(f"\n{CLR_BOLD}ANALISIS ARSITEKTURAL:{CLR_RESET}")
    print(f"Efisiensi traversal AVL terbukti ~{CLR_GREEN}{speedup:.1f}x lebih cepat{CLR_RESET} dalam traversal node.")
    print(f"Pohon Naive BST berdegenerasi penuh menjadi Single Linked List dengan kompleksitas {CLR_RED}O(N){CLR_RESET}.")
    print(f"AVL mempertahankan struktur seimbang dengan jaminan ketat kompleksitas {CLR_GREEN}O(log N){CLR_RESET}.\n")


if __name__ == "__main__":
    run_demo()