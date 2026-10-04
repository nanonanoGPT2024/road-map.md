# BAB 10: Quiz, Challenge, & Knowledge Check
**CI/CD, Automasi Fastlane, & App Store Deployment**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Anatomi dan Mekanisme Kriptografis iOS Code Signing:**
   Jelaskan secara presisi bagaimana Apple Developer Certificate, Private Key, Provisioning Profile, App ID, dan Entitlements saling terikat secara kriptografis selama proses kompilasi (`codesign`) hingga verifikasi runtime oleh kernel iOS (`amfid` - Apple Mobile File Integrity Daemon). Mengapa profil provisioning bertipe *Development* menolak eksekusi biner jika UDID perangkat tidak terdaftar di dalamnya, sedangkan profil bertipe *Distribution (App Store)* tidak memerlukan daftar UDID?

2. **Fastlane Match vs. Xcode Automatic Signing pada Lingkungan Headless CI:**
   Mengapa pendekatan *Automatic Signing* bawaan Xcode hampir selalu gagal atau dianggap sebagai *anti-pattern* pada *ephemeral CI/CD runners* (misal: Docker-based macOS runner, GitHub Actions, GitLab CI)? Jelaskan filosofi di balik arsitektur Fastlane `match` (Code Signing via Git/S3/GCS repository terenkripsi) dan bagaimana ia menyelesaikan masalah sinkronisasi sertifikat antar anggota tim dan mesin CI.

3. **Autentikasi Headless App Store Connect API:**
   Bandingkan penggunaan Apple ID berbasis session (dengan App-Specific Password dan Two-Factor Authentication SMS/Device) terhadap App Store Connect API Key (`.p8` JWT Token). Mengapa penggunaan App Store Connect API Key mutlak diperlukan untuk pipeline CI enterprise, dan bagaimana daur hidup validitas token JWT tersebut dikelola oleh Fastlane atau CLI tools modern?

4. **Dekomposisi Fase Kompilasi `xcodebuild`:**
   Jelaskan perbedaan mekanis dan efisiensi resource antara perintah `xcodebuild build-for-testing` dan `xcodebuild test-without-building`. Bagaimana pemisahan kedua fase ini memungkinkan orkestrasi parallel testing (test sharding) secara terdistribusi pada beberapa worker runner yang berbeda?

5. **Siklus Hidup dSYM dan Crash Symbolication Pasca-Deprekasi Bitcode:**
   Sejak Apple mendeprekasi Bitcode di Xcode 14, di mana tepatnya file debug symbols (`dSYM`) dihasilkan selama proses build? Jelaskan alur kerja otomatisasi yang harus diimplementasikan pada pipeline CI/CD untuk mengekstrak, mengompresi, dan mendistribusikan dSYM ke vendor crash reporting (seperti Sentry, Firebase Crashlytics, atau App Store Connect) guna menghindari *un-symbolicated crash stack traces* di lingkungan staging dan produksi.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Manajemen macOS Keychain Locking & Partition List Exceptions:**
   Pada lingkungan headless runner macOS, eksekusi Fastlane sering terhenti (*hang indefinitely*) atau melempar galat `errSecInternalComponent` saat mencoba mengakses private key untuk code signing. Bedah mekanisme internal macOS Keychain: apa yang dimaksud dengan *Keychain access partition list*, mengapa `security unlock-keychain` saja terkadang tidak cukup, dan bagaimana perintah `security set-key-partition-list` mengatasi interupsi dialog GUI authorization dari sistem operasi?

2. **Manajemen Determinisme dan Cache Invalidation Swift Package Manager (SPM):**
   Pada pipeline CI, kompilasi SPM sering kali mengalami bottleneck pada resolusi dependensi atau bahkan *failed build* akibat *transitive dependency mismatch*. Bagaimana mekanisme internal file `Package.resolved` menjamin determinisme build? Strategi *caching* DerivedData dan `.build/` seperti apa yang aman diterapkan tanpa memicu *cache poisoning* saat branch diperbarui?

3. **Race Condition pada Fastlane Match di Skala Konkuren:**
   Bayangkan sebuah tim dengan 30 iOS engineer yang menjalankan puluhan workflow CI secara paralel. Jika terjadi *regeneration* sertifikat atau pembuatan provisioning profile baru secara otomatis via `match`, *race condition* seperti apa yang dapat terjadi pada Git remote repository penyimpanan sertifikat? Parameter atau mekanisme penguncian (*locking mechanism*) apa yang harus diaktifkan pada Fastlane untuk mencegah korupsi repositori sertifikat tersebut?

4. **Diagnostik dan Mitigasi xcodebuild Exit Code 65 vs 70:**
   Bedah signifikansi sistemik dari dua galat umum `xcodebuild`: **Exit Code 65** dan **Exit Code 70**. Sebutkan masing-masing minimal tiga *root causes* yang membedakan kedua kode galat tersebut pada level build system, code signing, dan iOS Simulator lifecycle management di lingkungan headless CI.

5. **Optimasi Test Runner Virtualization & Simulator Clone Bottlenecks:**
   Saat menjalankan `run-tests` secara paralel pada mesin bare-metal macOS (misal: Mac Studio M2 Max), performa sering kali terdegradasi drastis jika beberapa simulator di-boot bersamaan. Jelaskan konsep *Simulator clone lifecycle* (`xcrun simctl clone`), bagaimana I/O disk virtual memory mempengaruhi execution time, dan bagaimana teknik *ramdisk* atau *parallel testing destinations* (`-parallel-testing-workers`) harus dikonfigurasi secara optimal.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck Durasi CI Pipeline dan Biaya Infrastruktur (Cost & Latency)
Perusahaan Anda memiliki aplikasi iOS enterprise monolitik dengan 450.000 baris kode Swift/Objective-C dan 80 dependensi pihak ketiga. Saat ini, pipeline PR-validation di GitHub Actions (menggunakan runner macOS-latest standar Apple Silicon) membutuhkan waktu **58 menit** per run. Akibatnya, terjadi antrean merge PR yang panjang, developer *idle*, dan pembengkakan biaya runner macOS GitHub Actions hingga \$4.000 per bulan.
* **Pertanyaan Diagnostik & Solusi:**
  1. Audit area build pipeline mana saja yang berpotensi menjadi penyumbang waktu terbesar (*DerivedData compilation*, *Dependency resolution*, *Unit testing*, *Linting/SonarQube*).
  2. Rancang arsitektur pipeline baru yang memangkas build time menjadi **di bawah 12 menit**. Jelaskan strategi *caching* layer (SPM, compilation cache/ccache/sccache, Tuist/Bazel modular build cache) dan orkestrasi worker yang Anda pilih.
  3. Berikan analisis *trade-off* finansial dan operasional antara tetap menggunakan Hosted Runner (GitHub Actions / Bitrise) vs migrasi ke Self-Hosted bare-metal Mac Studio clusters yang diorkestrasi via Kubernetes/Tart/Anka virtualization.

### Skenario B: Race Condition Build Number dan Kegagalan Tagging Rilis Konkuren
Tim Anda menerapkan pola branch-based deployment: setiap kali merge ke branch `release/*`, CI akan memicu Fastlane lane `:beta` yang mengambil nomor build terbaru dari App Store Connect via `latest_testflight_build_number`, menambahkan `+1`, mengompilasi biner, dan mengunggahnya ke TestFlight. Pada hari rilis, dua engineer secara bersamaan melakukan merge dua hotfix PR yang berbeda ke branch `release/1.4.0` dengan selisih waktu 40 detik.
* **Pertanyaan Diagnostik & Solusi:**
  1. Jelaskan mengapa *race condition* terjadi pada kasus ini dan galat spesifik apa yang dikembalikan oleh App Store Connect API saat upload biner kedua berlangsung.
  2. Mengapa reliance terhadap `latest_testflight_build_number` merupakan *anti-pattern* pada pipeline skala enterprise?
  3. Rancang strategi penentuan `CFBundleVersion` (Build Number) yang sepenuhnya deterministik, terisolasi, dan aman terhadap eksekusi paralel tanpa bergantung pada network polling status TestFlight.

### Skenario C: Migrasi Arsitektur Deployment ke In-House CLI vs Fastlane Ruby Monolith
Aplikasi Anda sedang bermigrasi ke arsitektur modular skala besar. Fastlane yang ditulis dengan Ruby (`Fastfile`, plugin `cocoapods`, plugin pihak ketiga) mulai menunjukkan kerapuhan: sering terjadi konflik dependency bundler (`gem`), performa eksekusi Ruby interpreter lambat saat startup, dan engineer iOS enggan memelihara codebase CI karena tidak familiar dengan Ruby ecosystem. VP of Engineering mengusulkan untuk membuang Fastlane sepenuhnya dan menggantinya dengan Swift-based automation CLI tooling (menggunakan Swift Argument Parser dan raw `xcodebuild` / App Store Connect API client).
* **Pertanyaan Diagnostik & Solusi:**
  1. Analisis risiko kritis dan *hidden costs* dari keputusan menulis sendiri App Store deployment tooling menggunakan pure Swift CLI.
  2. Bagaimana evaluasi Anda terhadap fitur-fitur kompleks Fastlane seperti *automatic certificate renewal*, *two-factor session handling*, *metadata localized screenshots frame extraction*, dan *dSYM re-downloading from Apple* jika harus diimplementasikan secara manual?
  3. Rekomendasikan jalan tengah arsitektur automasi yang modern: apakah tetap Fastlane dengan standardisasi containerized runtime, beralih ke Fastlane.swift, atau membangun hybrid orchestrator? Justifikasikan argumen Anda berdasarkan *maintainability* dan *developer experience*.

---

## 4. Chapter Challenge

### Tantangan Praktis: Enterprise Multi-Stage Delivery Pipeline dengan Fastlane, Dynamic Code Signing, dan Sentry Automation

#### Problem Statement:
Anda diminta merancang sistem otomasi CI/CD dari nol untuk aplikasi perbankan iOS. Aplikasi memiliki dua skema: `Staging` dan `Production`. Tim membutuhkan otomasi yang memvalidasi setiap Pull Request, mendistribusikan build nightly ke TestFlight internal, serta upload build Release Candidate ke TestFlight external lengkap dengan dSYM tracking ke Sentry.

#### Requirements:
1. **Fastlane Architecture:**
   * Tulis sebuah `Fastfile` modular yang mencakup minimal 3 lane:
     * `private_lane :setup_signing` (menerima parameter tipe environment).
     * `lane :pr_validation` (menjalankan SwiftLint, unit tests dengan xcresult formatter, dan build for testing).
     * `lane :build_and_deploy_testflight` (mengatur signing distribution, increment build number secara otomatis dan deterministik, kompilasi biner `.ipa`, upload ke TestFlight via App Store Connect API Key, dan upload dSYM ke Sentry via Sentry CLI/Fastlane plugin).
2. **Deterministic Code Signing (Match):**
   * Gunakan konfigurasi `Matchfile` yang mengisolasi sertifikat `development`, `adhoc`, dan `appstore` pada Git storage yang terenkripsi password. Mode harus diset ke `readonly: true` pada CI runner untuk menjamin integritas.
3. **App Store Connect Authentication:**
   * Konfigurasikan pemanggilan `app_store_connect_api_key` menggunakan parsing environment variables (Key ID, Issuer ID, dan Base64 encoded private key).
4. **Resiliency & Reporting:**
   * Buat `error block` global pada Fastlane yang dapat menangkap kegagalan pipeline, mengekstrak log `xcodebuild` yang relevan, membersihkan keychain sementara, dan mengirimkan notifikasi kegagalan ke webhook Slack.

#### Constraints:
* Waktu eksekusi build & archive tidak boleh menghasilkan dirty state pada git working directory.
* Keychain CI yang dibuat harus bertipe ephemeral (dibuat di awal pipeline dengan nama unik berbasis UUID/Build ID, dan dihapus secara mutlak di blok `ensure/always`).
* Dilarang melakukan hardcode secret (password, base64 key, token) di dalam file repository.

#### Expected Output:
* File `Fastfile` yang clean, idiomatik, dan terstruktur sesuai standar enterprise Ruby.
* File `Matchfile` yang siap digunakan.
* Script shell / pipeline step declaration (misal: format `.github/workflows/deploy.yml` atau script wrapper runner) yang mendemonstrasikan bagaimana environment variable disuntikkan dan keychain diisolasi.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan fungsional Certificate (`.cer`/`.p12`), Private Key, Provisioning Profile (`.mobileprovision`), dan Entitlements.
- [ ] Arsitektur internal Apple Mobile File Integrity (`amfid`) dalam memvalidasi integritas biner dan signature saat runtime.
- [ ] Cara kerja Fastlane `match` dalam mengenkripsi, mendekripsi (via OpenSSL), dan mengelola sertifikat di remote repository.
- [ ] Mengapa *App Store Connect API Key* (`.p8`) lebih superior dan deterministik dibanding *session-based Apple ID authentication*.
- [ ] Alur generasi debug symbols (`dSYM`), struktur mach-O UUID, dan mekanisme crash symbolication pasca-deprekasi Bitcode.
- [ ] Perbedaan mendasar `build-for-testing` vs `test-without-building` pada `xcodebuild` untuk parallel testing.
- [ ] Peran DerivedData, modul cache SPM, dan risiko *cache poisoning* pada persistent CI agents.
- [ ] Mekanisme keamanan macOS Keychain: access control list (ACL), partition list, dan unlocking timeout pada headless shell.

### Saya tidak perlu menghafal:
- [ ] Seluruh command line flag dari `xcodebuild` (misal: `-exportLocalizationsProviderOptionsDictionary`). Cukup pahami argumen core: `-workspace`, `-scheme`, `-destination`, `-derivedDataPath`, dan `-archivePath`.
- [ ] Sintaks exact dari OpenSSL cipher arguments yang digunakan Fastlane `match` di balik layar.
- [ ] Struktur XML internal dari file `.mobileprovision` secara mendalam byte-per-byte.

### Saya harus bisa melakukan:
- [ ] Menulis file automasi `Fastfile` dengan lane yang modular, idempotence, dan reusable.
- [ ] Mengonfigurasi Fastlane `match` dari nol menggunakan storage backend (Git/S3) dan mengenkripsinya dengan symmetric passphrase.
- [ ] Melakukan debugging kegagalan code signing di headless machine menggunakan command line tool (`security`, `codesign --verify -vvvv`, `openssl`).
- [ ] Mengekstrak nomor versi dan memanipulasi `CFBundleVersion` secara deterministik pada continuous delivery pipeline.
- [ ] Mengonfigurasi integrasi dSYM upload otomatis ke monitoring tool pihak ketiga (Sentry/Firebase) di dalam proses deployment.
- [ ] Mendesain arsitektur CI/CD terdistribusi yang memisahkan stage *Testing*, *Archiving*, dan *Distribution* untuk efisiensi waktu kompilasi.