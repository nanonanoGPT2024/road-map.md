#!/usr/bin/env python3
"""
=============================================================================
LAB EXERCISE: BAB 05 - POINTER MANIPULATION & LINKED LISTS
=============================================================================
Simulasi interaktif konsep fondasi inti manipulasi pointer pada Linked List:
1. Three-Pointer Reversal (prev, curr, next)
2. Fast & Slow Pointers (Floyd's Tortoise & Hare Cycle Detection)
3. Middle of Linked List (Tortoise & Hare Runner Technique)
4. Dummy Head Technique (Remove N-th Node from End)

Dijalankan secara mandiri dengan visualisasi grafis ANSI terminal.
=============================================================================
"""

import sys
import time
from typing import Optional, List, Tuple


# ANSI Color Codes untuk visualisasi terminal
class Colors:
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
    BG_GREEN = "\033[42m"


class ListNode:
    """Definisi Node standar LeetCode untuk Singly Linked List."""
    def __init__(self, val: int = 0, next_node: Optional['ListNode'] = None):
        self.val = val
        self.next = next_node

    def __repr__(self) -> str:
        return f"Node({self.val})"


def build_linked_list(values: List[int]) -> Optional[ListNode]:
    """Helper untuk membuat Linked List dari Python list."""
    if not values:
        return None
    head = ListNode(values[0])
    curr = head
    for v in values[1:]:
        curr.next = ListNode(v)
        curr = curr.next
    return head


def format_linked_list(head: Optional[ListNode], max_nodes: int = 20) -> str:
    """Format visualisasi linked list menjadi string: [1] -> [2] -> None."""
    elements = []
    curr = head
    count = 0
    visited = set()

    while curr and count < max_nodes:
        if id(curr) in visited:
            elements.append(f"{Colors.RED}[CYCLE: {curr.val}]{Colors.RESET}")
            break
        visited.add(id(curr))
        elements.append(f"{Colors.CYAN}[{curr.val}]{Colors.RESET}")
        curr = curr.next
        count += 1

    if curr and id(curr) not in visited:
        elements.append("...")
    elements.append(f"{Colors.WHITE}None{Colors.RESET}")
    return f" {Colors.YELLOW}->{Colors.RESET} ".join(elements)


def print_header(title: str):
    print(f"\n{Colors.BOLD}{Colors.BG_BLUE}{Colors.WHITE} === {title} === {Colors.RESET}\n")


def print_step(step_num: int, message: str):
    print(f"{Colors.YELLOW}[LANGKAH {step_num:02d}]{Colors.RESET} {message}")


# ---------------------------------------------------------------------------
# MODUL 1: In-Place Reversal (Three Pointers Technique)
# ---------------------------------------------------------------------------
def simulate_reverse_list(values: List[int], delay: float = 0.5):
    """
    Simulasi membalikkan arah pointer Linked List secara in-place.
    Menggunakan 3 pointer: prev, curr, next_node.
    Time Complexity: O(N) | Space Complexity: O(1)
    """
    print_header("SIMULASI 1: In-Place Reversal (Three Pointers)")
    head = build_linked_list(values)
    print(f"List Awal   : {format_linked_list(head)}")
    print(f"{Colors.DIM}Invarian    : prev selalu di belakang curr; pointer curr->next dibalik ke prev.{Colors.RESET}\n")

    prev = None
    curr = head
    step = 1

    while curr:
        next_temp = curr.next
        print_step(step, f"Kondisi saat ini: curr={Colors.GREEN}[{curr.val}]{Colors.RESET}, prev={Colors.MAGENTA}{[prev.val] if prev else 'None'}{Colors.RESET}, next_temp={Colors.BLUE}{[next_temp.val] if next_temp else 'None'}{Colors.RESET}")
        print(f"           Tindakan: Balik pointer -> {Colors.GREEN}[{curr.val}].next{Colors.RESET} diarahkan ke {Colors.MAGENTA}{[prev.val] if prev else 'None'}{Colors.RESET}")

        # Balik arah pointer
        curr.next = prev
        # Geser pointer prev dan curr maju satu node
        prev = curr
        curr = next_temp
        step += 1
        time.sleep(delay)

    print(f"\n{Colors.GREEN}✓ Reversal Selesai!{Colors.RESET}")
    print(f"List Baru   : {format_linked_list(prev)}")
    return prev


# ---------------------------------------------------------------------------
# MODUL 2: Floyd's Cycle Detection (Tortoise and Hare)
# ---------------------------------------------------------------------------
def simulate_cycle_detection(values: List[int], cycle_pos: int, delay: float = 0.4):
    """
    Deteksi cycle menggunakan Fast & Slow pointer.
    Fast melangkah 2x, Slow melangkah 1x. Jika ada cycle, pasti bertemu di titik tertentu.
    Time: O(N), Space: O(1)
    """
    print_header("SIMULASI 2: Floyd's Cycle Detection (Fast & Slow)")
    head = build_linked_list(values)
    if not head:
        print("List kosong.")
        return

    # Hubungkan cycle jika cycle_pos >= 0
    cycle_node = None
    tail = head
    curr = head
    idx = 0
    while curr:
        if idx == cycle_pos:
            cycle_node = curr
        if curr.next is None:
            tail = curr
            break
        curr = curr.next
        idx += 1

    if cycle_pos >= 0 and cycle_node:
        tail.next = cycle_node
        print(f"Struktur    : Dibuat siklus pada index {cycle_pos} (Node bernilai {cycle_node.val})")
    else:
        print("Struktur    : Tidak memiliki siklus (Linear List)")

    slow = head
    fast = head
    step = 1
    has_cycle = False
    meeting_node = None

    print(f"\n{Colors.DIM}Slow = 1 langkah/iterasi, Fast = 2 langkah/iterasi{Colors.RESET}\n")

    while fast and fast.next:
        slow = slow.next
        fast = fast.next.next

        print_step(step, f"Slow di {Colors.CYAN}[{slow.val}]{Colors.RESET}, Fast di {Colors.MAGENTA}[{fast.val if fast else 'None'}]{Colors.RESET}")

        if slow == fast:
            has_cycle = True
            meeting_node = slow
            print(f"\n{Colors.GREEN}>> Tabrakan terdeteksi! (Slow == Fast pada Node [{slow.val}]){Colors.RESET}")
            break

        step += 1
        time.sleep(delay)

    if not has_cycle:
        print(f"\n{Colors.RED}✗ Fast mencapai akhir (None) -> Tidak ada siklus pada Linked List.{Colors.RESET}")
        return None

    # Fase 2: Mencari titik awal cycle (Cycle Entry)
    print(f"\n{Colors.BOLD}[FASE 2] Menemukan Titik Masuk Siklus (Cycle Entry):{Colors.RESET}")
    print(f"{Colors.DIM}Reset p1 ke Head, biarkan p2 di titik temu ({meeting_node.val}). Maju 1 langkah bersamaan.{Colors.RESET}")

    p1 = head
    p2 = meeting_node
    step2 = 1
    while p1 != p2:
        print_step(step2, f"p1={Colors.CYAN}[{p1.val}]{Colors.RESET} (dari Head) vs p2={Colors.MAGENTA}[{p2.val}]{Colors.RESET} (dari Titik Temu)")
        p1 = p1.next
        p2 = p2.next
        step2 += 1
        time.sleep(delay)

    print(f"{Colors.GREEN}✓ Titik awal siklus ditemukan pada Node [{p1.val}]!{Colors.RESET}")
    return p1


# ---------------------------------------------------------------------------
# MODUL 3: Find Middle of Linked List
# ---------------------------------------------------------------------------
def simulate_middle_node(values: List[int], delay: float = 0.4):
    """
    Menemukan node tengah dengan satu lintasan (One-Pass) menggunakan Fast & Slow.
    """
    print_header("SIMULASI 3: Middle Node Finder (Runner Technique)")
    head = build_linked_list(values)
    print(f"Linked List : {format_linked_list(head)}")

    slow = head
    fast = head
    step = 1

    while fast and fast.next:
        print_step(step, f"Slow=[{slow.val}], Fast=[{fast.val}], Fast.next=[{fast.next.val}]")
        slow = slow.next
        fast = fast.next.next
        step += 1
        time.sleep(delay)

    print(f"\n{Colors.GREEN}✓ Node tengah adalah: [{slow.val}]{Colors.RESET}")
    print(f"Sub-list dari tengah: {format_linked_list(slow)}")
    return slow


# ---------------------------------------------------------------------------
# MODUL 4: Dummy Head Technique (Remove N-th Node from End)
# ---------------------------------------------------------------------------
def simulate_remove_nth_from_end(values: List[int], n: int, delay: float = 0.4):
    """
    Menghapus node ke-N dari belakang menggunakan Dummy Head dan 2 pointer
    dengan jarak N langkah.
    """
    print_header(f"SIMULASI 4: Remove {n}-th Node From End (Dummy Head)")
    head = build_linked_list(values)
    print(f"List Awal   : {format_linked_list(head)}")

    # Inisialisasi Dummy Head untuk menangani edge case penghapusan head
    dummy = ListNode(0, head)
    first = dummy
    second = dummy

    print(f"\n{Colors.DIM}Langkah 1: Berikan jarak {n} langkah antara pointer 'first' dan 'second'.{Colors.RESET}")
    for i in range(n + 1):
        first = first.next
        print_step(i + 1, f"First maju ke -> {Colors.CYAN}[{first.val if first else 'None'}]{Colors.RESET}")
        time.sleep(delay)

    print(f"\n{Colors.DIM}Langkah 2: Majukan 'first' dan 'second' bersama hingga 'first' mencapai None.{Colors.RESET}")
    step = 1
    while first:
        print_step(step, f"Second=[{second.val}], First=[{first.val}]")
        first = first.next
        second = second.next
        step += 1
        time.sleep(delay)

    # Node yang akan dihapus adalah second.next
    deleted_val = second.next.val if second.next else None
    print(f"\n{Colors.YELLOW}>> Memutus tautan: [{second.val}].next = [{second.val}].next.next{Colors.RESET}")
    print(f"{Colors.RED}>> Node [{deleted_val}] dihapus dari rantai memori.{Colors.RESET}")
    second.next = second.next.next

    result = dummy.next
    print(f"\n{Colors.GREEN}✓ Hasil Akhir: {format_linked_list(result)}{Colors.RESET}")
    return result


# ---------------------------------------------------------------------------
# AUTOMATED VERIFICATION SUITE
# ---------------------------------------------------------------------------
def run_all_self_tests():
    """Menjalankan unit test mandiri untuk memastikan kebenaran algoritma."""
    print_header("RUNNING INTERNAL ALGORITHM TEST SUITE")

    # Test 1: Reverse List
    test_1 = build_linked_list([10, 20, 30, 40])
    curr = test_1
    prev = None
    while curr:
        nxt = curr.next
        curr.next = prev
        prev = curr
        curr = nxt
    res1 = []
    c = prev
    while c:
        res1.append(c.val)
        c = c.next
    assert res1 == [40, 30, 20, 10], f"Reverse test failed: {res1}"
    print(f"{Colors.GREEN}[PASS]{Colors.RESET} Test 1: Reversal Logic (10->20->30->40 -> 40->30->20->10)")

    # Test 2: Middle of List
    test_2 = build_linked_list([1, 2, 3, 4, 5])
    s = test_2
    f = test_2
    while f and f.next:
        s = s.next
        f = f.next.next
    assert s.val == 3, f"Middle test failed: {s.val}"
    print(f"{Colors.GREEN}[PASS]{Colors.RESET} Test 2: Middle Node Odd Length (1..5 -> Middle 3)")

    # Test 3: Remove Nth Node
    dummy = ListNode(0, build_linked_list([1, 2, 3, 4, 5]))
    p1 = dummy
    p2 = dummy
    n = 2
    for _ in range(n + 1):
        p1 = p1.next
    while p1:
        p1 = p1.next
        p2 = p2.next
    p2.next = p2.next.next
    res3 = []
    c = dummy.next
    while c:
        res3.append(c.val)
        c = c.next
    assert res3 == [1, 2, 3, 5], f"Remove Nth failed: {res3}"
    print(f"{Colors.GREEN}[PASS]{Colors.RESET} Test 3: Remove 2nd from end ([1,2,3,4,5] -> [1,2,3,5])")

    print(f"\n{Colors.BOLD}{Colors.GREEN}Semua 3 Assertion Test Internal Berhasil 100%!{Colors.RESET}\n")


# ---------------------------------------------------------------------------
# INTERACTIVE CLI LOOP
# ---------------------------------------------------------------------------
def main():
    print(f"{Colors.CYAN}{Colors.BOLD}")
    print("*" * 65)
    print("   LEETCODE BAB 05: POINTER MANIPULATION & LINKED LIST LAB")
    print("*" * 65)
    print(f"{Colors.RESET}")

    # Cek jika mode batch / automated run
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        run_all_self_tests()
        simulate_reverse_list([1, 2, 3, 4, 5], delay=0.05)
        simulate_cycle_detection([3, 2, 0, -4], cycle_pos=1, delay=0.05)
        simulate_middle_node([10, 20, 30, 40, 50, 60], delay=0.05)
        simulate_remove_nth_from_end([1, 2, 3, 4, 5], n=2, delay=0.05)
        print(f"\n{Colors.GREEN}Batch execution selesai dengan sukses.{Colors.RESET}")
        return

    while True:
        print(f"{Colors.BOLD}PILIH SIMULASI POINTER:{Colors.RESET}")
        print(f"  {Colors.YELLOW}1.{Colors.RESET} Three-Pointer In-Place Reversal (LeetCode 206)")
        print(f"  {Colors.YELLOW}2.{Colors.RESET} Floyd's Cycle Detection & Cycle Entry (LeetCode 141 & 142)")
        print(f"  {Colors.YELLOW}3.{Colors.RESET} Fast & Slow Middle Node Finder (LeetCode 876)")
        print(f"  {Colors.YELLOW}4.{Colors.RESET} Dummy Head Technique: Remove N-th Node (LeetCode 19)")
        print(f"  {Colors.YELLOW}5.{Colors.RESET} Jalankan Automated Self-Test")
        print(f"  {Colors.RED}0.{Colors.RESET} Keluar")

        try:
            choice = input(f"\n{Colors.BOLD}Masukkan pilihan [0-5]: {Colors.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar program.")
            break

        if choice == "1":
            simulate_reverse_list([1, 2, 3, 4, 5], delay=0.4)
        elif choice == "2":
            simulate_cycle_detection([3, 2, 0, -4], cycle_pos=1, delay=0.4)
        elif choice == "3":
            simulate_middle_node([10, 20, 30, 40, 50, 60], delay=0.4)
        elif choice == "4":
            simulate_remove_nth_from_end([1, 2, 3, 4, 5], n=2, delay=0.4)
        elif choice == "5":
            run_all_self_tests()
        elif choice == "0":
            print(f"{Colors.GREEN}Terima kasih telah mencoba simulasi pointer linked list!{Colors.RESET}")
            break
        else:
            print(f"{Colors.RED}Pilihan tidak valid. Silakan coba lagi.{Colors.RESET}")


if __name__ == "__main__":
    main()
