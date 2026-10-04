#!/usr/bin/env python3
"""
Lab Hands-on: C Programming - Chapter 05
Topik: Array, String Idiom, & Zero-Copy Buffer Processing (Modul 02 Deep Dive)

Skrip ini memodelkan dan mensimulasikan mekanisme inti bahasa C:
1. Idiom Null-Terminated String & Emulasi Operasi Buffer Aman (strlcpy / boundary check).
2. Zero-Copy Network Frame Parsing menggunakan Python memoryview (memetakan pointer/offset C).
3. Benchmark kuantitatif: Alokasi & Penyalinan Tradisional vs Zero-Copy Slice.
"""

import sys
import time
import struct
import os

# --- ANSI Formatting Constants ---
CLR_RESET  = "\033[0m"
CLR_BOLD   = "\033[1m"
CLR_RED    = "\033[31m"
CLR_GREEN  = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_CYAN   = "\033[36m"
CLR_MAG    = "\033[35m"

def log_header(title: str):
    print(f"\n{CLR_BOLD}{CLR_CYAN}{'='*75}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN} [LAB] {title.upper()}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}{'='*75}{CLR_RESET}")

def log_step(step: str, desc: str):
    print(f"\n{CLR_BOLD}{CLR_MAG}[STEP] {step}:{CLR_RESET} {desc}")

def log_info(key: str, val: str):
    print(f"  {CLR_YELLOW}* {key:<24}:{CLR_RESET} {val}")

def log_success(msg: str):
    print(f"  {CLR_GREEN}✓ {msg}{CLR_RESET}")

def log_warn(msg: str):
    print(f"  {CLR_RED}! {msg}{CLR_RESET}")


# ==============================================================================
# 1. EMULASI C-STYLE BUFFER & NULL-TERMINATED STRING IDIOM
# ==============================================================================
class CStringBuffer:
    """
    Memodelkan array karakter C statis berukuran tetap: char buffer[CAPACITY].
    Menunjukkan bahaya buffer overflow, idiom terminasi null (\0),
    dan implementasi fungsi aman setara strlcpy().
    """
    def __init__(self, capacity: int):
        self.capacity = capacity
        # Alokasikan memori contiguous mentah diisi dengan nilai sentinel (0xAA)
        self.raw_mem = bytearray(b'\xAA' * capacity)
        self.raw_mem[0] = 0  # Inisialisasi string kosong: buffer[0] = '\0'

    def c_strlen(self) -> int:
        """Menghitung panjang string C dengan scanning byte hingga '\\0'."""
        for i in range(self.capacity):
            if self.raw_mem[i] == 0:
                return i
        return self.capacity

    def strlcpy(self, src: bytes) -> int:
        """
        Implementasi idiom BSD/C strlcpy(char *dst, const char *src, size_t siz).
        Menjamin null-termination dan mencegah overflow.
        Return: panjang string sumber yang ingin dibuat.
        """
        src_len = len(src)
        if self.capacity == 0:
            return src_len

        # Salin byte maksimal sejumlah capacity - 1
        copy_len = min(src_len, self.capacity - 1)
        for i in range(copy_len):
            self.raw_mem[i] = src[i]

        # Selalu jamin null-terminated
        self.raw_mem[copy_len] = 0x00
        return src_len

    def inspect_raw(self) -> str:
        """Memeriksa isi hexdump mentah dari memori fisik buffer."""
        return " ".join(f"{b:02X}" for b in self.raw_mem)

    def read_string(self) -> str:
        length = self.c_strlen()
        return self.raw_mem[:length].decode('ascii', errors='replace')


# ==============================================================================
# 2. ZERO-COPY FRAME PARSER (C STRUCT / POINTER SLICING MODEL)
# ==============================================================================
class ZeroCopyPacketParser:
    """
    Memodelkan Zero-Copy Ingest Buffer di layer Kernel/Drivers C.
    Header Frame:
      - Magic Byte: 2 bytes [0x5A, 0xA5]
      - Stream ID : 2 bytes (uint16_t, Big Endian)
      - Payload Len: 4 bytes (uint32_t, Big Endian)
      Total Header = 8 bytes.
    Payload langsung diakses via memoryview tanpa malloc/memcpy.
    """
    HEADER_STRUCT = "!HHI"
    HEADER_SIZE = struct.calcsize(HEADER_STRUCT)
    MAGIC_EXPECTED = 0x5AA5

    def __init__(self, raw_buffer: bytearray):
        # memoryview mengekspos C-level Buffer Protocol (pointer mentah)
        self.view = memoryview(raw_buffer)

    def parse_frame(self, offset: int):
        """Membedah frame tanpa alokasi memori payload."""
        if offset + self.HEADER_SIZE > len(self.view):
            raise ValueError("Buffer underflow saat membaca header")

        magic, stream_id, payload_len = struct.unpack_from(self.HEADER_STRUCT, self.view, offset)

        if magic != self.MAGIC_EXPECTED:
            raise ValueError(f"Magic byte tidak valid: {hex(magic)}")

        payload_offset = offset + self.HEADER_SIZE
        if payload_offset + payload_len > len(self.view):
            raise ValueError("Payload terpotong (truncated packet)")

        # ZERO-COPY SLICE: membuat memoryview baru yang menunjuk ke memori asal
        payload_view = self.view[payload_offset : payload_offset + payload_len]
        total_frame_len = self.HEADER_SIZE + payload_len

        return stream_id, payload_view, total_frame_len


# ==============================================================================
# 3. BENCHMARKING: MEMCPY (TRADISIONAL) VS ZERO-COPY (MEMORYVIEW)
# ==============================================================================
def run_benchmark(payload_size_mb: int = 64, iterations: int = 50):
    log_header("3. Benchmark Zero-Copy vs Deep-Copy Buffer")

    total_bytes = payload_size_mb * 1024 * 1024
    log_info("Ukuran Payload Induk", f"{payload_size_mb} MB ({total_bytes:,} bytes)")
    log_info("Iterasi Pengujian", f"{iterations} kali slice window")

    # Inisialisasi chunk besar (simulasi DMA transfer buffer)
    master_buffer = bytearray(os.urandom(total_bytes))
    slice_size = 10 * 1024 * 1024  # 10 MB per slice window
    start_pos = 1024 * 1024        # Mulai offset 1MB

    # Evaluasi Salinan Standar (Traditional Memcpy)
    t0 = time.perf_counter()
    for _ in range(iterations):
        # Slicing bytearray/bytes biasa selalu memicu malloc() dan memcpy() baru
        copied_chunk = master_buffer[start_pos : start_pos + slice_size]
        _ = copied_chunk[0]  # Read operation
    t_copy = time.perf_counter() - t0

    # Evaluasi Zero-Copy (Pointer/Memoryview Window)
    mem_view = memoryview(master_buffer)
    t0 = time.perf_counter()
    for _ in range(iterations):
        # Zero-copy slicing: hanya mengalokasikan struct metadata kecil, data tidak disalin
        zc_chunk = mem_view[start_pos : start_pos + slice_size]
        _ = zc_chunk[0]  # Read operation
    t_zerocopy = time.perf_counter() - t0

    log_info("Waktu Copy Tradisional", f"{t_copy * 1000:.3f} ms")
    log_info("Waktu Zero-Copy", f"{t_zerocopy * 1000:.3f} ms")
    
    speedup = t_copy / t_zerocopy if t_zerocopy > 0 else float('inf')
    print(f"\n  {CLR_BOLD}{CLR_GREEN}» Akselerasi Kinerja Zero-Copy: {speedup:.2f}x LEBIH CEPAT{CLR_RESET}")


# ==============================================================================
# MAIN EXECUTION PIPELINE
# ==============================================================================
def main():
    print(f"{CLR_BOLD}{CLR_CYAN}Sistem Simulasi C Memory & Buffer Pipeline v1.0{CLR_RESET}")
    print("Mengeksekusi demonstrasi mendalam array, string buffer, dan zero-copy idioms...\n")

    # --- BAGIAN 1: Null-Termination & Safe Buffer Sizing ---
    log_header("1. Emulasi C Null-Terminated Buffer & strlcpy")
    c_buf = CStringBuffer(capacity=16)

    log_step("1.1", "Inisialisasi Fixed-Size char buffer[16]")
    log_info("State Memori Awal", c_buf.inspect_raw())
    log_info("c_strlen() terdeteksi", str(c_buf.c_strlen()))

    log_step("1.2", "Menulis string pendek (Safe Bound)")
    input_str_1 = b"UNIX-C"
    c_buf.strlcpy(input_str_1)
    log_info("String yang ditulis", input_str_1.decode())
    log_info("State Memori Fisik", c_buf.inspect_raw())
    log_info("c_strlen() aktual", str(c_buf.c_strlen()))
    log_info("String terparse", c_buf.read_string())
    assert c_buf.read_string() == "UNIX-C"
    log_success("Data tersimpan dengan sentinel null terminator '\\0' yang tepat.")

    log_step("1.3", "Simulasi Pencegahan Buffer Overflow")
    overflow_str = b"SISTEM_OPERASI_TERDISTRIBUSI_MODERN"
    req_len = c_buf.strlcpy(overflow_str)
    log_info("Ukuran string sumber", f"{req_len} bytes")
    log_info("Kapasitas maksimum", f"{c_buf.capacity} bytes")
    log_info("State Memori Pasca-Truncate", c_buf.inspect_raw())
    log_info("Hasil Read Aman", c_buf.read_string())
    
    if req_len >= c_buf.capacity:
        log_warn("Truncation terdeteksi! String dipotong otomatis tanpa merusak frame memori sekitar.")
    assert c_buf.raw_mem[c_buf.capacity - 1] == 0x00
    log_success("Null-terminator byte terakhir dijamin aman oleh protokol strlcpy.")

    # --- BAGIAN 2: Network Frame Zero-Copy Parsing ---
    log_header("2. Zero-Copy Network Ingestion Pipeline")
    
    # Rakit raw network frame secara berurutan dalam memori
    packet_stream = bytearray()
    
    # Frame 1: Stream ID = 101, Payload = b"KERNEL_PACKET_A"
    p1 = b"KERNEL_PACKET_A"
    packet_stream.extend(struct.pack("!HHI", 0x5AA5, 101, len(p1)) + p1)
    
    # Frame 2: Stream ID = 202, Payload = b"MUTABLE_DMA_PAYLOAD"
    p2 = b"MUTABLE_DMA_PAYLOAD"
    packet_stream.extend(struct.pack("!HHI", 0x5AA5, 202, len(p2)) + p2)

    log_step("2.1", "Ingest Frame Stream ke Parser Zero-Copy")
    parser = ZeroCopyPacketParser(packet_stream)
    
    curr_offset = 0
    frame_idx = 1
    while curr_offset < len(packet_stream):
        stream_id, payload_view, frame_len = parser.parse_frame(curr_offset)
        
        log_info(f"Frame #{frame_idx} Offset", f"0x{curr_offset:04X} ({curr_offset} bytes)")
        log_info(f"Stream ID", str(stream_id))
        log_info(f"Payload Size", f"{len(payload_view)} bytes")
        log_info(f"Payload Content", bytes(payload_view).decode())
        
        # Demonstrasi In-Place Mutation tanpa alokasi baru
        if stream_id == 202:
            log_step("2.2", "Mutasi In-Place Memori via Pointer/Memoryview")
            log_info("Nilai awal buffer asli", bytes(packet_stream[curr_offset + 8 : curr_offset + frame_len]).decode())
            # Mengubah karakter pertama langsung di physical buffer via slice view
            payload_view[0:7] = b"DYNAMIC"
            log_info("Nilai buffer asli pasca-mutasi", bytes(packet_stream[curr_offset + 8 : curr_offset + frame_len]).decode())
            log_success("Mutasi berhasil tercermin pada buffer utama tanpa memcpy tambahan.")

        curr_offset += frame_len
        frame_idx += 1

    # --- BAGIAN 3: Benchmark Komparatif ---
    run_benchmark(payload_size_mb=48, iterations=100)

    log_header("Eksekusi Lab Selesai")
    print(f"{CLR_GREEN}Semua modul idiom C dan simulasi pointer zero-copy tervalidasi secara konsisten.{CLR_RESET}\n")

if __name__ == "__main__":
    main()