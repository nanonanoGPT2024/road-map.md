#!/usr/bin/env python3
"""
Hands-on Lab Exercise: BAB 10 - Advanced Structures & Specialized Paradigms
Topik: Segment Tree, Binary Indexed Tree (Fenwick), Trie, dan Disjoint Set Union (DSU).
Fitur: Simulasi interaktif berbasis terminal dengan format visual ANSI.
"""

import sys
import time
from typing import List, Optional, Dict, Any


# --- ANSI Color Codes untuk Visualisasi Terminal ---
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"


def header(title: str) -> None:
    print(f"\n{Colors.BG_BLUE}{Colors.WHITE}{Colors.BOLD} [LAB] {title.upper()} {Colors.RESET}")
    print(f"{Colors.CYAN}{'=' * 65}{Colors.RESET}")


# ==============================================================================
# 1. SEGMENT TREE (Range Sum Query & Point Update)
# ==============================================================================
class SegmentTree:
    def __init__(self, data: List[int]):
        self.n = len(data)
        self.data = data
        self.tree = [0] * (4 * self.n)
        if self.n > 0:
            self._build(0, 0, self.n - 1)

    def _build(self, node: int, start: int, end: int) -> None:
        if start == end:
            self.tree[node] = self.data[start]
            return
        mid = (start + end) // 2
        left_child = 2 * node + 1
        right_child = 2 * node + 2
        self._build(left_child, start, mid)
        self._build(right_child, mid + 1, end)
        self.tree[node] = self.tree[left_child] + self.tree[right_child]

    def update(self, idx: int, val: int) -> None:
        def _update(node: int, start: int, end: int, idx: int, val: int) -> None:
            if start == end:
                self.data[idx] = val
                self.tree[node] = val
                return
            mid = (start + end) // 2
            left_child = 2 * node + 1
            right_child = 2 * node + 2
            if start <= idx <= mid:
                _update(left_child, start, mid, idx, val)
            else:
                _update(right_child, mid + 1, end, idx, val)
            self.tree[node] = self.tree[left_child] + self.tree[right_child]

        _update(0, 0, self.n - 1, idx, val)

    def query(self, L: int, R: int) -> int:
        def _query(node: int, start: int, end: int, L: int, R: int) -> int:
            if R < start or end < L:
                return 0
            if L <= start and end <= R:
                return self.tree[node]
            mid = (start + end) // 2
            left_sum = _query(2 * node + 1, start, mid, L, R)
            right_sum = _query(2 * node + 2, mid + 1, end, L, R)
            return left_sum + right_sum

        return _query(0, 0, self.n - 1, L, R)


# ==============================================================================
# 2. DISJOINT SET UNION (DSU / UNION-FIND WITH PATH COMPRESSION & RANK)
# ==============================================================================
class DSU:
    def __init__(self, size: int):
        self.parent = list(range(size))
        self.rank = [0] * size
        self.components = size

    def find(self, i: int) -> int:
        if self.parent[i] == i:
            return i
        self.parent[i] = self.find(self.parent[i])  # Path compression
        return self.parent[i]

    def union(self, i: int, j: int) -> bool:
        root_i = self.find(i)
        root_j = self.find(j)
        if root_i != root_j:
            # Union by rank
            if self.rank[root_i] < self.rank[root_j]:
                self.parent[root_i] = root_j
            elif self.rank[root_i] > self.rank[root_j]:
                self.parent[root_j] = root_i
            else:
                self.parent[root_j] = root_i
                self.rank[root_i] += 1
            self.components -= 1
            return True
        return False


# ==============================================================================
# 3. PREFIX TREE (TRIE) DENGAN AUTOCOMPLETE & WILDCARD
# ==============================================================================
class TrieNode:
    def __init__(self):
        self.children: Dict[str, "TrieNode"] = {}
        self.is_end_of_word: bool = False


class Trie:
    def __init__(self):
        self.root = TrieNode()

    def insert(self, word: str) -> None:
        curr = self.root
        for char in word:
            if char not in curr.children:
                curr.children[char] = TrieNode()
            curr = curr.children[char]
        curr.is_end_of_word = True

    def search(self, word: str) -> bool:
        curr = self.root
        for char in word:
            if char not in curr.children:
                return False
            curr = curr.children[char]
        return curr.is_end_of_word

    def starts_with(self, prefix: str) -> List[str]:
        curr = self.root
        for char in prefix:
            if char not in curr.children:
                return []
            curr = curr.children[char]

        results: List[str] = []

        def dfs(node: TrieNode, path: str):
            if node.is_end_of_word:
                results.append(path)
            for ch, nxt in sorted(node.children.items()):
                dfs(nxt, path + ch)

        dfs(curr, prefix)
        return results


# ==============================================================================
# 4. SIMULASI INTERAKTIF & VISUALISASI
# ==============================================================================
def demo_segment_tree():
    header("Simulasi Segment Tree: Range Query & Point Update (O(log N))")
    raw = [1, 3, 5, 7, 9, 11]
    print(f"{Colors.YELLOW}Array Awal:{Colors.RESET} {raw}")
    st = SegmentTree(raw)

    print(f"\n{Colors.CYAN}[Query 1]{Colors.RESET} Sum range [1..3] (elemen: {raw[1]} + {raw[2]} + {raw[3]}):")
    res1 = st.query(1, 3)
    print(f" -> Hasil Query Segment Tree: {Colors.GREEN}{Colors.BOLD}{res1}{Colors.RESET}")

    print(f"\n{Colors.CYAN}[Update]{Colors.RESET} Mengubah indeks 2 dari {raw[2]} menjadi 10...")
    st.update(2, 10)
    print(f"{Colors.YELLOW}Array Baru:{Colors.RESET} {st.data}")

    print(f"\n{Colors.CYAN}[Query 2]{Colors.RESET} Sum range [1..3] pasca-update (elemen: {st.data[1]} + {st.data[2]} + {st.data[3]}):")
    res2 = st.query(1, 3)
    print(f" -> Hasil Query Segment Tree: {Colors.GREEN}{Colors.BOLD}{res2}{Colors.RESET}")


def demo_dsu():
    header("Simulasi Disjoint Set Union (DSU / Union-Find): Deteksi Konektivitas")
    n = 6
    dsu = DSU(n)
    print(f"{Colors.YELLOW}Jumlah node mandiri awal:{Colors.RESET} {n} (Komponen terpisah: {dsu.components})")

    edges = [(0, 1), (1, 2), (3, 4), (4, 5)]
    for u, v in edges:
        dsu.union(u, v)
        print(f"  {Colors.BLUE}+ Hubungkan edge ({u} <-> {v}){Colors.RESET} -> Komponen aktif: {dsu.components}")

    print(f"\n{Colors.CYAN}[Uji Konektivitas]{Colors.RESET}")
    tests = [(0, 2), (2, 3), (3, 5)]
    for u, v in tests:
        conn = dsu.find(u) == dsu.find(v)
        tag = f"{Colors.GREEN}TERHUBUNG{Colors.RESET}" if conn else f"{Colors.RED}TERPISAH{Colors.RESET}"
        print(f"  Apakah Node {u} dan Node {v} berada dalam satu set? -> {tag}")


def demo_trie():
    header("Simulasi Prefix Tree (Trie): Dictionary & Autocomplete")
    trie = Trie()
    vocab = ["algo", "algorithm", "algebra", "alien", "allocate", "binary", "bitmask"]
    for word in vocab:
        trie.insert(word)

    print(f"{Colors.YELLOW}Kosa Kata Terdaftar:{Colors.RESET} {', '.join(vocab)}")
    queries = ["algo", "alg", "bit", "tree"]

    print(f"\n{Colors.CYAN}[Pencarian Eksak (Exact Search)]{Colors.RESET}")
    for q in queries:
        found = trie.search(q)
        status = f"{Colors.GREEN}DITEMUKAN{Colors.RESET}" if found else f"{Colors.RED}TIDAK ADA{Colors.RESET}"
        print(f"  Search '{q}': {status}")

    print(f"\n{Colors.CYAN}[Autocomplete Suggester (Prefix Search)]{Colors.RESET}")
    for prefix in ["al", "bi", "z"]:
        matches = trie.starts_with(prefix)
        print(f"  Prefix '{prefix}*' -> {Colors.MAGENTA}{matches}{Colors.RESET}")


def run_interactive_menu():
    while True:
        print(f"\n{Colors.BOLD}{Colors.WHITE}=== BAB 10 LAB EXERCISE MENU INTERAKTIF ==={Colors.RESET}")
        print(f"{Colors.CYAN}1.{Colors.RESET} Jalankan Simulasi Segment Tree")
        print(f"{Colors.CYAN}2.{Colors.RESET} Jalankan Simulasi Disjoint Set Union (DSU)")
        print(f"{Colors.CYAN}3.{Colors.RESET} Jalankan Simulasi Prefix Tree (Trie)")
        print(f"{Colors.CYAN}4.{Colors.RESET} Jalankan SEMUA Simulasi Beruntun")
        print(f"{Colors.RED}0.{Colors.RESET} Keluar")
        
        choice = input(f"\n{Colors.YELLOW}Pilih opsi [0-4]: {Colors.RESET}").strip()
        if choice == "1":
            demo_segment_tree()
        elif choice == "2":
            demo_dsu()
        elif choice == "3":
            demo_trie()
        elif choice == "4":
            demo_segment_tree()
            demo_dsu()
            demo_trie()
        elif choice == "0":
            print(f"{Colors.GREEN}Lab selesai. Sampai jumpa!{Colors.RESET}")
            break
        else:
            print(f"{Colors.RED}Pilihan tidak valid. Silakan coba lagi.{Colors.RESET}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        demo_segment_tree()
        demo_dsu()
        demo_trie()
    else:
        # Jika dijalankan tanpa parameter interaktif di lingkungan non-tty
        if not sys.stdin.isatty():
            demo_segment_tree()
            demo_dsu()
            demo_trie()
        else:
            run_interactive_menu()
