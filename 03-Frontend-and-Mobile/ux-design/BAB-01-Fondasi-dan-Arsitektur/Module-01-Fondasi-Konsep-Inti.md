# Bab 01: Fondasi UX Architecture & Behavioral Engineering
## Module 01: Core UX Mechanics, Cognitive Models, dan Instrumentation

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis Kesenjangan Kognitif (*Gulf of Execution & Gulf of Evaluation*)**: Mengidentifikasi titik friksi mental antara model mental pengguna (*mental model*) dan arsitektur sistem (*system model*) pada antarmuka digital.
- **Mengimplementasikan Hukum-Hukum Ergonomi Kognitif (Hick-Hyman, Fitts, Doherty)**: Mengonversi prinsip-prinsip teoretis UX ke dalam parameter kuantitatif sistem front-end, seperti pembatasan branching UI, optimasi ukuran target sentuh (*hit-target scaling*), dan pereduksian latensi interaksi di bawah ambang batas persepsi visual ($<400\text{ ms}$).
- **Membangun Pipeline UX Telemetry & Behavioral Analytics**: Mengembangkan modul instrumentasi berbasis TypeScript untuk mengukur metrik persepsi pengguna secara *real-time* (Rage Clicks, Dead Clicks, Interaction to Next Paint/INP, Cumulative Layout Shift/CLS) tanpa membebani *main-thread performance*.
- **Merancang Finite State Machine (FSM) untuk Alur Antarmuka Kompleks**: Mengeliminasi *impossible UI states* menggunakan pemodelan transisi status yang deterministik guna menjamin konsistensi navigasi dan pemulihan kesalahan (*error recovery*).

---

### 2. Introduction & Architectural Context

User Experience (UX) Architecture dalam rekayasa perangkat lunak modern bukanlah sekadar perancangan estetika visual (*look and feel*), melainkan **disiplin rekayasa sistem yang meminimalkan beban kognitif (*cognitive load*) pengguna melalui optimasi transfer informasi dan determinisme interaksi**. Antarmuka adalah jembatan translasional antara *human mental model* (heuristik internal pengguna tentang cara kerja dunia) dan *implementation model* (arsitektur data, basis data, dan status aplikasi sebenarnya).

```
+-----------------------------------------------------------------------+
|                         HUMAN MENTAL MODEL                            |
|       (Harapan: Instan, Linear, Toleran terhadap Kesalahan)          |
+-----------------------------------------------------------------------+
                                  │  ▲
           Gulf of Execution (HOW) │  │ Gulf of Evaluation (WHAT HAPPENED)
                                  ▼  │
+-----------------------------------------------------------------------+
|                    UX ARCHITECTURAL TRANSLATION                       |
|       (Affordance, Feedback Loops, Optimistic UI, Error State)       |
+-----------------------------------------------------------------------+
                                  │  ▲
                      DOM Events  │  │ Render / Paint Pipeline
                                  ▼  │
+-----------------------------------------------------------------------+
|                        SYSTEM RUNTIME MODEL                           |
|       (Asinkron, Terdistribusi, Berpotensi Terjadi Latensi/Network)   |
+-----------------------------------------------------------------------+
```

Jika terjemahan ini gagal, timbul dua jurang pemisah kognitif (*Norman's Gulfs*):
1. **Gulf of Execution**: Pengguna kesulitan memetakan intensi mereka (misal: "Saya ingin membatalkan transaksi ini") ke dalam tindakan nyata yang disediakan oleh UI (misal: tombol ambigu, alur navigasi tersembunyi).
2. **Gulf of Evaluation**: Pengguna kesulitan memahami status sistem saat ini setelah suatu tindakan dieksekusi (misal: tombol loading tanpa feedback progresif, mutasi data tanpa konfirmasi visual deterministik).

Dalam arsitektur *production-grade*, kegagalan UX termanifestasi sebagai pembengkakan *bounce rate*, *drop-off* pada *checkout funnel*, kesalahan entri data operasional, hingga lonjakan tiket eskalasi dukungan teknis. Oleh karena itu, UX harus dirancang, diinstrumentasi, dan divalidasi dengan rigor matematis dan arsitektural yang sama dengan sistem *backend*.

---

### 3. Core Concept & Mechanics

#### A. Ergonomi Kognitif Matematis
UX berbasis rekayasa bertumpu pada tiga formulasi matematis fundamental:

1. **Hukum Fitts ($T = a + b \log_2(1 + \frac{D}{W})$)**:
   - Waktu ($T$) yang dibutuhkan untuk memindahkan kursor/jari ke area target adalah fungsi logaritmik dari jarak ($D$) ke target dibagi lebar ($W$) target.
   - *Implemetasi Teknis*: Elemen interaktif kritis (CTA, tombol konfirmasi) harus memiliki area sentuh minimum $48 \times 48\text{ px}$ (WCAG 2.5.5) dan ditempatkan pada zona ergonomis layar (misal: area bawah pada antarmuka *mobile* / *thumb zone*).

2. **Hukum Hick-Hyman ($T = b \cdot \log_2(n + 1)$)**:
   - Waktu pengambilan keputusan bertambah secara logaritmik seiring bertambahnya jumlah pilihan ($n$).
   - *Implementasi Teknis*: Reduksi percabangan UI. Hindari *mega-menu* yang tidak terstruktur; implementasikan *progressive disclosure* dan arsitektur *stepper* berfase.

3. **Doherty Threshold**:
   - Produktivitas pengguna meningkat secara eksponensial ketika interaksi antara komputer dan pengguna dieksekusi dalam tempo $<400\text{ ms}$.
   - *Implementasi Teknis*: Responsivitas UI tidak boleh menunggu respons jaringan I/O. Gunakan *Optimistic UI updates*, *Skeleton screens*, dan pemisahan rendering asinkron.

#### B. Anatomi Metrik Perilaku Kuantitatif
Untuk mengukur friksi UX di level kode, kita memetakan perilaku visual menjadi sinyal telemetri terukur:
- **Rage Clicks**: Definisi operasional: $\ge 3$ klik pada target DOM yang sama atau elemen berdekatan dalam rentang waktu $\le 500\text{ ms}$. Sinyal ini menunjukkan frustrasi pengguna akibat antarmuka yang tidak responsif (*unresponsive thread*) atau *affordance* yang menipu.
- **Dead Clicks**: Klik pada elemen statis yang memiliki visual affordance menyerupai elemen interaktif (misal: teks yang di-underline, badge statis dengan pointer cursor), di mana tidak terjadi mutasi DOM atau *network call* dalam $1000\text{ ms}$.
- **Interaction to Next Paint (INP)**: Mengukur latensi terburuk dari interaksi pengguna (klik, ketukan, input keyboard) hingga frame visual berikutnya di-*paint* oleh browser engine.

---

### 4. Why This Matters

Mengabaikan arsitektur UX di tingkat rekayasa front-end memiliki konsekuensi performa dan bisnis yang terukur:

1. **Skenario Kegagalan Sistem Transaksional**:
   Pada platform e-commerce volume tinggi, jika tombol *Submit Order* tidak menerapkan *state locking* deterministik (FSM) atau feedback instan saat terjadi *network throttling*, pengguna akan melakukan *double-submit* atau *rage click*. Dampaknya: duplikasi mutasi basis data, inkonsistensi stok, dan beban *read/write contention* pada kluster database.
2. **Degradasi Core Web Vitals (INP & CLS)**:
   Pembaruan layout dinamis yang tidak memperhitungkan ukuran ruang (*layout shift*) menyebabkan nilai CLS $> 0.25$. Pengguna salah menekan elemen (misal: menekan "Hapus Akun" alih-alih "Batal"), memicu *catastrophic user error* dan menurunkan *ranking* SEO teknis secara global.
3. **Latensi Kognitif vs. Machine Latency**:
   Mengoptimasi query backend dari $80\text{ ms}$ ke $20\text{ ms}$ tidak memberikan dampak signifikan jika front-end membekukan UI thread selama $600\text{ ms}$ untuk melakukan parsing payload JSON raksasa sebelum memberikan umpan balik visual kepada pengguna.

---

### 5. What Happens Behind the Scenes

Ketika pengguna berinteraksi dengan sebuah elemen pada aplikasi web modern, alur proses kognitif dan komputasional berjalan secara terororkestrasi:

```
[User Action: Click Button]
        │
        ▼
[Browser Event Demultiplexer] ── (Captures 'pointerdown' / 'pointerup')
        │
        ├─── Main Thread (Macro-task Queue)
        │       │
        │       ├─ 1. Hit-Testing: Perhitungan koordinat viewport vs CSS Render Tree
        │       ├─ 2. Dispatch Event: Event propagation (Capture -> Target -> Bubble)
        │       ├─ 3. Event Listener Execution (JS Engine):
        │       │       ├─ Perubahan State lokal (FSM: IDLE -> PENDING)
        │       │       ├─ Trigger Optimistic Render
        │       │       └─ Telemetry Observer Capture: Catat timestamp interaksi
        │       │
        │       └─ 4. Layout & Recalculate Styles -> Paint -> Composite
        │
        ▼ (Target < 16ms / Frame)
[Visual Update / Feedback Presented to Retina] (Doherty Check Passed)
        │
        ▼ (Background Worker / Micro-task)
[Network Request Issued] ── (Fetch API ke REST/GraphQL API)
        │
        ├── (Sukses) ── Mutasi Dikonfirmasi (FSM: PENDING -> SUCCESS)
        └── (Gagal)  ── Kompensasi/Rollback UI (FSM: PENDING -> ERROR_COMPENSATED)
```

1. **Hit-Testing**: Browser mengurai pohon komposit (*composited layer tree*) untuk menentukan elemen node DOM mana yang berada di bawah koordinat input $X, Y$.
2. **Telemetry Sampling**: Modul telemetri mengamati siklus hidup event. Bila event memicu kalkulasi berat pada JavaScript main-thread, browser menunda fase *rendering/painting*, menghasilkan *long task* ($> 50\text{ ms}$) yang langsung terdeteksi sebagai degradasi INP.
3. **Optimistic Rendering**: Antarmuka yang tangguh tidak menunggu *round-trip time* (RTT) jaringan. State UI segera beralih ke representasi sukses hipotetis, sementara *event dispatcher* mendaftarkan mekanisme *reversion* (pembatalan) jika jaringan mengembalikan kode status $\ge 400$.

---

### 6. Architecture Diagram

Berikut arsitektur decoupled antara antarmuka pengguna, penanganan status deterministik, dan mesin instrumentasi analitik perilaku:

```
+─────────────────────────────────────────────────────────────────────────────+
|                               VIEWPORT (DOM)                                |
|  [ Interactive Target ]  <--- (Pointer Events: click, down, keypress)       |
+─────────────────────────────────────────────────────────────────────────────+
           │                                                │
           │ (1) Raw Pointer Stream                         │ (4) Render / Mutasi DOM
           ▼                                                ▼
+───────────────────────────+                    +───────────────────────────+
|   UX TELEMETRY COLLECTOR  |                    |     UI STATE MACHINE      |
|                           |                    |                           |
| - Rage Click Detector     |                    |  [IDLE] ───(SUBMIT)───►   |
| - Dead Click Analyzer     |                    |    ▲           [PENDING]  |
| - Event Timing (INP)      |                    |    │               │      |
+───────────────────────────+                    | (ROLLBACK)     (RESOLVE)  |
           │                                     |    │               ▼      |
           │ (2) Sinyal Kuantitatif              |  [ERROR]      [SUCCESS]   |
           ▼                                     +───────────────────────────+
+───────────────────────────+                                  ▲
| BEHAVIORAL ANALYTICS BUS  |                                  │ (3) Action Trigger
| (Event Batching & Buffer) | ─────────────────────────────────┘
+───────────────────────────+
           │
           │ (5) Asynchronous Flush (Beacon API)
           ▼
+─────────────────────────────────────────────────────────────────────────────+
|                         BACKEND TELEMETRY INGESTION                         |
+─────────────────────────────────────────────────────────────────────────────+
```

---

### 7. Code Implementation: Minimal Working Example

Contoh minimal runtime TypeScript murni untuk mendeteksi *Rage Clicks* (indikator utama frustrasi kognitif akibat friksi UI) tanpa dependensi eksternal:

```typescript
// rage-click-detector.ts

export interface RageClickPayload {
  targetSelector: string;
  clickCount: number;
  timeSpanMs: number;
  timestamp: number;
}

export type RageClickCallback = (payload: RageClickPayload) => void;

export class RageClickDetector {
  private clickHistory: Array<{ target: HTMLElement; time: number }> = [];
  private readonly thresholdClicks: number;
  private readonly thresholdWindowMs: number;
  private readonly callback: RageClickCallback;

  constructor(
    callback: RageClickCallback,
    thresholdClicks = 3,
    thresholdWindowMs = 500
  ) {
    this.callback = callback;
    this.thresholdClicks = thresholdClicks;
    this.thresholdWindowMs = thresholdWindowMs;
    this.init();
  }

  private init(): void {
    window.addEventListener('pointerdown', this.handlePointerDown, {
      passive: true,
      capture: true,
    });
  }

  private handlePointerDown = (event: PointerEvent): void => {
    const target = event.target as HTMLElement;
    if (!target) return;

    const now = performance.now();
    this.clickHistory.push({ target, time: now });

    // Hapus klik yang berada di luar rentang jendela evaluasi
    this.clickHistory = this.clickHistory.filter(
      (entry) => now - entry.time <= this.thresholdWindowMs
    );

    // Ambil klik yang terkonsentrasi pada node target yang sama
    const targetClicks = this.clickHistory.filter(
      (entry) => entry.target === target || entry.target.contains(target)
    );

    if (targetClicks.length >= this.thresholdClicks) {
      const firstClick = targetClicks[0];
      const lastClick = targetClicks[targetClicks.length - 1];

      this.callback({
        targetSelector: this.getElementSelector(target),
        clickCount: targetClicks.length,
        timeSpanMs: Math.round(lastClick.time - firstClick.time),
        timestamp: Date.now(),
      });

      // Bersihkan antrian untuk mencegah trigger berulang kali pada event yang sama
      this.clickHistory = [];
    }
  };

  private getElementSelector(el: HTMLElement): string {
    if (el.id) return `#${el.id}`;
    if (el.dataset.testid) return `[data-testid="${el.dataset.testid}"]`;
    return `${el.tagName.toLowerCase()}${el.className ? '.' + el.className.split(' ').join('.') : ''}`;
  }

  public destroy(): void {
    window.removeEventListener('pointerdown', this.handlePointerDown, {
      capture: true,
    });
    this.clickHistory = [];
  }
}

// Inisialisasi penggunaan:
const detector = new RageClickDetector((metric) => {
  console.warn('[UX Friction Metric] Rage Click Terdeteksi:', metric);
});
```

---

### 8. Code Implementation: Production-Grade Pattern

Arsitektur produksi berikut mengintegrasikan Finite State Machine (FSM) untuk mitigasi *Gulf of Execution/Evaluation*, mekanisme *Optimistic UI*, dan instrumen telemetri INP (*Interaction to Next Paint*) dengan penanganan memori aman (*buffer flushing* via `navigator.sendBeacon`).

```typescript
// UxEngine.ts

export type UIState = 'IDLE' | 'PENDING' | 'SUCCESS' | 'ERROR';

export interface InteractionMetadata {
  id: string;
  name: string;
  startTime: number;
  duration?: number;
}

export interface StateMachineContext<T> {
  data: T | null;
  error: Error | null;
}

export type StateSubscriber<T> = (state: UIState, context: StateMachineContext<T>) => void;

/**
 * Robust UI Controller mengimplementasikan Finite State Machine
 * dengan penanganan Optimistic Execution dan Telemetry Profiling.
 */
export class ResilientUIController<T> {
  private state: UIState = 'IDLE';
  private context: StateMachineContext<T> = { data: null, error: null };
  private subscribers: Set<StateSubscriber<T>> = new Set();
  private activeInteractions: Map<string, InteractionMetadata> = new Map();

  constructor(private readonly componentId: string) {}

  public subscribe(subscriber: StateSubscriber<T>): () => void {
    this.subscribers.add(subscriber);
    subscriber(this.state, this.context);
    return () => this.subscribers.delete(subscriber);
  }

  private transition(nextState: UIState, contextUpdate: Partial<StateMachineContext<T>> = {}): void {
    this.state = nextState;
    this.context = { ...this.context, ...contextUpdate };
    for (const sub of this.subscribers) {
      sub(this.state, this.context);
    }
  }

  /**
   * Menjalankan mutasi dengan pendekatan Optimistic UI dan instrumentasi INP
   */
  public async executeOptimisticAction(
    actionName: string,
    optimisticData: T,
    asyncOperation: () => Promise<T>,
    rollbackData: T | null
  ): Promise<void> {
    const interactionId = `${this.componentId}:${actionName}:${crypto.randomUUID()}`;
    const startTime = performance.now();

    this.activeInteractions.set(interactionId, {
      id: interactionId,
      name: actionName,
      startTime,
    });

    // 1. Fase Optimis (Doherty Threshold Mitigation: UI diperbarui seketika)
    this.transition('PENDING', { data: optimisticData, error: null });

    // Ukur kapan frame render pertama dieksekusi setelah aksi
    requestAnimationFrame(() => {
      const renderPaintTime = performance.now();
      const visualFeedbackLatency = renderPaintTime - startTime;
      
      if (visualFeedbackLatency > 100) {
        this.logUXMetric('POOR_VISUAL_FEEDBACK_LATENCY', {
          interactionId,
          latencyMs: visualFeedbackLatency,
        });
      }
    });

    try {
      // 2. Operasi Asinkron / Jaringan Riil
      const serverResult = await asyncOperation();
      
      // 3. Rekonsiliasi Sukses
      this.transition('SUCCESS', { data: serverResult, error: null });
      this.finalizeMetric(interactionId, 'SUCCESS');
    } catch (err) {
      // 4. Rollback State jika Terjadi Kegagalan Jaringan/Server
      const error = err instanceof Error ? err : new Error(String(err));
      this.transition('ERROR', { data: rollbackData, error });
      this.finalizeMetric(interactionId, 'FAILURE');
    }
  }

  private finalizeMetric(interactionId: string, status: 'SUCCESS' | 'FAILURE'): void {
    const interaction = this.activeInteractions.get(interactionId);
    if (!interaction) return;

    const totalDuration = performance.now() - interaction.startTime;
    this.activeInteractions.delete(interactionId);

    this.logUXMetric('INTERACTION_COMPLETION', {
      interactionId,
      name: interaction.name,
      durationMs: totalDuration,
      status,
    });
  }

  private logUXMetric(eventType: string, payload: Record<string, unknown>): void {
    const telemetryEvent = {
      componentId: this.componentId,
      eventType,
      payload,
      timestamp: Date.now(),
    };

    const serialized = JSON.stringify(telemetryEvent);

    // Menggunakan sendBeacon agar transmisi metrik tidak menghambat alur rendering antarmuka
    if (navigator.sendBeacon) {
      const blob = new Blob([serialized], { type: 'application/json' });
      navigator.sendBeacon('/api/v1/ux-telemetry', blob);
    } else {
      fetch('/api/v1/ux-telemetry', {
        method: 'POST',
        body: serialized,
        headers: { 'Content-Type': 'application/json' },
        keepalive: true,
      }).catch((error) => {
        console.error('Failed to send telemetry asynchronously', error);
      });
    }
  }
}
```

---

### 9. Real-World Failure Modes & Debugging

| Kegagalan (*Failure Mode*) | Akar Masalah (*Root Cause*) | Metode Deteksi | Remediasi Arsitektur |
| :--- | :--- | :--- | :--- |
| **Phantom Submission** (Order dobel / Duplikasi data) | Tombol tidak memiliki *idempotency lock* atau FSM state protection; UI lambat merespons klik pertama. | Analisis log backend untuk *payload* identik berurutan dalam rentang $<2\text{ s}$; Metrik *Rage Click* tinggi pada tombol konfirmasi. | Implementasikan FSM: Kunci state menjadi `PENDING` secara sinkron sebelum menjalankan promise; terapkan *Idempotency Keys* pada level HTTP header. |
| **Cognitive Disorientation** (Pengguna bingung posisi/status) | State error global menghapus seluruh form input pengguna (*destructive failure*). | Deteksi *Session Drop-off* tinggi setelah visualisasi form error; Telemetri *Form Abandonment Rate*. | Pertahankan *dirty input state* lokal pengguna; gunakan *inline contextual error messaging* yang menunjuk persis atribut yang salah. |
| **Layout Thrashing / CLS Spikes** | Gambar dinamis, banner iklan, atau skeleton loader dirender tanpa menentukan atribut `aspect-ratio` atau dimensi statis. | Metrik PerformanceObserver CLS $> 0.1$; rekaman visual session replay (*jumping content*). | Reservasikan layout box menggunakan CSS `contain: layout size` dan definisikan `aspect-ratio` eksplisit sebelum konten asinkron dimuat. |
| **Unresponsive UI Thread** | Parsing payload JSON ukuran besar ($> 5\text{ MB}$) atau filtering data langsung di main thread saat pengguna mengetik. | Profiler DevTools menunjukkan *Long Tasks* ($> 50\text{ ms}$); metrik INP melampaui $200\text{ ms}$ pada event input. | Pindahkan proses komputasi array/JSON berat ke **Web Worker**; implementasikan teknik *concurrency* / *virtualized list* rendering. |

---

### 10. Performance Characteristics

```
        Main Thread Execution Timeline (Doherty Compliance)
0ms       16ms                     100ms                  400ms
├──────────┼────────────────────────┼──────────────────────┼─────────────►
│[Input]   │[Frame 1: Paint]        │[Max Visual Feedback] │[Max Background Sync]
│Hit-test  │Optimistic State Visual │Micro-animations      │Network completion /
│FSM Lock  │Skeleton Activated      │Progress indicators   │Graceful degradation
└──────────┴────────────────────────┴──────────────────────┴─────────────►
  Target:    Target: Immediate        Target: Keep Context   Target: Doherty Threshold
  < 8ms      < 16ms (60 FPS)          < 100ms                < 400ms
```

- **Alokasi Memori**: Modul instrumentasi UX telemetri wajib beroperasi dengan alokasi memori berkarakteristik $O(1)$ amortized. Struktur *sliding window buffer* harus menggunakan ukuran statis (misalnya batas array buffer: 50 metrik) untuk mencegah kebocoran memori (*memory leak*) pada aplikasi SPA yang berjalan berhari-hari.
- **Overhead CPU**: Tracking interaksi pengguna (misal: *event capture*) harus pasif (`{ passive: true }`) untuk menjamin compositor thread browser tidak terhambat (*scroll-jank prevention*).
- **Network Ingestion Cost**: Telemetri tidak boleh menggunakan pemanggilan `fetch` biasa pada alur kritis. Gunakan `navigator.sendBeacon` yang mengeksekusi pengiriman data secara asinkron di level kernel/browser process tanpa menunda *unload* halaman atau memotong bandwidth rendering UI.

---

### 11. Security & Edge Case Matrix

| Edge Case / Skenario Keamanan | Tingkat Keparahan | Vektor Risiko / Dampak | Pola Mitigasi (*Mitigation Pattern*) |
| :--- | :--- | :--- | :--- |
| **Telemetry PII Leakage** | Critical | Collector telemetri merekam input keyboard atau teks DOM yang memuat kata sandi, NIK, atau kartu kredit pengguna. | Masking otomatis pada tingkat collector: Abaikan semua elemen bertipe input `password`, textarea, atau elemen yang memiliki flag `data-private="true"`. |
| **Clickjacking via CSS Injection** | High | Elemen antarmuka transparan (*invisible iframe*) melapisi tombol sah aplikasi untuk membajak klik pengguna. | Konfigurasikan header `Content-Security-Policy: frame-ancestors 'self'` dan gunakan validasi `event.isTrusted === true`. |
| **Rapid Fire Double Input** (Bimodal click/tap) | Medium | Perangkat layar sentuh hibrida mengirimkan event `touchstart` diikuti `mousedown`, memicu mutasi ganda. | Gunakan standar W3C **Pointer Events** (`pointerdown`) secara universal, jangan campur-adukkan `mouse*` dan `touch*` handlers. |
| **Offline Optimistic State Divergence** | High | Pengguna melakukan aksi saat koneksi mati; UI menampilkan status 'Sukses', namun data tidak pernah sampai ke server. | Berikan visualisasi status *Sync Pending / Offline Mode*; simpan mutasi ke dalam IndexedDB dengan antrean rekonsiliasi berbasis *Exponential Backoff*. |

---

### 12. State Machine / Lifecycle Diagram

Diagram status berikut mengatur siklus hidup komponen antarmuka yang tahan banting (*resilient UI component*), memastikan tidak adanya kondisi ambiguitas (*Gulf of Evaluation*):

```
                       ┌────────────────────────┐
                       │          IDLE          │◄─────────────────────────────┐
                       └────────────────────────┘                              │
                                   │                                           │
                                   │ USER_SUBMIT (Validasi Input Lolos)        │
                                   ▼                                           │
                       ┌────────────────────────┐                              │
                       │        PENDING         │                              │
                       │ (Optimistic Render ON) │                              │
                       │ (Interaction Locked)   │                              │
                       └────────────────────────┘                              │
                                   │                                           │
                    ┌──────────────┴──────────────┐                            │
                    │                             │                            │
      ASYNC_RESOLVE │               ASYNC_REJECT  │                            │
                    ▼                             ▼                            │
      ┌────────────────────────┐    ┌────────────────────────┐                 │
      │        SUCCESS         │    │         ERROR          │                 │
      │ (Display Confirmation) │    │ (Rollback Optimistic)  │                 │
      │ (Acknowledge Telemetry)│    │ (Inline Alert Rendered)│                 │
      └────────────────────────┘    └────────────────────────┘                 │
                    │                             │                            │
                    │ TIMEOUT (Auto-reset)        │ RETRY / DISMISS            │
                    └─────────────────────────────┴────────────────────────────┘
```

---

### 13. Architectural Trade-offs

```
Optimistic UI Architecture
├── Pros:
│   ├── Persepsi latensi = 0ms (Doherty Threshold terpenuhi secara optimal).
│   └── User engagement dan konversi transaksi meningkat secara signifikan.
└── Cons / Trade-offs:
    ├── Kompleksitas kode meningkat (perlu logika rollback dan state synchronization).
    └── Berisiko menimbulkan kebingungan jika aksi gagal setelah pengguna berpindah halaman.

Pessimistic UI Architecture (Traditional Blocking Spinners)
├── Pros:
│   ├── Menjamin konsistensi data 100% antara layar dan basis data.
│   └── Logika kode sederhana; minim kemungkinan state divergence.
└── Cons / Trade-offs:
    ├── Beban kognitif tinggi: Pengguna terhambat oleh loader terus-menerus.
    └── Rawan memicu rage clicks jika latency jaringan berfluktuasi (> 1 detik).
```

*Panduan Keputusan Arsitek*: Gunakan **Optimistic UI** untuk tindakan idempotent dengan probabilitas kegagalan rendah (misal: "Like", "Bookmark", "Archiving Message"). Gunakan **Pessimistic UI** dengan status indikator progres eksplisit untuk tindakan non-idempotent bernilai tinggi dengan probabilitas kegagalan kompleks (misal: "Transfer Dana", "Penerbitan Sertifikat Kriptografi", "Deploy Cluster Cloud").

---

### 14. Anti-Patterns & Code Smells

#### Anti-Pattern: Primitive Loading State & Unlocked Submission
Menggunakan representasi status boolean primitif (`isLoading`) yang diatur secara manual di berbagai callback menyebabkan *race condition* dan celah waktu di mana klik ganda dapat lolos.

##### Bad Code (Smell):
```typescript
// ANTI-PATTERN: State tidak deterministik, rawan race conditions dan double submission
function SubmitButton() {
  let isLoading = false;

  async function handleClick() {
    isLoading = true; // Tidak memblokir thread, klik cepat berikutnya tetap dapat lolos
    updateSpinner(true);

    try {
      const response = await fetch('/api/pay', { method: 'POST' });
      const data = await response.json();
      showSuccess(data);
    } catch (err) {
      showError(err);
    } finally {
      isLoading = false;
      updateSpinner(false);
    }
  }

  document.getElementById('btn')?.addEventListener('click', handleClick);
}
```

##### Refactored Code (Production Pattern):
```typescript
// CLEAN PATTERN: FSM-driven execution dengan Idempotency Token dan Event Freezing
type ButtonActionState = 'IDLE' | 'PROCESSING' | 'COMPLETED';

class SecureSubmitController {
  private currentState: ButtonActionState = 'IDLE';
  private abortController: AbortController | null = null;

  constructor(
    private readonly buttonElement: HTMLButtonElement,
    private readonly endpoint: string
  ) {
    this.buttonElement.addEventListener('click', this.handleAction);
  }

  private handleAction = async (): Promise<void> => {
    // Deterministic Guard: Tolak secara mutlak jika transisi belum kembali ke IDLE
    if (this.currentState !== 'IDLE') {
      console.warn('[FSM] Action rejected: current state is', this.currentState);
      return;
    }

    this.currentState = 'PROCESSING';
    this.buttonElement.disabled = true; // Nonaktifkan affordance pada DOM
    this.buttonElement.setAttribute('aria-busy', 'true');

    this.abortController = new AbortController();
    const idempotencyKey = crypto.randomUUID();

    try {
      const response = await fetch(this.endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Idempotency-Key': idempotencyKey,
        },
        signal: this.abortController.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP Error: ${response.status}`);
      }

      this.currentState = 'COMPLETED';
      this.buttonElement.setAttribute('aria-busy', 'false');
      this.renderFeedback('Transaksi Berhasil');
    } catch (error) {
      this.currentState = 'IDLE'; // Reset state agar pengguna bisa mencoba lagi secara valid
      this.buttonElement.disabled = false;
      this.buttonElement.setAttribute('aria-busy', 'false');
      this.renderFeedback('Transaksi Gagal, Silakan Coba Lagi');
    }
  };

  private renderFeedback(msg: string): void {
    const feedbackBox = document.getElementById('feedback-region');
    if (feedbackBox) feedbackBox.textContent = msg;
  }
}
```

---

### 15. Testing & Verification Suite

Pengujian UX engineering berfokus pada verifikasi determinisme antarmuka, penanganan error transisi, dan validasi metrik perilaku menggunakan Vitest/Jest dengan JSDOM:

```typescript
// UxEngine.spec.ts
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ResilientUIController } from './UxEngine';

describe('ResilientUIController UX State Mechanics', () => {
  let controller: ResilientUIController<string>;

  beforeEach(() => {
    controller = new ResilientUIController<string>('checkout-flow');
    vi.clearAllMocks();
  });

  it('harus memancarkan status PENDING secara instan untuk memenuhi Doherty Threshold', async () => {
    const states: string[] = [];
    controller.subscribe((state) => states.push(state));

    const mockAsync = () =>
      new Promise<string>((resolve) => setTimeout(() => resolve('Server Done'), 50));

    const promise = controller.executeOptimisticAction(
      'updateItem',
      'Optimistic Value',
      mockAsync,
      'Initial Value'
    );

    // Verifikasi bahwa status PENDING langsung di-emit tanpa menunggu network resolution
    expect(states).toContain('PENDING');
    await promise;
    expect(states).toContain('SUCCESS');
  });

  it('harus melakukan rollback context data ke fallback value ketika server call gagal', async () => {
    const contexts: Array<string | null> = [];
    controller.subscribe((_, ctx) => contexts.push(ctx.data));

    const mockFailingAsync = () =>
      new Promise<string>((_, reject) =>
        setTimeout(() => reject(new Error('Network Drop')), 20)
      );

    await controller.executeOptimisticAction(
      'failingAction',
      'Optimistic Candidate',
      mockFailingAsync,
      'Safe Baseline'
    );

    // Urutan konteks: Initial (null) -> Optimistic Candidate -> Safe Baseline (Rollback)
    expect(contexts).toEqual([null, 'Optimistic Candidate', 'Safe Baseline']);
  });

  it('tidak boleh mengalami uncaught exceptions saat dispatching telemetri tanpa koneksi beacon', async () => {
    // Simulasikan lingkungan di mana navigator.sendBeacon bernilai undefined
    const originalBeacon = navigator.sendBeacon;
    // @ts-expect-error test teardown override
    navigator.sendBeacon = undefined;

    const mockFetch = vi.fn().mockImplementation(() => Promise.reject('Offline'));
    global.fetch = mockFetch;

    const mockSuccessAsync = () => Promise.resolve('Success');

    await expect(
      controller.executeOptimisticAction('testAction', 'val', mockSuccessAsync, null)
    ).resolves.not.toThrow();

    navigator.sendBeacon = originalBeacon;
  });
});
```

---

### 16. Production Readiness Checklist

- [ ] **Ergonomi Hit Target**: Semua elemen interaktif memiliki area klik minimum $\ge 48 \times 48\text{ CSS pixels}$ dengan padding isolasi visual yang cukup.
- [ ] **State Machine Determinism**: Tidak ada status komponen yang diatur via manipulasi boolean bertumpuk (`isLoading && !isError && isSuccess`); seluruh alur navigasi krusial dikontrol oleh FSM.
- [ ] **Telemetry Masking & Compliance**: Pipeline telemetri UX telah dipasangi filter PII (Personally Identifiable Information) otomatis guna mencegah kebocoran data sensitif ke analytical store.
- [ ] **Interaction Latency (INP) Budget**: Ambang batas latensi frame pertama antarmuka berada di bawah $100\text{ ms}$ (Good rating: $\le 200\text{ ms}$).
- [ ] **Visual Layout Stability**: Seluruh kontainer gambar, iframe, dan komponen asinkron telah mengonfigurasi `aspect-ratio` atau ukuran minimum eksplisit untuk menjamin CLS $< 0.1$.
- [ ] **Accessible Feedback Announcers**: Area perubahan visual dinamis (*dynamic content shifts*) telah terhubung dengan atribut `aria-live="polite"` atau `role="alert"` untuk assistive technologies.

---

### 17. Operational Runbook

#### Skenario 1: Lonjakan Anomali Rage Clicks pada Halaman Checkout
1. **Trigger Alert**: Alert Prometheus/Datadog terpicu: `Rate(ux_rage_clicks_total[5m]) > 50 events/min`.
2. **Diagnostik**:
   - Query trace log analitik UX untuk mengisolasi target selector:
     ```sql
     SELECT target_selector, COUNT(*) as click_volume 
     FROM ux_telemetry_events 
     WHERE event_type = 'RAGE_CLICK' AND created_at >= NOW() - INTERVAL 15 MINUTE 
     GROUP BY target_selector ORDER BY click_volume DESC LIMIT 5;
     ```
   - Verifikasi status backend endpoint yang terhubung dengan target selector tersebut (periksa apakah terjadi peningkatan kode status HTTP 504 / 429).
3. **Mitigasi**:
   - Jika tombol membeku akibat deadlock pada *third-party payment gateway script*, aktifkan *kill-switch* melalui Feature Flag untuk mengalihkan rute checkout ke fallback gateway sekunder.
   - Deploy emergency fix untuk mengaktifkan feedback visual seketika (*instant visual lock*) saat tombol dipicu pertama kali.

---

### 18. Migration / Evolution Path

Ketika bertransisi dari antarmuka monolitik klasik berbasis *pessimistic server-side rendering* ke arsitektur *event-driven resilient UX*:

```
[Phase 1: Instrumentation Only]
  └─ Pasang telemetry tracking (Rage Click, Dead Click, INP) pada antarmuka eksisting tanpa memodifikasi UX flow.
  └─ Kumpulkan baseline metrik friksi selama minimal 1 siklus rilis (2 minggu).

[Phase 2: FSM Decoupling]
  └─ Isolasi alur transaksi kritikal (misal: Form Registrasi, Cart Checkout).
  └─ Ganti pengelolaan boolean state (`loading=true`) dengan Finite State Controller terstruktur.

[Phase 3: Progressive Optimistic UI]
  └─ Terapkan Optimistic Updates secara terbatas pada mutasi bervolume tinggi dengan risiko rendah.
  └─ Bangun layer kompensasi error (Rollback Controller & Toast Notification).

[Phase 4: Full Resiliency & Telemetry Auto-Tuning]
  └─ Integrasikan deteksi network throttling (Network Information API) untuk secara dinamis
     beralih antara Optimistic UI (kondisi koneksi stabil) dan Pessimistic UI (kondisi 2G/Save-Data).
```

---

### 19. Best Practices & Pro Tips

- **Affordance Consistency**: Jangan pernah mengubah kursor mouse menjadi `cursor: pointer` pada elemen yang bukan merupakan tautan semantik (`<a>`) atau tombol interaktif (`<button>`). Hal ini mencegah terbentuknya *Dead Clicks* akibat ekspektasi navigasi palsu dari model mental pengguna.
- **Micro-Task Batching**: Hindari memanggil tracking telemetri secara sinkron di tengah handler animasi. Bungkus pemanggilan profiling dalam `requestIdleCallback()` atau `queueMicrotask()` agar browser dapat memprioritaskan kalkulasi layout dan rendering frame.
- **Skeletal State Hierarchy**: Jangan menampilkan *indeterminate full-screen spinner*. Gunakan *skeleton loaders* yang secara struktural merefleksikan geometri konten aktual yang akan dimuat. Hal ini mengurangi perceived wait time (*waktu tunggu yang dirasakan*) pengguna hingga 30% berdasarkan kaidah psikologi waktu kognitif.

---

### 20. Summary & Next Steps

Pada modul ini, kita telah membedah dasar-dasar arsitektur UX dari kacamata rekayasa perangkat lunak:
- Antarmuka digital berfungsi menjembatani kesenjangan persepsi antara model mental manusia dan model status sistem (*Norman's Gulfs*).
- Hukum Fitts, Hick-Hyman, dan Doherty Threshold bukan sekadar teori visual, melainkan parameter desain sistem front-end yang mengontrol ukuran elemen, branching antarmuka, dan latensi feedback DOM.
- Keandalan antarmuka dijamin dengan mengabstraksikan mutasi UI ke dalam Finite State Machine (FSM), mencegah status ambigu, dan mengukur friksi interaksi secara kuantitatif melalui telemetri (Rage Clicks, INP).

**Langkah Selanjutnya**:
Pada **Bab 01 Module 02**, kita akan melangkah lebih dalam ke materi **"Advanced Information Architecture & Layout Algorithms"**: mempelajari dekonstruksi pohon informasi, arsitektur *search-first navigation*, optimasi CSS Grid/Subgrid layout rendering pipelines, dan perancangan sistem navigasi multi-platform berskala masif.