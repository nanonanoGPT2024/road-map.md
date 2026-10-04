# Modul Pembelajaran: User Research Rekayasa: Kuantitatif & Kualitatif

---

## SEKSI 01 — IDENTITAS MODUL

* **Kategori Kurikulum:** 03-Frontend-and-Mobile
* **Jalur Spesialisasi:** UX Engineering & Human-Computer Interaction (HCI)
* **Bab:** 02 (User Research & Discovery Phase)
* **Modul:** 01
* **Judul/Topik:** User Research Rekayasa: Kuantitatif & Kualitatif
* **Tingkat Kompleksitas:** Tingkat Lanjut (Advanced)
* **Target Pembaca:** Frontend Engineer, Mobile Developer, UX Engineer, Product Designer Teknis
* **Prasyarat Pengetahuan:** Dasar instrumentasi telemetri peramban (Web APIs, DOM Event Model), dasar statistik deskriptif dan inferensial, serta arsitektur komponen React/TypeScript.

---

## SEKSI 02 — LEARNING OBJECTIVES

1. **Membangun Pipeline Riset Terintegrasi:** Mampu merancang dan mengimplementasikan instrumentasi telemetri sisi klien secara *programmatic* untuk mengumpulkan metrik perilaku kuantitatif (*time-on-task*, *rage clicks*, *drop-off rates*) tanpa mendegradasi performa *rendering thread*.
2. **Triangulasi Data Kuantitatif dan Kualitatif:** Mampu mengorelasikan log kejadian (*event logs*) berkategori kuantitatif dengan sesi evaluasi kualitatif semi-terstruktur berbasis metode *Think-Aloud Protocol* dan pengujian kegunaan (*usability testing*).
3. **Penerapan Pengujian Statistik Lanjut:** Menguasai implementasi uji hipotesis (t-test, Mann-Whitney U, Chi-Square) dan kalkulasi System Usability Scale (SUS) secara komputasional via TypeScript untuk memvalidasi signifikansi hasil iterasi fitur antarmuka pengguna.
4. **Automasi Heuristik Kegunaan:** Mengonversi data perilaku mikro (seperti *dead clicks*, deviasi pergerakan kursor, latensi interaksi) menjadi sinyal telemetri yang secara otomatis memicu umpan balik kualitatif kontekstual (*in-app contextual probes*).

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Dalam rekayasa antarmuka modern, User Research bukan sekadar aktivitas wawancara subjektif oleh desainer, melainkan sub-disiplin teknik berbasis data empiris (*empirical engineering discipline*). 

```
        +---------------------------------------------------------+
        |                 KESEIMBANGAN PENELITIAN                 |
        +---------------------------------------------------------+
        |                                                         |
        |   KUANTITATIF (What & How Much)   KUALITATIF (Why & How)|
        |   =============================   ===================== |
        |   * Log Peristiwa Telemetri       * Mental Model Sesi   |
        |   * Conversion Funnel Drop-off    * Cognitive Friction  |
        |   * Time-to-First-Action (TTFA)   * Frustrasi Semantik  |
        |   * Statistical Significance      * Context of Use      |
        |                                                         |
        |                \                       /                |
        |                 \                     /                 |
        |                  v                   v                  |
        |             +-------------------------------+           |
        |             | TRIANGULASI REKAYASA (TRUTH)  |           |
        |             |  Root Cause Analysis Masalah  |           |
        |             |  Interaksi & Eksekusi UX      |           |
        |             +-------------------------------+           |
        +---------------------------------------------------------+
```

Mental model seorang UX Engineer memandang setiap komponen antarmuka sebagai instrumen pengukur interaksi manusia. Data kuantitatif memberi tahu Anda **di mana** anomali terjadi (misal: tombol Checkout memiliki rasio *error* 18% dan 32% pengguna mengalami *rage click*). Namun, data kuantitatif buta terhadap alasan di balik fenomena tersebut. Data kualitatif mengungkap **mengapa** anomali terjadi (misal: pengguna mengira ikon gembok adalah tombol interaktif untuk membuka diskon, bukan indikator keamanan). 

Mengembangkan produk digital tanpa data kuantitatif bagaikan menavigasi kapal tanpa kompas; mengembangkannya tanpa data kualitatif bagaikan berlayar tanpa mengetahui tujuan akhir. Keunggulan teknis dicapai saat telemetri kode frontend Anda secara otomatis mendeteksi friksi kognitif dan menyajikan konteks kualitatif secara *real-time*.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Di bawah ini adalah arsitektur pipeline terpadu: dari interaksi pengguna di antarmuka web, pemrosesan deteksi heuristik interaksi mikro pada sisi klien (*client-side*), *buffering*, hingga transmisi data ke *analytic ingestion engine* yang memicu survei mikro kualitatif saat ambang batas (*threshold*) anomali terlampaui.

```
+---------------------------------------------------------------------------------------+
| SISI KLIEN (PERAMBAN PENGGUNA)                                                        |
|                                                                                       |
|   +-----------------------+        +----------------------------------------------+   |
|   |   Interaksi User      |        | Performance Observer API                     |   |
|   | (Pointer, Input, Nav) |        | (Long Tasks, INP, FID, CLS)                  |   |
|   +-----------+-----------+        +----------------------+-----------------------+   |
|               |                                           |                           |
|               | (DOM Events: click, input, scroll)        | (Layout Shift & Latency)  |
|               v                                           v                           |
|   +-------------------------------------------------------------------------------+   |
|   | Rekayasa Sensor: UX Telemetry Engine (Custom React Hook / Vanilla Wrapper)     |   |
|   | - Debounced Event Normalizer                                                  |   |
|   | - Heuristic Micro-Behavior Detectors (Rage Click, Dead Click, Thrashing)      |   |
|   +-------------------+-----------------------------------+-----------------------+   |
|                       |                                   |                           |
|      (Anomali Terdeteksi: Threshold Breach)               | (Batching Metrik)         |
|                       v                                   v                           |
|   +-----------------------------------+   +---------------------------------------+   |
|   | Micro-Survey Controller           |   | Telemetry Event Queue (IndexedDB/RAM) |   |
|   | Trigger Form Kualitatif Interaktif|   +-------------------+-------------------+   |
|   | (Contextual Think-Aloud Probe)    |                       |                       |
|   +-------------------+---------------+                       | navigator.sendBeacon  |
+-----------------------|---------------------------------------|-----------------------+
                        |                                       | Web Worker Async Sync
                        | Respon Kualitatif                     | Payload Kuantitatif
                        v                                       v
+---------------------------------------------------------------------------------------+
| BACKEND & PIPELINE ANALITIK                                                           |
|                                                                                       |
|   +-------------------------------------------------------------------------------+   |
|   | Edge Ingestion Gateway (HTTP API / Cloudflare Workers / Kafka Producer)       |   |
|   +---------------------------------------+---------------------------------------+   |
|                                           |                                           |
|                                           v                                           |
|   +-------------------------------------------------------------------------------+   |
|   | Streaming Analytics Core & ETL Pipeline                                       |   |
|   | - Parser Skema Event & Metadata Session                                       |   |
|   | - Korelator: ID Sesi Kuantitatif <---> Log Respon Kualitatif                  |   |
|   +-------------------+-----------------------------------+-----------------------+   |
|                       |                                   |                           |
|                       v                                   v                           |
|   +-----------------------------------+   +---------------------------------------+   |
|   | ClickHouse / TimescaleDB          |   | Elasticsearch / Vector DB             |   |
|   | (Data Deret Waktu & Metrik UX)    |   | (Transkrip Kualitatif & Analisis Teks)|   |
|   +-------------------+---------------+   +-------------------+-------------------+   |
|                       \                                   /                           |
|                        \                                 /                            |
|                         v                               v                             |
|   +-------------------------------------------------------------------------------+   |
|   | Automated Usability Evaluation Dashboard & Statistical Processing Engine      |   |
|   | - Uji Korelasi Mann-Whitney U, Perhitungan Skor SUS, Deteksi Regresi UI       |   |
|   +-------------------------------------------------------------------------------+   |
+---------------------------------------------------------------------------------------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Detektor Interaksi Mikro Kuantitatif
* **Rage Click Engine:** Melacak array waktu stempel klik `[t0, t1, t2...]` dalam radius piksel Euclidean $R \le 30\text{px}$. Jika jumlah klik $N \ge 3$ dalam rentang waktu $\Delta t \le 800\text{ms}$, kondisi ini diklasifikasikan sebagai *Rage Click*. Kondisi ini mengindikasikan frustrasi pengguna terhadap responsivitas visual yang lambat atau tautan/tombol yang macet.
* **Dead Click Engine:** Memvalidasi apakah sebuah peristiwa `click` pada elemen yang secara visual menyerupai kontrol interaktif (misalnya memiliki kursor `pointer`, gaya kartu, atau atribut `aria-role` implisit) menghasilkan mutasi DOM, permintaan jaringan (XHR/Fetch), atau perubahan URL dalam batas toleransi $\Delta t = 1000\text{ms}$. Jika tidak ada mutasi yang terdeteksi, peristiwa tersebut dicatat sebagai *Dead Click*.
* **Form Hesitation Engine:** Menghitung selisih waktu antara fokus elemen input (`focusin`) dan ketukan tombol pertama (`keydown` pertama). Latensi yang terlalu tinggi (misal: $> 4000\text{ms}$) mengindikasikan bahwa label, petunjuk *placeholder*, atau instruksi bidang input memiliki ambiguitas kognitif yang membebani memori kerja pengguna.

### 2. Mesin Evaluasi Kualitatif Kontekstual
* **In-Context Probe Orchestrator:** Alih-alih menampilkan survei acak yang mengganggu, orkestrator mendengarkan *event bus* dari detektor interaksi mikro. Saat terjadi 2 kali *Rage Click* berturut-turut pada alur krusial (misal: formulir pembayaran), orkestrator merender modul umpan balik non-blokir di sudut bawah layar secara asinkron. Modul ini mengajukan satu pertanyaan terbuka yang spesifik terhadap elemen target: *"Apakah ada kendala saat menekan tombol ini?"*.
* **Think-Aloud Protocol Engine:** Menggunakan API perekaman audio peramban (`MediaRecorder API`) yang disinkronkan dengan *DOM Mutation Observer*. Ini memungkinkan peneliti menangkap verbalisasi pemikiran pengguna bersamaan dengan representasi akurat dari keadaan antarmuka saat itu, tanpa memerlukan pengamat eksternal yang dapat memicu *Hawthorne Effect*.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Metrik UX Standar Industri: SUS, SUPR-Q, dan UMUX-Lite

Dalam pengujian kegunaan empiris, data kualitatif diskalakan menjadi metrik ordinal terstandarisasi. Salah satu instrumen yang paling banyak divalidasi adalah **System Usability Scale (SUS)**. SUS terdiri dari 10 pernyataan skala Likert 5 poin (dari "Sangat Tidak Setuju" bernilai 1, hingga "Sangat Setuju" bernilai 5).

#### Algoritma Komputasi Skor SUS:
1. Untuk pertanyaan bernomor ganjil (pernyataan positif: $Q_1, Q_3, Q_5, Q_7, Q_9$), kontribusi skor adalah nilai skala dikurangi 1:
   $$s_i = R_i - 1$$
2. Untuk pertanyaan bernomor genap (pernyataan negatif: $Q_2, Q_4, Q_6, Q_8, Q_{10}$), kontribusi skor adalah 5 dikurangi nilai skala:
   $$s_i = 5 - R_i$$
3. Jumlahkan seluruh kontribusi skor yang telah dikonversi, lalu kalikan dengan konstanta $2.5$ untuk menghasilkan rentang skor absolut 0 hingga 100:
   $$\text{SUS} = \left( \sum_{i=1}^{10} s_i \right) \times 2.5$$

Skor SUS bukanlah persentil. Berdasarkan distribusi empiris Sauro-Lewis:
* Rata-rata industri SUS adalah **68**.
* Skor $\ge 80.3$ berada pada persentil 90 (Grade A: *Excellent*).
* Skor $\le 51$ mengindikasikan masalah kegunaan kritis yang memerlukan intervensi rekayasa segera.

### Pengujian Signifikansi Statistik pada Data UX

Saat mengevaluasi perubahan desain antara Desain Kontrol (A) dan Desain Varian (B), rata-rata mentah tidak boleh langsung dijadikan dasar penarikan kesimpulan. UX Engineer wajib memperhitungkan varians dan ukuran sampel ($N$).

1. **Distribusi Metrik UX yang Bersifat Miring (Skewed Distribution):**
   Metrik waktu penyelesaian tugas (*Time-on-Task*) tidak pernah terdistribusi secara normal (Gaussian). Metrik ini selalu miring ke kanan (*positively skewed* / *log-normal*) karena batas minimum adalah nol, sementara batas atas tidak terhingga. Menerapkan uji parametrik $t$-test standar secara langsung pada data mentah menghasilkan tingkat kesalahan Tipe I (*False Positive*) yang tinggi. Solusi matematisnya adalah menerapkan transformasi logaritmik:
   $$Y = \ln(X)$$
   Atau menggunakan uji non-parametrik **Mann-Whitney U Test** untuk membandingkan distribusi median dari dua sampel independen.

2. **Ukuran Sampel Kualitatif vs Kuantitatif:**
   Berdasarkan model matematika penemuan masalah kegunaan Nielsen & Landauer:
   $$U(n) = N(1 - (1 - L)^n)$$
   Di mana $U(n)$ adalah proporsi masalah yang ditemukan, $N$ adalah total masalah dalam sistem, $L$ adalah probabilitas satu pengguna menemukan masalah (biasanya rata-rata $0.31$), dan $n$ adalah jumlah peserta.
   
   Model ini membuktikan bahwa untuk pengujian kualitatif mendalam (*usability test* murni), $n = 5$ pengguna mampu mengidentifikasi sekitar $85\%$ dari keseluruhan masalah kegunaan. Namun, untuk validasi kuantitatif (menentukan varian mana yang memiliki tingkat konversi atau metrik SUS lebih unggul secara statistik dengan $\alpha = 0.05$ dan $\text{Power } (1-\beta) = 0.80$), diperlukan ukuran sampel $n \ge 30$ hingga ratusan pengguna per sel pengujian.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi pustaka TypeScript murni tanpa dependensi eksternal untuk melacak interaksi mikro (Rage Click, Dead Click) dan modul komputasi SUS engine yang siap diintegrasikan ke framework modern.

```typescript
// File: TelemetryEngine.ts

export interface TelemetryEvent {
  eventType: 'RAGE_CLICK' | 'DEAD_CLICK' | 'FORM_HESITATION';
  targetSelector: string;
  timestamp: number;
  metadata: Record<string, unknown>;
}

export interface RageClickConfig {
  thresholdCount: number;
  timeWindowMs: number;
  radiusPx: number;
}

export class UXInteractionEngine {
  private clickHistory: { x: number; y: number; time: number; target: HTMLElement }[] = [];
  private rageConfig: RageClickConfig;
  private onAnomalyDetected: (event: TelemetryEvent) => void;

  constructor(
    rageConfig: RageClickConfig = { thresholdCount: 3, timeWindowMs: 800, radiusPx: 30 },
    onAnomalyDetected: (event: TelemetryEvent) => void
  ) {
    this.rageConfig = rageConfig;
    this.onAnomalyDetected = onAnomalyDetected;
    this.initListeners();
  }

  private initListeners(): void {
    if (typeof window === 'undefined') return;

    window.addEventListener('click', this.handleGlobalClick.bind(this), { capture: true });
    window.addEventListener('focusin', this.handleFormFocus.bind(this), { capture: true });
  }

  private getCssSelector(el: HTMLElement): string {
    if (el.id) return `#${el.id}`;
    if (el.getAttribute('data-testid')) return `[data-testid="${el.getAttribute('data-testid')}"]`;
    const tag = el.tagName.toLowerCase();
    const className = el.className && typeof el.className === 'string' 
      ? `.${el.className.trim().split(/\s+/).join('.')}` 
      : '';
    return `${tag}${className}`;
  }

  private handleGlobalClick(event: MouseEvent): void {
    const target = event.target as HTMLElement;
    if (!target) return;

    const now = performance.now();
    const currentPoint = { x: event.clientX, y: event.clientY, time: now, target };

    // Bersihkan riwayat yang berada di luar rentang waktu (time window)
    this.clickHistory = this.clickHistory.filter(
      (c) => now - c.time <= this.rageConfig.timeWindowMs
    );
    this.clickHistory.push(currentPoint);

    // Evaluasi Rage Click
    const nearbyClicks = this.clickHistory.filter((c) => {
      const distance = Math.sqrt(
        Math.pow(c.x - currentPoint.x, 2) + Math.pow(c.y - currentPoint.y, 2)
      );
      return distance <= this.rageConfig.radiusPx;
    });

    if (nearbyClicks.length >= this.rageConfig.thresholdCount) {
      this.onAnomalyDetected({
        eventType: 'RAGE_CLICK',
        targetSelector: this.getCssSelector(target),
        timestamp: Date.now(),
        metadata: {
          clickCount: nearbyClicks.length,
          durationMs: now - nearbyClicks[0].time,
        },
      });
      this.clickHistory = []; // Reset setelah deteksi untuk mencegah pemicu berulang
      return;
    }

    // Evaluasi Dead Click (Meneliti apakah elemen yang dapat diklik memicu mutasi)
    this.evaluateDeadClick(target, event);
  }

  private evaluateDeadClick(target: HTMLElement, event: MouseEvent): void {
    const isInteractiveCandidate = 
      window.getComputedStyle(target).cursor === 'pointer' ||
      target.tagName === 'BUTTON' ||
      target.tagName === 'A' ||
      target.getAttribute('role') === 'button';

    if (!isInteractiveCandidate) return;

    const initialHref = window.location.href;
    let domMutated = false;

    // Pasang MutationObserver untuk mendeteksi perubahan visual/struktur DOM
    const observer = new MutationObserver(() => {
      domMutated = true;
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
    });

    setTimeout(() => {
      observer.disconnect();
      const hrefChanged = window.location.href !== initialHref;

      if (!domMutated && !hrefChanged && !event.defaultPrevented) {
        this.onAnomalyDetected({
          eventType: 'DEAD_CLICK',
          targetSelector: this.getCssSelector(target),
          timestamp: Date.now(),
          metadata: {
            tagName: target.tagName,
            innerText: target.innerText?.slice(0, 30) ?? '',
          },
        });
      }
    }, 1000);
  }

  private handleFormFocus(event: FocusEvent): void {
    const target = event.target as HTMLElement;
    if (!target || !(target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement)) {
      return;
    }

    const focusTime = performance.now();
    const handleFirstKey = (keyEvent: KeyboardEvent) => {
      const latency = performance.now() - focusTime;
      // Ambang batas keraguan: Jika pengguna berhenti lebih dari 3500ms sebelum mengetik
      if (latency > 3500) {
        this.onAnomalyDetected({
          eventType: 'FORM_HESITATION',
          targetSelector: this.getCssSelector(target),
          timestamp: Date.now(),
          metadata: { hesitationLatencyMs: Math.round(latency) },
        });
      }
      target.removeEventListener('keydown', handleFirstKey);
    };

    target.addEventListener('keydown', handleFirstKey);
  }

  public destroy(): void {
    if (typeof window === 'undefined') return;
    window.removeEventListener('click', this.handleGlobalClick, { capture: true });
    window.removeEventListener('focusin', this.handleFormFocus, { capture: true });
  }
}

// File: UsabilityStatistics.ts

export type SUSAnswers = [number, number, number, number, number, number, number, number, number, number];

export class UXAnalyticsEngine {
  /**
   * Menghitung System Usability Scale (SUS) Score
   * Jawaban harus berupa array 10 angka dengan rentang nilai 1-5.
   */
  public static calculateSUS(answers: SUSAnswers): number {
    if (answers.length !== 10) {
      throw new Error('SUS mewajibkan tepat 10 respons.');
    }

    let oddSum = 0;
    let evenSum = 0;

    for (let i = 0; i < 10; i++) {
      const val = answers[i];
      if (val < 1 || val > 5) {
        throw new Error(`Nilai jawaban indeks ${i} tidak valid: ${val}. Harus di antara 1 dan 5.`);
      }

      if ((i + 1) % 2 !== 0) {
        // Item Ganjil (1, 3, 5, 7, 9): Posisi bernomor ganjil adalah indeks genap di array
        oddSum += (val - 1);
      } else {
        // Item Genap (2, 4, 6, 8, 10): Posisi bernomor genap adalah indeks ganjil di array
        evenSum += (5 - val);
      }
    }

    const totalContribution = oddSum + evenSum;
    return Number((totalContribution * 2.5).toFixed(2));
  }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Analisis File `TelemetryEngine.ts`

* **Baris 24–27:** `window.addEventListener('click', this.handleGlobalClick.bind(this), { capture: true });`
  Menggunakan opsi `{ capture: true }` (*Event Capturing Phase*). Hal ini menjamin mesin telemetri menangkap interaksi sebelum komponen UI tingkat bawah memanggil `event.stopPropagation()`, yang kerap memutus aliran telemetri analitik standar.
* **Baris 46–49:** Pembersihan riwayat klik `this.clickHistory.filter(c => now - c.time <= this.rageConfig.timeWindowMs);`
  Mencegah kebocoran memori (*memory leak*) pada SPA (*Single Page Application*) berdurasi panjang dengan secara agresif membersihkan riwayat interaksi klik di luar rentang evaluasi.
* **Baris 53–57:** Algoritma Jarak Euclidean `Math.sqrt(Math.pow(c.x - currentPoint.x, 2) + Math.pow(c.y - currentPoint.y, 2))`
  Mengukur jarak fisik piksel antar-klik. Hal ini memvalidasi bahwa serangkaian klik dilakukan pada satu area tombol target yang terkonsentrasi, bukan akibat pengguna yang mengklik beberapa elemen berbeda secara acak.
* **Baris 82–93:** Inisialisasi `MutationObserver` pada `document.body`
  Mengamati perubahan pada hierarki pohon DOM. Jika suatu elemen diklik namun tidak memicu mutasi DOM, perubahan URL, atau pemanggilan *event-default-prevented* dalam kurun waktu 1 detik, elemen tersebut dikategorikan sebagai *Dead Click* (elemen statis yang dikira interaktif oleh pengguna).
* **Baris 112–126:** Penanganan `handleFormFocus` dan `handleFirstKey`
  Mengukur waktu pemrosesan kognitif pengguna (*Cognitive Processing Time*). Jika pengguna mengklik bidang input namun membutuhkan lebih dari 3500ms untuk menekan tombol pertama, ini menjadi sinyal objektif adanya beban kognitif berlebih terkait label atau instruksi input tersebut.

### Analisis File `UsabilityStatistics.ts`

* **Baris 144–165:** Implementasi Normalisasi Standar Skor SUS
  Pada pertanyaan ganjil, skor diskalakan dengan `val - 1` (karena respon bernilai 5 menyumbang kontribusi maksimal 4). Pada pertanyaan genap, skor diskalakan dengan `5 - val` (karena respon bernilai 1 menyumbang kontribusi maksimal 4). Pengali skalar `2.5` mengonversi rentang total komposit 0–40 ke dalam skala standar 0–100.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi: Redesain Modul Pembayaran Enterprise FinTech ("PayFlow Global")

#### Latar Belakang Masalah
PayFlow Global meluncurkan antarmuka alur pembayaran baru yang mendukung multi-mata uang. Tim produk mencatat penurunan rasio konversi penyelesaian transaksi (*Checkout Completion Rate*) sebesar $14.2\%$ pada perangkat tablet dan desktop beresolusi tinggi, sementara metrik latensi jaringan backend (API p99) tetap stabil pada level $120\text{ms}$.

#### Investigasi Kuantitatif
Tim UX Engineering meninjau data telemetri interaksi mikro:
1. Elemen `#split-currency-toggle` menghasilkan rata-rata **4.8 Rage Clicks per sesi unik**.
2. Metrik *Form Hesitation* pada input `#vat-tax-id` melonjak dari $820\text{ms}$ menjadi $6200\text{ms}$.
3. Terjadi lonjakan *Dead Clicks* sebesar $42\%$ pada kontainer visual informasi ringkasan tagihan (`.summary-box-info`).

```
                    METRIK TELEMETRI PAYFLOW GLOBAL
+-------------------------+--------------------+----------------------+
| Elemen UI               | Metrik Terdeteksi  | Nilai Telemetri      |
+-------------------------+--------------------+----------------------+
| #split-currency-toggle  | Rage Click Rate    | 4.8 per sesi         |
| #vat-tax-id             | Form Hesitation    | 6200 ms (Kritis)     |
| .summary-box-info       | Dead Click Rate    | 42% (Anomali Tinggi) |
+-------------------------+--------------------+----------------------+
```

#### Investigasi Kualitatif
Menggunakan *Automated Qualitative Interceptor*, sistem memicu formulir umpan balik interaktif mini berbasis mikro-kuesioner tepat setelah pengguna terdeteksi melakukan *Rage Click* pada `#split-currency-toggle`. Bersamaan dengan itu, 8 sesi uji kegunaan berbasis *Concurrent Think-Aloud* digelar.

**Temuan Lapangan:**
* Pengguna mengira toggle mata uang tersebut bertindak sebagai kalkulator konversi waktu nyata (*live conversion calculator*), padahal sistem baru memproses kalkulasi setelah seluruh formulir divalidasi.
* Label pada `#vat-tax-id` menggunakan istilah legal spesifik yang tidak dipahami oleh pengguna non-korporat, menimbulkan kebingungan interpretasi (*Cognitive Paralysis*).
* Kontainer `.summary-box-info` menggunakan gaya visual kartu (*elevation 2dp* dengan *border-radius 8px*) yang menyerupai tombol akordeon interaktif, memicu pengguna untuk mengkliknya guna melihat rincian biaya tersembunyi.

#### Dampak Rekayasa Berbasis Triangulasi
Berdasarkan data gabungan tersebut:
1. UX Engineer menambahkan *live computation debounce* pada toggle mata uang.
2. Label `#vat-tax-id` direfaktor dengan tambahan *tooltip* kontekstual otomatis saat latensi fokus melebihi 2000ms.
3. Gaya visual `.summary-box-info` diubah menjadi *flat layout* datar tanpa bayangan untuk membedakannya secara jelas dari elemen interaktif.
4. **Hasil Akhir:** Tingkat konversi pulih dan meningkat sebesar $+18.6\%$. Skor rata-rata SUS sistem melonjak dari $58.2$ (kategori *Marginal/Poor*) menjadi $84.5$ (kategori *Excellent/Acceptable*).

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah implementasi sistematis production-ready yang mencakup:
1. Hook React custom (`useUXResearchTracker`) yang memonitor interaksi dan mengelola antrean telemetri.
2. Komponen kualitatif kontekstual (*Contextual Qualitative Interceptor*) yang muncul saat anomali terdeteksi.
3. Servis transmisi telemetri berbasis `navigator.sendBeacon` yang aman dan andal (*reliable*).

```tsx
// File: useUXResearchTracker.tsx
import React, { createContext, useContext, useEffect, useRef, useState, useCallback } from 'react';

export interface TelemetryPayload {
  sessionId: string;
  eventType: string;
  targetSelector: string;
  timestamp: number;
  metadata: Record<string, unknown>;
}

interface UXResearchContextType {
  sessionId: string;
  logFeedback: (feedback: { targetSelector: string; comment: string; rating: number }) => void;
}

const UXResearchContext = createContext<UXResearchContextType | null>(null);

const TELEMETRY_ENDPOINT = '/api/v1/telemetry/events';
const QUALITATIVE_ENDPOINT = '/api/v1/telemetry/qualitative';

export const UXResearchProvider: React.FC<{ sessionId: string; children: React.ReactNode }> = ({
  sessionId,
  children,
}) => {
  const [activeProbe, setActiveProbe] = useState<{ targetSelector: string; eventType: string } | null>(null);
  const eventQueue = useRef<TelemetryPayload[]>([]);
  const flushTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const flushEvents = useCallback(() => {
    if (eventQueue.current.length === 0) return;

    const dataToSend = JSON.stringify({ events: eventQueue.current });
    eventQueue.current = [];

    if (typeof navigator !== 'undefined' && 'sendBeacon' in navigator) {
      const blob = new Blob([dataToSend], { type: 'application/json' });
      navigator.sendBeacon(TELEMETRY_ENDPOINT, blob);
    } else {
      fetch(TELEMETRY_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: dataToSend,
        keepalive: true,
      }).catch((err) => console.error('Gagal mengirimkan telemetri UX:', err));
    }
  }, []);

  const queueEvent = useCallback((event: TelemetryPayload) => {
    eventQueue.current.push(event);
    if (!flushTimeoutRef.current) {
      flushTimeoutRef.current = setTimeout(() => {
        flushEvents();
        flushTimeoutRef.current = null;
      }, 5000); // Batch interval 5 detik
    }
  }, [flushEvents]);

  const logFeedback = useCallback(
    (feedback: { targetSelector: string; comment: string; rating: number }) => {
      const payload = {
        sessionId,
        ...feedback,
        timestamp: Date.now(),
      };

      fetch(QUALITATIVE_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      }).catch((err) => console.error('Gagal mengirimkan log kualitatif:', err));

      setActiveProbe(null); // Tutup probe setelah feedback terkirim
    },
    [sessionId]
  );

  useEffect(() => {
    let clickTimestamps: { time: number; target: HTMLElement; x: number; y: number }[] = [];

    const handleDocumentClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!target) return;

      const now = performance.now();
      const currentSelector = target.id ? `#${target.id}` : target.tagName.toLowerCase();

      // Deteksi Rage Click
      clickTimestamps = clickTimestamps.filter((c) => now - c.time <= 1000);
      clickTimestamps.push({ time: now, target, x: e.clientX, y: e.clientY });

      const clusterClicks = clickTimestamps.filter((c) => {
        const dist = Math.hypot(c.x - e.clientX, c.y - e.clientY);
        return dist <= 40;
      });

      if (clusterClicks.length >= 3) {
        queueEvent({
          sessionId,
          eventType: 'RAGE_CLICK',
          targetSelector: currentSelector,
          timestamp: Date.now(),
          metadata: { count: clusterClicks.length },
        });

        // Tampilkan Interseptor Kualitatif jika belum aktif
        setActiveProbe({
          targetSelector: currentSelector,
          eventType: 'RAGE_CLICK',
        });

        clickTimestamps = [];
      }
    };

    window.addEventListener('click', handleDocumentClick, { capture: true });
    window.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') flushEvents();
    });

    return () => {
      window.removeEventListener('click', handleDocumentClick, { capture: true });
      if (flushTimeoutRef.current) clearTimeout(flushTimeoutRef.current);
      flushEvents();
    };
  }, [sessionId, queueEvent, flushEvents]);

  return (
    <UXResearchContext.Provider value={{ sessionId, logFeedback }}>
      {children}
      {activeProbe && (
        <ContextualQualitativeDialog
          target={activeProbe.targetSelector}
          onDismiss={() => setActiveProbe(null)}
          onSubmit={(rating, comment) =>
            logFeedback({ targetSelector: activeProbe.targetSelector, rating, comment })
          }
        />
      )}
    </UXResearchContext.Provider>
  );
};

export const useUXResearch = () => {
  const context = useContext(UXResearchContext);
  if (!context) {
    throw new Error('useUXResearch harus dijalankan dalam lingkungan UXResearchProvider');
  }
  return context;
};

// File: ContextualQualitativeDialog.tsx

interface DialogProps {
  target: string;
  onSubmit: (rating: number, comment: string) => void;
  onDismiss: () => void;
}

export const ContextualQualitativeDialog: React.FC<DialogProps> = ({
  target,
  onSubmit,
  onDismiss,
}) => {
  const [rating, setRating] = useState<number>(3);
  const [comment, setComment] = useState<string>('');

  return (
    <aside
      aria-label="Panel Umpan Balik Cepat"
      style={{
        position: 'fixed',
