# Kurikulum Rekayasa Frontend & Desain Produk: Bab 07 - Usability Testing Terukur & Metrik UX Standar
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- Mengonstruksi arsitektur telemetri UX berdaya tampung tinggi (*high-throughput*) yang mengisolasi beban instrumentasi dari *main execution thread* antarmuka pengguna.
- Mengimplementasikan pipeline pengumpulan metrik *behavioral* (Task Completion Rate/TCR, Time-on-Task/ToT, *Lostness Metric*, *Rage Clicks*, *Dead Clicks*) dan *attitudinal* (SEQ, SUS, UMUX-Lite) secara terprogram.
- Menganalisis signifikansi statistik dari data kuantitatif menggunakan uji hipotesis formal (*Student's t-test*, *Mann-Whitney U test*, serta *Wilson Score Interval* untuk metrik biner).
- Mengintegrasikan instrumen telemetri UX ke dalam pipeline CI/CD dan sistem *real-user monitoring* (RUM) skala *enterprise*.

---

### 2. Prerequisite

Peserta didik wajib memahami konsep-konsep dasar berikut:
- **Statistika Dasar**: Distribusi probabilitas, *Confidence Intervals* (CI), $p$-value, varians, dan *standard error*.
- **DOM & Browser Performance APIs**: Pemahaman mendalam terkait `PerformanceObserver`, `requestIdleCallback`, `Beacon API`, serta siklus hidup *rendering* browser (LCP, INP, CLS).
- **TypeScript & Node.js/Python**: Kemampuan membaca dan menulis TypeScript lanjutan (Event delegation, Worker API) dan skrip komputasi analitik (Python dengan `scipy` dan `numpy`).

---

### 3. Concept & Internal Architecture

Implementasi kuantitatif dari *usability testing* modern memisahkan lapisan observasi menjadi dua domain utama: **Metrik Behavioral Kuantitatif** (*apa yang dilakukan pengguna*) dan **Metrik Attitudinal Standar** (*apa yang dipikirkan pengguna*). 

#### 3.1. Taksonomi Metrik UX Kuantitatif

1. **Task Completion Rate (TCR)**:
   Metrik dikotomi ($x_i \in \{0, 1\}$). Karena data bersifat biner, penghitungan *Confidence Interval* (CI) tidak boleh menggunakan pendekatan distribusi normal standar jika ukuran sampel $n < 100$. Standar industri mewajibkan estimasi berbasis **Wilson Score Interval** atau **Adjusted Wald Interval** (metode Agresti-Coull):
   $$\tilde{p} = \frac{X + 2}{n + 4}, \quad W = \tilde{p} \pm Z_{1-\alpha/2} \sqrt{\frac{\tilde{p}(1-\tilde{p})}{n + 4}}$$

2. **Lostness Metric ($L$)**:
   Mengukur efisiensi navigasi pengguna saat mencari target dalam arsitektur informasi.
   $$L = \sqrt{\left(\frac{N}{S} - 1\right)^2 + \left(\frac{R}{N} - 1\right)^2}$$
   - $N$: Jumlah *unique pages/states* yang dikunjungi pengguna selama pengerjaan *task*.
   - $S$: Jumlah total *page views/state transitions* yang terjadi.
   - $R$: Jumlah *minimum unique pages/states* optimal untuk menyelesaikan *task*.
   - Interpretasi: $L > 0.4$ mengindikasikan disorientasi pengguna yang signifikan; $L < 0.2$ menunjukkan jalur navigasi optimal.

3. **Single Ease Question (SEQ)**:
   Pengukuran tingkat kesulitan tugas (*post-task*) menggunakan skala Likert 7-titik. Standar industri menuntut konversi ke skala normalisasi z-score terhadap distribusi historis sistem untuk menentukan deviasi performa UX.

4. **UMUX-Lite (Usability Metric for User Experience - Lite)**:
   Pendekatan *post-test* 2-item yang memiliki korelasi tinggi ($r > 0.85$) dengan *System Usability Scale* (SUS) namun dengan friksi yang jauh lebih rendah:
   - Item 1: `[Sistem] memiliki kapabilitas yang sesuai dengan kebutuhan saya.` (1-7)
   - Item 2: `[Sistem] mudah digunakan.` (1-7)
   - Skor Regresi Linier Terhadap SUS:
     $$\text{Skor UMUX-Lite} = \left(\frac{x_1 + x_2 - 2}{12}\right) \times 100$$
     $$\text{Estimasi SUS} = 0.65 \times (\text{Skor UMUX-Lite}) + 22.9$$

#### 3.2. Arsitektur Telemetri UX Skala Enterprise

```
+---------------------------------------------------------------------------------------+
| Browser Client (Main Thread)                                                          |
|  +--------------------+    +----------------------+    +--------------------------+  |
|  | Interception Layer |    | MutationObserver     |    | User Action Proxy        |  |
|  | (Click, Keydown)   |    | (DOM State Changes)  |    | (Task Start/End Tracker) |  |
|  +---------+----------+    +----------+-----------+    +------------+-------------+  |
|            |                          |                             |                 |
|            +-------------------+      |      +----------------------+                 |
|                                |      |      |                                        |
|                                v      v      v                                        |
|                          +-----------------------+                                    |
|                          | UX Ring Buffer        |                                    |
|                          | (In-Memory Array)     |                                    |
|                          +-----------+-----------+                                    |
+--------------------------------------|------------------------------------------------+
                                       | MessageChannel / Comlink Transfer
+--------------------------------------v------------------------------------------------+
| Web Worker (Telemetry Isolation Thread)                                               |
|  +---------------------------------------------------------------------------------+  |
|  | - Schema Validation (Typebox/Zod)                                               |  |
|  | - Lostness Dynamic Calculation                                                  |  |
|  | - Batching & Windowing Compression (GZIP/Deflate via Compression Streams API)    |  |
|  +-----------------------------------+---------------------------------------------+  |
|                                      |                                                |
|                                      v                                                |
|                        +---------------------------+                                  |
|                        | navigator.sendBeacon()    |                                  |
|                        | / fetch(keepalive: true)  |                                  |
|                        +-------------+-------------+                                  |
+--------------------------------------|------------------------------------------------+
                                       | HTTPS POST /v1/telemetry
                                       v
+---------------------------------------------------------------------------------------+
| Edge Ingestion Gateway (Cloudflare Workers / AWS API Gateway)                         |
|  - Rate Limiting                                                                      |
|  - Header Extraction (Geo, Device Class, Network RTT)                                 |
+--------------------------------------+------------------------------------------------+
                                       |
                                       v
+---------------------------------------------------------------------------------------+
| Real-time Event Stream (Apache Kafka / AWS Kinesis)                                  |
+-------------------+-----------------------------------+-------------------------------+
                    |                                   |
                    v                                   v
+--------------------------------------+  +---------------------------------------------+
| Stream Processor (Apache Flink)      |  | Cold Storage Ingestion (S3 / Parquet)       |
| - Rolling Lostness Index Aggregation |  | - DuckDB / ClickHouse Analysis              |
| - Rage Click Detection (>3 within 1s)|  | - Automated Hypothesis Testing Worker        |
+--------------------------------------+  +---------------------------------------------+
```

---

### 4. Why & What

| Dimensi | UX Testing Kualitatif Tradisional | Arsitektur Telemetri UX Kuantitatif Terukur |
| :--- | :--- | :--- |
| **Ukuran Sampel ($n$)** | $n = 5 - 10$ partisipan. | $n = 100 - 100.000+$ pengguna aktif. |
| **Bias Koleksi Data** | Efek *Hawthorne* (partisipan sadar sedang diawasi observer). | *Natural interaction environment* (perilaku organik tanpa distorsi). |
| **Presisi Analisis** | Temuan berbasis observasi tematik, rawan bias konfirmasi. | Distribusi statistik matematis, deviasi standar, interval kepercayaan. |
| **Latensi Pelaporan** | 1–2 minggu penyusunan dokumen pengujian. | Evaluasi berkelanjutan via pipeline analitik otomatis. |
| **Dampak Frontend** | Nol dampak komputasi klien. | Risiko *thread starvation* jika telemetri tidak diisolasi secara asinkron. |

---

### 5. How (Workflow Detail)

1. **Definisi State Machine Tugas**: Definisikan kondisi awal (*Trigger*), node transisi yang sah (*Valid Paths*), dan kriteria akhir sukses (*Success Boundary*) untuk setiap *task*.
2. **Instrumentasi Klien**: Pasang agen pelacak berbasis *event delegation* yang mengumpulkan interaksi (klik, *input latency*, navigasi URL).
3. **Isolasi Pemrosesan (Worker Thread)**: Lakukan serialisasi dan ekstraksi metrik struktural (seperti jalur navigasi unik untuk metrik *Lostness*) di dalam Web Worker agar tidak menambah beban *Total Blocking Time* (TBT) antarmuka.
4. **Ingestion & Buffering**: Kirim data menggunakan `navigator.sendBeacon` pada *lifecycle events* (`pagehide`, *task completion*) untuk mencegah *data loss* saat navigasi antarhalaman.
5. **Agregasi & Komputasi Statistik Backend**: Lakukan pembersihan *outlier* pada metrik durasi (*Time-on-Task*) menggunakan transformasi logaritma natural ($\ln(ToT)$) karena distribusi durasi pengerjaan hampir selalu menceng ke kanan (*right-skewed* / log-normal).
6. **Pengujian Hipotesis**: Jalankan skrip inferensi statistik untuk membandingkan baseline desain lama versus perlakuan desain baru.

---

### 6. Analogy & Diagram ASCII

Bayangkan sistem avionik pada pesawat terbang komersial.

```
+-----------------------------------------------------------------------+
| Cockpit Analog: Pilot (Pengguna) berinteraksi dengan instrumen.       |
|                                                                       |
|  [ Kemudi / Switch ] ------ Interaksi -------> [ Permukaan Kendali ]  |
|            |                                                          |
|      (Tap Sensor)                                                     |
|            |                                                          |
|            v                                                          |
|  +---------------------+                                              |
|  | Flight Data Recorder|  (Black Box / Web Worker Telemetry)         |
|  | - Rekam tiap gerak  |  TIDAK membebani hidrolik kendali utama!     |
|  | - Kompresi data     |                                              |
|  +---------+-----------+                                              |
|            |                                                          |
|            +===== (Transmisi Satelit / Beacon API) ====> [ Tower ]    |
+-----------------------------------------------------------------------+
```

Jika sistem perekaman data penerbangan membebani kabel kontrol navigasi fisik pesawat, pesawat akan mengalami *lag* respon dan membahayakan penerbangan. Begitu pula instrumen UX: pelacakan metrik tidak boleh mengganggu *frame budget* 16.6ms (60 FPS) rendering browser.

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Tracker Lostness Metric Sisi Klien

Implementasi dasar pelacak alur state navigasi berbasis JavaScript murni:

```typescript
// simple-lostness-tracker.ts
export class SimpleLostnessTracker {
  private optimalStepCount: number;
  private visitedPath: string[] = [];

  constructor(optimalStepCount: number) {
    this.optimalStepCount = optimalStepCount;
  }

  public recordStep(routeIdentifier: string): void {
    this.visitedPath.push(routeIdentifier);
  }

  public calculateLostness(): number {
    const totalSteps = this.visitedPath.length;
    if (totalSteps === 0) return 0;

    const uniqueSteps = new Set(this.visitedPath).size;
    const optimal = this.optimalStepCount;

    // Formula Lostness: sqrt( (N / S - 1)^2 + (R / N - 1)^2 )
    // N = Unique steps, S = Total steps, R = Minimum optimal steps
    const term1 = Math.pow((uniqueSteps / totalSteps) - 1, 2);
    const term2 = Math.pow((optimal / uniqueSteps) - 1, 2);

    return Math.sqrt(term1 + term2);
  }
}

// Penggunaan sederhana:
const task = new SimpleLostnessTracker(3); // Rute optimal butuh 3 langkah: Home -> Cart -> Checkout
task.recordStep('/home');
task.recordStep('/cart');
task.recordStep('/promo'); // Pengguna tersesat ke promo
task.recordStep('/cart');
task.recordStep('/checkout');

console.log(`Lostness Index: ${task.calculateLostness().toFixed(4)}`);
// S = 5, N = 4, R = 3 => Menghasilkan indeks lostness terukur
```

#### 7.2. Practical Example: Production Telemetry SDK & Statistical Engine

Berikut adalah implementasi tingkat produksi dengan arsitektur non-blocking menggunakan Worker dan analisis inferensial statistik otomatis.

##### A. Telemetry Ingestion Core Client (`ux-telemetry-engine.ts`)

```typescript
// ux-telemetry-engine.ts
export interface TelemetryPayload {
  taskId: string;
  sessionToken: string;
  actionType: 'NAVIGATE' | 'ACTION' | 'RAGE_CLICK' | 'SUBMIT';
  elementSelector?: string;
  metadata?: Record<string, unknown>;
  timestamp: number;
}

export class UXMetricsTelemetry {
  private static instance: UXMetricsTelemetry;
  private ringBuffer: TelemetryPayload[] = [];
  private readonly bufferLimit = 50;
  private flushTimer: number | null = null;
  private endPoint: string;
  private clickTimestamps: number[] = [];

  private constructor(endPoint: string) {
    this.endPoint = endPoint;
    this.attachGlobalListeners();
  }

  public static initialize(endPoint: string): UXMetricsTelemetry {
    if (!UXMetricsTelemetry.instance) {
      UXMetricsTelemetry.instance = new UXMetricsTelemetry(endPoint);
    }
    return UXMetricsTelemetry.instance;
  }

  private attachGlobalListeners(): void {
    if (typeof window === 'undefined') return;

    // Deteksi Rage Clicks: > 3 klik pada target yang berdekatan dalam kurun 1000ms
    window.addEventListener('click', (event: MouseEvent) => {
      const now = performance.now();
      this.clickTimestamps = this.clickTimestamps.filter(t => now - t < 1000);
      this.clickTimestamps.push(now);

      const target = event.target as HTMLElement;
      const selector = this.resolveCssPath(target);

      if (this.clickTimestamps.length >= 3) {
        this.enqueue({
          taskId: 'current_task',
          sessionToken: this.getSessionToken(),
          actionType: 'RAGE_CLICK',
          elementSelector: selector,
          timestamp: Date.now()
        });
        this.clickTimestamps = [];
      } else {
        this.enqueue({
          taskId: 'current_task',
          sessionToken: this.getSessionToken(),
          actionType: 'ACTION',
          elementSelector: selector,
          timestamp: Date.now()
        });
      }
    }, { passive: true });

    // Flush otomatis saat dokumen akan ditinggalkan
    window.addEventListener('pagehide', () => {
      this.flushImmediately();
    });
  }

  private resolveCssPath(el: HTMLElement | null): string {
    if (!el || el.nodeType !== Node.ELEMENT_NODE) return '';
    if (el.id) return `#${el.id}`;
    const tag = el.tagName.toLowerCase();
    const className = el.className ? `.${el.className.split(' ').join('.')}` : '';
    return `${tag}${className}`;
  }

  public enqueue(payload: TelemetryPayload): void {
    this.ringBuffer.push(payload);
    if (this.ringBuffer.length >= this.bufferLimit) {
      this.flushImmediately();
    } else if (!this.flushTimer) {
      this.flushTimer = window.setTimeout(() => this.flushImmediately(), 5000);
    }
  }

  public flushImmediately(): void {
    if (this.flushTimer) {
      clearTimeout(this.flushTimer);
      this.flushTimer = null;
    }

    if (this.ringBuffer.length === 0) return;

    const dataToSend = JSON.stringify(this.ringBuffer);
    this.ringBuffer = [];

    // Prioritas 1: Gunakan Beacon API untuk mencegah kegagalan network cancellation
    if (navigator.sendBeacon) {
      const blob = new Blob([dataToSend], { type: 'application/json; charset=UTF-8' });
      const success = navigator.sendBeacon(this.endPoint, blob);
      if (success) return;
    }

    // Fallback: Fetch dengan keepalive flag
    fetch(this.endPoint, {
      method: 'POST',
      body: dataToSend,
      headers: { 'Content-Type': 'application/json' },
      keepalive: true
    }).catch(err => {
      console.error('[Telemetry Ingestion Failure]', err);
    });
  }

  private getSessionToken(): string {
    return sessionStorage.getItem('ux_session_tok') || 'anonymous-session';
  }
}
```

##### B. Statistical Testing Analysis Pipeline (`evaluate_ux_metrics.py`)

Skrip analitik backend untuk memvalidasi perbedaan performa antarmuka lama ($A$) versus baru ($B$):

```python
# evaluate_ux_metrics.py
import numpy as np
import scipy.stats as stats
from typing import Dict, List, Tuple

def wilson_score_interval(successes: int, trials: int, confidence: float = 0.95) -> Tuple[float, float]:
    """Menghitung Wilson Score Interval untuk Task Completion Rate (TCR)."""
    if trials == 0:
        return (0.0, 0.0)
    z = stats.norm.ppf(1 - (1 - confidence) / 2)
    p_hat = successes / trials
    denominator = 1 + z**2 / trials
    centre_adjusted_probability = p_hat + z**2 / (2 * trials)
    adjusted_standard_deviation = np.sqrt((p_hat * (1 - p_hat) + z**2 / (4 * trials)) / trials)
    
    lower_bound = (centre_adjusted_probability - z * adjusted_standard_deviation) / denominator
    upper_bound = (centre_adjusted_probability + z * adjusted_standard_deviation) / denominator
    return (float(lower_bound), float(upper_bound))

def evaluate_time_on_task(control_durations: List[float], treatment_durations: List[float]) -> Dict[str, float]:
    """
    Durasi bersifat Log-Normal. Harus diuji menggunakan log-transform Student's t-test
    atau non-parametrik Mann-Whitney U test.
    """
    log_ctrl = np.log(control_durations)
    log_treat = np.log(treatment_durations)
    
    # Uji homogenitas varians (Levene test)
    _, p_levene = stats.levene(log_ctrl, log_treat)
    equal_var = p_levene > 0.05
    
    # Student's t-test pada data log-transformed
    t_stat, p_val = stats.ttest_ind(log_ctrl, log_treat, equal_var=equal_var)
    
    # Non-parametric check (Mann-Whitney U) sebagai safety-rail
    u_stat, p_val_mw = stats.mannwhitneyu(control_durations, treatment_durations, alternative='two-sided')

    # Geometric mean ratio
    geo_mean_ctrl = np.exp(np.mean(log_ctrl))
    geo_mean_treat = np.exp(np.mean(log_treat))
    improvement_pct = ((geo_mean_ctrl - geo_mean_treat) / geo_mean_ctrl) * 100

    return {
        "geometric_mean_control_seconds": float(geo_mean_ctrl),
        "geometric_mean_treatment_seconds": float(geo_mean_treat),
        "relative_speedup_percent": float(improvement_pct),
        "t_test_p_value": float(p_val),
        "mann_whitney_p_value": float(p_val_mw),
        "is_statistically_significant": bool(p_val < 0.05)
    }

if __name__ == "__main__":
    # Baseline: Antarmuka Desain A
    task_a_successes = 78
    task_a_n = 100
    task_a_durations = [12.4, 15.2, 8.9, 22.1, 45.0, 11.2, 14.8, 18.0, 19.5, 33.2] * 10

    # Perlakuan: Antarmuka Desain B (Alur Disederhanakan)
    task_b_successes = 92
    task_b_n = 100
    task_b_durations = [9.1, 10.4, 7.8, 14.2, 21.0, 8.5, 11.0, 12.3, 13.1, 16.5] * 10

    ci_a = wilson_score_interval(task_a_successes, task_a_n)
    ci_b = wilson_score_interval(task_b_successes, task_b_n)
    
    print(f"Desain A - TCR: {task_a_successes/task_a_n:.2%}, 95% CI: [{ci_a[0]:.2%}, {ci_a[1]:.2%}]")
    print(f"Desain B - TCR: {task_b_successes/task_b_n:.2%}, 95% CI: [{ci_b[0]:.2%}, {ci_b[1]:.2%}]")

    tot_analysis = evaluate_time_on_task(task_a_durations, task_b_durations)
    print("\nEvaluasi Time-on-Task:")
    for k, v in tot_analysis.items():
        print(f"  {k}: {v}")
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
Aplikasi *Payment Gateway & Corporate Invoicing* skala enterprise memproses 1.200.000 transaksi B2B per hari. Terdapat lonjakan tiket keluhan pada alur *Batch Invoicing Approval*: pengguna sering menyetujui faktur yang salah atau mengalami *timeout* saat mencoba memvalidasi transaksi ganda.

#### Intervensi Desain & Hipotesis
Arsitektur informasi dirombak dari tabel monolitik berlapis-lapis menjadi alur *Split-Screen Contextual Drawer*.
- **Hipotesis 1**: Task Completion Rate (TCR) akan naik dari $\le 80\%$ ke $\ge 90\%$.
- **Hipotesis 2**: Indeks *Lostness* ($L$) akan turun dari rata-rata $0.48$ menjadi $< 0.15$.
- **Hipotesis 3**: Skor SEQ (*Single Ease Question*) akan naik secara signifikan dari skala rata-rata $3.8/7.0$ ke $> 5.5/7.0$.

#### Data Hasil Eksekusi ($n = 450$ Enterprise Approvers)

| Parameter | Desain Lama (Control) | Desain Baru (Treatment) | Pengujian Statistik | Hasil & Konfirmasi |
| :--- | :--- | :--- | :--- | :--- |
| **Sample Size ($n$)** | $n_1 = 225$ | $n_2 = 225$ | - | Statistical Power ($1-\beta$) = 0.92 |
| **TCR (Wilson 95% CI)** | 77.3% [71.4%, 82.3%] | 94.2% [90.3%, 96.6%] | Two-proportion Z-test ($Z = 4.88, p < 0.0001$) | Hipotesis 1 **Diterima** |
| **Lostness ($L$)** | Mean: 0.46 ($\sigma=0.18$) | Mean: 0.11 ($\sigma=0.06$) | Welch's t-test ($t = 27.8, p < 0.00001$) | Hipotesis 2 **Diterima** |
| **Median Time-on-Task** | 84.5 detik | 32.1 detik | Mann-Whitney U test ($U = 4120, p < 0.0001$) | Reduksi durasi kerja sebesar 62.0% |
| **SEQ Score (1 - 7)** | Mean: 3.6 ($\sigma=1.2$) | Mean: 5.9 ($\sigma=0.8$) | Independent t-test ($p < 0.0001$) | Hipotesis 3 **Diterima** |

Integrasi telemetri otomatis berhasil mendeteksi anomali pada perlakuan baru di hari ke-2 pengujian: browser versi Chromium lama memicu *Rage Clicks* pada tombol konfirmasi karena pemblokiran render CSS. Isu ini langsung diselesaikan melalui *hotfix* sebelum rilis publik penuh (100%).

---

### 9. Trade-offs

```
                  [Tingkat Granularitas Telemetri]
                                 /\
                                /  \
                               /    \
                              /      \
                             /   /\   \
                            /   /  \   \
                           /   /    \   \
  [Overhead Komputasi Klien]  /______\  [Akurasi Inferensi Statistik]
```

#### 1. Granularitas Event vs. Overhead Komputasi Klien
- **High-Frequency Capture (e.g., Mouse Trajectory, DOM Mutation)**:
  - *Kelebihan*: Mendukung rekonstruksi visual sesi (*session replay*) dan analisis mikroskopik *hesitation time*.
  - *Kekurangan*: Meningkatkan konsumsi memori heap DOM, berisiko menyebabkan penurunan frame rate animasi antarmuka, serta meningkatkan konsumsi baterai perangkat mobile.
- **Low-Frequency Macro-Events (e.g., Task Boundary, Clicks, Form Submits)**:
  - *Kelebihan*: Beban komputasi nol, tidak berdampak pada metrik Google Core Web Vitals (INP/CLS).
  - *Kekurangan*: Kehilangan konteks kualitatif ketika pengguna mengalami *hesitation* (diam tanpa klik).

#### 2. Synchronous Collection vs. Asynchronous Beaconing
- **Penyimpanan Lokal & Batch Flush**: Menghemat kapasitas bandwidth jaringan, namun berisiko kehilangan fragmen data akhir jika proses browser dipaksa mati (*hard process kill*).
- **Immediate Eager Dispatch**: Memastikan ketepatan waktu metrik hingga interaksi terakhir, namun menghasilkan overhead konkurensi koneksi HTTP/TLS handshake yang tinggi.

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan 1: Mengasumsikan Durasi Waktu Terdistribusi Normal
- **Anti-pattern**: Menghitung *Standard Deviation* pada *Time-on-Task* mentah dan menyajikannya sebagai $\mu \pm 2\sigma$.
- **Koreksi Arsitektural**: Distribusi waktu selalu memiliki limitasi $x > 0$ dan berekor panjang (*right-skewed*). Wajib menerapkan transformasi logaritmik $y = \ln(x)$, menghitung rata-rata geometri, atau menggunakan metrik non-parametrik (Median dan Interquartile Range / IQR).

#### Kesalahan 2: Blocking Event Loop Saat Menghitung Lostness
- **Anti-pattern**: Melakukan komputasi graf jalur navigasi langsung di dalam event handler `popstate` atau `hashchange`.
- **Koreksi Arsitektural**: Delegasikan komputasi array traversal ke Web Worker atau tangani di backend ingest stream.

#### Kesalahan 3: Panggilan API Telemetri Dibatalkan Saat Page Unload
- **Anti-pattern**: Menggunakan `axios.post` atau `fetch` standar di dalam event listener `beforeunload`.
- **Koreksi Arsitektural**: Request HTTP standar akan dibatalkan oleh browser begitu dokumen mulai dibongkar (*unloading*). Wajib menggunakan `navigator.sendBeacon()` atau `fetch(url, { keepalive: true })`.

---

### 11. Best Practices (Production Checklist)

- [ ] **Privacy by Design (Zero PII Ingestion)**: Masking otomatis seluruh teks input, field kata sandi, dan format kartu pembayaran sebelum payload masuk ke *Ring Buffer*.
- [ ] **Thread Isolation**: Komputasi metrik derivatif (seperti *Rage Clicks* dan *Lostness*) tidak boleh dieksekusi di *Main Execution Thread*.
- [ ] **Bounded Memory**: Terapkan batas absolut (*hard cap*) pada in-memory telemetry buffer (maksimal 100 entri) untuk mencegah kebocoran memori (*memory leaks*) pada SPA yang aktif lama.
- [ ] **Adaptive Sampling**: Terapkan *sampling rate* dinamis (misal: 10% untuk pengguna desktop koneksi cepat, 1% untuk pengguna mobile *low-end*).
- [ ] **Rigorous Statistical Null-Hypothesis Testing**: Jangan meluncurkan desain baru jika $p\text{-value} \ge 0.05$ atau *Statistical Power* ($1-\beta$) belum mencapai minimal 0.80.

---

### 12. Hands-on Practice

Simpan seluruh file berikut ke dalam direktori struktur: `hands-on/m02/`

#### Langkah 1: Inisialisasi Project & Konfigurasi TypeScript
```bash
mkdir -p hands-on/m02
cd hands-on/m02
npm init -y
npm install typescript @types/node --save-dev
npx tsc --init
```

#### Langkah 2: Buat Modul Kalkulator Metrik Kuantitatif (`hands-on/m02/ux-metrics.ts`)
Salin kode berikut ke `hands-on/m02/ux-metrics.ts`:
```typescript
export interface TaskRecord {
  taskId: string;
  durationMs: number;
  completed: boolean;
  pathTraversed: string[];
  optimalPathLength: number;
  seqScore?: number; // Skala 1-7
}

export class UXMetricsAnalyzer {
  public static calculateTCR(records: TaskRecord[]): { rate: number; wilsonCI: [number, number] } {
    const trials = records.length;
    if (trials === 0) return { rate: 0, wilsonCI: [0, 0] };

    const successes = records.filter(r => r.completed).length;
    const p = successes / trials;
    const z = 1.96; // 95% Confidence Level

    const denominator = 1 + (z * z) / trials;
    const center = p + (z * z) / (2 * trials);
    const margin = z * Math.sqrt((p * (1 - p) + (z * z) / (4 * trials)) / trials);

    const lower = (center - margin) / denominator;
    const upper = (center + margin) / denominator;

    return {
      rate: p,
      wilsonCI: [Math.max(0, lower), Math.min(1, upper)]
    };
  }

  public static calculateLostness(path: string[], optimalLength: number): number {
    if (path.length === 0 || optimalLength <= 0) return 0;
    const totalSteps = path.length;
    const uniqueSteps = new Set(path).size;

    const term1 = Math.pow((uniqueSteps / totalSteps) - 1, 2);
    const term2 = Math.pow((optimalLength / uniqueSteps) - 1, 2);

    return Math.sqrt(term1 + term2);
  }
}
```

#### Langkah 3: Eksekusi Pipeline Pengujian (`hands-on/m02/index.ts`)
Salin skrip eksekusi simulasi ini ke `hands-on/m02/index.ts`:
```typescript
import { UXMetricsAnalyzer, TaskRecord } from './ux-metrics';

const mockTaskData: TaskRecord[] = [
  { taskId: 'checkout', durationMs: 45000, completed: true, pathTraversed: ['/cart', '/addr', '/pay', '/success'], optimalPathLength: 4 },
  { taskId: 'checkout', durationMs: 65000, completed: true, pathTraversed: ['/cart', '/promo', '/cart', '/addr', '/pay', '/success'], optimalPathLength: 4 },
  { taskId: 'checkout', durationMs: 90000, completed: false, pathTraversed: ['/cart', '/home', '/cart', '/cancel'], optimalPathLength: 4 },
  { taskId: 'checkout', durationMs: 38000, completed: true, pathTraversed: ['/cart', '/addr', '/pay', '/success'], optimalPathLength: 4 },
];

const tcrResult = UXMetricsAnalyzer.calculateTCR(mockTaskData);
console.log('--- HASIL EVALUASI METRIK UX ---');
console.log(`Completion Rate: ${(tcrResult.rate * 100).toFixed(2)}%`);
console.log(`Wilson 95% CI   : [${(tcrResult.wilsonCI[0] * 100).toFixed(2)}%, ${(tcrResult.wilsonCI[1] * 100).toFixed(2)}%]`);

mockTaskData.forEach((task, index) => {
  const lostness = UXMetricsAnalyzer.calculateLostness(task.pathTraversed, task.optimalPathLength);
  console.log(`Partisipan #${index + 1} Lostness: ${lostness.toFixed(4)} ${lostness > 0.4 ? '(Disorientasi Tinggi)' : '(Optimal)'}`);
});
```

#### Langkah 4: Kompilasi dan Jalankan
```bash
npx ts-node hands-on/m02/index.ts
```

---

### 13. Exercise

#### Level Easy
Buat fungsi murni TypeScript `calculateUMUXLite(item1Score: number, item2Score: number): number` yang menerima parameter dua skor skala Likert (1 hingga 7), dan mengembalikan estimasi nilai System Usability Scale (SUS) standar berdasarkan formula regresi linier standar.
- *Input*: `item1Score = 6`, `item2Score = 5`
- *Target Luaran*: Prediksi skor SUS pada rentang interval 0–100.

#### Level Medium
Kembangkan interceptor JavaScript yang memantau interaksi form input dan mendeteksi metrik *Field Hesitation Time* (durasi sejak elemen input menerima `:focus` hingga event `input` atau `keydown` pertama ditembakkan). Emit data ini sebagai metrik kustom hanya jika durasi *hesitation* melebihi 3000 ms.

#### Level Hard
Rancang modul state machine di Node.js/TypeScript untuk *Event Stream Aggregator*. Modul harus membaca raw stream interaksi (klik, navigasi) dari JSON stream chunked, merekonstruksi alur perjalanan pengguna, dan mendeteksi kondisi *Navigation Loops* (siklus kunjungan state yang berulang: misal $A \to B \to C \to B \to C$). Outputkan rasio *Dead-Loop Interactivity* per sesi pengguna.

---

### 14. Challenge

**Skenario**: Anda memimpin tim arsitektur frontend pada sistem *Healthcare Patient Portal* berisiko tinggi. Pasien dengan kondisi darurat sering menggunakan fitur "Request Emergency Consultation". Desain baru telah dibuat untuk mereduksi kebingungan pemilihan poli darurat.

**Target Tantangan**:
1. Buat arsitektur instrumentasi yang mengukur Time-on-Task (ToT) dan Lostness ($L$) secara *zero-latency* dan *zero-data-loss*, dengan mengantisipasi kondisi jaringan buruk (3G/koneksi putus-nyambung di ambulans/daerah terpencil).
2. Tentukan kriteria penghentian dini eksperimen (*early stopping criteria*) menggunakan *Sequential Probability Ratio Test* (SPRT) atau Bayesian Sequential Analysis: jika alur desain baru ternyata menyebabkan TCR turun di bawah baseline 99.0% dengan signifikansi $p < 0.01$, sistem harus otomatis mematikan *feature flag* varian baru tanpa intervensi manual tim engineer.
3. Rancang model mitigasi privasi ketat untuk menjamin kepatuhan HIPAA/GDPR: tidak ada parameter rute atau ID pasien yang boleh terekspos ke vendor analitik pihak ketiga.

---

### 15. Quiz Evaluasi Pemahaman

#### Pertanyaan Basic
1. Mengapa penggunaan rata-rata aritmatika standar ($\bar{x}$) keliru jika diaplikasikan secara langsung pada pengukuran *Time-on-Task* (ToT)?
2. Berapa batas ambang batas (*threshold*) baku pada metrik *Lostness* ($L$) yang menandakan bahwa pengguna mengalami disorientasi parah dalam bernavigasi?
3. Apa keunggulan formula *Wilson Score Interval* dibandingkan estimasi normal standar (Wald Interval) untuk Task Completion Rate?
4. Kapan waktu yang tepat (*lifecycle event*) untuk mengeksekusi *Single Ease Question* (SEQ) dalam usability testing terukur?
5. Mengapa metode `navigator.sendBeacon()` lebih direkomendasikan daripada `fetch()` asinkron standar saat mentransmisikan metrik pada event `pagehide`?

#### Pertanyaan Intermediate
6. Bagaimana cara memvalidasi perbedaan skor kepuasan SUS antara Desain A dan Desain B jika data pengujian terbukti tidak terdistribusi normal?
7. Apa indikator perilaku visual DOM yang membedakan *Rage Click* dengan *Dead Click*?
8. Bagaimana pengaruh variasi ukuran sampel ($n_1 \ne n_2$) pada pengujian A/B usability testing dan bagaimana cara menangani homogenitas variansnya?
9. Jelaskan bagaimana formula UMUX-Lite mengonversi skala mentah 2-item (rentang 1-7) menjadi ekuivalensi skor SUS (rentang 0-100).
10. Bagaimana instrumen telemetri UX dapat mempengaruhi skor *Interaction to Next Paint* (INP) browser jika tidak diisolasi dengan benar?

#### Skenario Kasus Produksi
11. **Kasus 1**: Pada A/B testing sistem checkout, Desain B menunjukkan peningkatan Task Completion Rate sebesar 5% ($p = 0.04$), namun metrik pelacak sekunder mendeteksi kenaikan *Rage Clicks* sebesar 35% pada tombol *Submit*. Langkah arsitektural apa yang wajib diambil oleh tim engineering sebelum melakukan *rollout* penuh?
12. **Kasus 2**: Sebuah form registrasi multi-step mencatat lonjakan nilai metrik *Lostness* ($L = 0.65$) khusus pada platform mobile browser, sedangkan pada desktop tercatat optimal ($L = 0.08$). Aspek interaksi antarmuka apa yang paling berpeluang menjadi akar masalah struktural?
13. **Kasus 3**: Pipeline analitik Anda menerima puluhan juta event metrik UX per jam. Terjadi lonjakan latensi pengerjaan query pada database analitik berbasis baris (*row-oriented* RDBMS). Bagaimana Anda mendesain ulang arsitektur penyimpanan dan pipeline transformasinya agar laporan metrik usability kuantitatif dapat diakses secara near real-time?

---

#### Kunci Jawaban & Panduan Solusi Quiz

1. **Basic**: Durasi waktu pengerjaan tugas (*Time-on-Task*) tidak pernah simetris dan selalu menceng ke kanan (*log-normal distribution* / berekor panjang akibat adanya *outlier* pengguna yang terdistraksi). Rata-rata aritmatika mentah akan bias tertarik ke atas oleh nilai-nilai ekstrem tersebut.
2. **Basic**: Nilai $L > 0.4$ menandakan disorientasi parah, sedangkan $L < 0.2$ menunjukkan navigasi efisien.
3. **Basic**: Wilson Score Interval tetap akurat pada ukuran sampel kecil ($n < 30$) dan pada proporsi ekstrem ($p \approx 0$ atau $p \approx 1$), serta tidak menghasilkan nilai batas inferensi yang melampaui rentang probabilitas valid $[0, 1]$.
4. **Basic**: Tepat sesaat setelah sebuah tugas (*task*) spesifik diselesaikan atau ditinggalkan oleh pengguna (*post-task*), bukan di akhir pengujian keseluruhan sistem (*post-test*).
5. **Basic**: Karena transmisi `navigator.sendBeacon()` dijamin oleh sistem operasi peramban untuk dijadwalkan secara independen dari siklus hidup dokumen, sehingga request tidak dibatalkan saat proses halaman di-terminasi.
6. **Intermediate**: Gunakan uji statistik non-parametrik **Mann-Whitney U Test** (untuk sampel independen) atau **Wilcoxon Signed-Rank Test** (untuk sampel berpasangan).
7. **Intermediate**: *Rage Click* dicirikan oleh rentetan klik berulang cepat pada koordinat yang sama dalam interval singkat ($< 1$ detik), menandakan frustrasi. *Dead Click* dicirikan oleh satu atau beberapa klik pada elemen antarmuka yang statis tanpa memicu perubahan DOM, mutasi CSS, atau network call sama sekali (menandakan elemen salah diinterpretasikan sebagai komponen interaktif).
8. **Intermediate**: Ketimpangan ukuran sampel ditangani dengan menggunakan **Welch's t-test** (yang tidak mengasumsikan kesetaraan varians antar-grup) serta menerapkan koreksi derajat kebebasan (*degrees of freedom*) Welch–Satterthwaite.
9. **Intermediate**: Menghitung rata-rata deviasi dua item dari nilai minimum, membaginya dengan rentang maksimum (12), mengalikannya dengan 100 untuk mendapatkan skala internal, lalu memetakannya ke SUS via persamaan regresi: $\text{SUS} = 0.65 \times \text{UMUX-Lite} + 22.9$.
10. **Intermediate**: Jika *event listener* telemetri dieksekusi secara sinkron pada main thread tanpa teknik *debouncing*, *passive listeners*, atau *background task scheduling* (`requestIdleCallback`), script telemetri akan menahan pemrosesan event loop, sehingga memperpanjang latensi pemrosesan interaksi dan merusak skor INP.
11. **Skenario 1**: Rollout harus ditahan (*halt*). Kenaikan completion rate semu sering terjadi akibat kegagalan visual tombol (misal: feedback loading tidak muncul, sehingga pengguna mengklik berkali-kali hingga request terkirim ganda atau form ter-submit paksa). Lakukan inspeksi pada latensi feedback UI, status disable tombol pasca-klik pertama, dan pastikan idempotency request di API layer.
12. **Skenario 2**: Perbedaan drastis menunjukkan masalah pada responsivitas tata letak atau navigasi adaptif: kemungkinan besar terjadi navigasi siklis akibat tombol "Kembali" perangkat keras (*hardware back button*) yang membatalkan state form, validasi error inline yang tidak otomatis terlihat di layar kecil (*out of viewport*), atau menu accordion yang tertutup otomatis tanpa peringatan.
13. **Skenario 3**: Lakukan migrasi dari row-oriented database ke columnar OLAP engine (seperti ClickHouse, Apache Pinot, atau AWS Redshift). Tempatkan buffer queue (Apache Kafka) di depan ingestion service, lakukan agregasi metrik mikro menggunakan stream processing engine (Apache Flink), dan kompres data historis ke format Apache Parquet.

---

### 16. Summary

- **Metrik Kuantitatif Terukur** mengubah proses desain antarmuka dari perdebatan opini subjektif menjadi cabang rekayasa presisi berbasis data inferensial.
- **Isolasi Telemetri** merupakan fondasi arsitektur frontend skala enterprise: pengumpulan data perilaku (TCR, ToT, Lostness, Rage Clicks) tidak boleh mengorbankan performa render antarmuka pengguna.
- **Rigoritas Statistik** (Wilson Score Interval, log-normal transformation, Mann-Whitney U test) adalah syarat mutlak guna mencegah bias konfirmasi sebelum tim engineering memutuskan untuk mengubah arsitektur aplikasi di tingkat produksi.