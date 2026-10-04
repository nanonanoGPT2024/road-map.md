# Kurikulum Rekayasa Perangkat Lunak Enterprise: JavaScript Runtime & V8 Engine
## BAB 10: Enterprise Security Hardening & Production System Design
### Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Principal Engineer/Staff Engineer diharapkan memiliki kapabilitas terukur untuk:
- **Menganalisis & Memitigasi Kerentanan Runtime Tingkat Rendah:** Mengidentifikasi dan merekayasa mitigasi terhadap *Prototype Pollution* (Client/Server-side), *Regular Expression Denial of Service* (ReDoS) pada level V8 NFA engine, dan *Timing Attacks* pada verifikasi kriptografi.
- **Mengimplementasikan Arsitektur Sandboxing & Process Isolation:** Mengisolasi eksekusi kode dinamis yang tidak tepercaya (*untrusted code execution*) menggunakan *V8 Isolates* (`isolated-vm`), WebAssembly sandboxing, dan Node.js Core Permission Model (`--permission`).
- **Membangun Pertahanan Rantai Pasok (*Supply Chain Defense*):** Mendesain arsitektur *runtime integrity verification* dan *dynamic policy enforcement* untuk memproteksi dependency runtime dari serangan *zero-day supply-chain injection*.
- **Mengembangkan Zero-Trust Micro-Architecture Berbasis Node.js:** Mengonfigurasi mTLS end-to-end dengan *ephemeral key rotation*, zero-copy memory scrubbing untuk data sensitif, dan proteksi memori V8 heap terhadap *core dump exfiltration*.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:
- **Arsitektur Internal V8:** Siklus kompilasi Ignition & TurboFan, *hidden classes* (*Shape/Map*), *inline caching* (IC), dan struktur heap V8 (New Space, Old Pointer Space, Old Data Space).
- **Node.js Internals:** Libuv thread pool, integrasi OpenSSL C++ bindings, I/O non-blocking polling mechanics, serta siklus hidup Event Loop.
- **Kriptografi Terapan:** Asymmetric encryption (RSA, ECDSA), Symmetric ciphers (AES-GCM, ChaCha20-Poly1305), Hash Message Authentication Codes (HMAC), PKI (*Public Key Infrastructure*), dan X.509 certificate chains.
- **Tools:** Node.js v20+ LTS, Linux Kernel Security Context (seccomp, namespaces, cgroups), OpenSSL 3.x CLI, GDB/LLDB untuk inspeksi memori C++ Addons.

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 V8 Heap Mutation & Prototype Pollution Mechanics

Di dalam engine V8, setiap objek JavaScript direpresentasikan oleh struktur C++ internal yang disebut `JSObject`. Objek ini memiliki referensi ke `Map` (atau *Shape*) yang mendefinisikan layout memori propertinya, serta referensi ke *prototype object*-nya (`__proto__`).

```
+-------------------------------------------------------------------+
|                            JSObject                               |
|  +--------------------+---------------------+------------------+  |
|  |     Shape/Map      |   Elements (Array)  | Properties (Dict)|  |
|  +---------+----------+---------------------+------------------+  |
|            |                                                      |
|            v                                                      |
|  +--------------------+                                           |
|  |  Prototype Pointer | --------> Points to Object.prototype      |
|  +--------------------+                                           |
+-------------------------------------------------------------------+
                                            |
                                            v
+-------------------------------------------------------------------+
|                        Object.prototype                           |
|  +--------------------+---------------------+------------------+  |
|  | toString(), etc.   | Polluted Properties | isPrototypeOf()  |  |
|  +--------------------+---------------------+------------------+  |
+-------------------------------------------------------------------+
```

Ketika operasi *recursive merge* atau *deep path assignment* dijalankan tanpa sanitasi terhadap key properti (`__proto__`, `constructor`, `prototype`), penyerang dapat menyuntikkan properti langsung ke `Object.prototype`. Karena hampir seluruh objek JavaScript mewarisi `Object.prototype`, mutasi ini berdampak global:
1. **Hidden Class Invalidation:** Penambahan properti pada `Object.prototype` secara instan mendeprecate ribuan *Shapes* yang telah dioptimasi oleh TurboFan, memaksa V8 melakukan de-optimisasi massal (*deopt storms*) dan jatuh ke mode *megamorphic dictionary lookup*.
2. **Execution Hijacking / RCE:** Jika aplikasi mengandalkan konfigurasi opsional (misal: `options.shell`, `options.env`, atau sanitasi flags), properti yang terpolusi akan mengaburkan default logic (`undefined` menjadi terisi) yang sering kali berujung pada eksekusi perintah berbahaya (*Remote Code Execution* melalui `child_process.exec/spawn`).

#### 3.2 Engine V8 RegExp Backtracking Mechanics (ReDoS)

V8 menggunakan engine *Irregexp* untuk parsing regular expression. Irregexp mengompilasi regex menjadi bytecode atau native machine code menggunakan *Backtracking Non-deterministic Finite Automaton* (NFA).

Ketika menghadapi *nested quantifier* seperti `^(a+)+$`:
- String masukan `aaaaaX` akan dievaluasi.
- Karakter `X` gagal dicocokkan di akhir string.
- Engine NFA akan mencoba setiap permutasi pembagian karakter `a` di antara grup-grup luar dan dalam.
- Kompleksitas waktu komputasi melonjak secara eksponensial: $\mathcal{O}(2^n)$.
- Selama komputasi eksponensial ini berlangsung, thread utama V8 terblokir total, menghentikan penanganan event loop libuv, dan mematikan throughput HTTP server secara instan (*Denial of Service*).

#### 3.3 Node.js Permission Model & Sandbox Boundaries

Node.js v20+ mengintegrasikan model perizinan formal (*Permission Model*) langsung pada level C++ runtime bindings. Fitur ini memotong akses eksekusi langsung ke syscall kernel Linux untuk:
- Pembacaan/Penulisan Sistem Berkas (`--allow-fs-read`, `--allow-fs-write`)
- Spawning Process (`--allow-child-process`)
- Worker Threads (`--allow-worker`)

Model ini bekerja dengan cara memvalidasi token permission pada C++ layer sebelum mengeksekusi operasi libuv (`uv_fs_*`, `uv_spawn`). Namun, model ini **bukan** pengganti container security (seperti AppArmor/Seccomp), melainkan *application-level control plane* yang membatasi *blast radius* dari ketergantungan pihak ketiga (*compromised dependencies*).

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional | Enterprise-Grade Hardened Approach |
| :--- | :--- | :--- |
| **Mitigasi Prototype Pollution** | Blokir kata kunci `__proto__` menggunakan regex sebelum parse. | Deep validation berbasis JSON Schema via compile-time codegen, penggunaan `Object.create(null)`, freezing intrinsic primitives via `--disable-proto=delete`, dan sanitasi rekursif non-enumerable. |
| **Pencegahan ReDoS** | Blacklisting pola regex secara manual. | Eksekusi regex dengan batas deadline komputasi (*timeout-bounded Irregexp*), validasi AST regex static analysis via lint-rules, atau offloading regex kompleks ke engine berbasis Linear Automata (misal: RE2/Rust bindings via WebAssembly). |
| **Eksekusi Kode Pihak Ketiga** | Node.js native `vm` module (berbahaya, rentan context escape). | Isolasi proses berbasis V8 Isolates via C++ bindings (`isolated-vm`) dengan batasan waktu CPU mikrodetik dan alokasi memori fisik strictly-bounded. |
| **Verifikasi Kriptografis** | Operator `===` standar untuk komparasi token/hash. | `crypto.timingSafeEqual` yang dipadukan dengan alokasi buffer beralamat tetap untuk memitigasi *side-channel microarchitectural cache-timing attacks*. |
| **Manajemen Memori Kredensial** | String JavaScript standar (dikelola oleh V8 Garbage Collector). | Native `Buffer` alokasi khusus dengan teknik *zero-fill overwriting* eksplisit setelah selesai digunakan untuk mencegah kebocoran melalui Heap Dump / Core Dump file. |

---

### 5. How (Workflow Detail)

Untuk menerapkan arsitektur *runtime hardening* penuh pada gateway microservice Node.js berdaya tahan tinggi, alur eksekusi paket data mengikuti rantai pertahanan berlapis (*Defense-in-Depth*):

```
[ Request Masuk: Ingress TLS 1.3 ]
               │
               ▼
[ Layer 1: Payload Deserialization & Prototype Stripping ]
   ├── Blokir key berbahaya: '__proto__', 'constructor', 'prototype'
   └── Skema Parsing Ketat (Ajv dengan additionalProperties: false)
               │
               ▼
[ Layer 2: Sanitasi Input & Non-backtracking ReDoS Check ]
   └── RE2 Engine (DFA) / Regex AST Complexity Analyzer
               │
               ▼
[ Layer 3: Kriptografi Konstan & Verifikasi Identitas ]
   ├── Constant-time signature verification (crypto.timingSafeEqual)
   └── Validasi sertifikat mTLS (X.509 SAN parsing)
               │
               ▼
[ Layer 4: Sandboxed Dynamic Rule Engine (V8 Isolates) ]
   ├── isolated-vm execution context (Memory Limit: 16MB, Timeout: 15ms)
   └── Zero Node.js primitives exposed
               │
               ▼
[ Layer 5: Ephemeral Memory Scrubbing & Egress Dispatch ]
   ├── Scrubbing buffer kunci kriptografi (Zero-fill buffer.fill(0))
   └── Request diteruskan ke backend via internal mTLS
```

1. **Ingress Invalidation:** Payload JSON diurai menggunakan parser aman yang langsung mengabaikan atau menolak keys prototype sebelum instance objek dicetak.
2. **Schema Compilation:** Validator berbasis skema tertutup memvalidasi format data dan menghapus field yang tidak didefinisikan secara eksplisit.
3. **Execution Sandbox:** Jika payload memerlukan evaluasi script dinamis (misalnya aturan bisnis kustom atau rule routing), konteks dialihkan ke V8 Isolate independen. V8 Isolate ini tidak berbagi heap ataupun global context dengan Node.js event loop.
4. **Scrubbing Phase:** Setelah operasi cryptographic selesai, seluruh memory segment yang menampung sensitive plain-text token/kunci segera di-overwrite secara byte-by-byte (`buffer.fill(0)`).

---

### 6. Analogy & Diagram ASCII

#### Analogi: Arsitektur Keamanan Ruang Bersih (Cleanroom Isolation)
Bayangkan sebuah bank sentral:
- **Pendekatan Naif:** Nasabah membawa formulir dan dokumen langsung ke ruang brankas utama. Jika formulir mengandung racun kontak (Prototype Pollution), seluruh sistem brankas terkontaminasi.
- **Pendekatan Enterprise:** Nasabah meletakkan formulir di balik bilik kaca tertutup rapat (*V8 Isolate Sandbox*). Dokumen diperiksa melalui pemindai sinar-X (*Safe Schema Validation*). Jika dokumen perlu dihitung, kalkulator khusus digunakan tanpa akses ke sistem inventaris bank (*Process Permissions*). Setelah transaksi selesai, meja kaca disemprot disinfektan sampai tak bersisa (*Memory Zero-Filling*).

```
                      ARSITEKTUR V8 ISOLATE SANDBOXING
                      
+--------------------------------------------------------------------+
|  Node.js Main Process Runtime                                      |
|                                                                    |
|  +--------------------------------------------------------------+  |
|  | Event Loop (Libuv) & V8 Main Isolate                         |  |
|  |                                                              |  |
|  |  [HTTP Ingress] ---> [Ajv Parser] ---> [Payload Verifier]    |  |
|  |                                                │             |  |
|  +------------------------------------------------┼-------------+  |
+---------------------------------------------------┼----------------+
                                                    │ Snapshot Memory
                                                    │ Transferred via
                                                    │ ArrayBuffer
                                                    ▼
+--------------------------------------------------------------------+
|  Isolated-VM (Dedicated OS Thread & Separate V8 Heap)              |
|                                                                    |
|  +--------------------------------------------------------------+  |
|  | Memory Boundary (Max: 16MB)                                  |  |
|  | +---------------------------------------------------------+  |  |
|  | | Untrusted Script Context                                |  |  |
|  | | (No require, no process, no fetch, execution time <= 10ms)|  |
|  | +---------------------------------------------------------+  |  |
|  |                                                              |  |
|  | [Termination Watchdog Thread] ---> Force Interruption (OOM)  |  |
|  +--------------------------------------------------------------+  |
+--------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Constant-Time HMAC Signature Verification & Prototype Shield

```typescript
// simple-security-primitives.ts
import { createHmac, timingSafeEqual } from 'node:crypto';

/**
 * Mencegah Prototype Pollution secara deterministik pada objek masukan.
 */
export function sanitizeObject<T extends Record<string, any>>(target: T): T {
  const clean = Object.create(null);
  
  for (const [key, value] of Object.entries(target)) {
    // Drop prototype pollution vectors eksplisit
    if (key === '__proto__' || key === 'constructor' || key === 'prototype') {
      continue;
    }
    
    if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
      clean[key] = sanitizeObject(value);
    } else {
      clean[key] = value;
    }
  }
  
  return clean as T;
}

/**
 * Memverifikasi tanda tangan payload dengan proteksi side-channel timing attack.
 */
export function verifySignatureSafe(
  payload: string,
  incomingSignatureHex: string,
  secretKey: string
): boolean {
  const hmac = createHmac('sha256', secretKey);
  hmac.update(payload);
  const expectedSignatureHex = hmac.digest('hex');

  const incomingBuffer = Buffer.from(incomingSignatureHex, 'utf-8');
  const expectedBuffer = Buffer.from(expectedSignatureHex, 'utf-8');

  // Panjang byte harus sama persis sebelum masuk ke timingSafeEqual
  // untuk mencegah leakage panjang buffer internal
  if (incomingBuffer.length !== expectedBuffer.length) {
    return false;
  }

  return timingSafeEqual(incomingBuffer, expectedBuffer);
}
```

#### 7.2 Practical Example: Enterprise Hardened Ingress Pipeline

Contoh implementasi pipeline HTTP handler Node.js native dengan integrasi:
1. Skema parsing anti-pollution.
2. Sandboxing eksekusi script dinamis menggunakan `isolated-vm`.
3. Scrubbing memory buffer sensitif.

```typescript
// enterprise-hardened-server.ts
import createServer, { IncomingMessage, ServerResponse } from 'node:http';
import ivm from 'isolated-vm';
import { Buffer } from 'node:buffer';

interface SecureComputePayload {
  ruleSource: string;
  contextData: Record<string, unknown>;
}

class HardenedExecutionService {
  private isolatePool: ivm.Isolate;

  constructor() {
    // Inisialisasi Isolate dengan limitasi ketat
    this.isolatePool = new ivm.Isolate({ memoryLimit: 16 }); // Batas absolut 16MB
  }

  public async executeUntrustedRule(
    untrustedJS: string,
    sandboxData: Record<string, unknown>
  ): Promise<unknown> {
    const context = await this.isolatePool.createContext();
    const jail = context.global;

    // Set read-only global namespace
    await jail.set('global', jail.derefInto());

    // Inject data kontekstual yang sudah dibersihkan ke Isolate
    const dataCopy = new ivm.ExternalCopy(sandboxData);
    await jail.set('context', dataCopy.copyInto());

    // Compile & Jalankan Script dengan batas waktu CPU ketat
    const script = await this.isolatePool.compileScript(untrustedJS);
    
    try {
      const result = await script.run(context, {
        timeout: 20, // Timeout dalam millisecond (CPU time)
        copy: true,   // Copy hasil kembali ke main heap, lepas referensi memory
      });
      return result;
    } finally {
      // Reclaim memory context segera
      context.release();
    }
  }
}

const secureEngine = new HardenedExecutionService();

function parseSecureJson(rawBody: string): any {
  return JSON.parse(rawBody, (key, value) => {
    // Sanitasi native JSON parser level
    if (key === '__proto__' || key === 'constructor' || key === 'prototype') {
      throw new TypeError(`Malicious property injection detected: [${key}]`);
    }
    return value;
  });
}

function wipeMemory(sensitiveBuffer: Buffer): void {
  sensitiveBuffer.fill(0); // Overwrite memori fisik sebelum garbage collection
}

const server = createServer(async (req: IncomingMessage, res: ServerResponse) => {
  if (req.method !== 'POST' || req.url !== '/api/v1/compute-rule') {
    res.writeHead(404, { 'Content-Type': 'application/json' });
    return res.end(JSON.stringify({ error: 'Not Found' }));
  }

  const chunks: Buffer[] = [];
  let totalBytes = 0;
  const MAX_PAYLOAD = 64 * 1024; // 64 Kilobytes limit

  req.on('data', (chunk: Buffer) => {
    totalBytes += chunk.length;
    if (totalBytes > MAX_PAYLOAD) {
      res.writeHead(413, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Payload Too Large' }));
      req.destroy();
      return;
    }
    chunks.push(chunk);
  });

  req.on('end', async () => {
    const rawBuffer = Buffer.concat(chunks);
    
    try {
      const rawString = rawBuffer.toString('utf-8');
      const payload: SecureComputePayload = parseSecureJson(rawString);

      // Verifikasi integritas tipe dasar
      if (typeof payload.ruleSource !== 'string' || typeof payload.contextData !== 'object') {
        throw new Error('Malformed payload contract');
      }

      // Jalankan user-provided rules di dalam V8 Isolate terisolasi
      const executionResult = await secureEngine.executeUntrustedRule(
        payload.ruleSource,
        payload.contextData
      );

      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ success: true, result: executionResult }));
    } catch (err: any) {
      res.writeHead(400, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Security Exception', message: err.message }));
    } finally {
      // Memory Hygiene: Scrubbing buffer yang menampung payload
      wipeMemory(rawBuffer);
      for (const chunk of chunks) {
        wipeMemory(chunk);
      }
    }
  });
});

server.listen(8443, () => {
  console.log('Zero-Trust Hardened Node.js Listener running on port 8443');
});
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
Platform Core Payment Gateway memproses rata-rata 45.000 transaksi per detik (RPS) pada *peak hours*. Platform ini menyediakan fitur "Dynamic Merchant Routing Rules", di mana merchant tier-1 dapat mengunggah skrip transformasi payload transaksi mini untuk menentukan payment provider lokal dengan latensi terendah.

#### Insiden / Ancaman
Sistem mengalami serangan simultan:
1. **Supply-chain Poisoning:** Salah satu library utilitas dependensi di-hijack, menyuntikkan payload yang mencoba membaca `process.env` (berisi database connection secrets dan KMS private keys) dan memodifikasi `Object.prototype.isAdmin = true`.
2. **ReDoS Attack:** Eksekusi serentak pola regex regex merchant routing yang tidak divalidasi (`^([a-zA-Z0-9]+)*$`) pada invoice data berukuran 30KB yang sengaja divalidasi tidak cocok pada karakter paling akhir. Akibatnya, seluruh 32 Node.js worker event-loops mengalami utilisasi CPU 100%, health-check HTTP gagal, dan cluster Kubernetes melakukan restart massal secara terus menerus (*crash loop cascading failure*).

#### Solusi Arsitektural Enterprise

```
                                ARSITEKTUR SOLUSI
                                
                  +-----------------------------------------+
                  |           Kubernetes Ingress            |
                  +--------------------+--------------------+
                                       |
                   Strict HTTP Parsing & Size Quotas
                                       |
                                       v
         +------------------------------------------------------------+
         |               Hardened Node.js Gateway Pod                 |
         |                                                            |
         |  Runtime Node.js CLI Options:                              |
         |  --permission                                              |
         |  --allow-fs-read=/etc/ssl/certs/                           |
         |  --disable-proto=delete                                    |
         |                                                            |
         |  +------------------------------------------------------+  |
         |  | Node.js Main Event Loop Engine                       |  |
         |  |                                                      |  |
         |  |  1. Ajv JSON Parser (Strict Schema Enforcement)      |  |
         |  |                                                      |  |
         |  |  2. Re2 Engine (WebAssembly)                         |  |
         |  |     Deterministic Finite Automata Regex Processing   |  |
         |  |                                                      |  |
         |  |  3. Isolated-VM Sandbox Supervisor                   |  |
         |  |     +---------------------------------------------+  |  |
         |  |     | Dedicated Isolate Context                   |  |  |
         |  |     | Dynamic Merchant Code (Timeout: 10ms)       |  |  |
         |  |     | CPU Time strictly controlled by OS Thread   |  |  |
         |  |     +---------------------------------------------+  |  |
         |  +------------------------------------------------------+  |
         +------------------------------------------------------------+
```

1. **V8 Intrinsic Lockdown:** Runtime container Node.js di-start dengan flag flag:
   `node --disable-proto=delete --permission --allow-fs-read=/etc/ssl/certs/ --no-addons server.js`
   Hal ini mematikan akses ke `__proto__` secara menyeluruh pada level native V8 Engine dan memblokir akses filesystem di luar sertifikat SSL.
2. **Deterministic Regex Engine:** Mengganti engine bawaan V8 Irregexp pada validasi rule merchant dengan modul binding **RE2** (berbasis algoritma Thompson/DFA). Karakteristik Re2 menjamin waktu eksekusi linear terhadap ukuran input $\mathcal{O}(n)$, secara fundamental menghapus kerentanan ReDoS.
3. **Multi-Tenant Isolate Pool:** Skrip transformasi merchant dipindahkan sepenuhnya dari runtime utama ke dalam managed pool `isolated-vm`. Setiap isolasi dialokasikan CPU thread mandiri dengan limit eksekusi 10ms dan pembatasan memori 8MB per tenant. Jika skrip merchant mencoba melakukan loop tak hingga, Isolate Watchdog thread langsung memusnahkan (*dispose*) konteks tersebut tanpa memengaruhi loop utama server.

---

### 9. Trade-offs

| Pendekatan / Teknologi | Manfaat Utama | Latency Overhead | Memory Footprint Overhead | Kompleksitas Engineering |
| :--- | :--- | :--- | :--- | :--- |
| **`isolated-vm` Sandbox** | Isolasi mutlak; eksekusi untrusted code aman dari context escape. | +2.0ms s.d. +5.5ms per eksekusi (setup context & memory crossing). | +10MB hingga +25MB per isolate instance. | Tinggi. Memerlukan sinkronisasi transfer data lewat ArrayBuffer/Copy primitives. |
| **Linear Regex Engine (RE2)** | Kekebalan total dari ReDoS attack ($\mathcal{O}(n)$ linear guarantees). | Mirip V8 pada kasus regex normal, namun 1.2x lebih lambat pada simple string matches. | Sangat rendah (~beberapa KB per compiled instance). | Menengah. Tidak mendukung fitur lanjutan regex seperti *backreferences* dan *lookahead/lookbehind*. |
| **JSON Schema Pre-validation** | Menghentikan Prototype Pollution dan Type Juggling secara instan. | +0.1ms s.d. +0.4ms per request parsing. | +15MB s.d. +40MB di Old Space untuk pre-compiled AJV validation trees. | Rendah ke Menengah. Memerlukan sinkronisasi skema kontraktual data. |
| **Buffer Zero-fill Scrubbing** | Mengeliminasi kebocoran kredensial dari Heap/Core dump exfiltration. | Diabaikan (< 0.01ms per KB buffer). | Netral (0% overhead tambahan). | Rendah. Memerlukan disiplin tinggi dalam blok `finally {}`. |
| **`Object.freeze()` Primitives** | Mencegah modifikasi konfigurasi global atau runtime primitives. | Negatif terhadap optimasi V8 (Hidden class transitions, deoptimizes inline caches). | Sedikit peningkatan jika diterapkan luas pada ribuan objek dinamis. | Rendah. Namun berisiko melempar runtime exceptions jika ada modul yang bergantung pada mutasi. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Menggunakan Module Native `vm` untuk Sandboxing Kode Untrusted
*   **Kesalahan Fatal:** Menganggap modul bawaan Node.js `node:vm` aman untuk mengeksekusi kode user yang tidak tepercaya.
*   **Dampak:** Remote Code Execution (RCE) via Prototype Chain Escape. Kode di dalam `vm` dapat mengakses konstruktor luar melalui `this.constructor.constructor('return process')().mainModule.require('child_process').execSync(...)`.
*   **Troubleshooting & Mitigasi:** Ganti seluruh dependensi `vm.runInContext` dengan `isolated-vm`. Pastikan tidak ada objek native main thread yang di-pass via reference (harus via `ExternalCopy`).

#### 10.2 Asumsi `JSON.parse()` Sepenuhnya Mengamankan Payload
*   **Kesalahan Fatal:** Berpikir bahwa `JSON.parse(str)` default tidak memicu prototype pollution.
*   **Dampak:** Walaupun `JSON.parse` standar tidak memproses accessor `__proto__` sebagai prototype mutator pada beberapa versi ECMAScript baru, ia tetap memetakan key bernama `"__proto__"` sebagai plain own property. Jika objek tersebut digabungkan menggunakan fungsi helper tidak aman (misal: recursive object merge buatan sendiri atau lodash versi rentan), prototype global tetap dapat terpolusi.
*   **Troubleshooting:** Selalu gunakan *reviver function* pada `JSON.parse` untuk membuang field berbahaya atau gunakan utility deep merge yang terlindungi dari properti `__proto__`, `constructor`, dan `prototype`.

#### 10.3 Perbandingan String Kriptografi dengan Operator Equality Tradisional
*   **Kesalahan Fatal:** `if (userToken === serverToken)` atau `if (incomingHmac === calculatedHmac)`.
*   **Dampak:** Mengakibatkan *Timing Attack*. Operator `===` membandingkan string karakter demi karakter dari kiri ke kanan dan langsung berhenti begitu karakter pertama tidak cocok (*early exit*). Penyerang dapat mengukur variasi latensi respon dalam skala mikrodetik untuk menebak token byte per byte.
*   **Troubleshooting:**
    ```typescript
    // BENAR:
    const a = Buffer.from(signatureA);
    const b = Buffer.from(signatureB);
    if (a.length === b.length && crypto.timingSafeEqual(a, b)) { ... }
    ```

#### 10.4 Mengabaikan RegExp Denial of Service dalam Validasi Format
*   **Kesalahan Fatal:** Memvalidasi email, domain, atau slug menggunakan complex regex dengan greedy repeat token tanpa timeouts.
*   **Dampak:** 1 Core CPU tersangkut di looping tak terhingga, event loop starvation, throughput pod drop ke nol.
*   **Troubleshooting:**
    - Audit codebase menggunakan static scanner ReDoS (seperti `@eslint-community/eslint-plugin-regex`).
    - Pasang batas waktu timeout komputasi pada Irregexp (Node.js v12+ mendukung pembatalan via custom flags atau C++ level context).
    - Gunakan RE2 wrapper untuk user-submitted pattern checking.

#### 10.5 Tidak Membersihkan (Zero-fill) Buffer yang Mengandung Kredensial
*   **Kesalahan Fatal:** Mengalokasikan string untuk token dekripsi, lalu membiarkannya dihapus secara alami oleh V8 GC.
*   **Dampak:** String JavaScript bersifat *immutable*. V8 dapat memindahkan string tersebut di berbagai memory space (New Space -> Old Pointer/Data Space) selama fase *Scavenge* dan *Mark-Sweep*. Hal ini meninggalkan jejak plain-text kredensial di puluhan lokasi memori fisik proses yang dapat terbaca saat heap dumping (*post-mortem debugging*) atau melalui kerentanan *Heartbleed-style buffer over-read*.
*   **Troubleshooting:** Simpan plaintext rahasia selalu dalam format `Buffer`. Segera setelah operasi selesai:
    ```typescript
    secretBuffer.fill(0);
    ```

---

### 11. Best Practices (Production Checklist)

Gunakan checklist ini sebagai quality gate pada CI/CD Deployment Pipeline:

- [ ] **Node.js Runtime Hardening Flags Diterapkan:**
  - [ ] `--disable-proto=delete` (Menghapus properti `Object.prototype.__proto__`).
  - [ ] `--permission` diaktifkan dengan whitelisting folder spesifik (`--allow-fs-read`, `--allow-fs-write`).
  - [ ] `--disallow-code-generation-from-strings` (Mencegah `eval()`, `new Function()` dinamis di production).
- [ ] **Dependency & Supply Chain Security:**
  - [ ] Lockfile (`package-lock.json` atau `pnpm-lock.yaml`) menggunakan hash `sha512` integrity check.
  - [ ] Build pipeline menjalankan `npm audit --audit-level=high` dan static SBOM scan (misal: Syft / Trivy).
  - [ ] Menjalankan script instalasi pihak ketiga dinonaktifkan: `npm config set ignore-scripts true`.
- [ ] **Arsitektur Input & Deserialization:**
  - [ ] Semua payload input divalidasi menggunakan skema dengan mode restriksi penuh (`additionalProperties: false`).
  - [ ] Penggunaan modul native `vm` dihapus secara total dari codebase; diganti dengan `isolated-vm` untuk evaluasi dinamis.
- [ ] **Kriptografi & Manajemen Rahasia:**
  - [ ] Komparasi token, digest hash, dan signature wajib menggunakan `crypto.timingSafeEqual`.
  - [ ] Semua private key, token, dan decrypted payload dialokasikan dalam buffer dan dilakukan *zero-filling* (`buffer.fill(0)`) di dalam blok `finally`.
  - [ ] TLS termination mewajibkan minimal TLSv1.3 atau TLSv1.2 dengan cipher suites kuat (ECDHE-ECDSA-AES128-GCM-SHA256 atau sejenis).
- [ ] **Observabilitas & Forensik Keamanan:**
  - [ ] Exception unhandled rejection menangkap detail kesalahan tanpa mengekspos internal stack trace ke response HTTP client.
  - [ ] Node.js Process limits di-set pada level container (cgroups v2: memory.max, pids.max).

---

### 12. Hands-on Practice

Buat dan simpan praktikum ini di direktori: `hands-on/m02/`

#### Struktur Direktori
```
hands-on/m02/
├── package.json
├── tsconfig.json
├── src/
│   ├── app.ts
│   ├── sandbox-runner.ts
│   └── secure-validator.ts
└── test-exploit.ts
```

#### Langkah 1: Inisialisasi Project & Instalasi Dependensi
Jalankan di terminal Anda:
```bash
mkdir -p hands-on/m02/src
cd hands-on/m02
npm init -y
npm install isolated-vm ajv
npm install --save-dev typescript @types/node ts-node
```

Konfigurasi `tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "CommonJS",
    "moduleResolution": "node",
    "outDir": "./dist",
    "rootDir": "./",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true
  }
}
```

#### Langkah 2: Implementasi Secure Sandbox Engine (`src/sandbox-runner.ts`)
```typescript
import ivm from 'isolated-vm';

export class TenantSandbox {
  private isolate: ivm.Isolate;

  constructor() {
    this.isolate = new ivm.Isolate({ memoryLimit: 8 }); // 8 MB limit per worker
  }

  public async runIsolatedTask(code: string, inputPayload: Record<string, unknown>): Promise<unknown> {
    const context = await this.isolate.createContext();
    const jail = context.global;

    await jail.set('global', jail.derefInto());
    const payloadCopy = new ivm.ExternalCopy(inputPayload);
    await jail.set('INPUT_DATA', payloadCopy.copyInto());

    const script = await this.isolate.compileScript(code);

    try {
      const result = await script.run(context, {
        timeout: 15, // Maksimal 15 milidetik CPU time
        copy: true
      });
      return result;
    } finally {
      context.release();
    }
  }
}
```

#### Langkah 3: Implementasi Secure Validator (`src/secure-validator.ts`)
```typescript
import Ajv, { JSONSchemaType } from 'ajv';

export interface ComputeInput {
  script: string;
  data: Record<string, any>;
}

const computeSchema: JSONSchemaType<ComputeInput> = {
  type: 'object',
  properties: {
    script: { type: 'string', maxLength: 1000 },
    data: { type: 'object', additionalProperties: true }
  },
  required: ['script', 'data'],
  additionalProperties: false
};

const ajv = new Ajv({ allErrors: false });
const validate = ajv.compile(computeSchema);

export function validatePayload(payload: unknown): ComputeInput {
  const isValid = validate(payload);
  if (!isValid) {
    throw new Error(`Schema Validation Error: ${JSON.stringify(validate.errors)}`);
  }
  return payload as ComputeInput;
}
```

#### Langkah 4: Core Server Runner (`src/app.ts`)
```typescript
import http from 'node:http';
import { TenantSandbox } from './sandbox-runner';
import { validatePayload } from './secure-validator';

const sandbox = new TenantSandbox();

const server = http.createServer(async (req, res) => {
  if (req.method !== 'POST' || req.url !== '/run') {
    res.writeHead(404).end();
    return;
  }

  const chunks: Buffer[] = [];
  req.on('data', chunk => chunks.push(chunk));
  req.on('end', async () => {
    const completeBuffer = Buffer.concat(chunks);
    try {
      // 1. Safe Parse with Reviver prototype blocker
      const parsed = JSON.parse(completeBuffer.toString('utf-8'), (key, value) => {
        if (key === '__proto__' || key === 'constructor' || key === 'prototype') {
          throw new SecurityError(`Attempted prototype tampering via key: ${key}`);
        }
        return value;
      });

      // 2. Strict Schema Validation
      const validatedInput = validatePayload(parsed);

      // 3. Run in Hardware/Thread isolated V8 Isolate
      const executionResult = await sandbox.runIsolatedTask(
        validatedInput.script,
        validatedInput.data
      );

      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'success', data: executionResult }));
    } catch (err: any) {
      res.writeHead(400, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'denied', reason: err.message }));
    } finally {
      // 4. Scrubbing Memory
      completeBuffer.fill(0);
      for (const ch of chunks) ch.fill(0);
    }
  });
});

class SecurityError extends Error {}

server.listen(3000, () => {
  console.log('[Enterprise Runtime] Listening securely on port 3000');
});
```

#### Langkah 5: Skrip Uji Exploit Penetrasi (`test-exploit.ts`)
```typescript
import http from 'node:http';

function sendExploit(payload: object) {
  const data = JSON.stringify(payload);
  const req = http.request(
    {
      hostname: 'localhost',
      port: 3000,
      path: '/run',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(data),
      },
    },
    res => {
      let body = '';
      res.on('data', d => (body += d));
      res.on('end', () => {
        console.log(`[HTTP ${res.statusCode}] Output: ${body}`);
      });
    }
  );
  req.write(data);
  req.end();
}

console.log('--- TEST 1: Prototype Pollution via JSON Reviver ---');
sendExploit({
  "__proto__": { "polluted": true },
  "script": "return 1;",
  "data": {}
});

setTimeout(() => {
  console.log('\n--- TEST 2: ReDoS / Infinite Loop via Sandboxed Code ---');
  sendExploit({
    "script": "while(true) {}", // Harus diterminasi otomatis oleh watchdog Isolate dalam 15ms
    "data": {}
  });
}, 1000);

setTimeout(() => {
  console.log('\n--- TEST 3: Escaping Sandbox via Context Prototype ---');
  sendExploit({
    "script": "return this.constructor.constructor('return process')().env;",
    "data": {}
  });
}, 2000);

setTimeout(() => {
  console.log('\n--- TEST 4: Valid Operation ---');
  sendExploit({
    "script": "return INPUT_DATA.valA + INPUT_DATA.valB;",
    "data": { "valA": 40, "valB": 2 }
  });
}, 3000);
```

Jalankan server:
```bash
npx ts-node src/app.ts
```
Pada terminal lain, jalankan exploit tester:
```bash
npx ts-node test-exploit.ts
```

Pastikan:
- Test 1 ditolak (`Attempted prototype tampering`).
- Test 2 ditolak dengan timeout exception tanpa memblokir server.
- Test 3 gagal dan tidak dapat menyentuh objek `process`.
- Test 4 berhasil menghasilkan nilai 42.

---

### 13. Exercise

#### Level Easy
Tulis sebuah fungsi TypeScript:
`secureTokenCompare(tokenA: string, tokenB: string): boolean`
Fungsi ini harus mengompensasi perbedaan panjang string masukan tanpa membocorkan informasi panjang string melalui timing execution, lalu memvalidasi isinya secara konstan menggunakan `crypto.timingSafeEqual`.

#### Level Medium
Buat middleware Express/Fastify yang mendeteksi dan menghapus secara rekursif semua parameter yang mengandung karakter regex berbahaya (*high-risk backtracking structures* seperti nested quantifiers `(a+)+`) dari parameter query HTTP sebelum diteruskan ke handler aplikasi downstream.

#### Level Hard
Rancang modul Node.js C++ Addon (menggunakan Node-API / N-API) atau library TypeScript murni yang mengimplementasikan **Zero-Allocation Secure String Container**. Karakter-karakter dalam container tersebut tidak boleh tersimpan sebagai string V8 Engine reguler, melainkan dienkripsi langsung di *off-heap native memory* (`ArrayBuffer` beralamat tetap). Objek harus menyediakan metode `readDecrypted(key: Buffer, callback: (plain: Buffer) => void): void`, di mana `plain` buffer di-wipe bersih seketika setelah callback return.

---

### 14. Challenge

#### Skenario Kasus Produksi
Anda adalah Principal Security Architect di sebuah bank digital tier-1. Ditemukan kerentanan zero-day kritis di ekosistem open-source: sebuah modul logging populer yang digunakan di 85 layanan microservice Node.js Anda memuat vulnerability yang secara dinamis melakukan evaluasi string template di global scope.

Deploying ulang seluruh 85 repositori membutuhkan waktu rilis terkoordinasi selama 48 jam karena audit regulasi perbankan.

#### Tantangan Arsitektural:
Rancang dan implementasikan sebuah *Preload Agent Architecture* (`node --require ./hardened-sentinel.js`) tanpa downtime atau perubahan kode aplikasi sama sekali:
1. Sentinel script harus secara otomatis mengintervensi (*monkey-patch*) `eval`, `Function.prototype.constructor`, dan modul native `child_process`.
2. Mencegah seluruh bentuk mutasi baru terhadap `Object.prototype` dengan cara melakukan deep freezing terhadap semua standard JS intrinsics menggunakan `Object.freeze()` tanpa merusak library yang melakukan normal initialization.
3. Mendeteksi jika ada modul dependensi yang mencoba mengakses network connection via `net.Socket` atau `dgram` ke alamat IP publik di luar VPC cloud yang ditentukan secara strictly static.
4. Memberikan zero false-positive terhadap traffic transaksi existing yang sedang running di production.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Pertanyaan)
1. **Mengapa modifikasi `Object.prototype` (Prototype Pollution) dapat memengaruhi performa eksekusi aplikasi secara sistemik di seluruh engine V8?**
   - *Jawaban:* Karena V8 mengandalkan *Shapes* (*Hidden Classes*) dan *Inline Caches* (IC). Ketika `Object.prototype` dimutasi, V8 membatalkan (*invalidates*) seluruh optimasi Shapes yang bergantung pada prototipe tersebut, memaksa engine melakukan fallback dari machine code teroptimasi (TurboFan) ke de-optimisasi monomorphic/polymorphic lookup dan dictionary mode.

2. **Apa yang menyebabkan engine Regex Irregexp V8 terjebak dalam ReDoS?**
   - *Jawaban:* Penggunaan algoritma backtracking berbasis Non-deterministic Finite Automaton (NFA). Ketika regex dengan nested quantifier atau overlapping alternatives gagal mencocokkan input di karakter akhir, engine mencoba seluruh kombinasi jalur ekspansi secara rekursif, yang menghasilkan kompleksitas waktu eksponensial $\mathcal{O}(2^n)$.

3. **Mengapa modul bawaan Node.js `node:vm` tidak aman untuk isolasi kode eksternal (*untrusted sandboxing*)?**
   - *Jawaban:* Karena `node:vm` tidak menciptakan batas keamanan memori terisolasi (Isolate boundary). Objek yang dioper ke dalam konteks masih berbagi prototype chain yang sama dengan konteks eksternal. Penyerang dapat menggunakan accessor prototype traversal (`this.constructor.constructor`) untuk melompat keluar ke global context Node.js dan mendapatkan akses ke modul `process` atau `child_process`.

4. **Bagaimana cara kerja serangan *Timing Attack* pada validasi string HMAC?**
   - *Jawaban:* Operator komparasi standar mengevaluasi string karakter per karakter dan langsung berhenti (*early exit*) pada byte pertama yang tidak cocok. Penyerang dapat mengukur perbedaan waktu eksekusi jaringan/CPU berskala mikrodetik untuk menebak karakter yang benar satu per satu dari kiri ke kanan.

5. **Apa fungsi dari flag Node.js `--disable-proto=delete`?**
   - *Jawaban:* Flag ini menghapus properti aksesor bawaan `Object.prototype.__proto__` secara permanen sejak proses boot up, sehingga upaya traversal dan modifikasi prototipe melalui setter `__proto__` tidak lagi dapat dilakukan.

#### Bagian 2: Intermediate (5 Pertanyaan)
6. **Mengapa validasi `typeof value === 'object'` saja tidak cukup sebelum menjalankan recursive deep merge?**
   - *Jawaban:* Karena `typeof null` di JavaScript mengembalikan nilai `'object'`, dan array juga menghasilkan `'object'`. Tanpa pengecekan `value !== null` dan validasi khusus array, proses deep merge dapat melempar exception atau keliru memproses array sebagai generic dictionary yang membuka celah manipulasi index injection.

7. **Bagaimana `isolated-vm` mengisolasi memori script user dari heap utama Node.js?**
   - *Jawaban:* `isolated-vm` memanfaatkan C++ API V8 untuk membuat instance `v8::Isolate` baru yang terpisah secara fisik di memori. Setiap Isolate memiliki heap, garbage collector, dan thread eksekusi mandiri. Data antara isolate utama dan isolate child hanya dapat ditransfer melalui serialisasi deep-copy (`ExternalCopy`) atau shared memory binary buffers, bukan lewat shared pointer.

8. **Mengapa membersihkan data sensitif dari memori JavaScript menggunakan `str = null` tidak memberikan jaminan keamanan data enterprise?**
   - *Jawaban:* Karena `str = null` hanya menghapus referensi variabel. Alokasi string fisik di heap V8 tetap berada di memori sampai Garbage Collector berjalan (yang jadwalnya non-deterministik). Selain itu, GC tidak melakukan overwrite byte dengan angka nol (zero-fill), melainkan hanya menandai segmen memori sebagai free list. Data sensitif tetap dapat diekstraksi dari dump memori sistem.

9. **Apa perbedaan mendasar antara implementasi NFA (V8 Irregexp) dan DFA (Google RE2) dalam pemrosesan Regular Expression?**
   - *Jawaban:* NFA mengevaluasi state dengan kemungkinan backtracking eksploratif ke belakang jika terjadi kegagalan kecocokan, memungkinkan komputasi eksponensial pada pola tertentu. DFA (Deterministic Finite Automaton) membaca setiap karakter input tepat satu kali dan bertransisi antar multi-state secara serentak, memberikan garansi matematis eksekusi linier $\mathcal{O}(n)$ terhadap panjang input tanpa backtracking.

10. **Bagaimana flag arsitektural `--permission` Node.js membatasi blast radius dari package supply-chain yang terinfeksi?**
    - *Jawaban:* Dengan mengaktifkan Permission Model, runtime memblokir pemanggilan syscall sistem berkas, worker thread, dan child process secara native di layer bindings C++. Sekalipun script dependensi disusupi kode eksfiltrasi, ia tidak dapat membaca disk (misal: `/etc/passwd` atau `.env`) atau mengeksekusi binary host melalui `spawn`/`exec`.

#### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan)

11. **Skenario A:** Sebuah microservice Node.js memproses webhook transfer finansial dari partner. Sistem memvalidasi signature menggunakan `crypto.timingSafeEqual(Buffer.from(sigA), Buffer.from(sigB))`. Namun aplikasi tiba-tiba crash dengan error: `RangeError: Input buffers must have the same length` setiap kali penyerang mengirimkan signature acak. Bagaimana Anda memitigasinya tanpa membuka celah timing attack terhadap panjang signature?
    - *Solusi & Rasional:*
      ```typescript
      // Hitung HMAC dari kedua signature terlebih dahulu menggunakan ephemeral key
      // Hal ini menormalkan panjang kedua buffer menjadi persis 32 byte (SHA-256)
      // secara deterministik tanpa membocorkan panjang string asli via timing.
      const maskKey = crypto.randomBytes(32);
      const hashA = crypto.createHmac('sha256', maskKey).update(sigA).digest();
      const hashB = crypto.createHmac('sha256', maskKey).update(sigB).digest();
      const isValid = crypto.timingSafeEqual(hashA, hashB) && sigA.length === sigB.length;
      ```

12. **Skenario B:** Cluster Node.js Anda menggunakan Redis untuk caching JSON payload. Penyerang berhasil meracuni salah satu key Redis dengan nilai JSON: `{"constructor": {"prototype": {"isAdmin": true}}}`. Mengapa parser standar `JSON.parse()` tidak langsung mengeksekusi polusi prototipe, tetapi aplikasi Anda tetap terkompromi saat data tersebut dibaca oleh framework ORM/Permission layer internal?
    - *Solusi & Rasional:* `JSON.parse` memetakan string JSON murni menjadi plain object tanpa memicu setter prototipe; properti `constructor` hanya disimpan sebagai own-property biasa. Namun, jika library ORM atau Permission layer melakukan operasi kloning seperti `merge({}, cachedObject)` atau `Object.assign({}, cachedObject)`, traversal internal fungsi merge tersebut akan membaca property `constructor.prototype` sebagai lookup object aktual dan memutasi prototipe objek global secara tidak sengaja. Mitigasinya: Terapkan Object sanitization whitelist sebelum parsing cache masuk ke domain entities.

13. **Skenario C:** Anda memiliki service yang harus mengeksekusi ribuan user-defined string formatting rules per detik. Penggunaan `isolated-vm` menyebabkan CPU overhead melonjak hingga 45% akibat pembuatan context berulang kali. Bagaimana rancangan arsitektur optimasi Anda agar tetap mempertahankan zero-trust execution sandbox namun memangkas latensi context creation ke bawah 0.5ms?
    - *Solusi & Rasional:*
      Gunakan teknik **Isolate Context Pooling** dan **Isolate Snapshots**.
      1. Buat pool instance `v8::Isolate` yang tetap hidup (*warm worker isolates pool*), alih-alih instansiasi per-request.
      2. Gunakan `isolated-vm.Snapshot` untuk mengompilasi runtime script dan state awal satu kali di fase bootstrap pod.
      3. Setiap context yang diambil dari pool hanya mengeksekusi fungsi dalam sandbox tanpa alokasi global baru, dan segera gunakan `context.release()` atau reset state ringan menggunakan scope isolation internal tanpa menghancurkan thread Isolate induk.

---

### 16. Summary

Hardening JavaScript Runtime pada skala enterprise memerlukan pergeseran paradigma dari sanitasi input berbasis string perimeter tradisional menuju **Arsitektur Pertahanan Runtime Berlapis (Defense-in-Depth Contextual Hardening)**.

1. **V8 Engine Internals Defense:** Memahami interaksi antara memory map, Hidden Classes (*Shapes*), dan Prototype Chain adalah fondasi utama mitigasi *Prototype Pollution*. Modifikasi terhadap `Object.prototype` bukan sekadar bug fungsional, melainkan ancaman sistemik yang merusak performa TurboFan dan memicu celah RCE.
2. **Determinisme Komputasi:** Engine NFA (Irregexp) harus diproteksi dengan timeout terisolasi atau dialihkan ke engine Linear Deterministic Finite Automaton (RE2) untuk mematikan vektor serangan ReDoS secara matematis.
3. **Isolasi Mutlak via Isolate Boundaries:** Sandboxing kode dinamis pihak ketiga tidak boleh mengandalkan abstraksi level tinggi seperti modul native `node:vm`. Satu-satunya isolasi yang teruji di lingkungan enterprise adalah pemisahan level hardware memory boundary melalui V8 Isolates (`isolated-vm`) atau runtime process isolation.
4. **Disiplin Kriptografi & Memori:** Komparasi kredensial wajib kebal terhadap side-channel attacks (*constant-time equality*), dan residu memori plain-text kredensial harus dibersihkan secara eksplisit (*zero-filled memory buffers*) untuk mengamankan data dari exfiltrasi heap analysis.