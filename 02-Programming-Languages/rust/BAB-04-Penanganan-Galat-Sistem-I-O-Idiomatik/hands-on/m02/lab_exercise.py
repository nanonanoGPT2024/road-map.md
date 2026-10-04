#!/usr/bin/env python3
"""
Lab Hands-on: Rust - Penanganan Galat & Sistem I/O Idiomatik
Modul: 04 - Deep Dive Engine

Deskripsi:
Skrip ini mensimulasikan sistem penanganan galat idiomatik Rust (Result<T, E>,
Option<T>, operator '?', map_err, and_then) serta arsitektur I/O ter-buffer 
(BufRead, Cursor, BufWriter) menggunakan paradigma algebraic data types murni
di Python tanpa library pihak ketiga.
"""

from __future__ import annotations
import sys
import time
import io
from typing import TypeVar, Generic, Callable, Union, Optional
from dataclasses import dataclass
from enum import Enum, auto

# ==============================================================================
# ANSI Escape Sequences untuk Presentasi Terminal
# ==============================================================================
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"

T = TypeVar("T")
U = TypeVar("U")
E = TypeVar("E")
F = TypeVar("F")

# ==============================================================================
# Model Tipe Data Aljabar: Option<T> & Result<T, E> (Idiom Rust)
# ==============================================================================
class Option(Generic[T]):
    """Implementasi monadic Option<T> menyerupai std::option::Option Rust."""
    
    def __init__(self, value: Optional[T], is_some: bool):
        self._value = value
        self._is_some = is_some

    @staticmethod
    def Some(val: T) -> Option[T]:
        return Option(val, True)

    @staticmethod
    def None_() -> Option[T]:
        return Option(None, False)

    def is_some(self) -> bool:
        return self._is_some

    def is_none(self) -> bool:
        return not self._is_some

    def unwrap(self) -> T:
        if not self._is_some:
            raise PanicException("called `Option::unwrap()` on a `None` value")
        return self._value  # type: ignore

    def unwrap_or(self, default: T) -> T:
        return self._value if self._is_some else default

    def map(self, f: Callable[[T], U]) -> Option[U]:
        return Option.Some(f(self._value)) if self._is_some else Option.None_()  # type: ignore


class Result(Generic[T, E]):
    """Implementasi monadic Result<T, E> menyerupai std::result::Result Rust."""

    def __init__(self, ok_val: Optional[T], err_val: Optional[E], is_ok: bool):
        self._ok = ok_val
        self._err = err_val
        self._is_ok = is_ok

    @staticmethod
    def Ok(val: T) -> Result[T, E]:
        return Result(val, None, True)

    @staticmethod
    def Err(err: E) -> Result[T, E]:
        return Result(None, err, False)

    def is_ok(self) -> bool:
        return self._is_ok

    def is_err(self) -> bool:
        return not self._is_ok

    def unwrap(self) -> T:
        if not self._is_ok:
            raise PanicException(f"called `Result::unwrap()` on an `Err` value: {self._err!r}")
        return self._ok  # type: ignore

    def unwrap_or(self, default: T) -> T:
        return self._ok if self._is_ok else default

    def map(self, f: Callable[[T], U]) -> Result[U, E]:
        if self._is_ok:
            return Result.Ok(f(self._ok))  # type: ignore
        return Result.Err(self._err)  # type: ignore

    def map_err(self, f: Callable[[E], F]) -> Result[T, F]:
        if self._is_ok:
            return Result.Ok(self._ok)  # type: ignore
        return Result.Err(f(self._err))  # type: ignore

    def and_then(self, f: Callable[[T], Result[U, E]]) -> Result[U, E]:
        """Monadic bind (serupa operator '?')."""
        if self._is_ok:
            return f(self._ok)  # type: ignore
        return Result.Err(self._err)  # type: ignore


class PanicException(Exception):
    """Representasi unrecoverable panic di Rust."""
    pass


# ==============================================================================
# Hirarki Error Rust (std::error::Error & thiserror / anyhow)
# ==============================================================================
class ErrorKind(Enum):
    NotFound = auto()
    PermissionDenied = auto()
    UnexpectedEof = auto()
    InvalidData = auto()
    CorruptedChecksum = auto()


@dataclass(frozen=True)
class IoError:
    kind: ErrorKind
    message: str

    def __str__(self) -> str:
        return f"IoError({self.kind.name}): {self.message}"


@dataclass(frozen=True)
class ParseError:
    field: str
    raw_value: str
    reason: str

    def __str__(self) -> str:
        return f"ParseError on field '{self.field}' with value '{self.raw_value}': {self.reason}"


@dataclass(frozen=True)
class SystemError:
    """Error gabungan (enum SystemError { Io(IoError), Parse(ParseError) })."""
    cause: Union[IoError, ParseError]

    @staticmethod
    def from_io(err: IoError) -> SystemError:
        return SystemError(cause=err)

    @staticmethod
    def from_parse(err: ParseError) -> SystemError:
        return SystemError(cause=err)

    def __str__(self) -> str:
        return f"[SystemError RootCause] => {self.cause}"


# ==============================================================================
# Model Data Log & Idiomatic Buffered I/O Stream
# ==============================================================================
@dataclass
class TelemetryRecord:
    timestamp: int
    sensor_id: str
    reading: float
    checksum: int


class RustBufReader:
    """Simulasi trait std::io::BufRead dan BufReader<R> dengan buffer internal."""

    def __init__(self, stream: io.BytesIO, buffer_size: int = 64):
        self.stream = stream
        self.buffer_size = buffer_size
        self.internal_buf = bytearray()
        self.total_bytes_read = 0

    def read_line(self) -> Result[Option[str], IoError]:
        """
        Membaca baris secara efisien dari internal buffer hingga delimiter '\n'.
        Mengembalikan Result<Option<String>, IoError>.
        """
        line_bytes = bytearray()
        while True:
            # Periksa apakah newline ada di internal buffer
            newline_idx = self.internal_buf.find(b"\n")
            if newline_idx != -1:
                line_bytes.extend(self.internal_buf[: newline_idx + 1])
                del self.internal_buf[: newline_idx + 1]
                try:
                    decoded = line_bytes.decode("utf-8").strip()
                    return Result.Ok(Option.Some(decoded))
                except UnicodeDecodeError as exc:
                    return Result.Err(IoError(ErrorKind.InvalidData, str(exc)))

            # Jika buffer belum punya newline, ambil chunk baru dari stream
            chunk = self.stream.read(self.buffer_size)
            if not chunk:
                # EOF reached
                if len(self.internal_buf) > 0:
                    line_bytes.extend(self.internal_buf)
                    self.internal_buf.clear()
                    try:
                        return Result.Ok(Option.Some(line_bytes.decode("utf-8").strip()))
                    except UnicodeDecodeError as exc:
                        return Result.Err(IoError(ErrorKind.InvalidData, str(exc)))
                return Result.Ok(Option.None_())

            self.total_bytes_read += len(chunk)
            self.internal_buf.extend(chunk)


# ==============================================================================
# Logic Pipeline (Simulasi Parsing dengan Propagasi Galat '?')
# ==============================================================================
def compute_checksum(payload: str) -> int:
    """Menghitung checksum sederhana xor dari karakter."""
    chk = 0
    for ch in payload:
        chk ^= ord(ch)
    return chk


def parse_telemetry_line(raw_line: str) -> Result[TelemetryRecord, SystemError]:
    """
    Memvalidasi dan mem-parse format baris:
    `<TIMESTAMP>|<SENSOR_ID>|<READING>|<CHECKSUM>`
    Menggunakan chaining monadic mirip operator '?' di Rust.
    """
    parts = raw_line.split("|")
    if len(parts) != 4:
        err = ParseError("format", raw_line, "Jumlah token delimit '|' harus tepat 4")
        return Result.Err(SystemError.from_parse(err))

    # Parse Timestamp
    try:
        ts = int(parts[0])
    except ValueError:
        err = ParseError("timestamp", parts[0], "Bukan integer 64-bit valid")
        return Result.Err(SystemError.from_parse(err))

    sensor_id = parts[1].strip()
    if not sensor_id:
        err = ParseError("sensor_id", parts[1], "Sensor ID tidak boleh kosong")
        return Result.Err(SystemError.from_parse(err))

    # Parse Reading (Float)
    try:
        reading = float(parts[2])
    except ValueError:
        err = ParseError("reading", parts[2], "Bukan float valid")
        return Result.Err(SystemError.from_parse(err))

    # Parse & Verifikasi Checksum
    try:
        expected_chk = int(parts[3], 16)
    except ValueError:
        err = ParseError("checksum", parts[3], "Bukan representasi hex valid")
        return Result.Err(SystemError.from_parse(err))

    payload_segment = f"{ts}|{sensor_id}|{reading:.2f}"
    actual_chk = compute_checksum(payload_segment)

    if actual_chk != expected_chk:
        err = IoError(
            ErrorKind.CorruptedChecksum,
            f"Checksum mismatch: hitung=0x{actual_chk:02X}, tertulis=0x{expected_chk:02X}"
        )
        return Result.Err(SystemError.from_io(err))

    return Result.Ok(TelemetryRecord(ts, sensor_id, reading, expected_chk))


# ==============================================================================
# Engine Eksekusi & Pelaporan
# ==============================================================================
def process_telemetry_stream(stream_data: bytes) -> None:
    print(f"{BOLD}{CYAN}=== MEMULAI PEMROSESAN ALIRAN STREAM TELEMETRI (RUST-LIKE I/O) ==={RESET}\n")

    cursor = io.BytesIO(stream_data)
    reader = RustBufReader(cursor, buffer_size=32)

    line_number = 0
    successful_records = []
    error_records = []

    start_time = time.perf_counter()

    while True:
        line_number += 1
        # Membaca baris dengan penanganan Result<Option<String>, IoError>
        read_result = reader.read_line()

        if read_result.is_err():
            print(f"{RED}[Baris {line_number:02d}][I/O ERROR]{RESET} -> {read_result.unwrap_or(None)}")
            break

        opt_line = read_result.unwrap()
        if opt_line.is_none():
            # Kondisi EOF (End of Stream)
            break

        raw_line = opt_line.unwrap()
        if not raw_line or raw_line.startswith("#"):
            # Skip baris kosong atau komentar
            continue

        # Parsing dengan Result<TelemetryRecord, SystemError>
        parse_result = parse_telemetry_line(raw_line)

        # Pattern matching simulasi match res { Ok(v) => ..., Err(e) => ... }
        if parse_result.is_ok():
            rec = parse_result.unwrap()
            successful_records.append(rec)
            print(
                f"{GREEN}[OK]{RESET} Baris {line_number:02d}: "
                f"TS={MAGENTA}{rec.timestamp}{RESET} "
                f"Sensor={BOLD}{rec.sensor_id}{RESET} "
                f"Nilai={CYAN}{rec.reading:0.2f}{RESET} "
                f"Chk=0x{rec.checksum:02X}"
            )
        else:
            # Rekam error tanpa mematikan program (idiomatic error handling)
            err = parse_result._err
            error_records.append((line_number, raw_line, err))
            print(
                f"{RED}[ERR]{RESET} Baris {line_number:02d}: {YELLOW}'{raw_line}'{RESET} "
                f"\n     └── Detail: {err}"
            )

    elapsed_ms = (time.perf_counter() - start_time) * 1000

    print(f"\n{BOLD}{CYAN}=== RINGKASAN METRIK EKSEKUSI ==={RESET}")
    print(f"Total Byte Dibaca  : {BOLD}{reader.total_bytes_read}{RESET} bytes (Buffer internal: {reader.buffer_size} bytes)")
    print(f"Total Baris Diproses: {BOLD}{line_number - 1}{RESET}")
    print(f"Record Valid (Ok)   : {GREEN}{BOLD}{len(successful_records)}{RESET}")
    print(f"Record Gagal (Err)  : {RED}{BOLD}{len(error_records)}{RESET}")
    print(f"Waktu Proses        : {YELLOW}{elapsed_ms:.3f} ms{RESET}\n")

    if successful_records:
        avg_reading = sum(r.reading for r in successful_records) / len(successful_records)
        print(f"Statistik Sensor -> Rata-rata Pembacaan: {BOLD}{avg_reading:.2f}{RESET}")

    # Simulasi unrecoverable panic
    print(f"\n{BOLD}{MAGENTA}[Simulasi Unrecoverable Panic / unwrap() Galat]{RESET}")
    sample_err = Result.Err(IoError(ErrorKind.UnexpectedEof, "Koneksi terputus saat streaming"))
    try:
        print("Mencoba memanggil .unwrap() pada Result bertipe Err...")
        sample_err.unwrap()
    except PanicException as p:
        print(f"{RED}Thread 'main' panicked: {p}{RESET}")


def build_synthetic_payload() -> bytes:
    """Membuat payload bytes mentah yang berisi data valid dan anomali galat."""
    records = []
    
    # 1. Valid record
    line1_data = "1700000000|SEN-TEMP-01|24.50"
    records.append(f"{line1_data}|{compute_checksum(line1_data):02X}\n")

    # 2. Valid record
    line2_data = "1700000005|SEN-PRES-02|101.32"
    records.append(f"{line2_data}|{compute_checksum(line2_data):02X}\n")

    # 3. Anomali: Format delimiter tidak sesuai
    records.append("1700000010,SEN-VOLT-03,12.4\n")

    # 4. Anomali: Parse integer gagal
    records.append("NOT_A_TIMESTAMP|SEN-TEMP-01|25.10|AA\n")

    # 5. Anomali: Parse float gagal
    records.append("1700000020|SEN-TEMP-02|CORRUPTED_VAL|BB\n")

    # 6. Valid record
    line6_data = "1700000025|SEN-HUMD-01|65.40"
    records.append(f"{line6_data}|{compute_checksum(line6_data):02X}\n")

    # 7. Anomali: Checksum Mismatch (Integritas rusak)
    records.append("1700000030|SEN-TEMP-01|26.80|FF\n")

    return "".join(records).encode("utf-8")


# ==============================================================================
# Entry Point
# ==============================================================================
if __name__ == "__main__":
    payload = build_synthetic_payload()
    process_telemetry_stream(payload)
    sys.exit(0)