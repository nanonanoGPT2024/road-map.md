# Enterprise Git & GitHub: Architecture, Workflows, and DevSecOps Orchestration

Selamat datang di kurikulum teknis komprehensif **Git & GitHub**. Kurikulum ini dirancang oleh Senior Technical Curriculum Architect untuk mentransformasi pemahaman konseptual dan praktis Anda dari sekadar pengguna perintah dasar (*porcelain consumer*) menjadi arsitek sistem kontrol versi terdistribusi (*distributed version control systems engineer*).

---

## 1. Course Overview & Mindset

### Paradigma: Directed Acyclic Graph (DAG) & Content-Addressable Storage
Mayoritas engineer memperlakukan Git sebagai sistem pencatat riwayat linear berbasis waktu yang membingungkan. Ini adalah model mental yang keliru. Git pada intinya adalah sebuah **Content-Addressable Storage Engine** yang membungkus struktur data **Directed Acyclic Graph (DAG)** menggunakan hashing kriptografis (SHA-1 / SHA-256). Setiap commit, direktori (*tree*), dan file (*blob*) adalah simpul (*node*) yang *immutable* di dalam basis data objek Git.

GitHub, di sisi lain, bukan sekadar peladen *remote backup*; GitHub adalah platform tata kelola kode enterprise, orkestrasi otomasi (GitHub Actions), manajemen kepatuhan (DevSecOps), dan kolaborasi skala besar.

```
       [Working Directory]
               |
        (git add - Staging)
               v
            [Index]
               |
       (git commit - Tree/Blob)
               v
       [Object Database] (.git/objects)
               |
         (git push - DAG)
               v
       [GitHub Enterprise] (Rulesets, CI/CD, Audits)
```

### Sasaran Kompetensi
Setelah menyelesaikan kurikulum ini, Anda akan mampu:
1. Menjelaskan dan memanipulasi *Git plumbing commands* dan struktur internal repositori langsung di level filesystem `.git`.
2. Mendiagnosis dan memperbaiki anomali riwayat Git (merge conflict kompleks, dettached HEAD, history corruption) menggunakan `reflog`, `bisect`, dan *interactive rebase*.
3. Merancang topologi percabangan skala enterprise (*Trunk-Based Development*, *GitFlow*, *GitHub Flow*) yang selaras dengan Continuous Delivery.
4. Mengimplementasikan tata kelola repositori GitHub dengan *Branch Protection Rules*, *Rulesets*, *CODEOWNERS*, dan matriks otorisasi tim.
5. Membangun pipeline CI/CD *enterprise-grade* menggunakan GitHub Actions (reusable workflows, custom composite actions, caching, dan deployment environment).
6. Mengamankan rantai pasok perangkat lunak (*software supply chain security*) menggunakan commit signing (GPG/SSH), CodeQL, Secret Scanning, Push Protection, dan Dependabot.
7. Mengelola repositori skala raksasa (*monorepo*) dengan Git LFS, sparse-checkout, dan partial clone.

---

## 2. Learning Roadmap

```text
git-github-curriculum/
├── BAB 01: Core Architecture & Plumbing vs. Porcelain
│   ├── Modul 1: Content-Addressable Storage & The .git Directory Internals
│   ├── Modul 2: Git Object Model: Blobs, Trees, Commits, and Annotated Tags
│   └── Modul 3: The Index, Hashing (SHA-1/SHA-256), and Object Compression
├── BAB 02: Local Workflow & State Traversal
│   ├── Modul 1: The Three Trees: Working Directory, Index, and HEAD
│   ├── Modul 2: Branch Navigation, Detached HEAD, and Switch/Restore Semantics
│   └── Modul 3: Deep Stash Stack Management and State Isolation
├── BAB 03: Branching Strategies & Merge Topologies
│   ├── Modul 1: Fast-Forward, 3-Way Merge, and Merge Recursive vs. ORT
│   ├── Modul 2: Linear History Architecture: Rebase vs. Merge Trade-offs
│   └── Modul 3: Advanced Surgical Histology: Interactive Rebase & Cherry-Pick
├── BAB 04: History Rewriting, Recovery, and Auditing
│   ├── Modul 1: Non-Destructive Disaster Recovery with Git Reflog
│   ├── Modul 2: The Reset Anatomy: Soft, Mixed, and Hard Mechanics
│   └── Modul 3: Root-Cause Debugging: Binary Search with Git Bisect
├── BAB 05: Remote Collaboration & Distributed Architectures
│   ├── Modul 1: Remote Tracking Mechanics: Fetch, Pull, Push, and Lease Guards
│   ├── Modul 2: Distributed Topologies: Centralized, Integration-Manager, and Dictator
│   └── Modul 3: Nested Architectures: Git Submodules vs. Git Subtree
├── BAB 06: GitHub Platform Engineering & Governance
│   ├── Modul 1: Enterprise Access Control, Teams, and Granular RBAC
│   ├── Modul 2: Repository Rulesets, Branch Protection, and CODEOWNERS
│   └── Modul 3: Audit Log Streaming, Organization Policy, and Compliance
├── BAB 07: Pull Request Workflows & Code Review Mechanics
│   ├── Modul 1: The Anatomy of an Enterprise PR: Drafts, Checks, and Templates
│   ├── Modul 2: PR Merge Policies: Merge Commit, Squash & Merge, or Rebase
│   └── Modul 3: Automated Review Approvals and Branch Deployment Environtments
├── BAB 08: GitHub Actions CI/CD & Automation
│   ├── Modul 1: Workflow Engine: Triggers, Runners, Contexts, and Expressions
│   ├── Modul 2: Reusable Workflows, Composite Actions, and Matrix Builds
│   └── Modul 3: Enterprise Artifacts, Caching, and Deployment Gates
├── BAB 09: Repository Security, Compliance, & Secrets Management
│   ├── Modul 1: Cryptographic Identity: GPG and SSH Commit Verification
│   ├── Modul 2: Secret Scanning, Push Protection, and OpenSSF Scorecards
│   └── Modul 3: Automated Static Analysis with CodeQL and Dependabot Engine
└── BAB 10: Enterprise Scale, Monorepos, & Large Asset Management
    ├── Modul 1: Git LFS (Large File Storage): Pointer Architecture & Locking
    ├── Modul 2: High-Performance Monorepos: Sparse-Checkout and Partial Clones
    └── Modul 3: Enterprise History Sanitization: Git-Filter-Repo and BFG
```

---

## 3. Navigasi Detail Modul Silabus

### [BAB 01: Core Architecture & Plumbing vs. Porcelain](./bab-01-core-architecture/)
Mendedah fondasi sistematis berkas internal Git di balik antarmuka baris perintah standar.
* **[Modul 1: Content-Addressable Storage & The .git Directory Internals](./bab-01-core-architecture/modul-1-git-internals.md)**
  * Bedah anatomi `.git/` (`objects/`, `refs/`, `HEAD`, `config`, `hooks/`).
  * Perbedaan operasional antara *Plumbing commands* (`hash-object`, `cat-file`, `write-tree`) dan *Porcelain commands* (`add`, `commit`, `status`).
* **[Modul 2: Git Object Model: Blobs, Trees, Commits, and Annotated Tags](./bab-01-core-architecture/modul-2-git-object-model.md)**
  * Eksplorasi 4 tipe objek fundamental Git.
  * Dekonstruksi struktur header objek: `type <size>\0<content>`.
  * Perbedaan internal: Lightweight tags vs Annotated tags.
* **[Modul 3: The Index, Hashing (SHA-1/SHA-256), and Object Compression](./bab-01-core-architecture/modul-3-index-and-compression.md)**
  * Mekanisme kerja berkas `.git/index` sebagai *staging area binary*.
  * Hashing kriptografis, deteksi tabrakan SHA-1, dan transisi ke Object Format SHA-256.
  * Kompresi `zlib` pada loose objects dan optimasi ruang penyimpanan dengan Packfiles (`git gc`, `.pack`, `.idx`).

---

### [BAB 02: Local Workflow & State Traversal](./bab-02-local-workflow/)
Manajemen siklus hidup perubahan lokal, navigasi snapshot, dan isolasi state.
* **[Modul 1: The Three Trees: Working Directory, Index, and HEAD](./bab-02-local-workflow/modul-1-the-three-trees.md)**
  * Pelacakan status berkas: *untracked*, *modified*, *staged*, *committed*.
  * Siklus transisi status berkas antar-zona menggunakan `git diff` matrix: Working Directory vs. Index vs. HEAD.
* **[Modul 2: Branch Navigation, Detached HEAD, and Switch/Restore Semantics](./bab-02-local-workflow/modul-2-branch-navigation-detached-head.md)**
  * Konsep pointer HEAD dan anatomi status *Detached HEAD*.
  * Dekomposisi fungsionalitas `git checkout` menjadi perintah modern: `git switch` dan `git restore`.
* **[Modul 3: Deep Stash Stack Management and State Isolation](./bab-02-local-workflow/modul-3-git-stash-internals.md)**
  * Struktur internal `refs/stash` sebagai commit dua atau tiga cabang (Working Directory, Index, Untracked).
  * Manajemen stack stash: `push`, `pop`, `apply`, `branch`, dan flag `--keep-index` / `--include-untracked`.

---

### [BAB 03: Branching Strategies & Merge Topologies](./bab-03-branching-and-merging/)
Topologi percabangan tingkat lanjut, resolusi konflik matematis, dan rekayasa riwayat linear.
* **[Modul 1: Fast-Forward, 3-Way Merge, and Merge Recursive vs. ORT](./bab-03-branching-and-merging/modul-1-merge-topologies.md)**
  * Topologi Fast-Forward vs Non-Fast-Forward (`--no-ff`).
  * Algoritma 3-Way Merge dan identifikasi Common Ancestor (`merge-base`).
  * Analisis performa strategi merge engine: Recursive engine vs Engine ORT (Ostensibly Recursive's Twin).
* **[Modul 2: Linear History Architecture: Rebase vs. Merge Trade-offs](./bab-03-branching-and-merging/modul-2-rebase-vs-merge.md)**
  * Mekanisme transplantasi patch commit menggunakan `git rebase`.
  * Bahaya *The Golden Rule of Rebasing* pada public branches.
  * Trade-off arsitektural: Kepastian kronologis audit (Merge) vs Kebersihan visual log linear (Rebase).
* **[Modul 3: Advanced Surgical Histology: Interactive Rebase & Cherry-Pick](./bab-03-branching-and-merging/modul-3-rebase-interactive-cherry-pick.md)**
  * Modifikasi commit historis via `git rebase -i` (`squash`, `fixup`, `reword`, `edit`, `drop`).
  * Isolasi dan aplikasi selektif commit menggunakan `git cherry-pick` dan penanganan konflik deterministik.

---

### [BAB 04: History Rewriting, Recovery, and Auditing](./bab-04-rewriting-and-recovery/)
Instrumen bedah riwayat Git, teknik forensik data yang hilang, dan pelacakan regresi otomatis.
* **[Modul 1: Non-Destructive Disaster Recovery with Git Reflog](./bab-04-rewriting-and-recovery/modul-1-disaster-recovery-reflog.md)**
  * Arsitektur `.git/logs/`: Referensi lokal terhadap setiap pemindahan pointer HEAD.
  * Prosedur restorasi cabang yang terhapus (*deleted branch*) dan commit yang ter-rebase hard.
* **[Modul 2: The Reset Anatomy: Soft, Mixed, and Hard Mechanics](./bab-04-rewriting-and-recovery/modul-2-reset-deep-dive.md)**
  * Operasi `git reset`: Menggerakkan HEAD (`--soft`), memperbarui Index (`--mixed`), memanipulasi Working Directory (`--hard`).
  * Perbedaan fundamental antara `git reset` (destruktif lokal) dan `git revert` (konstruktif/aman untuk kolaborasi).
* **[Modul 3: Root-Cause Debugging: Binary Search with Git Bisect](./bab-04-rewriting-and-recovery/modul-3-debugging-with-bisect.md)**
  * Algoritma pencarian biner untuk mendeteksi *regression commit*.
  * Otomasi diagnosis menggunakan `git bisect run <test_script.sh>`.

---

### [BAB 05: Remote Collaboration & Distributed Architectures](./bab-05-remote-collaboration/)
Topologi terdistribusi, sinkronisasi jaringan aman, dan manajemen dependensi antar repositori.
* **[Modul 1: Remote Tracking Mechanics: Fetch, Pull, Push, and Lease Guards](./bab-05-remote-collaboration/modul-1-remote-tracking-mechanics.md)**
  * Sinkronisasi referensi: `origin/main` vs `refs/remotes/`.
  * Dekonstruksi `git pull` = `git fetch` + `git merge/rebase`.
  * Protokol push aman: Menghindari *race condition* tim menggunakan flag `--force-with-lease` vs `--force`.
* **[Modul 2: Distributed Topologies: Centralized, Integration-Manager, and Dictator](./bab-05-remote-collaboration/modul-2-distributed-topologies.md)**
  * Arsitektur integrasi kode: Model Forking (Integration-Manager) vs Model Shared Repository.
  * Alur upstream sync dan manajemen multiple remotes (`origin`, `upstream`).
* **[Modul 3: Nested Architectures: Git Submodules vs. Git Subtree](./bab-05-remote-collaboration/modul-3-submodules-vs-subtrees.md)**
  * Submodules: Pelacakan commit SHA spesifik melalui berkas `.gitmodules`.
  * Subtrees: Inklusi langsung struktur direktori eksternal ke dalam satu repositori.
  * Trade-off dependensi, clone recursion (`--recurse-submodules`), dan strategi versioning.

---

### [BAB 06: GitHub Platform Engineering & Governance](./bab-06-github-governance/)
Tata kelola repositori, kontrol akses berbasis peran (RBAC), dan kebijakan kepatuhan enterprise.
* **[Modul 1: Enterprise Access Control, Teams, and Granular RBAC](./bab-06-github-governance/modul-1-enterprise-rbac.md)**
  * Hirarki Organisasi GitHub, Team Sync (IdP/SSO/SAML), dan hak akses granular (Read, Triage, Write, Maintain, Admin).
* **[Modul 2: Repository Rulesets, Branch Protection, and CODEOWNERS](./bab-06-github-governance/modul-2-rulesets-and-codeowners.md)**
  * Penerapan GitHub Rulesets modern vs Legacy Branch Protection Rules.
  * Penegakan review domain spesifik menggunakan berkas `.github/CODEOWNERS` berbasis path wildcard.
* **[Modul 3: Audit Log Streaming, Organization Policy, and Compliance](./bab-06-github-governance/modul-3-audit-and-compliance.md)**
  * Monitoring peristiwa keamanan via GitHub Audit Log API dan streaming ke SIEM (Datadog/Splunk).
  * Konfigurasi IP allowlist, restriksi pembuatan repositori, dan retensi artefak enterprise.

---

### [BAB 07: Pull Request Workflows & Code Review Mechanics](./bab-07-pull-requests/)
Orkestrasi alur integrasi kode, tinjauan kolaboratif bermutu tinggi, dan strategi penggabungan.
* **[Modul 1: The Anatomy of an Enterprise PR: Drafts, Checks, and Templates](./bab-07-pull-requests/modul-1-enterprise-pr-anatomy.md)**
  * Standardisasi kontribusi via `.github/pull_request_template.md`.
  * Lifecycle PR: Draft PR, Required Status Checks, dan integrasi Issue auto-closing keywords.
* **[Modul 2: PR Merge Policies: Merge Commit, Squash & Merge, or Rebase](./bab-07-pull-requests/modul-2-pr-merge-policies.md)**
  * Evaluasi teknis tiga opsi merge GitHub: Create a merge commit, Squash and merge, dan Rebase and merge.
  * Pengelolaan *commit message cleanup* saat proses squash untuk pelacakan Git blame yang bersih.
* **[Modul 3: Automated Review Approvals and Branch Deployment Environments](./bab-07-pull-requests/modul-3-review-approvals-environments.md)**
  * GitHub Environments: Konfigurasi Deployment Protection Rules, Wait Timers, dan Required Reviewers.
  * Alur Branch Deployment dan integrasi ChatOps pada Pull Request.

---

### [BAB 08: GitHub Actions CI/CD & Automation](./bab-08-github-actions/)
Otomatisasi siklus hidup pengiriman perangkat lunak dengan pipeline integrasi terdistribusi.
* **[Modul 1: Workflow Engine: Triggers, Runners, Contexts, and Expressions](./bab-08-github-actions/modul-1-workflow-engine.md)**
  * Event triggers (`push`, `pull_request`, `workflow_dispatch`, `schedule`) dan path-filtering.
  * GitHub-hosted vs Self-hosted Runners: Keamanan, skalabilitas, dan arsitektur eksekusi ephemeral.
* **[Modul 2: Reusable Workflows, Composite Actions, and Matrix Builds](./bab-08-github-actions/modul-2-reusable-workflows-and-matrix.md)**
  * Menghindari duplikasi pipeline melalui Reusable Workflows (`workflow_call`).
  * Membangun Custom Composite Actions untuk abstraksi task internal.
  * Efisiensi pengujian multi-platform dan multi-versi dengan `strategy.matrix`.
* **[Modul 3: Enterprise Artifacts, Caching, and Deployment Gates](./bab-08-github-actions/modul-3-caching-and-deployments.md)**
  * Optimasi kecepatan runner dengan `actions/cache` untuk node_modules, maven, dan pip dependencies.
  * Proteksi release dengan Environments, OpenID Connect (OIDC) integration ke AWS/GCP/Azure tanpa static API keys.

---

### [BAB 09: Repository Security, Compliance, & Secrets Management](./bab-09-security-and-compliance/)
DevSecOps pada rantai pasok perangkat lunak, verifikasi kriptografi, dan deteksi kerentanan otomatis.
* **[Modul 1: Cryptographic Identity: GPG and SSH Commit Verification](./bab-09-security-and-compliance/modul-1-commit-signing.md)**
  * Mencegah pemalsuan identitas committer (*commit author spoofing*).
  * Konfigurasi dan verifikasi signature commit menggunakan kunci GPG dan SSH.
  * Penegakan aturan *Vigilant Mode* dan *Require signed commits* di GitHub.
* **[Modul 2: Secret Scanning, Push Protection, and OpenSSF Scorecards](./bab-09-security-and-compliance/modul-2-secrets-push-protection.md)**
  * Mitigasi kebocoran kredensial dengan GitHub Secret Scanning dan Push Protection bawaan.
  * Penilaian postur keamanan repositori otomatis menggunakan OpenSSF Scorecards.
* **[Modul 3: Automated Static Analysis with CodeQL and Dependabot Engine](./bab-09-security-and-compliance/modul-3-codeql-and-dependabot.md)**
  * Implementasi Static Application Security Testing (SAST) menggunakan CodeQL semantic analysis queries.
  * Manajemen dependensi otomatis: Dependabot Alerts, Security Updates, dan Dependabot Version Updates.

---

### [BAB 10: Enterprise Scale, Monorepos, & Large Asset Management](./bab-10-enterprise-scale/)
Skalabilitas repositori tingkat lanjut untuk basis kode masif dan aset non-teks.
* **[Modul 1: Git LFS (Large File Storage): Pointer Architecture & Locking](./bab-10-enterprise-scale/modul-1-git-lfs.md)**
  * Arsitektur Git LFS: Penggantian biner besar dengan text pointer file dan penyimpanan objek blob terpisah.
  * Manajemen file locking (`git lfs lock`) untuk aset binary yang tidak dapat dimerge (*unmergeable*).
* **[Modul 2: High-Performance Monorepos: Sparse-Checkout and Partial Clones](./bab-10-enterprise-scale/modul-2-monorepos-sparse-checkout.md)**
  * Mengatasi *monorepo bloat* menggunakan Cone Pattern Sparse-Checkout (`git sparse-checkout`).
  * Partial Clones (`git clone --filter=blob:none`) dan optimasi commit-graph untuk percepatan operasi git lokal.
* **[Modul 3: Enterprise History Sanitization: Git-Filter-Repo and BFG](./bab-10-enterprise-scale/modul-3-history-sanitization.md)**
  * Bahaya menghapus kredensial hanya dengan commit baru.
  * Pembersihan permanen riwayat repositori dari data sensitif atau file besar menggunakan `git-filter-repo` (pengganti resmi `git filter-branch`) dan BFG Repo-Cleaner.

---

## 4. Spesifikasi Capstone Project Enterprise

### Judul Proyek:
**"Enterprise Monorepo Migration, DevSecOps Hardening, & Automated Multi-Environment CI/CD Orchestration"**

### 1. Deskripsi Skenario
Perusahaan FinTech enterprise berskala multinasional menghadapi masalah skalabilitas basis kode: terdapat kebocoran kredensial historis pada repositori lawas, ketiadaan standardisasi branching, risiko *author spoofing*, pipeline deploy manual yang rentan human-error, serta integrasi biner aset testing berukuran puluhan gigabyte yang menyebabkan proses cloning lambat.

Tugas Anda adalah bertindak sebagai Lead Platform & DevSecOps Architect yang memimpin restrukturisasi, sanitasi, dan otomasi platform kontrol versi dari ujung ke ujung.

### 2. Persyaratan Arsitektural & Teknis Wajib

#### A. Rekayasa Riwayat & Higienitas Repositori (Git Plumbing & Sanitasi)
1. **Sanitasi Kredensial**:
   * Simulasikan repositori yang memiliki komitmen password dan private key API palsu pada 15 commit ke belakang.
   * Gunakan `git-filter-repo` untuk membersihkan berkas sensitif tersebut secara permanen dari seluruh referensi DAG dan packfiles tanpa merusak integritas riwayat commit fungsional lainnya.
2. **Aset Manajemen Skala Besar**:
   * Konfigurasikan `.gitattributes` untuk melacak file model `.bin`, `.iso`, dan gambar mockup `.psd` menggunakan **Git LFS**.
   * Demonstrasikan penguncian file biner (*file locking*) untuk mencegah race condition tim lintas fungsi.
3. **Monorepo Optimization**:
   * Setup skenario repositori monorepo dengan struktur `/services/order-service`, `/services/payment-service`, dan `/shared/libs`.
   * Tuliskan instruksi operasional untuk developer agar dapat bekerja hanya pada `/services/payment-service` menggunakan `sparse-checkout` dan *blobless partial clone*.

#### B. GitHub Enterprise Governance & Identity Security
1. **Cryptographic Identity Verification**:
   * Buat kunci penandatanganan (GPG atau SSH signing key).
   * Seluruh commit dalam proyek capstone wajib bertatus **Verified** di GitHub.
2. **Branch Protection & Rulesets Architecture**:
   * Konfigurasikan GitHub Ruleset pada branch `main`:
     * Blokir direct push (`--force` dan normal push).
     * Wajibkan Linear History (Rebase atau Squash only).
     * Wajibkan PR review minimal 2 approver dari tim yang didefinisikan dalam `.github/CODEOWNERS`.
     * Wajibkan seluruh status check CI lulus sebelum tombol merge aktif.
     * Wajibkan Signed Commits.

#### C. Enterprise GitHub Actions Pipeline (DevSecOps)
Buat struktur workflow modular di bawah folder `.github/workflows/`:
1. **Workflow 1: Static Code Analysis & DevSecOps Audit (`security.yml`)**:
   * Terpicu saat PR dibuka atau diupdate menuju branch `main`.
   * Menjalankan analisis semantik CodeQL (SAST).
   * Memvalidasi dependensi dengan dependabot scanning dan verifikasi bahwa tidak ada plain-text secrets yang lolos push protection.
2. **Workflow 2: Reusable Multi-Environment Deployment (`deploy.yml`)**:
   * Didesain sebagai *Reusable Workflow* (`workflow_call`) yang menerima parameter `environment` (`staging`, `production`).
   * Menggunakan integrasi GitHub Environment dengan protection rules (Environment `production` membutuhkan approval manual dari tim lead).
   * Menggunakan autentikasi cloud via OIDC (simulasi penukaran token JWT GitHub dengan IAM Role tanpa hardcoded long-lived credentials).

#### D. Simulasi Bencana & Prosedur Disaster Recovery
1. Tuliskan runbook langkah demi langkah untuk merecovery kasus darurat di mana seorang engineer senior secara tidak sengaja menghapus branch rilis penting yang belum dimerge ke `main` dan melakukan `reset --hard` ke state 10 hari yang lalu secara lokal.
2. Buktikan recovery berhasil dilakukan menggunakan referensi `git reflog` dan re-ekspos node commit yang terisolasi (*dangling commit*).

### 3. Deliverables Proyek
* **Repositori GitHub Publik**: Berisi implementasi penuh sesuai spesifikasi di atas dengan branch `main` yang dilindungi.
* **Berkas Konfigurasi**:
  * `.github/CODEOWNERS`
  * `.github/pull_request_template.md`
  * `.github/workflows/security.yml`
  * `.github/workflows/deploy.yml`
  * `.gitattributes` (konfigurasi Git LFS)
* **Dokumentasi Runbook (`RUNBOOK.md`)**: Berisi log audit perintah plumbing yang digunakan saat sanitasi riwayat, bukti penandatanganan commit GPG/SSH, dan panduan disaster recovery via reflog.