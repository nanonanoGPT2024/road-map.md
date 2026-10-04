# MODULE 04: Teori Terdistribusi: CAP Theorem & PACELC Theorem

## 1. Learning Objective
Setelah menyelesaikan module ini, Anda mampu:
1. Menjelaskan secara matematis dan fisik mengapa **Partition Tolerance (P)** adalah keniscayaan yang tidak bisa ditolak dalam jaringan komputer.
2. Membedakan trade-off arsitektur antara **CP System** (*Consistent & Partition Tolerant*) dan **AP System** (*Available & Partition Tolerant*).
3. Menganalisis batasan sistem dalam kondisi normal (tanpa partisi jaringan) menggunakan **PACELC Theorem**.
4. Membandingkan paradigma **ACID** (sistem relasional terpusat) vs **BASE** (sistem terdistribusi modern).
5. Menerapkan formula **Quorum Consensus ($W + R > N$)** untuk mengatur *Tunable Consistency* pada database terdistribusi.

---

## 2. Prerequisite
- Telah menyelesaikan [Module 03: High Availability, SLA, SLO, & SLI](./Module-03-High-Availability-SLA-SLO-SLI.md).
- Memahami konsep dasar replikasi data antar server.

---

## 3. Concept
Dalam rekayasa sistem terdistribusi, **CAP Theorem** (diperkenalkan oleh Eric Brewer pada tahun 2000) adalah hukum fundamental yang menyatakan bahwa sebuah sistem penyimpanan data terdistribusi hanya dapat menjamin secara bersamaan maksimal **dua dari tiga** jaminan berikut:
1. **Consistency (C):** Setiap operasi baca (*read*) menerima data penulisan (*write*) terbaru atau menghasilkan error.
2. **Availability (A):** Setiap request yang masuk ke node yang sehat selalu menerima respon non-error, tanpa jaminan bahwa respon tersebut berisi data paling mutakhir.
3. **Partition Tolerance (P):** Sistem tetap dapat beroperasi meskipun terjadi kehilangan atau keterlambatan pesan dalam jumlah besar antar-node akibat kegagalan jaringan.

---

## 4. Why? (Mengapa Memahami Ini Wajib?)

### Mitos "CA System" di Dunia Nyata
Banyak literatur usang menggambarkan CAP sebagai segitiga di mana arsitek bebas memilih: CA, CP, atau AP.

> **Kenyataan Keras Sistem Nyata:** Dalam jaringan komputer fisik kabel optik, switch, dan router, **Partisi Jaringan (Network Partition) PASTI AKAN TERJADI**. Kabel bisa putus, latency spike bisa memicu timeout, dan firewall bisa salah memblokir traffic antar server.

Karena **Partition Tolerance (P) wajib ada**, pilihan riil seorang arsitek terdistribusi **HANYA ADA DUA**:
$$\text{Pilihan Nyata} = \mathbf{CP} \quad \text{atau} \quad \mathbf{AP}$$
- **Jika memilih CP:** Saat jaringan antar data center terputus, sistem menolak request pengguna (*menolak availability*) demi mencegah data corrupt/inkonsisten.
- **Jika memilih AP:** Saat jaringan terputus, sistem tetap melayani request pengguna (*menjamin availability*), dengan risiko data yang dibaca adalah data usang (*stale data*) atau terjadi write conflict.

---

## 5. What? (Definisi Detail & PACELC)

### A. Tiga Pilar CAP Theorem
1. **Consistency (Linearizability / Strong Consistency):**
   - Bukan "C" pada ACID database relasional (Consistency pada ACID berarti kepatuhan terhadap aturan schema/foreign key).
   - "C" pada CAP adalah **Linearizability**: Setelah operasi penulisan bernilai $X$ sukses, seluruh operasi pembacaan di node mana pun di dunia detik itu juga wajib melihat nilai $X$.
2. **Availability:**
   - Setiap node yang tidak crash wajib mengembalikan jawaban non-error.
   - Mengembalikan HTTP 500 Internal Server Error atau Timeout dianggap melanggar Availability dalam definisi CAP.
3. **Partition Tolerance:**
   - Jaringan terdistribusi terbelah menjadi 2 atau lebih kelompok pulau terisolasi (*network partitions*) yang tidak bisa saling berkomunikasi.

### B. PACELC Theorem (Ekstensi Modern Daniel Abadi)
CAP Theorem hanya menjelaskan apa yang terjadi **saat ada partisi jaringan**. Namun, 99.9% waktu operasional sistem berjalan dalam kondisi jaringan **normal (tanpa partisi)**.

**PACELC** menjawab: *Bagaimana sistem berperilaku saat jaringan normal?*

```text
               STRUKTUR TEOREMA PACELC

  If Partition (P)  ────────▶  Pilih Availability (A) ATAU Consistency (C)
  
  Else (E) (Normal) ────────▶  Pilih Latency (L)      ATAU Consistency (C)
```

| Tipe Sistem | Perilaku Saat Partisi | Perilaku Saat Normal | Contoh Teknologi |
|---|---|---|---|
| **PC/EC** | Memilih Consistency | Memilih Consistency (Rela Latensi Naik) | Bigtable, Spanner, MongoDB (majority write) |
| **PA/EL** | Memilih Availability | Memilih Latency Rendah (Replikasi Async) | Cassandra, DynamoDB, Riak |
| **PC/EL** | Memilih Consistency | Memilih Latency Rendah saat normal | PostgreSQL / MySQL (Async Replication) |

### C. ACID vs BASE

```text
      ACID (Pilihan Sistem CP)           BASE (Pilihan Sistem AP)
      ------------------------           ------------------------
A - Atomicity                      BA - Basically Available
C - Consistency (Invariants)        S - Soft State
I - Isolation                       E - Eventual Consistency
D - Durability
```
- **ACID:** Mengutamakan integritas mutlak (misal: saldo perbankan). Operasi diblokir jika konsistensi tidak bisa dijamin.
- **BASE:** Mengutamakan ketersediaan layanan. Data diperbolehkan berada dalam kondisi sementara (*Soft State*), dan lambat laun seluruh node akan sinkron (*Eventual Consistency*).

---

## 6. How? (Formula Quorum Consensus: W + R > N)

Bagaimana database terdistribusi seperti Apache Cassandra dan Amazon DynamoDB mengatur konsistensi secara dinamis? Mereka menggunakan formula **Quorum**:
- $N$ = Jumlah total replica yang menyimpan salinan data.
- $W$ = Jumlah replica yang wajib mengonfirmasi penulisan (*write acknowledgement*) sebelum write dianggap sukses.
- $R$ = Jumlah replica yang wajib dibaca (*read response*) sebelum data dikembalikan ke client.

```text
               PRINSIP OVERLAPPING QUORUM (W + R > N)

         Node 1           Node 2           Node 3
    +--------------+ +--------------+ +--------------+
    | Write Sukses | | Write Sukses | | Data Usang   |
    | (Versi v2)   | | (Versi v2)   | | (Versi v1)   |
    +--------------+ +--------------+ +--------------+
    \______________ ______________/   \______________/
                   v                                  v
              Write Quorum (W=2)                 Node Tertinggal
             
    Client membaca Quorum (R=2):
    Membaca [Node 2 (v2)] dan [Node 3 (v1)]
    Client membandingkan timestamp/versi -> Memilih v2 (Strong Consistency Tercapai!)
```

### Konfigurasi Tingkat Konsistensi:
1. **Strong Consistency ($W + R > N$):**
   - Misal $N = 3, W = 2, R = 2 \implies 2 + 2 = 4 > 3$.
   - Dijamin selalu ada minimal 1 node dalam read quorum yang memiliki data penulisan terbaru.
2. **High Throughput / Weak Consistency ($W + R \le N$):**
   - Misal $N = 3, W = 1, R = 1 \implies 1 + 1 = 2 \le 3$.
   - Sangat cepat (latensi super rendah), namun ada risiko pembacaan membaca data usang.

---

## 7. Analogy: Janji Janjian Dokter Gigi
Bayangkan sebuah klinik gigi dengan 2 resepsionis: **Andi (Klinik Lantai 1)** dan **Budi (Klinik Lantai 2)**. Keduanya mencatat jadwal pasien di buku masing-masing dan saling menyinkronkan lewat telepon.

- **Kondisi Partisi Jaringan:** Kabel telepon antar lantai terputus.
- **Skenario Pasien Datang ke Lantai 1 Mau Membatalkan Janji:**
  - **Opsi CP (Consistency):** Andi berkata: *"Maaf, telepon ke Lantai 2 terputus. Saya tidak bisa memverifikasi jadwal dengan Budi, jadi saya menolak memproses perubahan Anda saat ini."* (Klinik menolak layanan demi mencegah jadwal ganda).
  - **Opsi AP (Availability):** Andi berkata: *"Baik, saya catat pembatalan Anda."* Sementara itu di Lantai 2, Budi yang tidak tahu telepon putus tetap mengonfirmasi pasien lain di jam yang sama. Jadwal menjadi ganda (*inkonsistensi data*).

---

## 8. Diagram: Skenario Partisi Jaringan Nyata

```text
                  PARTISI JARINGAN (SPLIT BRAIN POTENSIAL)

      [ WILAYAH ASIA - Data Center A ]       [ WILAYAH EROPA - Data Center B ]
      
             +---------------+                      +---------------+
             |    Node 1     |                      |    Node 2     |
             |  Saldo = $100 |                      |  Saldo = $100 |
             +-------+-------+                      +-------+-------+
                     ▲                                      ▲
                     │          Kabel Bawah Laut Putus      │
                     X - - - - - - - - X - - - - - - - - - -X
                     │                                      │
           User A (Tarik $100)                     User B (Tarik $100)
```
- Jika sistem memilih **AP**: Kedua user berhasil menarik $100 (Total keluar $200 dari saldo asli $100!). Bank mengalami kerugian akibat inkonsistensi.
- Jika sistem memilih **CP**: Node yang terisolasi dari mayoritas akan menolak transaksi User B dengan pesan error sampai kabel tersambung kembali.

---

## 9. Simple Example
- **Sistem ATM Bank (Harus CP):** Lebih baik ATM menampilkan layar *"Maaf, mesin sedang offline/gangguan"* daripada mengeluarkan uang tunai tetapi gagal mengurangi saldo rekening Anda.
- **Sistem Jumlah Like Instagram / Tweet (Cukup AP):** Jika jumlah like pada video reels Anda tertulis 1.450 di Jakarta dan 1.442 di London selama 3 detik, tidak ada orang yang dirugikan. Yang terpenting tombol like tidak pernah macet (*Available*).

---

## 10. Practical Example
Lihat simulasi interaktif partisi jaringan, perbandingan mode CP vs AP, dan verifikasi formula Quorum pada hands-on lab:
`System-Design/BAB-01-Fondasi-Skalabilitas/hands-on/m04/cap_partition_sim.js`

---

## 11. Real World Example

### 1. Google Spanner: CP System Skala Global dengan Jam Atom
Google Spanner adalah database relasional global yang menjamin **External Consistency (Linearizability)** dan ketersediaan tinggi 99.999%. Bagaimana Spanner mengatasi CAP?
Google memasang **GPS receiver dan Atomic Clock (Jam Atom Cesium)** di setiap data centernya (*TrueTime API*). Ketidakpastian waktu sinkronisasi ditekan hingga di bawah 7 milidetik secara fisik.

### 2. Amazon DynamoDB & Apache Cassandra (Tunable Consistency)
Cassandra memungkinkan developer menentukan tingkat konsistensi pada setiap query:
```sql
-- Client bebas memilih trade-off pada level baris kode:
CONSISTENCY ONE;    -- Menjadi AP (latensi < 2ms, ketersediaan tinggi)
CONSISTENCY QUORUM; -- Menjadi CP (latensi sedikit naik, jaminan data konsisten)
```

---

## 12. Trade-offs (CP System vs AP System)

| Dimensi | CP System (Consistency & Partition) | AP System (Availability & Partition) |
|---|---|---|
| **Perilaku saat Partisi** | Menolak request / Return Error | Menerima request / Mengembalikan data usang |
| **Karakteristik Latensi** | Lebih tinggi (butuh konsensus multi-node) | Sangat rendah (cukup respon 1 node terdekat) |
| **Resolusi Konflik** | Tidak perlu (konflik dicegah di awal) | Wajib ada (Last-Write-Wins, CRDTs, Vector Clocks) |
| **Use Case Utama** | Perbankan, Reservasi Tiket, Auth/Inventory | Feed Media Sosial, Shopping Cart, Telemetri IoT |
| **Contoh Database** | PostgreSQL Master-Replica, etcd, ZooKeeper | Apache Cassandra, Couchbase, ScyllaDB |

---

## 13. When To Use

### Pilih CP Jika:
- Bisnis Anda bergantung pada **kebenaran data mutlak**: sistem finansial, inventory stok barang langka (tiket konser tinggal 1 kursi), manajemen kunci otentikasi/token OAuth.
- Kesalahan data ganda (*double-spending*) menimbulkan kerugian legal atau finansial.

### Pilih AP Jika:
- Ketersediaan sistem lebih penting daripada kesegaran data sesaat.
- Bisnis Anda dapat menerima **Eventual Consistency** (misal: comment section, status timeline media sosial, metrics aggregator).

---

## 14. When NOT To Use
- Jangan gunakan arsitektur AP murni untuk pencatatan saldo dompet digital (*e-wallet*). Saldo negatif akan tercipta jika user melakukan penarikan simultan di dua lokasi partisi jaringan.

---

## 15. Common Mistakes
1. **Mengira "Eventual Consistency" Berarti "Tidak Konsisten":** Eventual consistency menjamin data pasti akan identik di semua node, asalkan tidak ada pembaruan baru setelah jeda waktu tertentu (biasanya beberapa ratus milidetik).
2. **Menyimpan Metadata State Terdistribusi di Database AP:** Menyimpan state kepemilikan lock terdistribusi di Cassandra/DynamoDB tanpa conditional write, memicu race condition parah. Gunakan sistem CP berbasis Raft/Paxos seperti **etcd** atau **Consul**.

---

## 16. Best Practices

- **Must Have:**
  - Pahami jenis data Anda: Pisahkan data berkarakteristik CP (pembayaran) dan data berkarakteristik AP (analitik/log).
- **Recommended:**
  - Gunakan **Idempotency Key** pada setiap penulisan di sistem AP untuk mencegah eksekusi duplikat saat network retry.
- **Advanced:**
  - Terapkan struktur data **CRDT** (*Conflict-free Replicated Data Types*) pada sistem AP multi-region untuk penggabungan data otomatis tanpa benturan logika (*conflict-free merge*).
- **Avoid / Overengineering:**
  - Memaksakan Distributed 2-Phase Commit (2PC) antar data center beda benua yang akan memperlambat response time hingga detik-an.

---

## 17. Troubleshooting Guide
```text
Gejala: Data yang baru saja disimpan pengguna tidak muncul saat halaman di-refresh.
---------------------------------------------------------------------------------
Kemungkinan Akar Masalah:
1. Fenomena "Read-Your-Own-Writes Inconsistency" pada replikasi asynchronous.
2. Request penulisan mendarat di Primary Node, tetapi request pembacaan diarahkan ke Read Replica yang mengalami jeda replikasi (Replication Lag 200ms).

Solusi Arsitektur:
- Terapkan "Session Consistency" atau "Read-After-Write Consistency":
  Setelah operasi penulisan, arahkan seluruh pembacaan user tersebut ke Primary Node selama 2 detik berikutnya, baru kemudian dialihkan kembali ke Read Replicas.
```

---

## 18. Hands-on Lab: Simulator Partisi Jaringan & Quorum Consensus

File lab sudah disiapkan di:
`System-Design/BAB-01-Fondasi-Skalabilitas/hands-on/m04/cap_partition_sim.js`

### Jalankan Uji Coba:
Buka terminal dan jalankan:
```bash
node System-Design/BAB-01-Fondasi-Skalabilitas/hands-on/m04/cap_partition_sim.js
```

### Yang Ditampilkan Script Ini:
1. Mensimulasikan cluster 3 node terdistribusi ($N = 3$).
2. Memutuskan sambungan jaringan antara Node 1 dengan Node 2 & 3 (*Network Partition Simulation*).
3. Menguji perilaku sistem dalam dua mode:
   - **Mode CP:** Node minoritas menolak penulisan data demi menjaga konsistensi.
   - **Mode AP:** Node minoritas tetap menerima data, lalu mendeteksi adanya data divergence (konflik versi).

---

## 19. Exercises (Latihan)

### Level 1 (Easy):
Sebutkan 3 komponen dari CAP Theorem dan jelaskan secara singkat mengapa sistem terdistribusi tidak bisa memilih "CA" saat terjadi partisi jaringan!

### Level 2 (Medium):
Sebuah database Cassandra memiliki cluster dengan faktor replikasi $N = 5$.
1. Berapa nilai minimum $W$ (Write Quorum) dan $R$ (Read Quorum) yang harus dipasang agar sistem menjamin **Strong Consistency**?
2. Jika Anda mengatur $W = 1$ dan $R = 1$, apa keuntungan dan kerugiannya terhadap latensi dan konsistensi data?

### Level 3 (Hard):
Jelaskan perbedaan mendasar antara **CAP Theorem** dan **PACELC Theorem**. Berikan contoh skenario nyata di mana teorema PACELC mampu menjelaskan trade-off sistem yang tidak tercakup oleh teorema CAP!

---

## 20. Summary & Knowledge Check
- [ ] Memahami arti presisi Consistency (Linearizability), Availability, dan Partition Tolerance.
- [ ] Memahami mengapa dalam jaringan fisik nyata, pilihannya selalu antara **CP** atau **AP**.
- [ ] Menguasai teorema **PACELC** untuk mengevaluasi trade-off Latency vs Consistency saat jaringan normal.
- [ ] Mampu menerapkan formula Quorum Consensus ($W + R > N$).
