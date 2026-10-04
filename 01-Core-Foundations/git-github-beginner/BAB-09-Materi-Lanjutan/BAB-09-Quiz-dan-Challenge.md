# BAB 09: Quiz, Challenge, & Knowledge Check
**Tata Kelola Kolaborasi & Keamanan Repositori (Governance & Security)**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **GitHub Rulesets vs. Legacy Branch Protection Rules:**  
   Jelaskan perbedaan arsitektural dan operasional antara konfigurasi *Branch Protection Rules* tradisional dengan *GitHub Rulesets*. Mengapa *Rulesets* dianggap sebagai paradigma tata kelola yang jauh lebih scalable untuk organisasi enterprise dengan ratusan repositori?
2. **Kriptografi Commit Signing (GPG / SSH):**  
   Metadata `author` dan `committer` pada Git dapat dengan mudah dipalsukan menggunakan perintah `git config user.name` dan `user.email`. Jelaskan alur kerja kriptografis di balik *Signed Commits* (menggunakan kunci GPG atau SSH) yang memungkinkan GitHub memberikan label *Verified*, serta risiko keamanan apa yang dimitigasi oleh mekanisme ini.
3. **Mekanisme Parsing & Precedence pada `CODEOWNERS`:**  
   Bagaimana mesin Git/GitHub mengevaluasi berkas `.github/CODEOWNERS` ketika terdapat aturan yang saling tumpang-tindih (*overlapping rules*)? Jelaskan konsep *precedence order* (urutan prioritas) dalam deklarasi pola path dan apa konsekuensinya terhadap penugasan otomatis *mandatory pull request reviewer*.
4. **Kelemahan Revert Commit terhadap Remediasi Insiden Rahasia (*Secret Leaks*):**  
   Ketika seorang pengembang secara tidak sengaja mengekspos API Key produksi ke repositori lalu membuat commit baru berupa `git rm .env && git commit -m "fix: remove secret"`, jelaskan secara teknis (mengacu pada struktur internal Git DAG / Directed Acyclic Graph) mengapa kredensial tersebut tetap berstatus kompromistis (*compromised*) dan dapat diekstraksi oleh aktor ancaman (*threat actor*).
5. **Prinsip *Least Privilege* dalam RBAC GitHub:**  
   Bandingkan tingkatan hak akses bawaan (*base roles*) pada repositori organisasi GitHub: `Read`, `Triage`, `Write`, `Maintain`, dan `Admin`. Dari perspektif mitigasi risiko serangan rantai pasok (*supply chain attack*), mengapa pengembang aplikasi umumnya tidak boleh diberikan hak akses `Maintain` atau `Admin` di repositori utama?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Remediasi Histori Tingkat Lanjut: `git filter-repo` vs. `git filter-branch`:**  
   Mengapa Git secara resmi mendepresiasi `git filter-branch` demi `git filter-repo` untuk membersihkan berkas sensitif dari seluruh histori repositori? Uraikan dampak penulisan ulang histori (*history rewriting*) ini terhadap nilai SHA-1/SHA-256 dari seluruh tree commit downstream, serta bagaimana cara memulihkan sinkronisasi lokal anggota tim lain tanpa menyebabkan *merge back* dari commit yang telah dibersihkan.
2. **Vektor Serangan PR Fork & Eksploitasi GitHub Actions Secrets:**  
   Dalam repositori publik atau antar-departemen, jelaskan perbedaan risiko keamanan antara pemicu alur kerja (*workflow trigger*) `on: pull_request` dan `on: pull_request_target`. Bagaimana seorang penyerang dapat mengeksfiltrasi GitHub Secrets melalui Pull Request dari fork jika alur kerja `pull_request_target` tidak diisolasi dengan benar?
3. **Mekanisme GitHub Push Protection vs. Client-side Pre-commit Hooks:**  
   Jelaskan boundaries pertahanan keamanan saat membandingkan *Secret Scanning Push Protection* bawaan GitHub Enterprise dengan *pre-commit hook* lokal (seperti `trufflehog` atau `gitleaks`). Apa yang terjadi secara internal pada protokol Git ketika GitHub menolak sebuah `git push` karena terdeteksi adanya secret token berformat Shannon entropy tinggi?
4. **Debugging Anomali `CODEOWNERS` Silenct Failure:**  
   Sebuah tim mengonfigurasi baris `@org/core-infra /deployments/` pada berkas `CODEOWNERS`. Namun, saat Pull Request yang memodifikasi berkas `/deployments/production.yaml` dibuat, GitHub sama sekali tidak mewajibkan *approval* dari tim `@org/core-infra`. Analisis tiga akar masalah konfigurasi (*root causes*) yang mungkin menyebabkan aturan ini gagal dieksekusi oleh GitHub PR evaluation engine.
5. **Perilaku Tag Immutability & Signed Releases:**  
   Secara *default*, Git tag (bahkan *annotated tag*) dapat dihapus dan dipindahkan ke referensi commit yang berbeda oleh pengguna dengan hak akses `Write`. Jelaskan bagaimana cara menerapkan *Tag Protection Rules* / *Rulesets* untuk memastikan integritas rilis (*release provenance*), dan jelaskan implikasi keamanan dari pergeseran tag terhadap pipeline continuous deployment (CD).

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Kebocoran Kredensial AWS IAM & Mirror Repository Spillover
Sebuah commit yang berisi AWS IAM Access Key berkemampuan administratif (`AdministratorAccess`) terdorong (*pushed*) ke repositori internal perusahaan pukul 02.15 dini hari. Repositori tersebut memiliki alur kerja CI yang secara otomatis melakukan *mirroring* ke server backup pihak ketiga setiap 10 menit. GitHub Secret Scanning memicu peringatan (*alert*), namun pengembang yang bersangkutan panik dan segera menjalankan perintah `git revert HEAD` lalu melakukan *force push* over-branch.
* **Pertanyaan Diagnostik & Triage:**
  1. Identifikasi kegagalan fatal dalam prosedur mitigasi kepanikan pengembang tersebut. Mengapa `git revert` dan *force push* parsial tidak menghentikan eksploitasi token?
  2. Susun prosedur *Incident Response* langkah-demi-langkah (tahap *Containment*, *Eradication*, dan *Recovery*) yang wajib dilakukan oleh tim Security Operations Center (SOC) dan Engineering Lead dalam 30 menit pertama.

### Skenario B: Rekayasa Identitas Commit & Bypass Audit Trail
Sebuah audit kepatuhan SOC 2 mendapati bahwa terdapat commit berbahaya (*malicious payload*) di branch `main` yang mencantumkan nama dan alamat email dari Chief Technology Officer (CTO) sebagai author. Namun, CTO menyatakan tidak pernah membuat atau menyetujui commit tersebut. Branch `main` memiliki *Branch Protection Rule* yang mewajibkan minimal 1 *Pull Request Approval* sebelum merge, tetapi tidak mewajibkan *Signed Commits*.
* **Pertanyaan Diagnostik & Triage:**
  1. Bagaimana aktor ancaman (yang memiliki akses `Write` ke repositori) secara teknis dapat menyisipkan kode berbahaya tersebut seolah-olah berasal dari CTO dan lolos ke branch `main` tanpa melanggar proteksi PR?
  2. Kebijakan teknis apa saja pada GitHub Governance (minimal 3 konfigurasi spesifik) yang harus segera diaktifkan untuk menutup celah spoofing dan memastikan audit trail yang tidak dapat disangkal (*non-repudiation*)?

### Skenario C: PR Deadlock & Scalability Bottleneck pada Monorepo
Sebuah organisasi rintisan bertumbuh pesat dari 15 insinyur menjadi 200 insinyur dalam satu monorepo. Tim arsitektur mengimplementasikan berkas `CODEOWNERS` yang sangat ketat: setiap folder modul mewajibkan persetujuan dari *Principal Engineer* terkait, dan branch protection memberlakukan *"Dismiss stale pull request approvals when new commits are pushed"* serta *"Require branches to be up to date before merging"*.  
Dampaknya: Rata-rata waktu tunggu merge sebuah PR melonjak dari 2 jam menjadi 4 hari (*deadlock*). Setiap kali seorang engineer meng-*update* branch-nya terhadap `main`, approval sebelumnya ter-reset, sementara Principal Engineers mengalami *review fatigue* ekstrem.
* **Pertanyaan Diagnostik & Triage:**
  1. Analisis *trade-off* antara keamanan/tata kelola ketat vs *developer velocity* pada konfigurasi di atas. Titik mana yang menjadi bottleneck utama?
  2. Rekonstruksi arsitektur tata kelola repositori tersebut menggunakan fitur modern GitHub (misal: Sub-teams, Ruleset bypass allowances, Merge Queue, granular CODEOWNERS) agar repositori tetap aman tanpa mengorbankan siklus rilis.

---

## 4. Chapter Challenge

### Tantangan Praktis: Enterprise Repository Hardening & Incident Remediation Protocol

#### Problem:
Anda ditunjuk sebagai Lead DevSecOps untuk mengamankan repositori `enterprise-payment-gateway` yang baru saja mengalami audit kegagalan tata kelola. Repositori tersebut memiliki riwayat commit di mana berkas konfigurasi dummy berisi *mock secret* terbawa ke branch `main`, tidak ada penegakan identitas kontributor, branch `main` dapat di-*force push* langsung oleh pengembang magang, dan tidak ada pemisahan tanggung jawab pada perubahan arsitektur kritis.

#### Requirements:
1. **Histori Sanitasi:**  
   Gunakan alat bantu modern (`git-filter-repo`) pada repositori lokal simulasi untuk menghapus seluruh jejak riwayat berkas bernama `config/credentials.json` dari semua commit historis tanpa merusak integritas graf commit yang valid.
2. **Implementasi GitHub Rulesets (via UI atau API Payload):**  
   Rancang konfigurasi Ruleset untuk target branch `refs/heads/main` dengan kriteria:
   - Blokir `force push` dan penghapusan branch bagi semua orang (tanpa pengecualian role Admin).
   - Wajibkan *Signed Commits* (semua commit tanpa GPG/SSH verified badge ditolak saat push).
   - Wajibkan minimal 2 Pull Request approvals sebelum merge.
   - Aktifkan opsi *Dismiss stale approvals when new commits are pushed*.
   - Integrasikan *Status Checks* wajib: CI Pipeline harus sukses dan branch harus up-to-date sebelum merge.
3. **Deklarasi Governance via `CODEOWNERS`:**  
   Buat struktur berkas `.github/CODEOWNERS` dengan pembagian hak akses:
   - Semua berkas dokumentasi (`*.md`) dapat disetujui oleh tim `@org/tech-writers`.
   - Modul pembayaran (`/src/payments/`) wajib disetujui secara eksklusif oleh `@org/payment-core`.
   - Modul konfigurasi CI/CD (`.github/workflows/`) hanya boleh diubah dengan persetujuan `@org/security-leads`.
4. **Verifikasi Identitas Lokal (Commit Signing):**  
   Konfigurasikan Git lokal Anda menggunakan kunci SSH atau GPG khusus signing. Pastikan seluruh commit pengujian ditandatangani secara kriptografis (`git log --show-signature` menampilkan status valid).

#### Constraints:
- Dilarang membuat repositori baru secara manual (pembersihan harus dilakukan secara *in-place* pada riwayat repositori yang ada).
- Operasi pembersihan histori tidak boleh meninggalkan dangling commit yang masih dapat diakses via `git checkout <sha>`.
- Ruleset harus dirancang sedemikian rupa agar tidak menimbulkan insiden *merge deadlock* untuk perubahan dokumentasi sederhana.

#### Expected Output:
1. Rekaman log terminal (`git log --oneline --graph --all`) yang membuktikan berkas `credentials.json` telah lenyap secara menyeluruh dari seluruh tree Git.
2. Berkas konfigurasi `.github/CODEOWNERS` yang lolos uji sintaks GitHub.
3. Ekspor format JSON dari GitHub Ruleset yang siap diimpor via GitHub REST API (`PUT /repos/{owner}/{repo}/rulesets`).
4. Tangkapan layar/Log verifikasi terminal dari eksekusi perintah:
   ```bash
   git log --show-signature -n 1
   ```
   yang mengonfirmasi adanya *Good signature* dari public key yang terdaftar.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan fundamental antara model otentikasi identitas commit (Author Metadata) vs verifikasi kriptografis (GPG/SSH Commit Signing).
- [ ] Alur evaluasi GitHub Rulesets berlapis (*inheritance rules*) pada level organisasi vs repositori.
- [ ] Mengapa penghapusan commit di Git lokal tidak menghapus blob data secara permanen dari database internal Git (`.git/objects`) tanpa *garbage collection* (`git gc --prune=now`).
- [ ] Implikasi hukum dan operasional ketika kredensial infrastruktur terekspos pada repositori publik vs privat.
- [ ] Mekanisme kerja *Branch Protection Bypass Allowances* dan batasan penggunaannya pada level kepatuhan industri (misal: SOC 2, PCI-DSS).

### Saya tidak perlu menghafal:
- [ ] Seluruh flag CLI command-line tingkat rendah dari pustaka `git filter-repo` atau Python helper scripts (cukup pahami sintaks umum pembersihan berkas/folder).
- [ ] Struktur internal format representasi JSON dari GitHub Ruleset API schema (cukup pahami parameter esensial dan cara mengekspor/mengimpor via dokumentasi resmi).
- [ ] Algoritma internal hashing SHA-1 vs SHA-256 yang dieksekusi Git saat mengkalkulasi object ID.

### Saya harus bisa melakukan:
- [ ] Mengonfigurasi penandatanganan commit berbasis SSH/GPG di lingkungan lokal dan mengintegrasikannya dengan profil GitHub.
- [ ] Menulis berkas `.github/CODEOWNERS` yang presisi dengan aturan *path matching* yang valid tanpa memicu *wildcard conflicts*.
- [ ] Melakukan sanitasi histori repositori yang terkontaminasi berkas sensitif menggunakan `git-filter-repo` serta mengoordinasikan *force-sync* yang aman kepada tim pengembang.
- [ ] Mengonfigurasi perlindungan branch (*Rulesets*) komprehensif yang menuntut PR approval, passing CI status checks, dan signed commits.
- [ ] Mengonfigurasi dan menginterpretasikan *Secret Scanning Push Protection* serta melakukan audit mitigasi insiden kebocoran kunci secara metodis.