# Kurikulum Rekayasa Perangkat Lunak Enterprise: Node.js
## Bab 07: Enterprise Security, Cryptography, & Hardening
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, tech lead dan arsitek backend diharapkan mampu:
*   **Menganalisis dan Membongkar** internal subsistem kriptografi Node.js (`src/node_crypto.cc`, integrasi OpenSSL/BoringSSL, abstraksi `node:crypto`, serta interaksi dengan libuv threadpool).
*   **Mengimplementasikan Arsitektur Kriptografi Berlapis (Defense-in-Depth)**: Menguasai Envelope Encryption (KMS/DEK), Authenticated Encryption with Associated Data (AEAD: AES-256-GCM / ChaCha20-Poly1305), dan Digital Signatures (Ed25519) dengan zero-memory leakage.
*   **Memitigasi Kerentanan Memori Tingkat Lanjut**: Melakukan zeroization buffer data sensitif sebelum Garbage Collection (GC) V8 berjalan, mencegah timing attacks via constant-time operations, dan mengamankan V8 runtime dari prototype pollution di level C++/flag runtime.
*   **Merancang dan Menggelar Arsitektur Zero-Trust**: Mengonfigurasi Mutual TLS (mTLS) berkinerja tinggi dengan validasi CRL/OCSP stapling, certificate pinning, dan protokol Demonstrating Proof-of-Possession (DPoP - RFC 9449) pada level reverse proxy/service mesh hingga Node.js core.

---

### 2. Prerequisite
*   Pemahaman mendalam mengenai arsitektur Node.js: Event Loop, Libuv Thread Pool, dan V8 Heap/Off-Heap Memory Management.
*   Kemahiran dalam TypeScript 5.x tingkat lanjut (Buffer manipulation, TypedArray, ArrayBuffer, Async/Await internals).
*   Dasar kriptografi: Symmetric vs Asymmetric, Hashing, Key Derivation Functions (KDF), dan Public Key Infrastructure (PKI/X.509).
*   Pengalaman operasional Linux minimal: POSIX signals, shared memory, IPC, namespaces, serta pemahaman seccomp/capabilities (`CAP_NET_BIND_SERVICE`).

---

### 3. Concept & Internal Architecture

Node.js tidak mengimplementasikan algoritma kriptografi sendiri menggunakan JavaScript murni karena performa dan keamanan (risiko side-channel attack). Node.js membungkus implementasi C/C++ dari OpenSSL (atau engine kriptografi kustom FIPS 140-3).

```
+-----------------------------------------------------------------------+
|                        JavaScript Application Space                   |
|         (import crypto from 'node:crypto' / Web Crypto API)           |
+-----------------------------------------------------------------------+
                                   |
                                   v  (V8 C++ Bindings)
+-----------------------------------------------------------------------+
|                       src/node_crypto.cc (Node.js Core)               |
|  - Validasi Tipe V8 Arguments (Uint8Array, Buffer, Strings)          |
|  - Manajemen State Threadpool libuv (uv_queue_work)                   |
|  - Penanganan Nonce/IV, Auth Tag, CipherContext                       |
+-----------------------------------------------------------------------+
            |                                           |
            | (Operasi Sinkron / Fast-path)             | (Operasi Asinkron / Heavy CPU)
            v                                           v
+------------------------------------+      +---------------------------+
|    OpenSSL EV_CIPHER / EVP_PKEY    |      |  libuv Worker Pool        |
|    (AES-NI Native Hardware Accel)  |      |  (scrypt, PBKDF2, RSA-gen)|
+------------------------------------+      +---------------------------+
                                                          |
                                                          v
                                            +---------------------------+
                                            | OpenSSL Cryptographic Ops |
                                            +---------------------------+
```

#### A. Jembatan `src/node_crypto.cc` dan Eksekusi Kriptografi
Saat memanggil `crypto.createCipheriv('aes-256-gcm', key, iv)`:
1. V8 meneruskan pointer memori mentah dari objek `Uint8Array` / `Buffer` melalui C++ binding layer (`node_crypto.cc`).
2. Objek C++ `CipherBase` dibuat, menginisialisasi OpenSSL `EVP_CIPHER_CTX` (`EVP_CIPHER_CTX_new()`).
3. Algoritma AEAD (AES-GCM) dieksekusi langsung pada CPU host menggunakan instruksi perangkat keras native (AES-NI) melalui OpenSSL.
4. **Alokasi Memori**: Buffer output dialokasikan di luar V8 Heap (*off-heap*) via `node::Buffer` (didukung oleh `ArrayBufferAllocator` C++), meminimalkan overhead V8 GC Scavenge/Mark-Sweep.

#### B. Threading Model: Sync vs Async Crypto
*   **Asynchronous Cryptography**: Algoritma komputasi berat (seperti KDF: `scrypt`, `pbkdf2`, dan pembangkitan kunci asimetris `generateKeyPair`) membungkus tugas ke dalam `uv_work_t` dan mengirimkannya ke `libuv threadpool`. Ukuran default threadpool adalah 4 (`UV_THREADPOOL_SIZE=4`). Jika 5 request kriptografi asinkron berat datang bersamaan, request ke-5 akan mengalami starvation di antrean libuv.
*   **Synchronous Cryptography**: Algoritma stream/block cipher seperti `AES-GCM`, `ChaCha20-Poly1305`, dan hashing (`SHA-256`) dieksekusi secara sinkron langsung di main thread (Event Loop). Karena akselerasi instruksi CPU hardware, throughput operasi ini mencapai ratusan megabyte per detik, sehingga biaya context-switching threadpool libuv justru lebih tinggi daripada mengeksekusinya secara inline di event loop.

#### C. V8 Garbage Collection & Memory Zeroing Flaw
Dalam JavaScript engine (V8):
*   Objek `String` bersifat immutable dan lokasinya dapat berpindah-pindah saat V8 melakukan *GC compaction*. Data sensitif (misal: private key plain-text, password, token) yang pernah berbentuk string akan tertinggal di unallocated heap pages hingga ditimpa oleh alokasi masa depan.
*   Dump memori V8 (via core dump, crash report, atau eksploitasi `/proc/self/mem`) dapat mengekspos rahasia tersebut.
*   **Solusi Rekayasa**: Gunakan `Buffer` alokasi native (`Buffer.alloc(size)`), jangan pernah konversi ke UTF-8 string, dan wajib lakukan *Zeroization* (`buffer.fill(0)`) sesegera mungkin di blok `finally`.

---

### 4. Why & What

| Dimensi | Kriptografi Konvensional / Pemula | Enterprise Zero-Trust Cryptography |
| :--- | :--- | :--- |
| **Symmetric Cipher** | AES-CBC atau AES-ECB (Insecure/Vulnerable to Padding Oracle) | AES-256-GCM / ChaCha20-Poly1305 (AEAD dengan integritas data otentikasi) |
| **Key Lifecycle** | Static key hardcoded di environment variable (`.env`) | Dynamic Envelope Encryption via KMS (AWS KMS, GCP KMS, HashiCorp Vault) |
| **Data in Memory** | String JavaScript murni (bertahan di V8 Heap selamanya) | Off-heap Buffers dengan deterministik memory zeroing (`crypto.randomFillSync`) |
| **Transport Layer** | Terminasi TLS standar di Ingress/Load Balancer | Strict End-to-End mTLS dengan sertifikat X.509 klien, DPoP (RFC 9449) |
| **Timing Attack** | Perbandingan string standar (`===` atau `==`) | Constant-time comparisons (`crypto.timingSafeEqual`) |

---

### 5. How (Workflow Detail)

#### Arsitektur Envelope Encryption (KMS + Local Node.js Runtime)

Envelope encryption melindungi data dengan *Data Encryption Key* (DEK) lokal, lalu mengenkripsi DEK tersebut menggunakan *Key Encryption Key* (KEK) yang dikelola oleh Hardware Security Module (HSM) atau Cloud KMS.

```
[ Inisialisasi Enkripsi ]
  1. Node.js App  ---> Request GenerateDataKey(KEK_ID) ---> Cloud KMS / HSM
  2. Cloud KMS    ---> Mengembalikan { Plaintext_DEK, Ciphertext_DEK }
  3. Node.js App  ---> AES-256-GCM Encrypt(Data, Plaintext_DEK) ---> Ciphertext_Payload + AuthTag
  4. Node.js App  ---> Zeroize Memori(Plaintext_DEK) [Buffer.fill(0)]
  5. Node.js App  ---> Simpan/Kirim { Ciphertext_Payload, AuthTag, IV, Ciphertext_DEK }

[ Alur Dekripsi ]
  1. Node.js App  ---> Kirim Ciphertext_DEK ---> Cloud KMS / HSM (Decrypt Action)
  2. Cloud KMS    ---> Mengembalikan Plaintext_DEK
  3. Node.js App  ---> AES-256-GCM Decrypt(Ciphertext_Payload, Plaintext_DEK, IV, AuthTag)
  4. Node.js App  ---> Zeroize Memori(Plaintext_DEK)
  5. Node.js App  ---> Konsumsi Plaintext Data ---> Zeroize Plaintext Data
```

---

### 6. Analogy & Diagram ASCII

Bayangkan sistem keamanan brankas bank multinasional:
*   **Plaintext Data**: Uang tunai yang hendak dilindungi.
*   **DEK (Data Encryption Key)**: Kunci fisik brankas lokal portabel. Cepat dan efisien untuk membuka brankas secara langsung.
*   **KEK (Key Encryption Key)**: Brankas raksasa di dalam bunker pusat bank (KMS/HSM) yang tidak pernah berpindah tempat.
*   **Ciphertext DEK**: Kunci brankas fisik yang dimasukkan ke dalam bunker pusat dan disegel.
*   **Zeroization**: Prosedur standar di mana staf operasional langsung membakar lembar memo berisi kode akses dari ingatan/meja kerja segera setelah pintu brankas terkunci.

```
       +-----------------------------------------------------------+
       |               STRUKTUR ENVELOPE PAYLOAD                   |
       |                                                           |
       |  [ IV: 12 bytes ] [ Auth Tag: 16 bytes ]                  |
       |  [ Encrypted DEK Length: 2 bytes ]                        |
       |  [ Encrypted DEK (Wrapped by KMS): N bytes ]              |
       |  [ Ciphertext Payload (Encrypted by DEK): M bytes ]       |
       +-----------------------------------------------------------+
```

---

### 7. Implementation: Simple & Practical Example

#### A. Core Primitives: Secure Zeroization & Constant-Time Validator

Simpan kode ini sebagai foundational module untuk mencegah V8 memori remanence dan timing attacks.

```typescript
// src/crypto/core-crypto.ts
import { timingSafeEqual } from 'node:crypto';

export class SecureMemory {
  /**
   * Menimpa isi Buffer dengan byte nol secara deterministik.
   * Melindungi plain-text secret dari pembacaan memory dump.
   */
  public static zeroize(buf: Buffer | Uint8Array): void {
    buf.fill(0);
  }

  /**
   * Constant-time comparison untuk string atau buffer arbitrer.
   * Mencegah pemindaian timing-attack pada perbandingan signature / hash / token.
   */
  public static constantTimeCompare(a: Buffer, b: Buffer): boolean {
    if (a.length !== b.length) {
      // Menjalankan operasi dummy konstan untuk menyamarkan panjang buffer
      const dummy = Buffer.alloc(a.length, 0);
      timingSafeEqual(dummy, dummy);
      return false;
    }
    return timingSafeEqual(a, b);
  }
}
```

#### B. Production-Grade Envelope Encryption Engine (AES-256-GCM)

Modul ini siap pakai untuk level produksi, mendukung AAD (Additional Authenticated Data), penanganan nonce unik, zeroization DEK, dan isolasi binary payload.

```typescript
// src/crypto/envelope-engine.ts
import {
  createCipheriv,
  createDecipheriv,
  randomBytes,
  CipherGCM,
  DecipherGCM,
} from 'node:crypto';
import { SecureMemory } from './core-crypto.js';

export interface IKmsProvider {
  generateDataKey(): Promise<{ plaintextKey: Buffer; encryptedKey: Buffer }>;
  decryptDataKey(encryptedKey: Buffer): Promise<Buffer>;
}

export interface EncryptedEnvelope {
  initializationVector: Buffer; // 12 bytes
  authTag: Buffer;              // 16 bytes
  encryptedDek: Buffer;         // Variable (tergantung KMS)
  ciphertext: Buffer;           // Variable
  aad: Buffer;                  // Additional Authenticated Data
}

export class EnvelopeEncryptionEngine {
  private static readonly ALGORITHM = 'aes-256-gcm';
  private static readonly IV_LENGTH = 12; // 96 bits disarankan NIST SP 800-38D
  private static readonly AUTH_TAG_LENGTH = 16;

  constructor(private readonly kmsProvider: IKmsProvider) {}

  public async encrypt(plaintext: Buffer, aad: Buffer = Buffer.alloc(0)): Promise<EncryptedEnvelope> {
    const { plaintextKey, encryptedKey } = await this.kmsProvider.generateDataKey();
    const iv = randomBytes(EnvelopeEncryptionEngine.IV_LENGTH);

    try {
      const cipher = createCipheriv(EnvelopeEncryptionEngine.ALGORITHM, plaintextKey, iv, {
        authTagLength: EnvelopeEncryptionEngine.AUTH_TAG_LENGTH,
      }) as CipherGCM;

      if (aad.length > 0) {
        cipher.setAAD(aad);
      }

      const ciphertext = Buffer.concat([cipher.update(plaintext), cipher.final()]);
      const authTag = cipher.getAuthTag();

      return {
        initializationVector: iv,
        authTag,
        encryptedDek: encryptedKey,
        ciphertext,
        aad,
      };
    } finally {
      // Pastikan DEK dalam bentuk plaintext dihancurkan dari memori
      SecureMemory.zeroize(plaintextKey);
    }
  }

  public async decrypt(envelope: EncryptedEnvelope): Promise<Buffer> {
    const plaintextKey = await this.kmsProvider.decryptDataKey(envelope.encryptedDek);

    try {
      const decipher = createDecipheriv(
        EnvelopeEncryptionEngine.ALGORITHM,
        plaintextKey,
        envelope.initializationVector,
        { authTagLength: EnvelopeEncryptionEngine.AUTH_TAG_LENGTH }
      ) as DecipherGCM;

      if (envelope.aad.length > 0) {
        decipher.setAAD(envelope.aad);
      }

      decipher.setAuthTag(envelope.authTag);

      const decrypted = Buffer.concat([
        decipher.update(envelope.ciphertext),
        decipher.final(), // Melempar exception jika tag/AAD/ciphertext telah dimanipulasi
      ]);

      return decrypted;
    } finally {
      SecureMemory.zeroize(plaintextKey);
    }
  }

  /**
   * Serialisasi Envelope ke Binary Stream Format terpadu untuk penyimpanan
   */
  public pack(envelope: EncryptedEnvelope): Buffer {
    const ivLen = envelope.initializationVector.length;
    const tagLen = envelope.authTag.length;
    const dekLen = envelope.encryptedDek.length;
    const aadLen = envelope.aad.length;
    const cipherLen = envelope.ciphertext.length;

    // Header struktur: [IV_LEN (1B)][TAG_LEN (1B)][DEK_LEN (2B)][AAD_LEN (2B)][IV][TAG][DEK][AAD][CIPHERTEXT]
    const header = Buffer.alloc(6);
    header.writeUInt8(ivLen, 0);
    header.writeUInt8(tagLen, 1);
    header.writeUInt16BE(dekLen, 2);
    header.writeUInt16BE(aadLen, 4);

    return Buffer.concat([
      header,
      envelope.initializationVector,
      envelope.authTag,
      envelope.encryptedDek,
      envelope.aad,
      envelope.ciphertext,
    ]);
  }

  public unpack(packedBuffer: Buffer): EncryptedEnvelope {
    const ivLen = packedBuffer.readUInt8(0);
    const tagLen = packedBuffer.readUInt8(1);
    const dekLen = packedBuffer.readUInt16BE(2);
    const aadLen = packedBuffer.readUInt16BE(4);

    let offset = 6;
    const initializationVector = packedBuffer.subarray(offset, offset + ivLen);
    offset += ivLen;

    const authTag = packedBuffer.subarray(offset, offset + tagLen);
    offset += tagLen;

    const encryptedDek = packedBuffer.subarray(offset, offset + dekLen);
    offset += dekLen;

    const aad = packedBuffer.subarray(offset, offset + aadLen);
    offset += aadLen;

    const ciphertext = packedBuffer.subarray(offset);

    return { initializationVector, authTag, encryptedDek, aad, ciphertext };
  }
}
```

#### C. Enterprise Zero-Trust mTLS Server dengan Client Certificate Pinning

Implementasi server HTTP/2 native menggunakan mutual TLS dengan validasi ekstensi Subject Alternative Name (SAN), Certificate Authority (CA) chain kustom, dan fingerprint pinning.

```typescript
// src/network/mtls-server.ts
import { createSecureServer, Http2SecureServer, ServerHttp2Stream } from 'node:http2';
import { readFileSync } from 'node:fs';
import { TLSSocket } from 'node:tls';
import { SecureMemory } from '../crypto/core-crypto.js';

export interface IMtlsConfig {
  port: number;
  host: string;
  caCertPath: string;
  serverCertPath: string;
  serverKeyPath: string;
  allowedClientFingerprints: Set<string>;
}

export class ProductionMtlsServer {
  private server: Http2SecureServer | null = null;

  constructor(private readonly config: IMtlsConfig) {}

  public start(): Promise<void> {
    return new Promise((resolve, reject) => {
      this.server = createSecureServer({
        key: readFileSync(this.config.serverKeyPath),
        cert: readFileSync(this.config.serverCertPath),
        ca: readFileSync(this.config.caCertPath),
        
        // Strict mTLS Flags
        requestCert: true,
        rejectUnauthorized: true, // Drop handshake jika CA tidak valid
        
        // Hardening TLS Ciphers & Protocol Minimum
        minVersion: 'TLSv1.3',
        honorCipherOrder: true,
      });

      this.server.on('secureConnection', (tlsSocket: TLSSocket) => {
        const clientCert = tlsSocket.getPeerCertificate(true);

        if (!clientCert || !clientCert.raw) {
          tlsSocket.destroy(new Error('Koneksi ditolak: Sertifikat klien tidak ditemukan.'));
          return;
        }

        // Ambil SHA-256 Fingerprint dari Sertifikat
        const certFingerprint = clientCert.fingerprint256;

        if (!this.config.allowedClientFingerprints.has(certFingerprint)) {
          // Zeroize/Clear sensitive ref jika ada
          tlsSocket.destroy(new Error(`Akses ditolak: Fingerprint ${certFingerprint} tidak sah.`));
          return;
        }
      });

      this.server.on('stream', (stream: ServerHttp2Stream, headers) => {
        stream.respond({
          'content-type': 'application/json',
          ':status': 200,
        });

        stream.end(
          JSON.stringify({
            status: 'SUCCESS',
            message: 'Terautentikasi melalui mutual TLS Zero-Trust Node.js runtime.',
            path: headers[':path'],
          })
        );
      });

      this.server.listen(this.config.port, this.config.host, () => {
        resolve();
      });

      this.server.on('error', (err) => reject(err));
    });
  }

  public async stop(): Promise<void> {
    return new Promise((resolve) => {
      if (this.server) {
        this.server.close(() => resolve());
      } else {
        resolve();
      }
    });
  }
}
```

---

### 8. Real World Case Study: PCI-DSS Tier 1 Core Banking Tokenization

#### Masalah
Sebuah platform gateway pembayaran berskala 18.000 TPS menangani Primary Account Number (PAN) kartu kredit. Audit PCI-DSS 4.0 Section 3 mewajibkan:
1. PAN tidak boleh muncul dalam plain-text di storage layer mana pun, termasuk database temporary dan memory snapshot V8.
2. Rotasi master key wajib terjadi setiap 90 hari tanpa melakukan downtime migrasi multi-terabyte data.
3. Node.js server berjalan di lingkungan shared Kubernetes multi-tenant.

#### Solusi Arsitektural
1. **Penerapan Envelope Encryption Dua-Tingkat**:
   * Data PAN dienkripsi dengan *DEK* unik per-transaksi/per-record via AES-256-GCM.
   * AAD (Additional Authenticated Data) menggunakan `account_holder_uuid` untuk mengikat enkripsi ke identitas pemilik (mencegah *ciphertext shuffling attacks*).
   * KEK (Key Encryption Key) disimpan dalam cloud HSM. Saat rotasi KEK terjadi, hanya kolom `encrypted_dek` yang di-re-wrap menggunakan KEK baru secara batch background; ciphertext utama tidak perlu didekripsi/dienkripsi ulang.
2. **Runtime Memory Scrubbing**:
   * PAN diterima melalui HTTP body buffer mentah via Fastify parser kustom.
   * Pemrosesan enkripsi dieksekusi off-heap via custom Node.js Addon C++ atau langsung lewat Buffer tanpa alokasi String JS.
   * `SecureMemory.zeroize(buffer)` dijalankan di interceptor `onResponse`.

```
Client Payload
     |
     v [Raw Binary Parser: Fastify]
[ Buffer (Off-Heap) ] 
     |
     +---> [AES-256-GCM Engine] ---> Enkripsi dengan DEK ---> Ciphertext disimpan ke DB
     |                                                          |
     +---> [SecureMemory.zeroize()]                             +---> DEK di-wrap KMS
     |
     x (Memori PAN dihapus dari RAM sebelum siklus GC V8 berikutnya)
```

---

### 9. Trade-offs & Production Matrix

| Dimensi Arsitektur | Pilihan A | Pilihan B | Trade-off Analysis |
| :--- | :--- | :--- | :--- |
| **Symmetric Algorithm** | **AES-256-GCM** | **ChaCha20-Poly1305** | AES-GCM memanfaatkan instruksi hardware AES-NI (sangat cepat pada arsitektur x86_64 modern). ChaCha20 jauh lebih cepat dan aman dari cache-timing attack pada perangkat tanpa instruksi hardware khusus AES (misal: sistem ARM legacy). |
| **Thread Management** | **Synchronous `createCipheriv`** | **Async Offloading (`worker_threads`)** | AES stream processing inline di main-loop memiliki latensi sub-milidetik. Menaruh AES biasa di worker thread menambahkan latensi serisasi IPC (Structured Clone Algorithm) yang lebih besar dari waktu enkripsi itu sendiri. Gunakan worker hanya untuk algoritma KDF berat (`Argon2id`, `scrypt`). |
| **Zero-Trust Boundary** | **Terminasi TLS di Envoy/Ingress** | **End-to-End Node.js mTLS** | Terminasi Ingress menghemat penggunaan CPU Node.js, namun membuka risiko *cleartext snooping* lateral di dalam cluster container. E2E mTLS ke Node.js menjamin Zero-Trust penuh tetapi menaikkan alokasi CPU per-pod sebesar ~12-18%. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Nonce/IV Reuse pada AES-GCM (Catastrophic Cryptographic Failure)
*   **Kesalahan Fatal**: Menggunakan IV statis atau IV berulang untuk key yang sama.
*   **Dampak**: Menyerang AES-GCM dengan *Two-Time Pad / XOR-differencing* membuka kemungkinan pemulihan kunci plain-text dan pemalsuan Authentication Tag.
*   **Deteksi & Perbaikan**:
    ```typescript
    // SALAH: IV statis
    const iv = Buffer.alloc(12, 0); 
    
    // BENAR: Kriptografis acak CSPRNG 96-bit per enkripsi
    const iv = randomBytes(12);
    ```

#### 2. Event Loop Starvation via Cryptographic Heavy Primitives
*   **Kesalahan Fatal**: Menjalankan fungsi sinkron KDF (`crypto.pbkdf2Sync`, `crypto.scryptSync`) di main-thread web request.
*   **Dampak**: Event loop berhenti total selama 50-300ms per kalkulasi, menyebabkan API gateway timeout dan health check kubernetes gagal (CrashLoopBackOff).
*   **Perbaikan**: Wajib menggunakan async callback/Promise (`crypto.scrypt(..., callback)`) atau memindahkannya ke Worker Thread pool terpisah.

#### 3. Timing Leak pada Signature Validation
*   **Kesalahan Fatal**:
    ```typescript
    if (incomingHmac === expectedHmac) { /* Insecure! */ }
    ```
*   **Dampak**: Operator `===` membandingkan byte demi byte dan mengembalikan `false` segera setelah mismatch pertama ditemukan. Penyerang dapat mengukur variasi latensi tingkat mikrodetik untuk menebak signature byte demi byte.
*   **Perbaikan**: Wajib gunakan `crypto.timingSafeEqual(Buffer.from(a), Buffer.from(b))`.

---

### 11. Best Practices (Production Checklist)

* [ ] **Minimum TLS Configuration**: Wajib set `minVersion: 'TLSv1.3'`. Nonaktifkan SSLv3, TLS 1.0, dan TLS 1.1 secara global.
* [ ] **Secure Cryptographic Primitives**: Gunakan hanya cipher AEAD (`aes-256-gcm`, `chacha20-poly1305`). Hindari `aes-*-cbc`, `aes-*-ecb`.
* [ ] **CSPRNG Generation**: Gunakan `crypto.randomBytes()` atau `crypto.randomFill()`. Jangan pernah gunakan `Math.random()`.
* [ ] **Prevent Prototype Pollution**: Terapkan runtime flag `--disable-proto=delete` atau `--disable-proto=throw` saat menjalankan binary Node.js.
* [ ] **V8 Heap Containment**: Eksekusi buffer scrubbing (`zeroize`) untuk kunci rahasia, token, dan data PII di blok `finally`.
* [ ] **Non-Root Execution**: Jalankan Node.js process di dalam container dengan namespace non-root (`USER node`, UID 1000) dan read-only root filesystem (`readOnlyRootFilesystem: true`).
* [ ] **Threadpool Sizing**: Set `UV_THREADPOOL_SIZE` sesuai jumlah core fisik jika aplikasi menangani *crypto hashing* (`scrypt`/`pbkdf2`) masif.
* [ ] **Constant-Time Verification**: Seluruh perbandingan token autentikasi, HMAC, atau hash digest wajib menggunakan `crypto.timingSafeEqual`.
* [ ] **Disable Insecure Descriptors**: Bekukan `Object.prototype` jika dependensi eksternal tidak dapat diverifikasi secara penuh (`Object.freeze(Object.prototype)`).
* [ ] **Security Engine Auditing**: Pastikan OpenSSL yang digunakan Node.js selalu sinkron dengan rilis patch CVE terbaru (`process.versions.openssl`).

---

### 12. Hands-on Practice

Buat dan jalankan modul praktikum mandiri dengan langkah-langkah terstruktur berikut di dalam direktori `hands-on/m02/`.

#### Struktur Direktori
```text
hands-on/m02/
├── package.json
├── tsconfig.json
├── src/
│   ├── crypto/
│   │   ├── core.ts
│   │   ├── envelope.ts
│   │   └── mock-kms.ts
│   └── index.ts
└── test/
    └── crypto.test.ts
```

#### File: `package.json`
```json
{
  "name": "enterprise-crypto-hardening",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "build": "tsc",
    "test": "node --test dist/test/*.test.js",
    "start": "tsc && node dist/src/index.js"
  },
  "devDependencies": {
    "@types/node": "^20.11.0",
    "typescript": "^5.3.3"
  }
}
```

#### File: `tsconfig.json`
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "outDir": "./dist",
    "rootDir": "./",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true
  },
  "include": ["src/**/*", "test/**/*"]
}
```

#### File: `src/crypto/core.ts`
```typescript
import { timingSafeEqual } from 'node:crypto';

export function secureZeroize(buffer: Buffer): void {
  buffer.fill(0);
}

export function safeCompare(a: Buffer, b: Buffer): boolean {
  if (a.length !== b.length) {
    const dummy = Buffer.alloc(a.length, 0);
    timingSafeEqual(dummy, dummy);
    return false;
  }
  return timingSafeEqual(a, b);
}
```

#### File: `src/crypto/mock-kms.ts`
```typescript
import { randomBytes, createCipheriv, createDecipheriv } from 'node:crypto';
import { secureZeroize } from './core.js';

export interface IKms {
  generateDataKey(): Promise<{ plaintextKey: Buffer; encryptedKey: Buffer }>;
  decryptDataKey(encryptedKey: Buffer): Promise<Buffer>;
}

export class MockLocalKms implements IKms {
  // Master Key (KEK) simulasi Hardware Security Module (32 bytes = 256 bits)
  private readonly kek = randomBytes(32);
  private readonly iv = randomBytes(12);

  public async generateDataKey(): Promise<{ plaintextKey: Buffer; encryptedKey: Buffer }> {
    const plaintextKey = randomBytes(32);
    
    // Wrap DEK menggunakan KEK
    const cipher = createCipheriv('aes-256-gcm', this.kek, this.iv);
    const encryptedKey = Buffer.concat([cipher.update(plaintextKey), cipher.final(), cipher.getAuthTag()]);

    return { plaintextKey, encryptedKey };
  }

  public async decryptDataKey(encryptedKey: Buffer): Promise<Buffer> {
    const authTag = encryptedKey.subarray(encryptedKey.length - 16);
    const ciphertext = encryptedKey.subarray(0, encryptedKey.length - 16);

    const decipher = createDecipheriv('aes-256-gcm', this.kek, this.iv);
    decipher.setAuthTag(authTag);

    return Buffer.concat([decipher.update(ciphertext), decipher.final()]);
  }

  public destroy(): void {
    secureZeroize(this.kek);
  }
}
```

#### File: `src/crypto/envelope.ts`
```typescript
import { createCipheriv, createDecipheriv, randomBytes, CipherGCM, DecipherGCM } from 'node:crypto';
import { secureZeroize } from './core.js';
import { IKms } from './mock-kms.js';

export class EnvelopeHandler {
  constructor(private readonly kms: IKms) {}

  public async encryptMessage(message: string, contextAad: string): Promise<Buffer> {
    const { plaintextKey, encryptedKey } = await this.kms.generateDataKey();
    const iv = randomBytes(12);
    const aadBuffer = Buffer.from(contextAad, 'utf-8');
    const plaintextBuffer = Buffer.from(message, 'utf-8');

    try {
      const cipher = createCipheriv('aes-256-gcm', plaintextKey, iv) as CipherGCM;
      cipher.setAAD(aadBuffer);

      const ciphertext = Buffer.concat([cipher.update(plaintextBuffer), cipher.final()]);
      const authTag = cipher.getAuthTag();

      // Struktur data: [IV: 12B][Tag: 16B][DEK_Len: 2B][DEK: NB][Ciphertext: MB]
      const dekLenBuf = Buffer.alloc(2);
      dekLenBuf.writeUInt16BE(encryptedKey.length, 0);

      return Buffer.concat([iv, authTag, dekLenBuf, encryptedKey, ciphertext]);
    } finally {
      secureZeroize(plaintextKey);
      secureZeroize(plaintextBuffer);
    }
  }

  public async decryptMessage(payload: Buffer, contextAad: string): Promise<string> {
    const iv = payload.subarray(0, 12);
    const authTag = payload.subarray(12, 28);
    const dekLength = payload.readUInt16BE(28);
    const encryptedDek = payload.subarray(30, 30 + dekLength);
    const ciphertext = payload.subarray(30 + dekLength);

    const plaintextKey = await this.kms.decryptDataKey(encryptedDek);
    const aadBuffer = Buffer.from(contextAad, 'utf-8');

    try {
      const decipher = createDecipheriv('aes-256-gcm', plaintextKey, iv) as DecipherGCM;
      decipher.setAAD(aadBuffer);
      decipher.setAuthTag(authTag);

      const decrypted = Buffer.concat([decipher.update(ciphertext), decipher.final()]);
      const resultString = decrypted.toString('utf-8');
      
      secureZeroize(decrypted);
      return resultString;
    } finally {
      secureZeroize(plaintextKey);
    }
  }
}
```

#### File: `test/crypto.test.ts`
```typescript
import { test, describe, after } from 'node:test';
import assert from 'node:assert';
import { MockLocalKms } from '../src/crypto/mock-kms.js';
import { EnvelopeHandler } from '../src/crypto/envelope.js';
import { safeCompare } from '../src/crypto/core.js';

describe('Enterprise Cryptography Module Tests', () => {
  const kms = new MockLocalKms();
  const handler = new EnvelopeHandler(kms);

  after(() => {
    kms.destroy();
  });

  test('Enkripsi dan Dekripsi Sukses dengan AAD yang Cocok', async () => {
    const secret = '4532-0154-9988-1234';
    const aad = 'customer_uuid=usr_99x_abc';

    const packed = await handler.encryptMessage(secret, aad);
    const decrypted = await handler.decryptMessage(packed, aad);

    assert.strictEqual(decrypted, secret);
  });

  test('Dekripsi Wajib Gagal jika AAD Dirusak (Tampering Attack)', async () => {
    const secret = '4532-0154-9988-1234';
    const aadOriginal = 'customer_uuid=usr_99x_abc';
    const aadTampered = 'customer_uuid=usr_666_hacked';

    const packed = await handler.encryptMessage(secret, aadOriginal);

    await assert.rejects(
      async () => {
        await handler.decryptMessage(packed, aadTampered);
      },
      {
        message: /Unsupported state or unable to authenticate data/,
      }
    );
  });

  test('Constant-Time Comparison Validations', () => {
    const tokenA = Buffer.from('enterprise-auth-secret-123');
    const tokenB = Buffer.from('enterprise-auth-secret-123');
    const tokenC = Buffer.from('enterprise-auth-secret-456');

    assert.strictEqual(safeCompare(tokenA, tokenB), true);
    assert.strictEqual(safeCompare(tokenA, tokenC), false);
  });
});
```

---

### 13. Exercises

#### Level: Easy
1. Modifikasi fungsi `safeCompare` di `src/crypto/core.ts` agar menerima input berupa `string` secara langsung tanpa memicu memory leak pada konversi encoding internal.
2. Tuliskan skrip uji yang membuktikan bahwa pemanggilan `secureZeroize(buffer)` benar-benar mengubah seluruh nilai byte menjadi integer `0`.

#### Level: Medium
1. Implementasikan mekanisme **Key Rotation Hook** pada modul `MockLocalKms`. Modul harus mampu mengenkripsi DEK baru menggunakan *Current KEK*, namun masih mampu mendekripsi DEK lama yang di-wrap oleh *Previous KEK* dengan membaca *Key Version Identifier* (1 byte prefix).

#### Level: Hard
1. Buat custom middleware Fastify / Node.js HTTP server yang mengimplementasikan protokol **DPoP (Demonstrating Proof-of-Possession - RFC 9449)**:
   * Parse header `DPoP` (JWT).
   * Validasi public key yang dikirimkan klien dalam format JWK (`epk`).
   * Verifikasi signature token menggunakan algoritma asimetris `Ed25519` via `crypto.verify()`.
   * Validasi klaim `htm` (HTTP Method), `htu` (HTTP URI path), dan cegah Replay Attack menggunakan in-memory cache dengan TTL untuk `jti` (JWT ID).

---

### 14. Challenges (Mission-Critical Problem)

**Skenario**:
Anda adalah Principal Cryptographic Engineer di bursa kripto tier-1. Sistem cold/warm storage Anda membutuhkan Node.js engine yang mampu memproses penandatanganan transaksi (secp256k1 atau Ed25519) dengan throughput minimal 3.000 signature per detik. Namun, audit kepatuhan FIPS 140-3 menemukan bahwa:
1. Memory dump sewaktu-waktu yang dipicu oleh instruksi `SIGSEGV` atau core-dump runtime mengekspos potongan ephemeral private key yang dialokasikan di V8 Heap.
2. Instruksi GC V8 menunda pembersihan Buffer hingga 10 detik di bawah load tinggi.

**Target Tugas**:
Rancang arsitektur micro-engine (disertai pembuktian desain matematis & arsitektur kode) yang mengimplementasikan **Off-Heap Ephemeral Memory Allocator** menggunakan Node.js `worker_threads` atau native memory pinning (`mlock` via POSIX API bindings) di mana:
*   Buffer private key dialokasikan di halaman RAM yang terkunci (`mlock()`), sehingga tidak pernah ter-swap ke swapfile disk OS.
*   Signal handler (POSIX `SIGTERM`, `SIGINT`, `SIGSEGV`) mencegat process crash dan secara instan mengeksekusi penghapusan memori eksplisit sebelum process termination selesai.
*   Seluruh alur penandatanganan tidak menggunakan V8 Garbage Collector thread untuk deallokasi memori cryptographic secret.

---

### 15. Quiz Evaluasi Pemahaman

#### Sifat: Menantang & Konseptual

##### Kategori Basic
1. Mengapa fungsi `Math.random()` sangat dilarang keras untuk digunakan dalam pembuatan session token, IV, salt, atau secret cryptographic lainnya di Node.js?
   * *Jawaban Singkat*: `Math.random()` menggunakan algoritma pseudo-random deterministik (seperti xorshift128+) yang dirancang untuk kecepatan eksekusi, bukan entropi cryptographically secure (CSPRNG). State internalnya dapat diprediksi dengan mengobservasi urutan output sebelumnya. Wajib gunakan `crypto.randomBytes()`.
2. Apa tujuan keberadaan `authTag` pada mode cipher AEAD seperti AES-256-GCM?
   * *Jawaban Singkat*: Berfungsi sebagai MAC (Message Authentication Code) yang menjamin integritas (integrity) dan keaslian (authenticity) payload. Jika data ciphertext atau AAD diubah satu bit saja, proses dekripsi akan melempar exception error.
3. Berapa ukuran Nonce/IV yang dianjurkan oleh standar NIST SP 800-38D untuk mode operasi AES-GCM, dan mengapa?
   * *Jawaban Singkat*: 12 bytes (96 bits). Panjang ini diproses secara langsung oleh fungsi hash GHASH internal tanpa overhead kalkulasi hashing tambahan, memberikan efisiensi komputasi tertinggi dan keamanan terhadap collision.
4. Apa fungsi dari pemanggilan `crypto.timingSafeEqual` dibandingkan dengan operator perbandingan kesetaraan reguler `===`?
   * *Jawaban Singkat*: Mengeksekusi perbandingan byte dengan kompleksitas waktu konstan ($O(1)$ relatif terhadap panjang byte), mencegah kerentanan *timing side-channel attacks*.
5. Di manakah buffer hasil alokasi `Buffer.alloc()` berada di dalam memory management Node.js?
   * *Jawaban Singkat*: Dialokasikan di luar memori V8 Garbage Collector heap (*off-heap memory*), dikelola via `node::Buffer` melalui representasi native C++ pointer.

##### Kategori Intermediate
6. Mengapa `UV_THREADPOOL_SIZE` dapat menjadi bottleneck utama pada aplikasi Node.js yang memanggil fungsi `crypto.scrypt` secara asinkron dalam frekuensi tinggi?
   * *Jawaban Singkat*: Algoritma KDF asinkron dieksekusi di libuv worker pool. Default ukurannya hanya 4 thread. Request ke-5 dan seterusnya akan mengantre hingga salah satu worker selesai, memicu latensi tinggi jika terjadi lonjakan beban.
7. Apa perbedaan mendasar antara enkripsi simetris biasa dengan Envelope Encryption dalam konteks rotasi kunci skala enterprise?
   * *Jawaban Singkat*: Pada enkripsi simetris biasa, rotasi kunci mengharuskan pembacaan dan enkripsi ulang seluruh data di database. Pada Envelope Encryption, data dienkripsi dengan DEK unik, dan hanya DEK yang di-wrap oleh KEK. Saat rotasi, cukup re-wrap DEK menggunakan KEK baru tanpa menyentuh data ciphertext utama.
8. Bagaimana serangan Padding Oracle dapat terjadi pada cipher mode AES-CBC, dan bagaimana AES-GCM memitigasinya?
   * *Jawaban Singkat*: Padding oracle terjadi saat server mengekspos perbedaan error validasi padding PKCS#7 dan ciphertext error. AES-GCM adalah cipher berbasis counter (stream-like) tanpa padding bit dan dilengkapi auth-tag terintegrasi yang diverifikasi sebelum parsing payload.
9. Mengapa mengonversi Buffer rahasia menjadi JavaScript `string` (`buffer.toString('utf-8')`) dianggap sebagai anti-pattern keamanan memori tinggi?
   * *Jawaban Singkat*: String di engine V8 bersifat immutable. Anda tidak dapat melakukan zeroization (menimpa memorinya dengan byte 0). String tersebut tetap tersimpan di V8 Heap dan berpotensi terbaca saat proses crash dump atau memory inspection.
10. Apa kegunaan utama dari AAD (Additional Authenticated Data) dalam cipher AEAD?
    * *Jawaban Singkat*: Memungkinkan integritas metadata plaintext (misal: ID transaksi, header, tanggal) diverifikasi secara bersamaan dengan dekripsi ciphertext tanpa perlu mengenkripsi metadata tersebut.

##### Kategori Skenario Kasus Produksi
11. **Skenario 1**: Sebuah layanan API e-commerce mengalami spike latency dari 20ms ke 4.500ms saat kampanye flash sale. Log CPU menunjukkan core server mencapai 100%. Setelah ditelusuri, pengembang menggunakan middleware HMAC verification dengan kode:
    `crypto.createHmac('sha256', secret).update(body).digest('hex')`
    diikuti enkripsi AES sinkronik pada 50 field JSON terpisah per request.
    *Diagnosis dan Solusi*:
    * *Akar Masalah*: Melakukan puluhan operasi hashing sinkron dan serialisasi/deserialisasi string JSON secara berulang di main thread memblokir V8 event loop.
    * *Solusi*: Konsolidasi enkripsi; enkripsi satu payload JSON terkonsolidasi alih-alih per-field terpisah. Hindari parsing string berulang kali; gunakan buffer stream langsung ke OpenSSL layer.
12. **Skenario 2**: Sistem mTLS Node.js Anda menolak koneksi dari klien korporat valid dengan error `ERR_TLS_CERT_ALTNAME_INVALID`. Sertifikat klien diterbitkan oleh Internal CA perusahaan yang terkonfigurasi di properti `ca`.
    *Diagnosis dan Solusi*:
    * *Akar Masalah*: Node.js (via OpenSSL) secara default memvalidasi kecocokan hostname target dengan ekstensi `Subject Alternative Name (SAN)` pada sertifikat klien. Klien menggunakan sertifikat lama yang hanya menyematkan informasi di field `Common Name (CN)` tanpa SAN.
    * *Solusi*: Perbarui penerbitan sertifikat PKI klien untuk mematuhi RFC 5280 dengan menyertakan DNS/URI SAN, atau berikan opsi `checkServerIdentity: () => undefined` hanya jika validasi identitas dilakukan manual melalui fingerprint pinning.
13. **Skenario 3**: Terjadi insiden keamanan di mana database replika PostgreSQL bocor ke publik. Database tersebut memuat payload hasil enkripsi AES-256-GCM. Namun, attacker berhasil merekonstruksi data plain-text sebagian nasabah. Setelah audit kode, ditemukan fungsi:
    `const iv = Buffer.from(record.id.padStart(12, '0'));`
    *Diagnosis dan Solusi*:
    * *Akar Masalah*: Pelanggaran mutlak Cryptographic Nonce Reuse. Menggunakan record ID berurutan menghasilkan IV yang statis dan deterministik. Dua record berbeda yang dienkripsi menggunakan Key sama dan IV sama membocorkan relasi XOR ($C_1 \oplus C_2 = P_1 \oplus P_2$), membuka pemulihan plain-text.
    * *Solusi*: Ganti implementasi menjadi `randomBytes(12)` non-deterministik dan simpan IV unik tersebut bersamaan dengan ciphertext record.

---

### 16. Summary

*   Sub-sistem kriptografi Node.js adalah antarmuka ke C++ OpenSSL engine. Operasi symmetric cipher (AES/ChaCha) sangat cepat dieksekusi di event loop, sementara fungsi KDF komputasi tinggi terikat pada throughput libuv threadpool.
*   Pola **Envelope Encryption** menyelesaikan kompleksitas rotasi kunci skala enterprise dan kepatuhan regulasi (PCI-DSS, GDPR, HIPAA) dengan memisahkan Data Encryption Key (DEK) dan Key Encryption Key (KEK).
*   Keamanan memori V8 memerlukan disiplin ketat: data sensitif tidak boleh dikonversi ke tipe JavaScript `string`, melainkan harus ditampung dalam off-heap `Buffer` yang wajib di-**zeroize** secara eksplisit di blok `finally`.
*   Zero-Trust pada arsitektur microservices modern diwujudkan melalui validasi Mutual TLS tingkat lanjut (mTLS) hingga tingkat proses Node.js, dipadukan dengan mitigasi serangan timing attack menggunakan `crypto.timingSafeEqual`.