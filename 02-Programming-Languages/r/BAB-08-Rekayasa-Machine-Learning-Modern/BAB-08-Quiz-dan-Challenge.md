# BAB 08: Quiz, Challenge, & Knowledge Check
**Rekayasa Machine Learning Modern (Tidymodels Ecosystem)**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Pemisahan Deklarasi dan Komputasi Desain Preprocessing
Jelaskan perbedaan mendasar antara fase deklarasi transformasi (`recipe()`), estimasi parameter statistik (`prep()`), dan eksekusi transformasi pada data baru (`bake()`) dalam paket `recipes`. Mengapa pemisahan siklus hidup (lifecycle) ini secara matematis dan arsitektural mencegah terjadinya *data leakage* (kebocoran data) jika dibandingkan dengan pendekatan fungsional *ad-hoc* seperti pemanggilan `scale()` atau imputasi nilai rata-rata langsung pada keseluruhan *data frame* sebelum *splitting*?

### Soal 1.2: Unified Interface Abstraction via `parsnip`
Dalam ekosistem R tradisional, pemodelan Random Forest dapat diakses melalui `randomForest::randomForest()`, `ranger::ranger()`, atau layanan terdistribusi seperti `sparklyr`. Analisis bagaimana `parsnip` membungkus divergensi argumen sintaksis (misalnya perbedaan `mtry`, penanganan missing values, format data matriks vs formula) ke dalam model specification standar. Apa implikasi arsitektural dari decoupling antara *model type*, *engine*, dan *mode* terhadap skalabilitas kode di lingkungan produksi?

### Soal 1.3: Mekanisme Resampling Non-Destruktif pada `rsample`
Ketika melakukan *k-fold cross-validation* menggunakan `vfold_cv()`, paket `rsample` tidak menduplikasi data set mentah sebanyak $k$ kali di dalam alokasi memori RAM. Jelaskan mekanisme representasi objek `rset` dan *pointer-based indexing* (menggunakan kelas `splits`) yang digunakan oleh `rsample` untuk meminimalkan *memory footprint*. Apa konsekuensinya terhadap garbage collection (GC) saat menangani dataset berukuran gigabyte?

### Soal 1.4: Kontrak Eksekusi Terisolasi pada `workflows`
Apa peran objek `workflow` sebagai *single point of encapsulation* yang mengikat spesifikasi model `parsnip` dan tahap pemrosesan `recipes` atau formula? Jelaskan secara teknis bagaimana sebuah workflow memastikan bahwa proses *fitting* data validasi tidak pernah mengeksekusi kalkulasi varians, mean, atau encoding level kategori baru yang berasal dari *testing set* atau *holdout set*.

### Soal 1.5: Metrologi Evaluasi Model via `yardstick`
Jelaskan secara struktural bagaimana fungsi-fungsi evaluasi matriks pada `yardstick` beroperasi di bawah prinsip *tidy data*. Bagaimana `yardstick` menangani metrik multikelas (multiclass classification metrics) menggunakan pendekatan *macro-averaging*, *micro-averaging*, dan *weighted-averaging*? Tunjukkan bagaimana struktur tabular input (`.pred_class`, `.pred_` probabilities, dan ground truth) divalidasi sebelum kalkulasi metrik dilakukan.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Debugging Resampling Failures & Convergence Edge-Cases
Saat menjalankan hyperparameter tuning skala besar menggunakan `tune_grid()` dengan backend paralel (`doFuture`), sebagian iterasi model gagal konvergen (misalnya: singular matrix pada penalized regression `glmnet` atau tree depth overflow pada `xgboost`), menghasilkan error yang berpotensi mematikan seluruh job multi-core.
* Pertanyaan: Parameter atau fungsi kontrol apa yang harus dikonfigurasi pada objek `control_grid()` untuk mengisolasi kegagalan per fold tanpa menghentikan worker lain? Bagaimana Anda mengekstraksi stack trace error internal yang tersimpan di dalam metadata `.notes` pada output tibble tuning?

### Soal 2.2: Edge Cases Penanganan Kategori Baru (Unseen Levels)
Pada pipeline klasifikasi, sebuah prediktor kategorikal berstatus *high-cardinality* memiliki level kategori baru pada *test set* atau data inferensi real-time yang tidak pernah muncul pada *training set*. 
* Pertanyaan: Bedah mekanisme internal dari step `step_novel()` versus `step_other()`. Pada urutan (order of execution) ke berapa step ini harus diletakkan relatif terhadap `step_dummy()`? Tunjukkan anomali aljabar linear (rank-deficient design matrix) yang terjadi jika *dummy encoding* dilakukan mendahului penanganan nilai *novel* tersebut.

### Soal 2.3: Overhead Serialisasi dan Bottleneck Objek Model Tidymodels
Sebuah workflow terlatih yang siap dideploy disimpan menggunakan fungsi dasar `saveRDS()`. Ukuran file biner yang dihasilkan melonjak hingga 450 MB, meskipun data training aslinya hanya berukuran 15 MB.
* Pertanyaan: Elemen metadata, lingkungan leksikal R (enclosing environment closures), dan internal model attributes apa saja yang tersimpan di dalam objek `workflow` ter-fit yang menyebabkan fenomena bloating ini? Bagaimana cara sistematis mereduksi ukuran artefak tersebut menggunakan paket `butcher` tanpa merusak fungsionalitas metode `predict()` di lingkungan produksi?

### Soal 2.4: Determinisme dan Stateful Randomness pada Parallel Tuning
Anda mengonfigurasi tuning grid hyperparameter dengan `tune_grid()` menggunakan 16 core CPU via framework `future`. Meskipun Anda telah mengeksekusi `set.seed(42)` sebelum memanggil `tune_grid()`, hasil evaluasi parameter optimal (misalnya nilai ROC-AUC) berubah-ubah di setiap eksekusi batch produksi.
* Pertanyaan: Mengapa `set.seed()` standar pada R gagal menjamin reproduksibilitas pada worker parallel asynchronous? Jelaskan bagaimana mekanisme RNG (Random Number Generator) berbasis L'Ecuyer-CMRG (`future.seed = TRUE` atau pengaturan seed internal Tidymodels) mengatasi collision state dan menjamin determinisme matematis antar-thread.

### Soal 2.5: Isolasi State: `prep()` Retention Pitfall
Secara default, pemanggilan `prep(recipe_obj)` mempertahankan internal dataset hasil transformasi di dalam slot objek melalui parameter `retain = TRUE`.
* Pertanyaan: Apa implikasi konsumsi memori dari perilaku default ini saat melakukan tuning dengan skema $10$-Fold CV yang diulang 5 kali ($50$ split instances)? Kapan seorang ML engineer wajib mengoperasikan `prep(recipe_obj, retain = FALSE)`, dan bagaimana fungsi `bake()` tetap dapat mengekstraksi representasi data training jika `retain = FALSE` diaktifkan?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Investigasi Resource Exhaustion & OOM Killer pada Tuning Cluster
Sebuah sistem Continuous Integration / Retraining Pipeline di AWS EC2 instance (`r5.4xlarge`, 16 vCPU, 128 GB RAM) mengalami crash fatal dengan pesan `Killed` dari Linux Kernel OOM (Out-Of-Memory) Killer. Sistem sedang menjalankan hyperparameter tuning model LightGBM (`boost_tree()`) menggunakan `finetune::tune_race_anova()` dengan skema 10-Fold CV pada dataset transaksi berukuran 8 GB (15 juta baris, 80 fitur). Backend konkurensi menggunakan `doParallel::registerDoParallel(cores = 16)`.
* **Pertanyaan Diagnostik:**
  1. Analisis arsitektur memori *forking* vs *background R sessions* (`multicore` vs `multisession`): Mengapa pemodelan multi-core native R pada environment Linux menyalin alokasi memori (copy-on-write degradation) hingga memicu OOM Killer?
  2. Bagaimana modifikasi arsitektur eksekusi tuning Anda? Jelaskan trade-off antara nesting paralelisme (paralelisasi tingkat tuning-fold vs paralelisasi internal thread C++ dari engine `lightgbm` via argumen `num_threads`).
  3. Rancang strategi tuning hemat sumber daya menggunakan parameter kontrol `control_race()` untuk mengeliminasi kandidat hyperparameter suboptimal secara dini tanpa mengeksekusi seluruh fold secara komprehensif.

### Skenario B: Target Leakage Sistemik pada Skema Time-Series Split
Sebuah tim kuantitatif membangun model prediksi default kredit untuk transaksi berulang nasabah selama horizon waktu 2018–2023. Pipeline menggunakan `recipes` dengan langkah:
1. `step_impute_median(all_numeric_predictors())`
2. `step_normalize(all_numeric_predictors())`
3. `step_pca(all_numeric_predictors(), num_comp = 10)`

Evaluasi validasi menggunakan `rsample::vfold_cv(v = 5)` melaporkan performa fantastis dengan AUC 0.94. Namun, ketika model dideploy ke sistem inferensi live (data kuartal berjalan), performa anjlok drastis ke AUC 0.58.
* **Pertanyaan Diagnostik:**
  1. Identifikasi dua sumber fatal kegagalan desain validasi dan preprocessing pada pipeline di atas yang menyebabkan distorsi performa.
  2. Mengapa penggunaan `vfold_cv()` konvensional melanggar dependensi temporal pada data berurutan (autocorrelated time-series), dan bagaimana fungsi `sliding_period()` atau `rolling_origin()` dari `rsample` memperbaiki bias prospektif ini?
  3. Buktikan secara teoritis bagaimana `step_pca()` dan `step_impute_median()` yang dieksekusi tanpa segregasi temporal yang ketat menginjeksi informasi masa depan (*lookahead bias*) ke dalam proses kalibrasi model.

### Skenario C: Deployment Microservice & Contract Decoupling via Vetiver
Organisasi Anda memutuskan untuk menstandarisasi artefak model Tidymodels ke dalam format microservice REST API yang berjalan di atas Kubernetes Pods. Model yang dilatih harus melayani *real-time inference* dengan throughput target 500 request/detik dan latency $P_{99} < 40\text{ ms}$. Tim mempertimbangkan dua rute arsitektur:
* **Rute 1:** Menyimpan full `workflow` ter-fit menggunakan paket `vetiver`, dibungkus server `plumber`, dan di-deploy via Docker image.
* **Rute 2:** Mengekstraksi underlying C++ engine binary (misal: serialisasi `xgb.Booster` mentah) atau mengonversi model pipeline ke format standar interoperabilitas terbuka (ONNX / Treelite) lalu dilayani menggunakan runtime Go/C++ (seperti Triton Inference Server).
* **Pertanyaan Diagnostik:**
  1. Apa trade-off arsitektural utama antara kemudahan operasional Rute 1 (preservasi transformasi data otomatis via recipe steps) dibandingkan dengan Rute 2 dalam konteks skalabilitas konkurensi (R's single-threaded event loop limitation)?
  2. Jika Rute 1 dipilih, modifikasi arsitektural apa saja pada level server API (`plumber`) dan containerization yang wajib diimplementasikan untuk menangani konkurensi tinggi tanpa memblokir CPU?
  3. Bagaimana `vetiver` memfasilitasi monitoring *feature drift* dan validasi skema payload input secara deklaratif di lingkungan Kubernetes?

---

## 4. Chapter Challenge

### Tantangan Praktis: Enterprise-Grade Fraud Detection Pipeline Engine

#### Deskripsi Masalah
Anda ditugaskan sebagai Principal ML Engineer di sebuah institusi fintech unicorn untuk merancang *pipeline end-to-end* deteksi transaksi mencurigakan (*fraud detection*). Karakteristik dataset ini memiliki ketidakseimbangan kelas ekstrem (*extreme class imbalance* sebesar 0.2% fraud), fitur multivariat dengan missing values heterogen, prediktor kategorikal ber-kardinalitas tinggi (misal: ID Merchant, Lokasi), serta noise fitur yang signifikan.

#### Requirements Teknis
1. **Data Splitting & Resampling Framework:**
   * Bangun partisi stratified split ($80/20$) dengan menjaga proporsi kelas langka menggunakan `rsample::initial_split()`.
   * Definisikan skema validasi silang temporal atau k-fold berulang bertingkat (*Repeated Stratified 5-Fold CV*) untuk optimasi tuning.
2. **Advanced Recipe Engineering:**
   * Lakukan penanganan missing values numerik menggunakan K-Nearest Neighbors imputation (`step_impute_knn()`) atau Bagged Trees imputation.
   * Tangani kardinalitas tinggi dan unseen categories dengan `step_novel()` dan `step_other()`.
   * Lakukan integrasi teknik subsampling terarah untuk menangani *class imbalance* menggunakan `themis::step_smote()` atau `themis::step_downsample()` khusus pada *training folds* secara terisolasi.
   * Lakukan ekstraksi fitur reduksi dimensi atau transformasi non-linear (misal: `step_YeoJohnson()`).
3. **Multi-Model Race Comparison via `workflowset`:**
   * Bangun sedikitnya dua spesifikasi model dari paradigma berbeda:
     * *Regularized Elastic Net* (`linear_reg()` / `multinom_reg()` via `glmnet`).
     * *Gradient Boosted Decision Trees* (`boost_tree()` via `xgboost`).
   * Pasangkan recipe dengan masing-masing model menggunakan `workflow_set()`.
4. **Adaptive Tuning Execution:**
   * Lakukan pencarian parameter optimal menggunakan optimasi cerdas (`finetune::tune_race_anova()` atau Bayesian optimization via `tune_bayes()`).
   * Optimasi metrik evaluasi yang kebal terhadap *class imbalance* (fokus pada `pr_auc` dan `roc_auc`).
5. **Model Finalization, Serialisation, & Payload Extraction:**
   * Pilih konfigurasi hyperparameter terbaik (*best candidate*).
   * Lakukan finalisasi model menggunakan `tune::last_fit()` pada test split untuk mendapatkan unbiased generalized performance report.
   * Lakukan pembersihan artefak (*stripping environment*) menggunakan `butcher::butcher()`.
   * Ekspor model menggunakan `vetiver::vetiver_model()` dan verifikasi kesiapan eksekusi inferensi pada batch data simulasi 100 baris.

#### Constraints
* **Pure Tidymodels Ecosystem:** Dilarang keras menggunakan pemanggilan fungsi transformasi data di luar `recipes` (dilarang menggunakan fungsi mutasi `dplyr` terpisah pasca-splitting) untuk membuktikan pipeline bebas data leakage.
* **Deterministic Execution:** Seluruh kode tuning multi-threading harus dikunci dengan seeding L'Ecuyer-CMRG yang dapat direproduksi secara deterministik.
* **Memory Management:** Pipeline harus mampu mengeksekusi garbage collection secara eksplisit dan tidak mempertahankan objek duplikat di RAM.

#### Expected Output
1. Script R arsitektural lengkap (`pipeline.R`) yang modular, modularisasi fungsi terstruktur, dan siap dieksekusi di *production runner*.
2. Visualisasi perbandingan metrik kinerja antar-model (`autoplot()` dari objek workflow set).
3. Matriks evaluasi testing (`conf_mat()`, `roc_auc()`, dan `pr_auc()`) yang dicetak dalam format tabular rapi.
4. Model artifact binary yang telah di-*butcher* beserta kalkulasi persentase reduksi ukuran memori (byte size comparison sebelum dan sesudah optimasi `butcher`).

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Siklus hidup pemrosesan data formal: Perbedaan arsitektural antara spesifikasi (`recipe`), fitting parameter statistik (`prep`), dan eksekusi inferensi data (`bake`).
- [ ] Desain isolasi `workflows`: Bagaimana objek workflow mengontrol pergerakan data dan mencegah *data leakage* di setiap fase cross-validation dan testing.
- [ ] Unified model parameter mapping: Cara `parsnip` menerjemahkan hyperparameter universal ke argumen spesifik engine backend (e.g., `cost_complexity` $\rightarrow$ `cp` pada `rpart` atau `cost` pada `C5.0`).
- [ ] Mekanisme indexing `rsample`: Cara pointer memori dan integer vector indices digunakan pada objek `rset` untuk menghindari duplikasi dataframe berulang.
- [ ] Teori evaluasi performa model klasifikasi imbalanced: Keterbatasan metrik Accuracy dan AUC-ROC vs keunggulan Precision-Recall AUC (PR-AUC) pada skewed labels.
- [ ] Prinsip paralelisasi asynchronous: Perbedaan thread parallel internal (C++ level) vs fold parallel (R process level) serta implikasinya terhadap alokasi memori sistem.
- [ ] Bahaya stateful closure R: Mengapa R environments mengikat variabel eksternal pada model object serialization dan teknik mitigasinya.

### Saya tidak perlu menghafal:
- [ ] Seluruh nama spesifik argumen mesin model di library aslinya (misalnya nama parameter internal spesifik di C API LightGBM vs XGBoost), karena telah diabstraksikan oleh `parsnip::show_model_info()`.
- [ ] Sintaks rumus matematis eksak step transformasi statistik kompleks (misalnya formula parameter Yeo-Johnson atau lambda Box-Cox), karena dikalkulasi secara otomatis oleh backend `recipes`.
- [ ] Daftar lengkap puluhan fungsi step preprocessing di library `recipes`; cukup memahami taksonomi penggunaannya (`step_impute_*`, `step_dummy`, `step_scale`, `step_pca`).

### Saya harus bisa melakukan:
- [ ] Merancang pipeline machine learning bebas bocor (*leakage-free*) end-to-end dari data ingestion hingga final testing menggunakan workflow Tidymodels.
- [ ] Melakukan tuning hyperparameter multi-dimensi dengan strategi pencarian grid, random, race anova, atau bayesian search.
- [ ] Mengontrol eksekusi konkurensi komputasi paralel menggunakan paket `future` dan backend cluster engine secara deterministik dan hemat memori.
- [ ] Melakukan troubleshooting error internal worker dan warning messages tersembunyi menggunakan atribut metadata objek tuning.
- [ ] Mengoptimalkan ukuran footprint biner model ML R menggunakan paket `butcher` untuk persiapan deployment microservice latency-sensitive.
- [ ] Mengintegrasikan pipeline Tidymodels ke model serving wrapper menggunakan framework `vetiver` untuk inferensi berbasis API.