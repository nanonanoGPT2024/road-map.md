# BAB 09 / MODUL 01: DEVELOPER EXPERIENCE (DX), SDKS, & OBSERVABILITY

---

## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul**: `ARCH-API-09-01`
* **Nama Modul**: Developer Experience (DX), SDKs, & Observability: RFC 7807/9457 Problem Details, Automated SDK Generation, Contract Testing, dan W3C Distributed Tracing
* **Kategori**: 06-Architecture-and-System-Design
* **Tingkat Kesulitan**: Advanced / Senior Level
* **Prasyarat**:
  * Pemahaman mendalam mengenai protokol HTTP/1.1 dan HTTP/2 (status codes, headers, MIME types).
  * Penguasaan spesifikasi OpenAPI 3.0/3.1 (OAS).
  * Pengalaman membangun RESTful API berbasis microservices dengan bahasa pemrograman Go, Node.js/TypeScript, atau sejenisnya.
  * Pemahaman dasar tentang continuous integration (CI/CD) pipelines dan distributed systems.
* **Estimasi Waktu Selesai**: 4 - 6 Jam Pembelajaran Mandiri / Hands-on Lab

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
1. **Mengabstraksikan dan Menerapkan Standard Error Handling**: Merancang serta mengimplementasikan skema penanganan kesalahan HTTP berbasis standar RFC 7807 dan RFC 9457 (`application/problem+json`), termasuk pemanfaatan ekstensi konteks domain error tanpa membocorkan infrastruktur internal.
2. **Mengotomatisasi Siklus Hidup SDK**: Membangun pipeline otomatisasi *code generation* SDK multi-bahasa dari satu sumber kebenaran (*single source of truth*) OpenAPI 3.1 menggunakan perkakas *generation tooling* industri.
3. **Mengintegrasikan Contract Testing**: Menerapkan validasi kontrak berbasis schema (*mock/validation*) menggunakan Prism serta *Consumer-Driven Contract Testing* (CDCT) menggunakan framework Pact guna mengeliminasi regresi integrasi lintas tim.
4. **Mengimplementasikan W3C Distributed Tracing**: Mengonfigurasi propagasi konteks *tracing* terdistribusi lintas batas layanan (*network boundary*) sesuai standar W3C Trace Context (`traceparent` dan `tracestate`) untuk mewujudkan observabilitas *end-to-end*.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                       API DESIGN QUALITY & USABILITY (DX)
                                      |
         +----------------------------+----------------------------+
         |                                                         |
  CONSUMABILITY & CONTRACTS                                 OBSERVABILITY & TRIAGE
         |                                                         |
  +------+------+                                           +------+------+
  |             |                                           |             |
RFC 9457     SDK AUTOMATION                              W3C TRACING   CONTRACT TESTING
(Errors)     (Tooling)                                   (Telemetry)   (Verification)
  |             |                                           |             |
  +-- Type      +-- OpenAPI 3.1 AST                         +-- traceparent +-- Prism (Schema-driven)
  +-- Title     +-- CodeGen (OpenAPI-Gen/Speakeasy)         +-- tracestate  +-- Pact (Consumer-driven)
  +-- Status    +-- Semantic Versioning Automation          +-- Context Extractor/Injector
  +-- Detail    +-- Multi-language Target Distribution
  +-- Instance
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

1. **Fragmentasi Respons Galat Mengakibatkan Biaya Integrasi Tinggi**: Tanpa standarisasi formal, setiap tim mikroservis cenderung menciptakan skema galat (*error schema*) tersendiri (misal: `{ "error": "msg" }`, `{ "errors": [...] }`, `{ "code": 1024, "message": "fail" }`). Konsumen API terpaksa menulis logika *parsing* defensif yang rapuh, memperlambat *time-to-market*, dan meningkatkan potensi kegagalan runtime.
2. **Pemeliharaan SDK Manual Bersifat *Error-Prone* dan Tidak Terukur**: Membangun client library secara manual untuk berbagai ekosistem bahasa (TypeScript, Go, Python, Java) menuntut sumber daya *engineering* yang masif. Ketidaksesuaian tipikal antara dokumentasi API dan implementasi SDK manual menyebabkan *bug* fungsional di tingkat konsumen.
3. **End-to-End Integration Testing di Lingkungan Staging Bersifat Lambat dan Rapuh**: Mengandalkan pengujian integrasi *end-to-end* (E2E) pada lingkungan *staging* berskala besar menyebabkan *flakiness*, antrean rilis panjang, serta kesulitan isolasi akar masalah. *Contract testing* memindahkan verifikasi kompatibilitas ke fase *shift-left* (pipeline CI pengembang lokal).
4. **Kegagalan Pelacakan dalam Sistem Terdistribusi (Microservices Black Box)**: Ketika sebuah transaksi bisnis melewati belasan layanan dan menghasilkan status HTTP 500, ketiadaan *distributed trace propagation* standar mengharuskan *engineering team* melakukan *log hunting* manual di berbagai klaster terisolasi. Standarisasi W3C Trace Context menyelesaikan masalah korelasi ini secara deterministik.

---

## SEKSI 05 — APA ITU (WHAT)

### RFC 7807 dan RFC 9457: Problem Details for HTTP APIs
RFC 9457 (yang memformalkan dan menggantikan RFC 7807) mendefinisikan payload JSON terstruktur dengan media type `application/problem+json` untuk menyampaikan rincian kesalahan mesin maupun manusiawi dari respons HTTP. Payload ini memiliki 5 atribut dasar:
* `type` (URI reference): Pengenal unik untuk tipe masalah (default: `about:blank`).
* `title` (string): Ringkasan singkat tingkat tinggi yang tidak berubah antar kejadian masalah yang sama.
* `status` (integer): HTTP status code yang dihasilkan oleh origin server.
* `detail` (string): Penjelasan spesifik mengenai insiden galat pada instansial ini.
* `instance` (URI reference): URI yang mengidentifikasi kejadian masalah spesifik tersebut.

### Automated SDK Generation
Automated SDK Generation adalah proses transformasi Abstract Syntax Tree (AST) spesifikasi OpenAPI (OAS 3.0/3.1) menjadi pustaka klien yang memiliki *type-safe wrappers*, dokumentasi *in-code*, *retry logic*, dan *serialization/deserialization* otomatis tanpa campur tangan penulisan kode manual.

### Contract Testing (Prism vs. Pact)
* **Prism**: Server proxy/mock dinamis HTTP yang memverifikasi lalu lintas *request-response* secara real-time terhadap kepatuhan skema OpenAPI. Digunakan terutama untuk *schema validation* dan simulasi API instan sebelum implementasi aktual tersedia.
* **Pact**: Framework *Consumer-Driven Contract Testing* (CDCT). Konsumen mendefinisikan ekspektasi payload (kontrak) yang disimpan dalam berkas Pact JSON. Berkas kontrak ini kemudian diverifikasi oleh layanan penyedia (*provider*) secara terisolasi tanpa membutuhkan lingkungan runtime konsumen yang aktif.

### W3C Trace Context
Standar spesifikasi global dari W3C yang mendefinisikan sekumpulan HTTP header seragam untuk mempropagasi metadata pelacakan (*tracing*) lintas platform terdistribusi:
* `traceparent`: Header berukuran tetap dengan format `version-trace_id-parent_id-trace_flags` (contoh: `00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01`).
* `tracestate`: Pasangan *key-value* buram (*opaque*) yang menampung informasi khusus vendor/sistem tanpa memodifikasi integritas `traceparent`.

---

## SEKSI 06 — BAGAIMANA BEKERJA (HOW)

### 1. Mekanisme Deserialisasi dan Validasi RFC 9457
Ketika sebuah permintaan melanggar aturan bisnis atau validasi skema:
1. Lapisan validasi/domain memicu sebuah *exception* atau tipe galat yang membawa domain-specific metadata.
2. HTTP interceptor/middleware global menangkap galat tersebut.
3. Middleware memetakan galat domain ke HTTP status yang sesuai, mengomposisi atribut `type`, `title`, `status`, `detail`, dan `instance`, serta menyematkan *field extension* (misalnya: `invalid_params` untuk galat 422).
4. Response dikirim dengan header `Content-Type: application/problem+json`.

### 2. Pipeline Otomatisasi SDK Generator
```
[OpenAPI 3.1 Spec] 
       │
       ▼ (CI Linting: Spectral)
[Validated OAS]
       │
       ├─────────────────────────────────┐
       ▼                                 ▼
[Speakeasy / OpenAPI Generator]   [Prism Mock Engine]
       │                                 │
       ▼                                 ▼
[Generated Client Libraries]       [Schema Sandbox Env]
 (TS, Go, Python, Java)
       │
       ▼ (Automated Semantic Versioning)
[Package Registries] (NPM, PyPI, etc.)
```
1. Spesifikasi OpenAPI dikomit ke repositori pusat (*design-first*).
2. Linter (misal: Spectral) memastikan integritas metadata OAS (keberadaan `operationId`, konsistensi tipe schema, dsb).
3. Engine generator memproses spesifikasi, menghasilkan *type safe client interfaces*, *HTTP client transport layer*, dan *marshalling code*.
4. Pipeline CI mengeksekusi kompilasi kode, unit test pada SDK, pembuatan tagging Git otomatis (*semantic-release*), dan mempublikasikan pustaka ke *registry* publik/privat.

### 3. Alur Consumer-Driven Contract Testing (Pact)
1. **Fase Konsumen**: Test suite unit konsumen menjalankan HTTP mock server bawaan Pact. Konsumen mengirim *request* dan memvalidasi respons mock. Pact merekam seluruh interaksi ke dalam berkas `pact-consumer-provider.json`.
2. **Pact Broker**: Berkas JSON dipublikasikan ke Pact Broker pusat yang bertindak sebagai repositori kontrak dan *source of truth* status integrasi.
3. **Fase Penyedia (Provider)**: Pipeline CI Provider mengunduh kontrak dari Pact Broker, mengeksekusi request nyata ke instansial internal API Provider dengan kondisi *state* tertentu (*provider states*), dan mencocokkan respons aktual dengan ekspektasi kontrak. Provider kemudian mempublikasikan status verifikasi kembali ke Broker.
4. **Can-I-Deploy**: Tool CLI `can-i-deploy` memeriksa apakah versi Provider dan Konsumen yang kompatibel telah diverifikasi sebelum deployment ke produksi diizinkan.

### 4. Ekstraksi dan Injeksi W3C Trace Context
1. Klien atau Gateway menghasilkan `trace_id` (16 bytes, heksadesimal) dan `span_id` awal (8 bytes, heksadesimal).
2. Header `traceparent: 00-{trace_id}-{span_id}-{flags}` disisipkan ke *outgoing request*.
3. Saat mikroservis penerima membaca request:
   * Header `traceparent` diekstraksi ke dalam konteks eksekusi lokal runtime (misal: `context.Context` di Go).
   * Middleware membuat `span_id` baru untuk eksekusi internal sambil mempertahankan `trace_id` yang sama.
4. Setiap panggilan HTTP/gRPC keluar (*egress*) berikutnya menginjeksikan header `traceparent` baru dengan `trace_id` asal dan `span_id` terkini sebagai `parent_id`.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

```
+-------------------------------------------------------------------------------------------------------+
|                                    DISTRIBUTED RUNTIME ARCHITECTURE                                   |
+-------------------------------------------------------------------------------------------------------+

[ Consumer Application ]
         |
         | 1. HTTP Request
         |    Headers:
         |      traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
         |      Accept: application/json, application/problem+json
         v
+-------------------------------------------------------------------------------------------------------+
| API Gateway / Reverse Proxy (e.g., Envoy / Kong)                                                      |
|   - Reads `traceparent` -> Generates child span: 5c394749f7e8a112                                     |
|   - Forwards request with modified parent context                                                     |
+-------------------------------------------------------------------------------------------------------+
         |
         | 2. Egress Request:
         |    Headers:
         |      traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-5c394749f7e8a112-01
         v
+-------------------------------------------------------------------------------------------------------+
| Upstream Order Service (Go / Gin Framework)                                                           |
|                                                                                                       |
|   +------------------------------------+      +---------------------------------------------------+   |
|   | Observability Middleware           |      | Domain Logic Layer                                |   |
|   |  - Extracts W3C Trace Context      | ---> |  - Validates Inventory via Payment Service        |   |
|   |  - Sets Trace Context to Context   |      |  - Throws InsufficientBalanceDomainError          |   |
|   +------------------------------------+      +---------------------------------------------------+   |
|                     |                                                   |                             |
|                     |                                                   v                             |
|                     |                         +---------------------------------------------------+   |
|                     |                         | Error Mapping Middleware (RFC 9457 Engine)        |   |
|                     |                         |  - Resolves Domain Error -> RFC 9457 Struct       |   |
|                     +------------------------>|  - Appends instance URI + tracing metadata        |   |
|                                               +---------------------------------------------------+   |
+-------------------------------------------------------------------------------------------------------+
         |
         | 3. Response: HTTP 403 Forbidden
         |    Content-Type: application/problem+json
         |    traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-5c394749f7e8a112-01
         |
         |    Payload:
         |    {
         |       "type": "https://api.platform.corp/errors/insufficient-credit",
         |       "title": "Insufficient Credit Balance",
         |       "status": 403,
         |       "detail": "Account balance of $12.50 is below required $45.00 for order.",
         |       "instance": "/orders/ord_99214/settlement",
         |       "balance": 12.50,
         |       "currency": "USD"
         |    }
         v
[ Consumer SDK / Client Layer ]
   - Intercepts `application/problem+json`
   - Maps directly to strongly typed SDK Exception: `InsufficientCreditException`
   - Logs correlated TraceID: `4bf92f3577b34da6a3ce929d0e0e4736`
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

### Anti-Pola vs. Standar RFC 9457

#### 1. Non-standard Error Format (Anti-Pola)
```json
// Buruk: Struktur arbitrer, menyulitkan konsumen membuat parsing terpadu
{
  "success": false,
  "err_code": "ERR_NO_FUNDS",
  "msg": "Saldo dompet tidak mencukupi untuk checkout",
  "timestamp": 1718009211
}
```

#### 2. Standar RFC 9457 / RFC 7807 Format
```http
HTTP/1.1 403 Forbidden
Content-Type: application/problem+json
traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01

{
  "type": "https://errors.domain.com/wallets/insufficient-balance",
  "title": "Insufficient Balance",
  "status": 403,
  "detail": "Saldo dompet Anda sebesar Rp 150.000 tidak mencukupi untuk transaksi sebesar Rp 450.000.",
  "instance": "/v1/wallets/wal-88912/transactions",
  "current_balance": 150000,
  "required_amount": 450000
}
```

### Format Anatomi W3C Trace Context
Header `traceparent`: `00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01`
* `00`: Versi protokol saat ini (2 karakter hex).
* `4bf92f3577b34da6a3ce929d0e0e4736`: Trace ID global (32 karakter hex / 16 bytes). Identik sepanjang seluruh jalur eksekusi antarlayanan.
* `00f067aa0ba902b7`: Parent/Span ID (16 karakter hex / 8 bytes). Merepresentasikan titik pemanggilan sebelumnya.
* `01`: Trace Flags (2 karakter hex / 8-bit bitmap). `01` menandakan bit *sampled* aktif (rekam telemetry).

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Contoh berikut mengilustrasikan implementasi produksi di Go yang mencakup middleware RFC 9457, penanganan error validasi bertingkat, serta propagasi konteks W3C Trace Context.

### 1. Definisi Abstraksi Problem Details (Go)

```go
package problem

import (
	"encoding/json"
	"net/http"
)

// RFC9457Problem merepresentasikan struktur standar Problem Details
type RFC9457Problem struct {
	Type       string                 `json:"type"`
	Title      string                 `json:"title"`
	Status     int                    `json:"status"`
	Detail     string                 `json:"detail,omitempty"`
	Instance   string                 `json:"instance,omitempty"`
	Extensions map[string]interface{} `json:"-"`
}

func (p RFC9457Problem) MarshalJSON() ([]byte, error) {
	type Alias RFC9457Problem
	b, err := json.Marshal(Alias(p))
	if err != nil {
		return nil, err
	}

	if len(p.Extensions) == 0 {
		return b, nil
	}

	var m map[string]interface{}
	if err := json.Unmarshal(b, &m); err != nil {
		return nil, err
	}

	for k, v := range p.Extensions {
		m[k] = v
	}

	return json.Marshal(m)
}

func Write(w http.ResponseWriter, p RFC9457Problem) {
	w.Header().Set("Content-Type", "application/problem+json")
	w.WriteHeader(p.Status)
	_ = json.NewEncoder(w).Encode(p)
}
```

### 2. Middleware Observabilitas W3C Tracing & Error Interceptor

```go
package middleware

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"fmt"
	"net/http"
	"strings"

	"yourmodule/problem"
)

type contextKey string
const TraceContextKey contextKey = "w3c_trace_context"

type TraceMetadata struct {
	TraceID string
	SpanID  string
	Sampled bool
}

func W3CTracingMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		rawTrace := r.Header.Get("traceparent")
		var meta TraceMetadata

		if rawTrace != "" {
			parts := strings.Split(rawTrace, "-")
			if len(parts) == 4 && parts[0] == "00" {
				meta.TraceID = parts[1]
				meta.Sampled = (parts[3] == "01")
			}
		}

		// Jika tidak ada traceparent valid, inisialisasi root trace baru
		if meta.TraceID == "" {
			meta.TraceID = generateHex(16) // 128-bit
			meta.Sampled = true
		}

		// Setiap hop membuat Span ID baru (64-bit)
		meta.SpanID = generateHex(8)

		// Set header response agar klien dapat melacak korelasi
		flags := "00"
		if meta.Sampled {
			flags = "01"
		}
		newTraceParent := fmt.Sprintf("00-%s-%s-%s", meta.TraceID, meta.SpanID, flags)
		w.Header().Set("traceparent", newTraceParent)

		ctx := context.WithValue(r.Context(), TraceContextKey, meta)
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

func generateHex(n int) string {
	bytes := make([]byte, n)
	_, _ = rand.Read(bytes)
	return hex.EncodeToString(bytes)
}
```

### 3. Handler Bisnis Menggunakan Validasi & Problem Details

```go
package handler

import (
	"net/http"

	"yourmodule/middleware"
	"yourmodule/problem"
)

type InvalidParam struct {
	Name   string `json:"name"`
	Reason string `json:"reason"`
}

func CreateTransferHandler(w http.ResponseWriter, r *http.Request) {
	traceMeta, _ := r.Context().Value(middleware.TraceContextKey).(middleware.TraceMetadata)

	// Simulasi validasi payload gagal
	validationErrors := []InvalidParam{
		{Name: "destination_account", Reason: "Must be a 10-digit numeric string"},
		{Name: "amount", Reason: "Must be greater than 0"},
	}

	prob := problem.RFC9457Problem{
		Type:     "https://errors.paymentcorp.internal/validation-error",
		Title:    "Payload Validation Failed",
		Status:   http.StatusUnprocessableEntity,
		Detail:   "One or more parameters in the request body failed structural validation.",
		Instance: r.URL.Path,
		Extensions: map[string]interface{}{
			"trace_id":       traceMeta.TraceID,
			"invalid_params": validationErrors,
		},
	}

	problem.Write(w, prob)
}
```

### 4. Consumer-Driven Contract Test Menggunakan Pact (TypeScript)

Berikut merupakan implementasi pengujian kontrak di sisi konsumen (*Consumer Contract Test*) untuk memastikan pemenuhan schema galat RFC 9457:

```typescript
import { PactV3, MatchersV3 } from '@pact-foundation/pact';
import axios from 'axios';

const provider = new PactV3({
  consumer: 'TransferServiceClient',
  provider: 'PaymentGatewayAPI',
});

describe('Payment Gateway - Transfer API Verification', () => {
  it('receives an RFC 9457 complaint error when sending invalid parameters', async () => {
    provider
      .given('Destination account is invalid')
      .uponReceiving('A transfer request with malformed fields')
      .withRequest({
        method: 'POST',
        path: '/v1/transfers',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/problem+json',
        },
        body: {
          destination_account: 'INVALID_ACC',
          amount: -50,
        },
      })
      .willRespondWith({
        status: 422,
        headers: {
          'Content-Type': 'application/problem+json',
        },
        body: {
          type: MatchersV3.regex(
            /^https:\/\/errors\.paymentcorp\.internal\/.*$/,
            'https://errors.paymentcorp.internal/validation-error'
          ),
          title: MatchersV3.string('Payload Validation Failed'),
          status: 422,
          detail: MatchersV3.string('One or more parameters in the request body failed structural validation.'),
          instance: MatchersV3.string('/v1/transfers'),
          invalid_params: MatchersV3.eachLike({
            name: MatchersV3.string('destination_account'),
            reason: MatchersV3.string('Must be a 10-digit numeric string'),
          }),
        },
      });

    await provider.executeTest(async (mockserver) => {
      try {
        await axios.post(
          `${mockserver.url}/v1/transfers`,
          { destination_account: 'INVALID_ACC', amount: -50 },
          { headers: { 'Accept': 'application/problem+json' } }
        );
        throw new Error('Should have failed with 422');
      } catch (error: any) {
        expect(error.response.status).toBe(422);
        expect(error.response.headers['content-type']).toBe('application/problem+json');
        expect(error.response.data.title).toBe('Payload Validation Failed');
        expect(Array.isArray(error.response.data.invalid_params)).toBe(true);
      }
    });
  });
});
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Dimensi | Pendekatan A | Pendekatan B | Analisis Trade-Off |
| :--- | :--- | :--- | :--- |
| **SDK Creation** | **Automated SDK Generation** (e.g., Speakeasy, Fern, OpenAPI Generator) | **Handcrafted Idiomatic SDKs** | Automated unggul mutlak dalam kecepatan rilis, konsistensi spesifikasi, dan *zero-lag* fitur. Handcrafted menawarkan pengalaman DX yang lebih natural per bahasa pemrograman (*idiomaticity*), namun membutuhkan *dedicated engineering team* yang mahal dan rentan terhadap desinkronisasi kontrak. |
| **Contract Testing** | **Consumer-Driven Contracts (Pact)** | **Schema-Driven API Mocking (Prism)** | Pact memverifikasi relasi dependensi secara nyata lintas siklus CI penyedia/konsumen, memastikan *breaking changes* terdeteksi sebelum deployment. Namun, Pact menuntut kurva pembelajaran tim yang tinggi. Prism sangat mudah diadopsi hanya bermodalkan file OpenAPI, tetapi Prism tidak membuktikan bahwa konsumen benar-benar mengonsumsi field tersebut. |
| **Error Detail** | **Rich RFC 9457 Problem Details** | **Minimal Error Envelope** (`{"error": "string"}`) | Rich RFC 9457 mempercepat debugging secara signifikan dan memfasilitasi penanganan error terprogram di sisi klien. Namun, jika tidak diaudit secara ketat, RFC 9457 berisiko mengekspos informasi sensitif arsitektur internal (*security leak*) melalui atribut `detail` atau *custom extension*. |
| **Tracing Context** | **W3C Trace Context Standard** | **Custom Trace Headers** (e.g., `X-Correlation-ID`) | W3C didukung secara native oleh APM modern (OpenTelemetry, Datadog, Jaeger, Cloud Logging) dan menjamin interoperabilitas lintas vendor. Format lama seperti `X-Correlation-ID` tidak memiliki standardisasi `span` hierarki maupun sampling flags (`trace-flags`). |

---

## SEKSI 11 — BEST PRACTICES

1. **Gunakan URI Absolut yang Dapat Di-resolve pada Atribut `type`**: Proyeksikan nilai atribut `type` pada URL dokumentasi operasional internal atau publik (misal: `https://api.domain.com/problems/invalid-idempotency-key`). Halaman HTML/Markdown pada endpoint tersebut harus menjelaskan penyebab galat serta langkah mitigasinya.
2. **Pisahkan Detail Internal dari Domain Detail**: Jangan pernah memasukkan *stack traces*, raw SQL query, nama tabel basis data, atau alamat IP internal ke dalam atribut `detail` atau extensions RFC 9457. Gunakan `trace_id` sebagai jembatan korelatif ke sistem log privat Anda.
3. **Posisikan OpenAPI Specification sebagai Artefak Kompilasi**: Jalankan linter OpenAPI (Spectral) dengan ruleset ketat pada pipeline CI:
   * Wajib memiliki `operationId` camelCase unik pada setiap operasi endpoint.
   * Setiap skema respons error wajib me-referensi komponen model RFC 9457.
4. **Otomatisasi Release SDK via Semantic Release**: Tautkan pipeline *git tag* spesifikasi OpenAPI dengan perilisan SDK target. Perubahan skema minor menaikkan versi minor pustaka; perubahan kompatibilitas kontraktual (*breaking change*) memicu penolakan build atau bump versi major otomatis.
5. **Gunakan OpenTelemetry Native Context Propagation**: Daripada mem-parsing string `traceparent` secara manual pada kode produksi aplikasi, gunakan SDK resmi OpenTelemetry (`propagation.TraceContext{}`).

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

1. **Mengembalikan `Content-Type: application/json` untuk RFC 9457**: Mengabaikan media type resmi `application/problem+json`. Klien berbasis HTTP modern menggunakan header respons `Content-Type` untuk menentukan parser yang tepat (*polymorphic deserialization*).
2. **Menyalahgunakan Atribut `title`**: Mengubah nilai `title` secara dinamis pada setiap instans error (misal: `"title": "User with ID 551 not found"`). Atribut `title` harus bersifat statis per kode/tipe galat (misal: `"title": "Resource Not Found"`). Variasi spesifik harus diletakkan di dalam atribut `detail`.
3. **Membuat Operasi Bersifat Flaky di SDK Generator**: Tidak menetapkan `operationId` yang deterministik dalam OpenAPI file. Akibatnya, OpenAPI Generator menghasilkan nama fungsi SDK acak berbasis path URL yang dapat berubah sewaktu-waktu dan memecah kompatibilitas kode konsumen (*breaking changes*).
4. **Memverifikasi Kontrak Pact Terhadap Data Produksi yang Nyata**: Menjalankan provider verification terhadap database dinamis yang datanya berubah-ubah. Hal ini merusak determinisme tes. Verifikasi harus menggunakan *Provider State Handlers* untuk menyuntikkan *mock data fixtures* sebelum pengujian dieksekusi.
5. **Memutus Propagasi `traceparent` pada Async Boundary**: Ketika mikroservis meneruskan event ke antrean pesan (e.g., Apache Kafka atau RabbitMQ), pengembang sering lupa menyematkan header `traceparent` ke dalam message headers/metadata, memutus mata rantai tracing secara permanen.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1 (Beginner): Standardisasi Schema RFC 9457
* **Tugas**: Tuliskan representasi JSON skema RFC 9457 untuk skenario kegagalan limit kuota API (*Rate Limiting* / HTTP 429).
* **Kebutuhan**:
  * Gunakan tipe media `application/problem+json`.
  * Tambahkan extension field `retry_after_seconds` bernilai integer `30`.
  * Sertakan extension field `quota_limit` bernilai `1000` dan `quota_remaining` bernilai `0`.

### Latihan 2 (Intermediate): Local API Mocking & Validation Menggunakan Prism
* **Tugas**: Setup validasi kontrak sisi server secara instan menggunakan Prism CLI.
* **Instruksi**:
  1. Buat berkas `api-spec.yaml` minimal (OpenAPI 3.1) yang memuat satu endpoint: `POST /v1/invoices`.
  2. Definisikan bahwa request body membutuhkan field wajib: `customer_id` (UUID format) dan `total_amount` (number, minimum 0.01).
  3. Jalankan mock server: `prism mock -p 4010 api-spec.yaml`.
  4. Lakukan request `curl` dengan payload yang salah (misal: `customer_id` berupa string non-UUID) dan amati bagaimana Prism memvalidasi request Anda dan merespons dengan galat skema.

### Latihan 3 (Advanced): Membangun W3C Trace Context Propagator Roundtrip
* **Tugas**: Buatlah sebuah program/skrip (menggunakan bahasa Go, Node.js, atau Python) yang:
  1. Menerima request HTTP masuk dengan header `traceparent` tertentu.
  2. Mengekstrak `trace_id` yang sama.
  3. Menghasilkan `span_id` baru (anak).
  4. Melakukan *outgoing HTTP call* ke endpoint lain dengan meneruskan header `traceparent` yang telah diperbarui.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1. **Apa perbedaan status spesifikasi antara RFC 7807 dan RFC 9457?**
   * A. RFC 9457 menggunakan XML, sedangkan RFC 7807 menggunakan JSON.
   * B. RFC 9457 adalah spesifikasi mutakhir yang secara resmi mengabstraksi dan menggantikan (*obsoletes*) RFC 7807 dengan penyempurnaan terminologi dan kejelasan extensibility.
   * C. RFC 7807 khusus untuk gRPC, RFC 9457 khusus untuk REST.
   * D. Tidak ada perbedaan, penomoran hanya berdasarkan wilayah implementasi.

2. **Perhatikan string berikut: `00-a807d3b9e4a3b1238912ef01a88b1928-1b2c3d4e5f6a7b8c-00`. Manakah bagian yang merepresentasikan `span_id` (parent ID)?**
   * A. `00`
   * B. `a807d3b9e4a3b1238912ef01a88b1928`
   * C. `1b2c3d4e5f6a7b8c`
   * D. `00` (terakhir)

3. **Mengapa penulisan `operationId` yang statis dan unik sangat penting pada spesifikasi OpenAPI saat menggunakan SDK Generator?**
   * A. Menjadi identifier nama fungsi/metode yang dihasilkan pada kode target SDK.
   * B. Diperlukan untuk alokasi memori internal di gateway HTTP.
   * C. Sebagai pengenal tracing W3C terdistribusi.
   * D. Menentukan urutan routing eksekusi database.

4. **Bagaimana Pact memverifikasi kompatibilitas antara Konsumen dan Penyedia tanpa melakukan pengujian end-to-end langsung di live environment?**
   * A. Menjalankan AI untuk memprediksi response backend.
   * B. Konsumen merekam ekspektasi interaksi ke dalam berkas kontrak terisolasi, yang kemudian diuji ulang secara independen langsung ke endpoint Provider via mock state runners.
   * C. Pact mengkloning database production ke local machine.
   * D. Menggunakan Webhook untuk memonitor log staging.

5. **Apa risiko keamanan utama jika RFC 9457 tidak disaring oleh Error Sanitization Layer sebelum dikirim ke publik?**
   * A. Header W3C trace context akan terhapus otomatis.
   * B. Bocornya detail teknis internal sistem (seperti exception message, tabel database, query context) melalui field `detail` atau custom extensions.
   * C. Pengurangan bandwidth server secara ekstrem.
   * D. Menyebabkan status code HTTP otomatis berubah menjadi 200 OK.

---

### Jawaban Kuis & Evaluasi
* **1: B** — RFC 9457 adalah suksesor langsung yang memformalkan dan menyempurnakan RFC 7807.
* **2: C** — Format W3C `traceparent` adalah `version-trace_id-parent_id(span_id)-flags`. Posisi segmen ketiga adalah `1b2c3d4e5f6a7b8c`.
* **3: A** — SDK Generator memetakan `operationId` secara langsung ke nama metode fungsi API klien (misal: `operationId: createTransfer` -> `client.transfers.createTransfer()`).
* **4: B** — Inti Consumer-Driven Contract testing adalah isolasi waktu dan tempat: eksekusi kontrak konsumen disimpan ke file JSON Pact, lalu divalidasi ke provider secara terpisah.
* **5: B** — Exception internal yang dilewatkan mentah-mentah ke atribut RFC 9457 membuka celah information leakage bagi penyerang sistem.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **IETF RFC 9457**: *Problem Details for HTTP APIs* (<https://www.rfc-editor.org/rfc/rfc9457.html>).
* **W3C Recommendation**: *Trace Context - Level 1* (<https://www.w3.org/TR/trace-context/>).
* **OpenAPI Initiative**: *OpenAPI Specification 3.1.0* (<https://spec.openapis.org/oas/v3.1.0>).
* **Pact Foundation Documentation**: *Introduction to Consumer-Driven Contracts* (<https://docs.pact.io/>).
* **Stoplight Prism Documentation**: *HTTP Mocking and Contract Linting Engine* (<https://meta.stoplight.io/docs/prism>).
* **Speakeasy / OpenAPI Generator Core Guides**: *Building resilient developer SDKs* (<https://speakeasyapi.dev/docs/>).

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1. **Standardisasi Error RFC 9457**: Menyediakan format deklaratif (`type`, `title`, `status`, `detail`, `instance`) yang konsisten, membebaskan konsumen dari keharusan merancang parser galat yang rapuh, sekaligus mengabstraksikan failure domain dengan rapi.
2. **SDK Automation**: Menghilangkan overhead pemeliharaan library manual. Dengan menjaga spesifikasi OpenAPI 3.1 sebagai satu-satunya *source of truth*, SDK multi-bahasa dapat dikompilasi, diuji, dan dirilis secara otomatis pada setiap iterasi pipeline CI/CD.
3. **Shift-Left Testing via Contracts**: Menggantikan integrasi E2E yang lambat dan rapuh dengan pengujian kontrak terfokus. Prism bertindak sebagai penjaga gerbang validasi kepatuhan skema (*schema gate*), sementara Pact menjamin kecocokan ekspektasi antara penyedia dan konsumen layanan.
4. **W3C Distributed Tracing**: Menghubungkan seluruh interaksi antar-layanan ke dalam satu pohon dependensi terpadu melalui propagasi header `traceparent` dan `tracestate`. Ini memungkinkan pengembang dan operator sistem melacak siklus hidup sebuah transaksi dari SDK klien hingga baris kode terdalam di downstream microservices.

---

## SEKSI 17 — GLOSARIUM

* **AST (Abstract Syntax Tree)**: Representasi struktur pohon dari kode sumber atau spesifikasi (seperti OpenAPI) yang digunakan oleh generator untuk menghasilkan kode program.
* **Consumer-Driven Contract Testing (CDCT)**: Metodologi pengujian integrasi di mana konsumen API menuliskan pengujian ekspektasi terhadap respons API penyedia, dan penyedia harus memverifikasi bahwa implementasi mereka memenuhi ekspektasi tersebut.
* **Idempotency**: Karakteristik sebuah request HTTP yang jika dieksekusi berulang kali dengan parameter yang sama akan menghasilkan status akhir state sistem yang identik tanpa efek samping tambahan.
* **Mock Server**: Server tiruan yang merespons permintaan HTTP dengan data dummy berdasarkan definisi kontrak atau skema tanpa mengeksekusi logika bisnis nyata.
* **OperationId**: String pengenal unik dalam spesifikasi OpenAPI yang mengidentifikasi operasi spesifik pada suatu path dan metode HTTP.
* **Provider States**: Keadaan/kondisi prasyarat data pada server API penyedia yang disiapkan sebelum sebuah pengujian kontrak Pact dijalankan.
* **Span ID**: Pengenal heksadesimal berukuran 8-byte yang menandai satu unit segmen kerja atau eksekusi tunggal dalam sebuah distributed trace.
* **Trace ID**: Pengenal heksadesimal berukuran 16-byte yang unik secara global, merepresentasikan keseluruhan transaksi ujung-ke-ujung melintasi berbagai sistem terdistribusi.
* **traceparent**: Standar header HTTP W3C yang memuat versi tracing, trace ID, parent/span ID, serta opsi tracing flags.
* **tracestate**: Header HTTP W3C pelengkap untuk membawa metadata spesifik sistem atau platform pemantau tanpa merusak struktur header `traceparent`.

---

## SEKSI 18 — CATATAN INSTRUKTUR

### Poin Penekanan Materi:
* **Fokus pada DX**: Ingatkan peserta didik bahwa API bukan sekadar endpoint fungsional, melainkan produk software yang ditujukan bagi pengembang lain (konsumen internal maupun eksternal). Desain respons galat yang buruk adalah sumber gesekan utama dalam ekosistem engineering.
* **Demistifikasi W3C Tracing**: Banyak pengembang menganggap tracing adalah ranah eksklusif DevOps/SRE. Tunjukkan bahwa arsitek API bertanggung jawab merancang middleware propagasi konteks agar trace correlation tidak terputus di lapisan aplikasi.

### Jebakan Umum Peserta Saat Lab:
* Peserta sering salah paham dengan mengira bahwa Pact menggantikan Unit Test. Jelaskan bahwa Pact **bukan** pengganti pengujian fungsionalitas logika bisnis, melainkan murni pengujian bentuk *interface* (kontrak) komunikasi data.
* Saat mengimplementasikan RFC 9457, peserta pemula sering memasukkan objek `err.Error()` mentah ke atribut `detail`. Tekankan bahaya kebocoran informasi kredensial, struktur database, atau stack trace.

---

## SEKSI 19 — CHANGELOG & VERSI

* **v1.0.0 (Juli 2024)**:
  * Inisialisasi rilis modul kurikulum teknis standar GEMINI.md.
  * Formalisasi materi transisi RFC 7807 ke RFC 9457 Problem Details.
  * Penyusunan contoh kode implementasi Go W3C trace extractor/injector.
  * Integrasi contoh pengujian Consumer-Driven Contract Testing via Pact TypeScript V3.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya**: `ARCH-API-08-03`: Webhooks, Idempotency Keys, Transactional Outbox Pattern, & Event-Driven APIs
* **Modul Berikutnya**: `ARCH-API-09-02`: API Gateway Patterns, Rate Limiting Architectures, & Distributed Token Bucket Implementation
* **Repositori Utama Kurikulum**: `api-design-architecture-index`