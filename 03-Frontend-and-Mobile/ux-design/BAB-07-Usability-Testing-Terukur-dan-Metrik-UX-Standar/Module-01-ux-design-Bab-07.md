# Kurikulum UX Design: Frontend and Mobile Engineering
## Bab 07: Evaluasi Empiris, Telemetri UX, dan Optimasi Konversi
### Module 01: Usability Testing Terukur & Metrik UX Standar

---

### SEKSI 01 — IDENTITAS MODUL

*   **Jalur Pembelajaran**: Frontend & Mobile Engineering (03-Frontend-and-Mobile)
*   **Domain Spesialisasi**: UX Engineering & Usability Metrics System
*   **Kode Modul**: UX-ENG-0701
*   **Prasyarat Pengetahuan**: 
    *   Pemahaman intermediate mengenai arsitektur SPA (Single Page Application) dan State Management.
    *   Penguasaan JavaScript/TypeScript modern (ES2022+).
    *   Pemahaman dasar tentang statistik deskriptif dan inferensial (Mean, Median, Standard Deviation, Confidence Intervals).
    *   Pengalaman integrasi browser APIs (`PerformanceObserver`, `EventTarget`).
*   **Tingkat Kesulitan**: Tingkat Lanjut (Advanced)
*   **Estimasi Waktu Selesai**: 6 Jam Pembelajaran Mandiri + 4 Jam Lab/Implementasi Praktis

---

### SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini secara komprehensif, engineer dan desainer sistemik ditargetkan mampu:

1.  **Mengoperasikan Metrik Kuantitatif Standar ISO 9241-11**: Menghitung secara deterministik tingkat efektivitas (*Task Completion Rate*), efisiensi (*Time-on-Task*, *Lostness Metric*), dan kepuasan subjektif pengguna (*SUS*, *UMUX-Lite*, *SEQ*).
2.  **Membangun Engine Instrumentasi Pengujian Usabilitas**: Mengembangkan SDK instrumentasi klien menggunakan TypeScript murni untuk merekam data interaksi temporal pengguna secara non-intrusif tanpa membebani performa frame rendering runtime (60/120 FPS).
3.  **Menerapkan Analisis Statistik Inferensial pada Pengujian Sampel Kecil**: Mengonstruksi interval kepercayaan (*Confidence Interval*) 95% menggunakan metode disesuaikan Wald (*Adjusted Wald*) dan Wilson Score untuk sampel $n < 30$, serta mengevaluasi deviasi standar metrik SEQ (*Single Ease Question*).
4.  **Mengintegrasikan Metrik Persepsi Kinerja UX dengan Web Vitals**: Mengkorelasikan degradasi nilai kepuasan pengguna terhadap metrik performa teknis seperti INP (*Interaction to Next Paint*), LCP (*Largest Contentful Paint*), dan CLS (*Cumulative Layout Shift*).
5.  **Merancang dan Mengamankan Pipeline Telemetri Usabilitas**: Menjamin kepatuhan regulasi data privasi (GDPR/UU PDP) melalui arsitektur sanitasi PII (*Personally Identifiable Information*) lokal sebelum metrik dikirim ke downstream analytics pipeline.

---

### SEKSI 03 — MINDSET & MENTAL MODEL

Dalam rekayasa perangkat lunak modern, "usabilitas" sering kali disalahpahami sebagai atribut kualitatif yang abstrak dan subjektif. Pola pikir ini merupakan anti-pattern yang berbahaya bagi skalabilitas sistem. 

```
Mental Model Usabilitas Terukur:
[Usabilitas Bukan Opini] ---> [Usabilitas Adalah Variabel Fisika Sistem Kognitif]
                                        │
             ┌──────────────────────────┴──────────────────────────┐
             ▼                                                     ▼
    Efisiensi Fisik (Mekanik)                            Beban Kognitif (Persepsi)
    - Latensi Input (INP)                                - Task Completion Rate (TCR)
    - Jarak Perpindahan Kursor (Fitts's Law)             - Mental Effort (SEQ)
    - Deviasi Jalur Interaksi (Lostness)                 - Subjective Usability (SUS)
```

Usabilitas harus diperlakukan selayaknya degradasi memori (*memory leak*) atau latensi jaringan (*network latency*): **sesuatu yang dapat diukur, dianalisis secara statistik, diverifikasi secara matematis, dan diperbaiki secara presisi**. 

Saat melakukan *Usability Testing*, praktisi rekayasa frontend tidak menguji "apakah pengguna menyukai antarmuka", melainkan mengukur:
*   Berapa energi kognitif yang dikonsumsi pengguna untuk menyelesaikan satu unit kerja (Task Execution).
*   Seberapa besar deviasi jalur navigasi aktual dibandingkan dengan *Optimal Path Model* (Lostness).
*   Seberapa tinggi probabilitas terjadinya *human error* pada kondisi batas (*boundary conditions*) arsitektur antarmuka.

---

### SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Berikut adalah arsitektur aliran data telemetri pengujian usabilitas, mulai dari interaksi mikro pada DOM hingga agregasi metrik statistik di backend analytics:

```
+---------------------------------------------------------------------------------------+
| BROWSER RUNTIME CLIENT (Browser Context)                                              |
|                                                                                       |
|  [User Actions] ---> Click / Keydown / Touch / Form Input                             |
|          │                                                                            |
|          ▼                                                                            |
|  [DOM Event Capture Phase] (Passive Listeners via WeakMap Registration)               |
|          │                                                                            |
|          ├───> [Lostness Calculator Module]                                            |
|          │      - Total Pages/States Visited (N)                                      |
|          │      - Unique States Visited (S)                                           |
|          │      - Minimum Required States (R)                                         |
|          │                                                                            |
|          ├───> [Time-On-Task Monitor]                                                 |
|          │      - High-Resolution Timestamp via performance.now()                     |
|          │      - Idle Time Detection Filter (Threshold > 5000ms)                    |
|          │                                                                            |
|          └───> [Error & Deviation Logger]                                             |
|                 - Form Validation Bounces (Unproductive inputs)                       |
|                 - Rage Clicks (Rapid clicks within 200ms radius 10px)                 |
|                                                                                       |
|  [Micro-Task Post-Survey Overlay]                                                     |
|          │                                                                            |
|          └───> Captures Single Ease Question (SEQ: 1-7 Likert Scale)                  |
+---------------------------------------------------------------------------------------+
                                           │
                                           │ Serialized Event Envelope
                                           │ via navigator.sendBeacon()
                                           ▼
+---------------------------------------------------------------------------------------+
| INGESTION RUNTIME / EDGE PROXY (Node.js/Cloudflare Workers)                           |
|                                                                                       |
|  [PII Sanitization Filter]                                                            |
|          │ Strips credit cards, passwords, plaintext email tokens                     |
|          ▼                                                                            |
|  [Telemetry Normalization Engine]                                                     |
|          │ Computes Wald Interval, SUS Score Transformation, UMUX Equivalents         |
|          ▼                                                                            |
|  [Time-Series Analytics OLAP Engine] (e.g., ClickHouse / InfluxDB)                     |
+---------------------------------------------------------------------------------------+
```

---

### SEKSI 05 — ANATOMI & MEKANISME INTERNAL

Instrumentasi metrik usabilitas bergantung pada korelasi sinkron antara kondisi mental pengguna dan metrik fungsional sistem:

1.  **Task Completion Rate (TCR / Rasio Keberhasilan)**:
    *   *Mekanisme*: Nilai biner $X \in \{0, 1\}$ yang merepresentasikan kegagalan ($0$) atau keberhasilan ($1$) pemenuhan kriteria penyelesaian (*Definition of Done*) tanpa intervensi fasilitator.
    *   *Statistik*: Menggunakan distribusi Binomial. Untuk sampel kecil ($N < 30$), estimasi proporsi populasi dihitung menggunakan pendekatan **Adjusted Wald Interval**:
        $$\hat{p} = \frac{X + 2}{N + 4}$$
        Di mana $X$ adalah jumlah sukses, dan $N$ adalah jumlah total partisipan.
2.  **Time-on-Task (ToT / Durasi Pengerjaan Tugas)**:
    *   *Mekanisme*: Dihitung menggunakan API presisi tinggi `performance.now()`, memisahkan waktu aktif (*Active Interaction Time*) dengan waktu dorman (*Idle Time* $> 5000\text{ ms}$).
    *   *Distribusi*: Distribusi ToT selalu menceng ke kanan (*positively skewed* / Lognormal). Analisis tidak boleh menggunakan mean aritmatika sederhana, melainkan harus menggunakan **Geometric Mean** atau **Median**.
3.  **Lostness Metric (Tingkat Disorientasi Navigasi)**:
    *   *Mekanisme*: Rasio yang dikembangkan oleh Smith (1996) untuk mengukur derajat disorientasi pengguna saat menelusuri arsitektur informasi:
        $$L = \sqrt{\left(\frac{N}{S} - 1\right)^2 + \left(\frac{R}{N} - 1\right)^2}$$
        *   $R$ = Jumlah minimum layar/state yang diperlukan untuk menyelesaikan tugas secara optimal.
        *   $S$ = Jumlah total layar/state unik yang dikunjungi.
        *   $N$ = Jumlah total layar/state yang dikunjungi pengguna (termasuk *backtracking* / pengulangan).
    *   *Interpretasi Ambang Batas*: Nilai $L > 0.4$ menandakan degradasi signifikan pada arsitektur navigasi, pengguna mengalami disorientasi sistemik. Nilai $L \le 0.4$ menunjukkan eksplorasi yang efisien.
4.  **System Usability Scale (SUS)**:
    *   *Mekanisme*: Skala psikometrik 10 pertanyaan Likert (1–5).
    *   *Kalkulasi*:
        *   Pertanyaan ganjil (1, 3, 5, 7, 9): Kontribusi skor = $\text{Tanggapan} - 1$.
        *   Pertanyaan genap (2, 4, 6, 8, 10): Kontribusi skor = $5 - \text{Tanggapan}$.
        *   Skor Total = $\sum(\text{Kontribusi}) \times 2.5$ (Menghasilkan rentang absolut 0–100).
5.  **Single Ease Question (SEQ)**:
    *   *Mekanisme*: Skala tunggal 7-poin yang diinjeksikan secara real-time langsung setelah sebuah tugas selesai (*post-task injection*). Nilai baseline industri berada pada $5.5$.

---

### SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

#### Distribusi Non-Normal dan Fallacy Analisis Statistik Metrik Usabilitas

Mayoritas engineer melakukan kesalahan fatal ketika mengasumsikan data metrik usabilitas terdistribusi secara normal (Gaussian).

```
Distribusi Lognormal Time-on-Task:
Frekuensi
   │      ▲
   │     ╱ ╲
   │    ╱   ╲  <-- Modus (Tugas selesai cepat)
   │   ╱     ╲
   │  ╱       ╲
   │ ╱    │    ╲────────────┐
   │╱     │     │           ╲────────────────────
   └──────┴─────┴─────────────────────────────────► Durasi (ms)
        Median  Mean
```

Data *Time-on-Task* terikat pada nilai non-negatif ($x \ge 0$) dan memiliki ekor panjang (*long tail*) yang disebabkan oleh interupsi atau beban kognitif tinggi yang sporadis. 

Untuk mentransformasi data ini ke dalam domain normal agar dapat diproses dengan uji parametrik (seperti *Student's t-test*), kita menerapkan transformasi logaritmik natural:
$$Y = \ln(X)$$
Setelah nilai $Y$ didapatkan, kita menghitung mean ($\bar{Y}$) dan standar deviasi ($s_Y$), kemudian mentransformasikan kembali (*back-transform*) ke skala asli melalui eksponensial:
$$\text{Geometric Mean} = e^{\bar{Y}}$$

#### Teori Adjusted Wald untuk Sampel Kecil ($N < 30$)

Dalam pengujian kegunaan formatif (*formative usability testing*), standar industri Nielsen merekomendasikan pengujian pada $5$ hingga $12$ pengguna. Pada ukuran sampel sekecil ini, kalkulasi *Wald Confidence Interval* standar ($\hat{p} \pm Z \sqrt{\frac{\hat{p}(1-\hat{p})}{N}}$) menghasilkan *coverage error* yang sangat buruk (interval yang terbentuk terlalu optimis dan tidak mencakup proporsi populasi sebenarnya).

Solusinya adalah menerapkan metode penyesuaian Agresti-Coull (Adjusted Wald) dengan menambahkan konstanta $Z^2 / 2$ (yang mendekati nilai $2$ untuk batas kepercayaan 95%, di mana $Z = 1.96$):
$$\tilde{n} = N + Z^2 \approx N + 4$$
$$\tilde{p} = \frac{X + \frac{Z^2}{2}}{\tilde{n}} \approx \frac{X + 2}{N + 4}$$
Margin of Error ($W$):
$$W = Z \sqrt{\frac{\tilde{p}(1 - \tilde{p})}{\tilde{n}}}$$
Interval Kepercayaan: $[\tilde{p} - W, \tilde{p} + W]$. Formula ini wajib diimplementasikan dalam engine statistik evaluasi UX.

---

### SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi pustaka mandiri TypeScript untuk melacak metrik usabilitas real-time pada browser: `UsabilityTelemetryEngine.ts`. Modul ini mengelola pelacakan tugas, perhitungan *Lostness*, pendeteksian *Rage Click*, serta kalkulasi *Geometric Mean Time-on-Task*.

```typescript
/**
 * UsabilityTelemetryEngine.ts
 * Pustaka instrumentasi metrik usabilitas tingkat produksi.
 */

export interface TaskConfig {
  taskId: string;
  optimalStepsCount: number; // Nilai R pada formula Lostness
  idleThresholdMs?: number;
}

export interface TaskResult {
  taskId: string;
  isSuccessful: boolean;
  totalTimeMs: number;
  activeTimeMs: number;
  idleTimeMs: number;
  lostness: number;
  rageClicksCount: number;
  uniqueStatesCount: number;
  totalStatesVisited: number;
}

export class UsabilityTelemetryEngine {
  private taskId: string;
  private optimalSteps: number;
  private idleThresholdMs: number;
  
  private startTime: number = 0;
  private lastActivityTime: number = 0;
  private totalIdleTimeMs: number = 0;
  
  private visitedStates: string[] = [];
  private rageClicks: number = 0;
  private clickTimestamps: number[] = [];
  
  private isRunning: boolean = false;
  private abortController: AbortController | null = null;

  constructor(config: TaskConfig) {
    this.taskId = config.taskId;
    this.optimalSteps = config.optimalStepsCount;
    this.idleThresholdMs = config.idleThresholdMs ?? 5000;
  }

  public startTask(initialState: string): void {
    if (this.isRunning) {
      throw new Error(`Tugas ${this.taskId} sudah berjalan.`);
    }

    this.isRunning = true;
    this.startTime = performance.now();
    this.lastActivityTime = this.startTime;
    this.totalIdleTimeMs = 0;
    this.visitedStates = [initialState];
    this.rageClicks = 0;
    this.clickTimestamps = [];
    this.abortController = new AbortController();

    this.bindDOMObservers(this.abortController.signal);
  }

  public recordStateTransition(newStateId: string): void {
    if (!this.isRunning) return;
    this.evaluateActivity();
    this.visitedStates.push(newStateId);
  }

  public completeTask(success: boolean): TaskResult {
    if (!this.isRunning) {
      throw new Error(`Tidak ada tugas yang sedang aktif untuk dihentikan.`);
    }

    const endTime = performance.now();
    this.evaluateActivity(endTime);
    this.isRunning = false;

    if (this.abortController) {
      this.abortController.abort();
      this.abortController = null;
    }

    const totalDuration = endTime - this.startTime;
    const activeDuration = totalDuration - this.totalIdleTimeMs;
    const lostnessMetric = this.calculateLostness();

    return {
      taskId: this.taskId,
      isSuccessful: success,
      totalTimeMs: Math.round(totalDuration),
      activeTimeMs: Math.round(activeDuration),
      idleTimeMs: Math.round(this.totalIdleTimeMs),
      lostness: parseFloat(lostnessMetric.toFixed(4)),
      rageClicksCount: this.rageClicks,
      uniqueStatesCount: new Set(this.visitedStates).size,
      totalStatesVisited: this.visitedStates.length,
    };
  }

  private calculateLostness(): number {
    const R = this.optimalSteps;
    const N = this.visitedStates.length;
    const S = new Set(this.visitedStates).size;

    if (S === 0 || N === 0) return 0;
    
    // Smith's Formula: L = sqrt((N/S - 1)^2 + (R/N - 1)^2)
    const term1 = Math.pow((N / S) - 1, 2);
    const term2 = Math.pow((R / N) - 1, 2);
    
    return Math.sqrt(term1 + term2);
  }

  private evaluateActivity(now = performance.now()): void {
    const elapsedSinceLastActivity = now - this.lastActivityTime;
    if (elapsedSinceLastActivity > this.idleThresholdMs) {
      this.totalIdleTimeMs += (elapsedSinceLastActivity - this.idleThresholdMs);
    }
    this.lastActivityTime = now;
  }

  private bindDOMObservers(signal: AbortSignal): void {
    const clickHandler = (event: MouseEvent) => {
      const now = performance.now();
      this.evaluateActivity(now);
      
      // Deteksi Rage Click: 3 klik dalam 500ms dalam radius 15px
      this.clickTimestamps.push(now);
      this.clickTimestamps = this.clickTimestamps.filter(t => now - t <= 500);

      if (this.clickTimestamps.length >= 3) {
        this.rageClicks++;
        this.clickTimestamps = []; // Reset setelah deteksi
      }
    };

    const inputHandler = () => {
      this.evaluateActivity();
    };

    window.addEventListener('click', clickHandler, { capture: true, passive: true, signal });
    window.addEventListener('keydown', inputHandler, { capture: true, passive: true, signal });
    window.addEventListener('scroll', inputHandler, { capture: true, passive: true, signal });
  }
}
```

---

### SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi teknis komponen vital dari `UsabilityTelemetryEngine.ts`:

*   **Baris 48–60 (`startTask`)**: Menginisialisasi `performance.now()`. Berbeda dengan `Date.now()`, `performance.now()` menggunakan *monotonically increasing timer* yang tidak terpengaruh oleh penyesuaian waktu OS atau jitter NTP, esensial untuk durasi sub-milidetik. `AbortController` diciptakan untuk mempermudah pelepasan seluruh listener secara bersih saat tugas berakhir.
*   **Baris 63–66 (`recordStateTransition`)**: Merekam perubahan state/rute aplikasi (misal, transisi antar-tahapan checkout). Setiap transisi memeriksa *idle time* untuk memastikan waktu transisi tidak memicu bias dorman.
*   **Baris 82–93 (`TaskResult` aggregation)**: Memisahkan secara ketat antara `totalTimeMs`, `activeTimeMs`, dan `idleTimeMs`. Membantu menganalisis apakah pengguna lambat karena membaca instruksi sistem yang rumit (*high active time*) atau terdistraksi oleh faktor eksternal (*high idle time*).
*   **Baris 95–106 (`calculateLostness`)**: Mengimplementasikan formula Smith secara eksak. Jika pengguna bergerak secara optimal sesuai skenario ($R = N = S$), maka:
    $$L = \sqrt{\left(\frac{R}{R} - 1\right)^2 + \left(\frac{R}{R} - 1\right)^2} = \sqrt{0 + 0} = 0$$
    Jika terjadi banyak *looping* atau redundansi ($N \gg S$), nilai $L$ akan membesar secara signifikan.
*   **Baris 116–135 (`bindDOMObservers`)**: Menggunakan `{ capture: true, passive: true }`. Modus *capture* menjamin event terdeteksi sebelum aplikasi mengeksekusi `event.stopPropagation()`, sementara opsi *passive* memastikan listener tidak memblokir jalur kritis thread rendering UI (*compositor thread*).

---

### SEKSI 09 — STUDI KASUS NYATA

#### Permasalahan: Kegagalan Arsitektur Checkout Multi-Step Perusahaan FinTech

**Konteks**: Platform pembiayaan B2B mengalami drop-off sebesar 42% pada alur pengajuan kredit usaha. Alur terdiri dari 4 tahapan: Identitas Bisnis, Keuangan, Dokumen Legal, dan Tanda Tangan Digital. Tim bisnis menuduh form legal terlalu panjang, sementara tim UI menduga tombol interaksi tidak jelas.

**Data Awal Pengujian Usabilitas Konvensional (Kualitatif, $N = 10$)**:
Partisipan merasa "alur cukup membingungkan", namun tidak ditemukan pola jelas bagian mana yang harus direfaktor.

**Solusi Berbasis Telemetri Metrik Standar**:
Engine telemetri usabilitas diintegrasikan ke alur pengujian dengan parameter:
*   *Optimal Steps ($R$)* = 4 state.
*   Metrik evaluasi: TCR (Adjusted Wald CI 95%), Lognormal Mean Time-on-Task, Lostness Metric ($L$), dan Post-Task SEQ.

**Temuan Data Terukur**:
1.  **Lostness Metric**: Tahap Identitas Bisnis ($L = 0.12$), Tahap Finansial ($L = 0.22$), Tahap Dokumen Legal ($L = 0.68$). Pengguna rata-rata melakukan $N = 14$ perpindahan state untuk mencapai $S = 4$ dokumen legal yang diminta.
2.  **Rage Clicks**: Terjadi 148 kali klik beruntun pada elemen unggah dokumen PDF di perangkat mobile.
3.  **SEQ**: Skor rata-rata Dokumen Legal adalah $2.4 / 7.0$, mengindikasikan beban mental ekstrem.
4.  **Akar Masalah**: Sistem penyerahan berkas menolak format PDF tanpa memberikan indikasi status parsing; pengguna mengklik tombol unggah berkali-kali karena tidak adanya status progress/loading (*feedback vacuum*), menyebabkan pengguna berpindah layar bolak-balik untuk mengecek kesalahan input.

---

### SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah implementasi agregator statistik backend untuk mengevaluasi data pengujian usabilitas, mencakup penghitungan *SUS Scoring*, *Adjusted Wald Interval*, dan transformasi *Lognormal Mean*:

```typescript
/**
 * UsabilityMetricsAggregator.ts
 * Engine analisis statistik metrik kegunaan berskala enterprise.
 */

export interface RawUsabilitySession {
  participantId: string;
  isSuccessful: boolean;
  timeOnTaskMs: number;
  lostness: number;
  seqScore: number; // 1 - 7
  susAnswers: number[]; // Array panjang 10, skala 1 - 5
}

export interface StatisticalAnalysisReport {
  sampleSize: number;
  completionRate: {
    pointEstimate: number;
    ciLower: number;
    ciUpper: number;
  };
  timeOnTask: {
    geometricMeanSeconds: number;
    medianSeconds: number;
  };
  lostness: {
    mean: number;
    disorientedUsersPercentage: number;
  };
  seq: {
    mean: number;
    standardDeviation: number;
  };
  sus: {
    meanScore: number;
    percentileGrade: 'A' | 'B' | 'C' | 'D' | 'F';
  };
}

export class UsabilityMetricsAggregator {
  public static calculateSUSScore(answers: number[]): number {
    if (answers.length !== 10) {
      throw new Error('SUS mewajibkan tepat 10 butir instrumen evaluasi.');
    }

    let rawScore = 0;
    for (let i = 0; i < 10; i++) {
      const val = answers[i];
      if (val < 1 || val > 5) {
        throw new Error(`Jawaban pada indeks ${i} di luar batas: ${val}`);
      }

      // Indeks ganjil (posisi pertanyaan 1, 3, 5, 7, 9) -> val - 1
      if (i % 2 === 0) {
        rawScore += (val - 1);
      } else {
        // Indeks genap (posisi pertanyaan 2, 4, 6, 8, 10) -> 5 - val
        rawScore += (5 - val);
      }
    }

    return rawScore * 2.5;
  }

  public static analyzeDataset(sessions: RawUsabilitySession[]): StatisticalAnalysisReport {
    const n = sessions.length;
    if (n === 0) {
      throw new Error('Dataset tidak boleh kosong untuk analisis statistik.');
    }

    // 1. Task Completion Rate via Adjusted Wald (95% CI -> Z = 1.96)
    const Z = 1.96;
    const successes = sessions.filter(s => s.isSuccessful).length;
    const adjustedN = n + Math.pow(Z, 2);
    const adjustedSuccesses = successes + (Math.pow(Z, 2) / 2);
    const pTilde = adjustedSuccesses / adjustedN;
    const marginOfError = Z * Math.sqrt((pTilde * (1 - pTilde)) / adjustedN);

    // 2. Time on Task (Geometric Mean via Log Transformation)
    const logTimes = sessions.map(s => Math.log(s.timeOnTaskMs / 1000));
    const meanLogTime = logTimes.reduce((acc, val) => acc + val, 0) / n;
    const geometricMeanSec = Math.exp(meanLogTime);

    const sortedTimes = sessions.map(s => s.timeOnTaskMs / 1000).sort((a, b) => a - b);
    const medianSec = n % 2 === 0
      ? (sortedTimes[n / 2 - 1] + sortedTimes[n / 2]) / 2
      : sortedTimes[Math.floor(n / 2)];

    // 3. Lostness Analysis
    const meanLostness = sessions.reduce((acc, s) => acc + s.lostness, 0) / n;
    const disorientedCount = sessions.filter(s => s.lostness > 0.4).length;
    const disorientedPct = (disorientedCount / n) * 100;

    // 4. SEQ Calculation
    const seqScores = sessions.map(s => s.seqScore);
    const meanSeq = seqScores.reduce((acc, val) => acc + val, 0) / n;
    const varianceSeq = seqScores.reduce((acc, val) => acc + Math.pow(val - meanSeq, 2), 0) / (n - 1 || 1);
    const stdDevSeq = Math.sqrt(varianceSeq);

    // 5. System Usability Scale (SUS) Processing
    const susScores = sessions.map(s => this.calculateSUSScore(s.susAnswers));
    const meanSus = susScores.reduce((acc, val) => acc + val, 0) / n;

    // Menentukan kurva distribusi persentil Sauro-Lewis
    let susGrade: 'A' | 'B' | 'C' | 'D' | 'F' = 'F';
    if (meanSus >= 80.3) susGrade = 'A';
    else if (meanSus >= 74) susGrade = 'B';
    else if (meanSus >= 68) susGrade = 'C';
    else if (meanSus >= 51) susGrade = 'D';

    return {
      sampleSize: n,
      completionRate: {
        pointEstimate: parseFloat((successes / n).toFixed(4)),
        ciLower: parseFloat(Math.max(0, pTilde - marginOfError).toFixed(4)),
        ciUpper: parseFloat(Math.min(1, pTilde + marginOfError).toFixed(4)),
      },
      timeOnTask: {
        geometricMeanSeconds: parseFloat(geometricMeanSec.toFixed(2)),
        medianSeconds: parseFloat(medianSec.toFixed(2)),
      },
      lostness: {
        mean: parseFloat(meanLostness.toFixed(4)),
        disorientedUsersPercentage: parseFloat(disorientedPct.toFixed(2)),
      },
      seq: {
        mean: parseFloat(meanSeq.toFixed(2)),
        standardDeviation: parseFloat(stdDevSeq.toFixed(2)),
      },
      sus: {
        meanScore: parseFloat(meanSus.toFixed(2)),
        percentileGrade: susGrade,
      },
    };
  }
}
```

---

### SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Metrik / Pendekatan | Biaya Komputasi Klien | Akurasi Diagnostik Masalah | Kompleksitas Analisis Data | Keterbatasan Utama |
| :--- | :--- | :--- | :--- | :--- |
| **System Usability Scale (SUS)** | Nol (Post-test survey) | Makro (Hanya mengukur persepsi holistik) | Rendah (Skor skalar 0–100) | Tidak dapat mendeteksi elemen antarmuka spesifik yang gagal. |
| **Single Ease Question (SEQ)** | Minimal (DOM Injection 1 item) | Mikro (Per-task spesifik) | Sangat Rendah (Skala 1–7) | Rentan terhadap *recency bias* dan bias kesopanan partisipan. |
| **Lostness Metric ($L$)** | Rendah (State tracking) | Sangat Tinggi (Struktur Navigasi/IA) | Menengah (Perlu pemodelan rute optimal $R$) | Memerlukan spesifikasi jalur ideal ($R$) yang akurat sebelum pengujian. |
| **Time-on-Task (ToT)** | Sangat Rendah (`performance.now`) | Menengah (Efisiensi mekanik pengguna) | Tinggi (Wajib pemodelan Lognormal & filtering idle) | Durasi tinggi belum tentu buruk jika alur bersifat eksploratif. |
| **Eye-Tracking Heatmaps** | Sangat Tinggi (Membutuhkan hardware/webcam ML) | Tinggi (Atensi visual) | Sangat Tinggi (Analisis area of interest / AOI) | *High noise-to-signal ratio*; membebani CPU secara masif jika berbasis JS. |

---

### SEKSI 12 — EDGE CASES & PITFALLS

#### 1. Zero-Task Completion Trap
Jika $X = 0$ dari $N = 10$ partisipan:
*   *Pendekatan Standar (Error)*: Mengklaim rasio keberhasilan $0\%$ dengan margin error $0\%$.
*   *Mitigasi Terukur*: Formula Adjusted Wald tetap memberikan estimasi ilmiah yang valid:
    $$\tilde{p} = \frac{0 + 2}{10 + 4} = \frac{2}{14} \approx 14.28\%$$
    Interval atas menunjukkan bahwa hingga $\approx 32\%$ populasi masih memiliki kemungkinan lolos dari skenario ini secara kebetulan.

#### 2. Invisible Idle Pitfall (Tab Switching)
Pengguna berpindah tab browser di tengah pengerjaan tugas usability untuk menjawab pesan Slack.
*   *Kegagalan Telemetri*: Waktu durasi tugas melonjak ke ribuan detik, merusak analisis parametrik.
*   *Mitigasi*: Integrasikan Web Visibility API:
    ```typescript
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        // Hentikan tracking timer aktif seketika
        this.pauseActiveTimer();
      } else {
        this.resumeActiveTimer();
      }
    });
    ```

#### 3. Single-Page App (SPA) Virtual History Confusion
Pada arsitektur SPA yang menggunakan dynamic virtual rendering tanpa manipulasi browser history, rute dokumen tidak pernah berubah. Akibatnya, nilai unik state ($S$) dan total kunjungan ($N$) bernilai $1$, merusak validitas kalkulasi *Lostness*.
*   *Solusi Arsitektural*: Binding State Transition engine langsung pada state management layer (Redux reducer, Zustand store, atau UI Router) ketimbang bergantung murni pada event `popstate` atau URL window.

---

### SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

1.  **Menggunakan Rata-Rata Aritmatika untuk Data Time-on-Task**:
    *   *Kesalahan*: Menghitung $\frac{\sum T}{N}$ pada data durasi. Nilai terdistorsi oleh satu pengguna yang memerlukan waktu sangat panjang.
    *   *Solusi*: Gunakan *Geometric Mean* ($\exp(\text{mean}(\ln(T)))$) atau *Median*.
2.  **Menanyakan Pertanyaan Usabilitas Sebelum Tugas Selesai**:
    *   *Kesalahan*: Memberikan kuesioner SEQ di tengah alur pengerjaan tugas.
    *   *Solusi*: SEQ hanya boleh dirender ketika penanda kriteria tugas tercapai atau tombol eksplisit penghentian tugas ditekan.
3.  **Mengabaikan Variabel "R" dalam Lostness**:
    *   *Kesalahan*: Menganggap nilai $R$ (jalur optimal) bersifat dinamis sesuai preferensi pengguna.
    *   *Solusi*: Tentukan $R$ secara formal bersama tim arsitektur informasi sebagai rute paling efisien tanpa backtracking secara matematis sebelum testing dimulai.
4.  **Menyamakan Skor SUS dengan Persentase Nilai Ujian**:
    *   *Kesalahan*: Menganggap skor SUS $68$ setara dengan nilai "D" (gagal) seperti sistem akademik.
    *   *Solusi*: Pahami bahwa secara empiris skor SUS $68$ merepresentasikan persentil ke-50 (Median Baseline industri global / Grade C).

---

### SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

*   **Non-Intrusive Observation Architecture**: Telemetri pengujian usabilitas tidak boleh memodifikasi timing eksekusi frame rendering runtime. Perekaman data harus sepenuhnya terisolasi dalam *microtasks* atau *requestIdleCallback*.
*   **Sample Size Sizing Berdasarkan Permasalahan**:
    *   Pengujian Formatif (Mencari *usability bugs*): $n = 5$ menemukan $\approx 85\%$ masalah antarmuka (Nielsen-Landauer Model).
    *   Pengujian Sumatif/Benchmark (Validasi metrik