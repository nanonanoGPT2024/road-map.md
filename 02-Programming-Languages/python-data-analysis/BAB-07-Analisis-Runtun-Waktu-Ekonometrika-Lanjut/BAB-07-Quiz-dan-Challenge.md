# BAB 07: Quiz, Challenge, & Knowledge Check
**Analisis Runtun Waktu & Ekonometrika Lanjut (Time Series)**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Strict Stationarity vs. Weak (Covariance) Stationarity & Spurious Regression
Jelaskan perbedaan matematis fundamental antara *Strict Stationarity* dan *Weak (Covariance) Stationarity*. Mengapa asumsi *Weak Stationarity* sudah mencukupi untuk metodologi Box-Jenkins (ARMA/ARIMA)? Uraikan pula konsekuensi matematis terhadap estimator Ordinary Least Squares (OLS) ketika dua variabel non-stasioner independen yang terintegrasi pada orde satu, $I(1)$, diregresikan satu sama lain (*spurious regression*), khususnya pengaruhnya terhadap distribusi nilai $t$-statistic dan $R^2$.

### Soal 1.2: Mekanisme Dualitas ACF dan PACF dalam Identifikasi Model ARMA
Dalam identifikasi spesifikasi model ARMA$(p, q)$ linier:
1. Mengapa Autocorrelation Function (ACF) meluruh secara eksponensial/sinusoidal (*tails off*) untuk proses Autoregressive (AR), sementara Partial Autocorrelation Function (PACF) terputus (*cuts off*) tepat setelah lag $p$? Buktikan relasi ini secara konseptual menggunakan persamaan Yule-Walker.
2. Jelaskan dualitas perilaku di atas jika diterapkan pada proses Moving Average (MA) murni orde $q$.

### Soal 1.3: Uji Akar Unit Komplementer (ADF vs. KPSS) dan Dampak Structural Break
Uji Augmented Dickey-Fuller (ADF) dan Kwiatkowski-Phillips-Schmidt-Shin (KPSS) sering digunakan bersamaan sebagai *confirmatory data analysis*.
1. Bandingkan formulasi hipotesis nol ($H_0$) dan hipotesis alternatif ($H_1$) dari kedua uji tersebut, serta jelaskan interpretasi operasional ketika ADF menolak $H_0$ dan KPSS juga menolak $H_0$.
2. Jelaskan fenomena *Perron Effect* (1989): bagaimana keberadaan satu *structural break* permanen pada level/intersep dapat membiaskan uji ADF standar sehingga gagal menolak hipotesis akar unit (*false non-rejection*).

### Soal 1.4: Kointegrasi (Engle-Granger & Johansen) vs. Differencing
Banyak praktisi data pemula melakukan diferensiasi derajat satu ($d=1$) pada setiap data $I(1)$ untuk menjamin kestasioneran sebelum pelatihan model regresi.
1. Informasi fundamental apa yang hilang (*loss of long-run equilibrium dynamics*) ketika kita mendiferensiasi runtun waktu yang sebenarnya memiliki hubungan kointegrasi?
2. Bagaimana Vector Error Correction Model (VECM) mengatasi *trade-off* antara dinamika jangka pendek (*short-run adjustments*) dan keseimbangan jangka panjang (*long-run cointegrating vector*) dibandingkan pemodelan VAR murni pada data selisih?

### Soal 1.5: Volatility Clustering dan Karakteristik ARCH/GARCH
Model runtun waktu linier (seperti ARIMA) mengasumsikan varians residual konstan (*homoskedasticity*).
1. Definisikan fenomena *volatility clustering* dan *fat tails* (kurtosis tinggi) pada runtun waktu finansial/operasional. Mengapa model ARIMA standar gagal menangkap dinamika risiko pada data jenis ini?
2. Jelaskan formulasi struktural model GARCH$(1,1)$ untuk conditional variance ($\sigma_t^2$) dan sebutkan batasan nilai parameter ($\omega, \alpha, \beta$) agar kestasioneran kovarians terpenuhi.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Lookahead Bias pada Preprocessing & Imputasi Runtun Waktu
Perhatikan cuplikan pipeline ekstraksi fitur untuk model prediksi harga komoditas berikut:

```python
# Raw DataFrame dengan DatetimeIndex berfrekuensi harian
df["target_diff"] = df["price"].diff()

# Normalisasi Min-Max
scaler = MinMaxScaler()
df["scaled_price"] = scaler.fit_transform(df[["price"]])

# Imputasi nilai hilang akibat noise sensor/libur bursa
df["interpolated_volume"] = df["volume"].interpolate(method="time")

# Ekstraksi fitur moving average
df["rolling_mean_7d"] = (
    df["scaled_price"].rolling(window=7, center=True).mean()
)
```

Identifikasi minimal **tiga kesalahan fatal** terkait *lookahead bias* / *data leakage* dalam kode di atas yang akan merusak validitas evaluasi *out-of-sample*, jelaskan mekanisme kerusakannya, dan tuliskan perbaikan kodenya.

### Soal 2.2: Diagnostik Invertibilitas dan Ketidakstabilan Numerik pada Estimasi MLE SARIMAX
Ketika mengeksekusi `statsmodels.tsa.statespace.sarimax.SARIMAX` dengan parameter estimasi Maximum Likelihood (MLE), fungsi optimasi (misalnya `L-BFGS-B`) sering kali memunculkan peringatan:

```text
UserWarning: Non-invertible starting MA parameters found. Using zeros as starting parameters.
ConvergenceWarning: Maximum Likelihood optimization failed to converge. Check mle_retries.
```

1. Apa definisi matematis dari kondisi *invertibility* pada komponen MA dan kondisi *stationarity* pada komponen AR ditinjau dari posisi akar karakteristik polinomial (*characteristic polynomial roots*) terhadap *unit circle* bidang kompleks?
2. Bagaimana `statsmodels` memaksakan transformasi parameter agar memenuhi batasan ini secara internal (misalnya menggunakan transformasi Jonquières atau *partial autocorrelation transform*), dan mengapa estimasi tetap bisa gagal konvergen?
3. Langkah teknis apa yang harus dilakukan *engineer* untuk mendebug dan memperbaiki model tersebut tanpa mengorbankan integritas data?

### Soal 2.3: Asimtotika Pemilihan Model: AIC vs. BIC pada Sampel Masif
Diberikan matriks evaluasi informasi untuk pemilihan orde lag ARMA:
$$\text{AIC} = 2k - 2\ln(\hat{L}), \quad \text{BIC} = k\ln(n) - 2\ln(\hat{L})$$
1. Buktikan secara teoretis mengapa kriteria AIC bersifat *asymptotically efficient* tetapi tidak konsisten (*inconsistent*), sehingga cenderung memilih model yang *overparameterized* (terlalu banyak lag) ketika ukuran sampel $n \to \infty$.
2. Dalam skenario apa di sistem produksi Anda secara spesifik memilih BIC dibandingkan AIC, dan sebaliknya? Analisis dampaknya terhadap *inference latency* dan risiko *generalization error*.

### Soal 2.4: Anomali Alignment Temporal pada Pandas Resampling & GBDTs
Ketika mengagregasi data transaksi berfrekuensi tinggi (misalnya data limit order book / tick logs) ke dalam interval 5 menit menggunakan pandas:

```python
aggregated_df = tick_df.resample("5min", label="right", closed="right").agg(
    {"price": "ohlc", "volume": "sum"}
)
```

1. Jelaskan perbedaan semantik antara parameter `label='left'`/`closed='left'` vs. `label='right'`/`closed='right'`. 
2. Jika data hasil agregasi ini akan digabungkan (*merge_asof*) dengan fitur makroekonomi yang dirilis harian untuk melatih model regresi berbasis Gradient Boosted Trees (LightGBM/XGBoost), bagaimana kesalahan pemilihan `label` dan `closed` dapat menciptakan *leakage* temporal mikro-detik yang menyebabkan kinerja pengujian tampak sempurna tetapi gagal total di *live environment*?

### Soal 2.5: Purged & Embargoed Cross-Validation vs. Standard TimeSeriesSplit
Metode standar `sklearn.model_selection.TimeSeriesSplit` menggunakan skema *walk-forward* ekspansif. 
1. Mengapa skema `TimeSeriesSplit` standar tetap menghasilkan bias optimistik (overfitting) pada data finansial dan runtun waktu yang memiliki autokorelasi serial residual yang panjang atau menggunakan label bertipe *overlapping* (misalnya *triple-barrier method*)?
2. Jelaskan arsitektur mekanisme **Purging** dan **Embargoing** (merujuk pada metodologi Marcos Lopez de Prado). Bagaimana keduanya secara matematis memotong kebocoran korelasi antar-fold pada data pelatihan dan validasi?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck Latensi Estimasi pada Pipeline Real-Time IoT Skala Besar
Sebuah perusahaan logistik rantai dingin (*cold-chain logistics*) memantau suhu dan getaran dari 25.000 kontainer kargo aktif di seluruh dunia menggunakan sensor telemetri yang mengirimkan data setiap 10 detik. Sistem arsitektur saat ini menggunakan pipeline berbasis Python/Celery worker yang melakukan evaluasi anomali secara lokal untuk tiap kontainer. 

Setiap 1 jam, worker mencoba mengeksekusi model `AutoARIMA` (menggunakan `pmdarima`) secara independen untuk tiap kontainer guna memprediksi ambang batas dinamis 30 menit ke depan. Akibatnya:
- Antrean *message broker* (RabbitMQ) meledak (lebih dari 1.000.000 tugas tertunda).
- Utilisasi CPU mencapai 100% dengan memory footprint per worker melonjak drastis, menyebabkan *Out-Of-Memory (OOM) Killer* menonaktifkan proses secara berulang.
- Latensi kalkulasi per batch melampaui jendela 1 jam, menyebabkan data prediksi basi (*stale*) dan kegagalan deteksi kerusakan komoditas bernilai tinggi.

**Pertanyaan Diagnostik & Arsitektur:**
1. Lakukan audit teknis: Mengapa pemanggilan `AutoARIMA` per kontainer pada skala 25.000 entitas secara arsitektural salah fatal untuk *real-time execution*? Tinjau kompleksitas komputasi fitting MLE berulang ($O(N \cdot iterations \cdot grid)$).
2. Rancang ulang arsitektur model ini secara menyeluruh. Bagaimana Anda mentransisikan sistem dari fitting model ARIMA individual per jam ke pendekatan yang lebih terukur (misalnya: representasi State-Space menggunakan Kalman Filtering dengan *online recursive updates*, Global Time Series Models, atau model linearisasi terdistribusi)?
3. Tentukan strategi komputasi matriks yang harus diterapkan (misalnya eksploitasi PyTorch/JAX untuk vektorisasi dimensi kontainer secara paralel pada GPU vs. agregasi multi-resolusi).

### Skenario B: Target Leakage & False Alpha pada Platform Algorithmic Trading
Sebuah tim kuantitatif meluncurkan strategi *statistical arbitrage* berbasis pasangan instrumen (*pairs trading*) kripto frekuensi menengah. Model dilatih menggunakan data tick historis selama 12 bulan yang di-resample ke interval 1 menit. 

Hasil *backtest* simulasi *walk-forward* menghasilkan metrik performa yang luar biasa: Sharpe Ratio 4.8, Maximum Drawdown hanya 2.1%, dan rasio kemenangan (*win-rate*) mencapai 74%. Namun, saat di-deploy ke sistem *paper trading* dan *canary production execution*:
- Strategi langsung mengalami penarikan modal (*drawdown*) sebesar 14.5% dalam 72 jam pertama.
- Model secara konsisten masuk ke posisi beli (*long*) atau jual (*short*) tepat sebelum pembalikan tren lokal (*mean-reversion*), tetapi harga eksekusi di pasar riil selalu bergeser drastis dari harga proyeksi model (*massive slippage*).

Hasil investigasi kode menemukan potongan logika berikut:
```python
# Menghitung spread antara dua aset A dan B
spread = df["Asset_A"] - beta * df["Asset_B"]

# Menggunakan Z-score untuk sinyal entry/exit
rolling_window = 60  # 60 menit
spread_mean = spread.rolling(window=rolling_window).mean()
spread_std = spread.rolling(window=rolling_window).std()
df["z_score"] = (spread - spread_mean) / spread_std

# Estimasi nilai Cointegration Vector (Beta)
# Beta dihitung satu kali menggunakan seluruh dataset (12 bulan) dengan OLS
model = sm.OLS(df["Asset_A"], df["Asset_B"]).fit()
beta = model.params[0]
```

**Pertanyaan Diagnostik & Forensik:**
1. Bedah secara mendalam setidaknya **tiga titik kebocoran data (*information leakage*)** dan asumsi salah kaprah dalam potongan logika dan proses evaluasi di atas.
2. Jelaskan mengapa estimasi parameter $\beta$ tunggal (*static beta*) di muka menggunakan seluruh dataset menghasilkan bias kognitif sistem (*lookahead bias*) yang merusak estimasi matriks varians-kovarians residual.
3. Rancang prosedur perbaikan: Bagaimana cara mengestimasi $\beta$ secara adaptif (misalnya melalui *Rolling OLS* tanpa lookahead, atau *Kalman Filter State-Space Tracking*), dan bagaimana memvalidasi sinyal eksekusi agar memperhitungkan *order book latency* dan biaya transaksi struktural?

### Skenario C: Trade-off Arsitektur: Ekonometrika Klasik vs. Deep Learning vs. GBDT untuk Peramalan Makro-Finansial Ter-regulasi
Sebuah bank sistemik nasional (*Tier-1 Bank*) diwajibkan oleh regulator moneter untuk membangun sistem stress testing likuiditas dan proyeksi rasio kredit macet (Non-Performing Loan / NPL) multivariat untuk rentang proyeksi 8 kuartal ke depan. 

Sistem ini memiliki batasan ketat:
1. **Regulator Requirement:** Model tidak boleh berupa *black-box*; hubungan kausalitas, mekanisme transmisi guncangan suku bunga acuan moneter (*monetary shock transmission*), dan interval kepercayaan (*confidence intervals*) harus dapat dibuktikan secara matematis di hadapan komite audit regulasi.
2. **Data Constraints:** Data historis yang tersedia hanya data kuartalan sejak tahun 1998 (~100 observasi per variabel macro, total ~15 variabel).
3. **Engineering Request:** Tim Data Science mengusulkan penggunaan arsitektur Deep Learning terkini (seperti Temporal Fusion Transformer / TFT) atau Temporal GBDTs dengan alasan performa metrik loss (RMSE) yang lebih unggul pada data validasi.

**Pertanyaan Diagnostik & Pengambilan Keputusan Arsitektur:**
1. Berikan argumentasi teknis mendalam mengapa usulan penggunaan model Deep Learning (TFT) pada dataset dengan $N \approx 100$ observasi adalah bencana arsitektur (*architectural anti-pattern*). Tinjau dari sudut pandang *Curse of Dimensionality*, parameter-to-sample ratio, dan varians estimasi.
2. Susun arsitektur peramalan yang optimal untuk memenuhi kebutuhan regulasi dan data terbatas tersebut menggunakan ekonometrika lanjutan (misalnya: Structural Vector Autoregression / SVAR atau Bayesian Vector Error Correction Model / BVECM).
3. Bagaimana Anda merancang pengujian dinamis respons guncangan (*Impulse Response Functions* - IRF) dan dekomposisi varians kesalahan peramalan (*Forecast Error Variance Decomposition* - FEVD) dalam pipeline tersebut untuk memvalidasi efek transmisi suku bunga terhadap NPL secara teruji?

---

## 4. Chapter Challenge

### Tantangan Praktis: Production-Grade Robust Econometric & Volatility Forecasting Engine dengan Backtesting Bebas Leakage

#### Deskripsi Masalah
Sebagai Principal Financial Data Architect, Anda ditugaskan membangun modul inti analisis dan prediksi risiko ekonometrik untuk platform manajemen portofolio institusional. Sistem harus mampu menerima runtun waktu instrumen finansial berfrekuensi harian, memvalidasi dan memproses stasionaritas data, melakukan pemilihan model SARIMAX secara otomatis (Auto-Order Selection) berdasarkan kriteria informasi, memodelkan conditional heteroskedasticity residual menggunakan GARCH, serta mengevaluasi Value-at-Risk (VaR) 1-hari ke depan menggunakan metode *Purged & Embargoed Rolling Walk-Forward Backtest*.

#### Requirements Implementasi
Anda harus menulis implementasi Python yang modular, *clean-code*, dan memenuhi spesifikasi teknis berikut:

1. **Stationarity Assessment Pipeline:**
   - Implementasikan fungsi diagnostik otomatis yang mengeksekusi uji ADF dan KPSS secara simultan.
   - Buat logika penentu transformasi: Jika data non-stasioner, lakukan diferensiasi hingga mencapai stasionaritas $I(0)$ (maksimal $d=2$). Catat urutan diferensiasi untuk rekonsiliasi inversi proyeksi.

2. **Automated Dynamic SARIMAX Modeling:**
   - Bangun fungsi pemilihan lag grid search $(p, d, q)$ berbasis penalti Bayesian Information Criterion (BIC).
   - Pastikan model menyertakan penanganan kondisi ketika optimasi MLE gagal konvergen atau menghasilkan koefisien non-stasioner/non-invertibel (menggunakan fallback ke orde yang lebih rendah secara elegan tanpa melempar unhandled exception).

3. **GARCH Residual Volatility Modeling:**
   - Ekstraksi standardized residuals dari model SARIMAX optimal.
   - Fit model GARCH(1,1) (menggunakan pustaka `arch`) pada residual tersebut untuk mengekstraksi conditional variance $\sigma_{t+1}^2$.
   - Hitung estimasi risiko Value-at-Risk dinamis: $\text{VaR}_{\alpha, t+1} = \hat{\mu}_{t+1} + z_{\alpha} \cdot \hat{\sigma}_{t+1}$ pada tingkat signifikansi $\alpha = 0.05$ dan $\alpha = 0.01$.

4. **Leakage-Free Rolling Walk-Forward Evaluator:**
   - Bangun kelas backtester yang mengimplementasikan *expanding* atau *rolling window* berukuran tetap.
   - Wajib menyertakan *Purging* (menghapus tumpang tindih data) dan *Embargoing* (buffer pemisah temporal sebesar $h$ observasi antara fold latih dan fold uji).
   - Seluruh tahapan imputasi, penskalaan, dan differencing harus difit **hanya** pada fold latih pada setiap iterasi langkah waktu $t$, kemudian diterapkan ke langkah waktu $t+1$.

5. **Risk Metrics & Validation:**
   - Lakukan pengujian formal terhadap keandalan estimasi VaR menggunakan **Kupiec POF (Proportion of Failures) Test** untuk mengevaluasi apakah rasio *VaR exceedance/violation* konsisten secara statistik dengan tingkat kepercayaan $\alpha$ yang dipilih.

#### Constraints
- Dilarang keras menggunakan data titik waktu $t+1$ pada sembarang transformasi data sebelum titik $t$.
- Gunakan `statsmodels`, `arch`, `numpy`, `pandas`, dan `scipy`.
- Seluruh pipeline kalkulasi per rolling step harus memiliki waktu eksekusi yang terkendali (definisikan *bounded iteration* dan hindari perulangan eksplisit yang tidak perlu).
- Kode harus dilengkapi *type hints*, *error handling*, dan *logging assertion*.

#### Expected Output
1. Script Python lengkap yang merepresentasikan kelas implementasi:
   - `EconometricRiskEngine`
   - `PurgedWalkForwardCV`
   - `KupiecBacktester`
2. Laporan output evaluasi diagnostik yang mencakup:
   - Nilai estimasi $p, d, q$ optimal per window tertentu.
   - Estimasi volatilitas bersyarat dan plot interval VaR terhadap realisasi return.
   - Hasil uji Kupiec POF ($LR$-statistic dan $p$-value) yang menyatakan apakah model risiko diterima (*accept*) atau ditolak (*reject*) oleh sistem audit internal.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Batasan matematis antara proses stasioner lemah (*covariance stationary*), *trend stationary*, dan *difference stationary* ($I(d)$).
- [ ] Formulasi teoritis dan representasi State-Space dari model ARIMA, SARIMAX, dan pemodelan volatilitas ARCH/GARCH.
- [ ] Implikasi teoretis dari Teorema Representasi Granger (*Granger Representation Theorem*) terkait keterkaitan kointegrasi dan Error Correction Model (ECM).
- [ ] Perilaku matematika uji akar unit (ADF, KPSS, Phillips-Perron) serta kerentanannya terhadap *structural break* dan panjang lag residual.
- [ ] Mengapa metrik evaluasi regresi standar (seperti $R^2$ konvensional) menjadi bias dan tidak valid pada data runtun waktu non-stasioner.
- [ ] Mekanisme matematis terjadinya bias kebocoran data (*lookahead leakage*) dalam transformasi multivariat, agregasi temporal, dan skema *cross-validation* sekuensial.

### Saya tidak perlu menghafal:
- [ ] Tabel nilai kritis persentil statistik Dickey-Fuller, MacKinnon, atau distribusi asymptotic Johansen Trace/Max-Eigenvalue (gunakan modul dependensi otomatis `statsmodels`).
- [ ] Kode sumber derivasi optimasi algoritma numerik internal BFGS, Nelder-Mead, atau Powell pada `statsmodels.tools`.
- [ ] Seluruh kombinasi hyperparameter konfigurasi musiman SARIMAX tingkat tinggi (gunakan algoritma seleksi terarah berbasis informasi seperti AIC/BIC).
- [ ] Implementasi manual aljabar linier tingkat rendah untuk inversi matriks kovarians autokorelasi berdimensi masif (cukup pahami batas kompleksitas komputasionalnya, gunakan implementasi BLAS/LAPACK yang teroptimasi).

### Saya harus bisa melakukan:
- [ ] Mengidentifikasi, mendebug, dan memusnahkan secara presisi segala bentuk *data leakage* temporal pada pipeline persiapan data runtun waktu skala produksi.
- [ ] Merancang pipeline ekonometrika modular yang memadukan transformasi stasioneritas adaptif, optimasi estimasi model SARIMAX, dan estimasi volatilitas GARCH.
- [ ] Mengimplementasikan skema validasi temporal ketat (*Purged & Embargoed Walk-Forward Cross-Validation*) dari awal (*from scratch*) tanpa bergantung pada modul naive standar.
- [ ] Mengaudit model deret waktu terdistribusi dalam arsitektur berskala besar dan merefaktornya dari bottleneck O($N$) eksekusi MLE individual ke pendekatan yang terukur (*scalable/vectorized state-space filters*).
- [ ] Mengevaluasi dan memvalidasi keandalan model risiko finansial secara kuantitatif menggunakan uji statistik formal seperti Kupiec Likelihood Ratio Test dan Christoffersen Independence Test.