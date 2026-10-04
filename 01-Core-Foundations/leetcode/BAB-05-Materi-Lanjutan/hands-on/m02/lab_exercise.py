#!/usr/bin/env python3
"""
Lab Hands-on: Pointer Manipulation & Linked Lists (Deep Dive)
Kategori: 01-Core-Foundations | Bab 05 - Modul 02
Topik: LeetCode Advanced Pointer Mechanics & Real-World In-Memory Caching

Materi Inti:
1. Fast & Slow Pointers (Floyd's Cycle-Finding & Entry Detection - LeetCode 142)
2. In-Place Reversal of Nodes in k-Group (LeetCode 25 - Strict Pointer Juggling)
3. High-Performance Doubly Linked List LRU Cache (LeetCode 146) vs Naive Array Cache Benchmark
"""

import time
import sys
from typing import Optional, Tuple, Dict, Any

# ============================================================================
# ANSI Color Palettes for Terminal Diagnostics
# ============================================================================
class Color:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    CYAN    = "\033[96m"
    MAGENTA = "\033[95m"


# ============================================================================
# Node Definitions
# ============================================================================
class ListNode:
    """Singly Linked List Node."""
    def __init__(self, val: int = 0, next: Optional['ListNode'] = None):
        self.val = val
        self.next = next

    def __repr__(self) -> str:
        return f"ListNode({self.val})"


class DListNode:
    """Doubly Linked List Node for LRU implementation."""
    def __init__(self, key: int = 0, val: int = 0):
        self.key = key
        self.val = val
        self.prev: Optional['DListNode'] = None
        self.next: Optional['DListNode'] = None


# ============================================================================
# Core Algorithmic Implementations
# ============================================================================
def build_linked_list(arr: list[int]) -> Optional[ListNode]:
    """Helper untuk membangun linked list dari array."""
    dummy = ListNode(0)
    curr = dummy
    for x in arr:
        curr.next = ListNode(x)
        curr = curr.next
    return dummy.next


def serialize_linked_list(head: Optional[ListNode], max_nodes: int = 20) -> str:
    """Serialisasi linked list ke representasi visual string."""
    vals = []
    curr = head
    count = 0
    while curr and count < max_nodes:
        vals.append(str(curr.val))
        curr = curr.next
        count += 1
    if curr:
        vals.append("... (loop/truncated)")
    return " -> ".join(vals) if vals else "EMPTY"


def detect_cycle_floyd(head: Optional[ListNode]) -> Tuple[bool, Optional[ListNode]]:
    """
    Algoritma Floyd's Tortoise and Hare (LeetCode 142).
    - Phase 1: Deteksi apakah terdapat siklus menggunakan dua pointer berkecepatan 1x dan 2x.
    - Phase 2: Jika siklus terdeteksi, reset satu pointer ke head, jalankan keduanya
      dengan kecepatan 1x. Titik temu keduanya dijamin matematis adalah titik awal siklus.
    """
    if not head or not head.next:
        return False, None

    slow = head
    fast = head

    # Fase 1: Identifikasi collision point
    has_cycle = False
    while fast and fast.next:
        slow = slow.next
        fast = fast.next.next
        if slow == fast:
            has_cycle = True
            break

    if not has_cycle:
        return False, None

    # Fase 2: Temukan simpul awal siklus
    ptr1 = head
    ptr2 = slow
    while ptr1 != ptr2:
        ptr1 = ptr1.next
        ptr2 = ptr2.next

    return True, ptr1


def reverse_k_group(head: Optional[ListNode], k: int) -> Optional[ListNode]:
    """
    Reverse Nodes in k-Group (LeetCode 25).
    Membalik sub-list setiap kelipatan k node secara in-place O(1) space.
    Sisa node (< k) dipertahankan dalam urutan aslinya.
    """
    if not head or k <= 1:
        return head

    dummy = ListNode(0, head)
    group_prev = dummy

    while True:
        # Cek apakah masih ada k node yang tersisa
        kth = group_prev
        for _ in range(k):
            kth = kth.next
            if not kth:
                return dummy.next

        group_next = kth.next

        # In-place reversal k node
        prev, curr = kth.next, group_prev.next
        while curr != group_next:
            tmp = curr.next
            curr.next = prev
            prev = curr
            curr = tmp

        # Hubungkan pointer group sebelum dan sesudah
        tmp_head = group_prev.next
        group_prev.next = kth
        group_prev = tmp_head


# ============================================================================
# LRU Cache Engine (Doubly Linked List + Hash Map)
# ============================================================================
class LRUCache:
    """
    LRU Cache O(1) get & put menggunakan Sentinel Head & Tail
    serta Hash Map untuk direct node dereferencing.
    """
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.cache: Dict[int, DListNode] = {}
        # Sentinel dummy nodes
        self.head = DListNode()
        self.tail = DListNode()
        self.head.next = self.tail
        self.tail.prev = self.head

    def _remove(self, node: DListNode) -> None:
        """Lepaskan node dari doubly linked list."""
        prev_node = node.prev
        next_node = node.next
        prev_node.next = next_node
        next_node.prev = prev_node

    def _add_to_front(self, node: DListNode) -> None:
        """Sisipkan node tepat setelah dummy head (Most Recently Used)."""
        node.next = self.head.next
        node.prev = self.head
        self.head.next.prev = node
        self.head.next = node

    def get(self, key: int) -> int:
        if key not in self.cache:
            return -1
        node = self.cache[key]
        self._remove(node)
        self._add_to_front(node)
        return node.val

    def put(self, key: int, value: int) -> None:
        if key in self.cache:
            self._remove(self.cache[key])
        node = DListNode(key, value)
        self._add_to_front(node)
        self.cache[key] = node

        if len(self.cache) > self.capacity:
            # Evict Least Recently Used (node sebelum tail)
            lru = self.tail.prev
            self._remove(lru)
            del self.cache[lru.key]


class NaiveArrayLRUCache:
    """Implementasi Naive LRU berbasis array O(N) untuk perbandingan benchmark."""
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.order: list[int] = []
        self.store: Dict[int, int] = {}

    def get(self, key: int) -> int:
        if key not in self.store:
            return -1
        self.order.remove(key)  # O(N)
        self.order.append(key)
        return self.store[key]

    def put(self, key: int, value: int) -> None:
        if key in self.store:
            self.order.remove(key)  # O(N)
        elif len(self.order) >= self.capacity:
            lru_key = self.order.pop(0)  # O(N)
            del self.store[lru_key]
        self.store[key] = value
        self.order.append(key)


# ============================================================================
# Main Diagnostic & Verification Runner
# ============================================================================
def run_lab() -> None:
    print(f"{Color.CYAN}{Color.BOLD}======================================================================{Color.RESET}")
    print(f"{Color.CYAN}{Color.BOLD}   SYSTEMS LAB: ADVANCED POINTER MANIPULATION & LINKED DATA STRUCTURES {Color.RESET}")
    print(f"{Color.CYAN}{Color.BOLD}======================================================================{Color.RESET}\n")

    # ------------------------------------------------------------------------
    # Task 1: Floyd's Cycle Detection Proof
    # ------------------------------------------------------------------------
    print(f"{Color.YELLOW}[TASK 1] Floyd's Cycle Detection & Origin Resolution (LeetCode 142){Color.RESET}")
    nodes_val = [10, 20, 30, 40, 50, 60, 70]
    head = build_linked_list(nodes_val)

    # Buat siklus buatan: node(70) diarahkan kembali ke node(30)
    curr = head
    cycle_entry = None
    tail = None
    while curr:
        if curr.val == 30:
            cycle_entry = curr
        if not curr.next:
            tail = curr
            break
        curr = curr.next

    tail.next = cycle_entry  # Mutasi pointer: buat loop
    print(f"  Topology   : 10 -> 20 -> [30] -> 40 -> 50 -> 60 -> 70 -> loop kembali ke [30]")

    has_cycle, detected_entry = detect_cycle_floyd(head)
    if has_cycle and detected_entry and detected_entry.val == 30:
        print(f"  Status     : {Color.GREEN}SUCCESS{Color.RESET}")
        print(f"  Deteksi    : Loop ditemukan, entry address node value = {Color.BOLD}{detected_entry.val}{Color.RESET}\n")
    else:
        print(f"  Status     : {Color.RED}FAILURE - Siklus gagal dideteksi{Color.RESET}\n")

    # Break cycle to allow garbage collection
    tail.next = None

    # ------------------------------------------------------------------------
    # Task 2: In-Place k-Group Reversal
    # ------------------------------------------------------------------------
    print(f"{Color.YELLOW}[TASK 2] In-Place Reversal of Nodes in k-Group (LeetCode 25){Color.RESET}")
    input_arr = [1, 2, 3, 4, 5, 6, 7, 8]
    k = 3
    test_list = build_linked_list(input_arr)
    print(f"  Input List : {serialize_linked_list(test_list)}")
    print(f"  Batch (k)  : {k}")

    reversed_head = reverse_k_group(test_list, k)
    output_str = serialize_linked_list(reversed_head)
    expected_str = "3 -> 2 -> 1 -> 6 -> 5 -> 4 -> 7 -> 8"
    print(f"  Output List: {output_str}")

    if output_str == expected_str:
        print(f"  Status     : {Color.GREEN}PASSED (Pointer exchange preserves non-k leftovers){Color.RESET}\n")
    else:
        print(f"  Status     : {Color.RED}FAILED (Mismatched output){Color.RESET}\n")

    # ------------------------------------------------------------------------
    # Task 3: Dual-Pointer LRU Cache Benchmark vs Naive List
    # ------------------------------------------------------------------------
    print(f"{Color.YELLOW}[TASK 3] High-Throughput LRU Cache Benchmark (O(1) vs O(N)){Color.RESET}")
    capacity = 1000
    operations = 40000

    print(f"  Kapasitas  : {capacity} slot")
    print(f"  Beban Uji  : {operations} read/write interleaved operations")

    # Benchmarking O(1) Doubly Linked List LRU
    lru_fast = LRUCache(capacity)
    t0 = time.perf_counter()
    for i in range(operations):
        lru_fast.put(i % 2000, i)
        if i % 2 == 0:
            _ = lru_fast.get((i // 2) % 2000)
    t1 = time.perf_counter()
    duration_fast = (t1 - t0) * 1000.0

    # Benchmarking O(N) Naive Array LRU
    lru_naive = NaiveArrayLRUCache(capacity)
    t2 = time.perf_counter()
    for i in range(operations):
        lru_naive.put(i % 2000, i)
        if i % 2 == 0:
            _ = lru_naive.get((i // 2) % 2000)
    t3 = time.perf_counter()
    duration_naive = (t3 - t2) * 1000.0

    speedup = duration_naive / duration_fast if duration_fast > 0 else 0

    print(f"  Hasil Run  :")
    print(f"    - Doubly Linked List LRU {Color.GREEN}O(1){Color.RESET} : {duration_fast:8.2f} ms")
    print(f"    - Naive List Array LRU  {Color.RED}O(N){Color.RESET} : {duration_naive:8.2f} ms")
    print(f"  Efisiensi  : {Color.GREEN}{Color.BOLD}{speedup:.2f}x Lebih Cepat{Color.RESET} dengan isolasi pointer mutlak!\n")

    print(f"{Color.CYAN}Diagnostic complete: All pointer manipulation test suites executed cleanly.{Color.RESET}")


if __name__ == "__main__":
    run_lab()