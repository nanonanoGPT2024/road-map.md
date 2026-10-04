# BAB 04: Quiz, Challenge, & Knowledge Check
**Functional Programming, Iterators & Generator Pipeline**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Iterator Protocol & PEP 479 Compliance**
   Jelaskan kontrak formal antara antarmuka `Iterable` dan `Iterator` menurut model data CPython. Mengapa metode `__iter__()` pada objek *Iterator* wajib mengembalikan `self`, dan apa konsekuensi arsitektural di runtime jika sebuah generator membiarkan exception `StopIteration` merembes keluar dari eksekusi internalnya (kaitkan dengan mekanisme PEP 479 / `RuntimeError`)?

2. **Mekanisme Frame Suspension pada Generator**
   Bagaimana CPython mengelola siklus hidup *execution frame* (`PyFrameObject`) ketika eksekusi fungsi generator menjumpai instruksi bytecode `YIELD_VALUE`? Bandingkan alokasi stack frame ini dengan pemanggilan fungsi konvensional yang berakhir dengan `RETURN_VALUE`.

3. **Referential Transparency, Immutability, & Closure Side-Effects**
   Definisikan konsep *referential transparency* dalam paradigma Functional Programming (FP) dan jelaskan dampaknya terhadap optimasi compiler/interpreter. Mengapa penggunaan struktur data mutable (seperti `list` atau `dict`) di dalam *closure* atau *higher-order function* dapat merusak jaminan deterministik ini secara fatal?

4. **Trade-Off Latensi & Memory: Lazy Evaluation vs Eager Evaluation**
   Secara teoritis, *generator expression* (lazy) selalu lebih hemat memori dibanding *list comprehension* (eager). Namun, dalam skenario pemrosesan data berukuran kecil hingga menengah yang membutuhkan iterasi berulang (*multiple traversals*), mengapa penggunaan generator justru dapat menghasilkan degradasi performa (latensi CPU yang lebih tinggi) dibandingkan list comprehension?

5. **Bidirectional Delegation via `yield from`**
   Jelaskan secara presisi mengapa konstruksi `yield from <sub_iterator>` bukan sekadar sintaks alternatif (*syntactic sugar*) untuk `for item in <sub_iterator>: yield item`. Uraikan bagaimana `yield from` menangani propagasi dua arah untuk metode `.send()`, `.throw()`, dan nilai kembalian (*return value*) dari sub-generator.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Late Binding Closures pada Function Factories**
   Perhatikan potongan kode berikut:
   ```python
   transforms = [lambda x: x + i for i in range(5)]
   results = [f(10) for f in transforms]
   ```
   Secara teknis, mengapa `results` menghasilkan `[14, 14, 14, 14, 14]` dan bukan `[10, 11, 12, 13, 14]`? Bedah bagaimana CPython menyelesaikan dereferensi variabel pada *cell object* (`__closure__`) dan sajikan dua teknik refactoring idiomatis untuk memperbaikinya tanpa mengubah struktur komprehensi.

2. **Generator Exhaustion & Arsitektur Re-iterable Container**
   Sebuah pipeline analitik menerima generator stream dan mengeksekusi dua pass: validasi skema, kemudian agregasi data:
   ```python
   def process_data(data_stream):
       if not all(validate(record) for record in data_stream):
           raise ValueError("Invalid record found")
       return aggregate(data_stream)
   ```
   Mengapa fungsi di atas selalu menghasilkan agregasi kosong (`0` atau `None`) meskipun seluruh data valid? Rancang pola kelas (*Custom Iterable Class*) yang mengimplementasikan `__iter__` secara lazy untuk menjamin data dapat diiterasi ulang tanpa memuat seluruh dataset ke dalam RAM sekaligus.

3. **Memory Bloat Mechanism pada `itertools.tee`**
   Dokumentasi Python menyatakan bahwa `itertools.tee(iterable, n)` membagi satu iterable menjadi *n* iterator independen. Jelaskan bagaimana struktur data *FIFO queue* internal `tee` bekerja pada CPython. Pada pola konsumsi data seperti apa `itertools.tee` justru menyebabkan memory leak/bloat yang setara atau lebih buruk daripada memanggil `list(iterable)`?

4. **Anatomi Siklus Hidup: Generator Termination & `GeneratorExit`**
   Kapan instruksi `.close()` dipanggil secara otomatis oleh Garbage Collector? Apa yang terjadi di level interpreter jika seorang developer menangkap exception `GeneratorExit` di dalam blok `try...except` generator lalu mengeksekusi statement `yield` berikutnya di dalam blok tersebut? Analisis pesan error yang dihasilkan.

5. **Frame Leaks via Exception Context (`__traceback__`) pada Suspended Generators**
   Ketika exception terjadi di dalam blok generator yang sedang disuspensi, bagaimana siklus referensi (*reference cycle*) antara `frame -> exception -> traceback -> frame` terbentuk? Mengapa siklus ini dapat menggagalkan *reference counting* standar CPython dan memaksa Cyclic Garbage Collector bekerja ekstra keras pada sistem dengan konkurensi tinggi?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden OOM pada Pipeline Ingestion Log 500GB
* **Latar Belakang:** Worker background (alokasi RAM: 2GB) memproses file log telemetri sebesar 500GB yang diunduh secara berkala. Arsitektur pipeline dirancang menggunakan generator bertingkat:
  ```python
  def read_lines(filepath):
      with open(filepath, 'r') as f:
          for line in f:
              yield line

  def parse_json(lines):
      return (json.loads(line) for line in lines)

  def extract_errors(records):
      return (r for r in records if r.get('level') == 'ERROR')

  def sort_by_timestamp(records):
      return sorted(records, key=lambda x: x['timestamp'])

  def write_to_db(records):
      for batch in chunked(records, 1000):
          db.bulk_insert(batch)
  ```
* **Gejala:** Worker selalu terbunuh oleh Linux OOM Killer (`SIGKILL`) setelah memproses sekitar 3–4% file.
* **Pertanyaan Diagnostik:**
  1. Identifikasi secara tepat di mana *bottleneck* memori terjadi dan jelaskan mengapa generator pipeline kehilangan sifat *laziness*-nya pada rantai pemrosesan tersebut.
  2. Bagaimana cara merefaktor tahapan komputasi tersebut agar pemrosesan log 500GB dapat selesai dengan alokasi RSS memori stabil di bawah 200MB?

### Skenario B: Race Condition & Silent Data Corruption pada Multi-threaded Generator Consumer
* **Latar Belakang:** Sebuah microservice ingest data menggunakan thread pool (`concurrent.futures.ThreadPoolExecutor`) untuk mempercepat pemrosesan data pipeline. Developer mengoper *single generator instance* ke beberapa worker thread:
  ```python
  raw_stream = (fetch_metric(device_id) for device_id in global_device_ids)

  def worker_task(stream):
      for metric in stream:
          persist_metric(metric)

  with ThreadPoolExecutor(max_workers=8) as executor:
      futures = [executor.submit(worker_task, raw_stream) for _ in range(8)]
  ```
* **Gejala:** Sistem kehilangan ribuan data secara acak tanpa adanya `Exception` yang dilempar. Pada runtime tertentu, muncul `ValueError: generator already executing`.
* **Pertanyaan Diagnostik:**
  1. Mengapa generator CPython secara fundamental tidak *thread-safe* meskipun Global Interpreter Lock (GIL) aktif?
  2. Jelaskan root cause dari munculnya `ValueError: generator already executing` dan bagaimana dua thread yang memanggil `next()` secara simultan dapat menyebabkan *silent data loss*.
  3. Desain pola arsitektur threading yang tepat untuk mendistribusikan data dari generator ke beberapa worker thread secara efisien tanpa kehilangan integritas data.

### Skenario C: Trade-off Arsitektur Streaming ETL: Pure Generators vs Multiprocessing vs Chunking
* **Latar Belakang:** Sebuah platform analitik finansial harus memvalidasi, menormalkan, dan menghitung matriks korelasi dari 50 juta baris transaksi per batch.
* **Dilema Arsitektur:**
  * Pendekatan 1: *Pure Lazy Single-Thread Generator Pipeline*.
  * Pendekatan 2: *Multiprocessing Pipeline* (mengirim chunk item via `multiprocessing.Queue`).
  * Pendekatan 3: *Hybrid Iterator Chunking* menggunakan vektorisasi NumPy/Pandas.
* **Pertanyaan Diagnostik:**
  1. Pada Pendekatan 2, mengapa penggunaan `multiprocessing.Queue` untuk streaming data per-record (bukan chunk) justru menyebabkan *CPU thrashing* dan penurunan performa hingga 10x lipat dibanding Pendekatan 1? (Kaitkan dengan *IPC overhead* dan serialisasi `pickle`).
  2. Bagaimana karakteristik dataset (apakah I/O-bound atau CPU-bound) menentukan batas di mana Anda harus beralih dari Pendekatan 1 ke Pendekatan 3?
  3. Susun matriks evaluasi trade-off (Throughput vs Latency vs Memory Overhead vs Kompleksitas Kode) untuk ketiga pendekatan tersebut.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Throughput Streaming Telemetry Aggregator & Dynamic Anomaly Detector

#### Problem Statement
Anda bertugas merancang modul *Core Data Engine* untuk sistem monitoring IoT. Engine harus membaca stream data log telemetri yang masif secara berkelanjutan, membersihkan format data, menghitung rata-rata bergerak (*moving average*) dan deviasi standar secara real-time, mendeteksi anomali sinyal (menggunakan ambang batas Z-score), serta mengekspos mekanisme dynamic reconfiguration (mengubah threshold Z-score tanpa me-restart pipeline).

#### Requirements
1. **Purity of Pipeline:** Seluruh pemrosesan dari pembacaan hingga kalkulasi wajib berbasis Generator Pipeline (Lazy Evaluation). Tidak boleh ada pemanggilan `list(stream)` atau membaca seluruh file/stream ke dalam memori.
2. **Dynamic Configuration via Coroutine (`.send()`):** Modul deteksi anomali harus diimplementasikan sebagai generator yang menerima penyesuaian nilai parameter `threshold_z_score` secara dinamis saat runtime menggunakan metode `.send()`.
3. **Sliding Window Statistics:** Implementasikan kalkulasi Welford's Algorithm (atau running variance O(1) memory) di dalam generator untuk menghitung *running mean* dan *running standard deviation* tanpa menyimpan seluruh riwayat data di memori.
4. **Deterministic Teardown:** Pipeline harus menangani sinyal terminasi (`GeneratorExit`) secara elegan untuk merilis file handle, menulis metadata pemrosesan terakhir, dan menjamin flushing data log terakhir.
5. **Memory Cap:** Penggunaan memori RSS tambahan tidak boleh melebihi **50MB**, terlepas dari apakah input memproses 10.000 record atau 100.000.000 record.

#### Constraints
* **Standard Library Only:** Hanya diperbolehkan menggunakan built-in Python dan modul standard library (`sys`, `itertools`, `functools`, `typing`, `math`, `time`, `tracemalloc`). Dilarang menggunakan dependensi eksternal seperti `numpy`, `pandas`, atau `scipy`.
* **Python Target:** Python 3.10+ (manfaatkan type hinting modern, pattern matching jika relevan).

#### Expected Output
1. Script Python tunggal yang mencakup:
   * Generator simulasi telemetry stream.
   * Transformer pipeline (Parsing -> Cleaning -> Metrics Calculation -> Anomaly Detection).
   * Harness test yang mendemonstrasikan:
     - Streaming minimal 100.000 record telemetri sintetis.
     - Injeksi anomali secara periodik.
     - Penyesuaian `threshold_z_score` di tengah pemrosesan via `.send()`.
     - Output log anomali yang terdeteksi secara real-time: `[ANOMALY DETECTED] Timestamp: <ts> | Value: <val> | Z-Score: <z> | Current Threshold: <th>`.
     - Pengukuran memori menggunakan `tracemalloc` yang membuktikan *peak memory* berada di bawah threshold 50MB.

---

## 5. Knowledge Check & Checklist

Gunakan checklist ini untuk mengaudit kesiapan pemahaman teknis Anda sebelum melangkah ke bab berikutnya.

### Saya harus memahami:
- [ ] Kontrak internal Iterator Protocol: interaksi formal antara `__iter__()`, `__next__()`, dan mekanisme raising `StopIteration`.
- [ ] Perilaku CPython terhadap PEP 479: bagaimana bubble-up `StopIteration` yang tidak sengaja dicegah agar tidak merusak eksekusi generator.
- [ ] Siklus hidup `PyFrameObject`: bagaimana interpreter mem-freeze dan me-resume stack frame saat menjumpai opcode `YIELD_VALUE`.
- [ ] Perbedaan esensial delegasi sub-generator: `yield from` vs iterasi manual, khususnya pada penanganan `.send()`, `.throw()`, dan `.close()`.
- [ ] Mekanisme Late Binding Closures: resolusi scoping LEGB pada CPython dan struktur `__closure__` cell object.
- [ ] Implikasi memori dari `itertools.tee()`: trade-off pemakaian antrean internal (FIFO) vs duplikasi data langsung.
- [ ] Batasan thread-safety pada CPython Generator: mengapa generator sharing antar-thread menghasilkan race condition meskipun ada GIL.

### Saya tidak perlu menghafal:
- [ ] Seluruh nomor opcode CPython yang berkaitan dengan iterasi (`GET_ITER`, `FOR_ITER`, dll.) di luar pemahaman alur eksekusinya.
- [ ] Formula matematis rumit untuk statistik lanjut di luar algoritma kalkulasi running streaming standar (seperti Welford's Algorithm).
- [ ] Implementasi source code CPython di layer C (`genobject.c`) baris demi baris, cukup memahami konseptual pointer state-nya.

### Saya harus bisa melakukan:
- [ ] Membangun multi-stage generator pipeline yang modular, composable, dan memproses dataset gigabyte dengan footprint memori konstan (O(1)).
- [ ] Melakukan refactoring fungsi rekursif atau nested loop kompleks menjadi generator berbasis `yield from` yang bersih dan efisien.
- [ ] Mengimplementasikan *bidirectional communication* pada coroutine generator menggunakan `.send()`, `.throw()`, dan `.close()`.
- [ ] Menemukan dan mengatasi *memory leak* tersembunyi yang diakibatkan oleh konsumsi generator yang tidak seimbang (*exhaustion bugs*, buffer `tee`, atau siklus exception traceback).
- [ ] Menggunakan modul `tracemalloc` untuk mengaudit dan membuktikan efisiensi alokasi memori (heap peak memory) pada kode streaming enterprise.