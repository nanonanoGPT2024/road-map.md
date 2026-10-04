# BAB 06: Wireframing, Lo-Fi Prototyping, dan Validasi Cepat
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
*   Mendesain dan mengimplementasikan **Component-Driven Greybox Systems** (Lo-Fi Design Systems) berskala enterprise untuk memisahkan validasi arsitektur informasi dari bias estetika visual.
*   Mengonstruksi **Finite State Machine (FSM) Low-Fidelity Prototyping** guna memetakan seluruh *edge-case*, *loading state*, dan *error boundaries* sebelum masuk ke fase High-Fidelity.
*   Membangun pipeline **Rapid Instrumented Validation** menggunakan instrumentasi telemetri mikro (misal: *time-to-first-interaction*, *misclick rate*, *hesitation time*) pada prototipe interaktif berbasis kode (*code-based lo-fi*).
*   Mengeksekusi siklus **RITE (Rapid Iterative Testing and Evaluation)** terotomatisasi yang terintegrasi dengan backlog rekayasa perangkat lunak tanpa memicu *design debt*.
*   Menghitung dan memitigasi **UX Cost of Rework** menggunakan metrik estimasi deviasi arsitektural berbasis *Boehm’s Law*.

---

### 2. Prerequisite
*   Pemahaman mendalam mengenai **Arsitektur Informasi (IA)**, *Mental Models*, dan *Cognitive Load Theory*.
*   Keahlian dasar dalam state management (State Machine / Reducer pattern) dan pemodelan alur aplikasi web/mobile.
*   Penguasaan sintaksis **TypeScript**, **React/Next.js** (atau framework frontend setara), dan utilitas styling seperti **Tailwind CSS**.
*   Pengalaman menggunakan instrumen riset kuantitatif/kualitatif (SUS, SEQ, Task Completion Time) dan analitik interaksi web (DOM event capturing).

---

### 3. Concept & Internal Architecture

Dalam rekayasa sistem enterprise, *Wireframing* dan *Lo-Fi Prototyping* bukanlah sekadar aktivitas menggambar sketsa kotak dan garis silang secara serampangan. Ini adalah tahap **dekomposisi struktural formal** dari sistem antarmuka.

#### Pemisahan Lapisan Estetika dan Lapisan Informasi
Berdasarkan prinsip *Aesthetic-Usability Effect*, pengguna cenderung mengabaikan cacat fungsional minor jika antarmuka terlihat menarik secara visual. Pada tahap awal validasi produk enterprise yang memiliki kompleksitas fungsional tinggi (seperti platform *FinTech Trading*, *EHR Kesehatan*, atau *Supply Chain Management*), efek ini justru menjadi anomali data (bias positif palsu).

```
+----------------------------------------------------------------------+
|                     HIERARKI ABSTRAKSI PRODUK                        |
+----------------------------------------------------------------------+
| [Layer 3] Chrome & Style       : Tipografi final, Token Warna, Aset  |
|                                  (Sumber utama bias estetika)        |
+----------------------------------------------------------------------+
| [Layer 2] State & Interaksi    : FSM, Micro-transitions, Form Flow  |
|                                  (VALIDASI MODUL 02)                 |
+----------------------------------------------------------------------+
| [Layer 1] Arsitektur Informasi : Hierarki DOM, Relasi Entitas,      |
|                                  Spatial Layout, Kontrak API         |
|                                  (VALIDASI MODUL 02)                 |
+----------------------------------------------------------------------+
```

Arsitektur produksi Lo-Fi mengisolasi **Layer 1** dan **Layer 2**. Dengan membuang seluruh *visual chrome* (Layer 3), pengujian difokuskan murni pada:
1.  **Navigability**: Apakah model mental tata letak sesuai ekspektasi operasional pengguna?
2.  **Semantic Hierarchy**: Apakah urutan pemindaian visual (*visual hierarchy*) terbaca dengan benar tanpa bantuan warna aksen?
3.  **Flow Resilience**: Bagaimana pengguna bereaksi terhadap skenario kegagalan (*network jitter*, validasi input kompleks, struktur data masif)?

#### Greybox Component-Driven Architecture
Alih-alih membuat wireframe statis terpisah di canvas Figma tanpa standarisasi struktural, tim enterprise mengadopsi **Greybox UI Kit**. Komponen ini menggunakan primitif headless (misal: Radix UI, Headless UI, atau HTML semantik) yang dilapisi dengan kelas *low-fidelity* deterministik:
*   Palet warna monokromatik terstandarisasi (skala abu-abu berbasis lightness ISO: `#F4F4F5`, `#E4E4E7`, `#71717A`, `#18181B`).
*   Placeholder dinamis dengan bounding-box kontekstual yang mengunci rasio aspek (*aspect-ratio preservation*).
*   Tipografi sans-serif netral berskala matematis tunggal (misal: sistem skala modular rasio 1.25) tanpa variasi bobot ekstrem.

#### Instrumented Validation Pipeline
Prototipe Lo-Fi tingkat lanjut diinstrumentasikan dengan pustaka telemetri lokal untuk menangkap interaksi pengguna secara presisi sebelum lini pertama kode UI High-Fidelity ditulis. Parameter yang diukur meliputi:
*   **Time-to-Intent (TTI)**: Durasi dari render layar hingga klik/fokus pertama yang relevan secara semantik.
*   **Misclick Index**: Rasio klik pada elemen non-interaktif dalam greybox terhadap total klik pengguna.
*   **State Traverse Divergence**: Deviasi antara rute *happy path* pada FSM versus urutan state aktual yang dijalankan pengguna selama evaluasi.

---

### 4. Why & What

| Dimensi | Pendekatan Ad-Hoc / Statis Lo-Fi | Enterprise-Grade Instrumented Lo-Fi |
| :--- | :--- | :--- |
| **Representasi State** | Single-state mockup (hanya skenario ideal). | Komprehensif (FSM: Empty, Loading, Error, Partial, Overflow). |
| **Validasi Pengguna** | Wawancara subjektif pasca-tes (*"Bagaimana menurut Anda?"*). | Pengukuran empiris (TTI, SEQ, Telemetri Misclick, Deviasi Task). |
| **Biaya Siklus Iterasi** | Lambat: Revisi visual memakan waktu di Figma/Canvas. | Sangat Cepat: Revisi semantik struktural dalam hitungan menit via token Lo-Fi. |
| **Handoff ke Engineering** | Tidak jelas: Developer harus menerka layout behavior. | Presisi: Kontrak tata letak struktural berbasis Grid/Flexbox dengan spesifikasi DOM. |
| **Toleransi Bias** | Tinggi (terpengaruh bias warna dan representasi visual). | Rendah (hanya struktur dan interaksi murni yang diuji). |

#### Dampak Finansial: Hukum Boehm dalam Siklus UX
Biaya memperbaiki defek arsitektur informasi meningkat secara eksponensial seiring bertambahnya siklus hidup software development:
*   **Fase Lo-Fi Wireframing**: Biaya perbaikan = **1x** (Perubahan struktur DOM/komponen teks).
*   **Fase Hi-Fi Visual Design**: Biaya perbaikan = **5x** (Penyesuaian token, auto-layout, interaksi Figma terhubung, desain responsif multi-platform).
*   **Fase Produksi Frontend**: Biaya perbaikan = **30x - 100x** (Refactoring state management, rewriting API payload bindings, re-testing QA).

Investasi pada validasi berbasis Lo-Fi yang ketat secara arsitektural mencegah deviasi struktural masuk ke fase implementasi kode produksi Hi-Fi.

---

### 5. How (Workflow Detail)

```
[Tahap 1: FSM & Structural Scaffolding]
       │
       ▼
[Tahap 2: Komposisi Greybox System (Code/Design)]
       │
       ▼
[Tahap 3: Instrumentasi Telemetri Event DOM]
       │
       ▼
[Tahap 4: Eksekusi Protokol RITE (N=5 per batch)]
       │
       ├───> Jika Defek Kritis Ditemukan (>60% kegagalan task)
       │         │
       │         └───> Refactor Arsitektur Seketika (Siklus < 2 Jam)
       ▼
[Tahap 5: Ekstraksi Insights & Handoff Arsitektural]
```

#### Langkah 1: Pemodelan State Alur Kerja (FSM Modeling)
Sebelum meletakkan elemen di kanvas atau editor kode, definisikan alur navigasi menggunakan mesin state formal.
*   Petakan semua state: `Idle`, `Loading`, `Active`, `Validating`, `Error_Input`, `Error_Network`, `Success`.
*   Tentukan transisi pemicu (*event triggers*) eksplisit untuk mencegah *dead-end states*.

#### Langkah 2: Konstruksi Antarmuka Greybox
Gunakan komponen greybox modular. Komponen harus mematuhi aturan berikut:
*   Tidak ada ikonografi dekoratif (gunakan representasi *bounding-box* universal dengan teks semantik).
*   Gunakan data semi-realistis (*structured synthetic data*), **hindari *Lorem Ipsum*** karena merusak validitas *cognitive scanning* penguji.
*   Pertahankan hierarki tipografi berbasis hierarki HTML murni (`h1`, `h2`, `h3`, `p`, `span`).

#### Langkah 3: Instrumentasi Prototipe
Pasang event listener analitik pada elemen interaktif untuk mencatat:
1.  Target Element ID.
2.  Timestamp Unix waktu interaksi terjadi.
3.  Bounding client rect koordinat klik (untuk memverifikasi misclick).
4.  Current State FSM.

#### Langkah 4: Pelaksanaan Siklus RITE (Rapid Iterative Testing and Evaluation)
*   Jalankan testing dengan partisipan dalam jumlah kecil ($N = 5$) per batch.
*   Jika partisipan 1 dan 2 mengalami *blocker* struktural pada titik interaksi yang sama, **hentikan tes secara temporer**.
*   Lakukan refactor struktural langsung pada prototipe Lo-Fi (karena berbasis Greybox, perubahan ini memakan waktu < 30 menit).
*   Lanjutkan pengujian dengan partisipan 3, 4, dan 5 untuk memvalidasi apakah perubahan struktural berhasil menyelesaikan masalah tersebut.

#### Langkah 5: Synthesis & Architectural Handoff
Hasil dari fase ini bukan sekadar wireframe statis, melainkan **Layout Structural Contract** yang memuat:
*   Spesifikasi flexbox/grid layout.
*   Struktur payload data minimal yang dibutuhkan oleh UI.
*   Matriks status kegagalan interaksi (*interaction failure matrix*).

---

### 6. Analogy & Diagram ASCII

#### Analogi: Rangka Tulang Beton vs. Pengecatan Interior
Membangun antarmuka pengguna tanpa validasi Lo-Fi yang ketat sama dengan membangun gedung pencakar langit langsung mengecat dinding dan memasang marmer sebelum struktur kolom beton dan jalur pipa air diuji tekanannya. Menggeser dinding pembatas ruangan saat gedung masih berupa tiang beton bertulang memakan biaya kecil dan waktu beberapa menit. Namun, menggeser dinding yang sudah dilapisi keramik impor, instalasi kelistrikan, dan cat dekoratif membutuhkan pembongkaran besar (*demolition cost*) yang masif.

#### Diagram Arsitektur Instrumented Lo-Fi Validation Platform

```
+──────────────────────────────────────────────────────────────────────────+
|                    GREYBOX INSTRUMENTED HARNESS                          |
+──────────────────────────────────────────────────────────────────────────+
|                                                                          |
|   +────────────────────────+            +────────────────────────────+   |
|   |   Component Tree       |            |   Finite State Machine     |   |
|   |   (Semantic Greybox)   |            |   (Interaction Controller) |   |
|   |                        |            |                            |   |
|   |   [ GreyboxNav ]       |            |   State: 'Awaiting_Input'  |   |
|   |   [ GreyboxDataTable ] |<──────────>|   Transitions:             |   |
|   |   [ GreyboxActionPane] |            |    - SUBMIT -> 'Validating'|   |
|   |   [ GreyboxModal ]     |            |    - RETRY  -> 'Fetching'  |   |
|   +───────────┬────────────+            +─────────────┬──────────────+   |
|               │                                       │                  |
|               │ DOM Interactions                      │ State Changes    |
|               ▼                                       ▼                  |
|   +──────────────────────────────────────────────────────────────────+   |
|   |                Telemetry Engine (Validation Layer)               |   |
|   |                                                                  |   |
|   |  - Event: CLICK, FOCUS, HOVER, SCROLL                            |   |
|   |  - Metrics: Time-to-Intent (TTI), Dead-Click Detector            |   |
|   |  - State Alignment: Actual Flow vs Expected Flow Mapper          |   |
|   +─────────────────────────────────┬────────────────────────────────+   |
|                                     │                                    |
+─────────────────────────────────────┼────────────────────────────────────+
                                      │ Dispatch Batch Telemetry
                                      ▼
                      +────────────────────────────────+
                      |   Local Storage / Log Server   |
                      |   - Time on Task               |
                      |   - Error Deviation Log        |
                      |   - RITE Iteration Marker      |
                      +────────────────────────────────+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Semantic Greybox Structure (HTML/Tailwind CSS)
Struktur statis semantik untuk memverifikasi model mental penempatan navigasi data tabel tanpa dekorasi visual.

```html
<!-- Structural Wireframe Component: High-Density Data Header -->
<header class="w-full bg-zinc-200 border-b-2 border-zinc-400 p-4 flex justify-between items-center">
  <div class="flex items-center gap-4">
    <!-- Visual Skeleton Placeholder -->
    <div class="w-8 h-8 bg-zinc-400 border border-zinc-500 rounded-none flex items-center justify-center text-xs font-mono font-bold">
      [L]
    </div>
    <div class="h-6 w-48 bg-zinc-300 border border-zinc-400 flex items-center px-2 text-xs font-mono text-zinc-700">
      SYSTEM_DASHBOARD / AUDIT
    </div>
  </div>
  
  <nav class="flex gap-2">
    <div class="h-8 w-24 bg-zinc-300 border border-zinc-400 flex items-center justify-center text-xs font-mono">
      FILTER [v]
    </div>
    <div class="h-8 w-28 bg-zinc-800 text-zinc-100 flex items-center justify-center text-xs font-mono font-bold">
      + EXECUTE [ENTER]
    </div>
  </nav>
</header>
```

#### B. Practical Example: Production-Grade Instrumented Greybox Prototype
Implementasi Lo-Fi prototipe berbasis React dan TypeScript yang memuat **Finite State Machine**, **Komponen Greybox Semantik**, dan **Engine Telemetri Sederhana** untuk validasi alur transaksi.

```tsx
// hands-on/m02/src/InstrumentedWireframe.tsx

import React, { useState, useEffect, useRef } from 'react';

// --- TELEMETRY CORE TYPES ---
interface InteractionEvent {
  targetId: string;
  eventType: string;
  timestamp: number;
  timeSinceRenderMs: number;
  fsmState: string;
  isMisclick?: boolean;
}

// --- FSM DEFINITION ---
type StepState = 'SELECT_RECIPIENT' | 'ALLOCATE_FUNDS' | 'VALIDATION_ERROR' | 'SYSTEM_PROCESSING' | 'CONFIRMATION';

export const InstrumentedTransferWireframe: React.FC = () => {
  const [state, setState] = useState<StepState>('SELECT_RECIPIENT');
  const [recipient, setRecipient] = useState<string>('');
  const [amount, setAmount] = useState<string>('');
  const telemetryLogs = useRef<InteractionEvent[]>([]);
  const mountTime = useRef<number>(Date.now());

  // Hook telemetry capture
  const trackInteraction = (targetId: string, eventType: string, isMisclick = false) => {
    const now = Date.now();
    const event: InteractionEvent = {
      targetId,
      eventType,
      timestamp: now,
      timeSinceRenderMs: now - mountTime.current,
      fsmState: state,
      isMisclick,
    };
    telemetryLogs.current.push(event);
    console.debug('[TELEMETRY DISPATCH]:', event);
  };

  // Misclick boundary handler
  const handleBackgroundClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget) {
      trackInteraction('CONTAINER_DEADZONE', 'MISCLICK', true);
    }
  };

  const handleNext = () => {
    trackInteraction('BTN_NEXT', 'CLICK');
    if (state === 'SELECT_RECIPIENT') {
      if (!recipient) {
        setState('VALIDATION_ERROR');
      } else {
        setState('ALLOCATE_FUNDS');
      }
    } else if (state === 'ALLOCATE_FUNDS') {
      if (!amount || parseFloat(amount) <= 0) {
        setState('VALIDATION_ERROR');
      } else {
        setState('SYSTEM_PROCESSING');
        setTimeout(() => {
          setState('CONFIRMATION');
          trackInteraction('SYSTEM', 'AUTO_TRANSITION_SUCCESS');
        }, 1200);
      }
    }
  };

  const dumpAnalytics = () => {
    console.log('--- TEST RUN ANALYTICS SUMMARY ---');
    console.table(telemetryLogs.current);
    alert(`Testing completed. Events logged: ${telemetryLogs.current.length}`);
  };

  return (
    <div 
      onClick={handleBackgroundClick}
      className="min-h-screen bg-zinc-100 p-8 font-mono text-zinc-900 flex flex-col justify-between"
    >
      {/* Top Bar / Metadata */}
      <header className="border-b-2 border-zinc-800 pb-4 flex justify-between items-center">
        <div>
          <span className="font-black text-sm bg-zinc-300 px-2 py-1 border border-zinc-600">WIRE-LOFI-002</span>
          <span className="ml-4 text-xs font-semibold">STAGE: {state}</span>
        </div>
        <button 
          onClick={dumpAnalytics}
          className="text-xs border border-zinc-800 px-3 py-1 bg-zinc-200 hover:bg-zinc-300 active:bg-zinc-400"
        >
          EXPORT_TELEMETRY()
        </button>
      </header>

      {/* Dynamic Interaction Workspace */}
      <main className="max-w-xl mx-auto w-full my-auto border-2 border-zinc-800 p-6 bg-white shadow-[4px_4px_0px_0px_rgba(24,24,27,1)]">
        {state === 'SELECT_RECIPIENT' && (
          <section className="space-y-4">
            <h2 className="text-sm font-bold tracking-tight">01 // SELECT BENEFICIARY ENTITY</h2>
            <div className="space-y-2">
              <label htmlFor="beneficiary-select" className="text-xs block text-zinc-600">ACCOUNT_DESIGNATION</label>
              <select 
                id="beneficiary-select"
                value={recipient}
                onChange={(e) => {
                  setRecipient(e.target.value);
                  trackInteraction('SELECT_ACCOUNT', 'CHANGE');
                }}
                className="w-full border-2 border-zinc-800 p-2 text-xs bg-zinc-50 rounded-none focus:outline-none focus:bg-zinc-200"
              >
                <option value="">-- ASSIGN TARGET --</option>
                <option value="TREASURY-098">TREASURY-098 (HOLDING CORP)</option>
                <option value="ESCROW-771">ESCROW-771 (SETTLEMENT)</option>
              </select>
            </div>
          </section>
        )}

        {state === 'ALLOCATE_FUNDS' && (
          <section className="space-y-4">
            <h2 className="text-sm font-bold tracking-tight">02 // ALLOCATE BALANCE UNITS</h2>
            <div className="p-2 bg-zinc-100 border border-zinc-400 text-xs">
              DESTINATION: <span className="font-bold">{recipient}</span>
            </div>
            <div className="space-y-2">
              <label htmlFor="fiat-amount" className="text-xs block text-zinc-600">VALUE_UNITS (USD)</label>
              <input 
                id="fiat-amount"
                type="number"
                value={amount}
                onChange={(e) => {
                  setAmount(e.target.value);
                  trackInteraction('INPUT_AMOUNT', 'INPUT');
                }}
                placeholder="0.00"
                className="w-full border-2 border-zinc-800 p-2 text-xs bg-zinc-50 rounded-none focus:outline-none focus:bg-zinc-200"
              />
            </div>
          </section>
        )}

        {state === 'VALIDATION_ERROR' && (
          <section className="space-y-4 border border-zinc-800 p-4 bg-zinc-200">
            <h2 className="text-sm font-black underline">INPUT_BREACH_DETECTED</h2>
            <p className="text-xs">Required system values were missing or structurally malformed during the state transition.</p>
            <button
              onClick={() => {
                trackInteraction('BTN_RESOLVE_ERROR', 'CLICK');
                setState(recipient ? 'ALLOCATE_FUNDS' : 'SELECT_RECIPIENT');
              }}
              className="w-full border border-zinc-800 bg-white py-2 text-xs font-bold hover:bg-zinc-50"
            >
              ACKNOWLEDGE_AND_REPAIR()
            </button>
          </section>
        )}

        {state === 'SYSTEM_PROCESSING' && (
          <div className="py-12 flex flex-col items-center justify-center space-y-4">
            <div className="w-6 h-6 border-2 border-zinc-800 border-t-transparent animate-spin"></div>
            <span className="text-xs animate-pulse">EXECUTING_LEDGER_ALLOCATION...</span>
          </div>
        )}

        {state === 'CONFIRMATION' && (
          <section className="space-y-4 text-center py-4">
            <div className="inline-block border-2 border-zinc-800 p-3 bg-zinc-200 text-sm font-bold">
              TX_COMMITTED
            </div>
            <p className="text-xs text-zinc-600">Transaction ID: {Math.random().toString(36).substring(7).toUpperCase()}</p>
            <button
              onClick={() => {
                trackInteraction('BTN_RESET', 'CLICK');
                setRecipient('');
                setAmount('');
                setState('SELECT_RECIPIENT');
              }}
              className="border border-zinc-800 px-4 py-2 text-xs hover:bg-zinc-200"
            >
              NEW_ALLOCATION
            </button>
          </section>
        )}

        {/* Global Action Terminal */}
        {state !== 'SYSTEM_PROCESSING' && state !== 'VALIDATION_ERROR' && state !== 'CONFIRMATION' && (
          <div className="mt-8 pt-4 border-t border-zinc-300 flex justify-end gap-2">
            <button 
              onClick={handleNext}
              className="bg-zinc-900 text-white px-6 py-2 text-xs font-bold hover:bg-zinc-700 active:scale-95 transition-all"
            >
              TRANSITION_STEP &gt;&gt;
            </button>
          </div>
        )}
      </main>

      {/* Structural Wireframe Footer */}
      <footer className="border-t border-zinc-300 pt-2 flex justify-between text-[10px] text-zinc-500">
        <span>GREYBOX VALIDATION HARNESS v2.1</span>
        <span>ENVIRONMENT: UNMODERATED_RUN</span>
      </footer>
    </div>
  );
};
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
*Platform*: Sistem Rekonsiliasi Valuta Asing Multi-Bank Tier-1 (B2B Clearing House).  
*Pengguna Target*: 1.200 Dealer Valas dan Corporate Treasurers dengan batas waktu eksekusi harian (*settlement cutoff window*) 15 menit.

#### Permasalahan Awal
Desain High-Fidelity lama menyebabkan rata-rata *Time-to-Execute* transaksi bernilai tinggi adalah 4,2 menit per order, dengan tingkat *order misrouting* sebesar 11,4%. Tim produk awalnya berasumsi bahwa pengguna membutuhkan "tampilan visual yang lebih modern" dengan dashboard berbasis tema gelap (*dark mode*) dan visual chart interaktif.

#### Intervensi Arsitektural (Modul 02 Engine)
1.  **Greybox Extraction**: Seluruh styling warna, icon kit mewah, dan chart animasi dibuang total. UI dikembalikan ke status *structural wireframe* berbasis monospace murni dengan layout tabular densitas tinggi (*high data-density greybox*).
2.  **Pemodelan Ulang State**: Ditemukan bahwa alur konfirmasi bertingkat memicu ambiguitas pemrosesan manual. FSM diubah dari *Linear Sequential Flow* menjadi *Single-Screen Split-Pane Ledger*.
3.  **Protokol RITE Terkomputasi**: Sebanyak 3 batch testing (total 15 treasurer profesional) dilakukan dalam 48 jam:
    *   *Batch 1 (Partisipan 1-5)*: 80% gagal menemukan tombol validasi cepat karena diletakkan di dalam footer modal. Prototipe langsung dimodifikasi: modal dihilangkan, aksi integrasikan langsung ke baris tabel (inline shortcut).
    *   *Batch 2 (Partisipan 6-10)*: TTI menurun 40%, namun terjadi *Misclick Index* tinggi pada *bulk action trigger*. Tipe seleksi diubah menjadi seleksi berbasis keyboard *hotkeys*.
    *   *Batch 3 (Partisipan 11-15)*: Selesai tanpa satu pun interupsi atau kegagalan struktural.

#### Hasil Produksi
Setelah struktur arsitektur tervalidasi via Lo-Fi greybox, barulah aset High-Fidelity Design System diterapkan.
*   **Time-to-Execute** terpangkas dari **4,2 menit menjadi 48 detik** per kliring transaksi.
*   **Tingkat Order Misrouting** anjlok menjadi **0,08%**.
*   Penghematan alokasi *engineering hours* diperkirakan mencapai 320 jam kerja dev team karena tidak ada *re-architecture* database maupun layout pasca-rilis.

---

### 9. Trade-offs

```
                       [CODE-BASED LO-FI]
                              ▲
                             / \
                            /   \
  Kecepatan Setup Cepat   /     \  Presisi Interaksi & Telemetri
  Fleksibilitas Desain   /       \ State Control Sempurna
                        /         \
                       ▼───────────▼
  [CANVAS-BASED LO-FI]               [HYBRID STATIC SPEC]
  (Figma/Balsamiq)                   (HTML/CSS Mockups)
```

| Pendekatan | Keuntungan Utama | Kerugian / Biaya Konsekuensi |
| :--- | :--- | :--- |
| **Canvas-Based Wireframing** *(e.g., Figma Greybox Kits)* | **Velocity tinggi**. Desainer non-teknis dapat mengubah tata letak spasial dalam hitungan detik. Bagus untuk *concept discovery* tingkat tinggi. | **State blindness**. Tidak mampu mensimulasikan ketergantungan logika asinkronus yang rumit, validasi form nyata, dan beban latensi rendering sistem sesungguhnya. |
| **Code-Based Instrumented Lo-Fi** *(e.g., React/Tailwind Greybox)* | **Presisi absolut**. Mampu menangkap telemetri mikro (misclick, TTI aktual), memvalidasi FSM dengan data dinamis, dan reusable sebagai *skeleton architecture* frontend. | **Initial overhead tinggi**. Membutuhkan skill rekayasa frontend dan waktu persiapan *harness* lebih lama sebelum pengujian dimulai. |
| **Monochrome Greyboxing** | Menghilangkan **Aesthetic Bias**. Menguji secara objektif hierarki spasial dan *scannability* data murni. | **Stakeholder Resistance**. Eksekutif atau klien non-teknis sering salah paham dan menganggap produk tampak "rusak", "jadul", atau belum selesai. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. "Aesthetic Creep" (Penyusupan Unsur Estetika Prematur)
*   *Gejala*: Menghabiskan waktu memilih variasi warna button, mencari ikon visual ilustratif, atau mengatur border-radius halus pada tahap wireframe.
*   *Dampak*: Pengguna fokus mengomentari warna atau gaya ikon alih-alih alur kerja fungsional (*visual distraction*).
*   *Mitigasi*: Kunci CSS global prototipe dengan style: `* { border-radius: 0px !important; font-family: monospace !important; }` dan batasi token warna hanya ke 4 tingkat abu-abu.

#### 2. Happy-Path Myopia (Mengabaikan Edge-Case State)
*   *Gejala*: Wireframe hanya memperlihatkan antarmuka saat data terisi secara rapi dan panjang teks selalu simetris.
*   *Dampak*: Saat masuk ke tahap engineering, tata letak pecah (*layout shift*) akibat teks overflow, data kosong (*null-state*), atau error validasi API.
*   *Mitigasi*: Definisikan aturan data *stress-test* pada wireframe: String sepanjang 200 karakter tanpa spasi, angka nominal desimal 18 digit, dan view ketika array koleksi data bernilai `[]` (kosong).

#### 3. Post-Testing Rationalization (Bias Konfirmasi)
*   *Gejala*: Mengabaikan keraguan partisipan saat menguji wireframe dengan dalih: *"Nanti kalau sudah ada warnanya dan gambarnya, mereka pasti paham."*
*   *Dampak*: Memindahkan kegagalan struktural ke dalam fase implementasi High-Fidelity.
*   *Mitigasi*: Jika partisipan gagal menyelesaikan tugas pada wireframe, asumsikan itu adalah **kegagalan arsitektur struktural**, bukan kegagalan estetika. Terapkan RITE: refactor struktur antarmuka sebelum partisipan berikutnya masuk.

---

### 11. Best Practices (Production Checklist)

#### Architectural Greybox Foundation
- [ ] Prototipe hanya menggunakan tipografi monospaced atau font sans-serif netral dengan maksimal 2 level ukuran font struktural.
- [ ] Seluruh variasi warna dibatasi pada skala lightness abu-abu netral; tidak ada warna aksen selain penanda error fungsional primitif.
- [ ] Bounding box placeholder mempertahankan rasio aspek nyata data produksi target.
- [ ] Semua elemen interaktif memiliki identitas semantik eksplisit (`data-testid` atau `id` yang merefleksikan model domain).

#### Finite State Validation
- [ ] State `Empty` (data kosong) dirancang dengan alur panduan pemulihan (*recovery path*).
- [ ] State `Error` (kegagalan sistem/validasi input) memiliki spesifikasi representasi antarmuka yang jelas.
- [ ] State `Loading/Processing` membatasi interaksi pengguna untuk mencegah *double submit*.
- [ ] State `Overflow` teruji terhadap teks panjang dan volume data ekstrem.

#### Instrumented Testing Readiness
- [ ] Telemetri capturing terpasang pada batas area non-interaktif (*misclick tracking*).
- [ ] Metrik Time-to-Intent (TTI) terukur secara otomatis dari pertama kali layar ter-render.
- [ ] Skenario testing mendefinisikan kriteria sukses obyektif (*Target Task Completion Time* < X detik).
- [ ] Mekanisme dump data telemetri (JSON/Table) dapat diakses tanpa merusak konteks pengujian.

---

### 12. Hands-on Practice

Buatlah sistem prototipe greybox instrumentasi mandiri di dalam direktori `hands-on/m02/`.

#### Langkah 1: Inisialisasi Lingkungan
```bash
mkdir -p hands-on/m02/src
cd hands-on/m02
npm init -y
npm install react react-dom clsx
npm install -D typescript @types/react @types/react-dom tailwindcss postcss autoprefixer vite @vitejs/plugin-react
npx tailwindcss init -p
```

#### Langkah 2: Konfigurasi Tailwind untuk Lo-Fi Monokromatik murni
Perbarui file `hands-on/m02/tailwind.config.js`:
```javascript
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        mono: ['Courier Prime', 'Courier', 'monospace'],
      },
      colors: {
        wire: {
          bg: '#E4E4E7',
          surface: '#FFFFFF',
          border: '#18181B',
          muted: '#71717A',
          shade: '#D4D4D8',
        }
      }
    },
  },
  plugins: [],
}
```

#### Langkah 3: Eksekusi File Prototipe
Salin kode dari **Seksi 7.B (`InstrumentedTransferWireframe`)** ke dalam `hands-on/m02/src/App.tsx`. Jalankan dengan Vite:
```bash
npx vite
```

#### Langkah 4: Validasi Mandiri
1.  Buka browser console.
2.  Lakukan klik pada area kosong (misclick) di sekitar form. Amati log telemetri:
    `[TELEMETRY DISPATCH]: Object { targetId: "CONTAINER_DEADZONE", eventType: "MISCLICK", isMisclick: true, ... }`
3.  Selesaikan seluruh alur transfer. Klik tombol `EXPORT_TELEMETRY()` di bagian atas untuk mencetak matriks evaluasi interaksi.

---

### 13. Exercise

#### Level 1 (Easy) - Structural Redesign
Ubah komponen modal konfirmasi yang biasanya berupa pop-up mengambang menjadi representasi **Inline Expansion (Accordion) Wireframe** menggunakan Tailwind CSS monokromatik. Komponen harus memiliki dua state visual statis: `COLLAPSED` dan `EXPANDED`.

#### Level 2 (Medium) - Instrumented Multi-Step Greybox Form
Bangun form 3 langkah (Identitas -> Alamat -> Tinjauan) berbasis React/TypeScript. Pasang telemetri yang menghitung waktu yang dihabiskan pengguna pada setiap field form (`hesitation time`) dari event `focus` hingga event `blur`. Tampilkan ringkasan durasi per field di akhir proses form.

#### Level 3 (Hard) - RITE Loop Engine dengan State Inversion
Implementasikan prototipe wireframe berbasis web untuk filter tabel kompleks. Buat sistem yang secara otomatis mengubah layout jika pengguna melakukan lebih dari 3 *misclick* atau salah memilih dropdown: antarmuka secara adaptif beralih dari model *Dropdown Multi-Select* ke model *Exposed Checkbox Matrix*. Seluruh transisi harus tercatat dalam log audit telemetri internal untuk validasi pengujian RITE berikutnya.

---

### 14. Challenge

#### Deskripsi Skenario Kasus Kompleks
Anda adalah Principal UX Architect untuk sistem **Clinical Intensive Care Unit (ICU) Dashboard**. Para perawat dan dokter bekerja di bawah tekanan tinggi (kelelahan kognitif ekstrem, pencahayaan bervariasi, alarm konstan). 

Sistem saat ini mengalami kendala: Waktu yang dibutuhkan perawat untuk memasukkan data penyesuaian dosis obat darurat (*Titration Dose*) memakan waktu rata-rata 38 detik karena antarmuka yang dipenuhi data sekunder non-kritis dan dropdown bertingkat.

#### Batasan Arsitektural dan Parameter Tantangan
1.  **Strict Greybox Only**: Desain tidak boleh menggunakan warna visual sama sekali kecuali warna solid abu-abu, hitam, dan putih (skala monokromatik). Tidak boleh menggunakan ikon SVG berbasis ilustratif.
2.  **Instrumented Code Prototype**: Buat implementasi berbasis TypeScript/React yang mencakup:
    *   State Machine lengkap: `NORMAL_MONITOR`, `ADJUST_DOSE_INITIATED`, `SAFETY_LIMIT_OVERRIDE_WARNING`, `DOSE_COMMITTED`.
    *   Pencegahan Human Error: Logika antarmuka harus mendeteksi *fat-finger input* (misal: input dosis melonjak 10x lipat dari baseline) dan memaksa model konfirmasi dua langkah struktural tanpa memicu kebingungan spasial.
3.  **Metrik Validasi**: Prototipe harus mengumpulkan data telemetri real-time:
    *   *Time-to-Intent (TTI)*
    *   *Total Task Execution Time*
    *   *Error Correction Velocity* (waktu dari munculnya state warning hingga perbaikan input).
4.  **Target Kinerja**: Alur interaksi yang Anda konstruksi harus membuktikan secara arsitektural bahwa penyesuaian dosis darurat dapat diselesaikan dalam waktu kurang dari **10 detik** pada prototipe instrumentasi tanpa memicu deviasi data (*zero unforced error*).

---

### 15. Quiz Evaluasi Pemahaman

#### Basic Level (5 Soal)

1. Mengapa bias estetika (*Aesthetic-Usability Effect*) berbahaya pada pengujian wireframe tahap awal?
   * A. Karena membuat pengguna meminta fitur animasi tambahan.
   * B. Karena pengguna cenderung memaafkan kecacatan fungsional dan struktural yang sebenarnya fatal akibat tampilan visual yang menarik.
   * C. Karena meningkatkan konsumsi memori browser saat rendering canvas.
   * D. Karena menghambat desainer dalam memilih warna brand perusahaan.

2. Ciri utama dari Greybox UI kit adalah:
   * A. Menggunakan warna-warna pastel untuk membedakan kategori fungsional.
   * B. Berorientasi pada visual akhir dengan aset bitmap beresolusi tinggi.
   * C. Penggunaan struktur monokromatik netral tanpa elemen dekoratif untuk mengevaluasi arsitektur informasi murni.
   * D. Selalu dibuat menggunakan aplikasi pensil manual di atas kertas kalkir.

3. Apa yang dimaksud dengan metrik Time-to-Intent (TTI) dalam telemetri wireframe?
   * A. Total waktu yang dibutuhkan frontend engine untuk memuat file CSS.
   * B. Durasi dari saat layar dirender hingga pengguna melakukan interaksi semantik terarah pertama kalinya.
   * C. Waktu yang diperlukan desainer untuk menggambar satu layar lo-fi.
   * D. Periode antara pengiriman form hingga respons kode status HTTP 200 diterima.

4. Manakah representasi data yang paling tepat digunakan pada wireframe fungsional enterprise?
   * A. Paragraf teks acak menggunakan *Lorem Ipsum dolor sit amet*.
   * B. Kotak kosong yang disilang tanpa informasi semantik sama sekali.
   * C. Data sintetis terstruktur yang mencerminkan rentang batas data riil di lingkungan produksi.
   * D. Variabel kosong bertuliskan `${data_goes_here}` di setiap label antarmuka.

5. Berdasarkan modifikasi Hukum Boehm untuk arsitektur UI/UX, kapankah waktu yang paling hemat biaya untuk mengubah arsitektur navigasi sistem?
   * A. Pada fase implementasi komponen High-Fidelity.
   * B. Saat pengujian QA pada staging environment.
   * C. Pada fase awal evaluasi struktural Low-Fidelity (Lo-Fi).
   * D. Satu minggu setelah rilis ke production environment.

#### Intermediate Level (5 Soal)

6. Apa karakteristik mendasar dari metode evaluasi RITE (Rapid Iterative Testing and Evaluation)?
   * A. Pengujian hanya dilakukan satu kali di akhir siklus sprint dengan 50 orang partisipan.
   * B. Pengujian dilakukan dalam batch kecil (misal N=5), dan perbaikan struktural langsung diimplementasikan seketika pada prototipe begitu pola defek kritis teridentifikasi.
   * C. Mengabaikan data kualitatif dan hanya mengandalkan heatmap pihak ketiga.
   * D. Mengunci prototipe agar tidak boleh dimodifikasi sama sekali sepanjang siklus evaluasi kuartalan berlangsung.

7. Mengapa prototipe berbasis kode (*code-based lo-fi*) sering kali lebih unggul dibanding canvas prototype Figma untuk alur pengisian form kompleks?
   * A. Karena canvas prototype tidak bisa diekspor ke format PDF.
   * B. Karena prototipe berbasis kode dapat mengeksekusi Finite State Machine (FSM), validasi dinamis, dan penangkapan telemetri event presisi secara *native*.
   * C. Karena developer menolak membaca file rancangan desain grafis.
   * D. Karena kode frontend selalu membutuhkan memori lebih sedikit dibanding file Figma.

8. Dalam instrumentasi wireframe, sebuah klik dikategorikan sebagai *Dead Click* atau *Misclick* apabila:
   * A. Terjadi pada elemen HTML `<button>` yang sedang disabled.
   * B. Pengguna melakukan klik ganda (*double click*) pada teks paragraf biasa.
   * C. Klik mendarat pada area non-interaktif atau ruang kosong yang tidak memicu mutasi state atau tindakan sistemik apa pun.
   * D. Klik dilakukan menggunakan peripheral mouse nirkabel.

9. Bagaimana strategi terbaik menangani *State Overflow* pada tahap perancangan wireframe tabel data enterprise?
   * A. Menyembunyikan sisa teks menggunakan property `display: none`.
   * B. Merancang batasan ekspansi layout, pemotongan string (*truncation*) dengan mekanisme hover tooltip, atau split horizontal scroll yang tervalidasi.
   * C. Memaksa pengguna mengecilkan zoom level browser agar seluruh kolom muat.
   * D. Menghapus kolom tabel hingga menyisakan maksimal 3 kolom data saja.

10. Apa keuntungan arsitektural dari mendefinisikan Finite State Machine (FSM) sebelum membuat layar wireframe?
    * A. Menghilangkan kebutuhan untuk berkolaborasi dengan Product Manager.
    * B. Mengidentifikasi seluruh status transisi, unhandled states, error recovery paths, dan mencegah *dead-end interaction* sebelum aset visual digambar.
    * C. Memastikan seluruh komponen menggunakan warna hex `#000000`.
    * D. Mempercepat proses kompilasi binary aplikasi pada server CI/CD.

#### Production Scenario Cases (3 Soal)

11. **Skenario Kasus 1**:  
    Tim Anda sedang menguji Lo-Fi prototipe dari modul konfigurasi izin akses (*RBAC Matrix*) berskala ribuan akun enterprise. Selama pengujian unmoderated dengan 10 administrator TI, data telemetri menunjukkan:
    *   Rata-rata Task Completion Time: Sangat Tinggi (9,4 menit dari target 2 menit).
    *   Misclick Index: 42% terkonsentrasi di sekitar checkbox permission matrix.
    *   TTI: Rendah (kurang dari 3 detik).  
    *Analisis arsitektural mana yang paling tepat dan tindakan korektif apa yang harus diambil pada siklus RITE berikutnya?*
    * A. TTI rendah membuktikan layout sudah sempurna; masalah ada pada lambatnya koneksi internet partisipan, abaikan hasil pengujian.
    * B. Pengguna tahu apa yang ingin dilakukan (TTI cepat), tetapi struktur checkbox grid terlalu padat atau membingungkan secara spasial (Misclick tinggi); refactor wireframe ke model *Batch Role Assignment* atau pencarian prediktif berorientasi entitas sebelum melangkah ke Hi-Fi.
    * C. Ganti font antarmuka menjadi Comic Sans untuk meningkatkan keterbacaan label izin akun.
    * D. Ubah checkbox matrix menjadi komponen multi-level drop down tersembunyi di dalam modal pop-up bertingkat.

12. **Skenario Kasus 2**:  
    Dalam pengujian wireframe aplikasi mobile logistik lapangan (*courier tracking*), partisipan lanjut usia sering gagal menyelesaikan tugas pelaporan pengiriman barang rusak karena mengabaikan banner error validasi di bagian atas layar. Mengingat protokol greybox melarang penggunaan warna peringatan merah menyala untuk menghindari bias estetika, bagaimana Anda menyelesaikan masalah visibilitas error ini secara arsitektural?
    * A. Melanggar aturan greybox dan mewarnai seluruh layar menjadi merah berkedip.
    * B. Mengubah arsitektur interaksi dari validasi pasif pasca-submit menjadi validasi kontekstual *inline-block* yang langsung mengunci field bermasalah dan mengarahkan fokus layar (*auto-focus + scroll anchor*) ke titik kegagalan secara deterministik.
    * C. Menambahkan audio alarm bernada keras saat terjadi validasi gagal.
    * D. Menghapus validasi sistem agar pengguna tidak pernah menemukan state error lagi.

13. **Skenario Kasus 3**:  
    Manajemen meminta tim UX untuk segera melompati fase evaluasi Lo-Fi Wireframe dan langsung mendesain visual High-Fidelity beresolusi penuh di Figma agar bisa segera dipresentasikan ke dewan direksi. Sistem yang dibangun adalah core banking dengan dependensi alur transaksi 7 langkah. Berdasarkan prinsip arsitektur produksi modern, apa risiko teknis dan bisnis terbesar jika permintaan ini dipenuhi tanpa mitigasi?
    * A. Tim desainer akan kehabisan lisensi plugin Figma pihak ketiga.
    * B. Terperangkap dalam *Aesthetic-Usability Effect*: Dewan direksi menyetujui visual antarmuka yang tampak rapi, namun saat diimplementasikan ke frontend engineering ditemukan inkonsistensi penanganan error state dan dependensi alur transaksi, yang memicu refactoring kode frontend berskala masif dengan estimasi biaya membengkak hingga 30x lipat.
    * C. Server database PostgreSQL akan mengalami *out of memory* akibat ketiadaan wireframe.
    * D. Waktu deployment pipeline CI/CD GitHub Actions akan melambat secara signifikan.

---

### Kunci Jawaban Quiz

#### Basic Level
1.  **B** — Aesthetic-Usability Effect menutupi masalah struktural melalui bias visual positif.
2.  **C** — Greybox kit secara sengaja membuang elemen dekorasi demi objektivitas arsitektur.
3.  **B** — TTI mengukur latensi kognitif pengguna sebelum mengambil tindakan pertama.
4.  **C** — Data sintetis realistis mencerminkan kondisi operasional sesungguhnya tanpa memicu distraksi.
5.  **C** — Memperbaiki defek pada fase Lo-Fi bernilai 1x dalam kurva biaya rework Boehm.

#### Intermediate Level
6.  **B** — RITE berbasis siklus batch kecil dengan tindakan perbaikan arsitektural seketika.
7.  **B** — Prototipe kode mampu mengeksekusi logika komputasi nyata dan telemetri langsung dari DOM.
8.  **C** — Misclick/Dead click adalah penanda definitif adanya deviasi model mental pengguna terhadap elemen antarmuka.
9.  **B** — Tata letak struktural harus mengantisipasi batas volume data ekstrem sebelum styling dilakukan.
10. **B** — FSM menjamin kelengkapan penanganan seluruh variasi kondisi sistem sejak awal perancangan.

#### Production Scenario Cases
11. **B** — TTI cepat dengan misclick tinggi pada grid menunjukkan niat pengguna terhalang oleh densitas kontrol yang buruk secara ergonomi struktural.
12. **B** — Solusi arsitektural mengandalkan reposisi spasial, auto-focus, dan feedback kontekstual, bukan bergantung pada persepsi warna.
13. **B** — Melewatkan Lo-Fi memicu risiko fatal tersembunyi di balik polesan visual, melipatgandakan UX Cost of Rework saat masuk ke fase rekayasa perangkat lunak.

---

### 16. Summary

1.  **Isolasi Struktural**: Wireframing dan Lo-Fi Prototyping enterprise adalah proses rekayasa arsitektural formal untuk memisahkan tata letak semantik dan interaksi (*Layer 1 & 2*) dari dekorasi estetika visual (*Layer 3*).
2.  **Mitigasi Bias Kognitif**: Penggunaan sistem monokromatik **Greybox** menetralkan fenomena *Aesthetic-Usability Effect*, memastikan pengujian antarmuka hanya mengukur efisiensi navigasi, kejelasan hierarki data, dan ketahanan alur mental pengguna.
3.  **State-Driven Design**: Wireframe modern wajib didasari oleh **Finite State Machine (FSM)** yang secara eksplisit memetakan state *Empty*, *Loading*, *Error*, *Overflow*, dan *Partial Data* untuk mencegah defek logika masuk ke lini produksi frontend.
4.  **Validasi Berbasis Telemetri**: Mengintegrasikan pencatatan metrik obyektif (TTI, Misclick Index, Task Execution Velocity) ke dalam prototipe berbasis kode memungkinkan tim rekayasa memvalidasi hipotesis UX secara empiris matematis, bukan berbasis asumsi opini subjektif.
5.  **Prinsip Efisiensi RITE**: Melalui siklus *Rapid Iterative Testing and Evaluation*, kegagalan struktural diperbaiki secara instan dalam hitungan jam selama proses testing berlangsung, menekan **UX Cost of Rework** sesuai kaidah Hukum Boehm sebelum komitmen implementasi High-Fidelity dimulai.