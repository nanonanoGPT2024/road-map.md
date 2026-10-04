# BAB 03: Modern JavaScript Engine & Runtime Mastery
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis Internal V8 Engine Pipeline**: Membedakan fase eksekusi kode dari AST, bytecode generation (Ignition), baseline compilation (Sparkplug), mid-tier optimization (Maglev), hingga peak JIT compilation (TurboFan).
- **Mengeliminasi Deoptimization Bailouts**: Mengidentifikasi dan memitigasi pola kode yang memicu deoptimisasi JIT compiler (TurboFan) menggunakan diagnostik V8 internal flags.
- **Mengoptimalkan Hidden Classes (Shapes) & Inline Caching (IC)**: Merancang struktur data objek monomorfik dan menghindari degradasi ke status polimorfik maupun megamorfik pada jalur eksekusi kritis (*hot path*).
- **Menerapkan Manajemen Memori Tingkat Lanjut & Orinoco GC Tuning**: Mengurangi latensi *stop-the-world* melalui arsitektur *zero-allocation*, pemanfaatan `ArrayBuffer`, typed arrays, dan pencegahan *retained memory leaks* menggunakan `WeakRef` serta `FinalizationRegistry`.
- **Menata Penjadwalan Asinkron Skala Enterprise**: Mencegah *microtask starvation* pada Event Loop runtime browser/Node.js menggunakan teknik interleaving yang deterministik.

---

### 2. Prerequisite
Sebelum mempelajari modul ini, Anda wajib menguasai:
- Konsep dasar JavaScript runtime (Call Stack, Memory Heap, Macrotask vs Microtask).
- Dasar-dasar arsitektur V8 (fase kompilasi dasar dan primitives JavaScript).
- Pengoperasian Chrome DevTools (Performance Panel & Memory Heap Profiler).
- Penggunaan CLI environment (Node.js runtime flags dan V8 built-in debug commands).

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Evolusi Eksekusi Mesin V8 Moderen
V8 modern tidak lagi langsung menerjemahkan kode JavaScript ke machine code. Mesin ini mengadopsi arsitektur multi-tier compilation:

```
[ JavaScript Source Code ]
           │
           ▼
     [ Parser / AST ]
           │
           ▼
    [ Ignition (Bytecode Interpreter) ]  ◄──┐ Feedback Vector
           │                                │
           ├───────────────────────────────►┤
           ▼                                │
    [ Sparkplug (Baseline Compiler) ]       │
           │                                │
           ▼                                │
    [ Maglev (Mid-Tier SSA Compiler) ]      │
           │                                │
           ▼                                │
    [ TurboFan (Optimizing JIT Compiler) ] ──┘
           │
           ├─ (Bailout / Deopt) ──► Kembali ke Ignition
           ▼
   [ Optimized Machine Code ]
```

1. **Parser & Bytecode Generation (Ignition)**: Kode dikonversi menjadi Abstract Syntax Tree (AST), lalu Ignition memproduksi bytecode ringkas. Ignition juga bertugas mengumpulkan *type feedback* ke dalam *Feedback Vector*.
2. **Sparkplug**: Compiler non-optimizing yang mengompilasi langsung dari bytecode ke machine code tanpa analisis tipe global, mempercepat fase *warm-up*.
3. **Maglev**: Engine tier menengah yang menghasilkan Static Single Assignment (SSA) form dengan representasi tipe level menengah untuk mengurangi beban TurboFan.
4. **TurboFan**: Peak optimizing compiler. Menggunakan data spekulatif dari Feedback Vector untuk menghasilkan native machine code berperforma tinggi. Jika asumsi tipe runtime berubah (misal: properti objek bernilai *undefined* yang tiba-tiba menerima *number*), TurboFan melakukan **Deoptimization (Bailout)**, membuang kode mesin yang dioptimasi, dan mengembalikan frame eksekusi ke Ignition.

#### B. Anatomi Objek: Hidden Classes (Shapes) & Descriptor Arrays
Dalam memori, V8 tidak merepresentasikan objek JavaScript sebagai *hash map* tradisional demi efisiensi cache CPU. Sebagai gantinya, V8 memanfaatkan **Hidden Classes** (secara internal disebut *Map* atau *Shape*).

Setiap kali properti ditambahkan ke objek:
- V8 membuat atau mencari *Shape* baru di dalam *Transition Tree*.
- Objek dialokasikan dalam dua model penyimpanan memori:
  1. **In-Object Properties**: Properti disimpan langsung di dalam blok alokasi objek utama. Kecepatannya paling tinggi (O(1)).
  2. **Backing Store (Normal/Dictionary Mode)**: Jika properti ditambah secara dinamis melampaui kapasitas in-object, atau jika perintah `delete` dieksekusi, V8 memindahkan penyimpanan ke *slow dictionary* (hash table biasa), menyebabkan *cache miss* pada CPU.

#### C. State Machine Inline Caching (IC)
Inline Cache adalah mekanisme optimasi di mana V8 menyimpan offset memori properti langsung pada *call site* pemanggilan kode. Terdapat 3 status utama:
- **Monomorphic**: Pemanggilan hanya pernah melihat 1 Shape. Akses properti membutuhkan 1 pointer comparison langsung ke native offset.
- **Polymorphic**: Call site telah melihat 2 hingga 4 Shape berbeda. Membutuhkan linear check (if-else branching) untuk mencocokkan Shape.
- **Megamorphic**: Call site telah melihat $\ge 5$ Shape berbeda. V8 menyerah melakukan inlining dan masuk ke global IC lookup table (pemberhentian optimasi lokal).

#### D. Orinoco Garbage Collection Pipeline
Orinoco adalah engine GC V8 berbasis generasi (*Generational Hypothesis*):
- **Young Generation (Nursery & Intermediate)**: Objek baru dialokasikan di sini. Dikelola oleh **Scavenger** menggunakan semi-space copying GC berbasis Cheney's algorithm, didorong secara paralel (`Parallel Scavenge`).
- **Old Generation**: Objek yang selamat dari 2 siklus Scavenge dipromosikan ke sini. Dikelola oleh **Major GC (Mark-Sweep-Compact)**:
  - *Concurrent Marking*: Background thread menandai objek hidup saat JavaScript utama masih berjalan.
  - *Incremental Steps*: UI thread melakukan porsi marking kecil di sela-sela frame rendering.
  - *Parallel Compacting*: Menghilangkan fragmentasi memori dengan memindahkan memori aktif secara paralel.

---

### 4. Why & What
- **Why**: Frontend skala enterprise modern (misal: Canva, Figma, TradingView, atau Bloomberg Terminal Web) mengeksekusi jutaan operasi per detik. Kode yang tidak *engine-sympathetic* memicu deoptimisasi berantai, lonjakan memori GC (*GC jank*), dan frame drop (< 60/120 FPS).
- **What**: Engine-sympathetic engineering adalah pendekatan rekayasa perangkat lunak di mana abstraksi JavaScript ditulis dengan mempertimbangkan batas-batas arsitektural parser, JIT compiler, alokasi heap, dan struktur internal runtime V8.

---

### 5. How (Workflow Detail)
Alur kerja diagnosis performa engine internal V8:
1. **Tracing Compilation & Deoptimization**:
   Jalankan Node/Browser dengan flags:
   `--trace-opt --trace-deopt --trace-ic`
2. **Identifikasi Hot Path**:
   Temukan fungsi dengan kompilasi berulang atau *deopt bailout reasons* seperti:
   `[deoptimizing: begin ... reason: not a Smi]` atau `[insufficient type feedback for call]`.
3. **Analisis Transisi Shape**:
   Gunakan flag `--allow-natives-syntax` pada environment pengujian untuk menginspeksi map ID dan memverifikasi konsistensi struktur memori objek.
4. **Memory Profiling**:
   Mengambil Heap Snapshot berurutan (T0, T1, T2) untuk menemukan *Detached DOM Nodes* dan *retained closures*.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Pabrik Perakitan Presisi (JIT) vs Gudang Umum (Slow Mode)
- **Monomorphic Code**: Sebuah cetakan pabrik yang hanya menerima satu jenis baut logam spesifik. Mesin perakitan bekerja pada kecepatan 100% tanpa henti.
- **Megamorphic Code**: Jalur perakitan yang tiba-tiba menerima baut kayu, plastik, segitiga, dan heksagonal secara acak. Mesin perakitan harus berhenti, memanggil teknisi ahli untuk mengukur ukuran baut, mencocokkannya ke katalog global, baru melanjutkan perakitan.

#### Diagram Transisi Shape dan Inline Cache
```
[ Instansiasi: let a = {} ]
        │
        ▼
   (Shape S0) 
        │
        │ Properti: a.x = 10
        ▼
   (Shape S1: offset 0 -> x)
        │
        │ Properti: a.y = 20
        ▼
   (Shape S2: offset 0 -> x, offset 1 -> y)

---------------------------------------------------------------------
Inline Cache (IC) States pada Function `read(point)`:
[ Call Site: point.x ]

Monomorphic (Ideal)     Polymorphic (Acceptable)     Megamorphic (Degraded)
┌─────────────────┐     ┌──────────────────────┐     ┌─────────────────────┐
│ If Shape == S2  │     │ If Shape == S2 -> o0 │     │ Global IC Hashmap   │
│   Return [off 0]│     │ Else If Shape == S3  │     │ Lookup (Slow path,  │
│ Else Bailout    │     │   Return [off 0]     │     │ cache miss, higher  │
└─────────────────┘     │ Else Bailout         │     │ instruction cycles) │
                        └──────────────────────┘     └─────────────────────┘
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Mengakibatkan Transisi Shape Tak Terduga vs Terstruktur
```javascript
// BURUK: Mengakibatkan polymorphisme dan hidden class split
function createPointBad(x, y, useZ) {
    const pt = {};
    pt.x = x;
    pt.y = y;
    if (useZ) {
        pt.z = 0; // Shape bertransisi bercabang: S0 -> S1 -> S2 -> S3
    }
    return pt; // Objek yang dihasilkan memiliki Shape berbeda-beda
}

// BAIK: Stabilkan Shape sejak inisialisasi awal
function createPointGood(x, y, useZ) {
    return {
        x: x,
        y: y,
        z: useZ ? 0 : null // Selalu menghasilkan Shape yang sama persis
    };
}
```

#### Practical Example: High-Performance Monomorphic Ring Buffer (Zero-Allocation)
Arsitektur state buffer untuk telemetry trading yang mempertahankan monomorfisme dan zero-GC allocation pada *hot path*:

```typescript
// TelemetryBuffer.ts
export interface TelemetryPayload {
    timestamp: number;
    price: number;
    volume: number;
    sensorId: number;
}

export class MonomorphicRingBuffer {
    private readonly capacity: number;
    // Pemanfaatan Float64Array memastikan flattened memory tanpa object pointer overhead
    private readonly data: Float64Array;
    private cursor: number = 0;
    private size: number = 0;
    private readonly stride: number = 4; // 4 field: timestamp, price, volume, sensorId

    constructor(capacity: number) {
        this.capacity = capacity;
        this.data = new Float64Array(capacity * this.stride);
    }

    /**
     * Hot path: Zero-allocation push operation.
     * Tidak ada instansiasi objek, tidak ada garbage collection pressure.
     */
    public push(timestamp: number, price: number, volume: number, sensorId: number): void {
        const offset = this.cursor * this.stride;
        
        this.data[offset] = timestamp;
        this.data[offset + 1] = price;
        this.data[offset + 2] = volume;
        this.data[offset + 3] = sensorId;

        this.cursor = (this.cursor + 1) % this.capacity;
        if (this.size < this.capacity) {
            this.size++;
        }
    }

    /**
     * Membaca langsung ke reference target tanpa alokasi memori baru.
     * Mencegah instansiasi polimorfik pada target konsumsi.
     */
    public readAt(index: number, outTarget: TelemetryPayload): boolean {
        if (index >= this.size) return false;

        const offset = index * this.stride;
        outTarget.timestamp = this.data[offset];
        outTarget.price = this.data[offset + 1];
        outTarget.volume = this.data[offset + 2];
        outTarget.sensorId = this.data[offset + 3];

        return true;
    }

    public getSize(): number {
        return this.size;
    }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Frame Jank pada Aplikasi Trading Skala Global
- **Konteks**: Dashboard trading real-time memproses pembaruan order book 5.000 events/detik melalui WebSocket.
- **Gejala**: Tampilan membeku (UI freeze) setiap 4–6 detik selama ~120 milidetik, menyebabkan frame rate anjlok dari 60 FPS ke 12 FPS (*jank* berat).
- **Hasil Profiling**:
  - Chrome DevTools Memory Timeline memperlihatkan grafik "sawtooth" yang sangat agresif.
  - Orinoco GC menghabiskan 18% dari total execution time CPU hanya untuk fase `Scavenge` dan `MinorGC`.
  - Inspeksi V8 (`--trace-deopt`) menemukan bahwa fungsi `aggregateTick()` mengalami deoptimisasi permanen akibat mutasi objek JSON dari WebSocket (Shape berubah secara acak karena API kadang mengirimkan properti `spread` dan kadang menghilangkannya).
- **Solusi Arsitektural**:
  1. **Schema Normalization**: Membuat parser biner berbasis `ArrayBuffer` dan `DataView` yang membuang deserialisasi objek JSON mentah.
  2. **Shape Lockdown**: Membekukan konstruktor model state dengan inisialisasi properti berurutan dan strict typed defaults (tidak pernah menggunakan `delete` dan tidak membiarkan nilai `undefined`).
  3. **Shared Worker Offloading**: Parsing data dialihkan ke Web Worker, kemudian data ditransfer ke main thread menggunakan `SharedArrayBuffer` dan `Atomics` untuk kontrol akses.
- **Hasil**:
  - Waktu GC turun dari 18% menjadi < 0.8%.
  - Frame rate stabil di 60 FPS terkunci (99th percentile frame time $\le 16.6\text{ ms}$).

---

### 9. Trade-offs

| Dimensi | Pendekatan Engine-Sympathetic (Typed/Shape Locked) | Pendekatan Konvensional Idiomatik JS |
| :--- | :--- | :--- |
| **Kinerja CPU** | Sangat Maksimal. TurboFan mampu mempertahankan inlined native assembly. | Fluktuatif. Rawan bailout, polymorphic lookup, dan overhead interpreter. |
| **Beban Memori (GC)** | Sangat Rendah. Mengeliminasi *short-lived allocations*. | Tinggi. Jutaan objek sementara memicu Minor/Major GC berulang. |
| **Keterbacaan Kode** | Rendah - Menengah. Banyak boilerplate inisialisasi dan manipulasi flat buffers. | Tinggi. Sintaks sangat ekspresif, ringkas, dan deklaratif (`map`, `filter`, destructuring). |
| **Waktu Development** | Lebih lambat; developer harus memahami batas toleransi runtime & engine. | Cepat; mengandalkan abstraksi level tinggi tanpa memikirkan layout memori. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Mutasi Objek Menggunakan Operator `delete`
- **Kesalahan**: Menghapus field `delete user.tempToken;`.
- **Dampak Engine**: Mengubah Shape objek secara paksa dari *Fast Mode* menjadi *Dictionary/Slow Mode*.
- **Solusi**: Atur field ke `null` atau `undefined`, atau petakan ke `Map` / instansiasi objek representasi baru.

#### 2. Penambahan Properti Secara Acak (Out-of-Order Initialization)
```javascript
// MEMICU DUA SHAPE BERBEDA
function initA() {
    const o = {};
    o.x = 1;
    o.y = 2; // Shape A -> B -> C
    return o;
}
function initB() {
    const o = {};
    o.y = 2;
    o.x = 1; // Shape A -> D -> E (Shape C != Shape E!)
    return o;
}
```
- **Solusi**: Selalu deklarasikan semua properti dalam urutan yang konsisten melalui konstruktor class.

#### 3. Microtask Starvation
- **Kesalahan**: Rekursi `Promise.resolve().then(...)` atau `queueMicrotask()` tanpa batasan yield.
- **Dampak**: Macrotask dan fase UI Rendering (`requestAnimationFrame`, Paint) diblokir secara total oleh microtask queue yang tak kunjung kosong.
- **Troubleshooting**: Pecah pemrosesan menggunakan `scheduler.yield()` (jika didukung) atau batasi pemrosesan microtask berdasarkan kuantum waktu ($\le 8\text{ ms}$) lalu kembalikan kontrol menggunakan `MessageChannel` / `setTimeout`.

---

### 11. Best Practices (Production Checklist)

- [ ] **Monomorphic Arrays**: Hindari array campuran tipe data (`[1, "dua", true]`). Gunakan homogen array (`HOLEY_SMI_ELEMENTS` vs `PACKED_SMI_ELEMENTS`). Hindari `holes` (misal: `new Array(3)`).
- [ ] **Constructor Discipline**: Selalu inisialisasi semua properti kelas di dalam `constructor`. Jangan pernah menambahkan properti baru di luar constructor.
- [ ] **Zero `delete` Usage**: Singkirkan seluruh pemanggilan operator `delete` pada objek intensif komputasi.
- [ ] **Stabilisasi Argument Function**: Jangan mengubah tipe parameter yang dilewatkan ke fungsi *hot path*.
- [ ] **WeakRef & FinalizationRegistry**: Gunakan untuk caching referensi berat tanpa menahan objek dari siklus Garbage Collection:
  ```typescript
  const cache = new Map<string, WeakRef<LargeDataNode>>();
  ```
- [ ] **Interleaved Scheduling**: Pastikan proses komputasi panjang mengembalikan kontrol eksekusi ke browser rendering loop setidaknya setiap 16ms.

---

### 12. Hands-on Practice
Simpan seluruh artefak praktikum ini di direktori: `hands-on/m02/`

#### Langkah 1: Eksperimen V8 Hidden Class Profiling
Buat file `hands-on/m02/shape_transition.js`:

```javascript
// Jalankan dengan: node --allow-natives-syntax hands-on/m02/shape_transition.js

function Point(x, y) {
    this.x = x;
    this.y = y;
}

const p1 = new Point(1, 2);
const p2 = new Point(3, 4);

console.log("Shape comparison 1:");
// %HaveSameMap memvalidasi apakah dua objek berbagi Hidden Class (Map) yang sama
console.log(%HaveSameMap(p1, p2)); // Expected: true

// Modifikasi dinamis:
p2.z = 5;

console.log("Shape comparison setelah p2 dimutasi secara dinamis:");
console.log(%HaveSameMap(p1, p2)); // Expected: false

// Memaksa objek p1 ke Dictionary Mode (Slow Mode)
delete p1.x;
console.log("Apakah p1 memiliki fast properties?");
console.log(%HasFastProperties(p1)); // Expected: false
```

#### Langkah 2: Memverifikasi Deoptimisasi TurboFan
Buat file `hands-on/m02/deopt_test.js`:

```javascript
// Jalankan dengan: node --trace-opt --trace-deopt hands-on/m02/deopt_test.js

function calculateArea(rect) {
    return rect.w * rect.h;
}

// 1. Warm-up JIT compiler dengan monomorphic shape
const r1 = { w: 10, h: 20 };
for (let i = 0; i < 100000; i++) {
    calculateArea(r1);
}

// 2. Kirim objek dengan tipe berbeda (string representation)
// Hal ini memaksa TurboFan melakukan deoptimisasi (Bailout)
const corruptedRect = { w: "10", h: 20 };
calculateArea(corruptedRect);
```

#### Langkah 3: Eksekusi dan Amati Terminal
Perhatikan output diagnostik V8:
```bash
node --trace-deopt hands-on/m02/deopt_test.js
```
Analisis baris output yang menunjukkan deoptimisasi (pencarian string `deoptimizing: begin ... reason:`).

---

### 13. Exercise

#### Level Easy
Diberikan fungsi berikut yang mengalami degradasi performa:
```javascript
function makeConfig(env) {
    const config = { env };
    if (env === 'prod') {
        config.ssl = true;
    }
    return config;
}
```
**Tugas**: Tulis ulang fungsi tersebut di `hands-on/m02/ex_easy.js` sehingga menghasilkan objek yang selalu memiliki Shape yang konsisten tanpa percabangan Shape internal.

#### Level Medium
Buat modul pooling memori sederhana `hands-on/m02/ex_medium.js` bernama `ObjectPool<T>` yang mengimplementasikan metode `acquire()` dan `release(obj: T)`.
- Syarat: Pool harus mengalokasikan memori di awal (pre-allocation) sebanyak $N$ instances dan tidak boleh memicu alokasi memori baru (`new`) selama fase transaksi runtime berjalan.

#### Level Hard
Buat script simulasi deteksi microtask starvation di `hands-on/m02/ex_hard.js`:
- Jalankan sebuah interval yang memonitor kelancaran runtime setiap 10ms.
- Jalankan microtask generator masif.
- Implementasikan algoritma adaptif *cooperative yielding* menggunakan `MessageChannel` untuk memotong eksekusi microtask ketika durasi pengerjaan melebihi ambang batas $8\text{ ms}$, sehingga interval monitoring tidak mengalami starvation.

---

### 14. Challenge
**Studi Kasus**: Arsitektur High-Throughput Frontend Cache Engine.
Anda diminta merancang subsistem state cache di frontend untuk menangani 100.000 mutasi data tabular per detik tanpa menyebabkan UI frame drop (>16.6ms).

**Ketentuan**:
1. Gunakan `ArrayBuffer` dan typed array layout untuk menampung entitas data tabular.
2. Implementasikan struktur referensi menggunakan `WeakMap` untuk mengaitkan metadata tanpa memblokir GC.
3. Seluruh function di hot path pembaruan state harus terbukti monomorfik melalui pengujian native syntax flag V8 (`%HaveSameMap`).
4. Dilarang menggunakan method fungsional bawaan array (`forEach`, `map`, `reduce`, `filter`) pada hot path karena alokasi closure function baru.
5. Buat laporan benchmark perbandingan throughput ops/sec dan footprint alokasi heap dibandingkan dengan implementasi array of objects konvensional.

Simpan solusi arsitektur ini pada `hands-on/m02/challenge_engine.ts`.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. Apa fungsi utama Ignition pada V8 Engine?
2. Apa yang dimaksud dengan *Hidden Class* (Shape) pada V8 dan mengapa V8 membutuhkannya?
3. Sebutkan status-status yang terdapat pada Inline Caching (IC)!
4. Mengapa operasi `delete obj.property` sangat tidak disarankan pada kode JavaScript yang menuntut performa tinggi?
5. Di generasi GC manakah objek yang baru diinisialisasi pertama kali ditempatkan?

#### B. Pertanyaan Intermediate
6. Jelaskan apa yang terjadi secara internal saat TurboFan memicu status *Deoptimization (Bailout)*!
7. Apa perbedaan mendasar antara elemen array tipe `PACKED_SMI_ELEMENTS` dan `HOLEY_ELEMENTS` dalam pemrosesan memori V8?
8. Mengapa `queueMicrotask` dapat menyebabkan aplikasi browser hang total, sedangkan serangkaian `setTimeout(fn, 0)` tidak menyebabkan browser hang dengan intensitas yang sama?
9. Bagaimana mekanisme *Concurrent Marking* pada Orinoco GC mengurangi latensi UI thread?
10. Kapan V8 memindahkan penyimpanan properti dari *In-Object Properties* ke *Slow Dictionary Mode*?

#### C. Skenario Kasus Produksi
11. **Skenario 1**: Sebuah platform SaaS pelaporan keuangan mendadak mengalami keluhan browser crash (Out of Memory) ketika pengguna membuka tabel data 50.000 baris. Profiling heap menunjukkan ribuan *Detached HTMLTableRowElements* tertahan. Apa penyebab arsitektural yang paling mungkin di balik retained reference ini, dan bagaimana strategi mengatasinya?
12. **Skenario 2**: Anda menjalankan profiler pada hot-path function penghitungan total keranjang belanja. Anda menemukan bahwa fungsi tersebut turun status dari JIT TurboFan ke Ignition dengan catatan: `reason: Insufficient type feedback for binary operation`. Apa arti peringatan ini dan bagaimana restrukturisasi kodenya?
13. **Skenario 3**: Sebuah library visualisasi data realtime menghasilkan lonjakan GC Scavenge setiap kali kursor digerakkan di atas canvas chart. Setelah diinspeksi, event handler melakukan destructuring objek mouse event `{ x, y } = event` dan mengalokasikan object koordinat baru pada setiap pixel delta. Jelaskan arsitektur refactoring untuk mencapai *zero-allocation tracking*!

---

### 16. Summary
1. **Engine Pipeline Understanding**: Arsitektur V8 modern mengeksekusi kode melalui transisi berjenjang (Ignition -> Sparkplug -> Maglev -> TurboFan). TurboFan melakukan optimasi spekulatif berdasarkan feedback tipe. Pelanggaran terhadap asumsi tipe memicu Deoptimization Bailout yang mahal.
2. **Hidden Classes & IC**: Menjaga konsistensi Shape objek dengan menginisialisasi properti secara seragam adalah fondasi tercapainya status Monomorphic Inline Caching. Status monomorfik menjamin pembacaan properti objek pada kecepatan setara native compiled code.
3. **Generational Garbage Collection**: Melalui Orinoco, V8 membagi siklus alokasi memori ke Scavenger (Young Gen) dan Mark-Sweep-Compact (Old Gen). Hindari memori churn (alokasi dan dealloc instan secara massal) agar terhindar dari *GC jank*.
4. **Runtime-Sympathetic Engineering**: Frontend performa tinggi pada level enterprise dicapai bukan dengan trik mikro sintaksis, melainkan perancangan struktur data yang stabil, alokasi memori terkendali, dan penjadwalan eksekusi yang ramah terhadap siklus Event Loop browser.