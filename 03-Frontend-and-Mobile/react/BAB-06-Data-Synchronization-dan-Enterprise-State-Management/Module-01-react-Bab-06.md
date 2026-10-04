# SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** 03-Frontend-and-Mobile
*   **Topik Utama:** React
*   **Bab:** 06
*   **Modul:** 01
*   **Judul Modul:** Data Synchronization & Enterprise State Management
*   **Tingkat Kesulitan:** Advanced / Staff Engineer Level
*   **Prasyarat Konseptual:** 
    *   Siklus hidup React (Mounting, Updating, Unmounting), Fiber Reconciliation, dan Rules of Hooks (`useEffect`, `useLayoutEffect`, `useSyncExternalStore`).
    *   State Management Paradigms: Immutable Update Patterns, Flux Architecture, Finite State Machines (FSM).
    *   Jaringan & Protokol: HTTP/REST, WebSocket, Server-Sent Events (SSE), Optimistic UI Updates, Exponential Backoff, Idempotency Keys.
    *   TypeScript Tingkat Lanjut: Generics, Discriminated Unions, Template Literal Types, Infer, dan Type Narrowing.

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, engineer diharapkan mampu:

1.  **Mendekomposisi State Boundaries:** Memisahkan secara tegas antara *Server State* (asinkron, shared ownership, stale-by-nature) dan *Client State* (sinkron, transient, UI-bound) menggunakan model arsitektur modern.
2.  **Merancang Sync Engine Mandiri:** Mengimplementasikan mesin sinkronisasi data modular berbasis pub/sub yang terintegrasi dengan React Core via hook `useSyncExternalStore` tanpa tearing pada concurrent rendering.
3.  **Mengimplementasikan Optimistic Updates dengan Rollback Deterministic:** Membangun alur mutasi yang mengeksekusi patch state secara optimis, mengelola buffer snapshot, dan melakukan rollback otomatis saat jaringan mengalami kegagalan.
4.  **Menerapkan Strategi Rekonsiliasi Konflik Lintas Tab:** Menyelesaikan write-conflicts menggunakan *Last-Write-Wins (LWW)* dan *Vector Clocks / Lamport Timestamps* melalui Web Storage Events dan BroadcastChannel API.
5.  **Mencegah Cascading Rerenders pada Enterprise Scale:** Mengisolasi re-render tree komponen React melalui selektor atomik terkomputasi, struktur state yang terdenormalisasi, dan memory leak mitigation.

---

# SEKSI 03 — MINDSET & MENTAL MODEL

Dalam skala enterprise, sebagian besar masalah arsitektur frontend berakar dari satu kesalahpahaman fundamental: **memperlakukan data yang bersumber dari server sebagai "state" lokal yang statis.**

```
               [ PARADIGMA KELIRU: GLOBAL STORE TUNGGAL ]
   API Data ----> Redux/Zustand Store (Sebagai Single Source of Truth)
                         │
                         ├─> State Stale? Tidak Tahu.
                         ├─> Cache Invalidation? Manual & Rawan Bug.
                         └─> Konflik Jaringan? State Rusak (Out-of-Sync).

             [ PARADIGMA MODERN: SEPARATION OF CONCERNS ]
   SERVER STATE (Cache Jarak Jauh)    vs.    CLIENT STATE (Epik / Transient)
   - Read-Through Cache                      - UI Modals / Drawer State
   - Invalidation by Tags / TTL              - Form Input Buffer
   - Snapshot & Rollback Capability          - Multi-step Wizard Step Index
   - Ownership: Database Server              - Ownership: Single Browser Runtime
```

### 1. Server State Adalah Remote Cache
Data yang didapatkan dari REST atau GraphQL bukanlah milik runtime browser; data tersebut hanyalah **snapshot temporal** dari database jarak jauh yang berpotensi langsung usang (*stale*) tepat pada milidetik respons HTTP diterima. Oleh karena itu, mental model yang benar adalah memperlakukan lapisan penampung server data di frontend bukan sebagai *State Store*, melainkan sebagai **Cache Client Layer** yang memiliki strategi revalidasi, invalidasi, garbage collection, dan mutasi optimistik.

### 2. Client State Adalah Deterministic State Machine
Client-side state harus dibatasi hanya untuk data yang kelangsungan hidupnya dikendalikan 100% oleh sesi pengguna saat ini (misalnya: apakah modal terbuka, tab aktif, draft input lokal). State jenis ini tidak membutuhkan caching multi-menit atau penanganan *stale-while-revalidate*, melainkan determinisme berbasis Finite State Machine (FSM) yang menjamin UI tidak pernah berada dalam kondisi invalid (*impossible states*).

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Di bawah ini adalah arsitektur sinkronisasi data enterprise lengkap yang mencakup Mutation Lifecycle, Optimistic UI, BroadcastChannel Multi-tab Sync, dan Automatic Rollback.

```
+--------------------------------------------------------------------------------------------------+
|                                    REACT COMPONENT TREE                                          |
+--------------------------------------------------------------------------------------------------+
          │                                                         ▲
   (1) Dispatches Mutation                                   (6) Render UI (Optimistic/Confirmed)
          │                                                         │
          ▼                                                         │
+-------------------------------------------------------------------+------------------------------+
|                                ENTERPRISE SYNC ENGINE CORE                                       |
+--------------------------------------------------------------------------------------------------+
|                                                                                                  |
|   +─────────────────────────+          Snapshot         +──────────────────────────────+         |
|   |   Optimistic Update     | ────────────────────────> |    Rollback Memory Buffer    |         |
|   |   Controller            |                           |    (LRU Mutation Stack)      |         |
|   +─────────────────────────+                           +──────────────────────────────+         |
|                │                                                        ▲                        |
|                │ (2) Apply Instant Cache Patch                          │ (Rollback triggered    |
|                ▼                                                        │  on 4xx/5xx / Timeout) |
|   +─────────────────────────+                                           │                        |
|   |  InMemory Entity Store  |                                           │                        |
|   |  (Normalized by ID)     |                                           │                        |
|   +─────────────────────────+                                           │                        |
|          │             ▲                                                │                        |
|          │             │ (5) Patch Confirmed / Rollback                 │                        |
|          │             │                                                │                        |
|          ▼             │                                                │                        |
|   +───────────────────────────────────+                                 │                        |
|   |   Network Coordination Engine     | ────────────────────────────────+                        |
|   |   (Axios/Fetch + Idempotency-Key) |                                                          |
|   +───────────────────────────────────+                                                          |
|          │                      ▲                                                                |
|          │ (3) HTTP POST/PUT    │ (4) HTTP 200 OK / Error                                        |
+----------┼──────────────────────┼────────────────────────────────────────────────────────────────+
           │                      │
           ▼                      │
+─────────────────────────────────────────+        +───────────────────────────────────────────────+
|         ENTERPRISE REST/GRAPHQL         |        |             OTHER BROWSER TABS                |
|               BACKEND                   |        +───────────────────────────────────────────────+
+─────────────────────────────────────────+                               ▲
                                                                          │
                                       (7) Broadcast Sync Event           │
                                           via BroadcastChannel           │
                                    ──────────────────────────────────────+
```

### Siklus Alur Data:
1. **Trigger:** Komponen memicu mutasi (misal: Update Role Pengguna).
2. **Snapshot & Optimistic Patch:** Engine mengambil snapshot state saat ini ke dalam *Rollback Memory Buffer*, lalu seketika memperbarui *InMemory Entity Store* dengan perkiraan state baru dan memberitahukan React melalui `useSyncExternalStore`.
3. **Network Dispatch:** Permintaan jaringan dikirim secara asinkron dengan menyertakan HTTP Header `Idempotency-Key` unik (UUIDv4) untuk mencegah pemrosesan ganda pada *retry network*.
4. **Respon Sukses:** Jika HTTP 200/201 kembali, engine menimpa entitas optimis dengan payload resmi dari server, menghapus entri di *Rollback Memory Buffer*, dan menyiarkan event pembaruan via `BroadcastChannel`.
5. **Respon Gagal / Timeout:** Jika network error (4xx/5xx/timeout), engine menarik data dari *Rollback Memory Buffer*, memulihkan state entitas ke kondisi awal, memicu notifikasi error global, dan merender ulang React Tree kembali ke status valid.
6. **Lintas Tab:** Tab lain menerima pesan via `BroadcastChannel`, lalu menandai cache terkait sebagai *stale* atau langsung melakukan patch memori secara instan.

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Dekonstruksi Mekanisme `useSyncExternalStore`
Dalam React 18+, Concurrent Renderer dapat menangguhkan (*suspend*), menghentikan sementara, atau membuang render pass di tengah jalan. Pola lama seperti `useEffect` + `useState` untuk mendengarkan store eksternal memicu bug fatal bernama **tearing**: sebuah inkonsistensi visual di mana dua komponen dalam satu render cycle membaca dua nilai yang berbeda dari store eksternal yang sama karena store termutasi di tengah proses rendering konkuren.

```
   [ RENDER PASS DIMULAI ] ───────────────────────────────────────────┐
              │                                                       │
              ▼                                                       ▼
   Komponen A membaca Store: v1                             Komponen B membaca Store: v2
              │                                                       │
              └───────────────> [ STORE BERMUTASI DI SINI ] ──────────┘
                                (TEARING TERJADI!)
```

`useSyncExternalStore` menyelesaikan ini dengan memvalidasi konsistensi secara sinkron:
```typescript
function useSyncExternalStore<Snapshot>(
  subscribe: (onStoreChange: () => void) => () => void,
  getSnapshot: () => Snapshot,
  getServerSnapshot?: () => Snapshot
): Snapshot;
```
*   `subscribe`: Fungsi callback yang mendaftarkan event listener. Harus stabil (`useCallback` atau dideklarasikan di luar scope komponen).
*   `getSnapshot`: Fungsi yang mengembalikan representasi nilai saat ini dari store. **Wajib mengembalikan nilai immutable referensial yang sama (`===`) jika data di store belum berubah.** Jika fungsi ini selalu mengembalikan objek/array baru secara instan, React akan terjebak dalam *infinite render loop*.
*   `getServerSnapshot`: Digunakan saat Server-Side Rendering (SSR) dan Hydration untuk mencegah hydration mismatch.

### 2. Normalisasi Cache vs Denormalisasi
Menyimpan data API bersarang (*deeply nested*) langsung ke dalam store adalah anti-pattern enterprise.
*   **Masalah:** Data entitas pengguna yang sama muncul di 5 tempat berbeda (List Transaksi, Detail Profil, Notifikasi, Dropdown Assignee, Header). Saat nama pengguna diperbarui, sistem harus mencari dan memutasi 5 subtree tersebut.
*   **Solusi Normalisasi:** Mengikuti standar basis data relasional. Entitas dipisah menjadi tabel berbasis lookup dictionary:
```typescript
interface NormalizedState {
  entities: {
    users: Record<string, UserEntity>;
    workspaces: Record<string, WorkspaceEntity>;
    tasks: Record<string, TaskEntity>;
  };
  results: {
    dashboardTaskList: string[]; // Berisi array ID: ['task-1', 'task-2']
  };
}
```

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### 1. Vector Clocks vs Last-Write-Wins (LWW)
Pada arsitektur enterprise terdistribusi dengan banyak tab aktif, *race condition* penulisan data lokal sering kali terjadi.
*   **Last-Write-Wins (LWW):** Bergantung pada *wall-clock timestamp* klien (`Date.now()`). Sangat rentan terhadap fenomena *clock skew* (perbedaan jam internal OS klien). Namun, implementasinya cepat dan efisien secara komputasi.
*   **Logical / Lamport Timestamps:** Menggunakan angka integer monotonik yang bertambah (*monotonic counter*) setiap kali aksi terjadi. Jika Tab A mengirim event dengan counter `5`, dan Tab B melihat state lokalnya berada pada counter `6`, aksi Tab A ditolak atau digabungkan (*merge*).

### 2. Cache Invalidation Strategy: Stale-While-Revalidate (RFC 5861)
Arsitektur sync engine mengadopsi direktif HTTP RFC 5861:
1.  **Fresh Window:** Data disajikan langsung dari memori tanpa request jaringan.
2.  **Stale Window:** Data disajikan instan dari memori untuk UX optimal, namun latar belakang memicu request jaringan (*background revalidation*) untuk memperbarui memori.
3.  **Expired / Inactive:** Cache dibersihkan oleh Garbage Collector jika tidak ada komponen yang me-*mount* data tersebut dalam jangka waktu tertentu (*time-to-idle*).

### 3. Tearing Prevention Algorithm
React memeriksa apakah nilai yang dikembalikan oleh `getSnapshot` pada awal render pass bernilai identik dengan yang dikembalikan pada akhir render pass. Jika nilai berbeda akibat mutasi store yang disinkronkan oleh Web Worker, WebSocket, atau event timer, React mengabaikan hasil render konkuren yang parsial dan mengulang proses render secara sinkron dari awal pohon komponen (*de-optimizing to synchronous render*) untuk menjamin konsistensi mutlak antarmuka pengguna.

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi fundamental dari **Enterprise Sync Store** yang aman terhadap React 18 Concurrent Rendering menggunakan TypeScript native dan `useSyncExternalStore`.

```typescript
// syncStore.ts
export type Listener = () => void;

export class EnterpriseSyncStore<TState> {
  private state: TState;
  private listeners: Set<Listener> = new Set();

  constructor(initialState: TState) {
    this.state = Object.freeze(initialState);
  }

  // Mengembalikan snapshot data saat ini (Immutable)
  public getSnapshot = (): TState => {
    return this.state;
  };

  // Mekanisme registrasi subscriber untuk React
  public subscribe = (listener: Listener): (() => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };

  // Mutasi state dengan deep-freeze proteksi
  public setState(updater: (prevState: TState) => TState): void {
    const nextState = Object.freeze(updater(this.state));
    // Validasi kesamaan referensial untuk menghindari rerender sia-sia
    if (!Object.is(this.state, nextState)) {
      this.state = nextState;
      this.notify();
    }
  }

  private notify(): void {
    this.listeners.forEach((listener) => {
      try {
        listener();
      } catch (error) {
        console.error("Critical error inside store listener subscriber:", error);
      }
    });
  }
}
```

Integrasi hook custom untuk memilih slice spesifik dengan referential equality check:

```typescript
// useStoreSelector.ts
import { useSyncExternalStore, useCallback, useRef } from "react";
import { EnterpriseSyncStore } from "./syncStore";

export function useStoreSelector<TState, TSelected>(
  store: EnterpriseSyncStore<TState>,
  selector: (state: TState) => TSelected,
  isEqual: (a: TSelected, b: TSelected) => boolean = Object.is
): TSelected {
  // Simpan nilai selektor sebelumnya untuk mempertahankan referensi jika nilainya ekuivalen
  const lastSelectedRef = useRef<TSelected | undefined>(undefined);

  const getSnapshot = useCallback((): TSelected => {
    const nextSelected = selector(store.getSnapshot());
    if (
      lastSelectedRef.current !== undefined &&
      isEqual(lastSelectedRef.current, nextSelected)
    ) {
      return lastSelectedRef.current;
    }
    lastSelectedRef.current = nextSelected;
    return nextSelected;
  }, [store, selector, isEqual]);

  return useSyncExternalStore(store.subscribe, getSnapshot, getSnapshot);
}
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Analisis Berkas `syncStore.ts`:
*   **Baris 4–7:** Variabel `state` dan `listeners` dideklarasikan sebagai `private`. `listeners` menggunakan struktur data `Set<Listener>` untuk menjamin penambahan dan penghapusan callback memiliki kompleksitas $O(1)$ serta mencegah duplikasi pemanggilan callback yang sama.
*   **Baris 9:** `this.state = Object.freeze(initialState);` menerapkan pembekuan objek (*shallow freezing*) untuk mencegah mutasi state secara mutatif langsung oleh kode eksternal tanpa melalui method `setState`.
*   **Baris 13:** `public getSnapshot = (): TState => { return this.state; };` ditulis menggunakan *arrow function field syntax* untuk mengikat (`bind`) konteks `this` secara permanen, sehingga aman saat dipassing sebagai referensi callback langsung ke `useSyncExternalStore`.
*   **Baris 18–23:** Method `subscribe` mengembalikan *cleanup function* anonim. Pola ini mematuhi kontrak API yang diwajibkan oleh React Engine untuk membersihkan memori (*unsubscribe*) ketika komponen unmount.
*   **Baris 27–32:** `Object.is(this.state, nextState)` mengevaluasi mutasi. Jika mutasi menghasilkan nilai primitif atau referensi objek yang identik, proses notifikasi dihentikan segera (*early exit*), memangkas *cascading renders* yang tidak diperlukan.

### Analisis Berkas `useStoreSelector.ts`:
*   **Baris 11:** `const lastSelectedRef = useRef<TSelected | undefined>(undefined);` menyediakan container yang persisten antar render untuk melacak snapshot terakhir yang diekstrak.
*   **Baris 13–22:** `getSnapshot` dibungkus dengan `useCallback`. Jika data yang dihasilkan oleh pemanggilan `selector(store.getSnapshot())` dianggap ekuivalen berdasarkan komparasi kustom `isEqual`, kita mengembalikan nilai lama (`lastSelectedRef.current`). Ini sangat kritikal: **jika mengembalikan referensi baru pada setiap pemanggilan getSnapshot, React 18 akan mendeteksi infinite state oscillation dan melempar error `Maximum update depth exceeded`.**

---

# SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi:
Sebuah platform perbankan investasi core-trading (**FinCorp Global**) memiliki fitur **Global Portfolio Ledger**. 
*   **Masalah:** Beberapa portfolio manager membuka tab peramban secara bersamaan pada layar multimonitor mereka. Mereka melakukan alokasi dana dan persetujuan transaksi (Approval Routing). 
*   **Tantangan Sistem:**
    1.  Jika Manajer A menyetujui transaksi pada Tab 1, Tab 2 pada komputer yang sama harus langsung merefleksikan alokasi modal terkini tanpa reload.
    2.  Koneksi internet trading floor sering mengalami degradasi mikro (packet loss temporer). Eksekusi transaksi harus terlihat instan bagi UI (Optimistic Update).
    3.  Jika backend menolak mutasi (misalnya: saldo cadangan margin tidak mencukupi di server pusat — HTTP 422), frontend harus memutar balik (*rollback*) UI ke nilai akurat persis sebelum tombol ditekan dan menampilkan peringatan tanpa merusak integritas alur kerja data lainnya.
    4.  Setiap mutasi wajib menyertakan Idempotency Key unik untuk mencegah penarikan modal ganda di gateway pembayaran akibat network retries.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah arsitektur lengkap kelas industri yang mengimplementasikan **Optimistic Ledger Mutation Engine**, sinkronisasi lintas-tab melalui `BroadcastChannel`, pencegahan tearing, dan deterministic state rollback.

```typescript
// ==========================================
// 1. DOMAIN MODELS & TYPES
// ==========================================

export interface LedgerItem {
  readonly id: string;
  readonly symbol: string;
  readonly amount: number;
  readonly status: "PENDING" | "CONFIRMED" | "FAILED";
  readonly version: number;
}

export interface LedgerState {
  readonly items: Readonly<Record<string, LedgerItem>>;
  readonly order: readonly string[];
}

export type BroadcastSyncMessage = 
  | { type: "SYNC_CONFIRMED"; payload: LedgerItem }
  | { type: "INVALIDATE_ALL" };

// ==========================================
// 2. PRODUCTION MULTI-TAB SYNC ENGINE
// ==========================================

export class EnterpriseLedgerEngine {
  private state: LedgerState = { items: {}, order: [] };
  private listeners: Set<() => void> = new Set();
  private rollbackBuffer: Map<string, LedgerItem | null> = new Map();
  private broadcastChannel: BroadcastChannel;

  constructor() {
    this.broadcastChannel = new BroadcastChannel("fincorp_ledger_sync_bus");
    this.broadcastChannel.onmessage = this.handleCrossTabBroadcast;
  }

  public getSnapshot = (): LedgerState => {
    return this.state;
  };

  public subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };

  private notify(): void {
    this.listeners.forEach((listener) => listener());
  }

  // Cross-Tab Message Receiver
  private handleCrossTabBroadcast = (event: MessageEvent<BroadcastSyncMessage>) => {
    const data = event.data;
    if (data.type === "SYNC_CONFIRMED") {
      this.applyServerUpdate(data.payload, false);
    }
  };

  // Direct Cache Update
  public applyServerUpdate(item: LedgerItem, shouldBroadcast = true): void {
    const existing = this.state.items[item.id];
    
    // Concurrency check via Lamport/Version field
    if (existing && existing.version > item.version) {
      console.warn(`[SyncEngine] Ignored stale update for ${item.id}. Version: ${item.version} < ${existing.version}`);
      return;
    }

    const nextItems = { ...this.state.items, [item.id]: Object.freeze(item) };
    const nextOrder = this.state.items[item.id] 
      ? this.state.order 
      : [...this.state.order, item.id];

    this.state = {
      items: Object.freeze(nextItems),
      order: Object.freeze(nextOrder),
    };

    this.notify();

    if (shouldBroadcast) {
      this.broadcastChannel.postMessage({
        type: "SYNC_CONFIRMED",
        payload: item,
      });
    }
  }

  // ==========================================
  // 3. OPTIMISTIC MUTATION & ROLLBACK CORE
  // ==========================================

  public async executeOptimisticUpdate(
    itemId: string,
    deltaAmount: number,
    networkMutationFn: (id: string, amount: number, idempotencyKey: string) => Promise<LedgerItem>
  ): Promise<void> {
    const originalItem = this.state.items[itemId];
    if (!originalItem) {
      throw new Error(`Target ledger item [${itemId}] does not exist in store.`);
    }

    const transactionId = crypto.randomUUID();
    const idempotencyKey = `idemp-${itemId}-${Date.now()}-${transactionId}`;

    // Snapshot buffer untuk deterministic rollback
    this.rollbackBuffer.set(transactionId, { ...originalItem });

    // Step 1: Aplikasikan patch optimistik instan
    const optimisticItem: LedgerItem = {
      ...originalItem,
      amount: originalItem.amount + deltaAmount,
      status: "PENDING",
      version: originalItem.version + 1,
    };

    this.state = {
      ...this.state,
      items: Object.freeze({
        ...this.state.items,
        [itemId]: Object.freeze(optimisticItem),
      }),
    };
    this.notify();

    // Step 2: Kirim Network Request
    try {
      const serverConfirmedItem = await networkMutationFn(itemId, optimisticItem.amount, idempotencyKey);
      
      // Mutasi Sukses: Bersihkan rollback snapshot
      this.rollbackBuffer.delete(transactionId);
      
      // Terapkan data terotorisasi resmi dari server
      this.applyServerUpdate(serverConfirmedItem, true);
    } catch (networkError) {
      // Step 3: Failure Execution -> Lakukan Rollback
      console.error(`[SyncEngine] Mutation failed for ${itemId}. Rolling back changes. Error:`, networkError);

      const rollbackSnapshot = this.rollbackBuffer.get(transactionId);
      this.rollbackBuffer.delete(transactionId);

      if (rollbackSnapshot) {
        this.state = {
          ...this.state,
          items: Object.freeze({
            ...this.state.items,
            [itemId]: Object.freeze(rollbackSnapshot),
          }),
        };
      } else {
        // Fallback jika tidak ada snapshot: Hapus item dari dictionary
        const filteredItems = { ...this.state.items };
        delete filteredItems[itemId];
        this.state = {
          items: Object.freeze(filteredItems),
          order: this.state.order.filter((id) => id !== itemId),
        };
      }

      this.notify();
      throw networkError; // Re-throw ke React Component Boundary
    }
  }

  public destroy(): void {
    this.broadcastChannel.close();
    this.listeners.clear();
    this.rollbackBuffer.clear();
  }
}

// Global Singleton Instance
export const globalLedgerEngine = new EnterpriseLedgerEngine();
```

Berikut adalah integrasi langsung pada layer Presentasi React:

```tsx
// LedgerView.tsx
import React, { useSyncExternalStore, useCallback, useState } from "react";
import { globalLedgerEngine, LedgerItem } from "./EnterpriseLedgerEngine";

// Simulasi Network Call dengan Fail-Rate & Latency
async function mockServerLedgerMutation(
  id: string,
  newAmount: number,
  idempotencyKey: string
): Promise<LedgerItem> {
  await new Promise((resolve) => setTimeout(resolve, 1200));

  // Simulasi penolakan acak dari server (misal: 30% kegagalan)
  if (Math.random() < 0.3) {
    throw new Error("HTTP 422: Unprocessable Entity. Ingestion Balance Fault.");
  }

  return {
    id,
    symbol: "USD-ALLOC",
    amount: newAmount,
    status: "CONFIRMED",
    version: Date.now(), // Monotonic timestamp server
  };
}

export const LedgerView: React.FC = () => {
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isMutating, setIsMutating] = useState<boolean>(false);

  // Subscribe ke store tanpa resiko Tearing
  const ledgerState = useSyncExternalStore(
    globalLedgerEngine.subscribe,
    globalLedgerEngine.getSnapshot,
    globalLedgerEngine.getSnapshot
  );

  const handleIncrement = useCallback(async (id: string) => {
    setIsMutating(true);
    setErrorMessage(null);

    try {
      await globalLedgerEngine.executeOptimisticUpdate(
        id,
        500, // Tambah $500 secara optimis
        mockServerLedgerMutation
      );
    } catch (err: unknown) {
      if (err instanceof Error) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage("Fatal transaction error occurred.");
      }
    } finally {
      setIsMutating(false);
    }
  }, []);

  // Inisialisasi data seed untuk demo
  const handleSeedData = () => {
    globalLedgerEngine.applyServerUpdate({
      id: "acc-101",
      symbol: "USD-ALLOC",
      amount: 10000,
      status: "CONFIRMED",
      version: 1,
    });
  };

  const item = ledgerState.items["acc-101"];

  return (
    <div style={{ padding: "24px", fontFamily: "sans-serif" }}>
      <h2>FinCorp Enterprise Portfolio Ledger</h2>
      
      {!item ? (
        <button onClick={handleSeedData}>Initialize Ledger Account</button>
      ) : (
        <div style={{ border: "1px solid #ccc", padding: "16px", borderRadius: "8px", maxWidth: "400px" }}>
          <div><strong>Account ID:</strong> {item.id}</div>
          <div><strong>Symbol:</strong> {item.symbol}</div>
          <div style={{ fontSize: "20px", margin: "12px 0" }}>
            <strong>Balance:</strong> ${item.amount.toLocaleString()}
          </div>
          <div>
            <strong>Status:</strong>{" "}
            <span style={{ color: item.status === "PENDING" ? "orange" : "green" }}>
              {item.status}
            </span>
          </div>
          <div style={{ fontSize: "12px", color: "#666" }}>Version: {item.version}</div>

          <div style={{ marginTop: "16px" }}>
            <button 
              disabled={isMutating} 
              onClick={() => handleIncrement(item.id)}
              style={{ padding: "8px 16px", cursor: isMutating ? "not-allowed" : "pointer" }}
            >
              {isMutating ? "Syncing..." : "Allocate +$500"}
            </button>
          </div>
        </div>
      )}

      {errorMessage && (
        <div style={{ marginTop: "16px", color: "red", backgroundColor: "#ffebee", padding: "8px" }}>
          🚨 <strong>Rollback Executed:</strong> {errorMessage}
        </div>
      )}
    </div>
  );
};
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Parameter Evaluasi | Custom Engine (`useSyncExternalStore`) | TanStack Query (React Query) | Redux Toolkit (RTK Query) | Zustand State Store |
| :--- | :--- | :--- | :--- | :--- |
| **Model Eksekusi** | Pub/Sub murni terintegrasi langsung ke React Dispatcher | Stale-While-Revalidate Engine | Flux Architecture + Reducer Machine | Minimalist External Store Pub/Sub |
| **Ukuran Bundle (Gzip)** | ~0.5 KB (Bawaan React) | ~13 KB | ~25 KB (RTK + Store) | ~1.2 KB |
| **Optimistic Rollback** | Kustom penuh (Manual Buffer Stack) | Terintegrasi via `onMutate` Context | Terintegrasi via `onQueryStarted` lifecycle | Manual via Transient Set |
| **Cross-Tab Synchronization** | Native via BroadcastChannel API | Plugin terpisah / Experimental Sync | Memerlukan Redux-State-Sync middleware | Memerlukan manual Storage sync |
| **Pencegahan Tearing** | Terjamin secara native oleh React Fiber | Terjamin | Terjamin | Terjamin |
| **Rekomendasi Pemakaian** | Sistem core-trading, SDK privat, regulasi zero-dependency | Server-state standard aplikasi Enterprise web | Sistem state kompleks dengan regulasi event audit log | Aplikasi skala menengah dengan Client-centric state |

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. Out-of-Order Mutasi Jaringan (Network Race Condition)
*   **Kasus:** Pengguna mengklik mutasi A (penambahan $100), kemudian langsung mengklik mutasi B (penambahan $200). Request A tertunda di jaringan ISP selama 3 detik, sementara Request B berhasil selesai dalam 200 milidetik. Request A tiba belakangan di server dan menimpa hasil Request B.
*   **Mitigasi:**
    *   Sematkan atribut `version` monotonik atau Lamport Timestamp pada setiap payload request.
    *   Gunakan abort controller untuk membatalkan inflight request sebelumnya jika data bersifat *mutually exclusive*:
    ```typescript
    private activeControllers = new Map<string, AbortController>();
    // Sebelum trigger request:
    this.activeControllers.get(entityId)?.abort();
    const controller = new AbortController();
    this.activeControllers.set(entityId, controller);
    ```

### 2. Zombie Snapshots pada Rollback Buffer
*   **Kasus:** Rollback snapshot disimpan di memori heap. Jika aplikasi berjalan berjam-jam dan terjadi ribuan error yang tidak memicu penanganan blok `catch` atau komponen ter-unmount secara mendadak saat mutasi berlangsung, memori buffer akan bocor (*memory leak*).
*   **Mitigasi:** Terapkan pembersihan berbasis Time-To-Live (TTL) atau gunakan kapasitas buffer terbatas menggunakan algoritma Least Recently Used (LRU Cache).

### 3. Infinite Re-render Loop pada `getSnapshot`
*   **Kasus:** Menghasilkan referensi array/objek baru di dalam implementasi fungsi `getSnapshot`:
    ```typescript
    // FATAL BUG: Menyebabkan Infinite Render Loop di React 18+
    getSnapshot: () => store.getItems().filter(item => item.isActive)
    ```
*   **Mitigasi:** Gunakan teknik *memoized selector* atau pastikan pemfilteran data hanya dilakukan saat data di dalam store mengalami mutasi, bukan saat `getSnapshot` dipanggil oleh React reconciliation.

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Sinkronisasi Server Data Menggunakan `useEffect`
```typescript
// BURUK: Anti-pattern useEffect Fetching
useEffect(() => {
  fetchData().then(data => setServerData(data));
}, [id]);
```
*Mengapa ini salah?* Rentan race condition jika `id` berubah cepat, tidak menangani caching, menyebabkan cascading updates (*layout shifts*), dan tidak mendukung Suspense/SSR.
*Solusi:* Gunakan Sync Engine berbasis subscription atau library server-state seperti TanStack Query.

### 2. Mutasi State Secara In-Place (Mutable Modification)
```typescript
// BURUK: Melanggar Prinsip Immutability
store.state.items['acc-101'].amount = 20000;
store.notify();
```
*Mengapa ini salah?* React mendeteksi perubahan nilai snapshot via perbandingan referensial `Object.is(prevSnapshot, nextSnapshot)`. Karena referensi objek tidak berubah, React menganggap tidak ada update yang terjadi, menyebabkan layar gagal merender perubahan data (*silent UI failure*).
*Solusi:* Gunakan *shallow clone* (`{ ...item }`) atau pustaka immutability seperti `Immer`.

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Immutability Enforcement:** Gunakan `Readonly<T>` secara rekursif pada level tipe TypeScript dan terapkan `Object.freeze()` pada fase *development* untuk menjamin tidak ada mutasi state langsung dari luar store.
2.  **Idempotency Keys:** Setiap API call yang memutasi status kritis finansial wajib membawa header `Idempotency-Key` (standar IETF draft). Server mencatat key ini di Redis; jika request dengan key yang sama terkirim ulang akibat gangguan jaringan, server mengembalikan respon yang sama tanpa memproses ulang mutasi di database.
3.  **Selector Atomicity:** Komponen hanya boleh me-subscribe slice data paling kecil yang dibutuhkannya. Hindari membaca seluruh root store jika hanya membutuhkan satu string status.

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI