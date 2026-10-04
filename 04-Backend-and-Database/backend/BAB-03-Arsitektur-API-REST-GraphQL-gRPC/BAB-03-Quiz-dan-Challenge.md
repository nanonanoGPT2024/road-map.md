---
[⬅️ Module 02: gRPC, Protobuf, & GraphQL N+1](./Module-02-gRPC-Protobuf-dan-GraphQL-N-Plus-One-Problem.md) | [📋 Silabus Induk](../README.md) | [BAB 04 Module 01: Relational Modeling & ACID ➡️](../BAB-04-RDBMS-dan-SQL-Mastery/Module-01-Relational-Modeling-ACID-dan-Isolation-Levels.md)
---

# BAB 03: Arsitektur API: RESTful, GraphQL, & gRPC — Quiz & Chapter Challenge

Dokumen ini berisi pengujian pemahaman konseptual, analisis skenario arsitektur integrasi API enterprise, serta tantangan implementasi sistematis untuk BAB 03.

---

## Bagian 1: Quiz Konseptual Dasar (5 Soal)

### Soal 1
Manakah tingkatan tertinggi (Level 3) dalam Richardson Maturity Model untuk REST API yang benar-benar membedakan REST sejati dari RPC sederhana?
- A. Penggunaan protokol HTTPS port 443.
- B. HATEOAS (*Hypermedia as the Engine of Application State*), di mana server merespons data disertai tautan hipermedia (*hyperlinks*) yang memandu client ke aksi berikutnya yang sah.
- C. Penggunaan database PostgreSQL berkecepatan tinggi.
- D. Mengubah seluruh format respon menjadi biner gRPC.

### Soal 2
Dari metode HTTP berikut, manakah kelompok metode yang tergolong **Idempotent** menurut spesifikasi RFC HTTP standar?
- A. `POST`, `PATCH`
- B. `GET`, `PUT`, `DELETE`, `HEAD`, `OPTIONS`
- C. `POST`, `CONNECT`, `TRACE`
- D. Hanya `GET` yang idempoten.

### Soal 3
Mengapa penomoran tag biner (`= 1`, `= 2`) pada skema Protocol Buffers (Protobuf) tidak boleh diubah atau ditukar setelah dirilis ke lingkungan produksi?
- A. Akan menyebabkan compiler Go menghapus file sumber kode.
- B. Protobuf tidak mengirimkan nama field teks (seperti "amount") di kabel jaringan, melainkan menyematkan nomor tag biner tersebut; mengubah nomor tag akan merusak kompatibilitas biner (*breaking backward/forward compatibility*), menyebabkan client membaca field yang salah.
- C. Cloudflare akan memblokir domain secara permanen.
- D. Nilai tag biner digunakan untuk menghitung tagihan cloud.

### Soal 4
Apa akar penyebab teknis dari **GraphQL N+1 Query Problem** pada implementasi resolver default?
- A. Server GraphQL kehabisan RAM saat mem-parsing skema SDL.
- B. GraphQL mengeksekusi fungsi resolver secara rekursif dan terisolasi untuk setiap item child, sehingga mengambil 1 list induk berisi $N$ baris akan memicu $N$ query SQL terpisah ke database untuk mengambil data relasinya.
- C. Database PostgreSQL menolak query yang memiliki lebih dari 1 relasi foreign key.
- D. Penggunaan port HTTP yang salah pada Apollo Server.

### Soal 5
Bagaimana pola **DataLoader** menyelesaikan N+1 Problem pada GraphQL?
- A. Menghapus seluruh relasi antar tipe di skema GraphQL.
- B. Menampung seluruh request identitas (IDs) yang masuk selama 1 tick event loop tunggal (*batching*), lalu mengeksekusi tepat 1 query SQL gabungan `WHERE id IN (...)` ke database dan mendistribusikan hasilnya kembali ke masing-masing promise.
- C. Mengonversi database SQL menjadi file teks CSV.
- D. Membatasi jumlah user yang boleh memanggil API maksimal 1 orang.

---

## Bagian 2: Quiz Skenario & Troubleshooting Tingkat Menengah (5 Soal)

### Soal 6
Pengguna mengeluh bahwa saldo rekening mereka terpotong dua kali (*double debit*) saat melakukan transfer uang karena sinyal ponsel terputus sesaat setelah menekan tombol "Kirim", dan aplikasi mobile secara otomatis melakukan retry request.
Solusi arsitektur backend manakah yang paling tepat dan terstandarisasi untuk mencegah terulangnya insiden ini?
- A. Menghapus tombol retry di aplikasi mobile.
- B. Menerapkan pola **Idempotency Key Middleware** pada endpoint `POST /v1/transfers`, di mana client menyematkan UUID unik di header, dan server memvalidasi via distributed lock (Redis) agar eksekusi debit hanya dilakukan tepat satu kali.
- C. Mengubah metode `POST` menjadi `GET`.
- D. Menurunkan batas maksimal transfer harian menjadi Rp 10.000.

### Soal 7
Tabel transaksi Anda memiliki 15.000.000 baris data. Saat dashboard admin memuat halaman ke-50.000 menggunakan endpoint `GET /transactions?page=50000&limit=20`, query database memakan waktu hingga 14 detik dan server mengalami lonjakan CPU.
Strategi paginasi apa yang harus diterapkan untuk memangkas latensi query tersebut menjadi di bawah 5 milidetik ($O(1)$)?
- A. Memperbesar RAM server database dari 32GB menjadi 256GB.
- B. Mengganti Offset-based pagination dengan **Cursor-based / Keyset Pagination** (`WHERE id > :last_seen_id ORDER BY id ASC LIMIT 20`) memanfaatkan B-Tree index.
- C. Menghapus 14 juta baris data transaksi lama.
- D. Mengubah format respon dari JSON menjadi XML.

### Soal 8
Anda sedang merancang sistem komunikasi internal antara 40 microservices di dalam cluster Kubernetes perbankan yang melayani 200.000 panggilan antar-layanan per detik. Tim Anda mempertimbangkan antara REST (JSON) vs gRPC (Protobuf).
Faktor teknis manakah yang menjadi alasan utama memilih **gRPC** untuk kebutuhan komunikasi internal (*East-West traffic*) ini?
- A. gRPC lebih mudah diuji menggunakan browser Safari daripada REST.
- B. gRPC berjalan di atas HTTP/2 dengan serialisasi biner Protobuf yang memangkas beban CPU parsing teks hingga 70%, ukuran paket kawat jauh lebih padat, dan mendukung kontrak tipe data kuat otomatis (*auto-generated SDK*).
- C. gRPC tidak memerlukan penulisan kode unit test.
- D. REST tidak dapat dijalankan di dalam container Docker.

### Soal 9
Klien frontend mengirimkan request pembaruan sebagian data profil pengguna:
`PATCH /v1/users/45` dengan body `{"phone_number": "08123456789"}`.
Namun, developer backend mengimplementasikan fungsi tersebut menggunakan query SQL:
`UPDATE users SET name = NULL, email = NULL, phone_number = '08123456789' WHERE id = 45;`, sehingga nama dan email pengguna terhapus.
Kesalahan pemahaman semantik HTTP apakah yang terjadi di sini?
- A. Developer menyalahartikan semantik `PATCH` (modifikasi parsial) sebagai semantik `PUT` (penggantian representasi sumber daya secara utuh).
- B. Metode `PATCH` tidak diizinkan mengubah nomor telepon.
- C. Database PostgreSQL tidak mendukung perintah UPDATE parsial.
- D. Client seharusnya menggunakan metode `DELETE`.

### Soal 10
Penyerang mengirimkan query GraphQL berikut ke endpoint publik Anda:
```graphql
query MaliciousQuery {
  user {
    friends {
      friends {
        friends {
          friends {
            friends {
              name
            }
          }
        }
      }
    }
  }
}
```
Query ini menyebabkan server backend Anda mengalami CPU 100% dan kehabisan memori (*Denial of Service*). Pengamanan GraphQL apakah yang wajib dipasang di layer API Gateway untuk menggagalkan serangan ini?
- A. Mengubah port server dari 4000 menjadi 8080.
- B. Mengimplementasikan **Query Depth Limiting** (membatasi kedalaman nesting maksimal, misal 4 tingkat) dan **Query Complexity Analysis**.
- C. Mewajibkan pengguna menggunakan browser Google Chrome.
- D. Menonaktifkan protokol TCP.

---

## Bagian 3: Skenario Kasus Arsitektur Tingkat Lanjut (3 Soal)

### Skenario 1: Hybrid API Gateway Architecture (North-South vs East-West)
Perusahaan fintech Unicorn Anda memiliki:
- 5.000.000 pengguna mobile (Android & iOS).
- 80 microservices internal yang berjalan di Kubernetes.
Rancang arsitektur API Gateway terpadu:
1. Protokol apa yang digunakan untuk komunikasi dari Mobile App ke API Gateway (*North-South*)? Berikan justifikasi teknisnya.
2. Protokol apa yang digunakan untuk komunikasi antar microservice di belakang API Gateway (*East-West*)? Berikan justifikasi teknisnya.
3. Bagaimana gateway menangani agregasi data dan penyebaran konteks pelacakan terdistribusi (*distributed tracing*)?

### Skenario 2: Idempotent Payment Webhook Dispatcher
Sistem pembayaran Anda harus mengirimkan Webhook notifikasi transaksi ke 5.000 merchant pihak ketiga setiap kali ada pembayaran berhasil.
Terkadang server merchant mengalami downtime atau timeout jaringan:
1. Rancang mekanisme retry berulang menggunakan **Exponential Backoff dengan Jitter**.
2. Bagaimana Anda menyusun payload Webhook dan header signature HMAC-SHA256 agar merchant dapat memverifikasi keaslian pesan serta memproses Webhook secara idempoten tanpa resiko double-crediting ke akun pelanggan mereka?

### Skenario 3: Skema Migrasi Protobuf Zero-Downtime
Microservice `CatalogService` Anda diakses oleh 15 microservice lain menggunakan gRPC. Anda perlu menambahkan field baru `discount_price` dan menghapus field lama `legacy_tax_code`.
Jelaskan aturan dan tahapan migrasi skema Protobuf langkah demi langkah (*backward and forward compatibility rules*) agar rilis versi baru ini tidak menyebabkan crash pada 15 microservice konsumen yang belum di-deploy ulang!

---

## Bagian 4: Chapter Challenge — Building a Production-Grade Idempotent Payment API

### Deskripsi Tantangan
Anda diminta membangun modul pembayaran transaksi perbankan kelas enterprise:
1. **Idempotency Engine**:
   - Tulis middleware endpoint `POST /v1/transfers` yang memvalidasi header `Idempotency-Key`.
   - Simpan status transaksi di Redis menggunakan atomic lock `SETNX` dengan TTL 86.400 detik (24 jam).
   - Validasi *Payload Fingerprint* (SHA-256): Jika key yang sama digunakan ulang dengan nilai nominal uang yang berbeda, tolak seketika dengan `HTTP 400 Bad Request`.
2. **HATEOAS Hypermedia**:
   - Jika transaksi berhasil (`HTTP 201 Created`), sertakan objek `_links` yang menyediakan tautan navigasi dinamis: `self`, `receipt_download`, dan `dispute_transaction`.
3. **Cursor-Based Audit Feed**:
   - Buat endpoint `GET /v1/transfers` dengan Cursor-based pagination yang mampu melayani navigasi feed mutasi rekening data besar secara instan ($O(1)$) tanpa degradasi performa!

---

## Bagian 5: Knowledge Check & Checklist

### Saya Harus Memahami:
- [ ] Enam prinsip arsitektur REST Roy Fielding.
- [ ] Richardson Maturity Model (Level 0 hingga Level 3 HATEOAS).
- [ ] Perbedaan Safe Methods vs Idempotent Methods (GET, POST, PUT, PATCH, DELETE).
- [ ] Standardisasi format error RFC 7807 (Problem Details).
- [ ] Mekanisme kerja Idempotency Key pada transaksi mutasi keuangan.
- [ ] Perbedaan performa Offset-based vs Cursor-based pagination.
- [ ] Efisiensi serialisasi biner Protocol Buffers (Protobuf v3) vs JSON.
- [ ] Empat mode komunikasi gRPC (Unary, Server Streaming, Client Streaming, Bi-di).
- [ ] Akar masalah GraphQL N+1 Problem dan solusinya via DataLoader batching.

### Saya Tidak Perlu Menghafal:
- [ ] Struktur bitmask biner ZigZag encoding internal untuk signed integer di Protobuf.
- [ ] Nomor registrasi RFC untuk setiap header HTTP eksperimental.

### Saya Harus Bisa Melakukan:
- [ ] Merancang RESTful URI yang bersih, elegan, dan berorientasi sumber daya kata benda (*nouns*).
- [ ] Mengimplementasikan middleware Idempotency Key anti-double-debit berbasis Redis.
- [ ] Menulis skema `.proto` dan mengompilasinya menjadi gRPC client/server SDK.
- [ ] Menulis schema GraphQL SDL dan resolver bebas N+1 menggunakan DataLoader.
- [ ] Memilih antara REST, GraphQL, atau gRPC berdasarkan konteks kebutuhan sistem.

---
[⬅️ Module 02: gRPC, Protobuf, & GraphQL N+1](./Module-02-gRPC-Protobuf-dan-GraphQL-N-Plus-One-Problem.md) | [📋 Silabus Induk](../README.md) | [BAB 04 Module 01: Relational Modeling & ACID ➡️](../BAB-04-RDBMS-dan-SQL-Mastery/Module-01-Relational-Modeling-ACID-dan-Isolation-Levels.md)
---
