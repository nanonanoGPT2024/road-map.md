# Bab 08: VertiPaq Optimization Engine & Performance Tuning

## Module 01: Arsitektur Internal VertiPaq, Encoding Engine, dan Memory Footprint Analysis

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis dekomposisi komputasi internal VertiPaq**: Membedakan secara granular siklus eksekusi antara *Formula Engine* (FE) dan *Storage Engine* (SE), termasuk pelacakan *physical query plan* dan instruksi `xmSQL`.
- **Mengevaluasi algoritma kompresi data kolom**: Mendiagnosis mekanisme kerja *Value Encoding*, *Dictionary/Hash Encoding*, dan *Run-Length Encoding* (RLE) pada level partisi dan segmen.
- **Mengukur alokasi memori internal Tabular**: Menghitung secara matematis dan empiris ukuran *Data Segment*, *Dictionary Segment*, dan *Hierarchy Structures* menggunakan *Dynamic Management Views* (DMVs).
- **Mendeteksi anomali *Storage Engine fallbacks***: Mengidentifikasi pemanggilan *CallbackDataID* yang mendeoptimasi paralelisasi SE dan memaksa pemrosesan kembali ke FE baris demi baris (*row-by-row iteration*).
- **Membangun sistem audit otomatis performa VertiPaq**: Mengembangkan skrip otomatisasi berbasis Python dan XMLA/DMV untuk memindai kardinalitas, rasio kompresi, dan fragmentasi struktur data secara terprogram.

---

### 2. Concept Overview

VertiPaq adalah *in-memory columnar database engine* yang menjadi fondasi *Analytic Services* (SSAS Tabular, Azure Analysis Services, Power BI Premium/Fabric). Karakteristik fundamental VertiPaq berakar pada dua premis:
1. **Columnar Orientation**: Data disimpan per kolom, bukan per baris (*tuple*). Operasi analitik agregatif ($\sum$, $\text{avg}$, $\text{max}$, dsb.) hanya memindai vektor memori yang relevan tanpa membaca atribut lain yang tidak diproyeksikan.
2. **Aggressive In-Memory Encoding**: Data dikompresi sedemikian rupa agar seluruh *working dataset* dapat termuat di dalam RAM. VertiPaq didesain dengan asumsi bahwa latensi akses memori primer jauh lebih rendah dibandingkan disk I/O, asalkan rasio kompresi cukup tinggi untuk memaksimalkan *CPU L1/L2/L3 cache line efficiency*.

#### Mental Model: Formula Engine vs. Storage Engine

```
                             +------------------------+
                             |       DAX Query        |
                             +------------------------+
                                         |
                                         v
                             +------------------------+
                             |     Formula Engine     |
                             |          (FE)          |
                             +------------------------+
                             | * Parser & Resolver    |
                             | * Logical/Physical Plan|
                             | * Single-threaded      |
                             | * Advanced DAX Logic   |
                             +------------------------+
                                         |
                       Generates xmSQL   |   Materializes
                          Requests       |   Data Cache
                                         v
                             +------------------------+
                             |     Storage Engine     |
                             |      (SE/VertiPaq)     |
                             +------------------------+
                             | * Multi-threaded       |
                             | * SIMD Vectorized Ops  |
                             | * Scans Segments & RLE |
                             | * Resolves Joins/Cache |
                             +------------------------+
```

- **Formula Engine (FE)**: Komponen pengatur alur kerja. FE menerima kueri DAX, membuat *logical and physical query plan*, mengeksekusi fungsi kompleks yang tidak didukung SE (seperti algoritma kalkulasi rekursif non-linier atau manipulasi konteks baris rumit), dan menyatukan hasil akhir. FE bekerja secara **single-threaded** per kueri.
- **Storage Engine (SE / VertiPaq)**: Komponen pekerja data. SE menerima instruksi dalam bentuk bahasa internal bernama `xmSQL` dari FE. SE mengeksekusi pemindaian (*scan*), penyaringan (*filter*), pengelompokan (*group by*), dan penggabungan (*hash join*) secara **multi-threaded**, memanfaatkan seluruh *core* CPU yang dialokasikan, serta mengeksekusi operasi langsung di atas data terkompresi.

---

### 3. Why It Matters

Di lingkungan enterprise, ketidakmampuan memahami mekanisme internal VertiPaq menyebabkan degradasi performa yang masif:

1. **Pemborosan Alokasi Memori Kapasitas (Fabric / Premium Core Throttling)**: Kapasitas Power BI (P-SKU atau F-SKU) memiliki batas RAM kaku (*working set limit*). Model data dengan penataan kolom yang buruk (misalnya menyertakan *timestamp* presisi milidetik atau *surrogate keys* GUID) dapat menggelembungkan memori hingga 10–50x lipat lebih besar. Hal ini memicu *memory paging*, penggusuran model (*model eviction*), atau penalti *compute throttling*.
2. **CPU Starvation Akibat CallbackDataID**: Ketika FE tidak dapat menerjemahkan kalkulasi DAX menjadi instruksi `xmSQL` murni, SE terpaksa meminta bantuan FE untuk setiap baris evaluasi melalui mekanisme `CallbackDataID`. Hal ini melumpuhkan pemrosesan multi-threaded SE, menyebabkan lonjakan drastis durasi kueri dari sub-detik menjadi puluhan detik.
3. **Kueri Konkuren yang Buruk**: Efisiensi VertiPaq bertumpu pada *scan throughput* memori. Jika kompresi buruk, SE memindahkan lebih banyak byte melalui bus memori (QPI/UPI), menyebabkan saturasi *memory bandwidth* saat diakses oleh ratusan pengguna secara bersamaan.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan siklus fisik konversi tabel tabular ke dalam segmen-segmen terkompresi VertiPaq:

```
Source Data Matrix (Relational Source / Flat Rows)
+------+---------------------+------------+-----------+
| Row  | Timestamp           | ProductID  | SalesAmt  |
+------+---------------------+------------+-----------+
| 1    | 2026-03-31 08:00:00 | PROD-A     | 100       |
| 2    | 2026-03-31 08:00:00 | PROD-B     | 100       |
| 3    | 2026-03-31 08:00:00 | PROD-A     | 150       |
| ...  | ...                 | ...        | ...       |
| 1.2M | 2026-03-31 09:00:00 | PROD-C     | 200       |
+------+---------------------+------------+-----------+
                           |
                           v  Transformation: Ingestion & Columnar Pivot
+-------------------------------------------------------------------------+
|                  VertiPaq Segment Partitioner (1M Rows)                 |
+-------------------------------------------------------------------------+
       |                                                 |
       v Segment 1 (Rows 1 to 1,000,000)                 v Segment 2 (Rows 1,000,001 to ...)
+------------------------------------+           +------------------------------------+
| Column: ProductID                  |           | Column: ProductID                  |
| 1. Dictionary Segment (Global)     |           | 1. Dictionary Segment (Global)     |
|    ID 0 -> PROD-A                  |           |    ID 0 -> PROD-A                  |
|    ID 1 -> PROD-B                  |           |    ID 1 -> PROD-B                  |
|    ID 2 -> PROD-C                  |           |    ID 2 -> PROD-C                  |
| 2. Bit-Packed Local Index Segment  |           | 2. Bit-Packed Local Index Segment  |
|    [0, 1, 0, 0, 1, ..., 2]         |           |    [2, 2, 1, 0, 1, ..., 0]         |
| 3. RLE Compression Run             |           | 3. RLE Compression Run             |
|    (Val:0, Count:1), (Val:1, C:1)..|           |    (Val:2, Count:2), (Val:1, C:1)..|
| 4. Hierarchy Structure & Bitmaps   |           | 4. Hierarchy Structure & Bitmaps   |
+------------------------------------+           +------------------------------------+
       |                                                 |
+------------------------------------+           +------------------------------------+
| Column: SalesAmt                   |           | Column: SalesAmt                   |
| 1. Value Encoding:                 |           | 1. Value Encoding:                 |
|    Base Value: 100                 |           |    Base Value: 100                 |
|    Data Segment: Delta values      |           |    Data Segment: Delta values      |
|    [0, 0, 50, ...]                 |           |    [100, 100, 0, ...]              |
| 2. Bit Width Optimization          |           | 2. Bit Width Optimization          |
|    Max Delta: 50 -> 6 bits/val     |           |    Max Delta: 100 -> 7 bits/val    |
+------------------------------------+           +------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### 5.1 Algoritma Kompresi VertiPaq

VertiPaq menggunakan tiga teknik kompresi inti yang dievaluasi secara dinamis saat kompilasi data (*partition processing*):

##### 1. Value Encoding
Value Encoding digunakan secara eksklusif untuk kolom numerik (integer atau desimal tetap) yang memiliki rentang nilai terbatas.
- **Mekanisme**: VertiPaq menghitung nilai minimum $V_{min}$ dari suatu kolom dalam partisi/segmen. Setiap nilai baris $V$ digantikan oleh nilai selisih (*delta*):
  $$V_{encoded} = V - V_{min}$$
- **Optimalisasi Bit**: Nilai $V_{encoded}^{max} = V_{max} - V_{min}$ menentukan jumlah bit minimum $b$ yang dibutuhkan untuk menyimpan data:
  $$b = \lceil \log_2(V_{encoded}^{max} + 1) \rceil$$
- Jika rentang nilai adalah $1.000.000$ hingga $1.000.015$, daripada menggunakan 32-bit atau 64-bit integer, VertiPaq hanya memerlukan $b = \lceil \log_2(16) \rceil = 4\text{ bit per baris}$.

##### 2. Hash / Dictionary Encoding
Digunakan untuk tipe data string, nilai non-numerik, atau integer yang rentang selisihnya terlampau besar sehingga *Value Encoding* tidak efisien.
- **Mekanisme**: VertiPaq menyusun *Dictionary Structure* yang memetakan setiap nilai unik ke integer ID ($0, 1, \dots, N-1$).
- **Bit-packing**: Jika sebuah kolom memiliki $N$ nilai unik (kardinalitas = $N$), maka setiap elemen array data disimpan menggunakan $b$ bit:
  $$b = \lceil \log_2(N) \rceil$$
- **Dampak Memori**: Terdiri dari dua komponen:
  1. *Dictionary Store*: Tabel hash pencarian yang menyimpan representasi literal string.
  2. *Data Stream*: Rangkaian bit-packed index integers yang menunjuk ke *Dictionary Store*.

##### 3. Run-Length Encoding (RLE)
RLE diterapkan di atas *Value Encoding* atau *Dictionary Encoding* untuk memampatkan nilai-nilai identik yang berurutan.
- **Representasi**: Alih-alih menyimpan array data $[0, 0, 0, 0, 1, 1, 2]$, RLE menyimpan representasi triplet/duplet:
  $$\langle \text{Value: } 0, \text{ Repeat: } 4 \rangle, \langle \text{Value: } 1, \text{ Repeat: } 2 \rangle, \langle \text{Value: } 2, \text{ Repeat: } 1 \rangle$$
- **Sort Order Impact**: RLE sangat bergantung pada urutan baris data (*sort order*). Kolom dengan kardinalitas rendah yang diurutkan secara terkonsentrasi dapat terkompresi hingga mendekati 0 byte dalam segmen.

#### 5.2 Segmentasi Data dan Parallel Scans
- VertiPaq membagi partisi tabel menjadi beberapa **Segmen**.
- Ukuran standar segmen (*default segment size*) adalah **1.048.576 baris ($2^{20}$ baris)**.
- Setiap segmen dioperasikan secara atomik oleh *thread* CPU independen. Pemrosesan paralel SE mendistribusikan segmen ke seluruh core CPU yang tersedia. Jika suatu tabel memiliki 8 juta baris, tabel tersebut akan dipecah menjadi 8 segmen terpisah dan dapat dipindai secara konkruen oleh 8 core.

#### 5.3 Hierarchy Structures and Relationships
Selain data kolom, memori terpakai untuk:
- **Hierarchies**: Struktur *B-Tree-like* yang dibangun VertiPaq untuk mempercepat navigasi hirarkis DAX dan pencarian indeks langsung (*Direct Point Lookups*).
- **Relationship Caches**: Tabel pemetaan biner dua arah antara kolom *Primary Key* dan *Foreign Key* yang menyimpan pointer fisik antar baris segmen, memungkinkan join dieksekusi tanpa kalkulasi hash secara *on-the-fly*.

---

### 6. Production-Ready Code Implementation

Berikut adalah skrip audit performa berbasis Python. Modul ini terhubung ke Analysis Services / Power BI XMLA endpoint menggunakan protokol ADOMD / OLEDB via `pyadomd`, mengeksekusi DMV internal VertiPaq, mengaudit jejak memori secara struktural, dan mengekstraksi metrik optimasi segmentasi.

```python
"""
VertiPaq Memory & Storage Engine Auditing Utility
File: vertipaq_auditor.py
Requires: pyadomd, pandas, tabulate
"""

from dataclasses import dataclass
from typing import List, Optional
import logging
import pandas as pd
from pyadomd import Pyadomd

# Setup granular enterprise logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s"
)
logger = logging.getLogger("VertiPaqAuditor")


@dataclass(frozen=True)
class ColumnStorageMetric:
    table_name: str
    column_name: str
    cardinality: int
    data_size_kb: float
    dictionary_size_kb: float
    hierarchy_size_kb: float
    total_size_kb: float
    encoding_type: str
    segments_count: int


class VertiPaqAnalyzer:
    """
    Konektor dan penganalisis struktur penyimpanan internal Tabular/VertiPaq.
    Mengakses DMV Analysis Services tingkat rendah untuk mengekstrak metrik segmentasi.
    """

    DMV_STORAGE_COLUMNS = """
    SELECT 
        [DIMENSION_NAME] AS [TABLE_NAME],
        [COLUMN_ID],
        [ATTRIBUTE_NAME] AS [COLUMN_NAME],
        [DICTIONARY_SIZE],
        [COLUMN_ENCODING]
    FROM $SYSTEM.DISCOVER_STORAGE_TABLE_COLUMNS
    WHERE [COLUMN_TYPE] = 'BASIC_DATA'
    """

    DMV_SEGMENT_DETAILS = """
    SELECT 
        [DIMENSION_NAME] AS [TABLE_NAME],
        [COLUMN_ID],
        [SEGMENT_NUMBER],
        [RECORDS_COUNT],
        [USED_SIZE],
        [BITS_PER_VALUE],
        [COMPRESSION_TYPE]
    FROM $SYSTEM.DISCOVER_STORAGE_TABLE_COLUMN_SEGMENTS
    """

    def __init__(self, connection_string: str) -> None:
        self._conn_str = connection_string

    def _execute_dmv(self, query: str) -> pd.DataFrame:
        """Mengeksekusi DMV dengan validasi error dan manajemen konteks ADOMD."""
        try:
            logger.info("Mengeksekusi kueri DMV VertiPaq...")
            with Pyadomd(self._conn_str) as conn:
                with conn.cursor() as cur:
                    cur.execute(query)
                    data = cur.fetchall()
                    columns = [desc[0] for desc in cur.description]
                    return pd.DataFrame(data, columns=columns)
        except Exception as ex:
            logger.error("Gagal mengeksekusi DMV: %s", str(ex), exc_info=True)
            raise ConnectionError(f"VertiPaq DMV execution failure: {ex}") from ex

    def analyze_memory_footprint(self) -> List[ColumnStorageMetric]:
        """
        Menganalisis memori VertiPaq pada level kolom dan segmen,
        kemudian merekonsiliasi ukuran data mentah, kamus, dan hirarki.
        """
        raw_cols_df = self._execute_dmv(self.DMV_STORAGE_COLUMNS)
        segments_df = self._execute_dmv(self.DMV_SEGMENT_DETAILS)

        if raw_cols_df.empty or segments_df.empty:
            logger.warning("Tidak ada metadata yang ditemukan dari instance VertiPaq.")
            return []

        # Agregasi data segment per kolom
        seg_summary = segments_df.groupby(['TABLE_NAME', 'COLUMN_ID']).agg(
            total_records=('RECORDS_COUNT', 'max'),
            total_data_bytes=('USED_SIZE', 'sum'),
            segment_count=('SEGMENT_NUMBER', 'count')
        ).reset_index()

        merged_df = pd.merge(
            raw_cols_df,
            seg_summary,
            on=['TABLE_NAME', 'COLUMN_ID'],
            how='inner'
        )

        metrics_list: List[ColumnStorageMetric] = []

        for _, row in merged_df.iterrows():
            dict_kb = float(row.get('DICTIONARY_SIZE', 0) or 0) / 1024.0
            data_kb = float(row.get('total_data_bytes', 0) or 0) / 1024.0
            # Hierarchy overhead diestimasi atau dihitung via segmen indeks (bila ada)
            hierarchy_kb = 0.0  
            total_kb = dict_kb + data_kb + hierarchy_kb

            encoding_raw = row.get('COLUMN_ENCODING', 0)
            # Pemetaan enumerasi encoding VertiPaq
            encoding_map = {1: "VALUE", 2: "HASH (DICTIONARY)"}
            encoding_desc = encoding_map.get(encoding_raw, f"UNKNOWN ({encoding_raw})")

            metric = ColumnStorageMetric(
                table_name=str(row['TABLE_NAME']),
                column_name=str(row['COLUMN_NAME']),
                cardinality=int(row.get('total_records', 0)),
                data_size_kb=round(data_kb, 2),
                dictionary_size_kb=round(dict_kb, 2),
                hierarchy_size_kb=round(hierarchy_kb, 2),
                total_size_kb=round(total_kb, 2),
                encoding_type=encoding_desc,
                segments_count=int(row.get('segment_count', 0))
            )
            metrics_list.append(metric)

        metrics_list.sort(key=lambda x: x.total_size_kb, reverse=True)
        return metrics_list

    def generate_recommendations(self, metrics: List[ColumnStorageMetric]) -> List[str]:
        """Menghasilkan saran perbaikan otomatis berdasarkan ambang batas arsitektural."""
        recommendations = []
        for m in metrics:
            # Aturan 1: Dictionary mendominasi total konsumsi memori
            if m.total_size_kb > 50000 and (m.dictionary_size_kb / m.total_size_kb) > 0.70:
                recommendations.append(
                    f"CRITICAL: Kolom '{m.table_name}'[{m.column_name}] didominasi Dictionary Size "
                    f"({m.dictionary_size_kb:.2f} KB / {m.total_size_kb:.2f} KB). "
                    f"Kardinalitas terlalu tinggi untuk string. Pertimbangkan dekomposisi atau hashing."
                )

            # Aturan 2: Kolom Hash Encoding padahal numerik rentang sempit
            if "HASH" in m.encoding_type and m.column_name.lower().endswith(('id', 'key', 'code', 'num')):
                recommendations.append(
                    f"OPTIMIZATION: Kolom '{m.table_name}'[{m.column_name}] menggunakan HASH encoding. "
                    f"Verifikasi apakah tipe data dapat diubah ke INTEGER murni untuk mengaktifkan VALUE encoding."
                )
        return recommendations


if __name__ == "__main__":
    # Konfigurasi koneksi XMLA (Power BI Premium Workspace atau Local SSAS)
    # Contoh endpoint lokal Tabular / DAX Studio:
    CONNECTION_STRING = (
        "Provider=MSOLAP;"
        "Data Source=localhost:51234;"
        "Initial Catalog=AdventureWorksModel;"
    )

    try:
        analyzer = VertiPaqAnalyzer(CONNECTION_STRING)
        results = analyzer.analyze_memory_footprint()
        
        print("\n=== TOP 5 MEMORY CONSUMING COLUMNS IN VERTIPAQ ===")
        for res in results[:5]:
            print(
                f"[{res.table_name}] -> {res.column_name} | "
                f"Total: {res.total_size_kb} KB | "
                f"Data: {res.data_size_kb} KB | "
                f"Dict: {res.dictionary_size_kb} KB | "
                f"Enc: {res.encoding_type}"
            )
            
        print("\n=== ARCHITECTURAL AUDIT RECOMMENDATIONS ===")
        recs = analyzer.generate_recommendations(results)
        for rec in recs:
            print(f"- {rec}")
            
    except ConnectionError:
        logger.warning("Simulasi lokal: Koneksi XMLA gagal diinisialisasi (Port mock offline).")
```

---

### 7. Edge Cases & Failure Modes

#### 1. The `CallbackDataID` Engine Stall
- **Kondisi**: Penggunaan ekspresi DAX kompleks di dalam fungsi agregasi/iterasi (misalnya `CALCULATE` di dalam `CONCATENATEX` atau `SUMX` dengan pemanggilan aturan keamanan RLS dinamis tingkat lanjut) di mana logika per baris tidak dapat diekspresikan via filter primitif `xmSQL`.
- **Dampak Kegagalan**: Storage Engine membangkitkan `CallbackDataID` ke Formula Engine. SE menghentikan sementara proses vektorisasinya, mentransfer eksekusi kembali ke FE secara *single-threaded*, mengevaluasi satu nilai, dan mengembalikan hasil ke SE. Latensi kueri melonjak eksponensial ($\mathcal{O}(N)$ FE roundtrips).
- **Mitigasi**: Sederhanakan filter konteks; hindari referensi measure kompleks di dalam iterasi baris ketat tanpa *materialized temporary flag*.

#### 2. High-Cardinality Strings & Dictionary Sprawl
- **Kondisi**: Menyimpan atribut string acak seperti GUID, Token, URL, atau *Free-Text Comments* pada tabel fakta dengan puluhan juta baris.
- **Dampak Kegagalan**: Ukuran *Dictionary Segment* melebihi ukuran *Data Segment* hingga 500%. Hal ini merusak *L3 CPU Cache Prefetching*, karena kamus berukuran gigabyte tidak muat dalam CPU cache, memaksa SE melakukan pembacaan memori acak (*random pointer traversal*) di RAM utama.
- **Mitigasi**: Pindahkan kolom komentar/detail keluar dari model Tabular; pisahkan GUID menjadi 2 kolom *binary integer* 64-bit atau hapus dari model bila tidak digunakan dalam relasi.

#### 3. Floating Point Value Encoding Invalidation
- **Kondisi**: Penggunaan tipe data `Decimal/Float` IEEE 754 presisi ganda untuk kolom mata uang atau metrik numerik kontinu (contoh: `12.345678`).
- **Dampak Kegagalan**: Algoritma kompresi mendeteksi bahwa pembagian nilai menghasilkan *delta* floating point kontinu yang mustahil dikompresi dengan *Value Encoding*. VertiPaq beralih ke *Hash Encoding*, membuat kamus string/float raksasa.
- **Mitigasi**: Gunakan tipe data `Fixed Decimal Number` (`Currency` di DAX/Tabular), yang secara internal diimplementasikan sebagai integer 64-bit berskala 4 desimal ($V \times 10.000$), memungkinkan *Value Encoding* beroperasi secara maksimal.

---

### 8. Trade-offs & Alternatif Solusi

| Dimensi Arsitektur | VertiPaq (In-Memory Import) | Direct Lake (Fabric OneLake) | DirectQuery (Relational Engine) | Composite Models |
| :--- | :--- | :--- | :--- | :--- |
| **Latensi Kueri** | **Ultra-Low (<100ms)** (SIMD In-Memory Vectorization) | **Sangat Rendah (<200ms)** (Streaming Parquet ke RAM) | **Tinggi (Detik - Menit)** (Tergantung performa RDBMS) | **Bervariasi** (Cepat untuk VertiPaq, Lambat jika DQ) |
| **Batas Memori** | Terikat kapasitas RAM host (P-SKU / F-SKU memory ceiling) | Memuat *columnar segments* langsung dari Parquet file saat dibutuhkan | Nol konsumsi RAM VertiPaq (semua di RDBMS) | Sebagian model termuat di RAM, sebagian di database |
| **Refresh Latency** | Membutuhkan ETL Processing Schedule | Real-time / Near Real-time (Data tersinkronisasi di Parquet) | Zero ETL Refresh (Langsung membaca sumber) | Terjadwal untuk partisi cache, real-time untuk DQ |
| **Skalabilitas Data** | Ratusan Juta Baris (Dibatasi RAM) | Miliaran Baris (Batas komputasi terdistribusi OneLake) | Puluhan Miliar Baris (Dibatasi kapasitas database sumber) | Skala sangat fleksibel melalui pemisahan partisi |

---

### 9. Best Practices & Standard Industri

1. **Dekonstruksi Date/Time Granularity**: Jangan pernah mempertahankan kolom `DateTime` utuh pada tabel transaksi volume tinggi. Pisahkan menjadi dua kolom terpisah:
   - Satu kolom `Date` murni (Kardinalitas $\approx 365$ nilai/tahun $\rightarrow$ kompresi optimal).
   - Satu kolom `Time` dibulatkan ke resolusi menit atau detik (Kardinalitas maksimal 1.440 atau 86.400). Hal ini mengeliminasi jutaan nilai unik.
2. **Sort Order Optimization untuk RLE**: Urutkan data secara fisik saat injeksi data (melalui ETL/Data Warehouse) berdasarkan kolom dengan kardinalitas terendah terlebih dahulu sebelum kolom kardinalitas tinggi:
   $$\text{Urutan Sort}: \text{TenantID} \longrightarrow \text{StatusID} \longrightarrow \text{Date} \longrightarrow \text{TransactionID}$$
   Ini memaksimalkan panjang *run* nilai identik yang berurutan, sehingga kompresi RLE dapat mereduksi miliaran baris menjadi representasi yang sangat kecil.
3. **Pembersihan Auto-Generated Metadata**: Nonaktifkan secara global opsi *Auto Date/Time* di Power BI Desktop Options. Opsi default ini membuat tabel kalender lokal tersembunyi untuk setiap kolom tanggal di setiap tabel, yang memboroskan alokasi kamus memori.
4. **Disabled Attribute Hierarchies**: Pada atribut tabel dimensi yang tidak pernah digunakan untuk *drill-down* visual atau *slicing* MDX, nonaktifkan pembuatan struktur hirarki internal menggunakan properti `IsAvailableInMdx = False` melalui Tabular Editor. Langkah ini menghemat 15–20% jejak memori pada dimensi besar.

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Anda bertindak sebagai Lead BI Platform Architect. Model data `FactOnlineSales` yang menampung 10.000.000 baris menghabiskan RAM sebesar **1.8 GB** pada kapasitas Premium, memicu lonjakan memori dan eksekusi kueri yang lambat. Anda diminta untuk menganalisis memori internal VertiPaq, menemukan biang keladi inefisiensi kompresi, dan mengoptimalkannya hingga konsumsi memori turun di bawah **300 MB**.

#### Langkah 1: Diagnosis Jejak Memori melalui DAX Studio / DMV
1. Buka file `.pbix` atau hubungkan DAX Studio ke endpoint XMLA workspace.
2. Navigasikan ke tab **Advanced** $\rightarrow$ klik **View Metrics** (VertiPaq Analyzer).
3. Evaluasi metrik berikut pada tabel `FactOnlineSales`:
   - Amati kolom `OnlineSalesKey` (Surrogate Key).
   - Amati kolom `TransactionTimestamp` (Presisi tanggal dan jam gabungan).
   - Catat nilai `Data Size`, `Dictionary Size`, dan `Cardinality`.

*Ekspektasi Temuan:*
- `OnlineSalesKey`: Kardinalitas = 10.000.000, Tipe = String/Hash, Dictionary Size $\approx$ 450 MB.
- `TransactionTimestamp`: Kardinalitas = 8.750.000, Tipe = Hash, Total Size $\approx$ 800 MB.

#### Langkah 2: Refactoring Kolom & Optimalisasi Struktur Data
Modifikasi transformasi data pada lapisan upstream SQL View / Power Query M:

1. **Eliminasi Primary Key / Surrogate Key yang Tidak Digunakan**:
   Jika `OnlineSalesKey` tidak digunakan untuk membangun relasi ke tabel lain dan tidak diproyeksikan pada agregasi visual, hapus kolom ini sepenuhnya dari model Tabular:
   ```powerquery
   // M Script Optimization
   Table.RemoveColumns(Source, {"OnlineSalesKey"})
   ```

2. **Dekomposisi Kolom DateTime**:
   Ubah kolom `TransactionTimestamp` menjadi integer date key dan integer minute key:
   ```sql
   -- Upstream SQL Engine View Refactoring
   SELECT 
       CAST(CONVERT(VARCHAR(8), TransactionTimestamp, 112) AS INT) AS OrderDateKey,
       CAST(DATEPART(HOUR, TransactionTimestamp) * 60 + DATEPART(MINUTE, TransactionTimestamp) AS SMALLINT) AS OrderTimeMinuteKey,
       ProductID,
       SalesAmount,
       SalesQuantity
   FROM FactOnlineSalesSource;
   ```

3. **Casting Tipe Numerik ke Currency / Fixed Decimal**:
   Ubah kolom `SalesAmount` dari tipe Float ke tipe `Currency` (`Decimal Number` di Tabular) untuk memaksa VertiPaq mengaktifkan **Value Encoding**.

#### Langkah 3: Validasi Empiris Pasca-Optimalisasi
1. Muat ulang model (*Process Full*).
2. Jalankan ulang **VertiPaq Analyzer** di DAX Studio.
3. Eksekusi skrip kueri validasi DMV berikut:

```sql
SELECT 
    [DIMENSION_NAME] AS [Table],
    [ATTRIBUTE_NAME] AS [Column],
    [COLUMN_ENCODING] AS [Encoding_Type],
    [DICTIONARY_SIZE] / 1024 / 1024 AS [Dict_MB]
FROM $SYSTEM.DISCOVER_STORAGE_TABLE_COLUMNS
WHERE [DIMENSION_NAME] = 'FactOnlineSales'
ORDER BY [DICTIONARY_SIZE] DESC;
```

#### Hasil Verifikasi
- Pemrosesan berhasil mengalihkan `SalesAmount` ke `Value Encoding` (Dictionary Size = 0 Byte).
- Kardinalitas `OrderDateKey` tereduksi dari 8,75 juta menjadi $\approx 1.095$ (3 tahun kalender).
- Kardinalitas `OrderTimeMinuteKey` stabil pada angka maksimal 1.440 nilai unik.
- Total jejak memori tabel `FactOnlineSales` menyusut dari **1.8 GB** menjadi **$\approx$ 145 MB** (Reduksi ukuran memori > 90%), membebaskan headroom kapasitas CPU/RAM host secara signifikan.