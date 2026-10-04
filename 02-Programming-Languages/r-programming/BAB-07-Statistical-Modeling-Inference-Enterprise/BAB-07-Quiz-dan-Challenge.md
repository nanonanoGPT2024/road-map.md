# BAB 07: Quiz, Challenge, & Knowledge Check
**Statistical Modeling & Inference Enterprise**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Anatomi Formulasi dan Konstruksi `model.matrix`
Jelaskan secara mendalam bagaimana R mengevaluasi ekspresi formula (misalnya `y ~ x1 * x2 - 1`) dan mentransformasikannya menjadi matriks desain numerik ($X$) melalui fungsi `model.matrix()`. Bagaimana R menangani variabel kategorikal (*factors*) secara default (kontras treatment), dan apa konsekuensi matematis serta komputasional terhadap matriks desain jika terjadi interaksi antar fitur bertipe faktor dengan kardinalitas tinggi?

### Soal 1.2: Mekanisme Iteratively Reweighted Least Squares (IRLS) pada GLM
Fungsi `glm()` menggunakan algoritma Fisher Scoring/IRLS untuk estimasi parameter Maximum Likelihood. Jelaskan tahapan matematis dari IRLS di setiap iterasi, peran fungsi *link* $g(\mu) = \eta$, fungsi varians $V(\mu)$, serta kalkulasi bobot kerja (*working weights*) $W$ dan variabel dependen kerja (*working response*) $z$. Mengapa pendekatan ini konvergen ke Ordinary Least Squares (OLS) ketika keluarga distribusi yang dipilih adalah Gaussian dengan identity link?

### Soal 1.3: Pengendalian Multiplicity: FWER vs. FDR dalam Inferensi Skala Besar
Dalam konteks pengujian hipotesis simultan skala enterprise (misalnya pengujian 50.000 metrik metrik A/B testing atau genomika), jelaskan perbedaan fundamental antara *Family-Wise Error Rate* (FWER) menggunakan koreksi Bonferroni atau Holm, dan *False Discovery Rate* (FDR) menggunakan metode Benjamini-Hochberg (BH). Kapan FWER menjadi terlalu konservatif secara patologis, dan bagaimana formula $P_{(i)} \le \frac{i}{m} Q$ pada BH menjamin kendali proporsi positif palsu?

### Soal 1.4: Dekomposisi Residual GLM: Pearson, Deviance, dan Working Residuals
Dalam evaluasi model linear tergeneralisasi (GLM), `residuals()` di R menyediakan tipe residual yang berbeda: `deviance`, `pearson`, `response`, dan `working`. Jelaskan formulasi matematis dan tujuan diagnostik spesifik dari **Pearson residuals** versus **Deviance residuals**. Mengapa Deviance residuals lebih disukai untuk mendeteksi *lack of fit* dan observasi *influential* pada regresi non-Gaussian (seperti Poisson atau Binomial)?

### Soal 1.5: Linear Mixed-Effects Models (LMM): Random Intercepts, Random Slopes, dan Penalti BLUP
Jelaskan formulasi matematis model campuran linear $y = X\beta + Zb + \epsilon$, di mana $b \sim \mathcal{N}(0, \Sigma)$ dan $\epsilon \sim \mathcal{N}(0, \sigma^2 I)$. Bagaimana algoritma Restricted Maximum Likelihood (REML) mengestimasi komponen varians secara tidak bias dibandingkan Maximum Likelihood (ML) standar? Jelaskan konsep *shrinkage* (partial pooling) pada *Best Linear Unbiased Predictors* (BLUPs) untuk efek acak dan bagaimana LMM menyelesaikan Simpson’s Paradox pada data terkelompok (*hierarchical/longitudinal*).

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Memory Footprint Bloat pada Serialisasi Objek `lm` dan `glm`
Sebuah model regresi sederhana dilatih pada data set 15 GB menggunakan sintaks:
```R
fit_model <- function(df) {
  fit <- lm(revenue ~ ., data = df)
  return(fit)
}
model <- fit_model(huge_df)
saveRDS(model, "model.rds")
```
Berkas `model.rds` yang dihasilkan berukuran lebih dari 15 GB, padahal estimasi koefisien hanya terdiri dari beberapa baris vektor numerik. Analisis struktur internal objek `lm` (termasuk atribut `terms`, lingkungan/`environment` leksikal, serta komponen `model`, `residuals`, dan `fitted.values`). Tuliskan kode idiomatik R untuk memangkas (*pruning*) objek model sebelum diserialisasi ke disk agar ukurannya turun ke tingkat kilobyte tanpa merusak kemampuan fungsi `predict(model, newdata)`.

### Soal 2.2: Fenomena Hauck-Donner dan Quasi-Complete Separation pada Regresi Logistik
Saat menjalankan `glm(status ~ x1 + x2, data = df, family = binomial)`, R mengeluarkan peringatan:
`Warning message: glm.fit: fitted probabilities numerically 0 or 1 occurred`.
Selain itu, nilai *p-value* untuk variabel $x_1$ melonjak menjadi mendekati 1.0 dengan *standard error* yang bernilai jutaan. Jelaskan mekanisme matematis di balik anomali Hauck-Donner dan masalah *complete/quasi-complete separation*. Bagaimana cara Anda memitigasi masalah ini di R tanpa menghapus variabel prediktor penting tersebut (analisis perbandingan antara metode Firth’s Penalized Likelihood via paket `logistf` versus regularisasi $L_2$/Ridge via `glmnet`)?

### Soal 2.3: Singularitas Desain Matriks dan Pivoted QR Decomposition
Ketika matriks desain $X$ mengalami multikolinearitas sempurna (rank-deficient), `lm()` di R tetap menghasilkan output tanpa melempar fatal error, namun beberapa koefisien bernilai `NA`. Jelaskan secara teknis bagaimana implementasi dekomposisi QR terpivotasi (*Pivoted QR Decomposition* berbasis Fortran LAPACK/LINPACK) mendeteksi defisiensi rank pada R. Apa dampak keberadaan `NA` pada sub-ruang proyeksi topi (*hat matrix*) $H = X(X^T X)^{-1}X^T$, dan bagaimana hal ini memengaruhi penghitungan derajat kebebasan (*degrees of freedom*) residu serta statistik uji F?

### Soal 2.4: Validitas Inferensi Pasca Seleksi (*Post-Selection Inference Trap*)
Pengembang analitik data menggunakan fungsi `stepAIC(model, direction = "both")` dari paket `MASS` untuk memilih subset variabel terbaik berdasarkan AIC, kemudian mengambil output `summary(best_model)` dan melaporkan nilai *p-value* dari t-test koefisien sebagai bukti signifikansi ilmiah kepada regulator. Tunjukkan cacat metodologis mendasar dari praktik ini (*data snooping/selection bias*). Mengapa standar error nominal yang dihasilkan `summary()` menjadi terlalu optimis (underestimated), dan bagaimana pendekatan valid seperti *data splitting* atau *selective inference* (misalnya via `selectiveInference`) memulihkan integritas interval kepercayaan?

### Soal 2.5: Overdispersion Diagnostik dan Quasi-Likelihood pada GLM Poisson
Diberikan model Poisson $Y_i \sim \text{Poisson}(\mu_i)$. Pada evaluasi data produksi di R, ditemukan bahwa statistik Deviance Residual jauh lebih besar daripada Residual Degrees of Freedom ($\text{Deviance}/df = 4.8$). Jelaskan implikasi kondisi *overdispersion* ini terhadap estimasi kovarians koefisien $\text{Var}(\hat{\beta})$. Tunjukkan bagaimana mendiagnosis overdispersion secara formal di R, dan bandingkan dua strategi pemulihannya: menggunakan varian *Quasi-Poisson* (sandwich variance correction) versus pemodelan *Negative Binomial* (`MASS::glm.nb`) dengan estimasi parameter dispersi $\theta$.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: OOM Crashes pada Training Batch Pipeline Skala 50 Juta Baris
Sebuah pipeline batch di cluster Kubernetes menjalankan skrip R harian untuk memprediksi probabilitas gagal bayar menggunakan regresi logistik pada 50 juta transaksi dengan 120 fitur campuran numerik dan kategorikal. Pipeline tersebut secara konsisten dihentikan oleh OS kernel dengan sinyal `OOMKilled` (Exit Code 137) pada node dengan RAM 128 GB saat mengeksekusi `glm(target ~ ., data = transactions, family = binomial)`.
*   **Pertanyaan Diagnostik & Solusi:**
    1.  Identifikasi titik kritis di dalam source code internal `glm()` dan `model.matrix()` yang memicu pelipatgandaan alokasi memori (*memory allocation overhead*) hingga menembus batas RAM 128 GB.
    2.  Rancang arsitektur komputasi pengganti di R yang memungkinkan estimasi parameter model GLM dilakukan tanpa memuat seluruh matriks desain ke dalam RAM sekaligus. Bandingkan efektivitas implementasi menggunakan pendekatan out-of-core streaming via `biglm`, pemanfaatan sparse design matrix via `fastglm` / `Matrix::sparse.model.matrix`, dan integrasi chunked parallel processing.

### Skenario B: Inferensi A/B Testing Terdistorsi Akibat "Continuous Peeking"
Sistem eksperimentasi online otomatis di sebuah platform e-commerce mengevaluasi konversi varian fitur baru. Skrip R diotomatisasi untuk mengeksekusi uji hipotesis dua sampel binomial (`prop.test` atau `t.test`) setiap 30 menit sekali secara real-time. Jika $p < 0.05$, pipeline otomatis menghentikan eksperimen dan meluncurkan varian tersebut ke 100% trafik produksi. Pasca implementasi, tim produk menemukan bahwa 45% fitur yang lolos seleksi ternyata tidak memberikan dampak kenaikan metrik sama sekali (false positive rate aktual jauh melampaui batas teoritis $\alpha = 0.05$).
*   **Pertanyaan Diagnostik & Solusi:**
    1.  Jelaskan fenomena *alpha spending violation* dan *optional stopping problem* yang terjadi akibat pengujian berulang (*continuous monitoring*) pada inferensi frekuentis klasik.
    2.  Modifikasi pipeline analisis R tersebut menggunakan metodologi inferensi yang valid untuk pengujian sekuensial. Rancang implementasi menggunakan koreksi batas penolakan (*Sequential Alpha Spending Function* seperti O'Brien-Fleming via paket `gsDesign`) atau transisi ke inferensi Bayesian Sequential Analysis (menghitung Bayes Factor atau posterior probability interval menggunakan `BayesFactor`).

### Skenario C: Latency vs. Interpretability Trade-Off pada Credit Risk Regulatory Engine
Sebuah bank multinasional wajib mematuhi regulasi Basel III / IFRS 9 dalam menghitung probabilitas gagal bayar (Probability of Default - PD). Regulator mewajibkan setiap bobot parameter model dapat diinterpretasikan secara matematis (analisis sensitivitas dan interval kepercayaan jelas), bebas dari efek multikolinearitas, dan memiliki kestabilan prediksi yang tinggi. Di sisi lain, sistem penilaian kredit tersebut harus di-deploy ke dalam REST API performa tinggi dengan *response time SLA* $< 30$ milidetik per request di lingkungan inference R (misalnya via `Plumber`).
*   **Pertanyaan Diagnostik & Solusi:**
    1.  Evaluasi trade-off arsitektural antara:
        *   Model Regresi Logistik Biasa (`stats::glm`).
        *   Elastic-Net Penalized GLM (`glmnet::glmnet`).
        *   Generalized Additive Models (`mgcv::gam`).
        *   Bayesian Generalized Linear Mixed Models (`brms` / `rstanarm`).
    2.  Model mana yang paling optimal untuk menyeimbangkan kebutuhan regulasi perbankan yang ketat (auditability & inference robustness) dengan SLA latensi 30ms? Jelaskan rancangan ekosistem scoring-nya: bagaimana parameter model diekstraksi dari objek pelatihan R dan dieksekusi di fase serving tanpa membawa overhead interpretasi objek R yang berat.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Throughput Memory-Optimized Robust Statistical Engine
Anda ditugaskan membangun sebuah R package modular tingkat enterprise bernama **`coreStatEngine`** yang mampu menangani pelatihan, diagnostik, inferensi statistik, dan ekspor artefak scoring dari model GLM binomial pada dataset bervolume tinggi yang memiliki karakteristik multikolinearitas dan data terpisah (*separation*).

#### Requirements:
1.  **Memory-Efficient Design Matrix Builder**:
    *   Buat fungsi `build_enterprise_matrix(formula, data)` yang mendeteksi variabel kategorikal kardinalitas tinggi dan mengonversinya secara efisien ke dalam format `Matrix::sparse.model.matrix` tanpa membuat salinan perantara (*dense matrix intermediate*) di heap memori.
2.  **Robust Regularized Inference**:
    *   Implementasikan fungsi `fit_robust_inference(sparse_X, y, alpha = 0.5)` yang menggunakan Elastic-Net via `glmnet`.
    *   Fungsi harus menghitung *standard error*, *z-value*, dan *p-value* koefisien non-nol menggunakan teknik post-regularization unpenalized refitting atau bootstrap non-parametrik yang dioptimalkan dengan komputasi paralel (`parallel` / `future`).
3.  **Model Stripping Engine**:
    *   Implementasikan fungsi `strip_model(model_obj)` yang membuang environments, fitted values, residuals, dan atribut tersembunyi lainnya, memastikan ukuran serialisasi model `< 50 KB`.
4.  **Zero-Dependency Prediction Micro-Kernel**:
    *   Buat fungsi `fast_score(stripped_model, newdata)` yang melakukan matriks perkalian vektor murni $\text{logit}^{-1}(X\beta)$ secara langsung menggunakan LAPACK tanpa memanggil fungsi `predict.glm` bawaan R, memangkas overhead pemanggilan generic S3.

#### Constraints:
*   Tidak boleh menggunakan variabel global atau manipulasi environment yang melanggar fungsi murni (*pure functions*).
*   Alokasi memori selama fase preprocessing dan training tidak boleh melebihi $2 \times$ ukuran memori dataset awal.
*   Skrip harus menyertakan unit test menggunakan `testthat` untuk menguji skenario deterministik: penanganan nilai kosong (*missing values*), deteksi singularitas, dan konsistensi matematis keluaran prediksi terhadap `stats::predict.glm`.

#### Expected Output:
Sebuah file R terstruktur rapi yang berisi fungsi-fungsi di atas, dilengkapi dengan dokumentasi parameter tipe data (Roxygen2), logging diagnostik (waktu eksekusi, memori yang terpakai via `pryr` atau `bench`), serta demonstrasi benchmark perbandingan kecepatan scoring antara `fast_score` vs `predict.glm`.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Representasi internal formula R (`terms`, `formula`, `factors`, dan atribut `.Environment`).
- [ ] Formulasi matematis IRLS dan dekomposisi QR dalam menyelesaikan sistem persamaan normal pada regresi.
- [ ] Perbedaan matematis dan interpretasi antara Pearson, Deviance, Hat values (leverage), dan Cook's Distance pada GLM.
- [ ] Masalah identifiabilitas, kolinearitas sempurna, dan bagaimana pivoted QR menangani rank-deficiency.
- [ ] Batasan pengujian hipotesis klasik: p-value fallacies, multiple testing artifacts, dan bahaya continuous peeking.
- [ ] Karakteristik *shrinkage* dan struktur matriks kovarians pada *Linear Mixed Models* (LMM/GLMM).
- [ ] Mekanisme terjadinya Complete Separation dan Hauck-Donner effect pada logistic regression.

### Saya tidak perlu menghafal:
- [ ] Kode C atau Fortran mendalam di dalam BLAS/LAPACK yang melandasi fungsi `dqrls`.
- [ ] Formula analitis exact untuk derajat kebebasan Satterthwaite atau Kenward-Roger pada LMM (cukup gunakan paket `lmerTest`).
- [ ] Nilai kritis tabel Z, T, F, atau Chi-Square untuk setiap derajat kebebasan manual (selalu gunakan fungsi distribusi `pt()`, `pf()`, `pchisq()`).

### Saya harus bisa melakukan:
- [ ] Menemukan dan mengisolasi memory leak pada objek model statistik yang disebabkan oleh penangkapan *enclosing environment* R.
- [ ] Memodifikasi dan mengimplementasikan koreksi multiple testing (Benjamini-Hochberg, Bonferroni) secara manual atau terprogram via `p.adjust()`.
- [ ] Menangani overdispersion pada data count menggunakan regresi Quasi-Poisson atau Negative Binomial dengan validasi statistik rasio likelihood / deviance test.
- [ ] Menjalankan cross-validation dan bootstrap non-parametrik terdistribusi untuk inferensi empiris model non-standar.
- [ ] Menulis fungsi prediksi kustom berlatensi ultra-rendah memanfaatkan operasi aljabar linear vektor/matriks murni (`%*%`) untuk deployment production API.