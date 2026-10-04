---
[⬅️ BAB 02 Quiz & Challenge](../BAB-02-Bahasa-Pemrograman-dan-Runtime-Execution/BAB-02-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: gRPC, Protobuf, & GraphQL N+1 ➡️](./Module-02-gRPC-Protobuf-dan-GraphQL-N-Plus-One-Problem.md)
---

# Module 01: Desain RESTful API Enterprise, Richardson Maturity Model, & Idempotency

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik mampu:
- Menguasai 6 prinsip arsitektur **Representational State Transfer (REST)** yang dirumuskan oleh Roy Fielding.
- Menerapkan **Richardson Maturity Model** dari Level 0 hingga Level 3 (**HATEOAS** - *Hypermedia as the Engine of Application State*).
- Menentukan metode HTTP yang tepat (**GET**, **POST**, **PUT**, **PATCH**, **DELETE**) dan membedakan konsep **Safe Methods** vs **Idempotent Methods**.
- Merancang struktur kode status HTTP (**HTTP Status Codes 2xx, 3xx, 4xx, 5xx**) yang ekspresif, terstandarisasi, dan ramah mesin.
- Mengimplementasikan pola ketahanan **Enterprise Idempotency Pattern** menggunakan header `Idempotency-Key` dan distributed cache guna mencegah pendebitan ganda pada transaksi pembayaran.
- Membandingkan strategi pembuatan versi API (**API Versioning**) dan memilih model paginasi yang tepat (**Offset-based** vs **Cursor-based / Keyset Pagination**).

---

## 2. Prerequisite
- Memahami protokol HTTP/1.1 dan HTTP/2 (Bab 01).
- Pemahaman format serialisasi data JSON (*JavaScript Object Notation*).
- Konsep dasar operasi CRUD (Create, Read, Update, Delete) pada database.

---

## 3. Concept
REST (*Representational State Transfer*) bukanlah protokol atau framework, melainkan **gaya arsitektur perangkat lunak** yang memanfaatkan protokol HTTP secara murni dan elegan.
Banyak developer mengklaim telah membangun "REST API" hanya karena mereka membuat endpoint URL yang mengembalikan data berformat JSON, padahal mereka menggunakan metode `POST /getUser` atau `POST /deleteUser`. Ini bukanlah REST, melainkan RPC buruk (*The Swamp of POX - Plain Old XML/JSON*).

Dalam REST sejati:
- **URI merepresentasikan Sumber Daya (Noun / Kata Benda)**: `/api/v1/orders`, bukan kata kerja.
- **HTTP Method merepresentasikan Aksi (Verb)**: `GET` (baca), `POST` (buat baru), `PUT` (ganti utuh), `PATCH` (modifikasi parsial), `DELETE` (hapus).
- **HTTP Status Code merepresentasikan Hasil**: `200 OK`, `201 Created`, `204 No Content`, `400 Bad Request`, `404 Not Found`, `409 Conflict`.

```
+-----------------------------------------------------------------------------------+
|                        RICHARDSON MATURITY MODEL OF REST                          |
|                                                                                   |
|  [ LEVEL 3: HATEOAS ]                                                             |
|    Merespons dengan data + link navigasi aksi berikutnya (rel="pay", rel="cancel")|
|                               ^                                                   |
|  [ LEVEL 2: HTTP VERBS & STATUS CODES ]                                           |
|    Menggunakan GET, POST, PUT, DELETE + Status 200, 201, 404, 409 secara tepat   |
|                               ^                                                   |
|  [ LEVEL 1: RESOURCES (URI Identifiers) ]                                         |
|    Memetakan URL ke entitas kata benda: /orders/123, /users/45/payments           |
|                               ^                                                   |
|  [ LEVEL 0: THE SWAMP OF POX ]                                                    |
|    Satu endpoint tunggal POST /api/service yang melayani semua aksi (Model RPC)   |
+-----------------------------------------------------------------------------------+
```

---

## 4. Why?
Mengapa desain RESTful API yang matang sangat penting bagi backend enterprise?
1. **Prediktabilitas & Developer Experience (DX)**: Developer mobile app atau integrasi merchant pihak ketiga tidak perlu menebak nama fungsi atau format error jika API mematuhi standar HTTP global.
2. **Skalabilitas Caching HTTP**: Dengan memanfaatkan metode `GET` dan header `Cache-Control` / `ETag`, gateway CDN (Cloudflare/Akamai) dapat melayani jutaan request langsung dari edge tanpa membebani database backend Anda.
3. **Mencegah Bencana Finansial (Idempotency)**: Jika koneksi jaringan pengguna terputus sesaat setelah menekan tombol "Bayar Sekarang", aplikasi mobile akan me-retry request secara otomatis. Tanpa desain *Idempotency*, saldo rekening pengguna akan terpotong dua kali (*double debit*).

---

## 5. What?

### A. Matriks Safe vs Idempotent Methods
- **Safe Method**: Pemanggilan endpoint TIDAK MENGUBAH state sumber daya di server sama sekali (*read-only*).
- **Idempotent Method**: Memanggil endpoint 1 kali atau 1.000 kali dengan parameter yang sama akan menghasilkan **keadaan akhir (*final state*) yang sama persis** di server.

| HTTP Method | Safe? | Idempotent? | Semantik Semantik Operasi |
|---|---|---|---|
| **GET** | **YA** | **YA** | Membaca data tanpa efek samping. |
| **HEAD** | **YA** | **YA** | Mengambil metadata header saja (tanpa body). |
| **OPTIONS** | **YA** | **YA** | Menanyakan metode dan CORS yang diizinkan server. |
| **PUT** | TIDAK | **YA** | Mengganti *seluruh* representasi objek. Jika diulang berkali-kali, state akhir tetap sama. |
| **DELETE** | TIDAK | **YA** | Menghapus sumber daya. Pemanggilan ke-2 menghasilkan state objek tetap terhapus (mengembalikan 204 atau 404). |
| **POST** | TIDAK | **TIDAK** | Membuat sumber daya baru atau memproses transaksi. Pemanggilan 2x membuat 2 objek baru (*non-idempotent*). |
| **PATCH** | TIDAK | **KONDISIONAL** | Modifikasi parsial. Idempotent jika `{"status": "PAID"}`, non-idempotent jika `{"counter": counter + 1}`. |

### B. Standardisasi Error Format: RFC 7807 (Problem Details)
Hindari mengembalikan format error acak seperti `{ "error": "Something went wrong" }`. Gunakan standar resmi IETF **RFC 7807**:

```json
{
  "type": "https://api.perusahaan.com/errors/insufficient-funds",
  "title": "Saldo Tidak Mencukupi",
  "status": 422,
  "detail": "Saldo rekening Rp 25.000 tidak mencukupi untuk penarikan sebesar Rp 50.000.",
  "instance": "/v1/transfers/tr-998231",
  "invalid_params": [
    { "name": "amount", "reason": "Melebihi saldo efektif rekening" }
  ]
}
```

### C. Strategi Paginasi: Offset vs Cursor-Based

| Karakteristik | Offset-Based (`?page=2&limit=20`) | Cursor-Based (`?after=c2VjcmV0...&limit=20`) |
|---|---|---|
| **Mekanisme SQL** | `LIMIT 20 OFFSET 1000000` | `WHERE id > 1000000 ORDER BY id ASC LIMIT 20` |
| **Performa pada Data Besar** | **Sangat Lambat ($O(N)$)**: Database harus memindai 1 juta baris sebelum membuangnya | **Ultra Cepat ($O(1)$)**: Langsung melompat via B-Tree Index |
| **Konsistensi Data Real-time** | Rawan bug loncat baris jika ada data baru masuk saat user paging | **Konsisten 100%**: Tidak ada duplikasi atau baris terlewat |
| **Kemampuan Lompat Halaman** | Bisa lompat langsung ke "Halaman 50" | Hanya bisa navigasi "Next" dan "Previous" |
| **Rekomendasi Use Case** | Dashboard internal data kecil (< 1.000 baris) | Infinite scroll social media, e-commerce, feed data raksasa |

---

## 6. How: Pola Idempotency Key Transaksi Keuangan

Untuk membuat endpoint `POST /v1/payments` menjadi idempoten:
1. Client menyematkan UUID unik di header: `Idempotency-Key: 7b83f4d0-1c09-4e52-a589-9e8c4599a012`.
2. Backend menerima request dan memeriksa key tersebut di Redis:
   - **Kasus A (Key Belum Ada)**: Pasang lock atomik di Redis dengan TTL 24 jam (`SET key "IN_PROGRESS" NX EX 86400`). Proses transaksi database, simpan respons final di Redis, dan kembalikan HTTP `201 Created`.
   - **Kasus B (Key Sudah Ada & Status IN_PROGRESS)**: Berarti ada request paralel identik yang sedang berjalan. Kembalikan HTTP `409 Conflict` (*Request in progress, please wait*).
   - **Kasus C (Key Sudah Ada & Status COMPLETED)**: Ambil respons tersimpan dari Redis dan langsung kembalikan ke client tanpa menyentuh database atau mendebit uang kembali!

```
CLIENT                                  BACKEND SERVER                      REDIS CACHE
  |                                           |                                  |
  | -- POST /payments (Idempotency-Key: K1) ->|                                  |
  |                                           | -- SET K1 "IN_PROGRESS" NX ----> |
  |                                           |<-- OK (Lock Acquired) ---------- |
  |                                           |                                  |
  |                                           | [ Eksekusi Debit Database ]      |
  |                                           |                                  |
  |                                           | -- SET K1 {"status":"PAID"} ---> |
  |<-- HTTP 201 Created {"id": "PAY-1"} ------|                                  |
  |                                           |                                  |
  | (Koneksi putus! Client me-retry request)  |                                  |
  |                                           |                                  |
  | -- POST /payments (Idempotency-Key: K1) ->|                                  |
  |                                           | -- GET K1 ---------------------> |
  |                                           |<-- Return {"status":"PAID"} ---- |
  |                                           |                                  |
  |<-- HTTP 200 OK {"id": "PAY-1"} (CACHED)---| (Zero DB Hits! No Double Debit!) |
```

---

## 7. Analogy
Bayangkan **Tombol Lift di Gedung Pencakar Langit**:
- **Idempotent (Tombol Lantai 10)**: Anda menekan tombol "Lantai 10" satu kali. Lift bergerak menuju lantai 10. Jika anak kecil di sebelah Anda menekan tombol "Lantai 10" sebanyak 20 kali berturut-turut, lift tetap menuju ke lantai 10. Keadaan akhir lift tidak berubah (**Idempotent**).
- **Non-Idempotent (Tombol Mesin ATM Setor Tunai)**: Setiap kali Anda menekan tombol "Setor Rp 100.000", mesin menarik uang tunai dari tangan Anda dan menambahkan saldo. Jika tombol ditekan 3 kali, uang Anda ditarik 3 kali (**Non-Idempotent**).
- **HATEOAS**: Seperti **Menu Otomatis di Layar ATM**. Setelah Anda memasukkan PIN, ATM tidak hanya menampilkan saldo, tetapi langsung menyediakan tombol pilihan langkah berikutnya: `[Tarik Tunai]`, `[Transfer]`, `[Bayar Tagihan]`. Anda tidak perlu menghafal menu apa yang tersedia; server memandu langkah navigasi Anda secara dinamis.

---

## 8. Diagram: Richardson Maturity Model & HATEOAS Response

```
+---------------------------------------------------------------------------------+
|                       HATEOAS JSON RESPONSE EXAMPLE                             |
+---------------------------------------------------------------------------------+

HTTP/1.1 200 OK
Content-Type: application/vnd.bank.account+json

{
  "account_id": "ACC-99021",
  "holder_name": "Budi Santoso",
  "balance": 15000000,
  "currency": "IDR",
  "status": "ACTIVE",
  "_links": {
    "self": {
      "href": "/v1/accounts/ACC-99021",
      "method": "GET"
    },
    "deposit": {
      "href": "/v1/accounts/ACC-99021/deposits",
      "method": "POST"
    },
    "transfer": {
      "href": "/v1/accounts/ACC-99021/transfers",
      "method": "POST"
    },
    "close": {
      "href": "/v1/accounts/ACC-99021/close",
      "method": "POST"
    }
  }
}
```

---

## 9. Simple Example: Cursor-Based Pagination Implementation

```javascript
// Contoh Endpoint Cursor-Based Pagination
app.get('/v1/transactions', async (req, res) => {
  const limit = parseInt(req.query.limit) || 20;
  const cursor = req.query.cursor ? Buffer.from(req.query.cursor, 'base64').toString('utf8') : null;

  // Query SQL efisien menggunakan B-Tree Index pada kolom 'id'
  // SELECT * FROM transactions WHERE id > cursor ORDER BY id ASC LIMIT limit + 1
  const items = await db.getTransactions({ afterId: cursor, limit: limit + 1 });

  let nextCursor = null;
  const hasMore = items.length > limit;
  if (hasMore) {
    const nextItem = items.pop(); // Hapus item ke-21
    nextCursor = Buffer.from(nextItem.id.toString()).toString('base64');
  }

  res.json({
    data: items,
    pagination: {
      limit: limit,
      next_cursor: nextCursor,
      has_more: hasMore
    }
  });
});
```

---

## 10. Practical Example: Implementasi Idempotency Middleware di Node.js

```javascript
const redisClient = require('./redis');

function idempotencyMiddleware(ttlSeconds = 86400) {
  return async (req, res, next) => {
    const idempotencyKey = req.headers['idempotency-key'];

    // Jika bukan metode mutasi atau tidak ada key, lewati
    if (req.method !== 'POST' || !idempotencyKey) {
      return next();
    }

    const cacheKey = `idempotency:${idempotencyKey}`;
    
    // 1. Cek apakah key sudah pernah diproses
    const cachedResponse = await redisClient.get(cacheKey);
    if (cachedResponse) {
      const parsed = JSON.parse(cachedResponse);
      if (parsed.status === 'IN_PROGRESS') {
        return res.status(409).json({
          error: "Conflict: Operasi dengan Idempotency-Key ini sedang diproses. Mohon tunggu."
        });
      }
      // Kembalikan respons yang pernah disimpan
      res.set('X-Cache-Lookup', 'HIT-IDEMPOTENT');
      return res.status(parsed.statusCode).json(parsed.body);
    }

    // 2. Kunci key dengan status IN_PROGRESS
    await redisClient.set(cacheKey, JSON.stringify({ status: 'IN_PROGRESS' }), 'EX', 60);

    // 3. Intercept res.json untuk menyimpan respons final ke Redis
    const originalJson = res.json.bind(res);
    res.json = (body) => {
      redisClient.set(cacheKey, JSON.stringify({
        status: 'COMPLETED',
        statusCode: res.statusCode,
        body: body
      }), 'EX', ttlSeconds);
      return originalJson(body);
    };

    next();
  };
}
```

---

## 11. Real World Example: Standar Idempotency API Stripe
Stripe memproses miliaran dolar volume pembayaran harian. Seluruh API `POST /v1/charges` dan `POST /v1/refunds` mereka mewajibkan atau menyarankan penyematan header `Idempotency-Key`.
- Jika bank merchant mengalami timeout jaringan selama 15 detik, SDK Stripe secara otomatis mencoba ulang request hingga 3 kali dengan Idempotency-Key yang sama.
- Server Stripe menjamin bahwa kartu kredit pelanggan **hanya didebit tepat satu kali**, dan token transaksi yang dikembalikan selalu konsisten.
- Jika pengguna mencoba mengirimkan Idempotency-Key yang sama namun dengan payload body yang berbeda (misal mengubah jumlah nominal uang), Stripe mendeteksi anomali ini dan mengembalikan `HTTP 400 Bad Request` (*Keys cannot be reused with different request parameters*).

---

## 12. Trade-offs

| Aspek Desain | Pendekatan A | Pendekatan B |
|---|---|---|
| **Versioning** | **URI Path (`/v1/users`)**: Sangat transparan, mudah di-cache oleh CDN | **Header (`Accept: application/vnd.v1+json`)**: URI bersih, namun sulit diuji di browser biasa |
| **Paginasi** | **Offset-based**: Mendukung lompat halaman bebas, namun lambat pada jutaan data | **Cursor-based**: Skalabilitas $O(1)$ tak terbatas, namun tidak bisa lompat halaman |
| **Maturity** | **Level 2 (HTTP Verbs & Status)**: Standar industri paling umum, praktis | **Level 3 (HATEOAS)**: Benar-benar decoupled, namun ukuran payload membengkak oleh link |
| **Payload Update** | **PUT (Full Replace)**: Semantik jelas, namun boros bandwidth jika hanya ubah 1 kolom | **PATCH (Partial)**: Hemat bandwidth, namun validasi schema parsial lebih rumit |

---

## 13. When To Use
- Selalu gunakan **Cursor-based Pagination** untuk tabel transaksi, log audit, feed pesan, dan seluruh koleksi data yang bertumbuh di atas 100.000 baris.
- Wajibkan header **`Idempotency-Key`** pada seluruh endpoint mutasi finansial (transfer dana, pembayaran invoice, pemesanan tiket).
- Terapkan standar **RFC 7807** untuk seluruh payload respons error di organisasi Anda.

---

## 14. When NOT To Use
- **JANGAN** menggunakan metode `GET` untuk aksi yang memiliki efek samping mengubah database (seperti `GET /users/delete?id=5`), karena web crawler dan browser pre-fetching dapat menghapus data Anda secara tidak sengaja.
- Jangan mengembalikan kode status `HTTP 200 OK` jika di dalam body terdapat error: `{ "status": 200, "error": "User not found" }`. Ini adalah anti-pattern fatal yang merusak arsitektur monitoring HTTP dan load balancer.

---

## 15. Common Mistakes
1. **Mengabaikan Idempotency pada Tombol Checkout**: Pengguna melakukan double-click pada tombol "Beli", menghasilkan dua request `POST` bersamaan yang lolos membuat 2 pesanan ganda.
2. **Menyalahartikan PUT dan PATCH**: Menggunakan `PUT` tetapi hanya mengirimkan satu field `{ "email": "new@mail.com" }`, sehingga database menimpa field nama, telepon, dan alamat menjadi `NULL`.
3. **Mengabaikan Query Pagination Limit**: Endpoint `GET /api/v1/products` mengembalikan seluruh 500.000 produk sekaligus jika parameter `limit` tidak disematkan, memicu Out-of-Memory pada server Node.js.

---

## 16. Best Practices
- **Must Have**: Validasi dan batasi parameter pagination: tetapkan `default_limit: 20` dan `max_limit: 100`.
- **Recommended**: Pasang header `ETag` pada respon `GET` agar client dapat melakukan kondisional caching menggunakan `If-None-Match` (mengembalikan `304 Not Modified` tanpa transfer body).
- **Advanced**: Implementasikan validasi *Payload Fingerprint* pada Idempotency Key: simpan SHA-256 dari request body untuk mendeteksi penggunaan ulang key dengan parameter berbeda.
- **Avoid**: Menempatkan kata kerja di URI (hindari `/create-user`, `/delete-order`, `/update-status`).

---

## 17. Troubleshooting Guide
```
Masalah: Client mendapatkan error "HTTP 409 Conflict" saat memanggil endpoint pembayaran dengan Idempotency-Key.
Penyebab : Request sebelumnya dengan key yang sama masih sedang diproses di worker backend (koneksi database lambat).
Diagnosa : Periksa status key di Redis: redis-cli GET idempotency:<key>
Solusi   : Client harus menerapkan Exponential Backoff dan mencoba kembali setelah 1-2 detik hingga status berubah menjadi COMPLETED.

Masalah: Pagination Offset lambat parah pada page 50000 (Query memakan waktu 12 detik).
Penyebab : PostgreSQL/MySQL memindai 1.000.000 baris B-Tree index dan membaca data ke disk sebelum membuang 999.980 baris.
Diagnosa : EXPLAIN ANALYZE SELECT * FROM orders LIMIT 20 OFFSET 1000000;
Solusi   : Migrasikan query ke Cursor-based pagination: WHERE id > :last_seen_id ORDER BY id ASC LIMIT 20.
```

---

## 18. Exercise
1. Desain struktur URI RESTful untuk entitas E-Commerce: Kategori, Produk, Ulasan Produk, dan Keranjang Belanja.
2. Tulis kontrak respons JSON untuk penambahan ulasan baru (`POST /products/12/reviews`) lengkap dengan status code 201 dan header `Location`.
3. Tulis representasi RFC 7807 jika pengguna mencoba memberikan rating bintang 6 (invalid parameter).

---

## 19. Challenge
Rancang arsitektur Idempotency Engine terdistribusi berskala enterprise yang mampu menangani **50.000 transaksi per detik**:
1. Gunakan Redis Cluster dengan penanganan failover sentinel.
2. Tangani skenario *Race Condition* di mana dua request dengan Idempotency-Key yang sama tiba di dua instance server backend berbeda pada milidetik yang sama (*Redis atomic SETNX with Lua script*).
3. Rancang strategi pembersihan TTL otomatis untuk mencegah membengkaknya memori Redis. Tuliskan pseudocode implementasinya!

---

## 20. Summary
Merancang RESTful API kelas enterprise bukan sekadar mengembalikan data JSON melalui HTTP, melainkan mengorkestrasikan semantik metode, pemetaan sumber daya, kode status standar, pagination berbasis kursor yang terukur, serta penegakan idempotensi yang kokoh. Penguasaan fondasi ini mutlak diperlukan sebelum membandingkannya dengan paradigma alternatif seperti gRPC dan GraphQL pada modul berikutnya.

---
[⬅️ BAB 02 Quiz & Challenge](../BAB-02-Bahasa-Pemrograman-dan-Runtime-Execution/BAB-02-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: gRPC, Protobuf, & GraphQL N+1 ➡️](./Module-02-gRPC-Protobuf-dan-GraphQL-N-Plus-One-Problem.md)
---
