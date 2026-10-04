#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Fondasi Struktur Data Linear
Topik: Dynamic Array, Singly Linked List, Stack (LIFO), dan Circular Queue (FIFO)
BAB-02: Struktur Data Linear
"""

import sys
import time
from typing import Any, Optional, List

# ANSI Color Codes
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
BG_GREEN = "\033[42m"


# ==========================================
# 1. DYNAMIC ARRAY SIMULATOR
# ==========================================
class DynamicArraySimulator:
    def __init__(self, initial_capacity: int = 2):
        self.capacity: int = initial_capacity
        self.size: int = 0
        self.array: List[Optional[Any]] = [None] * self.capacity

    def append(self, val: Any) -> None:
        print(f"\n{CYAN}--- Operasi Append: {BOLD}{val}{RESET} ---")
        if self.size == self.capacity:
            old_cap = self.capacity
            self.capacity *= 2
            new_arr = [None] * self.capacity
            for i in range(self.size):
                new_arr[i] = self.array[i]
            self.array = new_arr
            print(f"{YELLOW}⚠️  ARRAY RESIZING! Kapasitas penuh ({old_cap}). Dilipatgandakan -> {self.capacity}{RESET}")
        
        self.array[self.size] = val
        self.size += 1
        self.visualize()

    def pop(self) -> Optional[Any]:
        if self.size == 0:
            print(f"{RED}❌ Array kosong! Tidak dapat pop.{RESET}")
            return None
        val = self.array[self.size - 1]
        self.array[self.size - 1] = None
        self.size -= 1
        print(f"\n{MAGENTA}--- Operasi Pop -> {BOLD}{val}{RESET} ---")
        self.visualize()
        return val

    def visualize(self) -> None:
        cells = []
        for i in range(self.capacity):
            if i < self.size:
                cells.append(f"{GREEN}[{self.array[i]}]{RESET}")
            else:
                cells.append(f"{DIM}[空]{RESET}")
        ratio = f"Size: {self.size}/{self.capacity}"
        print(f"Memory: {' '.join(cells)}  {BOLD}({ratio}){RESET}")


# ==========================================
# 2. SINGLY LINKED LIST
# ==========================================
class Node:
    def __init__(self, val: Any):
        self.val: Any = val
        self.next: Optional['Node'] = None


class SinglyLinkedList:
    def __init__(self):
        self.head: Optional[Node] = None
        self.count: int = 0

    def insert_head(self, val: Any) -> None:
        new_node = Node(val)
        new_node.next = self.head
        self.head = new_node
        self.count += 1
        print(f"\n{CYAN}--- Insert Head: {BOLD}{val}{RESET} ---")
        self.visualize()

    def insert_tail(self, val: Any) -> None:
        new_node = Node(val)
        if not self.head:
            self.head = new_node
        else:
            curr = self.head
            while curr.next:
                curr = curr.next
            curr.next = new_node
        self.count += 1
        print(f"\n{CYAN}--- Insert Tail: {BOLD}{val}{RESET} ---")
        self.visualize()

    def delete(self, val: Any) -> bool:
        print(f"\n{RED}--- Menghapus Elemen: {BOLD}{val}{RESET} ---")
        curr = self.head
        prev = None
        while curr and curr.val != val:
            prev = curr
            curr = curr.next
        if not curr:
            print(f"{RED}Nilai {val} tidak ditemukan dalam list.{RESET}")
            return False
        if not prev:
            self.head = curr.next
        else:
            prev.next = curr.next
        self.count -= 1
        self.visualize()
        return True

    def visualize(self) -> None:
        curr = self.head
        nodes_str = []
        while curr:
            nodes_str.append(f"{BLUE}[ {curr.val} | • ]{RESET}")
            curr = curr.next
        nodes_str.append(f"{DIM}NULL{RESET}")
        print(f"Linked List: {' -> '.join(nodes_str)} {BOLD}(Total Nodes: {self.count}){RESET}")


# ==========================================
# 3. STACK (LIFO - Last In, First Out)
# ==========================================
class StackVisualizer:
    def __init__(self, max_depth: int = 6):
        self.stack: List[Any] = []
        self.max_depth: int = max_depth

    def push(self, val: Any) -> None:
        if len(self.stack) >= self.max_depth:
            print(f"{RED}⚠️ Stack Overflow! Maksimal kedalaman tercapai.{RESET}")
            return
        self.stack.append(val)
        print(f"\n{GREEN}--- Push ke Stack: {BOLD}{val}{RESET} ---")
        self.visualize()

    def pop(self) -> Optional[Any]:
        if not self.stack:
            print(f"{RED}⚠️ Stack Underflow! Stack kosong.{RESET}")
            return None
        val = self.stack.pop()
        print(f"\n{MAGENTA}--- Pop dari Stack: {BOLD}{val}{RESET} ---")
        self.visualize()
        return val

    def visualize(self) -> None:
        print(f"{BOLD}--- Kondisi Stack Saat Ini (TOP di atas) ---{RESET}")
        if not self.stack:
            print(f"  {DIM}| (Stack Kosong) |{RESET}")
        else:
            for i in range(len(self.stack) - 1, -1, -1):
                item = self.stack[i]
                if i == len(self.stack) - 1:
                    print(f"  {YELLOW}|  {item}  | <-- [TOP]{RESET}")
                else:
                    print(f"  {WHITE}|  {item}  |{RESET}")
        print(f"  {BOLD}+-------+{RESET}")


# ==========================================
# 4. CIRCULAR QUEUE (FIFO)
# ==========================================
class CircularQueue:
    def __init__(self, capacity: int = 5):
        self.capacity: int = capacity
        self.queue: List[Optional[Any]] = [None] * capacity
        self.front: int = -1
        self.rear: int = -1

    def is_full(self) -> bool:
        return (self.rear + 1) % self.capacity == self.front

    def is_empty(self) -> bool:
        return self.front == -1

    def enqueue(self, val: Any) -> bool:
        if self.is_full():
            print(f"\n{RED}⚠️ Queue Penuh! Tidak dapat enqueue {val}.{RESET}")
            return False
        if self.is_empty():
            self.front = 0
            self.rear = 0
        else:
            self.rear = (self.rear + 1) % self.capacity
        self.queue[self.rear] = val
        print(f"\n{GREEN}--- Enqueue: {BOLD}{val}{RESET} (Front: {self.front}, Rear: {self.rear}) ---")
        self.visualize()
        return True

    def dequeue(self) -> Optional[Any]:
        if self.is_empty():
            print(f"\n{RED}⚠️ Queue Kosong! Tidak dapat dequeue.{RESET}")
            return None
        data = self.queue[self.front]
        self.queue[self.front] = None
        if self.front == self.rear:
            self.front = -1
            self.rear = -1
        else:
            self.front = (self.front + 1) % self.capacity
        print(f"\n{MAGENTA}--- Dequeue: {BOLD}{data}{RESET} ---")
        self.visualize()
        return data

    def visualize(self) -> None:
        cells = []
        labels = []
        for i in range(self.capacity):
            val_str = str(self.queue[i]) if self.queue[i] is not None else "-"
            cells.append(f"[{val_str:^3}]")
            
            ptr = []
            if i == self.front:
                ptr.append("F")
            if i == self.rear:
                ptr.append("R")
            labels.append(f"{':'.join(ptr):^5}" if ptr else "     ")

        print(f"Index :  {'   '.join([f'{i:^5}' for i in range(self.capacity)])}")
        print(f"Buffer:  {' '.join([f'{CYAN}{c}{RESET}' for c in cells])}")
        print(f"Pointer: {' '.join([f'{YELLOW}{l}{RESET}' for l in labels])}")


# ==========================================
# INTERACTIVE DEMO HARNESS
# ==========================================
def run_automated_demo():
    print(f"\n{BG_BLUE}{WHITE}{BOLD} =================================================== {RESET}")
    print(f"{BG_BLUE}{WHITE}{BOLD}   LAB SIMULATOR STRUKTUR DATA LINEAR (BAB 02)       {RESET}")
    print(f"{BG_BLUE}{WHITE}{BOLD} =================================================== {RESET}\n")

    time.sleep(0.5)
    print(f"{BOLD}{YELLOW}>>> 1. DEMO DYNAMIC ARRAY (Geometric Resizing) <<<{RESET}")
    arr = DynamicArraySimulator(initial_capacity=2)
    for num in [10, 20, 30, 40, 50]:
        arr.append(num)
        time.sleep(0.2)
    arr.pop()
    time.sleep(0.3)

    print(f"\n{BOLD}{YELLOW}>>> 2. DEMO SINGLY LINKED LIST (Pointer Chaining) <<<{RESET}")
    sll = SinglyLinkedList()
    sll.insert_head("Node_B")
    sll.insert_head("Node_A")
    sll.insert_tail("Node_C")
    sll.insert_tail("Node_D")
    sll.delete("Node_B")
    time.sleep(0.3)

    print(f"\n{BOLD}{YELLOW}>>> 3. DEMO STACK (LIFO / Call Stack Mock) <<<{RESET}")
    st = StackVisualizer(max_depth=5)
    st.push("Frame_Main")
    st.push("Frame_FuncA")
    st.push("Frame_FuncB")
    st.pop()
    st.push("Frame_FuncC")
    time.sleep(0.3)

    print(f"\n{BOLD}{YELLOW}>>> 4. DEMO CIRCULAR QUEUE (Ring Buffer FIFO) <<<{RESET}")
    cq = CircularQueue(capacity=4)
    cq.enqueue("Paket_1")
    cq.enqueue("Paket_2")
    cq.enqueue("Paket_3")
    cq.dequeue()
    cq.enqueue("Paket_4")
    cq.enqueue("Paket_5")  # Mengisi posisi wrap-around ring
    cq.dequeue()
    cq.dequeue()

    print(f"\n{BG_GREEN}{WHITE}{BOLD} ✔ SIMULASI SEMUA STRUKTUR DATA LINEAR SELESAI DENGAN SUKSES! {RESET}\n")


def interactive_menu():
    while True:
        print(f"\n{BOLD}{CYAN}=== MENU SIMULATOR STRUKTUR DATA LINEAR ==={RESET}")
        print("1. Jalankan Simulasi Otomatis (Semua Modul)")
        print("2. Eksplorasi Dynamic Array")
        print("3. Eksplorasi Singly Linked List")
        print("4. Eksplorasi Stack (LIFO)")
        print("5. Eksplorasi Circular Queue (FIFO)")
        print("6. Keluar")
        choice = input(f"{BOLD}Pilih opsi (1-6): {RESET}").strip()

        if choice == "1":
            run_automated_demo()
        elif choice == "2":
            arr = DynamicArraySimulator(initial_capacity=2)
            while True:
                sub = input("Ketik nilai untuk append (atau 'pop', 'exit'): ").strip()
                if sub.lower() == 'exit':
                    break
                elif sub.lower() == 'pop':
                    arr.pop()
                elif sub:
                    arr.append(sub)
        elif choice == "3":
            sll = SinglyLinkedList()
            while True:
                sub = input("Ketik 'h <val>' (insert head), 't <val>' (insert tail), 'd <val>' (delete), atau 'exit': ").strip()
                if sub.lower() == 'exit':
                    break
                parts = sub.split(maxsplit=1)
                if len(parts) == 2:
                    cmd, val = parts[0], parts[1]
                    if cmd == 'h':
                        sll.insert_head(val)
                    elif cmd == 't':
                        sll.insert_tail(val)
                    elif cmd == 'd':
                        sll.delete(val)
        elif choice == "4":
            st = StackVisualizer(max_depth=6)
            while True:
                sub = input("Ketik nilai untuk push (atau 'pop', 'exit'): ").strip()
                if sub.lower() == 'exit':
                    break
                elif sub.lower() == 'pop':
                    st.pop()
                elif sub:
                    st.push(sub)
        elif choice == "5":
            cq = CircularQueue(capacity=4)
            while True:
                sub = input("Ketik nilai untuk enqueue (atau 'deq', 'exit'): ").strip()
                if sub.lower() == 'exit':
                    break
                elif sub.lower() == 'deq':
                    cq.dequeue()
                elif sub:
                    cq.enqueue(sub)
        elif choice == "6":
            print(f"{GREEN}Sampai jumpa di pembelajaran algoritma berikutnya!{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak valid.{RESET}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        run_automated_demo()
    elif not sys.stdin.isatty():
        # Running in non-interactive pipeline / test
        run_automated_demo()
    else:
        # Prompt or fallback to demo
        try:
            interactive_menu()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{YELLOW}Program dihentikan.{RESET}")
