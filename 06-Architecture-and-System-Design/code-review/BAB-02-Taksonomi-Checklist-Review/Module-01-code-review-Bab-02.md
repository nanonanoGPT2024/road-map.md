# Kurikulum Code Review: Architecture and System Design
## Modul 02.01: Taksonomi & Checklist Review Standar Industri

---

## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul**: `CR-ARCH-0201`
* **Nama Modul**: Taksonomi & Checklist Review Standar Industri: Hierarchy of Review Concerns & Pragmatic Anti-Patterns
* **Kategori**: 06-Architecture-and-System-Design
* **Tingkat Kesulitan**: Advanced / L4-L5 (Senior Software Engineer / Tech Lead)
* **Prasyarat**: 
  * Pemahaman mendalam tentang siklus hidup Git & Pull Request (PR)
  * Pemahaman arsitektur perangkat lunak (Clean Architecture, Hexagonal, Event-Driven, Microservices)
  * Pemahaman dasar keamanan aplikasi web (OWASP Top 10) dan performa database (indeks, transaksi, isolasi)
* **Alokasi Waktu**: 4 jam teori mendalam, 4 jam analisis studi kasus dan simulasi review
* **Target Pembaca**: Senior Engineers, Staff Engineers, Tech Leads, Engineering Managers, dan Software Architects yang bertanggung jawab menjaga integritas sistem multi-layanan.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta diharapkan mampu:

1. **Menerapkan Hierarchy of Review Concerns** secara sistematis: memprioritaskan Arsitektur > Ketepatan Logika > Keamanan > Performa > Konvensi/Gaya Kode.
2. **Mengeliminasi Cognitive Load terfragmentasi** dengan mendelegasikan pengecekan deterministik (konvensi, format, sintaksis) ke automated pipelines (linter, static analysis) sehingga waktu review manusia terfokus pada trade-off arsitektural.
3. **Mengidentifikasi dan Memitigasi Anti-Pattern Code Review**: secara aktif mendeteksi dan menghentikan praktik *Bikeshedding*, *Rubber-Stamping (LGTM Syndrome)*, *The Mega-PR Paralysis*, dan *Goalpost Moving*.
4. **Merancang Pragmatic Review Checklists** berbasis konteks risiko (High-Risk Financial/Auth vs Low-Risk Internal Tooling) yang dapat langsung dioperasikan dalam repositori produksi.
5. **Melakukan Code Review Tingkat Arsitektur**: membedah pull request bukan sekadar baris-per-baris, melainkan dari sudut pandang *state mutation*, batas modularitas domain, *failure modes*, dan konsistensi data terdistribusi.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                       [Hierarchy of Review Concerns]
                                     |
       +-----------------------------+-----------------------------+
       |                             |                             |
  [Tier 1: High Order]      [Tier 2: Mid Order]          [Tier 3: Low Order]
       |                             |                             |
 +-----+-----+                 +-----+-----+                 +-----+-----+
 |           |                 |           |                 |           |
[Arsitektur] [Ketepatan]     [Keamanan]  [Performa]     [Dokumentasi] [Gaya/Lint]
 (Boundaries, (Invariants,   (AuthZ/N,   (Latensi, IO,   (API Docs,    (Otomatisasi
  Coupling,    Edge Cases,    Injection,  Memory Leak,    Contextual    CI/CD Linter
  State)       Data Race)     PII Leak)   Scale Factor)   Comments)     Mandatory)
       |                             |                             |
       +-----------------------------+-----------------------------+
                                     |
                                 Dikelola via
                                     |
                      [Pragmatic Review Checklists]
                                     |
              +----------------------+----------------------+
              |                                             |
     [Structural Checklists]                       [Anti-Pattern Safeguards]
      - State Management                            - Anti-Bikeshedding
      - Transaction Boundaries                      - Anti-Rubber-Stamping
      - Failure Domain Isolation                    - Scope-Creep Defense
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Kegagalan terbesar dalam proses rekayasa perangkat lunak modern jarang disebabkan oleh kesalahan sintaksis atau kegagalan linter; kegagalan fatal di lingkungan produksi hampir selalu bersumber dari **kerusakan arsitektural, ketidakkonsistenan state, celah keamanan, dan bottleneck konkurensi**. 

Meskipun demikian, fenomena umum yang terjadi di industri adalah **Hukum Trivialitas Parkinson (*Bikeshedding*)**:
* Sebuah PR dengan 5 baris perubahan CSS atau *variable naming* memicu 40 komentar debat filosofis.
* Sebuah PR dengan 2.500 baris yang mengubah sistem isolasi transaksi database dan messaging queue disetujui dalam 5 menit dengan komentar *"LGTM! 🚀"*.

Ketika reviewer menghabiskan energi kognitif mereka untuk bertindak sebagai *human linter* (memeriksa spasi, format penamaan, kurung kurawal), mereka mengalami kelelahan mental (*review fatigue*). Akibatnya, mereka melewatkan pelanggaran arsitektur kritis seperti kebocoran domain (*domain leakage*), kueri $N+1$, tidak adanya *idempotency keys* pada endpoint pembayaran, atau *race conditions* pada pembacaan state bersama. Modul ini mengajarkan cara merestrukturisasi protokol review agar modalitas kognitif termahal tim rekayasa—waktu dan analisis senior engineer—dialokasikan secara presisi pada area dengan risiko sistemik tertinggi.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Hierarchy of Review Concerns
Hierarki ini adalah kerangka kerja berbasis prioritas yang menentukan urutan evaluasi kognitif saat seorang reviewer menganalisis perubahan kode:

1. **Arsitektur & Batas Domain (Tingkat Tertinggi)**: Apakah perubahan ini melanggar batas modularitas (*bounded context*)? Apakah ini memperkenalkan kopling sirkular (*circular dependency*)? Apakah abstraksi ini bocor (*leaky abstraction*)?
2. **Ketepatan Logika & Invarian (Correctness)**: Apakah fungsionalitas bisnis benar? Bagaimana penanganan *edge cases*? Apakah logika ini thread-safe? Apakah transaksi database menjaga keutuhan data ACID?
3. **Keamanan & Kepatuhan (Security)**: Apakah ada validasi input? Apakah otorisasi (*Broken Object Level Authorization / BOLA*) diverifikasi? Apakah ada data sensitif (PII) yang dicatat ke logging engine?
4. **Performa & Skalabilitas (Performance)**: Berapa alokasi memori heap? Apakah operasi I/O diblokir? Apakah ada potensi kueri $N+1$ atau degradasi indeks database?
5. **Gaya, Format, & Konvensi (Tingkat Terendah)**: Kerapian kode, pola penamaan variabel, struktur direktori minor. **Aturan utama: Jika dapat dideteksi oleh mesin/linter, manusia DILARANG mendebatkannya di PR review.**

### 2. Pragmatic Review Checklist
Checklist pragmatis bukanlah kuesioner birokratis berisi 50 pertanyaan wajib yang memperlambat laju rilis (*cycle time*). Ini adalah instrumen mental terdistribusi yang memandu reviewer memvalidasi invarian sistemik berdasarkan tingkat risiko perubahan (*risk tiering*).

### 3. Review Anti-Patterns
Pola-pola disfungsional yang merusak budaya engineering, memperlambat *throughput*, dan menurunkan kualitas software:
* **The Human Linter**: Menghabiskan energi mengomentari formatting yang seharusnya diurus oleh Prettier, ESLint, Checkstyle, atau `golangci-lint`.
* **The Rubber Stamp**: Menyetujui PR secara terburu-buru demi metrik kecepatan tanpa memahami dampak sistemik.
* **The Mega-PR (Kitchen Sink)**: Menggabungkan migrasi database, refactoring core domain, dan perbaikan bug kecil dalam satu PR berukuran 3.000 baris.
* **Moving the Goalposts**: Menuntut refactoring di luar lingkup PR awal setiap kali PR diperbarui.

---

## SEKSI 06 — BAGAIMANA BEKERJA (HOW)

### Alur Eksekusi Review Bertingkat (Top-Down Mental Pass)

Proses review dilakukan dalam **Tiga Putaran Pemeriksaan (Three-Pass Review Method)**:

```
[PR Masuk]
   │
   ▼
[Pass 1: Pemeriksaan Makro / Arsitektur] ──(Ada Pelanggaran?)──► [Minta Redesign/Tolak PR]
   │ (Lolos)
   ▼
[Pass 2: Pemeriksaan Mikro / Logika & Invarian] ──(Ada Cacat?)──► [Minta Revisi Logika]
   │ (Lolos)
   ▼
[Pass 3: Pemeriksaan Resiko / Keamanan & Skala] ──(Ada Resiko?)──► [Mitigasi & Hardening]
   │ (Lolos)
   ▼
[Merge Approval Diberikan]
```

#### Pass 1: Makro (Arsitektur & Integritas Desain)
Reviewer tidak membaca kode baris per baris. Reviewer membaca deskripsi PR, context ticket, dan daftar file yang berubah (`Files Changed` map).
* Tanyakan: File mana saja yang disentuh? Apakah layer `presentation` langsung mengakses layer `infrastructure` / database driver tanpa melewati layer `domain`?
* Evaluasi diagram dependensi: Apakah dependensi baru ditambahkan? Apakah pustaka eksternal (*third-party*) aman dan berbobot wajar?

#### Pass 2: Mikro (Ketepatan Logika & Perilaku Sistem)
Reviewer masuk ke file inti perubahan logika bisnis (*core domain logic*).
* Identifikasi *invarian*: Apa kondisi yang harus selalu bernilai benar sebelum dan sesudah eksekusi fungsi?
* Evaluasi status mutasi: Apakah operasi ini idempoten? Jika sistem mati di baris ke-42 akibat kegagalan listrik, apa status data di database?
* Edge cases: Nilai `nil`/`null`, array kosong, string tak terbatas, *clock drift*, pembagian dengan nol.

#### Pass 3: Risiko Sistemik (Keamanan, Konkurensi, Performa)
Reviewer memosisikan diri sebagai sistem eksternal atau penyerang.
* Konkurensi: Apakah ada *shared mutable state* tanpa mekanisme locking yang tepat? Apakah ada potensi *deadlock*?
* Data I/O: Apakah kueri SQL menggunakan indeks yang ada? Berapa ukuran batch yang ditarik ke memori?
* Sanitasi: Apakah parameter input yang belum divalidasi langsung dilempar ke RPC downstream atau database query?

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### 1. The Pyramid of Review Concerns vs. Automation Layer

```
+-------------------------------------------------------------+  REVISE BY:
|                     1. ARSITEKTUR & BOUNDARIES              |  Manusia (Staff/Senior)
|     - Boundary Leaks, Coupling, State Mutation Model        |  Fokus Kognitif: 50%
+-------------------------------------------------------------+
|                     2. KETEPATAN (CORRECTNESS)              |  Manusia (Senior/Peer)
|     - Business Invariants, Race Conditions, Edge Cases      |  Fokus Kognitif: 30%
+-------------------------------------------------------------+
|                     3. KEAMANAN & SKALABILITAS              |  Otomasi Statis (SAST)
|     - BOLA, Injection, Data Leaks, N+1 Query, Indexing      |  + Manusia (20%)
+-------------------------------------------------------------+
|                     4. GAYA & FORMATTING                    |  100% MESIN / CI/CD
|     - Tabs/Spaces, Naming Convention, Imports Ordering      |  Fokus Manusia: 0%
+-------------------------------------------------------------+
```

### 2. Anatomi Lifecycle Code Review Ideal vs Disfungsional

```
SIKLUS IDEAL (High Leverage):
Dev Submits PR ──► [CI Auto Checks: Lint/Tests] ──► [Architectural Pass] ──► [Logic Pass] ──► Merged
                         │ (Failed: Blocked)
                         ▼
                   (Fix in 2 mins)

SIKLUS DISFUNGSIONAL (Bikeshedding Hell):
Dev Submits PR ──► Reviewer A: "Rename this var" ──► Dev Renames ──►
Reviewer B: "I prefer snake_case here" ──► Dev Changes ──►
Reviewer C: "Why didn't you refactor the whole module?" (Goalpost Moving) ──►
[Fatigue sets in] ──► "Whatever, LGTM" ──► Production Outage (Data Race/Deadlock)
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Contoh ini mengilustrasikan perbedaan review yang berfokus pada gaya (salah) vs review yang berfokus pada hierarki kekhawatiran yang benar.

### Kode yang Ditinjau (Go)

```go
package service

import (
    "database/sql"
    "fmt"
)

type WalletService struct {
    db *sql.DB
}

// TransferFunds mentransfer sejumlah uang antar dua akun
func (s *WalletService) TransferFunds(fromAccountID string, toAccountID string, amount float64) error {
    var balance float64
    query := fmt.Sprintf("SELECT balance FROM accounts WHERE id = '%s'", fromAccountID)
    row := s.db.QueryRow(query)
    err := row.Scan(&balance)
    if err != nil {
        return err
    }

    if balance >= amount {
        _, err = s.db.Exec(fmt.Sprintf("UPDATE accounts SET balance = balance - %f WHERE id = '%s'", amount, fromAccountID))
        if err != nil {
            return err
        }
        
        _, err = s.db.Exec(fmt.Sprintf("UPDATE accounts SET balance = balance + %f WHERE id = '%s'", amount, toAccountID))
        if err != nil {
            return err
        }
    }
    return nil
}
```

### Review Buruk: Gaya & Bikeshedding (Taraf Rendah)
Reviewer fokus pada hal sepele:
```markdown
❌ Reviewer Comment:
Line 13: Kenapa parameternya ditulis `fromAccountID string, toAccountID string`? 
Bisa dipersingkat jadi `fromAccountID, toAccountID string`.
Line 19: Gunakan backticks untuk SQL query multiline agar lebih rapi.
Line 24: Lebih baik `err != nil` dibuat one-liner `if err := ...; err != nil`.
```
*Dampak: Kode di-merge dengan perubahan gaya, namun sistem mengalami eksploitasi SQL Injection dan kehilangan uang akibat Race Condition.*

### Review Benar: Berdasarkan Hierarchy of Concerns (Arsitektur, Ketepatan, Keamanan)
Reviewer mengabaikan preferensi sintaksis dan langsung menyerang akar permasalahan:
```markdown
CRITICAL CONCERNS DETECTED:

1. [Security - Injection] (Severity: BLOCKER)
   Line 15, 24, 29: Kueri dieksekusi menggunakan `fmt.Sprintf` dengan parameter string. 
   Ini celah fatal SQL Injection. Gunakan parameterized queries: 
   `db.QueryRowContext(ctx, "SELECT balance FROM accounts WHERE id = $1", fromAccountID)`.

2. [Architecture & Correctness - Atomicity & Race Condition] (Severity: BLOCKER)
   Operasi transfer ini melibatkan dua pembaruan state independen tanpa Transaksi Database (`BEGIN...COMMIT`) 
   dan tanpa isolasi konkurensi.
   - Jika proses crash setelah `UPDATE` pertama, uang berkurang dari `fromAccountID` tetapi tidak pernah masuk ke `toAccountID` (Pelanggaran Invarian Konsistensi).
   - Terjadi kondisi *Time-Of-Check to Time-Of-Use (TOCTOU)*: Pengecekan saldo `balance >= amount` dilakukan di memori aplikasi. Dua request transfer paralel dapat membaca saldo yang sama secara bersamaan, mengakibatkan penarikan ganda (*Double Spending*).
   
Action Required:
Bungkus operasi dalam `s.db.BeginTx()`. Gunakan lock eksplisit pada database level (`SELECT ... FOR UPDATE`) atau lakukan operasi atomic balance update langsung di SQL: 
`UPDATE accounts SET balance = balance - $1 WHERE id = $2 AND balance >= $1`.
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Mari kita bedah skenario nyata sistem order processing pada platform e-commerce dengan skala beban tinggi menggunakan TypeScript / Node.js.

### Kode Asli Pull Request (Under Review)

```typescript
// File: src/modules/orders/order.controller.ts
import { Request, Response } from 'express';
import { OrderModel } from '../../infra/database/models/Order';
import { InventoryService } from '../inventory/inventory.service';
import { NotificationClient } from '../../infra/external/notification.client';

export class OrderController {
  private inventoryService = new InventoryService();
  private notificationClient = new NotificationClient();

  // POST /orders/checkout
  async checkout(req: Request, res: Response) {
    const { userId, items, totalAmount } = req.body;

    // 1. Cek stok inventori
    for (const item of items) {
      const stock = await this.inventoryService.getStock(item.productId);
      if (stock < item.quantity) {
        return res.status(400).json({ error: `Out of stock: ${item.productId}` });
      }
    }

    // 2. Simpan order ke database
    const order = await OrderModel.create({
      userId,
      totalAmount,
      status: 'PENDING',
      items
    });

    // 3. Potong stok
    for (const item of items) {
      await this.inventoryService.deductStock(item.productId, item.quantity);
    }

    // 4. Kirim notifikasi async via network
    await this.notificationClient.sendOrderConfirmation(userId, order.id);

    return res.status(201).json(order);
  }
}
```

### Form Eksekusi Review Arsitektural (Senior Staff Review Sheet)

Berikut adalah anotasi review pragmatis yang mengaplikasikan taksonomi lengkap:

```markdown
### Summary PR Assessment
- **Status**: REQUEST CHANGES (Hard Block)
- **Tingkat Resiko**: HIGH (Transaksional, Finansial, Stateful)
- **Poin Utama Review**:
  1. Pelanggaran Batas Arsitektural (Layering Violation)
  2. Kegagalan Idempotensi & Distributed State Failure
  3. Kueri N+1 pada I/O Network & Database

---

### [Concern 1: Arsitektur & Modular Boundaries]
- **Lokasi**: `src/modules/orders/order.controller.ts:13`
- **Temuan**: Instansiasi Langsung (`new InventoryService()`, `new NotificationClient()`).
- **Masalah**: Controller terikat erat (*tightly coupled*) dengan implementasi konkret infrastruktur. Ini mencegah Unit Testing dengan mock dan melanggar prinsip *Dependency Inversion*. Selain itu, controller web HTTP bertanggung jawab mengatur alur domain transaksi, yang seharusnya menjadi milik `OrderUseCase` atau `OrderApplicationService`.
- **Rekomendasi Solusi**: 
  Pindahkan orkestrasi ke Application Layer. Gunakan *Dependency Injection* melalui konstruktor.

---

### [Concern 2: Ketepatan Logika & Konsistensi Invarian]
- **Lokasi**: Baris 17-38 (Deduct Stock & Create Order flow)
- **Temuan**: Skenario Kegagalan Parsial (*Partial Failure Mode*).
- **Masalah**: 
  - Tidak ada *Database Transaction* yang menyatukan pembuatan order dan pemotongan stok.
  - Jika `this.inventoryService.deductStock` gagal pada item ke-3 (misal network timeout atau database lock timeout), dua item pertama sudah terpotong stoknya, order tersimpan dengan status `PENDING`, dan sistem berada dalam kondisi inkonsisten (*corrupted state*).
  - Pengecekan stok di awal (baris 17-22) tidak menjamin ketersediaan saat pemotongan (baris 33-35) karena tidak ada distributed lock atau atomic reservation.
- **Rekomendasi Solusi**:
  Implementasikan pola Unit of Work / Database Transaction. Jika inventori berada di microservice terpisah, gunakan pola *Two-Phase Reservation* (Reserve -> Confirm) atau *Saga Pattern* dengan kompensasi otomatis.

---

### [Concern 3: Skalabilitas & Performa I/O]
- **Lokasi**: Baris 17-21 dan Baris 33-35
- **Temuan**: Anti-pattern Kueri Loop $N+1$.
- **Masalah**: Jika order memiliki 20 item, kode ini mengeksekusi 40 network round-trip terpisah (20 fetch, 20 deduct). Ini akan menghabiskan connection pool dan meningkatkan latensi secara eksponensial.
- **Rekomendasi Solusi**:
  Gunakan operasi batch: `inventoryService.reserveStocksBatch(items)`.

---

### [Concern 4: Keandalan & Ketahanan Sistem (Resilience)]
- **Lokasi**: Baris 38
- **Temuan**: Inline Blocking I/O untuk Notifikasi Pihak Ketiga (`await sendOrderConfirmation`).
- **Masalah**: Jika layanan notifikasi mengalami latensi 10 detik atau down (504 Gateway Timeout), proses checkout pengguna akan gagal atau timeout, padahal order dan inventori sudah terpotong. Notifikasi bukanlah operasi transaksional kritis (*non-core side-effect*).
- **Rekomendasi Solusi**:
  Gunakan Pola *Transactional Outbox* atau kirim event ke message broker (Kafka/RabbitMQ) secara asynchronous. Jangan pernah memblokir siklus HTTP transaksional dengan panggilan jaringan non-kritis.
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

Dalam menerapkan hierarchy of concerns dan checklist review, ada serangkaian trade-off mendasar yang harus dinavigasi oleh engineering leadership:

### 1. Kecepatan Pengiriman (*Throughput*) vs. Ketahanan Sistem (*Resilience*)
* **Strict Architecture Enforcement**: Memaksa setiap perubahan untuk memenuhi standar arsitektur murni (misal: Hexagonal Architecture lengkap dengan Ports & Adapters) dapat menurunkan kecepatan tim rilis di awal (*lead time to change*).
* **Pragmatic Compromise**: Untuk kode eksperimental (A/B testing, internal POC), review fokus pada: *apakah kode ini terisolasi dan mudah dihapus tanpa merusak dependensi inti?* Jika ya, turunkan standar arsitekturalnya, tetapi jaga ketat batas isolasinya.

### 2. Manual Checklist vs. Cognitive Overload
* **Birokrasi Checklist**: Mengharuskan reviewer mengisi 30 poin checklist di setiap PR akan memicu kelelahan kognitif. Hasil akhirnya adalah *blind clicking* (mencentang semua box tanpa membaca kode).
* **Solusi**: Batasi checklist manusia maksimal pada 5–7 pertanyaan strategis bernilai tinggi yang tidak bisa dideteksi oleh static analyzer.

### 3. Matriks Keputusan Prioritas Review

| Tipe Perubahan Kode | Prioritas 1 | Prioritas 2 | Tindakan Linter/CI |
| :--- | :--- | :--- | :--- |
| **Core Financial / Ledger** | Ketepatan Transaksi & Concurrency | Keamanan (Tamper-proofing) | Format, Coverage 100%, Static Typing |
| **High-Traffic Public API** | Skalabilitas I/O & Memory | Desain Kontrak API (Backward Compat) | Schema validation, Linting |
| **Internal Ops Dashboard** | Waktu Pengiriman | Fungsionalitas Dasar | Standar Linter Default |
| **Worker Async Event Handler** | Idempotensi & Failure Retries | Kecepatan Throughput | Dead-letter queue validation |

---

## SEKSI 11 — BEST PRACTICES

### 1. Delegasikan Syntax dan Konvensi Sepenuhnya ke Mesin
Gunakan Git Pre-commit Hooks (Husky/lefthook) dan CI Pipeline. Manusia **dilarang keras** mengomentari:
* Spasi, indentasi, dan batas kolom teks.
* Urutan import pustaka.
* Penamaan variabel yang polanya dapat diatur linter (misal: `camelCase` vs `snake_case`).
* Cakupan baris unit test sederhana (gunakan coverage gate otomatis).

### 2. Aturan Ukuran Pull Request: *The Small PR Rule*
* Batasi PR maksimal **200–400 baris perubahan** (excluding generated code / locks).
* Menurut studi empiris (SmartBear/Cisco Systems), densitas deteksi cacat menurun drastis setelah 400 baris kode dalam satu sesi review. Kecepatan review optimal adalah 200-300 baris per jam.

```
Densitas Cacat
 Ditemukan
    ▲
    │         Puncak Efektivitas Review
    │              (200-400 Baris)
    │                  ┌───┐
    │                 ┌┘   └┐
    │                ┌┘     └┐
    │               ┌┘       └┐
    │              ┌┘         └──────┐
    │             ┌┘                 └──────────────────┐
    └─────────────┴─────────────────────────────────────┴──────►
    0            200       400       600       800     1000+ Baris PR
```

### 3. Terapkan Konvensi Komentar *Conventional Comments*
Untuk mengeliminasi ambiguitas komunikasi dan bikeshedding, beri label pada setiap feedback:
* `praise:` - Pujian untuk solusi elegan (membangun psikologi tim).
* `nitpick (non-blocking):` - Masukan minor opsional. PR boleh di-merge tanpa revisi ini.
* `question:` - Meminta klarifikasi maksud desain, bukan tuduhan kesalahan.
* `suggestion:` - Alternatif pendekatan logis, sediakan contoh kode konkrit.
* `issue (blocking):` - Pelanggaran arsitektur, bug fungsional, atau celah keamanan. **Wajib diselesaikan sebelum merge.**

### 4. Terapkan Time-Boxing dan Prioritas Review
Review bukanlah tugas sampingan saat senggang. Review adalah pemblokir utama *cycle time*. Tim harus menetapkan Service Level Agreement (SLA):
* PR di bawah 200 baris wajib mendapatkan review pertama dalam waktu maksimal 4 jam kerja.
* Jangan menunda review hingga akhir sprint.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. *The Bikeshedding Trap* (Hukum Trivialitas)
* **Gejala**: Reviewer berdebat selama 3 hari tentang apakah sebuah enum status harus bernama `ORDER_STATUS_UNPAID` atau `ORDER_STATUS_PENDING_PAYMENT`, sementara tidak ada yang menyadari bahwa pembacaan status tidak menggunakan indeks database.
* **Mitigasi**: Tetapkan aturan: jika sebuah keputusan dapat diubah dalam 10 menit tanpa migrasi data (*two-way door decision*), setujui pilihan pembuat PR dan lanjutkan.

### 2. *Goalpost Moving* (Menggeser Garis Akhir)
* **Gejala**: Dev menyelesaikan revisi yang diminta oleh Reviewer A. Pada siklus review kedua, Reviewer A (atau Reviewer B yang baru bergabung) menuntut refactoring di file lain yang tidak terkait langsung dengan scope awal.
* **Mitigasi**: Ruang lingkup review dikunci pada diff awal dan komentar yang terdaftar di putaran pertama. Scope tambahan harus dicatat sebagai Tech Debt ticket baru di Jira/Linear, bukan memblokir PR aktif.

### 3. *The Human Linter Syndrome*
* **Gejala**: 90% komentar review berisi "tolong hapus baris kosong ini" atau "ganti kutip dua jadi kutip satu".
* **Mitigasi**: Terapkan *Branch Protection Rule*: PR tidak dapat dibuka atau ditinjau jika automated CI status checks (linter, security scanner, typechecker) masih berstatus merah (*failing*).

### 4. *LGTM on a 3000-Line PR* (Rubber-Stamping)
* **Gejala**: PR masif di-merge dalam waktu singkat dengan review dangkal.
* **Mitigasi**: Berikan hak prerogatif kepada reviewer untuk menolak mereview PR: *"PR ini terlalu besar dan menggabungkan 3 konsep bisnis berbeda. Mohon pecah menjadi 3 PR independen sebelum review dimulai."*

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Skenario Latihan
Anda adalah Staff Software Engineer yang menerima Pull Request berikut. PR ini mengklaim mengimplementasikan fitur "Klaim Kupon Diskon Terbatas".

```go
// Package coupon menangani klaim kupon diskon
package coupon

import (
    "context"
    "database/sql"
    "errors"
    "time"
)

type CouponService struct {
    DB *sql.DB
}

type ClaimRequest struct {
    UserID    int64
    CouponCode string
}

func (s *CouponService) ClaimCoupon(ctx context.Context, req ClaimRequest) error {
    // 1. Cek kupon di database
    var id int64
    var quota int
    var expiresAt time.Time

    query := "SELECT id, remaining_quota, expires_at FROM coupons WHERE code = $1"
    err := s.DB.QueryRowContext(ctx, query, req.CouponCode).Scan(&id, &quota, &expiresAt)
    if err != nil {
        if errors.Is(err, sql.ErrNoRows) {
            return errors.New("kupon tidak ditemukan")
        }
        return err
    }

    // 2. Validasi tanggal kedaluwarsa
    if time.Now().After(expiresAt) {
        return errors.New("kupon sudah kedaluwarsa")
    }

    // 3. Validasi kuota
    if quota <= 0 {
        return errors.New("kuota kupon habis")
    }

    // 4. Catat klaim oleh user
    insertClaim := "INSERT INTO user_coupons (user_id, coupon_id, claimed_at) VALUES ($1, $2, $3)"
    _, err = s.DB.ExecContext(ctx, insertClaim, req.UserID, id, time.Now())
    if err != nil {
        return errors.New("gagal mencatat klaim")
    }

    // 5. Kurangi sisa kuota
    updateQuota := "UPDATE coupons SET remaining_quota = remaining_quota - 1 WHERE id = $1"
    _, err = s.DB.ExecContext(ctx, updateQuota, id)
    if err != nil {
        return errors.New("gagal memperbarui kuota")
    }

    return nil
}
```

### Tugas Peserta
1. Lakukan audit kode di atas menggunakan **Hierarchy of Review Concerns**.
2. Identifikasi minimal:
   - Satu pelanggaran arsitektur / data integrity fatal (High Severity).
   - Satu celah konkurensi (Race Condition).
   - Satu celah kegagalan parsial (*failure atomicity*).
3. Tuliskan komentar code review formal dengan struktur:
   - Level Concern (Arsitektur / Ketepatan / Keamanan / Skala)
   - Deskripsi Masalah
   - Bukti / Skenario Kegagalan Produksi
   - Usulan Solusi (disertai kode perbaikan)

---

### Solusi Acuan (Reference Solution)

```markdown
### Review Summary
Status: CHANGES REQUESTED (Blocker Found)

Terima kasih atas implementasinya. Logika dasar sudah mudah dibaca dan parameter binding sudah aman dari SQL Injection. Namun, ada masalah kritis terkait integritas data dan konkurensi yang wajib diperbaiki sebelum masuk ke produksi:

---

#### 1. [Correctness & Concurrency] Race Condition: Kuota Jebol (Over-allocation)
- **Tingkat Resiko**: CRITICAL
- **Analisis**: 
  Pengecekan kuota (`if quota <= 0`) dilakukan pada layer aplikasi berdasarkan snapshot data dari kueri `SELECT`.
  Jika sisa kuota tersisa 1, lalu ada 100 request masuk secara bersamaan untuk `CouponCode` yang sama dalam rentang milidetik yang sama, ke-100 thread tersebut akan membaca `remaining_quota = 1`. Semua lolos validasi, dan semuanya mengeksekusi `UPDATE ... SET remaining_quota = remaining_quota - 1`.
- **Dampak Produksi**: Kupon dengan kuota 100 dapat diklaim oleh 500 pengguna (finansial defisit).
- **Perbaikan**:
  Delegasikan invarian kuota langsung ke database engine secara atomik:
  ```sql
  UPDATE coupons 
  SET remaining_quota = remaining_quota - 1 
  WHERE id = $1 AND remaining_quota > 0;
  ```
  Evaluasi `RowsAffected()`. Jika 0 baris berubah, kembalikan error "kuota kupon habis".

---

#### 2. [Architecture & Correctness] Kegagalan Transaksionalitas (Atomicity Violation)
- **Tingkat Resiko**: HIGH
- **Analisis**:
  Operasi pencatatan klaim (`INSERT INTO user_coupons`) dan pembaruan kuota (`UPDATE coupons`) dieksekusi secara independen tanpa transaksi database (`sql.Tx`).
  Jika koneksi database putus atau container dihentikan paksa (OOM/Killed) tepat setelah operasi `INSERT` berhasil, kuota kupon tidak pernah terpotong. Sebaliknya, jika urutannya dibalik, kuota terpotong tetapi hak user tidak tercatat.
- **Perbaikan**:
  Bungkus seluruh alur dalam satu transaksi database:
  ```go
  tx, err := s.DB.BeginTx(ctx, &sql.TxOptions{Isolation: sql.LevelReadCommitted})
  if err != nil {
      return err
  }
  defer tx.Rollback() // Aman jika commit berhasil
  // ... Eksekusi query dengan tx ...
  return tx.Commit()
  ```

---

#### 3. [Correctness] Idempotency & Double Claiming
- **Tingkat Resiko**: HIGH
- **Analisis**:
  Tidak ada pengecekan apakah `req.UserID` sudah pernah mengklaim kupon ini sebelumnya. User dapat melakukan spam click pada tombol frontend dan mendapatkan 10 kupon yang sama.
- **Perbaikan**:
  Tambahkan database constraint unik majemuk (*composite unique constraint*) pada database:
  `ALTER TABLE user_coupons ADD CONSTRAINT unique_user_coupon UNIQUE (user_id, coupon_id);`
  Tangani database error kode duplicate key violation (PostgreSQL `23505`) di layer Go.
```

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

Jawab pertanyaan-pertanyaan berikut secara mandiri untuk menguji pemahaman Anda:

1. **Mengapa formatting kode, penataan import, dan konvensi penamaan camelCase vs snake_case tidak boleh menjadi bahan perdebatan reviewer manusia di Pull Request?**
   * A. Karena hal tersebut tidak penting untuk performa aplikasi.
   * B. Karena perdebatan tersebut menghabiskan kapasitas kognitif reviewer yang seharusnya dialokasikan untuk mendeteksi cacat arsitektur dan logika yang tidak dapat dideteksi mesin.
   * C. Karena semua programmer harus bebas menulis gaya kode mereka sendiri.
   * D. Karena hal itu otomatis diperbaiki oleh compiler bahasa pemrograman.

2. **Dua goroutine atau thread membaca saldo rekening pengguna ($100). Keduanya secara simultan mengeksekusi transfer $80 setelah mengecek saldo di memori aplikasi (`if balance >= 80`). Keduanya berhasil mentransfer, menyisakan saldo $-60. Cacat review concern kategori apa ini?**
   * A. Security (Injection)
   * B. Architecture (Boundary Coupling)
   * C. Correctness (Race Condition / TOCTOU)
   * D. Performance (Memory Leak)

3. **Seorang engineer mengajukan PR 15 baris yang memodifikasi controller HTTP. Controller tersebut kini langsung memanggil `db.RawQuery(...)` untuk mengambil data, memotong pemanggilan Domain Service dan Repository. Reviewer menyetujuinya karena "kodenya pendek dan kuerinya cepat". Apa kesalahan reviewer tersebut?**
   * A. Mengabaikan Hierarchy of Concerns: mendahulukan performa/kesederhanaan lokal di atas batas arsitektural (modular boundary leak).
   * B. Kurang memeriksa unit testing pada database driver.
   * C. Seharusnya menyuruh author menggunakan ORM modern.
   * D. Mengabaikan optimasi kompresi response HTTP.

4. **Apa arti istilah *Bikeshedding* dalam konteks code review?**
   * A. Tindakan memecah satu PR besar menjadi micro-PR.
   * B. Kecenderungan memberikan perhatian berlebih pada hal-hal sepele sambil mengabaikan isu besar yang kompleks.
   * C. Meninjau kode tanpa menguji coba kodenya di local environment.
   * D. Memberikan tinjauan arsitektur secara mendalam tanpa melihat detail implementasi.

5. **Apa tindakan terbaik yang harus diambil seorang Staff Engineer jika dihadapkan pada PR berukuran 4.500 baris kode yang mencakup 8 modul berbeda?**
   * A. Luangkan waktu 3 hari membaca seluruh kode baris per baris.
   * B. Langsung berikan komentar "LGTM" karena perubahan sudah diuji oleh tim QA.
   * C. Tolak PR secara sopan dan minta author memecahnya menjadi serangkaian PR kecil yang kohesif dan dapat direview secara independen.
   * D. Jalankan linter dan merge jika test pipeline hijau.

### Kunci Jawaban
1. **B**
2. **C**
3. **A**
4. **B**
5. **C**

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **Google Engineering Practices Documentation**: *How to Do a Code Review* (`https://google.github.io/eng-practices/review/`)
* **SmartBear Software**: *Best Kept Secrets of Peer Code Review* (Studi Cisco Systems terhadap 2.500 review).
* **Karl E. Wiegers**: *Peer Reviews in Software: A Practical Guide*, Addison-Wesley Professional.
* **Conventional Comments Standard**: `https://conventionalcomments.org/`
* **Martin Fowler**: *Refactoring: Improving the Design of Existing Code (2nd Edition)* - Bab tentang Code Smells & Architectural Degradation.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1. **Hierarchy of Concerns**: Review kode wajib memprioritaskan Arsitektur > Ketepatan Logika > Keamanan > Performa > Konvensi. Isu arsitektur yang lolos ke produksi memiliki biaya perbaikan (*cost of fix*) ribuan kali lebih mahal dibanding masalah estetika.
2. **Eliminasi Bikeshedding**: Otomatisasikan setiap aspek sintaksis dan gaya menggunakan linter dan automated test checks. Waktu manusia adalah aset termahal tim rekayasa.
3. **Ukuran PR Menentukan Kualitas Review**: PR optimal berkisar antara 200–400 baris. Di atas 500 baris, efektivitas reviewer menurun drastis (*Rubber-Stamp effect*).
4. **Review Bukan Sekadar Linter**: Tugas reviewer manusia adalah memvalidasi apa yang **tidak terlihat** di baris kode: *invarian yang dilanggar, race conditions, edge cases, partial failure behavior,* dan *sistemik failure domain*.

---

## SEKSI 17 — GLOSARIUM

* **Bikeshedding (Hukum Trivialitas Parkinson)**: Kecenderungan psikologis manusia untuk menghabiskan waktu dan energi memperdebatkan hal-hal kecil dan sepele karena hal tersebut paling mudah dipahami, sementara topik inti yang kompleks diabaikan.
* **Rubber-Stamping**: Praktik memberikan persetujuan PR secara formalitas tanpa membaca, menganalisis, atau memahami kode dan implikasinya.
* **Invarian (System Invariant)**: Kondisi logis atau matematis yang harus selalu bernilai benar dalam seluruh siklus hidup sistem (contoh: saldo rekening tidak boleh bernilai negatif; kuota klaim tidak boleh melebihi batas).
* **TOCTOU (Time-Of-Check to Time-Of-Use)**: Kategori bug konkurensi di mana status sistem berubah antara waktu pemeriksaan kondisi dan waktu eksekusi tindakan berdasarkan hasil pemeriksaan tersebut.
* **Transactional Outbox Pattern**: Pola desain arsitektural yang menjamin konsistensi antara operasi penyimpanan database dan pengiriman event ke message broker tanpa kegagalan terdistribusi ganda.

---

## SEKSI 18 — CATATAN INSTRUKTUR

### Poin Penekanan Materi
* Tekankan kepada peserta bahwa code review **bukan ajang pembuktian superioritas intelektual**. Budaya review yang toksik menghancurkan psikologi tim. Komentar harus bersifat objektif, ditujukan pada kode, bukan pada kepribadian engineer pembuat kode.
* Simulasikan latihan hands-on (Seksi 13) di kelas interaktif. Minta peserta membaca kode selama 5 menit, catat komentar mereka, lalu tunjukkan berapa banyak peserta yang terjebak mengomentari nama variabel atau format query SQL alih-alih menemukan *Double Spending Race Condition*.
* Pastikan peserta memahami batasan: jangan jadikan arsitektur alasan untuk *over-engineering*. Terapkan prinsip YAGNI (*You Aren't Gonna Need It*) secara proporsional.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi 1.0.0** (Maret 2026):
  * Rilis inisial kurikulum standar industri.
  * Penambahan Taksonomi Hierarchy of Review Concerns.
  * Penyusunan Pragmatic Review Checklist dan panduan anti-bikeshedding.
  * Studi kasus konkret perbankan dan e-commerce berbasis Go dan TypeScript.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya**: `CR-ARCH-0103` — Fondasi Pemodelan Mental Sistem Terdistribusi
* **Modul Saat Ini**: `CR-ARCH-0201` — Taksonomi & Checklist Review Standar Industri: Hierarchy of Review Concerns
* **Modul Berikutnya**: `CR-ARCH-0202` — Mendeteksi Pelanggaran Batas Modularitas, Kopling Tersembunyi, dan Leaky Abstractions dalam PR