#!/usr/bin/env python3
"""
Lab Hands-on: C System Programming - Deep Dive
Bab 08: I/O Tingkat Rendah, File Descriptor, & POSIX Syscalls

Skrip ini mendemonstrasikan implementasi tingkat rendah dari konsep POSIX I/O:
1. Manipulasi raw File Descriptor (FD) menggunakan syscall langsung (os.open, os.read, os.write, os.lseek).
2. I/O Redirection & FD Duplication menggunakan dup() & dup2() (seperti implementasi Shell Redirection).
3. Inter-Process Communication (IPC) via POSIX Anonymous Pipes & Non-blocking I/O.
4. Analisis biaya Context Switching syscall (Micro-benchmark Write Granularity).
"""

import os
import sys
import time
import struct
import tempfile
import errno

# Konfigurasi Visual Output (ANSI Escape Codes)
CLR_RESET  = "\033[0m"
CLR_BOLD   = "\033[1m"
CLR_RED    = "\033[31m"
CLR_GREEN  = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE   = "\033[34m"
CLR_CYAN   = "\033[36m"

def print_header(title: str):
    print(f"\n{CLR_BOLD}{CLR_CYAN}{'=' * 75}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}[POSIX SYSCALL LAB] {title.upper()}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}{'=' * 75}{CLR_RESET}")

def print_step(step_num: int, desc: str):
    print(f"\n{CLR_BOLD}{CLR_YELLOW}>>> Langkah {step_num}: {desc}{CLR_RESET}")

def inspect_fd(fd: int, tag: str = ""):
    """Mengambil status metadata dari raw File Descriptor melalui fstat()."""
    stat_res = os.fstat(fd)
    flags_info = f"Inode={stat_res.st_ino}, Size={stat_res.st_size}B, Mode={oct(stat_res.st_mode)}"
    print(f"  {CLR_BLUE}[FD {fd:02d}]{CLR_RESET} {tag:<22} -> {flags_info}")

def demo_raw_fd_lifecycle():
    """
    Simulasi siklus hidup File Descriptor, bitwise open flags,
    dan pointer positioning menggunakan lseek (SEEK_SET, SEEK_CUR, SEEK_END).
    """
    print_header("Modul 1: Siklus Hidup File Descriptor & Pointer lseek()")

    # File temporer untuk low-level manipulation
    tmp_path = os.path.join(tempfile.gettempdir(), "posix_io_raw_lab.bin")
    
    print_step(1, "Membuka file menggunakan os.open() dengan bitwise flags POSIX")
    # O_RDWR | O_CREAT | O_TRUNC setara dengan fopen(..., "wb+") tingkat C
    # Mode 0o644 -> rw-r--r--
    fd = os.open(tmp_path, os.O_RDWR | os.O_CREAT | os.O_TRUNC, 0o644)
    inspect_fd(fd, "Target File Descriptor")

    print_step(2, "Menulis data terstruktur biner menggunakan raw os.write()")
    # Format biner C-struct: uint32_t ID, char[16] Name, double Balance
    record_format = "=I16sd"
    records = [
        (101, b"Alpha-Kernel\x00\x00\x00\x00", 1250.75),
        (102, b"Beta-POSIX\x00\x00\x00\x00\x00\x00", 8450.50),
        (103, b"Gamma-Driver\x00\x00\x00\x00", 3120.00)
    ]
    
    total_bytes = 0
    for r in records:
        raw_payload = struct.pack(record_format, *r)
        written = os.write(fd, raw_payload)
        total_bytes += written
    print(f"  {CLR_GREEN}Berhasil menulis {len(records)} record ({total_bytes} bytes).{CLR_RESET}")

    print_step(3, "Manipulasi file offset menggunakan os.lseek()")
    record_size = struct.calcsize(record_format)
    
    # Lompat ke Record Index 1 (Beta-POSIX) dari awal file
    offset_target = record_size * 1
    new_offset = os.lseek(fd, offset_target, os.SEEK_SET)
    print(f"  lseek(fd, {offset_target}, SEEK_SET) -> Offset sekarang: {new_offset}")

    raw_data = os.read(fd, record_size)
    rid, name_raw, bal = struct.unpack(record_format, raw_data)
    name = name_raw.decode('latin1').strip('\x00')
    print(f"  {CLR_GREEN}Data Terbaca [Index 1]: ID={rid}, Name='{name}', Balance={bal}{CLR_RESET}")

    # Patch data in-place: update balance Record 1 langsung pada disk
    os.lseek(fd, -record_size, os.SEEK_CUR)  # Mundur 1 record dari posisi saat ini
    updated_payload = struct.pack(record_format, rid, name_raw, 9999.99)
    os.write(fd, updated_payload)
    print(f"  In-place binary patch diterapkan pada record ID={rid}.")

    # Verifikasi modifikasi
    os.lseek(fd, offset_target, os.SEEK_SET)
    verif_data = os.read(fd, record_size)
    _, _, verif_bal = struct.unpack(record_format, verif_data)
    print(f"  {CLR_GREEN}Verifikasi Modifikasi: Balance Baru = {verif_bal}{CLR_RESET}")

    # Bersihkan file descriptor
    os.close(fd)
    if os.path.exists(tmp_path):
        os.unlink(tmp_path)

def demo_dup_redirection():
    """
    Simulasi mekanisme shell redirection ('echo test > file.txt')
    menggunakan syscall dup() dan dup2() pada level kernel.
    """
    print_header("Modul 2: FD Redirection via dup() & dup2()")

    log_path = os.path.join(tempfile.gettempdir(), "stdout_capture.log")
    log_fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)

    print_step(1, "Menyimpan referensi asli STDOUT (FD 1) menggunakan os.dup()")
    stdout_backup_fd = os.dup(1)
    inspect_fd(1, "STDOUT Asli (Console)")
    inspect_fd(stdout_backup_fd, "Backup STDOUT")

    print_step(2, "Mengarahkan FD 1 ke Log File menggunakan os.dup2()")
    # dup2 secara atomik menutup FD 1 dan menggantikannya dengan log_fd
    sys.stdout.flush()  # Kosongkan buffer user-space sebelum syscall
    os.dup2(log_fd, 1)

    # Teks berikut ditulis ke FD 1, namun kernel mengarahkannya ke log_path
    print("[INTERNAL_KERNEL_LOG] Kernel tracing initialized.")
    print("[INTERNAL_KERNEL_LOG] Allocating page frame pool: 4096 pages.")
    print("[INTERNAL_KERNEL_LOG] Virtual File System (VFS) mount ready.")
    sys.stdout.flush()

    # Kembalikan STDOUT asli
    os.dup2(stdout_backup_fd, 1)
    os.close(stdout_backup_fd)
    os.close(log_fd)

    print_step(3, "STDOUT Dikembalikan. Membaca isi file hasil pengalihan (redirection):")
    with open(log_path, "r") as f:
        content = f.read()
    for line in content.strip().split("\n"):
        print(f"  {CLR_CYAN}|>> {line}{CLR_RESET}")
    
    if os.path.exists(log_path):
        os.unlink(log_path)

def demo_pipe_nonblocking_io():
    """
    Simulasi POSIX Anonymous Pipe dengan Non-blocking I/O.
    Mendemonstrasikan penanganan error EAGAIN / EWOULDBLOCK.
    """
    print_header("Modul 3: POSIX Pipe & Non-blocking I/O (IPC Engine)")

    print_step(1, "Membuat anonymous pipe via os.pipe()")
    r_fd, w_fd = os.pipe()
    inspect_fd(r_fd, "Pipe Read End")
    inspect_fd(w_fd, "Pipe Write End")

    print_step(2, "Mengubah Read End menjadi mode Non-blocking")
    # Mengeset flag O_NONBLOCK pada read end
    os.set_blocking(r_fd, False)

    print_step(3, "Mencoba membaca dari pipe kosong (handling EAGAIN/EWOULDBLOCK)")
    try:
        data = os.read(r_fd, 128)
        print(f"  Mendapat data tak terduga: {data}")
    except BlockingIOError as err:
        print(f"  {CLR_RED}Expected Syscall Error: errno={err.errno} ({errno.errorcode[err.errno]} - {os.strerror(err.errno)}){CLR_RESET}")
        print(f"  -> Data belum tersedia; kernel tidak men-suspend process berkat O_NONBLOCK.")

    print_step(4, "Menulis dan mengonsumsi data atomic via pipe")
    message = b"MSG_PACKET_ID_99824_STATUS_OK"
    bytes_written = os.write(w_fd, message)
    print(f"  Menulis {bytes_written} bytes ke Write End (FD {w_fd}).")

    received = os.read(r_fd, 128)
    print(f"  {CLR_GREEN}Berhasil membaca dari Read End (FD {r_fd}): '{received.decode('utf-8')}'{CLR_RESET}")

    os.close(r_fd)
    os.close(w_fd)

def benchmark_syscall_overhead():
    """
    Mengukur biaya overhead syscall (Context Switch User Space <-> Kernel Space)
    berdasarkan variasi ukuran buffer write.
    """
    print_header("Modul 4: Syscall Granularity & Kernel Overhead Benchmark")
    
    total_data_size = 1 * 1024 * 1024  # 1 MegaByte
    buffer_sizes = [1, 64, 1024, 4096, 65536]
    dummy_path = os.path.join(tempfile.gettempdir(), "syscall_bench.dat")

    print(f"{'Buffer Size':<15} | {'Syscall Invocations':<20} | {'Elapsed Time (s)':<18} | {'Throughput (MB/s)':<18}")
    print("-" * 75)

    for buf_size in buffer_sizes:
        payload = b"X" * buf_size
        num_writes = total_data_size // buf_size
        
        fd = os.open(dummy_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
        
        start_time = time.perf_counter()
        for _ in range(num_writes):
            os.write(fd, payload)
        end_time = time.perf_counter()
        
        os.close(fd)

        elapsed = end_time - start_time
        throughput = (total_data_size / (1024 * 1024)) / elapsed if elapsed > 0 else 0.0
        
        print(f"{buf_size:<15} | {num_writes:<20} | {elapsed:<18.5f} | {throughput:<18.2f}")

    if os.path.exists(dummy_path):
        os.unlink(dummy_path)

if __name__ == "__main__":
    print(f"{CLR_BOLD}LAB POSIX I/O & FILE DESCRIPTORS (C SYSTEM PROGRAMMING DEEP DIVE){CLR_RESET}")
    print(f"PID: {os.getpid()} | Arsitektur POSIX Compatible")

    try:
        demo_raw_fd_lifecycle()
        demo_dup_redirection()
        demo_pipe_nonblocking_io()
        benchmark_syscall_overhead()
        
        print(f"\n{CLR_BOLD}{CLR_GREEN}[+] SELURUH LAB LOW-LEVEL I/O BERHASIL DI-EKSEKUSI SEMPURNA.{CLR_RESET}\n")
    except Exception as exc:
        print(f"\n{CLR_RED}[!] Error Fatal dalam Eksekusi Lab: {exc}{CLR_RESET}")
        sys.exit(1)