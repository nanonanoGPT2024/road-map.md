#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Fondasi Unsafe Rust & Foreign Function Interface (FFI)
BAB 08: Unsafe Rust & Foreign Function Interface (FFI)

Simulasi interaktif 5 Unsafe Superpowers di Rust:
1. Dereferencing Raw Pointers (*const T, *mut T) & Pointer Arithmetic
2. Pemanggilan Unsafe Functions & Extern "C" (FFI ABI Binding)
3. Implementasi Unsafe Trait (Send & Sync Invariant)
4. Mutasi Mutable Static State & Data Race Detection
5. Akses Field Union & Type Punning
"""

import sys
import time
import struct
from typing import Any, Dict, List, Optional

# ANSI Color Codes untuk Terminal
class TermColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    BG_DARK = "\033[40m"


def print_banner(title: str) -> None:
    print(f"\n{TermColor.MAGENTA}{'=' * 65}{TermColor.RESET}")
    print(f"{TermColor.BOLD}{TermColor.CYAN} [LAB SIMULATION] {title.upper()}{TermColor.RESET}")
    print(f"{TermColor.MAGENTA}{'=' * 65}{TermColor.RESET}\n")


def print_success(msg: str) -> None:
    print(f"{TermColor.GREEN}[✓] {msg}{TermColor.RESET}")


def print_warning(msg: str) -> None:
    print(f"{TermColor.YELLOW}[!] {msg}{TermColor.RESET}")


def print_error(msg: str) -> None:
    print(f"{TermColor.RED}[✗] {msg}{TermColor.RESET}")


def print_info(msg: str) -> None:
    print(f"{TermColor.BLUE}[i] {msg}{TermColor.RESET}")


class VirtualMemorySimulator:
    """Simulasi virtual heap & raw memory addressing untuk emulasi Raw Pointer Rust."""
    def __init__(self, size: int = 128):
        self.size = size
        self.buffer = bytearray(size)
        self.base_addr = 0x7FFF_0000

    def allocate_i32(self, offset: int, value: int) -> int:
        if offset + 4 > self.size:
            raise OverflowError("Memory out of bounds")
        packed = struct.pack("<i", value)
        self.buffer[offset:offset+4] = packed
        return self.base_addr + offset

    def deref_raw_pointer(self, ptr_address: int, is_mut: bool = False) -> int:
        offset = ptr_address - self.base_addr
        if ptr_address == 0:
            raise ValueError("Dereferencing NULL pointer! Undefined Behavior (UB) di Rust.")
        if offset < 0 or offset + 4 > self.size:
            raise MemoryError(f"Segmentation fault! Alamat 0x{ptr_address:08X} di luar batas alokasi.")
        (val,) = struct.unpack("<i", self.buffer[offset:offset+4])
        return val

    def write_raw_pointer(self, ptr_address: int, value: int) -> None:
        offset = ptr_address - self.base_addr
        if ptr_address == 0:
            raise ValueError("Writing through NULL pointer! Undefined Behavior (UB).")
        if offset < 0 or offset + 4 > self.size:
            raise MemoryError(f"Memory Access Violation saat write ke 0x{ptr_address:08X}!")
        self.buffer[offset:offset+4] = struct.pack("<i", value)


class FFISimulator:
    """Emulasi Foreign Function Interface (FFI) ABI C binding."""
    def __init__(self):
        self.c_symbols: Dict[str, Any] = {
            "abs": abs,
            "strlen": lambda s: len(s),
            "snprintf": lambda buf_size, fmt, arg: (fmt % arg)[:buf_size]
        }

    def call_symbol(self, symbol_name: str, *args) -> Any:
        if symbol_name not in self.c_symbols:
            raise LookupError(f"Unresolved foreign symbol: '{symbol_name}' (Linker error)")
        return self.c_symbols[symbol_name](*args)


def demo_raw_pointers():
    print_banner("1. Dereferencing Raw Pointers (*const T, *mut T)")
    mem = VirtualMemorySimulator()
    val = 42
    ptr_addr = mem.allocate_i32(offset=16, value=val)

    print_info(f"Variabel integer bernilai {val} dialokasikan pada alamat: {TermColor.BOLD}0x{ptr_addr:08X}{TermColor.RESET}")
    print_info("Dalam Safe Rust: membuat raw pointer `let r1 = &val as *const i32;` DIPERBOLEHKAN.")
    print_info("Namun, DEREFERENCING `*r1` WAJIB berada di dalam blok `unsafe { ... }`.")

    print(f"\n{TermColor.YELLOW}Simulasi 1A: Safe Dereference dalam unsafe block{TermColor.RESET}")
    try:
        read_val = mem.deref_raw_pointer(ptr_addr)
        print_success(f"unsafe {{ *r1 }} terbaca sukses: {read_val}")
    except Exception as e:
        print_error(f"Error: {e}")

    print(f"\n{TermColor.YELLOW}Simulasi 1B: Dereferencing NULL Pointer (Undefined Behavior){TermColor.RESET}")
    null_ptr = 0x0000_0000
    try:
        print_info(f"Mencoba dereferensi null pointer: 0x{null_ptr:08X}...")
        mem.deref_raw_pointer(null_ptr)
    except ValueError as e:
        print_error(f"Tertangkap Panik UB: {e}")

    print(f"\n{TermColor.YELLOW}Simulasi 1C: Pointer Arithmetic & Buffer Mutation (*mut i32){TermColor.RESET}")
    try:
        mem.write_raw_pointer(ptr_addr, 999)
        new_val = mem.deref_raw_pointer(ptr_addr)
        print_success(f"unsafe {{ *r_mut = 999; }} -> Nilai baru berhasil di-update: {new_val}")
    except Exception as e:
        print_error(f"Error: {e}")


def demo_ffi_call():
    print_banner("2. Memanggil Fungsi Eksternal C (FFI Binding)")
    ffi = FFISimulator()
    print_info("Deklarasi Rust: extern \"C\" { fn abs(input: i32) -> i32; }")
    print_info("Pemanggilan fungsi eksternal selalu tidak dipercaya oleh compiler -> Wajib `unsafe`.")

    test_nums = [-15, 42, -999]
    for num in test_nums:
        res = ffi.call_symbol("abs", num)
        print_success(f"unsafe {{ libc::abs({num}) }} = {res}")

    print_info("\nSimulasi pemanggilan fungsi string length C ABI:")
    sample = "Halo Unsafe Rust!"
    res_len = ffi.call_symbol("strlen", sample)
    print_success(f"unsafe {{ libc::strlen(\"{sample}\") }} = {res_len} bytes")


def demo_unsafe_traits():
    print_banner("3. Unsafe Trait Implementation (Send & Sync Invariant)")
    print_info("Trait `Send` dan `Sync` adalah marker traits otomatis di Rust.")
    print_info("Jika struct membungkus Raw Pointer (*mut T), compiler MENCABUT implementasi Send/Sync otomatis.")
    print_info("Programmer wajib mendeklarasikan: `unsafe impl Send for MyWrapper {}` dengan janji thread-safety.")

    class MyUnsafeWrapper:
        def __init__(self, raw_ptr: int, is_send_guaranteed: bool):
            self.raw_ptr = raw_ptr
            self.has_unsafe_send_impl = is_send_guaranteed

        def dispatch_to_thread(self, thread_id: int):
            if not self.has_unsafe_send_impl:
                raise TypeError(
                    f"`MyUnsafeWrapper` cannot be sent between threads safely (Trait `Send` tidak diimplementasikan)!"
                )
            print_success(f"Objek berhasil dikirim ke Worker Thread #{thread_id} via unsafe contract!")

    print(f"{TermColor.YELLOW}Uji Tipe Tanpa `unsafe impl Send`:{TermColor.RESET}")
    obj1 = MyUnsafeWrapper(raw_ptr=0x7FFF_0010, is_send_guaranteed=False)
    try:
        obj1.dispatch_to_thread(1)
    except TypeError as e:
        print_error(f"Compiler Error: {e}")

    print(f"\n{TermColor.YELLOW}Uji Tipe Dengan `unsafe impl Send`:{TermColor.RESET}")
    obj2 = MyUnsafeWrapper(raw_ptr=0x7FFF_0010, is_send_guaranteed=True)
    obj2.dispatch_to_thread(2)


def demo_mutable_static():
    print_banner("4. Mutable Static Variable & Concurrency Race")
    print_info("Variabel `static mut COUNTER: u32 = 0;` memiliki lokasi memori tetap.")
    print_info("Membaca atau menulis `static mut` adalah `unsafe` karena rawan DATA RACE.")

    state = {"COUNTER": 0}

    def unsafe_read_write(step: int, modify: int) -> int:
        prev = state["COUNTER"]
        state["COUNTER"] += modify
        return prev

    print_info(f"Nilai awal `COUNTER`: {state['COUNTER']}")
    unsafe_read_write(1, 10)
    print_success(f"unsafe {{ COUNTER += 10; }} -> Nilai saat ini: {state['COUNTER']}")
    unsafe_read_write(2, -3)
    print_success(f"unsafe {{ COUNTER -= 3; }}  -> Nilai saat ini: {state['COUNTER']}")
    print_warning("Di safe Rust modern, lebih disarankan memakai `AtomicU32` atau `Mutex<T>` daripada `static mut`.")


def demo_union_type_punning():
    print_banner("5. Akses Field Union (Type Punning)")
    print_info("Rust `union` memetakan beberapa tipe ke blok memori yang sama (overlap).")
    print_info("Membaca field union adalah `unsafe` karena compiler tidak melacak varian mana yang aktif.")

    # Simulasi union 4 bytes: f32 dan u32
    float_val = 3.1415927
    raw_bytes = struct.pack("<f", float_val)
    (int_repr,) = struct.unpack("<I", raw_bytes)

    print_info(f"Menyimpan nilai `f32`: {float_val}")
    print_info(f"Byte representation: {[hex(b) for b in raw_bytes]}")
    print_success(f"unsafe {{ punned_union.as_u32 }} -> Bitwise IEEE 754: 0x{int_repr:08X} ({int_repr})")
    print_warning("Type punning via union memerlukan validasi ukuran dan representasi biner.")


def interactive_quiz():
    print_banner("Kuis Interaktif: Validasi Pemahaman Unsafe Rust")
    questions = [
        {
            "q": "Apakah membuat (bukan mendereferensikan) raw pointer memerlukan blok `unsafe`?",
            "options": ["A. Ya, selalu wajib unsafe", "B. Tidak, safe rust boleh membuat pointer, hanya dereferensi yang unsafe"],
            "ans": "B",
            "explain": "Membuat raw pointer (*const T / *mut T) aman karena tidak mengakses memori. Yang berpotensi UB adalah dereferensinya."
        },
        {
            "q": "Mengapa pemanggilan fungsi C via `extern \"C\"` selalu dianggap unsafe oleh Rust?",
            "options": ["A. Compiler Rust tidak dapat memverifikasi jaminan memori dan invarian kode C", "B. Karena kode C dieksekusi di virtual machine berbeda"],
            "ans": "A",
            "explain": "Compiler Rust tidak memiliki kendali statis atas pointer, alokasi, atau aliasing di dalam implementasi biner bahasa C."
        }
    ]

    score = 0
    for idx, item in enumerate(questions, 1):
        print(f"{TermColor.BOLD}{TermColor.YELLOW}Pertanyaan #{idx}:{TermColor.RESET} {item['q']}")
        for opt in item["options"]:
            print(f"  {opt}")
        # Simulasi jawaban terverifikasi
        selected = item["ans"]
        print(f"Jawaban otomatis terpilih: {TermColor.CYAN}{selected}{TermColor.RESET}")
        print_success(f"Benar! {item['explain']}\n")
        score += 1

    print_success(f"Skor Kuis Evaluasi: {score}/{len(questions)} (100% Lulus)")


def main():
    print(f"{TermColor.BOLD}{TermColor.CYAN}Memulai Hands-on Lab Unsafe Rust & FFI Simulator...{TermColor.RESET}")
    time.sleep(0.2)

    demo_raw_pointers()
    demo_ffi_call()
    demo_unsafe_traits()
    demo_mutable_static()
    demo_union_type_punning()
    interactive_quiz()

    print_banner("Lab Selesai dengan Sukses")
    print_success("Seluruh konsep 5 Unsafe Superpowers & FFI telah disimulasikan secara valid.")


if __name__ == "__main__":
    main()
