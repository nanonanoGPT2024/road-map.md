# BAB 03: Quiz, Challenge, & Knowledge Check
**Branching Strategies & Merge Topologies**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Topologi DAG dan Fast-Forward Merge:**
   Jelaskan secara struktural bagaimana Directed Acyclic Graph (DAG) Git bertransisi saat eksekusi `git merge` dilakukan dalam kondisi *Fast-Forward* dibandingkan dengan *Non-Fast-Forward* (`--no-ff`). Mengapa banyak tim rekayasa perangkat lunak skala enterprise mewajibkan flag `--no-ff` pada integrasi branch fitur ke branch utama, dan apa trade-off topologis dari kebijakan ini terhadap penelusuran riwayat (`git bisect`)?

2. **Mekanisme 3-Way Merge vs Fast-Forward:**
   Uraikan cara kerja algoritma *3-Way Merge*. Komponen apa saja yang dianalisis oleh Git (petunjuk: *base commit*, *ours/current*, *theirs/incoming*), bagaimana Git menentukan Lowest Common Ancestor (LCA), dan apa indikator mutlak bahwa sebuah operasi merge tidak lagi dapat diselesaikan menggunakan mekanisme Fast-Forward?

3. **Rebase vs Merge Topologis:**
   Analisis perbedaan mendasar antara memadukan cabang menggunakan `git merge` versus `git rebase` dari perspektif integritas kriptografis (commit SHA-1/SHA-256) dan mutabilitas riwayat. Kapan sebuah rebase dianggap melanggar *The Golden Rule of Rebasing*, dan apa dampak operasionalnya terhadap developer lain yang bekerja pada cabang yang sama?

4. **Karakteristik Squash Merge dan Dampak Traversal:**
   `git merge --squash` memadatkan seluruh commit dari feature branch menjadi satu commit tunggal di branch target. Jelaskan bagaimana status relasi parent-child pada commit objek baru tersebut di dalam DAG! Mengapa setelah squash merge dilakukan, branch fitur aslinya tidak lagi dikenali sebagai *merged* oleh perintah `git branch --merged`?

5. **Trunk-Based Development vs GitFlow:**
   Bandingkan model topologi percabangan GitFlow dengan Trunk-Based Development (TBD). Evaluasi kedua model tersebut berdasarkan metrik DORA (*Deployment Frequency*, *Lead Time for Changes*, *Mean Time to Recovery*, dan *Change Failure Rate*), serta jelaskan peran *Feature Flags* (*Feature Toggles*) dalam mengeliminasi kebutuhan long-lived feature branches pada TBD.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Criss-Cross Merge dan Algoritma ORT/Recursive:**
   Jelaskan fenomena *criss-cross merge* di mana Git mendeteksi lebih dari satu Lowest Common Ancestor (LCA). Bagaimana strategi merge bawaan Git modern (`ort` – *Ostensibly Recursive's Twin*) menyelesaikan ambiguitas ini dibandingkan strategi legacy (`recursive`), dan bagaimana pohon virtual (*virtual merge base*) dikonstruksi di memori?

2. **Mekanika `git rebase --onto`:**
   Diberikan topologi berikut:
   ```text
   A---B---C (main)
        \
         D---E (feature-parent)
              \
               F---G (feature-child)
   ```
   Tuliskan perintah Git presisi menggunakan flag `--onto` untuk memindahkan *hanya* commit `F` dan `G` langsung ke atas commit `C` di branch `main`, tanpa menyertakan commit `D` dan `E`. Jelaskan bagaimana Git menentukan batas range commit yang diekstraksi dan diterapkan ulang (*replay*).

3. **Arsitektur Internal `git rerere` (Reuse Recorded Resolution):**
   Uraikan alur kerja internal Git ketika fitur `git rerere` diaktifkan:
   - Bagaimana Git membuat *hash fingerprint* dari konteks konflik?
   - Di mana artefak *preimage* dan *postimage* disimpan di dalam direktori `.git/`?
   - Apa risiko potensial dari `git rerere` jika seorang engineer mencatat resolusi konflik yang keliru (*erroneous resolution*) pada rebase berskala besar?

4. **Anatomi Cherry-Pick Collisions pasca Rebase:**
   Seorang engineer melakukan `git cherry-pick <commit-SHA>` dari branch tim lain. Beberapa hari kemudian, branch sumber tersebut di-rebase dan di-merge ke branch utama. Mengapa Git sering kali gagal mengenali patch yang identik ini secara otomatis saat integrasi akhir, memicu konflik palsu (*false conflicts*), dan bagaimana Git `patch-id` digunakan secara internal oleh `git rebase` untuk mendeteksi redundansi commit?

5. **Detached HEAD dan Graph Orphan Isolation:**
   Saat menjalankan `git checkout <commit-SHA>` di tengah-tengah strategi bisect atau debugging merge yang gagal, repositori berada dalam kondisi `Detached HEAD`. Jika seorang engineer secara tidak sengaja membuat commit baru dalam status ini lalu beralih kembali ke branch `main`, jelaskan siklus hidup commit-commit "terisolasi" tersebut. Perintah apa yang dapat melacak dan menyelamatkannya sebelum dieksekusi oleh Garbage Collector (`git gc`)?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Merge Hell pada Monorepo dan False Conflicts
Sebuah monorepo enterprise dengan 300+ insinyur mengimplementasikan branching strategy di mana sebuah tim inti mengerjakan refactor arsitektur modular (`refactor/core-networking`) yang berjalan selama 3 minggu. Di saat bersamaan, ratusan micro-commits dari 20 tim lain telah masuk ke `main`. Ketika tim inti mencoba melakukan `git merge origin/main` ke branch mereka, Git menghasilkan 48 file konflik, mayoritas disebabkan oleh pergeseran direktori massal (*file renames/moves*) yang dilakukan kedua belah pihak.
*   **Pertanyaan Diagnostik & Solusi:**
    1. Konfigurasi heuristik rename Git apa (`merge.renameLimit`, `diff.renames`) yang harus disesuaikan agar engine merge Git tidak menganggap operasi ini sebagai *deletion + creation*, melainkan *rename* yang tepat?
    2. Langkah mitigasi topologis apa yang seharusnya diambil tim inti untuk mencegah akumulasi divergence yang begitu masif, dan mengapa integrasi berkala via *merge upstream* dapat mengotori graph dengan *back-merge noise*?

### Skenario B: Race Condition dan Regresi Senyap (*Silent Regression*) pada CI/CD
Sebuah tim menerapkan GitHub Flow dengan mekanisme *Protected Branches* dan integrasi otomatis via PR. Dua developer (Dev X dan Dev Y) membuat branch terpisah dari commit `HEAD` `main` yang sama (Commit `M0`). 
- Dev X mengubah nama signature sebuah fungsi di service pembayaran pada `feature-x`.
- Dev Y menambahkan pemanggilan baru ke signature fungsi *lama* tersebut pada `feature-y`.
- PR Dev X lolos CI, di-merge ke `main` (menjadi `M1`).
- Dev Y me-retest branch-nya secara lokal (berbasis `M0`), CI-nya valid karena isolated container, lalu PR Dev Y di-merge via *squash-and-merge* ke `main` (menjadi `M2`).
Produksi langsung mengalami *outage* (Compile/Runtime Error) segera setelah `M2` di-deploy, meskipun kedua PR memiliki checklist tes 100% lulus di CI.
*   **Pertanyaan Diagnostik & Solusi:**
    1. Mengapa Git merge engine tidak memunculkan merge conflict pada Commit `M2`?
    2. Mekanisme integrasi modern apa pada tingkat Git hosting (misalnya *GitHub Merge Queue*, *GitLab Train*, atau auto-rebase enforcement) yang secara arsitektural dapat mencegah *semantic conflict / race condition* ini masuk ke `main`?

### Skenario C: Migrasi Regulasi FinTech dari GitFlow ke Trunk-Based
Sebuah institusi perbankan yang terikat regulasi kepatuhan audit SOC2 dan PCI-DSS saat ini menggunakan GitFlow murni dengan branches: `develop`, `release/*`, `hotfix/*`, dan `master`. Release cycle mereka memakan waktu 2 minggu, dengan fase *stabilization* yang sering diwarnai inkonsistensi sinkronisasi commit antara `release/` kembali ke `develop` (cherry-pick drift). Manajemen menuntut percepatan deploy ke staging dari 2 minggu menjadi beberapa kali sehari dengan Trunk-Based Development.
*   **Pertanyaan Diagnostik & Solusi:**
    1. Desainlah strategi transisi topologi Git yang menjamin bahwa jejak audit (*immutable traceability*) terhadap rilis produksi tetap terjaga tanpa menggunakan long-lived `release` branches.
    2. Bagaimana arsitektur *release-from-tag* atau *short-lived release branch* dipadukan dengan *ephemeral environments* untuk menggantikan fungsi `develop` branch secara total?

---

## 4. Chapter Challenge

### Tantangan Praktis: Rekonstruksi Riwayat Rusak dan DAG Splitting (Topological Disaster Recovery)

#### Problem Statement
Tim integrasi Anda baru saja mengalami insiden operasional. Seorang developer junior mencoba menggabungkan branch `feature/auth-v2` ke branch `staging` yang kotor (*dirty staging environment*), lalu secara tidak sengaja me-rebase branch fiturnya di atas staging tersebut. Akibatnya, `feature/auth-v2` sekarang tercemar oleh 40 commit staging yang belum teruji, sementara PR yang harus masuk ke `production` (`main`) *hanya* boleh berisi perubahan murni dari fitur autentikasi. Developer tersebut mencoba memperbaikinya dengan `git merge main` berulang kali, menciptakan topologi *spaghetti* yang tidak dapat di-review.

#### Requirements
1. Lakukan audit pada riwayat repositori untuk mengisolasi commit-commit fungsional milik `feature/auth-v2`.
2. Gunakan teknik *interactive rebase* dan/atau `git rebase --onto` untuk mencangkokkan rentang commit fungsional tersebut ke cabang bersih yang berpangkal tepat dari `origin/main` terbaru.
3. Bersihkan commit history sehingga seluruh commit perbaikan (*fixup/typo/WIP*) terpadatkan secara semantik, menyisakan commit yang mengikuti konvensi *Conventional Commits*.
4. Pastikan branch hasil rekonstruksi memiliki parentage langsung ke `main` tanpa melibatkan commit `staging` mana pun.

#### Constraints
- Dilarang menyalin-tempel (*copy-paste*) kode secara manual di luar Git interface (misalnya membuat folder baru).
- Dilarang menggunakan `git push --force` pada branch shared; Anda harus mendesain branch bersih baru (`feature/auth-v2-reborn`).
- Integritas *commit author* asli dan tanggal pembuatan commit harus dipertahankan semaksimal mungkin (hindari authored date resetting kecuali committer date).

#### Expected Output
1. Log visual topologi DAG sebelum dan sesudah intervensi (menggunakan `git log --graph --oneline --decorate`).
2. Baris perintah Git (*sequence of commands*) presisi yang dieksekusi mulai dari pemetaan hash hingga verifikasi akhir.
3. Bukti eksekusi `git diff origin/main...feature/auth-v2-reborn` yang membuktikan bahwa *zero staging code leaked* ke dalam final tree.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Representasi matematis cabang Git sebagai pointer yang bergerak di atas Directed Acyclic Graph (DAG).
- [ ] Perbedaan matematis dan operasional antara kalkulasi 3-way merge dan fast-forward traversal.
- [ ] Cara kerja strategi merge `recursive` vs `ort` dalam menangani multiple merge bases (*criss-cross merges*).
- [ ] Dampak topologis dan forensik dari `git rebase` terhadap hash commit, reflog, dan timeline audit.
- [ ] Mengapa *Semantic Conflicts* dapat lolos dari deteksi Git Merge Engine dan bagaimana mengatasinya pada level CI/CD.
- [ ] Trade-off arsitektur antara GitFlow, GitHub Flow, dan Trunk-Based Development dalam kaitannya dengan lead time dan delivery performance.

### Saya tidak perlu menghafal:
- [ ] Seluruh flag CLI langka dari `git merge-strategy` (misal: sub-opsi internal dari `git merge -s subtree`).
- [ ] Formula matematis komputasi hash SHA-1/SHA-256 internal Git untuk penamaan objek commit.
- [ ] Sintaks exact dari custom script merge driver pihak ketiga, selama memahami interface exit-code dasarnya (0 = clean, non-zero = conflict).

### Saya harus bisa melakukan:
- [ ] Menavigasi dan membedah DAG kompleks menggunakan format visualisasi terminal tingkat lanjut (`git log --graph --format=...`).
- [ ] Mengeksekusi `git rebase --onto` secara presisi untuk memindahkan sub-tree commit antar branch induk yang berbeda.
- [ ] Mengaktifkan, mengonfigurasi, dan memvalidasi `git rerere` untuk mengotomatisasi penyelesaian konflik berulang.
- [ ] Mengidentifikasi dan memulihkan commit yang hilang atau terisolasi melalui analisis `git reflog`.
- [ ] Merancang arsitektur branch protection rules, merge queues, dan strategi sinkronisasi PR pada Git enterprise server (GitHub/GitLab).