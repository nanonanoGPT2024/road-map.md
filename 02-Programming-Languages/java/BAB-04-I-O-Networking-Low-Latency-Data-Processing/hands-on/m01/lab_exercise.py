#!/usr/bin/env python3
"""
Lab Exercise: Java I/O, NIO & Low-Latency Data Processing Architecture Simulation
BAB-04: I/O, Networking & Low-Latency Data Processing

Simulasi arsitektur internal Java NIO, Direct Memory (Off-Heap), Zero-Copy I/O,
serta mekanika LMAX Disruptor (RingBuffer & Cache Line Padding).
"""

import sys
import time
import os
from typing import List, Optional

# ANSI Color Codes
class Color:
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
    BG_DARK = "\033[100m"

def print_header(title: str) -> None:
    print(f"\n{Color.BOLD}{Color.CYAN}{'=' * 72}{Color.RESET}")
    print(f"{Color.BOLD}{Color.WHITE}  [JAVA I/O & LOW-LATENCY SIMULATOR] :: {title.upper()}{Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}{'=' * 72}{Color.RESET}")

def print_sub(title: str) -> None:
    print(f"\n{Color.BOLD}{Color.YELLOW}--- {title} ---{Color.RESET}")

# ==============================================================================
# 1. SIMULASI JAVA NIO ByteBuffer (Position, Limit, Capacity & Modes)
# ==============================================================================
class SimulatedNioBuffer:
    def __init__(self, capacity: int, is_direct: bool = False):
        self.capacity: int = capacity
        self.limit: int = capacity
        self.position: int = 0
        self.mark_pos: Optional[int] = None
        self.is_direct: bool = is_direct  # DirectByteBuffer (Off-Heap) vs HeapByteBuffer
        self.data: List[int] = [0] * capacity

    def put(self, byte_val: int) -> bool:
        if self.position >= self.limit:
            print(f"{Color.RED}[BufferOverflowException] position={self.position} >= limit={self.limit}{Color.RESET}")
            return False
        self.data[self.position] = byte_val & 0xFF
        self.position += 1
        return True

    def get(self) -> Optional[int]:
        if self.position >= self.limit:
            print(f"{Color.RED}[BufferUnderflowException] position={self.position} >= limit={self.limit}{Color.RESET}")
            return None
        val = self.data[self.position]
        self.position += 1
        return val

    def flip(self) -> None:
        """Transisi dari Writing Mode ke Reading Mode."""
        self.limit = self.position
        self.position = 0
        self.mark_pos = None

    def clear(self) -> None:
        """Reset untuk Writing Mode baru (data tidak dihapus fisik)."""
        self.position = 0
        self.limit = self.capacity
        self.mark_pos = None

    def compact(self) -> None:
        """Pindahkan sisa unread bytes ke awal buffer."""
        unread_len = self.limit - self.position
        for i in range(unread_len):
            self.data[i] = self.data[self.position + i]
        self.position = unread_len
        self.limit = self.capacity
        self.mark_pos = None

    def display(self, label: str) -> None:
        buf_type = "DirectByteBuffer (Off-Heap)" if self.is_direct else "HeapByteBuffer (JVM GC Heap)"
        color_type = Color.MAGENTA if self.is_direct else Color.BLUE
        print(f"\n{Color.BOLD}{label}{Color.RESET} [{color_type}{buf_type}{Color.RESET}]")
        print(f"  Pointers: {Color.GREEN}position={self.position}{Color.RESET}, "
              f"{Color.YELLOW}limit={self.limit}{Color.RESET}, "
              f"{Color.CYAN}capacity={self.capacity}{Color.RESET}")

        # Visualisasi sel memori
        cells = []
        for i in range(self.capacity):
            val_str = f"{self.data[i]:02X}"
            if i < self.position:
                cells.append(f"{Color.BG_GREEN}{Color.WHITE} {val_str} {Color.RESET}")
            elif i < self.limit:
                cells.append(f"{Color.BG_BLUE}{Color.WHITE} {val_str} {Color.RESET}")
            else:
                cells.append(f"{Color.BG_DARK}{Color.DIM} {val_str} {Color.RESET}")
        print("  Slots  : " + "".join(cells))

        # Penanda pointer
        ptrs = ["    "] * self.capacity
        if self.position < self.capacity:
            ptrs[self.position] = "^POS"
        if self.limit < self.capacity:
            ptrs[self.limit] = "^LIM"
        elif self.limit == self.capacity:
            ptrs[-1] += " (LIM)"
        print("  Index  : " + "".join(f" [{i:02d}]" for i in range(self.capacity)))

# ==============================================================================
# 2. SIMULASI ZERO-COPY (sendfile / FileChannel.transferTo) VS STANDARD I/O
# ==============================================================================
def simulate_zero_copy() -> None:
    print_sub("Simulasi Arsitektur I/O: Traditional Copy vs OS Zero-Copy")

    print(f"\n{Color.BOLD}1. Pendekatan Tradisional (Standard java.io / Streams):{Color.RESET}")
    print("   [Disk] --(1. DMA Copy)--> [Kernel Buffer]")
    print("   [Kernel Buffer] --(2. CPU Copy / Context Switch)--> [User Space / JVM Heap]")
    print("   [JVM Heap] --(3. CPU Copy / Context Switch)--> [Socket Buffer (Kernel)]")
    print("   [Socket Buffer] --(4. DMA Copy)--> [NIC Protocol Engine]")
    print(f"   {Color.RED}=> Total 4 Context Switches + 4 Buffer Copies (2 CPU copies)!{Color.RESET}")

    print(f"\n{Color.BOLD}2. Pendekatan Zero-Copy (FileChannel.transferTo() / epoll sendfile):{Color.RESET}")
    print("   [Disk] --(1. DMA Copy)--> [Kernel Read Buffer]")
    print("   [Kernel Read Buffer] --(2. DMA Gather / Pipe)--> [NIC Buffer]")
    print(f"   {Color.GREEN}=> Total 2 Context Switches + 0 CPU Copy (Bypass JVM Heap sepenuhnya)!{Color.RESET}")

    # Micro-benchmark dummy throughput calculation
    data_size_mb = 512
    print(f"\n{Color.BOLD}Menjalankan Micro-Benchmark Simulasi Transfer File {data_size_mb} MB:{Color.RESET}")

    t0 = time.perf_counter()
    # Simulasi latency standard I/O (meniru overhead GC + dual user copy)
    time.sleep(0.35)
    t_std = time.perf_counter() - t0
    std_throughput = data_size_mb / t_std

    t1 = time.perf_counter()
    # Simulasi latency direct zero-copy
    time.sleep(0.08)
    t_zc = time.perf_counter() - t1
    zc_throughput = data_size_mb / t_zc

    print(f"  Standard java.io Copy : {t_std*1000:.2f} ms | Throughput: {Color.YELLOW}{std_throughput:.1f} MB/s{Color.RESET}")
    print(f"  Zero-Copy transferTo(): {t_zc*1000:.2f} ms | Throughput: {Color.GREEN}{zc_throughput:.1f} MB/s{Color.RESET}")
    speedup = zc_throughput / std_throughput
    print(f"  {Color.BOLD}{Color.GREEN}Peningkatan Efisiensi: {speedup:.2f}x lebih cepat tanpa GC Pauses!{Color.RESET}")

# ==============================================================================
# 3. SIMULASI LMAX DISRUPTOR & MECHANICAL SYMPATHY (RingBuffer & False Sharing)
# ==============================================================================
class DisruptorRingBuffer:
    def __init__(self, buffer_size: int = 8):
        # buffer_size harus power of 2 untuk fast bitwise modulo: seq & (size - 1)
        assert (buffer_size & (buffer_size - 1)) == 0, "Buffer size harus kelipatan kuadrat 2"
        self.buffer_size = buffer_size
        self.mask = buffer_size - 1
        self.entries = [None] * buffer_size
        self.cursor = -1  # Urutan published sequence

    def claim_and_publish(self, event_data: str) -> int:
        self.cursor += 1
        index = self.cursor & self.mask
        self.entries[index] = event_data
        return self.cursor

    def show_state(self) -> None:
        print(f"  RingBuffer Cursor: {Color.CYAN}{self.cursor}{Color.RESET} (Mask: {self.mask})")
        print("  Slots:")
        for idx in range(self.buffer_size):
            item = self.entries[idx]
            val = f"'{item}'" if item else "EMPTY"
            active = f"{Color.BG_GREEN}{Color.WHITE} ACTIVE {Color.RESET}" if (self.cursor >= 0 and (self.cursor & self.mask) == idx) else ""
            print(f"    Slot [{idx}]: {val:<12} {active}")

def simulate_false_sharing() -> None:
    print_sub("Mechanical Sympathy: Cache Line Padding & False Sharing")
    print("Di arsitektur CPU x86-64, L1/L2/L3 Cache Line berukuran 64 Bytes.")
    print("Jika 2 thread memodifikasi variabel bersebelahan dalam cache line yang sama:")
    print(f"{Color.RED}  [Thread 1: varA] <--- Cache Line Invalidation Conflict ---> [Thread 2: varB]{Color.RESET}")
    print("Solusi Java 8+: anotasi @Contended atau manual padding 56 bytes (7 x long):")
    print(f"{Color.GREEN}  [public long p1,p2,p3,p4,p5,p6,p7; public volatile long value; public long q1,q2...]{Color.RESET}")

# ==============================================================================
# 4. INTERACTIVE DEMO RUNNER
# ==============================================================================
def demo_nio_buffer() -> None:
    print_sub("Demonstrasi Lifecycle java.nio.ByteBuffer")
    buf = SimulatedNioBuffer(capacity=8, is_direct=True)
    buf.display("1. Inisialisasi DirectByteBuffer")

    print(f"\n{Color.CYAN}--> Menulis 5 byte data: [0x10, 0x20, 0x30, 0x40, 0x50]{Color.RESET}")
    for b in [0x10, 0x20, 0x30, 0x40, 0x50]:
        buf.put(b)
    buf.display("2. State Setelah Penulisan (Writing Mode)")

    print(f"\n{Color.CYAN}--> Memanggil buffer.flip() untuk transisi ke Reading Mode{Color.RESET}")
    buf.flip()
    buf.display("3. State Setelah flip()")

    print(f"\n{Color.CYAN}--> Membaca 2 byte pertama via buffer.get(){Color.RESET}")
    v1 = buf.get()
    v2 = buf.get()
    print(f"    Read Byte 1 = 0x{v1:02X}, Byte 2 = 0x{v2:02X}")
    buf.display("4. State Setelah Membaca 2 Byte")

    print(f"\n{Color.CYAN}--> Memanggil buffer.compact() untuk menggeser 3 byte tersisa ke indeks 0{Color.RESET}")
    buf.compact()
    buf.display("5. State Setelah compact() (Kembali siap di-write)")

def demo_disruptor() -> None:
    print_sub("Demonstrasi Lock-Free RingBuffer (LMAX Disruptor Pattern)")
    rb = DisruptorRingBuffer(buffer_size=8)
    events = ["ORDER_CREATED", "RISK_EVALUATED", "MATCHED", "SETTLED", "NOTIFIED"]
    for evt in events:
        seq = rb.claim_and_publish(evt)
        print(f"{Color.GREEN}[PUBLISH]{Color.RESET} Sequence #{seq:02d} -> Event: {evt}")
    print()
    rb.show_state()

def run_all() -> None:
    print_header("High Performance I/O & Networking Architecture")
    demo_nio_buffer()
    simulate_zero_copy()
    demo_disruptor()
    simulate_false_sharing()
    print(f"\n{Color.BOLD}{Color.GREEN}=== Seluruh Simulasi Konsep Fondasi Selesai Dijalankan! ==={Color.RESET}\n")

def interactive_menu() -> None:
    while True:
        print_header("Menu Eksplorasi Hands-On Java I/O & Low Latency")
        print("1. Simulasi Lifecycle java.nio.ByteBuffer (flip, compact, position, limit)")
        print("2. Benchmark Arsitektur Zero-Copy vs Traditional Streams")
        print("3. Simulasi LMAX Disruptor Lock-Free RingBuffer")
        print("4. Penjelasan Mechanical Sympathy & Cache Line Padding")
        print("5. Jalankan Seluruh Modul Berurutan")
        print("0. Keluar")

        choice = input(f"\n{Color.BOLD}{Color.CYAN}Pilih opsi [0-5]: {Color.RESET}").strip()
        if choice == "1":
            demo_nio_buffer()
        elif choice == "2":
            simulate_zero_copy()
        elif choice == "3":
            demo_disruptor()
        elif choice == "4":
            simulate_false_sharing()
        elif choice == "5":
            run_all()
        elif choice == "0":
            print(f"{Color.GREEN}Terima kasih! Sampai jumpa di lab berikutnya.{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid, silakan coba lagi.{Color.RESET}")

        input(f"\n{Color.DIM}Tekan [Enter] untuk kembali ke menu...{Color.RESET}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--non-interactive":
        run_all()
    else:
        interactive_menu()
