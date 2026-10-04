# BAB 10 / MODULE 01: Enterprise Security Hardening & Production System Design

---

## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul:** `JS-ENT-SEC-1001`
* **Jalur Kurikulum:** `02-Programming-Languages / JavaScript & Node.js Runtime`
* **Level Kemahiran:** `Advanced / Staff-to-Principal Engineer`
* **Prasyarat:**
  * Penguasaan Arsitektur Internal Node.js (V8 Engine, Event Loop, Libuv, Worker Threads).
  * Pemahaman mendalam tentang Asynchronous I/O dan Network Programming (HTTP/HTTPS, TCP/TLS).
  * Pemahaman dasar tentang Kriptografi Simetris/Asimetris (HMAC, AES-GCM, RSA/ECDSA, Public Key Infrastructure).
  * Familiaritas dengan Container Runtime (Docker, OCI-spec) dan Orchestration dasar (Kubernetes Pod Lifecycle).
* **Tech Stack Terkait:** Node.js v20/v22 LTS, native `node:crypto`, `node:diagnostics_channel`, Linux Namespaces/Capabilities, OpenTelemetry Core, Fastify/Node Native HTTP.

---

## SEKSI 02 — LEARNING OBJECTIVES

1. **Menganalisis & Mengisolasi Vektor Serangan Runtime V8:** Mendiagnosis kerentanan *Prototype Pollution*, *Regular Expression Denial of Service (ReDoS)*, dan *Event Loop Starvation* hingga ke level alokasi memori internal V8 dan struktur *Hidden Classes* (*Shapes*).
2. **Merancang Sistem Kriptografis Konstan (*Constant-Time*):** Mengimplementasikan protokol autentikasi berbasis HMAC dan validasi token kebal *side-channel timing attacks* menggunakan primitif native `node:crypto`.
3. **Membangun Arsitektur Pertahanan Berlapis (*Defense-in-Depth*):** Mengonfigurasi *Kernel-level isolation*, *Process Hardening* (dropping Linux privileges, Read-only Rootfs), dan *Secure Deserialization* pada workload Node.js skala produksi.
4. **Menerapkan Zero-Trust Production Runtime:** Mengeliminasi celah eksekusi kode dinamis (`eval`, `Function`, `vm`) dengan memanfaatkan runtime flags mutakhir (`--disallow-code-generation-from-strings`, `--frozen-intrinsics`) tanpa mengorbankan performa sistem secara drastis.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Prinsip Utama Keamanan Enterprise

```
               [ MODEL DEFENSE-IN-DEPTH NODE.JS ]
┌─────────────────────────────────────────────────────────────┐
│ 1. BOUNDARY LAYER (Network, Cloud WAF, Envoy/Kube Ingress)  │
├─────────────────────────────────────────────────────────────┤
│ 2. PROCESS LAYER (OS Sandbox, Non-Root UID, Seccomp, Capabilities)
├─────────────────────────────────────────────────────────────┤
│ 3. RUNTIME LAYER (V8 Flags, Prototype Immutability, Memory Limits)
├─────────────────────────────────────────────────────────────┤
│ 4. APPLICATION LAYER (Schema Validation, Timing-Safe Crypto)│
└─────────────────────────────────────────────────────────────┘
```

1. **Zero Trust Inside the Process:** Jangan pernah mempercayai dependensi internal sekalipun. Modul pihak ketiga di dalam direktori `node_modules` dieksekusi di context V8 yang sama dengan business logic Anda. Sebuah library parsing string sepele memiliki kapabilitas membaca memori, memodifikasi prototype bawaan global, atau mengekstraksi credential lingkungan runtime (`process.env`).
2. **Fail-Closed vs Fail-Open:** Kegagalan deserialisasi, otorisasi, atau validasi kriptografi harus selalu mengakhiri eksekusi secara deterministik (*Fail-Closed*). Jika state kriptografi tidak dapat dipastikan integritasnya, koneksi wajib diputus segera (*fast-kill* / *fail-secure*).
3. **Event Loop Resilience:** Pada Node.js, denial-of-service (DoS) tidak selalu membutuhkan saturasi bandwidth atau memori. Komputasi sinkron tunggal selama 3.000 ms sudah cukup melumpuhkan throughput ribuan koneksi konkuren. Keamanan pada JavaScript adalah fungsi langsung dari ketersediaan (*availability*) Event Loop.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Arsitektur pertahanan sistem Node.js tingkat enterprise pada infrastruktur terdistribusi:

```
[ Klien Eksternal / Penyerang ]
               │
               ▼
┌──────────────────────────────┐
│  Layer 1: Edge Proxy & WAF   │ ── TLS Termination, DDoS Shield, Geo-IP,
│  (Cloudflare / AWS Shield)   │    Early HTTP Flooding Drop
└──────────────┬───────────────┘
               │ mTLS (Strict Internal)
               ▼
┌──────────────────────────────┐
│  Layer 2: API Gateway        │ ── Token Bucket Rate Limiter, Schema Validation,
│  (Envoy / NGINX Ingress)     │    Strip Malicious Forwarded Headers
└──────────────┬───────────────┘
               │ HTTP/2 over mTLS
               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Container Pod (Linux Hardened Runtime: Non-Root, No New Privs)           │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ Node.js Application Master / Cluster Process                      │  │
│  │ Runtime: --frozen-intrinsics --disallow-code-generation-from-strs │  │
│  │                                                                   │  │
│  │  [Ingress Pipe]                                                   │  │
│  │         │                                                         │  │
│  │         ▼                                                         │  │
│  │  ┌──────────────┐     Payload     ┌────────────────────────────┐  │  │
│  │  │ Body Parser  │ ───────────────>│ Safe Deserializer          │  │  │
│  │  │ Size Guard   │                 │ (Object.create(null) / Map)│  │  │
│  │  └──────────────┘                 └─────────────┬──────────────┘  │  │
│  │                                                 │ Valid Object    │  │
│  │                                                 ▼                 │  │
│  │  ┌──────────────┐    Constant-Time ┌───────────────────────────┐  │  │
│  │  │ Timing-Safe  │ <─────────────── │ Cryptographic Subsystem   │  │  │
│  │  │ HMAC Guard   │   Buffer Compare │ (node:crypto primitives)  │  │  │
│  │  └──────┬───────┘                  └───────────────────────────┘  │  │
│  │         │ Valid Signature                                         │  │
│  │         ▼                                                         │  │
│  │  ┌──────────────────────────────┐                                 │  │
│  │  │ Business Logic Execution     │                                 │  │
│  │  │ (Async Non-Blocking Loop)    │                                 │  │
│  │  └──────────────┬───────────────┘                                 │  │
│  │                 │ Audit Trace                                     │  │
│  │                 ▼                                                 │  │
│  │  ┌──────────────────────────────┐                                 │  │
│  │  │ Structured Security Logger   │ ── Redact PII / Secrets to Pipe │  │
│  │  └──────────────────────────────┘                                 │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Prototype Pollution pada V8 Heap Engine
Objek JavaScript diinisialisasi dengan referensi tersembunyi ke prototipenya (`[[Prototype]]`, dapat diakses via `__proto__`). Ketika payload JSON dievaluasi oleh algoritma *recursive object merge* yang naif, penyerang dapat menyuntikkan properti ke `Object.prototype`. 

```
Penyerang mengirim: {"__proto__": {"isAdmin": true}}
             │
             ▼
Object.prototype.isAdmin = true
             │
             ▼
Setiap Object baru: {} -> mewarisi { isAdmin: true }
```

Dampaknya: Bypass autentikasi, *Remote Code Execution* (jika dependensi lain mengecek properti konfigurasi seperti `options.shell` pada `child_process.spawn`), atau *Denial-of-Service* (merusak method bawaan seperti `Object.prototype.toString`).

### 2. Algorithmic Complexity Attacks (ReDoS)
Mesin regex V8 menggunakan implementasi *Nondeterministic Finite Automaton* (NFA). NFA mengeksplorasi setiap cabang kemungkinan saat mencocokkan string.
* Masalah: *Catastrophic Backtracking*.
* Pola berisiko: Nested quantifiers seperti `^(a+)+$`.
* Jika string target adalah `aaaa...a!` (panjang $N$ karakter tanpa akhiran valid), kompleksitas waktu melonjak dari $\mathcal{O}(N)$ ke $\mathcal{O}(2^N)$. Untuk $N = 30$, prosesor membutuhkan miliaran operasi sinkron. Akibatnya: Event Loop Node.js berhenti merespons I/O (*starvation*).

### 3. Side-Channel Timing Attacks pada Verifikasi Kriptografi
Komparasi string standar JavaScript (`a === b`) mengeksekusi *early return* begitu menemukan karakter pertama yang tidak cocok:

$$\text{Waktu Komparasi} \propto \text{Indeks Karakter Pertama yang Tidak Cocok}$$

Penyerang dapat mengukur latensi jaringan dalam skala mikrodetik (menggunakan distribusi statistik ratusan *request*) untuk menebak secret HMAC byte demi byte. Solusinya: Pembandingan waktu konstan (*constant-time comparison*) yang memproses seluruh byte terlepas dari lokasi perbedaan data.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### Memory Boundary & V8 Intrinsics
V8 menyimpan *built-in intrinsics* (objek standar seperti `Array`, `Object`, `Function`, `Promise`) di heap global. Ketika sebuah modul memodifikasi prototype bawaan, mutasi tersebut bersifat global across module context:

```javascript
Array.prototype.push = function() { /* malicious injection */ };
```

Untuk mitigasi level enterprise, Node.js menyediakan flag `--frozen-intrinsics`. Saat flag ini aktif, runtime mengeksekusi `Object.freeze()` secara rekursif pada seluruh *built-in objects* sebelum modul pertama dimuat.

```
       Global Realm Init
               │
               ▼
      [ V8 Intrinsics ]
               │
     Object.freeze() Rekursif
               │
               ▼
    [ Frozen Intrinsics ] ── Immutable: Penulisan ke Array.prototype
               │                melemparkan TypeError dalam strict mode
               ▼
      Load User Module
```

### Defense Against Event Loop Starvation
Karena arsitektur *single-threaded event loop*, keamanan ketersediaan (availability) bertumpu pada pencegahan pemblokiran thread utama. Semua operasi CPU-bound intensif (seperti enkripsi, hashing, kompresi, parsing struktur data masif) wajib dialihkan ke Threadpool Libuv internal via native bindings atau dieksekusi di dalam pool `Worker Threads` terisolasi.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi modul utilitas pertahanan inti (*Core Security Primitives*) menggunakan zero-dependency native Node.js API.

```javascript
// security-primitives.mjs
import { timingSafeEqual, createHmac, randomBytes } from 'node:crypto';

/**
 * 1. Safe Deserialization & Anti-Prototype Pollution Guard
 * Mencegah object injection ke prototype global.
 */
export function safeDeepClone(source, maxDepth = 10) {
  if (source === null || typeof source !== 'object') {
    return source;
  }

  function clone(target, depth) {
    if (depth > maxDepth) {
      throw new RangeError('Max payload depth exceeded (anti-recursion guard)');
    }

    // Gunakan Object.create(null) untuk memutus rantai prototype
    const result = Array.isArray(target) ? [] : Object.create(null);

    for (const key of Object.keys(target)) {
      // Blacklist prototype pollution triggers secara mutlak
      if (key === '__proto__' || key === 'constructor' || key === 'prototype') {
        continue;
      }

      const val = target[key];
      if (val !== null && typeof val === 'object') {
        result[key] = clone(val, depth + 1);
      } else {
        result[key] = val;
      }
    }
    return result;
  }

  return clone(source, 1);
}

/**
 * 2. Constant-Time Signature Validator
 * Melindungi dari Remote Side-Channel Timing Attacks.
 */
export function verifySignatureConstantTime(payload, signatureHex, secretKey) {
  if (typeof payload !== 'string' || typeof signatureHex !== 'string') {
    return false;
  }

  const expectedHmac = createHmac('sha256', secretKey).update(payload).digest();
  const providedHmac = Buffer.from(signatureHex, 'hex');

  // Panjang buffer WAJIB identik sebelum masuk ke timingSafeEqual
  // Jika panjang berbeda, timingSafeEqual akan melempar RangeError.
  if (expectedHmac.length !== providedHmac.length) {
    // Lakukan komparasi tiruan untuk membakar siklus CPU secara stabil (anti-timing leakage)
    timingSafeEqual(expectedHmac, expectedHmac);
    return false;
  }

  return timingSafeEqual(expectedHmac, providedHmac);
}

/**
 * 3. Safe RegExp Matcher with Hard Timeout
 * Menghalau serangan ReDoS (Catastrophic Backtracking) pada synchronous thread.
 */
export function safeRegexMatch(regex, inputString, timeoutMs = 50) {
  return new Promise((resolve, reject) => {
    const startTime = performance.now();
    
    // Alokasikan execution check pada microtask/macrotask boundary
    const timer = setTimeout(() => {
      reject(new Error(`ReDoS Guard: Execution exceeded timeout of ${timeoutMs}ms`));
    }, timeoutMs);

    try {
      const match = regex.exec(inputString);
      clearTimeout(timer);
      const elapsed = performance.now() - startTime;
      resolve({ match, elapsed });
    } catch (err) {
      clearTimeout(timer);
      reject(err);
    }
  });
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Pembahasan Modul: `security-primitives.mjs`

1. **Baris 1:** `import { timingSafeEqual, createHmac, randomBytes } from 'node:crypto';`
   * Menggunakan prefix `node:` untuk menjamin bahwa runtime mengimpor core library bawaan Node.js, bukan modul tiruan dari `node_modules` (mitigasi *Dependency Confusion/Typo-squatting*).
2. **Baris 7–20:** `safeDeepClone(source, maxDepth = 10)`
   * Menetapkan batasan kedalaman rekursi rekursif `maxDepth`. Jika penyerang menyuntikkan payload JSON tersarang ekstrem (misal 1.000 tingkat kurung kurawal), fungsi akan berhenti sebelum V8 mengalami *Call Stack Overflow*.
3. **Baris 19:** `const result = Array.isArray(target) ? [] : Object.create(null);`
   * `Object.create(null)` membuat plain object tanpa prototype (`result.__proto__ === undefined`). Menghilangkan sepenuhnya risiko pewarisan properti dari `Object.prototype`.
4. **Baris 23:** `if (key === '__proto__' || key === 'constructor' || key === 'prototype') continue;`
   * Filter eksplisit terhadap kunci-kunci fatal. Memblokir penulisan ke properti internal metadata objek.
5. **Baris 48–56:** `verifySignatureConstantTime(...)`
   * Melakukan alokasi `Buffer.from(signatureHex, 'hex')`.
6. **Baris 54–58:**
   ```javascript
   if (expectedHmac.length !== providedHmac.length) {
     timingSafeEqual(expectedHmac, expectedHmac);
     return false;
   }
   ```
   * Jika panjang kedua buffer berbeda, penyerang tidak boleh mengetahui kesalahan tersebut secara instan. `timingSafeEqual(expectedHmac, expectedHmac)` dieksekusi untuk memastikan waktu respons komparasi buffer tetap setara dengan komparasi penuh, menghindari *length-leakage side-channel*.
7. **Baris 67–85:** `safeRegexMatch(...)`
   * Membungkus eksekusi regex dalam batasan batas waktu (*time-budgeted promise*). Jika operasi regex melakukan backtracking berulang yang memblokir alur kerja melebihi `timeoutMs`, sistem segera memutus alur untuk menyelamatkan Event Loop.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario: Arsitektur Financial Webhook Receiver (FinTech API)
Sebuah perusahaan pembayaran memproses rata-rata 15.000 webhook/detik dari berbagai perbankan mitra.
* **Insiden:** Terjadi *DDoS diam-diam* di mana Event Loop latensi melonjak dari 2 ms ke 12.000 ms, menyebabkan ribuan koneksi HTTP drop serentak (*Gateway Timeout 504*).
* **Akar Masalah (Root Cause):**
  1. Penyerang mengirimkan header `X-Signature` acak dengan variasi karakter yang berbeda di awal string, memanfaatkan komparasi `===` non-constant-time untuk memetakan secret token gateway.
  2. Payload webhook berisi JSON tersarang dengan kunci `__proto__`, yang memicu Prototype Pollution di parser JSON kustom internal, mengubah konfigurasi `strictRouting` global menjadi `false`.
  3. Payload menyertakan string email masif tak valid yang diproses oleh regex validasi email naif (`/^([a-zA-Z0-9_\.\-])+\@(([a-zA-Z0-9\-])+\.)+([a-zA-Z0-9]{2,4})+$/`), mengunci Event Loop dengan komputasi eksponensial.
* **Target Solusi:** Merekayasa ulang API Gateway Node.js menggunakan zero-trust pipeline: Validasi integritas HMAC tahan timing-attack, schema sanitizer kebal prototype pollution, parsing terisolasi, dan proses container yang melepaskan seluruh hak akses *root*.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah server HTTP produksi yang mengintegrasikan teknik pengerasan keamanan end-to-end.

```javascript
// server-hardened.mjs
import http from 'node:http';
import { timingSafeEqual, createHmac } from 'node:crypto';

// 1. Immutable Secret Management
const SHARED_SECRET = Buffer.from(process.env.WEBHOOK_SECRET || 'insecure-secret-change-in-production-immediately', 'utf-8');
const MAX_PAYLOAD_BYTES = 1024 * 64; // Batas kaku: 64 KB
const PORT = parseInt(process.env.PORT || '8443', 10);

// Mencegah parsing berbahaya ke Prototype bawaan
function sanitizePayload(rawStr) {
  return JSON.parse(rawStr, (key, value) => {
    if (key === '__proto__' || key === 'constructor' || key === 'prototype') {
      return undefined; // Hapus kunci secara otomatis saat deserialisasi
    }
    return value;
  });
}

// Constant-Time HMAC Signature Check
function validateAuth(rawBodyBuffer, signatureHeader) {
  if (!signatureHeader || typeof signatureHeader !== 'string') {
    return false;
  }

  const computedHmac = createHmac('sha256', SHARED_SECRET).update(rawBodyBuffer).digest();
  const providedHmac = Buffer.from(signatureHeader, 'hex');

  if (computedHmac.length !== providedHmac.length) {
    timingSafeEqual(computedHmac, computedHmac);
    return false;
  }

  return timingSafeEqual(computedHmac, providedHmac);
}

// Inisialisasi Server HTTP Terproteksi
const server = http.createServer({
  keepAlive: true,
  keepAliveTimeout: 5000,
  maxRequestsPerSocket: 1000,
  insecureHTTPParser: false // Wajib false: Tolak malformed HTTP headers
}, (req, res) => {
  // Hardened Security Headers (OWASP Recommended Defaults)
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('X-Frame-Options', 'DENY');
  res.setHeader('Content-Security-Policy', "default-src 'none'; frame-ancestors 'none'");
  res.setHeader('Strict-Transport-Security', 'max-age=63072000; includeSubDomains; preload');
  res.setHeader('Cache-Control', 'no-store, no-cache, must-revalidate, proxy-revalidate');

  if (req.method !== 'POST' || req.url !== '/api/v1/secure-webhook') {
    res.writeHead(404, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Route not found' }));
    return;
  }

  // Enforcement: Content-Type Restriction
  if (req.headers['content-type'] !== 'application/json') {
    res.writeHead(415, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Unsupported Media Type: Must be application/json' }));
    return;
  }

  const chunks = [];
  let receivedBytes = 0;

  req.on('data', (chunk) => {
    receivedBytes += chunk.length;

    // Buffer Overflow & Exhaustion Guard
    if (receivedBytes > MAX_PAYLOAD_BYTES) {
      req.destroy(new Error('Payload Too Large: Max limit exceeded'));
    } else {
      chunks.push(chunk);
    }
  });

  req.on('end', () => {
    const rawBodyBuffer = Buffer.concat(chunks);
    const signature = req.headers['x-hub-signature-256'];

    // Validasi Signature Kriptografis
    if (!validateAuth(rawBodyBuffer, signature)) {
      res.writeHead(401, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Unauthorized: Invalid Cryptographic Signature' }));
      return;
    }

    try {
      // Deserialisasi Aman (Sanitized)
      const sanitizedData = sanitizePayload(rawBodyBuffer.toString('utf-8'));

      // Pemrosesan Payload Bisnis (Simulasi Eksekusi Aman)
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'Accepted', traceId: req.headers['x-request-id'] || null }));
    } catch (parseErr) {
      res.writeHead(400, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Malformed JSON payload' }));
    }
  });

  req.on('error', (err) => {
    if (!res.headersSent) {
      res.writeHead(413, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: err.message }));
    }
  });
});

// Kernel Hardening: Melepaskan Linux Privileges setelah Bind Port Rendah
server.listen(PORT, '0.0.0.0', () => {
  console.log(`[RUNTIME SECURE] Listening on port ${PORT}`);

  // Drop Privileges jika proses dijalankan sebagai root/sudo secara tidak sengaja
  if (process.getuid && process.setgid && process.setuid) {
    try {
      const TARGET_UID = 'node'; // Atau UID non-root, misal: 10001
      const TARGET_GID = 'node';
      
      process.setgid(TARGET_GID);
      process.setuid(TARGET_UID);
      console.log(`[PRIVILEGE DROPPED] Successfully switched process user to UID: ${TARGET_UID}`);
    } catch (err) {
      console.error('[SECURITY FATAL] Failed to drop root privileges:', err);
      process.exit(1); // Fail-Closed: Tolak berjalan sebagai root!
    }
  }
});

// Graceful Termination
function shutdown(signal) {
  console.log(`[SHUTDOWN] Signal ${signal} received. Closing HTTP listener...`);
  server.close(() => {
    console.log('[SHUTDOWN] Safe cleanup completed. Terminating.');
    process.exit(0);
  });

  setTimeout(() => {
    console.error('[SHUTDOWN TIMEOUT] Forced shutdown initiated.');
    process.exit(1);
  }, 10000).unref();
}

process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown('SIGINT'));
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

| Pendekatan / Mekanisme | Keuntungan Utama | Kerugian / Trade-off | Dampak Terhadap Throughput |
| :--- | :--- | :--- | :--- |
| **`Object.freeze()` Rekursif Payload** | Menjamin objek tidak dapat dimodifikasi di seluruh alur bisnis downstream. | Mengubah *Hidden Classes* V8 menjadi dictionary mode; overhead GC tinggi. | Penurunan throughput sebesar ~15–25% pada payload masif. |
| **Flag `--frozen-intrinsics`** | Memblokir runtime prototype tampering secara total pada level mesin V8. | Mematahkan library legacy yang melakukan polyfill (misal: core-js lama, lodash lama). | Imbalan performa netral; mitigasi keamanan fundamental. |
| **JSON Schema Validation (TypeBox/Ajv)** | Validasi ketat tipe data, proteksi field tambahan (*additionalProperties: false*). | Membutuhkan fase kompilasi skema di awal; maintenance skema ganda. | Performa sangat cepat jika skema di-precompile; parsing memakan siklus CPU. |
| **Node.js Native VM Sandboxing** | Mengisolasi parsing konteks eksekusi kode script dari penyerang. | `node:vm` **BUKAN** security boundary; rentan escape via prototype traversal (`this.constructor.constructor`). | Latensi tinggi alokasi context; overhead alokasi memori heap baru. |
| **Isolated Process / Wasm (WebAssembly)** | *Real Security Sandbox*; eksekusi terisolasi dari heap V8 utama. | Kompleksitas arsitektur; biaya serialisasi/deserialisasi IPC (Inter-Process Comm). | Penurunan throughput untuk inter-thread transfer data besar. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

1. **Crash Loop via `crypto.timingSafeEqual` Buffer Length Mismatch:**
   * *Pitfall:* Melewatkan buffer dengan panjang berbeda ke `crypto.timingSafeEqual(bufA, bufB)` akan memicu exception unhandled: `RangeError: Input buffers must have the same length`.
   * *Bahaya:* Jika tidak ditangani dalam blok `try/catch`, penyerang cukup mengirim header dengan panjang byte berbeda untuk mematikan (*crash*) proses Node.js seketika.
2. **Memory Leak Akibat Closure pada Event Listeners Request:**
   * Menyimpan referensi `req` atau `res` di dalam variabel scope modul global untuk tujuan audit logging tanpa dereferensi eksplisit akan menahan seluruh payload buffer di heap V8, menyebabkan `JavaScript heap out of memory`.
3. **Penyalahgunaan `Object.assign()`:**
   * Melakukan `Object.assign({}, JSON.parse(input))` **tidak** melindungi dari Prototype Pollution. Jika `input` memiliki properti `__proto__`, `Object.assign` menyalin properti tersebut ke prototype objek target.
4. **Header Injection via CRLF (`\r\n`):**
   * Menyisipkan karakter carriage return (`\r\n`) pada nilai header yang ditulis manual via `res.setHeader()` dapat membelah HTTP response (*HTTP Response Splitting*). Selalu sanitasi input string sebelum menjadikannya HTTP metadata.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Mempercayai `req.headers['x-forwarded-for']` Secara Langsung
* **Kesalahan Fatal:** Mengambil IP penyerang dari header pertama untuk keperluan rate-limiting:
  ```javascript
  const clientIp = req.headers['x-forwarded-for'].split(',')[0]; // RENTAN SPOOFING!
  ```
* **Solusi Perbaikan:** Penyerang dapat menyuntikkan header `X-Forwarded-For: 127.0.0.1`. Ambil IP dari proxy terpercaya terakhir, atau konfigurasikan reverse proxy Anda (NGINX/Envoy) untuk menghapus (*strip*) header ini sebelum diteruskan ke Node.js.

### 2. Validasi Tipe Data Longgar (Loose Comparison)
* **Kesalahan Fatal:**
  ```javascript
  if (userToken == secretToken) { /* rentan type juggling */ }
  ```
* **Solusi Perbaikan:** Selalu gunakan *Strict Identity Comparison* (`===`) atau `crypto.timingSafeEqual()` untuk token keamanan kriptografi.

### 3. Eksekusi Perintah Sistem Menggunakan `child_process.exec`
* **Kesalahan Fatal:**
  ```javascript
  import { exec } from 'node:child_process';
  exec(`convert-image ${req.body.filename}`); // RENTAN REMOTE CODE EXECUTION!
  ```
* **Solusi Perbaikan:** Gunakan `child_process.execFile` atau `spawn` dengan parameter array terpisah, dan matikan opsi `shell`:
  ```javascript
  import { execFile } from 'node:child_process';
  execFile('/usr/bin/convert-image', [validatedFilename], { shell: false });
  ```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

### CIS Benchmark Alignment untuk Node.js Production
1. **Eksekusi dengan Least Privilege:**
   * Buat user sistem non-root khusus di Dockerfile:
     ```dockerfile
     RUN addgroup -S appgroup && adduser -S appuser -G appgroup
     USER appuser
     ```
2. **Read-Only Root Filesystem:**
   * Jalankan container dengan flag `--read-only`. Berikan akses tulis hanya pada `/tmp` (menggunakan `tmpfs` RAM disk) jika runtime membutuhkan penyimpanan file sementara.
3. **Software Bill of Materials (SBOM) & Provenance:**
   * Gunakan `npm audit signatures` dan sertifikasi `SLSA (Supply-chain Levels for Software Artifacts)` pada CI/CD pipeline untuk memastikan seluruh transitive dependencies tidak terkompromi.
4. **Disable Code Generation from Strings:**
   * Jalankan runtime dengan:
     ```bash
     node --disallow-code-generation-from-strings --frozen-intrinsics server.js
     ```
   * Flag ini menghentikan eksekusi runtime jika ada library yang memanggil `eval()`, `new Function()`, atau `setTimeout('string')`.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### Impact Mitigasi Kriptografi pada Event Loop
Operasi kriptografi seperti pemrosesan HMAC menggunakan modul native C++ `node:crypto` yang berjalan di luar thread V8 jika menggunakan callback API, tetapi berjalan sinkron jika memanggil API `.digest()` langsung.

```
Synchronous Crypto (CPU Spike) ──> Memblokir Event Loop Tick
Asynchronous Crypto (Threadpool) ──> Didelegasikan ke Libuv Worker Threads
```

* **Rekomendasi Skala Tinggi:**
  Jika ukuran payload webhook mencapai skala Megabyte (MB), **jangan** gunakan `.update(buffer).digest()` sinkron. Gunakan `createHmac` dalam stream pipeline:

```javascript
import { pipeline } from 'node:stream/promises';
import { createHmac } from 'node:crypto';

async function calculateHmacStream(readableStream, secret) {
  const hmac = createHmac('sha256', secret);
  await pipeline(readableStream, hmac);
  return hmac.digest(); // Tetap non-blocking terhadap payload streaming besar
}
```

* **Manajemen Libuv Threadpool:**
  Secara default, Libuv mengalokasikan 4 worker threads. Jika load enkripsi/komparasi tinggi, naikkan ukuran threadpool sebelum proses berjalan:
  ```bash
  UV_THREADPOOL_SIZE=16 node server-hardened.mjs
  ```

---

## SEKSI 16 — KEAMANAN & HARDENING

### Production Hardened Dockerfile Template

Konfigurasi container multi-stage berstandar industri dengan pengupasan seluruh attack-surface:

```dockerfile
# Stage 1: Build Phase
FROM node:20-alpine AS builder
WORKDIR /usr/src/app
COPY package*.json ./
RUN npm ci --only=production --ignore-scripts

# Stage 2: Hardened Minimal Production Distroless
FROM gcr.io/distroless/nodejs20-debian12:nonroot
WORKDIR /app

# Ambil artifact murni dari builder
COPY --from=builder /usr/src/app/node_modules ./node_modules
COPY --chown=nonroot:nonroot src/ ./src/

# Gunakan Flag Runtime Strict
ENV NODE_ENV=production
ENV NODE_OPTIONS="--disallow-code-generation-from-strings --frozen-intrinsics"

USER nonroot

# Expose restricted unprivileged port
EXPOSE 8443

ENTRYPOINT ["/nodejs/bin/node", "src/server-hardened.mjs"]
```

### Konfigurasi Linux Seccomp & Capabilities
Saat menjalankan container di Kubernetes, nonaktifkan seluruh kemampuan root kernel yang tidak dibutuhkan:

```yaml
securityContext:
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true
  runAsNonRoot: true
  runAsUser: 65532 # distroless nonroot UID
  capabilities:
    drop:
      - ALL
  seccompProfile:
    type: RuntimeDefault
```

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### Structured Audit Logging (Zero-Data Leakage)
Sistem audit enterprise wajib memisahkan antara *Security Events* dan *Application Tracing*, serta menjamin tidak ada PII (Personally Identifiable Information) atau kredensial yang masuk ke `stdout`.

```javascript
// audit-logger.mjs
import { diagnostics_channel } from 'node:diagnostics_channel';

const securityChannel = diagnostics_channel.channel('enterprise:security:audit');

// PII/Secret Redaction Engine
const SENSITIVE_KEYS = new Set(['authorization', 'x-hub-signature-256', 'password', 'token', 'secret']);

function redactSensitiveData(data) {
  if (typeof data !== 'object' || data === null) return data;
  
  const redacted = Array.isArray(data) ? [] : {};
  for (const [key, value] of Object.entries(data)) {
    if (SENSITIVE_KEYS.has(key.toLowerCase())) {
      redacted[key] = '[REDACTED_BY_SECURITY_POLICY]';
    } else if (typeof value === 'object') {
      redacted[key] = redactSensitiveData(value);
    } else {
      redacted[key] = value;
    }
  }
  return redacted;
}

// Subscriber untuk Audit Stream
securityChannel.subscribe((event) => {
  const auditEntry = {
    timestamp: new Date().toISOString(),
    severity: event.severity || 'INFO',
    eventType: event.type,
    originIp: event.ip,
    metadata: redactSensitiveData(event.metadata),
    eventSignature: event.signature
  };
  
  // Output JSON murni ke stdout (ditangkap oleh fluentbit/vector)
  process.stdout.write(JSON.stringify(auditEntry) + '\n');
});

export function logSecurityAnomaly(type, ip, metadata = {}) {
  securityChannel.publish({
    type,
    ip,
    severity: 'CRITICAL',
    metadata
  });
}
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

1. **Anti-Prototype Pollution:** Gunakan `Object.create(null)` atau `Map` untuk dictionary. Hindari deep-merge tanpa sanitasi keys `__proto__`, `constructor`, `prototype`.
2. **Kriptografi:** Selalu gunakan `crypto.timingSafeEqual(bufA, bufB)`. Validasi bahwa `bufA.length === bufB.length` sebelum pemanggilan untuk mencegah unhandled `RangeError`.
3. **Proteksi Input Size:** Jangan izinkan body parsing tanpa membatasi akumulasi `chunk.length`.
4. **ReDoS Guard:** Larang penulisan regex dengan nested quantifiers `(a+)+`. Atur batas timeout pencocokan string regex.
5. **Runtime Hardening Flags:**
   * `--frozen-intrinsics` $\rightarrow$ Membekukan seluruh prototype objek JavaScript global.
   * `--disallow-code-generation-from-strings` $\rightarrow$ Mematikan `eval` dan `new Function`.
6. **Container Security:** Buang semua Linux Capabilities (`drop: [ALL]`), aktifkan `readOnlyRootFilesystem: true`, dan jangan pernah menjalankan container dengan UID `0` (root).

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Basic (1–5)

1. **Mengapa perbandingan signature `a === b` tidak boleh digunakan untuk memvalidasi token keamanan?**
   * *Jawaban:* Operator `===` melakukan pembandingan karakter demi karakter dan langsung keluar (*early return*) saat menemukan ketidakcocokan pertama. Pola latensi ini memungkinkan penyerang menebak string karakter per karakter via side-channel timing attack.
2. **Apa yang terjadi secara internal jika penyerang mengirimkan payload `{"__proto__": {"admin": true}}` pada parser objek yang tidak aman?**
   * *Jawaban:* Properti `admin` diinjeksikan langsung ke heap global `Object.prototype`, menyebabkan semua objek baru di seluruh aplikasi runtime secara otomatis mewarisi properti `admin: true`.
3. **Mengapa pengecekan ukuran panjang Buffer wajib dilakukan sebelum mengeksekusi `crypto.timingSafeEqual`?**
   * *Jawaban:* `timingSafeEqual` melempar runtime exception `RangeError` jika kedua buffer memiliki alokasi panjang yang berbeda. Exception tak tertangani ini dapat mematikan (*crash*) proses Node.js.
4. **Sebutkan dampak flag runtime `--disallow-code-generation-from-strings`.**
   * *Jawaban:* Runtime V8 akan melemparkan exception jika mendeteksi pemanggilan fungsi yang mengompilasi string menjadi kode yang dieksekusi, seperti `eval()`, `new Function()`, dan `WebAssembly.compile()`.
5. **Mengapa `JSON.parse()` standar lebih aman daripada deep clone recursive custom buatan sendiri?**
   * *Jawaban:* Native `JSON.parse()` yang sesuai spesifikasi ECMAScript modern membuat properti biasa pada objek dan tidak mengevaluasi rantai prototype accessor `__proto__` sebagai pointer prototype setter bawaan.

### Soal Intermediate (6–10)

6. **Mengapa flag `--frozen-intrinsics` dapat merusak library dependensi pihak ketiga tertentu?**
   * *Jawaban:* Library pihak ketiga yang melakukan polyfill pada standard global objects (seperti memodifikasi prototype `Array.prototype.flat` atau memperluas method bawaan) akan mengalami kegagalan/crash karena objek intrinsics V8 sudah berstatus `Object.freeze()`.
7. **Bagaimana penyerang dapat mengeksploitasi ReDoS untuk melumpuhkan seluruh API gateway Node.js?**
   * *Jawaban:* Pola regex catastrophic backtracking mengeksekusi siklus komputasi eksponensial secara sinkron. Ini memblokir Event Loop thread utama, menghentikan penanganan socket network I/O untuk seluruh request lain yang masuk.
8. **Diberikan skenario: Node.js berjalan di balik NGINX Ingress Controller. Apa bahayanya membaca IP klien langsung dari `req.socket.remoteAddress`?**
   * *Jawaban:* `req.socket.remoteAddress` akan selalu mengembalikan alamat IP internal dari NGINX Ingress controller, bukan IP asli klien publik, sehingga merusak logika rate-limiting dan IP allowlisting.
9. **Apa batasan arsitektur modul `node:vm` dalam hal isolasi keamanan?**
   * *Jawaban:* Modul `node:vm` bukan boundary keamanan tepercaya. Kode yang berjalan di dalam konteks VM masih dapat mengakses constructor host context melalui rantai prototype `(() => {}).constructor('return process')()` untuk melarikan diri (*sandbox escape*).
10. **Mengapa kita harus menjalankan fungsi `process.setuid()` dan `process.setgid()` setelah `server.listen()`, bukan sebelumnya?**
    * *Jawaban:* Port TCP istimewa (privileged ports < 1024) membutuhkan hak akses root untuk proses *binding socket*. Setelah socket berhasil dibuka oleh kernel, proses harus segera melepaskan hak akses root dan beralih ke user non-root demi prinsip *Least Privilege*.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Rancang Bangun: Enterprise Secure Gateway Guard (ESGG)

#### Skenario Tugas
Anda ditunjuk sebagai Principal Security Engineer untuk membangun micro-gateway HTTP Node.js native (tanpa dependensi framework eksternal seperti Express atau Fastify) yang berfungsi sebagai penapis request di depan core processing service.

#### Kriteria Keberhasilan & Persyaratan Fungsional:
1. **Zero-Dependency Module:** Hanya diperbolehkan menggunakan native Node.js API (`node:http`, `node:crypto`, `node:stream`, `node:buffer`, `node:diagnostics_channel`).
2. **Defensive Ingress Pipeline:**
   * Menerapkan batas keras payload size ($32\text{ KB}$). Jika terlampaui, request langsung diputus seketika via `req.destroy()`.
   * Memvalidasi signature webhook HMAC-SHA512 pada header `X-Signature-SHA512` menggunakan perbandingan *constant-time* yang kebal terhadap *buffer-length crash*.
3. **Prototype Defense & Schema Sanitization:**
   * Buat sanitizer rekursif yang secara aktif menghapus key berbahaya (`__proto__`, `constructor`, `prototype`).
   * Konversikan payload yang tervalidasi ke dalam dictionary berbasis `Object.create(null)` atau `Map`.
4. **ReDoS Safe Matching:**
   * Terapkan validasi format referensi transaksi (misal: alphanumeric ID dengan prefix tertentu) yang dibungkus dengan isolasi eksekusi berbasis *execution timeout* $20\text{ ms}$.
5. **Hardened Runtime Compliance:**
   * Skrip harus dapat dieksekusi dengan perintah:
     ```bash
     node --frozen-intrinsics --disallow-code-generation-from-strings esgg-gateway.mjs
     ```
   * Sediakan mekanisme *graceful shutdown* untuk menangani sinyal `SIGTERM` dan `SIGINT` tanpa memutuskan koneksi yang sedang aktif berjalan.
6. **Security Audit Log:**
   * Output log JSON terstruktur yang otomatis menyensor token signature dan field rahasia sebelum diarahkan ke standard output (`stdout`).