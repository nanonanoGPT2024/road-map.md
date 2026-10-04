---
[⬅️ Module 01: API Fundamentals & HTTP](./Module-01-Fondasi-API-Testing-HTTP-Status-Codes-Headers.md) | [📋 Silabus Induk](../README.md) | [Quiz & Challenge BAB 04 ➡️](./BAB-04-Quiz-dan-Challenge.md)
---

# Module 02: Otomasi Pengujian API: JSON Schema Validation, Contract Testing (Pact), & Mocking

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- Menguasai teknik validasi struktur respon otomatis menggunakan **JSON Schema (Draft-07 & 2020-12 standard)** untuk memastikan integritas tipe data, field wajib (*required*), format regex, dan batasan nilai numerik.
- Mencegah fenomena **Schema Drift** dan *Contract Regression* pada arsitektur Microservices menggunakan filosofi **Consumer-Driven Contract Testing (CDC / Pact)**.
- Menerapkan teknik **Mocking & Service Virtualization** untuk mengisolasi pengujian API dari ketergantungan pihak ketiga (*third-party dependencies* seperti Payment Gateway, SMS OTP, atau Layanan Logistik).
- Melakukan pengujian keamanan dan ketahanan API lanjutan: **Rate Limiting & Throttling (HTTP 429 Too Many Requests)** serta deteksi kerentanan **Broken Object Level Authorization (BOLA / IDOR)**.

---

## 2. Prerequisite
- Memahami protokol HTTP, status code, headers, dan idempotensi dari Module 01.
- Pemahaman struktur JSON dasar (object, array, string, integer, boolean).

---

## 3. Concept
Menguji API hanya dengan memeriksa HTTP Status Code (`200 OK`) dan mencocokkan satu nilai teks tertentu adalah pendekatan yang sangat rentan (*fragile*). Jika tim backend secara tidak sengaja mengubah tipe data ID dari `integer` menjadi `string`, atau menghapus field penting `totalAmount` dari payload, aplikasi mobile pengguna di produksi akan langsung crash seketika (*white screen of death*), meskipun status code-nya tetap `200 OK`.

Solusi standar industri untuk masalah ini adalah **JSON Schema Validation** dan **Contract Testing**. JSON Schema bertindak sebagai cetak biru (*blueprint*) deklaratif yang memvalidasi seluruh bentuk (*shape*), tipe data, dan aturan struktur data JSON. Sementara itu, Contract Testing menjamin bahwa penyedia layanan (*Provider*) tidak melanggar perjanjian kontrak yang diharapkan oleh konsumen (*Consumer*).

---

## 4. Why?
Mengapa kita wajib menerapkan JSON Schema dan Contract Testing?
1. **Menangkap "Silent Breaking Changes"**: Mencegah perubahan sepihak developer backend yang mengubah nama key JSON (misal `user_id` diubah menjadi `userId`), yang tidak terdeteksi oleh unit test backend namun merusak seluruh aplikasi mobile.
2. **Pengujian Tanpa Biaya Pihak Ketiga (Zero Cost Mocking)**: Setiap kali Anda memanggil sandbox payment gateway riil atau SMS OTP provider untuk pengujian regresi, biaya tagihan API atau kuota SMS terkuras. Service Virtualization memungkinkan pengujian 100% gratis, cepat, dan terisolasi.
3. **Penyelarasan Pengembangan Paralel (Frontend & Backend Decoupling)**: Berbekal kontrak data JSON Schema, tim QA dan Frontend dapat langsung membuat mock server dan menulis automation test tanpa perlu menunggu backend selesai dibuat.

---

## 5. What?

### A. Anatomi JSON Schema
JSON Schema mendefinisikan aturan ketat untuk struktur JSON:
- `type`: Tipe data (`object`, `array`, `string`, `number`, `integer`, `boolean`, `null`).
- `properties`: Kamus definisi properti/field di dalam objek.
- `required`: Daftar field yang **wajib ada** dalam respon.
- `additionalProperties: false`: Melarang adanya field tak dikenal yang tidak didefinisikan dalam spesifikasi (mencegah *Data Leakage*).
- `format`: Format string spesifik (`date-time`, `email`, `uri`, `uuid`).
- `minimum` / `maximum`: Batas rentang numerik.
- `enum`: Daftar nilai statis yang diizinkan.

---

### B. Consumer-Driven Contract Testing (Pact Philosophy)
Dalam arsitektur Microservices tradisional, pengujian integrasi E2E antar-puluhan service sangat lambat dan rapuh (*integration test hell*). 

**Consumer-Driven Contract Testing (CDC)** membalikkan paradigma:
1. **Consumer (Aplikasi Mobile / Frontend)** mendefinisikan kontrak: *"Saya membutuhkan endpoint `GET /users/1` mengembalikan minimal field `id` (integer) dan `fullName` (string)"*.
2. Kontrak ini diekspor ke dalam file kontrak formal (file JSON Pact).
3. **Provider (Backend Microservice)** menjalankan pengujian mandiri di pipeline CI/CD-nya untuk memverifikasi apakah kodenya memenuhi seluruh ekspektasi dalam file kontrak tersebut.
4. **Hasil**: Kedua service dapat dirilis secara independen dengan keyakinan 100% tanpa perlu menjalankan E2E environment raksasa yang mahal.

---

## 6. How? Menulis JSON Schema Validator Mandiri

### Contoh Spesifikasi Respon API User Profile:
```json
{
  "id": 10042,
  "username": "budi_qa",
  "email": "budi@testing.id",
  "role": "QA_ENGINEER",
  "rating": 4.8,
  "isActive": true
}
```

### JSON Schema Pendamping:
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["id", "username", "email", "role", "isActive"],
  "additionalProperties": false,
  "properties": {
    "id": { "type": "integer", "minimum": 1 },
    "username": { "type": "string", "pattern": "^[a-z0-9_]{3,20}$" },
    "email": { "type": "string", "format": "email" },
    "role": { "type": "string", "enum": ["ADMIN", "DEVELOPER", "QA_ENGINEER", "USER"] },
    "rating": { "type": "number", "minimum": 0, "maximum": 5 },
    "isActive": { "type": "boolean" }
  }
}
```

Jika server backend salah mengembalikan `id: "10042"` (string) atau `role: "SUPER_USER"` (di luar enum), JSON Schema validator akan melempar error kegagalan seketika!

---

## 7. Analogy
Bayangkan proses pengiriman paket logistik internasional:
- **Status Code 200**: Kurir sampai di gerbang rumah dan berkata paket berhasil diantar.
- **Tanpa JSON Schema**: Anda membuka kotak paket, dan ternyata di dalamnya bukan laptop yang Anda pesan, melainkan sebongkah batu bata (Server membalas 200 OK, tetapi datanya salah/hancur).
- **Dengan JSON Schema**: Ada petugas bea cukai di gerbang yang memeriksa bentuk fisik kotak, memindai barcode, menimbang berat tepat 2.5 kg, dan memeriksa label segel resmi sebelum paket boleh diserahkan kepada Anda.
- **Contract Testing (Pact)**: Nota kesepakatan tertulis antara pengirim dan penerima mengenai spesifikasi dimensi kotak yang tidak boleh diubah sepihak tanpa pemberitahuan.

---

## 8. Diagram

```text
========================================================================================
                 CONSUMER-DRIVEN CONTRACT TESTING (CDC) WORKFLOW
========================================================================================

   [ CONSUMER SIDE (Mobile App / Web) ]
             |
             v
   Tulis Unit Test Konsumen
             |
             v
   Hasilkan File Kontrak (pact.json)
             |
             +-----------------------+
                                     | Publish Contract
                                     v
                           [ PACT BROKER SERVER ]
                                     |
                                     | Download Contract
             +-----------------------+
             v
   [ PROVIDER SIDE (Backend API Service) ]
             |
             v
   Putar Ulang Request Kontrak ke Controller Nyata
             |
             +---------> [ Sesuai Kontrak? ]
                                |
                   +------------+------------+
                   |                         |
                 (YA)                      (TIDAK)
                   v                         v
           [ PASS CI Build ]         [ BREAK CI Build! ]
          (Aman untuk Rilis)      (Cegah Rilis ke Staging)
```

---

## 9. Simple Example: Skrip Validasi Skema JSON Minimalis

```javascript
function validateSchema(data, schema) {
  // Validasi tipe data induk
  if (schema.type && typeof data !== schema.type) {
    throw new Error(`Schema Violation: Expected type '${schema.type}', got '${typeof data}'`);
  }

  // Validasi field wajib
  if (schema.required) {
    for (const reqField of schema.required) {
      if (data[reqField] === undefined) {
        throw new Error(`Schema Violation: Missing required field '${reqField}'`);
      }
    }
  }

  // Validasi properti individu
  if (schema.properties) {
    for (const [key, propRule] of Object.entries(schema.properties)) {
      if (data[key] !== undefined) {
        if (propRule.type === "integer" && (!Number.isInteger(data[key]) || data[key] < (propRule.minimum || 0))) {
          throw new Error(`Field '${key}' must be an integer >= ${propRule.minimum || 0}`);
        }
        if (propRule.enum && !propRule.enum.includes(data[key])) {
          throw new Error(`Field '${key}' value '${data[key]}' not in allowed enum: [${propRule.enum.join(", ")}]`);
        }
      }
    }
  }
  return true;
}
```

---

## 10. Practical Example: Menguji Kerentanan API Broken Object Level Authorization (BOLA)

BOLA (atau IDOR) adalah kerentanan nomor 1 dalam daftar **OWASP API Security Top 10**. Terjadi ketika server tidak memverifikasi apakah pengguna yang meminta data benar-benar pemilik sah dari resource tersebut.

### Skenario Uji Otomasi BOLA:
```javascript
async function testBolaVulnerability(apiClient) {
  // 1. Login sebagai Korban (User A)
  const tokenA = await apiClient.login("victim@test.com", "passA");
  const profileA = await apiClient.getProfile(tokenA);
  const resourceIdA = profileA.walletId; // Wallet ID milik User A: "WAL-1001"

  // 2. Login sebagai Penyerang (User B)
  const tokenB = await apiClient.login("attacker@test.com", "passB");

  // 3. UJI PENETRASI: User B mencoba membaca dompet milik User A
  const response = await apiClient.getWallet(tokenB, resourceIdA);

  // EKSPEKTASI QA:
  // Server WAJIB menolak dengan HTTP 403 Forbidden atau 404 Not Found!
  if (response.status === 200) {
    throw new Error(
      `🚨 BOLA SECURITY VULNERABILITY FOUND! User B berhasil membaca data finansial User A!`
    );
  } else if (response.status === 403) {
    console.log("✓ BOLA Defense Valid: Server mengembalikan HTTP 403 Forbidden.");
  }
}
```

---

## 11. Real World Example: Crash Massal Aplikasi E-Commerce Akibat Perubahan Skema
Sebuah platform belanja online terbesar mengalami crash pada 100% pengguna aplikasi Android:
- **Penyebab**: Tim backend merilis update microservice katalog produk. Mereka mengganti field `discount_percentage` (tipe `integer`: contoh `20`) menjadi objek baru `{ "value": 20, "label": "20% OFF" }`.
- **Dampak**: Aplikasi mobile Java/Kotlin yang mengurai JSON menggunakan parser strongly-typed mengalami `JsonSyntaxException: Expected an int but was BEGIN_OBJECT`.
- Seluruh aplikasi force close seketika saat membuka halaman beranda.
- **Pencegahan**: Jika tim QA mengimplementasikan automated JSON Schema test atau Contract Test di CI/CD backend, perubahan destruktif ini akan memicu peringatan merah dan memblokir deployment sebelum sampai ke staging.

---

## 12. Trade-offs

| Pendekatan Pengujian API | Kelebihan | Kelemahan |
|---|---|---|
| **Simple Value Assertion (`res.body.name == 'X'`)** | Sangat cepat dibuat, intuitif. | Melewatkan perubahan tipe data, tidak memeriksa struktur field opsional. |
| **JSON Schema Validation** | Memvalidasi seluruh bentuk data secara komprehensif, standar ISO/RFC. | Perlu memelihara file schema saat ada perubahan fitur resmi. |
| **Contract Testing (Pact)** | Menjamin kompatibilitas antar-service tanpa perlu integrasi langsung. | Memerlukan kurva belajar tim dan infrastruktur Pact Broker. |
| **Full Live End-to-End Environment** | Menguji sistem paling riil. | Sangat lambat, mahal, rentan jaringan down, sulit setup data uji. |

---

## 13. When To Use
- Terapkan **JSON Schema Validation** pada seluruh endpoint publik dan response API penting di regression suite.
- Terapkan **Contract Testing (CDC)** pada organisasi yang memiliki arsitektur Microservices dengan tim independen yang terpisah.
- Terapkan **Mocking** untuk mensimulasikan skenario kegagalan langka yang sulit direproduksi di server nyata (misal: simulasi server payment gateway melempar HTTP 503 saat jam 2 malam).

## 14. When NOT To Use
- Jangan membuat Contract Testing yang rumit jika seluruh sistem berada dalam satu aplikasi monolitik kecil (*Monolith*) yang dikelola oleh 2 orang developer.
- Jangan memvalidasi field yang bernilai dinamis acak (seperti token hash unik) menggunakan kecocokan string statis; gunakan validasi regex pattern pada JSON Schema.

---

## 15. Common Mistakes

```text
1. MISTAKE: Tidak menyertakan aturan "additionalProperties: false" pada JSON Schema.
   WHY IT HAPPENS: Default JSON Schema mengizinkan properti tambahan tak terbatas.
   WHY IT IS BAD: Backend membocorkan kolom internal database sensitif (seperti password_hash atau salt) tanpa terdeteksi oleh validator QA.
   CORRECT APPROACH: Kunci skema dengan "additionalProperties: false" pada model data sensitif.

2. MISTAKE: Menggunakan Mocking untuk semua hal hingga tidak pernah menguji integrasi nyata.
   WHY IT HAPPENS: Malas mengelola test data di database staging.
   WHY IT IS BAD: Mock bisa saja mengembalikan data sukses palsu sementara sistem riil sudah rusak.
   CORRECT APPROACH: Padukan mock untuk pengujian komponen cepat dengan pengujian integrasi berkala.
```

---

## 16. Best Practices

### Must Have
- Validasi tipe data ketat dan deklarasi field wajib (*required*) pada setiap pengujian respon JSON.
- Pengujian pembatasan laju (*Rate Limiting / Throttling*) untuk mencegah serangan Denial-of-Service (DoS) pada endpoint publik.

### Recommended
- Menggunakan generator skema otomatis dari OpenAPI/Swagger specification untuk menghemat waktu penulisan manual.
- Memverifikasi skenario batas rate limit: Melakukan $N+1$ request cepat dan memastikan request ke-$N+1$ mengembalikan status **HTTP 429 Too Many Requests** lengkap dengan header `Retry-After`.

### Advanced
- Mengintegrasikan Pact verification step ke dalam pipeline CI/CD Pull Request: Jika sebuah PR melanggar kontrak Consumer yang aktif, PR ditolak secara otomatis (*Cannot deploy to production*).

### Avoid / Overengineering
- Menulis skema JSON sedalam 10 level bersarang untuk data log audit internal yang tidak pernah dikonsumsi oleh pengguna.

---

## 17. Troubleshooting: Mengatasi "Contract Verification Failure" di CI/CD
Jika verifikasi kontrak Pact gagal di pipeline backend:
1. **Penyebab**: Backend mengubah nama atribut atau menghapus field yang masih dibutuhkan oleh aplikasi mobile versi lama yang beredar di pasar.
2. **Solusi Backward Compatibility**: Terapkan pola *Expand and Contract*:
   - Pertahankan field lama dan tambahkan field baru secara bersamaan.
   - Depresiasi field lama secara bertahap setelah seluruh pengguna meng-upgrade aplikasi mobile.

---

## 18. Exercise
1. Tuliskan JSON Schema Draft-07 untuk memvalidasi respon transaksi pembayaran berikut:
   ```json
   {
     "transactionId": "TX-998812",
     "amount": 150000,
     "paymentStatus": "SUCCESS",
     "currency": "IDR",
     "settlementDate": "2026-09-11T16:00:00Z"
   }
   ```
   Aturan: `transactionId` harus berawalan "TX-", `amount` minimal 10.000, `paymentStatus` hanya boleh bernilai "SUCCESS", "PENDING", atau "FAILED", dan `settlementDate` berformat `date-time`.
2. Jelaskan langkah-langkah QA menguji bahwa mekanisme Rate Limiting API (maksimal 5 request per detik) bekerja dengan benar.

---

## 19. Challenge
Rancang sebuah **Contract Testing & API Security Suite** lengkap untuk arsitektur Microservices E-Commerce:
1. Definisikan kontrak JSON Pact antara Order Service (Consumer) dan Payment Service (Provider).
2. Rancang 1 skenario pengujian BOLA (IDOR) pada endpoint pembatalan pesanan: `POST /api/v1/orders/{orderId}/cancel`.
3. Rancang 1 skenario virtualisasi mock server yang mensimulasikan latensi jaringan 5 detik dan kegagalan HTTP 504 Gateway Timeout untuk memverifikasi mekanisme circuit-breaker di sisi klien.

---

## 20. Summary
- JSON Schema memberikan validasi deklaratif yang menjamin bahwa tipe data, format, dan struktur payload API selalu konsisten.
- Consumer-Driven Contract Testing (Pact) memecahkan masalah integrasi microservices dengan mengotomasi verifikasi ekspektasi antar-layanan di pipeline CI/CD.
- Mocking mengisolasi ketergantungan pihak ketiga dan memungkinkan simulasi skenario kegagalan ekstrem tanpa biaya.
- Pengujian keamanan API dasar wajib mencakup verifikasi BOLA (IDOR) dan penegakan batas laju panggilan (*Rate Limiting* 429).

---

## Hands-on Practice: Simulator JSON Schema Validator, Contract Mocking, & Rate Limiting
Jalankan script simulator yang mengimplementasikan mesin validasi JSON Schema mandiri, simulasi Consumer-Driven Contract testing, pengujian BOLA security check, dan demonstrasi respons 429 Rate Limiter:

```bash
node QA/BAB-04-Pengujian-API-dan-Validasi-Kontrak/hands-on/m02/contract_testing_mock_sim.js
```

---
[⬅️ Module 01: API Fundamentals & HTTP](./Module-01-Fondasi-API-Testing-HTTP-Status-Codes-Headers.md) | [📋 Silabus Induk](../README.md) | [Quiz & Challenge BAB 04 ➡️](./BAB-04-Quiz-dan-Challenge.md)
---
