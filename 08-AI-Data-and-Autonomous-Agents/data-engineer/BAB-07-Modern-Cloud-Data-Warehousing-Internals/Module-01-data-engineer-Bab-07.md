# Modern Cloud Data Warehousing Internals

## Module 01: Decoupled Compute-Storage & Vectorized Execution Engine

---

### 1. Learning Objectives (Spesifik & Terukur)

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis dan menguraikan** arsitektur internal *modern cloud data warehouse* (seperti Snowflake, BigQuery, dan Databricks Photon) yang memisahkan lapisan *compute*, *centralized metadata*, dan *immutable remote storage*.
- **Mengimplementasikan** mekanisme *partition pruning* berbasis metadata (*zone maps*, min/max statistics) dan evaluasi predikat terdistribusi untuk mereduksi *data scanning overhead* minimal 80% pada skala terabyte.
- **Merekonstruksi** prinsip *vectorized execution engine* (SIMD-aligned batch processing) untuk mengatasi *instruction cache thrashing* dan *virtual function call overhead* yang terjadi pada *traditional Volcano iterator model*.
- **Mendiagnosis** anomali performa seperti *partition skew*, *metadata bloat*, dan *memory spill* (baik *local NVMe spill* maupun *remote storage spill*) menggunakan metrik *execution profiler*.
- **Merancang** strategi kompresi kolumnar (*Run-Length Encoding*, *Dictionary Encoding*, *Bit-Packing*) yang dioptimalkan untuk akses paralel SIMD.

---

### 2. Concept Overview (Mental Model & Teori Inti)

Secara historis, sistem analitik mengadopsi arsitektur **Shared-Nothing MPP (Massively Parallel Processing)** (seperti Teradata, Netezza, Greenplum). Pada sistem ini, setiap *node* memiliki CPU, memori, dan *disk* lokal secara terikat. Kelemahan fatal arsitektur ini muncul di era *cloud elasticity*: penambahan kapasitas penyimpanan (*storage scaling*) memaksa penambahan kapasitas komputasi (*compute scaling*), memicu proses *data reshuffling/rebalancing* jaringan yang sangat mahal secara komputasional (*IO-bound cluster re-indexing*).

*Modern Cloud Data Warehouses* merevolusi paradigma ini dengan menerapkan **Decoupled Storage and Compute Architecture**.

```
+---------------------------------------------------------------------------------+
|                                 MENTAL MODEL                                    |
|                                                                                 |
|   TRADITIONAL MPP (Tightly Coupled)            MODERN CLOUD DW (Decoupled)      |
|   +-------------------------------+          +-------------------------------+  |
|   | Node 1: CPU + RAM + Storage   |          | Stateless Compute Cluster     |  |
|   +-------------------------------+          | (VMs with local NVMe Cache)   |  |
|                  ^                           +-------------------------------+  |
|            Interconnect (Reshuffle pain)                     |                  |
|                  v                           +-------------------------------+  |
|   +-------------------------------+          | Global Metadata / Catalog Svc |  |
|   | Node 2: CPU + RAM + Storage   |          +-------------------------------+  |
|   +-------------------------------+                          |                  |
|                                              +-------------------------------+  |
|                                              | Remote Immutable Object Store |  |
|                                              | (S3, GCS, Azure Blob)         |  |
|                                              +-------------------------------+  |
+---------------------------------------------------------------------------------+
```

Kunci operasional sistem ini terletak pada tiga fondasi teori:

1. **Immutable Micro-Partitioning**: Tabel tidak disimpan sebagai file monolitik atau partisi folder berbasis direktori kaku, melainkan dipecah menjadi ribuan partisi independen (*micro-partitions*, berukuran 50 MB hingga 500 MB dalam format kolumnar terkompresi). Setiap *micro-partition* bersifat *immutable* (tulis-sekali), memungkinkan *concurrency control* berbasis **MVCC (Multi-Version Concurrency Control)** murni tanpa penguncian tabel tingkat rendah (*low-level locking*).
2. **Metadata-Driven Pruning**: Karena partisi bersifat *immutable*, *metadata service* mencatat statistik ringkas (*column min/max values*, *null counts*, *distinct values count*) pada setiap micro-partition. *Query engine* mengevaluasi klausul `WHERE` langsung terhadap metadata, membuang (*pruning*) 90-99% file tanpa melakukan I/O fisik ke *remote storage*.
3. **Vectorized Execution**: Arsitektur mesin pengolahan klasik mengeksekusi model *Volcano Iterator* (`next()` mengembalikan satu *tuple* per panggilan), yang memicu lonjakan *CPU instruction cache miss* dan overhead *virtual dispatch*. *Modern Cloud DW* menggunakan mesin tervektorisasi (*vector-at-a-time*): operasi dieksekusi per blok data homogen (misalnya 1024 elemen) yang disimpan secara contiguous di memori, memaksimalkan penggunaan instruksi CPU modern seperti **SIMD (Single Instruction, Multiple Data)**.

---

### 3. Why It Matters (Masalah di Dunia Nyata & Kebutuhan Enterprise)

Di lingkungan *enterprise* dengan beban analitik petabyte:
- **Fluktuasi Beban Kerja & Concurrency**: Beban kerja analitik bersifat *bursty*. Tim *data science* menjalankan query agregasi berat di awal kuartal, sementara sistem BI memerlukan SLA sub-detik untuk ribuan pengguna konkuren. Dengan *decoupled architecture*, komputasi untuk BI dapat diisolasi total (*Virtual Warehouse A*) dari komputasi transformasi ETL/ELT (*Virtual Warehouse B*) tanpa terjadi *resource contention*, meskipun keduanya mengakses data yang identik secara simultan.
- **Biaya Akses Jaringan vs. Latensi I/O**: Membaca data langsung dari *remote object store* (misal: AWS S3) memiliki latensi dasar 50-100 ms per *request*. Tanpa *micro-partition pruning* dan *caching tiered NVMe*, kueri analitik akan bangkrut secara ekonomi dan performa akibat *network throughput bottleneck* dan biaya *API egress/GET calls*.
- **Instruction-Level Efficiency**: Pemrosesan baris-per-baris tradisional pada CPU 64-bit modern menyia-nyiakan 80-90% siklus instruksi karena *branch misprediction* saat mengevaluasi tipe data dinamis. Vectorized engine menjamin *instruction cache* CPU tetap jenuh (*high IPC - Instructions Per Cycle*), memotong waktu eksekusi kueri dari skala menit ke detik.

---

### 4. Arsitektur & Diagram Komponen

Berikut adalah arsitektur internal *Modern Cloud Data Warehouse* yang memperlihatkan alur metadata, eksekusi tervektorisasi, dan hierarki penyimpanan bertingkat:

```
+--------------------------------------------------------------------------------------+
|                           CLOUD SERVICES LAYER (Global Control Plane)                |
|                                                                                      |
|  +------------------------+   +-----------------------+   +----------------------+   |
|  | Access Control & Auth  |   | Cost-Based Optimizer  |   | Transaction Manager  |   |
|  | (RBAC, Session Mgr)    |   | (CBO, Pushdown Rules) |   | (ACID, MVCC, Timetravel) |
|  +------------------------+   +-----------------------+   +----------------------+   |
|                                           |                                          |
|                               +-----------------------+                              |
|                               | Global Metadata Store |                              |
|                               | (Zone Maps, Catalogs) |                              |
|                               +-----------------------+                              |
+-------------------------------------------|------------------------------------------+
                                            | Query Plan & Partition Manifest
                                            v
+--------------------------------------------------------------------------------------+
|                     VIRTUAL COMPUTE CLUSTER (Stateless Worker Nodes)                 |
|                                                                                      |
|  +--------------------------------------------------------------------------------+  |
|  | Worker Node Instance                                                           |  |
|  |                                                                                |  |
|  |  +--------------------+     +-----------------------------------------------+  |  |
|  |  | Vectorized Engine  | <-> | Local Tiered Cache (Local NVMe SSD / DRAM)    |  |  |
|  |  | - Batch Buffers    |     | - Decoded micro-partitions                    |  |  |
|  |  | - SIMD Operators   |     | - Eviction Policy: LRU / Cache Leasing        |  |  |
|  |  | - Predicate Vector |     +-----------------------------------------------+  |  |
|  |  +--------------------+                                                        |  |
|  |            ^                                                                   |  |
|  |            | Memory Spill (When working set > RAM)                             |  |
|  |            v                                                                   |  |
|  |  +--------------------+                                                        |  |
|  |  | Local Spill (NVMe) |                                                        |  |
|  |  +--------------------+                                                        |  |
|  +--------------------------------------------------------------------------------+  |
+-------------------------------------------|------------------------------------------+
                                            | Spill to Remote (Emergency Out-of-Disk)
                                            | Cache Miss Read
                                            v
+--------------------------------------------------------------------------------------+
|                        REMOTE STORAGE LAYER (Cloud Object Storage)                   |
|                                                                                      |
|   +-------------------+    +-------------------+    +-------------------+            |
|   | Micro-Partition 1 |    | Micro-Partition 2 |    | Micro-Partition N |   ...      |
|   | [Col A | Col B]   |    | [Col A | Col B]   |    | [Col A | Col B]   |            |
|   | Format: Parquet   |    | Format: Proprietary|   | Encrypted (AES256)|            |
|   +-------------------+    +-------------------+    +-------------------+            |
+--------------------------------------------------------------------------------------+
```

#### Diagram Vectorized Execution Pipeline (Aliran Komputasi SIMD):

```
Tuple-at-a-time (Volcano):
Row 1 -> [Filter] -> [Project] -> [Aggregate] -> (Ulangi N kali: Tinggi Virtual Dispatch Overhead)

Vectorized Execution (Batch of 1024):
Col A Array [1024 Ints] 
       |
       v (SIMD Vector Comparison: AVX-512)
Bitmask Vector [1024 Bits] (1 = Match, 0 = Reject)
       |
       v (Vector Selection Vector Masking)
Filtered Col B Array [K Elements] -> Passed contiguous to next operator in L1 Cache
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Micro-Partitioning & Metadata-Driven Zone Maps
Setiap tabel secara otomatis dipotong menjadi partisi-partisi berukuran seimbang. Data di dalamnya disusun dalam format kolumnar. Bersamaan dengan kompresi data, *storage engine* mengekstrak statistik deterministik:

$$\text{ZoneMap}(P_i, C_j) = \{ \min(C_j), \max(C_j), N_{\text{nulls}}, N_{\text{distinct}} \}$$

Ketika kueri mengeksekusi predikat seleksi:
$$\sigma_{C_j \ge V_{\text{target}}}(T)$$

*Query Optimizer* melakukan *evaluasi interval Boolean* sebelum membuka koneksi I/O:
$$\text{Skip Partition } P_i \iff \max(C_j) < V_{\text{target}}$$

Jika kondisi tersebut terpenuhi, $P_i$ sepenuhnya dieliminasi dari *query execution graph*.

#### B. Columnar Storage Encoding Protocols
Data tidak disimpan sebagai *raw bytes*, melainkan dikompresi menggunakan skema yang mempertahankan kapabilitas pencarian (*searchable compressed state*):
1. **Dictionary Encoding**: Mengganti string berukuran besar dengan integer berukuran kecil ($k$-bit IDs). Operasi filter `WHERE country = 'INDONESIA'` diubah menjadi evaluasi integer `WHERE country_id = 4`.
2. **Run-Length Encoding (RLE)**: Menyimpan urutan berulang sebagai pasangan `(value, run_count)`. Sangat efisien untuk data yang sudah terurut (*clustered*).
3. **Bit-Packing / Frame of Reference (FoR)**: Menyimpan selisih (*delta*) dari nilai minimum referensi menggunakan jumlah bit minimal teoritis, mengoptimasi penggunaan register SIMD.

#### C. Vectorized SIMD Batch Execution
Pada model Volcano standar:
```cpp
// Pseudocode Volcano: dynamic dispatch overhead per baris
Value* VolcanoFilter::next() {
    while (true) {
        Tuple* t = child->next(); // Panggilan virtual method (vtable lookup)
        if (!t) return nullptr;
        if (eval_predicate(t)) return t; // Branch misprediction risk
    }
}
```

Pada *Vectorized Execution*:
Data dikemas ke dalam *contiguous in-memory arrays* (*Column Vectors*). Filter dieksekusi melalui operasi *loop unrolling* yang dapat diverifikasi secara otomatis oleh kompilator CPU menjadi instruksi SIMD:
```cpp
// Pseudocode Vectorized: SIMD pipelining friendly
void VectorizedFilter::next_vector(VectorBatch& batch) {
    child->next_vector(batch);
    int* data = batch.get_column(0).raw_int_array();
    uint8_t* selection_vector = batch.selection_vector();
    int size = batch.size(); // cth. 1024 elemen

    // Loop ini ditransformasikan menjadi instruksi SIMD (cth. _mm512_cmpgt_epi32_mask)
    #pragma clang loop vectorize(enable)
    for (int i = 0; i < size; ++i) {
        selection_vector[i] = (data[i] > target_val) ? 1 : 0;
    }
}
```
Hasil evaluasi disimpan sebagai *Selection Vector* (atau *bitmask*), dan operator berikutnya hanya memproses elemen di mana bit bernilai 1 tanpa merombak struktur memori asli.

#### D. Hierarki Cache (Result Cache vs. Local NVMe SSD Cache)
1. **Layer 1: Query Result Cache (Cloud Services)**: Menyimpan *final result set*. Kueri yang persis sama dalam rentang waktu tertentu (dan underlying table belum berubah) akan langsung mengembalikan data ini tanpa menyalakan *compute cluster* (0 compute cost).
2. **Layer 2: Local NVMe SSD / DRAM Cache (Compute Layer)**: Ketika kueri membaca *micro-partition* dari remote storage, partisi tersebut didekompresi/disimpan di SSD NVMe lokal worker. Akses berikutnya oleh kueri berbeda yang menggunakan partisi yang sama dilayani dengan latensi bus NVMe lokal (ratusan $\mu\text{s}$), bukan latensi jaringan S3 (puluhan $\text{ms}$).
3. **Layer 3: Remote Immutable Storage**: Sumber kebenaran (*single source of truth*), menyediakan skalabilitas volume tak terbatas dan durabilitas hingga $99.999999999\%$.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi Python 3.11+ yang memodelkan komponen internal *vectorized execution engine*, *columnar storage format*, dan *metadata-driven partition pruning* dengan standar clean architecture dan pengetikan statis ketat.

```python
"""
Module: core_cloud_dw_engine.py
Deskripsi: Simulasi Vectorized Query Engine dengan Micro-Partition Pruning
           menggunakan arsitektur pemrosesan berbasis kolumnar dan SIMD-aligned array.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, Tuple, Sequence
import numpy as np
import numpy.typing as npt
import uuid
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("DWInternals")


# --- DATA STORAGE LAYER PRIMITIVES ---

@dataclass(frozen=True)
class ColumnStats:
    """Menyimpan statistik mikro per-kolom untuk zone maps."""
    min_value: Any
    max_value: Any
    null_count: int
    row_count: int


@dataclass
class MicroPartition:
    """
    Representasi immutable storage file yang terfragmentasi.
    Data disimpan secara terpisah antar-kolom (Columnar Storage).
    """
    partition_id: str
    column_stats: Dict[str, ColumnStats]
    columns_data: Dict[str, npt.NDArray[Any]]
    row_count: int

    @staticmethod
    def create(data: Dict[str, Sequence[Any]]) -> MicroPartition:
        """Membuat micro-partition baru dan mengekstraksi zone maps secara deterministik."""
        part_id = str(uuid.uuid4())
        col_stats: Dict[str, ColumnStats] = {}
        processed_data: Dict[str, npt.NDArray[Any]] = {}

        total_rows = len(next(iter(data.values()))) if data else 0

        for col_name, raw_values in data.items():
            if len(raw_values) != total_rows:
                raise ValueError(f"Inkonsistensi panjang kolom pada {col_name}")

            # Konversi ke NumPy array untuk eksekusi tervektorisasi
            arr: npt.NDArray[Any] = np.array(raw_values)
            processed_data[col_name] = arr

            # Kalkulasi Zone Map Metadata
            non_null_mask = ~np.isnan(arr) if np.issubdtype(arr.dtype, np.number) else (arr != None)
            valid_elements = arr[non_null_mask]

            if len(valid_elements) > 0:
                c_min = np.min(valid_elements)
                c_max = np.max(valid_elements)
            else:
                c_min, c_max = None, None

            null_cnt = total_rows - len(valid_elements)
            col_stats[col_name] = ColumnStats(
                min_value=c_min,
                max_value=c_max,
                null_count=null_cnt,
                row_count=total_rows
            )

        return MicroPartition(
            partition_id=part_id,
            column_stats=col_stats,
            columns_data=processed_data,
            row_count=total_rows
        )


# --- EXECUTION ENGINE ABSTRACTIONS ---

@dataclass
class VectorBatch:
    """Membungkus potongan data in-memory array kontinu berukuran tetap (vektor)."""
    columns: Dict[str, npt.NDArray[Any]]
    selection_mask: npt.NDArray[np.bool_]
    batch_size: int

    @property
    def active_row_count(self) -> int:
        return int(np.sum(self.selection_mask))


class Operator(Protocol):
    """Protokol dasar bagi operator mesin eksekusi kueri tervektorisasi."""
    def open(self) -> None:
        ...

    def next(self) -> Optional[VectorBatch]:
        ...

    def close(self) -> None:
        ...


# --- VECTORIZED OPERATORS IMPLEMENTATION ---

class VectorizedTableScan(Operator):
    """
    Operator pembaca data yang mengimplementasikan Metadata-Driven Pruning.
    Partisi yang gagal lolos evaluasi predikat didorong keluar tanpa I/O array.
    """
    def __init__(
        self,
        partitions: List[MicroPartition],
        columns: List[str],
        predicates: Dict[str, Tuple[str, Any]],  # format: {"col": (">=", val)}
        vector_chunk_size: int = 1024
    ) -> None:
        self.partitions = partitions
        self.target_columns = columns
        self.predicates = predicates
        self.vector_chunk_size = vector_chunk_size
        self.eligible_partitions: List[MicroPartition] = []
        self._current_part_idx = 0
        self._current_offset = 0

    def open(self) -> None:
        """Evaluasi metadata zone maps untuk menyeleksi partisi yang valid."""
        logger.info(f"Memulai Predicate Pushdown pada {len(self.partitions)} micro-partitions...")
        pruned_count = 0

        for part in self.partitions:
            if self._should_keep_partition(part):
                self.eligible_partitions.append(part)
            else:
                pruned_count += 1

        logger.info(
            f"Pruning Selesai. Total: {len(self.partitions)}, "
            f"Dibuang: {pruned_count}, Diproses: {len(self.eligible_partitions)}"
        )
        self._current_part_idx = 0
        self._current_offset = 0

    def _should_keep_partition(self, partition: MicroPartition) -> bool:
        """Memvalidasi interval zone map terhadap predikat."""
        for col_name, (op, val) in self.predicates.items():
            if col_name not in partition.column_stats:
                continue

            stats = partition.column_stats[col_name]
            if stats.min_value is None or stats.max_value is None:
                continue

            # Logika Min/Max Pruning
            if op == ">" and not (stats.max_value > val):
                return False
            elif op == ">=" and not (stats.max_value >= val):
                return False
            elif op == "<" and not (stats.min_value < val):
                return False
            elif op == "<=" and not (stats.min_value <= val):
                return False
            elif op == "==" and not (stats.min_value <= val <= stats.max_value):
                return False

        return True

    def next(self) -> Optional[VectorBatch]:
        """Menghasilkan batch berukuran tetap secara tervektorisasi."""
        if self._current_part_idx >= len(self.eligible_partitions):
            return None

        current_part = self.eligible_partitions[self._current_part_idx]
        total_rows = current_part.row_count

        if self._current_offset >= total_rows:
            self._current_part_idx += 1
            self._current_offset = 0
            return self.next()

        end_offset = min(self._current_offset + self.vector_chunk_size, total_rows)
        slice_len = end_offset - self._current_offset

        batch_cols: Dict[str, npt.NDArray[Any]] = {}
        for col in self.target_columns:
            # Slicing contiguous array memori tanpa deep copying
            batch_cols[col] = current_part.columns_data[col][self._current_offset:end_offset]

        self._current_offset = end_offset
        mask = np.ones(slice_len, dtype=np.bool_)

        return VectorBatch(columns=batch_cols, selection_mask=mask, batch_size=slice_len)

    def close(self) -> None:
        self.eligible_partitions.clear()


class VectorizedFilter(Operator):
    """
    Operator evaluasi predikat SIMD.
    Memanipulasi bitmask tanpa merealokasi array data fisik.
    """
    def __init__(
        self,
        child: Operator,
        target_col: str,
        operation: str,
        threshold: Any
    ) -> None:
        self.child = child
        self.target_col = target_col
        self.operation = operation
        self.threshold = threshold

    def open(self) -> None:
        self.child.open()

    def next(self) -> Optional[VectorBatch]:
        while True:
            batch = self.child.next()
            if batch is None:
                return None

            col_data = batch.columns[self.target_col]
            
            # Operasi SIMD/Array tervektorisasi via NumPy C-kernel
            if self.operation == ">":
                condition_mask = col_data > self.threshold
            elif self.operation == ">=":
                condition_mask = col_data >= self.threshold
            elif self.operation == "<":
                condition_mask = col_data < self.threshold
            elif self.operation == "==":
                condition_mask = col_data == self.threshold
            else:
                raise NotImplementedError(f"Operator {self.operation} tidak didukung")

            # Bitwise AND untuk memutakhirkan selection vector
            batch.selection_mask = np.logical_and(batch.selection_mask, condition_mask)

            # Jika seluruh batch tersaring, lanjut ke batch berikutnya
            if batch.active_row_count > 0:
                return batch

    def close(self) -> None:
        self.child.close()


class VectorizedAggregate(Operator):
    """
    Operator agregasi (misal SUM, COUNT) dengan pemanfaatan selection mask.
    """
    def __init__(self, child: Operator, agg_col: str, agg_func: str = "SUM") -> None:
        self.child = child
        self.agg_col = agg_col
        self.agg_func = agg_func.upper()
        self._executed = False

    def open(self) -> None:
        self.child.open()
        self._executed = False

    def next(self) -> Optional[VectorBatch]:
        if self._executed:
            return None

        total_sum = 0.0
        total_count = 0

        while True:
            batch = self.child.next()
            if batch is None:
                break

            active_elements = batch.columns[self.agg_col][batch.selection_mask]
            if len(active_elements) > 0:
                total_sum += float(np.sum(active_elements))
                total_count += len(active_elements)

        self._executed = True

        result_val = total_sum if self.agg_func == "SUM" else float(total_count)
        return VectorBatch(
            columns={f"{self.agg_func}({self.agg_col})": np.array([result_val])},
            selection_mask=np.array([True]),
            batch_size=1
        )

    def close(self) -> None:
        self.child.close()


# --- ORCHESTRATION & VALIDATION PIPELINE ---

def run_production_pipeline_simulation() -> None:
    logger.info("Menginisialisasi dataset sintetis dan micro-partitions...")
    np.random.seed(42)

    # 1. Menghasilkan dataset acak yang tersebar di 5 micro-partitions
    partitions: List[MicroPartition] = []
    num_partitions = 5
    rows_per_partition = 100_000

    for i in range(num_partitions):
        # Buat data dengan domain id yang teratur untuk mendemonstrasikan pruning
        account_ids = np.random.randint(i * 1000, (i + 1) * 1000, size=rows_per_partition)
        transaction_amounts = np.random.uniform(10.0, 5000.0, size=rows_per_partition)
        
        part = MicroPartition.create({
            "account_id": account_ids,
            "amount": transaction_amounts
        })
        partitions.append(part)

    # Menampilkan informasi Zone Map dari partisi
    for idx, p in enumerate(partitions):
        stats = p.column_stats["account_id"]
        logger.debug(f"P{idx}: Min={stats.min_value}, Max={stats.max_value}")

    # 2. Definisikan Kueri: 
    # SELECT SUM(amount) FROM table WHERE account_id >= 3500 AND amount > 2500.0
    logger.info("Mengeksekusi Kueri: Predikat [account_id >= 3500, amount > 2500.0]")

    # Pipeline perakitan plan (Query Plan Construction)
    scan_op = VectorizedTableScan(
        partitions=partitions,
        columns=["account_id", "amount"],
        predicates={"account_id": (">=", 3500)}, # Metadata pruning level
        vector_chunk_size=4096
    )

    filter_op = VectorizedFilter(
        child=scan_op,
        target_col="amount",
        operation=">",
        threshold=2500.0 # Vector SIMD evaluation level
    )

    agg_op = VectorizedAggregate(
        child=filter_op,
        agg_col="amount",
        agg_func="SUM"
    )

    # 3. Jalankan Eksekusi
    agg_op.open()
    result = agg_op.next()
    agg_op.close()

    if result:
        col_name = list(result.columns.keys())[0]
        val = result.columns[col_name][0]
        logger.info(f"Hasil Eksekusi Akhir: {col_name} = {val:,.2f}")
    else:
        logger.error("Kueri tidak menghasilkan batch.")


if __name__ == "__main__":
    run_production_pipeline_simulation()
```

---

### 7. Edge Cases & Failure Modes

#### A. Metadata Bloat & Pathological Pruning Overhead
- **Mekanisme Kegagalan**: Terjadi ketika tabel mengalami frekuensi penulisan kecil berulang kali (*micro-batch ingestion* berlebih), menghasilkan jutaan partisi berukuran kecil (<5 MB).
- **Dampak**: Ukuran metadata global melampaui kapasitas RAM node koordinator (*Metadata Service*). Waktu kompilasi kueri dan evaluasi *zone maps* membutuhkan waktu puluhan detik sebelum I/O data dimulai.
- **Mitigasi**: Jalankan proses *Auto-Clustering* dan *Background Compaction Service* secara periodik untuk melebur (*merge*) file-file kecil menjadi ukuran optimal (100 MB - 500 MB).

#### B. Partition Skew & Clustering Degeneration
- **Mekanisme Kegagalan**: Kolom yang sering dijadikan filter memiliki korelasi rendah atau derajat keterurutan nol (*zero natural clustering*), misalnya predikat filtering dilakukan pada UUID yang dihasilkan secara acak.
- **Dampak**: Nilai `min` dan `max` dari setiap *micro-partition* mencakup hampir seluruh domain data tabel $[-\infty, +\infty]$. *Zone map pruning* gagal bekerja ($0\%$ partisi tereliminasi), memaksa sistem membaca 100% data dari *remote storage*.
- **Mitigasi**: Tentukan secara eksplisit *Clustering Key* berbasis kolom dengan kardinalitas sedang yang merefleksikan pola kueri dominan (seperti `organization_id`, `event_date`).

#### C. Memory Spillover Cascade
- **Mekanisme Kegagalan**: Kueri melibatkan agregasi `GROUP BY` atau *Hash Join* kardinalitas tinggi di mana ukuran tabel hash melebihi RAM worker node.
- **Tahapan Degradasi**:
  1. *Spill to Local Storage*: Engine menulis buffer ke local SSD NVMe. Penurunan throughput terjadi secara moderat (sekitar 2x-5x lebih lambat).
  2. *Spill to Remote Storage*: Local SSD NVMe penuh; engine terpaksa menulis temporary spill files ke AWS S3 / GCS secara sinkron via jaringan.
- **Dampak**: Throughput jatuh drastis (hingga 100x lebih lambat), berpotensi memicu *Query Timeout Exception*.
- **Mitigasi**: Terapkan deteksi dini ukuran memori (*memory reservation protocols*) dan lakukan *scale-up* warehouse size (misalnya dari ukuran Medium ke X-Large) untuk melipatgandakan alokasi RAM per node sebelum eksekusi pipeline berat.

---

### 8. Trade-offs & Alternatif Solusi

| Arsitektur / Komponen | Pilihan A | Pilihan B | Trade-off / Implikasi Teknis |
| :--- | :--- | :--- | :--- |
| **Engine Execution Model** | **Vectorized Execution (Batching)**<br>*(Snowflake, Photon, ClickHouse)* | **JIT Code Generation**<br>*(HyPer, Spark Catalyst, DuckDB hybrid)* | Vectorized Engine lebih stabil untuk kompilasi kueri yang sangat cepat, mudah di-*debug*, dan ramah terhadap profiling CPU profiler. JIT Engine menghilangkan instruksi memori antar-operator (*data stays in CPU register*), namun biaya *compilation latency* dapat mendominasi jika kueri dieksekusi secara ad-hoc dengan runtime pendek. |
| **Storage Topology** | **Decoupled Compute & Storage** | **Shared-Nothing MPP Architecture** | Decoupled memberikan elastisitas tanpa batas, isolasi beban kerja, dan efisiensi biaya saat komputasi mati (*auto-suspend*). Kelemahannya: ada latensi jaringan dasar saat *cold-cache*. Shared-Nothing menawarkan *raw latency* lebih rendah untuk kueri repetitif jika data sudah tersimpan di RAM/Disk lokal, tetapi sangat kaku dan mahal dalam proses scaling. |
| **Micro-Partition Metadata** | **Eager Global Catalog (Snowflake)** | **On-Storage Parquet Footers (Delta Lake/Iceberg)** | Global Catalog memusatkan metadata di *low-latency KV store*, menghasilkan kalkulasi pruning yang sangat cepat. Parquet Footer/Manifest File berbasis storage terbuka (*open standards*) portabel terhadap berbagai engine, tetapi dapat menimbulkan overhead I/O saat membaca metadata ribuan file manifest. |

---

### 9. Best Practices & Standard Industri

1. **Alignment Partisi Terhadap Rentang Waktu (Temporal Clustering)**:
   Hampir 80% analitik enterprise memiliki komponen filter temporal (`WHERE event_timestamp >= '...'`). Selalu susun urutan *ingestion* atau definisikan clustering keys yang diawali oleh dimensi waktu, untuk memaksimalkan efisiensi *micro-partition pruning* otomatis.
2. **Hindari Antipattern Evaluasi Fungsi pada Kolom Filter**:
   ```sql
   -- BAD: Menggagalkan Metadata Pruning secara total
   -- Driver tidak dapat mengevaluasi Zone Map karena kolom terbungkus fungsi runtime
   SELECT * FROM enterprise_sales WHERE DATE(created_at) = '2023-10-01';

   -- GOOD: Menjaga integritas evaluasi Zone Map
   SELECT * FROM enterprise_sales 
   WHERE created_at >= '2023-10-01 00:00:00' AND created_at < '2023-10-02 00:00:00';
   ```
3. **Warehouse Auto-Suspend & Auto-Resume Configuration**:
   Konfigurasikan batas *auto-suspend* secara ketat (misalnya 60 detik untuk beban batch ETL, 300 detik untuk dashboard BI interaktif guna menjaga *warm NVMe cache*). Hindari nilai `NEVER SUSPEND` pada lingkungan analitik non-kritis.
4. **Optimasi Cardinality Clustering**:
   Jangan pernah menggunakan kolom dengan kardinalitas mutlak (seperti UUID, Email, atau `nanosecond_timestamp`) sebagai *sole clustering key*. Gunakan kombinasi: kolom kardinalitas rendah/sedang terlebih dahulu, diikuti kolom kardinalitas lebih tinggi (misal: `tenant_id` kemudian `date`).

---

### 10. Hands-on Lab Exercise

#### Skenario:
Anda adalah Staff Data Engineer yang bertugas mendiagnosis performa kueri analitik finansial bernilai jutaan baris yang lambat. Anda diminta mengukur perbedaan konsumsi scanning memori/vektor antara sistem non-pruned vs. metadata-pruned, serta memverifikasi eksekusi filter tervektorisasi.

#### Langkah 1: Setup Environment
Pastikan dependensi terpasang pada Python 3.11+:
```bash
pip install numpy pyarrow tabulate
```

#### Langkah 2: Buat Skrip Eksperimen Komparasi
Simpan kode berikut sebagai `lab_dw_execution.py`:

```python
import time
import numpy as np
from core_cloud_dw_engine import (
    MicroPartition, 
    VectorizedTableScan, 
    VectorizedFilter, 
    VectorizedAggregate
)

def run_lab():
    print("================================================================")
    print("LAB: METADATA-DRIVEN PRUNING & VECTORIZED SCAN EXPERIMENT")
    print("================================================================")

    # 1. Bangun 20 Micro-partitions sintetis (Total 2,000,000 baris)
    num_parts = 20
    rows_per_part = 100_000
    partitions = []

    print(f"Generating {num_parts} micro-partitions ({num_parts * rows_per_part:,} rows)...")
    for i in range(num_parts):
        # Partisi terkelompok (clustered) secara alami berdasarkan urutan logis
        start_id = i * 10_000
        end_id = (i + 1) * 10_000
        account_ids = np.random.randint(start_id, end_id, size=rows_per_part)
        amounts = np.random.exponential(scale=100.0, size=rows_per_part)
        
        part = MicroPartition.create({
            "account_id": account_ids,
            "amount": amounts
        })
        partitions.append(part)

    # 2. Definisikan Predikat Seleksi Sempit
    # Kueri: Mencari account_id >= 180,000 (Hanya ada di 2 partisi terakhir)
    target_account = 180_000

    print("\n--- TEST CASE A: Eksekusi Tanpa Pruning (Full Scan Vectorized) ---")
    start_time = time.perf_counter()
    
    # Inisialisasi scan tanpa predikat pushdown (Full Scan)
    scan_naive = VectorizedTableScan(
        partitions=partitions,
        columns=["account_id", "amount"],
        predicates={}, # Tanpa pushdown
        vector_chunk_size=2048
    )
    filter_naive = VectorizedFilter(scan_naive, "account_id", ">=", target_account)
    agg_naive = VectorizedAggregate(filter_naive, "amount", "SUM")
    
    agg_naive.open()
    res_naive = agg_naive.next()
    agg_naive.close()
    duration_naive = time.perf_counter() - start_time
    val_naive = list(res_naive.columns.values())[0][0] if res_naive else 0.0

    print(f"Result : {val_naive:,.2f}")
    print(f"Elapsed Time: {duration_naive * 1000:.2f} ms")

    print("\n--- TEST CASE B: Eksekusi Dengan Metadata-Driven Pruning ---")
    start_time = time.perf_counter()
    
    # Inisialisasi scan dengan predikat pushdown (Engine memotong partisi via zone map)
    scan_optimized = VectorizedTableScan(
        partitions=partitions,
        columns=["account_id", "amount"],
        predicates={"account_id": (">=", target_account)},
        vector_chunk_size=2048
    )
    filter_optimized = VectorizedFilter(scan_optimized, "account_id", ">=", target_account)
    agg_optimized = VectorizedAggregate(filter_optimized, "amount", "SUM")
    
    agg_optimized.open()
    res_optimized = agg_optimized.next()
    agg_optimized.close()
    duration_optimized = time.perf_counter() - start_time
    val_optimized = list(res_optimized.columns.values())[0][0] if res_optimized else 0.0

    print(f"Result : {val_optimized:,.2f}")
    print(f"Elapsed Time: {duration_optimized * 1000:.2f} ms")

    # Evaluasi Reduksi
    speedup = duration_naive / duration_optimized if duration_optimized > 0 else 0
    print("\n================================================================")
    print(f"PERFORMANCE METRICS SUMMARY:")
    print(f"- Speedup Factor       : {speedup:.2f}x")
    print(f"- Eligible Partitions  : {len(scan_optimized.eligible_partitions)} / {num_parts}")
    print(f"- Scan Elimination     : {((num_parts - len(scan_optimized.eligible_partitions)) / num_parts) * 100:.1f}% data bypassed")
    print("================================================================")

if __name__ == "__main__":
    run_lab()
```

#### Langkah 3: Eksekusi dan Analisis Hasil
Jalankan skrip:
```bash
python lab_dw_execution.py
```

#### Kriteria Keberhasilan Verifikasi:
1. Nilai agregasi matematis `res_naive` dan `res_optimized` identik secara presisi.
2. Metrik `Scan Elimination` mencapai minimal **90%** (hanya 2 dari 20 micro-partitions yang dibaca).
3. Waktu eksekusi Case B menunjukkan reduksi latensi signifikan secara konsisten berbanding lurus dengan jumlah data yang berhasil di-*prune*.