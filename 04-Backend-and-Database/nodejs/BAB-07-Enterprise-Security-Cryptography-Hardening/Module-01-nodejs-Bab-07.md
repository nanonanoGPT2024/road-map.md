# Bab 07 Module 01: Enterprise Security, Cryptography, & Hardening

---

## 01: Identitas Modul
* **Track:** Node.js Backend Engineering
* **Kategori:** 04-Backend-and-Database
* **Bab:** 07 (Advanced Security & Resiliency)
* **Modul:** 01
* **Judul:** Enterprise Security, Cryptography, & Hardening
* **Tingkat Kesulitan:** Advanced / Senior Engineer
* **Prasyarat:** Pemahaman mendalam tentang Node.js Event Loop, HTTP lifecycle, Buffer, Streams, Asynchronous Programming, serta arsitektur Microservices.

---

## 02: Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. Mengimplementasikan enkripsi simetris (*Authenticated Encryption with Associated Data* / AEAD via AES-256-GCM) dan asimetris (RSA/ECDSA via Web Crypto API / Node.js `crypto`) secara *thread-safe* dan *leak-free*.
2. Membangun strategi mitigasi kerentanan tingkat lanjut: *Timing Attacks*, *Prototype Pollution*, ReDoS (*Regular Expression Denial of Service*), serta *Event Loop Starvation* akibat operasi kriptografi.
3. Mengonfigurasi dan menegakkan kebijakan *Defense-in-Depth* pada HTTP headers (CSP, HSTS, HPKP deprecation, Permissions-Policy) dan *Runtime Hardening* (Node.js permission model, memory sanitization, V8 flags).
4. Merancang *Secret Management Lifecycle* dengan zeroization di memori untuk mencegah eksfiltrasi kredensial melalui *Heap Dump inspection*.
5. Mengintegrasikan verifikasi integritas dependensi dan runtime attestation ke dalam CI/CD pipeline.

---

## 03: Concept Map Diagram ASCII
```
+---------------------------------------------------------------------------------------------------+
|                        ENTERPRISE NODE.JS RUNTIME SECURITY & CRYPTOGRAPHY                         |
+---------------------------------------------------------------------------------------------------+
                                                  |
         +----------------------------------------+---------------------------------------+
         |                                        |                                       |
         v                                        v                                       v
+------------------+                    +-------------------+                   +-------------------+
| LAYER 1: RUNTIME |                    | LAYER 2: CRYPTO   |                   | LAYER 3: APPSEC   |
| & HOST HARDENING |                    | ENGINE (OpenSSL)  |                   | & HTTP DEFENSES   |
+------------------+                    +-------------------+                   +-------------------+
  |                                       |                                       |
  +--> Node Permission Model              +--> AEAD (AES-256-GCM)                 +--> Strict CSP / HSTS
  |    (--experimental-permission)        |    Cipher/Decipher Streams            |    Permissions-Policy
  |                                       |                                       |
  +--> Zeroization Memory                 +--> Key Derivation                     +--> Prototype Pollution
  |    (Buffer.fill(0) / Sodium)          |    (Argon2id, scrypt, HKDF)           |    Freeze / Map(null)
  |                                       |                                       |
  +--> Process Isolation & Drops          +--> Asymmetric & Signatures            +--> Timing-Safe Ops
       (Setuid/Setgid, V8 flags)               (Ed25519, ECDSA P-384, RSA-PSS)         (timingSafeEqual)
                                                  |
                                                  v
                                    +---------------------------+
                                    | ZERO-TRUST DATA PIPELINE  |
                                    | (Envelope Encryption KMS) |
                                    +---------------------------+
```

---

## 04: Mengapa Relevan
Node.js berjalan di atas V8 engine dengan model single-threaded event loop yang dikombinasikan dengan Libuv thread pool. Karakteristik ini menimbulkan trade-off keamanan yang unik:
* **Event Loop Blocking:** Operasi hashing yang salah dikonfigurasi (misalnya `bcrypt` sinkron atau iterasi PBKDF2 berlebih pada main thread) melumpuhkan throughput server secara total.
* **Memory Dump Exposure:** Garbage Collector (V8 GC) memindahkan string dan buffer di memori tanpa membersihkan lokasi lama, mengekspos kunci enkripsi, JWT secret, dan PII (*Personally Identifiable Information*) ke eksploitasi *heap inspection*.
* **Ecosystem Attack Surface:** Ketergantungan modular yang dalam meningkatkan risiko *supply-chain attacks* dan *prototype pollution* yang dapat berujung pada RCE (*Remote Code Execution*).

Aplikasi skala enterprise membutuhkan arsitektur kriptografi modern (misalnya beralih dari CBC ke GCM/ChaCha20-Poly1305) dan proteksi runtime proaktif untuk mematuhi regulasi ketat seperti PCI-DSS v4.0, HIPAA, dan GDPR.

---

## 05: Anatomi Konsep Inti

### 1. Authenticated Encryption with Associated Data (AEAD)
Enkripsi modern wajib menjamin kerahasiaan (*confidentiality*) dan integritas (*authenticity*) secara simultan. AES-GCM (Galois/Counter Mode) menghasilkan *ciphertext* dan *authentication tag*.
* **Cipher:** AES-256 (kunci 32-byte).
* **Initialization Vector (IV):** 12-byte (96-bit) deterministik acak unik per enkripsi. **Dilarang keras menggunakan kembali IV dengan kunci yang sama.**
* **Auth Tag:** 16-byte (128-bit) untuk memvalidasi bahwa ciphertext dan AAD (*Additional Authenticated Data*) tidak dimanipulasi.

### 2. Key Derivation Functions (KDF): Argon2id vs scrypt vs PBKDF2
Menyimpan kata sandi atau menurunkan kunci dari master key membutuhkan algoritma yang *memory-hard* dan *CPU-intensive* untuk melawan serangan GPU/ASIC.
* **Argon2id:** Pilihan standar industri modern (pemenang *Password Hashing Competition*), tahan terhadap *side-channel attacks* dan optimasi GPU.
* **scrypt:** Alternatif bawaan Node.js `crypto` yang sangat aman dengan konfigurasi $N$ (cost), $r$ (block size), dan $p$ (parallelization).

### 3. Constant-Time Comparisons
Eksekusi perbandingan string tradisional (`===`) berhenti pada karakter pertama yang tidak cocok. Penyerang dapat mengukur delta waktu eksekusi dalam orde nanodetik untuk merekonstruksi token rahasia secara berurutan (*Timing Attack*). Node.js menyediakan `crypto.timingSafeEqual(Buffer a, Buffer b)` untuk menjamin waktu komputasi konstan terlepas dari posisi ketidakcocokan karakter.

### 4. Memory Zeroization & Buffer Security
V8 mengelola memori via Garbage Collection otomatis, namun GC tidak menghapus data sensitif secara deterministik. Kunci kriptografi harus dialokasikan dalam buffer non-pool (`Buffer.alloc(size)` bukan `Buffer.allocUnsafe(size)`) dan secara eksplisit dibersihkan menggunakan `.fill(0)` setelah selesai digunakan.

---

## 06: Panduan Implementasi Step-by-Step

### Langkah 1: Inisialisasi Enkripsi Data dengan AES-256-GCM
1. Bangun fungsi enkripsi yang menerima `plaintext`, `masterKey`, dan `associatedData`.
2. Generate cryptographically secure IV sepanjang 12 byte menggunakan `crypto.randomBytes(12)`.
3. Inisialisasi cipher menggunakan `crypto.createCipheriv('aes-256-gcm', key, iv)`.
4. Tambahkan AAD via `cipher.setAAD(Buffer.from(aad))`.
5. Gabungkan `iv`, `authTag`, dan `ciphertext` ke dalam satu payload terstandarisasi.

### Langkah 2: Mengamankan Komparasi Token / Hash
1. Pastikan kedua buffer yang dibandingkan memiliki panjang byte yang persis sama.
2. Gunakan `crypto.timingSafeEqual` pada representasi Buffer (bukan string mentah).

### Langkah 3: Proteksi Runtime Prototype Pollution
1. Gunakan `Object.freeze(Object.prototype)` dan `Object.freeze(Array.prototype)` pada bootstrap aplikasi jika dependensi mendukung, ATAU:
2. Wajibkan penggunaan `Map` murni atau objek tanpa prototipe (`Object.create(null)`) untuk parsing input dinamis/JSON payload.

---

## 07: Contoh Kasus Sederhana: Constant-Time Token Verifier
Implementasi verifikasi webhook token / API signature yang aman dari serangan timing side-channel:

```typescript
import crypto from 'node:crypto';

export function secureCompareTokens(providedToken: string, expectedToken: string): boolean {
  const providedBuffer = Buffer.from(providedToken, 'utf-8');
  const expectedBuffer = Buffer.from(expectedToken, 'utf-8');

  // Panjang buffer HARUS diverifikasi terlebih dahulu secara deterministik
  if (providedBuffer.length !== expectedBuffer.length) {
    // Lakukan komparasi dummy untuk menyamarkan jejak waktu eksekusi
    crypto.timingSafeEqual(expectedBuffer, expectedBuffer);
    return false;
  }

  return crypto.timingSafeEqual(providedBuffer, expectedBuffer);
}
```

---

## 08: Implementasi Production-Grade Lengkap Kode
Di bawah ini adalah implementasi **Enterprise Cryptography Vault Engine** yang mencakup AEAD Stream Encryption, Password Hashing via Argon2/scrypt, Key Zeroization, dan Payload Tamper Verification.

```typescript
import {
  createCipheriv,
  createDecipheriv,
  randomBytes,
  scrypt,
  timingSafeEqual,
  CipherGCMTypes
} from 'node:crypto';
import { promisify } from 'node:util';

const scryptAsync = promisify(scrypt);

export interface EncryptedPayload {
  version: string;
  algorithm: CipherGCMTypes;
  iv: string;      // Base64
  tag: string;     // Base64
  data: string;    // Base64
  aad?: string;    // UTF-8 identifier
}

export class EnterpriseCryptoVault {
  private static readonly ALGORITHM: CipherGCMTypes = 'aes-256-gcm';
  private static readonly IV_LENGTH_BYTES = 12; // 96 bits for GCM
  private static readonly TAG_LENGTH_BYTES = 16; // 128 bits
  private static readonly PAYLOAD_VERSION = 'v1';

  /**
   * Derives a cryptographic key from password and salt using scrypt (Node native).
   */
  public static async deriveKey(
    secret: string,
    salt: Buffer,
    keyLength = 32
  ): Promise<Buffer> {
    // N=32768, r=8, p=1 recommended minimum for sensitive operations
    return (await scryptAsync(secret, salt, keyLength, {
      N: 32768,
      r: 8,
      p: 1,
      maxmem: 64 * 1024 * 1024
    })) as Buffer;
  }

  /**
   * Encrypts plaintext buffer using AES-256-GCM with memory zeroization.
   */
  public static encrypt(
    plaintextBuffer: Buffer,
    key: Buffer,
    associatedData?: string
  ): EncryptedPayload {
    if (key.length !== 32) {
      throw new Error('Invalid key length: AES-256 requires exactly 32 bytes.');
    }

    const iv = randomBytes(this.IV_LENGTH_BYTES);
    const cipher = createCipheriv(this.ALGORITHM, key, iv, {
      authTagLength: this.TAG_LENGTH_BYTES
    });

    if (associatedData) {
      cipher.setAAD(Buffer.from(associatedData, 'utf-8'));
    }

    try {
      const ciphertext = Buffer.concat([
        cipher.update(plaintextBuffer),
        cipher.final()
      ]);

      const tag = cipher.getAuthTag();

      return {
        version: this.PAYLOAD_VERSION,
        algorithm: this.ALGORITHM,
        iv: iv.toString('base64'),
        tag: tag.toString('base64'),
        data: ciphertext.toString('base64'),
        aad: associatedData
      };
    } finally {
      // Memory Hygiene: Sanitize internal buffers if needed
      iv.fill(0);
    }
  }

  /**
   * Decrypts ciphertext and verifies integrity via Authentication Tag.
   */
  public static decrypt(
    payload: EncryptedPayload,
    key: Buffer
  ): Buffer {
    if (payload.algorithm !== this.ALGORITHM) {
      throw new Error(`Unsupported cipher algorithm: ${payload.algorithm}`);
    }

    if (key.length !== 32) {
      throw new Error('Invalid key length: AES-256 requires exactly 32 bytes.');
    }

    const iv = Buffer.from(payload.iv, 'base64');
    const tag = Buffer.from(payload.tag, 'base64');
    const ciphertext = Buffer.from(payload.data, 'base64');

    if (iv.length !== this.IV_LENGTH_BYTES) {
      throw new Error('Invalid IV length.');
    }

    if (tag.length !== this.TAG_LENGTH_BYTES) {
      throw new Error('Invalid Auth Tag length.');
    }

    const decipher = createDecipheriv(this.ALGORITHM, key, iv, {
      authTagLength: this.TAG_LENGTH_BYTES
    });

    decipher.setAuthTag(tag);

    if (payload.aad) {
      decipher.setAAD(Buffer.from(payload.aad, 'utf-8'));
    }

    try {
      const plaintext = Buffer.concat([
        decipher.update(ciphertext),
        decipher.final() // Will throw if tag verification fails
      ]);

      return plaintext;
    } catch (err) {
      throw new Error('Decryption failed: Ciphertext or metadata has been tampered with.');
    }
  }

  /**
   * Explicitly zeroes out sensitive Buffers from memory.
   */
  public static wipeBuffer(buffer: Buffer): void {
    buffer.fill(0);
  }
}
```

---

## 09: Diagram Alur Kerja ASCII: AEAD Encryption & Decryption Lifecycle
```
[ PLAINTEXT DATA ] + [ 32-BYTE KEY ] + [ AAD METADATA ]
        |
        v
 Generate CSPRNG 12-byte IV 
        |
        +----------------------------+
        |                            |
        v                            v
  AES-256 Core Engine <----+   Set Additional Auth Data (AAD)
        |                  |
        v                  |
 [ CIPHERTEXT ]            +-- Galois Hash Computation
        |                            |
        +----------------------------+
        |
        v
 Compute 16-byte Auth Tag
        |
        +---> Output JSON Envelope: { version, iv, data, tag, aad }

====================================================================
DECRYPTION & INTEGRITY VERIFICATION PIPELINE
====================================================================

 Envelope JSON ---> Parse Base64 Fields (iv, tag, ciphertext)
                          |
                          v
               Set Key, IV, and Expected Tag
                          |
                          v
                  Provide Same AAD
                          |
                          v
               Execute decipher.final()
                          |
             +------------+------------+
             | Tag Valid?              | Tag Invalid?
             v                         v
     [ EMIT PLAINTEXT ]        [ THROW AUTH EXCEPTION ]
     (Integrity Guaranteed)    (Tamper Attempt Aborted)
```

---

## 10: Analisis Trade-offs
| Pendekatan / Algoritma | Keuntungan Utama | Kerugian / Trade-off | Skenario Rekomendasi |
| :--- | :--- | :--- | :--- |
| **AES-256-GCM** | Terakselerasi hardware (AES-NI), performa tinggi, built-in integrity check. | Rentan jika IV terulang (catastrophic key recovery). | Default standard untuk database & payload transport. |
| **ChaCha20-Poly1305** | Performa sangat tinggi pada sistem tanpa AES hardware instructions. | Kurang umum di modul enterprise legacy. | Mobile-to-backend payload encryption, ARM IoT edge. |
| **Argon2id** | Ketahanan tertinggi terhadap brute-force GPU/ASIC/Side-channel. | Membutuhkan dependensi native C++ bindings jika versi Node < 21. | Enterprise user credentials authentication. |
| **scrypt (Node Native)** | Native bindings tanpa dependensi pihak ketiga, *memory-hard*. | Alokasi memori tinggi dapat memicu DoS jika parameter tidak dibatasi. | Password hashing murni tanpa dependensi native eksternal. |
| **In-Memory Zeroization** | Memperkecil window eksfiltrasi data saat core dump crash. | Manual overhead; V8 Garbage Collector tetap dapat menduplikasi string. | High-security HSM/KMS client middleware. |

---

## 11: Best Practices & Antipatterns

### Best Practices
* **Enforce Zeroization:** Alokasikan secret dalam `Buffer.alloc()` dan panggil `.fill(0)` dalam blok `finally`.
* **Gunakan Unique IV:** Gunakan selalu `crypto.randomBytes(12)` per payload enkripsi.
* **Strict Prototype Nullification:** Gunakan `Object.create(null)` atau `new Map()` saat melakukan deserialisasi data input eksternal.
* **Defense-in-Depth Headers:** Terapkan Content Security Policy level 3 dan set `Strict-Transport-Security: max-age=63072000; includeSubDomains; preload`.

### Antipatterns
* **Gunakan AES-CBC tanpa HMAC terpisah:** Sangat rentan terhadap serangan *Padding Oracle Attacks*.
* **Reusing IV:** Mengenkripsi dua payload berbeda dengan IV dan Kunci yang sama pada AES-GCM mengekspos Galois Hash key.
* **Math.random() untuk Operasi Keamanan:** Menggunakan `Math.random()` alih-alih `crypto.randomBytes()` atau `crypto.getRandomValues()` membuat token mudah diprediksi (*pseudo-random sequence leak*).
* **Konversi Kunci Sensitif ke String:** Mengubah buffer kunci menjadi string Javascript (`key.toString('utf-8')`) menyebabkan data masuk ke *immutable string pool* V8 yang tidak bisa di-zeroize secara manual.

---

## 12: Security Hardening

### 1. Node.js Security Model Enforcement
Jalankan runtime dengan flags restriksi sistem:
```bash
node --experimental-permission \
     --allow-fs-read=/app/dist,/app/node_modules \
     --allow-fs-write=/app/logs \
     --allow-net=api.internal.vault,api.stripe.com \
     --no-addons \
     dist/server.js
```

### 2. HTTP Hardening Headers Middleware (Express/Fastify Equivalent)
```typescript
import { IncomingMessage, ServerResponse } from 'node:http';

export function applyEnterpriseSecurityHeaders(req: IncomingMessage, res: ServerResponse): void {
  // Prevent MIME type sniffing
  res.setHeader('X-Content-Type-Options', 'nosniff');
  // Clickjacking mitigation
  res.setHeader('X-Frame-Options', 'DENY');
  // Modern Strict Content Security Policy
  res.setHeader('Content-Security-Policy', "default-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none';");
  // Force HTTPS & Preloading
  res.setHeader('Strict-Transport-Security', 'max-age=63072000; includeSubDomains; preload');
  // Restrict sensitive browser features
  res.setHeader('Permissions-Policy', 'camera=(), microphone=(), geolocation=(), payment=()');
  // Cross-Origin Isolations
  res.setHeader('Cross-Origin-Opener-Policy', 'same-origin');
  res.setHeader('Cross-Origin-Resource-Policy', 'same-origin');
}
```

---

## 13: Observabilitas & Debugging
Metrik dan logging kriptografi harus diaudit tanpa membocorkan ciphertext, IV, atau key metadata ke log monitoring.

```typescript
import { performance } from 'node:perf_hooks';

export class CryptoAuditor {
  public static trackOperation(
    operationName: string,
    algorithm: string,
    executionFn: () => void
  ): void {
    const start = performance.now();
    let success = false;
    try {
      executionFn();
      success = true;
    } finally {
      const durationMs = (performance.now() - start).toFixed(3);
      // Structured Security Log (aman dikirim ke ELK / Datadog / OpenTelemetry)
      const auditEvent = {
        timestamp: new Date().toISOString(),
        event: 'CRYPTO_OP_METRICS',
        operation: operationName,
        algorithm,
        durationMs: Number(durationMs),
        status: success ? 'SUCCESS' : 'FAILED'
      };
      
      process.stdout.write(JSON.stringify(auditEvent) + '\n');
    }
  }
}
```

---

## 14: Benchmarking & Performance
Berikut adalah script benchmark komparasi throughput AES-256-GCM vs AES-256-CBC with HMAC menggunakan native Buffer:

```typescript
import { randomBytes, createCipheriv, createHmac } from 'node:crypto';
import { performance } from 'node:perf_hooks';

const iterations = 50_000;
const payload = Buffer.from(JSON.stringify({ accountId: 'acc_123', balance: 5000000, secure: true }));
const key = randomBytes(32);
const hmacKey = randomBytes(32);
const iv = randomBytes(12);
const ivCbc = randomBytes(16);

console.log(`Starting benchmark with ${iterations} operations...\n`);

// Benchmark AES-256-GCM
const startGcm = performance.now();
for (let i = 0; i < iterations; i++) {
  const cipher = createCipheriv('aes-256-gcm', key, iv);
  const data = Buffer.concat([cipher.update(payload), cipher.final()]);
  const tag = cipher.getAuthTag();
}
const durationGcm = performance.now() - startGcm;
console.log(`AES-256-GCM: ${(iterations / (durationGcm / 1000)).toFixed(2)} ops/sec (${durationGcm.toFixed(2)} ms)`);

// Benchmark AES-256-CBC + HMAC-SHA256
const startCbc = performance.now();
for (let i = 0; i < iterations; i++) {
  const cipher = createCipheriv('aes-256-cbc', key, ivCbc);
  const data = Buffer.concat([cipher.update(payload), cipher.final()]);
  const hmac = createHmac('sha256', hmacKey).update(data).digest();
}
const durationCbc = performance.now() - startCbc;
console.log(`AES-256-CBC + HMAC: ${(iterations / (durationCbc / 1000)).toFixed(2)} ops/sec (${durationCbc.toFixed(2)} ms)`);
```

---

## 15: Hands-on Lab Mini-Project
**Objektif:** Bangun *Envelope Encryption Key-Management-System (KMS) Client Mock* yang menggunakan Master Key untuk mengenkripsi Data Encryption Key (DEK), dan menggunakan DEK untuk mengenkripsi record PII.

```typescript
// lab-envelope-kms.ts
import { EnterpriseCryptoVault, EncryptedPayload } from './EnterpriseCryptoVault';
import { randomBytes } from 'node:crypto';

interface EnvelopeEncryptedRecord {
  encryptedDEK: EncryptedPayload;
  encryptedData: EncryptedPayload;
}

export class EnvelopeEncryptionService {
  private masterKey: Buffer;

  constructor(masterKey: Buffer) {
    if (masterKey.length !== 32) throw new Error('Master key must be 32 bytes.');
    this.masterKey = Buffer.from(masterKey);
  }

  public encryptRecord(data: Buffer, recordId: string): EnvelopeEncryptedRecord {
    // 1. Generate local volatile Data Encryption Key (DEK)
    const localDEK = randomBytes(32);

    try {
      // 2. Encrypt plaintext payload with local DEK
      const encryptedData = EnterpriseCryptoVault.encrypt(data, localDEK, recordId);

      // 3. Encrypt local DEK with Master Key
      const encryptedDEK = EnterpriseCryptoVault.encrypt(localDEK, this.masterKey, recordId);

      return { encryptedDEK, encryptedData };
    } finally {
      // 4. Secure zeroize the ephemeral DEK immediately
      EnterpriseCryptoVault.wipeBuffer(localDEK);
    }
  }

  public decryptRecord(record: EnvelopeEncryptedRecord, recordId: string): Buffer {
    let localDEK: Buffer | null = null;
    try {
      // 1. Decrypt DEK using Master Key
      localDEK = EnterpriseCryptoVault.decrypt(record.encryptedDEK, this.masterKey);

      // 2. Decrypt actual record using decrypted DEK
      const decryptedData = EnterpriseCryptoVault.decrypt(record.encryptedData, localDEK);
      return decryptedData;
    } finally {
      if (localDEK) {
        EnterpriseCryptoVault.wipeBuffer(localDEK);
      }
    }
  }
}
```

---

## 16: Automated Testing & Verification
Unit test suite menggunakan Jest/Vitest untuk memvalidasi integritas enkripsi dan penolakan tampering:

```typescript
// vault.spec.ts
import { EnterpriseCryptoVault } from './EnterpriseCryptoVault';
import { randomBytes } from 'node:crypto';

describe('EnterpriseCryptoVault Test Suite', () => {
  const masterKey = randomBytes(32);
  const sampleData = Buffer.from('CONFIDENTIAL_PII_DATA_PAYLOAD');
  const aad = 'customer-tenant-99';

  it('should encrypt and successfully decrypt valid payload', () => {
    const payload = EnterpriseCryptoVault.encrypt(sampleData, masterKey, aad);
    const result = EnterpriseCryptoVault.decrypt(payload, masterKey);
    expect(result.toString('utf-8')).toBe(sampleData.toString('utf-8'));
  });

  it('should fail decryption if ciphertext is tampered with', () => {
    const payload = EnterpriseCryptoVault.encrypt(sampleData, masterKey, aad);
    
    // Tamper ciphertext
    const rawCiphertext = Buffer.from(payload.data, 'base64');
    rawCiphertext[0] ^= 0xff; // Flip bit
    payload.data = rawCiphertext.toString('base64');

    expect(() => {
      EnterpriseCryptoVault.decrypt(payload, masterKey);
    }).toThrow('Decryption failed: Ciphertext or metadata has been tampered with.');
  });

  it('should fail decryption if AAD metadata does not match', () => {
    const payload = EnterpriseCryptoVault.encrypt(sampleData, masterKey, aad);
    payload.aad = 'compromised-tenant-00';

    expect(() => {
      EnterpriseCryptoVault.decrypt(payload, masterKey);
    }).toThrow('Decryption failed: Ciphertext or metadata has been tampered with.');
  });
});
```

---

## 17: Troubleshooting Guide
1. **Error: `Unsupported state or unable to authenticate data`**
   * *Root Cause:* Auth Tag mismatch pada AES-GCM.
   * *Diagnosa:* Periksa apakah IV yang digunakan saat decrypt berbeda dengan saat encrypt, atau payload/AAD termodifikasi di transit.
2. **High Event Loop Latency / Lag under Crypto Operations**
   * *Root Cause:* Menjalankan KDF sinkron (misal: `scryptSync` atau hashing berulang) pada main thread.
   * *Solusi:* Migrasi ke async KDF API (`scryptAsync`) atau offload ke `Worker Threads` / Libuv pool via `crypto.pbkdf2`.
3. **ERR_CRYPTO_TIMING_SAFE_EQUAL_LENGTH**
   * *Root Cause:* `crypto.timingSafeEqual` dipanggil pada dua buffer yang berbeda panjang karakternya.
   * *Solusi:* Lakukan pre-check `bufA.length !== bufB.length` secara manual sebelum mengeksekusi method tersebut.

---

## 18: Checklist Produksi
- [ ] Semua enkripsi simetris menggunakan mode AEAD (`aes-256-gcm` atau `chacha20-poly1305`).
- [ ] Tidak ada IV/Nonce yang digunakan ulang (*Never reuse Nonce/IV with the same key*).
- [ ] Komparasi secret string menggunakan `crypto.timingSafeEqual`.
- [ ] Parameter KDF (scrypt/argon2) terkalibrasi aman ($N \ge 32768, r=8, p=1$).
- [ ] Secret buffer di-zeroize (`.fill(0)`) sesaat setelah dieksekusi dalam blok `finally`.
- [ ] Header keamanan minimum (`HSTS`, `CSP`, `X-Content-Type-Options`) terpasang aktif.
- [ ] Node.js dijalankan dengan limitasi privilege `--no-addons` dan non-root container user.
- [ ] Dependensi dipindai menggunakan `npm audit` / Snyk / Trivy pada pipeline CI/CD.

---

## 19: Ringkasan Eksekutif
Keamanan enterprise pada Node.js menuntut lebih dari sekadar perlindungan layer perimeter. Penerapan kriptografi modern berbasis AEAD (AES-256-GCM) memastikan validitas data dan kerahasiaan secara atomik. Arsitektur aplikasi harus secara proaktif mencegah *Timing Attacks* via `crypto.timingSafeEqual`, mengisolasi payload memori untuk mencegah kebocoran secret pada V8 Heap, serta memberlakukan postur *Defense-in-Depth* mulai dari runtime execution flags hingga HTTP response headers.

---

## 20: Referensi & Bacaan Lanjutan
* **Node.js Official Documentation:** Cryptography API (`node:crypto`) & Permissions Model.
* **NIST SP 800-38D:** *Recommendation for Block Cipher Modes of Operation: Galois/Counter Mode (GCM) and GMAC*.
* **OWASP Node.js Security Cheat Sheet:** Guidelines for Hardening and Secure Coding.
* **RFC 9106:** *Argon2 Memory-Hard Function for Password Hashing and Proof-of-Work Applications*.