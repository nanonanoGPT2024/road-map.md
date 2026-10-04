# Kurikulum Enterprise Python: Rekayasa Perangkat Lunak Lanjutan
## Topik: 02-Programming-Languages / Python
### BAB-04: Functional Programming, Iterators, Generator & Streaming Pipeline
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Principal Software Engineer / Senior Data Platform Engineer diharapkan mampu:

1. **Menganalisis Internal Runtime CPython**: Mengurai struktur internal CPython (`PyGenObject`, `PyFrameObject`, `f_lasti`), siklus hidup frame suspension/resumption, dan eksekusi bytecode engine (`YIELD_VALUE`, `RESUME`, `SEND`) pada level C-API.
2. **Merancang Streaming Pipeline Asinkron dan Sinkron**: Mengimplementasikan arsitektur pengolahan data streaming dengan konsumsi memori konstan $O(1)$, zero-copy data flow, serta mekanisme bidirectional coroutine menggunakan `.send()`, `.throw()`, dan `.close()`.
3. **Menguasai Generator Delegation**: Mengorkestrasikan delegasi sub-generator melalui `yield from` untuk transmisi data dua arah transparan, propagasi exception lintas tumpukan frame, serta pengembalian nilai (`return value`) sub-rutin.
4. **Menerapkan Backpressure dan Flow Control**: Merancang antarmuka pipa pemrosesan data (ETL/ELT) terdistribusi yang resilient terhadap memory exhaustion, burst traffic, dan degradasi latensi downstream.
5. **Audit dan Hardening Produksi**: Mengidentifikasi dan memitigasi antipattern kritis seperti *Generator Exhaustion*, kebocoran referensi frame siklik, *blocking I/O injection* dalam pipeline, serta kegagalan *resource cleanup*.

---

### 2. Prerequisite

Sebelum menelaah modul ini, engineer wajib memiliki pemahaman mendalam tentang:
*   **Python Memory Model**: Reference counting, cyclic garbage collection (GC generation 0, 1, 2), pointer references, dan alokasi heap via `PyObject_Malloc`.
*   **Protokol Dasar Iterasi**: Implementasi dasar `__iter__()` dan `__next__()`, serta terminasi iterasi via `StopIteration`.
*   **First-Class Functions & Closures**: Lexical scoping (`LEGB`), free variables, dan object dunder `__closure__`.
*   **Dasar Bytecode CPython**: Kemampuan membaca keluaran modul `dis` (`LOAD_FAST`, `CALL_FUNCTION`, `RETURN_VALUE`).

---

### 3. Concept & Internal Architecture

#### 3.1 Struktur Internal `PyGenObject` pada CPython
Pada CPython, sebuah fungsi yang memiliki *keyword* `yield` dikompilasi secara berbeda dari fungsi standar. Compiler CPython menandai flag kode objek (`co_flags`) dengan bitmask `CO_GENERATOR` (0x0020). Ketika dipanggil, fungsi ini tidak langsung mengeksekusi body-nya, melainkan mengembalikan instansiasi dari struct `PyGenObject` yang dialokasikan di heap:

```c
/* Include/cpython/genobject.h & internal/pycore_frame.h */
typedef struct {
    PyObject_HEAD
    /* Konteks eksekusi frame yang ditangguhkan */
    _PyInterpreterFrame *gi_frame;
    PyObject *gi_name;
    PyObject *gi_qualname;
    _PyErr_StackItem gi_exc_state;
    char gi_status; /* FRAME_CREATED, FRAME_SUSPENDED, FRAME_EXECUTING, FRAME_COMPLETED */
    char gi_hooks_inited;
    /* Informasi debugging dan tracing */
} PyGenObject;
```

#### 3.2 Siklus Hidup Frame Evaluator (`ceval.c`)
Fungsi standar Python dieksekusi di dalam frame CPython (`_PyInterpreterFrame`). Ketika fungsi standar melakukan `return`, frame-nya dialokasikan dan dihancurkan dari stack mesin C. Sebaliknya, generator memisahkan masa hidup frame dari stack mesin C:

1. **Inisialisasi**: Frame generator dibuat di heap. Pointer instruksi `f_lasti` (last instruction offset) disetel ke -1.
2. **Penangguhan (`YIELD_VALUE`)**: Ketika eksekusi mencapai opcode `YIELD_VALUE`, nilai teratas dari *evaluation stack* (TOS) diambil untuk dikembalikan ke caller. Nilai `f_lasti` disimpan, menunjuk tepat setelah opcode yield. State register CPU dikosongkan untuk konteks C, dan status frame generator diubah menjadi `FRAME_SUSPENDED`. Heap frame dipertahankan dari deallokasi.
3. **Pemulihan (`RESUME` / `SEND`)**: Caller memanggil `next(gen)` atau `gen.send(val)`. Evaluator CPython memuat kembali context `gi_frame`, menaruh argumen `val` ke atas evaluation stack, memperbarui status menjadi `FRAME_EXECUTING`, dan melompat langsung ke instruksi bytecode yang ditunjuk oleh `f_lasti`.
4. **Terminasi**: Ketika body fungsi mencapai `return` atau EOF, CPython mengeksekusi `RETURN_VALUE`. Runtime melempar exception `StopIteration`, status frame diubah menjadi `FRAME_COMPLETED`, dan referensi ke local variables di dalam frame dibebaskan (`_PyFrame_Clear()`).

```
                +-------------------+
                |   FRAME_CREATED   |
                +-------------------+
                          |
                          | next() / send(None)
                          v
        +-------->+-------------------+<-------+
        |         |  FRAME_EXECUTING  |        |
        |         +-------------------+        |
yield   |                   |                  | resume via
value   |                   | YIELD_VALUE      | send() / next()
        |                   v                  |
        +---------+-------------------+--------+
                  |  FRAME_SUSPENDED  |
                  +-------------------+
                            |
                            | return / StopIteration / Uncaught Exception
                            v
                  +-------------------+
                  |  FRAME_COMPLETED  |
                  +-------------------+
```

#### 3.3 Mekanika `yield from` (PEP 380 Delegation)
Konstruksi `yield from <expr>` bukan sekadar sintaks gula untuk loop `for item in <expr>: yield item`. `yield from` membuka kanal koneksi langsung (bidirectional tunnel) antara *caller* eksternal dan *sub-generator*:

*   **Penerusan Nilai (`send`)**: Nilai yang dikirimkan via `.send()` langsung disuntikkan ke evaluation stack sub-generator tanpa intervensi frame generator pendelegasi.
*   **Penanganan Eksepsi (`throw`)**: Panggilan `.throw()` dialirkan langsung ke sub-generator. Jika sub-generator menangani eksepsi tersebut dan menghasilkan yield baru, eksekusi pendelegasi tetap berlanjut normal.
*   **Pembersihan Tertib (`close`)**: Panggilan `.close()` memicu propagasi recursive `GeneratorExit` ke sub-generator terdalam.
*   **Pengembalian Nilai Final**: Nilai ekspresi `yield from` adalah argumen yang dibawa oleh `StopIteration(value)` sub-generator saat terminasi (yaitu nilai dari statement `return <expr>` pada sub-generator).

---

### 4. Why & What

| Paradigma / Pendekatan | Karakteristik Memori | Latensi Elemen Pertama | Throughput / IO Overhead | Kompleksitas Skalabilitas |
| :--- | :--- | :--- | :--- | :--- |
| **In-Memory Materialization** (`list`, `dict`) | $O(N)$ — Memori proporsional total volume data. | Tinggi (harus memproses $100\%$ batch sebelum data pertama keluar). | Optimal untuk operasi berbasis indeks/in-place sorts, buruk untuk stream masif. | Buruk; crash seketika akibat OOM (Out Of Memory) jika $N > RAM$. |
| **Chunk-based Processing** (e.g., Pandas Chunks) | $O(k)$ — Proporsional terhadap ukuran chunk konstan $k$. | Menengah (memproses satu partisi chunk). | Sedikit overhead pada boundary chunk; memory fragmentation tinggi. | Menengah; membutuhkan re-assembly stateful jika data terpotong chunk. |
| **Streaming Generator Pipeline** (`yield`, itertools) | $O(1)$ — Konstan, hanya menampung representasi elemen aktif. | Sangat Rendah (instan; emisi streaming item demi item). | Zero-copy data handling; minimal cache-invalidation; low footprint. | Sangat Tinggi; skalabilitas linear tanpa peningkatan footprint RAM. |

*   **Mengapa Generator Vital untuk Skala Enterprise?**
    1. **Eliminasi Memory Pressure**: Menghilangkan fenomena lonjakan GC (Garbage Collection spikes) akibat alokasi objek sementara bervolume jutaan.
    2. **Compositional Pipelining**: Operator transformasi data (Filter, Map, Enrich, Aggregate) dapat dirangkai layaknya pipa sistem operasi Unix (`stdout | stdin`) menggunakan pure functions yang decoupled.
    3. **Elastic Backpressure Support**: Konsumen hilir (*downstream consumer*) mendikte kecepatan produsen hulu (*upstream producer*). Hulu berhenti beroperasi saat hilir tertahan operasi I/O, mencegah overflow buffer memori.

---

### 5. How (Workflow Detail)

Alur kerja arsitektur pemrosesan data berbasis generator enterprise diimplementasikan sebagai alur berarah (*directed acyclic pipeline*):

```
+-----------------------------------------------------------------------------------------+
|                                    GENERATOR LIFECYCLE                                  |
+-----------------------------------------------------------------------------------------+
  [Producer Source]               [Transform Pipeline]                [Consumer / Sink]
     File/Socket                     Filter & Schema                     Storage/API
          |                                 |                                 |
          |  (1) Instansiasi Iterator       |                                 |
          |-------------------------------->|                                 |
          |                                 |  (2) Binding Generator Pipeline |
          |                                 |-------------------------------->|
          |                                 |                                 |
          |                                 |        (3) next() / Pull Event  |
          |                                 |<--------------------------------|
          |        (4) next() / Delegasi    |                                 |
          |<--------------------------------|                                 |
          |                                 |                                 |
          |  (5) YIELD_VALUE (Payload)      |                                 |
          |================================>|                                 |
          |   [Frame Producer Suspended]    |  (6) YIELD_VALUE (Transformed)  |
          |                                 |================================>|
          |                                 |    [Frame Pipeline Suspended]   |
          |                                 |                                 |
          |                                 |        (7) next() / Pull Event  |
          |                                 |<--------------------------------|
          |        (8) next() / Delegasi    |                                 |
          |<--------------------------------|                                 |
          |              ...                |              ...                |
```

1. **Binding Pipeline**: Pipeline diinisialisasi secara deklaratif tanpa eksekusi komputasi. Setiap generator menerima objek iterator sebelumnya sebagai argumen parameter.
2. **Pull Mechanics**: Sink hilir memanggil metode `__next__()`. Panggilan ini merambat ke hulu secara bertingkat hingga mencapai *root producer*.
3. **State Suspension**: Root producer membaca potongan data I/O terkecil (e.g., streaming chunk via buffer socket), meng-yield hasilnya, dan frame runtime-nya dibekukan (*suspended*).
4. **Inline Transformation**: Nilai mengalir melalui node transformasi perantara, diverifikasi, ditransformasi secara in-place, lalu diteruskan ke sink.
5. **Bidirectional Feedback (Opsional via Coroutine)**: Jika sink mendeteksi degradasi performa atau anomali skema, sink dapat mengirimkan payload balasan via `.send(feedback_metric)` atau menyuntikkan terminasi terencana menggunakan `.throw(DataCorruptionError)`.

---

### 6. Analogy & Diagram ASCII

#### Analogi Dunia Nyata
Bayangkan sebuah pabrik perakitan mobil.
*   **Pendekatan List (Materialisasi)**: Anda memesan 1.000.000 ton baja, menyimpannya di gudang (membutuhkan area penyimpanan raksasa bernilai mahal), mencetak seluruh 1.000.000 pintu sekaligus, lalu menyimpannya lagi, sebelum akhirnya merakit 1.000.000 mobil bersamaan. Jika gudang penuh, pabrik kolaps (OOM Crash).
*   **Pendekatan Generator Pipeline (Just-in-Time/JIT)**: Satu lembar baja dipotong dari mesin penggulung (Source Yield), langsung dibentuk oleh mesin pres (Transform Yield), dicat (Enrich Yield), lalu dipasang di mobil (Sink). Area gudang hanya berukuran untuk *satu* lembar baja pada setiap waktu.

```
Pendekatan Batch (In-Memory Materialization):
Data Source [=== 10GB Data ===] 
   ---> RAM: [=== 10GB Raw ===] (Alokasi 1)
   ---> RAM: [=== 10GB Parsed ===] (Alokasi 2) -> TOTAL PEAK: 20GB! 
        (Resiko High Latency & OOM Killer)

Pendekatan Streaming Generator:
Data Source [=== 10GB Data ===]
   ---> [Chunk 64KB] -> [Parse] -> [Filter] -> [Sink]
        ^                                        |
        +-- (Ukuran Buffer Memori Konstan O(1): ~64KB Terlepas dari Volume File) --+
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Dynamic State Coroutine via Bytecode Manipulation
Contoh fundamental penggunaan bidirectional coroutine dengan verifikasi frame inspection.

```python
from inspect import getgeneratorstate, GEN_CREATED, GEN_SUSPENDED, GEN_CLOSED
from typing import Generator

def dynamic_accumulator() -> Generator[float, float, float]:
    """
    Coroutine akumulator bergerak.
    Menerima float via .send(), mengembalikan rata-rata berjalan,
    dan mengembalikan total kumulatif saat ditutup secara graceful.
    """
    total: float = 0.0
    count: int = 0
    running_average: float = 0.0

    try:
        while True:
            # yield nilai saat ini, tangguhkan frame, lalu terima masukan baru
            payload = yield running_average
            if payload is None:
                continue
            total += payload
            count += 1
            running_average = total / count
    except GeneratorExit:
        # Penanganan pembersihan state internal
        return total

# Execution Test
coro = dynamic_accumulator()
assert getgeneratorstate(coro) == GEN_CREATED

# Priming generator (maju ke statement yield pertama)
initial_val = next(coro)
assert initial_val == 0.0
assert getgeneratorstate(coro) == GEN_SUSPENDED

# Mengirim data secara dinamis
print(f"Rata-rata: {coro.send(10.0)}")  # 10.0
print(f"Rata-rata: {coro.send(20.0)}")  # 15.0
print(f"Rata-rata: {coro.send(30.0)}")  # 20.0

# Menutup coroutine secara terkendali
coro.close()
assert getgeneratorstate(coro) == GEN_CLOSED
```

#### 7.2 Practical Example: Industrial-Grade Bidirectional Pipeline Protocol
Implementasi komponen pipeline enterprise yang menerapkan `yield from`, strict typing, safe context delegation, serta resilience exception.

```python
from collections.abc import Generator, Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import sys
from typing import Any, TypeVar

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("StreamingEngine")

TIn = TypeVar("TIn")
TOut = TypeVar("TOut")

@dataclass(frozen=True, slots=True)
class TelemetryEvent:
    device_id: str
    temperature_celsius: float
    timestamp: float

@dataclass(frozen=True, slots=True)
class EnrichedAlert:
    device_id: str
    metric: float
    alert_level: str
    emitted_at: str

def telemetry_source(total_events: int) -> Iterator[str]:
    """Simulasi data source mentah berskala besar (NDJSON format)."""
    for i in range(total_events):
        # Simulasi lonjakan data secara acak
        temp = 20.0 + (i % 15) * 2.5
        yield f'{{"device_id": "sensor-x{i:04d}", "temp": {temp}, "ts": 1700000000.0}}'

def json_parser_subgen(
    upstream: Iterator[str]
) -> Generator[TelemetryEvent, None, int]:
    """
    Sub-generator: Parsing payload mentah, memvalidasi skema,
    dan mengembalikan total data yang berhasil diproses.
    """
    import json
    parsed_count = 0
    for raw_line in upstream:
        try:
            doc = json.loads(raw_line)
            yield TelemetryEvent(
                device_id=doc["device_id"],
                temperature_celsius=float(doc["temp"]),
                timestamp=float(doc["ts"]),
            )
            parsed_count += 1
        except (json.JSONDecodeError, KeyError, ValueError) as err:
            logger.warning("Kegagalan deserialisasi record: %s, payload: %s", err, raw_line)
            continue
    return parsed_count

def anomaly_detector_subgen(
    threshold: float
) -> Generator[EnrichedAlert, TelemetryEvent, None]:
    """
    Bidirectional Consumer: Mengaudit stream event secara streaming
    menggunakan pola send-driven push stream.
    """
    alert_count = 0
    while True:
        # Menerima event baru dari luar
        event: TelemetryEvent = yield  # type: ignore[assignment]
        if event is None:
            continue
        if event.temperature_celsius > threshold:
            alert_count += 1
            yield EnrichedAlert(
                device_id=event.device_id,
                metric=event.temperature_celsius,
                alert_level="CRITICAL" if event.temperature_celsius > 45.0 else "WARNING",
                emitted_at=datetime.now(timezone.utc).isoformat(),
            )

class PipelineOrchestrator:
    """
    Koordinator pemrosesan stream zero-copy delegatif via PEP 380.
    """
    @staticmethod
    def run_pipeline(source: Iterator[str]) -> Generator[TelemetryEvent, None, int]:
        logger.info("Menginisialisasi pipeline pipeline delegation via yield from...")
        # Delegasi kontrol tumpukan frame sepenuhnya ke json_parser_subgen
        total_parsed: int = yield from json_parser_subgen(source)
        logger.info("Subgenerator parsing selesai dieksekusi.")
        return total_parsed

# Demonstrasi Eksekusi
if __name__ == "__main__":
    raw_stream = telemetry_source(total_events=5)
    pipeline = PipelineOrchestrator.run_pipeline(raw_stream)

    try:
        while True:
            event = next(pipeline)
            print(f"[Consumer Sink] Diterima: {event}")
    except StopIteration as stop:
        # Nilai kembalian sub-generator ditangkap via ekspresi StopIteration.value
        total = stop.value
        print(f"[Pipeline Complete] Total event valid diekstrak: {total}")
```

---

### 8. Real World Case Study: High-Frequency Financial Tick Architecture

#### Konteks Masalah
Sebuah platform broker kuantitatif global menerima stream transaksi pasar (Trade Ticks) berukuran ratusan gigabyte per hari melalui socket raw TCP/IPC. 
*   **Permasalahan**: Arsitektur lama membaca data per batch (50.000 transaksi sekaligus via list comprehension), mengakibatkan memori server sering melonjak tajam melewati batas 16 GB, memicu GC pauses selama 400-800 milidetik, yang melanggar SLA latensi eksekusi algoritma trading (< 5 milidetik).
*   **Solusi**: Membangun *Streaming Tick Ingestion Engine* yang menerapkan zero-copy generator chains, sliding window aggregation dengan array sirkuler konstan, serta mitigasi memory pressure menggunakan protocol iterasi Python native.

#### Implementasi Produksi

```python
from collections import deque
from collections.abc import Generator, Iterator
from dataclasses import dataclass
import gc
import math
import sys
import time
import tracemalloc
from typing import Final, NamedTuple

# Optimasi alokasi struktur data menggunakan NamedTuple untuk memory layout C-level
class MarketTick(NamedTuple):
    symbol: str
    price: float
    volume: int
    timestamp_ns: int

class VolatilityMetric(NamedTuple):
    symbol: str
    window_mean: float
    standard_deviation: float
    window_ticks: int

class SyntheticSocketBuffer:
    """Simulasi driver low-level socket non-blocking I/O."""
    def __init__(self, total_packets: int) -> None:
        self._total = total_packets
        self._curr = 0

    def read_packets(self, chunk_size: int = 256) -> Iterator[list[bytes]]:
        """Streaming chunk data byte secara deterministik."""
        while self._curr < self._total:
            batch: list[bytes] = []
            for _ in range(min(chunk_size, self._total - self._curr)):
                self._curr += 1
                # Format: SYMBOL,PRICE,VOL,TIMESTAMP
                tick_bytes = f"NVDA,{130.0 + (self._curr % 20) * 0.15},{100 + self._curr},{time.time_ns()}".encode("ascii")
                batch.append(tick_bytes)
            yield batch

class TickProcessingPipeline:
    __slots__ = ("_window_size", "_raw_source")

    def __init__(self, raw_source: SyntheticSocketBuffer, window_size: int = 1000) -> None:
        self._window_size: Final[int] = window_size
        self._raw_source: Final[SyntheticSocketBuffer] = raw_source

    def byte_deserializer(self) -> Generator[MarketTick, None, None]:
        """Node 1: Transformasi byte stream ke Immutable Tick Struct O(1)."""
        for chunk in self._raw_source.read_packets():
            for raw_tick in chunk:
                # Bypass split overhead via direct string parsing
                sym, prc, vol, ts = raw_tick.decode("ascii").split(",")
                yield MarketTick(
                    symbol=sym,
                    price=float(prc),
                    volume=int(vol),
                    timestamp_ns=int(ts),
                )

    def tick_filter(self, upstream: Iterator[MarketTick], target_symbol: str) -> Generator[MarketTick, None, None]:
        """Node 2: Predicate Engine filtering in-flight data."""
        for tick in upstream:
            if tick.symbol == target_symbol:
                yield tick

    def sliding_window_volatility(
        self, upstream: Iterator[MarketTick]
    ) -> Generator[VolatilityMetric, None, None]:
        """
        Node 3: Sliding window Welford's algorithm untuk single-pass streaming
        standard deviation calculation tanpa re-iterasi window.
        Memory footprint: O(Window Size).
        """
        window: deque[float] = deque(maxlen=self._window_size)
        
        # Variabel algoritma single-pass
        for tick in upstream:
            price = tick.price
            window.append(price)

            if len(window) >= 2:
                # Evaluasi Mean & Deviasi Standar berbasis elemen window aktif
                n = len(window)
                mean = sum(window) / n
                variance = sum((x - mean) ** 2 for x in window) / (n - 1)
                std_dev = math.sqrt(variance)

                yield VolatilityMetric(
                    symbol=tick.symbol,
                    window_mean=mean,
                    standard_deviation=std_dev,
                    window_ticks=n,
                )

    def execute_live_pipeline(self) -> None:
        """Entry point eksekusi pipeline hilir."""
        deserializer = self.byte_deserializer()
        filter_node = self.tick_filter(deserializer, target_symbol="NVDA")
        volatility_node = self.sliding_window_volatility(filter_node)

        # Sink Execution: Konsumsi elemen
        processed = 0
        for metric in volatility_node:
            processed += 1
            if processed % 10000 == 0:
                # Log status secara berkala tanpa interupsi stream
                pass

if __name__ == "__main__":
    # Benchmark Memori Profiling
    tracemalloc.start()
    gc.collect()
    start_time = time.perf_counter()

    TOTAL_STREAM_TICKS = 100_000
    mock_socket = SyntheticSocketBuffer(total_packets=TOTAL_STREAM_TICKS)
    engine = TickProcessingPipeline(raw_source=mock_socket, window_size=500)
    
    engine.execute_live_pipeline()

    current_mem, peak_mem = tracemalloc.get_traced_memory()
    elapsed = time.perf_counter() - start_time
    tracemalloc.stop()

    print(f"=== METRIK PERFORMA PIPELINE STREAMING ===")
    print(f"Total Ticks Diproses : {TOTAL_STREAM_TICKS:,} events")
    print(f"Waktu Eksekusi       : {elapsed:.4f} detik ({TOTAL_STREAM_TICKS/elapsed:,.0f} ops/sec)")
    print(f"Peak Memory Footprint: {peak_mem / 1024:.2f} KiB")
    print(f"Current Memory In-Use: {current_mem / 1024:.2f} KiB")
    
    # Assert bahwa memori peak berada di bawah batas ambang 1.5MB
    assert peak_mem < 1.5 * 1024 * 1024, "Memory breach! Pipeline melanggar batas O(1)."
```

---

### 9. Trade-offs

Menggunakan arsitektur berbasis Generator dan Functional Iterator bukanlah solusi tanpa konsekuensi (*no silver bullet*). Evaluasi trade-off berikut wajib dianalisis secara arsitektural:

```
    Memori Rendah & Latensi Inisial Cepat
                     ▲
                    / \
                   /   \
  Streaming Pipeline    \    In-Memory Batch
  (Generator Chains)     \   (List, Polars, Vectorized)
         /                \
        /                  \
       ▼                    ▼
Debugging Lebih Sulit &     Throughput Maksimum CPU &
Overhead Per-Elemen         Akses Data Acak (Indexing)
```

1. **Overhead Panggilan Fungsi (Function Call Overhead)**:
   *   *Dampak*: Setiap iterasi generator memicu evaluasi loop CPython dan context suspension/resumption. Untuk operasi aritmatika murni skala besar, pemrosesan per-elemen via generator dapat 2x hingga 5x lebih lambat daripada operasi ter-vektorisasi (seperti NumPy SIMD atau Apache Arrow).
   *   *Solusi*: Gunakan teknik *micro-batching*; lakukan *yield* pada sekumpulan array ter-vektorisasi (misal: 1 chunk berukuran 1.000 elemen) alih-alih skalar tunggal.

2. **Hilangnya Kemampuan Indeksasi Acak (Random Access Denial)**:
   *   *Dampak*: Iterator bersifat *forward-only* dan *ephemeral*. Anda tidak dapat melakukan operasi `stream[50]` atau `len(stream)` tanpa mengonsumsi dan menghancurkan state iterator hingga indeks tersebut.
   *   *Solusi*: Gunakan `itertools.tee` (hati-hati terhadap retensi memori buffer) atau caching lokal selektif.

3. **Debugging dan Stack Traces Complexity**:
   *   *Dampak*: Ketika eksepsi terjadi di tengah generator pipeline yang dalam, tumpukan frame trace terputus secara modular di titik `yield`, menyamarkan jejak asal muasal state internal data yang cacat (*tainted data*).

---

### 10. Common Mistakes & Troubleshooting

#### Antipola 1: The "Accidental Re-Iteration" (Generator Exhaustion Silent Bug)
*Problem*: Mengonsumsi iterator yang telah terpakai (*exhausted*), mengakibatkan iterasi berikutnya menghasilkan loop kosong tanpa adanya peringatan error secara eksplisit.

```python
# KODE BERBAHAYA (ANTI-PATTERN)
def fetch_users():
    yield "admin"
    yield "operator"

users = fetch_users()

# Auditor membaca data
if any(u == "admin" for u in users):
    send_security_alert()

# Eksekusi logging (BUG: users SUDAH EXHAUSTED / KOSONG!)
for user in users:
    write_audit_log(user) # Tidak akan pernah dieksekusi!
```

```python
# PERBAIKAN ENTERPRISE (PRODUCTION-READY)
from collections.abc import Iterable, Iterator

def fetch_users_safe() -> Iterable[str]:
    # Bungkus dalam factory generator yang selalu menghasilkan instance baru
    return ("admin", "operator")

# ATAU: Menggunakan runtime validation via Collection Protocol
users_gen: Iterator[str] = iter(["admin", "operator"])
# Konsumsi hanya sekali secara eksplisit dan transformasikan ke struktur permanen jika multi-read mutlak dibutuhkan.
```

#### Antipola 2: Kebocoran Memori Siklik Akibat Penangkapan Frame Generator (`gen.gi_frame`)
*Problem*: Menghubungkan frame generator yang aktif ke dalam exception handler atau local variable yang saling merujuk silang, sehingga Garbage Collector menunda pembersihan memori.

```python
# KODE BERBAHAYA
def memory_leak_pipeline(stream):
    frame_tracker = []
    for item in stream:
        try:
            yield item * 2
        except Exception as e:
            # e.__traceback__.tb_frame mereferensikan gi_frame secara siklik!
            frame_tracker.append(e) 

# PERBAIKAN: Selalu putus referensi siklik exception
try:
    ...
except Exception as e:
    logger.error("Failed: %s", e)
finally:
    # Explicitly clear internal exception reference
    del e
```

#### Panduan Troubleshooting Operasional
*   **Gejala**: Memori pipeline membengkak perlahan meskipun menggunakan `yield`.
    *   *Akar Masalah*: Ada pemanggilan fungsi internal yang memicu materialisasi diam-diam, seperti `sorted()`, `list()`, penggunaan regex tanpa flag stream, atau penggunaan `itertools.tee` di mana salah satu cabang konsumen tertinggal sangat jauh di belakang konsumen lainnya.
    *   *Audit*: Pasang tracing hook menggunakan `sys.settrace()` atau pantau menggunakan profil library memory allocator:
    ```bash
    python -m memray run --live-remote production_pipeline.py
    ```

---

### 11. Best Practices (Production Checklist)

| Tahapan Arsitektur | Kriteria Audit Produksi | Status Verifikasi |
| :--- | :--- | :--- |
| **Type Integrity** | Seluruh pipeline menggunakan pengetikan ketat: `collections.abc.Iterator[T]` atau `collections.abc.Generator[YieldType, SendType, ReturnType]`. | [ ] Mandatory |
| **Resource Safety** | File handle, database cursor, socket connection yang dibuka di dalam generator dibungkus dalam blok `try...finally` atau Context Manager untuk merespons `.close()` via `GeneratorExit`. | [ ] Mandatory |
| **No Silent Exhaustion** | Fungsi tidak menerima instance `Iterator` jika berniat mengonsumsinya lebih dari satu kali; validasi menggunakan `isinstance(data, collections.abc.Iterator)` untuk melempar `TypeError`. | [ ] Mandatory |
| **O(1) Memory Guarantee** | Tidak ada pemanggilan operasi greedy-aggregation (`list()`, `tuple()`, `set()`, `sorted()`) di dalam loop rantai transformasi generator. | [ ] Mandatory |
| **Micro-Batching** | Untuk sistem throughput tinggi, pipeline mengalirkan batched arrays / tuples per tick (100 - 10.000 items) guna menekan calling overhead evaluation loop CPython. | [ ] Recommended |
| **Propagasi Trace ID** | Objek metadata distributed tracing (misal: OpenTelemetry trace context) dilekatkan pada setiap entitas record stream untuk memudahkan observabilitas lintas node generator. | [ ] Mandatory |

---

### 12. Hands-on Practice

Simpan seluruh file praktikum ini ke dalam direktori: `hands-on/m02/`

#### Struktur Proyek
```bash
hands-on/m02/
├── app.py
├── test_pipeline.py
└── stream_framework.py
```

#### Langkah 1: Buat Engine Core Framework (`stream_framework.py`)
Membangun abstraction base class pipeline generator yang mendukung pipe-operator syntax (`|`).

```python
# hands-on/m02/stream_framework.py
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator
from typing import Generic, TypeVar

T = TypeVar("T")
U = TypeVar("U")

class StreamNode(ABC, Generic[T, U]):
    def __init__(self) -> None:
        self._upstream: Iterator[T] | None = None

    def __iter__(self) -> Iterator[U]:
        if self._upstream is None:
            raise RuntimeError("StreamNode belum diikat ke data source upstream!")
        return self._process(self._upstream)

    def __or__(self, other: "StreamNode[U, Any]") -> "StreamNode[U, Any]":
        other._upstream = iter(self)
        return other

    @abstractmethod
    def _process(self, upstream: Iterator[T]) -> Iterator[U]:
        pass

class Source(StreamNode[None, T]):
    def __init__(self, iterable_factory: Callable[[], Iterator[T]]) -> None:
        super().__init__()
        self._factory = iterable_factory

    def _process(self, _: Iterator[None]) -> Iterator[T]:
        return self._factory()

    def __iter__(self) -> Iterator[T]:
        return self._factory()

class Filter(StreamNode[T, T]):
    def __init__(self, predicate: Callable[[T], bool]) -> None:
        super().__init__()
        self._predicate = predicate

    def _process(self, upstream: Iterator[T]) -> Iterator[T]:
        for item in upstream:
            if self._predicate(item):
                yield item

class Map(StreamNode[T, U]):
    def __init__(self, mapper: Callable[[T], U]) -> None:
        super().__init__()
        self._mapper = mapper

    def _process(self, upstream: Iterator[T]) -> Iterator[U]:
        for item in upstream:
            yield self._mapper(item)
```

#### Langkah 2: Buat Pipeline Produksi (`app.py`)
Mengintegrasikan komponen yang aman terhadap resource shutdown.

```python
# hands-on/m02/app.py
from collections.abc import Iterator
import contextlib
import time
from stream_framework import Source, Filter, Map

def generate_log_records() -> Iterator[str]:
    logs = [
        "200:GET:/api/v1/users",
        "500:POST:/api/v1/checkout",
        "200:GET:/api/v1/products",
        "404:GET:/api/v1/orders/999",
        "503:POST:/api/v1/payments",
    ]
    for log in logs:
        yield log

@contextlib.contextmanager
def managed_pipeline_execution():
    logger_source = Source(generate_log_records)
    filter_errors = Filter(lambda line: line.startswith(("500", "503")))
    transform_enrich = Map(lambda err: f"[INCIDENT] Server Fault Detected: {err}")

    pipeline = logger_source | filter_errors | transform_enrich
    try:
        yield pipeline
    finally:
        # Tempat mendaftarkan mekanisme flushing / socket cleanup
        print("[Framework] Melakukan teardown pipeline gracefully...")

if __name__ == "__main__":
    with managed_pipeline_execution() as stream:
        for incident in stream:
            print(f"Action Required -> {incident}")
```

#### Langkah 3: Unit & Performance Testing (`test_pipeline.py`)

```python
# hands-on/m02/test_pipeline.py
import pytest
from stream_framework import Source, Filter, Map

def test_pipeline_zero_copy_composition():
    source_data = lambda: iter(range(10))
    pipeline = (
        Source(source_data) 
        | Filter(lambda x: x % 2 == 0) 
        | Map(lambda x: x * 10)
    )
    
    result = list(pipeline)
    assert result == [0, 20, 40, 60, 80]

def test_stream_node_unbound_raises_runtime_error():
    unbound_filter = Filter(lambda x: True)
    with pytest.raises(RuntimeError):
        list(unbound_filter)
```

Eksekusi pengujian:
```bash
pytest hands-on/m02/test_pipeline.py -v
python hands-on/m02/app.py
```

---

### 13. Exercise

#### Level Easy
*   **Tugas**: Buatlah generator `chunked_stream(source: Iterator[T], chunk_size: int) -> Iterator[list[T]]` yang mengelompokkan elemen stream hulu menjadi partisi berukuran `chunk_size` secara konstan $O(chunk\_size)$ memori tanpa menggunakan dependency eksternal. Tangani kasus edge jika data terakhir tidak genap memenuhi ukuran chunk.

#### Level Medium
*   **Tugas**: Implementasikan pipeline generator bidirectional interaktif yang memproses sequence transaksi keuangan. Gunakan `.send(new_fx_rate)` untuk memperbarui nilai tukar valuta asing (FX Rate) secara real-time pada generator yang sedang aktif berjalan di tengah loop pemrosesan tanpa merestart state pipeline.

#### Level Hard
*   **Tugas**: Rancang custom iterator engine berbasis struktur data *B-Tree stream-merger*. Engine harus menerima $K$ buah file sorted integer generators yang tak terbatas (infinite/streaming), lalu mengembalikan stream terurut tunggal yang terintegrasi (*merged sorted stream*).
*   *Batasan Operasional*: Memori maksimum sistem harus tetap terikat secara statis pada kompleksitas $O(K)$, bukan $O(N)$ dari total record. Akselerasikan deteksi nilai minimum dengan algoritma Min-Heap berbasis C-level struct via `heapq`.

---

### 14. Challenge: The Zero-Allocation Realtime Log De-duplicator

#### Kasus Masalah
Perusahaan Anda mengoperasikan 50 cluster gateway Nginx yang menghasilkan rata-rata 30.000 log access lines per detik. Muncul anomali *retry-storm* yang mengakibatkan ribuan log baris identik terduplikasi secara berurutan dalam rentang waktu mikrodetik (*burst window*), membanjiri Elasticsearch cluster.

#### Spesifikasi Tantangan
Bangun sebuah streaming engine mandiri menggunakan arsitektur Python pure-generator tanpa framework pihak ketiga dengan ketentuan teknis absolut berikut:
1. **Deduplikasi Dinamis Berbasis Temporal**: Saring pesan kembar yang masuk dalam rentang *sliding window* 50.000 elemen aktif terakhir.
2. **Karakteristik Alokasi Memori**: Engine dilarang keras mengalokasikan string hashing tak hingga yang menyebabkan memory leak. Total footprint memori engine tidak boleh melampaui **12 MiB**, divalidasi via modul `tracemalloc`, saat dialiri 5.000.000 baris log terus-menerus.
3. **Mekanisme Backpressure Sinkronisasi**: Jika sink down-stream mengalami sleep/delay (misal: simulasi delay jaringan 20ms), generator produsen harus otomatis tertahan pada tingkat I/O buffer tanpa menumpuk cache di memori internal.
4. **Handling Graceful Termination**: Tangani interupsi OS (`SIGTERM` / `KeyboardInterrupt`) secara lossless: generator wajib melakukan `.close()`, mengekstrak summary hash record terakhir yang berhasil lolos, dan menyimpannya ke storage recovery point.

*Kriteria Keberhasilan*: Lulus audit benchmarking zero OOM crash, latensi per pemrosesan item $\le 15$ mikrodetik, dan memory footprint absolut datar ($O(1)$ flat-line memory profile).

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Pertanyaan)
1. **Apa nilai instruksi `f_lasti` pada struct internal `PyGenObject` sesaat setelah fungsi generator diinstansiasi, dan apa indikasinya?**
   * *Jawaban*: Bernilai `-1`. Ini mengindikasikan bahwa objek generator telah berhasil dialokasikan pada heap runtime, namun belum ada pemanggilan `__next__()` pertama kali; bytecode frame-nya berada pada status `FRAME_CREATED` dan belum ada opcode yang dieksekusi.

2. **Mengapa pemanggilan `next()` pada objek generator yang sudah selesai (exhausted) melempar `StopIteration` alih-alih me-restart eksekusi dari baris pertama?**
   * *Jawaban*: Sesuai PEP 234/255, iterator Python beroperasi secara satu arah (*forward-only, single-pass*). Begitu opcode `RETURN_VALUE` tercapai atau badan fungsi tuntas, status frame diubah secara ireversibel menjadi `FRAME_COMPLETED` dan pointer lokalnya dibebaskan oleh CPython untuk mencegah memory leak.

3. **Apa perbedaan fungsional utama antara keyword `return None` dan `yield None` di dalam sebuah generator?**
   * *Jawaban*: `yield None` menangguhkan (*suspends*) frame eksekusi, mengembalikan objek `None` ke caller, mempertahankan register eksekusi dan variabel lokal agar dapat dipulihkan nanti. `return None` menterminasi generator, membersihkan frame, dan memicu exception `StopIteration(None)` ke caller.

4. **Bagaimana mekanisme runtime melewatkan data dari pemanggil ke dalam tubuh generator ketika menggunakan metode `.send(value)`?**
   * *Jawaban*: Runtime CPython mengambil parameter `value`, menempatkannya tepat di puncak *evaluation stack* (TOS) dari frame generator yang sedang ditangguhkan (`gi_frame`), lalu memicu kelanjutan eksekusi melalui opcode pemulihan instruksi runtime C.

5. **Apa fungsi utama statement `yield from` bila ditinjau dari sisi delegasi transmisi return value sub-generator?**
   * *Jawaban*: `yield from` secara otomatis menangkap exception `StopIteration` yang dilemparkan oleh sub-generator internal, lalu mengekstrak atribut `StopIteration.value` (yang berasal dari statement `return <expr>` pada sub-generator) dan menjadikannya sebagai nilai evaluasi dari ekspresi `yield from` itu sendiri.

---

#### Bagian 2: Intermediate (5 Pertanyaan)
6. **Pada CPython modern (Python 3.11+), mengapa overhead alokasi frame generator secara signifikan lebih rendah dibandingkan versi-versi sebelumnya?**
   * *Jawaban*: Berkat PEP 659 dan perombakan arsitektur internal frame, objek frame (`_PyInterpreterFrame`) kini dialokasikan secara *chunked* atau terintegrasi langsung di dalam buffer struct `PyGenObject` itu sendiri, menghindari alokasi heap `PyObject_Malloc` yang terpisah dan mengoptimalkan CPU data cache locality.

7. **Jelaskan siklus propagasi eksepsi ketika method `.throw(CustomException)` dipanggil pada generator yang sedang mendelegasikan eksekusi melalui `yield from`!**
   * *Jawaban*: Generator pendelegasi langsung meneruskan eksepsi tersebut ke method `.throw()` milik sub-generator terdalam. Jika sub-generator menangkap eksepsi tersebut dan mengeksekusi yield baru, nilai yield dialirkan kembali ke pemanggil luar. Jika sub-generator melempar `GeneratorExit` atau tidak menangani eksepsi tersebut, eksepsi menggelembung (*bubbles up*) keluar ke frame pendelegasi.

8. **Mengapa penggunaan `itertools.tee(stream, 2)` dapat membahayakan memori sistem produksi jika kedua cabang iterasi tidak dikonsumsi secara paralel seimbang?**
   * *Jawaban*: `itertools.tee` menahan nilai yang telah diekstrak dari stream utama di dalam buffer FIFO internal (deque) sampai semua turunan iterator mengonsumsinya. Jika konsumen cabang A berjalan 1.000.000 record mendahului konsumen cabang B, maka 1.000.000 record tersebut dipaksa tertahan di memori, merusak jaminan efisiensi $O(1)$.

9. **Apa yang terjadi secara internal jika suatu generator yang sedang aktif menunggu dihentikan oleh runtime melalui garbage collection sebelum tuntas dieksekusi?**
   * *Jawaban*: Destructor `tp_dealloc` pada CPython memanggil method `.close()` pada generator. Ini menyuntikkan exception `GeneratorExit` ke frame yang ditangguhkan. Jika generator menangani `GeneratorExit` namun justru mencoba melakukan `yield` nilai lain, runtime CPython secara instan melempar `RuntimeError: generator ignored GeneratorExit`.

10. **Bagaimana cara mencegah kebocoran file descriptor pada generator yang membaca file besar ketika konsumen hilir secara tiba-tiba memutus iterasi menggunakan statement `break`?**
    * *Jawaban*: Kode pembaca file wajib dibungkus di dalam blok `with open(...) as f:` atau blok `try ... finally: f.close()`. Ketika konsumen memutus loop via `break`, referensi generator yang tidak terikat akan dibersihkan, memicu pemanggilan `.close()` dan eksekusi blok `finally` secara deterministik.

---

#### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan Kompleks)

11. **Skenario 1 (Memory Leak Tracing)**:
    Sebuah microservice data crawler memproses puluhan ribu dokumen XML per menit menggunakan generator streaming bertingkat. Namun, metrik monitoring menunjukkan memori heap Kubernetes Pod meningkat secara persisten hingga terbunuh oleh OOMKilled (Exit Code 137). Dalam kode, ditemukan konstruksi:
    ```python
    def parse_documents(xml_stream):
        for raw_xml in xml_stream:
            tree = etree.fromstring(raw_xml)
            yield tree.xpath("//record/text()")
    ```
    *Analisis dan Solusi*: Mengapa konstruksi ini menyebabkan memori Pod melonjak tajam padahal sudah menggunakan generator `yield`?
    * *Jawaban*: Node objek C-based (seperti `lxml.etree` atau XML DOM C-structures) sering kali memiliki referensi kepemilikan terbalik (*parent reference pointer*) ke seluruh dokumen XML root. Ketika generator meng-yield representasi list atau node teks parsial, seluruh dokumen pohon C-DOM XML tetap terkunci di heap memori karena referensi root-nya belum dihancurkan. Solusinya adalah memanggil `.clear()` secara eksplisit pada node parent atau menggunakan parser parsing streaming murni berbasis SAX / `etree.iterparse()` dengan pembebasan referensi root via `root.clear()`.

12. **Skenario 2 (Deadlock / Latency Spikes pada Async IO Bridge)**:
    Tim platform Anda mencoba menghubungkan generator sinkronus warisan (*legacy sync generator*) dengan event loop asynchronous melalui fungsi:
    ```python
    async def async_data_bridge(sync_generator):
        for item in sync_generator:
            await async_queue.put(item)
    ```
    Sistem mengalami *latency spike* parah dan response time API lain di thread yang sama anjlok drastis. 
    *Analisis dan Solusi*: Di mana letak kesalahan arsitekturalnya dan bagaimana rekonstruksi kodenya?
    * *Jawaban*: Statement `for item in sync_generator:` berjalan sinkron di thread utama event-loop. Jika `sync_generator` melakukan blocking I/O (misal pembacaan disk atau socket jaringan lambat) sebelum mencapai statement `yield`, thread utama terblokir sepenuhnya, melumpuhkan penjadwalan task asinkron lainnya. Solusinya: bungkus iterasi generator di thread terpisah menggunakan `asyncio.to_thread` atau gunakan iterasi off-loop melalui executor:
    ```python
    def safe_poll(gen):
        return next(gen, _SENTINEL)
    # Pindahkan polling item ke worker pool thread agar tidak membekukan event loop
    item = await asyncio.to_thread(safe_poll, sync_generator)
    ```

13. **Skenario 3 (Data Duplication Under Threading Concurrency)**:
    Sebuah service backend membagikan sebuah instance generator objek tunggal ke multi-threading worker pool via `concurrent.futures.ThreadPoolExecutor` untuk memproses data secara paralel. Hasil akhir menunjukkan integritas data rusak parah; banyak elemen terlewat dan beberapa dieksekusi berulang kali.
    *Analisis dan Solusi*: Mengapa generator standar Python tidak *thread-safe*, apa kondisi internal runtime yang rusak, dan bagaimana merancangnya agar aman (*thread-safe generator decorator*)?
    * *Jawaban*: Generator CPython **tidak thread-safe**. Struktur data `_PyInterpreterFrame` tidak memiliki internal thread-locking. Ketika dua thread memanggil `next(gen)` bersamaan, race-condition terjadi pada verifikasi flag frame dan pergeseran offset instruksi `f_lasti`, mengakibatkan korupsi evaluation stack atau race condition pelemparan `StopIteration`. 
    Solusinya adalah membungkus instance generator dengan Mutual Exclusion Lock (Mutex):
    ```python
    import threading

    class ThreadSafeIterator:
        def __init__(self, it):
            self._it = iter(it)
            self._lock = threading.Lock()

        def __iter__(self):
            return self

        def __next__(self):
            with self._lock:
                return next(self._it)
    ```

---

### 16. Summary

1. **CPython Virtual Machine Internals**: Generator adalah fungsi dengan flag `CO_GENERATOR` yang siklus hidup eksekusinya dilepaskan dari C-call stack menuju heap-allocated `PyGenObject`. Penangguhan dan pemulihan frame dikoordinasikan secara efisien oleh opcode `YIELD_VALUE`, `RESUME`, dan `SEND`.
2. **Deterministic Linear Scalability**: Arsitektur streaming berbasis generator menjamin pemrosesan volume data tak terbatas dengan kompleksitas memori konstan $O(1)$, menjauhkan sistem produksi berskala petabyte dari bahaya fatal OS Kernel OOM Killer.
3. **Control Flow Bi-directional**: Melalui PEP 342 (`.send()`, `.throw()`, `.close()`) dan PEP 380 (`yield from`), generator berevolusi dari sekadar produsen pasif menjadi coroutine pemroses data interaktif berkemampuan backpressure flow-control dua arah.
4. **Disiplin Rekayasa Produksi**: Generator menuntut disiplin tinggi terhadap siklus hidup resource (`try...finally`), kewaspadaan terhadap *silent exhaustion*, mitigasi antipola materialisasi tak disengaja, serta kesadaran arsitektural terhadap overhead evaluasi per-elemen CPython runtime. Gunakan micro-batching ketika throughput komputasi SIMD murni diperlukan.