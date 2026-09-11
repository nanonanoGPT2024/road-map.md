---
[⬅️ BAB 09 Quiz & Challenge](../BAB-09-Pengujian-Backend-Kualitas-Kode-dan-CICD/BAB-09-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: Transaksi Terdistribusi, Saga, & CQRS ➡️](./Module-02-Transaksi-Terdistribusi-Saga-Event-Sourcing-CQRS.md)
---

# Module 01: Monolith, Modular Monolith, Microservices, & Domain-Driven Design (DDD)

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik mampu:
- Menganalisis spektrum evolusi arsitektur: **Single Monolith**, **Modular Monolith**, dan **Distributed Microservices** berdasarkan kematangan tim dan skala organisasi.
- Menguasai pilar **Domain-Driven Design (DDD) Strategis**: *Ubiquitous Language*, *Subdomains (Core, Supporting, Generic)*, dan pemetaan batasan model (**Bounded Contexts**).
- Menguasai pilar **Domain-Driven Design (DDD) Taktis**: **Entities**, **Value Objects** (Immutability), **Aggregates & Aggregate Roots**, **Domain Events**, dan **Repositories**.
- Menerapkan **Pola Strangler Fig** untuk memigrasikan sistem warisan (*Legacy Monolith*) ke microservices modern secara inkremental tanpa risiko kegagalan *Big Bang Rewrite*.
- Merancang batas layanan microservices yang kohesif dan terhindar dari jebakan *Distributed Monolith*.

---

## 2. Prerequisite
- Pemahaman komunikasi API REST, GraphQL, dan gRPC (BAB 03).
- Pemahaman transaksi database relasional dan non-relasional (BAB 04 & BAB 05).
- Pemahaman event-driven architecture dengan Apache Kafka (BAB 07).

---

## 3. Concept
Dalam rekayasa sistem enterprise, kode backend bukan sekadar kumpulan instruksi komputasi teknis; kode adalah **cerminan langsung dari proses bisnis dunia nyata**.

Kesalahan terbesar yang sering dilakukan oleh pengembang adalah memilih arsitektur Microservices terlalu dini sebelum memahami batasan domain bisnis. Hasilnya adalah bencana yang disebut **Distributed Monolith**: sistem terdistribusi yang mewarisi seluruh kelemahan monolit (kopling ketat) ditambah seluruh kelemahan sistem terdistribusi (latensi jaringan, kegagalan parsial, kerumitan deployment).

Arsitektur yang sehat berevolusi secara organik:
$$\text{Monolith Rapi} \longrightarrow \text{Modular Monolith} \longrightarrow \text{Targeted Microservices via DDD}$$

---

## 4. Why?
Tanpa pemahaman DDD dan pemisahan arsitektur yang tepat:
1. **The Big Ball of Mud:** Seluruh tabel database di-join secara liar oleh puluhan modul kode tanpa batasan. Perubahan kecil pada tabel `users` merusak modul `inventory`, `billing`, dan `shipping`.
2. **Kopling Database Berbagi (*Shared Database Antipattern*):** 10 microservices mengakses satu database PostgreSQL yang sama secara bersamaan. Saat salah satu service mengubah tipe data kolom, 9 service lainnya crash seketika di produksi.
3. **Anemic Domain Model:** Objek entitas hanya berupa struktur data pasif (*getters/setters*) tanpa logika bisnis, sementara logika bisnis tercecer di puluhan lapisan *Service Layer* raksasa yang tidak terkelola (*Fat Services*).
4. **Kegagalan Migrasi Big Bang:** Manajemen memutuskan merombak total monolit lama dari nol selama 2 tahun. Proyek dihentikan di tengah jalan karena kebutuhan bisnis telah berubah drastis sebelum proyek selesai.

---

## 5. What? (Spektrum Arsitektur & Elemen Taktis DDD)

### A. Spektrum Gaya Arsitektur Backend
| Karakteristik | Single Monolith | Modular Monolith | Microservices Terdistribusi |
|---|---|---|---|
| **Penyebaran (Deployment)** | 1 Unit Artefak (1 Container) | 1 Unit Artefak (Batas Modul Ketat) | Puluhan Container Independen |
| **Database** | 1 Database Bersama | 1 Database (Skema Terisolasi per Modul)| **Database-per-Service** Wajib |
| **Komunikasi Antar-Modul**| Panggilan Fungsi Memori Lokal | In-Memory Interface / Event Bus | Jaringan (HTTP/gRPC/Kafka) |
| **Latensi Antar-Komponen** | Sub-mikrodetik (In-Memory) | Sub-mikrodetik (In-Memory) | Milidetik (Network I/O) |
| **Kompleksitas Operasional**| Sangat Rendah | Rendah ke Menengah | **Sangat Tinggi** (K8s, Tracing, Service Mesh)|
| **Kesesuaian Tim** | 1 - 3 Tim Pengembang | 2 - 8 Tim Pengembang | Puluhan Tim Otonom Skala Besar |

### B. Bangunan Taktis Domain-Driven Design (DDD)
- **Entity:** Objek yang memiliki identitas unik (*Identity*) yang bertahan sepanjang waktu, meskipun atributnya berubah (contoh: `User`, `Order`).
- **Value Object:** Objek tanpa identitas unik yang didefinisikan murni oleh nilainya dan bersifat *Immutable* (tidak dapat diubah setelah dibuat). Dua objek bernilai sama dianggap identik (contoh: `Money(10000, 'IDR')`, `Address('Jl. Sudirman', 'Jakarta')`).
- **Aggregate Root:** Kluster entitas dan value objects yang diperlakukan sebagai satu kesatuan konsistensi data. Modifikasi data internal **hanya boleh** dilakukan melalui gerbang *Aggregate Root* (contoh: Mengubah item pesanan harus melalui `Order.addItem()`, dilarang mengupdate `OrderItem` secara langsung di database!).
- **Domain Event:** Catatan bahwa sesuatu yang bernilai bisnis telah terjadi di masa lalu (contoh: `OrderPlacedDomainEvent`, `PaymentFailedDomainEvent`).

---

## 6. How? (Pola Migrasi Strangler Fig)

Pola **Strangler Fig** diilhami oleh pohon ara pencekik di hutan tropis yang tumbuh menempel pada pohon tua, perlahan-lahan menggantikan pohon lama dari luar ke dalam hingga pohon tua mati tanpa merusak ekosistem sekitarnya.

```
FASE 1: PENYISIPAN API GATEWAY DI DEPAN MONOLITH LAMA
[ Client Apps ] ──▶ [ Reverse Proxy / API Gateway ] ──100% Trafik──▶ [ Legacy Monolith ]

FASE 2: EKSTRAKSI SERVICE PERTAMA (CONTOH: NOTIFICATION SERVICE)
[ Client Apps ] ──▶ [ API Gateway ] ──┬── /api/v1/notifications ──▶ [ New Notification Microservice ]
                                      └── Sisa 90% Endpoint ──────▶ [ Legacy Monolith ]

FASE 3: EKSTRAKSI BERKELANJUTAN HINGGA MONOLITH MENYUSUT & DIHANCURKAN
[ Client Apps ] ──▶ [ API Gateway ] ──┬── /orders ────────▶ [ Order Microservice ]
                                      ├── /payments ──────▶ [ Payment Microservice ]
                                      ├── /inventory ─────▶ [ Inventory Microservice ]
                                      └── /notifications ─▶ [ Notification Microservice ]
                                     (Legacy Monolith resmi dipadamkan tanpa downtime!)
```

---

## 7. Analogy
- **Monolith ibarat Pisau Lipat Tentara Swiss:** Semua alat (pisau, gunting, pembuka botol, obeng) berada dalam satu genggaman logam yang kokoh. Sangat praktis dibawa dan tidak pernah ada bagian yang ketinggalan. Namun jika Anda ingin mengganti gunting yang tumpul dengan gunting baru, Anda harus membongkar seluruh gagang pisau.
- **Microservices ibarat Kotak Perkakas Bengkel Profesional:** Setiap obeng, kunci pas, dan palu memiliki wadahnya masing-masing. Mekanik A bisa meminjam obeng tanpa mengganggu Mekanik B yang menggunakan kunci pas. Namun, jika Anda menjatuhkan baut di lantai atau salah satu alat hilang saat koordinasi kerja (**Network Partition**), bengkel bisa macet.

---

## 8. Diagram: Boundary Bounded Context & Aggregate Root

```
BOUNDED CONTEXT: E-COMMERCE SALES & ORDERING
┌────────────────────────────────────────────────────────────────────────┐
│  AGGREGATE ROOT: Order (ID: ORD-101)                                   │
│  ├── Status: 'CONFIRMED'                                               │
│  ├── CustomerId: 'USR-88'                                              │
│  ├── ShippingAddress (Value Object: Immutable)                         │
│  │   └── street: 'Gatot Subroto', city: 'Jakarta'                      │
│  └── Items (Entities yang dilindungi Aggregate Root):                  │
│      ├── OrderItem-1: sku: 'IPHONE-15', qty: 1, price: Money(20M, IDR) │
│      └── OrderItem-2: sku: 'CASE-CLR',  qty: 2, price: Money(150K, IDR)│
│                                                                        │
│  Metode Bisnis Terproteksi:                                           │
│  order.cancelOrder() -> Memvalidasi status, menerbitkan Domain Event   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼ (Menerbitkan Domain Event)
                  [ OrderCancelledDomainEvent ]
                                    │
                                    ▼ (Didengarkan Bounded Context lain)
┌────────────────────────────────────────────────────────────────────────┐
│  BOUNDED CONTEXT: WAREHOUSE & LOGISTICS                                │
│  └── Mengembalikan alokasi inventaris barang ke rak gudang             │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 9. Simple Example: Value Object Immutability (Node.js murni)

```javascript
class Money {
  constructor(amount, currency = 'IDR') {
    if (amount < 0) throw new Error('Nilai uang tidak boleh negatif');
    this.amount = amount;
    this.currency = currency;
    Object.freeze(this); // Wajib Immutable! Tidak boleh diubah setelah dibuat
  }

  add(otherMoney) {
    if (this.currency !== otherMoney.currency) {
      throw new Error(`Tidak bisa menjumlahkan mata uang berbeda: ${this.currency} vs ${otherMoney.currency}`);
    }
    // Mengembalikan instance baru, bukan mengubah instance lama!
    return new Money(this.amount + otherMoney.amount, this.currency);
  }

  equals(otherMoney) {
    return otherMoney instanceof Money &&
      this.amount === otherMoney.amount &&
      this.currency === otherMoney.currency;
  }
}

// Pengujian Value Object
const price1 = new Money(50000, 'IDR');
const price2 = new Money(50000, 'IDR');
console.log(price1.equals(price2)); // true (Nilai sama, walau referensi memori beda)

const total = price1.add(new Money(25000, 'IDR'));
console.log(total.amount); // 75000
console.log(price1.amount); // 50000 (Tetap utuh tidak berubah)
```

---

## 10. Practical Example: Rich Domain Model Aggregate Root (Bukan Anemic!)

```javascript
class OrderAggregateRoot {
  constructor(id, customerId) {
    this.id = id;
    this.customerId = customerId;
    this.items = [];
    this.status = 'DRAFT';
    this.domainEvents = [];
  }

  addItem(productSku, quantity, unitPrice) {
    if (this.status !== 'DRAFT') {
      throw new Error('Tidak dapat mengubah item pada pesanan yang sudah difinalisasi!');
    }
    if (quantity <= 0) throw new Error('Kuantitas barang minimal 1');

    this.items.push({ productSku, quantity, unitPrice });
  }

  checkout() {
    if (this.items.length === 0) {
      throw new Error('Pesanan kosong tidak dapat di-checkout!');
    }
    if (this.status !== 'DRAFT') {
      throw new Error('Pesanan sudah pernah di-checkout sebelumnya!');
    }

    this.status = 'PLACED';

    // Merekam Domain Event
    this.domainEvents.push({
      eventName: 'ORDER_PLACED',
      orderId: this.id,
      customerId: this.customerId,
      totalAmount: this.calculateTotal(),
      occurredOn: new Date()
    });
  }

  calculateTotal() {
    return this.items.reduce((acc, item) => acc + (item.quantity * item.unitPrice), 0);
  }

  pullDomainEvents() {
    const events = [...this.domainEvents];
    this.domainEvents = []; // Kosongkan event setelah diambil untuk dipublish
    return events;
  }
}
```

---

## 11. Real World Example: Transformasi Modular Monolith Shopify

Shopify mengelola jutaan transaksi e-commerce global dengan basis kode Ruby on Rails monolit raksasa:
- Alih-alih memecah kode menjadi 500 microservices yang memicu mimpi buruk koordinasi jaringan, Shopify menerapkan arsitektur **Modular Monolith**.
- Batasan domain didefinisikan secara tegas menggunakan tool open-source `packwerk`:
  - Modul `Core::Orders` tidak diizinkan memanggil model ActiveRecord `Core::Inventory` secara langsung.
  - Komunikasi lintas modul wajib melalui **Public API Interface** yang terdokumentasi dan terisolasi.
- Hasil: Shopify mempertahankan kecepatan rilis 40 deployment per hari dengan performa in-memory super cepat tanpa overhead latensi jaringan microservices.

---

## 12. Trade-offs

| Aspek Arsitektur | Single Monolith | Modular Monolith | Microservices Terdistribusi |
|---|---|---|---|
| **Pemisahan Batas Kode** | Lemah (Sering spageti) | Kuat (Ditegakkan oleh tool linter/packwerk) | **Mutlak** (Terpisah repositori / proses) |
| **Independensi Deployment**| Nol (Deploy satu adalah deploy semua)| Nol (Tetap satu artefak biner) | **Tinggi** (Service A deploy tanpa sentuh B) |
| **Fault Isolation (Ketahanan)**| Rendah (Crash 1 modul bisa mematikan app)| Rendah ke Sedang | **Tinggi** (Kegagalan terisolasi di 1 pod) |
| **Latensi Komunikasi** | ~0.001 ms (In-Memory Function) | ~0.001 ms (In-Memory Function) | ~2 - 15 ms (Network RPC / TCP) |
| **Konsistensi Transaksi** | Transaksi ACID Database Lokal | Transaksi ACID Database Lokal | **Eventual Consistency** (Pola Saga) |

---

## 13. When To Use
- **Gunakan Single / Modular Monolith Jika:**
  - Anda sedang membangun produk baru (MVP / Startup) dengan ukuran tim di bawah 15 insinyur.
  - Domain bisnis masih sangat cair dan sering berubah drastis setiap minggu.
  - Kecepatan iterasi fitur dan kesederhanaan deployment adalah prioritas utama.
- **Gunakan Microservices Jika:**
  - Organisasi memiliki 100+ insinyur yang dibagi menjadi puluhan tim otonom yang saling menghambat jika menggunakan satu repositori kode bersama.
  - Bagian tertentu dari sistem membutuhkan karakteristik penskalaan perangkat keras yang sangat berbeda (misal: Transcoder Video butuh instance GPU, sementara Auth Service hanya butuh CPU ringan).

---

## 14. When NOT To Use
- **Jangan Memulai dari Microservices di Hari Pertama Proyek Baru:** Memulai proyek startup dengan microservices sebelum domain bisnis matang adalah resep tercepat menuju kebangkrutan teknis.
- **Jangan Gunakan Microservices dengan Shared Database:** Menghubungkan 10 service microservices ke satu database MySQL yang sama adalah antipattern fatal yang meniadakan seluruh manfaat microservices dan menyisakan seluruh kerumitannya.

---

## 15. Common Mistakes
1. **Anemic Domain Model (Anti-DDD):** Menjadikan class entitas hanya penampung data tanpa logika (*Property-Bag*), lalu menulis ribuan baris if-else di file `OrderService.java` atau `order.service.ts`.
2. **Membuat Entity untuk Segala Hal:** Membuat class Entity untuk konsep yang seharusnya adalah *Value Object*. Jika dua alamat jalan atau dua nilai mata uang bernilai sama, mereka tidak butuh ID unik!
3. **Mengabaikan Ubiquitous Language:** Menggunakan istilah yang berbeda antara pembicaraan tim bisnis dengan kode pengembang (misal: Tim bisnis menyebut "Kredit Poin", namun di kode database ditulis `user_discount_vouchers`).
4. **Microservices Terlalu Kecil (Nano-services):** Memecah satu fungsi CRUD sederhana (misal `UserAvatarService`) menjadi satu microservice terpisah. Overhead jaringan dan monitoring akan jauh melampaui logika kode yang dijalankan.

---

## 16. Best Practices

### Must Have
- Terapkan aturan **Database-per-Service** jika memilih arsitektur Microservices.
- Lindungi integritas data dengan **Aggregate Root**: Akses ke entitas anak wajib melalui metode publik Aggregate Root.
- Jadikan **Value Objects** selalu *Immutable* (gunakan `Object.freeze()` atau record type di Java/C#).

### Recommended
- Mulailah proyek dengan arsitektur **Modular Monolith**: Pisahkan modul dengan batas domain yang bersih sejak dini. Jika suatu saat modul tertentu perlu diskalakan secara independen, modul tersebut dapat diekstraksi menjadi microservice dengan mudah.
- Gunakan **Strangler Fig Pattern** untuk modernisasi sistem monolitik warisan secara bertahap.

### Advanced
- Terapkan **Anti-Corruption Layer (ACL)** ketika microservice baru harus berkomunikasi dengan sistem legacy lama untuk mencegah model data legacy yang kotor mencemari domain model baru yang bersih.

---

## 17. Troubleshooting

| Masalah Arsitektur | Indikasi Gejala | Langkah Investigasi | Tindakan Koreksi |
|---|---|---|---|
| **Distributed Monolith Terbentuk** | Untuk merilis perubahan kecil di Service A, tim harus merilis Service B, C, dan D secara serentak | Cek dependency graph deployment antar service | Evaluasi kembali Bounded Context, gabungkan service yang terlalu erat menjadi satu |
| **Circular Dependency Antar Modul** | Modul Order mengimpor Modul User, dan Modul User mengimpor Modul Order | Jalankan linter modul (misal `madge` di Node.js) | Lepaskan dependensi langsung dengan menggunakan Domain Events / PubSub |
| **Integritas Invariant Aggregate Bocor** | Data anak di dalam Aggregate termodifikasi di luar kendali Aggregate Root | Audit kode repository, periksa apakah ada query langsung ke tabel anak | Hapus repository untuk tabel anak; hanya sediakan repository untuk Aggregate Root |

---

## 18. Exercise
1. Rancang Value Object `Email` dan `Money` yang bersifat immutable dan memvalidasi formatnya sendiri saat inisialisasi.
2. Bangun Aggregate Root `ShoppingCart` yang mengelola koleksi `CartItem`.
3. Terapkan invariant bisnis: Total item dalam keranjang tidak boleh melebihi 20 barang, dan total nominal belanja tidak boleh bernilai negatif.

---

## 19. Challenge
Rancang dekomposisi Domain-Driven Design (DDD) untuk platform E-Commerce Marketplace skala nasional:
1. Identifikasi dan petakan 4 **Bounded Contexts** utama (contoh: *Customer Identity, Product Catalog, Sales Ordering, & Warehouse Fulfillment*).
2. Tentukan **Core Domain**, **Supporting Domain**, dan **Generic Subdomain**.
3. Rancang spesifikasi **Context Map** yang mendefinisikan hubungan antar-konteks (Upstream/Downstream, Shared Kernel, Customer/Supplier, atau Anti-Corruption Layer)!

---

## 20. Summary
Arsitektur perangkat lunak yang unggul bukanlah tentang mengikuti tren teknologi terpopuler, melainkan tentang keselarasan antara struktur kode dengan kompleksitas domain bisnis. Dengan menerapkan Domain-Driven Design (DDD) secara disiplin, memprioritaskan Modular Monolith pada fase pertumbuhan, dan memanfaatkan Strangler Fig saat bertransisi ke Microservices, Anda membangun fondasi sistem yang mampu bertahan dan berkembang melintasi dekade.

---
[⬅️ BAB 09 Quiz & Challenge](../BAB-09-Pengujian-Backend-Kualitas-Kode-dan-CICD/BAB-09-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: Transaksi Terdistribusi, Saga, & CQRS ➡️](./Module-02-Transaksi-Terdistribusi-Saga-Event-Sourcing-CQRS.md)
---
