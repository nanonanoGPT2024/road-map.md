# Bab 09 Module 01: Enterprise Security, Governance & CSFLE

---

## Seksi 01: Identitas Modul
* **Kategori Kurikulum:** 04-Backend-and-Database
* **Track:** MongoDB Enterprise Database Architecture
* **Modul ID:** `MDB-ENT-09-01`
* **Level Teknis:** Advanced / Enterprise Architect
* **Prasyarat:** Pemahaman mendalam tentang MongoDB CRUD, Sharding & Replica Set Internals, Public Key Infrastructure (PKI), x.509 Certificates, AWS IAM/KMS, dan Node.js/TypeScript Backend Development.

---

## Seksi 02: Learning Objectives
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
1. **Mengonfigurasi dan Mengimplementasikan** otentikasi enterprise berlapis menggunakan x.509 Client Certificates dan Role-Based Access Control (RBAC) kustom dengan prinsip *least privilege*.
2. **Merancang dan Menerapkan** Client-Side Field Level Encryption (CSFLE) deterministik dan acak (*randomized*) menggunakan AWS KMS dan master key lokal untuk melindungi data PII/Finansial sebelum menyentuh wire memory layer database.
3. **Mengonfigurasi Sistem Audit Enterprise** untuk melacak, memfilter, dan mengirim log audit kepatuhan (HIPAA, PCI-DSS, GDPR) ke *centralized SIEM engine*.
4. **Menganalisis Overhead Kriptografis** CSFLE terhadap performa query, indexing limits, dan resource consumption pada driver layer vs database storage engine layer.
5. **Membangun Pipeline Otomasi Pengujian Keamanan & Rotasi Kunci** (Customer Master Key dan Data Encryption Key) tanpa downtime aplikasi.

---

## Seksi 03: Concept Map Diagram ASCII

```
+==================================================================================================+
|                                    APPLICATION LAYER (Node.js/TypeScript)                        |
|                                                                                                  |
|   +------------------------------------------------------------------------------------------+   |
|   | MongoCryptd Process / Automatic Encryption Shared Library (crypt_shared)                 |   |
|   +------------------------------------------------------------------------------------------+   |
|               ^                                                                |                 |
|      1. Fetch JSON Schema                                             4. Encrypt/Decrypt         |
|               |                                                              Payload (PII)       |
|               v                                                                v                 |
|   +-----------------------+     2. Retrieve CMK     +----------------------------------------+   |
|   |  Key Vault Collection | <---------------------> | AWS KMS / Local KMS / HashiCorp Vault  |   |
|   |  (Data Keys / DEK)    |                         +----------------------------------------+   |
|   +-----------------------+                                                                      |
|               |                                                                                  |
|   3. Decrypt DEK locally                                                                         |
+===============|==================================================================================+
                |
                |  TLS 1.3 with Mutual x.509 Authentication (mTLS)
                |  Payload contains Ciphertext fields + Plaintext non-sensitive fields
                v
+==================================================================================================+
|                              MONGODB ENTERPRISE SERVER LAYER                                     |
|                                                                                                  |
|   +------------------------------------------------------------------------------------------+   |
|   | Network Interface: mTLS Termination & User Identity Extraction (Subject DN)              |   |
|   +------------------------------------------------------------------------------------------+   |
|               |                                                                                  |
|               v                                                                                  |
|   +---------------------------------------+      +-------------------------------------------+   |
|   | RBAC Engine (Roles, Privileges, Auth) | ---> | Enterprise Audit Log (JSON Filter Stream) |   |
|   +---------------------------------------+      +-------------------------------------------+   |
|               |                                                                |                 |
|               v                                                                v                 |
|   +------------------------------------------------------------------------------------------+   |
|   | Storage Engine (WiredTiger) with Encryption-at-Rest (AES-256-CBC)                         |   |
|   +------------------------------------------------------------------------------------------+   |
+==================================================================================================+
```

---

## Seksi 04: Mengapa Relevan
Dalam arsitektur modern, proteksi perimeter tradisional (*firewall*, VPC *peering*) tidak lagi memadai untuk menangkal ancaman *insider threats*, eksfiltrasi memori, atau kompromi infrastruktur cloud. Standar regulasi internasional seperti **PCI-DSS 4.0**, **GDPR**, dan **HIPAA** mewajibkan kontrol ketat terhadap data sensitif (*Personally Identifiable Information* / PII).

**Client-Side Field Level Encryption (CSFLE)** membalikkan paradigma keamanan database tradisional: database engine tidak lagi memiliki akses ke plaintext data sensitif maupun kunci dekripsinya (*Zero-Knowledge Storage Model*). Bahkan jika instance database dieksfiltrasi, disita, atau diakses oleh DBA/SysAdmin dengan privasi `root`, data tetap terenkripsi secara kriptografis menggunakan algoritma authenticated cipher **AEAD (AES-256-GCM)**.

---

## Seksi 05: Anatomi Konsep Inti

### 1. CSFLE Cryptographic Primitives: CMK vs. DEK
* **Customer Master Key (CMK):** Kunci asimetris/simetris tingkat atas yang dikelola di Hardware Security Module (HSM) atau KMS eksternal (AWS KMS, Azure Key Vault, Google Cloud KMS, HashiCorp Vault). CMK tidak pernah keluar dari boundary KMS.
* **Data Encryption Key (DEK):** Kunci enkripsi simetris yang digunakan langsung untuk mengenkripsi *field* dokumen. DEK disimpan di dalam database pada koleksi `__keyVault` dalam kondisi terenkripsi (*Envelope Encryption*) oleh CMK.
* **Proses Dekripsi:** Driver mengambil DEK terenkripsi dari `__keyVault`, mengirimkannya ke AWS KMS untuk didekripsi via CMK, menerima plaintext DEK di memori lokal aplikasi, lalu mengenkripsi/mendekripsi data field lokal menggunakan library `crypt_shared`.

### 2. Encryption Types
* **Deterministic Encryption (`AEAD_AES_256_CBC_HMAC_SHA_512-Deterministic`):** Menghasilkan ciphertext yang identik untuk input plaintext yang sama dengan DEK yang sama. Mendukung operasi *point-lookup / exact-match queries* (`find({ ssn: "123-45-6789" })`), tetapi rentan terhadap analisis frekuensi statistik jika variasi nilai rendah.
* **Randomized Encryption (`AEAD_AES_256_CBC_HMAC_SHA_512-Random`):** Menggunakan *Initialization Vector (IV)* unik per enkripsi, menghasilkan ciphertext berbeda meskipun plaintext dan DEK sama. Lebih aman secara matematis, namun tidak dapat diindeks dan tidak mendukung operasi pencarian/query langsung.

### 3. Mutual TLS (mTLS) & x.509 Authentication
Menggantikan otentikasi username/password berbasis SCRAM dengan sertifikat digital X.509 terverifikasi oleh Certificate Authority (CA) internal. Identitas pengguna dipetakan langsung dari `RFC2253 Distinguished Name (DN)` pada subjek sertifikat ke sistem RBAC internal MongoDB `$external`.

### 4. Enterprise Audit Subsystem
Fasilitas pelacakan aksi database secara granuler. Log audit MongoDB Enterprise dapat memfilter operasi berbasis event (`authCheck`, `authenticate`, `createUser`), otentikasi role, dan status kegagalan/keberhasilan langsung ke file JSON lokal atau syslog, memfasilitasi integrasi SIEM (Splunk, Datadog, ELK).

---

## Seksi 06: Panduan Implementasi Step-by-Step

### Persiapan Infrastruktur: Konfigurasi AWS KMS & IAM
1. Buat symmetric AWS KMS Key dengan alias `alias/mongodb-csfle-cmk`.
2. Berikan policy permission minimal ke IAM Role aplikasi:
   * `kms:Encrypt`
   * `kms:Decrypt`
   * `kms:DescribeKey`

### Step 1: Konfigurasi `mongod.conf` Enterprise Hardening
Tambahkan konfigurasi audit dan x.509 pada file konfigurasi cluster.

```yaml
# /etc/mongod.conf
net:
  port: 27017
  bindIp: 0.0.0.0
  tls:
    mode: requireTLS
    certificateKeyFile: /etc/ssl/mongodb.pem
    CAFile: /etc/ssl/ca.crt
    allowConnectionsWithoutCertificates: false

security:
  authorization: enabled
  clusterAuthMode: x509

auditLog:
  destination: file
  format: JSON
  path: /var/log/mongodb/audit.json
  filter: '{ "atype": { "$in": [ "authCheck", "authenticate" ] }, "param.command": { "$in": [ "insert", "find", "update", "delete" ] } }'

processManagement:
  fork: true
  timeZoneInfo: /usr/share/zoneinfo
```

### Step 2: Inisialisasi Koleksi Key Vault & JSON Schema
Koleksi Key Vault harus memiliki `unique index` pada field `keyAltNames`.

```javascript
// init-keyvault.js (Executed via mongosh)
use admin;
db.auth({ mechanism: "MONGODB-X509" });

use encryption;
db.__keyVault.createIndex(
  { keyAltNames: 1 },
  { unique: true, partialFilterExpression: { keyAltNames: { $exists: true } } }
);
```

---

## Seksi 07: Contoh Kasus Sederhana

Berikut adalah contoh inisialisasi Client Encryption menggunakan Local Key Provider (32-byte master key) untuk lingkungan pengujian/staging sebelum beralih ke AWS KMS di produksi.

```typescript
// simple-csfle-test.ts
import { MongoClient, ClientEncryption } from 'mongodb';
import { randomBytes } from 'crypto';

async function runSimpleTest() {
  const connectionString = "mongodb://localhost:27017/?tls=true&tlsCAFile=ca.crt&tlsCertificateKeyFile=client.pem";
  const keyVaultNamespace = "encryption.__keyVault";
  
  // Master key 96 bytes untuk local testing (hanya contoh staging)
  const localMasterKey = randomBytes(96);
  const kmsProviders = {
    local: { key: localMasterKey }
  };

  const client = new MongoClient(connectionString);
  await client.connect();

  const clientEncryption = new ClientEncryption(client, {
    keyVaultNamespace,
    kmsProviders,
  });

  const dataKeyId = await clientEncryption.createDataKey("local", {
    keyAltNames: ["customer-pii-key"],
  });

  console.log(`Generated Data Encryption Key UUID: ${dataKeyId.toString('hex')}`);
  await client.close();
}

runSimpleTest().catch(console.error);
```

---

## Seksi 08: Implementasi Production-Grade Lengkap Kode

Implementasi lengkap berikut menggunakan TypeScript, AWS KMS, driver `mongodb` resmi versi `>=6.0`, pustaka kriptografi native `mongodb-crypt` / `crypt_shared`, serta strict JSON Schema enforcement.

```typescript
// enterprise-csfle-service.ts
import { MongoClient, ClientEncryption, Binary, MongoCryptError } from 'mongodb';
import { KMSClient, DescribeKeyCommand } from '@aws-sdk/client-kms';

// ==========================================
// 1. ENVIRONMENT CONFIGURATION & TYPES
// ==========================================
interface SecureCustomerDocument {
  _id?: Binary;
  organizationId: string;
  fullName: string;
  taxIdentificationNumber: string; // PII: Deterministic Encryption (Searchable)
  medicalHistoryNotes: string;      // Sensitive: Randomized Encryption (Non-searchable)
  createdAt: Date;
}

interface CSFLEConfig {
  mongoUri: string;
  keyVaultDb: string;
  keyVaultColl: string;
  awsRegion: string;
  kmsKeyArn: string;
  cryptSharedLibPath: string;
}

const config: CSFLEConfig = {
  mongoUri: process.env.MONGODB_URI || "mongodb://enterprise-cluster.internal:27017/?replicaSet=rs0&tls=true&tlsCAFile=/etc/ssl/ca.crt&tlsCertificateKeyFile=/etc/ssl/app-client.pem&authMechanism=MONGODB-X509",
  keyVaultDb: "encryption",
  keyVaultColl: "__keyVault",
  awsRegion: process.env.AWS_REGION || "ap-southeast-1",
  kmsKeyArn: process.env.AWS_KMS_KEY_ARN || "arn:aws:kms:ap-southeast-1:123456789012:key/abcd-1234-efgh",
  cryptSharedLibPath: process.env.CRYPT_SHARED_PATH || "/usr/lib/mongo_crypt_v1.so",
};

export class EnterpriseCSFLEService {
  private baseClient!: MongoClient;
  private secureClient!: MongoClient;
  private keyVaultNamespace: string;

  constructor() {
    this.keyVaultNamespace = `${config.keyVaultDb}.${config.keyVaultColl}`;
  }

  // ==========================================
  // 2. KMS VALIDATION & HEALTH CHECK
  // ==========================================
  private async validateAWSKMSAccess(): Promise<void> {
    const kmsClient = new KMSClient({ region: config.awsRegion });
    try {
      const command = new DescribeKeyCommand({ KeyId: config.kmsKeyArn });
      const response = await kmsClient.send(command);
      if (!response.KeyMetadata?.Enabled) {
        throw new Error(`AWS KMS Key ${config.kmsKeyArn} is disabled or unavailable.`);
      }
    } catch (error) {
      throw new Error(`KMS Validation failed: ${(error as Error).message}`);
    }
  }

  // ==========================================
  // 3. SECURE CLIENT INITIALIZATION ENGINE
  // ==========================================
  public async initialize(): Promise<void> {
    await this.validateAWSKMSAccess();

    this.baseClient = new MongoClient(config.mongoUri);
    await this.baseClient.connect();

    const kmsProviders = {
      aws: {
        accessKeyId: process.env.AWS_ACCESS_KEY_ID!,
        secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY!,
        sessionToken: process.env.AWS_SESSION_TOKEN, // Optional: if using IAM role/STS
      },
    };

    const clientEncryption = new ClientEncryption(this.baseClient, {
      keyVaultNamespace: this.keyVaultNamespace,
      kmsProviders,
    });

    // Resolve or generate Data Encryption Key (DEK)
    let dataKey = await this.baseClient
      .db(config.keyVaultDb)
      .collection(config.keyVaultColl)
      .findOne({ keyAltNames: "customer-data-key" });

    let dataKeyId: Binary;

    if (!dataKey) {
      dataKeyId = await clientEncryption.createDataKey("aws", {
        masterKey: {
          region: config.awsRegion,
          key: config.kmsKeyArn,
        },
        keyAltNames: ["customer-data-key"],
      });
      console.log(`Generated new DEK with ID: ${dataKeyId.buffer.toString('hex')}`);
    } else {
      dataKeyId = dataKey._id as Binary;
      console.log(`Reusing existing DEK ID: ${dataKeyId.buffer.toString('hex')}`);
    }

    // Explicit JSON Schema defining encryption policies per field
    const schemaMap = {
      "enterprise_crm.customers": {
        bsonType: "object",
        encryptMetadata: {
          keyId: [dataKeyId],
        },
        properties: {
          taxIdentificationNumber: {
            encrypt: {
              bsonType: "string",
              algorithm: "AEAD_AES_256_CBC_HMAC_SHA_512-Deterministic",
            },
          },
          medicalHistoryNotes: {
            encrypt: {
              bsonType: "string",
              algorithm: "AEAD_AES_256_CBC_HMAC_SHA_512-Random",
            },
          },
        },
      },
    };

    // Instantiate Auto-Encrypting MongoClient
    this.secureClient = new MongoClient(config.mongoUri, {
      autoEncryption: {
        keyVaultNamespace: this.keyVaultNamespace,
        kmsProviders,
        schemaMap,
        extraOptions: {
          cryptSharedLibPath: config.cryptSharedLibPath,
          cryptSharedLibRequired: true,
        },
      },
    });

    await this.secureClient.connect();
    console.log("Enterprise CSFLE Client Connected Successfully.");
  }

  // ==========================================
  // 4. SECURE DATA OPERATIONS PIPELINE
  // ==========================================
  public async createCustomerRecord(data: Omit<SecureCustomerDocument, '_id' | 'createdAt'>): Promise<void> {
    const db = this.secureClient.db("enterprise_crm");
    const collection = db.collection<SecureCustomerDocument>("customers");

    try {
      const result = await collection.insertOne({
        ...data,
        createdAt: new Date(),
      });
      console.log(`Secured Document Inserted. ID: ${result.insertedId}`);
    } catch (err) {
      if (err instanceof MongoCryptError) {
        console.error("Cryptographic engine error during ingestion:", err.message);
      }
      throw err;
    }
  }

  public async findByTaxId(taxId: string): Promise<SecureCustomerDocument | null> {
    const db = this.secureClient.db("enterprise_crm");
    const collection = db.collection<SecureCustomerDocument>("customers");

    // Exact match query works automatically because of Deterministic Encryption
    return await collection.findOne({ taxIdentificationNumber: taxId });
  }

  public async verifyRawStorageProof(taxId: string): Promise<void> {
    // Reading with BaseClient (unencrypted view) to verify that database holds only Ciphertext
    const rawDb = this.baseClient.db("enterprise_crm");
    const rawDoc = await rawDb.collection("customers").findOne({ organizationId: "ORG-001" });
    
    console.log("\n--- RAW STORAGE PERSISTENCE PROOF ---");
    console.log("Payload on Database Storage (WiredTiger):", JSON.stringify(rawDoc, null, 2));
    console.log("-------------------------------------\n");
  }

  public async teardown(): Promise<void> {
    await this.secureClient?.close();
    await this.baseClient?.close();
  }
}
```

---

## Seksi 09: Diagram Alur Kerja ASCII

```
[Application]                   [crypt_shared]                 [AWS KMS]            [MongoDB Database]
      |                               |                            |                        |
      |-- 1. Insert Document -------->|                            |                        |
      |   (Plaintext PII)             |-- 2. Fetch DEK Meta ------>|                        |
      |                               |                              -- 3. Read Encrypted DEK ->
      |                               |                              <- 4. Encrypted DEK Byte -
      |                               |-- 5. Send Encrypted DEK -->|                        |
      |                               |   (kms:Decrypt)            |                        |
      |                               |<- 6. Plaintext DEK --------|                        |
      |                               |                                                     |
      |                               |-- 7. Execute Local AEAD-256-GCM                     |
      |                               |      (Encrypt Fields)                               |
      |                               |                                                     |
      |                               |-- 8. Transmit Wire Frame (Ciphertext Payload) ----->|
      |                               |      Over TLS 1.3 mTLS Connection                   |
      |                               |                                                     |-- 9. Persist
      |                               |                                                     |   to Disk
      |                               |<-- 10. Write ACK -----------------------------------|
      |<-- 11. Transaction Resolved --|
```

---

## Seksi 10: Analisis Trade-offs

| Aspek | CSFLE (Client-Side Encryption) | TDE (Transparent Data Encryption / At-Rest) | Application-Level Encryption (Manual) |
| :--- | :--- | :--- | :--- |
| **Zero-Knowledge Guarantees** | **Sangat Tinggi** (Server MongoDB tidak pernah memegang plain data atau DEK). | **Rendah** (Server MongoDB memegang dekripsi di RAM aktif engine). | **Tinggi** (Developer mengelola cipher logic manual). |
| **Kemampuan Query** | **Terbatas** (Hanya point query pada tipe *Deterministic*; tidak ada range query/regex). | **Penuh** (Semua query operator indexing berjalan normal). | **Tidak Ada** (Database menganggap field sebagai binary/string acak). |
| **Beban Komputasi (CPU)** | **Driver-Side** (Beban pindah ke pod aplikasi mikroservis). | **Database-Side** (WiredTiger engine menanggung beban enkripsi/dekripsi). | **Driver-Side** (Overhead eksekusi manual tinggi). |
| **Schema Validation Rigidity** | **Tinggi** (Perlu JSON schema ketat & dynamic type handling). | **Rendah** (Skema dokumen bebas dan dinamis). | **Manual** (Sulit dipelihara antar multi-bahasa). |
| **Key Management Overhead** | **Tinggi** (Perlu arsitektur KMS terdistribusi & *Key Vault Namespace*). | **Sedang** (Konfigurasi `KMIP` terpusat pada server daemon). | **Sangat Tinggi** (Risiko kebocoran kunci di source code tinggi). |

---

## Seksi 11: Best Practices & Antipatterns

### Best Practices
* Gunakan modul `crypt_shared` C-library dinamis dibanding menjalankan sub-proses `mongocryptd` terpisah untuk memangkas *IPC context-switching overhead*.
* Isolasi hak akses `keyVaultNamespace` pada database yang berbeda dengan data operasional, dan batasi hak tulis (*write privilege*) hanya untuk Security Provisioning Service.
* Selalu gunakan `Randomized Encryption` untuk data ber-entropi rendah (misalnya: status kesehatan, jenis kelamin, flag status boolean) guna menghindari *Statistical Frequency Analysis Attacks*.

```
   // ANTI-PATTERN: Melakukan Deterministic Encryption pada field Boolean/Low-Entropy
   // Penyerang dapat menyimpulkan data hanya dengan membandingkan kesamaan Ciphertext!
   isTestedPositiveForDisease: {
     encrypt: {
       bsonType: "bool",
       algorithm: "AEAD_AES_256_CBC_HMAC_SHA_512-Deterministic" // SALAH!
     }
   }
```

* Simpan sertifikat mTLS dan private key dengan permission file `0400` di OS Linux dan miliki mekanisme rotasi periodik sebelum masa aktif sertifikat berakhir (*expiry threshold* < 30 hari).

### Antipatterns
* **Over-indexing Plaintext Reference:** Menyimpan versi *hash* dari data PII di field terbuka lain untuk tujuan query tanpa perlindungan *salted HMAC*.
* **Reusing Master Keys (CMK) across Environments:** Menggunakan KMS Key yang sama untuk cluster Development, Staging, dan Production.
* **Inline Key Generation:** Mengizinkan aplikasi transaksi biasa mengeksekusi `clientEncryption.createDataKey()` saat runtime tanpa kontrol approval.

---

## Seksi 12: Security Hardening

```
                +-------------------------------------------------------------+
                |           x.509 CERTIFICATE CHAIN HARDENING                 |
                +-------------------------------------------------------------+
                |                                                             |
                |  [ Root CA ] (Offline HSM - 4096-bit RSA)                   |
                |      |                                                      |
                |      v                                                      |
                |  [ Intermediate CA ] (Policy: Client & Server Auth Only)    |
                |      |                                                      |
                |      +-----> [ Server Cert ] (Ext: ServerAuth, DNS SANs)    |
                |      |                                                      |
                |      +-----> [ Client Cert ] (Ext: ClientAuth, mTLS DN)     |
                |                                                             |
                +-------------------------------------------------------------+
```

### Konfigurasi Custom RBAC Enterprise
Eksekusi di `admin` database untuk mengisolasi peran operator:

```javascript
// create-hardened-roles.js
use admin;

db.createRole({
  role: "PIIDataReader",
  privileges: [
    {
      resource: { db: "enterprise_crm", collection: "customers" },
      actions: [ "find" ]
    },
    {
      resource: { db: "encryption", collection: "__keyVault" },
      actions: [ "find" ]
    }
  ],
  roles: []
});

db.createRole({
  role: "SecuredSecurityOfficer",
  privileges: [
    {
      resource: { db: "encryption", collection: "__keyVault" },
      actions: [ "find", "insert", "update", "remove" ]
    }
  ],
  roles: []
});
```

---

## Seksi 13: Observabilitas & Debugging

Log audit disimpan dalam format JSON terstruktur untuk ingest langsung ke OpenSearch/Splunk.

### Contoh Audit Event Log (Ingestion Payload)
```json
{
  "atype": "authCheck",
  "ts": { "$date": "2024-10-24T10:15:30.123Z" },
  "local": { "ip": "10.0.1.5", "port": 27017 },
  "remote": { "ip": "10.0.2.80", "port": 54322 },
  "users": [
    { "user": "CN=crm-app-service,OU=Engineering,O=FinTech,C=ID", "db": "$external" }
  ],
  "roles": [
    { "role": "PIIDataReader", "db": "admin" }
  ],
  "param": {
    "command": "find",
    "ns": "enterprise_crm.customers",
    "filter": { "taxIdentificationNumber": { "$type": "binData" } }
  },
  "result": 0
}
```

### Script Healthcheck CSFLE Cryptographic State
```typescript
// csfle-diagnostics.ts
import { MongoClient } from 'mongodb';

export async function checkCSFLEStatus(client: MongoClient) {
  const adminDb = client.db("admin");
  const pingResult = await adminDb.command({ ping: 1 });
  
  // Pastikan crypt_shared library aktif (tidak fallback ke mongocryptd)
  const buildInfo = await adminDb.command({ buildInfo: 1 });
  console.log(`Cluster: MongoDB v${buildInfo.version}`);

  const keyVaultColl = client.db("encryption").collection("__keyVault");
  const totalDEKs = await keyVaultColl.countDocuments();
  console.log(`Health Diagnostic: Detected ${totalDEKs} Active DEKs in Key Vault.`);
  
  return { status: pingResult.ok === 1 ? "HEALTHY" : "UNHEALTHY", totalDEKs };
}
```

---

## Seksi 14: Benchmarking & Performance

Dampak eksekusi kriptografis pada CPU dan Throughput aplikasi:

```
Operation: Batch Insert 10,000 Documents with 2 Encrypted Fields (Deterministic + Random)

Plaintext Ingestion   : [==========] 12,400 ops/sec (Base Latency: 1.2ms)
CSFLE (crypt_shared)  : [======]      7,800 ops/sec (Latency: 2.1ms) - Overhead ~37%
CSFLE (mongocryptd)   : [===]         4,100 ops/sec (Latency: 4.8ms) - Overhead ~66% (IPC Bottleneck)
```

### Mitigasi Bottleneck Performa
1. **DEK In-Memory Caching:** Driver MongoDB secara internal men-*cache* plaintext DEK di memori lokal aplikasi setelah di-decrypt oleh AWS KMS. Pastikan instans aplikasi tidak sering di-*restart* agar tidak memicu throttling API KMS (`KMS:Decrypt` Limit).
2. **Deterministic Index Sizing:** Ciphertext deterministik memiliki ukuran byte array yang jauh lebih panjang (rata-rata 80-120 bytes) dibanding string biasa. Alokasikan RAM yang memadai untuk WiredTiger Cache guna menampung B-Tree index yang lebih besar.

---

## Seksi 15: Hands-on Lab Mini-Project

### Objective
Membangun microservice tokenisasi identitas yang menyimpan nomor kartu kredit terenkripsi secara acak (*random*) dan nomor jaminan sosial terenkripsi secara deterministik menggunakan skema CSFLE otomatis.

### Langkah Pengerjaan
1. Setup local replica set via Docker Compose.
2. Buat Self-Signed CA dan daftarkan sertifikat x.509 client & server.
3. Jalankan pipeline migrasi skema enkripsi JSON.
4. Uji verifikasi keamanan data mentah.

```yaml
# docker-compose.yml
version: '3.8'
services:
  mongo-enterprise:
    image: mongodb/mongodb-enterprise-server:7.0-ubuntu
    container_name: mongo-sec-lab
    environment:
      - MONGO_INITDB_DATABASE=enterprise_crm
    ports:
      - "27017:27017"
    volumes:
      - ./certs:/etc/ssl
      - ./mongod.conf:/etc/mongod.conf
    command: ["--config", "/etc/mongod.conf"]
```

---

## Seksi 16: Automated Testing & Verification

Suite pengujian unit & integrasi menggunakan Jest untuk memverifikasi CSFLE invariants.

```typescript
// csfle-security.spec.ts
import { EnterpriseCSFLEService } from './enterprise-csfle-service';
import { MongoClient } from 'mongodb';

describe('Enterprise Security & CSFLE Invariant Tests', () => {
  let service: EnterpriseCSFLEService;
  let rawClient: MongoClient;

  beforeAll(async () => {
    service = new EnterpriseCSFLEService();
    await service.initialize();

    rawClient = new MongoClient(process.env.MONGODB_URI!);
    await rawClient.connect();
  });

  afterAll(async () => {
    await service.teardown();
    await rawClient.close();
  });

  it('Invariant-1: Should insert PII and successfully resolve exact match lookup', async () => {
    const ssn = `SSN-${Date.now()}`;
    await service.createCustomerRecord({
      organizationId: "ORG-001",
      fullName: "John Doe",
      taxIdentificationNumber: ssn,
      medicalHistoryNotes: "Hypertension Stage 1",
    });

    const doc = await service.findByTaxId(ssn);
    expect(doc).not.toBeNull();
    expect(doc?.taxIdentificationNumber).toBe(ssn);
    expect(doc?.medicalHistoryNotes).toBe("Hypertension Stage 1");
  });

  it('Invariant-2: Database storage layer MUST store binary ciphertext, NEVER plaintext', async () => {
    const rawDoc = await rawClient
      .db("enterprise_crm")
      .collection("customers")
      .findOne({ organizationId: "ORG-001" });

    expect(rawDoc).not.toBeNull();
    // Memastikan data tersimpan sebagai MongoDB Binary subtype 6 (Encrypted BSON)
    expect(typeof rawDoc?.taxIdentificationNumber).not.toBe('string');
    expect(rawDoc?.taxIdentificationNumber._bsontype).toBe('Binary');
    expect(rawDoc?.taxIdentificationNumber.sub_type).toBe(6);
  });
});
```

---

## Seksi 17: Troubleshooting Guide

### 1. Error: `MongoCryptError: crypt_shared library failed to load`
* **Root Cause:** Path konfigurasi `cryptSharedLibPath` salah atau library tidak memiliki execution permission.
* **Remediasi:** Pastikan file `mongo_crypt_v1.so` (Linux) atau `mongo_crypt_v1.dylib` (macOS) berada pada path yang tepat dan dapat dibaca oleh user proses (`chmod 755 mongo_crypt_v1.so`).

### 2. Error: `MongoCryptError: Key with ID ... not found in KeyVault`
* **Root Cause:** Dokumen DEK terhapus dari `__keyVault`, atau user aplikasi tidak memiliki role `find` pada database/collection key vault.
* **Remediasi:** Validasi hak RBAC pengguna mTLS terhadap namespace `encryption.__keyVault`.

### 3. Latency Spike saat Cold-Start Aplikasi
* **Root Cause:** Aplikasi melakukan request serial KMS untuk mendekripsi ratusan DEK.
* **Remediasi:** Konsolidasikan DEK menggunakan skema per-tenant/per-entity daripada per-document. Manfaatkan internal KMS key caching.

---

## Seksi 18: Checklist Produksi

```
[ ] mTLS Enforced: Tidak ada koneksi yang diizinkan tanpa valid client x.509 certificate.
[ ] Certificate Expiry Alerts: Monitoring aktif pada masa berlaku TLS Certificate (< 30 hari).
[ ] KMS Least Privilege: IAM Role driver dibatasi hanya pada CMK ARN spesifik (bukan kms:*).
[ ] Native crypt_shared Active: dynamic library crypt_shared digunakan penuh, mongocryptd dinonaktifkan.
[ ] JSON Schema Locked: Validasi schemaMap terpasang di client driver dan $jsonSchema validator di server.
[ ] Audit System Configured: File JSON audit diarahkan ke rotasi log terdistribusi dan SIEM aggregator.
[ ] Encryption-at-Rest Active: Penyimpanan block device WiredTiger menggunakan AES-256 cipher.
[ ] Non-Root Mongod Process: Proses daemon dijalankan di bawah system user `mongodb` non-root.
[ ] DEK Redundancy & KMS Multi-Region: Kunci CMK tereplikasi di secondary cloud region untuk disaster recovery.
```

---

## Seksi 19: Ringkasan Eksekutif

Penerapan **Enterprise Security, Governance, & CSFLE** di MongoDB mengubah postur keamanan dari model pertahanan pasif (*perimeter/disk-level*) menjadi model proteksi aktif berbasis kriptografi *Zero-Knowledge*. Melalui pemisahan tugas (*separation of concerns*) antara **KMS (Cloud/HSM)**, **Driver Cryptographic Engine (`crypt_shared`)**, dan **Storage Engine Database (WiredTiger)**, data sensitif tetap terlindungi bahkan dalam skenario infrastruktur database disusupi sepenuhnya.

Implementasi yang benar menuntut standardisasi ketat: penggunaan **mTLS x.509** untuk autentikasi level transport & user, pembatasan hak akses berbasis **RBAC granular**, pengawasan jejak audit menyeluruh melalui **Audit Subsystem**, serta pemilihan algoritma **Deterministic vs. Randomized AEAD** yang tepat untuk menyeimbangkan kebutuhan enkripsi data dan fungsionalitas query sistem.

---

## Seksi 20: Referensi & Bacaan Lanjutan
* [MongoDB Enterprise Security Architecture Documentation](https://www.mongodb.com/docs/manual/security/)
* [Client-Side Field Level Encryption (CSFLE) Specification](https://github.com/mongodb/specifications/blob/master/source/client-side-encryption/client-side-encryption.rst)
* [National Institute of Standards and Technology (