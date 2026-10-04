# BAB 08: Quiz, Challenge, & Knowledge Check
**Pemodelan Statistik Inferensial & Machine Learning Terapan**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Misinterpretasi Nilai $p$ (*p-value*) dan Konsekuensi Bisnis
Secara matematis, jelaskan definisi presisi dari *p-value* dalam konteks pengujian hipotesis *Null-Hypothesis Significance Testing* (NHST). Mengapa menginterpretasikan *p-value* sebesar $0.03$ sebagai "kemungkinan hipotesis nol benar adalah 3%" atau "kemungkinan efek ini terjadi secara kebetulan adalah 3%" merupakan kesalahan fatal (*fallacy*)? Analisis dampaknya terhadap pengambilan keputusan berbasis data di level produksi.

### Soal 1.2: Geometri Regularisasi L1 (Lasso) vs. L2 (Ridge)
Ditinjau dari formulasi optimasi konveks dengan fungsi kerugian *Ordinary Least Squares* (OLS):
$$\min_{\beta} \|y - X\beta\|_2^2 + \lambda \|\beta\|_p$$
Jelaskan secara geometris dan matematis mengapa penalti norm-1 ($p=1$, Lasso) mampu menghasilkan *sparse coefficients* (eliminasi fitur secara otomatis menjadi tepat bernilai nol), sedangkan penalti norm-2 ($p=2$, Ridge) hanya mampu memperkecil magnitude koefisien mendekati nol tanpa pernah menyentuh nilai nol.

### Soal 1.3: Asimptotik dan Asumsi Distribusi OLS
Sebutkan asumsi-asumsi klasik Gauss-Markov pada regresi linier OLS. Apa implikasi struktural jika terjadi pelanggaran asumsi *homoscedasticity* (terjadi *heteroscedasticity*) dan *multicollinearity* yang parah pada matriks kovariat $X$? Jelaskan perbedaannya terhadap efisiensi estimator $\hat{\beta}$ versus ketepatan inferensi berbasis uji-$t$ dan uji-$F$.

### Soal 1.4: Dilema Metrik pada Dataset Kelas Sangat Tidak Seimbang (*Extreme Imbalance*)
Pada kasus deteksi *financial fraud* dengan rasio kelas positif $0.05\%$, jelaskan mengapa metrik *Receiver Operating Characteristic - Area Under Curve* (ROC-AUC) memberikan gambaran optimisme palsu (*overly optimistic performance*) dibandingkan *Precision-Recall Area Under Curve* (PR-AUC / Average Precision). Tinjau argumen Anda berdasarkan formulasi *False Positive Rate* (FPR) vs *Recall* (*True Positive Rate*) dan *Precision*.

### Soal 1.5: Mekanika Kebocoran Data (*Data Leakage*) dalam Preprocessing
Mengapa melakukan standardisasi fitur (misal: `StandardScaler().fit_transform(X)`) atau pengisian nilai hilang (*imputation*) pada seluruh dataset sebelum membaginya menjadi *training set* dan *test set* diklasifikasikan sebagai *data leakage*? Bagaimana kebocoran ini memengaruhi varians estimator dan reliabilitas estimasi generalisasi model saat *deployment*?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Debugging Singular Matrix & Multikolinearitas Sempurna pada `statsmodels`
Diberikan cuplikan kode eksekusi menggunakan `statsmodels.api` berikut:

```python
import numpy as np
import statsmodels.api as sm

# X_raw berisi data kategorikal bertipe string yang di-encode
# menggunakan pd.get_dummies(df, drop_first=False)
X = sm.add_constant(X_dummies)
model = sm.OLS(y, X).fit()
print(model.summary())
```

Output menampilkan peringatan: `LinAlgError: SVD did not converge` atau menghasilkan estimasi parameter dengan `Standard Error` yang luar biasa besar ($> 10^7$) dan nilai condition number bernilai astronomis. 
1. Bedah mekanisme aljabar linier internal pada dekomposisi matriks $(X^T X)^{-1} X^T y$ yang memicu kegagalan ini (*dummy variable trap*).
2. Tuliskan algoritma remediasi menggunakan *Variance Inflation Factor* (VIF) untuk mendeteksi dan mengeliminasi multikolinearitas multivariat secara terprogram.

### Soal 2.2: Kebocoran Waktu (*Temporal Leakage*) pada Scikit-Learn Pipelines
Seorang *data scientist* membuat *pipeline* evaluasi model prediksi *churn* bulanan dengan kode berikut:

```python
from sklearn.model_selection import KFold, cross_val_score
from sklearn.pipeline import Pipeline
from category_encoders import TargetEncoder
from xgboost import XGBClassifier

pipeline = Pipeline([
    ('encoder', TargetEncoder()),
    ('classifier', XGBClassifier(n_estimators=100, random_state=42))
])

cv = KFold(n_splits=5, shuffle=True, random_state=42)
scores = cross_val_score(pipeline, X_time_series, y_time_series, cv=cv, scoring='roc_auc')
```

Identifikasi dua kecacatan fatal pada arsitektur validasi di atas terkait:
1. Penggunaan `KFold(shuffle=True)` pada data time-series/event-based.
2. Mekanisme komputasi internal `TargetEncoder` jika dikaitkan dengan *out-of-fold target calculation*. Tuliskan solusi perbaikannya menggunakan primitif Scikit-Learn yang tepat.

### Soal 2.3: Kalibrasi Probabilitas dan Brier Score
Sebuah model *risk scoring* memiliki performa ROC-AUC sebesar $0.88$, namun departemen aktuaria menolak model tersebut karena prediksi probabilitasnya tidak terkalibrasi (*miscalibrated*).
1. Apa arti praktis dari probabilitas yang terkalibrasi secara empiris?
2. Bagaimana cara kerja internal metode kalibrasi *Platt Scaling* (regresi logistik univariat) vs *Isotonic Regression* (regresi non-parametrik monotonik)? 
3. Mengapa *Isotonic Regression* rentan mengalami *overfitting* pada dataset berukuran kecil hingga menengah?

### Soal 2.4: Paradoks Simpson dalam Pengujian A/B Skala Besar
Sebuah platform e-commerce menjalankan pengujian A/B untuk alur *checkout* baru selama dua minggu. Secara agregat:
- Conversion Rate (CR) Kontrol: $4.2\%$
- Conversion Rate (CR) Treatment: $3.8\%$ (Treatment dinyatakan kalah secara signifikan, $p < 0.01$).

Namun, ketika data dibedah berdasarkan segmen pengguna:
- Pengguna Mobile: CR Kontrol $2.1\%$, CR Treatment $2.5\%$
- Pengguna Desktop: CR Kontrol $8.0\%$, CR Treatment $8.5\%$

Jelaskan mekanisme kausalitas matematis yang menyebabkan Paradoks Simpson ini terjadi. Variabel pengganggu (*confounder*) apa yang terabaikan dalam pengacakan (*randomization*), dan uji hipotesis apa yang seharusnya diaplikasikan (misal: *Cochran-Mantel-Haenszel test*) untuk menetralisir efek tersebut?

### Soal 2.5: Trade-off Resampling (SMOTE) vs Class-Weighted Loss
Dalam menangani ketidakseimbangan kelas (*class imbalance*), terdapat dua pendekatan populer: oversampling sintetis (*Synthetic Minority Over-sampling Technique* - SMOTE) dan penyesuaian fungsi objektif (*cost-sensitive learning* / `class_weight='balanced'`).
1. Ulas mekanisme internal interpolasi linear ruang fitur berdimensi tinggi pada SMOTE dan jelaskan risiko timbulnya *noise bridging* serta pelanggaran batas keputusan (*decision boundary degradation*).
2. Tinjau bagaimana `class_weight='balanced'` memodifikasi Hessian dan Gradien secara matematis pada algoritma *Gradient Boosted Decision Trees* (LightGBM/XGBoost) tanpa mengubah manifold data asli.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck Latensi Komputasi SHAP Values pada Pipeline Inferensi Real-Time
*Konteks Skala*: Sebuah institusi perbankan meluncurkan sistem *real-time automated loan approval*. Sistem ini menggunakan model *LightGBM* yang melayani $2.500$ *requests per second* (RPS) dengan batasan SLA latensi $p99 \le 40\text{ ms}$. Regulasi perbankan mewajibkan setiap penolakan pinjaman disertai dengan 3 faktor penjelas utama yang dihitung secara matematis menggunakan *TreeSHAP* (`shap.TreeExplainer`).

*Insiden*: Saat uji beban (*load testing*), latensi $p99$ melonjak hingga $450\text{ ms}$, memicu *timeout cascade* pada gateway microservice. Profiling menunjukkan bahwa 85% CPU time terserap oleh komputasi eksak `TreeExplainer.shap_values()`.

*Pertanyaan Diagnostik & Solusi*:
1. Jelaskan secara algoritmik mengapa komputasi eksak Shapley values memiliki kompleksitas tinggi dan bagaimana algoritma TreeSHAP memangkasnya menjadi polinomial, namun tetap tidak mampu memenuhi SLA latensi $40\text{ ms}$ pada beban 2.500 RPS.
2. Rancang arsitektur rekayasa inferensi (*inference engineering*) untuk memecahkan bottleneck ini. Pertimbangkan strategi *asynchronous background explainability*, aproksimasi *interventional TreeSHAP*, *feature attribution caching*, atau penyederhanaan kompleksitas pohon (*tree depth vs latency trade-off*). Berikan justifikasi teknis arsitektur pilihan Anda.

---

### Skenario B: Target Leakage Terselubung pada Sistem Deteksi Penipuan Finansial
*Konteks Skala*: Tim Data Science mengembangkan model deteksi pencucian uang (*Anti-Money Laundering* / AML). Di lingkungan *offline backtesting*, model XGBoost mencapai performa fantastis: PR-AUC $0.94$ dan False Positive Rate hanya $0.01\%$. Namun, saat di-*deploy* ke mode *shadow execution* di *production*, performa model hancur: PR-AUC turun menjadi $0.18$, menghasilkan puluhan ribu transaksi sah yang terblokir secara keliru.

*Investigasi*: Arsitektur *feature store* mengagregasi data transaksi dengan pipeline streaming (Kafka -> Flink -> Redis). Salah satu fitur utama adalah `sum_failed_trans_last_24h` dan `account_status_flag`.

*Pertanyaan Diagnostik & Solusi*:
1. Tunjukkan bagaimana kebocoran target (*target leakage*) atau bias tinjauan ke belakang (*lookahead bias*) dapat masuk ke dalam *feature store* selama proses *backfill* data historis offline vs bagaimana data tersebut ditulis di *production event pipeline*.
2. Rancang metode validasi data *Point-in-Time Correctness* (PIT-Join / Time-travel query) untuk memastikan bahwa matriks fitur pelatihan hanya menggunakan state data yang benar-benar eksis *persis sebelum* timestamp transaksi terjadi ($\Delta t - \epsilon$). Tuliskan skema verifikasi integritas fitur tersebut.

---

### Skenario C: Dilema Regulasi: Black-Box XGBoost vs. Constrained Explainable Generalized Additive Model (GAM)
*Konteks Skala*: Perusahaan asuransi kesehatan sedang merevisi model *pricing risk premium*. Tim A mengajukan model *Deep Neural Network + XGBoost Ensemble* dengan Gini Coefficient $0.62$. Tim B mengajukan model *Explainable Boosting Machine* (EBM) / *Generalized Additive Models with Constraints* (GAMs) dengan Gini Coefficient $0.58$.

*Kendala Regulasi & Bisnis*:
1. Otoritas Jasa Keuangan (OJK) mewajibkan bahwa premi tidak boleh diskriminatif secara kausalitas terbalik (misal: jika umur meningkat, risiko murni tidak boleh menurun secara fluktuatif hanya karena anomali data sampel lokal). Model harus memiliki sifat *Monotonicity Constraints*.
2. Sistem harus bebas dari *proxy discrimination* (variabel non-sensitif yang menjadi representasi tersembunyi dari suku, agama, atau kondisi disabilitas).

*Pertanyaan Diagnostik & Solusi*:
1. Mengapa model unconstrained XGBoost berkinerja lebih tinggi sering kali mengeksploitasi *spurious correlation* yang melanggar batas monotonicity, dan bagaimana Anda mengimplementasikan *Monotonic Constraints* di XGBoost (`monotone_constraints`)?
2. Buat analisis trade-off komprehensif (Akurasi Finansial vs *Auditability* Regulasi vs *Legal Liability*) antara memilih model performa murni (Tim A) versus model *glass-box* terikat batas matematis (Tim B). Dalam kondisi apa Tim A mutlak ditolak?

---

## 4. Chapter Challenge

### Tantangan Praktis: Rekayasa Pipeline Inferensial & Predictive Scoring Berstandar Audit dengan Guardrail Anti-Leakage

#### Deskripsi Masalah
Sebagai Principal Data/ML Engineer di sebuah perusahaan *Fintech P2P Lending*, Anda ditugaskan membangun pipeline pemodelan risiko kredit (*Credit Default Prediction*) yang harus memenuhi dua pilar:
1. **Pilar Inferensi Statistik**: Menyajikan model inferensial berbasis Regresi Logistik teratur (dengan interval kepercayaan dan p-value terkoreksi) untuk diserahkan ke komite audit risiko perbankan.
2. **Pilar Prediktif Produksi**: Menyajikan model prediktif berbasis *Scikit-Learn Pipeline* yang tahan terhadap kebocoran data (*leakage-proof*), menggunakan *nested cross-validation*, terkalibrasi secara probabilitas, dan siap diekspor ke format inferensi biner.

#### Requirements Teknis
1. **Data Preprocessing & Custom Transformers**:
   - Buat custom transformer Scikit-Learn: `OutlierWinsorizer` (menggunakan metode interquartile range / IQR) dan `WeightOfEvidenceEncoder` khusus fitur kategorikal yang *hanya* melakukan fitting pada target fold pelatihan untuk mencegah leakage.
   - Integrasikan seluruh alur pembersihan ke dalam satu objek `sklearn.pipeline.Pipeline`.
2. **Statistical Inferential Layer**:
   - Buat fungsi yang mengekstraksi matriks kovarian dan menghitung *Standard Error*, *Wald Chi-Square Statistic*, dan *p-values* yang disesuaikan (*adjusted p-values* menggunakan metode Benjamini-Hochberg FDR) untuk setiap fitur yang diuji.
   - Deteksi heteroskedastisitas menggunakan uji Breusch-Pagan dan otomatis ubah matriks kovarian menggunakan *Heteroskedasticity-Consistent Covariance Matrix Estimator* (Robust Standard Errors: HC3) jika terbukti heteroskedastik.
3. **Robust Predictive Layer**:
   - Gunakan skema validasi `StratifiedKFold(n_splits=5)`.
   - Lakukan kalibrasi probabilitas menggunakan `CalibratedClassifierCV` dengan metode `isotonic` atau `sigmoid` melalui evaluasi Brier Score.
   - Hitung metrik evaluasi akhir: PR-AUC, ROC-AUC, Brier Score Loss, dan matriks biaya penalti bisnis ($Cost = 10 \times FN + 1 \times FP$).
4. **Constraints & Strict Rules**:
   - Dilarang keras memanggil `.fit()` atau `.fit_transform()` pada data validasi/pengujian.
   - Seluruh pipeline Scikit-Learn tidak boleh bergantung pada variabel global.
   - Kode harus berorientasi objek (*clean code*), memiliki pengetikan statis (*type hints*), dan *docstrings* berstandar Sphinx/NumPy.

#### Format Output yang Diharapkan
1. **Class Architecture**: Implementasi kelas lengkap berbasis Python (`CreditRiskModelingPipeline`).
2. **Tabel Ringkasan Inferensi Statistik**:
   ```text
   +-------------------+-------------+------------+---------+-------------------+---------------+
   | Feature           | Coefficient | Robust SE  | Wald z  | Adjusted p (FDR)  | Sig Flag      |
   +-------------------+-------------+------------+---------+-------------------+---------------+
   | debt_to_income    | 0.4521      | 0.0312     | 14.49   | < 0.0001          | ***           |
   | num_delinquencies | 0.8912      | 0.1145     | 7.78    | < 0.0001          | ***           |
   | ...               | ...         | ...        | ...     | ...               | ...           |
   +-------------------+-------------+------------+---------+-------------------+---------------+
   ```
3. **Model Calibration Curve**: Plot kalibrasi (Reliability Diagram) yang membandingkan probabilitas prediksi vs fraksi positif empiris sebelum dan sesudah kalibrasi.
4. **Cost Optimization Curve**: Visualisasi threshold keputusan optimal yang meminimalkan kerugian finansial bisnis terhadap ambang batas probabilitas standar $0.5$.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan fundamental antara tujuan pemodelan inferensial (estimasi parameter $\beta$, interval kepercayaan, uji hipotesis) dan pemodelan prediktif (minimasi fungsi kerugian $\mathcal{L}(y, \hat{y})$ pada *unseen data*).
- [ ] Mengapa *p-value* bukan ukuran besaran efek (*effect size*) dan bagaimana *sample size* yang masif dapat membuat perbedaan sepele menjadi "secara statistik signifikan" (*p-value hacking via sample size*).
- [ ] Kondisi matematika di balik dekomposisi bias-varians (*Bias-Variance Decomposition*) dan bagaimana L1/L2 regularization menukar sedikit bias untuk reduksi varians yang masif.
- [ ] Geometri batas keputusan regresi logistik dan generalisasinya ke *Generalized Linear Models* (GLM) dengan berbagai fungsi tautan (*link functions*).
- [ ] Dampak kebocoran informasi (*data leakage*) rantai preprocessing (scaling, imputation, feature selection) terhadap reliabilitas metrik cross-validation.
- [ ] Karakteristik ROC-AUC vs PR-AUC pada data terdistribusi miring ekstrem (*extreme class imbalance*).
- [ ] Arti penting probabilitas terkalibrasi (*calibrated probabilities*) pada sistem otomasi keputusan berbasis cost-matrix.

### Saya tidak perlu menghafal:
- [ ] Formula analitik turunan parsial untuk setiap variasi robust covariance estimator (misal: formula eksak HC0, HC1, HC2, HC3). Cukup pahami fungsinya untuk mengoreksi standard error ketika varians residual tidak konstan.
- [ ] Nilai kritis tabel distribusi $t$, $Z$, atau $F$ pada tingkat signifikansi $\alpha = 0.05$ atau $0.01$. Biarkan modul komputasi (`scipy.stats`) menghitungnya secara eksak.
- [ ] Sintaks parameter tingkat rendah dari algoritma *hyperparameter optimization* (misal: parameter internal solver C-code pada liblinear/libsvm). Cukup pahami intuisi hyperparameter utama: regularisasi $C$, $\alpha$, $\lambda$, *learning rate*, dan *max depth*.

### Saya harus bisa melakukan:
- [ ] Merancang pipeline pengujian hipotesis statistik multivariat lengkap menggunakan `statsmodels` dengan validasi asumsi residu (Normality, Homoscedasticity, Multicollinearity via VIF).
- [ ] Mengoreksi bias uji signifikansi simultan (*multiple hypothesis testing*) menggunakan koreksi Bonferroni atau *False Discovery Rate* (FDR - Benjamini-Hochberg) untuk menghindari False Discovery explosion.
- [ ] Mengembangkan *Custom Transformer* Scikit-Learn yang aman (*leakage-proof*) menggunakan antarmuka `BaseEstimator` dan `TransformerMixin`.
- [ ] Mengonfigurasi skema validasi silang yang tepat (*TimeSeriesSplit*, *GroupKFold*, *StratifiedKFold*) sesuai struktur ketergantungan data produksi.
- [ ] Melakukan probabilitas kalibrasi menggunakan `CalibratedClassifierCV` dan mengevaluasi kualitas kalibrasi menggunakan *Brier Score Loss* dan diagram reliabilitas.
- [ ] Menentukan threshold probabilitas klasifikasi optimal yang meminimalkan matriks kerugian biaya moneter (*expected business loss minimization*), bukan sekadar mengandalkan default threshold 0.5.