# MODULE 02: Database Replication, Read Replicas, & Failover

## 1. Learning Objective
Setelah menyelesaikan module ini, Anda mampu:
1. Merancang topologi database **Primary-Replica (Master-Standby)** untuk meningkatkan kapasitas pembacaan (*Read Scaling*) dan ketersediaan tinggi (*High Availability*).
2. Membandingkan secara teknis trade-off antara **Synchronous**, **Asynchronous**, dan **Semi-Synchronous Replication**.
3. Mendiagnosa dan memitigasi anomali **Replication Lag** serta fenomena **Read-Your-Own-Writes Inconsistency**.
4. Mengukur dampak keandalan menggunakan **RTO** (*Recovery Time Objective*) dan **RPO** (*Recovery Point Objective*).
5. Mengimplementasikan simulasi replication lag dan mitigasi session consistency menggunakan hands-on script.

---

## 2. Prerequisite
- Telah menyelesaikan [BAB 05 — Module 01: RDBMS Scaling, Indexing, & ACID](./Module-01-RDBMS-Scaling-Indexing-dan-ACID.md).
- Memahami konsep dasar transaksi dan Write-Ahead Logging (WAL).

---

## 3. Concept
Dalam sebagian besar aplikasi internet modern (seperti Instagram, Twitter, Wikipedia, atau E-Commerce), pola beban kerja database didominasi secara masif oleh pembacaan daripada penulisan:
$$\text{Rasio Read : Write} \approx 10:1 \quad \text{hingga} \quad 100:1$$
Satu server database tunggal akan cepat kehabisan CPU dan koneksi jika harus melayani 50.000 query `SELECT` sekaligus menangani transaksi `INSERT/UPDATE`.

**Database Replication** adalah teknik menduplikasi data dari satu node database server (**Primary / Master**) ke satu atau beberapa node database lainnya (**Replicas / Standbys**). Primary bertugas mengeksekusi seluruh operasi penulisan (*Write/Update/Delete*), sedangkan kumpulan Replicas didedikasikan untuk melayani operasi pembacaan (*Read Scaling*).

---

## 4. Why? (Mengapa Read Replicas Tidak Menyelesaikan Masalah Write?)

### Miskonsepsi Fatal Arsitek Pemula
> *"Traffic transaksi penulisan aplikasi kita naik 10x lipat, mari tambahkan 5 Read Replicas!"*

Ini adalah kesalahan pemahaman yang sangat berbahaya:
- **Read Replicas HANYA meningkatkan kapasitas baca (SELECT).**
- Menambah Read Replicas **TIDAK MENINGKATKAN** kapasitas penulisan sama sekali!
- Faktanya: Menambah terlalu banyak Read Replicas justru dapat **memperlambat Primary Server**, karena Primary harus membagi bandwidth CPU dan jaringan untuk mengalirkan log perubahan (*WAL / Binlog*) ke seluruh replica tersebut!

---

## 5. What? (Model Replikasi: Synchronous vs Asynchronous)

```text
       [ SYNCHRONOUS REPLICATION ]                   [ ASYNCHRONOUS REPLICATION ]
       
         Client                                        Client
           │                                             │
           ├── 1. Write Data                             ├── 1. Write Data
           │                                             │
           ▼                                             ▼
     [ PRIMARY DB ]                                [ PRIMARY DB ]
           │                                             │
           ├── 2. Replikasi WAL                          │ 2. Tulis Sukses!
           │                                             │◀── Langsung Respon ke Client!
           ▼                                             │
     [ REPLICA DB ]                                      ├── 3. Replikasi di Background...
           │                                             │      (Ada Replication Lag!)
           └── 3. Acknowledge Sukses                     ▼
                  │                                [ REPLICA DB ]
                  ▼
     [ PRIMARY merespon ke Client ]
```

### Tabel Komparasi Model Replikasi:

| Parameter | Synchronous Replication | Asynchronous Replication | Semi-Synchronous (Postgres/MySQL) |
|---|---|---|---|
| **Write Latency** | **Lambat** (Menunggu RTT jaringan ke replica) | **Sangat Cepat** (Instan commit di primary) | Cepat (Cukup menunggu 1 replica tercepat) |
| **Risiko Kehilangan Data (RPO)** | **Nol (RPO = 0)**. Data dijamin ada di 2 node | Ada risiko (Data yang belum terkirim hilang jika crash) | Sangat minim |
| **Availability saat Network Down** | Rentan (Jika replica mati, Primary menolak write) | Sangat Tinggi (Primary terus menerima write) | Tinggi (Fallback ke async jika replica down) |
| **Kesesuaian Penggunaan** | Sistem Finansial, Core Banking | Web Apps, E-Commerce, Social Media | Standar Industri Cloud Production |

---

## 6. How? (Replication Lag & Anomali Read-Your-Own-Writes)

### Anatomi Replication Lag
Dalam replikasi asinkron, ada jeda waktu (misal 50 ms hingga 2.000 ms) antara saat transaksi sukses di-commit di Primary hingga perubahan tersebut selesai diterapkan (*replayed*) di Replica. Jeda waktu ini disebut **Replication Lag**.

### Skenario Anomali "Read-Your-Own-Writes":
1. Budi mengubah nama profilnya dari *"Budi"* menjadi *"Budi Santoso"* di website (Request `POST /profile` mendarat di **Primary DB**).
2. Transaksi sukses. Halaman me-refresh otomatis.
3. Request pembacaan `GET /profile` diarahkan oleh load balancer ke **Read Replica 1**.
4. Read Replica 1 mengalami lag 500 ms dan belum menerima update tersebut.
5. Halaman kembali menampilkan nama lama: *"Budi"*.
6. Budi bingung dan panik mengira sistem error, lalu menekan tombol simpan berulang-ulang!

```text
               SOLUSI ARSITEKTUR: SESSION CONSISTENCY
               
                      [ HTTP Request ]
                              │
               Baru saja melakukan Write dalam 5 detik terakhir?
                              │
              ┌───────────────┴───────────────┐
              ▼ (YA)                          ▼ (TIDAK)
     [ BACA DARI PRIMARY DB ]        [ BACA DARI READ REPLICA ]
   (Dijamin 100% Konsisten)         (Meringankan Beban Primary)
```

---

## 7. Analogy: Kantor Berita & Surat Kabar Daerah
- **Primary Database:** Kantor redaksi pusat koran di Jakarta. Wartawan menulis berita baru (Write).
- **Asynchronous Replication:** Kantor pusat mencetak file PDF koran dan mengirimkannya via pesawat kargo ke percetakan daerah di Surabaya dan Medan (butuh waktu perjalanan = *Replication Lag*).
- **Read Replica:** Kios koran di Surabaya yang menjual koran ke masyarakat (Read). Pembaca di Surabaya membaca berita yang berusia 3 jam yang lalu, tetapi redaksi di Jakarta tidak terganggu melayani antrean pembaca koran eceran.

---

## 8. Diagram: Alur Automated Failover dengan Quorum (Patroni / Orchestrator)

```text
                  TOPOLOGI HIGH AVAILABILITY DATABASE

                     [ HEALTH CHECK & CONSENSUS ]
                      (etcd / Consul / ZooKeeper)
                                  │
                 ┌────────────────┴────────────────┐
                 ▼ (Heartbeat OK)                  ▼ (Heartbeat OK)
          +---------------+                 +---------------+
          |  PRIMARY DB   | ~ ~ Replikasi ~ |  REPLICA DB   |
          |  (10.0.1.10)  |      Stream     |  (10.0.1.20)  |
          +---------------+                 +---------------+
                 ▲                                 ▲
                 │ (Primary Crash!)                │ (Promosi Menjadi Master Baru!)
                 X                                 │
          [ Virtual IP / Route53 DNS ] ────────────┘
          (Mengarahkan Traffic Write ke 10.0.1.20)
```

---

## 9. Simple Example: Routing Query di Level Kode Backend
```javascript
// Database Router Helper
const primaryDB = createConnection({ host: 'primary.db.internal' });
const replicaPool = createConnectionPool({ host: 'reader.db.internal' });

async function executeQuery(sql, params, isWriteOperation = false, userLastWriteTime = 0) {
  const isRecentWriter = (Date.now() - userLastWriteTime) < 3000; // Jeda 3 detik

  // Jika operasi write ATAU user baru saja melakukan penulisan -> Arahkan ke Primary
  if (isWriteOperation || isRecentWriter) {
    return primaryDB.query(sql, params);
  }

  // Jika query baca biasa -> Arahkan ke Read Replica Pool
  return replicaPool.query(sql, params);
}
```

---

## 10. Practical Code Example
Lihat simulasi replication lag, anomali stale reads, dan mekanisme resolusi session consistency pada:
`System-Design/BAB-05-Arsitektur-Basis-Data/hands-on/m02/replication_lag_sim.js`

---

## 11. Real World Example: Insiden Data Loss GitLab (2017)
- **Kronologi Insiden:** Pada awal 2017, database primary PostgreSQL GitLab mengalami lonjakan beban akibat spammer. Replikasi ke secondary node mengalami **Replication Lag parah (tertinggal puluhan Gigabyte)**.
- Saat tim engineer mencoba memperbaiki lag secara manual, terjadi kesalahan eksekusi perintah terminal yang secara keliru menghapus direktori database primary asli!
- Saat mencoba melakukan failover ke replica secondary, ternyata proses backup berkala dan snapshot disk otomatis tidak berjalan selama berbulan-bulan. GitLab harus offline selama berjam-jam dan kehilangan data issue/komentar selama 6 jam terakhir.
- **Pelajaran Mahal:** Replikasi bukanlah backup! Automated monitoring replication lag dan Disaster Recovery test wajib diuji secara berkala.

---

## 12. Trade-offs (Single Primary vs Multi-Primary)

| Dimensi | Single-Primary (Standard) | Multi-Primary (Multi-Master) |
|---|---|---|
| **Penanganan Write** | Sangat Sederhana (Hanya 1 node yang menerima write) | Sangat Sulit (Bisa menulis di node mana saja) |
| **Konflik Data** | Nol (Tidak ada benturan transaksi write) | **Tinggi!** (Butuh mekanisme Conflict Resolution) |
| **Kapasitas Write** | Terbatas pada kapasitas 1 mesin Primary | Skalabilitas write terdistribusi |
| **Kompleksitas Operasional** | Rendah - Menengah | Sangat Tinggi (Galera, CockroachDB, Spanner) |

---

## 13. When To Use What
- **Gunakan Single-Primary dengan Read Replicas:** Untuk 95% aplikasi web konvensional di mana rasio read jauh lebih dominan daripada write.
- **Gunakan Multi-Region Read Replicas:** Untuk melayani pengguna global agar query pembacaan data katalog lokal dieksekusi di data center terdekat (misal: Read Replica di Eropa untuk user Eropa).

---

## 14. When NOT To Use Read Replicas
- Jangan gunakan Read Replicas jika aplikasi Anda adalah platform penulisan log / telemetri sensor IoT (*Write-Heavy / Ingestion-Only System*). Untuk kasus ini, gunakan time-series database (TimescaleDB / ClickHouse) atau Message Queue (Kafka).

---

## 15. Common Mistakes
1. **Mengirim Query Mutasi Data ke Read Replica:** Mengirimkan perintah `INSERT/UPDATE` ke connection string replica yang berstatus `read_only = on`. Transaksi akan langsung gagal dengan error `cannot execute INSERT in a read-only transaction`.
2. **Tidak Memantau Ukuran WAL / Binlog Saat Replica Lambat:** Jika replica tertinggal terlalu jauh, Primary terpaksa menahan file log WAL di disk. Disk primary bisa penuh 100% dan menyebabkan database utama mogok!
3. **Mengabaikan Connection Limits Saat Menambah Replica:** Menambah 10 replica tetapi tidak menggunakan Connection Pooler (seperti PgBouncer), sehingga jumlah koneksi membengkak dan menghabiskan RAM database.

---

## 16. Best Practices

- **Must Have:**
  - Pasang **Connection Pooler terpisah** (misal: PgBouncer untuk Postgres, ProxySQL untuk MySQL) di depan cluster database.
  - Terapkan alarm monitoring: Bunyikan notifikasi PagerDuty jika **Replication Lag > 5 detik**.
- **Recommended:**
  - Terapkan pola **Session Consistency (Sticky Primary Routing)** selama beberapa detik setelah user melakukan operasi penulisan.
- **Advanced:**
  - Gunakan orchestrator HA otomatis seperti **Patroni** (berbasis Raft/Consul) untuk failover otomatis tanpa campur tangan manusia.
- **Avoid / Overengineering:**
  - Membangun database Multi-Master sinkron antar-benua dengan latensi jaringan 200 ms. Latensi setiap transaksi write Anda akan melonjak hingga 1 detik!

---

## 17. Troubleshooting Guide
```text
Gejala: Replication Lag tiba-tiba melonjak dari 10ms menjadi 120 detik.
---------------------------------------------------------------------
Penyebab:
1. Ada query analitik laporan besar (SELECT raksasa) yang sedang berjalan di Read Replica, mengunci tabel dan memblokir thread replay log.
2. Spesifikasi hardware CPU/Disk I/O di Read Replica lebih kecil daripada Primary Server.

Solusi:
- Pastikan spesifikasi mesin Read Replica IDENTIK dengan Primary Server.
- Di PostgreSQL, setel parameter:
  max_standby_archive_delay = 30s
  max_standby_streaming_delay = 30s
  (Replica akan otomatis membatalkan query analitik yang memblokir proses replikasi).
```

---

## 18. Hands-on Lab: Simulator Replication Lag & Session Consistency

File lab sudah disiapkan di:
`System-Design/BAB-05-Arsitektur-Basis-Data/hands-on/m02/replication_lag_sim.js`

### Jalankan Uji Coba:
Buka terminal dan jalankan:
```bash
node System-Design/BAB-05-Arsitektur-Basis-Data/hands-on/m02/replication_lag_sim.js
```

### Yang Ditampilkan Script Ini:
1. Menyimulasikan arsitektur Primary DB dan Read Replica dengan Replication Lag buatan sebesar 200 ms.
2. Menunjukkan bug **Stale Read**: Klien membaca dari Replica tepat setelah menulis ke Primary (menghasilkan data nama lama!).
3. Menunjukkan perbaikan dengan **Session Consistency Router**: Klien diarahkan ke Primary jika baru saja menulis (< 1 detik), membuktikan data yang dibaca 100% mutakhir.

---

## 19. Exercises (Latihan)

### Level 1 (Easy):
Sebutkan perbedaan antara metrik **RTO (Recovery Time Objective)** dan **RPO (Recovery Point Objective)** dalam rencana penanggulangan bencana (*Disaster Recovery*) database!

### Level 2 (Medium):
Sebuah aplikasi web memiliki 1 Primary DB dan 3 Read Replicas. Pengguna baru mendaftar akun (`POST /register`), lalu langsung diarahkan ke halaman selamat datang (`GET /dashboard`).
1. Apa anomali yang bisa dialami pengguna jika query `GET /dashboard` diarahkan secara acak ke salah satu Read Replica?
2. Sebutkan 2 pendekatan arsitektur untuk menyelesaikan masalah tersebut!

### Level 3 (Hard):
Jelaskan bagaimana arsitektur konsensus **Raft / Paxos** (seperti pada tool Patroni) mampu mencegah bencana **Split-Brain** ketika Primary database lama sempat terputus dari jaringan selama 30 detik lalu menyala kembali saat Replica sudah diangkat menjadi Primary baru!

---

## 20. Summary & Knowledge Check
- [ ] Memahami alasan mengapa Read Replicas hanya men-scale pembacaan, bukan penulisan.
- [ ] Memahami trade-off Synchronous vs Asynchronous vs Semi-synchronous replication.
- [ ] Menguasai penyebab dan dampak dari Replication Lag.
- [ ] Mampu menerapkan pola Session Consistency untuk mencegah anomali Read-Your-Own-Writes.
- [ ] Memahami arsitektur automated failover dan pencegahan Split-Brain.
