# BAB 09: Quiz, Challenge, & Knowledge Check
**Testing Strategy, Profiling & Performance Tuning**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Semantik Fixture Scoping & State Mutation pada Pytest
Jelaskan perbedaan mendasar siklus hidup (*lifecycle*) dan batas isolasi (*isolation boundary*) antara scope `function`, `module`, dan `session` pada fixture `pytest`. Analisis risiko arsitektural yang muncul ketika sebuah fixture bertipe mutable (misalnya instance koneksi database atau dictionary cache) dideklarasikan dengan scope `session` namun dimodifikasi oleh salah satu test case di tengah eksekusi test suite. Bagaimana cara memitigasi efek samping (*side-effects*) tersebut secara deterministik?

### Soal 1.2: Deterministic vs. Statistical Profiling
Bandingkan mekanisme internal antara *deterministic (event-based) profiler* (seperti `cProfile` yang memanfaatkan hook internal CPython `PyEval_SetProfile`) dengan *statistical (sampling) profiler* (seperti `py-spy` atau `austin`). Kapan seorang arsitek sistem harus melarang penggunaan `cProfile` pada *live production environment*, dan mengapa statistical profiler menjadi pilihan non-intrusif yang jauh lebih aman terhadap latency overhead?

### Soal 1.3: Taksonomi Test Doubles (Gerard Meszaros / Martin Fowler)
Dalam konteks ekosistem Python (`unittest.mock`), jelaskan perbedaan konseptual dan implementatif antara:
1. **Stub**
2. **Spy**
3. **Mock**
4. **Fake**

Berikan contoh kasus di mana penggunaan **Mock** yang berlebihan (*over-mocking*) justru menghasilkan *false positive test suite* (tes berhasil lolos, tetapi integrasi gagal total di level runtime), dan jelaskan mengapa **Fake** (misalnya `InMemoryRepository`) sering kali lebih superior untuk menjaga integritas domain logic.

### Soal 1.4: Dynamic Memory Allocation vs. Object Interning
Jelaskan bagaimana CPython mengelola alokasi memori melalui *Small Object Allocator* (PyMalloc) dan arena/pools. Mengapa eksekusi profiling berbasis waktu komputasi (`timeit`) pada operasi manipulasi string atau integer kecil sering kali memberikan hasil yang bias akibat mekanisme *interning* (*string interning* dan *small integer caching* antara -5 hingga 256)? Bagaimana seorang engineer harus mengisolasi variabel uji agar hasil micro-benchmarking merefleksikan kondisi kerja sebenarnya?

### Soal 1.5: Metrik Kualitas Test: Line Coverage vs. Mutation Testing
Tingkat *code coverage* (line dan branch coverage) sebesar 100% dari tool seperti `coverage.py` tidak menjamin sistem bebas dari celah logika fatal. Jelaskan prinsip kerja *Mutation Testing* (misalnya menggunakan `mutmut` atau `cosmic-ray`). Bagaimana mutation testing mengevaluasi efektivitas *assertion* dalam unit test Anda melalui injeksi *mutants*, dan apa indikasi dari skor *mutant survival rate* yang tinggi?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Resolusi Lookup dan Namespace Leakage pada `unittest.mock.patch`
Diberikan struktur modul sebagai berikut:
```python
# app/services/notifier.py
from app.clients.email import send_email

def notify_user(user):
    return send_email(user.email, "Welcome")
```
Jika seorang developer menulis test dengan deklarasi:
`@patch('app.clients.email.send_email')`, mengapa fungsi `send_email` di dalam `notify_user` **tetap mengeksekusi kode aslinya** dan gagal di-mock? Jelaskan mekanisme namespace binding di Python saat instruksi `from x import y` dieksekusi, serta di mana lokasi patch target yang benar secara deterministik.

### Soal 2.2: Memory Leaks via Reference Cycles dan Siklus Hidup Cyclic GC
Meskipun CPython menggunakan *Reference Counting* sebagai mekanisme utama deallokasi memori, kebocoran memori (*memory leak*) tetap lazim terjadi.
Jelaskan bagaimana siklus referensi melingkar (*reference cycles*) terbentuk (misalnya pada struktur graf atau penanganan *closure exceptions* via `sys.exc_info()`). Bagaimana modul `gc` (Generational Garbage Collector: Gen 0, Gen 1, Gen 2) mendeteksi dan membersihkan siklus tersebut? Apa dampak implementasi metode `__del__` pada objek sebelum Python 3.4 dan sesudah PEP 442?

### Soal 2.3: Profiling Asynchronous Concurrency (`asyncio` Event Loop Latency)
Mengapa penggunaan profiler standar C-extension berbasis thread (`cProfile`) memberikan profil performa yang terdistorsi dan menyesatkan saat digunakan untuk menganalisis aplikasi berbasis `asyncio`? Jelaskan fenomena *Event Loop Lag* dan bagaimana operasi CPU-bound sinkron yang tidak sengaja terpanggil di dalam coroutine dapat memblokir eksekusi coroutine lain. Tool profiling apa yang harus digunakan untuk mengukur *scheduling delay* pada event loop?

### Soal 2.4: Bytecode Disassembly & CPU Cache Locality (`dis` module)
Analisis potongan bytecode berikut yang dihasilkan oleh modul `dis` untuk dua pendekatan iterasi:
1. Pembangunan list via `for loop` tradisional dengan `list.append()`.
2. Pembangunan list via `list comprehension`.

Jelaskan dari perspektif instruksi bytecode CPython (`LIST_APPEND` vs `LOAD_FAST` + `CALL_METHOD`) dan pemanfaatan cache CPU (L1/L2 data cache hit), mengapa *list comprehension* secara konsisten mengungguli loop tradisional. Kapan optimasi ini menjadi tidak relevan akibat I/O bottleneck?

### Soal 2.5: Determinisme Property-Based Testing (Hypothesis Engine)
Dalam pengujian berbasis properti menggunakan library `hypothesis`, sistem menghasilkan ratusan data input acak untuk mencari kegagalan fungsi (*falsification*). Jelaskan mekanisme internal **Shrinking Phase** yang dilakukan `hypothesis` saat menemukan kasus kegagalan. Bagaimana arsitektur engine mempertahankan determinisme uji sehingga input kegagalan yang sama dapat direproduksi secara konsisten di CI/CD pipeline tanpa harus menjalankan ulang seluruh ruang probabilitas?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Latency Spikes (p99 Degradation) pada High-Throughput REST Gateway
* **Konteks:** Sebuah microservice FastAPI melayani 15.000 RPS untuk agregasi data e-commerce. Pada saat load normal, p50 berada di 12ms. Namun, metrik p99 melonjak secara sporadis hingga 1.800ms setiap 3 hingga 5 menit sekali, menyebabkan *timeout cascading* pada upstream reverse proxy (Nginx).
* **Observasi Awal:** CPU utilization server melonjak ke 100% pada satu core secara bergantian, metrik alokasi memori RSS (*Resident Set Size*) menunjukkan pola gigi gergaji (*sawtooth pattern*), dan log aplikasi tidak mencatat error koneksi basis data.
* **Pertanyaan Diagnostik:**
  1. Bagaimana metodologi Anda dalam mengidentifikasi apakah lonjakan p99 tersebut disebabkan oleh siklus eksekusi Generational Garbage Collector CPython (Gen 2 collection lock-up), deserialisasi payload JSON yang masif, atau *event loop blocking*?
  2. Rancang strategi instrumentasi performa (menggunakan `tracemalloc`, `yappi`, atau `py-spy`) di lingkungan staging yang dapat mereproduksi dan membedah bottleneck ini tanpa mendegradasi performa I/O asynchronous.

---

### Skenario B: Flaky Test Suite Execution pada Distributed CI Runner (`pytest-xdist`)
* **Konteks:** Sebuah pipeline CI/CD menjalankan 4.000 automated tests menggunakan `pytest -n auto` (multiprocessing worker). Test suite sering gagal secara intermiten (flakiness rate ~8%) dengan error bervariasi: `IntegrityError: duplicate key value violates unique constraint` pada PostgreSQL test container, dan `AttributeError: 'NoneType' object has no attribute 'x'` pada mocking Redis client. Saat test yang gagal dijalankan secara terisolasi (`pytest path/to/failed_test.py`), pengujian selalu sukses 100%.
* **Pertanyaan Diagnostik:**
  1. Bedah potensi *root-cause* terjadinya *race conditions* dan *cross-worker contamination* antar worker process pada `pytest-xdist`.
  2. Rancang arsitektur isolasi data state untuk layer database relasional dan shared global cache (Redis) agar setiap worker memiliki sandbox runtime yang hermetis dan deterministik.

---

### Skenario C: Architectural Trade-off: Stream Processing Memory Footprint
* **Konteks:** Sistem ETL internal bertugas mengekstrak dan memvalidasi file batch log berukuran 120GB setiap jam pada node pekerja dengan kapasitas RAM terbatas (16GB RAM). Implementasi awal menggunakan `pandas.read_csv` berujung pada crash sistem akibat *OOM (Out Of Memory) Killer*. Tim engineering terbelah menjadi 3 kubu solusi:
  * *Opsi 1:* Migrasi pipeline ke `Polars` berbasis *lazy streaming execution*.
  * *Opsi 2:* Menulis ulang core validator menggunakan Python native generator dikombinasikan dengan library `ijson` / `csv` streaming.
  * *Opsi 3:* Penskalaan horizontal membagi file menjadi chunk kecil menggunakan `multiprocessing.Pool`.
* **Pertanyaan Diagnostik:**
  1. Lakukan analisis komparatif mendalam (Trade-off Matrix) terhadap ketiga opsi tersebut dengan mempertimbangkan: Memory safety, CPU utilization di bawah batasan CPython GIL, kompleksitas pemeliharaan kode, dan kemudahan penulisan automated test.
  2. Manakah keputusan arsitektural terbaik jika batasan non-fungsional sistem mengharuskan waktu pemrosesan total di bawah 20 menit tanpa menambah spesifikasi hardware node? Justifikasi pilihan Anda.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Memory-Safe Log Aggregator & Benchmark Harness

#### Problem Statement
Anda menerima kode warisan (*legacy module*) sebuah in-memory log parser yang bertugas membaca log traffic HTTP berukuran besar, mengekstrak status error (HTTP 5xx), menghitung top 10 IP penyerang, dan mengirimkan ringkasannya ke alerting system. Kode tersebut mengalami dua masalah kritis di lingkungan produksi:
1. Memakan memori eksponensial (kebocoran memori hingga OOM saat ukuran file > 2GB).
2. Performa parsing sangat lambat (membutuhkan waktu 95 detik untuk memproses 1 juta baris log).

#### Task & Requirements
1. **Isolasi Masalah via Profiling:**
   * Tulis sebuah profiling script menggunakan modul `cProfile` dan `tracemalloc`. Identifikasi line of code yang menjadi titik alokasi memori tertinggi dan bottleneck CPU terbesar.
   * Dokumentasikan temuan snapshot memori (Top 5 memory consumers by trace line).
2. **Refaktorisasi Arsitektur Engine:**
   * Tulis ulang modul parser menggunakan pendekatan *streaming generator pipeline*.
   * Terapkan struktur data rendah memori (misalnya `__slots__` pada class representasi log, atau tuple parsing alih-alih `dict`).
   * Hilangkan alokasi redundan dan minimalkan *garbage collection overhead*.
3. **Rigorous Automated Test Suite:**
   * Buat test suite lengkap menggunakan `pytest`.
   * Implementasikan minimal 1 *Property-Based Test* menggunakan `hypothesis` untuk memverifikasi parser tahan terhadap karakter anomali (malformed log lines, byte corruptions).
   * Implementasikan automated test untuk mendeteksi *memory regression*: tes harus secara otomatis gagal (*assert fail*) jika konsumsi alokasi memori puncak (*peak memory usage*) pemrosesan log melebihi 50MB, berapapun ukuran dataset uji yang dialirkan.
4. **Benchmark Harness Validation:**
   * Sediakan file micro-benchmark menggunakan `pytest-benchmark` untuk membuktikan adanya peningkatan *throughput* minimal **5x lebih cepat** dibandingkan implementasi awal.

#### Constraints
* Tidak diperbolehkan menggunakan framework eksternal seperti PySpark atau Polars (wajib menggunakan standar pustaka Python murni: CPython 3.11+, `re`, `itertools`, `collections`, `tracemalloc`, dll.).
* Wajib mempertahankan determinisme logging: urutan agregasi tidak boleh menghasilkan deviasi hasil hitung.

#### Expected Output
* Repositori mini / direktori terstruktur berisi:
  1. `legacy_parser.py` (simulasi baseline yang lambat dan memakan memori).
  2. `optimized_parser.py` (engine streaming teroptimasi).
  3. `profiler_report.py` (script diagnostik `cProfile` + `tracemalloc`).
  4. `test_suite/` (berisi unit test, hypothesis test, memory boundary assertion, dan benchmark).
  5. `AUDIT_REPORT.md` (analisis kuantitatif perbandingan metrik memori, execution time, dan mitigasi bottleneck).

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Anatomi Pytest fixtures: dependency injection, cascading teardown (`yield`), dynamic parameterization, dan caching behavior antar scope.
- [ ] Perbedaan fundamental antara deterministic profiler overhead (`sys.setprofile`) dan low-overhead statistical/sampling profilers (`py-spy`).
- [ ] Mekanisme deteksi siklus Generational Garbage Collection CPython (Gen 0, 1, 2 thresholds) serta dampaknya terhadap latency spikes.
- [ ] Aturan resolusi namespace binding pada Python imports dan implikasinya terhadap penempatan target mock patching (`where to patch`).
- [ ] Limitasi Global Interpreter Lock (GIL) terhadap multithreaded profiling serta perbedaannya dengan multi-process/asynchronous profiling.
- [ ] Prinsip Property-Based Testing dan algoritma state shrinking untuk memetakan edge-case kegagalan domain logic.

### Saya tidak perlu menghafal:
- [ ] Seluruh opcode internal CPython dari modul `dis` (cukup pahami instruksi umum terkait loop, call, dan load).
- [ ] Sintaks flag CLI dari setiap profiler tool eksternal (cukup pahami parameter esensial seperti sampling rate dan thread inclusion).
- [ ] API lengkap dari ratusan assertion matchers bawaan (cukup kuasai standard assertions dan manfaatkan dynamic assertion rewriting bawaan Pytest).

### Saya harus bisa melakukan:
- [ ] Mendiagnosis dan menghentikan memory leaks pada aplikasi produksi menggunakan `tracemalloc` dan visualisasi alokasi snapshot.
- [ ] Mengonfigurasi isolasi database dan mock environment secara konkuren pada distributed testing runner (`pytest-xdist`).
- [ ] Mengaudit performa fungsi kritis menggunakan kombinasi `cProfile`, `pstats`, dan flame graph visualizers.
- [ ] Menulis unit test hermetis yang terbebas dari *flakiness*, *test pollution*, dan *temporal coupling*.
- [ ] Mengoptimalkan kode berbasis CPU-bound dan memory-bound ke bentuk zero-copy streaming pipeline menggunakan native Python patterns.