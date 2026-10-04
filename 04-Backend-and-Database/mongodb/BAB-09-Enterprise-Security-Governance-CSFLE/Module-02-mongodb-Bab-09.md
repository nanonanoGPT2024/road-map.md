# Kurikulum Enterprise MongoDB: Arsitektur Keamanan Lanjutan & Tata Kelola Data

*   **Jalur**: Backend & Database Engineering (`04-Backend-and-Database`)
*   **Bab**: 09 — *Enterprise Security Governance & Client-Side Field Level Encryption (CSFLE)*
*   **Modul**: 02 — *Deep Dive, Implementasi Lanjutan & Arsitektur Produksi*
*   **Target Audiens**: Senior Backend Engineer, Lead Database Administrator, Enterprise Data Architect

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Mengonseptualisasikan dan Menganalisis** arsitektur kriptografi internal CSFLE (Client-Side Field Level Encryption) dan Queryable Encryption (QE), mencakup Key Hierarchies (CMK/KEK vs. DEK) serta protokol komunikasi driver dengan engine enkripsi.
2. **Mengeliminasi Ketergantungan Legacy Process** dengan mengganti proses `mongocryptd` menggunakan library dinamis C-based `crypt_shared` pada lingkungan runtime Linux/Container berkinerja tinggi.
3. **Mengintegrasikan Enterprise Key Management Service (KMS)** (seperti AWS KMS, GCP Cloud KMS, atau HashiCorp Vault) ke dalam pipeline runtime Node.js/TypeScript secara nir-hambatan (*seamless*) dengan mekanisme *DEK Caching*.
4. **Mendesain dan Mengimplementasikan Skema Enkripsi Deklaratif** berbasis BSON `$jsonSchema` server-side enforcement untuk mencegah masuknya data *plaintext* akibat kesalahan konfigurasi sisi klien.
5. **Mengeksekusi Operasi Rotasi Kunci Kriptografi (Key Re-wrapping)** pada Data Encryption Keys (DEK) tanpa downtime operasional aplikasi (*zero-downtime key lifecycle management*).
6. **Mendiagnosis dan Mengatasi *Bottleneck* Performa** yang timbul dari latensi KMS, *CPU throttling* saat proses enkripsi/dekripsi masif, serta limitasi pengindeksan data terenkripsi.

---

## 2. Prerequisites

Sebelum mempelajari modul ini, peserta wajib memahami:
*   Mekanisme otentikasi dan otorisasi enterprise MongoDB (SCRAM-SHA-256, x.509 PKI, LDAP/Kerberos).
*   Arsitektur dasar BSON, pemanfaatan WiredTiger storage engine, dan pipeline agregasi MongoDB.
*   Pemahaman kriptografi simetris/asimetris: Enkripsi AEAD (AES-256-GCM), HMAC-SHA-512, Initialization Vector (IV), *Envelope Encryption*.
*   Pemrograman Node.js/TypeScript tingkat lanjut (Asynchronous execution, Worker threads, Buffer & Stream manipulation).
*   Dasar interaksi IAM & Cloud KMS (AWS IAM Policy/Role, KMS Key ARN, atau HashiCorp Vault AppRole).

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Envelope Encryption & Key Hierarchy

Keamanan tingkat tinggi pada CSFLE dan Queryable Encryption mengadopsi pola **Envelope Encryption**:

```
+-----------------------------------------------------------------------+
| Key Encryption Key (KEK) / Customer Master Key (CMK)                  |
| - Lokasi: Hardware Security Module (HSM) / Enterprise Cloud KMS       |
| - Sifat: Tidak pernah meninggalkan batas aman KMS                      |
+-----------------------------------+-----------------------------------+
                                    | Dienkripsi oleh KMS
                                    v
+-----------------------------------------------------------------------+
| Data Encryption Key (DEK)                                             |
| - Lokasi: Database `admin.datakeys` (tersimpan dalam bentuk ciphertext)|
| - Sifat: Didekripsi oleh Driver via KMS, dicache di memori klien      |
+-----------------------------------+-----------------------------------+
                                    | Dienkripsi oleh Driver
                                    v
+-----------------------------------------------------------------------+
| Sensitive Field Plaintext (e.g., Nomor Kartu Kredit, NIK, Gaji)       |
| - Lokasi: In-Flight Network & Disk Storage MongoDB Server             |
| - Sifat: Tersimpan sebagai BSON Binary Subtype 6 (Ciphertext)         |
+-----------------------------------------------------------------------+
```

1.  **Customer Master Key (CMK/KEK)**: Berada di dalam KMS (AWS KMS, GCP KMS, Azure Key Vault, HashiCorp Vault Transit Engine). Driver MongoDB mengirimkan DEK terenkripsi ke KMS via API call untuk didekripsi menjadi *plaintext* DEK di dalam memori driver.
2.  **Data Encryption Key (DEK)**: Dibuat secara acak dengan entropi tinggi (kunci simetris 96-byte: 32 bytes AES-256 key, 32 bytes HMAC-SHA-512 key, 32 bytes IV material). DEK disimpan dalam koleksi *Key Vault* (secara default `encryption.__keyVault`) dalam status terenkripsi oleh KEK.

### 3.2 CSFLE vs. Queryable Encryption (QE)

*   **CSFLE (Client-Side Field Level Encryption)**:
    *   *Deterministic Encryption*: Nilai input yang sama selalu menghasilkan *ciphertext* yang sama untuk DEK yang sama. Memungkinkan query kesetaraan (`$eq`), namun rentan terhadap analisis frekuensi (*frequency analysis attack*).
    *   *Randomized Encryption*: Menggunakan IV acak untuk setiap enkripsi. Dua plaintext yang identik menghasilkan ciphertext yang sama sekali berbeda. Sangat aman, tetapi **tidak dapat di-query** sama sekali kecuali di-decrypt seluruhnya di client side.
*   **Queryable Encryption (QE)**:
    *   Generasi terbaru (MongoDB 6.0/7.0+) menggunakan teknik kriptografi mutakhir (*Structured Encryption* / *Fast Searchable Symmetric Encryption*).
    *   Mendukung pencarian kesetaraan (`Equality`) pada ciphertext terenkripsi acak tanpa membocorkan pola frekuensi data.
    *   Mendukung evaluasi *Range* dan *Prefix/Suffix* queries (pada versi MongoDB mutakhir) langsung pada data terenkripsi di server menggunakan skema struktur data terenkripsi pendukung (`enxcol_.*` collections: internal state, lookup table, insert/update compaction tokens).

### 3.3 Engine Driver: `mongocryptd` vs. `crypt_shared`

Driver resmi MongoDB membutuhkan pustaka logika kriptografis untuk mem-parsing dokumen BSON, menentukan *field* mana yang wajib dienkripsi via schema map, dan menyusun ciphertext token.

| Aspek | Legacy: `mongocryptd` | Modern Enterprise: `crypt_shared` |
| :--- | :--- | :--- |
| **Bentuk Distribusi** | Standalone Executable Binary | Dynamic Shared Object (`.so` / `.dylib` / `.dll`) |
| **Mekanisme Komunikasi**| IPC / Local Network Loopback Socket | Native In-Process FFI (Foreign Function Interface) |
| **Overhead Operasional**| Harus di-spawn, diawasi (PID monitoring), boros RAM | Dimuat langsung ke dalam address space driver |
| **Latensi per Operasi** | Tinggi (terdapat network hop & serialisasi internal) | Ekstrem rendah (direct C-memory access) |
| **Produksi Standar** | *Deprecated untuk implementasi baru* | **Mandatori (Production Standard)** |

---

## 4. Why & What

### Mengapa Perlu CSFLE / Queryable Encryption?
*   **Model Zero-Trust Storage**: Database Administrator (DBA), Cloud Infrastructure Provider (AWS, GCP, Atlas), dan penyerang yang mengeksploitasi celah file system (`/data/db`), memory dump, maupun packet sniffer pada transport wire **tidak dapat membaca data asli**. Data tiba di MongoDB sudah dalam bentuk *ciphertext*.
*   **Kepatuhan Regulasi Ekstrem**: Memenuhi klausul ketat PCI-DSS 4.0 (Primary Account Number masking & encryption), HIPAA (ePHI), GDPR (Right to be Forgotten via *Crypto-Shredding*), dan UU Pelindungan Data Pribadi (UU PDP).
*   **Crypto-Shredding**: Untuk menghapus data spesifik pengguna secara permanen dan instan (GDPR), aplikasi cukup menghapus DEK milik pengguna tersebut dari Key Vault. Data terenkripsi di database secara matematis menjadi *unrecoverable noise* selamanya, tanpa perlu menjalankan `deleteMany` masif pada disk.

---

## 5. How (Workflow Detail)

### 5.1 Siklus Operasi Tulis (Write Path)

```
[Aplikasi / Client]
       │
       ▼
 1. Driver mengevaluasi Skema Enkripsi (Schema Map / Server $jsonSchema)
       │
       ▼
 2. Driver memeriksa Local DEK Cache di memory.
    - IF DEK Cache Miss:
        Driver membaca encrypted DEK dari collection 'keyVault'.
        Driver memanggil API KMS (e.g., `kms:Decrypt`) -> KMS mengembalikan Plaintext DEK.
        Driver menyimpan Plaintext DEK di in-memory cache dengan TTL tertentu.
    - IF DEK Cache Hit:
        Gunakan Plaintext DEK dari memory.
       │
       ▼
 3. Native library `crypt_shared` mengenkripsi plaintext field -> BSON Binary Subtype 6.
       │
       ▼
 4. Driver memaketkan BSON dokumen baru (field sensitif terenkripsi, non-sensitif plaintext).
       │
       ▼
 5. Driver mengirimkan command `insert` / `update` over TLS ke Mongod Cluster.
       │
       ▼
[MongoDB Engine (mongod)]
       │
       ▼
 6. Menulis dokumen ke WiredTiger engine (data terenkripsi di disk & server RAM).
```

### 5.2 Siklus Operasi Baca (Read Path)

```
[Aplikasi / Client]
       │
       ▼
 1. Driver membuat read query (e.g., { ssn: "001-23-4567" }).
       │
       ▼
 2. `crypt_shared` mengenkripsi nilai filter menggunakan DEK terkait (Deterministic atau QE Token).
       │
       ▼
 3. Query dengan nilai filter terenkripsi dikirim ke MongoDB over TLS.
       │
       ▼
[MongoDB Engine (mongod)]
       │
       ▼
 4. Mongod mencocokkan filter terenkripsi dengan indeks/dokumen di storage engine.
 5. Mongod mengembalikan dokumen hasil (masih berbentuk ciphertext) ke Driver.
       │
       ▼
[Aplikasi / Client]
       │
       ▼
 6. Driver menerima dokumen BSON.
 7. `crypt_shared` mengekstraksi Binary Subtype 6, mendekripsinya menggunakan DEK lokal,
    dan mengonversi kembali ke BSON plaintext.
 8. Plaintext object diserahkan ke kode aplikasi.
```

---

## 6. Analogy & Diagram ASCII

### Analogi Brankas Diplomatik
Bayangkan Anda mengirimkan dokumen negara melalui jasa kurir (MongoDB). 
*   **Enkripsi Tradisional (At-Rest)**: Kurir membawa map transparan, tetapi mobil boks kurir tersebut terkunci gembok baja. Jika sopir boks (DBA) berkhianat, ia bisa membuka mobil dan membaca isi map.
*   **CSFLE (Client-Side Encryption)**: Anda meletakkan dokumen ke dalam brankas mini titanium anti-peluru berkunci biometrik Anda (DEK), lalu brankas mini tersebut dimasukkan ke dalam koper diplomatik (TLS). Kurir menerima brankas mini titanium tersebut dan menyimpannya di gudang (WiredTiger). Kurir maupun pengelola gudang tidak pernah memiliki kunci brankas mini tersebut; mereka hanya memindahkan kotak baja yang tidak dapat mereka intip isinya.

```
       ARSTIEKTUR PRODUCTION-GRADE CSFLE DENGAN CRYPT_SHARED & KMS
       
 +-------------------------------------------------------------------+
 | APPLICATION RUNTIME LAYER (Node.js / Go / Java Service)          |
 |                                                                   |
 |  +-------------------------------------------------------------+  |
 |  | MongoDB Official Driver                                     |  |
 |  |                                                             |  |
 |  |  +---------------------+        +-------------------------+ |  |
 |  |  | In-Memory DEK Cache |        | crypt_shared (.so/.dll) | |  |
 |  |  |  (TTL Management)   |        |  (Native Dynamic Lib)   | |  |
 |  |  +----------▲----------+        +------------▲------------+ |  |
 |  +-------------┼--------------------------------┼--------------+  |
 +----------------┼────────────────────────────────┼-----------------+
                  │ 2. Decrypt DEK                  │ 3. In-Memory
                  │    Request                     │    Encryption
                  ▼                                │
       +--------------------+                      │
       | ENTERPRISE KMS     |                      │
       | (AWS KMS / Vault)  |                      │
       |                    |                      │
       | [Customer Master]  |                      │
       | [   Key (CMK)   ]  |                      │
       +--------------------+                      │
                                                   ▼
 +-------------------------------------------------------------------+
 | NETWORK LAYER (mTLS 1.3 Transport)                                |
 | Data In-Transit: Payload BSON sudah berisi Ciphertext Subtype 6   |
 +----------------------------------▲--------------------------------+
                                    │
                                    │ 4. Read/Write Wire Protocol
                                    ▼
 +-------------------------------------------------------------------+
 | MONGODB CLUSTER (mongod / mongos)                                 |
 |                                                                   |
 |  +---------------------------------+  +------------------------+  |
 |  | Database: 'finance_db'          |  | Database: 'encryption' |  |
 |  | Collection: 'transactions'      |  | Collection:            |  |
 |  |                                 |  | '__keyVault'           |  |
 |  | [ssn: BinData(6, "a8f9c1...")]  |  |                        |  |
 |  | [amount: 50000000.00 (plain)]   |  | Stores Encrypted DEKs  |  |
 |  +---------------------------------+  +------------------------+  |
 |                                                                   |
 |  +-------------------------------------------------------------+  |
 |  | WiredTiger Storage Engine (Encrypted-at-Rest as 2nd barrier)|  |
 |  +-------------------------------------------------------------+  |
 +-------------------------------------------------------------------+
```

---

## 7. Simple & Practical Implementations

Berikut adalah implementasi enterprise menggunakan **TypeScript** dan driver resmi `mongodb` dengan integrasi `mongodb-client-encryption`.

### 7.1 Simple Example: Skema Enkripsi Sisi Klien (Schema Definition)

```typescript
// schema.ts
export const patientSchemaMap = {
  "medical_records.patients": {
    bsonType: "object",
    properties: {
      patientId: { bsonType: "string" },
      medicalCondition: {
        // Enkripsi Acak: Perlindungan tertinggi, tidak bisa di-query
        encrypt: {
          bsonType: "string",
          algorithm: "AEAD_AES_256_CBC_HMAC_SHA_512-Random"
        }
      },
      nationalId: {
        // Enkripsi Deterministik: Memungkinkan indexing dan pencarian kesetaraan ($eq)
        encrypt: {
          bsonType: "string",
          algorithm: "AEAD_AES_256_CBC_HMAC_SHA_512-Deterministic"
        }
      }
    }
  }
};
```

### 7.2 Practical Example: Production-Ready Client CSFLE dengan AWS KMS Mock/Real

```typescript
// csfle-production-service.ts
import { MongoClient, ClientEncryption, Binary } from "mongodb";
import * as path from "path";

// 1. Definisi Tipe dan Interface Konfigurasi
interface KmsConfiguration {
  kmsProvider: "aws" | "local";
  credentials: {
    aws?: {
      accessKeyId: string;
      secretAccessKey: string;
      sessionToken?: string;
    };
    local?: {
      key: Buffer; // 96-byte Cryptographic Master Key for simulation
    };
  };
  keyArn?: string;
  keyVaultNamespace: string;
}

export class EnterpriseSecureStorage {
  private baseClient: MongoClient;
  private secureClient: MongoClient | null = null;
  private clientEncryption: ClientEncryption | null = null;
  private readonly config: KmsConfiguration;
  private readonly mongoUri: string;

  constructor(mongoUri: string, config: KmsConfiguration) {
    this.mongoUri = mongoUri;
    this.config = config;
    this.baseClient = new MongoClient(this.mongoUri);
  }

  public async initialize(): Promise<void> {
    await this.baseClient.connect();
    
    // Pastikan index unik pada Key Vault Collection sesuai standar MongoDB Enterprise
    const [dbName, collName] = this.config.keyVaultNamespace.split(".");
    const keyVaultDb = this.baseClient.db(dbName);
    await keyVaultDb.collection(collName).createIndex(
      { keyAltNames: 1 },
      { 
        unique: true, 
        partialFilterExpression: { keyAltNames: { $exists: true } } 
      }
    );

    // Siapkan driver client encryption helper
    this.clientEncryption = new ClientEncryption(this.baseClient, {
      keyVaultNamespace: this.config.keyVaultNamespace,
      kmsProviders: this.getKmsProviderPayload()
    });

    // Inisialisasi atau temukan DEK
    const dekId = await this.ensureDataEncryptionKey("pii-financial-dek");

    // Definisikan Skema Validasi Enkripsi Programatik
    const schemaMap = {
      "enterprise_bank.accounts": {
        bsonType: "object",
        encryptMetadata: {
          keyId: [dekId] // Bind field yang terenkripsi ke DEK yang telah digenerate
        },
        properties: {
          taxNumber: {
            encrypt: {
              bsonType: "string",
              algorithm: "AEAD_AES_256_CBC_HMAC_SHA_512-Deterministic"
            }
          },
          bankBalance: {
            encrypt: {
              bsonType: "double",
              algorithm: "AEAD_AES_256_CBC_HMAC_SHA_512-Random"
            }
          }
        }
      }
    };

    // Konfigurasi MongoClient Otomatis Enkripsi dengan 'crypt_shared'
    this.secureClient = new MongoClient(this.mongoUri, {
      autoEncryption: {
        keyVaultNamespace: this.config.keyVaultNamespace,
        kmsProviders: this.getKmsProviderPayload(),
        schemaMap: schemaMap,
        // PRODUCTION: Arahkan langsung ke dynamic library crypt_shared untuk performa maksimal
        extraOptions: {
          cryptSharedLibPath: process.env.CRYPT_SHARED_PATH || "/usr/lib/mongo_crypt_v1.so",
          cryptSharedLibRequired: true // Hard fail jika binary native tidak ditemukan
        }
      }
    });

    await this.secureClient.connect();
    console.log("[SECURITY] Secure Auto-Encrypt Client Initialized using crypt_shared.");
  }

  private getKmsProviderPayload(): any {
    if (this.config.kmsProvider === "aws") {
      return {
        aws: {
          accessKeyId: this.config.credentials.aws!.accessKeyId,
          secretAccessKey: this.config.credentials.aws!.secretAccessKey,
          sessionToken: this.config.credentials.aws!.sessionToken
        }
      };
    }
    return {
      local: {
        key: this.config.credentials.local!.key
      }
    };
  }

  private async ensureDataEncryptionKey(keyAltName: string): Promise<Binary> {
    if (!this.clientEncryption) throw new Error("ClientEncryption not initialized");

    const existingKey = await this.baseClient
      .db(this.config.keyVaultNamespace.split(".")[0])
      .collection(this.config.keyVaultNamespace.split(".")[1])
      .findOne({ keyAltNames: keyAltName });

    if (existingKey) {
      return existingKey._id as Binary;
    }

    console.log(`[SECURITY] Generating new DEK with identifier: ${keyAltName}`);
    let masterKeyParam: any = undefined;
    
    if (this.config.kmsProvider === "aws") {
      masterKeyParam = {
        key: this.config.keyArn,
        region: "ap-southeast-1"
      };
    }

    return await this.clientEncryption.createDataKey(this.config.kmsProvider, {
      masterKey: masterKeyParam,
      keyAltNames: [keyAltName]
    });
  }

  public getSecureDatabase(name: string) {
    if (!this.secureClient) throw new Error("Instance not initialized");
    return this.secureClient.db(name);
  }

  public async close(): Promise<void> {
    await this.baseClient.close();
    if (this.secureClient) await this.secureClient.close();
  }
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Financial Core API - PT. FinTek Nusantara Transaksi
*   **Profil Beban**: 12.000 Transaksi per Detik (TPS), 400 Juta Dokumen Akun, Regulasi Standar BI & PCI-DSS Tier 1.
*   **Permasalahan**: Auditor mewajibkan dekripsi *Primary Account Number (PAN)* dan *Customer Balance* tidak boleh dapat dilakukan oleh staf Internal Infrastructure/SysAdmin, bahkan jika instance database dicuri secara fisik.
*   **Implementasi Arsitektur**:
    1.  *Multi-Region Envelope Encryption*: Menggunakan **AWS KMS Multi-Region Keys** (`arn:aws:kms:ap-southeast-1:xxx:key/mrk-...` direplikasi ke `ap-southeast-3`).
    2.  *Connection Pooling Separation*: Arsitektur microservices memisahkan *Payment Service* (memiliki akses IAM KMS untuk dekripsi) dan *Reporting Service* (sama sekali tidak diberi hak IAM `kms:Decrypt`). Ketika Reporting Service membaca database MongoDB, field PAN dan Balance tetap terlihat sebagai Binary Subtype 6 acak tanpa beban komputasi server.
    3.  *Mengatasi KMS Bottleneck*: Driver mengimplementasikan caching Plaintext DEK in-memory. Tanpa caching, 12.000 TPS akan memicu 12.000 network requests/detik ke AWS KMS, yang berakibat pada pembengkakan tagihan puluhan ribu dolar dan KMS HTTP 429 *Throttling Exception*.

---

## 9. Trade-offs: Analisis Biaya, Performa & Skalabilitas

| Komponen | Baseline (Unencrypted) | CSFLE Deterministic | CSFLE Randomized | Queryable Encryption (QE) |
| :--- | :--- | :--- | :--- | :--- |
| **Throughput (Writes)** | 100% | ~80 - 85% | ~85 - 90% | ~60 - 75% |
| **Storage Engine Overhead** | Baseline BSON | BSON Binary overhead (~2x size) | BSON Binary overhead (~2x size) | Metadata Index overhead (3x-5x index size) |
| **CPU Footprint (Client)** | Sangat Rendah | Sedang (AES-GCM-HMAC calculation) | Sedang (AES-GCM cipher generation) | Tinggi (Structured Cryptographic Primitives) |
| **Queryability** | Penuh (Range, Regex, Eq) | Hanya `$eq`, `$in`, `$ne` | **None** (Blind Read Only) | `$eq`, Range, Prefix (MongoDB 7+) |
| **KMS Cost Impact** | $0 | Rendah (selama DEK dicache di RAM) | Rendah (selama DEK dicache di RAM) | Rendah (selama DEK dicache di RAM) |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Mengandalkan Fallback `mongocryptd` di Lingkungan Produksi
*   *Gejala*: Aplikasi sering mengalami timeout saat lonjakan koneksi baru, memory container membengkak secara tidak terkontrol akibat spawn subproses OS berulang kali.
*   *Root Cause*: `cryptSharedLibRequired` diatur ke `false` atau tidak disetel, sementara binary `mongo_crypt_v1.so` tidak ditemukan pada `LD_LIBRARY_PATH`. Driver secara otomatis fallback men-spawn daemon `mongocryptd`.
*   *Solusi*: Terapkan flag `cryptSharedLibRequired: true` pada `autoEncryption.extraOptions`. Pastikan *Dockerfile* production mengunduh package `mongodb-crypt-library` resmi dan memuat path yang valid.

### 10.2 Server-Side Data Leakage Melalui Plaintext Injection
*   *Gejala*: Dokumen masuk ke collection dalam bentuk teks polos (unencrypted string), padahal client auto-encryption sudah disiapkan.
*   *Root Cause*: Ada microservice lama atau admin yang mengakses cluster menggunakan Mongo shell biasa atau driver tanpa konfigurasi schema map.
*   *Solusi*: **Wajib** terapkan *Server-Side `$jsonSchema` Validation* langsung pada MongoDB Server yang menolak field mentah non-Binary.

```javascript
// Dijalankan di mongosh oleh Admin
db.runCommand({
  collMod: "accounts",
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["taxNumber"],
      properties: {
        taxNumber: {
          bsonType: "binData", // MENOLAK STRING! Hanya menerima ciphertext binary subtype 6
          description: "taxNumber MUST be encrypted before reaching the server"
        }
      }
    }
  },
  validationLevel: "strict",
  validationAction: "error"
});
```

---

## 11. Best Practices (Production Checklist)

- [ ] **Native Dynamic Library Binding**: Gunakan pustaka resmi `crypt_shared` berpasangan dengan versi MongoDB Server Anda. Tinggalkan `mongocryptd`.
- [ ] **Isolasi Database Key Vault**: Pisahkan namespace Key Vault (misal: `__keyVaultStore.__keys`) dari collection data bisnis. Terapkan RBAC ketat: Aplikasi reguler hanya boleh `read`, sedangkan provisioning pipeline boleh `write/createDataKey`.
- [ ] **Server-Side Enforcement**: Jangan hanya mempercayakan enkripsi pada client schema map. Konfigurasikan Server-side `$jsonSchema` validator dengan `bsonType: "binData"`.
- [ ] **KMS Latency Resiliency**: Terapkan *exponential backoff* dan retry logic pada level KMS client. Tempatkan KMS Key pada region yang identik dengan application worker untuk meminimalkan *Round Trip Time* (RTT).
- [ ] **Audit Key Lifecycle**: Terapkan mekanisme rotasi DEK berkala menggunakan fungsi `rewrapManyDataKey`.

---

## 12. Hands-on Practice: Membangun Production CSFLE Engine

Langkah-langkah berikut didesain untuk dieksekusi langsung pada folder praktikum `hands-on/m02/`.

### Langkah 1: Persiapan Lingkungan & Docker
Buat file `hands-on/m02/docker-compose.yml`:

```yaml
version: '3.8'
services:
  mongodb-enterprise:
    image: mongo:7.0
    container_name: mongo-csfle-node
    environment:
      MONGO_INITDB_DATABASE: enterprise_bank
    ports:
      - "27017:27017"
    command: ["--bind_ip_all"]
```

Jalankan:
```bash
docker compose -f hands-on/m02/docker-compose.yml up -d
```

### Langkah 2: Setup Project & Dependency Engine
Inisialisasi workspace Node.js di dalam `hands-on/m02/`:
```bash
cd hands-on/m02/
npm init -y
npm install mongodb mongodb-client-encryption dotenv
npm install -D typescript @types/node tsx
npx tsc --init
```

Unduh binary `crypt_shared` yang sesuai dengan OS Anda dari portal resmi MongoDB Community Crypt Library, simpan path lokasinya (misal `/opt/mongo/lib/mongo_crypt_v1.so` atau letakkan pada root hands-on sebagai `mongo_crypt_v1.so`).

### Langkah 3: Eksekusi Kode Ingestion dan Verifikasi Storage
Buat script `hands-on/m02/run-test.ts`:

```typescript
import { EnterpriseSecureStorage } from "./csfle-production-service";
import crypto from "crypto";
import { MongoClient } from "mongodb";

async function main() {
  // Simulasi KEK Local 96-Byte Cryptographic Secure Random Key
  const localMasterKey = crypto.randomBytes(96);
  const MONGO_URI = "mongodb://localhost:27017";

  const storageService = new EnterpriseSecureStorage(MONGO_URI, {
    kmsProvider: "local",
    credentials: { local: { key: localMasterKey } },
    keyVaultNamespace: "encryption.__keyVault"
  });

  await storageService.initialize();

  const db = storageService.getSecureDatabase("enterprise_bank");
  const accounts = db.collection("accounts");

  // Bersihkan data lama
  await accounts.deleteMany({});

  console.log("[TEST] Menyimpan dokumen melalui Secure CSFLE Client...");
  await accounts.insertOne({
    accountHolder: "Budi Santoso",
    taxNumber: "09.123.456.7-001.000", // Harus terenkripsi (Deterministic)
    bankBalance: 125000000.50          // Harus terenkripsi (Random)
  });

  console.log("[TEST] Membaca data menggunakan Secure CSFLE Client (Auto-Decrypt):");
  const readSecured = await accounts.findOne({ taxNumber: "09.123.456.7-001.000" });
  console.log("Output Decrypted:", readSecured);

  // Verifikasi Integritas Data di Sisi Server Database (Raw Unencrypted View)
  console.log("\n[VERIFIKASI SERVER-SIDE] Membaca langsung via Base Unencrypted Driver:");
  const plainClient = new MongoClient(MONGO_URI);
  await plainClient.connect();
  const rawDocument = await plainClient.db("enterprise_bank").collection("accounts").findOne({});
  
  console.log("Raw Stored Payload:");
  console.dir(rawDocument, { depth: null });

  await plainClient.close();
  await storageService.close();
}

main().catch(console.error);
```

Jalankan script:
```bash
npx tsx hands-on/m02/run-test.ts
```

---

## 13. Exercises

### Level: Easy
1. Modifikasi script `run-test.ts` untuk mencoba query pencarian kesetaraan (`$eq`) pada field `bankBalance`. Amati apa yang terjadi pada runtime!
   * *Pertanyaan*: Mengapa pencarian tersebut melemparkan error atau mengembalikan nilai `null`? Konsep CSFLE apa yang membatasinya?

### Level: Medium
2. Buat skrip automasi `key-rotation.ts` menggunakan method `ClientEncryption.rewrapManyDataKey()`. Simulasikan pergantian Master Key Lokal baru tanpa mendekripsi seluruh koleksi data bisnis di `enterprise_bank.accounts`.

### Level: Hard
3. Bangun implementasi *Multi-Tenant Data Encryption*:
   * Rancang arsitektur di mana Tenant A dan Tenant B berbagi database dan collection yang sama (`saas_db.orders`), namun masing-masing tenant memiliki DEK yang terpisah (`dek_tenant_a` dan `dek_tenant_b`).
   * Tulis middleware TypeScript yang mencegat operasi insert dan memilih DEK yang tepat secara dinamis berdasarkan context `tenantId` yang sedang aktif saat runtime.

---

## 14. Real-World Architecture Challenge

**Konteks Tantangan**:
Anda adalah Principal Data Architect di sebuah platform HealthTech Nasional. Platform Anda saat ini menyimpan 50 Juta rekam medis pasien di koleksi `records_v1` dalam keadaan plaintext. Sistem beroperasi 24/7 dengan batas toleransi downtime maksimum adalah **0 detik (Zero-Downtime Migration)**.

**Persyaratan Solusi**:
1. Rancang blueprint arsitektur dan strategi deployment untuk memigrasikan database plaintext tersebut menjadi **Queryable Encryption (QE)** / CSFLE.
2. Selesaikan masalah migrasi bertahap (*Dual-Write and Lazy-Migration pattern*): Bagaimana sistem membaca dokumen yang sebagian sudah terenkripsi dan sebagian masih plaintext selama masa transisi?
3. Jelaskan strategi *Rollback plan* jika pada pertengahan proses migrasi, AWS KMS mengalami gangguan regional (disaster recovery strategy).
4. Susun implementasi logic *Zero-Downtime Dual-Write Worker* dalam bentuk pseudocode arsitektural.

---

## 15. Evaluasi Pemahaman

### 15.1 Basic (Pilihan Ganda)
1. Apa subtype BSON resmi yang digunakan oleh MongoDB untuk menandai field ciphertext CSFLE?
   * A. Subtype 0 (Generic Binary)
   * B. Subtype 4 (UUID)
   * C. Subtype 6 (Encrypted BSON value)
   * D. Subtype 7 (Encrypted Sensitive String)
2. Manakah algoritma enkripsi CSFLE yang memungkinkan kita melakukan query pencarian kesetaraan (`$eq`)?
   * A. `AEAD_AES_256_CBC_HMAC_SHA_512-Random`
   * B. `AEAD_AES_256_CBC_HMAC_SHA_512-Deterministic`
   * C. `RSA_4096_OAEP`
   * D. `ChaCha20-Poly1305`
3. Di mana letak penyimpanan fisik Customer Master Key (CMK) pada implementasi CSFLE standar enterprise?
   * A. Pada collection `admin.keys` di MongoDB Server.
   * B. Di dalam file konfigurasi `mongod.conf`.
   * C. Di dalam Hardware Security Module (HSM) atau Cloud KMS eksternal.
   * D. Di-hardcode pada environment variable `crypt_shared`.
4. Mengapa pustaka `crypt_shared` lebih direkomendasikan untuk cluster produksi dibandingkan binary `mongocryptd`?
   * A. Karena `crypt_shared` mengabaikan TLS handshake.
   * B. Karena `crypt_shared` berjalan in-process memory via C-binding tanpa IPC socket overhead.
   * C. Karena `crypt_shared` gratis sedangkan `mongocryptd` berbayar.
   * D. Karena `crypt_shared` tidak memerlukan integrasi KMS.
5. Apa konsekuensi keamanan jika kita memilih algoritma *Deterministic Encryption* pada field dengan nilai yang variasi kardinalitasnya rendah (misal: field Jenis Kelamin: 'M' / 'F')?
   * A. Terjadi kebocoran kunci enkripsi utama.
   * B. Rentan terhadap serangan analisis frekuensi (*Frequency Analysis Attack*).
   * C. Performa penulisan drop drastis hingga 90%.
   * D. Muncul error BSON document size validation.

### 15.2 Intermediate (Analisis Kasus Singkat)
6. Sebuah tim microservice mengeluhkan performa aplikasi mereka drop drastis saat mengaktifkan CSFLE, dan tagihan bulanan AWS KMS membengkak drastis hingga ribuan dolar. Apa kesalahan arsitektural fatal yang hampir pasti dilakukan oleh tim tersebut?
7. Bagaimana cara kerja konsep *Crypto-Shredding* untuk memenuhi hak penghapusan data GDPR secara instan?
8. Bisakah kita membuat indeks compound pada field yang dienkripsi menggunakan algoritma `Randomized`? Jelaskan alasannya.
9. Jelaskan peran collection `encryption.__keyVault` dan bagaimana pola pengindeksan terbaik yang direkomendasikan oleh MongoDB!
10. Apa yang akan terjadi jika sebuah aplikasi mencoba menulis data plaintext string ke collection yang telah diproteksi validator `$jsonSchema` server-side dengan aturan `bsonType: "binData"`?

### 15.3 Skenario Produksi Kompleks
11. **Skenario Disaster Recovery KMS**:
    Aplikasi pembayaran Anda menggunakan AWS KMS di Region Singapore (`ap-southeast-1`). Terjadi pemadaman total (*total regional outage*) pada seluruh data center AWS di Singapore. Jelaskan bagaimana Anda mendesain arsitektur key redundancy agar aplikasi yang beralih ke Disaster Recovery site di Jakarta (`ap-southeast-3`) tetap dapat mendekripsi data tanpa harus mengutak-atik dokumen yang telah tersimpan di MongoDB!
12. **Skenario Schema Evolution**:
    Sebuah collection yang sudah berisi 100 juta record terenkripsi CSFLE membutuhkan penambahan satu field sensitif baru (misal: `phoneNumber`). Bagaimana strategi Anda memodifikasi `schemaMap` pada kode aplikasi tanpa memutus kompatibilitas (*backward compatibility*) dengan dokumen-dokumen lama yang belum memiliki field tersebut?
13. **Skenario Range Query on Encrypted Data**:
    Manajemen membutuhkan fitur pencarian rentang saldo rekening (`bankBalance` antara 10 Juta s/d 50 Juta). Fitur ini sebelumnya menggunakan CSFLE Randomized dan gagal. Pendekatan arsitektural apa yang dapat Anda tawarkan di MongoDB modern tanpa mengorbankan keamanan data at-rest secara zero-trust?

---

## 16. Summary

*   **Zero-Trust Paradigma**: CSFLE dan Queryable Encryption (QE) mengubah total model keamanan database; MongoDB server hanya diperlakukan sebagai *untrusted storage engine* yang menyimpan blind ciphertext (BSON Subtype 6).
*   **Envelope Encryption**: Memisahkan kewenangan secara elegan. KEK/CMK tersimpan aman di KMS, sementara DEK tersimpan terenkripsi di Key Vault database, di-cache secara efisien di memori driver aplikasi.
*   **Performa Modern**: Di lingkungan produksi kelas enterprise, penggunaan pustaka native `crypt_shared` adalah keharusan absolut untuk meminimalisasi latensi dan menghindari instabilitas manajemen proses eksternal `mongocryptd`.
*   **Keamanan Holistik**: Kunci keamanan produksi tidak hanya bergantung pada driver aplikasi, melainkan gabungan dari Client-side Encryption Logic, KMS IAM least privilege, dan Server-side Schema Enforcement (`$jsonSchema`) untuk mencegah insiden *plaintext data leak*.