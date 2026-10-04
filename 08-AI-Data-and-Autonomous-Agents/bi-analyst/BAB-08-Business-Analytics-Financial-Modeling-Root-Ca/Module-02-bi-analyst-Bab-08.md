# Module 02 — Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 08: Business Analytics, Financial Modeling & Root Cause Analysis**
**Track: 08-AI-Data-and-Autonomous-Agents / BI-Analyst**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik mampu:
- Merancang dan mengimplementasikan mesin dekomposisi variansi deterministik (*Price-Volume-Mix / PVM Analysis*) berskala produksi menggunakan Python, Polars, dan DuckDB.
- Membangun *automated metric tree* berbasis Directed Acyclic Graph (DAG) untuk penelusuran akar masalah (*Root Cause Analysis* / RCA) pada metrik keuangan kompleks (EBITDA, Net Revenue, Contribution Margin).
- Mengintegrasikan algoritma atribusi dimensi (Shapley Value / Entropy-based Contribution Analysis) untuk mendeteksi deviasi anomali bisnis pada data transaksi bervolume tinggi ($>10^7$ baris).
- Mengonfigurasi arsitektur analitik terdistribusi yang menyatukan pemodelan keuangan berlatensi rendah dengan *pipeline* validasi data otomatis (*great_expectations* / *Soda-like assertions*).

---

## 2. Prerequisite

Peserta didik diharapkan telah menguasai:
- **Foundational Financial Metrics**: Pemahaman mutlak mengenai LTV, CAC, Gross Margin, Net Margin, ARR/MRR Churn, dan Working Capital.
- **Advanced SQL & OLAP Engine Internals**: Window functions, vectorized execution, columnar storage format (Parquet), dan *partition pruning*.
- **Modern Data Processing Engine**: Pemrograman Python tingkat lanjut berorientasi performa tinggi menggunakan Polars atau PySpark.
- **Linear Algebra & Graph Theory Dasar**: Konsep Directed Acyclic Graph (DAG) untuk perambatan metrik dan kombinatorika kontribusi.

---

## 3. Concept & Internal Architecture (Mendalam)

Analitika bisnis dan pemodelan keuangan pada skala *enterprise* bukan sekadar membuat visualisasi dashboard atau pivot tabel statis, melainkan penyediaan *deterministic compute engine* yang mampu membedah anomali performa secara instan dan matematis.

```
                           +-------------------------------------+
                           |      Semantic Metric Store          |
                           |   (DAG Metric Tree Definitions)     |
                           +------------------+------------------+
                                              |
                                              v
+------------------+       +-------------------------------------+       +------------------------+
| Bronze/Silver    |       |     Vectorized Analytics Engine     |       | Real-Time RCA Engine   |
| Parquet DataLake | ----> |   (DuckDB / Polars Micro-Core)      | ----> | - PVM Decomposition    |
| (Transactions)   |       | - Parallel Partition Scanning       |       | - Dimension Slicing    |
+------------------+       | - Zero-Copy Memory Layout (Arrow)   |       | - Anomaly Attribution  |
                           +-------------------------------------+       +-----------+------------+
                                                                                     |
                                                                                     v
                                                                         +------------------------+
                                                                         | Actionable Diagnostic  |
                                                                         | Output & Alerting      |
                                                                         +------------------------+
```

### 3.1. Anatomi Price-Volume-Mix (PVM) Decomposition
Dalam evaluasi performa finansial kuartalan ($Q_t$ versus $Q_{t-1}$), perubahan *Gross Revenue* ($\Delta R$) bukan skalar tunggal, melainkan vektor hasil interaksi multi-faktor:

$$\Delta R = R_t - R_{t-1} = \Delta \text{Price} + \Delta \text{Volume} + \Delta \text{Mix}$$

Di mana untuk setiap produk $i \in \{1, \dots, N\}$:
- **Price Effect**: Mengukur dampak murni perubahan harga per unit dengan asumsi volume konstan.
  $$\text{Price Effect}_i = V_{i, t} \times (P_{i, t} - P_{i, t-1})$$
- **Volume Effect**: Mengukur dampak perubahan total volume penjualan absolut dari portofolio.
  $$\text{Volume Effect}_i = (V_{\text{total}, t} - V_{\text{total}, t-1}) \times \frac{V_{i, t-1}}{V_{\text{total}, t-1}} \times P_{i, t-1}$$
- **Mix Effect**: Mengukur pergeseran proporsi penjualan antar-SKU (apakah bergeser ke SKU margin tinggi atau rendah).
  $$\text{Mix Effect}_i = V_{\text{total}, t} \times \left( \frac{V_{i, t}}{V_{\text{total}, t}} - \frac{V_{i, t-1}}{V_{\text{total}, t-1}} \right) \times (P_{i, t-1} - \bar{P}_{t-1})$$
  *(dengan $\bar{P}_{t-1}$ merupakan rata-rata tertimbang harga portofolio pada periode $t-1$)*.

### 3.2. Directed Acyclic Graph (DAG) Metric Engine
Metrik tingkat tinggi (seperti *Return on Equity* atau *EBITDA Margin*) dimodelkan sebagai *node* terminal pada sebuah DAG. Setiap simpul anak merepresentasikan operan matematika (penjumlahan, perkalian, rasio). 

Ketika simpul induk mengalami anomali deviasi:
$$\text{Anomaly Score} > \tau$$
Sistem melakukan *depth-first search* (DFS) berbasis gradien untuk mengisolasi cabang dengan kontribusi variansi terbesar ($\frac{\partial f}{\partial x_i} \cdot \Delta x_i$).

---

## 4. Why & What

| Dimensi | Pendekatan Konvensional (BI 1.0 / Dashboarding) | Enterprise Analytics Engine (Modern Modern BI/RCA) |
| :--- | :--- | :--- |
| **Metodologi Analisis** | *Ad-hoc slicing*, manual filtering di Tableau/PowerBI. | *Vectorized automated decomposition* (PVM & Shapley Attribution). |
| **Pola Konsumsi** | Laporan statis pasif; analis mencari sendiri anomali. | *Proactive diagnostics*; anomali dideteksi dan diatribusikan oleh *engine*. |
| **Keandalan Metrik** | Logika perhitungan tersebar di ratusan formula dashboard. | Sentralisasi *Semantic Layer* berbasis kode (DAG-driven, version-controlled). |
| **Integritas Numerik** | Sering terjadi pembagian dengan nol, *null handling* inkonsisten. | *Strict Type-safe schemas*, *Arrow-native floating precision validation*. |
| **Latensi Diagnosis** | Jam hingga harian (harus query berkali-kali). | Sub-detik pada puluhan juta baris data transaksi. |

---

## 5. How (Workflow Detail)

Arsitektur produksi RCA dan pemodelan finansial dieksekusi melalui 5 tahap terstruktur:

1. **Ingestion & Normalization Layer**: Mengambil transaksi dari *Silver Layer* (Delta/Iceberg/Parquet), menormalisasi stempel waktu ke dalam interval analitik seragam ($t_0$ dan $t_1$).
2. **Deterministic Metric Tree Execution**: Memvalidasi simpul dasar (*unit sold*, *gross unit price*, *discount*, *COGS*, *OPEX*) menggunakan kontrak data (*data contracts*).
3. **PVM Decomposition Kernel**: Menghitung matriks variansi dimensi secara paralel antar partisi *Product Family*, *Customer Segment*, dan *Geography*.
4. **Dimension Slicing & Pruning (Shapley/Top-K Driver)**: Menghitung kontribusi diferensial sub-dimensi terhadap deviasi metrik utama. Membuang dimensi yang memiliki signifikansi statistik rendah (*noise reduction*).
5. **Payload Synthesis**: Mengompilasi output diagnosis struktural ke dalam format JSON/Parquet untuk integrasi *Alert Manager* atau antarmuka analitik eksekutif.

---

## 6. Analogy & Diagram ASCII

Analogi: Metrik finansial utama (seperti *Net Profit*) dapat diibaratkan seperti tekanan darah pada sistem kardiovaskular manusia.

Jika tekanan darah turun drastis, dokter tidak memeriksa seluruh sel tubuh secara acak satu per satu. Dokter menggunakan diagram alur fisiologis (Metric DAG): memeriksa curah jantung (*Volume*), resistensi pembuluh darah perifer (*Price*), dan viskositas darah (*Mix*). Algoritma RCA adalah pemindai otomatis yang langsung melacak jalur pembuluh mana yang mengalami kebocoran.

```
+-----------------------------------------------------------------------------------+
| METRIC TREE DAG: NET PROFIT DECOMPOSITION                                         |
+-----------------------------------------------------------------------------------+
                                   [ Net Profit ]
                                    /          \
                                  (-)          (-)
                                  /              \
                          [ Gross Margin ]       [ OPEX ]
                             /        \          /   |   \
                           (+)        (-)      [R&D][S&M][G&A]
                           /            \
                    [ Revenue ]       [ COGS ]
                    /    |    \
                  (*)   (*)   (*)
                  /      |      \
             [Price]  [Volume]  [Mix]  <-- Deterministic PVM Isolator
+-----------------------------------------------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: In-Memory PVM Calculation (Polars)

Contoh dasar kalkulasi Price-Volume-Mix antara dua SKU pada dua periode berurutan.

```python
import polars as pl

# Data baseline (Period 0) dan data current (Period 1)
data = pl.DataFrame({
    "sku": ["SKU-A", "SKU-B", "SKU-A", "SKU-B"],
    "period": [0, 0, 1, 1],
    "volume": [100.0, 200.0, 120.0, 150.0],
    "price": [10.0, 15.0, 9.5, 17.0]
})

# Hitung Revenue
df = data.with_columns((pl.col("volume") * pl.col("price")).alias("revenue"))

# Pivot data untuk komputasi diferensial
pivot_df = df.pivot(
    values=["volume", "price", "revenue"],
    index="sku",
    on="period"
)

# Hitung efek PVM per SKU
pvm_summary = pivot_df.with_columns([
    (pl.col("volume_1") * (pl.col("price_1") - pl.col("price_0"))).alias("price_effect"),
    ((pl.col("volume_1") - pl.col("volume_0")) * pl.col("price_0")).alias("volume_effect"),
    (pl.col("revenue_1") - pl.col("revenue_0")).alias("total_variance")
])

print(pvm_summary.select(["sku", "price_effect", "volume_effect", "total_variance"]))
```

### 7.2. Practical Example: Enterprise-Grade Modular RCA Engine

Implementasi kelas enterprise dengan penanganan skenario skala besar, komputasi PVM matematis lengkap (termasuk *Mix Effect* berbasis portofolio), dan pencarian anomali dimensional menggunakan Polars.

```python
from dataclasses import dataclass
from typing import Dict, List, Tuple
import polars as pl
import numpy as np

@dataclass(frozen=True)
class PVMResult:
    total_delta_revenue: float
    price_effect: float
    volume_effect: float
    mix_effect: float
    decomposition_table: pl.DataFrame

class ProductionPVMEngine:
    """
    High-performance Price-Volume-Mix (PVM) Engine designed for 
    batch & micro-batch enterprise dimensional root-cause diagnostics.
    """
    def __init__(self, epsilon: float = 1e-9):
        self.epsilon = epsilon

    def compute_decomposition(
        self, 
        df: pl.DataFrame, 
        entity_col: str, 
        volume_col: str, 
        revenue_col: str, 
        period_col: str,
        t_base: int, 
        t_curr: int
    ) -> PVMResult:
        """
        Melakukan dekomposisi matematis 3-faktor PVM yang strictly additive:
        Delta Revenue = Price Effect + Volume Effect + Mix Effect
        """
        # 1. Filter dan pisahkan data per periode
        df_filtered = df.filter(pl.col(period_col).is_in([t_base, t_curr]))
        
        # Validasi schema dan input
        for col in [entity_col, volume_col, revenue_col, period_col]:
            if col not in df.columns:
                raise ValueError(f"Kolom target {col} tidak ditemukan dalam DataFrame.")

        # Aggregasi data transaksi untuk memastikan entitas unik per periode
        agg_df = df_filtered.group_by([entity_col, period_col]).agg([
            pl.col(volume_col).sum().alias("volume"),
            pl.col(revenue_col).sum().alias("revenue")
        ]).with_columns(
            (pl.col("revenue") / (pl.col("volume") + self.epsilon)).alias("avg_price")
        )

        # 2. Pivot data ke layout kolom flat
        base_df = agg_df.filter(pl.col(period_col) == t_base).rename({
            "volume": "v_base", "revenue": "r_base", "avg_price": "p_base"
        }).drop(period_col)

        curr_df = agg_df.filter(pl.col(period_col) == t_curr).rename({
            "volume": "v_curr", "revenue": "r_curr", "avg_price": "p_curr"
        }).drop(period_col)

        # Outer join untuk mengakomodasi SKU baru atau SKU yang dihentikan (churned items)
        aligned = base_df.join(curr_df, on=entity_col, how="full", coalesce=True).fill_null(0.0)

        # 3. Hitung makro metrik portofolio (Total Volume & Weighted Average Prices)
        total_v_base = aligned["v_base"].sum()
        total_v_curr = aligned["v_curr"].sum()
        total_r_base = aligned["r_base"].sum()
        
        avg_portfolio_price_base = (total_r_base / total_v_base) if total_v_base > 0 else 0.0

        # 4. Kalkulasi Vektor Efek PVM Matematika Presisi
        # Price Effect = V_curr * (P_curr - P_base)
        # Volume Effect = (Total_V_curr - Total_V_base) * (V_base / Total_V_base) * P_base
        # Mix Effect = Total_V_curr * ( (V_curr / Total_V_curr) - (V_base / Total_V_base) ) * (P_base - P_macro_base)
        
        decomp = aligned.with_columns([
            # Efek Harga
            (pl.col("v_curr") * (pl.col("p_curr") - pl.col("p_base"))).alias("price_effect"),
            
            # Efek Volume
            ((total_v_curr - total_v_base) * 
             (pl.col("v_base") / (total_v_base + self.epsilon)) * 
             pl.col("p_base")).alias("volume_effect"),
             
            # Efek Bauran (Mix)
            (pl.lit(total_v_curr) * 
             ((pl.col("v_curr") / (total_v_curr + self.epsilon)) - 
              (pl.col("v_base") / (total_v_base + self.epsilon))) * 
             (pl.col("p_base") - pl.lit(avg_portfolio_price_base))).alias("mix_effect"),
             
            # Aktual Deviasi
            (pl.col("r_curr") - pl.col("r_base")).alias("actual_delta_revenue")
        ]).with_columns(
            (pl.col("price_effect") + pl.col("volume_effect") + pl.col("mix_effect")).alias("pvm_explained_delta")
        )

        # 5. Agregasi Eksekutif
        tot_delta = float(decomp["actual_delta_revenue"].sum())
        p_eff = float(decomp["price_effect"].sum())
        v_eff = float(decomp["volume_effect"].sum())
        m_eff = float(decomp["mix_effect"].sum())

        return PVMResult(
            total_delta_revenue=tot_delta,
            price_effect=p_eff,
            volume_effect=v_eff,
            mix_effect=m_eff,
            decomposition_table=decomp.sort(by="actual_delta_revenue", descending=True)
        )

# Pipeline Demo
if __name__ == "__main__":
    # Generate simulasi 100,000 rekod transaksi
    np.random.seed(42)
    n_records = 100_000
    skus = [f"SKU_{i:03d}" for i in range(50)]
    
    mock_data = pl.DataFrame({
        "sku": np.random.choice(skus, n_records),
        "period": np.random.choice([2023, 2024], n_records, p=[0.45, 0.55]),
        "qty": np.random.exponential(scale=10, size=n_records).round(0) + 1,
        "revenue": np.random.normal(loc=500, scale=50, size=n_records).clip(50, 1000)
    })

    engine = ProductionPVMEngine()
    result = engine.compute_decomposition(
        df=mock_data,
        entity_col="sku",
        volume_col="qty",
        revenue_col="revenue",
        period_col="period",
        t_base=2023,
        t_curr=2024
    )

    print(f"--- Enterprise PVM Summary ---")
    print(f"Total Revenue Delta : ${result.total_delta_revenue:,.2f}")
    print(f"Price Effect        : ${result.price_effect:,.2f}")
    print(f"Volume Effect       : ${result.volume_effect:,.2f}")
    print(f"Mix Effect          : ${result.mix_effect:,.2f}")
    print(f"Sum Check Delta     : ${(result.price_effect + result.volume_effect + result.mix_effect):,.2f}")
    print("\nTop 5 Drivers of Variances:")
    print(result.decomposition_table.select([
        "sku", "r_base", "r_curr", "price_effect", "volume_effect", "mix_effect", "actual_delta_revenue"
    ]).head(5))
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Defisit Gross Margin $4.2M pada Perusahaan Quick-Commerce Multinational
- **Latar Belakang**: Sebuah platform Quick-Commerce dengan 12.000 SKU aktif di 85 *fulfillment centers* (dark stores) membukukan penurunan Gross Margin sebesar 280 basis points (setara defisit \$4.2 Juta) pada Q3 dibandingkan target anggaran (Budget).
- **Masalah Pendekatan Tradisional**: Tim BI manual memerlukan waktu 11 hari kerja untuk membedah data di spreadsheet dan dashboard OLAP. Dashboard hanya menunjukkan bahwa "Kategori Minuman & Susu mengalami penurunan margin", tanpa membuktikan apakah akar masalahnya adalah diskon berlebih, kenaikan ongkos pemasok, atau pergeseran preferensi konsumen.
- **Implementasi Mesin Solusi**:
  1. Dibangun *Automated Root Cause Engine* berbasis DuckDB + PyArrow di atas Lakehouse (Delta Parquet).
  2. Mengeksekusi dekomposisi 3 lapis: PVM pada Revenue $\rightarrow$ Cost Variance Decomposition pada COGS (Purchase Cost vs Logistics Waste) $\rightarrow$ Dimension Slicing pada geografi *Hub*.
- **Hasil Investigasi Otomatis (Compute Runtime: 3.4 detik)**:
  - Efek Harga (*Price Effect*): Mengindikasikan gain murni +\$1.1M (kenaikan harga katalog berhasil).
  - Efek Volume (*Volume Effect*): Mengindikasikan gain +\$0.8M (ekspansi basis pengguna baru).
  - Efek Bauran (*Mix Effect*): Mengalami kerugian dahsyat -\$6.1M!
  - **Akar Masalah Utama Terisolasi**: Konsumen secara masif beralih (*cannibalization*) dari minyak goreng kemasan premium 1-Liter bermargin 22% ke minyak goreng bersubsidi kemasan 2-Liter bermargin 2% akibat kampanye promosi bebas ongkir tanpa ambang batas minimum keranjang (*basket threshold*).
- **Aksi Finansial**: Algoritma memicu perubahan aturan keranjang dinamis (*dynamic cart thresholding*) dalam tempo 24 jam, menghentikan laju *cash bleed* seketika.

---

## 9. Trade-offs

```
                       COMPUTATIONAL SPEED
                              /\
                             /  \
                            /    \
                           /      \
                          /   *    \  Polars / In-Memory Vectorized
                         /          \ (Optimal for < 100M rows)
                        /            \
                       /              \
                      /________________\
   ALGORITHMIC COMPLEXITY           STORAGE & SYSTEM OVERHEAD
  (Shapley / Exact PVM)            (Distributed PySpark / Presto)
```

| Trade-off Dimension | Alternatif A: SQL Engine Tradisional (Contoh: Snowflake/BigQuery) | Alternatif B: Vectorized Memory-Mapped (Polars / DuckDB Arrow Engine) | Alternatif C: Algorithmic Game-Theoretic (Exact Shapley Attribution) |
| :--- | :--- | :--- | :--- |
| **Throughput & Scalability** | Skala terdistribusi masif (Petabytes); auto-scaling clustering compute. | Sangat cepat pada skala memori tunggal (hingga $\sim 500$ juta baris per node 128GB). | Lambat; eksponensial terhadap jumlah fitur ($O(2^d)$ kecuali menggunakan aproksimasi). |
| **Compute Cost** | Tinggi; scanning biaya per-query terus berjalan saat slice-and-dice berulang. | Minimum; dijalankan pada container CPU deterministik (fixed cost). | Tinggi secara utilisasi CPU; memerlukan optimasi sampling Monte-Carlo. |
| **Analytical Expressiveness** | Terbatas pada fungsi analitik SQL; sulit mengimplementasikan logika DAG iteratif. | Sangat fleksibel; native Python data-structures, graph traversal terintegrasi. | Presisi matematis atribusi variansi tertinggi tanpa korelasi bias antar-dimensi. |
| **Debugging / Maintainability**| Debugging query CTE 500 baris sangat rentan *human-error*. | Mudah di-*unit-test*, *strongly-typed schemas*, modular codebase. | Logika kompleks, sulit dijelaskan secara langsung kepada auditor finansial awam. |

---

## 10. Common Mistakes & Troubleshooting

### Kesalahan Kritis 1: The "Unbalanced Base" Fallacy (Mengabaikan SKU Hilang/Baru)
- **Gejala**: Total penjumlahan $\text{Price} + \text{Volume} + \text{Mix} \neq \Delta \text{Revenue}$ aktual. Ada residu misterius bernilai jutaan dolar.
- **Penyebab**: Menggunakan *Inner Join* antara periode $t_0$ dan $t_1$. SKU yang baru meluncur pada periode $t_1$ atau SKU yang diskontinu pada periode $t_0$ tereliminasi dari komputasi.
- **Solusi**: Wajib menggunakan `full_outer_join` dengan pengisian nilai *default* ($V=0, P=0$) dan penyesuaian khusus pada vektor *Mix* (SKU baru membawa *Mix Effect* inheren terhadap bobot rata-rata historis).

### Kesalahan Kritis 2: Pembagian dengan Nol (*Floating-point NaN Propagation*)
- **Gejala**: Nilai metrik tingkat atas menghasilkan `NaN` atau `Inf` secara tiba-tiba ketika menganalisis level dimensional mikro (*sub-branch*).
- **Penyebab**: Perhitungan harga implisit ($P = \frac{\text{Revenue}}{\text{Volume}}$) ketika transaksi memiliki volume $0$ (seperti baris penyesuaian akuntansi, *voucher credit*, atau retur barang murni).
- **Solusi**: Terapkan *safe epsilon division* atau masking kondisional secara ketat:
  ```python
  pl.when(pl.col("volume") > 0).then(pl.col("revenue") / pl.col("volume")).otherwise(0.0)
  ```

### Kesalahan Kritis 3: Simpson's Paradox pada Agregasi Hierarki Dimensi
- **Gejala**: Price effect di tingkat nasional positif, namun ketika dipecah ke seluruh 34 provinsi, seluruh provinsi bernilai negatif.
- **Penyebab**: Mengabaikan bobot volume realokasi regional antar waktu. Variansi regional bertindak sebagai *Mix Effect* agregat, bukan *Price Effect*.
- **Solusi**: Jangan pernah menjumlahkan dekomposisi PVM dimensi anak secara langsung tanpa rekonsiliasi bobot hierarki (*Nested Matrix Decomposition*).

---

## 11. Best Practices (Production Checklist)

- [ ] **Contract Validation**: Skema transaksi input telah divalidasi tipe datanya sebelum masuk ke engine RCA (pastikan kuantitas bukan tipe string, dan stempel waktu memiliki timezone yang terdefinisi).
- [ ] **Exact Additivity Guarantee**: $\sum (\text{Price} + \text{Volume} + \text{Mix}) - \Delta \text{Revenue} < 10^{-4}$ (Bebas residu matematis).
- [ ] **Cold/Warm State Separation**: Pisahkan data historis basis ($t_0$) ke dalam format *memory-mapped Parquet file* agar engine tidak memindai ulang data statis.
- [ ] **Deterministic Dimension Pruning**: Gunakan signifikansi variansi ($\frac{|\Delta \text{Metric}_d|}{\sum |\Delta \text{Metric}|} \ge 0.01$) untuk memangkas *noise* dimensi ekor panjang (*long-tail dimensions*) sebelum rendering ke dashboard/laporan.
- [ ] **Audit Trail Snapshot**: Setiap diagnosis Root Cause harus menyertakan *fingerprint hash* input data untuk validasi auditor kepatuhan finansial (SOX/Internal Audit).

---

## 12. Hands-on Practice

Simpan seluruh skrip praktikum ini di direktori: `hands-on/m02/`

### File: `hands-on/m02/setup_environment.sh`
```bash
#!/usr/bin/env bash
set -e

mkdir -p hands-on/m02/data
mkdir -p hands-on/m02/src

python -m venv hands-on/m02/.venv
source hands-on/m02/.venv/bin/activate
pip install --upgrade pip
pip install polars==0.20.10 duckdb==0.9.2 pyarrow==15.0.0 pytest==8.0.0
echo "Environment setup complete."
```

### File: `hands-on/m02/src/data_generator.py`
```python
import polars as pl
import numpy as np

def generate_enterprise_ledger(output_path: str, rows: int = 500_000):
    np.random.seed(1337)
    categories = ["Enterprise", "SME", "Consumer"]
    regions = ["APAC", "EMEA", "AMER"]
    skus = [f"SKU-{i:04d}" for i in range(200)]
    
    # Generate Period 2023 (Base)
    n_base = rows // 2
    base_df = pl.DataFrame({
        "transaction_id": [f"TX-2023-{i:07d}" for i in range(n_base)],
        "period": [2023] * n_base,
        "sku": np.random.choice(skus, n_base),
        "segment": np.random.choice(categories, n_base, p=[0.2, 0.3, 0.5]),
        "region": np.random.choice(regions, n_base),
        "volume": np.random.exponential(scale=5, size=n_base).clip(1, 100).round(0),
        "unit_cogs": np.random.uniform(10, 50, size=n_base).round(2),
        "unit_price": np.random.uniform(20, 100, size=n_base).round(2)
    })
    
    # Generate Period 2024 (Current) with intentional structural shift
    # SME volume drops, Enterprise price hikes
    n_curr = rows // 2
    curr_df = pl.DataFrame({
        "transaction_id": [f"TX-2024-{i:07d}" for i in range(n_curr)],
        "period": [2024] * n_curr,
        "sku": np.random.choice(skus, n_curr),
        "segment": np.random.choice(categories, n_curr, p=[0.35, 0.15, 0.5]), # Mix Shift
        "region": np.random.choice(regions, n_curr),
        "volume": np.random.exponential(scale=4.8, size=n_curr).clip(1, 100).round(0),
        "unit_cogs": np.random.uniform(12, 55, size=n_curr).round(2), # Inflationary pressure
        "unit_price": np.random.uniform(22, 115, size=n_curr).round(2) # Price increases
    })
    
    full_df = pl.concat([base_df, curr_df])
    full_df = full_df.with_columns([
        (pl.col("volume") * pl.col("unit_price")).alias("gross_revenue"),
        (pl.col("volume") * pl.col("unit_cogs")).alias("total_cogs")
    ]).with_columns(
        (pl.col("gross_revenue") - pl.col("total_cogs")).alias("gross_profit")
    )
    
    full_df.write_parquet(output_path)
    print(f"Synthesized {full_df.height} enterprise financial rows -> {output_path}")

if __name__ == "__main__":
    generate_enterprise_ledger("hands-on/m02/data/ledger.parquet")
```

### File: `hands-on/m02/src/rca_analyzer.py`
```python
import polars as pl
import duckdb

def run_duckdb_dimensional_rca(parquet_path: str):
    """
    Eksekusi high-performance multi-dimensional Gross Margin bridge query
    menggunakan vectorized SQL execution di DuckDB.
    """
    con = duckdb.connect()
    
    query = f"""
    WITH aggregated AS (
        SELECT 
            period,
            segment,
            region,
            SUM(volume) as total_volume,
            SUM(gross_revenue) as total_revenue,
            SUM(total_cogs) as total_cogs,
            SUM(gross_profit) as total_margin
        FROM read_parquet('{parquet_path}')
        GROUP BY period, segment, region
    ),
    pivoted AS (
        SELECT 
            segment,
            region,
            SUM(CASE WHEN period = 2023 THEN total_volume ELSE 0 END) as vol_2023,
            SUM(CASE WHEN period = 2024 THEN total_volume ELSE 0 END) as vol_2024,
            SUM(CASE WHEN period = 2023 THEN total_revenue ELSE 0 END) as rev_2023,
            SUM(CASE WHEN period = 2024 THEN total_revenue ELSE 0 END) as rev_2024,
            SUM(CASE WHEN period = 2023 THEN total_margin ELSE 0 END) as margin_2023,
            SUM(CASE WHEN period = 2024 THEN total_margin ELSE 0 END) as margin_2024
        FROM aggregated
        GROUP BY segment, region
    )
    SELECT 
        segment,
        region,
        margin_2023,
        margin_2024,
        (margin_2024 - margin_2023) as delta_margin,
        ROUND((margin_2024 / NULLIF(rev_2024, 0)) - (margin_2023 / NULLIF(rev_2023, 0)), 4) * 100 as margin_rate_diff_pct
    FROM pivoted
    ORDER BY delta_margin ASC;
    """
    
    result = con.execute(query).pl()
    print("=== DUCKDB DIMENSIONAL ROOT CAUSE MATRIX ===")
    print(result)

if __name__ == "__main__":
    run_duckdb_dimensional_rca("hands-on/m02/data/ledger.parquet")
```

---

## 13. Exercise

### Level Easy
Tuliskan satu fungsi Python menggunakan Polars untuk memvalidasi *Data Contract*: Memastikan tidak ada nilai transaksi bernilai negatif pada kolom `volume`, `unit_price`, dan `gross_revenue`. Jika ditemukan anomali, kembalikan daftar *primary key* transaksi yang korup.

### Level Medium
Bangun sistem penghitung variansi margin (*Gross Margin Bridge*) yang memisahkan deviasi laba kotor menjadi:
1. *Revenue Impact* (Dampak pergeseran omzet)
2. *Cost Inflation Impact* (Dampak kenaikan HPP/COGS per unit)

Data input diuji menggunakan dataset Parquet dari `hands-on/m02/data/ledger.parquet`.

### Level Hard
Rancang sebuah class `RecursiveMetricTree` yang menerima simpul formula berbasis string (contoh: `"EBITDA = Gross_Profit - OPEX"`, `"Gross_Profit = Revenue - COGS"`). Implementasikan traversal otomatis yang menghitung turunan parsial untuk menentukan metrik terminal tingkat paling bawah yang memberikan kontribusi instabilitas deviasi terbesar (*Maximum Absolute Variance Contributor*).

---

## 14. Challenge

**Studi Kasus Sistemik**: Sebuah konglomerat SaaS B2B mengalami penurunan metrik *Net Retention Rate (NRR)* dari 118% menjadi 94% dalam 2 kuartal berturut-turut. Arsitektur data mereka memiliki 5 entitas dimensional: *Tier Paket Langganan*, *Negara Operasi*, *Cohort Kuartal Onboarding*, *Sektor Industri Klien*, dan *Channel Sales Executive*.

**Target Rekayasa**:
Bangun arsitektur analisis atribusi *non-parametric* (tanpa mengandalkan asumsi distribusi normal) yang dapat membaca raw event data log churn/downgrade ($1.2 \times 10^7$ events) dan secara deterministik mengeluarkan:
1. Kombinasi dimensi paling dominan (contoh: `Tier=Starter AND Sector=Fintech AND Channel=SelfServe`) yang bertanggung jawab atas $>60\%$ penurunan total NRR.
2. Melakukan isolasi efek secara simultan sehingga tim eksekutif dapat memisahkan antara penurunan *User Usage (Seat Churn)* dengan *Downgrade Discounting*.
3. Kode harus dieksekusi dalam tempo $< 15$ detik pada mesin virtual standar (8 vCPU, 32GB RAM).

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Konsep Dasar (Basic)
1. **Apa perbedaan konseptual mendasar antara Volume Effect dan Mix Effect dalam dekomposisi variansi pendapatan?**
   - *Jawaban*: Volume effect merepresentasikan perubahan murni skala total unit yang terjual secara absolut pada seluruh portofolio produk, sedangkan Mix effect merepresentasikan perubahan proporsi/komposisi distribusi relatif penjualan SKU yang bergeser ke arah produk dengan harga/margin lebih tinggi atau lebih rendah.

2. **Mengapa dekomposisi variansi Price-Volume-Mix wajib bersifat strictly additive?**
   - *Jawaban*: Agar hasil audit keuangan valid dan dapat diverifikasi tanpa residu misterius; penjumlahan efek Harga, efek Volume, dan efek Bauran harus bernilai persis sama dengan selisih mutlak nilai moneter antara periode aktual dan periode dasar ($\Delta R = \text{Price} + \text{Volume} + \text{Mix}$).

3. **Apa kegunaan nilai epsilon ($10^{-9}$) dalam komputasi metriks finansial berbasis data transaksi?**
   - *Jawaban*: Untuk mencegah *ZeroDivisionError* atau penyebaran nilai tak terhingga (*Inf/NaN*) pada unit data mikro yang memiliki volume transaksi nol saat kalkulasi harga implisit ($P = R / V$).

4. **Dalam visualisasi analisis keuangan eksekutif, bagan apa yang paling standar digunakan untuk menampilkan PVM?**
   - *Jawaban*: *Waterfall Chart* (Bagan Air Terjun), yang menampilkan transisi bertahap dari nilai awal periode ($t_0$) melewati penambahan atau pengurangan faktor-faktor PVM menuju nilai akhir periode ($t_1$).

5. **Apa definisi dari *Cannibalization* dalam analisis bauran produk (*Mix Analysis*)?**
   - *Jawaban*: Fenomena di mana produk baru atau produk berdiskon/bermargin rendah mengambil alih pangsa volume dari produk bermargin tinggi milik perusahaan itu sendiri, yang mengakibatkan penurunan rata-rata tertimbang margin keseluruhan.

---

### Bagian B: Analisis Menengah (Intermediate)
6. **Bagaimana penanganan SKU yang baru terdaftar pada periode $t_1$ (belum ada di $t_0$) pada perhitungan Price Effect?**
   - *Jawaban*: Karena tidak ada harga pembanding dasar ($P_{t0}$), Price Effect formal matematis adalah nol, dan seluruh nilai moneternya masuk ke dalam kombinasi penetrasi Volume dan pergeseran Mix portofolio terhadap baseline rata-rata portofolio lama.

7. **Mengapa Polars atau DuckDB secara signifikan lebih direkomendasikan daripada Pandas dalam pipeline komputasi finansial berskala puluhan juta baris?**
   - *Jawaban*: Polars dan DuckDB mengimplementasikan arsitektur *Vectorized Execution* berbasis Apache Arrow, komputasi multi-threaded otomatis pada multicore CPU, serta *memory footprint* minimal tanpa overhead *boxing/unboxing* objek Python yang lambat seperti pada arsitektur Pandas klasik.

8. **Jelaskan risiko penggunaan *mean average* alih-alih *weighted average* pada saat mengukur rata-rata harga produk di level kategori.**
   - *Jawaban*: Penggunaan *mean average* mengabaikan bobot volume penjualan aktual tiap SKU. Satu SKU langka berharga fantastis yang hanya terjual 1 unit akan mendistorsi harga rata-rata kategori, menghasilkan kalkulasi efek harga yang salah secara material (*skewed*).

9. **Apa yang dimaksud dengan perambatan gradien (*gradient traversal*) pada DAG metrik keuangan?**
   - *Jawaban*: Metode sistematis untuk menelusuri simpul metrik anak mana yang memiliki nilai turunan parsial terhadap simpul induk tertinggi dikalikan dengan deviasi aktualnya, sehingga sistem dapat langsung menandai akar masalah utama secara matematis tanpa memeriksa cabang yang tidak relevan.

10. **Bagaimana cara mencegah anomali *Simpson's Paradox* ketika melakukan Root Cause Analysis multi-level?**
    - *Jawaban*: Dengan melakukan dekomposisi berbasis matriks nested hirarkis yang secara konsisten mempertahankan faktor bobot volume tingkat agregat pada setiap pemecahan dimensi anak, dan tidak menarik kesimpulan hanya dari data sub-kelompok yang terisolasi.

---

### Bagian C: Skenario Kasus Produksi
11. **Skenario 1**: *Pipeline nightly RCA* Anda mengalami *memory crash* (OOM/Out-of-Memory) saat memproses transaksi tanggal kembar (11.11) yang melonjak $10\times$ lipat. 
    - *Diagnosis & Solusi*: Script analitik memuat seluruh raw data langsung ke satu DataFrame Polars in-memory. Solusinya adalah mengubah metode pembacaan menjadi *lazy scan* (`pl.scan_parquet()`), menerapkan *projection pushdown* (hanya ambil kolom: sku, qty, amount, timestamp), dan memanfaatkan *streaming mode* (`.collect(streaming=True)`) atau mendelegasikannya ke DuckDB out-of-core engine yang dapat menumpahkan memori berlebih ke disk secara teratur.

12. **Skenario 2**: Analis Keuangan melaporkan bahwa total Volume Effect bernilai negatif, padahal secara riil jumlah unit produk yang terjual naik 15%.
    - *Diagnosis & Solusi*: Terjadi kesalahan implementasi formula. Formula yang digunakan analis adalah $(V_{i,t} - V_{i,t-1}) \times P_{i,t-1}$ pada masing-masing produk (ini adalah formula volume mentah yang menggabungkan volume dan mix). Pada PVM 3-faktor standar, total Volume Effect harus murni mencerminkan laju portofolio makro: $(\sum V_t - \sum V_{t-1}) \times \bar{P}_{t-1}$. Jika implementasinya salah, pergeseran portofolio SKU murah akan mengontaminasi kalkulasi volume global.

13. **Skenario 3**: Sebuah metrik komposit `LTV/CAC Ratio` tiba-tiba bernilai negatif pada laporan harian, memicu alarm kepanikan di tingkat eksekutif C-Level.
    - *Diagnosis & Solusi*: Terjadi anomali data di mana CAC (Customer Acquisition Cost) bernilai sedikit negatif akibat adanya penyesuaian kredit diskon vendor iklan (*ad-spend rebate*) yang dicatat secara mendadak pada hari tersebut, atau terjadi pembagian saat CAC bernilai nol. Solusi arsitektural: Menerapkan layer *Circuit Breaker* dan *Data Contract Assertion* sebelum komputasi rasio; jika penyebut $\le 0$, isolasi rekod ke tabel karantina dan bekukan perambatan metrik otomatis sambil menyalakan peringatan *Data Quality Issue*, bukan membunyikan peringatan *Business Crisis*.

---

## 16. Summary

- **Dekomposisi Deterministik**: Analitika bisnis modern mengandalkan model dekomposisi variansi matematis presisi (seperti PVM) untuk menggantikan spekulasi subjektif dalam membedah fluktuasi finansial.
- **Isolasi 3-Faktor Fundamental**: Perubahan omzet atau laba selalu dapat dipisahkan secara murni menjadi: intervensi harga (*Price*), skala portofolio murni (*Volume*), dan dinamika pergeseran preferensi keranjang (*Mix*).
- **Arsitektur Berkecepatan Tinggi**: Menggabungkan penyimpanan terstruktur berbasis Parquet dengan *vectorized query execution engine* (Polars/DuckDB) memungkinkan diagnosa anomali data bernilai miliaran baris diselesaikan dalam hitungan detik.
- **Operasionalisasi Berkelanjutan**: Sistem Root Cause Analysis yang matang memerlukan integrasi kontrak data (*Data Contracts*), validasi pencegahan pembagian nol, dan automasi *alerting* cerdas yang berorientasi langsung pada aksi mitigasi finansial.