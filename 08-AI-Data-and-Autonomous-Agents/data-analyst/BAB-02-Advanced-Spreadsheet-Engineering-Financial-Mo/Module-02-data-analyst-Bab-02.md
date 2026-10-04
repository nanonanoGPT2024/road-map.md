# BAB 02: Advanced Spreadsheet Engineering & Financial Modeling
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis dan Mengoptimalkan Calculation Engine Internal**: Membedah cara kerja Directed Acyclic Graph (DAG), dirty cell tracking, dan Multi-Threaded Recalculation (MTR) pada spreadsheet modern untuk meminimalisir latensi eksekusi workbook skala enterprise.
- **Mengimplementasikan Functional Spreadsheet Programming**: Membangun model deterministik bebas *side-effects* menggunakan fungsi dinamis modern (`LET`, `LAMBDA`, `MAP`, `REDUCE`, `SCAN`) guna mengeliminasi redundansi komputasi dan kompleksitas formula berulang.
- **Merancang Arsitektur Finansial Enterprise 3-Statement & Debt Waterfall**: Mengembangkan model terintegrasi (Income Statement, Balance Sheet, Cash Flow Statement) dengan mekanisme *circular reference breaker* yang deterministik dan matematis.
- **Mengotomatisasi Validasi & Pengujian Spreadsheet Headless**: Mengintegrasikan model spreadsheet ke dalam pipeline data modern menggunakan Python (`openpyxl` / `duckdb`) untuk continuous integration, stress testing, dan schema enforcement.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:
- **Spreadsheet Foundations**: Pemahaman absolut terkait *absolute/relative referencing* (`$A$1`), fungsi lookup modern (`XLOOKUP`, `INDEX/MATCH`), dan matriks logika boolean (`SUMIFS`, boolean masking).
- **Dasar Akuntansi & Finansial Korporat**: Mekanisme debit-kredit, struktur modal kerja (*working capital*), depresiasi aset, amortisasi pinjaman, dan integrasi laba bersih ke saldo laba ditahan (*retained earnings*).
- **Dasar Python & Data Engineering**: Pemrosesan data menggunakan Python dasar (manipulasi tipe data, IO file) dan pemahaman struktur data tabular (DataFrame/Array).

---

### 3. Concept & Internal Architecture

Spreadsheet enterprise bukan sekadar kanvas presentasi grid data, melainkan sebuah **stateful runtime engine berbasis dependency graph**. Memahami performa spreadsheet membutuhkan dekonstruksi atas tiga layer arsitektur utamanya:

```
+-----------------------------------------------------------------------+
|                         APPLICATION LAYER                             |
|         Grid Interface, Rendering Pipeline, User Input Events         |
+-----------------------------------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------+
|                    CALCULATION ENGINE RUNTIME                         |
|  +-----------------------------+     +-----------------------------+  |
|  |    Dependency Graph (DAG)   |     |    Dirty Cell State Tree    |  |
|  | Nodes: Cells/Ranges/Lambdas |     | Tracks mutated dependencies |  |
|  | Edges: Formula references   |     | Prevents global recalculate |  |
|  +-----------------------------+     +-----------------------------+  |
|                                  |                                    |
|                                  v                                    |
|  +-----------------------------------------------------------------+  |
|  |           Multi-Threaded Recalculation (MTR) Scheduler          |  |
|  | Concurrently evaluates independent branches across CPU workers  |  |
|  +-----------------------------------------------------------------+  |
+-----------------------------------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------+
|                          MEMORY & DATA LAYER                          |
|         Sparse Matrix Cell Storage, Dynamic Array Buffer Cache        |
+-----------------------------------------------------------------------+
```

#### A. Directed Acyclic Graph (DAG) & Calculation Chains
Setiap kali formula dimasukkan (misalnya `C1 = A1 + B1`), engine spreadsheet mendaftarkan `C1` sebagai *dependent* dan `A1`, `B1` sebagai *precedents*. Engine mengompilasi relasi ini ke dalam Directed Acyclic Graph (DAG). 
- Jika node tidak memiliki dependensi siklikal (*circular references*), engine melakukan *topological sort* untuk menentukan urutan eksekusi linier: 
  $$\text{Order} = [v_1, v_2, \dots, v_n] \quad \text{dimana} \quad \forall (u, v) \in E, \text{index}(u) < \text{index}(v)$$
- Adanya referensi melingkar (*circular reference*, misal `A1 = B1 + 10` dan `B1 = A1 * 0.05`) merusak sifat asiklikal graf. Engine terpaksa beralih ke mode *iterative calculation* dengan konvergensi epsilon ($\epsilon < 0.001$), yang menurunkan performa komputasi hingga ratusan kali lipat.

#### B. Dirty Cell Tracking & Multi-Threaded Recalculation (MTR)
Ketika nilai pada cell `A1` diubah, calculation engine tidak menghitung ulang seluruh sheet secara naif. Engine menandai `A1` dan seluruh subtree dependensinya di DAG sebagai **dirty**.
1. Engine memecah dependency graph menjadi rantai komputasi (*calculation chains*).
2. Rantai yang independen secara struktural dialokasikan ke thread pool yang berbeda (MTR).
3. Eksekusi thread disinkronisasi melalui *thread-safe memory fences* untuk memastikan tidak ada race condition saat dua rantai komputasi membaca cell penyangga (*intermediate values*) yang sama.

#### C. Memory Model: Sparse Matrix vs. Dynamic Array Allocator
Engine spreadsheet modern tidak mengalokasikan array 2D secara *dense* ($1.048.576 \times 16.384$ sel memori langsung dialokasikan). Engine mengimplementasikan **Sparse Matrix Storage**:
- Hanya cell yang memiliki payload (nilai, format, formula) yang mengonsumsi alokasi memori heap.
- Penggunaan formula Dynamic Array (misal: `FILTER`, `SEQUENCE`) mengalokasikan memori secara kontigu untuk blok hasil dan memproyeksikannya (*spill*) ke sel-sel tetangga. Jika blok proyeksi tersebut menabrak sel yang terisi data, engine melemparkan error `#SPILL!` untuk mencegah *in-place memory corruption*.

---

### 4. Why & What

| Dimensi | Spreadsheet Konvensional (Ad-hoc) | Spreadsheet Engineering Kelas Enterprise |
| :--- | :--- | :--- |
| **Paradigma Formula** | Nested functions dalam satu baris, hardcoded ranges (`A1:A500`). | Functional programming (`LET`, `LAMBDA`), dynamic dynamic spill ranges (`A1#`). |
| **Model Finansial** | Dependensi melingkar tidak terkontrol pada perhitungan bunga pinjaman. | *Algebraic circular breaker* atau struktur *beginning-balance debt engine*. |
| **Auditability** | Manual formula tracing via panah dependensi UI. | Pemisahan absolut data/logic/presentation; deterministic pipeline; CI validations. |
| **Skalabilitas** | Latensi hitung tinggi akibat fungsi volatil (`INDIRECT`, `OFFSET`, `NOW`). | Zero-volatile policy; dependency tree dangkal (*shallow DAG*); alokasi terindeks. |
| **Integritas Data** | Nilai input tercampur aduk dengan formula komputasi. | Input terisolasi, strict schema validation, penanganan error struktural (`#N/A`, `#VALUE!`). |

**Mengapa ini penting?** 
Di industri keuangan kuantitatif, perbankan investasi, dan analitik enterprise, kesalahan kecil pada spreadsheet dapat memicu kerugian finansial masif (misal: insiden manipulasi cell JPMorgan London Whale senilai \$6 miliar). Memperlakukan spreadsheet sebagai sistem perangkat lunak terkompilasi menjamin validitas model, stabilitas performa pada dataset masif, dan kesiapan integrasi dengan data warehouse modern.

---

### 5. How (Workflow Detail)

Arsitektur produksi spreadsheet engineering mengikuti siklus hidup modular berikut:

```
[ Data Ingestion / Staging ] 
            |
            v
[ Schema Validation & Normalization Layer ]
            |
            v
[ Core Deterministic Calculation Engine (LET/LAMBDA) ]
            |
            v
[ Financial Statements & Waterfall Module (Break Circularities) ]
            |
            v
[ Stress Test & Headless Assertion Engine (Python/CI) ]
            |
            v
[ Presentation & Reporting Consumption Layer ]
```

1. **Tahap Ingestion & Staging**: Pisahkan data input mentah (*raw transactional data*) ke dalam sheet terisolasi (`STG_DATA`). Dilarang keras menaruh formula kalkulasi bisnis di sheet ini.
2. **Normalisasi & Validasi Skema**: Gunakan Data Validation terstandarisasi. Beri label tipe data eksplisit (Integer, Float, Date ISO-8601, ISO Currency).
3. **Core Calculation Engine**: Bangun komputasi bisnis menggunakan fungsi `LET` untuk meng-cache variabel lokal dan `LAMBDA` modular untuk logika yang digunakan berulang kali. Hindari fungsi volatil.
4. **Isolasi Finansial 3-Statement**:
   - Hitung Depresiasi via Fixed Asset Schedule.
   - Hitung Working Capital via rasio perputaran (AR, AP, Inventory).
   - Eksekusi Debt Waterfall menggunakan saldo awal (*Beginning Cash & Debt*) untuk menghancurkan dependensi melingkar (*circularity loop*).
5. **Headless Audit & Assertions**: Jalankan automated test scripts melalui Python untuk menguji integritas model:
   - Balance Sheet Balance Check: $\text{Assets} - (\text{Liabilities} + \text{Equity}) = 0$.
   - Mathematical Boundaries: Debt Balance $\ge 0$, Cash $\ge 0$.

---

### 6. Analogy & Diagram ASCII

Bayangkan kalkulasi spreadsheet seperti **Pipeline Kompilasi & Eksekusi Perangkat Lunak**:

- **Cell Input** = Parameter argumen fungsi.
- **DAG Engine** = Dependency Linker & Compiler Optimizer.
- **Fungsi Volatil (`OFFSET`/`INDIRECT`)** = Memory Pointer De-reference tak berindeks yang memaksa *cache-invalidation* pada seluruh memori CPU di setiap tick clock.
- **LET/LAMBDA** = Deklarasi variabel lokal pada stack frame dan reusable micro-functions yang dievaluasi secara efisien di memori.

```
Model Tradisional (Penuh Volatilitas & Circularity):
[Cell A1 (Input)] ---> [Cell B1 (OFFSET)] ---> [Cell C1 (Interest)]
       ^                                              |
       |                                              v
       +-----------------(Circular Dependency)--------+
Result: Engine dipaksa melakukan kalkulasi berulang 100x hingga konvergen, menghabiskan thread CPU.

Model Enterprise Terstruktur (Topological Clean DAG):
[INPUT_VARS]
     |
     +--> [SCHEDULES: Depreciation & Amortization] 
     |                    |
     +--> [WORKING CAPITAL MODEL]
     |                    |
     v                    v
[INCOME STATEMENT] --> [DEBT WATERFALL (Beginning Balances Engine)]
     |                                    |
     v                                    v
[CASH FLOW STATEMENT] <-------------------+
     |
     v
[BALANCE SHEET] ---> [ASSERTION ENGINE: Assets - (Liab + Eq) == 0]
Result: DAG dieksekusi 1-pass linier via Multi-Threading (MTR), latensi < 10ms.
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Refactoring Komputasi Komisi Bertingkat dengan `LET` dan Dynamic Arrays

*Implementasi Buruk (Nested IF, Redundan, Sulit Dibaca, Lambat):*
```excel
=IF(D2>100000, D2*0.15, IF(D2>50000, D2*0.10, IF(D2>10000, D2*0.05, 0))) + IF(D2>100000, (D2-100000)*0.02, 0)
```
*Masalah*: Referensi cell `D2` diulang berkali-kali. Jika formula diterapkan ke 100.000 baris, lookup referensi sel dievaluasi ratusan ribu kali pada stack frame.

*Implementasi Enterprise Modern (`LET` + Deterministic Logic):*
```excel
=LET(
    revenue, D2:D1000,
    base_rate, XLOOKUP(revenue, {0; 10001; 50001; 100001}, {0; 0.05; 0.10; 0.15}, 0, -1),
    accelerator, IF(revenue > 100000, (revenue - 100000) * 0.02, 0),
    total_commission, (revenue * base_rate) + accelerator,
    total_commission
)
```
*Keunggulan*: Rentang `D2:D1000` dievaluasi sebagai vektor tunggal (Dynamic Array), variabel `revenue` di-cache di memori, dan komputasi dieksekusi secara instan via SIMD vectorization.

---

#### B. Practical Example: Production-Grade Debt Schedule & Cash Waterfall Engine

Komponen paling kritis dalam financial modeling adalah integrasi **Interest Expense** pada Income Statement dan **Debt Ending Balance** pada Balance Sheet tanpa menciptakan dependensi melingkar (*circular reference*).

Pendekatan enterprise yang valid: Menggunakan **Beginning Debt Balance** untuk menghitung bunga periode berjalan, atau mengimplementasikan **Algebraic Closed-Form Solver** di dalam sheet.

Berikut adalah struktur formula debt schedule 1 periode yang deterministik menggunakan `LET`:

```excel
=LET(
    beg_debt, B10,
    cfads, B25,                 /* Cash Flow Available for Debt Service */
    interest_rate, $C$4,
    min_cash_buffer, $C$5,
    cash_before_debt, B20,
    
    /* Perhitungan bunga deterministik berbasis saldo awal */
    interest_expense, beg_debt * interest_rate,
    
    /* Kapasitas pelunasan pokok: CFADS setelah melunasi bunga */
    repayment_capacity, MAX(0, cfads - interest_expense),
    
    /* Principal repayment tidak boleh melebihi saldo awal pokok hutang */
    principal_repaid, MIN(beg_debt, repayment_capacity),
    
    /* Kebutuhan borrowing baru jika kas berada di bawah batas likuiditas minimum */
    cash_deficit, MAX(0, min_cash_buffer - (cash_before_debt - interest_expense - principal_repaid)),
    new_borrowing, cash_deficit,
    
    end_debt, beg_debt - principal_repaid + new_borrowing,
    
    /* Mengembalikan baris metrik terstruktur sebagai array vertikal */
    VSTACK(interest_expense, principal_repaid, new_borrowing, end_debt)
)
```

Berikutnya, implementasikan headless validation engine menggunakan script Python untuk mengecek model spreadsheet tersebut secara otomatis:

```python
# scripts/validate_financial_model.py
import openpyxl
import sys
import numpy as np

def run_model_health_check(workbook_path: str):
    print(f"[*] Loading workbook: {workbook_path}...")
    wb = openpyxl.load_workbook(workbook_path, data_only=True)
    
    if "Model_Core" not in wb.sheetnames:
        print("[!] ERROR: Sheet 'Model_Core' tidak ditemukan!")
        sys.exit(1)
        
    sheet = wb["Model_Core"]
    
    # 1. Verifikasi Balance Sheet Identity: Assets - (Liabilities + Equity) == 0
    # Asumsi Row 50 = Total Assets, Row 65 = Total Liab + Eq, Col C hingga G (5 Tahun)
    years = ["C", "D", "E", "F", "G"]
    tolerance = 1e-4
    
    balance_errors = []
    for col in years:
        assets = sheet[f"{col}50"].value or 0.0
        liab_eq = sheet[f"{col}65"].value or 0.0
        delta = abs(assets - liab_eq)
        
        if delta > tolerance:
            balance_errors.append((col, delta, assets, liab_eq))
            
    # 2. Verifikasi Saldo Kas Tidak Boleh Negatif
    cash_errors = []
    for col in years:
        ending_cash = sheet[f"{col}25"].value or 0.0
        if ending_cash < -tolerance:
            cash_errors.append((col, ending_cash))

    # Evaluate Assertions
    print("\n--- Model Assertion Report ---")
    if balance_errors:
        print("[FAIL] Balance Sheet out of balance:")
        for col, delta, a, l in balance_errors:
            print(f"  - Periode {col}: Delta = {delta:.4f} (Assets: {a:.2f}, L+E: {l:.2f})")
    else:
        print("[PASS] Balance Sheet Integrity Verified across all forecast years.")
        
    if cash_errors:
        print("[FAIL] Cash Solvency Invalidation:")
        for col, val in cash_errors:
            print(f"  - Periode {col}: Negative Ending Cash = {val:.2f}")
    else:
        print("[PASS] Cash Solvency Cleared (No negative cash anomalies).")
        
    if balance_errors or cash_errors:
        sys.exit(1)
    
    print("\n[SUCCESS] Seluruh checks lulus standar audit enterprise.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python validate_financial_model.py <path_to_xlsx>")
        sys.exit(1)
    run_model_health_check(sys.argv[1])
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Kasus
Sebuah perusahaan Fintech B2B SaaS dengan ekspansi di 4 negara Asia Tenggara memiliki workbook model finansial *Cohort LTV/CAC & Multi-Currency Liquidity Forecast*.
- **Volume Data Input**: 150.000 baris transaksi per bulan.
- **Problem Statement**: 
  - Waktu kalkulasi sheet (*freeze time*) mencapai **48 detik** setiap kali cell input diubah.
  - Sering terjadi crash memori (Excel out-of-memory).
  - Terjadi deviasi perhitungan bunga sebesar $420.000 akibat dependensi melingkar yang tidak konvergen secara konsisten pada algoritma iterative solver bawaan spreadsheet.

#### Root Cause Analysis (RCA)
1. **Volatile Functions Abuse**: Terdapat 12.000 cell yang menggunakan fungsi `=OFFSET(...)` dan `=INDIRECT(...)` untuk mereferensikan tab cohort historis. Hal ini memaksa dependency tree mereset status dirty pada *setiap* interaksi keyboard, membatalkan optimasi MTR.
2. **Dense Range SUMIFS**: Terdapat ribuan baris formula `=SUMIFS(..., A:A, ...)` yang memindai seluruh kolom (1.048.576 sel) alih-alih rentang dinamis.
3. **Circular Reference Loop**: Cash Flow Statement mereferensikan Interest Expense dari Income Statement, sedangkan Interest Expense dihitung dari rata-rata saldo hutang:
   $$\text{Avg Debt} = \frac{\text{Beginning Debt} + \text{Ending Debt}}{2}$$
   dan $\text{Ending Debt}$ bergantung langsung pada penarikan fasilitas kredit di Cash Flow Statement.

#### Solusi Rekayasa & Arsitektur
1. **Eliminasi Total Volatilitas**: Seluruh formula `OFFSET` diganti dengan kombinasi deterministik `INDEX(..., ...):INDEX(..., ...)`.
2. **Dinamisasi Range via LET**: Rentang pencarian dibatasi secara dinamis menggunakan pointer terhitung.
3. **Pemutusan Dependensi Melingkar (Circularity Elimination)**:
   Perhitungan bunga dialihkan dari *Average Balance* ke *Beginning Balance* ditambah *Mid-Period Principal Schedule Allocation* yang ditentukan secara independen dari Cash Flow Available for Debt Service (CFADS):
   
   $$\text{Interest}_{\text{period}} = \left(\text{Debt}_{\text{begin}} \times r\right) + \left(\text{Committed Repayment} \times \frac{r}{2}\right)$$
   
   Hal ini memutus ketergantungan $\text{Debt}_{\text{end}}$ terhadap output baris bunga, mereduksi graf perhitungan menjadi strictly acyclic (DAG).

#### Hasil Implementasi
- **Calculation Latency**: Turun dari **48 detik** menjadi **0,35 detik** (peningkatan kecepatan $\sim 137\times$).
- **Memory Consumption**: Berkurang dari 1.8 GB heap memory menjadi 190 MB.
- **Auditing Integrity**: Nilai delta Balance Sheet terkunci secara presisi pada 0.00000000 across 60 bulan proyeksi.

---

### 9. Trade-offs

Setiap keputusan arsitektur pada spreadsheet engineering memiliki konsekuensi teknis langsung:

| Pilihan Arsitektural | Keuntungan (Pros) | Biaya/Konsekuensi (Cons) | Rekomendasi Kontekstual |
| :--- | :--- | :--- | :--- |
| **Beginning Balance vs. Average Balance (Debt)** | Menghilangkan circular reference secara total; eksekusi instan 1-pass deterministic. | Sedikit meremehkan (*understate*) beban bunga jika pelunasan hutang masif terjadi di awal bulan. | Wajib untuk model berskala besar; deviasi dapat dikoreksi via interval forecast lebih granular (bulanan vs tahunan). |
| **Dynamic Array Formula (`FILTER`/`SPILL`)** | Formula terpusat di satu sel; eliminasi formula duplikat; zero dead-space memori. | Rentan error `#SPILL!` jika ada sel non-kosong di area ekspansi; kompatibilitas terbatas pada engine modern. | Standar arsitektur baru. Larang user mengedit area output proyeksi. |
| **Volatile Functions (`INDIRECT`, `OFFSET`)** | Kemudahan membangun referensi dinamis ad-hoc lintas tab tanpa struktur baku. | Merusak efisiensi dependency tree; memaksa sheet hitung ulang penuh; menghancurkan multi-threading. | **Strictly Prohibited** pada arsitektur spreadsheet production. |
| **External Headless Execution (Python / DuckDB)** | Validasi skala jutaan baris data; integrasi langsung ke pipeline CI/CD; automated reporting. | Memerlukan runtime sekunder di luar lingkungan spreadsheet lokal native. | Wajib sebagai automated gatekeeper sebelum model divalidasi oleh dewan direksi/auditor eksternal. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Circular Reference Deadlock
* **Gejala**: Muncul popup warning "There are one or more circular references", hasil kalkulasi menghasilkan nilai 0 atau angka statis yang salah.
* **Akar Masalah**: Siklus tak berujung dalam DAG kalkulasi.
* **Remediasi**:
  1. Akses menu `Formulas` -> `Error Checking` -> `Circular References`.
  2. Identifikasi loop dependencies.
  3. Lakukan decoupling secara aljabar: Ubah kalkulasi target menjadi fungsi deterministik dari parameter saldo awal (*beginning balance*) atau gunakan *algebraic substitution*.

#### 2. The `#SPILL!` Collision Bug
* **Gejala**: Formula Dynamic Array (`FILTER`, `UNIQUE`, `SEQUENCE`) memunculkan error `#SPILL!`.
* **Akar Masalah**: Ada sel di jalur ekspansi array yang mengandung karakter spasi, teks tersembunyi, atau formula residual.
* **Remediasi**:
  1. Klik ikon warning di sebelah sel bermasalah, pilih `Select Obstructing Cells`.
  2. Tekan `Delete` untuk mengosongkan jalur ekspansi secara total.
  3. Beri proteksi sel (*lock cells*) pada canvas ekspansi formula.

#### 3. Floating-Point Precision Drift
* **Gejala**: Balance Sheet balance assertion berbunyi gagal (`Assets - Liab - Eq != 0`), padahal secara visual nilainya sama persis hingga dua desimal.
* **Akar Masalah**: Standar IEEE 754 Floating-Point representation menyimpan nilai biner mendekati angka riil (contoh: $0.1 + 0.2 = 0.30000000000000004$).
* **Remediasi**:
  Bungkus komputasi rekonsiliasi akhir dengan fungsi `ROUND`:
  ```excel
  =IF(ROUND(Total_Assets - (Total_Liabilities + Total_Equity), 4) = 0, "BALANCED", "UNBALANCED")
  ```

---

### 11. Best Practices (Production Checklist)

Gunakan checklist ini sebelum merilis spreadsheet finansial ke level produksi:

- [ ] **Data Independence**: Data mentah, logika kalkulasi, dan dashboard presentasi berada pada tab yang terpisah secara fisik.
- [ ] **Zero Hardcoded Numbers**: Tidak ada angka input manual yang tertanam di dalam formula (misal: dilarang `=A1 * 0.12`; gunakan `=A1 * Input_Tax_Rate`).
- [ ] **Strict Color-Coding Standards**:
  - Teks Biru (`#0000FF`): Input Manual / Asumsi mentah.
  - Teks Hitam (`#000000`): Formula internal / Kalkulasi logic.
  - Teks Hijau (`#008000`): Referensi link antar-sheet (*inter-sheet references*).
  - Background Merah Lembut: Status error / Gagal assertion audit.
- [ ] **Volatile Function Ban**: Workbook 100% bebas dari fungsi `INDIRECT`, `OFFSET`, `TODAY()`, atau `NOW()` pada computational path utama (gunakan injection parameter statis).
- [ ] **Integrity Assertion Block**: Terdapat blok tabel assertion diagnostik yang selalu menampilkan status kesehatan model (`OK` vs `FAIL`) untuk setiap periode proyeksi.
- [ ] **Headless Test Pass**: Model lolos pengujian skrip otomatis eksternal (Python sanity check) dengan exit code 0.

---

### 12. Hands-on Practice

Buatlah direktori lokal dan ikuti panduan langkah-demi-langkah berikut untuk membangun model finansial 3-statement deterministik.

#### Struktur Direktori:
```
hands-on/m02/
├── template_model.py
├── financial_engine.xlsx
└── run_assertions.py
```

#### Langkah 1: Generate Workbook melalui Python
Simpan script berikut sebagai `hands-on/m02/template_model.py` untuk mengenerate struktur spreadsheet standar FAST:

```python
# hands-on/m02/template_model.py
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

def build_production_sheet():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Financial_Engine"
    ws.views.sheetView[0].showGridLines = True

    # Styling Palettes
    header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    kpi_font = Font(name="Calibri", size=11, bold=True)
    border_thin = Border(bottom=Side(style='thin', color='D9D9D9'))
    double_bottom = Border(bottom=Side(style='double', color='000000'), top=Side(style='thin', color='000000'))

    # Headers
    ws["B2"] = "FINANCIAL PROJECTION ENGINE (DETERMINISTIC)"
    ws["B2"].font = Font(name="Calibri", size=14, bold=True, color="1F4E78")
    
    headers = ["Line Items / Financial Metric", "FY2024 (Base)", "FY2025", "FY2026", "FY2027", "FY2028"]
    for col_idx, header in enumerate(headers, start=2):
        cell = ws.cell(row=4, column=col_idx, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center" if col_idx > 2 else "left")

    # Inisialisasi Template Data Baris
    model_rows = [
        # (Row, Label, BaseVal, IsFormula, FormulaStr)
        (5, "Revenue", 1000.0, False, None),
        (6, "  Revenue Growth YoY", 0.0, False, None),
        (7, "Cost of Goods Sold (COGS)", 400.0, True, "=C5*0.4"),
        (8, "Gross Profit", None, True, "=C5-C7"),
        (9, "Operating Expenses (OPEX)", 250.0, True, "=C5*0.25"),
        (10, "Depreciation & Amortization", 50.0, False, None),
        (11, "Operating Income (EBIT)", None, True, "=C8-C9-C10"),
        (12, "Interest Expense", None, True, "=C19*0.08"),  # Interest dihitung dari Beginning Debt (C19)
        (13, "Earnings Before Taxes (EBT)", None, True, "=C11-C12"),
        (14, "Income Tax (20%)", None, True, "=MAX(0, C13*0.2)"),
        (15, "Net Income", None, True, "=C13-C14"),
        
        # Debt Schedule
        (18, "--- DEBT SCHEDULE ---", "", False, None),
        (19, "Beginning Debt Balance", 300.0, False, None),
        (20, "Less: Principal Repayment", None, True, "=MIN(C19, MAX(0, C11*0.5))"),
        (21, "Add: New Borrowing", 0.0, False, None),
        (22, "Ending Debt Balance", None, True, "=C19-C20+C21"),
        
        # Balance Sheet Minimal Assertions
        (25, "--- BALANCE SHEET DIAGNOSTICS ---", "", False, None),
        (26, "Cash & Equivalents", 150.0, True, "=150+C15+C10-C20"),
        (27, "Other Assets", 500.0, False, None),
        (28, "Total Assets", None, True, "=C26+C27"),
        (29, "Ending Debt", None, True, "=C22"),
        (30, "Retained Earnings & Equity", 350.0, True, "=350+C15"),
        (31, "Total Liabilities & Equity", None, True, "=C29+C30"),
        (32, "BALANCE CHECK (Assets - Liab&Eq)", None, True, "=C28-C31")
    ]

    for r_idx, label, val, is_formula, form in model_rows:
        ws.cell(row=r_idx, column=2, value=label)
        if not is_formula and val != "":
            ws.cell(row=r_idx, column=3, value=val)
        elif is_formula:
            ws.cell(row=r_idx, column=3, value=form)

    # Populate Projection Years (Cols D to G)
    cols = ["C", "D", "E", "F", "G"]
    for i in range(1, len(cols)):
        cur = cols[i]
        prev = cols[i-1]
        
        ws[f"{cur}5"] = f"={prev}5*(1+0.15)" # Revenue grows 15%
        ws[f"{cur}6"] = 0.15
        ws[f"{cur}7"] = f"={cur}5*0.40"
        ws[f"{cur}8"] = f"={cur}5-{cur}7"
        ws[f"{cur}9"] = f"={cur}5*0.25"
        ws[f"{cur}10"] = 50.0
        ws[f"{cur}11"] = f"={cur}8-{cur}9-{cur}10"
        ws[f"{cur}12"] = f"={cur}19*0.08" # Non-circular interest calculation
        ws[f"{cur}13"] = f"={cur}11-{cur}12"
        ws[f"{cur}14"] = f"=MAX(0, {cur}13*0.20)"
        ws[f"{cur}15"] = f"={cur}13-{cur}14"
        
        # Debt Schedule Rollforward
        ws[f"{cur}19"] = f"={prev}22" # Beg Debt = Prev End Debt
        ws[f"{cur}20"] = f"=MIN({cur}19, MAX(0, {cur}11*0.5))"
        ws[f"{cur}21"] = 0.0
        ws[f"{cur}22"] = f"={cur}19-{cur}20+{cur}21"
        
        # Balance Sheet Elements
        ws[f"{cur}26"] = f"={prev}26+{cur}15+{cur}10-{cur}20"
        ws[f"{cur}27"] = f"={prev}27"
        ws[f"{cur}28"] = f"={cur}26+{cur}27"
        ws[f"{cur}29"] = f"={cur}22"
        ws[f"{cur}30"] = f"={prev}30+{cur}15"
        ws[f"{cur}31"] = f"={cur}29+{cur}30"
        ws[f"{cur}32"] = f"=ROUND({cur}28-{cur}31, 4)"

    wb.save("hands-on/m02/financial_engine.xlsx")
    print("[+] Model created: hands-on/m02/financial_engine.xlsx")

if __name__ == "__main__":
    build_production_sheet()
```

#### Langkah 2: Eksekusi Pembangunan Workbook
Jalankan script pembuatan workbook:
```bash
mkdir -p hands-on/m02
python hands-on/m02/template_model.py
```

#### Langkah 3: Eksekusi Test Runner & Assertions
Tulis dan jalankan file `hands-on/m02/run_assertions.py`:

```python
# hands-on/m02/run_assertions.py
import openpyxl

def evaluate():
    wb = openpyxl.load_workbook("hands-on/m02/financial_engine.xlsx", data_only=False)
    sheet = wb["Financial_Engine"]
    
    # Static Formula Syntax Audit (Pastikan tidak ada formula volatile)
    disallowed_tokens = ["OFFSET(", "INDIRECT("]
    flagged = 0
    
    for row in sheet.iter_rows(values_only=False):
        for cell in row:
            if cell.data_type == 'f':
                val = str(cell.value).upper()
                for token in disallowed_tokens:
                    if token in val:
                        print(f"[!] Violation: {token} detected at {cell.coordinate}")
                        flagged += 1
                        
    if flagged == 0:
        print("[+] PASS: Zero Volatile Functions Detected in Model Core.")
    else:
        print(f"[-] FAIL: {flagged} structural violations detected.")

if __name__ == "__main__":
    evaluate()
```
```bash
python hands-on/m02/run_assertions.py
```

---

### 13. Exercise

#### Level Easy
1. Ubah rumus pencarian manual bertingkat yang menggunakan 4 tingkat `IF` bersarang menjadi bentuk modern dengan `LET` dan satu fungsi `XLOOKUP` dengan *exact match or next smaller item mode* (`match_mode = -1`).
2. Tuliskan formula assertion di sel `B1` untuk memeriksa apakah seluruh nilai di rentang `C32:G32` bernilai tepat `0`. Jika ya, tampilkan `"SYSTEM OK"`, jika tidak tampilkan `"SYSTEM DEGRADED"`.

#### Level Medium
1. Rancang formula dynamic array menggunakan `SCAN` yang menghitung *cumulative retained earnings* secara otomatis sepanjang rentang proyeksi laba bersih 10-tahun tanpa perlu men-drag formula secara manual:
   - Input Net Income: Range `C15:L15`
   - Initial Retained Earnings: `100.0`
   - Hint: Gunakan `SCAN(initial_value, array, LAMBDA(accumulator, current_val, ...))`
2. Buat skema *revolving credit line* di mana penarikan hutang otomatis terjadi jika kas akhir berada di bawah ambang batas likuiditas minimum sebesar \$50.000, namun tidak menciptakan loop referensi melingkar.

#### Level Hard
1. Buat custom function menggunakan `LAMBDA` rekursif atau kombinasi `REDUCE` bernama `WATERFALL_TIER(capital_array, hurdle_rates, carry_rates)` yang memproses skema profit sharing *Private Equity Waterfall (European style)*:
   - Menghitung alokasi modal investor vs sponsor lintas 4 hurdle tiers (Return of Capital, Preferred Return 8%, Catch-up 20%, Final Split 80/20).
   - Seluruh logika harus berada di dalam single formula block tanpa baris perantara di sheet.

---

### 14. Challenge

**Skenario**: Anda ditunjuk sebagai Principal Financial Engineer di sebuah hedge fund. Perusahaan memiliki model akuisisi LBO (*Leveraged Buyout*) berskala \$2 Miliar dengan utang multi-tranche:
1. **Senior Secured Term Loan A**: Bunga SOFR + 2.5%, amortisasi 7% per tahun.
2. **Mezzanine Debt**: Bunga 10% Cash + 4% PIK (*Payment-in-Kind*, di mana bunga dikapitalisasi menambah saldo pokok pinjaman).
3. **Revolving Credit Facility**: Bunga SOFR + 3.0%, digunakan secara otomatis jika ada *cash deficit*.

**Tantangan**:
Bangun arsitektur kalkulasi spreadsheet deterministik yang:
- Menghitung seluruh amortisasi, kas minimum, dan penarikan revolver secara akurat tanpa mengaktifkan mode *Iterative Calculation* (Circular Reference must be zero).
- Mengintegrasikan mekanisme simulasi Monte Carlo headless via Python yang menyuntikkan 10.000 jalur volatilitas suku bunga SOFR dan memetakan probabilitas terjadinya *Debt Covenant Breach* (saat rasio $\text{Total Debt} / \text{EBITDA} > 4.5\times$).
- Seluruh pipeline assertion harus terintegrasi dalam script CI terminal tunggal yang mengembalikan status lolos/gagal secara otomatis.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic (5 Soal)

1. Apa dampak mendasar terhadap calculation engine saat fungsi volatil seperti `OFFSET` atau `INDIRECT` dieksekusi di spreadsheet?
   - A. Menurunkan konsumsi RAM dengan menghapus alokasi cache.
   - B. Mematikan fitur MTR dan memaksa kalkulasi ulang seluruh dependency chain di setiap interaksi sheet.
   - C. Mengubah matriks komputasi menjadi *dense buffer* permanen.
   - D. Mengubah formula menjadi teks statis secara otomatis.
   *Jawaban*: **B**. Engine menganggap sel berstatus *dirty* permanen di setiap trigger cycle.

2. Apa fungsi utama fungsi `LET` dalam spreadsheet engineering modern?
   - A. Membuat sheet menjadi read-only bagi user publik.
   - B. Mengalokasikan variabel lokal dalam memory scope formula untuk menghindari evaluasi sub-ekspresi berulang.
   - C. Memisahkan teks secara otomatis berdasarkan delimitator string.
   - D. Menghubungkan spreadsheet langsung ke server database SQL.
   *Jawaban*: **B**. Mengurangi beban CPU dan mempercepat evaluasi formula berulang.

3. Apa arti dari error `#SPILL!` pada Excel Dynamic Arrays?
   - A. Tipe data yang dimasukkan ke argumen formula tidak valid.
   - B. Terjadi pembagian dengan nilai nol pada salah satu elemen array.
   - C. Terdapat konten atau format pemblokir pada rentang sel yang ingin ditempati oleh hasil proyeksi array.
   - D. Formula melampaui batas rekursi maksimum kalkulasi 1.000 iterasi.
   *Jawaban*: **C**. Jalur rendering array terhambat oleh nilai di dalam sel lain.

4. Mengapa referensi melingkar (*circular reference*) dihindari secara mutlak dalam model finansial enterprise?
   - A. Karena tidak didukung oleh file bertipe `.xlsx`.
   - B. Karena menghancurkan integritas DAG, memperlambat performa komputasi secara masif, dan menghasilkan hasil tak-deterministik.
   - C. Karena langsung menyebabkan file spreadsheet terkena korupsi data permanen.
   - D. Karena menghilangkan kemampuan spreadsheet untuk mencetak dokumen ke format PDF.
   *Jawaban*: **B**. Merusak topological sort calculation engine dan bergantung pada konvergensi semu.

5. Manakah dari pilihan berikut yang merepresentasikan kode warna standar FAST untuk sel input asumsi manual?
   - A. Font Hijau
   - B. Font Hitam
   - C. Font Biru
   - D. Font Merah
   *Jawaban*: **C**. Standar finansial global menetapkan teks biru murni untuk hardcoded inputs.

---

#### B. Pertanyaan Intermediate (5 Soal)

1. Bagaimana cara Multi-Threaded Recalculation (MTR) memetakan kalkulasi pada workbook yang memiliki dependensi kompleks?
   - *Jawaban*: Engine membangun DAG, menandai sel terdampak sebagai *dirty*, menyusun urutan evaluasi via *topological sort*, lalu membagi rantai dependensi yang secara fungsional independen ke beberapa worker thread terpisah secara paralel.

2. Sebutkan kelemahan struktural menghitung beban bunga berdasarkan $\text{Average Debt} = (\text{Beg} + \text{End})/2$ di dalam model yang memiliki fasilitas penarikan kas fleksibel!
   - *Jawaban*: Formula menciptakan *circular reference loop* karena Ending Debt bergantung pada Arus Kas Bersih (yang telah dipotong bunga), sedangkan Bunga itu sendiri dihitung dari Ending Debt.

3. Apa perbedaan alokasi memori internal antara representasi data *Sparse Matrix* dan *Dense Array* pada spreadsheet engine?
   - *Jawaban*: Sparse matrix hanya mengalokasikan heap memory untuk koordinat sel yang terisi data atau pointer logika. Dense array mengalokasikan ruang memori statis untuk seluruh grid (bahkan sel kosong), yang memboroskan RAM secara eksponensial.

4. Bagaimana cara mengonversi model amortisasi depresiasi aset multi-tahun menjadi bentuk fungsional murni tanpa tabel pembantu (*helper table*) menggunakan fungsi Dynamic Array modern?
   - *Jawaban*: Menggunakan fungsi `LAMBDA` yang digabungkan dengan `MAKEARRAY` atau `MAP`/`SCAN` terhadap parameter Capex dan useful-life matrix, menghasilkan output jadwal depresiasi dalam satu ekspresi array mandiri.

5. Apa perbedaan semantik antara fungsi `SCAN` dan `REDUCE` pada spreadsheet engineering?
   - *Jawaban*: `REDUCE` mengevaluasi array dan hanya mengembalikan satu nilai agregat skalar akhir (*folded output*), sedangkan `SCAN` mengembalikan array intermediate states yang merekam nilai akumulasi di setiap langkah iterasi.

---

#### C. Skenario Kasus Produksi (3 Kasus)

1. **Skenario 1**: 
   Workbook konsolidasi bulanan sebuah grup konglomerasi memakan waktu 3 menit setiap kali dibuka dan sering mengalami crash saat diekspor ke format headless. Saat diaudit, ditemukan banyak formula:
   `=VLOOKUP(A2, INDIRECT("'" & B2 & "'!A1:Z50000"), 10, FALSE)`
   *Pertanyaan Arsitektural*: Mengapa arsitektur ini merusak engine spreadsheet dan bagaimana solusi engineering untuk memperbaikinya tanpa mengubah layout data induk?
   *Solusi*: 
   `INDIRECT` memaksa seluruh 50.000 baris dievaluasi di setiap tick, membatalkan caching dependency DAG. Solusinya: Hapus `INDIRECT`. Gunakan struktur data relasional terkonsolidasi via Power Query / Data Model, atau gabungkan seluruh sheet transaksi ke dalam satu tab terstruktur tunggal (`FACT_TRANSACTIONS`) lalu gunakan indexing deterministik via single dynamic array: `=XLOOKUP(A2, FACT_TRANSACTIONS[ID], FACT_TRANSACTIONS[TargetCol])`.

2. **Skenario 2**: 
   Model merger & akuisisi menampilkan nilai Balance Sheet seimbang saat dianalisis di layar monitoring komputer lokal, tetapi pipeline assertion Python melaporkan failure: `AssertionError: abs(Assets - LiabEq) > 1e-4`. Nilai delta yang terbaca adalah `0.00003412`.
   *Pertanyaan Arsitektural*: Jelaskan akar masalah representasi biner yang memicu error ini dan berikan formula standar enterprise untuk menangani bug ini pada level model spreadsheet!
   *Solusi*: 
   Penyebabnya adalah floating-point precision leakage representasi IEEE 754. Angka desimal floating point tidak selalu terpetakan sempurna ke dalam fraksi biner 64-bit. Solusinya adalah menerapkan strict rounding truncation pada baris balancing check:
   `=ROUND(Total_Assets, 2) - ROUND(Total_Liabilities_Equity, 2)` dan pada validasi assert script gunakan batas toleransi eksplisit: `math.isclose(assets, liab_eq, abs_tol=1e-2)`.

3. **Skenario 3**: 
   Sebuah model DCF korporat memiliki tombol circular breaker toggle pada sel `C2` (bernilai `TRUE` atau `FALSE`). Jika diaktifkan, Interest Expense mengambil formula iterative. Pada saat diuji di environment deployment headless Linux berbasis Python menggunakan engine openpyxl, nilai proyeksi DCF selalu bernilai `#VALUE!` atau `0`.
   *Pertanyaan Arsitektural*: Mengapa openpyxl gagal menghasilkan output kalkulasi yang benar pada model berbasis circular breaker manual tersebut?
   *Solusi*: 
   `openpyxl` adalah library pembaca/penulis XML zip archive spreadsheet dan **bukan calculation engine runtime**. Library ini tidak mengevaluasi formula spreadsheet natively; ia hanya membaca nilai cache yang tersimpan (`data_only=True`). Jika workbook dimutasi via script tanpa memanggil runtime engine Excel/LibreOffice secara headless, dependency tree tidak akan pernah dievaluasi dan nilai terhitung menjadi stale/kosong. Untuk model kalkulasi aktif, eksekusi headless wajib menggunakan library dengan embedded recalculation engine (seperti `formulas`, `xlwings` dengan native process, atau mengompilasi logika spreadsheet ke Python native logic via `duckdb`/`numpy`).

---

### 16. Summary

1. **Spreadsheet sebagai Sistem Perangkat Lunak**: Spreadsheet modern harus diperlakukan dengan kaidah rekayasa perangkat lunak: dependency flow harus asiklikal (DAG), formula harus deterministik, dan arsitektur harus memisahkan data mentah dari core logic computation.
2. **Kinerja Kalkulasi Bergantung pada Struktur DAG**: Eliminasi fungsi volatil (`OFFSET`, `INDIRECT`) adalah prasyarat mutlak untuk menjaga efisiensi dirty cell tracking dan Multi-Threaded Recalculation (MTR).
3. **Pemberantasan Dependensi Melingkar**: Desain finansial kelas enterprise tidak bergantung pada iterative solver Excel. Loop antara interest expense dan cash debt waterfall wajib dipecahkan secara struktural menggunakan *beginning-balance engine* atau *algebraic closed-form formulation*.
4. **Pola Modern Functional Spreadsheet**: Sintaks mutakhir seperti `LET` dan `LAMBDA` mentransformasikan grid sel yang rapuh menjadi modul program yang bersih, modular, hemat memori (*sparse matrix efficiency*), dan dapat diaudit secara programmatic.
5. **Headless Quality Assurance**: Model finansial enterprise harus dapat divalidasi secara otomatis melalui script CI/CD eksternal guna memverifikasi integritas neraca, ambang likuiditas, dan konsistensi skema sebelum disajikan kepada stakeholder pengambil keputusan.