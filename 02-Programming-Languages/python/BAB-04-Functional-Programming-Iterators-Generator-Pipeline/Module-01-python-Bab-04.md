# SEKSI 01 — IDENTITAS MODUL

*   **Kurikulum:** Python Software Engineering & System Architecture
*   **Kategori:** 02-Programming-Languages
*   **Bab:** 04 — Advanced Paradigm & Data Flow
*   **Modul:** 01 — Functional Programming, Iterators & Generator Pipeline
*   **Prasyarat:** Pemahaman mendalam tentang Python Object Model, Data Structures (list, dict, set), Exception Handling, dan Memory Management dasar (Stack vs Heap, Reference Counting).
*   **Target Audiens:** Senior Software Engineer, Backend Architect, Data Platform Engineer.
*   **Estimasi Waktu Baca / Praktik:** 120 Menit

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1.  **Mengoperasikan Paradigma Fungsional Murni di Python:** Mengimplementasikan konsep *first-class functions*, *pure functions*, *immutability*, dan *higher-order functions* (HOF) dengan memanfaatkan modul `functools` dan `itertools` untuk mereduksi *side-effects*.
2.  **Mendekonstruksi Iterator Protocol:** Menjelaskan dan mengimplementasikan protokol iterasi berbasis *dunder methods* (`__iter__` dan `__next__`), serta menangani terminasi aliran via `StopIteration` pada level CPython runtime.
3.  **Membangun Stateful Engine dengan Generator:** Memanfaatkan *keyword* `yield` dan `yield from` untuk mengontrol *frame suspension*, serta mengelola interaksi dua arah menggunakan `generator.send()`, `generator.throw()`, dan `generator.close()`.
4.  **Mendesain Streaming Data Pipeline Hemat Memori:** Mengonstruksi pipeline pengolahan data berskala gigabyte/terabyte dengan karakteristik *lazy evaluation*, mempertahankan konsumsi memori pada batas konstan $\mathcal{O}(1)$.
5.  **Mendiagnosis Masalah dan Mengoptimalkan Aliran Data:** Mengidentifikasi *leaks*, evaluasi prematur, serta anomali mutasi data pada iterator pipeline menggunakan teknik profiling dan *defensive functional patterns*.

---

# SEKSI 03 — MINDSET & MENTAL MODEL

Dalam pemrograman imperatif tradisional, developer bertindak sebagai mandor yang mendikte komputer langkah demi langkah: *"Ambil memori sebesar array X, iterasi indeks 0 sampai N, mutasikan variabel penampung Y, lalu kembalikan Y."* Pendekatan ini berpusat pada mutasi status (*state mutation*) dan alokasi memori *eager* (seluruh data dimuat sekaligus ke RAM).

```
Eager Processing (Imperatif):
[Data Mentah di Disk] ---> [Load Seluruh Data ke RAM (10GB)] ---> [Mutasi State] ---> [Hasil Akhir]
                            ⚠️ Rawan Out-Of-Memory (OOM)

Lazy Streaming (Fungsional & Iterator):
[Data Mentah di Disk] ---> (Item 1) ---> [Filter] ---> [Transform] ---> [Sink]
                      ---> (Item 2) ---> [Filter] ---> [Transform] ---> [Sink]
                      Memori stabil: O(1) per item!
```

Mental model pemrograman fungsional dan iterator pipeline memandang data bukan sebagai sekumpulan struktur statis di memori, melainkan sebagai **aliran air dalam pipa (stream/pipeline)**:

1.  **Data as a Stream (Aliran):** Data tidak menetap di memori secara kolektif; ia ditarik (*pull-based execution*) satu per satu hanya ketika elemen hilir membutuhkannya.
2.  **Purity and Statelessness:** Setiap fungsi transformasi diibaratkan seperti filter air mekanis murni tanpa efek samping (*pure function*): input yang sama selalu menghasilkan output yang identik tanpa merusak variabel global atau mengubah input aslinya.
3.  **Suspension & Resumption:** Generator bukan sekadar fungsi biasa, melainkan sebuah mesin status (*state machine*) yang dapat membekukan eksekusi (*freeze frame*), menyerahkan kendali kembali ke pemanggil (*yield*), dan melanjutkan operasinya persis di titik terakhir saat diminta kembali.

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Di CPython, fungsi konvensional mengeksekusi *frame stack* hingga selesai (`RETURN_VALUE`), yang kemudian menghancurkan *frame* tersebut dari memori. Sebaliknya, generator function membungkus *frame* ke dalam objek generator pada heap. 

### Diagram Alur: Generator Frame Stack Lifecycle & Suspension

```
[ Caller Scope ]                                  [ Generator Frame Scope ]
       │                                                      │
       ├─── 1. call: gen = worker() ─────────────────────────┤ (Instansiasi: Status GEN_CREATED)
       │                                                      │
       ├─── 2. pull: next(gen) ──────────────────────────────►│ (Eksekusi dimulai hingga yield)
       │                                                      ├─ Variabel lokal disimpan di heap
       │◄── 3. yield value ───────────────────────────────────┤ (Status: GEN_SUSPENDED)
       │    (Caller memproses nilai)                          │
       │                                                      │
       ├─── 4. pull: next(gen) / gen.send(v) ────────────────►│ (Resumption: Eksekusi berlanjut)
       │                                                      ├─ Memproses logic berikutnya
       │◄── 5. yield value ───────────────────────────────────┤ (Status: GEN_SUSPENDED)
       │                                                      │
       ├─── 6. pull: next(gen) ──────────────────────────────►│ (Eksekusi selesai / return)
       │◄── 7. raise StopIteration ───────────────────────────┤ (Status: GEN_CLOSED & Frame Cleanup)
       ▼                                                      ▼
```

### Diagram Arsitektur: Multi-Stage Lazy Generator Pipeline

Data ditarik secara berantai dari kanan ke kiri (*pull-driven*): consumer memanggil `next()` pada pipa paling ujung, yang memicu penarikan beruntun hingga ke sumber data terbawah.

```
       +-----------------------------------------------------------------------+
       |                           CONSUMER LOOP                               |
       |  for record in sink_pipeline: consume(record)                         |
       +-----------------------------------------------------------------------+
                                          ▲  next()
                                          │
       +----------------------------------┴------------------------------------+
       | STAGE 3: Aggregator / Serializer (Generator)                          |
       | yield orjson.dumps(enrich(data))                                      |
       +-----------------------------------------------------------------------+
                                          ▲  next()
                                          │
       +----------------------------------┴------------------------------------+
       | STAGE 2: Filter & Validator (Generator)                               |
       | if is_valid(data): yield data                                         |
       +-----------------------------------------------------------------------+
                                          ▲  next()
                                          │
       +----------------------------------┴------------------------------------+
       | STAGE 1: File/Socket Ingestion Stream (Generator)                     |
       | while line := file.readline(): yield line                             |
       +-----------------------------------------------------------------------+
                                          ▲  read
                                          │
                            [ Raw Data (e.g. 50GB Log) ]
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Iterator Protocol (`PyIter_Next`)
Objek Python disebut *Iterable* jika mengimplementasikan `__iter__()` yang mengembalikan objek *Iterator*. Objek *Iterator* wajib mengimplementasikan:
*   `__iter__()`: Mengembalikan dirinya sendiri (`return self`).
*   `__next__()`: Menghasilkan elemen berikutnya atau melempar pengecualian `StopIteration` saat aliran data habis.

Di level CPython, pemanggilan `next(it)` dieksekusi via slot tipe C `tp_iternext`. Loop `for` pada dasarnya adalah translasi bytecode dari:

```python
iterator = iter(iterable)
while True:
    try:
        item = next(iterator)
    except StopIteration:
        break
    # Loop body
```

### 2. Generator Internal (`PyGenObject`)
Ketika interpreter menemukan *keyword* `yield` di dalam fungsi, kompilator menandai fungsi tersebut dengan flag `CO_GENERATOR` pada atribut `f_code.co_flags`. Pemanggilan fungsi tidak langsung mengeksekusi instruksi bytecode di dalamnya, melainkan mengembalikan instansi struktur C `PyGenObject`:

```c
typedef struct {
    PyObject_HEAD
    PyFrameObject *gi_frame;       // Frame stack aktif yang dibekukan
    char gi_running;               // Flag apakah generator sedang dieksekusi
    PyObject *gi_code;             // Bytecode object
    PyObject *gi_weakreflist;      // Weak references
    PyObject *gi_name;             // Nama generator
    PyObject *gi_qualname;
    _PyErr_StackState gi_exc_state;// Menyimpan status traceback exception
} PyGenObject;
```

Instruksi bytecode `YIELD_VALUE` mengekstrak elemen teratas dari stack ekspresi, menyimpan instruksi pointer instruksi berikutnya (`f_lasti`), menyalin frame pointer, dan mengembalikan kontrol ke frame eksekusi pemanggil tanpa menghancurkan alokasi frame stack.

### 3. Generator States
Generator memiliki 4 status internal yang dapat diinspeksi melalui fungsi `inspect.getgeneratorstate()`:
*   `GEN_CREATED`: Objek generator telah diinstansiasi, namun belum dieksekusi via `next()`.
*   `GEN_RUNNING`: Generator saat ini sedang dieksekusi oleh interpreter (aktif hanya di dalam generator itu sendiri).
*   `GEN_SUSPENDED`: Eksekusi dibekukan pada instruksi `yield`.
*   `GEN_CLOSED`: Generator telah selesai mengeksekusi frame atau dihentikan via `.close()`.

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI

### Functional Programming Foundations di Python

Meskipun Python adalah bahasa *multi-paradigm* yang berakar kuat pada *Object-Oriented Programming* (OOP), Python mengadopsi pilar fungsional esensial:

#### A. First-Class & Higher-Order Functions
Fungsi di Python adalah *first-class citizen*—ia merupakan turunan kelas `object`, dapat di-assign ke variabel, disimpan dalam struktur data, dikirim sebagai argumen, dan dikembalikan sebagai *return value*. *Higher-Order Function* (HOF) adalah fungsi yang menerima fungsi lain sebagai parameter atau mengembalikan fungsi (contoh: `map()`, `filter()`, `functools.reduce()`, dan decorators).

#### B. Purity & Immutability
Sebuah fungsi dikatakan *pure* jika:
1.  **Deterministic:** Menghasilkan output yang sama untuk input yang sama persis.
2.  **Zero Side-Effects:** Tidak mengubah variabel di luar scopenya, tidak memutasi argumen yang diterima, dan tidak melakukan operasi I/O yang mengubah *environment state* secara implisit.

```python
# Impure: Memutasi list global dan hasil bergantung pada environment luar
data_store: list[int] = []
def impure_append(val: int) -> list[int]:
    data_store.append(val)
    return data_store

# Pure: Mengembalikan instance baru tanpa memodifikasi argumen asli
from typing import Sequence
def pure_append(collection: Sequence[int], val: int) -> tuple[int, ...]:
    return (*collection, val)
```

#### C. Modul `functools` dan `itertools`
*   `functools.partial`: Menghasilkan fungsi baru dengan mengunci sebagian argumen (*currying approximation*), mendukung komposisi fungsi secara modular.
*   `functools.reduce`: Akumulasi nilai sekuensial dari kiri ke kanan menggunakan fungsi biner.
*   `itertools`: Toolkit primitif untuk iterator berkinerja tinggi yang ditulis dalam bahasa C, seperti `islice` (*slicing* lazy stream), `chain` (merangkai multiple iterator), `tee` (menduplikasi iterator), dan `cycle`.

### Mekanisme `yield from`
Diperkenalkan pada PEP 380, `yield from <iterable>` bukan sekadar sintaks gula untuk:
```python
for item in iterable:
    yield item
```
`yield from` membuka **sub-channel komunikasi transparan** dua arah antara *caller* terluar dan *sub-generator* terdalam. Sinyal pemanggilan metode `.send()`, `.throw()`, dan `.close()` dari *caller* dilewatkan langsung melewati generator perantara ke sub-generator terdalam, serta menangani pengembalian nilai (`return value`) dari sub-generator ke dalam ekspresi penugasan variabel:

```python
result = yield from sub_generator()
```

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi bertahap dari:
1. Custom Iterator murni berbasis class iterator protocol.
2. Advanced Generator berbasis `yield`, `send()`, dan `close()`.
3. Generator Pipeline fungsional menggunakan `itertools` dan `functools`.

```python
from collections.abc import Generator, Iterator
import functools
import itertools
from typing import Any, TypeVar

T = TypeVar("T")

# ============================================================================
# 1. Custom Iterator Protocol
# ============================================================================
class FibonacciIterator:
    """Iterator eksplisit yang menghitung deret Fibonacci hingga batas tertentu."""
    
    def __init__(self, max_limit: int) -> None:
        self._max_limit = max_limit
        self._a: int = 0
        self._b: int = 1
        self._count: int = 0

    def __iter__(self) -> Iterator[int]:
        # Suatu iterator wajib mengembalikan dirinya sendiri
        return self

    def __next__(self) -> int:
        if self._count >= self._max_limit:
            raise StopIteration
        
        current = self._a
        self._a, self._b = self._b, self._a + self._b
        self._count += 1
        return current


# ============================================================================
# 2. Coroutine-Style Generator (yield, send, throw, close)
# ============================================================================
def rolling_average_coroutine() -> Generator[float, float, None]:
    """Menghitung rata-rata kumulatif dinamis menggunakan receiver generator."""
    total: float = 0.0
    count: int = 0
    average: float = 0.0

    while True:
        # Yield 'average' ke pemanggil dan tunggu penerimaan 'value' baru via .send()
        new_value: float = yield average
        if new_value is None:
            break
        total += new_value
        count += 1
        average = total / count


# ============================================================================
# 3. Composable Functional Generator Pipeline
# ============================================================================
def stream_numbers(limit: int) -> Generator[int, None, None]:
    """Menghasilkan infinite/finite stream sequence secara lazy."""
    yield from range(limit)

def filter_even(stream: Iterator[int]) -> Generator[int, None, None]:
    """Pure generator filter: hanya melewatkan bilangan genap."""
    for item in stream:
        if item % 2 == 0:
            yield item

def square_transform(stream: Iterator[int]) -> Generator[int, None, None]:
    """Pure generator mapping: memangkatkan dua setiap elemen."""
    for item in stream:
        yield item ** 2
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Analisis Kelas `FibonacciIterator` (Seksi 07.1)
*   **Baris 11-16 (`__init__`):** Menginisialisasi *internal state*. Variabel `_a` dan `_b` menyimpan dua bilangan terakhir untuk kalkulasi deret. Parameter `_max_limit` menentukan batas evaluasi.
*   **Baris 18-20 (`__iter__`):** Standar kontrak Iterator: Mengembalikan `self` agar objek ini kompatibel dengan ekspresi Python seperti `for x in FibonacciIterator(10)`.
*   **Baris 22-29 (`__next__`):**
    *   `if self._count >= self._max_limit: raise StopIteration`: Terminasi wajib bagi iterator finite. Tanpa `StopIteration`, perulangan pemanggil akan berjalan tanpa batas (*infinite loop*).
    *   `self._a, self._b = self._b, self._a + self._b`: Atomic unpacking khas Python untuk mengkalkulasi bilangan berikutnya secara simultan tanpa variabel temporer eksplisit.

### Analisis Coroutine `rolling_average_coroutine` (Seksi 07.2)
*   **Baris 35 (`Generator[float, float, None]`):** Typing annotation dengan struktur: `Generator[YieldType, SendType, ReturnType]`. Menghasilkan `float`, menerima input `float` melalui `.send()`, dan tidak mengembalikan nilai akhir (`None`).
*   **Baris 41 (`new_value = yield average`):** Jantung operasi suspensi dua arah:
    1. Mesin mengirimkan nilai `average` keluar ke caller.
    2. Eksekusi dibekukan (`GEN_SUSPENDED`).
    3. Ketika caller memanggil `coro.send(value)`, eksekusi aktif kembali dan menetapkan data yang dikirim ke `new_value`.

### Analisis Pipeline `square_transform(filter_even(stream_numbers(...)))` (Seksi 07.3)
*   **Baris 49 (`yield from range(limit)`):** Delegasi iterator secara langsung ke objek `range()`. Melewatkan setiap elemen tanpa *overhead* manual loop di layer ini.
*   **Baris 51-60:** Komposisi pipeline. Aliran data tidak disimpan dalam list kolektif. Setiap pemanggilan `next()` pada pipa terluar (`square_transform`) akan meminta satu data dari `filter_even`, yang kemudian meminta satu data mentah dari `stream_numbers`.

---

# SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi: High-Throughput Web Server Audit Log Ingestion Engine
Sebuah sistem perbankan memiliki cluster gateway API yang mencatat riwayat transaksi HTTP ke dalam file log harian berukuran **85 GB per file**. Format file adalah JSON baris-demi-baris (*JSON Lines* / `.jsonl`). 

**Kebutuhan Bisnis & Infrastruktur:**
1.  **Ekstraksi Transaksi Mencurigakan:** Temukan transaksi dengan HTTP status code `401` (Unauthorized) atau `403` (Forbidden) yang memiliki nilai transaksi di atas batas regulasi ($10.000).
2.  **Constraint Resource Memory:** Layanan pengolah audit dijalankan di dalam container Kubernetes yang dibatasi (*hard limit*) memori sebesar **256 MiB**. Memuat seluruh log ke dalam memori via `json.loads(file.read())` akan memicu *OOMKilled* (Kernel exit code 137).
3.  **Real-Time Hash Verification:** Setiap baris log diikat dengan hash SHA-256 kriptografis berantai (*Merkle chain*) untuk menjamin keaslian log tidak diubah oleh penyerang.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah implementasi modular, *type-safe*, dan siap produksi untuk memproses puluhan gigabyte log audit dengan penggunaan memori statis $\mathcal{O}(1)$.

```python
from collections.abc import Generator, Iterable, Iterator
from dataclasses import dataclass
import hashlib
import json
import logging
import sys
from typing import Final, Optional

# Setup Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("AuditEngine")

AUDIT_THRESHOLD: Final[float] = 10_000.00

@dataclass(frozen=True, slots=True)
class LogPayload:
    """Struktur data immutable dengan performa tinggi & footprint memori rendah."""
    timestamp: str
    ip_address: str
    status_code: int
    amount: float
    raw_hash: str


def raw_log_reader(file_path: str) -> Generator[str, None, None]:
    """Lazy file reader: membaca file baris demi baris tanpa alokasi eager."""
    logger.info(f"Membuka stream berkas audit: {file_path}")
    try:
        with open(file_path, mode="r", encoding="utf-8") as file_handle:
            for line_no, line in enumerate(file_handle, start=1):
                clean_line = line.strip()
                if clean_line:  # Abaikan baris kosong
                    yield clean_line
    except FileNotFoundError:
        logger.error(f"File log audit tidak ditemukan: {file_path}")
        raise
    except OSError as err:
        logger.critical(f"I/O error saat membaca {file_path}: {err}")
        raise


def json_deserializer(stream: Iterable[str]) -> Generator[dict, None, None]:
    """Parsing string JSON Lines menjadi dictionary secara lazy dengan penanganan galat."""
    for raw_string in stream:
        try:
            parsed_data = json.loads(raw_string)
            yield parsed_data
        except json.JSONDecodeError as err:
            logger.warning(f"Melewati record korup: {raw_string[:50]}... Error: {err}")
            continue


def record_transformer(stream: Iterable[dict]) -> Generator[LogPayload, None, None]:
    """Transformasi dictionary mentah ke immutable domain model ber-tipe data statis."""
    for record in stream:
        try:
            payload = LogPayload(
                timestamp=record["timestamp"],
                ip_address=record["ip_address"],
                status_code=int(record["status_code"]),
                amount=float(record.get("amount", 0.0)),
                raw_hash=hashlib.sha256(json.dumps(record, sort_keys=True).encode("utf-8")).hexdigest()
            )
            yield payload
        except (KeyError, ValueError) as err:
            logger.warning(f"Skema log invalid: {record}. Error: {err}")
            continue


def suspicious_activity_filter(stream: Iterable[LogPayload]) -> Generator[LogPayload, None, None]:
    """Pure business logic filter: HTTP 401/403 dengan amount signifikan."""
    for payload in stream:
        if payload.status_code in (401, 403) and payload.amount >= AUDIT_THRESHOLD:
            yield payload


def audit_alert_sink(stream: Iterable[LogPayload]) -> int:
    """Consumer terminal stage: Mengonsumsi stream akhir dan memicu aksi analitik."""
    processed_alerts = 0
    for anomaly in stream:
        processed_alerts += 1
        # Mengirim alert ke SIEM / Security Operations Center
        logger.warning(
            f"SECURITY ALERT [{processed_alerts}] | IP: {anomaly.ip_address} | "
            f"Code: {anomaly.status_code} | Amount: ${anomaly.amount:,.2f} | "
            f"Hash: {anomaly.raw_hash[:8]}..."
        )
    return processed_alerts


# ============================================================================
# Driver Execution Pipeline Orchestrator
# ============================================================================
def execute_pipeline(log_file_path: str) -> None:
    """Merakit dan mengeksekusi pipeline stream processing."""
    # Pipeline composition: Deklarasi jalur aliran data
    # Evaluasi BELUM terjadi di sini (Zero Execution Overhead)
    file_stream = raw_log_reader(log_file_path)
    dict_stream = json_deserializer(file_stream)
    payload_stream = record_transformer(dict_stream)
    filtered_stream = suspicious_activity_filter(payload_stream)

    # Eksekusi ditarik secara lazy oleh sink terminal
    logger.info("Memulai pemrosesan transaksi...")
    total_anomalies = audit_alert_sink(filtered_stream)
    logger.info(f"Selesai. Total anomali mencurigakan terdeteksi: {total_anomalies}")


if __name__ == "__main__":
    import tempfile
    
    # Mock data generator untuk testing runtime
    with tempfile.NamedTemporaryFile("w+", delete=False, encoding="utf-8") as temp_log:
        temp_log.write('{"timestamp": "2026-03-31T01:00:00Z", "ip_address": "192.168.1.10", "status_code": 200, "amount": 150.0}\n')
        temp_log.write('{"timestamp": "2026-03-31T01:00:01Z", "ip_address": "10.0.0.99", "status_code": 401, "amount": 1250000.0}\n') # Anomali
        temp_log.write('{"timestamp": "2026-03-31T01:00:02Z", "ip_address": "10.0.0.99", "status_code": 403, "amount": 900.0}\n')     # Normal (< threshold)
        temp_log.write('CORRUPT_JSON_DATA_STREAM\n')                                                                                   # Korup
        temp_log.write('{"timestamp": "2026-03-31T01:00:03Z", "ip_address": "172.16.0.4", "status_code": 403, "amount": 45000.0}\n')   # Anomali
        temp_log_path = temp_log.name

    execute_pipeline(temp_log_path)
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

| Parameter | In-Memory Lists (`list comprehension`) | Functional Streams (`itertools` / `map`) | Custom Generator (`yield`) |
| :--- | :--- | :--- | :--- |
| **Kompleksitas Memori** | $\mathcal{O}(N)$ — Menyimpan seluruh elemen di RAM. Bahaya OOM pada big data. | $\mathcal{O}(1)$ — Lazy. Hanya 1 item berada di register pada satu waktu. | $\mathcal{O}(1)$ — Lazy. Beban memori konstan per stack frame. |
| **CPU Overhead** | Sangat rendah. Iterasi diimplementasikan di pure C array traversal. | Sangat rendah. Banyak komponen berjalan pada loop level C internal CPython. | Sedang. Ada *overhead switching* antar frame stack saat suspensi `yield`. |
| **Random Access Indexing** | Ya. Mendukung direct indexing: `data[i]`, *slicing*, dan `len(data)`. | Tidak. Harus dikonsumsi urut dari awal. Tidak bisa *backward*. | Tidak. Bersifat *forward-only*. Elemen yang sudah di-`yield` hilang dari memori. |
| **Reusability** | Ya. Objek list dapat diiterasi berulang-ulang tanpa batas. | Tidak. Sekali dikonsumsi, iterator habis (*exhausted*). | Tidak. Generator mati setelah selesai (*exhausted*). Harus dibuat ulang. |
| **Debugging Complexity** | Sederhana. Cukup `print(data)` atau intip via visual debugger. | Sedang. Data tidak terlihat sampai dievaluasi secara eksplisit. | Sulit. Butuh tracking state suspensi, nilai `.send()`, dan inspect frame. |

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. Iterator Exhaustion (Kelelahan Iterator)
Iterator hanya dapat dikonsumsi satu kali seumur hidupnya di Python runtime. Sekali `StopIteration` terlempar, pemanggilan berikutnya akan langsung melempar `StopIteration` kembali secara instan.

```python
gen = (x for x in range(3))
list_a = list(gen)  # Output: [0, 1, 2]
list_b = list(gen)  # Output: [] -> HATI-HATI! Generator sudah kosong/exhausted!
```
*Solusi:* Jika Anda butuh melakukan re-iterasi data berulang kali, gunakan `itertools.tee(gen, n)` untuk menduplikasi stream atau buat fungsi factory pembangun generator baru.

### 2. Mutasi Penutupan Variabel (*Late Binding pada Generator Expressions*)
Generator expression mengevaluasi variabel di scope luar secara *lazy* saat *next* dipanggil, bukan saat fungsi generator dibuat (*late binding*):

```python
multipliers = [(lambda x: x * i) for i in range(3)] # Biasa
gen_mult = (lambda x: x * i for i in range(3))      # Lazy Generator

# Bahaya pada for-loop:
funcs = []
for i in range(3):
    funcs.append(lambda x: x * i)
# Seluruh fungsi akan mengalikan nilai dengan '2' karena nilai terakhir dari 'i' adalah 2!
```

### 3. Generator Resource Leaks pada Unhandled Termination
Jika Anda membuka koneksi soket atau file descriptor di dalam generator:
```python
def leak_generator():
    f = open("huge.bin", "rb")
    for chunk in iter(lambda: f.read(4096), b""):
        yield chunk
    f.close() # ⚠️ Tidak akan pernah dieksekusi jika caller menggunakan 'break'!
```
*Solusi:* Wajib gunakan konteks manager (`with`) atau blok `try...finally`. CPython menjamin saat generator di-garbage collect, metode `.close()` otomatis dipanggil yang akan menembakkan exception `GeneratorExit` ke dalam frame yang dibekukan, memicu blok `finally`.

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Mistake 1: Menggunakan Operasi Indexing atau `len()` pada Generator
```python
# SALAH: Melempar TypeError: object of type 'generator' has no len()
data_stream = (x for x in range(100))
print(len(data_stream))
print(data_stream[0])

# BENAR: Konsumsi menggunakan library streaming
import itertools
first_item = next(data_stream)
slice_items = list(itertools.islice(data_stream, 5))
```

### Mistake 2: Menyembunyikan `StopIteration` di dalam Generator (PEP 479)
Sebelum PEP 479, melemparkan `StopIteration` secara manual dari dalam generator function dapat memutus perulangan luar secara tidak sengaja.
```python
# SALAH (Melanggar PEP 479 di Python 3.7+):
def faulty_generator():
    yield 1
    raise StopIteration # Menghasilkan RuntimeError: generator raised StopIteration

# BENAR: Gunakan 'return' sederhana untuk terminasi bersih
def correct_generator():
    yield 1
    return
```

### Mistake 3: Mengeksekusi List Comprehension Eagerly saat Ingin Streaming
```python
# SALAH: Menghabiskan 4GB RAM secara prematur
sum([x * 2 for x in range(100_000_000)])

# BENAR: Menggunakan generator expression (mengganti [] dengan ())
# Memori hanya beberapa byte, kalkulasi dilakukan streaming
sum(x * 2 for x in range(100_000_000))
```

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Gunakan Type Hinting Lengkap dari `collections.abc`:** Selalu tandai argumen pipeline Anda sebagai `Iterable[T]` atau `Iterator[T]`, bukan `list[T]`. Ini memastikan fungsi Anda fleksibel menerima `list`, `set`, generator function, maupun generator expression.
2.  **Hindari Side-Effects pada Filter dan Mapper:** Fungsi yang disematkan ke dalam pipeline tidak boleh memutasi status eksternal atau memodifikasi objek yang masuk. Kembalikan instansi baru (`dataclass(frozen=True)` atau `namedtuple`).
3.  **Terapkan PEP 8 Naming Conventions:** Gunakan kata kerja aktif berbasis streaming untuk fungsi generator (e.g., `generate_events()`, `stream_chunks()`, `filter_anomalies()`).
4.  **Bungkus Generator Bersihkan Resource dengan Context Manager:** Jika generator Anda mengelola resource OS, implementasikan context manager menggunakan `@contextlib.contextmanager`.
5.  **Fail Fast & Log Explicitly:** Di dalam pipeline stream, tangani record kotor dengan *error trapping isolation* per elemen tanpa membunuh keseluruhan stream pipeline yang sedang berjalan.

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### Mengukur Jejak Memori: List vs Generator
Untuk mendemonstrasikan efisiensi generator, mari bandingkan alokasi memori menggunakan modul `sys`:

```python
import sys

# 10 Juta elemen alokasi Eager List
eager_list = [i for i in range(10_000_000)]
print(f"Ukuran List di RAM: {sys.getsizeof(eager_list) / (1024**2):.2f} MB")
# Output: ~80.0 MB (belum termasuk alokasi pointer integer di heap!)

# 10 Juta elemen alokasi Lazy Generator
lazy_gen = (i for i in range(10_000_000))
print(f"Ukuran Generator di RAM: {sys.getsizeof(lazy_gen)} Bytes")
# Output: ~208 Bytes (Konstan terlepas dari ukuran elemen)
```

### Optimalisasi dengan Modul C-Level: `itertools`
Fungsi generator Python murni memiliki overhead eksekusi loop bytecode Python. Jika memungkinkan, ganti generator buatan tangan dengan modul `itertools` atau `functools` yang dikompilasi langsung dalam C:

```python
import itertools

# Generator Manual (Python Frame Switch Overhead):
def manual_chain(iter1, iter2):
    for x in iter1: yield x
    for y in iter2: yield y

# Menggunakan itertools (C-Speed, Direct Pointer Traversal):
fast_chain = itertools.chain(iter1, iter2)
```

Gunakan `itertools.islice()` alih-alih mengekstrak slice via `[]` manual, dan gunakan `operator.itemgetter()` untuk *mapping transformation* ultra-cepat tanpa overhead lambda execution.

---

# SEKSI 16 — KEAMANAN & HARDENING

1.  **Proteksi Infinite Generator DOS Attack:**
    Generator yang beroperasi pada aliran tidak terbatas (*unbounded/infinite stream*) tanpa mekanisme terminasi dapat menyebabkan *Denial of Service* (DoS) jika dihubungkan dengan *sink terminal* seperti `list()`, `max()`, atau `sorted()`.
    *Hardening Pattern:* Pasang pembatas batas konsumsi maksimal (*circuit breaker*) menggunakan `itertools.islice`:
    ```python
    import itertools
    # Memaksa pembacaan maksimal 50,000 item untuk mencegah resource starvation
    safe_stream = itertools.islice(untrusted_infinite_stream, 50_000)
    ```

2.  **Mencegah Regex DoS (ReDoS) pada Parsing Stream:**
    Saat menerapkan filter regex di dalam generator stream, evaluasi waktu eksekusi pola regex agar tidak membekukan *pipeline loop worker thread*.

3.  **Generators Cleanup pada Async / Multithreading:**
    Jika generator dibagikan antar thread tanpa konkurensi terkontrol, race condition internal pada `gi_frame` dapat memicu `ValueError: generator already executing`. Generator **tidak thread-safe**. Lindungi pipeline generator dengan *threading Lock* atau isolasi instance generator per thread worker.

---

# SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Debugging lazy pipeline memiliki tantangan inheren: data tidak terevaluasi sampai dieksekusi di akhir, sehingga *breakpoint* tradisional di tengah pembuatan pipeline tidak akan terpanggil secara langsung.

### Pola Observabilitas: *Tee Inspector Pattern*
Gunakan generator penyadap (*tap/spy generator*) untuk logging transparan tanpa mengganggu aliran data asli:

```python
from collections.abc import Iterable, Iterator
import logging
from typing import TypeVar

T = TypeVar("T")

def stream_inspector_tap(
    stream: Iterable[T], 
    stage_name: str, 
    sample_rate: int = 1000
) -> Iterator[T]:
    """Menyadap data pipeline untuk metrik & visualisasi tanpa memutasi payload."""
    for idx, item in enumerate(stream):
        if idx % sample_rate == 0:
            logging.debug(f"[PIPELINE SPY: {stage_name}] Sampled Item #{idx}: {item}")
        yield item
```

### Inspeksi Status Frame Eksekusi
Gunakan modul `inspect` untuk membedah isi generator yang sedang mengalami suspensi:

```python
import inspect

def audit_worker():
    x = 42
    yield x
    y = 100
    yield y

worker = audit_worker()
print("State 1:", inspect.getgeneratorstate(worker)) # GEN_CREATED
next(worker)
print("State 2:", inspect.getgeneratorstate(worker)) # GEN_SUSPENDED
print("Local Variables in Frame:", worker.gi_frame.f_locals) # {'x': 42}
```

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

*   **Iterable:** Memiliki metode `__iter__()` yang mengembalikan iterator.
*   **Iterator:** Memiliki metode `__iter__()` (mengembalikan `self`) dan `__next__()` (mengembalikan elemen berikutnya atau melempar `StopIteration`).
*   **Generator Function:** Fungsi dengan keyword `yield`. Menghasilkan `PyGenObject` bertipe lazy.
*   **Generator Expression:** Sintaks lazy comprehension: `(expression for item in iterable)`.
*   **`yield` vs `yield from`:** `yield` mengembalikan nilai individual; `yield from` mendelegasikan iterasi ke sub-iterable secara langsung dan membuka kanal transmisi `.send()`/`.throw()`.
*   **Generator Methods:**
    *   `next(gen)` / `gen.__next__()`: Lanjutkan eksekusi sampai `yield` berikutnya.
    *   `gen.send(value)`: Lanjutkan eksekusi dan suntikkan `value` ke evaluasi statement `yield`.
    *   `gen.throw(type, val, tb)`: Lempar exception buatan ke dalam frame generator yang sedang *suspended*.
    *   `gen.close()`: Matikan generator via exception `GeneratorExit`.
*   **Prinsip Emas Memori:** *Lazy evaluation* menjamin penggunaan memori $\mathcal{O}(1)$ stabil terlepas dari volume data yang diproses.

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Basic (1 - 5)

1.  **Apa perbedaan mendasar antara implementasi `__iter__` pada sebuah *Iterable* vs sebuah *Iterator*?**
    *   *Jawaban:* Pada *Iterable*, `__iter__` harus mengembalikan objek iterator baru. Pada *Iterator*, `__iter__` cukup mengembalikan dirinya sendiri (`return self`).
2.  **Apa yang terjadi jika suatu fungsi memiliki *keyword* `yield` sekaligus perintah `return "selesai"`?**
    *   *Jawaban:* Fungsi tetap menjadi generator. Saat baris `return "selesai"` tercapai, interpreter akan melempar exception `StopIteration("selesai")`. String pengembalian disimpan pada atribut `.value` dari exception tersebut.
3.  **Apakah konsumsi memori dari generator expression `(x for x in range(10_000_000))` lebih kecil daripada list comprehension `[x for x in range(10_000_000)]`? Jelaskan!**
    *   *Jawaban:* Ya, jauh lebih kecil. Generator expression dievaluasi secara lazy sehingga hanya memegang status instruksi dan frame stack saat ini ($\mathcal{O}(1)$ memori), sedangkan list comprehension langsung mengalokasikan array 10 juta integer di heap memori ($\mathcal{O}(N)$ memori).
4.  **Apa status (`inspect.getgeneratorstate`) generator yang baru saja diinstansiasi namun belum pernah dipanggil fungsi `next()` pertamanya?**
    *   *Jawaban:* `GEN_CREATED`.
5.  **Bagaimana cara menduplikasi sebuah iterator agar bisa dikonsumsi secara independen sebanyak dua kali tanpa membaca ulang seluruh data ke memori list?**
    *   *Jawaban:* Menggunakan fungsi `itertools.tee(iterable, 2)`.

### Soal Intermediate (6 - 10)

6.  **Mengapa pemanggilan method `.send(data)` akan melempar exception `TypeError: can't send non-None value to a just-started generator` jika dilakukan pada generator berstatus `GEN_CREATED`?**
    *   *Jawaban:* Karena generator baru belum memulai frame eksekusinya dan belum mencapai statement `yield` pertama untuk menerima data suntikan tersebut. Generator harus diinisialisasi terlebih dahulu via `next(gen)` atau `gen.send(None)`.
7.  **Jelaskan implikasi PEP 479 terhadap pelemparan error `StopIteration` manual di dalam generator block!**
    *   *Jawaban:* Berdasarkan PEP 479, pelemparan `StopIteration` secara eksplisit di dalam generator tidak lagi dianggap sebagai terminasi normal, melainkan akan ditangkap dan dibungkus oleh interpreter menjadi `RuntimeError: generator raised StopIteration` untuk mencegah tersembunyinya error logika tak terduga.
8.  **Diberikan kode berikut:**
    ```python
    def sub():
        return "Alfa"
        yield 1
    def master():
        val = yield from sub()
        yield val
    ```
    **Berapakah urutan output jika dieksekusi `list(master())`?**
    *   *Jawaban:* Outputnya adalah `['Alfa']`. Karena pada `sub()`, baris pertama langsung `return "Alfa"`, yang berarti generator `sub` segera melempar `StopIteration("Alfa")`. Nilai return ini ditangkap oleh statement penugasan `val = yield from sub()`, lalu baris berikutnya `yield val` menghasilkan `'Alfa'`. Nilai `yield 1` tidak pernah dieksekusi.
9.  **Mengapa operasi `sorted(my_generator)` membatalkan keunggulan efisiensi memori dari generator pipeline?**
    *   *Jawaban:* Karena algoritma pengurutan (seperti Timsort pada Python) memerlukan visibilitas total terhadap seluruh data untuk membandingkan posisi setiap elemen. Akibatnya, `sorted()` akan mengonsumsi habis (*exhaust*) generator dan memuat seluruh data ke dalam list memory internal secara eager ($\mathcal{O}(N)$ memori).
10. **Bagaimana cara menghentikan generator internal yang sedang suspended di dalam loop `while True:` dari luar frame tanpa mematikan aplikasi?**
    *   *Jawaban:* Dengan memanggil metode `generator.close()`. Pemanggilan ini menembakkan exception `GeneratorExit` tepat di titik `yield` generator yang sedang suspended, memutus perulangan tak terbatas dan mengeksekusi blok pembersihan `finally` yang relevan.

---

# SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Judul Proyek: Real-Time High-Velocity Financial Fraud Event Processing Engine

#### Deskripsi
Bangunlah sebuah mesin pemroses analitik anomali transaksi finansial (*anti-money laundering stream processor*) berbasis arsitektur *lazy pipeline* fungsional tanpa menggunakan framework pihak ketiga (hanya library standar Python: `typing`, `collections`, `itertools`, `functools`, `dataclasses`, `time`).

#### Spesifikasi Input Data
Simulasikan aliran stream data transaksi kartu kredit (dapat berupa file CSV/JSONL atau mock infinite generator) dengan format payload transaksi:
```python
{
    "transaction_id": "uuid4",
    "account_id": "acc-1029",
    "timestamp": 1711843200, # Unix epoch
    "amount": 4500.0,
    "location": "ID-JKT"
}
```

#### Spesifikasi Pipeline yang Harus Dibangun

1.  **Stage 1 - Ingestion & Schema Sanitizer (`Generator`):**
    Mengambil data mentah, membersihkan whitespace, memvalidasi kelengkapan tipe field, dan membuang record korup.
2.  **Stage 2 - Sliding Window Time-Series Grouper (`itertools` / Generator Coroutine):**
    Implementasikan generator berbasis state windowing. Untuk setiap akun (`account_id`), pantau transaksi dalam rentang jendela waktu 10 detik terakhir (*sliding window*).
3.  **Stage 3 - Fraud Business Logic Heuristics (Pure Functions):**
    Deteksi pola penipuan kartu kredit:
    *   *Velocity Attack:* Sebuah akun melakukan lebih dari 3 transaksi dalam kurun waktu kurang dari 5 detik.
    *   *Geographical Impossibility:* Sebuah akun melakukan transaksi di dua lokasi berbeda dalam jarak waktu kurang dari 1 menit.
4.  **Stage 4 - Metric Accumulator (`functools.reduce` / Stateful Coroutine):**
    Hitung secara real-time total uang yang berhasil diblokir dari transaksi fraud, dan hitung persentase rasio fraud terhadap transaksi normal.

#### Syarat Implementasi
*   Dilarang keras memuat seluruh dataset transaksi ke dalam memori via `list()`, `set()`, atau `dict()` global tak terbatas.
*   Gunakan struktur data `collections.deque(maxlen=...)` di dalam generator window untuk mempertahankan memori tetap konstan terikat waktu.
*   Seluruh pipeline harus disusun secara deklaratif dengan signature:
    ```python
    final_alerts = fraud_detector(window_grouper(sanitizer(raw_feed())))
    ```
*   Tuliskan unit-test sederhana menggunakan modul `unittest` untuk memverifikasi bahwa pipeline tetap me-release resource jika loop pemanggil di-terminasi sebelum stream selesai (`break`).