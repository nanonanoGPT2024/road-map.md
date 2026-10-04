# BAB 03: Quiz, Challenge, & Knowledge Check
**Prinsip Desain RESTful API & Kontrak Data**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Dekomposisi Richardson Maturity Model**  
   Jelaskan secara arsitektural evolusi dari Level 1 (Resources) hingga Level 3 (HATEOAS) dalam Richardson Maturity Model. Apa rasionalisasi teknis mengapa sebagian besar sistem enterprise modern secara sadar berhenti di Level 2, dan konsekuensi operasional apa yang muncul jika Hypermedia Controls (Level 3) dipaksakan pada ekosistem microservices internal?

2. **Idempotensi Matematis vs Implementasi Protokol HTTP**  
   Definisikan karakteristik *Safe* dan *Idempotent* dalam metode HTTP (`GET`, `POST`, `PUT`, `PATCH`, `DELETE`) secara formal. Jelaskan mengapa operasi `DELETE /users/123` tetap diklasifikasikan sebagai *idempotent* menurut spesifikasi RFC 9110, meskipun respons HTTP pertama menghasilkan status `200/204` dan pemanggilan kedua berpotensi menghasilkan status `404 Not Found`.

3. **Prinsip Robustness (Postel’s Law) dan Kontrak Data**  
   Bagaimana Postel's Law (*"Be conservative in what you send, be liberal in what you accept"*) diterapkan dalam perancangan skema data RESTful API? Apa bahaya struktural menerapkan prinsip ini secara berlebihan (*over-lenient*) pada backend yang menangani transaksi finansial atau data sensitif?

4. **Semantik Validasi: HTTP 400 vs 422 vs 409**  
   Banyak developer keliru mencampuradukkan penanganan error klien. Bedakan batas semantik yang presisi antara status code `400 Bad Request`, `422 Unprocessable Entity` (RFC 4918/9110), dan `409 Conflict`. Berikan contoh payload atau kondisi sistem konkret yang memicu masing-masing status tersebut dalam alur registrasi pengguna baru.

5. **Content Negotiation dan Header Semantics**  
   Jelaskan alur *Proactive Content Negotiation* antara klien dan server menggunakan header `Accept`, `Content-Type`, dan `Accept-Encoding`. Bagaimana backend secara elegan merespons permintaan jika klien meminta representasi data yang tidak didukung (`406 Not Acceptable` vs `415 Unsupported Media Type`)?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Tristate Problem dalam Operasi PATCH: `null` vs `undefined`**  
   Dalam implementasi partial update menggunakan HTTP `PATCH`, bagaimana engine backend Anda membedakan secara deterministik antara tiga state data berikut pada payload JSON:
   * Field tidak dikirim (klien tidak ingin mengubah data).
   * Field dikirim dengan nilai `null` (klien ingin menghapus/mengosongkan data di database).
   * Field dikirim dengan nilai kosong seperti string kosong `""` atau angka `0`?  
   Bandingkan pendekatan solusi menggunakan RFC 7386 (JSON Merge Patch) versus RFC 6902 (JSON Patch).

2. **Mekanisme Optimistic Locking Menggunakan ETag dan Conditional Headers**  
   Jelaskan siklus hidup (*lifecycle*) konkurensi data menggunakan header `ETag`, `If-Match`, dan `If-None-Match`. Bagaimana mekanisme ini mencegah fenomena *lost update* (ketika dua admin mengedit resource yang sama secara bersamaan) tanpa perlu mengunci baris database (*pessimistic lock*)?

3. **Anatomi dan Standardisasi Error RFC 7807 (Problem Details)**  
   Analisis mengapa struktur payload error *ad-hoc* (misal: `{"success": false, "message": "error"}`) merupakan anti-pattern dalam integrasi skala besar. Bedah field wajib dan opsional dari standar RFC 7807 (`type`, `title`, `status`, `detail`, `instance`), serta jelaskan bagaimana Anda menginjeksikan trace correlation ID (`traceparent` W3C) ke dalam struktur tersebut tanpa membocorkan stack trace internal.

4. **Bottleneck Pagination: Offset-Based vs Cursor-Based (Keyset)**  
   Tinjau query database di balik endpoint pagination. Mengapa `GET /items?limit=20&offset=1000000` dapat mendegradasi performa database relational secara drastis (*O(N) scan overhead*) dan menyebabkan masalah *data drift*? Rancang struktur kontrak data untuk Cursor-Based Pagination yang menyelesaikan kedua masalah tersebut.

5. **Desain Operasi Batch dan Bulk Mutasi pada REST**  
   REST secara alamiah berorientasi pada manipulasi resource tunggal. Ketika sistem Anda dituntut untuk mengeksekusi operasi massal (misal: import 5.000 transaksi sekaligus), bagaimana Anda merancang kontrak API-nya? Bahas trade-off antara synchronous atomic processing (menggunakan `200 OK` / `400 Bad Request`), partial failure reporting (`207 Multi-Status`), dan asynchronous processing (`202 Accepted` dengan polling status resource).

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden "Double Charge" Akibat Retry Network Timeout
**Konteks Insiden:**  
Sebuah aplikasi mobile checkout e-commerce memanggil endpoint `POST /v1/payments`. Klien mengalami timeout koneksi (TCP socket timeout) pada detik ke-5 karena latensi jaringan seluler buruk, lalu secara otomatis mengirimkan ulang (*retry*) request yang sama sebanyak 3 kali. Di sisi server, request pertama sebenarnya berhasil diproses oleh database dan memotong saldo user, namun koneksi TCP terputus sebelum server sempat mengirimkan respons HTTP 201 ke klien. Akibatnya, saldo pengguna terpotong 4 kali lipat untuk 1 checkout.

**Pertanyaan Diagnostik:**
1. Rancang arsitektur mekanisme *Idempotency-Key* berbasis HTTP header (`Idempotency-Key: <UUID>`) pada backend gateway/service untuk memitigasi insiden ini.
2. Bagaimana strategi caching idempotency state machine Anda (menggunakan state: `STARTED`, `PROCESSED`, `FAILED`) di Redis? Bagaimana Anda mencegah *race condition* jika retry request kedua tiba saat request pertama masih berjalan di thread pool worker server?
3. Status code dan payload apa yang harus dikembalikan server ketika retry request tiba saat status transaksi masih `STARTED`?

---

### Skenario B: Crash Massal Mobile App Akibat Kontrak Data Pecah (Breaking Changes)
**Konteks Insiden:**  
Tim backend merilis update microservice katalog. Untuk menyamakan standardisasi internal, mereka mengubah format respons:
* Mengganti penamaan field dari `snake_case` (`user_address`) ke `camelCase` (`userAddress`).
* Mengubah tipe data field `price` dari integer representasi sen/rupiah terkecil (`1500000`) menjadi string format desimal (`"15000.00"`).
* Menghapus field `status` yang dianggap redundan dan menggantinya dengan enum array `lifecycle_flags`.

Dalam 15 menit pasca rilis, 40% pengguna aplikasi Android versi lawas mengalami crash instan (*Fatal Exception: NullPointerException / JsonParseException*) saat membuka halaman utama. Rollback darurat terpaksa dilakukan.

**Pertanyaan Diagnostik:**
1. Bedah secara mendalam apa saja definisi *Backward Compatibility* dan *Forward Compatibility* dalam evolusi schema JSON.
2. Buat matriks klasifikasi: mana perubahan skema yang tergolong *Breaking Changes* versus *Non-Breaking Changes*.
3. Rancang strategi migrasi API zero-downtime untuk skenario di atas tanpa melakukan versioning URL baru (`/v2/catalog`) jika tim arsitek melarang URL path explosion. Evaluasi strategi via *Schema Dual-Writing*, *Header-based Versioning*, atau *Deprecation Header Policies* (RFC 8594).

---

### Skenario C: N+1 Network Cascade dan Sub-resource Explosion
**Konteks Insiden:**  
Frontend Web Dashboard SPA memuat data monitoring pesanan. Untuk menampilkan sebuah tabel berisi 50 transaksi, browser terpaksa memanggil:
* 1x call ke `GET /orders?limit=50`
* 50x parallel calls ke `GET /orders/{id}/items`
* 50x parallel calls ke `GET /customers/{id}`
* 50x parallel calls ke `GET /shipments/{tracking_id}`

Total 151 HTTP requests per page load memicu Network Throttling pada browser, HTTP/1.1 Head-of-Line Blocking, serta lonjakan CPU di API Gateway. Tim frontend meminta backend membuat satu endpoint sapu jagat: `GET /dashboard-data` yang mengembalikan seluruh data mentah dari database.

**Pertanyaan Diagnostik:**
1. Mengapa menyetujui endpoint monolitik `GET /dashboard-data` merusak integritas arsitektur RESTful jangka panjang (anti-pattern *API as Database Dump*)?
2. Bagaimana Anda merancang kontrak data RESTful yang elegan untuk menyelesaikan masalah ini tanpa membuang arsitektur resource-oriented? Jelaskan implementasi pola *Resource Embedding / Expansion* (misal: `?include=items,customer,shipment`) dan *Sparse Fieldsets* (misal: `?fields[orders]=id,total&fields[customer]=name`).
3. Dari perspektif alokasi resource database, indeks dan optimasi query apa yang wajib diintegrasikan pada backend agar dynamic resource expansion ini tidak memicu SQL N+1 Query Problem di storage engine Anda?

---

## 4. Chapter Challenge

### Tantangan Praktis: Desain Kontrak Data & Engine RESTful "Core Fulfillment API"

#### Deskripsi Problem
Anda ditunjuk sebagai Lead Backend Architect untuk membangun sistem *Fulfillment & Inventory Mutation* berstandar perbankan/enterprise di platform logistik multi-tenant. Sistem ini sering mengalami degradasi jaringan dari kurir lapangan, potensi race condition double-scan paket barang, serta kebutuhan integrasi pihak ketiga yang sangat kaku. Anda diwajibkan mendesain spesifikasi kontrak API dan logic engine penanganannya.

#### Requirements
1. **Spesifikasi OpenAPI 3.1 (Schema Design):**
   * Rancang kontrak endpoint mutasi inventaris paket:
     `POST /v1/warehouses/{warehouse_id}/parcels/{parcel_id}/transitions`
   * Kontrak harus mendukung transisi status paket (misal: `RECEIVED` -> `SORTING` -> `OUT_FOR_DELIVERY` -> `DELIVERED`).
   * Desain payload request yang mendukung idempotensi, metadata koordinat geolokasi, dan validasi array barang di dalam paket.
   * Definisikan kontrak respons lengkap: skenario sukses (`200 OK` / `201 Created`), skenario konflik transisi (`409 Conflict`), skenario entitas terkunci/sedang diproses (`423 Locked` atau `400`), dan validasi input (`422 Unprocessable Entity`).
2. **Standardisasi Error Sesuai RFC 7807:**
   * Buat struktur schema JSON representasi error ketika kurir mencoba mengubah status paket yang sudah `DELIVERED` menjadi `SORTING` (transisi ilegal). Payload harus menyertakan kode error domain spesifik, timestamp, correlation tracing ID, dan invalid parameter pointers.
3. **Desain Kontrak Keyset Pagination:**
   * Rancang kontrak `GET /v1/warehouses/{warehouse_id}/parcels` yang menggunakan cursor pagination.
   * Sertakan parameter `cursor`, `limit`, `sort_by`, dan `sort_direction`.
   * Format metadata respons harus menyediakan pointer cursor untuk halaman berikutnya (`next_cursor`) tanpa mengekspos raw database auto-increment ID ke publik secara telanjang.
4. **Conditional Update Contract:**
   * Tentukan bagaimana endpoint `PATCH /v1/warehouses/{warehouse_id}/parcels/{parcel_id}` memanfaatkan header `If-Match` dan respons header `ETag` untuk mencegah overwrite data antar dua admin logistik.

#### Constraints
* Tidak boleh menggunakan tipe data ambigu (seperti field `data: any` atau field tanpa validasi eksplisit).
* Format penamaan field wajib konsisten: `snake_case` untuk JSON keys, `kebab-case` untuk HTTP Headers.
* Seluruh representasi waktu wajib mematuhi standar ISO 8601 dengan timezone offset eksplisit (UTC: `YYYY-MM-DDTHH:mm:ssZ`).
* Nilai uang/biaya (jika ada) tidak boleh menggunakan representasi floating point; gunakan representasi integer currency unit terkecil atau decimal string pattern.

#### Expected Output
* File spesifikasi OpenAPI 3.1 (dapat berupa potongan file valid YAML/JSON) yang merepresentasikan endpoint mutasi dan query di atas.
* Dokumen *Architecture Decision Record (ADR)* singkat (maksimal 300 kata) yang menjelaskan rasionalisasi penanganan idempotency state machine dan mitigasi *out-of-order execution* pada sistem delivery ini.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Batasan arsitektur REST menurut disertasi Roy Fielding (termasuk *Statelessness*, *Client-Server*, *Cacheable*, *Layered System*, dan *Uniform Interface*).
- [ ] Perbedaan matematis dan implementasi jaringan antara Safe Methods (`GET`, `HEAD`, `OPTIONS`) dan Idempotent Methods (`PUT`, `DELETE`).
- [ ] Alur teknis conditional requests menggunakan header HTTP (`ETag`, `If-Match`, `If-None-Match`, `Last-Modified`, `If-Modified-Since`).
- [ ] Kapan harus menggunakan HTTP Status Code secara presisi (termasuk `200`, `201`, `202`, `204`, `400`, `401`, `403`, `404`, `409`, `422`, `429`, `500`, `502`, `503`, `504`).
- [ ] Mekanisme parsing JSON Patch (RFC 6902) versus JSON Merge Patch (RFC 7386).
- [ ] Kelemahan Offset-based pagination pada tabel masif dan keunggulan matematis/indeks dari Cursor-based (Keyset) pagination.
- [ ] Aturan evolusi skema data (Backward and Forward Compatibility) serta risiko Breaking Changes.

### Saya tidak perlu menghafal:
- [ ] Seluruh nomor kode status HTTP yang eksotik dan jarang digunakan (misal: RFC 2324 `418 I'm a teapot`, status kode WebDAV kompleks seperti `424 Failed Dependency`), cukup simpan cheatsheet spesifikasi IANA/MDN.
- [ ] Spesifikasi sintaksis OpenAPI 3.1 secara baris demi baris di luar kepala; fokuslah pada pemahaman relasi skema, referensi (`$ref`), dan tipe datanya. Generator tools/GUI dapat digunakan untuk syntax scaffold.
- [ ] Header HTTP eksperimental non-standar yang sudah deprecated (seperti `X-XSS-Protection` atau vendor-specific headers lama).

### Saya harus bisa melakukan:
- [ ] Menulis spesifikasi OpenAPI 3.0/3.1 (Swagger) yang valid, bersih, modular, dan dapat dikonsumsi oleh tool automation (code generator, mock server).
- [ ] Mengimplementasikan validasi input yang ketat pada layer transport backend dan memetakan kegagalan validasi ke format RFC 7807 (Problem Details).
- [ ] Merancang arsitektur idempotency layer menggunakan Redis/Database untuk mengamankan endpoint non-idempotent (`POST`) dari network retry loop.
- [ ] Menganalisis log akses API dan payload HTTP klien untuk mendiagnosis insiden integrasi data atau contract mismatch tanpa melihat source code klien.
- [ ] Mendesain skema endpoint RESTful yang ramah performa database, mencegah query N+1 dengan pola embedding resource yang terkontrol.