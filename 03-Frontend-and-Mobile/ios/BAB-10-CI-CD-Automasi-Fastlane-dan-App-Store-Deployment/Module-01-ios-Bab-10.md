# BAB 10: MODULE 01 — CI/CD, AUTOMASI FASTLANE, & APP STORE DEPLOYMENT

---

## SEKSI 01 — IDENTITAS MODUL

* **Jalur Pembelajaran:** 03-Frontend-and-Mobile
* **Teknologi Utama:** iOS (Swift, Xcodebuild, Fastlane, GitHub Actions)
* **Topik Modul:** CI/CD, Automasi Fastlane, & App Store Deployment
* **Prasyarat Pengetahuan:** Penguasaan arsitektur aplikasi iOS modular, SPM (Swift Package Manager), konfigurasi Xcode (`.xcconfig`, targets, schemes), dasar-dasar CLI Unix/macOS, manajemen Git tingkat lanjut, serta pemahaman alur kerja Apple Developer Program (Certificates, Identifiers, Provisioning Profiles).
* **Tingkat Kesulitan:** Advanced / Staff Engineer Level
* **Estimasi Waktu Penyelesaian:** 12 - 16 Jam Pembelajaran Mendalam & Praktik Mandiri

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, engineer diharapkan memiliki kompetensi industri tingkat lanjut untuk:

1. **Merancang Pipeline CI/CD Skala Enterprise:** Mampu mengarsiteksi dan mengimplementasikan pipeline build, test, signing, dan release multi-tier otomatis menggunakan kombinasi GitHub Actions/GitLab CI dan macOS self-hosted runners.
2. **Menguasai Toolchain Fastlane:** Mengimplementasikan orkestrasi otomasi menggunakan Ruby/Fastlane API (`Fastfile`, `Appfile`, `Matchfile`, `Pluginfile`) secara modular, deterministik, dan dapat dipelihara (*maintainable*).
3. **Mengeliminasi "Code Signing Hell":** Menerapkan filosofi *Git-based Code Signing* melalui `fastlane match` dengan enkripsi asimetris/simetris OpenSSL, mengelola Apple Developer Certificate & Provisioning Profile secara otomatis dan aman.
4. **Menerapkan Otomasi Metadata & Distribusi:** Mengonfigurasi otomatisasi transmisi aset grafis, lokal metadata, upload binary `.ipa` ke TestFlight (internal/external groups), serta submit ke App Store Connect Review API secara *headless*.
5. **Menjamin Keamanan Rantai Pasok (Supply Chain Security):** Menerapkan praktik zero-trust credential injection menggunakan App Store Connect API Key (JSON Web Token), SSH private keys, rotasi sertifikat, dan perlindungan *ephemeral runner*.
6. **Mengoptimalkan Kinerja Build & Infrastruktur:** Memangkas durasi kompilasi hingga 60% melalui Xcode DerivedData caching, Swift Package Manager artifact caching, parallel testing (`xcodebuild -parallel-testing-enabled YES`), dan differential linting.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma: Local Manual Build vs Deterministic Headless Build
Paradigma manual pengembang iOS pemula berpusat pada Xcode GUI: menekan tombol `Cmd + B` untuk kompilasi lokal, mengklik tombol *Archive*, dan membiarkan "Xcode Automatically Manage Signing" mengelola profil provisioning. Pendekatan ini gagal total pada skala enterprise karena memunculkan fenomena:
* *"It works on my machine"*: Ketidakcocokan versi Swift compiler, toolchain macOS, dan *transitive dependency*.
* *"Certificate Invalidation War"*: Pengembang saling merevoke Distribution Certificate rekan kerja karena batas maksimal kuota sertifikat Apple Developer Program tercapai.
* *Human Error Release*: Terlewatnya pengujian regresi kritis, kebocoran metadata debug/staging ke binary production, atau salah memilih entitlement provisioning profile.

Mental model level Staff Engineer memandang rilis aplikasi iOS sebagai sistem terdistribusi yang deterministik. Kode sumber harus dikonversi menjadi binary yang telah ditandatangani (*signed binary artifact*) di lingkungan isolasi (*ephemeral container* atau *clean-slate macOS agent*). Xcode GUI hanyalah antarmuka sekunder; antarmuka utamanya adalah sekumpulan script berbasis CLI: `xcodebuild`, `codesign`, `security`, `simctl`, dan `altool`/`xcrun notarytool` yang diabstraksi secara elegan oleh Fastlane.

### Prinsip Fastlane: Abstraksi Idempoten
Fastlane bertindak sebagai *unified glue layer*. Fastlane membungkus complex tools CLI macOS ke dalam *actions* dan *lanes* yang bersifat deklaratif dan idempoten:
* **State Immutability:** Menjalankan *lane* yang sama berkali-kali pada commit SHA yang sama harus menghasilkan artefak yang identik secara fungsional.
* **Separation of Secrets:** Kredensial tidak pernah disimpan di dalam repositori kode aplikasi. Kredensial diinjeksi saat *runtime* melalui secure environment variables ke dalam keychain sementara (*transient keychain*) yang akan dihancurkan seketika setelah pipeline selesai.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Berikut adalah arsitektur holistik otomasi rilis continuous deployment iOS berbasis Fastlane, GitHub Actions, dan Apple Developer Program Services:

```
+---------------------------------------------------------------------------------------------------+
|                                      GIT REPOSITORY WORKFLOW                                      |
+---------------------------------------------------------------------------------------------------+
                                                  |
                 [Developer Git Push: feat/* / fix/* / main / release/*]
                                                  |
                                                  v
+---------------------------------------------------------------------------------------------------+
|                                  CI ORCHESTRATOR (GitHub Actions)                                 |
|                                                                                                   |
|  +---------------------------+  +---------------------------+  +-------------------------------+  |
|  | Job 1: Static Analysis    |  | Job 2: Unit & UI Tests    |  | Job 3: Build & Distribution   |  |
|  | - SwiftLint / SwiftFormat |  | - xcodebuild test         |  | - fastlane match (Sync Certs) |  |
|  | - Periphery (Dead Code)   |  | - Parallel Simulators     |  | - gym / xcodebuild archive    |  |
|  | - Dependency Audit (SPM)  |  | - Slather (Code Coverage) |  | - deliver / pilot (Upload)    |  |
|  +---------------------------+  +---------------------------+  +-------------------------------+  |
+---------------------------------------------------------------------------------------------------+
                                                  |
                    +-----------------------------+-----------------------------+
                    |                                                           |
                    v (Fetch Certs / Profiles via Git Storage)                  v (Authenticate API)
+---------------------------------------+             +---------------------------------------------+
|    CERTIFICATE STORAGE (Private Git)  |             |      APP STORE CONNECT API (Headless JWT)   |
|                                       |             |                                             |
|  - Encrypted Distribution Cert (.p12) |             |  - Issuer ID                                |
|  - Encrypted Apple WWDRCA             |             |  - Key ID                                   |
|  - Provisioning Profiles (.mobileprov)|             |  - Private Key (.p8)                        |
+---------------------------------------+             +---------------------------------------------+
                    |                                                           |
                    +-----------------------------+-----------------------------+
                                                  |
                                                  v
+---------------------------------------------------------------------------------------------------+
|                                     MACOS EPHEMERAL BUILD RUNNER                                  |
|                                                                                                   |
| 1. Create Transient Keychain: `fastlane_tmp_keychain`                                             |
| 2. Import Decrypted Keys & Certificates                                                           |
| 3. Resolve SPM Dependencies (Cache: ~/Library/Caches/org.swift.swiftpm)                           |
| 4. Compile & Link: `xcodebuild -workspace App.xcworkspace -scheme Production -configuration ...`  |
| 5. Sign Binary: `codesign -s "Apple Distribution: ..." Payload/App.app`                           |
| 6. Package: Generate Production IPA (`App.ipa`) & dSYM bundles                                    |
| 7. Cleanup: Delete `fastlane_tmp_keychain`                                                        |
+---------------------------------------------------------------------------------------------------+
                                                  |
                    +-----------------------------+-----------------------------+
                    | (Upload Crash Artifacts)                                  | (Upload Binary & Meta)
                    v                                                           v
+---------------------------------------+             +---------------------------------------------+
|     CRASH MONITORING (e.g. Sentry)    |             |              APPLE INFRASTRUCTURE           |
|                                       |             |                                             |
|  - App.app.dSYM.zip (Debug Symbols)   |             |  - TestFlight Internal (QA Engineers)       |
|  - Proguard / Swift Source Maps       |             |  - TestFlight External (Beta Testers)       |
|                                       |             |  - App Store Review (Production Release)    |
+---------------------------------------+             +---------------------------------------------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Mekanisme Kriptografi Code Signing Apple
Binary iOS tidak dapat dieksekusi oleh kernel XNU (kernel iOS) tanpa validasi tanda tangan digital berbasis kriptografi kunci publik.
* **Apple Root CA & Intermediate CA:** Menjamin bahwa tanda tangan digital diterbitkan oleh otoritas resmi Apple Developer Relations.
* **Developer/Distribution Certificate (`.cer` / `.p12`):** Berisi kunci publik developer yang telah ditandatangani oleh Apple Intermediate CA, dipasangkan dengan Kunci Pribadi (*Private Key*) yang aman tersimpan di macOS Keychain.
* **Provisioning Profile (`.mobileprovision`):** File berformat CMS (*Cryptographic Message Syntax*) yang membungkus:
  1. Daftar UUID perangkat yang diizinkan (khusus Development/AdHoc).
  2. Entitlements aplikasi (App Groups, Associated Domains, Push Notifications).
  3. Bundle ID eksplisit/wildcard.
  4. Salinan satu atau lebih Certificate publik.
* **Sealing the Payload:** Saat eksekusi `codesign`, Xcode membuat *Code Directory Hash* (CDHash) dari setiap file executable, resource, framework, dan file `embedded.mobileprovision`. CDHash ini dienkripsi menggunakan *Private Key* developer dan disematkan ke dalam Mach-O binary header.

### 2. Inner Working: `fastlane match`
`fastlane match` mengimplementasikan pendekatan *"One team, one certificate"*. Alih-alih setiap developer membuat sertifikat masing-masing:
1. `match` melakukan clone atas Git repository terenkripsi via SSH/HTTPS.
2. `match` mendekripsi repositori lokal menggunakan algoritma simetris `OpenSSL` (AES-256-CBC) dengan variabel sandi `MATCH_PASSWORD`.
3. `match` membuat macOS keychain sementara (`custom.keychain-db`).
4. `match` mengimpor sertifikat `.cer` dan kunci privat `.p12` ke dalam keychain sementara dan mengaturnya ke keychain search list.
5. `match` mengunduh atau memverifikasi kesesuaian `.mobileprovision` dari portal App Store Connect menggunakan App Store Connect API.
6. Profil diinstal ke direktori sistem: `~/Library/MobileDevice/Provisioning Profiles/`.
7. `match` memetakan UUID profil ke *Environment Variable* standar Xcode (misal: `$(App_PROVISIONING_PROFILE)`).

### 3. Ekosistem Komponen Fastlane Core
Fastlane bukan monolit, melainkan kumpulan modul Ruby (Gems):
* **`sigh`:** Mengunduh, memperbarui, dan mengelola provisioning profile.
* **`cert`:** Membuat dan memperbarui distribution certificate jika belum ada.
* **`gym` (di-alias sebagai `build_app`):** Wrapper untuk utility `xcodebuild`. Mengelola fase `clean`, `analyze`, `archive`, dan `exportArchive` serta parsing `exportOptions.plist`.
* **`pilot` (di-alias sebagai `upload_to_testflight`):** Berkomunikasi dengan TestFlight API untuk upload `.ipa`, mengelola groups tester, dan polling status processing TestFlight.
* **`deliver` (di-alias sebagai `upload_to_app_store`):** Mengunggah metadata (deskripsi, release notes, rating, localized strings), screenshot dari snapshots, dan submit binary untuk App Store Review.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Transisi Transporter: Dari Legacy Password ke App Store Connect API Key (JWT)
Dahulu, Fastlane berkomunikasi dengan backend Apple melalui teknik web scraping dan `iTMSTransporter` menggunakan kredensial akun Apple ID (Email + Password) yang memerlukan bypass 2FA melalui sesi SMS / TOTP (`FASTLANE_SESSION`). Pendekatan ini rapuh dan sering terputus sewaktu-waktu.

Arsitektur modern mengandalkan **App Store Connect API Key** berbasis standar RFC 7519 (JWT). Kunci privat ECC (*Elliptic Curve Cryptography*, kurva P-256) berekstensi `.p8` digunakan untuk menandatangani JWT token secara lokal. Header dan Claims JWT tersebut memuat:

$$\text{JWT} = \text{Base64URL}(\text{Header}) \,||\, "." \,||\, \text{Base64URL}(\text{Payload}) \,||\, "." \,||\, \text{Signature}$$

Di mana Payload memuat:
```json
{
  "iss": "57246542-96fe-1a63-e053-0824d011072a", // Issuer ID
  "exp": 1672531199,                               // Expiration Unix Epoch (Max 20 mins)
  "aud": "appstoreconnect-v1",                      // Audience
  "bid": "com.company.enterprise.app"               // Bundle ID (opsional)
}
```
Fastlane meregenerasi token JWT berumur pendek ini (maksimum 20 menit) untuk setiap siklus sesi REST API request. Pendekatan ini sepenuhnya mengeliminasi masalah 2FA dan dapat dijalankan 100% *headless* di CI runner.

### Dekonstruksi `xcodebuild -exportArchive` dan `ExportOptions.plist`
Proses kompilasi iOS modern terbagi menjadi dua fase independen:
1. **Fase Archive:** Mentranslasikan source code Swift, resource, dan dependensi menjadi satu set *Unsigned / Developer-Signed Mach-O bundles* yang diletakkan di dalam folder bundle archive berformat `.xcarchive`.
2. **Fase Export:** Mengonversi `.xcarchive` menjadi `.ipa` (*iOS Packaged Application*) yang siap didistribusikan. Fase ini dikontrol penuh oleh file `ExportOptions.plist`.

Parameter krusial pada `ExportOptions.plist`:
* `method`: `app-store`, `ad-hoc`, `enterprise`, atau `development`.
* `signingStyle`: `manual` (Wajib di CI modern demi determinisme; hindari `automatic`).
* `provisioningProfiles`: Kamus/Dictionary eksplisit yang memetakan setiap Application Bundle Identifier (termasuk App Extensions, Widget extensions, Notification Service extensions) ke string UUID provisioning profile yang tepat.
* `stripSwiftSymbols`: Mengurangi ukuran file binary dengan memotong metadata Swift yang tidak esensial.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah struktur direktori proyek standar untuk automasi Fastlane enterprise:

```text
.
├── .github/
│   └── workflows/
│       └── deployment.yml
├── fastlane/
│   ├── Appfile
│   ├── Fastfile
│   ├── Matchfile
│   └── Pluginfile
├── Config/
│   ├── Enterprise.xcconfig
│   └── ExportOptions.plist
├── Gemfile
├── Gemfile.lock
└── App.xcodeproj
```

### 1. `Gemfile`
Mengunci versi dependensi Fastlane dan Ruby tools lainnya secara deterministik menggunakan Bundler:

```ruby
source "https://rubygems.org"

gem "fastlane", "2.220.0"
gem "cocoapods", "1.15.2"

plugins_path = File.join(File.dirname(__FILE__), 'fastlane', 'Pluginfile')
eval_gemfile(plugins_path) if File.exist?(plugins_path)
```

### 2. `fastlane/Appfile`
Mendefinisikan variabel global identifier aplikasi:

```ruby
app_identifier("com.megacorp.fintech")
apple_id("devops-ios@megacorp.com")
team_id("ABCDE12345")
itc_team_id("987654321")
```

### 3. `fastlane/Matchfile`
Mendefinisikan repositori sentral sinkronisasi sertifikat:

```ruby
git_url("git@github.com:megacorp-org/ios-certificates-keystore.git")
storage_mode("git")
type("appstore")
app_identifier(["com.megacorp.fintech", "com.megacorp.fintech.NotificationExtension"])
username("devops-ios@megacorp.com")
team_id("ABCDE12345")
shallow_clone(true)
clone_branch_headless(true)
```

### 4. `fastlane/Fastfile` (Implementasi Lane Fundamental)

```ruby
default_platform(:ios)

platform :ios do
  before_all do
    ensure_git_status_clean
  end

  desc "Run Unit Tests and code validation"
  lane :test do
    run_tests(
      workspace: "FintechApp.xcworkspace",
      scheme: "FintechAppTests",
      devices: ["iPhone 15"],
      clean: true,
      code_coverage: true,
      output_directory: "./fastlane/test_output"
    )
  end

  desc "Build and sign the enterprise IPA without distribution"
  lane :build_staging do
    api_key = app_store_connect_api_key(
      key_id: ENV["ASC_KEY_ID"],
      issuer_id: ENV["ASC_ISSUER_ID"],
      key_content: ENV["ASC_KEY_CONTENT"],
      is_key_content_base64: true
    )

    create_keychain(
      name: "ci_transient_keychain",
      password: ENV["KEYCHAIN_PASSWORD"],
      default_keychain: true,
      unlock: true,
      timeout: 3600,
      lock_when_sleeps: false
    )

    match(
      type: "appstore",
      readonly: true,
      keychain_name: "ci_transient_keychain",
      keychain_password: ENV["KEYCHAIN_PASSWORD"],
      api_key: api_key
    )

    build_app(
      workspace: "FintechApp.xcworkspace",
      scheme: "Production",
      configuration: "Release",
      clean: true,
      output_directory: "./build/artifacts",
      output_name: "FintechApp_Staging.ipa",
      export_method: "app-store",
      export_options: {
        signingStyle: "manual",
        provisioningProfiles: {
          "com.megacorp.fintech" => "match AppStore com.megacorp.fintech",
          "com.megacorp.fintech.NotificationExtension" => "match AppStore com.megacorp.fintech.NotificationExtension"
        }
      }
    )

    delete_keychain(name: "ci_transient_keychain")
  end
end
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Mari kita bedah secara komprehensif logika teknis internal dari lane `build_staging` pada `Fastfile` di Seksi 07:

1. **`app_store_connect_api_key(...)`**
   * Menginstansiasi objek otentikasi REST API Apple. Parameter `key_content` mengekstrak string base64 dari environment variable pipeline untuk menghindari penyimpanan file fisik `.p8` di dalam runner filesystem. Otomatisasi Fastlane selanjutnya yang membutuhkan akses Apple Dev Center akan mengonsumsi API token yang di-generate dari kunci ini.
2. **`create_keychain(...)`**
   * Menginstansiasi keychain macOS baru (`ci_transient_keychain-db`).
   * Parameter `default_keychain: true` mengalihkan fokus sistem pencarian sertifikat dari `login.keychain` milik host runner ke keychain sementara ini.
   * `lock_when_sleeps: false` dan `timeout: 3600` mencegah macOS mengunci keychain di tengah proses kompilasi/signing yang memakan waktu lama.
3. **`match(type: "appstore", readonly: true, ...)`**
   * Parameter `readonly: true` adalah pengaman krusial pada level CI. Ini mencegah runner membuat atau merevoke sertifikat distribusi secara tidak sengaja di Apple Developer Portal jika terjadi ketidaksesuaian profil; CI hanya diizinkan membaca/mengunduh profil yang sudah ada.
   * Parameter `keychain_name` mengarahkan instalasi Private Key `.p12` secara langsung ke dalam keychain sementara yang baru dibuat.
4. **`build_app(...)` (Gym execution wrapper)**
   * Menjalankan instruksi CLI `xcodebuild -archivePath ... archive` kemudian dilanjutkan dengan `xcodebuild -exportArchive`.
   * Dictionary `provisioningProfiles` di dalam `export_options` memetakan Bundle Identifier utama dan ekstensi secara eksplisit ke nama file provisioning profile yang digenerate oleh `match` (format: `match <Type> <BundleIdentifier>`). Pendekatan ini menghentikan mekanisme *guessing profile* otomatis dari Xcode yang rentan menghasilkan binary mismatch.
5. **`delete_keychain(name: "ci_transient_keychain")`**
   * Fase pembersihan (*teardown phase*). Menginstruksikan modul CLI `security delete-keychain` untuk menghapus seluruh file keychain, kunci privat, dan sertifikat yang baru diimpor dari hard disk runner. Hal ini mencegah *credential leakage* antar sesi runner, khususnya pada self-hosted runner yang dipakai bergantian oleh banyak proyek.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario Korporasi: PT Bank Neo Finansial
PT Bank Neo Finansial mengelola aplikasi perbankan ritel dengan arsitektur modular (1 Application Core, 3 App Extensions: Push Notification Service, Siri Intent, dan Dynamic Island Widget).

### Masalah yang Dihadapi (Systemic Failures):
1. **Flaky Code Signing:** Aplikasi sering gagal rilis mingguan karena salah satu pengembang secara tidak sengaja mengklik *"Revoke Certificate"* saat mencoba memperbarui profil development lokal mereka.
2. **Manual TestFlight Upload:** QA harus menunggu Tech Lead meluangkan waktu 45 menit untuk me-release manual binary dari laptop pribadinya via Xcode Organizer setiap kali ada pengujian sprint.
3. **Insecure Credential Distribution:** File sertifikat `.p12` dan password-nya disebarkan melalui channel private Slack internal, melanggar standar kepatuhan regulasi finansial (PCI-DSS & ISO 27001).
4. **Build Time Bloat:** Kompilasi dan eksekusi total 4.200 unit tests pada host runner memakan waktu hingga 85 menit, memperlambat *time-to-market*.

### Solusi Arsitektural:
* Menerapkan Git-driven zero-touch deployment menggunakan GitHub Actions dengan runner bare-metal macOS Apple Silicon (M2 Pro).
* Sentralisasi sertifikat via `fastlane match` terenkripsi AES-256 pada private Git repository yang hanya dapat diakses oleh CI runner bot.
* Pembuatan skema dual-distribution: Setiap merge ke branch `staging` akan otomatis men-deploy binary ke TestFlight Internal Groups, sedangkan pembuatan Git Tag bertaraf semantic versioning (misal `v2.4.0`) di branch `main` akan memicu release production hingga App Store Connect Ready for Review.
* Utilisasi parallel testing dan cache DerivedData bertarget.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah implementasi lengkap standar industri untuk kasus PT Bank Neo Finansial.

### 1. `fastlane/Fastfile` Lengkap (Production Level)

```ruby
# fastlane/Fastfile
default_platform(:ios)

platform :ios do
  # Setup global configuration
  before_all do
    setup_ci if is_ci
  end

  # Helpers
  private_lane :get_asc_api_key do
    app_store_connect_api_key(
      key_id: ENV.fetch("ASC_KEY_ID"),
      issuer_id: ENV.fetch("ASC_ISSUER_ID"),
      key_content: ENV.fetch("ASC_KEY_CONTENT"),
      is_key_content_base64: true,
      in_house: false
    )
  end

  private_lane :prepare_keychain do
    create_keychain(
      name: "bank_ci_keychain",
      password: ENV.fetch("KEYCHAIN_PASSWORD"),
      default_keychain: true,
      unlock: true,
      timeout: 7200,
      lock_when_sleeps: false
    )
  end

  private_lane :teardown_keychain do
    if File.exist?(File.expand_path("~/Library/Keychains/bank_ci_keychain-db"))
      delete_keychain(name: "bank_ci_keychain")
    end
  end

  desc "Run deterministic testing suite"
  lane :run_system_tests do
    run_tests(
      workspace: "BankApp.xcworkspace",
      scheme: "BankAppScheme",
      devices: ["iPhone 15 Pro"],
      clean: false,
      code_coverage: true,
      parallel_testing: true,
      concurrent_workers: 4,
      result_bundle: true,
      output_directory: "./test_results"
    )
  end

  desc "Deploy Release Candidate to TestFlight (Internal & External Beta)"
  lane :distribute_testflight do |options|
    api_key = get_asc_api_key
    prepare_keychain

    # Increment Build Number based on CI Run ID / Commit Count
    build_number = options[:build_num] || number_of_commits.to_s
    increment_build_number(
      build_number: build_number,
      xcodeproj: "BankApp.xcodeproj"
    )

    # Sync AppStore Distribution Signing Material via Match
    match(
      type: "appstore",
      readonly: is_ci,
      keychain_name: "bank_ci_keychain",
      keychain_password: ENV.fetch("KEYCHAIN_PASSWORD"),
      api_key: api_key
    )

    # Build Application
    output_dir = "./build_output"
    ipa_path = build_app(
      workspace: "BankApp.xcworkspace",
      scheme: "BankAppProduction",
      configuration: "Release",
      clean: true,
      output_directory: output_dir,
      output_name: "BankApp_Release.ipa",
      export_method: "app-store",
      export_options: {
        signingStyle: "manual",
        provisioningProfiles: {
          "com.bankneo.app" => "match AppStore com.bankneo.app",
          "com.bankneo.app.NotificationExtension" => "match AppStore com.bankneo.app.NotificationExtension"
        }
      }
    )

    # Upload to Apple TestFlight
    upload_to_testflight(
      api_key: api_key,
      ipa: ipa_path,
      skip_waiting_for_build_processing: false,
      distribute_external: true,
      groups: ["Beta Core Employees", "Public Beta Testers"],
      changelog: "Stability improvements, modern core architectural updates."
    )

    # Teardown Security Resources
    teardown_keychain
  end

  desc "Promote Build to App Store for Official Review"
  lane :submit_to_app_store do
    api_key = get_asc_api_key

    upload_to_app_store(
      api_key: api_key,
      force: true, # Skips HTML report confirmation prompt
      skip_metadata: false,
      skip_screenshots: true,
      reject_if_possible: true,
      submit_for_review: true,
      automatic_release: false,
      phased_release: true,
      submission_information: {
        add_id_info_uses_idfa: false
      }
    )
  end

  error do |lane, exception|
    teardown_keychain
    # Send webhook alert (e.g. Slack/Teams)
    UI.error("Pipeline failure on lane #{lane}: #{exception.message}")
  end
end
```

### 2. GitHub Actions Workflow Configuration (`.github/workflows/deployment.yml`)

```yaml
name: Production iOS Deployment Pipeline

on:
  push:
    branches:
      - main
    tags:
      - 'v*.*.*'

concurrency:
  group: ios-deploy-${{ github.ref }}
  cancel-in-progress: true

jobs:
  validate_and_test:
    name: Run Unit Tests & Lint
    runs-on: macos-14
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Setup Ruby Environment
        uses: ruby/setup-ruby@v1
        with:
          ruby-version: '3.2.2'
          bundler-cache: true

      - name: Cache SPM Packages
        uses: actions/cache@v4
        with:
          path: .build
          key: ${{ runner.os }}-spm-${{ hashFiles('**/Package.resolved') }}
          restore-keys: |
            ${{ runner.os }}-spm-

      - name: Execute Fastlane Test Lane
        run: bundle exec fastlane run_system_tests

      - name: Upload Test Results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: test-results
          path: test_results

  build_and_deploy_testflight:
    name: Build & Upload to TestFlight
    needs: validate_and_test
    runs-on: macos-14
    env:
      ASC_KEY_ID: ${{ secrets.ASC_KEY_ID }}
      ASC_ISSUER_ID: ${{ secrets.ASC_ISSUER_ID }}
      ASC_KEY_CONTENT: ${{ secrets.ASC_KEY_CONTENT }}
      MATCH_PASSWORD: ${{ secrets.MATCH_PASSWORD }}
      MATCH_GIT_PRIVATE_KEY: ${{ secrets.MATCH_GIT_PRIVATE_KEY }}
      KEYCHAIN_PASSWORD: ${{ secrets.KEYCHAIN_PASSWORD }}
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Setup SSH for Match Access
        uses: webfactory/ssh-agent@v0.9.0
        with:
          ssh-private-key: ${{ secrets.MATCH_GIT_PRIVATE_KEY }}

      - name: Setup Ruby
        uses: ruby/setup-ruby@v1
        with:
          ruby-version: '3.2.2'
          bundler-cache: true

      - name: Cache DerivedData
        uses: actions/cache@v4
        with:
          path: ~/Library/Developer/Xcode/DerivedData
          key: ${{ runner.os }}-derived-data-${{ hashFiles('**/*.swift') }}
          restore-keys: |
            ${{ runner.os }}-derived-data-

      - name: Run TestFlight Distribution Lane
        run: |
          bundle exec fastlane distribute_testflight build_num:${{ github.run_number }}

      - name: Upload IPA & dSYM Artifacts
        uses: actions/upload-artifact@v4
        with:
          name: build-artifacts
          path: |
            ./build_output/*.ipa
            ./build_output/*.zip
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

Dalam arsitektur pipeline iOS, beberapa keputusan desain memiliki implikasi trade-off yang signifikan:

| Parameter Arsitektur | Opsi A: `fastlane match` (Git Storage) | Opsi B: Xcode Automatic Signing | Opsi C: Manual Profiles di VCS |
| :--- | :--- | :--- | :--- |
| **Kelebihan** | Sentralisasi, sepenuhnya deterministik, zero-trust, tidak merusak profil engineer lain. | Sangat mudah digunakan pada laptop lokal, zero initial setup script. | Tidak butuh external connection saat CI mendowload certificate. |
| **Kekurangan** | Memerlukan setup Git repo sekunder, enkripsi OpenSSL, dan konfigurasi API keys. | Membutuhkan kredensial login interaktif (tidak cocok untuk CI murni), non-deterministik. | Risiko tinggi human error, merge conflict biner, sertifikat usang tidak terdeteksi. |
| **Security Posture** | Sangat Tinggi (AES-256 + Kunci terpisah). | Lemah pada multi-tenant CI. | Kritis (Binary cert rentan bocor di commit history). |

| Strategi Host Pipeline | Cloud-Hosted macOS Runner (e.g. GitHub Actions) | Bare-Metal Self-Hosted Runner (Mac Studio Farm) |
| :--- | :--- | :--- |
| **Maintenance Cost** | Zero maintenance (Apple Silicon dikelola vendor). | Sangat Tinggi (OS updates, Xcode patching, physical security). |
| **Build Execution Time** | Rata-rata (Bergantung pada vCPU tier yang disewa). | Sangat Cepat (Native Apple Silicon bare-metal M2 Ultra/M3 Max). |
| **Biaya Finansial** | Tinggi (Penagihan per menit, macOS tier bernilai 10x Linux). | Tinggi di awal (CapEx hardware), sangat murah secara jangka panjang (OpEx). |
| **Sanitasi Lingkungan** | Terjamin (100% ephemeral VM direset tiap job). | Berbahaya jika script cleanup keychain/derived data gagal dieksekusi. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. App Store Connect API Processing Hanging (Timeout Failure)
* **Symptom:** Lane `upload_to_testflight` hang lebih dari 30 menit saat fase *"Waiting for App Store Connect to process the build"*.
* **Root Cause:** Apple backend mengalami pipeline congestion internal, atau binary memicu review statis otomatis yang memerlukan waktu analisis struktural (misalnya: integrasi framework binary privat tanpa izin).
* **Mitigation:** Konfigurasikan `skip_waiting_for_build_processing: true` pada `upload_to_testflight` untuk melepaskan runner pipeline segera setelah upload file `.ipa` berhasil dikonfirmasi. Gunakan webhook independen via Apple App Store Connect Events API untuk mendeteksi kesiapan pengujian.

### 2. Transitive Entitlements & App Extension Bundle ID Mismatch
* **Symptom:** Output kompilasi sukses, namun deployment gagal saat eksekusi `xcodebuild -exportArchive` dengan error:
  `Provisioning profile "..." doesn't match the entitlements file's value for the application-identifier entitlement.`
* **Root Cause:** Target App Extensions (misalnya Notification Service) tidak memiliki bundle identifier yang berakar langsung pada Target Container Bundle ID utama. Contoh: Parent adalah `com.bankneo.app`, namun Extension didefinisikan sebagai `com.bankneo.ext` alih-alih `com.bankneo.app.notification`.
* **Mitigation:** Pastikan standarisasi hierarki namespace Bundle ID dan verifikasi bahwa setiap target terdaftar secara independen di dalam array `app_identifier` pada `Matchfile`.

### 3. macOS Transient Keychain Locking
* **Symptom:** Command `codesign` berhenti merespons (hang) atau mengeluarkan error: `errSecInternal