---
[⬅️ Module 02: Transaksi Terdistribusi, Saga, & CQRS](./Module-02-Transaksi-Terdistribusi-Saga-Event-Sourcing-CQRS.md) | [📋 Silabus Induk](../README.md) | [CAPSTONE PROJECT ➡️](../CAPSTONE-PROJECT-Enterprise-Omnichannel-Payment-Backend.md)
---

# BAB 10: Evaluasi Pemahaman, Quiz, & Tantangan Arsitektur Lanjutan, DDD, Saga, & CQRS

Selamat! Anda telah menuntaskan **BAB 10: Arsitektur Backend Lanjutan & Skalabilitas Sistem**, bab penutup dari kurikulum teori dan praktik Backend Developer Mastery. Dokumen ini menguji kapasitas arsitektural Anda dalam memecahkan masalah sistem enterprise terdistribusi skala besar.

---

## 1. Pertanyaan Konseptual Fundamental (Basic)

1. **Jelaskan perbedaan mendasar antara Monolith Tradisional, Modular Monolith, dan Distributed Microservices!** Mengapa Shopify memilih bertahan pada Modular Monolith dibanding memecah sistem menjadi ratusan microservices?
2. **Dalam Domain-Driven Design (DDD), apa perbedaan antara Entity dan Value Object?** Mengapa Value Object wajib bersifat *Immutable*?
3. **Apa fungsi utama dari Aggregate Root dalam arsitektur DDD?** Mengapa memodifikasi entitas anak secara langsung di database (tanpa melalui metode publik Aggregate Root) dianggap sebagai pelanggaran berat?
4. **Mengapa transaksi ACID Two-Phase Commit (2PC / XA) sangat jarang digunakan pada sistem cloud microservices modern?** Apa kelemahan utama koordinator 2PC saat terjadi partisi jaringan?
5. **Jelaskan konsep dasar Event Sourcing!** Apa perbedaan fundamental antara cara penyimpanan database CRUD biasa dengan Event Store berbasis append-only?

---

## 2. Pertanyaan Analisis & Rekayasa Sistem (Intermediate)

6. **Saga Choreography vs Saga Orchestration:**
   Bandingkan kedua pola implementasi Saga ini dari aspek *Coupling*, visibilitas alur bisnis (*Observability*), dan kemudahan menangani transaksi kompensasi saat melibatkan 6 microservices berbeda!
7. **Prinsip Kerja Transaksi Kompensasi (Semantic Rollback):**
   Mengapa transaksi kompensasi tidak bisa disamakan dengan perintah `ROLLBACK` SQL? Mengapa seluruh operasi transaksi kompensasi wajib dirancang bersifat **Idempotent**?
8. **Arsitektur CQRS (Command Query Responsibility Segregation):**
   Bagaimana pemisahan Write Model (dioptimalkan untuk konsistensi invariant bisnis) dan Read Model (terdenormalisasi di Elasticsearch/Redis) memecahkan kebuntuan skalabilitas pada sistem dengan rasio 99% Read vs 1% Write?
9. **Eventual Consistency pada Antarmuka Pengguna (UI/UX):**
   Karena pembaruan Read Model pada CQRS membutuhkan waktu propagasi asinkron (misal: 50 ms), bagaimana Anda mendesain pengalaman pengguna di frontend (UI) agar user tidak bingung ketika data yang baru saja mereka submit belum langsung muncul di tabel pencarian?
10. **Pola Migrasi Strangler Fig:**
    Jelaskan tahapan implementasi pola Strangler Fig saat memigrasikan modul pembayaran dari aplikasi Monolith PHP lama ke Microservices Go baru tanpa menimbulkan downtime operasional!

---

## 3. Studi Kasus Skenario Produksi (Scenario-Based)

### Skenario A: Kegagalan Pengiriman Barang & Bencana Saldo Tergantung
Sebuah platform travel mengorkestrasi pemesanan paket liburan yang melibatkan 3 microservices:
1. *FlightService* memotong kuota kursi pesawat (Sukses).
2. *HotelService* memesan kamar hotel (Sukses).
3. *CarRentalService* menyewa mobil (Gagal karena stok mobil habis).
Karena pengembang tidak mengimplementasikan alur kompensasi terotomasi, sistem berhenti di tengah jalan. Saldo nasabah sudah terpotong Rp 8.000.000, kursi pesawat dan kamar hotel terisi, namun voucher liburan tidak pernah terbit.
- **Identifikasi Masalah:** Mengapa ketiadaan pola Saga merusak kepercayaan pelanggan?
- **Rancang Solusi:** Buat diagram alur *Saga Orchestrator State Machine* lengkap dengan urutan panggilan *Compensating Transactions* untuk membatalkan hotel dan penerbangan secara elegan!

### Skenario B: Event Replay yang Terlalu Lambat pada Event Sourcing
Sebuah sistem core banking menggunakan Event Sourcing murni untuk mencatat mutasi rekening nasabah korporat. Akun korporat PT Makmur memiliki 850.000 riwayat transaksi dalam 3 tahun terakhir.
Setiap kali nasabah melakukan transaksi baru, aplikasi membutuhkan waktu 12 detik hanya untuk merekonstruksi status saldo terakhir dari event pertama di tahun 2023.
- **Analisis:** Mengapa waktu rekonstruksi agregat melonjak drastis?
- **Solusi Arsitektur:** Bagaimana implementasi **Snapshotting Pattern** (menyimpan potret saldo setiap kelipatan 500 event) memangkas waktu rekonstruksi dari 12 detik menjadi $< 5 \text{ ms}$?

### Skenario C: The Distributed Monolith Nightmare
Sebuah perusahaan rintisan memecah monolit mereka menjadi 25 microservices. Namun, seluruh 25 service tersebut terhubung ke satu server database MySQL yang sama (*Shared Database*). Setiap kali tim Order mengubah skema tabel `users`, 6 service lain langsung error. Selain itu, untuk melakukan deployment fitur baru, tim rilis harus mematikan dan menyalakan ke-25 service secara bersamaan.
- **Evaluasi:** Jelaskan mengapa arsitektur ini merupakan *Distributed Monolith Antipattern*!
- **Rencana Transformasi:** Rancang langkah-langkah dekomposisi database (*Database-per-Service*) dan penggunaan event asinkron untuk memutus kopling fisik tersebut!

---

## 4. Chapter Challenge: Desain Global Ride-Hailing & Logistics Platform

### Deskripsi Masalah
Sebagai Enterprise Principal Architect, Anda diminta merancang arsitektur backend generasi baru untuk platform Ride-Hailing & Logistics (skala Uber / Gojek):
1. **Domain-Driven Design (DDD):**
   - Identifikasi 4 Bounded Context: *Passenger Identity, Driver Matching & Geolocation, Trip Lifecycle & Dispatch, dan Billing & Payments*.
   - Rancang Aggregate Root untuk entitas `TripAggregate` lengkap dengan proteksi invariant statusnya (*REQUESTED -> MATCHED -> PICKED_UP -> COMPLETED / CANCELLED*).
2. **Saga Orchestrator Transaksi Pembayaran & Driver:**
   - Rancang state machine alur pemesanan perjalanan: Alokasi Driver -> Hold Saldo E-Wallet -> Selesai Perjalanan -> Settlement Dana Driver.
   - Sertakan alur kompensasi jika penumpang membatalkan perjalanan secara sepihak saat driver sudah menuju titik penjemputan (*Cancellation Fee Policy*).
3. **CQRS & Real-time Location Projection:**
   - Pisahkan aliran pembaruan koordinat GPS driver (100.000 driver mengirim GPS setiap 2 detik via UDP/WebSocket) ke dalam Read Model geospasial Redis GEO, terpisah dari transaksi riwayat perjalanan permanen di database PostgreSQL.

---

## 5. Knowledge Check & Mastery Checklist

### Saya Harus Memahami:
- [ ] Spektrum evolusi arsitektur: Kapan Monolith cukup, kapan Modular Monolith tepat, dan kapan Microservices benar-benar dibutuhkan.
- [ ] Pilar strategis DDD: Bounded Contexts, Ubiquitous Language, dan Context Mapping.
- [ ] Pilar taktis DDD: Aggregates, Aggregate Root, Entities, Value Objects, dan Domain Events.
- [ ] Batasan Two-Phase Commit (2PC) dan keunggulan Pola Saga berbasis Eventual Consistency.
- [ ] Perbedaan implementasi Saga Choreography vs Saga Orchestration.
- [ ] Paradigma Event Sourcing, Rekonstruksi Agregat, dan Snapshotting.
- [ ] Pemisahan Command Model dan Read Model pada pola CQRS.

### Saya Tidak Perlu Menghafal:
- Seluruh spesifikasi formal X/Open XA Distributed Transaction protocol.
- Sintaks spesifik library state machine tertentu (fokuslah pada logika transisi status dan idempotensi kompensasi).

### Saya Harus Bisa Melakukan:
- [ ] Merancang class Aggregate Root yang melindungi konsistensi data internalnya.
- [ ] Menulis Value Object yang terbukti immutable dengan operasi aritmatika yang mengembalikan instance baru.
- [ ] Membangun Saga Orchestrator yang mampu memutar balik transaksi (*Semantic Rollback*) saat salah satu langkah microservice gagal.
- [ ] Merekonstruksi status objek secara deterministik dari riwayat log Event Sourcing.

---
[⬅️ Module 02: Transaksi Terdistribusi, Saga, & CQRS](./Module-02-Transaksi-Terdistribusi-Saga-Event-Sourcing-CQRS.md) | [📋 Silabus Induk](../README.md) | [CAPSTONE PROJECT ➡️](../CAPSTONE-PROJECT-Enterprise-Omnichannel-Payment-Backend.md)
---
