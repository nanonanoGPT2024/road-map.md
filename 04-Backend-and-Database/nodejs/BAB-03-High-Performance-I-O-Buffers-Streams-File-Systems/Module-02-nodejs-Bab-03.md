# BAB 03: High-Performance I/O, Buffers, Streams & File Systems
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Mendiagnosis dan mengoptimalkan konsumsi memori V8 Heap dan External Memory (*C++ heap/ArrayBuffer*) melalui pemahaman mendalam tentang **Slab Allocator** pada Buffer Node.js.
- Mengimplementasikan arsitektur stream kustom (`Readable`, `Writable`, `Transform`, `Duplex`) tingkat lanjut yang tahan terhadap kegagalan, mematuhi kontrak **Backpressure** secara deterministik, serta mendukung integrasi `AbortSignal`.
- Menerapkan manipulasi File System berkinerja tinggi menggunakan teknik *zero-copy semantics*, mutasi berkas atomik (*atomic file operations*), penanganan *File Descriptor* tingkat rendah, dan mitigasi *threadpool starvation* pada Libuv.
- Membangun pipeline pemrosesan data biner terenkripsi dan terkompresi skala enterprise dengan jejak memori (*Resident Set Size / RSS*) konstan di bawah beban konkurensi tinggi.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda harus memahami:
- Arsitektur dasar Event Loop Node.js (Phases: Timers, Pending Callbacks, Poll, Check, Close) dan Libuv.
- Konsep dasar JavaScript TypedArray (`ArrayBuffer`, `Uint8Array`, `DataView`).
- Dasar-dasar I/O asinkron (`fs/promises`, EventEmitters).
- Prinsip dasar transmisi data biner (Endianness, Encoding UTF-8 vs Hex vs Base64).

---

### 3. Concept & Internal Architecture

#### 3.1 V8 Heap vs. Node.js Buffer & Slab Allocation Engine

Di dalam runtime Node.js, `Buffer` bukan sekadar array JavaScript biasa. `Buffer` adalah implementasi dari `Uint8Array` yang memori dasarnya dialokasikan di luar V8 JavaScript Heap (dikenal sebagai *Off-Heap / External Memory*).

```
+-------------------------------------------------------------------------+
|                              Node.js Process                            |
|                                                                         |
|  +---------------------------+        +------------------------------+  |
|  |       V8 Engine Heap      |        |        C++ / Libuv Heap      |  |
|  |                           |        |       (External Memory)      |  |
|  |  +---------------------+  |        |  +------------------------+  |  |
|  |  | JS Buffer Wrapper   |--+--Ref---+->| Raw Binary Data        |  |  |
|  |  | (Uint8Array Object) |  |        |  | (malloc/posix_memalign)|  |  |
|  |  +---------------------+  |        |  +------------------------+  |  |
|  +---------------------------+        +------------------------------+  |
+-------------------------------------------------------------------------+
```

Untuk menghindari *overhead* pemanggilan alokasi memori sistem operasi (`malloc`) secara berulang untuk alokasi data berukuran kecil, Node.js menggunakan teknik **Slab Allocation**.

- Ukuran default satu unit slab (`Buffer.poolSize`) adalah **8192 byte (8 KiB)**.
- Setiap kali Anda memanggil `Buffer.allocUnsafe(size)` atau operasi I/O membaca data di mana `size < (Buffer.poolSize >>> 1)` (kurang dari 4 KiB), Node.js tidak meminta memori baru ke OS, melainkan mengambil irisan (*slice*) dari satu slab `ArrayBuffer` berukuran 8 KiB yang telah dialokasikan sebelumnya.
- **Bahaya Retensi Memori:** Jika sebuah buffer kecil (misalnya 16 byte) dipotong dari slab 8 KiB dan referensi ke buffer 16 byte tersebut tetap hidup di dalam memori, maka **seluruh slab 8 KiB tidak dapat dibersihkan oleh Garbage Collector (GC)**.

```
Slab (ArrayBuffer 8192 bytes)
[ [Allocated: 16B] | [Allocated: 32B] | [Unallocated: 8144B] ... ]
       ^
       |-- Jika pointer ini dipertahankan, seluruh slab 8KB tertahan di RAM!
```

#### 3.2 Alur Transmisi Stream & Mekanisme Backpressure

Stream di Node.js adalah implementasi konkret dari pola desain *Publisher-Subscriber* yang dikombinasikan dengan *Finite State Machine (FSM)*. Inti dari stabilitas stream terletak pada **Backpressure**.

```
[ READABLE STREAM ]                                        [ WRITABLE STREAM ]
+------------------+                                      +------------------+
| Buffer Internal  |                                      | Buffer Internal  |
| (highWaterMark)  |                                      | (highWaterMark)  |
| [Chunk][Chunk]   |                                      | [Chunk][Chunk]   |
+--------+---------+                                      +--------+---------+
         |                                                         ^
         | .push(chunk)                                            | .write(chunk)
         v                                                         |
   +-----------+         return false (Buffer Penuh)         +------------+
   | consumer  | ==========================================> |  producer  |
   | (Reader)  | <========================================== |  (Writer)  |
   +-----------+             Emit 'drain' event              +------------+
```

1. **Readable State:** Membaca data dari sumber I/O ke dalam antrean internal (`_readableState.buffer`). Ketika ukuran buffer mencapai `highWaterMark`, `readable.push(chunk)` akan mengembalikan nilai `false`. Stream berhenti membaca data dari kernel sampai data diambil oleh consumer.
2. **Writable State:** Ketika data ditulis melalui `writable.write(chunk)`, jika buffer internal (`_writableState.getBuffer()`) melampaui `highWaterMark`, method `.write()` mengembalikan `false`.
3. **Koordinasi:** Saat reader mendeteksi nilai `false` dari method write target, reader **harus** menghentikan pembacaan (`readable.pause()`). Ketika buffer writable berhasil dikosongkan dan dikirim ke target I/O dasar, writable memancarkan event `'drain'`, yang menjadi sinyal bagi reader untuk melanjutkan (`readable.resume()`).
4. **Transform Pipeline:** Transform stream bertindak sebagai Duplex di mana bagian writable secara internal terhubung ke bagian readable melalui method `_transform(chunk, encoding, callback)`.

#### 3.3 Libuv Threadpool vs. Direct Asynchronous I/O

Penting untuk dicatat bahwa operasi File System (`fs`) pada Node.js **tidak memiliki asynchronous non-blocking API native** di level kernel sistem operasi (POSIX AIO memiliki banyak batasan pada Linux; `io_uring` baru diadopsi secara bertahap). 

Oleh karena itu:
- Semua fungsi `fs.*` asinkron (misalnya `fs.promises.readFile`) didelegasikan ke **Libuv Threadpool** (`UV_THREADPOOL_SIZE`, default: 4 threads).
- Berbeda dengan I/O Jaringan (Socket TCP/UDP) yang memanfaatkan mekanisme *readiness notifications* berbasis kernel non-blocking murni (`epoll` di Linux, `kqueue` di macOS, `IOCP` di Windows) tanpa mengonsumsi threadpool Libuv.
- **Saturasi Threadpool:** Membaca atau menulis ratusan file secara paralel dapat memblokir threadpool, menunda operasi asinkron lain seperti resolusi DNS (`dns.lookup`) dan kriptografi (`crypto.pbkdf2`, `crypto.randomBytes`).

---

### 4. Why & What

| Komponen | Mengapa Diperlukan? | Apa Masalah yang Diselesaikan? |
| :--- | :--- | :--- |
| **Slab Allocation (`Buffer`)** | Alokasi memori OS berskala nanodetik via syscall `brk`/`mmap` memicu *system overhead* yang masif jika dipanggil jutaan kali per detik. | Mengurangi syscall alokasi memori dengan mempartisi blok 8KB di userspace secara pre-allocated. |
| **Backpressure Handling** | Produsen data (misal: disk SSD membaca 500 MB/s) jauh lebih cepat daripada konsumen data (misal: koneksi jaringan klien mengunggah 1 MB/s). | Menghindari *Out-Of-Memory (OOM)* crash akibat penumpukan data tak terbatas di memori internal Node.js process. |
| **Pipeline Composition** | Pemrosesan streaming modular (baca $\to$ parse $\to$ validasi $\to$ enkripsi $\to$ kompresi $\to$ tulis) rawan mengalami *resource leak* jika ditangani via event listener manual (`.on('data')`). | Otomatisasi pembersihan resource (menutup File Descriptor), propagasi error, dan manajemen event `drain`/`pause`/`resume`. |
| **File Descriptors (`fs.open`)** | Membuka dan menutup file secara berulang (`fs.readFile`) membuang siklus CPU pada kernel syscall `open(2)` dan `close(2)`. | Mempertahankan referensi integer (*handle*) langsung ke tabel berkas kernel untuk operasi baca/tulis biner acak secara efisien. |

---

### 5. How (Workflow detail)

Alur transmisi data streaming industri menggunakan `stream.pipeline` terenkapsulasi:

```
[Source: Incoming HTTP Body / Large File]
                   │
                   ▼ (1)
         [Readable Stream Engine]
                   │
                   ├───────► Ukuran internal buffer >= highWaterMark?
                   │         ├─ YES ──► Stop OS read syscall (pause)
                   │         └─ NO  ──► Continue fetching from Kernel
                   ▼ (2)
         [Custom Transform Stream]
                   │  - Parsing chunk secara deterministic
                   │  - Kalkulasi Rolling Hash / HMAC
                   │  - Transformasi byte array
                   ▼ (3)
         [Destination: Encrypted File / Outgoing Socket]
                   │
                   ├───────► Target write buffer >= highWaterMark?
                   │         ├─ YES ──► Return false, emit 'drain' nantinya
                   │         └─ NO  ──► Flush langsung ke Kernel Socket/Disk
                   ▼ (4)
[Lifecycle Finalizer: Auto Close All Descriptors on Error or Success]
```

1. **Inisialisasi Channel:** Pipeline memvalidasi integritas stream dan mengikat listener lifecycle (`error`, `close`, `finish`, `end`).
2. **Chunk Propagation:** Data biner dialokasikan melalui Buffer slab, disalurkan ke method `_transform()`. Transformasi harus bersifat non-mutatif terhadap buffer input jika buffer tersebut masih terikat pada memori slab bersama.
3. **Flow Control Synchronization:** Jika downstream lambat, upstream dipaksa menghentikan `read(2)`. Saat downstream selesai melakukan flush ke kernel buffer, event `drain` dipancarkan, mengizinkan upstream memanggil `read(2)` kembali.
4. **Graceful Teardown:** Jika terjadi unhandled error di tengah stream, pipeline memanggil `.destroy(err)` ke semua stream yang terdaftar, memastikan File Descriptor dilepas kembali ke OS.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Pengolahan Air dan Waduk Penampungan

Bayangkan sistem transfer data seperti jaringan pipa air:
- **Readable Stream** adalah **Mata Air Pegunungan** dengan keran kontrol.
- **Writable Stream** adalah **Pabrik Pembotolan Air**.
- **Buffer / highWaterMark** adalah **Tandon Air Darurat (Waduk)**.
- **Backpressure** adalah **Pelampung Otomatis**.

```
+------------------+         +------------------+         +------------------+
|     MATA AIR     |         |      TANDON      |         |     PABRIK       |
| (Readable Stream)|         | (Buffer Storage) |         | (Writable Stream)|
|                  |         |                  |         |                  |
|  [Pipa Aliran]===|========>|  ~~~~ Level ~~~~ |========>| Kapasitas:       |
|  Buka/Tutup Otomatis       |  [highWaterMark] |         | 100 Liter/detik  |
+------------------+         +--------+---------+         +------------------+
         ^                            |
         |                            | Sensor Ketinggian Air
         +==== Sinyal "STOP/RESUME" ==+ (Backpressure)
```

Jika Pabrik hanya bisa memproses 100 liter/detik tetapi Mata Air memancarkan 500 liter/detik, air akan mengisi Tandon. 
- **Tanpa Backpressure:** Tandon akan meluap, membanjiri ruang mesin (**OOM Error: JavaScript heap out of memory**).
- **Dengan Backpressure:** Saat air mencapai garis batas (`highWaterMark`), pelampung mengirim sinyal mekanik untuk menutup keran Mata Air. Ketika air di tandon surut, keran dibuka kembali.

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Bahaya Alokasi Slab Unsafe vs Safe Copy

File: `slab-leak-demo.mjs`

```javascript
import { Buffer } from 'node:buffer';

// Simulasi retensi memori akibat alokasi slab
function leakyBufferAllocation() {
  // Mengalokasikan 100 chunk kecil (masing-masing 16 byte)
  const retainedChunks = [];
  
  for (let i = 0; i < 100; i++) {
    // Buffer.allocUnsafe mengalokasikan dari Slab berukuran 8KB
    const smallChunk = Buffer.allocUnsafe(16);
    
    // Mengisi dengan payload dummy
    smallChunk.fill(0xff);
    
    // KESALAHAN: Menyimpan irisan ini secara langsung
    // Dampak: 100 slab terpisah (total 800 KB) tertahan di memori 
    // hanya untuk menampung data riil berukuran 1600 Byte (1.6 KB)!
    retainedChunks.push(smallChunk);
  }
  return retainedChunks;
}

function safeBufferAllocation() {
  const retainedChunks = [];
  
  for (let i = 0; i < 100; i++) {
    const smallChunk = Buffer.allocUnsafe(16);
    smallChunk.fill(0xaa);
    
    // BENAR: Salin data keluar dari Slab bersama jika chunk akan disimpan lama
    const decoupledBuffer = Buffer.alloc(16);
    smallChunk.copy(decoupledBuffer);
    
    retainedChunks.push(decoupledBuffer);
  }
  return retainedChunks;
}

const leaky = leakyBufferAllocation();
const safe = safeBufferAllocation();
console.log(`Leaky chunks count: ${leaky.length}, Safe chunks count: ${safe.length}`);
```

#### 7.2 Practical Example: Enterprise-Grade Chunked Binary Encryptor & Hash Checksum Transform Stream

File: `secure-stream-processor.mjs`

```javascript
import { Transform, pipeline } from 'node:stream';
import { createReadStream, createWriteStream } from 'node:fs';
import { createCipheriv, randomBytes, createHash } from 'node:crypto';
import { promisify } from 'node:util';
import { performance } from 'node:perf_hooks';

const pipelineAsync = promisify(pipeline);

/**
 * Transform Stream untuk menghitung checksum SHA-256 secara inline
 * tanpa menghentikan atau menduplikasi aliran buffer di memori.
 */
class ChecksumCalculatorStream extends Transform {
  constructor(options = {}) {
    super(options);
    this.hasher = createHash('sha256');
    this.totalBytesProcessed = 0;
  }

  _transform(chunk, encoding, callback) {
    try {
      this.hasher.update(chunk);
      this.totalBytesProcessed += chunk.length;
      // Meneruskan chunk tanpa modifikasi ke stream berikutnya (PassThrough behavior)
      this.push(chunk);
      callback();
    } catch (err) {
      callback(err);
    }
  }

  _flush(callback) {
    this.digest = this.hasher.digest('hex');
    callback();
  }
}

/**
 * Transform Stream untuk enkripsi AES-256-GCM berbasis frame biner
 */
class AesGcmEncryptorStream extends Transform {
  constructor(key, iv, options = {}) {
    super(options);
    if (key.length !== 32) throw new Error('Key harus berukuran 256 bit (32 bytes)');
    if (iv.length !== 12) throw new Error('IV untuk GCM harus 96 bit (12 bytes)');
    
    this.cipher = createCipheriv('aes-256-gcm', key, iv);
    this.iv = iv;
    this.ivEmitted = false;
  }

  _transform(chunk, encoding, callback) {
    try {
      // Sisipkan IV di awal stream (hanya sekali) sebagai metadata pembaca
      if (!this.ivEmitted) {
        this.push(this.iv);
        this.ivEmitted = true;
      }
      
      const encrypted = this.cipher.update(chunk);
      if (encrypted.length > 0) {
        this.push(encrypted);
      }
      callback();
    } catch (err) {
      callback(err);
    }
  }

  _flush(callback) {
    try {
      this.cipher.final();
      const authTag = this.cipher.getAuthTag(); // GCM Auth Tag (16 bytes)
      this.push(authTag); // Append auth tag di akhir berkas
      callback();
    } catch (err) {
      callback(err);
    }
  }
}

// Eksekusi Pipeline Produksi
async function runSecurePipeline(sourcePath, destPath) {
  const startTime = performance.now();
  
  // Konfigurasi kunci enkripsi
  const secretKey = randomBytes(32);
  const initializationVector = randomBytes(12);

  // Instansiasi Streams dengan highWaterMark terkalibrasi (64 KiB)
  const fileReader = createReadStream(sourcePath, { highWaterMark: 64 * 1024 });
  const checksumStream = new ChecksumCalculatorStream({ highWaterMark: 64 * 1024 });
  const encryptorStream = new AesGcmEncryptorStream(secretKey, initializationVector, { 
    highWaterMark: 64 * 1024 
  });
  const fileWriter = createWriteStream(destPath, { highWaterMark: 64 * 1024 });

  console.log(`[PIPELINE] Memulai enkripsi aman: ${sourcePath} -> ${destPath}`);

  try {
    await pipelineAsync(
      fileReader,
      checksumStream,
      encryptorStream,
      fileWriter
    );

    const duration = (performance.now() - startTime).toFixed(2);
    console.log(`[PIPELINE] Selesai dalam ${duration}ms`);
    console.log(`[PIPELINE] Total Data: ${checksumStream.totalBytesProcessed} bytes`);
    console.log(`[PIPELINE] SHA256 Asli: ${checksumStream.digest}`);
  } catch (error) {
    console.error('[PIPELINE-ERROR] Kegagalan transmisi stream:', error);
    throw error;
  }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Skenario:
Sistem Core Banking FinTech menerima *Audit Transaction Log* harian terkompresi berukuran **15 Gigabyte** per berkas. Sistem wajib mengurai data baris-demi-baris (JSON newline-delimited), menyaring transaksi yang mencurigakan, mengenkripsi ulang payload berstatus "MATCHED", dan menyimpannya ke volume penyimpanan permanen. 

#### Tantangan:
- Server container (Kubernetes Pod) dibatasi secara ketat dengan **Resource Limit RAM: 256 MB**.
- Penggunaan `fs.readFile` atau mengabaikan backpressure akan membunuh container secara instan melalui sistem Linux Out-Of-Memory Killer (`Killed: 137`).

#### Solusi Arsitektural:
1. Membaca sumber stream melalui *chunked framing* tanpa deserialisasi seluruh berkas sekaligus.
2. Membangun implementasi kustom `Transform` stream yang mengelola buffer parsial (*line-splitting algorithm*) dengan alokasi konstan.
3. Menggunakan backpressure terintegrasi untuk memperlambat pembacaan disk ketika worker enkripsi mencapai saturasi pemrosesan.

```
[15 GB File on Disk]
       │ (Read Chunks: 64KB)
       ▼
[Libuv Threadpool]
       │
       ▼
[StreamLineSplitter (Transform)] <--- Mempertahankan Buffer Parsial (Maksimal 64KB)
       │ (Push individual lines)
       ▼
[ComplianceAnalyzer (Transform)] <--- Analisis RegEx & Sanitasi
       │
       ▼
[Disk Writer (Writable)]         <--- RAM Tetap Konstan di ~35MB RSS
```

Implementasi `StreamLineSplitter`:

```javascript
import { Transform } from 'node:stream';

export class ChunkedLineSplitter extends Transform {
  constructor(options = {}) {
    super({ ...options, readableObjectMode: true });
    this.bufferRemainder = null;
  }

  _transform(chunk, encoding, callback) {
    try {
      let data = chunk;
      
      // Jika ada sisa byte dari chunk sebelumnya, gabungkan
      if (this.bufferRemainder) {
        data = Buffer.concat([this.bufferRemainder, chunk]);
        this.bufferRemainder = null;
      }

      let startIndex = 0;
      let newlineIndex = 0;

      // Scan pemisah baris \n (ASCII 0x0A)
      while ((newlineIndex = data.indexOf(0x0A, startIndex)) !== -1) {
        const lineBuffer = data.subarray(startIndex, newlineIndex);
        
        // Push baris sebagai Uint8Array terisolasi ke downstream
        this.push(lineBuffer);
        
        startIndex = newlineIndex + 1;
      }

      // Simpan byte tersisa yang belum menemukan newline penutup
      if (startIndex < data.length) {
        this.bufferRemainder = Buffer.from(data.subarray(startIndex));
      }

      callback();
    } catch (err) {
      callback(err);
    }
  }

  _flush(callback) {
    if (this.bufferRemainder && this.bufferRemainder.length > 0) {
      this.push(this.bufferRemainder);
      this.bufferRemainder = null;
    }
    callback();
  }
}
```

---

### 9. Trade-offs

| Parameter | Pendekatan A: Default Stream (`highWaterMark: 16KB / 64KB`) | Pendekatan B: Jumbo Stream (`highWaterMark: 1MB - 8MB`) | Analisis Trade-off |
| :--- | :--- | :--- | :--- |
| **Throughput** | Sedang - Tinggi pada network stream biasa. | Maksimal pada Local Disk NVMe / SAN Storage. | Ukuran chunk besar meminimalkan pergantian konteks (*context switches*) pada kernel syscall read/write, mendongkrak throughput hingga 3x lipat pada storage berkecepatan tinggi. |
| **Latency to First Byte (TTFB)** | Rendah (Milidetik). Data langsung terdistribusi ke downstream. | Tinggi. Menunggu akumulasi buffer internal mencapai Megabyte sebelum diteruskan. | Untuk sistem *interactive* atau HTTP streaming, chunk besar memicu degradasi latensi interaktif secara drastis. |
| **Memory Footprint (RSS)** | Sangat Rendah (~30MB - 50MB konstan). | Cepat Meningkat di Bawah Beban Konkurensi Tinggi. | Jika terdapat 1.000 koneksi bersamaan yang masing-masing menggunakan buffer 8MB, proses akan menggunakan $1000 \times 8\text{MB} \approx 8\text{GB}$ RAM, meningkatkan risiko *OOM kill*. |
| **GC Pressure** | Sedang. Pembuatan objek Buffer wrapper terjadi lebih sering. | Rendah secara frekuensi alokasi, namun GC Pause V8 dapat melonjak jika objek besar lolos ke generasi *Old Space*. | Ukuran buffer yang lebih kecil dan stabil menjaga alokasi tetap berada dalam batasan *Scavenge collection* generasi muda V8. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan Fatal 1: Mengabaikan Nilai Boolean `stream.push()` dan `writable.write()`
*Penyebab:* Developer berasumsi pemanggilan `.push()` akan selalu berhasil tanpa memeriksa apakah internal buffer sudah jenuh.
*Gejala:* Memori RAM membengkak tak terkendali hingga proses mati (`OOM / Error: JavaScript heap out of memory`).
*Solusi:*
```javascript
// KESALAHAN:
for (const record of massiveDataset) {
  readable.push(record); // Buffer internal meledak jika consumer lambat
}

// BENAR:
function pushAsync(stream, data) {
  return new Promise((resolve) => {
    const canContinue = stream.push(data);
    if (canContinue) return resolve();
    stream.once('drain', resolve); // Menunggu event drain
  });
}
```

#### Kesalahan Fatal 2: Memory Leak Akibat Retensi Slab Allocator
*Penyebab:* Memotong buffer kecil via `Buffer.subarray()` atau `Buffer.slice()` dari buffer hasil pembacaan file besar, lalu menyimpannya dalam cache memori jangka panjang (misal Map/LRU).
*Gejala:* Node.js process menggunakan 2GB memori padahal data yang tersimpan di cache menurut kalkulasi matematika hanya 10MB.
*Solusi:* Putuskan kaitan slab dengan mengkloning data via `Buffer.from(slice)` atau `Uint8Array.prototype.slice()`.

#### Kesalahan Fatal 3: Penanganan Event Error Stream Secara Parsial
*Penyebab:* Menggunakan `.pipe()` warisan lama Node.js (Node < 10) tanpa error forwarding.
*Gejala:* Unhandled exception menutup aplikasi runtime secara tiba-tiba atau kebocoran *File Descriptor* (`EMFILE: too many open files`).
*Solusi:* Gunakan fungsi `stream.pipeline` atau `stream/promises` secara eksklusif yang otomatis menangani agregasi error dan penghancuran channel I/O.

---

### 11. Best Practices (Production Checklist)

1. [ ] **Gunakan `stream/promises` atau `pipeline`:** Jangan pernah menggunakan manual `.pipe()` pada aplikasi produksi modern.
2. [ ] **Kalibrasi `highWaterMark` Berdasarkan Tipe I/O:** 
   - Network Sockets / WebSockets: `16 KiB - 64 KiB`.
   - File I/O (Disk NVMe): `128 KiB - 1024 KiB`.
   - ObjectMode: Batasi angka hitungan objek antara `16` hingga `100`.
3. [ ] **Implementasi AbortSignal:** Pasang `signal: controller.signal` pada semua konstruktor stream untuk memungkinkan pembatalan instan saat request HTTP klien terputus.
4. [ ] **Lindungi Operasi File System Bersamaan:** Jangan memanggil `fs.promises.writeFile` secara acak pada target file yang sama tanpa menerapkan file locking (*advisory locking* via `fcntl` atau pustaka penunjang) guna mencegah korupsi data biner (*race conditions*).
5. [ ] **Gunakan `Buffer.alloc` untuk Zero-Filled Memory:** Hindari penggunaan `Buffer.allocUnsafe` pada sistem yang melayani multi-tenant publik kecuali buffer tersebut langsung dan sepenuhnya di-overwrite dengan data baru untuk mencegah kebocoran sisa memori privat (data sisa memori kernel/proses lain).

---

### 12. Hands-on Practice

Struktur direktori praktikum:
```
hands-on/m02/
├── package.json
├── src/
│   ├── atomic-writer.mjs
│   ├── high-perf-pipeline.mjs
│   └── rate-limited-stream.mjs
└── test/
    └── pipeline.test.mjs
```

#### Langkah 1: Persiapan Environment

Masuk ke direktori kerja dan inisialisasi:
```bash
mkdir -p hands-on/m02/src hands-on/m02/test
cd hands-on/m02
npm init -y
npm pkg set type="module"
```

#### Langkah 2: Implementasi Atomic File Writer Menggunakan File Descriptors

File: `hands-on/m02/src/atomic-writer.mjs`

```javascript
import { open, rename, unlink } from 'node:fs/promises';
import { randomBytes } from 'node:crypto';
import { dirname, join } from 'node:path';

/**
 * Menulis berkas secara atomik ke filesystem.
 * Mencegah pembacaan berkas parsial jika server mengalami crash di tengah penulisan.
 */
export async function writeAtomic(targetPath, bufferData) {
  const dir = dirname(targetPath);
  const tempPath = join(dir, `.tmp-${randomBytes(8).toString('hex')}`);
  
  let fileHandle;
  try {
    // 1. Buka file descriptor temporer dalam mode Write-Only
    fileHandle = await open(tempPath, 'w', 0o600);
    
    // 2. Tulis seluruh buffer ke file temporer
    await fileHandle.write(bufferData, 0, bufferData.length, null);
    
    // 3. Paksa kernel untuk mengosongkan cache disk internal (Fsync)
    await fileHandle.sync();
    
    // 4. Tutup File Descriptor sebelum operasi pergantian nama atomik
    await fileHandle.close();
    fileHandle = null;

    // 5. Atomic Rename (POSIX rename(2) menjamin sifat atomik di level filesystem)
    await rename(tempPath, targetPath);
  } catch (error) {
    if (fileHandle) {
      await fileHandle.close().catch(() => {});
    }
    await unlink(tempPath).catch(() => {});
    throw error;
  }
}
```

#### Langkah 3: Implementasi Rate-Limited Throttle Transform Stream

File: `hands-on/m02/src/rate-limited-stream.mjs`

```javascript
import { Transform } from 'node:stream';

/**
 * Membatasi throughput pemrosesan data (Leaky Bucket Stream).
 */
export class RateLimiterStream extends Transform {
  constructor(bytesPerSecond, options = {}) {
    super(options);
    this.bytesPerSecond = bytesPerSecond;
    this.tokenBucket = bytesPerSecond;
    this.lastRefill = Date.now();
  }

  _transform(chunk, encoding, callback) {
    const now = Date.now();
    const elapsedTime = (now - this.lastRefill) / 1000;
    
    // Refill bucket
    this.tokenBucket = Math.min(
      this.bytesPerSecond, 
      this.tokenBucket + elapsedTime * this.bytesPerSecond
    );
    this.lastRefill = now;

    if (this.tokenBucket >= chunk.length) {
      this.tokenBucket -= chunk.length;
      this.push(chunk);
      callback();
    } else {
      // Hitung durasi sleep yang dibutuhkan hingga token cukup
      const neededBytes = chunk.length - this.tokenBucket;
      const delayMs = Math.ceil((neededBytes / this.bytesPerSecond) * 1000);

      setTimeout(() => {
        this.tokenBucket = 0;
        this.lastRefill = Date.now();
        this.push(chunk);
        callback();
      }, delayMs);
    }
  }
}
```

#### Langkah 4: Pipeline Pengujian Otomatis

File: `hands-on/m02/test/pipeline.test.mjs`

```javascript
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile, unlink } from 'node:fs/promises';
import { join } from 'node:path';
import { Buffer } from 'node:buffer';
import { writeAtomic } from '../src/atomic-writer.mjs';

test('Atomic Writer Operation should guarantee data integrity', async () => {
  const testFile = join(process.cwd(), 'test-data-atomic.bin');
  const payload = Buffer.from('CRITICAL_FINANCIAL_RECORD_PAYLOAD_BYTE_STREAM');

  try {
    await writeAtomic(testFile, payload);
    const readResult = await readFile(testFile);
    
    assert.deepEqual(readResult, payload);
    assert.equal(readResult.length, payload.length);
  } finally {
    await unlink(testFile).catch(() => {});
  }
});
```

Jalankan pengujian via terminal:
```bash
node --test test/pipeline.test.mjs
```

---

### 13. Exercise

#### Tingkat Easy:
Buatlah fungsi `inspectBufferSlab(buffer: Buffer): { byteLength: number, isDirectSlab: boolean }` yang menerima input buffer dan mendeteksi apakah buffer tersebut berbagi alokasi memori dengan global slab pool Node.js menggunakan properti `buffer.buffer.byteLength`.

#### Tingkat Medium:
Bangun sebuah custom `Duplex` stream bernama `EchoProtocolStream`. Sisi Writable menerima frame teks terenkripsi string heksadesimal, mendekripsinya, lalu sisi Readable memancarkan kembali hasil dekripsi tersebut dalam format biner murni dengan pemisah framing 4-byte big-endian yang menyatakan ukuran payload.

#### Tingkat Hard:
Implementasikan custom `Readable` stream yang membaca data dari file log biner berukuran sangat besar secara **mundur (dari EOF ke byte 0)** menggunakan `fs.read` dengan direct file descriptor manipulation. Stream harus memancarkan baris demi baris teks secara terbalik tanpa pernah memuat lebih dari 128 KiB ke dalam memori proses pada satu satuan waktu.

---

### 14. Challenge

**Skenario Tantangan:**
Perusahaan logistik multinasional membutuhkan sistem pipeline *Zero-Leak Stream Aggregator* untuk mengumpulkan telemetry data biner dari armada sensor IoT.

**Spesifikasi Kebutuhan:**
1. Bangun pipeline streaming yang menerima *inbound byte stream* tak terbatas (*infinite stream*).
2. Terapkan custom transform stream yang mengelompokkan data berdasarkan rentang waktu (*Tumbling Time Window*) setiap **500 milidetik** ATAU akumulasi ukuran buffer mencapai **5 MegaByte** (mana pun yang tercapai lebih dulu).
3. Setiap batch window harus dikompresi menggunakan algoritma Gzip (`node:zlib`), dihitung integritas SHA-256-nya, dan ditulis ke disk menggunakan implementasi file writing non-blocking tanpa mengganggu transmisi data chunk berikutnya.
4. **Target Performa:** Pipeline harus memproses throughput minimal 50.000 events/detik tanpa memicu alokasi heap V8 yang mengakibatkan major garbage collection pause lebih dari 15 milidetik, dengan backpressure handling ketat di bawah proteksi `AbortSignal`.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Soal)
1. Berapa ukuran default slab memori internal (`Buffer.poolSize`) pada Node.js, dan operasi apa yang memicu pemanfaatannya?
2. Mengapa method `Buffer.allocUnsafe(size)` jauh lebih cepat dieksekusi daripada `Buffer.alloc(size)`?
3. Apa perbedaan konseptual antara event `'close'`, `'end'`, dan `'finish'` pada siklus hidup Node.js Streams?
4. Mengapa operasi pembacaan file via `fs.promises.readFile` melibatkan Libuv Threadpool, sedangkan pembacaan data TCP Socket tidak?
5. Apa indikasi utama terjadinya pelanggaran backpressure pada sisi produsen stream?

#### Intermediate (5 Soal)
6. Jelaskan apa yang terjadi di level kernel dan memori Node.js saat pemanggilan method `stream.cork()` dan `stream.uncork()` dilakukan pada Writable Stream!
7. Mengapa menyimpan potongan kecil (`subarray`) dari buffer hasil I/O jangka panjang di memori dapat mengakibatkan kebocoran memori tersembunyi (*hidden memory leak*)?
8. Bagaimana implementasi internal `highWaterMark` pada stream dengan konfigurasi `objectMode: true` dibandingkan `objectMode: false`?
9. Apa perbedaan esensial antara syscall POSIX `rename(2)` pada Linux vs implementasi pada Windows saat file tujuan sudah ada di disk?
10. Bagaimana cara kerja internal `stream.pipeline` dalam menangani penutupan File Descriptor jika stream ketiga dari total empat rantai stream memancarkan error?

#### Skenario Kasus Produksi (3 Skenario)
11. **Skenario 1 (Memory Leak):** Profiler aplikasi Node.js Anda menunjukkan heap V8 stabil di angka 100MB, namun Resident Set Size (RSS) pada dashboard Kubernetes terus meningkat hingga 1.5GB sebelum container dimatikan paksa oleh sistem. Analisis komponen apa dari I/O Buffer yang paling mungkin menjadi penyebab utama dan bagaimana cara memperbaikinya!
12. **Skenario 2 (Starvation):** Layanan Node.js Anda melayani API gateway dengan traffic tinggi. Tiba-tiba, panggilan modul `crypto.pbkdf2` dan resolusi alamat IP mikroservis lain via `dns.lookup` mengalami lonjakan latensi hingga 5.000 milidetik saat cron job sinkronisasi file lokal berjalan. Apa akar penyebab masalah ini dan bagaimana mitigasi arsitekturalnya?
13. **Skenario 3 (Data Corruption):** Dua proses worker Node.js menulis log transaksi keuangan secara bersamaan ke file yang sama menggunakan flag `fs.createWriteStream(path, { flags: 'a' })`. Terkadang ditemukan data baris log yang saling menimpa (*interleaved / corrupted*). Mengapa flag append (`'a'`) gagal menjamin konsistensi data jika ukuran chunk melampaui ambang batas tertentu?

---

### Kunci Jawaban & Panduan Evaluasi Quiz

#### Jawaban Basic:
1. **8192 bytes (8 KiB).** Digunakan saat membuat Buffer menggunakan method seperti `Buffer.allocUnsafe(size)` atau operasi pembacaan stream biner internal di mana ukuran buffer yang diminta lebih kecil dari `Buffer.poolSize >>> 1` (4096 bytes).
2. `Buffer.allocUnsafe` hanya menggeser offset pointer pada memori yang dialokasikan tanpa membersihkan atau menginisialisasi byte-byte di dalamnya dengan angka nol (`zero-filling`), sedangkan `Buffer.alloc` melakukan loop pengisian nilai `0x00` pada seluruh blok memori yang diminta.
3. `'finish'` dipancarkan oleh Writable Stream setelah semua buffer data berhasil diflush ke underlying resource; `'end'` dipancarkan oleh Readable Stream ketika tidak ada lagi data yang dapat dikonsumsi; `'close'` dipancarkan ketika sumber daya tingkat rendah (seperti file descriptor atau socket) telah sepenuhnya ditutup.
4. Karena sebagian besar kernel OS modern (POSIX/Windows) tidak menyediakan asynchronous non-blocking API native yang konsisten untuk filesystem, sehingga Libuv menggunakan Threadpool worker untuk mensimulasikan I/O asinkron. Sebaliknya, socket jaringan didukung penuh oleh multiplexer kernel non-blocking (`epoll`/`kqueue`/`IOCP`).
5. Produsen stream terus memanggil `writable.write()` meskipun fungsi tersebut telah mengembalikan nilai `false`, menyebabkan antrean buffer internal melonjak melampaui `highWaterMark`.

#### Jawaban Intermediate:
6. `cork()` memaksa data yang ditulis ditahan di memori internal Node.js tanpa langsung disalurkan ke underlying OS socket/descriptor. Ketika `uncork()` dipanggil, seluruh chunk yang terakumulasi dikonsolidasikan dan dikirim menggunakan satu syscall write berukuran besar (sering memanfaatkan `writev(2)`), meminimalkan context switch CPU.
7. `subarray()` tidak membuat salinan buffer baru, melainkan hanya membuat view baru (`Uint8Array`) yang mengarah ke `ArrayBuffer` slab berukuran 8KB yang sama. Selama view kecil tersebut memiliki referensi aktif, GC V8 dilarang membebaskan keseluruhan slab 8KB dari memori.
8. Pada stream biner standar (`objectMode: false`), `highWaterMark` diukur dalam **satuan total bytes** (contoh default 16384 bytes). Pada `objectMode: true`, `highWaterMark` diukur dalam **satuan jumlah objek** JavaScript diskrit (contoh default 16 objek).
9. Pada Linux/POSIX, `rename(2)` bersifat atomik murni dan akan langsung menimpa file tujuan yang sudah ada secara instan tanpa race condition. Pada Windows, jika target file sudah ada dan sedang dibuka oleh proses lain, syscall penggantian nama akan gagal (`EPERM` / `EBUSY`), sehingga memerlukan penanganan unlinking atau locking khusus.
10. `stream.pipeline` mendaftarkan listener error pada setiap stream di dalam rantai. Jika salah satu stream gagal, pipeline akan memanggil method `.destroy(err)` pada seluruh stream lainnya, memastikan event `'close'` terpancarkan dan file handle/socket internal ditutup melalui callback finalizer tanpa memory leak.

#### Jawaban Skenario Kasus Produksi:
11. **Analisis:** Penyebab utama adalah penumpukan alokasi di luar V8 Heap (*External Memory*), kemungkinan besar akibat backpressure stream yang diabaikan atau retensi pointer slab buffer pada modul native C++ / stream pipeline. Buffer dialokasikan di C++ heap, sehingga metrik heap V8 terlihat normal namun RSS sistem operasi terus membesar. **Solusi:** Terapkan `stream.pipeline` untuk menegakkan backpressure secara ketat, ubah penggunaan `Buffer.allocUnsafe` menjadi alokasi mandiri yang dikloning jika disimpan di cache, dan periksa apakah ada stream listener `.on('data')` yang tidak mematuhi status jeda.
12. **Analisis:** Terjadi **Libuv Threadpool Starvation**. Cron job file I/O memonopoli 4 worker threads default Libuv. Karena `crypto.pbkdf2` dan `dns.lookup` juga bergantung pada threadpool yang sama, eksekusinya antre di belakang operasi file disk. **Solusi:** Naikkan kapasitas threadpool saat inisialisasi aplikasi via environment variable `UV_THREADPOOL_SIZE=64` (maksimal 128), pisahkan pemrosesan cron job ke background worker process/thread terpisah, dan gantikan pemanggilan `dns.lookup` dengan `dns.resolve*` yang berjalan langsung pada network socket non-blocking.
13. **Analisis:** Operasi append ke file hanya dijamin atomik di level kernel sistem operasi jika penulisan buffer tidak melebihi batasan ukuran buffer pipa kernel (pada POSIX dikenal sebagai konstanta `PIPE_BUF`, umumnya 4096 bytes pada Linux). Jika payload log melebihi 4KB, kernel akan memecah data menjadi beberapa syscall write terpisah, menyebabkan proses konkuren lain dapat menyisipkan byte datanya di tengah-tengah paket data sebelumnya.

---

### 16. Summary

- `Buffer` di Node.js dialokasikan pada *External Memory* (C++ heap) dan dioptimalkan menggunakan teknik **Slab Allocation** (blok 8 KiB) untuk menekan overhead alokasi memori sistem operasi.
- Retensi referensi parsial terhadap slab buffer dapat memicu retensi memori tak terlihat yang signifikan; gunakan salinan decoupled (`Buffer.from`) untuk data berumur panjang.
- Operasi File System (`fs`) pada dasarnya memanfaatkan **Libuv Threadpool**, yang dapat tersaturasi jika pipeline stream file lokal tidak diatur secara seimbang bersama komputasi kriptografi dan DNS.
- **Backpressure** adalah hukum fundamental dalam streaming biner: selalu periksa nilai kembali dari method `.write()` dan `.push()`, serta gunakan **`stream.pipeline`** untuk mengelola siklus hidup stream dan penutupan resource secara deterministik.
- Operasi atomik pada file system membutuhkan kombinasi penulisan berkas temporer, instruksi flush eksplisit ke piringan disk (`fsync`), dan pergantian nama atomik via kernel (`rename`) untuk mencegah korupsi data akibat crash sistem.