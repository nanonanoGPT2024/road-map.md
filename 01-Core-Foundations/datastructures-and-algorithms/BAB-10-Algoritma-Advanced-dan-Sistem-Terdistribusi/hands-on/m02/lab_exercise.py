#!/usr/bin/env python3
"""
Lab Hands-on: Advanced Data Structures & Algorithms - Self-Balancing Trees (AVL)
Category: 01-Core-Foundations | Chapter 10: Deep Dive

Memodelkan dan mensimulasikan:
1. Algoritma Self-Balancing AVL Tree (Rotasi LL, RR, LR, RL).
2. Mekanisme Invariant Verification (Ketinggian & Faktor Keseimbangan).
3. Visualisasi ASCII Struktur Pohon Dinamis.
4. Benchmark Komparatif Kinerja: AVL Tree O(log N) vs Degenerate Naive BST O(N).
"""

import sys
import time
import random
from typing import Optional, Tuple, List

# Konfigurasi rekursi untuk pengujian degenerate tree
sys.setrecursionlimit(10000)

# Kode Warna ANSI untuk Visualisasi Terminal
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_CYAN = "\033[96m"


class AVLNode:
    """Node individual untuk struktur AVL Tree."""
    def __init__(self, key: int, value: str):
        self.key: int = key
        self.value: str = value
        self.height: int = 1
        self.left: Optional['AVLNode'] = None
        self.right: Optional['AVLNode'] = None


class AVLTree:
    """Implementasi lengkap pohon biner terurut seimbang mandiri (AVL Tree)."""

    def __init__(self):
        self.root: Optional[AVLNode] = None

    def get_height(self, node: Optional[AVLNode]) -> int:
        """Mengembalikan tinggi node (0 jika None)."""
        return node.height if node else 0

    def get_balance(self, node: Optional[AVLNode]) -> int:
        """Menghitung faktor keseimbangan (Balance Factor = Height(L) - Height(R))."""
        return self.get_height(node.left) - self.get_height(node.right) if node else 0

    def _rotate_right(self, y: AVLNode) -> AVLNode:
        """
        Rotasi Kanan (Right Rotation):
             y                               x
            / \     Rotasi Kanan (y)        / \
           x   T3   ================>      T1  y
          / \                                 / \
         T1  T2                              T2 T3
        """
        x = y.left
        assert x is not None, "Invarian AVL Gagal: Sisi kiri rotasi kanan tidak boleh None."
        t2 = x.right

        # Eksekusi pointer swap
        x.right = y
        y.left = t2

        # Update ketinggian (bottom-up)
        y.height = 1 + max(self.get_height(y.left), self.get_height(y.right))
        x.height = 1 + max(self.get_height(x.left), self.get_height(x.right))

        return x

    def _rotate_left(self, x: AVLNode) -> AVLNode:
        """
        Rotasi Kiri (Left Rotation):
             x                               y
            / \     Rotasi Kiri (x)         / \
           T1  y    ===============>       x   T3
              / \                         / \
             T2  T3                      T1 T2
        """
        y = x.right
        assert y is not None, "Invarian AVL Gagal: Sisi kanan rotasi kiri tidak boleh None."
        t2 = y.left

        # Eksekusi pointer swap
        y.left = x
        x.right = t2

        # Update ketinggian (bottom-up)
        x.height = 1 + max(self.get_height(x.left), self.get_height(x.right))
        y.height = 1 + max(self.get_height(y.left), self.get_height(y.right))

        return y

    def insert(self, key: int, value: str) -> None:
        """Membungkus fungsi rekursif insert ke root."""
        self.root = self._insert_node(self.root, key, value)

    def _insert_node(self, node: Optional[AVLNode], key: int, value: str) -> AVLNode:
        """Penyisipan rekursif dengan rebalancing otomatis."""
        # 1. Standar BST Insertion
        if not node:
            return AVLNode(key, value)

        if key < node.key:
            node.left = self._insert_node(node.left, key, value)
        elif key > node.key:
            node.right = self._insert_node(node.right, key, value)
        else:
            # Update data jika key duplikat
            node.value = value
            return node

        # 2. Update Ketinggian Node Leluhur
        node.height = 1 + max(self.get_height(node.left), self.get_height(node.right))

        # 3. Hitung Balance Factor untuk mendeteksi anomali struktur
        balance = self.get_balance(node)

        # 4. Tangani 4 Kasus Pelanggaran Invarian AVL:
        # Kasus 1: Left-Left (LL)
        if balance > 1 and key < node.left.key:
            return self._rotate_right(node)

        # Kasus 2: Right-Right (RR)
        if balance < -1 and key > node.right.key:
            return self._rotate_left(node)

        # Kasus 3: Left-Right (LR)
        if balance > 1 and key > node.left.key:
            node.left = self._rotate_left(node.left)
            return self._rotate_right(node)

        # Kasus 4: Right-Left (RL)
        if balance < -1 and key < node.right.key:
            node.right = self._rotate_right(node.right)
            return self._rotate_left(node)

        return node

    def delete(self, key: int) -> None:
        """Membungkus fungsi rekursif delete pada root."""
        self.root = self._delete_node(self.root, key)

    def _get_min_value_node(self, node: AVLNode) -> AVLNode:
        """Mencari node suksesor inorder (nilai terkecil di subtree kanan)."""
        curr = node
        while curr.left:
            curr = curr.left
        return curr

    def _delete_node(self, node: Optional[AVLNode], key: int) -> Optional[AVLNode]:
        """Penghapusan rekursif dan penyeimbangan kembali pohon."""
        if not node:
            return None

        # 1. Standar BST Delete Traversal
        if key < node.key:
            node.left = self._delete_node(node.left, key)
        elif key > node.key:
            node.right = self._delete_node(node.right, key)
        else:
            # Node ditemukan: Eksekusi penghapusan
            if not node.left or not node.right:
                temp = node.left if node.left else node.right
                node = None if not temp else temp
            else:
                # Memiliki 2 anak: Ganti dengan inorder successor
                temp = self._get_min_value_node(node.right)
                node.key = temp.key
                node.value = temp.value
                node.right = self._delete_node(node.right, temp.key)

        if not node:
            return None

        # 2. Update ketinggian
        node.height = 1 + max(self.get_height(node.left), self.get_height(node.right))

        # 3. Hitung balance factor
        balance = self.get_balance(node)

        # 4. Rebalancing setelah penghapusan
        if balance > 1 and self.get_balance(node.left) >= 0:
            return self._rotate_right(node)

        if balance > 1 and self.get_balance(node.left) < 0:
            node.left = self._rotate_left(node.left)
            return self._rotate_right(node)

        if balance < -1 and self.get_balance(node.right) <= 0:
            return self._rotate_left(node)

        if balance < -1 and self.get_balance(node.right) > 0:
            node.right = self._rotate_right(node.right)
            return self._rotate_left(node)

        return node

    def search(self, key: int) -> Optional[str]:
        """Pencarian kunci dengan kompleksitas O(log N)."""
        curr = self.root
        while curr:
            if key == curr.key:
                return curr.value
            curr = curr.left if key < curr.key else curr.right
        return None

    def verify_invariants(self, node: Optional[AVLNode]) -> Tuple[bool, str]:
        """Validasi ketat invarian AVL: BST Property dan |BF| <= 1."""
        if not node:
            return True, "Tree kosong atau leaf tercapai."

        balance = self.get_balance(node)
        if abs(balance) > 1:
            return False, f"Invarian Balance Factor dilanggar pada Node [{node.key}]: BF={balance}"

        # Validasi properti BST
        if node.left and node.left.key >= node.key:
            return False, f"Invarian BST dilanggar: Node Kiri [{node.left.key}] >= Parent [{node.key}]"
        if node.right and node.right.key <= node.key:
            return False, f"Invarian BST dilanggar: Node Kanan [{node.right.key}] <= Parent [{node.key}]"

        left_valid, msg = self.verify_invariants(node.left)
        if not left_valid:
            return False, msg

        return self.verify_invariants(node.right)

    def print_ascii_tree(self, node: Optional[AVLNode], prefix: str = "", is_left: bool = True) -> None:
        """Visualizer pohon berbasis ASCII untuk representasi struktur internal."""
        if not node:
            return

        if node.right:
            self.print_ascii_tree(node.right, prefix + ("│   " if is_left else "    "), False)

        connector = "└── " if is_left else "┌── "
        bf = self.get_balance(node)
        bf_color = CLR_GREEN if abs(bf) <= 1 else CLR_RED
        print(f"{prefix}{connector}{CLR_BOLD}[{node.key}:{node.value}]{CLR_RESET} (h:{node.height}, bf:{bf_color}{bf}{CLR_RESET})")

        if node.left:
            self.print_ascii_tree(node.left, prefix + ("    " if is_left else "│   "), True)


class NaiveBSTNode:
    """Node untuk Binary Search Tree naif tanpa balancing."""
    def __init__(self, key: int, value: str):
        self.key: int = key
        self.value: str = value
        self.left: Optional['NaiveBSTNode'] = None
        self.right: Optional['NaiveBSTNode'] = None


class NaiveBST:
    """Implementasi BST naif (rentan mengalami degenerasi menjadi Linked List)."""
    def __init__(self):
        self.root: Optional[NaiveBSTNode] = None

    def insert(self, key: int, value: str) -> None:
        new_node = NaiveBSTNode(key, value)
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

    def search(self, key: int) -> Optional[str]:
        curr = self.root
        while curr:
            if key == curr.key:
                return curr.value
            curr = curr.left if key < curr.key else curr.right
        return None


def run_laboratory_exercise():
    """Eksekusi skenario laboratorium hands-on."""
    print(f"\n{CLR_BOLD}{CLR_CYAN}=== LAB: SELF-BALANCING AVL TREE vs NAIVE BST BENCHMARK ==={CLR_RESET}\n")

    avl = AVLTree()
    test_keys = [10, 20, 30, 40, 50, 25, 5, 15]

    print(f"{CLR_YELLOW}[1] Menguji Rotasi Dinamis AVL dengan Menyisipkan Data Bertahap...{CLR_RESET}")
    for k in test_keys:
        val = f"payload_{k}"
        avl.insert(k, val)
        print(f" -> Menyisipkan Key [{k:2d}] ... Balance Root: {avl.get_balance(avl.root)} | Height: {avl.get_height(avl.root)}")

    print(f"\n{CLR_CYAN}[2] Visualisasi Struktur Internal AVL Tree Setelah Self-Balancing:{CLR_RESET}")
    avl.print_ascii_tree(avl.root)

    # Validasi Invarian
    valid, message = avl.verify_invariants(avl.root)
    status_color = CLR_GREEN if valid else CLR_RED
    print(f"\n{CLR_BOLD}Pengecekan Invarian AVL:{CLR_RESET} {status_color}{message}{CLR_RESET}")

    # Uji Kasus Penghapusan Node
    del_key = 30
    print(f"\n{CLR_YELLOW}[3] Menguji Penghapusan Node dengan 2 Anak (Key: {del_key})...{CLR_RESET}")
    avl.delete(del_key)
    print(f"Struktur pohon setelah Key [{del_key}] dihapus:")
    avl.print_ascii_tree(avl.root)

    valid, message = avl.verify_invariants(avl.root)
    print(f"{CLR_BOLD}Pengecekan Invarian Pasca-Penghapusan:{CLR_RESET} {CLR_GREEN if valid else CLR_RED}{message}{CLR_RESET}")

    # 4. Stress Test & Benchmark Komparatif (Degenerate Scenario)
    print(f"\n{CLR_CYAN}[4] Memulai Benchmark: AVL Tree vs Naive BST (Worst-Case Sorted Input){CLR_RESET}")
    dataset_size = 2000
    sorted_dataset = list(range(1, dataset_size + 1))
    random_queries = [random.randint(1, dataset_size) for _ in range(5000)]

    print(f"Ukuran Dataset        : {CLR_BOLD}{dataset_size}{CLR_RESET} entri berurutan (Strictly Increasing)")
    print(f"Total Operasi Cari    : {CLR_BOLD}{len(random_queries)}{CLR_RESET} queries acak")

    # Inisialisasi struktur
    naive_tree = NaiveBST()
    avl_benchmark_tree = AVLTree()

    # Insertion Benchmark - Naive BST
    t0 = time.perf_counter()
    for k in sorted_dataset:
        naive_tree.insert(k, f"val_{k}")
    t_insert_naive = time.perf_counter() - t0

    # Insertion Benchmark - AVL Tree
    t0 = time.perf_counter()
    for k in sorted_dataset:
        avl_benchmark_tree.insert(k, f"val_{k}")
    t_insert_avl = time.perf_counter() - t0

    # Search Benchmark - Naive BST (Harus menelusuri O(N) linear-like degenerate tree)
    t0 = time.perf_counter()
    for q in random_queries:
        naive_tree.search(q)
    t_search_naive = time.perf_counter() - t0

    # Search Benchmark - AVL Tree (Menjamin kedalaman O(log N))
    t0 = time.perf_counter()
    for q in random_queries:
        avl_benchmark_tree.search(q)
    t_search_avl = time.perf_counter() - t0

    # Tampilkan Hasil Benchmark
    print(f"\n{CLR_BOLD}--- HASIL PENGUJIAN PERFORMA ---{CLR_RESET}")
    print(f"{'Metrik':<28} | {'Naive BST (Degenerate)':<22} | {'AVL Tree (Balanced)':<20}")
    print("-" * 76)
    print(f"{'Tinggi Pohon Maksimal':<28} | {dataset_size:<22} | {avl_benchmark_tree.get_height(avl_benchmark_tree.root):<20}")
    print(f"{'Durasi Insert (' + str(dataset_size) + ' items)':<28} | {t_insert_naive*1000:>18.3f} ms | {t_insert_avl*1000:>16.3f} ms")
    print(f"{'Durasi Search (' + str(len(random_queries)) + ' queries)':<28} | {t_search_naive*1000:>18.3f} ms | {t_search_avl*1000:>16.3f} ms")

    speedup = t_search_naive / t_search_avl if t_search_avl > 0 else float('inf')
    print("-" * 76)
    print(f"{CLR_GREEN}{CLR_BOLD}Akselerasi Pencarian AVL Tree: {speedup:.2f}x Lebih Cepat dibanding Naive BST!{CLR_RESET}\n")


if __name__ == "__main__":
    run_laboratory_exercise()