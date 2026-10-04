# Modul 03.01: Pemodelan Perilaku, Sintesis Riset & Service Blueprinting

---

## SEKSI 01 — IDENTITAS MODUL

* **Jalur Kurikulum**: `03-Frontend-and-Mobile`
* **Domain Keilmuan**: UX Engineering, Human-Computer Interaction (HCI), dan Arsitektur Sistem Layanan
* **Kode Modul**: `UX-ENG-0301`
* **Tingkat Kompleksitas**: Tingkat Lanjut (*Advanced*) / Tingkat Staf (*Staff-Level Engineering*)
* **Prasyarat**: 
  * Pemahaman mendalam mengenai siklus hidup pengembangan perangkat lunak (SDLC).
  * Penguasaan TypeScript/JavaScript modern (ESNext) dan pola arsitektur berbasis komponen.
  * Pemahaman fundamental mengenai *State Management*, Web APIs, dan *Event-Driven Architecture*.
  * Teori dasar riset pengguna (*Qualitative/Quantitative Research*, *Affinity Mapping*).
* **Estimasi Waktu Pengerjaan**: 14 - 18 Jam Belajar Mandiri & Implementasi Lab

---

## SEKSI 02 — LEARNING OBJECTIVES

Pada akhir modul ini, peserta didik memiliki kapabilitas terukur untuk:

1. **Menerjemahkan Data Kualitatif Menjadi State Machine Deterministik**: Mengonversi transkrip riset pengguna, rekaman telemetri, dan model mental ke dalam format *Finite State Machine* (FSM) yang matematis dan bebas ambiguitas menggunakan TypeScript dan XState.
2. **Merancang Service Blueprint Multi-Tier**: Mengonstruksi diagram dan struktur data *Service Blueprint* yang memetakan relasi kausal antara interaksi *frontend* (bukti fisik & tindakan pengguna), operasi *frontstage/backstage*, serta layanan komputasi/basis data pendukung (*supporting processes*).
3. **Membangun Runtime Telemetri UX Berbasis Event Driven**: Mengimplementasikan arsitektur pelacakan analitik dan observabilitas UX (*Interaction Telemetry Pipeline*) pada aplikasi klien yang secara langsung memvalidasi hipotesis riset tanpa degradasi performa pada *main thread*.
4. **Mengisolasi dan Memitigasi UX Anti-Patterns**: Mengidentifikasi titik friksi interaksi melalui *Journey Latency Profiling*, *Split-brain state*, dan menangani *failure mode* pada level antarmuka serta orkestrasi *backend*.
5. **Menghubungkan UX Blueprint dengan Event Contract Backend**: Merumuskan kontrak data (*schema/payload*) yang menyinkronkan *line of visibility* dan *line of internal interaction* antara klien web dan sistem terdistribusi.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma: "Antarmuka Bukan Sekadar Kanvas Piksel, Melainkan Proyeksi State Mesin Layanan"

Mayoritas *frontend developer* memandang antarmuka pengguna (UI) sebagai representasi statis dari komponen visual yang merespons aksi klik pengguna dan menampilkan respons JSON dari API. Pendekatan ini rapuh dan memicu munculnya *edge-case hell*—kondisi di mana status UI menjadi tidak konsisten (*split-brain*) akibat latensi jaringan, kegagalan parsial layanan pihak ketiga, atau aksi pengguna di luar skenario ideal (*happy path*).

```
   PARADIGMA TRADISIONAL (RAPUH)
   [ Desain Figma ] ---> [ Komponen UI ] <---> [ REST API / Mutasi State ]
   
   PARADIGMA STAFF-LEVEL UX ENGINEERING (DETERMINISTIK)
   [ Riset Kualitatif ] 
            │
            ▼
   [ Pemodelan Mental & Perilaku ]
            │
            ▼
   [ State Machine / FSM ] ───(Formal Contract)───► [ Service Blueprint ]
            │                                             │
            ▼                                             ▼
   [ Dynamic Client UI Engine ] ◄───(Distributed Events)───► [ Microservices Orchestration ]
```

### Konsep Inti Pemodelan Layanan

1. **The Iceberg of User Experience**: Apa yang dilihat pengguna (*Physical Evidence* & *User Actions*) di layar hanyalah 20% dari total sistem. Kegagalan UX sebesar 80% lainnya terjadi di bawah garis visibilitas (*Line of Visibility*), di mana proses *backstage* gagal merespons dalam batasan waktu persepsi manusia (*Perceptual Latency Thresholds*).
2. **State Transition Rigidity**: Alur pengguna (*User Journey*) bukanlah sekadar diagram panah visual yang longgar. Setiap perpindahan status (*state transition*) harus diperlakukan sebagai fungsi transisi matematis:
   $$\delta: S \times E \rightarrow S'$$
   Artinya: Berada pada status $S$, jika menerima *Event* $E$, sistem **hanya boleh** berpindah ke status $S'$, atau melempar galat eksplisit. Tidak ada status antara (*indeterminate state*).
3. **Sintesis Riset sebagai Reduksi Entropi**: Data kualitatif pengguna mengandung ambiguitas tinggi (*high entropy*). Tugas UX Engineer adalah menyaring data mentah tersebut (*Affinity Diagramming*, *Behavioral Coding*) menjadi *Invariant Constraints* yang dapat dieksekusi oleh mesin kode.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Di bawah ini adalah arsitektur operasional end-to-end yang memetakan keterkaitan langsung antara interaksi pengguna di layar peramban dengan infrastruktur *backstage* enterprise:

```
+====================================================================================================+
|                                    SERVICE BLUEPRINT ARCHITECTURE                                  |
+====================================================================================================+
| LAYER 1: PHYSICAL EVIDENCE (Bukti Fisik / Artefak UI)                                              |
|  [ Push Notification ]       [ Push-to-Pay Form Modal ]        [ Animated Skeleton / Optimistic UI]|
+----------------------------------------------------------------------------------------------------+
                                               │ (Melihat/Merespons)
                                               ▼
+----------------------------------------------------------------------------------------------------+
| LAYER 2: CUSTOMER ACTIONS (Alur Perilaku Pengguna / Client FSM)                                    |
|  [ Terima Notifikasi Tagihan ] ──► [ Klik Tombol "Bayar Cepat" ] ──► [ Konfirmasi Biometrik ]      |
+====================================================================================================+
| ---------------------------------- LINE OF INTERACTION ------------------------------------------- |
+====================================================================================================+
| LAYER 3: FRONTSTAGE ACTIONS (Komponen Frontend / Web Client Engine)                                |
|  - Render Biometric Prompt WebAuthn API                                                            |
|  - Validasi Payload Klien (Zod Schema Validation)                                                  |
|  - Dispatch Telemetry Interaction Event: `PAYMENT_SUBMITTED`                                       |
+====================================================================================================+
| ---------------------------------- LINE OF VISIBILITY -------------------------------------------- |
+====================================================================================================+
| LAYER 4: BACKSTAGE ACTIONS (API Gateway & Backend For Frontend / BFF)                              |
|  - API Gateway: Rate Limiting & Auth Token Decryption                                              |
|  - BFF: Orkestrasi Payload Transaksi                                                               |
|  - Idempotency Key Validation Engine (Redis Lock)                                                  |
+====================================================================================================+
| ------------------------------ LINE OF INTERNAL INTERACTION -------------------------------------- |
+====================================================================================================+
| LAYER 5: SUPPORT PROCESSES (Layanan Inti Terdistribusi & Database)                                 |
|  - Core Banking Transaction Engine (Distributed Ledger)                                            |
|  - Fraud Detection System (ML Event Stream via Apache Kafka)                                       |
|  - SMS/WhatsApp Notification Gateway (Third-Party Provider)                                        |
+====================================================================================================+
| LAYER 6: OBSERVABILITY & TELEMETRY STREAM                                                          |
|  - Web Vitals Tracking (INP, LCP)                                                                  |
|  - Sentry Distributed Tracing (Span ID Propagation)                                                |
|  - OpenTelemetry Collector ──► ClickHouse / Datadog Dashboard                                      |
+====================================================================================================+
```

### Visualisasi Transisi State: Siklus Checkout

```
          [ IDLE ]
              │
              │ USER_CLICK_INITIATE
              ▼
    [ VALIDATING_LOCAL ]
      ├─── Validation Error ───► [ DISPLAY_INLINE_ERRORS ] ──► (Kembali ke IDLE)
      │
      └─── Valid Payload
              ▼
   [ ACQUIRING_BIOMETRIC ]
      ├─── Biometric Reject ───► [ FALLBACK_TO_PIN ]
      │
      └─── Biometric Success
              ▼
   [ DISPATCHING_PAYMENT ] ── (Optimistic Update: UI Berubah ke "Memproses")
              │
              ├─── Timeout (10s) ───► [ RESOLVING_AMBIGUOUS_STATE ] ──► [ POLLING_STATUS ]
              ├─── Server Error ────► [ ROLLBACK_OPTIMISTIC_STATE ] ──► [ DISPLAY_MODAL_ALERT ]
              │
              └─── 200 OK (Payment Settled)
                      ▼
             [ PAYMENT_SUCCESS ]
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

Sebuah Service Blueprint yang siap dieksekusi secara teknis memuat komponen struktural berikut:

### 1. The Five Blueprint Strata

* **Physical Evidence (Bukti Fisik)**: Tangible artifacts yang dialami pancaindra pengguna pada setiap titik kontak (*touchpoint*). Dalam konteks rekayasa web, ini mencakup: *Progress Bar*, URL Address Bar, Email Konfirmasi, *Haptic Feedback*, dan Lembar Faktur PDF.
* **Customer Actions (Tindakan Pengguna)**: Pilihan, keputusan, dan aksi fisik langsung yang dilakukan pengguna (misalnya: *Scroll*, *Long-press*, *Input OTP*, *FaceScan*).
* **Frontstage Technologies (Layanan Tatap Muka)**: Bagian sistem yang langsung berinteraksi dengan pengguna. Diimplementasikan melalui komponen React/Vue/Svelte, Service Workers, Local Storage, dan Web APIs.
* **Backstage Technologies (Layanan Belakang Layar)**: Logika server yang memproses permintaan frontstage tanpa interaksi visual langsung dengan pengguna. Dijalankan oleh BFF (*Backend-for-Frontend*), Microservices internal, worker queue, dan cache memory.
* **Support Processes (Proses Pendukung)**: Layanan pendukung esensial, sering kali mencakup integrasi pihak ketiga (*Payment Gateway*, *KYC Provider*, *Credit Scoring Engine*) dan sistem internal warisan (*Legacy Mainframes*).

### 2. The Interaction & Visibility Boundaries

* **Line of Interaction**: Garis batas langsung antara *Customer Actions* dan *Frontstage Technologies*. Pelanggaran pada titik ini mengakibatkan masalah aksesibilitas dan hambatan interaksi (*input lag*, *unresponsive UI*).
* **Line of Visibility**: Garis krusial yang memisahkan apa yang **bisa** dilihat pengguna dengan proses internal server. Di sinilah optimisme antarmuka (*Optimistic UI*) dioperasikan: antarmuka memproyeksikan keberhasilan status sebelum *Line of Visibility* memberikan konfirmasi aktual.
* **Line of Internal Interaction**: Garis pemisah antara subsistem yang terpapar langsung ke internet (BFF/Gateway) dengan infrastruktur internal tertutup (*Private Core Subnets*).

### 3. Matriks Data Perilaku Pengguna (Behavioral Synthesis Schema)

Untuk mengonversi temuan riset kualitatif menjadi artefak rekayasa, data mentah harus diurai menjadi skema struktural yang mencakup relasi berikut:

$$\text{Behavioral Unit} = \{ U_c, M_m, A_i, \Delta t_{expected}, F_m \}$$

* $U_c$ (*User Context*): Kondisi eksternal pengguna (jaringan 3G, perangkat *low-end*, situasi terburu-buru).
* $M_m$ (*Mental Model*): Persepsi pengguna mengenai cara kerja sistem ("Uang saya langsung terpotong detik itu juga").
* $A_i$ (*Action Intent*): Target komputasi yang ingin dicapai pengguna.
* $\Delta t_{expected}$ (*Expected Latency*): Ambang batas waktu toleransi pengguna sebelum menganggap sistem rusak (*Doherty Threshold* $\approx 400\text{ms}$).
* $F_m$ (*Failure Mitigation*): Alur pemulihan visual bila sistem gagal memenuhi ekspektasi.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Doherty Threshold dan Psikofisika Persepsi Waktu UI

Hukum Doherty (1982) menetapkan bahwa produktivitas pengguna meningkat secara eksponensial ketika interaksi antara komputer dan manusia terjadi dalam waktu kurang dari **400 milidetik**. Ketika latensi jaringan di atas *Line of Visibility* menembus angka ini, beban kognitif (*cognitive load*) melonjak tajam karena fokus pengguna terpecah.

Terdapat tiga batas persepsi waktu manusia dalam rekayasa antarmuka:

1. **0.1 Detik (100ms)**: Batas persepsi instan. Respon terhadap aksi klik (*active-state*, penekanan tombol) harus dirender di bawah 100ms untuk mempertahankan ilusi manipulasi fisik langsung (*Direct Manipulation*). Metrik modern: **Interaction to Next Paint (INP)** harus $\le 200\text{ms}$.
2. **1.0 Detik (1000ms)**: Batas alur berpikir pengguna tidak terganggu. Jika proses membutuhkan durasi antara 0.1 hingga 1.0 detik, transisi halus berupa mikro-animasi atau *spinner* mini harus ditampilkan. Pengguna masih merasa memegang kendali.
3. **10 Detik**: Batas perhatian penuh. Melebihi batas ini, pengguna akan meninggalkan aplikasi atau membuka tab peramban baru. Jika Service Blueprint menunjukkan durasi $t > 10\text{s}$, sistem **wajib** diubah dari arsitektur sinkron (*Request-Response*) menjadi asinkron (*Polling*, *Long-Polling*, atau *Server-Sent Events / SSE*) dengan notifikasi sekunder.

### Finite State Machine (FSM) Formalism untuk UX Stability

Pendekatan manajemen status umum sering menggunakan boolean flags multidimensi:

```typescript
// ANTI-PATTERN: Ledakan Kombinatorik State (Boolean Flags Hell)
interface BadCheckoutState {
  isLoading: boolean;
  isError: boolean;
  isSuccess: boolean;
  isBiometricActive: boolean;
  isRetrying: boolean;
}
// Menghasilkan 2^5 = 32 kemungkinan kombinasi status!
// Termasuk status mustahil: { isLoading: true, isSuccess: true }
```

FSM mereduksi $2^n$ kemungkinan status mustahil menjadi himpunan status terhingga yang valid:

$$M = (S, \Sigma, \delta, s_0, F)$$

* $S$: Himpunan hingga semua status antarmuka yang diizinkan.
* $\Sigma$: Himpunan hingga simbol masukan (*Event* yang dipicu pengguna/sistem).
* $\delta$: Fungsi transisi status ($S \times \Sigma \rightarrow S$).
* $s_0$: Status awal ($s_0 \in S$).
* $F$: Himpunan status terminal/akhir ($F \subseteq S$).

Dengan FSM, bug UI di mana tombol berstatus *loading* namun pesan galat tetap terlihat dapat dieliminasi secara matematis pada tahap kompilasi kode.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi deterministik FSM untuk alur otentikasi biometrik multi-tahap pada transaksi finansial. Implementasi ini menggunakan TypeScript murni tanpa dependensi eksternal, mendemonstrasikan bagaimana model perilaku dieksekusi secara ketat.

```typescript
// ============================================================================
// File: core-ux-machine.ts
// Deskripsi: Mesin Status FSM Berbasis Tipe Deterministik untuk UX Alur Pembayaran
// ============================================================================

export type PaymentState = 
  | { status: 'IDLE' }
  | { status: 'VALIDATING_INPUT'; payload: { amount: number; recipientId: string } }
  | { status: 'AWAITING_BIOMETRICS'; challengeId: string; amount: number }
  | { status: 'FALLBACK_PIN_ENTRY'; amount: number; attemptsLeft: number }
  | { status: 'DISPATCHING_UPSTREAM'; transactionToken: string }
  | { status: 'TRANSACTION_SUCCESS'; receiptId: string }
  | { status: 'TERMINAL_FAILURE'; errorCode: string; errorMessage: string };

export type PaymentEvent =
  | { type: 'INITIATE'; amount: number; recipientId: string }
  | { type: 'VALIDATION_PASSED'; challengeId: string }
  | { type: 'VALIDATION_FAILED'; reason: string }
  | { type: 'BIOMETRIC_SUCCESS'; signature: string }
  | { type: 'BIOMETRIC_FAILED_FALLBACK' }
  | { type: 'PIN_SUBMITTED'; pin: string }
  | { type: 'PIN_FAILED'; remainingAttempts: number }
  | { type: 'NETWORK_SETTLED'; receiptId: string }
  | { type: 'NETWORK_ABORT'; errorCode: string; message: string }
  | { type: 'RESET' };

export class PaymentStateMachine {
  private currentState: PaymentState;
  private readonly listeners: Array<(state: PaymentState) => void> = [];

  constructor(initialState: PaymentState = { status: 'IDLE' }) {
    this.currentState = initialState;
  }

  public getState(): PaymentState {
    return this.currentState;
  }

  public subscribe(listener: (state: PaymentState) => void): () => void {
    this.listeners.push(listener);
    listener(this.currentState);
    return () => {
      const idx = this.listeners.indexOf(listener);
      if (idx !== -1) this.listeners.splice(idx, 1);
    };
  }

  public transition(event: PaymentEvent): void {
    const nextState = this.resolveNextState(this.currentState, event);
    
    // Invariant check: cegah transisi identik yang memicu unnecessary re-renders
    if (JSON.stringify(nextState) === JSON.stringify(this.currentState)) {
      return;
    }

    this.currentState = nextState;
    this.notify();
  }

  private notify(): void {
    for (const listener of this.listeners) {
      listener(this.currentState);
    }
  }

  private resolveNextState(current: PaymentState, event: PaymentEvent): PaymentState {
    switch (current.status) {
      case 'IDLE':
        if (event.type === 'INITIATE') {
          return {
            status: 'VALIDATING_INPUT',
            payload: { amount: event.amount, recipientId: event.recipientId },
          };
        }
        break;

      case 'VALIDATING_INPUT':
        if (event.type === 'VALIDATION_PASSED') {
          return {
            status: 'AWAITING_BIOMETRICS',
            challengeId: event.challengeId,
            amount: current.payload.amount,
          };
        }
        if (event.type === 'VALIDATION_FAILED') {
          return {
            status: 'TERMINAL_FAILURE',
            errorCode: 'INVALID_PAYLOAD',
            errorMessage: event.reason,
          };
        }
        break;

      case 'AWAITING_BIOMETRICS':
        if (event.type === 'BIOMETRIC_SUCCESS') {
          return {
            status: 'DISPATCHING_UPSTREAM',
            transactionToken: event.signature,
          };
        }
        if (event.type === 'BIOMETRIC_FAILED_FALLBACK') {
          return {
            status: 'FALLBACK_PIN_ENTRY',
            amount: current.amount,
            attemptsLeft: 3,
          };
        }
        break;

      case 'FALLBACK_PIN_ENTRY':
        if (event.type === 'PIN_SUBMITTED') {
          return {
            status: 'DISPATCHING_UPSTREAM',
            transactionToken: `pin-auth-${Date.now()}`,
          };
        }
        if (event.type === 'PIN_FAILED') {
          if (event.remainingAttempts <= 0) {
            return {
              status: 'TERMINAL_FAILURE',
              errorCode: 'AUTH_LOCKOUT',
              errorMessage: 'Akun Anda terkunci sementara demi keamanan.',
            };
          }
          return {
            ...current,
            attemptsLeft: event.remainingAttempts,
          };
        }
        break;

      case 'DISPATCHING_UPSTREAM':
        if (event.type === 'NETWORK_SETTLED') {
          return {
            status: 'TRANSACTION_SUCCESS',
            receiptId: event.receiptId,
          };
        }
        if (event.type === 'NETWORK_ABORT') {
          return {
            status: 'TERMINAL_FAILURE',
            errorCode: event.errorCode,
            errorMessage: event.message,
          };
        }
        break;

      case 'TRANSACTION_SUCCESS':
      case 'TERMINAL_FAILURE':
        if (event.type === 'RESET') {
          return { status: 'IDLE' };
        }
        break;
    }

    // Defensive programming: Tangani transisi ilegal secara eksplisit
    console.warn(`[FSM Warning] Transisi ilegal dari status: '${current.status}' dengan event: '${event.type}'`);
    return current;
  }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi arsitektural dari kode di atas:

* **Baris 7–14 (`PaymentState`)**: Menggunakan *Discriminated Unions* TypeScript. Properti `status` berfungsi sebagai penanda diskriminator (*tag*). Setiap cabang status membawa *payload* eksklusif yang relevan. Misalnya, saat berada di status `IDLE`, sistem tidak dapat mengakses objek `receiptId`. Hal ini memvalidasi integritas data pada *compile-time*.
* **Baris 16–26 (`PaymentEvent`)**: Memodelkan seluruh stimulus yang dapat memengaruhi sistem secara deklaratif. Membatasi ruang aksi pengguna dan respons sistem hanya pada kontrak tipe ini.
* **Baris 28–34 (`PaymentStateMachine`)**: Implementasi mandiri dari pola *Observer*. Status disimpan dalam enkapsulasi *private* `currentState` dan hanya bisa dimutasi melalui fungsi transisi formal `transition()`.
* **Baris 48–56 (`transition`)**: 
  * Baris 50 menjalankan evaluasi deterministik menggunakan *pure function* `resolveNextState`.
  * Baris 52–54 melakukan *structural equality checking* untuk menghentikan propagasi event redundan yang berpotensi memicu render ulang (*unnecessary re-renders*) pada UI layer.
* **Baris 63–145 (`resolveNextState`)**: Implementasi tabel transisi formal. Logika bisnis dipetakan secara kaku:
  * Baris 89–95: Menangani *graceful degradation*. Jika otentikasi biometrik WebAuthn gagal (`BIOMETRIC_FAILED_FALLBACK`), sistem beralih ke `FALLBACK_PIN_ENTRY` alih-alih melempar galat fatal ke pengguna.
  * Baris 108–114: Mencegah *brute-force* secara visual dan operasional. Jika `remainingAttempts <= 0`, FSM beralih ke `TERMINAL_FAILURE` yang mengunci input.
  * Baris 140–144: Mengisolasi sistem dari transisi liar (*illegal transitions*). Apabila sebuah event masuk pada saat status tidak mengizinkannya, mutasi ditolak dan status saat ini dipertahankan utuh.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario Skala Enterprise: Sistem Pembayaran QRIS / PayLater "SuperApp Bank Digital"

* **Profil Beban Sistem**: 15 Juta Pengguna Aktif Harian (DAU), 4.500 transaksi per detik (TPS) pada jam sibuk, dengan 35% populasi pengguna berada di jaringan seluler 3G/koneksi tidak stabil.
* **Akar Masalah UX**:
  * Riset kualitatif menunjukkan lonjakan komplain pelanggan sebesar 42% pada alur transaksi kasir fisik. Pengguna menekan tombol "Bayar" berulang kali karena respons UI melebihi 3 detik (*double-charge syndrome*).
  * Tim backend mengalami lonjakan beban transaksi ganda (*race conditions*) akibat aksi klik berulang pada antarmuka pengguna.
  * Ketika koneksi internet pengguna terputus saat uang sudah terpotong di *core banking* tetapi respons gateway belum sampai ke perangkat, aplikasi menampilkan status galat "Gagal Transaksi". Hal ini memicu panik pada pengguna dan meningkatkan beban kerja staf *Customer Experience* (CX).
* **Solusi Terpadu**:
  1. Transformasi alur interaksi frontend menggunakan *Finite State Machine* yang memblokir klik paralel melalui *distributed locking* dan *client-side event gating*.
  2. Perancangan ulang *Service Blueprint* dengan menyisipkan status perantara asinkron: **Ambiguous Pending State** dengan mekanisme rekonsiliasi otomatis menggunakan *Event Telemetry Engine*.
  3. Mengadopsi transaksi dengan *Idempotency Keys* yang dihasilkan pada lapisan klien saat transisi dari *AWAITING_BIOMETRICS* menuju *DISPATCHING_UPSTREAM*.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Implementasi arsitektur produksi menggunakan XState v5 dan pipeline telemetri terintegrasi untuk mengorkestrasi Service Blueprint di atas:

```typescript
// ============================================================================
// File: production-checkout-engine.ts
// Deskripsi: Implementasi Komprehensif State Machine Transaksi Skala Produksi
// ============================================================================

import { createMachine, createActor, assign } from 'xstate';

// ----------------------------------------------------------------------------
// 1. DATA CONTRACTS & INTERFACES
// ----------------------------------------------------------------------------
export interface TransactionTelemetryEvent {
  traceId: string;
  eventType: string;
  timestamp: number;
  durationMs?: number;
  metadata?: Record<string, unknown>;
}

export interface CheckoutContext {
  idempotencyKey: string | null;
  amount: number;
  merchantId: string;
  startTime: number;
  attempts: number;
  receiptId: string | null;
  errorPayload: { code: string; message: string } | null;
}

export type CheckoutMachineEvents =
  | { type: 'USER_SUBMIT'; amount: number; merchantId: string }
  | { type: 'BIOMETRIC_AUTH_SUCCESS'; credentialToken: string }
  | { type: 'BIOMETRIC_AUTH_FAILURE' }
  | { type: 'PIN_ENTERED'; pin: string }
  | { type: 'NETWORK_SUCCESS'; data: { receiptId: string } }
  | { type: 'NETWORK_TIMEOUT' }
  | { type: 'NETWORK_SERVER_ERROR'; code: string; message: string }
  | { type: 'POLL_CONFIRMED'; data: { receiptId: string } }
  | { type: 'POLL_FAILED'; code: string; message: string }
  | { type: 'RETRY' };

// ----------------------------------------------------------------------------
// 2. TELEMETRY AGENT IMPLEMENTATION (OBSERVABILITY)
// ----------------------------------------------------------------------------
class InteractionTelemetrySink {
  private buffer: TransactionTelemetryEvent[] = [];

  public capture(event: TransactionTelemetryEvent): void {
    this.buffer.push(event);
    // Sinkronisasi non-blocking via Beacon API jika didukung lingkungan browser
    if (typeof navigator !== 'undefined' && navigator.sendBeacon) {
      const payload = JSON.stringify(event);
      // navigator.sendBeacon('/telemetry/ux-events', payload);
    }
    console.info(`[TELEMETRY TRACE] ${event.traceId} -> ${event.eventType}`, event);
  }

  public flush(): TransactionTelemetryEvent[] {
    const dumped = [...this.buffer];
    this.buffer = [];
    return dumped;
  }
}

export const telemetrySink = new InteractionTelemetrySink();

// ----------------------------------------------------------------------------
// 3. XSTATE v5 PRODUCTION STATE MACHINE
// ----------------------------------------------------------------------------
export const checkoutMachine = createMachine({
  id: 'checkoutOrchestrator',
  types: {} as {
    context: CheckoutContext;
    events: CheckoutMachineEvents;
  },
  initial: 'idle',
  context: {
    idempotencyKey: null,
    amount: 0,
    merchantId: '',
    startTime: 0,
    attempts: 0,
    receiptId: null,
    errorPayload: null,
  },
  states: {
    idle: {
      on: {
        USER_SUBMIT: {
          target: 'authenticatingBiometrics',
          actions: assign({
            amount: ({ event }) => event.amount,
            merchantId: ({ event }) => event.merchantId,
            idempotencyKey: () => `tx-${crypto.randomUUID()}`,
            startTime: () => performance.now(),
            errorPayload: () => null,
          }),
        },
      },
    },

    authenticatingBiometrics: {
      entry: [
        ({ context }) => {
          telemetrySink.capture({
            traceId: context.idempotencyKey!,
            eventType: 'LINE_OF_INTERACTION_BIOMETRIC_PROMPT',
            timestamp: Date.now(),
          });
        },
      ],
      on: {
        BIOMETRIC_AUTH_SUCCESS: {
          target: 'dispatchingPayment',
        },
        BIOMETRIC_AUTH_FAILURE: {
          target: 'fallbackPinEntry',
        },
      },
    },

    fallbackPinEntry: {
      entry: [
        assign({
          attempts: ({ context }) => context.attempts + 1,
        }),
        ({ context }) => {
          telemetrySink.capture({
            traceId: context.idempotencyKey!,
            eventType: 'UX_FRICTION_FALLBACK_PIN_ENTRY',
            timestamp: Date.now(),
            metadata: { attemptNumber: context.attempts },
          });
        },
      ],
      on: {
        PIN_ENTERED: {
          target: 'dispatchingPayment',
        },
      },
    },

    dispatchingPayment: {
      // Mengaktifkan Optimistic UI & Idempotent Upstream Call
      entry: [
        ({ context }) => {
          telemetrySink.capture({
            traceId: context.idempotencyKey!,
            eventType: 'BACKSTAGE_DISPATCH_INITIATED',
            timestamp: Date.now(),
          });
        },
      ],
      on: {
        NETWORK_SUCCESS: {
          target: 'settledSuccess',
          actions: assign({
            receiptId: ({ event }) => event.data.receiptId,
          }),
        },
        NETWORK_TIMEOUT: {
          // Melindungi dari Split-Brain dengan beralih ke Polling State
          target: 'resolvingAmbiguousState',
        },
        NETWORK_SERVER_ERROR: {
          target: 'terminalFailure',
          actions: assign({
            errorPayload: ({ event }) => ({ code: event.code, message: event.message }),
          }),
        },
      },
    },

    resolvingAmbiguousState: {
      // Kasus Ambigu: Line of Visibility terputus, backend tetap memproses transaksi
      entry: [
        ({ context }) => {
          telemetrySink.capture({
            traceId: context.idempotencyKey!,
            eventType: 'BACKSTAGE_NETWORK_AMBIGUOUS_RECOVERY_STARTED',
            timestamp: Date.now(),
          });
        },
      ],
      on: {
        POLL_CONFIRMED: {
          target: 'settledSuccess',
          actions: assign({
            receiptId: ({ event }) => event.data.receiptId,
          }),
        },
        POLL_FAILED: {
          target: 'terminalFailure',
          actions: assign({
            errorPayload: ({ event }) => ({ code: event.code, message: event.message }),
          }),
        },
      },
    },

    settledSuccess: {
      entry: [
        ({ context }) => {
          const latency = performance.now() - context.startTime;
          telemetrySink.capture({
            traceId: context.idempotencyKey!,
            eventType: 'PHYSICAL_EVIDENCE_SUCCESS_DISPLAYED',
            timestamp: Date.now(),
            durationMs: latency,
          });
        },
      ],
      type: 'final',
    },

    terminalFailure: {
      entry: [
        ({ context }) => {
          telemetrySink.capture({
            traceId: context.idempotencyKey || 'unknown',
            eventType: 'PHYSICAL_EVIDENCE_ERROR_DISPLAYED',
            timestamp: Date.now(),
            metadata: context.errorPayload || {},
          });
        },
      ],
      on: {
        RETRY: {
          target: 'idle',
        },
      },
    },
  },
});

// ----------------------------------------------------------------------------
// 4. HANDS-ON RUNTIME CLIENT INTEGRATION
// ----------------------------------------------------------------------------
export class ProductionCheckoutService {
  private actor = createActor(checkoutMachine);

  constructor() {
    this.actor.start();
  }

  public getSnapshot() {
    return this.actor.getSnapshot();
  }

  public subscribe(callback: () => void) {
    return this.actor.subscribe(callback);
  }

  public async initiateCheckout(amount: number, merchantId: string): Promise<void> {
    this.actor.send({ type: 'USER_SUBMIT', amount, merchantId });

    // Simulasi Biometrics API (WebAuthn Native Interface)
    try {
      const authSuccess = await this.mockWebAuthnChallenge();
      if (authSuccess) {
        this.actor.send({ type: 'BIOMETRIC_AUTH_SUCCESS', credentialToken: 'token-xyz-123' });
        await this.dispatchNetworkTransaction();
      } else {
        this.actor.send({ type: 'BIOMETRIC_AUTH_FAILURE' });
      }
    } catch {
      this.actor.send({ type: 'BIOMETRIC_AUTH_FAILURE' });
    }
  }

  public async submitFallbackPin(pin: string): Promise<void> {
    this.actor.send({ type: 'PIN_ENTERED', pin });
    await this.dispatchNetworkTransaction();
  }

  private async dispatchNetworkTransaction(): Promise<void> {
    const snapshot = this.actor.getSnapshot();
    const { idempotencyKey, amount, merchantId } = snapshot.context;

    const controller = new AbortController();
    const timeoutHandle = setTimeout(() => controller.abort(), 3500); // Batas timeout 3.5 detik

    try {
      // Mensimulasikan pemanggilan API Gateway Backstage
      const response = await this.mockNetworkCall({
        idempotencyKey,
        amount,
        merchantId,
        signal: controller.signal,
      });
      clearTimeout(timeoutHandle);
      this.actor.send