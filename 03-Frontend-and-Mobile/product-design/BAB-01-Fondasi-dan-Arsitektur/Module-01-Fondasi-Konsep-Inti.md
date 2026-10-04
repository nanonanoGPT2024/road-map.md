# Bab 01: Fondasi Product Design Engineering & Arsitektur Solusi Digital
## Module 01: Paradigma Desain Produk Berbasis Sistem (Systemic Product Design)

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis** masalah bisnis multi-dimensi menggunakan kerangka kerja *First-Principles Problem Framing* dan mengubahnya menjadi spesifikasi fungsional produk.
- **Merancang** arsitektur *Dual-Track Discovery-Delivery* untuk menjamin keselarasan antara eksplorasi validasi nilai (*value risk*) dan implementasi rekayasa teknis (*feasibility risk*).
- **Mengonstruksi** kontrak formal antara desain dan *engineering* menggunakan *Design Tokens* berstandar W3C DTCG (*Design Tokens Community Group*).
- **Mengevaluasi** performa interaksi UI melalui pemodelan *Deterministic State Machine* (Zero, Loading, Partial, Error, Success).
- **Mengukur** dampak arsitektur pengalaman pengguna (*User Experience Architecture*) menggunakan metrik *Heart-to-Funnel Telemetry*.

---

### 2. Concept Overview
Desain Produk (*Product Design*) modern bukan sekadar pembuatan antarmuka visual estetis (*visual decoration*), melainkan rekayasa sistem antarmuka holistik yang mengintegrasikan tiga domain: **Kebutuhan Pengguna (Desirability)**, **Viabilitas Bisnis (Viability)**, dan **Kelayakan Teknis (Feasibility)**. 

Paradigma *Systemic Product Design* memperlakukan desain sebagai abstraksi logika komputasional: setiap elemen visual mewakili status data (*state*), setiap navigasi mewakili transisi status (*state transition*), dan setiap alur interaksi (*user journey*) merupakan optimasi dari algoritma penyelesaian masalah pengguna. 

Perbedaan fundamental antara desain grafis tradisional dan desain produk digital adalah keberadaan **umpan balik real-time (*state-driven feedback loops*)**, **kondisi asinkron (*asynchronous latency*)**, dan **keragaman kapabilitas lingkungan eksekusi (*heterogeneous client runtimes*)**.

---

### 3. Why It Matters
Kegagalan mayoritas inisiatif produk digital bukan terletak pada kegagalan sintaksis kode, melainkan pembangunan artefak perangkat lunak yang salah (*building the wrong thing right*). 

1. **Efisiensi Capital Expenditure (CapEx):** Mengubah kode pada tahap produksi membutuhkan biaya hingga 100x lebih mahal dibandingkan melakukan modifikasi pada tingkat *interactive wireframe* atau kontrak logika antarmuka (*interface contract*).
2. **Eliminasi Ambivalensi Antara Desain dan Rekayasa:** Diskoneksi antara artboard Figma dan basis kode React/Flutter sering memicu *technical and design debt*. Pendekatan sistematis memformalisasikan elemen desain menjadi artefak deterministik (berbasis JSON/AST).
3. **Optimasi Waktu Menuju Pasar (*Time-to-Value*):** Dengan mendefinisikan komponen terisolasi, logika validasi sisi klien (*optimistic UI*), dan penanganan galat terstandarisasi, tim rekayasa dapat melakukan integrasi API tanpa interpretasi ambigu.

---

### 4. What It Is
Secara formal, **Product Design** dalam ekosistem rekayasa perangkat lunak adalah:

> *Disiplin rekayasa arsitektural yang bertugas mendefinisikan batas sistem antarmuka (*interface boundaries*), hierarki informasi (*information architecture*), affordance interaksi, dan alur konversi melalui pendekatan deterministik berbasis data dan kapabilitas teknis.*

#### Komponen Inti:
- **Problem Framing Engine:** Dekonstruksi domain masalah (Jobs to be Done / JTBD).
- **Information Architecture (IA):** Struktur ontologi, taksonomi, dan peta hubungan entitas data dalam konteks navigasi pengguna.
- **Interaction Contract:** Spesifikasi transisi status UI (*UI State Machine*) yang independen dari kerangka kerja frontend (*framework-agnostic*).
- **Design Systems & Tokenomics:** Sumber kebenaran tunggal (*Single Source of Truth*) yang mendefinisikan nilai semantik (warna, elevasi, tipografi, grid) yang dapat dikompilasi secara otomatis ke berbagai target platform (CSS, iOS Swift, Android Compose).

#### Batasan Sistem:
Product Design **tidak** mencakup:
- Strategi *marketing campaign* atau akuisisi iklan berbayar (kecuali konversi alur *landing page*).
- Implementasi internal algoritma backend (*database schema tuning*, *distributed locking*), meskipun desainer produk harus memahami latensi dan batasan integritas data jaringan.

---

### 5. How It Works
Siklus hidup perancangan produk beroperasi di atas pola *Dual-Track Agile*, yang memisahkan dan mensinkronisasikan jalur penemuan (*Discovery Track*) dan pengiriman (*Delivery Track*).

```
[ Problem Space ] ----------> [ Solution Space ] ----------> [ Production Run ]
 Discovery Track               Contract Definition             Delivery Track
  - User Research               - Design Tokens (JSON)          - React/Compose Engine
  - JTBD Vectorization          - State Machine (XState)        - API Integration
  - Prototype Validation        - WCAG Audit Protocol           - Telemetry & Analytics
```

#### Alur Eksekusi Langkah Demi Langkah:
1. **Divergence (Problem Discovery):** Pengumpulan data kualitatif dan telemetri kuantitatif untuk mengisolasi titik hambatan (*friction point*) pengguna.
2. **Convergence (Problem Framing):** Transformasi temuan menjadi pernyataan masalah terkuantisasi:
   $$\text{Opportunity} = \text{Importance} + \max(\text{Importance} - \text{Satisfaction}, 0)$$
3. **Artifact Mapping (Interaction Design):** Pemetaan *mental model* pengguna ke *system model*. Pembuatan struktur pohon navigasi dan diagram aliran status (*state-flow diagram*).
4. **Contract Formalization (Design Tokenization):** Ekstraksi parameter visual ke dalam format terstruktur (JSON).
5. **Deterministic State Modeling:** Penentuan visualisasi UI pada lima status baku (Empty, Loading, Success, Partial Error, Fatal Failure).
6. **Delivery & Instrumentation:** Validasi otomatis melalui pengujian regresi visual (*visual regression test*) dan penyematan skema telemetri analitik (*event tracking payload*).

---

### 6. ASCII Architecture / Mental Model Diagram

```
+---------------------------------------------------------------------------------------+
|                               PRODUCT DESIGN SUBSYSTEM                                |
+---------------------------------------------------------------------------------------+
                                           |
    +--------------------------------------+-------------------------------------+
    |                                                                            |
    v                                                                            v
[ DISCOVERY SUBSYSTEM ]                                              [ DESIGN SYSTEM FOUNDATION ]
+-----------------------------------+                                +--------------------------+
| - JTBD Matrix                     |                                | - W3C Design Tokens JSON |
| - Opportunity Solution Tree (OST) |                                | - Typography Scale       |
| - Heuristic Evaluation Engine     |                                | - Semantic Color Palette |
+-----------------------------------+                                +--------------------------+
    |                                                                            |
    | (User Context & Validated Problem)                                         | (Tokens Compiler)
    v                                                                            v
+---------------------------------------------------------------------------------------+
| INTERACTION CONTRACT LAYER                                                            |
| +-----------------------------------------------------------------------------------+ |
| | UI Finite State Machine (FSM)                                                     | |
| |                                                                                   | |
| |   [IDLE] ===(FETCH_DATA)===> [LOADING]                                            | |
| |                                 |                                                 | |
| |                  +--------------+--------------+                                  | |
| |                  v                             v                                  | |
| |     [RESOLVED: SUCCESS]               [REJECTED: ERROR]                           | |
| |        |             |                         |                                  | |
| |        v             v                         v                                  | |
| |  (Data Present)  (Zero Data)          (Recoverable vs Fatal)                      | |
| +-----------------------------------------------------------------------------------+ |
+---------------------------------------------------------------------------------------+
                                           |
                                           v
+---------------------------------------------------------------------------------------+
| RUNTIME PARITY BRIDGE (Figma UI <---> Target Client Codebases)                        |
| - React Web Engine (Tailwind / CSS-in-JS)                                             |
| - Android Compose Declarative UI                                                      |
| - iOS SwiftUI Declarative UI                                                          |
| - Telemetry & Event Payload Ingestion (Mixpanel, Datadog RUM, PostHog)                |
+---------------------------------------------------------------------------------------+
```

---

### 7. Minimal Simple Example
Berikut adalah representasi minimal kontrak desain-ke-rekayasa berupa spesifikasi *Design Token* untuk komponen atomik antarmuka (tombol interaktif) yang mematuhi standar JSON W3C DTCG:

```json
{
  "component": {
    "actionButton": {
      "base": {
        "paddingX": {
          "$value": "16px",
          "$type": "dimension"
        },
        "paddingY": {
          "$value": "12px",
          "$type": "dimension"
        },
        "borderRadius": {
          "$value": "8px",
          "$type": "dimension"
        }
      },
      "color": {
        "background": {
          "default": { "$value": "#0F172A", "$type": "color" },
          "hover": { "$value": "#1E293B", "$type": "color" },
          "disabled": { "$value": "#94A3B8", "$type": "color" }
        },
        "label": {
          "default": { "$value": "#F8FAFC", "$type": "color" }
        }
      }
    }
  }
}
```

Implementasi pemetaan ke komponen antarmuka fungsional:

```typescript
// button.contract.ts
export type ButtonIntent = 'default' | 'hover' | 'disabled';

export interface ActionButtonSpec {
  padding: { x: string; y: string };
  borderRadius: string;
  backgroundColor: Record<ButtonIntent, string>;
  textColor: string;
}

// Konsumsi token di level view
export const actionButtonStyles = (intent: ButtonIntent): string => `
  padding: 12px 16px;
  border-radius: 8px;
  background-color: ${
    intent === 'disabled' ? '#94A3B8' : intent === 'hover' ? '#1E293B' : '#0F172A'
  };
  color: #F8FAFC;
  cursor: ${intent === 'disabled' ? 'not-allowed' : 'pointer'};
  transition: background-color 150ms cubic-bezier(0.4, 0, 0.2, 1);
`;
```

---

### 8. Practical Real-World Implementation
Mari bangun arsitektur sistem antarmuka untuk komponen kritis transaksi: **Withdrawal Verification Gate**. Komponen ini harus menangani latensi jaringan, validasi batas nominal, dan kegagalan asinkron tanpa membiarkan visual UI berada dalam kondisi tidak terdefinisi (*undefined state*).

#### A. Mesin Status Deterministik Komponen (Core Interaction Logic)
```typescript
// stateMachine.ts
export type MachineState = 
  | 'IDLE' 
  | 'VALIDATING' 
  | 'SUBMITTING' 
  | 'SUCCESS' 
  | 'NETWORK_ERROR' 
  | 'INSUFFICIENT_FUNDS';

export type MachineEvent = 
  | { type: 'CHANGE_AMOUNT'; amount: number }
  | { type: 'SUBMIT' }
  | { type: 'API_RESOLVE' }
  | { type: 'API_REJECT'; reason: 'NETWORK' | 'INSUFFICIENT_BALANCE' }
  | { type: 'RETRY' };

export interface MachineContext {
  amount: number;
  availableBalance: number;
  errorMessage?: string;
}

export function withdrawalReducer(
  state: MachineState, 
  event: MachineEvent, 
  context: MachineContext
): { nextState: MachineState; nextContext: MachineContext } {
  switch (state) {
    case 'IDLE':
      if (event.type === 'CHANGE_AMOUNT') {
        return {
          nextState: 'IDLE',
          nextContext: { ...context, amount: event.amount }
        };
      }
      if (event.type === 'SUBMIT') {
        if (context.amount > context.availableBalance) {
          return {
            nextState: 'INSUFFICIENT_FUNDS',
            nextContext: { ...context, errorMessage: 'Saldo akun tidak mencukupi.' }
          };
        }
        if (context.amount <= 0) {
          return {
            nextState: 'IDLE',
            nextContext: { ...context, errorMessage: 'Nominal penarikan harus lebih dari 0.' }
          };
        }
        return { nextState: 'SUBMITTING', nextContext: context };
      }
      return { nextState: state, nextContext: context };

    case 'SUBMITTING':
      if (event.type === 'API_RESOLVE') {
        return { nextState: 'SUCCESS', nextContext: { ...context, errorMessage: undefined } };
      }
      if (event.type === 'API_REJECT') {
        if (event.reason === 'INSUFFICIENT_BALANCE') {
          return {
            nextState: 'INSUFFICIENT_FUNDS',
            nextContext: { ...context, errorMessage: 'Saldo akun telah berubah atau tidak mencukupi.' }
          };
        }
        return {
          nextState: 'NETWORK_ERROR',
          nextContext: { ...context, errorMessage: 'Koneksi terputus. Silakan coba lagi.' }
        };
      }
      return { nextState: state, nextContext: context };

    case 'NETWORK_ERROR':
    case 'INSUFFICIENT_FUNDS':
      if (event.type === 'RETRY' || event.type === 'CHANGE_AMOUNT') {
        return { nextState: 'IDLE', nextContext: { ...context, errorMessage: undefined } };
      }
      return { nextState: state, nextContext: context };

    case 'SUCCESS':
      return { nextState: state, nextContext: context }; // Terminal state

    default:
      return { nextState: state, nextContext: context };
  }
}
```

#### B. Deklarasi Tampilan Komponen Sesuai Status Antarmuka (Production React/TS Component)
```tsx
// WithdrawalGate.tsx
import React, { useReducer } from 'react';
import { withdrawalReducer, MachineState, MachineContext } from './stateMachine';

interface WithdrawalGateProps {
  initialBalance: number;
  onExecuteWithdrawal: (amount: number) => Promise<void>;
  onTelemetryEvent: (eventName: string, payload: Record<string, unknown>) => void;
}

export const WithdrawalGate: React.FC<WithdrawalGateProps> = ({
  initialBalance,
  onExecuteWithdrawal,
  onTelemetryEvent
}) => {
  const [context, setContext] = React.useState<MachineContext>({
    amount: 0,
    availableBalance: initialBalance,
  });
  const [currentState, setCurrentState] = React.useState<MachineState>('IDLE');

  const dispatch = (action: Parameters<typeof withdrawalReducer>[1]) => {
    const { nextState, nextContext } = withdrawalReducer(currentState, action, context);
    setCurrentState(nextState);
    setContext(nextContext);

    // Logging transisi UI ke pipeline analitik
    onTelemetryEvent('ui_state_transition', {
      from: currentState,
      to: nextState,
      amount: nextContext.amount
    });
  };

  const handleAction = async () => {
    dispatch({ type: 'SUBMIT' });
    if (context.amount > context.availableBalance || context.amount <= 0) {
      return;
    }

    try {
      await onExecuteWithdrawal(context.amount);
      dispatch({ type: 'API_RESOLVE' });
    } catch (err: any) {
      if (err?.code === 'BALANCE_INSUFFICIENT') {
        dispatch({ type: 'API_REJECT', reason: 'INSUFFICIENT_BALANCE' });
      } else {
        dispatch({ type: 'API_REJECT', reason: 'NETWORK' });
      }
    }
  };

  return (
    <div className="w-full max-w-md p-6 bg-slate-900 border border-slate-800 rounded-xl text-slate-100 shadow-2xl">
      <header className="mb-4">
        <h2 className="text-sm font-semibold tracking-wider text-slate-400 uppercase">
          Dompet Kas / Penarikan Dana
        </h2>
        <p className="text-2xl font-bold tracking-tight text-white mt-1">
          Rp {context.availableBalance.toLocaleString('id-ID')}
        </p>
      </header>

      <div className="space-y-4">
        <div>
          <label htmlFor="amount-input" className="block text-xs font-medium text-slate-400 mb-1">
            Nominal yang ditarik (IDR)
          </label>
          <input
            id="amount-input"
            type="number"
            disabled={currentState === 'SUBMITTING' || currentState === 'SUCCESS'}
            value={context.amount || ''}
            onChange={(e) => dispatch({ type: 'CHANGE_AMOUNT', amount: Number(e.target.value) })}
            placeholder="0"
            className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50"
            aria-invalid={currentState === 'INSUFFICIENT_FUNDS' || !!context.errorMessage}
            aria-describedby="amount-feedback"
          />
        </div>

        {/* FEEDBACK STATUS ENGINE */}
        {context.errorMessage && (
          <div 
            id="amount-feedback" 
            role="alert" 
            className="p-3 text-xs rounded-lg bg-rose-950/50 border border-rose-800 text-rose-300"
          >
            {context.errorMessage}
          </div>
        )}

        {currentState === 'SUCCESS' && (
          <div 
            role="status" 
            className="p-3 text-xs rounded-lg bg-emerald-950/50 border border-emerald-800 text-emerald-300"
          >
            Transaksi berhasil dieksekusi. Dana sedang menuju rekening tujuan.
          </div>
        )}

        <button
          onClick={currentState === 'NETWORK_ERROR' ? () => dispatch({ type: 'RETRY' }) : handleAction}
          disabled={currentState === 'SUBMITTING' || currentState === 'SUCCESS'}
          className={`w-full py-3 px-4 font-semibold text-sm rounded-lg transition duration-200 flex items-center justify-center ${
            currentState === 'SUBMITTING'
              ? 'bg-slate-700 cursor-wait text-slate-300'
              : currentState === 'SUCCESS'
              ? 'bg-emerald-600 cursor-default text-white'
              : 'bg-indigo-600 hover:bg-indigo-500 active:scale-[0.98] text-white'
          }`}
        >
          {currentState === 'SUBMITTING' ? (
            <span className="inline-flex items-center gap-2">
              <svg className="animate-spin h-4 w-4 text-white" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
              </svg>
              Memproses...
            </span>
          ) : currentState === 'NETWORK_ERROR' ? (
            'Coba Ulang Transaksi'
          ) : currentState === 'SUCCESS' ? (
            'Transaksi Selesai'
          ) : (
            'Konfirmasi & Tarik'
          )}
        </button>
      </div>
    </div>
  );
};
```

---

### 9. Trade-offs & Comparisons

| Paradigma / Metrik | Perancangan Visual Konvensional (Figma-First Ad-hoc) | Rekayasa Sistem Desain Deterministik (Systemic Product Design) |
| :--- | :--- | :--- |
| **Kecepatan Fase Awal (*Discovery*)** | Cepat; desainer langsung membuat mockup visual tanpa skema ketat. | Lebih lambat; memerlukan dekonstruksi *data ontology* dan definisi token. |
| **Biaya Pemeliharaan (*Maintenance*)** | Sangat Tinggi; rentan inkonsistensi saat basis kode berskala besar (>50 engineer). | Rendah; perubahan variabel disinkronkan secara terprogram melalui Design Tokens. |
| **Penanganan Galat Antarmuka (*Edge Cases*)** | Sering terlewat; hanya fokus pada *Happy Path* (data ideal). | Lengkap; setiap komponen wajib mendefinisikan *State Matrix* (Zero, Error, Stale). |
| **Kesesuaian Desain-Kode (*Parity Gap*)** | Lebar; interpretasi manual dari file desain ke CSS/Markup. | Sangat Sempit; konversi otomatis via token schema dan spesifikasi eksplisit. |
| **Aksesibilitas (WCAG)** | Pasif; diaudit setelah rilis antarmuka ke lingkungan produksi. | Proaktif; rasio kontras warna dan pembaca layar (*screen reader*) divalidasi sejak awal. |

---

### 10. Best Practices & Guidelines

#### Anjuran (DO):
- **Gunakan Semantic Tokenization:** Definisikan token berdasarkan tujuan fungsi, bukan nilai absolut visual. Gunakan `color.background.interactive.hover`, bukan `color.slate.800`.
- **Rancang Berdasarkan Batasan Nyata (*Defensive UI*):** Uji antarmuka menggunakan teks lokal terpanjang (misal: nama bahasa Jerman atau alamat multibaris Indonesia) untuk menguji penataan ruang (*layout breakage*).
- **Pertahankan Rasio Aksesibilitas Minimum:** Pastikan seluruh teks dan elemen kontrol interaktif memenuhi standar kontras WCAG 2.1 AA (minimal 4.5:1 untuk teks normal, 3:1 untuk teks tebal/besar).
- **Petakan Logika Asinkron:** Setiap interaksi dengan backend wajib memvisualisasikan status *Optimistic*, *Pending*, dan *Failed Retry*.

#### Pantangan (DON'T):
- **Jangan Menggunakan Komponen Statis Un-versioned:** Jangan mengekspor aset grafis langsung dari kanvas tanpa mendaftarkannya ke dalam kamus desain terstruktur (*design library registry*).
- **Hindari *Magic Numbers*:** Dilarang meletakkan margin/padding arbitrari seperti `padding: 13px` atau `margin-top: 7px`. Terapkan skala ruang kelipatan 4pt atau 8pt secara rigid.
- **Jangan Mengabaikan Kontrak Kehilangan Fokus Antarmuka (*Focus Trapping*):** Pada dialog modal, jangan biarkan fokus keyboard lolos ke elemen di balik modal.

---

### 11. Anti-patterns to Avoid

#### 1. The Happy Path Mirage
*   **Symptom:** UI tampak elegan pada artboard Figma dengan nama pengguna ringkas ("John Doe") dan foto beresolusi tinggi, namun tampilan rusak saat pengguna riil menggunakan nama 80 karakter tanpa avatar.
*   **Root Cause:** Kegagalan mengisolasi variabilitas struktur data pada fase spesifikasi antarmuka.
*   **Correction:** Wajibkan setiap *screen review* menyertakan pengujian dengan skenario batas: *Empty String*, *Truncation Limits*, *Multi-byte Characters* (emoji/aksara non-Latin), dan *Broken Assets*.

#### 2. Visual-Driven Architecture
*   **Symptom:** Desainer menciptakan komponen kontrol interaktif kustom (misal: custom picker) yang tidak mewarisi atribut semantik HTML native (`<select>` / `<input>`).
*   **Root Cause:** Mengutamakan bentuk estetis di atas pemodelan fungsional dan kapabilitas aksesibilitas.
*   **Correction:** Terapkan prinsip *Semantic-First*. Manfaatkan elemen antarmuka standar (*headless UI libraries* seperti Radix atau React Aria) dan bungkus dengan lapisan gaya visual sesuai sistem token.

#### 3. Ghost Loading Paradox
*   **Symptom:** Komponen menampilkan animasi berkedip (*skeleton loader*) yang kemudian digantikan oleh *spinner*, lalu berpindah layout saat data tiba (*Cumulative Layout Shift* tinggi).
*   **Root Cause:** Ketiadaan kontrak dimensi layout sebelum data diunduh secara asinkron.
*   **Correction:** Dimensi skeleton harus mencerminkan ukuran absolut dari elemen akhir yang akan dirender menggunakan aturan `min-height` dan `aspect-ratio`.

---

### 12. Edge Cases & Failure Modes

Setiap interaksi antarmuka harus memiliki prosedur pemulihan kegagalan (*failure recovery pathway*):

1. **Jaringan Lambat Berkelanjutan (*High Latency / Offline Transition*):**
   * *Mode Kegagalan:* Pengguna menekan tombol berkali-kali karena tidak melihat perubahan visual seketika.
   * *Mitigasi Desain:* Terapkan *instant debouncing*, matikan tombol segera setelah klik pertama, dan render *optimistic feedback indicator* dalam durasi < 100ms.

2. **Truncation & Text Expansion Discrepancy:**
   * *Mode Kegagalan:* Teks deskripsi memotong tombol aksi (*action button*) sehingga tertutup atau keluar dari *viewport* pada perangkat mobile kecil (layar 320px).
   * *Mitigasi Desain:* Gunakan teknik *Flexbox wrapping* dengan urutan fallback: teks memotong dengan elipsis (*ellipsis*) di tengah, bukan memotong tombol aksi.

3. **Komputasi Desimal Titik Mengambang Antarmuka (*Floating Point Input*):**
   * *Mode Kegagalan:* Pengguna memasukkan tanda koma `,` atau titik `.` saat memasukkan angka desimal, menyebabkan parsing NaN (*Not a Number*).
   * *Mitigasi Desain:* Sanitasi input secara *real-time* sesuai konfigurasi regional pengguna (*locale-aware parsing*).

---

### 13. Performance, Accessibility & Resilience Considerations

#### A. Web Vitals & Runtime Constraints
- **CLS (Cumulative Layout Shift):** Wajib < 0.1. Hindari menyuntikkan elemen banner promosi atau pesan galat dinamis di atas elemen yang sedang dibaca pengguna. Gunakan reservasi ruang absolut (*space reservation*).
- **INP (Interaction to Next Paint):** Wajib < 200ms. Hindari animasi visual berbasis CSS yang memicu *Layout Reflow* (seperti menganimasikan `width`, `height`, `top`). Batasi manipulasi animasi hanya pada properti GPU-accelerated: `transform` dan `opacity`.

#### B. Standar Aksesibilitas (WCAG 2.1 Level AA)
- Seluruh elemen yang dapat diklik (*touch targets*) harus memiliki luas area minimum **48 x 48 CSS pixels** pada perangkat layar sentuh, terlepas dari ukuran visual ikon di dalamnya.
- Hubungan visual hierarki harus tercermin pada DOM Tree: jangan pernah menggunakan `<div>` yang diberi handler `onClick` untuk menggantikan `<button>`.

```html
<!-- Contoh Benar: Accessible Touch Target Wrapper -->
<button 
  type="button"
  aria-label="Tutup dialog transaksi"
  className="relative p-2 text-slate-400 hover:text-white"
>
  <!-- Visual Icon: 16x16 px -->
  <svg className="w-4 h-4" aria-hidden="true">...</svg>
  <!-- Absolute Inset: Menjamin area sentuh memenuhi 48x48 px -->
  <span className="absolute -inset-2 block" aria-hidden="true" />
</button>
```

---

### 14. Observability, Analytics & Telemetry

Desain produk yang tidak dapat diobservasi adalah desain yang buta terhadap kegagalan operasional. Setiap alur antarmuka wajib mengintegrasikan skema pelacakan terstruktur.

#### Skema Kontrak Payload Telemetri (JSON Schema)
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "UIInteractionTelemetryPayload",
  "type": "object",
  "properties": {
    "event_name": { "type": "string", "enum": ["interaction_click", "interaction_view", "state_transition", "validation_failed"] },
    "surface": { "type": "string", "example": "withdrawal_modal" },
    "component_id": { "type": "string", "example": "confirm_withdrawal_btn" },
    "source_state": { "type": "string", "example": "IDLE" },
    "destination_state": { "type": "string", "example": "SUBMITTING" },
    "duration_ms": { "type": "number", "description": "Waktu interaksi sejak komponen dirender hingga aksi dieksekusi" },
    "metadata": {
      "type": "object",
      "properties": {
        "viewport_width": { "type": "integer" },
        "has_error": { "type": "boolean" },
        "error_code": { "type": "string" }
      },
      "required": ["viewport_width", "has_error"]
    }
  },
  "required": ["event_name", "surface", "component_id", "source_state", "destination_state", "metadata"]
}
```

Metrik inti yang wajib dipantau melalui dasbor analitik produk:
1. **Drop-off Velocity:** Tingkat penurunan pengguna pada setiap transisi antarmuka.
2. **Error Recovery Rate:** Persentase pengguna yang berhasil menyelesaikan transaksi setelah menemui status kesalahan (*error state*).
3. **Rage Clicks Rate:** Deteksi pengguna yang menekan elemen interaktif > 3 kali dalam jendela waktu 1 detik.

---

### 15. Verification & Testing Guide

Untuk memverifikasi kekokohan desain produk sebelum fase rilis, jalankan protokol pengujian berikut:

#### Visual Regression Testing Test Script (Playwright TypeScript)
```typescript
// tests/visual/withdrawalGate.spec.ts
import { test, expect } from '@playwright/test';

test.describe('WithdrawalGate Visual & State Verification', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/components/preview/withdrawal-gate');
  });

  test('Harus merender status default (IDLE) secara akurat tanpa pergeseran layout', async ({ page }) => {
    const card = page.locator('[data-testid="withdrawal-card"]');
    await expect(card).toBeVisible();
    await expect(card).toHaveScreenshot('withdrawal-gate-idle.png', {
      maxDiffPixelRatio: 0.01 // Ambang toleransi visual 1%
    });
  });

  test('Harus merender visual status INSUFFICIENT_FUNDS saat input melebihi saldo', async ({ page }) => {
    const input = page.locator('#amount-input');
    const submitBtn = page.getByRole('button', { name: /Konfirmasi & Tarik/i });

    // Simulasi pengetikan input melebihi batas saldo (Rp 10.000.000)
    await input.fill('99999999');
    await submitBtn.click();

    const alertBox = page.locator('div[role="alert"]');
    await expect(alertBox).toBeVisible();
    await expect(alertBox).toContainText('Saldo akun tidak mencukupi.');

    // Verifikasi screenshot untuk status galat
    await expect(page.locator('[data-testid="withdrawal-card"]')).toHaveScreenshot('withdrawal-gate-error.png');
  });
});
```

---

### 16. Step-by-Step Implementation Blueprint

Jika Anda merancang fitur antarmuka baru dari awal, ikuti urutan linear berikut:

1. **Dekonstruksi Alur Data (T-Minus 4 Minggu):**
   * Identifikasi model data backend dan petakan keterbatasan jaringan (payload latency, validasi server).
   * Rumuskan dokumen spesifikasi fungsional antarmuka (*Functional Spec Canvas*).
2. **Perancangan State Machine (T-Minus 3 Minggu):**
   * Definisikan diagram status Finite State Machine (FSM).
   * Petakan kelima status wajib: *Empty*, *Loading*, *Success*, *Partial Error*, *Fatal Error*.
3. **Penyusunan Desain Berbasis Token (T-Minus 2 Minggu):**
   * Rancang antarmuka di Figma menggunakan library terstandarisasi.
   * Gunakan variabel desain yang sinkron dengan nama token di repositori kode (*Design Tokens*).
4. **Pemeriksaan Kontras dan Aksesibilitas (T-Minus 1 Minggu):**
   * Audit rasio kontras menggunakan ekstensi otomatis.
   * Validasi struktur DOM semantik dan uji coba navigasi keyboard penuh (Tab, Shift+Tab, Enter, Escape).
5. **Instrumentasi Telemetri & Sign-off (T-Minus 0 Hari):**
   * Sisipkan skema tracking payload pada event transisi komponen.
   * Tinjau hasil *Visual Regression Testing* dan kunci baseline snapshot.

---

### 17. Production Readiness Checklist

Sebelum menyatakan modul/komponen desain siap diserahkan (*hand-off*) ke pipeline rilis produksi:

- [ ] **State Completeness:** Seluruh status (Empty, Loading, Error, Success, Retry) telah dirancang dan diimplementasikan.
- [ ] **Accessibility (WCAG 2.1 AA):** Rasio kontras teks reguler $\ge$ 4.5:1; teks tebal/skala besar $\ge$ 3:1.
- [ ] **Screen Reader Compatibility:** Semua tombol ikonik memiliki atribut `aria-label`; elemen dinamis memiliki `aria-live` atau `role="alert"`.
- [ ] **Responsive Breakpoints:** Antarmuka telah diuji pada resolusi minimum ekstrem (320px) hingga monitor layar lebar (1440px) tanpa terjadinya *overflow clipping*.
- [ ] **Touch Target Integrity:** Area interaktif layar sentuh minimal 48 x 48 CSS pixels.
- [ ] **Design Tokens Compliance:** Tidak ada kode hex warna atau ukuran spacing *hardcoded* di dalam berkas styling antarmuka.
- [ ] **Telemetry Coverage:** Seluruh aksi konversi pengguna dan transisi kegagalan sistem telah dipasangi instrumen *event tracking*.
- [ ] **Error Handling Communication:** Pesan kegagalan memberikan instruksi pemulihan tindakan (*actionable recovery*), bukan pesan internal server seperti "Error 500: Null Pointer".

---

### 18. Troubleshooting & Diagnostic Guide

#### Masalah 1: Input Antarmuka Terasa Lambat (*Input Lag / Stuttering*)
- **Kemungkinan Akar Masalah:** 
  1. Komponen melakukan kalkulasi berat atau memicu perenderan ulang (*re-rendering*) pohon hierarki komponen yang tidak terkait pada setiap ketukan tuts keyboard (*keystroke*).
  2. Komponen input dijalankan sebagai *uncontrolled component* yang dipaksa melakukan *heavy state synchronization* ke storage global.
- **Langkah Diagnostik:** 
  Buka Chrome DevTools $\rightarrow$ Performance Tab $\rightarrow$ Rekam interaksi pengetikan input. Cari durasi *Long Task* (> 50ms) yang dipicu oleh fungsi rendering.
- **Solusi Rekayasa:** 
  Pindahkan state input ke tingkat lokal terdekat. Gunakan debouncing/throttling pada operasi dispatch ke penyimpanan global atau pemanggilan API.

#### Masalah 2: Tampilan Rusak Saat Terjadi Kesalahan Jaringan Asinkron
- **Kemungkinan Akar Masalah:** 
  Komponen mengasumsikan respons payload API selalu mengembalikan struktur data yang sempurna (*schema assumption mismatch*).
- **Langkah Diagnostik:** 
  Periksa konsol peramban apakah terdapat peringatan galat `TypeError: Cannot read properties of undefined (reading 'map')`.
- **Solusi Rekayasa:** 
  Terapkan pola *Defensive Rendering* menggunakan *Optional Chaining* (`data?.items ?? []`) dan gunakan *Error Boundary* di sekeliling komponen untuk merender UI Fallback yang menyediakan tombol *Try Again*.

---

### 19. Frequently Asked Questions (FAQ)

#### T: Kapan kita harus menggunakan Modal Dialog vs Halaman Navigasi Penuh (*Dedicated Screen*)?
**J:** Gunakan **Modal Dialog** hanya untuk interaksi tugas tunggal yang singkat, fokus, dan tidak memerlukan persistensi URL (misal: konfirmasi pembatalan atau pemilihan opsi sederhana dengan durasi < 30 detik). Gunakan **Dedicated Screen** jika proses memiliki alur multi-langkah (*multi-step flow*), memerlukan ruang kerja yang luas, atau perlu memiliki status URL unik (*deep linking*) yang dapat dibagikan atau di-*refresh* pengguna tanpa kehilangan progres.

#### T: Mengapa kita tidak boleh hanya mengandalkan warna untuk mengomunikasikan kesalahan input (*error state*)?
**J:** Berdasarkan standar aksesibilitas WCAG, mengandalkan warna saja (misal: mengubah border input menjadi merah) mengabaikan pengguna dengan keterbatasan penglihatan warna (*color blindness*). Status galat harus selalu menyertakan indikator ganda: warna, ikon grafis, dan pesan teks eksplisit dengan atribut `role="alert"`.

#### T: Apa perbedaan mendasar antara Skeletal Loading dan Spinner Indicator?
**J:** **Skeletal Loading** digunakan untuk pemuatan awal layout utama guna mengurangi *perceived loading time* dan mencegah *Cumulative Layout Shift* dengan memesan ruang visual sebelumnya. **Spinner Indicator** digunakan untuk aksi transaksi inline berdurasi singkat (< 2 detik) di mana bentuk struktur respons belum diketahui atau saat aksi pengguna sedang memblokir layar interaktif (seperti tombol "Sedang Memproses...").

---

### 20. Hands-on Laboratory / Challenges

#### Deskripsi Tantangan
Rancang dan bangun arsitektur sistem antarmuka untuk komponen **Multi-Currency Converter & Checkout Engine**. Komponen ini bertugas mengonversi saldo, menampilkan biaya transaksi tersembunyi, dan mengonfirmasi eksekusi pembayaran secara aman.

#### Persyaratan Teknis & Kriteria Keberhasilan:
1. **Modelkan Status Antarmuka:** Tuliskan berkas FSM lengkap yang menangani minimal status: `SELECTING_CURRENCY`, `FETCHING_RATE`, `DEBOUNCING_INPUT`, `READY_TO_CHECKOUT`, `PROCESSING_PAYMENT`, `PAYMENT_SUCCESS`, dan `PAYMENT_EXPIRED_TIMEOUT`.
2. **Design Token Mapping:** Sediakan skema JSON mini yang mendefinisikan warna aksen dinamis berdasarkan status transaksi (misal: *amber* untuk pending konversi, *emerald* untuk sukses, *rose* untuk galat batas transaksi).
3. **Penyusunan UI Defensive:** Komponen harus mampu menangani nilai input angka hingga 15 digit tanpa merusak struktur visual layout kontainer (*no visual overflow*).
4. **Audit Aksesibilitas Mandiri:** Seluruh komponen input harus dapat dinavigasi hanya menggunakan tuts keyboard (Tab / Enter / Space) dan lolos validasi rasio kontras 4.5:1.
5. **Kriteria Kelulusan Evaluasi:** Komponen tidak boleh memicu Layout Shift (CLS = 0) saat bertransisi dari status `FETCHING_RATE` ke status rendering nilai final konversi. Kontrak penanganan galat jaringan harus menyediakan tombol coba-ulang eksplisit (*explicit retry mechanism*).