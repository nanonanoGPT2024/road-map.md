# Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 02: Composition API dan Custom Composables In-Depth**  
**Kategori: 03-Frontend-and-Mobile (Vue.js)**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, software engineer diharapkan mampu:
1. **Menganalisis dan Membedah Internal Reactivity Engine**: Menguraikan alur kerja internal `@vue/reactivity`, mencakup mekanisme `ReactiveEffect`, `track`, `trigger`, serta struktur data `Link` / *doubly linked list* dependensi (optimasi Vue 3.4+) dan manajemen siklus hidup reaktivitas via `EffectScope`.
2. **Merancang Custom Composables Kelas Enterprise**: Mengimplementasikan composables yang tangguh (*resilient*), *memory-leak safe*, mendukung input polimorfik (`MaybeRefOrGetter`), SSR-compliant, dan terisolasi secara konkurensi.
3. **Mengelola Asynchronous Concurrency dan Race Conditions**: Membangun composables asinkron mutakhir yang menangani pembatalan request otomatis (*auto-cancellation*) via `AbortController`, pengabaian mutasi usang (*stale-while-revalidate* / token sequencing), dan resolusi idempotensi.
4. **Menerapkan Pola State Isolation vs Shared State**: Memilih dan mengeksekusi batasan arsitektur state: *Per-Instance Scope*, *Module-level Singleton Scope*, atau *Provide/Inject Contextual Scope* berbasis trade-off konsumsi memori dan isolasi sesi.
5. **Melakukan Audit dan Profiling Memori Frontend**: Mengidentifikasi serta menyelesaikan kebocoran memori akibat *lingering event listeners*, *unmanaged microtasks*, dan *detached async scope* pada composables.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:
- **TypeScript 5.x Advanced**: Generics tingkat lanjut, Conditional Types, Type Narrowing, `infer`, dan Utility Types (`Readonly<T>`, `UnwrapRef<T>`).
- **Vue 3 Fundamental**: Konsep dasar `ref`, `reactive`, `computed`, `watch`, `watchEffect`, dan komponen berbasis Single File Component (SFC) `<script setup>`.
- **Browser Runtime & Event Loop**: Pemahaman siklus Microtask vs Macrotask, `requestAnimationFrame`, Garbage Collection (GC) via Mark-and-Sweep, serta `WeakMap`/`WeakSet`.
- **Dasar HTTP/Network API**: Penggunaan `fetch`, WebSockets, Server-Sent Events (SSE), dan penanganan abort signal via native `AbortController`.

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Vue Reactivity Engine Internals: `Dep`, `Link`, dan `ReactiveEffect`

Arsitektur internal `@vue/reactivity` mengalami revolusi signifikan pada Vue 3.4+. Sebelumnya, relasi antara dependensi (`Dep`, kumpulan efek yang bergantung pada satu properti) dan penikmat data (`ReactiveEffect`) disimpan menggunakan `Set<ReactiveEffect>`. Model lama ini membebani Garbage Collector karena seringnya alokasi/dealokasi objek `Set` pada reaktivitas yang dinamis.

Pada arsitektur modern, relasi dependensi dimodelkan sebagai **Doubly Linked List** via node `Link`:

```
[Target: Object]
       │
   (Proxy Get)
       ▼
[Property Key] ──► [Dep] (Head of Link)
                     │ ▲
               Link  │ │  (nextDep / prevDep)
                     ▼ │
             [ReactiveEffect] (Running Execution Context)
                     ▲ │
               Link  │ │  (nextSub / prevSub)
                     │ ▼
                   [Dep]
```

1. **`track(target, type, key)`**:
   Ketika getter dipanggil di dalam konteks komputasi aktif (`activeSub` atau `activeEffect`), Vue mencari `Dep` milik `target[key]` via `targetMap` (`WeakMap<Target, Map<Key, Dep>>`). Node `Link` dibuat atau di-*reuse* untuk mengaitkan `Dep` dengan `activeSub`.
2. **Optimasi Versi Reaktivitas (`version` tracking)**:
   Setiap mutasi pada `Dep` menaikkan internal counter (`dep.version++`). Komputasi (`ComputedRefImpl`) membandingkan `dep.version` dengan versi terakhir yang direkam untuk menentukan apakah komputasi harus dievaluasi ulang (*dirty checking*) tanpa mengeksekusi ulang fungsi kalkulasi jika nilai tidak berubah.
3. **`trigger(target, type, key, newValue, oldValue)`**:
   Ketika setter dipanggil, Vue mengakses `Dep` terkait dan melintasi rantai linked list untuk memanggil `effect.notify()`. Ini menandai dependensi downstream sebagai kotor (*dirty*) dan menjadwalkan ulang fungsi evaluasi melalui batch scheduler.

### 3.2 Dynamic Scope Management: `EffectScope`

Tiap komponen memiliki `EffectScope` yang dibuat saat inisialisasi instance. Komposabel yang mendaftarkan `watch`, `computed`, atau event listener internal harus melekatkan efek-efek ini ke scope pemanggil.

```
       [Parent EffectScope (Component Instance)]
                       │
             ┌─────────┴─────────┐
             ▼                   ▼
    [Child EffectScope]     [watch / computed]
   (Manual/Nested Scope)         │
             │                   ▼
             ▼            [Target Cleanup]
     [Auto Cleanup]
```

- Ketika instance komponen di-*unmount*, `scope.stop()` dipanggil secara otomatis.
- Pemanggilan `scope.stop()` akan melintasi seluruh `ReactiveEffect` yang terdaftar, memutus referensi linked list (`Link`), mengosongkan listener, dan mengeksekusi callback yang didaftarkan melalui `onScopeDispose()`.
- **Bahaya Async Scope Detachment**: Apabila efek reaktif (`watch`, `computed`) dibuat di dalam microtask asinkron (misal: setelah instruksi `await`), *Vue runtime kehilangan referensi `activeEffectScope`*. Efek tersebut menjadi terisolasi secara global (mengapung) dan **tidak akan terhapus** saat komponen di-unmount, memicu *severe memory leak*.

---

## 4. Why & What

### Mengapa Pendekatan Composables Tradisional Sering Gagal di Skala Enterprise?
1. **Reactivity Loss (Destructuring Antipattern)**: Pengembang pemula sering melakukan destrukturisasi objek return atau parameter props, merusak *getter/setter proxy traps*.
2. **Race Condition pada Operasi Asinkron**: Dalam dashboard transaksi tinggi, pengguna memicu sorting/filtering secara cepat. Permintaan asinkron pertama (A) yang lambat dapat merespons setelah permintaan kedua (B) selesai, menimpa data baru dengan data lama (*stale state override*).
3. **Leakage of Side Effects**: Event listener window (seperti resize atau visibilitychange), WebSocket, dan interval sering tertinggal di background jika pembersihan (*teardown*) terikat secara salah pada lifecycle SFC alih-alih scope composable.

### Apa yang Ditawarkan oleh Arsitektur Lanjutan?
- **Universal Input Polymorphism (`MaybeRefOrGetter<T>`)**: Composable menerima nilai mentah (primitif/objek), `Ref<T>`, atau getter function `() => T`. Konsumsi dieksekusi secara aman menggunakan `toValue()`.
- **Structural Destruction Safety**: Memanfaatkan `toRefs` secara defensif atau menyediakan composables yang mengekspos primitives/actions yang aman untuk didestrukturisasi.
- **Async Concurrency Primitive Integration**: Membungkus setiap request asinkron dengan kontrol pembatalan berbasis `AbortController`, penolakan mutasi usang (*cancellation sequencing*), dan status granular (`isLoading`, `isStale`, `error`).

---

## 5. How (Workflow Detail)

Alur kerja arsitektur pemanggilan Composable Asinkron yang *Toleran Terhadap Pembatalan*:

```
[Inisialisasi Composable]
       │
       ▼
Normalisasi Parameter: toValue(args)
       │
       ▼
Registrasi onScopeDispose() ──► Daftarkan Teardown Global
       │
[Trigger Eksekusi / Watch Trigger]
       │
       ├─► 1. Apakah ada running instance?
       │        └─► YA: AbortController.abort() & diskualifikasi promise sebelumnya
       │        └─► TIDAK: Lanjut
       │
       ├─► 2. Inisiasi instance AbortController baru
       ├─► 3. Generate Request ID (Monotonic Increment)
       ├─► 4. Set state: isLoading = true, error = null
       │
       ▼
[Eksekusi I/O Asinkron (Fetch/WS)]
       │
       ├─► SUKSES:
       │     └─► Validasi: Apakah Request ID == Current Request ID?
       │           ├─► YA: Update Data, set isLoading = false
       │           └─► TIDAK: Buang response (Stale Mutation Prevented)
       │
       └─► GAGAL:
             └─► Cek: Apakah err.name === 'AbortError'?
                   ├─► YA: Abaikan (Silenced intentional cancel)
                   └─► TIDAK: Set state: error = err, isLoading = false
```

---

## 6. Analogy & Diagram ASCII

### Analogi: Sakelar Lampu vs Jalur Pipa Hidrolik
- **Options API / State Naif**: Seperti **sakelar lampu mekanis**. Jika Anda menghidupkan sakelar A, Anda harus secara manual mengingat kabel mana yang terhubung ke lampu A. Jika lampu dipindahkan, Anda harus merombak seluruh dinding (komponen monolitik).
- **Composition API dengan Linked Dependency**: Seperti **sistem distribusi hidrolik cerdas**. `Ref` adalah katup air; `ReactiveEffect` adalah kincir air; `Link` adalah pipa fleksibel bertekanan. Katup tidak perlu tahu siapa pemilik kincir air. Ketika katup dibuka, air otomatis mengalir hanya ke kincir yang terhubung pipa. Jika kincir dibongkar (`onScopeDispose`), pipa dilepas otomatis tanpa tumpahan oli (*leak*).

### ASCII: Siklus Hidup Reaktivitas Normal vs Asynchronous Scope Leak

```
KASUS 1: KONEKSI NORMAL (SAFE)
Komponen Init ──► Create Scope ──► Panggil useDataFetcher() ──► watchEffect()
      │                                                              │
      │ (Terkoneksi ke Scope Tree)                                   │
      ▼                                                              ▼
Komponen Destroyed ──► scope.stop() ────────────────────────► Dispose Effect
                                                              (Memori Bersih)

---------------------------------------------------------------------------------

KASUS 2: LEAKED CONTEXT (DANGEROUS)
Komponen Init ──► Panggil useLeakedComposable()
      │
      ├── await fetchAuthToken()  <-- Microtask boundary memutus activeEffectScope
      │
      └──► watchEffect()  <-- Dibuat TANPA induk EffectScope!
                                     │
Komponen Destroyed ──► scope.stop()  │
      X (Tidak dapat menjangkau effect) │
                                     ▼
                      Effect tetap hidup selamanya di memori!
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Safe Polymorphic Debounced Counter

Implementasi sederhana yang mendemonstrasikan normalisasi input menggunakan `MaybeRefOrGetter` dan penggunaan `toValue`:

```typescript
import { ref, watch, type MaybeRefOrGetter, toValue } from 'vue';

export function useDebouncedCounter(
  source: MaybeRefOrGetter<number>,
  delay: MaybeRefOrGetter<number> = 300
) {
  const debouncedValue = ref(toValue(source));
  let timer: ReturnType<typeof setTimeout> | undefined;

  watch(
    () => toValue(source),
    (newVal) => {
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => {
        debouncedValue.value = newVal;
      }, toValue(delay));
    },
    { immediate: true }
  );

  return { debouncedValue };
}
```

### 7.2 Practical Example: Enterprise-Grade Resilient HTTP Composable

Modul composable produksi yang mengelola pembatalan request otomatis, penanganan race conditions, isolasi lifecycle, dan komputasi reaktif polimorfik:

```typescript
// composables/useResilientFetch.ts
import {
  ref,
  shallowRef,
  isRef,
  watch,
  onScopeDispose,
  toValue,
  type Ref,
  type MaybeRefOrGetter
} from 'vue';

export interface UseResilientFetchOptions<T> {
  immediate?: boolean;
  initialData?: T;
  transform?: (raw: any) => T;
  onError?: (err: Error) => void;
}

export interface UseResilientFetchReturn<T> {
  data: Ref<T | null>;
  error: Ref<Error | null>;
  isLoading: Ref<boolean>;
  isStale: Ref<boolean>;
  execute: () => Promise<void>;
  abort: () => void;
}

export function useResilientFetch<T>(
  urlSource: MaybeRefOrGetter<string>,
  initOptions: RequestInit = {},
  options: UseResilientFetchOptions<T> = {}
): UseResilientFetchReturn<T> {
  const { immediate = true, initialData = null, transform, onError } = options;

  // Optimasi: shallowRef digunakan untuk menghindari overhead proxy berulang pada payload JSON besar
  const data = shallowRef<T | null>(initialData) as Ref<T | null>;
  const error = shallowRef<Error | null>(null);
  const isLoading = ref<boolean>(false);
  const isStale = ref<boolean>(false);

  let currentAbortController: AbortController | null = null;
  let latestRequestId = 0;

  const abort = () => {
    if (currentAbortController) {
      currentAbortController.abort();
      currentAbortController = null;
    }
  };

  const execute = async (): Promise<void> => {
    // 1. Batalkan transaksi yang sedang berjalan (race condition prevention)
    abort();

    // 2. Buat kontroler dan identitas transaksi baru
    const abortController = new AbortController();
    currentAbortController = abortController;
    const thisRequestId = ++latestRequestId;

    isLoading.value = true;
    error.value = null;
    isStale.value = false;

    const url = toValue(urlSource);

    try {
      const response = await fetch(url, {
        ...initOptions,
        signal: abortController.signal
      });

      if (!response.ok) {
        throw new Error(`HTTP Request Failed: ${response.status} ${response.statusText}`);
      }

      const json = await response.json();

      // Guard: Cek apakah ada eksekusi baru yang mendahului selesainya parsing ini
      if (thisRequestId !== latestRequestId) {
        return; // Mutasi usang diredam
      }

      data.value = transform ? transform(json) : json;
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        // Eksekusi dibatalkan dengan sengaja; abaikan mutasi error
        return;
      }

      if (thisRequestId === latestRequestId) {
        const parsedError = err instanceof Error ? err : new Error(String(err));
        error.value = parsedError;
        if (onError) onError(parsedError);
      }
    } finally {
      if (thisRequestId === latestRequestId) {
        isLoading.value = false;
        if (currentAbortController === abortController) {
          currentAbortController = null;
        }
      } else {
        isStale.value = true;
      }
    }
  };

  // Auto execute & reactive URL mutation watcher
  watch(
    () => toValue(urlSource),
    () => {
      if (immediate) {
        execute();
      }
    },
    { immediate }
  );

  // Wajib: Cleanup otomatis saat scope pemilik (component/scope manual) berhenti
  onScopeDispose(() => {
    abort();
  });

  return {
    data,
    error,
    isLoading,
    isStale,
    execute,
    abort
  };
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario Kasus: Sistem Monitoring Telemetri Multi-Tenant Financial Core
- **Domain**: Real-time Trading Engine Telemetry & Order Book Stream.
- **Beban Lalu Lintas**: Hingga 250 transaksi state mutations/detik dari WebSocket; fallback polling tiap 2 detik via HTTP REST.
- **Masalah Utama**:
  1. Pengguna sering beralih akun tenant (mengubah `tenantId`), yang memicu banjir koneksi socket usang (*socket zombie*).
  2. Alokasi reaktivitas mendalam (`reactive()`) pada data array berukuran 5.000 elemen menyebabkan freeze antarmuka (*jank*) hingga 120 FPS *dropped frame rate*.
  3. Memory retention rate meningkat 15 MB per menit akibat listener WebSocket tertinggal di memory heap saat berpindah routing.

### Solusi Arsitektur
Dibuat composable arsitektural terpusat: `useTenantTelemetryStream` yang memadukan WebSocket pooling, `shallowRef`, throttling via microtask scheduling, dan pembersihan instan via `EffectScope`.

```typescript
// composables/useTenantTelemetryStream.ts
import {
  shallowRef,
  ref,
  watch,
  onScopeDispose,
  toValue,
  type MaybeRefOrGetter,
  type Ref
} from 'vue';

export interface TelemetryPacket {
  id: string;
  metric: string;
  value: number;
  timestamp: number;
}

export function useTenantTelemetryStream(
  tenantIdSource: MaybeRefOrGetter<string>,
  wsGatewayUrl: string
) {
  // Solusi Jank 1: shallowRef mencegah konversi deep-reactive proxy yang tidak diperlukan
  const telemetryData = shallowRef<Map<string, TelemetryPacket>>(new Map());
  const isConnected = ref(false);
  const packetLossRate = ref(0);

  let activeSocket: WebSocket | null = null;
  let batchBuffer: TelemetryPacket[] = [];
  let rafHandle: number | null = null;

  // Flush buffer menggunakan requestAnimationFrame untuk menyelaraskan dengan paint cycle layar
  const flushBufferToState = () => {
    if (batchBuffer.length === 0) return;

    // Mutasi shallowRef memerlukan assignment instance baru untuk memicu trigger reactivity
    const updatedMap = new Map(telemetryData.value);
    for (let i = 0; i < batchBuffer.length; i++) {
      const packet = batchBuffer[i];
      updatedMap.set(packet.metric, packet);
    }

    telemetryData.value = updatedMap;
    batchBuffer = [];
    rafHandle = null;
  };

  const terminateSocket = () => {
    if (activeSocket) {
      activeSocket.onopen = null;
      activeSocket.onmessage = null;
      activeSocket.onerror = null;
      activeSocket.onclose = null;
      activeSocket.close(1000, 'Tenant Swapped or Scope Disposed');
      activeSocket = null;
    }
    if (rafHandle !== null) {
      cancelAnimationFrame(rafHandle);
      rafHandle = null;
    }
    batchBuffer = [];
    isConnected.value = false;
  };

  const connectToStream = (tenantId: string) => {
    terminateSocket();

    if (!tenantId) return;

    const uri = `${wsGatewayUrl}?tenant=${encodeURIComponent(tenantId)}`;
    activeSocket = new WebSocket(uri);

    activeSocket.onopen = () => {
      isConnected.value = true;
    };

    activeSocket.onmessage = (event: MessageEvent) => {
      try {
        const payload: TelemetryPacket = JSON.parse(event.data);
        batchBuffer.push(payload);

        // Batasi mutasi DOM/Reactivity agar sinkron dengan 60-120hz frame rate
        if (rafHandle === null) {
          rafHandle = requestAnimationFrame(flushBufferToState);
        }
      } catch {
        packetLossRate.value += 1;
      }
    };

    activeSocket.onclose = () => {
      isConnected.value = false;
    };
  };

  // Reaktif terhadap pergantian Tenant
  watch(
    () => toValue(tenantIdSource),
    (newTenantId) => {
      connectToStream(newTenantId);
    },
    { immediate: true }
  );

  // Solusi Memory Leak: Hard Teardown saat unmount
  onScopeDispose(() => {
    terminateSocket();
    telemetryData.value.clear();
  });

  return {
    telemetryData,
    isConnected,
    packetLossRate
  };
}
```

---

## 9. Trade-offs

| Pendekatan / Pola | Keuntungan | Biaya & Konsekuensi |
| :--- | :--- | :--- |
| **`shallowRef` vs `reactive`** | Mengurangi overhead CPU dan alokasi memori hingga 90% pada struktur data besar/nested JSON. | Tidak ada auto-unwrapping. Perubahan properti internal tidak reaktif; wajib meng-assign ulang `.value` secara utuh. |
| **Polymorphic (`MaybeRefOrGetter`)** | Fleksibilitas tinggi bagi pemanggil (menerima literal, ref, maupun getter). | Kompleksitas tipe bertambah; mewajibkan penggunaan konstan `toValue()` di seluruh internal composable. |
| **Module-level Singleton State** | Menghilangkan duplikasi request antar komponen; hemat memori data. | Bahaya kebocoran data antar pengguna pada SSR (*Cross-Request State Pollution*); status tidak terisolasi per testing unit. |
| **Contextual (`provide/inject`) Scope** | Aman untuk SSR; data terisolasi secara sempurna per hierarki komponen. | Memerlukan ancestor component sebagai provider; tracing dependensi lebih sulit dibanding direct import. |
| **High-Frequency RAF Batching** | Mengeliminasi render-blocking jank; menyatukan puluhan mutasi per frame. | Latensi introduksi maksimal 1 frame (~16ms); state tidak sepenuhnya real-time sinkronis pada saat event loop tick yang sama. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Kehilangan Reaktivitas Akibat Destrukturisasi
- **Gejala**: Komponen tidak me-render ulang saat state di composable berubah.
- **Akar Masalah**: Melakukan destructuring langsung pada objek reaktif biasa tanpa wrapper `toRefs`.
- **Troubleshooting & Fix**:

```typescript
// ANTIPATTERN (Rusak: Reaktivitas Hilang)
export function useUserState() {
  const state = reactive({ name: 'Alice', role: 'Admin' });
  return { ...state }; // Return primitif statis!
}

// SOLUSI PRODUKSI
export function useUserState() {
  const state = reactive({ name: 'Alice', role: 'Admin' });
  return toRefs(state); // Membungkus setiap key ke dalam RefImpl individual
}
```

### 10.2 Asynchronous Scope Detachment
- **Gejala**: Efek `watchEffect` atau `computed` tetap berjalan di background dan mengonsumsi resource meskipun komponen sudah dihancurkan.
- **Akar Masalah**: Memanggil watcher atau subscription setelah instruksi `await`.
- **Troubleshooting & Fix**:

```typescript
// ANTIPATTERN (Scope terputus akibat tick asinkron)
async function setupSync() {
  const token = await fetchAuthToken();
  // Ini TIDAK terikat ke lifecycle komponen karena scope sudah berganti microtask!
  watch(source, () => { /* Logika */ });
}

// SOLUSI PRODUKSI
function setupSync() {
  // Inisialisasi watcher secara sinkron di tingkat root composable
  const token = shallowRef<string | null>(null);

  watch(source, () => {
    if (!token.value) return;
    /* Logika aman */
  });

  fetchAuthToken().then(t => {
    token.value = t;
  });
}
```

### 10.3 Cross-Request State Pollution pada Server-Side Rendering (SSR)
- **Gejala**: Pengguna A di browser dapat melihat data sensitif milik Pengguna B secara acak pada saat initial SSR load.
- **Akar Masalah**: Deklarasi state reaktif di level modul (*global module scope*) dieksekusi di Node.js memory space yang persisten di antara beberapa HTTP request.
- **Troubleshooting & Fix**: Jangan pernah mendeklarasikan `const user = ref()` di luar fungsi composable jika berjalan di server. Gunakan `provide/inject` atau framework state manager yang menggunakan pinia SSR store context.

---

## 11. Best Practices (Production Checklist)

- [ ] **Polymorphic Args**: Gunakan `MaybeRefOrGetter<T>` untuk seluruh parameter input dinamis pada composable publik.
- [ ] **Evaluation Safety**: Gunakan `toValue()` untuk mengekstrak nilai parameter, bukan `isRef() ? val.value : val`.
- [ ] **Payload Optimization**: Gunakan `shallowRef` untuk payload berukuran > 100 item atau data yang bersifat read-heavy tanpa mutasi granular.
- [ ] **Teardown Parity**: Setiap composable yang mendaftarkan event eksternal (Window/DOM/SSE/WS/Interval) **harus** mengimplementasikan `onScopeDispose` untuk membersihkan dependensi.
- [ ] **Race Condition Shielding**: Integrasikan `AbortController` pada seluruh asinkron composable yang menangani mutasi network.
- [ ] **Async Scope Pre-attachment**: Hindari memanggil `watch`, `computed`, atau lifecycle hooks di bawah baris kode `await`.
- [ ] **Strict Typing**: Seluruh composable harus secara eksplisit mendefinisikan return interface (hindari type inference otomatis yang terlalu longgar).

---

## 12. Hands-on Practice

Simpan seluruh file praktikum di direktori: `hands-on/m02/`

### File Structure:
```
hands-on/m02/
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
└── src/
    ├── App.vue
    ├── main.ts
    └── composables/
        └── useAsyncQueue.ts
```

### Langkah 1: Setup Lingkungan
Eksekusi di terminal:
```bash
mkdir -p hands-on/m02/src/composables
cd hands-on/m02
npm init -y
npm install vue@latest
npm install -D typescript vite @vitejs/plugin-vue
```

Tuliskan konfigurasi dasar `vite.config.ts`:
```typescript
import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

export default defineConfig({
  plugins: [vue()]
});
```

Dan `tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ESNext",
    "useDefineForClassFields": true,
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "strict": true,
    "jsx": "preserve",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "esModuleInterop": true,
    "lib": ["ESNext", "DOM"],
    "skipLibCheck": true
  },
  "include": ["src/**/*.ts", "src/**/*.d.ts", "src/**/*.tsx", "src/**/*.vue"]
}
```

### Langkah 2: Implementasi `useAsyncQueue.ts`
Implementasikan custom composable untuk mengeksekusi antrean tugas asinkron dengan batasan konkurensi (Concurrency Limit):

```typescript
// hands-on/m02/src/composables/useAsyncQueue.ts
import { ref, shallowRef, onScopeDispose } from 'vue';

export type AsyncTask<T> = () => Promise<T>;

export interface AsyncQueueItem<T> {
  id: number;
  task: AsyncTask<T>;
  resolve: (value: T | PromiseLike<T>) => void;
  reject: (reason?: any) => void;
}

export function useAsyncQueue(concurrency: number = 2) {
  const activeCount = ref(0);
  const queueLength = ref(0);
  const isPaused = ref(false);

  let nextId = 0;
  const pendingQueue: AsyncQueueItem<any>[] = [];
  let isDisposed = false;

  const processNext = () => {
    if (isDisposed || isPaused.value || activeCount.value >= concurrency || pendingQueue.length === 0) {
      return;
    }

    const item = pendingQueue.shift();
    if (!item) return;

    queueLength.value = pendingQueue.length;
    activeCount.value++;

    item.task()
      .then((res) => {
        if (!isDisposed) item.resolve(res);
      })
      .catch((err) => {
        if (!isDisposed) item.reject(err);
      })
      .finally(() => {
        if (!isDisposed) {
          activeCount.value--;
          processNext();
        }
      });
  };

  const enqueue = <T>(task: AsyncTask<T>): Promise<T> => {
    if (isDisposed) {
      return Promise.reject(new Error('AsyncQueue has been disposed'));
    }

    return new Promise<T>((resolve, reject) => {
      pendingQueue.push({
        id: ++nextId,
        task,
        resolve,
        reject
      });
      queueLength.value = pendingQueue.length;
      processNext();
    });
  };

  const pause = () => {
    isPaused.value = true;
  };

  const resume = () => {
    isPaused.value = false;
    processNext();
  };

  const clear = () => {
    pendingQueue.forEach((item) => item.reject(new Error('Queue cleared')));
    pendingQueue.length = 0;
    queueLength.value = 0;
  };

  onScopeDispose(() => {
    isDisposed = true;
    clear();
  });

  return {
    enqueue,
    pause,
    resume,
    clear,
    activeCount,
    queueLength,
    isPaused
  };
}
```

### Langkah 3: Integrasi pada SFC `App.vue`
```html
<!-- hands-on/m02/src/App.vue -->
<script setup lang="ts">
import { ref } from 'vue';
import { useAsyncQueue } from './composables/useAsyncQueue';

const logs = ref<string[]>([]);
const { enqueue, activeCount, queueLength, pause, resume, isPaused } = useAsyncQueue(2);

const addLog = (msg: string) => {
  logs.value.unshift(`[${new Date().toLocaleTimeString()}] ${msg}`);
};

const scheduleTask = (durationMs: number) => {
  addLog(`Enqueuing task (${durationMs}ms)`);
  enqueue(async () => {
    addLog(`Running task (${durationMs}ms)...`);
    await new Promise((res) => setTimeout(res, durationMs));
    addLog(`Completed task (${durationMs}ms)`);
    return durationMs;
  }).catch((err) => {
    addLog(`Task failed: ${err.message}`);
  });
};
</script>

<template>
  <main style="font-family: sans-serif; padding: 2rem;">
    <h2>Production Composable: Concurrency-Limited Async Queue</h2>
    <div>
      <p>Active Running: <strong>{{ activeCount }}</strong> | Waiting Queue: <strong>{{ queueLength }}</strong></p>
      <p>Status: <strong>{{ isPaused ? 'PAUSED' : 'PROCESSING' }}</strong></p>
    </div>

    <div style="display: flex; gap: 8px; margin-bottom: 1rem;">
      <button @click="scheduleTask(1000)">Enqueue 1000ms</button>
      <button @click="scheduleTask(3000)">Enqueue 3000ms</button>
      <button @click="scheduleTask(5000)">Enqueue 5000ms</button>
      <button @click="pause" :disabled="isPaused">Pause</button>
      <button @click="resume" :disabled="!isPaused">Resume</button>
    </div>

    <div style="background: #1e1e1e; color: #4af626; padding: 1rem; border-radius: 4px; height: 300px; overflow-y: auto;">
      <div v-for="(log, idx) in logs" :key="idx">{{ log }}</div>
    </div>
  </main>
</template>
```

---

## 13. Exercise

### Level Easy
1. Modifikasi composable `useResilientFetch` pada Seksi 7.2 agar menerima konfigurasi `timeoutMs`. Jika request melewati batas waktu, batalkan secara otomatis via `AbortController` dengan memicu error timeout yang dapat dibedakan.
2. Jelaskan mengapa `ref(toValue(x))` berbeda perilakunya dengan `toRef(x)` ketika parameter `x` adalah fungsi getter: `() => props.id`.

### Level Medium
1. Bangun composable `useBroadcastChannel<T>(channelName: string)` yang memungkinkan sinkronisasi data antar tab/browser window secara reaktif. Pastikan channel ditutup secara elegan (`channel.close()`) saat scope dihancurkan via `onScopeDispose`.
2. Implementasikan composable `useElementSize(target: MaybeRefOrGetter<HTMLElement | null>)` yang menggunakan `ResizeObserver`. Atasi masalah jika elemen target baru tersedia setelah mounting (kondisional `v-if`).

### Level Hard
1. Buat composable `useOptimisticMutation<TData, TVariables>` yang meniru perilaku Optimistic UI mutakhir:
   - Menerima state target (Ref).
   - Memodifikasi state target secara instan saat mutasi dieksekusi.
   - Menyimpan *snapshot/rollback state*.
   - Melakukan eksekusi I/O server.
   - Mengembalikan state lama secara deterministik dan mulus jika transaksi jaringan melempar failure/rejection.

---

## 14. Challenge

**Skenario**: Anda adalah Principal Frontend Architect di sebuah bursa pertukaran kripto (*crypto exchange*). Anda diminta merancang sistem composable bernama `useOrderBookEngine`.

**Kebutuhan Sistem**:
1. **Toleransi Frekuensi Tinggi**: Engine menerima delta perubahan buku pesanan (*bids/asks*) hingga 500 update/detik per trading pair via server stream.
2. **Dynamic Pair Switching**: User dapat mengubah trading pair secara instan (misal `BTC-USDT` ke `ETH-USDT`) melalui antarmuka reaktif. Composable harus memutus koneksi lama, mereset tree visual buku pesanan, dan menginisiasi koneksi baru tanpa kebocoran thread pemrosesan atau memory leak.
3. **Adaptive Backpressure & Memory Bounds**: Pertahankan memori agar DOM tidak pernah crash: terapkan algoritma pembatasan (*clamping*) yang mempertahankan maksimal top 50 baris harga terbaik, diagregasi setiap 50 milidetik menggunakan web worker atau scheduling berbasis microtasks.
4. **Resilience & Idempotency**: Jika stream koneksi drop, implementasikan algoritma *exponential backoff reconnection* yang secara reaktif memperbarui status antarmuka (`CONNECTING`, `OPEN`, `STALE_RECONNECTING`, `TERMINATED`).
5. **No Memory Leaks**: Buktikan secara arsitektural bahwa tidak ada closure atau observer yang tersisa saat komponen unmount atau saat terjadi error kritis.

*Tugas*: Rancang kode TypeScript composable lengkap tanpa library pihak ketiga eksternal, gunakan hanya API Vue Core (`@vue/reactivity`, `@vue/runtime-core`) dan Native Browser APIs.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda)
1. Apa fungsi dari primitif `toValue()` yang diperkenalkan di Vue 3.3+?
   - A. Mengubah objek biasa menjadi deep reactive proxy.
   - B. Menormalkan nilai, `Ref`, atau getter function menjadi nilai mentah (*unwrapped value*).
   - C. Mengkloning referensi memori secara deep-copy.
   - D. Menghubungkan ref secara manual ke global scope.
2. Kapan sebaiknya fungsi `onScopeDispose()` digunakan di dalam custom composable?
   - A. Hanya saat kita ingin mereset nilai `ref` ke `null`.
   - B. Untuk mengeksekusi teardown atau pembersihan side-effect saat scope reaktif yang menaunginya berhenti.
   - C. Untuk memicu re-render paksa pada template HTML.
   - D. Untuk menghapus elemen DOM secara manual dari dokumen tree.
3. Mengapa destrukturisasi langsung pada `props` dalam `<script setup>` dianggap sebagai antipattern sebelum era Reactive Props Destructure?
   - A. Karena memicu runtime error syntax TypeScript.
   - B. Karena menghilangkan reaktivitas akibat terputusnya getter proxy Vue.
   - C. Karena membuat ukuran bundle JavaScript menjadi dua kali lipat.
   - D. Karena browser lama tidak mendukung sintaks destructuring.
4. Manakah tipe data yang tepat untuk mengoptimalkan array berukuran 100.000 elemen yang hanya diganti secara menyeluruh saat pembaruan?
   - A. `reactive()`
   - B. `ref()`
   - C. `shallowRef()`
   - D. `computed()`
5. Apa konsekuensi teknis jika memanggil `watchEffect()` di dalam blok `setTimeout` tanpa scope khusus?
   - A. Timer setTimeout dibatalkan otomatis oleh engine Vue.
   - B. Watcher terlepas dari siklus hidup komponen dan berisiko bocor di memori.
   - C. Komponen gagal melakukan kompilasi file SFC.
   - D. Tidak ada konsekuensi; Vue secara ajaib selalu melacak konteks asynchronous.

### Bagian 2: Intermediate (Pilihan Ganda & Analisis)
6. Bagaimana cara kerja internal pelacakan dependensi Vue 3.4+ dibandingkan versi terdahulu?
   - A. Menggunakan traversal array statis untuk menghemat memori.
   - B. Mengganti dependensi `Set<ReactiveEffect>` dengan struktur data Doubly Linked List via node `Link`.
   - C. Menghapus sepenuhnya konsep `Dep` dan mengandalkan `WeakSet` global browser.
   - D. Melacak mutasi menggunakan `Object.observe` polyfill.
7. Di bawah ini, manakah skenario yang **paling tepat** untuk menggunakan `toRef` alih-alih `ref`?
   - A. Ketika membuat variabel reaktif baru yang berdiri sendiri tanpa dependensi.
   - B. Ketika ingin mempertahankan tautan reaktif dua arah (*two-way binding*) ke properti tertentu dari objek reaktif.
   - C. Ketika data yang disimpan bertipe fungsi atau Promise.
   - D. Ketika kita ingin membekukan mutasi objek agar tidak bisa diubah (*immutable*).
8. Apa yang terjadi jika composable mendaftarkan state di module scope (di luar fungsi composable utama) pada aplikasi SSR (Nuxt/Node.js)?
   - A. Aplikasi melempar exception `Hydration Mismatch` instan di client.
   - B. Terjadi kebocoran state antar pengguna (*Cross-Request State Leakage*) karena memory space modul di-cache oleh proses server.
   - C. Server memicu reload worker secara otomatis setiap ada HTTP hit.
   - D. Tidak terjadi masalah apa pun jika Node.js dijalankan dalam multi-threading mode.
9. Fungsi utama dari kelas `EffectScope` adalah:
   - A. Mengelompokkan efek reaktif sehingga dapat dihentikan (*disposed*) secara kolektif dalam satu operasi.
   - B. Mengisolasi css scoped styling di runtime.
   - C. Memisahkan eksekusi thread JavaScript ke background Web Worker.
   - D. Menyediakan context injector alternatif untuk `Provide/Inject`.
10. Composable asinkron menerima getter `() => props.filter`. Opsi watcher manakah yang memastikan eksekusi tidak tertinggal satu frame di belakang render cycle?
    - A. `{ flush: 'post' }`
    - B. `{ flush: 'sync' }`
    - C. `{ flush: 'pre' }`
    - D. `{ deep: true }`

### Bagian 3: Skenario Kasus Produksi
11. **Skenario A**: Tim Anda mendapati penggunaan RAM browser melonjak drastis saat pengguna membuka-tutup halaman analitik yang berisi composable `useWindowResizeListener`. Kode di dalam composable adalah:
    ```typescript
    export function useWindowResizeListener(cb: () => void) {
      window.addEventListener('resize', cb);
    }
    ```
    Analisis akar masalah teknisnya dan tentukan solusi terbaiknya!
12. **Skenario B**: Seorang engineer menulis composable otentikasi:
    ```typescript
    // composables/useAuth.ts
    const user = ref<User | null>(null);
    export function useAuth() {
      const login = async (creds) => { /* ... */ };
      return { user, login };
    }
    ```
    Sistem di-deploy ke server Node.js (SSR). Pengguna A login, lalu pengguna B me-refresh halaman dan mendapati data profil pengguna A muncul di layarnya. Jelaskan mekanisme kegagalan tersebut dan arsitektur perbaikannya!
13. **Skenario C**: Pada dashboard live search, ketika pengguna mengetik kata kunci "vue", permintaan HTTP dikirim untuk 'v', lalu 'vu', lalu 'vue'. Karena latensi jaringan fluktuatif, respons untuk 'v' mendarat di browser **setelah** respons untuk 'vue'. Antarmuka akhirnya menampilkan hasil pencarian untuk 'v'. Tentukan mekanisme arsitektural di tingkat composable untuk mengeliminasi bug konkurensi ini tanpa rely pada UI state!

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Kunci Bagian 1 & 2
1. **B** — `toValue()` menormalkan nilai langsung, ref, atau fungsi getter.
2. **B** — `onScopeDispose` adalah kait teardown universal yang mengeksekusi pembersihan ketika EffectScope mati.
3. **B** — Destrukturisasi langsung mengambil nilai statis saat evaluasi, melepaskan get/set tracking proxy.
4. **C** — `shallowRef` hanya melacak mutasi pada level `.value`, mengabaikan pengamatan rekursif pada elemen internal.
5. **B** — Operasi di dalam asynchronous callback kehilangan referensi `activeEffectScope`, membiarkan watcher hidup tanpa parent.
6. **B** — Vue 3.4 merekonstruksi sub/dep tracking menggunakan Doubly Linked List via node `Link` untuk memangkas alokasi GC.
7. **B** — `toRef` menciptakan referensi reaktif yang tetap mencerminkan properti dari objek sumbernya.
8. **B** — Pada lingkungan SSR, module level variable dipertahankan di heap server; satu instance dibagi oleh seluruh request pengguna.
9. **A** — `EffectScope` mengumpulkan dependensi komputasi dan watcher untuk dibersihkan serentak via `.stop()`.
10. **C** — `flush: 'pre'` (default) berjalan sebelum komponen melakukan render update.

#### Solusi Bagian 3 (Skenario Kasus Produksi)
11. **Solusi Skenario A**:
    - *Akar Masalah*: Event listener didaftarkan pada objek global `window` tanpa pernah dilepaskan via `window.removeEventListener`. Ketika komponen di-unmount, fungsi callback dan referensi context komponen dipertahankan di memory heap oleh browser event system (*Zombie Listener*).
    - *Solusi*: Bungkus dengan `onScopeDispose`:
      ```typescript
      export function useWindowResizeListener(cb: () => void) {
        window.addEventListener('resize', cb);
        onScopeDispose(() => {
          window.removeEventListener('resize', cb);
        });
      }
      ```
12. **Solusi Skenario B**:
    - *Akar Masalah*: State `user` dideklarasikan di level root module (`module-level singleton`). Pada SSR, runtime Node.js tidak mereset context modul antar HTTP requests. Ini menyebabkan *Cross-Request State Pollution*, membahayakan privasi data.
    - *Solusi Arsitektur*: Pindahkan inisialisasi state ke dalam fungsi composable atau gunakan context Injection via `provide/inject` atau Pinia (yang secara default mengisolasi store per request instance).
13. **Solusi Skenario C**:
    - *Solusi Arsitektur*: Terapkan pembatalan request aktif dan validasi Request Sequencing (seperti yang dirancang pada Seksi 7.2):
      1. Gunakan native `AbortController` untuk membatalkan sinyal request 'v' begitu input 'vu' diketik.
      2. Terapkan increment monotonic counter (`requestId`). Abaikan data yang mendarat jika `thisRequestId !== latestRequestId`.

---

## 16. Summary

- **Reactivity Engine Internals**: Vue 3.4+ meminimalkan *GC churn* dengan beralih ke struktur data **Doubly Linked List** (`Link`) antara `Dep` dan `ReactiveEffect`, dioptimalkan dengan pelacakan `version` diskrit.
- **Composable Flexibility**: Composable modern tingkat enterprise wajib menerima `MaybeRefOrGetter<T>` dan mengekstrak nilainya via `toValue()` guna menjamin fleksibilitas integrasi polimorfik.
- **Teardown Lifecycle Consistency**: Pemanfaatan `onScopeDispose()` memastikan composable bersifat mandiri (*self-cleaning*) dan independen dari lifecycle component tertentu, memungkinkan composable dioperasikan di dalam SFC, Worker, maupun Custom Scope tanpa resiko kebocoran memori.
- **Asynchronous Concurrency Control**: Pengelolaan request mutasi di composable wajib diproteksi dari race condition dengan menerapkan pembatalan transaksi usang (*AbortController*) dan pengamanan nomor sequence request.
- **SSR Preparedness**: State tidak boleh dideklarasikan di scope modul global jika kode ditargetkan untuk lingkungan isomorphic/SSR, melainkan harus terikat pada instance lifecycle atau contextual dependency injection.