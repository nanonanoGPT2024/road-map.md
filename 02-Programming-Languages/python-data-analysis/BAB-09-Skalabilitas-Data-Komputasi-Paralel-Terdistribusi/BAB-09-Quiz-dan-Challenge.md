# BAB 09: Quiz, Challenge, & Knowledge Check
**Skalabilitas Data & Komputasi Paralel Terdistribusi (Dask & Ray)**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Lazy Evaluation vs. Eager Execution (Dask vs. Ray):**  
   Jelaskan secara arsitektural perbedaan paradigma eksekusi antara Dask (yang secara default mengandalkan konstruksi Directed Acyclic Graph/DAG secara *lazy* via antarmuka High-Level Collections seperti `dask.dataframe`) dan Ray (yang beroperasi secara *eager-by-default* melalui `ray.remote`). Apa implikasi dari perbedaan ini terhadap alokasi memori, latensi pemanggilan fungsi (*task submission latency*), dan strategi optimasi eksekusi?

2. **Arsitektur Scheduler Dask (Single-Machine vs. Distributed):**  
   Bandingkan mekanisme internal Dask *Single-Machine Schedulers* (khususnya perbedaan antara backend `threaded` dan `processes`) dengan `dask.distributed.Scheduler`. Mengapa pada pemrosesan data numerik murni (NumPy-based) backend multithreading sering kali sudah memadai, sedangkan transformasi teks murni Python membutuhkan scheduler terdistribusi atau multiproses untuk menghindari Python Global Interpreter Lock (GIL)?

3. **Shared Memory Architecture & Zero-Copy Deserialization pada Ray:**  
   Bagaimana Ray Object Store (berbasis Plasma) memanfaatkan memori bersama (*shared memory* via `/dev/shm`) dan format memori Apache Arrow untuk mengeliminasi *overhead* serialisasi/deserialisasi (*zero-copy deserialization*) antar proses worker pada satu node fisik yang sama? Dalam kondisi apa *zero-copy* ini runtuh dan memaksa eksekusi *copy-on-write* atau deep copy?

4. **Stateless Tasks vs. Stateful Actors dalam Ray:**  
   Bedakan siklus hidup (*lifecycle*), alokasi sumber daya (*resource pinning*), dan pola replikasi antara Ray Tasks (`@ray.remote` pada fungsi biasa) dan Ray Actors (`@ray.remote` pada class). Jelaskan trade-off performa yang muncul jika Anda memaksakan implementasi *stateful stream processing* menggunakan Ray Tasks vs. memaksakan pemrosesan *embarrassingly parallel batch* menggunakan Ray Actors.

5. **Granularitas Partisi dan Chunking:**  
   Dalam eksekusi `dask.dataframe` atau `dask.array`, bagaimana ukuran partisi (*chunk size*) memengaruhi performa kluster? Analisis skenario ekstrem di mana:
   - Partisi terlalu kecil (misal: 10 MB per chunk pada dataset 1 TB).
   - Partisi terlalu besar (misal: 50 GB per chunk pada mesin dengan RAM 64 GB).  
   Sertakan analisis dampaknya terhadap *scheduler task overhead* dan risiko *out-of-memory* (OOM).

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Dask Worker Memory Management Lifecycle:**  
   Dask Distributed mengelola memori worker menggunakan empat ambang batas berbasis fraksi RAM: `target`, `spill`, `pause`, dan `terminate` (dikelola oleh *Nanny Process*). Jelaskan mekanisme mekanistik apa yang dipicu oleh worker pada masing-masing ambang batas tersebut. Jika disk I/O lambat (misal: throttling pada network-attached storage), bagaimana fase `spill` dapat memicu *cascading failure* di seluruh worker?

2. **Serialisasi Objek, Closures, dan Pickle Poisoning:**  
   Mengapa passing objek non-serializable seperti open file handlers, socket database connections, atau complex closures yang mereferensikan modul global dapat menyebabkan `PickleError` atau `Cloudpickle` failure saat submit task ke Dask/Ray? Bagaimana cara mendeteksi variabel tersembunyi yang ditangkap (*captured variables*) oleh closure sebelum melakukan submit task ke kluster?

3. **Ray Placement Groups dan Resource Scheduling Deadlock:**  
   Jelaskan bagaimana strategi scheduling bundling (`STRICT_SPREAD`, `PACK`, `STRICT_PACK`) pada Ray Placement Groups bekerja. Bagaimana skenario dependensi task bersarang (*nested remote tasks*) di mana *parent task* membutuhkan resource CPU dan memicu pemanggilan *child tasks* yang juga meminta resource CPU dapat menimbulkan situasi *Distributed Scheduling Deadlock*? Bagaimana cara mitigasinya menggunakan `ray.yield_resources` atau arsitektur non-blocking?

4. **Backpressure & Memory Leaks akibat Akumulasi Ray Object References / Dask Futures:**  
   Jika sebuah proses driver menjalankan perulangan tak terbatas yang melakukan iterasi dan men-submit ribuan task:
   ```python
   # Pola anti-pattern
   futures = [compute.remote(x) for x in infinite_stream]
   ```
   Bagaimana Garbage Collector driver dan Object Store terdistribusi bereaksi terhadap penumpukan `Ray ObjectRef` atau `dask.distributed.Future` tersebut? Jelaskan implementasi mekanisme *backpressure* eksplisit untuk menjaga jumlah *in-flight tasks* tetap konstan tanpa membebani scheduler.

5. **Shuffle Architecture: Task-based vs. P2P (Peer-to-Peer):**  
   Operasi relasional seperti `DataFrame.merge()` atau `DataFrame.set_index()` membutuhkan fase *shuffling*. Mengapa pendekatan *task-based shuffle* historis pada Dask (yang membagi data menjadi $N \times M$ partisi perantara) menyebabkan *bottleneck* I/O dan kelebihan beban metadata pada scheduler? Bagaimana arsitektur *P2P Shuffle* modern (berbasis streaming TCP sockets antar worker) memitigasi masalah skala ini?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Worker OOM & Cascading Death pada Pipeline ETL Skala Terabyte
Sebuah pipeline Dask terdistribusi memproses 800 GB log klik e-commerce harian menggunakan kluster dengan 4 node worker (masing-masing 32 GB RAM, 8 vCPU). Pipeline menjalankan operasi pembersihan, diikuti oleh agregasi berat:
```python
df = dd.read_parquet("s3://bucket/clickstream/*.parquet")
cleaned = df.dropna(subset=["user_id"]).astype({"user_id": "int64"})
result = (
    cleaned.groupby("user_id")
    .agg({"price": "sum", "click_count": "count"})
    .compute()
)
```
**Insiden:** Pada saat eksekusi mencapai 65%, satu per satu worker mati dengan status *WorkerKilled (Memory limit exceeded)*. Scheduler mencoba me-reschedule task dari worker yang mati ke worker yang masih hidup, yang secara beruntun menyebabkan worker yang tersisa mengalami crash secara cascading hingga seluruh kluster *down*.

*Pertanyaan Diagnostik & Solusi:*
1. Mengapa pemanggilan `.compute()` secara langsung pada operasi agregasi tersebut sangat fatal terhadap kestabilan memori Driver dan Worker?
2. Bagaimana mekanisme rescheduling bawaan Dask justru memperburuk fenomena *cascading failure* ini?
3. Rancang ulang strategi eksekusi kode di atas (termasuk konfigurasi persistensi, pemilihan engine shuffle, pengelolaan partisi output, dan eksekusi penyimpanan out-of-core) agar pipeline dapat berjalan dengan aman tanpa melampaui ambang batas RAM kluster.

---

### Skenario B: Race Condition dan State Drift pada Stateful Ray Actor Cluster
Sebuah sistem deteksi fraud real-time menggunakan pool Ray Actors untuk mempertahankan state rolling window perilaku pengguna selama 1 jam terakhir:
```python
@ray.remote
class UserProfileTracker:

    def __init__(self):
        self.profiles = {}  # user_id -> dict metrics

    def update_and_check(self, user_id, transaction_data):
        # Update metrics lokal
        profile = self.profiles.setdefault(
            user_id, {"velocity": 0, "last_ts": 0}
        )
        profile["velocity"] += transaction_data["amount"]
        # Logika validasi fraud
        return profile["velocity"] > 10000
```
Untuk meningkatkan throughput, tim mereplikasi actor ini menjadi 10 instance (`tracker_pool`) dan mendistribusikan request dari Kafka consumer menggunakan pola round-robin atau task submission paralel secara acak via driver.

**Insiden:** Sistem mulai membiarkan transaksi mencurigakan lolos dan memicu alert false-negative yang masif. Data audit menunjukkan bahwa penghitungan metrik rolling window tidak konsisten dan tidak akurat.

*Pertanyaan Diagnostik & Solusi:*
1. Identifikasi secara tepat akar masalah arsitektural dari implementasi pool stateful actor ini. Mengapa pendistribusian beban via *stateless load-balancing* merusak integritas state pada distributed actor?
2. Jika dua event untuk `user_id` yang sama masuk ke actor yang sama secara asinkron (misal: method diubah menjadi `async def`), race condition internal apa yang masih berpotensi terjadi pada pemutakhiran dictionary Python in-memory?
3. Rancang arsitektur baru yang memanfaatkan teknik *consistent hashing* / *key-based routing* dan mekanisme concurrency bawaan Ray (seperti `max_concurrency` pada asyncio actor atau actor threading) untuk menjamin strictly-partitioned state processing tanpa mengorbankan skalabilitas throughput horizontal.

---

### Skenario C: Trade-off Arsitektur Migrasi Batch ML: Dask vs. Ray vs. Spark
Perusahaan FinTech memproses 10 TB data terstruktur bulanan untuk melatih puluhan model Gradient Boosted Trees (XGBoost/LightGBM) dan deep learning embeddings (PyTorch). Arsitektur saat ini menggunakan Apache Spark on EMR untuk keseluruhan pipeline (ETL + MLlib). Tim mengeluhkan tingginya biaya komputasi, tingginya latensi interop saat mengirim dataframe Spark ke PyTorch (overhead konversi Java/JVM ke Python C-extensions), serta keterbatasan ekosistem ML Python modern di lingkungan JVM.

Direktur Teknik mengusulkan dua opsi modernisasi stack:
- **Opsi 1:** Full Dask Stack (Dask DataFrame + Dask-ML + Dask-XGBoost).
- **Opsi 2:** Hybrid Ray Stack (Ray Core + Ray Data + Ray Train + vLLM/XGBoost on Ray).

*Pertanyaan Diagnostik & Evaluasi:*
1. Bandingkan efisiensi internal kedua opsi tersebut dalam mentransfer data berukuran ratusan gigabyte dari tahap preprocessing data tabular langsung ke tensor GPU/PyTorch tanpa overhead serialisasi. Mengapa integrasi Ray Train + Arrow Plasma Store secara fundamental lebih unggul daripada Dask dalam konteks deep learning?
2. Di sisi lain, dalam hal fungsionalitas murni manipulasi data tabular (SQL-like data transformations, indexing, API alignment dengan standard Pandas), keunggulan spesifik apa yang masih dipertahankan oleh ekosistem Dask DataFrame dibanding Ray Data?
3. Berikan rekomendasi arsitektural komprehensif: Bagaimana jika kedua engine dikombinasikan, atau pada kondisi boundary data apa Opsi 1 dipilih versus Opsi 2? Susun matriks keputusannya mencakup: throughput data, kompleksitas operasional kluster, debugging capability, dan integrasi dengan hardware akselerator (GPU).

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Throughput Out-of-Core Feature Engineering & Distributed Serving Engine

#### Problem:
Anda diminta membangun pipeline *hybrid feature pipeline* terdistribusi yang memproses dataset clickstream tabular berskala besar yang tidak muat di memori lokal, melakukan agregasi agregat out-of-core, dan menyalurkan fitur tersebut secara *zero-copy* ke sekelompok Ray Actors untuk scoring inferensi model machine learning berkecepatan tinggi dengan proteksi backpressure penuh.

#### Requirements:
1. **Dask Processing Phase:**
   - Hasilkan synthetic dataset clickstream menggunakan `dask.datasets.timeseries()` atau sintesis Parquet partisi (minimal 10.000.000 records, simulasi ukuran melebihi kapasitas RAM kerja yang dialokasikan).
   - Lakukan agregasi out-of-core kompleks: hitung *cumulative spending* dan *session frequency* per user ID menggunakan optimasi partisi dan P2P shuffle.
   - Konversi partisi hasil olahan Dask secara streaming/partisi-demi-partisi ke dalam format Apache Arrow Tables atau batched PyArrow Records tanpa memanggil `.compute()` yang menarik seluruh data ke driver.
2. **Ray Serving & Ingestion Phase:**
   - Buat sebuah pool Ray Actors bernama `InferenceWorker` (minimal 4 instance actor). Masing-masing actor memuat bobot model dummy (vektor floating point besar di memori).
   - Implementasikan *custom stream orchestrator* di Ray: Konsumsi data terproses dari Dask, kirimkan partisi via Ray Shared Memory (`ray.put`), dan distribusikan task inferensi ke Actor pool menggunakan strategi batched round-robin atau work-stealing queue.
3. **Robustness & Backpressure Control:**
   - Terapkan mekanisme pembatasan kapasitas buffer antrean (*bounded queue*). Maksimal hanya boleh ada 8 task inferensi yang berstatus *in-flight* secara bersamaan untuk mencegah kehabisan memori driver/cluster.
   - Terapkan penanganan error: Apabila salah satu worker di-kill secara paksa (simulasikan kegagalan via `ray.kill()`), sistem harus secara otomatis mendeteksi, me-restart actor, dan me-reschedule batch inference yang gagal tanpa menghentikan seluruh pipeline.

#### Constraints:
- Alokasi memori maksimal untuk scheduler + workers Dask dan Ray dibatasi secara ketat (simulasikan lingkungan terbatas: gunakan memory limit 4 GB untuk Dask worker pool dan 4 GB untuk Ray Object Store).
- Dilarang keras menggunakan pandas dataframe `.to_dict()` atau looping baris-per-baris berbasis Python native standard primitives (wajib ter-vektorisasi penuh via Arrow / NumPy zero-copy interfaces).
- Driver process RAM usage harus flat (konstan) di bawah 500 MB sepanjang keseluruhan siklus eksekusi pipeline berlangsung.

#### Expected Output:
1. File skrip Python produksi tunggal yang self-contained (`hybrid_distributed_engine.py`) yang mengorkestrasi Dask dan Ray secara bersamaan dalam satu lifecycle proses run yang bersih.
2. Log konsol sistem terstruktur yang mendemonstrasikan:
   - Tahapan transisi Dask DAG execution tanpa memory spill alerts.
   - Distribusi payload partisi Arrow ke Ray Shared Memory.
   - Ray actor metrics: throughput transaksi per detik (TPS), latensi inferensi rata-rata per batch.
   - Bukti eksekusi pemulihan worker (*fault-recovery proof*) saat salah satu actor dimatikan di tengah jalan.
3. Metrik ringkasan eksekusi: Total execution time, peak memory usage pada driver, rasio data processed to peak memory footprint.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Arsitektur internal Directed Acyclic Graph (DAG) pada Dask dan bagaimana scheduler mengoptimalkan pemotongan cabang task (*graph culling*).
- [ ] Perbedaan fundamental antara Ray Object Store (Plasma) in-memory storage dengan model message-passing IPC konvensional.
- [ ] Cara kerja Ray Distributed Task Scheduler (Bottom-up scheduling architecture: Local Scheduler/Raylet vs. Global Scheduler).
- [ ] Batasan Python GIL terhadap komputasi paralel dan strategi bypassing menggunakan Dask/Ray native memory data structures.
- [ ] Mekanisme Dynamic Task Graphs pada Dask/Ray di mana task baru dapat di-spawn dari dalam task yang sedang berjalan (*nested execution*).
- [ ] Life cycle pengelolaan memori worker (Target, Spill, Pause, Kill) pada sistem terdistribusi modern.
- [ ] Konsep Zero-Copy read menggunakan Apache Arrow via shared memory segments (`/dev/shm`).

### Saya tidak perlu menghafal:
- [ ] Semua konfigurasi internal flag pada `dask.config` (cukup pahami cara membaca dan menimpa opsi kunci seperti `distributed.worker.memory.target`).
- [ ] Parameter low-level internal Cython/C++ Plasma Object Store allocator (cukup pahami batas ambang ukuran objek dan shared memory limits).
- [ ] Seluruh variasi API method dari `dask.dataframe` (cukup pahami paritas fungsinya dengan API Pandas dan trade-off komputasi out-of-core).
- [ ] Kode implementasi internal cloudpickle (cukup pahami batasan serialisasi state dan dependency wrapping).

### Saya harus bisa melakukan:
- [ ] Melakukan profiling dan debugging bottleneck pipeline Dask secara langsung menggunakan Dask Diagnostic Dashboard (Task Stream, Progress Bar, Memory Profiler).
- [ ] Menulis pipeline transformasi data *out-of-core* pada Dask DataFrame tanpa menyebabkan driver memory exhaustion atau memory spill thrashing.
- [ ] Membangun, mengalokasikan, dan mengelola lifecycle Ray Actors dan Ray Tasks dengan isolasi CPU/GPU resource constraints yang eksplisit.
- [ ] Mencegah dan memitigasi distributed deadlock pada pemanggilan nested Ray Tasks dan Placement Groups.
- [ ] Mengimplementasikan pola kontrol aliran *backpressure* pada Ray Object Store untuk memproses continuous/batch data streaming tanpa lonjakan OOM.
- [ ] Mengombinasikan pipeline interoperabilitas high-performance data: membaca data via Dask, parsing via Apache Arrow, dan komputasi/inferensi model via Ray Actors secara seamless.