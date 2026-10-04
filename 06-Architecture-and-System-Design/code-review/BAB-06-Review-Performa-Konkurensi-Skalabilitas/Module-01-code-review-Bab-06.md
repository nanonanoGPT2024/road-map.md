## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul**: CR-ARCH-0601
* **Nama Modul**: Review Khusus: Performa, Konkurensi, & Skalabilitas (Database, Execution Plans, Indexing, Concurrency, Resource Leaks)
* **Kategori**: 06-Architecture-and-System-Design
* **Prasyarat**: 
  * Pemahaman mendalam tentang Relational Database Management Systems (PostgreSQL/MySQL) & Transaction Isolation Levels.
  * Pemahaman tentang Concurrency Primitives (Threads, Goroutines, Mutexes, Semaphores, Channels).
  * Pengalaman membaca sintaks Go, SQL, dan analisis runtime profile (pprof).
* **Estimasi Waktu**: 8 Jam Pembelajaran Mandiri / Workshop
* **Tingkat Kesulitan**: Advanced (L3 - Senior/Lead Reviewer)

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, reviewer diharapkan mampu:
1. **Menganalisis Execution Plan SQL**: Mengidentifikasi anomali seperti *Sequential Scan*, *Nested Loop Join* yang tidak optimal, dan *High-Cost Sorts* langsung dari deskripsi PR atau artefak query log.
2. **Mendeteksi Pattern Anti-Performa Database**: Menemukan masalah *N+1 Queries*, penggunaan indeks yang keliru (*index suppression* akibat fungsi skalar), dan pemilihan indeks komposit yang melanggar prinsip *Leftmost Prefix*.
3. **Mengidentifikasi Resiko Locking & Deadlock**: Menganalisis urutan akuisisi lock pada transaksi database dan kode aplikasi untuk memitigasi *Wait-For Graph cycles* dan lock escalation.
4. **Mengaudit Concurrency & Thread-Safety**: Menemukan *race conditions*, akses memori bersama tanpa sinkronisasi, serta manipulasi pointer yang tidak aman dalam lingkungan multi-threaded/goroutine.
5. **Menemukan Vektor Resource Leaks**: Memvalidasi siklus hidup objek runtime (koneksi database, file descriptor, HTTP response body, goroutine/thread terblokir) agar tidak memicu degradasi memori bertahap (*OOM*) atau *connection pool starvation*.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                              AUDIT ARSITEKTUR RUNTIME & DATA
                                             │
      ┌──────────────────────────────────────┴──────────────────────────────────────┐
      │                                                                            │
DATABASE & I/O SUBSYSTEM                                               CONCURRENCY & RUNTIME RESOURCES
      │                                                                            │
  ┌───┴──────────────────────────┐                                       ┌──────────┴─────────────────────────┐
  │                              │                                       │                                    │
EXECUTION EFFICIENCY      CONTENTION & LOCKING                   THREAD/GOROUTINE SAFETY             RESOURCE LIFECYCLE
  │                              │                                       │                                    │
  ├─ Execution Plans (Seq vs Idx)├─ Lock Granularity (Row vs Table)     ├─ Data Races (Shared Memory)        ├─ Connection Pools (Exhaustion)
  ├─ B-Tree & Composite Indexes  ├─ Deadlock Cycle Prevention            ├─ Deadlocks (Lock Inversion)        ├─ File Descriptors (Unclosed Body)
  ├─ N+1 Query Patterns          ├─ Optimistic vs Pessimistic Locks      ├─ Channel Deadlock / Abandonment    ├─ Goroutine Leaks (Blocked Select)
  └─ Pagination (Offset vs Keys) └─ Isolation Level Anomalies            └─ Atomic vs Mutex Primitives        └─ Memory Bloat / Buffering
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Kode yang lolos dari unit test fungsional dan integration test di lingkungan *staging* sering kali runtuh seketika saat menerima beban produksi riil. Alasannya: **Fungsionalitas tidak menguji skenario saturasi resource dan interleaving konkurensi.**

1. **Efek Latensi Eksponensial**: Query *N+1* atau *missing index* mungkin hanya memakan waktu 2ms pada database lokal dengan 100 baris data. Namun pada tabel produksi dengan 50 juta baris, query tersebut berubah menjadi *Sequential Scan* yang memakan waktu 15 detik, memblokir I/O disk, dan memicu *cascading failures* ke seluruh microservice.
2. **Kerapuhan Sistem Akibat Deadlock**: Urutan eksekusi transaksi yang berbeda beberapa milidetik dapat menghasilkan deadlock siklik (*Cyclic Wait-For Graph*). Hal ini menghentikan transaksi, membuang resource komputasi, dan meningkatkan *error rate* secara drastis.
3. **Silent Killers (Resource Leaks)**: Goroutine atau thread yang tertahan pada operasi channel/I/O yang tidak memiliki timeout/cancellation tidak akan langsung mematikan aplikasi. Mereka mengonsumsi stack memory secara perlahan, memicu *Garbage Collection thrashing*, hingga sistem mengalami *crash* mendadak via *Out Of Memory (OOM) Killer* pada jam sibuk.

Reviewer kode adalah benteng terakhir yang membedakan antara sistem yang "sekadar berjalan" dengan sistem yang "stabil di bawah saturasi ekstrem".

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Database Interactions & Query Plans
Interaksi database yang buruk umumnya berakar dari *abstraksi ORM yang bocor (leaky abstractions)*. Reviewer harus memeriksa bukan hanya kode pemanggil, melainkan representasi SQL yang dihasilkan.
* **Execution Plan**: Peta jalan yang dibuat oleh query planner database (misalnya PostgreSQL) untuk mengeksekusi query. Aspek kritis: *Node Type* (Index Scan vs Seq Scan vs Bitmap Heap Scan), *Cost*, *Actual Rows vs Planned Rows*, dan *Filter Efficiency*.
* **Indexing Strategy**: B-Tree adalah default. Reviewer harus memverifikasi *SARGability* (Search Argument Able), kardinalitas kolom, dan penerapan *Leftmost Prefix Rule* pada indeks komposit `(col_a, col_b, col_c)`.
* **N+1 Query Problem**: Terjadi ketika ORM mengeksekusi 1 query untuk mengambil *parent entities*, lalu secara naif mengeksekusi $N$ query tambahan untuk mengambil *child entities* di dalam loop aplikasi.

### 2. Database Locking & Contention
* **Lock Modes**: Membedakan penggunaan *Shared Locks (S)* dan *Exclusive Locks (X)*. Transaksi yang menjalankan `SELECT ... FOR UPDATE` menahan baris dan dapat memicu *contention* antrian.
* **Deadlock Conditions**: Terjadi ketika dua atau lebih transaksi saling menunggu resource yang dipegang oleh yang lain (Koffman conditions: Mutual Exclusion, Hold and Wait, No Preemption, Circular Wait).

### 3. Goroutine & Thread Safety
* **Race Condition**: Dua atau lebih concurrent execution unit mengakses lokasi memori yang sama secara simultan, dan minimal satu operasi adalah penulisan (write), tanpa ada mekanisme sinkronisasi (Mutex, RWMutex, Atomic).
* **Deadlock / Livelock Runtime**: Goroutine yang menunggu sinyal dari channel yang tidak pernah dikirim, atau dua thread yang mengunci mutex dengan urutan terbalik (*AB-BA lock ordering*).

### 4. Resource Leaks
* Terjadi ketika abstraksi runtime mengalokasikan resource kernel/OS (file descriptor, socket jaringan, memory heap) namun siklus pelepasan resource (*cleanup/close*) tidak terikat pada lifecycle eksekusi atau terlewati karena branching error (*unhandled error return*).

---

## SEKSI 06 — BAGAIMANA BEKERJA (HOW)

Reviewer harus mengikuti metodologi audit terstruktur saat mengevaluasi pull request (PR) yang menyentuh I/O dan konkurensi:

```
[PR Masuk]
    │
    ├─► 1. AUDIT AKSES DATABASE
    │     ├── Apakah ada query di dalam loop? ──► [FLAG: N+1]
    │     ├── Periksa klausa WHERE/JOIN: Apakah terindeks & SARGable?
    │     └── Periksa transaksi: Apakah urutan akses tabel konsisten?
    │
    ├─► 2. AUDIT RUNTIME KONKURENSI
    │     ├── Apakah ada shared-state yang dimutasi? Mutex/Atomic terpasang?
    │     ├── Apakah lifetime goroutine/thread dibatasi oleh Context?
    │     └── Apakah channel operations berpotensi unbuffered & unread?
    │
    └─► 3. AUDIT RESOURCE LIFECYCLE
          ├── Setiap I/O resource (Body, DB Rows, File) langsung di-defer Close?
          └── Apakah defer dipanggil dalam loop tak terhingga? ──► [FLAG: Memory Leak]
```

### Langkah 1: Audit Query Plan & Index
* Mintalah output `EXPLAIN (ANALYZE, BUFFERS)` jika PR mengubah skema atau menambahkan query baru dengan join kompleks.
* **Red Flags**:
  * Adanya *Seq Scan* pada tabel besar ($>10.000$ baris).
  * Deviasi signifikan antara `rows=X` di estimasi planner dan `actual rows=Y` (indikasi statistik tabel *stale*, perlu `ANALYZE`).
  * Filter dengan operasi fungsi: misal `WHERE DATE(created_at) = '2026-03-30'` (mematikan indeks pada `created_at`).

### Langkah 2: Audit Locking Pattern
* Pastikan transaksi database dibuat sependek mungkin. Hindari pemanggilan eksternal (HTTP API, gRPC) di dalam transaksi database yang sedang membuka lock.
* Periksa keseragaman urutan penguncian (*Lock Ordering*). Jika Transaksi 1 mengunci Tabel A lalu B, maka Transaksi 2 TIDAK BOLEH mengunci Tabel B lalu A.

### Langkah 3: Audit Thread/Goroutine Lifecycle
* Pastikan pemanggilan `go func(...)` memiliki ownership yang jelas. Kapan ia selesai? Bagaimana ia diberitahu untuk berhenti jika sistem melakukan shutdown atau context HTTP dibatalkan?
* Pastikan tidak ada capture pointer variabel iterator loop (klasik Go issue sebelum Go 1.22, tetap kritis untuk pemahaman memory sharing).

### Langkah 4: Audit Pool & File Descriptor Management
* Verifikasi bahwa setiap `*sql.Rows`, `net.Conn`, atau `http.Response.Body` ditutup segera setelah error handling alokasi selesai.
* Pastikan error handling tidak keluar dari fungsi sebelum `.Close()` dieksekusi.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### 1. Deteksi N+1 vs Batch Query Architecture

```
Pola Anti-Pattern: N+1 Queries (Network Choke)
App Engine                            Database Engine
    │                                       │
    │────── 1. SELECT * FROM users ────────►│ (1 query round-trip)
    │◄───── Return 100 rows ────────────────│
    │                                       │
    │─── 2. SELECT * FROM orders WHERE uid=1 ─►│ (Query #1 round-trip)
    │◄── Return order details ──────────────│
    │─── 3. SELECT * FROM orders WHERE uid=2 ─►│ (Query #2 round-trip)
    │◄── Return order details ──────────────│
    │   ... [98 kali round-trip berikutnya] │
    │─── N. SELECT * FROM orders WHERE uid=100►│ (Query #100 round-trip)
    │◄── Return order details ──────────────│
    TOTAL: 101 Network Round-Trips! Latensi = 101 * Network_RTT + Overhead

Pola Optimal: Batch Eager Loading / Join
App Engine                            Database Engine
    │                                       │
    │────── 1. SELECT * FROM users ────────►│ (Query 1)
    │◄───── Return 100 rows ────────────────│
    │                                       │
    │────── 2. SELECT * FROM orders ───────►│ (Query 2: Single batch trip)
    │          WHERE user_id IN (1, 2, ..100)│
    │◄───── Return all matched orders ──────│
    TOTAL: 2 Network Round-Trips!
```

### 2. Lock Inversion Deadlock

```
Goroutine/Thread 1                        Goroutine/Thread 2
      │                                         │
Acquires Mutex A                          Acquires Mutex B
      │                                         │
Tries to acquire Mutex B                  Tries to acquire Mutex A
      │                                         │
      ▼                                         ▼
[BLOCKED: Menunggu Mutex B]               [BLOCKED: Menunggu Mutex A]
      │                                         │
      └──────────────── DEADLOCK ───────────────┘
                     (Circular Wait)
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Contoh kasus kebocoran goroutine (*Goroutine Leak*) akibat unbuffered channel tanpa context cancellation saat memproses panggilan asinkron.

### Kode Bermasalah (Ditolak saat PR Review)
```go
// BAD: Jika timeout terjadi lebih cepat daripada doWork(), 
// goroutine akan terblokir selamanya saat mengirim ke ch (unbuffered).
func ProcessTaskWithTimeout(timeout time.Duration) (*Result, error) {
    ch := make(chan *Result) // Unbuffered channel

    go func() {
        res := doWork() // Membutuhkan waktu bervariasi
        ch <- res       // AKAN TERBLOKIR PERMANEN JIKA TIMEOUT TELAH EXPIRED!
    }()

    select {
    case res := <-ch:
        return res, nil
    case <-time.After(timeout):
        return nil, errors.New("task timed out")
    }
}
```

### Reviewer Comment:
> *"Blocking pada baris `ch <- res`. Channel ini tidak memiliki buffer (`unbuffered`). Jika cabang `time.After` terpenuhi terlebih dahulu, fungsi pengambil `ProcessTaskWithTimeout` akan kembali (*return*), meninggalkan goroutine di latar belakang dalam keadaan terblokir selamanya menunggu *receiver*. Hal ini menyebabkan stack goroutine bocor. Gunakan buffer berkapasitas 1 atau lewati Context untuk membatalkan proses anak."*

### Kode Perbaikan (Disetujui)
```go
// GOOD: Channel berkapasitas 1 mencegah pengirim terblokir 
// meskipun fungsi utama sudah return via timeout.
func ProcessTaskWithTimeout(ctx context.Context, timeout time.Duration) (*Result, error) {
    ctx, cancel := context.WithTimeout(ctx, timeout)
    defer cancel()

    ch := make(chan *Result, 1) // Buffered channel (kapasitas 1)

    go func() {
        // doWorkWithContext menghormati ctx.Done()
        res := doWorkWithContext(ctx)
        ch <- res // Non-blocking write karena ada buffer 1 slot
    }()

    select {
    case res := <-ch:
        return res, nil
    case <-ctx.Done():
        return nil, ctx.Err()
    }
}
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Berikut adalah simulasi skenario Pull Request nyata: Service pemrosesan *Ledger Transaction* yang memiliki cacat performa database, race condition, dan potensi kebocoran koneksi.

### Pull Request Diff (Bermasalah)
```go
package ledger

import (
    "database/sql"
    "fmt"
    "net/http"
    "sync"
)

type AccountService struct {
    db *sql.DB
}

// Handler untuk transfer dana antar akun
func (s *AccountService) TransferFundsHandler(w http.ResponseWriter, r *http.Request) {
    fromAccountID := r.URL.Query().Get("from")
    toAccountID := r.URL.Query().Get("to")
    amount := 100.00 // simplified for brevity

    tx, err := s.db.Begin()
    if err != nil {
        http.Error(w, err.Error(), 500)
        return
    }

    // MASALAH 1: Missing ORDER BY / Inverted Lock Order -> DEADLOCK POTENTIAL
    // Update balance 1
    _, err = tx.Exec("UPDATE accounts SET balance = balance - $1 WHERE id = $2", amount, fromAccountID)
    if err != nil {
        tx.Rollback()
        http.Error(w, err.Error(), 500)
        return
    }

    // Update balance 2
    _, err = tx.Exec("UPDATE accounts SET balance = balance + $1 WHERE id = $2", amount, toAccountID)
    if err != nil {
        tx.Rollback()
        http.Error(w, err.Error(), 500)
        return
    }

    // MASALAH 2: Remote call di dalam database transaction -> POOL EXHAUSTION
    resp, err := http.Post("http://notification-service/notify", "application/json", nil)
    if err != nil {
        tx.Rollback()
        http.Error(w, err.Error(), 500)
        return
    }
    // MASALAH 3: Body tidak ditutup -> RESOURCE LEAK (FD leak)
    _ = resp

    tx.Commit()
    w.WriteHeader(http.StatusOK)
}

// Audit history endpoint
func (s *AccountService) GetAuditReport(w http.ResponseWriter, r *http.Request) {
    // MASALAH 4: N+1 Query & Non-SARGable Query
    // Tanggal dievaluasi via fungsi DATE() -> bypass index
    rows, err := s.db.Query("SELECT id, user_id FROM accounts WHERE DATE(created_at) = '2026-03-30'")
    if err != nil {
        http.Error(w, err.Error(), 500)
        return
    }
    // MASALAH 5: rows.Close() tidak dipanggil via defer -> Connection Leak jika error di loop
    
    type ReportItem struct {
        AccountID string
        UserName  string
    }
    var report []ReportItem

    for rows.Next() {
        var accID, userID string
        rows.Scan(&accID, &userID)

        // EKSTREM N+1: Melakukan query tambahan di setiap loop iterasi!
        var userName string
        s.db.QueryRow("SELECT name FROM users WHERE id = $1", userID).Scan(&userName)

        report = append(report, ReportItem{AccountID: accID, UserName: userName})
    }

    rows.Close()
    // render JSON (omitted)
}
```

---

### Hasil Audit Kode oleh Senior Reviewer

```markdown
### ⚠️ Temuan Arsitektur & Kinerja Kritis:

1. **Deadlock Hazard pada Transfer Transaksi**:
   - Jika Akun A mentransfer ke B (mengunci A lalu B), dan di saat yang sama Akun B mentransfer ke A (mengunci B lalu A), database akan mendeteksi *lock cycle deadlock*.
   - **Solusi**: Normalisasi urutan lock. Selalu kunci record berdasarkan urutan leksikografis ID terkecil dahulu (`sort(id1, id2)`).

2. **Database Connection Pool Exhaustion (Tahan Transaksi via I/O Eksternal)**:
   - Baris `http.Post` berada di dalam transaksi database `tx`. Jika `notification-service` mengalami lonjakan latensi (misal 5 detik), koneksi database akan tertahan selama 5 detik hanya untuk menunggu respons jaringan eksternal. Ini akan menguras koneksi pada pool database (`max_open_conns`).
   - **Solusi**: Pindahkan I/O jaringan ke luar transaksi DB, atau gunakan *Outbox Pattern*.

3. **File Descriptor Leak (HTTP Body)**:
   - `resp.Body` tidak pernah ditutup via `defer resp.Body.Close()`. Ini menguras Socket/File Descriptors OS.

4. **Query Performance Degradation**:
   - `WHERE DATE(created_at) = '2026-03-30'` bersifat *non-SARGable*. Database tidak dapat menggunakan index range scan pada `created_at` dan dipaksa menjalankan *Full Table Scan*.
   - **Solusi**: Ubah menjadi range scan: `WHERE created_at >= '2026-03-30 00:00:00' AND created_at < '2026-03-31 00:00:00'`.

5. **N+1 Query Pattern**:
   - Endpoint `GetAuditReport` mengeksekusi $N$ query tambahan untuk mengambil nama user.
   - **Solusi**: Lakukan `INNER JOIN users u ON a.user_id = u.id` dalam 1 query tunggal.
```

---

### Kode Terfaktor & Disetujui (Production-Grade)

```go
package ledger

import (
    "context"
    "database/sql"
    "io"
    "net/http"
    "strings"
    "time"
)

type AccountService struct {
    db         *sql.DB
    httpClient *http.Client
}

func (s *AccountService) TransferFundsHandler(w http.ResponseWriter, r *http.Request) {
    ctx := r.Context()
    fromAccountID := r.URL.Query().Get("from")
    toAccountID := r.URL.Query().Get("to")
    amount := 100.00

    if fromAccountID == toAccountID {
        http.Error(w, "invalid transfer target", http.StatusBadRequest)
        return
    }

    // FIX 1: Deterministic Lock Ordering untuk mencegah deadlock
    firstID, secondID := fromAccountID, toAccountID
    firstDelta, secondDelta := -amount, amount
    if strings.Compare(fromAccountID, toAccountID) > 0 {
        firstID, secondID = toAccountID, fromAccountID
        firstDelta, secondDelta = amount, -amount
    }

    err := func() error {
        tx, err := s.db.BeginTx(ctx, &sql.TxOptions{Isolation: sql.LevelReadCommitted})
        if err != nil {
            return err
        }
        defer tx.Rollback() // Rollback aman jika dieksekusi sebelum commit

        // Kunci baris secara deterministik
        if _, err := tx.ExecContext(ctx, "UPDATE accounts SET balance = balance + $1 WHERE id = $2", firstDelta, firstID); err != nil {
            return err
        }
        if _, err := tx.ExecContext(ctx, "UPDATE accounts SET balance = balance + $1 WHERE id = $2", secondDelta, secondID); err != nil {
            return err
        }

        return tx.Commit()
    }()

    if err != nil {
        http.Error(w, "Transfer failed: "+err.Error(), http.StatusInternalServerError)
        return
    }

    // FIX 2: External I/O dijalankan di luar transaksi database
    go s.notifyAsync(fromAccountID, toAccountID, amount)

    w.WriteHeader(http.StatusOK)
}

func (s *AccountService) notifyAsync(from, to string, amount float64) {
    // Isolate lifetime using independent context with timeout
    ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
    defer cancel()

    req, err := http.NewRequestWithContext(ctx, http.MethodPost, "http://notification-service/notify", nil)
    if err != nil {
        return
    }

    resp, err := s.httpClient.Do(req)
    if err != nil {
        return
    }
    // FIX 3: Pastikan response body selalu dikeringkan (dread) dan ditutup
    defer resp.Body.Close()
    _, _ = io.Copy(io.Discard, resp.Body)
}

func (s *AccountService) GetAuditReport(w http.ResponseWriter, r *http.Request) {
    ctx := r.Context()

    // FIX 4: SARGable query format, memanfaatkan index pada `created_at`
    startRange := time.Date(2026, 3, 30, 0, 0, 0, 0, time.UTC)
    endRange := startRange.Add(24 * time.Hour)

    // FIX 5: Hilangkan N+1 via explicit SQL JOIN
    query := `
        SELECT a.id, u.name 
        FROM accounts a
        INNER JOIN users u ON a.user_id = u.id
        WHERE a.created_at >= $1 AND a.created_at < $2
    `
    rows, err := s.db.QueryContext(ctx, query, startRange, endRange)
    if err != nil {
        http.Error(w, err.Error(), http.StatusInternalServerError)
        return
    }
    defer rows.Close() // FIX: Resource protection

    type ReportItem struct {
        AccountID string `json:"account_id"`
        UserName  string `json:"user_name"`
    }
    var report []ReportItem

    for rows.Next() {
        var item ReportItem
        if err := rows.Scan(&item.AccountID, &item.UserName); err != nil {
            http.Error(w, err.Error(), http.StatusInternalServerError)
            return
        }
        report = append(report, item)
    }

    if err := rows.Err(); err != nil {
        http.Error(w, err.Error(), http.StatusInternalServerError)
        return
    }

    // Render logic continues...
}
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

Saat mereview optimasi performa dan konkurensi, selalu pertimbangkan *engineering trade-offs* berikut:

| Aspek / Teknik | Keuntungan | Kerugian / Biaya Operasional | Kapan Digunakan |
|---|---|---|---|
| **Eager JOIN vs Application Batching** | Mengurangi RTT jaringan secara absolut (1 round-trip via JOIN). | Membebani memory database engine jika Cartesian product membesar. | Relasi 1:1 atau 1:N dengan kardinalitas child yang rendah. |
| **Pessimistic Locking (`SELECT FOR UPDATE`)** | Mencegah anomali double-spend secara ketat pada level data. | Menurunkan throughput konkurensi secara drastis; latensi antrian request naik. | Transaksi finansial kritis dengan frekuensi tabrakan akun yang tinggi. |
| **Optimistic Locking (Version Column)** | *Non-blocking*; throughput tinggi tanpa menahan state lock pada engine DB. | Harus mengimplementasikan mekanisme *retry* pada level aplikasi; boros CPU jika kolisi tinggi. | Operasi sistem inventory/katalog yang dominan baca (*read-heavy*), mutasi jarang. |
| **Index Tambahan (Composite/Covering)** | Memangkas *table scan* menjadi *Index Only Scan*; latensi query terpangkas dari detik ke milidetik. | Menambah penalti latensi pada operasi write (`INSERT`/`UPDATE`/`DELETE`); konsumsi storage bertambah. | Query analitik atau endpoint inti dengan frekuensi panggil >1000 RPS. |
| **Worker Pool Pattern** | Membatasi jumlah goroutine/thread aktif; mencegah OOM akibat unbounded concurrency. | Kompleksitas kode naik; potensi bottleneck jika pool worker tersaturasi antrian. | Pemrosesan background job massal yang mengonsumsi CPU atau memory tinggi. |

---

## SEKSI 11 — BEST PRACTICES

Reviewer harus menguji PR terhadap checklist performa dan konkurensi berikut:

- [ ] **SQL SARGability**: Pastikan kolom berindeks tidak dibungkus oleh fungsi (misal: `WHERE LOWER(email) = ?` tidak menggunakan indeks pada `email`, melainkan butuh *Functional Index*).
- [ ] **Deterministic Lock Hierarchy**: Pastikan resource multi-kunci selalu diakses dalam urutan seragam (contoh: urutkan ID ascending sebelum melakukan `Lock()` atau `SELECT FOR UPDATE`).
- [ ] **No Network Calls in DB Transactions**: Jangan izinkan panggilan HTTP, gRPC, enkripsi CPU berat, atau I/O disk diapit oleh `db.Begin()` dan `tx.Commit()`.
- [ ] **Strict Context Propagation**: Setiap goroutine yang di-*spawn* harus menerima `context.Context` untuk memastikan terminasi saat proses induk dibatalkan.
- [ ] **Bounded Resource Allocation**:
  - Ganti *unbounded channel* dengan *buffered channel* terukur atau mekanisme *backpressure*.
  - Hindari `SELECT *`; eksplisitkan kolom yang dibutuhkan untuk memaksimalkan *Covering Index*.
- [ ] **Resource Drainage & Closure**:
  - `resp, err := client.Do(req)` $\rightarrow$ Selalu pasang `defer resp.Body.Close()`.
  - Jangan biarkan defer dijalankan di dalam loop jangka panjang (gunakan fungsi closure terisolasi).
  - Panggil `rows.Close()` pada hasil query SQL, dan cek error terminal `rows.Err()`.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

1. **Blind Indexing**: Pengembang menambahkan indeks tunggal pada setiap kolom di klausa `WHERE` secara terpisah (misal: satu indeks pada `org_id`, satu pada `status`). Reviewer harus mencatat bahwa database umumnya hanya memilih *satu* indeks terbaik, atau memicu *Bitmap Merge* yang tidak efisien. Solusinya adalah *Composite Index* berurutan: `(org_id, status)`.
2. **Offset Pagination Pitfall**: Mengizinkan `SELECT * FROM orders ORDER BY id LIMIT 50 OFFSET 1000000`. Database harus membaca dan membuang 1.000.000 baris sebelum mengembalikan 50 baris. Wajibkan pola *Keyset Pagination* (*Cursor-based*): `WHERE id > last_seen_id ORDER BY id ASC LIMIT 50`.
3. **Ghost Read/Write pada Goroutine Loop Variables**: Menjalankan `go func() { process(item) }()` dalam loop di mana pointer atau reference variabel `item` berubah di setiap iterasi.
4. **Ignored Mutex Copies**: Mengoper struct yang membungkus `sync.Mutex` secara *pass-by-value* alih-alih *pass-by-pointer*. Hal ini menduplikasi status internal mutex sehingga proteksi konkurensi menjadi hilang sepenuhnya (*unprotected shared state*).
5. **Connection Leak pada SQL Rows**: Mengira bahwa iterasi loop `for rows.Next()` akan selalu otomatis menutup baris. Jika `rows.Scan()` mengalami kegagalan (*error break*), koneksi tidak akan dikembalikan ke pool sampai garbage collection dieksekusi, memicu *connection pool exhaustion*.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Skenario Latihan
Tinjau potongan kode berikut (fungsi agregator analitik) dan temukan **3 cacat fatal** yang berhubungan dengan performa, kebocoran memori, dan konkurensi. Tuliskan catatan review formal Anda.

```go
func (svc *AnalyticsService) AggregateMetrics(targets []string) map[string]int {
    results := make(map[string]int)
    var wg sync.WaitGroup

    for _, target := range targets {
        wg.Add(1)
        go func() {
            // Melakukan fetch data HTTP
            resp, err := http.Get("https://api.internal/stats/" + target)
            if err == nil {
                var count int
                json.NewDecoder(resp.Body).Decode(&count)
                // Menyimpan ke map
                results[target] = count
            }
            wg.Done()
        }()
    }

    wg.Wait()
    return results
}
```

### Lembar Jawaban & Analisis Mandiri
Periksa temuan Anda terhadap kunci evaluasi berikut:
1. **Data Race Fatal**: Penulisan serentak ke variabel `results[target]` dari banyak goroutine tanpa sinkronisasi (Go runtime panic: *fatal error: concurrent map writes*). Solusi: Pasang `sync.Mutex` atau gunakan thread-safe storage.
2. **Resource Leak (File Descriptor)**: `resp.Body` tidak pernah ditutup dengan `.Close()`, menyebabkan socket network menggantung dalam status `CLOSE_WAIT` atau menahan descriptor hingga proses kehabisan kuota file descriptor kernel.
3. **Closure Capture Bug**: Variabel `target` ditangkap oleh closure goroutine secara referensial. Banyak goroutine akan mengeksekusi request dengan nilai target terakhir dari loop. Solusi: Oper nilai `target` sebagai parameter fungsi goroutine: `go func(t string) { ... }(target)`.
4. *(Bonus)* **Unbounded Concurrency**: Jika slice `targets` berisi 10.000 elemen, kode akan menembakkan 10.000 goroutine dan socket HTTP secara simultan tanpa throttling (berpotensi memicu *connection refused* atau penolakan OS socket).

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

Jawablah pertanyaan berikut untuk menguji ketajaman analisa review Anda:

1. **Dalam eksekusi PostgreSQL, kondisi apa yang menunjukkan bahwa indeks pada tabel berukuran 100GB diabaikan oleh engine?**
   * A) `Index Only Scan using idx_created_at`
   * B) `Bitmap Heap Scan` diikuti oleh `Recheck Cond`
   * C) `Seq Scan on orders (cost=0.00..1823901.20 rows=... actual time=0.045..12450.231)`
   * D) `Index Scan using orders_pkey on orders`

2. **Dua transaksi berjalan konkuren:**
   * *Tx 1*: Mengupdate akun ID 100, lalu ID 200.
   * *Tx 2*: Mengupdate akun ID 200, lalu ID 100.
   **Apa istilah resmi untuk kondisi kebuntuan yang terjadi di engine database?**
   * A) Phantom Read Anomaly
   * B) Cyclic Wait-For Graph (Deadlock)
   * C) Write Skew Anomaly
   * D) Lock Escalation Cascading

3. **Anda menemukan kode Go berikut pada sebuah PR:**
   ```go
   var mu sync.RWMutex
   func ReadMetric() Metric {
       mu.RLock()
       data := fetchUnsafeCache()
       mu.RUnlock()
       return data
   }
   ```
   **Jika `fetchUnsafeCache()` mengubah state pointer internal cache saat cache miss, apa yang terjadi?**
   * A) Kode aman karena diproteksi oleh `RLock`.
   * B) RLock otomatis naik (*escalates*) menjadi Exclusive Lock.
   * C) Terjadi data race, karena multiple reader dapat mengeksekusi mutasi cache secara simultan.
   * D) Compiler Go akan melempar compile-time error.

4. **Bagaimana cara mendeteksi Goroutine Leak di environment staging/staging integration test secara programatis?**
   * A) Memeriksa log error HTTP 500.
   * B) Menggunakan `goleak.VerifyNone(t)` dari library `go.uber.org/goleak` pada teardown unit/integration test.
   * C) Mengamati memory usage server melalui perintah `top`.
   * D) Mengatur `runtime.GOMAXPROCS(1)`.

5. **Kapan implementasi Keyset Pagination (`WHERE id > ? LIMIT ?`) TIDAK COCOK digunakan dan harus mempertimbangkan alternatif?**
   * A) Ketika tabel memiliki data lebih dari 10 juta baris.
   * B) Ketika pengguna membutuhkan fitur UI untuk langsung lompat ke halaman spesifik (misal: "Lompat langsung ke halaman 45").
   * C) Ketika primary key bertipe integer auto-increment.
   * D) Ketika query memiliki latensi di bawah 10ms.

---

### Kunci Jawaban Quiz
* **1: C** — `Seq Scan` menandakan database memindai seluruh halaman disk secara berurutan dan mengabaikan indeks.
* **2: B** — *Cyclic Wait-For Graph* adalah representasi formal deadlock di mana simpul-simpul transaksi saling menunggu pelepasan resource secara siklik.
* **3: C** — `RLock()` (Read Lock) mengizinkan banyak goroutine masuk secara konkuren. Jika terjadi mutasi internal memori di dalamnya, proteksi runtuh dan data race terjadi.
* **4: B** — `goleak` secara aktif membandingkan stack goroutine sebelum dan sesudah test selesai untuk menangkap kebocoran goroutine yang masih berjalan di latar belakang.
* **5: B** — Keyset pagination mengandalkan titik relatif baris terakhir (*cursor*), sehingga tidak mendukung perhitungan navigasi acak (*random access page skipping*) seperti yang didukung oleh klausa `OFFSET`.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

1. **Books**:
   * *Designing Data-Intensive Applications* oleh Martin Kleppmann (O'Reilly Media) — Wajib baca untuk bab *Transactions*, *Concurrency Control*, dan *Partitioning*.
   * *Database Internals: A Deep Dive into How Distributed Data Systems Work* oleh Alex Petrov (O'Reilly Media).
   * *The Go Programming Language* oleh Alan Donovan & Brian Kernighan (Addison-Wesley) — Bab 8 & 9: *Goroutines and Channels*, *Concurrency with Shared Variables*.

2. **Database Engine Documentation**:
   * [PostgreSQL Documentation: Using EXPLAIN](https://www.postgresql.org/docs/current/using-explain.html)
   * [PostgreSQL Documentation: Explicit Locking](https://www.postgresql.org/docs/current/explicit-locking.html)
   * [Use The Index, Luke!](https://use-the-index-luke.com/) — Panduan komprehensif konsep indexing SQL untuk developer.

3. **Profiling & Tooling**:
   * [Go Diagnostics & Profiling (pprof)](https://go.dev/doc/diagnostics)
   * [Uber Go Style Guide: Concurrency Patterns](https://github.com/uber-go/guide/blob/master/style.md#concurrency)
   * Tool: `go.uber.org/goleak` untuk goroutine leak detection.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

Menilai kualitas arsitektural sebuah Pull Request membutuhkan paradigma beyond *functional correctness*. Seorang reviewer ahli harus memvalidasi stabilitas kode di bawah saturasi:

1. **Database Interactions**: Evaluasi query dari sudut pandang *Access Path*. Awasi indikasi *Sequential Scan*, non-SARGable predicates, dan siklus query berulang (N+1).
2. **Lock Order Consistency**: Deadlock dapat dieliminasi secara preventif dengan menetapkan protokol penguncian resource yang deterministik dan mempertahankan transaksi database dalam durasi sesingkat mungkin.
3. **I/O Isolation**: Jangan pernah membiarkan latensi jaringan pihak ketiga mendikte durasi transaksi basis data.
4. **Strict Concurrency Hygiene**: Shared state memerlukan sinkronisasi eksklusif; goroutine memerlukan jalur terminasi yang pasti via context propagation; dan channel operations wajib memperhitungkan skenario unbuffered block.
5. **Resource Closure Invariant**: Setiap alokasi file descriptor, koneksi pool, atau streaming reader harus memiliki pasangan instruksi pembebasan resource yang kebal terhadap cabang kegagalan error (*fail-safe cleanup*).

---

## SEKSI 17 — GLOSARIUM

* **SARGable (Search Argument Able)**: Karakteristik predikat query SQL yang memungkinkan engine database memanfaatkan struktur indeks B-Tree secara langsung tanpa harus melakukan kalkulasi atau transformasi fungsi pada setiap baris data.
* **N+1 Query**: Anti-pattern di mana satu query pembuka menghasilkan $N$ eksekusi query turunan untuk mengambil data asosiasi, mendegradasi performa melalui network latency amplifications.
* **Wait-For Graph**: Graf berarah yang digunakan oleh DBMS untuk merepresentasikan relasi dependensi transaksi; siklus (*cycle*) di dalam graf ini menandakan kondisi Deadlock.
* **Data Race**: Kondisi tak tersinkronisasi di mana dua thread/goroutine mengakses alamat memori yang sama secara berbarengan dengan minimal satu operasi adalah penulisan.
* **Keyset Pagination**: Teknik penomoran halaman data menggunakan penanda nilai kolom unik terakhir (biasanya ID atau timestamp) alih-alih menggunakan `OFFSET`, menjaga efisiensi pembacaan data tetap konstan ($O(\log N)$ alih-alih $O(N)$).
* **Connection Pool Starvation**: Kondisi ketika semua koneksi yang tersedia di dalam pool habis tertahan oleh operasi lama atau kebocoran resource, sehingga request baru terblokir atau mengalami penolakan (*connection timeout*).
* **Leftmost Prefix Rule**: Aturan pemanfaatan indeks gabungan (*Composite Index*) di mana query planner hanya dapat memanfaatkan indeks jika pencarian dimulai dari kolom paling kiri yang didefinisikan dalam struktur indeks.

---

## SEKSI 18 — CATATAN INSTRUKTUR

### Fokus Pengajaran
* **Tantangan Mental Terbesar Peserta**: Developer sering berpikir bahwa ORM menangani semua urusan database. Instruktur harus mendemonstrasikan bahwa ORM menyembunyikan query nyata dan memicu N+1 secara default jika tidak dikonfigurasi secara eksplisit (misal: `Preload` di GORM atau `select_related`/`prefetch_related` di Django).
* **Simulasi Lapangan**:
  * Gunakan flag Go Race Detector (`go test -race`) untuk menunjukkan kegagalan konkurensi langsung di terminal.
  * Tunjukkan secara visual visualisasi pohon query menggunakan tools online seperti `explain.depesz.com` atau `explain.dalibo.com` agar peserta memahami cost node query plan.
* **Hal yang Harus Ditegaskan**: "Jika Anda melihat `go func()` tanpa `context.Context` atau channel pembatal, tolak PR tersebut secara default sampai siklus hidupnya dibuktikan aman."

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi 1.0.0** (Maret 2026):
  * Rilis modul kurikulum perdana.
  * Penyusunan materi teknis komprehensif: Database SARGability, N+1, Locking, Deadlock Graphs, Goroutine Safety, dan Resource Management.
  * Standarisasi format modul 20 Seksi GEMINI.md.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya**: `CR-ARCH-0503`: Review Khusus: Error Handling, Resilience Patterns, & Circuit Breakers
* **Modul Saat Ini**: `CR-ARCH-0601`: Review Khusus: Performa, Konkurensi, & Skalabilitas (Database, Execution Plans, Indexing, Concurrency, Resource Leaks)
* **Modul Berikutnya**: `CR-ARCH-0602`: Review Khusus: Keamanan Sistem, AuthN/AuthZ, Injeksi, & Data Sanitization
* **Materi Terkait**:
  * `04-Clean-Code-and-Patterns`: Code Smells & Refactoring Idiomatic Go
  * `05-Testing-and-QA`: Concurrency Stress Testing & Race Detection in CI Pipeline