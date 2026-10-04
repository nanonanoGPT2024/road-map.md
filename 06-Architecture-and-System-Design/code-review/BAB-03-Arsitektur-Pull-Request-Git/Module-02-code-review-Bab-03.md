# Kurikulum Rekayasa Perangkat Lunak Enterprise
## Topik: Code Review & Git Engineering Architecture
### Kategori: 06-Architecture-and-System-Design
### Bab 03: Arsitektur Pull Request & Git
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta didik pada level Senior/Staff Engineer diharapkan mampu:
*   **Menganalisis Internal DAG (Directed Acyclic Graph) Git**: Membedah mutasi pointer commit, struktur *tree object*, dan algoritma penggabungan cabang (*merge engine* `ort` dan `recursive`) secara deterministik.
*   **Merancang Enterprise PR Lifecycles & Merge Queues**: Mengeliminasi fenomena *broken trunk* dan *semantic merge conflict* pada skala ratusan pull request per hari menggunakan arsitektur *Merge Train* / *Merge Queue*.
*   **Mengonfigurasi dan Mengotomasi Strategic Branching**: Memilih dan mengeksekusi strategi integrasi cabang (*3-way merge*, *rebase & fast-forward*, atau *squash & merge*) berdasarkan trade-off histori audit vs *bisectability*.
*   **Membangun Gatekeeping CI/CD Terdistribusi**: Mengonfigurasi *branch protection rules*, *concurrency cancelation*, *path-based triggering*, dan *required status checks* di tingkat organisasi enterprise.
*   **Menangani State Repository Skala Besar**: Menangani mitigasi *monorepo drift*, *stale branches*, *ref lock contention*, dan *phantom commit issues*.

---

## 2. Prerequisites

Sebelum mempelajari modul ini, peserta wajib menguasai:
1.  **Git Fundamentals**: Pemahaman solid mengenai three-tree architecture (Working Directory, Staging Area/Index, HEAD), serta format object Git (Blob, Tree, Commit, Tag).
2.  **CI/CD Pipeline Engine**: Pengalaman konfigurasi runner CI (GitHub Actions, GitLab CI, atau Argo Workflows).
3.  **Basic Graph Theory**: Pemahaman siklus, traversal, dan topological sorting pada Directed Acyclic Graph (DAG).
4.  **CLI & Automation Scripting**: Mahir menggunakan Bash dan Python untuk interaksi API Git/GitHub/GitLab.

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Anatomi Git Object Storage & Commit DAG

Git secara fundamental adalah sebuah *content-addressable key-value datastore* berbasis objek biner yang dibungkus oleh antarmuka *Directed Acyclic Graph* (DAG). Setiap objek diidentifikasi oleh hash SHA-1 (160-bit) atau SHA-256 (256-bit).

```
.git/objects/
├── [2-char prefix]/
│   └── [38-char hash] -> Zlib-compressed object: [type] [size]\0[content]
```

Ada 4 tipe objek dasar dalam Git:
1.  **Blob**: Menyimpan data mentah berkas (tanpa metadata izin/nama berkas).
2.  **Tree**: Menyimpan pointer ke Blob (berkas) atau Tree lain (direktori), lengkap dengan atribut mode UNIX dan nama berkas.
3.  **Commit**: Node dalam DAG. Berisi pointer ke root Tree, array pointer ke parent commit SHA, metadata author/committer, timestamp, dan commit message.
4.  **Tag**: Pointer statis beranotasi ke suatu commit tertentu.

```
       [ Commit Object ]
       +---------------+
       | tree 8a3f...  | ----> [ Tree Object: Root ]
       | parent 4b21.. |       ├── 100644 blob c3d8... (main.go)
       | author ...    |       └── 040000 tree e1a2... (pkg/)
       +---------------+                               └── 100644 blob f91c... (util.go)
              |
              v (references)
       [ Parent Commit ]
```

### 3.2 Anatomi Pull Request di Level Server Git

Pull Request (atau Merge Request) bukan merupakan konsep primitif di dalam spesifikasi engine Git; PR adalah abstraksi application-layer yang dibangun oleh forge hosting (GitHub, GitLab, Bitbucket).

Ketika sebuah Pull Request dibuat dari `feature-branch` menuju `main`:
1.  Forge membuat namespace ref khusus secara dinamis:
    *   GitHub: `refs/pull/[PR_ID]/head` (commit terkini dari PR) dan `refs/pull/[PR_ID]/merge` (commit bayangan hasil uji merge otomatis ke target branch).
    *   GitLab: `refs/merge-requests/[MR_ID]/head`.
2.  Forge menjalankan algoritma uji penggabungan (*speculative merge*) di server background untuk memvalidasi apakah merge dapat diselesaikan secara otomatis (tanpa konflik sintaksis Git). Hasil kalkulasi ini menentukan atribut `mergeable: true/false` pada API PR.

### 3.3 Anatomi Mesin Merge: Fast-Forward vs 3-Way vs Rebase vs Squash

```
Kondisi Awal:
        B---C  (feature)
       /
  A---D        (main)

1. Fast-Forward Merge (Hanya jika D tidak divergen dari A):
  A---B---C (main, feature)

2. 3-Way Merge (True Merge Commit):
        B---C      (feature)
       /     \
  A---D-------M    (main -> Commit M memiliki 2 parent: D dan C)

3. Rebase and Fast-Forward:
  A---D---B'---C'  (main, feature -> B' dan C' memiliki SHA baru)

4. Squash and Merge:
  A---D---S        (main -> S adalah commit tunggal dengan tree setara C, parent tunggal D)
```

Perbandingan Mekanisme Internal:
*   **3-Way Merge (`git merge --no-ff`)**: Mesin mencari *Lowest Common Ancestor* (LCA) antara commit D dan C (yaitu commit A). Mesin menjalankan algoritma merge (default modern: engine `ort` - *Ostensibly Recursive's Twin*) untuk mengompilasi delta `A -> D` dan delta `A -> C`. Jika tidak ada benturan byte, commit baru (M) dibuat dengan **dua parent pointer**: `parent1 = D`, `parent2 = C`.
*   **Rebase (`git rebase main`)**: Mengubah basis commit feature. Git mengambil commit `B` dan `C`, menyimpannya sebagai patch sementara di `.git/rebase-apply`, mereset HEAD ke `D`, lalu menerapkan patch `B` (menjadi `B'`) dan `C` (menjadi `C'`). Hash SHA berubah karena parent, timestamp, dan konteks tree berubah.
*   **Squash and Merge**: Git mengomparasi root tree `D` dengan root tree `C`. Delta dikompresi menjadi satu *changeset*. Commit baru `S` dibuat dengan `parent = D`. Seluruh granularitas riwayat commit `B` dan `C` dihapus dari trunk, menjaga linearitas commit log.

### 3.4 Concurrency Race Condition pada Skala Enterprise: "The Broken Trunk Problem"

Pada tim rekayasa skala enterprise (>50 developer aktif), PR diverifikasi secara independen melalui CI terhadap basis commit saat PR tersebut dibuka. Kondisi ini menimbulkan **Semantic Race Condition**:

```
Time 0: Main berada di commit A.
Time 1: PR 1 (Dev A) dicabangkan dari A. CI sukses menguji (A + PR1).
Time 2: PR 2 (Dev B) dicabangkan dari A. CI sukses menguji (A + PR2).
Time 3: PR 1 dimerge ke Main -> Main = A + PR1.
Time 4: PR 2 dimerge ke Main -> Main = A + PR1 + PR2.
```

Masalah: CI untuk PR 2 **tidak pernah menguji** kombinasi `A + PR1 + PR2`. Jika PR 1 mengubah kontrak fungsi (misal: mengganti tipe data argumen) dan PR 2 memanggil fungsi tersebut dengan tipe lama, **sintaksis Git tidak mendeteksi konflik file**, namun pipeline commit Main **langsung patah (*broken trunk*)**.

Solusi: **Merge Queue (Merge Train)**.

---

## 4. Why & What

### Mengapa Pendekatan Konvensional Gagal?
*   **Naive Branch Protection**: Hanya mengandalkan *"Require branches to be up to date before merging"* memaksa developer me-rebase cabang mereka berulang kali setiap kali ada PR lain yang dimerge. Ketika frekuensi merge mencapai 20 PR/jam, developer terjebak dalam kondisi *starvation* (rebase terus menerus tanpa pernah sempat merge).
*   **Semantic Failure**: Pemeriksaan konflik file berbasis hash byte Git tidak memahami AST (Abstract Syntax Tree). Perubahan skema basis data, konfigurasi microservice, atau refactoring method akan lolos filter Git tetapi merusak runtime.

### Apa itu Enterprise PR Engine?
Arsitektur PR Enterprise adalah sistem orkestrasi yang menggabungkan:
1.  **Branch Protection Policy**: Pembatasan akses tulis ke branch utama, penegakan persetujuan review minimal berbasis kepemilikan kode (Code Owners), dan passing status checks.
2.  **Optimistic Merge Queue**: Antrean transaksional yang menggabungkan PR secara serial/spekulatif ke cabang virtual, memicu validasi CI terisolasi, dan memajukan branch utama secara atomik.
3.  **Auto-healing & Bisect Engine**: Mekanisme otomatis yang mengisolasi dan mendepak PR penyebab kegagalan CI dari antrean tanpa memblokir PR lain di belakangnya.

---

## 5. How: Workflow Detail Arsitektur Merge Queue

Berikut adalah siklus hidup Pull Request dalam arsitektur Enterprise Merge Queue:

```
[ Developer ] 
      │ (1) Buat Feature Branch & Push
      ▼
[ Git Forge (GitHub/GitLab) ]
      │ (2) Webhook: PR Opened / Synchronized
      ▼
[ CI Matrix Evaluation ]
      │ (3) Linter, Unit Test, Secret Scanning, Static Analysis
      ▼
[ Peer Review & Code Owners ]
      │ (4) Approval minimal 2 Senior + Approval Tim Security jika sentuh /infra
      ▼
[ User Labels: 'ready-to-merge' ]
      │ (5) Enqueue ke Engine Merge Queue
      ▼
[ Merge Queue Engine ]
      ├── Buat Temporary Branch: queue/pr-123-speculative
      ├── Merge PR ke HEAD trunk terbaru
      ├── Jalankan Integration Test & E2E Test
      │     ├── GAGAL ──> Keluarkan PR, beri notifikasi, revert queue
      │     └── SUKSES ─> Majukan Main Branch (Fast-Forward)
      ▼
[ Trunk Updated (Main) ]
      │ (6) Webhook: Push Event
      ▼
[ CD Deployment Pipeline ]
```

---

## 6. Analogy & Diagram ASCII

### Analogi Jalur Rel Kereta Api (Merge Train)
Bayangkan branch `main` adalah sebuah jalur rel utama. PR konvensional seperti mobil-mobil yang mencoba masuk ke jalur utama tanpa lampu lalu lintas: tabrakan semantik tak terhindarkan.

Merge Queue bertindak seperti **stasiun langsir kereta api spekulatif**:
*   Jika ada 3 PR masuk antrean: PR-A, PR-B, dan PR-C.
*   Sistem tidak menguji mereka satu per satu secara sekuensial lambat.
*   Sistem menyusun gerbong spekulatif paralel:
    *   Uji Train 1: `Main + PR-A`
    *   Uji Train 2: `Main + PR-A + PR-B`
    *   Uji Train 3: `Main + PR-A + PR-B + PR-C`
*   Jika Train 1 & 2 lulus, tapi Train 3 gagal, maka PR-A dan PR-B langsung dimasukkan ke `main`, sementara PR-C diejeksi dari antrean. Sistem lalu langsung menyusun gerbong baru untuk PR berikutnya.

### Diagram Arsitektur Antrean Merge Spekulatif (Speculative Execution)

```
Target Trunk (Commit H)
       │
       ├── Batch 1: [H + PR_A] ──────────────────> CI Status: PASS ──> MERGED TO MAIN
       │
       ├── Batch 2: [H + PR_A + PR_B] ───────────> CI Status: FAIL ──> EJECTED (PR_B Drop)
       │                                                                      │
       └── Batch 3: [H + PR_A + PR_B + PR_C] ──> ABORTED                    │
                                │                                             │
                                └── RE-BATCH 3: [H + PR_A + PR_C] ────────────┴──> CI Status: PASS -> MERGED
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Simulasi Deteksi Semantic Conflict via CLI

Skenario: Developer A mengubah nama fungsi di `math.go`, Developer B menambahkan pemanggilan ke fungsi lama di `calc.go`.

```bash
# 1. Setup repository lokal
mkdir git-conflict-demo && cd git-conflict-demo
git init -b main
git config user.name "Enterprise Architect"
git config user.email "architect@enterprise.internal"

# Commit awal di main
cat << 'EOF' > math.go
package math

func Add(a, b int) int {
    return a + b
}
EOF
git add math.go
git commit -m "feat: initial Add implementation"

# 2. Cabang PR 1: Refactor nama method Add -> AddNumbers
git checkout -b pr-1
cat << 'EOF' > math.go
package math

// AddNumbers menggantikan Add untuk kejelasan semantik
func AddNumbers(a, b int) int {
    return a + b
}
EOF
git add math.go
git commit -m "refactor: rename Add to AddNumbers"

# 3. Cabang PR 2: Dari commit awal main yang sama, menggunakan method Add
git checkout main
git checkout -b pr-2
cat << 'EOF' > calc.go
package math

func Compute() int {
    return Add(10, 20)
}
EOF
git add calc.go
git commit -m "feat: add Compute using Add function"

# 4. Simulasikan Merge PR 1 ke Main
git checkout main
git merge --no-ff pr-1 -m "merge: pr-1 to main"

# 5. Coba Merge PR 2 ke Main (Git akan menganggap ini SUKSES karena beda file!)
git merge --no-ff pr-2 -m "merge: pr-2 to main"

# Output Git: Merge made by the 'ort' strategy.
# GIT MENGANGGAP BERHASIL! (Exit code 0, tidak ada conflict marker)

# 6. Jalankan static compiler / build check
# go vet / build akan gagal seketika di Main branch:
# "calc.go:4:12: undefined: Add"
```

### 7.2 Practical Example: Enterprise GitHub Actions Workflow dengan Path Filter, Concurrency Group, dan Merge Guard

File `.github/workflows/pr-gatekeeper.yml`:

```yaml
name: Enterprise PR Gatekeeper

on:
  pull_request:
    branches: [ main ]
    types: [ opened, synchronize, reopened, ready_for_review ]
  merge_group:
    types: [ checks_requested ]

concurrency:
  # Batalkan run CI yang sedang jalan jika ada push baru ke PR yang sama.
  # Tetapi JANGAN batalkan jika sedang dieksekusi di dalam merge_group!
  group: ${{ github.workflow }}-${{ github.event.pull_request.number || github.ref }}
  cancel-in-progress: ${{ github.event_name != 'merge_group' }}

jobs:
  validate-metadata:
    runs-on: ubuntu-latest
    if: github.event.pull_request.draft == false
    steps:
      - name: Validate Conventional Commits & PR Title
        uses: amannn/action-semantic-pull-request@v5
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        with:
          types: |
            feat
            fix
            chore
            refactor
            docs
            ci
          requireScope: true

  detect-changes:
    runs-on: ubuntu-latest
    needs: validate-metadata
    outputs:
      backend: ${{ steps.filter.outputs.backend }}
      infra: ${{ steps.filter.outputs.infra }}
    steps:
      - uses: actions/checkout@v4
      - uses: dorny/paths-filter@v3
        id: filter
        with:
          filters: |
            backend:
              - 'services/**'
              - 'go.mod'
              - 'go.sum'
            infra:
              - 'terraform/**'
              - 'k8s/**'

  backend-ci:
    needs: detect-changes
    if: ${{ needs.detect-changes.outputs.backend == 'true' || github.event_name == 'merge_group' }}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Go
        uses: actions/setup-go@v5
        with:
          go-version: '1.22'
          check-latest: true
          cache: true

      - name: Static Analysis & Linter
        run: |
          go vet ./...
          # Menjalankan golangci-lint secara strict
          # curl -sSfL https://raw.githubusercontent.com/golangci/golangci-lint/master/install.sh | sh -s -- -b $(go env GOPATH)/bin
          # golangci-lint run ./...

      - name: Unit & Integration Tests with Race Detector
        run: |
          go test -race -v -coverprofile=coverage.out ./...

  gatekeeper-status-check:
    name: "PR Gatekeeper Pass"
    needs: [ backend-ci ]
    if: always()
    runs-on: ubuntu-latest
    steps:
      - name: Evaluate Dependencies
        run: |
          if [[ "${{ needs.backend-ci.result }}" =~ ^(success|skipped)$ ]]; then
            echo "All mandatory CI checks passed successfully or skipped safely."
            exit 0
          else
            echo "Mandatory CI checks failed."
            exit 1
          fi
```

### 7.3 Advanced Configuration: `.github/CODEOWNERS`

```text
# Aturan Kepemilikan Kode Enterprise
# Sintaks: [path] [pemilik yang wajib approve]

# Global Fallback (Platform Core Team)
*                   @enterprise-org/core-architects

# Backend Services
/services/payment/  @enterprise-org/payment-reviewers @enterprise-org/sec-ops
/services/auth/     @enterprise-org/security-reviewers

# Infrastructure as Code
/terraform/         @enterprise-org/sre-team
/k8s/               @enterprise-org/sre-team

# Architecture Decision Records
/docs/adr/          @enterprise-org/principal-engineers
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Monolith E-Commerce Skala 800+ Engineer
*   **Konteks**: Sebuah perusahaan decacorn mengelola satu repository monolitik skala besar (mono-backend) yang ditulis dalam Go dan Java, dilayani oleh ~800 engineer aktif.
*   **Gejala Masalah**:
    *   Setiap hari terjadi 350-500 PR yang berstatus *ready to merge*.
    *   Trunk `main` rusak (*build failed*) rata-rata 8 kali per hari karena *semantic race conditions*.
    *   CI full-suite memakan waktu 25 menit.
    *   Developer mengalami *rebase starvation*: setelah merge gagal, cabang mereka harus di-rebase ulang, memicu CI 25 menit lagi, sementara developer lain sudah mendahului merge. Biaya komputasi CI membengkak drastis.
*   **Solusi Arsitektural**:
    1.  **Implements Optimistic Merge Train Engine**: Mengadopsi sistem merge queue dengan ukuran paralel batch = 5.
    2.  **Optimistic Speculative Batching**: Antrean memvalidasi hingga 5 PR dalam satu DAG terprediksi. Jika batch gagal, algoritma otomatis bisection (binary search) membagi batch menjadi sub-antrean untuk mengisolasi commit yang korup secara otomatis.
    3.  **Path-Based Dynamic CI Execution**: Menggunakan distributed caching (Bazel/Nx) sehingga pengujian hanya dieksekusi pada paket AST yang terdampak langsung dan dependensi hilirnya (*downstream dependencies*).
    4.  **Enforce Strict "Squash and Merge" with Conventional Commits**: Membersihkan histori monorepo dan mempermudah auto-revert atomik jika ditemukan *silent defect* di lingkungan produksi.
*   **Hasil**:
    *   Frekuensi *broken trunk* turun menjadi **0 kejadian per bulan**.
    *   Throughput deployment meningkat dari 45 PR/hari menjadi **280+ PR/hari**.
    *   Waktu tunggu rata-rata seorang engineer dari status *approved* ke *merged* berkurang sebesar 68%.

---

## 9. Trade-offs: Analisis Strategi Integrasi Cabang

Tabel komparasi komprehensif antara strategi integrasi Git pada skala enterprise:

| Dimensi Arsitektural | 3-Way Merge (`--no-ff`) | Rebase & Fast-Forward | Squash and Merge |
| :--- | :--- | :--- | :--- |
| **Bentuk Commit DAG** | Non-linear, graf multi-parent bercabang banyak | Linear absolut (1 dimensi vertikal) | Linear absolut (1 dimensi vertikal) |
| **Preservasi Histori Asli** | 100% utuh (seluruh commit mikro tersimpan) | Utuh, namun hash commit & timestamp bermutasi | Nol. Semua commit mikro digulung menjadi satu |
| **Bisectability (`git bisect`)** | **Buruk**: Dapat mendarat di commit intermediate PR yang rusak | **Tinggi**: Setiap commit individual dapat diuji | **Sangat Baik**: Setiap commit di `main` setara dengan 1 PR utuh yang tervalidasi CI |
| **Reversibilitas Produksi** | Sulit: Membutuhkan `git revert -m 1 <commit-hash>` | Sedang: Harus me-revert rentang commit individual | **Sangat Mudah**: Cukup `git revert <single-squash-sha>` |
| **Auditability Konteks PR** | Tinggi (terikat langsung dengan merge commit ID) | Rendah (kehilangan jejak batch PR tanpa git-reflog forge) | Sangat Tinggi jika pesan squash mencantumkan nomor PR (mis: `#1024`) |
| **Kompleksitas Resolusi Konflik**| Diselesaikan sekali di akhir pada saat commit merge | Diselesaikan iteratif untuk setiap commit yang di-rebase | Diselesaikan sekali pada saat penggabungan tree |
| **Rekomendasi Skala Enterprise** | Microservices independen / Open Source repos | Tim kecil dengan standar commit hygiene sangat tinggi | **Monorepo Enterprise / Tim Skala Besar** |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Silent Merge Race Condition (Git Phantom Commit)
*   **Masalah**: Cabang PR tidak konflik dengan target `main`, tetapi hasil merge menghasilkan dependensi runtime yang tidak valid.
*   **Troubleshooting**:
    1.  Cek referensi tersembunyi forge: `git fetch origin refs/pull/[PR_ID]/merge:pr-merge-eval`.
    2.  Pindah ke ref tersebut: `git checkout pr-merge-eval`.
    3.  Eksekusi compiler/linter lokal untuk membuktikan cacat semantik sebelum merge dilakukan:
        ```bash
        go test -v ./...
        ```
    4.  Terapkan proteksi: Aktifkan **Merge Queue** atau setel GitHub setting: *"Require branches to be up to date before merging"*.

### 10.2 Contention Lock pada File `.git/refs/heads/main.lock`
*   **Masalah**: Runner CI/CD yang mengeksekusi merge paralel lokal ke remote bare repository mengalami kegagalan: `fatal: Unable to create '.../.git/refs/heads/main.lock': File exists`.
*   **Penyebab**: Lebih dari satu proses mencoba memutasi pointer HEAD trunk pada waktu mikrodetik yang sama.
*   **Solusi**:
    *   Terapkan mekanisme antrean merge terpusat (Merge Queue) agar pembaruan pointer `refs/heads/main` diatur secara serial (`pessimistic lock` di tingkat API forge).

### 10.3 Kehilangan Jejak Audit Akibat Force Push yang Ceroboh
*   **Masalah**: Developer menggunakan `git push --force` setelah melakukan rebase lokal, menimpa commit review yang sudah disetujui reviewer lain.
*   **Troubleshooting & Mitigasi**:
    *   Larang secara keras `git push --force` pada enterprise branch protection rule.
    *   Gunakan hanya `git push --force-with-lease`. Opsi ini memvalidasi bahwa referensi remote belum diubah oleh pihak ketiga sebelum commit lokal menimpanya.
    *   Lacak histori commit lama yang hilang menggunakan reflog pada mesin developer:
        ```bash
        git reflog show origin/feature-branch
        git reset --hard origin/feature-branch@{1}
        ```

---

## 11. Best Practices (Production Checklist)

### Checklist Konfigurasi Repository Enterprise:
- [ ] **Linear History Enforced**: Aktifkan *"Require linear history"* untuk mencegah merge commit redundant di repository trunk.
- [ ] **Strict Branch Protection Rules**:
    - [ ] `main` atau `master` dilindungi dari direct push.
    - [ ] Minimal 2 persetujuan (*approvals*) dari peer reviewers.
    - [ ] Perubahan file kritis (`/infra`, `/auth`, `billing`) wajib mendapatkan sign-off eksplisit dari `CODEOWNERS`.
    - [ ] Aktifkan opsi: *"Dismiss stale pull request approvals when new commits are pushed"*.
- [ ] **Automated Context Checking**:
    - [ ] Enforce Conventional Commits linter pada judul PR.
    - [ ] Enforce tautan Issue Tracker (Jira, Linear, GitHub Issues) di deskripsi PR via regex automation.
- [ ] **Automated Housekeeping**:
    - [ ] Aktifkan *"Automatically delete head branches"* setelah PR sukses dimerge.
- [ ] **Merge Queue Configuration**:
    - [ ] Aktifkan Merge Queue untuk repository dengan aktivitas > 50 PR/hari.
    - [ ] Tentukan batas *merge method* hanya menggunakan **Squash and Merge** atau **Rebase and Fast-Forward**.
- [ ] **CI Pipeline Isolation**:
    - [ ] Pisahkan pipeline *quick check* (linter, unit tests: target execution < 3 menit) dari pipeline *deep validation* (E2E, dynamic security testing, integration test: target execution < 15 menit).

---

## 12. Hands-on Practice: Simulasi Mesin Merge Queue Mini Menggunakan Shell Script

Kita akan membangun prototipe sistem Merge Queue lokal di folder `hands-on/m02/` yang memverifikasi dua cabang PR yang bersaing, mendeteksi konflik build semantik, dan memajukan trunk secara deterministik.

### Langkah 1: Persiapan Lingkungan Hands-on

```bash
mkdir -p hands-on/m02
cd hands-on/m02
rm -rf test-repo merge-queue-runtime
mkdir test-repo
cd test-repo

git init -b main
git config user.name "Platform Bot"
git config user.email "bot@platform.internal"

# Inisialisasi Project Go Mini
cat << 'EOF' > go.mod
module enterprise.internal/mqdemo

go 1.22
EOF

cat << 'EOF' > service.go
package main

import "fmt"

func ProcessOrder(id int) string {
    return fmt.Sprintf("Order-%d", id)
}

func main() {
    println(ProcessOrder(101))
}
EOF

git add .
git commit -m "chore: initial service commit"
```

### Langkah 2: Buat Cabang Persaingan (Simulasi 2 Developer Buka PR Bersamaan)

```bash
# PR 1: Mengubah Signature ProcessOrder (menambahkan parameter context)
git checkout -b feature-pr-1
cat << 'EOF' > service.go
package main

import "fmt"

// ProcessOrder sekarang butuh prefix string
func ProcessOrder(id int, prefix string) string {
    return fmt.Sprintf("%s: Order-%d", prefix, id)
}

func main() {
    println(ProcessOrder(101, "ORD"))
}
EOF
git add service.go
git commit -m "feat(pr-1): update signature ProcessOrder with prefix"

# PR 2: Menambahkan method baru di file lain yang memanggil ProcessOrder versi lama
git checkout main
git checkout -b feature-pr-2
cat << 'EOF' > reporter.go
package main

func GenerateReport() string {
    // Memanggil signature lama!
    return ProcessOrder(999)
}
EOF
git add reporter.go
git commit -m "feat(pr-2): add reporting function utilizing ProcessOrder"
```

### Langkah 3: Bangun Skrip Worker Merge Queue Engine

Simpan skrip berikut dengan nama `hands-on/m02/merge_queue_worker.sh`:

```bash
#!/usr/bin/env bash
set -eo pipefail

TRUNK="main"
QUEUE=("feature-pr-1" "feature-pr-2")

echo "=========================================="
echo "    STARTING ENTERPRISE MERGE QUEUE ENGINE"
echo "=========================================="

# Pastikan berada di root repo
cd "$(dirname "$0")/test-repo"

for pr in "${QUEUE[@]}"; do
    echo ""
    echo ">>> [QUEUE WORKER] Memproses Antrean: $pr"
    
    # Buat branch isolasi spekulatif dari target trunk terkini
    SPECVIEW="mq-speculative-eval"
    git checkout -B "$SPECVIEW" "$TRUNK"
    
    # Coba merge PR ke branch isolasi
    echo ">>> [QUEUE WORKER] Menjalankan 3-Way Merge Spekulatif..."
    if ! git merge --no-ff "$pr" -m "merge-speculative: evaluate $pr"; then
        echo "!!! [CRITICAL] Syntax Git Conflict terdeteksi pada $pr. Ejeksi dari antrean!"
        git merge --abort
        continue
    fi
    
    # Jalankan Semantic Compilation Verification (Gatekeeper)
    echo ">>> [QUEUE WORKER] Menjalankan Semantic Validation (go build)..."
    if go build ./... > /dev/null 2>&1; then
        echo ">>> [PASSED] $pr lolos validasi integrasi semantik!"
        
        # Majukan branch trunk secara fast-forward ke hasil evaluasi yang sukses
        git checkout "$TRUNK"
        git merge --ff-only "$SPECVIEW"
        echo ">>> [SUCCESS] $TRUNK berhasil dimajukan ke state baru dari $pr!"
        
        # Hapus temporary evaluation branch
        git branch -D "$SPECVIEW"
    else
        echo "!!! [EJECTED] Semantic Race Condition Terdeteksi! Kode gagal dikompilasi pada $pr."
        echo "!!! Pipeline build output:"
        go build ./... || true
        
        # Bersihkan workspace dan buang evaluasi spekulatif
        git checkout "$TRUNK"
        git branch -D "$SPECVIEW"
        echo ">>> [RECOVERY] $pr berhasil didepak. Branch $TRUNK tetap aman dan bersih!"
    fi
done

echo ""
echo "=========================================="
echo "    HASIL AKHIR TRUNK LOG ($TRUNK)"
echo "=========================================="
git log --oneline --graph
```

### Langkah 4: Eksekusi dan Amati Hasil

Jalankan skrip:
```bash
chmod +x ../merge_queue_worker.sh
../merge_queue_worker.sh
```

**Hasil Ekspektasi**:
*   `feature-pr-1` akan berhasil diuji dan dimerge ke `main`.
*   `feature-pr-2` berhasil dimerge secara sintaksis Git (karena beda file), namun **gagal pada fase `go build`** karena ketidakcocokan argumen fungsi `ProcessOrder`.
*   Engine Merge Queue secara otomatis mendepak `feature-pr-2`, menjaga cabang `main` tetap hijau (*green build*).

---

## 13. Exercises

### Level Easy
Tuliskan satu baris perintah Git CLI (`git log`) dengan format khusus yang menampilkan grafik commit DAG lengkap, hash terkompresi (7 karakter), author date, author name, dan commit subject dalam representasi topological order untuk seluruh cabang referensi.
*   **Target Output**: Representasi graf visual terminal yang mudah dibaca saat troubleshooting percabangan PR.

### Level Medium
Buat sebuah script shell `git-audit-pr.sh` yang menerima input satu hash commit merge di branch `main`, kemudian mengekstrak:
1.  Parent SHA-1 pertama dan parent SHA-2 kedua.
2.  Daftar seluruh file yang diubah eksklusif di dalam PR tersebut.
3.  Apakah commit tersebut berstatus fast-forward, true 3-way merge, atau squash commit.

### Level Hard
Rancang deklarasi arsitektur GitHub Actions Workflow matrix yang dinamis:
Repository monorepo berisi 3 service: `/auth`, `/billing`, `/notification`.
Workflow harus:
1.  Mendeteksi service mana yang diubah pada PR.
2.  Memicu job test hanya untuk service yang disentuh.
3.  Namun, jika PR menyentuh folder `/shared-kernel`, **seluruh ketiga service wajib diuji secara paralel**.
4.  Gunakan hanya satu status check akhir bernama `enterprise-ci-gate` yang wajib berwarna hijau agar PR dapat dimerge.

---

## 14. Challenge: Arsitektur Monorepo Distributed Merge Train

### Deskripsi Masalah
Perusahaan Anda memiliki monorepo skala ultra-besar dengan metrik operasional sebagai berikut:
*   **Jumlah Active Engineer**: 1.500 engineers.
*   **Frekuensi PR**: Rata-rata 1.200 PR per hari kerja.
*   **Durasi Full E2E & Smoke Test Suite**: 45 menit jika dijalankan secara penuh tanpa filter.
*   **Kapasitas Runner CI**: Maksimum 200 runner paralel berbiaya tinggi.

Saat ini tim mengalami degradasi ekstrem: jika merge queue dijalankan secara murni sekuensial (1 demi 1), antrean membutuhkan waktu $1.200 \times 45\text{ menit} = 54.000\text{ menit}$ (tidak mungkin selesai dalam 24 jam). Jika dijalankan spekulatif murni 5 batch, satu PR yang gagal di awal batch merusak seluruh komputasi batch berikutnya, membuang ribuan dolar compute cost per hari.

### Tugas Desain Anda
Rancang dokumen arsitektur komprehensif sistem **Predictive Distributed Merge Train** internal perusahaan yang menyelesaikan masalah throughput ini. Dokumen arsitektur harus memaparkan:
1.  **Dependency Graph & Impact Analysis Engine**: Bagaimana monorepo diuraikan ke dalam DAG paket menggunakan caching pintar (misal: analisis dependensi via Bazel/Turborepo) sehingga E2E test yang dieksekusi hanya subset absolut.
2.  **Antrean Partisi Independen (Partitioned Queues)**: Bagaimana arsitektur mengelompokkan PR ke antrean yang berjalan paralel secara concurrent jika PR-PR tersebut terbukti 100% *disjoint* (tidak memiliki overlap dependency graph).
3.  **Algoritma Isolasi Kegagalan (Failure Bisection Algorithm)**: Spesifikasikan pseudocode/langkah state-machine untuk mengisolasi commit yang rusak jika sebuah batch gabungan PR mengalami kegagalan CI.
4.  **Cost Optimization & CI Throttling Policy**: Strategi penanganan jika kapasitas runner mencapai limit maksimal (backpressure mechanism).

---

## 15. Quiz Evaluasi Pemahaman

### 15.1 Bagian 1: Basic (Pilihan Ganda)

1. **Objek Git manakah yang menyimpan informasi nama berkas dan perizinan mode UNIX?**
   * A. Commit Object
   * B. Blob Object
   * C. Tree Object
   * D. Tag Object
   * *Jawaban yang Benar*: C
   * *Penjelasan*: Objek Blob hanya menyimpan byte payload mentah berkas tanpa metadata. Objek Tree bertanggung jawab memetakan nama file, izin eksekusi UNIX (100644, 100755), dan hash Blob atau sub-Tree terkait.

2. **Apa yang terjadi secara internal pada Git DAG saat perintah Fast-Forward merge dijalankan?**
   * A. Sebuah commit baru dengan dua parent dibuat secara otomatis.
   * B. Pointer referensi target branch hanya dimajukan (*moved forward*) ke commit tip cabang yang dimerge tanpa membuat commit baru.
   * C. Riwayat commit lama dihapus dan ditulis ulang menggunakan hash SHA-256 baru.
   * D. Staging index dibersihkan dan git reflog dinonaktifkan.
   * *Jawaban yang Benar*: B
   * *Penjelasan*: Fast-Forward merge hanya dapat terjadi jika tidak ada percabangan divergen pada target branch. Git cukup memajukan pointer branch ke commit SHA paling ujung dari branch fitur.

3. **Algoritma merge engine default yang digunakan oleh Git versi modern (v2.33+) untuk menggantikan recursive engine adalah:**
   * A. octopus
   * B. resolve
   * C. ort
   * D. subtree
   * *Jawaban yang Benar*: C
   * *Penjelasan*: Engine `ort` (*Ostensibly Recursive's Twin*) ditulis ulang untuk mengatasi masalah performa dan kebenaran (*correctness*) logika rebase dan merge pada Git modern, menggantikan algoritma recursive lama.

4. **Bagaimana format representasi referensi Git untuk sebuah Pull Request nomor 42 yang dibuka di platform GitHub?**
   * A. `refs/heads/pr/42`
   * B. `refs/pull/42/head`
   * C. `refs/remotes/pr-42`
   * D. `refs/tags/pull-request-42`
   * *Jawaban yang Benar*: B
   * *Penjelasan*: GitHub mengekspos commit ujung dari sebuah PR pada namespace `refs/pull/[ID]/head`, dan commit merge spekulatifnya di `refs/pull/[ID]/merge`.

5. **Apa fungsi utama dari konfigurasi flag `cancel-in-progress: true` pada concurrency group di GitHub Actions?**
   * A. Menghapus commit yang rusak secara otomatis dari remote repository.
   * B. Membatalkan antrean merge jika ada reviewer yang memberikan status Reject.
   * C. Menghentikan workflow CI yang sedang berjalan pada PR yang sama jika developer melakukan push commit baru, guna menghemat biaya komputasi runner.
   * D. Mengabaikan file besar agar tidak diunggah ke storage artefak.
   * *Jawaban yang Benar*: C
   * *Penjelasan*: Pengembang yang melakukan push berulang kali pada PR yang sama tidak perlu menunggu CI lama selesai. Job lama dibatalkan untuk segera menguji commit SHA yang paling baru.

---

### 15.2 Bagian 2: Intermediate (Pilihan Ganda & Analisis Kasus)

6. **Mengapa strategi "Squash and Merge" sangat disukai oleh arsitek monorepo enterprise dibanding "3-Way True Merge", terlepas dari hilangnya granularitas commit individual?**
   * A. Karena Squash and Merge tidak memerlukan runner CI untuk validasi.
   * B. Karena membatasi histori branch utama menjadi 1 commit per PR, sehingga operasi `git revert` dan pelacakan `git bisect` bersifat deterministik dan atomik jika terjadi insiden produksi.
   * C. Karena Squash and Merge menghapus keharusan file CODEOWNERS.
   * D. Karena Squash and Merge mencegah developer membuat branch lokal baru.
   * *Jawaban yang Benar*: B
   * *Penjelasan*: Pada monorepo dengan ratusan tim, commit mikro (seperti: "fix typo", "wip") yang rusak di tengah branch fitur akan mematahkan eksekusi `git bisect`. Dengan Squash, satu commit di main merepresentasikan satu unit fitur yang utuh dan mudah di-revert secara instan.

7. **Kapan kondisi "Rebase Starvation" terjadi pada tim pengembang yang menerapkan policy PR ketat?**
   * A. Ketika kapasitas disk pada server Git Forge penuh mencapai 100%.
   * B. Ketika antrean PR terlalu panjang dan aturan "Require branch to be up to date before merging" diaktifkan tanpa sistem Merge Queue, sehingga setiap kali branch `main` terisi, PR lain ter-invalidasi dan harus di-rebase ulang.
   * C. Ketika reviewer menolak PR tanpa memberikan komentar deskriptif.
   * D. Ketika token autentikasi Git developer mengalami kedaluwarsa secara masal.
   * *Jawaban yang Benar*: B
   * *Penjelasan*: Developer terjebak dalam lingkaran setan me-rebase branch, menunggu CI selesai, namun sebelum sempat klik merge, PR developer lain telah masuk ke `main`, membatalkan status up-to-date dan memaksa rebase ulang tiada henti.

8. **Perhatikan skenario command berikut pada branch lokal:**
   ```bash
   git checkout main
   git merge --squash feature-branch
   git commit -m "feat: squash integration"
   ```
   **Berapa banyak Parent Commit SHA yang dimiliki oleh commit baru yang terbentuk di branch `main` tersebut?**
   * A. Dua parent (commit terakhir `main` dan commit terakhir `feature-branch`).
   * B. Sebanyak jumlah commit yang ada di dalam `feature-branch`.
   * C. Tepat satu parent (commit terakhir `main` sebelum proses squash dijalankan).
   * D. Nol parent, karena commit squash adalah root commit baru.
   * *Jawaban yang Benar*: C
   * *Penjelasan*: Perintah `git merge --squash` hanya mengambil perubahan state working tree dan staging index dari cabang target tanpa membawa pointer riwayat parent branch target. Commit baru yang dihasilkan hanya memiliki 1 parent (HEAD `main` sebelumnya).

9. **Apa perbedaan teknis mendasar antara `git push --force` dan `git push --force-with-lease`?**
   * A. `--force-with-lease` melakukan enkripsi TLS ganda saat transfer objek.
   * B. `--force-with-lease` menolak menimpa remote branch jika referensi remote ref telah diperbarui oleh orang lain yang belum di-fetch ke lokal repository kita, mencegah hilangnya pekerjaan rekan kerja secara tidak sengaja.
   * C. `--force` hanya bekerja pada tag, sedangkan `--force-with-lease` bekerja pada branch.
   * D. `--force-with-lease` otomatis membuat merge commit cadangan di server.
   * *Jawaban yang Benar*: B
   * *Penjelasan*: `--force-with-lease` adalah bentuk defensif dari force push. Perintah ini memeriksa apakah pointer remote-tracking branch lokal sama dengan pointer aktual di remote forge. Jika ada orang lain yang melakukan push commit baru, operasi force ditolak.

10. **Dalam arsitektur pipeline CI modern, mengapa pattern "Gatekeeper Status Check" (menggunakan job agregasi akhir dengan kriteria `if: always()`) dianggap sebagai best practice?**
    * A. Menghindari developer membayar tagihan infrastruktur CI.
    * B. Mengizinkan satu status check statis di Branch Protection Rule meskipun matriks job testing di baliknya bersifat dinamis (dapat di-skip atau dipecah berdasarkan perubahan file).
    * C. Memastikan pipeline tetap berjalan meskipun server Git Forge sedang offline.
    * D. Memaksa seluruh tes dijalankan tanpa caching.
    * *Jawaban yang Benar*: B
    * *Penjelasan*: Branch Protection Rule Git Forge membutuhkan nama job yang deterministik untuk status check wajib. Jika kita menggunakan dynamic path-filtering (di mana job backend dilewati jika hanya mengedit dokumentasi), job agregator akhir memastikan status check tetap mengirimkan sinyal `success` ke forge.

---

### 15.3 Bagian 3: Skenario Kasus Produksi (Analisis Mendalam)

#### Skenario Kasus 1: "The Ghost PR Outage"
Sebuah tim Core Banking meluncurkan PR #405 yang berisi pembaruan library enkripsi kartu. Review telah disetujui oleh 3 Principal Engineers dan pipeline CI berstatus hijau centang (`passed`). Segera setelah PR #405 di-merge ke branch `main`, pipeline trunk utama tiba-tiba merah (`failed`), dan seluruh rilis produksi terblokir. Saat diinvestigasi, ternyata 5 menit sebelum PR #405 dimerge, PR #401 (dari tim lain) baru saja dimerge ke `main` dan menghapus interface lama yang masih digunakan oleh PR #405.
*   **Pertanyaan**: Mengapa CI PR #405 berstatus hijau sebelum di-merge, dan perubahan arsitektur apa yang menjamin insiden serupa tidak akan pernah terjadi lagi di masa depan?
*   **Rekomendasi Jawaban & Analisis Arsitektur**:
    *   *Akar Masalah*: CI PR #405 dievaluasi terhadap `HEAD` basis commit lama sebelum PR #401 masuk (stale target base commit). Karena perubahan terjadi di file yang berbeda, forge Git tidak melihat adanya konflik sintaks teks, dan mengizinkan merge.
    *   *Solusi Arsitektur*: 
        1. Aktifkan **Merge Queue (Merge Train)**: Memaksa PR #405 digabungkan secara spekulatif di atas PR #401 sebelum masuk ke `main`.
        2. Atau aktifkan opsi branch protection: *"Require branches to be up to date before merging"*, yang secara otomatis mendiskualifikasi centang hijau PR #405 begitu PR #401 masuk, memaksa pengujian ulang terhadap basis commit `main` terbaru.

#### Skenario Kasus 2: "The Billion-Dollar Monorepo Lockup"
Sebuah perusahaan logistik global memiliki monorepo dengan 20.000 folder microservices. Mereka menggunakan antrean sekuensial sederhana di mana setiap PR harus menunggu PR sebelumnya di-merge dan lulus E2E test selama 10 menit. Rata-rata terdapat 60 PR diajukan per jam. Antrean merge menumpuk hingga 400 PR, menyebabkan waktu tunggu merge mencapai lebih dari 40 jam.
*   **Pertanyaan**: Bagaimana Anda merancang arsitektur integrasi cabang baru untuk memangkas waktu tunggu dari 40 jam menjadi di bawah 30 menit tanpa mengorbankan stabilitas trunk?
*   **Rekomendasi Jawaban & Analisis Arsitektur**:
    *   *Langkah 1 (AST Dependency Partitioning)*: Gunakan sparse-checkout & smart build tool (seperti Bazel/Nx). Analisis *affected graph*. PR tim Service A (folder `/services/logistics-routing`) dan PR tim Service B (folder `/services/warehouse-inventory`) yang tidak berbagi dependensi transitif dapat diproses di **Merge Queues Paralel yang Independen**.
    *   *Langkah 2 (Speculative Batching / Merge Trains)*: Terapkan optimasi paralel batch (misal ukuran batch 4-8 PR sekaligus). Jika batch 4 PR lolos validasi bersama, keempat PR dimerge secara instan dalam 1 interval CI (10 menit memproses 4 PR, bukan 40 menit).
    *   *Langkah 3 (Tiered Testing Strategy)*: Pisahkan E2E suite yang lambat menjadi asynchronous synthetic test di staging, batasi validasi merge queue hanya pada *Affected Integration Unit Tests* dan *API Contract Tests* yang dapat selesai dalam waktu < 3 menit.

#### Skenario Kasus 3: "Accidental Secret Leak in Long Commit History"
Seorang junior engineer membuka PR yang terdiri dari 42 commit mikro. Di commit ke-3, engineer tersebut tidak sengaja meletakkan private certificate SSH perusahaan, lalu di commit ke-4 ia menghapus berkas tersebut dan menambahkan file tersebut ke `.gitignore`. PR telah diapprove dan tim menggunakan metode default **Fast-Forward & Rebase** untuk menjaga histori linear.
*   **Pertanyaan**: Apa dampak keamanan jangka panjang dari penggunaan metode Rebase/Fast-Forward pada kasus ini terhadap trunk produksi, dan bagaimana arsitektur proteksi PR seharusnya menangani situasi ini?
*   **Rekomendasi Jawaban & Analisis Arsitektur**:
    *   *Dampak*: Dengan Rebase & Fast-Forward, commit ke-3 tetap masuk ke dalam histori abadi branch `main`. Siapa pun yang memiliki izin read/clone repository di masa depan dapat mengekstrak sertifikat SSH privat tersebut via `git checkout [commit-3-sha]`. Secret tersebut bocor permanen di level DAG.
    *   *Mitigasi & Proteksi*:
        1. **Pre-receive / CI Secret Scanning Hooks**: Pasang tooling seperti `Gitleaks` atau `TruffleHog` pada pipeline PR Gatekeeper untuk menolak PR jika ada commit di dalam rentang PR yang mengandung secret, meskipun secret tersebut telah "dihapus" di commit berikutnya.
        2. **Squash and Merge Policy**: Jika policy menggunakan Squash and Merge, riwayat commit mikro ke-3 dan ke-4 akan digulung menjadi satu tree perubahan akhir di mana file sertifikat tersebut memang tidak pernah ada di snapshot tree akhir. (Meskipun demikian, secret scanning pre-merge tetap wajib untuk mencegah kebocoran di git storage).

---

## 16. Summary

1.  **Git Internals Rule PRs**: Pull Request adalah layer abstraksi platform; stabilitasnya diatur oleh integritas graf DAG (*Directed Acyclic Graph*), pointer objek commit, dan keakuratan mesin penggabungan (*merge engine*).
2.  **Semantic Conflict Overrides Syntax Merge**: Keberhasilan Git melakukan 3-way merge tanpa konflik teks sama sekali tidak menjamin kebenaran runtime program. Broken trunk pada skala enterprise hampir selalu dipicu oleh benturan semantik antar branch yang independen.
3.  **Merge Queues are Mandatory at Scale**: Untuk tim rekayasa skala enterprise (>50 engineer aktif), antrean merge spekulatif (*Merge Trains / Optimistic Merge Queues*) adalah satu-satunya solusi arsitektur yang mengeliminasi fenomena *broken trunk* sekaligus mencegah *rebase starvation*.
4.  **Strategic Branch Merging**: Strategi integrasi (*Squash vs Rebase vs 3-Way*) memiliki trade-off nyata:
    *   *Squash & Merge*: Optimal untuk enterprise monorepo karena menyajikan linearitas mutlak, reversibilitas instan, dan mempermudah auto-bisect.
    *   *3-Way Merge*: Menjaga jejak sejarah historis namun menghasilkan graf DAG yang sangat rumit dan rentan patah saat audit.
5.  **Strict Gatekeeping Automation**: Branch protection kelas produksi modern mengandalkan sinergi antara integrasi `CODEOWNERS`, validasi AST/path-filtering, *semantic PR title enforcement*, dan job agregasi status check yang deterministik.