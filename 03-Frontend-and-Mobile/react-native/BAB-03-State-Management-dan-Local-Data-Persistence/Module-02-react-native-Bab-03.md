# Bab 03: State Management & Local Data Persistence
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
- **Menganalisis & Mengeliminasi Bottleneck Serialisasi Bridge:** Membedah perbedaan mekanisme I/O antara asynchronous bridge-based storage (`AsyncStorage`) dengan synchronous memory-mapped I/O berbasis C++ JSI (`react-native-mmkv`, `op-sqlite`).
- **Merancang Arsitektur Offline-First Skala Enterprise:** Mengimplementasikan pola *Optimistic Mutation Queue* dengan persistensi mutasi atomik, deduplikasi *network requests*, dan mekanisme resolusi konflik (*Last-Write-Wins* vs *Vector Clocks*).
- **Menerapkan Advanced State Partitioning:** Mengonfigurasi Zustand menggunakan `useSyncExternalStore` dengan *atomic selectors* dan middleware kustom guna mencegah re-render cascade pada component tree berukuran besar.
- **Mengintegrasikan Server-State Synchronization:** Menghubungkan TanStack Query (v5) dengan client storage terenkripsi melalui *persister pipelines* yang mendukung dehidrasi/rehidrasi parsial.
- **Mengaudit & Menangani Race Condition serta Memory Leaks:** Mengidentifikasi dan memitigasi *stale closures*, *leaked subscriptions*, *zombie children*, dan *concurrency write locks* pada embedded SQLite engine.

---

### 2. Prerequisites
Sebelum mempelajari modul ini, engineer wajib memiliki pemahaman mendalam tentang:
- Arsitektur React Native New Architecture (Fabric Renderer, TurboModules, dan JavaScript Interface/JSI).
- Fundamental React Hooks (`useCallback`, `useMemo`, `useRef`, dan `useSyncExternalStore`).
- Konsep dasar ACID (Atomicity, Consistency, Isolation, Durability) dan arsitektur database relasional (SQLite Engine, WAL mode).
- Teori concurrency JavaScript: Event Loop, Microtask Queue, Promise execution lifecycle, dan Web Workers/Worker Threads.

---

### 3. Concept & Internal Architecture

#### A. Evolusi Persistence Engine: JSI vs Asynchronous Bridge
Secara historis, persistensi lokal pada React Native mengandalkan `AsyncStorage`, yang bergantung pada serialization/deserialization JSON via asynchronous JSON-RPC Bridge. 

```
[Legacy Bridge Workflow]
JS Thread -> JSON.stringify() -> Bridge Queue (Async) -> Native Android/iOS -> Disk I/O
Disk I/O -> Native Callback -> Bridge Queue (Async) -> JSON.parse() -> JS Thread

[Modern JSI Architecture]
JS Engine (Hermes) <=> JSI C++ Host Object <=> MMKV / SQLite Engine <=> OS Page Cache (mmap)
```

1. **JSI (JavaScript Interface):** Memungkinkan runtime JavaScript (Hermes) memegang referensi langsung (*Host Objects*) ke objek C++. Tidak ada komputasi serialisasi string JSON, parsing, atau antrean FIFO bridge. Operasi eksekusi berlangsung secara sinkronus pada microsecond latency.
2. **Memory-Mapped I/O (`mmap`):** `react-native-mmkv` memanfaatkan sistem panggilan kernel Unix `mmap` yang memetakan file disk langsung ke virtual memory address space proses aplikasi. Operasi penulisan memodifikasi OS page cache secara instan tanpa membebani runtime JS. Kernel OS bertanggung jawab mem-flush dirty pages ke physical flash memory (NAND).

#### B. Zustand Internal State Subscriptions & `useSyncExternalStore`
Zustand mengabaikan Context API murni untuk distribusi state berfrekuensi tinggi demi menghindari context re-render cascade. Zustand mengimplementasikan pola *External Mutable Store* yang diamankan oleh React core API: `useSyncExternalStoreWithSelector`.

```
                  ┌───────────────────────────────┐
                  │   Zustand Vanilla Store       │
                  │   (Plain JS Closure Object)   │
                  └──────────────┬────────────────┘
                                 │
                   Listeners Set │ (Set<Listener>)
                                 ▼
         ┌─────────────────────────────────────────────────┐
         │              useSyncExternalStore               │
         │  - Subscribes to store changes via listeners    │
         │  - Extracts slice via selector                  │
         │  - Compares previous slice vs next (Object.is)  │
         └───────┬─────────────────────────────────┬───────┘
                 │ (Equal: Skip)                   │ (Not Equal: Trigger)
                 ▼                                 ▼
         ┌───────────────┐                 ┌───────────────┐
         │ No Re-render  │                 │ Re-render UI  │
         └───────────────┘                 └───────────────┘
```
Mekanisme ini mencegah masalah *tearing* (inkonsistensi visual ketika render konkuren React terinterupsi oleh mutasi sinkronus eksternal) sekaligus membatasi re-render hanya pada komponen yang selector slice-nya menghasilkan identitas referensial baru.

#### C. Relational Offline Engine: OP-SQLite & WAL Mode
Untuk relasi data kompleks (ratusan ribu baris), NoSQL Key-Value store tidak memadai. Digunakan embedded SQLite yang dieksekusi native melalui C++ TurboModule JSI (`op-sqlite`).
- **Write-Ahead Logging (WAL):** Modus default SQLite sering memblokir pembacaan saat penulisan berlangsung. Dengan WAL mode, operasi penulisan diarahkan ke file `*-wal` terpisah, sehingga *readers do not block writers, and writers do not block readers*.
- **Direct Memory Binding:** Parameter query dan return types dipetakan langsung dari memori C++ native ArrayBuffer ke JS ArrayBuffer tanpa konversi string intermediate.

---

### 4. Why & What

| Dimensi | Legacy Approach (AsyncStorage + Redux murni) | Modern Production Architecture (Zustand + MMKV + TanStack Query + OP-SQLite) |
| :--- | :--- | :--- |
| **I/O Latency** | Asinkronus (10ms - 150ms tergantung muatan bridge) | Sinkronus / Quasi-instant (< 0.1ms via JSI `mmap`) |
| **State Boundary** | Seluruh data (server cache & client UI) dicampur di Redux | Terisolasi: Server state di TanStack Query, Client state di Zustand, Large dataset di SQLite |
| **Cold Startup Impact**| Lambat (menunggu asinkronitas hidrasi seluruh store) | Instan (Store dihidrasi sinkronus dari MMKV sebelum first layout pass) |
| **Offline Synchronization**| Redux Persist mentah (risiko over-fetching & payload bloat) | Delta-sync, atomic mutation queue dengan retry backoff otomatis |
| **Concurrency Safe** | Rawan tearing pada Concurrent React | Aman 100% menggunakan kontrak `useSyncExternalStore` |

---

### 5. How: Workflow Detail

#### Alur Eksekusi Mutasi Offline-First dengan Optimistic Update & Auto-Rollback

```
+--------------------------------------------------------------------------------------------------+
| USER ACTION: "Submit Order"                                                                      |
+--------------------------------------------------------------------------------------------------+
                                                 |
                                                 v
                     +-------------------------------------------------------+
                     | 1. Snapshot Current Cache (TanStack Query / Zustand) |
                     +-------------------------------------------------------+
                                                 |
                                                 v
                     +-------------------------------------------------------+
                     | 2. Optimistic Update Local Cache (UI reflects instant)|
                     +-------------------------------------------------------+
                                                 |
                                                 v
                     +-------------------------------------------------------+
                     | 3. Enqueue Mutation to OP-SQLite Transactional Queue  |
                     |    Status: PENDING | Attempts: 0 | IdempotencyKey: UUID|
                     +-------------------------------------------------------+
                                                 |
                                                 v
                                    +--------------------------+
                                    | Network Connectivity Check|
                                    +--------------------------+
                                       /                     \
                         [ONLINE]     /                       \     [OFFLINE]
                                     v                         v
        +-----------------------------------------+   +------------------------------------+
        | 4. Dispatch Network Request (Axios/Fetch)|   | 4b. Suspend Queue Processing       |
        +-----------------------------------------+   |     Listen to NetInfo event change |
                     /                   \            +------------------------------------+
          [SUCCESS] /                     \ [HTTP ERROR / TIMEOUT]
                   v                       v
+-------------------------------+  +-------------------------------------------------------+
| 5a. Acknowledge Server State  |  | 5b. Evaluate Error Category                           |
| - Remove job from SQLite Queue|  +-------------------------------------------------------+
| - Reconcile temporary local ID|         /                                         \
|   with server real entity ID  |   [4xx Client Error]                    [5xx / Timeout / NetFail]
+-------------------------------+          /                                           \
                                          v                                             v
                       +---------------------------------------+    +------------------------------------+
                       | 6a. Rollback Cache to Step 1 Snapshot |    | 6b. Exponential Backoff Policy     |
                       | - Show Failure Toast / Error Banner   |    | - Increment 'Attempts' counter     |
                       | - Mark Job FAILED in SQLite Queue     |    | - Leave in SQLite for next sync    |
                       +---------------------------------------+    +------------------------------------+
```

---

### 6. Analogi & Diagram ASCII

#### Analogi: Arsitektur Pengiriman Surat Fisik vs Pipa Pneumatik JSI
- **AsyncStorage (Sistem Pos Konvensional):** Anda menulis instruksi di kantor (JS Thread). Surat dibungkus amplop tebal (JSON serialize), ditaruh di nampan keluar (Bridge Queue), kurir bersepeda mengantarnya melintasi jembatan kota ke kantor arsip (Native Layer). Kantor arsip membaca, mengeksekusi, dan mengirimkan kurir balasan menyeberangi jembatan lagi. Jika lalu lintas jembatan macet (UI thread sedang merender animasi berat), surat tertahan.
- **MMKV/OP-SQLite via JSI (Pipa Tabung Pneumatik Langsung):** Meja kerja Anda memiliki akses langsung ke lemari arsip melalui tabung vakum pneumatik berkecepatan tinggi. Anda membuka laci lemari arsip secara fisik saat itu juga tanpa perantara. Tidak ada pembungkusan amplop dan tidak ada antrean jembatan.

#### Arsitektur Topology Multi-Tier State

```
+-----------------------------------------------------------------------------------+
|                                 APPLICATION LAYER                                 |
|                                                                                   |
|  +------------------------------------+   +------------------------------------+  |
|  |     Zustand UI Stores (Memory)     |   |   TanStack Query Cache (Memory)    |  |
|  | (Modal states, Auth Session, Theme)|   | (Server Responses, Remote Entities)|  |
|  +------------------┬-----------------+   +------------------┬-----------------+  |
+---------------------┼────────────────────────────────────────┼────────────────----+
                      | Synchronous Serialization               | Dehydration Adapter
                      v                                        v
+-----------------------------------------------------------------------------------+
|                            HIGH-PERFORMANCE DATA LAYER                            |
|                                                                                   |
|  +------------------------------------+   +------------------------------------+  |
|  |    react-native-mmkv (JSI mmap)    |   |     op-sqlite Engine (WAL Mode)    |  |
|  |   - Encrypted KV Store             |   |   - Atomic Offline Mutations Queue |  |
|  |   - Auth Tokens & User Settings    |   |   - Complex Relational Cache       |  |
|  +------------------------------------+   +------------------------------------+  |
+-----------------------------------------------------------------------------------+
```

---

### 7. Implementation: Simple & Practical Enterprise Examples

#### A. Custom High-Performance Storage Adapter (MMKV v3 + Zustand)
Adapter ini mengimplementasikan kontrak `StateStorage` milik Zustand dengan binding sinkronus langsung ke MMKV serta enkripsi hardware-level AES-256.

```typescript
// src/core/storage/mmkvStorage.ts
import { MMKV } from 'react-native-mmkv';
import { StateStorage } from 'zustand/middleware';

export const secureStorage = new MMKV({
  id: 'enterprise-secure-storage',
  encryptionKey: 'c8f1b2d4e5a6f7b8c9d0e1f2a3b4c5d6', // Wajib diambil via Secure KeyChain/Keystore
});

export const mmkvZustandAdapter: StateStorage = {
  setItem: (name: string, value: string): void => {
    secureStorage.set(name, value);
  },
  getItem: (name: string): string | null => {
    const value = secureStorage.getString(name);
    return value ?? null;
  },
  removeItem: (name: string): void => {
    secureStorage.delete(name);
  },
};
```

#### B. Optimistic Atomic State Slice dengan Selector Anti-Re-render
Implementasi store Zustand yang memisahkan actions dari states untuk memvalidasi zero-cost referential updates.

```typescript
// src/features/session/useSessionStore.ts
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { mmkvZustandAdapter } from '../../core/storage/mmkvStorage';

interface UserProfile {
  id: string;
  name: string;
  email: string;
  role: 'ADMIN' | 'OPERATOR' | 'FIELD_AGENT';
}

interface SessionState {
  token: string | null;
  user: UserProfile | null;
  isAuthenticated: boolean;
  actions: {
    setSession: (token: string, user: UserProfile) => void;
    clearSession: () => void;
    updateUserName: (name: string) => void;
  };
}

export const useSessionStore = create<SessionState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      isAuthenticated: false,
      actions: {
        setSession: (token, user) =>
          set({
            token,
            user,
            isAuthenticated: true,
          }),
        clearSession: () =>
          set({
            token: null,
            user: null,
            isAuthenticated: false,
          }),
        updateUserName: (name) =>
          set((state) => ({
            user: state.user ? { ...state.user, name } : null,
          })),
      },
    }),
    {
      name: 'session-store',
      storage: createJSONStorage(() => mmkvZustandAdapter),
      // Hanya persist token dan user data, hindari serialization actions
      partialize: (state) => ({
        token: state.token,
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);

// Atomic hooks untuk mencegah component re-render akibat perubahan field lain
export const useAuthToken = () => useSessionStore((state) => state.token);
export const useCurrentUser = () => useSessionStore((state) => state.user);
export const useIsAuthenticated = () => useSessionStore((state) => state.isAuthenticated);
export const useSessionActions = () => useSessionStore((state) => state.actions);
```

#### C. Database-Backed Mutation Queue Menggunakan `op-sqlite`
Komponen runtime native untuk mengeksekusi antrean mutasi data secara transaksional ketika konektivitas terputus.

```typescript
// src/core/database/mutationQueue.ts
import { open, DB } from '@op-engineering/op-sqlite';

export interface QueuedMutation {
  id: string;
  mutationType: string;
  payload: string;
  createdAt: number;
  retryCount: number;
}

class MutationDatabase {
  private db: DB;

  constructor() {
    this.db = open({ name: 'mutation_queue.sqlite' });
    this.initializeSchema();
  }

  private initializeSchema(): void {
    // Aktifkan mode WAL untuk performa tulis tanpa mengunci operasi baca
    this.db.execute('PRAGMA journal_mode = WAL;');
    this.db.execute(`
      CREATE TABLE IF NOT EXISTS mutations (
        id TEXT PRIMARY KEY NOT NULL,
        mutationType TEXT NOT NULL,
        payload TEXT NOT NULL,
        createdAt INTEGER NOT NULL,
        retryCount INTEGER DEFAULT 0
      );
    `);
    this.db.execute(`
      CREATE INDEX IF NOT EXISTS idx_mutations_created_at 
      ON mutations (createdAt ASC);
    `);
  }

  public push(mutation: Omit<QueuedMutation, 'retryCount'>): void {
    const query = `
      INSERT INTO mutations (id, mutationType, payload, createdAt, retryCount)
      VALUES (?, ?, ?, ?, 0);
    `;
    this.db.execute(query, [
      mutation.id,
      mutation.mutationType,
      mutation.payload,
      mutation.createdAt,
    ]);
  }

  public getPendingMutations(limit = 50): QueuedMutation[] {
    const result = this.db.execute(
      'SELECT id, mutationType, payload, createdAt, retryCount FROM mutations ORDER BY createdAt ASC LIMIT ?;',
      [limit]
    );
    
    if (!result.rows) return [];
    
    const mutations: QueuedMutation[] = [];
    for (let i = 0; i < result.rows.length; i++) {
      mutations.push(result.rows.item(i) as QueuedMutation);
    }
    return mutations;
  }

  public incrementRetry(id: string): void {
    this.db.execute(
      'UPDATE mutations SET retryCount = retryCount + 1 WHERE id = ?;',
      [id]
    );
  }

  public remove(id: string): void {
    this.db.execute('DELETE FROM mutations WHERE id = ?;', [id]);
  }
}

export const mutationQueueDB = new MutationDatabase();
```

---

### 8. Real World Case Study: FinTech Offline Point-of-Sale (POS) System

#### Konteks & Masalah
Sebuah platform POS ritel enterprise melayani 20.000 transaksi per hari di area pergudangan dengan sinyal seluler yang fluktuatif. 
- **Kendala Awal:** Arsitektur lama berbasis `AsyncStorage` + Redux Persist mengalami crash *Out of Memory (OOM)* ketika checkout memproses 5.000 order lokal saat offline selama 8 jam.
- **Root Cause Analysis:** 
  1. `AsyncStorage` mencoba memuat seluruh state JSON ke memori JS sekaligus saat inisialisasi aplikasi. Ukuran file serialized JSON mencapai 120MB, melebihi heap memory limits Hermes pada Android kelas menengah.
  2. Terjadi *data race* saat koneksi pulih: 50 transaksi dikirimkan secara serentak tanpa deduplikasi dan kontrol urutan, menghasilkan duplikasi inventory checkout dan mutasi saldo terbalik.

#### Solusi Arsitektural Terpasang
1. **Tiered Persistence Architecture:** 
   - State sesi & metadata aktif disimpan di **MMKV**.
   - Queue pesanan offline dialihkan ke **OP-SQLite** dengan schema terindeks, transaksi terisolasi secara ACID, dan streaming query terbatas (chunking 50 entri per transaksi).
2. **Deterministic Mutation Sync Engine:**
   - Dibuat custom foreground sync-orchestrator yang membaca record dari SQLite secara sekuensial. Setiap request disuntikkan header idempotency `X-Idempotency-Key: UUIDv5(OrderId + Timestamp)`.
   - Menggunakan TanStack Query `onlineManager` untuk memicu proses sync hanya ketika socket ping TCP sukses (bukan hanya NetInfo network-connected).

#### Hasil Metrik Produksi
- **Cold Boot Time:** Turun dari 4.8 detik menjadi 420 milidetik.
- **Crash Rate (OOM):** Turun dari 3.8% menjadi 0.001%.
- **Zero Inconsistent Balances:** Tidak ada data transaksi yang hilang (*zero data loss*) meskipun terminal dimatikan mendadak saat status transaksi berada di posisi *pending sync*.

---

### 9. Trade-offs & Engineering Decisions

#### A. MMKV vs SQLite vs WatermelonDB
- **`react-native-mmkv`:**
  - *Pros:* Waktu akses read/write paling cepat (~0.05ms); footprint biner kecil; sangat mudah dikonfigurasi.
  - *Cons:* Tidak mendukung query relasional kompleks (tidak ada indexing native selain Key-Value); tidak mendukung SQL operations (`JOIN`, `GROUP BY`).
- **`op-sqlite` (Raw SQLite via JSI):**
  - *Pros:* Query SQL lengkap; transaksi ACID atomik; performa tinggi melalui index B-Tree; cocok untuk offline queue enterprise.
  - *Cons:* Perlu memelihara skrip migrasi skema manual; payload data harus dimodelkan secara relasional.
- **`WatermelonDB` (Lazy-Loading Reactive DB):**
  - *Pros:* Mendukung lazy loading otomatis pada jutaan list item; observables built-in via RxJS.
  - *Cons:* Arsitektur sangat opiniatif; kompleksitas konfigurasi Babel decorators; integrasi TypeScript membutuhkan banyak boilerplate model.

#### B. Synchronous vs Asynchronous State Hydration
- Memilih **Synchronous Hydration (MMKV)** memblokir thread eksekusi JS selama fraksi milidetik, namun menjamin UI tidak menampilkan *flicker* layout atau loading skeleton palsu saat bootstrap.
- Memilih **Asynchronous Hydration (AsyncStorage)** membebaskan main thread secara langsung, namun mewajibkan arsitektur UI menangani state interstitial (`isHydrated: false`) di seluruh root screen tree.

---

### 10. Common Mistakes & Troubleshooting

#### A. Stale Closures pada Zustand Actions
*Penyebab:* Menggunakan referensi state luar secara langsung di dalam deklarasi actions tanpa memanfaatkan parameter setter callback `set((state) => ...)`.
```typescript
// ANTI-PATTERN: State capturing via stale closure
const useCartStore = create((set, get) => {
  let localCounter = 0;
  return {
    items: [],
    addItem: (item) => {
      // items di bawah ini menangkap closure awal jika dipanggil via async callback
      set({ items: [...get().items, item] }); 
    }
  };
});

// BEST PRACTICE: Functional state updater
const useCartStore = create((set) => ({
  items: [],
  addItem: (item) => {
    set((state) => ({ items: [...state.items, item] }));
  }
}));
```

#### B. Zombie Child Problem pada React Context
*Penyebab:* Child component melakukan subscribe ke Context data, sementara parent component menghapus child tersebut berdasarkan perubahan state yang sama. Jika child dieksekusi lebih dulu oleh React scheduler, child akan membaca context yang sudah tidak valid/undefined dan memicu unhandled runtime error.
*Solusi:* Gunakan Zustand atau Redux Toolkit yang memanfaatkan `useSyncExternalStore` dengan top-down execution ordering algorithm terjamin.

#### C. SQLite Database Locking Error (`SQLITE_BUSY`)
*Penyebab:* Menjalankan transaksi tulis (`INSERT`/`UPDATE`) serentak dari background thread worker dan main UI thread tanpa mengaktifkan WAL mode.
*Solusi:* Jalankan query konfigurasi pragmas saat inisialisasi:
```sql
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 5000; -- Menunggu hingga 5 detik sebelum melempar exception BUSY
```

---

### 11. Best Practices & Production Checklist

- [ ] **Enkripsi Storage:** Semua data sensitif (tokens, PII) di MMKV dilindungi kunci enkripsi yang diambil langsung dari iOS Keychain / Android KeyStore. Kunci tidak boleh di-*hardcode* di dalam kode JS/TS.
- [ ] **Partialize Zustand Persist:** Jangan pernah menyimpan non-serializable objects (functions, circular references, Promise, JSX) ke local storage.
- [ ] **Selector Granularity:** Komponen UI tidak boleh mengimpor root state object secara utuh. Selalu gunakan *fine-grained atomic selectors* atau equality checker `shallow`.
- [ ] **Idempotency Assurance:** Semua mutasi offline wajib menyertakan unique tracking UUID yang di-*generate* pada saat entri dibuat di device client.
- [ ] **Lifecycle Memory Teardown:** Daftarkan pembersihan listener event bus dan store subscriptions di dalam return callback `useEffect`.
- [ ] **Storage Quota Budgeting:** Buat limit kapasitas untuk cached network entities (misal: maximum 200 items atau TTL 48 jam) untuk mencegah bloat disk yang dapat memicu penolakan OS saat storage device penuh.

---

### 12. Hands-on Practice

Buatlah implementasi queue mutasi offline yang persisten dengan struktur direktori sebagai berikut:
```text
hands-on/m02/
├── package.json
├── tsconfig.json
└── src/
    ├── storage/
    │   └── secureStorage.ts
    ├── database/
    │   └── dbEngine.ts
    ├── store/
    │   └── useSyncStore.ts
    └── index.ts
```

#### Step 1: Inisialisasi Package Dependencies
Simulasikan instalasi dependency modern pada `hands-on/m02/package.json`:
```json
{
  "name": "enterprise-state-persistence",
  "version": "1.0.0",
  "main": "src/index.ts",
  "dependencies": {
    "zustand": "^4.5.2",
    "react-native-mmkv": "^3.0.0",
    "@op-engineering/op-sqlite": "^8.0.0"
  },
  "devDependencies": {
    "typescript": "^5.4.0"
  }
}
```

#### Step 2: Implementasi State Sync Engine
Tuliskan implementasi logic pada `hands-on/m02/src/store/useSyncStore.ts`:
```typescript
import { create } from 'zustand';

interface SyncTask {
  id: string;
  endpoint: string;
  body: Record<string, unknown>;
  createdAt: number;
}

interface SyncStoreState {
  isOnline: boolean;
  activeTasks: SyncTask[];
  actions: {
    setOnlineStatus: (status: boolean) => void;
    addTask: (task: SyncTask) => void;
    resolveTask: (taskId: string) => void;
  };
}

export const useSyncStore = create<SyncStoreState>((set) => ({
  isOnline: false,
  activeTasks: [],
  actions: {
    setOnlineStatus: (isOnline) => set({ isOnline }),
    addTask: (task) =>
      set((state) => ({
        activeTasks: [...state.activeTasks, task],
      })),
    resolveTask: (taskId) =>
      set((state) => ({
        activeTasks: state.activeTasks.filter((t) => t.id !== taskId),
      })),
  },
}));
```

#### Step 3: Implementasi Mutex Sync Worker Loop
Tuliskan file runner `hands-on/m02/src/index.ts`:
```typescript
import { useSyncStore } from './store/useSyncStore';

class OfflineSyncCoordinator {
  private isProcessing = false;

  public async drainQueue(): Promise<void> {
    const { isOnline, activeTasks, actions } = useSyncStore.getState();

    if (!isOnline || this.isProcessing || activeTasks.length === 0) {
      return;
    }

    this.isProcessing = true;
    console.log(`[SyncEngine] Processing queue of size: ${activeTasks.length}`);

    for (const task of activeTasks) {
      try {
        console.log(`[SyncEngine] Dispatching task ${task.id} to ${task.endpoint}`);
        // Simulasi request network IO
        await new Promise((resolve) => setTimeout(resolve, 300));
        
        // Buang task setelah berhasil dieksekusi
        actions.resolveTask(task.id);
        console.log(`[SyncEngine] Task ${task.id} reconciled successfully.`);
      } catch (err) {
        console.error(`[SyncEngine] Task ${task.id} failed. Halt queue to prevent race conditions.`);
        break;
      }
    }

    this.isProcessing = false;
  }
}

export const syncCoordinator = new OfflineSyncCoordinator();
```

---

### 13. Exercises

#### Level Easy
Tuliskan sebuah custom selector hook untuk Zustand store bernama `useCartCount` yang hanya memicu re-render ketika total kuantitas barang dalam keranjang berubah, tanpa terpengaruh oleh mutasi harga atau label deskripsi barang.

#### Level Medium
Buat sebuah middleware Zustand kustom berlabel `actionLogger` dengan interface TypeScript yang mencatat ke konsol setiap mutasi yang terjadi: nama action, payload, execution time (dalam milidetik), dan snapshot state sebelum vs sesudah mutasi.

#### Level Hard
Rancang database layer menggunakan `op-sqlite` yang mengimplementasikan transaction commit and rollback terisolasi: Jika satu antrean pesanan offline memiliki 5 mutasi baris item dan item ke-4 melempar foreign key constraint failure, seluruh transaksi 5 item tersebut harus di-*rollback* secara atomik dan error dicatat ke table `audit_failures`.

---

### 14. Challenge: Offline Conflict Engine
Rancang arsitektur sinkronisasi dua arah (*bi-directional synchronization*) untuk aplikasi kolaborasi dokumen medis darurat yang digunakan paramedis lapangan:
- **Spesifikasi Kasus:** 
  Dua dokter berbeda mengubah record pasien yang sama pada saat offline secara simultan. Dokter A mengubah riwayat alergi obat (`allergies: ['Penicillin']`), sedangkan Dokter B mencatat tekanan darah terbaru (`vitals.bp: '120/80'`).
- **Target Tantangan:**
  1. Buat skema payload perubahan data yang tidak menimpa field satu sama lain (*No Overwrites of Unrelated Fields*).
  2. Implementasikan resolusi konflik berbasis *Field-Level Vector Clocks* atau *Operation Transforms (OT)* menggunakan SQLite lokal.
  3. Desain kontrak API server untuk mendeteksi split-brain hazard dan menyelesaikan reconciliation secara non-destructive tanpa kehilangan data klinis dokter mana pun.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian A: Pemahaman Konseptual (Basic)
1. Mengapa `react-native-mmkv` memiliki performa penulisan data yang jauh lebih tinggi daripada default `@react-native-async-storage/async-storage`?
2. Bagaimana cara kerja mekanik `useSyncExternalStore` dalam mencegah visual artifact berupa UI tearing?
3. Sebutkan kelemahan arsitektur utama jika seluruh caching respon server REST API disimpan di dalam Zustand store!
4. Apa fungsi dari opsi `partialize` pada middleware persistensi Zustand?
5. Mengapa mode SQLite WAL (Write-Ahead Logging) direkomendasikan untuk aplikasi mobile offline-first?

#### Bagian B: Analisis Arsitektur (Intermediate)
6. Jelaskan konsekuensi performa jika kita melakukan subscribe ke Zustand store dengan format: `const { user, token, settings } = useAppStore();` tanpa selector individual!
7. Kapan operasi IO sinkronus via JSI justru dapat mendegradasi performa dan merusak Frame Per Second (FPS) React Native?
8. Bagaimana strategi yang benar dalam mengelola rotasi key enkripsi lokal pada MMKV jika user mengubah PIN/Passcode aplikasi?
9. Jelaskan perbedaan mendasar antara pola deduplikasi request pada level UI (TanStack Query) versus deduplikasi pada level Queue Database (SQLite)!
10. Mengapa kita tidak disarankan melakukan serialisasi class instance yang memiliki prototype methods ke dalam storage lokal?

#### Bagian C: Skenario Kasus Produksi
11. **Skenario 1:** Sebuah aplikasi kurir logistik mendapati bahwa ketika handphone baterainya habis mendadak saat offline, beberapa file JSON cache `AsyncStorage` korup dan aplikasi crash total saat dibuka kembali (`SyntaxError: Unexpected token in JSON at position...`). Bagaimana Anda mendesain ulang arsitektur persistensi agar toleran terhadap power outage mendadak?
12. **Skenario 2:** Aplikasi streaming musik mengalami memori leak bertahap saat user scrolling ribuan daftar playlist. Profiler menunjukkan alokasi memori ribuan listener functions. Di mana potensi kebocoran alokasi terjadi dalam implementasi store subscription?
13. **Skenario 3:** Tim Anda mengimplementasikan optimistic updates pada fitur transfer saldo. Pengguna mengklik kirim uang, UI langsung memotong saldo optimis. Tiba-tiba server mengembalikan response error HTTP 422 (Insufficient Balance Server-Side). Jelaskan step-by-step skenario penanganan error dan reconciliasi rollback state agar tidak terjadi inkonsistensi saldo visual!

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Jawaban Bagian A
1. **MMKV vs AsyncStorage:** MMKV berkomunikasi langsung dengan Hermes engine via C++ JSI tanpa jembatan asynchronous bridge queue dan menggunakan `mmap` kernel mapping yang mengeliminasi overhead alokasi memori berulang dari serialize/deserialize JSON.
2. **UI Tearing Mitigation:** `useSyncExternalStore` mengunci pembacaan snapshot store eksternal secara sinkronus pada saat proses render React berjalan; jika mutasi terjadi di tengah-tengah render, React akan membatalkan pass render saat itu juga dan merender ulang seluruh tree menggunakan data snapshot terbaru secara atomik.
3. **Server Cache di Zustand:** Membutuhkan manual tracking untuk status stale time, deduplikasi concurrent requests, garbage collection cache memory, background polling, dan window focus re-fetching yang semuanya sudah ditangani secara native dan deklaratif oleh TanStack Query/RTK Query.
4. **Fungsi Partialize:** Berfungsi sebagai whitelist filter untuk menyaring field state mana saja yang diizinkan untuk di-serialize ke persistent storage dan membuang state ephemeral (seperti status fetching flag, actions methods, modal open toggles).
5. **Keuntungan WAL Mode:** Memisahkan berkas append log transaksi dari berkas database utama, memungkinkan transaksi pembacaan data berjalan bersamaan tanpa pernah terblokir oleh transaksi penulisan background worker.

#### Jawaban Bagian B
6. **Destructuring Tanpa Selector:** Setiap kali salah satu property di dalam store berubah (misalnya `settings`), komponen akan dievaluasi ulang untuk re-render meskipun property `user` dan `token` yang sebenarnya digunakan tidak mengalami perubahan, memicu degradasi cascade render.
7. **JSI Sync IO Blocking:** Jika file yang dibaca dari disk berukuran sangat besar (misal: JSON payload puluhan Megabyte), pemanggilan JSI sinkronus akan menahan eksekusi JS thread utama, yang secara langsung menyebabkan UI macet (*frame drop*) dan touch event tidak merespons (ANR).
8. **Rotasi Enkripsi Keychain:** Data lama harus dibaca ke memori sementara secara aman, storage instance baru diinisialisasi dengan Cipher key baru yang disimpan di Secure Enclave/KeyStore, data dituliskan ulang ke instance baru tersebut, lalu block storage lama di-wipe secara permanen.
9. **Deduplikasi UI vs DB Queue:** Deduplikasi UI mencegah inisiasi duplikasi HTTP request pada waktu terbang (*in-flight*) yang bersamaan dari layer komponen; sedangkan deduplikasi DB Queue menjamin mutasi yang tersimpan di disk storage tidak dieksekusi dua kali ke downstream server API melalui verifikasi idempotency key unik.
10. **Prototype Method Serialization:** JSON serializer secara default hanya mempertahankan enumerable own properties. Method prototype, getter, setter, dan inheritance hierarchy akan terhapus (*stripped out*), menghasilkan objek plain JS saat dihidrasi kembali yang akan memicu runtime crash jika method dipanggil.

#### Jawaban Bagian C (Kasus Produksi)
11. **Solusi Skenario 1 (Power Outage Tolerant):**
    Migrasi storage layer dari berkas JSON raw ke SQLite atau MMKV. MMKV dan SQLite menggunakan *page-level write buffer* dengan proteksi atomik. Jika write interrupted, berkas master tidak terkorupsi karena pointer database hanya digeser setelah flushing block selesai seutuhnya (konsep Atomic Commit). Terapkan pula fallback `try-catch` saat parsing initial boot yang otomatis melakukan reset cache rusak tanpa memicu root crash aplikasi.
12. **Solusi Skenario 2 (Memory Leak Subscriptions):**
    Kebocoran memori terjadi karena komponen individual di dalam baris list mendaftarkan store subscription manual (misal: `store.subscribe(...)`) di dalam hook atau lifecycle tanpa memanggil fungsi unsubscribe di return block `useEffect`. Solusinya adalah beralih murni ke hook-based atomic selector Zustand (`useAppStore(state => state.item[id])`) di mana alokasi subscription dikelola dan dibersihkan secara otomatis oleh engine React lifecycle hooks.
13. **Solusi Skenario 3 (Reconciliation Rollback Mutasi):**
    - Simpan snapshot state saldo sebelum optimistic update dieksekusi (`context.previousBalance = queryClient.getQueryData(['balance'])`).
    - Mutasi optimis diterapkan ke visual store.
    - Saat server melempar HTTP 422: Interseptor catch error membatalkan invalidasi query aktif dan segera memaksa update cache lokal kembali ke data `context.previousBalance`.
    - Tampilkan modal interaktif atau error toast yang menginformasikan kepada user: "Transaksi Ditolak: Saldo server tidak mencukupi" untuk memulihkan kepercayaan visual pengguna secara transparan.

---

### 16. Summary
- **Arsitektur I/O Modern:** Transisi dari bridge-based storage ke engine berbasis JSI C++ (`react-native-mmkv`, `op-sqlite`) memangkas latency operasi disk dari ratusan milidetik menjadi microsecond, sekaligus meniadakan serialization CPU overhead.
- **Pemisahan Boundary State:** Aplikasi enterprise wajib membagi state ke dalam domain yang jelas:
  1. *Client Transient State* (UI open/close, tabs) $\rightarrow$ Memory-only Zustand.
  2. *Client Persistent State* (Tokens, preferences) $\rightarrow$ Zustand + MMKV Storage Adapter.
  3. *Server Caching State* (API responses) $\rightarrow$ TanStack Query dengan partial hydration.
  4. *Relational Large Offline Queue* $\rightarrow$ OP-SQLite dengan mode WAL.
- **Reliabilitas Offline-First:** Sistem mutasi offline yang tangguh dibangun di atas tiga pilar utama: *ACID Persistence Layer*, *Deterministic In-order Processing*, dan *Idempotency Guarantee* pada endpoint server downstream.