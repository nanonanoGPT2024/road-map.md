# Bab 03 Module 01: High-Performance I/O: Buffers, Streams, & File Systems

---

## 01: IDENTITAS MODUL

* **Domain Kurikulum:** Backend Development & Database Architecture
* **Kategori:** 04-Backend-and-Database
* **Track:** Node.js Advanced Runtime Engineering
* **Nomor Modul:** Bab 03 Module 01
* **Judul Modul:** High-Performance I/O: Buffers, Streams, & File Systems
* **Tingkat Kesulitan:** Advanced / L5-L6 Engineering Standard
* **Prasyarat Pengetahuan:** Node.js Event Loop Internals, Libuv Thread Pool Lifecycle, Asynchronous Programming (Promises, Async/Await), JavaScript TypedArrays, POSIX System Calls (`read`, `write`, `fsync`, `open`).

---

## 02: LEARNING OBJECTIVES

1. **Menguasai Arsitektur Memori Node.js:** Membedakan alokasi V8 Heap vs. Off-Heap C++ Memory via Buffer API, serta memahami mekanisme `Buffer.allocUnsafe` dan pencegahan kebocoran data (*information disclosure*).
2. **Implementasi Streaming Pipelines:** Menguasai 4 tipe Streams (`Readable`, `Writable`, `Duplex`, `Transform`) dan orkestrasi via `stream.pipeline` dengan penanganan *backpressure* deterministik.
3. **Optimasi Low-Level File System Operations:** Mengimplementasikan manipulasi file berkinerja tinggi menggunakan File Handles, Direktori Rekursif, Fast-CSV parsing manual, serta sinkronisasi storage via `fsync` dan atomic swap.
4. **Analisis Komparasi Kinerja I/O:** Mengukur metrik throughput, memory churn, dan time-to-first-byte (TTFB) antara chunk-based streaming vs batch buffering pada skala data multi-gigabyte.

---

## 03: CONCEPT MAP DIAGRAM

```
Node.js High-Performance I/O Subsystem
├── V8 Engine
│   └── JS Heap Memory (Metadata, Primitive References)
└── C++ Native Binding Layer (Node.js Core)
    ├── Buffer Architecture (Off-Heap Allocation via ArrayBuffer)
    │   ├── Buffer.alloc (Zero-filled, Safe)
    │   ├── Buffer.allocUnsafe (Fast, Raw Slab Memory)
    │   └── Buffer Pool (8KB Slab Allocator: Buffer.poolSize)
    ├── Stream Architecture (Chunk-by-Chunk Processing)
    │   ├── Readable (Push/Pull Modes, .read(), 'data' event)
    │   ├── Writable (.write(), highWaterMark, 'drain' event)
    │   ├── Duplex / Transform (Through streams, zlib, crypto)
    │   └── Flow Control Mechanism (Backpressure Engine)
    └── File System Engine (fs/promises, fs.constants)
        ├── POSIX Abstraction (open, read, write, close, fsync)
        └── Libuv Threadpool Offloading (Non-blocking File I/O)
```

---

## 04: MENGAPA RELEVAN

Memuat keseluruhan file berukuran 1GB–10GB ke dalam RAM menggunakan `fs.readFile()` akan langsung memicu `ERR_STRING_TOO_LONG` atau `FATAL ERROR: Ineffective mark-compacts near heap limit Allocation failed - JavaScript heap out of memory`. V8 Engine memiliki batas heap default (~1.4GB–4GB tergantung arsitektur dan flag `--max-old-space-size`).

```
[ Traditional File Read: fs.readFile ]
Storage File (2GB) ──> [ Load Entire File into V8 Heap ] ──> Crash: OOM Out-of-Memory!

[ High-Performance Streaming Pipeline ]
Storage File (2GB) ──> [ Chunk: 64KB ] ──> [ Transform ] ──> [ Destination ] ──> Memory Peak: < 30MB!
```

Arsitektur I/O streaming dan alokasi off-heap Buffer menyelesaikan tantangan ini. Node.js mampu memproses data yang ukurannya jauh melampaui kapasitas RAM fisik dengan *memory footprint* konstan (seringkali di bawah 30MB). Kemampuan ini mutlak dibutuhkan pada aplikasi enterprise: pemrosesan batch log ETL, sinkronisasi file S3, ingestion CSV jutaan baris, hingga enkripsi media real-time.

---

## 05: ANATOMI KONSEP INTI

### 1. Buffer Internals & The 8KB Slab Allocator
Buffer pada Node.js adalah representasi sekuens byte mentah yang dialokasikan di luar (*off-heap*) V8 heap memory melalui C++ layer (`node::Buffer`).
* **Slab Allocator:** Untuk alokasi berukuran $\le 4\text{ KB}$ (`Buffer.poolSize >>> 1`), Node.js menggunakan sistem slab pra-alokasi berukuran 8192 bytes (`Buffer.poolSize`). Potongan kecil dialokasikan dari slab yang sama untuk menekan *system call allocation overhead* (`malloc`).
* **`Buffer.alloc(size)`:** Mengalokasikan memori dan membersihkannya (diisi byte `0x0`). Aman, bebas kebocoran memori, tetapi memiliki sedikit overhead inisialisasi.
* **`Buffer.allocUnsafe(size)`:** Mengalokasikan memori langsung tanpa inisialisasi. Jauh lebih cepat, namun memori yang didapat dapat berisi data sensitif (*garbage memory*) dari proses sebelumnya. Harus segera ditimpa penuh (`fill` atau disalin via I/O).

### 2. Stream Architecture & Backpressure Dynamics
Stream adalah antarmuka abstrak berbasis `EventEmitter` untuk menangani data sekuensial secara bertahap (*streaming*).

$$\text{Backpressure Triggered} \iff \text{Writable Buffer Length} \ge \text{highWaterMark}$$

* **Readable Stream:** Sumber data. Beroperasi dalam dua mode: *flowing* (otomatis mendorong data via event `data`) dan *paused* (eksplisit ditarik via `stream.read()`).
* **Writable Stream:** Target data. Method `writable.write(chunk)` mengembalikan nilai boolean:
  * `true`: Internal buffer belum melampaui `highWaterMark` (default 16KB untuk object streams, 64KB untuk byte streams). Aman untuk terus menulis.
  * `false`: Internal buffer penuh (*Backpressure* terjadi). Produser **harus** berhenti mengirim data dan menunggu event `drain`.
* **Transform Stream:** Stream `Duplex` yang melakukan komputasi matematis/mutasi pada chunk input untuk menghasilkan output (misalnya: enkripsi `crypto`, kompresi `zlib`, kompilasi baris CSV).

### 3. File System Internals: Libuv & POSIX
Operasi File System di Node.js didelegasikan ke Libuv Thread Pool (default 4 thread, dikonfigurasi via `UV_THREADPOOL_SIZE`) karena sistem operasi modern umumnya tidak memiliki antarmuka non-blocking asynchronous file I/O yang konsisten di semua platform (seperti halnya epoll/kqueue pada Network Sockets). Penggunaan `fs/promises` dan FileHandle mengabstraksikan file descriptor (`fd`) untuk operasi atomic dan streaming berpresisi tinggi.

---

## 06: PANDUAN IMPLEMENTASI STEP-BY-STEP

### Langkah 1: Eksplorasi Alokasi Memory Buffer Aman vs Unsafe
Inisialisasi buffer, amati mutasi biner, dan bandingkan performa alokasi.

```javascript
import { Buffer } from 'node:buffer';

// 1. Alokasi Aman (Zero-filled)
const safeBuf = Buffer.alloc(10);
console.log('Safe Buffer (Zero-filled):', safeBuf); // <Buffer 00 00 00 00 00 00 00 00 00 00>

// 2. Alokasi Unsafe (Mengandung uninitialized raw memory)
const unsafeBuf = Buffer.allocUnsafe(10);
console.log('Unsafe Buffer (Garbage Memory):', unsafeBuf);
// Sanitasi instan jika menggunakan allocUnsafe:
unsafeBuf.fill(0);

// 3. String Encoding & Mutation
const stringBuf = Buffer.from('Node.js I/O');
console.log('UTF-8 Octets:', stringBuf);
console.log('Hex representation:', stringBuf.toString('hex'));
```

### Langkah 2: Mengimplementasikan Custom Transform Stream
Membuat parser stream berbasis byte yang mengonversi teks mentah menjadi baris JSON terstruktur.

```javascript
import { Transform } from 'node:stream';

class UpperCaseTransform extends Transform {
  constructor(options = {}) {
    super(options);
  }

  _transform(chunk, encoding, callback) {
    try {
      const upperChunk = chunk.toString('utf-8').toUpperCase();
      this.push(Buffer.from(upperChunk));
      callback(); // Chunk sukses diproses
    } catch (err) {
      callback(err); // Propagasi error
    }
  }

  _flush(callback) {
    // Dipanggil sebelum stream benar-benar ditutup
    this.push(Buffer.from('\n--- STREAM COMPLETED ---'));
    callback();
  }
}
```

### Langkah 3: Mengendalikan Backpressure Secara Manual
Menulis data massal ke `WritableStream` tanpa membebani RAM via event `drain`.

```javascript
import { createWriteStream } from 'node:fs';

function writeMillionRecords(writer, dataProvider, encoding = 'utf-8') {
  let i = 1_000_000;
  
  function write() {
    let ok = true;
    do {
      i--;
      const data = dataProvider(i);
      if (i === 0) {
        // Penulisan terakhir
        writer.write(data, encoding);
      } else {
        // Cek backpressure: ok = false jika buffer penuh
        ok = writer.write(data, encoding);
      }
    } while (i > 0 && ok);
    
    if (i > 0) {
      // Buffer penuh! Tunggu hingga buffer dikosongkan ke disk
      writer.once('drain', write);
    }
  }
  
  write();
}
```

---

## 07: CONTOH KASUS SEDERHANA

Streaming dan kompresi file teks menggunakan `node:zlib` dan `node:stream/promises`.

```javascript
// simple-compress.js
import { createReadStream, createWriteStream } from 'node:fs';
import { createGzip } from 'node:zlib';
import { pipeline } from 'node:stream/promises';

async function compressFile(sourcePath, destinationPath) {
  const readStream = createReadStream(sourcePath);
  const gzipStream = createGzip({ level: 6 }); // Compression Level
  const writeStream = createWriteStream(destinationPath);

  try {
    console.time('Compression Execution');
    // pipeline menangani error propagation dan auto-destruction stream
    await pipeline(readStream, gzipStream, writeStream);
    console.timeEnd('Compression Execution');
    console.log(`Kompresi sukses: ${destinationPath}`);
  } catch (error) {
    console.error('Pipeline gagal:', error.message);
    throw error;
  }
}

// Eksekusi (Opsional)
// await compressFile('sample.txt', 'sample.txt.gz');
```

---

## 08: IMPLEMENTASI PRODUCTION-GRADE

Sistem ETL Log Engine berskala Enterprise yang memproses file log mentah multi-gigabyte, melakukan parsing baris via Transform Stream kustom, mengenkripsi stream menggunakan AES-256-GCM, mengompresinya dengan Gzip, lalu menyimpannya secara atomik ke disk.

```javascript
// production-log-pipeline.js
import { createReadStream, createWriteStream } from 'node:fs';
import { open, rename, unlink } from 'node:fs/promises';
import { pipeline } from 'node:stream/promises';
import { Transform } from 'node:stream';
import { createGzip } from 'node:zlib';
import { createCipheriv, randomBytes } from 'node:crypto';
import path from 'node:path';

/**
 * Custom Line Transformer & Redactor Stream
 * Mengurai stream byte mentah menjadi baris terstruktur dan menyensor data sensitif (PII/Tokens).
 */
class LogSanitizerStream extends Transform {
  constructor(options = {}) {
    super({ ...options, readableObjectMode: false, writableObjectMode: false });
    this._tail = '';
    this._redactPattern = /(password|token|apiKey|authorization)=([^&\s]+)/gi;
  }

  _transform(chunk, encoding, callback) {
    try {
      const data = this._tail + chunk.toString('utf-8');
      const lines = data.split('\n');
      
      // Simpan elemen terakhir sebagai sisa buffer untuk chunk berikutnya
      this._tail = lines.pop() || '';

      const sanitizedLines = [];
      for (let i = 0; i < lines.length; i++) {
        const line = lines[i].trim();
        if (!line) continue;
        
        // Sensor sensitive keys
        const sanitized = line.replace(this._redactPattern, '$1=[REDACTED]');
        sanitizedLines.push(JSON.stringify({
          timestamp: new Date().toISOString(),
          payload: sanitized
        }) + '\n');
      }

      if (sanitizedLines.length > 0) {
        this.push(Buffer.from(sanitizedLines.join('')));
      }
      callback();
    } catch (err) {
      callback(err);
    }
  }

  _flush(callback) {
    if (this._tail.trim()) {
      const sanitized = this._tail.replace(this._redactPattern, '$1=[REDACTED]');
      this.push(Buffer.from(JSON.stringify({
        timestamp: new Date().toISOString(),
        payload: sanitized
      }) + '\n'));
    }
    callback();
  }
}

/**
 * Enterprise Production Pipeline
 */
export async function processLogPipeline({
  sourceFilePath,
  targetDirectory,
  encryptionKey
}) {
  if (!encryptionKey || encryptionKey.length !== 32) {
    throw new Error('Encryption Key harus valid 32 bytes (256-bit).');
  }

  const timestamp = Date.now();
  const tempTargetFile = path.join(targetDirectory, `.temp-${timestamp}.log.gz.enc`);
  const finalTargetFile = path.join(targetDirectory, `processed-${timestamp}.log.gz.enc`);

  // Initializing Cryptographic Context (AES-256-GCM)
  const iv = randomBytes(12); // NIST recommend 96-bit IV for GCM
  const cipher = createCipheriv('aes-256-gcm', encryptionKey, iv);

  // File Read & Write Streams
  const readStream = createReadStream(sourceFilePath, {
    highWaterMark: 128 * 1024 // 128KB chunks untuk performa disk I/O maksimal
  });

  const writeStream = createWriteStream(tempTargetFile, {
    flags: 'w',
    mode: 0o600, // Read/Write khusus Owner (POSIX hardening)
    highWaterMark: 128 * 1024
  });

  // Tulis Initialization Vector (IV) pada 12 byte pertama file target
  writeStream.write(iv);

  const sanitizer = new LogSanitizerStream({ highWaterMark: 64 * 1024 });
  const gzip = createGzip({ level: 7, memLevel: 8 });

  try {
    console.log(`[PIPELINE START] Processing: ${sourceFilePath}`);
    
    await pipeline(
      readStream,
      sanitizer,
      gzip,
      cipher,
      writeStream
    );

    // Ambil Auth Tag GCM untuk memvalidasi integritas ciphertext
    const authTag = cipher.getAuthTag();
    
    // Simpan Auth Tag (16 bytes) di akhir file via Low-Level FileHandle
    const handle = await open(tempTargetFile, 'a');
    try {
      await handle.write(authTag);
      // Flush kernel cache ke fisik storage medium
      await handle.sync();
    } finally {
      await handle.close();
    }

    // Atomic Move (Rename) untuk menjamin integritas file di storage target
    await rename(tempTargetFile, finalTargetFile);
    console.log(`[PIPELINE COMPLETE] Generated: ${finalTargetFile}`);
    
    return {
      status: 'SUCCESS',
      outputPath: finalTargetFile,
      ivHex: iv.toString('hex'),
      authTagHex: authTag.toString('hex')
    };
  } catch (error) {
    console.error(`[PIPELINE FAILED] Eradicating temporary file: ${tempTargetFile}`);
    try {
      await unlink(tempTargetFile);
    } catch {
      // Abaikan jika file temp belum sempat dibuat
    }
    throw error;
  }
}
```

---

## 09: DIAGRAM ALUR KERJA

```
Data Ingestion Flow (AES-GCM Encrypted & Compressed Pipeline)

[ Source File (Disk) ]
         │ (Chunk Size: 128KB)
         ▼
[ Readable Stream (HighWaterMark: 128KB) ]
         │
         ▼
[ LogSanitizerStream (Transform) ] ──> Redact PII (password=[REDACTED])
         │
         ▼ (String to Buffer)
[ Gzip Stream (Transform) ] ─────────> Deflate Compression Level 7
         │
         ▼
[ AES-256-GCM (Transform) ] ─────────> Stream Encryption
         │ (Payload Encrypted)
         ▼
[ Writable Stream (Disk Temp) ] ─────> 1. Writes 12-byte IV Header
         │                             2. Writes Encrypted Chunks
         │                             3. HighWaterMark Controlled (Drain)
         ▼
[ Low-Level fsync & Auth Tag Append ]
         │
         ▼
[ Atomic POSIX Rename: temp -> final ]
```

---

## 10: ANALISIS TRADE-OFFS

| Pendekatan | Kelebihan | Kelemahan | Kapan Digunakan |
| :--- | :--- | :--- | :--- |
| **`fs.readFile` (In-Memory Buffer)** | Sangat sederhana, eksekusi cepat untuk file kecil, synchronous mental model. | Menghabiskan RAM, resiko OOM Crash, limit string V8 ~512MB–1GB. | Konfigurasi `.json`, certs `.pem`, file $< 10\text{ MB}$. |
| **Streams (`stream.pipeline`)** | Konsumsi RAM statis ($O(1)$ Memory Complexity), elastisitas Backpressure, composable. | Error handling kompleks jika manual, tracing async stack trace lebih sulit. | Data $> 50\text{ MB}$, transformasi ETL, media processing, proxying. |
| **Direct FileHandle (`open/read/write`)** | Kontrol byte-offset eksplisit, zero intermediate abstraction, POSIX `fsync` direct control. | Boilerplate kode tinggi, manual tracking position offset, manual descriptor closing. | Database custom storage engines, append-only transaction logging (WAL). |
| **`Buffer.allocUnsafe`** | Bypass overhead zero-filling memory, throughput komputasi mentah tertinggi. | Resiko kebocoran data sensitif (*Information Leak*) jika tidak ditimpa penuh. | Alokasi berfrekuensi tinggi di hot-path yang segera ditimpa via I/O read. |

---

## 11: BEST PRACTICES & ANTIPATTERNS

### Antipatterns
1. **Menggunakan `.pipe()` Tradisional:** `readable.pipe(writable)` **tidak** membersihkan streams jika terjadi uncaught error pada stream perantara, menyebabkan *descriptor leak* dan *memory leak*.
2. **Buffer Concatenation via Array Accumulation:** Mengakumulasikan buffer `let str = ''; stream.on('data', c => str += c)` memicu konversi implisit UTF-8 yang memotong multi-byte karakter (seperti Kanji/Emoji) dan memicu fragmentasi memori V8.
3. **Mengabaikan Nilai Boolean `stream.write()`:** Terus memompa data tanpa mendengarkan status backpressure menyebabkan unconstrained RAM consumption hingga limit OOM tercapai.

### Best Practices
1. **Gunakan `stream.pipeline` (atau `node:stream/promises`):** Secara otomatis menangani error handling, propagasi error pada rantai pipeline, dan menutup semua file descriptor.
2. **Terapkan `StringDecoder`:** Jika mengubah stream byte menjadi teks parsial, gunakan `string_decoder` untuk mempertahankan multi-byte UTF-8 boundary integrity.
3. **Konfigurasi `highWaterMark` Sesuai Beban I/O:** Gunakan nilai yang lebih tinggi ($128\text{ KB} - 256\text{ KB}$) untuk operasi file disk throughput tinggi, dan gunakan ukuran lebih kecil ($16\text{ KB}$) untuk memory constrained network proxying.

---

## 12: SECURITY HARDENING

1. **Information Leakage via Uninitialized Buffers:**
   Selalu gunakan `Buffer.alloc(size)` pada layer API publik. Jika terpaksa menggunakan `Buffer.allocUnsafe(size)` demi performa internal parser, pastikan buffer segera ditimpa penuh atau gunakan method `.fill(0)`.
2. **Path Traversal Mitigation:**
   Validasi resolusi path file secara mutlak dan pastikan target berada dalam direktori yang diizinkan (whitelisted root).
   ```javascript
   import path from 'node:path';

   function resolveSecurePath(userInput, baseDirectory) {
     const safePath = path.normalize(userInput).replace(/^(\.\.[\/\\])+/, '');
     const resolved = path.resolve(baseDirectory, safePath);
     if (!resolved.startsWith(baseDirectory)) {
       throw new Error('SECURITY_VIOLATION: Path Traversal Detected.');
     }
     return resolved;
   }
   ```
3. **File Permission Lockdown:**
   Saat membuat file sensitif (seperti log yang memuat info sistem atau file terenkripsi), tentukan *POSIX permissions* eksplisit `mode: 0o600` (hanya owner yang memiliki akses Read/Write).

---

## 13: OBSERVABILITAS & DEBUGGING

Lakukan instrumentasi stream lifecycle untuk mengidentifikasi bottleneck dan backpressure stall menggunakan Node.js core events.

```javascript
import { PassThrough } from 'node:stream';

export function createStreamMetricsTracker(metricName) {
  let totalBytes = 0;
  let backpressureCount = 0;
  const startTime = performance.now();

  const monitor = new PassThrough();

  monitor.on('data', (chunk) => {
    totalBytes += chunk.length;
  });

  // Track drain event on downstream writable
  monitor.on('pipe', (src) => {
    console.log(`[MONITOR:${metricName}] Pipeline connected.`);
  });

  return {
    monitorStream: monitor,
    getMetrics: () => ({
      name: metricName,
      bytesProcessed: totalBytes,
      durationMs: performance.now() - startTime,
      throughputMBps: (totalBytes / (1024 * 1024)) / ((performance.now() - startTime) / 1000)
    })
  };
}
```

* **Debugging via Native Trace Flags:**
  Jalankan aplikasi Node.js dengan flag diagnostik stream internal:
  ```bash
  NODE_DEBUG=stream,fs node production-log-pipeline.js
  ```

---

## 14: BENCHMARKING & PERFORMANCE

Ukur perbedaan eksekusi antara `fs.readFile` (Buffered) vs `createReadStream` (Streaming) pada dataset 500MB.

```javascript
// benchmark-io.js
import { writeFile, readFile, rm } from 'node:fs/promises';
import { createReadStream, createWriteStream } from 'node:fs';
import { pipeline } from 'node:stream/promises';
import { Transform } from 'node:stream';

const TEST_FILE = './bench_data.raw';
const DUMMY_SIZE = 500 * 1024 * 1024; // 500MB

async function setup() {
  console.log('Generating dummy dataset 500MB...');
  const handle = await createWriteStream(TEST_FILE);
  const chunk = Buffer.alloc(1024 * 1024, 'X'); // 1MB chunk
  for (let i = 0; i < 500; i++) {
    handle.write(chunk);
  }
  await new Promise(resolve => handle.end(resolve));
}

async function runBenchmark() {
  await setup();

  // Test 1: Buffered (readFile)
  const memBefore1 = process.memoryUsage().heapUsed;
  const start1 = performance.now();
  try {
    const data = await readFile(TEST_FILE);
    const length = data.length;
  } catch (err) {
    console.error('readFile Failed:', err.message);
  }
  const end1 = performance.now();
  const memAfter1 = process.memoryUsage().heapUsed;
  console.log(`[Buffered fs.readFile] Duration: ${(end1 - start1).toFixed(2)}ms | Peak Memory Delta: ${((memAfter1 - memBefore1) / (1024 * 1024)).toFixed(2)} MB`);

  // Force Garbage Collection jika exposed via node --expose-gc
  if (global.gc) global.gc();

  // Test 2: Stream Pipeline
  const memBefore2 = process.memoryUsage().heapUsed;
  const start2 = performance.now();
  let streamLength = 0;
  const countingStream = new Transform({
    transform(chunk, enc, cb) {
      streamLength += chunk.length;
      cb();
    }
  });

  await pipeline(
    createReadStream(TEST_FILE, { highWaterMark: 64 * 1024 }),
    countingStream
  );
  const end2 = performance.now();
  const memAfter2 = process.memoryUsage().heapUsed;
  console.log(`[Stream Pipeline]     Duration: ${(end2 - start2).toFixed(2)}ms | Peak Memory Delta: ${((memAfter2 - memBefore2) / (1024 * 1024)).toFixed(2)} MB`);

  await rm(TEST_FILE, { force: true });
}

runBenchmark();
```

---

## 15: HANDS-ON LAB MINI-PROJECT

### High-Throughput Binary File Splitter and Checksum Verifier

Buat aplikasi CLI yang:
1. Membaca file biner besar (*Source File*).
2. Membagi file tersebut menjadi partisi chunk individual berukuran $10\text{ MB}$ (`chunk.part001`, `chunk.part002`, dst).
3. Secara paralel menghitung digest SHA-256 secara streaming tanpa overhead alokasi ganda.

```javascript
// lab-file-splitter.js
import { createReadStream, createWriteStream } from 'node:fs';
import { createHash } from 'node:crypto';
import { Writable } from 'node:stream';
import { pipeline } from 'node:stream/promises';
import path from 'node:path';

class ChunkSplitterStream extends Writable {
  constructor(chunkSizeBytes, outputDirectory, baseFilename, options = {}) {
    super(options);
    this.chunkSizeBytes = chunkSizeBytes;
    this.outputDirectory = outputDirectory;
    this.baseFilename = baseFilename;
    this.currentPart = 1;
    this.currentBytesWritten = 0;
    this.currentWriteStream = null;
  }

  _getPartFilename() {
    const partNumber = String(this.currentPart).padStart(4, '0');
    return path.join(this.outputDirectory, `${this.baseFilename}.part.${partNumber}`);
  }

  _initNewPart() {
    if (this.currentWriteStream) {
      this.currentWriteStream.end();
    }
    const partPath = this._getPartFilename();
    this.currentWriteStream = createWriteStream(partPath);
    this.currentBytesWritten = 0;
    this.currentPart++;
  }

  _write(chunk, encoding, callback) {
    let offset = 0;
    
    while (offset < chunk.length) {
      if (!this.currentWriteStream || this.currentBytesWritten >= this.chunkSizeBytes) {
        this._initNewPart();
      }

      const remainingInPart = this.chunkSizeBytes - this.currentBytesWritten;
      const bytesToWrite = Math.min(chunk.length - offset, remainingInPart);
      
      const slice = chunk.subarray(offset, offset + bytesToWrite);
      this.currentWriteStream.write(slice);
      
      this.currentBytesWritten += bytesToWrite;
      offset += bytesToWrite;
    }
    
    callback();
  }

  _final(callback) {
    if (this.currentWriteStream) {
      this.currentWriteStream.end(callback);
    } else {
      callback();
    }
  }
}

// Eksekusi Lab Pipeline
export async function runSplitterLab(sourceFile, outputDir, partSizeMB = 10) {
  const partSizeBytes = partSizeMB * 1024 * 1024;
  const hash = createHash('sha256');
  
  const readStream = createReadStream(sourceFile, { highWaterMark: 64 * 1024 });
  const splitter = new ChunkSplitterStream(partSizeBytes, outputDir, path.basename(sourceFile));

  // T-Stream Pattern: Update hash sembari meneruskan data ke splitter
  readStream.on('data', (chunk) => hash.update(chunk));

  console.log(`Memulai partisi untuk file: ${sourceFile}`);
  await pipeline(readStream, splitter);
  
  const finalChecksum = hash.digest('hex');
  console.log(`Partisi selesai. SHA-256 Digest Master: ${finalChecksum}`);
  return { finalChecksum, totalParts: splitter.currentPart - 1 };
}
```

---

## 16: AUTOMATED TESTING & VERIFICATION

Unit test suite menggunakan `node:test` dan `node:assert` untuk memvalidasi *Transform Stream integrity* dan *backpressure resilience*.

```javascript
// test/stream-pipeline.test.js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { Readable, Writable } from 'node:stream';
import { pipeline } from 'node:stream/promises';
import { Buffer } from 'node:buffer';

test('Stream Backpressure & Data Integrity Suite', async (t) => {
  await t.test('Harus memproses chunk dengan ukuran buffer tepat tanpa data corruption', async () => {
    const inputDataset = ['chunk1 ', 'chunk2 ', 'chunk3_end'];
    const expectedOutput = 'CHUNK1 CHUNK2 CHUNK3_END';

    const sourceStream = Readable.from(inputDataset);
    let outputAccumulator = '';

    const upperTransformer = new (await import('node:stream')).Transform({
      transform(chunk, enc, cb) {
        cb(null, chunk.toString().toUpperCase());
      }
    });

    const destinationStream = new Writable({
      write(chunk, enc, cb) {
        outputAccumulator += chunk.toString();
        cb();
      }
    });

    await pipeline(sourceStream, upperTransformer, destinationStream);

    assert.equal(outputAccumulator, expectedOutput);
  });

  await t.test('Buffer allocator integrity: alloc vs allocUnsafe', () => {
    const safeBuf = Buffer.alloc(128);
    for (const byte of safeBuf) {
      assert.equal(byte, 0, 'Buffer.alloc harus zero-filled');
    }

    const unsafeBuf = Buffer.allocUnsafe(128);
    assert.equal(unsafeBuf.length, 128);
    // Unsafe buffer aman digunakan jika langsung di-fill atau ditimpa
    unsafeBuf.fill(0xFF);
    assert.equal(unsafeBuf[0], 255);
  });
});
```

Eksekusi:
```bash
node --test test/stream-pipeline.test.js
```

---

## 17: TROUBLESHOOTING GUIDE

| Gejala Error | Akar Masalah (*Root Cause*) | Solusi Remediasi |
| :--- | :--- | :--- |
| `ERR_STREAM_PREMATURE_CLOSE` | Stream ditutup sebelum siklus transfer byte selesai (misal: koneksi TCP/HTTP diputus klien). | Tangani error via `stream.pipeline()` callback/promise catch block; hapus file temp parsial. |
| `FATAL ERROR: Ineffective mark-compacts near heap limit Allocation failed` | Data dimuat sekaligus ke memory heap (`fs.readFile` atau String concat). | Refactor ke `fs.createReadStream` dan proses secara streaming per-chunk. |
| Memory usage membengkak terus-menerus (*Slow Memory Leak*) | Backpressure diabaikan pada loop penulisan `writable.write()` manual. | Dengarkan nilai balik `.write()`; jika `false`, tunda loop dan tunggu event `once('drain')`. |
| Karakter multi-byte rusak (*Garbage character* ``) | `chunk.toString()` dipanggil pada batas chunk yang memotong byte sequence UTF-8. | Gunakan module `node:string_decoder` (`StringDecoder('utf8')`) alih-alih `chunk.toString()`. |
| `EMFILE: too many open files` | File descriptor bocor karena loop stream manual tidak memanggil `.destroy()` atau `close()`. | Gunakan `stream.pipeline` atau pastikan blok `try/finally` memanggil `fileHandle.close()`. |

---

## 18: CHECKLIST PRODUKSI

- [ ] **Gunakan `stream.pipeline`:** Tidak ada lagi penggunaan method usang `.pipe()` di codebase.
- [ ] **Stream Error Cleanup:** Pastikan temporary files selalu dihapus (`unlink`) pada blok penanganan error pipeline.
- [ ] **Alokasi Buffer Aman:** Hilangkan pemanggilan `Buffer.allocUnsafe` pada logic yang menangani data dari untrusted client input.
- [ ] **File Permissions Restricted:** Pembuatan file output sensitif dikonfigurasi dengan mode POSIX `0o600` atau `0o640`.
- [ ] **Atomic File Writes:** Terapkan strategi tulis ke `.temp` file lalu eksekusi `fs.rename` untuk mencegah *race condition* atau data korup akibat *unexpected process crash*.
- [ ] **Fsync Persistence:** Panggil `.sync()` pada `FileHandle` kritis sebelum file ditutup untuk menjamin data tersimpan di media fisik storage.
- [ ] **Libuv Pool Sizing:** Konfigurasi environment variable `UV_THREADPOOL_SIZE` (default 4) disesuaikan dengan volume konkuren disk I/O (misal: diset ke 16 atau 64).

---

## 19: RINGKASAN EKSEKUTIF

1. **Efisiensi Memori Off-Heap:** Node.js Buffer meng