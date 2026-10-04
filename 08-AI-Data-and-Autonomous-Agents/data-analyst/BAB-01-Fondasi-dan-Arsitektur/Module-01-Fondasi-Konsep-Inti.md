# Bab 01: Fondasi Analisis Data Modern, Taksonomi Entitas, dan Siklus Hidup Analitik

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- **Menganalisis** struktur data (terstruktur, semi-terstruktur, tidak terstruktur) serta implikasinya terhadap strategi penyimpanan, latensi kueri, dan kompleksitas transformasi.
- **Mengimplementasikan** paradigma *Tidy Data* (Wickham) untuk menormalisasi dataset denormalisasi mentah menjadi bentuk kanonikal analitis.
- **Merancang** alur validasi integritas data deterministik menggunakan skema kontrak (*schema contracts*) berbasis tipe data, batasan nilai (*constraints*), dan kelengkapan (*completeness*).
- **Mengevaluasi** spektrum analitik (Deskriptif, Diagnostik, Prediktif, Preskriptif) berdasarkan trade-off antara kompleksitas komputasi dan dampak bisnis.
- **Mengonstruksi** pipeline profiling data otomatis tingkat produksi menggunakan Python (`pandas`, `numpy`, `pydantic`) yang siap diintegrasikan ke orkestrasi analitik modern.

---

## 2. Conceptual Foundation

Data Analytics bertransformasi dari sekadar agregasi ad-hoc dan pelaporan historis menjadi disiplin rekayasa yang mengidentifikasi kausalitas sistemis. Landasan teoritis analisis data berakar pada **Teori Relasional Codd (1970)** dan **Prinsip Tidy Data Hadley Wickham (2014)**. 

Secara matematis, dataset terstruktur adalah relasi $R$ di atas himpunan domain $D_1, D_2, \dots, D_n$, di mana sebuah tupel $t \in R$ mewakili pemetaan instan dari entitas dunia nyata ke dalam ruang atribut terukur:
$$t = (d_1, d_2, \dots, d_n) \quad \text{dengan} \quad d_i \in D_i$$

Prinsip *Tidy Data* menetapkan standarisasi representasi semantik dataset:
1. Setiap variabel membentuk satu kolom.
2. Setiap observasi membentuk satu baris.
3. Setiap unit observasi membentuk satu tabel.

```
       Untidy (Pivot-Wide/Format Laporan)             Tidy (Format Analisis Kanonikal)
+------------+-------+-------+                  +------------+---------+-------+
| Department | Q1    | Q2    |                  | Department | Quarter | Metric|
+------------+-------+-------+                  +------------+---------+-------+
| Sales      | 15000 | 18000 |   ==[ Melt ]==>  | Sales      | Q1      | 15000 |
| Engineering| 42000 | 45000 |                  | Sales      | Q2      | 18000 |
+------------+-------+-------+                  | Engineering| Q1      | 42000 |
                                                | Engineering| Q2      | 45000 |
                                                +------------+---------+-------+
```

Jika data tidak berada dalam format kanonikal ini, operasi aljabar relasional dasar (seleksi, proyeksi, agregasi, penggabungan) membutuhkan mutasi skema runtime yang menguras alokasi memori $O(N \cdot M)$ dan memecah vektorisasi komputasi pada CPU modern.

---

## 3. The "Why"

Banyak inisiatif analitik korporat gagal bukan karena kelemahan algoritma pemodelan, melainkan akibat rapuhnya fondasi pemahaman data di hulu.

1. **Efisiensi Biaya Komputasi**: Struktur data yang salah memicu pemindaian *Full Table Scan* pada analytical warehouse berbasis kolom (seperti Google BigQuery, Snowflake, ClickHouse). Mengetahui perbedaan tipe skema mencegah alokasi *slot-time* dan *compute-unit* yang berlebihan.
2. **Kesesuaian Semantik**: Analisis deskriptif ("Apa yang terjadi?") yang dioperasikan di atas data kotor akan menghasilkan bias konfirmasi sistemik. Jika tim analitik salah membedakan antara nilai `NULL` (data hilang secara stokastik) dan `0` (kuantitas absolut nihil), estimasi rata-rata parametrik ($\mu$) menjadi terdistorsi secara permanen.
3. **Reproduisibilitas**: Menetapkan siklus hidup analitik formal (*Lifecycle Engine*) memastikan bahwa setiap temuan bisnis dapat dilacak balik (*audit trail*) hingga ke sumber atomiknya, memitigasi kerugian keputusan bisnis bernilai miliaran rupiah.

---

## 4. The "What"

Analisis data tingkat enterprise mencakup pemahaman batas-batas sistem, taksonomi data, dan diferensiasi peran teknis.

### Taksonomi Data

| Dimensi | Structured | Semi-Structured | Unstructured |
| :--- | :--- | :--- | :--- |
| **Model Skema** | *Schema-on-Write* (RDBMS, Data Warehouse) | *Schema-on-Read* (JSON, XML, Parquet) | *No Strict Schema* (Log teks mentah, Audio, PDF) |
| **Penyimpanan Utama**| PostgreSQL, Snowflake, ClickHouse | MongoDB, S3 Object Store, DocumentStore | AWS S3, Azure Blob, HDFS |
| **Akses Bahasa** | ANSI SQL | JSONPath, SQL/JSON functions | Engine NLP, Model Visi Komputer, Regex |
| **Entropi Informasi**| Sangat Rendah (Prediktif) | Menengah (Dinamis/Polimorfik) | Sangat Tinggi (Acak/Tergantung Konteks) |

### Analytics Maturity Model

```
Dampak Bisnis
     ^                                                      [Preskriptif]
     |                                             Optimasi Skenario Tindakan
     |                                                  (Simulasi, Heuristik)
     |                                      [Prediktif]
     |                               Peramalan Tren & Risiko
     |                              (Regresi, ML Time Series)
     |                     [Diagnostik]
     |               Akar Masalah (Root Cause)
     |             (Drill-down, Korelasi Multivariat)
     |        [Deskriptif]
     |     Kinerja Historis
     |  (Dashboard, KPI, Agregasi)
     +------------------------------------------------------------------------> Kompleksitas
```

---

## 5. The "How"

Siklus Hidup Analitik Modern dieksekusi melalui metodologi 6 tahap yang berulang:

1. **Frame the Problem**: Menerjemahkan kebutuhan bisnis kualitatif menjadi hipotesis statistik kuantitatif dan menentukan *Primary Metric* serta *Guardrail Metric*.
2. **Data Discovery & Acquisition**: Menemukan lokasi data (*catalog metadata*), menetapkan hak akses, dan mengekstrak sampel representatif.
3. **Data Profiling & Hygiene Verification**: Audit kualitas data: tipe data fisik vs logis, distribusi kurtosis/skewness, persentase nilai kosong (*nullness rate*), dan integritas referensial.
4. **Data Normalization & Feature Reshaping**: Mengonversi dataset menjadi bentuk *Tidy Data* kanonikal menggunakan aljabar relasional (*pivot, unpivot/melt, join, group-by*).
5. **Exploratory Data Analysis (EDA) & Statistical Inference**: Memetakan korelasi, mendeteksi anomali, melakukan uji beda hipotesis (t-test, ANOVA, Mann-Whitney U), dan mengekstraksi pola kausalitas.
6. **Communication, Operationalization & Data Contract Closure**: Mentransformasikan visualisasi menjadi cerita analitis (*data storytelling*) yang dapat ditindaklanjuti serta mengunci skema data ke dalam *Data Contract* produksi.

---

## 6. Architecture & System Flow

Alur data end-to-end yang menjembatani data mentah hingga penyajian insight:

```
[Sumber Data Operasional]
  |-- OLTP Database (Postgres) ---> CDC (Debezium)
  |-- API Events (JSON)       ---> Event Stream (Kafka)
  |-- 3rd Party SaaS (Stripe) ---> Batch Extractor
                                         |
                                         v
                         +--------------------------------+
                         |       BRONZE / RAW ZONE        |
                         | (Object Storage: MinIO/S3)     |
                         | - Format: JSON mentah, Parquet |
                         | - Integritas: Unvalidated      |
                         +--------------------------------+
                                         |
                       [Profiling & Validation Engine]
                       (Pydantic, Schema Constraints)
                                         |
                                         v
                         +--------------------------------+
                         |       SILVER / STAGING         |
                         | (Transformed Canonical Tidy)   |
                         | - Schema-on-Write di-enforce   |
                         | - Deduping, Tipe Data Strict   |
                         +--------------------------------+
                                         |
                          [Agregasi Bisnis & Dim Modeling]|
                          (dbt / Polars / DuckDB Engine)  |
                                         |
                                         v
                         +--------------------------------+
                         |         GOLD / MARTS           |
                         | (Data Warehouse / Star Schema) |
                         | - Fact Tables, Dimension Tables|
                         | - Agregasi Metrik Teroptimasi  |
                         +--------------------------------+
                                   |            |
                     +-------------+            +-------------+
                     v                                        v
          [Interactive Analytics]                     [Production BI]
          (DuckDB / Jupyter / Python)               (Metabase / Apache Superset)
```

---

## 7. Code Implementation: Minimalist / Simple Example

Contoh berikut menunjukkan cara membedah data JSON semi-terstruktur mentah, merapikan format (*unpivoting/melting*), dan melakukan agregasi analitik dasar menggunakan `pandas`.

```python
import pandas as pd
import json

# 1. Ingestion payload semi-terstruktur mentah
raw_api_payload = """
[
    {"store_id": "JKT-01", "date": "2026-03-01", "metrics": {"revenue": 12000000, "orders": 120}},
    {"store_id": "JKT-01", "date": "2026-03-02", "metrics": {"revenue": 14500000, "orders": 135}},
    {"store_id": "BDG-01", "date": "2026-03-01", "metrics": {"revenue": 8500000, "orders": 90}},
    {"store_id": "BDG-01", "date": "2026-03-02", "metrics": {"revenue": 9200000, "orders": 95}}
]
"""

# 2. Parsing payload menjadi representasi tabular
data = json.loads(raw_api_payload)
df_nested = pd.json_normalize(data)

# Rename kolom hasil parsing nested JSON
df_nested.rename(
    columns={"metrics.revenue": "revenue", "metrics.orders": "orders"}, 
    inplace=True
)

# 3. Transformasi Tidy Data: Mengubah kolom metrik menjadi baris (Melt)
df_tidy = pd.melt(
    df_nested,
    id_vars=["store_id", "date"],
    value_vars=["revenue", "orders"],
    var_name="metric_name",
    value_name="metric_value"
)

# 4. Agregasi Analitis Deskriptif
df_summary = df_tidy.groupby(["store_id", "metric_name"])["metric_value"].agg(
    ["mean", "sum"]
).reset_index()

print("--- CANONICAL TIDY DATA ---")
print(df_tidy)
print("\n--- ANALYTICAL SUMMARY ---")
print(df_summary)
```

---

## 8. Code Implementation: Production-Grade / Practical Example

Implementasi production-grade di bawah mengintegrasikan pemrosesan streaming record demi record, validasi tipe data menggunakan `Pydantic v2`, penanganan nilai yang hilang secara eksplisit, komputasi metrik menggunakan vektorisasi `numpy`, dan pembagian kuantil analitis.

```python
from datetime import date
from typing import List, Optional, Dict, Any
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, ValidationError, field_validator


# ==========================================
# 1. DATA CONTRACT & SCHEMA SPECIFICATION
# ==========================================
class TransactionRecord(BaseModel):
    transaction_id: str = Field(..., min_length=8, max_length=64)
    customer_id: str = Field(..., min_length=4, max_length=32)
    timestamp_epoch: int = Field(..., ge=0)
    gross_amount: float = Field(..., ge=0.0)
    discount_amount: float = Field(default=0.0, ge=0.0)
    tax_amount: float = Field(default=0.0, ge=0.0)
    payment_status: str = Field(...)

    @field_validator("payment_status")
    @classmethod
    def validate_payment_status(cls, value: str) -> str:
        allowed = {"SETTLED", "PENDING", "FAILED", "CHARGED_BACK"}
        normalized = value.strip().upper()
        if normalized not in allowed:
            raise ValueError(f"Invalid payment status: {value}. Must be in {allowed}")
        return normalized

    @field_validator("discount_amount")
    @classmethod
    def validate_discount(cls, value: float, info) -> float:
        gross = info.data.get("gross_amount", 0.0)
        if value > gross:
            raise ValueError(f"Discount {value} exceeds gross_amount {gross}")
        return value


# ==========================================
# 2. PRODUCTION ANALYTICS INGESTION ENGINE
# ==========================================
class TransactionBatchPipeline:
    def __init__(self, raw_events: List[Dict[str, Any]]) -> None:
        self._raw_events = raw_events
        self._quarantine_records: List[Dict[str, Any]] = []
        self._validated_records: List[Dict[str, Any]] = []

    def execute_hygiene_phase(self) -> "TransactionBatchPipeline":
        """
        Memisahkan data valid dari anomali menggunakan skema kontrak ketat.
        Data gagal masuk ke karantina untuk auditibilitas.
        """
        for event in self._raw_events:
            try:
                validated = TransactionRecord(**event)
                self._validated_records.append(validated.model_dump())
            except (ValidationError, TypeError) as err:
                self._quarantine_records.append({
                    "raw_data": event,
                    "rejection_reason": str(err)
                })
        return self

    def transform_to_analytics_mart(self) -> pd.DataFrame:
        """
        Normalisasi data, perhitungan net value dengan vektorisasi,
        dan segmentasi kuantil untuk analitik diagnostik.
        """
        if not self._validated_records:
            return pd.DataFrame()

        # Ekstraksi ke DataFrame
        df = pd.DataFrame(self._validated_records)

        # 1. Transformasi Data Typings & Kolom Waktu
        df["transaction_time"] = pd.to_datetime(df["timestamp_epoch"], unit="s", utc=True)
        df["transaction_date"] = df["transaction_time"].dt.date
        df.drop(columns=["timestamp_epoch"], inplace=True)

        # 2. Vektoriasi Penghitungan Net Revenue
        # Net = Gross - Discount + Tax
        gross = df["gross_amount"].to_numpy(dtype=np.float64)
        discount = df["discount_amount"].to_numpy(dtype=np.float64)
        tax = df["tax_amount"].to_numpy(dtype=np.float64)
        
        df["net_amount"] = gross - discount + tax

        # 3. Filter Deterministic Domain: Hanya transaksi sukses dihitung dalam GMV
        df_settled = df[df["payment_status"] == "SETTLED"].copy()

        if df_settled.empty:
            return df_settled

        # 4. Analitik Diagnostik: Outlier Detection via Robust IQR
        q25 = np.percentile(df_settled["net_amount"], 25)
        q75 = np.percentile(df_settled["net_amount"], 75)
        iqr = q75 - q25
        upper_bound = q75 + (1.5 * iqr)
        lower_bound = np.maximum(0.0, q25 - (1.5 * iqr))

        df_settled["is_outlier"] = (df_settled["net_amount"] > upper_bound) | (
            df_settled["net_amount"] < lower_bound
        )

        # 5. Segmentasi Kuantil Menggunakan Categorical Dtype
        labels = ["Low-Value", "Mid-Value", "High-Value", "VIP"]
        df_settled["value_tier"] = pd.qcut(
            df_settled["net_amount"],
            q=4,
            labels=labels,
            duplicates="drop"
        )

        return df_settled

    @property
    def quarantine_layer(self) -> List[Dict[str, Any]]:
        return self._quarantine_records


# ==========================================
# 3. RUNTIME EXECUTION SIMULATION
# ==========================================
if __name__ == "__main__":
    payload = [
        # Transaksi Valid
        {"transaction_id": "TXN-880011-OK", "customer_id": "CUST-001", "timestamp_epoch": 1772496000, "gross_amount": 1500000.0, "discount_amount": 50000.0, "tax_amount": 145000.0, "payment_status": "SETTLED"},
        {"transaction_id": "TXN-880012-OK", "customer_id": "CUST-002", "timestamp_epoch": 1772496100, "gross_amount": 250000.0, "discount_amount": 0.0, "tax_amount": 25000.0, "payment_status": "SETTLED"},
        {"transaction_id": "TXN-880013-OK", "customer_id": "CUST-003", "timestamp_epoch": 1772496200, "gross_amount": 8900000.0, "discount_amount": 200000.0, "tax_amount": 870000.0, "payment_status": "SETTLED"},
        {"transaction_id": "TXN-880014-OK", "customer_id": "CUST-004", "timestamp_epoch": 1772496300, "gross_amount": 350000.0, "discount_amount": 10000.0, "tax_amount": 34000.0, "payment_status": "PENDING"},
        {"transaction_id": "TXN-880015-OK", "customer_id": "CUST-005", "timestamp_epoch": 1772496400, "gross_amount": 50000000.0, "discount_amount": 0.0, "tax_amount": 5000000.0, "payment_status": "SETTLED"},
        # Transaksi Anomali / Gagal Validasi
        {"transaction_id": "TXN-CORRUPT-1", "customer_id": "CUST-006", "timestamp_epoch": -100, "gross_amount": 1000.0, "payment_status": "SETTLED"}, # Invalid Epoch
        {"transaction_id": "TXN-CORRUPT-2", "customer_id": "CUST-007", "timestamp_epoch": 1772496500, "gross_amount": 100000.0, "discount_amount": 200000.0, "payment_status": "SETTLED"}, # Discount > Gross
        {"transaction_id": "TXN-CORRUPT-3", "customer_id": "CUST-008", "timestamp_epoch": 1772496600, "gross_amount": 50000.0, "payment_status": "UNKNOWN_CODE"} # Invalid Enum
    ]

    pipeline = TransactionBatchPipeline(payload).execute_hygiene_phase()
    clean_df = pipeline.transform_to_analytics_mart()

    print("=== SUMMARY RECORD DISPOSITION ===")
    print(f"Total Validated  : {len(clean_df)} valid settled transactions")
    print(f"Total Quarantined: {len(pipeline.quarantine_layer)} records rejected")

    print("\n=== ANALYTICAL DATASET PREVIEW ===")
    print(clean_df[["transaction_id", "customer_id", "net_amount", "value_tier", "is_outlier"]])

    if pipeline.quarantine_layer:
        print("\n=== QUARANTINE SAMPLE ===")
        print(f"Sample Error: {pipeline.quarantine_layer[0]['rejection_reason']}")
```

---

## 9. Step-by-Step Deep Dive

Analisis rinci alur kerja implementasi di atas:

1. **Definisi Kontrak (`TransactionRecord`)**:
   - `Pydantic BaseModel` bertindak sebagai *gatekeeper* skema analitis di layer staging.
   - Variabel numerik divalidasi dengan batas bawah absolut `ge=0.0`. Hal ini mencegah anomali matematika seperti nilai transaksi bernilai negatif yang lolos tanpa flag *refund*.
   - Menggunakan `@field_validator` untuk membatasi status pembayaran ke dalam `Set` diskrit ($O(1)$ lookup time) guna menjamin integritas referensial data.

2. **Isolasi Mutasi Melalui Karantina (*Dead-Letter Logic*)**:
   - Data yang memicu `ValidationError` tidak dibuang secara diam-diam (*silent failure*), melainkan dialihkan ke `_quarantine_records`. Hal ini memungkinkan tim data analyst mengaudit persentase *error rate* per ingestor secara presisi.

3. **Vektorisasi Penghitungan Net Revenue**:
   - Transformasi `gross - discount + tax` tidak dijalankan dengan perulangan baris (`df.apply()` atau `for row in ...`), melainkan dikonversi ke array mentah C-contiguous `numpy.float64`.
   - Pola ini memicu optimasi Single Instruction, Multiple Data (SIMD) pada CPU modern, meningkatkan throughput pemrosesan dari kisaran $\approx 10^3$ baris/detik menjadi $\approx 10^6$ baris/detik.

4. **Deteksi Outlier Menggunakan Interquartile Range (IQR)**:
   - Metrik $Q_1$ (persentil 25) dan $Q_3$ (persentil 75) dihitung secara non-parametrik, sehingga tahan terhadap distorsi ekstrem jika dibandingkan dengan pendekatan deviasi standar Z-Score ($\mu \pm 3\sigma$) pada distribusi berskew tinggi.

5. **Segmentasi Diskrit Melalui `pd.qcut`**:
   - Membagi pelanggan secara objektif ke dalam jumlah frekuensi yang sama per bin persentil ($25\%$). Format kolom diubah menjadi tipe data kategorikal (`CategoricalDtype`), yang menghemat penggunaan memori hingga 80% dibandingkan tipe `Object`/string biasa.

---

## 10. Edge Cases, Failure Modes & Mitigations

| Failure Mode / Edge Case | Dampak Teknis | Mekanisme Mitigasi |
| :--- | :--- | :--- |
| **Silent Type Coercion** | String numerik `"100"` dijumlahkan sebagai konkatenasi string `"100100"` alih-alih `200`. | Gunakan static schema validation (Pydantic/Pandera) dan hindari pembacaan raw tanpa tipe data eksplisit pada `read_csv(dtype=...)`. |
| **High Cardinality Timestamps** | `pd.to_datetime` lambat saat membaca variasi format ISO-8601 acak. | Wajibkan format UTC ISO-8601 standar atau simpan dalam format numerik Unix Epoch integer. Gunakan parameter `format='ISO8601'`. |
| **Divide-by-Zero pada Metrik Rasio**| Menghasilkan nilai `inf` atau `NaN` pada metrik persentase konversi (misal: Transaksi / Klik saat Klik = 0). | Bungkus operasi pembagian menggunakan `np.where(denominator == 0, 0.0, numerator / denominator)` secara eksplisit. |
| **Duplicate Transaction Events** | Penghitungan metrik ganda (Double-counting GMV). | Definisikan *Idempotency Key* berbasis kombinasi unik kolom `['transaction_id', 'timestamp_epoch']` dan jalankan deduplikasi sebelum transformasi. |
| **Null-Propagation pada Agregasi**| SQL `COUNT(column)` mengabaikan `NULL`, namun `COUNT(*)` menghitung `NULL`. Menghasilkan gap metrik antar dashboard. | Buat dokumentasi kamus data yang mengatur pemakaian fungsi agregasi: gunakan `COALESCE(val, 0)` sebelum operasi agregasi dilakukan. |

---

## 11. Performance Considerations & Optimization Techniques

Ketika volume data tumbuh dari *Megabyte* ke *Gigabyte/Terabyte*, pendekatan analitik di memori harus beradaptasi:

- **Pemilihan Tipe Data Memori**: 
  Secara default, pandas mengalokasikan integer sebagai `int64` (8 bytes) dan float sebagai `float64` (8 bytes). Gunakan *downcasting*:
  - Mengubah representasi string berulang menjadi `category` memangkas ukuran string pointer dari 64-bit per nilai ke integer lookup table berukuran 8-bit (`int8`).
  - Ganti `float64` ke `float32` jika presisi 6 digit desimal sudah memadai untuk metrik bisnis yang dianalisis.
- **Operasi In-Memory vs Out-of-Core**:
  - Untuk data $< 10\text{ GB}$: Eksekusi berbasis `Polars` atau `DuckDB` jauh lebih efisien dibanding `pandas` berkat arsitektur berbasis *Apache Arrow* yang mengeliminasi overhead *pointer-chasing* internal bahasa Python.
  - Untuk data $> 100\text{ GB}$: Delegasikan transformasi ke analytical data warehouse (ClickHouse, BigQuery) dan tarik hanya data hasil agregasi akhir (*pushdown computation*).
- **Hindari Algoritma Bersarang ($O(N^2)$)**:
  - Jangan pernah menggunakan iterasi bersarang untuk mencocokkan data antar dua tabel. Gunakan penggabungan hash-join terindeks ($O(N + M)$).

---

## 12. Security, Governance & Compliance Considerations

Dalam ranah enterprise modern, kepatuhan data diatur oleh standar seperti **GDPR**, **CCPA**, dan **UU PDP (Indonesia)**:

- **Pseudonimisasi Data PII**: 
  Data pengenal pribadi (*Personally Identifiable Information* seperti NIK, Nomor HP, Email) tidak boleh dibaca langsung di layer analitik. Jalankan fungsi *Cryptographic Hashing* bergaram (Salted SHA-256) pada fase ingestion:
  $$\text{Masked\_ID} = \text{HMAC-SHA256}(\text{Raw\_PII}, \text{Secret\_Salt})$$
- **Principle of Least Privilege (PoLP)**:
  - Tim analitik umum tidak boleh memiliki hak akses modifikasi skema tabel produksi (*Write/Drop*). Gunakan akun akses *Read-Only* tersendiri.
- **Audit Logging**:
  - Setiap eksekusi kueri analitik pada tabel sensitif wajib memancarkan log kueri (meliputi User, Waktu, Resource consumed, Kolom yang disentuh) untuk mendeteksi potensi exfiltrasi data internal.

---

## 13. Architectural Trade-offs & Alternatives

| Pendekatan / Pola | Keuntungan | Kerugian | Skenario Pemakaian Optimal |
| :--- | :--- | :--- | :--- |
| **Schema-on-Write** (RDBMS / Warehouses) | Integritas data terjamin 100%; kueri analitik hilir sangat terprediksi dan efisien. | Ingestion melambat; perubahan skema di sumber membutuhkan migrasi basis data yang kompleks (*schema drift friction*). | Data finansial, core billing, audit laporan tahunan. |
| **Schema-on-Read** (Data Lake / Parquet) | Ingestion sangat cepat; mampu menampung evolusi data semi-terstruktur tanpa downtime. | Beban komputasi validasi bergeser ke kueri hilir; data berisiko menjadi *data swamp* jika profiling diabaikan. | Analisis log klik web (*clickstream*), event telemetry IoT, feed integrasi eksternal. |
| **Denormalized Flat Table** | Kueri baca (*Read Query*) instan tanpa join; mudah digunakan oleh tool dashboard BI (Tableau, Looker). | Duplikasi data masif; rawan inkonsistensi saat ada entitas yang diperbarui (*update anomaly*). | Serving Layer (Gold Layer), Mart pelaporan dashboard eksekutif. |
| **Normalized (3NF)** | Menghilangkan redundansi data; integritas mutasi data operasional terjaga penuh. | Kueri analitis membutuhkan multi-table JOIN berkali-kali yang memperlambat performa agregasi OLAP. | Backend operasional transactional OLTP. |

---

## 14. Verification, Testing & Validation

Pipeline analitik harus diverifikasi menggunakan framework unit testing deterministik (misalnya `pytest`).

```python
import pytest
import pandas as pd
import numpy as np

def calculate_conversion_rate(df: pd.DataFrame) -> float:
    """Menghitung conversion rate: checkout / visit."""
    if df.empty or "visits" not in df.columns or "checkouts" not in df.columns:
        raise ValueError("Dataset tidak memiliki schema yang valid.")
    
    total_visits = df["visits"].sum()
    total_checkouts = df["checkouts"].sum()
    
    if total_visits == 0:
        return 0.0
        
    return float(total_checkouts / total_visits)

# ================= Unit Test Suite =================
def test_conversion_rate_standard():
    test_df = pd.DataFrame({"visits": [100, 200, 300], "checkouts": [10, 20, 30]})
    assert calculate_conversion_rate(test_df) == pytest.approx(0.10)

def test_conversion_rate_zero_visits():
    test_df = pd.DataFrame({"visits": [0, 0], "checkouts": [0, 0]})
    assert calculate_conversion_rate(test_df) == 0.0

def test_conversion_rate_missing_schema():
    invalid_df = pd.DataFrame({"impressions": [1000], "clicks": [50]})
    with pytest.raises(ValueError, match="schema yang valid"):
        calculate_conversion_rate(invalid_df)
```

---

## 15. Real-World Anti-Patterns to Avoid

- **Anti-Pattern 1: The Infinite Excel Pivot Mindset**
  - *Kesalahan*: Membawa data berformat laporan presentasi (*Untidy*, multi-level header, kolom pivot bulanan) langsung ke dalam data warehouse atau engine Python tanpa proses normalisasi *unpivot*.
  - *Perbaikan*: Lakukan reshape data menggunakan `.melt()` ke bentuk kanonikal sebelum masuk ke tabel basis data analitik.

- **Anti-Pattern 2: The Implicit Imputation Fallacy**
  - *Kesalahan*: Mengisi nilai kosong (*missing values*) secara otomatis dengan angka 0 atau rata-rata ($\mu$) tanpa memahami konteks bisnisnya.
  - *Perbaikan*: Klasifikasikan mekanisme kekosongan data: MCAR (*Missing Completely at Random*), MAR (*Missing at Random*), atau MNAR (*Missing Not at Random*). Nilai kosong pada diskon berarti "tanpa diskon" (dapat diisi 0), namun nilai kosong pada skor kepuasan CSAT berarti "pelanggan menolak menjawab" (tidak boleh diisi nilai artifisial tanpa flag eksplisit).

- **Anti-Pattern 3: In-Memory Explosion (`df.iterrows()`)**
  - *Kesalahan*: Melakukan iterasi per baris menggunakan `iterrows()` atau perulangan for biasa untuk manipulasi data tabular besar.
  - *Perbaikan*: Selalu gunakan operasi tervektorisasi (*vectorized operations*) dari `pandas`/`numpy` atau transformasi langsung pada mesin SQL engine.

---

## 16. Production Readiness Checklist

Setiap pipeline analisis data wajib memenuhi kriteria berikut sebelum hasilnya dirilis ke stakeholder:

- [ ] **Data Contract Verification**: Tipe data tiap kolom telah dikonfirmasi dan divalidasi dengan batasan skema yang jelas.
- [ ] **Null-Value Handling Policy**: Semua kemungkinan nilai kosong (`NaN`, `None`, `null`, `""`) ditangani secara terencana sesuai aturan bisnis.
- [ ] **Uniqueness & Primary Key Check**: Tidak ada baris terduplikasi pada level granularitas entitas primer.
- [ ] **Timestamp Standardization**: Semua data waktu menggunakan format waktu terpadu (disarankan UTC) dengan zona waktu yang konsisten.
- [ ] **Vectorized Computation**: Semua kalkulasi metrik derivatif berjalan menggunakan operasi tervektorisasi, tanpa perulangan baris secara manual.
- [ ] **Quarantine Strategy Operational**: Rekor anomali atau data rusak dialihkan ke tabel terpisah untuk keperluan investigasi, tanpa menghentikan pemrosesan batch data utama.
- [ ] **Cost Profiling Validated**: Kueri data warehouse analitis telah dioptimalkan (memanfaatkan partisi dan pengelompokan/clustering) tanpa menjalankan full scan yang tidak perlu.

---

## 17. Best Practices Summary

```
                       BEST PRACTICES ANALISIS DATA
                                    |
      +-----------------------------+-----------------------------+
      |                             |                             |
      v                             v                             v
[Arsitektur Data]            [Desain Metrik]             [Rekayasa Kode]
- Terapkan skema Tidy       - Tentukan pembanding       - Wajibkan eksekusi
  kanonikal di Bronze/        baseline sebelum            tervektorisasi (SIMD).
  Silver layer.               mengevaluasi metrik.      - Downcast tipe data
- Gunakan tipe data         - Bedakan korelasi            untuk mengefisiensikan
  kategorikal pada string     matematis dari hubungan     penggunaan memori.
  berkardinalitas rendah.     kausalitas nyata.         - Buat unit test pada
- Karantinakan data rusak   - Evaluasi metrik rasio       setiap transformasi
  ke layer terpisah.          bersama volume absolutnya.  kritis bisnis.
```

---

## 18. Industry Case Study (Failure vs Success)

### Studi Kasus: Deteksi Fraud FinTech Payment Gateway

- **Skenario Masalah**: Sebuah unicorn pembayaran digital memproses 20 juta transaksi harian. Tim analitik membuat dashboard pelaporan churn dan transaksi mencurigakan untuk mendeteksi lonjakan indikasi fraud di berbagai merchant rekanan.
- **Pendekatan Gagal (Failure Path)**: Tim analitik membaca data langsung dari replica OLTP JSON payload tanpa kontrak skema. Nilai diskon promo promosi diinput tanpa validasi batasan, di mana beberapa event memunculkan diskon lebih besar dari gross amount akibat bug di aplikasi merchant mobile. Karena pandas membaca seluruh angka ke default `float64` dan mengisi `NaN` menjadi `0`, pipeline analitik melaporkan bahwa merchant terkait membukukan margin operasional negatif secara anomali, sehingga memicu pemblokiran akun merchant secara otomatis. Kerugian bisnis: puluhan merchant tier-1 komplain keras, churn pengguna melonjak, dan valuasi reputasi tertekan.
- **Pendekatan Sukses (Success Path)**: Pipeline didesain ulang dengan arsitektur validasi bertahap:
  1. Validasi kontrak data diterapkan di layer staging menggunakan schema validator terotomasi. Transaksi dengan nilai `discount > gross` langsung diarahkan ke karantina dead-letter queue, bukan langsung diproses ke analitik.
  2. Format JSON semi-terstruktur diekstraksi ke format tabel Parquet kanonikal yang rapi.
  3. Metrik fraud dihitung menggunakan teknik persentil dinamis yang dipisah dari anomali skema payload teknis.
  Hasil: Tingkat false-positive fraud drop sebesar 94%, dan data anomali merchant dapat diinvestigasi langsung oleh tim integrasi API dalam hitungan menit tanpa merusak laporan kinerja bisnis utama.

---

## 19. Practical Exercises / Lab

### Lab 1 (Beginner): Canonical Tidy Reshaping
Diberikan tabel data penjualan triwulanan produk multi-regional berikut dalam bentuk *Untidy/Wide Format*:

```python
import pandas as pd
untidy_data = pd.DataFrame({
    "Product_ID": ["P101", "P102", "P103"],
    "Region": ["ID-JKT", "ID-SBY", "ID-BDG"],
    "2025_Q1_Revenue": [5000, 7000, 4000],
    "2025_Q2_Revenue": [5200, 7100, 4300],
    "2025_Q1_Units": [50, 70, 40],
    "2025_Q2_Units": [52, 71, 43]
})
```
- **Tugas**: Ubah dataframe tersebut menggunakan fungsi `pd.wide_to_long` atau pemanggilan berantai `.melt()` sehingga memenuhi kriteria Tidy Data dengan format kolom: `['Product_ID', 'Region', 'Year', 'Quarter', 'Revenue', 'Units']`. Pastikan tipe data kolom `Year` dan `Quarter` bertipe integer/kategorikal bersih.

### Lab 2 (Intermediate): Pipeline Profiling Data Otomatis
- **Tugas**: Bangun fungsi Python `profile_dataset(df: pd.DataFrame) -> pd.DataFrame` yang menerima DataFrame masukan arbitrer dan menghasilkan tabel ringkasan profiling analitik dengan kolom:
  1. `column_name` (nama kolom)
  2. `inferred_type` (tipe data riil: Numeric, Categorical, Datetime, Unknown)
  3. `null_percentage` (persentase data kosong terhadap total baris)
  4. `unique_cardinality` (jumlah nilai distinktif)
  5. `memory_footprint_kb` (alokasi memori aktual kolom dalam Kilobyte)

### Lab 3 (Advanced): Engine Deteksi Anomali Transaksi Berbasis Stream Batch
- **Tugas**: Buat pipeline analitik utuh yang memproses transaksi e-commerce kotor berformat list of dictionaries.
  - Implementasikan skema validasi menggunakan `Pydantic` atau *pure array validation* untuk mendeteksi string tanggal tidak valid dan nilai kuantitas negatif.
  - Pisahkan data menjadi 2 output: DataFrame Transaksi Bersih dan DataFrame Karantina yang mencatat id transaksi beserta kode kegagalannya.
  - Hitung metrik *Rolling Mean* 7-hari untuk Net Revenue per pelanggan, serta tandai transaksi pelanggan yang nilainya melebihi 3 deviasi standar di atas rolling mean historis mereka sendiri. Pipeline dilarang menggunakan fungsi loop lambat (`iterrows()` / `itertuples()`).

---

## 20. Suggested Further Reading & Official Documentation

- **Wickham, H. (2014)**. *Tidy Data*. Journal of Statistical Software, 59(10). [Link Publikasi JSS](https://www.jstatsoft.org/article/view/v059i10).
- **Codd, E. F. (1970)**. *A Relational Model of Data for Large Shared Data Banks*. Communications of the ACM, 13(6).
- **Dokumentasi Resmi Pandas**: *Essential Basic Functionality & Reshaping and Pivot Tables*. [Pandas User Guide](https://pandas.pydata.org/docs/user_guide/reshaping.html).
- **Dokumentasi Pydantic (v2)**: *Data Validation and Settings Management using Python Type Hints*. [Pydantic Documentation](https://docs.pydantic.dev/latest/).
- **Kimball, R., & Ross, M. (2013)**. *The Data Warehouse Toolkit: The Definitive Guide to Dimensional Modeling (3rd Edition)*. John Wiley & Sons.