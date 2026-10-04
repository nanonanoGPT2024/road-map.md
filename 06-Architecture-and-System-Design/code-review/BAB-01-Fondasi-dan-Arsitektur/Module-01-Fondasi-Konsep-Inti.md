# Bab 01 Module 01: Anatomi dan Filosofi Code Review Modern

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
*   **Menganalisis** batas kognitif peninjau (*reviewer cognitive load*) berdasarkan korelasi antara *Lines of Code* (LOC) dan *defect density* menurut studi empiris rekayasa perangkat lunak.
*   **Merancang** arsitektur *review pipeline* modern yang memisahkan verifikasi deterministik (otomatisasi CI/Linter) dari verifikasi heuristik (evaluasi desain manusia).
*   **Mengidentifikasi** dan memitigasi kegagalan proses peninjauan kode, seperti fenomena *bikeshedding* (Hukum Trivialitas Parkinson) dan *rubber-stamping*.
*   **Menerapkan** taksonomi umpan balik terstruktur berbasis *Conventional Comments* untuk mereduksi ambiguitas komunikasi asinkron antar-insinyur.
*   **Mengonfigurasi** tata kelola cabang (*branch protection rules*) dan template *Pull Request* (PR) yang menjamin kepatuhan terhadap prinsip *Four-Eyes* (*two-person rule*).

---

### 2. Introduction & Conceptual Hook
Dalam rekayasa perangkat lunak skala produksi, *Pull Request* berukuran 2.500 baris kode hampir selalu direspons dengan komentar: *"LGTM! (Looks Good To Me)"* dalam waktu 5 menit, lalu digabungkan (*merged*). Sebaliknya, *Pull Request* 10 baris kode yang memodifikasi format ekspresi reguler sering kali memicu perdebatan sengit sepanjang 40 komentar. Anomali ini dikenal sebagai **Hukum Trivialitas Parkinson (*Bikeshedding*)**: tim memberikan perhatian terbesar pada hal-hal yang paling sepele karena hal tersebut paling mudah dipahami.

```
+---------------------------------------------------------------+
|                      THE CODE REVIEW PARADOX                  |
|                                                               |
|   10 lines of code change  --> 40 comments, 3 days of debate  |
|   2,500 lines of code diff --> "LGTM! :rocket:" (merged in 5m)|
+---------------------------------------------------------------+
```

Code review modern bukanlah ajang pembuktian superioritas intelektual atau sesi pencarian kesalahan spasi (*linting* manual). Code review adalah **mekanisme kontrol kualitas terdistribusi dan gerbang transfer pengetahuan asinkron** yang beroperasi di bawah batasan kognitif manusia. Tanpa pemahaman filosofis dan sistemik mengenai cara kerja peninjauan kode, proses ini berubah menjadi *bottleneck* rekayasa yang destruktif: memperlambat *lead time* rilis tanpa memberikan jaminan reduksi cacat (*defect rate*).

---

### 3. Why It Matters (The "Why")
Berdasarkan data dari IBM System Science Institute, biaya perbaikan cacat perangkat lunak (*software defect*) meningkat secara eksponensial seiring berjalannya fase siklus hidup pengembangan sistem:

$$\text{Cost to Fix: Maintenance Phase} \approx 100 \times \text{Cost to Fix: Design/Code Phase}$$

Code review adalah garis pertahanan terakhir dalam strategi *Shift-Left* sebelum sebuah artefak kode diintegrasikan ke cabang utama dan disebarkan ke lingkungan produksi.

```
Biaya Relatif Perbaikan Cacat:
Design        [x1]
Implementation[x6.5]
Code Review   [x15]  <-- Garis Pertahanan Shift-Left Terakhir Manusia
Testing (QA)  [x40]
Production    [x100]
```

Manfaat sistemik dari code review yang diimplementasikan secara terstruktur meliputi:
1.  **Reduksi Defect Escape Rate:** Menangkap kesalahan logika bisnis (*business logic flaws*) yang lolos dari unit test otomatis.
2.  **Dekontaminasi Technical Debt:** Mencegah degradasi integritas arsitektur dengan memblokir peretasan sementara (*hacky workarounds*) yang melanggar kontrak domain.
3.  **Eliminasi Truck Factor (Bus Factor):** Menyebarkan kepemilikan kode (*code ownership*) sehingga pengetahuan arsitektural tidak terisolasi pada satu insinyur saja.
4.  **Normalisasi Standar Rekayasa:** Bertindak sebagai instrumen *mentorship* organik berbiaya rendah bagi insinyur junior melalui evaluasi langsung terhadap kode kontekstual.

---

### 4. Core Concept & Theoretical Foundations (The "What")

#### Batasan Kognitif Cisco SmartBear Study
Studi empiris komprehensif oleh Cisco Systems (melibatkan 2.500 tinjauan, 50 insinyur, 3,2 juta baris kode) menetapkan tiga hukum fisik peninjauan kode:

1.  **Batas Kecepatan Peninjauan (*Review Rate*):** Kecepatan inspeksi optimal manusia berada di bawah **300–500 LOC per jam**. Di atas 500 LOC/jam, kemampuan mendeteksi cacat menurun drastis (*defect density drop-off*).
2.  **Ukuran Maksimum Per Sesi (*Batch Size*):** Peninjau tidak boleh mengevaluasi lebih dari **200–400 baris kode dalam satu sesi**. Melebihi 400 LOC, kelelahan kognitif (*cognitive fatigue*) mendominasi, dan tingkat deteksi cacat mendekati nol.
3.  **Batas Durasi Waktu (*Time Cap*):** Efektivitas peninjauan menurun signifikan setelah **60 menit**. Peninjauan harus dilakukan secara berkala dalam blok waktu terpisah.

```
Defect Density
(Defects Found / kLOC)
   ^
   |     OPTIMAL ZONE
40 |    [============]
   |    /            \
20 |   /              \   FATIGUE THRESHOLD
   |  /                \-------------------------- (LGTM Cliff)
 0 +-------------------------------------------->
   0   100   200   300   400   500   600   700  LOC
```

#### Dual-Track Verification Engine
Sistem code review modern membagi inspeksi kode menjadi dua jalur paralel yang tidak boleh tumpang tindih:

```
+----------------------------------------------------------------+
|                   DUAL-TRACK REVIEW ENGINE                     |
+----------------------------------------------------------------+
| 1. DETERMINISTIC (Mesin / CI Pipeline)                         |
|    - Static Analysis (SAST) & Formatting (Linter)              |
|    - Type Checking & Compilation Integrity                     |
|    - Test Coverage & Mutation Score Validation                 |
|    - Secret Scanning & Dependency Vulnerability Check          |
+----------------------------------------------------------------+
| 2. HEURISTIC (Manusia / Code Reviewer)                         |
|    - Kesesuaian Kebutuhan Domain / Logika Bisnis               |
|    - Batasan Arsitektur & Pola Desain (Clean/Hexagonal/DDD)   |
|    - Kompleksitas Waktu & Ruang Algoritmik (Edge Cases)       |
|    - Ergonomi API & Kemudahan Pemeliharaan (Maintainability)   |
+----------------------------------------------------------------+
```

Jika seorang *reviewer* manusia menghabiskan energi untuk mengomentari kesalahan spasi, penamaan variabel yang tidak sesuai format kebab/camelCase, atau *unused imports*, maka sistem rekayasa tersebut mengalami kegagalan otomasi (*tooling failure*).

---

### 5. Architectural & System Mechanics (The "How It Works Under the Hood")

Mekanisme code review diintegrasikan langsung ke dalam arsitektur kontrol versi (Git) melalui *Branch Protection Rules* dan *Webhook-driven CI Pipelines*.

#### Status Checks dan Atomic Transitions
1.  **Branch Isolation:** Pengembang dilarang melakukan *push* langsung ke *trunk branch* (`main` atau `master`). Seluruh perubahan wajib melalui *ephemeral feature branch*.
2.  **Webhook Firing:** Saat PR dibuka, server Git (GitHub/GitLab) menembakkan *webhook event* (`pull_request.opened`) ke *CI Orchestrator*.
3.  **Deterministic Evaluation:** CI memicu *runner* untuk mengeksekusi *Linters*, *SAST tools*, dan *Automated Tests*. Hasilnya dikirimkan kembali ke Git API dalam bentuk status kriteria: `pending`, `failure`, atau `success`.
4.  **Human Gatekeeping:** Server Git mengevaluasi ekspresi logika perlindungan cabang:
    
$$\text{CanMerge} = (\text{CI Status} == \text{SUCCESS}) \land (\text{Human Approvals} \ge N) \land (\text{Conversations} == \text{RESOLVED})$$

5.  **Merge Execution:** Git mengeksekusi integrasi komit menggunakan salah satu dari strategi: *Squash and Merge*, *Rebase and Merge*, atau *Merge Commit (Merge via non-fast-forward)*.

---

### 6. Architectural / Workflow Diagrams

#### Alur Kerja State Machine Pull Request Modern
Diagram berikut mengilustrasikan transisi status PR dari pembukaan cabang hingga penggabungan (*merge*):

```
+---------------+
| Local Feature |
| Branch Commit |
+-------+-------+
        | git push origin feature/X
        v
+-------+-------+
|  PR Created   |
+-------+-------+
        |
        +-----------------------------------+
        |                                   |
        v [Trigger Webhook]                 v [Notify Assignee]
+-------+-------+                   +---------------+
| CI Automation |                   | Human Peer    |
| - Linter      |                   | Reviewer      |
| - Unit Tests  |                   +-------+-------+
| - Security    |                           |
+-------+-------+                           |
        |                                   |
    [Pass/Fail]                             |
        |                                   |
        v                                   v
+-------+-------+   Changes Requested  +----+-----------+
| CI Status:    | <--------------------+ Evaluate Logic &|
| GREEN         |                      | Architecture   |
+-------+-------+                      +----+-----------+
        |                                   |
        | Approved                          | Approved
        +-----------------+-----------------+
                          |
                          v
                +---------+-----------+
                | CanMerge Criteria   |
                | Met (All Resolved)  |
                +---------+-----------+
                          |
                          v
                +---------+-----------+
                | Trunk Branch (main) |
                | Fast-Forward / Merge|
                +---------------------+
```

---

### 7. Step-by-Step Implementation Guide

Untuk membangun infrastruktur code review yang tangguh, ikuti langkah sistematis berikut:

#### Langkah 1: Terapkan Template Pull Request Terstruktur
Simpan template pada jalur direktori `.github/pull_request_template.md` (untuk GitHub) atau `.gitlab/merge_request_templates/Default.md` (untuk GitLab).

```markdown
### 1. Deskripsi Perubahan
<!-- Jelaskan secara ringkas domain problem dan solusi teknis yang diterapkan -->

### 2. Tipe Perubahan
- [ ] Bug fix (perbaikan non-breaking)
- [ ] New feature (fitur baru non-breaking)
- [ ] Breaking change (perubahan yang merusak backward compatibility)
- [ ] Refactoring (perubahan struktur tanpa mengubah fungsionalitas)

### 3. Tautan Tiket
JIRA / Linear / Issue: #ID-

### 4. Self-Review Checklist (Wajib dicek oleh Penulis)
- [ ] Ukuran diff tidak melebihi 400 LOC (di luar file autogenerated / lock files).
- [ ] Unit test baru mencakup skenario batas (*edge cases*).
- [ ] Tidak ada log debug, API keys, atau credential yang tertinggal.
- [ ] Dokumentasi arsitektur atau OpenAPI specs telah diperbarui sesuai perubahan API.

### 5. Konteks Pengujian Manual (Staging / Verification)
<!-- Tuliskan langkah reproduksi dan curl/payload pengujian -->
```

#### Langkah 2: Standarisasi Sintaks Komentar Menggunakan *Conventional Comments*
Terapkan konvensi komunikasi untuk meminimalkan friksi subjektif. Setiap komentar wajib diawali dengan label berikut:

*   `suggestion:` Merekomendasikan alternatif pendekatan arsitektural. Sifat: Opsional/Dapat dinegosiasikan.
*   `issue:` Menandai cacat konkret, bug keamanan, atau pelanggaran performa. Sifat: **Blokir (Wajib diperbaiki)**.
*   `nitpick:` (atau `nit:`) Catatan minoritas estetika kode yang berada di luar cakupan linter. Sifat: Non-blokir.
*   `question:` Klarifikasi intensi atau konteks logika bisnis. Sifat: Harus dijawab sebelum approval.
*   `thought:` Ide eksploratif untuk iterasi masa depan. Sifat: Non-blokir.

Contoh format komentar:
```
issue (security): Parameter 'userId' diambil langsung dari body request tanpa validasi ownership context (IDOR vulnerability).
suggestion: Gunakan context wrapper `ctx.GetAuthenticatedUser()` untuk memastikan identitas pemanggil.
```

---

### 8. Code Example: Basic / Minimal Concept

Berikut adalah perbandingan konkret antara interaksi code review yang salah (toksik/tidak produktif) dan interaksi code review yang benar (sistemik/berorientasi nilai).

#### Diff Kode yang Ditinjau
```diff
--- a/services/payment_service.go
+++ b/services/payment_service.go
@@ -10,6 +10,7 @@ type PaymentProcessor struct {
 
 func (p *PaymentProcessor) Process(amount float64, currency string) error {
+    time.Sleep(2 * time.Second) // Tunggu transient network timeout
     if amount <= 0 {
         return errors.New("invalid amount")
     }
```

#### Komentar Review yang Buruk (Anti-Pattern)
> Reviewer: *"Kenapa pakai sleep di sini? Ini jelek sekali kodenya. Tolong perbaiki, jangan asal commit."*
*   **Analisis Masalah:** Mengandung nada ad-hominem, tidak menawarkan solusi sistemik, tidak menjelaskan dampak kegagalan, dan menggunakan penilaian subjektif ("jelek").

#### Komentar Review yang Baik (Idiomatik & Berdasarkan Prinsip)
> Reviewer:
> `issue (reliability, performance):` Penggunaan `time.Sleep()` di dalam alur eksekusi sinkronus pembayaran akan memblokir *goroutine worker pool* dan berpotensi menyebabkan thread starvation jika traffic meningkat tajam. Selain itu, cara ini tidak menjamin konektivitas jaringan pulih secara deterministik.
> 
> `suggestion:` Terapkan pola *Retry with Exponential Backoff and Jitter* menggunakan context timeout:
> ```go
> err := retry.Do(
>     func() error { return p.gateway.Charge(ctx, amount, currency) },
>     retry.Attempts(3),
>     retry.DelayType(retry.BackOffDelay),
> )
> ```

---

### 9. Code Example: Production-Ready / Real-World

Implementasi otomatisasi gerbang integrasi (*continuous integration gatekeeper*) menggunakan GitHub Actions untuk memvalidasi batas LOC, mengeksekusi linter, dan memblokir code review jika syarat deterministik tidak terpenuhi.

Simpan pada direktori `.github/workflows/pr-lint-gate.yml`:

```yaml
name: Pull Request Architectural Gate

on:
  pull_request:
    types: [opened, synchronize, reopened, edited]

jobs:
  size-limit-guard:
    name: Validate PR Blast Radius (LOC Limit)
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Source Code
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Calculate Total Diff Excluded Auto-generated Files
        id: pr_size
        run: |
          BASE_REF="origin/${{ github.base_ref }}"
          HEAD_REF="origin/${{ github.head_ref }}"
          
          # Hitung total LOC yang diubah, kecualikan dependensi dan file autogenerated
          CHANGES=$(git diff --numstat $BASE_REF...$HEAD_REF | \
            grep -Ev '(go.sum|package-lock.json|yarn.lock|generated/|.*_mock.go)' | \
            awk '{add += $1; del += $2} END {print add + del}')
          
          # Jika tidak ada perubahan yang terdeteksi selain file yang dikecualikan
          CHANGES=${CHANGES:-0}
          echo "TOTAL_LOC=$CHANGES" >> $GITHUB_ENV
          echo "Total Monitored LOC Changed: $CHANGES"

      - name: Enforce Maximum LOC Threshold
        run: |
          MAX_PERMITTED_LOC=400
          if [ "${{ env.TOTAL_LOC }}" -gt "$MAX_PERMITTED_LOC" ]; then
            echo "::error file=pr_size::PR melanggar batas kognitif code review!"
            echo "Total perubahan: ${{ env.TOTAL_LOC }} LOC (Batas Maksimal: $MAX_PERMITTED_LOC LOC)."
            echo "Pecah PR ini menjadi sub-task yang lebih kecil (Atomic PRs) untuk memastikan review yang berkualitas."
            exit 1
          fi

  lint-and-sast:
    name: Automated Deterministic Audit
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Set up Go
        uses: actions/setup-go@v5
        with:
          go-version: '1.22'
          check-latest: true

      - name: Execute Staticcheck
        uses: dominikh/staticcheck-action@v1.3.1
        with:
          version: "latest"
          install-go: false
          cache-key: "${{ runner.os }}-go-cache"

      - name: Execute Security AST Scanner (Gosec)
        run: |
          go install github.com/securego/gosec/v2/cmd/gosec@latest
          gosec -quiet -exclude-dir=test ./...
```

---

### 10. Edge Cases, Failure Modes, and Anti-Patterns

| Anti-Pattern / Edge Case | Indikator Gejala (Symptoms) | Dampak Teknis / Sistemik | Mitigasi Solutif |
| :--- | :--- | :--- | :--- |
| **The Rubber Stamp (LGTM)** | Review disetujui dalam < 3 menit pada PR > 300 LOC tanpa komentar substansial. | Tingkat cacat di produksi melonjak; unit test kosong tetap lolos ke branch utama. | Pasang bot metriks yang mengecek rasio waktu baca terhadap LOC sebelum mengaktifkan tombol approval. |
| **The Bikeshedding Trap** | Puluhan komentar memperdebatkan nama variabel privat atau posisi kurung kurawal. | *Developer fatigue*, waktu siklus integrasi melambat drastis tanpa peningkatan kualitas logika. | Delegasikan seluruh aturan sintaksis ke *linter* otomatis dengan status *blocker* di CI. |
| **The Megalithic PR (Mega-PR)** | PR berisi 1.500+ LOC mencakup 5 fitur berbeda sekaligus refactoring framework. | Reviewer mengabaikan analisis mendalam; rollback mustahil dilakukan tanpa merusak fitur lain. | Batalkan PR secara tegas (*reject & split*); terapkan *Stacked Pull Requests* atau fitur *feature flags*. |
| **The Ghost Reviewer** | PR terhenti (*stalled*) selama berminggu-minggu menunggu respons dari reviewer yang ditunjuk. | Terjadi *merge conflict hell* yang parah seiring majunya trunk branch; *lead time* meningkat. | Tetapkan *Review SLA* otomatis: jika reviewer tidak merespons dalam 24 jam, oper tiket ke reviewer berikutnya. |
| **The Hostile Gatekeeper** | Komentar bernada sarkastik, merendahkan pembuat PR (*condescending*), atau defensif. | Kerusakan psikologis tim, insinyur menghindari inisiatif refaktorisasi, tingginya *turnover*. | Terapkan *Code of Conduct*, adopsi *Conventional Comments*, dan terapkan rotasi reviewer secara acak. |

---

### 11. Trade-Off Analysis & Decision Matrix

Menentukan modalitas integrasi kode membutuhkan kompromi teknis yang disesuaikan dengan kematangan tim, toleransi latensi, dan kompleksitas domain.

```
       SINKRON (Pair Programming)             ASINKRON (Pull Request Matrix)
┌───────────────────────────────────────┐┌───────────────────────────────────────┐
│ Kelebihan:                            ││ Kelebihan:                            │
│ - Waktu integrasi instan (0 latensi)  ││ - Dokumentasi tertulis permanen       │
│ - Diskusi arsitektur real-time        ││ - Mendukung tim multi-zona waktu      │
│ - Transfer pengetahuan langsung       ││ - Fokus kognitif tanpa interupsi      │
│                                       ││                                       │
│ Kekurangan:                           ││ Kekurangan:                           │
│ - Mengonsumsi 2x engineering hours    ││ - Latensi penyelesaian (PR blocking)  │
│ - Sulit untuk jadwal kerja fleksibel  ││ - Risiko miskomunikasi tekstual       │
└───────────────────────────────────────┘└───────────────────────────────────────┘
```

#### Comparative Evaluation Matrix

| Kriteria Metrik | Pair/Mob Programming | Async Code Review (Standard PR) | Post-Commit Audit (Ship & Show) |
| :--- | :--- | :--- | :--- |
| **Throughput (Velocity)** | Sedang | Rendah – Sedang | Sangat Tinggi |
| **Defect Detection Latency**| Seketika (*Real-time*) | Menengah (Jam - Hari) | Sangat Terlambat (Post-Deploy) |
| **Engineering Cost** | Tinggi (2x *Man-Hours*) | Optimal | Minimal di awal, Mahal saat insiden |
| **Documentation Trail** | Buruk (Ephemeral) | Ekselen (Terekam dalam Git Histori) | Moderat |
| **Konteks Penggunaan** | Sistem Finansial Kritis, Onboarding | Pengembangan Fitur Standard SaaS | Prototyping Startup, Tim Senior Elite |

---

### 12. Performance & Optimization Considerations
Efisiensi proses code review berdampak langsung pada metrik DORA (*DevOps Research and Assessment*), khususnya *Lead Time for Changes*.

#### Mengoptimalkan Throughput Tanpa Mengorbankan Kualitas
1.  **Penerapan Pola Stacked PR:** Daripada membuat satu PR besar berisi 1.000 LOC, buat rantai PR kecil (*stacked PR chain*) berisi masing-masing 150-200 LOC:
    ```
    main <--- [PR-1: Model & Migrations] <--- [PR-2: Business Logic] <--- [PR-3: API Delivery Layer]
    ```
2.  **Karantina File Autogenerated:** Konfigurasikan `.gitattributes` di repositori untuk menyembunyikan file non-logika dari review diff:
    ```gitattributes
    # Otomatis tandai file autogen agar di-collapse oleh GitHub/GitLab
    *.pb.go linguist-generated=true
    swagger.json linguist-generated=true
    pnpm-lock.yaml linguist-generated=true
    ```
3.  **Reviewer Parallelization:** Batasi jumlah reviewer wajib menjadi maksimal 2 orang. Menambah reviewer manusia dari 2 menjadi 5 tidak meningkatkan tingkat deteksi cacat secara linier, namun meningkatkan latensi penyelesaian (*review latency*) secara eksponensial.

---

### 13. Security Considerations & Threat Modeling
Code review manusia adalah garis pertahanan utama dalam menghadapi ancaman internal (*insider threats*) dan manipulasi rantai pasokan perangkat lunak (*supply chain compromises*).

#### Vektor Ancaman Terhadap Proses Review
*   **Trojan Source Attacks (Unicode Steganography):** Penyerang menyisipkan karakter kontrol Unicode bidirectional (seperti `U+202E`) yang mengubah urutan eksekusi logika kode di compiler tanpa mengubah representasi teks yang dibaca oleh reviewer.
    *   *Penanggulangan:* Konfigurasikan git hook atau CI gate untuk menolak komit yang mengandung karakter kontrol Unicode di luar batas ASCII yang sah.
*   **Split-Brain Dependencies:** Penyerang mengubah *hash* integritas dependensi secara tersembunyi di dalam modifikasi besar file `package-lock.json` atau `go.sum`.
    *   *Penanggulangan:* Larang peninjauan manual untuk lockfiles; serahkan verifikasi cryptographic check kepada *CI dependency lock integrity checkers*.
*   **IDOR & Logic-Based Authorization Bypasses:** Static Application Security Testing (SAST) sering kali buta terhadap *Insecure Direct Object References* (IDOR) karena memerlukan pemahaman konteks otorisasi domain.
    *   *Audit Checklist Reviewer:* Wajib memverifikasi bahwa setiap ID entitas yang diterima dari path parameter dicocokkan dengan ID *tenant/user* yang diekstrak dari JWT/Session terotentikasi.

---

### 14. Testing & Verification Strategies

Sebagai peninjau (*reviewer*), evaluasi bukan hanya diarahkan pada kode aplikasi, melainkan juga pada **kualitas pengujian itu sendiri** (*Test Inspection Matrix*).

```
                               TEST QUALITY CHECK
                                       |
    +----------------------------------+----------------------------------+
    |                                                                     |
    v                                                                     v
[STRUKTUR PENGUJIAN]                                              [EFEKTIVITAS ASSERTION]
- Apakah mengikuti pola AAA (Arrange, Act, Assert)?               - Apakah assert memvalidasi invariant bisnis?
- Apakah unit test terisolasi (no real network I/O)?              - Hindari assertion tautologis: `assert.True(true)`
- Apakah edge cases (nil, overflow, empty) tercakup?              - Pastikan tidak ada "Assert Roulette"
```

#### Anti-Pattern Pengujian yang Harus Ditolak saat Review:
1.  **The Mocking Mirage:** Pengembang melakukan *mocking* terhadap hampir seluruh sistem internal sehingga pengetesan hanya menguji implementasi mock itu sendiri, bukan logika riil.
2.  **The Hidden Flaky Test:** Menggunakan `time.Sleep()` di dalam unit test untuk menunggu operasi asinkron alih-alih menggunakan sinkronisasi berbasis *channel signaling* atau *polling primitives*.
3.  **Assert Roulette:** Menjalankan 10 assertion berbeda dalam satu blok pengujian tanpa pesan kesalahan spesifik, sehingga mempersulit diagnosis saat salah satu assertion gagal di pipeline.

---

### 15. Operational & Day-2 Management

Mengelola ekosistem code review dalam skala organisasi memerlukan pemantauan berbasis metrik objektif untuk mendeteksi *developer friction*.

#### Key Performance Indicators (KPIs)
*   **Time to First Review (TTFR):** Durasi waktu sejak PR dibuka hingga komentar substansial pertama diajukan oleh reviewer. Target optimal: **< 4 jam kerja**.
*   **Review Turnaround Time (RTT):** Durasi dari tanggapan pertama hingga keputusan persetujuan (*approved/rejected*). Target optimal: **< 24 jam kerja**.
*   **Review Depth Index:** Rasio jumlah komentar substantif terhadap kLOC. Nilai yang terlalu rendah (< 1 comment / 500 LOC) mengindikasikan *rubber-stamping*; nilai yang terlalu tinggi (> 50 comment / 100 LOC) mengindikasikan masalah arsitektur fundamental atau perdebatan gaya kode.

#### Reviewer SLA Alerts
Otomatisasikan notifikasi bot (misalnya melalui integrasi Slack / Microsoft Teams) yang mengirimkan *alert* peringatan jika sebuah PR belum menerima respons peninjauan dalam interval:
*   **Tier 1 (24 Jam):** Notifikasi ke peninjau yang ditugaskan (*assignee*).
*   **Tier 2 (48 Jam):** Notifikasi eskalasi ke *Engineering Manager* / *Tech Lead*.

---

### 16. Best Practices & Idiomatic Patterns

Berikut adalah aturan emas pelaksanaan code review berstandar industri:

1.  **Small Batches:** Pertahankan ukuran perubahan di bawah 300 LOC. Buat PR kecil, berikan dampak spesifik, dan selesaikan dengan cepat.
2.  **Separate Refactoring from Features:** Jangan pernah menggabungkan *refactoring* format kode struktural dengan implementasi fitur baru dalam satu PR yang sama. Buat dua PR terpisah: pertama PR refactoring, kedua PR fitur.
3.  **Praise in Public, Critique the Code (Not the Author):** Puji solusi elegan secara eksplisit di kolom komentar. Jangan serang pribadi pengembang; fokuskan seluruh kritik pada kode dan perilakunya.
    *   *Buruk:* "Kamu lupa lagi pasang validasi error di sini."
    *   *Baik:* "Fungsi ini belum menangani skenario saat database mengembalikan `sql.ErrNoRows`. Sebaiknya ditambahkan pengecekan eksplisit."
4.  **Adopt Explicit Disclaimers:** Gunakan penanda non-blokir untuk membebaskan pembuat kode dari kewajiban melakukan revisi trivial: `nit: nama variabel 'usr' bisa lebih deskriptif jika diganti 'customerSession', tapi silakan merge tanpa mengubah ini jika mendesak.`

---

### 17. Troubleshooting & Diagnostic Guide

Ketika proses code review dalam tim mengalami disfungsi, gunakan bagan diagnostik berikut untuk menemukan akar masalah sistemik:

```
Masalah: Waktu integrasi kode (Lead Time) sangat lambat (> 5 hari)
│
├── Apakah PR berukuran > 500 LOC?
│   └── YA  --> Masalah: Batch Size terlalu besar. 
│               Solusi: Batasi LOC via CI gate; pecah epics menjadi atomic tasks.
│
├── Apakah CI Automation sering gagal atau lambat (> 20 menit)?
│   └── YA  --> Masalah: Tooling Inefficiency.
│               Solusi: Paralelisasi runner test; optimasi cache container build.
│
├── Apakah reviewer memperdebatkan format estetika koding?
│   └── YA  --> Masalah: Bikeshedding (Lacking Automation).
│               Solusi: Terapkan opinionated linter (e.g., Prettier, Black, Gofmt) 
│                       dan pasang pre-commit hook enforcement.
│
└── Apakah PR sering terabaikan tanpa ada yang mereview?
    └── YA  --> Masalah: Tragedi Kepemilikan Bersama (Diffused Responsibility).
                Solusi: Gunakan GitHub `CODEOWNERS` untuk menunjuk reviewer otomatis
                        yang bertanggung jawab atas modul tertentu.
```

---

### 18. Real-World Case Study

#### Insiden Knight Capital Group (Refleksi Review Kegagalan Konfigurasi & Dead Code)
Pada tahun 2012, Knight Capital Group mengalami kerugian fatal sebesar **$440 juta USD hanya dalam waktu 45 menit** akibat kegagalan integrasi perangkat lunak sistem *SMARS* (algoritma perdagangan ekuitas frekuensi tinggi).

*   **Akar Masalah Teknis:** Pengembang menggunakan kembali (*reused*) flag variabel lama bernama `Power Peg` yang fungsionalitas aslinya telah dinonaktifkan sejak tahun 2003. Rekayasa perangkat lunak tidak menerapkan proses pembersihan *dead code* secara ketat. Tim menyebarkan kode baru ke 8 server secara manual, tetapi teknisi lupa menyalin kode tersebut ke server ke-8. Ketika server menerima pesan pasar, kode usang di server ke-8 membaca flag tersebut dan mengeksekusi pembelian jutaan saham secara serampangan pada harga penawaran tinggi lalu menjualnya pada harga rendah.
*   **Analisis Kegagalan Code Review:**
    1.  Proses peninjauan kode tidak memverifikasi apakah flag fitur baru benar-benar entitas baru atau menggunakan kembali kode mati (*dead code*).
    2.  Tidak adanya penegakan review arsitektur terhadap penghapusan pustaka dan kode yang sudah *deprecated*.
    3.  Kurangnya otomatisasi verifikasi konsistensi *deployment* yang divalidasi silang melalui hash komit Git.
*   **Solusi Modern yang Mencegahnya:**
    *   Penggunaan aturan *Static Analysis* ketat yang melarang penggunaan flag/variabel ambigu.
    *   Penetapan aturan code review wajib (*zero dead-code tolerance policy*): PR baru yang menyentuh fungsionalitas kritis diwajibkan menghapus cabang eksekusi lama yang sudah tidak digunakan.

---

### 19. Hands-On Exercises & Assignments

#### Latihan 1: Melakukan Tinjauan Kode pada PR Rentan (Hands-on Review)
Salin kode Go berikut ke dalam lingkungan editor Anda. Identifikasi minimal **tiga cacat kritis** (termasuk satu celah keamanan dan satu potensi *resource leak*). Tuliskan respons komentar review Anda menggunakan sintaks **Conventional Comments**.

```go
package handler

import (
    "database/sql"
    "fmt"
    "net/http"
)

type UserHandler struct {
    DB *sql.DB
}

func (h *UserHandler) GetUserProfile(w http.ResponseWriter, r *http.Request) {
    userID := r.URL.Query().Get("id")
    
    // PERHATIKAN BLOK DI BAWAH INI:
    query := fmt.Sprintf("SELECT username, email FROM users WHERE id = '%s'", userID)
    rows, err := h.DB.Query(query)
    if err != nil {
        http.Error(w, "Database error", http.StatusInternalServerError)
        return
    }
    
    var username, email string
    for rows.Next() {
        _ = rows.Scan(&username, &email)
    }
    
    w.Header().Set("Content-Type", "application/json")
    w.Write([]byte(fmt.Sprintf(`{"username":"%s","email":"%s"}`, username, email)))
}
```

#### Tugas Praktikum:
1.  Tuliskan komentar penolakan terhadap SQL Injection di baris 17 menggunakan tag `issue (security):`. Berikan solusi *parameterized query*.
2.  Tuliskan komentar perbaikan terhadap kebocoran koneksi database (`rows.Close()`) menggunakan tag `issue (performance):`.
3.  Tuliskan komentar perbaikan penanganan data kosong (*empty record*) jika user ID tidak ditemukan, menggunakan tag `suggestion:`.

---

### 20. Summary, Knowledge Check & Next Steps

#### Rangkuman Modul
*   Code review adalah instrumen rekayasa asinkron untuk mendeteksi cacat fungsional dan menyebarkan pengetahuan arsitektur, bukan ajang pemeriksaan estetika sintaksis manual.
*   Kapasitas kognitif peninjau manusia dibatasi secara fisik: efektivitas optimal tercapai pada inspeksi **< 400 LOC per sesi** dengan kecepatan inspeksi di bawah **500 LOC per jam**.
*   Sistem review modern memisahkan peninjauan menjadi dua: **Deterministik (CI/Linter/SAST)** yang bersifat absolut dan otomatis, serta **Heuristik (Manusia)** yang fokus pada logika bisnis dan arsitektur.
*   Komunikasi teknis yang objektif, transparan, dan tidak ambigu dapat distandarisasi menggunakan taksonomi **Conventional Comments**.

#### Knowledge Check
1.  **Sebuah PR berisi 1.200 baris kode yang mencakup perubahan database schema, refactoring authentication, dan penambahan endpoint pembayaran diajukan ke repositori. Apa tindakan yang paling tepat dari reviewer?**
    *   A. Langsung melakukan review menyeluruh selama 3 jam tanpa henti.
    *   B. Mengabaikan file database dan hanya memeriksa endpoint pembayaran.
    *   C. Menolak PR secara sopan dan meminta pembuat memecahnya menjadi tiga sub-PR yang independen (Stacked PRs).
    *   D. Menyetujui PR dengan komentar "LGTM" karena kode mendesak untuk rilis produksi.
    *   *Jawaban yang benar: C.*

2.  **Manakah dari skenario peninjauan berikut yang merupakan implementasi dari anti-pattern "Bikeshedding"?**
    *   A. Mendiskusikan potensi terjadinya *deadlock* pada transaksi database konkruen.
    *   B. Berdebat sepanjang 25 komentar mengenai preferensi penggunaan tanda kutip satu (`'`) vs tanda kutip dua (`"`) yang tidak diatur di linter.
    *   C. Memblokir PR karena tidak terdapat validasi otorisasi berbasis hak akses peran (*RBAC*).
    *   D. Meminta penambahan test suite untuk menguji batas *integer overflow*.
    *   *Jawaban yang benar: B.*

3.  **Mengapa verifikasi formatting (seperti indentasi, spasi, penamaan file) harus dikeluarkan dari lingkup peninjau manusia?**
    *   A. Karena format kode sama sekali tidak penting dalam rekayasa perangkat lunak.
    *   B. Karena manusia cenderung bias terhadap gaya pemrograman tertentu.
    *   C. Karena tugas deterministik dapat dieksekusi secara instan dan tanpa emosi oleh *linter automated tooling*, sehingga menghemat energi kognitif manusia untuk evaluasi logika.
    *   D. Karena format kode hanya ditentukan oleh framework yang digunakan.
    *   *Jawaban yang benar: C.*

#### Next Steps
Lanjutkan ke **Bab 01 Module 02: Otomasi Gerbang Kualitas (Linters, SAST, dan CI Checkpoints)**, di mana kita akan mempelajari cara merancang dan mengonfigurasi *linter* yang agresif, mengintegrasikan Static Application Security Testing (Semgrep/Gosec), serta membangun *git-hooks* berbasis Husky untuk memblokir kode cacat sebelum meninggalkan mesin lokal pengembang.