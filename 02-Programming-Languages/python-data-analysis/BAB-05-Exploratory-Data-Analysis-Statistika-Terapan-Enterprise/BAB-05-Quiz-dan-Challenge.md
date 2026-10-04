# BAB 05: Quiz, Challenge, & Knowledge Check
**Exploratory Data Analysis & Statistika Terapan Enterprise**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Kegagalan Statistik Ringkasan Klasik
Jelaskan fenomena *Anscombe's Quartet* dan *Datasaurus Dozen* dalam konteks pipeline machine learning modern. Mengapa mengandalkan mean, varians, dan koefisien korelasi Pearson secara eksklusif dapat meloloskan fitur yang rusak (*silent data corruption*) ke tahap *feature store*, dan bagaimana visualisasi diagnostik multivariat mengatasinya?

### Soal 1.2: Batasan Central Limit Theorem (CLT) pada Distribusi Fat-Tailed
Dalam metrik performa sistem (seperti network latency atau monetary transaction volume), distribusi data hampir selalu bersifat *heavy-tailed* (misal: Log-Normal, Pareto). Mengapa aplikasi Central Limit Theorem (CLT) untuk penentuan *confidence interval* rata-rata dapat menghasilkan estimasi risiko yang sangat bias (*underestimation of tail risk*), dan mengapa parameter non-parametrik atau *extreme value theory* (EVT) lebih diutamakan?

### Soal 1.3: Simpson's Paradox dalam Analisis Cohort A/B Testing
Uraikan bagaimana *Simpson's Paradox* dapat membalikkan kesimpulan statistik dari uji A/B testing skala enterprise (misal: konversi fitur checkout baru). Apa mekanisme matematis di balik agregasi data yang menyembunyikan efek sub-populasi, dan prosedur stratifikasi apa yang wajib dijalankan saat EDA untuk memitigasinya?

### Soal 1.4: Mekanisme Missing Data (MCAR, MAR, MNAR) dan Bias Estimasi
Bedakan secara matematis antara *Missing Completely at Random* (MCAR), *Missing at Random* (MAR), dan *Missing Not at Random* (MNAR). Jika sebuah pipeline menerapkan *mean/median imputation* secara default pada kolom fitur yang berstatus MNAR (misal: user berpendapatan tinggi sengaja mengosongkan isian gaji), jelaskan dampak sistematisnya terhadap varians data dan koefisien regresi hilir.

### Soal 1.5: Robust Statistics: MAD vs IQR vs Standar Deviasi
Bandingkan efisiensi statistik dan *breakdown point* antara Standar Deviasi ($\sigma$), *Interquartile Range* (IQR), dan *Median Absolute Deviation* (MAD). Dalam kondisi anomali ekstrem (data terkontaminasi hingga 20-30% pencilan akibat malfungsi sensor IoT), mengapa MAD secara teoritis dan empiris lebih superior dibanding IQR untuk standarisasi fitur (*robust scaling*)?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Numerically Stable Variance Computation (Welford’s Algorithm)
Implementasi naive dari varians sampel menggunakan formula $\text{Var}(X) = \frac{1}{N}\sum X^2 - (\bar{X})^2$ rentan terhadap *catastrophic cancellation* akibat keterbatasan representasi IEEE 754 floating-point. Uraikan bagaimana algoritma Welford menyelesaikan masalah ini secara iteratif pada data streaming dengan kompleksitas memori $\mathcal{O}(1)$ dan kestabilan numerik yang presisi.

### Soal 2.2: Algoritma Kuantil dan Interpolasi pada Data Diskret/Sparse
Fungsi `pandas.DataFrame.quantile()` dan `numpy.percentile()` menyediakan beberapa metode estimasi kuantil (misal: metode 7 secara default vs metode 1-9 R-style). Jelaskan bagaimana perbedaan metode interpolasi (`linear`, `lower`, `nearest`, `midpoint`) mempengaruhi penentuan ambang batas anomali (P99/P99.9) pada data integer sparse berskala besar, serta mengapa T-Digest atau DDSketch dibutuhkan pada sistem terdistribusi.

### Soal 2.3: Kerapuhan Uji Hipotesis Sampel Masif (The Large $N$ Problem)
Saat melakukan uji normalitas (seperti *Shapiro-Wilk* atau *Kolmogorov-Smirnov*) atau uji perbandingan distribusi pada dataset enterprise berukuran $N > 10^7$, nilai $p$-value hampir selalu bernilai $0.0000$ (menolak $H_0$). Debug akar permasalahan metodologis ini. Metrik statistik apa (*effect size*, Cohen's $d$, Wasserstein distance, Population Stability Index) yang harus digunakan menggantikan $p$-value untuk pengambilan keputusan teknis?

### Soal 2.4: Bottleneck Memori Vektorisasi Bootstrapping
Seorang data engineer mencoba menghitung selang kepercayaan 95% untuk P95 latency dengan metode non-parametric bootstrap ($B = 10.000$ iterasi) menggunakan matriks NumPy berukuran $(10000, 10^6)$ elemen float64 secara ter-vektorisasi penuh. Kode tersebut mengalami crash seketika karena *Out-Of-Memory* (OOM). Hitung kebutuhan memori dari array tersebut dan rancang arsitektur eksekusi bootstrap berbasis *chunking* atau *generator streaming* yang membatasi konsumsi RAM di bawah 500 MB.

### Soal 2.5: Degenerasi Matriks Kovarians pada Multikolinearitas Tinggi
Ketika melakukan deteksi korelasi multivariat antar ratusan fitur numerik melalui invers matriks kovarians $\mathbf{\Sigma}^{-1}$ (misalnya untuk menghitung jarak Mahalanobis), sistem melempar error `LinAlgError: Singular matrix` atau menghasilkan nilai determinan yang mendekati nol ($< 10^{-15}$). Jelaskan mekanisme algebra linear dari kondisi *ill-conditioned matrix* ini dan bagaimana regularisasi *Ledoit-Wolf shrinkage* memulihkan stabilitas estimasi kovarians.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Bottleneck Otomasi Profiling Data Skala Besar
* **Konteks:** Perusahaan fintech menjalankan cron job harian yang mengeksekusi library visual EDA otomatis (*profiling tool*) terhadap tabel snapshot transaksi berukuran 85 GB (berisi 120 juta baris dan 80 kolom) pada mesin instance AWS EC2 bertipe `r5.4xlarge` (128 GB RAM).
* **Insiden:** Job tersebut selalu terbunuh oleh Linux OOM Killer pada tahap kalkulasi korelasi Pearson/Spearman dan interaksi spasial pasangan variabel.
* **Pertanyaan Diagnostik:**
  1. Identifikasi komponen komputasi internal pada automated profiling tools yang memiliki kompleksitas waktu $\mathcal{O}(M^2 \cdot N)$ dan memori $\mathcal{O}(N \cdot M)$ sehingga menghabiskan RAM secara eksponensial.
  2. Rancang strategi arsitektur profiling data alternatif tanpa mengubah infrastruktur server, menggunakan teknik *statistical sampling validation* (misal: Cochran’s formula / Hoeffding’s Inequality) untuk menentukan ukuran sampel minimum yang secara statistik mempertahankan akurasi distribusi dengan tingkat keyakinan 99% dan margin error 1%.
  3. Bagaimana mengalihkan kalkulasi metrik ringkasan (histogram, kuantil, cardinality) langsung ke engine pemrosesan berbasis chunk/out-of-core (seperti DuckDB atau Polars streaming engine)?

### Skenario B: Integritas Data & Covariate Shift Akibat Event Flash Sale
* **Konteks:** Model fraud detection e-commerce mengalami lonjakan *False Positive Rate* (FPR) sebesar 450% dalam 2 jam pertama *Midnight Flash Sale*, mengakibatkan puluhan ribu transaksi pengguna sah terblokir.
* **Gejala:** EDA darurat menunjukkan distribusi fitur volume belanja (`amount`), frekuensi checkout per menit (`trx_velocity`), dan persentase diskon (`discount_ratio`) bergeser drastis dari baseline data training historis 6 bulan terakhir.
* **Pertanyaan Diagnostik:**
  1. Bagaimana Anda membedakan secara kuantitatif apakah insiden ini merupakan *Covariate Shift* murni ($P(X)$ berubah, $P(Y|X)$ tetap) atau *Concept Drift* ($P(Y|X)$ berubah)?
  2. Implementasikan kalkulasi *Population Stability Index* (PSI) secara algoritmik. Tentukan batas ambang (*rule of thumb*) nilai PSI untuk menentukan apakah feature set harus di-recalibrate, di-retrain, atau dihentikan sementara (*fallback to rule-based engine*).
  3. Bagaimana Anda mendeteksi jika lonjakan anomali disebabkan oleh *clipping artefact* (misal: fitur numerik terpotong pada batas integer maksimum database)?

### Skenario C: Trade-off Arsitektur Offline vs Real-Time Feature Drift Monitoring
* **Konteks:** Arsitektur sistem credit scoring memiliki dua jalur: batch computing (Parquet via Spark/DuckDB untuk EDA bulanan) dan streaming ingestion (Kafka -> Flink/Redis untuk scoring real-time). Tim kepatuhan regulasi menuntut deteksi pergeseran distribusi fitur dilakukan setiap 5 menit dengan latensi agregasi $< 3$ detik.
* **Trade-off:** Menjalankan uji non-parametrik dua sampel (seperti Kolmogorov-Smirnov 2-sample) secara terus-menerus pada stream data berkecepatan 50.000 event/detik mustahil dilakukan karena komputasi sorting memakan resource CPU masif.
* **Pertanyaan Diagnostik:**
  1. Bandingkan trade-off akurasi vs latency vs resource utilization antara pendekatan sliding-window exact distribution vs approximate streaming summary algorithms (*HyperLogLog* untuk kardinalitas, *KLL/DDSketch* untuk kuantil, *Count-Min Sketch* untuk frekuensi).
  2. Jika terjadi fenomena *late-arriving data* akibat network partition pada sistem streaming, bagaimana strategi watermarking mempengaruhi validitas EDA streaming dan bagaimana mendeteksi deviasi distribusi yang disebabkan murni oleh data arrival latency daripada perubahan perilaku populasi?

---

## 4. Chapter Challenge

### Tantangan Praktis: Enterprise Automated Data Drift Engine & Streaming EDA Profiler

#### Deskripsi Masalah
Dalam ekosistem production machine learning, data tabular rentan terhadap degradasi kualitas dan pergeseran distribusi (*data drift*). Library profiling bawaan seringkali tidak memadai untuk produksi karena memakan memori berlebih dan tidak mendukung update iteratif. Anda ditugaskan membangun engine inti *Exploratory Data Analysis & Statistical Drift Detection* berbasis Python murni dan NumPy/SciPy yang dapat beroperasi pada mode streaming micro-batch tanpa pernah memuat keseluruhan dataset ke dalam memori.

#### Spesifikasi Fungsional & Requirements
Buat module Python bernama `StreamingEDAEngine` dengan spesifikasi berikut:

1. **Online Statistical Accumulator:**
   * Menerima data secara bertahap (batch per batch berupa NumPy 2D array atau Pandas DataFrame).
   * Menghitung dan memperbarui metrik berikut secara online tanpa menyimpan row mentah historis:
     * Mean dan Standar Deviasi (Wajib menggunakan Welford’s Algorithm).
     * Skewness dan Kurtosis secara streaming (menggunakan *higher-order central moments* online).
     * Min, Max, dan Missing Value Counter.
   * Mengestimasi kuantil data ($P25, P50, P75, P95, P99$) menggunakan pendekatan binning berbasis histogram dinamis atau modul aproksimasi kuantil dengan error terikat ($\epsilon \le 0.01$).

2. **Statistical Drift Evaluation Engine:**
   * Memiliki method `.compare_drift(baseline_engine)` yang membandingkan instance engine saat ini (current batch/window) dengan engine baseline historis.
   * Menghitung **Population Stability Index (PSI)** untuk setiap fitur numerik menggunakan quantile-based binning (10 bin stabil dari baseline).
   * Menghitung **Wasserstein Distance** (Earth Mover's Distance) antar distribusi yang ter-aproksimasi.
   * Mengembalikan status kesehatan data: `GREEN` (PSI < 0.1), `YELLOW` (0.1 $\le$ PSI $\le$ 0.2), atau `RED` (PSI > 0.2).

3. **Robust Anomaly & Contamination Profiling:**
   * Mengidentifikasi rasio kontaminasi anomali menggunakan estimasi *Median Absolute Deviation* (MAD) yang dihitung dari distribusi aproksimasi.

#### Constraints Teknis
* **Memory Footprint:** Penggunaan memori engine harus konstan $\mathcal{O}(K \cdot B)$ di mana $K$ adalah jumlah fitur dan $B$ adalah jumlah bin/state algoritma, **bukan** $\mathcal{O}(N)$ terhadap jumlah total row. Maksimal alokasi memori instance adalah 50 MB, bahkan jika telah memproses $10^8$ baris data.
* **Dependensi:** Dilarang menggunakan library AutoML/Profiling pihak ketiga seperti `ydata-profiling`, `evidently`, atau `great-expectations`. Gunakan hanya `numpy`, `scipy`, `pandas` (hanya untuk I/O micro-batch), dan library bawaan Python standard.
* **Runtime Efficiency:** Mampu memproses throughput minimal $500.000$ baris per detik per core CPU untuk dataset dengan 20 fitur numerik.

#### Expected Output
Module harus menghasilkan dictionary/JSON report terstruktur yang merefleksikan ringkasan statistik dan diagnosis drift:
```json
{
  "total_records_processed": 5000000,
  "features": {
    "transaction_amount": {
      "mean": 142.5032,
      "std": 45.1201,
      "skewness": 2.145,
      "kurtosis": 8.651,
      "quantiles": {
        "p25": 85.12,
        "p50": 120.45,
        "p75": 180.20,
        "p99": 450.88
      },
      "missing_ratio": 0.0002,
      "drift_metrics": {
        "psi": 0.2451,
        "wasserstein_distance": 18.432,
        "status": "RED",
        "action_required": "RETRAIN_MODEL_OR_RECALIBRATE"
      }
    }
  }
}
```

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Batasan fundamental metrik statistik bivariat sederhana (Pearson) dalam mendeteksi dependensi non-linear dan struktur tersembunyi data.
- [ ] Dampak variasi sampling dan risiko *p-hacking* inadvertent saat menganalisis dataset dengan ukuran observasi raksasa ($N > 10^7$).
- [ ] Mengapa algoritma kalkulasi statistik berbasis satu kali pass (*single-pass stream*) seperti Welford wajib digunakan untuk komputasi terdistribusi dan streaming data.
- [ ] Perbedaan matematis dan konsekuensi operasional antara Covariate Shift, Prior Shift, dan Concept Drift pada data pipeline produksi.
- [ ] Teori di balik Population Stability Index (PSI) dan Wasserstein Distance sebagai metrik penentu kestabilan fitur.
- [ ] Kategori hilangnya data (MCAR, MAR, MNAR) dan bagaimana pemilihan metode imputasi dapat merusak struktur korelasi multivariat.

### Saya tidak perlu menghafal:
- [ ] Formula analitik eksak dari tabel distribusi kritis Mann-Whitney U atau Kolmogorov-Smirnov (cukup delegasikan ke pustaka `scipy.stats`).
- [ ] Sintaks parameter visualisasi styling mikroskopis (seperti warna hex palet atau format font tick label Matplotlib/Seaborn).
- [ ] Konstanta pembagi normalisasi exact untuk kalkulasi Fisher-Pearson kurtosis (cukup pahami perbedaan antara *excess kurtosis* vs *raw kurtosis*).

### Saya harus bisa melakukan:
- [ ] Menulis algoritma pemrosesan statistik online (mean, varians, kuantil aproksimasi) yang stabil secara numerik dengan penggunaan memori $\mathcal{O}(1)$.
- [ ] Mendiagnosis keberadaan *Simpson's Paradox* pada dataset bisnis terstratifikasi dan merancang visualisasi interaksi sub-grup yang membuktikannya.
- [ ] Mengukur pergeseran distribusi fitur (*data drift*) antar dua temporal window secara programatis menggunakan Python murni/NumPy.
- [ ] Menerapkan transformasi data yang tepat (Box-Cox, Yeo-Johnson, Log-transform, Quantile Transformer) berdasarkan skewness dan keberadaan nilai negatif/nol pada data.
- [ ] Melakukan profiling dataset berukuran puluhan gigabyte secara efisien tanpa mengalami crash memori (OOM) dengan memanfaatkan teknik streaming, chunking, atau database-native aggregation.