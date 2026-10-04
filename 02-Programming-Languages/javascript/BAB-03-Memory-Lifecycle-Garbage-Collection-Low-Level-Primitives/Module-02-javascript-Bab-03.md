# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 03: Memory Lifecycle, Garbage Collection & Low-Level Primitives**  
**Kategori: 02-Programming-Languages / JavaScript**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Menganalisis dan Membedah Arsitektur V8 Memory Space**: Memahami alokasi memori internal (*New Space*, *Old Space*, *Large Object Space*, *Code Space*, dan *Map Space*) serta mekanisme kerja engine modern (V8 Orinoco).
2. **Menguasai Siklus Garbage Collection Tingkat Lanjut**: Menguraikan algoritma *Scavenge (Cheney's Copying)*, *Mark-Sweep-Compact*, *Tri-color Marking*, *Write Barriers*, serta teknik mitigasi latensi melalui *Incremental Marking*, *Concurrent Marking*, dan *Parallel Compacting*.
3. **Mengimplementasikan Low-Level Memory Primitives**: Membangun struktur data bebas alokasi (*zero-allocation*) dan arsitektur pengolahan biner performa tinggi menggunakan `ArrayBuffer`, `TypedArray`, `DataView`, `SharedArrayBuffer`, dan `Atomics`.
4. **Mengelola Siklus Hidup Objek Kompleks**: Menerapkan manajemen memori deterministik menggunakan `WeakRef` dan `FinalizationRegistry` tanpa melanggar prinsip prediktabilitas GC.
5. **Mendiagnosis dan Mengeliminasi Memory Leak Skala Enterprise**: Mengidentifikasi *closure memory retention*, *detached buffers*, *hidden class de-optimizations*, dan *off-heap memory fragmentation* menggunakan CLI profil, heap snapshots, dan tracing core runtime V8.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib memahami:
* Konsep dasar *Execution Context*, *Call Stack*, dan *Event Loop* (Microtask & Macrotask phase).
* Konsep dasar Pointer, Alokasi Memori Statis vs Dinamis (Stack vs Heap).
* Ekosistem Node.js runtime (Event Loop, Thread Pool via `libuv`, dan Buffers).
* Dasar penulisan TypeScript tingkat lanjut (Generics, Type Narrowing, ArrayBuffers).

---

## 3. Concept & Internal Architecture (Mendalam)

JavaScript adalah bahasa dengan *managed-memory environment*, yang berarti pengembang tidak secara eksplisit memanggil `malloc()` atau `free()`. Pengelolaan memori sepenuhnya diabstraksikan oleh V8 Engine (Chromium/Node.js/Deno). Namun, abstraksi ini menciptakan ilusi alokasi memori berbiaya nol (*zero-cost allocation*). Pada kenyataannya, runtime V8 beroperasi di bawah batasan arsitektur sistem operasi dan perangkat keras yang ketat.

### 3.1 V8 Memory Layout: Resident Set Size (RSS)

Ketika proses Node.js dijalankan, sistem operasi mengalokasikan blok virtual memory yang disebut **Resident Set Size (RSS)**. RSS dibagi menjadi beberapa segmen utama:

```
+-----------------------------------------------------------------------+
|                         Resident Set Size (RSS)                       |
+------------------------------------+----------------------------------+
|             V8 Heap Memori         |         Non-Heap Memori          |
|  +-------------------------------+ |  +-----------------------------+ |
|  | New Space (Semi-Spaces)       | |  | C++ Native Objects (libuv)  | |
|  | - From-Space | To-Space       | |  +-----------------------------+ |
|  +-------------------------------+ |  | Native Node.js Buffers      | |
|  | Old Pointer Space             | |  | (Pool / Slab Allocator)     | |
|  +-------------------------------+ |  +-----------------------------+ |
|  | Old Data Space (Raw Payloads) | |  | Thread Call Stacks          | |
|  +-------------------------------+ |  +-----------------------------+ |
|  | Large Object Space (LOS)      | |  | WebAssembly Instances       | |
|  +-------------------------------+ |  +-----------------------------+ |
|  | Code Space (JIT Generated)    | |                                  |
|  +-------------------------------+ |                                  |
|  | Map / Cell Space (Shapes)     | |                                  |
|  +-------------------------------+ |                                  |
+------------------------------------+----------------------------------+
```

1. **New Space (Nursery)**: Tempat objek berumur pendek dialokasikan pertama kali. Berukuran relatif kecil (biasanya 1MB hingga 64MB, bergantung flag V8). Terbagi menjadi dua semi-space identik: **From-Space** dan **To-Space**.
2. **Old Pointer Space**: Berisi objek yang bertahan dari beberapa siklus alokasi New Space dan memiliki referensi (pointer) ke objek lain.
3. **Old Data Space**: Berisi raw payload (string byte, raw unboxed numbers, data tanpa referensi ke objek heap lain).
4. **Large Object Space**: Objek yang ukurannya melebihi batas alokasi New Space langsung dialokasikan di sini. Objek di area ini tidak pernah dipindahkan oleh Garbage Collector (menghindari biaya komputasi *copying overhead*).
5. **Code Space**: Menampung *Machine Code* yang telah dikompilasi oleh JIT Compiler (Ignition Interpreter dan TurboFan Compiler).
6. **Map Space (Shape Space)**: Menyimpan `Hidden Classes` (Shape) dari objek untuk optimasi inline cache (IC). Objek yang memiliki shape yang sama berbagi Map yang sama.

### 3.2 Algoritma Garbage Collection: Orinoco Engine

V8 mengimplementasikan **Generational Hypothesis**: *Mayoritas objek mati segera setelah dialokasikan*. Berdasarkan hipotesis ini, GC dibagi menjadi dua proses independen:

#### A. Minor GC (Scavenger / Cheney’s Copying Algorithm)
Minor GC membersihkan New Space dengan latensi rendah (< 1-2 ms).
* **Alokasi**: Objek baru dimasukkan ke *From-Space* melalui *Allocation Pointer*.
* **Siklus Scavenge**:
  1. Pointer menelusuri objek root (Stack, Global Objects).
  2. Objek yang dapat dijangkau (*live objects*) disalin ke *To-Space*. Objek yang tidak terjangkau diabaikan (dianggap mati).
  3. Objek yang telah bertahan dari dua kali siklus Scavenge dipromosikan (*evacuation/tenuring*) ke **Old Space**.
  4. Peran kedua space dibalik: *To-Space* menjadi *From-Space*, dan *From-Space* lama dikosongkan secara instan dengan mereset pointer.

#### B. Major GC (Mark-Sweep-Compact)
Major GC membersihkan Old Space ketika ruang memori mencapai ambang batas (*threshold*) tertentu.
* **Marking Phase (Tri-Color Marking)**:
  * **White**: Objek belum ditemukan/dianalisis oleh GC (kandidat mati).
  * **Grey**: Objek telah ditemukan, tetapi referensi internalnya belum dianalisis.
  * **Black**: Objek telah ditemukan beserta seluruh referensi anaknya (dijamin hidup).
* **Write Barrier**: Karena proses penandaan (*marking*) dilakukan secara **Incremental** dan **Concurrent** bersamaan dengan eksekusi thread JavaScript, mutasi objek yang dilakukan oleh aplikasi dicegat oleh *Write Barrier*. Jika objek *Black* mengacu pada objek *White* yang baru dibuat, Write Barrier mengubah warna objek White tersebut menjadi Grey, mencegah terhapusnya objek aktif secara prematur.
* **Sweeping Phase**: Thread background mengidentifikasi memori yang dialokasikan untuk objek White dan menambahkannya ke *Free List* tanpa menghentikan thread utama (Concurrent Sweeping).
* **Compacting Phase**: Objek *Black* dipindahkan ke area memori yang berdekatan untuk mengurangi fragmentasi memori. Pointer referensi yang mengarah ke objek tersebut di-update (*pointer readjustment*).

---

## 4. Why & What

### Mengapa Abstraksi Memori V8 Memerlukan Intervensi Pengembang?
Pada sistem enterprise berbeban tinggi (misalnya: *High-Frequency Trading*, platform ingest log ribuan event per detik, atau WebSockets gateway dengan jutaan koneksi):
* **Stop-the-World (STW) Pauses**: Major GC yang memicu kompresi memori (*compaction*) pada heap berukuran besar (>4GB) dapat menghentikan eksekusi kode selama puluhan hingga ratusan milidetik. Hal ini menyebabkan lonjakan drastis pada latensi P99.
* **Memory Fragmentation**: Alokasi objek dengan siklus hidup bervariasi secara terus-menerus menyebabkan fragmentasi heap. Meskipun kapasitas total RAM mencukupi, sistem operasi tidak dapat mengalokasikan blok memori kontigu, memicu error `Out-of-Memory (OOM) Killer`.
* **V8 Heap Overhead**: Objek JavaScript murni (`Object`, `Array`) membawa overhead metadata internal yang signifikan (Map pointer, Property array pointer, Element backing store pointer). Satu integer 64-bit di dalam objek dapat mengonsumsi hingga 32-48 byte memori.

### Apa Solusinya?
* Mengurangi tekanan alokasi (*allocation pressure*) pada GC dengan **Object Pooling** dan **Zero-Copy Pipelines**.
* Menggunakan **Low-Level Typed Memory Primitives** (`ArrayBuffer`, `SharedArrayBuffer`, `DataView`) untuk menyimpan data biner padat tanpa metadata overhead dari V8 Object.
* Memanfaatkan **Ephemerons**, `WeakRef`, dan `FinalizationRegistry` untuk resource lifecycle tracking yang aman tanpa menahan deallokasi garbage collection.

---

## 5. How (Workflow Detail)

### 5.1 Alur Kerja Alokasi, Mutasi, dan Evakuasi Memori

Berikut adalah alur hidup data dari inisialisasi hingga dealokasi di V8:

```
[Inisialisasi Objek: const data = {...}]
               │
               ▼
[Apakah Objek > Batas New Space?]
        ├── YA  ──> [Alokasi Langsung di Large Object Space (LOS)]
        └── TIDAK ──> [Alokasi di New Space: From-Space]
                            │
              (New Space Penuh / Triggers GC)
                            │
                            ▼
              [Minor GC: Cheney's Scavenger]
               ├── Objek Tidak Terjangkau? ──> [Diabaikan / Overwritten]
               └── Objek Hidup? 
                     ├── Bertahan < 2 Siklus? ──> [Salin ke To-Space]
                     └── Bertahan >= 2 Siklus? ──> [Promosikan ke Old Space]
                                                         │
                                             (Old Space Threshold Melewati Limit)
                                                         │
                                                         ▼
                                            [Major GC: Orinoco Flow]
                                             1. Concurrent / Incremental Mark
                                             2. Write Barrier Protection
                                             3. Concurrent Sweep to Free-List
                                             4. Parallel Evacuation & Compaction
```

---

## 6. Analogy & Diagram ASCII

### 6.1 Analogi: Meja Kerja Kantor vs Arsip Dokumen
Bayangkan memori V8 sebagai sebuah kantor fisik:
* **Stack**: Otak dari pekerja. Hanya menyimpan data lokal instan dan pointer catatan yang sedang dipikirkan.
* **New Space (Nursery)**: Kertas memo (*Post-it*) di atas meja kerja. Cepat ditulis, cepat dibuang ke tempat sampah tanpa harus merapikan meja.
* **Old Space**: Lemari arsip permanen di ruang bawah tanah. Dokumen yang bertahan di meja kerja selama berhari-hari akan dipindahkan ke sini. Pembersihan lemari arsip ini membutuhkan audit menyeluruh, pembongkaran rak, dan penataan ulang dokumen yang memakan waktu lama.
* **SharedArrayBuffer**: Papan tulis kaca raksasa di tengah ruangan yang dapat dibaca dan ditulisi oleh beberapa departemen (*Worker Threads*) sekaligus, menggunakan spidol khusus (*Atomics*) agar tulisan tidak saling tumpang tindih.

### 6.2 Tri-Color Marking State Transition

```
                 +-----------------------+
                 |        WHITE          |  <-- Kandidat GC (Belum diperiksa)
                 +-----------------------+
                             │
            [GC Root mengidentifikasi referensi]
                             │
                             ▼
                 +-----------------------+
                 |        GREY           |  <-- Objek ditemukan, anak-anaknya
                 +-----------------------+      belum diperiksa
                             │
           [Semua referensi anak selesai dipindai]
                             │
                             ▼
                 +-----------------------+
                 |        BLACK          |  <-- Objek aktif aman (Retained)
                 +-----------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Analisis Alokasi Memori Objek vs Primitive TypedArray

Contoh berikut menunjukkan perbandingan footprint memori antara JavaScript Object standar dan representasi Low-Level Buffer.

```typescript
// simple-memory-footprint.ts
import { performance } from 'node:perf_hooks';

function getMemoryUsageInMB(): number {
  return process.memoryUsage().heapUsed / 1024 / 1024;
}

const ITERATIONS = 1_000_000;

// Skenario A: Objek JavaScript Standar (High Allocation Overhead)
global.gc && global.gc();
const memBeforeObj = getMemoryUsageInMB();
const objectArray: Array<{ id: number; active: boolean; score: number }> = [];

for (let i = 0; i < ITERATIONS; i++) {
  objectArray.push({
    id: i,
    active: i % 2 === 0,
    score: i * 1.5,
  });
}

const memAfterObj = getMemoryUsageInMB();
console.log(`[Object Array] Memory Footprint: ${(memAfterObj - memBeforeObj).toFixed(2)} MB`);

// Bersihkan referensi untuk GC
objectArray.length = 0;
global.gc && global.gc();

// Skenario B: Low-Level TypedArray / Memory Buffers (Contiguous Memory)
// Layout: [id: Uint32 (4 byte)] + [active: Uint8 (1 byte)] + [padding: 3 byte] + [score: Float64 (8 byte)] = 16 bytes per entri
const BYTES_PER_RECORD = 16;
const memBeforeBuffer = getMemoryUsageInMB();

const rawBuffer = new ArrayBuffer(ITERATIONS * BYTES_PER_RECORD);
const dataView = new DataView(rawBuffer);

for (let i = 0; i < ITERATIONS; i++) {
  const byteOffset = i * BYTES_PER_RECORD;
  dataView.setUint32(byteOffset, i, true);              // Offset 0-3: ID
  dataView.setUint8(byteOffset + 4, i % 2 === 0 ? 1 : 0); // Offset 4: Active boolean
  // Offset 5-7: Padding / Reserved
  dataView.setFloat64(byteOffset + 8, i * 1.5, true);   // Offset 8-15: Score
}

const memAfterBuffer = getMemoryUsageInMB();
console.log(`[ArrayBuffer + DataView] Memory Footprint: ${(memAfterBuffer - memBeforeBuffer).toFixed(2)} MB`);
```

### 7.2 Practical Example: Zero-Allocation Object Pool & Binary Serialization Pipeline

Implementasi pipeline deserialisasi biner jaringan enterprise menggunakan *object reuse* (Object Pool) untuk meniadakan overhead GC pada ingestion payload.

```typescript
// binary-packet-pipeline.ts
export interface NetworkPacket {
  packetId: number;
  sensorId: number;
  timestamp: bigint;
  payloadValue: number;
  reset(): void;
}

// Concrete Implementasi Reusable Packet
class ReusableNetworkPacket implements NetworkPacket {
  public packetId: number = 0;
  public sensorId: number = 0;
  public timestamp: bigint = 0n;
  public payloadValue: number = 0;

  public reset(): void {
    this.packetId = 0;
    this.sensorId = 0;
    this.timestamp = 0n;
    this.payloadValue = 0;
  }
}

// Enterprise Object Pool untuk Mencegah Minor GC Spikes
export class PacketObjectPool {
  private pool: ReusableNetworkPacket[];
  private cursor: number = 0;
  private readonly capacity: number;

  constructor(capacity: number) {
    this.capacity = capacity;
    this.pool = new Array(capacity);
    for (let i = 0; i < capacity; i++) {
      this.pool[i] = new ReusableNetworkPacket();
    }
  }

  public acquire(): ReusableNetworkPacket {
    if (this.cursor >= this.capacity) {
      // Fallback fallback: allocation jika pool deplesi (atau lempar exception terukur)
      return new ReusableNetworkPacket();
    }
    const instance = this.pool[this.cursor++];
    return instance;
  }

  public release(instance: ReusableNetworkPacket): void {
    if (this.cursor > 0) {
      instance.reset();
      this.cursor--;
      this.pool[this.cursor] = instance;
    }
  }
}

// Binary Decoder Engine menggunakan DataView
export class HighThroughputBinaryParser {
  private pool: PacketObjectPool;

  constructor(poolCapacity: number = 10_000) {
    this.pool = new PacketObjectPool(poolCapacity);
  }

  /**
   * Layout Paket:
   * [0..3]   uint32: Packet ID (Big Endian)
   * [4..7]   uint32: Sensor ID (Big Endian)
   * [8..15]  uint64: Unix Epoch Nanoseconds (Big Endian)
   * [16..23] float64: Sensor Floating Metric (Little Endian)
   */
  public parsePacket(buffer: ArrayBuffer, byteOffset: number = 0): ReusableNetworkPacket {
    const view = new DataView(buffer, byteOffset, 24);
    const packet = this.pool.acquire();

    packet.packetId = view.getUint32(0, false);
    packet.sensorId = view.getUint32(4, false);
    packet.timestamp = view.getBigUint64(8, false);
    packet.payloadValue = view.getFloat64(16, true);

    return packet;
  }

  public recycle(packet: ReusableNetworkPacket): void {
    this.pool.release(packet);
  }
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Ingest Platform High-Frequency Telemetry Data (Fintech & IoT)
* **Problem Statement**: Sebuah sistem ingestion IoT memproses 200.000 metrik per detik per Node.js process. Sistem sering mengalami *P99 latency spike* hingga 1.2 detik setiap 30 detik. Akibatnya, upstream queue (Apache Kafka) mengalami penumpukan backlog dan memicu alert OOM-Killed pada pod Kubernetes.
* **Root Cause Analysis**:
  1. Penggunaan `JSON.parse(buffer.toString('utf8'))` membuat 200.000 short-lived string dan objek per detik di *New Space*.
  2. Akumulasi alokasi cepat ini memicu Scavenge GC setiap 20 milidetik, dan mempromosikan ribuan objek yang belum sempat dibersihkan ke *Old Space*.
  3. Setiap 30 detik, Old Space penuh, memicu **Major GC Full Compacting**, yang membekukan (Stop-the-World) event loop thread utama selama 800-1200ms.
* **Solusi Rekayasa**:
  1. Ubah encoding ingest dari JSON ke raw Binary Protocol berbasis Fixed-width frame via `SharedArrayBuffer` ring buffer.
  2. Implementasikan *Zero-Allocation Parsing Worker Pool* memanfaatkan `Atomics` dan TypedArrays untuk offload komputasi keluar dari Main Thread tanpa biaya overhead serialisasi IPC `structuredClone()`.
* **Dampak**:
  * GC Pause P99 turun dari 1.200ms menjadi **< 3.5ms**.
  * RSS Memory footprint turun dari 3.8GB stabil di **420MB**.
  * Throughput ingestion melonjak sebesar **450%**.

---

## 9. Trade-offs (Arsitektur & Konfigurasi)

| Pendekatan | Latensi (P99) | Kompleksitas Kode | Memory Overhead | Batasan / Konsekuensi |
| :--- | :--- | :--- | :--- | :--- |
| **Standard V8 Objects** | Tinggi (GC pauses tak terprediksi) | Sangat Rendah | Sangat Tinggi (Metadata V8, Hidden Classes) | Tidak cocok untuk throughput di atas >50k ops/sec. |
| **Object Pooling** | Sangat Rendah (Prediktabilitas tinggi) | Sedang | Rendah (Konstan di heap) | Risiko state contamination jika objek tidak di-reset total saat dikembalikan. |
| **TypedArray & ArrayBuffer** | Hampir Nol Latensi Alokasi | Tinggi (Manual offset & byte calculation) | Minimum (Hanya raw data, 1 byte = 1 byte) | Tidak fleksibel terhadap skema data dinamis; endianness harus ditangani manual. |
| **SharedArrayBuffer + Atomics** | Bersih (Multi-thread, Zero-Copy) | Sangat Tinggi (Resiko Race Condition / Deadlock) | Minimum (Dibagikan antar worker thread) | Memerlukan isolasi keamanan Cross-Origin (COOP/COEP headers di browser) & implementasi thread synchronization kompleks. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Common Mistake: Memory Retention melalui Context Lexical Scope (Closure Leak)

```typescript
// ANTI-PATTERN: Closure memegang referensi objek masif secara tidak disengaja
function setupLeakyListener() {
  const massiveDataPayload = new Uint8Array(100 * 1024 * 1024); // 100MB
  const tinyMetadata = { serviceName: 'TelemetryCollector' };

  // Closure 1 (dijalankan di tempat lain)
  function logService() {
    console.log(tinyMetadata.serviceName);
  }

  // Closure 2 (event listener yang tidak pernah dilepas)
  process.on('SIGUSR2', () => {
    // Karena logService dan closure ini berbagi Context Lexical Environment yang sama di V8,
    // seluruh scope (termasuk massiveDataPayload) dapat tertahan di Old Space!
    logService();
  });
}
```

**Solusi & Perbaikan:**
Nullifikasi variabel besar sebelum mengembalikan closure, atau pisahkan scope deklarasi:

```typescript
// PATTERN BERSIH: Isolasi Lexical Scope
function setupCleanListener() {
  const tinyMetadata = { serviceName: 'TelemetryCollector' };

  process.on('SIGUSR2', () => {
    console.log(tinyMetadata.serviceName);
  });
  
  // massiveDataPayload dideklarasikan dalam block scope terisolasi
  {
    const massiveDataPayload = new Uint8Array(100 * 1024 * 1024);
    // Operasikan massiveDataPayload di sini...
  } // Langsung memenuhi syarat GC Scavenger segera setelah block selesai
}
```

### 10.2 Hidden Class (Map) De-optimization (Polymorphism Bloat)

V8 menggunakan *Hidden Classes* untuk mengoptimasi akses properti. Menambahkan properti secara dinamis dengan urutan berbeda menciptakan Map baru di Map Space, membatalkan inline caching (IC) dan meningkatkan penggunaan memori.

```typescript
// BURUK: Urutan inisialisasi properti tidak seragam (Memicu 2 Hidden Class berbeda)
function createPointA(x: number, y: number) {
  const pt: Record<string, number> = {};
  pt.x = x;
  pt.y = y;
  return pt;
}
function createPointB(x: number, y: number) {
  const pt: Record<string, number> = {};
  pt.y = y; // Urutan dibalik!
  pt.x = x;
  return pt;
}

// BAIK: Selalu deklarasikan properti di constructor dengan urutan seragam
class Point {
  constructor(public x: number, public y: number) {}
}
```

### 10.3 Troubleshooting Playbook di Lingkungan Produksi

1. **Dump Heap Snapshot saat Memory Threshold Tercapai**:
   Jalankan Node.js dengan flag diagnostik:
   ```bash
   node --max-old-space-size=4096 \
        --trace-gc \
        --trace-gc-ignore-scavenger \
        --heap-prof \
        dist/server.js
   ```
2. **Programmatic Heap Snapshot Trigger**:
   ```typescript
   import v8 from 'node:v8';
   import fs from 'node:fs';

   export function captureHeapSnapshot(dumpPath: string): void {
     const snapshotStream = v8.getHeapSnapshot();
     const fileStream = fs.createWriteStream(dumpPath);
     snapshotStream.pipe(fileStream);
   }
   ```
3. **Analisis Chrome DevTools**:
   Buka `chrome://inspect` -> *Memory* -> *Load Snapshot*.
   * Periksa kolom **Retainers**: Identifikasi jalur pointer terpanjang (*Retaining Path*) menuju root.
   * Urutkan berdasarkan **Distance**: Objek dengan Distance besar mengindikasikan struktur nested context / closure chaining.
   * Urutkan berdasarkan **Shallow Size** vs **Retained Size**: Retained size yang tinggi pada objek kecil menunjukkan bahwa ia adalah simpul penahan memory leak masif.

---

## 11. Best Practices & Production Checklist

- [ ] **Hindari Mutasi Objek Dinamis**: Jangan gunakan `delete object.property` karena mengubah Shape V8 menjadi Dictionary Mode (Hash Table) yang lambat dan boros memori. Gunakan `object.property = undefined` atau `Map`.
- [ ] **Alokasikan Buffer Konstan**: Gunakan `Buffer.allocUnsafe(size)` hanya jika Anda langsung menimpa seluruh byte-nya untuk menghindari *data-leak security bug*. Hindari pembuatan buffer kecil berulang kali di luar pool bawaan Node.js (8KB pool size).
- [ ] **Set Flag V8 Sesuai Batas Container**: Jika kontainer memiliki RAM 4GB, tetapkan `--max-old-space-size=3072` (75% dari batas RAM kontainer). Jangan pernah menyetelnya ke 100% karena RSS non-heap, thread stacks, dan off-heap buffer membutuhkan ruang sistem operasi.
- [ ] **Hindari JSON.parse Skala Besar pada Event Loop**: Pecah payload besar menggunakan stream parsing biner atau TypedArray views untuk mencegah memory spikes di Old Space.
- [ ] **Gunakan WeakRef dengan Hati-hati**: Jangan gunakan `WeakRef` untuk arsitektur logic inti. Deallokasi `WeakRef` bersifat non-deterministik dan bergantung sepenuhnya pada internal engine GC schedule.

---

## 12. Hands-on Practice

Buat dan simpan file-file praktikum berikut di direktori `hands-on/m02/`.

### Struktur Direktori:
```
hands-on/m02/
├── package.json
├── tsconfig.json
├── worker.ts
└── ring-buffer.ts
```

### 1. Inisialisasi Project (`package.json`)
```json
{
  "name": "hands-on-m02-memory-engine",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "start": "tsx ring-buffer.ts"
  },
  "devDependencies": {
    "tsx": "^4.7.0",
    "typescript": "^5.3.3",
    "@types/node": "^20.11.0"
  }
}
```

### 2. Implementasi Worker Task: `worker.ts`
Worker yang menulis data ke `SharedArrayBuffer` menggunakan `Atomics` untuk eliminasi alokasi data transfer:

```typescript
// hands-on/m02/worker.ts
import { parentPort, workerData } from 'node:worker_threads';

interface WorkerConfig {
  sharedBuffer: SharedArrayBuffer;
  totalWrites: number;
}

const { sharedBuffer, totalWrites } = workerData as WorkerConfig;

// Buffer Layout:
// Byte 0-3: Mutex / State Guard (Int32)
// Byte 4-7: Write Index Counter (Int32)
// Byte 8..N: Data payload (Int32 integers)
const controlArray = new Int32Array(sharedBuffer, 0, 2);
const dataPayload = new Int32Array(sharedBuffer, 8);

function produceData() {
  for (let i = 0; i < totalWrites; i++) {
    // Tunggu akses aman atau langsung perbarui data menggunakan Atomics
    const nextSlot = Atomics.add(controlArray, 1, 1); // Atomic increment index counter
    
    if (nextSlot < dataPayload.length) {
      dataPayload[nextSlot] = i * 42; // Tulis nilai secara langsung ke shared physical memory
    }
  }

  parentPort?.postMessage({ status: 'PRODUCER_DONE', itemsProduced: totalWrites });
}

produceData();
```

### 3. Implementasi Ring Buffer Orchestrator: `ring-buffer.ts`
Thread utama yang mengalokasikan memori, menjalankan worker, dan memvalidasi integritas data:

```typescript
// hands-on/m02/ring-buffer.ts
import { Worker } from 'node:worker_threads';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const CAPACITY = 5_000_000; // 5 Juta Integer 32-bit (20MB data)
const HEADER_SIZE = 8; // 8 Byte untuk atomic counters
const TOTAL_BUFFER_SIZE = HEADER_SIZE + CAPACITY * Int32Array.BYTES_PER_ELEMENT;

async function executeZeroCopyPipeline() {
  console.log(`[Main] Mengalokasikan SharedArrayBuffer sebesar: ${(TOTAL_BUFFER_SIZE / 1024 / 1024).toFixed(2)} MB`);
  
  const sharedBuffer = new SharedArrayBuffer(TOTAL_BUFFER_SIZE);
  const controlArray = new Int32Array(sharedBuffer, 0, 2);
  const dataPayload = new Int32Array(sharedBuffer, 8);

  // Inisialisasi Counter di Shared Memory
  controlArray[0] = 0; // State: 0 (Active)
  controlArray[1] = 0; // Write Cursor: 0

  const startTime = performance.now();

  const worker = new Worker(path.resolve(__dirname, 'worker.ts'), {
    workerData: {
      sharedBuffer,
      totalWrites: CAPACITY,
    },
  });

  await new Promise<void>((resolve, reject) => {
    worker.on('message', (msg) => {
      console.log(`[Worker Signal Received]:`, msg);
      resolve();
    });
    worker.on('error', reject);
  });

  const duration = performance.now() - startTime;
  console.log(`[Main] Selesai membaca ${controlArray[1]} data item.`);
  console.log(`[Main] Durasi Eksekusi: ${duration.toFixed(2)} ms`);
  console.log(`[Main] Validasi Index 0: ${dataPayload[0]} (Expected: 0)`);
  console.log(`[Main] Validasi Index 100: ${dataPayload[100]} (Expected: 4200)`);
  console.log(`[Main] Validasi Akhir: ${dataPayload[CAPACITY - 1]} (Expected: ${(CAPACITY - 1) * 42})`);
}

executeZeroCopyPipeline().catch(console.error);
```

### Eksekusi Program:
```bash
npm install
npm start
```

---

## 13. Exercise

### Level Easy
**Soal**: Buat skrip yang mendeteksi kebocoran memori pada objek cache sederhana menggunakan `WeakRef` dan `FinalizationRegistry`. Pastikan program mencatat log tepat saat objek target dibersihkan oleh Garbage Collector.
* *Constraint*: Objek tidak boleh dicegah untuk di-deallokasi oleh registry callback itu sendiri.

### Level Medium
**Soal**: Tulis kelas serialisasi biner kustom `BinaryOrderBook` yang membaca dan menulis order transaksi (*Order ID, Price, Quantity, Side/Buy/Sell*) langsung ke dalam `ArrayBuffer` berukuran tetap tanpa menggunakan objek JavaScript per transaksi. Sediakan method `readOrder(index: number)` yang mengembalikan nilai menggunakan buffer scanning murni.
* *Constraint*: Hindari penggunaan library pihak ketiga.

### Level Hard
**Soal**: Implementasikan *Zero-Allocation Circular Ring Buffer Queue* yang aman untuk skenario Single-Producer Multi-Consumer (SPMC) berbasis `SharedArrayBuffer` dan `Atomics.wait()` / `Atomics.notify()`. Buktikan melalui pengujian benchmark bahwa alokasi memori heap (diperiksa via `process.memoryUsage().heapUsed`) bersifat flat (konstan) selama eksekusi pemrosesan 10.000.000 pesan.

---

## 14. Challenge (Kompleksitas Enterprise)

### Arsitektur Zero-Allocation High-Speed In-Memory Key-Value Store
Rancanglah modul database in-memory berbasis Node.js yang mampu menangani setidaknya **1.000.000 record string kueri** dengan latensi operasi per kueri `< 0.05 ms`, yang memenuhi batasan arsitektur berikut:

1. **V8 Heap Constraint**: Ukuran `heapUsed` V8 tidak boleh bertambah lebih dari **15MB** meskipun database menampung 500MB raw data string. Seluruh data string harus disimpan langsung di *Off-Heap Memory* atau menggunakan *TypedArray Native Buffers* yang dikelola sendiri (*Custom Memory Page Allocator*).
2. **Crash & Collision Recovery**: Implementasikan *Linear Probing* atau *Robin Hood Hashing* langsung di atas `ArrayBuffer` mentah tanpa array atau objek penolong dinamis.
3. **Eviction Policy**: Jika kapasitas memory pages penuh, terapkan algoritma estimasi deallokasi memori manual (misal: Slotted-Page Architecture) untuk mendaur ulang blok memori tanpa memicu intervensi GC V8.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda & Analisis Singkat)

#### Q1. Manakah ruang memori di V8 yang bertanggung jawab menyimpan objek berumur sangat pendek?
A. Old Pointer Space  
B. Large Object Space  
C. New Space (Nursery)  
D. Map Space  
*Jawaban*: **C**. New Space dialokasikan khusus untuk objek baru dengan asumsi bahwa mayoritas objek tersebut akan mati segera setelah pembuatan.

#### Q2. Algoritma salin memori yang digunakan oleh Minor GC di V8 adalah?
A. Cheney's Copying Algorithm  
B. Mark-Compact Algorithm  
C. LALR Parsing Algorithm  
D. Conservative Reference Counting  
*Jawaban*: **A**. Minor GC (Scavenger) menggunakan modifikasi algoritma Cheney untuk menyalin objek hidup dari *From-Space* ke *To-Space*.

#### Q3. Apa efek samping dari penggunaan kata kunci `delete` pada properti objek JavaScript di V8?
A. Mengurangi penggunaan memori secara langsung dan instan.  
B. Merusak Hidden Class (Map) objek tersebut dan mengubahnya menjadi Slow Dictionary Mode.  
C. Memaksa runtime memanggil Major GC secara sinkron.  
D. Memindahkan objek ke Large Object Space.  
*Jawaban*: **B**. Menghapus properti secara dinamis membatalkan skema *Hidden Class*, mengubah objek menjadi mode kamus (dictionary) berbasis hash table yang memiliki overhead memori lebih besar dan akses properti yang lambat.

#### Q4. Manakah representasi array berikut yang paling hemat memori untuk sekumpulan data integer 32-bit?
A. `Array<number>`  
B. `Int32Array`  
C. `Set<number>`  
D. `Array<string>`  
*Jawaban*: **B**. `Int32Array` mengalokasikan blok memori kontigu dengan ukuran eksak 4 byte per entri tanpa metadata overhead V8.

#### Q5. Apa yang dijamin oleh `FinalizationRegistry` dalam JavaScript engine?
A. Waktu dan urutan pemanggilan cleanup callback bersifat deterministik.  
B. Callback dijamin langsung dipanggil tepat pada mikrodetik objek di-garbage collect.  
C. Memberikan notifikasi pembersihan setelah objek dibersihkan oleh GC, tanpa kepastian waktu eksekusi.  
D. Mencegah objek dibersihkan oleh Garbage Collector jika terjadi kegagalan transaksi.  
*Jawaban*: **C**. Engine tidak pernah menjamin waktu pasti pengeksekusian callback `FinalizationRegistry`; eksekusinya bersifat non-deterministik bergantung pada siklus GC.

---

### Bagian 2: Intermediate

#### Q6. Mengapa Write Barrier diperlukan dalam siklus Major GC modern (Orinoco)?
*Jawaban*: Karena Major GC menggunakan teknik *Incremental* dan *Concurrent Marking*. Ketika thread latar belakang sedang menandai objek, thread utama tetap mengeksekusi kode JavaScript dan dapat mengubah referensi (misalnya menghubungkan objek *Black* ke objek *White* yang baru). Write barrier mendeteksi mutasi ini dan menandai objek White tersebut menjadi Grey agar tidak terhapus secara keliru pada Sweeping phase.

#### Q7. Jelaskan perbedaan mendasar antara `ArrayBuffer` dan `SharedArrayBuffer`!
*Jawaban*: `ArrayBuffer` merepresentasikan blok memori biner dengan kepemilikan eksklusif; jika dikirimkan ke Worker Thread via `postMessage`, buffer tersebut ditransfer (*detached*) atau dikloning (*structuredClone*). Sebaliknya, `SharedArrayBuffer` memetakan blok memori fisik yang sama ke beberapa thread worker secara simultan tanpa duplikasi data, dan sinkronisasinya wajib dikelola menggunakan primitif `Atomics`.

#### Q8. Apa yang menyebabkan sebuah objek JavaScript langsung dialokasikan di Large Object Space (LOS) daripada di New Space?
*Jawaban*: Jika ukuran alokasi payload objek melebihi kapasitas ambang batas alokasi New Space (biasanya objek berukuran > 256KB-1MB bergantung versi/flag V8). Objek ditempatkan di LOS agar tidak membebani algoritma Scavenger dengan operasi penyalinan (*copying memory overhead*) yang mahal.

#### Q9. Apa bahaya retain pointer pada sub-string slicing (`String.prototype.slice`) pada engine V8 lama/tertentu?
*Jawaban*: Pada implementasi lama V8, memotong string kecil dari string raksasa (misal: mengambil 10 karakter dari string 50MB) menghasilkan *Sliced String* yang mempertahankan referensi internal ke induk string utuh tersebut di Old Space. Akibatnya, memori 50MB induk tidak dapat dibersihkan selama string 10 karakter tersebut masih aktif.

#### Q10. Mengapa `WeakMap` tidak memiliki method `.keys()`, `.values()`, atau `.size`?
*Jawaban*: Karena referensi key dalam `WeakMap` bersifat *weak* (lemah) dan dapat dihapus oleh GC sewaktu-waktu secara non-deterministik. Jika properti enumerasi disediakan, isi koleksi akan bergantung pada status siklus Garbage Collection saat itu, yang merusak determinisme logika program.

---

### Bagian 3: Skenario Kasus Produksi

#### Skenario 1: The "Mysterious" OOM Crash During High Load
Sebuah gateway WebSocket perbankan mencatat lonjakan memori Old Space hingga crash OOM setiap kali terjadi lonjakan transaksi pasar (*flash event*), padahal setiap pesan WebSocket langsung diproses dan tidak disimpan di variabel global. Dari profiling, ditemukan ratusan ribu fungsi callback `socket.on('data', ...)` terdaftar berulang kali di dalam loop request handling.  
*Pertanyaan*: Jelaskan mekanisme kebocoran memori ini di tingkat V8 dan berikan langkah penanganannya!  
*Solusi*: Setiap registrasi event listener `socket.on` menciptakan closure baru yang menahan referensi ke lexical scope tempat fungsi itu dideklarasikan. Jika event listener tidak pernah dilepas via `socket.removeListener` (atau tidak menggunakan flag `{ once: true }`), instance EventEmitter mempertahankan array referensi fungsi callback tersebut di Old Space selamanya. Solusinya: Jangan mendeklarasikan event listener di dalam request-response loop; gunakan pola message dispatcher terpusat, atau bersihkan listener pada blok `finally`.

#### Skenario 2: De-optimasi Inline Cache karena JSON Payload Polymorphism
Microservice pemrosesan klaim asuransi mengalami penurunan performa drastis hingga 80% dan latensi P99 membengkak setelah tim upstream mengubah format payload dengan menambahkan field opsional secara acak: `{ id, status }` kadang menjadi `{ status, id }` atau `{ id, metadata, status }`.  
*Pertanyaan*: Mengapa inkonsistensi struktur JSON menyebabkan lonjakan CPU dan inefisiensi memori di runtime V8?  
*Solusi*: V8 mengidentifikasi tipe data dinamis melalui **Hidden Classes (Maps)**. Setiap variasi urutan field atau keberadaan properti opsional menghasilkan *Map transition* baru. Ketika sebuah fungsi menerima objek dengan lebih dari 4 variasi Map yang berbeda pada call-site yang sama, Inline Cache (IC) beralih dari mode *Monomorphic* -> *Polymorphic* -> *Megamorphic*. Pada mode Megamorphic, V8 mematikan TurboFan JIT assembly optimization dan beralih ke pencarian kamus dinamis (hash table lookup), memperlambat eksekusi dan meningkatkan konsumsi memori untuk menyimpan representasi Map transisi. Solusinya: Normalisasikan bentuk objek segera setelah deserialisasi menggunakan schema parser baku (misal: TypeBox atau parsing manual terstruktur).

#### Skenario 3: Native Buffer Leak di Luar Batas Heap V8
Sebuah sistem transcoding video berbasis Node.js melaporkan konsumsi memori RSS mencapai 14GB pada container Kubernetes, namun grafik metrik `heapUsed` V8 hanya menunjukkan angka 350MB. Pod kemudian dimatikan paksa oleh sistem operasi dengan status `OOMKilled (Exit Code 137)`.  
*Pertanyaan*: Di manakah kebocoran memori ini terjadi dan tooling apa yang harus digunakan untuk mengidentifikasinya?  
*Solusi*: Kebocoran terjadi di **Non-Heap (Off-Heap) Memory**, kemungkinan berasal dari alokasi native C++ Addon, libuv worker buffers, atau alokasi `Buffer.allocUnsafe()` Node.js yang ditahan oleh referensi C++ native binding yang tidak pernah dibebaskan. Metrik Heap V8 (`v8.getHeapStatistics()`) tidak melacak memori off-heap ini. Penanganan: Gunakan command line profiler sistem operasi seperti `jemalloc` / `Valgrind` / `AddressSanitizer (ASan)`, atau monitor metrik `process.memoryUsage().arrayBuffers` dan `process.memoryUsage().external`.

---

## 16. Summary

```
                      V8 MEMORY ARCHITECTURE & LIFECYCLE
                      
      +---------------------------------------------------------------+
      |                   RESIDENT SET SIZE (RSS)                     |
      |                                                               |
      |  +---------------------------------------------------------+  |
      |  |                   V8 MANAGED HEAP                       |  |
      |  |                                                         |  |
      |  |  +----------------------+     +----------------------+  |  |
      |  |  |      NEW SPACE       |     |      OLD SPACE       |  |  |
      |  |  | (Minor GC: Scavenge) |     | (Major GC: Orinoco)  |  |  |
      |  |  | - From-Space         | --> | - Pointer Space      |  |  |
      |  |  | - To-Space           |     | - Data Space         |  |  |
      |  |  +----------------------+     +----------------------+  |  |
      |  |             |                            |              |  |
      |  |             v                            v              |  |
      |  |    Cheney's Copying               Tri-Color Marking     |  |
      |  |    High Allocation Rate           (White/Grey/Black)    |  |
      |  |    Pointers Promoted              Concurrent Sweeping   |  |
      |  |                                   Parallel Compacting   |  |
      |  +---------------------------------------------------------+  |
      |                                |                              |
      |  +-----------------------------+---------------------------+  |
      |  |                   OFF-HEAP / PRIMITIVES                 |  |
      |  |                                                         |  |
      |  |  - ArrayBuffer / SharedArrayBuffer (Contiguous Memory)  |  |
      |  |  - Node.js C++ Buffer Pool (Off-Heap Slab Allocator)    |  |
      |  |  - Multi-Threading Coordination via Atomics Primitives  |  |
      |  +---------------------------------------------------------+  |
      +---------------------------------------------------------------+
```

Memahami siklus hidup memori V8 dan GC membedakan insinyur software tingkat lanjut dari pengembang reguler:
1. **Memory Discipline**: Memori di JavaScript bersifat otomatis, tetapi tidak tak terbatas. Menulis kode performa tinggi menuntut pemahaman mendalam tentang alokasi objek dan perilaku engine di tingkat rendah (*mechanical sympathy*).
2. **Generational Awareness**: Desain sistem aplikasi harus memisahkan objek berumur sangat pendek (mudah dibersihkan oleh Minor GC) dari objek berumur panjang (dikelola dalam cache yang terkontrol).
3. **Primitive Over Abstraction**: Ketika berhadapan dengan data biner skala gigabyte atau jutaan event per detik, singkirkan abstraksi objek standar dan manfaatkan primitif biner kontigu: `ArrayBuffer`, `DataView`, dan sinkronisasi multi-threaded `SharedArrayBuffer` + `Atomics`.