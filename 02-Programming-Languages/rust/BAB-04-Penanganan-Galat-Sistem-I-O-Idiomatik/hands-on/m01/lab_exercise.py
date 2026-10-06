#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Fondasi Penanganan Galat & Sistem I/O Idiomatik Rust
BAB-04: Penanganan Galat & Sistem I/O Idiomatik

Skrip ini mereplikasi semantik penanganan galat Rust secara interaktif:
1. Tipe Aljabar Result<T, E> dan Option<T>
2. Operator Penjalaran Galat '?' (Early Return / Error Propagation)
3. Hierarki Galat Idiomatik (std::error::Error trait & chaining source)
4. I/O Berpenyangga (BufReader vs Unbuffered I/O)
"""

import sys
import time
from typing import Generic, TypeVar, Callable, Any, Optional, Union, List

# ANSI Color Codes untuk visualisasi terminal
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"

T = TypeVar('T')
E = TypeVar('E')
U = TypeVar('U')


# ============================================================================
# 1. EMULASI TIPE RESULT<T, E> & OPTION<T> RUST
# ============================================================================

class RustPanic(Exception):
    """Representasi thread panic! pada Rust (galat fatal tak tertangani)."""
    pass


class Result(Generic[T, E]):
    """Emulasi std::result::Result<T, E> dari Rust standard library."""
    
    def __init__(self, value: Optional[T] = None, error: Optional[E] = None, is_ok: bool = True):
        self._val = value
        self._err = error
        self._is_ok = is_ok

    @staticmethod
    def Ok(val: T) -> 'Result[T, E]':
        return Result(value=val, error=None, is_ok=True)

    @staticmethod
    def Err(err: E) -> 'Result[T, E]':
        return Result(value=None, error=err, is_ok=False)

    def is_ok(self) -> bool:
        return self._is_ok

    def is_err(self) -> bool:
        return not self._is_ok

    def unwrap(self) -> T:
        if self._is_ok:
            return self._val  # type: ignore
        raise RustPanic(f"called `Result::unwrap()` on an `Err` value: {self._err}")

    def expect(self, msg: str) -> T:
        if self._is_ok:
            return self._val  # type: ignore
        raise RustPanic(f"{msg}: {self._err}")

    def unwrap_or(self, default: T) -> T:
        return self._val if self._is_ok else default  # type: ignore

    def unwrap_or_else(self, op: Callable[[E], T]) -> T:
        return self._val if self._is_ok else op(self._err)  # type: ignore

    def map(self, op: Callable[[T], U]) -> 'Result[U, E]':
        if self._is_ok:
            return Result.Ok(op(self._val))  # type: ignore
        return Result.Err(self._err)  # type: ignore

    def and_then(self, op: Callable[[T], 'Result[U, E]']) -> 'Result[U, E]':
        if self._is_ok:
            return op(self._val)  # type: ignore
        return Result.Err(self._err)  # type: ignore

    def __repr__(self) -> str:
        if self._is_ok:
            return f"{Style.GREEN}Ok({self._val}){Style.RESET}"
        return f"{Style.RED}Err({self._err}){Style.RESET}"


# ============================================================================
# 2. HIERARKI GALAT & CHAINING CAUSE (std::error::Error)
# ============================================================================

class RustError:
    """Emulasi std::error::Error trait dengan pelacakan rantai penyebab."""
    def __init__(self, message: str, source: Optional['RustError'] = None):
        self.message = message
        self.source_err = source

    def source(self) -> Optional['RustError']:
        return self.source_err

    def __str__(self) -> str:
        return self.message

    def display_chain(self) -> str:
        chain = [f"{Style.RED}{self.message}{Style.RESET}"]
        curr = self.source_err
        depth = 1
        while curr:
            indent = "  " * depth
            chain.append(f"{indent}↳ {Style.YELLOW}Caused by: {curr.message}{Style.RESET}")
            curr = curr.source()
            depth += 1
        return "\n".join(chain)


class IoError(RustError):
    pass

class ParseIntError(RustError):
    pass

class ConfigError(RustError):
    pass


# ============================================================================
# 3. SIMULASI OPERATOR '?' (PROPAGASI GALAT)
# ============================================================================

class EarlyReturnErr(Exception):
    """Mekanisme early return untuk mereplikasi semantik '?' di fungsi Rust."""
    def __init__(self, err_val: Any):
        self.err_val = err_val


def try_op(res: Result[T, E]) -> T:
    """Emulasi operator '?' pada ekspresi Result di Rust."""
    if res.is_err():
        raise EarlyReturnErr(res._err)
    return res._val  # type: ignore


def rust_fn(func: Callable[..., Any]) -> Callable[..., Result[Any, Any]]:
    """Dekorator untuk fungsi yang mengembalikan Result via operator '?'."""
    def wrapper(*args: Any, **kwargs: Any) -> Result[Any, Any]:
        try:
            return Result.Ok(func(*args, **kwargs))
        except EarlyReturnErr as e:
            return Result.Err(e.err_val)
    return wrapper


# ============================================================================
# 4. SIMULASI SISTEM I/O IDIOMATIK (BufReader & Read Stream)
# ============================================================================

class VirtualBuffer:
    """Simulasi in-memory stream untuk mengilustrasikan Read + BufReader."""
    def __init__(self, content: bytes):
        self._content = content
        self._pos = 0
        self.syscall_count = 0

    def read_exact_unbuffered(self, chunk_size: int = 1) -> bytes:
        """Membaca sedikit demi sedikit langsung tanpa buffer (banyak syscall)."""
        if self._pos >= len(self._content):
            return b""
        self.syscall_count += 1
        chunk = self._content[self._pos:self._pos + chunk_size]
        self._pos += len(chunk)
        return chunk


class BufReaderSimulator:
    """Simulasi std::io::BufReader dengan kapasitas internal 64-byte."""
    def __init__(self, source: VirtualBuffer, capacity: int = 64):
        self.source = source
        self.capacity = capacity
        self.internal_buffer = b""
        self.buffer_pos = 0
        self.reads_served = 0

    def read_line(self) -> Result[str, IoError]:
        line_bytes = bytearray()
        while True:
            # Isi internal buffer jika kosong
            if self.buffer_pos >= len(self.internal_buffer):
                chunk = self.source.read_exact_unbuffered(self.capacity)
                if not chunk:
                    break
                self.internal_buffer = chunk
                self.buffer_pos = 0

            b = self.internal_buffer[self.buffer_pos:self.buffer_pos+1]
            self.buffer_pos += 1
            self.reads_served += 1
            line_bytes.extend(b)
            if b == b"\n":
                break

        if not line_bytes:
            return Result.Ok("")
        try:
            decoded = line_bytes.decode('utf-8').rstrip('\r\n')
            return Result.Ok(decoded)
        except Exception as e:
            return Result.Err(IoError(f"UTF-8 decode error: {e}"))


# ============================================================================
# 5. STUDI KASUS PIPELINE PARSER KONFIGURASI
# ============================================================================

def parse_port(raw: str) -> Result[int, ParseIntError]:
    raw = raw.strip()
    if not raw.isdigit():
        return Result.Err(ParseIntError(f"Invalid integer format: '{raw}'"))
    port = int(raw)
    if not (1 <= port <= 65535):
        return Result.Err(ParseIntError(f"Port out of range [1-65535]: {port}"))
    return Result.Ok(port)


@rust_fn
def load_server_config(raw_input: str) -> dict:
    """
    Menyerupai fungsi Rust:
    fn load_server_config(raw: &str) -> Result<Config, ConfigError>
    """
    lines = raw_input.strip().split("\n")
    config = {}
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            # Early return galat via try_op
            try_op(Result.Err(ConfigError(f"Malformed line: '{line}'")))
        
        key, val = line.split("=", 1)
        key, val = key.strip(), val.strip()
        
        if key == "PORT":
            # Propagasi galat dari parse_port ke ConfigError (Chaining)
            parsed = parse_port(val)
            if parsed.is_err():
                chained = ConfigError("Failed to parse PORT setting", source=parsed._err)
                try_op(Result.Err(chained))
            config["port"] = parsed._val
        elif key == "HOST":
            config["host"] = val
        elif key == "WORKERS":
            try_op(Result.Ok(val))
            config["workers"] = int(val) if val.isdigit() else 1

    if "port" not in config:
        try_op(Result.Err(ConfigError("Missing required key 'PORT'")))
        
    return config


# ============================================================================
# 6. RUNNER INTERAKTIF & LAB WORKFLOW
# ============================================================================

def header(title: str) -> None:
    print(f"\n{Style.BOLD}{Style.CYAN}{'='*60}{Style.RESET}")
    print(f"{Style.BOLD}{Style.CYAN} {title} {Style.RESET}")
    print(f"{Style.BOLD}{Style.CYAN}{'='*60}{Style.RESET}")


def run_lab_result_patterns() -> None:
    header("LAB 1: Pola Ekstraksi Result<T, E> (unwrap vs match)")
    print(f"{Style.DIM}Di Rust, unwrap() sembrono memicu panic! Penanganan idiomatik menggunakan match.{Style.RESET}\n")

    res_ok: Result[int, str] = Result.Ok(42)
    res_err: Result[int, str] = Result.Err("Koneksi ditolak oleh peer")

    print(f"1. Eksplorasi nilai Ok:")
    print(f"   Objek: {res_ok}")
    print(f"   is_ok(): {res_ok.is_ok()}, unwrap(): {res_ok.unwrap()}")

    print(f"\n2. Eksplorasi nilai Err:")
    print(f"   Objek: {res_err}")
    print(f"   unwrap_or(0): {Style.GREEN}{res_err.unwrap_or(0)}{Style.RESET}")
    print(f"   unwrap_or_else(): {res_err.unwrap_or_else(lambda e: -1)}")

    print(f"\n3. Simulasi panic pada unwrap():")
    try:
        res_err.unwrap()
    except RustPanic as p:
        print(f"   {Style.BG_RED}{Style.BOLD} PANIC THREAD {Style.RESET} {Style.RED}{p}{Style.RESET}")


def run_lab_question_mark_propagation() -> None:
    header("LAB 2: Operator Penjalaran Galat '?' & Chaining")
    print(f"{Style.DIM}Simulasi operator '?' Rust yang menghentikan eksekusi dan mengembalikan Err secara instan.{Style.RESET}\n")

    valid_conf = "HOST = 127.0.0.1\nPORT = 8080\nWORKERS = 4"
    invalid_port_conf = "HOST = 0.0.0.0\nPORT = bukan_angka\nWORKERS = 2"
    syntax_error_conf = "HOST = 0.0.0.0\nINI_BARIS_RUSAK_TANPA_SAMA_DENGAN"

    configs = [
        ("Konfigurasi Valid", valid_conf),
        ("Konfigurasi Galat Parse (Port)", invalid_port_conf),
        ("Konfigurasi Sintaks Malformed", syntax_error_conf)
    ]

    for label, raw in configs:
        print(f"\n--- Menguji: {Style.BOLD}{label}{Style.RESET} ---")
        outcome = load_server_config(raw)
        if outcome.is_ok():
            print(f"  Status: {Style.GREEN}BERHASIL MEMUAT{Style.RESET}")
            print(f"  Hasil Config: {outcome._val}")
        else:
            print(f"  Status: {Style.RED}GAGAL (Early Return via '?'){Style.RESET}")
            err = outcome._err
            if isinstance(err, RustError):
                print(f"  Hierarki Galat:")
                print(err.display_chain())


def run_lab_buffered_io() -> None:
    header("LAB 3: Efisiensi Idiomatik I/O (BufReader vs Raw Syscalls)")
    print(f"{Style.DIM}Membandingkan jumlah syscall/disk hit pembacaan baris dengan dan tanpa penyangga (buffer).{Style.RESET}\n")

    raw_text = (
        "baris_1: inisialisasi daemon\n"
        "baris_2: konfigurasi port 9000 dimuat\n"
        "baris_3: socket mendengarkan paket masuk\n"
        "baris_4: sinyal heartbeat terkirim\n"
        "baris_5: koneksi ditutup secara rapi\n"
    ).encode('utf-8')

    print(f"Total ukuran data teks: {len(raw_text)} byte.")

    # Simulasi 1: Tanpa Penyangga (Unbuffered per byte)
    unbuf_stream = VirtualBuffer(raw_text)
    total_unbuf_reads = 0
    while True:
        b = unbuf_stream.read_exact_unbuffered(1)
        if not b:
            break
        total_unbuf_reads += 1

    # Simulasi 2: Dengan Penyangga (BufReader 64-byte chunks)
    buf_stream = VirtualBuffer(raw_text)
    reader = BufReaderSimulator(buf_stream, capacity=64)
    lines_read = 0
    while True:
        line_res = reader.read_line()
        if line_res.is_err() or line_res._val == "":
            break
        lines_read += 1

    print(f"\nHasil Pengujian Komparasi I/O:")
    print(f"  {Style.YELLOW}[Unbuffered 1-byte]{Style.RESET} Syscall/Hit ke Media: {Style.BOLD}{unbuf_stream.syscall_count}{Style.RESET} kali")
    print(f"  {Style.GREEN}[BufReader 64-byte]{Style.RESET} Syscall/Hit ke Media: {Style.BOLD}{buf_stream.syscall_count}{Style.RESET} kali")
    reduction = ((unbuf_stream.syscall_count - buf_stream.syscall_count) / unbuf_stream.syscall_count) * 100
    print(f"  Efisiensi Pengurangan Syscall: {Style.BOLD}{Style.GREEN}{reduction:.1f}%{Style.RESET}")


def interactive_menu() -> None:
    while True:
        print(f"\n{Style.BOLD}{Style.MAGENTA}=== LAB INTERAKTIF RUST: BAB 04 PENANGANAN GALAT & I/O ==={Style.RESET}")
        print("1. Jalankan Lab 1: Pola Ekstraksi Result<T, E> & Panic Safety")
        print("2. Jalankan Lab 2: Operator Penjalaran '?' & Chaining std::error::Error")
        print("3. Jalankan Lab 3: Simulasi Efisiensi BufReader vs Unbuffered I/O")
        print("4. Jalankan Seluruh Skenario (Automated Suite)")
        print("5. Keluar")
        
        try:
            choice = input(f"\n{Style.BOLD}Pilih opsi [1-5]: {Style.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar dari simulasi.")
            break

        if choice == "1":
            run_lab_result_patterns()
        elif choice == "2":
            run_lab_question_mark_propagation()
        elif choice == "3":
            run_lab_buffered_io()
        elif choice == "4":
            run_lab_result_patterns()
            run_lab_question_mark_propagation()
            run_lab_buffered_io()
        elif choice == "5":
            print(f"{Style.GREEN}Selesai. Terima kasih!{Style.RESET}")
            break
        else:
            print(f"{Style.RED}Pilihan tidak valid. Silakan coba lagi.{Style.RESET}")


if __name__ == "__main__":
    # Jika dijalankan secara non-interaktif (piped atau argumen --all)
    if len(sys.argv) > 1 and sys.argv[1] == "--all" or not sys.stdin.isatty():
        run_lab_result_patterns()
        run_lab_question_mark_propagation()
        run_lab_buffered_io()
    else:
        interactive_menu()
