# SEKSI 01 — IDENTITAS MODUL

*   **Jalur Pembelajaran:** Frontend & Mobile Engineering / Product Design Architecture
*   **Kategori:** 03-Frontend-and-Mobile
*   **Bab:** 04 — Rapid Prototyping, Usability Validation, and Design Systems
*   **Modul:** 01 — Wireframing, Low-Fi Testing & Desain Eksperimental
*   **Tingkat Kesulitan:** Advanced / Staff Level
*   **Prasyarat Konseptual:** Pemahaman solid siklus hidup rekayasa UI (React/React Native/Web Components), instrumentasi metrik kognitif (System Usability Scale, Time on Task, Task Success Rate), dan prinsip dasar *heuristic evaluation* (Nielsen-Norman).

---

# SEKSI 02 — LEARNING OBJECTIVES

Pada akhir modul ini, peserta didik memiliki kapabilitas terukur untuk:
1.  **Merancang dan Mengabstraksikan Skema Wireframe Arsitektural:** Membangun *low-fidelity state diagrams* dan antarmuka terstruktur tanpa bias estetika visual menggunakan prinsip desain berbasis token dan slot-structural semantics.
2.  **Mengeksekusi Metodologi Pengujian Low-Fidelity Skala Produksi:** Mengoperasikan pengujian fungsionalitas dengan artefak berresolusi rendah guna mengidentifikasi *gulf of execution* dan *gulf of evaluation* lebih awal sebelum alokasi sumber daya teknis intensif.
3.  **Membangun Engine Desain Eksperimental (Multi-Arm Hypothesis Prototyping):** Mengimplementasikan arsitektur kode frontend yang mampu mengisolasi varian eksperimental secara deterministik menggunakan *split-testing logic*, *context routing*, dan penanganan *layout shifts*.
4.  **Mengotomatisasi Metrik Observabilitas Interaksi Pengguna:** Memasang instrumen telemetri kustom (*event streaming*, *dwell time*, *misclick heatmapping logic*) pada artefak low-fi untuk menarik kesimpulan kuantitatif dan kualitatif berbasis data empiris.

---

# SEKSI 03 — MINDSET & MENTAL MODEL

### Mental Model 1: The Blueprint vs. Interior Decorator Paradigm
Rekayasa produk sering kali terjebak dalam *aesthetic-usability effect*, di mana stakeholder mengasumsikan antarmuka yang indah secara visual pasti berfungsi optimal secara struktural. Wireframing dan low-fi testing adalah fase pembuatan cetak biru (*blueprint*) struktural bangunan, bukan penentuan warna cat dinding atau material marmer. Jika sirkulasi fondasi cacat, dekorasi visual beresolusi tinggi hanya memperparah biaya refactoring teknis (*technical debt*) di masa depan.

### Mental Model 2: Cheap Failure as an Optimization Function
Biaya iterasi kode atau desain berbanding lurus secara eksponensial dengan tingkat fidelitasnya:

$$\text{Cost of Change} = k \cdot e^{(\text{Fidelity Level})}$$

Pengujian low-fi bertujuan mereduksi biaya kegagalan (*cost of failure*) mendekati nol. Hipotesis arsitektural antarmuka harus diuji pada level representasi paling murah yang tetap mempertahankan validitas ekologis fungsi pengujian.

```
+-------------------------------------------------------------------------+
|                    THE FIDELITY ESCALATION TAX                           |
|                                                                         |
|  High-Fi (Pixel-Perfect Code) : $$$$$$$$$$ [Sangat Mahal untuk Diubah]  |
|  Interactive Component Mockup : $$$$$      [Moderat]                    |
|  Code-based Low-Fi Wireframe  : $$         [Sangat Murah]               |
|  Paper / Static SVG Sketch    : $          [Dapat Dibuang Kapan Saja]   |
+-------------------------------------------------------------------------+
```

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Di bawah ini adalah siklus interaksi loop tertutup (*closed-loop interaction cycle*) dari fase spesifikasi wireframe, deployment eksperimental multi-varian, hingga ingestion telemetri untuk evaluasi hipotesis.

```
+---------------------------------------------------------------------------------------+
|                 ARSITEKTUR SIKLUS DESAIN EKSPERIMENTAL & LOW-FI TESTING                |
+---------------------------------------------------------------------------------------+

 [ PRD & Task Flow Specs ]
            |
            v
 +----------------------+
 | Low-Fi Structural    |
 | Wireframing (Code)   |-----> [ Eliminasi Bias Visual: No Colors, Monospace, Greyscale ]
 +----------------------+
            |
            v
 +-----------------------------------------------------------------------------------+
 | Dynamic Experimentation Engine (Runtime Variant Orchestrator)                     |
 |                                                                                   |
 |  +---------------------+   Bucketing Engine   +--------------------------------+  |
 |  | Context / User Hash |--------------------->| Allocator (Deterministic Murmur3|  |
 |  +---------------------+                      +--------------------------------+  |
 |                                                              |                     |
 |                               +------------------------------+                     |
 |                               |                              |                     |
 |                               v                              v                     |
 |                 +---------------------------+  +---------------------------+       |
 |                 | Variant A: Sequential Flow|  | Variant B: Chunked Stepper|       |
 |                 | (Semantic Wireframe DOM)  |  | (Semantic Wireframe DOM)  |       |
 |                 +---------------------------+  +---------------------------+       |
 +-----------------------------------------------------------------------------------+
            |                                                   |
            +-------------------------+-------------------------+
                                      |
                                      v
                 +-----------------------------------------+
                 | Observability & Telemetry Interceptor   |
                 | - Time-to-First-Action (TTFA)           |
                 | - Misclick / Dead-Click Tracker         |
                 | - Task Completion Delta Engine          |
                 +-----------------------------------------+
                                      |
                                      v
                 +-----------------------------------------+
                 | Validation Gate (Bayesian/Z-Test Engine)|
                 |                                         |
                 | Success?  ==> Lanjut ke High-Fi Token   |
                 | Failure?  ==> Mutasi Hierarki Wireframe |
                 +-----------------------------------------+
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. The Wireframe Abstraction Layer (WAL)
Wireframe modern bukan sekadar gambar sketsa; di tim rekayasa tingkat lanjut, wireframe dapat direpresentasikan sebagai komponen fungsional yang menggunakan *structural constraint tokens*. 
*   **Box Sizing & Layout Flow:** Menggunakan flexbox/grid primitif yang memproyeksikan batas wilayah tanpa detail estetika.
*   **Content Masking:** Menggunakan *synthesized skeleton text* atau *redacted blocks* untuk memaksa penguji fokus pada navigasi dan hierarki alur daripada teks literal.

### 2. Low-Fi Testing Mechanics
*   **Task Completion Path Verification:** Menghitung deviasi langkah aktual pengguna relatif terhadap *Critical Path Method (CPM)* ideal.
*   **Cognitive Load Indicators:** Mengukur *hesitation time*—durasi antara munculnya layar dan event `pointerdown` pertama. Jika ambang batas terlampaui (misal $> 2.500\text{ ms}$ pada antarmuka sederhana), terjadi *visual search latency* berlebih.

### 3. Experimental Core Subsystem
*   **Deterministic Assignment:** Membagi pengguna/penguji secara konsisten ke dalam cabang eksperimen menggunakan fungsi hashing (`MurmurHash3` atau hash modular pada entitas identitas sesi).
*   **Layout Shift Prevention:** Pengujian eksperimen berbasis wireframe harus memiliki *zero-layout shift (CLS = 0)* pada saat pengalihan varian untuk mencegah bias respons motorik penguji.

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Hukum Fitts dan Prediksi Waktu Interaksi
Keberhasilan wireframe sangat terikat pada Hukum Fitts untuk efisiensi motorik:

$$MT = a + b \cdot \log_2 \left( \frac{2D}{W} \right)$$

Di mana:
*   $MT$ = *Movement Time* (Waktu yang dibutuhkan untuk mencapai target interaktif).
*   $a, b$ = Konstanta empiris regresi.
*   $D$ = Jarak (*Distance*) ke pusat target interaksi.
*   $W$ = Lebar (*Width*) target sepanjang sumbu gerak.

Dalam pengujian low-fidelity, desainer dan engineer mengevaluasi rasio $\frac{D}{W}$. Jika low-fi testing menunjukkan dispersi klik tinggi di luar *bounding box* target, $W$ dinilai terlalu kecil atau $D$ terlalu besar dari target logis sebelumnya, tanpa terpengaruh oleh warna atau animasi tombol.

### Hukum Hick-Hyman dan Kompleksitas Pilihan
Waktu reaksi kognitif untuk memilih di antara $n$ alternatif:

$$T = b \cdot \log_2(n + 1)$$

Desain eksperimental pada tahap wireframe berfokus pada reduksi parameter $n$ melalui pemecahan hierarki visual (*information architecture chunking*). Melalui varian A/B struktural, kita dapat secara langsung memvalidasi apakah penataan mendatar (*flat layout* dengan $n$ tinggi) berkinerja lebih buruk dibandingkan arsitektur bertingkat (*nested stepper* dengan $n$ rendah per langkah).

### Metrik Evaluasi Kuantitatif Low-Fi
1.  **Single Ease Question (SEQ):** Pertanyaan pasca-tugas 7-titik untuk menilai kemudahan subjektif.
2.  **Lostness Metric ($L$):** Metrik untuk mengukur inefisiensi navigasi pengguna:

    $$L = \sqrt{ \left( \frac{N}{S} - 1 \right)^2 + \left( \frac{R}{N} - 1 \right)^2 }$$

    Di mana:
    *   $R$ = Jumlah tugas minimum yang optimal.
    *   $S$ = Jumlah total halaman/state unik yang dikunjungi.
    *   $N$ = Jumlah total kunjungan halaman/state.
    *   Jika $L > 0.4$, struktur navigasi dinilai membingungkan; jika $L < 0.2$, arsitektur wireframe dinyatakan efisien.

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi sistem wireframing fungsional berbasis TypeScript dan React yang menerapkan styling primitif berkecepatan tinggi, bebas bias visual, dan memiliki *event telemetry interceptor* terintegrasi.

```tsx
// src/components/wireframe/WireframePrimitives.tsx
import React, { createContext, useContext, useEffect, useRef } from 'react';

// -------------------------------------------------------------
// TELEMETRY CONTEXT & CONTRACTS
// -------------------------------------------------------------
export interface TelemetryPayload {
  elementId: string;
  eventType: 'click' | 'hesitation' | 'dead_click';
  timestamp: number;
  durationMs?: number;
  metadata?: Record<string, unknown>;
}

interface WireframeContextValue {
  emitMetric: (payload: TelemetryPayload) => void;
  variantId: string;
}

const WireframeContext = createContext<WireframeContextValue | null>(null);

export const WireframeProvider: React.FC<{
  variantId: string;
  onDispatchMetric: (payload: TelemetryPayload) => void;
  children: React.ReactNode;
}> = ({ variantId, onDispatchMetric, children }) => {
  return (
    <WireframeContext.Provider value={{ emitMetric: onDispatchMetric, variantId }}>
      <div style={{ fontFamily: 'monospace', backgroundColor: '#F4F4F4', minHeight: '100vh', padding: 24 }}>
        {children}
      </div>
    </WireframeContext.Provider>
  );
};

// -------------------------------------------------------------
// STRUCTURAL WIREFRAME COMPONENTS (LOW-FI PRIMITIVES)
// -------------------------------------------------------------
interface WireframeBoxProps {
  id: string;
  width?: string | number;
  height?: string | number;
  children?: React.ReactNode;
  isInteractive?: boolean;
  onClick?: () => void;
  role?: string;
}

export const WireframeBox: React.FC<WireframeBoxProps> = ({
  id,
  width = '100%',
  height = 'auto',
  children,
  isInteractive = false,
  onClick,
  role = 'region',
}) => {
  const context = useContext(WireframeContext);
  const mountTimeRef = useRef<number>(performance.now());
  const hasInteractedRef = useRef<boolean>(false);

  useEffect(() => {
    // Deteksi Hesitation Time jika box merupakan elemen interaktif primer
    if (isInteractive) {
      const timer = setTimeout(() => {
        if (!hasInteractedRef.current && context) {
          context.emitMetric({
            elementId: id,
            eventType: 'hesitation',
            timestamp: Date.now(),
            durationMs: 3000,
          });
        }
      }, 3000);

      return () => clearTimeout(timer);
    }
  }, [id, isInteractive, context]);

  const handleClick = (e: React.MouseEvent<HTMLDivElement>) => {
    hasInteractedRef.current = true;
    if (context) {
      context.emitMetric({
        elementId: id,
        eventType: isInteractive ? 'click' : 'dead_click',
        timestamp: Date.now(),
        durationMs: performance.now() - mountTimeRef.current,
      });
    }
    if (onClick) onClick();
  };

  const baseStyle: React.CSSProperties = {
    width,
    height,
    border: '2px solid #333333',
    backgroundColor: isInteractive ? '#EAEAEA' : '#FFFFFF',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    position: 'relative',
    boxSizing: 'border-box',
    cursor: isInteractive ? 'pointer' : 'default',
    margin: '8px 0',
    padding: 12,
  };

  return (
    <div
      role={role}
      data-wireframe-id={id}
      style={baseStyle}
      onClick={handleClick}
    >
      <div
        style={{
          position: 'absolute',
          top: 2,
          left: 4,
          fontSize: 9,
          color: '#666',
          textTransform: 'uppercase',
        }}
      >
        [{id}]
      </div>
      {children}
    </div>
  );
};

export const WireframePlaceholderText: React.FC<{ lines?: number; length?: 'short' | 'medium' | 'long' }> = ({
  lines = 1,
  length = 'medium',
}) => {
  const getWidth = () => {
    if (length === 'short') return '35%';
    if (length === 'medium') return '65%';
    return '95%';
  };

  return (
    <div style={{ width: '100%', margin: '4px 0' }}>
      {Array.from({ length: lines }).map((_, idx) => (
        <div
          key={idx}
          style={{
            height: 12,
            backgroundColor: '#888888',
            marginBottom: 4,
            width: idx === lines - 1 ? getWidth() : '100%',
          }}
        />
      ))}
    </div>
  );
};
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

*   **Baris 19-35 (`WireframeContext` & `WireframeProvider`):** Mengisolasi status eksperimen dan fungsi dispatch telemetri dari hierarki view. Menggunakan font `monospace` global dan skema warna netral (`#F4F4F4`) secara terprogram untuk menonaktifkan biasing visual seperti tipografi serif/sans modern dan saturasi warna.
*   **Baris 48-60 (`WireframeBox` Interface & Refs):** Menangkap `mountTimeRef` menggunakan API resolusi tinggi `performance.now()`. Menyimpan status `hasInteractedRef` untuk mengukur latensi reaksi kognitif pengguna terhadap komponen secara independen.
*   **Baris 62-75 (`useEffect` Hesitation Engine):** Menjadwalkan pengiriman telemetri jika elemen target yang dapat diklik (`isInteractive = true`) diabaikan oleh pengguna selama lebih dari 3000 ms. Ini memberikan sinyal kuantitatif adanya kebingungan affordance (*signifier ambiguity*).
*   **Baris 77-88 (`handleClick` Interaction Interceptor):** Membedakan aksi `click` valid pada elemen target dengan aksi `dead_click` jika pengguna memicu event pada container non-interaktif. Metrik *dead click* mengindikasikan bahwa tata letak memproyeksikan ilusi affordance palsu.
*   **Baris 90-103 (`baseStyle` Configuration):** Penegakan token visual low-fi: garis tegas monokrom 2px, padding terstandardisasi, dan visualisasi tag struktural eksplisit `[{id}]` pada Baris 112-120 untuk memastikan korelasi pemetaan 1:1 antara artefak testing dan event log data pipeline.
*   **Baris 127-147 (`WireframePlaceholderText`):** Mencegah fenomena bias *reading comprehension* penguji dengan menggunakan balok geometris solid terukur alih-alih teks *Lorem Ipsum* yang kerap mengalihkan perhatian penguji dari struktur informasi.

---

# SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi: Redesain Alur Checkout FinTech Skala Enterprise
*   **Organisasi:** Platform Pembiayaan B2B Transnasional.
*   **Masalah:** Alur persetujuan transaksi multi-pihak (*Approval Matrix*) mengalami tingkat *drop-off* sebesar 41% pada fase input data parameter finansial. Tim engineering dan produk berselisih mengenai dua paradigma navigasi:
    *   *Hipotesis A:* Model formulir panjang terkonsolidasi satu halaman (*Single-View Accordion*).
    *   *Hipotesis B:* Model tahapan modular berurutan (*Multi-Step Wizard Engine*).
*   **Dilema:** Mengembangkan kedua varian dalam status *high-fidelity* lengkap (terintegrasi API backend, validasi microservice, dan desain grafis adaptif) diprediksi memakan waktu 8 minggu sprint.
*   **Solusi:** Membangun *Low-Fi Experimental Test Harness* langsung di web engine dalam 48 jam kerja menggunakan mock-wiring. Pengguna target (financial controller eksternal) diarahkan pada prototipe berbasis kode low-fi fungsional yang merekam tingkat *lostness*, *hesitation rate*, dan *task completion velocity*.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah arsitektur *A/B Testing Low-Fi Testbed* dengan algoritma penugasan deterministik dan kalkulator metrik *Lostness* secara real-time.

```tsx
// src/experiments/CheckoutFlowExperiment.tsx
import React, { useState, useMemo } from 'react';
import { WireframeProvider, WireframeBox, WireframePlaceholderText, TelemetryPayload } from '../components/wireframe/WireframePrimitives';

// ---------------------------------------------------------------------
// DETERMINISTIC HASH FUNCTION (MURMUR-LIKE SIMPLE HASH)
// ---------------------------------------------------------------------
function hashUserVariant(userId: string): 'variant-a' | 'variant-b' {
  let hash = 0;
  for (let i = 0; i < userId.length; i++) {
    const char = userId.charCodeAt(i);
    hash = (hash << 5) - hash + char;
    hash |= 0; // Convert to 32bit integer
  }
  return Math.abs(hash) % 2 === 0 ? 'variant-a' : 'variant-b';
}

// ---------------------------------------------------------------------
// EXPERIMENTAL LOW-FI VIEW: VARIANT A (SINGLE-PAGE ACCORDION)
// ---------------------------------------------------------------------
const VariantAAccordion: React.FC<{ onComplete: () => void; recordStep: (step: string) => void }> = ({
  onComplete,
  recordStep,
}) => {
  const [openSection, setOpenSection] = useState<number>(1);

  return (
    <div style={{ maxWidth: 600, margin: '0 auto' }}>
      <h3>Struktur Low-Fi Varian A: Accordion Monolitik</h3>
      <WireframeBox
        id="accordion-sec-1"
        isInteractive
        onClick={() => {
          setOpenSection(1);
          recordStep('acc-sec-1');
        }}
      >
        <h4>[Section 1: Data Identitas Perusahaan]</h4>
        {openSection === 1 && (
          <>
            <WireframePlaceholderText lines={2} />
            <WireframeBox id="input-mock-1" height={40}>Input Block Identitas</WireframeBox>
          </>
        )}
      </WireframeBox>

      <WireframeBox
        id="accordion-sec-2"
        isInteractive
        onClick={() => {
          setOpenSection(2);
          recordStep('acc-sec-2');
        }}
      >
        <h4>[Section 2: Parameter Finansial Limit]</h4>
        {openSection === 2 && (
          <>
            <WireframePlaceholderText lines={3} />
            <WireframeBox id="input-mock-2" height={40}>Input Block Finansial</WireframeBox>
          </>
        )}
      </WireframeBox>

      <WireframeBox
        id="btn-complete-a"
        isInteractive
        onClick={() => {
          recordStep('complete');
          onComplete();
        }}
      >
        <strong>EKSEKUSI FINALISASI ORDER</strong>
      </WireframeBox>
    </div>
  );
};

// ---------------------------------------------------------------------
// EXPERIMENTAL LOW-FI VIEW: VARIANT B (STEPPER WIZARD)
// ---------------------------------------------------------------------
const VariantBStepper: React.FC<{ onComplete: () => void; recordStep: (step: string) => void }> = ({
  onComplete,
  recordStep,
}) => {
  const [step, setStep] = useState<number>(1);

  return (
    <div style={{ maxWidth: 600, margin: '0 auto' }}>
      <h3>Struktur Low-Fi Varian B: Multi-Step Sequential</h3>
      <WireframeBox id={`stepper-indicator-${step}`}>
        Indikator Progres Aktif: Tahap {step} dari 2
      </WireframeBox>

      {step === 1 && (
        <WireframeBox id="step-1-container">
          <h4>[Langkah 1: Identitas Perusahaan]</h4>
          <WireframePlaceholderText lines={3} />
          <WireframeBox id="step-1-input" height={40}>Input Field</WireframeBox>
          <WireframeBox
            id="btn-next-step"
            isInteractive
            onClick={() => {
              recordStep('step-2');
              setStep(2);
            }}
          >
            Lanjut ke Tahap 2 -&gt;
          </WireframeBox>
        </WireframeBox>
      )}

      {step === 2 && (
        <WireframeBox id="step-2-container">
          <h4>[Langkah 2: Parameter Finansial Limit]</h4>
          <WireframePlaceholderText lines={2} />
          <WireframeBox id="step-2-input" height={40}>Input Field</WireframeBox>
          <WireframeBox
            id="btn-complete-b"
            isInteractive
            onClick={() => {
              recordStep('complete');
              onComplete();
            }}
          >
            <strong>SELESAIKAN PROSES</strong>
          </WireframeBox>
        </WireframeBox>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------
// HARNESS CONTAINER & TELEMETRY INGESTION ENGINE
// ---------------------------------------------------------------------
export const CheckoutExperimentHarness: React.FC<{ testSessionUserId: string }> = ({ testSessionUserId }) => {
  const variant = useMemo(() => hashUserVariant(testSessionUserId), [testSessionUserId]);
  
  // Metrik Navigasi (Lostness Metric Variables)
  const [visitedNodes, setVisitedNodes] = useState<string[]>([]);
  const [sessionCompleted, setSessionCompleted] = useState<boolean>(false);
  const [telemetryLogs, setTelemetryLogs] = useState<TelemetryPayload[]>([]);

  const optimalSteps = 2; // R (Minimum optimal steps: input-1 -> input-2 -> complete)

  const handleRecordStep = (stepNode: string) => {
    setVisitedNodes((prev) => [...prev, stepNode]);
  };

  const handleTelemetryDispatch = (event: TelemetryPayload) => {
    setTelemetryLogs((prev) => [...prev, event]);
    // Di lingkungan produksi: kirim via navigator.sendBeacon ke event ingestion bus
  };

  const computeLostness = (): number => {
    const N = visitedNodes.length; // Total kunjungan langkah
    const S = new Set(visitedNodes).size; // Total unique state/pages
    const R = optimalSteps;

    if (S === 0 || N === 0) return 0;
    const term1 = Math.pow(N / S - 1, 2);
    const term2 = Math.pow(S / R - 1, 2);
    return Math.sqrt(term1 + term2);
  };

  return (
    <WireframeProvider variantId={variant} onDispatchMetric={handleTelemetryDispatch}>
      <div style={{ borderBottom: '1px solid #999', paddingBottom: 16, marginBottom: 24 }}>
        <h2>Experimental Low-Fi Session Harness</h2>
        <p>User Identifier: <code>{testSessionUserId}</code> | Alokasi Varian: <strong>{variant.toUpperCase()}</strong></p>
      </div>

      {!sessionCompleted ? (
        variant === 'variant-a' ? (
          <VariantAAccordion
            recordStep={handleRecordStep}
            onComplete={() => setSessionCompleted(true)}
          />
        ) : (
          <VariantBStepper
            recordStep={handleRecordStep}
            onComplete={() => setSessionCompleted(true)}
          />
        )
      ) : (
        <WireframeBox id="evaluation-receipt">
          <h3>Eksperimen Berhasil Diselesaikan</h3>
          <p>Kalkulasi Lostness Score: <strong>{computeLostness().toFixed(4)}</strong></p>
          <p>Total Interaksi Terekam: {telemetryLogs.length} events</p>
          <pre style={{ textAlign: 'left', fontSize: 11, background: '#eee', padding: 8, width: '90%' }}>
            {JSON.stringify({ visitedNodes, telemetryLogs }, null, 2)}
          </pre>
        </WireframeBox>
      )}
    </WireframeProvider>
  );
};
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Aspek Arsitektural | Paper Wireframing | Digital Low-Fi (Figma/Sketch) | Code-Based Low-Fi Prototypes |
| :--- | :--- | :--- | :--- |
| **Kecepatan Inisiasi** | **Sangat Tinggi** (< 1 jam) | **Sedang** (1 - 2 hari) | **Rendah - Sedang** (2 - 3 hari) |
| **Presisi Penangkapan Data** | Nol (manual via catatan) | Parsial (Click-map dasar) | **Absolut** (Telemetry, DOM, Timers) |
| **Akurasi Interaksi State** | Rendah (Simulasi verbal) | Moderat (Transisi linear) | **Tinggi** (Kondisional dinamis penuh) |
| **Biaya Buang/Pivot** | **Hampir Nol** | Rendah | Sedang |
| **Bias Estetika Penguji** | Nol | Rendah - Moderat | **Terkontrol Sepenuhnya via CSS System** |
| **Interaksi Keyboard/A11y** | Tidak Dapat Diuji | Tidak Dapat Diuji | **Sepenuhnya Valid & Dapat Diuji** |

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. The "Aesthetic Gap" Misdirection
*   *Failure Mode:* Stakeholder atau subjek pengujian berasumsi prototipe low-fi adalah produk rusak karena ketiadaan grafis/warna dan memberikan feedback yang tidak relevan ("Warnanya membosankan", "Tombol tidak menarik").
*   *Mitigasi:* Berikan *framing script* baku sebelum pengetesan: *"Kami sedang menguji arsitektur struktural dan kejelasan navigasi, bukan estetika grafis. Semua visual sengaja diubah menjadi primitif monokrom."* Terapkan watermark eksplisit `[LOW-FIDELITY STRUCTURAL TEST]` di latar belakang prototipe.

### 2. State Explosion pada Wireframe Berbasis Kode
*   *Failure Mode:* Pembuatan prototipe wireframe berbasis kode tergoda untuk mengimplementasikan *business rules* backend secara mendalam, menyebabkan waktu pengerjaan molor dari tujuan awal.
*   *Mitigasi:* Batasi arsitektur mock pada tingkat *in-memory mutation* lokal. Tolak konektivitas database transaksional riil; gunakan repositori statis tersimulasi (*deterministic mocked delay* maksimal 100 ms).

### 3. Click-Spamming & False Dead-Click Signals
*   *Failure Mode:* Pengguna yang gelisah mengklik container statis secara berulang tanpa niat navigasi, membanjiri metrik *dead-click*.
*   *Mitigasi:* Terapkan algoritma *debouncing* dan *spatial-clustering*: hanya hitung sebagai *dead click* jika klik terisolasi dari klik sebelumnya sebesar $> 500\text{ ms}$ atau berada dalam radius $> 30\text{ px}$.

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Penggunaan Teks "Lorem Ipsum" Acak
*   *Kesalahan:* Memasukkan paragraf teks Latin generik. Hal ini merusak validitas pengujian pemahaman alur karena pengguna tidak memiliki petunjuk konteks untuk memahami fungsi blok.
*   *Solusi:* Gunakan *redacted blocks* (garis balok abu-abu untuk teks isi) atau gunakan label semantik eksplisit yang mendeskripsikan peran konten (misal: `[Ringkasan Kewajiban Pajak Tahunan]`).

### 2. Terlalu Dini Menggunakan Komponen Design System High-Fi
*   *Kesalahan:* Mengimpor komponen dari UI library produksi yang sudah memiliki styling visual, warna, dan mikro-animasi lengkap untuk pengujian alur navigasi dasar.
*   *Solusi:* Bangun layer isolasi berupa *Skeleton Theme* atau gunakan paket komponen *Wireframe UI Primitives* khusus eksperimen yang mematikan *elevation*, warna aksen, dan kurva kurvatur modern.

### 3. Tidak Adanya Randomisasi Alokasi Varian (Selection Bias)
*   *Kesalahan:* Menguji Varian A kepada 10 orang pertama di pagi hari dan Varian B kepada 10 orang di sore hari secara manual.
*   *Solusi:* Selalu gunakan fungsi *deterministic cryptographic/pseudo-random hash* yang mengikat identitas unik tester dengan varian uji pada tingkat runtime arsitektur pengetesan.

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Strict 8-Point Grayscale Matrix:** Dalam wireframing kode, gunakan hanya 4 rentang warna fungsional: `#FFFFFF` (permukaan), `#E0E0E0` (komponen interaktif pasif), `#888888` (masking teks/placeholder), dan `#111111` (batas struktural dan teks instruksional).
2.  **Explicit Target Boundary Demarcation:** Semua batas elemen interaktif wajib memiliki outline solid minimal 2px dengan kontras tinggi guna menguji affordance fisik secara akurat.
3.  **Real Data Typography Placeholders:** Jika teks harus ditampilkan, gunakan ukuran font terstandardisasi (12px, 14px, 18px) menggunakan famili font fixed-width (`Courier New`, `ui-monospace`) untuk menghilangkan bias tipografi komersial.
4.  **Task Success Thresholds (Quantifiable Definition of Done):** Sebuah iterasi wireframe low-fi hanya boleh lolos ke tahap pembuatan *High-Fi Design Token* jika memenuhi kriteria:
    *   *Task Completion Rate* $\ge 85\%$.
    *   *Lostness Metric* ($L$) $\le 0.25$.
    *   *Critical Path Dead-Click Rate* $< 5\%$.

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

Meskipun berupa prototipe beresolusi rendah, pengujian eksperimental sering kali dijalankan pada perangkat pengguna secara remote tanpa supervisi teknis. Beban telemetri tidak boleh mendegradasi frame rate pengujian:

### 1. Batching dan Buffering Telemetri Interaksi
Hindari pengiriman transmisi HTTP per event interaksi:

```ts
// TelemetryBuffer.ts
class TelemetryDispatcher {
  private buffer: TelemetryPayload[] = [];
  private readonly flushThreshold: number = 10;
  private readonly endpoint: string = '/api/v1/experiment-metrics';

  public record(event: TelemetryPayload): void {
    this.buffer.push(event);
    if (this.buffer.length >= this.flushThreshold) {
      this.flush();
    }
  }

  public flush(): void {
    if (this.buffer.length === 0) return;
    const payload = JSON.stringify(this.buffer);
    this.buffer = [];

    if (typeof navigator !== 'undefined' && navigator.sendBeacon) {
      navigator.sendBeacon(this.endpoint, payload);
    } else {
      fetch(this.endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: payload,
        keepalive: true,
      }).catch((err) => console.error('Failed to flush telemetry', err));
    }
  }
}
export const telemetryDispatcher = new TelemetryDispatcher();
```

### 2. Memory Leak Mitigation pada Event Tracking Terdistribusi
Komponen interaktif low-fi yang memantau interaksi hover dan durasi hesitation wajib membersihkan timer internal (`clearTimeout`) pada siklus `unmount` untuk mencegah memory leak selama navigasi dinamis berulang.

---

# SEKSI 16 — KEAMANAN & HARDENING

1.  **PII Sanitization pada Input Mocking:** Prototipe pengujian sering kali meminta pengguna memasukkan data simulasi. Sistem harness eksperimen wajib mematikan *autofill browser* (`autoComplete="off"`) dan menyamarkan (*mask*) semua input karakter sebelum dicatat ke dalam log telemetri guna mematuhi standar GDPR dan ISO 27001.
2.  **Experiment Token Cryptographic Tampering Prevention:** Status alokasi varian pengguna tidak boleh disimpan secara plaintext di local-storage tanpa penandatanganan HMAC jika