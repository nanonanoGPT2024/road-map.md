#!/usr/bin/env python3
"""
Simulasi Interaktif Konsep Fondasi Inti Ruby: BAB-04 Resource Management & Low-Level I/O
Topik:
  1. Low-Level File Descriptors (FD) vs Buffered IO (IO#sysread / IO#syswrite vs IO#read / IO#write)
  2. Block Scoping & Deterministic Cleanup (File.open { |f| ... } vs dangling handles)
  3. File Descriptor Leak Detection & Table Exhaustion Simulation
  4. ObjectSpace.define_finalizer & Non-deterministic GC Cleanup Simulation
"""

import sys
import time
import os
import io

# ANSI Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[1;32m"
BLUE = "\033[1;34m"
CYAN = "\033[1;36m"
YELLOW = "\033[1;33m"
RED = "\033[1;31m"
MAGENTA = "\033[1;35m"
DIM = "\033[2m"

def print_header(title: str):
    print(f"\n{BOLD}{CYAN}{'=' * 72}{RESET}")
    print(f"{BOLD}{CYAN}[SIMULASI RUBY I/O] {title}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 72}{RESET}")

class VirtualKernel:
    """Simulasi Kernel OS yang mengelola File Descriptor Table."""
    def __init__(self, max_descriptors: int = 16):
        self.max_descriptors = max_descriptors
        self.allocated_fds: dict[int, str] = {
            0: "STDIN",
            1: "STDOUT",
            2: "STDERR"
        }
        self.next_fd = 3

    def allocate_fd(self, resource_name: str) -> int:
        if len(self.allocated_fds) >= self.max_descriptors:
            raise OSError(24, f"Errno::EMFILE - Too many open files (Kernel Limit: {self.max_descriptors})")
        
        while self.next_fd in self.allocated_fds:
            self.next_fd += 1
        
        fd = self.next_fd
        self.allocated_fds[fd] = resource_name
        self.next_fd += 1
        return fd

    def close_fd(self, fd: int):
        if fd not in self.allocated_fds:
            raise ValueError(f"Errno::EBADF - Bad file descriptor (FD {fd} not open)")
        del self.allocated_fds[fd]

    def render_fd_table(self):
        print(f"\n{BOLD}Kernel File Descriptor Table ({len(self.allocated_fds)}/{self.max_descriptors} in use):{RESET}")
        for fd in sorted(self.allocated_fds.keys()):
            name = self.allocated_fds[fd]
            tag = f"{BLUE}[SYS]{RESET}" if fd < 3 else f"{GREEN}[USER]{RESET}"
            print(f"  FD {fd:>2} -> {tag} {name}")
        slots_left = self.max_descriptors - len(self.allocated_fds)
        bar_filled = "#" * len(self.allocated_fds)
        bar_empty = "." * slots_left
        status_color = GREEN if slots_left > 4 else (YELLOW if slots_left > 1 else RED)
        print(f"  Utilization: [{status_color}{bar_filled}{DIM}{bar_empty}{RESET}] ({slots_left} slots free)\n")

class SimulatedRubyIO:
    """Simulasi Ruby IO object dengan Dual-Layer (Buffered vs Low-Level Raw Syscall)."""
    def __init__(self, kernel: VirtualKernel, path: str, mode: str = "w+"):
        self.kernel = kernel
        self.path = path
        self.mode = mode
        self.closed = False
        self.fd = kernel.allocate_fd(path)
        self.user_buffer = io.BytesIO()
        self.storage = bytearray()
        print(f"  {DIM}[Kernel] sys_open('{path}') -> FD {self.fd}{RESET}")

    def write(self, data: bytes) -> int:
        """Buffered write (Ruby: IO#write). Data tersimpan di userspace buffer dulu."""
        if self.closed:
            raise IOError("IOError: closed stream")
        self.user_buffer.write(data)
        print(f"  {YELLOW}[Ruby IO#write]{RESET} {len(data)} bytes -> Buffered di User Space (Belum flush ke disk/FD)")
        return len(data)

    def flush(self):
        """Ruby: IO#flush -> Mengosongkan buffer ke level OS kernel."""
        if self.closed:
            raise IOError("IOError: closed stream")
        data = self.user_buffer.getvalue()
        if data:
            self.storage.extend(data)
            self.user_buffer = io.BytesIO()
            print(f"  {CYAN}[Ruby IO#flush]{RESET} {len(data)} bytes dipindahkan dari User Buffer ke Kernel Storage via FD {self.fd}")

    def syswrite(self, data: bytes) -> int:
        """Unbuffered direct syscall (Ruby: IO#syswrite). Melewati userspace buffer."""
        if self.closed:
            raise IOError("IOError: closed stream")
        if self.user_buffer.tell() > 0:
            print(f"  {RED}[Warning]{RESET} Ruby syswrite dipanggil saat buffer tidak kosong! Potensi data interleaving.")
        self.storage.extend(data)
        print(f"  {GREEN}[Ruby IO#syswrite]{RESET} Direct POSIX write(2) {len(data)} bytes ke FD {self.fd} (By-passing buffer)")
        return len(data)

    def close(self):
        """Ruby: IO#close -> Flush lalu release FD."""
        if not self.closed:
            if self.user_buffer.tell() > 0:
                self.flush()
            self.kernel.close_fd(self.fd)
            self.closed = True
            print(f"  {MAGENTA}[Ruby IO#close]{RESET} File stream '{self.path}' ditutup, FD {self.fd} dilepaskan.")

def demo_buffering(kernel: VirtualKernel):
    print_header("1. Buffered IO vs Raw Syscall (IO#write vs IO#syswrite)")
    print(f"{BOLD}Konsep Ruby:{RESET} IO#write mengumpulkan data dalam CRT/Ruby userspace buffer (default 4KB/8KB),")
    print("sedangkan IO#syswrite memicu syscall write(2) kernel secara langsung tanpa buffer.\n")
    
    file_io = SimulatedRubyIO(kernel, "logs/app.log")
    
    # 1. Buffered IO
    file_io.write(b"Line 1: Inisialisasi service\n")
    file_io.write(b"Line 2: Processing request #1042\n")
    print(f"  -> Isi Disk Storage saat ini: {len(file_io.storage)} bytes (Masih kosong karena belum di-flush)")
    
    # 2. Flush
    file_io.flush()
    print(f"  -> Isi Disk Storage setelah flush: {len(file_io.storage)} bytes")

    # 3. Direct Syswrite
    file_io.syswrite(b"Line 3: CRITICAL KERNEL SIGNAL (Instant direct write)\n")
    print(f"  -> Isi Disk Storage seketika: {len(file_io.storage)} bytes")
    
    file_io.close()

def ruby_style_file_open(kernel: VirtualKernel, path: str, block):
    """
    Implementasi pola idiomatis Ruby:
    File.open(path) do |f|
      ...
    end # Otomatis f.close dipanggil di blok ensure
    """
    io_obj = SimulatedRubyIO(kernel, path)
    try:
        return block(io_obj)
    finally:
        # Meniru klausa 'ensure' di Ruby
        print(f"  {BOLD}{MAGENTA}[Ruby ensure hook]{RESET} Menjamin deterministic cleanup stream...")
        io_obj.close()

def demo_block_cleanup(kernel: VirtualKernel):
    print_header("2. Block Scoping & Deterministic RAII Cleanup (File.open { |f| ... })")
    print(f"{BOLD}Konsep Ruby:{RESET} Blok File.open menjamin stream selalu ditutup (close) bahkan ketika")
    print("terjadi StandardError atau Exception tak terduga (menggunakan begin...ensure).\n")
    
    print(f"{BOLD}Kasus A: Eksekusi normal dengan block-pass{RESET}")
    def safe_operation(f: SimulatedRubyIO):
        f.write(b"Transaksi data penting #8821\n")
        f.flush()
        print(f"    Eksekusi kerja di dalam blok aman. Status FD: {f.fd}")

    ruby_style_file_open(kernel, "db/transactions.dat", safe_operation)
    kernel.render_fd_table()

    print(f"{BOLD}Kasus B: Terjadi Exception di tengah operasi{RESET}")
    def faulty_operation(f: SimulatedRubyIO):
        f.write(b"Mencoba payload berisiko...\n")
        print(f"    {RED}Terjadi Runtime Error / ZeroDivisionError di dalam blok!{RESET}")
        raise RuntimeError("Gagal menghubungi remote storage!")

    try:
        ruby_style_file_open(kernel, "db/crash_test.dat", faulty_operation)
    except RuntimeError as err:
        print(f"  {RED}[Rescued Error]:{RESET} {err}")

    print(f"  {GREEN}[Hasil]:{RESET} Walaupun error dilempar, FD berhasil dilepas tanpa bocor!")
    kernel.render_fd_table()

def demo_fd_leak_and_exhaustion(kernel: VirtualKernel):
    print_header("3. Simulasi Resource Leakage & File Descriptor Exhaustion (Errno::EMFILE)")
    print(f"{BOLD}Konsep Ruby:{RESET} Lupa memanggil close (membuka file tanpa block atau tanpa ensure)")
    print("akan menahan FD di Kernel table hingga batas OS tercapai (Errno::EMFILE).\n")

    leaked_handles = []
    print(f"{BOLD}Membuka stream berulang-ulang tanpa memanggil close():{RESET}")
    try:
        count = 1
        while True:
            file_name = f"tmp/worker_job_{count}.tmp"
            io_obj = SimulatedRubyIO(kernel, file_name)
            io_obj.write(f"Job data #{count}\n".encode())
            # SENGAJA TIDAK DI-CLOSE (RESOURCE LEAK)
            leaked_handles.append(io_obj)
            print(f"  {YELLOW}[LEAK]{RESET} Alokasi {file_name} -> Menahan FD {io_obj.fd}")
            count += 1
            time.sleep(0.05)
    except OSError as e:
        print(f"\n{RED}{BOLD}[CRASH DITIRUKAN]: {e}{RESET}")
        print(f"{RED}Kernel menolak membuka koneksi baru karena FD table penuh!{RESET}")

    kernel.render_fd_table()

    print(f"{BOLD}Membersihkan handle yang bocor secara manual...{RESET}")
    for h in leaked_handles:
        h.close()
    print(f"{GREEN}Semua resource leak telah dinormalisasi.{RESET}")
    kernel.render_fd_table()

def demo_finalizer_concept():
    print_header("4. ObjectSpace.define_finalizer vs Deterministic Cleanup")
    print(f"{BOLD}Konsep Ruby:{RESET}")
    print("  - Ruby menyediakan ObjectSpace.define_finalizer sebagai jaring pengaman (safety net).")
    print("  - Namun, garbage collector (GC) bersifat non-deterministik! File Descriptor bisa")
    print("    habis jauh sebelum siklus GC berjalan.")
    print("  - JANGAN PERNAH mengandalkan finalizer untuk manajemen file/socket primer!\n")

    class RubyObjectWithFinalizer:
        def __init__(self, name: str, fd_id: int):
            self.name = name
            self.fd_id = fd_id
            print(f"  ObjectSpace: Mendaftarkan finalizer untuk objek '{self.name}' (FD {self.fd_id})")

        def simulate_gc_sweep(self):
            print(f"  {MAGENTA}[GC Finalizer Hook]{RESET} Membebaskan FD {self.fd_id} milik '{self.name}' saat GC Mark & Sweep")

    obj = RubyObjectWithFinalizer("EphemeralSocket", 9)
    print(f"  Objek kehilangan referensi (scope berakhir)...")
    print(f"  {YELLOW}[Warning]: FD 9 masih menggantung sampai GC memutuskan melakukan sweep!{RESET}")
    time.sleep(0.2)
    obj.simulate_gc_sweep()
    print(f"  {GREEN}[Kesimpulan]: Selalu gunakan blok File.open {{ ... }} untuk deterministik.{RESET}\n")

def run_all_interactive_simulations():
    print(f"{BOLD}{GREEN}=== SIMULASI INTERAKTIF: RUBY RESOURCE MANAGEMENT & LOW-LEVEL I/O ==={RESET}")
    print(f"Direktori Target: hands-on/m01/lab_exercise.py | Ruby Standard Spec\n")
    
    kernel = VirtualKernel(max_descriptors=8)

    demo_buffering(kernel)
    demo_block_cleanup(kernel)
    demo_fd_leak_and_exhaustion(kernel)
    demo_finalizer_concept()

    print(f"{BOLD}{GREEN}Seluruh demonstrasi simulasi selesai 100% tanpa error.{RESET}")
    print(f"{CYAN}{'=' * 72}{RESET}\n")

if __name__ == "__main__":
    run_all_interactive_simulations()
