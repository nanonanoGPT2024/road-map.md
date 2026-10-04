# Module 03: Event-Driven Architecture, CQRS, & Event Sourcing

## 1. Learning Objective
Setelah menyelesaikan modul ini, Anda akan mampu:
- Memahami pola arsitektur **Event-Driven Architecture (EDA)** dan variasinya (*Event Notification* vs *Event-Carried State Transfer*).
- Mengimplementasikan **CQRS (Command Query Responsibility Segregation)** untuk memisahkan model penulisan (*Write*) dan pembacaan (*Read*) data.
- Menguasai konsep **Event Sourcing**: menyimpan seluruh sejarah perubahan sebagai urutan *immutable domain events* alih-alih hanya menyimpan state terkini.
- Memahami konsep Projections, Materialized Views, dan strategi menghadapi *Eventual Consistency*.

## 2. Prerequisite
- Memahami perbedaan database relational (ACID) dan NoSQL.
- Memahami dasar event log dan message broker (Kafka/RabbitMQ) dari Module 01 & 02.

## 3. Concept
Pada aplikasi tradisional berbasis CRUD (Create, Read, Update, Delete), kita hanya menyimpan snapshot data terakhir di database. Ketika saldo rekening berubah dari Rp 100.000 menjadi Rp 80.000, database menimpa (*overwrite*) baris tersebut. Konteks mengapa, siapa yang mengubah, dan urutan mutasi hilang kecuali dicatat terpisah.

Dua pola arsitektur modern untuk mengatasi keterbatasan ini adalah:
1. **CQRS (Command Query Responsibility Segregation)**:
   Memisahkan jalur **Command** (mutasi data: Insert/Update/Delete dengan validasi bisnis ketat) dari jalur **Query** (pembacaan data yang dioptimasi untuk query cepat, agregasi, dan pencarian).
2. **Event Sourcing**:
   Alih-alih menyimpan *current state*, sistem menyimpan rentetan peristiwa masa lalu yang tidak dapat diubah (*immutable stream of domain events*). State saat ini dihitung dengan memutar ulang (*replaying*) seluruh event dari awal waktu:
   $$\text{Current State} = \sum (\text{All Historical Events})$$

## 4. Why?
- **Audit Trail Sempurna**: Di industri perbankan dan fintech, regulator menuntut bukti legalitas setiap perubahan saldo secara kronologis. Event sourcing memberikan audit trail bawaan (*built-in zero-effort audit*).
- **Asymmetric Scaling**: Rasio pembacaan (*Read*) terhadap penulisan (*Write*) pada aplikasi modern seringkali 100:1 atau 1000:1. CQRS memungkinkan kita menggunakan database write yang terfokus pada konsistensi (PostgreSQL) dan database read yang terfokus pada kecepatan baca (Elasticsearch, Redis, MongoDB).
- **Time Travel & Root Cause Analysis**: Anda dapat merekonstruksi kondisi sistem pada tanggal dan jam berapapun di masa lalu untuk menyelidiki bug atau fraud.

## 5. What?
### Komponen CQRS:
- **Command Model**: Menerima aksi pengguna (misal: `PlaceOrderCommand`). Melakukan validasi bisnis, memeriksa batas kredit, lalu memicu event.
- **Write Store (Event Store)**: Tempat penyimpanan event terurut (Append-Only).
- **Projector / Event Handler**: Worker yang mendengarkan event baru dan memperbarui *Read Model*.
- **Read Model (Materialized View)**: Database terdenormalisasi (misal Elasticsearch untuk full-text search produk, Redis untuk cached catalog) yang siap dibaca oleh API tanpa perlu `JOIN` tabel yang mahal.

### Komponen Event Sourcing:
- **Domain Event**: Pernyataan fakta masa lalu yang tidak dapat dibantah (*past tense*, misal: `OrderCreated`, `ItemAddedToCart`, `PaymentAuthorized`).
- **Aggregate**: Entitas bisnis (misal: `BankAccount`) yang merekonstruksi statusnya dari event stream.
- **Snapshot**: Cadangan state berkala (misal setiap 1000 event) agar rekonstruksi state tidak perlu membaca jutaan event dari hari pertama.

## 6. How?
### Alur Kerja CQRS + Event Sourcing
```text
[Client / UI]
   │
   ├── 1. POST /orders (Command) ──> [Command Handler]
   │                                         │
   │                                         ├── 2. Validasi Bisnis
   │                                         └── 3. Simpan Event ke [Event Store]
   │                                                     │
   │                                                     ▼ 4. Publish Domain Event
   │                                                [Message Bus]
   │                                                     │
   │                                                     ├── 5. [Projector Service]
   │                                                     │            │
   │                                                     │            ▼ 6. Update View
   │                                                     │   [Read DB: Elasticsearch]
   │                                                     │
   └── 7. GET /orders?status=active (Query) ─────────────┴──────> Read Fast View!
```

## 7. Analogy
- **CRUD Tradisional = Papan Tulis Kapur**: Setiap kali skor bertambah, angka lama dihapus dengan penghapus lalu ditulis angka baru. Anda hanya tahu skor akhir, bukan bagaimana jalannya pertandingan.
- **Event Sourcing = Buku Besar Kas Akuntansi (Accounting Ledger)**: Akuntan dilarang menghapus baris transaksi yang sudah dicatat. Jika ada salah transfer, akuntan membuat baris baru: *Koreksi Pembukuan Debit/Kredit*. Saldo akhir adalah penjumlahan dari seluruh baris debit dan kredit sejak hari pertama rekening dibuka.

## 8. Diagram

```text
================ EVENT SOURCING AGGREGATE RECONSTRUCTION ================

Event Store Stream for Account #ACC-001:
┌─────────────────────────────────────────────────────────────┐
│ 1. AccountOpened      { initialDeposit: 100.000 }           │
│ 2. MoneyDeposited     { amount: 50.000 }                    │
│ 3. MoneyWithdrawn     { amount: 20.000 }                    │
│ 4. InterestAdded      { amount: 1.500 }                     │
└─────────────────────────────────────────────────────────────┘
                               ↓ (Replay)
Calculated Current State: Balance = Rp 131.500

(Jika ada Snapshot di Event #3 [Balance: 130.000], cukup load snapshot lalu apply Event #4)
```

## 9. Simple Example
Event Sourcing Handler dalam Pseudocode:
```javascript
function applyEvent(state, event) {
  switch (event.type) {
    case 'AccountCreated':
      return { id: event.id, balance: event.initialBalance };
    case 'MoneyDeposited':
      return { ...state, balance: state.balance + event.amount };
    case 'MoneyWithdrawn':
      return { ...state, balance: state.balance - event.amount };
    default:
      return state;
  }
}
```

## 10. Practical Example: Event-Carried State Transfer vs Event Notification
- **Event Notification**: Pesan hanya berisi sinyal ringan: `{ event: "OrderUpdated", orderId: 101 }`. Consumer harus memanggil HTTP REST kembali ke Order Service untuk mengetahui data apa yang berubah. Ini membebani producer dengan query balik.
- **Event-Carried State Transfer (ECST)**: Pesan memuat seluruh data yang dibutuhkan:
  `{ event: "OrderPlaced", orderId: 101, customer: { id: 55, email: "user@test.com" }, items: [...] }`. Consumer dapat langsung meng-update read database lokalnya tanpa pernah menghubungi Order Service lagi!

## 11. Real World Example
- **Git Version Control**: Git adalah sistem event sourcing paling terkenal di dunia! Git tidak menyimpan file duplikat utuh di setiap commit; Git menyimpan riwayat delta commit (patch). Cabang (*branch*), *rebase*, dan *cherry-pick* adalah operasi manipulasi event log.
- **E-Commerce Shopping Cart (Amazon)**: Riwayat penambahan barang, penghapusan barang, hingga pembatalan voucher disimpan sebagai event stream untuk analisis perilaku pengguna (*behavioral analytics*).

## 12. Trade-offs

| Parameter | CRUD Tradisional | CQRS & Event Sourcing |
|---|---|---|
| **Kompleksitas Kode** | Rendah, sangat familiar bagi developer | Tinggi, membutuhkan pemahaman event driven & DDD |
| **Audit & History** | Butuh tabel log terpisah yang rentan tidak sinkron | Bawaan (*Built-in 100% accurate audit trail*) |
| **Konsistensi** | Strong Consistency (ACID) | **Eventual Consistency** (Read Model tertinggal beberapa ms) |
| **Skalabilitas Baca/Tulis**| Terikat pada satu model database | Skala baca dan tulis dapat di-scale independen |
| **Skema Evolusi** | `ALTER TABLE` migrasi SQL standar | Event bersifat immutable, butuh *Upcasters* untuk event lama |

## 13. When To Use CQRS & Event Sourcing
- Domain dengan logika bisnis kompleks, kolaboratif tinggi, dan audit ketat (Fintech, Banking, Supply Chain, Healthcare).
- Sistem dengan perbedaan ekstrem antara beban baca dan tulis.
- Kebutuhan fitur undo/redo, temporal queries, atau rekonstruksi data historis.

## 14. When NOT To Use
- Aplikasi CRUD sederhana (Internal Admin Dashboard, Sistem Manajemen Blog/CMS biasa).
- Sistem yang mutlak memerlukan *Immediate Read-Your-Own-Writes Consistency* di semua level tanpa toleransi lag milidetik sama sekali.

## 15. Common Mistakes
1. **Menerapkan CQRS dan Event Sourcing di seluruh sistem secara membabi buta**: Hanya terapkan pada Bounded Context yang benar-benar membutuhkan (misal Core Payment Aggregate), bukan pada modul profil pengguna sederhana.
2. **Membiarkan Stream Event Membengkak Tanpa Snapshotting**: Mencoba merekonstruksi akun yang memiliki 200.000 transaksi dari awal akan membunuh performa memori dan CPU server. Gunakan Snapshot berkala!
3. **Mengubah Event yang Sudah Tersimpan di Event Store**: Event adalah fakta masa lalu. Dilarang melakukan `UPDATE` atau `DELETE` pada baris event store!

## 16. Best Practices
- **Idempotent Projectors**: Pastikan setiap fungsi projection yang membangun Read Model bersifat idempoten terhadap event yang sama.
- **Upcasting Pattern**: Ketika format payload event versi 1 berubah di versi 2, buat *Upcaster transformer* di layer deserialisasi daripada memodifikasi data mentah di database.
- **Mitigasi Eventual Consistency di Frontend**: Setelah user menekan tombol submit (Command), UI dapat menggunakan *Optimistic UI Update* atau WebSocket notification untuk mengabari saat Projection selesai.

## 17. Troubleshooting
- **Masalah: User mengklik submit pesanan, lalu dialihkan ke halaman detail pesanan, tapi pesanan belum muncul (404 Not Found)**.
  - *Sebab*: Lag asinkron pada Projector. Command sudah masuk ke Event Store, tapi Read Model (Elasticsearch) belum selesai mengindeks event tersebut (*Eventual Consistency Lag*).
  - *Solusi*:
    1. Arahkan pembacaan langsung setelah write ke *Write Model* untuk ID pesanan tersebut (*Read-your-own-writes*).
    2. Gunakan version/timestamp token di response POST, dan tahan request GET di client sampai Read Model mencapai versi tersebut.

## 18. Hands-on Practice
Mari kita uji implementasi nyata Bank Account Aggregate berbasis Event Sourcing, lengkap dengan kalkulasi state historis, snapshotting, dan projection ke Read Model di `hands-on/m03/cqrs_event_sourcing_demo.js`.

## 19. Exercises & Challenge
- **Exercise**: Hitung state akhir dari akun bank dengan rentetan event: `Opened(500k)`, `Deposited(200k)`, `Withdrawn(100k)`, `Withdrawn(50k)`. Berapa saldo akhirnya? (Jawaban: Rp 550.000).
- **Challenge**: Rancang skema *Compensating Transaction* (Saga Pattern) untuk skenario di mana Command reservasi hotel sukses, tapi Command pembayaran kartu kredit ditolak bank mitra.

## 20. Summary
CQRS memisahkan tanggung jawab mutasi data dari query, memungkinkan optimasi ekstrem pada masing-masing jalur. Dipadukan dengan Event Sourcing, data disimpan sebagai rekaman sejarah yang utuh, menyediakan fleksibilitas arsitektur, auditabilitas mutlak, dan kemampuan proyeksi data ke bentuk penyimpanan apapun di masa depan.
