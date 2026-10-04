# SEKSI 01 — IDENTITAS MODUL

* **Jalur Kurikulum:** 02-Programming-Languages
* **Topik Utama:** JavaScript Deep Internals
* **Modul:** Bab 03 Module 01
* **Judul:** Memory Lifecycle, Garbage Collection & Low-Level Primitives
* **Tingkat Kesulitan:** Advanced / Senior Engineering
* **Prasyarat Pengetahuan:**
  * Pemahaman mendalam tentang JavaScript Event Loop dan Asynchronous Model.
  * Pemahaman struktur data dasar (Array, Map, Set, Doubly-Linked List).
  * Pengalaman menggunakan Node.js runtime atau Browser Engine environment.
* **Perkiraan Waktu Penyelesaian:** 3 – 4 Jam Pembelajaran Intensif

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis Arsitektur Memori Engine V8:** Menjelaskan pembagian internal memori (Stack vs. Heap, New Space, Old Space, Large Object Space, Code Space) secara struktural.
2. **Membedah Mekanisme Garbage Collection (GC):** Menguraikan algoritma Orinoco, Minor GC (Scavenger/Cheney's Copying), Major GC (Mark-Sweep-Compact), serta teknik optimasi konkurensi (Concurrent Marking, Incremental Marking, Parallel Compacting).
3. **Mengidentifikasi Representasi Data Internal:** Memahami representasi Tagged Pointers (Smi vs. HeapObject) dan dampaknya terhadap konsumsi memori serta optimasi hidden classes.
4. **Menguasai Low-Level Memory Primitives:** Mengimplementasikan manipulasi byte-level secara langsung menggunakan `ArrayBuffer`, `TypedArray`, dan `DataView` dengan mempertimbangkan *endianness*.
5. **Mengelola Memori Non-Deterministik:** Memanfaatkan `WeakRef` dan `FinalizationRegistry` secara presisi tanpa memicu degradasi performa atau *memory leaks*.
6. **Mendiagnosis dan Mengeliminasi Memory Leaks:** Mengisolasi kebocoran memori pada lingkungan produksi menggunakan V8 profiling flags, Heap Snapshot, dan Allocation Timeline.

---

# SEKSI 03 — MINDSET & MENTAL MODEL

### Ilusi Otomasi Memori
Banyak pengembang menganggap bahwa bahasa dengan *Automatic Memory Management* seperti JavaScript membebaskan mereka dari tanggung jawab pengelolaan memori. Ini adalah ilusi berbahaya. JavaScript Engine (seperti V8, JavaScriptCore, SpiderMonkey) mengotomatiskan **reklamasi** memori, bukan **perencanaan** memori.

### Trade-Off Fundamental: Throughput vs. Latency
Setiap alokasi objek membawa biaya komputasi di masa depan. Garbage Collector beroperasi di bawah kompromi fundamental:
* Menghabiskan CPU cycles untuk membersihkan memori secara agresif menurunkan *latency* (jeda UI/server minimal), tetapi menurunkan *throughput* maksimum.
* Menunda pembersihan memori meningkatkan *throughput*, tetapi meningkatkan resiko *Stop-The-World (STW) spikes* dan *footprint* RAM yang masif.

```
+------------------------------------------------------------------+
| MENTAL MODEL: PHYSICAL MEMORY AS LEASED REAL ESTATE              |
|                                                                  |
| Objek bukan entitas abstrak. Setiap objek adalah blok byte fisik |
| yang disewa dari sistem operasi:                                 |
| 1. Alokasi = Menandatangani kontrak sewa (CPU & RAM cost).       |
| 2. Retensi Tak Sengaja = Membayar sewa untuk ruang tak terpakai. |
| 3. GC Pause = Audit gedung mendadak yang menghentikan semua      |
|    operasional normal (Stop-the-World).                          |
+------------------------------------------------------------------+
```

Menulis kode JavaScript berkinerja tinggi menuntut Anda berpikir layaknya *systems programmer*: sadari kapan representasi *pointer-heavy* harus digantikan oleh *contiguous binary buffers*, dan sadari siklus hidup setiap referensi yang dibuat oleh closure atau struktur data global.

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Arsitektur Alokasi Memori Engine V8

```
+------------------------------------------------------------------------------------+
|                                    V8 HEAP TOTAL                                   |
|                                                                                    |
|  +-------------------------------------+  +-------------------------------------+  |
|  |              NEW SPACE              |  |              OLD SPACE              |  |
|  |             (1 - 64 MB)             |  |            (Hingga GB-an)           |  |
|  |                                     |  |                                     |  |
|  |  +---------------+---------------+  |  |  +---------------+---------------+  |  |
|  |  |   FROM-SPACE  |    TO-SPACE   |  |  |  | OLD POINTER   |   OLD DATA    |  |  |
|  |  | (Active Alloc)| (GC Evacuate) |  |  |  |  (Obj References) | (Raw Payloads)|  |  |
|  |  |               |               |  |  |  +---------------+---------------+  |  |
|  |  |    Cheney's Copy Algorithm    |  |  |                                     |  |
|  |  +---------------+---------------+  |  |      Mark-Sweep-Compact Algorithm   |  |
|  +------------------|------------------+  +------------------^------------------+  |
|                     |                                        |                     |
|                     +------------ (Survivor 2x) -------------+                     |
|                                     Promosi                                        |
|                                                                                    |
|  +---------------------+  +---------------------+  +----------------------------+  |
|  | LARGE OBJECT SPACE  |  |      CODE SPACE     |  |          MAP SPACE         |  |
|  | (> AllocationLimit) |  |  (JIT Compiled Code|  |   (Shapes/Hidden Classes   |  |
|  | Never Moved by GC   |  |    Executable W^X)  |  |     Descriptor Arrays)     |  |
|  +---------------------+  +---------------------+  +----------------------------+  |
+------------------------------------------------------------------------------------+
|                                  SYSTEM C++ STACK                                  |
|  [ Call Frame: Contexts | Local Primitives | Object Pointer References (Root Set) ]|
+------------------------------------------------------------------------------------+
```

### Siklus Hidup Alokasi & Pipeline Garbage Collection

```
[Inisiasi: Objek Baru Dibuat]
         |
         v
Ukuran > K threshold? 
    |               \
   (Ya)             (Tidak)
    |                 \
    v                  v
[Alokasi Langsung]   [Alokasi di New Space: From-Space]
[Large Object Space]   |
                       v
         Apakah New Space Penuh?
               |              \
              (Ya)            (Tidak)
               |                \
               v                 v
        [Jalankan Minor GC]   [Lanjutkan Eksekusi]
        [Scavenger: Cheney]
               |
      Objek lolos 2 siklus?
          |          \
         (Ya)        (Tidak)
          |            \
          v             v
    [Promosi ke]    [Salin ke To-Space]
    [ Old Space]    [Swap From <-> To ]
          |
  Apakah Old Space Melampaui Heuristik Ambang Batas?
          |
         (Ya)
          |
          v
   [Jalankan Major GC: Full Mark-Compact (Orinoco)]
   1. Concurrent Marking (Latar Belakang)
   2. Incremental Marking (Interleaved STW)
   3. Parallel Sweeping/Compacting (Threads Terpisah)
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Tagged Pointers & Representasi Smi (Small Integer)
Di dalam arsitektur 64-bit, alokasi *pointer* mentah ke setiap angka primitif akan memboroskan memori. V8 menggunakan teknik manipulasi bit bernama **Pointer Tagging**.

Setiap slot nilai direpresentasikan dalam 64-bit (atau 32-bit jika V8 Pointer Compression aktif):
* **Smi (Small Integer):** Diakhiri dengan bit `0`. Contoh format 32-bit: `[31-bit signed integer][0]`. Nilai di-*shift* 1 bit ke kiri tanpa perlu alokasi heap.
* **HeapObject Pointer:** Diakhiri dengan bit `1`. Menunjuk ke alamat memori sebenarnya di V8 Heap (harus *word-aligned*, sehingga 2-3 bit terendah selalu 0, memungkinkan bit terakhir diubah menjadi `1` sebagai penanda/tag).

```
Nilai Smi (Angka 42):
+-------------------------------------------------------------+---+
| 00000000 00000000 00000000 00000000 00000000 00000000 0010101 | 0 |  <-- Bit 0 = Smi
+-------------------------------------------------------------+---+

Pointer ke Heap Object (Alamat 0x...4):
+-------------------------------------------------------------+---+
| 00111111 11010000 ... Heap Address ...              0000010 | 1 |  <-- Bit 1 = Pointer
+-------------------------------------------------------------+---+
```

### 2. Generational Hypothesis
Mayoritas objek mati sesaat setelah dialokasikan (*Infant Mortality Rate* tinggi). Berdasarkan observasi empiris ini, V8 membagi Heap menjadi dua generasi:
1. **Young Generation (New Space):** Dirancang untuk alokasi cepat dan pembersihan frekuensi tinggi dengan *overhead* minimum.
2. **Old Generation (Old Space):** Menampung objek yang bertahan dari dua kali siklus Minor GC. Diperiksa lebih jarang dengan algoritma yang lebih kompleks.

### 3. Orinoco Collector Sub-systems
* **Minor GC (Scavenger):** Menggunakan algoritma Cheney. Membagi New Space menjadi *From-Space* dan *To-Space*. Selama Scavenging, objek hidup disalin secara kontigu ke *To-Space* (mengeliminasi fragmentasi secara otomatis), lalu peran kedua ruang dibalik (*pointer swap*).
* **Major GC (Mark-Sweep-Compact):**
  * **Marking:** Melakukan penelusuran graf dari *Root Set* (Global variables, DOM tree, Current Stack Frame) menggunakan sistem tri-color (*White*, *Grey*, *Black*). Dilakukan secara konkruen di *worker threads*.
  * **Sweeping:** Memindai *memory chunks* untuk menemukan slot kosong yang ditinggalkan objek *White* (tak terjangkau), lalu mencatatnya ke dalam *Free-List*.
  * **Compacting:** Menggeser objek-objek *Black* (hidup) yang terfragmentasi ke awal halaman memori untuk menciptakan blok memori kontigu yang besar, memperbarui semua referensi pointer yang menunjuk ke objek-objek tersebut.

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI

### Memory Lifecyle: Allocate $\rightarrow$ Use $\rightarrow$ Release
Siklus hidup memori universal terdiri dari tiga fase:
1. **Allocate:** Sistem operasi menyediakan memori (pada JS, engine mengalokasikannya di Stack atau Heap).
2. **Use:** Membaca atau menulis data ke lokasi memori yang telah dialokasikan.
3. **Release:** Memori yang tidak lagi dibutuhkan dibebaskan agar dapat digunakan kembali oleh aplikasi.

### Low-Level Memory Primitives
Ekosistem JavaScript modern menyediakan akses memori berorientasi biner langsung melalui spesifikasi ECMAScript typed arrays:

#### 1. ArrayBuffer
`ArrayBuffer` adalah representasi memori biner mentah (*raw memory buffer*) dengan panjang tetap. `ArrayBuffer` tidak dapat dibaca atau dimanipulasi secara langsung; ia hanyalah referensi ke alokasi memori berkelanjutan di C++ heap (*out-of-V8-heap* untuk buffer besar).

#### 2. TypedArray Views
`TypedArray` (seperti `Uint8Array`, `Int32Array`, `Float64Array`) adalah *view* bertipe di atas `ArrayBuffer`. `TypedArray` menginterpretasikan rentang byte mentah sebagai elemen-elemen homogen:
$$\text{Offset Byte} = \text{Index} \times \text{Bytes Per Element}$$

#### 3. DataView
Berbeda dengan `TypedArray` yang terkunci pada arsitektur mesin host (umumnya *Little-Endian* pada x86 dan ARM modern), `DataView` menyediakan akses fleksibel berorientasi byte dengan kendali eksplisit atas **Endianness** (*Big-Endian* vs. *Little-Endian*):
* **Big-Endian (Network Byte Order):** Byte paling signifikan disimpan pada alamat memori terendah.
* **Little-Endian:** Byte paling tidak signifikan disimpan pada alamat memori terendah.

#### 4. SharedArrayBuffer & Atomics
`SharedArrayBuffer` memetakan blok memori yang sama ke beberapa Web Workers atau Threads di Node.js (`worker_threads`). Karena operasi read-modify-write bersamaan dapat menyebabkan *data races*, namespace `Atomics` menyediakan operasi tak terpisahkan (*atomic operations*) seperti `Atomics.load()`, `Atomics.store()`, `Atomics.add()`, `Atomics.wait()`, dan `Atomics.notify()`.

### Weak References: Menghindari Memory Leaks
* **Strong Reference:** Referensi standar. Mencegah objek dikumpulkan oleh Garbage Collector.
* **WeakMap & WeakSet:** Kunci (key) bersifat lemah. Jika tidak ada referensi kuat lain ke objek kunci tersebut, entri dapat dieliminasi oleh GC. Kuncinya tidak *enumerable*.
* **WeakRef:** Objek yang memungkinkan pemeliharaan referensi ke target tanpa mencegah target tersebut di-GC. Akses dilakukan melalui method `.deref()`, yang mengembalikan objek asli jika masih ada, atau `undefined` jika sudah dibersihkan.
* **FinalizationRegistry:** Fasilitas callback untuk membersihkan sumber daya eksternal (misal: *file descriptors*, *C++ handles*) saat objek JavaScript tertentu telah musnah dari memori.

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah kode fungsional yang mendemonstrasikan manipulasi biner tingkat rendah menggunakan `ArrayBuffer`, `DataView`, `TypedArray`, serta penggunaan `WeakRef` dan `FinalizationRegistry`:

```javascript
// fundamental-memory.js

// 1. Alokasi Buffer Mentah (8 Byte)
const rawBuffer = new ArrayBuffer(8);
console.log(`Panjang Buffer: ${rawBuffer.byteLength} byte`);

// 2. Manipulasi Menggunakan DataView dengan Variasi Endianness
const dataView = new DataView(rawBuffer);

// Tulis 32-bit Integer (4 byte) di offset 0: Format Big-Endian
dataView.setInt32(0, 0x12345678, false);

// Tulis 16-bit Unsigned Integer (2 byte) di offset 4: Format Little-Endian
dataView.setUint16(4, 0xABCD, true);

// Baca representasi byte mentah menggunakan Uint8Array View
const byteInspector = new Uint8Array(rawBuffer);
console.log("Struktur Memori Heksadesimal Mentah:");
console.log(Array.from(byteInspector).map(b => '0x' + b.toString(16).padStart(2, '0')).join(' '));

// 3. Rekonstruksi Nilai dengan Memperhatikan Endianness
const readBigEndian = dataView.getInt32(0, false);
const readLittleEndian = dataView.getInt32(0, true);
console.log(`Baca Offset 0 (Big-Endian): 0x${readBigEndian.toString(16)}`);
console.log(`Baca Offset 0 (Diinterpretasi Little-Endian): 0x${readLittleEndian.toString(16)}`);

// 4. Implementasi Lifecycle Monitoring via WeakRef & FinalizationRegistry
const cleanupRegistry = new FinalizationRegistry((heldValue) => {
  console.log(`[GC Telemetry]: Objek dengan payload '${heldValue}' telah di-sweep oleh Garbage Collector.`);
});

function allocateMonitoredScope() {
  let ephemeralResource = {
    id: "METRIC_COLLECTOR_CHUNK_01",
    payload: new Uint32Array(1024 * 1024) // Mengalokasikan 4MB data mentah
  };

  // Daftarkan ke cleanup registry
  cleanupRegistry.register(ephemeralResource, ephemeralResource.id);

  // Buat referensi lemah
  const weakRef = new WeakRef(ephemeralResource);

  console.log(`Status sebelum keluar scope: deref() is valid -> ${weakRef.deref() !== undefined}`);
  
  // ephemeralResource keluar dari lexical scope di sini, menjadi eligible untuk GC
  return weakRef;
}

const observedRef = allocateMonitoredScope();

// Catatan: Pemanggilan deref() di luar lexical scope
console.log(`Status segera setelah keluar scope: deref() is valid -> ${observedRef.deref() !== undefined}`);
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi mekanis dari potongan kode pada Seksi 07:

1. `const rawBuffer = new ArrayBuffer(8);`
   * **Engine Level:** V8 membuat instance `ArrayBuffer` di V8 Heap dan mengalokasikan 8 byte memori yang berdekatan (*contiguous block*) pada C++ heap menggunakan alokator internal (`malloc` atau `PartitionAlloc`). Nilai setiap byte diinisialisasi ke bit `0x00`.
2. `const dataView = new DataView(rawBuffer);`
   * **Engine Level:** Membuat *wrapper pointer* (metadata view) yang menunjuk ke base memory address dari `rawBuffer`. Tidak ada alokasi buffer baru di memori; ini murni sebuah struktur pembaca (*accessor layer*).
3. `dataView.setInt32(0, 0x12345678, false);`
   * **Engine Level:** Menulis 4 byte mulai dari offset 0. Parameter `false` menginstruksikan engine untuk menulis data dalam urutan **Big-Endian**. 
   * Representasi fisik di alamat:
     * `Offset 0: 0x12`
     * `Offset 1: 0x34`
     * `Offset 2: 0x56`
     * `Offset 3: 0x78`
4. `dataView.setUint16(4, 0xABCD, true);`
   * **Engine Level:** Menulis 2 byte mulai dari offset 4. Parameter `true` menginstruksikan engine menggunakan urutan **Little-Endian** (Least Significant Byte disimpan lebih dulu).
   * Representasi fisik di alamat:
     * `Offset 4: 0xCD`
     * `Offset 5: 0xAB`
5. `const byteInspector = new Uint8Array(rawBuffer);`
   * **Engine Level:** Mengarahkan TypedArray langsung ke buffer eksisting. Menghasilkan *aliasing* memori: memodifikasi `byteInspector` akan langsung terlihat oleh `dataView` dan sebaliknya tanpa *copying overhead*.
6. `const cleanupRegistry = new FinalizationRegistry((heldValue) => { ... });`
   * **Engine Level:** Mendaftarkan *callback queue* yang ditangani secara asinkron di microtask checkpoint setelah GC Major/Minor menandai objek terdaftar sebagai *unreachable* dan membersihkannya. `heldValue` tidak boleh mereferensikan objek target secara langsung agar tidak menciptakan siklus referensi baru.
7. `const weakRef = new WeakRef(ephemeralResource);`
   * **Engine Level:** Membuat objek referensi khusus di mana penunjuk (*pointer*) ke `ephemeralResource` tidak dihitung sebagai akar (*root*) atau sisi penghubung graf (*graph edge*) selama *Marking Phase* V8 GC.
8. `ephemeralResource = null; (secara implisit saat scope fungsi berakhir)`
   * **Engine Level:** Satu-satunya referensi kuat ke objek hilang dari *activation record* / Stack frame. Objek kini diwarnai *White* pada algoritma penandaan V8 dan berstatus dapat diklaim kembali (*reclaimable*).

---

# SEKSI 09 — STUDI KASUS NYATA

### Skenario: Node.js High-Throughput Financial Stream Aggregator
Sebuah sistem mikroservis di bursa efek menerima 100.000 pesan/detik melalui protokol TCP biner mentah. Setiap pesan merepresentasikan *limit order tick* (Order ID, Stock Ticker, Price, Volume, Timestamp).

### Kegagalan Produksi Awal
* **Desain Naif:** Setiap kali paket TCP tiba, sistem mem-parsing buffer biner menjadi representasi JavaScript Plain Object (`{ id: ..., ticker: ..., price: ... }`).
* **Gejala:** 
  1. CPU utilisasi berada di 100%, tetapi hanya 35% digunakan untuk kalkulasi bisnis; sisanya habis dalam eksekusi V8 Garbage Collection (*Major GC Pauses*).
  2. Latensi P99.9 meroket hingga 850 milidetik (Stop-The-World pause).
  3. Terjadi lonjakan New Space allocations yang memicu Scavenger bekerja terus menerus, mendorong ribuan objek pendek ke Old Space (*premature promotion*), yang berujung pada seringnya Full Mark-Compact GC.

### Solusi Teknis
Mengimplementasikan **Zero-Allocation Ring Buffer** menggunakan kombinasi `ArrayBuffer` dan `DataView` yang dipooling secara statis. Menghapus konversi biner-ke-objek dalam *hot-path* pemrosesan data, mengeliminasi GC churn hingga 99.8%.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah implementasi sistem pemrosesan transaksi biner berkinerja tinggi berbasis *Fixed Memory Buffer Pooling*:

```javascript
// binary-tick-processor.mjs
import { Buffer } from 'node:buffer';

/**
 * SKEMA DATA TICKER (Total: 24 Bytes per Transaksi)
 * Offset 0  - [Uint32] Transaction ID (4 byte)
 * Offset 4  - [Uint32] Timestamp Epoch Sec (4 byte)
 * Offset 8  - [Uint8Array(8)] Symbol (ASCII, 8 byte)
 * Offset 16 - [Float64] Price (8 byte)
 */
export const TICK_SIZE = 24;

export class BinaryMemoryPool {
  #buffer;
  #dataView;
  #capacity;
  #currentSlot = 0;

  constructor(maxTicks) {
    this.#capacity = maxTicks;
    // Alokasi memori berukuran masif di awal secara berkelanjutan (Contiguous Memory)
    this.#buffer = new ArrayBuffer(this.#capacity * TICK_SIZE);
    this.#dataView = new DataView(this.#buffer);
    this.symbolDecoder = new TextDecoder('ascii');
  }

  get capacity() {
    return this.#capacity;
  }

  get currentUsage() {
    return this.#currentSlot;
  }

  /**
   * Menulis langsung ke memory heap tanpa membuat objek JS intermediet.
   */
  writeTick(txId, timestamp, symbolStr, price) {
    if (this.#currentSlot >= this.#capacity) {
      throw new Error("Pool Buffer Penuh! Wajib flush sebelum alokasi baru.");
    }

    const baseOffset = this.#currentSlot * TICK_SIZE;

    // Tulis Tx ID
    this.#dataView.setUint32(baseOffset + 0, txId, true);
    // Tulis Timestamp
    this.#dataView.setUint32(baseOffset + 4, timestamp, true);

    // Tulis Simbol (ASCII max 8 karakter)
    for (let i = 0; i < 8; i++) {
      const charCode = i < symbolStr.length ? symbolStr.charCodeAt(i) : 0;
      this.#dataView.setUint8(baseOffset + 8 + i, charCode);
    }

    // Tulis Price
    this.#dataView.setFloat64(baseOffset + 16, price, true);

    this.#currentSlot++;
    return baseOffset;
  }

  /**
   * Pembacaan data in-place langsung dari offset, menghindari GC Object Creation.
   */
  readPrice(slotIndex) {
    const baseOffset = slotIndex * TICK_SIZE;
    return this.#dataView.getFloat64(baseOffset + 16, true);
  }

  readTxId(slotIndex) {
    const baseOffset = slotIndex * TICK_SIZE;
    return this.#dataView.getUint32(baseOffset + 0, true);
  }

  /**
   * Daur ulang memori instan tanpa intervensi GC (O(1) operation).
   */
  reset() {
    this.#currentSlot = 0;
  }

  getRawBuffer() {
    return this.#buffer;
  }
}

// =========================================================================
// SIMULASI LOAD HIGH-THROUGHPUT
// =========================================================================

const BATCH_SIZE = 1_000_000;
const memoryPool = new BinaryMemoryPool(BATCH_SIZE);

console.time("Proses 1 Juta Tick (Zero-Allocation Pool)");

for (let i = 0; i < BATCH_SIZE; i++) {
  memoryPool.writeTick(i, 1710000000 + i, "BBCA", 9850.50 + (i % 100));
}

// Kalkulasi agregasi in-place
let totalValue = 0;
for (let i = 0; i < BATCH_SIZE; i++) {
  totalValue += memoryPool.readPrice(i);
}

console.timeEnd("Proses 1 Juta Tick (Zero-Allocation Pool)");
console.log(`Total Volume Dihitung: ${totalValue.toFixed(2)}`);
console.log(`Memori fisik statis dialokasikan: ${(BATCH_SIZE * TICK_SIZE) / (1024 * 1024)} MB`);

// Reset untuk reuse tanpa memicu Garbage Collector
memoryPool.reset();
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

| Karakteristik | High-Level Plain Objects (`{}`) | TypedArray / ArrayBuffer | Low-Level DataView |
| :--- | :--- | :--- | :--- |
| **Beban Alokasi (Allocation Footprint)** | Sangat Tinggi (Object header, Hidden Class/Map pointer, Property array). | Sangat Rendah (Blok byte kontigu murni, nol per-item headers). | Sangat Rendah (Berbagi buffer yang sama dengan TypedArray). |
| **Intervensi Garbage Collector** | Konstan dan berat (Memicu Scavenge & Mark-Sweep berulang). | Nol selama lifecycle (Buffer dialokasikan sekali / persistent). | Nol jika buffer dipertahankan secara statis. |
| **Kecepatan Akses CPU (L1/L2 Cache)** | Kurang efisien (Data tersebar melalui pointer chashing di Heap). | Sangat Efisien (Data kontigu, memaksimalkan *CPU Cache Lines*). | Sedikit lebih lambat dari TypedArray karena abstraksi endianness. |
| **Fleksibilitas Struktur Data** | Sangat Tinggi (Dynamic schema, polymorphic, dynamic keys). | Kaku (Hanya tipe data numerik seragam per View). | Tinggi untuk data heterogen (dapat mix Uint8, Int32, Float64). |
| **Kompleksitas Pengembangan** | Sangat Rendah (Idiomatik, familiar bagi mayoritas developer). | Menengah (Memerlukan pemahaman batas offset numerik). | Tinggi (Mengharuskan kalkulasi manual *byte offset* dan *endianness*). |
| **Cross-Thread Zero-Copy** | Tidak Mendukung (Harus di-serialize lewat `postMessage`/JSON). | Mendukung (`SharedArrayBuffer` atau Transferable Objects). | Mendukung via representasi `SharedArrayBuffer` di baliknya. |

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. Detached ArrayBuffer
Ketika `ArrayBuffer` ditransfer antar thread menggunakan `structuredClone(buffer, { transfer: [buffer] })` atau `worker.postMessage(buffer, [buffer])`, buffer asli di thread pengirim akan berstatus **Detached** (panjang byte menjadi 0, pointer internal dialihkan ke `nullptr`).
* **Bahaya:** Upaya membaca atau menulis ke TypedArray yang terikat pada *detached buffer* akan melempar `TypeError: Cannot perform %TypedArray%.prototype... on a detached ArrayBuffer`.

### 2. TypedArray `.slice()` vs `.subarray()`
* `TypedArray.prototype.slice()`: Mengalokasikan `ArrayBuffer` **baru** dan menyalin bit-bit secara independen (*deep copy*).
* `TypedArray.prototype.subarray()`: Membuat *view* **baru** di atas `ArrayBuffer` yang **sama** (*zero-copy reference*).
* **Pitfall:** Menggunakan `subarray` untuk menyimpan data kecil dari buffer raksasa mencegah seluruh buffer besar tersebut di-GC, memicu *hidden leak*.

```javascript
// Memori 100MB tertahan di RAM hanya karena 4 byte yang direferensikan
const massiveBuffer = new ArrayBuffer(100 * 1024 * 1024);
const leakProneSlice = new Uint8Array(massiveBuffer).subarray(0, 4);
```

### 3. V8 Pointer Alignment and Unaligned Memory Accesses
Saat membaca tipe data multi-byte (misal `Float64` = 8 byte) menggunakan TypedArray, *byte offset* **harus** merupakan kelipatan dari ukuran elemen.
```javascript
const buffer = new ArrayBuffer(10);
// Melempar RangeError: byte offset of Float64Array should be a multiple of 8
const invalidView = new Float64Array(buffer, 3);
```
Solusi: Gunakan `DataView` yang mendukung akses *unaligned*, meskipun dengan penalti performa mikro pada arsitektur CPU tertentu.

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. The Closure Retaining Scope Trap
Closure menahan seluruh lexical environment, bukan hanya variabel spesifik yang digunakan, jika variabel lain dalam lexical scope yang sama ditutup oleh fungsi internal lainnya.

```javascript
// SALAH: bufferHolder tertahan di memori melalui closure tak langsung
function setupDataConsumer() {
  const hugePayload = new Uint8Array(50 * 1024 * 1024); // 50 MB
  const metaInfo = { id: 101, status: "READY" };

  return {
    getMeta() {
      // Closure ini hanya butuh metaInfo, TAPI scope menahan hugePayload 
      // jika ada closure lain di scope ini yang mereferensikannya!
      return metaInfo.id;
    },
    debugTrace() {
      console.log(hugePayload.length);
    }
  };
}
```

```javascript
// BENAR: Isolasi scope secara eksplisit atau nullify referensi berat
function setupDataConsumerFixed() {
  let hugePayload = new Uint8Array(50 * 1024 * 1024);
  const id = 101;
  
  // Pisahkan siklus hidup data
  const debugTrace = () => console.log(hugePayload.length);
  debugTrace();
  hugePayload = null; // Putus rantai GC reachable

  return {
    getMeta() {
      return id; // Lexical environment bersih dari payload raksasa
    }
  };
}
```

### 2. Accidental DOM Retainers via Detached Nodes
Menghapus elemen dari pohon DOM dengan `element.remove()` tidak akan membebaskan elemen dari memori jika elemen tersebut (atau salah satu anaknya) masih disimpan dalam array JavaScript atau event listener.

```javascript
// SALAH: Memory Leak DOM
const cache = [];
function bindButton() {
  const btn = document.createElement("button");
  btn.textContent = "Click Me";
  document.body.appendChild(btn);
  cache.push(btn); // Menyimpan referensi kuat
  btn.remove();    // Dihapus dari DOM visual, tapi TETAP HIDUP di Heap V8!
}
```

```javascript
// BENAR: Gunakan WeakSet atau hapus referensi array secara eksplisit
const cacheClean = new WeakSet();
function bindButtonClean() {
  const btn = document.createElement("button");
  document.body.appendChild(btn);
  cacheClean.add(btn); // Weak reference: tidak mencegah GC
  btn.remove();        // GC bebas membersihkan btn saat tidak terjangkau lagi
}
```

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Prinsip "Allocate Once, Reuse Infinitely":** Pada subsistem dengan throughput tinggi (misal: WebSocket server, Game engine, Parsing Engine), inisialisasi *object pools* atau *typed buffers* saat *booting*, bukan saat *runtime loop*.
2. **Favoritkan Monomorphic Callsites:** V8 melacak bentuk objek (*Hidden Classes / Shapes*). Mengubah skema objek secara dinamis (`delete obj.prop` atau menambah properti sembarangan) menurunkan optimasi TurboFan ke status *Megamorphic*, yang memperlambat akses memori dan meningkatkan overhead pointer tracking.
3. **Posisikan WeakRef Sebagai Fallback Terakhir:** Jangan gunakan `WeakRef` untuk logika arsitektur primer. GC bersifat non-deterministik: Anda tidak bisa memprediksi kapan GC akan berjalan. Mengandalkan `WeakRef` untuk konsistensi data bisnis adalah *anti-pattern*.
4. **Hindari Primitive Boxing:** Operasi yang secara implisit membungkus nilai primitif ke dalam objek (misal: `"string".toUpperCase()` yang berulang-ulang dalam miliaran operasi teks) menghasilkan alokasi singkat yang menekan *Scavenger GC*. Gunakan buffer statis jika memproses data string biner.

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### Benchmarking GC Impact: Pooling vs Allocation Per Request

Mari amati disparitas alokasi memori antara alokasi ad-hoc dan pooling menggunakan node performance hooks:

```javascript
// memory-bench.mjs
import { performance } from 'node:perf_hooks';

const ITERATIONS = 5_000_000;

// Skenario A: Ad-Hoc Object Allocation (Menekan GC)
function runAdHocAllocations() {
  const startMem = process.memoryUsage().heapUsed;
  const start = performance.now();

  let sink;
  for (let i = 0; i < ITERATIONS; i++) {
    sink = {
      x: i,
      y: i * 2,
      active: true
    };
  }

  const end = performance.now();
  const endMem = process.memoryUsage().heapUsed;
  console.log(`[Ad-Hoc] Durasi: ${(end - start).toFixed(2)} ms | Heap Delta: ${((endMem - startMem) / 1024 / 1024).toFixed(2)} MB`);
  return sink;
}

// Skenario B: Flat TypedArray Allocation (Zero Object Churn)
function runContiguousFlatAllocation() {
  const startMem = process.memoryUsage().heapUsed;
  const start = performance.now();

  // Dialokasikan SEKALI: Menampung 5 juta x, y (Int32) dan active (Uint8)
  const xValues = new Int32Array(ITERATIONS);
  const yValues = new Int32Array(ITERATIONS);

  for (let i = 0; i < ITERATIONS; i++) {
    xValues[i] = i;
    yValues[i] = i * 2;
  }

  const end = performance.now();
  const endMem = process.memoryUsage().heapUsed;
  console.log(`[Flat Array] Durasi: ${(end - start).toFixed(2)} ms | Heap Delta: ${((endMem - startMem) / 1024 / 1024).toFixed(2)} MB`);
  return { xValues, yValues };
}

console.log("=== MEMULAI PERFORMANCE EXPERIMENT ===");
runAdHocAllocations();
runContiguousFlatAllocation();
```

### Eksekusi V8 Profiler Flags
Jalankan benchmark di atas dengan flag internal V8 untuk menganalisis frekuensi GC pauses:
```bash
node --trace-gc --trace-gc-ignore-scavenger memory-bench.mjs
```
Output flag `--trace-gc` akan memperlihatkan baris `[Mark-sweep (reduce library)]` saat eksekusi Ad-Hoc berjalan, sementara eksekusi Contiguous Flat Array mengeksekusi operasi secara mulus tanpa interupsi Major GC.

---

# SEKSI 16 — KEAMANAN & HARDENING

### 1. Mitigasi Spectre via COOP & COEP
`SharedArrayBuffer` dinonaktifkan secara *default* di browser modern pasca kerentanan *Spectre*. Serangan *Spectre* memanfaatkan timer beresolusi tinggi yang dibangun di atas manipulasi memori bersama untuk membaca data lintas *origin* melalui analisis *side-channel CPU branch prediction*.

Untuk mengaktifkan `SharedArrayBuffer` di browser, Anda **wajib** menyetel HTTP Response Headers:
```http
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Embedder-Policy: require-corp
```

### 2. Atomics untuk Mencegah Race Conditions
Ketika dua thread mengakses `SharedArrayBuffer` secara bersamaan, modifikasi non-atomik dapat menyebabkan korupsi memori logis (*Torn Writes*).

```javascript
// worker-thread.mjs
import { parentPort, workerData } from 'node:worker_threads';

const sharedBuffer = workerData.buffer;
const sharedArray = new Int32Array(sharedBuffer);

// TIDAK AMAN: sharedArray[0]++ (Bukan operasi atomik, melibatkan fetch, add, store)
// AMAN: Operasi Hardware-Level Atomic Lock
Atomics.add(sharedArray, 0, 1);
```

### 3. Buffer Bounds Check Validation
Meskipun V8 melindungi dari *Buffer Overflow* C++ klasik (membaca di luar batas TypedArray melempar error atau mengembalikan `undefined`), penulisan logika yang salah pada buffer biner mentah dapat menimpa data transaksi lain dalam pool (*Data Corruption*). Selalu lakukan validasi offset secara tegas sebelum mengeksekusi `setUint32`/`setFloat64`.

---

# SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### 1. Programmatic Heap Telemetry
Di Node.js, gunakan modul native `v8` untuk mendapatkan metrik granular terkait struktur ruang heap:

```javascript
// heap-monitor.mjs
import v8 from 'node:v8';

export function dumpDetailedHeapSpace() {
  const heapSpaces = v8.getHeapSpaceStatistics();
  console.table(heapSpaces.map(space => ({
    Space: space.space_name,
    SizeMB: (space.space_size / 1024 / 1024).toFixed(2),
    UsedMB: (space.space_used_size / 1024 / 1024).toFixed(2),
    AvailableMB: (space.space_available_size / 1024 / 1024).toFixed(2),
    PhysicalSizeMB: (space.physical_space_size / 1024 / 1024).toFixed(2)
  })));
}

dumpDetailedHeapSpace();
```

### 2. V8 Diagnostic Core Flags
Gunakan argumen CLI berikut saat mendiagnosis sistem di lingkungan *staging*:
* `--max-old-space-size=4096`: Membatasi memori heap Old Space maksimum sebesar 4 GB.
* `--expose-gc`: Mengizinkan kode memanggil fungsi native global `gc()`. Hanya untuk benchmarking/analisis, jangan pernah digunakan di produksi!
* `--heap-prof`: Menghasilkan sampling profile V8 Heap yang dapat divisualisasikan langsung di Google Chrome DevTools (Tab Memory $\rightarrow$ Load Profile).

### 3. Mengambil Heap Snapshot Secara Programatik Saat Anomali Terjadi
```javascript
import v8 from 'node:v8';
import fs from 'node:fs';

export function captureHeapSnapshotOnPressure(thresholdPercentage = 0.85) {
  const stats = v8.getHeapStatistics();
  const usageRatio = stats.used_heap_size / stats.total_heap_size;

  if (usageRatio > thresholdPercentage) {
    const filename = `heap-${Date.now()}.heapsnapshot`;
    const snapshotStream = v8.getHeapSnapshot();
    const fileStream = fs.createWriteStream(filename);
    snapshotStream.pipe(fileStream);
    console.warn(`[EMERGENCY GC DUMP] Rasio Heap ${usageRatio.toFixed(2)}. Snapshot disimpan ke ${filename}`);
  }
}
```

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

### Mekanisme Memori Utama
* **Stack:** Alokasi cepat, ukuran tetap, menyimpan konteks eksekusi primitif dan pointer objek.
* **Heap:** Alokasi dinamis, memuat objek tak terstruktur, dikelola via Garbage Collection.
* **Scavenger (Minor GC):** Menghapus objek baru di New Space menggunakan algoritma penyalinan Cheney. Efisien dan berlatensi sangat rendah.
* **Mark-Sweep-Compact (Major GC):** Membersihkan Old Space. Terdiri dari *Concurrent Marking*, *Parallel Sweeping*, dan *Compacting* untuk mencegah fragmentasi memori.

### Cheat Sheet Binary Primitives

```javascript
// Alokasi 16 byte mentah
const buf = new ArrayBuffer(16);

// Akses tipe homogen (indeks berbasis elemen)
const u32 = new Uint32Array(buf); // 4 elemen (masing-masing 4 byte)
u32[0] = 4294967295;

// Akses byte individual tanpa copy (indeks berbasis byte)
const u8 = new Uint8Array(buf);
console.log(u8[0]); // 255

// Akses heterogen fleksibel dengan deklarasi endianness
const dv = new DataView(buf);
dv.setFloat32(0, 3.14159, true);  // Little-Endian
dv.setInt16(4, -1200, false);      // Big-Endian
```

### Cheat Sheet GC Flags
* `node --trace-gc main.js` $\rightarrow$ Log status GC dasar.
* `node --trace-gc-verbose main.js` $\rightarrow$ Log durasi tiap fase (marking, sweeping).
* `node --max-old-space-size=N` $\rightarrow$ Menentukan limit Old Space dalam MegaByte.

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Basic (1 - 5)

1. **Di manakah letak penyimpanan dari nilai variabel primitif `const x = 42;` dalam konteks eksekusi fungsi normal pada V8 Engine?**
   * A. Old Space di dalam Heap.
   * B. Langsung di dalam Stack Frame fungsi tersebut sebagai Small Integer (Smi).
   * C. Large Object Space.
   * D. Map Space.

2. **Algoritma pembersihan memori apakah yang secara fundamental digunakan oleh Minor GC (Scavenger) pada V8 Engine?**
   * A. Mark-Sweep-Compact.
   * B. Reference Counting.
   * C. Cheney's Copying Algorithm.
   * D. Tri-color incremental Sweeper.

3. **Apa perbedaan struktural utama antara `TypedArray.prototype.slice()` dan `TypedArray.prototype.subarray()`?**
   * A. `slice` mengembalikan DataView, sedangkan `subarray` mengembalikan ArrayBuffer.
   * B. `slice` membuat salinan ArrayBuffer baru (deep copy), sedangkan `subarray` membuat view baru di atas ArrayBuffer yang sama (zero copy).
   * C. `subarray` hanya bekerja pada tipe data Float.
   * D. Tidak ada perbedaan fungsional selain alias method.

4. **Karakteristik unik apa yang membedakan `WeakMap` dari standar `Map` dalam konteks referensi objek?**
   * A. Kunci `WeakMap` dapat diiterasi menggunakan `for..of`.
   * B. Kunci `WeakMap` harus berupa Objek dan tidak mencegah proses Garbage Collection jika tidak ada referensi kuat lain.
   * C. `WeakMap` menyimpan datanya di System Stack bukan di V8 Heap.
   * D. Nilai (values) di dalam `WeakMap` selalu di-freeze secara otomatis.

5. **Apa fungsi dari sistem "Pointer Tagging" pada arsitektur V8 64-bit?**
   * A. Membedakan apakah sebuah word 64-bit merepresentasikan Smi (Small Integer) atau pointer ke HeapObject tanpa membedah alokasi heap.
   * B. Melindungi memori dari serangan SQL Injection.
   * C. Mencegah closure mengakses variabel luar.
   * D. Mengunci buffer ketika diakses oleh Web Worker.

---

### Soal Intermediate (6 - 10)

6. **Perhatikan kode berikut:**
   ```javascript
   let registry = new FinalizationRegistry((held) => console.log(held));
   (() => {
     let payload = { data: new ArrayBuffer(1024) };
     registry.register(payload, "Payload Destroyed");
   })();
   ```
   **Mengapa kita TIDAK BOLEH mengandalkan pemanggilan callback `FinalizationRegistry` di atas untuk mengeksekusi logika kritis (seperti menyimpan state transaksi perbankan)?**
   * A. Karena `FinalizationRegistry` hanya bekerja pada browser, bukan di Node.js.
   * B. Karena GC berjalan non-deterministik; engine tidak memberikan jaminan bahwa GC akan dijalankan sebelum program berhenti.
   * C. Karena eksekusi callback tersebut melempar error `SecurityError` secara bawaan.
   * D. Karena `payload` masih tertahan oleh parameter `held`.

7. **Jika sebuah `ArrayBuffer` berukuran 16 byte dibaca menggunakan `new Float64Array(buffer, 4)`, apa yang akan terjadi di runtime?**
   * A. Mengembalikan array berisi dua elemen numerik float.
   * B. Engine otomatis menambahkan padding 4 byte secara dinamis.
   * C. Melempar `RangeError` karena byte offset Float64Array harus merupakan kelipatan dari 8 byte.
   * D. Nilai otomatis di-cast menjadi BigInt64Array.

8. **Sebuah memory leak terjadi di mana heap terus membesar meskipun fungsi `clearInterval()` telah dipanggil. Apa penyebab paling logis dalam representasi V8?**
   * A. Pointer Compression gagal mengompres pointer.
   * B. Masih terdapat closure lain di runtime scope yang mempertahankan referensi ke target data melalui lexical environment chain.
   * C. Ukuran Large Object Space telah melewati batas 4GB.
   * D. DataView membaca data menggunakan Big-Endian pada CPU Little-Endian.

9. **Apa implikasi performa dari fenomena *Premature Promotion* pada sistem Garbage Collection V8?**
   * A. Objek berumur pendek lolos ke Old Space secara prematur, menyebabkan Old Space cepat penuh dan meningkatkan frekuensi Major GC (Stop-the-World) yang mahal.
   * B. Kecepatan baca disk menurun drastis.
   * C. Menghapus hidden class dari memori secara permanen.
   * D. Memaksa engine beralih dari JIT Compilation ke mode Pure Interpreter (Ignition).

10. **Bagaimanakah urutan byte fisik dari angka integer 32-bit `0x0A0B0C0D` jika ditulis ke dalam memori menggunakan arsitektur Little-Endian mulai dari offset 0?**
    * A. `Offset 0: 0x0A | Offset 1: 0x0B | Offset 2: 0x0C | Offset 3: 0x0D`
    * B. `Offset 0: 0x0D | Offset 1: 0x0C | Offset 2: 0x0B | Offset 3: 0x0A`
    * C. `Offset 0: 0x00 | Offset 1: 0x0A | Offset 2: 0x0B | Offset 3: 0x0C`
    * D. `Offset 0: 0x0B | Offset 1: 0x0A | Offset 2: 0x0D | Offset 3: 0x0C`

---

### Kunci Jawaban & Pembahasan

1. **B** — Primitif kecil seperti integer direpresentasikan langsung di stack/register sebagai Smi (Small Integer) via pointer tagging tanpa memerlukan alokasi di Heap.
2. **C** — Minor GC menggunakan variasi Cheney's copying algorithm untuk mengevakuasi objek hidup dari From-Space ke To-Space.
3. **B** — `slice()` mengalokasikan memori baru dan menyalin isinya, sedangkan `subarray()` hanya membuat view baru di atas buffer yang sama (*zero-copy*).
4. **B** — WeakMap memegang referensi lemah pada kuncinya, memungkinkan kunci tersebut dibersihkan oleh GC jika tidak ada referensi kuat lain di luar WeakMap.
5. **A** — V8 menggunakan bit terendah (tag bit) untuk membedakan secara instan antara nilai Smi numerik murni dan pointer alamat memori HeapObject.
6. **B** — Garbage collection bersifat non-deterministik. Tidak ada jaminan GC akan dieksekusi sebelum proses dihentikan, sehingga pembersihan via `FinalizationRegistry` tidak boleh diandalkan untuk data transaksi kritis.
7. **C** — Spesifikasi ECMAScript mewajibkan byte offset untuk TypedArray harus merupakan kelipatan dari ukuran byte elemennya (`Float64` = 8 byte). 4 bukan kelipatan 8, sehingga memicu `RangeError`.
8. **B** — Scope closure menahan seluruh context lexical environment. Jika ada fungsi lain yang masih hidup mereferensikan variabel dalam context tersebut, seluruh objek dalam context tetap hidup di Heap.
9. **A** — *Premature promotion* membanjiri Old Space dengan sampah objek berumur pendek, yang memaksa Major GC melakukan proses Mark-Sweep-Compact yang memakan banyak siklus CPU.
10. **B** — Pada format *Little-Endian*, Byte paling tidak signifikan (*Least Significant Byte* / `0x0D`) ditaruh di alamat memori terendah (offset 0), diikuti byte selanjutnya secara terbalik.

---

# SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Judul Proyek: High-Performance Off-Heap Circular Ring Buffer Telemetry

### Deskripsi Masalah
Dalam aplikasi analitik sensor IoT, Anda menerima ribuan metrik per detik. Anda ditugaskan untuk merancang **Circular Ring Buffer** biner berperforma tinggi yang menampung data telemetri tanpa memicu alokasi objek heap baru setelah tahap inisialisasi awal.

### Spesifikasi Teknis
1. **Memory Allocation:**
   * Alokasikan tepat 1 blok memori menggunakan `ArrayBuffer`.
   * Buffer harus beroperasi secara melingkar (*circular*): ketika kapasitas maksimum tercapai, penulisan baru menimpa data paling usang di index 0 (*FIFO Overwrite Strategy*).
2. **Spesifikasi Data Tiap Record (Fixed-Size: 16 Bytes per record):**
   * Offset 0: `SensorId` (Uint16 - 2 byte)
   * Offset 2: `Flags` (Uint8 - 1 byte, misal: status bit mask)
   * Offset 3: `Reserved/Padding` (Uint8 - 1 byte, penyeimbang alignment)
   * Offset 4: `Timestamp` (Uint32 - 4 byte, Epoch time in seconds)
   * Offset 8: `SensorReading` (Float64 - 8 byte, data metrik desimal)
3. **Fitur yang Wajib Diimplementasikan:**
   * `push(sensorId, flags, timestamp, reading)`: Menulis data metrik baru ke slot aktif tanpa alokasi objek.
   * `readAt(index)`: Mengembalikan data pada slot tertentu tanpa membuat objek baru jika memungkinkan, atau membaca metrik tertentu secara granular (misal: `getReading(index)`).
   * Menangani *endianness* secara konsisten menggunakan `DataView` (*Big-Endian* untuk simulasi Network Protocol).
   * Melakukan benchmarking menggunakan `process.memoryUsage().heapUsed` sebelum dan sesudah 5.000.000 penulisan untuk membuktikan bahwa tidak terjadi kenaikan heap yang signifikan (Heap Churn Delta mendekati 0 byte).

### Kriteria Evaluasi
* Tidak ada pembuatan objek JS Plain (`{}`) di dalam loop pengiriman/penulisan data (`push`).
* Tidak terjadi error *out-of-bounds* atau *unaligned offset access*.
* Pemakaian memori heap V8 stabil (*flat-line memory graph*).
* Struktur kode modular, terdokumentasi, dan lolos uji batas kapasitas (wrap-around ring buffer logic).