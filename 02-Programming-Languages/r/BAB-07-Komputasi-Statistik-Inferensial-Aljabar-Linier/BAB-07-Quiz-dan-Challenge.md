# BAB 07: Quiz, Challenge, & Knowledge Check
**Komputasi Statistik Inferensial & Aljabar Linier**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Dekomposisi Matriks pada OLS (`lm()`)
Jelaskan secara matematis dan algoritmik mengapa fungsi `lm()` di dalam R mengimplementasikan faktorisasi **QR Decomposition dengan Pivoting** (berbasis algoritma LINPACK/LAPACK) secara *default*, alih-alih menyelesaikan Normal Equations secara langsung via inversi matriks Cholesky ($\hat{\beta} = (X^T X)^{-1} X^T y$). Apa implikasinya terhadap *condition number* ($\kappa$) dari sistem persamaan tersebut dan bagaimana QR decomposition mencegah hilangnya presisi numerik (*loss of significance*) pada *floating-point arithmetic* IEEE 754?

### Soal 1.2: Arsitektur BLAS/LAPACK & Optimasi Komputasi
R secara *default* dikompilasi dengan pustaka referensi Netlib BLAS/LAPACK single-threaded. Analisis perbedaan arsitektur antara implementasi Netlib standar ini dengan pustaka *Optimized Hardware-Aware BLAS* (seperti OpenBLAS, Intel MKL, atau Apple Accelerate Framework). Mengapa operasi aljabar linier Level 3 (seperti perkalian matriks `GEMM`) mendapatkan peningkatan performa *order-of-magnitude* ketika dialihkan ke BLAS multi-threaded, sedangkan operasi Level 1 (`AXPY`) sering kali mengalami *bottleneck* pada *memory bandwidth* dan *thread synchronization overhead*?

### Soal 1.3: Mekanisme PRNG dan Manajemen State `.Random.seed`
Saat mengeksekusi simulasi inferensial (misalnya Bootstrap atau Uji Permutasi) menggunakan fungsi distribusi probabilitas seperti `rnorm()` atau `runif()`, bagaimana mekanisme internal R mengelola status Pseudo-Random Number Generator (PRNG)? Uraikan struktur data dari objek `.Random.seed` di dalam `.GlobalEnv`, algoritma default *Mersenne Twister* ($MT19937$), serta risiko konkurensi data jika simulasi tersebut diparalelkan tanpa penanganan stream RNG eksplisit (seperti *L'Ecuyer-CMRG*).

### Soal 1.4: Kompleksitas Semantik Operasi Matriks: `%*%` vs `crossprod()`
Jelaskan perbedaan mendasar antara pernyataan `t(X) %*% X` dan `crossprod(X)` di R ditinjau dari alokasi memori internal (*heap allocation*), mekanisme *copy-on-modify*, dan kompleksitas komputasi. Mengapa `crossprod(X, y)` jauh lebih hemat memori dan secara signifikan lebih cepat daripada `t(X) %*% y`, terutama ketika matriks $X$ memiliki dimensi baris ($n$) dalam orde jutaan?

### Soal 1.5: Inferensi Simultan dan Pengendalian Error Rate
Dalam pengujian hipotesis massal (misalnya pada studi *High-Throughput Omics* atau pengujian A/B testing multi-varian), jelaskan perbedaan teoritis dan matematis antara pengendalian **Family-Wise Error Rate (FWER)** melalui metode Bonferroni/Holm dan pengendalian **False Discovery Rate (FDR)** melalui pendekatan Benjamini-Hochberg (BH). Bagaimana implementasi internal `p.adjust()` memvektorisasi kalkulasi nilai kritis ini tanpa memerlukan loop iteratif di R?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Diagnostik Singularitas dan Multikolinearitas Sempurna
Perhatikan cuplikan output model berikut:
```r
fit <- lm(y ~ x1 + x2 + x3, data = production_data)
# Parameter estimates:
# (Intercept)   12.4
# x1             0.8
# x2             1.5
# x3              NA
```
Jelaskan secara mendalam mekanisme internal QR decomposition dengan pivoting (`dqrls` Fortran routine) yang menyebabkan R secara otomatis memberikan nilai koefisien `NA` pada `x3`. Mengapa matriks varians-kovariansi parameter `vcov(fit)` menjadi bermasalah, dan bagaimana cara mengekstrak unaliased sub-matrix secara terprogram untuk mencegah eror saat kalkulasi $t$-statistik manual?

### Soal 2.2: Anti-Pattern `solve(A)` dan Ill-Conditioned Matrices
Mengapa penggunaan sintaks `solve(A) %*% b` untuk menyelesaikan sistem linier $Ax = b$ dianggap sebagai *fatal anti-pattern* dalam komputasi numerik produksi? Jelaskan bagaimana fungsi `solve(A, b)` bekerja menggunakan faktorisasi LU tanpa secara eksplisit membentuk matriks invers $A^{-1}$. Tunjukkan bagaimana Anda mendeteksi matriks yang rentan terhadap galat pembulatan menggunakan fungsi `rcond()` dan interpretasikan batas ambang batas (*threshold*) teoritisnya berdasarkan batas presisi mesin (`.Machine$double.eps`).

### Soal 2.3: Silent Bugs Akibat Dimension Dropping
Diberikan fungsi kalkulasi statistik multivariat internal berikut:
```r
compute_mahalanobis_centroid <- function(X) {
  cov_mat <- cov(X)
  center <- colMeans(X)
  inv_cov <- solve(cov_mat)
  diff <- X - rep(center, each = nrow(X))
  # Hitung jarak kuadrat
  d2 <- rowSums((diff %*% inv_cov) * diff)
  return(d2)
}
```
Jika `X` adalah matriks berukuran $n \times p$, apa yang terjadi jika pipeline data upstream secara tidak sengaja memfilter dataset hingga menyisakan $p = 1$ fitur atau subset baris hingga $n = 1$? Identifikasi letak kegagalan akibat fitur implisit `drop = TRUE` pada R dasar, dan rekonstruksi fungsi tersebut agar *fail-safe* dan defensif terhadap degradasi dimensi.

### Soal 2.4: Sparse Matrix Architecture vs Dense Allocation
Ketika memodelkan data graf atau representasi *bag-of-words* berdimensi $100.000 \times 50.000$ dengan tingkat sparsitas 99.8%, pemanggilan fungsi `matrix()` dasar akan menyebabkan *crash* sistem (`vector memory exhausted`). Jelaskan struktur internal kelas `dgCMatrix` (Compressed Sparse Column - CSC) dari paket `Matrix` di R. Bagaimana CSC merepresentasikan data secara hemat memori menggunakan tiga vektor dasar (`@x`, `@i`, `@p`), dan pada densitas matriks berapa persen transisi komputasi dense-ke-sparse mencapai *breakeven point* terkait *computational overhead*?

### Soal 2.5: Isolasi Memory Leak pada Uji Non-Parametrik Masif
Sebuah pipeline analitik mengeksekusi uji Wilcoxon Rank-Sum atau Uji Permutasi secara sekuensial sebanyak $500.000$ kali pada potongan subset data. Meskipun setiap iterasi hanya memproses array kecil, penggunaan RAM mesin bertambah secara konstan (*memory bloat*) hingga proses di-*kill* oleh Linux Out-Of-Memory (OOM) Killer. Analisis bagaimana pembentukan formula interface (misalnya `wilcox.test(y ~ group)`) menangkap *enclosing environment* dan memory frame data historis, serta bagaimana mengubah implementasi tersebut ke level *matrix operations/vector arguments* murni untuk mengeliminasi pemanggilan *garbage collection* (GC) yang masif.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck Latensi Ekstrem pada Scoring Model GLM Skala Masif
Sebuah sistem *fraud detection* perbankan mengeksekusi pipeline *Logistic Regression* (GLM) setiap malam untuk menilai 20 juta transaksi dengan 80 variabel prediktor. Implementasi produksi saat ini:
```r
# Script batch malam hari
model <- glm(is_fraud ~ ., data = train_data, family = binomial(link = "logit"))
preds <- predict(model, newdata = test_data, type = "response")
```
Pipeline ini membutuhkan waktu 4.5 jam untuk *fitting* dan 45 menit untuk *scoring*, sering kali melanggar batasan Service Level Agreement (SLA) waktu jendela pemrosesan malam (maksimal 1.5 jam total). Profiling menunjukkan bahwa penggunaan CPU hanya 100% pada satu core (tidak terutilisasi pada mesin 64-core), dan konsumsi memori membengkak hingga $120\text{ GB}$ akibat duplikasi data frame selama evaluasi model matrix.

* **Pertanyaan Diagnostik & Solusi:**
  1. Identifikasi secara tepat letak bottleneck komputasi internal dari `glm.fit` (Iteratively Reweighted Least Squares / IRLS) saat berhadapan dengan data frame besar.
  2. Rancang arsitektur refaktorisasi komputasi untuk model ini tanpa berpindah dari ekosistem R. Rincikan penggunaan pustaka matrix tingkat rendah, optimasi BLAS multi-threading, dan bypass representasi *formula interface* ke `matrix` murni atau paket berbasis C++ (misal `fastglm` atau `RcppEigen`).
  3. Hitung estimasi optimasi memori dan akselerasi komputasi teoritis dari pendekatan baru tersebut.

---

### Skenario B: Kerusakan Integritas Data pada Matriks Covariance Non-Positive Definite
Dalam pipeline pemodelan risiko kuantitatif (*Value at Risk* / VaR Portofolio), sistem Anda menghitung matriks varians-kovariansi $\Sigma$ dari 2.500 aset finansial menggunakan data historis dengan *pairwise complete observations* (akibat perbedaan hari libur pasar antar negara):
```r
sigma <- cov(asset_returns, use = "pairwise.complete.obs")
```
Ketika sistem mengeksekusi simulasi Monte Carlo multivariat menggunakan Dekomposisi Cholesky:
```r
L <- chol(sigma)
# ERROR: the leading minor of order 842 is not positive definite
```
Sistem berhenti mendadak (*pipeline breakdown*) pada pukul 03:00 dini hari karena dekomposisi gagal.

* **Pertanyaan Diagnostik & Solusi:**
  1. Mengapa teknik estimasi kovariansi berbasis *pairwise deletion* secara matematis menghancurkan sifat *Positive Semi-Definite* (PSD) dari matriks simetris? Tunjukkan representasi nilai eigen terkecilnya ($\lambda_{\min}$).
  2. Implementasikan algoritma perbaikan terprogram (*numerical remediation*) secara *in-line* menggunakan algoritma *Higham's Nearest Correlation Matrix* (`Matrix::nearPD()`) atau *Spectral Truncation* (Eigendecomposition).
  3. Bagaimana Anda merancang unit test matematis otomatis untuk memverifikasi bahwa matriks yang diperbaiki tetap menjaga korelasi empiris asli sedekat mungkin (berdasarkan *Frobenius Norm*) namun menjamin kestabilan dekomposisi Cholesky?

---

### Skenario C: Trade-off Arsitektur Komputasi Inferensial Paralel (CPU vs Shared-Memory vs Rcpp)
Departemen analitik Anda ditugaskan membangun engine kalkulasi *Spatial Autoregressive Model* (SAR) yang memerlukan kalkulasi log-determinan dari matriks spasial berukuran $N \times N$ ($N = 100.000$ lokasi) berulang kali dalam optimasi Maximum Likelihood:
$$\ln |I_N - \rho W|$$
di mana $W$ adalah *row-standardized spatial weights matrix* (sangat jarang/sparse) dan $\rho \in (-1, 1)$ dievaluasi ribuan kali oleh *optimizer* `optim()`.

Arsitek sistem mengajukan 3 alternatif:
1. **Opsi 1**: Evaluasi via Base R paralel (`parallel::mclapply`) menggunakan dense decomposition setelah konversi.
2. **Opsi 2**: Pure Sparse Spline Cholesky via package `spatialreg` / `Matrix` (algoritma sparse Cholesky P-Pivoted dari CHOLMOD).
3. **Opsi 3**: Kompilasi rutin C++ melalui `Rcpp` yang terhubung langsung ke pustaka eksternal *SuiteSparse* / *Eigen* dengan paralelisasi OpenMP.

* **Pertanyaan Diagnostik & Solusi:**
  1. Analisis mengapa Opsi 1 adalah kegagalan arsitektur fatal ditinjau dari alokasi memori $\mathcal{O}(N^2)$ dan kompleksitas komputasi determinan dense $\mathcal{O}(N^3)$.
  2. Evaluasi Opsi 2 versus Opsi 3: Di mana letak batas *bottleneck overhead* interop R-ke-C++ jika fungsi determinan harus dievaluasi di dalam loop optimasi L-BFGS-B R?
  3. Buat keputusan arsitektur final: Pilih opsi terbaik, jelaskan *trade-off* pemeliharaan kode vs efisiensi runtime, dan sertakan strategi *caching* nilai eigen/faktorisasi simbolik (*symbolic factorization*) untuk mempercepat evaluasi $\rho$ berikutnya.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Regularized Linear Solver Engine Berstandar Enterprise
Sebagai Principal Engineer, Anda dilarang menggunakan fungsi *high-level* seperti `lm()`, `glm()`, `glmnet::glmnet()`, atau `solve()` standar untuk tugas ini. Anda diwajibkan membangun *custom engine* R berkinerja tinggi untuk menyelesaikan estimasi regresi **Ridge Regression (L2-Regularization)** dan diagnostik inferensialnya secara langsung melalui manipulasi aljabar linier LAPACK.

#### Problem:
Diberikan matriks data $X \in \mathbb{R}^{n \times p}$ dan vektor respon $y \in \mathbb{R}^n$, di mana $X$ bersifat *ill-conditioned* (multikolinearitas parah) dan memiliki ukuran moderat-ke-besar ($n = 500.000$, $p = 150$). Anda harus menghitung vektor estimasi parameter $\hat{\beta}_{\lambda}$:
$$\hat{\beta}_{\lambda} = (X^T X + \lambda I_p)^{-1} X^T y$$
serta menghitung nilai *Effective Degrees of Freedom* ($df_{\lambda}$):
$$df_{\lambda} = \text{tr}\left( X (X^T X + \lambda I_p)^{-1} X^T \right)$$
dan standar galat (*standard errors*) dari seluruh koefisien parameter untuk sekumpulan nilai regularisasi $\lambda = \{\lambda_1, \lambda_2, \dots, \lambda_k\}$.

#### Requirements:
1. **Kestabilan Numerik Tinggi**: Jangan pernah membentuk matriks $X^T X$ secara langsung jika menggunakan dekomposisi berbasis data mentah. Manfaatkan **Singular Value Decomposition (SVD)** dari matriks $X$ yang berpusat (*centered*) dan terskala (*scaled*):
   $$X = U D V^T$$
   sehingga inversi untuk berbagai variasi nilai $\lambda$ dapat dievaluasi secara instan dalam kompleksitas $\mathcal{O}(p)$ tanpa melakukan faktorisasi ulang matriks.
2. **Efisiensi Memori Ekstrem**: Matriks $U$ dari SVD ekonomi ($n \times p$) tidak boleh diduplikasi di heap memory R. Optimalkan kalkulasi $U^T y$ hanya sekali di awal proses.
3. **Diagnostik Sistem Linier**: Implementasikan kalkulasi *Condition Number* 2-norm dari sistem matriks ter-regularisasi sebagai fungsi dari $\lambda$.
4. **Standard Error Extraction**: Ekstrak nilai Standard Error dari setiap $\hat{\beta}_{\lambda, j}$ secara analitik:
   $$\widehat{\text{Var}}(\hat{\beta}_{\lambda}) = \hat{\sigma}^2 (X^T X + \lambda I)^{-1} X^T X (X^T X + \lambda I)^{-1}$$
   di mana residual variance dihitung via $\hat{\sigma}^2 = \frac{\|y - X\hat{\beta}_{\lambda}\|_2^2}{n - df_{\lambda}}$.
5. **Robust Packaging**: Bungkus seluruh pipeline ke dalam fungsi terstruktur:
   `fast_ridge_engine(X, y, lambdas, compute_se = TRUE)`
   yang mengembalikan objek S3 berkelas `"fast_ridge"` lengkap dengan metode `print()` dan `predict()`.

#### Constraints:
* **Larangan Pustaka Eksternal**: Hanya boleh menggunakan fungsi-fungsi bawaan paket `base` dan `stats` R (misalnya: `svd()`, `crossprod()`, `tcrossprod()`, `colMeans()`).
* **Zero Overhead Iterasi**: Kalkulasi prediksi dan estimasi parameter melintasi seluruh grid $\lambda$ harus sepenuhnya tervektorisasi (manfaatkan matriks broadcasting via kalkulasi diagonal atau operasi array), tidak boleh ada nested-loop lambat di R level.
* **Batas Toleransi Galat**: Nilai koefisien $\hat{\beta}_{\lambda}$ harus presisi hingga toleransi $10^{-9}$ jika dibandingkan dengan solusi referensi analitik.

#### Expected Output:
Fungsi harus mencetak ringkasan diagnostik:
* Waktu eksekusi faktorisasi vs waktu sweep nilai $\lambda$.
* Condition number sebelum dan sesudah regularisasi.
* Tabel output: $\lambda$, $df_{\lambda}$, Residual Scale ($\hat{\sigma}$), dan eksekusi prediksi validasi silang (jika disediakan).

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Bukti matematis mengapa dekomposisi QR memiliki batas galat numerik $\mathcal{O}(\varepsilon \kappa(X))$ sedangkan penyelesaian Normal Equations melalui inversi eksplisit memiliki batas galat $\mathcal{O}(\varepsilon \kappa(X)^2)$, di mana $\kappa(X)$ adalah condition number.
- [ ] Peran fundamental pustaka BLAS Level 1 (vektor-vektor), Level 2 (matriks-vektor), dan Level 3 (matriks-matriks), serta implikasinya terhadap *cache locality* prosesor.
- [ ] Perilaku internal fungsi `crossprod(A, B)` yang memanggil rutin BLAS `DGEMM`/`DSYRK` secara langsung tanpa membuat alokasi objek transposing temporer di R.
- [ ] Teorema Spektral dalam Eigendecomposition matriks kovariansi riil simetris dan syarat mutlak *Positive Definiteness* ($\lambda_i > 0, \forall i$).
- [ ] Trade-off antara mengendalikan Type I Error rate individual ($\alpha$), FWER, dan False Discovery Rate (FDR) dalam konteks uji hipotesis berdimensi tinggi.
- [ ] Mekanisme deteksi multikolinearitas pada Pivoted Cholesky dan Pivoted QR di mana elemen diagonal R matrix di bawah nilai ambang batas (*tolerance*) dieliminasi dari estimasi.
- [ ] Arsitektur representasi Compressed Sparse Column (CSC) dan Compressed Sparse Row (CSR) pada pemrosesan matriks berdimensi masif.

### Saya tidak perlu menghafal:
- [ ] Implementasi baris-per-baris kode sumber Fortran 77 dari rutin LINPACK `dqrls` atau LAPACK `dgesdd`.
- [ ] Angka konstanta eksak bit-level dari state array *Mersenne Twister* ($MT19937$).
- [ ] Sintaks mikro dari seluruh ratusan argumen opsional algoritma penyesuaian matriks korelasi pada package `Matrix::nearPD`.

### Saya harus bisa melakukan:
- [ ] Melakukan profiling dan menghubungkan R dengan BLAS berkinerja tinggi (OpenBLAS/MKL) pada level sistem operasi Linux/macOS.
- [ ] Mendiagnosis dan memperbaiki eror numerik `"system is computationally singular"` tanpa menghilangkan informasi fitur secara sembrono.
- [ ] Mengonversi kode komputasi matriks yang boros memori (`t(X) %*% X`) menjadi bentuk optimal berkinerja tinggi (`crossprod(X)`) secara konsisten.
- [ ] Menyelesaikan sistem persamaan linier $Ax = b$ menggunakan teknik faktorisasi matriks yang paling tepat (Cholesky untuk SPD, QR untuk rectangular/rank-deficient, SVD untuk *ill-conditioned* parah).
- [ ] Membangun simulasi inferensial Monte Carlo berbasis vektor dan matriks yang aman terhadap *concurrency* multithread menggunakan stream PRNG *L'Ecuyer-CMRG*.
- [ ] Memproteksi kode produksi dari penurunan dimensi matriks tak terduga (*dimension dropping*) menggunakan idiom defensif `drop = FALSE`.