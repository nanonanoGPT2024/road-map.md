# Bab 03 Module 01: State Management & Local Data Persistence

---

## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** Frontend and Mobile Engineering
*   **Kategori:** 03-Frontend-and-Mobile
*   **Topik:** React Native Deep Dive
*   **Modul:** Bab 03 Module 01 — State Management & Local Data Persistence
*   **Tingkat Kesulitan:** Advanced / Staff Engineer Level
*   **Prasyarat:** Pemahaman mendalam tentang React lifecycle, React Hooks (`useState`, `useReducer`, `useContext`, `useCallback`), TypeScript Generics, Native Modules Bridge, dan arsitektur threading React Native (UI Thread, JS Thread, Shadow Tree).

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1.  **Mendiagnosis dan Mengeliminasi Bottleneck Re-render:** Mengidentifikasi masalah rendering cascade pada React Native menggunakan profiler dan memitigasinya melalui isolasi state atomik atau selector-based subscriptions (Zustand).
2.  **Mengimplementasikan Data Persistence Berkinerja Tinggi:** Memilih, mengkonfigurasi, dan mengoptimalkan integrasi antara MMKV (via JSI) dan SQLite/WatermelonDB dibanding solusi asinkron warisan (`AsyncStorage`).
3.  **Membangun Engine Sinkronisasi Offline-First:** Merancang state layer terdistribusi lokal yang menangani mutasi optimistik, *conflict resolution*, antrean mutasi persisten (*mutation queue*), dan sinkronisasi delta dengan remote backend.
4.  **Menerapkan Strategi Keamanan Data-at-Rest:** Mengenkripsi data lokal yang sensitif menggunakan kunci kriptografi dari hardware keystore (Android Keystore / iOS Keychain) secara mulus pada layer persistence.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Dalam rekayasa aplikasi mobile skala enterprise, state management bukanlah sekadar "wadah variabel global". State adalah representasi diskrit dari model bisnis aplikasi pada satu titik waktu tertentu (*snapshot of truth*), yang harus hidup berdampingan dengan keterbatasan perangkat mobile: memori terbatas, terminasi proses oleh OS secara mendadak, konektivitas intermiten, dan latency thread JavaScript.

### Mental Model 1: "The Thread Barrier and JSI"
Model lama menganggap state storage (`AsyncStorage`) sebagai jembatan JSON asinkron yang melintasi Native Bridge. Model mental modern yang harus Anda tanamkan adalah: **Memory-Mapped Direct Access via JSI (JavaScript Store Interface)**. Operasi I/O persistensi lokal harus dipandang seperti membaca memori lokal C++, bukan memicu round-trip network/bridge serialized. MMKV memetakan file langsung ke address space memori proses melalui fungsi `mmap()`, mengeliminasi serialization overhead.

### Mental Model 2: "State as an Offline Event Stream"
Jangan memandang data lokal sebagai cache pasif dari API backend. Pandanglah data lokal sebagai **Primary Source of Truth**. UI selalu membaca dari Local Persistent Store. Mutasi pengguna diterapkan secara lokal terlebih dahulu (optimistic state), dicatat ke dalam antrean *write-ahead log* lokal, lalu di-drain secara asinkron ke server. Server hanya bertindak sebagai mediator rekonsiliasi state global.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Arsitektur sinkronisasi offline-first dengan optimasi JSI MMKV dan Zustand:

```text
+---------------------------------------------------------------------------------------+
|                                JAVASCRIPT THREAD (REACT)                              |
|                                                                                       |
|   +-------------------+         Dispatches Action          +----------------------+   |
|   |   React Native    | ---------------------------------> |   Zustand Store      |   |
|   |    UI Component   |                                    | (In-Memory State)    |   |
|   +-------------------+                                    +----------------------+   |
|             ^                                                         |               |
|             | Selective Subscription via Selector                     | Middleware    |
|             | (Prevents unnecessary re-renders)                       v Interceptor   |
|             |                                              +----------------------+   |
|             |                                              | Persistence Manager  |   |
|             |                                              +----------------------+   |
|             |                                                         |               |
+-------------|---------------------------------------------------------|---------------+
              |                                                         | Synchronous
              | JSI (Direct C++ In-Memory Pointer Access)               | Calls (No Bridge)
              | Zero Serialization Overhead                             v
+-------------|-------------------------------------------------------------------------+
|             |                C++ CORE / JSI LAYER (REACT NATIVE ENGINE)               |
|             |                                                                         |
|             |       +------------------------------------+                            |
|             +-----> | react-native-mmkv (JSI Host Object)| <--------------------------+
|                     +------------------------------------+                            |
|                                       |                                               |
|                                       | POSIX mmap()                                  |
+---------------------------------------|-----------------------------------------------+
                                        v
+---------------------------------------------------------------------------------------+
|                                  OPERATING SYSTEM KERNEL                              |
|                                                                                       |
|      +--------------------------------------------------------+                       |
|      | Virtual Memory Pages (Page Cache shared with Disk)     |                       |
|      +--------------------------------------------------------+                       |
|                                       | Dirty Pages Flushing                          |
|                                       v                                               |
|      +--------------------------------------------------------+                       |
|      | Physical Flash Storage (Data-at-Rest)                  |                       |
|      | [Encrypted SQLite DB / MMKV binary format]             |                       |
|      +--------------------------------------------------------+                       |
+---------------------------------------------------------------------------------------+
```

### Alur Mutasi Data Sinkronisasi Offline:

```text
[User Interaction] 
        |
        v
[1. UI Action Dispatched] 
        |
        v
[2. Optimistic Update applied to Zustand State] 
        | 
        +---> Trigger UI Re-render (Only Subscribed Nodes)
        |
        +---> [3. Enqueue to Persistent Outbox Queue (via MMKV/SQLite)]
                    |
                    v
          [Network Available?]
             /           \
          (YES)          (NO)
           /               \
          v                 v
[4. Flush Queue via API]   [Idle: Wait for NetInfo Connectivity Recovery Event]
        |
  [Server Error?]
    /         \
 (4xx/5xx)    (200 OK)
   /             \
  v               v
[5. Rollback State & Alert]  [6. Dequeue Outbox & Commit Snapshot]
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Zustand Internal Mechanics
Zustand beroperasi di luar siklus hidup React. Store Zustand pada intinya adalah penutupan (*closure*) JavaScript sederhana yang mengelola `state`, `listeners` (berupa `Set<Listener>`), dan fungsi dispatch (`setState`, `getState`, `subscribe`).

Ketika `setState` dipanggil:
1. State baru dihitung melalui partial state update: `const nextState = typeof partial === 'function' ? partial(state) : partial`.
2. Dilakukan perbandingan referensial `Object.is(nextState, state)`. Jika referensi sama, mutasi dibatalkan (*no-op*).
3. Jika referensi berbeda, `state = Object.assign({}, state, nextState)` dijalankan.
4. Semua callback dalam listener `Set` dipanggil secara iteratif: `listeners.forEach(listener => listener(state, prevState))`.
5. Komponen React yang terhubung via `useStore(selector, equalityFn)` memanfaatkan hook internal `useSyncExternalStoreWithSelector` dari React 18+. Hook ini mengevaluasi apakah hasil dari `selector(nextState)` secara referensial berbeda dari `selector(prevState)` menggunakan equality check (default: `Object.is`).
6. Jika selector menghasilkan nilai yang identik, React melewati proses reconciliation pada komponen tersebut secara penuh.

### 2. MMKV Storage Engine via JSI
Dibandingkan dengan `AsyncStorage` yang menggunakan thread pool native (melalui Java/Objective-C serialization ke SQLite atau flat file), MMKV memanfaatkan **Tencent's Memory Mapping (mmap)** yang diekspos langsung ke JavaScript melalui JavaScript Interface (JSI).

*   **mmap (POSIX):** MMKV memetakan deskriptor file ke dalam memori virtual aplikasi. Membaca dan menulis ke array memori ini secara langsung memanipulasi disk virtual tanpa context switch dari User Space ke Kernel Space melalui syscall manual `read()` / `write()`.
*   **Protobuf Serialization:** MMKV menyimpan data dalam format biner Protocol Buffers mini. Tidak ada proses `JSON.stringify` atau `JSON.parse` yang membebani CPU JS thread.
*   **JSI Host Objects:** Objek MMKV diinstansiasi sebagai `HostObject` C++. Engine JavaScript (Hermes) memiliki referensi pointer langsung ke instance C++ ini. Fungsi seperti `mmkv.getString('key')` dieksekusi secara sinkronis dalam hitungan *sub-millisecond* (skala nanodetik ke mikrodetik), menghindari latency asinkronisasi Promise queue.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### State Colocation vs Global State
Salah satu kegagalan arsitektur terbesar adalah sentralisasi *semua* state ke store global. Prinsip rekayasa state performan:
1.  **Ephemeral UI State:** Harus diisolasi pada level komponen menggunakan `useState` / `useReducer` (contoh: status ekspansi akordeon, animasi toggle).
2.  **Server Cache State:** State yang bersumber dari server dan di-cache secara lokal (contoh: data profil, list produk). Harus ditangani oleh dedicated server-cache tools seperti `@tanstack/react-query`.
3.  **App/Client State:** State murni aplikasi yang mengatur sesi pengguna, preferensi global, keranjang belanja lokal, atau mutasi outbox offline. Inilah ruang lingkup sejati **Zustand**.

### Re-render Cascades & Zombie Child Problem
Pada arsitektur state berbasis Context API bawaan React, setiap perubahan *value* pada Context Provider memicu re-render pada seluruh konsumen context tersebut, mengabaikan apakah subtree komponen tersebut membutuhkan fragmen data yang berubah atau tidak.

Zustand menghindari problem ini dengan sistem subskripsi berbasis selektor *pub-sub*. Namun, sistem pub-sub eksternal rentan terhadap **Zombie Child Problem**: kondisi ketika child component membaca data store yang sudah dihapus oleh parent component sebelum parent component sempat meng-unmount child tersebut dalam siklus render. React 18 memitigasi problem ini secara fundamental via hook `useSyncExternalStore`, yang menjamin sinkronisasi pembacaan state eksternal secara konsisten tanpa tearing pada transisi concurrent.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut implementasi custom MMKV storage adapter untuk Zustand yang mengintegrasikan validasi TypeScript strictly-typed dan enkripsi.

### File: `src/storage/mmkv.ts`
```typescript
import { MMKV } from 'react-native-mmkv';
import { StateStorage } from 'zustand/middleware';

// Inisialisasi instance storage terisolasi dengan enkripsi
export const secureAppStorage = new MMKV({
  id: 'app-secure-storage',
  encryptionKey: 'MY_SECURE_KEY_MANAGED_BY_KEYSTORE', // Pada prod, ambil dari hardware keychain!
});

// Implementasi StateStorage interface Zustand ke MMKV
export const mmkvStorageAdapter: StateStorage = {
  setItem: (name: string, value: string): void => {
    secureAppStorage.set(name, value);
  },
  getItem: (name: string): string | null => {
    const value = secureAppStorage.getString(name);
    return value ?? null;
  },
  removeItem: (name: string): void => {
    secureAppStorage.delete(name);
  },
};
```

### File: `src/store/useAppPreferencesStore.ts`
```typescript
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { mmkvStorageAdapter } from '../storage/mmkv';

export type AppTheme = 'light' | 'dark' | 'system';

interface AppPreferencesState {
  theme: AppTheme;
  isBiometricsEnabled: boolean;
  accentColor: string;
  setTheme: (theme: AppTheme) => void;
  toggleBiometrics: (enabled: boolean) => void;
  resetPreferences: () => void;
}

const DEFAULT_PREFERENCES = {
  theme: 'system' as AppTheme,
  isBiometricsEnabled: false,
  accentColor: '#0066FF',
};

export const useAppPreferencesStore = create<AppPreferencesState>()(
  persist(
    (set) => ({
      ...DEFAULT_PREFERENCES,

      setTheme: (theme: AppTheme) => {
        set({ theme });
      },

      toggleBiometrics: (isBiometricsEnabled: boolean) => {
        set({ isBiometricsEnabled });
      },

      resetPreferences: () => {
        set(DEFAULT_PREFERENCES);
      },
    }),
    {
      name: 'app-preferences-store',
      storage: createJSONStorage(() => mmkvStorageAdapter),
      // Hanya persist field konfigurasi spesifik jika diperlukan
      partialize: (state) => ({
        theme: state.theme,
        isBiometricsEnabled: state.isBiometricsEnabled,
        accentColor: state.accentColor,
      }),
    }
  )
);
```

### File: `src/components/ThemeToggle.tsx`
```typescript
import React, { memo } from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { useAppPreferencesStore, AppTheme } from '../store/useAppPreferencesStore';

export const ThemeToggle: React.FC = memo(() => {
  // ATOMIK SELEKTOR: Komponen HANYA re-render jika `theme` atau `setTheme` berubah!
  // Tidak akan re-render jika `isBiometricsEnabled` berubah.
  const theme = useAppPreferencesStore((state) => state.theme);
  const setTheme = useAppPreferencesStore((state) => state.setTheme);

  const handleToggle = () => {
    const nextTheme: AppTheme = theme === 'dark' ? 'light' : 'dark';
    setTheme(nextTheme);
  };

  return (
    <View style={styles.container}>
      <Text style={styles.label}>Tema Aktif: {theme}</Text>
      <TouchableOpacity style={styles.button} onPress={handleToggle}>
        <Text style={styles.buttonText}>Ubah Tema</Text>
      </TouchableOpacity>
    </View>
  );
});

const styles = StyleSheet.create({
  container: {
    padding: 16,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  label: {
    fontSize: 16,
    fontWeight: '500',
  },
  button: {
    backgroundColor: '#0066FF',
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderRadius: 8,
  },
  buttonText: {
    color: '#FFFFFF',
    fontWeight: '600',
  },
});
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Analisis `src/storage/mmkv.ts`
*   `new MMKV({ id: 'app-secure-storage', ... })`: Membuat memori sandbox MMKV independen. Nama file fisik pada disk OS akan dikelompokkan dengan id ini, mencegah tabrakan data (*namespace collision*) antar modul.
*   `encryptionKey: '...'`: Menginstruksikan modul C++ internal MMKV untuk mengenkripsi block storage menggunakan enkripsi simetris AES-CFB 128-bit.
*   `mmkvStorageAdapter: StateStorage`: Membuat jembatan integrasi bertipe data ketat yang memenuhi kontrak `StateStorage` milik middleware Zustand. Fungsi `set`, `getString`, dan `delete` dieksekusi secara instan dan sinkron pada C++ thread tanpa membungkus return value ke dalam `Promise`.

### Analisis `src/store/useAppPreferencesStore.ts`
*   `create<AppPreferencesState>()(...)`: Menggunakan double parentheses currying pattern khas TypeScript Zustand untuk memastikan inferensi tipe state dan action berjalan sempurna tanpa error casting.
*   `persist(..., { storage: createJSONStorage(() => mmkvStorageAdapter) })`: Membungkus store dengan state synchronizer. Setiap kali `set()` dipanggil, middleware mencegat perubahan tersebut, mengeksekusi serialization, dan memanggil `mmkvStorageAdapter.setItem()` secara otomatis.
*   `partialize: (state) => ({ ... })`: Pola seleksi atribut persisten. Berfungsi memfilter state sementara (*transient/in-memory only*) agar tidak mengotori disk storage.

### Analisis `src/components/ThemeToggle.tsx`
*   `useAppPreferencesStore((state) => state.theme)`: Penggunaan **Selector Pattern**. Komponen tidak mengonsumsi keseluruhan objek state. Zustand menginjeksi selector ini ke React `useSyncExternalStoreWithSelector`. Jika field `accentColor` bermutasi, fungsi komparasi mendeteksi `state.theme` lama === `state.theme` baru, sehingga siklus render diabaikan sepenuhnya (*zero re-render overhead*).

---

## SEKSI 09 — STUDI KASUS NYATA

### Enterprise Scenario: Offline Order Collection Application (Supply Chain)
Pada aplikasi enterprise pergudangan/logistik, kurir sering kali harus memproses transaksi pesanan barang (*checkout*) di area tanpa koneksi internet (basement gedung atau remote area). 

#### Kendala Produksi Nyata:
1.  **Concurrency Conflict:** Aplikasi harus menerima pesanan baru secara offline dan menghasilkan state ID sementara tanpa menunggu server.
2.  **App Termination Recovery:** Jika perangkat mendadak kehabisan baterai atau aplikasi dimatikan oleh OS Memory Killer saat antrean belum terkirim, antrean pesanan tidak boleh hilang (*Zero Data Loss*).
3.  **Idempotency & Race Condition:** Ketika internet kembali tersambung, antrean mutasi harus dikirim berurutan (*FIFO*) tanpa menduplikasi pembuatan invoice di backend.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Arsitektur modul offline-first ini terdiri atas Zustand Transaction Engine, Persistent Queue melalui MMKV, dan Mutator Worker yang otomatis sinkron saat konektivitas kembali normal.

### File: `src/features/orders/types.ts`
```typescript
export type OrderStatus = 'PENDING_SYNC' | 'SYNCED' | 'FAILED';

export interface OrderItem {
  sku: string;
  quantity: number;
  unitPrice: number;
}

export interface Order {
  localId: string;
  remoteId?: string;
  customerName: string;
  items: OrderItem[];
  totalAmount: number;
  status: OrderStatus;
  createdAt: number;
  retryCount: number;
}
```

### File: `src/features/orders/orderStore.ts`
```typescript
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { mmkvStorageAdapter } from '../../storage/mmkv';
import { Order, OrderItem } from './types';

interface OrderState {
  orders: Record<string, Order>;
  outboxQueue: string[]; // Menyimpan localId pesanan yang harus disinkronkan
  createOrder: (payload: { customerName: string; items: OrderItem[] }) => Promise<string>;
  markOrderSynced: (localId: string, remoteId: string) => void;
  markOrderFailed: (localId: string) => void;
  removeOrder: (localId: string) => void;
}

export const useOrderStore = create<OrderState>()(
  persist(
    (set, get) => ({
      orders: {},
      outboxQueue: [],

      createOrder: async ({ customerName, items }) => {
        // Generate UUID lokal secara deterministik/acak
        const localId = `local_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
        const totalAmount = items.reduce((acc, item) => acc + item.quantity * item.unitPrice, 0);

        const newOrder: Order = {
          localId,
          customerName,
          items,
          totalAmount,
          status: 'PENDING_SYNC',
          createdAt: Date.now(),
          retryCount: 0,
        };

        // Mutasi Optimistik: Simpan ke state lokal dan catat ke outbox secara atomik
        set((state) => ({
          orders: {
            ...state.orders,
            [localId]: newOrder,
          },
          outboxQueue: [...state.outboxQueue, localId],
        }));

        return localId;
      },

      markOrderSynced: (localId, remoteId) => {
        set((state) => {
          const currentOrder = state.orders[localId];
          if (!currentOrder) return state;

          return {
            orders: {
              ...state.orders,
              [localId]: {
                ...currentOrder,
                remoteId,
                status: 'SYNCED',
              },
            },
            outboxQueue: state.outboxQueue.filter((id) => id !== localId),
          };
        });
      },

      markOrderFailed: (localId) => {
        set((state) => {
          const currentOrder = state.orders[localId];
          if (!currentOrder) return state;

          return {
            orders: {
              ...state.orders,
              [localId]: {
                ...currentOrder,
                status: 'FAILED',
                retryCount: currentOrder.retryCount + 1,
              },
            },
            // Tetap biarkan di outbox atau terapkan strategi Dead-Letter-Queue jika retryCount > batas
          };
        });
      },

      removeOrder: (localId) => {
        set((state) => {
          const nextOrders = { ...state.orders };
          delete nextOrders[localId];
          return {
            orders: nextOrders,
            outboxQueue: state.outboxQueue.filter((id) => id !== localId),
          };
        });
      },
    }),
    {
      name: 'order-persistent-vault',
      storage: createJSONStorage(() => mmkvStorageAdapter),
    }
  )
);
```

### File: `src/features/orders/SyncEngine.ts`
```typescript
import NetInfo, { NetInfoState } from '@react-native-community/netinfo';
import { useOrderStore } from './orderStore';
import { Order } from './types';

class OfflineSyncEngine {
  private isProcessing = false;
  private unsubscribeNetInfo: (() => void) | null = null;

  public initialize(): void {
    // Dengarkan perubahan konektivitas jaringan
    this.unsubscribeNetInfo = NetInfo.addEventListener((state: NetInfoState) => {
      if (state.isConnected && state.isInternetReachable) {
        this.drainQueue();
      }
    });
  }

  public teardown(): void {
    if (this.unsubscribeNetInfo) {
      this.unsubscribeNetInfo();
      this.unsubscribeNetInfo = null;
    }
  }

  public async drainQueue(): Promise<void> {
    if (this.isProcessing) return;
    this.isProcessing = true;

    try {
      const { outboxQueue, orders, markOrderSynced, markOrderFailed } = useOrderStore.getState();

      for (const localId of outboxQueue) {
        const order = orders[localId];
        if (!order || order.status === 'SYNCED') continue;

        // Abort jika retryCount melebihi limit (Dead Letter Strategy)
        if (order.retryCount >= 5) {
          console.warn(`[SyncEngine] Order ${localId} melebihi batas retry limit.`);
          continue;
        }

        try {
          const remoteId = await this.uploadOrderWithIdempotency(order);
          markOrderSynced(localId, remoteId);
        } catch (error) {
          console.error(`[SyncEngine] Gagal sinkronisasi order ${localId}:`, error);
          markOrderFailed(localId);
          // Berhenti memproses antrean secara sekuensial jika network terputus di tengah jalan
          break;
        }
      }
    } finally {
      this.isProcessing = false;
    }
  }

  private async uploadOrderWithIdempotency(order: Order): Promise<string> {
    // Payload mock pengiriman API dengan header Idempotency Key
    const response = await fetch('https://api.enterprise-logistics.internal/v1/orders', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Idempotency-Key': order.localId, // Menjamin server tidak menduplikasi order jika request re-transmit
      },
      body: JSON.stringify({
        customer: order.customerName,
        items: order.items,
        total: order.totalAmount,
        clientTimestamp: order.createdAt,
      }),
    });

    if (!response.ok) {
      throw new Error(`Server returned status code: ${response.status}`);
    }

    const result = await response.json();
    return result.id as string;
  }
}

export const syncEngine = new OfflineSyncEngine();
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Fitur / Parameter | Zustand + MMKV | Redux Toolkit + Redux Persist | WatermelonDB / SQLite | TanStack Query + MMKV Cache |
| :--- | :--- | :--- | :--- | :--- |
| **Paradigma Arsitektur** | Minimalist Pub-Sub Atomik | Centralized Unidirectional Flux | Relational Observable (SQLite Engine) | Server-Cache Asynchronous State |
| **Overhead Bundle Size** | Sangat Rendah (~1.5 KB + MMKV) | Tinggi (~12 KB + dependencies) | Sangat Besar (Komponen Native SQLite) | Menengah (~13 KB) |
| **Kecepatan I/O (Read/Write)**| **Ekstrem (< 0.1ms via C++ JSI)** | Lambat jika default ke AsyncStorage | Tinggi (C++ Native SQLite bridge) | Sangat Tinggi via custom MMKV client |
| **Relational Query Capability**| Manual (In-Memory JS Indexing) | Manual (Normalizr/EntityAdapter) | **Bawaan (SQL Query & Relations)** | Terbatas (Document/Cache Key-based) |
| **Kurva Belajar Dev** | Sangat Rendah | Menengah - Tinggi | Tinggi (Butuh schema, decorators) | Rendah - Menengah |
| **Thread Block Vulnerability**| Nol (Jika data serialized kecil) | Potensial (JSON serialization besar)| Nol (Offload ke native threads) | Nol |

### Rekomendasi Pemilihan Solusi:
*   Gunakan **Zustand + MMKV** jika aplikasi membutuhkan global client state, performa ultra-cepat, minim boilerplate, dan struktur data yang tidak memiliki relasi kompleks antar ribuan entitas data.
*   Gunakan **WatermelonDB** jika aplikasi adalah sistem database lokal penuh (seperti Notion, WhatsApp) yang mengelola ratusan ribu baris data relasional dan membutuhkan lazy-loading data ke memori secara bertahap.

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. File Corruption pada Hard Crash OS
*   **Kasus:** Jika OS Android/iOS mematikan proses saat buffer memori sedang ditulis, data storage berbasis flat-file berisiko korup.
*   **Mitigasi MMKV:** MMKV menggunakan proteksi ukuran file fixed-increment dan CRC32 checksum. Saat membaca data yang korup, MMKV mendeteksi mismatch CRC dan membuang block data yang tidak utuh secara otomatis tanpa melempar fatal native crash.

### 2. Large Object Memory Spikes
*   **Kasus:** Menyimpan base64 attachment gambar atau respon JSON utuh berukuran >10MB ke dalam Zustand/MMKV.
*   **Dampak:** Terjadi lonjakan alokasi memori JS Heap (Memory Spike) yang memicu *Out of Memory (OOM) Kill* oleh kernel sistem operasi pada perangkat Android low-end.
*   **Mitigasi:** Jangan simpan data blob/biner ke dalam state store. Tulis file blob ke File System OS (`react-native-fs` / `expo-file-system`) dan simpan **Path URI-nya saja** di dalam Zustand store.

### 3. Skema Data Berubah (Schema Migration Pitfall)
*   **Kasus:** Struktur interface store versi 1.0.0 berbeda dengan versi 1.1.0 (misal: field dihapus atau tipe data diubah dari `string` menjadi `string[]`).
*   **Mitigasi:** Manfaatkan properti `version` dan fungsi `migrate` pada middleware `persist`:

```typescript
persist(
  (set) => ({ ... }),
  {
    name: 'order-persistent-vault',
    version: 2, // Naikkan versi
    migrate: (persistedState: any, version: number) => {
      if (version === 0) {
        // Migrasi state versi 0 ke versi 1
        persistedState.items = [];
      }
      if (version === 1) {
        // Migrasi state versi 1 ke versi 2: Tambahkan default outboxQueue
        persistedState.outboxQueue = [];
      }
      return persistedState;
    },
    storage: createJSONStorage(() => mmkvStorageAdapter),
  }
)
```

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan 1: Destructuring Objek Langsung dari Store Hook
```typescript
// SALAH! Komponen akan re-render SETIAP KALI ada state apapun yang berubah di useOrderStore!
const { orders, createOrder } = useOrderStore(); 
```
**Perbaikan:** Selalu gunakan atomic selector individual atau shallow equality:
```typescript
// BENAR!
const orders = useOrderStore((state) => state.orders);
const createOrder = useOrderStore((state) => state.createOrder);

// Atau gunakan `useShallow` dari 'zustand/react/shallow' jika mengambil multiple properties sekaligus:
import { useShallow } from 'zustand/react/shallow';
const { orders, outboxQueue } = useOrderStore(
  useShallow((state) => ({ orders: state.orders, outboxQueue: state.outboxQueue }))
);
```

### Kesalahan 2: Menggunakan `AsyncStorage` untuk Operasi Sinkronis Cepat
`AsyncStorage` mengeksekusi operasi baca secara asinkron عبر JSON serialization bridge, menyebabkan blank flash pada UI jika data dibutuhkan saat cold-start mount.  
**Perbaikan:** Migrasikan seluruh penyimpanan preferensi cold-boot ke MMKV synchronous JSI.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Immutability Enforcement:** Selalu manfaatkan spread operator atau library seperti `immer` (via middleware Zustand `immer()`) saat memperbarui nested object dalam state store untuk menghindari mutasi referensial diam-diam (*silent bugs*).
2.  **Separate UI State from Sync State:** Pisahkan domain antrean sinkronisasi, domain otentikasi, dan domain konfigurasi ke dalam store file yang berbeda (*Store Slice Pattern*). Jangan satukan semua state ke satu monolithic store file.
3.  **Strict Store Reset Hook:** Sediakan hook sentralisasi untuk memusnahkan seluruh isi store dan memori disk saat skenario logout pengguna (*Session Purge*).

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

### 1. Flat Data Normalization
Hindari menyimpan data bersarang (*deeply nested arrays of objects*). Normalisasikan data menyerupai tabel relasional menggunakan ID sebagai index kunci:
```typescript
// BURUK
orders: [{ id: '1', items: [{ id: '10', name: 'A' }] }]

// OPTIMAL (O(1) Access and Update)
orders: { '1': { id: '1', itemIds: ['10'] } }
items: { '10': { id: '10', name: 'A' } }
```

### 2. Network Payload Delta-Compression
Saat melakukan drain sinkronisasi mutasi, jangan kirimkan keseluruhan objek. Kirimkan hanya *patch payload* (perubahan spesifik yang dibuat). Ini menghemat penggunaan data seluler pengguna dan mengurangi waktu transmisi radio modem perangkat.

---

## SEKSI 16 — KEAMANAN & HARDENING

Menyimpan data lokal mentah di perangkat berakar (*rooted Android*) atau *jailbroken iOS* mengekspos data ke inspeksi file system langsung.

### Security Hardening Workflow:
1.  **Hardware Keystore Key Generation:** Jangan pernah melakukan *hardcode* enkripsi string pada file JS bundle! Gunakan library seperti `react-native-keychain` untuk men-generate dan mengamankan kunci simetris AES-256 di Secure Enclave (iOS) atau Android Keystore.
2.  **Pass-key to MMKV Engine:** Masukkan string rahasia yang diekstrak dari Keyring/Keystore saat runtime ke konfigurasi MMKV initialization:

```typescript
import * as Keychain from 'react-native-keychain';
import { MMKV } from 'react-native-mmkv';

export async function initializeSecureStorage(): Promise<MMKV> {
  const service = 'com.myapp.storageservice';
  let credentials = await Keychain.getGenericPassword({ service });

  if (!credentials) {
    // Generate secure random string
    const generatedEntropyKey = Array.from({ length: 32 }, () => 
      Math.floor(Math.random() * 36).toString(36)
    ).join('');

    await Keychain.setGenericPassword('mmkv_vault', generatedEntropyKey, { service });
    credentials = { username: 'mmkv_vault', password: generatedEntropyKey, service };
  }

  return new MMKV({
    id: 'hardened-enterprise-store',
    encryptionKey: credentials.password,
  });
}
```

---

## SEKSI 17 — OBSERVABILITAS, TELEMETRI & DEBUGGING

### Zustand Redux DevTools Integration
Integrasikan middleware DevTools untuk mengamati mutasi state saat fase pengembangan:

```typescript
import { devtools } from 'zustand/middleware';

export const useOrderStore = create<OrderState>()(
  devtools(
    persist(
      (set) => ({ ... }),
      { name: 'order-store' }
    ),
    { name: 'OrderStoreDebugger', enabled: __DEV__ }
  )
);
```

### Sentry / Crashlytics Breadcrumb Logging
Tangkap setiap kali operasi drain queue sinkronisasi offline mengalami kegagalan berulang. Catat status konektivitas, panjang outbox queue, dan error code ke dalam log analytics monitoring tanpa mencatat PII (*Personally Identifiable Information*).

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

*   **Zustand:** Micro state manager berbasis subskripsi atomik eksternal; bebas dari