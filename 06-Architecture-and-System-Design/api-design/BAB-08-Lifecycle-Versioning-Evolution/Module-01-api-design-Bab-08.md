## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** 06-Architecture-and-System-Design
*   **Mata Kuliah:** API Design & Evolution
*   **Bab 08:** Lifecycle, Versioning, & Evolution Strategy
*   **Modul 01:** Strategi Versioning (URI, Header, Media Type), Deprecation & Sunset Headers, Automated Breaking Changes Detection di CI/CD
*   **Tingkat Kesulitan:** Advanced (Tingkat Mahir)
*   **Prasyarat:** Pemahaman mendalam mengenai protokol HTTP/1.1 & HTTP/2, RFC 7231 (HTTP Semantics), OpenAPI Specification (OAS) 3.0/3.1, arsitektur REST, dan dasar-dasar CI/CD pipeline (GitHub Actions/GitLab CI).
*   **Estimasi Waktu Belajar:** 180 Menit (Teori: 60 Menit, Bedah Kode & Setup CI/CD: 75 Menit, Latihan: 45 Menit)

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1.  **Menganalisis dan Mengkomparasi** empat strategi utama *API Versioning* (URI Path, Query Parameter, Custom Header, dan Media Type/Content Negotiation) berdasarkan implikasinya terhadap *HTTP caching*, *Developer Experience* (DX), dan kompleksitas perutean pada *API Gateway*.
2.  **Merancang dan Mengimplementasikan** mekanisme *Deprecation* dan *Sunsetting* yang patuh terhadap standar IETF RFC 8594 (`Sunset`) dan IETF Draft (`Deprecation`), lengkap dengan *link relations* ke dokumentasi migrasi.
3.  **Mengklasifikasikan** perubahan skema API menjadi kategori *breaking change* vs *non-breaking change* berdasarkan *Robustness Principle* (Postel’s Law).
4.  **Membangun Pipeline Otomatis** pada CI/CD untuk mendeteksi *backward-incompatible changes* secara statis menggunakan *schema diff engine* sebelum kode di-merge ke *branch* utama.
5.  **Merumuskan Kebijakan Evolusi API** (*Evolution Policy*) multi-tahap yang meminimalkan *downtime* integrasi bagi sistem klien pihak ketiga (*third-party consumers*).

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                       API EVOLUTION STRATEGY
                                 │
         ┌───────────────────────┴───────────────────────┐
         ▼                                               ▼
  RUNTIME STRATEGY                               CICD / LIFECYCLE GATE
         │                                               │
 ┌───────┴───────┐                               ┌───────┴───────┐
 ▼               ▼                               ▼               ▼
Versioning     Deprecation & Sunset           Contract       Compatibility
Mechanisms     (RFC 8594 / Draft)             Diffing         Verification
 │               │                               │               │
 ├─ URI Path     ├─ Header: Deprecation          ├─ OpenAPI 3.x  ├─ Breaking:
 ├─ Query Param  ├─ Header: Sunset (HTTP-date)   ├─ Protobuf        - Field removed
 ├─ Header       └─ Header: Link (rel=sunset)    └─ GraphQL         - Type changed
 └─ Media Type                                                      - New required
    (Accept)                                                     └─ Non-Breaking:
                                                                    - Field added
                                                                    - Validations
                                                                      relaxed
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Dalam arsitektur terdistribusi modern, sebuah API adalah **kontrak publik yang mengikat** (*immutable public contract*). Perubahan internal pada basis data, domain model, maupun performa sistem tidak boleh serta-merta merusak (*break*) integrasi sistem klien yang mengonsumsinya. 

Kesalahan dalam mengelola evolusi API menimbulkan dampak fatal:
1. **Kegagalan Runtime Klien**: Ketika sebuah kolom (*field*) diubah tipe datanya dari `integer` ke `string` atau dihapus tanpa pemberitahuan, ribuan aplikasi klien (baik aplikasi mobile yang lambat diperbarui oleh pengguna maupun sistem perbankan pihak ketiga) akan mengalami *crash* mendadak akibat *deserialization error*.
2. **Kekacauan Cache (Cache Poisoning & Invalidation Breakdown)**: Kesalahan memilih strategi versioning dapat merusak kemampuan HTTP Caching (seperti CDN Cloudflare, Akamai, atau Varnish). Penggunaan *header-based versioning* tanpa header `Vary: Accept` yang tepat dapat menyebabkan pengguna V2 menerima respons ter-cache milik V1.
3. **Akumulasi Technical Debt & Zombie APIs**: Ketiadaan strategi *Deprecation* dan *Sunset* yang formal memaksa tim *engineering* mempertahankan puluhan versi kode usang di dalam *monolith* atau *microservice*, memicu pemborosan sumber daya komputasi dan kompleksitas pemeliharaan yang ekstrem.

Evolusi API bukan sekadar masalah penamaan endpoint; ini adalah **disiplin rekayasa sistem** yang menyeimbangkan antara kecepatan inovasi internal (*feature velocity*) dan stabilitas eksternal (*system stability*).

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Strategi API Versioning

API Versioning adalah metodologi yang digunakan untuk mengekspos variasi perilaku atau kontrak data API yang berbeda secara simultan kepada klien.

*   **URI Path Versioning**: Menyematkan versi secara eksplisit di dalam path URL.
    *   *Contoh*: `GET /api/v1/orders/102`
*   **Query Parameter Versioning**: Menyertakan parameter query untuk mendefinisikan versi kontrak.
    *   *Contoh*: `GET /api/orders/102?version=1`
*   **Custom Request Header Versioning**: Mengirimkan versi melalui header HTTP kustom.
    *   *Contoh*: `X-API-Version: 2024-05-01`
*   **Media Type Versioning (Content Negotiation)**: Meminta versi tertentu melalui header standar `Accept` menggunakan *custom vendor MIME type*.
    *   *Contoh*: `Accept: application/vnd.company.orders.v2+json`

### 2. Standar IETF Deprecation & Sunset

Untuk mematikan endpoint tanpa merusak klien secara sepihak, IETF menetapkan dua header standar:

*   **RFC 8594 (`Sunset`)**: Mengembalikan tanggal dan waktu spesifik (dalam format RFC 1123 / IMF-fixdate) kapan sumber daya (*resource*) atau endpoint tersebut akan dimatikan secara permanen dan tidak lagi responsif.
    *   *Sintaks*: `Sunset: Wed, 11 Nov 2026 00:00:00 GMT`
*   **IETF Draft (`Deprecation`)**: Menandakan bahwa sumber daya atau versi API yang diakses saat ini telah usang dan penggunaannya sangat tidak disarankan. Nilai header dapat berupa *boolean* (`@true`) atau tanggal penandaan deprecation.
    *   *Sintaks*: `Deprecation: @true` atau `Deprecation: Sun, 10 Nov 2024 00:00:00 GMT`
*   **RFC 8288 (`Link`)**: Menyediakan tautan navigasi kontekstual yang mengarahkan pengembang ke dokumentasi migrasi atau kebijakan sunset.
    *   *Sintaks*: `Link: <https://api.example.com/docs/migration/v1-to-v2>; rel="deprecation"; type="text/html"`

### 3. Breaking vs Non-Breaking Changes

*   **Non-Breaking Changes (Kompatibel ke Belakang)**:
    *   Menambahkan endpoint/path baru.
    *   Menambahkan field/properti opsional baru pada *request payload*.
    *   Menambahkan field baru pada *response payload*.
    *   Menambahkan header respons baru.
*   **Breaking Changes (Merusak Kompatibilitas)**:
    *   Menghapus atau mengganti nama (*rename*) field pada respons atau request.
    *   Mengubah tipe data field (misal: array of strings menjadi array of objects).
    *   Mengubah status HTTP Code (misal: dari `200 OK` dengan error body menjadi `400 Bad Request`).
    *   Menambahkan validasi baru yang mewajibkan (*required*) field yang sebelumnya opsional pada request.
    *   Mengubah struktur URL atau parameter wajib query.

---

## SEKSI 06 — BAGAIMANA BEKERJA (HOW)

### 1. Mekanisme Evaluasi Negosiasi Konten & Caching Proxy

Ketika menggunakan *Header-based* atau *Media Type Versioning*, perantara jaringan (*reverse proxy*, CDN) harus diinstruksikan untuk tidak menyajikan cache dari versi yang salah. Ini dicapai via response header `Vary`.

```
[Client] ──> Accept: application/vnd.app.v2+json ──> [Cloudflare CDN] 
                                                              │
                                                     Cache Miss (v2)
                                                              │
                                                              ▼
                                                        [API Gateway]
                                                              │
[Client] <── HTTP 200 (Vary: Accept) <────────────────────────┤
```

Jika server lupa menyertakan `Vary: Accept`, maka permintaan berikutnya dari klien lain yang meminta `Accept: application/vnd.app.v1+json` berisiko menerima *cached body* milik V2 dari CDN, yang langsung memicu insiden fatal di sisi klien.

### 2. Lifecycle States of an API Endpoint

Evolusi API yang matang melewati empat status siklus hidup terkelola:

1.  **Active / GA (General Availability)**: Versi utama yang didukung penuh, menerima perbaikan bug dan peningkatan performa.
2.  **Deprecated**: Endpoint masih berfungsi normal, namun header `Deprecation` dan `Link` mulai diinjeksikan pada respons HTTP. Peringatan log mulai dikirimkan ke dasbor telemetri.
3.  **Sunset Period**: Header `Sunset` diaktifkan bersama tanggal terminasi pasti. Klien menerima notifikasi terjadwal, dan metrik penggunaan dipantau secara ketat.
4.  **Retired / Tombstoned**: Endpoint dimatikan total. Permintaan mengembalikan status `HTTP 410 Gone` atau `HTTP 404 Not Found` disertai payload terstruktur RFC 7807 (Problem Details).

### 3. Automated Breaking Change Gate di CI/CD

Pencegahan *breaking change* dilakukan sebelum kode masuk ke *trunk branch* (`main`/`master`):
1. Pengembang mengubah skema OpenAPI (`openapi.yaml`) atau anotasi kode di *feature branch*.
2. Git Hook / CI Runner mengeksekusi diffing engine (`oasdiff`, `openapi-diff`, atau `buf` untuk gRPC).
3. Tool membandingkan `openapi.yaml` cabang fitur terhadap versi canonical di cabang `main`.
4. Jika ditemukan pelanggaran (misalnya: `type` field `amount` berubah dari `number` ke `string`), CI pipeline gagal (*exit code 1*), memblokir *Pull Request*.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### Diagram 1: Flowchart Perutean API Gateway & Negosiasi Versi

```
                       Request Masuk
                             │
                             ▼
               Apakah Versi ada di URI Path?
               (/v1/resource vs /v2/resource)
                        /         \
                     YA            TIDAK
                     /               \
                    ▼                 ▼
          Pilih Route Target    Apakah Versi ada di Header?
          Berdasarkan Path      (X-API-Version atau Accept Media)
                                      /         \
                                   YA            TIDAK
                                   /               \
                                  ▼                 ▼
                        Evaluasi Versi       Gunakan Default Versi
                        & Inject Header      (LTS / Latest Stable)
                        Vary: Accept               │
                                  │                │
                                  ▼                ▼
                         ┌───────────────────────────┐
                         │   Forward ke Downstream   │
                         │    Microservice Worker    │
                         └───────────────────────────┘
```

### Diagram 2: State Machine Siklus Hidup API (RFC 8594 Workflow)

```
  ┌────────────┐
  │   ACTIVE   │ ◄─── Penerapan Baru (v2.0.0)
  └─────┬──────┘
        │
        │ Pengumuman Rilis Mayor Baru (v3.0.0)
        ▼
  ┌────────────┐
  │ DEPRECATED │ ─── Respons mengembalikan:
  └─────┬──────┘     - Deprecation: @true
        │            - Link: <docs>; rel="deprecation"
        │
        │ Memasuki Tenggat Waktu Penghentian (Cut-off Defined)
        ▼
  ┌────────────┐
  │   SUNSET   │ ─── Respons mengembalikan:
  └─────┬──────┘     - Deprecation: @true
        │            - Sunset: Wed, 11 Nov 2026 00:00:00 GMT
        │            - Link: <migration>; rel="sunset"
        │
        │ Tanggal Sunset Terlampaui (Dead Deadline)
        ▼
  ┌────────────┐
  │  RETIRED   │ ─── Respons Permanen:
  └────────────┘     - HTTP 410 Gone
                     - Payload: RFC 7807 Problem Details
```

### Diagram 3: CI/CD Automated Breaking Change Gate Pipeline

```
[ Developer ]
      │
      │ git push origin feat/modify-payload
      ▼
[ GitHub Actions / GitLab CI ]
      │
      ├─► Step 1: Checkout Branch Fitur
      ├─► Step 2: Fetch Target Branch (origin/main)
      ├─► Step 3: Ekstraksi Canonical 'openapi.yaml' dari origin/main
      ├─► Step 4: Jalankan Schema Diff Engine (misal: oasdiff / openapi-diff)
      │           ┌───────────────────────────────────────────────┐
      │           │ oasdiff breaking base.yaml feat.yaml          │
      │           └───────────────────────┬───────────────────────┘
      │                                   │
      ▼                                   ▼
[ Breaking Change Ditemukan? ] ──── YA ──► [ FAIL CI RUN ]
      │                                    Block Merge!
      │ TIDAK                              Post Review Comment ke PR
      ▼
[ PASS CI RUN ]
Izinkan Merge ke Main
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah implementasi *minimalist* dalam Bahasa Go yang mendemonstrasikan penanganan header RFC 8594 (`Sunset`), `Deprecation`, dan `Link` pada rute yang sudah usang, serta implementasi `Vary: Accept` pada rute yang menggunakan negosiasi konten.

```go
package main

import (
	"encoding/json"
	"net/http"
	"time"
)

type UserResponseV1 struct {
	FullName string `json:"name"`
}

type UserResponseV2 struct {
	FirstName string `json:"first_name"`
	LastName  string `json:"last_name"`
}

func legacyUserHandler(w http.ResponseWriter, r *http.Request) {
	// RFC 8594 & IETF Deprecation Headers
	sunsetDate := time.Date(2026, time.December, 31, 23, 59, 59, 0, time.UTC)
	
	w.Header().Set("Deprecation", "@true")
	w.Header().Set("Sunset", sunsetDate.Format(http.TimeFormat))
	w.Header().Set("Link", `<https://api.domain.com/docs/v1-sunset>; rel="sunset"; type="text/html"`)
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)

	json.NewEncoder(w).Encode(UserResponseV1{
		FullName: "Budi Pratama",
	})
}

func contentNegotiatedUserHandler(w http.ResponseWriter, r *http.Request) {
	// Wajib menyertakan Vary: Accept untuk HTTP Caching
	w.Header().Set("Vary", "Accept")

	acceptHeader := r.Header.Get("Accept")
	switch acceptHeader {
	case "application/vnd.company.app.v2+json":
		w.Header().Set("Content-Type", "application/vnd.company.app.v2+json")
		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(UserResponseV2{
			FirstName: "Budi",
			LastName:  "Pratama",
		})
	default: // Fallback ke V1 jika diminta v1 atau wildcard
		w.Header().Set("Content-Type", "application/vnd.company.app.v1+json")
		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(UserResponseV1{
			FullName: "Budi Pratama",
		})
	}
}

func main() {
	mux := http.NewServeMux()
	mux.HandleFunc("/v1/users", legacyUserHandler)
	mux.HandleFunc("/users", contentNegotiatedUserHandler)

	http.ListenAndServe(":8080", mux)
}
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Kasus nyata: Implementasi arsitektur produksi menggunakan Node.js/TypeScript dengan framework Fastify. Mencakup *lifecycle middleware* untuk membaca konfigurasi *sunset/deprecation* serta konfigurasi GitHub Actions CI/CD Pipeline lengkap untuk mendeteksi *breaking changes* menggunakan `oasdiff`.

### 1. Kode Server: Lifecycle Middleware (Fastify + TypeScript)

```typescript
// src/plugins/lifecycle.ts
import { FastifyPluginAsync, FastifyReply, FastifyRequest } from 'fastify';
import fp from 'fastify-plugin';

export interface RouteEvolutionConfig {
  deprecated?: boolean;
  sunsetDate?: string; // Format ISO-8601: "2026-12-31T23:59:59Z"
  migrationDocUrl?: string;
}

declare module 'fastify' {
  interface FastifyContextConfig {
    evolution?: RouteEvolutionConfig;
  }
}

const lifecyclePluginAsync: FastifyPluginAsync = async (fastify) => {
  fastify.addHook('onSend', async (request: FastifyRequest, reply: FastifyReply, payload) => {
    const config = reply.context.config.evolution;

    if (!config) {
      return payload;
    }

    if (config.deprecated) {
      reply.header('Deprecation', '@true');
    }

    if (config.sunsetDate) {
      const date = new Date(config.sunsetDate);
      // Validasi apakah waktu sekarang sudah melewati tanggal sunset
      if (Date.now() >= date.getTime()) {
        reply.status(410); // Gone
        reply.header('Content-Type', 'application/problem+json');
        return JSON.stringify({
          type: 'https://api.domain.com/errors/gone',
          title: 'Resource Permanent Gone',
          status: 410,
          detail: `Endpoint ini telah dimatikan secara permanen sejak ${date.toUTCString()}.`,
        });
      }
      reply.header('Sunset', date.toUTCString());
    }

    if (config.migrationDocUrl) {
      const rel = config.sunsetDate ? 'sunset' : 'deprecation';
      reply.header('Link', `<${config.migrationDocUrl}>; rel="${rel}"; type="text/html"`);
    }

    return payload;
  });
};

export const lifecyclePlugin = fp(lifecyclePluginAsync);
```

```typescript
// src/app.ts
import Fastify from 'fastify';
import { lifecyclePlugin } from './plugins/lifecycle';

const server = Fastify({ logger: true });

server.register(lifecyclePlugin);

// Route yang berstatus Deprecated & Memiliki Sunset Schedule
server.get(
  '/api/v1/wallets/:id',
  {
    config: {
      evolution: {
        deprecated: true,
        sunsetDate: '2026-06-01T00:00:00Z',
        migrationDocUrl: 'https://docs.domain.com/api/migrations/wallets-v2',
      },
    },
  },
  async (request, reply) => {
    return {
      wallet_id: (request.params as any).id,
      balance: 500000,
      currency: 'IDR',
    };
  }
);

// Route Baru (V2)
server.get('/api/v2/wallets/:id', async (request, reply) => {
  return {
    id: (request.params as any).id,
    balances: [
      { currency: 'IDR', amount: 500000, precision: 2 }
    ],
    status: 'ACTIVE'
  };
});

server.listen({ port: 3000, host: '0.0.0.0' }, (err) => {
  if (err) {
    server.log.error(err);
    process.exit(1);
  }
});
```

### 2. CI/CD Pipeline: GitHub Actions untuk Automated Breaking Change Detection

Gunakan `oasdiff` untuk memeriksa apakah Pull Request mengubah skema OpenAPI secara destruktif tanpa perpindahan versi rute.

Simpan file berikut di `.github/workflows/openapi-diff.yml`:

```yaml
name: OpenAPI Contract Safety Gate

on:
  pull_request:
    branches: [ "main" ]
    paths:
      - "openapi/**"
      - "spec/openapi.yaml"

jobs:
  breaking-change-check:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Feature Branch
        uses: actions/checkout@v4
        with:
          path: current

      - name: Checkout Base (Canonical) Branch
        uses: actions/checkout@v4
        with:
          ref: main
          path: base

      - name: Install OASDiff Engine
        run: |
          curl -fsSL https://raw.githubusercontent.com/tufin/oasdiff/main/install.sh | sh
          sudo mv ./bin/oasdiff /usr/local/bin/

      - name: Verify Compatibility (Diff Engine)
        id: diff-step
        run: |
          echo "Comparing spec/openapi.yaml against main branch..."
          oasdiff breaking base/spec/openapi.yaml current/spec/openapi.yaml --format json > breaking-changes.json || true
          
          # Catat jumlah breaking changes
          COUNT=$(jq '. | length' breaking-changes.json)
          echo "BREAKING_COUNT=$COUNT" >> $GITHUB_ENV
          
          if [ "$COUNT" -gt 0 ]; then
            echo "::error::Ditemukan $COUNT breaking change(s) yang tidak terproteksi versi baru!"
            cat breaking-changes.json | jq .
            exit 1
          else
            echo "Tidak ada breaking change yang terdeteksi. Skema sepenuhnya backward-compatible."
          fi

      - name: Post Failure Comment to Pull Request
        if: failure() && steps.diff-step.outcome == 'failure'
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const diffData = fs.readFileSync('breaking-changes.json', 'utf8');
            const body = `### ⚠️ API Breaking Changes Detected!\n\nPipeline CI menolak perubahan ini karena melanggar backward compatibility pada kontrak publik tanpa peningkatan versi.\n\n\`\`\`json\n${diffData}\n\`\`\`\n\n**Tindakan yang Diperlukan:**\n1. Rollback perubahan destruktif ini, atau\n2. Buat rute baru (misal: \`/v2/...\`) dan biarkan field pada rute lama tetap ada.`;
            
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: body
            });
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

Berikut adalah matriks komparasi empat strategi *API Versioning*:

| Parameter Evaluasi | URI Path Versioning (`/v1/orders`) | Custom Header (`X-API-Version: 2`) | Content Negotiation (`Accept: application/vnd...`) | Query Parameter (`?v=2`) |
| :--- | :--- | :--- | :--- | :--- |
| **HTTP Caching Friendly** | **Sangat Tinggi**. URI adalah *cache key* standar bagi seluruh CDN/Proxy. | **Rendah - Sedang**. Bergantung penuh pada ketepatan header `Vary`. | **Rendah - Sedang**. Mewajibkan `Vary: Accept`. Rentan cache poisoning jika miskonfigurasi. | **Tinggi**. Selama query parameter dimasukkan ke dalam cache key CDN. |
| **Developer Experience (DX)** | **Sangat Baik**. Mudah diuji di browser, Postman, dan curl tanpa parameter tambahan. | **Sedang**. Klien harus mengonfigurasi header pada HTTP client engine mereka. | **Rendah**. Sangat *verbose*. Membutuhkan sintaks `Accept` MIME eksplisit. | **Sangat Baik**. Cukup modifikasi query string di URL. |
| **Kesesuaian Filosofi REST** | **Melanggar HATEOAS**. Mengubah URI berarti mengubah entitas/identitas sumber daya. | **Baik**. Identitas URI tetap sama, hanya variasi metadata yang diminta. | **Terbaik (Sempurna)**. Sesuai prinsip negosiasi representasi RFC 7231. | **Melanggar HATEOAS**. Menggunakan parameter kontrol alih-alih identitas. |
| **Kompleksitas Routing Gateway** | **Sederhana**. Path-based matching native di Envoy, NGINX, Kong, AWS ALB. | **Tinggi**. Gateway harus mengurai header untuk melakukan dynamic upstream routing. | **Tinggi**. Membutuhkan parser regex pada header `Accept`. | **Sedang**. Didukung sebagian besar gateway melalui query parsing. |
| **Dampak Tooling (Swagger/Postman)** | **Generik & Native**. Langsung didukung tanpa plugin khusus. | **Terbatas**. Sulit membedakan spesifikasi ganda pada URI yang sama. | **Kompleks**. Tooling seperti OpenAPI Generator sering kali bermasalah. | **Generik**. Didukung secara bawaan. |

---

## SEKSI 11 — BEST PRACTICES

1.  **Terapkan Prinsip Ekstensibilitas Aditif (*Additive-Only Evolution*)**:
    Usahakan semaksimal mungkin untuk tidak merilis versi mayor baru. Tambahkan field baru sebagai opsional, bukan menghapus atau mengganti nama yang lama. Rilis versi baru hanya jika model domain atau arsitektur dasar berubah secara fundamental.
2.  **Gunakan Standard-Compliant Headers**:
    Gunakan header resmi IETF RFC 8594 (`Sunset`), Draft RFC (`Deprecation`), dan RFC 8288 (`Link`). Hindari menggunakan header *ad-hoc* seperti `X-Deprecated: true` atau `X-Kill-Date`.
3.  **Patuhi Format IMF-fixdate / RFC 1123**:
    Header `Sunset` wajib menggunakan format tanggal absolut HTTP (contoh: `Sunset: Wed, 11 Nov 2026 00:00:00 GMT`). Jangan gunakan timestamp Unix milidetik atau format ISO-8601 tanpa timezone GMT.
4.  **Konfigurasikan Header `Vary` Secara Agresif**:
    Jika API melakukan perutean respons berdasarkan `Accept`, `Accept-Language`, atau *custom header*, tambahkan header tersebut ke dalam `Vary` (misal: `Vary: Accept, X-API-Version`). Ini menginstruksikan reverse proxy untuk mengisolasi cache berdasarkan kombinasi nilai tersebut.
5.  **Masa Transisi (*Grace Period*) Minimum 6–12 Bulan**:
    Untuk API publik/pihak ketiga, jangan pernah menetapkan tanggal `Sunset` kurang dari 6 bulan sejak header diaktifkan. Untuk API internal antar-microservice, tetapkan minimal 2 siklus sprint/kuartal.
6.  **Terapkan *Brownout Drills* Sebelum Terminasi Total**:
    Dua minggu sebelum tanggal *Sunset*, lakukan *brownout*: matikan endpoint lama secara temporer selama 1 jam (mengembalikan HTTP 410/503) untuk memicu alarm sistem klien yang masih belum migrasi, lalu aktifkan kembali.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

1.  **Mengubah Status Code Keberhasilan menjadi Error Tanpa Versi Baru**:
    Contoh: Versi lama mengembalikan `HTTP 200 OK` dengan payload `{ "status": "failed", "error": "..." }`, lalu tiba-tiba diubah menjadi `HTTP 400 Bad Request` pada URI yang sama. Klien lama yang mengandalkan pengecekan HTTP 200 akan langsung melempar exception fatal.
2.  **Menghapus Field yang "Diduga Tidak Digunakan" Tanpa Analisis Log**:
    Mengasumsikan tidak ada yang menggunakan field `user.fax_number` lalu menghapusnya tanpa verifikasi telemetri access log. Selalu lakukan *distributed tracing* / *log sampling* untuk memvalidasi apakah klien masih mengekstrak properti tersebut.
3.  **Zombie API Versi Lama yang Terlupakan**:
    Membiarkan API `v1` berjalan selama bertahun-tahun tanpa rencana dekomisi (*sunsetting*). Hal ini menyebabkan dependensi library basi yang rentan celah keamanan (CVE) dan membebani arsitektur data.
4.  **Melupakan `Vary: Accept` pada Negosiasi Konten**:
    Ketika mengimplementasikan Media Type Versioning, server lupa menyuntikkan header `Vary: Accept`. Akibatnya, CDN menyimpan respons V2 dan menyajikannya ke klien lama yang meminta V1, mematahkan fungsi parser aplikasi klien.
5.  **Memperkenalkan Validasi Baru yang Terlalu Ketat**:
    Menambahkan batasan karakter minimum atau format regex pada field opsional lama yang sebelumnya menerima teks bebas. Payload klien yang valid di masa lalu mendadak ditolak dengan status `422 Unprocessable Entity`.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1 (Investigasi Breaking Changes):
Diberikan dua spesifikasi OpenAPI berikut. Analisis secara manual dan tentukan semua perubahan yang termasuk ke dalam kategori *Breaking Change*:

*Spec Lama (`base.yaml`):*
```yaml
openapi: 3.0.0
paths:
  /checkout:
    post:
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [cart_id]
              properties:
                cart_id: { type: string }
                coupon_code: { type: string }
      responses:
        '200':
          content:
            application/json:
              schema:
                type: object
                required: [total, status]
                properties:
                  total: { type: number }
                  status: { type: string }
```

*Spec Baru (`head.yaml`):*
```yaml
openapi: 3.0.0
paths:
  /checkout:
    post:
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [cart_id, payment_method]
              properties:
                cart_id: { type: string }
                coupon_code: { type: string }
                payment_method: { type: string, enum: [CREDIT_CARD, EWALLET] }
      responses:
        '200':
          content:
            application/json:
              schema:
                type: object
                required: [total_amount, status]
                properties:
                  total_amount: { type: integer }
                  status: { type: string }
```

### Latihan 2 (Implementasi Sunset Protocol):
Tulis sebuah fungsi middleware HTTP native di bahasa pemrograman pilihan Anda (Go/Node.js/Python) yang mengidentifikasi apakah waktu sekarang telah melampaui tanggal `2025-01-01T00:00:00Z`. Jika sudah lewat, middleware harus memutus request dan mengembalikan status `HTTP 410 Gone` beserta payload JSON `application/problem+json`. Jika belum lewat, sertakan header `Sunset`, `Deprecation`, dan `Link`.

### Latihan 3 (Pipeline Gate Automation):
Buat repositori Git lokal, pasang CLI tool `oasdiff` atau `@openapitools/openapi-diff`, buat script shell `.sh` yang mengembalikan kode status *exit 1* jika terdeteksi perubahan *breaking*, dan buktikan dengan mencoba mengubah field type dari integer ke array.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1.  **Manakah di antara skenario berikut yang BUKAN merupakan *breaking change* pada RESTful API?**
    *   A. Mengubah field response `id` dari tipe `string` ke `integer`.
    *   B. Menambahkan parameter opsional baru pada endpoint query `GET /products`.
    *   C. Menambahkan enum baru pada request body yang wajib divalidasi oleh klien.
    *   D. Mengubah response HTTP dari `204 No Content` menjadi `200 OK` dengan payload baru.

2.  **Apa fungsi utama dari menyertakan header `Vary: Accept` ketika menggunakan Media Type / Content Negotiation Versioning?**
    *   A. Memberitahukan klien URL baru tempat dokumentasi API berada.
    *   B. Mengarahkan traffic ke downstream Kubernetes pod yang berbeda secara dinamis.
    *   C. Memerintahkan cache layer (CDN, Browser, Reverse Proxy) untuk membedakan cache object berdasarkan isi header `Accept`.
    *   D. Mencegah serangan DDoS dengan membatasi request yang tidak memiliki header Accept.

3.  **Sesuai dengan RFC 8594, format penanggalan manakah yang sah digunakan pada header `Sunset`?**
    *   A. `Sunset: 2026-11-11T00:00:00Z` (ISO-8601)
    *   B. `Sunset: 1794355200` (Unix Timestamp Epoch)
    *   C. `Sunset: Wed, 11 Nov 2026 00:00:00 GMT` (IMF-fixdate / RFC 1123)
    *   D. `Sunset: 11-11-2026 00:00:00`

4.  **Mengapa URI Path Versioning (`/v1/resource`) secara teori melanggar prinsip murni HATEOAS / REST?**
    *   A. Karena URI Path tidak mendukung transmisi data biner.
    *   B. Karena URI seharusnya merepresentasikan identitas unik sebuah sumber daya (*resource identity*), bukan variasi skema representasi dari sumber daya tersebut.
    *   C. Karena gateway tidak dapat membaca URI path dengan efisien.
    *   D. Karena HTTP/2 tidak mendukung URI path yang memiliki angka.

5.  **Sebuah endpoint telah berada dalam status Sunset dan melewati tanggal batas akhir (cutoff date). Respons HTTP status code apa yang paling tepat dikembalikan menurut RFC Semantics?**
    *   A. `HTTP 404 Not Found`
    *   B. `HTTP 500 Internal Server Error`
    *   C. `HTTP 400 Bad Request`
    *   D. `HTTP 410 Gone`

### Kunci Jawaban & Pembahasan

1.  **Jawaban: B**. Menambahkan parameter query opsional (*optional query parameter*) adalah perubahan non-breaking. Klien lama yang tidak mengirim parameter tersebut akan tetap dilayani dengan asumsi default oleh server tanpa memicu kegagalan komunikasi.
2.  **Jawaban: C**. Header `Vary` adalah instruksi eksplisit kepada caching engine untuk menyertakan nilai header yang ditunjuk ke dalam algoritma hashing *cache key*. Tanpa ini, CDN akan mengalami *cache collision/poisoning*.
3.  **Jawaban: C**. RFC 8594 Section 3 secara eksplisit mewajibkan format nilai header `Sunset` mematuhi spesifikasi `HTTP-date` sebagaimana didefinisikan pada RFC 7231 (IMF-fixdate / RFC 1123).
4.  **Jawaban: B**. Dalam paradigma REST sejati oleh Roy Fielding, URI adalah *Uniform Resource Identifier*. Entitas konseptual "User 123" tetaplah entitas yang sama, terlepas apakah representasi datanya disajikan dalam skema format tahun 2020 atau format tahun 2024.
5.  **Jawaban: D**. `HTTP 410 Gone` dirancang khusus untuk mengindikasikan bahwa sumber daya target yang diminta pernah ada di server, namun kini telah sengaja dihapus dan tidak akan pernah tersedia lagi secara permanen.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

*   **IETF Standards**:
    *   RFC 8594: *The Sunset HTTP Header Field* (https://www.rfc-editor.org/rfc/rfc8594.html)
    *   IETF Draft: *The Deprecation HTTP Header Field* (https://datatracker.ietf.org/doc/draft-ietf-httpapi-deprecation-header/)
    *   RFC 7231: *Hypertext Transfer Protocol (HTTP/1.1): Semantics and Content*
    *   RFC 8288: *Web Linking (Link Header Parsing)*
    *   RFC 7807: *Problem Details for HTTP APIs*
*   **Engineering Blogs & Books**:
    *   Stripe Engineering: *API versioning at Stripe - Designing robust and evolvable APIs*
    *   Google Cloud Architecture: *API Design Guide (Versioning & Compatibility rules)*
    *   Newman, Sam. *Building Microservices: Designing Fine-Grained Systems (Chapter 4: Integration & Versioning)*. O'Reilly Media.
*   **Open-Source CI/CD Tools**:
    *   Tufin `oasdiff`: https://github.com/tufin/oasdiff
    *   OpenAPI-Tools `openapi-diff`: https://github.com/OpenAPITools/openapi-diff
    *   Buf CLI (khusus Protobuf/gRPC breaking checks): https://buf.build/docs/breaking/overview

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1.  **API Versioning adalah Kompromi Rekayasa**: URI Path versioning menawarkan kepraktisan pengujian (*DX*) dan kompatibilitas *caching*, sementara Media Type versioning mempertahankan kemurnian arsitektur REST namun menuntut disiplin ketat pada layer caching (`Vary: Accept`).
2.  **Kelola Siklus Hidup Secara Transparan**: Matikan API lama menggunakan protokol standar: tandai dengan `Deprecation: @true`, tentukan tenggat waktu dengan `Sunset: <IMF-fixdate>`, berikan instruksi dengan `Link: <url>; rel="sunset"`, dan akhiri siklus hidup dengan status `HTTP 410 Gone`.
3.  **Karakterisasi Perubahan Kontrak**: Setiap modifikasi skema yang menghapus properti, mengubah nama, mengubah tipe data, atau memperketat aturan validasi pada request payload diklasifikasikan sebagai *Breaking Change*.
4.  **Otomatisasi Proteksi di CI/CD**: Jangan mengandalkan pengecekan manual manusia saat code review. Pasang *diffing tool* (`oasdiff`) pada CI runner untuk memblokir pull request yang berpotensi merusak sistem klien secara otomatis dan deterministik.

---

## SEKSI 17 — GLOSARIUM

*   **Breaking Change**: Perubahan pada kontrak API (permintaan atau respons) yang menyebabkan klien yang dibangun berdasarkan kontrak sebelumnya gagal memproses data atau mengalami error sistem.
*   **Non-Breaking Change (Additive Change)**: Perubahan kontrak yang tetap mempertahankan kompatibilitas ke belakang (*backward compatibility*), memungkinkan klien lama beroperasi tanpa modifikasi kode.
*   **Content Negotiation**: Mekanisme yang didefinisikan dalam HTTP yang memungkinkan klien dan server menyepakati format representasi data terbaik yang didukung oleh kedua belah pihak via header `Accept` dan `Content-Type`.
*   **RFC 8594 (Sunset Header)**: Header respons HTTP standar yang mengomunikasikan tanggal dan waktu ketika ketersediaan sumber daya target akan dihentikan secara permanen.
*   **Deprecation Header**: Header respons HTTP (standar rancangan IETF) yang menginformasikan kepada klien bahwa endpoint atau representasi yang digunakan tidak lagi direkomendasikan dan akan segera dihapus.
*   **Vary Header**: Header respons HTTP yang digunakan oleh server untuk menginstruksikan cache proxy (CDN) mengenai header permintaan apa saja yang harus dijadikan bagian dari *cache key composite*.
*   **HTTP 410 Gone**: Status kode respons HTTP yang menunjukkan bahwa akses ke sumber daya target telah sengaja dihentikan secara permanen dan tidak ada alamat pengalihan (*forwarding address*).
*   **oasdiff**: Alat baris perintah (CLI) deterministik dan *Go library* yang digunakan untuk memvalidasi perbedaan (*diff*) serta mendeteksi *breaking changes* antara dua dokumen OpenAPI Specification.

---

## SEKSI 18 — CATATAN INSTRUKTUR

*   **Tantangan Utama Peserta Didik**: Peserta didik sering kali meremehkan perubahan kecil pada respons payload (seperti mengubah tipe data `timestamp` dari milidetik integer menjadi ISO-8601 string). Tekankan bahwa pada bahasa pemrograman dengan *strict typing* (seperti Java, Swift, Go), perubahan ini langsung menyebabkan kegagalan unmarshaling data.
*   **Poin Penekanan Caching**: Buat simulasi sederhana di kelas menggunakan *curl* dan *reverse proxy* (misal NGINX) untuk mendemonstrasikan apa yang terjadi jika `Vary: Accept` dihilangkan pada Media Type versioning. Tunjukkan secara nyata fenomena *cache poisoning*.
*   **Saran Praktikum CI/CD**: Pastikan lingkungan belajar peserta didik telah memiliki akses Git dan binary `oasdiff`. Dorong peserta untuk sengaja membuat *pull request* yang menghapus sebuah required field untuk melihat bagaimana pipeline CI memblokir merge secara langsung.

---

## SEKSI 19 — CHANGELOG & VERSI

*   **Versi 1.0.0 (Oktober 2024)**:
    *   Inisialisasi draf awal kurikulum.
    *   Integrasi spesifikasi IETF RFC 8594 dan IETF Draft Deprecation Header.
    *   Penambahan implementasi framework Fastify TypeScript dan Go Native HTTP.
    *   Penyusunan pipeline workflow automated breaking changes detection menggunakan GitHub Actions dan `oasdiff`.

---

## SEKSI 20 — NAVIGASI KURIKULUM

*   **Modul Sebelumnya**: Bab 07 — *API Performance, Compression, & Caching Strategies*
*   **Modul Saat Ini**: Bab 08 Module 01 — *Lifecycle, Versioning, & Evolution Strategy*
*   **Modul Berikutnya**: Bab 08 Module 02 — *Backward and Forward Compatibility Patterns: Schema Evolution, Protobuf Forward-Compatibility, and Tolerant Reader Pattern*