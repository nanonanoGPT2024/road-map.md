## SEKSI 01 — IDENTITAS MODUL

*   **Mata Kuliah / Kurikulum:** API Architecture & System Design
*   **Kategori:** 06-Architecture-and-System-Design
*   **Kode Modul:** ASD-API-0201
*   **Bab:** 02 — RESTful API Design & Best Practices
*   **Modul:** 01 — Resource Modeling & Pragmatic REST Architecture
*   **Tingkat Kesulitan:** Advanced / Intermediate to Senior Software Engineer
*   **Prasyarat:** Pemahaman dasar protokol HTTP/1.1 dan HTTP/2, konsep dasar Domain-Driven Design (Entities, Value Objects, Aggregates), serta pengalaman membangun backend API dengan arsitektur berbasis layanan.
*   **Estimasi Waktu Penyelesaian:** 150 Menit (Teori: 60 Menit, Bedah Kode & Analisis Kasus: 60 Menit, Latihan Mandiri: 30 Menit)

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1.  **Mendekomposisi Domain Bounded Context (DDD) ke dalam URI Resource:** Mengidentifikasi *Aggregate Roots*, membedakannya dari entitas internal, dan memetakan model relasional/domain ke dalam URI tanpa membocorkan skema basis data (*leaky abstraction*).
2.  **Menyusun Hierarki Endpoint yang Pragmatis:** Mengambil keputusan arsitektural berbasis *trade-off* antara sub-resource bersarang (*nested URIs*) versus relasi datar (*flat/independent resources*).
3.  **Mengimplementasikan Semantik HTTP Sesuai Spesifikasi RFC 9110:** Membedakan karakteristik *Safe* dan *Idempotent* pada kata kerja HTTP (`GET`, `POST`, `PUT`, `PATCH`, `DELETE`), serta memvalidasi kepatuhan arsitekturalnya terhadap idempotensi sisi server.
4.  **Mengevaluasi dan Menerapkan HATEOAS (Hypermedia as the Engine of Application State):** Menilai rasio *cost-to-benefit* dari penerapan Richardson Maturity Model Level 3, serta mendesain *state machine* transisi menggunakan format standar seperti HAL (*Hypertext Application Language*).
5.  **Mendesain Operasi Massal (*Bulk/Batch Actions*):** Menyusun kontrak API pragmatis untuk operasi massal yang menangani kegagalan parsial (*partial failures*) menggunakan status kode HTTP yang tepat (`207 Multi-Status` atau pola asinkron `202 Accepted`).

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                       DOMAIN-DRIVEN DESIGN (DDD)
                                   │
               ┌───────────────────┴───────────────────┐
               ▼                                       ▼
        Bounded Context                         Aggregate Root
               │                                       │
               │ (Context Path)                        │ (Top-Level Resource)
               ▼                                       ▼
        /fulfillment/api/v1                        /orders
                                                       │
                           ┌───────────────────────────┴───────────────────────────┐
                           ▼                                                       ▼
                    Sub-Resources                                           State Machine
               (Child Entities/VOs)                                         (Lifecycle)
                           │                                                       │
                           ▼                                                       ▼
                  /orders/{id}/items                                            HATEOAS
                           │                                                (_links, actions)
                           ▼                                                       │
         PRAGMATIC COMPILATION PATTERNS                                            ▼
                           │                                            Pragmatic Application
         ┌─────────────────┴─────────────────┐                                     │
         ▼                                   ▼                                     ▼
    Bulk Actions                     Idempotency Semantics                     RFC 9110
  - POST /orders/bulk-cancel       - Safe: GET, HEAD                         - Hypermedia State
  - 207 Multi-Status               - Idempotent: PUT, DELETE                   Transitions
  - 202 Accepted + Job URL         - Non-Idempotent: POST, PATCH
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Sering kali pengembang menganggap REST sekadar "mengirimkan JSON melalui HTTP". Anggapan keliru ini menghasilkan arsitektur RPC-over-HTTP (*Remote Procedure Call*) yang rapuh, di mana URI dipenuhi kata kerja seperti `/getUserDetails`, `/cancelOrder`, atau `/updateStatus`, serta respons acak yang selalu mengembalikan status HTTP `200 OK` dengan payload internal `{ "status": "error" }`. 

Dampaknya terhadap sistem terdistribusi meliputi:
1.  **Coupling yang Erat (Tight Coupling):** Klien bergantung pada detail internal implementasi server. Ketika server mengubah alur logika internal, integrasi klien hancur (*breaking changes*).
2.  **Ketiadaan Jaminan Retry (Failed Idempotency Guarantees):** Jaringan terdistribusi bersifat tidak andal (*fallacies of distributed computing*). Ketika transmisi jaringan mengalami *timeout*, klien tidak tahu apakah aman mengirim ulang permintaan. Kegagalan memahami semantik HTTP menyebabkan pemotongan saldo ganda (*double-charging*) atau korupsi data agregat.
3.  **Leaky Abstractions:** Memetakan tabel basis data secara mentah (1:1) menjadi URI membuat batasan konsistensi sistem terbuka ke publik, mengorbankan keamanan, skalabilitas caching, dan fleksibilitas refactoring internal.

Memahami pemodelan resource secara pragmatis menjamin kontrak API stabil, aman terhadap mekanisme *retry*, mendukung arsitektur *caching* berlapis (*edge computing/CDN*), dan mencerminkan domain bisnis secara akurat.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Dekomposisi DDD ke REST Resource
Dalam DDD, sebuah *Aggregate* adalah kluster objek domain yang dapat diperlakukan sebagai satu kesatuan (*unit of data change*). Setiap *Aggregate* memiliki satu *Aggregate Root* yang menjadi pintu gerbang seluruh manipulasi internal. 
*   **Aturan REST Pragmatis:** Hanya *Aggregate Root* yang boleh diekspos sebagai *Top-Level Resource* (misal: `/orders`, `/customers`). 
*   Entitas internal di dalam batas agregat diekspos sebagai *Sub-Resource* hanya jika entitas tersebut tidak memiliki makna hidup di luar *root*-nya (misal: `/orders/{orderId}/items`). Jika entitas anak dapat dirujuk secara global lintas agregat, entitas tersebut harus dipromosikan menjadi resource independen (misal: `/products/{productId}`).

### 2. Semantik Naming (URI Syntax)
URI (Uniform Resource Identifier) adalah **kata benda** (*nouns*), bukan **kata kerja** (*verbs*). Tindakan (*actions*) diekspresikan melalui metode protokol HTTP, bukan melalui segmen path.
*   *Anti-pattern:* `POST /orders/createOrder`, `GET /orders/delete?id=123`
*   *Idiomatik:* `POST /orders`, `DELETE /orders/123`

### 3. Safe & Idempotent Methods (RFC 9110)
*   **Safe Methods:** Metode yang tidak boleh mengubah state server yang terlihat oleh representasi resource. Metode ini aman di-*prefetch* oleh peramban atau *caching proxies* (`GET`, `HEAD`, `OPTIONS`).
*   **Idempotent Methods:** Metode yang apabila dieksekusi sekali atau *N* kali secara berurutan dengan muatan payload yang sama, akan menghasilkan efek samping (*side-effect*) yang identik pada server (`PUT`, `DELETE`, serta safe methods).
*   **Non-Idempotent Methods:** Metode yang setiap eksekusinya dapat menghasilkan perubahan *state* baru atau efek samping tambahan (`POST`, `PATCH` secara teoretis RFC 5789, kendati implementasi patch tertentu bisa didesain idempoten).

| HTTP Method | Safe? | Idempotent? | RFC 9110 Semantics |
| :--- | :--- | :--- | :--- |
| `GET` | **Ya** | **Ya** | Mengambil representasi resource |
| `HEAD` | **Ya** | **Ya** | Mengambil header respons tanpa body |
| `OPTIONS` | **Ya** | **Ya** | Mengambil kapabilitas komunikasi resource |
| `PUT` | Tidak | **Ya** | Mengganti (*replace*) seluruh representasi resource target |
| `PATCH` | Tidak | Tidak* | Modifikasi parsial (*delta update*) |
| `DELETE` | Tidak | **Ya** | Menghapus resource target |
| `POST` | Tidak | Tidak | Pemrosesan target spesifik / pembuatan resource |

*\*Catatan: `PATCH` dapat dibuat idempoten dengan payload berbasis state absolut atau deklaratif, tetapi RFC 5789 tidak mewajibkan idempotensi secara inheren.*

### 4. HATEOAS (Hypermedia As The Engine Of Application State)
Tingkat puncak (Level 3) dari *Richardson Maturity Model*. Sebuah representasi data tidak hanya memuat data atribut mentah, tetapi juga menyertakan pranala kontrol (*hyperlink controls*) yang memberitahukan klien tindakan apa saja yang valid dilakukan berikutnya berdasarkan *state* internal resource saat ini.

### 5. Bulk & Batch Operations
*   **Bulk Operation:** Menjalankan satu jenis operasi yang sama terhadap sekumpulan resource dari tipe yang sama (misal: membatalkan 100 pesanan sekaligus).
*   **Batch Operation:** Membungkus serangkaian operasi yang berbeda (*heterogeneous requests*) ke dalam satu panggilan HTTP komposit (misal: buat user, update order, hapus notifikasi).

---

## SEKSI 06 — BAGAIMANA BEKERJA (HOW)

### Alur 1: Memetakan Domain DDD ke Hierarki Endpoint
1.  **Analisis Transactional Boundary:** Tentukan batas agregat. Jangan biarkan klien mengubah relasi data secara acak tanpa melalui aturan invariabel *Aggregate Root*.
2.  **Identifikasi Identitas Relasional:**
    *   Jika entitas turunan hanya ada selama induknya ada (komposisi ketat), gunakan sub-resource: `/parents/{parentId}/children/{childId}`.
    *   **Batas Kedalaman:** Batasi kedalaman sarang (*nesting*) maksimal **2 tingkat**. Sarang lebih dari dua tingkat (misal: `/tenants/1/users/2/orders/3/items/4/taxes`) adalah indikasi buruknya dekomposisi API (*anti-pattern* "Deep Nesting").
3.  **Flattening Resources:** Jika resource anak memerlukan navigasi langsung, pisahkan menjadi top-level resource dengan filter relasi query parameters:
    *   Alih-alih: `GET /users/58/departments/3/projects/12/tasks`
    *   Gunakan: `GET /tasks?projectId=12&userId=58`

### Alur 2: Menentukan Idempotensi dan State Transition
Untuk mengubah state pada Aggregate Root yang kompleks (misalnya: mengubah status pesanan dari `PLACED` ke `CANCELLED`):
*   **Pendekatan REST Murni (Resource Mutation):**
    ```http
    PATCH /orders/ORD-8921 HTTP/1.1
    Content-Type: application/merge-patch+json

    {
      "status": "CANCELLED",
      "cancellationReason": "Customer requested refund"
    }
    ```
*   **Pendekatan Pragmatic Sub-Resource State (Action-as-a-Resource):**
    Jika transisi state memerlukan payload audit yang kompleks atau memicu alur kerja asinkron yang panjang, perlakukan aksi tersebut sebagai resource tersendiri:
    ```http
    POST /orders/ORD-8921/cancellation HTTP/1.1
    Content-Type: application/json
    Idempotency-Key: 7b9a528e-cfbe-48be-850d-6126ca1215b2

    {
      "reason": "Customer requested refund",
      "requestedBy": "USER-441"
    }
    ```

### Alur 3: Eksekusi Bulk Actions
Terdapat dua pendekatan standar bergantung pada batas latensi pemrosesan:
1.  **Synchronous Small Bulk (`207 Multi-Status`):** Digunakan jika eksekusi operasi dapat diselesaikan dalam window latensi HTTP normal (< 1-2 detik).
2.  **Asynchronous Large Bulk (`202 Accepted`):** Digunakan jika pemrosesan massal membutuhkan waktu lama. Server membuat *Job Resource* dan mengembalikan URI pelacak via header `Location`.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### Pemetaan Aggregate Root DDD ke Hierarki REST API

```
+-----------------------------------------------------------------------------------+
| BOUNDED CONTEXT: ORDER MANAGEMENT                                                 |
|                                                                                   |
|  +-------------------------------------------------------+                        |
|  | AGGREGATE: Order (Aggregate Root)                     |                        |
|  |   - ID: ORD-901                                       |                        |
|  |   - Status: CONFIRMED                                 |                        |
|  |   - CustomerRef: CUST-44                              |                        |
|  |   - LineItems: [                                      |                        |
|  |       Item { ID: ITEM-1, Product: "A", Qty: 2 },      |                        |
|  |       Item { ID: ITEM-2, Product: "B", Qty: 1 }       |                        |
|  |     ]                                                 |                        |
|  +-------------------------------------------------------+                        |
+-----------------------------------------------------------------------------------+
                                   │
               Pemetaan ke Kontrak Arsitektur HTTP Pragmatis
                                   │
                                   ▼
+───────────────────────────────────────────────────────────────────────────────────+
| TOP-LEVEL RESOURCE (Mewakili Aggregate Root)                                      |
| -> GET, POST      : /api/v1/orders                                                |
| -> GET, PUT, PATCH: /api/v1/orders/ORD-901                                        |
+───────────────────────────────────────────────────────────────────────────────────+
         │                                                 │
         │ (Sub-resource terikat siklus hidup)             │ (State Transition Control)
         ▼                                                 ▼
+─────────────────────────────────────────+     +───────────────────────────────────+
| SUB-RESOURCE (Child Entity)             |     | SUB-RESOURCE INTENT / TRANSITION  |
| -> GET  : /api/v1/orders/ORD-901/items  |     | -> POST:                          |
| -> POST : /api/v1/orders/ORD-901/items  |     |    /api/v1/orders/ORD-901/cancel  |
| -> PATCH:                               |     |    (Atau PATCH status)            |
|    /api/v1/orders/ORD-901/items/ITEM-1  |     +───────────────────────────────────+
+─────────────────────────────────────────+
```

### State Machine Transisi Lifecycle Resource via HATEOAS

```
              State: CREATED
         +──────────────────────+
         | GET /orders/101      |
         | Links: [pay, cancel] |
         +──────────────────────+
              │            │
   POST /pay  │            │ POST /cancel
              ▼            ▼
     State: PAID          State: CANCELLED
+─────────────────────+  +──────────────────────+
| GET /orders/101     |  | GET /orders/101      |
| Links: [ship]       |  | Links: [archive]     |
+─────────────────────+  +──────────────────────+
         │
POST /ship
         ▼
    State: SHIPPED
+─────────────────────+
| GET /orders/101     |
| Links: [track]      |
+─────────────────────+
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah representasi endpoint pengelolaan pesanan yang mencontohkan *naming convention*, semantik HTTP standar, dan manipulasi *state*.

### 1. Membuat Resource Baru (Non-Idempotent)
**Request:**
```http
POST /api/v1/orders HTTP/1.1
Host: api.store.domain.com
Content-Type: application/json

{
  "customerId": "cust_88291",
  "items": [
    { "productId": "prod_110", "quantity": 2 }
  ]
}
```

**Response:**
```http
HTTP/1.1 201 Created
Location: /api/v1/orders/ord_55102
Content-Type: application/json

{
  "id": "ord_55102",
  "status": "PENDING",
  "customerId": "cust_88291",
  "items": [
    { "itemId": "item_1", "productId": "prod_110", "quantity": 2 }
  ],
  "createdAt": "2026-03-31T08:00:00Z"
}
```

### 2. Membaca Resource Secara Aman dan Idempoten
**Request:**
```http
GET /api/v1/orders/ord_55102 HTTP/1.1
Host: api.store.domain.com
Accept: application/json
```

**Response:**
```http
HTTP/1.1 200 OK
Content-Type: application/json
ETag: W/"order-55102-v1"

{
  "id": "ord_55102",
  "status": "PENDING",
  "customerId": "cust_88291",
  "totalAmount": 250000,
  "createdAt": "2026-03-31T08:00:00Z"
}
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Kasus arsitektur enterprise: Modul *Fulfillment Order Management Engine* yang menangani idempotensi jaringan, navigasi *hypermedia state* (HATEOAS HAL JSON), dan eksekusi pembatalan massal (*Bulk Cancellation*).

### Implementasi Model Representasi HATEOAS (Format HAL RFC/IETF Draft)

Ketika klien mengeksekusi `GET /api/v1/orders/ORD-9901`, server mengevaluasi *business rules* dan mengembalikan status beserta aksi berikutnya yang *legal* bagi klien tersebut:

```http
HTTP/1.1 200 OK
Content-Type: application/hal+json
Cache-Control: private, max-age=60
ETag: "9b4f2c8d1"

{
  "orderId": "ORD-9901",
  "status": "AWAITING_PAYMENT",
  "total": {
    "amount": 1450000.00,
    "currency": "IDR"
  },
  "customer": {
    "id": "CUST-1029",
    "name": "Alex Wira"
  },
  "_links": {
    "self": {
      "href": "/api/v1/orders/ORD-9901"
    },
    "customer": {
      "href": "/api/v1/customers/CUST-1029"
    },
    "payment": {
      "href": "/api/v1/orders/ORD-9901/payments",
      "method": "POST",
      "title": "Pay this order before expiration"
    },
    "cancel": {
      "href": "/api/v1/orders/ORD-9901/cancellation",
      "method": "POST",
      "title": "Cancel order"
    }
  }
}
```
*Jika order telah berstatus `PAID`, tautan `payment` dan `cancel` otomatis dicabut dari payload respons server. Klien cukup memeriksa ketersediaan link untuk merender UI tombol pembayaran.*

---

### Implementasi Operasi Idempoten dengan Header Eksternal

Menghindari duplikasi pembayaran ketika terjadi *timeout* jaringan di sisi klien:

```http
POST /api/v1/orders/ORD-9901/payments HTTP/1.1
Host: api.store.domain.com
Content-Type: application/json
Idempotency-Key: 8a93a027-313d-4c3e-a1e4-39909249e0c7

{
  "method": "BANK_TRANSFER",
  "amount": 1450000.00,
  "referenceNumber": "TRX-BCA-9812739"
}
```

**Penanganan Server (Logika Idempotensi):**
```go
// Cuplikan Logika Idempotensi Tingkat Engine Server (Pseudo-Go)
func HandlePayment(w http.ResponseWriter, r *http.Request) {
    idempotencyKey := r.Header.Get("Idempotency-Key")
    if idempotencyKey == "" {
        http.Error(w, "Idempotency-Key header is required", http.StatusBadRequest)
        return
    }

    // 1. Cek Atomic Lock / Record Cache di Redis
    cachedResponse, exists := cache.Get(r.Context(), idempotencyKey)
    if exists {
        // Kembalikan byte respons asli yang tersimpan sebelumnya tanpa re-eksekusi domain logic
        w.Header().Set("X-Cache-Lookup", "HIT - Idempotent Replay")
        w.WriteHeader(cachedResponse.StatusCode)
        w.Write(cachedResponse.Body)
        return
    }

    // 2. Jalankan Perubahan State Domain Aggregat
    paymentResult, err := domainService.ExecutePayment(r.Context(), r.Body)
    if err != nil {
        handleDomainError(w, err)
        return
    }

    // 3. Simpan Respons ke Cache terdistribusi dengan TTL aman (misal: 24 jam)
    cache.Save(r.Context(), idempotencyKey, paymentResult, 24*time.Hour)

    w.WriteHeader(http.StatusCreated)
    json.NewEncoder(w).Encode(paymentResult)
}
```

---

### Kontrak Bulk Action: Pola Sinkron Parsial (RFC 4918 / WebDAV 207 Multi-Status)

Klien membatalkan sekumpulan pesanan sekaligus (`POST /api/v1/orders/bulk-cancel`):

**Request:**
```http
POST /api/v1/orders/bulk-cancel HTTP/1.1
Host: api.store.domain.com
Content-Type: application/json

{
  "cancellationReason": "Warehouse Inventory Mismatch",
  "orderIds": [
    "ORD-9901",
    "ORD-9902",
    "ORD-9903"
  ]
}
```

**Response (HTTP 207 Multi-Status):**
```http
HTTP/1.1 207 Multi-Status
Content-Type: application/json

{
  "summary": {
    "total": 3,
    "succeeded": 2,
    "failed": 1
  },
  "results": [
    {
      "orderId": "ORD-9901",
      "status": 200,
      "message": "Order successfully cancelled"
    },
    {
      "orderId": "ORD-9902",
      "status": 409,
      "error": {
        "code": "ORDER_ALREADY_SHIPPED",
        "detail": "Cannot cancel order because package has left fulfillment center"
      }
    },
    {
      "orderId": "ORD-9903",
      "status": 200,
      "message": "Order successfully cancelled"
    }
  ]
}
```

---

### Kontrak Bulk Action: Pola Asinkron (*Long-Running Job Pattern*)

Jika bulk action mencakup ribuan item, server tidak boleh menahan socket TCP:

**Request:**
```http
POST /api/v1/orders/bulk-archive HTTP/1.1
Host: api.store.domain.com
Content-Type: application/json

{
  "filter": {
    "createdBefore": "2025-01-01T00:00:00Z"
  }
}
```

**Response:**
```http
HTTP/1.1 202 Accepted
Location: /api/v1/jobs/job-arch-77189
Retry-After: 30
Content-Type: application/json

{
  "jobId": "job-arch-77189",
  "status": "QUEUED",
  "createdAt": "2026-03-31T08:30:00Z",
  "_links": {
    "status": {
      "href": "/api/v1/jobs/job-arch-77189"
    }
  }
}
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Dimensi Arsitektur | Opsi A | Opsi B | Trade-off Analysis |
| :--- | :--- | :--- | :--- |
| **Hierarki Resource** | **Deeply Nested**<br>`/departments/1/teams/2/users/3` | **Flat Resources**<br>`/users/3` atau `/users?teamId=2` | *Deeply Nested* memperjelas hierarki otorisasi dan konteks kepemilikan, namun membuat URI kaku, panjang, serta merekatkan URI ke struktur hierarki internal. *Flat Resources* memberikan fleksibilitas tinggi, URI lebih pendek, dan mempermudah caching, tetapi memerlukan mekanisme otorisasi decoupled pada layer business logic. |
| **Penerapan HATEOAS** | **Full Hypermedia Engine (HAL/Siren)** | **Static Payload Tanpa Hypermedia** | *Full HATEOAS* menurunkan *coupling* logika klien terhadap *state transitions* di server (klien hanya mengikuti link), namun secara drastis meningkatkan ukuran payload JSON (bandwidth overhead) dan kompleksitas implementasi klien mobile yang umumnya menyukai schema statis (e.g., TypeScript/Swift types). |
| **Bulk Actions** | **Sinkron (207 Multi-Status)** | **Asinkron (202 Accepted + Job Polling)** | *Sinkron* mudah dikonsumsi klien karena respons langsung diterima, namun berisiko HTTP timeout jika memproses volume masif dan mengunci thread koneksi DB. *Asinkron* mampu menangani jutaan baris tanpa membebani gateway, tetapi klien dipaksa mengimplementasikan pola *polling* atau *WebSocket/webhook* untuk memantau status eksekusi. |
| **Idempotensi `PATCH` vs `PUT`**| **Strict `PUT` (Whole Replace)** | **Partial `PATCH` (JSON Patch / Merge)** | `PUT` secara bawaan aman diulang (*idempotent*), tetapi klien harus selalu mengirim *seluruh* payload atribut yang rentan *race condition* jika ada modifikasi bersamaan. `PATCH` menghemat bandwidth, namun memastikan idempotensi pada operasi manipulasi delta (misal: "tambahkan saldo 100") membutuhkan penanganan `Idempotency-Key` khusus di server. |

---

## SEKSI 11 — BEST PRACTICES

1.  **Gunakan Kata Benda Jamak (*Plural Nouns*):** Konsisten menggunakan kata benda jamak untuk koleksi resource (`/api/v1/products`, `/api/v1/invoices`).
2.  **Gunakan Kasus Huruf Kecil Berkebab (*kebab-case*):** URI bersifat case-sensitive menurut spesifikasi RFC (kecuali skema dan domain). Gunakan pemisah tanda hubung untuk segmen gabungan kata: `/order-fulfillments`, bukan `/orderFulfillments` atau `/order_fulfillments`.
3.  **Hormati Semantik Status Kode HTTP:**
    *   `200 OK`: Pengambilan/pembaruan data sukses sinkron.
    *   `201 Created`: Pembuatan resource berhasil, **wajib** sertakan header `Location`.
    *   `202 Accepted`: Permintaan diterima dan divalidasi, tetapi pemrosesan dilakukan secara asinkron.
    *   `204 No Content`: Eksekusi berhasil, tidak ada data payload yang dikembalikan (umum pada operasi `DELETE`).
    *   `400 Bad Request`: Payload rusak, malformed JSON, atau validasi tipe data gagal.
    *   `404 Not Found`: URI tidak merujuk pada resource konkret manapun.
    *   `409 Conflict`: Permintaan melanggar aturan integritas domain/state agregat saat ini (misal: membatalkan pesanan yang sudah terkirim).
    *   `422 Unprocessable Entity`: Sintaksis JSON benar, namun terdapat validasi bisnis semantik yang gagal.
4.  **Enforce Idempotency Keys pada Mutasi Kritis:** Wajibkan header `Idempotency-Key` (UUIDv4) pada operasi `POST` finansial atau manipulasi resource esensial untuk mencegah *charge/action duplication*.
5.  **Isolasi Versi API di Path Utama:** Letakkan versi pada tingkat domain atau path prefix awal (`/api/v1/orders`), bukan sebagai query parameter (`/orders?v=1`).

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. The "Tunneling RPC over GET/POST" Anti-Pattern
*   *Salah:* Menggunakan GET untuk mutasi atau menyematkan aksi di URL:
    ```http
    GET /api/v1/deleteUser?userId=102 HTTP/1.1
    POST /api/v1/orders/102/update-status-to-paid HTTP/1.1
    ```
*   *Perbaikan:* Gunakan kata kerja HTTP yang tepat atau ubah aksi transisi menjadi state resource:
    ```http
    DELETE /api/v1/users/102 HTTP/1.1
    POST /api/v1/orders/102/payments HTTP/1.1
    ```

### 2. The "200 OK Error Pattern"
*   *Salah:* Mengembalikan HTTP 200 dengan status kegagalan di dalam payload JSON:
    ```http
    HTTP/1.1 200 OK
    Content-Type: application/json

    {
      "success": false,
      "errorCode": "INSUFFICIENT_FUNDS",
      "message": "Saldo akun tidak mencukupi"
    }
    ```
*   *Bahaya Arsitektural:* Load balancer, API Gateway, CDN, dan proxy jaringan akan menganggap transmisi ini sukses, mencatat metrik ketersediaan (*availability SLA*) palsu, dan berpotensi menyimpan representasi *error* ke dalam cache publik.
*   *Perbaikan:* Kembalikan status HTTP `422 Unprocessable Entity` atau `400 Bad Request` dengan payload standar RFC 7807 (*Problem Details for HTTP APIs*).

### 3. Mengabaikan Idempotensi pada Operasi `DELETE`
*   *Salah:* Merancang server untuk mengembalikan `404 Not Found` ketika `DELETE /orders/102` dipanggil untuk kedua kalinya, sehingga memicu kepanikan (*error alert*) di pipeline klien.
*   *Perbaikan:* Klien mengeksekusi DELETE dengan ekspektasi: "Pastikan resource ini tidak lagi ada di sistem". Jika pemanggilan kedua mendapati resource sudah hilang, server pragmatis harus tetap merespons aman dengan `204 No Content` atau `200 OK` (atau `404` hanya jika konteks domain mengharuskan pelacakan histori yang ketat). Intinya, efek samping (*state of the system*) tetap sama: resource terhapus.

### 4. Over-Nesting URIs (URI Pyramid of Doom)
*   *Salah:*
    ```http
    GET /organizations/12/divisions/4/teams/88/members/99/permissions
    ```
*   *Perbaikan:*
    ```http
    GET /members/99/permissions
    ```
    *Dekomposisi domain: Jika `member` memiliki identitas ID unik global (`99`), buat ia dapat diakses langsung tanpa membeberkan silsilah organisasinya di dalam path.*

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1: Dekomposisi Model Domain ke Spesifikasi API (Tingkat: Intermediate)
*   **Skenario:** Anda adalah Principal Architect untuk platform pergudangan logistik. Terdapat Domain Aggregate Root bernama `ShipmentBatch`. Di dalam `ShipmentBatch`, terdapat entitas `Package`, dan di dalam `Package` terdapat kumpulan `Item`. Sebuah `ShipmentBatch` memiliki siklus hidup: `STAGED` -> `LOADING` -> `IN_TRANSIT` -> `DELIVERED`.
*   **Tugas:**
    1.  Tuliskan struktur URI untuk mengambil seluruh `Packages` di dalam `ShipmentBatch` tertentu.
    2.  Tuliskan struktur URI untuk menambahkan `Item` baru ke dalam `Package` tertentu.
    3.  Tuliskan kontrak HTTP (Metode, URI, Headers, dan Payload) untuk memicu transisi status `ShipmentBatch` dari `STAGED` ke `LOADING` dengan menjamin idempotensi jaringan.

### Latihan 2: Desain API Bulk Update dengan Partial Failure (Tingkat: Advanced)
*   **Skenario:** Klien enterprise ingin memperbarui kuota inventaris untuk 50 produk sekaligus dalam satu kali panggilan network. Beberapa produk mungkin tidak ditemukan, beberapa berhasil diperbarui, dan beberapa terkunci oleh proses lain.
*   **Tugas:**
    1.  Rancang kontrak HTTP Request (Endpoint, Verb, Payload body).
    2.  Rancang format respons yang mematuhi semantik `207 Multi-Status` atau pola `RFC 7807 Problem Details` yang menjelaskan hasil evaluasi per-item.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1.  **Mengapa operasi `GET` harus dirancang "Safe" menurut spesifikasi RFC 9110?**
    *   a) Agar beban database berkurang drastis saat traffic tinggi.
    *   b) Karena intermediary proxies, peramban, dan CDN memiliki hak untuk mengeksekusi, mengulang, atau melakukan caching pada safe methods tanpa mengubah state resource di server.
    *   c) Agar server tidak perlu mengembalikan data payload di dalam response body.
    *   d) Karena metode yang safe otomatis mengenkripsi data yang ditransmisikan.

2.  **Manakah rancangan endpoint berikut yang mematuhi kaidah Resource-Centric REST pragmatis untuk membatalkan pesanan?**
    *   a) `POST /api/v1/orders/cancel?orderId=ORD-1`
    *   b) `GET /api/v1/orders/ORD-1/cancel`
    *   c) `POST /api/v1/orders/ORD-1/cancellation`
    *   d) `DELETE /api/v1/orders/cancel-ORD-1`

3.  **Sebuah aplikasi mobile mengirim `POST /api/v1/payments` dengan header `Idempotency-Key: X`. Koneksi putus sebelum mobile menerima respons. Mobile mengirim ulang request yang persis sama. Apa yang harus dilakukan oleh server?**
    *   a) Menolak request dan mengembalikan `400 Bad Request`.
    *   b) Memotong saldo kembali untuk menjamin konsistensi ACID database.
    *   c) Mengenali `Idempotency-Key: X`, membatalkan transaksi domain baru, dan memutar ulang (*replay*) respons yang identik dengan transaksi sebelumnya.
    *   d) Mengembalikan `404 Not Found`.

4.  **Apa indikasi utama sebuah endpoint menderita *anti-pattern* "Deep Nesting"?**
    *   a) Endpoint menggunakan lebih dari satu kata kerja HTTP.
    *   b) URI memiliki hierarki child resource lebih dari dua lapis (misal: `/a/{id}/b/{id}/c/{id}/d/{id}`).
    *   c) Endpoint mengembalikan format XML bukan JSON.
    *   d) Endpoint menggunakan UUID alih-alih auto-increment integer.

5.  **Kapan sebaiknya kita beralih dari pola Synchronous Bulk (`207 Multi-Status`) ke Pola Asynchronous Job (`202 Accepted`)?**
    *   a) Saat ukuran payload JSON melebihi 1 Kilobyte.
    *   b) Ketika pemrosesan batch membutuhkan waktu eksekusi yang lama atau tidak dapat diprediksi secara real-time, sehingga berisiko memutuskan koneksi gateway/proxy.
    *   c) Saat database tidak memiliki tabel relasional.
    *   d) Setiap kali kita menggunakan HTTP/2 atau HTTP/3.

---

### Jawaban Kuis & Evaluasi Mandiri
*   **1: b** — Intermediary components bergantung pada kesepakatan bahwa `Safe` methods tidak mengubah representasi state resource secara langsung.
*   **2: c** — Menggunakan kata benda dan memperlakukan proses transisi state kritis sebagai resource intent (`/cancellation`) atau menggunakan `PATCH` pada status.
*   **3: c** — Mekanisme idempotensi bertugas meredam duplikasi mutasi akibat *network retry* dan membalas dengan representasi state yang sudah dihasilkan sebelumnya.
*   **4: b** — Kedalaman relasi URI yang melebihi 2 tingkat menandakan bocornya relasi internal database ke interface publik.
*   **5: b** — Asynchronous job pattern membebaskan koneksi HTTP agar tidak terkena *gateway timeout* (HTTP 504) ketika memproses agregasi data yang masif.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

1.  **IETF Specifications:**
    *   *RFC 9110: HTTP Semantics* (Bagian: Safe Methods, Idempotent Methods, Status Codes).
    *   *RFC 5789: PATCH Method for HTTP*.
    *   *RFC 7807: Problem Details for HTTP APIs*.
    *   *RFC 4918: HTTP Extensions for WebDAV (Multi-Status 207)*.
2.  **Buku Klasik Arsitektur:**
    *   Fielding, Roy Thomas. (2000). *Architectural Styles and the Design of Network-based Software Architectures* (Disertasi Doktoral UC Irvine — Chapter 5: REST).
    *   Evans, Eric. (2003). *Domain-Driven Design: Tackling Complexity in the Heart of Software*. Addison-Wesley.
    *   Vernon, Vaughn. (2013). *Implementing Domain-Driven Design*. Addison-Wesley.
3.  **Spesifikasi Desain Hypermedia:**
    *   *JSON HAL (Hypertext Application Language):* `draft-kelly-json-hal-11`.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1.  **Dekomposisi DDD:** Memetakan domain bisnis ke API membutuhkan isolasi *Aggregate Root*. Hanya *Aggregate Root* yang diekspos sebagai resource tingkat utama (*Top-Level*). Hindari mengekspos tabel database secara mentah.
2.  **Pragmatic REST vs Dogmatic REST:** REST sejati bukanlah dogma akademis kaku. Kita tidak perlu memaksakan HATEOAS ke setiap representasi internal, namun prinsip semantik kata benda (*nouns*), kata kerja HTTP (*verbs*), serta *Safe/Idempotent contract* adalah fondasi non-negosiasi bagi kestabilan sistem terdistribusi.
3.  **Idempotensi adalah Jaminan Sistem:** Kegagalan jaringan adalah keniscayaan. Operasi mutasi kritis wajib dilindungi kontrak idempotensi (menggunakan semantik HTTP `PUT`/`DELETE` murni, atau menyertakan `Idempotency-Key` pada operasi `POST`/`PATCH`).
4.  **Bulk Management:** Bedakan synchronous bulk handling (`207 Multi-Status`) untuk muatan berlatensi rendah dari asynchronous long-running job (`202 Accepted` + `Location header`) untuk eksekusi data bervolume masif.

---

## SEKSI 17 — GLOSARIUM

*   **Aggregate Root:** Entitas utama dalam Domain-Driven Design yang bertindak sebagai gerbang tunggal untuk mengakses, memvalidasi, dan memodifikasi sekumpulan entitas internal di bawah batas transaksionalnya.
*   **Idempotency:** Properti sistem di mana pemanggilan operasi yang sama sebanyak satu kali atau berkali-kali secara berurutan menghasilkan state server yang sama persis tanpa efek samping tambahan.
*   **Safe Methods:** Metode HTTP yang eksekusinya bersifat read-only terhadap state representasi resource (tidak mengubah data esensial di sisi server).
*   **HATEOAS:** *Hypermedia As The Engine Of Application State*; panduan arsitektur REST di mana server mengembalikan data beserta tautan hypermedia dinamis yang memandu klien tentang aksi apa yang sah diambil selanjutnya.
*   **HAL (Hypertext Application Language):** Standar konvensi JSON sederhana untuk menyematkan hyperlink (`_links`) dan resource tersemat (`_embedded`) ke dalam representasi API.
*   **Partial Failure:** Kondisi dalam pemrosesan operasi massal (*bulk*) di mana sebagian data berhasil diproses sedangkan sebagian lainnya mengalami kegagalan.

---

## SEKSI 18 — CATATAN INSTRUKTUR

*   **Fokus Pedagogis:** Mahasiswa/engineer kerap kesulitan memahami perbedaan antara `PUT` dan `PATCH`. Tekankan bahwa `PUT` adalah *replacement* (mengganti total, jika ada atribut kosong berarti di-set null/default), sedangkan `PATCH` adalah mutasi parsial (*delta*). Berikan analogi berkas fisik: `PUT` membuang map lama dan menaruh map baru; `PATCH` hanya menempelkan label koreksi di halaman tertentu.
*   **Edukasi HATEOAS:** Jangan mengajarkan HATEOAS sebagai kewajiban mutlak di seluruh enterprise endpoint. Akui secara jujur bahwa HATEOAS membawa *payload overhead* dan sering kali diabaikan oleh tim frontend modern yang mengandalkan strongly-typed generated clients (seperti OpenAPI/Swagger-Codegen atau tRPC). Ajarkan HATEOAS secara pragmatis: gunakan saat state machine siklus hidup resource sangat dinamis (misal: status order, checkout workflow, approval chain).
*   **Live Coding Demo:** Buat demonstrasi langsung di mana koneksi diputus (menggunakan simulasi proxy latency/timeout) saat klien mengeksekusi pembayaran, kemudian tunjukkan bagaimana backend menangani eksekusi ulang via `Idempotency-Key` tanpa menduplikasi data transaksi di basis data.

---

## SEKSI 19 — CHANGELOG & VERSI

*   **Versi 1.0.0 (Maret 2026):**
    *   Rilis awal materi kurikulum arsitektur API tingkat lanjut.
    *   Penyelarasan penuh terminologi dengan RFC 9110 (menggantikan referensi usang RFC 7231 / RFC 2616).
    *   Integrasi panduan dekomposisi Domain-Driven Design ke pemodelan URI.
    *   Penambahan spesifikasi penanganan Bulk Actions (Sync 207 vs Async 202).

---

## SEKSI 20 — NAVIGASI KURIKULUM

*   **Modul Sebelumnya:** Bab 01 Module 03 — *Protocols Deep-Dive: HTTP/1.1 Pipelining, HTTP/2 Multiplexing, HTTP/3 QUIC & gRPC Internals*
*   **Modul Berikutnya:** Bab 02 Module 02 — *API Versioning, Breaking Changes Lifecycle, Deprecation Strategies & Contract Evolution*
*   **Modul Terkait (Cross-Reference):**
    *   `06-Architecture-and-System-Design/api-design/03-01`: *Data Contract Governance & Schema Evolution with Protobuf and JSON Schema*
    *   `06-Architecture-and-System-Design/distributed-systems/04-02`: *Distributed Transactions & Idempotency Engines*