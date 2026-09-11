---
[⬅️ Module 01: Monolith, Microservices, & DDD](./Module-01-Monolith-Modular-Microservices-dan-DDD.md) | [📋 Silabus Induk](../README.md) | [BAB 10 Quiz & Challenge ➡️](./BAB-10-Quiz-dan-Challenge.md)
---

# Module 02: Transaksi Terdistribusi, Pola Saga, Event Sourcing, & CQRS

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik mampu:
- Memahami mengapa transaksi ACID tradisional (**Two-Phase Commit / 2PC**) runtuh saat diterapkan pada microservices terdistribusi skala cloud.
- Menguasai implementasi **Pola Saga** untuk mengelola transaksi bisnis lintas service: membandingkan **Saga Choreography** (berbasis event terdesentralisasi) vs **Saga Orchestration** (state machine terpusat).
- Merancang **Transaksi Kompensasi (Compensating Transactions)** untuk melakukan *Semantic Rollback* saat salah satu langkah saga gagal.
- Menguasai paradigma **Event Sourcing**: menyimpan status sistem bukan sebagai baris mutasi tabel, melainkan sebagai aliran fakta sejarah yang tak dapat diubah (*Append-Only Event Stream*).
- Mengimplementasikan **CQRS (Command Query Responsibility Segregation)**: memisahkan Model Penulisan (*Write/Command Model*) yang mengutamakan konsistensi invariant dari Model Pembacaan (*Read/Query Model*) yang terdenormalisasi untuk performa pencarian kilat.

---

## 2. Prerequisite
- Memahami konsep ACID dan isolasi transaksi database (BAB 04).
- Pemahaman message brokers, Kafka append-only logs, dan consumer group (BAB 07).
- Pemahaman taktis DDD: Aggregate Root dan Domain Events (Modul 01).

---

## 3. Concept
Ketika sebuah arsitektur backend dipecah menjadi microservices dengan prinsip **Database-per-Service**, transaksi bisnis tunggal (misal: "Beli Tiket Pesawat") tidak lagi dapat dibungkus dalam satu blok `BEGIN ... COMMIT` SQL lokal:
- Pengurangan kuota kursi ada di Database *FlightService*.
- Pendebitan kartu kredit ada di Database *PaymentService*.
- Penerbitan boarding pass ada di Database *TicketingService*.

Jika langkah ketiga gagal, database SQL tidak memiliki cara otomatis untuk me-rollback database pada service pertama dan kedua yang berada di server fisik terpisah.

Solusi modern untuk masalah ini bukanlah Two-Phase Commit (2PC) yang lambat dan rentan deadlock, melainkan **Pola Saga** yang bersandar pada jaminan **Eventual Consistency** dan **Transaksi Kompensasi**.

---

## 4. Why?
Tanpa pemahaman Transaksi Terdistribusi, Saga, dan CQRS:
1. **Inkonsistensi Saldo Terdistribusi:** Service pembayaran sukses memotong saldo Rp 2.000.000, namun service inventaris gudang gagal memesan barang karena out of stock. Tanpa transaksi kompensasi terotomasi, uang nasabah hilang tanpa mendapatkan barang.
2. **Kerapuhan Two-Phase Commit (2PC):** Sistem memaksakan protokol XA/2PC lintas 10 server. Jika koordinator transaksi crash atau salah satu server mengalami latency spike, seluruh 10 database terkunci (*Row Lock*) selama bermenit-menit hingga sistem tumbang bersama (*Cascading Freeze*).
3. **Kehilangan Jejak Audit Historis:** Database CRUD biasa hanya menyimpan status terakhir (`status: CANCELLED`). Perusahaan tidak memiliki bukti kronologis: siapa yang membatalkan, kapan tepatnya dibatalkan, dan apa status saldo 5 menit sebelum pembatalan terjadi.
4. **Dilema Skalabilitas Query vs Write:** Model database relasional dinormalisasi hingga 4NF untuk mencegah anomali tulis, namun akibatnya setiap query halaman dashboard user membutuhkan JOIN 12 tabel yang memakan waktu 3 detik.

---

## 5. What? (Pola Saga, Event Sourcing, & CQRS)

### A. Saga: Choreography vs Orchestration
- **Choreography (Tari Bersama Tanpa Konduktor):** Setiap service mendengarkan domain event dari service lain via broker (Kafka), lalu memutuskan tindakan berikutnya secara mandiri.
  - *Kelebihan:* Sangat terdesentralisasi, loosely coupled, cocok untuk alur sederhana (2-3 service).
  - *Kekurangan:* Sulit dipahami secara visual (*Spaghetti Events*), rentan siklus looping event tak berujung.
- **Orchestration (Konduktor Orkestra Terpusat):** Satu service koordinator (*Saga Orchestrator*) menginstruksikan setiap service untuk mengeksekusi perintah (*Command*) dan menerima balasan (*Reply*) menggunakan State Machine.
  - *Kelebihan:* Alur bisnis transparan, penanganan error dan transaksi kompensasi terpusat, mudah di-audit.
  - *Kekurangan:* Menambah satu titik koordinasi (*Orchestrator Service*).

### B. Transaksi Kompensasi (Semantic Rollback)
Transaksi kompensasi **bukanlah** `ROLLBACK` SQL fisik yang membatalkan perubahan secara gaib. Transaksi kompensasi adalah transaksi baru yang membalikkan efek bisnis dari transaksi sebelumnya secara eksplisit:
- Tindakan Asli: `Debit(Rp 500.000)` $\longrightarrow$ Kompensasi: `Credit_Refund(Rp 500.000)`.
- Tindakan Asli: `ReserveSeat(12A)` $\longrightarrow$ Kompensasi: `ReleaseSeat(12A)`.
- Tindakan Asli: `SendEmail()` $\longrightarrow$ Kompensasi: Tidak bisa unsend email, kirim email klarifikasi: `SendCancellationEmail()`.

---

## 6. How? (Arsitektur CQRS & Event Sourcing)

```
                              [ WRITE MODEL / COMMAND ]
                                         │
                               1. POST /orders/checkout
                                         │
                                         ▼
                            [ OrderAggregateRoot (DDD) ]
                             (Validasi Aturan & Invariant)
                                         │
                                         ▼
                         [ Event Store (Append-Only Log) ]
                         ├── Event 1: OrderCreatedEvent
                         ├── Event 2: PaymentAuthorizedEvent
                         └── Event 3: OrderShippedEvent
                                         │
                                         ▼ (Asynchronous Projection / CDC)
                     ┌───────────────────┴───────────────────┐
                     │                                       │
                     ▼                                       ▼
        [ Read DB: Elasticsearch ]              [ Read DB: Redis Cache ]
         (Kueri Pencarian Teks & Filter)         (Dashboard User: Sub-ms GET)
                     │                                       │
                     └───────────────────┬───────────────────┘
                                         │
                               2. GET /orders/:id
                                         │
                                         ▼
                              [ READ MODEL / QUERY ]
```
1. **Command:** Mengubah status sistem. Validasi bisnis ketat, menulis event ke **Event Store** murni tanpa modifikasi data lama (*Append-Only*).
2. **Projection Worker:** Membaca event baru secara asinkron dan memproyeksikannya (*Materialize View*) ke dalam database baca yang dioptimalkan (Elasticsearch untuk search, PostgreSQL denormalized untuk reporting, Redis untuk cache).
3. **Query:** Membaca data langsung dari Read DB dalam hitungan milidetik tanpa join tabel yang rumit.

---

## 7. Analogy
- **Event Sourcing ibarat Buku Rekening Koran Bank:** Buku tabungan bank tidak pernah menyimpan satu baris angka "Saldo: Rp 10.000.000" yang langsung ditimpa. Buku tabungan mencatat setiap baris peristiwa: *Setor Tunai +5jt, Transfer Keluar -1jt, Bunga +50rb*. Saldo Anda saat ini adalah **hasil kalkulasi penjumlahan dari seluruh baris peristiwa dari awal buku dibuka hingga hari ini**.
- **Saga Orchestrator ibarat Manajer Perjalanan Wisata (Travel Agent):** Anda ingin liburan: booking hotel, sewa mobil, dan tiket pesawat. Manajer menelpon hotel (sukses). Manajer menelpon maskapai (sukses). Manajer menelpon rental mobil (ternyata habis!). Manajer secara teratur menelpon balik maskapai dan hotel untuk membatalkan pesanan (*Kompensasi*) dan mengembalikan uang Anda secara utuh.

---

## 8. Diagram: Alur Saga Orchestration dengan Kegagalan & Kompensasi

```
[ Saga Orchestrator ]
         │
         ├── 1. Command: ReserveCredit(CUST-1, 100K) ──▶ [ Account Service ] (SUKSES ✅)
         │◀── Status: CREDIT_RESERVED ───────────────────┘
         │
         ├── 2. Command: AllocateStock(ITEM-99, 2) ─────▶ [ Inventory Service ] (SUKSES ✅)
         │◀── Status: STOCK_ALLOCATED ───────────────────┘
         │
         ├── 3. Command: DispatchCourier(ORD-101) ──────▶ [ Shipping Service ] (GAGAL: ALAMAT TIDAK TERJANGKAU! ❌)
         │◀── Status: DISPATCH_FAILED ───────────────────┘
         │
         ▼ (MEMULAI ALUR TRANSAKSI KOMPENSASI SECARA REVERSE / MUNDUR)
         ├── 4. Compensate: ReleaseStock(ITEM-99, 2) ───▶ [ Inventory Service ] (Stok Dikembalikan ✅)
         └── 5. Compensate: RefundCredit(CUST-1, 100K) ──▶ [ Account Service ] (Uang Dikembalikan ✅)
         │
         ▼
[ Order Status Diubah Menjadi: FAILED_AND_REFUNDED ] (Integritas Data 100% Terjaga)
```

---

## 9. Simple Example: Event Sourcing Entity Reconstitution (Node.js)

```javascript
class BankAccountAggregate {
  constructor(accountId) {
    this.accountId = accountId;
    this.balance = 0;
    this.isClosed = false;
    this.version = 0; // Optimistic locking version
  }

  // Rekonstruksi status terkini dari riwayat event (Event Replay)
  reconstituteFromHistory(events) {
    for (const event of events) {
      this.apply(event);
      this.version++;
    }
  }

  apply(event) {
    switch (event.type) {
      case 'ACCOUNT_OPENED':
        this.balance = event.initialDeposit;
        break;
      case 'MONEY_DEPOSITED':
        this.balance += event.amount;
        break;
      case 'MONEY_WITHDRAWN':
        this.balance -= event.amount;
        break;
      case 'ACCOUNT_CLOSED':
        this.isClosed = true;
        break;
      default:
        throw new Error(`Event tidak dikenali: ${event.type}`);
    }
  }
}

// Uji Coba Event Sourcing
const historicalEvents = [
  { type: 'ACCOUNT_OPENED', initialDeposit: 1000000 },
  { type: 'MONEY_DEPOSITED', amount: 500000 },
  { type: 'MONEY_WITHDRAWN', amount: 200000 },
  { type: 'MONEY_DEPOSITED', amount: 150000 }
];

const account = new BankAccountAggregate('ACC-8841');
account.reconstituteFromHistory(historicalEvents);

console.log(`Saldo Rekonstruksi: Rp ${account.balance.toLocaleString('id-ID')}`); // Rp 1.450.000
console.log(`Versi Event Log   : ${account.version}`); // 4
```

---

## 10. Practical Example: Implementasi Saga Orchestrator dengan State Machine

```javascript
class OrderSagaOrchestrator {
  constructor(paymentService, inventoryService, shippingService) {
    this.payment = paymentService;
    this.inventory = inventoryService;
    this.shipping = shippingService;
  }

  async executeSaga(orderId, customerId, items, amount, destination) {
    const context = { orderId, customerId, items, amount, destination };
    const executedSteps = [];

    try {
      // Langkah 1: Debit Pembayaran
      console.log(`[SAGA STEP 1] Mendebit pembayaran sebesar Rp ${amount}...`);
      await this.payment.debit(customerId, amount);
      executedSteps.push('PAYMENT');

      // Langkah 2: Reservasi Stok Barang
      console.log(`[SAGA STEP 2] Mengalokasikan inventaris stok...`);
      await this.inventory.reserveStock(items);
      executedSteps.push('INVENTORY');

      // Langkah 3: Jadwalkan Kurir Pengiriman
      console.log(`[SAGA STEP 3] Menghubungi kurir pengiriman...`);
      await this.shipping.dispatch(orderId, destination);
      executedSteps.push('SHIPPING');

      console.log(`[SAGA SUCCESS] Seluruh langkah berhasil! Order ${orderId} selesai.`);
      return { success: true, status: 'COMPLETED' };

    } catch (err) {
      console.error(`[SAGA FAILURE] Terjadi kesalahan pada langkah berikutnya: ${err.message}`);
      console.log(`[SAGA ROLLBACK] Menjalankan Transaksi Kompensasi secara mundur...`);

      // Rollback kompensasi berdasarkan langkah yang sempat sukses
      for (const step of executedSteps.reverse()) {
        if (step === 'INVENTORY') {
          console.log(`  ↪️ Membatalkan reservasi inventaris barang...`);
          await this.inventory.releaseStock(items);
        }
        if (step === 'PAYMENT') {
          console.log(`  ↪️ Mengembalikan dana pembayaran (Refund) ke nasabah...`);
          await this.payment.refund(customerId, amount);
        }
      }

      return { success: false, status: 'COMPENSATED', error: err.message };
    }
  }
}
```

---

## 11. Real World Example: Tiket Kereta Api & Maskapai Penerbangan (Uber / KAI / Traveloka)

Ketika Anda memesan paket perjalanan "Tiket Kereta + Hotel + Taksi Bandara":
- Sistem tidak menggunakan database tunggal. Masing-masing vendor adalah entitas terpisah.
- **Saga Orchestrator** mengatur reservasi:
  1. KAI reservasi kursi kereta.
  2. Hotel reservasi kamar.
  3. Taksi mengonfirmasi driver.
- Jika di detik terakhir kamar hotel ternyata penuh (*Sold Out*), Orchestrator langsung memanggil API pembatalan tiket KAI secara instan dan mengembalikan saldo kartu kredit pelanggan.
- Pelanggan tidak pernah ditinggalkan dalam kondisi "tiket kereta terbeli tapi tidak punya tempat menginap".

---

## 12. Trade-offs

| Paradigma Arsitektur | Jaminan Konsistensi Data | Latensi Transaksi | Kompleksitas Kode | Kemampuan Audit |
|---|---|---|---|---|
| **Traditional RDBMS (ACID / 2PC)** | Strong Consistency Mutlak | Lambat saat terdistribusi (Row Locks) | Sederhana | Terbatas (Hanya status mutakhir) |
| **Saga Pattern (Orchestration)** | **Eventual Consistency** | Cepat (Setiap step transaksi lokal) | Menengah ke Tinggi | Tinggi (Status state machine terekam) |
| **Event Sourcing** | Eventual Consistency | Cepat Append-Only ($O(1)$) | Tinggi | **Maksimal** (Setiap fakta sejarah tersimpan) |
| **CQRS (Read/Write Separation)**| Read Model Eventual Consistent| Sangat Cepat untuk Read Query | Tinggi (Butuh sinkronisasi proyeksi)| Tinggi |

---

## 13. When To Use
- **Pola Saga:** Wajib digunakan pada arsitektur Microservices di mana satu transaksi bisnis melintasi $\ge 2$ service yang memiliki database independen.
- **Event Sourcing:** Sangat ideal untuk sistem pembukuan keuangan (*Financial Ledgers*), aplikasi legal/kepatuhan audit, sistem reservasi penerbangan/kursi, dan game online multiplayer di mana rekonstruksi riwayat peristiwa sangat berharga.
- **CQRS:** Sangat tepat jika sistem Anda memiliki rasio baca banding tulis yang sangat timpang (misal: 99% Read vs 1% Write pada e-commerce), atau ketika query pelaporan membutuhkan bentuk agregasi data yang sangat berbeda dari struktur data penyimpanan transaksional.

---

## 14. When NOT To Use
- **Jangan Gunakan Event Sourcing untuk Aplikasi CRUD Sederhana:** Menyimpan event sourcing untuk form pendaftaran profil blog biasa hanya akan membuang waktu dan menambah lapisan kompleksitas yang tidak dibutuhkan.
- **Jangan Gunakan CQRS Jika Konsistensi Seketika (*Immediate Read-After-Write*) Diwajibkan Mutlak:** Karena sinkronisasi antara Write Model ke Read Model bersifat asinkron (*Eventual Consistency* dengan delay beberapa milidetik), query yang dieksekusi 1 milidetik setelah write mungkin belum melihat data baru.

---

## 15. Common Mistakes
1. **Mengabaikan Idempotensi pada Transaksi Kompensasi:** Mengirim perintah refund kompensasi tanpa `idempotency_key`. Jika jaringan putus saat kompensasi di-retry, nasabah bisa mendapatkan refund dua kali!
2. **Event Schema Versioning Diabaikan:** Mengubah struktur payload event di Event Store tanpa membuat versi baru (`OrderCreated_v2`). Akibatnya, saat kode melakukan replay event lama versi 1, deserializer crash karena field yang diharapkan tidak ada.
3. **Event Store Tanpa Snapshotting:** Membiarkan sebuah entitas merekam 500.000 event tanpa pernah membuat *Snapshot*. Setiap kali entitas di-load ke memori, server membutuhkan waktu 10 detik hanya untuk merekonstruksi status dari event pertama!
4. **Membiarkan State Tergantung pada Read Model di Sisi Write:** Membuat validasi logika bisnis di Command Handler dengan cara melakukan query ke Read DB (yang bisa jadi masih *stale/stuck lag*), melanggar integritas invariant bisnis.

---

## 16. Best Practices

### Must Have
- Desain seluruh transaksi kompensasi pada Saga agar bersifat **Idempotent** dan **Tidak Pernah Gagal (*Must Eventually Succeed*)**.
- Buat mekanisme **Periodic Snapshotting** pada Event Sourcing (misal: buat snapshot status setiap kelipatan 100 event) untuk menjaga waktu replay tetap di bawah 5 ms.
- Gunakan pengidentifikasi korelasi (**Correlation ID / Causation ID**) pada setiap event untuk mempermudah penelusuran rantai transaksi di log terdistribusi.

### Recommended
- Gunakan **Saga Orchestration** jika alur transaksi melibatkan lebih dari 3 service atau jika bisnis Anda membutuhkan visibilitas status transaksi real-time di admin portal.
- Informasikan karakteristik *Eventual Consistency* pada antarmuka pengguna (UI/UX) dengan pola optimistik (misal: tampilkan status "Pesanan Anda sedang diproses..." alih-alih langsung memuat ulang data sebelum sinkronisasi selesai).

### Advanced
- Gabungkan Event Sourcing dengan **Outbox Pattern** dan CDC (Debezium) untuk menjamin penerbitan event ke Kafka 100% konsisten tanpa risiko Dual-Write.

---

## 17. Troubleshooting

| Gejala Masalah | Indikasi Akar Masalah | Langkah Investigasi | Tindakan Perbaikan |
|---|---|---|---|
| **Saga Terjebak di Status Menengah (*Stuck State*)** | Service downstream tidak mengirimkan ACK reply ke Orchestrator | Periksa log timer timeout Orchestrator | Pasang dead-letter timer dan jalankan kompensasi otomatis jika timeout tercapai |
| **Read Model CQRS Mengalami Keterlambatan (*Projection Lag*)** | Worker proyeksi terhambat lonjakan event atau crash | Cek metrik `consumer_lag` pada broker event | Tingkatkan jumlah partisi dan scale up worker proyeksi |
| **Replay Event Sourcing Sangat Lambat saat Startup** | Entitas memiliki ribuan event tanpa ada file snapshot | Analisis jumlah event per Aggregate ID di Event Store | Jalankan job background untuk menghasilkan snapshot komposit status terakhir |

---

## 18. Exercise
1. Tulis simulasi Event Sourcing untuk entitas `OrderTicket`.
2. Rekam 5 event berurutan: `TICKET_CREATED`, `SEAT_ASSIGNED`, `PASSENGER_ADDED`, `UPGRADED_TO_VIP`, dan `TICKET_CANCELLED`.
3. Putar ulang (*replay*) seluruh event tersebut dan buktikan status akhir tiket sesuai dengan akumulasi seluruh perubahan.

---

## 19. Challenge
Rancang arsitektur Saga Orchestrator untuk sistem reservasi e-commerce Flash Sale:
1. Layanan yang terlibat: *OrderService*, *PaymentService*, *WarehouseService*, dan *CourierService*.
2. Rancang tabel state machine `saga_instances` yang menyimpan status transisi setiap langkah.
3. Simulasikan kegagalan pada langkah ke-3 (Kurir kehabisan armada) dan tunjukkan log eksekusi transaksi kompensasi yang memulihkan uang nasabah dan stok barang!

---

## 20. Summary
Transaksi terdistribusi bukanlah hal yang harus ditakuti, melainkan sebuah kepastian matematis saat sistem berkembang melintasi batas mesin tunggal. Dengan menguasai pola Saga Orchestration untuk menjamin konsistensi bisnis, memanfaatkan Event Sourcing sebagai sumber kebenaran historis mutlak, dan memisahkan baca-tulis melalui CQRS, Anda telah menguasai puncak rekayasa arsitektur backend modern.

---
[⬅️ Module 01: Monolith, Microservices, & DDD](./Module-01-Monolith-Modular-Microservices-dan-DDD.md) | [📋 Silabus Induk](../README.md) | [BAB 10 Quiz & Challenge ➡️](./BAB-10-Quiz-dan-Challenge.md)
---
