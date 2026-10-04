# Bab 05: REST API Architecture & OpenAPI Specification
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Mendesain & Mengorkestrasi Arsitektur Contract-First (Design-First):** Mengembangkan OpenAPI Specification (OAS) 3.1.x standar enterprise yang fully compliant terhadap spesifikasi JSON Schema Draft 2020-12.
- **Mengintegrasikan API Documentation Tooling ke CI/CD Pipeline:** Mengimplementasikan automated linting (Spectral), documentation generation (Redocly/Stoplight), breaking-change detection (oasdiff), dan automated contract testing (Prism/Dredd).
- **Mengoptimalkan API Spec untuk Konsumsi Autonomous Agent:** Menulis metadata endpoint, schema descriptions, dan parameter constraints yang dirancang secara deterministik untuk engine LLM Function Calling dan API Agent Tooling.
- **Mengelola Skalabilitas dan Tata Kelola Spesifikasi:** Memecah (decoupling) dokumen OAS monolitik menggunakan JSON Schema `$ref` pointers eksternal dan bundling kembali ke target runtime tanpa circular dependency error.
- **Merancang Security & Governance Matrix:** Mengonfigurasi OAuth2 flows, OpenID Connect (OIDC), API Key rotation, dan strict validation schema guna mencegah injection attack pada API Gateway.

---

### 2. Prerequisites
Sebelum mendalami modul ini, Anda wajib memiliki pemahaman operasional mengenai:
- Arsitektur RESTful API standar (HTTP Verbs, Status Codes, Content Negotiation, Idempotency).
- Struktur data JSON, YAML, dan dasar-dasar JSON Schema Core.
- Penggunaan Git, CI/CD pipeline (GitHub Actions/GitLab CI), dan CLI tooling berbasis Node.js/Python.
- Konsep dasar AI Tool Calling / Function Calling (OpenAI Tool Use, LangChain/Semantic Kernel tool parsing).

---

### 3. Concept & Internal Architecture

#### 3.1 Evolusi OAS 3.0 vs OAS 3.1 (JSON Schema 2020-12 Alignment)
Pada OpenAPI 3.0.x, subset JSON Schema yang digunakan memiliki divergensi signifikan terhadap standar IETF JSON Schema (contoh: penggunaan keyword non-standar `nullable: true` dan ketiadaan dukungan penuh untuk keyword conditional). 

OAS 3.1 menyatukan spesifikasi secara penuh dengan **JSON Schema Draft 2020-12**. Implikasi teknis internalnya meliputi:
- **Type Arrays:** `type: [string, "null"]` menggantikan `nullable: true`.
- **Dynamic References & Dialects:** Dukungan terhadap `$schema`, `$id`, `$vocabulary`, dan `$dynamicAnchor`.
- **Top-Level Webhooks:** Pendefinisian asinkronus push API di luar `paths` menggunakan keyword `webhooks`.
- **SPDX License Identifiers:** Metadata lisensi terstandarisasi.

```
+----------------------------------------------------------------------+
|                     OpenAPI Document (Root Object)                  |
|                                                                      |
|  openapi: 3.1.0                                                      |
|  info: { title, version, summary, description, license: { identifier } }
|  servers: [ { url, description, variables } ]                       |
|                                                                      |
|  +------------------------+  +------------------------------------+  |
|  | paths:                 |  | webhooks:                          |  |
|  |  /agents/runs:         |  |  newExecutionEvent:               |  |
|  |    post:               |  |    post:                           |  |
|  |      requestBody: ...  |  |      requestBody: ...              |  |
|  |      responses: ...    |  |      responses: ...                |  |
|  +------------------------+  +------------------------------------+  |
|                                                                      |
|  +----------------------------------------------------------------+  |
|  | components:                                                    |  |
|  |   schemas: { AgentTask: { type: object, properties: ... } }     |  |
|  |   securitySchemes: { OAuth2Bearer: { type: oauth2, ... } }      |  |
|  |   parameters: { TraceIdHeader: { in: header, ... } }            |  |
|  +----------------------------------------------------------------+  |
+----------------------------------------------------------------------+
```

#### 3.2 Parsing Engine dan Abstract Syntax Tree (AST)
Ketika tool parser OAS (misal: `@stoplight/spectral` atau parser generator API gateway) membaca dokumen YAML/JSON, terjadi pemrosesan internal:
1. **Lexical Analysis & Tokenization:** Parsing string YAML/JSON menjadi token individual.
2. **AST Generation:** Pembentukan tree data structure yang memetakan baris, kolom, dan relasi key-value.
3. **Reference Dereferencing Engine:** Parser mengidentifikasi pointer `$ref: './schemas/agent.yaml#/definitions/AgentConfig'`, membuka I/O stream ke file terkait, memvalidasi dependensi siklik (cyclic check via visited node hash table), dan menyatukan node tersebut ke AST utama.
4. **Semantic Validation:** AST divalidasi terhadap meta-schema OAS 3.1.0 JSON Schema.
5. **Linting Ruleset Execution:** Linter mengeksekusi fungsi kustom pada node AST yang cocok dengan ekspresi JSONPath.

#### 3.3 Semantic Readiness untuk LLM Tool Calling
Dalam arsitektur *Autonomous Agents*, LLM membaca schema OpenAPI untuk menentukan:
- Kapan memanggil tool tertentu (berdasarkan `operationId`, `summary`, dan `description`).
- Parameter apa yang wajib diekstrak dari prompt pengguna (`parameters.schema` dan `requestBody.content.application/json.schema`).
- Format inferensi data (validasi type strict: string, integer, boolean, enum).

Jika technical writer menuliskan deskripsi ambigu atau schema terlalu longgar (misal `type: object` tanpa `properties`), LLM akan mengalami halusinasi argumen, menyebabkan kegagalan eksekusi API runtime.

---

### 4. Why & What

| Dimensi | Code-First Approach | Design-First (Contract-Driven) Approach |
| :--- | :--- | :--- |
| **Definisi** | Kode backend ditulis dahulu; OAS digenerate via anotasi kode. | OAS ditulis dahulu sebagai SSOT (Single Source of Truth); kode & mock digenerate dari spec. |
| **Dampak AI/Agent** | Deskripsi endpoint seringkali minimalis atau tidak informatif bagi LLM. | Metadata dirancang presisi untuk konsumsi human & agent sebelum backend diimplementasi. |
| **Integrasi Tim** | Frontend dan AI Engineers terblokir hingga backend selesai deploy. | Mock server instan (Prism) memungkinkan paralelisme kerja sejak hari pertama. |
| **Governance** | Linter berjalan terlambat; breaking change terdeteksi saat staging/prod. | Linter dan breaking change detector berjalan di Pull Request file spesifikasi. |
| **Maintenance** | Drift antara dokumentasi dan implementasi nyata sangat tinggi. | OAS terikat pada CI/CD testing contract; schema drift dieliminasi secara otomatis. |

---

### 5. How (End-to-End Workflow)

Workflow pengembangan API enterprise berbasis Contract-First:

```
[Tech Writer & Architects]
            │
            ▼
┌─────────────────────────┐
│ 1. Tulis OAS 3.1 Specs  │ <── Modular Multi-File ($ref)
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ 2. Linting & Validation │ <── Spectral (Rules: Security, AI-Docs, Naming)
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ 3. Breaking Change Test │ <── oasdiff vs main branch
└───────────┬─────────────┘
            │
            ├────────────────────────────────────────┐
            ▼                                        ▼
┌─────────────────────────┐              ┌─────────────────────────┐
│ 4a. Bundling & Artifact │              │ 4b. Local Mocking       │
│     (Redocly CLI)       │              │     (Prism Engine)      │
└───────────┬─────────────┘              └─────────────────────────┘
            │
            ├────────────────────────────────────────┐
            ▼                                        ▼
┌─────────────────────────┐              ┌─────────────────────────┐
│ 5a. Deploy Docs Portal  │              │ 5b. SDK & Agent Tool    │
│     (Human Developers)  │              │     Generator (OpenAI)  │
└─────────────────────────┘              └─────────────────────────┘
```

1. **Authoring:** Penulisan dokumen modular menggunakan ekstensi file terpisah untuk setiap domain (`paths/`, `schemas/`, `parameters/`).
2. **Static Analysis (Linting):** Eksekusi Spectral di CI/CD untuk memastikan kepatuhan terhadap style guide korporat dan standar AI-readiness.
3. **Contract Diffing:** Komparasi snapshot OAS terhadap versi produksi menggunakan `oasdiff` untuk memblokir backward-incompatible changes tanpa semantic version bump yang sesuai.
4. **Bundling:** Mengompilasi multi-file OAS menjadi satu file dereferenced/bundled artifact JSON/YAML via `@redocly/cli`.
5. **Orchestration:** Output bundle didistribusikan ke documentation portal (Redoc/Stoplight), API Gateway (Kong/Apigee) untuk schema validation, dan tool calling registry autonomous agent.

---

### 6. Analogy & Diagram ASCII

#### Analogi Konseptual
Bayangkan OAS 3.1 sebagai **Blueprint Rancang Bangun Presisi Tinggi**:
- **OAS File:** Gambar teknik arsitektur berskala milimeter.
- **Contract-First:** Anda tidak membangun gedung dahulu baru kemudian mengukur denah lantainya. Anda membuat denah, melakukan review struktural bersama tim sipil, mekanikal, dan interior, baru kemudian konstruksi fisik dimulai.
- **LLM/Autonomous Agent:** Robot perakit modular otomatis. Robot tidak dapat menebak material apa yang harus dipasang jika blueprint hanya bertuliskan *"pasang pipa di sini"* (tanpa spesifikasi diameter, material PVC/baja, dan tekanan maksimum). Semakin presisi toleransi ukuran di blueprint, semakin akurat kinerja robot.

#### Diagram Parser & Dynamic Reference Engine
```
root.openapi.yaml
 ├── info: { ... }
 ├── paths:
 │    └── /v1/agents/execute:
 │         └── post:
 │              ├── parameters: 
 │              │    └── $ref: './parameters/trace-id.yaml' ───┐
 │              └── requestBody:                                │
 │                   └── content:                               │
 │                        └── application/json:                 │
 │                             └── schema:                      │
 │                                  └── $ref: './schemas/req.yaml' ──┐
 │                                                              │    │
 └── components:                                                │    │
      └── (Internal Cache AST Registry)                         │    │
           ├── [Ref: ./parameters/trace-id.yaml] <──────────────┘    │
           │    └── in: header, name: X-Trace-Id, schema: ...        │
           └── [Ref: ./schemas/req.yaml] <───────────────────────────┘
                └── type: object, properties: ...
```

---

### 7. Code Implementations

#### 7.1 Minimal OAS 3.1 Document vs Production-Grade Modular Architecture
Berikut adalah implementasi production-grade dokumen OpenAPI 3.1.0 yang merepresentasikan endpoint orkestrasi Autonomous AI Agent.

##### `root.openapi.yaml`
```yaml
openapi: 3.1.0
info:
  title: Enterprise Autonomous Agent Orchestrator API
  version: 1.4.0
  summary: Core REST gateway for orchestrating, scheduling, and observing LLM Autonomous Agents.
  description: |
    Enterprise API providing deterministic lifecycle management for AI Agents.
    Designed for compliance with strict function-calling runtime environments.
  contact:
    name: API Platform & Governance Engineering
    email: api-platform@enterprise.internal
    url: https://developer.enterprise.internal/support
  license:
    name: Apache-2.0
    identifier: Apache-2.0

servers:
  - url: https://api.enterprise.internal/v1
    description: Production Gateway Instance
  - url: https://staging-api.enterprise.internal/v1
    description: Staging Environment with Sandbox LLM Providers

paths:
  /agents/runs:
    post:
      operationId: createAgentRun
      summary: Initialize and execute an Autonomous Agent Run
      description: |
        Dispatches an autonomous run to the orchestration execution engine.
        Accepts model configurations, dynamic constraints, and tool registries.
        Guarantees deterministic schema validation prior to LLM context loading.
      tags:
        - Agent Execution
      security:
        - OAuth2Bearer:
            - "agent:execute"
            - "agent:read"
      parameters:
        - $ref: './parameters/trace-id.yaml'
      requestBody:
        required: true
        description: Target payload for the autonomous run deployment.
        content:
          application/json:
            schema:
              $ref: './schemas/agent-run-request.yaml'
      responses:
        '202':
          description: Agent Run accepted and queued for execution.
          headers:
            Location:
              description: URI pointer to poll run execution progress.
              schema:
                type: string
                format: uri
          content:
            application/json:
              schema:
                $ref: './schemas/agent-run-response.yaml'
        '400':
          $ref: './responses/400-bad-request.yaml'
        '401':
          $ref: './responses/401-unauthorized.yaml'
        '422':
          $ref: './responses/422-validation-error.yaml'
        '500':
          $ref: './responses/500-internal-error.yaml'

webhooks:
  agentRunCompleted:
    post:
      summary: Asynchronous notification dispatch on agent task completion.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required:
                - eventId
                - runId
                - status
                - timestamp
              properties:
                eventId:
                  type: string
                  format: uuid
                  example: "a8098c1a-f86e-11da-bd1a-00112444be1e"
                runId:
                  type: string
                  format: uuid
                  example: "c29f8c1a-f86e-11da-bd1a-00112444be1e"
                status:
                  type: string
                  enum: [completed, failed, terminated]
                metrics:
                  type: object
                  properties:
                    totalTokensConsumed:
                      type: integer
                      minimum: 0
                    executionLatencyMs:
                      type: integer
                      minimum: 0
      responses:
        '200':
          description: Webhook received and acknowledged by subscriber.

components:
  securitySchemes:
    OAuth2Bearer:
      type: oauth2
      description: Enterprise Keycloak/Okta OAuth2 authorization server integration.
      flows:
        clientCredentials:
          tokenUrl: https://auth.enterprise.internal/oauth/v2/token
          scopes:
            "agent:execute": "Permission to trigger and execute autonomous agent workflows"
            "agent:read": "Permission to inspect execution state and audit trails"
            "agent:admin": "Administrative operations over agent lifecycle"
```

##### `parameters/trace-id.yaml`
```yaml
name: X-Trace-Id
in: header
required: true
description: W3C distributed trace identifier for end-to-end distributed transaction tracking.
schema:
  type: string
  pattern: '^[0-9a-fA-F]{32}$'
  example: "4bf92f3577b34da6a3ce929d0e0e4736"
```

##### `schemas/agent-run-request.yaml`
```yaml
type: object
required:
  - agentId
  - taskPrompt
  - executionStrategy
properties:
  agentId:
    type: string
    format: uuid
    description: Target unique identifier of the pre-configured autonomous agent.
    example: "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"
  taskPrompt:
    type: string
    minLength: 10
    maxLength: 4096
    description: Natural language task definition ingested by the orchestrator system prompt.
    example: "Analyze Q3 revenue report and cross-reference with historical anomalies."
  executionStrategy:
    type: string
    enum:
      - sequential
      - parallel-swarm
      - human-in-the-loop
    description: Concurrency model applied during autonomous sub-agent delegation.
  fallbackModel:
    type:
      - "string"
      - "null"
    description: Optional secondary model used in case of primary LLM circuit breaking.
    example: "claude-3-5-sonnet"
  timeoutSeconds:
    type: integer
    minimum: 1
    maximum: 3600
    default: 300
    description: Maximum operational window before execution cancellation.
```

##### `schemas/agent-run-response.yaml`
```yaml
type: object
required:
  - runId
  - status
  - createdAt
properties:
  runId:
    type: string
    format: uuid
    example: "d3b07384-d113-494b-9c8e-aa5843c323f4"
  status:
    type: string
    enum:
      - queued
      - running
    example: "queued"
  createdAt:
    type: string
    format: date-time
    example: "2026-03-31T09:12:28.000Z"
```

##### `responses/400-bad-request.yaml`
```yaml
description: Malformed request payload or syntactic schema violation.
content:
  application/problem+json:
    schema:
      type: object
      required:
        - type
        - title
        - status
        - detail
      properties:
        type:
          type: string
          format: uri
          example: "https://errors.enterprise.internal/bad-request"
        title:
          type: string
          example: "Bad Request"
        status:
          type: integer
          example: 400
        detail:
          type: string
          example: "The field 'executionStrategy' must match one of the allowed enum values."
        invalidParams:
          type: array
          items:
            type: object
            properties:
              name:
                type: string
              reason:
                type: string
```

#### 7.2 Custom Spectral Ruleset (`.spectral.yaml`)
Automated linter ruleset enforces design hygiene, security policies, and documentation readability:

```yaml
extends: ["spectral:oas"]

rules:
  # Enforce operationId formatting
  operation-operationId-camelCase:
    description: "Every operationId must be strictly written in camelCase format."
    message: "operationId '{{value}}' must follow camelCase convention."
    severity: error
    given: "$.paths.*[get,post,put,delete,patch].operationId"
    then:
      function: casing
      functionOptions:
        type: camel

  # AI & Documentation Readability: Require thorough description
  operation-description-length:
    description: "Operations must have a description with at least 50 characters for LLM Tool Clarity."
    message: "Description for '{{path}}' is too brief (minimum 50 chars required)."
    severity: warn
    given: "$.paths.*[get,post,put,delete,patch].description"
    then:
      function: length
      functionOptions:
        min: 50

  # Security enforcement: OAuth2/OIDC must be defined globally or per operation
  operation-security-defined:
    description: "Every endpoint must specify explicit security configurations."
    message: "Missing security requirements at {{path}}."
    severity: error
    given: "$.paths.*[get,post,put,delete,patch]"
    then:
      field: security
      function: defined

  # Prevent unconstrained string fields (Defense against DoS and LLM input flood)
  schema-strings-must-have-bounds:
    description: "String types inside schemas must define maxLength to avoid memory exhaustion."
    message: "String property '{{property}}' must declare maxLength."
    severity: warn
    given: "$..properties[?(@.type === 'string' && !@.format && !@.enum)]"
    then:
      field: maxLength
      function: defined
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks & Problem
Sebuah konglomerasi FinTech (PT FinTech International) membangun platform orkestrasi transaksi otonom berbasis LLM Agent. Masalah utama yang dihadapi:
- Dokumentasi API dibuat secara *Code-First* menggunakan anotasi framework Java Spring Boot.
- Anotasi menghasilkan OpenAPI 3.0 monolitik sepanjang 48.000 baris.
- Terdapat puluhan inkonsistensi naming (`camelCase` bercampur `snake_case`), ketiadaan deskripsi semantik untuk parameter internal, dan penggunaan schema bebas (`type: object` polimorfik tanpa properties).
- **Insiden Kritis:** Ketika Autonomous Reconciler Agent diluncurkan, model LLM mengeksekusi parameter terbalik antara `sourceAccountId` dan `targetAccountId` akibat deskripsi parameter yang ambigu dan ketiadaan validasi pattern UUID, mengakibatkan kesalahan transfer dana sebesar USD $1.2M pada staging production mirroring.

#### Solusi Arsitektural (Migration to OAS 3.1 & Contract-First)
1. **Pemisahan Desain dari Kode (Decoupling):** Technical Writers dan Platform Engineers mengambil alih kepemilikan definisi API melalui repositori git terpusat: `api-contracts`.
2. **Modularisasi Total:** Spesifikasi monolitik dipecah menjadi 350+ file komponen independen menggunakan standar JSON Schema 2020-12.
3. **Automated Gatekeeping:** 
   - CI Pipeline mengeksekusi `spectral lint` dengan rule ketat: wajib ada constraints (`maxLength`, `pattern`, `minimum`), deskripsi semantik wajib mendetailkan konteks finansial, dan seluruh skema status HTTP menggunakan RFC 7807 (`application/problem+json`).
   - Eksekusi `oasdiff` untuk mendeteksi `breaking` changes pada setiap Pull Request.
4. **Mock Testing Paralel:**prism mock engine dijalankan otomatis pada lingkungan preview cluster k8s, memungkinkan tim QA menguji logika agent terhadap mock server sebelum backend engineer selesai mengubah logic controller.

#### Metrik Keberhasilan (Hasil Pasca Implementasi)
- **Zero Schema-induced Agent Hallucination:** Tingkat kesalahan inferensi parameter oleh autonomous agent turun ke 0.00%.
- **Development Cycle Reduction:** Waktu integrasi frontend & QA agent berkurang dari 18 hari menjadi 4 hari kerja berkat ketersediaan Prism contract mocking instan.
- **Documentation Drift Elimination:** 100% build gagal di CI jika engineer meng-update payload response backend tanpa menyinkronkan spesifikasi OAS terlebih dahulu.

---

### 9. Trade-offs

| Pendekatan / Keputusan | Keuntungan | Kerugian & Konsekuensi |
| :--- | :--- | :--- |
| **Design-First vs Code-First** | Kontrak API sangat terstruktur, netral terhadap bahasa pemrograman, zero-drift, ramah terhadap autonomous agent ingestion. | Membutuhkan kurva belajar tinggi bagi tim teknis; proses perancangan awal memakan waktu lebih lama sebelum baris kode pertama ditulis. |
| **OAS 3.1 vs OAS 3.0** | Full JSON Schema Draft 2020-12 alignment, native conditional schemas, support webhooks terstandarisasi. | Kompatibilitas tooling parsial (sejumlah API Gateway legacy dan open-source code generator lama belum mendukung penuh keyword OAS 3.1). |
| **Multi-File Modular Specs vs Single Monolithic Spec** | Mudah di-maintenance oleh banyak tim paralel via Git, modularitas tinggi, reusability schemas maksimal. | Memerlukan bundling pipeline khusus; potensi runtime dereferencing latency jika parser lokal lambat menangani deep nested references. |
| **Strict Schema Bounds (`maxLength`, `pattern`)** | Mencegah resource exhaustion (DoS), membatasi context window token LLM, validasi input deterministik. | Overhead waktu dalam merancang spesifikasi; resiko over-constraining schema yang menolak payload valid yang tidak terduga. |

---

### 10. Common Mistakes & Troubleshooting

#### Mistake 1: Menggunakan Sintaks OAS 3.0 `nullable: true` pada Dokumen OAS 3.1
*Symptom:* Parser OAS 3.1 mengabaikan `nullable: true`, sehingga validation engine menolak nilai `null` dan melempar error 422.
*Root Cause:* OAS 3.1 menghapus keyword `nullable`. Validasi diselaraskan dengan JSON Schema 2020-12.
*Fix:*
```yaml
# SALAH (OAS 3.0 syntax)
type: string
nullable: true

# BENAR (OAS 3.1 syntax)
type:
  - "string"
  - "null"
```

#### Mistake 2: Missing Strict `operationId`
*Symptom:* Tool auto-generation membuat nama method acak (misal `postV1AgentsRuns()`), dan LLM Tool Caller gagal mengeksekusi routing dengan stabil.
*Fix:* Tentukan `operationId` unik berbasis format baku imperatif (`createAgentRun`, `getExecutionMetrics`).

#### Mistake 3: Pointers `$ref` yang Mengalami Unresolved Cyclic Dependency
*Symptom:* Bundler runtime melempar error: `Maximum call stack size exceeded` saat memproses schema yang mereferensikan dirinya sendiri (self-referential structure seperti hierarchical agent tasks).
*Fix:* Batasi siklus menggunakan wrapper property atau pisahkan schema definition ke level komponen internal dengan resolusi non-inline.

#### Mistake 4: Regular Expression Denial of Service (ReDoS) pada Keyword `pattern`
*Symptom:* API Gateway mengalami spike CPU 100% saat memvalidasi header atau parameter payload dengan ekspresi regex yang tidak efisien.
*Fix:* Hindari catastrophic backtracking regex. Uji semua regex pattern menggunakan engine RE2 compliance check dan pasang batasan `maxLength` pada target string.

---

### 11. Best Practices & Production Checklist

#### Production Readiness Checklist
- [ ] **OpenAPI Version:** Dokumen menggunakan versi stabil terbaru `openapi: 3.1.0`.
- [ ] **Deterministic Metadata:** Setiap endpoint memiliki `operationId`, `summary`, dan `description` (minimal 50 karakter yang menjelaskan dependensi bisnis dan konteks eksekusi).
- [ ] **Security Matrix:** Seluruh paths memiliki skema `security` yang mengikat, minimal OAuth2 scopes atau API Key authorization.
- [ ] **JSON Schema Compliance:** Tidak ada keyword legacy (seperti `nullable: true`). Gunakan array type `[type, "null"]`.
- [ ] **Boundary Constraints:** Semua string memiliki `maxLength` dan `pattern` (jika relevan). Semua number/integer memiliki `minimum` dan `maximum`.
- [ ] **Deterministic Enums:** Semua enum didokumentasikan dengan jelas nilai dan fungsinya.
- [ ] **RFC 7807 Error Standard:** Seluruh error response (4xx, 5xx) menggunakan format payload terstandarisasi `application/problem+json`.
- [ ] **Static Linting Gate:** CI Pipeline menjalankan Spectral linter dengan level `severity: error` yang memblokir merge pull request.
- [ ] **Breaking Changes Check:** Eksekusi `oasdiff` untuk mendeteksi breaking change sebelum deploy ke branch `main`.

---

### 12. Hands-on Practice: Membangun Toolchain OAS 3.1 di `hands-on/m02/`

Ikuti langkah-langkah terstruktur di bawah ini untuk membuat toolchain contract validation end-to-end.

#### Langkah 1: Setup Workspace & Tooling
Buka terminal dan inisialisasi project baru:
```bash
mkdir -p hands-on/m02/{schemas,parameters,responses}
cd hands-on/m02
npm init -y
npm install --save-dev @stoplight/spectral-cli @stoplight/spectral-rulesets @redocly/cli @stoplight/prism-cli oasdiff
```

#### Langkah 2: Buat File `.spectral.yaml`
Simpan ruleset berikut di root direktori `hands-on/m02/.spectral.yaml`:
```yaml
extends: ["spectral:oas"]
rules:
  operation-operationId-valid:
    description: "operationId must exist and be camelCase."
    severity: error
    given: "$.paths.*[get,post,put,delete].operationId"
    then:
      function: casing
      functionOptions:
        type: camel
  meaningful-description:
    description: "Operation description must be rich enough for Agent ingestion."
    severity: error
    given: "$.paths.*[get,post,put,delete].description"
    then:
      function: length
      functionOptions:
        min: 30
```

#### Langkah 3: Buat File Spesifikasi Modular
Gunakan isi file spesifikasi dari **Seksi 7.1** pada modul ini dan distribusikan sesuai path:
- Simpan `root.openapi.yaml` di root `hands-on/m02/`.
- Simpan `parameters/trace-id.yaml`.
- Simpan `schemas/agent-run-request.yaml`.
- Simpan `schemas/agent-run-response.yaml`.
- Simpan `responses/400-bad-request.yaml`.

Tambahkan response minimal untuk `responses/401-unauthorized.yaml`, `responses/422-validation-error.yaml`, dan `responses/500-internal-error.yaml` dengan struktur RFC 7807 serupa.

#### Langkah 4: Validasi dan Linting
Jalankan Spectral untuk menganalisis struktur AST dokumen modular:
```bash
npx spectral lint root.openapi.yaml
```
*Expected Output:* Spectral menampilkan status sukses tanpa pesan error (exit code 0).

#### Langkah 5: Bundle Menjadi Single Artifact
Kompilasi spesifikasi multi-file menjadi satu artefak independen:
```bash
npx @redocly/cli bundle root.openapi.yaml --output dist/openapi.bundled.yaml --ext yaml
```

#### Langkah 6: Jalankan Prism Mock Server
Jalankan server tiruan (mock) instan berdasarkan kontrak yang telah disusun:
```bash
npx prism mock dist/openapi.bundled.yaml -p 4010
```

#### Langkah 7: Eksekusi Test Request terhadap Mock Server
Buka terminal lain dan kirim request via `curl`:
```bash
curl -i -X POST http://localhost:4010/agents/runs \
  -H "Content-Type: application/json" \
  -H "X-Trace-Id: 4bf92f3577b34da6a3ce929d0e0e4736" \
  -H "Authorization: Bearer mock-token" \
  -d '{
    "agentId": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "taskPrompt": "Analyze transaction logs for anomalies",
    "executionStrategy": "sequential"
  }'
```
*Expected Output:* Server Prism merespons dengan HTTP Status `202 Accepted` beserta schema mock data dari `schemas/agent-run-response.yaml`.

---

### 13. Exercises

#### Level Easy
Buat file parameter header reusable `parameters/client-version.yaml` yang mendefinisikan header `X-Client-Version` dengan kriteria:
- Wajib diisi (`required: true`).
- Format string mengikuti Semantic Versioning regex pattern (`^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$`).
- Sediakan contoh (`example: "1.2.0"`).
*Acceptance Criteria:* File tervalidasi sukses melalui `spectral lint`.

#### Level Medium
Definisikan model polimorfik pada schema `schemas/agent-task-step.yaml` menggunakan keyword `oneOf` dan `discriminator`.
- Schema ini harus mendukung dua jenis tipe aksi agent: `ToolCallStep` (memiliki properties `toolName` [string] dan `arguments` [object]) dan `FinalResponseStep` (memiliki properties `responseContent` [string] dan `confidenceScore` [number]).
- Definisikan field `stepType` sebagai discriminator mapping.
*Acceptance Criteria:* Parser Prism berhasil memvalidasi payload mock dari masing-masing tipe polymorphism tanpa conflict validation.

#### Level Hard
Rancang script integrasi CI/CD berbasis Node.js (`scripts/verify-contract.js`) yang:
1. Membaca `root.openapi.yaml`.
2. Menjalankan linter Spectral via programmatic API Node.js.
3. Menjalankan command `oasdiff` komparasi terhadap snapshot versi production (`production.yaml`).
4. Mengeluarkan error message detail dan melempar `process.exit(1)` jika ditemukan breaking change atau lint error.
*Acceptance Criteria:* Script berjalan headless di dalam terminal container Linux dengan exit code deterministik.

---

### 14. Challenge (Tantangan Studi Kasus Nyata)

**Skenario:**
Sebuah enterprise Autonomous AI Agent Gateway memproses streaming request menggunakan Server-Sent Events (SSE) dan Webhooks balik ke client. Anda diminta merancang arsitektur kontrak OAS 3.1 tanpa menggunakan anotasi kode untuk endpoint `/agents/runs/{runId}/stream`. Endpoint ini mentransmisikan *chunk token* secara parsial dengan protokol `text/event-stream`.

**Tantangan Arsitektur:**
1. Rancang pendefinisian streaming response pada OAS 3.1 dengan content type `text/event-stream` menggunakan schema composition yang merepresentasikan aneka varian event SSE (`token_delta`, `tool_execution_start`, `agent_completed`, `runtime_error`).
2. Sediakan arsitektur schema security di mana token streaming diamankan menggunakan Ephemeral JWT Scopes yang masa berlakunya hanya 60 detik.
3. Rancang Spectral Custom Function (berbasis JavaScript) yang memverifikasi bahwa *setiap* endpoint dengan SSE wajib mendefinisikan response code `200` dengan header `Cache-Control: no-cache` dan `Connection: keep-alive`.

*Constraint:* Dilarang keras menggabungkan semua varian event menjadi satu schema flat generic `type: object`. Desain harus strictly typed dan lolos dereferencing engine Stoplight/Redocly.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Soal)
1. **Bagaimana cara menyatakan bahwa sebuah field bertipe string dapat menerima nilai `null` di OpenAPI 3.1?**
   - A. `type: string` dan `nullable: true`
   - B. `type: [string, "null"]`
   - C. `type: null-or-string`
   - D. `$ref: '#/components/schemas/nullString'`
   *Jawaban:* B. OAS 3.1 menyelaraskan diri sepenuhnya dengan JSON Schema Draft 2020-12, sehingga penggunaan `nullable: true` dihilangkan dan diganti dengan type array.

2. **Keyword apa di level akar (root) OpenAPI 3.1 yang digunakan untuk mendefinisikan API push/callback asinkronus tanpa mengikatnya pada interaksi endpoint tertentu?**
   - A. `callbacks`
   - B. `asyncPaths`
   - C. `webhooks`
   - D. `events`
   *Jawaban:* C. `webhooks` adalah top-level object di OAS 3.1 untuk mendokumentasikan API push asinkronus (out-of-band events).

3. **Di manakah lokasi standard untuk menyimpan komponen skema yang dapat digunakan kembali (reusable components) dalam dokumen OpenAPI?**
   - A. `definitions`
   - B. `components/schemas`
   - C. `structures`
   - D. `models`
   *Jawaban:* B. Dokumen OpenAPI 3.x memusatkan seluruh reusable items di bawah blok `components`.

4. **Apa fungsi utama dari identifier `operationId` pada definisi endpoint?**
   - A. Memberikan URL unik pada server.
   - B. Menyediakan identifier unik case-sensitive bagi tooling code-generator dan AI Agent function calling.
   - C. Menentukan nama tabel basis data backend.
   - D. Menjadi penanda versi semantic dokumen.
   *Jawaban:* B. `operationId` adalah identifier unik yang digunakan engine generator, router, dan LLM Tool Caller untuk memetakan fungsi eksekusi.

5. **Format status error manakah yang direkomendasikan secara enterprise untuk response code HTTP 4xx dan 5xx di REST API modern?**
   - A. `text/plain`
   - B. `application/xml`
   - C. `application/problem+json` (RFC 7807)
   - D. `application/javascript`
   *Jawaban:* C. RFC 7807 (`application/problem+json`) mendefinisikan payload machine-readable standard untuk detail kesalahan HTTP.

#### Intermediate (5 Soal)
6. **Mengapa autonomous agent LLM lebih rentan mengalami kegagalan eksekusi saat mengonsumsi OAS yang dibuat dengan pendekatan *Code-First* tanpa penyesuaian manual?**
   - A. Karena LLM tidak mendukung parsing format JSON.
   - B. Karena *Code-First* seringkali menghasilkan schema longgar (`type: object`), minim deskripsi semantik konteks parameter, dan ketiadaan boundary regex/enum.
   - C. Karena dokumen *Code-First* tidak memiliki HTTP Status Codes.
   - D. Karena library AI hanya bisa membaca schema GraphQL.
   *Jawaban:* B. Auto-generated schema sering kali kehilangan semantic domain knowledge dan boundaries (seperti regex, enum, min/max length), yang sangat dibutuhkan LLM untuk melakukan argument extraction secara akurat.

7. **Pada tools Spectral, apa peran ekspresi `given` di dalam sebuah custom rule?**
   - A. Menentukan aksi perbaikan yang harus dieksekusi secara otomatis.
   - B. Menggunakan sintaks JSONPath untuk menavigasi dan memilih target node spesifik di dalam dokumen AST yang akan dievaluasi.
   - C. Mendefinisikan pesan error jika aturan dilanggar.
   - D. Mengimpor dependensi eksternal dari npm.
   *Jawaban:* B. Keyword `given` mengeksekusi ekspresi JSONPath untuk menentukan elemen-elemen AST mana yang akan diuji oleh parameter `then`.

8. **Manakah perubahan berikut yang dikategorikan sebagai *Breaking Change* oleh tool breaking-change detector (`oasdiff`)?**
   - A. Menambahkan endpoint baru `/agents/metrics`.
   - B. Menambahkan properti baru yang bersifat optional (`required: false`) pada request payload.
   - C. Mengubah enum yang ada dengan menghapus salah satu allowed value pada requestBody.
   - D. Menambahkan response code `201 Created` baru.
   *Jawaban:* C. Menghapus allowed enum value pada requestBody adalah breaking change karena client yang sebelumnya mengirimkan nilai enum tersebut akan ditolak oleh validation engine.

9. **Apa bahaya terbesar membiarkan schema string tanpa keyword `maxLength` pada API Gateway yang menggunakan OAS-based runtime request validation?**
   - A. Response JSON akan dikonversi menjadi binary.
   - B. Potensi serangan Memory Exhaustion / ReDoS (Regular Expression Denial of Service) akibat pengiriman string dengan payload raksasa.
   - C. Client tidak bisa melakukan parsing data.
   - D. Spectral linter akan menghapus schema tersebut.
   *Jawaban:* B. Tanpa batasan ukuran (`maxLength`), Gateway engine akan mengalokasikan buffer memory besar dan mengeksekusi CPU-intensive regex matching pada arbitrary length string, memicu kerentanan DoS.

10. **Bagaimana mekanisme kerja keyword `discriminator` dalam schema composition polimorfik (`oneOf`)?**
    - A. Memaksa client mengirimkan seluruh variasi tipe data sekaligus.
    - B. Mengidentifikasi property spesifik (payload field) yang berfungsi sebagai petunjuk (hint) bagi parser untuk menentukan schema validasi turunan yang tepat secara instan.
    - C. Mengenkripsi payload sebelum dikirimkan ke server.
    - D. Menghubungkan client langsung ke WebSocket target.
    *Jawaban:* B. `discriminator` menginstruksikan validator untuk mengevaluasi satu field kunci (misal: `stepType`) sehingga proses penentuan schema target dari kumpulan `oneOf` berjalan deterministik tanpa memvalidasi semua kemungkinan secara brute-force.

#### Production Scenario Analysis (3 Soal Kasus)

11. **Skenario 1:**
Sebuah tim platform mendapati bahwa pipeline CI/CD mereka membutuhkan waktu 22 menit hanya untuk menjalankan Spectral linter pada repositori API Contracts. Repositori tersebut memiliki 400 endpoint yang dipecah ke dalam 1.200 file YAML menggunakan `$ref`.
*Pertanyaan Analisis:* Apa akar masalah arsitektur ini dan tindakan apa yang harus diambil untuk memangkas waktu eksekusi linter menjadi di bawah 30 detik?
*Jawaban Teknis:* Akar masalah adalah tingginya disk I/O dan Network/Filesystem lookups berulang akibat dynamic dereferencing unbundled multi-file pada ribuan node individual. Solusinya:
- Implementasikan langkah bundling awal menggunakan `@redocly/cli bundle` ke dalam satu in-memory atau temporary single-file bundled artifact.
- Jalankan Spectral linter pada dokumen hasil bundling tersebut, bukan pada entrypoint unbundled yang memicu dereferencing tree traversal berulang.
- Aktifkan caching node modules dan caching AST registry pada pipeline runner.

12. **Skenario 2:**
Setelah migrasi spesifikasi ke OAS 3.1, API Gateway (Kong) yang bertugas melakukan schema validation menolak 100% request ke endpoint yang mendefinisikan field `createdAt` dengan schema:
```yaml
type:
  - "string"
  - "null"
format: date-time
```
Error log menunjukkan: `Schema compilation error: Unknown keyword 'type' value array`.
*Pertanyaan Analisis:* Mengapa gateway melempar error tersebut, dan apa solusi kompatibilitas enterprise tanpa harus menurunkan versi spesifikasi dokumen utama kembali ke OAS 3.0?
*Jawaban Teknis:* Gateway plugin Kong tersebut masih menggunakan parser validator JSON Schema Draft 4 atau Draft 7 (yang hanya mengizinkan `type` bertipe string tunggal, bukan type array).
Solusi Enterprise:
- Tambahkan step transformasi artefak di CI/CD build pipeline khusus target gateway deployment (`build:gateway`).
- Gunakan tooling transpile (seperti `@redocly/cli` dengan decorator custom atau script compiler) yang mendowngrade format JSON Schema 2020-12 ke JSON Schema Draft 7 / OpenAPI 3.0 semantics (`type: string` dan `nullable: true`) hanya untuk konsumsi gateway plugin, sementara SSOT repositori tetap mempertahankan standar OpenAPI 3.1 untuk konsumsi LLM Agent dan dokumentasi human portal.

13. **Skenario 3:**
Autonomous Agent yang bertugas melakukan rekonsiliasi database sering kali gagal ketika memanggil endpoint POST `/v1/transactions/reconcile`. Agent tersebut mengirimkan request payload dengan format:
`{"amount": "150000.00", "currency": "IDR"}`.
Namun backend menolak dengan error code HTTP 400. Ketika dicek di OAS 3.1, spesifikasi mendefinisikan:
```yaml
amount:
  type: number
  minimum: 0.01
```
*Pertanyaan Analisis:* Mengapa LLM melakukan kesalahan konversi tipe data tersebut dan bagaimana technical writer harus merevisi spesifikasi OAS agar kesalahan deterministik ini teratasi dari sisi dokumentasi/kontrak?
*Jawaban Teknis:* LLM mengekstrak nominal finansial sebagai string akibat floating point precision risk (standar umum dalam representasi moneter untuk menghindari precision loss di JavaScript/Python). Karena schema OAS mendefinisikan `type: number` tanpa deskripsi konversi, model sering kali memunculkan halusinasi pembungkusan tanda kutip string.
Langkah Koreksi Spesifikasi:
- Jika backend menerima numeric types: Tambahkan `description: "Strict IEEE 754 floating-point numeric value. Do NOT send as string quotes."` dan tambahkan validasi `example: 150000.00`.
- Jika backend berbasis perbankan standar yang menghindari floating point: Ubah tipe data di kontrak menjadi string dengan pattern moneter terikat:
```yaml
amount:
  type: string
  pattern: '^[0-9]+(\.[0-9]{2})?$'
  description: "Monetary amount formatted as a decimal string with exactly two decimal places. Do not include currency symbols."
  example: "150000.00"
```
Revisi ini memberikan constraint semantik dan struktural yang deterministik bagi parser model LLM.

---

### 16. Summary

1. **OpenAPI Specification 3.1** adalah standar modern untuk merancang interface API enterprise, menghadirkan keselarasan penuh dengan **JSON Schema Draft 2020-12**, penghapusan keyword non-standar seperti `nullable`, dan penambahan dukungan native untuk Webhooks.
2. Dalam ekosistem **AI Data & Autonomous Agents**, OpenAPI bertindak sebagai antarmuka deterministik (*Action Interface*). Kualitas penulisan metadata, parameter descriptions, bounds constraints, dan typed structures menentukan akurasi inferensi LLM dalam memanggil API tanpa halusinasi.
3. Pendekatan **Contract-First (Design-First)** memisahkan spesifikasi dari dependensi implementasi kode fisik backend, memicu paralelisasi tim melalui mock engine (Prism), serta memindahkan pendeteksian cacat arsitektur ke tahap awal development cycle.
4. **Toolchain Governance Enterprise** membutuhkan integrasi empat lapis di CI/CD:
   - *Static Linting* (Spectral) untuk memastikan kepatuhan standar metadata.
   - *Breaking Change Detection* (oasdiff) untuk mencegah terputusnya integrasi downstream client.
   - *Artifact Bundling* (Redocly) untuk mereduksi multi-file I/O bottleneck.
   - *Contract Testing / Dynamic Mocking* (Prism) untuk verifikasi operasional sebelum kode dirilis.