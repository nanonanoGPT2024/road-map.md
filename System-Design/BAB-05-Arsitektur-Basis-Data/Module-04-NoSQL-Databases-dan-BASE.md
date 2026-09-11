# MODULE 04: NoSQL Databases & Paradigma BASE

## 1. Learning Objective
Setelah menyelesaikan module ini, Anda mampu:
1. Membedakan secara arsitektural dan fungsional 4 kategori database NoSQL: **Document Store**, **Key-Value Store**, **Wide-Column Store**, dan **Graph Database**.
2. Menerapkan paradigma **BASE (Basically Available, Soft State, Eventual Consistency)** sebagai alternatif fleksibel dari ACID.
3. Menerapkan prinsip **Query-Driven Data Modeling** (merancang skema berbasis query, bukan entitas relasional).
4. Merancang arsitektur **Polyglot Persistence** (mengombinasikan SQL, Document, Key-Value, dan Search Engine dalam satu sistem produksi terpadu).
5. Menjalankan benchmark perbandingan antara *Relational Multi-Table JOIN* vs *Denormalized NoSQL Document Fetch* menggunakan hands-on script.

---

## 2. Prerequisite
- Telah menyelesaikan [BAB 05 — Module 01: RDBMS Scaling, Indexing, & ACID](./Module-01-RDBMS-Scaling-Indexing-dan-ACID.md).
- Telah menyelesaikan [BAB 05 — Module 03: Database Partitioning & Sharding](./Module-03-Database-Partitioning-dan-Sharding.md).

---

## 3. Concept
Selama beberapa dekade, Relational Database (RDBMS) adalah pilihan default mutlak. Namun ledakan data internet pada era Web 2.0 melahirkan tantangan **3V**:
- **Volume:** Ukuran data melompat dari Gigabyte menjadi Petabyte.
- **Velocity:** Kecepatan data masuk mencapai jutaan event per detik (telemetri, klik, pesan chat).
- **Variety:** Bentuk data tidak seragam (semi-terstruktur seperti JSON, XML, grafik hubungan sosial).

**NoSQL (Not Only SQL)** adalah sebutan bagi rumpun teknologi database non-relasional yang dirancang dari awal untuk **skalabilitas horizontal (*Scale-Out*)** alami dan fleksibilitas skema, sering kali mengorbankan sebagian garansi ACID demi mencapai ketersediaan (*Availability*) dan performa penulisan masif.

---

## 4. Why? (Mengapa Kita Membutuhkan NoSQL di Samping SQL?)

### Biaya Komputasi Operasi `JOIN` pada Skala Terdistribusi
Pada database relasional yang dinormalisasi (3rd Normal Form / 3NF):
Untuk menampilkan halaman profil toko di Tokopedia, database harus melakukan join 5 tabel:
`users JOIN stores JOIN products JOIN product_reviews JOIN shipping_options`
- Di satu server tunggal, operasi JOIN ini memakan banyak memori dan CPU.
- Pada database yang sudah di-shard ke beberapa server fisik, **operasi JOIN antar-mesin (*Distributed Join*) hampir mustahil dilakukan secara efisien** karena memicu lalu lintas jaringan raksasa antar-node.

**Filosofi NoSQL:** Lebih baik menduplikasi data (**Denormalisasi**) ke dalam satu dokumen tunggal sehingga 100% data yang dibutuhkan untuk halaman produk dapat dibaca dalam **satu kali operasi $O(1)$** tanpa JOIN!

---

## 5. What? (4 Kategori NoSQL & Paradigma BASE)

### A. 4 Kategori Utama Database NoSQL

```text
1. KEY-VALUE STORE (Redis, DynamoDB, Memcached)
   Paling sederhana dan paling cepat. Beroperasi seperti kamus hash map raksasa.
   Key: "session_token_xyz" -> Value: "{ user_id: 101, login_time: ... }"
   Use Case: Manajemen sesi login, shopping cart, cache, rate limiter.

2. DOCUMENT STORE (MongoDB, Couchbase, Firestore)
   Menyimpan data semi-terstruktur dalam format JSON / BSON / XML hierarkis.
   Mendukung sub-dokumen bersarang (nested arrays/objects) dan indexing fleksibel.
   Use Case: Katalog produk e-commerce, profil pengguna, Content Management System (CMS).

3. WIDE-COLUMN / COLUMNAR STORE (Apache Cassandra, ScyllaDB, Bigtable, ClickHouse)
   Menyimpan data dalam baris dengan jutaan kolom dinamis yang dikelompokkan dalam column family.
   Sangat optimal untuk penulisan (*write-heavy*) dan agregasi analitik kolom (OLAP).
   Use Case: Time-series telemetri IoT, logging riwayat tontonan (Netflix), chat history.

4. GRAPH DATABASE (Neo4j, Amazon Neptune, ArangoDB)
   Menyimpan data sebagai simpul (**Nodes**) dan relasi keterhubungan (**Edges**).
   Melakukan traversal relasi kompleks berjarak 5 tingkat dalam hitungan milidetik.
   Use Case: Jejaring sosial (LinkedIn connections), fraud detection perbankan, knowledge graph.
```

---

### B. Paradigma BASE vs ACID

```text
                    ACID (RDBMS / SQL)           vs          BASE (NoSQL)
                ---------------------------             ---------------------------
                - Atomicity                             - Basically Available
                - Consistency                           - Soft State
                - Isolation                             - Eventual Consistency
                - Durability
```

1. **Basically Available (BA):** Sistem menjamin ketersediaan data untuk merespon request pengguna, meskipun respon tersebut berasal dari node replica yang sedang terdegradasi.
2. **Soft State (S):** Keadaan data dapat berubah dari waktu ke waktu tanpa adanya input baru, karena proses replikasi dan konsensus di background sedang berjalan.
3. **Eventual Consistency (E):** Sistem menjamin bahwa jika tidak ada pembaruan baru pada data tersebut, seluruh node replica lambat laun (*eventually*) akan konvergen memiliki nilai data yang identik.

---

## 6. How? (Prinsip Query-Driven Data Modeling)

### Pola Pikir RDBMS vs NoSQL:
- **Di RDBMS (Relational):** Anda memodelkan data berdasarkan **Entitas Nyata di Dunia** (*Entity-Relationship Modeling*). Anda menormalisasi tabel agar tidak ada data yang redundan, lalu Anda memikirkan query-nya nanti menggunakan klausa JOIN.
- **Di NoSQL (Khususnya Cassandra / DynamoDB):** Anda **WAJIB MENGETAHUI QUERY APLIKASI TERLEBIH DAHULU** sebelum membuat tabel! (*Query-Driven Modeling*).
  - Jika Anda memiliki 3 query berbeda untuk menampilkan data artikel, Anda seringkali membuat **3 tabel berbeda** yang menyimpan duplikasi data artikel yang sama, dioptimalkan untuk masing-masing Partition Key!

```text
               DENORMALISASI DOKUMEN (MONGODB STYLE)

  RDBMS (3 Tabel Terpisah butuh 2x JOIN):
  [ users_table ] ──(JOIN)──▶ [ orders_table ] ──(JOIN)──▶ [ order_items_table ]

  NoSQL Document (1 Dokumen JSON Tunggal, Sekali Baca O(1)):
  {
    "_id": "ORD-1001",
    "customer_name": "Budi Santoso",
    "items": [
      { "name": "Mechanical Keyboard", "qty": 1, "price": 80 },
      { "name": "Mousepad XL", "qty": 1, "price": 20 }
    ],
    "total": 100
  }
```

---

## 7. Analogy: Lemari Map Berkas vs Formulir Lengkap
- **SQL (Ternormalisasi):** Formulir pendaftaran mahasiswa di mana nama mahasiswa dicatat di Gedung A, alamat di Gedung B, dan daftar mata kuliah di Gedung C. Setiap kali dekan ingin melihat data mahasiswa, staf kampus harus berlari ke tiga gedung berbeda untuk mengumpulkan ketiga berkas tersebut (JOIN).
- **NoSQL (Denormalisasi):** Satu map folder tebal berisi satu lembar kertas formulir lengkap yang mencantumkan nama, alamat, dan seluruh mata kuliah sekaligus. Dekan cukup membuka satu map tersebut dan langsung mendapatkan seluruh informasi dalam sekejap.

---

## 8. Diagram: Arsitektur Polyglot Persistence Modern

Di sistem modern berskala besar (seperti Shopee, Tokopedia, atau Gojek), Anda **tidak memilih antara SQL ATAU NoSQL**. Anda menggunakan **KEDUANYA** secara harmonis sesuai keunggulan masing-masing (*Polyglot Persistence*):

```text
                           [ CLIENT APPLICATION ]
                                     │
                 ┌───────────────────┼───────────────────┐
                 ▼                   ▼                   ▼
        [ Transaksi Finansial ]  [ Katalog Produk ]    [ Search & Filter ]
                 │                   │                   │
                 ▼                   ▼                   ▼
         [ PostgreSQL DB ]     [ MongoDB / NoSQL ]     [ Elasticsearch ]
          (ACID, Saldo,         (Skema Fleksibel,      (Full-Text Search,
           Integritas Uang)      Spesifikasi Varian)    Faceted Filtering)
                 │                   │                   │
                 └───────────────────┴───────────────────┘
                                     │ (Sinkronisasi Event via Kafka CDC)
                                     ▼
                           [ Redis In-Memory ]
                           (Session & Top Cache)
```

---

## 9. Simple Example: Penanganan Skema Fleksibel E-Commerce
Di e-commerce, produk memiliki atribut yang sangat heterogen:
- Baju memiliki atribut: `ukuran` (S, M, L), `warna`, `bahan`.
- Laptop memiliki atribut: `processor`, `ram_gb`, `storage_ssd`, `gpu`.
- Ban Mobil memiliki atribut: `diameter_ring`, `lebar_tapak`, `aspek_rasio`.

Jika menggunakan SQL: Anda membutuhkan puluhan kolom nullable atau tabel `Entity-Attribute-Value (EAV)` yang sangat lambat di-query.  
Di MongoDB NoSQL: Setiap produk cukup disimpan sebagai dokumen JSON dengan atribut dinamisnya sendiri!

---

## 10. Practical Code Example
Lihat perbandingan performa waktu eksekusi antara query relasional Multi-Table JOIN vs single Document Key Fetch pada:
`System-Design/BAB-05-Arsitektur-Basis-Data/hands-on/m04/sql_vs_nosql_benchmark.js`

---

## 11. Real World Example: Netflix Menggunakan Apache Cassandra & Uber Menggunakan Schemaless
- **Netflix Viewing History:** Netflix melayani lebih dari 250 juta pelanggan yang menonton ratusan juta jam video setiap hari. Setiap kali pengguna menekan pause, bookmark menit video dicatat. Netflix menggunakan **Apache Cassandra (Wide-Column)** di AWS yang tersebar di multi-region. Cassandra mampu menyerap jutaan penulisan telemetri per detik dengan latensi konsisten < 5 ms berkat arsitektur *LSM-Tree (Log-Structured Merge-Tree)* tanpa pernah mengalami locking database.
- **Uber Schemaless:** Uber awalnya menggunakan PostgreSQL monolitik. Ketika perjalanan ojek/taksi melonjak miliaran order, Uber membangun platform penyimpanan *Schemaless* di atas MySQL InnoDB yang bertindak seperti Append-Only Document Store terdistribusi.

---

## 12. Trade-offs (SQL vs NoSQL)

| Dimensi | Relational Database (SQL) | NoSQL Datastores |
|---|---|---|
| **Model Skema** | Kaku, terdefinisi di awal (*Schema-on-Write*) | Fleksibel, dinamis (*Schema-on-Read*) |
| **Model Skalabilitas** | Alami Vertikal (Scale Up). Sharding kompleks | Alami Horizontal (Scale Out out-of-the-box) |
| **Garansi Transaksi** | Kuat (ACID mutlak) | Fleksibel (BASE / Eventual Consistency) |
| **Kemampuan Query** | Sangat Kaya (JOIN, Subquery, Window Functions) | Terbatas (Fokus pada key-value atau partition path) |
| **Integritas Relasi** | Dijamin oleh Foreign Key & Check Constraint | Menjadi tanggung jawab logika kode aplikasi |

---

## 13. When To Use What
- **Pilih Relational SQL (Postgres / MySQL) jika:**
  - Data bersifat sangat relasional dengan banyak relasi antar-entitas.
  - Bisnis menuntut integritas transaksi finansial mutlak (Core Banking, Payment, ERP, Akuntansi).
- **Pilih Document NoSQL (MongoDB) jika:**
  - Skema data terus berubah dengan cepat (*rapid prototyping* / agile).
  - Data bersifat hierarkis bersarang (dokumen JSON mandiri).
- **Pilih Wide-Column NoSQL (Cassandra / ScyllaDB) jika:**
  - Volume penulisan data masif (*Write-Heavy*, misal: telemetri IoT, sensor pabrik, logging audit).
- **Pilih Graph Database (Neo4j) jika:**
  - Masalah bisnis Anda adalah mencari jalur koneksi (*Pathfinding / Relationship Traversal*), seperti rekomendasi teman mutual di LinkedIn atau deteksi sindikat pencucian uang.

---

## 14. When NOT To Use NoSQL
- Jangan gunakan NoSQL murni jika model bisnis Anda membutuhkan transaksi multi-tabel ACID yang ketat dan sering melakukan query analitik ad-hoc tanpa pola yang jelas.

---

## 15. Common Mistakes
1. **Menggunakan MongoDB seperti MySQL:** Membuat 15 koleksi terpisah lalu melakukan operasi `$lookup` (JOIN) berlapis-lapis di setiap query. Performa aplikasi akan jauh lebih lambat daripada database relasional asli!
2. **Tidak Memahami Tombstones di Cassandra:** Menghapus jutaan baris data di Cassandra secara berkala. Cassandra menandai data terhapus dengan *Tombstone*. Saat membaca data, Cassandra harus memindai jutaan tombstone tersebut, memicu *TombstoneOverwhelmingException* dan crash server!
3. **Mengabaikan Biaya Storage Akibat Denormalisasi:** Menduplikasi seluruh detail nama, alamat, dan deskripsi produk ke setiap baris order tanpa memperhitungkan pembengkakan ukuran disk database.

---

## 16. Best Practices

- **Must Have:**
  - Terapkan **Polyglot Persistence**: Gunakan database yang tepat untuk pekerjaan yang tepat (*Right tool for the right job*).
  - Selalu definisikan index pada field yang menjadi filter utama di Document Store.
- **Recommended:**
  - Pahami rasio *Embedded Documents vs References*: Masukkan data sebagai sub-dokumen jika datanya terikat mati (1:1 atau 1:few seperti item order). Gunakan referensi ID jika datanya independen (1:many besar seperti user komentar).
- **Advanced:**
  - Manfaatkan **Change Data Capture (CDC)** dengan Debezium untuk menyinkronkan data dari SQL Database ke Elasticsearch dan NoSQL secara asinkron tanpa membebani thread transaksi utama.
- **Avoid / Overengineering:**
  - Mengganti database PostgreSQL yang sudah berjalan stabil dengan cluster Cassandra 10 node hanya karena tren teknologi.

---

## 17. Troubleshooting Guide
```text
Gejala: Query find() pada koleksi MongoDB jutaan dokumen sangat lambat (CPU 100%).
-------------------------------------------------------------------------------
Penyebab:
1. Query filter mencari field di dalam sub-dokumen yang tidak memiliki index (COLLSCAN / Collection Scan).

Cara Diagnosa:
- Jalankan analisis query di Mongo Shell:
  db.products.find({ "specs.ram": "16GB" }).explain("executionStats")
- Perhatikan stage: Jika tertulis "COLLSCAN", artinya MongoDB memindai seluruh dokumen dari awal.

Solusi:
- Buat Compound / Single Index pada field bersarang:
  db.products.createIndex({ "specs.ram": 1 })
```

---

## 18. Hands-on Lab: Komparasi Relational JOIN vs NoSQL Document Fetch

File lab sudah disiapkan di:
`System-Design/BAB-05-Arsitektur-Basis-Data/hands-on/m04/sql_vs_nosql_benchmark.js`

### Jalankan Uji Coba:
Buka terminal dan jalankan:
```bash
node System-Design/BAB-05-Arsitektur-Basis-Data/hands-on/m04/sql_vs_nosql_benchmark.js
```

### Yang Ditampilkan Script Ini:
1. Mensimulasikan pendekatan **Relasional (SQL Normalized)**: Mengambil data order yang membutuhkan **2x operasi JOIN** (Users Table + Orders Table + OrderItems Table) dengan kompleksitas $O(M \times N)$.
2. Mensimulasikan pendekatan **NoSQL Document (Denormalized)**: Mengambil data order yang sama yang sudah teragregasi dalam satu dokumen JSON utuh dalam kompleksitas $O(1)$.
3. Menghitung rasio perbedaan efisiensi waktu eksekusi.

---

## 19. Exercises (Latihan)

### Level 1 (Easy):
Sebutkan 4 kategori utama database NoSQL beserta satu contoh teknologi untuk masing-masing kategori!

### Level 2 (Medium):
Jelaskan prinsip **BASE (Basically Available, Soft State, Eventual Consistency)**! Mengapa model BASE sangat cocok untuk fitur jumlah Like pada postingan media sosial, tetapi berbahaya jika diterapkan pada sistem saldo perbankan?

### Level 3 (Hard):
Sebuah perusahaan logistik memiliki 50.000 truk pengiriman yang mengirimkan koordinat GPS setiap 2 detik (25.000 writes/detik). Rancang arsitektur penyimpanan data yang memadukan **Polyglot Persistence**:
1. Di mana data koordinat GPS time-series disimpan?
2. Di mana data master akun sopir dan kontrak truk disimpan?
3. Di mana status posisi terkini (*current live location*) disimpan untuk ditampilkan di peta customer?

---

## 20. Summary & Knowledge Check
- [ ] Memahami perbedaan filosofis arsitektur SQL (ACID) vs NoSQL (BASE).
- [ ] Menguasai 4 kategori NoSQL: Key-Value, Document, Wide-Column, dan Graph.
- [ ] Memahami prinsip *Query-Driven Data Modeling* dan teknik Denormalisasi.
- [ ] Menguasai konsep arsitektur *Polyglot Persistence*.
- [ ] Mampu mendiagnosa kesalahan penggunaan NoSQL yang menyerupai pola relasional.
