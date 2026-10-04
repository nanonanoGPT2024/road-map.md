# BAB 03: Quiz, Challenge, & Knowledge Check
**Memory Lifecycle, Garbage Collection & Low-Level Primitives**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Semantika Alokasi Stack vs. Heap
Jelaskan perbedaan mendasar antara mekanisme alokasi memori pada *Call Stack* dan *Managed Heap* dalam *runtime engine* JavaScript (seperti V8). Mengapa tipe primitif tidak selalu dialokasikan di *Stack*, dan dalam kondisi apa sebuah nilai primitif terpaksa dialokasikan ke dalam *Heap*?

### Soal 1.2: Batasan Fundamental Reference Counting
Algoritma *Reference Counting* memiliki kompleksitas konseptual yang lebih sederhana dibandingkan algoritma pelacak berbasis keterjangkauan (*Tracing Garbage Collection*). Jelaskan kegagalan struktural algoritma *Reference Counting* saat menghadapi *cyclic reference*, dan mengapa *engine* modern secara eksklusif mengadopsi varian dari algoritma *Mark-and-Sweep* untuk *heap* utama.

### Soal 1.3: The Generational Hypothesis & Pembagian Ruang Heap
Jelaskan hipotesis dasar *Weak Generational Hypothesis* dan bagaimana V8 menerjemahkan hipotesis ini ke dalam partisi memori (*Young Generation* vs. *Old Generation*). Mengapa algoritma *Scavenger* (*Cheney's Copying Algorithm*) sangat optimal untuk *Nursery Space*, sedangkan *Mark-Sweep-Compact* dialokasikan untuk *Old Space*?

### Soal 1.4: Arsitektur Biner: ArrayBuffer, TypedArray, dan DataView
Bandingkan karakteristik alokasi dan akses memori antara `ArrayBuffer`, `TypedArray` (misalnya `Uint8Array`), dan `DataView`. Mengapa `DataView` secara inheren lebih lambat daripada `TypedArray`, dan skenario arsitektur spesifik apa yang mewajibkan penggunaan `DataView` alih-alih `TypedArray`?

### Soal 1.5: Siklus Hidup Referensi Lemah (WeakRef & FinalizationRegistry)
Bagaimana representasi objek di dalam `WeakMap` dan `WeakRef` memengaruhi pembentukan *Root Reachability Graph* pada fase *Marking* di Garbage Collector? Mengapa spesifikasi ECMAScript secara eksplisit melarang arsitek sistem bergantung pada `FinalizationRegistry` untuk membersihkan *critical resources* (seperti *file descriptor* atau koneksi basis data)?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Lexical Scope Leakage via Closures
Perhatikan skenario di mana dua fungsi bersarang (*nested functions*) berbagi *Lexical Environment* yang sama. Analisis bagaimana deklarasi variabel berukuran besar yang hanya dibaca oleh satu fungsi dapat menyebabkan *unintended memory retention* pada fungsi kedua yang memiliki masa hidup (*lifetime*) lebih panjang. Bagaimana V8 menangani *Context Allocation* pada level internal untuk skenario ini?

### Soal 2.2: Transisi Hidden Class dan Dampaknya pada Memory Footprint
Bagaimana dereferensi dan mutasi dinamis pada bentuk objek (*object shape/Hidden Class/Map*) dapat meningkatkan konsumsi memori dan memicu deoptimasi pada *Inline Cache* (IC)? Jelaskan trade-off antara penggunaan *Dictionary Mode* (*slow properties*) dan *Fast Properties* (*in-object* vs. *out-of-object properties array*) terhadap jejak memori (*memory footprint*).

### Soal 2.3: Fragmentasi Memori dan Biaya Evacuation/Compaction
Dalam siklus *Major GC* (Full GC), fase *Compaction* (atau *Evacuation*) membutuhkan penulisan ulang pointer di seluruh *heap*. Apa yang memicu *engine* untuk mengeksekusi *Compacting Phase* alih-alih sekadar *Sweep Phase*? Apa konsekuensi teknis terhadap *Stop-The-World* (STW) *pause time*, dan bagaimana *Orinoco Garbage Collector* memitigasi latensi tersebut melalui teknik *Parallel, Concurrent, & Incremental Marking/Compaction*?

### Soal 2.4: Memory Consistency & Atomics pada SharedArrayBuffer
Ketika dua *Web Workers* beroperasi secara paralel pada sebuah instans `SharedArrayBuffer`, operasi pembacaan dan penulisan biasa tidak menjamin *sequential consistency* karena optimasi kompilator (*out-of-order execution*) dan *cache coherence* pada level CPU. Jelaskan bagaimana metode `Atomics.load`, `Atomics.store`, dan `Atomics.compareExchange` menegakkan *memory barriers/fences* untuk mencegah *torn reads/writes* dan *data race*.

### Soal 2.5: Diagnosis Heap Snapshot: Shallow Size vs. Retained Size
Dalam analisis memori menggunakan *Heap Profiler* (Chrome DevTools atau Node.js diagnostic tools), jelaskan perbedaan matematis dan praktis antara *Shallow Size* dan *Retained Size*. Jika Anda menemukan objek dengan *Shallow Size* 32 byte tetapi memiliki *Retained Size* sebesar 250 MB, langkah diagnostik apa yang harus diambil untuk menelusuri *Retaining Path* hingga ke *GC Root*?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Monotonic Memory Leak pada Service Gateway Skala Besar
Sebuah microservice API Gateway berbasis Node.js yang melayani 45.000 RPS mengalami degradasi performa bertahap. Metrik pemantauan menunjukkan pola grafik *sawtooth* yang abnormal: memori *RSS (Resident Set Size)* dan *Heap Used* terus naik secara linier selama 48 jam hingga mendekati ambang batas `--max-old-space-size=4096`, lalu proses mati mendadak dengan status `OOM (Out Of Memory) / JavaScript heap out of memory`. 

Setelah dilakukan profiling awal, ditemukan bahwa insinyur sebelumnya menerapkan modul kustom untuk *distributed request tracing* yang mengikat metadata *request context* ke dalam sebuah *global event bus* (`EventEmitter`) dan menyimpan *callback* otorisasi di dalam closure.

**Pertanyaan Diagnostik:**
1. Rancang metodologi investigasi sistematis untuk mengisolasi kebocoran memori ini di lingkungan *staging* tanpa menghentikan lalu lintas produksi (*core dumps*, *allocation timeline*, vs. *heap snapshot comparisons*).
2. Bagaimana cara membuktikan secara analitis bahwa *listener* `EventEmitter` atau *closure* konteks HTTP request yang tidak terlepas (*dangling listeners*) adalah penyebab penahanan *Old Space* memori?
3. Tuliskan koreksi kode refaktor untuk menjamin pembersihan referensi secara deterministik saat siklus HTTP request berakhir.

---

### Skenario B: Race Condition dan Memory Corruption pada Audio Processing Engine
Sebuah aplikasi web *Digital Audio Workstation* (DAW) memproses sinyal audio *real-time* multi-track dengan latensi sangat rendah (< 5ms) menggunakan arsitektur Web Audio API, `AudioWorkletNode`, dan sekumpulan *Dedicated Web Workers*. Para *workers* bertugas melakukan transformasi Fourier (FFT) secara paralel pada *buffer* audio mentah berukuran 64 MB yang dialokasikan dalam sebuah `SharedArrayBuffer`.

Di bawah beban kerja tinggi, output audio terdistorsi (*glitching* parah), dan unit pengujian mendeteksi adanya data *frame* yang tertimpa secara acak atau terbaca sebagian (*torn reads*). Arsitektur saat ini menggunakan variabel status biasa di dalam buffer untuk menandai apakah worker telah selesai menulis.

**Pertanyaan Diagnostik:**
1. Bedah kegagalan arsitektur konkurensi di atas dari perspektif model memori JavaScript (*weak memory ordering*, ketiadaan sinkronisasi atomik, dan *instruction reordering*).
2. Rancang struktur protokol *Lock-Free Ring Buffer* (Single Producer, Multiple Consumer) berbasis `SharedArrayBuffer` dan primitif `Atomics` (`Atomics.wait`, `Atomics.notify`, `Atomics.waitAsync`). Tentukan layout byte biner untuk *Header*, *Write Pointer*, *Read Pointer*, dan segmen *Payload*.
3. Jelaskan trade-off performa antara pemblokiran thread dengan `Atomics.wait` vs. pendekatan non-blocking berbasis *spin-lock* atau `Atomics.waitAsync` di lingkungan thread utama vs *Dedicated Worker thread*.

---

### Skenario C: Ingestion Telemetri Skala Ekstrim: JSON Heap Objects vs. Flat TypedArray Buffers
Anda bertindak sebagai Principal Engineer pada sistem observabilitas IoT yang menerima 120.000 metrik per detik per node server. Format data masuk awalnya diparsing sebagai *array of dynamic JavaScript objects* (`{ deviceId: string, timestamp: number, metricType: number, value: number }`). 

Namun, arsitektur ini menyebabkan GC *Minor* (Scavenge) berjalan setiap 80ms dan GC *Major* berjalan setiap 3 detik, menghabiskan 38% total CPU time hanya untuk operasi *Garbage Collection overhead*, yang berujung pada *dropped UDP packets*.

**Pertanyaan Diagnostik:**
1. Lakukan dekonstruksi jejak memori: Hitung perkiraan *overhead* memori di V8 untuk merepresentasikan 1.000.000 titik data telemetri jika menggunakan *plain JavaScript objects* vs. merepresentasikannya dalam representasi struktur data *Struct of Arrays* (SoA) atau *Array of Structures* (AoS) menggunakan *Off-Heap/Pre-allocated TypedArray* (`ArrayBuffer`).
2. Rancang arsitektur alokasi memori *zero-allocation / pooling* untuk alur *ingestion* ini. Bagaimana Anda mendesain skema pembacaan biner menggunakan `ArrayBuffer` tetap (*fixed-size circular buffer*) guna mengeliminasi tekanan alokasi pada *Young Generation* V8 hingga mendekati nol GC pause?
3. Evaluasi *trade-off* sistem yang muncul: Apa dampak dari hilangnya fleksibilitas skema dinamis JavaScript, kompleksitas serialisasi/deserialisasi, dan biaya pemeliharaan kode tim terhadap performa throughput *throughput* yang didapat?

---

## 4. Chapter Challenge

### Tantangan Praktis: Implementasi High-Performance Zero-Copy Circular FIFO Buffer
**Konteks Sistem:** Anda ditugaskan membangun lapisan komunikasi data berkecepatan tinggi antar-*thread* (antara *Main Thread* dan *Worker Thread*) untuk pertukaran paket data biner tanpa melalui overhead serialisasi `postMessage` (Structured Clone Algorithm).

#### 1. Problem Statement
Algoritma `postMessage` standar mengeksekusi operasi kloning mendalam (*deep-copy*) atau transfer kepemilikan (*ownership transfer*). Untuk skenario pemrosesan data biner *high-frequency* (misalnya telemetry stream atau video frame processing), transfer kepemilikan bolak-balik menyebabkan alokasi objek baru yang terus-menerus memicu siklus GC. Anda diwajibkan mengimplementasikan *Lock-Free, Concurrent, Zero-Copy Circular FIFO Ring Buffer* di atas satu memori bersama (`SharedArrayBuffer`).

#### 2. Technical Requirements
1. **Memory Layout Architecture:**
   - Alokasikan sebuah `SharedArrayBuffer` tunggal.
   - Buat skema *Memory Header* pada offset byte awal (minimal 32 byte pertama) yang mencakup:
     - `Head Pointer` (32-bit unsigned integer, atomic)
     - `Tail Pointer` (32-bit unsigned integer, atomic)
     - `Buffer Capacity` (32-bit unsigned integer)
     - `State Flags` (Drop count, Shutdown flags, dll.)
   - Sisa memori digunakan sebagai area sirkular untuk *fixed-size slots* atau *variable-length frames* dengan format frame biner terstruktur (`Length + Payload`).
2. **Synchronization Primitives:**
   - Gunakan `Atomics` API untuk seluruh operasi pembaruan indeks pointer (`Atomics.load`, `Atomics.store`, `Atomics.compareExchange`).
   - Implementasikan mekanisme *backpressure*:
     - Jika buffer penuh (*full*), Producer dapat memilih antara *dropping frame* (dengan mencatat metrik atomik) atau *suspending* menggunakan `Atomics.wait` (jika di worker thread) / sinkronisasi asinkron.
     - Jika buffer kosong (*empty*), Consumer harus menunggu data baru secara efisien (`Atomics.wait` / `Atomics.notify`).
3. **API Contracts:**
   - Kelas `SharedRingBufferProducer`:
     - `constructor(sharedBuffer: SharedArrayBuffer)`
     - `write(byteArray: Uint8Array): boolean`
   - Kelas `SharedRingBufferConsumer`:
     - `constructor(sharedBuffer: SharedArrayBuffer)`
     - `read(targetBuffer: Uint8Array): number` (mengembalikan byte terbaca, 0 jika kosong)
     - `pollBlocking(targetBuffer: Uint8Array, timeoutMs: number): number`

#### 3. Constraints
- **Zero GC Allocation in Hot Paths:** Metode `write`, `read`, dan pembacaan indeks tidak boleh membuat alokasi objek heap baru (`new Object`, `new Array`, penutupan closure baru, atau alokasi buffer baru di dalam hot loop). Gunakan buffer yang telah dialokasikan sebelumnya (*pre-allocated target buffer*).
- **Thread Safety:** Harus terbukti aman dieksekusi secara simultan oleh minimal 1 Producer Worker dan 1 Consumer Worker tanpa terjadi *memory corruption* atau *deadlock*.
- **No Node.js-only / Native C++ Bindings:** Harus murni menggunakan primitif standar ECMAScript (dapat dijalankan di Node.js modern atau Browser yang mendukung `cross-origin isolated`).

#### 4. Expected Output & Verification
- Tuliskan kode implementasi kelas secara komprehensif dalam JavaScript/TypeScript.
- Sediakan modul pengujian verifikasi konkurensi:
  - Jalankan skrip uji dengan dua worker: Producer menulis 1.000.000 pesan berurutan (dengan payload urutan integer 0 hingga 999.999), Consumer memvalidasi integritas setiap nilai yang masuk.
  - Skrip pengujian harus secara eksplisit mendeteksi: data korup (*mismatched payload*), *lost updates*, dan *deadlock*.
  - Catat metrik alokasi memori melalui `process.memoryUsage()` (di Node.js) atau `performance.memory` untuk membuktikan bahwa *Heap Used* tetap konstan (*flat line*) selama 1.000.000 iterasi transaksi biner berlangsung.

---

## 5. Knowledge Check & Checklist

Beri tanda centang pada daftar evaluasi mandiri berikut untuk mengukur kesiapan teknis Anda pada level sistem:

### Saya harus memahami:
- [ ] Model arsitektur memori V8 (Call Stack, Young Generation [Nursery & Intermediate], Old Pointer Space, Old Data Space, Large Object Space, Code Space, dan Map Space).
- [ ] Detail siklus GC: *Cheney's Copying Algorithm* pada Scavenger vs. *Mark-Sweep-Compact* pada Major GC.
- [ ] Dampak *Tri-color Marking* (White, Grey, Black) dan bagaimana *Write Barriers* mempertahankan invariant penandaan selama *Concurrent Marking*.
- [ ] Batasan spesifikasi dan siklus penagihan memori pada referensi ephemeron (`WeakMap`), referensi non-ephemeral (`WeakRef`), serta ketiadaan garansi *execution timing* pada `FinalizationRegistry`.
- [ ] Arsitektur representasi biner di JavaScript: Perbedaan *ArrayBuffer Allocation*, segmentasi *TypedArray*, dan penanganan byte order (*Little-Endian vs. Big-Endian*) pada `DataView`.
- [ ] Model konkurensi memori ECMAScript: Hubungan antara `SharedArrayBuffer`, *Atomic Operations*, *Sequential Consistency*, serta mekanisme *Signaling* (`Atomics.wait` dan `Atomics.notify`).

### Saya tidak perlu menghafal:
- [ ] Angka pasti ukuran byte internal dari struktur C++ V8 (seperti ukuran pasti `MapWord` atau C++ class header size yang dapat berubah antar rilis).
- [ ] Konstanta heksadesimal representasi *pointer tagging* internal V8 (misalnya format *Smi* vs. *HeapObject pointer tag bitmask*).
- [ ] Nama-nama spesifik flag compiler internal V8 yang usang atau sub-algoritma eksperimental yang belum distandardisasi.

### Saya harus bisa melakukan:
- [ ] Mengambil, membaca, dan menganalisis *Heap Snapshot* untuk mendeteksi *Retaining Paths*, serta membedakan kebocoran akibat *closure scope*, *dangling event listeners*, atau *unbounded cache*.
- [ ] Menggunakan Node.js diagnostic flags (`--trace-gc`, `--trace-gc-nvp`, `--max-old-space-size`) untuk memvisualisasikan frekuensi, tipe (Minor vs Major), dan durasi STW GC pauses pada server produksi.
- [ ] Menulis algoritma pemrosesan data berbasis *TypedArrays* dan *DataView* dengan memperhatikan *byte alignment* dan struktur biner performa tinggi.
- [ ] Mendesain arsitektur konkurensi berbasis multi-worker menggunakan `SharedArrayBuffer` dan `Atomics` secara aman tanpa memicu *race condition*, *torn reads*, atau *memory leaks*.
- [ ] Menerapkan strategi *Object Pooling* dan *Pre-allocation* untuk mengeliminasi alokasi dinamis di dalam *hot code paths* (loop kritis) guna mencapai stabilitas memori *zero-GC*.