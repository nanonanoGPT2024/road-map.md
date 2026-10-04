# BAB 10: Quiz, Challenge, & Knowledge Check
**Otomasi Dasar CI/CD Menggunakan GitHub Actions**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Topologi Eksekusi GitHub Actions:**
   Jelaskan dekomposisi hierarki antara *Workflows*, *Events*, *Jobs*, *Steps*, dan *Actions/Commands*. Bagaimana siklus hidup (*lifecycle*) data dan *filesystem* bertransisi antar *Step* dalam satu *Job*, dibandingkan antar *Job* yang berbeda dalam satu *Workflow*?

2. **Mekanisme Event Dispatching & Trigger Filtering:**
   Bedakan semantik eksekusi antara event `push` dan `pull_request`. Mengapa mendefinisikan branch filter (`branches: [main]`) pada event `pull_request` beroperasi secara fundamental berbeda dengan filter yang sama pada event `push` (khususnya terkait konsep *base branch* vs *head branch*)?

3. **Komputasi Virtual Runner vs Containerized Steps:**
   Ketika Anda mendefinisikan `runs-on: ubuntu-latest`, lingkungan seperti apa yang sebenarnya dialokasikan oleh GitHub? Apa perbedaan mendasar antara mengeksekusi instruksi langsung pada Host VM Runner (`run: npm test`) dibandingkan mengeksekusi instruksi di dalam Docker Container Step (`uses: docker://...` atau deklarasi `container:`)?

4. **Anatomi dan Bahaya Default GITHUB_TOKEN:**
   GitHub secara otomatis menyuntikkan `secrets.GITHUB_TOKEN` ke dalam setiap eksekusi workflow. Jelaskan prinsip *Least Privilege* yang harus diterapkan pada token ini. Mengapa event yang dipicu oleh mutasi Git menggunakan `GITHUB_TOKEN` secara default *tidak* memicu workflow lain secara rekursif?

5. **Prinsip Idempotensi dan Determinisme dalam CI:**
   Mengapa dependensi dependan (*external dependencies*) pada pipeline CI harus dikunci menggunakan *lockfiles* (seperti `package-lock.json`, `poetry.lock`, `Cargo.lock`) dan instalasi divalidasi via perintah *clean install* (seperti `npm ci` bukan `npm install`)? Apa implikasi strukturalnya jika prinsip ini dilanggar pada sistem CI/CD?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **State Persistence vs Artifact Passing:**
   Dua *job* independen (`build` dan `test-e2e`) dideklarasikan dengan relasi `needs: build`. Secara default, mengapa artefak hasil kompilasi dari job `build` tidak otomatis tersedia di workspace job `test-e2e`? Jelaskan mekanisme internal `actions/upload-artifact` dan `actions/download-artifact` dalam menjembatani isolasi antar runner.

2. **Eksploitasi dan Limitasi Secret Masking:**
   GitHub Actions secara otomatis menyamarkan (*masking*) nilai dari `secrets.*` pada log konsol. Sebutkan minimal dua skenario edge-case di mana secret dapat bocor secara tidak sengaja (*information disclosure*) ke dalam build logs meskipun fitur masking aktif, dan bagaimana cara memitigasinya.

3. **Analisis Failure Cascading dan `if: always()`:**
   Sebuah pipeline mendefinisikan step pembersihan (*teardown*) dengan kondisi `if: always()`. Jika runner mengalami *hard crash* (misalnya: OOM Killer mematikan proses runner host, atau node runner kehilangan koneksi jaringan/power), apakah step tersebut dijamin tereksekusi? Jelaskan batas toleransi sistem runner terhadap kegagalan tingkat OS vs kegagalan tingkat aplikasi (*non-zero exit code*).

4. **Matrix Strategy dan Fail-Fast Behavior:**
   Ketika menjalankan matrix testing untuk 9 kombinasi environment (misal: 3 Node.js versions x 3 OS types), job pada `Node 18 - Windows` gagal pada detik ke-10. Secara default, apa yang terjadi pada 8 job lainnya? Bagaimana mekanisme `fail-fast: false` dan `continue-on-error` memodifikasi grafik eksekusi (*DAG - Directed Acyclic Graph*) dari workflow tersebut?

5. **Concurrency Groups dan Race Condition Prevention:**
   Jelaskan kegunaan blok `concurrency:` yang dikombinasikan dengan pembatalan otomatis (`cancel-in-progress: true`). Bagaimana mekanisme ini mencegah pemborosan komputasi (*billing minutes*) dan benturan mutasi *state* ketika seorang *developer* melakukan 5 kali *push* berturut-turut dalam rentang waktu 30 detik pada *branch* yang sama?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: CI Bottleneck & Queue Exhaustion pada Skala Monorepo
* **Kasus:** Tim enterprise Anda baru saja menggabungkan 12 mikroservis ke dalam satu monorepo. Setiap kali ada PR dibuka untuk servis analitik (hanya mengubah 2 file `.py`), seluruh workflow CI terpicu: menjalankan kompilasi Java, linting Go, testing frontend, dan audit Docker image. Waktu tunggu antrean CI melesat dari 4 menit menjadi 45 menit per PR, menghabiskan kuota *runner minutes* bulanan organisasi dalam waktu 5 hari.
* **Pertanyaan Diagnostik:**
  1. Bagaimana Anda merestrukturisasi konfigurasi trigger workflow menggunakan teknik *Path Filtering* (`paths` / `paths-ignore`) atau modularisasi actions untuk mengisolasi eksekusi?
  2. Bagaimana arsitektur *change detection* tingkat lanjut (menggunakan Git diff SHA base vs head) diterapkan jika servis-servis tersebut memiliki dependensi internal bersama (*shared libraries*)?

### Skenario B: Race Condition dan Out-of-Order Deployment pada Staging
* **Kasus:** Dua developer, Alice dan Bob, melakukan merge PR ke branch `main` hampir bersamaan (selisih 10 detik). PR Alice (Commit A) membutuhkan waktu build 15 menit karena menjalankan migrasi skema database. PR Bob (Commit B - hanya hotfix styling) selesai dalam 2 menit. Runner mengeksekusi pipeline Commit B lebih dulu hingga tahap deploy, lalu 13 menit kemudian pipeline Commit A menyelesaikan deploy staging. Akibatnya, perubahan styling Bob tertimpa kembali oleh image lama dari commit Alice.
* **Pertanyaan Diagnostik:**
  1. Identifikasi kecacatan arsitektural pada konfigurasi deployment pipeline di atas.
  2. Rancang solusi deterministic deployment menggunakan kombinasi `concurrency group`, environment locks, atau strategi *linear history deployment* untuk memastikan integritas rilis.

### Skenario C: Trade-off Arsitektur: GitHub-Hosted vs Self-Hosted Runners
* **Kasus:** Perusahaan Fintech Anda memiliki regulasi kepatuhan ketat: artefak build tidak boleh keluar dari VPC internal AWS, dan pipeline membutuhkan akses ke database dev internal berukuran 100GB untuk testing performa. Manajemen mengusulkan migrasi penuh dari *GitHub-hosted runners* ke *Self-Hosted Runners* di dalam subnet privat AWS.
* **Pertanyaan Diagnostik:**
  1. Apa risiko keamanan fatal (*security blast radius*) dari penggunaan *Self-Hosted Runner* pada repositori publik vs privat, khususnya terkait vektor serangan modifikasi workflow via *Pull Request* eksternal?
  2. Berikan analisis komparatif (*trade-off*) dari aspek: *Maintenance Overhead* (ephemeral vs persistent runners), *Cost/Autoscaling complexity*, dan *Network Latency* terhadap sumber daya internal.

---

## 4. Chapter Challenge

### Tantangan Praktis: "Production-Grade Pull Request Sanitizer & Build Matrix"

#### Problem Statement
Anda ditugaskan merancang gerbang kualitas kode (*Quality Gate*) otomatis untuk repositori backend Node.js/TypeScript sebelum kode diizinkan masuk ke branch `main`. Pipeline harus cepat, deterministik, aman dari serangan injeksi, dan hemat biaya eksekusi.

#### Requirements
1. **Triggering Engine:**
   - Workflow hanya berjalan pada *Pull Request* yang menargetkan branch `main`.
   - Workflow harus membatalkan run sebelumnya jika ada push commit baru pada PR yang sama.
2. **Quality Gate Jobs (Parallel Execution):**
   - **Job 1: Linter & Static Analysis**
     - Menjalankan pemeriksaan format dan TypeScript type checking.
   - **Job 2: Unit Testing Matrix**
     - Menguji kode pada dua versi LTS: Node.js `18.x` dan `20.x`.
     - Menggunakan mekanisme cache dependensi (`npm cache`) untuk memangkas durasi build.
3. **Packaging Job (Dependent Execution):**
   - **Job 3: Artifact Compilation**
     - Hanya berjalan jika Job 1 dan SELURUH matrix Job 2 berhasil (`needs`).
     - Melakukan kompilasi TypeScript menjadi JavaScript (`dist/`).
     - Mengunggah folder `dist/` sebagai GitHub Actions Artifact dengan waktu retensi 3 hari.
4. **Security & Governance:**
   - Batasi permission `GITHUB_TOKEN` ke level terendah: `contents: read`.
   - Tambahkan timeout eksplisit pada setiap job (maksimal 10 menit) untuk mencegah runaway process.

#### Constraints
- Seluruh pipeline harus didefinisikan dalam satu file workflow tunggal: `.github/workflows/pr-sanitizer.yml`.
- Wajib menggunakan sintaks YAML standar GitHub Actions yang valid (bebas *deprecated actions* seperti `actions/checkout@v2`).

#### Expected Output
1. File workflow `.github/workflows/pr-sanitizer.yml` yang memenuhi seluruh kriteria secara presisi.
2. Dokumentasi singkat (3-4 paragraf teknis) yang menjelaskan:
   - Bagaimana penanganan cache menghemat *bandwidth* dan waktu eksekusi.
   - Mengapa isolasi permission (`permissions: contents: read`) merupakan mitigasi efektif terhadap supply-chain attack.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Anatomi file YAML GitHub Actions: perbedaan semantik `uses` (reusable actions) vs `run` (shell commands).
- [ ] Perilaku runner virtual environment: isolasi proses antar *job* dan volatilitas workspace lokal.
- [ ] Mekanisme parsing DAG (*Directed Acyclic Graph*) yang diatur oleh sintaks `needs`.
- [ ] Aturan resolusi secret: kapan secret dienkripsi, dikirim, dan bagaimana GitHub runners memfilter secret dari output stream (*stdout/stderr*).
- [ ] Strategi caching dependensi vs persistensi artefak: perbedaan fungsi, siklus hidup, dan batasan ukuran (*storage quotas*).

### Saya tidak perlu menghafal:
- [ ] Daftar lengkap spesifikasi hardware default GitHub-hosted runner (RAM/CPU exact numbers per OS image).
- [ ] Seluruh sintaks ekspresi internal GitHub context (misal: payload mendalam dari `github.event.*`); cukup pahami cara mengaksesnya via dokumentasi.
- [ ] Sintaks exact dari ratusan third-party action marketplace; cukup pahami cara membaca `action.yml` untuk mengetahui input, output, dan permission requirements-nya.

### Saya harus bisa melakukan:
- [ ] Menulis workflow YAML dari nol dengan struktur hierarki yang valid tanpa syntax error.
- [ ] Mengonfigurasi event trigger spesifik dengan filter `branches`, `paths`, dan `tags`.
- [ ] Mengamankan workflow dengan mengonfigurasi blok `permissions` secara granular di level workflow maupun job.
- [ ] Menerapkan `actions/cache` dan `actions/setup-*` untuk mempercepat durasi siklus CI.
- [ ] Menganalisis *raw build logs* untuk mendiagnosis kegagalan pipeline (membedakan antara syntax error, environment failure, test assertion failure, dan network timeout).
- [ ] Menggunakan `concurrency groups` untuk mengeliminasi pemborosan resource akibat commit bertubi-tubi.