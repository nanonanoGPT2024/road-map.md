# Bab 08: Network Resiliency, Offline-First Architecture, dan Security
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Merancang dan mengimplementasikan** arsitektur *Offline-First* berbasis *Durable Mutation Outbox Queue* menggunakan SQLite/WatermelonDB via JavaScript Interface (JSI).
- **Membangun** *Reconciliation & Conflict Resolution Engine* deterministik menggunakan pendekatan *Last-Write-Wins* (LWW) dengan *Hybrid Logical Clocks* (HLC) dan *Conflict-Free Replicated Data Types* (CRDT).
- **Mengembangkan** *Network Resiliency Layer* tingkat lanjut yang mengimplementasikan *Circuit Breaker Pattern*, *Exponential Backoff* dengan *Full Jitter*, serta manajemen idempotensi global.
- **Mengonfigurasi dan menegakkan** protokol keamanan *Zero-Trust Mobile Client*, mencakup *Dynamic SSL/TLS Public Key Pinning* (HPKP/SPKI), enkripsi database *at-rest* via SQLCipher (AES-256-GCM), dan proteksi kunci kriptografi berbasis *Hardware Security Module* (iOS Keychain Secure Enclave & Android Keystore TEE).

---

### 2. Prerequisites
Sebelum mendalami modul ini, Anda harus memiliki pemahaman mendalam tentang:
- Arsitektur inti React Native modern (Fabric Renderer, TurboModules, Bridgeless Mode, dan integrasi JSI/C++).
- Konsep dasar konkurensi, thread pools (UI Thread, JS Thread, Background/Worker Threads), dan *event-loop execution model*.
- Dasar-dasar protokol HTTP/2, HTTP/3 (QUIC), TLS Handshake, dan struktur sertifikat X.509.
- Penggunaan dasar SQLite atau engine relasional lokal pada lingkungan mobile.

---

### 3. Concept & Internal Architecture (Mendalam)

Membangun aplikasi mobile enterprise kelas dunia memerlukan pergeseran paradigma dari *Network-Centric* (mengasumsikan koneksi internet selalu stabil dan cepat) menuju *Local-First / Offline-First* (menganggap jaringan lokal adalah sumber kebenaran instan, sedangkan jaringan eksternal adalah kanal sinkronisasi asinkron yang tidak dapat diprediksi).

```
+---------------------------------------------------------------------------------------+
|                                    REACT NATIVE UI                                    |
|   (Optimistic UI Update: Langsung bereaksi tanpa memblokir interaksi pengguna)         |
+---------------------------------------------------------------------------------------+
       │                                                                  ▲
       ▼                                                                  │ Event Bus /
[Command Dispatch]                                                  [Reactive Query]
       │                                                                  │
+──────▼──────────────────────────────────────────────────────────────────┴─────────────+
|                               LOCAL DATA ENGINE                                       |
|  +-------------------------------------+   +---------------------------------------+  |
|  |           SQLite / SQLCipher        |   |         Hardware Security Layer       |  |
|  |     (AES-256 Database Encryption)   |   |   (iOS Secure Enclave / Android TEE)  |  |
|  |                                     |   +---------------------------------------+  |
|  |  +---------------+ +-------------+  |                       ▲                      |
|  |  | Domain State  | | Mutation    |  |                       │ Crypto Operations    |
|  |  | Tables        | | Outbox Log  |  |                       │ (Key Management)     |
|  |  +---------------+ +-------------+  |                       ▼                      |
|  +-------------------------------------+   +---------------------------------------+  |
|                                            |    Idempotency & HMAC Generator       |  |
|                                            +---------------------------------------+  |
+──────────────────────────────────────────────────────────────────┬────────────────────+
                                                                   │
                                                      [Background Sync Worker]
                                                                   │
+──────────────────────────────────────────────────────────────────▼────────────────────+
|                           NETWORK RESILIENCY ENGINE                                   |
|  +---------------------------------------------------------------------------------+  |
|  |  Circuit Breaker (Closed -> Open -> Half-Open)                                  |  |
|  |  Exponential Backoff with Full Jitter Queue                                     |  |
|  |  Network State Detector (NetInfo + Ping Probing)                                |  |
|  +---------------------------------------------------------------------------------+  |
+──────────────────────────────────────────────────────────────────┬────────────────────+
                                                                   │ Mutual TLS /
                                                                   │ Dynamic Key Pinning
+──────────────────────────────────────────────────────────────────▼────────────────────+
|                                   REMOTE API GATEWAY                                  |
|   (Idempotent Receiver, Conflict Detector & Watermark/Timestamp Generator)             |
+---------------------------------------------------------------------------------------+
```

#### A. The Outbox Mutation Pattern & State Machine
Pada sistem enterprise, mutasi data tidak boleh langsung ditembakkan via `fetch` atau `axios`. Setiap operasi mutasi (`CREATE`, `UPDATE`, `DELETE`) harus dienkapsulasi menjadi *Command Object* yang dicatat secara transaksional (*ACID Transaction*) ke dalam tabel lokal bernama `mutation_outbox`.

State machine mutasi melewati status berikut:
1. `ENQUEUED`: Mutasi tersimpan secara persisten di disk lokal; UI langsung diperbarui secara optimistik.
2. `PROCESSING`: Mutasi sedang dikirim melalui jaringan dengan *lock* aktif untuk mencegah *race condition* mutasi berikutnya pada entitas yang sama.
3. `COMMITTED`: Server mengonfirmasi penerimaan mutasi; server timestamp diterapkan ke entitas lokal, dan log mutasi diarsipkan atau dihapus.
4. `FAILED_RETRYABLE`: Kegagalan transien jaringan (timeout, 502/503/504); dijadwalkan ulang melalui algoritma *Exponential Backoff*.
5. `DEAD_LETTER`: Kegagalan permanen (4xx selain 408/429, payload corrupt, skema usang); membutuhkan intervensi atau resolusi kompensasi pengguna.

#### B. Conflict Resolution: HLC & Vector Clocks vs. CRDT
Ketika klien offline melakukan mutasi dan klien lain juga memutasi data yang sama di server, timbul konflik. Terdapat tiga paradigma utama resolusi:
1. **Server-Authoritative Last-Write-Wins (LWW):** Menggunakan timestamp server. Rentan terhadap hilangnya data klien offline karena mutasi klien yang terjadi lebih awal secara riil dapat menimpa mutasi klien yang offline lebih lama jika resolusinya naif.
2. **Hybrid Logical Clocks (HLC):** Mengombinasikan physical time (NTP/Wall-clock) dengan logical counter. HLC menjamin hubungan kausalitas (*causality tracking*) tanpa rentan terhadap *clock skew/drift* sistem operasi mobile klien.
3. **State-based / Delta-based CRDTs (Conflict-Free Replicated Data Types):** Struktur data matematis (seperti PN-Counters, LWW-Element-Set, atau RGA) yang menjamin konvergensi deterministik antar *node* yang terdistribusi secara independen tanpa memerlukan koordinasi terpusat.

#### C. Zero-Trust Security Perimeter
- **Transport Layer Security:** Mengandalkan CA publik standar membuka celah serangan *Man-In-The-Middle* (MITM) via *rogue root certificates* di perangkat pengguna (misal: perangkat root/jailbreak atau enterprise proxy). Solusinya adalah *Public Key Pinning* (Subject Public Key Info / SPKI pinning) yang memverifikasi *cryptographic hash* dari public key server sebelum payload dikirimkan.
- **Data-at-Rest Security:** Seluruh database lokal dienkripsi menggunakan *SQLCipher* berbasis algoritma AES-256-GCM. Kunci enkripsi database tidak pernah disimpan secara *hardcoded* di JavaScript; kunci diturunkan via *PBKDF2* atau *Argon2* dari *master secret* yang diisolasi di dalam *Hardware Keystore* (Android KeyStore TEE atau iOS Keychain Secure Enclave).

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional (Naive) | Pendekatan Enterprise (Offline-First Resilient) |
| :--- | :--- | :--- |
| **Penyimpanan State** | Memory State (Redux/Zustand) + Async Storage ad-hoc. | SQLite/WatermelonDB via JSI dengan arsitektur Outbox transaksional. |
| **Respon UI** | Loading spinner memblokir UI hingga HTTP call selesai. | Optimistic update instan; UI tidak pernah terkunci oleh fluktuasi jaringan. |
| **Penanganan Error** | Muncul Alert Dialog: *"Network Error, Try Again"*. | Silent retry via durable queue, exponential backoff, dan circuit breaker. |
| **Integritas Mutasi** | Risiko *double-submitting* form transaksi saat koneksi lemot. | Strict Idempotency Keys (UUIDv4 + Payload SHA-256) di header permintaan. |
| **Keamanan Data** | Plaintext SQLite / AsyncStorage, validasi HTTPS default OS. | Full DB Encryption (SQLCipher) + Dynamic SPKI Pinning via Native Layer. |

---

### 5. How (Workflow Detail)

Alur eksekusi mutasi data lokal-ke-server:
1. **Capture & Enqueue:** UI memanggil action `updateUserProfile()`. Transaction dimulai di SQLite: entitas `User` diperbarui secara lokal, dan *command* `UPDATE_PROFILE` dimasukkan ke tabel `mutation_outbox`. Transaksi di-*commit*. UI segera merender perubahan.
2. **Signal Queue Worker:** Database hook mentrigger `SyncWorker`.
3. **Circuit Check:** Worker memeriksa status *Circuit Breaker*. Jika sirkuit `OPEN`, worker menghentikan operasi dan menunggu jeda *cooldown*.
4. **Acquire Lock & Prepare Request:** Worker mengambil *oldest pending mutation*, menandai statusnya sebagai `PROCESSING`. Mengambil *Idempotency-Key* yang terasosiasi.
5. **Secure Dispatch:** Engine Native Network memvalidasi sertifikat SSL via SPKI Pin. Jika pin cocok, HTTP request dikirimkan dengan header `X-Idempotency-Key`.
6. **Evaluate Response:**
   - **Status 200/201 (Success):** Server mengembalikan state terverifikasi beserta *watermark timestamp*. Worker memperbarui state lokal dengan konfirmasi server, lalu menghapus item outbox.
   - **Status 409 (Conflict):** Worker meneruskan payload ke *Conflict Resolver Engine*. Jika algoritma CRDT/3-Way Merge sukses mengonvergensikan state, mutasi penyeimbang dikirimkan ke server.
   - **Status 5xx / Network Timeout:** Worker menandai entitas sebagai `FAILED_RETRYABLE`, menghitung interval penundaan berikutnya via *Full Jitter Backoff*, dan melepaskan status `PROCESSING`.

---

### 6. Analogy & Diagram ASCII

#### A. Analogi Dunia Nyata: Kantor Diplomat dan Tas Diplomatik
Bayangkan seorang atase militer di daerah terpencil yang harus mengirim dokumen strategis ke kantor pusat.
- **Naive approach:** Sang atase menelepon kantor pusat setiap kali ada memo. Jika sinyal radio mati, dia panik, pekerjaan terhenti, dan dokumen tercecer.
- **Offline-First Outbox approach:** Sang atase memiliki brankas baja tahan api (SQLite terenkripsi). Setiap memo dimasukkan ke dalam tas diplomatik bersegel resmi (Durable Outbox Queue) dengan nomor seri unik (*Idempotency Key*). Begitu konvoi kurir tiba (Jaringan aktif), kurir membawa tas satu per satu. Jika jembatan putus (*Circuit Breaker*), kurir kembali ke pos dan mencoba lagi nanti sesuai jadwal adaptif (*Exponential Backoff*). Dokumen asli tetap aman di dalam brankas sampai tanda terima resmi dari pusat tiba.

#### B. State Machine Mutation Lifecycle Diagram
```
              [ User Action Triggered ]
                          │
                          ▼
            ┌───────────────────────────┐
            │       Local SQLite        │
            │   Optimistic Write State  │
            └─────────────┬─────────────┘
                          │
                          ▼
            ┌───────────────────────────┐
            │   Mutation Outbox Table   │
            │     (Status: ENQUEUED)    │
            └─────────────┬─────────────┘
                          │
            ┌─────────────┴─────────────┐
            ▼                           ▼
[Network Offline / Breaker OPEN]   [Network Connected / Breaker CLOSED]
            │                           │
            │ Wait for Online Event     │ Worker processes FIFO
            └─────────────┬─────────────┘
                          ▼
            ┌───────────────────────────┐
            │   Status: PROCESSING      │
            │ (Lock Acquired, SPKI Pin) │
            └─────────────┬─────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼ (2xx Success)   ▼ (409 Conflict)  ▼ (5xx / Timeout)
 ┌──────────────┐  ┌──────────────┐  ┌─────────────────────────┐
 │ Status:      │  │ Conflict     │  │ Calculate Exponential   │
 │ COMMITTED    │  │ Resolution   │  │ Backoff + Full Jitter   │
 └──────┬───────┘  └──────┬───────┘  └────────────┬────────────┘
        │                 │                       │
        ▼                 ▼                       ▼
 [Purge Outbox]   [Merge & Commit]       [Status: FAILED_RETRY]
                                                  │
                                          Exceeded max retries?
                                                  ├───── No ──> Re-enqueue
                                                  │
                                                  └───── Yes ─> [DEAD_LETTER]
```

---

### 7. Simple Example & Practical Enterprise Example

#### A. Simple Example: In-Memory Resilient Backoff with Full Jitter
Snippet fungsional mandiri yang mendemonstrasikan algoritma *Full Jitter Backoff* standar AWS Architecture.

```typescript
// utils/backoff.ts
export interface BackoffConfig {
  baseDelayMs: number;
  maxDelayMs: number;
  maxAttempts: number;
}

export const DEFAULT_BACKOFF_CONFIG: BackoffConfig = {
  baseDelayMs: 500,
  maxDelayMs: 10000,
  maxAttempts: 5,
};

/**
 * Menghitung waktu tunggu berdasarkan algoritma Full Jitter:
 * Sleep = rand(0, min(maxDelay, baseDelay * 2 ^ attempt))
 */
export function calculateFullJitterDelay(attempt: number, config = DEFAULT_BACKOFF_CONFIG): number {
  const exponentialDelay = config.baseDelayMs * Math.pow(2, attempt);
  const cappedDelay = Math.min(config.maxDelayMs, exponentialDelay);
  return Math.floor(Math.random() * cappedDelay);
}

export async function executeWithRetry<T>(
  operation: (attempt: number) => Promise<T>,
  config = DEFAULT_BACKOFF_CONFIG
): Promise<T> {
  let attempt = 0;
  while (attempt < config.maxAttempts) {
    try {
      return await operation(attempt);
    } catch (error) {
      attempt++;
      if (attempt >= config.maxAttempts) {
        throw new Error(`Max retry attempts (${config.maxAttempts}) reached. Root error: ${String(error)}`);
      }
      const delay = calculateFullJitterDelay(attempt, config);
      await new Promise((resolve) => setTimeout(resolve, delay));
    }
  }
  throw new Error('Unexpected execution flow termination');
}
```

#### B. Practical Enterprise Example: Complete Production-Grade Resilient Outbox & SSL Verification Layer

Struktur implementasi ini mencakup:
1. Interface & Engine SQLite Outbox Queue.
2. Idempotency Generation & Circuit Breaker Logic.
3. Worker Orkestrasi Sinkronisasi.

```typescript
// types/sync.ts
export type MutationStatus = 'ENQUEUED' | 'PROCESSING' | 'COMMITTED' | 'FAILED_RETRYABLE' | 'DEAD_LETTER';

export interface OutboxMutation<TPayload = Record<string, unknown>> {
  id: string; // UUIDv4
  idempotencyKey: string;
  entityName: string;
  entityId: string;
  action: 'CREATE' | 'UPDATE' | 'DELETE';
  payload: TPayload;
  createdAt: number;
  updatedAt: number;
  retryCount: number;
  status: MutationStatus;
  lastErrorMessage?: string;
}

export interface SyncResult {
  success: boolean;
  serverTimestamp?: number;
  conflictDetected?: boolean;
  error?: string;
}
```

```typescript
// storage/SQLiteDatabase.ts
// Abstraksi driver SQLite berbasis JSI (misal: react-native-nitro-sqlite / op-sqlite)
export interface DatabaseDriver {
  execute(query: string, params?: unknown[]): Promise<{ rows: unknown[] }>;
  executeTransaction(queries: { query: string; params?: unknown[] }[]): Promise<void>;
}

export class AppDatabase {
  private static instance: AppDatabase;
  private db: DatabaseDriver;

  private constructor(driver: DatabaseDriver) {
    this.db = driver;
  }

  public static initialize(driver: DatabaseDriver): AppDatabase {
    if (!AppDatabase.instance) {
      AppDatabase.instance = new AppDatabase(driver);
    }
    return AppDatabase.instance;
  }

  public static getInstance(): AppDatabase {
    if (!AppDatabase.instance) {
      throw new Error('AppDatabase belum diinisialisasi');
    }
    return AppDatabase.instance;
  }

  public async initSchema(): Promise<void> {
    await this.db.execute(`
      CREATE TABLE IF NOT EXISTS mutation_outbox (
        id TEXT PRIMARY KEY,
        idempotencyKey TEXT UNIQUE NOT NULL,
        entityName TEXT NOT NULL,
        entityId TEXT NOT NULL,
        action TEXT NOT NULL,
        payload TEXT NOT NULL,
        createdAt INTEGER NOT NULL,
        updatedAt INTEGER NOT NULL,
        retryCount INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL,
        lastErrorMessage TEXT
      );
    `);
    await this.db.execute(`
      CREATE INDEX IF NOT EXISTS idx_outbox_processing 
      ON mutation_outbox(status, createdAt);
    `);
  }

  public getDriver(): DatabaseDriver {
    return this.db;
  }
}
```

```typescript
// network/CircuitBreaker.ts
export enum CircuitState {
  CLOSED,
  OPEN,
  HALF_OPEN,
}

export class CircuitBreaker {
  private state: CircuitState = CircuitState.CLOSED;
  private failureCount: number = 0;
  private lastFailureTime: number = 0;

  constructor(
    private readonly failureThreshold: number = 5,
    private readonly resetTimeoutMs: number = 30000
  ) {}

  public canExecute(): boolean {
    if (this.state === CircuitState.OPEN) {
      const now = Date.now();
      if (now - this.lastFailureTime > this.resetTimeoutMs) {
        this.state = CircuitState.HALF_OPEN;
        return true;
      }
      return false;
    }
    return true;
  }

  public recordSuccess(): void {
    this.failureCount = 0;
    this.state = CircuitState.CLOSED;
  }

  public recordFailure(): void {
    this.failureCount++;
    this.lastFailureTime = Date.now();
    if (this.failureCount >= this.failureThreshold) {
      this.state = CircuitState.OPEN;
    }
  }

  public getState(): CircuitState {
    return this.state;
  }
}
```

```typescript
// sync/MutationOutboxService.ts
import { AppDatabase } from '../storage/SQLiteDatabase';
import { OutboxMutation, SyncResult } from '../types/sync';
import { CircuitBreaker } from '../network/CircuitBreaker';
import { calculateFullJitterDelay } from '../utils/backoff';

export class MutationOutboxService {
  private isProcessing: boolean = false;

  constructor(
    private readonly db = AppDatabase.getInstance().getDriver(),
    private readonly circuitBreaker = new CircuitBreaker(),
    private readonly maxRetriesThreshold = 5
  ) {}

  /**
   * Enqueue mutation ke persistent database secara transaksional
   */
  public async enqueueMutation<T extends Record<string, unknown>>(
    entityName: string,
    entityId: string,
    action: 'CREATE' | 'UPDATE' | 'DELETE',
    payload: T,
    idempotencyKey: string
  ): Promise<void> {
    const id = `mut_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
    const now = Date.now();

    await this.db.execute(
      `INSERT INTO mutation_outbox (
        id, idempotencyKey, entityName, entityId, action, payload, createdAt, updatedAt, retryCount, status
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 'ENQUEUED');`,
      [id, idempotencyKey, entityName, entityId, action, JSON.stringify(payload), now, now]
    );

    // Memicu trigger sync secara aman di background thread
    this.processQueue().catch((err) => {
      console.error('[SyncOutbox] Async trigger processing error:', err);
    });
  }

  /**
   * Worker Loop utama untuk eksekusi antrean Outbox
   */
  public async processQueue(): Promise<void> {
    if (this.isProcessing) return;
    if (!this.circuitBreaker.canExecute()) {
      console.warn('[SyncOutbox] Circuit Breaker is OPEN. Membatalkan pemrosesan.');
      return;
    }

    this.isProcessing = true;

    try {
      const { rows } = await this.db.execute(
        `SELECT * FROM mutation_outbox 
         WHERE status IN ('ENQUEUED', 'FAILED_RETRYABLE') 
         ORDER BY createdAt ASC LIMIT 1;`
      );

      if (rows.length === 0) {
        this.isProcessing = false;
        return;
      }

      const rawMutation = rows[0] as any;
      const mutation: OutboxMutation = {
        ...rawMutation,
        payload: JSON.parse(rawMutation.payload),
      };

      // Set status menjadi PROCESSING untuk mencegah konkurensi antar-thread
      await this.db.execute(
        `UPDATE mutation_outbox SET status = 'PROCESSING', updatedAt = ? WHERE id = ?;`,
        [Date.now(), mutation.id]
      );

      const result = await this.dispatchToServer(mutation);

      if (result.success) {
        this.circuitBreaker.recordSuccess();
        // Hapus mutasi yang telah berhasil dicatat server
        await this.db.execute(`DELETE FROM mutation_outbox WHERE id = ?;`, [mutation.id]);
      } else {
        await this.handleMutationFailure(mutation, result.error ?? 'Unknown error');
      }
    } catch (criticalError: any) {
      console.error('[SyncOutbox] Fatal loop error:', criticalError);
      this.circuitBreaker.recordFailure();
    } finally {
      this.isProcessing = false;
    }
  }

  private async handleMutationFailure(mutation: OutboxMutation, errorMessage: string): Promise<void> {
    this.circuitBreaker.recordFailure();
    const nextRetryCount = mutation.retryCount + 1;
    const now = Date.now();

    if (nextRetryCount >= this.maxRetriesThreshold) {
      // Pindahkan ke Dead Letter Status
      await this.db.execute(
        `UPDATE mutation_outbox 
         SET status = 'DEAD_LETTER', retryCount = ?, updatedAt = ?, lastErrorMessage = ? 
         WHERE id = ?;`,
        [nextRetryCount, now, errorMessage, mutation.id]
      );
    } else {
      // Jadwalkan ulang status FAILED_RETRYABLE
      await this.db.execute(
        `UPDATE mutation_outbox 
         SET status = 'FAILED_RETRYABLE', retryCount = ?, updatedAt = ?, lastErrorMessage = ? 
         WHERE id = ?;`,
        [nextRetryCount, now, errorMessage, mutation.id]
      );

      const delay = calculateFullJitterDelay(nextRetryCount);
      setTimeout(() => {
        this.processQueue().catch(console.error);
      }, delay);
    }
  }

  private async dispatchToServer(mutation: OutboxMutation): Promise<SyncResult> {
    try {
      // Integrasi network call dengan Idempotency Header
      const response = await fetch(`https://api.enterprise.com/v1/sync/${mutation.entityName}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Idempotency-Key': mutation.idempotencyKey,
        },
        body: JSON.stringify({
          entityId: mutation.entityId,
          action: mutation.action,
          payload: mutation.payload,
          clientTimestamp: mutation.createdAt,
        }),
      });

      if (response.ok) {
        const body = await response.json();
        return { success: true, serverTimestamp: body.serverTimestamp };
      }

      if (response.status === 409) {
        // Logika rekonsiliasi spesifik server conflict
        return { success: false, conflictDetected: true, error: 'State Conflict' };
      }

      return { success: false, error: `HTTP ${response.status}: ${response.statusText}` };
    } catch (networkError: any) {
      return { success: false, error: networkError.message };
    }
  }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Aplikasi Mobile Banking Agen Logistik Lapangan (Tier-3 Rural Areas)
- **Konteks:** Sebuah bank multinasional meluncurkan aplikasi *Micro-Loan Field Collection* untuk agen di pelosok kepulauan tanpa jaringan seluler reguler selama 8-12 jam sehari.
- **Tantangan Arsitektur:**
  1. Agen memproses ratusan transaksi pencairan pinjaman tunai secara *offline*.
  2. Terjadi manipulasi jam lokal pada perangkat Android oleh oknum agen (*local clock tampering*) untuk mengakali batas bunga keterlambatan.
  3. Serangan MITM di warung kopi dengan Wi-Fi publik saat agen melakukan sinkronisasi di akhir hari.
  4. Database lokal di-dump menggunakan ADB pada perangkat murah yang belum terkunci *bootloader*-nya.
- **Solusi Rekayasa:**
  1. **Clock Skew Mitigation:** Mengganti pembacaan `Date.now()` sistem OS dengan **Hybrid Logical Clock (HLC)** yang disinkronkan ke TrueTime API bank melalui header respons HTTP tiap kali ada koneksi. Setiap mutasi menyertakan *HLC tuple* `(l, c)`.
  2. **Security at Rest:** Database SQLite dienkripsi total via SQLCipher AES-256. *Key derivation* dilakukan saat login menggunakan kombinasi PIN agen + *Hardware Root of Trust* via Android Keystore `MasterKey` dengan flag `setUserAuthenticationRequired(true)`.
  3. **Transit Defense:** Native OkHttp / URLSession dikonfigurasi menggunakan **SPKI Fingerprint Pinning** (dua backup pins hardcoded di layer C++/JSI core). Jika sertifikat dipalsukan, jaringan menolak transmisi data secara absolut.
  4. **Strict Idempotency:** Setiap pencairan tunai menghasilkan `UUIDv5(agentId + accountId + hlcTimestamp)`. Server bank menolak eksekusi ganda jika agen mencoba melakukan sinkronisasi ulang paket data secara manual.

---

### 9. Trade-offs

```
                           [Arsitektur Offline]
                                     │
                 ┌───────────────────┴───────────────────┐
                 ▼                                       ▼
       [Optimistic UI Update]                 [Pessimistic Locking]
        - User Experience: Instan               - UX: Terblokir Loading UI
        - Konsistensi: Eventual                 - Konsistensi: Kuat (Strong)
        - Kompleksitas: SANGAT TINGGI           - Kompleksitas: Rendah
        (Perlu Rollback & Reconciliation)
```

| Trade-off Vector | Pilihan A | Pilihan B | Analisis Rekayasa Enterprise |
| :--- | :--- | :--- | :--- |
| **Penyimpanan Lokal** | AsyncStorage / MMKV | SQLite / WatermelonDB | MMKV sangat cepat untuk *key-value*, tetapi tidak mendukung query relasional kompleks, indexing atomik multi-kolom, atau transaksi ACID yang mutlak dibutuhkan untuk *Durable Outbox Pattern*. |
| **Resolusi Konflik** | Last-Write-Wins (LWW) | CRDT (e.g. Yjs / Automerge) | LWW sederhana dan hemat CPU/Memory, namun berisiko kehilangan mutasi minor (silent data loss). CRDT menjamin nol kehilangan data matematis, namun meningkatkan konsumsi payload data serta kompleksitas komputasi CPU mobile saat proses deserialisasi. |
| **Keamanan Jaringan** | Trust-On-First-Use (CA OS Default) | Strict Dynamic SPKI Pinning | CA OS Default membuat setup lebih fleksibel saat rotasi sertifikat API Gateway, tetapi rentan terhadap *corporate proxy interception*. Dynamic SPKI Pinning sangat aman, namun jika sertifikat server kedaluwarsa tanpa implementasi *backup pin* yang matang, seluruh basis pengguna aplikasi mobile akan terisolasi total (*bricked connection*). |

---

### 10. Common Mistakes & Troubleshooting

#### A. Kesalahan Fatal yang Sering Terjadi
1. **Unbounded Mutation Growth:** Membiarkan mutasi yang berulang kali gagal (misal: 400 Bad Request karena bug logika backend) tetap berada di status antrean `ENQUEUED`. Hal ini menyebabkan penyumbatan antrean mutasi (*Head-of-Line Blocking*) untuk seluruh entitas lainnya.
2. **Insecure Keystore Caching:** Menyimpan passphrase database SQLCipher ke dalam plaintext `MMKV` atau `AsyncStorage` demi kenyamanan *developer experience* agar tidak perlu autentikasi ulang.
3. **Optimistic Race Conditions:** Menimpa entitas yang baru saja dimutasi optimistik dengan respons data *stale* (usang) yang berasal dari background sync yang dipicu sebelum mutasi lokal terjadi.

#### B. Diagnostic Matrix & Root Cause Remediation

| Gejala Masalah (Symptom) | Kemungkinan Akar Masalah (Root Cause) | Tindakan Koreksi (Remediation) |
| :--- | :--- | :--- |
| Database crash dengan kode error: `file is not a database` saat startup. | Kunci enkripsi SQLCipher yang didekripsi dari Keystore korup atau salt PBKDF2 tidak konsisten antar app restart. | Pastikan hardware key alias tidak terhapus saat lifecycle backup OS; gunakan safe fallback yang memaksa logout bersih (*clean session purge*) jika dekripsi hardware gagal permanen. |
| Permintaan API gagal dengan error: `javax.net.ssl.SSLPeerUnverifiedException`. | Public Key Pinning gagal karena server merotasi sertifikat Leaf/Intermediate tanpa aplikasi memiliki backup pin. | Konfigurasikan minimal **2 backup pins** di aplikasi: satu untuk Intermediate CA aktif saat ini, dan satu untuk Offline Disaster Recovery Root CA. |
| Pengguna melihat data kembali ke nilai lama sesaat setelah melakukan edit, lalu berubah lagi. | Optimistic write tertimpa oleh *fetch query* yang berjalan lambat dan membawa payload usang. | Terapkan monotonic sequence revision counter pada entitas lokal. Abaikan respons query jika `incoming.revision < local.revision`. |

---

### 11. Best Practices (Production Checklist)

- [ ] **Deterministic Idempotency:** Header `X-Idempotency-Key` menggunakan UUIDv4 acak atau hash deterministik `SHA-256(payload + user_id + monotonic_id)` untuk mencegah eksekusi duplikat di backend.
- [ ] **Full Jitter Implemented:** Jeda retry tidak boleh murni seragam; terapkan *Full Jitter* untuk mencegah *Thundering Herd Problem* pada API Gateway saat jaringan pulih dari gangguan massal.
- [ ] **Transaction Atomicity:** Pembaruan UI State lokal dan insersi ke antrean Outbox harus dieksekusi dalam satu blok transaksi database tunggal (`BEGIN TRANSACTION ... COMMIT`).
- [ ] **Memory Offloading:** Log mutasi yang berstatus `COMMITTED` harus dibersihkan secara berkala (*garbage collection / vacuum*) untuk mencegah pembengkakan ukuran SQLite.
- [ ] **Hardware-Backed Encryption:** Kunci database SQLCipher diturunkan dari Android Keystore (KeyGenParameterSpec dengan TEE/StrongBox) atau iOS Keychain Access Control `kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly`.
- [ ] **Zero Secrets in JavaScript Bundle:** Tidak menyimpan sertifikat privat, token permanen, atau secret key di dalam konstanta TypeScript/JS.
- [ ] **Circuit Breaker Integration:** Sinkronisasi background otomatis dihentikan jika berturut-turut menerima HTTP 503/504 guna menghemat masa pakai baterai perangkat dan utilisasi CPU.

---

### 12. Hands-on Practice

Buatlah implementasi pengujian lokal pada direktori proyek Anda: `hands-on/m02/`

#### Langkah 1: Struktur Proyek
Pastikan struktur direktori berikut terbentuk di direktori hands-on:
```bash
hands-on/m02/
├── index.ts
├── SQLiteMock.ts
├── ResilientSyncEngine.ts
└── README.md
```

#### Langkah 2: Buat Mock Database JSI Transaksional
Simulasikan perilaku database SQLite dengan kapabilitas ACID di `hands-on/m02/SQLiteMock.ts`:

```typescript
// hands-on/m02/SQLiteMock.ts
export interface QueryTask {
  query: string;
  params?: unknown[];
}

export class SQLiteMock {
  private tables: Map<string, Array<Record<string, any>>> = new Map();

  constructor() {
    this.tables.set('mutation_outbox', []);
  }

  public async execute(query: string, params: unknown[] = []): Promise<{ rows: any[] }> {
    const trimmed = query.trim().toUpperCase();

    if (trimmed.startsWith('INSERT INTO MUTATION_OUTBOX')) {
      const row = {
        id: params[0],
        idempotencyKey: params[1],
        entityName: params[2],
        entityId: params[3],
        action: params[4],
        payload: params[5],
        createdAt: params[6],
        updatedAt: params[7],
        retryCount: params[8],
        status: params[9],
      };
      this.tables.get('mutation_outbox')!.push(row);
      return { rows: [] };
    }

    if (trimmed.startsWith('SELECT * FROM MUTATION_OUTBOX')) {
      const records = this.tables.get('mutation_outbox')!;
      const filtered = records.filter(r => r.status === 'ENQUEUED' || r.status === 'FAILED_RETRYABLE');
      return { rows: [...filtered] };
    }

    if (trimmed.startsWith('UPDATE MUTATION_OUTBOX SET STATUS = ?')) {
      const status = params[0];
      const updatedAt = params[1];
      const id = params[2];
      const record = this.tables.get('mutation_outbox')!.find(r => r.id === id);
      if (record) {
        record.status = status;
        record.updatedAt = updatedAt;
      }
      return { rows: [] };
    }

    if (trimmed.startsWith('DELETE FROM MUTATION_OUTBOX')) {
      const id = params[0];
      const items = this.tables.get('mutation_outbox')!;
      const index = items.findIndex(r => r.id === id);
      if (index !== -1) {
        items.splice(index, 1);
      }
      return { rows: [] };
    }

    return { rows: [] };
  }

  public dumpTable(tableName: string) {
    return this.tables.get(tableName) || [];
  }
}
```

#### Langkah 3: Eksekusi Test Harness Resiliency
Tulis pengujian skenario kegagalan jaringan di `hands-on/m02/index.ts`:

```typescript
// hands-on/m02/index.ts
import { SQLiteMock } from './SQLiteMock';

async function runScenario() {
  console.log('=== Memulai Praktikum Offline-First Durable Outbox Engine ===');
  const db = new SQLiteMock();

  // 1. Simulasikan mutasi masuk saat offline
  const mockMutation = [
    'mut_001',
    'idemp_abc123',
    'Order',
    'ord_999',
    'CREATE',
    JSON.stringify({ item: 'Secure Hardware Token', amount: 500 }),
    Date.now(),
    Date.now(),
    0,
    'ENQUEUED'
  ];

  console.log('[1] Mengantrekan mutasi lokal...');
  await db.execute(
    'INSERT INTO MUTATION_OUTBOX (id, idempotencyKey, entityName, entityId, action, payload, createdAt, updatedAt, retryCount, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
    mockMutation
  );

  console.log('Isi Outbox saat ini:', db.dumpTable('mutation_outbox'));

  // 2. Eksekusi pemrosesan awal
  console.log('\n[2] Memulai worker pemrosesan queue...');
  const pending = await db.execute('SELECT * FROM MUTATION_OUTBOX');
  if (pending.rows.length > 0) {
    const item = pending.rows[0];
    console.log(`Mengambil item ${item.id} untuk diproses. Mengubah status -> PROCESSING`);
    await db.execute('UPDATE MUTATION_OUTBOX SET STATUS = ?, UPDATEDAT = ? WHERE ID = ?', ['PROCESSING', Date.now(), item.id]);
  }

  // 3. Simulasikan network outage: Rollback ke FAILED_RETRYABLE
  console.log('\n[3] Jaringan terputus (503 Service Unavailable). Mengubah status -> FAILED_RETRYABLE');
  await db.execute('UPDATE MUTATION_OUTBOX SET STATUS = ?, UPDATEDAT = ? WHERE ID = ?', ['FAILED_RETRYABLE', Date.now(), 'mut_001']);
  console.log('Isi Outbox pasca kegagalan:', db.dumpTable('mutation_outbox'));

  // 4. Jaringan pulih, kirim mutasi berhasil
  console.log('\n[4] Jaringan pulih. Memproses ulang item...');
  await db.execute('DELETE FROM MUTATION_OUTBOX WHERE ID = ?', ['mut_001']);
  console.log('Isi Outbox pasca sukses komit:', db.dumpTable('mutation_outbox'));
  console.log('=== Praktikum Selesai Secara Deterministik ===');
}

runScenario().catch(console.error);
```

Jalankan skrip menggunakan Node/ts-node runtime:
```bash
npx ts-node hands-on/m02/index.ts
```

---

### 13. Exercises

#### Level Easy
Buat fungsi murni `generateIdempotencyKey(userId: string, payload: object, clientTimestamp: number): string` yang mengembalikan hash SHA-256 hex string deterministik. Fungsi harus menjamin bahwa variasi urutan key properti pada `payload` tidak mengubah nilai hash yang dihasilkan.

#### Level Medium
Kembangkan kelas `DeadLetterQueueManager` yang mengumpulkan seluruh mutasi outbox dengan status `DEAD_LETTER`. Lengkapi dengan metode:
1. `purgeExhaustedMutations()`: Membersihkan item yang melewati retensi waktu tertentu.
2. `exportDiagnosticsPayload()`: Menghasilkan format JSON terenkripsi untuk diunggah ke backend crash-analytics.

#### Level Hard
Rancang dan implementasikan engine sinkronisasi rekonsiliasi tiga arah (*3-Way Merge Engine*) untuk mengatasi konflik update profil offline:
- Input: `Base State` (versi data terakhir yang diketahui kedua pihak), `Local State` (hasil mutasi offline agen), dan `Remote Server State` (state terkini di database pusat).
- Aturan: Field yang tidak saling bertabrakan harus langsung dimerge; jika ada tabrakan pada field yang sama, selesaikan dengan strategi delegasi custom resolver callback yang dapat diinjeksikan secara modular.

---

### 14. Challenge

#### Skenario Sistem Rekam Medis Bencana Alam (Air-Gapped Sync)
Sebuah tim medis gawat darurat ditugaskan pada zona gempa vulkanik tanpa akses internet sama sekali selama berminggu-minggu. Setiap paramedis membawa tablet React Native untuk mencatat triase pasien, pemberian obat anestesi dosis tinggi (yang memiliki limitasi hukum ketat), dan tindakan bedah darurat.

Sinkronisasi antar tablet hanya dapat terjadi melalui jaringan lokal *Ad-hoc Wi-Fi Mesh / Bluetooth Low Energy (BLE)* saat dua paramedis berpapasan dalam jarak dekat.

**Tugas Arsitektur:**
1. Desain skema data penyimpanan lokal yang mencegah *double-allocation* kuota obat terbatas antar tablet independen tanpa koneksi server terpusat.
2. Tentukan bagaimana struktur data CRDT (misal: *Bounded Counter* atau *LWW-Element-Set*) diimplementasikan di atas SQLite mobile untuk menjamin konvergensi state logis triase pasien saat dua perangkat bersinkronisasi lewat koneksi P2P yang terputus-putus (*flaky local peer connection*).
3. Buat rancangan proteksi integritas kriptografi: Bagaimana membuktikan bahwa catatan pemberian obat tidak diubah secara ilegal oleh pihak luar saat tablet berada di tenda darurat tanpa autentikasi server OAuth?

*Catatan: Selesaikan rancangan ini dalam bentuk dokumen arsitektur komprehensif, class design diagram, dan interface TypeScript tingkat lanjut.*

---

### 15. Quiz Evaluasi Pemahaman

#### Pertanyaan Basic
1. Apa alasan utama kegagalan penanganan offline jika aplikasi hanya mengandalkan in-memory state manager (seperti vanilla Redux) tanpa persistent storage?
2. Dalam algoritma Exponential Backoff, apa peran utama penambahan komponen *Full Jitter* dibandingkan penambahan interval delay statis?
3. Mengapa pembacaan timestamp dari jam perangkat `Date.now()` berbahaya jika dijadikan acuan tunggal dalam penyelesaian konflik mutasi offline?
4. Apa fungsi dari header HTTP `X-Idempotency-Key` dalam arsitektur transmisi data mobile?
5. Mengapa SSL Pinning publik lebih disarankan memvalidasi hash *Subject Public Key Info* (SPKI) dibandingkan memvalidasi sertifikat *Leaf* secara utuh (Full Certificate Pinning)?

#### Pertanyaan Intermediate
6. Bagaimana status `PROCESSING` pada Durable Mutation Outbox mencegah terjadinya *race conditions* saat aplikasi memiliki beberapa thread worker atau service background aktif?
7. Jelaskan siklus transisi status pada implementasi *Circuit Breaker Pattern* (`CLOSED`, `OPEN`, `HALF_OPEN`) dan bagaimana keterkaitannya dengan proteksi konsumsi daya baterai perangkat mobile!
8. Apa perbedaan struktural antara *State-based CRDT* dan *Operation-based CRDT*, serta mana yang lebih cocok untuk arsitektur mobile berlatar belakang koneksi data paket buruk?
9. Jelaskan bagaimana serangan *Man-In-The-Middle* (MITM) tetap dapat terjadi pada aplikasi mobile meskipun komunikasi sudah menggunakan protokol HTTPS standar jika tidak dilengkapi Public Key Pinning!
10. Bagaimana enkripsi SQLite berbasis SQLCipher melindungi data dari skenario ekstraksi memori fisik melalui *ADB backup* atau pembacaan storage di perangkat berstatus *rooted*?

#### Skenario Kasus Produksi
11. **Skenario 1:** Tim QA menemukan bahwa ketika pengguna menekan tombol "Bayar Tagihan" sebanyak 3 kali berturut-turut pada kondisi jaringan lambat (2G connection), pengguna mendapati saldo terpotong 2 kali di sistem backend core-banking. Selidiki pada layer mana kecacatan implementasi terjadi dan rancang arsitektur perbaikannya!
12. **Skenario 2:** Setelah merilis pembaruan sertifikat domain API Gateway di sisi infrastruktur cloud, 40% pengguna lama aplikasi mobile Anda tidak dapat melakukan login sama sekali dan menampilkan error TLS Handshake Failure secara terus-menerus. Aplikasi tidak dapat diperbaiki melalui CodePush karena jaringan terblokir total. Apa kesalahan fatal dalam strategi certificate pinning yang dilakukan, dan bagaimana prosedur mitigasi daruratnya?
13. **Skenario 3:** Aplikasi gudang (*Warehouse Logistics*) mengalami penurunan drastis pada frame rate UI (jank/stutter parah hingga ANR - *Application Not Responding*) setiap kali koneksi jaringan kembali terhubung setelah fase offline selama 4 jam. Analisis penyebab performa buruk ini dari kacamata thread React Native dan JSI execution context, serta berikan solusi arsitekturnya!

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Jawaban Basic
1. In-memory state akan hilang seketika jika aplikasi ditutup paksa oleh OS (Android LMK - *Low Memory Killer*) atau pengguna melakukan *kill app*. Mutasi yang belum tersinkronisasi akan lenyap tanpa jejak.
2. Full Jitter menyebarkan waktu retry secara acak melintasi interval spektrum waktu. Hal ini mencegah terjadinya *Thundering Herd Problem*, yaitu kondisi di mana ribuan perangkat klien secara serentak menyerbu server pada milidetik yang sama begitu server pulih.
3. Jam sistem klien dapat dimanipulasi manual oleh pengguna, mengalami pergeseran (*clock drift*), atau tidak sinkron akibat keterlambatan sinkronisasi protokol NTP lokal, sehingga kausalitas urutan mutasi menjadi bias.
4. Memberikan penanda identitas unik dan deterministik bagi operasi request. Jika request terputus di tengah jalan namun sempat diproses server, retry berikutnya dengan key yang sama tidak akan mengeksekusi logika bisnis dua kali di server.
5. Memvalidasi SPKI (public key) memungkinkan perpanjangan masa berlaku sertifikat (renewal leaf certificate) asalkan key-pair yang digunakan tetap sama, tanpa menyebabkan aplikasi mobile *crash* atau terblokir akibat masa berlaku sertifikat lama habis.

#### Jawaban Intermediate
6. Status `PROCESSING` bertindak sebagai *optimistic lock* pada tingkat database lokal. Worker lain yang membaca antrean akan melewati record tersebut sehingga tidak akan terjadi pengiriman payload ganda secara bersamaan di kanal HTTP.
7. Sirkuit dimulai dari `CLOSED` (normal). Jika terjadi kegagalan beruntun melebihi *threshold*, sirkuit meloncat ke `OPEN` di mana request langsung ditolak tanpa memicu radio antena transmisi (menghemat baterai). Setelah batas jeda waktu (*cooldown*), sirkuit menjadi `HALF_OPEN` untuk menguji satu request percontohan ke remote endpoint.
8. *State-based CRDT* mengirimkan seluruh state saat ini dan membutuhkan operasi merge yang idempotent serta komutatif, sangat cocok untuk mobile karena paket data yang hilang atau urutan yang tertukar di jaringan fluktuatif tidak merusak konvergensi akhir.
9. Penyerang dapat menginstal sertifikat *Custom Root CA* ke dalam system trust store perangkat pengguna (melalui root tool, malware, atau profil enterprise), sehingga OS memvalidasi proxy jahat tersebut sebagai otoritas valid jika aplikasi tidak memverifikasi pin publik internalnya.
10. SQLCipher mengenkripsi setiap *page* database di disk storage menggunakan enkripsi tingkat militer AES-256 dengan *per-page IV and HMAC check*. Tanpa kunci dekripsi yang tersimpan aman di Secure Enclave/TEE, file database yang disalin via ADB hanya berupa deretan *pseudorandom bytes* yang tidak terbaca.

#### Jawaban Kasus Produksi
11. **Analisis & Solusi:** Kecacatan terletak pada tidak adanya *Immediate Client-Side Debouncing* dan ketiadaan *Durable Idempotency Key*. Begitu tombol ditekan, tombol harus langsung dinonaktifkan di UI layer, sebuah UUIDv4 harus dibuat dan disimpan bersama mutasi ke dalam transaksi lokal SQLite, lalu dikirimkan via header `X-Idempotency-Key`. Backend core-banking wajib mengimplementasikan tabel idempotensi terdistribusi (Redis/Postgres) untuk mengabaikan eksekusi transaksi jika key yang sama sudah dalam tahap pemrosesan atau selesai.
12. **Analisis & Solusi:** Tim infrastruktur merotasi sertifikat tanpa menyiapkan strategi *Key Rollover* dan aplikasi tidak memiliki *Backup Pin* (cadangan SPKI Intermediate/Root). Mitigasi darurat: Jika aplikasi native mengizinkan *Cleartext fallback* (sangat jarang dan tidak aman) atau memiliki endpoint cadangan tanpa pinning, arahkan traffic DNS ke sana. Jika tidak, satu-satunya jalan keluar adalah merilis *emergency binary update* ke Google Play Store dan Apple App Store dengan konfigurasi pin baru yang cocok, sambil mengaktifkan opsi *Force Update*.
13. **Analisis & Solusi:** Saat koneksi pulih, background sync worker melakukan iterasi ribuan data mutasi outbox secara sinkron di JavaScript thread utama atau melakukan serialization JSON payload berukuran besar yang memblokir *JS Event Loop*. Solusi:
    - Pindahkan pemrosesan antrean ke background thread via native worker TurboModule / Worklets.
    - Batasi eksekusi dalam mekanisme batching bertahap (*chunking*, misal: 10 item per batch dengan jeda micro-task).
    - Pastikan semua query SQLite dieksekusi secara asinkron via JSI bindings tanpa membebani jembatan komunikasi UI thread.

---

### 16. Summary

Arsitektur *Offline-First* pada React Native enterprise bukan sekadar pelengkap fungsionalitas, melainkan fondasi mutlak untuk menjamin ketersediaan (*availability*), keandalan (*resiliency*), dan integritas data tingkat tinggi. 

Dengan memadukan:
1. **Durable Mutation Outbox Pattern** berbasis SQLite lokal terenkripsi,
2. **Deterministic Conflict Resolution** yang berbasis pada model kausalitas logis,
3. **Resilient Network Dispatching** yang dilindungi oleh Circuit Breakers dan Exponential Jitter, serta
4. **Zero-Trust Security Perimeter** melalui integrasi SPKI Pinning dan Hardware-backed Keystore,

aplikasi mobile Anda memiliki ketahanan arsitektural yang mampu menghadapi anomali jaringan terburuk sekaligus menjaga keamanan aset data pengguna dengan standar industri tertinggi.