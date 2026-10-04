# Kurikulum Rekayasa Data & Ekonometrika Kuantitatif Enterprise
## BAB 07: Analisis Runtun Waktu & Ekonometrika Lanjut
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Merancang & Mengimplementasikan Model Sistem Multivariat**: Menguasai formulasi matematis dan implementasi *Vector Error Correction Model* (VECM) dan Uji Kointegrasi Johansen untuk mengidentifikasi relasi ekuilibrium jangka panjang pada data non-stasioner terintegrasi $I(1)$.
- **Membangun Dynamic State-Space Filter**: Mengabstraksi dan mengeksekusi *Kalman Filter* untuk estimasi parameter *time-varying* secara real-time pada sistem linier stokastik berkecepatan tinggi.
- **Memodelkan Volatilitas Asimetris & Heteroskedastisitas**: Mengimplementasikan kelas model GARCH/EGARCH untuk estimasi matriks varians-kovarians dinamis dan *Value at Risk* (VaR).
- **Membangun Arsitektur Produksi Rendah Latensi**: Membangun *pipeline* inferensi bebas *lookahead-bias* dengan latensi sub-50ms menggunakan integrasi `statsmodels`, `arch`, dan `numpy` berbasis arsitektur *event-driven*.
- **Mitigasi Masalah Numerik**: Menangani singularitas matriks, divergensi filter, dan instabilitas kovarians melalui faktorisasi Cholesky dan *Joseph form covariance update*.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta harus menguasai:
1. **Statistika & Ekonometrika Dasar**: Uji Stasionaritas (ADF, KPSS), ARIMA/SARIMAX, konsep autokorelasi (ACF/PACF), dan estimasi *Ordinary Least Squares* (OLS).
2. **Aljabar Linier Lanjut**: Dekomposisi Eigendecomposition, Singular Value Decomposition (SVD), Faktorisasi Cholesky, serta kalkulus matriks multivariat.
3. **Python Engineering**: Pemrograman berorientasi objek tingkat lanjut, *type hinting* mutlak (`typing`), manipulasi vektor NumPy tingkat tinggi, dan pemanfaatan pustaka `statsmodels` serta `arch`.

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 Teorema Representasi Granger & Vector Error Correction Model (VECM)

Ketika $K$ buah variabel runtun waktu tidak stasioner pada levelnya tetapi terintegrasi pada ordo yang sama, dinotasikan sebagai $Y_t \sim I(1)$, regresi OLS langsung akan memicu regresi lancung (*spurious regression*). Namun, jika terdapat kombinasi linier dari variabel-variabel tersebut yang menghasilkan residual stasioner $I(0)$, variabel-variabel tersebut dikatakan **terkointegrasi**.

Berdasarkan *Granger Representation Theorem*, sistem kointegrasi VAR($p$) dapat diformulasikan ulang menjadi VECM:

$$\Delta Y_t = \Pi Y_{t-1} + \sum_{i=1}^{p-1} \Gamma_i \Delta Y_{t-i} + \Phi D_t + \epsilon_t$$

Di mana:
- $\Delta Y_t = Y_t - Y_{t-1}$.
- $\Pi = \sum_{j=1}^p A_j - I_K$. Matriks dampak jangka panjang (*long-run impact matrix*) berdimensi $K \times K$.
- $\Gamma_i = -\sum_{j=i+1}^p A_j$. Matriks koefisien dinamis jangka pendek.
- $D_t$ merepresentasikan vektor deterministik (konstanta, tren linier).
- $\epsilon_t \sim \text{i.i.d. } \mathcal{N}(0, \Sigma)$.

Matriks $\Pi$ menentukan sifat kointegrasi sistem melalui evaluasi *rank* ($r = \text{rank}(\Pi)$):
1. **$r = 0$**: Tidak ada kointegrasi. Model direduksi menjadi standar VAR pada diferensiasi pertama ($\Delta Y_t$).
2. **$r = K$**: Seluruh variabel pada dasarnya sudah stasioner pada level $I(0)$. Gunakan standar VAR level.
3. **$0 < r < K$**: Terdapat $r$ hubungan kointegrasi linier independen. Matriks $\Pi$ dapat difaktorisasi menjadi:
   $$\Pi = \alpha \beta'$$
   - $\beta$ ($K \times r$): Matriks vektor kointegrasi (*cointegrating vectors*) yang mendefinisikan ekuilibrium jangka panjang: $Z_{t-1} = \beta' Y_{t-1} \sim I(0)$.
   - $\alpha$ ($K \times r$): Matriks penyesuaian kecepatan (*speed of adjustment* atau *error correction coefficients*). Mengukur seberapa cepat sistem kembali ke garis ekuilibrium jika terjadi deviasi.

```
                      +-----------------------------+
                      |   Multivariate Series Y_t   |
                      +-----------------------------+
                                     |
                                     v
                      +-----------------------------+
                      |  Unit Root Tests (ADF/KPSS) |
                      +-----------------------------+
                                     |
                         All series are I(1)?
                                     |
                       +-------------+-------------+
                       | YES                       | NO
                       v                           v
        +-----------------------------+  +-------------------+
        | Johansen Cointegration Test |  | Use Standard VAR  |
        +-----------------------------+  | or Differencing   |
                       |                 +-------------------+
             Rank(Pi) = r ?
                       |
        +--------------+--------------+
        |                             |
      r = 0                         0 < r < K
        |                             |
        v                             v
+------------------+        +-------------------------+
| VAR(p) on Delta  |        | VECM: Pi = alpha * beta'|
| without ECT      |        | ECT = beta' * Y_{t-1}   |
+------------------+        +-------------------------+
```

#### 3.2 State-Space Model & Algoritma Rekursif Kalman Filter

Sistem runtun waktu dapat diekspresikan ke dalam ruang status (*State-Space Representation*). Format kanonikal sistem dinamis linier Gaussian adalah:

1. **Persamaan Transisi (State Equation)**:
   $$x_k = F_k x_{k-1} + B_k u_k + w_k, \quad w_k \sim \mathcal{N}(0, Q_k)$$
2. **Persamaan Pengukuran (Measurement Equation)**:
   $$z_k = H_k x_k + v_k, \quad v_k \sim \mathcal{N}(0, R_k)$$

Di mana:
- $x_k \in \mathbb{R}^n$ adalah vektor status tersembunyi (*latent state*) pada saat $k$.
- $z_k \in \mathbb{R}^m$ adalah vektor observasi aktual (*observable measurement*).
- $F_k$ adalah matriks transisi status (*state transition matrix*).
- $H_k$ adalah matriks observasi (*measurement matrix*).
- $Q_k \in \mathbb{R}^{n \times n}$ dan $R_k \in \mathbb{R}^{m \times m}$ adalah matriks kovarians *process noise* dan *measurement noise*.

Algoritma rekursif Kalman Filter beroperasi dalam siklus dua fase yang ketat:

##### Fase 1: Time Update (Predict)
Memproyeksikan status dan estimasi kovarians ke masa depan ($k-1 \to k$):
$$\hat{x}_{k|k-1} = F_k \hat{x}_{k-1|k-1} + B_k u_k$$
$$P_{k|k-1} = F_k P_{k-1|k-1} F_k' + Q_k$$

##### Fase 2: Measurement Update (Correct)
Mengoreksi proyeksi menggunakan realisasi data terbaru $z_k$:
- **Innovation / Measurement Residual**:
  $$y_k = z_k - H_k \hat{x}_{k|k-1}$$
- **Innovation Covariance**:
  $$S_k = H_k P_{k|k-1} H_k' + R_k$$
- **Optimal Kalman Gain**:
  $$K_k = P_{k|k-1} H_k' S_k^{-1}$$
- **Updated State Estimate**:
  $$\hat{x}_{k|k} = \hat{x}_{k|k-1} + K_k y_k$$
- **Updated Covariance Estimate (Joseph Form)** untuk stabilitas numerik terhadap pembulatan floating point:
  $$P_{k|k} = (I - K_k H_k) P_{k|k-1} (I - K_k H_k)' + K_k R_k K_k'$$

#### 3.3 Dynamic Volatility Modeling: GARCH(p, q)

Dalam model ekonometrika keuangan dan runtun waktu resolusi tinggi, varians residual $\epsilon_t$ tidak konstan (*heteroskedastic*). Model GARCH($p, q$) memodelkan varians kondisional $\sigma_t^2$ sebagai fungsi dari volatilitas masa lalu (*ARCH terms*) dan varians masa lalu (*GARCH terms*):

$$\epsilon_t = \sigma_t \eta_t, \quad \eta_t \sim \text{i.i.d. } \mathcal{N}(0, 1)$$
$$\sigma_t^2 = \omega + \sum_{i=1}^q \alpha_i \epsilon_{t-i}^2 + \sum_{j=1}^p \beta_j \sigma_{t-j}^2$$

Syarat stasionaritas kovarians:
$$\omega > 0, \quad \alpha_i \ge 0, \quad \beta_j \ge 0, \quad \sum_{i=1}^q \alpha_i + \sum_{j=1}^p \beta_j < 1$$

---

### 4. Why & What

| Dimensi | Pendekatan Klasik (OLS / Moving Average) | Pendekatan Lanjut (VECM + Kalman Filter + GARCH) |
| :--- | :--- | :--- |
| **Relasi Kointegrasi** | Mengabaikan sifat non-stasioner data, berisiko tinggi menghasilkan koefisien korelasi palsu ($R^2$ tinggi, Durbin-Watson rendah). | Mengisolasi *mean-reverting spread* jangka panjang ($\beta$) seraya mengekstrak koefisien penyesuaian dinamis ($\alpha$). |
| **Estimasi Parameter** | Asumsi parameter konstan/statis sepanjang masa observasi (*static hedge ratio*). | Parameter berevolusi secara dinamis terhadap waktu (*time-varying*) menggunakan *State-Space Representation*. |
| **Model Volatilitas** | Asumsi *homoskedasticity* (varians konstan). Mengabaikan fenomena *volatility clustering*. | Memodelkan *conditional heteroskedasticity* untuk penetapan margin risiko dinamis (*Value at Risk*). |
| **Arsitektur Produksi**| Rentan terhadap *lookahead bias* akibat normalisasi *in-sample* global (misal: `StandardScaler` di seluruh data). | Estimasi berbasis *sliding window* rekursif kausal. Kompatibel dengan *streaming* transaksi frekuensi tinggi. |

---

### 5. How (Workflow Detail)

Arsitektur siklus data ekonometrika end-to-end:

```
[Raw Ingestion] 
     │ (Tick/OHLCV via Kafka/ZeroMQ)
     ▼
[Resampling & Preprocessing]
     │ Data Aligned DateTimeIndex (UTC)
     ▼
[Unit Root Testing Stage]
     ├─ ADF Test (Stationarity of Level)
     └─ KPSS Test (Stationarity Verification)
     │
     ├─ [All I(1)] ──> [Johansen Cointegration Test]
     │                      │
     │                      ├─ Trace Stat > Critical Value?
     │                      └─ Max-Eigen Stat > Critical Value?
     │                             │
     │                             ▼
     │                      [VECM Estimation]
     │                      (alpha, beta extraction)
     │
     ▼
[Online Adaptive Tracking (Kalman Filter)]
     │
     ├─ Predict Step (State Projection)
     ├─ Receive Real-Time Measurement z_k
     └─ Update Step (State Correction via Kalman Gain)
     │
     ▼
[Dynamic Volatility Engine (GARCH)]
     │
     ├─ Realized Residual Extraction: e_t = z_k - H * x_k
     └─ Compute Conditional Variance: sigma_t^2
     │
     ▼
[Risk Engine / Execution Trigger]
     └─ Compute Dynamic Z-Score & VaR Limits -> Publish Order
```

---

### 6. Analogy & Diagram ASCII

#### Analogi Kointegrasi: *The Drunk and His Dog*
Bayangkan seorang pemabuk yang berjalan keluar dari kedai secara acak (*Random Walk* / $I(1)$). Dia menuntun anjingnya dengan tali kekang yang elastis. Anjing tersebut juga bergerak secara acak mengendus ke sana kemari ($I(1)$). Namun, karena dihubungkan oleh tali pengikat, jarak antara pemabuk dan anjingnya memiliki batas maksimal dan selalu kembali mendekat. Jarak ini adalah stasioner ($I(0)$). 
- Panjang dan arah tali pengikat adalah **Vektor Kointegrasi ($\beta$)**.
- Tarikan tali saat mereka saling menjauh adalah **Mekanisme Koreksi Kesalahan ($\alpha$)**.

#### Arsitektur Produksi Streaming State-Space Pipeline

```
+─────────────────────────────────────────────────────────────────────────────+
|                    HIGH-THROUGHPUT TRADING / RISK ENGINE                   |
+─────────────────────────────────────────────────────────────────────────────+
       │
 [Market Data] (Tick Array: Instrument A, Instrument B)
       │
       ▼
+─────────────────────────────────────────────────────────────────────────────+
| INGESTION & RING BUFFER (Lock-Free Circular Memory Buffer)                  |
+─────────────────────────────────────────────────────────────────────────────+
       │
       ▼
+─────────────────────────────────────────────────────────────────────────────+
| ONLINE KALMAN STATE-SPACE ESTIMATOR                                         |
|                                                                             |
|  State x_k = [beta_k, alpha_k]'                                              |
|                                                                             |
|  Predict:                                                                   |
|    x_k|k-1 = F * x_k-1|k-1                                                  |
|    P_k|k-1 = F * P_k-1 * F' + Q                                             |
|                                                                             |
|  Measurement:                                                               |
|    z_k = Price_A                                                            |
|    H_k = [Price_B, 1.0]                                                     |
|                                                                             |
|  Update:                                                                    |
|    y_k = z_k - H_k * x_k|k-1              <-- Dynamic Spread                |
|    K_k = P_k|k-1 * H_k' * inv(S_k)        <-- Adaptive Gain                 |
|    x_k|k = x_k|k-1 + K_k * y_k            <-- Optimal Hedge Ratio Update    |
|    P_k|k = (I - K*H)*P*(I - K*H)' + K*R*K'<-- Joseph-Stabilized Covariance  |
+─────────────────────────────────────────────────────────────────────────────+
       │                                       │
       │ Dynamic Residual (y_k)                │ State Vector (x_k)
       ▼                                       ▼
+───────────────────────────+         +───────────────────────────────────────+
| GARCH(1,1) ENGINE         |         | EXECUTION CONTROLLER                  |
|                           |         |                                       |
| sigma_t^2 = w + a*e^2     |         | Compute Adaptive Z-Score:             |
|             + b*sigma^2   |────────>| Z = y_k / sigma_t                     |
|                           |         |                                       |
| Output: Real-time dynamic |         | Decision Logic:                       |
| volatility threshold      |         | |Z| > 2.0 -> Rebalance / Execute      |
+───────────────────────────+         +───────────────────────────────────────+
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Johansen Cointegration & VECM

Implementasi dasar penentuan relasi kointegrasi dan estimasi model koreksi kesalahan:

```python
import numpy as np
import pandas as pd
from statsmodels.tsa.vector_ar.vecm import coint_johansen, VECM

# 1. Sintesis Data Kointegrasi non-stasioner I(1)
np.random.seed(42)
n_samples = 1000
e1 = np.random.normal(0, 1, n_samples)
e2 = np.random.normal(0, 1, n_samples)

# Random Walk bersama (Common Stochastic Trend)
common_trend = np.cumsum(np.random.normal(0, 1, n_samples))

price_b = common_trend + e1
price_a = 1.85 * common_trend + 0.5 + e2  # Terkointegrasi dengan beta ~ [1, -1.85]

df = pd.DataFrame({"Asset_A": price_a, "Asset_B": price_b})

# 2. Uji Kointegrasi Johansen
# det_order: 0 = tidak ada deterministik; 1 = konstanta dalam kointegrasi
# k_ar_diff: ordo lag dari perbedaan variabel (VECM p-1)
johansen_result = coint_johansen(df, det_order=0, k_ar_diff=1)

trace_stat = johansen_result.lr1
crit_vals_trace = johansen_result.cvt

print(f"Johansen Trace Statistic: {trace_stat}")
print(f"Critical Values (90%, 95%, 99%):\n{crit_vals_trace}")

# Evaluasi Rank: Bandingkan trace_stat dengan cvt level 95% (kolom indeks 1)
cointegration_rank = sum(trace_stat > crit_vals_trace[:, 1])
print(f"Terdeteksi Cointegration Rank (r): {cointegration_rank}")

# 3. Fitting VECM jika rank > 0
if cointegration_rank > 0:
    vecm_model = VECM(df, k_ar_diff=1, coint_rank=cointegration_rank, deterministic="co")
    vecm_fit = vecm_model.fit()
    print("\nAlpha (Speed of Adjustment):")
    print(vecm_fit.alpha)
    print("\nBeta (Cointegrating Vector):")
    print(vecm_fit.beta)
```

#### 7.2 Practical Example: Production-Grade Dynamic Tracking Engine

Pipeline berikut mengimplementasikan `KalmanSpreadTracker` adaptif dengan *Joseph form update*, dikombinasikan dengan modul inferensi *rolling* `GARCH(1,1)` untuk menghasilkan estimasi batas risiko bebas bias:

```python
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Tuple, Optional

import numpy as np
import pandas as pd
from arch import arch_model

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("EconometricsEngine")


@dataclass(frozen=True)
class StateEstimate:
    """Immutable data carrier for production state updates."""
    timestamp: pd.Timestamp
    beta: float
    alpha: float
    spread: float
    spread_std: float
    z_score: float


class KalmanSpreadTracker:
    """
    Online Adaptive Kalman Filter untuk pelacakan dinamis time-varying hedge ratio.
    Model:
        Measurement: y_t = beta_t * x_t + alpha_t + v_t,  v_t ~ N(0, R)
        State:       theta_t = [beta_t, alpha_t]'
                     theta_t = theta_{t-1} + w_t,          w_t ~ N(0, Q)
    """

    def __init__(self, delta: float = 1e-4, r_variance: float = 1e-3) -> None:
        """
        Parameters
        ----------
        delta : float
            Faktor skala untuk transisi varians kovarians parameter (Process Noise).
        r_variance : float
            Varians measurement noise.
        """
        # State: [beta, alpha]^T
        self.state = np.zeros((2, 1), dtype=np.float64)
        
        # Inisialisasi Kovarians Status P
        self.cov = np.eye(2, dtype=np.float64) * 1.0
        
        # Matriks Process Noise Q
        self.delta = delta
        self.Q = (delta / (1.0 - delta)) * np.eye(2, dtype=np.float64)
        
        # Measurement Noise R
        self.R = float(r_variance)
        
        self.identity_2x2 = np.eye(2, dtype=np.float64)

    def step(self, y: float, x: float) -> Tuple[float, float, float]:
        """
        Melakukan satu iterasi sekuensial Kalman Predict-Update.
        
        Parameters
        ----------
        y : float
            Harga instrumen dependen (Measurement).
        x : float
            Harga instrumen independen.

        Returns
        -------
        Tuple[float, float, float]
            (Estimated Beta, Estimated Alpha, Spread Residual)
        """
        # 1. PREDICT: State transition matrix F = I (Random Walk assumption)
        # state_{t|t-1} = state_{t-1|t-1}
        # P_{t|t-1} = P_{t-1|t-1} + Q
        self.cov = self.cov + self.Q

        # 2. MEASUREMENT MATRIX: H = [x, 1.0]
        H = np.array([[x, 1.0]], dtype=np.float64)

        # 3. INNOVATION RESIDUAL
        # y_hat = H * state_{t|t-1}
        y_pred = float(H @ self.state)
        residual = y - y_pred

        # 4. INNOVATION COVARIANCE: S = H * P * H' + R
        S = float(H @ self.cov @ H.T) + self.R

        # Defensive Check: cegah deviasi singularitas
        if abs(S) < 1e-12:
            logger.warning("Measurement covariance near zero. Forcing minimum threshold.")
            S = 1e-12

        # 5. KALMAN GAIN: K = P * H' * S^(-1)
        K = (self.cov @ H.T) / S

        # 6. UPDATE: Status aktual
        self.state = self.state + K * residual

        # 7. UPDATE: Kovarians dengan Joseph Form guna menjamin Positive Semi-Definite (PSD)
        # P = (I - K H) P (I - K H)' + K R K'
        I_KH = self.identity_2x2 - K @ H
        self.cov = I_KH @ self.cov @ I_KH.T + (K * self.R) @ K.T

        beta_est = float(self.state[0, 0])
        alpha_est = float(self.state[1, 0])

        return beta_est, alpha_est, residual


class ProductionEconometricPipeline:
    """
    Enterprise Pipeline yang menggabungkan Dynamic State Tracking dan Volatilitas GARCH.
    """

    def __init__(self, garch_refit_frequency: int = 50, window_size: int = 250) -> None:
        self.tracker = KalmanSpreadTracker(delta=1e-5, r_variance=1e-2)
        self.garch_refit_frequency = garch_refit_frequency
        self.window_size = window_size
        self.residual_history: list[float] = []
        self._cached_garch_omega: float = 1e-4
        self._cached_garch_alpha: float = 0.05
        self._cached_garch_beta: float = 0.90
        self._last_variance: float = 1.0

    def _refit_garch(self) -> None:
        """Mengestimasi ulang parameter GARCH(1,1) secara periodik dari residual spread."""
        if len(self.residual_history) < self.window_size:
            return

        window_data = np.array(self.residual_history[-self.window_size:])
        try:
            am = arch_model(window_data, mean="Zero", vol="GARCH", p=1, q=1, rescale=False)
            res = am.fit(disp="off", show_warning=False)
            self._cached_garch_omega = res.params["omega"]
            self._cached_garch_alpha = res.params["alpha[1]"]
            self._cached_garch_beta = res.params["beta[1]"]
        except Exception as e:
            logger.error(f"GARCH optimization failure: {e}. Fallback to cached parameters.")

    def process_tick(self, timestamp: pd.Timestamp, price_a: float, price_b: float) -> StateEstimate:
        """
        Memproses stream observasi baru tanpa kebocoran informasi masa depan.
        """
        # Kalman filter update
        beta, alpha, spread = self.tracker.step(y=price_a, x=price_b)
        self.residual_history.append(spread)

        # Refit GARCH bila mencapai interval
        if len(self.residual_history) % self.garch_refit_frequency == 0:
            self._refit_garch()

        # Update 1-step ahead conditional variance menggunakan formulasi diferensiasi GARCH
        # sigma_t^2 = omega + alpha * e_{t-1}^2 + beta * sigma_{t-1}^2
        current_variance = (
            self._cached_garch_omega
            + self._cached_garch_alpha * (spread ** 2)
            + self._cached_garch_beta * self._last_variance
        )
        self._last_variance = max(current_variance, 1e-8)
        current_std = np.sqrt(self._last_variance)

        z_score = spread / current_std

        return StateEstimate(
            timestamp=timestamp,
            beta=beta,
            alpha=alpha,
            spread=spread,
            spread_std=current_std,
            z_score=z_score
        )


if __name__ == "__main__":
    pipeline = ProductionEconometricPipeline(garch_refit_frequency=100, window_size=200)

    # Inisialisasi data simulasi
    np.random.seed(1337)
    timestamps = pd.date_range("2026-01-01 09:30:00", periods=500, freq="1s")
    base_price = 100.0 + np.cumsum(np.random.normal(0, 0.2, 500))
    
    # Model time-varying beta: beta bertransisi secara perlahan dari 1.5 ke 2.0
    true_beta = np.linspace(1.5, 2.0, 500)
    asset_b = base_price
    asset_a = true_beta * base_price + 2.0 + np.random.normal(0, 0.5, 500)

    # Simulasi eksekusi streaming
    records: list[StateEstimate] = []
    for ts, pa, pb in zip(timestamps, asset_a, asset_b):
        estimate = pipeline.process_tick(ts, pa, pb)
        records.append(estimate)

    last_est = records[-1]
    print(f"Execution complete. Final processed tick:")
    print(f"Timestamp: {last_est.timestamp} | Estimated Beta: {last_est.beta:.4f} | "
          f"Spread: {last_est.spread:.4f} | Volatility: {last_est.spread_std:.4f} | "
          f"Dynamic Z-Score: {last_est.z_score:.4f}")
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
Platform Multi-Asset Market-Making pada Tier-1 Algorithmic Trading House menangani pasangan mata uang sintetis dan ETF (*Cross-Currency Triangulation & Index Arbitrage*). Volume transaksi harian melebihi 10 juta pesan per hari dengan target SLA kalkulasi estimasi deviasi portofolio $\le 2$ milidetik.

#### Masalah Produksi
Model OLS statis gagal merefleksikan perubahan rezim likuiditas pasar (*structural break*) ketika bank sentral mengintervensi pasar valas. Residual spread terdisrupsi drastis, memicu sinyal beli/jual palsu yang mengakibatkan *maximum drawdown* sebesar 4.2% dalam 30 menit transaksi.

#### Solusi Arsitektur
1. **Pemisahan Jalur Komputasi (*Hot Path* & *Cold Path*)**:
   - **Hot Path (C++ / Cythonized Python)**: Kalman Filter beroperasi secara sekuensial pada thread independen per pasangan aset. Latensi inferensi status: $\approx 14\,\mu\text{s}$.
   - **Cold Path (Celery Worker / Redis Stream)**: Uji Johansen Cointegration dan *Maximum Likelihood Estimation* (MLE) GARCH dijalankan secara paralel dalam interval waktu *rolling* 1 jam. Parameter matriks noise $Q, R$ serta hiperparameter $\omega, \alpha, \beta$ diperbarui ke memori *shared* via SharedMemory/Plasma store.
2. **Dynamic Stop-Loss Menggunakan Model Risiko GARCH**:
   Threshold eksekusi tidak lagi mengandalkan ambang deviasi standar statis ($2\sigma$), melainkan batas probabilistik kondisional:
   $$\text{Threshold}_t = \mu_t \pm \kappa \cdot \hat{\sigma}_{t+1|t}^{\text{GARCH}}$$

#### Hasil Arsitektur
- Reduksi *slippage* kerugian akibat kesalahan *regime shift* sebesar 82%.
- *Tracking error* rasio kointegrasi turun dari 12.8% menjadi 1.1%.
- *Zero lookahead bias* terbukti pada audit validasi model regulator (SR 11-7 compliance).

---

### 9. Trade-offs

| Aspek Komparasi | Kalman Filter Adaptif | Recurrent Neural Network (LSTM/GRU) | Vector Autoregression Diferensiasi |
| :--- | :--- | :--- | :--- |
| **Inference Latency** | **Sangat Rendah** (< $50\,\mu\text{s}$). Matriks inversi $2 \times 2$ dapat dihitung analitik. | **Sedang-Tinggi** ($5 - 50\,\text{ms}$). Bergantung pada akselerasi GPU/TensorRT. | **Sangat Rendah** (< $100\,\mu\text{s}$). Hanya perkalian matriks linear. |
| **Explainability (SR 11-7)**| **Tinggi**. Matriks status dan kovarians merepresentasikan intersep dan slope secara matematis. | **Sangat Rendah** (*Black-box*). Atribusi gradien sulit diaudit secara regulatori perbankan. | **Tinggi**. Koefisien langsung dianalisis via *Impulse Response Functions* (IRF). |
| **Memory Footprint** | **Minimal** ($\approx$ bytes/state). Hanya membutuhkan vektor status dan matriks $P, Q, R$. | **Tinggi** (Ratusan megabyte untuk bobot model dan konteks sekuens). | **Minimal** (Kovarians lag statis). |
| **Kapasitas Non-Linier** | **Rendah** (hanya tracking linier stokastik; memerlukan EKF/UKF untuk non-linier). | **Sangat Tinggi**. Mampu mempelajari dinamika manifold non-linier kompleks. | **Tidak Ada**. Sepenuhnya linier. |
| **Cost Infrastructure** | Sangat murah. Berjalan optimal pada instance CPU skala mikro. | Mahal. Membutuhkan infrastruktur klaster inferensi berbasis GPU/TPU. | Sangat murah. Hanya memerlukan operasi aljabar linier standar. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Divergensi Numerik pada Filter Kovarians
* **Gejala**: Matriks kovarians $P$ kehilangan sifat *Positive Semi-Definite* (PSD), ditandai dengan munculnya nilai eigen negatif atau nilai NaN pada `z_score`.
* **Akar Masalah**: Kesalahan akumulasi floating-point (pembulatan IEEE 754) pada operasi update kovarians standar: $P = (I - KH)P$.
* **Troubleshooting**: Selalu gunakan formulasi simetris **Joseph Form**:
  $$P_{k|k} = (I - K_k H_k) P_{k|k-1} (I - K_k H_k)' + K_k R_k K_k'$$
  Jika perlu, lakukan symmetrization eksplisit pada tiap langkah: `P = 0.5 * (P + P.T)`.

#### 2. Spurious Cointegration Akibat Structural Break
* **Gejala**: Uji Johansen menunjukkan rank $r=1$ pada periode historis, namun model VECM kolaps ketika dideploy ke live data.
* **Akar Masalah**: Uji stasionaritas dan kointegrasi standar mengasumsikan parameter stasioner konstan. Adanya pergeseran struktural rezim (*structural breaks*) membuat variabel tampak terkointegrasi semu.
* **Troubleshooting**: Terapkan uji **Gregory-Hansen Cointegration Test** yang mengizinkan *structural break* pada level intersep dan tren sebelum menetapkan parameter VECM.

#### 3. Lookahead Bias pada Estimasi Skala Deviasi
* **Gejala**: Backtest menunjukkan Sharpe Ratio > 5, namun performa live ambruk ke wilayah negatif.
* **Akar Masalah**: Standarisasi z-score menggunakan nilai mean ($\mu$) dan varians ($\sigma$) dari keseluruhan dataset (*full-sample*).
* **Troubleshooting**: Parameter scaling wajib dihitung secara kausal (rekursif/expanding atau rolling window strictly sebelum waktu $t$).

---

### 11. Best Practices (Production Checklist)

- [ ] **Data Time-Synchronization**: Verifikasi bahwa seluruh time series telah diselaraskan menggunakan timestamp UTC terpotong (*monotonically increasing*), tanpa ada data masa depan yang terindeks sebelumnya.
- [ ] **Unit Root Pre-Check**: Lakukan ADF dan KPSS secara bergantian. Jangan gunakan VECM jika variabel bersifat $I(0)$ atau $I(2)$.
- [ ] **Joseph Form Implementation**: Pastikan Kalman Filter menggunakan pembaruan kovarians bentuk Joseph Form untuk stabilitas numerik floating-point 64-bit.
- [ ] **Warm-up Interval Validation**: Sediakan setidaknya $N \ge 100$ data tick awal untuk memanaskan (*warm-up*) matriks kovarians filter sebelum sinyal diarahkan ke modul routing order.
- [ ] **Matrix Rank Verification**: Lakukan evaluasi *condition number* pada matriks estimasi sebelum menghitung inversi: `np.linalg.cond(S) < 1e12`.
- [ ] **Graceful Exception Fallback**: Saat kalkulasi MLE GARCH mengalami divergensi atau mencapai iterasi maksimum tanpa konvergen, fallback ke nilai varians sebelumnya dengan model EWMA (*Exponentially Weighted Moving Average*).
- [ ] **Deterministic Component Restriction**: Pastikan restriksi matriks deterministik pada Johansen test (apakah konstanta/tren masuk ke ruang kointegrasi atau ke VAR diferensial) sesuai dengan realitas ekonomi aset.

---

### 12. Hands-on Practice

Struktur direktori kerja:
```bash
hands-on/
└── m02/
    ├── src/
    │   ├── __init__.py
    │   ├── kalman.py
    │   └── econometric_pipeline.py
    ├── tests/
    │   └── test_pipeline.py
    └── run_pipeline.py
```

#### Langkah 1: Siapkan Virtual Environment & Dependencies
```bash
mkdir -p hands-on/m02/src hands-on/m02/tests
cd hands-on/m02
python -m venv .venv
source .venv/bin/activate
pip install numpy pandas statsmodels arch pytest
```

#### Langkah 2: Buat Modul Inti Kalman (`src/kalman.py`)
Tuliskan kelas `KalmanSpreadTracker` dari seksi 7.2 ke dalam file `src/kalman.py`. Pastikan integrasi validasi simetri kovarians ditambahkan:
```python
# Tambahkan method symmetrize pada file hands-on/m02/src/kalman.py
def _enforce_symmetry(self) -> None:
    self.cov = 0.5 * (self.cov + self.cov.T)
```

#### Langkah 3: Implementasikan Eksekusi Simulasi (`run_pipeline.py`)
Import modul dari `src/kalman.py`, lakukan simulasi data sepanjang 2000 observasi dengan injeksi *volatility spike* pada step 1000 s.d. 1200, lalu cetak performa latensi rata-rata per iterasi komputasi:
```python
import time
from src.kalman import KalmanSpreadTracker
import numpy as np

tracker = KalmanSpreadTracker()
times = []
for i in range(2000):
    y = 150.0 + np.sin(i / 50.0) + np.random.normal(0, 0.5)
    x = 100.0 + np.sin(i / 50.0) + np.random.normal(0, 0.3)
    
    t0 = time.perf_counter_ns()
    beta, alpha, res = tracker.step(y, x)
    t1 = time.perf_counter_ns()
    times.append(t1 - t0)

print(f"Latency P50: {np.percentile(times, 50) / 1000.0:.2f} microseconds")
print(f"Latency P99: {np.percentile(times, 99) / 1000.0:.2f} microseconds")
```

#### Langkah 4: Verifikasi Unit Testing (`tests/test_pipeline.py`)
Pastikan tidak terjadi pelanggaran PSD pada matriks kovarians:
```python
import numpy as np
import pytest
from src.kalman import KalmanSpreadTracker

def test_kalman_psd_property():
    tracker = KalmanSpreadTracker()
    for _ in range(500):
        y = np.random.normal(10, 2)
        x = np.random.normal(5, 1)
        tracker.step(y, x)
        eigenvalues = np.linalg.eigvals(tracker.cov)
        assert np.all(eigenvalues >= -1e-10), f"Covariance matrix lost PSD: {eigenvalues}"
```
Jalankan pengujian:
```bash
pytest tests/
```

---

### 13. Exercise

#### Level Easy
Ekstrak data simulasi dua aset terintegrasi $I(1)$. Lakukan uji Augmented Dickey-Fuller (ADF) pada level harga dasar dan pada selisih pertama (*first difference*). Validasi bahwa p-value level $> 0.05$ dan p-value difference $< 0.01$.

#### Level Medium
Buat skrip menggunakan `arch` untuk mengestimasi model **EGARCH(1,1)** (*Exponential GARCH*) guna menangkap efek asimetri (*leverage effect*) pada return aset. Tunjukkan nilai koefisien $\gamma$ (asimetri) dan interpretasikan dampaknya ketika terjadi *negative shock* pasar dibandingkan *positive shock*.

#### Level Hard
Rancang modul **Multi-State Kalman Filter** untuk portofolio 3-Aset (Trivariat). 
Formulasi pengukuran:
$$z_t = \beta_1 x_{1, t} + \beta_2 x_{2, t} + \alpha + \epsilon_t$$
Estimasi vektor status $\theta_t = [\beta_1, \beta_2, \alpha]^T$ secara online. Sertakan penanganan otomatis (*zero imputation* atau kalman skipping) ketika observasi pada $x_2$ mengalami keterlambatan paket data (*missing tick*).

---

### 14. Challenge

**Skenario**: Anda adalah Principal Quant Engineer di hedge fund sistematis. Anda ditugaskan membangun engine ekonometrika real-time untuk arbitrase kointegrasi berfrekuensi tinggi antara kontrak berjangka komoditas energi (Minyak Mentah Brent vs WTI).

**Syarat & Spesifikasi Teknis**:
1. **Adaptive State Transition**: Matriks Process Noise $Q$ tidak boleh statis konstan. Implementasikan skema adaptif *covariance matching* atau penyesuaian berbasis estimasi laju pergeseran residual spread secara real-time.
2. **Online Regime Switching Detection**: Integrasikan detektor struktural non-parametrik (misal: *CUSUM test* pada residual inovasi Kalman). Ketika structural break terdeteksi (tali kointegrasi putus), sistem harus secara otomatis memblokir order baru dan memperluas varians status $P$ untuk mempercepat konvergensi ke level relasi ekuilibrium yang baru.
3. **Execution Latency SLA**: Keseluruhan proses eksekusi `predict()`, `update()`, deteksi regime break, dan kalkulasi dinamis z-score harus memiliki batas atas latensi maksimal $P99.9 < 150\,\mu\text{s}$ pada Python (dioptimalkan via Numba atau NumPy vector memory pre-allocation tanpa alokasi garbage collection baru).
4. **Deliverable**: Berikan modul Python yang berdiri sendiri (*self-contained*), dilengkapi benchmark performa mikrodetik dan pembuktian matematis integritas matriks kovarians status.

---

### 15. Quiz Evaluasi Pemahaman

#### Sesi 1: Pertanyaan Basic (5 Soal)
1. Apa kondisi matematis yang membedakan dua seri non-stasioner $I(1)$ yang terkointegrasi dengan dua seri non-stasioner yang independen?
2. Dalam matriks dekomposisi VECM $\Pi = \alpha \beta'$, apa fungsi spesifik dari matriks $\alpha$?
3. Sebutkan asumsi utama yang mendasari algoritma standar Kalman Filter terkait distribusi error pengukuran (*measurement noise*) dan transisi (*process noise*)!
4. Mengapa model regresi linier OLS menghasilkan inferensi nilai $t$-statistik yang salah ketika diaplikasikan pada variabel dengan tren stokastik?
5. Apa tujuan utama pemodelan varians menggunakan spesifikasi model GARCH dibandingkan estimasi standar deviasi historis sederhana (*rolling standard deviation*)?

#### Sesi 2: Pertanyaan Intermediate (5 Soal)
6. Pada Uji Kointegrasi Johansen, jelaskan perbedaan hipotesis antara uji *Trace Statistic* ($\lambda_{\text{trace}}$) dan uji *Maximum Eigenvalue Statistic* ($\lambda_{\text{max}}$)!
7. Mengapa formulasi pembaruan kovarians bentuk Joseph Form lebih disukai untuk implementasi produksi Kalman Filter dibandingkan rumus kanonikal $P = (I - KH)P$?
8. Bagaimana kriteria pemilihan nilai hiperparameter process noise $Q$ mempengaruhi *responsiveness* vs *smoothness* dari estimasi slope $\beta_t$ pada Kalman Filter?
9. Bagaimana restriksi stasionaritas kovarians pada model GARCH(1,1) diukur, dan apa implikasi matematisnya jika $\alpha_1 + \beta_1 \ge 1$?
10. Mengapa data runtun waktu pasar keuangan beresolusi tinggi hampir selalu gagal dalam uji normalitas residual Gaussian, dan apa mitigasinya dalam estimasi MLE GARCH?

#### Sesi 3: Skenario Kasus Produksi (3 Skenario)
11. **Skenario Sistemik**: Sebuah pipeline VECM mendeteksi kointegrasi kuat ($r=1$) pada pasangan saham perbankan. Namun saat dijalankan pada sistem trading live, spread residual melenceng terus-menerus menjauhi nol selama 4 hari bursa tanpa tanda-tanda berbalik arah (*mean-reverting*). Identifikasi 2 penyebab potensial pada model dan tindakan arsitektural untuk mendeteksi anomali ini sebelum terjadi kerugian modal!
12. **Skenario Numerik**: Saat market mengalami crash kilat (*flash crash*), sistem Kalman tracking mengeluarkan galat `LinAlgError: Matrix is singular`. Baris kode mana pada siklus kalkulasi yang memicu error ini, dan bagaimana cara membuat arsitektur penanganan matriks yang *fault-tolerant*?
13. **Skenario Latensi**: Tim infrastruktur melaporkan bahwa pemanggilan fungsi `.fit()` dari `arch_model` pada cold-path memakan waktu 80 milidetik, sementara throughput sistem membutuhkan update parameter setiap 5 milidetik. Bagaimana Anda mendesain ulang arsitektur sistem agar parameter volatilitas tetap akurat tanpa memblokir thread eksekusi utama?

---

### 16. Summary

- **VECM** membedah dinamika sistem multivariat non-stasioner dengan memisahkan pengaruh jangka panjang (vektor kointegrasi $\beta$) dari fluktuasi transien jangka pendek (kecepatan penyesuaian $\alpha$), menyelesaikan masalah regresi lancung tanpa kehilangan informasi level absolut harga.
- **Kalman Filter** menyediakan kerangka kerja probabilistik inferensi status rekursif optimal untuk memperkirakan parameter dinamis yang bervariasi terhadap waktu (*time-varying parameters*). Implementasi produksi memerlukan formulasi kovarians bentuk **Joseph Form** guna menjamin sifat simetris dan *Positive Semi-Definite*.
- **Model GARCH** menangkap fenomena pengelompokan volatilitas pasar secara dinamis, mencegah deviasi ambang risiko statis yang rentan mengalami *over-trading* pada periode tenang dan kegagalan proteksi batas risiko pada periode gejolak pasar ekstrem (*fat-tail events*).
- Menghadirkan ekonometrika lanjut ke ranah produksi skala enterprise menuntut pemisahan beban komputasi secara tegas: inferensi sekuensial mikrodetik (*Hot Path*) dipisahkan secara asinkron dari optimasi parameter MLE berat (*Cold Path*), dengan eliminasi total terhadap segala bentuk kebocoran data masa depan (*zero lookahead bias*).