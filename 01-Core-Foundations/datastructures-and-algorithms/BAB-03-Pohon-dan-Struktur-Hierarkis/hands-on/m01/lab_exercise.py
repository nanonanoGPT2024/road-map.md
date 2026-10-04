#!/usr/bin/env python3
"""
Hands-on Lab M01: Simulasi Interaktif Binary Search Tree (BST) & Struktur Hierarkis
BAB-03: Pohon dan Struktur Hierarkis
Fokus Fondasi: Node Pointer, Properti BST, Tree Traversal (DFS & BFS), Visualisasi ASCII
"""

from collections import deque
import sys
import time

# Kode Warna ANSI Terminal
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
MAGENTA = "\033[95m"
RED = "\033[91m"
BLUE = "\033[94m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


class TreeNode:
    """Representasi satu simpul (node) dalam struktur pohon biner."""

    def __init__(self, key: int):
        self.key = key
        self.left = None
        self.right = None


class BinarySearchTree:
    """Implementasi Binary Search Tree lengkap dengan operasi traversal dan metrik hierarki."""

    def __init__(self):
        self.root = None

    def insert(self, key: int) -> bool:
        """Memasukkan key ke dalam BST sesuai properti: kiri < root <= kanan."""
        if self.root is None:
            self.root = TreeNode(key)
            return True

        curr = self.root
        while True:
            if key == curr.key:
                return False  # Menolak duplikasi untuk demo fondasi BST murni
            elif key < curr.key:
                if curr.left is None:
                    curr.left = TreeNode(key)
                    return True
                curr = curr.left
            else:
                if curr.right is None:
                    curr.right = TreeNode(key)
                    return True
                curr = curr.right

    def search(self, key: int):
        """Mencari node dan mencatat jalur/path yang dilewati."""
        curr = self.root
        path = []
        while curr:
            path.append(curr.key)
            if key == curr.key:
                return True, path
            elif key < curr.key:
                curr = curr.left
            else:
                curr = curr.right
        return False, path

    def inorder(self, node, res=None):
        """Depth-First Search (DFS) In-Order: Left -> Root -> Right (Menghasilkan urutan terurut)."""
        if res is None:
            res = []
        if node:
            self.inorder(node.left, res)
            res.append(node.key)
            self.inorder(node.right, res)
        return res

    def preorder(self, node, res=None):
        """Depth-First Search (DFS) Pre-Order: Root -> Left -> Right (Kloning/Serialisasi)."""
        if res is None:
            res = []
        if node:
            res.append(node.key)
            self.preorder(node.left, res)
            self.preorder(node.right, res)
        return res

    def postorder(self, node, res=None):
        """Depth-First Search (DFS) Post-Order: Left -> Right -> Root (Penghapusan/Evaluasi)."""
        if res is None:
            res = []
        if node:
            self.postorder(node.left, res)
            self.postorder(node.right, res)
            res.append(node.key)
        return res

    def bfs_levels(self):
        """Breadth-First Search (BFS) / Level-Order Traversal."""
        if not self.root:
            return []
        levels = []
        queue = deque([(self.root, 0)])
        while queue:
            node, lvl = queue.popleft()
            if len(levels) <= lvl:
                levels.append([])
            levels[lvl].append(node.key)
            if node.left:
                queue.append((node.left, lvl + 1))
            if node.right:
                queue.append((node.right, lvl + 1))
        return levels

    def get_height(self, node):
        """Menghitung tinggi pohon (height) dari simpul tertentu."""
        if node is None:
            return -1  # Berdasarkan konvensi edge count (tinggi leaf = 0)
        return 1 + max(self.get_height(node.left), self.get_height(node.right))

    def count_nodes(self, node):
        """Menghitung total simpul dalam pohon."""
        if node is None:
            return 0
        return 1 + self.count_nodes(node.left) + self.count_nodes(node.right)

    def count_leaves(self, node):
        """Menghitung jumlah simpul daun (leaf nodes)."""
        if node is None:
            return 0
        if node.left is None and node.right is None:
            return 1
        return self.count_leaves(node.left) + self.count_leaves(node.right)

    def display_tree(self):
        """Mencetak diagram hierarkis pohon secara visual ke terminal."""
        if not self.root:
            print(f"{YELLOW}[!] Pohon saat ini kosong.{RESET}")
            return

        lines = []

        def _build_display(node, prefix="", is_left=True, has_sibling=False):
            if node.right:
                new_prefix = prefix + ("│   " if is_left and has_sibling else "    ")
                _build_display(node.right, new_prefix, False, node.left is not None)

            branch = "└── " if not has_sibling or not is_left else "├── "
            lines.append(f"{prefix}{branch}{CYAN}{BOLD}[{node.key}]{RESET}")

            if node.left:
                new_prefix = prefix + ("│   " if not is_left and has_sibling else "    ")
                _build_display(node.left, new_prefix, True, False)

        _build_display(self.root)
        for line in lines:
            print(line)


def print_banner():
    print(f"{BLUE}{BOLD}" + "=" * 65 + f"{RESET}")
    print(f"{CYAN}{BOLD}  LAB SIMULASI INTERAKTIF: POHON & STRUKTUR HIERARKIS (BST){RESET}")
    print(f"{MAGENTA}  Modul 01 - Core Foundations: Data Structures & Algorithms{RESET}")
    print(f"{BLUE}{BOLD}" + "=" * 65 + f"{RESET}")


def interactive_cli():
    bst = BinarySearchTree()
    # Inisialisasi awal dengan data contoh standar
    sample_data = [50, 30, 70, 20, 40, 60, 80, 15, 25]
    for val in sample_data:
        bst.insert(val)

    while True:
        print_banner()
        print(f"\n{BOLD}Menu Operasi Struktur Hierarkis:{RESET}")
        print(f"  {GREEN}[1]{RESET} Visualisasi Pohon (Hierarchical ASCII Diagram)")
        print(f"  {GREEN}[2]{RESET} Sisipkan (Insert) Kunci Baru")
        print(f"  {GREEN}[3]{RESET} Pencarian (Search) Kunci & Jalur Penelusuran")
        print(f"  {GREEN}[4]{RESET} Demonstrasi Tree Traversal (In-Order, Pre-Order, Post-Order)")
        print(f"  {GREEN}[5]{RESET} Demonstrasi BFS / Level-Order Traversal")
        print(f"  {GREEN}[6]{RESET} Metrik Analisis Pohon (Tinggi, Kedalaman, Ukuran, Daun)")
        print(f"  {GREEN}[7]{RESET} Muat Ulang Contoh Data Awal (Reset Tree)")
        print(f"  {RED}[0]{RESET} Keluar (Exit)")

        pilihan = input(f"\n{YELLOW}Pilih opsi [0-7]: {RESET}").strip()

        if pilihan == "1":
            print(f"\n{MAGENTA}{BOLD}--- DIAGRAM POHON BINER ---{RESET}")
            bst.display_tree()
        elif pilihan == "2":
            try:
                raw_input = input(f"{CYAN}Masukkan nilai integer yang ingin disisipkan: {RESET}")
                val = int(raw_input.strip())
                sukses = bst.insert(val)
                if sukses:
                    print(f"{GREEN}[✓] Berhasil menyisipkan simpul {val} ke dalam hierarki.{RESET}")
                else:
                    print(f"{YELLOW}[!] Kunci {val} sudah ada dalam BST (duplikasi diabaikan).{RESET}")
            except ValueError:
                print(f"{RED}[✗] Masukan tidak valid! Harap masukkan integer.{RESET}")
        elif pilihan == "3":
            try:
                raw_input = input(f"{CYAN}Masukkan nilai integer yang ingin dicari: {RESET}")
                val = int(raw_input.strip())
                found, path = bst.search(val)
                path_str = " -> ".join([f"{CYAN}[{p}]{RESET}" for p in path])
                print(f"\n{BOLD}Jalur Pencarian (Lookup Path):{RESET} {path_str}")
                if found:
                    print(f"{GREEN}[✓] Nilai {val} DITEMUKAN setelah melewati {len(path)} langkah perbandingan.{RESET}")
                else:
                    print(f"{RED}[✗] Nilai {val} TIDAK DITEMUKAN dalam pohon hierarkis.{RESET}")
            except ValueError:
                print(f"{RED}[✗] Masukan tidak valid! Harap masukkan integer.{RESET}")
        elif pilihan == "4":
            print(f"\n{MAGENTA}{BOLD}--- HASIL TRAVERSAL DFS ---{RESET}")
            print(f"{BOLD}In-Order   (L-Root-R) :{RESET} {GREEN}{bst.inorder(bst.root)}{RESET}")
            print(f"{BOLD}Pre-Order  (Root-L-R) :{RESET} {CYAN}{bst.preorder(bst.root)}{RESET}")
            print(f"{BOLD}Post-Order (L-R-Root) :{RESET} {YELLOW}{bst.postorder(bst.root)}{RESET}")
            print(f"{DIM}Catatan: In-Order pada BST selalu menghasilkan deret terurut secara teratur.{RESET}")
        elif pilihan == "5":
            print(f"\n{MAGENTA}{BOLD}--- BREADTH-FIRST SEARCH / LEVEL-ORDER ---{RESET}")
            levels = bst.bfs_levels()
            for idx, lvl in enumerate(levels):
                print(f"{BOLD}Level {idx}:{RESET} {BLUE}{lvl}{RESET}")
        elif pilihan == "6":
            h = bst.get_height(bst.root)
            total = bst.count_nodes(bst.root)
            leaves = bst.count_leaves(bst.root)
            print(f"\n{MAGENTA}{BOLD}--- METRIK STRUKTUR POHON ---{RESET}")
            print(f"• Total Simpul (Size)       : {GREEN}{total}{RESET}")
            print(f"• Tinggi Pohon (Height)     : {CYAN}{h}{RESET} edges (tinggi root)")
            print(f"• Jumlah Daun (Leaves)      : {YELLOW}{leaves}{RESET}")
            print(f"• Status Keseimbangan Kasar : {DIM}{'Proporsional' if h >= 0 and (2**h <= total * 2) else 'Condong (Skewed)'}{RESET}")
        elif pilihan == "7":
            bst = BinarySearchTree()
            for val in [50, 30, 70, 20, 40, 60, 80, 15, 25]:
                bst.insert(val)
            print(f"{GREEN}[✓] Pohon di-reset ke konfigurasi default.{RESET}")
        elif pilihan == "0":
            print(f"\n{CYAN}Keluar dari lab simulasi. Selamat belajar!{RESET}")
            sys.exit(0)
        else:
            print(f"{RED}[!] Pilihan tidak dikenali. Masukkan angka antara 0-7.{RESET}")

        input(f"\n{DIM}Tekan [Enter] untuk melanjutkan...{RESET}")


if __name__ == "__main__":
    interactive_cli()
