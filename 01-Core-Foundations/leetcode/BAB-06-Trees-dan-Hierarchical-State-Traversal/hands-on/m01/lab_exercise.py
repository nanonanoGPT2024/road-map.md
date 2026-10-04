#!/usr/bin/env python3
"""
Hands-on Lab Exercise: BAB-06 Trees dan Hierarchical State Traversal
Simulasi visual interaktif konsep fondasi binary trees:
1. Tree Construction & ASCII Representation
2. BFS (Level-Order Traversal) dengan inspeksi antrean (Queue state)
3. DFS Traversal (Pre-Order, In-Order, Post-Order) dengan call stack tracing
4. Maximum Depth & Diameter Calculation (Bottom-Up Divide & Conquer)
5. Lowest Common Ancestor (LCA) Decision Path Tracing
"""

import sys
import collections
from typing import Optional, List, Tuple

# ANSI Escape Colors for Rich Terminal Output
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


class TreeNode:
    """Definisi node standar LeetCode untuk Binary Tree."""
    def __init__(self, val: int = 0, left: Optional['TreeNode'] = None, right: Optional['TreeNode'] = None):
        self.val = val
        self.left = left
        self.right = right


def build_tree_from_list(values: List[Optional[int]]) -> Optional[TreeNode]:
    """Membangun binary tree dari representasi level-order array (standar LeetCode)."""
    if not values or values[0] is None:
        return None

    root = TreeNode(values[0])
    queue = collections.deque([root])
    idx = 1
    n = len(values)

    while queue and idx < n:
        curr = queue.popleft()

        # Child kiri
        if idx < n and values[idx] is not None:
            curr.left = TreeNode(values[idx])
            queue.append(curr.left)
        idx += 1

        # Child kanan
        if idx < n and values[idx] is not None:
            curr.right = TreeNode(values[idx])
            queue.append(curr.right)
        idx += 1

    return root


def print_tree_structure(root: Optional[TreeNode], prefix: str = "", is_left: bool = True):
    """Mencetak visualisasi hierarki pohon ASCII dengan pewarnaan branch."""
    if root is None:
        return

    if root.right:
        print_tree_structure(root.right, prefix + ("│   " if is_left else "    "), False)

    branch_char = "└── " if is_left else "┌── "
    color = GREEN if (root.left or root.right) else CYAN
    print(f"{prefix}{YELLOW}{branch_char}{RESET}{color}{BOLD}[{root.val}]{RESET}")

    if root.left:
        print_tree_structure(root.left, prefix + ("    " if is_left else "│   "), True)


def simulate_bfs_level_order(root: Optional[TreeNode]):
    """Simulasi Level-Order Traversal dengan inspeksi antrean BFS per level."""
    print(f"\n{BOLD}{CYAN}=== [1] BFS LEVEL-ORDER TRAVERSAL (QUEUE SIMULATION) ==={RESET}")
    if not root:
        print(f"{RED}Tree kosong!{RESET}")
        return

    queue = collections.deque([root])
    level = 0
    traversal_result = []

    while queue:
        level_size = len(queue)
        current_level_vals = []
        queue_snapshot = [str(node.val) for node in queue]

        print(f"\n{BOLD}{MAGENTA}Level {level}:{RESET} (Nodes count: {level_size})")
        print(f"  {DIM}Isi Queue saat ini:{RESET} [{', '.join(queue_snapshot)}]")

        for i in range(level_size):
            node = queue.popleft()
            current_level_vals.append(node.val)
            print(f"  -> Mengunjungi Node {BOLD}{GREEN}{node.val}{RESET}", end="")

            children = []
            if node.left:
                queue.append(node.left)
                children.append(f"Left: {node.left.val}")
            if node.right:
                queue.append(node.right)
                children.append(f"Right: {node.right.val}")

            if children:
                print(f" | Enqueue ({', '.join(children)})")
            else:
                print(f" | Leaf node (tanpa anak)")

        traversal_result.append(current_level_vals)
        level += 1

    print(f"\n{BOLD}{GREEN}✓ Hasil akhir Level-Order:{RESET} {traversal_result}")


def simulate_dfs_traversals(root: Optional[TreeNode]):
    """Simulasi 3 mode DFS (Pre-Order, In-Order, Post-Order) dengan tracing call-stack."""
    print(f"\n{BOLD}{CYAN}=== [2] DFS HIERARCHICAL STATE TRAVERSALS ==={RESET}")

    preorder_res, inorder_res, postorder_res = [], [], []

    def dfs(node: Optional[TreeNode], depth: int = 0):
        if not node:
            return

        indent = "  " * depth
        # 1. PRE-ORDER VISIT
        preorder_res.append(node.val)
        print(f"{indent}{YELLOW}→ [PRE-VISIT] Entry Node ({node.val}) pada depth {depth}{RESET}")

        dfs(node.left, depth + 1)

        # 2. IN-ORDER VISIT
        inorder_res.append(node.val)
        print(f"{indent}{CYAN}↔ [IN-ORDER] Di antara Left & Right ({node.val}){RESET}")

        dfs(node.right, depth + 1)

        # 3. POST-ORDER VISIT
        postorder_res.append(node.val)
        print(f"{indent}{MAGENTA}← [POST-VISIT] Selesai Subtree Node ({node.val}) Backtrack{RESET}")

    print(f"{DIM}Memulai eksekusi rekursi DFS...{RESET}")
    dfs(root)

    print(f"\n{BOLD}Ringkasan DFS:{RESET}")
    print(f"  {YELLOW}Pre-Order  (Root -> L -> R) :{RESET} {preorder_res}")
    print(f"  {CYAN}In-Order   (L -> Root -> R) :{RESET} {inorder_res}")
    print(f"  {MAGENTA}Post-Order (L -> R -> Root) :{RESET} {postorder_res}")


def calculate_depth_and_diameter(root: Optional[TreeNode]) -> Tuple[int, int]:
    """Menghitung Max Depth dan Diameter dengan pelacakan bottom-up state."""
    print(f"\n{BOLD}{CYAN}=== [3] DIVIDE & CONQUER: MAX DEPTH & DIAMETER ==={RESET}")
    max_diameter = 0

    def get_height(node: Optional[TreeNode], depth: int = 0) -> int:
        nonlocal max_diameter
        if not node:
            return 0

        indent = "  " * depth
        left_h = get_height(node.left, depth + 1)
        right_h = get_height(node.right, depth + 1)

        local_path = left_h + right_h
        if local_path > max_diameter:
            max_diameter = local_path
            print(f"{indent}{BOLD}{RED}★ Rekor Diameter Baru di Node [{node.val}]: {left_h} + {right_h} = {local_path}{RESET}")

        curr_h = max(left_h, right_h) + 1
        print(f"{indent}Node [{node.val}] | L_Height: {left_h}, R_Height: {right_h} -> Return Height: {curr_h}")
        return curr_h

    root_depth = get_height(root)
    print(f"\n{BOLD}{GREEN}✓ Max Depth Tree   :{RESET} {root_depth}")
    print(f"{BOLD}{GREEN}✓ Diameter Tree    :{RESET} {max_diameter} edges")
    return root_depth, max_diameter


def find_lca(root: Optional[TreeNode], p: int, q: int) -> Optional[TreeNode]:
    """Mencari Lowest Common Ancestor (LCA) dari dua nilai node."""
    print(f"\n{BOLD}{CYAN}=== [4] LOWEST COMMON ANCESTOR (LCA) SIMULATION ==={RESET}")
    print(f"Mencari LCA untuk target: {BOLD}{YELLOW}p={p}{RESET} dan {BOLD}{YELLOW}q={q}{RESET}")

    def lca_helper(node: Optional[TreeNode], path: List[int]) -> Optional[TreeNode]:
        if not node:
            return None

        curr_path = path + [node.val]
        print(f"  {DIM}Mengunjungi Node {node.val} | Path: {curr_path}{RESET}")

        if node.val == p or node.val == q:
            print(f"    {GREEN}Target [{node.val}] ditemukan! Mengembalikan node ini ke caller.{RESET}")
            return node

        left = lca_helper(node.left, curr_path)
        right = lca_helper(node.right, curr_path)

        if left and right:
            print(f"    {BOLD}{MAGENTA}LCA Konvergen di Node [{node.val}] (Left: {left.val}, Right: {right.val}){RESET}")
            return node

        return left if left else right

    lca_node = lca_helper(root, [])
    if lca_node:
        print(f"\n{BOLD}{GREEN}✓ Lowest Common Ancestor:{RESET} {BOLD}{YELLOW}Node [{lca_node.val}]{RESET}")
    else:
        print(f"\n{RED}LCA tidak ditemukan.{RESET}")
    return lca_node


def interactive_menu():
    """Menu CLI interaktif untuk mengeksplorasi lab tree traversal."""
    # Pohon pengujian default: [3, 5, 1, 6, 2, 0, 8, None, None, 7, 4]
    sample_nodes = [3, 5, 1, 6, 2, 0, 8, None, None, 7, 4]
    tree = build_tree_from_list(sample_nodes)

    while True:
        print(f"\n{BG_BLUE}{WHITE}{BOLD} --- LEETCODE LAB: BAB-06 TREES & STATE TRAVERSAL --- {RESET}")
        print(f"{BOLD}Tree Aktif (Level-Order Array):{RESET} {sample_nodes}\n")
        print("Visualisasi Struktur Pohon:")
        print_tree_structure(tree)
        print("-" * 55)
        print(f"{BOLD}Pilih Demonstrasi:{RESET}")
        print(f"  {GREEN}[1]{RESET} BFS Traversal (Queue Level-Order Snapshot)")
        print(f"  {GREEN}[2]{RESET} DFS Traversal (Pre-Order, In-Order, Post-Order Call Stack)")
        print(f"  {GREEN}[3]{RESET} Hitung Max Depth & Diameter (Divide & Conquer)")
        print(f"  {GREEN}[4]{RESET} Cari Lowest Common Ancestor (LCA)")
        print(f"  {GREEN}[5]{RESET} Jalankan Seluruh Skenario (Batch Demo)")
        print(f"  {RED}[0]{RESET} Keluar")
        print("-" * 55)

        try:
            choice = input(f"{BOLD}Masukkan opsi [0-5]: {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar dari program.")
            break

        if choice == "1":
            simulate_bfs_level_order(tree)
        elif choice == "2":
            simulate_dfs_traversals(tree)
        elif choice == "3":
            calculate_depth_and_diameter(tree)
        elif choice == "4":
            find_lca(tree, 5, 4)
        elif choice == "5":
            simulate_bfs_level_order(tree)
            simulate_dfs_traversals(tree)
            calculate_depth_and_diameter(tree)
            find_lca(tree, 5, 4)
        elif choice == "0":
            print(f"{GREEN}Lab selesai. Sampai jumpa!{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak valid, silakan coba lagi.{RESET}")


if __name__ == "__main__":
    # Jika dijalankan non-interaktif (piped input/CI), jalankan mode batch demo
    if not sys.stdin.isatty():
        sample_nodes = [3, 5, 1, 6, 2, 0, 8, None, None, 7, 4]
        tree = build_tree_from_list(sample_nodes)
        print(f"{BG_BLUE}{WHITE}{BOLD} --- NON-INTERACTIVE BATCH RUN --- {RESET}")
        print_tree_structure(tree)
        simulate_bfs_level_order(tree)
        simulate_dfs_traversals(tree)
        calculate_depth_and_diameter(tree)
        find_lca(tree, 5, 4)
    else:
        interactive_menu()
