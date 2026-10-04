# BAB 06: Quiz, Challenge, & Knowledge Check
**Continuous Integration (CI) Praktis**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Definisi Filosofis vs Implementasi Tooling**  
   Martin Fowler mendefinisikan *Continuous Integration* (CI) sebagai praktik pengembangan perangkat lunak di mana anggota tim mengintegrasikan pekerjaan mereka secara frekuen (biasanya setiap hari per developer), yang diverifikasi oleh *automated build* untuk mendeteksi *integration errors* secepat mungkin. Mengapa mengonfigurasi pipeline otomatis di GitHub Actions atau GitLab CI belum tentu mencerminkan bahwa tim Anda telah menerapkan CI sesungguhnya? Jelaskan kaitannya dengan *long-lived feature branches* vs *Trunk-Based Development*.

2. **Diferensiasi Arsitektur: Build Artifacts vs Pipeline Caching**  
   Jelaskan perbedaan mendasar antara *Artifacts* dan *Cache* dalam eksekusi CI dari perspektif persistensi, konsistensi data (*immutability*), dan tujuan penggunaannya. Berikan contoh skenario konkret di mana penggunaan *cache* untuk menyimpan binary executable hasil kompilasi merupakan anti-pattern fatal.

3. **Komputasi CI: Ephemeral Runners vs Persistent Runners**  
   Bandingkan arsitektur *ephemeral runner* (container/VM yang dimusnahkan setelah satu job selesai) dengan *persistent runner* (host VM/bare-metal yang melayani banyak job secara berurutan). Analisis implikasi keduanya terhadap isolasi keamanan, risiko *state leakage* antar-job, serta biaya *overhead provisioning*.

4. **Desain Pipeline Efisien: Fail-Fast Mechanism dan Ordering Principle**  
   Mengapa penentuan urutan eksekusi *stage* (misal: *Linting/Static Analysis* $\to$ *Unit Testing* $\to$ *Integration Testing* $\to$ *Container Build*) sangat kritikal bagi performa tim dan efisiensi resource compute? Jelaskan konsep *Fail-Fast* dan bagaimana kegagalan di stage awal menghemat *compute-minutes*.

5. **Shift-Left Security dalam CI**  
   Apa yang dimaksud dengan paradigma *Shift-Left* dalam konteks CI, dan bagaimana integrasi SAST (*Static Application Security Testing*) serta SCA (*Software Composition Analysis*) pada level CI memitigasi risiko keamanan dibandingkan pengujian penetrasi (pen-test) di fase akhir rilis?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Investigasi Non-Deterministic Pipeline (Flaky Tests)**  
   Sebuah pipeline CI sesekali gagal pada *stage* unit test dengan `Exit Code 1`, tetapi ketika developer menjalankan ulang test tersebut secara lokal (atau melakukan *re-run* job di CI tanpa perubahan kode), test tersebut berhasil (`Passed`). Bagaimana metodologi sistematis Anda untuk melacak akar masalah apakah ini disebabkan oleh *race condition*, *time-zone/locale dependency*, *unseeded random generator*, atau *port binding collision* di lingkungan paralel runner?

2. **Mekanisme Cache Invalidation dan Determinisme Dependency**  
   Perhatikan key cache berikut: `cache-node-modules-${{ hashFiles('**/package-lock.json') }}`.  
   - Apa yang terjadi di level runner jika developer menambahkan dependency baru tetapi lupa melakukan commit pada file `package-lock.json`?  
   - Bagaimana Anda mendesain struktur *fallback cache keys* (restore keys) agar pipeline tetap dapat memanfaatkan *partial cache* tanpa menyebabkan *poisoning cache* atau *inconsistent state*?

3. **Analisis Insiden: OOMKilled pada Containerized Runner (Exit Code 137)**  
   Job kompilasi Go/Rust atau bundling Webpack pada Kubernetes-based self-hosted runner mendadak mati dengan pesan `Command terminated with exit code 137`.  
   - Bagaimana Anda memverifikasi secara pasti bahwa proses tersebut dihentikan oleh Linux Kernel OOM Killer akibat melanggar `limits.memory` cgroup container runner, bukan karena kehabisan alokasi RAM pada level Kubernetes Node host?  
   - Parameter kernel atau metrik apa yang harus Anda periksa?

4. **Vulnerabilitas Secret Masking & Output Leakage**  
   Sistem CI modern memiliki mekanisme otomatis untuk melakukan *redaction* (*masking*) string secret pada log console. Jelaskan skenario teknis di mana mekanisme masking ini dapat gagal dan membocorkan credential bernilai tinggi ke log publik (misalnya melalui format transformasi base64, *partial string splitting*, atau penanganan *multiline secrets*), serta bagaimana cara memitigasinya.

5. **Optimasi Concurrency: Stale Build Cancellation**  
   Seorang developer melakukan 4 kali `git push` berturut-turut ke branch PR yang sama dalam rentang waktu 3 menit. Secara default, sistem CI akan memicu 4 instance pipeline terpisah secara bersamaan.  
   - Bagaimana Anda mengonfigurasi mekanisme *concurrency control* dan *auto-cancel* untuk memastikan hanya commit terbaru yang dieksekusi?  
   - Mengapa mekanisme *auto-cancel* ini berbahaya jika diaplikasikan pada branch utama (`main`/`trunk`)?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Monorepo Build Time Explosion & CI Queue Congestion
Perusahaan Anda memiliki monorepo backend yang terdiri dari 15 microservices (Go, Python, dan Node.js). Setiap kali ada Pull Request dibuka ke branch `main`, pipeline CI memakan waktu 48 menit karena mengeksekusi linting, testing, dan docker build untuk **seluruh** 15 service secara sekuensial. Hal ini menyebabkan antrean pipeline menumpuk hingga 60 antrean PR, menghabiskan kuota compute engine, dan memperlambat throughput tim secara masif.
- **Tugas Anda:** Rancang arsitektur pipeline CI baru untuk menyelesaikan bottleneck ini.
- **Pertanyaan Diagnostik & Solusi:**
  1. Mekanisme Git apa yang dapat digunakan untuk mendeteksi *path change* sehingga hanya service yang kodenya berubah yang diuji dan dibangun?
  2. Bagaimana Anda menyusun topologi pipeline agar pengujian antar service yang terisolasi dapat berjalan secara paralel (*Matrix Strategy / Dynamic DAG*)?
  3. Bagaimana Anda menangani kasus jika ada perubahan pada library bersama (*shared core package*) yang digunakan oleh semua service?

### Skenario B: Race Condition dan Cache Poisoning pada Persistent Runner Shared Volume
Tim infrastruktur memutuskan menggunakan VM Bare-Metal sebagai persistent runner untuk menghemat biaya cloud. Runner tersebut dikonfigurasi untuk menjalankan 4 worker paralel yang berbagi filesystem volume lokal (`/mnt/ci-cache`) untuk menyimpan direktori `.m2` (Maven cache) dan `node_modules`. Setelah seminggu berjalan, build service mulai mengalami *corrupted binary errors*, package checksum mismatch, dan dependensi hilang secara acak.
- **Tugas Anda:** Analisis kegagalan arsitektur dan lakukan pemulihan (*remediation*).
- **Pertanyaan Diagnostik & Solusi:**
  1. Jelaskan mengapa *concurrent write* oleh beberapa worker ke direktori cache yang sama menyebabkan korupsi data (*race condition* pada filesystem level).
  2. Jika tim tetap diwajibkan menggunakan VM persistent tersebut karena keterbatasan anggaran, bagaimana isolasi layer cache harus direkayasa ulang tanpa mengorbankan performa read/write?
  3. Mengapa *cache key immutability* (seperti yang diterapkan pada object storage S3/MinIO) jauh lebih aman daripada shared local mount?

### Skenario C: Arsitektur Keamanan CI: SaaS Runner vs Self-Hosted Private Runner
Aplikasi finansial institusi Anda memiliki regulasi ketat: basis data staging dan cluster Kubernetes staging berada di dalam private VPC tanpa akses publik sama sekali. Pengujian tahap integrasi mengharuskan pipeline CI mengeksekusi query langsung ke database staging sementara. Tim junior menyarankan untuk membuka firewall port database ke IP pool publik GitHub Actions SaaS Runner.
- **Tugas Anda:** Tolak saran tersebut berdasarkan prinsip *Zero Trust* dan berikan arsitektur pengganti yang aman.
- **Pertanyaan Diagnostik & Solusi:**
  1. Mengapa mem-whitelist rentang IP public SaaS runner adalah risiko keamanan kritis (*attack vector*)?
  2. Rancang arsitektur *Self-Hosted Runner* di dalam private VPC Anda: Bagaimana runner berkomunikasi dengan control plane GitHub/GitLab tanpa membutuhkan *inbound ports* yang terbuka dari internet (*outbound-only polling pattern*)?
  3. Bagaimana Anda mencegah developer nakal (*malicious pull request*) mengekstraksi credential internal VPC melalui script berbahaya yang disisipkan di dalam file pipeline YAML PR publik?

---

## 4. Chapter Challenge

### Tantangan Praktis: Perancangan Pipeline CI Zero-Trust Multi-Stage Berperforma Tinggi
Sebagai Senior DevOps Engineer, Anda diminta membangun pipeline CI standar industri untuk REST API berbasis container (Node.js/Go/Python) menggunakan CI provider pilihan Anda (GitHub Actions atau GitLab CI).

#### 1. Problem Statement
Pipeline eksisting lambat (eksekusi >15 menit), rentan terhadap *supply chain attack*, tidak memiliki validasi kode statis, dan membiarkan container image dibangun meskipun unit test gagal. Pipeline juga sering membocorkan kredensial ke log output.

#### 2. Requirements & Execution Stages
Pipeline Anda harus diimplementasikan dalam bentuk declarative pipeline YAML file dengan kriteria teknis berikut:
- **Stage 1: Code Quality & Security (Paralel)**
  - Lakukan linting kode dengan *strict rules* (exit code non-zero jika ada warning kritis).
  - Lakukan SCA (*Software Composition Analysis*) untuk mendeteksi dependensi rentan (CVE) menggunakan Trivy atau Snyk CLI. Batalkan build jika ditemukan kerentanan level `HIGH` atau `CRITICAL`.
- **Stage 2: Automated Testing with Smart Caching**
  - Implementasikan dynamic caching dependensi berbasis hash manifest lockfile (`package-lock.json`, `go.sum`, atau `poetry.lock`).
  - Eksekusi automated unit test dengan coverage minimum 80%. Gagalkan pipeline jika coverage tidak terpenuhi.
- **Stage 3: Secure Container Build & Attestation**
  - Hanya berjalan jika Stage 1 dan Stage 2 sukses (`dependencies/needs`).
  - Bangun container image menggunakan *multi-stage build* untuk meminimalisir attack surface.
  - Pindai container image yang baru dibangun untuk mendeteksi *operating system vulnerabilities* menggunakan Trivy.
  - Tag image secara deterministik menggunakan `git-commit-sha` pendek (bukan `latest`).
- **Stage 4: Artifact Management**
  - Export test coverage report dan vulnerability report sebagai build artifacts yang dapat diunduh (retensi: 7 hari).

#### 3. Constraints
- **Strict Execution Budget:** Seluruh pipeline harus selesai dieksekusi di bawah 4 menit saat cache *warm*, dan di bawah 7 menit saat cache *cold*.
- **Zero Inbound Security:** Runner tidak boleh mengekspos port ingress apa pun.
- **No Plaintext Secrets:** Dilarang keras menaruh credentials/tokens di dalam repository code. Wajib menggunakan secret management native platform CI.

#### 4. Expected Output
1. File konfigurasi pipeline lengkap yang bersih, terdokumentasi, dan siap pakai (misal: `.github/workflows/ci.yml` atau `.gitlab-ci.yml`).
2. Penjelasan arsitektur singkat mengenai alur dependensi antar job (`DAG visualization`).
3. Bukti simulasi kegagalan: Tunjukkan log output ketika SCA mendeteksi dependency berbahaya dan bagaimana pipeline menghentikan stage berikutnya secara elegan (*fail-fast*).

---

## 5. Knowledge Check & Checklist

Gunakan checklist ini untuk mengevaluasi kesiapan teknis Anda sebelum melangkah ke Bab 07 (Continuous Delivery & Deployment).

### Saya harus memahami:
- [ ] Perbedaan esensial antara Continuous Integration, Continuous Delivery, dan Continuous Deployment.
- [ ] Dampak buruk dari *Merge Hell* akibat penggunaan *long-lived branches* dan keunggulan *Trunk-Based Development*.
- [ ] Perbedaan mendasar dalam lifecycle, persistensi, dan konsistensi antara *Cache* dan *Artifact*.
- [ ] Cara kerja Linux containers dan cgroups dalam membatasi resource runner (CPU, Memory limits) serta akar masalah `Exit Code 137 (OOMKilled)`.
- [ ] Arsitektur komunikasi *long-polling* outbound pada Self-Hosted Runners tanpa membuka incoming traffic port.
- [ ] Anatomi serangan *Supply Chain Attack* pada dependensi CI dan mitigasi melalui lockfile verification dan SCA scanning.

### Saya tidak perlu menghafal:
- [ ] Sintaks exact YAML dari setiap vendor CI (setiap platform seperti GitHub Actions, GitLab CI, CircleCI memiliki dokumentasi referensi yang mudah dicari).
- [ ] Daftar lengkap kode CVE dari security scanner.
- [ ] Seluruh flag CLI command dari tools pengujian atau linter; fokuslah pada pemahaman konsep *exit codes* dan *I/O redirection*.

### Saya harus bisa melakukan:
- [ ] Menulis declarative pipeline YAML multi-stage dengan dependensi yang benar (`needs` / `dependencies`).
- [ ] Mengonfigurasi dynamic dependency caching berbasis file hash dengan strategi fallback keys.
- [ ] Melakukan debugging kegagalan CI melalui pembacaan raw execution logs, exit codes, dan cgroup status.
- [ ] Mengintegrasikan security linter dan container image vulnerability scanner (misal: Trivy) ke dalam pipeline CI.
- [ ] Mengisolasi build artifacts sehingga runner stage berikutnya dapat mengonsumsinya secara deterministik dan aman.
- [ ] Menerapkan *concurrency control* untuk membatalkan proses build lama secara otomatis saat commit baru didorong.