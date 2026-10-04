# BAB 03: Contract-First Design Specifications
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Merancang Arsitektur Kontrak API Modern:** Menguasai spesifikasi OpenAPI 3.1 (berbasis JSON Schema Draft 2020-12) dan AsyncAPI 3.0 secara komprehensif untuk sistem berskala enterprise.
- **Mengimplementasikan Validasi AST & Tata Kelola Kontrak:** Mengonfigurasi engine *linting* berbasis Abstract Syntax Tree (AST) menggunakan Spectral dengan *custom functions* untuk menegakkan standar tata kelola API perusahaan.
- **Membangun Pipeline CI/CD Breaking Change Detection:** Mengintegrasikan tooling deteksi perubahan destruktif (*breaking changes*) otomatis berbasis semantik AST (*semantic diffing*) dalam pipeline integrasi berkelanjutan.
- **Mengeksekusi Bidirectional Code Generation & Strict Runtime Validation:** Mengotomatiskan generasi kode *type-safe* untuk server *stubs* dan *client SDKs*, serta menerapkan *runtime schema enforcement engine* dengan overhead performa minimal (< 2ms p99).
- **Mengelola Siklus Hidup Kontrak Terdistribusi:** Mengorkestrasi skema *event-driven* dan *synchronous RPC/REST* menggunakan skema registri tersentralisasi dan memitigasi *drift* antara spesifikasi dan implementasi kode.

---

### 2. Prerequisite
Untuk menyerap materi ini secara optimal, peserta wajib menguasai:
- **Fondasi Protokol Jaringan:** HTTP/1.1, HTTP/2, semantics method, status code, TLS, dan arsitektur WebSocket/SSE.
- **JSON Schema Intermediate:** Pemahaman mendalam terkait kata kunci JSON Schema (`type`, `properties`, `required`, `pattern`, `anyOf`, `allOf`, `oneOf`).
- **Bahasa Pemrograman & Runtime:** Pengalaman tingkat menengah dengan TypeScript/Node.js atau Go (pemahaman tentang *interfaces*, *reflection*, dan *memory management*).
- **Dasar DevOps:** Pengetahuan operasional GitHub Actions/GitLab CI, Docker containerization, dan Semantic Versioning (SemVer 2.0.0).

---

### 3. Concept & Internal Architecture (Mendalam)

#### Konvergensi OpenAPI 3.1 dan JSON Schema Draft 2020-12
Pada OpenAPI 3.0, spesifikasi menggunakan superset/subset divergen dari JSON Schema Draft 00. Hal ini menimbulkan fragmentasi perkakas (*tooling fragmentation*), di mana pustaka validasi JSON standar tidak dapat memvalidasi dokumen OpenAPI secara langsung.

OpenAPI 3.1 menyelesaikan masalah ini dengan menyelaraskan dialeknya secara penuh ke **JSON Schema Draft 2020-12**:
- **Nullability:** Parameter `nullable: true` (OpenAPI 3.0) dieliminasi. OpenAPI 3.1 mengadopsi tipe union JSON Schema formal:
  ```yaml
  type: ["string", "null"]
  ```
- **Polimorfisme Lanjutan:** Penggunaan kata kunci `$dynamicAnchor` dan `$dynamicRef` memungkinkan evaluasi skema rekursif dan pewarisan tipe polimorfik tanpa batas ambiguitas lokal.
- **PrefixItems untuk Validasi Array Tuple:** Mendukung pemodelan struktur data heterogen berbasis indeks secara deterministik.

```
       OpenAPI 3.0.x                            OpenAPI 3.1.x
+---------------------------+            +---------------------------+
| Extended JSON Schema D00  |            |   JSON Schema 2020-12     |
| - nullable: true          |  =======>  | - type: [T, "null"]       |
| - custom discriminator    |            | - $defs & dynamicAnchor   |
| - limited dynamic refs    |            | - Standard vocabulary     |
+---------------------------+            +---------------------------+
```

#### Internal Architecture: AST Parsing & Semantic Diffing
Ketika dokumen kontrak API (`openapi.yaml`) masuk ke dalam pipeline rekayasa perangkat lunak, dokumen tersebut diuraikan menjadi pohon sintaks abstrak (**Abstract Syntax Tree / AST**). Engine linters (seperti Spectral) dan differs (seperti `oasdiff`) tidak memperlakukan spesifikasi sebagai teks mentah atau objek JSON murni, melainkan sebagai simpul semantik terstruktur (*structured semantic nodes*).

```
[Raw OpenAPI YAML/JSON]
           │
           ▼
[YAML/JSON Parser (e.g., YAMLScript)]
           │
           ▼
[Concrete Syntax Tree (CST)] ──(Position Map: Line, Col)
           │
           ▼
[Abstract Syntax Tree (AST)]
           │
           ├───────────────────────────────┬──────────────────────────────┐
           ▼                               ▼                              ▼
 [Spectral Rule Engine]          [Semantic Diff Engine]         [Template AST Compiler]
 - JSONPath/NIMMA queries        - Graph traversal              - Generator (Mustache/Jinja)
 - Node assertion checks         - Breaking-change matrix       - Type definitions emission
 - Violation reporting           - Changelog generation         - Stubs & Mock handlers
```

1. **Graph Traversal & Dereferencing:** Engine menganalisis relasi `$ref` (internal maupun eksternal via URI). Jika terjadi siklus referensi (*circular references*), algoritma pemecah dereferensi siklik memecah simpul menjadi representasi graf asiklik terarah (*Directed Acyclic Graph* / DAG) menggunakan penanda *lazy evaluation*.
2. **Semantic Breaking Change Engine:** Berbeda dengan Git diff berbasis baris teks, deteksi semantik membandingkan model relasional:
   - *Breaking:* Menambahkan field `required` baru pada skema request.
   - *Breaking:* Menghapus atau membatasi *enum value* pada skema request.
   - *Breaking:* Menambahkan *enum value* pada skema response (karena client dengan tipe ketat akan mengalami deserialization error).
   - *Breaking:* Mengubah status code respons sukses (misal `200 OK` menjadi `201 Created` tanpa fallback).
   - *Non-Breaking:* Menambahkan field opsional pada skema request.
   - *Non-Breaking:* Menambahkan field baru pada skema response (mengasumsikan client mematuhi Postel's Law / *Robustness Principle*).

#### Engine Validasi Runtime: Dynamic Evaluator vs Ahead-of-Time (AOT) Compiled Code
Pada arsitektur produksi, validasi payload HTTP terhadap skema OpenAPI dilakukan melalui dua pendekatan:

| Komponen | Dynamic Interpreted Engine (e.g., Python jsonschema) | AOT Compiled Engine (e.g., Ajv Standalone, Go Kin-OpenAPI) |
| :--- | :--- | :--- |
| **Mekanisme** | Menguraikan AST skema pada setiap siklus eksekusi dan mengevaluasi simpul secara rekursif per request. | Mengompilasi skema OpenAPI/JSON Schema menjadi kode JavaScript/Go murni saat proses *build* (*AOT code generation*). |
| **Latency Impact** | Overhead berkisar antara 5ms - 25ms per request berskala sedang. | Overhead berkisar antara 0.1ms - 0.8ms per request (hampir setara fungsi native). |
| **Memory Footprint** | Tinggi; mempertahankan seluruh skema AST dan objek memori referensi di RAM runtime. | Sangat rendah; representasi skema diubah menjadi instruksi percabangan kode teroptimasi (kondisional native). |
| **Keamanan** | Rentan terhadap DoS regex skema (*ReDoS*) jika parser tidak memiliki timeout terisolasi. | Dapat dianalisis secara statis saat kompilasi untuk mendeteksi catastrophic backtracking regex. |

---

### 4. Why & What

#### Kegagalan Paradigma Code-First di Skala Enterprise
Dalam paradigma *Code-First*, rekayasawan menulis kode implementasi (misal anotasi pada controller Java Spring atau Go struct tags), lalu dokumen OpenAPI digenerasi secara otomatis melalui refleksi runtime atau build tool. Di lingkungan enterprise dengan ratusan microservices, pendekatan ini memicu masalah struktural:

```
[Code-First Anti-Pattern Lifecycle]
Dev Team 1 ──> Ubah Kode Backend ──> Regenerasi Docs ──> Deploy
                                                             │
                  (Drift: API Docs Berubah Diam-diam)        │
                                                             ▼
                                                Frontend / Consumer Gagal Integrasi
                                                Integration Tests Pecah di Production!
```

1. **Contract Drift:** Implementasi internal bocor ke API publik tanpa desain arsitektur yang matang.
2. **Consumer Desynchronization:** Tim frontend dan sistem hilir (*downstream consumers*) terblokir menunggu kode backend selesai dideploy untuk mendapatkan definisi endpoint.
3. **Review Blindspots:** Pull Request yang memuat ribuan baris logika bisnis mempersulit peninjau (*reviewer*) untuk mengidentifikasi degradasi desain antarmuka atau kebocoran abstraksi data sensitif.

#### Paradigma Contract-First Sebagai Sumber Kebenaran Tunggal (*Single Source of Truth*)
*Contract-First* membalik alur kerja: kontrak API dirancang, di-lint, ditinjau oleh lintas tim, disimulasikan melalui *mock servers*, dan divalidasi dependensinya **sebelum satu baris pun kode produksi ditulis**.

```
[Contract-First Lifecycle]
       Design Contract (OpenAPI 3.1)
                    │
                    ▼
          Spectral Linting & Governance Pass?
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
    Parallel:               Parallel:
 Backend Code Gen       Frontend Mock Server
 (Stubs & Validasi)     (MSW / Prism)
        │                       │
        └───────────┬───────────┘
                    ▼
    Automated Semantic Contract Diffing
                    │
                    ▼
         Zero-Drift Production
```

- **What:** Kontrak API adalah artefak formal yang mendefinisikan batas sistem (*system boundaries*), semantik pertukaran data, aturan bisnis skematis, dan jaminan kompatibilitas.
- **Why:** Memangkas siklus integrasi dari hitungan minggu menjadi jam, memungkinkan eksekusi pengembangan paralel antara produsen dan konsumen, serta menjamin keandalan sistem melalui validasi matematis skema.

---

### 5. How (Workflow Detail)

Berikut adalah alur kerja operasional standar Contract-First berskala enterprise:

```
[Phase 1: Authoring]
  └─ OpenAPI 3.1 YAML disusun secara modular menggunakan multi-file domain splitting ($ref).
[Phase 2: Static Analysis & Linting]
  └─ Spectral CLI dijalankan secara lokal (pre-commit hook) dan CI pipeline dengan strict rule-sets.
[Phase 3: Semantic Diff & Breaking Change Gate]
  └─ Tool diffing (misal oasdiff) membandingkan commit aktif terhadap branch target (misal `main`).
  └─ Jika ditemukan breaking change: CI fail, blokir pull request kecuali terdapat persetujuan khusus & major semver bump.
[Phase 4: Artifact Generation & Registry Publishing]
  └─ Skema di-bundle menjadi single file distribution via Redocly / OpenAPI CLI.
  └─ Publish spesifikasi ke API Catalog tersentralisasi atau Schema Registry.
  └─ Code Generator menghasilkan Server Interfaces dan Client SDKs (TypeScript, Go, Java).
[Phase 5: Implementation & Strict Runtime Enforcement]
  └─ Server stub diimplementasikan oleh rekayasawan backend.
  └─ Middleware validasi request/response disematkan di layer HTTP routing untuk memvalidasi input/output payload.
```

---

### 6. Analogy & Diagram ASCII

#### Analogi Konseptual
Merancang perangkat lunak dengan pendekatan *Code-First* diibaratkan seperti membangun gedung pencakar langit dengan menuangkan semen fondasi terlebih dahulu, lalu menggambar cetak biru (*blueprint*) arsitektur setelah dinding berdiri. Jika lantai dasar melenceng 5 derajat, seluruh lantai di atasnya terancam runtuh saat integrasi mekanikal dan elektrikal dilakukan.

Pendekatan *Contract-First* adalah proses pembuatan cetak biru struktural bersertifikasi teknik sipil terlebih dahulu. Kontraktor elektrikal, perpipaan, dan interior dapat bekerja serentak di pabrikasi masing-masing berdasarkan cetak biru tersebut tanpa menunggu seluruh kerangka fisik gedung selesai didirikan.

#### Diagram Arsitektur Pipeline CI/CD Contract-First

```
+---------------------------------------------------------------------------------------------------+
| CI/CD Pipeline Gateway                                                                            |
|                                                                                                   |
|  Git Push / PR                                                                                    |
|       │                                                                                           |
|       ▼                                                                                           |
|  [Spectral Linting Engine] ──(Fails if casing, security, or docs rule violated)                   |
|       │ Passed                                                                                    |
|       ▼                                                                                           |
|  [oasdiff Semantic Engine]                                                                        |
|       ├── Compare: PR spec VS base branch (main)                                                  |
|       └── Breaking Change Found?                                                                  |
|             ├── YES ──> [SemVer Label is NOT 'MAJOR'?] ──> [FAIL Pipeline & Post Comment to PR]   |
|             └── NO  ──> [Continue Pipeline]                                                       |
|                               │                                                                   |
|       ┌───────────────────────┴──────────────────────────────────┐                                |
|       ▼                                                          ▼                                |
|  [Artifact Generator]                                      [Publishing Engine]                    |
|       ├── openapi-generator CLI                                  ├── Push to Schema Registry      |
|       │    ├── Client SDKs (NPM / Go Module)                     └── Update API Gateway Routing   |
|       │    └── Server Interfaces / Scaffolding                                                    |
|       └── Prism Docker Mock Service Generation                                                    |
+---------------------------------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: OpenAPI 3.1 Strict Schema Definition
Menunjukkan implementasi OpenAPI 3.1 murni dengan JSON Schema Draft 2020-12, tipe union, penanganan `null`, serta ekspresi regex deterministik.

```yaml
# contracts/simple-spec.yaml
openapi: 3.1.0
info:
  title: Micro-Wallet Service
  version: 1.0.0
  description: Layanan transaksi saldo berbasis OpenAPI 3.1 standar JSON Schema 2020-12.
paths:
  /wallets/{walletId}/balance:
    get:
      summary: Ambil saldo dompet pengguna
      operationId: getWalletBalance
      parameters:
        - name: walletId
          in: path
          required: true
          schema:
            type: string
            format: uuid
      responses:
        '200':
          description: Saldo berhasil diambil
          content:
            application/json:
              schema:
                $ref: '#/$defs/WalletBalanceResponse'
        '404':
          description: Dompet tidak ditemukan
          content:
            application/json:
              schema:
                $ref: '#/$defs/ErrorEnvelope'

$defs:
  WalletBalanceResponse:
    type: object
    additionalProperties: false
    required:
      - walletId
      - currency
      - amount
      - lastAuditedAt
    properties:
      walletId:
        type: string
        format: uuid
      currency:
        type: string
        enum: [IDR, USD, SGD]
      amount:
        type: integer
        minimum: 0
        description: Nilai nominal dalam satuan unit terkecil (e.g., Cents, Rupiah).
      lastAuditedAt:
        type: ["string", "null"]
        format: date-time
        description: Timestamp audit terakhir. Bernilai null jika belum pernah diaudit.

  ErrorEnvelope:
    type: object
    additionalProperties: false
    required:
      - errorCode
      - message
    properties:
      errorCode:
        type: string
        pattern: '^[A-Z0-9_]{5,32}$'
      message:
        type: string
        maxLength: 255
```

---

#### B. Practical Example: Production-Grade Implementation

Kita akan mengimplementasikan skenario end-to-end:
1. Custom Spectral Rule Definition (`.spectral.yaml`).
2. Enterprise-Grade CI/CD Breaking Change Check via GitHub Actions.
3. Server Runtime Schema Enforcement Middleware pada Go menggunakan engine routing router OpenAPI native.

##### 1. Konfigurasi Linting AST Perusahaan: `.spectral.yaml`
Konfigurasi ini memastikan seluruh URL berformat kebab-case, setiap respons memuat trace ID, dan melarang penggunaan tipe data primitif tanpa batasan panjang/nilai.

```yaml
# .spectral.yaml
extends: ["spectral:oas"]

rules:
  # Penegakan casing URL kebab-case
  paths-kebab-case:
    description: Seluruh path URL harus menggunakan format kebab-case.
    severity: error
    given: $.paths[*]~
    then:
      function: pattern
      functionOptions:
        match: "^(/[a-z0-9]+(-[a-z0-9]+)*|/{[a-zA-Z0-9_]+})+$"

  # Melarang properti string tanpa pembatasan ukuran memori (mencegah DoS)
  no-unbounded-strings:
    description: Seluruh field string harus mendefinisikan maxLength atau pattern.
    severity: warn
    given: "$..properties[?(@.type === 'string' && !@.maxLength && !@.pattern && !@.enum && !@.format)]"
    then:
      function: defined

  # Penegakan trace ID pada envelope error response
  error-response-must-have-trace-id:
    description: Respons 4xx dan 5xx wajib mereferensikan properti traceId.
    severity: error
    given: "$.paths..responses[?(@property.match(/^[45]/))].content['application/json'].schema"
    then:
      field: properties.traceId
      function: defined
```

##### 2. Automation Engine: GitHub Actions Contract Governance Pipeline
Pipeline ini memvalidasi aturan linting dan memblokir breaking changes secara semantik sebelum kode di-merge ke branch `main`.

```yaml
# .github/workflows/contract-governance.yml
name: API Contract Governance & Compatibility Check

on:
  pull_request:
    paths:
      - "contracts/**"

jobs:
  lint-and-validate:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Source Code
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Setup Node.js Environment
        uses: actions/setup-node@v4
        with:
          node-version: 20

      - name: Install Linting Tooling
        run: npm install -g @stoplight/spectral-cli @redocly/cli

      - name: Execute Spectral AST Linting
        run: |
          spectral lint contracts/**/*.yaml --ruleset .spectral.yaml --fail-severity=error

      - name: Validate OpenAPI 3.1 Structural Integrity
        run: |
          redocly lint contracts/root.yaml

  breaking-change-detection:
    runs-on: ubuntu-latest
    needs: lint-and-validate
    steps:
      - name: Checkout Current PR Branch
        uses: actions/checkout@v4

      - name: Fetch Target Base Branch
        run: |
          git fetch origin main:main

      - name: Setup oasdiff Binary
        run: |
          curl -fsSL https://raw.githubusercontent.com/tufin/oasdiff/main/install.sh | sh
          sudo mv bin/oasdiff /usr/local/bin/

      - name: Run Semantic AST Diffing
        id: diff-check
        run: |
          # Periksa apakah ada breaking changes dari main ke branch PR
          oasdiff breaking origin/main:contracts/root.yaml contracts/root.yaml --format text > breaking_report.txt || true
          
          if [ -s breaking_report.txt ]; then
            echo "BREAKING_CHANGES_DETECTED=true" >> $GITHUB_ENV
            echo "::error::Breaking changes detected in API contract!"
            cat breaking_report.txt
          else
            echo "BREAKING_CHANGES_DETECTED=false" >> $GITHUB_ENV
            echo "Kontrak sepenuhnya kompatibel (Non-breaking)."
          fi

      - name: Enforce PR Failure on Unlabeled Breaking Changes
        if: env.BREAKING_CHANGES_DETECTED == 'true'
        run: |
          # Validasi label PR: Jika ada breaking change, PR wajib memiliki label 'release:major'
          PR_LABELS="${{ toJson(github.event.pull_request.labels.*.name) }}"
          if [[ ! "$PR_LABELS" =~ "release:major" ]]; then
            echo "FATAL: Ditemukan breaking change pada kontrak API, namun PR tidak memiliki label 'release:major'."
            echo "Hubungi System Architect dan bump versi mayor spesifikasi sebelum melakukan merge."
            exit 1
          fi
```

##### 3. Go Production Runtime: OpenAPI Schema Enforcement Middleware
Implementasi server Go menggunakan library `getkin/kin-openapi` untuk memvalidasi request HTTP secara real-time terhadap spesifikasi OpenAPI 3.1 sebelum payload masuk ke *business logic handler*.

```go
// cmd/server/main.go
package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"

	"github.com/getkin/kin-openapi/openapi3"
	"github.com/getkin/kin-openapi/openapi3filter"
	legacyrouter "github.com/getkin/kin-openapi/routers/gorillamux"
)

// OpenAPIValidationMiddleware membungkus http.Handler untuk memvalidasi payload request
func OpenAPIValidationMiddleware(doc *openapi3.T) func(http.Handler) http.Handler {
	router, err := legacyrouter.NewRouter(doc)
	if err != nil {
		log.Fatalf("Gagal menginisialisasi router skema OpenAPI: %v", err)
	}

	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			// 1. Temukan rute pada spesifikasi OpenAPI yang sesuai dengan HTTP request masuk
			route, pathParams, err := router.FindRoute(r)
			if err != nil {
				writeErrorJSON(w, http.StatusNotFound, "ROUTE_NOT_FOUND", "Endpoint tidak terdaftar dalam kontrak spesifikasi.")
				return
			}

			// 2. Siapkan parameter validasi request
			requestValidationInput := &openapi3filter.RequestValidationInput{
				Request:    r,
				PathParams: pathParams,
				Route:      route,
				Options: &openapi3filter.Options{
					MultiError: true, // Tangkap seluruh error validasi, bukan hanya error pertama
				},
			}

			// 3. Eksekusi validasi AST terhadap query parameters, headers, dan payload body
			ctx := r.Context()
			if err := openapi3filter.ValidateRequest(ctx, requestValidationInput); err != nil {
				writeErrorJSON(w, http.StatusUnprocessableEntity, "CONTRACT_VIOLATION", err.Error())
				return
			}

			// Request valid sesuai kontrak, lanjutkan ke handler aplikasi berikutnya
			next.ServeHTTP(w, r)
		})
	}
}

func writeErrorJSON(w http.ResponseWriter, statusCode int, errorCode string, message string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(statusCode)
	// Output terstruktur sesuai kontrak $defs/ErrorEnvelope
	fmt.Fprintf(w, `{"errorCode":"%s","message":%q}`, errorCode, message)
}

func main() {
	ctx := context.Background()
	loader := openapi3.NewLoader()
	loader.IsExternalRefsAllowed = true

	// Membaca spesifikasi yang telah dibundle
	specPath := "contracts/root.yaml"
	doc, err := loader.LoadFromFile(specPath)
	if err != nil {
		log.Fatalf("Gagal memuat file kontrak: %v", err)
	}

	// Validasi integritas internal dokumen OpenAPI
	if err := doc.Validate(ctx); err != nil {
		log.Fatalf("Integritas file kontrak OpenAPI tidak valid: %v", err)
	}

	mux := http.NewServeMux()

	// Implementasi endpoint bisnis
	mux.HandleFunc("/wallets/", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		// Respons terstruktur sesuai kontrak WalletBalanceResponse
		w.Write([]byte(`{
			"walletId": "a8098c1a-f86e-11da-bd1a-00112444be1e",
			"currency": "IDR",
			"amount": 50000000,
			"lastAuditedAt": null
		}`))
	})

	// Rangkai middleware
	validatedHandler := OpenAPIValidationMiddleware(doc)(mux)

	port := 8080
	log.Printf("Engine produksi aktif pada port :%d (Strict Schema Enforcement diaktifkan)", port)
	if err := http.ListenAndServe(fmt.Sprintf(":%d", port), validatedHandler); err != nil {
		log.Fatalf("Server berhenti mendadak: %v", err)
	}
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem: Transisi Pembayaran Global "PayNexus"
PayNexus memproses 120.000 transaksi pembayaran per detik (TPS) pada puncak beban. Arsitektur terdiri dari 85 layanan microservices yang dibangun dengan Go, Java, dan Node.js.

#### Insiden Fatal Sebelum Standardisasi Kontrak
Tim Merchant Settlement mengubah format field respons `settlementTimestamp` dari string ISO-8601 (`2023-10-15T08:00:00Z`) menjadi representasi integer Unix Epoch Milliseconds (`1697356800000`) pada rilis minor (v2.1.0). Perubahan ini dilakukan menggunakan pendekatan *Code-First*. 

Akibatnya:
- Layanan Financial Auditing (Java Spring) mengalami kegagalan *JSON deserialization parsing exception*.
- Antrean *dead-letter queue* (DLQ) membludak hingga 4.2 juta transaksi tertunda.
- Dampak finansial: Kerugian SLA denda keterlambatan settlement sebesar $380,000 USD dalam 3 jam downtime parsial.

#### Solusi Arsitektural Contract-First PayNexus
PayNexus merombak total metodologi rekayasa API mereka dengan menerapkan arsitektur terpadu:

```
[API Core Spec Repo] 
         │ (Git Push)
         ▼
[Automated GitHub Actions]
   ├── Spectral AST Check (Security, Casing, Strict Types)
   ├── Buf & oasdiff Engine Check (Zero Breaking Changes Tolerated)
   └── Bundler (Redocly)
         │
         ▼
[Artifactory / Central Schema Registry]
   ├── Generasi Otomatis SDK Client (TypeScript, Java, Go) via AOT Generator
   └── Registrasi Route Definition ke Kong API Gateway
         │
         ▼
[Microservices Mesh Deployment]
   ├── Gateway memvalidasi Schema Ingress (Menolak payload sampah di perimeter terluar)
   └── Internal Service menjalankan AOT Compiled Schema Validation (Ajv Standalone / Kin-OpenAPI)
```

#### Hasil Metrik Pasca Implementasi (Audit 6 Bulan)
- **Contract Drift Incidents:** Berkurang dari 14 insiden per kuartal menjadi **0 insiden**.
- **Time-to-Integration:** Penurunan durasi integrasi tim consumer (Web/Mobile) terhadap API baru dari **9 hari kerja** menjadi **kurang dari 4 jam** karena tersedianya Mock Server otomatis sejak fase desain.
- **Payload Validation Overhead:** Berkat validasi AOT engine di layer API Gateway, beban CPU internal microservice berkurang sebesar **18%**.

---

### 9. Trade-offs

| Dimensi Arsitektural | Keuntungan (*Pros*) | Konsekuensi / Kerugian (*Cons*) |
| :--- | :--- | :--- |
| **Strict Runtime Validation** | Menjamin integritas data 100% masuk ke *domain logic*; mencegah serangan injeksi parameter tak dikenal (*mass assignment attack*). | Menambahkan penalti latensi CPU (0.2ms - 3ms tergantung kompleksitas payload & regex); konsumsi alokasi memori heap tambahan pada pipeline HTTP. |
| **Monorepo Schema Registry** | Visibilitas perubahan lintas batas divisi optimal; pendeteksian dependensi siklik dan *breaking change* dapat dieksekusi terpusat. | Butuh koordinasi tata kelola (*governance*) yang ketat; pipeline build CI menjadi lebih panjang; risiko bottleneck approval dari tim platform core. |
| **Automated SDK Code Generation** | Konsistensi penamaan tipe client 100% identik dengan server; eliminasi *human-error* dalam penulisan payload HTTP network call. | Kode hasil generasi (*generated code*) sering kali verbose (*bloated*); abstraksi yang kaku mempersulit kustomisasi logika koneksi level rendah (*custom connection pooling/retries*). |
| **OpenAPI 3.1 vs 3.0** | Kompatibilitas penuh dengan standar JSON Schema 2020-12; dukungan native union types (`type: [string, null]`). | Ekosistem tooling pihak ketiga (beberapa cloud API Gateway vendor lama) belum sepenuhnya mendukung spesifikasi 3.1 dan masih terbatas pada 3.0. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Kesalahan: Ambiguitas Evaluasi Polimorfisme Tanpa Properti `discriminator`
*Masalah:* Menggunakan `oneOf` atau `anyOf` untuk membedakan dua payload tanpa mendefinisikan objek `discriminator` eksplisit:
```yaml
# SALAH: Engine runtime akan memvalidasi terhadap SEMUA skema, memicu performa lambat dan error ambigu
paymentMethod:
  oneOf:
    - $ref: '#/$defs/CreditCard'
    - $ref: '#/$defs/BankTransfer'
```
*Solusi:* Definisikan `discriminator` dengan pemetaan eksplisit (*explicit mapping*):
```yaml
# BENAR: Evaluasi skema bersifat O(1) deterministik berdasarkan nilai field 'type'
paymentMethod:
  type: object
  discriminator:
    propertyName: type
    mapping:
      card: '#/$defs/CreditCard'
      va: '#/$defs/BankTransfer'
  oneOf:
    - $ref: '#/$defs/CreditCard'
    - $ref: '#/$defs/BankTransfer'
```

#### 2. Kesalahan: Kebocoran Breaking Change Tersembunyi pada Response Enums
*Masalah:* Rekayasawan menambahkan enum baru pada skema respons dengan anggapan non-breaking:
```yaml
# Versi 1.0.0
TransactionStatus:
  type: string
  enum: [PENDING, SUCCESS, FAILED]

# Versi 1.1.0 (Dianggap Minor)
TransactionStatus:
  type: string
  enum: [PENDING, SUCCESS, FAILED, EXPIRED] # <-- FATAL: BREAKING CHANGE!
```
*Troubleshooting:* Klien yang menggunakan bahasa bertipe statis (seperti Java, Swift, Rust, atau Go) akan mengalami *unmarshaling failure* karena enum internal mereka tidak mengenali nilai `EXPIRED`. 
*Mitigasi:* Gunakan detektor AST (`oasdiff`) dalam CI/CD pipeline yang secara otomatis mengklasifikasikan penambahan *enum respons* sebagai breaking change, kecuali spesifikasi klien secara eksplisit memiliki fallback `UNKNOWN_VALUE`.

#### 3. Kesalahan: ReDoS (Regular Expression Denial of Service) pada Validasi Skema
*Masalah:* Menggunakan regex tanpa pembatasan kompleksitas pada kata kunci `pattern`:
```yaml
pattern: '^([a-zA-Z0-9]+)+$' # Memicu catastrophic backtracking jika menerima input panjang tidak valid
```
*Solusi:* Tetapkan batas panjang maksimum pada string yang menggunakan regex melalui `maxLength`, dan pastikan pola ekspresi reguler bersifat linear $O(N)$ (hindari evaluasi kuadratik bertingkat).

---

### 11. Best Practices (Production Checklist)

#### Standard Governance Checklist
- [ ] **SemVer Enforcement:** Mengadopsi Semantic Versioning ketat:
  - MAJOR: Menghapus endpoint, menghapus field response, menambah required request parameter, menambah enum response.
  - MINOR: Menambah endpoint baru, menambah field response opsional, menambah skema baru.
  - PATCH: Pembaruan deskripsi, perbaikan dokumentasi metadata skema.
- [ ] **Sunset & Deprecation Headers:** Endpoint lama yang ditandai `deprecated: true` pada OpenAPI wajib menyuntikkan header HTTP formal pada response:
  ```http
  Deprecation: @1735689600
  Sunset: Wed, 01 Jan 2025 00:00:00 GMT
  Link: <https://api.domain.com/docs/v2>; rel="successor-version"
  ```
- [ ] **Properti `additionalProperties: false`:** Wajib dideklarasikan pada seluruh payload mutasi (`POST`, `PUT`, `PATCH`) untuk mencegah injeksi field sampah (*payload pollution*).
- [ ] **Batas Atas Payload (*Bounding Limits*):** Seluruh tipe `string` wajib memiliki `maxLength`, tipe `array` memiliki `maxItems`, dan tipe `integer/number` memiliki `minimum` serta `maximum`.
- [ ] **Standardisasi Error Envelope:** Format respons error wajib mematuhi standar terpadu (seperti RFC 7807 / RFC 9457 `Problem Details for HTTP APIs`).

---

### 12. Hands-on Practice

Dalam latihan ini, Anda akan membangun pipeline validasi kontrak lokal lengkap dengan konfigurasi Spectral, script deteksi breaking changes, serta file validasi spec.

#### Struktur Direktori
Simpan seluruh artefak praktikum pada direktori `hands-on/m02/`:

```
hands-on/m02/
├── .spectral.yaml
├── package.json
├── contracts/
│   ├── base-spec.yaml
│   └── current-spec.yaml
└── scripts/
    └── check-breaking.sh
```

#### Langkah 1: Inisialisasi Project & Dependensi
Buka terminal dan navigasikan ke root workspace:

```bash
mkdir -p hands-on/m02/contracts hands-on/m02/scripts
cd hands-on/m02
npm init -y
npm install --save-dev @stoplight/spectral-cli @redocly/cli
```

#### Langkah 2: Buat Aturan Custom Spectral
Buat file `hands-on/m02/.spectral.yaml`:

```yaml
extends: ["spectral:oas"]

rules:
  operation-4xx-response:
    description: Setiap operasi HTTP wajib mendefinisikan respons penanganan kesalahan 4xx.
    severity: error
    given: $.paths.*[get,post,put,delete,patch]
    then:
      field: responses
      function: schema
      functionOptions:
        schema:
          type: object
          patternProperties:
            "^4[0-9]{2}$":
              type: object
```

#### Langkah 3: Siapkan Kontrak API Baseline & Kontrak Eksperimental
Buat baseline kontrak (versi produksi saat ini) di `hands-on/m02/contracts/base-spec.yaml`:

```yaml
openapi: 3.1.0
info:
  title: Order Management API
  version: 1.0.0
paths:
  /orders:
    post:
      summary: Buat pesanan baru
      operationId: createOrder
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required:
                - customerId
                - amount
              properties:
                customerId:
                  type: string
                  format: uuid
                amount:
                  type: number
                  minimum: 0.01
      responses:
        '201':
          description: Created
          content:
            application/json:
              schema:
                type: object
                required:
                  - orderId
                properties:
                  orderId:
                    type: string
                    format: uuid
        '400':
          description: Bad Request
```

Buat kontrak baru yang memuat modifikasi di `hands-on/m02/contracts/current-spec.yaml`:

```yaml
openapi: 3.1.0
info:
  title: Order Management API
  version: 1.1.0
paths:
  /orders:
    post:
      summary: Buat pesanan baru
      operationId: createOrder
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required:
                - customerId
                - amount
                - paymentMethodId # <-- BREAKING CHANGE: Menambahkan required field baru!
              properties:
                customerId:
                  type: string
                  format: uuid
                amount:
                  type: number
                  minimum: 0.01
                paymentMethodId:
                  type: string
                  format: uuid
      responses:
        '201':
          description: Created
          content:
            application/json:
              schema:
                type: object
                required:
                  - orderId
                properties:
                  orderId:
                    type: string
                    format: uuid
        '400':
          description: Bad Request
```

#### Langkah 4: Buat Script Validasi Lokal
Buat file executable di `hands-on/m02/scripts/check-breaking.sh`:

```bash
#!/usr/bin/env bash
set -e

echo "[1/3] Menjalankan Spectral Linter..."
npx spectral lint contracts/current-spec.yaml --ruleset .spectral.yaml

echo "[2/3] Memasang tool OASDiff (menggunakan Docker)..."
docker run --rm -v $(pwd)/contracts:/specs \
  tufin/oasdiff:latest \
  breaking /specs/base-spec.yaml /specs/current-spec.yaml --format text > breaking.log || true

echo "[3/3] Menganalisis Laporan Breaking Changes..."
if [ -s breaking.log ]; then
  echo "=========================================================="
  echo "PERINGATAN: BREAKING CHANGES TERDETEKSI PADA KONTRAK API!"
  echo "=========================================================="
  cat breaking.log
  echo "=========================================================="
  rm -f breaking.log
  exit 1
else
  echo "Sukses: Perubahan bersifat backward-compatible."
  rm -f breaking.log
fi
```

Beri izin eksekusi dan jalankan:

```bash
chmod +x scripts/check-breaking.sh
./scripts/check-breaking.sh
```

Perhatikan bahwa skrip akan menggagalkan build karena penambahan `paymentMethodId` terdeteksi memutus kompatibilitas konsumen lama.

---

### 13. Exercise

#### Level Easy
Ubah file `hands-on/m02/contracts/current-spec.yaml` agar field `paymentMethodId` bersifat *non-breaking* (opsional), namun jika field tersebut dikirimkan oleh klien, formatnya wajib berupa UUID. Jalankan kembali `./scripts/check-breaking.sh` hingga mencapai status lolos verifikasi (exit status 0).

#### Level Medium
Tuliskan satu *custom rule* Spectral baru pada `.spectral.yaml` dengan nama `enforce-request-id-header` yang mewajibkan seluruh operasi `post` dan `put` memiliki header parameter bernama `X-Correlation-ID` dengan tipe data string format UUID. Uji aturan tersebut terhadap spesifikasi yang ada hingga menghasilkan error linting yang akurat.

#### Level Hard
Rancang spesifikasi OpenAPI 3.1 modular untuk model domain E-Commerce Checkout yang memanfaatkan komponen polimorfik:
1. Skema request payload `CheckoutRequest` yang menerima array heterogen berisi objek item pembayaran (`CashOnDeliveryPayment`, `CreditCardPayment`, atau `EWalletPayment`).
2. Gunakan kata kunci `discriminator` yang mengarah ke properti `paymentType`.
3. Terapkan validasi ketat sehingga setiap tipe pembayaran memiliki batas-batas validasi spesifik (misal: panjang digit CVV, format enum nama e-wallet).
4. Pisahkan skema komponen tersebut ke dalam file-file terpisah (`schemas/payment.yaml`, `schemas/cart.yaml`) dan integrasikan menggunakan referensi `$ref`.

---

### 14. Challenge

#### Skenario Kasus Kompleks: Arsitektur Hybrid REST Sync & Event-Driven AsyncAPI
Anda bertindak sebagai Principal API Architect di sebuah platform logistik multi-nasional. Perusahaan sedang bertransisi dari monolit ke event-driven architecture, di mana setiap operasi bisnis melibatkan dua saluran sekaligus:
1. Klien memanggil endpoint HTTP REST (`POST /shipments`) untuk memesan pengiriman.
2. Ketika status pengiriman berubah (e.g., `PICKED_UP`, `IN_TRANSIT`, `DELIVERED`), sistem menyiarkan event melalui Kafka topic `shipment.lifecycle.v1`.

#### Tugas Arsitektural Anda:
1. Rancang cetak biru repositori terpadu yang memadukan spesifikasi **OpenAPI 3.1** (untuk endpoint REST) dan **AsyncAPI 3.0** (untuk pesan Kafka).
2. Terapkan mekanisme di mana payload objek inti `ShipmentEntity` **hanya didefinisikan satu kali** sebagai file JSON Schema Draft 2020-12 independen, lalu direferensikan silang secara valid oleh kedua spesifikasi (OpenAPI dan AsyncAPI) tanpa redundansi definisi.
3. Rancang strategi versioning dan skrip CI/CD pipeline yang mendeteksi skenario berikut:
   - Jika ada developer yang mengubah field bertipe kritis di `ShipmentEntity`, pipeline wajib mengevaluasi dampak destruktif (*breaking change impact analysis*) secara simultan terhadap kontrak HTTP REST dan konsumen topic Kafka.
4. Susun rencana migrasi tanpa downtime (*Zero-Downtime Migration Plan*) untuk menangani perubahan struktur format koordinat GPS armada kurir dari format string `lat,long` menjadi nested object `{ "latitude": float64, "longitude": float64 }`.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic Questions
1. Mengapa parameter `nullable: true` tidak lagi direkomendasikan pada OpenAPI 3.1?
   - *Jawaban:* Karena OpenAPI 3.1 telah selaras penuh dengan JSON Schema Draft 2020-12 yang secara native mendukung union type, sehingga pendekatan standar yang digunakan adalah `type: ["string", "null"]`.
2. Apa perbedaan mendasar antara Abstract Syntax Tree (AST) linting dibandingkan dengan regular expression (Regex) grep linting?
   - *Jawaban:* AST menguraikan dokumen menjadi struktur hierarki pohon berbasis semantik dan pemetaan konteks grammar formal, sehingga mampu mengenali relasi simpul dan path secara presisi tanpa terpengaruh oleh indentasi atau urutan penulisan, sedangkan Regex grep hanya mencocokkan pola teks mentah yang rentan terhadap false positive.
3. Apa peran kata kunci `additionalProperties: false` dalam skema OpenAPI?
   - *Jawaban:* Untuk melarang payload menerima field tambahan yang tidak didefinisikan secara eksplisit di dalam skema, mencegah serangan mass assignment dan inkonsistensi data.
4. Mengapa penambahan properti baru pada skema request bersifat breaking change jika properti tersebut berstatus `required`?
   - *Jawaban:* Karena klien lama yang mengirimkan payload tanpa properti baru tersebut akan ditolak oleh sistem validasi server (HTTP 400/422).
5. Pada layer arsitektur apa runtime schema enforcement idealnya dijalankan untuk proteksi optimal?
   - *Jawaban:* Pada perimeter terluar ingress (API Gateway atau Middleware Router layer) sebelum request masuk dan dialokasikan ke layer logika domain internal (*application business core*).

#### Intermediate Questions
6. Mengapa penambahan nilai enum baru pada response payload dianggap sebagai breaking change oleh library diffing semantik?
   - *Jawaban:* Klien dengan sistem tipe data statis (seperti Go, Java, C#, Swift) biasanya men-deserialisasi enum ke konstanta bahasa. Kehadiran nilai enum baru yang tidak dikenal akan memicu runtime serialization/parsing error pada sisi klien.
7. Jelaskan bagaimana mekanisme resolving siklik (*circular `$ref`*) ditangani oleh generator kode API!
   - *Jawaban:* Generator memutus referensi langsung tak hingga dengan membungkus tipe yang berulang menggunakan pointer (pada Go/C++), referensi memori tidak langsung (lazily-evaluated objects), atau interface generic agar ukuran alokasi memori saat inisialisasi tipe tidak bernilai tak terhingga.
8. Apa implikasi performa dari penggunaan dynamic validation engine berbasis JSON Schema dibandingkan AOT (Ahead-of-Time) validation code?
   - *Jawaban:* Dynamic engine menginterpretasikan aturan skema pada setiap siklus request melalui pembacaan memori pohon skema yang memicu penalti latensi CPU (beberapa milidetik) dan peningkatan GC pressure, sedangkan AOT mengompilasi skema menjadi kode kondisional native (if-else statements) yang memiliki latensi sub-milidetik.
9. Bagaimana cara kerja kata kunci `discriminator` pada OpenAPI dalam mempercepat evaluasi validasi skema polimorfik?
   - *Jawaban:* Discriminator bertindak sebagai penunjuk indeks langsung ke skema target melalui pemetaan eksplisit properti pembeda, mengubah kompleksitas evaluasi pengujian dari $O(N)$ (menguji semua skema `oneOf` satu per satu) menjadi $O(1)$.
10. Sebutkan dua header HTTP standar IETF yang wajib dikirimkan oleh server saat melayani rute API yang telah ditandai sebagai *deprecated* pada kontrak!
    - *Jawaban:* Header `Deprecation` (menunjukkan waktu deprecation) dan header `Sunset` (menunjukkan tanggal resmi rute tersebut dimatikan secara permanen).

#### Skenario Kasus Produksi
11. **Skenario 1:** Sebuah tim backend merilis perbaikan bug di mana field `phoneNumber` pada respons diubah validasi regex-nya dari mengizinkan karakter bebas menjadi format E.164 (`^\+[1-9]\d{1,14}$`). Mengapa hal ini memicu insiden di level konsumen aplikasi mobile, dan bagaimana skema kontrak seharusnya mengantisipasi hal ini?
    - *Solusi Arsitektural:* Klien lama kemungkinan menyimpan nomor telepon dalam format lokal non-E.164 di database lokal mereka. Ketika respons divalidasi secara lokal oleh SDK client terhadap kontrak baru yang ketat, terjadi parsing crash. Tim backend seharusnya tidak mengetatkan aturan validasi output tanpa strategi migrasi data historis, atau harus memisahkan representasi field raw dan normalized (`phoneNumberRaw` dan `phoneNumberE164`).
12. **Skenario 2:** Pipeline CI/CD Anda memproses dokumen OpenAPI berukuran 8 MB yang memuat ribuan `$ref` eksternal. Waktu eksekusi linting Spectral melonjak hingga 12 menit dan menyebabkan pipeline antrean merge terblokir. Optimasi apa yang harus diterapkan?
    - *Solusi Arsitektural:* Terapkan pre-bundling skema menjadi artefak tunggal (*single dereferenced artifact*) menggunakan tool kompilasi berkinerja tinggi berbasis AST parser multi-thread seperti `@redocly/cli bundle` sebelum linting. Selain itu, batasi eksekusi linter Spectral hanya terhadap sub-file yang mengalami perubahan pada git commit menggunakan selective path filtering.
13. **Skenario 3:** Tim Anda menggunakan OpenTelemetry untuk tracing. Diperlukan standarisasi bahwa seluruh payload error (HTTP 4xx dan 5xx) di 40 microservices harus menyertakan `traceId` yang sinkron dengan context trace distributed tracing. Bagaimana Anda memaksakan tata kelola ini secara mutlak tanpa mengedit satu per satu repositori aplikasi?
    - *Solusi Arsitektural:* Buat custom Spectral ruleset enterprise yang di-*publish* sebagai package NPM privat atau URL terpusat. Terapkan rule dengan target path `$.paths..responses[?(@property.match(/^[45]/))]` yang memvalidasi keberadaan properti `traceId`. Masukkan ruleset ini ke dalam reusable standard CI pipeline templates yang wajib di-*extend* oleh seluruh repositori microservices di organisasi. PR yang melanggar kontrak error envelope akan ditolak secara otomatis di level gate CI.

---

### 16. Summary

1. **Prinsip Utama Contract-First:** Kontrak API (OpenAPI 3.1 / AsyncAPI 3.0) berfungsi sebagai cetak biru arsitektur dan *single source of truth* formal. Seluruh kode backend, client SDK, mock server, dan pengujian integrasi diturunkan langsung dari kontrak, bukan sebaliknya.
2. **Penyelarasan OpenAPI 3.1 & JSON Schema 2020-12:** Standardisasi OpenAPI 3.1 mengeliminasi fragmentasi dialek tipe data, mengadopsi native union types (`type: ["string", "null"]`), dan memungkinkan interoperabilitas penuh dengan engine JSON Schema modern.
3. **Automasi Tata Kelola (AST & CI Gate):** Penegakan standar perancangan API tidak boleh bergantung pada tinjauan manual manusia. Penggunaan Spectral untuk validasi AST dan oasdiff untuk deteksi *breaking changes* semantik secara otomatis menjamin stabilitas backward-compatibility ekosistem microservices enterprise.
4. **Validasi Runtime Berkinerja Tinggi:** Skema kontrak harus ditegakkan pada lapisan runtime request/response engine untuk mencegah *contract drift* dan serangan data injection. Penggunaan compiled validation middleware menjamin overhead eksekusi tetap berada pada batas latensi sub-milidetik.