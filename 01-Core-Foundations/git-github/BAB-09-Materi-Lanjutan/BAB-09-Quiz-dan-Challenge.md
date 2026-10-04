# BAB 09: Quiz, Challenge, & Knowledge Check
**Repository Security, Compliance, & Secrets Management**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Integritas Identitas vs Kriptografi: Mengapa Git Author/Committer Header Tidak Menjamin Keaslian (Authenticity)?**  
   Jelaskan secara struktural bagaimana Git menyimpan metadata `author` dan `committer` di dalam objek *commit*, serta mengapa konfigurasi `git config user.name` dan `user.email` dapat dipalsukan secara trivial tanpa memicu error integritas SHA-1/SHA-256. Bagaimana *cryptographic commit signing* (GPG/SSH/S/MIME) menyelesaikan celah validasi ini pada level DAG?

2. **Dilema `.gitignore` sebagai Kontrol Keamanan**  
   Mengapa menambahkan path file sensitif (misalnya `.env` atau `id_rsa`) ke dalam file `.gitignore` setelah file tersebut terlanjur di-track dan di-push ke remote repository adalah tindakan mitigasi yang sepenuhnya tidak efektif? Jelaskan siklus hidup index/staging Git terkait status *tracked* versus *untracked*.

3. **Mekanisme Kerja GitHub Secret Scanning: Push Protection vs Post-Push Detection**  
   Bandingkan arsitektur kerja dan vektor mitigasi antara *Push Protection* (pre-receive hook level) dan *Post-Push Secret Scanning* (asynchronous worker). Mengapa remediator tetap wajib melakukan rotasi token (*token revocation & rotation*) meskipun insiden push commit yang mengandung kredensial langsung ditolak oleh *Push Protection*?

4. **Arsitektur Token Akses: Fine-Grained Personal Access Tokens (PAT) vs Classic PAT**  
   Dari perspektif *principle of least privilege* (PoLP) dan isolasi blast-radius, analisis kelemahan mendasar arsitektur Classic PAT GitHub yang berbasis *coarse-grained scopes*. Bagaimana Fine-Grained PAT mengubah model izin pada level resource (organisasi, repository individual, permission target)?

5. **Prinsip Evaluasi File `CODEOWNERS` dalam Tata Kelola Repository**  
   Bagaimana mesin parser GitHub mengevaluasi aturan dalam file `CODEOWNERS` ketika sebuah file yang dimodifikasi dalam Pull Request cocok (*matches*) dengan beberapa pattern path sekaligus? Apa implikasinya terhadap *branch protection rule* yang mewajibkan *"Require review from Code Owners"* jika urutan deklarasi aturan tidak dikonfigurasi secara presisi?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Anatomi Git Object Scrubbing: Mengapa `git commit --amend` atau `git rm` Gagal Menghapus Rahasia?**  
   Jelaskan mengapa mengeksekusi `git rm --cached secret.json` yang diikuti dengan commit baru tidak menghapus konten file tersebut dari direktori internal `.git/objects/`. Bagaimana cara kerja objek *blob* yang bersifat *immutable* dalam mempertahankan jejak kredensial, dan mengapa kredensial tersebut tetap dapat diakses via commit hash spesifik di web interface GitHub meskipun branch telah ditimpa dengan `git push --force`?

2. **Mechanics of History Rewriting: `git-filter-repo` vs `git filter-branch`**  
   Secara arsitektural dan performa I/O, mengapa `git filter-branch` didepresiasi dan digantikan oleh `git-filter-repo`? Ketika `git-filter-repo --invert-paths --path secret.env` dieksekusi, bagaimana tool ini memodifikasi *tree objects*, *commit hashes*, dan *parent pointers* secara rekursif ke seluruh commit history tanpa merusak integritas *merge commits*?

3. **Vektor Serangan Git Client-Side Hooks Bypass dan Enforcing Controls**  
   Banyak tim mengandalkan *pre-commit hooks* (seperti Husky atau framework pre-commit) untuk memblokir secret leaks. Jelaskan bagaimana developer dapat melewati proteksi ini menggunakan flag `--no-verify` atau manipulasi lingkungan lokal. Mengapa arsitektur keamanan Zero-Trust mewajibkan kontrol validasi dipindahkan ke server-side (misalnya via GitHub Repository Rulesets atau CI workflows) alih-alih hanya bergantung pada client-side hooks?

4. **Federated Identity via GitHub Actions OIDC: Mengeliminasi Long-Lived Cloud Credentials**  
   Uraikan alur *OpenID Connect* (OIDC) *exchange token* antara GitHub Actions runner dan Cloud Provider (seperti AWS STS / GCP Cloud IAM). Data apa saja yang dimuat dalam JSON Web Token (JWT) yang diterbitkan oleh GitHub (`token.actions.githubusercontent.com`), dan bagaimana *trust policy* pada cloud provider memverifikasi *claims* (seperti `sub`, `aud`, `repository`) untuk mencegah eskalasi hak akses antar-repository dalam organisasi yang sama?

5. **Resolusi dan Hierarki Evaluasi GitHub Repository Rulesets**  
   Jika sebuah repository memiliki Branch Protection Rule legacy yang membolehkan bypass bagi tim *DevOps*, namun pada saat yang sama diatur oleh *Enterprise Repository Ruleset* yang memberlakukan *Require linear history* dan *Enforce signed commits* dengan bypass list kosong:  
   Bagaimana GitHub mengevaluasi pertentangan konfigurasi ini? Manakah aturan yang memiliki prioritas lebih tinggi, dan bagaimana model penegakan *defense-in-depth* diterapkan?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Kebocoran Kredensial Produksi Cloud Skala Enterprise
Sebuah tim microservices secara tidak sengaja melakukan push commit yang mengandung file `terraform.tfvars` berisi *Production AWS Master IAM Access Key & Secret Key* ke repository internal GitHub Enterprise Cloud. Repository tersebut di-mirror secara real-time ke staging environment. Dalam waktu 7 menit:
* Security Operations Center (SOC) mendeteksi anomali akses AWS API dari region tak dikenal.
* Developer yang panik mengeksekusi `git revert` pada commit tersebut, lalu melakukan `git push origin main`.
* Developer mengklaim masalah selesai karena file `terraform.tfvars` sudah tidak terlihat lagi di branch `main`.

**Pertanyaan Diagnostik & Forensik:**
1. Buktikan secara teknis mengapa tindakan `git revert` sama sekali tidak menyelesaikan insiden keamanan ini dan justru memperpanjang masa kompromi sistem.
2. Rancang *Immediate Incident Response Playbook* (langkah-langkah darurat menit ke-0 hingga menit ke-60) yang mencakup isolasi kredensial, mitigasi cache GitHub (`/commit/<sha>` dangling reference via GitHub Support / Ghost commits), dan teknik pembersihan repositori menggunakan `git-filter-repo`.

### Skenario B: Race Condition dan Subversi Review pada Supply Chain Integrity
Sebuah organisasi menerapkan *Branch Protection Rule* dengan syarat: *"Require pull request reviews before merging"* (minimal 1 approval) dan *"Dismiss stale pull request approvals when new commits are pushed"*. Namun, seorang adversary internal yang memiliki akses *write* ke repository berhasil melakukan serangan supply chain:
* Adversary membuka Pull Request (PR) berisi modifikasi dokumentasi yang valid dan mendapatkan approval dari reviewer resmi.
* Sebelum menekan tombol merge, adversary memanfaatkan race condition automasi atau memanfaatkan setting repository yang mengizinkan *Squash and Merge* dengan custom commit message/body tanpa verifikasi ulang signature, menyisipkan dependency berbahaya langsung ke dalam manifest package manager.

**Pertanyaan Diagnostik & Forensik:**
1. Lubang konfigurasi spesifik apa pada branch protection / merge policy yang memungkinkan commit/payload yang belum di-review masuk ke default branch?
2. Bagaimana Anda merancang konfigurasi *Repository Rulesets*, *Branch Protection*, dan *CODEOWNERS* untuk memitigasi vektor serangan semacam ini secara deterministik?

### Skenario C: Migrasi Zero-Trust Compliance (SOC 2 Type II / ISO 27001)
Organisasi fintech dengan 450 engineer dan 120 repository microservices sedang diaudit untuk sertifikasi SOC 2 Type II dan ISO 27001. Temuan awal auditor menemukan:
* Sekitar 35% commit pada repository inti tidak memiliki cryptographic signature.
* Penggunaan static *Personal Access Tokens* (Classic) dengan scope `repo` penuh masih masif digunakan pada server automasi legacy Jenkins.
* Developer dapat melakukan force push pada branch fitur yang berujung pada hilangnya audit trail history sebelum merge.

**Pertanyaan Diagnostik & Forensik:**
1. Desain arsitektur governance menyeluruh menggunakan fitur GitHub Enterprise (Rulesets, SSH/GPG Signing Enforcement, Fine-grained PAT, GitHub Apps, dan Audit Log Streaming) yang memenuhi kriteria *non-repudiation*, *least privilege*, dan *tamper-evident audit trail*.
2. Rancang strategi migrasi teknis bertahap (*Zero-Downtime Migration*) bagi para developer tanpa memblokir siklus rilis harian (*deployment velocity*).

---

## 4. Chapter Challenge

### Tantangan Praktis: Full-Lifecycle Secret Remediation & Zero-Trust Enforcement Pipeline

#### Problem Statement
Sebuah repository monorepo fiktif `core-banking-gateway` mengalami insiden kontaminasi rahasia: sebuah commit di masa lalu (`HEAD~5`) memuat file kredensial privat `certs/payment_private_key.pem`. Repositori ini belum memiliki perlindungan branch, commit verification, maupun scan otomatis. Tugas Anda adalah melakukan pembedahan riwayat, membersihkan rahasia secara permanen, dan mengunci repository menggunakan standar enterprise Zero-Trust.

#### Requirements
1. **Repository & Incident Emulation:**
   * Buat sebuah repositori lokal baru dan lakukan minimal 6 commit berurutan.
   * Pada commit ke-2, sertakan file dummy `certs/payment_private_key.pem` berisi text acak private key.
   * Tambahkan commit ke-3 hingga ke-6 yang memodifikasi file lain secara normal untuk menyimulasikan perkembangan riwayat commit.
2. **Deterministic Secret Scrubbing:**
   * Gunakan tool `git-filter-repo` (bukan `git filter-branch`) untuk membersihkan `certs/payment_private_key.pem` dari seluruh commit history.
   * Pastikan tidak ada dangling blob, commit, atau tree di reflog lokal (`.git/logs/`) yang masih merujuk ke private key tersebut.
   * Lakukan garbage collection agresif menggunakan `git gc --prune=now --aggressive`.
3. **Automated Preventive Defense Configuration:**
   * Tulis sebuah konfigurasi hook server-side / pre-receive atau GitHub Actions workflow (`.github/workflows/security-scan.yml`) yang memanfaatkan `gitleaks` atau tool secret scanner sejenis.
   * Scanner harus dijalankan pada setiap event `pull_request` dan `push`, memblokir build (status check: failure) jika mendeteksi signature high-entropy string atau format API Key umum.
4. **Zero-Trust Hardening:**
   * Konfigurasikan penandatanganan commit lokal (*Commit Signing*) menggunakan SSH Key atau GPG Key.
   * Buat file `CODEOWNERS` yang membatasi akses direktori sensitif (`/infra/`, `/security/`) kepada minimal satu tim keamanan khusus.
   * Tulis file dokumentasi audit trail `SECURITY_AUDIT.md` yang memuat bukti komparasi SHA-1 commit sebelum dan sesudah sanitasi, membuktikan integritas riwayat baru.

#### Constraints
* Dilarang membuat repositori baru dari nol untuk menghilangkan file rahasia; history rewriting wajib mempertahankan seluruh log commit non-rahasia dan commit timestamps.
* Penggunaan `git-filter-repo` harus tepat sasaran; tidak boleh menghapus file lain selain path target yang terkontaminasi.
* Workflow scanning tidak boleh mengizinkan bypass flag (`--no-verify` tidak boleh mempengaruhi CI/CD server).

#### Expected Output
1. Output terminal log dari eksekusi `git-filter-repo` dan validasi menggunakan `git log --all --full-history -- "**/payment_private_key.pem"` yang menghasilkan string kosong (file benar-benar terhapus dari seluruh commit DAG).
2. Bukti hash inspection via `git verify-commit` atau `git log --show-signature` yang menunjukkan signature valid pada commit baru.
3. Berkas konfigurasi workflow scanning lengkap (`.github/workflows/security-scan.yml`) yang siap produksi dengan konfigurasi caching signature DB.
4. File `SECURITY_AUDIT.md` ringkas yang mencantumkan analisis forensik insiden, diff tree, dan rekomendasi rotasi kredensial.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Anatomi objek Git (`blob`, `tree`, `commit`, `annotated tag`) dan bagaimana manipulasi history mengubah SHA identifier secara kriptografis (*Merkle Tree cascade effect*).
- [ ] Perbedaan fundamental antara identitas commit (`Author`/`Committer`) dan integritas kriptografis (`GPG`/`SSH`/`S/MIME signatures`).
- [ ] Keterbatasan struktural `.gitignore` terhadap file yang sudah berstatus *tracked* di dalam Git index.
- [ ] Mengapa dangling commit dan cached ref di platform remote (seperti GitHub event cache) tetap berisiko membocorkan kredensial pasca `git push --force`.
- [ ] Arsitektur pertukaran token OIDC (OpenID Connect) untuk autentikasi CI/CD runner ke cloud provider tanpa static secret keys.
- [ ] Hirarki, mekanisme evaluasi, dan model inheritance pada GitHub Repository Rulesets vs Branch Protection Rules legacy.
- [ ] Cara kerja alat bantu rewriting history modern (`git-filter-repo`) dibandingkan tool usang (`git filter-branch`).
- [ ] Mekanisme parsing dan batasan fungsional file `CODEOWNERS`.

### Saya tidak perlu menghafal:
- [ ] Seluruh flag CLI bawaan `gpg` atau variasi flag kompleks OpenSSL untuk pembuatan keypair.
- [ ] Regular Expression (regex) pattern internal yang digunakan oleh secret scanner bawaan GitHub untuk mendeteksi token vendor spesifik.
- [ ] Sintaks JSON payload mentah dari webhook GitHub Enterprise Audit Log.

### Saya harus bisa melakukan:
- [ ] Menemukan dan membersihkan file rahasia yang terlanjur ter-push ke dalam history repositori secara permanen menggunakan `git-filter-repo` dan `git gc`.
- [ ] Mengonfigurasi SSH/GPG Key lokal untuk signing commit dan mendaftarkan public key terkait ke akun GitHub.
- [ ] Mengonfigurasi ruleset branch repository untuk memblokir commit yang tidak ditandatangani kriptografis (*Require signed commits*).
- [ ] Mengimplementasikan *pre-commit framework* atau *Gitleaks* secara lokal dan mengintegrasikannya ke dalam GitHub Actions CI workflow sebagai hard gate.
- [ ] Mengganti static access key pada CI/CD deployment pipeline dengan AWS/GCP/Azure OIDC federated authentication.
- [ ] Melakukan investigasi forensik insiden kebocoran kredensial dengan melacak commit history dan menganalisis GitHub Audit Log events.