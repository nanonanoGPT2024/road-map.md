## SEKSI 01 — IDENTITAS MODUL

*   **Kode Modul:** CR-ARCH-0301
*   **Judul Modul:** Arsitektur Pull Request & Git Workflows: Trunk-Based Development, Stacked Diffs/PRs, Feature Flags, Anatomy of Exemplary PR, dan Atomic Commits
*   **Kategori:** 06-Architecture-and-System-Design
*   **Track:** Code Review & Engineering Velocity
*   **Tingkat Kesulitan:** Advanced / Staff Engineer Track
*   **Prasyarat:** Pemahaman mendalam tentang Git internals (DAG, SHA-1/SHA-256 objects, refs), Continuous Integration/Continuous Deployment (CI/CD) pipelines, serta pengalaman me-review pull request skala enterprise.
*   **Estimasi Waktu Penyelesaian:** 180 Menit

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1.  **Mendiagnosis** kegagalan throughput review yang disebabkan oleh *long-lived feature branches* dan *mega-diffs*.
2.  **Merancang dan Mengimplementasikan** strategi *Trunk-Based Development* (TBD) dengan frekuensi merge tinggi menggunakan *Feature Flags* untuk decoupling *deployment* dari *release*.
3.  **Mengoperasikan** workflow *Stacked PRs / Stacked Diffs* menggunakan tooling modern (seperti Graphite atau CLI `git stack`) untuk memecah perubahan arsitektur masif menjadi unit review kecil independen yang dapat diverifikasi secara paralel.
4.  **Menyusun** *Anatomy of an Exemplary Pull Request* yang meminimalkan *cognitive load* reviewer, mempercepat *Time to First Review* (TTFR), dan menjamin *bisectability*.
5.  **Menegakkan** disiplin *Atomic Commits* berbasis prinsip single logical change dengan pesan commit terstruktur yang tahan uji forensik audit.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                           +-------------------------------------+
                           |    ENGINEERING REVIEW VELOCITY      |
                           +-------------------------------------+
                                              |
        +-------------------------------------+-------------------------------------+
        |                                                                           |
        v                                                                           v
+--------------------------------+                               +--------------------------------+
|    VERSION CONTROL WORKFLOW    |                               |      PR QUALITY ARTIFACTS      |
+--------------------------------+                               +--------------------------------+
        |                                                                           |
        +---> Trunk-Based Development (TBD)                                         +---> Anatomy of Exemplary PR
        |     (Short-lived branches, <= 24 jam)                                     |     (Context, Invariants, Rollback)
        |                                                                           |
        +---> Stacked Diffs / Stacked PRs                                           +---> Atomic Commits
        |     (DAG of micro-PRs, graphite/sprig)                                          (Single logical change, bisectable)
        |                                                                           |
        +---> Feature Flags / Toggles                                               +---> Context Minimization
              (Decouple deployment from release)                                          (PR size <= 250 LOC)
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Penyebab utama stagnasi dalam *software delivery* bukanlah waktu penulisan kode, melainkan **Review Latency** dan **Integration Pain**. 

Dalam survei DORA (*DevOps Research and Assessment*), metrik *Lead Time for Changes* secara langsung berkorelasi dengan ukuran unit kerja yang dikirimkan. Paradigma usang seperti GitFlow mengarahkan tim menuju *long-lived feature branches* yang hidup selama berminggu-minggu. Konsekuensinya:
1.  **Merge Hell:** Divergensi branch yang ekstrem menuntut resolusi konflik manual berskala besar, yang kerap menghapus perbaikan bug rekan setim tanpa disengaja.
2.  **Rubber-Stamp Reviews:** Pull request dengan volume >800 LOC (*Lines of Code*) memicu *review fatigue*. Reviewer cenderung hanya melihat sekilas lalu menyetujui ("LGTM!"), melewatkan cacat logika kritis, kerentanan keamanan, atau regresi performa.
3.  **Deploy Blockers:** Fitur masif yang gagal di staging memblokir fitur-fitur lain yang sudah siap rilis namun terjebak dalam cabang rilis yang sama.

Untuk mencapai kapabilitas *Continuous Deployment* kelas dunia (seperti yang dipraktikkan di Meta, Google, dan Uber), arsitektur pull request harus bertransformasi dari sekadar "alat inspeksi kode" menjadi **kontrak atomik, inkremental, dan self-contained**. Memahami Stacked Diffs, Trunk-Based Development, dan Feature Flags adalah fondasi wajib arsitek sistem modern.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Trunk-Based Development (TBD)
Trunk-Based Development adalah strategi percabangan di mana seluruh engineer menggabungkan perubahan kecil dan sering (*frequent, micro-integrations*) langsung ke satu branch utama (biasanya dinamai `main` atau `trunk`). Masa hidup suatu branch fitur umumnya di bawah 24 jam. TBD mengeliminasi branch berumur panjang seperti `develop`, `release/*`, atau `feature/*` yang terisolasi berbulan-bulan.

### 2. Stacked Diffs / Stacked PRs
Stacked Diffs adalah metodologi rekayasa perangkat lunak di mana satu fitur besar dipecah menjadi rantai *pull requests* kecil yang berurutan dan saling bergantung (membentuk Directed Acyclic Graph/DAG). PR lapis kedua dibangun di atas cabang PR lapis pertama, PR lapis ketiga di atas lapis kedua, dan seterusnya. Reviewer dapat meninjau setiap layer (misal: 100 LOC) secara terisolasi tanpa menunggu seluruh fitur selesai, sementara tooling modern menangani operasi `rebase` kaskade secara otomatis.

### 3. Feature Flags (Feature Toggles)
Mekanisme arsitektural untuk membungkus jalur eksekusi kode baru di balik conditional statement yang dinamis. Tujuannya adalah mengintegrasikan kode yang belum selesai atau berisiko tinggi ke `main` dan mendeploy-nya ke produksi tanpa mengaktifkannya bagi pengguna akhir, memisahkan secara absolut antara **Deploy** (pergerakan biner ke infrastruktur) dan **Release** (eksposur fungsionalitas ke pengguna).

### 4. Anatomy of an Exemplary PR
Struktur standardisasi PR yang dirancang untuk meminimalkan beban kognitif reviewer. Elemen vitalnya mencakup:
*   *Motivation/Problem Statement*
*   *Architectural Decisions & Trade-offs*
*   *Proof of Correctness* (Unit, integration test, logs, benchmark, screencast)
*   *Blast Radius & Failure Scenarios*
*   *Rollback Runbook*

### 5. Atomic Commits
Komit yang merepresentasikan satu unit logika terkecil yang lengkap dan tidak dapat dipecah lagi. Aturan absolut atomic commit: **setiap commit dalam sejarah git harus berada dalam kondisi yang lulus kompilasi dan lulus seluruh automated test suites**. Ini menjamin perintah `git bisect` dapat berjalan deterministik untuk mendeteksi akar masalah bug regresi.

---

## SEKSI 06 — BAGAIMANA BEKERJA (HOW)

### Alur Kerja Stacked Diffs Berbasis Git

Di platform konvensional (GitHub bawaan), membuat branch bertingkat sering kali menyiksa karena jika branch basis diperbarui pasca-review, semua branch anak harus di-rebase secara manual. Tool seperti `graphite` atau `sprig` mengotomasi sinkronisasi pohon referensi (ref).

```
[Stack Visualizer]
(downstream) PR 3: feat(api): expose /checkout endpoint     --> depends on PR 2
                 ^
                 |
             PR 2: feat(core): implement checkout logic     --> depends on PR 1
                 ^
                 |
(upstream)   PR 1: schema: add checkout_transactions table  --> merges into main
```

1.  **Fase Dekomposisi:** Arsitek/Engineer membedah fungsionalitas menjadi layer independen:
    *   *Layer 1 (Data):* Migrasi skema basis data.
    *   *Layer 2 (Domain/Business Logic):* Implementasi model, validasi, dan unit test.
    *   *Layer 3 (Transport/API):* Serializer, HTTP handler/gRPC endpoint.
    *   *Layer 4 (Telemetry & Feature Flag):* Metrik Prometheus, OpenTelemetry traces, toggle initialization.
2.  **Pembuatan Stack:**
    *   Engineer mencabangkan `pr-1` dari `main`. Commit & submit.
    *   Engineer langsung mencabangkan `pr-2` dari `pr-1` tanpa menunggu `pr-1` di-review atau di-merge.
    *   Engineer mencabangkan `pr-3` dari `pr-2`.
3.  **Proses Review Paralel:** Reviewer A meninjau PR 1 (Data), Reviewer B meninjau PR 2 (Logic). Karena masing-masing diff < 150 LOC, review selesai dalam hitungan menit.
4.  **Rebasing Kaskade:** Ketika PR 1 mendapat saran perubahan (misal: penambahan index skema), author merevisi PR 1 (`git commit --amend`), lalu CLI tooling secara otomatis mengeksekusi:
    ```bash
    git checkout pr-2 && git rebase pr-1
    git checkout pr-3 && git rebase pr-2
    ```
5.  **Merge Strategi:** Dapat menggunakan *Merge Queue* berbasis trunk. PR 1 masuk ke `main`, PR 2 secara otomatis di-retarget ke `main`, divalidasi CI, dan di-merge secara berurutan.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### Komparasi Pola Integrasi: GitFlow vs Trunk-Based + Stacked PRs

```
========================================================================================
POLA 1: GITFLOW (LONG-LIVED FEATURE BRANCHES) - HIGH RISK, HIGH FRICTION
========================================================================================

main     ========================================================================*======>
                    \                                                           /
develop  ------------*---------------------------------------------------------*-------->
                      \                                                       /
feature                *---[2 weeks work: 45 files, 2500 lines diff]---------*
                            (Reviewer butuh 3 hari, merge conflict masif, CI lama)

========================================================================================
POLA 2: TRUNK-BASED DEVELOPMENT DENGAN STACKED DIFFS & FEATURE FLAGS
========================================================================================

main     ---*--------------*--------------*--------------*----------------------------->
             \            / \            / \            /
stack-1       *--[PR 1]--*   \          /   \          /
               (DB Schema)    \        /     \        /
                               \      /       \      /
stack-2                         *-[PR 2]-*     \    /
                              (Core Logic)      \  /
                                                 \/
stack-3                                           *--[PR 3]--*
                                                  (API + Flag)

           | <----------- Loop Eksekusi Tiap PR: 2 s/d 4 Jam ------------> |
```

### Decoupling Deploy dari Release via Feature Flag

```
+---------------------------------------------------------------------------------------+
| TRUNK CODEBASE                                                                        |
|                                                                                       |
|   func ProcessPayment(req PaymentRequest) Response {                                  |
|       if featureFlags.IsEnabled("NEW_PAYMENT_GATEWAY_V2", req.UserID) {               |
|           return v2Engine.Execute(req)  // KODE BARU (Sudah di-deploy, tapi gated)    |
|       }                                                                               |
|       return v1Engine.Execute(req)      // KODE LAMA (Production default)             |
|   }                                                                                   |
+---------------------------------------------------------------------------------------+
         |                                                       ^
         v                                                       |
+-----------------------------------+        +------------------------------------------+
| 1. Deploy to Production           |        | 2. Toggle Flag via Control Plane         |
| (Karyawan internal / Canary 1%)   | -----> | (Bypass redeploy, 0-downtime blast audit)|
+-----------------------------------+        +------------------------------------------+
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

### Teknik Atomic Commit: Memecah Perubahan Monolitik Menggunakan Git Patch

Skenario: Anda memodifikasi file konfigurasi database dan menambahkan repository baru dalam satu sesi kerja. Jangan satukan keduanya ke dalam satu commit!

```bash
# Periksa status working tree
$ git status
On branch feat/user-storage
Changes not staged for commit:
	modified:   config/database.go
	new file:   internal/repository/user.go

# 1. Commit perubahan konfigurasi secara mandiri (Commit 1)
$ git add config/database.go
$ git commit -m "refactor(config): add connection pool limits for postgres"

# 2. Commit implementasi repository (Commit 2)
$ git add internal/repository/user.go
$ git commit -m "feat(repository): implement postgres user retrieval"

# Memverifikasi integritas riwayat commit (linear, atomic, bisectable)
$ git log --oneline -n 2
a3f12c4 feat(repository): implement postgres user retrieval
8b9e011 refactor(config): add connection pool limits for postgres
```

Jika `internal/repository/user.go` memiliki bug, kita dapat me-revert `a3f12c4` tanpa membatalkan tuning connection pool di `8b9e011`.

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

### Skenario End-to-End: Stacked Diffs Migrasi Skema, Domain Service, dan Feature-Flagged Controller

Berikut adalah perancangan 3 PR bertingkat (*stacked*) untuk implementasi kalkulasi pajak dinamis.

#### Layer 1: PR #101 - Database Schema & Entity Definition
*Target: `main`*

```sql
-- migrations/20231025120000_add_tax_rules.sql
CREATE TABLE tax_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    country_code VARCHAR(2) NOT NULL,
    rate_basis_points INT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_tax_rules_country ON tax_rules(country_code);
```

#### Layer 2: PR #102 - Domain Logic & Repository Layer
*Target: Branch `PR-101` (atau `main` jika PR #101 sudah di-merge)*

```go
// internal/tax/calculator.go
package tax

import (
	"context"
	"fmt"
)

type Repository interface {
	GetRateByCountry(ctx context.Context, countryCode string) (int, error)
}

type Calculator struct {
	repo Repository
}

func NewCalculator(repo Repository) *Calculator {
	return &Calculator{repo: repo}
}

func (c *Calculator) CalculateTax(ctx context.Context, amountCents int64, countryCode string) (int64, error) {
	if amountCents < 0 {
		return 0, fmt.Errorf("invalid amount: %d", amountCents)
	}
	basisPoints, err := c.repo.GetRateByCountry(ctx, countryCode)
	if err != nil {
		return 0, fmt.Errorf("tax evaluation failed: %w", err)
	}
	return (amountCents * int64(basisPoints)) / 10000, nil
}
```

#### Layer 3: PR #103 - API Handler dengan Feature Flag Protection
*Target: Branch `PR-102`*

```go
// internal/handler/checkout.go
package handler

import (
	"net/http"
	"github.com/gin-gonic/gin"
	"myproject/internal/tax"
	"myproject/pkg/flags"
)

type CheckoutHandler struct {
	taxCalc  *tax.Calculator
	flagUser flags.Client
}

func (h *CheckoutHandler) HandleCheckout(c *gin.Context) {
	userID := c.GetString("user_id")
	var req struct {
		Amount  int64  `json:"amount"`
		Country string `json:"country"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	var taxAmount int64 = 0
	var err error

	// Gating logic: Hanya aktifkan engine pajak dinamis jika flag aktif untuk entitas ini
	if h.flagUser.Evaluate(c.Request.Context(), "ENABLE_DYNAMIC_TAX_V2", userID) {
		taxAmount, err = h.taxCalc.CalculateTax(c.Request.Context(), req.Amount, req.Country)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Tax calculation error"})
			return
		}
	}

	c.JSON(http.StatusOK, gin.H{
		"base_amount": req.Amount,
		"tax_amount":  taxAmount,
		"total":       req.Amount + taxAmount,
	})
}
```

#### Templat PR Eksemplar untuk PR #103:

```markdown
### What changes does this PR introduce?
Mengekspos endpoint kalkulasi checkout dengan kalkulasi pajak dinamis baru di balik feature flag `ENABLE_DYNAMIC_TAX_V2`. 
Tergantung pada PR #102 (Domain Logic).

### Architectural Invariants & Safety
- **Blast Radius:** Terisolasi hanya untuk user yang terdaftar dalam targeted segment feature flag. Default fallback: `$0 tax` (perilaku legacy).
- **Performance:** P99 latency overhead < 3ms (karena layer in-memory cache pada flag evaluation client).
- **Idempotency:** Endpoint bersangkutan sepenuhnya murni read-only pada domain tax.

### Verification Strategy
- [x] Unit tests cover: Zero amount, invalid country, flag off vs flag on (`go test -race ./...`)
- [x] Integration test dengan container database tax rules.
- [x] E2E staging smoke test verified. Link trace Datadog: `https://datadog.internal/apm/trace/8971239`

### Rollback Runbook
Jika metrik error 5xx naik > 0.05%:
1. Matikan feature flag via dashboard: `https://flags.internal/toggles/ENABLE_DYNAMIC_TAX_V2` (Instant: propagasi < 5 detik).
2. Tidak butuh rollback biner/deployment git revert.
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Dimensi | GitFlow / Feature Branch Panjang | Trunk-Based + Stacked PRs |
| :--- | :--- | :--- |
| **Review Velocity** | Sangat Rendah (PR besar, butuh hari/minggu untuk ditinjau). | Sangat Tinggi (PR kecil < 200 LOC, review selesai < 2 jam). |
| **Merge Overhead** | Eksponensial seiring waktu (*Merge Hell* di akhir fase rilis). | Terdistribusi konstan (Rebase kecil terjadi setiap saat). |
| **Cognitive Load** | Tinggi: Reviewer harus memahami 10+ layer sekaligus. | Rendah: Reviewer fokus pada satu domain abstraksi per PR. |
| **Tooling Dependency** | Minimal (cukup CLI Git standar dan GitHub/GitLab). | Tinggi (membutuhkan tooling stacked CLI seperti Graphite, Sprig, dan Merge Queues). |
| **Blast Radius** | Tinggi: Sekali merge, seluruh kegagalan masuk ke production. | Sangat Rendah: Dibatasi oleh *Feature Flags* per level pengguna. |
| **Technical Debt** | Risiko integrasi tersembunyi hingga masa rilis. | Hutang Feature Flag: Jika flag usang tidak dihapus, terjadi *flag rot*. |

---

## SEKSI 11 — BEST PRACTICES

1.  **Batasi Ukuran Diff (The 200-LOC Rule):** Buat batas toleransi review: PR maksimal berisi 200-400 baris perubahan di luar file autogenerated (*lockfiles*, schemas, protobufs).
2.  **Squash and Rebase / Rebase-Merge Policy:** Hindari *merge commits* berantakan di branch `main`. Gunakan *Squash and Merge* untuk PR individual non-stack, atau *Rebase and Merge* untuk rangkaian Stacked PR guna menjaga linearitas DAG.
3.  **Terapkan Short-Lived Feature Flags:** Berikan siklus hidup terikat waktu pada setiap feature flag. Beri label penanda tiket pembersihan (*cleanup ticket*) sejak hari pertama flag dibuat:
    ```go
    // TODO(DEPRECATE: 2024-Q1, TICKET: CORE-10492): Hapus toggle dan fallback kode legacy
    ```
4.  **Enforce Strict CI pada Tiap Node di Stack:** Setiap commit atau layer dalam stack harus lulus linter dan tes secara mandiri tanpa bergantung pada commit masa depan di stack tersebut.
5.  **Gunakan Merge Queue Otomatis:** Pasang merge queue (seperti GitHub Merge Queue, Bors, atau Graphite Merge Queue) untuk mencegah *semantic merge conflicts* (di mana CI hijau di branch, namun rusak saat digabung serentak dengan PR lain ke `main`).

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. The "Broken Intermediate" Commit
*Anti-pattern:* Commit 1 menambahkan pemanggilan fungsi baru, namun fungsi tersebut baru dideklarasikan pada Commit 2.
*Dampak:* Melanggar kaidah atomik. Eksekusi `git bisect` yang mendarat di Commit 1 akan menghasilkan *build failure*, merusak proses investigasi insiden otomatis.
*Solusi:* Susun urutan: Komit abstraksi/deklarasi interface dan fungsi terlebih dahulu, baru konsumsi fungsi tersebut di komit selanjutnya.

### 2. Zombie Feature Flags
*Anti-pattern:* Membiarkan kondisi `if (flag) { ... } else { ... }` mengendap di basis kode selama bertahun-tahun setelah fitur 100% dirilis ke seluruh populasi user.
*Dampak:* Kompleksitas siklomatis (*cyclomatic complexity*) meroket, testing matrix berlipat ganda, dan beban kognitif engineer melonjak.
*Solusi:* Wajibkan pembuatan PR penghapusan flag tepat setelah fase rilis mencapai GA (*General Availability*).

### 3. Review Fatigue Melalui "Stacked Spam"
*Anti-pattern:* Memecah 1000 LOC PR menjadi sepuluh PR berukuran 100 LOC yang dikirim serentak dalam waktu 5 detik kepada reviewer yang sama tanpa konteks payung (*umbrella issue*).
*Dampak:* Reviewer kehilangan gambaran arsitektur besar (*can't see the forest for the trees*).
*Solusi:* Sertakan ringkasan RFC/Architecture Decision Record (ADR) dan tautkan seluruh child PR ke satu Root Epic PR sebagai navigasi utama.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan: Membangun dan Memanipulasi Stacked Commits Menggunakan Native Git

#### Tujuan:
Membuat riwayat git linear dengan 2 PR bertingkat, lalu mengubah commit terdahulu (*downstream*) dan me-rebase commit sesudahnya (*upstream*) tanpa konflik.

#### Instruksi:

1. Inisialisasi repositori lokal:
   ```bash
   mkdir stacked-lab && cd stacked-lab
   git init -b main
   echo "Initial application setup" > app.txt
   git add app.txt && git commit -m "chore: initial commit"
   ```

2. Buat layer pertama (Model):
   ```bash
   git checkout -b stack/1-model
   echo "type User struct { ID string }" >> app.txt
   git add app.txt
   git commit -m "feat(model): define user entity"
   ```

3. Buat layer kedua langsung dari layer pertama (Service):
   ```bash
   git checkout -b stack/2-service
   echo "func GetUser() {}" >> app.txt
   git add app.txt
   git commit -m "feat(service): implement user service"
   ```

4. Simulasikan *Review Feedback* pada `stack/1-model`: Reviewer meminta penambahan field `Email` pada User model.
   ```bash
   git checkout stack/1-model
   # Modifikasi model
   cat <<EOF > app.txt
   Initial application setup
   type User struct { 
       ID string 
       Email string 
   }
   EOF
   git add app.txt
   git commit --amend -m "feat(model): define user entity with email"
   ```

5. Rebase layer kedua (`stack/2-service`) di atas layer pertama yang baru saja di-amend:
   ```bash
   git checkout stack/2-service
   git rebase stack/1-model
   ```

6. Verifikasi log riwayat untuk memastikan seluruh perubahan tersinkronisasi rapi dan linear:
   ```bash
   git log --graph --oneline
   ```

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

### Pertanyaan Pilihan Ganda

1. **Apa perbedaan mendasar antara "Deployment" dan "Release" dalam paradigma Trunk-Based Development tingkat lanjut?**
   * A. Deployment dilakukan oleh engineer, Release dilakukan oleh QA.
   * B. Deployment adalah proses kompilasi kode, Release adalah proses commit ke branch staging.
   * C. Deployment adalah pengiriman fisik biner kode ke server produksi, sedangkan Release adalah aktivasi fungsi bagi pengguna akhir (misal: via feature flag).
   * D. Deployment membutuhkan persetujuan manajerial, Release berjalan secara otomatis lewat cron job.

2. **Mengapa *atomic commit* sangat penting dalam rekayasa keandalan sistem (*reliability engineering*)?**
   * A. Agar repositori git menggunakan penyimpanan disk sekecil mungkin.
   * B. Agar utilitas otomatisasi seperti `git bisect` dapat mengisolasi commit penyebab regresi tanpa terhenti oleh commit yang rusak/gagal kompilasi.
   * C. Agar proses code review tidak lagi membutuhkan linter dan unit testing.
   * D. Karena platform GitHub melarang commit yang memiliki lebih dari 1 file perubahan.

3. **Seorang engineer mengirimkan PR sebesar 1.400 LOC yang memodifikasi skema DB, logika kalkulasi, controller, dan antarmuka UI. Tindakan apa yang paling tepat diambil oleh Staff Engineer yang menjadi reviewer?**
   * A. Menyetujui PR tersebut segera untuk menghindari blocking pengiriman fitur.
   * B. Menolak meninjau secara mendalam dan meminta author memecahnya menjadi struktur Stacked PRs (Schema -> Domain -> API -> UI) yang dilindungi Feature Flag.
   * C. Menugaskan lima junior engineer untuk mereview PR tersebut secara terpisah.
   * D. Menginstruksikan author untuk menghapus unit tests agar LOC diff berkurang hingga di bawah 500.

4. **Kapan kondisi sebuah *Feature Flag* bertransformasi menjadi *Technical Debt* berbahaya?**
   * A. Ketika feature flag diuji di lokal staging environment.
   * B. Ketika feature flag diimplementasikan menggunakan kontrol berbasis database alih-alih file JSON statis.
   * C. Ketika flag tetap dibiarkan aktif di kode produksi lama setelah fitur mencapai adopsi 100%, membengkakkan jalur percabangan logika (*flag rot*).
   * D. Ketika flag digunakan untuk membatasi traffic ke pengguna internal (*dogfooding*).

5. **Dalam konsep Stacked Diffs, jika Author meng-amend Commit #1 di bagian bawah stack, apa yang harus dilakukan terhadap Branch PR #2 dan Branch PR #3 di atasnya?**
   * A. Menghapus PR #2 dan PR #3 lalu membuatnya dari awal.
   * B. Melakukan `rebase` berurutan (cascade rebase) dari Branch #1 ke Branch #2, lalu Branch #2 ke Branch #3.
   * C. Melakukan merge commit dari `main` langsung ke PR #3 tanpa menyentuh PR #2.
   * D. Tidak perlu melakukan apa pun karena Git secara otomatis menyatukan memory ref tanpa rebase.

### Kunci Jawaban
1. **C** — Feature flags memungkinkan decoupling sempurna antara deployment biner dan aktivasi fungsionalitas (release).
2. **B** — Setiap atomic commit harus lulus tes dan build secara mandiri agar proses `git bisect` berfungsi deterministik saat insiden terjadi.
3. **B** — PR monolitik memicu resiko kelalaian deteksi bug dan sulit diverifikasi. Memecahnya menjadi Stacked Diffs adalah solusi struktural.
4. **C** — *Flag rot* terjadi ketika kode conditional flag yang sudah usang tidak dibersihkan, memicu kerumitan logika yang tidak perlu.
5. **B** — Mengubah node upstream/bawah pada DAG Git menuntut semua child node di-rebase secara kaskade agar tidak terjadi divergensi pohon referensi.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

*   **Buku:** Forsgren, N., Humble, J., & Kim, G. (2018). *Accelerate: The Science of Lean Software and DevOps*. IT Revolution Press.
*   **Buku:** Winters, T., Manshreck, T., & Wright, H. (2020). *Software Engineering at Google: Lessons Learned from Programming Over Time*. O'Reilly Media.
*   **Dokumentasi Resmi:** *Trunk Based Development Handbook* — [https://trunkbaseddevelopment.com/](https://trunkbaseddevelopment.com/)
*   **Metodologi Stacked Diffs:** *Stacked Diffs Versus Pull Requests* (Graphite Guides) — [https://graphite.dev/guides/stacked-diffs](https://graphite.dev/guides/stacked-diffs)
*   **Engineering Blog:** Martin Fowler. (2017). *Feature Toggles (aka Feature Flags)* — [https://martinfowler.com/articles/feature-toggles.html](https://martinfowler.com/articles/feature-toggles.html)

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1.  **Trunk-Based Development** adalah landasan *engineering velocity* kelas dunia, mereduksi cabang berumur panjang dan menggantinya dengan integrasi harian berskala mikro.
2.  **Stacked Diffs/PRs** memecahkan masalah integrasi perubahan arsitektur masif dengan menyusun rantai PR kecil yang saling terisolasi per layer abstraksi, memungkinkan review paralel berkecepatan tinggi.
3.  **Feature Flags** memisahkan rilis teknis (*Deployment*) dari rilis bisnis (*Release*), memangkas *blast radius* kegagalan dan memungkinkan *instant rollback* tanpa menyentuh deployment pipeline.
4.  **Anatomy of an Exemplary PR** berfokus pada empati terhadap reviewer: diff ramping (< 250 LOC), konteks arsitektural yang jelas, bukti pengujian komprehensif, dan runbook mitigasi bencana.
5.  **Atomic Commits** menjamin riwayat git bersifat fungsional pada setiap titik perhentian kompilasi, menjaga kemampuan investigasi forensik (*bisectability*) dalam sistem produksi yang kompleks.

---

## SEKSI 17 — GLOSARIUM

*   **Atomic Commit:** Perubahan kode terkecil yang merepresentasikan satu unit logika tunggal, mandiri, dan menjaga test suite tetap lulus.
*   **Bisectability:** Karakteristik repositori git di mana perintah `git bisect` dapat dijalankan pada setiap titik riwayat untuk menemukan commit pemecah sistem tanpa terganggu kegagalan kompilasi yang tidak relevan.
*   **Blast Radius:** Cakupan area sistem atau populasi pengguna yang terdampak secara negatif apabila suatu komponen atau kode mengalami malfungsi.
*   **Cascade Rebase:** Operasi rebase berantai yang diterapkan ke seluruh branch anak dalam stack diff ketika branch induk mengalami modifikasi atau *amend*.
*   **Feature Flag (Feature Toggle):** Variabel kondisional yang mengontrol aliran eksekusi fitur secara dinamis pada saat *runtime* tanpa perlu melakukan *re-deployment* biner.
*   **Merge Queue:** Sistem orkestrasi otomatis yang mengantrekan PR yang disetujui, menguji integrasinya secara serial dengan `main`, lalu melakukan merge untuk mencegah *semantic conflicts*.
*   **Review Latency:** Waktu total yang dihabiskan sejak sebuah pull request dibuka hingga mendapatkan review pertama dan persetujuan final.
*   **Stacked PRs:** Kumpulan pull request kecil yang disusun berlapis membentuk hierarki dependensi langsung untuk memecah fitur besar.
*   **Trunk-Based Development (TBD):** Pola kontrol sumber di mana semua pengembang menggabungkan kode mereka ke satu branch utama secara reguler (minimal sekali sehari).

---

## SEKSI 18 — CATATAN INSTRUKTUR

### Poin Penekanan Materi:
*   Banyak engineer menolak TBD karena takut kode yang "setengah jadi" merusak branch `main`. Tekankan bahwa kuncinya adalah **kombinasi Feature Flags dan Branch by Abstraction**. Kode yang belum selesai bisa masuk ke `main` setiap jam selama ia terisolasi dari jalur eksekusi aktif.
*   Saat menjelaskan *Stacked PRs*, peserta sering bingung mengenai kapan harus melakukan *merge*. Jelaskan bahwa PR di layer bawah bisa di-merge lebih dulu ke `main` (asalkan di belakang feature flag), memendekkan stack secara bertahap.

### Jebakan Umum Peserta:
*   Peserta sering menyamakan *Atomic Commit* dengan *"satu commit per file"*. Tegaskan: atomisitas diukur dari **unit logika fungsional**, bukan jumlah file. Jika satu refactoring membutuhkan perubahan 10 file interface, itu tetap **satu** atomic commit.
*   Peserta sering lupa mengalokasikan waktu untuk *flag cleanup*. Tekankan aturan: setiap PR pembuatan feature flag harus otomatis menghasilkan tiket dependensi di issue tracker untuk pembersihannya.

---

## SEKSI 19 — CHANGELOG & VERSI

*   **Versi 1.0.0 (Oktober 2023):**
    *   Rilis kurikulum awal.
    *   Standarisasi materi Trunk-Based Development, Stacked Diffs, Feature Flags, dan Atomic Commits.
    *   Penambahan skenario implementasi Go dan diagram alur visual Stacked PR.

---

## SEKSI 20 — NAVIGASI KURIKULUM

*   **Modul Sebelumnya:** `CR-FOUND-0203: Metrik Code Review: TTFR, Review Size, dan Defect Density`
*   **Modul Berikutnya:** `CR-ARCH-0302: Branch by Abstraction Pattern & Large Scale Refactoring Review`
*   **Daftar Modul Kategori:** `06-Architecture-and-System-Design`