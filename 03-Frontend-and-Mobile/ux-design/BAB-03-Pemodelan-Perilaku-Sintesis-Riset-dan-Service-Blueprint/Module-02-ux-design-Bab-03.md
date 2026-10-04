# Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 03: Pemodelan Perilaku, Sintesis Riset, dan Service Blueprint**  
**Kategori: 03-Frontend-and-Mobile / ux-design**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Mentransformasikan artefak kualitatif riset UX (User Persona, Mental Models, Journey Maps) menjadi model formal berbasis **State Machine (FSM / Statecharts)** dan **Event-Driven Architecture (EDA)** di sisi frontend dan backend.
- Merancang dan mengeksekusi sintesis data riset multi-sumber (telemetri kuantitatif, analisis sentimen NLP, transkrip wawancara) ke dalam pipeline data terstruktur menggunakan skema analitik standar industri.
- Mengonversi **Service Blueprint** lintas fungsional (Frontstage, Backstage, Support Processes) menjadi kontrak arsitektur perangkat lunak konkret: *BFF (Backend-for-Frontend)*, *API Gateway schemas*, *Saga Orchestrations*, dan *Distributed Tracing Context (W3C Trace Context)*.
- Mengidentifikasi titik kegagalan interaksi (*fail-states*, *bottlenecks*, *escalation pathways*) melalui sinkronisasi antara *user touchpoints* dan *system state transitions*.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:
- **Foundational UX Research**: Metodologi kualitatif/kuantitatif, *thematic analysis*, dan penyusunan *Customer Journey Map (CJM)* dasar.
- **Frontend Architecture**: Komponen berbasis *declarative UI* (React/TypeScript), State Management modern, dan siklus hidup komponen.
- **Backend & Distributed Systems Basics**: Konsep REST, GraphQL, WebSocket, arsitektur Microservices, serta *Message Broker* (Kafka/RabbitMQ).
- **Format Data & Validasi**: JSON Schema, Protocol Buffers, Zod / TypeBox.

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Formalisasi Pemodelan Perilaku (Behavioral Modeling via Statecharts)

Pendekatan konvensional UX sering kali merepresentasikan alur pengguna sebagai diagram linear atau diagram alir (*flowchart*) statis. Pada sistem enterprise, representasi ini gagal menangkap kondisi riil seperti: *network degradation*, *race conditions*, *concurrent multi-tab operations*, dan *asynchronous human-in-the-loop approvals*.

Untuk menjembatani UX Design dan Software Engineering, pemodelan perilaku diformalkan menggunakan **Harel Statecharts** (ekstensi dari *Deterministic Finite Automata*). Model ini memetakan:
- **States ($S$)**: Kondisi mental/persepsi pengguna yang terikat langsung ke status visual aplikasi (misal: `Idle`, `Authenticating`, `ReviewingKYC`, `DegradedState`).
- **Events ($E$)**: Aksi pengguna (*intent*), respons jaringan, atau pembaruan latar belakang (*telemetry tick*, push notification).
- **Transitions ($\delta: S \times E \to S$)**: Perpindahan deterministik antar state dengan *guard conditions*.
- **Actions/Effects**: Efek samping seperti logging ke analytics engine, triggering distributed trace, atau mutasi state lokal.

```
       [User Intent: Submit KYC] 
                   │
                   ▼
┌────────────────────────────────────────────────────────┐
│ State: DRAFTING                                        │
│   Entry: Render Form, Pull Draft from IndexedDB        │
└──────────────────┬─────────────────────────────────────┘
                   │ Event: SUBMIT_CLICKED
                   ▼
┌────────────────────────────────────────────────────────┐
│ State: VALIDATING_CLIENT_SIDE                         │
│   Guard: isValidIdentityDocument()                     │
└───┬────────────────────────────────────────────────┬───┘
    │ [Valid]                                        │ [Invalid]
    ▼                                                ▼
┌───────────────────────────────┐  ┌────────────────────────────────────┐
│ State: SUBMITTING_TO_GATEWAY  │  │ State: DISPLAYING_INLINE_ERRORS    │
│   Context: correlation_id     │  │   Telemetry: logValidationDropOff │
└───────────────────────────────┘  └────────────────────────────────────┘
```

### 3.2 Service Blueprint sebagai Kontrak Rekayasa Sistem

Service Blueprint enterprise bukan sekadar kanvas visual di Miro/Figma, melainkan **arsitektur orkestrasi sosioteknikal**. Service Blueprint mendefinisikan 5 lapisan struktural:

1. **Physical / Digital Evidence**: Komponen UI, push notifications, email konfirmasi, SMS OTP, struk digital.
2. **Customer Actions (Frontstage User Flow)**: Interaksi langsung pengguna terhadap antarmuka.
3. **Frontstage Touchpoints (Onstage Contact)**: UI Layer, BFF (Backend-for-Frontend), Edge Worker yang melayani request secara synchronous.
4. **Backstage Interactions**: Layanan Microservices internal, asynchronous worker queues, database operations yang tidak langsung terlihat oleh pengguna tetapi esensial terhadap *request-reply cycle*.
5. **Support Processes**: Vendor pihak ketiga (e.g., Identity Verification Provider, Payment Gateway, Fraud Engine, Core Banking, manual verification dashboard).

Antara lapisan 2 dan 3 terdapat **Line of Interaction**; antara lapisan 3 dan 4 terdapat **Line of Visibility**; dan antara lapisan 4 dan 5 terdapat **Line of Internal Interaction**.

```
+-------------------------------------------------------------------------+
| PHYSICAL EVIDENCE: Web Dashboard, OTP Push Notification, Email Notif    |
+=========================================================================+
| CUSTOMER ACTIONS: Klik "Ajukan Pinjaman", Input Nominal, Scan KTP       |
+~~~~~~~~~~~~~~~~~~~~~~~~ Line of Interaction ~~~~~~~~~~~~~~~~~~~~~~~~~~~~+
| FRONTSTAGE (BFF): Next.js Server Action / GraphQL Mutation              |
|                   Session Validation, Telemetry Ingestion               |
+------------------------ Line of Visibility ----------------------------+
| BACKSTAGE: Loan Origination Service (Spring Boot), Credit Scoring Engine|
|            Event Broker (Apache Kafka), PostgreSQL Datastore            |
+------------------------ Line of Internal Interaction -------------------+
| SUPPORT PROCESSES: ASLI RI (KYC API), Dukcapil Connector,               |
|                    Manual Underwriter Risk Dashboard                    |
+-------------------------------------------------------------------------+
```

### 3.3 Research Synthesis Data Pipeline: Telemetry & Qualitative Ingestion

Proses sintesis riset modern mengintegrasikan sinyal kualitatif (*unstructured data*) dan telemetri kuantitatif (*time-series event stream*):

1. **Event Capture Layer**: Pustaka telemetri sisi klien mengumpulkan event *behavioral* (misal: *dwell time*, *rage clicks*, *form interaction latency*, *scroll depth*) dengan menyuntikkan `traceparent` (W3C Trace Context).
2. **Ingestion & Stream Processing**: Event dikirim ke ingestion gateway (e.g., Kafka / Snowplow), dipisahkan menjadi:
   - *Cold Path*: Data lake untuk aggregasi cohort, pemetaan retention matrix, dan segmentasi mental model berbasis unsupervised clustering (K-Means/DBSCAN).
   - *Hot Path*: Real-time stream analytics (Apache Flink) untuk mendeteksi *UX anomalies* (e.g., lonjakan *validation error rate* pada input field tertentu dalam rentang 5 menit).
3. **Qualitative-Quantitative Correlation**: Hasil transkrip wawancara dan komplain pengguna (diekstraksi via LLM semantic embeddings) dipetakan terhadap distributed trace ID untuk merekonstruksi exact state machine sistem saat kegagalan user experience terjadi.

---

## 4. Why & What

### Mengapa Pendekatan Tradisional Gagal?
- **Silo Desain vs Implementasi**: Desainer memproduksi artefak statis (Figma) yang mengasumsikan sistem selalu beroperasi pada kondisi jaringan ideal (*happy path*). Ketika diterapkan pada sistem terdistribusi riil dengan latensi, timeout, dan partial failure, UI menjadi tidak terprediksi (*undefined states*).
- **Disparitas Bahasa**: Product Designer berbicara dalam terminologi "Empathy Map" dan "Pain Points", sementara Software Engineer berbicara dalam "Latency p99", "Idempotency", dan "Circuit Breakers".
- **Analisis Riset yang Tidak Terverifikasi**: Riset kualitatif berbasis 5-8 partisipan sering kali bias jika tidak divalidasi terhadap jutaan log telemetri produksi.

### Apa Solusinya?
- **Unified Statechart Formalism**: Menyatukan bahasa visual desainer dan arsitektur kode frontend menggunakan finite-state machine yang dapat dieksekusi secara native (*executable specifications*).
- **Service Blueprint as Code**: Mendokumentasikan dan memvalidasi Service Blueprint ke dalam bentuk skema terstruktur (JSON/YAML) yang terintegrasi dengan pipeline CI/CD dan sistem monitoring OpenTelemetry.
- **Continuous Behavioral Synthesis**: Menjadikan sintesis riset sebagai data pipeline berkelanjutan yang secara otomatis memetakan anomali metrik teknis ke titik-titik kritis customer journey.

---

## 5. How (Workflow Detail)

Alur kerja rekayasa pemodelan perilaku dan service blueprinting terbagi ke dalam 4 fase siklus hidup sistem:

```
[FASE 1: Riset & Telemetri]
       │
       ▼
   Ekstraksi Kualitatif (Thematic Tagging) + Event Telemetry (Snowplow/Kafka)
       │
       ▼
[FASE 2: Pemodelan Statechart & Event Storming]
       │
       ▼
   Frontstage States <── (Mapped via Domain Events) ──> Backstage States
       │
       ▼
[FASE 3: Blueprint-to-Architecture Contract]
       │
       ▼
   Definisi Schema Kontrak (OpenAPI/GraphQL) + Saga Compensation Flows
       │
       ▼
[FASE 4: Verifikasi & Observabilitas]
       │
       ▼
   Synthetics Monitoring, OpenTelemetry Tracing, Dead-Letter Recovery UI
```

1. **Fase 1: Riset & Telemetri**: Menggabungkan data wawancara pengguna dengan metrik performa interaksi (RUM - *Real User Monitoring*, Core Web Vitals, INP, Form Abandonment Rate).
2. **Fase 2: Pemodelan Statechart & Event Storming**: Melakukan lokakarya *Event Storming* gabungan (UX + Engineering). Mengidentifikasi User Intent, Domain Events, Read Models, dan State Machines pendukung.
3. **Fase 3: Blueprint-to-Architecture Contract**: Mengonfigurasi Service Blueprint ke dalam bentuk file metadata arsitektural. Menentukan protokol komunikasi pada setiap *Line*:
   - Line of Interaction: HTTPS / WSS / gRPC-Web
   - Line of Visibility: gRPC / Internal RPC
   - Line of Internal Interaction: Event Streams / Asynchronous Message Queues
4. **Fase 4: Verifikasi & Observabilitas**: Menanamkan metadata Service Blueprint (`stage`, `touchpoint`, `actor`) ke dalam OpenTelemetry distributed tracing context. Setiap interaksi pengguna dapat dilacak dari klik tombol hingga query basis data level terendah.

---

## 6. Analogy & Diagram ASCII

### Analogi Sistem: Teater Opera Skala Dunia

- **Frontstage (Panggung Utama)**: Aktor bernyanyi, pencahayaan panggung, set dekorasi, dan dialog. Ini adalah **Antarmuka Pengguna (UI), Notifikasi, dan Haptic Feedback**. Penonton (User) hanya melihat apa yang diperbolehkan oleh sutradara.
- **Line of Visibility (Tirai Panggung)**: Pembatas mutlak. Penonton tidak boleh melihat tali katrol, asisten panggung yang berlari, atau sutradara yang berteriak memberi aba-aba.
- **Backstage (Belakang Panggung)**: Kru panggung yang memutar latar teater, teknisi audio, penata rias cepat. Ini adalah **BFF, Microservices, Message Broker, dan Database**. Mereka harus berkoordinasi secara senyap dan sinkron tanpa merusak ilusi panggung.
- **Support Processes (Pabrik Properti & Pemasok Listrik)**: Pembangkit listrik PLN kota, vendor penjahit kostum, distributor naskah. Ini adalah **Payment Gateway (Xendit/Stripe), Layanan KYC Pemerintah (Dukcapil), dan Penyedia Cloud (AWS/GCP)**. Jika suplai listrik kota padam, genset backstage harus menyala tanpa membuat aktor berhenti bernyanyi secara canggung.

### Diagram Arsitektur Holistik End-to-End

```
+---------------------------------------------------------------------------------------------------+
| USER BEHAVIORAL LAYER (Mental Model: "Saya ingin mencairkan pinjaman darurat sekarang juga")       |
+---------------------------------------------------------------------------------------------------+
                                         │
                                         ▼ [User Action: Trigger Tap]
+---------------------------------------------------------------------------------------------------+
| FRONTSTAGE SUBSYSTEM                                                                              |
|                                                                                                   |
|  ┌─────────────────────────┐           ┌───────────────────────────────────────────────────────┐  |
|  │   React / React Native  │           │ UI Behavior Statechart (XState v5 Engine)             │  |
|  │  ┌───────────────────┐  │  Events   │  ┌──────────────┐   SUBMIT    ┌────────────────────┐  │  |
|  │  │ LoanSubmitButton  ├──┼──────────┼─►│     IDLE     ├────────────►│  SUBMITTING_LOAN   │  │  |
|  │  └───────────────────┘  │           │  └──────────────┘             └─────────┬──────────┘  │  |
|  │  ┌───────────────────┐  │  State    │  ┌──────────────┐   REJECT              │             │  |
|  │  │ Interactive Error │◄─┼───────────┼──┤ FAILED_RETRY │◄──────────────────────┘             │  |
|  │  └───────────────────┘  │  Context  │  └──────────────┘                                     │  |
|  └───────────┬─────────────┘           └───────────────────────────────────────────────────────┘  |
+==============│====================================================================================+
               │ [Line of Interaction] -> HTTPS / W3C Trace Context (traceparent: 00-4bf92f...-01)
               ▼
+---------------------------------------------------------------------------------------------------+
| FRONTSTAGE GATEWAY / EDGE TOUCHPOINTS                                                            |
|                                                                                                   |
|  ┌─────────────────────────────────────────────────────────────────────────────────────────────┐  |
|  │ BFF (Node.js / Fastify Layer)                                                               │  |
|  │  - Context Injection: Append Device Posture, Network Quality, Session Risk Score            │  |
|  │  - Idempotency-Key Validation (Prevent Double Tap Mutation)                                 │  |
|  └──────────────────────────────────────────────┬──────────────────────────────────────────────┘  |
+=================================================│=================================================+
                                                  │ [Line of Visibility]
                                                  ▼
+---------------------------------------------------------------------------------------------------+
| BACKSTAGE MICROSERVICES & EVENT BUS                                                               |
|                                                                                                   |
|  ┌────────────────────────┐   Sync RPC   ┌───────────────────────┐  Sync RPC  ┌────────────────┐  |
|  │ Loan Origination Engine├─────────────►│ Risk & Fraud Engine   ├───────────►│ Account Ledger │  |
|  └───────────┬────────────┘              └───────────────────────┘            └────────────────┘  |
|              │                                                                                    |
|              ▼ Async Domain Event (Kafka Topic: `loan.application.submitted`)                     |
|  ┌─────────────────────────────────────────────────────────────────────────────────────────────┐  |
|  │ Distributed Event Bus: Apache Kafka Partitioned by `user_id`                                 │  |
|  └───────┬──────────────────────────────────────────────┬──────────────────────────────────────┘  |
+==========│==============================================│=========================================+
           │                                              │ [Line of Internal Interaction]
           ▼                                              ▼
+---------------------------------------------------------------------------------------------------+
| SUPPORT PROCESSES & VENDOR ECOSYSTEM                                                              |
|                                                                                                   |
|  ┌────────────────────────────────────────┐    ┌───────────────────────────────────────────────┐  |
|  │ Dukcapil / ASLI RI KYC Validation      │    │ Core Banking Settlement (BI-FAST / RTGS Host) │  |
|  │ (External Rest API / Circuit Breaker)  │    │ (ISO 8583 / AS2 Gateway Protocol)             │  |
|  └────────────────────────────────────────┘    └───────────────────────────────────────────────┘  |
+---------------------------------------------------------------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: State Machine Pemodelan UX Form Input (TypeScript)

Berikut implementasi dasar mesin penanganan *mental model* pengguna terhadap proses pengisian field sensitif (nomor identitas/KTP) dengan toleransi koreksi instan.

```typescript
// Simple Behavioral State Machine Pattern
export type FormState = 'PRISTINE' | 'DIRTY_EDITING' | 'VALIDATING' | 'VALID' | 'INVALID';

export interface FormContext {
  value: string;
  errorMessage?: string;
  retryCount: number;
}

export type FormEvent = 
  | { type: 'TYPING'; payload: string }
  | { type: 'BLUR' }
  | { type: 'RESET' }
  | { type: 'VALIDATION_SUCCESS' }
  | { type: 'VALIDATION_FAILURE'; payload: string };

export class InputBehaviorModel {
  private state: FormState = 'PRISTINE';
  private context: FormContext = { value: '', retryCount: 0 };

  public transition(event: FormEvent): FormState {
    switch (this.state) {
      case 'PRISTINE':
        if (event.type === 'TYPING') {
          this.context.value = event.payload;
          this.state = 'DIRTY_EDITING';
        }
        break;

      case 'DIRTY_EDITING':
        if (event.type === 'TYPING') {
          this.context.value = event.payload;
        } else if (event.type === 'BLUR') {
          this.state = 'VALIDATING';
        }
        break;

      case 'VALIDATING':
        if (event.type === 'VALIDATION_SUCCESS') {
          this.state = 'VALID';
          this.context.errorMessage = undefined;
        } else if (event.type === 'VALIDATION_FAILURE') {
          this.state = 'INVALID';
          this.context.errorMessage = event.payload;
          this.context.retryCount += 1;
        }
        break;

      case 'INVALID':
        if (event.type === 'TYPING') {
          this.context.value = event.payload;
          this.state = 'DIRTY_EDITING';
        } else if (event.type === 'RESET') {
          this.state = 'PRISTINE';
          this.context = { value: '', retryCount: 0 };
        }
        break;

      case 'VALID':
        if (event.type === 'TYPING') {
          this.context.value = event.payload;
          this.state = 'DIRTY_EDITING';
        }
        break;
    }
    return this.state;
  }

  public getSnapshot() {
    return { state: this.state, context: { ...this.context } };
  }
}
```

### 7.2 Practical Example: Enterprise Production Statechart & Service Blueprint Validation Pipeline

Implementasi produksi berikut mencakup:
1. Validasi Service Blueprint Schema menggunakan `Zod`.
2. Mesin statechart transaksi checkout pinjaman terdistribusi menggunakan `XState v5`.
3. Injeksi OpenTelemetry context propagation pada setiap event frontstage-to-backstage.

```typescript
import { createMachine, assign, createActor } from 'xstate';
import { z } from 'zod';

// ============================================================================
// 1. SERVICE BLUEPRINT FORMAL CONTRACT SCHEMA
// ============================================================================
export const ServiceBlueprintStageSchema = z.enum([
  'PHYSICAL_EVIDENCE',
  'CUSTOMER_ACTION',
  'FRONTSTAGE_TOUCHPOINT',
  'BACKSTAGE_SYSTEM',
  'SUPPORT_PROCESS'
]);

export const BlueprintNodeSchema = z.object({
  nodeId: z.string().uuid(),
  stage: ServiceBlueprintStageSchema,
  label: z.string().min(3),
  ownerSquad: z.string(),
  latencyBudgetMs: z.number().int().positive(),
  failoverBehavior: z.enum(['GRACEFUL_DEGRADATION', 'BLOCK_AND_ESCALATE', 'SILENT_RETRY']),
  telemetryEventName: z.string()
});

export type BlueprintNode = z.infer<typeof BlueprintNodeSchema>;

// ============================================================================
// 2. BEHAVIORAL STATECHART MODEL WITH DISTRIBUTED TELEMETRY
// ============================================================================
export interface LoanFlowContext {
  loanAmount: number;
  userId: string;
  traceId: string;
  idempotencyKey: string;
  errorMessage?: string;
  retryAttempt: number;
}

export type LoanFlowEvent =
  | { type: 'REQUEST_SUBMISSION'; amount: number }
  | { type: 'BACKEND_SUCCESS'; transactionId: string }
  | { type: 'BACKEND_REJECTED'; reason: string }
  | { type: 'NETWORK_TIMEOUT' }
  | { type: 'USER_CANCELLED' }
  | { type: 'RETRY' };

export const loanDisbursementMachine = createMachine({
  id: 'loanDisbursement',
  types: {} as {
    context: LoanFlowContext;
    events: LoanFlowEvent;
  },
  initial: 'idle',
  context: ({ input }: { input: { userId: string; traceId: string } }) => ({
    loanAmount: 0,
    userId: input.userId,
    traceId: input.traceId,
    idempotencyKey: crypto.randomUUID(),
    retryAttempt: 0
  }),
  states: {
    idle: {
      on: {
        REQUEST_SUBMISSION: {
          target: 'evaluatingFrontstagePolicies',
          actions: assign({
            loanAmount: ({ event }) => event.amount,
            idempotencyKey: () => crypto.randomUUID()
          })
        }
      }
    },
    evaluatingFrontstagePolicies: {
      entry: ['emitTelemetryFrontstageEvaluation'],
      always: [
        {
          guard: ({ context }) => context.loanAmount > 0 && context.loanAmount <= 50_000_000,
          target: 'submittingToBackstage'
        },
        {
          target: 'frontstagePolicyRejected'
        }
      ]
    },
    submittingToBackstage: {
      entry: ['emitTelemetryDisbursementRequested'],
      invoke: {
        id: 'dispatchLoanApplication',
        src: 'executeDistributedDisbursement',
        input: ({ context }) => ({
          userId: context.userId,
          amount: context.loanAmount,
          traceId: context.traceId,
          idempotencyKey: context.idempotencyKey
        }),
        onDone: {
          target: 'settled',
          actions: ['emitTelemetryDisbursementSettled']
        },
        onError: [
          {
            guard: ({ context }) => context.retryAttempt < 3,
            target: 'transientNetworkFailure',
            actions: assign({
              retryAttempt: ({ context }) => context.retryAttempt + 1,
              errorMessage: ({ event }) => (event.error as Error).message
            })
          },
          {
            target: 'terminalFailure',
            actions: assign({
              errorMessage: ({ event }) => (event.error as Error).message
            })
          }
        ]
      }
    },
    transientNetworkFailure: {
      entry: ['emitTelemetryDegradedExperience'],
      on: {
        RETRY: {
          target: 'submittingToBackstage'
        },
        USER_CANCELLED: {
          target: 'abandonedByCustomer'
        }
      }
    },
    frontstagePolicyRejected: {
      entry: ['emitTelemetryPolicyViolation'],
      on: {
        REQUEST_SUBMISSION: {
          target: 'evaluatingFrontstagePolicies',
          actions: assign({
            loanAmount: ({ event }) => event.amount
          })
        }
      }
    },
    settled: {
      type: 'final'
    },
    terminalFailure: {
      entry: ['emitTelemetryEscalatedFailure'],
      type: 'final'
    },
    abandonedByCustomer: {
      type: 'final'
    }
  }
});

// ============================================================================
// 3. ACTOR EXECUTION & TELEMETRY WIRING
// ============================================================================
export function runProductionDisbursementFlow() {
  const actor = createActor(loanDisbursementMachine.provide({
    actors: {
      executeDistributedDisbursement: async ({ input }) => {
        // Simulasi network request ke BFF dengan W3C Trace Context Propagation
        const response = await fetch('https://api.enterprise-bank.internal/v1/loans', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Idempotency-Key': input.idempotencyKey,
            'traceparent': `00-${input.traceId}-0000000000000001-01`
          },
          body: JSON.stringify({
            userId: input.userId,
            amount: input.amount
          })
        });

        if (!response.ok) {
          throw new Error(`HTTP Error ${response.status}: Failed to reach ledger`);
        }

        return await response.json();
      }
    },
    actions: {
      emitTelemetryFrontstageEvaluation: ({ context }) => {
        console.log(`[OTEL TRACE ${context.traceId}] Touchpoint: Local Policy Check. Amount: ${context.loanAmount}`);
      },
      emitTelemetryDisbursementRequested: ({ context }) => {
        console.log(`[OTEL TRACE ${context.traceId}] Touchpoint: Dispatching to Backstage. Idempotency: ${context.idempotencyKey}`);
      },
      emitTelemetryDisbursementSettled: ({ context }) => {
        console.log(`[OTEL TRACE ${context.traceId}] UX Outcome: Transaction Settled. Success evidence dispatched.`);
      },
      emitTelemetryDegradedExperience: ({ context }) => {
        console.warn(`[OTEL TRACE ${context.traceId}] UX Bottleneck: Network degraded. Retry attempt: ${context.retryAttempt}`);
      },
      emitTelemetryPolicyViolation: ({ context }) => {
        console.warn(`[OTEL TRACE ${context.traceId}] Validation Failure: Amount ${context.loanAmount} exceeds policy.`);
      },
      emitTelemetryEscalatedFailure: ({ context }) => {
        console.error(`[OTEL TRACE ${context.traceId}] Critical UX Failure: Escalating to Support Process. Error: ${context.errorMessage}`);
      }
    }
  }), {
    input: {
      userId: 'usr_c09a823e_7781',
      traceId: '4bf92f3577b34da6a3ce929d0e0e4736'
    }
  });

  actor.subscribe((snapshot) => {
    console.log(`[State Transition Snapshot] State: "${snapshot.value}" | Retries: ${snapshot.context.retryAttempt}`);
  });

  actor.start();
  return actor;
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario: Omni-Channel Core Banking Migration (Tier-1 Financial Institution)
- **Skala**: 12 juta daily active users (DAU), 4.500 transaksi per detik (TPS) pada jam sibuk, integrasi terhadap 34 sistem legacy (termasuk IBM AS/400 Core Banking).
- **Insiden Awal**: Pada kuartal pertama pasca-peluncuran mobile banking baru, terjadi lonjakan komplain *customer care* hingga 300%. Pengguna mengeluhkan uang terdebet dari rekening tetapi status aplikasi masih menampilkan *spinning loader* tanpa henti, memicu kepanikan dan aksi unjuk rasa di kantor cabang.

### Root Cause Analysis (Berdasarkan Service Blueprinting Audit)
1. **Line of Visibility Collapse**: Backend mengadopsi event-driven architecture asinkron (Kafka), sementara UI mengasumsikan model *synchronous request-response* HTTP. Ketika core banking lambat merespons (p99 latency > 45 detik), gateway memutus koneksi dengan HTTP 504 Gateway Timeout.
2. **Missing State Transition in UX**: UI langsung berpindah ke state `Transaction Failed` secara salah (*false negative*), padahal Kafka consumer di backstage masih memproses mutasi saldo di core banking hingga selesai (*eventual consistency mismatch*).
3. **Absence of Support Process Synchronization**: Agen *call center* tidak memiliki visibilitas real-time terhadap saga transaction yang sedang berjalan, sehingga memberikan informasi yang bertolak belakang kepada pengguna.

### Solusi Rekayasa Sosioteknikal
1. **Rekonstruksi Service Blueprint**:
   - Menambahkan state eksplisit pada Frontstage: `PROCESSING_ASYNCHRONOUSLY` dengan batas waktu toleransi visual (*optimistic UI* dengan interval *fallback polling* via Server-Sent Events).
   - Menetapkan batas *Line of Interaction*: Klien menerima acknowledgment `202 Accepted` beserta `polling_token` dan `idempotency_key` dalam waktu < 400ms.
2. **Implementasi Backstage Saga Compensation Pattern**:
   - Jika transaksi gagal pada tahap akhir di core banking, saga orchestrator otomatis memicu kompensasi (pengembalian saldo) dan memicu push notification instan ke ponsel pengguna dalam kurun waktu $< 2$ detik.
3. **Observabilitas Terintegrasi Melalui OpenTelemetry Trace Context**:
   - Parameter `traceparent` diinjeksi sejak penekanan tombol di UI mobile, melintasi Kong API Gateway, BFF, Kafka message header, hingga database log AS/400. Tim support dapat memasukkan trace ID pengguna dan langsung melihat Service Blueprint interaktif yang menyala sesuai path eksekusi riil.

### Hasil Kuantitatif
- Penurunan komplain terkait "transaksi menggantung" sebesar **94.2%**.
- Reduksi *Mean Time to Resolution (MTTR)* insiden operasional dari 4.2 jam menjadi **8 menit**.
- Zero double-debit incident berkat penegakan state machine idempotensi yang ketat di level frontstage touchpoint.

---

## 9. Trade-offs

| Dimensi | Pendekatan Linear / Ad-Hoc UX | Pendekatan Formal Statecharts + Service Blueprint |
| :--- | :--- | :--- |
| **Development Velocity (Awal)** | **Tinggi**: Desain langsung diimplementasikan tanpa validasi skema menyeluruh. | **Rendah**: Memerlukan lokakarya lintas fungsi, pemodelan event-storming, dan setup tooling state machine. |
| **Maintenance & Scalability** | **Rendah**: Kode penuh dengan flag boolean (`isLoading`, `isError`, `isSuccess2`) yang rawan *race conditions* dan *impossible states*. | **Tinggi**: Deterministik, *self-documenting*, penambahan alur baru hanya menambah node/transisi tanpa merusak alur lama. |
| **Client-Side Runtime Overhead** | **Nol / Sangat Kecil**: Hanya mengandalkan state lokal primitif (`useState`). | **Sedang**: Pustaka state machine (e.g., XState) menambahkan bundle size (~15-20 KB gzip), memory footprint untuk actor tree. |
| **Observability & Debugging** | **Buruk**: Membutuhkan rekonstruksi manual dari log terfragmentasi tanpa konteks perjalanan mental pengguna. | **Sangat Unggul**: Setiap perubahan state UI berkorelasi langsung dengan distributed trace ID dan node Service Blueprint. |
| **Organizational Alignment** | **Rendah**: Tim UX, Product, dan Engineering memiliki pemahaman mental yang berbeda tentang batas kapabilitas sistem. | **Tinggi**: Service Blueprint berfungsi sebagai kontrak tunggal (*single source of truth*) yang mengikat semua departemen. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Boolean Explosion pada State UX
- **Kesalahan**: Menggunakan multiple boolean flag untuk merepresentasikan state UI:
  ```typescript
  // ANTI-PATTERN: Menghasilkan 2^4 = 16 kemungkinan state,
  // termasuk kondisi mustahil seperti isLoading=true DAN isSuccess=true.
  const [isLoading, setIsLoading] = useState(false);
  const [isError, setIsError] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  ```
- **Solusi**: Gunakan tagged union atau formal state machine:
  ```typescript
  // PRODUCTION PATTERN: Eksplisit, hanya ada 1 status aktif dalam satu waktu.
  type ViewState = 
    | { status: 'idle' }
    | { status: 'loading' }
    | { status: 'error'; error: Error }
    | { status: 'success'; data: TransactionData };
  ```

### 10.2 Service Blueprint Tanpa Batasan Latensi (Latency Budgets)
- **Kesalahan**: Service Blueprint mencantumkan dependensi vendor eksternal pada Support Process (misal: verifikasi biometrik wajah) tanpa menentukan *Service Level Objective (SLO)* latensi p95/p99.
- **Dampak**: Frontstage UI freeze ketika API vendor mengalami degradasi respons hingga 30 detik.
- **Solusi**: Tentukan batas toleransi (*timeout budget*) pada setiap node blueprint. Pasang *Client-side Circuit Breaker*: Jika vendor tidak merespons dalam 3 detik, alihkan UI ke alur *Asynchronous Manual Review* dengan instruksi visual yang menenangkan pengguna.

### 10.3 Kehilangan Distributed Trace Context di Garis Visibilitas
- **Kesalahan**: BFF tidak meneruskan header `traceparent` dari klien ke sistem antrean pesan asinkron (Kafka/RabbitMQ).
- **Dampak**: Rantai observabilitas terputus; insiden kegagalan di Backstage tidak dapat dihubungkan ke aksi pengguna di Frontstage.
- **Solusi**: Wajibkan middleware tracing di level BFF yang mengekstraksi context HTTP dan menyuntikkannya ke dalam Kafka record headers secara otomatis.

---

## 11. Best Practices (Production Checklist)

### Checklist Pemodelan Perilaku (Behavioral Modeling)
- [ ] Semua state UI telah dimodelkan menggunakan finite states (tidak ada kondisi *undefined/unhandled transitions*).
- [ ] Semua aksi mutasi pengguna memiliki mekanisme proteksi *double-submit* berbasis *Idempotency-Key*.
- [ ] Error states tidak hanya menampilkan pesan generik ("Terjadi kesalahan"), melainkan menyediakan *Recovery Pathway* yang jelas (Retry, Alternative Payment, Hubungi Support).
- [ ] State Machine mencakup penanganan kondisi *offline* dan *flaky network* (degraded connection mode).

### Checklist Service Blueprint
- [ ] Seluruh dependensi pada baris *Support Processes* memiliki *Timeout*, *Circuit Breaker*, dan *Fallback Strategy*.
- [ ] Setiap titik interaksi (*touchpoint*) pada Frontstage memiliki pemetaan telemetry event name standar.
- [ ] Batas kepemilikan (*squad ownership*) terdefinisi dengan jelas untuk setiap node backstage dan support process.
- [ ] Service Blueprint telah di-review dan disetujui bersama oleh Triad: Product Manager, UX Lead, dan Lead System Architect.

### Checklist Observabilitas & Telemetri
- [ ] Klien menyuntikkan W3C Trace Context pada setiap API request.
- [ ] Telemetri tidak mencatat *Personally Identifiable Information (PII)* seperti nomor KTP, kata sandi, atau CVV kartu kredit (patuh GDPR/UU PDP).
- [ ] Visualisasi metrik interaksi (Rage Clicks, Abandonment Rate) tersedia di dashboard real-time (Grafana/Datadog).

---

## 12. Hands-on Practice

Dalam latihan ini, Anda akan membangun sistem pemodelan perilaku checkout terdistribusi yang memvalidasi Service Blueprint runtime dan menangani kegagalan jaringan secara anggun (*graceful degradation*).

### Setup Direktori Praktikum
Buka terminal dan siapkan lingkungan kerja Anda di folder:
```bash
mkdir -p hands-on/m02
cd hands-on/m02
npm init -y
npm install xstate@5 zod
npm install -D typescript @types/node tsx
npx tsc --init
```

### Langkah 1: Buat Engine Service Blueprint Runtime
Buat file `hands-on/m02/blueprint-engine.ts`:

```typescript
import { z } from 'zod';

export const BlueprintContract = z.object({
  id: z.string(),
  touchpoint: z.string(),
  maxToleratedLatencyMs: z.number(),
  criticality: z.enum(['P0', 'P1', 'P2'])
});

export type BlueprintContract = z.infer<typeof BlueprintContract>;

export class BlueprintTelemetryBridge {
  private static registeredNodes = new Map<string, BlueprintContract>();

  public static registerNode(contract: BlueprintContract) {
    this.registeredNodes.set(contract.id, contract);
  }

  public static recordExecution(nodeId: string, actualLatencyMs: number, traceId: string) {
    const node = this.registeredNodes.get(nodeId);
    if (!node) {
      console.warn(`[WARN] Node ${nodeId} tidak terdaftar dalam Service Blueprint formal!`);
      return;
    }

    if (actualLatencyMs > node.maxToleratedLatencyMs) {
      console.error(
        `[SLA BREACH - ${node.criticality}] Trace: ${traceId} | Node: "${node.touchpoint}" ` +
        `membutuhkan ${actualLatencyMs}ms (Batas Blueprint: ${node.maxToleratedLatencyMs}ms). ` +
        `Memicu degradasi UX Frontstage.`
      );
    } else {
      console.log(
        `[SLA OK] Trace: ${traceId} | Node: "${node.touchpoint}" dieksekusi dalam ${actualLatencyMs}ms.`
      );
    }
  }
}
```

### Langkah 2: Buat Statechart Interaksi Pengguna
Buat file `hands-on/m02/user-journey-fsm.ts`:

```typescript
import { createMachine, assign, createActor } from 'xstate';
import { BlueprintTelemetryBridge } from './blueprint-engine';

export interface CheckoutContext {
  userId: string;
  cartTotal: number;
  traceId: string;
  executionAttempts: number;
}

export type CheckoutEvent =
  | { type: 'PROCEED_TO_PAYMENT' }
  | { type: 'NETWORK_RETRY' }
  | { type: 'PAYMENT_CONFIRMED' }
  | { type: 'TIMEOUT_TRIGGERED' };

export const checkoutBehaviorMachine = createMachine({
  id: 'checkoutBehavior',
  types: {} as {
    context: CheckoutContext;
    events: CheckoutEvent;
  },
  initial: 'reviewingCart',
  context: ({ input }: { input: { userId: string; cartTotal: number; traceId: string } }) => ({
    userId: input.userId,
    cartTotal: input.cartTotal,
    traceId: input.traceId,
    executionAttempts: 0
  }),
  states: {
    reviewingCart: {
      on: {
        PROCEED_TO_PAYMENT: {
          target: 'contactingPaymentGateway'
        }
      }
    },
    contactingPaymentGateway: {
      entry: assign({
        executionAttempts: ({ context }) => context.executionAttempts + 1
      }),
      invoke: {
        id: 'callPaymentVendor',
        src: 'simulatePaymentVendorCall',
        input: ({ context }) => ({ traceId: context.traceId }),
        onDone: {
          target: 'checkoutCompleted'
        },
        onError: [
          {
            guard: ({ context }) => context.executionAttempts < 2,
            target: 'gracefulDegradationWarning'
          },
          {
            target: 'hardFailureEscalation'
          }
        ]
      }
    },
    gracefulDegradationWarning: {
      on: {
        NETWORK_RETRY: {
          target: 'contactingPaymentGateway'
        }
      }
    },
    checkoutCompleted: {
      type: 'final'
    },
    hardFailureEscalation: {
      type: 'final'
    }
  }
});
```

### Langkah 3: Eksekusi dan Verifikasi
Buat file `hands-on/m02/index.ts`:

```typescript
import { createActor } from 'xstate';
import { BlueprintTelemetryBridge } from './blueprint-engine';
import { checkoutBehaviorMachine } from './user-journey-fsm';

// 1. Daftarkan Service Blueprint nodes
BlueprintTelemetryBridge.registerNode({
  id: 'node_payment_vendor',
  touchpoint: 'Third-Party Payment Settlement (Support Process)',
  maxToleratedLatencyMs: 1500,
  criticality: 'P0'
});

// 2. Setup runner simulasi
const testTraceId = 'tr_98234abcf012345';

const checkoutActor = createActor(
  checkoutBehaviorMachine.provide({
    actors: {
      simulatePaymentVendorCall: async ({ input }) => {
        const startTime = Date.now();
        console.log(`[HTTP Request] Memulai request pembayaran...`);

        // Simulasikan delay network yang melebihi SLA Service Blueprint (2000ms > 1500ms)
        await new Promise((res) => setTimeout(res, 2000));
        const duration = Date.now() - startTime;

        BlueprintTelemetryBridge.recordExecution('node_payment_vendor', duration, input.traceId);

        // Lempar error untuk menguji alur fallback
        throw new Error('E_GATEWAY_TIMEOUT: Vendor did not reply within acceptable window');
      }
    }
  }),
  {
    input: {
      userId: 'user_enterprise_99',
      cartTotal: 1500000,
      traceId: testTraceId
    }
  }
);

checkoutActor.subscribe((snapshot) => {
  console.log(`>>> Current Behavior State: [${snapshot.value}]`);
});

checkoutActor.start();

// Jalankan interaksi pengguna
console.log('--- User menekan tombol checkout ---');
checkoutActor.send({ type: 'PROCEED_TO_PAYMENT' });

// Tunggu hingga simulasi selesai lalu coba retry jika degradasi
setTimeout(() => {
  if (checkoutActor.getSnapshot().value === 'gracefulDegradationWarning') {
    console.log('--- User memilih mencoba kembali (Retry Recovery Pathway) ---');
    checkoutActor.send({ type: 'NETWORK_RETRY' });
  }
}, 3000);
```

Jalankan skrip untuk melihat validasi blueprint dan transisi behavior secara realtime:
```bash
npx tsx hands-on/m02/index.ts
```

---

## 13. Exercise

### Level Easy
Modifikasi mesin state pada `hands-on/m02/user-journey-fsm.ts` untuk menambahkan state `cancelledByUser`. State ini harus dapat diakses saat sistem berada di `gracefulDegradationWarning` apabila pengguna menolak untuk mencoba kembali.
- *Petunjuk*: Tambahkan event `USER_ABORT` dan hubungkan transisinya ke state final baru tersebut.

### Level Medium
Integrasikan skema Zod untuk memvalidasi *payload input* pada state `reviewingCart`. Jika `cartTotal <= 0` atau `cartTotal > 100_000_000`, cegah transisi ke `contactingPaymentGateway` dan arahkan secara langsung ke state baru: `invalidOrderPolicyViolation`.
- *Petunjuk*: Gunakan guard condition pada XState v5 yang mengevaluasi context terhadap hasil validasi Zod.

### Level Hard
Implementasikan pola arsitektur **Dead-Letter Queue (DLQ) Recovery Pathway** ke dalam Service Blueprint. Ketika pembayaran gagal secara permanen (`hardFailureEscalation`), actor harus secara otomatis memicu background support process (simulasikan via async service) yang menyimpan status keranjang belanja ke sistem penyimpanan lokal klien (IndexedDB / mock storage) dan mengembalikan respons visual: *"Pesanan Anda telah kami amankan di antrean darurat. CS kami akan menghubungi Anda dalam 15 menit."* tanpa membiarkan data belanjaan hilang.

---

## 14. Challenge

**Skenario**: Anda adalah Principal UX Engineer di sebuah platform e-commerce SuperApp multi-nasional saat Flash Sale Midnight (100.000 concurrent users memperebutkan 500 unit PlayStation 5).

**Masalah Arsitektural**:
Kapasitas Backstage Inventory Service tidak mampu menangani read-write traffic secara sinkron. Tim backend memberlakukan sistem antrean virtual (*Virtual Waiting Room*) berbasis Cloudflare Workers & Redis Leaky Bucket. Pengguna yang menekan tombol *"Beli Sekarang"* tidak langsung dialihkan ke pembayaran, melainkan dimasukkan ke antrean dengan estimasi waktu tunggu dinamis (1 detik hingga 8 menit).

**Instruksi Penugasan**:
1. Buat Service Blueprint lengkap (format JSON Schema / TypeScript Object terstruktur) yang mencakup 5 layer dari Physical Evidence hingga Support Processes, secara spesifik memetakan status `QUEUE_HOLDING`, `TOKEN_ISSUED`, `TOKEN_EXPIRED`, dan `CHECKOUT_WINDOW_ACQUIRED`.
2. Susun Finite State Machine untuk Frontstage UI yang menjamin:
   - Pengguna dilarang melakukan refresh manual (jika refresh terjadi, posisi antrean tidak hilang melalui pemulihan token session).
   - Menampilkan visual progress bar yang adaptif terhadap perubahan waktu tunggu tanpa membuat pengguna cemas (*preventing rage refresh*).
   - Menangani edge-case kegagalan token kedaluwarsa (*Token Expiration Race Condition* ketika user sudah menunggu 5 menit tetapi gagal menyelesaikan pembayaran dalam waktu jendela alokasi 3 menit).
3. Buat skema mitigasi UX jika stok habis saat pengguna sedang berada di posisi antrean #10.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda)

1. **Apa perbedaan mendasar antara Customer Journey Map (CJM) dan Service Blueprint?**  
   a. CJM menggunakan Figma, sedangkan Service Blueprint menggunakan Jira.  
   b. CJM hanya berfokus pada pengalaman emosional pengguna dari sisi luar, sedangkan Service Blueprint memetakan operasi internal end-to-end (frontstage, backstage, support process) yang memungkinkan pengalaman tersebut terwujud.  
   c. Service Blueprint tidak memerlukan data riset pengguna.  
   d. CJM selalu dibuat setelah perangkat lunak masuk ke tahap produksi.  
   *Jawaban: b. Service Blueprint membedah hingga ke balik layar sistem operasi dan infrastruktur yang mendukung setiap touchpoint CJM.*

2. **Garis batas yang memisahkan interaksi langsung antara pengguna dan antarmuka dengan aktivitas sistem internal yang tidak terlihat disebut...**  
   a. Line of Internal Interaction  
   b. Line of Interaction  
   c. Line of Visibility  
   d. Line of Escalation  
   *Jawaban: c. Line of Visibility memisahkan aksi panggung depan (frontstage) dengan panggung belakang (backstage).*

3. **Mengapa penggunaan representasi State Machine (Statechart) lebih direkomendasikan dibanding diagram alir linear dalam pemodelan UX aplikasi enterprise?**  
   a. Karena State Machine secara matematis mencegah *impossible states*, menangkap kondisi asinkron, dan mendefinisikan guard transitions secara deterministik.  
   b. Karena State Machine lebih mudah dipahami oleh orang awam tanpa pelatihan teknis.  
   c. Karena diagram alir linear tidak dapat digambar di komputer.  
   d. Karena State Machine menghilangkan kebutuhan akan penulisan unit testing.  
   *Jawaban: a. Statecharts mencegah status ambigu dan memodelkan sistem asinkron secara deterministik.*

4. **Apa yang dimaksud dengan "Physical Evidence" dalam Service Blueprint aplikasi digital?**  
   a. Perangkat keras server fisik di data center.  
   b. Artefak nyata atau digital yang diterima/dilihat pengguna sebagai bukti berlangsungnya layanan (e.g., struk PDF, badge notifikasi, email verifikasi).  
   c. Gedung kantor cabang institusi terkait.  
   d. Kode sumber mentah aplikasi.  
   *Jawaban: b. Physical/Digital Evidence adalah bukti nyata yang dirasakan dan dilihat pengguna.*

5. **Apa fungsi utama penyuntikan W3C Trace Context (`traceparent`) pada interaksi frontstage?**  
   a. Mempercepat koneksi internet pengguna hingga 50%.  
   b. Menghubungkan setiap event interaksi visual pengguna ke log backend, microservices, dan database terdistribusi di bawah satu ID trace yang unik.  
   c. Mengompresi ukuran payload JSON yang dikirim ke gateway.  
   d. Menyimpan kata sandi pengguna secara terenkripsi di browser.  
   *Jawaban: b. Memungkinkan *end-to-end distributed tracing* dari level interaksi UI hingga backend internal.*

---

### Bagian 2: Intermediate (Pilihan Ganda & Analisis Konseptual)

6. **Dalam arsitektur event-driven, jika sistem menerapkan *Eventual Consistency*, bagaimana frontstage UX harus memodelkan state saat pengguna melakukan mutasi transaksi?**  
   a. Langsung menampilkan pesan "Transaksi Berhasil" secara permanen tanpa verifikasi.  
   b. Mengunci antarmuka (*freeze*) hingga database master selesai melakukan sinkronisasi selama puluhan detik.  
   c. Menampilkan state *Optimistic Pending/Processing* dengan polling atau SSE listener, disertai fallback state jika saga orchestration gagal melakukan kompensasi.  
   d. Melempar runtime error `500 Internal Server Error`.  
   *Jawaban: c. Pola Optimistic UI dengan asynchrony reconciliation adalah standar emas dalam sistem eventual consistency.*

7. **Kapan *Client-side Circuit Breaker* harus dipicu dalam pemodelan Service Blueprint?**  
   a. Saat baterai perangkat pengguna di bawah 10%.  
   b. Ketika tingkat kegagalan atau timeout pada touchpoint vendor pihak ketiga melampaui ambang batas SLO, mengalihkan UI ke safe degraded mode.  
   c. Setiap kali pengguna salah memasukkan password sebanyak 1 kali.  
   d. Ketika pengguna berpindah dari Wi-Fi ke data seluler.  
   *Jawaban: b. Mencegah cascading failures dan UI hang dengan memutus sementara pemanggilan dependensi yang bermasalah.*

8. **Manakah dari skenario berikut yang merupakan contoh pelanggaran "Line of Internal Interaction"?**  
   a. Frontend React langsung memanggil basis data PostgreSQL production via port 5432 terbuka tanpa melewati API Gateway/BFF.  
   b. Mobile App berkomunikasi via HTTPS ke BFF.  
   c. BFF menerbitkan event ke Apache Kafka.  
   d. Microservice Payments memanggil API eksternal Stripe melalui Circuit Breaker.  
   *Jawaban: a. Frontend melompati Line of Interaction, Visibility, dan Internal Interaction sekaligus, menimbulkan risiko keamanan dan stabilitas masif.*

9. **Apa peran *Thematic Coding / Tagging* dalam sintesis riset UX berskala enterprise?**  
   a. Mewarnai diagram Figma agar terlihat lebih menarik bagi manajemen.  
   b. Mengelompokkan data kualitatif terfragmentasi menjadi taksonomi pola perilaku berbobot yang dapat dikorelasikan dengan telemetri kuantitatif.  
   c. Menghapus log error yang tidak diinginkan dari server backend.  
   d. Mengenkripsi identitas peserta riset agar tidak terlihat oleh peneliti.  
   *Jawaban: b. Menjembatani observasi kualitatif subjektif menjadi unit data kuantitatif yang terukur.*

10. **Apa bahaya laten arsitektural jika Service Blueprint tidak mendefinisikan *Idempotency-Key* pada Customer Action yang memicu transaksi finansial?**  
    a. Pengguna akan diarahkan ke halaman login secara acak.  
    b. Koneksi Wi-Fi pengguna akan terputus secara otomatis.  
    c. Ketukan ganda (*double-tap*) atau *network retry* otomatis dari klien dapat memicu pemotongan saldo berulang kali di Backstage Ledger.  
    d. Desain antarmuka akan kehilangan responsivitas ukuran layar (CSS break).  
    *Jawaban: c. Idempotency menjamin operasi yang dieksekusi berulang kali dengan kunci yang sama hanya menghasilkan efek samping satu kali.*

---

### Bagian 3: Skenario Kasus Produksi (Analisis Arsitektur)

#### Skenario 1
Sebuah platform investasi saham mengalami lonjakan traffic saat pembukaan pasar. Pengguna mengklik tombol "Beli Saham". UI menampilkan status *Loading*, namun setelah 15 detik sistem menampilkan *Toast Error*: *"Network Timeout"*. Pengguna mengklik kembali tombol tersebut sebanyak 3 kali. Satu jam kemudian, pengguna mendapati portofolionya telah membeli saham tersebut sebanyak 4 kali dan saldo kasnya minus.  
**Pertanyaan**: Bedah kegagalan Service Blueprint ini dari aspek Frontstage, Backstage, dan Solusi State Machine-nya.  
*Analisis Evaluasi*:  
- **Frontstage Failure**: Kegagalan penerapan state *disablement* dan tidak adanya isolasi tombol transaksi saat state `SUBMITTING` berlangsung. UI mengartikan timeout jaringan sebagai pembatalan transaksi, padahal order telah masuk antrean.
- **Backstage Failure**: API Gateway tidak menerapkan *Idempotency Key Check*. Setiap HTTP request baru diproses sebagai pesanan baru oleh Order Matching Engine tanpa mengecek apakah request tersebut adalah retry dari klien yang sama.
- **Solusi State Machine**: Mengunci state ke `SUBMIT_PENDING_CONFIRMATION`, menghasilkan UUID idempotency key di sisi klien per intent transaksi, dan tidak mengizinkan retry mutasi baru sebelum ada final status dari endpoint rekonsiliasi.

#### Skenario 2
Platform Telemedicine memiliki fitur konsultasi video langsung dengan dokter spesialis. Pada Service Blueprint awal, alur dirancang linear:  
`User Bayar -> Dokter Ditugaskan -> Video Call Terhubung`.  
Di lapangan, 18% panggilan gagal karena dokter terlambat merespons panggilan masuk dalam waktu 60 detik, membuat pasien menunggu di layar kosong hingga frustrasi dan menutup aplikasi.  
**Pertanyaan**: Bagaimana Anda merancang ulang Service Blueprint ini dengan menerapkan *Graceful Degradation* dan *Automated Escalation Pathway*?  
*Analisis Evaluasi*:  
- Tambahkan **Timer State** pada Frontstage (`WAITING_FOR_PHYSICIAN_ACCEPTANCE`, max 45 detik) dengan animasi interaktif penenang dan informasi posisi antrean dokter.
- Pada Backstage, implementasikan *Timeout Event Listener*: Jika dalam 45 detik dokter target tidak mengambil sesi, orkestrator memindahkan tugas ke pool dokter pengganti siaga secara otomatis (*Automated Failover*).
- Pada Support Process, sediakan fallback interaktif pada detik ke-60: UI menawarkan opsi kepada pasien: (a) Tunggu 2 menit lagi dengan voucher diskon kompensasi, (b) Alihkan ke sesi chat asinkron dokter spesialis lain, atau (c) *Instant Full Refund* otomatis dalam 1 klik tanpa birokrasi tiket CS.

#### Skenario 3
Sebuah aplikasi SuperApp ingin melacak mengapa 40% pengguna membatalkan proses registrasi akun baru pada tahap verifikasi e-KTP. Tim UX mengklaim prosesnya "mudah", namun data drop-off sangat tinggi.  
**Pertanyaan**: Bagaimana Anda membangun pipeline integrasi riset kuantitatif-kualitatif untuk mengungkap akar masalah teknis dan perilakunya?  
*Analisis Evaluasi*:  
- Pasang event telemetri granular di Frontstage: Catat `dwell_time_per_field`, `camera_permission_denial_rate`, `image_reupload_count`, dan `client_side_validation_error_frequency`.
- Tautkan setiap sesi drop-off dengan OpenTelemetry Trace ID dan *Session Replay tool* (e.g., OpenReplay/LogRocket) yang telah dimaskir PII-nya.
- Lakukan korelasi data: Analisis apakah *reupload count* yang tinggi berkorelasi dengan respons time API OCR pihak ketiga di Support Process yang timeout atau menghasilkan confidence score rendah akibat kompresi gambar berlebih di sisi klien.
- Simpulkan hasil riset sintesis ke dalam pembaruan Service Blueprint: Tambahkan *real-time client-side frame detection* sebelum foto diunggah ke backend untuk memastikan ketajaman gambar e-KTP sejak awal.

---

## 16. Summary

1. **Konvergensi Desain dan Arsitektur**: Pemodelan perilaku UX modern menuntut formalisasi matematis. Finite State Machines (FSM) dan Harel Statecharts menghapus ambiguitas antara mock-up visual dan eksekusi kode frontend enterprise.
2. **Kekuatan Service Blueprint Terintegrasi**: Service Blueprint bukan sekadar diagram ilustratif, melainkan spesifikasi arsitektur sosioteknikal yang mendefinisikan kontrak interaksi antara *Frontstage Touchpoints*, *Backstage Microservices*, dan *Support Processes*.
3. **Observabilitas Lintas Garis (Cross-Line Observability)**: Pemanfaatan W3C Trace Context yang mengalir dari event frontstage hingga ke database terdalam memungkinkan visualisasi real-time terhadap performa customer journey dan deteksi dini kegagalan operasional.
4. **Resiliensi Pengalaman Pengguna (UX Resilience)**: Sistem enterprise yang tangguh dirancang bukan dengan mengasumsikan jaringan tidak pernah putus, melainkan dengan memodelkan state *transient degradation*, *idempotent transactions*, dan *recovery pathways* secara elegan pada setiap titik interaksi.