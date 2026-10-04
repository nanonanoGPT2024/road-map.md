# Kurikulum Rekayasa Perangkat Lunak Enterprise
## Kategori: 06-Architecture-and-System-Design
### BAB-01: Fondasi dan Arsitektur
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi — Code Review

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Merancang dan Mengimplementasikan** arsitektur *Automated Code Review Pipeline* berbasis *Architectural Fitness Functions* untuk mendeteksi pelanggaran batas domain (*bounded context*), kebocoran abstraksi, dan degradasi performa sebelum fase merge.
- **Menganalisis dan Mengevaluasi** perubahan sistem terdistribusi (skema basis data, kontrak API, konkurensi, dan transaksi) pada pull request berskala besar dengan pendekatan *Risk-Based PR Triage*.
- **Membangun** *Custom Static Analysis Linter* dan integrasi *Rule-based AST (Abstract Syntax Tree)* guna menegakkan *Architectural Decision Records* (ADR) secara otomatis.
- **Mengeliminasi** *anti-patterns* peninjauan kode (*rubber-stamping*, *bike-shedding*, kelelahan kognitif) melalui formalisasi protokol *Peer Review Service Level Objectives* (PR-SLO) dan desentralisasi *Code Ownership*.

---

### 2. Prerequisite
Sebelum mempelajari modul ini, peserta diwajibkan memahami:
- **Git Internals**: Struktur DAG (*Directed Acyclic Graph*), reflog, commit tree traversal, serta manipulasi *diff plumbing* (`git diff-tree`, `git merge-base`).
- **Distributed Systems Fundamentals**: *Eventual consistency*, *network partitions*, transaksi terdistribusi (Saga pattern), serta *forward/backward compatibility* pada serialisasi payload (Protobuf, JSON schema).
- **CI/CD Pipeline Architecture**: Webhooks, ephemeral runners, isolated testing environments, dan branch protection policies (GitHub Rulesets/GitLab Protected Branches).
- **Static Analysis Basics**: Mekanisme kerja parser, Lexer, Tokens, dan traversal Abstract Syntax Tree (AST).

---

### 3. Concept & Internal Architecture

Dalam rekayasa sistem enterprise, *Code Review* bukanlah sekadar aktivitas editorial untuk memeriksa gaya penulisan (*formatting/linting*) atau kesalahan sintaksis sepele. Code review adalah **gerbang validasi integritas arsitektural (*Architectural Gate*)** terakhir sebelum artefak biner dikompilasi, dideploy, dan melayani *production traffic*.

#### 3.1. Taksonomi Inspeksi Arsitektural dalam PR
Sistem review modern memisahkan tanggung jawab menjadi dua ranah utama:
1. **Machine-Automated Verification (Invariance Gates)**:
   - *Architectural Fitness Functions*: Menjamin modul tidak melanggar aturan dependensi (misalnya: *Domain Layer* tidak boleh mengimpor *Infrastructure Layer*).
   - *Contract & Schema Evolution*: Memvalidasi bahwa migrasi database mematuhi paradigma *Expand and Contract* dan skema gRPC/OpenAPI bersifat *non-breaking*.
   - *Security & Secret Scanning*: Deteksi kebocoran entropi tinggi, SAST (*Static Application Security Testing*), dan SCA (*Software Composition Analysis*).
2. **Human Cognitive Review (Intent & Trade-off Assessment)**:
   - Validasi asumsi bisnis, ketahanan sistem terhadap *partial failure*, pertimbangan konsistensi vs. ketersediaan (*CAP theorem trade-offs*), serta dampak latensi (*tail latency degradation*).

#### 3.2. Risk-Based PR Classification Engine
PR tidak boleh diperlakukan secara seragam. Model arsitektur review enterprise menerapkan *Risk-Scoring Algorithm*:

$$\text{PR Risk Score} = (w_1 \cdot \text{ChgLOC}) + (w_2 \cdot \text{CriticalPaths}) + (w_3 \cdot \text{SchemaChg}) + (w_4 \cdot \text{ConcurrencyPrims})$$

- **Tier 1 (High Risk)**: Perubahan pada *core financial ledger*, isolasi transaksi DB, algoritma enkripsi, atau dependensi lintas domain. Wajib mendapatkan *approval* minimal dari 2 Principal/Staff Engineers + lolos 100% *automated invariant tests*.
- **Tier 2 (Medium Risk)**: Penambahan *endpoint* baru, perubahan logika bisnis internal domain, modifikasi indeks database. Cukup 1 Senior Peer Reviewer.
- **Tier 3 (Low Risk)**: Pembaruan dokumentasi, perbaikan teks UI, konfigurasi dependensi minor non-core. Dapat digabungkan secara otomatis (*auto-merge*) jika lolos CI.

---

### 4. Why & What

| Dimensi | Mengapa Diperlukan (*Why*) | Apa Entitasnya (*What*) |
| :--- | :--- | :--- |
| **Architectural Drift** | Tanpa kontrol ketat, batas dependensi modul terdegradasi menjadi *Big Ball of Mud* secara perlahan. | *Automated Dependency Rule Enforcement* via AST parsing dan ArchUnit/custom linters. |
| **Production Outages** | 70% insiden produksi terdistribusi dipicu oleh *silent breaking changes* (misal: serialisasi enum atau *blocking I/O* pada event loop). | *Backward Compatibility Review Checklist* & *Static Blocking Detection*. |
| **Cognitive Exhaustion** | Reviewer manusia menghabiskan energi untuk hal mekanistik (*indentation, naming convention*), mengabaikan celah konkurensi fatal. | *Shift-left Automation*: Delegasi 100% verifikasi mekanis ke CI pipeline. |
| **Velocity Bottleneck** | PR menumpuk berhari-hari menunggu review, memicu *merge conflicts* masif dan menurunkan *Deployment Frequency* (DORA metric). | Penegakan *PR Sizing Limits* ($\le 250$ LOC) dan formalisasi *Review Response SLO* ($\le 4$ jam). |

---

### 5. How (Workflow Detail)

Alur kerja peninjauan arsitektural pada skala enterprise diatur melalui *Multi-Stage Gated Pipeline*:

```
[Developer Push] 
       │
       ▼
[Stage 0: Pre-Commit / Local Hook] 
       │ (Gitleaks, Lint, Local Unit Tests)
       ▼
[Stage 1: Ingestion & PR Triage Engine]
       │ ── Compute Diff Risk Score & AST Impact Analysis
       │ ── Apply Dynamic Branch Protection Rules
       ▼
[Stage 2: Asynchronous Machine Verification]
       ├── Linting & Formatting Check (Prettier, GolangCI-Lint, Ruff)
       ├── Architectural Fitness Check (Dependency Validation)
       ├── Backward Compatibility Gate (Buf breaking, OpenAPI Diff)
       └── Database Migration Safety Check (Dry-run, Lock Analysis)
       │
       ├─── [Any Gate Fails?] ──► [Block PR & Add Review Bot Annotations]
       │
       ▼ [All Automated Gates Pass]
[Stage 3: Risk-Directed Routing]
       ├── Tier 1 ──► Domain Expert + Staff/Principal Systems Architect
       ├── Tier 2 ──► Peer Domain Reviewer
       └── Tier 3 ──► Fast-Track Merge
       │
       ▼
[Stage 4: Human Collaborative Inspection]
       │ ── Verify Failure Modes, Telemetry/Observability, Resource Leaks
       ▼
[Stage 5: Final Merge & Telemetry Tracking]
       └── Auto-squash/rebase merge -> Collect Time-to-Merge (TTM) Metrics
```

---

### 6. Analogy & Diagram ASCII

#### Analogi
Bayangkan pembangunan gedung pencakar langit.
- **Linter & Unit Test** adalah inspeksi material dasar: memastikan adukan semen dan diameter besi beton sesuai standar pabrik.
- **Architectural Code Review** adalah inspeksi struktur oleh Ahli Rekayasa Sipil: mengevaluasi apakah pergeseran pilar di lantai 12 akan menyebabkan keruntuhan progresif (*progressive collapse*) ketika terjadi gempa bumi berkekuatan 7 SR, atau apakah sistem pipa darurat dapat menahan tekanan air puncak.

#### Diagram Arsitektur Alur Review

```
                ARSITEKTUR REVIEW GATE ENTERPRISE
                
   +-------------------------------------------------------------+
   |                        Developer PR                         |
   |             (Git Diff Payload + Context Metadata)           |
   +-------------------------------------------------------------+
                                  |
                                  v
   +-------------------------------------------------------------+
   |                     Static Orchestrator                     |
   +-------------------------------------------------------------+
            |                      |                      |
            v                      v                      v
     +--------------+      +--------------+      +----------------+
     | Dependencies |      | DB Migration |      |   API Schema   |
     | Boundaries   |      |  Lock Safety |      | Compatibility  |
     | (Arch Linter)|      | (pg-migrate) |      | (Buf / Spectral|
     +--------------+      +--------------+      +----------------+
            |                      |                      |
            +----------------------+----------------------+
                                   |
                   +---------------+---------------+
                   | Fail                          | Pass
                   v                               v
         [PR Status: RED BLOCKED]      [Automated PR Labeling:    ]
         [Bot Post Line Annotations]   [Tier-1 / Domain: Core-Fin ]
                                                   |
                                                   v
                                       +-----------------------+
                                       | CODEOWNERS Routing    |
                                       | - Staff System Eng    |
                                       | - Domain Specialist   |
                                       +-----------------------+
                                                   |
                                                   v
                                       +-----------------------+
                                       | Human Architectural   |
                                       | Verification          |
                                       +-----------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: PR Description & Atomic Boundary

**Buruk (Anti-Pattern):**
```markdown
PR: Fix payment and add report feature
Description: Fixed some bugs, added transaction table, updated user endpoints.
Files Changed: 48 files (+2400, -890)
```
*Masalah*: Monolitik, mencampurkan perbaikan *bug* dengan *feature release*, tidak ada konteks arsitektural, memicu *cognitive overload*.

**Standar Enterprise:**
```markdown
### Architectural Context
- **Domain**: Billing & Settlement (`bounded_context: payments`)
- **Type**: Architectural Optimization (DB I/O Bottleneck)
- **ADR Reference**: ADR-2024-08 (Outbox Pattern Implementation)

### Changes
1. Menghapus direct synchronous call ke `NotificationService` dari dalam database transaction block.
2. Mengimplementasikan transactional outbox payload ke tabel `outbox_events`.

### Invariant & Performance Validation
- [x] Zero Schema Breaking Changes (Skema backwards-compatible tested).
- [x] Transaksi database `db.tx` direduksi dari durasi median 180ms ke 12ms.
- [x] Metrik Prometheus baru: `payment_outbox_enqueue_duration_seconds`.
```

#### 7.2 Practical Example (Enterprise AST Linter untuk Deteksi Pelanggaran Arsitektur)

Contoh nyata: Mencegah *Goroutine Leak* dan memaksakan propagasi `context.Context` serta melarang pemanggilan database/HTTP langsung dari dalam paket `domain` menggunakan custom linter berbasis Go AST.

```go
// File: tools/archlinter/main.go
package main

import (
	"fmt"
	"go/ast"
	"go/parser"
	"go/token"
	"os"
	"path/filepath"
	"strings"
)

// Architectural Invariant:
// 1. Paket 'internal/domain' TIDAK BOLEH mengimpor 'internal/infrastructure'.
// 2. Fungsi public di 'internal/domain' WAJIB menerima 'context.Context' sebagai argumen pertama.

func main() {
	if len(os.Args) < 2 {
		fmt.Println("Usage: archlinter <root_directory>")
		os.Exit(1)
	}

	rootDir := os.Args[1]
	fset := token.NewFileSet()
	hasViolations := false

	err := filepath.Walk(rootDir, func(path string, info os.FileInfo, err error) error {
		if err != nil || !strings.HasSuffix(path, ".go") || strings.HasSuffix(path, "_test.go") {
			return nil
		}

		node, parseErr := parser.ParseFile(fset, path, nil, parser.ImportsOnly|parser.ParseComments)
		if parseErr != nil {
			fmt.Printf("ERROR: Failed to parse %s: %v\n", path, parseErr)
			hasViolations = true
			return nil
		}

		// Rule 1: Check Domain Isolation
		if strings.Contains(path, "internal/domain") {
			for _, imp := range node.Imports {
				importPath := strings.Trim(imp.Path.Value, `"`)
				if strings.Contains(importPath, "internal/infrastructure") {
					fmt.Printf("VIOLATION: [ARCH-001] Layer Leaking at %s:%d\n", path, fset.Position(imp.Pos()).Line)
					fmt.Printf("  -> Package 'domain' cannot depend on 'infrastructure': %s\n", importPath)
					hasViolations = true
				}
			}
		}

		// Rule 2: Advanced Syntax Tree inspection for DB Query Inside HTTP Handler
		fullNode, err := parser.ParseFile(fset, path, nil, 0)
		if err == nil && strings.Contains(path, "internal/delivery/http") {
			ast.Inspect(fullNode, func(n ast.Node) bool {
				call, ok := n.(*ast.CallExpr)
				if !ok {
					return true
				}

				// Deteksi pemanggilan langsung ke SQL execution method di transport layer
				if sel, ok := call.Fun.(*ast.SelectorExpr); ok {
					dangerousMethods := map[string]bool{"Query": true, "QueryRow": true, "Exec": true}
					if dangerousMethods[sel.Sel.Name] {
						fmt.Printf("VIOLATION: [ARCH-002] Direct DB execution inside Transport Layer at %s:%d\n",
							path, fset.Position(sel.Pos()).Line)
						fmt.Println("  -> Use Application/Usecase Service layer instead.")
						hasViolations = true
					}
				}
				return true
			})
		}

		return nil
	})

	if err != nil {
		fmt.Printf("Scan failure: %v\n", err)
		os.Exit(1)
	}

	if hasViolations {
		fmt.Println("\nResult: PR Review Check FAILED. Architectural boundaries violated.")
		os.Exit(1)
	}

	fmt.Println("Result: PR Review Check PASSED. Architectural boundaries intact.")
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
- **Perusahaan**: Payment Fintech Unicorn (Skala: 35.000 TPS, 600+ Engineer, Monorepo 4.5 Juta Baris Kode).
- **Insiden Fatal**: Sebuah PR sederhana disetujui (2 approval peer review konvensional) untuk menambahkan validasi idempotensi ke tabel `ledger_entries`. 
- **Akar Masalah**: Engineer menambahkan indeks database baru menggunakan perintah standar:
  ```sql
  CREATE INDEX idx_ledger_idempotency ON ledger_entries (idempotency_key);
  ```
  Di Postgres, eksekusi ini memperoleh *AccessExclusiveLock*, memblokir seluruh operasi `INSERT` dan `UPDATE` pada tabel pembayaran selama 42 menit di jam sibuk.

#### Solusi Arsitektur Peninjauan Kode
1. **Penerapan Automated Database Migration Linter** pada CI:
   Setiap PR yang menyentuh direktori `migrations/*.sql` secara otomatis dicegat oleh pipeline yang mengeksekusi analisis statis lint SQL:
   - Menolak perintah `CREATE INDEX` tanpa klausa `CONCURRENTLY`.
   - Menolak penambahan kolom `NOT NULL` tanpa `DEFAULT` value bertahap.
   - Menolak `ALTER TABLE ... ADD CONSTRAINT` tanpa status `NOT VALID`.
2. **Dynamic Reviewer Assignment (CODEOWNERS + Risk Matrix)**:
   Perubahan pada migration, layer konkurensi, dan core balancing service dialihkan secara otomatis ke *Data Platform Guild* dan *Principal Architect*.
3. **Hasil**: Penurunan insiden *database locking downtime* sebesar 100% dalam 12 bulan berikutnya, tanpa menurunkan kecepatan *deployment* tim non-core.

---

### 9. Trade-offs

```
                           Trade-Off Spectrum
         Kecepatan (Velocity) <────────────────> Keandalan (Reliability)
    (Optimistis / Rubber-stamp)                (Ketelitian Arsitektural)
```

| Dimensi | Pendekatan Ringan (*Optimistic Review*) | Pendekatan Ketat (*Strict Architectural Gate*) |
| :--- | :--- | :--- |
| **Throughput / DORA Lead Time** | Sangat Cepat (PR merge dalam hitungan jam). | Lebih Lambat (Membutuhkan 1-2 siklus review spesialis). |
| **System Latency & Stability** | Rentan degradasi latensi karena *N+1 queries*, *goroutine leak*, *unindexed tables*. | Terjamin; performa *p99* terjaga melalui analisis formal sebelum merge. |
| **Developer Autonomy vs Control** | Otonomi tinggi; resiko *architectural drift* dan fragmentasi desain tinggi. | Otonomi terstruktur; konsistensi sistemik terjamin via kontrak desain. |
| **Resource & Compute Cost** | Biaya CI rendah (hanya lint/unit test standar). | Biaya CI lebih tinggi (AST parsing, transient ephemeral DB runs, compatibility testing). |

---

### 10. Common Mistakes & Troubleshooting

#### 1. The "Looks Good To Me" (LGTM) Rubber-Stamping
- **Gejala**: PR 1.000 LOC di-approve dalam waktu kurang dari 5 menit tanpa satu pun komentar teknis.
- **Dampak Arsitektur**: Kebocoran memori terdistribusi, kegagalan *circuit breaker*, dan bypass autentikasi lolos ke staging/prod.
- **Solusi**: Terapkan *Time-on-Review Monitoring* dan batasi batas maksimal diff PR menjadi $\le 300$ baris per unit inspeksi.

#### 2. Bike-Shedding (Law of Triviality)
- **Gejala**: Reviewer berdebat 50 komentar mengenai nama variabel atau urutan penulisan import, tetapi mengabaikan pemanggilan `SELECT * FOR UPDATE` tanpa timeout di dalam loop.
- **Solusi**: Pisahkan ranah: Gaya penulisan harus diselesaikan 100% oleh *auto-formatter* (`gofmt`, `biome`, `ruff`) sebelum PR dapat dibuka. Manusia dilarang mengomentari hal yang dapat diotomasi.

#### 3. Unbounded Context Leakage
- **Gejala**: Service Cart langsung melakukan query ke database Order untuk memvalidasi voucher diskon.
- **Troubleshooting**: Terapkan isolasi jaringan database (user role privileges) dan enforce *Dependency Linters* pada CI PR gate.

---

### 11. Best Practices (Production Checklist)

#### Author's Pre-Flight Checklist
- [ ] PR berukuran atomik ($\le 300$ baris diff logika produktif, di luar file autogen).
- [ ] Menyertakan metrik observabilitas (Prometheus counters, distributed tracing spans) untuk logika bisnis baru.
- [ ] Skema database dan payload serialisasi diverifikasi backwards-compatible (*dual-write/expand-contract ready*).
- [ ] Alur penanganan kesalahan (*error handling*) mencakup skenario *fallback* dan pembatasan timeout pada semua pemanggilan I/O eksternal.

#### Reviewer's Architectural Inspection Checklist
- [ ] **Concurrency**: Apakah struktur data terlindungi dari *race condition*? Apakah lock scope dibuat se-minimal mungkin?
- [ ] **Backpressure & Resource Management**: Apakah koneksi stream/database di-close dengan benar (`defer`, `using`, `try-with-resources`)?
- [ ] **Data Safety**: Apakah ada potensi *table locking*, *table scan* pada volume data besar, atau *data loss* saat rollback?
- [ ] **Failure Blast Radius**: Jika dependensi pihak ketiga gagal/timeout, apakah fungsi utama sistem tetap berjalan secara terdegradasi (*graceful degradation*)?

---

### 12. Hands-on Practice

Buat struktur direktori untuk praktikum implementasi linter arsitektur otomatis:

```bash
mkdir -p hands-on/m02/rules
mkdir -p hands-on/m02/src/domain
mkdir -p hands-on/m02/src/infrastructure
mkdir -p hands-on/m02/src/delivery
```

#### Langkah 1: Siapkan Struktur Kode
Buat file target pengujian pelanggaran arsitektur.

`hands-on/m02/src/domain/entity.go`:
```go
package domain

// Model representasi entitas murni tanpa dependensi eksternal
type Order struct {
    ID     string
    Amount float64
}
```

`hands-on/m02/src/domain/violation.go` (Kode Pelanggar):
```go
package domain

// BAD PRACTICE: Domain bergantung langsung pada infrastruktur
import (
    "context"
    "hands-on/m02/src/infrastructure"
)

type OrderUseCase struct {
    repo infrastructure.DatabaseClient // VIOLATION!
}

func (uc *OrderUseCase) Execute(ctx context.Context) error {
    return nil
}
```

`hands-on/m02/src/infrastructure/db.go`:
```go
package infrastructure

type DatabaseClient struct{}
```

#### Langkah 2: Buat Pipeline Verifikasi
Implementasikan script verifikasi `hands-on/m02/verify.sh`:

```bash
#!/usr/bin/env bash
set -e

echo "[+] Menjalankan Static Architectural Boundaries Inspector..."

# Simulasikan kompilasi dan eksekusi custom Go AST analyzer
cat << 'EOF' > hands-on/m02/linter.go
package main

import (
	"fmt"
	"go/parser"
	"go/token"
	"os"
	"path/filepath"
	"strings"
)

func main() {
	fset := token.NewFileSet()
	hasError := false

	filepath.Walk("hands-on/m02/src/domain", func(path string, info os.FileInfo, err error) error {
		if !strings.HasSuffix(path, ".go") {
			return nil
		}
		node, err := parser.ParseFile(fset, path, nil, parser.ImportsOnly)
		if err != nil {
			return err
		}
		for _, imp := range node.Imports {
			if strings.Contains(imp.Path.Value, "infrastructure") {
				fmt.Printf("[GAGAL] Pelanggaran Arsitektur ditemukan pada %s: Mengimpor Infrastructure layer!\n", path)
				hasError = true
			}
		}
		return nil
	})

	if hasError {
		os.Exit(1)
	}
	fmt.Println("[SUKSES] Semua batasan arsitektur terpenuhi.")
}
EOF

go run hands-on/m02/linter.go
```

#### Langkah 3: Eksekusi dan Verifikasi
Jalankan script verifikasi untuk memastikan CI pipeline memblokir pelanggaran:
```bash
chmod +x hands-on/m02/verify.sh
./hands-on/m02/verify.sh
# Expected output: Return code 1 dengan pesan error pelanggaran arsitektur terdeteksi.
```

---

### 13. Exercise

#### Level Easy
- **Tugas**: Buat file konfigurasi `.github/pull_request_template.md` yang memuat verifikasi kriteria arsitektur: ADR linkage, dampak terhadap P99 Latency, skema migrasi database, dan pemantauan SLO.

#### Level Medium
- **Tugas**: Buat GitHub Actions workflow yang menganalisis file git diff pada PR. Jika terdapat perubahan file pada skema SQL (`migrations/*.sql`), namun tidak menyertakan pembaruan file rollback (`rollback/*.sql`), gagalkan pipeline secara otomatis.

#### Level Hard
- **Tugas**: Bangun CLI tool dalam bahasa Go, Python, atau Rust yang menerima output `git diff origin/main...HEAD` dan menghitung *Architectural Blast Radius Score*. Lakukan pemblokiran otomatis pada pipeline jika fungsi yang ditandai dengan anotasi `// @critical-path` diubah tanpa menyertakan pengujian beban (*benchmark test* `*_bench_test.go`).

---

### 14. Challenge

**Skenario**: Sistem Rekening Giro Enterprise (Core Banking) mengalami insiden *concurrency deadlock* karena sebuah PR menggabungkan modifikasi dua entitas akun bank tanpa urutan *locking* yang terstandarisasi (*Resource Hierarchy Ordering*).

**Tantangan**:
Rancang mekanisme review end-to-end yang menjamin hal ini tidak terulang:
1. Formulasikan sebuah **Arsitektur Static Analyzer / Code Review Gate Rule** yang memvalidasi bahwa setiap akuisisi *distributed lock* atau *database row-level lock* (`SELECT ... FOR UPDATE`) pada lebih dari 1 tabel/baris wajib melakukan locking berdasarkan urutan deterministik (*lexicographical order by UUID/ID*).
2. Buat matriks eskalasi peninjauan (*Review Escalation Policy*) yang menetapkan parameter kapan sebuah PR harus ditolak secara otomatis untuk dipecah menjadi beberapa *Micro-PRs*, lengkap dengan strategi validasi transaksi terdistribusi tanpa downtime.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Pertanyaan)
1. **Mengapa pemeriksaan formatting/linting sintaks tidak boleh menjadi tanggung jawab manusia saat code review?**
   - *Jawaban*: Karena formatting dan sintaks bersifat deterministik dan mekanis, sehingga pemborosan waktu kognitif reviewer (memicu *bike-shedding*) yang seharusnya dialokasikan untuk memverifikasi logika bisnis, arsitektur, dan konkurensi.

2. **Apa dampak arsitektural utama dari PR yang berukuran terlalu besar (>1.000 baris diff)?**
   - *Jawaban*: Penurunan drastis pada kedalaman evaluasi teknis (*review fatigue*), tingginya kemungkinan insiden tersembunyi lolos ke produksi (*rubber-stamping*), serta risiko *merge conflicts* yang tinggi.

3. **Apa fungsi utama dari berkas `CODEOWNERS` dalam arsitektur repositori skala enterprise?**
   - *Jawaban*: Menegakkan routing otomatis hak peninjauan dan persetujuan wajib (*mandatory approval*) kepada pemilik domain/infrastruktur yang bertanggung jawab atas direktori atau modul tertentu.

4. **Dalam paradigma clean architecture, mengapa domain layer sama sekali tidak boleh mengimpor infrastructure layer?**
   - *Jawaban*: Agar *core business logic* bersifat agnostik terhadap teknologi eksternal (database, network, transport layer), independen, mudah diuji secara modular, dan tidak terdistorsi oleh implementasi teknis tingkat rendah.

5. **Apa yang dimaksud dengan "Architectural Fitness Function"?**
   - *Jawaban*: Fungsi, tes, atau analisis statis otomatis yang mengukur dan menjamin bahwa sistem tetap mematuhi batasan integritas arsitektural yang telah ditetapkan seiring evolusi basis kode.

#### Intermediate (5 Pertanyaan)
6. **Bagaimana cara mengamankan review PR yang memodifikasi skema database tabel dengan 100 juta baris data agar tidak terjadi downtime?**
   - *Jawaban*: Reviewer harus memastikan operasi menggunakan teknik *expand-contract*: hindari locking eksklusif (misal: gunakan `ADD COLUMN` nullable atau tanpa default value yang berat, gunakan `CREATE INDEX CONCURRENTLY`), serta hindari modifikasi tipe data secara in-place.

7. **Pada distributed system, hal mendasar apa yang harus dievaluasi reviewer ketika melihat pemanggilan remote RPC sinkron baru di dalam loop?**
   - *Jawaban*: Bahaya *cascading failures*, degradasi latensi kumulatif (*head-of-line blocking*), ketiadaan timeout/circuit breaker, serta potensi habisnya pool koneksi socket.

8. **Bagaimana peran Abstract Syntax Tree (AST) dalam mengotomatisasi peninjauan arsitektur?**
   - *Jawaban*: AST merepresentasikan hierarki sintaks kode sebagai struktur pohon data, memungkinkan penganalisis statis memverifikasi tipe data argumen, impor paket terlarang, struktur kontrol eksekusi, dan penggunaan anotasi secara programatik tanpa menjalankan aplikasi.

9. **Apa indikasi terjadinya "Silent Breaking Change" pada serialisasi event driven system saat meninjau PR?**
   - *Jawaban*: Mengubah tipe data field lama pada payload event, menghapus field yang diasumsikan selalu ada oleh konsumen lama, atau mengganti urutan/makna field enum tanpa mekanisme migrasi versi schema (*backward-incompatible*).

10. **Bagaimana menetapkan Review SLO yang seimbang antara kecepatan tim (*velocity*) dan ketelitian desain?**
    - *Jawaban*: Menerapkan *Risk-Based Triage*: membatasi ukuran PR ($\le 250$ baris), mewajibkan respons review awal maksimal 4 jam kerja untuk PR low/medium risk, dan mengarahkan PR high-risk ke jadwal arsitektural review terencana tanpa menghalangi aliran kerja tim lainnya.

#### Skenario Kasus Produksi (3 Pertanyaan)

11. **Skenario 1**: Seorang software engineer mengajukan PR yang mengimplementasikan *caching* Redis pada microservice Order untuk mempercepat query status pembayaran. Di dalam PR terdapat kode berikut:
    ```go
    val, err := redisClient.Get(ctx, orderID).Result()
    if err == redis.Nil {
        val = db.Query("SELECT status FROM orders WHERE id = ?", orderID)
        redisClient.Set(ctx, orderID, val, 0) // No TTL
    }
    ```
    *Sebagai Staff Reviewer, sebutkan 3 celah arsitektural fatal yang harus membuat PR ini DITOLAK!*
    - *Jawaban*: 
      1. *Unbounded Cache Growth / OOM*: Ketiadaan TTL (`TTL = 0`) akan membuat memori instance Redis penuh secara progresif, memicu eviction berbahaya atau Redis Out-Of-Memory panic.
      2. *Cache Stampede (Thundering Herd)*: Ketiadaan mekanisme *single-flight* atau *mutex locking* saat cache miss akan membuat lonjakan traffic langsung menghancurkan database utama.
      3. *Cache-Database Inconsistency*: Tidak ada mekanisme invalidasi cache saat status order di-update di database, mengakibatkan pembacaan data basi (*stale data*) permanen.

12. **Skenario 2**: Dalam sebuah repositori berbasis microservices, tim pembayaran membuat PR yang mengimpor package repository langsung dari microservice user melalui shared library internal (`github.com/org/user/repo`). 
    *Apa kritik arsitektural Anda dan bagaimana mitigasinya?*
    - *Jawaban*: PR ini melanggar isolasi *Bounded Context* dan *Data Autonomy*. Berbagi *data access layer* antar layanan microservice menciptakan *tight coupling* pada skema database bersama (*Shared Database Anti-pattern*). Reviewer harus menolak PR dan memaksakan interaksi melalui kontrak API resmi (gRPC/REST) atau replikasi event asinkron (*Event-Carried State Transfer*).

13. **Skenario 3**: Sebuah PR menambahkan fungsi pemrosesan data batch yang meluncurkan worker pool menggunakan unbounded Go goroutines:
    ```go
    for _, item := range massivePayloadList {
        go processItem(item)
    }
    ```
    *Bagaimana analisis dampak review Anda terhadap utilisasi memori dan kestabilan sistem host saat load tinggi? Solusi apa yang harus Anda instruksikan?*
    - *Jawaban*: Pembuatan goroutine tanpa batas (*unbounded concurrency*) akan menyebabkan lonjakan alokasi memori yang masif, kelelahan thread OS (*thread exhaustion*), *context-switching thrashing*, serta membanjiri downstream I/O hingga memicu OOM Kill (*crash*). Reviewer harus menginstruksikan implementasi *Worker Pool* berukuran tetap (*fixed-size worker pool*), penggunaan channel bertipe *bounded buffer*, atau mekanisme semaphore untuk membatasi konkurensi puncak.

---

### 16. Summary

Peninjauan kode tingkat arsitektural (*Enterprise Architectural Code Review*) merupakan pilar pertahanan terdepan dalam menjaga integritas struktur sistem, keberlanjutan basis kode, dan keandalan sistem berskala besar.

```
       DELEGASIKAN KE MESIN                    FOKUSKAN KEPADA MANUSIA
 ┌───────────────────────────────┐        ┌───────────────────────────────┐
 │ • Linting & Coding Standards  │        │ • Architectural Trade-offs    │
 │ • Dependency Rule Violations  │   VS   │ • Concurrency & Race Hazards  │
 │ • Breaking Contract Changes   │        │ • Partial Failure Resilience  │
 │ • SQL Migration Lock Hazards  │        │ • Domain Logic Soundness      │
 └───────────────────────────────┘        └───────────────────────────────┘
```

Kunci keberhasilan skalabilitas review terletak pada **pembagian beban kerja**: delegasikan seluruh verifikasi mekanistik, deterministik, dan struktural ke sistem otomatis (*Automated CI Gates* & *AST Linters*), sehingga kapasitas kognitif engineer tingkat lanjut dapat difokuskan seutuhnya pada evaluasi trade-off arsitektural, batas kegagalan sistem (*blast radius*), dan keberlanjutan sistem jangka panjang.